# Plan: Task 2a.8b — FastAPI Route Extraction via AST Only

## Goal

Build a pure-AST FastAPI route extractor that finds every route decorator in the target repo
and emits ROUTE nodes graded against `eval/ground_truth.json`.

No subprocess. No import. No runtime introspection.

The task description explicitly permits a two-tier deliverable:
- **Tier A (required):** method + handler + *relative* path (the path string on the decorator itself, e.g. `""`, `"/{slug}"`, `"/login"`)
- **Tier B (stretch):** full path (e.g. `/api/articles/{slug}`) by resolving the `include_router` prefix chain

The plan keeps these tiers cleanly separated so you can approve only Tier A, only both, or stop after grading Tier A.

---

## Complexity comparison: Tier A vs Tier B

### Tier A — relative path only

**What needs to happen:**

1. Walk all files already indexed by `walk_repo` + `build_module_index`.
2. For each file, scan `ast` for assignment targets of the form `router = APIRouter()` to identify which names are router objects in that file.
3. Scan for `@<router_name>.<http_method>(path_literal, ...)` decorators on `async def` functions.
   - `<http_method>` ∈ `{get, post, put, delete, patch, head, options}`.
   - `path_literal` is always a string constant in the target repo — direct `ast.Constant` read.
4. Emit one ROUTE node per (method, relative_path, handler_func_name) triple.

**Why it's easy:**
- All of the hard infrastructure (walker, module index, `extract_file`) already exists.
- Router variable names are local to each file; no cross-file resolution needed.
- The decorator path argument is always a literal string in the target (confirmed by reading all route files).
- Handler name = the `def` name immediately below the decorator — already available from `extract_file`.

**Edge cases in the target (all tractable):**
- `@router.get("")` — empty string path → treat as `"/"` or `""` as-is.
- `@router.post(...)` with a multi-line call — `ast` already collapses this; just read `args[0]` or `kwargs["path"]`.
- `dependencies=[Depends(...)]` in decorator kwargs — ignore for this task (that's 2a.9).

**Output accuracy on the target:** 19/19 routes found, method + handler all correct; relative paths only (no `/api` prefix, no `/articles` prefix).

---

### Tier B — full path (additionally required for 100% grade)

**What *additionally* needs to happen:**

Reconstruct the prefix chain by tracing `include_router(router, prefix=...)` calls up the import graph. This is a multi-file, multi-hop traversal:

```
main.py
  application.include_router(api_router, prefix=settings.api_prefix)
       ↑ api_prefix is "/api" — hardcoded in AppSettings default, NOT a literal in main.py
       ↑ requires reading the settings class in app/core/settings/app.py

routes/api.py
  router.include_router(articles.router, tags=["articles"])          ← no prefix
  router.include_router(authentication.router, prefix="/users")
  router.include_router(comments.router, prefix="/articles/{slug}/comments")
  ...

routes/articles/api.py
  router.include_router(articles_resource.router, prefix="/articles")
```

**Full resolution steps:**

1. **Parse `include_router` calls** in every file: record `(router_expr, prefix_expr)` for each call. Router expression is typically a dotted name like `articles.router` or `api_router`.

2. **Resolve the router expression** to a file-level variable via import records — e.g. `articles.router` → `from app.api.routes.articles import api as articles` → `articles.router` in `routes/articles/api.py`.

3. **Build a prefix-chain graph**: each router node knows its own relative decorators AND its accumulated prefix from parent `include_router` calls. This is a DFS/BFS over the graph.

4. **Handle the `settings.api_prefix` case in `main.py`**: the top-level prefix is NOT a literal string — it is `settings.api_prefix` which resolves to `"/api"` only if you read the class default in `app/core/settings/app.py`. Purely literal resolution fails here; a fallback heuristic (look up the class field default) is needed.

5. **Cycle guard**: the router graph is a DAG in practice but the code must guard against cycles.

**Why it's harder:**
- Requires cross-file import resolution of dotted attribute access (`articles.router` is an attribute of the `articles` module alias, not a simple name).
- The top-level prefix (`settings.api_prefix`) is not a literal — it requires following an attribute access into a class definition across two files.
- A router variable can be re-imported under an alias (`from app.api.routes.articles import api as articles`).
- Some `include_router` calls have no `prefix` argument (e.g. `articles.router` in `api.py`) — their prefix is `""`.
- The router graph is two levels deep in the articles sub-package.

**Output accuracy on the target:** 19/19 routes, full paths correct — *if* the `settings.api_prefix` heuristic is implemented. Without it, 19 routes are found but paths are missing the `/api` prefix.

---

## Architecture

The new code lives in a new file: `src/docgen/extract/adapters/fastapi_ast.py`

It does NOT replace `fastapi.py` (the introspection adapter). It is wired into `cli.py` as an additional Step 8b that always runs (alongside or fallback to 8a), and its results are compared to ground truth in tests.

### Data structures

```
RouterDef:
  file: str                    # POSIX path of the file defining this router
  var_name: str                # local variable name ("router", "articles", etc.)
  decorators: list[RouteDecl]  # found on this router in this file
  children: list[ChildInclude] # include_router calls on this router

RouteDecl:
  method: str
  relative_path: str
  handler_name: str
  line: int

ChildInclude:
  child_router_expr: str       # e.g. "articles.router", "authentication.router"
  prefix: str | None           # None if not a literal
```

### Key functions (Tier A)

- `scan_router_defs(file_ast, file_path) -> list[RouterDef]` — find `x = APIRouter()` assignments and collect route decorators from all decorated functions using `x`.
- `extract_ast_routes(file_paths, repo_root) -> list[RouteDecl]` — iterate all files, call `scan_router_defs`, return flat list of `(method, relative_path, handler, file, line)`.

### Additional functions (Tier B only)

- `scan_include_router_calls(file_ast) -> list[ChildInclude]` — find `x.include_router(y, prefix=...)` calls.
- `resolve_router_expr(expr_str, import_records, dotted_to_path) -> str | None` — map `articles.router` → POSIX file path via module index.
- `build_router_graph(all_router_defs, module_index) -> dict[file, RouterDef]` — links parent→child with prefixes.
- `compute_full_paths(router_graph, entry_file, entry_prefix) -> list[RouteDecl with full_path]` — DFS walk.
- `_resolve_attribute_default(attr_expr, all_file_asts) -> str | None` — heuristic: look up class field default value for `settings.api_prefix`-style expressions.

---

## Sub-tasks

### Sub-task 1 — Tier A: relative-path AST scanner [ ] pending

**Intent:** Scan all route files and emit (method, relative_path, handler_name) triples using only AST.

**Expected outcomes:**
- New file `src/docgen/extract/adapters/fastapi_ast.py` with `scan_router_defs` and `extract_ast_routes`.
- `extract_ast_routes` returns 19 entries for the target repo.
- 100% method + handler match against `eval/ground_truth.json`.
- Relative path for each route is the literal string from the decorator.

**Relevant context:**
- Route files: `target/app/api/routes/*.py` and `target/app/api/routes/articles/*.py`
- All router objects in target: declared as `router = APIRouter()` at module level.
- All decorator path args are string literals (no variables).
- Existing pattern to follow: `extract_file` in `src/docgen/extract/core.py` for AST traversal style.
- `HTTP_METHODS` constant already defined in `core.py` — import or copy.

**Tests to add** (in `tests/test_fastapi_ast.py`):
1. Fixture: minimal router file with two decorated functions → correct RouteDecl list.
2. Fixture: empty-string path `@router.get("")` → relative_path is `""`.
3. Fixture: multi-line decorator → method/path still extracted.
4. Fixture: non-router decorator (`@pytest.fixture`) → not included.
5. Integration: run on real target → 19 entries, all methods/handlers match ground truth.

---

### Sub-task 2 — Tier B: `include_router` prefix resolution [ ] pending

**Intent:** Walk the `include_router` call graph to compute full paths from router leaf files up to `main.py`.

**Expected outcomes:**
- Each `RouteDecl` gains a `full_path` field.
- Full-path accuracy vs ground truth reported as a % (19/19 = 100% is the target).
- `settings.api_prefix` resolved to `"/api"` via class-field heuristic.
- Unresolved entries emitted when a prefix can't be determined (e.g. dynamic prefix variable).

**Relevant context:**
- `include_router` wiring: `target/app/main.py`, `target/app/api/routes/api.py`, `target/app/api/routes/articles/api.py`.
- Top-level prefix source: `app/core/settings/app.py` line 27 (`api_prefix: str = "/api"`).
- Import resolution to use: `build_module_index` + `resolve_imports` from `modules.py`.
- Existing cross-file resolution pattern: `extract/classes.py` `resolve_all_classes`.

**Tests to add** (extend `tests/test_fastapi_ast.py`):
1. Fixture: two files — parent calls `include_router(child.router, prefix="/items")`, child has `@router.get("")` → full path `/items`.
2. Fixture: three-level chain (main → api → sub) → full path includes all prefixes concatenated.
3. Fixture: `include_router` with no prefix kwarg → prefix treated as `""`.
4. Fixture: prefix is a non-literal expression → relative path emitted, Unresolved added.
5. Integration: run on real target → 19/19 full paths match ground truth exactly.

---

### Sub-task 3 — Grading + wiring into CLI and eval [ ] pending

**Intent:** Connect the ast extractor to `cli.py` and produce a graded accuracy report.

**Expected outcomes:**
- `cli.py` runs `fastapi_ast.extract_ast_routes` after the module index step (Step 5 or 6).
- A `grade_ast_routes(extracted, ground_truth_path)` function computes recall % and prints linter-style output.
- `docgen extract` prints: `AST routes: 19/19 found (100%)` (or similar).
- No new failures in existing 105-test suite.

**Relevant context:**
- `src/docgen/cli.py` — existing pipeline; introspection adapter wired at Step 7.
- `eval/ground_truth.json` — 19 routes, `"method"` + `"path"` fields.
- Linter output format: already established in `cli.py` (`WARN [type] file:line — why`).

**Tests to add**:
1. `test_grade_ast_routes`: fixture ground truth with 3 routes, extractor finds 2 → recall = 66%.
2. `test_grade_ast_routes_perfect`: all 3 found → 100%, no output to stdout.
3. CLI integration test: `docgen extract` on the real repo includes the AST route line in stdout.

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/extract/adapters/fastapi_ast.py` | **New** — Tier A + Tier B scanner |
| `src/docgen/cli.py` | Add Step 8b call + grading print |
| `tests/test_fastapi_ast.py` | **New** — all tests above |

`src/docgen/extract/adapters/fastapi.py` — **unchanged** (introspection adapter stays).

---

## Open question for you before implementation

**Q:** The task says "If time is short, grade method + handler + relative path only."

Do you want to build **both Tier A and Tier B** now, or **Tier A only** and revisit Tier B before the 2a.10 gate?

The grading requirement for 2a.10 is 100% route recall. Tier A alone achieves 100% recall on method + handler + relative path. Tier B is needed only if the 2a.10 gate requires **full paths** to count as a match.
