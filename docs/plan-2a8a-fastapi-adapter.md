# Plan: Task 2a.8a — FastAPI Adapter: Routes via Introspection

## Top-Level Overview

**Goal:** Implement `src/docgen/extract/adapters/fastapi.py` so that after `docgen extract` runs, the fact graph includes route nodes, HANDLES edges (route→handler function), and REQUEST_MODEL/RESPONSE_MODEL edges — extracted by importing the FastAPI app in a subprocess and calling `app.openapi()`.

**Done when:** The adapter runs on the dev repo and its extracted route set is consistent with `eval/ground_truth.json` (19 routes, correct methods and paths). This is a **consistency check, not a graded evaluation** (both the adapter and the ground truth read the same running app).

**Fallback:** If the subprocess import fails (missing env, import error, timeout), the adapter logs a notice to `unresolved` and returns empty — the rest of the fact graph is unaffected.

**Scope:** `adapters/base.py` (Adapter protocol), `adapters/fastapi.py` (implementation), update `cli.py` to call the adapter, new tests. No changes to `schema.py` or `store.py`.

---

## Design Decisions

- **Extraction method:** `app.openapi()` — richer than iterating `app.routes` directly; gives status codes, operation IDs, request/response model names in one call.
- **Subprocess approach:** A small Python script is written to a temp file and executed via the target venv's Python (`target/.venv/Scripts/python.exe` on Windows, `target/.venv/bin/python` on Linux). The script imports the app, calls `app.openapi()`, and writes the result as JSON to stdout.
- **Dummy env vars (hardcoded):** `SECRET_KEY=dummy-secret-for-docgen`, `DATABASE_URL=postgresql://localhost/dummy`, `MAX_CONNECTIONS_COUNT=1`, `MIN_CONNECTIONS_COUNT=1`. No config needed.
- **Timeout:** 30 seconds — enough for any reasonable FastAPI app to import.
- **Handler name resolution:** The subprocess script is enriched to output `route.endpoint.__name__` per route alongside the OpenAPI dict. This gives an exact function name (e.g. `list_articles`) with no ambiguity — no operationId prefix-matching needed.
- **Handler function node ID:** built as `<source_root>/<handler_file>::<func_name>` — we get the file by matching the handler function name against already-extracted FUNCTION nodes.
- **ROUTE node ID scheme:** `route:METHOD /full/path` (per architecture.md §5 ID scheme).
- **Model resolution:** response/request model names from OpenAPI `$ref` strings (`#/components/schemas/ArticleInResponse`) → stripped to `ArticleInResponse` → matched against CLASS nodes in the fact graph by name.

---

## Sub-Tasks

---

### Sub-task A — `adapters/base.py`: Adapter protocol

**Intent:** Define a minimal `Adapter` protocol so the CLI can call any adapter uniformly.

**Expected Outcomes:**
- A `Protocol` class `Adapter` with one method: `extract(nodes, edges, config, repo_root) -> AdapterResult`.
- `AdapterResult` is a dataclass holding `(nodes, edges, unresolved)` — the new facts produced.
- `base.py` has no external dependencies beyond stdlib.

**Todo List:**
1. Define `AdapterResult(nodes, edges, unresolved)` dataclass.
2. Define `Adapter(Protocol)` with `extract(...)` signature.

**Relevant Context:**
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) — `Node`, `Edge`, `Unresolved`.

**Status:** `[ ] pending`

---

### Sub-task B — Subprocess runner

**Intent:** A private helper that spawns the target venv's Python, imports the FastAPI app, calls `app.openapi()`, and returns the JSON result (or raises on failure).

**Expected Outcomes:**
- `_run_app_introspection(app_import_path, repo_root, source_root, timeout=30)` returns the parsed OpenAPI dict.
- On `subprocess.TimeoutExpired`, `CalledProcessError`, or JSON decode error → raises a specific `IntrospectionError` exception.
- The subprocess script sys.path-prepends `repo_root/source_root` so `import app.main` resolves.
- Dummy env vars injected; existing env vars inherited.
- Works on both Windows and Linux (venv path selection).

**Todo List:**
1. Write the inline Python script (as a string) that the subprocess executes:
   ```python
   import sys, json
   sys.path.insert(0, "<repo_root>/<source_root>")
   module_path, attr = "<app_import_path>".rsplit(":", 1)
   import importlib
   mod = importlib.import_module(module_path)
   app = getattr(mod, attr)
   print(json.dumps(app.openapi()))
   ```
2. Write `_run_app_introspection(app_import_path, repo_root, source_root, timeout)`:
   - Detect venv Python path (`target/.venv/Scripts/python.exe` or `target/.venv/bin/python`).
   - If no venv found, fall back to `sys.executable`.
   - Build env dict: inherit os.environ, add dummy vars.
   - Run via `subprocess.run([python, "-c", script], capture_output=True, timeout=timeout, env=env)`.
   - Parse stdout as JSON; raise `IntrospectionError` on any failure.

**Relevant Context:**
- Python subprocess docs — `subprocess.run` with `env=`, `capture_output=True`, `timeout=`.
- `target/.venv/Scripts/python.exe` (Windows), `target/.venv/bin/python` (Linux).

**Status:** `[ ] pending`

---

### Sub-task C — OpenAPI → fact graph mapping

**Intent:** Parse the OpenAPI dict returned by the subprocess and produce `Node` (ROUTE) and `Edge` (HANDLES, REQUEST_MODEL, RESPONSE_MODEL) objects.

**Expected Outcomes:**
- One `Node(type=ROUTE)` per route with correct `id`, `method`, `full_path`, `name`, `status_code`.
- One `HANDLES` edge per route pointing to the matched FUNCTION node (matched by function name from operationId against existing FUNCTION nodes' `node.name`).
- `REQUEST_MODEL` / `RESPONSE_MODEL` edges pointing to matched CLASS nodes (matched by schema name against `node.name`).
- Unmatched handlers and models logged as `Unresolved` entries (not crashes).

**How function name is extracted:**
- The subprocess script outputs a mapping `{"path:method": {"handler": endpoint.__name__, ...}}` alongside the OpenAPI spec. This gives the exact Python function name (e.g. `list_articles`) per route — no ambiguity, no operationId parsing.

**How route status code is extracted:**
- OpenAPI `paths[path][method]["responses"]` — the first 2xx key (e.g. `"201"`, `"200"`) gives the status code.

**Todo List:**
1. Write `_extract_status_code(responses_dict)` — find first 2xx key, return int.
2. Write `_extract_schema_name(ref_or_schema)` — strip `#/components/schemas/` prefix from `$ref` strings.
3. Write `_openapi_to_facts(openapi_dict, handler_map, all_nodes)` that:
   - Iterates `openapi_dict["paths"]` → per-path, per-method entry.
   - Builds ROUTE node, HANDLES edge, REQUEST/RESPONSE_MODEL edges.
   - Returns `(route_nodes, edges, unresolved)`.

**Relevant Context:**
- [`src/docgen/facts/schema.py`](src/docgen/facts/schema.py) — `NodeType.ROUTE`, `EdgeType.HANDLES`, `EdgeType.REQUEST_MODEL`, `EdgeType.RESPONSE_MODEL`.
- Ground truth: `eval/ground_truth.json` — 19 routes with paths and methods to cross-check against.

**Status:** `[ ] pending`

---

### Sub-task D — Public `extract()` entry point + fallback

**Intent:** Wire sub-tasks B and C into the `AdapterResult extract(...)` function, with the fallback logic if introspection fails.

**Expected Outcomes:**
- `extract(nodes, edges, config, repo_root)` returns an `AdapterResult`.
- On `IntrospectionError`: appends one `Unresolved(what="adapter_import_failed", ...)` entry, returns empty nodes/edges (no crash, rest of graph intact).
- On success: returns route nodes + HANDLES + REQUEST/RESPONSE_MODEL edges.

**Todo List:**
1. Implement `extract()` in `adapters/fastapi.py` — try introspection, catch `IntrospectionError`, fall back to empty result + unresolved notice.
2. Print a stderr notice when falling back: `"WARNING: FastAPI adapter import failed — route facts omitted"`.

**Status:** `[ ] pending`

---

### Sub-task E — Wire adapter into `cli.py`

**Intent:** Call the FastAPI adapter in `_run_extract()` when `config.adapter_name == "fastapi"`, merging the adapter's output into the fact graph before writing.

**Expected Outcomes:**
- `_run_extract` calls the adapter after `scan_for_unresolved`.
- Route nodes and edges added to `all_nodes` / `all_edges`.
- Adapter unresolved entries added to `all_unresolved`.
- If `adapter_name != "fastapi"` or `adapter_name == "none"`, adapter step is skipped silently.

**Todo List:**
1. In `cli.py` `_run_extract`, after `scan_for_unresolved`, add:
   ```python
   if config.adapter_name == "fastapi":
       from docgen.extract.adapters.fastapi import extract as fastapi_extract
       adapter_result = fastapi_extract(all_nodes, all_edges, config, repo_root)
       all_nodes.extend(adapter_result.nodes)
       all_edges.extend(adapter_result.edges)
       all_unresolved.extend(adapter_result.unresolved)
   ```

**Status:** `[ ] pending`

---

### Sub-task F — Consistency check + tests

**Intent:** Write a test that runs the full adapter on the real target repo and verifies the extracted route set matches `eval/ground_truth.json`.

**Expected Outcomes:**
1. `_run_app_introspection` on a trivial FastAPI fixture returns a valid OpenAPI dict.
2. `_openapi_to_facts` on a minimal OpenAPI dict with 1 route produces 1 ROUTE node + 1 HANDLES edge.
3. Introspection failure (bad app path) → `IntrospectionError` raised (not crash).
4. `extract()` on failure → returns `AdapterResult` with 1 unresolved, 0 nodes/edges.
5. **Consistency check (integration):** Run `extract()` on real target — compare extracted route `(method, path)` pairs against ground truth. All 19 ground-truth routes must appear.

**Todo List:**
1. Create `tests/test_fastapi_adapter.py`.
2. Write a small fixture FastAPI app in a temp dir for unit tests.
3. Write the 5 tests above.
4. For test 5: load `eval/ground_truth.json`, run the real adapter, assert all 19 `(method, path)` pairs present.

**Relevant Context:**
- [`eval/ground_truth.json`](eval/ground_truth.json) — 19 routes as answer key.
- [`target/.venv`](target/.venv) — must exist for the real-repo test.

**Status:** `[ ] pending`

---

## Dependency Order

```
Sub-task A (base.py protocol)
    ↓
Sub-task B (subprocess runner)
    ↓
Sub-task C (OpenAPI → facts mapping)
    ↓
Sub-task D (public extract() + fallback)
    ↓
Sub-task E (wire into cli.py)
    ↓
Sub-task F (tests + consistency check)
```

---

## Files to Touch

| File | Change |
|---|---|
| `src/docgen/extract/adapters/base.py` | Adapter protocol + AdapterResult dataclass |
| `src/docgen/extract/adapters/fastapi.py` | Full implementation |
| `src/docgen/cli.py` | Wire adapter into _run_extract |
| `tests/test_fastapi_adapter.py` | New — 5 tests incl. consistency check |

No changes to `schema.py`, `store.py`, or other extract modules.
