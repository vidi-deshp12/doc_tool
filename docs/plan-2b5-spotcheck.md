# Plan: Task 2b.5 — Entailment Spot-Check

## Goal

Produce a **hand-grading sheet**: a CSV (or JSON) file where each row is one sampled
(sentence, cited_fact_snippet) pair, with a blank `verdict` column for a human to fill in
(1 = supported, 0 = not supported, ? = unclear). The sheet is the artefact; the LLM-free
sampling and fact-lookup logic lives in `summarize/citations.py` (extending the existing
module) or in a standalone `eval/` script.

**Done when:** `docgen spotcheck` (or `docgen eval --spotcheck`) samples N claims from
`summaries.json`, looks up the cited fact snippets from `facts.json`, writes a CSV to a
configurable path, and prints a count summary. The output can be hand-graded to measure
claim precision (PRD §8: ≥ 90% target on ≥ 30 claims).

---

## Scope

Task 2b.5 owns:

- `eval/spotcheck.py` — sampling + fact lookup + CSV writer (standalone script, no new dep)
- `src/docgen/cli.py` — new `spotcheck` subcommand that calls the eval script logic
- `tests/test_spotcheck.py` — offline tests (no filesystem CSV; test the core logic functions)

Task 2b.5 does **NOT** own:

- The grading itself — that is a human task (see 2b.7 gate)
- LLM entailment checking — architecture.md says "spot-check *may* use LLM" but this task
  produces the sheet only; LLM checking would be a stretch
- Changes to `citations.py`, `prompts.py`, `hierarchy.py`, `store.py` — unchanged

---

## Sources of truth

- **`architecture.md` §7:** "spot-check that the cited fact/snippet supports the sentence" —
  the entailment check is described as a spot-check, not a full pass
- **`PRD.md` §8:** "Claim precision ≥ 90% on a hand-graded sample of ≥ 30 claims (publish
  the real number even if lower)" — N = 30 is the minimum; configurable
- **`facts.json` structure:** nodes have `id`, `type`, `file`, `lines`, `hash_struct`,
  `hash_source`, `docstring`, `signature`, `source_text` is not stored in facts.json — the
  raw source must be re-read from `node.file` + `node.lines` at spotcheck time
- **`summaries.json` structure:** list of `{node_id, text, backend, hash_input}`; `text`
  contains inline `[[id]]` citations

---

## Key design decisions

### D-A — What a "claim" is

A claim = one (sentence, cited_id) pair. A sentence citing two IDs produces two rows.
This is the finest granularity and ensures every citation is evaluated independently.

### D-B — What "fact snippet" to show the grader

For each cited `fact_id`, look up the node in `facts.json`:
- If the node has a `docstring`: show the docstring (most human-readable)
- Otherwise show the `signature` (for functions/methods)
- Otherwise show the first 200 characters of the raw source text (re-read from disk)
- Otherwise show the node's `id` and `type` only

This gives the grader the most relevant fragment without requiring them to open the repo.

### D-C — Sampling strategy

Random sample without replacement, seeded for reproducibility (`--seed`, default 42).
Sample from all non-system, non-stub summaries first (real LLM output); fall back to any
summaries if not enough real ones. Skip summaries with zero sentences or zero citations.

`N` is configurable via `--n` (default 30, minimum 10).

### D-D — Output format

CSV with columns: `row`, `node_id`, `sentence`, `cited_id`, `fact_type`, `fact_snippet`,
`verdict` (blank). Written with `csv` stdlib module; UTF-8; no extra deps.

The file path defaults to `generated/spotcheck.csv` (next to `summaries.json`).

### D-E — Where the code lives

The sampling and fact-lookup logic lives in `eval/spotcheck.py` as importable functions
(not just a `__main__` block), so `cli.py` can call them and `tests/test_spotcheck.py` can
test them without subprocess. The `docgen spotcheck` CLI is a thin wrapper.

---

## Row structure

```
row | node_id | sentence | cited_id | fact_type | fact_snippet | verdict
 1  | pkg/mod.py::create_article | This handler raises HTTPException when the slug is taken [[external:...]] | external:fastapi.HTTPException | external | (external library — no docstring) |
 2  | pkg/mod.py::create_article | It depends on get_current_user_authorizer for auth [[pkg/auth.py::get_current_user_authorizer]] | pkg/auth.py::get_current_user_authorizer | function | def get_current_user_authorizer(...) |
```

---

## Sub-tasks

### Sub-task 1 — `eval/spotcheck.py`: claim extraction [ ] pending

**Intent:** Extract all (sentence, cited_id) pairs from a list of summaries.

**Expected outcomes:**
- `extract_claims(summaries: list[SummaryResult]) -> list[dict]` — returns a list of dicts
  with keys `node_id`, `sentence`, `cited_id`. One dict per (sentence, citation) pair.
  Uses `_split_sentences` and `extract_citations` from `citations.py` / `prompts.py`.

**Relevant context:**
- [`_split_sentences`](src/docgen/summarize/citations.py:36) — already splits correctly
- [`extract_citations`](src/docgen/summarize/prompts.py:105) — canonical citation parser
- The system node's citations cite package ids which are valid nodes — include them

**Status:** `[ ] pending`

---

### Sub-task 2 — `eval/spotcheck.py`: fact snippet lookup [ ] pending

**Intent:** For each cited_id, retrieve the best human-readable snippet from the fact graph.

**Expected outcomes:**
- `get_fact_snippet(node_id: str, graph: FactGraph, repo_root: Path) -> tuple[str, str]`
  returns `(fact_type, fact_snippet)`:
  - Looks up the node in `graph.nodes` by id
  - If not found (e.g. `external:...`): returns `("external", "(external — no source)")`
  - If `node.docstring`: returns `(node.type.value, node.docstring[:300])`
  - If `node.signature`: returns `(node.type.value, node.signature)`
  - Otherwise reads source lines from `repo_root / node.file` (using `read_source_text`
    from `hierarchy.py`), returns first 200 chars

**Relevant context:**
- [`read_source_text`](src/docgen/summarize/hierarchy.py:43) — already handles OSError safely
- [`_node_to_dict`](src/docgen/facts/store.py:12) — shows which fields are populated

**Status:** `[ ] pending`

---

### Sub-task 3 — `eval/spotcheck.py`: sample + write CSV [ ] pending

**Intent:** Combine claims, sample N, look up snippets, write the grading sheet.

**Expected outcomes:**
- `sample_claims(claims, n, seed) -> list[dict]` — random sample without replacement,
  seeded, minimum `min(n, len(claims))` rows
- `write_spotcheck_csv(rows: list[dict], path: Path) -> None` — writes CSV with columns
  `row, node_id, sentence, cited_id, fact_type, fact_snippet, verdict`; UTF-8; `csv` module
- `run_spotcheck(summaries, graph, repo_root, n, seed, output_path)` — orchestrates the
  full pipeline: extract → sample → lookup → write; returns count of rows written

**Status:** `[ ] pending`

---

### Sub-task 4 — `cli.py`: `spotcheck` subcommand [ ] pending

**Intent:** Wire the spotcheck into `docgen spotcheck`.

**Expected outcomes:**
- `docgen spotcheck [--config docgen.toml] [--n 30] [--seed 42] [--output generated/spotcheck.csv]`
- Reads `facts.json` + `summaries.json`, calls `run_spotcheck`, prints count summary to stderr
- Missing `summaries.json` or `facts.json` → `SystemExit` with clear message
- Prints: `"spotcheck.csv written: N rows"` to stdout

**Relevant context:**
- Pattern from [`_run_validate`](src/docgen/cli.py:265) in cli.py

**Status:** `[ ] pending`

---

### Sub-task 5 — Tests [ ] pending

**Intent:** Prove claim extraction, snippet lookup, and sampling offline — no CSV I/O in
most tests; one end-to-end test writes to `tmp_path`.

**Test file:** `tests/test_spotcheck.py`

**Tests to add:**

1. `test_extract_claims_basic` — two-sentence summary with one citation each → two claim dicts
2. `test_extract_claims_multi_citation` — one sentence with two citations → two dicts with same sentence
3. `test_extract_claims_no_citations` — uncited sentence → no claims extracted (no citations to pair)
4. `test_get_fact_snippet_external` — `external:...` id → `("external", "(external — no source)")`
5. `test_get_fact_snippet_docstring` — node with docstring → docstring returned
6. `test_get_fact_snippet_signature_fallback` — node with signature but no docstring → signature
7. `test_sample_claims_reproducible` — same seed → same sample; different seed → different sample
8. `test_sample_claims_capped_at_available` — N larger than available claims → all claims returned
9. `test_write_spotcheck_csv_columns` — output CSV has expected column headers and N data rows
10. `test_cli_spotcheck_e2e` — end-to-end via `_run_spotcheck`; CSV file created with correct row count

**Status:** `[ ] pending`

---

### Sub-task 6 — Log [ ] pending

Update `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md`.

**Status:** `[ ] pending`

---

## Files to touch

| File | Change |
|---|---|
| `eval/spotcheck.py` | **New** — `extract_claims`, `get_fact_snippet`, `sample_claims`, `write_spotcheck_csv`, `run_spotcheck` |
| `src/docgen/cli.py` | **Add** `_run_spotcheck` function + `spotcheck` subparser |
| `tests/test_spotcheck.py` | **New** — 10 offline tests |
| `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md` | Status/log updates only |

`citations.py`, `prompts.py`, `hierarchy.py`, `base.py`, `store.py` — **unchanged**.

---

## Open questions

- **Stub summaries:** `StubSummarizer` produces `"Stub summary for X [[X]]"` — each is one
  sentence with one (self-)citation. Sampling stub summaries gives trivial rows (a node citing
  itself). The sampling function should prefer `backend != "stub"` rows when available, falling
  back to stub only if there are not enough real summaries. Confirmed: D-C already covers this.
- **`external:` citations in the sheet:** they cannot be looked up in `facts.json` (not nodes).
  The snippet is `"(external — no source)"`. The grader will mark these as "?" — they are
  context mentions, not real entailment checks. Including them is fine; the precision metric
  should probably count only rows where `fact_type != "external"`.
