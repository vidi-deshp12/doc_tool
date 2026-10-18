# articles

This module defines the `Article` domain model used to represent a complete article object within the application [[target/app/models/domain/articles.py]]. It imports `DateTimeModelMixin` and `IDModelMixin` from the common models layer, `Profile` from the domain profiles module, and `RWModel` from the domain base, then composes them into a single class [[target/app/models/domain/articles.py]].

The `Article` class is a Pydantic model that inherits from `IDModelMixin`, `DateTimeModelMixin`, and `RWModel` [[target/app/models/domain/articles.py::Article]]. From its own definition it declares eight fields: `slug`, `title`, `description`, and `body` are plain strings; `tags` is a list of strings; `author` is a `Profile` instance representing the article's owner; `favorited` is a boolean indicating whether the current viewer has favourited the article; and `favorites_count` is an integer recording how many users have done so [[target/app/models/domain/articles.py::Article]]. The `IDModelMixin` contributes an `id_` field typed as `int` and aliased to `"id"` for serialisation purposes, so that the wire representation uses the key `"id"` rather than the internal `id_` name [[target/app/models/domain/articles.py::Article]]. The `DateTimeModelMixin` contributes `created_at` and `updated_at` timestamp fields, both typed as `datetime.datetime` and defaulting to `None` [[target/app/models/domain/articles.py::Article]]. Because `Article` is a Pydantic model and `RWModel` applies automatic camelCase aliasing, all fields without an explicit alias are exposed in camelCase on the API boundary — while `id_` retains its own explicit `"id"` alias and is not affected by that rule [[target/app/models/domain/articles.py::Article]].

## Article

`Article` is a Pydantic model representing a full article domain object [[target/app/models/domain/articles.py::Article]]. It inherits from three base classes: `IDModelMixin`, `DateTimeModelMixin`, and `RWModel` [[target/app/models/common.py::IDModelMixin]] [[target/app/models/common.py::DateTimeModelMixin]] [[target/app/models/domain/rwmodel.py::RWModel]].

From its own definition it carries eight fields: `slug`, `title`, `description`, and `body` are all plain strings; `tags` is a list of strings; `author` is a `Profile` instance; `favorited` is a boolean; and `favorites_count` is an integer [[target/app/models/domain/articles.py::Article]]. From `IDModelMixin` it inherits `id_`, typed as `int` and declared with `Field(0, alias="id")`, meaning it is serialised and deserialised under the key `"id"` rather than `"id_"` [[target/app/models/common.py::IDModelMixin]]. From `DateTimeModelMixin` it inherits `created_at` and `updated_at`, both typed as `datetime.datetime` and defaulting to `None` [[target/app/models/common.py::DateTimeModelMixin]].

Because `Article` is a Pydantic model, all field values are validated on construction and the inherited `RWModel` base applies automatic camelCase aliasing to fields unless an explicit alias has already been declared [[target/app/models/domain/articles.py::Article]] [[target/app/models/domain/rwmodel.py::RWModel]].

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

