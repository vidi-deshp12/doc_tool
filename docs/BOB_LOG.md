# Bob Log

Evidence that IBM Bob was a core part of the workflow (judging: tool usage and depth, 30%).

## How to keep this log
- One entry per substantial Bob session (planning, coding, review, debugging, exploration). Skip trivial one-line questions.
- Dates use `YYYY-MM-DD`. Newest entries at the **bottom**.
- Save screenshots to `docs/bob-screenshots/` named `YYYY-MM-DD_<mode>_<short-title>.png` and reference them in the entry.
- Always record the **task ID** from `docs/tasks.md`, and what you checked yourself.
- Take a **Bobalytics snapshot** at least once a week (table at the bottom).
- Bob updates this file after each task, using the template below. Keep the same field names so entries stay consistent.

## Entry template (copy this)

```markdown
### YYYY-MM-DD | Task <ID> | <Mode: Ask / Plan / Code / Review / Shell / Orchestrator>
- **Goal:** one line.
- **Prompt (short):** the key instruction given to Bob.
- **What Bob produced:** files created/changed, or a summary of the answer.
- **What I verified or changed:** how the output was checked; what Bob got wrong.
- **Outcome:** done / partly done / blocked. Tests run and their result.
- **Screenshot:** `docs/bob-screenshots/<file>.png`
```

---

## Entries

### 2026-10-04 | Task 1.1 (exploration, reduced) | Ask
- **Goal:** Understand how the target app handles a "create article" request.
- **Prompt (short):** Trace what happens when a client sends a POST request to create a new article, step by step, naming files and functions.
- **What Bob produced:** An eight-step trace: CORS middleware in `main.py`; routing through `api/routes/api.py` to `create_new_article`; auth dependency (`get_current_user_authorizer`, JWT decode, user lookup); DB connection dependency (`get_repository`); request-body parsing into `ArticleInCreate` (alias `tagList` to `tags`); the handler generating a slug and checking for duplicates; `ArticlesRepository.create_article` running a transaction with SQL from `articles.sql`; response built with `ArticleForResponse` / `ArticleInResponse`, status 201.
- **What I verified or changed:** Not yet verified against the code. One claim looks doubtful: that body validation errors (422) happen before the auth dependency (403). To check by experiment (see `docs/memory.md`, unverified claims).
- **Outcome:** Useful orientation; confirmed that SQL lives in `.sql` files (aiosql-style), which matters for the gaps list.
- **Screenshot:** `docs/bob-screenshots/2026-10-04_ask_request-trace.png` *(add)*

<!-- Add new entries below this line -->

---

## Bobalytics snapshots

| Date | What the dashboard shows (contribution, sessions, etc.) | Screenshot |
|---|---|---|
| *(first snapshot)* | | `docs/bob-screenshots/<file>.png` |

## Summary for the deck (fill in near the end)
- Number of Bob sessions by mode (Ask / Plan / Code / Review / Shell):
- Tasks where Bob did most of the work:
- Bugs Bob caught in review mode:
- Things Bob got wrong and how we caught them:
