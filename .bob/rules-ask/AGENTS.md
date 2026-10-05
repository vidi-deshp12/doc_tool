# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Non-Obvious Documentation Context for `target/`

- **SQL query names are the source of truth for Python method names.** `-- name: get-article-by-slug^` in a `.sql` file becomes `queries.get_article_by_slug()` in Python (hyphens → underscores). The suffix (`^`, `!`, `<!`, `*!`) is stripped from the method name but controls return behaviour.

- **`app/db/queries/queries.pyi` is a manually maintained stub file** — it is not auto-generated. It exists purely for mypy type-checking of `aiosql`-generated methods. When looking up what arguments a query accepts, read this file.

- **Two separate article router files serve the same `/articles` prefix.** `articles_resource.py` handles CRUD; `articles_common.py` handles feed and favourites. They are merged in `app/api/routes/articles/api.py`. There is no functional difference between them — the split is organisational only.

- **`app/core/settings/` has four environments**: `base`, `development`, `production`, `test`. The active one is selected by the `APP_ENV` env var. Tests force `APP_ENV=test` in `conftest.py` before any imports.

- **JWT prefix is `Token`, not `Bearer`.** All documentation and test fixtures use `"Token <jwt>"` format.
