# Plan: Task 2b.3 — Hierarchy Driver + Cache

## Goal

Replace the flat `_run_summarize` pass with a bottom-up hierarchy driver that:

1. Processes nodes in order: functions/methods → classes → modules → packages → (optional system root)
2. Passes each node's already-completed child summaries into its `SummaryRequest.child_summaries`
3. Skips regeneration when the cached summary's `hash_input` matches the freshly computed one
   (the cache key now includes child hashes and `PROMPT_VERSION`)
4. Applies early cutoff: if the regenerated text is identical to the cached text, the ancestor
   summary is also considered fresh (it will compute the same cache key)

**Done when:** a test with a call counter shows that re-running with no changes makes **zero**
summarizer calls.

---

## Scope

Task 2b.3 owns:

- `src/docgen/summarize/hierarchy.py` — new implementation: `run_hierarchy` entry point,
  `build_contains_index`, `topological_order`, extended `hash_input_with_children`
- `src/docgen/cli.py` — replace the flat loop in `_run_summarize` with a call to
  `run_hierarchy`; extend `_node_level` to handle `PACKAGE`
- `tests/test_hierarchy.py` — 6+ tests

Task 2b.3 does **NOT** own:

- `base.py`, `prompts.py`, `store.py`, `manual.py` — unchanged
- Phase 3 renderer, manifest, check, update — separate tasks

---

## Sources of truth

- **`architecture.md` §7:** "Hierarchy: function → module → package → system. Each level
  receives only its own facts and child summaries. Cache key = hash of inputs. Early cutoff:
  if regenerated summary is materially unchanged, don't propagate to ancestors."
- **`base.py`:** `SummaryRequest.child_summaries: list[SummaryResult]` (populated here for the
  first time; was always empty in 2b.1)
- **`facts/schema.py`:** `NodeType.PACKAGE` exists; there is no `SYSTEM` node — the system level
  is a virtual synthetic node representing the repo root, not stored in `facts.json`
- **`facts/schema.py` `EdgeType.CONTAINS`:** `package→module, module→{class,function}, class→method`
- **`prompts.py`:** `PROMPT_VERSION = "2b2.1"` — currently not in `hash_input()`; must be added
  to the cache key in 2b.3 so a prompt update invalidates old summaries
- **`cli.py` `_node_level`:** currently returns `"module"` for all non-FUNCTION/non-CLASS nodes;
  must return `"package"` for `NodeType.PACKAGE`

---

## Key design decisions

### D-A — Cache key includes PROMPT_VERSION and child hashes

The existing `hash_input(req)` = sha256(node_id + hash_struct + hash_source). For the hierarchy
driver a new helper `hash_input_with_children(req, prompt_version)` appends:
- `PROMPT_VERSION` (so a prompt edit invalidates all cached summaries on the next run)
- Sorted, concatenated `hash_input` values of all `req.child_summaries`

The old `base.hash_input()` is left unchanged (test compatibility). The new helper lives in
`hierarchy.py` and is what the driver stores in `SummaryResult.hash_input`.

### D-B — CONTAINS index is the only graph traversal needed

Build a `dict[str, list[Node]]` from `EdgeType.CONTAINS` edges: parent_id → list of child nodes.
Topological order follows: process a node only after all its CONTAINS children are done. A simple
post-order walk starting from roots (nodes with no CONTAINS parent) produces the correct order.

### D-C — The "system" level is synthetic but always produced

There is no `SYSTEM` NodeType in `facts.json`. After processing all packages, the driver
always produces one final `SummaryResult` with:
- `node_id = "system"`, `level = "system"`, `facts = {}`, `source_text = ""`
- `child_summaries` = all package-level summaries (sorted by node_id)

The cache key uses the same formula: sha256 of `"system" + "" + "" + prompt_version +
sorted child hash_inputs`. The system summary is written to `summaries.json` alongside all
others.

### D-D — Early cutoff via cache key identity

A "materially unchanged" summary is one whose freshly computed `hash_input_with_children` matches
the stored entry's `hash_input`. Because the cache key incorporates child hashes, if a child's
text doesn't change, its `hash_input` doesn't change either, so the parent's cache key also
stays the same — the parent is skipped too. No separate text-diff is required.

### D-E — The existing flat pass is replaced, not kept

The flat `_run_summarize` body is replaced by a call to `run_hierarchy(...)`. The CLI public
interface (`docgen summarize`) is unchanged.

### D-F — PACKAGE nodes: source text and level

`NodeType.PACKAGE` nodes in the fact graph represent `__init__.py` files. Their `file` and
`lines` are set. `_node_level` returns `"package"` for them. The relational-edge indexing in
the CLI (RAISES/DEPENDS_ON/CALLS/INHERITS) remains unchanged.

---

## Hierarchy driver algorithm

```
1. Load existing summaries from summaries.json → cache: dict[node_id, SummaryResult]
2. Build CONTAINS index: parent_id → list[Node]
3. Topological sort (post-order DFS from roots):
   - A "root" is any summarizable node not referenced as the `to` side of a CONTAINS edge
     whose `from` is another summarizable node
   - Visit children first (recursively), then the parent
4. For each node in topological order:
   a. Collect child SummaryResults for all CONTAINS children of this node
   b. Build SummaryRequest with child_summaries populated
   c. Compute hash_input_with_children(req, PROMPT_VERSION)
   d. If cache.get(node.id) and cache[node.id].hash_input == computed_key: use cached, skip call
   e. Otherwise: call summarizer.summarize(req); store in cache; mark changed
5. Write all SummaryResults to summaries.json
```

---

## Acceptance criterion (test)

A `CountingSummarizer` wraps a `StubSummarizer` and increments a counter per call.

1. Run `run_hierarchy` on a fixture fact graph → N calls
2. Run `run_hierarchy` again without changing any facts → **0 calls** (all from cache)
3. Edit one node's `hash_struct` → exactly that node plus its ancestors are re-summarized

---

## Sub-tasks

### Sub-task 1 — `hierarchy.py`: contains index + topological sort [ ] pending

**Intent:** Build the graph-traversal foundation that all hierarchy logic depends on.

**Expected outcomes:**
- `build_contains_index(graph: FactGraph) -> dict[str, list[Node]]` returns each summarizable
  parent's direct children (only `FUNCTION`, `CLASS`, `MODULE`, `PACKAGE` nodes; non-summarizable
  node types such as ROUTE and EXTERNAL are excluded from the index)
- `topological_order(graph: FactGraph, index: dict[str, list[Node]]) -> list[Node]` returns
  summarizable nodes in bottom-up order (children before parents)

**Relevant context:**
- [`FactGraph`](src/docgen/facts/schema.py:108) — `nodes` and `edges` tuples
- `EdgeType.CONTAINS` — parent→child relationships
- Summarizable types: `{FUNCTION, CLASS, MODULE, PACKAGE}`

**Status:** `[ ] pending`

---

### Sub-task 2 — `hierarchy.py`: `hash_input_with_children` + `run_hierarchy` [ ] pending

**Intent:** Implement the cache key, cache lookup, and the bottom-up summarization loop.

**Expected outcomes:**
- `hash_input_with_children(req: SummaryRequest, prompt_version: str) -> str` returns a
  SHA-256 over `node_id + hash_struct + hash_source + prompt_version + sorted child hash_inputs`
- `run_hierarchy(graph, summarizer, repo_root, existing_cache, prompt_version) -> list[SummaryResult]`
  implements the algorithm described above; returns the full list of summaries (cached + fresh)
- Function accepts `existing_cache: dict[str, SummaryResult]` so tests can inject a pre-populated
  cache without touching the filesystem

**Relevant context:**
- [`hash_input`](src/docgen/summarize/base.py:79) — reference implementation; new function mirrors but extends it
- [`PROMPT_VERSION`](src/docgen/summarize/prompts.py:26) — passed in so hierarchy is decoupled from prompts module
- [`_node_to_dict`](src/docgen/facts/store.py:12) — populates `SummaryRequest.facts`; used as-is
- [`_read_source_text`](src/docgen/cli.py:214) — moved/imported into hierarchy or duplicated minimally

**Status:** `[ ] pending`

---

### Sub-task 3 — `cli.py`: wire hierarchy driver, extend `_node_level` [ ] pending

**Intent:** Connect the new `run_hierarchy` function to the CLI, replacing the flat loop.

**Expected outcomes:**
- `_node_level` returns `"package"` for `NodeType.PACKAGE` (was `"module"` before)
- `_run_summarize` loads existing summaries (if `summaries.json` exists) into a cache dict, calls
  `run_hierarchy(...)`, and writes the result; zero-change re-runs produce no summarizer calls
- The `docgen summarize` CLI signature is unchanged

**Relevant context:**
- [`_run_summarize`](src/docgen/cli.py:236) — current flat loop to be replaced
- [`read_summaries`](src/docgen/summarize/store.py:50) — load cache from disk
- [`write_summaries`](src/docgen/summarize/store.py:35) — write final result

**Status:** `[ ] pending`

---

### Sub-task 4 — Tests [ ] pending

**Intent:** Prove bottom-up ordering, cache hit, cache miss, and early cutoff offline.

**Test file:** `tests/test_hierarchy.py`

**Tests to add:**

1. `test_topological_order_children_before_parents` — a 3-node graph (module contains class
   contains function); asserts function appears before class, class before module in the output.
2. `test_run_hierarchy_passes_child_summaries` — a class with one method; after running, the
   class's `SummaryRequest.child_summaries` contained the method's result (captured via a
   recording summarizer).
3. `test_run_hierarchy_zero_calls_on_rerun` — run with an empty cache → N calls; run again
   passing the results of the first run as the existing cache → 0 calls.
4. `test_run_hierarchy_reruns_on_hash_change` — same as above but modify one node's `hash_struct`;
   exactly that node and its parent module are re-summarized (≥2 calls).
5. `test_run_hierarchy_includes_package_nodes` — a graph with a PACKAGE node containing a MODULE
   that contains a FUNCTION; all three get summaries, package summary has module as child.
6. `test_hash_input_with_children_changes_on_prompt_version` — same req but different
   `prompt_version` strings produce different hashes.

**Relevant context:**
- See `tests/test_summarize.py` for fixture-building pattern (`_make_fixture_repo`)
- Tests are fully offline: use `StubSummarizer` and in-memory fact graphs

**Status:** `[ ] pending`

---

### Sub-task 5 — Log [ ] pending

Update `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md`.

**Status:** `[ ] pending`

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/hierarchy.py` | **Implement** — contains index, topological sort, `hash_input_with_children`, `run_hierarchy` |
| `src/docgen/cli.py` | **Modify** — extend `_node_level` for PACKAGE; replace flat loop in `_run_summarize` with `run_hierarchy` call; load/pass existing cache |
| `tests/test_hierarchy.py` | **New** — 6 offline tests |
| `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md` | Status/log updates only |

`base.py`, `prompts.py`, `store.py`, `manual.py`, `citations.py` — **unchanged**.

---

## Open questions / risks

- **`_read_source_text` in `cli.py` is private.** The hierarchy driver needs it for building
  `SummaryRequest`. Options: (a) import from `cli.py` (acceptable since it is a sibling module),
  (b) move it to `hierarchy.py` or a shared utility. Recommend moving to `hierarchy.py` since
  it is not CLI-specific; then `cli.py` imports from `hierarchy`.
- **`system` level:** not needed for the 2b.3 acceptance criterion. Keep the door open by making
  `run_hierarchy` return a `list[SummaryResult]` that a caller can append a synthetic system
  summary to, but don't implement it here.
- **Summarizable node types:** ROUTE, ROUTER, EXTERNAL, UNRESOLVED, SQL_QUERY are excluded from
  summarization. The driver should skip them silently.
