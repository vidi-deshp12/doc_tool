# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Architecture Constraints for `target/`

- **Tests share one real DB connection per test run, wrapped in a single rolled-back transaction.** `FakeAsyncPGPool` (in `tests/fake_asyncpg_pool.py`) makes every `pool.acquire()` return the *same* connection, so all DB work in a test is part of one transaction that is rolled back at teardown. This means tests cannot test transaction isolation or `COMMIT` behaviour.

- **No ORM — asyncpg returns raw `Record` objects.** `Record` behaves like a dict (`row["column"]`). There is no SQLAlchemy session. Repository methods manually map `Record` fields onto domain model constructors.

- **`ArticlesRepository` makes multiple sequential DB round-trips per article load.** `_get_article_from_db_record` issues separate queries for tags, favourites count, and is-favourited. This is by design (simplicity over performance) — do not try to merge them into a single query without revisiting all callers.

- **Adding a new route requires touching three files minimum**: the route handler file, `app/api/routes/api.py` (or the relevant sub-router), and `app/api/dependencies/` if new auth/lookup logic is needed.

- **`app/db/queries/tables.py` uses typed `Table` subclasses (pypika) for dynamic queries only.** Static queries use raw column name strings in `.sql` files. The two systems do not share schema definitions — keep them in sync manually when altering table structure.
