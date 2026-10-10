# Project Memory

Append-only log of decisions, bugs, and open questions. **Update after every task.** Newest entries at the bottom of each section. Format: ID, date, what, why.

## 1. Decisions

| ID | Date | Decision | Why |
|---|---|---|---|
| D-001 | Oct 4 | Facts come from deterministic analysis; the LLM only writes prose on top | Trust; hallucination control |
| D-002 | Oct 4 | Two layers: generic core + framework adapters (v1: FastAPI) | Generalizability beyond one repo |
| D-003 | Oct 4 | Dev repo = FastAPI RealWorld (`nsidnev/fastapi-realworld-example-app`); showcase repo = non-FastAPI, lesser-known (Flask preferred) | RealWorld has `app.openapi()` ground truth; a different framework proves the core |
| D-004 | Oct 4 | Node IDs are repo-root-relative POSIX paths; members `path::Class::method` | Stable across machines/OS |
| D-005 | Oct 4 | Node span and hash include decorators | Decorator edits (route path/status) must count as change |
| D-006 | Oct 4 | Two hashes: `hash_struct` (no line numbers/comments) and `hash_source` | Avoid false-positive drift; detect body changes separately |
| D-007 | Oct 4 | Gap scope tiers. Tier 1 (build): G5 name resolution, G6 class fields/inheritance, G1 full route paths, G2 recursive dependency tree, G8 raises + raw calls, G4 detect-and-report, G14-G17. Tier 2 (if time): aiosql query linking, annotation-based call matching. Tier 3 (later/never): ERD, full call graph, G9, G11, G12, G13 | Time budget (~14 days) |
| D-008 | Oct 4 | Call graph deferred: store raw call text only | `ast` cannot resolve receiver types reliably |
| D-009 | Oct 4 | Summarizer behind an interface (Stub / Manual / BobShell) | Bob scriptability unconfirmed |
| D-010 | Oct 4 | CI default = report/propose update, hard-fail optional | Blocking PRs on docs breeds resentment |
| D-011 | Oct 4 | Rules file kept short; large docs read on demand | Bob loads every `.md` in `.bob/rules/` on every interaction |
| D-012 | Oct 4 | The endpoint map is an enrichment, not a headline feature. OpenAPI documents the outside of an API; docgen documents the inside (handler, dependency chain, behavior, all non-endpoint code) | FastAPI already produces OpenAPI; most of the codebase has no endpoints |
| D-013 | Oct 4 | `app.openapi()` grades the `ast`-only route extractor, not the introspection adapter | Both read the same running app, so grading one against the other is circular |
| D-014 | Oct 4 | Task IDs use the phase label (`2a.3`, `2b.1`, `3e.2`); `rules.md` now requires approval before implementing; calendar shifted to start Oct 5; broad exploration (1.1) reduced to logging the existing trace | Old numbering made `3.x` ambiguous; Oct 4 ended with setup still open |
| D-018 | Oct 6 | Bob Shell supports non-interactive use via `bob run --format json`; BobShellSummarizer is the real backend | Confirmed: `bob run` works, costs ~0.009 Bobcoins per call, 50-coin budget is sufficient |
| D-019 | Oct 6 | DB approach: Table definitions are in target/app/db/migrations/versions/fdf8821871d7_main_tables.py (single migration file, 7 tables). ERD is fully feasible from this file alone — no SQL parsing needed, just read the SQLAlchemy create_table calls.
| D-020 | Oct 5 | 19 route decorators hand-counted in `target/app/api/routes/` by grepping `@router.(get\|post\|put\|delete\|patch)`; `app.openapi()` also returns 19 routes — counts match | Cross-check required by task 1.2 to ensure the answer key itself is not trusted blindly |
| D-021 | Oct 5 | `target/.venv` uses Python 3.11 (not 3.14); pydantic v1 is incompatible with Python 3.14 (`unable to infer type` error on un-annotated fields in FastAPI 0.79's `openapi/models.py`) | Target requires pydantic 1.x; must pin Python ≤ 3.12 for target venv |
| D-022 | Oct 5 | `aiosql` must be pinned to `==6.2` in the target venv; `aiosql>=7` changed the SQL name-comment parser to require mandatory parameter lists, breaking `.sql` files that use the old `!` suffix | Target was built against aiosql 6.2 (`poetry.lock`) |
| D-023 | Oct 5 | Seeded bug: `HTTP_201_CREATED` → `HTTP_200_OK` in `create_new_article` decorator (`target/app/api/routes/articles/articles_resource.py`). Bug currently **reverted** (code is correct). Re-apply for Phase 4 demo. | Exercises `hash_struct` drift (decorator arg change), not merely a body/comment change |
| D-024 | Oct 6 | Task 2a.1 complete: `facts/schema.py` (Node, Edge, Unresolved, FactGraph dataclasses with all types from architecture.md §5) and `facts/store.py` (stable JSON with sorted keys, indent=2, UTF-8, no timestamps, no absolute paths). Round-trip test passes; byte-identical output on repeat writes. | Foundation for deterministic fact graph; enables all downstream phases. |
| D-025 | Oct 9 | hash_source uses Python tokenizer (tokenize module), not raw text or ast.dump(). Keeps comments (summarizer sees source_text with comments), strips blank lines/whitespace/CRLF. hash_struct unchanged (ast.dump() based, ignores comments). Record Python version in manifest to warn on tokenizer mismatch. | Blank lines and reformatting don't trigger regeneration; useful comment edits do since summarizer sees raw source_text. |
| D-026 | Oct 9 | Walker uses substring matching on absolute paths for excludes (e.g., "tests", "migrations" matches any path containing those strings). Config loaded via stdlib tomllib; exclude defaults to empty tuple. | Simple, no regex needed; matches docgen.toml exclude list directly. |
| D-027 | Oct 9 | Walker yields root-relative POSIX paths (forward slashes) using PurePath.as_posix() on all platforms. Path IDs in facts.json use the same POSIX scheme. | Stable across OS; Windows paths converted to POSIX for determinism (D-004). |
| D-028 | Oct 9 | Task 2a.3 complete: `extract/core.py` implements per-file AST extraction with decorator-inclusive spans, hash_struct (sha256 of synthetic AST with signature, decorators, bases, fields, imports), hash_source (tokenize-based, keeps comments, strips blank/whitespace). SyntaxError returns Unresolved. All hash test table rows pass. | Core extraction foundation; enables downstream module/class/body resolution. |
| D-029 | Oct 9 | Module index uses `source_root` from config to compute Python package dotted names (e.g., `target/app/main.py` with source_root=`target` → `app.main`). Import resolution handles absolute/relative imports, aliases, star imports, and __init__.py re-exports. External imports marked as external nodes. | Matches Python import semantics; repo root != package root. |

## 2. Bugs found and fixed

| ID | Date | Bug | Fix |
|---|---|---|---|
| B-001 | Oct 4 | In spike: function line span and hash started at `def`, excluding decorators, so a route path/status change would not change the hash | Span starts at first decorator; hash covers it; `def_line` kept separately. Verified by editing a decorator |
| B-002 | Oct 4 | In spike: `Depends(...)` inside decorator kwargs (`dependencies=[Depends(...)]`) missing from `depends_on`; these are the authorization checks | New `decorator_depends` field (becomes `depends_on` edge with `via=decorator`) |
| B-003 | Oct 4 | PowerShell `>` wrote JSON as UTF-16; file looked blank | Script writes UTF-8 itself via an output argument. Rule: never redirect JSON with `>` on Windows |
| B-004 | Oct 4 | Duplicate route data (`routes` field repeated `decorators[].route`) | Removed `routes` |
| B-005 | Oct 4 | Spike IDs started with `target/` depending on run location | Added `--root`; IDs relative to root, POSIX slashes |
| B-006 | Oct 5 | Seeded bug (task 1.4): `status_code=status.HTTP_200_OK` in `create_new_article` decorator instead of `HTTP_201_CREATED` | Fix: revert to `HTTP_201_CREATED`. Test: `tests/test_seeded_bug.py::test_create_article_returns_201` fails with bug, passes without |

## 3. Open questions
- Q-1: Can Bob Shell run non-interactively with output captured? (task 0.4)
- Q-2: Solo or team? If team, assign phases.
- Q-3: How does the target store DB schema (migrations vs SQL vs aiosql)? Is an ERD feasible? (task 1.3)
- Q-4: Which showcase repo? Must be non-famous, 5k-30k lines, has tests, permissive license.
- Q-5: Is a Flask adapter worth building after Phase 3? Decide at the Phase 3 gate.
- Q-6: Where exactly is the router prefix applied in the target (believed `app/api/routes/api.py`)? Confirm.

## 4. Unverified claims (do not rely on these)
- An "ibm-bob SDK/API" for calling Bob from code: not confirmed to exist.
- Target uses aiosql + asyncpg + Alembic: believed from Bob's trace (`articles.sql`, `<!` suffix); verify in repo.
- Bob's trace claimed body validation (422) runs before auth (403). Probably wrong: FastAPI resolves dependencies first, so a bad token gives 403 even with a bad body. Verify by experiment.
- Dispatch (Netflix) and others as showcase repo: unchecked leads.
- Flask routes/blueprints are close enough to FastAPI decorators that a small adapter could reuse the decorator parser: untested assumption.

## 5. Spike results (reference)
- `spike.py` parses one file into JSON (imports, assignments, classes, functions, decorators, routes, `Depends`, hashes).
- Run on `articles_resource.py` (120 lines, 5 endpoints): enough to write a useful paragraph about endpoints, methods, status codes, response models, dependencies.
- Gaps seen in real output: relative-only paths (G1), dependency names unresolved (G2/G5), no body facts (G8), class fields live in other files (G6).
- Observed: update/delete carry `check_article_modification_permissions` in the decorator; list endpoint uses optional auth (`required=False`).

## 6. Session log
| Date | What was done | Next |
|---|---|---|
| Oct 4 | Bob installed; target cloned; spike built and fixed (B-001..B-005); v1 scope, framework decision, and these context files written | Phase 0 tasks 0.1-0.5, then 1.1 |
| Oct 4 | Clarified relationship to OpenAPI (D-012); fixed circular route test (D-013); added task 2a.8b | Same |
| Oct 4 (late) | Fixed task numbering, tightened rules.md, re-planned calendar from Oct 5, added BOB_LOG.md skeleton | Tasks 0.1-0.5 |
| Oct 5 | Task 0.1: `.gitignore`, `pyproject.toml`, `docgen.toml`, `README.md`, full `src/docgen/` skeleton (all sub-packages), `viewer/`, `eval/`, `generated/`, `tests/`; committed and pushed to https://github.com/vidi-deshp12/doc_tool | Task 0.2 |
| Oct 5 | Task 1.2: `eval/dump_ground_truth.py` + `eval/build_ground_truth.py`; `target/.venv` (Python 3.11, pydantic 1.10.21, aiosql 6.2); `eval/ground_truth.json` (19 routes, 25 schemas); `tests/test_ground_truth.py` (16 tests, all pass). Hand-count confirms 19 decorators = 19 routes. | Task 1.3 |
| Oct 5 | Task 1.4: Seeded bug (`HTTP_200_OK` instead of `HTTP_201_CREATED` on `create_new_article`); `tests/test_seeded_bug.py` + `tests/_check_create_article_status.py`; bug reverted; 17/17 tests pass. | Task 2a.1 |
| Oct 6 | Task 2a.1: Implemented `src/docgen/facts/schema.py` (Node, Edge, Unresolved, FactGraph dataclasses with all types from architecture.md §5) and `src/docgen/facts/store.py` (write_facts/read_facts with stable JSON: sorted keys, indent=2, UTF-8, no timestamps, no absolute paths). Created `tests/test_schema.py` with round-trip and byte-identical repeat tests — all 6 pass. | Task 2a.2 |
| Oct 9 | Task 2a.2: Implemented `src/docgen/config.py` (loads docgen.toml via tomllib, validates adapter name, returns Config dataclass) and `src/docgen/walker.py` (walks repo, applies exclude substring matching, yields root-relative POSIX paths via PurePath.as_posix()). Created `tests/test_walker.py` with 9 tests covering basic walk, excludes, Windows paths, empty repo, and toml convenience function — all pass. | Task 2a.3 |
| Oct 9 | Task 2a.3: Implemented `src/docgen/extract/core.py` with per-file AST extraction (modules, classes, functions, decorators, docstrings, imports), decorator-inclusive spans, hash_struct (sha256 of synthetic AST), hash_source (tokenize-based), SyntaxError→Unresolved. Created `tests/test_core.py` with 15 tests covering all hash table rows + multi-line decorators + edge cases — all pass. | Task 2a.4 |
| Oct 9 | Task 2a.4: Implemented `src/docgen/extract/modules.py` with module index (dotted name ↔ path), import resolution (absolute/relative, aliases, star imports, __init__.py re-exports), external import marking. Created `tests/test_modules.py` with 9 tests covering internal/external resolution, relative imports, star imports, aliases, unresolved errors — all pass. Verified on real target repo (70 files, 100+ imports resolved). | Task 2a.5 |
| Oct 9 | Task 2a.5: Implemented `src/docgen/extract/classes.py` with `resolve_all_classes()` entry point. Removed stub INHERITS edges from `core.py`. Resolves raw base name strings to in-repo node IDs or `external:<dotted>` via import record lookup. Flattens inherited fields (in-repo chain only, child wins on name clash). Sets `is_pydantic_model=True` transitively. Cycle-safe. Bug fixed: single-letter class names (e.g. `A`) were incorrectly skipped by an overzealous generic-param guard. Created `tests/test_classes.py` with 8 tests — all 64 tests pass. | Task 2a.6 |

