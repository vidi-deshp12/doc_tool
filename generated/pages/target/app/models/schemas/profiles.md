# profiles

This module defines the response schema used when returning profile data from the API [[target/app/models/schemas/profiles.py]]. It contains a single class, `ProfileInResponse`, which is a Pydantic model that inherits from `BaseModel` and declares one field, `profile`, typed as `Profile` [[target/app/models/schemas/profiles.py::ProfileInResponse]]. The `Profile` type is imported from the domain layer at `app.models.domain.profiles`, meaning `ProfileInResponse` acts as a thin envelope that wraps an existing domain object rather than redeclaring its fields [[target/app/models/schemas/profiles.py]]. This wrapping pattern ensures that the serialised JSON response nests the profile data under a `"profile"` key, a convention common in structured API responses [[target/app/models/schemas/profiles.py::ProfileInResponse]].

## ProfileInResponse

`ProfileInResponse` is a Pydantic model that serves as the response envelope for profile data [[target/app/models/schemas/profiles.py::ProfileInResponse]]. It inherits directly from `BaseModel` and declares a single field, `profile`, typed as `Profile` [[target/app/models/schemas/profiles.py::ProfileInResponse]]. This structure wraps a `Profile` object in a named key, which is a common pattern for shaping JSON API responses [[target/app/models/schemas/profiles.py]].

| Field | Type | Default |
|-------|------|---------|
| `profile` | `Profile` |  |

