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

### 2026-10-12 | Task 2b.3 | Plan + Agent
- **Goal:** Bottom-up hierarchy driver — children summarized before parents; cache so unchanged nodes are skipped on re-run; synthetic system-level node always produced.
- **Prompt (short):** "Plan task 2b.3." User confirmed: system node always produced (not deferred), `_read_source_text` moves to hierarchy.py. Implemented immediately after approval.
- **What Bob produced:** `summarize/hierarchy.py` — `build_contains_index`, `topological_order`, `hash_input_with_children`, `run_hierarchy`, `read_source_text`, `_node_level`, `_build_edges_by_from`, `_node_type_for_id`, `SYSTEM_NODE_ID`; `cli.py` — flat loop replaced by `run_hierarchy` call, existing cache loaded from `summaries.json`; `tests/test_hierarchy.py` (8 tests); `docs/plan-2b3-hierarchy-cache.md`.
- **What I verified or changed:** Cache key folds in `PROMPT_VERSION` (resolving D-035 flag) and sorted child `hash_input` values — same cache key without changes guarantees zero calls on re-run. `test_run_hierarchy_zero_calls_on_rerun` explicitly asserts 0 calls. System node is last in `summaries.json` with `node_id="system"`. Existing `test_cli_summarize_stub_e2e` updated (now expects 3 summaries including system). All 157 tests pass first run.
- **Outcome:** Done. `docgen summarize` now runs bottom-up with child summaries populated at every level. Zero re-calls on unchanged cache verified.
- **Screenshot:** _(none this session)_

### 2026-10-12 | Task 2b.4 | Plan + Agent
- **Goal:** Citation validator — check that every `[[id]]` exists in `facts.json` and every sentence is cited (with a calls-name exemption).
- **Prompt (short):** "Plan task 2b.4." User added the calls exemption: sentences mentioning a raw CALLS to_id are exempt from the citation rule (D-008 reasoning). Approved immediately after plan.
- **What Bob produced:** `summarize/citations.py` — `CitationError` dataclass, `_split_sentences` (with leading-citation merging), `validate_summaries(summaries, known_ids, calls_by_node)`, `format_report`; `cli.py` — `_run_validate` + `validate` subparser (exit 0/1); `tests/test_citations.py` (15 tests); `docs/plan-2b4-citation-validator.md`.
- **What I verified or changed:** First run: 4 tests failed. Root cause: sentence splitter split `"clause. [[id]] next clause"` at the period, leaving `[[id]]` as the *start* of the next fragment instead of the *end* of the previous one. Fixed by stripping leading `[[...]]` tokens from each fragment and prepending them to the preceding sentence. All 15 tests then passed first run. `docgen validate` exits 0 on clean stub output, exits 1 on uncited sentences.
- **Outcome:** Done. 172/172 tests pass.
- **Screenshot:** _(none this session)_

### 2026-10-16 | Task 2b.6 | Plan + Agent
- **Goal:** Build `BobShellSummarizer` — the real LLM backend using `bob run --format json` non-interactively; add per-node failure handling so one bad summarizer call never kills the whole run.
- **Prompt (short):** "Plan task 2b.6." Before implementing, verified three things: (1) `echo "say hello" | bob run --format json --max-cost 0.1` returns `{"status":"success","last_message":"..."}` ✓; (2) `shutil.which("bob")` resolves to `bob.CMD` on Windows, subprocess runs it without `shell=True` ✓; (3) user specified: needs_human_review nodes should be written to summaries.json and skipped by the validator.
- **What Bob produced:** `summarize/bob_shell.py` — `BobShellError`, `_find_bob`, `_call_bob` (NamedTemporaryFile stdin, JSON parse, delete=False for Windows), `BobShellSummarizer` (API key check at init, `_find_bob`, 2-attempt retry with 5s backoff); `hierarchy.py` — `NEEDS_HUMAN_REVIEW_BACKEND` constant, `_call_summarizer` helper wrapping every summarizer call in try/except; `citations.py` — skip loop for `needs_human_review` backend; `cli.py` — `bob_shell` backend + `--max-cost`/`--max-turns` flags; `tests/test_bob_shell.py` (10 tests).
- **What I verified or changed:** All 10 tests passed first run including retry, missing API key, validator skip, and hierarchy continue-on-failure. Full suite: 182/182 pass. Live `bob run` test confirmed JSON schema before writing code.
- **Outcome:** Done. `docgen summarize --backend bob_shell` is now the real end-to-end pipeline.
- **Screenshot:** _(none this session)_

### 2026-10-16 | Extractor + hierarchy fixes | Plan + Agent
- **Goal:** Fix six gaps found after the first `bob_shell` summarization run: per-span function hashes (E1), route hashes and real request-model edges (E4+E5), synthesized package nodes for the system summary (S2), and route data reaching function prompts with citeable route IDs (S4a+S4b).
- **Prompt (short):** User reported issues from live run (32 citation errors, system summary refusal, no package level, bad request-model edges). Planned fixes across extractor and hierarchy layers; user approved with amendments: route hash_struct must include handler+models; route IDs must be citeable; implicit Pydantic body parameters (no Body default) must also be detected.
- **What Bob produced:** `extract/core.py` — `_make_function_node` now computes per-span `hash_source` (fixes whole-file hash bug); `extract/adapters/fastapi.py` — `_extract_request_models_from_handler` (AST-based, detects explicit Body() and implicit Pydantic params, filters Body_... auto-names), `_openapi_to_facts` computes `hash_struct`/`hash_source` from method+path+status+handler+models; `extract/packages.py` (new) — `synthesize_packages` groups MODULE nodes by parent directory into PACKAGE nodes with CONTAINS edges and nested package links; `cli.py` — Step 5b wires `synthesize_packages`; `summarize/hierarchy.py` — `_build_edges_by_from` now also indexes HANDLES edges by `to_id` (the function); `summarize/prompts.py` — `"handles"` added to `_CITEABLE_EDGE_TYPES`, `allowed_fact_ids` adds `edge["from"]` for handles (the route id), `_RENDERED_EDGE_TYPES` includes `"handles"` first.
- **What I verified or changed:** Design nuance discovered during implementation: HANDLES edges are stored as `{from: route_id, to: func_id}`, so `allowed_fact_ids` must add `edge["from"]` not `edge["to"]` for `handles` type. Bob caught this when writing the test and fixed `allowed_fact_ids` accordingly. All 15 new tests passed (2 core, 6 fastapi, 5 packages, 1 hierarchy, 1 prompts). Full suite: 197/197.
- **Outcome:** Done. `docgen extract` now emits package nodes, per-span function hashes, route hashes, and real request-model edges. Handler function prompts receive route context and can cite route IDs.
- **Screenshot:** _(none this session)_

### 2026-10-17 | Tasks 3.1–3.5 | Plan + Agent
- **Goal:** Implement the full Phase 3 Renderers + Freshness pipeline: `docgen render`, `docgen check`, and `docgen update`.
- **Prompt (short):** Handoff document from previous chat pasted in; user confirmed plan and said "yes implement".
- **What Bob produced:** `src/docgen/render/markdown.py` — `render_all()` now calls `render_api_table` internally (D-040) and returns `(list[PageRecord], list[tuple[str,str]])`. `src/docgen/check/drift.py` — `find_stale_pages` (hash_struct-only comparison) + `warn_if_facts_stale` (mtime check). `src/docgen/check/update.py` — `UpdatePlan` dataclass + `plan_update` (identifies stale nodes and nodes needing re-summarization). `src/docgen/cli.py` — `_run_render`, `_run_check`, `_run_update` functions + proper subparser wiring with `--config`, `--fresh`, `--backend` flags. `tests/test_render.py` (8 tests), `tests/test_manifest.py` (4 tests), `tests/test_drift.py` (6 tests), `tests/test_update.py` (4 tests), `tests/fixtures/freshness/` (3-file fixture repo + docgen.toml), `tests/test_freshness_gate.py` (4 integration tests).
- **What I verified or changed:** All 26 new tests passed first run. Full suite: 223/223 pass. Decisions D-040–D-042 recorded.
- **Outcome:** Done. Phase 3 complete. Next: Phase 3e (eval command + showcase repo).
- **Screenshot:** _(none this session)_

### 2026-10-18 | Task 4.4 | Agent (Code)
- **Goal:** Implement the Streamlit documentation viewer over `generated/pages/`.
- **Prompt (short):** Build `viewer/app.py` with sidebar file tree, mermaid split-render via `streamlit-mermaid`, default `index.md`, and top bar with page title + path.
- **What Bob produced:** `viewer/app.py` (162 lines): `_all_pages()` (rglob), `_repo_rel()` (abs→POSIX relative), `_page_title()` (first `# ` heading), `_split_mermaid()` (regex split on ` ```mermaid ` blocks, returns `list[tuple[kind, text]]`), `_render_page()` (top bar + per-segment dispatch to `st.markdown` or `st_mermaid`), `_build_sidebar()` (top-level buttons + folder expanders with active-page highlight). Installed `streamlit` and `streamlit-mermaid` into `.venv`. Smoke-tested all logic in isolation (72 pages found, 1 mermaid block in index.md, all assertions pass).
- **What I verified or changed:** Confirmed `streamlit-mermaid` and `streamlit` import without error. Verified `_split_mermaid` handles: no diagram, diagram only, text-before+diagram+text-after. `PAGES_DIR` uses `Path(__file__).parent.parent` so it resolves correctly regardless of CWD.
- **Outcome:** Done. Run with `streamlit run viewer/app.py`. Task 4.4 ticked.
- **Screenshot:** _(none this session)_

### 2026-10-29 | Handler resolution fix | Plan + Agent
- **Goal:** Implement `docs/plan-handler-resolution-fix.md` — resolve FastAPI handlers by exact node ID (`__module__` + `__qualname__`) instead of name alone, unwrap `Body_*` request wrappers, and stop silently guessing when class names collide.
- **Prompt (short):** "The plan for fixing the fastapi introspection adapter is written in docs/plan-handler-resolution-fix.md. Implement it as-is and only touch the files mentioned in the plan." Followed sub-tasks 1 → 2a → 2c → 3 → 4, then the mandatory regression probe, then the doc entries.
- **What Bob produced:** `src/docgen/extract/adapters/fastapi.py` — introspection script records `handler`/`module`/`qualname`/`name` behind `getattr(..., None)` guards; new `_qualname_to_node_id` and `_resolve_handler` (returns `(node, failure_reason)`); `_find_function_node` deleted; `_extract_body_schema_name(request_body, components)` unwraps one `Body_*` level; `_find_class_node` returns `None` for 0 or 2+ matches; new `_resolve_model_id` emits `ambiguous_class_name:<Name>`; `dotted_to_path` param added to `_openapi_to_facts` and `extract`. `src/docgen/cli.py` — Step 7 passes `dotted_to_path=dotted_to_path`. `tests/test_handler_resolution.py` (new, 9 tests: plan tests 1–7 plus direct helper checks). `tests/test_fastapi_adapter.py` — imports and every `_openapi_to_facts`/`extract` call site updated with `module`/`qualname`/`dotted_to_path`; tests 8–10 folded into `test_real_repo_route_consistency` with helper `_cross_check_handles`. `docs/memory.md` — D-044 + session log row.
- **What I verified or changed (regression probe, mandatory step 6):** backed up the fixed file, edited `_openapi_to_facts` back to a name-only `_find_function_node`-equivalent scan, ran `pytest tests/test_handler_resolution.py tests/test_fastapi_adapter.py -v`, then restored from the backup (sha256 match, probe text absent).
  - **With the name-only scan:** test 1 failed (bound `repo.py::Repo::create` when the method came first); test 2 failed (`GET /b` bound to `routes_a.py::list_items`); test 8 failed listing exactly the four original bad edges — `GET /api/articles/feed`, `DELETE /api/articles/{slug}/favorite`, `POST /api/articles/{slug}/comments`, `GET /api/tags` → repository methods — and aborted the test before test 9 ran, so test 9's checker was executed separately on the same graph: **4 violations**, each naming the AST declaration under `target/app/api/routes/...`; test 5 failed because the probe kept the old generic unresolved reason (no `locals` detail). Tests 3, 4, 6, 7, 10 passed under the probe as intended.
  - **After restore:** `21 passed` for the two files; full suite `231 passed, 1 failed`.
- **Deviations from the plan (all deliberate):**
  1. The plan predicted only tests 1/8/9 would fail under the probe. Test 2 also fails — two route files sharing one handler name is precisely what a name scan gets wrong — and test 5 fails because it asserts the new typed failure reason. Both are expected consequences of the tests' stated intent.
  2. Test 8 initially passed *even with the name-only scan*: `walk_repo()` yields `app/api/...` before `app/db/...`, so the first name match happened to be the right handler (the committed `generated/facts.json` shows the 4 wrong bindings, so the real run saw a different node order). Test 8 now passes `list(reversed(all_nodes))` to `extract(...)`, putting the colliding repository methods first. The probe then failed with exactly the 4 original bad edges, making the guard order-independent.
  3. On an ambiguous class name the plan's snippet emitted `Unresolved` and then fell through to `external:`, while its test 6 required no RESPONSE_MODEL edge. Implemented the test's contract: Unresolved is emitted and the edge is dropped.
- **Verified on target:** 19/19 route nodes, 19/19 HANDLES edges, 0 class-method targets, 0 adapter Unresolved, and `route:POST /api/articles/{slug}/comments → target/app/models/schemas/comments.py::CommentInCreate` now present. The only full-suite failure is the pre-existing `tests/test_seeded_bug.py::test_create_article_returns_201` — the seeded `HTTP_200_OK` bug is committed at `target/app/api/routes/articles/articles_resource.py:55`; untouched by this change.
- **Outcome:** Done. The resolver no longer binds same-named repository methods to routes, and the missing request-model edge is restored. `generated/` was not regenerated (not in the plan's file list), so `docgen extract` → `docgen update` still needs to run to refresh the 4 route pages and `api.md`.
- **Screenshot:** _(none this session)_

### 2026-11-02 | Prompt quality fixes (2b.8) | Plan + Agent
- **Goal:** Implement `docs/plan-2b-prompt-quality-fixes.md` — six prompt/hierarchy fixes found while reading the summarize phase.
- **Prompt (short):** "The plan is written at docs/plan-2b-prompt-quality-fixes.md. Implement the plan as-is, don't deviate, and touch only the files mentioned."
- **What Bob produced:** `src/docgen/summarize/prompts.py` — `render_edges` renders `from` for `handles`; `_CITEABLE_EDGE_TYPES`/`_RENDERED_EDGE_TYPES` gained `request_model`/`response_model`; the `CITATION_RULES` example cites an in-repo id instead of `[[external:fastapi.HTTPException]]`; `PROMPT_VERSION` is a 16-char sha256 of `SYSTEM_PREAMBLE + CITATION_RULES + OUTPUT_INSTRUCTION + _GROUNDING_RULE + _LEVEL_FOCUS.values()`; stale "2b.3 should fold it in" comment deleted. `src/docgen/summarize/hierarchy.py` — `_PROMPT_FACTS_DROP` + filtered facts for the backend call; `hash_input_with_children` hashes child summary text; `_build_edges_by_from` indexes model edges.
- **Deviations (deliberate):**
  1. Plan B's todo indexes model edges by `from_id` = the route node, but ROUTE nodes are never summarized, so the plan's stated outcome (handler prompt shows `request_model`) would not happen. Model edges are additionally indexed on the handler resolved through HANDLES. Verified: `create_comment_for_article` now renders `- handles: route:POST /api/articles/{slug}/comments`, `- request_model: ...::CommentInCreate`, `- response_model: ...::CommentInResponse`.
  2. Plan D replaces `req.facts` with the filtered dict, but `hash_input_with_children` reads `hash_struct`/`hash_source` from that dict — filtering first would make body edits invisible to the cache. The key is computed from the full dict; only the request handed to the backend is filtered.
  3. `test_run_hierarchy_reruns_on_hash_change` asserted the parent also re-runs, which fix E deliberately prevents when the prose is unchanged. It now asserts exactly one re-summarization; new tests cover the positive propagation path (`test_child_text_change_reruns_parent`, prose depends on the signature) and model edges reaching the handler.
- **What I verified or changed:** `tests/test_prompts.py tests/test_hierarchy.py` → 26 passed. Full suite → 238 passed, 1 failure (`test_seeded_bug`, the pre-existing `HTTP_200_OK` seeded bug in `target/`). Ran `run_hierarchy` over the real `generated/facts.json` with a recording backend: 234 results, 6 requests carry model edges, `PROMPT_VERSION = 2ccb2d0894c1714a`, and a function's prompt facts keys are `['async_flag','decorators','file','id','lines','name','returns','signature']` (no `type`/`hash_*`).
- **Outcome:** Done. Every cached summary is now stale (template hash changed). `docgen summarize --backend bob_shell` → `docgen validate` → `docgen render` → `docgen check` still needs to run; not run here because it spends Bobcoins and needs the Bob API key.
- **Screenshot:** _(none this session)_

### 2026-11-02 | Task 2b.9 | Plan + Agent
- **Goal:** Implement `docs/plan-parallel-summarization.md` — depth-batched parallel summarization, `--workers` on `summarize`/`update`, and one summarizer factory shared by both commands.
- **Prompt (short):** "okay plan approved and yes for all 4 of these … lets implement this plan. stick to the plan, make only those changes mentioned in the plan."
- **What Bob produced:** `src/docgen/summarize/hierarchy.py` — `batched_topological_order` (CONTAINS-depth batches, deterministic); `run_hierarchy(..., max_workers=1)` with a per-batch `ThreadPoolExecutor`, worker clamping, and a `_process_node` closure whose results are written to `results` by the main thread in submission order; module docstring documents the concurrent-call contract. `src/docgen/cli.py` — `_build_summarizer(args, output_dir)` as the single backend construction point for `_run_summarize` and `_run_update` (unknown backends now exit; `update --backend manual` now works); `--workers` on both subparsers; `getattr(args, "workers", 1)` at both call sites. `tests/test_hierarchy.py` — 3 batching tests + 4 parallel tests (output/order equality, 16-node timing, single-failure containment, clamp). `tests/test_summarize.py` — 3 factory tests.
- **What I verified or changed:** targeted tests `33 passed`; full suite `248 passed, 1 failed` (`test_seeded_bug`, the committed `HTTP_200_OK` seeded bug in `target/`). On the real graph: batches `154/52/16/6/4/1` (233 nodes); a stub run at 1 and 4 workers produced identical 234-result lists element-by-element; replaying the new cache made 0 calls at either worker count. Live: a 10-function fixture at 1 vs 4 workers produced identical node order, 15/15 summaries each, 0 failures; text differed run-to-run (0/15 identical), and a 1-vs-1 control also differed 0/15, so that is LLM nondeterminism, not the parallel path. Real target: `docgen summarize --backend bob_shell --workers 4` → 234/234 summaries in **6 min 27 s**, 0 `needs_human_review` (previously ~24 min sequential).
- **Deviations / observations:** the plan's live criterion "same text" is unsatisfiable with a nondeterministic LLM; the meaningful checks (node order, counts, zero failures, deterministic backend equality in tests) pass. `docgen validate` on the fresh bob_shell prose still reports 33 citation errors (one `unknown_id` from a truncated route id, 32 `uncited_sentence`) — a pre-existing prompt/validator gap tracked under 2b.5/2b.7, not caused by this change. Rendered pages were not refreshed (out of scope); `generated/summaries.json` now holds the new summaries.
- **Outcome:** Done. All four approved decisions implemented (workers default 1, factory included, `--workers` on `update`, live verification run).
- **Screenshot:** _(none this session)_
