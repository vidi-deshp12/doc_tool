# Plan: Task 2b.4 — Citation Validator

## Goal

Implement `src/docgen/summarize/citations.py`: a pure, deterministic validator that checks
every `SummaryResult` against the fact graph and reports broken citations without crashing the
run. Wire it into the CLI as `docgen validate`.

**Done when:** the validator correctly identifies (a) citations to node IDs absent from
`facts.json`, (b) sentences with no citation at all, and (c) summaries that reference the
synthetic `"system"` node id without error — and a `docgen validate` command reports the
findings and exits 1 if any broken citations are found, 0 if clean.

---

## Scope

Task 2b.4 owns:

- `src/docgen/summarize/citations.py` — validator logic (pure functions, no I/O, no LLM)
- `src/docgen/cli.py` — new `validate` subcommand
- `tests/test_citations.py` — offline tests

Task 2b.4 does **NOT** own:

- Entailment spot-check (checking that cited facts *support* the claim) → that is 2b.5
- Changes to `prompts.py`, `base.py`, `store.py`, `hierarchy.py` — unchanged

---

## Sources of truth

- **`architecture.md` §7:** Validator checks (1) ID exists in `facts.json`, (2) every sentence
  has ≥1 citation, (3) spot-check — (3) is 2b.5, out of scope here.
- **`prompts.py`:** `CITATION_RE = re.compile(r"\[\[([^\[\]]+)\]\]")` and `extract_citations`
  are the canonical parser — **reused directly** so validator and prompt never diverge.
- **`base.py`:** `SummaryResult.node_id` and `SummaryResult.text` are the two fields the
  validator reads.
- **Synthetic `"system"` node (2b.3):** the system summary has `node_id = "system"` and
  `facts = {}` — it is not in `facts.json`. The validator must treat it as a special case:
  allowed citation IDs for the system summary are the `node_id` values of its child summaries
  (all package-level summaries). Since we do not track child relationships in `summaries.json`,
  the simplest correct approach is: for the system node, *skip* the ID-existence check (the
  system prompt instructs the model to cite package IDs, which are checked for those packages'
  own summaries) and still enforce the sentence-coverage rule.

---

## Key design decisions

### D-A — What "a sentence" means; calls exemption

Split on `.`, `!`, and `?` followed by whitespace or end-of-string. Strip the result; skip
empty fragments. A fragment is only considered a "sentence" if it is non-empty after stripping
and contains at least one word character. This avoids false positives from trailing punctuation
or list markers.

A sentence *passes the coverage check* if:
- It contains at least one `[[id]]` citation, **OR**
- It mentions at least one raw call-target name from the node's `CALLS` edges (the `to_id`
  values of edges where `type == "calls"`).

**Why the calls exemption:** `CALLS` edges store unresolved callable names (e.g.
`"articles_repo.create_article"`, `"get_slug_for_article"`) — not node IDs in `facts.json`.
A sentence like *"this handler calls `articles_repo.create_article` to persist the article"*
is genuinely useful but cannot carry a `[[id]]` citation because the target is not a node.
Blocking such sentences would make summaries less informative (D-008).

`validate_summaries` therefore takes a second parameter:
```python
calls_by_node: dict[str, set[str]]  # node_id → set of call target names
```
The CLI builds this from `FactGraph.edges` where `edge.type == EdgeType.CALLS`. A sentence is
exempt from the citation requirement if `any(call_name in sentence for call_name in calls)`.

### D-B — What a "broken citation" is

Two kinds, kept separate for reporting:

| Kind | Field name | Meaning |
|---|---|---|
| `unknown_id` | `CitationError.kind` | The cited `[[id]]` is not in `facts.json` node ids |
| `uncited_sentence` | `CitationError.kind` | A sentence in the summary has no `[[…]]` at all |

### D-C — Output dataclass

```python
@dataclass(frozen=True)
class CitationError:
    node_id: str       # which summary this error belongs to
    kind: str          # "unknown_id" or "uncited_sentence"
    detail: str        # the bad id, or the uncited sentence text (truncated to 120 chars)
```

A `ValidationReport` groups the errors and provides a human-readable summary.

### D-D — The public API is two functions

```python
def validate_summaries(
    summaries: list[SummaryResult],
    known_ids: set[str],
) -> list[CitationError]: ...

def format_report(errors: list[CitationError]) -> str: ...
```

`validate_summaries` is pure (no I/O). The CLI reads `facts.json` to build `known_ids`,
reads `summaries.json`, calls `validate_summaries`, then prints/exits.

`known_ids` is built from `FactGraph.nodes` by the CLI, plus the `"system"` node id is added
so a summary that cites `"system"` does not produce a false positive.

### D-E — System-node ID-existence bypass

The system summary's text is validated for sentence coverage. For ID-existence, the validator
allows citation of any id in `known_ids` as usual — but since `"system"` is explicitly added to
`known_ids` by the CLI, a self-citation `[[system]]` is also valid. The stub produces exactly
`"Stub summary for system [[system]]"` — this passes cleanly.

### D-F — CLI exit codes

- Exit 0: no errors found.
- Exit 1: at least one `CitationError`. The broken citations are printed to stdout in a
  linter-style format: `ERROR [kind] <node_id>: <detail>`, one per line, with a count summary.

---

## Sentence-splitting heuristic

```python
import re
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+|$')

def _sentences(text: str) -> list[str]:
    # Split on sentence-ending punctuation followed by whitespace, or at end.
    # Each fragment is stripped; empty ones are dropped.
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip() and re.search(r'\w', p)]
```

This is intentionally simple and not perfect (e.g. "Mr. Smith" would split). It is sufficient
for the structured summaries the tool produces — short paragraphs with explicit citations.

---

## Sub-tasks

### Sub-task 1 — `citations.py`: data types + `validate_summaries` [ ] pending

**Intent:** Define the error dataclass and the core validation function.

**Expected outcomes:**
- `CitationError` dataclass (`node_id`, `kind`, `detail`) — frozen, importable by tests
- `validate_summaries(summaries, known_ids) -> list[CitationError]` — pure function:
  - For each summary, for each citation extracted via `CITATION_RE`/`extract_citations`,
    emit `unknown_id` if the id is not in `known_ids`
  - For each summary, for each sentence in the text that has no citation, emit
    `uncited_sentence`
  - The system node id (`"system"`) is just another entry in `known_ids` — no special-case
    logic inside the validator itself; the CLI adds it

**Relevant context:**
- [`extract_citations`](src/docgen/summarize/prompts.py:105) — reuse, never re-implement
- [`CITATION_RE`](src/docgen/summarize/prompts.py:29) — also reuse
- [`SummaryResult`](src/docgen/summarize/base.py:35) — `.node_id` + `.text`

**Status:** `[ ] pending`

---

### Sub-task 2 — `citations.py`: `format_report` [ ] pending

**Intent:** Produce a human-readable linter-style string for the CLI and tests.

**Expected outcomes:**
- `format_report(errors: list[CitationError]) -> str` returns a multi-line string:
  - One `ERROR [kind] <node_id>: <detail>` line per error (sorted: node_id then kind then detail)
  - Final line: `N citation error(s) found.` or `No citation errors.`
- Empty list → `"No citation errors.\n"`

**Status:** `[ ] pending`

---

### Sub-task 3 — `cli.py`: `validate` subcommand [ ] pending

**Intent:** Wire the validator into the CLI so it can be run standalone.

**Expected outcomes:**
- `docgen validate [--config docgen.toml]` reads `facts.json` + `summaries.json`, runs
  `validate_summaries`, prints the report to stdout
- Exits 0 if no errors; exits 1 if any `CitationError` found
- Missing `summaries.json` → `SystemExit` with clear message (run `docgen summarize` first)
- Missing `facts.json` → `SystemExit` with clear message

**Relevant context:**
- [`_run_summarize`](src/docgen/cli.py:199) — pattern to follow for config loading
- Existing subparser pattern in [`main()`](src/docgen/cli.py:266)

**Status:** `[ ] pending`

---

### Sub-task 4 — Tests [ ] pending

**Intent:** Prove each validation rule offline, including edge cases.

**Test file:** `tests/test_citations.py`

**Tests to add:**

1. `test_valid_summary_no_errors` — all sentences cited, all IDs known → empty error list.
2. `test_unknown_id_detected` — a citation `[[nonexistent.py::f]]` not in `known_ids` →
   `CitationError(kind="unknown_id", ...)`.
3. `test_uncited_sentence_detected` — a sentence with no `[[…]]` → `CitationError(kind="uncited_sentence", ...)`.
4. `test_multiple_errors_in_one_summary` — one unknown id + one uncited sentence → two errors.
5. `test_system_node_self_cite_is_valid` — `SummaryResult(node_id="system", text="... [[system]]")`
   with `"system"` in `known_ids` → no errors.
6. `test_format_report_no_errors` — empty list → `"No citation errors.\n"`.
7. `test_format_report_with_errors` — non-empty list → correct `ERROR [kind]` lines + count line.
8. `test_detail_truncated_to_120_chars` — very long uncited sentence is truncated in `detail`.
9. `test_cli_validate_exits_0_on_clean` — end-to-end CLI test with a clean summary → exit 0
   (no `SystemExit` raised).
10. `test_cli_validate_exits_1_on_errors` — end-to-end CLI test with a broken summary →
    `SystemExit` or exit 1.

**Status:** `[ ] pending`

---

### Sub-task 5 — Log [ ] pending

Update `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md`.

**Status:** `[ ] pending`

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/citations.py` | **Implement** — `CitationError`, `validate_summaries`, `format_report` |
| `src/docgen/cli.py` | **Add** `_run_validate` function + `validate` subparser entry |
| `tests/test_citations.py` | **New** — 10 offline tests |
| `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md` | Status/log updates only |

`base.py`, `prompts.py`, `store.py`, `hierarchy.py`, `manual.py` — **unchanged**.

---

## Open questions

- **What to do with stub summaries in production?** The stub produces `"Stub summary for X [[X]]"` — one sentence, one citation. All stub-generated summaries are clean. Real summaries from Bob may have multi-sentence text; the validator only runs meaningfully on real (manual or BobShell) output. This is fine — the validator is always safe to run and will just report 0 errors on stub output.
- **Should `validate` also write a report file?** The architecture does not mention a report file (only printed output). Keep it stdout-only for now; a file can be added in Phase 3.
