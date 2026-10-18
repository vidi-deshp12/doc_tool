# Plan: Phase 3 — Renderers and Freshness

## Goal

Implement `docgen render`, `docgen check`, and `docgen update` so the pipeline
goes end-to-end from `facts.json` + `summaries.json` → `generated/pages/` →
drift detection → incremental update.

**Done when:**
- `docgen render` produces markdown pages under `generated/pages/`
- `manifest.json` maps every page to the fact hashes it was built from
- `docgen check` exits 0 on a fresh run, exits 1 after a code edit, naming stale pages
- `docgen check --fresh` re-extracts first, then checks
- `docgen update` re-renders only stale pages and exits 0
- Harmless edits (comment/format) never trigger drift
- The 4 freshness gate tests pass (task 3.5)

---

## Sub-task 3.1 + 3.2 — Renderers + Manifest [pending]

**Intent:** Write the three page types and the manifest in one pass (they share
the render command). All rendering is a pure function of `facts.json` +
`summaries.json` — no I/O beyond reading those two files and writing markdown.

### Pages produced

| Page file | Content |
|---|---|
| `generated/pages/index.md` | Architecture overview: system summary + package summaries + Mermaid package diagram |
| `generated/pages/<mirrored-path>.md` | One file per MODULE node, mirroring the source directory structure |
| `generated/pages/api.md` | Enriched API endpoint table |

### Mermaid diagram (`mermaid.py`)

Show only **package→package** CONTAINS edges — gives ≤16 nodes on the target
repo, well under any readability limit. Module detail belongs on module pages.
No truncation logic.

Format: `flowchart LR`. Node label = last path component of the package id
(`target/app/db` → `db`). No module nodes in this diagram.

### Module pages (`markdown.py`)

**File path:** Mirror the source directory structure under `generated/pages/`.
`target/app/api/dependencies/articles.py` →
`generated/pages/target/app/api/dependencies/articles.md`.

**Content structure:**
```
# articles          ← last path component, .py stripped
<module summary>

## ClassName
<class summary>
| Field | Type | Default |
|---|---|---|

### method_name
<method summary>

## function_name
<function summary>

> **Raises:** ...   ← from RAISES edges, inline
> **FastAPI deps:** ...  ← from DEPENDS_ON edges, inline
```

Strip `.py` from the `#` heading. Use `_(no summary yet)_` when a summary is
absent. No `<details>` blocks — they don't render in all Markdown renderers.

### API table (`api_table.py`)

Markdown table: `Method | Path | Status | Handler | FastAPI Deps | Request model | Response models`

- Column name "FastAPI Deps" (not "Dependencies" — avoids ambiguity with Python
  package dependencies). Values: DEPENDS_ON targets of the handler function.
- Handler: relative Markdown link to the handler's mirrored module page.
- Request model / Response models: class names from REQUEST_MODEL / RESPONSE_MODEL
  edges. Many rows will be blank (facts gap, not rendering bug).
- Rows sorted by (path, method) for deterministic output.

### Manifest schema (`manifest.py`)

Keys are **repo-root-relative POSIX** paths, matching `facts.json` conventions:

```json
{
  "pages": {
    "generated/pages/index.md": {
      "fact_ids": ["system", "target/app", "target/app/db"],
      "hashes": {
        "target/app": {"hash_struct": "abc...", "hash_source": "def..."},
        "target/app/db": {"hash_struct": "...", "hash_source": "..."}
      }
    },
    "generated/pages/target/app/db/repositories.md": { ... }
  }
}
```

`manifest.py` exports: `PageRecord` dataclass, `build_manifest`,
`write_manifest`, `read_manifest`. Written with `sort_keys=True, indent=2`.
`hash_struct` = drift signal. `hash_source` = re-summarization trigger.

### CLI
`docgen render [--config docgen.toml]` — reads `facts.json` + `summaries.json`,
writes pages + `manifest.json`, prints count to stderr.

### Files
`src/docgen/render/markdown.py`, `src/docgen/render/mermaid.py`,
`src/docgen/render/api_table.py`, `src/docgen/check/manifest.py`,
`src/docgen/cli.py`

### Tests

**`tests/test_render.py` (8 tests):**
1. `test_render_index_contains_system_summary`
2. `test_render_index_contains_mermaid_block`
3. `test_render_mermaid_packages_only` — no `.py` node IDs in the Mermaid block
4. `test_render_module_page_mirrored_path` — file written at the correct mirrored path
5. `test_render_module_page_contains_summary`
6. `test_render_api_table_has_all_routes` — api.md has one data row per ROUTE node
7. `test_render_missing_summary_graceful` — absent summary → `_(no summary yet)_`, no crash
8. `test_render_output_is_deterministic` — same inputs → byte-identical output on two calls

**`tests/test_manifest.py` (4 tests):**
1. `test_manifest_roundtrip` — write + read → identical content
2. `test_manifest_stable_json` — same inputs → byte-identical output
3. `test_manifest_covers_all_pages` — every page file has a manifest entry
4. `test_manifest_records_hash_struct` — a known node's `hash_struct` is stored correctly

---

## Sub-task 3.3 — `docgen check` [pending]

**Intent:** Compare `hash_struct` values in `manifest.json` against the current
`facts.json`. Exit 0 when clean; exit 1 with stale page list when anything drifted.

### Two modes
- **`docgen check`** — fast path: reads `facts.json` as-is.
- **`docgen check --fresh`** — re-runs `docgen extract` first, then checks.

### Stale-facts warning
When using the fast path, if `facts.json` is **older than** `manifest.json`
(by mtime), emit a warning to stderr:
```
WARNING: facts.json predates manifest.json — run 'docgen extract' first or use --fresh
```
This catches the footgun where a developer runs `check`, sees "all good," but
`facts.json` is days old. The check still runs; this is a warning, not an error.

### Design (`drift.py`)
`find_stale_pages(manifest: dict, graph: FactGraph) -> list[str]`:
- For each page in the manifest, check whether any recorded `hash_struct` value
  differs from the current graph, or whether any recorded fact ID is absent.
- Returns stale page paths (repo-root-relative POSIX, same keys as manifest).
- `hash_source`-only changes: **not** drift — set a `needs_resummarize` flag for
  `update` but do not cause `check` to exit 1.

`warn_if_facts_stale(facts_path: Path, manifest_path: Path) -> None`:
- Compares `facts_path.stat().st_mtime` to `manifest_path.stat().st_mtime`.
- Prints warning to stderr if facts predates manifest.

### CLI
`docgen check [--config docgen.toml] [--fresh]`
Exit 0 = clean. Exit 1 = stale (list printed to stdout).

### Files
`src/docgen/check/drift.py`, `src/docgen/cli.py`

### Tests — `tests/test_drift.py` (6 tests)
1. `test_check_clean_returns_empty`
2. `test_check_detects_hash_struct_change`
3. `test_check_ignores_hash_source_only_change` — `hash_source` changed, `hash_struct` same → not stale
4. `test_check_detects_deleted_node` — fact ID removed from graph → stale
5. `test_check_new_node_not_stale` — new node that no page depends on → not stale
6. `test_warn_if_facts_stale` — facts older than manifest → warning emitted to stderr

---

## Sub-task 3.4 — `docgen update` [pending]

**Intent:** Re-render only the stale pages identified by `check`. For nodes
whose `hash_source` also changed, re-summarize first, then re-render. Early
cutoff is automatic via the cache-key mechanism.

### Design (`update.py`)
`plan_update(stale_pages, manifest, graph, summaries) -> UpdatePlan`:
- `UpdatePlan(pages_to_render: list[str], nodes_to_resummarize: list[str])`.
- Node needs re-summarization if `hash_source` changed AND it has an existing summary.
- Re-summarization uses `run_hierarchy` with the prior cache; only nodes whose
  `hash_input_with_children` changed are called.
- Early cutoff: if new text == old text, parent cache key unchanged → parent skipped.
- After re-summarization, render only `pages_to_render`.

### CLI
`docgen update [--config docgen.toml] [--backend stub|bob_shell]`
Exit 0 on success, 1 on any render failure.

### Files
`src/docgen/check/update.py`, `src/docgen/cli.py`

### Tests — `tests/test_update.py` (4 tests)
1. `test_update_rerenders_only_stale_pages`
2. `test_update_skips_resummarize_when_hash_source_unchanged`
3. `test_update_writes_updated_manifest`
4. `test_update_noop_when_no_stale_pages`

---

## Sub-task 3.5 — Freshness gate [pending]

**Intent:** 4 integration tests on a small fixture repo.

### Fixture repo (`tests/fixtures/freshness/`)
```
docgen.toml        # adapter = none, root = ".", source_root = "."
main.py            # one module-level function + one class
models.py          # one Pydantic model
```

### Gate tests (`tests/test_freshness_gate.py`)
1. **Fresh run → check passes.** `render` → `check` → exit 0.
2. **Edit function signature → check fails naming the right page.**
   Mutate `main.py` function signature → re-extract → `check` → exit 1 + correct page.
3. **`update` rebuilds only that page → check passes.**
   `update` → assert only affected page re-rendered → `check` → exit 0.
4. **Harmless comment edit → no drift.**
   Add comment to `main.py` → re-extract → `check` → exit 0
   (`hash_struct` unchanged; only `hash_source` differs).

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/render/markdown.py` | Implement `render_index`, `render_module_page`, `render_all_module_pages` |
| `src/docgen/render/mermaid.py` | Implement `render_mermaid_diagram` (packages only) |
| `src/docgen/render/api_table.py` | Implement `render_api_table` |
| `src/docgen/check/manifest.py` | Implement `PageRecord`, `build_manifest`, `write_manifest`, `read_manifest` |
| `src/docgen/check/drift.py` | Implement `find_stale_pages`, `warn_if_facts_stale` |
| `src/docgen/check/update.py` | Implement `UpdatePlan`, `plan_update` |
| `src/docgen/cli.py` | Add `_run_render`, `_run_check`, `_run_update` + subparser wiring |
| `tests/test_render.py` | New — 8 tests |
| `tests/test_manifest.py` | New — 4 tests |
| `tests/test_drift.py` | New — 6 tests |
| `tests/test_update.py` | New — 4 tests |
| `tests/fixtures/freshness/` | New fixture repo |
| `tests/test_freshness_gate.py` | New — 4 integration tests |
| `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md` | Status updates after all sub-tasks |

---

## Dependency order

```
3.1 + 3.2 (render + manifest)   implement together (render command writes manifest)
3.3       (check)               depends on manifest schema from 3.2
3.4       (update)              depends on check logic + renderer
3.5       (freshness gate)      last — integration test of 3.1–3.4
```
