# Project Roadmap

Deadline: **Oct 18, 2026, 11:59 PM ET.** Plan to submit **Oct 17**. Calendar below starts Oct 5 (13 days left; Oct 4 went to planning and setup). Detailed tasks are in `tasks.md`. **A phase's gate must pass before the next phase starts.**

## Calendar

| Dates | Phase | Gate (must pass to continue) |
|---|---|---|
| Oct 5-6 | **0 + 1:** repo, environment, rules, Bob Shell check, ground truth, seeded bug (broad exploration skipped; the existing request-trace session is just logged) | Bob follows the rules file; Bob Shell decision recorded; `ground_truth.json` exists; seeded-bug test fails then passes |
| Oct 7-9 | **2a:** fact extractor + FastAPI adapter (the biggest phase) | The `ast`-only route extractor finds 100% of routes (method + handler) vs ground truth; unresolved list reviewed |
| Oct 10-11 | **2b:** cited summarizer | No broken citations; 10 summaries hand-checked; unchanged re-run = 0 calls |
| Oct 12-13 | **3:** renderers + freshness | The three freshness tests pass; harmless edits don't trigger drift |
| Oct 13-14 | **3e:** minimal eval + showcase repo | Metrics reproducible with one command |
| Oct 14-16 | **4:** bug-fix story, feature, viewer, deploy (start the demo script on Oct 14) | Live URL works from a clean browser; story works in one take |
| Oct 16-17 | **5:** README, deck, video, submit | A stranger can follow the README and run the tests |
| Oct 18 | Buffer only | |

Reality check: phases 0 and 1 hold nine tasks in two days, and 2a holds eleven in three. If a phase slips, use the time-pressure rules below instead of moving the deadline.

## What each phase produces

| Phase | Produces | Consumed by |
|---|---|---|
| 1 | `eval/ground_truth.json`, seeded bug + failing test, understanding of target | 2a (grading), 4 (story) |
| 2a | `generated/facts.json` (nodes, edges, unresolved) | 2b, 3 |
| 2b | `generated/summaries.json` + validation report | 3 |
| 3 | `generated/pages/*.md`, `manifest.json`, `check`/`update` | 3.5, 4 |
| 3.5 | Results table (recall, claim precision, drift false positives, incremental savings) | Deck, README |
| 4 | Fixed bug, new feature, live demo | Deck, video |

## Time-pressure rules (14 days is short)
1. Tier-3 items are cut without discussion (ERD, full call graph, config/env facts, middleware, nested functions, git history).
2. Tier-2 items (aiosql linking, annotation-based call matching, Flask adapter) start only after the Phase 3 gate passes and only if on schedule.
3. If Phase 2a slips past Oct 7, drop dependency-tree depth to one level and cut the `calls` facts; keep routes + `raises`.
4. The eval harness can be minimal: route recall (automatic) + 30 hand-graded claims + one drift test suite.
5. Start the demo video script on Oct 14, not Oct 16.
6. Task 1.1 (broad exploration of the target) is already reduced to logging the existing trace; do not expand it.

## Using Bob (30% of the score)
- Use Bob from day one for planning (Plan), coding (Code), review (Review), exploration (Ask).
- Log every substantial session in `BOB_LOG.md` with a screenshot; capture Bobalytics stats weekly.
- If Bob Shell can be scripted, the pipeline calls it; otherwise Bob writes summaries in the IDE and the tool validates them. Either way, show it in the demo.

## Demo storyline
"Here's a repo nobody documented. One command produces cited docs and diagrams. A seeded bug: the docs show where to look; Bob fixes it. I re-run the check, and only the affected pages update. Here are our measured accuracy numbers, and the same core on a Flask repo it had never seen."

## Future roadmap (for the deck)
Flask and Django adapters; call-graph resolution via type annotations; ERD from migrations; git-history "why"; CI bot that opens a PR with doc updates; grounded Q&A.
