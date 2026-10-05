# Project Handoff: Grounded, Self-Updating Docs for Undocumented Python Repos

*Written for continuing this project in a new thread. Last updated Oct 4, 2026. Read Section 12 first for caveats and the user's working style. **Date correction:** earlier calendars assumed Sep 30 as day one; today is Oct 4, so about 14 days remain (deadline Oct 18, 11:59 PM ET). The current calendar is in `docs/project_roadmap.md`. Sections 13 and 14 hold the locked v1 scope and the list of agent context files; where they conflict with earlier sections, 13 and 14 win.*

---

## 1. Context

- **Who:** A masters student entering IBM's "Building with IBM Bob" hackathon (hosted via AngelHack). Team size is not yet confirmed (solo or up to 5; ask).
- **Deadline:** Oct 18, 2026, 11:59 PM ET. Target submitting by Oct 17. Winners announced Oct 28.
- **Track:** Theme 1, Students / Early Career, "Explore, Fix, and Build": start with an unfamiliar application, use Bob to understand it, fix a seeded issue, and add a useful feature. Documentation is explicitly listed as a use case.
- **Prizes:** $1,000 + IBM swag for 1st place per theme; runner-up gets swag and a marketing feature. All eligible submissions get Bob certificates.
- **Judging criteria:**
  - Tool usage and depth of adoption: **30%** (Bob must be a core part of the workflow, not bolted on at the end)
  - Innovation and use-case relevance: **30%** (credible, realistic use of Bob)
  - Functionality and technical execution: **30%** (works as demoed, sound for 3 weeks)
  - Presentation and clarity: **10%**
- **Submission requirements:** public GitHub repo (code, README, deployment files, test instructions); project description (max 100 words); selected track; tech stack list; improvements made during the hacking period; PDF pitch deck (team/project intro, summary, future roadmap); demo video (max 3 min, pre-recorded, on YouTube); live project demo URL.
- **IBM Bob:** an IDE assistant plus a CLI (Bob Shell). Modes include Ask, Plan, Code, Review, Orchestrator. There is a **Bobalytics** feature that tracks usage and contribution (docs: bob.ibm.com/docs/ide/features/bobalytics; Shell docs: bob.ibm.com/docs/shell). **It is not confirmed that Bob can be called programmatically from user code.** Rules say Bob is what you build *with*.
- **Environment so far:** Windows, PowerShell. Bob IDE installed (context-menu entries and PATH option checked). Promo code was obtained; user reports setup is done. Project folder: `E:\ibm_bob_docs_tool`. Target repo cloned to `E:\ibm_bob_docs_tool\target`.

---

## 2. What we're building

A tool that reads an undocumented Python codebase and produces documentation (architecture overview, module pages, API endpoint table, dependency diagram, ERD), then detects when the docs have gone stale and updates only the pages that need it.

**Why this and not "AI explains your repo":** that space is crowded (Bob itself, DeepWiki, Copilot, Sourcegraph, Swimm). The differentiators are:
1. **Trust:** every claim is tied to specific code facts (grounded, citable).
2. **Freshness:** drift detection and incremental regeneration, so docs don't rot.
3. **Scale:** hierarchical summarization, so repos larger than a context window work.
4. **Measured accuracy:** published numbers from an eval harness, not just a pretty demo.

**Core design principle:** *everything factual is computed deterministically; the LLM only writes prose on top of those facts.* Structure (routes, imports, models, diagrams) comes from code analysis. The LLM explains but never invents structure.

**Honest limitation to state in the pitch:** the tool documents what the code *does*, not *why* (intent and history live outside the code). Git history is a possible partial fix (stretch).

---

## 3. Plain-language pipeline

```
target repo → [extract] → facts.json → [summarize] → summaries.json → [validate]
           → [render] → docs/ → [check / update] → [viewer]
```

1. **Extractor (no AI):** Python script using `ast` (plus runtime introspection for routes) lists facts: files, functions, classes, routes, imports. Output: `facts.json` (the fact graph).
2. **Summarizer (AI):** writes plain-English explanations bottom-up (function → module → package → system), each level seeing only the facts and child summaries it needs. Claims cite fact IDs.
3. **Checker (no AI):** compares the facts now against the facts the docs were built from, and flags stale pages.

**Planned repo layout:**
```
/target         cloned app, pinned commit
/src/extract    ast + introspection → facts.json
/src/summarize  facts → cited summaries
/src/render     summaries + facts → markdown / mermaid
/src/check      hashing, drift check, incremental update
/viewer         Streamlit app (reads committed docs/, no LLM at runtime)
/docs           generated output (committed)
/tests  BOB_LOG.md  README.md
```
Add a config file (repo path, package filters) so the tool stays repo-agnostic.

---

## 4. The fact graph

### 4.1 What it is
A JSON structure of **nodes** (things in the code) and **edges** (relations), where every node has a stable ID. Summaries point back to these IDs.

**Nodes:** package, module, class, function/async function (including methods), route, model/schema, and later config/SQL assets.
**Edges:** `contains` (module → function), `imports` (module → module), `inherits` (class → base), `handles` (route → function), `depends_on` (function → dependency function), and later `calls`.

**Example node:**
```json
{
  "id": "app/api/routes/articles/articles_resource.py::create_new_article",
  "type": "async_function",
  "lines": [58, 79],
  "def_line": 59,
  "signature": "create_new_article(article_create: ArticleInCreate=Body(...), user: User=Depends(...), ...)",
  "returns": "ArticleInResponse",
  "decorators": [{"text": "router.post('', status_code=..., response_model=..., name='articles:create-article')",
                   "route": {"method": "POST", "path": "", "kwargs": {"...": "..."}}}],
  "depends_on": ["get_current_user_authorizer()", "get_repository(ArticlesRepository)"],
  "decorator_depends": [],
  "docstring": null,
  "hash": "a3d87cf6be"
}
```

### 4.2 What `ast` gives reliably (exact, parsing not guessing)
Names, line ranges, signatures, decorators, docstrings, class bases, class-level annotated fields, imports (including relative ones with `level`), top-level assignments (e.g. `router = APIRouter()`), the folder-based package → module hierarchy, and per-node source hashes. The import graph from this drives the dependency diagram.

### 4.3 Gap catalog: what `ast` alone cannot give us

**All gaps are listed here. Which ones go into scope is still to be decided.** "Proposed" is a starting suggestion only.

| # | Gap | What goes wrong | Possible bridge | Proposed |
|---|---|---|---|---|
| G1 | **Full route paths** | Decorator shows `@router.post("/")`; the real URL is built where routers are combined (`include_router(prefix=...)`, believed to be in `app/api/routes/api.py`). Observed: paths came out as `""` and `/{slug}`. | For FastAPI, import the app and read `app.routes` / `app.openapi()` for exact paths, methods, handlers, request/response models. Keep `ast` as fallback. | **In** |
| G2 | **Dependency injection** | `Depends(get_article_by_slug_from_path)` is a bare name. Its meaning (auth, permissions, DB access) is in another file. Factory calls like `get_repository(ArticlesRepository)` return a function whose behavior depends on arguments. Dependencies can sit in parameters *and* in decorators (`dependencies=[Depends(...)]`). Runtime effects (what the dependency actually enforces) are invisible. | Resolve name → import → module → function node; record `depends_on` and `decorator_depends` as edges; summarize each dependency function and link. Treat factories as "unresolved factory" with arguments recorded. | **In** (name resolution); factory semantics later |
| G3 | **Call graphs** | `service.save(x)`: `ast` can't know what type `service` is, so can't link to the right method. Inheritance, duck typing, and callbacks make this worse. | MVP: skip. Later options: record raw call names per function as facts with an "unresolved" flag; type-hint-based resolution for simple cases; tools like `jedi`/`pyright`. | **Out** for MVP |
| G4 | **Dynamic behavior** | `getattr`, dynamic/`importlib` imports, `from x import *`, decorators that wrap decorators, metaclasses, monkeypatching, registering handlers in loops, string-based lookups. | Detect and list in an explicit **`unresolved`** section so nothing is silently missed. Never guess. | **In** (detect and report only) |
| G5 | **Cross-file name resolution** | Relative imports, re-exports through `__init__.py`, aliases (`import x as y`), circular imports. | Build a module-level symbol table; resolve imports to module IDs; flag anything that fails. | **In** |
| G6 | **Type and inheritance across files** | `response_model=ArticleInResponse` is just text. Pydantic fields inherited from a base class in another file aren't in the subclass body. | Resolve names through the symbol table; flatten inherited fields; the OpenAPI schema from introspection also helps. | **In** (basic) |
| G7 | **Database layer is not in the Pydantic models** | The Pydantic classes are API schemas, not DB tables. I believe (unverified) this repo uses raw SQL via `aiosql`/`asyncpg` with Alembic migrations, so tables come from migrations/SQL files, not ORM classes. | Parse migration files / SQL assets for the ERD, or drop the ERD to stretch. **Check the repo before promising an ERD.** | **Decide after inspecting repo** |
| G8 | **Function-body behavior** | Spike extracts signatures but not what bodies do: exceptions raised (`HTTPException` + status), repository/service methods called, side effects. | Add simple body facts: `raises`, raw `calls` names (unresolved). Summarizer also receives the source text of each function. | **In** (raises, calls as names) |
| G9 | **Config and environment** | Settings classes, env vars, `.env`, secrets handling are not visible in routes. | Extract settings classes and `os.environ` / `getenv` usage as facts. | Later |
| G10 | **Non-Python assets** | SQL files, migrations, Dockerfile, CI config, tests are not parsed by `ast`. | Treat as separate asset node types; start with SQL/migrations if needed for G7. | Later |
| G11 | **Imperative app wiring** | Middleware, exception handlers, startup/shutdown events, `app.add_event_handler(...)` calls register behavior outside decorators. | Introspect the app object (middleware stack, exception handlers) and/or scan for `app.add_*` calls. | Later |
| G12 | **Nested functions, closures, conditional definitions** | Spike only handles top-level functions and class methods. `if TYPE_CHECKING:` blocks, nested defs, and lambdas are skipped. | Walk nested scopes; tag conditional definitions. | Later |
| G13 | **Intent / "why"** | Code can't say why decisions were made. | Feed `git log` / commit messages per module (stretch). State the limit openly otherwise. | Stretch |
| G14 | **Runtime introspection risks** | Importing the app *executes the target's code*. Needs its dependencies installed, env vars set, possibly a DB at import time. Untrusted code is a security issue. | Run in a venv/container; set dummy env vars; fall back to `ast`-only when import fails and say so. | **In**, with fallback |
| G15 | **Python-version mismatch** | `ast.unparse` needs Python 3.9+. Code using newer syntax than the parsing interpreter fails; Python 2 code can't be parsed. | Run on 3.11+; catch `SyntaxError` per file and report as unparsed. | **In** |
| G16 | **Fragile line-number citations** | Any edit shifts line numbers, making old citations wrong. | Cite symbol/fact ID plus line; regenerate lines on update; validate IDs, not just lines. | **In** |
| G17 | **Hash granularity** | File-level hashes over-trigger (comment edits flip them). Function-body-only hashes under-trigger (decorator edits don't change them, a bug found and fixed in the spike). | Hash *facts* (signature, decorators, routes, imports), and include decorators in the span. | **In** |

### 4.4 Spike findings (what actually happened)

A single-file spike (`spike.py`, ~60-line concept, now slightly larger) ran against the real file `target/app/api/routes/articles/articles_resource.py` (120 lines, 5 endpoints). Result: **the approach passes**: a useful paragraph (endpoints, methods, status codes, response models, dependencies) can be written from the JSON alone.

Findings from the real output:
1. **Bug (fixed in spike):** `ast` reports a function's line at `def`, not at its decorators. So `lines` excluded decorators and the hash covered only the body, meaning a change to a route's path or status code would **not** register as drift. Fix: span now starts at the first decorator; a new `def_line` field keeps the original line. Verified by test: editing a decorator now changes the hash.
2. **Bug (fixed in spike):** permission checks in `dependencies=[Depends(check_article_modification_permissions)]` inside the decorator were missing from `depends_on`. New field `decorator_depends` captures them. This matters because these are the authorization rules for update/delete.
3. **Paths are relative** (`""`, `/{slug}`): confirms G1 and the plan for introspection.
4. **Dependencies are bare names:** confirms G2; imports already show the source module, so resolution is feasible.
5. **No docstrings** in this code, so summaries must come from source plus body facts (G8).
6. **Output is noisy:** the `routes` field duplicates data inside `decorators`; JSON was ~2.5x the size of the source. Trim duplicates before sending to an LLM.

**Windows note:** PowerShell's `>` redirect writes UTF-16, which made `out.json` look blank. The script now accepts an output filename: `python spike.py <file.py> out.json` (writes UTF-8). The user's first run produced the correct JSON this way.

**Status of the updated script:** the fixed `spike.py` was delivered as a file; confirm the user replaced their copy and re-ran it (check that `lines` now starts at the decorator).

---

## 5. Pressure test: how useful, and how good must it be

### 5.1 Which features carry value

| Feature | Value | Bar to be useful |
|---|---|---|
| Drift detection | High (stale docs are why docs get abandoned) | Low false positives; a noisy checker gets ignored |
| Grounded claims | High (the trust story) | Wrong claims must be rare and the rate measured |
| Deterministic facts (routes, imports, models) | Medium | Near 100% on covered items; explicit about what's unresolved |
| Prose summaries | Medium (table stakes now) | Accurate and specific, not generic |
| Diagrams | Demo value | Correct, nothing more |

Trust is asymmetric: one confidently wrong page costs more than ten right ones earn.

### 5.2 Weaknesses in the original plan, and fixes

1. **Citation validation proves less than implied.** Checking that `file:line` exists shows the reference is real, not that the claim is true. *Fix:* tie each sentence to fact IDs (symbol + line), and add a second-pass check that the cited snippet supports the claim.
2. **File-level hashing over-triggers.** *Fix:* hash facts, not files.
3. **Incremental updates can snowball** (regenerating ancestors on every change; LLM variation causes constant diffs). *Fix:* early cutoff, like build systems: if a regenerated summary is materially the same, stop propagating.
4. **A failing CI check breeds resentment.** *Fix:* default to a bot that proposes the doc update; make hard-fail optional.
5. **The "why" is missing.** *Fix:* state the limit; optionally add git history context.
6. **`ast` limits** (see Section 4.3). *Fix:* explicit `unresolved` report.
7. **FastAPI already generates OpenAPI,** so an API table alone isn't novel. *Fix (revised Oct 4, see Section 15):* the endpoint map is an enrichment, not a headline feature; `app.openapi()` is the answer key for grading our independent `ast`-only route extractor (not the introspection adapter, which reads the same source).

### 5.3 The demo repo problem and the two-repo strategy

FastAPI RealWorld is small, cleanly structured, and almost certainly in the model's training data. So (a) the scale claim is untested and (b) the model may describe the repo from memory, not from the facts, undermining the "grounded" claim.

**Decision (LOCKED Oct 4): use two repos; the showcase repo should be non-FastAPI (Flask preferred) to prove the core layer generalizes.**
- **Dev repo: FastAPI RealWorld** (`nsidnev/fastapi-realworld-example-app`, already cloned) for Phases 1-3. Small, fast iteration, built-in ground truth via `app.openapi()`.
- **Showcase repo:** larger, lesser-known, for the eval harness and the demo ("built on RealWorld, proven on a repo it had never seen").

**Showcase repo criteria:** Python with a framework the extractor handles (FastAPI or Flask; Django routing is harder statically); roughly 5k-30k lines; a real test suite (for the seeded bug); sparse docs and some mess; permissive license; pinned commit; not famous.
**Leads to inspect (unverified; I couldn't check sizes or licenses):** Netflix's Dispatch (real FastAPI + SQLAlchemy, probably large; may need to document only some packages); a mid-size FastAPI or Flask app with a few hundred GitHub stars; FastAPI's full-stack template as a fallback (very well known). Checks per candidate: `cloc`, license, tests pass on fresh clone, README doesn't already explain the architecture.

**Anti-memorization trick:** run the tool on a copy of RealWorld with identifiers renamed. If docs stay accurate, they came from the facts.

### 5.4 Eval harness: report real numbers

- Route and model recall vs `app.openapi()` ground truth (target 100%)
- Claim precision: hand-grade ~30 random claims as supported or not (target 90%+, publish it)
- Drift false-positive rate over a set of harmless edits (target near 0)
- Incremental savings: pages regenerated vs total after a one-file change

---

## 6. Phase-by-phase roadmap

**Dates below are superseded by `docs/project_roadmap.md` (compressed to start Oct 4).** Each phase produces a file the next phase consumes; **do not advance until its gate passes.** Rule of thumb: a working Phase 3 with no UI beats a half-built everything.

### Phase 0: Foundations (Sep 30 - Oct 1) *[mostly done]*
- **Build:** repo skeleton, Python 3.11 environment, pytest, working Bob setup.
- **How:** create GitHub repo; open folder in Bob IDE; have Bob scaffold in Plan mode; read Bob Shell docs for a non-interactive mode.
- **Using:** Bob IDE/Shell, GitHub, Python 3.11+, pytest.
- **Output:** skeleton, `BOB_LOG.md` with first entry, written decision on the summarizer.
- **Gate:** Bob answers a question about a file in the repo; summarizer decision written down.
- **Status:** Bob installed; target cloned; `spike.py` working. **Still open:** GitHub repo creation, `BOB_LOG.md`, Bob Shell scripted-mode check, Bobalytics check, `target/.git` nesting cleanup (delete `target/.git` or gitignore `target/` when setting up the project repo).

### Phase 1: Understand the target and seed the bug (Oct 2 - 4)
- **Build:** knowledge of an unfamiliar app, a known bug, a ground-truth list.
- **How:** use Bob Ask and Plan modes to explore `target/`, saving the sessions; seed one realistic bug (e.g. wrong status code, broken validation) with a failing test; build `ground_truth.md` from `app.openapi()` and a manual list of models/tables.
- **Output:** `ground_truth.md`, the failing test, screenshots in `BOB_LOG.md`.
- **Gate:** test fails with the bug and passes without it; ground truth complete (it grades the extractor).
- **Note:** verify the repo's actual DB approach (G7) now.

### Phase 2a: Fact extractor (Oct 5 - 6)
- **Build:** `extract` turns the whole target into `facts.json`.
- **How:** `ast` over every `.py` file (two passes: nodes/edges, then import resolution); runtime introspection for routes and OpenAPI; body facts (`raises`, raw `calls`); `unresolved` report; per-file `SyntaxError` handling. Start from `spike.py`. Build with Bob Plan then Code mode, then Review mode.
- **Using:** `ast`, `importlib`/FastAPI app import in a venv, pytest.
- **Output:** `facts.json`, `unresolved` section, unit tests.
- **Gate:** the `ast`-only route extractor finds 100% of routes (method + handler) and correct models vs the `app.openapi()` ground truth; full-path accuracy reported separately; unresolved items listed, never silently dropped. (Introspection output is a consistency check only.)

### Phase 2b: Cited summarizer (Oct 7 - 8)
- **Build:** `summarize` writes prose for each function → module → package → system.
- **How:** each level gets only the facts and child summaries it needs. Prompt requires claims to cite fact IDs. Validator checks cited IDs exist and that sentences carry citations; second-pass entailment check that the cited snippet supports the claim. Cache keyed by input fact hashes. Summarizer mechanism depends on the Phase 0 decision: **Bob Shell if scripted use works**; otherwise Bob in the IDE generates summaries into committed files while the tool validates and checks them.
- **Output:** `summaries.json`, validation report.
- **Gate:** no broken citations; hand-read 10 summaries for accuracy; re-run with no changes makes **zero** LLM calls.

### Phase 3: Renderers and freshness (Oct 9 - 12)
- **Build:** `render` generates docs; `check` and `update` keep them current.
- **How:** `docs/` with architecture overview, per-module pages, Mermaid dependency diagram (from import graph), API table (from routes), ERD (if G7 allows). A manifest maps each page to the fact hashes it depends on (derived from citations). `check` recomputes hashes and exits non-zero on drift, naming stale pages. `update` regenerates only affected pages, with early cutoff.
- **Output:** full `docs/`, `manifest.json`, `check`/`update` commands, tests.
- **Gate (three tests):** (1) fresh run, `check` passes; (2) edit one file, `check` fails and names stale pages; (3) `update` rebuilds only those and `check` passes again. Mermaid renders on GitHub. Harmless edits (comments, formatting) do not trigger drift.

### Phase 3.5: Eval harness and stress repo (Oct 12 - 13)
- **Build:** the metrics in Section 5.4 and a run on the showcase repo (plus the renamed-identifier RealWorld copy).
- **Output:** a results table for the deck and README.
- **Gate:** numbers computed and reproducible with one command.

### Phase 4: Theme 1 story and viewer (Oct 13 - 15)
- **Build:** proof the docs are useful, plus the demo UI.
- **How:** locate the seeded bug using the docs alone; have Bob fix it; re-run `check`/`update` and record which pages changed. Add one small feature to the target app with Bob, using the docs as context. Streamlit viewer reading committed `docs/` (no LLM at runtime). Deploy on Streamlit Community Cloud from the public repo.
- **Output:** fixed bug, new feature, updated docs, live URL.
- **Gate:** the viewer loads from a fresh browser with no local setup; the bug → fix → partial-update story works end to end in one take.

### Phase 5: Submission (Oct 16 - 17; Oct 18 buffer only)
- **Build:** README with setup and test instructions; 100-word description; tech stack list; improvements list; PDF deck (with Bobalytics screenshots and Bob session evidence, eval numbers); 3-minute YouTube demo; submit with Theme 1 selected.
- **Gate:** someone who has never seen the project can follow the README and run the tests.

### Stretch (only if ahead)
Grounded Q&A box ("where is auth handled?"); generated onboarding guide; "needs human review" flags on low-confidence sections; git-history context for the "why"; call-graph support (G3).

**Cut:** security audit, tech-debt scorecard, Postman export, multi-language support, Jira/Confluence ingestion.

---

## 7. Demo story
"Here's a repo nobody documented. One command produces cited docs and diagrams. I change a file, and only the affected pages update. A drift check catches stale docs. Here are the measured accuracy numbers, and here's the same tool on a repo it had never seen." Within Theme 1: docs → locate seeded bug → Bob fixes it → docs update incrementally → Bob adds a feature using the docs.

---

## 8. How to score on the "Bob usage" criterion (30%)

- Use Bob from day one for planning (Plan mode), coding (Code mode), review (Review mode), tests, and exploration (Ask mode); don't bolt it on at the end.
- Keep `BOB_LOG.md`: dated entries with screenshots of Bob sessions and Bobalytics stats.
- If scripted Bob Shell works, make the pipeline call Bob Shell (strongest story) and embed the drift check in CI via Bob Shell.
- Show Bobalytics in the deck as direct evidence.

---

## 9. Open decisions

1. **Can Bob Shell run non-interactively?** Decides how summarization is automated. Settle in Phase 0.
2. **Solo or team?** If a team, assign phases per person.
3. ~~Which gaps are in MVP scope?~~ **Resolved:** see Section 13.
4. **Showcase repo choice** (non-FastAPI, lesser-known, 5k-30k lines, real tests, permissive license).
5. **ERD feasibility** (depends on how the target stores DB schema).
6. **Hosting for the live demo link** (Streamlit Community Cloud is the current plan).

---

## 10. Immediate next steps

1. Confirm the updated `spike.py` runs and that `lines` now starts at the decorator.
2. Create the GitHub repo; resolve the `target/.git` nesting.
3. Check Bob Shell docs for non-interactive mode; log first Bob session in `BOB_LOG.md`.
4. Experiment: ask Bob to summarize `articles_resource.py` from the source, then from the JSON facts only; compare to learn what the summarizer prompt needs.
5. Write the full-repo extractor (Phase 2a), starting from `spike.py`.

---

## 11. Files and locations

- `E:\ibm_bob_docs_tool\spike.py` — single-file extractor spike (latest version has the decorator-span and `decorator_depends` fixes).
- `E:\ibm_bob_docs_tool\target\` — clone of `nsidnev/fastapi-realworld-example-app`.
- `out.json` — spike output for `target\app\api\routes\articles\articles_resource.py`.
- Run command: `python spike.py target\app\api\routes\articles\articles_resource.py out.json`

---

## 12. Notes for the next thread

**Unverified or previously wrong claims (do not rely on them):**
- An earlier part of the discussion mentioned an "ibm-bob SDK/API" that wraps Bob; its existence is **not confirmed**. Bob appears to be an IDE assistant plus CLI.
- An earlier claim that the RealWorld app uses Tortoise ORM was probably wrong. Believed instead: raw SQL via `aiosql`/`asyncpg` and Alembic migrations. **Verify in the repo.**
- Showcase repo candidates (Dispatch, etc.) are unchecked leads.
- Route prefix location (`app/api/routes/api.py`) is from memory; confirm.
- Bob promo/redemption specifics weren't confirmed from docs; the user says setup is complete.

**User's working style:**
- Types fast with typos; intent is usually clear.
- Got overwhelmed once by too much planning at once ("im lost, what exactly are we doing"). Keep steps small, concrete, and in order; give one next action at a time; explain in plain language before detail.
- On Windows/PowerShell: use `E:` to switch drives; avoid `>` redirects for JSON (UTF-16); use `python` or `py`.
- Asks for pressure-testing and honest assessment; appreciates being told when a plan has holes.
- Prefers working code and runnable commands over abstract advice.


---

## 13. v1 scope (LOCKED Oct 4)

### 13.1 Scope statement
- **Works on:** pure-Python repositories (Python 3.9+ syntax), analyzed statically, with first-class FastAPI support.
- **Degrades gracefully on:** other Python code (Flask, Django, libraries, scripts): structure, summaries, diagrams, drift detection, but no routes or dependency trees.
- **Does not handle:** Python 2, notebooks, non-Python languages, multi-repo systems, runtime-only behavior (reported as unresolved).
- **Design:** generic core + framework adapters; no repo-specific names in code; repo-specific settings live in `docgen.toml`.

### 13.2 Framework decision and why
Survey data (JetBrains/PSF 2024 survey published 2025): FastAPI 38%, Django 35%, Flask 34%. Stack Overflow 2025 (all developers): FastAPI 14.8%, Flask 14.4%, Django 12.6%. Sources disagree on exact numbers. Caveat (inference, not data): undocumented enterprise code probably skews older, i.e. more Django/Flask. So: dev repo stays FastAPI RealWorld (best ground truth via `app.openapi()`); showcase repo is non-FastAPI to prove generality. LangChain/LangGraph rejected as a target: they are libraries not an app structure, the repo is huge and likely memorized, and graphs are built dynamically at runtime. A Django adapter is out of v1 (routing too involved); a Flask adapter is a stretch goal.

### 13.3 Nodes
Core: package, module, class (fields, bases, pydantic tag), function (incl. async/methods), external (leaf), unresolved. FastAPI adapter: route, router. Tier 2: sql_query.

### 13.4 Edges
Core: contains, imports, inherits, calls (raw text), raises. FastAPI adapter: handles, includes (router prefix), depends_on (via parameter or decorator; factory args recorded), request_model / response_model. Tier 2: runs_query.

### 13.5 Gap decisions

| Gap | v1 decision | Extent |
|---|---|---|
| G1 full route paths | In (adapter) | Via running app; fallback to relative paths + unresolved notice |
| G2 dependency injection | In (adapter) | Recursive tree via name resolution; factories recorded with args, not interpreted |
| G3 call graph | Out | Raw call names only; annotation-based matching is Tier 2 |
| G4 dynamic behavior | Detect and report | Listed as unresolved, never guessed |
| G5 name resolution | In (core) | Absolute/relative imports, aliases, `__init__` re-exports; star imports flagged |
| G6 class fields/inheritance | In (core, basic) | In-repo bases only |
| G7 ERD / G10 SQL | Tier 2 / decide after inspecting repo | aiosql query linking is cheap; ERD only if schema source is parseable |
| G8 function bodies | In (core) | `raises` and raw `calls` |
| G9, G11, G12, G13 | Later / never | |
| G14-G17 | In (core) | Safe import fallback, syntax/version handling, ID+line citations, fact-level hashing |

### 13.6 Understanding-the-repo status
User is new to Python beyond DSA. Concepts explained so far: module, package, import, dependency (package vs injection), decorator, router, route, model/schema, AST node types (FunctionDef, Return, BinOp), fields vs nodes. User asked Bob to explain the repo and received a request trace for POST /api/articles (middleware, routing, auth dependency, DB dependency, body parsing, handler, repository transaction, response). Next: user writes a half-page in their own words (what the app does; request path for create article; purpose of each `app/` folder).

---

## 14. Agent context files (in `project-files/`)

| File | Purpose | Where it goes |
|---|---|---|
| `.bob/rules/rules.md` | Short, strict rules; Bob reads every `.md` in `.bob/rules/` on every interaction, so keep it small | `<project>/.bob/rules/` |
| `docs/PRD.md` | What/why/who, scope, features, success criteria, risks | `<project>/docs/` |
| `docs/architecture.md` | Pipeline, folder layout, config, fact-graph schema, hashes, summarizer interface, error policy | `<project>/docs/` |
| `docs/tasks.md` | One-task-at-a-time breakdown with acceptance criteria and a prompt template | `<project>/docs/` |
| `docs/memory.md` | Decisions, bugs and fixes, open questions, unverified claims, session log (pre-populated) | `<project>/docs/` |
| `docs/project_roadmap.md` | Calendar from Oct 4, gates, time-pressure rules | `<project>/docs/` |
| `BOB_LOG.md` | Skeleton with entry template and first entry (the request-trace session); Bob appends after each task | `<project>/` (root) |

Bob's `/init` also creates `AGENTS.md` files per mode; run it first and keep these files alongside. Bob supports workspace rules (`.bob/rules/`) that override global ones and an optional `AGENTS.md` in the workspace root.


---

## 15. Relationship to OpenAPI, and the circular-test fix (added Oct 4)

**Why build an extractor if FastAPI generates OpenAPI?** OpenAPI documents the outside of the API (URLs, methods, request/response shapes, status codes) for people who call it. docgen documents the inside for maintainers: the file and function behind each endpoint, the dependency chain (including decorator-level permission checks, which typically don't show in OpenAPI), what the handler does (raises, calls into services/repositories), and all code that isn't an endpoint (most folders in `app/`). OpenAPI also exists only for FastAPI apps that can be imported and run. So the endpoint map is an **enrichment**, not a headline feature.

**Circular-test flaw found and fixed:** the plan had the FastAPI adapter read routes from the running app while grading against `app.openapi()` from the same app, which would pass automatically. Fix: add an independent `ast`-only route extractor (task 2a.8b: decorators + `include_router` prefix resolution through imports) and grade *that* against the OpenAPI key. The introspection adapter is only checked for consistency. Also cross-check the route count by hand once. Files updated: `PRD.md` (section 4.1, F6, F9, F11, success criteria), `tasks.md` (1.2, 2a.8a/2a.8b, 2a.10), `architecture.md` (key choices, new section 11), `memory.md` (D-012, D-013).

**Why Phases 0 and 1 exist before extraction (for orientation):** Phase 0 sets up what every later gate depends on: a repo (required for submission), a test environment (every gate is a passing test), Bob rules and `BOB_LOG.md` (Bob usage is 30% of the score and needs evidence from day one), and the Bob Shell scripted-mode check (decides how Phase 2b works). Phase 1 gives understanding of the target (needed to judge extractor output, and Theme 1 step one), the ground-truth answer key, the seeded bug (must exist before the first docs are generated so the later fix shows docs going stale), and the database-approach check (decides whether an ERD is feasible). Both phases can be compressed under the 14-day deadline.


**Update (Oct 4, late):** task IDs now use the phase label (`0.x`, `1.x`, `2a.x`, `2b.x`, `3.x`, `3e.x`, `4.x`, `5.x`; the old "Phase 3.5" is `3e`). `rules.md` now requires the agent to stop and wait for approval after presenting its plan. The calendar starts Oct 5 (13 days left) and is in `docs/project_roadmap.md`. Broad exploration (task 1.1) is reduced to logging the existing request-trace session.
