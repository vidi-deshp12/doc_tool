# Plan: Prompt Quality Fixes (2b prompt + hierarchy)

## Goal

Fix six correctness and quality issues in `summarize/prompts.py` and
`summarize/hierarchy.py` that were identified in a post-implementation review.
All changes are confined to those two files and their tests.

After this task:
- Handler prompts receive correct route context (fix 3) and see request/response
  model edges (fix 6).
- The LLM is never shown a forbidden citation example (fix 2).
- The facts dict sent to the LLM is stripped of internal fields the model cannot
  use (fix 5).
- A comment-only edit in a function no longer cascades re-summarization to all
  ancestor nodes (cache fix).
- `PROMPT_VERSION` is derived from prompt content — no manual bumping needed (auto-version).

Because `PROMPT_VERSION` will change as a result of fixes 2, 3, 5, and 6, all
231 cached summaries in `summaries.json` will be invalidated and a full re-run of
`docgen summarize` will be needed after this task.

---

## Sub-task A — Fix the `handles` edge rendering in `render_edges` [pending]

**Intent:** `render_edges` currently renders `edge["to"]` for every edge type,
including `handles`. For a HANDLES edge `{from: route_id, to: function_id}`, the
`to` value is the function's own ID — which the model already knows. The useful
value is `from` (the route ID with its method/path/status), which is exactly what
`allowed_fact_ids` already correctly adds to the citeable list. This mismatch means
the Relational facts section shows the function its own ID instead of the route it
serves.

**Expected outcomes:**
- Handler prompts show `- handles: route:POST /api/articles/{slug}/comments`
  (the route ID) instead of their own function ID.
- No other edge types are affected.

**Todo list:**
1. In `render_edges` in `prompts.py`, add a special case: when `edge_type == "handles"`,
   render `edge.get("from", "")` instead of `edge.get("to", "")`.
2. Update the existing prompt test that covers `render_edges` with a `handles` edge
   to assert the `from` value is rendered.

**Relevant context:**
- [`src/docgen/summarize/prompts.py:164-185`](src/docgen/summarize/prompts.py) — `render_edges`
- [`src/docgen/summarize/hierarchy.py:193-195`](src/docgen/summarize/hierarchy.py) — `_build_edges_by_from` already indexes handles by `to_id` (correct); only the renderer is wrong
- D-039 / S4a: HANDLES edges have `from=route_id, to=function_id` by design

---

## Sub-task B — Add REQUEST_MODEL and RESPONSE_MODEL edges to prompts [pending]

**Intent:** `_build_edges_by_from` in `hierarchy.py` only indexes
`{RAISES, DEPENDS_ON, CALLS, INHERITS, HANDLES}`. REQUEST_MODEL and RESPONSE_MODEL
edges extracted in D-044 / E5 are silently dropped. Handler function prompts never
see what models they accept or return, so summaries can't mention or cite them.

**Expected outcomes:**
- For `POST /api/articles/{slug}/comments`, `create_comment_for_article`'s prompt
  will include `- request_model: target/app/models/schemas/comments.py::CommentInCreate`
  and `- response_model: target/app/models/schemas/comments.py::CommentInResponse`.
- Both edge types are citeable (model node IDs are in-repo).
- `render_edges` renders them in a predictable order.

**Todo list:**
1. In `_build_edges_by_from` in `hierarchy.py`, add `ET.REQUEST_MODEL` and
   `ET.RESPONSE_MODEL` to `by_from_types` (indexed by `from_id` = the route node).
2. In `prompts.py`, add `"request_model"` and `"response_model"` to
   `_CITEABLE_EDGE_TYPES`.
3. In `prompts.py`, add `"request_model"` and `"response_model"` to
   `_RENDERED_EDGE_TYPES` (in a logical order, e.g. after `"handles"`).
4. In `allowed_fact_ids`, the existing loop over `_CITEABLE_EDGE_TYPES` already
   adds `edge["to"]` for any non-external target — no change needed there, since
   REQUEST_MODEL and RESPONSE_MODEL `to` values are in-repo CLASS node IDs.
5. Add a test in `tests/test_prompts.py` that builds a `SummaryRequest` with
   `request_model` and `response_model` edges and asserts both appear in the
   rendered prompt and in `allowed_fact_ids`.

**Relevant context:**
- [`src/docgen/summarize/hierarchy.py:180-196`](src/docgen/summarize/hierarchy.py) — `_build_edges_by_from`
- [`src/docgen/summarize/prompts.py:98-105`](src/docgen/summarize/prompts.py) — `_CITEABLE_EDGE_TYPES`, `_RENDERED_EDGE_TYPES`
- [`src/docgen/summarize/prompts.py:126-161`](src/docgen/summarize/prompts.py) — `allowed_fact_ids`

---

## Sub-task C — Fix the contradictory citation example [pending]

**Intent:** `CITATION_RULES` at line 43 shows `[[external:fastapi.HTTPException]]`
as the example. But `allowed_fact_ids` excludes all `external:` targets, and the
citation rules themselves say "cite ONLY IDs from the Allowed fact IDs list". The
model is shown a forbidden ID in the example. The validator won't catch it either
because `external:` nodes exist in `known_ids`. This is the worst combination:
wrong instruction + silent validation pass.

**Expected outcomes:**
- The example uses an ID that could actually appear in `allowed_fact_ids`.
- No `external:` IDs appear anywhere in the citation rules section.

**Todo list:**
1. Replace the `[[external:fastapi.HTTPException]]` example in `CITATION_RULES`
   with a plausible in-repo example, e.g.:
   `"This function raises DBError when the record is not found [[target/app/db/errors.py::EntityDoesNotExist]]."`
2. Keep the second multi-ID example unchanged (it already uses valid in-repo IDs).
3. Verify the existing `test_citation_rules_example` test (if it exists) still
   passes, or update it.

**Relevant context:**
- [`src/docgen/summarize/prompts.py:38-50`](src/docgen/summarize/prompts.py) — `CITATION_RULES`
- [`src/docgen/summarize/prompts.py:126-161`](src/docgen/summarize/prompts.py) — `allowed_fact_ids` (excludes `external:`)

---

## Sub-task D — Filter internal fields from the facts dict sent to the LLM [pending]

**Intent:** `_node_to_dict(node)` produces the full serialized node including
internal fields that mean nothing to a doc writer and inflate token count. The
filtered set to drop is:

```
type          — redundant: level label already says "FUNCTION/CLASS/MODULE"
hash_struct   — internal pipeline field
hash_source   — internal pipeline field
what          — Unresolved-node field; always "" on summarizable nodes
why           — Unresolved-node field; always "" on summarizable nodes
where         — Unresolved-node field; always "" on summarizable nodes
variable      — always "" in current codebase (scaffolded for ROUTER, not yet used)
prefix        — always "" in current codebase (scaffolded for ROUTER, not yet used)
```

Keep: `id`, `file`, `lines`, `name`, `dotted_name`, `docstring`, `signature`,
`returns`, `async_flag`, `decorators`, `bases`, `fields`, `is_pydantic_model`,
`parent_class`, `method`, `full_path`, `status_code`, `library_name`,
`sql_name`, `sql_file`.

Rationale for keeping `library_name`, `sql_name`, `sql_file`: these are empty for
all currently summarizable node types, but keeping them avoids a schema mismatch
when aiosql linking (2a.11) is implemented. Their presence adds zero tokens when
empty (they're omitted by `_node_to_dict` when falsy).

**Expected outcomes:**
- The `## Node facts` block in every prompt no longer contains `type`, `hash_struct`,
  `hash_source`, `what`, `why`, `where`, `variable`, or `prefix`.
- All doc-useful fields (`signature`, `decorators`, `docstring`, `bases`, etc.)
  are still present.
- Token count per prompt is reduced for every node type.

**Todo list:**
1. Define a module-level constant in `hierarchy.py`:
   ```python
   _PROMPT_FACTS_DROP: frozenset[str] = frozenset({
       "type", "hash_struct", "hash_source",
       "what", "why", "where",
       "variable", "prefix",
   })
   ```
2. In `run_hierarchy`, when building `req`, replace `facts=_node_to_dict(node)` with:
   ```python
   facts={k: v for k, v in _node_to_dict(node).items() if k not in _PROMPT_FACTS_DROP}
   ```
3. Add a test that builds a `SummaryRequest` via `run_hierarchy` (using
   `StubSummarizer`) and asserts none of the dropped fields appear in the
   `req.facts` dict passed to the summarizer. Use a spy/wrapper around
   `StubSummarizer` to capture the request.

**Relevant context:**
- [`src/docgen/summarize/hierarchy.py:282-289`](src/docgen/summarize/hierarchy.py) — `req` construction in `run_hierarchy`
- [`src/docgen/facts/store.py:12-69`](src/docgen/facts/store.py) — `_node_to_dict` (unchanged — this is the facts.json serializer; the filtering is a prompt-layer concern only)

---

## Sub-task E — Change child propagation to use output text hash [pending]

**Intent:** `hash_input_with_children` currently uses `c.hash_input` (the child's
*input* hash) when building a parent's cache key. This means any input change to a
child (including a comment edit that changes `hash_source`) propagates to all
ancestor nodes even if the child's new prose is byte-identical to the old.
Architecture §7's "materially unchanged → stop propagating" cutoff is not
implemented by the current code.

Fix: use `sha256(c.text)` (the child's *output text* hash) instead. If a comment
edit causes a function to be re-summarized but produces identical prose, the
parent's cache key is unchanged and the parent is skipped.

**Expected outcomes:**
- A comment-only edit to one function triggers re-summarization of that function
  only; its class/module/package/system ancestors are not re-summarized (assuming
  the prose is identical, which `StubSummarizer` guarantees in the test).
- The existing test `test_no_resummary_on_unchanged_cache` still passes.
- New test: modify a child node's `hash_source` but keep the summarizer output
  identical → assert the parent is not re-summarized.

**Todo list:**
1. In `hash_input_with_children` in `hierarchy.py`, replace:
   ```python
   child_hashes = "".join(sorted(c.hash_input for c in req.child_summaries))
   ```
   with:
   ```python
   child_hashes = "".join(
       sorted(
           hashlib.sha256(c.text.encode("utf-8")).hexdigest()
           for c in req.child_summaries
       )
   )
   ```
2. Add a test: set up a parent→child graph; run hierarchy; mutate child's
   `hash_source` in the graph (simulating a comment edit) but configure
   `StubSummarizer` to return the same text as before; re-run hierarchy with the
   updated graph and the previous results as cache. Assert: child is re-called
   (input changed); parent is NOT re-called (child text identical).

**Relevant context:**
- [`src/docgen/summarize/hierarchy.py:70-89`](src/docgen/summarize/hierarchy.py) — `hash_input_with_children`
- [`tests/test_hierarchy.py`](tests/test_hierarchy.py) — existing cache tests

---

## Sub-task F — Auto-derive PROMPT_VERSION from template content [pending]

**Intent:** `PROMPT_VERSION = "2b4.1"` is a manually-maintained string. If a
developer edits a template string and forgets to bump it, cached summaries from the
old prompt are silently used with the new prompt — the whole point of the version is
defeated. Replace the constant with a hash of the actual prompt template content so
it changes automatically whenever any template string changes.

**Expected outcomes:**
- Editing any of `SYSTEM_PREAMBLE`, `CITATION_RULES`, `OUTPUT_INSTRUCTION`,
  `_GROUNDING_RULE`, or `_LEVEL_FOCUS` automatically changes `PROMPT_VERSION`.
- The string is still human-readable in logs (truncated to 16 hex chars).
- No test needs to assert a specific value — only that it is a non-empty string
  and that it changes when a template changes.

**Todo list:**
1. Move `PROMPT_VERSION` definition to *after* all template strings (currently
   after `_LEVEL_FOCUS`, around line 92 in the current file).
2. Replace the string literal with:
   ```python
   import hashlib as _hashlib

   PROMPT_VERSION: str = _hashlib.sha256(
       (
           SYSTEM_PREAMBLE
           + CITATION_RULES
           + OUTPUT_INSTRUCTION
           + _GROUNDING_RULE
           + "".join(_LEVEL_FOCUS.values())
       ).encode("utf-8")
   ).hexdigest()[:16]
   ```
3. Remove the stale comment on lines 23–25 that says "2b.3 should fold it in" —
   that work is already done in `hash_input_with_children`.
4. Update any test that asserts `PROMPT_VERSION == "2b4.1"` to assert
   `len(PROMPT_VERSION) == 16` and `PROMPT_VERSION.isalnum()` instead.

**Relevant context:**
- [`src/docgen/summarize/prompts.py:23-26`](src/docgen/summarize/prompts.py) — current constant + stale comment
- [`src/docgen/summarize/hierarchy.py:70-89`](src/docgen/summarize/hierarchy.py) — uses `prompt_version` in cache key

---

## Files to touch

| File | Changes |
|---|---|
| `src/docgen/summarize/prompts.py` | Sub-tasks A (render_edges), B (_CITEABLE/_RENDERED_EDGE_TYPES), C (citation example), F (PROMPT_VERSION) |
| `src/docgen/summarize/hierarchy.py` | Sub-tasks B (_build_edges_by_from), D (_PROMPT_FACTS_DROP + req construction), E (hash_input_with_children) |
| `tests/test_prompts.py` | Tests for A, B, C, F |
| `tests/test_hierarchy.py` | Tests for D, E |
| `docs/tasks.md` | Tick new task entry after completion |
| `docs/memory.md` | Add D-045 |
| `BOB_LOG.md` | Add entry |

`src/docgen/facts/store.py`, `src/docgen/facts/schema.py`, and all other files are
**not touched**. The filtering is a prompt-layer concern only.

---

## Dependency order

```
A (handles render)      ─┐
B (model edges)          ├─→  F (PROMPT_VERSION auto-derived — must be last because
C (citation example)     │       A/B/C all change template content that F hashes)
D (filter fields)       ─┘

E (child text hash)     — independent; can be done in parallel with A–D
F (PROMPT_VERSION)      — must be done after A, B, C are complete
```

Do A, B, C, D, E in one pass; do F last. All sub-tasks are in the same two files
so a single implementation session is appropriate.

---

## Post-task: re-run summarizer

Because `PROMPT_VERSION` will change (template edits in A, B, C trigger it), all
cached summaries in `generated/summaries.json` are invalidated. After the task:

```powershell
docgen summarize --backend bob_shell
docgen validate
docgen render
docgen check   # should exit 0
```

The re-run produces summaries that correctly mention request/response models and
cite route IDs from the right direction.
