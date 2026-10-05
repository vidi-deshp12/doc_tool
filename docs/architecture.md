# Architecture

## 1. Principle
**Everything factual is computed deterministically. The LLM only writes prose on top of those facts.** Structure (routes, imports, models, diagrams, dependency trees) comes from code analysis. The LLM explains; it never invents structure.

Two layers:
- **Core layer:** works on any Python repo.
- **Adapter layer:** adds framework knowledge (v1: FastAPI; stretch: Flask). Adapters are optional; without one the tool degrades, it doesn't break.

## 2. Pipeline

```
repo ──► [walker] ──► [core extract] ──► [adapter extract] ──► facts.json
                                                                  │
                         summaries.json ◄── [summarize] ◄─────────┤
                              │                                   │
                              ▼                                   ▼
                       [citation validate]                  [render] ──► docs/
                                                                  │
                          manifest.json ◄─────────────────────────┘
                                │
                     [check] / [update]  ──► (only stale pages regenerate)
                                │
                           [viewer] (reads docs/, no LLM)
```

| Stage | Input | Output | LLM? |
|---|---|---|---|
| walker | config + repo root | list of file paths (root-relative, POSIX) | no |
| core extract | files | nodes/edges (packages, modules, classes, functions, imports, inherits, raises, calls) + unresolved | no |
| adapter extract | facts + running app | routes, routers, dependency edges, request/response models | no |
| summarize | facts | `summaries.json` (cited prose per node) | **yes** |
| validate | summaries + facts | validation report | no (entailment spot-check may use LLM) |
| render | facts + summaries | `docs/*.md`, Mermaid, API table | no |
| check | repo + manifest | pass/fail + stale page list | no |
| update | stale list | regenerated pages | yes (only for stale parts) |

## 3. Repository layout

```
project-root/
├── .bob/rules/rules.md          # short; auto-loaded by Bob every interaction
├── docs/                        # project docs for the agent (this folder) -- NOT generated output
│   ├── PRD.md  architecture.md  tasks.md  memory.md  project_roadmap.md
├── generated/                   # tool OUTPUT (committed): facts.json, summaries.json, manifest.json, pages/
├── src/docgen/
│   ├── cli.py                   # argparse entry: extract | summarize | render | check | update | eval
│   ├── config.py                # loads docgen.toml
│   ├── walker.py                # find .py files, apply excludes, make IDs
│   ├── facts/
│   │   ├── schema.py            # dataclasses for Node, Edge, Unresolved, FactGraph
│   │   └── store.py             # stable JSON read/write (sorted keys, no timestamps)
│   ├── extract/
│   │   ├── core.py              # per-file ast extraction (ported from spike)
│   │   ├── modules.py           # dotted-name <-> path index, import resolution
│   │   ├── classes.py           # fields, inheritance flattening (in-repo bases only)
│   │   ├── bodies.py            # raises, calls
│   │   └── adapters/
│   │       ├── base.py          # Adapter protocol
│   │       ├── fastapi.py       # routes (introspection), Depends tree, models
│   │       └── flask.py         # STRETCH
│   ├── summarize/
│   │   ├── base.py              # Summarizer protocol
│   │   ├── hierarchy.py         # bottom-up driver, cache
│   │   ├── prompts.py           # prompt templates, citation format
│   │   ├── citations.py         # validator + entailment spot-check
│   │   ├── bob_shell.py         # CONDITIONAL on Bob Shell scripted mode
│   │   └── manual.py            # reads summaries Bob wrote in the IDE
│   ├── render/                  # markdown.py, mermaid.py, api_table.py
│   └── check/                   # manifest.py, drift.py, update.py
├── viewer/app.py                # Streamlit, reads generated/
├── eval/                        # ground-truth comparison, claim sampling sheet
├── tests/
├── target/                      # cloned repo under analysis (gitignored)
├── docgen.toml                  # config for a run
├── BOB_LOG.md  README.md  pyproject.toml
```

## 4. Config (`docgen.toml`)

```toml
[repo]
root = "target"            # repo being analysed
source_root = "target"     # folder containing top-level packages (e.g. "target/src" for src layouts)
exclude = [".git", ".venv", "venv", "node_modules", "__pycache__", "tests", "migrations"]

[adapter]
name = "fastapi"           # or "none"
app = "app.main:app"       # import path of the app object (adapter-specific)

[output]
dir = "generated"
```
Anything repo-specific lives here, never in code.

## 5. Fact graph

**Nodes** (all have `id`, `type`, `file`, `lines`, `hash_struct`, `hash_source`):

| Layer | Type | Key fields |
|---|---|---|
| core | `package` | path |
| core | `module` | dotted name, docstring |
| core | `class` | bases, fields (name, annotation, default), `is_pydantic_model`, decorators |
| core | `function` | signature, returns, decorators, docstring, async flag, parent class |
| core | `external` | library name (leaf; never analysed) |
| core | `unresolved` | what, why, where |
| fastapi | `route` | method, full path, name, status code |
| fastapi | `router` | variable, prefix |
| tier 2 | `sql_query` | name, file |

**Edges** (`type`, `from`, `to`, optional `meta`):

| Layer | Type | Meaning |
|---|---|---|
| core | `contains` | package→module, module→class/function, class→method |
| core | `imports` | module→module or module→external |
| core | `inherits` | class→base class |
| core | `calls` | function→raw call text (mostly unresolved) |
| core | `raises` | function→exception type, meta: args |
| fastapi | `handles` | route→function |
| fastapi | `includes` | router→router, meta: prefix |
| fastapi | `depends_on` | function→dependency function; meta: `via` = parameter/decorator, factory args |
| fastapi | `request_model` / `response_model` | route→class |
| tier 2 | `runs_query` | function→sql_query |

**ID scheme:** `path/to/file.py` for modules; `path/to/file.py::Class::method` for members; `route:METHOD /full/path` for routes. Paths are **relative to repo root, POSIX slashes**, always.

**Two hashes per node:**
- `hash_struct`: structural fields only (signature, decorators incl. route args, bases, fields, imports, depends). **Excludes line numbers and comments.** Change here → dependent doc pages are stale.
- `hash_source`: source text from first decorator to end of body. Change here → that node's own summary is stale.

## 6. Key technical choices

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ (target code parsed as 3.9+ syntax) | `ast.unparse` needs 3.9+ |
| Static analysis | stdlib `ast` | exact, safe, no execution |
| Routes | primary: import the app in a subprocess, read `app.routes`; independent fallback: `ast`-only decorator + `include_router` resolution | Introspection gives exact URLs but needs a runnable app; the `ast` path works without running code and is the one we grade (see §11) |
| Data model | `dataclasses` + stable JSON | no extra deps |
| CLI | `argparse` | no extra deps |
| Tests | `pytest` | |
| Viewer | Streamlit; Mermaid via `components.html` with the Mermaid JS (verify before choosing a package) | |
| Deploy | Streamlit Community Cloud from public repo | viewer needs no LLM or target code |

## 7. Summarizer interface (decouples the open Bob question)

```python
class Summarizer(Protocol):
    def summarize(self, req: SummaryRequest) -> SummaryResult: ...
# SummaryRequest: node_id, level, facts (dict), source_text, child_summaries
# SummaryResult:  text (with [[fact_id]] citations), model/backend name
```
Implementations: `StubSummarizer` (tests), `ManualSummarizer` (reads files Bob wrote in the IDE, validates them), `BobShellSummarizer` (only if Bob Shell supports non-interactive use). The pipeline, validator, and checker don't care which one is used.

**Citation format:** inline `[[<fact_id>]]` after each claim. Validator checks (1) ID exists in `facts.json`, (2) every sentence has ≥1 citation, (3) spot-check that the cited fact/snippet supports the sentence.

**Hierarchy:** function → module → package → system. Each level receives only its own facts and child summaries, never the whole repo. Cache key = hash of inputs. **Early cutoff:** if a regenerated summary is materially unchanged, don't propagate to ancestors.

## 8. Freshness

`generated/manifest.json` maps each doc page → list of fact IDs and their `hash_struct` at generation time (+ `hash_source` for pages that quote bodies).
- `docgen check`: re-extract, compare hashes, exit non-zero if any page is stale, list pages.
- `docgen update`: regenerate only stale pages (plus ancestors only when a summary materially changed).
- CI behaviour: default is *report*; hard-fail is an option.

## 9. Error handling policy
- Per-file failures (`SyntaxError`, decoding) never stop a run: record as `unresolved` (type `unparsed_file`) and continue.
- Anything unresolvable (dynamic import, star import, unknown decorator wrapper, name not found) → `unresolved` entry. **Never guess.**
- Adapter import failure → fall back to `ast`-only output and add a prominent notice to the generated docs.
- Importing the target executes its code: run in a subprocess with a timeout and dummy env vars.
- LLM failures: retry with backoff, then mark the page `needs_human_review` and continue.

## 10. Determinism requirements
Sorted JSON keys, sorted lists where order isn't meaningful, no timestamps or absolute paths in `facts.json`. Same repo state ⇒ byte-identical `facts.json`.

## 11. Validating route extraction (avoid circular tests)
- `app.openapi()` is the **answer key** (`eval/ground_truth.json`). It is produced by running the app.
- The introspection adapter reads the same running app, so comparing it to the key proves nothing; treat that comparison as a consistency check only.
- The **`ast`-only route extractor** is independent of the key (it reads source text and resolves routers through imports). It is graded against the key: route recall, handler correctness, relative-path correctness, and full-path accuracy (reported separately).
- Also cross-check route counts by hand once (text search for route decorators), so the key itself is not trusted blindly.
- This matters beyond FastAPI: the `ast` path is the template for non-runnable repos and for future adapters.
