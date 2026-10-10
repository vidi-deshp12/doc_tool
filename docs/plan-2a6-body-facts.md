# Plan: Task 2a.6 — Body Facts (`extract/bodies.py`)

## Top-Level Overview

**Goal:** Implement `src/docgen/extract/bodies.py` so that after extraction the fact graph has:
1. **`RAISES` edges** — one per `raise` statement in each module-level function body, pointing from the function node to the resolved exception type (`external:<dotted>` or in-repo node ID), with `meta` carrying the constructor args as raw unparsed text.
2. **`CALLS` edges** — one per unique callable name found anywhere in each module-level function body (via `ast.walk`), pointing from the function node to `ast.unparse(call_node.func)` as `to_id` (e.g. `"articles_repo.filter_articles"`), with `meta=(("call_text", ast.unparse(call_node)),)` carrying the full call text. No node is created for call targets.

**Scope:** One new file (`extract/bodies.py`), new test file. No changes to `core.py`, `classes.py`, or `schema.py`.

**Non-goals:** Resolving call targets to node IDs, extracting body facts from class methods (core.py doesn't extract them yet), handling exec/eval/getattr dynamics.

---

## Design Decisions (confirmed)

- **`CALLS` to_id:** `ast.unparse(call_node.func)` — the callable name only, e.g. `"articles_repo.filter_articles"`. No resolution, no external Node.
- **`CALLS` meta:** `(("call_text", ast.unparse(call_node)),)` — full call text including args, for the summarizer to quote.
- **`CALLS` deduplication:** one edge per unique `to_id` per function (same callable called twice → one edge, last call_text wins).
- **`RAISES` to_id:** resolved via the file's import records exactly like `classes.py` resolves base names. Result is `external:<dotted.name>` for external exceptions or an in-repo node ID for custom exceptions defined in the repo. An external Node is emitted once per unique exception type (guarded by a seen-set).
- **`RAISES` meta:** `(("args", "<raw unparsed args string>"),)` where the args string is the unparsed text of all positional and keyword arguments to the exception constructor (e.g. `"status_code=status.HTTP_400_BAD_REQUEST, detail=strings.ARTICLE_ALREADY_EXISTS"`). Empty tuple if the raise is a bare `raise` or raises a variable (non-Call expression).
- **Chained raises** (`raise X from Y`): capture the exception being raised (`X`); ignore the cause (`Y`). Record as a single RAISES edge.
- **Bare `raise`** (re-raise inside except block): skip — no exception type to resolve.
- **`raise <variable>`** (not a Call): emit RAISES edge with `to_id = "external:<name>"` and empty meta. The variable's type is unknowable statically.
- Only processes **module-level functions** (matches what `core.py` currently extracts; class methods are out of scope until core.py is extended).

---

## Sub-Tasks

---

### Sub-task A — Exception type resolution helper

**Intent:** Reuse the same name→import→dotted logic from `classes.py` to resolve a bare exception name like `"HTTPException"` to `"external:fastapi.HTTPException"` or an in-repo node ID.

**Expected Outcomes:**
- A private function `_resolve_exception_type(name, file_path, path_to_info, dotted_to_path, node_map)` returns a resolved ID string or `None` for unknowable cases.
- `HTTPException` imported from `fastapi` → `"external:fastapi.HTTPException"`.
- A custom exception class defined in the same repo → `"<file>::ClassName"`.
- A dotted name like `errors.NotFound` → resolved through the import for `errors`.

**Todo List:**
1. Write `_resolve_exception_type()` that accepts a raw name string (already stripped of any subscript). Reuses the same `name_to_dotted` import-lookup pattern established in `classes.py` (`_resolve_base_name`).
2. Handle dotted names in the raise expression (e.g. `raise errors.NotFound(...)`) by splitting on `.` and resolving the base module name first.
3. Return `None` for truly dynamic / unresolvable cases (e.g. variable raised without a call).

**Relevant Context:**
- [`src/docgen/extract/classes.py`](src/docgen/extract/classes.py) — `_resolve_base_name()` (lines ~40-102) is the exact pattern to adapt.
- [`src/docgen/extract/modules.py`](src/docgen/extract/modules.py) — `ModuleInfo`, `ImportRecord`.

**Status:** `[ ] pending`

---

### Sub-task B — Extract `RAISES` edges from function bodies

**Intent:** Walk each module-level function's AST body, find all `ast.Raise` nodes, resolve the exception type, and emit `RAISES` edges.

**Expected Outcomes:**
- `create_new_article` (articles_resource.py) → `RAISES` edge → `"external:fastapi.HTTPException"` with `meta=(("args", "status_code=status.HTTP_400_BAD_REQUEST, detail=strings.ARTICLE_ALREADY_EXISTS"),)`.
- Bare `raise` (no exc) → skipped, no edge.
- `raise variable` (non-Call) → `RAISES` edge with `to_id="external:<name>"` and empty meta.
- Chained `raise X from Y` → RAISES edge for `X` only, Y ignored.
- One external Node emitted per unique exception `to_id` (seen-set guard).

**Todo List:**
1. Write `_extract_raises(func_node, func_id, file_path, path_to_info, dotted_to_path, node_map, external_seen)` that uses `ast.walk` to find all `ast.Raise` nodes inside a function.
2. For each `ast.Raise`:
   - If `node.exc` is None (bare `raise`) → skip.
   - If `node.exc` is `ast.Call` → extract the callable name via `ast.unparse(node.exc.func)`, resolve it, build meta from `ast.unparse` of all args and kwargs.
   - Otherwise (raise a variable/attribute) → use `ast.unparse(node.exc)` as the name, resolve, empty meta.
3. Emit `Edge(type=EdgeType.RAISES, from_id=func_id, to_id=resolved_id, meta=...)`.
4. Emit external Node if new.

**Relevant Context:**
- `ast.Raise` node fields: `.exc` (the exception, or None), `.cause` (the `from` part, or None).
- `ast.Call` node fields: `.func` (the callable), `.args`, `.keywords`.
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) — `EdgeType.RAISES`, `NodeType.EXTERNAL`.

**Status:** `[ ] pending`

---

### Sub-task C — Extract `CALLS` edges from function bodies

**Intent:** Walk each module-level function's AST body, find all `ast.Call` nodes via `ast.walk`, and emit one `CALLS` edge per call.

**Expected Outcomes:**
- Every call expression in `list_articles` (e.g. `articles_repo.filter_articles(...)`, `ArticleForResponse.from_orm(article)`, `len(articles)`, `ListOfArticlesInResponse(...)`) produces a `CALLS` edge.
- `to_id` is `ast.unparse(call_node.func)` — the callable name only.
- `meta` is `(("call_text", ast.unparse(call_node)),)` — full call text including args.
- No external Node is created (calls are raw reference text only).
- Calls nested inside list comprehensions, conditionals, or other sub-expressions are captured (ast.walk visits all nodes).
- Deduplicated per function: one edge per unique `to_id`.

**Todo List:**
1. Write `_extract_calls(func_node, func_id)` that uses `ast.walk` over `func_node.body` to collect all `ast.Call` nodes.
2. For each Call: emit `Edge(type=EdgeType.CALLS, from_id=func_id, to_id=ast.unparse(call_node.func), meta=(("call_text", ast.unparse(call_node)),))`.
3. Deduplicate per function by `to_id`: if the same callable is called multiple times, emit one edge (last call_text kept). Use a `dict[str, Edge]` keyed by `to_id`.

**Relevant Context:**
- `ast.walk(node)` visits all descendant nodes recursively.
- `ast.unparse(call_node)` gives the full source text of the call including args.

**Status:** `[ ] pending`

---

### Sub-task D — Public entry point `extract_body_facts()`

**Intent:** Expose a single clean function that takes the already-extracted nodes + edges from `core.py` and the module index, iterates all `FUNCTION` nodes, calls the raise/call extractors, and returns the new edges + new external nodes.

**Expected Outcomes:**
- One public function: `extract_body_facts(nodes, edges, path_to_info, dotted_to_path)`.
- Returns `(new_raises_edges, new_calls_edges, new_external_nodes, unresolved)`.
- Only processes nodes whose `type == NodeType.FUNCTION`.
- Consistent calling convention with `resolve_all_classes()`.

**Todo List:**
1. Build `node_map: dict[str, Node]` from all nodes for name lookup.
2. Iterate nodes: for each `NodeType.FUNCTION` node, call `_extract_raises()` and `_extract_calls()`.
3. Collect and return all new edges + external nodes.

**Relevant Context:**
- [`src/docgen/extract/classes.py`](src/docgen/extract/classes.py) `resolve_all_classes()` — same input/output pattern.
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) — `NodeType.FUNCTION`.

**Status:** `[ ] pending`

---

### Sub-task E — Tests

**Intent:** Write `tests/test_bodies.py` covering all branches. Use the same temp-dir fixture pattern from `test_classes.py`.

**Expected Outcomes (one test per scenario):**
1. **Basic `RAISES`:** function with `raise HTTPException(status_code=400, detail="x")` → RAISES edge with correct `to_id` and `meta`.
2. **External Node created:** exception type imported from external lib → external Node in output.
3. **Bare `raise` skipped:** `raise` alone in except block → no RAISES edge.
4. **`raise variable` (no Call):** raises a pre-built instance → RAISES edge with empty meta.
5. **Chained raise ignored:** `raise X from Y` → only X captured, no second edge for Y.
6. **Basic `CALLS`:** function with several calls → CALLS edges with correct raw text.
7. **Calls deduplicated:** same call text twice in one function → one edge.
8. **`ast.walk` depth:** call nested inside a list comprehension → still captured.
9. **Non-function nodes skipped:** class nodes and module nodes produce no RAISES/CALLS edges.
10. **Integration smoke test:** run against real `target/app/api/routes/articles/articles_resource.py` — `create_new_article` has exactly one RAISES edge to `"external:fastapi.HTTPException"`.

**Todo List:**
1. Create `tests/test_bodies.py`.
2. Write a `_extract_body` helper that writes a temp file, calls `extract_file`, `build_module_index`, then `extract_body_facts`.
3. Write one test function per scenario above.

**Relevant Context:**
- Pattern from [`tests/test_classes.py`](tests/test_classes.py) — `_write`, `_extract_all`, `build_module_index` pattern.
- Real target: `create_new_article` in `target/app/api/routes/articles/articles_resource.py`.

**Status:** `[ ] pending`

---

## Dependency Order

```
Sub-task A (exception type resolution helper)
    ↓
Sub-task B (RAISES edge extraction)
    ↓
Sub-task C (CALLS edge extraction)
    ↓
Sub-task D (public entry point)
    ↓
Sub-task E (tests)
```

All sub-tasks are sequential; E validates A–D together.

---

## Files to Touch

| File | Change |
|---|---|
| `src/docgen/extract/bodies.py` | Full implementation (was 2-line stub) |
| `tests/test_bodies.py` | New file |

No other files require changes.
