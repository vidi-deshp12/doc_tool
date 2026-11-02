# Plan: Parallel Summarization in run_hierarchy

**Status:** amended 2026-11-02 after review; awaiting approval. Not implemented.

## Goal

Replace the sequential node-by-node loop in `run_hierarchy` with a
batch-parallel loop that submits all nodes at the same depth of the CONTAINS
tree concurrently. Nodes at the same depth are fully independent — none of their
summaries feeds into another at that depth — so this is safe without any locking
on the results dict.

**Done when:**
- `run_hierarchy` accepts a `max_workers` parameter (default `1` = sequential,
  preserving existing behaviour).
- `docgen summarize --workers N` runs N concurrent summarizer calls per batch.
- The output (`list[SummaryResult]`) is identical regardless of `max_workers`,
  **including list order** (deterministic ordering, same content).
- All existing tests pass unchanged.
- New tests verify parallel correctness: (a) all nodes are summarized, (b) output
  is identical — element-by-element — to the sequential run, (c) a per-batch
  timing test shows N calls complete in ~1× not N× the single-call time (using a
  sleep-based stub).
- Bob Shell concurrency is verified on a small fixture (`--workers 4` vs
  `--workers 1`, same text and order) and once on the real target at
  `--workers 4`.
- Backend construction is factored into one helper shared by `summarize` and
  `update` (sub-task 4), so the upcoming pluggable-backends work has a single
  place to extend.

**Hard rules:**
- `max_workers=1` must be the default. Existing callers (tests, CLI) that do not
  pass `max_workers` are unchanged.
- No new dependencies. `concurrent.futures.ThreadPoolExecutor` is stdlib.
- **`results` is written by the main thread only.** Worker threads return a
  `SummaryResult`; they never mutate `results`. The main thread collects each
  batch in submission order, so no lock is needed and `summaries.json`'s array
  order is byte-identical to the sequential run.
- `_call_summarizer` already catches all exceptions and returns a
  `needs_human_review` placeholder — that contract is unchanged.
- Do not change prompt text or cache-key semantics in this phase. Every cached
  summary is already invalidated by the 2b.8 prompt-version bump; this phase
  must not add another reason to regenerate.

---

## The key insight: depth-based batching

`topological_order` returns a flat list in bottom-up order. To parallelise, we
need to group nodes by their depth in the CONTAINS tree so all nodes at depth D
can run concurrently while depth D+1 waits.

A new function `batched_topological_order` replaces `topological_order` as the
internal driver. It returns `list[list[Node]]` where each inner list is one
batch (all nodes at the same depth), ordered bottom-up:

```
Batch 0: all FUNCTION nodes (leaves — deepest)
Batch 1: all CLASS nodes + MODULE nodes that contain only functions
Batch 2: MODULE nodes that contain classes
Batch 3: PACKAGE nodes
System:  synthetic system node (always last, single node, never batched)
```

The depth of a node is: `max(depth(child) for child in children) + 1`, or 0
for leaf nodes. This is computed in one pass over the index with memoisation.

**Why depth, not NodeType?** A MODULE that contains only bare functions is at
depth 1; a MODULE that contains classes (which contain methods) is at depth 2.
Using NodeType directly would put them in the same batch, but the depth-2
MODULE must wait for its classes to complete. Depth is the correct signal.

---

## Corrections incorporated from the 2026-11-02 review

The first draft had four defects that would have broken tests or produced
nondeterministic output. The sub-tasks below already reflect the fixes; this
section records what changed and why.

| # | Original draft | Corrected plan |
|---|---|---|
| A | Workers write directly into `results`, justified by the GIL | Workers **return** a `SummaryResult`; the main thread assigns `results[node.id]` in submission order. Deterministic file order, no lock, no GIL argument. |
| B | `_run_summarize` passes `max_workers=args.workers` | `getattr(args, "workers", 1)` — `test_cli_summarize_hierarchy_e2e` builds a `Namespace` without `workers`. |
| C | `_run_update` passes `max_workers=args.workers` | Same `getattr`; the `update` subparser has no `--workers` flag at all (unless the open decision below changes that). |
| D | Timing test: 8 nodes, 4 workers, assert `< sequential / 2`, marked `@pytest.mark.slow` | 16 nodes, 4 workers, assert `< sequential * 0.6`; marker dropped (unregistered in `pyproject.toml`, skips nothing, test is < 1 s). |
| E | Failure test asserted the *first* call fails | Assert **exactly one** node is `needs_human_review`, whichever it is — thread completion order is nondeterministic; guard the counter with a lock. |
| F | Not in the draft | Document that backends must be thread-safe; the protocol is now called concurrently. |
| G | Not in the draft | `max_workers < 1` is clamped to `1`, so `--workers 0` degrades to sequential instead of raising. |

Measured on the real graph (233 summarizable nodes + system): depth batches are
**154 / 52 / 16 / 6 / 4 / 1**, with no topological violations. At 4 workers the
ideal schedule is ~60 rounds vs 234 sequential → ~3.8× (24 min → ~6 min); at
6 workers ~5.7× (~4 min). 88% of nodes sit in the first two batches, which is
why the batch barrier costs little here.

---

## Sub-task 1 — Add `batched_topological_order` [pending]

**Intent:** Replace `topological_order` with a version that returns batches.
The new function must produce the same nodes in a bottom-up-within-batch order
and must never put a parent in the same batch as any of its children.

**Expected outcomes:**
- `batched_topological_order(graph, index)` returns `list[list[Node]]`.
- Each batch contains nodes whose children (in the index) are all in earlier
  batches.
- Concatenating all batches in order produces a valid topological ordering
  (no parent before its children).
- Deterministic: same graph always produces the same batches.

**Todo list:**
1. Add `batched_topological_order(graph, index) -> list[list[Node]]` to
   `hierarchy.py`.

   Algorithm:
   ```python
   def _depth(node_id, index, memo):
       if node_id in memo:
           return memo[node_id]
       children = index.get(node_id, [])
       d = max((_depth(c.id, index, memo) for c in children), default=-1) + 1
       memo[node_id] = d
       return d

   summarizable = [n for n in graph.nodes if n.type in _SUMMARIZABLE]
   memo = {}
   depth_map = {n.id: _depth(n.id, index, memo) for n in summarizable}
   max_depth = max(depth_map.values(), default=0)

   batches = [[] for _ in range(max_depth + 1)]
   for n in sorted(summarizable):   # sort for determinism within a batch
       batches[depth_map[n.id]].append(n)
   return [b for b in batches if b]  # drop empty depths
   ```

2. Keep `topological_order` intact — it is used by existing tests and its
   flat list is still valid for `max_workers=1`. Do not remove it.

3. Add tests in `tests/test_hierarchy.py`:
   - `test_batched_order_children_before_parents`: assert no batch contains a
     node whose child is in the same or later batch.
   - `test_batched_order_is_deterministic`: same graph → same batches twice.
   - `test_batched_order_covers_all_nodes`: set of nodes in all batches ==
     set from `topological_order`.

**Relevant context:**
- [`src/docgen/summarize/hierarchy.py:145-184`](src/docgen/summarize/hierarchy.py) — `topological_order`
- [`src/docgen/summarize/hierarchy.py:115-142`](src/docgen/summarize/hierarchy.py) — `build_contains_index`

---

## Sub-task 2 — Parallelise `run_hierarchy` [pending]

**Intent:** Replace the sequential `for node in order` loop in `run_hierarchy`
with a `for batch in batches` outer loop. Within each batch, use
`ThreadPoolExecutor` when `max_workers > 1`, fall back to a plain loop when
`max_workers == 1`.

**Expected outcomes:**
- `run_hierarchy(..., max_workers=1)` behaves identically to the current code.
- `run_hierarchy(..., max_workers=4)` submits all nodes in a batch concurrently.
- `results` is only written by the main thread (workers return results; the main
  thread collects each batch before starting the next) — no race conditions and
  no lock.
- The `SummaryResult` list returned is in the same deterministic order as before
  (batch order, then system last) — identical list order, not merely the same
  set of nodes.

**Todo list:**
1. Add `max_workers: int = 1` parameter to `run_hierarchy`.

2. Replace the current sequential loop:
   ```python
   # current
   for node in order:
       ...
       results[node.id] = _call_summarizer(...)
   ```
   with a batched loop in which **workers return results and only the main
   thread writes `results`**:
   ```python
   batches = batched_topological_order(graph, index)

   for batch in batches:
       if max_workers <= 1 or len(batch) == 1:
           pairs = [(node, _process_node(node, ...)) for node in batch]
       else:
           with ThreadPoolExecutor(max_workers=max_workers) as pool:
               futures = [(node, pool.submit(_process_node, node, ...)) for node in batch]
               # Collect in submission order, not completion order: this keeps
               # summaries.json byte-identical to the sequential run.
               pairs = [(node, future.result()) for node, future in futures]
       for node, result in pairs:
           results[node.id] = result
   ```
   `_process_node` is a helper (or a closure) that returns a `SummaryResult`:
   cache hit → the cached result; cache miss → `_call_summarizer(...)`. It must
   not write to `results`.

   Note: `future.result()` in submission order blocks on the first future, but
   every future in the batch is already running, so the batch takes ~max(call
   time), not the sum. `as_completed` is deliberately not used because it would
   reorder the output.

3. **Thread safety:** `results` is a main-thread-only dict. No lock is needed
   and none should be added. The only shared objects read by workers are
   `existing_cache`, `index`, `edges_by_from`, `repo_root`, and the summarizer
   instance; all are treated as read-only. Add a note to the `hierarchy.py`
   module docstring (and the `Summarizer` protocol docstring if convenient) that
   `summarize()` may be called concurrently and implementations must be
   thread-safe. The three current backends are stateless per call.

4. `_process_node` reads `existing_cache`, `index`, `edges_by_from`,
   `prompt_version`, `repo_root`, and `results` for *child* lookups. Children are
   always in an earlier batch, so `results` is fully populated for them before
   the batch starts. It must not read `results` for nodes in its own batch — no
   node at a given depth depends on another node at that depth.

5. Clamp the worker count at the top of `run_hierarchy`:
   `max_workers = max(1, int(max_workers))`, so `0` or a negative value means
   sequential instead of raising from `ThreadPoolExecutor`.

6. **System node** is always processed sequentially after all batches complete.
   It needs all package results, which are in `results` at that point. No change
   to the system node logic.

7. Pass `max_workers` at both CLI call sites using
   **`getattr(args, "workers", 1)`** — not `args.workers`:
   - `_run_summarize`: `test_cli_summarize_hierarchy_e2e` builds
     `argparse.Namespace(config=..., backend="stub")` by hand, with no `workers`
     attribute.
   - `_run_update`: the `update` subparser has no `--workers` flag at all, so
     `args.workers` is always missing there.

8. Keep the `list[SummaryResult]` return shape: `list(results.values())` +
   `[system_result]` still yields batch order because the main thread inserts
   values in batch order.

**Relevant context:**
- [`src/docgen/summarize/hierarchy.py:286-366`](src/docgen/summarize/hierarchy.py) — `run_hierarchy`
- [`src/docgen/summarize/hierarchy.py:250-279`](src/docgen/summarize/hierarchy.py) — `_call_summarizer`

---

## Sub-task 3 — CLI `--workers` flag + tests [pending]

**Intent:** Expose `max_workers` as `--workers N` on the `summarize` subcommand.
Add tests that verify parallel correctness without needing a real LLM.

**Expected outcomes:**
- `docgen summarize --workers 4 --backend bob_shell` runs 4 concurrent calls per
  batch.
- `docgen summarize` (no flag) uses `max_workers=1` — sequential, no change.
- Test: output of `run_hierarchy(..., max_workers=4)` is identical to
  `run_hierarchy(..., max_workers=1)` on the same graph — **same list order**,
  same node IDs, same text, same `hash_input`.
- Test: with a `SlowStubSummarizer` that sleeps 0.05s, 16 independent nodes
  finish in under 60% of the sequential time with 4 workers (theoretical 4×,
  so the assertion has real headroom).
- `--workers 0` behaves like `--workers 1` (clamped).

**Todo list:**
1. Add `--workers` flag to the `summarize` subparser in `cli.py`:
   ```python
   summarize_parser.add_argument(
       "--workers",
       type=int,
       default=1,
       help=(
           "Number of parallel summarizer calls per batch "
           "(default: 1 = sequential). Values above 6 risk "
           "rate-limiting from hosted LLM APIs."
       ),
   )
   ```
2. Pass `max_workers=getattr(args, "workers", 1)` to `run_hierarchy` in
   `_run_summarize`.
3. Pass `max_workers=getattr(args, "workers", 1)` to `run_hierarchy` in
   `_run_update` (`getattr`, not `args.workers` — see sub-task 2, item 7).
4. Add tests in `tests/test_hierarchy.py`:

   **`test_parallel_output_matches_sequential`:**
   Build a graph with 8 function nodes in two modules. Run `run_hierarchy`
   with `max_workers=1` and `max_workers=4` using `StubSummarizer`. Assert the
   two returned lists are equal **element by element**: same `node_id` order,
   same `text`, same `backend`, same `hash_input`. Compare the lists directly
   (`parallel == sequential`), not as sets — order is part of the contract.

   **`test_parallel_batch_is_faster`:**
   Build a graph with 16 independent function nodes (all in one module, leaf
   level). Use a `SlowStubSummarizer` that sleeps 0.05s per call. Time
   `run_hierarchy` with `max_workers=4` vs `max_workers=1` using
   `time.perf_counter`. Assert `parallel < sequential * 0.6` — theoretical
   speedup is 4×, so this leaves >2.5× of scheduling headroom. Do **not** mark
   it `@pytest.mark.slow`: the marker is not registered in `pyproject.toml` and
   nothing skips it, and the test costs under a second.

   **`test_parallel_exception_handling`:**
   Build a graph with 4 nodes. Use a `FailingStubSummarizer` that raises on
   exactly one call and succeeds on the rest; because threads complete in
   nondeterministic order, count calls under a `threading.Lock` and fail exactly
   the call whose counter equals 1 rather than assuming which node is "first".
   Assert: all 4 nodes have a result (no exception escapes); **exactly one** has
   `backend == "needs_human_review"`; that entry has `hash_input == ""` so it is
   retried next run.

   **`test_workers_below_one_is_sequential`:**
   Run the same graph with `max_workers=0` and `max_workers=1`; assert the two
   result lists are identical. Guards the clamp in sub-task 2, item 5.

**Relevant context:**
- [`src/docgen/cli.py:598-619`](src/docgen/cli.py) — `summarize` subparser
- [`tests/test_hierarchy.py`](tests/test_hierarchy.py) — existing hierarchy tests

---

## Sub-task 4 — One summarizer factory for `summarize` and `update` [pending, added 2026-11-02]

**Intent:** `_run_summarize` and `_run_update` each build a backend with
different rules (`_run_summarize` supports `stub`/`manual`/`bob_shell` and honours
`--max-cost`/`--max-turns`; `_run_update` supports only `bob_shell` and silently
falls back to stub for anything else). `--workers` must be threaded through both,
so extract the duplication now rather than adding a third and fourth copy when
the OpenAI/Anthropic backends land.

**Expected outcomes:**
- One helper in `cli.py`, e.g.
  `_build_summarizer(args, output_dir) -> tuple[str, Summarizer]`, is the only
  place a backend is constructed. It returns `(backend_name, summarizer)` so
  `_run_update` can keep its `backend != "stub"` gate.
- `_run_summarize` and `_run_update` both call it.
- Documented backends behave exactly as today; the two silent behaviours become
  explicit (deltas below).
- Factory unit tests run without network or real Bob installs.

**Todo list:**
1. Add the helper:
   ```python
   def _build_summarizer(args, output_dir):
       backend = getattr(args, "backend", "stub")
       max_cost = float(getattr(args, "max_cost", 2.0))
       max_turns = int(getattr(args, "max_turns", 10))
       if backend == "stub":
           summarizer = StubSummarizer()
       elif backend == "manual":
           summarizer = ManualSummarizer(output_dir / "manual_summaries")
       elif backend == "bob_shell":
           summarizer = BobShellSummarizer(max_cost=max_cost, max_turns=max_turns)
       else:
           raise SystemExit(
               f"Unknown backend: {backend!r} "
               "(expected 'stub', 'manual', or 'bob_shell')."
           )
       return backend, summarizer
   ```
   Keep the imports local (as today) so `stub`/`manual` runs do not import the
   Bob Shell module.
2. `_run_summarize`: replace the `if/elif` chain with
   `backend, summarizer = _build_summarizer(args, output_dir)`; keep the existing
   `docgen summarize: … (backend=…)` line.
3. `_run_update`: resolve `backend` the same way, but construct lazily — only
   when `update_plan.nodes_to_resummarize` is non-empty and `backend != "stub"`.
   This preserves today's behaviour that a plain `docgen update` never requires
   `BOB_API_KEY`.
4. Accept or override these behaviour deltas (all consequences of one code
   path):
   - **Unknown backend in `update` now raises.** Today any name other than
     `bob_shell` silently becomes `StubSummarizer`. Raising is recommended;
     silent fallback is a bug magnet.
   - **`update --backend manual` now works.** It re-summarizes from
     `manual_summaries/` instead of silently using stub. Recommended. Alternative:
     keep an allowlist in `_run_update` if you want the old strictness.
   - **`update` passes `max_cost`/`max_turns` to `BobShellSummarizer`.** The
     `update` subparser has neither flag today, so `getattr` yields `2.0`/`10`,
     which equals today's no-argument construction — no observable change until
     the flags are added there.
5. Tests in `tests/test_summarize.py`:
   - Factory selects `StubSummarizer` for `stub`, `ManualSummarizer` for
     `manual`, and `BobShellSummarizer` for `bob_shell` (monkeypatch the class or
     `BOB_API_KEY`; no subprocess).
   - Unknown backend raises `SystemExit` naming all valid backends.
   - A `Namespace` with only `backend`/`config` (no `max_cost`, `max_turns`,
     `workers`) builds successfully — the regression that broke
     `test_cli_summarize_hierarchy_e2e`.
6. Keep the valid-backend list in the factory only; the error message and help
   text must not drift. The backends plan later extends this single list with
   `openai` and `anthropic`.

---

## Open decisions (need your OK before implementation)

1. **Default for `--workers`.** The plan says `1` (sequential, byte-identical
   default); the alternative is `4` (fast by default, sequential opt-in via
   `--workers 1`). Recommendation: keep `1`. Existing behaviour stays the
   default and the 24-minute pain is solved by passing a flag.
2. **Include sub-task 4 (one summarizer factory) in this phase?**
   Recommendation: **yes**. `--workers` has to be threaded through both
   `_run_summarize` and `_run_update` anyway, and
   `plan-pluggable-llm-backends.md` would otherwise add a third and fourth copy
   of backend construction. Scope is one helper in `cli.py` plus tests. If you
   say no, both call sites only get the `getattr` fix and the factory moves to
   the backends phase.
3. **Add `--workers` to the `update` subparser as well?** The draft did not; the
   minimum safe change is `getattr` only. Recommendation: **yes** — `update` can
   re-summarize many nodes when bodies changed, so the flag is useful there too,
   and symmetry costs one line. This is a scope addition; say no and it stays
   `getattr`-only.
4. **Live Bob Shell verification.** Recommendation: a 10-node fixture run at
   `--workers 1` and `--workers 4` (same text and order, ~0.1 Bobcoins), then one
   real 234-node run at `--workers 4`. The alternative — two full target runs to
   compare directly — proves equality more strongly but doubles coin spend and
   time.

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/hierarchy.py` | Add `batched_topological_order`; add `max_workers` param + batched loop to `run_hierarchy`; docstring note that backends must be thread-safe |
| `src/docgen/cli.py` | Add `--workers` to the `summarize` subparser; pass `max_workers=getattr(args, "workers", 1)` in `_run_summarize` and `_run_update`; add `_build_summarizer(args, output_dir)` and use it in both (sub-task 4) |
| `tests/test_hierarchy.py` | Add 3 batching tests + 4 parallel tests (output equality/order, timing, failure containment, worker clamp) |
| `tests/test_summarize.py` | Add 3 factory tests (backend selection, unknown backend exits, partial `Namespace` works) |
| `docs/tasks.md` | Add task 2b.9 entry |
| `docs/memory.md` | Add D-046. Note: `plan-pluggable-llm-backends.md` also claims D-046 — whichever lands second takes D-047 |
| `docs/BOB_LOG.md` | Add entry (the project log lives under `docs/`, not at the repo root) |

**Not touched:** `prompts.py`, `base.py`, `bob_shell.py`, `store.py`,
`schema.py`, `config.py`, `check/*`, `render/*` — parallelism lives in
`run_hierarchy`, and the factory moves code inside `cli.py` without changing
backend behaviour beyond the deltas listed in sub-task 4.
The new backends (plan-pluggable-llm-backends.md) inherit parallelism for free
because they implement the same `Summarizer` protocol and `run_hierarchy` calls
them.

---

## Dependency order

```
Sub-task 1  (batched_topological_order)
    ↓
Sub-task 2  (run_hierarchy parallelised)
    ↓
Sub-task 3  (CLI --workers flag + tests)
    ↓
Sub-task 4  (one summarizer factory, shared by summarize/update)
```

All four are in one module plus the CLI. Implement sequentially in one session.
Sub-task 4 must land **before** `plan-pluggable-llm-backends.md`, which then
extends the factory instead of duplicating backend selection a third time.

---

## Thread-safety model

`results` is owned by the main thread. Worker threads only compute and return a
`SummaryResult`; the main thread assigns `results[node.id]` while collecting the
batch in submission order. There is therefore no concurrent write to `results`
and no `threading.Lock` is needed (nor should one be added).

Correctness rests on the batch barrier, not on the GIL:

1. A batch is submitted only after every earlier batch has been collected.
2. Child summaries are read from `results` when a parent's request is built, so
   they are always fully written before any parent batch starts.
3. Within a batch no node reads another node's summary — nodes at the same depth
   are independent by construction of `batched_topological_order`.

The returned list is `list(results.values()) + [system]`; because insertion is
in batch order, `summaries.json` is byte-identical to the sequential run.

Backends must be safe to call concurrently (the protocol becomes
multi-threaded). `StubSummarizer`, `ManualSummarizer` and `BobShellSummarizer`
already are: none holds per-call mutable state, and `_call_bob` creates its own
temp files per call. State this in the `Summarizer` protocol docstring so future
backends do not break the assumption.

If this is ever ported to `ProcessPoolExecutor`, results must be returned from
futures (already the case here) and backend state must be picklable. Document
that constraint in the code before changing the executor.

---

## Why not parallelise within `topological_order` vs after?

`topological_order` returns a flat list with no batch boundaries. Adding batching
there would require changing its return type and all callers. The cleaner design
is a separate `batched_topological_order` that is only used by `run_hierarchy`,
keeping `topological_order` for tests and any future callers that need the flat
list.

---

## Rate-limiting guidance (in CLI help text)

Add to the `--workers` help string:
> "Values above 6 risk rate-limiting from hosted LLM APIs. Default: 1 (sequential)."

Note: a rate-limited or timed-out call becomes a `needs_human_review`
placeholder with `hash_input=""`, which is retried on the next run. A parallel
run that trips a 429 is therefore recoverable by re-running `docgen summarize`,
not by starting over.

---

## Verification plan

| Step | Check | Expected |
|---|---|---|
| Targeted tests | `python -m pytest tests/test_hierarchy.py tests/test_summarize.py -q` | all pass; batching tests prove every child sits in an earlier batch |
| Full suite | `python -m pytest -q` | 238+ pass; only `test_seeded_bug` fails (committed seeded bug in `target/`) |
| Determinism | run `run_hierarchy` on `tests/fixtures/freshness` at 1 and 4 workers, diff the resulting `summaries.json` | byte-identical, including list order |
| Concurrency | timing test (16 nodes, 0.05 s per call, 4 workers) | parallel < 0.6 × sequential |
| Failure containment | `FailingStubSummarizer` case | exactly one `needs_human_review`, with `hash_input=""` |
| Live backend | 10-node fixture at `--workers 1` vs `4` with `bob_shell`; then the real target at `--workers 4` | same text and order; no unrecoverable rate-limit failures |
| Cache replay | rerun `docgen summarize` with no changes | 0 summarizer calls, regardless of worker count |

Wall-clock speedup on the real repo is reported, not asserted — it depends on API
latency. Note that the first real run after the 2b.8 prompt changes re-summarizes
all 234 entries no matter which worker count is used.

