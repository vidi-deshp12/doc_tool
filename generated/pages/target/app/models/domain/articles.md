# articles

The file `target/app/models/domain/articles.py` defines the core domain model for articles within the application [[target/app/models/domain/articles.py]]. Its sole export is the `Article` class, a Pydantic model that represents a fully realised published article [[target/app/models/domain/articles.py::Article]].

`Article` composes three base classes — `IDModelMixin`, `DateTimeModelMixin`, and `RWModel` — to inherit identity, timestamp, and serialisation behaviour without duplicating that logic [[target/app/models/domain/articles.py::Article]]. Through `IDModelMixin` it receives an `id_` integer field aliased to the JSON key `"id"`, and through `DateTimeModelMixin` it gains `created_at` and `updated_at` datetime fields that track the article's lifecycle [[target/app/models/domain/articles.py::Article]].

On top of those inherited fields, `Article` declares eight fields of its own [[target/app/models/domain/articles.py::Article]]. The `slug` and `title` strings carry the URL-friendly identifier and human-readable headline, while `description` and `body` hold the short summary and full article content respectively [[target/app/models/domain/articles.py::Article]]. A `tags` field typed as `List[str]` associates the article with zero or more topic labels, and an `author` field typed as `Profile` links the article directly to the user who wrote it [[target/app/models/domain/articles.py::Article]]. Rounding out the model, `favorited` is a boolean indicating whether the article has been favourited by the requesting user, and `favorites_count` is an integer recording the total number of times it has been favourited across all users [[target/app/models/domain/articles.py::Article]].

## Article

`Article` is a Pydantic domain model that represents a published article in the application [[target/app/models/domain/articles.py::Article]]. It inherits from three base classes: `IDModelMixin`, `DateTimeModelMixin`, and `RWModel`, combining identity, timestamp, and serialisation behaviour into a single type [[target/app/models/common.py::IDModelMixin]] [[target/app/models/common.py::DateTimeModelMixin]] [[target/app/models/domain/rwmodel.py::RWModel]].

From `IDModelMixin` it gains an `id_` field of type `int`, declared with `Field(0, alias="id")` so that the JSON key `"id"` maps to the Python attribute `id_` [[target/app/models/common.py::IDModelMixin]]. From `DateTimeModelMixin` it gains `created_at` and `updated_at` fields, both typed as `datetime.datetime` and defaulting to `None`, which track when the article was created and last modified [[target/app/models/common.py::DateTimeModelMixin]].

The class defines eight fields of its own: `slug` and `title` hold the URL-friendly identifier and human-readable headline of the article as plain strings, while `description` and `body` carry the short summary and full content respectively [[target/app/models/domain/articles.py::Article]]. `tags` is a `List[str]` that associates the article with zero or more topic labels, and `author` is typed as `Profile`, linking the article to the user who wrote it [[target/app/models/domain/articles.py::Article]]. Finally, `favorited` is a `bool` indicating whether the article has been favourited (typically by the requesting user), and `favorites_count` is an `int` recording the total number of times the article has been favourited [[target/app/models/domain/articles.py::Article]].

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

