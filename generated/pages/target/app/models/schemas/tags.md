# tags

The [`tags.py`](target/app/models/schemas/tags.py) module defines the Pydantic schema used to represent a collection of tags [[target/app/models/schemas/tags.py]]. It imports `List` from the standard `typing` module and `BaseModel` from Pydantic, which together form the basis of its single data model [[target/app/models/schemas/tags.py]].

The only class defined in this module is [`TagsInList`](target/app/models/schemas/tags.py::TagsInList), a Pydantic model that inherits directly from `BaseModel` [[target/app/models/schemas/tags.py::TagsInList]]. It declares one field, `tags`, typed as `List[str]`, which holds a list of tag name strings [[target/app/models/schemas/tags.py::TagsInList]]. The model serves as a structured container for returning or transmitting a set of tags as a validated payload [[target/app/models/schemas/tags.py::TagsInList]].

## TagsInList

`TagsInList` is a Pydantic model defined in the tags schema module [[target/app/models/schemas/tags.py::TagsInList]]. It inherits directly from `BaseModel`, making it a Pydantic-validated data class [[target/app/models/schemas/tags.py::TagsInList]]. The model declares a single field, `tags`, typed as `List[str]`, which holds a list of tag name strings [[target/app/models/schemas/tags.py::TagsInList]]. Its purpose is to represent a collection of tags as a structured response or payload container [[target/app/models/schemas/tags.py]].

| Field | Type | Default |
|-------|------|---------|
| `tags` | `List[str]` |  |

