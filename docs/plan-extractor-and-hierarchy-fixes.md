# Plan: Extractor and Hierarchy Fixes

## Goal

Fix six concrete gaps discovered after the first bob_shell summarization run.
All are grouped into one extraction pass + one hierarchy/prompts pass so the
pipeline runs `docgen extract` once, then `docgen summarize`, and the full
set of improvements is live.

**Done when:** `docgen extract && docgen summarize --backend bob_shell` produces:
- PACKAGE nodes for every folder containing modules (system summary works)
- Route nodes with non-empty `hash_struct` / `hash_source`
- REQUEST_MODEL edges pointing to the handler's actual Pydantic class
- Module-level functions with per-span `hash_source` (not whole-file)
- Route ID (`route:GET /api/...`) citeable by the handler function summary
- A working system summary built from package-level children

---

## Issues addressed

| ID | Where | Description |
|---|---|---|
| E1 | `extract/core.py` | Module-level function `hash_source` uses whole-file hash |
| E4 | `extract/adapters/fastapi.py` | Route nodes have empty `hash_struct` / `hash_source` |
| E5 | `extract/adapters/fastapi.py` | REQUEST_MODEL edges point to auto-generated wrapper names |
| S2 | `extract/packages.py` (new) + `cli.py` | No PACKAGE nodes — system summary has no children |
| S4a | `summarize/hierarchy.py` | HANDLES edges not indexed by function — route data absent from function prompts |
| S4b | `summarize/prompts.py` | Route IDs not in `allowed_fact_ids` — handler can't cite its own route |

---

## Sub-task 1 — E1: Per-span `hash_source` for module-level functions [pending]

**Intent:** Every module-level function should have a `hash_source` covering only
its own decorator-to-end span. Today `extract_file` computes a single file-level
`hash_source` and passes it to `_make_function_node` for every function in the file,
so editing one function marks every sibling stale. Methods are already correct.

**Fix:** Remove the `hash_source` parameter from `_make_function_node`; compute it
inside the function using `_hash_source_span(source, start, end)` (same as
`_make_method_node` at line 273). Update the call site in `extract_file` to pass
`source` instead of `hash_source`. The module node continues using the whole-file hash.

**Files:** `src/docgen/extract/core.py`

**Tests to add** in `tests/test_core.py`:
1. Two functions in the same file have different `hash_source` values.
2. Editing one function's body changes that function's `hash_source` but not the other's.

---

## Sub-task 2 — E4 + E5: Route hashes and real request model edges [pending]

**Intent:**
- **E4:** Route nodes have `hash_struct=""` and `hash_source=""`, so route drift is
  invisible. Compute deterministic hashes from the route's structural data.
- **E5:** REQUEST_MODEL edges point to FastAPI auto-generated wrapper names
  (`Body_articles_create_article_api_articles_post`). Derive them instead from the
  handler function's parameter annotations.

**Order of operations inside `_openapi_to_facts`** (resolves the contradiction in the
draft — all model work happens before the Node is constructed):

1. Look up the handler function node by name.
2. Resolve REQUEST_MODEL: call `_extract_request_models_from_handler` (new helper) to
   get real model IDs from the handler's AST. Fall back to OpenAPI-derived names only
   when the AST yields nothing. **Filter out any name starting with `Body_`.**
3. Resolve RESPONSE_MODEL: existing logic (unchanged).
4. **Hash:** compute `hash_struct` and `hash_source` from fully-resolved data:
   - `hash_struct = sha256(method + full_path + str(status_code) + handler_id
     + sorted_request_model_ids + sorted_response_model_ids)`
   - `hash_source = hash_struct` (routes have no separate body; structural = source)
5. Construct the ROUTE `Node` with those hashes.
6. Emit HANDLES, REQUEST_MODEL, RESPONSE_MODEL edges.

**`_extract_request_models_from_handler` design:**

FastAPI request body parameters follow two patterns:

- **Explicit Body:** `item: ItemModel = Body(...)` — annotation is the model.
- **Implicit body:** `item: ItemModel` with no default — if the annotation resolves to
  an in-repo Pydantic model and the parameter is NOT `self`, `request`, `response`,
  `db`, `background_tasks`, nor has a `Depends`/`Query`/`Path` default, treat it as the
  request body.

Steps:
1. From `func_node.file` + function name, look up the AST node (re-parse via the
   already-available `path_to_info` import records).
2. For each parameter, check whether its annotation resolves to an in-repo Pydantic
   model using `_resolve_annotation` (new small helper, same logic as
   `bodies._resolve_exception_type` — look up the bare name in import records, walk
   `dotted_to_path`, check `is_pydantic_model` on the resulting node).
3. Classify the parameter as body/non-body using the rules above. Yield `(param_name,
   resolved_class_id)` for each body parameter.

Accept `path_to_info` and `dotted_to_path` and `node_map` as additional arguments to
`_openapi_to_facts` (and propagate from `extract()`).

**Files:** `src/docgen/extract/adapters/fastapi.py`

**Tests to add** in `tests/test_fastapi_adapter.py`:
1. Route nodes have non-empty `hash_struct` after extraction.
2. Changing `full_path` changes `hash_struct`.
3. Explicit `Body(...)` parameter: REQUEST_MODEL edge points to the annotation class.
4. Implicit Pydantic parameter (no default): REQUEST_MODEL edge points to the class.
5. `Depends` parameter is not treated as a request body.
6. Auto-generated `Body_...` name from OpenAPI is filtered out when AST resolution
   succeeds.

---

## Sub-task 3 — S2: Synthesize PACKAGE nodes from directory structure [pending]

**Intent:** The hierarchy driver needs PACKAGE nodes to build the package level, which
feeds the system summary. Without them `package_results` is empty and bob refuses the
system prompt.

**Design — new file `src/docgen/extract/packages.py`:**

`synthesize_packages(module_nodes, existing_nodes, repo_root, source_root)`:
- Collect all MODULE nodes. Skip any that live in the repo root directory itself
  (their parent would be the virtual system node, not a package).
- Group by **immediate parent directory** of the module's POSIX path (relative to
  `source_root`).
- For each unique directory, produce one PACKAGE node:
  - `id` = directory path relative to repo root, POSIX (e.g. `target/app/db`)
  - `type` = `NodeType.PACKAGE`
  - `file` = `""`, `lines` = `(0, 0)`
  - `hash_struct` = sha256 of sorted child node IDs (modules + sub-packages)
  - `hash_source` = same as `hash_struct`
  - `name` = last component of the directory path
- Emit `CONTAINS` edges: package → each child MODULE in that directory.
- Handle nesting: `target/app/db/repositories` → parent is `target/app/db`. Emit
  CONTAINS edge from parent package to child package. Sort packages depth-first so
  inner packages are resolved before outer ones.
- Do NOT duplicate packages that already exist as `NodeType.PACKAGE` in the graph
  (check `existing_nodes`).
- Returns `(new_package_nodes, new_contains_edges)`.

Wire into `_run_extract` in `cli.py` as **Step 5b** — after body facts (Step 5) and
before the FastAPI adapter (Step 7), since route extraction can then reference packages.

**Files:** `src/docgen/extract/packages.py` (new), `src/docgen/cli.py`

**Tests — `tests/test_packages.py` (new file, 5 tests):**
1. Two modules in the same directory → one PACKAGE node + two CONTAINS edges.
2. Nested directories → parent CONTAINS child package + inner CONTAINS edges.
3. Module in root directory → no PACKAGE node created for the root itself.
4. `hash_struct` changes when a module is added to the package.
5. `topological_order` from `hierarchy.py` places package nodes after their modules.

---

## Sub-task 4 — S4a + S4b: Route data in function prompts and citeable route IDs [pending]

**Two related changes; implement together.**

### S4a — HANDLES edges indexed by function (`hierarchy.py`)

`_build_edges_by_from` currently only indexes edges by `from_id`. HANDLES edges go
`route → function`, so they appear under the route's ID, which is never summarized.
The function never sees them.

Fix: extend `_build_edges_by_from` to also include HANDLES edges **keyed by `to_id`**
(the function). This makes the HANDLES edge appear in `req.edges` for the handler
function. The prompt renders it under `## Relational facts` as:

```
- handles: route:POST /api/articles
```

The route node's full facts (path, method, status_code) are already in `facts.json`
and will be visible to the model via the cited route ID.

### S4b — Route IDs in `allowed_fact_ids` (`prompts.py`)

`allowed_fact_ids` currently includes in-repo targets of `raises`, `depends_on`, and
`inherits` edges. Extend `_CITEABLE_EDGE_TYPES` to also include `"handles"`. Since HANDLES
edges are now in `req.edges` (after S4a), the route ID flows into `allowed_fact_ids`
automatically with this one-line change.

Route nodes are already in `facts.json` (they have type `route`) and therefore in the
validator's `known_ids` set — no change to `citations.py` or `cli.py` is needed.

**Files:** `src/docgen/summarize/hierarchy.py`, `src/docgen/summarize/prompts.py`

**Tests to add:**
- `tests/test_hierarchy.py`: a FUNCTION node with a HANDLES-to edge receives that edge
  in its `SummaryRequest.edges`.
- `tests/test_prompts.py`: a request with a `handles` edge includes the route ID in
  `allowed_fact_ids`.

---

## Sub-task 5 — Docs updates [pending]

After all sub-tasks pass and `docgen extract` + `docgen summarize` complete cleanly:

- Tick the relevant task IDs in `docs/tasks.md`
- Add D-039 to `docs/memory.md`
- Add entry to `BOB_LOG.md`

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/extract/core.py` | Sub-task 1: per-span `hash_source` for module-level functions |
| `src/docgen/extract/adapters/fastapi.py` | Sub-task 2: route hashes + real request model edges |
| `src/docgen/extract/packages.py` | Sub-task 3: new file — `synthesize_packages` |
| `src/docgen/cli.py` | Sub-task 3: wire in `synthesize_packages` as Step 5b |
| `src/docgen/summarize/hierarchy.py` | Sub-task 4a: HANDLES edges indexed by `to_id` |
| `src/docgen/summarize/prompts.py` | Sub-task 4b: `"handles"` added to `_CITEABLE_EDGE_TYPES` |
| `tests/test_core.py` | Sub-task 1: 2 new hash tests |
| `tests/test_fastapi_adapter.py` | Sub-task 2: 6 new tests |
| `tests/test_packages.py` | Sub-task 3: new file, 5 tests |
| `tests/test_hierarchy.py` | Sub-task 4a: 1 new test |
| `tests/test_prompts.py` | Sub-task 4b: 1 new test |
| `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md` | Sub-task 5: status updates |

---

## Dependency order

```
Sub-task 1 (E1)       independent — run first
Sub-task 2 (E4+E5)    independent of 1; 2 changes in fastapi.py done together
Sub-task 3 (S2)       independent of 1+2; unblocks system summary
Sub-task 4 (S4a+S4b)  independent of 1-3; 2 changes done together
Sub-task 5            last
```

Sub-tasks 1, 2, 3, and 4 have no shared files and can be implemented in any order.
Sub-tasks 2 (E4+E5) must be done in a single edit to `fastapi.py` because both touch
`_openapi_to_facts`; the order within that function is:
resolve models (E5) → hash (E4) → construct Node → emit edges.
