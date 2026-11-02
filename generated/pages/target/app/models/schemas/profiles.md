# profiles

The module [`target/app/models/schemas/profiles.py`](target/app/models/schemas/profiles.py) defines the response schema for user profile data, importing `Profile` from the domain layer and wrapping it for API output [[target/app/models/schemas/profiles.py]]. Its sole class, `ProfileInResponse`, is a Pydantic model that acts as a response envelope for a user profile [[target/app/models/schemas/profiles.py::ProfileInResponse]]. It inherits directly from `BaseModel` and exposes a single field, `profile`, typed as `Profile`, which gives it automatic validation and serialisation of that field at no extra cost [[target/app/models/schemas/profiles.py::ProfileInResponse]].

## ProfileInResponse

`ProfileInResponse` is a Pydantic model that serves as the response wrapper for a user profile [[target/app/models/schemas/profiles.py::ProfileInResponse]]. It inherits directly from `BaseModel` and declares a single field, `profile`, typed as `Profile` [[target/app/models/schemas/profiles.py::ProfileInResponse]]. Being a Pydantic model, it gains automatic validation and serialisation behaviour for its `profile` field at no extra cost [[target/app/models/schemas/profiles.py::ProfileInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `profile` | `Profile` |  |

