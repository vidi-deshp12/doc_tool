# Plan: Task 2a.9 — FastAPI Dependency Tree

## Goal

Resolve the `DEPENDS_ON` edges that `core.py` already emits with placeholder `to_id = "external:<unparsed>"` into real in-repo node IDs where possible, and then **trace the chain recursively** so the full dependency tree is captured in `facts.json`.

The task acceptance criterion: `create_new_article` shows the full chain to auth and DB dependencies; update/delete show the permission dependency.

---

## What already exists (do NOT re-implement)

`core.py` already:
- Detects every `Depends(...)` in function parameters and `dependencies=[Depends(...)]` decorator kwargs.
- Emits `DEPENDS_ON` edges from the function to `to_id = "external:<ast.unparse(arg)>"`.
- Stores `meta=(("via", "parameter"),)` or `meta=(("via", "decorator"),)`.

So the raw `dep_name` strings are already in the graph. Examples from the target:
- `"get_articles_filters"` — a plain function name
- `"get_current_user_authorizer(required=False)"` — a factory call (returns a callable)
- `"get_repository(ArticlesRepository)"` — another factory call

The gap is that all `to_id` values are `external:...`, meaning no link to in-repo FUNCTION nodes.

---

## Key design insight: what "resolve" means for Tier A

A `Depends(...)` argument is one of two shapes:
1. **Direct name**: `Depends(get_articles_filters)` — `dep_name = "get_articles_filters"` — resolves to a FUNCTION node in the fact graph.
2. **Factory call**: `Depends(get_repository(ArticlesRepository))` — `dep_name = "get_repository(ArticlesRepository)"` — the *factory* (`get_repository`) is a FUNCTION node; the *result* is not separately tracked. Resolve to the factory function node.

Resolution algorithm: extract the base function name from the `dep_name` string (split off `(...)` if present), look it up in the existing node set by name, use import records to find the right file when ambiguous.

---

## Complexity of the recursive tree

The target has a 3-level dep chain for the article modify routes:

```
update_article_by_slug
  → check_article_modification_permissions     [via decorator]
      → get_article_by_slug_from_path           [via parameter]
          → get_current_user_authorizer(req=F)  [via parameter]
          → get_repository(ArticlesRepository)  [via parameter]
      → get_current_user_authorizer()           [via parameter]
  → get_article_by_slug_from_path              [via parameter]
  → get_repository(ArticlesRepository)         [via parameter]
```

The recursion is across **files** — each dependency function is defined in a different module (`dependencies/articles.py`, `dependencies/authentication.py`, `dependencies/database.py`). So:
- `core.py` already extracted the DEPENDS_ON edges for each *file* as it was processed.
- The missing piece is the *re-linking pass* that replaces `external:` with in-repo node IDs.
- No new traversal is needed at run time — the full tree is implicit once all nodes are linked correctly.

Cycle guard: a dependency graph can contain cycles if badly written. We need to detect them, emit Unresolved entries, and not infinite-loop.

---

## Where the new code lives

A new file: `src/docgen/extract/adapters/resolve_deps.py`

This is an **adapter-layer** pass (run after core extraction and import resolution) that:
1. Takes all existing nodes and edges.
2. For every `DEPENDS_ON` edge with `to_id = "external:<dep_name>"`, tries to resolve it to a real FUNCTION node.
3. Replaces (or supplements — see sub-task 1 design) the edge with the resolved `to_id`.
4. Emits `Unresolved` for anything that cannot be resolved.

It does **not** re-traverse the tree; the recursive structure emerges naturally because every dep function's own DEPENDS_ON edges were already emitted by `core.py` during per-file extraction.

---

## Resolution strategy in detail

### Step A — build a name→node lookup

From `all_nodes`, build:
```python
name_to_nodes: dict[str, list[Node]]  # function name → list of FUNCTION nodes with that name
```

### Step B — per-edge resolution

For each DEPENDS_ON edge `from_id → external:<dep_name>`:

1. Parse the `dep_name` string into three parts: optional module alias, base function name, optional args.

   Simple names:
   - `"get_articles_filters"` → alias=none, base=`"get_articles_filters"`, args=none
   - `"get_current_user_authorizer(required=False)"` → alias=none, base=`"get_current_user_authorizer"`, args=`"required=False"`
   - `"get_repository(ArticlesRepository)"` → alias=none, base=`"get_repository"`, args=`"ArticlesRepository"`

   Module-qualified names (e.g. from aliased imports like `from app.api.dependencies import authentication`):
   - `"authentication.get_current_user_authorizer()"` → alias=`"authentication"`, base=`"get_current_user_authorizer"`, args=`""`
   - `"articles.get_article_by_slug_from_path"` → alias=`"articles"`, base=`"get_article_by_slug_from_path"`, args=none
   - `"database.get_repository(CommentsRepository)"` → alias=`"database"`, base=`"get_repository"`, args=`"CommentsRepository"`

   When a module alias is present, use the `from_id`'s file import records to resolve alias → dotted module name, then `dotted_to_path` → file path. Only look up the base name in nodes belonging to that specific file.

2. Look up `name_to_nodes[base_name]` (filtered to resolved file when alias present):
   - **0 matches** → keep `to_id` as `external:...`; emit Unresolved.
   - **1 match** → resolve: new `to_id = node.id`.
   - **2+ matches (no alias)** → use import records to disambiguate by file. If still ambiguous, keep `external:` and emit Unresolved. **Option B — never guess.**

3. If args were present (factory call), add `("factory_args", args_str)` to the edge `meta`.

### Step C — output

Return `(resolved_edges, new_unresolved)` where `resolved_edges` is a replacement list of all DEPENDS_ON edges with in-repo targets swapped in.

### Cycle guard (for 2a.10 and future recursive traversal)

A cycle guard is needed for any future traversal of the dep graph, but since we are only *re-linking* edges (not traversing), cycles in this pass don't cause infinite loops. However, include a `detect_dep_cycles(nodes, edges)` utility that:
- Builds the DEPENDS_ON sub-graph.
- Runs DFS with a visited+stack set.
- Returns list of cycle paths as strings.
- Called from cli.py Step 7c; emits Unresolved for each cycle.

---

## Sub-tasks

### Sub-task 1 — Resolution pass: `resolve_deps.py` [ ] pending

**Intent:** Replace `external:` placeholders in DEPENDS_ON edges with real in-repo FUNCTION node IDs.

**Expected outcomes:**
- `DEPENDS_ON` edges from `create_new_article` point to `target/app/api/dependencies/authentication.py::get_current_user_authorizer` (etc.) not `external:get_current_user_authorizer()`.
- Factory call deps (`get_repository(ArticlesRepository)`) resolve to the factory function node; `meta` includes `factory_args`.
- Unresolved emitted when base name not found anywhere.
- `detect_dep_cycles` utility included; returns `[]` for the target (no cycles).

**Todo list:**
1. Create `src/docgen/extract/adapters/resolve_deps.py`.
2. Implement `_extract_base_name(dep_name: str) -> str` — split off `(...)`.
3. Implement `_build_name_index(nodes: list[Node]) -> dict[str, list[Node]]` — FUNCTION nodes only.
4. Implement `_resolve_dep_name(dep_name, from_id, name_index, path_to_info, dotted_to_path) -> str | None` — returns resolved node ID or None.
5. Implement `resolve_dep_edges(nodes, edges, path_to_info, dotted_to_path) -> tuple[list[Edge], list[Unresolved]]` — main entry point; re-emits all non-DEPENDS_ON edges unchanged, replaces DEPENDS_ON with resolved version.
6. Implement `detect_dep_cycles(nodes, edges) -> list[str]` — DFS on DEPENDS_ON sub-graph, returns cycle descriptions.

**Relevant context:**
- Current DEPENDS_ON edges: `from_id` = in-repo function node ID; `to_id` = `"external:<dep_name>"`; `meta` = `(("via", "parameter"|"decorator"),)`.
- `path_to_info` (from `modules.py`): maps POSIX file path → `ModuleInfo` with `.imports` list of `ImportRecord`. Use to disambiguate which file a name comes from.
- `dotted_to_path` maps dotted module name → POSIX file path.
- Resolution pattern to follow: `extract/classes.py` `_resolve_base` which does the same name→file→node lookup for class bases.

---

### Sub-task 2 — Tests [ ] pending

**Intent:** Verify resolution, factory-call handling, ambiguity, and cycle detection.

**Tests to add** in `tests/test_resolve_deps.py`:

1. **Plain name resolves to node**: fixture with `Depends(get_filters)` → DEPENDS_ON edge `to_id = node.id`.
2. **Factory call resolves to factory node**: `Depends(get_repo(MyRepo))` → edge `to_id = get_repo_node.id`, `meta` includes `factory_args = "MyRepo"`.
3. **Unresolved name stays external**: `Depends(unknown_func)` → keeps `external:unknown_func`, emits Unresolved.
4. **Non-DEPENDS_ON edges are passed through unchanged**.
5. **detect_dep_cycles empty graph**: returns `[]`.
6. **detect_dep_cycles cycle**: A→B, B→A → returns a non-empty list with both names.
7. **Integration**: run `resolve_dep_edges` on the real target fact graph; verify `create_new_article`'s DEPENDS_ON edges all have in-repo `to_id`s (no `external:` remaining for known dep functions).

---

### Sub-task 3 — Wire into `cli.py` [ ] pending

**Intent:** Run the resolution pass after the core extraction steps so `facts.json` contains resolved dep edges.

**Expected outcomes:**
- `cli.py` Step 7c calls `resolve_dep_edges`.
- `docgen extract` on the target prints a summary: `N dep edges resolved, M unresolved`.
- Cycle detection runs and emits Unresolved for any cycles found (0 expected on target).
- All existing 115 tests still pass.

**Todo list:**
1. Add Step 7c to `_run_extract` in `cli.py`, after Step 7b (AST routes) and before Step 8 (dedup).
2. Replace the DEPENDS_ON edges in `all_edges` with the resolved version.
3. Run `detect_dep_cycles` and extend `all_unresolved`.
4. Print a stderr summary line.

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/extract/adapters/resolve_deps.py` | **New** — resolution pass + cycle guard |
| `src/docgen/cli.py` | Add Step 7c |
| `tests/test_resolve_deps.py` | **New** — 7 tests |

`src/docgen/extract/core.py` — **unchanged** (already emits DEPENDS_ON correctly).
`src/docgen/facts/schema.py` — **unchanged** (EdgeType.DEPENDS_ON already defined).

---

## Known limitations (not in scope)

- `Security(...)` calls (used for header-based auth in `authentication.py`) look like `Depends` but use a different FastAPI class. They are **not** currently collected by `core.py`. Out of scope for 2a.9 — the acceptance criterion only requires `Depends(...)` edges.
- `get_current_user_authorizer()` is a factory that returns one of two private functions (`_get_current_user` or `_get_current_user_optional`) based on `required=`. The resolution will point to the factory itself, not the returned callable. This is the correct Tier A behaviour — the task says "factory calls recorded with args".
- Private functions (leading `_`) that are the real implementations will appear in the graph as nodes (they are top-level functions in their files) and will be reachable if a DEPENDS_ON edge points directly to them (e.g. `_get_current_user` appears as a dep of `_get_current_user_optional`).
