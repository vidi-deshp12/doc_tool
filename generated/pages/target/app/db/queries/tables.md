# tables

This module defines the typed table descriptors and query-parameter helper used to build SQL queries throughout the application [[target/app/db/queries/tables.py]].

The foundation is `TypedTable`, a subclass of pypika's `Table` that adds a declarative `__table__` class attribute for naming the underlying database table [[target/app/db/queries/tables.py::TypedTable]]. When instantiated, it resolves the table name by checking first for an explicit argument, then for `__table__`, and finally falling back to the class's own `__name__`, forwarding the result to pypika's `Table` constructor [[target/app/db/queries/tables.py::TypedTable]]. All other table descriptors in the module inherit from it.

`Users` maps to the `"users"` table and declares two fields, `id` (`int`) and `username` (`str`) [[target/app/db/queries/tables.py::Users]]. `Articles` maps to the `articles` table and carries eight fields — `id`, `slug`, `title`, `description`, `body`, `author_id`, `created_at`, and `updated_at` — covering both the article content and its authorship and timestamp metadata [[target/app/db/queries/tables.py::Articles]]. `Tags` is the simplest descriptor, representing the `tags` table with a single `tag` (`str`) field [[target/app/db/queries/tables.py::Tags]]. `ArticlesToTags` represents the join table that associates articles with tags, declaring `article_id` (`int`) and `tag` (`str`) [[target/app/db/queries/tables.py::ArticlesToTags]]. `Favorites` maps to the `"favorites"` table and holds two integer foreign-key columns, `article_id` and `user_id`, linking articles to the users who have favourited them [[target/app/db/queries/tables.py::Favorites]].

Alongside the table descriptors, the module defines `Parameter`, a thin subclass of pypika's `CommonParameter` whose sole job is to emit asyncpg-style positional placeholders such as `$1` or `$2` when building dynamic queries [[target/app/db/queries/tables.py::Parameter]]. Its constructor accepts an integer `count` and immediately formats it into the string `"${count}"` before delegating to the parent class, keeping the rest of the query-building code free of placeholder-formatting details [[target/app/db/queries/tables.py::Parameter]].

Finally, the module instantiates one module-level singleton for each descriptor — `users`, `articles`, `tags`, `articles_to_tags`, and `favorites` — so that query-building code elsewhere can reference these shared table objects directly without constructing new instances [[target/app/db/queries/tables.py]].

## Articles

`Articles` is a table-mapping class that inherits from `TypedTable` and represents the `articles` database table [[target/app/db/queries/tables.py::Articles]]. It is not a Pydantic model [[target/app/db/queries/tables.py::Articles]]. The class declares eight typed fields: `id` (`int`), `slug` (`str`), `title` (`str`), `description` (`str`), `body` (`str`), `author_id` (`int`), `created_at` (`datetime`), and `updated_at` (`datetime`) [[target/app/db/queries/tables.py::Articles]]. It inherits its structural behaviour from `TypedTable` [[target/app/db/queries/tables.py::TypedTable]], which provides the base class contract for all typed table definitions in this module [[target/app/db/queries/tables.py]].

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

`ArticlesToTags` is a class defined in [`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) that represents the `articles_to_tags` database table, mapping articles to their associated tags [[target/app/db/queries/tables.py::ArticlesToTags]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::ArticlesToTags]], which provides its base typed-table behaviour [[target/app/db/queries/tables.py::TypedTable]]. The class declares two fields: `article_id` of type `int` and `tag` of type `str`, which together form the association between an article and a tag [[target/app/db/queries/tables.py::ArticlesToTags]].

| Field | Type | Default |
|-------|------|---------|
| `article_id` | `int` |  |
| `tag` | `str` |  |

## Favorites

`Favorites` is a table-mapping class that inherits from `TypedTable` [[target/app/db/queries/tables.py::Favorites]] [[target/app/db/queries/tables.py::TypedTable]]. It is not a Pydantic model; it follows the project's own typed-table convention rather than `BaseModel` [[target/app/db/queries/tables.py::Favorites]]. The class is bound to the `"favorites"` database table via the `__table__` class attribute [[target/app/db/queries/tables.py::Favorites]]. It declares two integer fields: `article_id` and `user_id`, both of type `int` with no default values, representing the two foreign-key columns that link an article to a user in the favorites relationship [[target/app/db/queries/tables.py::Favorites]].

| Field | Type | Default |
|-------|------|---------|
| `article_id` | `int` |  |
| `user_id` | `int` |  |

## Parameter

`Parameter` is a subclass of `CommonParameter` defined in the query-building module [[target/app/db/queries/tables.py]]. It is not a Pydantic model [[target/app/db/queries/tables.py::Parameter]]. Its sole responsibility is to produce asyncpg-style numbered placeholders (such as `$1` or `$2`) for use in dynamically constructed SQL queries [[target/app/db/queries/tables.py::Parameter]].

Construction is handled entirely by [`__init__`](target/app/db/queries/tables.py::Parameter::__init__), which accepts a single integer argument `count` and immediately delegates to the parent class constructor, passing the formatted string `"${count}"` so that the rendered placeholder reflects the positional number supplied [[target/app/db/queries/tables.py::Parameter::__init__]]. No additional fields are declared on the class itself, and no value is returned from construction nor are any exceptions raised [[target/app/db/queries/tables.py::Parameter::__init__]].

### __init__

Initialises the `Parameter` instance by delegating immediately to the parent class constructor, passing the formatted string `"${count}"` (where `count` is substituted positionally) so that the parameter renders as a numbered asyncpg placeholder such as `$1` or `$2` [[target/app/db/queries/tables.py::Parameter::__init__]]. The sole input is `count`, an integer whose value determines the placeholder number embedded in the string [[target/app/db/queries/tables.py::Parameter::__init__]]. No value is returned and no exceptions are raised [[target/app/db/queries/tables.py::Parameter::__init__]].

## Tags

`Tags` is a table-mapping class defined in [`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) that represents the `tags` database table [[target/app/db/queries/tables.py::Tags]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::Tags]], which provides the base structure for typed table definitions [[target/app/db/queries/tables.py::TypedTable]]. The class declares a single field, `tag`, typed as `str`, which corresponds to the tag column in that table [[target/app/db/queries/tables.py::Tags]]. It is not a Pydantic model; it is a plain Python class extending `TypedTable` [[target/app/db/queries/tables.py::TypedTable]].

| Field | Type | Default |
|-------|------|---------|
| `tag` | `str` |  |

## TypedTable

`TypedTable` is a subclass of pypika's `Table`, extending it with a class-level `__table__` attribute that defaults to an empty string [[target/app/db/queries/tables.py::TypedTable]]. It is not a Pydantic model [[target/app/db/queries/tables.py::TypedTable]]. Its purpose is to allow subclasses to declare their database table name declaratively via `__table__`, rather than relying solely on the class name [[target/app/db/queries/tables.py::TypedTable]]. When constructing an instance, if no explicit `name` argument is provided, the constructor resolves the table name by falling back first to the class-level `__table__` attribute and, if that is also absent, to the class's own `__name__` [[target/app/db/queries/tables.py::TypedTable::__init__]]. The resolved name, together with `schema`, `alias`, and `query_cls`, is forwarded to the parent `Table` implementation via `super().__init__` [[target/app/db/queries/tables.py::TypedTable::__init__]].

### __init__

When `name` is not supplied, the constructor falls back first to the class-level `__table__` attribute and, if that is also absent, to the class's own `__name__` [[target/app/db/queries/tables.py::TypedTable::__init__]]. The resolved name, along with `schema`, `alias`, and `query_cls`, is then forwarded to the parent class via `super().__init__` [[target/app/db/queries/tables.py::TypedTable::__init__]].

## Users

`Users` is a table descriptor class defined in [`tables.py`](target/app/db/queries/tables.py) that represents the `users` database table [[target/app/db/queries/tables.py::Users]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::TypedTable]], which provides the base structure for typed table definitions [[target/app/db/queries/tables.py::Users]]. It is not a Pydantic model. The class declares two fields: `id` of type `int` and `username` of type `str` [[target/app/db/queries/tables.py::Users]]. The class-level attribute `__table__` is set to `"users"`, which identifies the underlying database table this descriptor maps to [[target/app/db/queries/tables.py::Users]].

| Field | Type | Default |
|-------|------|---------|
| `id` | `int` |  |
| `username` | `str` |  |

