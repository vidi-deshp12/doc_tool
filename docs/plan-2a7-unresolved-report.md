# Plan: Task 2a.7 — Unresolved Report

## Top-Level Overview

**Goal:** Two deliverables:

1. **Detection** — add detection for three entry types not yet emitted anywhere in the pipeline:
   - `star_import`: `from x import *` (already recorded in `ImportRecord.is_star` but never emitted as `Unresolved`)
   - `dynamic_import`: `__import__(...)`, `importlib.import_module(...)`, or any call whose callee is `importlib.*`
   - `getattr_dynamic`: `getattr(obj, name)` where `name` is not a string literal (runtime name lookup, statically unknowable)

2. **CLI `extract` command** — implement the full extraction pipeline in `cli.py`:
   - Walk repo → `extract_file` → `build_full_index` → `resolve_all_classes` → `extract_body_facts`
   - Collect all `Unresolved` entries from every stage
   - Write `facts.json` to the configured output dir
   - Print a linter-style unresolved summary to stdout (one line per entry, sorted by `where`), followed by a count line

**Scope:** One new file (`extract/unresolved.py` for the detection pass), changes to `cli.py`, new tests. No changes to `schema.py` or `store.py`.

**Non-goals:** Detecting every possible dynamic access pattern (metaclasses, `vars()`, `locals()`, `eval()`), emitting `unresolved-name` for every undefined call target (that would flood the report), resolving star-import names.

---

## Design Decisions

- **Star-import detection lives in a new `extract/unresolved.py` scan pass**, not in `modules.py`. `modules.py` already records `is_star=True` on `ImportRecord`; `unresolved.py` reads that flag and emits the `Unresolved` entry. This avoids modifying `modules.py`.
- **Dynamic-import and getattr detection** also live in `unresolved.py` via `ast.walk` over each file's AST.
- **`where` format:** `"<file>:<line>"` for all new entry types (consistent with existing entries).
- **`what` values (fixed strings):** `"star_import"`, `"dynamic_import"`, `"getattr_dynamic"` — easy to grep.
- **CLI output format:**
  ```
  WARN [star_import] target/app/foo.py:12 — from os.path import *
  WARN [dynamic_import] target/app/bar.py:5 — __import__('x')
  ...
  3 unresolved entries (1 star_import, 1 dynamic_import, 1 getattr_dynamic)
  ```
  Sorted by `where` (alphabetically, which approximates file+line order).
- **CLI exit code:** 0 even if there are unresolved entries (exit 1 is reserved for `check` / drift detection per architecture.md §8). The summary is informational.
- **`facts.json` written to `<output_dir>/facts.json`** where `output_dir` comes from `config.output_dir`.

---

## Sub-Tasks

---

### Sub-task A — `extract/unresolved.py`: detection pass

**Intent:** A single function `scan_for_unresolved(module_paths, path_to_info, repo_root)` that scans all files for the three new entry types and returns a list of `Unresolved` entries.

**Expected Outcomes:**
- `from os import *` in a file → `Unresolved(what="star_import", why="from os import *", where="<file>:<line>")`.
- `__import__("x")` in a function body → `Unresolved(what="dynamic_import", why="__import__('x')", where="<file>:<line>")`.
- `importlib.import_module("x")` → `Unresolved(what="dynamic_import", why="importlib.import_module('x')", where="<file>:<line>")`.
- `getattr(obj, name_var)` where `name_var` is not a string literal → `Unresolved(what="getattr_dynamic", why="getattr(obj, name_var)", where="<file>:<line>")`.
- `getattr(obj, "literal")` → **not flagged** (static name, no ambiguity).
- Each of the three pattern types has a helper: `_scan_star_imports`, `_scan_dynamic_imports`, `_scan_getattr`.

**Todo List:**
1. Create `src/docgen/extract/unresolved.py`.
2. `_scan_star_imports(path_to_info)` — iterate `ModuleInfo.imports`, flag any `ImportRecord.is_star == True`.
3. `_scan_dynamic_imports(file_path, tree)` — `ast.walk` looking for:
   - `ast.Call` where `ast.unparse(call.func) == "__import__"` 
   - `ast.Call` where `ast.unparse(call.func).startswith("importlib.")` (e.g. `importlib.import_module`)
4. `_scan_getattr(file_path, tree)` — `ast.walk` for `ast.Call` where `ast.unparse(call.func) == "getattr"` and the second argument is NOT an `ast.Constant` (i.e. the attribute name is dynamic).
5. `scan_for_unresolved(module_paths, path_to_info, repo_root)` — parses each file once (re-use the source already accessible via `repo_root / file_path`), calls the three helpers, returns a sorted flat list of `Unresolved`.

**Relevant Context:**
- [`src/docgen/extract/modules.py`](src/docgen/extract/modules.py) — `ModuleInfo`, `ImportRecord.is_star`.
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) — `Unresolved(what, why, where)`.

**Status:** `[ ] pending`

---

### Sub-task B — `cli.py`: implement `docgen extract`

**Intent:** Replace the `NotImplementedError` stub in `cli.py` with a real `extract` subcommand that runs the full pipeline (no adapter yet) and prints the unresolved summary.

**Expected Outcomes:**
- `docgen extract` (from the project root, with `docgen.toml` present) runs to completion.
- Writes `<output_dir>/facts.json` with nodes, edges, and all unresolved entries.
- Prints to stdout:
  - One `WARN [<type>] <where> — <what>` line per unresolved entry, sorted by `where`.
  - A final summary line: `N unresolved entries (X type_a, Y type_b, ...)`.
  - If zero entries: `0 unresolved entries`.
- Exits 0 in all cases (unresolved entries are warnings, not failures).
- The other subcommands (`summarize`, `render`, `check`, `update`, `eval`) still raise `NotImplementedError`.

**Pipeline order in `extract`:**
1. `load_config(docgen.toml)`
2. `walk_repo(config)` → `module_paths`
3. For each path: `extract_file(path, repo_root)` → accumulate nodes, edges, unresolved
4. `build_module_index(module_paths, repo_root, source_root)` → `dotted_to_path, path_to_info`
5. `resolve_imports(dotted_to_path, path_to_info, repo_root, source_root)` → more edges + unresolved
6. `resolve_all_classes(nodes, edges, path_to_info, dotted_to_path)` → updated nodes + more edges + unresolved
7. `extract_body_facts(nodes, edges, path_to_info, dotted_to_path, repo_root)` → raises + calls edges + new externals
8. `scan_for_unresolved(module_paths, path_to_info, repo_root)` → star/dynamic/getattr unresolved
9. Assemble `FactGraph(nodes=..., edges=..., unresolved=...)` (merge all unresolved from all stages)
10. `write_facts(graph, output_dir/facts.json)`
11. Print unresolved summary

**Todo List:**
1. In `cli.py`: add `--config` argument to the `extract` subparser (default: `"docgen.toml"`).
2. Write `_run_extract(args)` function that executes steps 1–11.
3. Write `_print_unresolved_summary(unresolved)` that formats and prints the linter-style output.
4. Dispatch `extract` to `_run_extract` instead of `NotImplementedError`.
5. All other subcommands remain `NotImplementedError`.

**Relevant Context:**
- [`src/docgen/config.py`](src/docgen/config.py) — `load_config()`.
- [`src/docgen/walker.py`](src/docgen/walker.py) — `walk_repo()`.
- [`src/docgen/extract/core.py`](src/docgen/extract/core.py) — `extract_file()`.
- [`src/docgen/extract/modules.py`](src/docgen/extract/modules.py) — `build_module_index()`, `resolve_imports()`.
- [`src/docgen/extract/classes.py`](src/docgen/extract/classes.py) — `resolve_all_classes()`.
- [`src/docgen/extract/bodies.py`](src/docgen/extract/bodies.py) — `extract_body_facts()`.
- [`src/docgen/facts/store.py`](src/docgen/facts/store.py) — `write_facts()`.
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) — `FactGraph`, `NodeType.EXTERNAL`.

**Status:** `[ ] pending`

---

### Sub-task C — Tests

**Intent:** Write `tests/test_unresolved.py` covering the detection pass and `tests/test_cli_extract.py` covering the CLI command.

**Expected Outcomes:**
1. `scan_for_unresolved` on a fixture with `from os import *` → one `star_import` entry.
2. `scan_for_unresolved` on a fixture with `__import__("x")` → one `dynamic_import` entry.
3. `scan_for_unresolved` on a fixture with `importlib.import_module("y")` → one `dynamic_import` entry.
4. `scan_for_unresolved` on a fixture with `getattr(obj, var)` → one `getattr_dynamic` entry.
5. `scan_for_unresolved` on a fixture with `getattr(obj, "literal")` → **no** entry (static name).
6. `scan_for_unresolved` on a clean fixture with none of the above → empty list.
7. CLI `extract` subcommand runs end-to-end on a small fixture repo, writes `facts.json`, and the JSON contains a `"unresolved"` array.
8. CLI `extract` prints at least the count line to stdout.
9. Integration: `scan_for_unresolved` on real `target/` repo returns a list (possibly empty — target is clean, but call must not crash).

**Todo List:**
1. Create `tests/test_unresolved.py` — tests 1–6 and 9, using the `_write` / temp-dir pattern.
2. Create `tests/test_cli_extract.py` — tests 7–8, invoking `main()` via `subprocess` or by patching `sys.argv` and capturing stdout.

**Relevant Context:**
- Pattern from [`tests/test_bodies.py`](tests/test_bodies.py) — `_write`, temp-dir fixture, `build_module_index`.
- For CLI tests: use `subprocess.run(["python", "-m", "docgen", "extract", "--config", str(toml_path)])` or call `main()` directly with `capsys`.

**Status:** `[ ] pending`

---

## Dependency Order

```
Sub-task A (scan_for_unresolved in extract/unresolved.py)
    ↓
Sub-task B (cli.py extract command — uses A)
    ↓
Sub-task C (tests for A and B)
```

---

## Files to Touch

| File | Change |
|---|---|
| `src/docgen/extract/unresolved.py` | New file — detection pass |
| `src/docgen/cli.py` | Implement `extract` subcommand |
| `tests/test_unresolved.py` | New file |
| `tests/test_cli_extract.py` | New file |

No other files require changes.
