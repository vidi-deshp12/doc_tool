# Plan: Prompt-Hash Cache Key + Per-Node Payload Deduplication

**Status:** approved 2026-11-08 (decisions 1 and 2 accepted; 3, 4, 5 declined; 6 deferred as recommended).
Implementation in progress.

## Goal

Two related changes to the summarize phase, in this order:

1. **Cache key = hash of the prompt.** Replace the hand-assembled
   `hash_input_with_children(node_id + hash_struct + hash_source + prompt_version + child
   hashes)` with `hash_prompt(summarizer_identity + "\n" + build_prompt(req))`, so the cache
   answer to "would this call produce the same output?" is derived from the actual payload
   instead of from a proxy that has to be kept in sync by hand.
2. **Stop paying for the same bytes twice in a parent's prompt.** Today a class/module prompt
   contains its entire source *and* the prose of every child that source is made of. Send the
   parent only the part of its span that no child already covers ("residual source"), plus the
   child summaries in full. Then, separately, ask the **lower-level** prompts for tighter prose
   — qualitative guidance, **no numeric word or token caps** — so the child block that ancestors
   consume stops growing at 3–4× the size of the code it describes.

Change 2 is only *effective* if change 1 lands first (or 2 bumps the version by hand): under
today's key, which source text goes into a prompt is invisible to the cache, so a payload change
silently reuses stale prose. That dependency is the reason both live in one plan.

**Done when:**

- `docgen summarize` on an unchanged repo makes **0** calls, and on a repo where only prompt
  payload changed makes calls for exactly the affected nodes.
- A class/module prompt contains no source line that appears inside one of its children.
- Editing a method body does not change its module's prompt (residual is stable).
- `docgen validate`, `docgen render`, `docgen check` behave exactly as today.
- `hash_struct` / `hash_source` are still emitted, still stored in `facts.json`, and still drive
  `docgen check` and `docgen update`. Only the *summarize* cache stops reading them.
- Test suite green (one pre-existing known failure: `test_seeded_bug`).
- Prompt sizes are measured before/after, not asserted; expected effect is recorded in the PR/log.

---

## Part 0 — What happens today (measured, not assumed)

### 0.1 How one prompt is assembled

`hierarchy._process_node` builds one `SummaryRequest` per node
(`node_id`, `level`, `facts`, `source_text`, `child_summaries`, `edges`), then
`prompts.build_prompt(req)` renders, in order:

```
PROMPT_VERSION: <16 hex>      ← sha256 of the template strings (prompts.PROMPT_VERSION)
SYSTEM_PREAMBLE
## Your task                  ← LEVEL_INSTRUCTIONS[level]
## Citation rules
## Allowed fact IDs            ← own id ∪ facts.file ∪ facts.parent_class ∪ child ids ∪ citeable edge targets
## Node facts                  ← _node_to_dict(node) minus _PROMPT_FACTS_DROP
## Relational facts            ← render_edges(req.edges)
## Source                      ← read_source_text(repo_root, node)   ← same call for every level
## Child summaries             ← every child of this node, full text, sorted by id
## Output
```

`source_text` is node-span source for **every** level: a function gets its body, a class gets
its whole body *including every method it contains*, a module gets the whole file. So a parent
prompt already contains its children twice — once as code, once as prose.

### 0.2 How the cache key is computed

`hierarchy.hash_input_with_children(req, prompt_version)`:

```
sha256( node_id
      + facts["hash_struct"]
      + facts["hash_source"]
      + prompt_version
      + "".join(sorted(sha256(child.text) for each child)) )
```

Covers: node identity, own structure, own source (per the extractor's recipes), template
version, children's prose. **Does not cover:** `req.edges` (the `## Relational facts` block and
the edge-derived part of `## Allowed fact IDs`), child *ids*, `lines`, or which backend produced
the text. `prompt_version` is threaded in by hand from both CLI call sites and ~16 test call
sites. The key is computed from the **unfiltered** fact dict, so `_process_node` does a second
`replace(req, facts=prompt_facts)` purely to tidy the prompt (documented as a deviation in
D-045 item D).

### 0.3 Measured payload, current repo (234 summaries; chars ≈ tokens × 4)

Measured over `generated/facts.json` + `generated/summaries.json`. "Residual" = node span minus
the union of its direct children's spans.

| level | n | own source median / p90 / max | child prose median / p90 / max | **residual** median / p90 / max |
|---|---|---|---|---|
| function | 56 | 343 / 957 / 1,399 | – | – |
| method | 42 | 372 / 967 / 3,313 | – | – |
| class | 49 | 104 / 1,394 / 9,791 | 0 / 2,683 / 21,384 | **75 chars, 3 lines** / 206 / 626 |
| module | 70 | 472 / 2,721 / 10,523 | 1,338 / 4,882 / 10,554 | **117 chars, 3 lines** / 643 / 996 |
| package | 16 | 0 (no file) | 9,506 / 15,671 / 24,112 | – |
| system | 1 | 0 | 7,324 | – |

The two worst prompts in the repo:

| node | source | child prose | total | residual |
|---|---|---|---|---|
| `target/app/db/repositories/articles.py::ArticlesRepository` (14 method children) | 9,791 | 21,384 | **31,175 (~7.8k tok)** | **70 chars** (`class ArticlesRepository(BaseRepository):  # noqa: WPS214` + blank lines) |
| `target/app/db/repositories/articles.py` (1 class child) | 10,523 | 5,115 | **15,638 (~3.9k tok)** | **731 chars** (imports, 3 module constants, one regex) |

Repo-wide: class source totals 25,381 chars, module source totals 66,907 chars — and the parts
inside children are, by construction, already summarized. In the `articles.py` module, 9,791 of
10,523 source chars (93%) sit inside its one child.

Summary lengths against the code they describe:

| level | median summary | median source | ratio |
|---|---|---|---|
| function | 1,338 | 343 | **3.9×** |
| method | 1,259 | 372 | 3.4× |
| class | 778 | 104 (header only) | – |
| module | 1,500 | 472 | 3.2× |
| package | 3,783 | 0 | – |

`prompts.py` contains **no** length instruction anywhere — not in `_LEVEL_FOCUS`, not in
`OUTPUT_INSTRUCTION`.

### 0.4 What that implies

- A class body *is* its methods in this repo; "class source" is essentially a second copy of
  child code. The residual is 3 lines, typically `class X(Y):`.
- A module's own source is imports + constants + `if __name__` — genuinely load-bearing for
  "what does this file depend on" and not obtainable from child prose.
- The expensive block at parents is **child prose**, and it is expensive because leaves were
  never told to be concise. That is the right place to compress; the parent is the wrong place.

---

## Part 1 — Cache key becomes a hash of the prompt

### 1.1 The change

```python
# hierarchy.py
def hash_prompt(prompt: str) -> str:
    """Cache key for one summarizer call: sha256 of the exact text sent."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _summarizer_identity(summarizer: Summarizer) -> str:
    """Which backend produced the prose.

    Documented protocol attribute ``name``, falling back to the class name so
    third-party backends (OSS users writing their own Summarizer) need no change.
    """
    return str(getattr(summarizer, "name", type(summarizer).__name__))
```

`_process_node` collapses to one dict, one string, one key:

```python
def _process_node(node: Node) -> SummaryResult:
    children = index.get(node.id, [])
    req = SummaryRequest(
        node_id=node.id,
        level=_node_level(node),
        facts=_prompt_facts(_node_to_dict(node)),
        source_text=read_residual_source(repo_root, node, children),   # Part 2
        child_summaries=[results[c.id] for c in children if c.id in results],
        edges=edges_by_from.get(node.id, []),
    )

    prompt = build_prompt(req)
    cache_key = hash_prompt(_summarizer_identity(summarizer) + "\n" + prompt)

    cached = existing_cache.get(node.id)
    if cached is not None and cached.hash_input == cache_key:
        return cached
    return _call_summarizer(summarizer, req, cache_key)
```

The system node gets the same treatment (build prompt → hash → compare), replacing
`hash_input_with_children(system_req, prompt_version)`.

**Contract this creates:** a backbone must send exactly `build_prompt(req)`. Document it on the
`Summarizer` protocol docstring. `BobShellSummarizer` already does; the OpenAI/Anthropic
backends in `plan-pluggable-llm-backends.md` must too (splitting the string into
system/user messages is fine — the *text* is what is hashed).

### 1.2 Why

| # | Reason |
|---|---|
| 1 | **A cache key is only correct if it is a function of the payload.** Today's key is a hand-maintained summary of the payload. It does not cover `req.edges` at all: if handler resolution shifts or the adapter emits a new model edge, `## Relational facts` and `## Allowed fact IDs` change but the key does not, so the cached prose may cite an id it should no longer cite (or miss one it now can). This is live: D-039 added route ids to the citeable set, D-045 added model ids — nothing in the key noticed. |
| 2 | **Prompt-shaping work becomes safe.** Part 2 changes what the model sees without touching `hash_struct`/`hash_source`. Under today's key those changes are invisible and cached summaries silently survive. The alternative is remembering to bump `PROMPT_VERSION` by hand — exactly the thing an OSS user gets wrong. |
| 3 | **Nothing is lost.** Every ingredient is already inside the string: `node_id` in `## Allowed fact IDs`/`## Node facts`; `hash_struct` renders as signature/decorators/bases/fields/`is_pydantic_model`; `hash_source` renders as `## Source`; `PROMPT_VERSION` is literally line 1; child prose is the `## Child summaries` block. |
| 4 | **It removes a maintenance obligation.** `prompt_version` disappears from `run_hierarchy`'s signature and from every call site; `PROMPT_VERSION` stays (it is embedded in the prompt, so template edits still invalidate automatically) and stays useful in log lines. |
| 5 | **The double-facts dance goes away.** One `replace`/filter, one string, one key — no "hash the unfiltered dict but send the filtered one" rule to remember. |

### 1.3 Why this is not coarser (the question that decides the design)

| today's key ingredient | where it already lives in the prompt |
|---|---|
| `node_id` | `## Allowed fact IDs` (first entry) and `## Node facts.id` |
| `hash_struct` | signature (**including defaults**, which the extractor zeroes out of its synthetic AST → strictly finer), decorators, bases, keywords, fields (name + annotation + default), return annotation, `async_flag`, `is_pydantic_model` |
| `hash_source` | `## Source` (raw span) |
| `prompt_version` | first line |
| child prose hashes | `## Child summaries`, in full |

Where the old key was blind and the new one sees: `req.edges`; child **ids** (a renamed child
id changes the block headings and the allowed list); defaults; docstrings (class `hash_source`
is header-only, so a docstring edit is invisible to the old key); and which backend wrote the
text. Net: **strictly more sensitive on the node's own material, never less** — after 1.4.

### 1.4 The one place it would be coarser: `lines`

`_node_to_dict` includes `lines`, and `_PROMPT_FACTS_DROP` does not strip it, so `## Node facts`
shows `"lines": [55, 70]`. Under prompt-hash, inserting a blank line at the top of a file
changes the key for **every node in that file**, and then for their ancestors. Today
`hash_struct`/`hash_source` ignore line numbers (`include_attributes=False`, token-based), so a
pure move is free.

**Fix:** add `"lines"` to `_PROMPT_FACTS_DROP`. Nothing is lost — line numbers are not citable
and not rendered; the renderers read `node.lines` from `facts.json`, not from the prompt.

**Do not add `"file"` to that set.** `allowed_fact_ids` reads `req.facts["file"]` to make the
module id citeable from a function prompt. Dropping it would silently remove that id from the
allowed list (the node id alone is `file::func`, not `file`). If `file` is ever dropped from the
prompt, `allowed_fact_ids` must derive it from the node id instead — note in the code, do not
change it now.

Remaining over-eagerness, accepted: a whitespace-only reformat changes `## Source` and therefore
the key, where `_hash_source_span` ignored it. That is over-eager, not under-eager; if it ever
bites, the fix is in the source-block builder (pass normalised text), not in the key.

### 1.5 Backend identity in the key

Without it, landing OpenAI + Anthropic means `--backend` switches silently reuse the previous
provider's prose. With `_summarizer_identity` the key answers both "what went in" and "what
produced it". Chosen as `getattr(summarizer, "name", type(...).__name__)` so no existing test
double or third-party backend breaks; `name` becomes documented-but-optional on the protocol,
and the shipped backends should set it (`"bob_shell"`, `"openai:gpt-…"`, `"anthropic:claude-…"`,
`"stub"`, `"manual"`) to match `SummaryResult.backend`.

Deliberate consequence: re-running `docgen summarize --backend manual` after a `bob_shell` run
regenerates everything from the manual folder. That is the honest behaviour; suppressing it is a
one-line key edit if a user ever asks.

### 1.6 What does **not** change

- `hash_struct` / `hash_source` remain in `facts.json` and keep driving `check/drift.py`
  (`find_stale_pages` reads `hash_struct`) and `check/update.py`
  (`plan_update` puts `hash_source`-changed nodes into `nodes_to_resummarize`). **The extractor
  is not touched by this plan.** Only the summarize cache stops reading them.
- `base.hash_input()` stays (used by `Stub/ManualSummarizer` to fill `SummaryResult.hash_input`,
  which `_call_summarizer` overwrites anyway). Not worth churn; leave it.
- `needs_human_review` keeps `hash_input=""`, so failed nodes are always retried.
- Early cutoff keeps working: identical children → identical child block → identical parent
  prompt → identical key.
- `summaries.json` schema (`node_id`, `text`, `backend`, `hash_input`) is unchanged; only the
  length/meaning of `hash_input` stays the same (64 hex chars) but the value changes for every
  node — one full regeneration.

### 1.7 Sub-task 1.1 — implement the key swap

**Todos**

1. Add `hash_prompt(prompt)` and `_summarizer_identity(summarizer)` to `hierarchy.py`.
2. Delete `hash_input_with_children`; update the module docstring (item 3 of the header list
   describes the old key) and `run_hierarchy`'s docstring/Args.
3. Remove the `prompt_version` parameter from `run_hierarchy`; remove the
   `from ...prompts import PROMPT_VERSION` import + argument at both CLI call sites
   (`_run_summarize`, `_run_update`).
4. Add `_prompt_facts(facts) -> dict` (the `_PROMPT_FACTS_DROP` comprehension currently inlined
   in `_process_node`) and restructure `_process_node` and the system branch as in 1.1 — one
   filtered facts dict, one prompt, one key. Delete the stale comment "the cache key is still
   computed from the full dict".
5. Add `"lines"` to `_PROMPT_FACTS_DROP` with a comment explaining the prompt-hash dependency.
6. Document on the `Summarizer` protocol that `summarize` must send `build_prompt(req)`
   verbatim, and that `name` (optional) participates in the cache key.

**Tests (`tests/test_hierarchy.py`, `tests/test_bob_shell.py`)**

- Replace `test_hash_input_with_children_changes_on_prompt_version` with
  `test_prompt_hash_changes_on_child_source_and_edges` — three assertions on `build_prompt`-derived
  keys: (a) different child text → different key, (b) different `source_text` → different key,
  (c) different `edges` → different key (**new capability**). A `PROMPT_VERSION`-only change is
  no longer a parameter; the template-edit test lives in `test_prompts.py`.
- **`test_legacy_key_was_blind_to_edges` — the test that justifies the whole change.** Build a
  `SummaryRequest`, compute the *old* key with a local, test-only reproduction of the retired
  formula, change `req.edges`, compute it again, and assert they are **equal** (the old key was
  blind to the new relational fact *and* to the id it makes citeable). Then assert the
  prompt-hash key **is** different. Without this test there is no evidence in the suite that the
  old key was broken.
- **`test_prompt_hash_ignores_line_shift` — the most likely source of false positives in
  production, so it is a file-level test, not only a dict-level one.** Write two functions to a
  real file, summarize once, then prepend a blank line and shift every node's `lines` by one (the
  extractor's hashes are token-based, so they legitimately do not change). Re-run with the first
  run's cache: **0 calls**, at function, module and system level. A second, cheap assertion covers
  the same guard at the `SummaryRequest` level (`facts["lines"]` changed → key unchanged).
- `test_key_includes_backend_name` — two summarizers with different `name`/class → cache miss
  for the second even with an identical prompt.
- Drop `prompt_version=` from every `run_hierarchy(...)` call in tests (`grep -n
  "prompt_version"` — currently ~16 sites across `test_hierarchy.py` and `test_bob_shell.py`).
- Keep `test_run_hierarchy_zero_calls_on_rerun` unchanged — it is the regression guard for the
  whole idea.

---

## Part 2 — Payload deduplication: stop sending a parent its children twice

### 2.1 The principle

> **A node's prompt must contain every fact its prose is allowed to assert, and nothing whose
> only job is to restate a block already present.**

Three kinds of information, and only one of them is source code:

| kind | block | what only it can tell you |
|---|---|---|
| code as written | `## Source` | exact defaults, control flow, comments, literals, ordering |
| relationships | `## Relational facts` + allowed ids | who calls / raises / inherits / handles / accepts which model |
| meaning | `## Child summaries` | what each piece is *for*, in the words that will appear on the child's page, with the ids the citation validator will check |

A **leaf** needs kind 1 as its primary evidence. A **parent** needs kinds 2 and 3; it needs 1
only where 1 says something 3 does not. Hence:

```
residual(node) = node span − union of direct children's spans
```

which, for this repo, is the class header (75 chars), the module's imports/constants
(117 chars), or the whole span when there are no children.

Keep child summaries **in full**. Dropping them instead would (a) leave the model with ids in
`## Allowed fact IDs` that it has never seen described — it either cites them blindly or gets
flagged as `uncited_sentence`; (b) make the class paragraph contradict the method paragraphs
rendered directly beneath it; (c) re-couple parents to leaf bodies and lose the early-cutoff
property; (d) lose cross-file references that exist nowhere in the parent's own source.

### 2.2 Sub-task 2.1 — `read_residual_source`

```python
def read_residual_source(repo_root: Path, node: Node, children: list[Node]) -> str:
    """Source inside *node*'s span that no direct child already covers.

    A child is described by its own summary, so its code would otherwise appear
    twice in this node's prompt. Children in other files, and nodes with no
    children, fall back to the full span. Deterministic and whitespace-normalised
    so a reformat elsewhere in a child cannot change this node's cache key.
    """
```

**Algorithm**

1. `full = read_source_text(repo_root, node)`; if `not children` → return `full`.
2. Build the covered set: for each child whose `child.file == node.file`, the inclusive
   1-indexed range `child.lines`. (`child.lines` already starts at the first decorator line —
   `_get_decorator_start_line` — so decorators are covered too. Merge overlapping/adjacent
   ranges.)
3. Emit the lines of `full` not in the covered set, 1-indexed relative to the node span.
4. Normalise: strip trailing whitespace, collapse runs of 2+ blank lines to one, drop leading
   and trailing blank lines.
5. If nothing survives → return `""` (`build_prompt` already omits an empty `## Source`).

**Edge cases to cover in tests**

| case | expected |
|---|---|
| class with 3 method children, all spans contiguous | returns header lines only |
| class with a docstring | header includes the docstring (it is outside every method span) |
| class whose methods wrap a class-level constant or `__slots__` between them | that block is returned |
| class with no children (field-only model/dataclass) | full source — the code *is* the evidence |
| nested class inside a class (nested classes are not extracted as nodes) | its body stays in the parent residual: correct, it has no summary anywhere |
| empty module (`lines == (1, 0)`) | `""` |
| child in a different file (should not happen, but) | skipped; residual keeps the lines |
| module where the extractor produced no children (re-export `__init__.py`) | full file |

**Why this is safe for the module level:** imports are the module's own architectural signal
("this file depends on `app.db.queries`") and no child summary carries it. The residual keeps
exactly that.

**Cache interaction:** this changes `source_text` only. Under the Part 1 key it invalidates
parents automatically; under the old key it would have changed nothing at all. Another reason
Part 1 goes first.

### 2.3 Sub-task 2.2 — drop `lines` from the prompt facts

Same edit as 1.4/1.7 item 5 (one change, listed once in the code but serving both goals: less
per-node payload, and a key that ignores pure line shifts). Effect: ~1 line per prompt, plus
stability.

### 2.4 Sub-task 2.3 — concision at the lower levels (qualitative, no numeric caps)

**What we are not doing:** no word counts, no `max_tokens`, no target lengths in
`_LEVEL_FOCUS`. A number in the prompt makes the model pad to the number on trivial functions
and truncate real detail on complex ones, and `max_tokens` turns an overrun into a silently
truncated summary that still passes through the citation validator.

**What we are doing:** one shared rule string (like `_GROUNDING_RULE`), appended to the
**function and method** level instructions, so the wording lives in one place and
`PROMPT_VERSION` picks it up automatically:

```python
_CONCISION_RULE = (
    "Be concise: one sentence per distinct behaviour, and stop when the behaviour is "
    "described. Do not restate the signature, the decorators, or the return annotation "
    "as prose — they are already visible above. Do not open with framing such as "
    "\"This function is responsible for\" or close with a restatement. Never omit a "
    "factual detail in order to be shorter: mention every exception raised, every "
    "side effect, and every notable collaborator the inputs show, each with its "
    "citation. Conciseness comes from dropping filler, not from dropping facts."
)
```

Applied as `LEVEL_INSTRUCTIONS = {"function": f"{focus}\n\n{_CONCISION_RULE}\n\n{_GROUNDING_RULE}",
"method": ...}`. `class` may get it too (its median is already 778 chars; leave it out for now
and revisit after measuring).

**Why the leaves and not the parents:** a leaf has the full code in front of it, so choosing what
matters is a lossy-but-informed decision — which is what summarizing *is*. A parent compressing
its children can only drop whole children, arbitrarily, while still being allowed to cite them.

**Measurement, not assertion:** after the change, recompute the table in 0.3 (median chars per
level, and total child prose per parent) and record before/after in the log. Expect function and
method summaries to fall well below the current 3.9× ratio; if class/module prompts still look
top-heavy, revisit with real numbers rather than picking a number now.

### 2.5 Sub-task 2.4 — fan-in budget (deferred; design only)

Not built now. Recorded so the 2,000-leaf case does not require re-architecting the phase:

- Trigger: a parent with > N direct children (N ≈ 40) **and** total child prose above a char
  threshold.
- Action for children beyond the first N: send the **leading sentence + its citations** instead
  of the full prose, not a mid-sentence cut (a truncated sentence carries citations for claims
  it no longer makes).
- The ids stay in `## Allowed fact IDs` either way, and the block keeps every child heading, so
  the "structure is complete, detail is budgeted" property holds.
- Must be a pure function of the `SummaryRequest`, so the prompt-hash key keeps working.
- Default N/threshold must be high enough that this repo (max 14 children) never triggers.

### 2.6 Duplication we deliberately keep

Listed so a future reader does not "optimise" it away:

- **Child ids in both `## Allowed fact IDs` and the `## Child summaries` headings.** Cheapest
  possible redundancy; removing either breaks the citation contract.
- **`facts.signature` / `decorators` / `docstring` in `## Node facts` and again in
  `## Source`** for leaves. Splitting them means re-deriving facts from source at render time;
  the overlap is a line or two.
- **`facts.file`** — load-bearing for `allowed_fact_ids` (see 1.4).

---

## Dependency order

```
1.1  key = hash(prompt)            ← must land first: payload changes are invisible without it
      ↓
2.2  drop `lines` from prompt facts (same edit also protects the key from line shifts)
      ↓
2.1  read_residual_source           (class + module: the actual byte win)
      ↓
2.3  _CONCISION_RULE on function/method
      ↓
measure → log → (later, only if scale demands) 2.4 fan-in budget
```

---

## Files to touch

| File | Change |
|---|---|
| `src/docgen/summarize/hierarchy.py` | `hash_prompt`, `_summarizer_identity`, `read_residual_source`; delete `hash_input_with_children`; drop `prompt_version` param; `_process_node` + system branch restructure; `"lines"` in `_PROMPT_FACTS_DROP`; module/`Summarizer` docstrings |
| `src/docgen/summarize/prompts.py` | `_CONCISION_RULE` + apply to `function`/`method` in `LEVEL_INSTRUCTIONS` and fold into the `PROMPT_VERSION` payload string |
| `src/docgen/summarize/base.py` | `Summarizer` protocol docstring: must send `build_prompt(req)` verbatim; optional `name` participates in the key |
| `src/docgen/cli.py` | Remove `prompt_version=PROMPT_VERSION` at `_run_summarize` and `_run_update` |
| `tests/test_hierarchy.py` | New key tests (edges/source/child-text/line-shift/backend), residual-rendering tests, remove `prompt_version=` sites |
| `tests/test_prompts.py` | Assert `_CONCISION_RULE` present for function/method and absent from package/system; `PROMPT_VERSION` still derives from template text |
| `tests/test_bob_shell.py` | Remove `prompt_version=` at the two `run_hierarchy` calls |
| `docs/memory.md` | One design decision row (next free D-number — D-047 is contested by the backends plan) |
| `docs/tasks.md`, `docs/BOB_LOG.md` | Task entry + session log |

**Not touched:** `extract/*`, `facts/*`, `check/*`, `render/*`, `facts.json` schema,
`summaries.json` schema, the citation validator, `bob_shell.py`, `manual.py`.

---

## Verification plan

| Step | Check | Expected |
|---|---|---|
| Key semantics | `pytest tests/test_hierarchy.py -q` | cache tests pass; new tests prove edges/source/child-text/backend change the key and a line shift does not |
| Prompt content | `pytest tests/test_prompts.py -q` | concision rule scoped to function/method; `PROMPT_VERSION` still content-derived |
| Payload measurement | script over `facts.json` + `summaries.json`, same method as 0.3 | report per-level prompt chars before/after; assert nothing (report only) |
| Residual correctness | targeted tests from 2.2's edge-case table | `ArticlesRepository` residual is header-only; a field-only model keeps full source |
| Cache replay | `docgen summarize` twice with no changes | second run: 0 calls at any `--workers` |
| End-to-end regression | `docgen summarize --backend bob_shell → docgen validate → docgen render → docgen check` | all 234 regenerated once; `validate` reports **no new** broken citations (a new `unknown_id`/`uncited_sentence` class means the residual removed something a summary was citing — that is a quality regression); `check` exits **0** on unchanged code (non-zero means the prompt-hash key is producing false positives) |
| Quality spot-check (manual) | read five regenerated nodes: `ArticlesRepository` (worst case, 70-char residual), `filter_articles` (complex method), `articles_resource.py` (module with imports), one field-only Pydantic model (must still see its full source), and the `system` summary | each correct and complete; if these five are, the rest are |
| End-to-end regression | `docgen summarize --backend bob_shell → docgen validate → docgen render → docgen check` | 234 regenerated once; `validate` reports **no new** broken citations (a new `unknown_id`/`uncited_sentence` means the residual removed something a summary was citing — a quality regression); `check` exits **0** on unchanged code (non-zero means the prompt-hash key yields false positives) |
| Quality spot-check (manual) | read five regenerated nodes: `ArticlesRepository` (worst case, 70-char residual), `filter_articles` (complex method), `articles_resource.py` (module with imports), one field-only Pydantic model (must still see its full source), and the `system` summary | all five correct and complete; if they are, the rest are |
| Regression guard | `pytest -q` | green except pre-existing `test_seeded_bug` |

---

## Open decisions — resolved 2026-11-08

1. **Key includes backend identity?** **Yes** — via
   `getattr(summarizer, "name", type(summarizer).__name__)`. `StubSummarizer` declares
   `name = "stub"`; `BobShellSummarizer` / `ManualSummarizer` are unchanged in this plan and fall
   back to their class names (still distinct per backend).
2. **Drop `lines` from prompt facts?** **Yes** (1.4/2.2).
3. **Drop `file` from prompt facts?** **No** — it is how `allowed_fact_ids` makes the module
   citable from a function prompt (1.4). Left in, with a comment explaining why.
4. **Apply `_CONCISION_RULE` to `class` as well?** **No** — function and method only; measure
   before touching the class level.
5. **Keep `hash_input_with_children` as a deprecated alias?** **No** — the value it produces is
   now wrong-by-construction; a silent alias is worse than an ImportError.
6. **Ship 2.4 (fan-in budget) now?** **No** — this repo's max fan-in is 14.

---

## Risks

| Risk | Mitigation |
|---|---|
| A backend wraps or annotates the prompt before sending, so the key hashes text that was not sent | Document "send `build_prompt(req)` verbatim" on the protocol; all shipped backends comply |
| Removing class source loses class-level statements (constants, `__slots__`, metaclass kwargs) | They are residual, not children — masked code is only what has its own summary; covered by explicit tests |
| A reader sees less code and writes thinner parent prose | Child summaries stay in full; measure prompt output quality before/after, not just size |
| Prompt-hash makes a whitespace reformat regenerate many summaries | Accepted (over-eager); source-block normalisation is the escape hatch if it ever bites |
| One-time full regeneration cost | Expected: 234 calls (~6–7 min at 4 workers). Announce it in the log; `--workers` already exists |
