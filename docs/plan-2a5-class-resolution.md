# Plan: Task 2a.5 — Class Resolution (`extract/classes.py`)

## Top-Level Overview

**Goal:** Implement `src/docgen/extract/classes.py` so that after extraction the fact graph has:
1. **Resolved `INHERITS` edges** — replace the stub `external:<raw-name>` edges emitted by `core.py` with edges pointing to the correct in-repo node ID (`path/to/file.py::ClassName`) or to `external:<dotted.library.name>`.
2. **Flattened inherited fields** — each class Node gets a `fields` tuple that includes fields from all in-repo ancestors, deduplicated (child wins on name clash), stopping at the repo boundary.
3. **`is_pydantic_model` flag** — set to `True` on any class whose resolved ancestor chain reaches `pydantic.BaseModel` (or `pydantic.main.BaseModel`).

**Scope:** One new file (`extract/classes.py`), minor change to `extract/core.py` to suppress the stub INHERITS edges (so classes.py owns all INHERITS edges), new test file.

**Non-goals:** Resolving method calls, tracking field defaults through inheritance, handling `__init_subclass__` / metaclasses, resolving class members defined outside `__init__` (those are out of scope for Phase 2a).

---

## Design Decisions (confirmed by user)

- `Node.bases` stays as raw source text (what the source code says — useful for prose generation).
- `INHERITS` edges carry the resolved topology. Where resolution succeeds, the edge points to the in-repo node ID. Where it fails (external, dynamic), the edge points to `external:<lib_name>.<ClassName>`.
- `core.py`'s stub INHERITS edges (`external:<raw-name>`) are **removed** from `extract_file()` — `classes.py` takes ownership of all INHERITS edge production.
- Fields flattening is **in-repo ancestors only** (per architecture.md §5 and task spec). External bases contribute no fields.

---

## Sub-Tasks

---

### Sub-task A — Remove stub INHERITS edges from `core.py`

**Intent:** `core.py` currently emits `INHERITS` edges with unresolved `external:<raw-name>` targets. Since `classes.py` will produce fully resolved edges, the stubs must be removed so edges are not doubled.

**Expected Outcomes:**
- `extract_file()` no longer emits any `INHERITS` edges.
- Existing tests that check the `CONTAINS` edges still pass.
- No test that was asserting on stub INHERITS edges (there are none — confirmed by subagent).

**Todo List:**
1. In `extract_file()` (core.py, around line 439-448), delete the loop that appends `EdgeType.INHERITS` edges.
2. Run existing tests — confirm all 39 still pass.

**Relevant Context:**
- [`src/docgen/extract/core.py`](src/docgen/extract/core.py) lines 439-448 — the loop to remove.

**Status:** `[ ] pending`

---

### Sub-task B — Implement `resolve_classes()` in `extract/classes.py`

**Intent:** Build the core resolution function. It takes the full set of extracted nodes + edges (from `core.py` + `modules.py`) and:
1. Builds a class lookup table: `class_node_id → Node` and `file_path → list[class_node_id]`.
2. For each class node, resolves each raw base name to a node ID by:
   a. Looking up what names are imported into the class's file (using the `path_to_info` import records from `modules.py`).
   b. Looking up the resolved import target in `dotted_to_path`.
   c. Looking for a class with that name in the target file.
   d. Falling back to `external:<lib_name>.<ClassName>` if unresolved.
3. Emits a resolved `INHERITS` edge for each base (in-repo or external).
4. For external bases, emits an `external` Node (guarded by a seen-set to avoid duplicates).

**Expected Outcomes:**
- `ListOfArticlesInResponse` → `INHERITS` → `target/app/models/schemas/rwschema.py::RWSchema` (in-repo edge).
- `RWSchema` → `INHERITS` → `target/app/models/domain/rwmodel.py::RWModel` (in-repo edge).
- `RWModel` → `INHERITS` → `external:pydantic.BaseModel` (external edge).
- No stale `external:RWSchema` stub edges appear.
- Unresolvable bases (e.g. dynamic / forward refs) logged as `Unresolved` entries.

**Todo List:**
1. Define the public function signature:
   ```python
   def resolve_classes(
       nodes: list[Node],
       edges: list[Edge],
       path_to_info: dict[str, ModuleInfo],
       dotted_to_path: dict[str, str],
   ) -> tuple[list[Edge], list[Node], list[Unresolved]]:
   ```
   Returns: new INHERITS edges, new external Nodes, unresolved entries.
2. Build internal lookup: `file_to_classes: dict[str, dict[str, Node]]` mapping file path → class name → Node.
3. For each class Node, iterate `node.bases`. For each raw base string:
   - Strip any subscript/generic (e.g. `Generic[T]` → `Generic`, `List[str]` → skip — not a base class, just annotation noise).
   - Look up the base name in the imports of that file (via `path_to_info[file].imports`).
   - Resolve the import to a target file path, then look up that file in `file_to_classes` for the class name.
   - If found → emit `INHERITS` edge to `<file_path>::<ClassName>`.
   - If not found in imports → check if the name is defined in the same file (self-file lookup).
   - If still not found → emit `INHERITS` edge to `external:<base_name>` + ensure external Node exists.
4. Add cycle guard (seen-set of class node IDs) for the field-flattening step below.

**Relevant Context:**
- [`src/docgen/extract/modules.py`](src/docgen/extract/modules.py) — `ModuleInfo`, `ImportRecord`, `dotted_to_path`.
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) — `Node`, `Edge`, `EdgeType.INHERITS`, `NodeType.EXTERNAL`.
- Import resolution pattern established in `modules.py` `_resolve_single_import()`.

**Status:** `[ ] pending`

---

### Sub-task C — Field flattening and `is_pydantic_model` tagging

**Intent:** Using the resolved INHERITS edges from sub-task B, update each class Node with:
- `fields`: own fields + fields from every in-repo ancestor, in MRO order (parents after child; child fields win on name clash).
- `is_pydantic_model`: `True` if any resolved ancestor edge reaches `external:pydantic.BaseModel` (or `external:pydantic.main.BaseModel`).

**Important constraint:** Nodes are frozen dataclasses — they cannot be mutated in place. The function must return new Node objects (using `dataclasses.replace()`).

**Expected Outcomes:**
- `ListOfArticlesInResponse` node has `fields` containing `articles` and `articles_count` (own) with no additional fields from `RWSchema`/`RWModel` (those have no annotated fields in body, only a nested `Config` class).
- `RWModel` node has `is_pydantic_model=True` (direct base is `pydantic.BaseModel`).
- `RWSchema` node has `is_pydantic_model=True` (transitive via `RWModel`).
- `ListOfArticlesInResponse` node has `is_pydantic_model=True` (transitive).
- All class Nodes with in-repo bases that have zero annotated fields pass through unchanged except for `is_pydantic_model`.

**Todo List:**
1. Build a `resolved_inherits: dict[str, list[str]]` mapping class_node_id → list of resolved base node IDs (from the edges produced in sub-task B).
2. Write a recursive helper `_collect_ancestor_fields(node_id, node_map, resolved_inherits, visited)` that walks up the chain (in-repo only, stops at `external:`) and collects `fields` tuples in order.
3. Write `_is_pydantic(node_id, resolved_inherits, visited)` that returns `True` if any ancestor is `external:pydantic.BaseModel` or `external:pydantic.main.BaseModel` (check with `startswith("external:pydantic")`).
4. Iterate all class Nodes and produce updated Nodes via `dataclasses.replace(node, fields=..., is_pydantic_model=...)`.
5. Return the list of updated Nodes; callers replace old Nodes with these in the final graph.

**Relevant Context:**
- `dataclasses.replace()` — Python stdlib, needed for frozen dataclass mutation.
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) `Node.fields` — `tuple[tuple[str,str,str],...]`.
- `ListOfArticlesInResponse` → `RWSchema` → `RWModel` → `pydantic.BaseModel` chain in target.

**Status:** `[ ] pending`

---

### Sub-task D — Public API and integration entry point

**Intent:** Expose a single clean entry point that callers (and eventually the CLI) can call to run class resolution over an already-extracted set of nodes + edges.

**Expected Outcomes:**
- One public function `resolve_all_classes(nodes, edges, path_to_info, dotted_to_path)` that chains sub-tasks B and C.
- Returns `(updated_nodes, new_edges, new_external_nodes, unresolved)` — everything a caller needs to merge into the FactGraph.
- All returned nodes are the updated versions (Pydantic flag set, fields flattened).

**Todo List:**
1. Define `resolve_all_classes()` that calls `resolve_classes()` then the field/pydantic update step.
2. Merge the updated class Nodes back over the original node list (replace by `node.id`).
3. Document the function signature and return types clearly.

**Relevant Context:**
- Architecture.md §2 pipeline: `core extract → adapter extract → facts.json`. This function sits in the "core extract" stage, after `extract_file()` and `build_full_index()`.

**Status:** `[ ] pending`

---

### Sub-task E — Tests

**Intent:** Write `tests/test_classes.py` that exercises all branches of the implementation without touching the real target repo (use temp fixture repos following the pattern in `tests/test_modules.py`).

**Expected Outcomes:**
- At least one test per bullet below passes:
  1. In-repo single-level inheritance: base class in another file → `INHERITS` edge resolves to `<file>::<ClassName>`.
  2. Transitive (2-level) in-repo chain: `C → B → A` — `C.fields` includes `A`'s fields.
  3. External base (`pydantic.BaseModel`) → `INHERITS` edge to `external:pydantic.BaseModel` + external Node created.
  4. `is_pydantic_model=True` propagated transitively.
  5. Cycle guard: `A(B), B(A)` does not hang or crash.
  6. Unresolvable base (name not in imports and not in same file) → `Unresolved` entry emitted, no crash.
  7. Multiple inheritance: fields from both parents merged (child wins on clash).
  8. Integration smoke test against the real `target/` repo: `ListOfArticlesInResponse` has `is_pydantic_model=True`.

**Todo List:**
1. Create `tests/test_classes.py`.
2. Write a `make_class_fixture(tmpdir, ...)` helper that creates small repos with class hierarchies in temp dirs.
3. Write one test function per outcome above.
4. For the real-repo smoke test, use the existing `docgen.toml` + `walk_repo` + `build_full_index` + `extract_file` pipeline then call `resolve_all_classes`.

**Relevant Context:**
- Pattern from [`tests/test_modules.py`](tests/test_modules.py) — `create_fixture_repo(tmpdir)` temp dir pattern.
- Pattern from [`tests/test_core.py`](tests/test_core.py) — `extract_file(path, root)` call pattern.

**Status:** `[ ] pending`

---

## Dependency Order

```
Sub-task A (remove core.py stubs)
    ↓
Sub-task B (resolve_classes — emit INHERITS edges)
    ↓
Sub-task C (field flattening + is_pydantic_model)
    ↓
Sub-task D (public API / entry point)
    ↓
Sub-task E (tests)
```

All sub-tasks are sequential. Sub-task E validates A–D together.

---

## Files to Touch

| File | Change |
|---|---|
| `src/docgen/extract/core.py` | Remove stub INHERITS edge loop (sub-task A) |
| `src/docgen/extract/classes.py` | Full implementation (sub-tasks B, C, D) |
| `tests/test_classes.py` | New file (sub-task E) |

No other files require changes.
