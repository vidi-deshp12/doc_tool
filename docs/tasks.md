# Tasks

Give Bob **one task at a time** using this template:

> Read `.bob/rules/rules.md`, `docs/PRD.md`, `docs/architecture.md`, and `docs/memory.md`. Work only on task **X.Y** in `docs/tasks.md`. Start in Plan mode: list the files you'll touch and the tests you'll add, and wait for my OK. Then implement, run the tests, and update `docs/tasks.md`, `docs/memory.md`, and `BOB_LOG.md`.

Status legend: `[ ]` todo, `[x]` done, `[~]` in progress. Dates are the plan from Oct 5; see `project_roadmap.md`.

**Task IDs = phase label + number** (`0.1`, `1.2`, `2a.8b`, `2b.1`, `3.4`, `3e.1`, `4.2`, `5.1`). Say the full ID when asking Bob for a task, e.g. "work on task 2b.1".

---

## Phase 0: Foundations (Oct 5)
- [x] **0.1 Project repo.** Create the GitHub repo, `.gitignore` (include `target/`, `.venv/`, `__pycache__/`), commit skeleton folders from `architecture.md` §3. *Done when:* repo pushed; folder skeleton present.
- [x] **0.2 Environment.** `pyproject.toml`, venv, pytest runs an empty test. *Done when:* `pytest` passes on a trivial test.
- [x] **0.3 Bob rules.** Run Bob's `/init`, then add `.bob/rules/rules.md` from this pack. *Done when:* a Bob chat shows it follows a rule (e.g. asks which task).
- [x] **0.4 Bob Shell scripted-mode check.** Read bob.ibm.com/docs/shell; test whether a prompt can be run non-interactively and its output captured. Record in `memory.md` as decision D-0xx. *Done when:* decision written: Bob Shell backend yes/no.
- [x] **0.5 BOB_LOG.md.** Copy the `BOB_LOG.md` skeleton to the project root and fill in the first entry (the request-trace session already done). Add a Bobalytics screenshot if available. *Done when:* file exists with at least one complete entry.

## Phase 1: Understand the target (Oct 5-6)
- [x] **1.1 Exploration (reduced for time).** Skip broad exploration. Save the existing Bob session that traced `POST /api/articles` into `BOB_LOG.md`. Skim only the files that task 1.4 touches. *Done when:* the trace is logged. (Optional if time allows: write a half-page in your own words on what the app does and what each folder in `app/` is for.)
- [x] **1.2 Ground truth.** Script that imports the target app and dumps routes/models from `app.openapi()` to `eval/ground_truth.json`. This is the **independent answer key for the `ast`-only extractor (task 2a.8b)**. It does not grade the introspection adapter (same source, circular). *Done when:* file lists every route (method, full path) and schema; also cross-check the route count by hand against a text search for route decorators.
- [x] **1.3 Confirm DB approach.** Inspect how the target stores schema (migrations/SQL/aiosql). Record in `memory.md`. Decides whether ERD is feasible.
- [x] **1.4 Seed a bug.** One realistic bug in `target/` plus a failing test that catches it. *Done when:* test fails with bug, passes when reverted. Log in `memory.md`.

## Phase 2a: Fact extractor (Oct 7-9)
- [ ] **2a.1 Schema + store.** `facts/schema.py` dataclasses (Node, Edge, Unresolved, FactGraph); `facts/store.py` stable JSON. *Done when:* round-trip test; output byte-identical on repeat.
- [ ] **2a.2 Config + walker.** `config.py` loads `docgen.toml`; `walker.py` yields root-relative POSIX paths, honoring excludes. *Done when:* test on a fixture repo lists expected files only; works with Windows paths.
- [ ] **2a.3 Core per-file extraction.** Port `spike.py` into `extract/core.py`: modules, classes (fields, bases), functions, decorators, docstrings, imports. Decorator-inclusive spans; both hashes (`architecture.md` §5). Per-file `SyntaxError` handling. *Done when:* tests on fixtures incl. multi-line decorators; editing a decorator changes `hash_struct`; editing a comment does not.
- [ ] **2a.4 Module index + import resolution.** `extract/modules.py`: dotted name ↔ path, resolve absolute/relative imports, aliases, `__init__` re-exports; mark library imports `external`; flag star imports. *Done when:* every in-repo import in `target/app` resolves or appears in `unresolved`.
- [x] **2a.5 Class resolution.** `extract/classes.py`: resolve bases across files, flatten inherited fields (in-repo bases only), tag Pydantic models. *Done when:* `ListOfArticlesInResponse` shows its fields via resolved class.
- [x] **2a.6 Body facts.** `extract/bodies.py`: `raises` (type + args), raw `calls` text, per function. *Done when:* tests on fixtures; `HTTPException(status_code=...)` captured.
- [x] **2a.7 Unresolved report.** Collect dynamic-import, `getattr`, star import, unparsed-file, unresolved-name entries with reason + location. *Done when:* report is a section in `facts.json` and a readable summary prints from the CLI.
- [x] **2a.8a FastAPI adapter: routes via introspection.** `adapters/fastapi.py`: import app in subprocess (timeout, dummy env), read routes (method, full path, handler, status, models), link `route -handles-> function`. If import fails, fall back to 2a.8b output and add a notice. *Done when:* runs on the dev repo and its route set is consistent with `eval/ground_truth.json` (this is a consistency check, **not** an accuracy measure, since both read the same source).
- [x] **2a.8b FastAPI adapter: routes via `ast` only.** Find route decorators (`@<router>.<method>(...)`) and `include_router(..., prefix=...)` calls; resolve the router argument through import resolution (2.4) to compute full paths. If a prefix can't be resolved, emit the relative path and an `unresolved` entry. *Done when:* graded against `eval/ground_truth.json`: 100% of routes found with correct method and handler; full-path accuracy reported as a percentage. **This is the graded extractor.** If time is short, grade method + handler + relative path only. **Implemented Tier A (relative path + method + handler). 19/19 routes, 100% recall. Full-path Tier B deferred to v0.2 (D-030).**
- [x] **2a.9 FastAPI adapter: dependency tree.** Recursive `depends_on` edges via name resolution, `via` = parameter/decorator, factory calls recorded with args. Cycle guard. *Done when:* `create_new_article` shows the full chain to auth and DB dependencies; update/delete show the permission dependency. **Implemented. 66/66 DEPENDS_ON edges resolved (0 external remaining). No cycles on target. 130 tests pass.**
- [ ] **2a.10 Extractor gate.** `eval` check: the `ast`-only route extractor (2a.8b) finds 100% of routes and models vs ground truth; unresolved list reviewed by hand. Record result in `memory.md`. **Do not start Phase 2b until this passes.**
- [ ] **2a.11 (Tier 2) aiosql linking.** Parse `.sql` name comments; link `queries.<name>` calls to `sql_query` nodes. Only if schedule allows.

## Phase 2b: Cited summarizer (Oct 10-11)
- [ ] **2b.1 Summarizer interface.** `summarize/base.py` protocol + `StubSummarizer`; `ManualSummarizer` reading files from a folder. *Done when:* pipeline runs end to end with Stub in tests.
- [ ] **2b.2 Prompts + citation format.** `prompts.py`: per-level prompts; `[[fact_id]]` citations. 
- [ ] **2b.3 Hierarchy driver + cache.** Bottom-up function→module→package→system; cache keyed by input hashes. *Done when:* re-run with no changes makes zero summarizer calls (test with call counter).
- [ ] **2b.4 Citation validator.** IDs exist; each sentence has a citation; report broken ones. 
- [ ] **2b.5 Entailment spot-check.** Sample N claims, check cited facts support them; produce a sheet for hand-grading.
- [ ] **2b.6 Real backend.** `BobShellSummarizer` if task 0.4 said yes; otherwise document the manual flow (Bob in the IDE writes summaries into the folder). 
- [ ] **2b.7 Summarizer gate.** No broken citations; user reads 10 summaries and confirms accuracy.

## Phase 3: Renderers and freshness (Oct 12-13)
- [ ] **3.1 Renderers.** Architecture overview, per-module pages, Mermaid dependency diagram (import graph), API endpoint table. Render only from facts + summaries.
- [ ] **3.2 Manifest.** Page → fact IDs + `hash_struct` at generation time.
- [ ] **3.3 `check`.** Re-extract, compare, exit 1 and list stale pages on drift.
- [ ] **3.4 `update`.** Regenerate only stale pages; early cutoff for ancestors.
- [ ] **3.5 Freshness gate (3 tests).** (1) fresh run → check passes. (2) edit one file → check fails naming the right pages. (3) update rebuilds only those → check passes. Harmless edit (comment/format) → no drift.

## Phase 3e: Eval and showcase repo (Oct 13-14; called Phase 3.5 in the handoff)
- [ ] **3e.1 Eval command.** Route/model recall; claim sample sheet; drift false-positive suite; incremental savings count.
- [ ] **3e.2 Showcase repo.** Pick a non-FastAPI, lesser-known repo (criteria in `PRD`/handoff). Run core layer on it; record what degrades. Also run on a renamed-identifier copy of the dev repo.
- [ ] **3e.3 Results table** in README.

## Phase 4: Story and viewer (Oct 14-16)
- [ ] **4.1 Find the seeded bug using only the docs;** Bob fixes it; record before/after.
- [ ] **4.2 Re-run `check`/`update`;** record which pages changed.
- [ ] **4.3 Add one small feature** to the target using the docs as context.
- [ ] **4.4 Streamlit viewer** over `generated/`.
- [ ] **4.5 Deploy** (Streamlit Community Cloud); verify from a clean browser.

## Phase 5: Submission (Oct 16-17; Oct 18 buffer only)
- [ ] **5.1 README** with setup + test instructions a stranger can follow.
- [ ] **5.2** 100-word description, tech stack list, improvements-made list.
- [ ] **5.3 Pitch deck PDF** (team/project intro, summary, roadmap) with Bobalytics screenshots and eval numbers.
- [ ] **5.4 Demo video** ≤3 min, uploaded to YouTube.
- [ ] **5.5 Submit** with Theme 1 selected; verify all links open logged-out.

## Stretch (only if ahead of schedule)
Flask adapter; grounded Q&A; onboarding guide; git-history "why"; "needs human review" flags.
