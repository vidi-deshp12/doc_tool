## This is DeepSeek's response to gaps found in the tool

I read the code paths behind each item (not just the plans) and checked the target repo's actual SQL/migrations. No files changed. Here's the discussion, grounded in what's there.

1. What I verified in code

-  render/mermaid.py  emits exactly one diagram:  CONTAINS  edges between package nodes, on the index page only. That is a directory tree, not a dependency graph —  docs/tasks.md  3.1 calls it an "import graph", and that's false. Cross-package imports ( api → services → db ) appear nowhere.
-  render/markdown.py  appends summary text verbatim.  [[id]]  is never transformed. The only links in generated docs are in the API table's Handler column.
- Worse than non-clickable: the model is already writing its own links.  generated/pages/index.md  contains  [ main.py ](target/app/main.py) . That page lives at  generated/pages/ , so the link resolves to  generated/pages/target/app/main.py  — 404. Some citations are already broken links, not just plain text.
- The viewer ( viewer/app.py ) renders with  st.markdown  +  st_mermaid ;  [[...]]  shows literally, and Mermaid already works there.
-  SQL_QUERY  /  RUNS_QUERY  and  Node.sql_name/sql_file  exist in the schema, but nothing ever creates them ( extract/core.py  hardcodes  ""  at four sites).
-  walker.py  does  rglob("*.py")  only, and excludes by substring of the resolved absolute path.  docgen.toml  excludes  "migrations" , so the DB layer is invisible twice over.
- Target reality: 24 queries across 5  .sql  files, suffix kinds  !  (write),  ^  (one row),  <  (insert returning),  *  (insert many), plain (all).  queries = aiosql.from_path(..., "asyncpg")  at module level, and 24 call sites of the form  queries.get_article_by_slug(...)  in repositories. There is also  queries.pyi , an aiosql-generated stub with every query signature — a free answer key, exactly like  eval/ground_truth.json  is for routes.
- No DDL in  .sql . The ER source is Alembic: 7  op.create_table  calls with 7  ForeignKey s and composite PKs. Parseable with  ast , no imports.
- CLI  --backend  defaults to  "stub"  (cli.py ~611), so "args.backend if explicitly set" in the backends plan is not implementable as written.
-  render_all  builds the manifest purely from facts. It never checks that summaries exist, and  check  compares facts only. So a render over a partial  summaries.json  writes 72 pages of  _(no summary yet)_  and marks them fresh. That's the real danger in soft spot (f) — not the empty pages, the manifest lying.

2. The soft spots, explained

(a) 31  uncited_sentence  errors. The validator splits on  (?<=[.!?])\s+  and demands each sentence contain a  [[id]]  or a raw CALLS name. The prose that fails is connective composition: "It is not a Pydantic model.", topic sentences, paragraph openers. Every claim is cited; the connective tissue isn't. Consequence:  validate  exits 1 on every real run, so it can never be used as a CI gate, and an OSS user's first experience is 31 red lines. It is not a correctness hole (0  unknown_id ), it's a credibility hole. The clean fix is level-dependent: sentence-level citation for function/method (where facts are dense), paragraph-level for module/package/system (where the claim was already cited in the child summary that produced the paragraph). That's principled and still deterministic. Cheap alternative — prompt "no standalone sentences" — is what already fails.

(b) One memorized repo.  fastapi-realworld-example-app  is a tutorial repo; models have seen it. Facts are extracted, so structure is safe, but prose can be recalled rather than grounded — and the citation validator is the only thing catching that. The renamed-identifier copy (routes, class names, table names changed) is the decisive test, and it's not run. Unrun too: src-layout repos, namespace packages, monorepos, syntax-error files,  TYPE_CHECKING  imports, non-ASCII. This is the OSS gate, not a nice-to-have.

(c) AST routes can't produce full paths. Tier A resolves the decorator path and literal  include_router  prefixes. The target mounts under a config-derived prefix, so you get  /{slug}  instead of  /api/articles/{slug} . Cosmetic in the table, but the route ID is  f"route:{method} {path}"  (fastapi.py:485) — two routers that each define  GET /{id}  produce the same node id, and one silently disappears along with its HANDLES/model edges. On a one-router demo that's invisible; on a real app it's a data-loss bug, not a display bug. Tier B (constant folding through module constants, settings classes,  APIRouter(prefix=...) ) fixes both.

(d) Substring excludes.  "tests" in "/home/me/latest/tests_utils.py"  is true; so is  contest/ ,  testimonials.py ,  myvenv/ . The failure is silent: files vanish from facts, docs look complete. Fix is matching path components plus  fnmatch  globs, and printing an excluded-files count so silence becomes a number. This also blocks ERD, since  "migrations"  is excluded.

(e) Importing the target runs its code. Already sandboxed to a subprocess with a timeout and dummy env, which is better than most tools. For OSS, the risk is the user's: pointing docgen at a random repo executes arbitrary  import  side effects (network, disk, env). Recommendation: make introspection opt-in ( --introspect , default off), AST-only by default, and say plainly in the README that enabling it executes the repo. That also removes the "needs a runnable app with a working venv" barrier, which is the main reason the AST path exists.

(f) Partial summaries + render. Explained above: guard it.  render  should refuse (or require  --allow-partial ) when any summarizable node lacks a summary, and never write a manifest it can't stand behind. This becomes urgent the moment checkpointing lands.

(g) No live provider in CI. All backend tests mock the SDK or  _call_bob . Nothing proves the request shape, the header parsing, or the SDK's own retry behaviour. Fix: hand-written JSON fixtures per provider (no new dep), a  docgen check-backend  command that makes one tiny call and prints backend/model/latency/tokens, and one manual smoke test in the release checklist. Full CI with keys is not worth it.

3. Retry plan: accept the direction, fix six things first

The sequencing instinct is right: this must land before the backends, because backends multiply the failure surface and because  BackendError  is the protocol they're written against. The plan is unusually honest (it even names the line numbers and says what isn't implemented). I'd accept sub-tasks 1–7 with these changes.

Two contradictions to resolve before coding:
1. Sub-task 5.2 wants a report line "N summaries were written from a placeholder child", but decision 8 explicitly refuses a degraded flag. That count is not derivable from the results without exactly the flag you rejected. Drop the line (the repair pass makes it moot: if repair succeeded, there is no placeholder child).
2.  plan-pluggable-llm-backends.md  test 3 still says "retry on first failure, success on second" — that's the pre-supersede behaviour and contradicts sub-task 1. Its todo also still returns  hash_input=hash_input(req) , the legacy value the driver overwrites. Both should be corrected so the two plans don't disagree.

Amendments:
- Checkpoint granularity defeats the purpose. The leaf batch is ~170 of 234 nodes, so "after each batch" can still lose 20 minutes of a 25-minute run. Chunk each depth batch into deterministic slices (e.g. 25 nodes) and checkpoint at each slice boundary; ordering is unchanged, so byte-identical output is preserved.
-  _call_summarizer  has an unbound variable. After the loop it prints  err.message , but  err  only exists if an exception was raised.  --retries 0  →  max_attempts=0  → loop never runs →  NameError . Clamp  max_attempts >= 1  and reject negative  --retries  in argparse.
- Auth failures raised in  __init__  bypass the whole mechanism.  BobShellSummarizer  raises  BobShellError  from  __init__  when  BOB_API_KEY  is missing, and  _build_summarizer  isn't inside the try that maps to exit 2 — you'd get a traceback and exit 1. Wrap  _build_summarizer  too, and add that test.
- Context overflow must not be fatal. A 400 "prompt too long" on one giant module should not abort a 2,000-file run. Split the concept:  FatalBackendError  = configuration/auth (exit 2, stop); a per-node "cannot summarize this node" (context overflow, output truncation) = placeholder + count +  --strict  failure. The plan currently maps 400 to fatal and says "234 placeholders" is the thing to avoid — but the opposite failure (one node kills the run) is just as bad.
-  _FATAL_STDERR  is too broad.  "not found"  will abort on a transient proxy 404. Keep fatal to auth-shaped strings ( 401 ,  403 ,  api key ,  invalid key ,  unauthorized ,  login ), and match  model not found  only when "model" is present.
- Include the exception class in messages.  str(exc)  alone gives "object has no attribute …" with no type; a bug in the prompt builder then burns 12 attempts looking like provider flakiness.
- Parse HTTP-date with  email.utils.parsedate_to_datetime , which covers IMF-fixdate plus the two obsolete formats; hand-rolling three formats is a bug farm.
- Add a shared cooldown for 429s. Sleeping per-worker means four workers each burn their own four attempts against the same exhausted window. A thread-safe "not before T" in the driver makes four workers behave like one well-mannered client — this is exactly what Groq's 30 RPM free tier will otherwise expose.
- Cap total sleep per node.  max_attempts × (1+repair_passes) × 120 s  is an hour for one unlucky node. A per-node retry-sleep budget (e.g. 5 min) plus the existing caps bounds it honestly.
-  --strict  must count missing summaries, not only placeholders. After a fatal abort the checkpoint has no system node and no failures; strict would exit 0 on an incomplete run. Define strict as "no placeholders and every summarizable node present".
- Two small ones: repair passes should share the CLI policy but default to  repair_passes=1  (2 is fine, but state the worst case in the help text); and checkpoint writes must be skipped when nothing changed in a pass, otherwise a zero-call replay writes the file 10 times.

Everything else in the plan —  BackendError  shape,  RetryPolicy  defaults,  os.replace  atomic checkpoint, the key-as-dependency-graph argument for repair, the bounded  for  loop, determinism test 18, and the "0 calls on unchanged target" regression — is right and I wouldn't change it.

4. Backends plan: right shape, five gaps

1. Cache identity is not covered. The driver's key uses  summarizer.name  (hierarchy.py  _summarizer_identity ), not  SummaryResult.backend . If  name  is just  "openai" , switching from  gpt-4o  to  llama3  or from OpenAI to Ollama reuses cached prose. Each backend must set  name  to include model and base URL ( openai:gpt-4o@default ,  openai:qwen2.5-coder@http://localhost:11434/v1 ). This is a correctness bug the plan doesn't mention.
2.  --backend  default hides intent.  default="stub"  makes CLI-vs-config precedence undecidable; switch to  default=None  and resolve.
3. The SDK retries underneath you.  openai.OpenAI()  defaults to  max_retries=2 ; that's a hidden backend retry loop, which violates "no backend retries" and ignores the driver's  Retry-After . Pass  max_retries=0  and an explicit timeout. Same for Anthropic.
4. Anthropic  max_tokens  and truncation. 4096 can truncate a system summary; a truncated reply may lose trailing citations and get flagged, or worse, pass while missing facts. Default 8192 and treat  stop_reason == "max_tokens"  as a per-node failure, not silent success.
5. No  [openai] / [anthropic]  extras. Optional dependencies can live in  pyproject.toml  as extras and remain non-mandatory; the plan's "not in pyproject at all" is stricter than needed and gives a worse error message. Extras plus the in- __init__  ImportError message is strictly better.

Also worth adding:  docgen check-backend  (one tiny call), Ollama needs  /v1  in the base URL and no key,  _run_update  must gate on the resolved backend (it currently compares  args.backend != "stub" ), and  --workers  guidance per provider belongs in  --help .

5. Diagrams: what to actually build

The current diagram is a tree of package containment. It answers "what directories exist", which the sidebar already answers, and it can never show the  api → services → db  collaboration your summaries talk about. Four diagrams, in increasing cost:
1. Package import graph (index, replaces the tree). Aggregate  IMPORTS  edges to package→package, in-repo only, dedup with a count in the label. All facts already exist. This is the single highest-value diagram change and it's one file.
2. Class/inheritance diagram per module ( classDiagram  from  INHERITS ), only on modules with ≥2 classes. Real edges, no inference.
3. ER diagram from Alembic (below), on its own  generated/pages/schema.md  rather than bloating the index.
4. Route sequence diagram — route → dependency chain ( DEPENDS_ON ,  via ) → handler → SQL. Honest only after aiosql linking; before that it stops at the handler and is too thin to be worth the page.

One correctness trap: the index manifest currently records only  system  + packages. If the diagram starts drawing  IMPORTS , an import change won't mark the page stale. Every diagram must register its fact ids in the  PageRecord , or add a synthetic diagram hash. Otherwise  check  reports clean on a stale picture — the exact failure mode the tool exists to prevent.

6. Clickable citations

This is the cheapest win on your list and needs no LLM calls (the cache key is the prompt, so render changes cost zero).

Design: at render time, build  id → (page_path, anchor)  from the graph and layout; replace  [[id]]  with  [`short_name`](relative/path.md#anchor "full::id") . Keep  summaries.json  raw — the citation format is the audit trail and the validator must keep seeing  [[id]] . Anchors need a deterministic GitHub-compatible slugger with duplicate counting (two classes with  __init__  on one page), or explicit anchors; pick one and test it. Targets: module → its page; class/function → module page + anchor; package/system → index section; route →  api.md  (row anchors are fragile; page-level is fine).

Separately, normalize the model's own links: if  [text](target/app/x.py)  maps to a node, rewrite it to that node's page; otherwise unwrap it to a code span. Shipping 404s in docs that claim navigability is worse than plain text. A validator warning for unknown link targets closes the loop.

Streamlit caveat:  st.markdown  won't scroll or navigate to  #anchors . So decide now — clickable in rendered Markdown (GitHub/static) is the deliverable, or the viewer needs an explicit "related pages" affordance under each summary. I'd do the former now, the latter only if the demo runs in Streamlit.

7. aiosql + ERD

The repo makes both unusually tractable:
- aiosql linking: parse  -- name:  comments into  sql_query  nodes ( sql:<file>::<name> ), capturing kind ( ! ^ < * ), parameter names, and the statement. For edges, don't touch call text heuristics: find module-level  X = aiosql.from_path(...) , mark  X  as an aiosql object, and resolve  X.<name>(...)  call sites (including re-imports) to  runs_query . On this target every call site is exactly  queries.<snake_name>(...) , so 24/24 should be checkable — against  queries.pyi , which is aiosql's own output, making it an independent answer key. That's the same anti-circularity trick that made route extraction credible, and it's worth stating in the README.
- ER diagram: parse the Alembic revision for  op.create_table ,  sa.Column  (type, nullable, PK, unique),  sa.ForeignKey("table.col") , and  create_primary_key . Seven tables, composite join PKs, one FK-referenced  tags.tag  — a real  erDiagram . Multi-revision repos need to apply migrations in  down_revision  order;  ALTER / DROP /rename are not followed by an  op.create_table  parser, so record them as  unresolved  rather than pretending. Add  [db] migrations = "..."  to  docgen.toml  and a dedicated non- .py  walk; don't let migration modules enter the summarizer (they're noise).
- Render: a SQL table on the module page (name, kind, params, file:line) and the statement only for the query's own page/section; add  runs_query  to the citeable edge types so repository summaries can cite real queries instead of raw  queries.create_article  text. That materially improves the prose you already paid for.

Model choice: add  NodeType.TABLE  +  EdgeType.FOREIGN_KEY  and  NodeType.SQL_QUERY  (already declared) so drift and rendering work uniformly, rather than a side  schema  blob the manifest can't track. That's a schema version bump, and the store's field list needs the new fields — small but real.

8. Recommended order

┌──────┬───────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────┐
│ Orde │ Work                                          │ Why here                                                                            │
│ r    │                                               │                                                                                     │
├──────┼───────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────┤
│ A    │ Retry/failure recovery + the amendments above │ Every later item makes runs longer and flakier. This is also the protocol the       │
│      │                                               │ backends compile against; doing it after means writing them twice                   │
│ B    │ OpenAI-compatible (incl. Ollama) → Anthropic, │ Unlocks OSS use and gives the eval a cheap provider; name/cache identity and SDK    │
│      │ config, check-backend, extras                 │ max_retries=0 land here                                                             │
│ C    │ Render truth: clickable citations, link       │ Cheap, no LLM, and the guard must exist before checkpointing can leave partial      │
│      │ normalization, render-on-partial guard        │ files                                                                               │
│ D    │ Import graph (replace the tree) + class       │ One-file diagram change with existing facts; makes the docs look like the product   │
│      │ diagrams + manifest fact ids                  │                                                                                     │
│ E    │ aiosql linking + ERD (+ route sequence        │ Needs new non-.py extraction; the sequence diagram is only honest after this        │
│      │ diagram once queries resolve)                 │                                                                                     │
│ F    │ Unseen repo + renamed-identifier copy +       │ The actual gate for open-sourcing. Run it with B's cheap backend                    │
│      │ results table                                 │                                                                                     │
└──────┴───────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────┘

I would not put the Flask adapter, a full call graph, or asyncio anywhere near this list yet.

9. Decisions I need from you

1. Citations in the page: link with the full id as hover title (my recommendation), or keep the raw  [[id]]  visible after the link?
2. Navigation target: GitHub/static Markdown only, or must the Streamlit viewer navigate too?
3. Introspection default: flip to opt-in ( --introspect ) for OSS, or keep it on?
4. Context overflow / truncation: per-node placeholder (my recommendation) rather than fatal abort?
5. Checkpoint granularity: slice the leaf batch (~25 nodes), or accept batch-level loss?
6. Strict: count missing summaries as failure (my recommendation)?
7. Diagram placement: replace the package tree with the import graph, or show both?
8. ERD scope: Alembic  create_table  only, with  ALTER / DROP  as unresolved — acceptable for v0.1?
9. OSS gate: is the second-repo + renamed-identifier run a blocker before publishing? I think it should be.

Once you pick, I'd start by folding the amendments into  plan-retry-and-failure-recovery.md  and implementing A, since everything else sits on it.