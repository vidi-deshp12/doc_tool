# Plan: Retry Policy and Failure Recovery

## Goal

Three separate weaknesses in the summarize path all come from the same shortcut: every failure is
treated as "the provider was busy".

1. **Retry is per-backend, fixed, and blind.** `bob_shell.py` sleeps 5 s twice. Each HTTP backend
   about to be written would have to grow its own loop, and none of them would read
   `Retry-After`, which is the provider telling you exactly how long to wait.
2. **One failure poisons its ancestors.** A failed node becomes `[needs_human_review]` with
   `hash_input=""`, but that placeholder *text* is handed to its parent as a child summary
   (`hierarchy.py:465`). The module summarizes a leaf called `[needs_human_review]`, then the package
   summarizes that module, then the system overview summarizes the packages — and all of them are
   written to `summaries.json` as if they were fine.
3. **A long run is not resumable.** `_run_summarize` calls `write_summaries` exactly once, after
   `run_hierarchy` returns (`cli.py:250-300`). Ctrl-C, a crash, or an abort at minute 25 loses every
   summary already paid for — the 234-call run in `docs/BOB_LOG.md` took 25 minutes sequentially.

This plan moves failure handling out of the backends and into the driver: one typed error, one retry
loop that obeys the provider, one checkpoint after every slice, and a repair pass that fixes what the
retry loop could not **before** ancestors are written.

**Done when:**

- A 429 carrying `retry-after: 17` waits ~17 s and succeeds, instead of burning 5 s twice and writing
  a placeholder.
- A 401 or an unknown model aborts immediately with the node id and the provider's message, instead
  of producing 234 placeholders. A context overflow is **not** fatal — it fails that one node and the
  run continues (amendment 4).
- Ctrl-C mid-run leaves `summaries.json` containing every completed *slice* (not just batch), and the
  next run makes calls only for the rest.
- A node that cannot be retried (context overflow, truncated output) is attempted once and reported,
  not retried three times.
- With `--workers 4`, one worker's `Retry-After` pauses the others too, so the group behaves like one
  polite client instead of four independent ones.
- A leaf that fails pass 1 but succeeds on the repair pass yields real prose for its module, package
  and system; untouched siblings make zero calls.
- No backend contains a retry loop.
- The retry tests assert the delays and never sleep (injected sleep).

---

## Current state (verified, not assumed)

| Location | Today |
|---|---|
| `bob_shell.py:41-42` | `_RETRY_ATTEMPTS = 2`, `_RETRY_SLEEP_S = 5` |
| `bob_shell.py:205-223` | loop around `_call_bob`, catches only `BobShellError`, `time.sleep(5)` flat |
| `hierarchy.py:379-408` | `_call_summarizer`: blanket `except Exception` → `WARN` + placeholder, `hash_input=""` |
| `hierarchy.py:465` | `child_summaries=[results[c.id] for c in children if c.id in results]` — placeholders included verbatim |
| `cli.py:250-300` | `_run_summarize`: one `run_hierarchy` call, one `write_summaries` at the end |
| `cli.py:502-517` | `_run_update`: same shape |
| `cli.py:224-248` | `_build_summarizer`: `BobShellSummarizer(...)` raises from `__init__` when `BOB_API_KEY` is unset — outside the try that will map failures to exit 2 |
| `bob_shell.py:_call_bob` | the failure's shape is only visible as a string; nothing classifies auth vs busy |

A repo-wide search for `BackendError|retry_after|Retry-After|fixpoint` returns **0 matches**: none of
this exists yet, in code or in a plan.

### Amendments from the plan review (2026-11-15)

This plan was reviewed against the code, and twelve changes are folded in below, marked
`(amendment N)` where they land:

1. **Checkpoint granularity.** The leaf batch is ~170 of 234 nodes, so batch-level checkpointing can
   still lose 20 minutes. Split each batch into deterministic slices (`checkpoint_every=25`).
2. **Unbound `err` in `_call_summarizer`.** With `--retries 0` the loop body never runs and the
   final `err.message` raises `NameError`. Clamp to one attempt and reject negative `--retries`.
3. **Auth errors raised in `__init__` bypass the retry loop.** `_build_summarizer` must be inside the
   `FatalBackendError` handling, or a missing key prints a traceback and exits 1.
4. **Context overflow must not abort the run.** Split `fatal` from `transient` in `BackendError`:
   auth/config is fatal, context overflow / truncated output fails only that node.
5. **`_FATAL_STDERR` is too broad.** A transient proxy 404 matches `"not found"`; narrow it to
   auth-shaped strings and match `model not found` only when `model` is present.
6. **Errors name the exception class.** `str(exc)` alone cannot distinguish a provider failure from a
   bug in the prompt builder; a bug would otherwise burn every attempt looking like flakiness.
7. **`parse_retry_after` uses `email.utils.parsedate_to_datetime`** instead of hand-rolled formats.
8. **Shared cooldown for 429s.** A `RetryGate` so one worker's `Retry-After` gates the others instead
   of four workers each burning their own attempts against the same exhausted window.
9. **Per-node sleep budget** (`max_node_sleep`) so a 120 s header cannot park a worker for an hour.
10. **`--strict` counts missing summaries**, not only placeholders: after a fatal abort the checkpoint
    holds no failures, so the old definition would exit 0 on an incomplete run.
11. **`repair_passes` defaults to 1 and gets a flag** (`--repair-passes`), so the worst case is 8
    attempts per node, not 12. The report line "written from a placeholder child" is dropped: it
    needs the degraded flag decision 8 rejects, and a successful repair makes it moot.
12. **Checkpoints are skipped when nothing changed in a slice**, so a zero-call replay does not
    rewrite the file once per slice.

---

## Sub-task 1 — `BackendError`, `FatalBackendError`, single-attempt contract

**Intent:** one error type that carries everything the driver needs to decide what to do, so the
driver — not each backend — owns retry policy.

**Expected outcomes:**

- Backends raise `BackendError` and perform exactly one attempt.
- Unknown exception types are still handled (treated as transient).
- `except BobShellError` in existing tests keeps working.

**Todo list:**

1. In `src/docgen/summarize/base.py`, add:

   ```python
   class BackendError(Exception):
       """A provider failure, classified for the driver's retry policy.

       transient=True   → the driver may wait and retry the same request.
       transient=False  → retrying this request cannot help.
       fatal=True       → configuration/auth/shape problem: stop the whole run (exit 2).
       fatal=False      → this node only: write a placeholder and continue the run.
       retry_after      → seconds the provider asked us to wait (HTTP Retry-After).
       """
       def __init__(self, message, *, transient=True, fatal=False, retry_after=None):
           super().__init__(message)
           self.message = message
           self.transient = transient
           self.fatal = fatal
           self.retry_after = retry_after
   ```

   Three flags, not two, because "do not retry this request" and "abort the whole run" are different
   decisions (amendment 4). A 401/403, an unknown model, or a missing key is
   `transient=False, fatal=True`. A context overflow or a `max_tokens` truncation is
   `transient=False, fatal=False`: one attempt, a placeholder, counted by `--strict`, skipped by the
   repair pass. The defaults stay permissive — `transient=True, fatal=False` — because an
   unclassified failure in a subprocess is far more often a hiccup than a misconfiguration, and one
   wasted retry beats a hole.

2. Add `FatalBackendError(Exception)` with `node_id` and `cause: BackendError`. It lives here rather
   than in `hierarchy.py` so `cli.py` can catch it without importing the driver's internals.

3. Add `parse_retry_after(value: str | None, *, now: float | None = None) -> float | None`:
    - numeric → `max(0.0, float(value))`, rejected if not finite (`nan`/`inf`);
    - HTTP-date → `max(0.0, parsed - now)` via `email.utils.parsedate_to_datetime`, which covers
      IMF-fixdate plus the two obsolete RFC 850 / asctime forms (amendment 7);
    - `None`, `""`, or unparseable → `None` (the driver falls back to backoff).

   `parsedate_to_datetime` returns a naive datetime for the obsolete forms; assume UTC when
   `tzinfo is None`, and take `now` from `time.time()` when it is not injected.

4. Update the `Summarizer` protocol docstring: `summarize` performs **one** attempt and raises
   `BackendError`; the driver owns retries, backoff, and sleeping. Keep the existing "must send
   `build_prompt(req)` verbatim" contract unchanged.

**Relevant context:** `base.py` already holds `SummaryRequest`/`SummaryResult`/`Summarizer`, so this
adds no new module.

---

## Sub-task 2 — `bob_shell` classifies instead of retrying

**Intent:** delete the backend's loop; make `_call_bob` say *why* it failed.

**Expected outcomes:**

- `BobShellSummarizer.summarize` calls `_call_bob` once.
- Auth-looking failures abort the run instead of being retried 4 times.

**Todo list:**

1. Delete `_RETRY_ATTEMPTS`, `_RETRY_SLEEP_S`, and the retry loop in `summarize()`. Drop
   `import time` if it becomes unused.
2. Keep `class BobShellError(BackendError)` so existing `except BobShellError` sites and test imports
   still work.
3. Classify in `_call_bob`, where stderr is visible:

   | failure | transient | fatal | retry_after |
   |---|---|---|---|
   | `subprocess.TimeoutExpired` | yes | no | — |
   | exit ≠ 0, stderr matches `_FATAL_STDERR` (auth / api key / unauthorized / 401 / 403 / login) | **no** | **yes** | — |
   | exit ≠ 0, stderr contains `model not found` (with `model`) | **no** | **yes** | — |
   | exit ≠ 0, anything else | yes | no | — |
   | stdout not valid JSON (truncated pipe) | yes | no | — |
   | `status != "success"` | yes | no | — |
   | `last_message` missing (unexpected shape) | yes | no | — |
   | `bob` not on PATH, `BOB_API_KEY` unset (raised in `__init__`) | **no** | **yes** | — |

   `_FATAL_STDERR` is a module-level tuple of lowercase substrings with a comment saying it is a
   heuristic; it only decides "stop the run", never "succeed". `"not found"` must not be in it on
   its own: a proxy can return a 404 HTML page for a URL that exists, and that is transient
   (amendment 5). `"model"` and `"not found"` are matched as a pair instead.

---

## Sub-task 3 — one retry loop, in `_call_summarizer`

**Intent:** a single policy for every backend, honouring the provider's own timing.

**Expected outcomes:**

- `Retry-After` is obeyed when present; exponential backoff otherwise; jitter; caps.
- Sleeps are logged so a long run does not look hung.
- Tests can assert delays without waiting.

**Todo list:**

1. In `base.py`, add:

   ```python
   @dataclass(frozen=True)
   class RetryPolicy:
       max_attempts: int = 4          # 1 initial + 3 retries
       base_delay: float = 2.0
       max_delay: float = 60.0        # cap for computed backoff
       max_retry_after: float = 120.0 # cap for a provider-supplied Retry-After
       max_node_sleep: float = 300.0  # total seconds one node may spend waiting
       jitter: float = 0.5            # sleep = delay * (1 + random()*jitter)

       def delay_for(self, attempt: int, retry_after: float | None) -> float: ...
   ```

   `delay_for`: `retry_after` if present (clamped to `max_retry_after`), else
   `min(base_delay * 2**attempt, max_delay)`; then multiply by `1 + random.random() * jitter` when
   the delay is positive. Jitter is applied on top of a provider's number too — waiting slightly
   longer is always safe, and it stops four workers waking in lockstep.

   `max_node_sleep` bounds the *sum* of a node's waits, not any single wait (amendment 9). Without
   it, `max_attempts × (1 + repair_passes) × max_retry_after` = 4 × 2 × 120 s per node is a plausible
   hour for one unlucky node; with it, a node that has already waited 300 s stops instead of parking
   its worker again. The remaining attempts are simply not made and the node lands as a placeholder.

   Also in `base.py`, one shared cooldown object (amendment 8):

   ```python
   class RetryGate:
       """A shared 'do not call before T' so parallel workers cool down together.

       One worker's 429 with retry-after: 20 otherwise leaves the other three
       hammering the same window, each burning its own four attempts.
       """
       def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
           self._clock = clock
           self._not_before = 0.0
           self._lock = threading.Lock()

       def defer(self, seconds: float) -> None:
           with self._lock:
               self._not_before = max(self._not_before, self._clock() + seconds)

       def wait(self, sleep: Callable[[float], None]) -> float:
           with self._lock:
               delay = self._not_before - self._clock()
           if delay > 0:
               sleep(delay)
               return delay
           return 0.0
   ```

   `run_hierarchy` creates one gate per run and passes it to every worker; `gate=None` (the default)
   disables it, which is what the unit tests use.

2. Rewrite `_call_summarizer(summarizer, req, cache_key, policy, sleep, gate=None)`. It now returns
   `(SummaryResult, retryable)` — the flag tells the repair pass whether a placeholder is worth
   another attempt:

   ```python
   attempts = max(1, policy.max_attempts)      # amendment 2: --retries 0 is one attempt
   spent = 0.0
   last_err: BackendError | None = None

   for attempt in range(attempts):
       if gate is not None:
           gate.wait(sleep)                     # shared cooldown (amendment 8)
       try:
           result = summarizer.summarize(req)
           return SummaryResult(..., hash_input=cache_key), True
       except Exception as exc:
           last_err = exc if isinstance(exc, BackendError) else BackendError(
               f"{type(exc).__name__}: {exc}"     # amendment 6
           )
           if last_err.fatal:
               raise FatalBackendError(req.node_id, last_err) from exc
           if not last_err.transient:
               break                             # context overflow: this node only
           if attempt == attempts - 1:
               break
           delay = policy.delay_for(attempt, last_err.retry_after)
           if spent + delay > policy.max_node_sleep:   # amendment 9
               print(f"  WARN: {req.node_id!r} retry budget exhausted "
                     f"({spent:.0f}s spent)", file=sys.stderr)
               break
           spent += delay
           if gate is not None and last_err.retry_after is not None:
               gate.defer(delay)
           print(f"  RETRY {req.node_id!r} in {delay:.1f}s "
                 f"[attempt {attempt + 1}/{attempts}]: {last_err.message}",
                 file=sys.stderr)
           sleep(delay)

   print(f"  WARN: {req.node_id!r} not summarized: {last_err.message}", file=sys.stderr)
   return placeholder, last_err.transient
   ```

   Behaviour changes to record: the WARN is now the *give-up* case (not only exhausted retries), the
   attempt count is clamped so `err` always exists, every wait is announced, and an unknown exception
   names its class.

3. Thread the knobs through the driver:

   ```python
   def run_hierarchy(..., max_workers: int = 1,
                     retry: RetryPolicy = RetryPolicy(),
                     sleep: Callable[[float], None] = time.sleep,
                     checkpoint: Callable[[list[SummaryResult]], None] | None = None,
                     checkpoint_every: int = 25,
                     repair_passes: int = 1) -> list[SummaryResult]:
   ```

   All new parameters are trailing with defaults, so existing call sites and tests keep working.

**Note on concurrency:** a sleep occupies a worker thread. With `--workers 4` against a provider
returning `retry-after: 20`, all four slots park. That is correct behaviour (the alternative is
hammering a provider that just said no) and it is why `max_retry_after` exists — a 900 s header must
not silently turn a 25-minute run into a 3-hour one.

The gate changes the failure mode this used to have: without it, four workers each discover the same
429 and each spend four attempts inside it. With it, the first `retry_after` defers the whole group,
so a 30 RPM free tier behaves like one client at 30 RPM rather than four clients at 120 RPM that are
all being rejected. The gate only ever sleeps *longer*; it never shortens a backoff.

---

## Sub-task 4 — checkpoint after every slice

**Intent:** a run that dies keeps what it has. This also makes sub-task 5's abort safe.

**Expected outcomes:**

- `summaries.json` is updated atomically after each slice, from the main thread only.
- An interrupted run's file loads cleanly and seeds the next run's cache.

**Todo list:**

1. `run_hierarchy` gains `checkpoint` and `checkpoint_every` (default 25). Split each depth batch
   into consecutive slices of at most `checkpoint_every` nodes — `batched_topological_order` is
   untouched, so the batch barrier and the submission order (and therefore the output) are
   unchanged. After each slice's results are merged into `results`, call
   `checkpoint(list(results.values()))` — cumulative, in bottom-up order. When `checkpoint is None`,
   skip the slicing entirely so existing tests and call sites behave exactly as today.

   **Why slices:** the leaf batch is ~170 of 234 nodes, so "after each batch" can still lose 20
   minutes (amendment 1). A slice of 25 bounds the loss to one small group of calls, and because the
   merge order is unchanged, byte-identical output is preserved.
2. In `cli.py`, add one helper used by both `_run_summarize` and `_run_update`:

   ```python
   def _checkpoint_writer(path: Path):
       def write(partial):
           tmp = path.with_suffix(".json.tmp")
           write_summaries(partial, tmp)
           os.replace(tmp, path)        # atomic on the same volume, works on Windows
       return write
   ```

   Pass it as `checkpoint=_checkpoint_writer(summaries_path)`.
3. Keep the final `write_summaries` call. It is the authoritative write; the checkpoint only ever
   holds a prefix.
4. Document the partial-file semantics in the `run_hierarchy` docstring: the file contains the
   completed slices and **no** system node until the run finishes; `read_summaries` tolerates any
   subset. A later `render` on a partial file writes pages with `_(no summary yet)_`; that guard
   belongs to the render work (roadmap item C), not this plan.
5. `_checkpoint_writer` keeps the serialized bytes of its last write and returns early when the new
   payload is identical, so a zero-call replay does not rewrite the file once per slice
   (amendment 12).

**Cost:** one write per slice — ~10 for 234 nodes at 25/slice — of ≤350 KB each, and none at all on a
cached replay. Writes happen on the main thread between slices, so they can never interleave with a
worker.

---

## Sub-task 5 — fatal aborts, exit codes, `--strict`

**Intent:** distinguish "the provider is busy" from "your config is wrong" — which is most of what an
OSS user actually hits.

**Expected outcomes:**

- Wrong key / unknown model: one line naming the node and the provider's message, exit 2, work so far
  on disk.
- Leftover placeholders: normal exit 0 with a count; `--strict` makes it exit 1.

**Todo list:**

1. Wrap `_build_summarizer` **and** both `run_hierarchy` call sites in the same handler:

   ```python
   try:
       backend, summarizer = _build_summarizer(args, output_dir)   # amendment 3
       results = run_hierarchy(...)
   except FatalBackendError as exc:
       print(f"docgen summarize: fatal backend error at {exc.node_id}: "
             f"{exc.cause.message}", file=sys.stderr)
       raise SystemExit(2)
   ```

   `_build_summarizer` must be inside: `BobShellSummarizer.__init__` raises when `BOB_API_KEY` is
   unset, and the OpenAI/Anthropic backends will raise there for a missing package or key. For
   construction failures `FatalBackendError.node_id` is `"<backend>"`. Because of sub-task 4, the
   completed slices are already in `summaries.json`.
2. After the run, print the recovery report:

   ```
     summaries written: 234 (231 fresh, 3 from cache)
     3 node(s) need human review: <id>, <id>, <id>
     summary complete: 234/234 nodes
   ```

   The third line is what makes `--strict` legible: a fatal abort leaves a short count and no
   failures, exactly the case the old report could not show (amendment 10). The old "written from a
   placeholder child" line is dropped — it would need the degraded flag decision 8 rejects, and a
   successful repair makes it moot (amendment 11).

3. Exit codes: `0` clean; `1` under `--strict` when **either** placeholders remain **or** a
   summarizable node is missing from the results (mirrors `validate`/`check`, where 1 means "found
   something"); `2` fatal backend error. "Missing" is computed against
   `summarizable_node_ids(graph) | {SYSTEM_NODE_ID}`, exported from `hierarchy.py` using the same
   `_SUMMARIZABLE` set as `batched_topological_order`, so the two cannot drift.
4. Flags, on both `summarize` and `update`: `--retries N` (default 3; `--retries 0` = one attempt;
   negative values rejected by an argparse `_non_negative_int` type) →
   `RetryPolicy(max_attempts=N + 1)`; `--strict` (store_true); `--repair-passes N` (default 1, also
   `_non_negative_int`).
5. Document the parallel case: a fatal raised inside a worker surfaces at the batch barrier via
   `future.result()`; `ThreadPoolExecutor.__exit__` waits for in-flight calls, so up to
   `max_workers` extra calls may complete and be discarded. No partial slice is written.

---

## Sub-task 6 — repair pass (the poisoning fix)

**Intent:** every ancestor of a repaired node must be rebuilt from the repaired prose within the same
run, and nothing else may be re-called.

**Expected outcomes:**

- A leaf that succeeds on the repair pass yields non-placeholder prose for its module, package and
  the system overview.
- Siblings and unrelated subtrees make zero calls.
- A permanently failing node cannot spin the loop.

**Todo list:**

1. Extract the body of `run_hierarchy` into a private `_run_pass(...) -> tuple[dict[str,
   SummaryResult], set[str]]`: the second value is the set of node ids that failed *non-retryably* (context
   overflow, truncation) and must not be attempted again. It takes the seed cache and writes into a
   fresh `results` dict, including the system node. No behaviour change to pass 1.
2. Drive it:

   ```python
   results, unretryable = _run_pass(seed=existing_cache)
   for attempt in range(repair_passes):
       failed = [
           n for n in order
           if results[n.id].backend == NEEDS_HUMAN_REVIEW_BACKEND and n.id not in unretryable
       ]
       if not failed:
           break
       print(f"  repair pass {attempt + 1}: retrying {len(failed)} node(s) …", file=sys.stderr)
       results, more = _run_pass(seed={**existing_cache, **results})
       unretryable |= more
   ```

   `order` is the flattened bottom-up batch order already produced by
   `batched_topological_order`. Skipping `unretryable` is what keeps a context-overflow node from
   spending a second pass proving it still does not fit (amendment 4).

3. Why re-running the whole pass is correct, and cheap:
   - a placeholder has `hash_input=""`, which can never equal a computed key, so failed nodes are
     always called;
   - seeding with the run's own results means every node whose inputs are unchanged hits its key and
     makes no call;
   - a repaired child changes its parent's prompt, so the parent's key changes, so the parent is
     recomputed — and its change cascades to package and system in the same bottom-up pass;
   - no dependency tracking is needed: the cache key **is** the dependency graph (D-047). This is the
     step that was not available before the prompt-hash key landed.

4. Bounds: `repair_passes=1` by default (`--repair-passes` to raise it), and the loop is `for`,
   never `while`. Worst case attempts per node is `max_attempts × (1 + repair_passes)` = 8, and worst
   case waiting is bounded again by `max_node_sleep`; state both in the docstring, since they are the
   upper bound on how long a badly rate-limited run can take.

5. Do **not** add a "degraded" flag to parent results. The key already guarantees the parent
   re-summarizes the moment the child becomes real; a flag would need its own invalidation rules,
   which is exactly the hand-maintained-proxy design 2b.9b removed. Record this as a decision.

---

## Sub-task 7 — tests

New `tests/test_retry.py` (all delays asserted through an injected `sleep`; nothing sleeps):

1. `test_parse_retry_after_seconds` — `"17"` → 17.0, `"0"` → 0.0, `"-5"` → 0.0.
2. `test_parse_retry_after_http_date` — a date 30 s ahead (fixed `now=`) → ~30; a past date → 0.0.
3. `test_parse_retry_after_garbage` — `None`, `""`, `"soon"` → `None`.
4. `test_plain_exception_is_transient` — a summarizer raising `RuntimeError` is retried, then
   succeeds; result carries the real key.
5. `test_retry_honours_retry_after` — raises `BackendError(retry_after=12)` once, then succeeds with
   `jitter=0` → `sleeps == [12.0]`, two calls.
6. `test_backoff_without_header` — `jitter=0, base=2, max_attempts=4`, always failing →
   `sleeps == [2.0, 4.0, 8.0]`.
7. `test_backoff_is_capped` — `base=100, max_delay=60` → `[60.0, 60.0, 60.0]`.
8. `test_retry_after_is_capped` — `retry_after=999, max_retry_after=120` → `[120.0]`.
9. `test_exhausted_retries_produce_placeholder` — always transient → exactly `max_attempts` calls,
   placeholder text, `hash_input == ""`.
10. `test_fatal_error_aborts` — `BackendError(transient=False, fatal=True)` → `FatalBackendError`
    propagates with the node id; exactly one call; no placeholder in the results.
11. `test_fatal_error_in_parallel_batch_aborts` — `max_workers=4`, one fatal → still raises.
12. `test_backend_does_not_retry` — patch `_call_bob` to raise twice then succeed;
    `BobShellSummarizer.summarize` calls it **once** and raises. Proves the loop moved up.

`tests/test_hierarchy.py` additions:

13. `test_checkpoint_after_each_slice` — checkpoint receives one call per slice, cumulative lengths
    grow; the collected final list equals the returned results minus the system node.
14. `test_crash_mid_run_keeps_completed_slices` — summarizer raises a *fatal* error at the third
    leaf; after the `FatalBackendError`, the checkpointed list holds the completed slices; reloading
    it and re-running calls only the remaining nodes.
15. `test_repair_pass_recovers_failed_leaf` — one leaf fails on its first appearance and succeeds
    afterwards; assert the final module/package/system texts are real, and the call log contains the
    leaf, its module, its package and `system`, but no untouched sibling.
16. `test_repair_passes_are_bounded` — permanently failing leaf → exactly `repair_passes` extra
    attempts, ancestors recomputed at most that many times, run still returns (placeholders, not an
    exception).
17. `test_no_repair_pass_when_nothing_failed` — call count identical to a clean run.
18. `test_repair_preserves_determinism` — workers 1 vs 4 with a repair: identical list order and
    identical texts.
19. `test_retry_gate_shared_cooldown` — `defer(10)` then `wait` sleeps ~10 through the injected sleep;
    a second `wait` inside the window sleeps only the remainder.
20. `test_node_sleep_budget_stops_retries` — `retry_after=60`, `max_node_sleep=5` → one call, no
    sleep, placeholder.
21. `test_context_overflow_is_not_fatal` — `BackendError(transient=False, fatal=False)` → one call,
    placeholder, run returns normally, and the node is absent from the repair pass's retry list.
22. `test_checkpoint_is_sliced` — one depth with 7 nodes, `checkpoint_every=2` → checkpoint calls
    with cumulative lengths 2, 4, 6, 7, and no write when a slice makes zero calls.
23. `test_unknown_exception_names_its_class` — a summarizer raising `KeyError("x")` produces a WARN
    containing `KeyError`.

Existing tests that must change (all inside files already touched):

- `tests/test_bob_shell.py` — the two-attempt retry test becomes
  `test_summarize_makes_one_attempt` (asserts one `_call_bob` call and a raised `BackendError`);
  the missing-key test now asserts `isinstance(exc, BackendError) and exc.fatal`; import-error
  unchanged.
- `tests/test_summarize.py` — add: `--strict` exit 1 with a placeholder; `--retries 0` reaching the
  backend once; a fatal error from `_build_summarizer` (missing key) exiting 2 with no traceback;
  `--retries -1` rejected by argparse; and `--strict` exit 1 when a summarizable node is absent from
  the results even though no placeholder exists.
- `tests/test_hierarchy.py::test_parallel_exception_handling` and any other failure-exercising test —
  pass `retry=RetryPolicy(max_attempts=1)` and `sleep=lambda _: None` so they stay fast and keep
  asserting "one failure → one placeholder".

---

## Verification

1. `PYTHONPATH=src python -m pytest tests/test_retry.py tests/test_hierarchy.py tests/test_bob_shell.py tests/test_summarize.py -q`,
   then the full suite (expect the one known `test_seeded_bug` failure and nothing else).
2. Fault injection without a provider: a `FlakySummarizer` script that fails the first N leaves with
   `BackendError(retry_after=1)` and then one node on every pass. Assert: one RETRY line, one repair
   pass, a final placeholder, and that the parents were re-called exactly once.
2b. Missing key: `BOB_API_KEY` unset, `docgen summarize --backend bob_shell` exits 2 with one line
   naming the backend, prints no traceback, and leaves an existing `summaries.json` untouched.
3. Cache neutrality: on unchanged `target/` with the fresh `summaries.json`,
   `docgen summarize --backend bob_shell --workers 4` must make **0 calls** — this is the regression
   guard proving the pass/repair restructure did not change a single cache key, and it must also
   confirm the checkpoint writer skipped every write.
4. `docgen summarize --strict` exits 0 on the clean cache, and exits 1 after deleting one summary
   from `summaries.json` (no placeholder present — the missing-node case).
5. Once the OpenAI backend exists: `--workers 4` against Groq's free tier (30 RPM, 8k TPM) and
   confirm the log shows honoured waits and no placeholders.

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/base.py` | `BackendError` (with `fatal`), `FatalBackendError`, `RetryPolicy` (with `max_node_sleep`), `RetryGate`, `parse_retry_after`; protocol docstring → single attempt |
| `src/docgen/summarize/bob_shell.py` | delete `_RETRY_*` and the loop; classify failures in `_call_bob`; `BobShellError(BackendError)` |
| `src/docgen/summarize/hierarchy.py` | retry loop in `_call_summarizer`; slice chunking; `_run_pass`; checkpoint; repair passes; `summarizable_node_ids`; end-of-run report |
| `src/docgen/cli.py` | `--retries`, `--strict`, `--repair-passes` on `summarize` + `update`; checkpoint writer; `_build_summarizer` inside the fatal handler; `FatalBackendError` → exit 2; strict → exit 1 |
| `tests/test_retry.py` | New — 12 tests |
| `tests/test_hierarchy.py` | 11 new tests + existing failure tests updated |
| `tests/test_bob_shell.py` | retry test replaced by single-attempt test |
| `tests/test_summarize.py` | 5 CLI cases |
| `docs/plan-pluggable-llm-backends.md` | one-line pointer + supersede its "2 attempts, 5 s" retry decision |
| `docs/tasks.md`, `docs/memory.md`, `docs/BOB_LOG.md` | task entry, decision, session log |

## Not touched

`prompts.py`, `summarize/store.py`, `summarize/citations.py`, `render/`, `check/`, `extract/`, the
Bob Shell transport (`_call_bob`'s PowerShell/temp-file mechanics), and `openai_backend.py` /
`anthropic_backend.py` — those are written later and simply raise `BackendError`.

---

## Dependency order

```
1 BackendError ──► 2 bob_shell ──► 3 driver retry ──► 4 checkpoint ──► 5 abort/exit codes
                                                          └──────────► 6 repair pass
```

4 before 5: aborting without a checkpoint throws away the run. 3 before 6: the repair pass is just
another traversal of the same retry policy.

---

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Fatal errors abort the run (exit 2) instead of writing placeholders | "Your key is wrong" must not silently produce 234 holes; the retry loop cannot fix it |
| 2 | `--strict` exits 1 when placeholders remain | Matches `validate`/`check`, where 1 means "found something" |
| 3 | `max_attempts=4`, `base=2`, `max_delay=60`, `max_retry_after=120`, `jitter=0.5` | 14 s of backoff for a blip; a 2-minute ceiling on a provider's own number |
| 4 | `repair_passes=1`, raised by `--repair-passes` | Enough to ride out one bad minute; bounded worst case of 8 attempts per node |
| 5 | `BobShellError` stays, as a `BackendError` subclass | No test churn, message text preserved |
| 6 | Checkpoint via `summaries.json.tmp` + `os.replace` | Atomic on the same volume, correct on Windows |
| 7 | Unknown exceptions are transient | A subprocess hiccup is far likelier than a config error; one wasted retry beats a hole |
| 8 | No "degraded parent" flag | The prompt-hash key already invalidates exactly the affected ancestors |
| 9 | Context overflow and truncation are per-node failures (`fatal=False`), not fatal | One oversized module must not abort a 2,000-file run; "234 placeholders" is not the only bad outcome |
| 10 | `max_node_sleep=300` | Bounds one node's waiting independently of `max_attempts × max_retry_after`, which would otherwise reach an hour |
| 11 | One shared `RetryGate` per run | Four workers each discovering the same 429 is four clients, not one; the gate makes a free tier behave like one |
| 12 | Checkpoint every 25 nodes, and skip identical writes | The leaf batch is ~170 nodes, so batch-level checkpointing loses most of its value; identical rewrites are pure noise |
| 13 | `--strict` counts missing nodes as well as placeholders | A fatal abort leaves neither failures nor a complete file; the old definition would pass it |

**Resolved in review:** `--retries` governs every attempt, including repair passes (one policy); the
checkpoint does not `fsync` (the write is atomic, and durability against power loss is not a goal).
**Still open:** whether `repair_passes` should be 2 for hosted providers — it stays 1 until the Groq
observation in Verification 5 says otherwise.

---

## Risks and interactions

- **Worker slots during backoff.** Sleeps park threads; with 4 workers and 20 s waits, throughput is
  capped at ~4 calls per 20 s regardless of the provider's RPM. Correct, but it makes the worker count
  look ineffective — worth one line in the log (already planned).
- **System node recompute.** It is rebuilt in every pass because its key covers all package texts.
  That is one call per pass at most, and zero when nothing changed.
- **Partial files.** A checkpointed file has no system node; `render` would produce a page with a
  missing overview. Guarding `render` is roadmap item C (it must not write a manifest for a partial
  file); until then, `check` reports drift afterwards.
- **Truncated output.** A reply cut at `max_tokens` can end mid-sentence and still parse. Classifying
  it as a per-node failure rather than a success is what stops half a paragraph from being cited as
  prose; this plan supplies the classification, the backends supply the detection (`finish_reason` /
  `stop_reason`).
- **Gate pessimism.** One bad `Retry-After` defers healthy workers too. That is the intent, but a
  900 s header (clamped to 120 s) costs the whole run up to two minutes of throughput.
- **Determinism.** Assembly order is unchanged (submission order within a batch, batches in order), so
  `summaries.json` stays byte-identical across worker counts — including after a repair pass, which
  must be covered by test 18.

## Out of scope

asyncio migration; scoping/budget flags (`--path`, `--max-nodes`, `--estimate`); prompt-size budgets;
per-batch ETA display beyond the retry/report lines above; provider token accounting.
