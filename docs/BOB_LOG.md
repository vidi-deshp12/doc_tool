# Bob Log

Evidence that IBM Bob was a core part of the workflow (judging: tool usage and depth, 30%).

## How to keep this log
- One entry per substantial Bob session (planning, coding, review, debugging, exploration). Skip trivial one-line questions.
- Dates use `YYYY-MM-DD`. Newest entries at the **bottom**.
- Save screenshots to `docs/bob-screenshots/` named `YYYY-MM-DD_<mode>_<short-title>.png` and reference them in the entry.
- Always record the **task ID** from `docs/tasks.md`, and what you checked yourself.
- Take a **Bobalytics snapshot** at least once a week (table at the bottom).
- Bob updates this file after each task, using the template below. Keep the same field names so entries stay consistent.

## Entry template (copy this)

```markdown
### YYYY-MM-DD | Task <ID> | <Mode: Ask / Plan / Code / Review / Shell / Orchestrator>
- **Goal:** one line.
- **Prompt (short):** the key instruction given to Bob.
- **What Bob produced:** files created/changed, or a summary of the answer.
- **What I verified or changed:** how the output was checked; what Bob got wrong.
- **Outcome:** done / partly done / blocked. Tests run and their result.
- **Screenshot:** `docs/bob-screenshots/<file>.png`
```

---

## Entries

### 2026-10-04 | Task 1.1 (exploration, reduced) | Ask
- **Goal:** Understand how the target app handles a "create article" request.
- **Prompt (short):** Trace what happens when a client sends a POST request to create a new article, step by step, naming files and functions.
- **What Bob produced:** An eight-step trace: CORS middleware in `main.py`; routing through `api/routes/api.py` to `create_new_article`; auth dependency (`get_current_user_authorizer`, JWT decode, user lookup); DB connection dependency (`get_repository`); request-body parsing into `ArticleInCreate` (alias `tagList` to `tags`); the handler generating a slug and checking for duplicates; `ArticlesRepository.create_article` running a transaction with SQL from `articles.sql`; response built with `ArticleForResponse` / `ArticleInResponse`, status 201.
- **What I verified or changed:** Not yet verified against the code. One claim looks doubtful: that body validation errors (422) happen before the auth dependency (403). To check by experiment (see `docs/memory.md`, unverified claims).
- **Outcome:** Useful orientation; confirmed that SQL lives in `.sql` files (aiosql-style), which matters for the gaps list.
- **Screenshot:** `docs/bob-screenshots/2026-10-04_ask_request-trace.png` *(add)*

<!-- Add new entries below this line -->

### 2026-10-05 | Task 0.1 | Agent (Code)
- **Goal:** Create the GitHub repo skeleton — `.gitignore`, `pyproject.toml`, `docgen.toml`, all `src/docgen/` sub-packages, `viewer/`, `eval/`, `generated/`, `tests/`, `README.md`, `BOB_LOG.md` root stub.
- **Prompt (short):** "yes" — approval to implement the plan that Bob laid out in Plan mode.
- **What Bob produced:** 53 files committed in one shot: `.gitignore` (excludes `target/`, `.venv/`, `__pycache__/`), `pyproject.toml` (stdlib + pytest only), `docgen.toml` (config skeleton from `architecture.md` §4), full `src/docgen/` tree with module-level docstrings, `viewer/app.py`, `eval/`, `generated/`, `tests/` placeholders. Pushed to `https://github.com/vidi-deshp12/doc_tool` as the initial commit.
- **What I verified or changed:** Confirmed `target/` does not appear in staged files (`git status --short`). Push succeeded (branch `master` created on origin).
- **Outcome:** Done. No tests for this task (tests introduced in 0.2). `docs/tasks.md` task 0.1 ticked.
- **Screenshot:** *(add Bobalytics or repo screenshot if available)*

### 2026-10-05 | Task 1.2 | Plan + Agent (Code)
- **Goal:** Build `eval/ground_truth.json` — the independent answer key for the `ast`-only route extractor.
- **Prompt (short):** "okay lets start working on task 1.2" → plan approved → "ok".
- **What Bob produced:** `eval/dump_ground_truth.py` (subprocess helper that imports `app.main.app`, calls `app.openapi()`, writes JSON to a given output path); `eval/build_ground_truth.py` (orchestrator that sets dummy env vars, runs the helper in a subprocess with a 30 s timeout, prints a cross-check table); `target/.venv` (Python 3.11, pydantic 1.10.21, aiosql 6.2); `eval/ground_truth.json` (19 routes, 25 schemas, full `/api/…` paths); `tests/test_ground_truth.py` (16 tests).
- **What I verified or changed:** Approved the plan. Confirmed target needed Python 3.11 (pydantic v1 incompatible with 3.14). Confirmed aiosql must be pinned to 6.2 (breaking change in 7.x). Hand-count of `@router.<method>` decorators = 19; matches `app.openapi()` count.
- **Outcome:** Done. 16/16 tests pass. `docs/tasks.md` task 1.2 ticked.
- **Screenshot:** *(add if available)*

### 2026-10-05 | Task 1.4 | Agent (Code)
- **Goal:** Seed a realistic bug in `target/` that a test can catch, proves `hash_struct` drift detection, and leaves the app importable.
- **Prompt (short):** "seed the bug as a wrong status code on the create article endpoint (201 → 200 in the decorator)."
- **What Bob produced:** Changed `status_code=status.HTTP_201_CREATED` to `status_code=status.HTTP_200_OK` in `create_new_article` decorator (`target/app/api/routes/articles/articles_resource.py`); wrote `tests/test_seeded_bug.py` (asserts status code is 201) and subprocess helper `tests/_check_create_article_status.py`; confirmed test fails with bug and passes after revert; ran full suite (17/17).
- **What I verified or changed:** Confirmed the bug choice — decorator arg change exercises `hash_struct` (structural) drift, not just `hash_source` (body text). Reverted bug after confirming test behavior. Ground truth (19 routes, 25 schemas) unchanged.
- **Outcome:** Done. Test fails with bug (200 ≠ 201), passes without. 17/17 total tests pass with reverted code. `docs/tasks.md` task 1.4 ticked.
- **Screenshot:** *(add if available)*

---

## Bobalytics snapshots

| Date | What the dashboard shows (contribution, sessions, etc.) | Screenshot |
|---|---|---|
| *(first snapshot)* | | `docs/bob-screenshots/<file>.png` |

## Summary for the deck (fill in near the end)
- Number of Bob sessions by mode (Ask / Plan / Code / Review / Shell):
- Tasks where Bob did most of the work:
- Bugs Bob caught in review mode:
- Things Bob got wrong and how we caught them:

### 2026-10-09 | Task 2a.5 | Plan + Agent
- **Goal:** Implement `extract/classes.py` — resolve class bases across files, flatten inherited fields (in-repo only), tag Pydantic models.
- **Prompt (short):** "Plan task 2a.5 — how will we do that?" followed by design decision (Option B: bases stay as raw source text, INHERITS edges carry the resolved topology).
- **What Bob produced:** Plan written to `docs/plan-2a5-class-resolution.md`; `src/docgen/extract/classes.py` (full implementation: `resolve_classes`, `resolve_all_classes`, field flattening, `is_pydantic_model` propagation); removed 10-line stub INHERITS loop from `src/docgen/extract/core.py`; `tests/test_classes.py` (8 tests).
- **What I verified or changed:** Ran full suite — 2 tests failed (single-letter class names like `A` were filtered by a too-broad generic-param guard `len==1 and isupper()`). Bob diagnosed the bug from trace output and fixed it in one diff. All 64 tests then passed.
- **Outcome:** Done. 64/64 tests pass.
- **Screenshot:** _(none this session)_

### 2026-10-09 | Task 2a.6 | Plan + Agent
- **Goal:** Implement `extract/bodies.py` — RAISES edges (exception type + args) and CALLS edges (callable name + full call text) for all module-level functions.
- **Prompt (short):** "Plan task 2a.6 for body facts." User then refined the CALLS design: `to_id = ast.unparse(call.func)` (callable name only), `meta = (("call_text", full_call),)` — confirmed before implementation.
- **What Bob produced:** `src/docgen/extract/bodies.py` (full implementation: `_resolve_exception_type`, `_extract_raises`, `_extract_calls`, `extract_body_facts`); `tests/test_bodies.py` (10 tests covering all branches + real-repo smoke test).
- **What I verified or changed:** All 74 tests passed first run. No bugs.
- **Outcome:** Done. 74/74 tests pass.
- **Screenshot:** _(none this session)_

### 2026-10-09 | Task 2a.7 | Plan + Agent
- **Goal:** Unresolved report — detect star_import, dynamic_import, getattr_dynamic; implement real `docgen extract` CLI pipeline; write facts.json; print linter-style summary.
- **Prompt (short):** "Plan task 2a.7 for unresolved report." Two design questions confirmed: (1) full pipeline in CLI (not read-only), (2) linter-style one-line-per-entry sorted by `where` with count line.
- **What Bob produced:** `src/docgen/extract/unresolved.py` (detection pass); `src/docgen/cli.py` (full extract pipeline + summary printer); `tests/test_unresolved.py` (7 tests); `tests/test_cli_extract.py` (5 tests).
- **What I verified or changed:** All 86 tests passed first run. No bugs.
- **Outcome:** Done. 86/86 tests pass. `docgen extract` now runs end-to-end and writes facts.json.
- **Screenshot:** _(none this session)_

### 2026-10-09 | Task 2a.8a | Plan + Agent
- **Goal:** FastAPI adapter via subprocess introspection — ROUTE nodes, HANDLES/REQUEST_MODEL/RESPONSE_MODEL edges, fallback on failure.
- **Prompt (short):** "Plan task 2a.8a." Design decisions: use `app.openapi()` for richness; enrich subprocess script to output `endpoint.__name__` per route (exact match, no operationId heuristics); dummy env vars hardcoded.
- **What Bob produced:** `adapters/base.py` (AdapterResult); `adapters/fastapi.py` (full implementation); cli.py Step 7 (adapter wiring); `tests/test_fastapi_adapter.py` (6 tests incl. 19-route consistency check).
- **What I verified or changed:** 1 failure: pydantic v1 PostgresDsn requires `userinfo` in DATABASE_URL. Bob fixed dummy URL to `postgresql://docgen:docgen@localhost/dummy`. All 92 tests then passed.
- **Outcome:** Done. 92/92 tests pass. Consistency check: all 19 ground-truth routes extracted.
- **Screenshot:** _(none this session)_

### 2026-10-09 | Tasks 2a.3b + 2a.6b | Agent
- **Goal:** Extract class methods as FUNCTION nodes; extend bodies.py to process method body facts.
- **Prompt (short):** "Plan tasks 2a.3b and 2a.6b together." User clarified: header span includes docstring; execute immediately after plan approval.
- **What Bob produced:** `core.py` — `_hash_struct_class`, `_class_header_end_line`, `_make_method_node`, method loop in `extract_file`; `bodies.py` — two-level AST cache, removed module-level restriction; `tests/test_core_methods.py` (9 tests); `tests/test_bodies_methods.py` (4 tests).
- **What I verified or changed:** 1 test failure: test 6 checked `hash_source` for field changes but fields affect `hash_struct`. Bob corrected the test and added a separate docstring-changes-hash_source test. All 105 tests then passed.
- **Outcome:** Done. 105/105 tests pass.
- **Screenshot:** _(none this session)_

### 2026-10-09 | Task 2a.8b | Plan + Agent
- **Goal:** FastAPI route extractor via AST only (Tier A: method + relative path + handler name). 100% recall without subprocess or import.
- **Prompt (short):** "Plan task 2a.8b, clearly separating Tier A (relative paths) vs Tier B (full path resolution). Show complexity difference before deciding." Decision: build Tier A only; record Tier B as D-030 known gap for v0.2; grade 2a.10 on method + handler.
- **What Bob produced:** `adapters/fastapi_ast.py` — `scan_router_defs` (APIRouter() detection + @router.<method> collector), `extract_ast_routes` (multi-file, SyntaxError-safe), `grade_ast_routes`; `cli.py` Step 7b (prints AST route count); `tests/test_fastapi_ast.py` (10 tests: 5 unit, 2 fixture, 2 grading, 1 integration).
- **What I verified or changed:** All 10 tests passed first run. Integration test: 19/19 routes, 100% recall. Grading design confirmed: operation_ids don't embed handler names directly (e.g. `create_new_article` → `create_article` in operation_id), so grade on (method, handler_name) pairs not operation_id substrings.
- **Outcome:** Done. 115/115 tests pass.
- **Screenshot:** _(none this session)_

### 2026-10-09 | Task 2a.9 | Plan + Agent
- **Goal:** Resolve DEPENDS_ON edges from `external:` placeholders to real in-repo FUNCTION node IDs; cycle guard.
- **Prompt (short):** "Plan task 2a.9." Inspected actual `facts.json` before planning — discovered three dep_name shapes including module-qualified names (`authentication.get_current_user_authorizer()`). Chose conservative Option B (never guess) before implementing.
- **What Bob produced:** `adapters/resolve_deps.py` — regex parser for dep_name strings, name index, alias/plain resolution via import records, `resolve_dep_edges`, `detect_dep_cycles`; `cli.py` Step 7c; `tests/test_resolve_deps.py` (15 tests).
- **What I verified or changed:** All 15 tests passed first run. CLI run: `DEP edges: 66/66 resolved`, 0 unresolved dep edges, no cycles. Matches plan acceptance criterion.
- **Outcome:** Done. 130/130 tests pass.
- **Screenshot:** _(none this session)_

### 2026-10-09 | Task 2a.10 | Agent (eval)
- **Goal:** Run the extractor gate: compare AST route extractor + full pipeline against ground truth; review unresolved list; pass/fail decision for Phase 2b.
- **Prompt (short):** "Work on task 2a.10. Run the eval check, confirm the 3 unresolved entries are legitimate. Record results in memory.md."
- **What Bob produced:** Ran `eval_2a10.py` script against `generated/facts.json` and `eval/ground_truth.json`. No code changes — pure evaluation.
- **What I verified:** Route recall 19/19 (100%). Method accuracy 19/19. Handler accuracy 19/19. DEP edges 66/66 resolved. 3 unresolved entries: (1) `CommonParameter` = aliased import from pypika — extractor correctly can't see through aliases; (2) `Exception` = Python built-in, not imported; (3) `logging.Handler` = attribute access on stdlib module. All three are expected limitations, not bugs. GATE PASSED.
- **Outcome:** Done. Phase 2b cleared to begin. 130/130 tests pass (unchanged).
- **Screenshot:** _(none this session)_

### 2026-10-11 | Task 2b.1 | Plan + Agent
- **Goal:** Build the Summarizer interface and wire a flat `docgen summarize` pipeline that runs end to end with a deterministic stub (no LLM).
- **Prompt (short):** "Read docs/plan-2b1-summarizer-interface.md and implement task 2b.1 exactly as described." Followed the plan's six sub-tasks in order.
- **What Bob produced:** `summarize/base.py` (`SummaryRequest`, `SummaryResult`, `Summarizer` protocol, `StubSummarizer`, `MissingSummaryError`, `NodeLevel`, shared `hash_input()`), `summarize/manual.py` (`ManualSummarizer` reading `<folder>/<safe_name>.md`), `summarize/store.py` (`write_summaries`/`read_summaries`, stable JSON), `cli.py` (`_run_summarize`, `_node_level`, `_read_source_text`, `summarize` subparser with `--config`/`--backend`), and `tests/test_summarize.py` (8 tests).
- **What I verified or changed:** The summarizers perform no I/O — the CLI reads `source_text` from `node.file` + `node.lines` before constructing each request. Only FUNCTION/CLASS/MODULE nodes are summarized; the pass is flat (`child_summaries=[]`). Unknown `--backend` raises `SystemExit`. New tests: `8 passed in 0.27s`.
- **Outcome:** Done. `facts.json` → `summaries.json` works end to end with the stub backend.
- **Screenshot:** _(none this session)_

### 2026-10-12 | Task 2b.2 | Plan + Agent
- **Goal:** Implement `summarize/prompts.py`: per-level prompt templates and the `[[fact_id]]` citation format; no LLM calls.
- **Prompt (short):** "Implement task 2b.2 from docs/plan-2b2-prompts.md exactly as planned." Preceded by a small fix: `cli.py` no longer imports the private `_edge_to_dict` from `facts/store.py`; the edge dict is built inline.
- **What Bob produced:** `prompts.py` (`PROMPT_VERSION`, `CITATION_RE`, `format_citation`, `extract_citations`, `SYSTEM_PREAMBLE`, `CITATION_RULES`, `OUTPUT_INSTRUCTION`, `LEVEL_INSTRUCTIONS` for the 6 levels, `allowed_fact_ids`, `render_edges`, `build_prompt`) and `tests/test_prompts.py` (9 tests).
- **What I verified or changed:** Allowed IDs include in-repo `raises`/`depends_on`/`inherits` targets but exclude `external:` and bare `calls` names (verified against `generated/facts.json`: `calls` targets are names like `Depends`/`HTTPException`, not node ids). `build_prompt` is deterministic (sorted facts/ids/children/edges) and omits empty optional sections. Tests: `19 passed` (9 new + 10 existing).
- **Outcome:** Done. Prompt + citation format ready for the 2b.3 hierarchy driver and the 2b.6 backend.
- **Screenshot:** _(none this session)_
