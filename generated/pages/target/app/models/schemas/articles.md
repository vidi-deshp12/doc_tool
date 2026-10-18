# articles

This module defines the full set of Pydantic schemas used to validate, serialise, and deserialise article data flowing into and out of the API [[target/app/models/schemas/articles.py]]. It also establishes two module-level constants — `DEFAULT_ARTICLES_LIMIT` (20) and `DEFAULT_ARTICLES_OFFSET` (0) — that act as fallback pagination values shared across the schemas [[target/app/models/schemas/articles.py]].

The central building block is `ArticleForResponse`, which combines `RWSchema` (for camelCase aliasing and serialisation conventions) with the domain model `Article` (for all core article fields such as `slug`, `title`, `description`, `body`, `author`, `favorited`, `favorites_count`, timestamps, and `id_`) through multiple inheritance [[target/app/models/schemas/articles.py::ArticleForResponse]]. The only field it adds directly is `tags`, a `List[str]` exposed under the JSON key `"tagList"` [[target/app/models/schemas/articles.py::ArticleForResponse]]. This class serves as the shared article payload type reused by the other response schemas.

`ArticleInResponse` wraps a single `ArticleForResponse` instance in an `article` field, forming the envelope returned to a caller when one article is fetched [[target/app/models/schemas/articles.py::ArticleInResponse]]. `ListOfArticlesInResponse` similarly wraps a collection: it holds an `articles` field typed as `List[ArticleForResponse]` alongside an `articles_count` integer, together forming the envelope for multi-article responses [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]]. Both inherit from `RWSchema` and therefore share the same serialisation behaviour as `ArticleForResponse` [[target/app/models/schemas/articles.py::ArticleInResponse]] [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]].

On the request side, `ArticleInCreate` captures the data needed to create a new article — required `title`, `description`, and `body` strings, plus an optional `tags` list (aliased as `"tagList"`, defaulting to an empty list) — and inherits from `RWSchema` so that incoming JSON keys are handled consistently [[target/app/models/schemas/articles.py::ArticleInCreate]]. `ArticleInUpdate` handles partial edits by declaring `title`, `description`, and `body` all as `Optional[str]` defaulting to `None`, making every field omittable and fitting PATCH-style semantics [[target/app/models/schemas/articles.py::ArticleInUpdate]].

Finally, `ArticlesFilters` stands apart from the others by inheriting directly from Pydantic's `BaseModel` rather than `RWSchema` [[target/app/models/schemas/articles.py::ArticlesFilters]]. It models the query parameters available when listing articles: optional `tag`, `author`, and `favorited` string filters, plus `limit` (minimum 1, defaulting to `DEFAULT_ARTICLES_LIMIT`) and `offset` (minimum 0, defaulting to `DEFAULT_ARTICLES_OFFSET`) for pagination, with all constraints enforced automatically at instantiation [[target/app/models/schemas/articles.py::ArticlesFilters]].

## ArticleForResponse

`ArticleForResponse` is a Pydantic model defined in [`target/app/models/schemas/articles.py`](target/app/models/schemas/articles.py) that combines the schema serialisation behaviour of `RWSchema` with the domain fields of `Article` to produce a complete article payload suitable for API responses [[target/app/models/schemas/articles.py::ArticleForResponse]]. It inherits from both `RWSchema` and `Article`, making it a multiple-inheritance Pydantic model [[target/app/models/schemas/rwschema.py::RWSchema]] [[target/app/models/domain/articles.py::Article]].

The only field declared directly on the class is `tags`, typed as `List[str]` and exposed under the JSON alias `"tagList"` via `Field(..., alias="tagList")` [[target/app/models/schemas/articles.py::ArticleForResponse]]. The remaining fields are all inherited from `Article`: `slug`, `title`, `description`, and `body` (all `str`); `author` (typed as `Profile`); `favorited` (`bool`); `favorites_count` (`int`); `id_` (an `int` stored under the alias `"id"`, defaulting to `0`); and `created_at` and `updated_at` (both `datetime.datetime`, defaulting to `None`) [[target/app/models/domain/articles.py::Article]]. Because `RWSchema` is listed as a base, all camelCase aliasing and serialisation conventions provided by that mixin apply to every field on the model [[target/app/models/schemas/rwschema.py::RWSchema]].

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

`ArticleInCreate` is a Pydantic model that represents the data required to create a new article [[target/app/models/schemas/articles.py::ArticleInCreate]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which serves as its base class. The model declares four fields: `title`, `description`, and `body`, each typed as `str`, plus `tags`, typed as `List[str]`, which defaults to an empty list and is exposed under the alias `"tagList"` [[target/app/models/schemas/articles.py::ArticleInCreate]]. This alias means that when the model is populated from incoming JSON, the field is read from the key `tagList` rather than `tags` [[target/app/models/schemas/articles.py::ArticleInCreate]]. Because it is a Pydantic model, field validation and serialisation are handled automatically by Pydantic at runtime [[target/app/models/schemas/articles.py::ArticleInCreate]].

| Field | Type | Default |
|-------|------|---------|
| `title` | `str` |  |
| `description` | `str` |  |
| `body` | `str` |  |
| `tags` | `List[str]` | `Field([], alias='tagList')` |

## ArticleInResponse

`ArticleInResponse` is a Pydantic model defined in [`articles.py`](target/app/models/schemas/articles.py) that represents the response envelope returned when a single article is fetched [[target/app/models/schemas/articles.py::ArticleInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides shared serialisation behaviour for all response and request schemas in the project [[target/app/models/schemas/articles.py::ArticleInResponse]]. The class declares a single field, `article`, typed as `ArticleForResponse`, which holds the article payload to be returned to the caller [[target/app/models/schemas/articles.py::ArticleInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `article` | `ArticleForResponse` |  |

## ArticleInUpdate

`ArticleInUpdate` is a Pydantic model used to carry the optional fields that a client may supply when updating an existing article [[target/app/models/schemas/articles.py::ArticleInUpdate]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared schema configuration for the project's request/response models [[target/app/models/schemas/articles.py::ArticleInUpdate]]. The class defines three fields — `title`, `description`, and `body` — all typed as `Optional[str]` and defaulting to `None`, meaning a caller may omit any or all of them in a partial update request [[target/app/models/schemas/articles.py::ArticleInUpdate]]. Because every field is optional with a `None` default, the model places no required attributes on the caller, making it suitable for PATCH-style semantics where only the fields that need changing are sent [[target/app/models/schemas/articles.py::ArticleInUpdate]].

| Field | Type | Default |
|-------|------|---------|
| `title` | `Optional[str]` | `None` |
| `description` | `Optional[str]` | `None` |
| `body` | `Optional[str]` | `None` |

## ArticlesFilters

`ArticlesFilters` is a Pydantic model that represents the set of query filters available when listing articles [[target/app/models/schemas/articles.py::ArticlesFilters]]. It inherits directly from `BaseModel` [[target/app/models/schemas/articles.py::ArticlesFilters]].

The model exposes three optional string filters: `tag`, `author`, and `favorited`, each defaulting to `None` when not supplied [[target/app/models/schemas/articles.py::ArticlesFilters]]. Pagination is controlled by two integer fields: `limit`, which enforces a minimum value of `1` and defaults to `DEFAULT_ARTICLES_LIMIT`, and `offset`, which enforces a minimum value of `0` and defaults to `DEFAULT_ARTICLES_OFFSET` [[target/app/models/schemas/articles.py::ArticlesFilters]]. Because it is a Pydantic model, these constraints are validated automatically at instantiation time [[target/app/models/schemas/articles.py::ArticlesFilters]].

| Field | Type | Default |
|-------|------|---------|
| `tag` | `Optional[str]` | `None` |
| `author` | `Optional[str]` | `None` |
| `favorited` | `Optional[str]` | `None` |
| `limit` | `int` | `Field(DEFAULT_ARTICLES_LIMIT, ge=1)` |
| `offset` | `int` | `Field(DEFAULT_ARTICLES_OFFSET, ge=0)` |

## ListOfArticlesInResponse

`ListOfArticlesInResponse` is a Pydantic model defined in the articles schemas module [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which serves as the shared base for response schema classes in this project [[target/app/models/schemas/articles.py]].

The class holds two fields: `articles`, typed as `List[ArticleForResponse]`, which carries the collection of article objects to be returned, and `articles_count`, typed as `int`, which records the total number of articles in that collection [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]]. Together, these two fields form the envelope used to return multiple articles in a single response payload [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `articles` | `List[ArticleForResponse]` |  |
| `articles_count` | `int` |  |

