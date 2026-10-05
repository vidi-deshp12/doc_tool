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

## 2. Bugs found and fixed

| ID | Date | Bug | Fix |
|---|---|---|---|
| B-001 | Oct 4 | In spike: function line span and hash started at `def`, excluding decorators, so a route path/status change would not change the hash | Span starts at first decorator; hash covers it; `def_line` kept separately. Verified by editing a decorator |
| B-002 | Oct 4 | In spike: `Depends(...)` inside decorator kwargs (`dependencies=[Depends(...)]`) missing from `depends_on`; these are the authorization checks | New `decorator_depends` field (becomes `depends_on` edge with `via=decorator`) |
| B-003 | Oct 4 | PowerShell `>` wrote JSON as UTF-16; file looked blank | Script writes UTF-8 itself via an output argument. Rule: never redirect JSON with `>` on Windows |
| B-004 | Oct 4 | Duplicate route data (`routes` field repeated `decorators[].route`) | Removed `routes` |
| B-005 | Oct 4 | Spike IDs started with `target/` depending on run location | Added `--root`; IDs relative to root, POSIX slashes |

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
