# Plan: Task 2b.2 — Prompts + Citation Format

## Goal

Implement `src/docgen/summarize/prompts.py`: the **per-level prompt templates** and the
canonical **`[[fact_id]]` citation format**, so any prose backend (Bob Shell in 2b.6) can turn
a `SummaryRequest` into a citation-instructed prompt. **No LLM calls happen here** — this task
produces strings only.

**Done when:** `build_prompt(req)` returns a deterministic, level-appropriate prompt that
(a) lists exactly the fact IDs the model may cite, (b) renders the node's relational edges as
context, (c) mandates the `[[fact_id]]` citation format, and (d) is covered by offline tests.

---

## Scope boundaries

Task 2b.2 owns:

- The citation format definition + parsing/formatting helpers
- Per-level instruction templates (`function`, `method`, `class`, `module`, `package`, `system`)
- The `build_prompt(req)` assembler (facts block, relational-edges block, source block,
  child-summary block, citation rules)
- `tests/test_prompts.py`

Task 2b.2 does **NOT** own:

- LLM invocation → 2b.6 (`BobShellSummarizer`)
- Recursion, bottom-up driver, cache → 2b.3
- Citation validation → 2b.4
- Entailment spot-check → 2b.5
- `base.py`, `cli.py`, `store.py`, `manual.py` stay **unchanged** (2b.1 + its edge addendum are done)

---

## Sources of truth

- **`architecture.md` §7:** citation format is inline `[[<fact_id>]]` after each claim;
  `SummaryResult.text` carries the citations; the validator will check (1) the ID exists in
  `facts.json`, (2) every sentence has ≥1 citation, (3) entailment spot-check. Hierarchy is
  `function → module → package → system`; each level receives **only its own facts and child
  summaries**.
- **`base.py` `SummaryRequest`** (after the Oct 11 addendum): `node_id`, `level` (`NodeLevel`),
  `facts` (the node's own `facts.json` dict), `source_text`, `child_summaries`
  (`list[SummaryResult]`), and `edges` (`list[dict]` — the node's `raises` / `depends_on` /
  `calls` / `inherits` edges, same shape as `facts.json`).
- **`generated/facts.json` edge shapes (verified):**

  | Edge type | `to` shape | Citeable target? |
  |---|---|---|
  | `depends_on` | in-repo node id, or `external:...` | yes, when in-repo |
  | `inherits` | in-repo node id, or `external:...` | yes, when in-repo |
  | `raises` | in-repo node id, or `external:<dotted>` | yes, when in-repo |
  | `calls` | **bare call name** (e.g. `"Depends"`, `"HTTPException"`, `"check_user_can_modify_article"`) | **no** — context only |

---

## Key design decisions

### D-A — What a citation is

A citation is `[[` + a **node id from `facts.json`** + `]]`, placed immediately after the
clause/sentence it supports.

- `CITATION_RE = re.compile(r"\[\[([^\[\]]+)\]\]")`
- `format_citation(fact_id: str) -> str` → `f"[[{fact_id}]]"`
- `extract_citations(text: str) -> list[str]` — ordered, de-duplicated. **Reused by the 2b.4
  validator** so prompt-side and validation-side regexes can never diverge.

### D-B — Which IDs a prompt may cite

Derived from `req` alone (no graph access, no `base.py` change):

```python
allowed = { req.node_id }
        | { req.facts.get("file", "") }          # the module node id
        | { req.facts.get("parent_class", "") }   # the enclosing class id
        | { cs.node_id for cs in req.child_summaries }
        | { e["to"] for e in req.edges
              if e["type"] in {"raises", "depends_on", "inherits"}
              and not e["to"].startswith("external:") }
# drop empty strings, dedupe, sort
```

- `calls` targets are **excluded** from the allowed-ID set: they are raw call names, not node
  ids (see the table above), so citing them would fail the 2b.4 validator. They are still shown
  to the model as context.
- `external:...` targets are excluded (they are not in `facts.json`).
- Rationale for keeping this `req`-derived: §7's `SummaryRequest` carries only own facts +
  child summaries + (now) own edges, and `build_prompt` should stay pure and testable.

### D-C — Per-level instructions

One instruction block per `NodeLevel`; all share the grounding rule *"base every statement only
on the inputs shown; omit anything unclear rather than guess"*.

| Level | Instruction focus |
|---|---|
| `function` | Purpose; inputs from the signature; return value; notable decorators (route/auth); exceptions raised; dependencies; notable calls; cite own id plus module/class ids |
| `method` | Same as `function`, plus its role within `parent_class` |
| `class` | Responsibility; base classes (`inherits`); fields incl. inherited; whether Pydantic model; use child method summaries |
| `module` | Purpose + main definitions, composed **from child summaries**; how the pieces relate |
| `package` | Purpose + how submodules fit together, from child summaries |
| `system` | Whole-project architecture overview from package child summaries; no invented components |

### D-D — Determinism

The prompt must be a pure function of `req`:

- facts rendered via `json.dumps(facts, sort_keys=True, indent=2, ensure_ascii=False)`
- edges rendered grouped by type, and within a type ordered by `to`
- allowed IDs sorted; child summaries sorted by `node_id`

This is what keeps 2b.3's cache and the 2b.5 eval reproducible.

### D-E — Prompt version

A module-level `PROMPT_VERSION` constant is embedded in the prompt. Note: `base.hash_input()`
hashes `node_id + hash_struct + hash_source` only, so a *prompt* edit alone will not invalidate
cached summaries — flagged for 2b.3 to fold `PROMPT_VERSION` into the cache key. `base.py` is
untouched in 2b.2.

### D-F — Output contract

Markdown prose; every sentence ends with ≥1 `[[id]]`; cite only IDs from the allowed list;
never invent an ID or a component. Length guidance per level (function/method/class: 2–5
sentences; module: one paragraph; package: 1–2 paragraphs; system: 2–4 paragraphs).

---

## Prompt structure

```
PROMPT_VERSION: <version>
<SYSTEM_PREAMBLE>                    # role: factual doc-writer; never invents structure

## Your task
<per-level instruction block>

## Citation rules
- Every sentence must end with at least one citation: [[<fact_id>]]
- Cite ONLY IDs from "Allowed fact IDs". Never invent an ID.
- Do not restate anything you cannot ground in the inputs.

## Allowed fact IDs
- <id>                              (sorted)

## Node facts
```json
<sorted JSON of req.facts>
```

## Relational facts              # omitted when req.edges is empty
- raises: external:fastapi.HTTPException
- depends_on: target/app/api/dependencies/authentication.py::get_current_user_authorizer
- calls: get_repository
- inherits: target/app/core/settings/base.py::BaseAppSettings

## Source                        # omitted when source_text is empty
```python
<req.source_text>
```

## Child summaries               # omitted when there are none
### <child node_id>
<child text>

## Output
Markdown prose. Every sentence carries at least one [[id]] citation.
```

---

## Sub-tasks

### Sub-task 1 — Citation format + constants [ ] pending

**Intent:** One canonical definition of the citation format that the prompt and (later) the
validator both use.

**Expected outcomes:**
- `CITATION_RE`, `format_citation`, `extract_citations` implemented.
- `PROMPT_VERSION`, `SYSTEM_PREAMBLE`, `CITATION_RULES` constants.
- Module docstring explaining *why* (grounding), not just what.

### Sub-task 2 — Per-level instruction templates [ ] pending

**Intent:** Distinct guidance so each level describes the right thing (D-C).

**Expected outcomes:**
- `LEVEL_INSTRUCTIONS: dict[NodeLevel, str]` covering all six levels.
- Every block contains the shared grounding rule.

### Sub-task 3 — `build_prompt(req)` assembler [ ] pending

**Intent:** Compose all inputs into one deterministic, citation-instructed prompt.

**Expected outcomes:**
- `allowed_fact_ids(req: SummaryRequest) -> list[str]` (D-B, sorted/deduped).
- `render_edges(edges) -> str` grouped by type, ordered by `to`.
- `build_prompt(req: SummaryRequest) -> str` assembling the sections above; omits empty blocks.
- No I/O, no LLM, deterministic bytes for a given `req`.

### Sub-task 4 — Tests [ ] pending

**Intent:** Prove the format and per-level behaviour offline.

**Tests to add** in `tests/test_prompts.py`:

1. `test_build_prompt_includes_core_sections` — preamble, citation rules, node facts, source.
2. `test_build_prompt_lists_allowed_ids_sorted` — includes own id, module file, parent class,
   child ids, and in-repo edge targets; sorted; deduped; excludes `external:` and `calls` targets.
3. `test_build_prompt_per_level_distinct` — parametrized over the six levels; blocks differ.
4. `test_build_prompt_deterministic` — same request twice → byte-identical prompt.
5. `test_build_prompt_child_summaries_sorted` — children rendered ordered by `node_id`.
6. `test_build_prompt_renders_edges` — `raises`/`depends_on`/`calls`/`inherits` appear as context;
   `calls` target is present as text but absent from "Allowed fact IDs".
7. `test_build_prompt_omits_empty_blocks` — no `## Source` / `## Child summaries` / `## Relational facts` when empty.
8. `test_citation_roundtrip` — `format_citation(id)` is matched by `extract_citations`.
9. `test_extract_citations_multiple_and_dedup` — multiple per sentence, dedup, ignores malformed `[]` / unclosed `[[`.

### Sub-task 5 — Log [ ] pending

Update `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md` (repo convention).

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/prompts.py` | **Implement** — constants, citation helpers, per-level templates, `build_prompt` |
| `tests/test_prompts.py` | **New** — 9 offline tests |
| `docs/tasks.md`, `docs/memory.md`, `BOB_LOG.md` | Status/log updates only |

`base.py`, `cli.py`, `store.py`, `manual.py`, `citations.py`, `hierarchy.py`, `bob_shell.py` — **unchanged**.

---

## Open questions

- **`calls` are not citeable.** Call targets are unresolved raw names (D-008), so a summary can
  *mention* a call but must cite a real node id (usually its own). Resolving calls is Tier 2
  (2a.11), out of scope. Confirm this is acceptable, or the model will occasionally want to cite
  a call that is not a fact ID.
- **Prompt-version invalidation** (D-E) needs a 2b.3 cache-key decision.
- **Enforcement** lives in 2b.4 — `build_prompt` only *instructs*.
