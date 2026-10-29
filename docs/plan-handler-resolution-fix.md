# Plan: Exact Handler Resolution via __module__ + __qualname__

## Problem

`_find_function_node` in `src/docgen/extract/adapters/fastapi.py` matches handlers
by name alone. This produces four wrong HANDLES edges in the real-world target repo
where a route handler and a repository method share the same name:

```
route:DELETE /api/articles/{slug}/favorite  →  ArticlesRepository::remove_article_from_favorites  ✗
route:GET /api/articles/feed                →  ArticlesRepository::get_articles_for_user_feed      ✗
route:GET /api/tags                         →  TagsRepository::get_all_tags                        ✗
route:POST /api/articles/{slug}/comments    →  CommentsRepository::create_comment_for_article      ✗
```

**Second-order effect:** the route node's `file`, `lines`, and `handler_id` are
all derived from the wrong function node, so `hash_struct` for all four routes is
wrong. After the fix, all four route nodes get new hashes → those route pages +
`api.md` + ancestor pages become stale and must be re-rendered.

**Missing REQUEST_MODEL edge — two compounding bugs:**
For `POST /api/articles/{slug}/comments`:
1. Handler lookup picks the repository method → `_extract_request_models_from_handler`
   parses the repository file and finds no `CommentInCreate` annotation.
2. The OpenAPI fallback finds the schema name `Body_comments_create_comment_...`
   and skips it because it starts with `Body_`, without looking inside the
   wrapper's `properties` for the nested `CommentInCreate` reference.
   Fix (1) alone closes the missing edge — the AST path works correctly once it
   reads the actual handler file. Fix (2) is an independent general improvement.

**Silent failure:** the name-only scan emits no `Unresolved` entry. Nothing in
the unresolved report flagged the bug.

**Core rule:** never guess. If the exact lookup fails, emit `Unresolved`.

---

## Fix: capture `__module__` + `__qualname__` in the introspection script

`route.endpoint.__module__` is the dotted module name where the function was
**defined** — unaffected by re-exports. `route.endpoint.__qualname__` is:
- `"func_name"` — module-level function
- `"ClassName.method_name"` — class-based view method
- `"outer.<locals>.inner"` — nested function; not a graph node

Combined with `dotted_to_path` (already built at cli.py Step 3), the exact node
ID is constructed without any scan:

```
__module__  →  dotted_to_path  →  file_path
file_path + "::" + qualname.replace(".", "::")  →  node_id
```

Examples:
```
__module__ = "app.api.routes.articles.articles_common"
__qualname__ = "remove_article_from_favorites"
→  "target/app/api/routes/articles/articles_common.py::remove_article_from_favorites"

__module__ = "app.views"
__qualname__ = "ArticleView.get"
→  "target/app/views.py::ArticleView::get"
```

`<locals>` in `__qualname__` → emit `Unresolved`, no HANDLES edge, no crash.
Missing `__module__`/`__qualname__` (functools.partial, callable object, wrapper
without functools.wraps) → guarded by `getattr(..., None)` → emit `Unresolved`.

---

## Sub-task 1 — Introspection script: capture `__module__` and `__qualname__`

**Status:** [ ] pending  
**File:** `src/docgen/extract/adapters/fastapi.py`

In `_INTROSPECTION_SCRIPT`, extend the handler dict. Guard all attribute accesses
so unusual endpoints never crash the subprocess:

```python
ep = route.endpoint
handlers[key] = {
    "handler":  getattr(ep, "__name__",     None),
    "module":   getattr(ep, "__module__",   None),
    "qualname": getattr(ep, "__qualname__", None),
    "name":     getattr(route, "name", "") or "",
}
```

No `resp_*` capture needed — response model resolution comes from the OpenAPI
`responses` dict, not from `route.response_model`.

**Expected outcome:** the JSON printed by the subprocess contains `module` and
`qualname` for every handler entry.

---

## Sub-task 2 — Replace `_find_function_node` with exact ID lookup

**Status:** [ ] pending  
**Files:** `src/docgen/extract/adapters/fastapi.py`, `src/docgen/cli.py`

### 2a — `_resolve_handler` (replaces `_find_function_node`)

Add these two functions; delete `_find_function_node`:

```python
def _qualname_to_node_id(file_path: str, qualname: str) -> str:
    """Convert file path + __qualname__ to a node ID.

    "func"           → "path/to/file.py::func"
    "Class.method"   → "path/to/file.py::Class::method"
    """
    return file_path + "::" + qualname.replace(".", "::")


def _resolve_handler(
    handler_info: dict,
    dotted_to_path: dict[str, str],
    node_map: dict[str, Node],
) -> tuple[Node | None, str | None]:
    """Resolve a handler info dict to its Node using __module__ + __qualname__.

    Returns (node, failure_reason).  failure_reason is None on success.
    Never guesses — returns (None, reason) on any lookup failure.
    """
    module   = handler_info.get("module")
    qualname = handler_info.get("qualname")

    if not module or not qualname:
        return None, "missing __module__ or __qualname__ (unusual endpoint)"

    if "<locals>" in qualname:
        return None, f"nested function '{qualname}' is not a graph node"

    file_path = dotted_to_path.get(module)
    if not file_path:
        return None, f"module '{module}' not found in module index"

    node_id = _qualname_to_node_id(file_path, qualname)
    node = node_map.get(node_id)
    if node is None:
        return None, f"node '{node_id}' not found in extracted graph"

    return node, None
```

**Signature changes:**

Add `dotted_to_path: dict[str, str]` to `_openapi_to_facts` and `extract()`.
Build `node_map = {n.id: n for n in all_nodes}` once at the top of
`_openapi_to_facts` (replaces the per-route scan in `_find_function_node`).

In `cli.py` Step 7:
```python
adapter_result = fastapi_extract(
    all_nodes, all_edges, config, repo_root,
    dotted_to_path=dotted_to_path,
)
```

### 2b — Fix `_extract_request_models_from_handler` latent bug (note only)

The function currently finds the handler's AST node by name alone
(`item.name == func_node.name`). With sub-task 2a in place this cannot produce
a wrong result for the collision cases, because the correct file is always
passed. The full fix (matching on `parent_class` to disambiguate two functions
with the same name in the same file) is left as a follow-up comment in the
code — not blocking this sub-task.

### 2c — Fix the OpenAPI fallback for `Body_` wrappers

This is an independent correctness improvement that closes the second compounding
bug for `POST /api/articles/{slug}/comments` and works for any FastAPI repo using
`Body(embed=True)` or `Body(alias=...)`.

Currently the fallback skips any schema whose name starts with `Body_`. These
generated wrappers contain a `properties` dict whose values are `$ref` entries
pointing to the real model. Fix: unwrap one level instead of skipping entirely.

Change `_extract_body_schema_name` to accept the `components` schemas dict and
unwrap `Body_` wrappers:

```python
def _extract_body_schema_name(
    request_body: dict[str, Any],
    components: dict[str, Any],
) -> str | None:
    content = request_body.get("content", {})
    for media_type in content.values():
        schema = media_type.get("schema", {})
        name = _extract_schema_name(schema)
        if not name:
            for key in ("allOf", "anyOf", "oneOf"):
                for item in schema.get(key, []):
                    name = _extract_schema_name(item)
                    if name:
                        break
        if not name:
            continue
        if name.startswith("Body_"):
            # Unwrap: look in components/schemas/<name>/properties for nested $ref
            body_schema = components.get(name, {})
            for prop in body_schema.get("properties", {}).values():
                nested = _extract_schema_name(prop)
                if nested:
                    return nested
        else:
            return name
    return None
```

Pass `openapi_dict.get("components", {}).get("schemas", {})` as `components`
at the call site in `_openapi_to_facts`.

**Expected outcome after 2a + 2c:**
- All four wrong HANDLES edges are fixed
- `POST /api/articles/{slug}/comments` gains REQUEST_MODEL edge to `CommentInCreate`
- `hash_struct` for all four route nodes changes (handler ID, file, lines differ)

---

## Sub-task 3 — Guard `_find_class_node` against ambiguous class names

**Status:** [ ] pending  
**File:** `src/docgen/extract/adapters/fastapi.py`

The current target repo has no duplicate class names, so the name-only scan is
safe here by luck. In general FastAPI repos, Pydantic v1 renames clashing schema
names with module prefixes (e.g. two classes both named `Item` in different files).
A name-only scan would silently pick the wrong one.

The minimal correct fix: when `_find_class_node` sees multiple matches, return
`None` and emit `Unresolved` at the call site instead of silently picking one:

```python
def _find_class_node(class_name: str, all_nodes: list[Node]) -> Node | None:
    """Return the unique CLASS node with this name, or None.

    Returns None for both zero matches (not found) and two-or-more matches
    (ambiguous — caller must emit Unresolved rather than guessing).
    """
    matches = [n for n in all_nodes if n.type is NodeType.CLASS and n.name == class_name]
    return matches[0] if len(matches) == 1 else None
```

At every call site where `_find_class_node` is used for response/request model
resolution, add an ambiguity check:

```python
matches = [n for n in all_nodes if n.type is NodeType.CLASS and n.name == schema_name]
if len(matches) > 1:
    unresolved.append(Unresolved(
        what=f"ambiguous_class_name:{schema_name}",
        why=f"{len(matches)} CLASS nodes named '{schema_name}': "
            + ", ".join(n.id for n in matches),
        where=route_id,
    ))
    # fall through to external:
```

**Expected outcome:** on the current target repo: no behaviour change (no
duplicates). On a repo with same-named models: `external:ClassName` + an
`Unresolved` entry surfacing the ambiguity, rather than a silent wrong link.

---

## Sub-task 4 — Tests

**Status:** [ ] pending  
**New file:** `tests/test_handler_resolution.py`  
**Updated file:** `tests/test_fastapi_adapter.py`

### Unit tests in `tests/test_handler_resolution.py`

All tests construct the fact graph directly and call `_openapi_to_facts` with
fixture handler maps that include `module` + `qualname`. No subprocess, no real
target.

**Test 1 — same name, handler vs repository method, order-independent:**
Graph: `routes.py::create` (module-level) + `repo.py::Repo::create` (method,
`parent_class` set). Feed `{"module": "routes", "qualname": "create", ...}`.
Assert HANDLES edge → `routes.py::create`. Run with nodes in reversed order;
assert identical result.

**Test 2 — same handler name in two route files:**
`routes_a.py::list_items` and `routes_b.py::list_items`. Two routes:
`GET /a` → `module="routes_a"`, `GET /b` → `module="routes_b"`.
Assert each HANDLES edge points to its own file.

**Test 3 — handler defined in defining module, registered via re-export:**
Graph has `utils.py::helper`. Feed `module="utils"`, `qualname="helper"`.
Assert HANDLES edge → `utils.py::helper` (not whatever file the route is in).

**Test 4 — class-based handler (CBV):**
Graph has `views.py::ArticleView::get` with `parent_class` set.
Feed `qualname="ArticleView.get"`, `module="app.views"`.
Assert HANDLES edge → `views.py::ArticleView::get`.

**Test 5 — nested function → Unresolved, no crash:**
Feed `qualname="outer.<locals>.inner"`.
Assert: no HANDLES edge; one `Unresolved` with `"locals"` in the reason; no exception.

**Test 6 — two classes with the same name → Unresolved, no wrong edge:**
Two CLASS nodes named `Item` in different files.
Assert `_find_class_node("Item", nodes)` returns `None`.
Assert the RESPONSE_MODEL resolution emits `Unresolved` with
`ambiguous_class_name:Item`. Assert no RESPONSE_MODEL edge is produced.

**Test 7 — introspection output contract:**
Mock the subprocess to return a known JSON payload.
Assert the parsed handler dict contains both `"module"` and `"qualname"` keys.
This is a contract test: it fails if the introspection script is changed in a
way that drops those fields.

### Invariant tests folded into `tests/test_fastapi_adapter.py`

These fold into the existing `test_real_repo_route_consistency`, which already
builds the full node graph from source and calls `extract()`.

**Test 8 — every HANDLES target is module-level:**
After calling `extract(...)`, for every HANDLES edge, look up the target Node
object (from the returned node list, not from `generated/facts.json`). Assert
`node.parent_class == ""` for every target. Expected: 0 violations. Would have
caught all four original bad edges.

**Test 9 — AST extractor and introspection adapter agree on full ID:**
For every HANDLES edge `(route_id → func_id)` returned by `extract()`:
- Take `func_id` = e.g. `"target/app/api/routes/comments.py::create_comment_for_article"`
- From the AST extractor output (`extract_ast_routes`), find the `RouteDecl`
  whose `(method, handler_name)` matches `(route.method, func_id.rsplit("::", 1)[-1])`
- Assert `func_id == RouteDecl.file + "::" + RouteDecl.handler_name`

This is an independent check: the AST extractor reads `@router.method(...)` from
source text directly; the introspection adapter reads `route.endpoint.__module__`
+ `__qualname__` from the running app. Agreement on the **full ID** (file +
name, not name alone) confirms both paths point to the same function. This would
have caught the original bug — the name matched, but the file differed.

**Why this is not circular:** the route node's `file` field is set from
`func_node.file`, so asserting `func_id.startswith(route.file)` would be
circular. Test 9 instead compares against `RouteDecl.file` — a value the
introspection adapter never sees — which makes the check genuinely independent.

**Test 10 — cross-check can detect disagreement:**
Take the HANDLES edges from `extract()`, replace one `to_id` with a
known-wrong value (e.g. a repository method ID). Call the cross-check helper
directly. Assert it returns a non-empty violation list. Confirms the check is
not trivially passing.

### Updated call sites in `tests/test_fastapi_adapter.py`

The following must be updated or the file fails to import/collect after the fix:

1. **Import list:** remove `_find_function_node`; add `_resolve_handler`,
   `_qualname_to_node_id`.

2. **All `_openapi_to_facts` call sites** (tests 2, 3, E4×2, E5×4): add
   `dotted_to_path={}` or a fixture-appropriate mapping. Add `module` and
   `qualname` to every handler map. For tests that deliberately omit them,
   assert `Unresolved` is emitted and no HANDLES edge is produced.

   Example rewrite:
   ```python
   # Before
   handler_map = {"GET /items": {"handler": "list_items", "name": "items:list"}}
   route_nodes, edges, unresolved = _openapi_to_facts(
       openapi_dict, handler_map, all_nodes, Path(".")
   )

   # After
   handler_map = {
       "GET /items": {
           "handler": "list_items",
           "module": "app.routes",
           "qualname": "list_items",
           "name": "items:list",
       }
   }
   dotted_to_path = {"app.routes": "app/routes.py"}
   route_nodes, edges, unresolved = _openapi_to_facts(
       openapi_dict, handler_map, all_nodes, Path("."),
       dotted_to_path=dotted_to_path,
   )
   ```

3. **`test_real_repo_route_consistency`:** pass `dotted_to_path` (already built
   inside the test at line 175) into `extract(...)`.

---

## Regression verification (mandatory before marking done)

After all sub-tasks are implemented and tests pass:

1. In `fastapi.py`, temporarily revert to name-only scan (restore
   `_find_function_node`, replace `_resolve_handler` call with it).
2. Run `pytest tests/test_handler_resolution.py tests/test_fastapi_adapter.py -v`.
3. Confirm **tests 1, 8, and 9 fail** (and only those — not 2–7, 10).
4. Restore the fix.
5. Re-run; confirm all tests pass.
6. Log the before/after test output in `BOB_LOG.md`.

This step is required. A test that doesn't fail without the fix provides no
protection.

---

## On the runtime warning

**Decision: drop it entirely.** After the fix, a HANDLES target has `parent_class`
set only when `__qualname__` is `Class.method` — the legitimate CBV case.
The warning cannot fire on a mis-resolution; it fires on every CBV route,
which is noise. Test 8 is the correct guard.

---

## Second-order effects after re-running `docgen extract`

- 4 route nodes get new `hash_struct` (handler ID, file, lines all change)
- `docgen check` reports those 4 route pages + `api.md` as stale
- `docgen update` re-renders them
- `POST /api/articles/{slug}/comments` gains REQUEST_MODEL edge to `CommentInCreate`

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/extract/adapters/fastapi.py` | Extend introspection script (1); add `_resolve_handler`, `_qualname_to_node_id`, delete `_find_function_node` (2a); fix `_extract_body_schema_name` for `Body_` wrappers (2c); guard `_find_class_node` for ambiguous names (3); add `dotted_to_path` param to `_openapi_to_facts` + `extract` |
| `src/docgen/cli.py` | Pass `dotted_to_path` into `fastapi_extract(...)` |
| `tests/test_handler_resolution.py` | New — tests 1–7 |
| `tests/test_fastapi_adapter.py` | Update imports; rewrite all `_openapi_to_facts` call sites; add tests 8–10 into `test_real_repo_route_consistency` |
| `docs/memory.md` | Add D-044 |
| `docs/BOB_LOG.md` | Add entry + regression verification result |

---

## Dependency order

```
Sub-task 1  (introspection script: add module + qualname)
    ↓
Sub-task 2a (handler resolver + cli threading)
Sub-task 2c (Body_ wrapper unwrapping — independent, same PR)
    ↓
Sub-task 3  (ambiguous class name guard)
    ↓
Sub-task 4  (tests written against fixed code)
    ↓
Regression check (revert → confirm tests 1/8/9 fail → restore → log in BOB_LOG)
```
