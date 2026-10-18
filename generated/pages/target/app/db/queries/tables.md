# tables

[`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) is the central module that defines typed pypika table representations and a custom query parameter class for use throughout the application's database query layer [[target/app/db/queries/tables.py]].

The foundation is `TypedTable`, a subclass of pypika's `Table` that adds a convention-based name resolution mechanism [[target/app/db/queries/tables.py::TypedTable]]. When a subclass sets the `__table__` class attribute to a non-empty string, `TypedTable` uses that as the database table name; if `__table__` is left empty and no explicit `name` is passed to the constructor, it falls back to the class's own `__name__` [[target/app/db/queries/tables.py::TypedTable::__init__]]. This makes subclassing clean and declarative, since each table class only needs to declare its fields and a `__table__` string rather than passing the name at construction time [[target/app/db/queries/tables.py::TypedTable]].

Five concrete table classes are built on top of `TypedTable`. `Users` maps to the `"users"` table and exposes `id` and `username` fields [[target/app/db/queries/tables.py::Users]]. `Articles` maps to the `"articles"` table and covers all core article columns: `id`, `slug`, `title`, `description`, `body`, `author_id`, `created_at`, and `updated_at` [[target/app/db/queries/tables.py::Articles]]. `Tags` maps to the `"tags"` table and declares a single `tag` field [[target/app/db/queries/tables.py::Tags]]. `ArticlesToTags` maps to the `"articles_to_tags"` join table, holding `article_id` and `tag` to represent the many-to-many relationship between articles and tags [[target/app/db/queries/tables.py::ArticlesToTags]]. `Favorites` maps to the `"favorites"` table with `article_id` and `user_id`, capturing which users have favorited which articles [[target/app/db/queries/tables.py::Favorites]].

Alongside the table classes, the module defines `Parameter`, a thin subclass of pypika's `CommonParameter` [[target/app/db/queries/tables.py::Parameter]]. Its sole purpose is to reformat an integer index into the asyncpg positional placeholder syntax (`$1`, `$2`, etc.), which asyncpg requires instead of the `?` or `%s` placeholders used by other database drivers [[target/app/db/queries/tables.py::Parameter]]. The module closes by instantiating each of the five table classes as module-level singletons (`users`, `articles`, `tags`, `articles_to_tags`, `favorites`), making them directly importable for use in query construction throughout the codebase [[target/app/db/queries/tables.py]].

## Articles

`Articles` is a typed table class defined in [`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) that maps to the `"articles"` database table [[target/app/db/queries/tables.py::Articles]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::TypedTable]], which provides the base typing contract, and is not a Pydantic model [[target/app/db/queries/tables.py::Articles]]. The class declares eight fields representing an article record: `id` (`int`), `slug` (`str`), `title` (`str`), `description` (`str`), `body` (`str`), `author_id` (`int`), `created_at` (`datetime`), and `updated_at` (`datetime`) [[target/app/db/queries/tables.py::Articles]]. No default values are set on any of these fields, meaning all are expected to be provided when an instance is constructed [[target/app/db/queries/tables.py::Articles]].

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

`ArticlesToTags` is a class defined in [`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) that maps the relationship between articles and tags in the database [[target/app/db/queries/tables.py::ArticlesToTags]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::ArticlesToTags]], which provides the typed table infrastructure shared across table definitions in this module [[target/app/db/queries/tables.py::TypedTable]]. The class is not a Pydantic model [[target/app/db/queries/tables.py::ArticlesToTags]]. It declares two fields: `article_id` of type `int`, which identifies the associated article, and `tag` of type `str`, which holds the tag value [[target/app/db/queries/tables.py::ArticlesToTags]]. The class-level `__table__` attribute is set to `"articles_to_tags"`, binding it to that database table [[target/app/db/queries/tables.py::ArticlesToTags]].

| Field | Type | Default |
|-------|------|---------|
| `article_id` | `int` |  |
| `tag` | `str` |  |

## Favorites

`Favorites` is a table-mapping class defined in [`tables.py`](target/app/db/queries/tables.py) that represents the `favorites` database table [[target/app/db/queries/tables.py::Favorites]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::Favorites]], which provides the base structure for typed table definitions [[target/app/db/queries/tables.py::TypedTable]]. The class declares two integer fields: `article_id` and `user_id`, which together capture the relationship between a user and a favorited article [[target/app/db/queries/tables.py::Favorites]]. It is not a Pydantic model; the inheritance chain runs through `TypedTable` rather than any Pydantic base class [[target/app/db/queries/tables.py::TypedTable]].

| Field | Type | Default |
|-------|------|---------|
| `article_id` | `int` |  |
| `user_id` | `int` |  |

## Parameter

`Parameter` is a thin subclass of `CommonParameter`, defined in two lines in [`tables.py`](target/app/db/queries/tables.py), and is not a Pydantic model [[target/app/db/queries/tables.py::Parameter]]. Its entire purpose is to convert an integer index into the asyncpg-style positional placeholder syntax (`$1`, `$2`, and so on) expected by asyncpg queries [[target/app/db/queries/tables.py::Parameter::__init__]]. It exposes a single constructor that accepts one argument, `count: int`, and immediately delegates to the parent class by calling `super().__init__` with the string produced by formatting `count` into the template `"${0}"` [[target/app/db/queries/tables.py::Parameter::__init__]]. No fields are declared on the class itself, and no logic beyond that integer-to-placeholder transformation is added — all further behaviour lives in `CommonParameter` [[target/app/db/queries/tables.py::Parameter]] [[target/app/db/queries/tables.py::Parameter::__init__]].

### __init__

The `__init__` method is the constructor for the `Parameter` class, accepting a single argument `count` of type `int` and returning `None` [[target/app/db/queries/tables.py::Parameter::__init__]]. Its sole purpose is to delegate to the parent class constructor by calling `super().__init__` with a formatted string argument [[target/app/db/queries/tables.py::Parameter::__init__]]. Specifically, it formats `count` into the template `"${0}"` using Python's `str.format`, producing a positional placeholder such as `$1` or `$2` — the asyncpg-style numbered parameter syntax — and passes that string up to the parent class [[target/app/db/queries/tables.py::Parameter::__init__]]. This means the class itself adds no additional logic beyond transforming an integer index into the `$n` placeholder form expected by asyncpg before handing control to the superclass [[target/app/db/queries/tables.py::Parameter]] [[target/app/db/queries/tables.py::Parameter::__init__]].

## Tags

`Tags` is a class defined in [`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) that represents the `tags` database table [[target/app/db/queries/tables.py::Tags]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::Tags]], which provides the base typed-table behaviour shared across table definitions in this module [[target/app/db/queries/tables.py::TypedTable]]. It is not a Pydantic model. The class declares a single field, `tag`, typed as `str`, which maps to the corresponding column in the underlying table [[target/app/db/queries/tables.py::Tags]]. The class-level attribute `__table__` is set to the string `"tags"`, identifying the physical table this class corresponds to [[target/app/db/queries/tables.py::Tags]].

| Field | Type | Default |
|-------|------|---------|
| `tag` | `str` |  |

## TypedTable

`TypedTable` is a subclass of pypika's `Table`, extending it with a convention-based name resolution mechanism [[target/app/db/queries/tables.py::TypedTable]]. It is not a Pydantic model [[target/app/db/queries/tables.py::TypedTable]].

The class declares a single class-level field, `__table__`, initialised to an empty string, which subclasses can override to explicitly specify the underlying database table name [[target/app/db/queries/tables.py::TypedTable]]. When no explicit `name` argument is passed to the constructor, the class first checks whether `__table__` has been set and uses that value; if `__table__` is also empty, it falls back to the class's own `__name__` as a convention-based default [[target/app/db/queries/tables.py::TypedTable::__init__]].

The constructor accepts four optional parameters — `name`, `schema`, `alias`, and `query_cls` — all defaulting to `None` [[target/app/db/queries/tables.py::TypedTable::__init__]]. Once the table name has been resolved through this fallback strategy, the constructor delegates entirely to the parent `Table` class by calling `super().__init__` with the resolved name and the remaining arguments unchanged [[target/app/db/queries/tables.py::TypedTable::__init__]]. The method raises no exceptions and returns `None` [[target/app/db/queries/tables.py::TypedTable::__init__]].

### __init__

The `__init__` method is the constructor for the `TypedTable` class, responsible for initialising a new table instance with an optional name, schema, alias, and query class [[target/app/db/queries/tables.py::TypedTable::__init__]]. It accepts four optional parameters: `name`, `schema`, `alias`, and `query_cls`, all of which default to `None` [[target/app/db/queries/tables.py::TypedTable::__init__]].

When `name` is not provided, the constructor applies a fallback resolution strategy: it first checks whether the class-level `__table__` attribute has been set, and if so uses that value as the table name; otherwise it falls back to the class's own `__name__` [[target/app/db/queries/tables.py::TypedTable::__init__]]. This means subclasses can declare a `__table__` attribute to explicitly control the underlying database table name, or simply rely on the class name as a convention-based default [[target/app/db/queries/tables.py::TypedTable]].

Once the name has been resolved, the constructor delegates entirely to the parent class by calling `super().__init__` with the resolved `name` alongside the `schema`, `alias`, and `query_cls` arguments [[target/app/db/queries/tables.py::TypedTable::__init__]]. The method returns `None` and raises no exceptions [[target/app/db/queries/tables.py::TypedTable::__init__]].

## Users

`Users` is a class defined in [`target/app/db/queries/tables.py`](target/app/db/queries/tables.py) that represents the `users` database table [[target/app/db/queries/tables.py::Users]]. It inherits from `TypedTable` [[target/app/db/queries/tables.py::TypedTable]], which provides the typed table contract it builds upon [[target/app/db/queries/tables.py::Users]]. It is not a Pydantic model [[target/app/db/queries/tables.py::Users]]. The class declares two fields: `id` of type `int` and `username` of type `str` [[target/app/db/queries/tables.py::Users]]. The `__table__` class attribute is set to `"users"`, binding this class to the underlying database table of that name [[target/app/db/queries/tables.py::Users]].

| Field | Type | Default |
|-------|------|---------|
| `id` | `int` |  |
| `username` | `str` |  |

