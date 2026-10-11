# Plan: Tasks 2a.3b + 2a.6b — Class Method Extraction and Method Body Facts

## Top-Level Overview

**Two tightly coupled tasks:**

**2a.3b (core.py):** Extend `extract_file()` to extract class methods as `FUNCTION` nodes, with:
- `id = "<file>::<ClassName>::<method_name>"`
- `parent_class` field set to the class node's id (e.g. `"<file>::<ClassName>"`)
- `CONTAINS` edge from the class node to the method node
- Decorator-inclusive span, `hash_struct`, `hash_source` computed the same way as module-level functions
- `DEPENDS_ON` edges from `Depends(...)` in parameters and decorators — same as module-level

Additionally, the **class `hash_struct`** is updated to include each method's `hash_struct`, so a method signature change marks the class node stale (and thus triggers re-summarisation of the class).

The **class `hash_source`** is narrowed to cover only the class header — decorators, `class` line, bases, docstring, and class-level `AnnAssign` fields — **not** method bodies (which belong to their own method nodes' `hash_source`).

**2a.6b (bodies.py):** Extend `extract_body_facts()` to also process `FUNCTION` nodes that have a non-empty `parent_class` field (class methods), extracting their `RAISES` and `CALLS` edges the same way as module-level functions. The only new plumbing needed is the AST lookup: methods live inside a `ClassDef` body, so the per-file AST cache must be extended to also index method nodes by `(class_name, method_name)`.

**Done when:**
- A class with methods produces method nodes with `parent_class` set and `CONTAINS` edges from the class node.
- Editing a method signature changes the class's `hash_struct`.
- Editing only a method body does NOT change the class's `hash_struct` (only the method's own `hash_source`).
- A `raise` inside a class method produces a `RAISES` edge from the method node.

---

## Design Decisions

- **Method node ID:** `<file>::<ClassName>::<method_name>`. Exactly matches the ID scheme in `architecture.md` §5: `"path/to/file.py::Class::method"`.
- **Class `hash_struct`:** The synthetic AST for the class body now includes (a) field annotations as before, and (b) the `hash_struct` string of each method as a synthetic `ast.Constant` node. This makes the class hash sensitive to method signature changes without duplicating the full method AST.
- **Class `hash_source`:** Computed as a new token span: from the decorator start line to the line before the first method starts. If there are no methods, it covers the whole class body. If the class has no preamble (only methods), the span is just the `class` header line.
- **Method `hash_source`:** Computed with `_hash_source_span(source, decorator_start, end_lineno)` — same as module-level functions today.
- **`_make_synthetic_ast_for_hash` for classes:** Updated to accept an optional `method_hash_structs: list[str]` parameter so callers can inject the pre-computed method hashes into the synthetic body.
- **bodies.py AST cache:** Extended from `dict[str, dict[str, FunctionDef]]` (top-level only) to `dict[str, dict[str, dict[str, FunctionDef] | FunctionDef]]`. Practically: a two-level dict: `file_path → {"__top__": {func_name: node}, class_name: {method_name: node}}`.
- **No changes to `schema.py`:** `parent_class` already exists as a field on `Node`.
- **No changes to `classes.py`:** Method nodes are `FUNCTION` type, not `CLASS` — class resolution is unchanged.

---

## Sub-Tasks

---

### Task 2a.3b — Sub-task A: Update class hash computation

**Intent:** Change `_make_class_node` so that its `hash_struct` includes method signatures and its `hash_source` covers only the class header.

**Expected Outcomes:**
- `hash_struct` of a class changes when any method's signature (or decorator) changes.
- `hash_struct` does NOT change when a method body comment or blank line changes.
- `hash_source` of a class changes when the class header changes (bases, class-level fields, docstring).
- `hash_source` does NOT change when a method body changes.

**Todo List:**
1. In `extract_file()`, when processing a `ClassDef`, first collect all method `ast.FunctionDef`/`ast.AsyncFunctionDef` nodes from `item.body`.
2. For each method, compute its `hash_struct` using `_hash_struct_node(method_ast)`.
3. Update `_make_synthetic_ast_for_hash` for `ast.ClassDef`: add each method's `hash_struct` string as a `ast.Constant` node in the synthetic body (after field annotations). This makes the class synthetic AST sensitive to method signature changes.
4. For class `hash_source`: compute the header span as lines from `decorator_start` to `(first_method.lineno - 1)` if any methods exist, otherwise the whole class body span. Use `_hash_source_span(source, header_start, header_end)`.
5. Pass the method hash_structs into `_make_class_node` (new parameter `method_hash_structs: list[str]`).

**Relevant Context:**
- [`src/docgen/extract/core.py`](src/docgen/extract/core.py) `_make_synthetic_ast_for_hash` lines 58-80 — the class synthetic AST builder.
- [`src/docgen/extract/core.py`](src/docgen/extract/core.py) `_make_class_node` lines 211-264 — where `hash_struct` and `hash_source` are currently computed.

**Status:** `[ ] pending`

---

### Task 2a.3b — Sub-task B: Extract method nodes and edges

**Intent:** Inside the `ClassDef` processing loop in `extract_file()`, iterate `item.body` to extract each method as a `FUNCTION` node with `parent_class` set, and emit a `CONTAINS` edge from the class node.

**Expected Outcomes:**
- A class with 3 methods produces 3 `FUNCTION` nodes with `id = "<file>::<ClassName>::<method_name>"`.
- Each method node has `parent_class = "<file>::<ClassName>"`.
- Each method node has its own `hash_struct` (from its signature/decorators) and `hash_source` (from its full span including decorators).
- `CONTAINS` edge from `cls_node.id` → `method_node.id` for each method.
- `DEPENDS_ON` edges for `Depends(...)` in method parameters and decorators.
- Nested class definitions inside a class body are ignored (out of scope).

**Todo List:**
1. Add a helper `_make_method_node(method_ast, source, mid, class_id, class_name, is_async)` that:
   - Computes `method_id = f"{mid}::{class_name}::{method_ast.name}"`.
   - Computes decorator-inclusive span, `hash_struct`, `hash_source` (exactly as `_make_function_node` does).
   - Sets `parent_class = class_id`.
   - Returns a `Node(type=NodeType.FUNCTION, ...)`.
2. In `extract_file()`, after building `cls_node`, iterate `item.body` for `FunctionDef` / `AsyncFunctionDef` items:
   - Call `_make_method_node(...)` for each.
   - Append to `nodes`.
   - Append `CONTAINS` edge from `cls_node.id` → `method_node.id`.
   - Append `DEPENDS_ON` edges from `_collect_depends_from_params` and `_collect_decorator_depends`.

**Relevant Context:**
- [`src/docgen/extract/core.py`](src/docgen/extract/core.py) `_make_function_node` lines 163-208 — the template to follow.
- `_collect_depends_from_params` and `_collect_decorator_depends` already exist and work on any `FunctionDef`.

**Status:** `[ ] pending`

---

### Task 2a.3b — Sub-task C: Tests

**Intent:** Write `tests/test_core_methods.py` (or extend `tests/test_core.py`) verifying the new behaviour.

**Expected Outcomes:**
1. A class with one method → 1 `FUNCTION` node with `parent_class` set, 1 `CONTAINS` edge from class to method.
2. Editing a method signature → class `hash_struct` changes.
3. Editing a method comment → class `hash_struct` unchanged, method `hash_source` changes.
4. Editing a class-level field → class `hash_source` changes.
5. Editing only a method body → class `hash_source` unchanged.
6. Method with `Depends(...)` → `DEPENDS_ON` edge from method node.
7. Method node id has three parts: `<file>::<Class>::<method>`.

**Todo List:**
1. Create `tests/test_core_methods.py` with the 7 test scenarios above.

**Status:** `[ ] pending`

---

### Task 2a.6b — Sub-task D: Extend bodies.py AST cache for methods

**Intent:** The current per-file AST cache in `extract_body_facts()` only indexes top-level functions. Extend it to also index class methods, so method `FUNCTION` nodes can have their AST looked up by `(class_name, method_name)`.

**Expected Outcomes:**
- For a `FUNCTION` node with `parent_class = "<file>::ClassName"`, `_get_func_ast` correctly returns the method's `ast.FunctionDef`.
- Module-level function lookup is unchanged.

**Todo List:**
1. Change the AST cache structure to: `dict[str, tuple[dict[str, FuncNode], dict[str, dict[str, FuncNode]]]]` — i.e. per file: `(top_level_funcs, {class_name: {method_name: ast_node}})`.
2. When parsing a file for the cache, also iterate `ast.ClassDef` items in `tree.body`, and for each, iterate `classdef.body` for method nodes.
3. In `extract_body_facts()`, when processing a `FUNCTION` node:
   - If `node.parent_class` is empty → top-level lookup (existing behaviour).
   - If `node.parent_class` is non-empty → parse the class name from `node.parent_class` (last component after `::`) and look up in the methods dict.

**Status:** `[ ] pending`

---

### Task 2a.6b — Sub-task E: Process method nodes in extract_body_facts

**Intent:** Remove the "module-level functions only" restriction. The RAISES/CALLS extraction logic is identical for methods — no special casing needed once the AST is found.

**Expected Outcomes:**
- A `raise` inside a class method produces a `RAISES` edge from the method node id.
- Calls inside a class method produce `CALLS` edges from the method node id.
- The module docstring and `bodies.py` docstring are updated to reflect methods are now included.

**Todo List:**
1. In `extract_body_facts()`, remove the comment "Only module-level functions are processed".
2. Update the `_get_func_ast` lookup to use the two-level cache for methods (sub-task D).
3. No changes to `_extract_raises` or `_extract_calls` — they operate on the AST node directly and are already method-agnostic.
4. Update the module docstring.

**Status:** `[ ] pending`

---

### Task 2a.6b — Sub-task F: Tests

**Intent:** Write `tests/test_bodies_methods.py` verifying method body facts are extracted.

**Expected Outcomes:**
1. `raise HTTPException(...)` inside a class method → `RAISES` edge from `<file>::<Class>::<method>`.
2. A call inside a class method → `CALLS` edge from the method node.
3. Module-level functions still produce edges as before (regression).
4. Integration smoke: a repository class method with a known raise produces the correct RAISES edge.

**Todo List:**
1. Create `tests/test_bodies_methods.py` with the 4 tests above.

**Status:** `[ ] pending`

---

## Dependency Order

```
2a.3b Sub-task A (update class hash computation)
    ↓
2a.3b Sub-task B (extract method nodes + edges)
    ↓
2a.3b Sub-task C (tests for core.py changes)
    ↓
2a.6b Sub-task D (extend bodies.py AST cache)
    ↓
2a.6b Sub-task E (process method nodes)
    ↓
2a.6b Sub-task F (tests for bodies.py changes)
```

All sub-tasks are sequential. Sub-task B depends on A (class hash must be correct before method nodes are built). Sub-task D depends on C (tests confirm core.py is stable before extending bodies.py).

---

## Files to Touch

| File | Change |
|---|---|
| `src/docgen/extract/core.py` | `_make_synthetic_ast_for_hash` (class branch), `_make_class_node`, new `_make_method_node`, `extract_file` (method loop) |
| `src/docgen/extract/bodies.py` | Extended AST cache, remove module-level-only restriction, update docstring |
| `tests/test_core_methods.py` | New file — 7 tests |
| `tests/test_bodies_methods.py` | New file — 4 tests |

No changes to `schema.py`, `store.py`, `classes.py`, or `modules.py`.

---

## Key Non-Obvious Constraints

- **`hash_source` span for class header:** The "header" ends at the line *before* the first method definition. If `class Foo:\n    x: int = 0\n    def foo(self): ...` — the header span is lines 1-2 (the `class Foo:` line and `x: int = 0`). If a class has no fields and only methods, the header is just the `class` line itself.
- **Frozen dataclass replacement in classes.py:** `resolve_all_classes` calls `dataclasses.replace()` on class nodes. Since method nodes are `FUNCTION` type (not `CLASS`), they pass through `resolve_all_classes` unchanged — no change needed there.
- **bodies.py `node.name` lookup:** Method nodes have `node.name = "method_name"` (just the method name, not the class-qualified name). The AST cache lookup uses `parent_class` to find the class, then `node.name` to find the method within it — this is why the two-level cache structure is needed.
- **`parent_class` value:** Set to the class node id (`"<file>::<ClassName>"`), not just the class name. This is a stable, unambiguous reference. To extract the class name for AST lookup, split on `::` and take the last component.
