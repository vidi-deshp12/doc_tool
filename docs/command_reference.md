Command reference

Every subcommand reads a  docgen.toml , and the repository root is the directory that contains that file — not your current directory. So global behaviour is uniform:

┌───────────────────┬────────────────────────────────────────────────────────────────────────────────┐
│ Behaviour         │ Detail                                                                         │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ Config flag       │ --config PATH on every command (default docgen.toml in the current directory)  │
│ Repo root         │ The folder holding docgen.toml. All file IDs and page paths are relative to it │
│ Where output goes │ <repo root>/<output.dir> from the config (generated/ in the examples)          │
│ Prerequisites     │ Each step consumes the previous step's file. The table below shows which       │
└───────────────────┴────────────────────────────────────────────────────────────────────────────────┘

Order of operations. These are not interchangeable —  render  will not run without  facts.json  and  summaries.json .

// text
extract ──► summarize ──► [validate] ──► render ──► check ──► update
   │            │                          │          │         │
facts.json  summaries.json           pages/ +     stale page  re-render
                                    manifest.json  list      stale pages

┌───────────┬──────────────────────────────────────────────────┬─────────────────────────────────────────┬────────────────────────────────────────────┐
│ Command   │ Run it when                                      │ Needs                                   │ Produces                                   │
├───────────┼──────────────────────────────────────────────────┼─────────────────────────────────────────┼────────────────────────────────────────────┤
│ extract   │ Code changed, or first run on a repo             │ docgen.toml + source                    │ facts.json                                 │
│ summarize │ Facts changed and you want the prose refreshed   │ facts.json                              │ summaries.json                             │
│ validate  │ After generating summaries, before publishing    │ facts.json, summaries.json              │ report only, exits 1 on broken citations   │
│ render    │ Summaries are good and you want the site rebuilt │ facts.json, summaries.json              │ pages/, manifest.json                      │
│ check     │ CI, or before you start work                     │ manifest.json, facts.json               │ stale page list, exits 1                   │
│ update    │ check reported stale pages                       │ manifest.json, facts.json,              │ rewrites only stale pages                  │
│           │                                                  │ summaries.json                          │                                            │
│ eval      │ Measuring route recall against ground truth      │ —                                       │ not implemented (raises                    │
│           │                                                  │                                         │ NotImplementedError)                       │
└───────────┴──────────────────────────────────────────────────┴─────────────────────────────────────────┴────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────────────

 docgen extract 

Builds the fact graph: packages, modules, classes, functions, imports, raises, calls, routes and dependency edges. Pure  ast  walking plus one subprocess for the FastAPI adapter. Writes  facts.json  and nothing else.

When to use it: first run on a repo; after any code change (this is the step that makes  check  able to see the change); after editing  docgen.toml .

Flags:

┌───────────────┬─────────────┬─────────────────────────────────────────────────────────────────┐
│ Flag          │ Default     │ Meaning                                                         │
├───────────────┼─────────────┼─────────────────────────────────────────────────────────────────┤
│ --config PATH │ docgen.toml │ Config file to load. Its parent directory becomes the repo root │
└───────────────┴─────────────┴─────────────────────────────────────────────────────────────────┘

What it does:
1. Walks  repo.root , skipping  repo.exclude  entries, collecting  .py  files.
2. Extracts nodes/edges per file, then resolves imports, inheritance,  raises  and  calls  across files.
3. Synthesises  package  nodes from the directory layout.
4. Flags dynamic patterns (star imports,  importlib , computed  getattr ) as  unresolved  instead of guessing.
5. If  adapter.name = "fastapi" , imports  adapter.app  in a subprocess to read  app.openapi() , then maps each route to its handler and request/response models.
6. Runs the AST-only route extractor as an independent cross-check (method + relative path + handler).
7. Resolves  depends_on  edges, then reports dependency cycles.
8. Writes  <output>/facts.json .

Output: progress on stderr ( N Python files found ,  N nodes, N edges ,  adapter: N route nodes ), and on stdout the graded lines plus any warnings:

// text
AST routes: 19 route decorators found (method + relative path + handler; full paths deferred to v0.2)
DEP edges: 66/66 resolved
WARN [star_import] target/app/x.py:3 — star import hides names
12 unresolved entries (9 external_base, 3 star_import)

Unresolved entries are informational —  extract  still exits 0. Read them as "here is what static analysis could not see", not as failures.

Watch out: with the FastAPI adapter enabled, extraction imports and executes the target app. Run it on repositories you trust, inside a virtualenv, with the target's dependencies and env vars available. If the import fails you get a single  adapter_import_failed  entry and no routes; set  adapter.name = "none"  (or install the target's deps) to move on.

// bash
docgen extract
docgen extract --config ../other-project/docgen.toml

────────────────────────────────────────────────────────────────────────────────

 docgen summarize 

Walks the graph bottom-up (function → class/module → package → system) and produces cited prose for each node. Because parents receive their children's finished summaries, one call never sees the whole repo.

When to use it: after  extract , when you want current prose. On a re-run with unchanged code it makes zero calls — every node's cache key still matches — so it is safe to run routinely.

Flags:

┌───────────────────────────────────┬─────────────┬───────────────────────────────────────┐
│ Flag                              │ Default     │ Meaning                               │
├───────────────────────────────────┼─────────────┼───────────────────────────────────────┤
│ --config PATH                     │ docgen.toml │ Config file                           │
│ --backend {stub,manual,bob_shell} │ stub        │ Which summarizer writes the text      │
│ --max-cost FLOAT                  │ 2.0         │ Bobcoins ceiling per bob_shell call   │
│ --max-turns INT                   │ 10          │ Conversation turns per bob_shell call │
└───────────────────────────────────┴─────────────┴───────────────────────────────────────┘

Backends:

┌──────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┬───────────────────────┐
│ Backend  │ What it does                                                                                                     │ Needs                 │
├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────┤
│ stub     │ Deterministic placeholder text (Stub summary for <id> [[<id>]]). Real node IDs, zero cost                        │ nothing               │
│ manual   │ Reads one file per node from <output>/manual_summaries/, named after the node ID with / → _, :: → __. A missing  │ files you write by    │
│          │ file becomes a [needs_human_review] placeholder                                                                  │ hand                  │
│ bob_shel │ Pipes the deterministic prompt to bob run --format json and takes last_message; retries once after 5s, then      │ bob on PATH and       │
│ l        │ records a placeholder and continues                                                                              │ BOB_API_KEY set       │
└──────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┴───────────────────────┘

 --max-cost  /  --max-turns  apply only to  bob_shell .

Caching: the key is the node ID plus its  hash_struct  and  hash_source  plus its children's keys plus  PROMPT_VERSION . Nodes whose key matches  summaries.json  are skipped, so re-running after touching one file re-summarizes only that node and its ancestors.

A consequence worth knowing: the cache does not record which backend produced a summary. Switching  --backend  only affects nodes that need regeneration, so one  summaries.json  can legitimately mix backends. Running plain  docgen summarize  (stub) on a repo with Bob-written prose will keep the existing prose for unchanged nodes and only stub the changed ones.

// bash
docgen summarize --backend stub              # smoke test, no cost
docgen summarize --backend bob_shell --max-cost 0.1
docgen summarize --backend manual            # picks up generated/manual_summaries/

Failure behaviour: a node that fails (missing manual file,  bob  error) gets  [needs_human_review]  with an empty cache key, which means it is retried automatically next run. The run does not abort.

────────────────────────────────────────────────────────────────────────────────

 docgen validate 

Checks every  [[fact_id]]  in  summaries.json  against the node IDs in  facts.json . Mechanical, no LLM.

When to use it: after  summarize , before  render  — especially in CI, where a summary written by a model that cited a non-existent function should fail the build rather than ship.

Flags:  --config PATH  only.

Exit codes:  0  all citations resolve;  1  at least one error. The report is printed to stdout, so it reads well in CI logs.

Note what it does not prove: the cited ID exists. It does not check the sentence about it is true.

// bash
docgen validate || exit 1

────────────────────────────────────────────────────────────────────────────────

 docgen render 

Renders every page from  facts.json  +  summaries.json  and rewrites  manifest.json . Deterministic, no LLM.

When to use it: first build; after a full re-summarize; after any change that touches many pages. For a handful of changed pages,  update  is the cheaper path.

Flags:  --config PATH  only.

What it writes:

┌────────────────────────────┬──────────────────────────────────────────────────────────────────────┐
│ Path                       │ Contents                                                             │
├────────────────────────────┼──────────────────────────────────────────────────────────────────────┤
│ <output>/pages/index.md    │ System overview, package diagram (Mermaid), navigation               │
│ <output>/pages/<module>.md │ One page per module: summaries, signatures, classes, dependencies    │
│ <output>/pages/api.md      │ Endpoint table — method, full path, handler, request/response models │
│ <output>/manifest.json     │ Page → the node IDs and hash_struct values it was built from         │
└────────────────────────────┴──────────────────────────────────────────────────────────────────────┘

The manifest is the whole point: it is the record  check  later compares against. Rendering without writing it would silently disable drift detection.

// bash
docgen render
streamlit run viewer/app.py     # browse the result

────────────────────────────────────────────────────────────────────────────────

 docgen check 

Compares  manifest.json  against the current  facts.json  and lists the pages whose structural facts changed. Read-only: it never writes pages and never calls a model.

When to use it: in CI on every PR; locally before you start, to see whether the docs in front of you are still true.

Flags:

┌───────────────┬─────────────┬─────────────────────────────────────────────────┐
│ Flag          │ Default     │ Meaning                                         │
├───────────────┼─────────────┼─────────────────────────────────────────────────┤
│ --config PATH │ docgen.toml │ Config file                                     │
│ --fresh       │ off         │ Run the full extract pipeline first, then check │
└───────────────┴─────────────┴─────────────────────────────────────────────────┘

Staleness rule: a page is stale if any node it was built from has a different  hash_struct  or has disappeared from the graph.  hash_source  changes — bodies, comments, formatting — are deliberately not drift, so reindenting a file never fails your build.

Without  --fresh  it uses whatever  facts.json  is on disk. If that file predates  manifest.json  you get a warning that the check may be against stale data; the check still runs. In CI you almost always want  --fresh , because the facts on disk are from the last person's machine.

Exit codes:  0  everything fresh;  1  one or more stale pages (paths printed to stdout, one per line), or  manifest.json / facts.json  missing.

// bash
docgen check
docgen check --fresh          # CI: extract + compare in one step
docgen check --fresh || docgen update

 check  tells you what drifted. It does not fix it — that is  update .

────────────────────────────────────────────────────────────────────────────────

 docgen update 

Regenerates only the stale pages, then merges their new records into the existing manifest. This is the incremental path.

When to use it: after  check  reports stale pages and you want the docs fixed without re-rendering everything.

Flags:

┌────────────────────────────┬─────────────┬────────────────────────────────────────────────────────┐
│ Flag                       │ Default     │ Meaning                                                │
├────────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ --config PATH              │ docgen.toml │ Config file                                            │
│ --backend {stub,bob_shell} │ stub        │ Backend for optional re-summarization of changed nodes │
└────────────────────────────┴─────────────┴────────────────────────────────────────────────────────┘

What it does:
1. Recomputes the stale set (same rule as  check ). If it is empty, prints  nothing to update  and exits 0.
2. If stale nodes exist and  --backend  is not  stub , re-summarizes them through the hierarchy driver (with the usual cache, so unchanged ancestors are still skipped).
3. Re-renders each stale page —  index.md ,  api.md , or the specific module page.
4. Writes the pages and merges the updated records back into  manifest.json , leaving untouched pages' records alone.

Important:  update  does not re-extract. It reads the  facts.json  that is already on disk. After editing code the sequence is  extract  →  check  →  update . Run  update  on stale facts and it will faithfully re-render the old structure.

 --backend  accepts  stub  or  bob_shell  only ( manual  is not wired here). Re-summarization also needs  BOB_API_KEY  and  bob  on  PATH ; with the default  stub , changed nodes keep their existing prose and only tables/signatures are refreshed. That is the deliberate trade:  check / update  guarantee structural correctness immediately, while narrative accuracy waits for the next  summarize .

// bash
docgen check --fresh                 # what drifted?
docgen update --backend bob_shell    # fix it, refreshed prose included

────────────────────────────────────────────────────────────────────────────────

 docgen eval 

Registered in the CLI but not implemented — it raises  NotImplementedError . Route recall is measured elsewhere (see  eval/ground_truth.json  and the adapter tests). Don't document it as usable.

────────────────────────────────────────────────────────────────────────────────

Exit codes

┌──────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Code │ Meaning                                                                                                                 │
├──────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 0    │ Success. For check: nothing stale. For validate: all citations resolve                                                  │
│ 1    │ Something actionable: stale pages (check), citation errors (validate), or a missing prerequisite file / unknown backend │
└──────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Missing inputs fail fast with a message naming the command to run first, for example:

// text
facts.json not found at generated/facts.json; run `docgen extract` first.

Typical workflows

First run on a repo

// bash
docgen extract
docgen summarize --backend bob_shell --max-cost 0.1
docgen validate
docgen render

Day-to-day after a code change

// bash
docgen extract
docgen check --fresh      # expect exit 1 with a short page list
docgen update --backend bob_shell
docgen validate

CI gate (docs must not silently rot)

// bash
docgen check --fresh

Offline / no Bob — everything except real prose works:  extract  →  summarize --backend stub  →  render  →  check --fresh . Structure, routes, diagrams and drift detection are all intact; only the narrative is placeholder text.

Single command from a different directory

// bash
docgen check --fresh --config path/to/project/docgen.toml

The repo root follows the config file, so you never need to  cd  first.

────────────────────────────────────────────────────────────────────────────────

Two things worth flagging for your README:
- I documented  validate  even though you didn't list it — it's a real subcommand that sits between  summarize  and  render , and a manual that omits it would leave a hole.  eval  I listed only to say it's unimplemented.
- The  --backend  flag behaves differently on the two commands ( summarize  allows  manual ,  update  does not; only  summarize  takes  --max-cost / --max-turns ). That asymmetry is in  cli.py  today, so the manual states it rather than papering over it.