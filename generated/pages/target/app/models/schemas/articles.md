# articles

[`target/app/models/schemas/articles.py`](target/app/models/schemas/articles.py) is the articles schema module, responsible for defining the Pydantic models that shape article data as it moves in and out of the API [[target/app/models/schemas/articles.py]]. It also establishes two module-level pagination constants — `DEFAULT_ARTICLES_LIMIT` (20) and `DEFAULT_ARTICLES_OFFSET` (0) — that are reused by the filter model [[target/app/models/schemas/articles.py]].

The module's schemas divide naturally into request shapes, response shapes, and a query-filter shape. On the request side, `ArticleInCreate` captures the data needed to create a new article: the required `title`, `description`, and `body` strings, plus an optional `tags` list exposed under the alias `"tagList"` [[target/app/models/schemas/articles.py::ArticleInCreate]]. `ArticleInUpdate` handles partial edits by making all three text fields — `title`, `description`, and `body` — `Optional[str]` defaulting to `None`, so a caller can supply any combination without being forced to repeat unchanged values [[target/app/models/schemas/articles.py::ArticleInUpdate]].

On the response side, `ArticleForResponse` is the central building block: it inherits the full set of article domain fields from `Article` and adds its own `tags` field (aliased `"tagList"`), producing the complete shape used whenever a single article is serialised for the API [[target/app/models/schemas/articles.py::ArticleForResponse]]. `ArticleInResponse` wraps that shape in a single `article` field of type `ArticleForResponse`, forming the envelope returned by single-article endpoints [[target/app/models/schemas/articles.py::ArticleInResponse]]. For list endpoints, `ListOfArticlesInResponse` holds an `articles` field typed as `List[ArticleForResponse]` together with a required `articles_count` integer, covering both the result set and its total count in one response object [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]].

`ArticlesFilters` stands apart from the request/response pair as a query-parameter model: it inherits directly from `BaseModel` rather than `RWSchema` and bundles the three optional string filters `tag`, `author`, and `favorited` with `limit` and `offset` pagination fields, the latter two constrained by the module-level defaults and validated lower bounds [[target/app/models/schemas/articles.py::ArticlesFilters]]. All five schemas that participate in API serialisation — `ArticleForResponse`, `ArticleInCreate`, `ArticleInResponse`, `ArticleInUpdate`, and `ListOfArticlesInResponse` — inherit from `RWSchema`, which provides the shared camelCase aliasing behaviour throughout the module [[target/app/models/schemas/articles.py::ArticleForResponse]] [[target/app/models/schemas/articles.py::ArticleInCreate]] [[target/app/models/schemas/articles.py::ArticleInResponse]] [[target/app/models/schemas/articles.py::ArticleInUpdate]] [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]].

## ArticleForResponse

`ArticleForResponse` is a Pydantic model defined in the articles schemas module that composes two base classes: `RWSchema` and `Article` [[target/app/models/schemas/articles.py::ArticleForResponse]]. By inheriting from `RWSchema`, it gains automatic camelCase aliasing for serialization [[target/app/models/schemas/rwschema.py::RWSchema]]. Through its `Article` base it inherits the core article fields: `slug`, `title`, `description`, `body`, `author` (typed as `Profile`), `favorited`, `favorites_count`, `id_` (exposed under the alias `"id"` with a default of `0`), `created_at`, and `updated_at` [[target/app/models/domain/articles.py::Article]]. On top of those inherited fields, `ArticleForResponse` declares one field of its own — `tags`, a `List[str]` exposed under the alias `"tagList"` — making it the shape used when an article is serialized for an API response [[target/app/models/schemas/articles.py::ArticleForResponse]].

| Field | Type | Default |
|-------|------|---------|
| `tags` | `List[str]` | `Field(..., alias='tagList')` |
| `slug` | `str` |  |
| `title` | `str` |  |
| `description` | `str` |  |
| `body` | `str` |  |
| `author` | `Profile` |  |
| `favorited` | `bool` |  |
| `favorites_count` | `int` |  |
| `id_` | `int` | `Field(0, alias='id')` |
| `created_at` | `datetime.datetime` | `None` |
| `updated_at` | `datetime.datetime` | `None` |

## ArticleInCreate

`ArticleInCreate` is a Pydantic model that captures the data required to create a new article [[target/app/models/schemas/articles.py::ArticleInCreate]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared base configuration for request/response schemas in this application. The class declares four fields: `title`, `description`, and `body`, all typed as `str`, plus `tags`, typed as `List[str]` with a default of an empty list and exposed under the alias `"tagList"` [[target/app/models/schemas/articles.py::ArticleInCreate]]. Because the alias `"tagList"` is declared explicitly via `Field`, it overrides any automatic camelCase aliasing that `RWSchema` would otherwise apply to a field named `tags` [[target/app/models/schemas/articles.py::ArticleInCreate]] [[target/app/models/schemas/rwschema.py::RWSchema]].

| Field | Type | Default |
|-------|------|---------|
| `title` | `str` |  |
| `description` | `str` |  |
| `body` | `str` |  |
| `tags` | `List[str]` | `Field([], alias='tagList')` |

## ArticleInResponse

`ArticleInResponse` is a Pydantic model defined in the articles schema module [[target/app/models/schemas/articles.py::ArticleInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared schema configuration for the application's response models [[target/app/models/schemas/articles.py::ArticleInResponse]]. The class declares a single field, `article`, typed as `ArticleForResponse`, which holds the article data to be returned in an API response [[target/app/models/schemas/articles.py::ArticleInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `article` | `ArticleForResponse` |  |

## ArticleInUpdate

`ArticleInUpdate` is a Pydantic model that represents the payload for updating an existing article [[target/app/models/schemas/articles.py::ArticleInUpdate]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the base schema configuration shared across request/response models in this application. All three of its fields — `title`, `description`, and `body` — are typed as `Optional[str]` and default to `None`, meaning a caller may supply any combination of them or none at all to perform a partial update [[target/app/models/schemas/articles.py::ArticleInUpdate]]. Because every field is optional, the model imposes no required attributes, making it well-suited for HTTP PATCH-style semantics where only the fields that need changing are sent [[target/app/models/schemas/articles.py]].

| Field | Type | Default |
|-------|------|---------|
| `title` | `Optional[str]` | `None` |
| `description` | `Optional[str]` | `None` |
| `body` | `Optional[str]` | `None` |

## ArticlesFilters

`ArticlesFilters` is a Pydantic model that inherits from `BaseModel` and is responsible for encapsulating the filter and pagination parameters used when querying a list of articles [[target/app/models/schemas/articles.py::ArticlesFilters]].

It exposes three optional string filters — `tag`, `author`, and `favorited` — each defaulting to `None`, allowing callers to narrow results by any combination of article tag, author identity, or the username of a user who has favourited the article [[target/app/models/schemas/articles.py::ArticlesFilters]]. Pagination is handled by two integer fields: `limit`, which defaults to `DEFAULT_ARTICLES_LIMIT` and is constrained to be at least `1`, and `offset`, which defaults to `DEFAULT_ARTICLES_OFFSET` and must be `0` or greater [[target/app/models/schemas/articles.py::ArticlesFilters]].

| Field | Type | Default |
|-------|------|---------|
| `tag` | `Optional[str]` | `None` |
| `author` | `Optional[str]` | `None` |
| `favorited` | `Optional[str]` | `None` |
| `limit` | `int` | `Field(DEFAULT_ARTICLES_LIMIT, ge=1)` |
| `offset` | `int` | `Field(DEFAULT_ARTICLES_OFFSET, ge=0)` |

## ListOfArticlesInResponse

`ListOfArticlesInResponse` is a Pydantic model that inherits from `RWSchema` and represents a paginated list of articles for use in API responses [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]]. It extends `RWSchema`, which provides shared serialisation behaviour across schema types [[target/app/models/schemas/rwschema.py::RWSchema]]. The class declares two fields: `articles`, typed as `List[ArticleForResponse]`, which holds the collection of article objects, and `articles_count`, typed as `int`, which records the total number of articles in the list [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]]. Both fields carry no default values, making them required when constructing an instance [[target/app/models/schemas/articles.py]].

| Field | Type | Default |
|-------|------|---------|
| `articles` | `List[ArticleForResponse]` |  |
| `articles_count` | `int` |  |

