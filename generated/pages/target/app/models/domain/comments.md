# comments

The module [`target/app/models/domain/comments.py`](target/app/models/domain/comments.py) defines the domain-layer representation of a comment, importing the shared mixins and base model it needs from elsewhere in the application [[target/app/models/domain/comments.py]]. Its sole export is the `Comment` model, a Pydantic class that composes identity, timestamps, and comment-specific data into a single cohesive type [[target/app/models/domain/comments.py::Comment]].

`Comment` inherits from `IDModelMixin`, `DateTimeModelMixin`, and `RWModel`, pulling in all shared structure from those bases rather than redefining it [[target/app/models/domain/comments.py::Comment]]. From `IDModelMixin` it gains an `id_` field typed as `int`, serialised under the JSON key `"id"`, which uniquely identifies each comment [[target/app/models/domain/comments.py::Comment]]. From `DateTimeModelMixin` it inherits `created_at` and `updated_at`, both `datetime.datetime` fields that track when the comment was first created and when it was last changed [[target/app/models/domain/comments.py::Comment]]. The `RWModel` base supplies the shared Pydantic configuration applied consistently across domain models in this application [[target/app/models/domain/comments.py::Comment]].

On top of those inherited fields, `Comment` adds two fields of its own: `body`, a `str` that holds the comment's text content, and `author`, a `Profile` instance that records who wrote the comment [[target/app/models/domain/comments.py::Comment]]. Together, these pieces give the type everything needed to represent a fully-formed comment — its identity, its content, its authorship, and its lifecycle timestamps — in a single validated structure [[target/app/models/domain/comments.py::Comment]].

## Comment

`Comment` is a Pydantic model [[target/app/models/domain/comments.py::Comment]] that represents a comment in the domain layer, inheriting from `IDModelMixin`, `DateTimeModelMixin`, and `RWModel` [[target/app/models/common.py::IDModelMixin]] [[target/app/models/common.py::DateTimeModelMixin]] [[target/app/models/domain/rwmodel.py::RWModel]]. It defines two fields of its own: `body`, a `str` holding the comment text, and `author`, a `Profile` instance representing who wrote the comment [[target/app/models/domain/comments.py::Comment]]. From `IDModelMixin` it inherits `id_` typed as `int` with `Field(0, alias='id')`, meaning the field is serialised and deserialised under the key `"id"` [[target/app/models/common.py::IDModelMixin]]. From `DateTimeModelMixin` it inherits `created_at` and `updated_at`, both typed as `datetime.datetime` and defaulting to `None`, which track when the comment was created and last modified [[target/app/models/common.py::DateTimeModelMixin]]. The `RWModel` base provides the shared Pydantic configuration used across domain models in this application [[target/app/models/domain/rwmodel.py::RWModel]].

| Field | Type | Default |
|-------|------|---------|
| `body` | `str` |  |
| `author` | `Profile` |  |
| `id_` | `int` | `Field(0, alias='id')` |
| `created_at` | `datetime.datetime` | `None` |
| `updated_at` | `datetime.datetime` | `None` |

