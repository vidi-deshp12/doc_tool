# articles

This module defines the `Article` domain model, which is the canonical representation of a full article object within the application [[target/app/models/domain/articles.py]].

The single class it exports, `Article`, is a Pydantic model that inherits from three base classes — `IDModelMixin`, `DateTimeModelMixin`, and `RWModel` — combining identity, timestamp, and serialisation behaviour into one type [[target/app/models/domain/articles.py::Article]]. From its own definition it carries nine fields: `slug`, `title`, `description`, and `body` are plain strings; `tags` is a `List[str]`; `author` is a `Profile`; `favorited` is a `bool`; and `favorites_count` is an `int` [[target/app/models/domain/articles.py::Article]]. Through `IDModelMixin` it gains an `id_` field typed `int`, declared with `Field(0, alias="id")` so it serialises under the key `"id"` [[target/app/models/domain/articles.py::Article]]. Through `DateTimeModelMixin` it inherits `created_at` and `updated_at`, both typed `datetime.datetime` [[target/app/models/domain/articles.py::Article]]. The `RWModel` base provides the shared Pydantic configuration — including camelCase aliasing — that all domain models in the project rely on [[target/app/models/domain/articles.py::Article]].

## Article

`Article` is a Pydantic model that represents a full article domain object [[target/app/models/domain/articles.py::Article]]. It inherits from three base classes: `IDModelMixin`, `DateTimeModelMixin`, and `RWModel` [[target/app/models/common.py::IDModelMixin]] [[target/app/models/common.py::DateTimeModelMixin]] [[target/app/models/domain/rwmodel.py::RWModel]].

From its own definition it carries nine fields: `slug`, `title`, `description`, and `body` are all plain strings; `tags` is a `List[str]`; `author` is a `Profile`; `favorited` is a `bool`; and `favorites_count` is an `int` [[target/app/models/domain/articles.py::Article]]. Through `IDModelMixin` it also gains an `id_` field typed `int`, declared with `Field(0, alias="id")` so it serialises under the key `"id"` [[target/app/models/common.py::IDModelMixin]]. Through `DateTimeModelMixin` it inherits `created_at` and `updated_at`, both typed `datetime.datetime` and defaulting to `None` [[target/app/models/common.py::DateTimeModelMixin]]. The `RWModel` base provides the shared Pydantic configuration — such as camelCase aliasing — that the rest of the domain models rely on [[target/app/models/domain/rwmodel.py::RWModel]].

| Field | Type | Default |
|-------|------|---------|
| `slug` | `str` |  |
| `title` | `str` |  |
| `description` | `str` |  |
| `body` | `str` |  |
| `tags` | `List[str]` |  |
| `author` | `Profile` |  |
| `favorited` | `bool` |  |
| `favorites_count` | `int` |  |
| `id_` | `int` | `Field(0, alias='id')` |
| `created_at` | `datetime.datetime` | `None` |
| `updated_at` | `datetime.datetime` | `None` |

