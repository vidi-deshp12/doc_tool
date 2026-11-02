# tables

This module defines the table reference layer used to construct type-annotated pypika queries against the application's PostgreSQL database [[target/app/db/queries/tables.py]].

The foundation is `Parameter`, a thin subclass of pypika's `CommonParameter` that overrides placeholder formatting to produce asyncpg-style positional parameters — `$1`, `$2`, and so on — instead of the default style, making it compatible with the asyncpg driver used elsewhere in the application [[target/app/db/queries/tables.py::Parameter]].

Above that sits `TypedTable`, a subclass of pypika's `Table` that introduces a class-level `__table__` attribute [[target/app/db/queries/tables.py::TypedTable]]. When a subclass sets `__table__`, the constructor resolves the database table name from it automatically, falling back to the class's own `__name__` if `__table__` is absent; this lets each subclass act as a self-describing table reference without any construction-time arguments [[target/app/db/queries/tables.py::TypedTable]].

All five concrete table classes inherit from `TypedTable` and carry typed field annotations that mirror their respective database columns. `Users` maps to the `"users"` table and declares `id` and `username` [[target/app/db/queries/tables.py::Users]]. `Articles` maps to `"articles"` and declares eight fields — `id`, `slug`, `title`, `description`, `body`, `author_id`, `created_at`, and `updated_at` [[target/app/db/queries/tables.py::Articles]]. `Tags` maps to `"tags"` with a single `tag` string column [[target/app/db/queries/tables.py::Tags]]. `ArticlesToTags` maps to `"articles_to_tags"` and carries `article_id` and `tag`, representing the join between articles and their tags [[target/app/db/queries/tables.py::ArticlesToTags]]. `Favorites` maps to `"favorites"` with `article_id` and `user_id`, linking a user to a favorited article [[target/app/db/queries/tables.py::Favorites]].

The module closes by instantiating each table class once — `users`, `articles`, `tags`, `articles_to_tags`, and `favorites` — producing the shared singleton table references that query-building code imports directly [[target/app/db/queries/tables.py]].

## Articles

`Articles` is a typed table class that maps to the `"articles"` database table [[target/app/db/queries/tables.py::Articles]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::TypedTable]], which provides the base structure for table definitions in this codebase [[target/app/db/queries/tables.py]]. It is not a Pydantic model. The class declares eight fields: an integer `id`, a string `slug`, a string `title`, a string `description`, a string `body`, an integer `author_id`, and two `datetime` fields `created_at` and `updated_at` [[target/app/db/queries/tables.py::Articles]]. No default values are specified for any of these fields [[target/app/db/queries/tables.py::Articles]].

| Field | Type | Default |
|-------|------|---------|
| `id` | `int` |  |
| `slug` | `str` |  |
| `title` | `str` |  |
| `description` | `str` |  |
| `body` | `str` |  |
| `author_id` | `int` |  |
| `created_at` | `datetime` |  |
| `updated_at` | `datetime` |  |

## ArticlesToTags

`ArticlesToTags` is a table definition class that inherits from `TypedTable` [[target/app/db/queries/tables.py::ArticlesToTags]] [[target/app/db/queries/tables.py::TypedTable]]. It maps to the `"articles_to_tags"` database table and is not a Pydantic model [[target/app/db/queries/tables.py::ArticlesToTags]]. The class declares two fields: `article_id` of type `int` and `tag` of type `str`, which together represent the relationship between an article and a tag [[target/app/db/queries/tables.py::ArticlesToTags]].

| Field | Type | Default |
|-------|------|---------|
| `article_id` | `int` |  |
| `tag` | `str` |  |

## Favorites

`Favorites` is a typed table class that inherits from `TypedTable` [[target/app/db/queries/tables.py::Favorites]] [[target/app/db/queries/tables.py::TypedTable]]. It is not a Pydantic model; rather, it is a plain Python class that uses class-level annotations to declare its columns [[target/app/db/queries/tables.py::Favorites]]. The class maps to the `"favorites"` database table via the `__table__` attribute [[target/app/db/queries/tables.py::Favorites]]. It defines two integer fields: `article_id` and `user_id`, both of type `int` with no default values, representing the two foreign-key columns that link a user to a favorited article [[target/app/db/queries/tables.py::Favorites]].

| Field | Type | Default |
|-------|------|---------|
| `article_id` | `int` |  |
| `user_id` | `int` |  |

## Parameter

`Parameter` is a subclass of `CommonParameter`, defined in [`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) at lines 7–9 [[target/app/db/queries/tables.py::Parameter]]. It is not a Pydantic model. Its sole purpose is to produce asyncpg-style positional placeholders (e.g. `$1`, `$2`) for use in dynamically constructed SQL queries [[target/app/db/queries/tables.py::Parameter]].

The class exposes a single constructor, [`__init__`](target/app/db/queries/tables.py), which accepts one integer argument `count` and immediately delegates to the parent `CommonParameter` constructor by formatting `count` into the string template `"${0}"` [[target/app/db/queries/tables.py::Parameter::__init__]]. No additional fields are declared on the class itself; all state is managed by `CommonParameter` through that delegating `super().__init__` call [[target/app/db/queries/tables.py::Parameter::__init__]]. The constructor returns `None` and performs no other work [[target/app/db/queries/tables.py::Parameter::__init__]].

### __init__

The [`__init__`](target/app/db/queries/tables.py::Parameter::__init__) method initialises a `Parameter` instance by accepting a single integer argument `count` and immediately delegating to the parent class constructor via `super().__init__` [[target/app/db/queries/tables.py::Parameter::__init__]]. It formats `count` into the string template `"${0}"`, producing a positional placeholder such as `$1`, `$2`, and so on, which is the asyncpg-style numbered parameter syntax [[target/app/db/queries/tables.py::Parameter]]. The method returns `None` and performs no other work beyond this single delegating call [[target/app/db/queries/tables.py::Parameter::__init__]].

## Tags

`Tags` is a table-mapping class that inherits from `TypedTable` [[target/app/db/queries/tables.py::Tags]] [[target/app/db/queries/tables.py::TypedTable]]. It is not a Pydantic model. It maps to the `"tags"` database table via the `__table__` class attribute [[target/app/db/queries/tables.py::Tags]]. The class defines a single field, `tag`, typed as `str` [[target/app/db/queries/tables.py::Tags]].

| Field | Type | Default |
|-------|------|---------|
| `tag` | `str` |  |

## TypedTable

`TypedTable` is a subclass of pypika's `Table`, extending it with a class-level naming convention [[target/app/db/queries/tables.py::TypedTable]]. It is not a Pydantic model [[target/app/db/queries/tables.py::TypedTable]].

The class declares a single class-level field, `__table__`, initialised to an empty string, which subclasses can override to specify the target database table name without passing it explicitly at construction time [[target/app/db/queries/tables.py::TypedTable]]. No additional instance fields beyond those inherited from `Table` are introduced [[target/app/db/queries/tables.py::TypedTable]].

Its constructor accepts four optional parameters — `name`, `schema`, `alias`, and `query_cls` — all defaulting to `None` [[target/app/db/queries/tables.py::TypedTable::__init__]]. When `name` is omitted, it applies a two-step fallback: it uses the value of `__table__` if that attribute is set on the class, and otherwise falls back to the class's own `__name__` [[target/app/db/queries/tables.py::TypedTable::__init__]]. Once the name is resolved, all four arguments are forwarded unchanged to the parent `Table` constructor via `super().__init__` [[target/app/db/queries/tables.py::TypedTable::__init__]].

The overall responsibility of `TypedTable` is therefore to let subclasses act as self-describing table references: a subclass needs only to set `__table__` (or rely on its own class name) and the correct table identity is resolved automatically at construction time [[target/app/db/queries/tables.py::TypedTable]] [[target/app/db/queries/tables.py::TypedTable::__init__]].

### __init__

The [`__init__`](target/app/db/queries/tables.py::TypedTable::__init__) method is the constructor for the [`TypedTable`](target/app/db/queries/tables.py::TypedTable) class, responsible for initialising a typed table reference with an optional name, schema, alias, and query class [[target/app/db/queries/tables.py::TypedTable::__init__]]. It accepts four optional parameters — `name`, `schema`, `alias`, and `query_cls` — all of which default to `None` [[target/app/db/queries/tables.py::TypedTable::__init__]].

When `name` is not provided, the method applies a fallback strategy: it first checks whether the class-level `__table__` attribute is set, and if so uses that value as the table name; otherwise it falls back to the class's own `__name__` [[target/app/db/queries/tables.py::TypedTable::__init__]]. This design lets subclasses declare their target table via `__table__` without having to pass an explicit name at construction time [[target/app/db/queries/tables.py::TypedTable]].

Once the name is resolved, the method delegates to the parent class constructor via `super().__init__`, forwarding `name`, `schema`, `alias`, and `query_cls` unchanged [[target/app/db/queries/tables.py::TypedTable::__init__]]. The method returns `None` and raises no exceptions [[target/app/db/queries/tables.py::TypedTable::__init__]].

## Users

`Users` is a class defined in [`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) that represents the `users` database table [[target/app/db/queries/tables.py::Users]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::TypedTable]], which provides its typed table contract [[target/app/db/queries/tables.py::Users]]. The class declares two fields: `id` of type `int` and `username` of type `str` [[target/app/db/queries/tables.py::Users]]. It is not a Pydantic model; it uses plain Python class-level type annotations alongside the `__table__` attribute to identify the backing database table [[target/app/db/queries/tables.py::Users]].

| Field | Type | Default |
|-------|------|---------|
| `id` | `int` |  |
| `username` | `str` |  |

