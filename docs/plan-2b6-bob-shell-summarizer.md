# Plan: Task 2b.6 — BobShellSummarizer (Real Backend)

## Goal

Implement `src/docgen/summarize/bob_shell.py`: a `BobShellSummarizer` that calls
`bob run --format json` non-interactively, passes the prompt from `build_prompt(req)` via
a temporary file on stdin, parses `last_message` from the JSON response, and returns a
`SummaryResult`. Wire it into the CLI as `--backend bob_shell`.

**Done when:** `docgen summarize --backend bob_shell` runs end-to-end on the target repo,
produces cited prose summaries from Bob, and writes them to `summaries.json`. Failures are
caught per-node and produce a `needs_human_review` placeholder instead of crashing the run.

---

## Scope

Task 2b.6 owns:

- `src/docgen/summarize/bob_shell.py` — `BobShellSummarizer`, `BobShellError`
- `src/docgen/summarize/hierarchy.py` — add per-node exception catching so a `BobShellError`
  (or any summarizer exception) produces a `needs_human_review` placeholder and continues
- `src/docgen/cli.py` — add `"bob_shell"` to the backend selector in `_run_summarize`
- `tests/test_bob_shell.py` — offline tests using `monkeypatch` to mock `subprocess.run`

Task 2b.6 does **NOT** own:

- Any LLM prompt content changes — `build_prompt` in `prompts.py` is unchanged
- The entailment spot-check (2b.5)
- The 2b.7 gate (human reads summaries)

---

## Sources of truth

- **D-018 (memory.md):** `bob run --format json` confirmed working; ~0.009 Bobcoins per call
- **Confirmed JSON output schema (from D-018 follow-up):**

```json
{
  "type": "result",
  "timestamp": "...",
  "status": "success",
  "stats": {
    "task_id": "...",
    "duration_ms": 1234,
    "session_costs": 0.023,
    "max_cost": 0.1,
    "tool_calls": 0
  },
  "last_message": "<the model response text>"
}
```

  Field to parse: `last_message`. `status` can be `"success"` or `"error"`.

- **`architecture.md` §9:** "LLM failures: retry with backoff, then mark the page
  `needs_human_review` and continue." — implemented in `run_hierarchy`, not inside the
  summarizer itself.
- **Project rules (`rules.md`):** "Do not write secrets, tokens, or API keys into files."
  `BOB_API_KEY` comes from the environment; never hardcoded.

---

## Key design decisions

### D-A — Prompt delivery via temp file + stdin pipe

Long prompts from `build_prompt(req)` contain multi-line JSON, code fences, and special
characters that would break shell quoting. The safest approach:

1. Write the prompt to a `NamedTemporaryFile` (text, UTF-8)
2. Open the file and pass it as `stdin` to `subprocess.run`
3. Delete the temp file after the call (use `delete=False` + manual cleanup for Windows
   compatibility — Windows cannot read a NamedTemporaryFile while it is still open)

Alternatively: write prompt to a temp file, then pass as: `bob run --format json < prompt.tmp`
via `subprocess.run(..., stdin=open(tmp_path))`. Both work; prefer the explicit open approach
for Windows compatibility.

### D-B — `bob run` command construction

```python
cmd = ["bob", "run", "--format", "json", "--max-cost", str(max_cost), "--max-turns", str(max_turns)]
```

The prompt is passed on stdin. `stdout=PIPE`, `stderr=PIPE`, `text=True`, `encoding="utf-8"`.
`timeout` defaults to 120 seconds (configurable). Subprocess inherits the caller's environment
so `BOB_API_KEY` flows through automatically.

### D-C — `BOB_API_KEY` check at construction time

`BobShellSummarizer.__init__` checks `os.environ.get("BOB_API_KEY")`. If missing, raises
`BobShellError("BOB_API_KEY environment variable is not set")` immediately rather than
failing at first `summarize()` call. This surfaces the problem early.

### D-D — `BobShellError` exception

```python
class BobShellError(Exception):
    """Raised when bob run fails or returns an unexpected response."""
```

Raised in three cases:
1. `BOB_API_KEY` missing at init
2. `subprocess.run` returns non-zero exit code (stderr captured and included in message)
3. JSON parsed but `status != "success"` or `last_message` key absent

### D-E — Retry with backoff (simple, two attempts)

Architecture says "retry with backoff". Keep it minimal: two attempts, 5-second sleep
between them, using `time.sleep`. If both fail, raise `BobShellError`. The hierarchy driver
(not the summarizer) catches this and marks `needs_human_review`.

### D-F — `needs_human_review` in `run_hierarchy`

Currently `run_hierarchy` in `hierarchy.py` has no exception handling around
`summarizer.summarize(req)` — any failure crashes the whole run. This task adds:

```python
try:
    result = summarizer.summarize(req)
except Exception as exc:
    print(f"  WARN: summarizer failed for {node.id}: {exc}", file=sys.stderr)
    result = SummaryResult(
        node_id=node.id,
        text=f"[needs_human_review] Summarizer failed: {exc}",
        backend="needs_human_review",
        hash_input="",   # empty → will always be re-attempted on next run
    )
```

Using `hash_input=""` ensures the node is retried on every subsequent `docgen summarize`
call until it succeeds.

### D-G — `BobShellSummarizer` constructor parameters

```python
class BobShellSummarizer:
    def __init__(
        self,
        max_cost: float = 2.0,
        max_turns: int = 10,
        timeout: int = 120,
    ) -> None: ...
```

All configurable at construction time; passed through to `bob run`. The CLI can expose
`--max-cost` and `--max-turns` flags on `docgen summarize` when `--backend bob_shell` is
selected.

---

## `bob run` invocation sketch

```python
import json, os, subprocess, tempfile, time
from pathlib import Path

def _call_bob(prompt: str, max_cost: float, max_turns: int, timeout: int) -> str:
    """Invoke `bob run --format json` and return the `last_message` text."""
    cmd = ["bob", "run", "--format", "json",
           "--max-cost", str(max_cost),
           "--max-turns", str(max_turns)]

    # Write prompt to a temp file; Windows can't read NamedTemporaryFile while open.
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                      encoding="utf-8", delete=False)
    try:
        tmp.write(prompt)
        tmp.flush()
        tmp.close()

        with open(tmp.name, encoding="utf-8") as stdin_fh:
            proc = subprocess.run(
                cmd, stdin=stdin_fh,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", timeout=timeout,
            )
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    if proc.returncode != 0:
        raise BobShellError(
            f"bob run exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        )

    data = json.loads(proc.stdout)
    if data.get("status") != "success" or "last_message" not in data:
        raise BobShellError(
            f"unexpected bob run response: status={data.get('status')!r}"
        )
    return data["last_message"]
```

---

## Sub-tasks

### Sub-task 1 — `bob_shell.py`: `BobShellError` + `_call_bob` helper [ ] pending

**Intent:** Isolate the subprocess invocation into one testable function.

**Expected outcomes:**
- `BobShellError(Exception)` defined
- `_call_bob(prompt, max_cost, max_turns, timeout) -> str` — temp file, subprocess, JSON parse
- Raises `BobShellError` on non-zero exit or bad response
- No global state; all parameters passed in

**Status:** `[ ] pending`

---

### Sub-task 2 — `bob_shell.py`: `BobShellSummarizer` class [ ] pending

**Intent:** Implement the `Summarizer` protocol using `_call_bob` with retry.

**Expected outcomes:**
- `BobShellSummarizer.__init__` checks `BOB_API_KEY`, raises `BobShellError` if missing
- `summarize(req)` calls `build_prompt(req)`, then `_call_bob` with two-attempt retry +
  5 s backoff; returns `SummaryResult(text=last_message, backend="bob_shell", ...)`
- Uses `hash_input_with_children` from `hierarchy.py` for the cache key (imported lazily to
  avoid circular imports; or use `base.hash_input` as the simplest correct option — the
  hierarchy driver will overwrite it with the extended key anyway when storing results)

**Relevant context:**
- [`build_prompt`](src/docgen/summarize/prompts.py:170) — builds the prompt string
- [`hash_input`](src/docgen/summarize/base.py:79) — base cache key helper
- [`ManualSummarizer`](src/docgen/summarize/manual.py:30) — pattern to follow for
  `SummaryResult` construction

**Status:** `[ ] pending`

---

### Sub-task 3 — `hierarchy.py`: per-node exception handling [ ] pending

**Intent:** Ensure a single summarizer failure does not crash the entire run.

**Expected outcomes:**
- `run_hierarchy` wraps `summarizer.summarize(req)` in a `try/except Exception`
- On failure: prints a `WARN` line to stderr, inserts a `needs_human_review` placeholder
  with `hash_input=""` (so the node is retried next run), and continues
- The system-level node gets the same treatment

**Relevant context:**
- [`run_hierarchy`](src/docgen/summarize/hierarchy.py:201) — lines 250–255

**Status:** `[ ] pending`

---

### Sub-task 4 — `cli.py`: add `bob_shell` backend option [ ] pending

**Intent:** Allow `docgen summarize --backend bob_shell` to select the new backend.

**Expected outcomes:**
- `_run_summarize` recognises `backend == "bob_shell"` and constructs
  `BobShellSummarizer(max_cost=..., max_turns=...)` with values from CLI args
- Two new optional CLI flags on the `summarize` subparser:
  `--max-cost` (float, default 2.0) and `--max-turns` (int, default 10)
- Error message for unknown backends updated to include `'bob_shell'`

**Status:** `[ ] pending`

---

### Sub-task 5 — Tests [ ] pending

**Intent:** Prove the happy path, failure path, retry, and missing-key check — all offline
with monkeypatched subprocess.

**Test file:** `tests/test_bob_shell.py`

**Tests to add:**

1. `test_bob_shell_success` — monkeypatch `subprocess.run` to return valid JSON with
   `status="success"` and `last_message="Good summary."` → `SummaryResult.text` matches.
2. `test_bob_shell_error_status` — `status="error"` in JSON → `BobShellError` raised.
3. `test_bob_shell_nonzero_exit` — `returncode=1` → `BobShellError` raised.
4. `test_bob_shell_missing_last_message` — valid JSON but no `last_message` key →
   `BobShellError` raised.
5. `test_bob_shell_retry_succeeds_on_second_attempt` — first call raises, second returns
   valid JSON → no exception; call count = 2.
6. `test_bob_shell_retry_exhausted` — both attempts fail → `BobShellError` raised.
7. `test_bob_shell_missing_api_key` — `BOB_API_KEY` not in env → `BobShellError` at
   construction time.
8. `test_run_hierarchy_continues_on_summarizer_failure` — inject a summarizer that always
   raises; `run_hierarchy` returns results with `backend="needs_human_review"` placeholder
   and does not raise.
9. `test_needs_human_review_hash_input_empty` — the `needs_human_review` placeholder has
   `hash_input=""` so it is always retried.

**Status:** `[ ] pending`

---

### Sub-task 6 — Log [ ] pending

Update `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md`.

**Status:** `[ ] pending`

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/bob_shell.py` | **Implement** — `BobShellError`, `_call_bob`, `BobShellSummarizer` |
| `src/docgen/summarize/hierarchy.py` | **Modify** — per-node exception handling in `run_hierarchy` |
| `src/docgen/cli.py` | **Modify** — `bob_shell` backend + `--max-cost`/`--max-turns` flags |
| `tests/test_bob_shell.py` | **New** — 9 offline tests |
| `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md` | Status/log updates only |

`base.py`, `prompts.py`, `store.py`, `manual.py`, `citations.py` — **unchanged**.

---

## Open questions / risks

- **`bob run` vs `bob -p`:** D-018 records `bob run --format json`. Need to confirm at
  implementation time whether stdin pipe works with `bob run` specifically (vs `bob -p
  "..."` with text inline). The plan uses stdin via temp file; if `bob run` doesn't accept
  stdin, fall back to `bob -p "$(cat prompt.tmp)"` or the `-p @prompt.tmp` file-reference
  syntax if Bob supports it.
- **Windows path in subprocess:** `bob` must be on `PATH`. On Windows the executable may
  be `bob.cmd`. Use `shutil.which("bob")` to find it at init time; raise `BobShellError`
  if not found (not just `BOB_API_KEY` missing).
- **Prompt size:** `build_prompt(req)` for a large module or package can be several
  thousand tokens. The `--max-turns 10` cap prevents runaway loops; `--max-cost` prevents
  overspend. The 50-coin budget noted in D-018 is comfortably covered at ~0.009 coins/call.
