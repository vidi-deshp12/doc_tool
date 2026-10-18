# tags

This module defines the response schema used for returning tag data in the application [[target/app/models/schemas/tags.py]]. It contains a single class, `TagsInList`, which is a Pydantic model that inherits from `BaseModel` and exposes one field, `tags`, typed as `List[str]`, representing a collection of tag name strings [[target/app/models/schemas/tags.py::TagsInList]]. The class has no additional fields or methods beyond this declaration, making it a minimal, purpose-built schema for serialising lists of tags in API responses [[target/app/models/schemas/tags.py::TagsInList]].

## TagsInList

`TagsInList` is a Pydantic model that serves as a simple response schema for returning a collection of tags [[target/app/models/schemas/tags.py::TagsInList]]. It inherits from `BaseModel` and defines a single field, `tags`, typed as `List[str]`, which holds the list of tag name strings [[target/app/models/schemas/tags.py::TagsInList]]. The class has no additional fields or methods beyond this declaration [[target/app/models/schemas/tags.py]].

| Field | Type | Default |
|-------|------|---------|
| `tags` | `List[str]` |  |

