# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Coding Rules for `target/`

- **Never write inline SQL.** Add a `-- name: <query-name>[suffix]` block to the matching `app/db/queries/sql/*.sql` file, then add a type stub entry to `app/db/queries/queries.pyi`. The `queries` object is built once at startup — no registration elsewhere needed.

- **`id_` not `id`.** Domain models use `id_: int = Field(0, alias="id")`. Always construct with `id_=row["id"]`, never `id=`.

- **Dynamic queries use pypika + custom `Parameter`.** `Parameter(n)` in `app/db/queries/tables.py` emits `$n` (asyncpg positional syntax). Do not use `?` or `%s`. Add `# fmt: off` / `# fmt: on` around pypika chains so black doesn't mangle them.

- **`RWModel` auto-aliases all fields to camelCase.** When adding a field that needs a *different* alias (e.g. `tags` ↔ `tagList`), declare `Field(..., alias="tagList")` explicitly — the auto-alias will be overridden.

- **All functions must have type annotations** — mypy strict mode is enforced. `Callable` without subscript is acceptable only where FastAPI DI prevents it (existing pattern).

- **`# noqa: WPS...` is intentional** in dependency and repository files — the linter is globally configured in `setup.cfg` to suppress certain WPS rules for FastAPI DI patterns. Do not remove these comments.
