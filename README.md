# docgen

> **Cited, drift-aware documentation for Python repositories. Built with IBM Bob**

docgen reads an undocumented Python codebase, extracts a structured fact graph using static analysis, asks IBM Bob to write cited prose summaries on top of those facts, and renders the result as a navigable documentation site. It then watches for drift: when code changes, only the pages whose underlying facts changed are regenerated.

Built for **IBM Hackathon 2026 Theme 1** (IBM Bob-assisted development).

---

## The problem

Enterprise Python repos are commonly undocumented, or documented in ways that have rotted. New developers spend days reading code to understand a single request flow. Existing "AI explains your codebase" tools have two failure modes:

1. **Trust**: summaries may hallucinate. Nothing ties a claim to code.
2. **Staleness**: a one-shot generator is out of date within weeks.

docgen addresses both. Every factual statement in the output cites a fact ID that exists in the extracted graph. And because facts are hashed at generation time, a `docgen check` run can tell you exactly which pages are stale without re-running anything expensive.

---

## Who it's for

- **A developer joining an unfamiliar service** wants to understand the architecture, find the handler for a route, and trace the dependency chain, without reading 70 files.
- **Anyone who wants docs kept in sync with code** without manual effort. `docgen check` runs in CI; `docgen update` regenerates only what changed.

---

## Demo

The `generated/` directory in this repo contains the full output of running docgen on [`nsidnev/fastapi-realworld-example-app`](https://github.com/nsidnev/fastapi-realworld-example-app) , a real-world FastAPI app with 70 Python files.

| Metric | Value |
|---|---|
| Python files analysed | 70 |
| Fact graph nodes | 320 |
| Fact graph edges | 1,190 |
| Summaries generated (via Bob Shell) | 234 |
| Documentation pages produced | 72 |
| Route recall — AST extractor vs `app.openapi()` ground truth | 19 / 19 = 100% |
| `DEPENDS_ON` edges resolved | 66 / 66 = 100% |
| False positives on harmless edits (comment/format) | 0 |
| LLM calls on unchanged re-run | 0 |
| Tests passing | 223 / 223 |

**Run the viewer locally:**

```bash
pip install streamlit streamlit-mermaid
streamlit run viewer/app.py
```

---

> **Where to find things:**
> system design → [`docs/architecture.md`](docs/architecture.md) ·
> requirements → [`docs/PRD.md`](docs/PRD.md) ·
> design decisions and bugs (D-001 to D-043) → [`docs/memory.md`](docs/memory.md) ·
> IBM Bob session log → [`docs/BOB_LOG.md`](docs/BOB_LOG.md)

---

## What it does, and doesn't do (yet)

### ✅ Works in v1

| Feature | Detail |
|---|---|
| Core fact extraction | Packages, modules, classes (fields, bases, Pydantic detection), functions (signature, decorators, docstrings, async), imports, raises, raw calls — all via `ast`, no execution |
| Import resolution | Absolute, relative, aliases, `__init__.py` re-exports; star imports flagged as unresolved |
| FastAPI adapter | Routes via app introspection **+** an independent AST-only extractor (fallback when the app can't be imported; also the graded one); recursive `Depends` tree; request/response models |
| Hierarchical cited summaries | Bottom-up: function → module → package → system. Each level receives its own facts and child summaries, never the whole repo. Cache key = hash of inputs; zero LLM calls on re-run with no changes |
| Citation validation | Every factual claim must cite a `[[fact_id]]` that exists in `facts.json`. Validated mechanically before rendering |
| Drift detection | 	hash_struct (signature/decorator changes) vs hash_source (body/comment changes). Only hash_struct changing marks a page stale. A comment or reformat change may refresh the summary, but never triggers a re-render |
| Incremental update | `docgen update` re-renders only stale pages; ancestors are skipped unless a summary materially changed |
| Streamlit viewer | Sidebar file tree, Mermaid diagrams (via `streamlit-mermaid`), full-text markdown rendering. Reads `generated/` at runtime, no LLM |

### ❌ Not in v1 (documented gaps, not surprises)

| Gap | Status |
|---|---|
| Full route path resolution from AST | Tier B deferred. Routes are extracted with method + handler at 100% recall; full `/api/articles/{slug}` path requires tracing `include_router` prefix chains across files. The introspection adapter produces full paths; the AST fallback produces relative paths |
| Flask / Django adapters | Core layer works on any Python repo; FastAPI is the only framework adapter implemented |
| aiosql query linking | `.sql` name comments parsed; call→SQL linking deferred |
| ERD | DB schema is in a single Alembic migration file; ERD generation not built |
| Parallel summarization | Bob Shell calls are sequential. Same-level nodes are independent and could be parallelised |
| Eval harness | Route recall measurement done; claim precision spot-check (hand-grade 30 claims) not yet run |
| Git-history context | "Why was this code written this way?" requires `git log -p` integration — not built |

---

## Architecture

This is the overview. The full design (pipeline, fact-graph schema, hashing, error policy) is in [`docs/architecture.md`](docs/architecture.md).

```text
repo ──► [walker] ──► [core extract] ──► [adapter extract] ──► facts.json
                                                                   │
summaries.json ◄── [Bob Shell] ◄───────────────────────────────────┤
       │                                                           │
       ▼                                                           ▼
[citation validate]                                            [render] ──► generated/pages/
                                                                   │
manifest.json ◄────────────────────────────────────────────────────┘
       │
[check] / [update]  ──► only stale pages regenerate
       │
[viewer]  (reads generated/, no LLM)
```

**The core principle:** facts are computed deterministically. IBM Bob only writes prose on top of those facts — it never invents structure. Routes, imports, models, dependency trees, and diagrams all come from code analysis. This is what makes the citations mechanically verifiable.

### Stage table

| Stage | Input | Output | LLM? |
|---|---|---|---|
| walker | config + repo root | file paths (root-relative POSIX) | no |
| core extract | `.py` files | nodes, edges, unresolved entries | no |
| adapter extract | facts + running app | routes, dependency edges, models | no |
| summarize | facts | `summaries.json` with `[[fact_id]]` citations | **yes — IBM Bob** |
| validate | summaries + facts | validation report (exits 1 on broken citations) | no |
| render | facts + summaries | `.md` pages, Mermaid diagram, API table | no |
| check | current facts + manifest | pass / fail + stale page list | no |
| update | stale list + facts | regenerated pages | yes (stale nodes only) |

### Fact graph

Every node has `id`, `type`, `file`, `lines`, `hash_struct`, `hash_source`.

**Node types:** `package`, `module`, `class`, `function`, `external`, `unresolved`, `route`, `router`

**Edge types:** `contains`, `imports`, `inherits`, `calls`, `raises`, `handles`, `depends_on`, `request_model`, `response_model`

**ID scheme:** `path/to/file.py` for modules; `path/to/file.py::Class::method` for members. All paths are repo-root-relative with forward slashes.

**Two hashes per node:**

- `hash_struct` — structural fields only (signature, decorators, bases, fields). No line numbers, no comments. A change here marks dependent pages stale.
- `hash_source` — token hash of the source text the summarizer sees (comments kept, blank lines stripped). A change here marks that node's existing summary stale.

This separation is why harmless edits (add a comment, reformat) never trigger a re-render.

### Source layout

```text
src/docgen/
├── cli.py                  # argparse entry point
├── config.py               # loads docgen.toml
├── walker.py               # file discovery, exclude list, POSIX IDs
├── facts/
│   ├── schema.py           # Node, Edge, Unresolved, FactGraph dataclasses
│   └── store.py            # deterministic JSON read/write
├── extract/
│   ├── core.py             # per-file AST extraction
│   ├── modules.py          # import resolution, dotted-name index
│   ├── classes.py          # base resolution, field flattening
│   ├── bodies.py           # raises, calls
│   ├── packages.py         # synthesise PACKAGE nodes from directory structure
│   └── adapters/
│       ├── fastapi.py      # introspection adapter (subprocess, timeout)
│       ├── fastapi_ast.py  # AST-only route extractor (graded)
│       └── resolve_deps.py # DEPENDS_ON edge resolution
├── summarize/
│   ├── base.py             # Summarizer protocol, StubSummarizer
│   ├── hierarchy.py        # bottom-up driver + cache
│   ├── prompts.py          # prompt templates, citation format
│   ├── citations.py        # citation validator
│   ├── bob_shell.py        # BobShellSummarizer (calls bob run --format json)
│   └── manual.py           # reads summaries written by hand
├── render/
│   ├── markdown.py         # index page, module pages, render_all
│   ├── mermaid.py          # package→package flowchart
│   └── api_table.py        # enriched endpoint table
└── check/
    ├── manifest.py         # PageRecord, build/write/read manifest
    ├── drift.py            # find_stale_pages, warn_if_facts_stale
    └── update.py           # UpdatePlan, plan_update
```

---

## Setup

**Requirements:** Python 3.11+

```bash
git clone https://github.com/vidi-deshp12/doc_tool
cd doc_tool

python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

The viewer needs two extra packages (not declared as package deps — viewer only):

```bash
pip install streamlit streamlit-mermaid
```

### Run the tests

```bash
pytest
```

223 tests, ~25 seconds. No LLM calls, no network, no target repo needed.

---

## Configuration

Create a `docgen.toml` in your project root:

```toml
[repo]
root = "target"          # directory containing the repo to analyse
source_root = "target"   # where top-level Python packages live (use "target/src" for src layouts)
exclude = [".git", ".venv", "__pycache__", "tests", "migrations"]

[adapter]
name = "fastapi"         # "fastapi" or "none"
app = "app.main:app"     # import path of the ASGI app object (fastapi adapter only)

[output]
dir = "generated"        # where facts.json, summaries.json, manifest.json, and pages/ are written
```

Nothing repo-specific ever goes in the code — only in this file.

---

## Usage

Run these commands in order for a fresh repo:

```bash
# 1. Extract the fact graph
docgen extract

# 2. Generate cited summaries (requires IBM Bob CLI)
docgen summarize --backend bob_shell

# 3. (Optional) validate citations before rendering
docgen validate

# 4. Render documentation pages + manifest
docgen render

# 5. Check for drift after a code change
docgen check              # fast path: reads facts.json as-is
docgen check --fresh      # re-extracts first, then checks

# 6. Regenerate only stale pages
docgen update

# 7. View the docs
streamlit run viewer/app.py
```

For testing without IBM Bob, use the stub summarizer (produces placeholder text, real citations):

```bash
docgen summarize --backend stub
```

---

## IBM Bob integration

IBM Bob was central to this project in two ways:

1. **As the development partner** — every implementation file was written by Bob in Plan → Agent mode. Design decisions, bugs found, and fixes are logged in `docs/memory.md` (D-001 through D-043) and `docs/BOB_LOG.md` (18+ session entries covering planning, coding, review, and debugging).

2. **As the summarizer backend** — `BobShellSummarizer` calls `bob run --format json --max-cost 0.1` once per node to generate the 234 summaries in `generated/summaries.json`. The `bob run` non-interactive mode was confirmed working at ~0.009 Bobcoins per call. Prompts are built deterministically from the fact graph; Bob writes the prose; the citation validator checks the output before rendering.

The `Summarizer` interface is pluggable — the pipeline works identically with `stub`, `manual`, or `bob_shell` backends.

---

## Project docs

| File | Contents |
|---|---|
| `docs/PRD.md` | Requirements, goals, success criteria, non-goals |
| `docs/architecture.md` | Full design: pipeline, fact graph schema, hashing, error policy |
| `docs/tasks.md` | Task checklist (phases 0–5) |
| `docs/memory.md` | All decisions (D-001–D-043), bugs found and fixed |
| `docs/BOB_LOG.md` | Bob session log — prompts, outputs, what was verified |
| `eval/ground_truth.json` | 19 routes, 25 schemas from `app.openapi()` — the answer key |
| `generated/facts.json` | 320 nodes, 1,190 edges extracted from the demo repo |
| `generated/summaries.json` | 234 summaries generated by IBM Bob |
| `generated/pages/` | 72 rendered documentation pages |

---

## Known limitations

docgen records what it cannot resolve instead of guessing. The limits below are
design choices or time-boxed gaps.

### What the fact graph cannot see

| Limitation | What it means in practice |
|---|---|
| **No call graph** | `calls` edges store raw call text (e.g. `articles_repo.create_article(...)`). They are not linked to the function being called, because static analysis cannot tell what type `articles_repo` is. There are no "who calls X" queries or impact analysis. Summaries still describe calls (Bob reads the source), but those descriptions are not backed by graph edges. |
| **Dependency factories are not followed** | `Depends(get_repository(ArticlesRepository))` and `Depends(get_current_user_authorizer())` are recorded with their arguments, but the tool does not follow what the factory returns. The dependency tree stops at the factory (endpoint → `get_current_user_authorizer`, not on to `_get_current_user` and JWT decoding). The later steps appear in prose summaries, not as edges. |
| **Dynamic behavior** | Star imports, `__import__`/`importlib` calls, and `getattr` with computed names are detected and listed under `unresolved`. Other dynamic patterns (decorators wrapping decorators, metaclasses, monkeypatching) are not detected. |
| **Nested and conditional definitions** | Only module-level functions, classes, and their methods become nodes. Nested functions, lambdas, and `if TYPE_CHECKING` blocks do not. |
| **App wiring** | Middleware, exception handlers, startup/shutdown events, and settings/environment variables are not modelled as facts. Summaries may mention them (from source), but they are not graph-backed. |
| **Database layer** | `.sql` files (aiosql) and migrations are not parsed. Repository calls to `queries.*` are not linked to SQL, and there is no ERD. |
| **Route paths** | Full URLs (`/api/articles/{slug}`) come from importing the running app. This needs the target's dependencies installed and its environment variables set, and it executes the target's code, so run it only on repositories you trust (in a virtualenv or container). The AST-only fallback finds methods and handlers with relative paths. |
| **Scope** | Python 3.9+ syntax, one repository at a time, FastAPI is the only framework adapter. On other frameworks you get structure, summaries, diagrams and drift detection, but no routes or dependency trees. Tested end-to-end on one repository (RealWorld). |

### Trust, drift, and process

| Limitation | What it means in practice |
|---|---|
| **Citations prove existence, not truth** | The validator checks that every cited ID is a real node. It does not check that the sentence is correct. A hand-graded claim-precision sample (30 claims) has not been run yet. Transitional sentences may be uncited. |
| **Prose lags behind structure** | `docgen check` detects structural drift and `docgen update` re-renders the affected pages, so tables (route table, signatures) are correct immediately. A summary's narrative may still describe the old behavior (e.g. a changed status code) until `docgen summarize` runs again. |
| **Some `unresolved` entries are noise** | A few base classes from builtins, the standard library, or same-file aliases (`Exception`, `logging.Handler`, `CommonParameter` → `pypika.Parameter`) appear under `unresolved` although they could be resolved. They are harmless. |
| **Speed and platform** | Bob Shell is called once per node, sequentially (234 calls). Nodes at the same level are independent, so parallelization is the obvious next step. Developed and tested on Windows, where the Bob Shell backend pipes prompts through PowerShell. |
