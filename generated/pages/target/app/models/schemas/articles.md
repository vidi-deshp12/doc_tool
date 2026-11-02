# articles

This module defines the Pydantic schemas used to validate and serialise article-related data flowing into and out of the API [[target/app/models/schemas/articles.py]]. It also establishes two module-level constants, `DEFAULT_ARTICLES_LIMIT` and `DEFAULT_ARTICLES_OFFSET`, which anchor the default pagination behaviour shared across the schemas [[target/app/models/schemas/articles.py]].

The central building block is `ArticleForResponse`, which merges the `RWSchema` mixin with the domain `Article` model to produce a fully populated article payload fit for API responses [[target/app/models/schemas/articles.py::ArticleForResponse]]. It inherits all core article fields from `Article` — including `slug`, `title`, `description`, `body`, `author`, `favorited`, `favorites_count`, `id_`, `created_at`, and `updated_at` — and adds a single `tags` field exposed under the alias `"tagList"`, overriding the automatic camelCase aliasing that `RWSchema` would otherwise apply [[target/app/models/schemas/articles.py::ArticleForResponse]].

Two response envelopes wrap that building block. `ArticleInResponse` acts as the top-level wrapper for a single article, exposing one field, `article`, typed as `ArticleForResponse` [[target/app/models/schemas/articles.py::ArticleInResponse]]. `ListOfArticlesInResponse` covers the collection case, pairing an `articles` list of `ArticleForResponse` items with an `articles_count` integer that records the total number of articles in the result set [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]].

On the request side, `ArticleInCreate` captures the payload for creating a new article, requiring `title`, `description`, and `body` as plain strings while accepting an optional `tags` list (aliased to `"tagList"`, defaulting to empty) [[target/app/models/schemas/articles.py::ArticleInCreate]]. `ArticleInUpdate` covers partial edits: all three of its fields — `title`, `description`, and `body` — are `Optional[str]` defaulting to `None`, so a caller may supply any subset of them in a single request [[target/app/models/schemas/articles.py::ArticleInUpdate]].

Finally, `ArticlesFilters` handles query-parameter filtering and pagination for article listings [[target/app/models/schemas/articles.py::ArticlesFilters]]. It inherits directly from `BaseModel` rather than `RWSchema`, and exposes three optional string filters — `tag`, `author`, and `favorited` — alongside `limit` (constrained to at least `1`, defaulting to `DEFAULT_ARTICLES_LIMIT`) and `offset` (constrained to at least `0`, defaulting to `DEFAULT_ARTICLES_OFFSET`), enabling callers to narrow and page through results in any combination [[target/app/models/schemas/articles.py::ArticlesFilters]].

## ArticleForResponse

`ArticleForResponse` is a Pydantic model defined in the articles schema module that combines two base classes, `RWSchema` and `Article`, to produce a fully shaped article payload suitable for API responses [[target/app/models/schemas/articles.py::ArticleForResponse]]. It inherits the `RWSchema` mixin, which provides automatic camelCase aliasing for all fields [[target/app/models/schemas/rwschema.py::RWSchema]], and the domain `Article` model, which contributes the core article fields [[target/app/models/domain/articles.py::Article]].

From the `Article` base it inherits `slug` (`str`), `title` (`str`), `description` (`str`), `body` (`str`), `author` (`Profile`), `favorited` (`bool`), `favorites_count` (`int`), `id_` (`int`, stored under the alias `"id"`), `created_at` (`datetime.datetime`), and `updated_at` (`datetime.datetime`) [[target/app/models/schemas/articles.py::ArticleForResponse]] [[target/app/models/domain/articles.py::Article]]. The one field declared directly on `ArticleForResponse` is `tags` (`List[str]`), which is exposed under the alias `"tagList"` rather than the default field name, overriding the auto-aliasing that `RWSchema` would otherwise apply [[target/app/models/schemas/articles.py::ArticleForResponse]] [[target/app/models/schemas/rwschema.py::RWSchema]].

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

`ArticleInCreate` is a Pydantic model that captures the data required when creating a new article [[target/app/models/schemas/articles.py::ArticleInCreate]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the base configuration shared across request/response schemas in this application. The class declares four fields: `title`, `description`, and `body`, all typed as `str`, plus `tags`, typed as `List[str]` and defaulting to an empty list [[target/app/models/schemas/articles.py::ArticleInCreate]]. The `tags` field is exposed under the alias `"tagList"` in serialized form, meaning incoming payloads are expected to supply that field as `tagList` rather than `tags` [[target/app/models/schemas/articles.py::ArticleInCreate]].

| Field | Type | Default |
|-------|------|---------|
| `title` | `str` |  |
| `description` | `str` |  |
| `body` | `str` |  |
| `tags` | `List[str]` | `Field([], alias='tagList')` |

## ArticleInResponse

`ArticleInResponse` is a Pydantic model defined in [`target/app/models/schemas/articles.py`](target/app/models/schemas/articles.py) that serves as the top-level response envelope for a single article [[target/app/models/schemas/articles.py::ArticleInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared base configuration for all read/write schemas in this application [[target/app/models/schemas/articles.py::ArticleInResponse]]. The class exposes a single field, `article`, typed as `ArticleForResponse`, which holds the article payload returned to the client [[target/app/models/schemas/articles.py::ArticleInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `article` | `ArticleForResponse` |  |

## ArticleInUpdate

`ArticleInUpdate` is a Pydantic model used to represent the data submitted when updating an existing article [[target/app/models/schemas/articles.py::ArticleInUpdate]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared base configuration for schema classes in this project [[target/app/models/schemas/articles.py::ArticleInUpdate]]. All three of its fields — `title`, `description`, and `body` — are typed as `Optional[str]` and default to `None`, meaning any combination of them may be omitted in a partial update request [[target/app/models/schemas/articles.py::ArticleInUpdate]].

| Field | Type | Default |
|-------|------|---------|
| `title` | `Optional[str]` | `None` |
| `description` | `Optional[str]` | `None` |
| `body` | `Optional[str]` | `None` |

## ArticlesFilters

`ArticlesFilters` is a Pydantic model that represents the set of query parameters used to filter and paginate a list of articles [[target/app/models/schemas/articles.py::ArticlesFilters]]. It inherits from `BaseModel` and carries five fields: `tag`, `author`, and `favorited` are all `Optional[str]` defaulting to `None`, allowing callers to omit any combination of them [[target/app/models/schemas/articles.py::ArticlesFilters]]. The `limit` field is an `int` constrained to be at least `1` via a `Field` declaration with a default drawn from `DEFAULT_ARTICLES_LIMIT`, while `offset` is an `int` constrained to be at least `0` with a default drawn from `DEFAULT_ARTICLES_OFFSET` [[target/app/models/schemas/articles.py::ArticlesFilters]]. Together, `limit` and `offset` support standard pagination, and the three optional string filters allow narrowing results by tag, author username, or the username of a user who has favourited the articles [[target/app/models/schemas/articles.py::ArticlesFilters]].

| Field | Type | Default |
|-------|------|---------|
| `tag` | `Optional[str]` | `None` |
| `author` | `Optional[str]` | `None` |
| `favorited` | `Optional[str]` | `None` |
| `limit` | `int` | `Field(DEFAULT_ARTICLES_LIMIT, ge=1)` |
| `offset` | `int` | `Field(DEFAULT_ARTICLES_OFFSET, ge=0)` |

## ListOfArticlesInResponse

`ListOfArticlesInResponse` is a Pydantic model that represents a paginated collection of articles returned from the API [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides shared serialisation behaviour for response schemas in this application [[target/app/models/schemas/articles.py]]. The class declares two fields: `articles`, a list of `ArticleForResponse` items, and `articles_count`, an integer representing the total number of articles in the collection [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `articles` | `List[ArticleForResponse]` |  |
| `articles_count` | `int` |  |

