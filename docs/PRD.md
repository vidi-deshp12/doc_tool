# Product Requirements Document

Working name: **docgen** (rename freely).

## 1. One-line summary
A tool that reads an undocumented Python repository and produces **trustworthy, cited documentation that stays current**: architecture overview, module pages, API endpoint table, dependency diagram. It detects when docs have drifted from the code and updates only the pages that need it.

## 2. Problem
- Enterprise Python repos are commonly undocumented or documented in ways that have rotted. New developers spend days reading code to learn how a request flows.
- "AI explains your repo" tools exist, but two things stop teams from relying on them:
  1. **Trust:** summaries may hallucinate, and nothing ties a claim to code.
  2. **Staleness:** a one-shot generator is out of date within weeks.
- Large repos don't fit in a model's context window.

## 3. Who it's for
- **Primary user:** a developer new to an unfamiliar Python codebase (onboarding, inheriting a service, auditing before a change).
- **Secondary user:** a tech lead who wants docs kept in sync with code without manual effort.

## 4. What kinds of repositories (scope statement)
- **Works on:** pure-Python repositories (Python 3.9+ syntax), analyzed statically, with first-class support for **FastAPI** apps.
- **Degrades gracefully on:** other Python code (Flask, Django, libraries, scripts). The user still gets packages, modules, classes, functions, imports, inheritance, raises/calls, summaries, diagrams and drift detection. Routes and dependency trees are not produced unless an adapter exists.
- **Does not handle:** Python 2, notebooks, non-Python languages, multi-repo systems, anything decided at runtime. These are reported as *unresolved*, never guessed.
- **Design rule:** generic core + framework adapters. No repo-specific names in code.

### 4.1 Relationship to FastAPI's built-in OpenAPI
FastAPI already generates an OpenAPI spec, which documents the **outside** of an app for people who call it: URLs, methods, request/response shapes, status codes. docgen documents the **inside**, for developers who maintain it: which file and function handle each endpoint, the dependency chain (auth, permissions, DB access), what the handler does (exceptions raised, services/repositories called), and everything that is not an endpoint (services, repositories, models, core config, how files import each other). Most folders in a typical app contain no endpoints at all. OpenAPI also exists only for FastAPI apps that can be imported and run.
- The **endpoint map is an enrichment, not a headline feature.** For endpoints we reuse the framework's own data where possible and add links to code, dependencies, and citations.
- `app.openapi()` is used as an **independent answer key** to grade our `ast`-based route extractor (see `architecture.md` §11).

## 5. Goals
1. Every factual statement in the docs is **grounded**: it cites a fact ID that exists in the extracted fact graph.
2. Docs **stay fresh**: a check command detects stale pages; an update command regenerates only affected pages.
3. **Scales**: hierarchical summarization, so repo size is not limited by context window.
4. **Measured**: accuracy numbers reported from an eval harness, not just a demo.
5. Built **with IBM Bob** as a core part of the workflow (hackathon criterion), with evidence logged.

## 6. Non-goals
Security audit, tech-debt scoring, Postman export, multi-language support, Jira/Confluence ingestion, a complete call graph, explaining *why* decisions were made (code can't say; stretch: git history).

## 7. Core features (v1)

### Must have
| ID | Feature | Notes |
|---|---|---|
| F1 | Repo walker + config | One root path; exclude list; root-relative POSIX IDs |
| F2 | Core fact extraction (`ast`) | Packages, modules, classes (fields, bases), functions, imports, decorators, docstrings |
| F3 | Import/name resolution | Absolute, relative, aliases, `__init__` re-exports; star imports flagged |
| F4 | Body facts | `raises` (type + args) and raw `calls` per function |
| F5 | Unresolved report | Anything not resolvable is listed with reason and location |
| F6 | FastAPI adapter | Routes via app introspection **plus an independent `ast`-only route extractor** (fallback when the app can't be imported; also the graded one); recursive dependency tree (`Depends`, incl. decorator-level); response/request models |
| F7 | Hierarchical cited summaries | function → module → package → system; claims cite fact IDs |
| F8 | Citation validator | IDs exist; every claim carries a citation; entailment spot-check |
| F9 | Doc renderers | Architecture overview, per-module pages, Mermaid dependency diagram, enriched endpoint map (endpoint → handler → dependency chain → behavior, each cited) |
| F10 | Drift check + incremental update | Fact-level hashing, manifest, early cutoff; `check` exits non-zero on drift |
| F11 | Eval harness | Recall of the **`ast`-only extractor** vs `app.openapi()` (independent key), claim precision (hand-graded sample), drift false-positive rate, incremental savings |

### Should have
Streamlit viewer over committed `docs/` (no LLM at runtime), live demo deployment, aiosql query linking (call → `.sql` query).

### Stretch
Flask adapter, grounded Q&A, onboarding guide, git-history context for the "why", ERD (only if schema source is parseable), call-graph via annotation matching.

## 8. Success criteria
- The `ast`-only extractor finds 100% of routes (method + handler) and models vs the `app.openapi()` ground truth on the dev repo; full-path accuracy reported separately. (The introspection adapter is not graded against OpenAPI, since both read the same source.)
- Claim precision ≥ 90% on a hand-graded sample of ≥ 30 claims (publish the real number even if lower).
- Drift check: 0 false positives on harmless edits (comment/format changes); correctly flags a real change.
- Re-run with no changes makes **zero** LLM calls.
- Theme 1 story works end to end in one take: docs → locate seeded bug → Bob fixes → only affected pages update → Bob adds a feature using the docs.

## 9. Constraints
- Hackathon deadline **Oct 18, 2026 23:59 ET** (plan to submit Oct 17). About 14 days from Oct 4.
- Submission needs: public GitHub repo with README + test instructions, 100-word description, track (Theme 1), tech stack, improvements made, PDF deck, ≤3-min YouTube demo, live demo URL.
- Judging: Bob usage depth 30%, use-case relevance 30%, execution 30%, presentation 10%.
- Must run on Windows (developer machine) and Linux (deployment).
- Open dependency: whether Bob Shell can run non-interactively (decides how summaries are automated). See `docs/architecture.md` §7.

## 10. Risks
| Risk | Mitigation |
|---|---|
| Bob can't be scripted | Pluggable summarizer; manual-file backend (Bob writes summaries in the IDE, tool validates them) |
| Summaries cite real IDs but say wrong things | Entailment spot-check + hand-graded sample + published precision |
| Route/dependency resolution takes too long | Introspection first; `ast`-only fallback; cut ERD/SQL |
| Drift check is noisy | Hash facts, not files; test with harmless edits |
| Time (14 days) | Strict phase gates; tier-3 items cut without discussion |
| Model memorized the demo repo | Test on non-famous repo and renamed-identifier copy |
