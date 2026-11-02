# tags

The [`tags.py`](target/app/models/schemas/tags.py) module defines the schema used to represent a collection of tags in API responses [[target/app/models/schemas/tags.py]]. It contains a single class, `TagsInList`, which is a Pydantic model inheriting from `BaseModel` [[target/app/models/schemas/tags.py::TagsInList]]. Its sole responsibility is to wrap a list of tag strings into a structured response object [[target/app/models/schemas/tags.py::TagsInList]]. It exposes one field, `tags`, typed as `List[str]`, with no default value, meaning the field is required whenever the model is instantiated [[target/app/models/schemas/tags.py::TagsInList]].

## TagsInList

`TagsInList` is a Pydantic model that inherits from `BaseModel` [[target/app/models/schemas/tags.py::TagsInList]]. Its sole responsibility is to represent a list of tag strings as a structured response object [[target/app/models/schemas/tags.py::TagsInList]]. It declares a single field, `tags`, typed as `List[str]`, with no default value [[target/app/models/schemas/tags.py::TagsInList]].

| Field | Type | Default |
|-------|------|---------|
| `tags` | `List[str]` |  |

