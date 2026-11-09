# profiles

This module defines the schema layer for profile-related API responses [[target/app/models/schemas/profiles.py]]. It imports Pydantic's `BaseModel` and the `Profile` domain model, then uses them to build a single response wrapper [[target/app/models/schemas/profiles.py]]. The only class it defines is `ProfileInResponse`, a Pydantic model that acts as the response envelope for a profile resource [[target/app/models/schemas/profiles.py::ProfileInResponse]]. It inherits directly from `BaseModel` and declares one field, `profile`, typed as `Profile`, ensuring the returned JSON always wraps the profile object under a `profile` key [[target/app/models/schemas/profiles.py::ProfileInResponse]]. Field validation and serialisation are handled automatically by Pydantic, requiring no additional boilerplate in this file [[target/app/models/schemas/profiles.py::ProfileInResponse]].

## ProfileInResponse

`ProfileInResponse` is a Pydantic model that serves as the response envelope for a profile resource [[target/app/models/schemas/profiles.py::ProfileInResponse]]. It inherits directly from `BaseModel` and declares a single field, `profile`, typed as `Profile` [[target/app/models/schemas/profiles.py::ProfileInResponse]]. Because it is a Pydantic model, field validation and serialisation are handled automatically by the framework [[target/app/models/schemas/profiles.py::ProfileInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `profile` | `Profile` |  |

