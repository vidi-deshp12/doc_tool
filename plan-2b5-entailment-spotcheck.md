# Plan: Task 2b.5 — Entailment Spot-Check

## Overview

**Goal:** Sample N claims from `summaries.json`, check that each claim's cited
`facts.json` node actually supports what the summary says, and write a CSV sheet
that a human reviewer can hand-grade.

**What this is not:** a second pass of the ID-existence or sentence-coverage
checks (those live in `citations.py` / task 2b.4). This task goes one level
deeper: it verifies *semantic* grounding — does the cited fact actually justify
the sentence? It does not call an LLM automatically; it produces a graded sample
sheet for human review (or, as a stretch, for Bob to review interactively).

**Scope:** one new module `summarize/entailment.py`, one new `docgen entailment`
CLI subcommand, one new test file `tests/test_entailment.py`, and a tiny update
to `cli.py`. No changes to existing modules.

---

## Sub-Task 1 — `summarize/entailment.py`: sampling + evidence extraction

**Intent:** Build the pure, deterministic half of the spot-check. Given
`summaries.json` + `facts.json`, pick N sentences that carry citations, locate
the cited facts, and return structured claim records ready to be written to CSV.
No LLM, no Bob call in this step.

**Expected Outcomes:**
- `sample_claims(summaries, graph, n, seed) -> list[ClaimRecord]` is pure and
  deterministic (same seed → same rows).
- `ClaimRecord` carries: `node_id`, `backend`, `sentence`, `cited_ids`, and
  `evidence` (the raw text of the cited fact nodes: their `id`, `type`,
  `docstring`, `signature`, and/or any other human-readable fields that Bob would
  use to confirm the claim).
- Sentences with `needs_human_review` backend are skipped.
- If `n` is larger than the population, all eligible sentences are returned.

**Todo List:**
- [ ] Add `ClaimRecord` dataclass to `summarize/entailment.py` (fields:
  `node_id`, `backend`, `sentence`, `cited_ids: list[str]`,
  `evidence: list[dict]`).
- [ ] Implement `_extract_evidence(cited_ids, graph) -> list[dict]` — for each
  id look up the node in the graph, collect its human-readable fields
  (`id`, `type`, `file`, `docstring`, `signature` if present, `fields` if
  present); return a list of dicts. Unknown ids → empty evidence dict with just
  the id.
- [ ] Implement `sample_claims(summaries, graph, n, seed) -> list[ClaimRecord]`:
  - Collect all (result, sentence) pairs where the result backend is not
    `needs_human_review` and the sentence has ≥1 citation.
  - Use `random.Random(seed).sample(population, min(n, len(population)))` for
    deterministic, seeded sampling.
  - For each sampled pair, call `_extract_evidence`, build and return
    `ClaimRecord`.

**Relevant Context:**
- [`src/docgen/summarize/citations.py`](src/docgen/summarize/citations.py) — `_split_sentences`,
  `extract_citations` pattern to reuse.
- [`src/docgen/summarize/base.py`](src/docgen/summarize/base.py) — `SummaryResult`.
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) — `FactGraph`, `Node`.
- [`src/docgen/summarize/hierarchy.py`](src/docgen/summarize/hierarchy.py) — `NEEDS_HUMAN_REVIEW_BACKEND`.

**Status:** `[ ] pending`

---

## Sub-Task 2 — CSV writer

**Intent:** Serialize `list[ClaimRecord]` to a stable CSV sheet that a human can
open in a spreadsheet. One row per claim. The "evidence" column is a JSON blob
so the CSV stays a single file.

**Expected Outcomes:**
- `write_sheet(claims, path)` writes UTF-8 CSV with header:
  `node_id, backend, sentence, cited_ids, evidence`.
- `cited_ids` and `evidence` are JSON-serialized (sorted keys, compact).
- Rows are sorted by `(node_id, sentence)` for determinism.
- Function is pure side-effect-of-file-write only; nothing printed to stdout.

**Todo List:**
- [ ] Add `write_sheet(claims: list[ClaimRecord], path: Path) -> None` to
  `summarize/entailment.py`.
- [ ] Use stdlib `csv.writer` with `lineterminator="\n"`, `encoding="utf-8"`.
- [ ] Columns: `node_id`, `backend`, `sentence`, `cited_ids` (JSON array),
  `evidence` (JSON array of dicts, `sort_keys=True`).
- [ ] Rows sorted by `(node_id, sentence)`.

**Relevant Context:**
- `json.dumps(..., sort_keys=True, ensure_ascii=False)` for the JSON columns
  (matches project's JSON style from `facts/store.py`).

**Status:** `[ ] pending`

---

## Sub-Task 3 — `docgen entailment` CLI subcommand

**Intent:** Wire the entailment module into the CLI so it can be run as
`docgen entailment --n 30 --seed 42 --out eval/entailment_sheet.csv`.

**Expected Outcomes:**
- New `entailment` subparser in `cli.py` with `--n` (default 30), `--seed`
  (default 42), `--out` (default `eval/entailment_sheet.csv`), and `--config`
  flags.
- Reads `facts.json` and `summaries.json` from the configured output dir.
- Calls `sample_claims` then `write_sheet`; prints a one-line summary to stdout:
  `"N claim(s) sampled → <path>"`.
- If fewer than `--n` eligible sentences exist, prints a warning but exits 0.

**Todo List:**
- [ ] Add `entailment` subparser to the `subparsers` block in `cli.py`.
- [ ] Add `_run_entailment(args)` function mirroring `_run_validate` in style.
- [ ] Dispatch `args.command == "entailment"` in `main()`.
- [ ] Accept `--n`, `--seed`, `--out`, `--config` flags.
- [ ] Create parent directories of `--out` if needed (`Path.mkdir(parents=True,
  exist_ok=True)`).

**Relevant Context:**
- [`src/docgen/cli.py`](src/docgen/cli.py) lines 272-327 — `_run_validate` is
  the closest pattern to copy.
- Output dir comes from `config.output_dir`.

**Status:** `[ ] pending`

---

## Sub-Task 4 — Tests (`tests/test_entailment.py`)

**Intent:** Cover the pure functions deterministically without any LLM or
filesystem side-effects beyond writing a temp CSV.

**Expected Outcomes:**
- All tests pass in the existing `pytest` suite; total count increases by ~8.
- No test calls a real LLM or reads `target/`.

**Todo List:**
- [ ] `test_sample_claims_deterministic` — same seed → same rows; different seed
  → different rows (or at least not identical when population is large enough).
- [ ] `test_sample_claims_skips_needs_human_review` — results with that backend
  never appear in the sample.
- [ ] `test_sample_claims_n_exceeds_population` — returns all eligible rows,
  no error raised.
- [ ] `test_sample_claims_no_cited_sentences` — returns empty list when no
  sentence has a citation.
- [ ] `test_extract_evidence_known_id` — returns a dict with `id` and at least
  one other field for a known node.
- [ ] `test_extract_evidence_unknown_id` — returns `{"id": unknown_id}` stub dict
  (not an error).
- [ ] `test_write_sheet_columns` — CSV has the right header row; rows sorted.
- [ ] `test_write_sheet_encoding` — file is UTF-8 and round-trips correctly
  for non-ASCII text.

**Relevant Context:**
- Fixture data: build small in-memory `SummaryResult` and `FactGraph` objects
  using existing dataclasses (no fixture files needed).
- [`tests/test_citations.py`](tests/test_citations.py) — pattern for constructing
  `SummaryResult` objects in tests.

**Status:** `[ ] pending`

---

## Files Touched

| File | Change |
|---|---|
| `src/docgen/summarize/entailment.py` | New: `ClaimRecord`, `sample_claims`, `_extract_evidence`, `write_sheet` |
| `src/docgen/cli.py` | Add `entailment` subcommand + `_run_entailment` |
| `tests/test_entailment.py` | New: 8 tests |

No existing modules are modified except `cli.py` (additive only).

---

## Out of Scope

- Automatic LLM-graded entailment (stretch; would go in `summarize/bob_shell.py`
  or a new `summarize/entailment_llm.py`).
- Changing `validate_summaries` or `citations.py`.
- Producing or updating `summaries.json` as part of this task.
