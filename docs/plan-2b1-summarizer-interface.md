# Plan: Task 2b.1 — Summarizer Interface

## Goal

Implement the `Summarizer` protocol, `SummaryRequest`/`SummaryResult` dataclasses,
`StubSummarizer`, and `ManualSummarizer` in `src/docgen/summarize/`.

Wire the `docgen summarize` CLI command so the **full pipeline** (extract → summarize → write
`summaries.json`) works end-to-end in tests using `StubSummarizer` with no LLM calls.

**Done when:** pipeline runs end to end with Stub in tests.

---

## Scope boundaries

Task 2b.1 owns:
- The data types (`SummaryRequest`, `SummaryResult`)
- The `Summarizer` protocol
- `StubSummarizer` — deterministic, no LLM
- `ManualSummarizer` — reads pre-written `.md` files from a folder
- `summaries.json` write/read (stable JSON, same rules as `facts.json`)
- `docgen summarize` CLI command (reads `facts.json`, writes `summaries.json`)
- Tests proving end-to-end with Stub

Task 2b.1 does **NOT** own:
- Prompt templates (2b.2)
- Hierarchy driver / cache (2b.3) — that's the bottom-up recursion; in 2b.1 the summarizer is called **flat** (one call per node, no child_summaries passed upward yet)
- Citation validator (2b.4)
- BobShellSummarizer (2b.6)

---

## Key design decisions to make explicit

### What goes in SummaryRequest?

From `architecture.md §7`:
```
SummaryRequest: node_id, level, facts (dict), source_text, child_summaries
```

- `node_id`: the node's ID string (e.g. `"target/app/api/routes/articles/articles_resource.py::create_new_article"`)
- `level`: one of `"function"`, `"method"`, `"class"`, `"module"`, `"package"`, `"system"`
- `facts`: the node's own fact dict (from `facts.json` node entry — all fields)
- `source_text`: the raw source text for this node — **read by the CLI** from `node.file` + `node.lines` before constructing the request; the summarizer does no I/O (D-Q1 decision). Includes comments per D-025.
- `child_summaries`: list of `SummaryResult` from already-summarized children (empty for all nodes in 2b.1's flat pass; populated in 2b.3's hierarchy driver)

`source_text` extraction (CLI responsibility): given `node.file` (POSIX path relative to repo root) and `node.lines` (start, end), read those lines from the source file before constructing `SummaryRequest`. The summarizer receives a plain string and never touches the filesystem.

### What goes in SummaryResult?

From `architecture.md §7`:
```
SummaryResult: text (with [[fact_id]] citations), model/backend name
```

- `node_id`: echoes back which node this summary covers
- `text`: prose with inline `[[fact_id]]` citations
- `backend`: string identifying the summarizer (e.g. `"stub"`, `"manual"`, `"bob_shell"`)
- `hash_input`: SHA-256 of the inputs (node's `hash_struct` + `hash_source` + child hashes) — used by the cache in 2b.3

### What does summaries.json look like?

Parallel to `facts.json`: a stable JSON file, sorted keys, no timestamps, UTF-8.

```json
{
  "summaries": [
    {
      "backend": "stub",
      "hash_input": "<sha256>",
      "node_id": "target/app/...",
      "text": "Stub summary for target/app/... [[target/app/...]]"
    }
  ]
}
```

One entry per summarized node. Indexed by `node_id` for fast lookup.

### What nodes does 2b.1 summarize?

The CLI command summarizes FUNCTION, CLASS, and MODULE nodes. ROUTE, EXTERNAL, PACKAGE,
UNRESOLVED, and ROUTER nodes are skipped. This is a scope decision: 2b.1 produces flat
per-node summaries; the full bottom-up hierarchy (feeding child summaries upward) is
2b.3's job.

### ManualSummarizer folder convention

Reads from a configurable folder (default: `generated/manual_summaries/`). Each file is
named `<node_id_sanitized>.md` where node_id is sanitized by replacing `/`, `::`, `:`,
and spaces with `_`. The file contains plain markdown — the summarizer returns it verbatim
as `text`.

If the file for a node doesn't exist, raises a `MissingSummaryError` (a specific exception
the CLI can catch and report).

---

## Architecture diagram

```
facts.json
    │
    ▼
_run_summarize (cli.py)
    │  reads facts, iterates FUNCTION + MODULE nodes
    │
    ▼
summarize(req: SummaryRequest) → SummaryResult
    │
    ├── StubSummarizer   → "Stub summary for {node_id} [[{node_id}]]"
    └── ManualSummarizer → reads generated/manual_summaries/{safe_name}.md
    │
    ▼
summaries.json  (sorted, stable)
```

---

## Sub-tasks

### Sub-task 1 — Data types + protocol: `base.py` [ ] pending

**Intent:** Define the shared types that every summarizer and every caller uses.
Nothing beyond the interface — no logic, no I/O.

**Expected outcomes:**
- `SummaryRequest` dataclass with fields: `node_id`, `level`, `facts`, `source_text`, `child_summaries`.
- `SummaryResult` dataclass with fields: `node_id`, `text`, `backend`, `hash_input`.
- `Summarizer` Protocol with one method: `summarize(req) -> SummaryResult`.
- `MissingSummaryError` exception class.
- `NodeLevel` string enum or literal type: `"function"`, `"method"`, `"class"`, `"module"`, `"package"`, `"system"`.
- Module docstring explaining *why* (not just what).

**Relevant context:**
- `src/docgen/summarize/base.py` — currently a stub with a comment.
- Follow `src/docgen/facts/schema.py` pattern: `dataclasses`, `from __future__ import annotations`, no external deps.

---

### Sub-task 2 — StubSummarizer [ ] pending

**Intent:** A no-LLM summarizer for tests. Returns a fixed template so tests can assert on the output without any network or Bob calls.

**Expected outcomes:**
- `StubSummarizer` class implements `Summarizer`.
- `summarize(req)` returns: `text = f"Stub summary for {req.node_id} [[{req.node_id}]]"`, `backend = "stub"`.
- `hash_input` is the SHA-256 of `req.node_id + req.facts.get("hash_struct","") + req.facts.get("hash_source","")`.
- Deterministic: same input → same output always.
- Lives in `base.py` alongside the types (no separate file needed for a one-liner impl).

---

### Sub-task 3 — ManualSummarizer + `manual.py` [ ] pending

**Intent:** Read pre-written `.md` files from a folder. The real flow for early demos is:
Bob writes a summary in the IDE → file lands in `generated/manual_summaries/` → pipeline picks it up.

**Expected outcomes:**
- `ManualSummarizer(folder: Path)` implements `Summarizer`.
- `summarize(req)` looks for `<folder>/<safe_name>.md` where `safe_name = node_id.replace("/", "_").replace("::", "__").replace(":", "_")`.
- Returns `SummaryResult(node_id=req.node_id, text=<file contents>, backend="manual", hash_input=<sha256>)`.
- Raises `MissingSummaryError(node_id)` if the file is not found.
- Lives in `src/docgen/summarize/manual.py`.

---

### Sub-task 4 — `summaries.json` read/write [ ] pending

**Intent:** Stable JSON store for summaries, same conventions as `facts.json`.

**Expected outcomes:**
- `write_summaries(results: list[SummaryResult], path: Path) -> None` — stable JSON, sorted keys, UTF-8.
- `read_summaries(path: Path) -> list[SummaryResult]` — round-trips cleanly.
- Output format: `{"summaries": [{...}, ...]}` with keys `node_id`, `text`, `backend`, `hash_input`.
- Lives in `src/docgen/summarize/store.py` (new file, parallel to `facts/store.py`).

---

### Sub-task 5 — `docgen summarize` CLI command [ ] pending

**Intent:** Wire the pipeline: read `facts.json`, build `SummaryRequest` per node, call the
summarizer, write `summaries.json`. For 2b.1 this is flat (no hierarchy).

**Expected outcomes:**
- `_run_summarize(args)` implemented in `cli.py`.
- Reads `facts.json` from `config.output_dir`.
- Summarizes **FUNCTION, CLASS, and MODULE** nodes only (ROUTE, EXTERNAL, PACKAGE, UNRESOLVED, ROUTER skipped).
- For each node: CLI reads `source_text` from `node.file` + `node.lines` (repo_root-relative) before calling `summarize()`. The summarizer receives it as a plain string — no I/O inside the summarizer.
- `child_summaries=[]` for all nodes in this flat pass (hierarchy is 2b.3's job).
- Writes `summaries.json` to `config.output_dir`.
- Backend selected by `--backend stub|manual` flag (default `stub`). Raises `SystemExit` with a clear message for unrecognised backends.
- Prints stderr progress; prints summary count to stdout.

---

### Sub-task 6 — Tests [ ] pending

**Intent:** Prove end-to-end with Stub. All tests use `StubSummarizer` — no LLM, no network.

**Tests to add** in `tests/test_summarize.py`:

1. `test_stub_summarizer_returns_result` — single request → SummaryResult with correct fields.
2. `test_stub_summarizer_deterministic` — same request twice → identical results.
3. `test_manual_summarizer_reads_file` — fixture folder with one `.md` file → returns its content.
4. `test_manual_summarizer_missing_file` — no file → raises `MissingSummaryError`.
5. `test_write_read_summaries_roundtrip` — write then read → identical list.
6. `test_write_summaries_stable` — write twice → byte-identical files.
7. `test_cli_summarize_stub_e2e` — fixture `facts.json` with 2 nodes → `summaries.json` written with 2 entries, each containing the node_id.
8. `test_cli_summarize_source_text_read` — SummaryRequest has non-empty `source_text` for a FUNCTION node with known lines.

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/base.py` | **Implement** — SummaryRequest, SummaryResult, Summarizer, StubSummarizer, MissingSummaryError, NodeLevel |
| `src/docgen/summarize/manual.py` | **Implement** — ManualSummarizer |
| `src/docgen/summarize/store.py` | **New** — write_summaries, read_summaries |
| `src/docgen/cli.py` | Implement `_run_summarize`; dispatch in `main()` |
| `tests/test_summarize.py` | **New** — 8 tests |

`src/docgen/summarize/hierarchy.py`, `prompts.py`, `citations.py`, `bob_shell.py` — **unchanged** (not in scope for 2b.1).
