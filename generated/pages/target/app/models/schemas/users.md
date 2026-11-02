# users

This module defines the Pydantic schemas used to validate and shape user-related request and response data throughout the application [[target/app/models/schemas/users.py]]. It imports from both the domain layer and a shared base schema, then builds a small hierarchy of models that cover the four main user operations: login, registration, update, and response [[target/app/models/schemas/users.py]].

The hierarchy starts with `UserInLogin`, which inherits from `RWSchema` and declares the two fields a user must supply to authenticate: a validated `email` and a plain-string `password` [[target/app/models/schemas/users.py::UserInLogin]]. `UserInCreate` extends `UserInLogin` directly, inheriting those two credential fields and adding a required `username` field, making it the complete schema for new account registration [[target/app/models/schemas/users.py::UserInCreate]].

For profile edits, `UserInUpdate` stands apart from that inheritance chain; it inherits from `BaseModel` directly and makes all five of its fields — `username`, `email`, `password`, `bio`, and `image` — optional and defaulting to `None`, so a caller can supply any subset when patching a user record [[target/app/models/schemas/users.py::UserInUpdate]]. The `email` field uses `EmailStr` for format validation and `image` uses `HttpUrl` to enforce a valid URL whenever a value is provided [[target/app/models/schemas/users.py::UserInUpdate]].

On the response side, `UserWithToken` extends the domain `User` class, inheriting its `username`, `email`, `bio`, and `image` fields and adding a single required `token: str` field, making it suitable for any response that must carry an authentication token alongside profile data [[target/app/models/schemas/users.py::UserWithToken]]. `UserInResponse` then wraps `UserWithToken` in a single `user` field and inherits from `RWSchema`, ensuring the outgoing payload conforms to the aliasing and serialisation conventions shared across all response schemas in the application [[target/app/models/schemas/users.py::UserInResponse]].

## UserInCreate

`UserInCreate` is a Pydantic model defined in the user schemas module [[target/app/models/schemas/users.py::UserInCreate]]. It extends `UserInLogin` [[target/app/models/schemas/users.py::UserInLogin]], inheriting that base class's `email: EmailStr` and `password: str` fields [[target/app/models/schemas/users.py::UserInCreate]]. On top of those inherited fields, `UserInCreate` adds a single field of its own: `username: str`, making it the schema used when creating a new user account where all three pieces of information — username, email, and password — are required [[target/app/models/schemas/users.py::UserInCreate]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `email` | `EmailStr` |  |
| `password` | `str` |  |

## UserInLogin

`UserInLogin` is a Pydantic model defined in the users schema module [[target/app/models/schemas/users.py]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared configuration and aliasing behaviour common to all request/response schemas in this application. The class carries two fields: `email`, typed as `EmailStr` for automatic email validation, and `password`, typed as a plain `str` [[target/app/models/schemas/users.py::UserInLogin]]. Together these two fields represent the credentials a user submits when logging in [[target/app/models/schemas/users.py::UserInLogin]].

| Field | Type | Default |
|-------|------|---------|
| `email` | `EmailStr` |  |
| `password` | `str` |  |

## UserInResponse

`UserInResponse` is a Pydantic model defined in the users schema module [[target/app/models/schemas/users.py]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the base configuration shared across response schemas. The class declares a single field, `user`, typed as `UserWithToken`, which holds the user data along with an authentication token [[target/app/models/schemas/users.py::UserInResponse]]. As a direct subclass of `RWSchema`, it participates in the same aliasing and serialization conventions established by that base class [[target/app/models/schemas/rwschema.py::RWSchema]] [[target/app/models/schemas/users.py::UserInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `user` | `UserWithToken` |  |

## UserInUpdate

`UserInUpdate` is a Pydantic model used to represent a partial update payload for a user [[target/app/models/schemas/users.py::UserInUpdate]]. It inherits directly from `BaseModel` [[target/app/models/schemas/users.py::UserInUpdate]]. All five of its fields — `username`, `email`, `password`, `bio`, and `image` — are optional and default to `None`, meaning a caller may supply any subset of them when updating a user record [[target/app/models/schemas/users.py::UserInUpdate]]. The `email` field is typed as `Optional[EmailStr]`, which delegates e-mail format validation to Pydantic, while `image` is typed as `Optional[HttpUrl]`, enforcing a valid URL when a value is provided [[target/app/models/schemas/users.py::UserInUpdate]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `Optional[str]` | `None` |
| `email` | `Optional[EmailStr]` | `None` |
| `password` | `Optional[str]` | `None` |
| `bio` | `Optional[str]` | `None` |
| `image` | `Optional[HttpUrl]` | `None` |

## UserWithToken

`UserWithToken` is a Pydantic model defined in the users schema module that extends the domain `User` class [[target/app/models/schemas/users.py::UserWithToken]]. It inherits from `User` [[target/app/models/domain/users.py::User]], bringing in the `username` (str), `email` (str), `bio` (str, defaulting to `''`), and `image` (Optional[str], defaulting to `None`) fields [[target/app/models/schemas/users.py::UserWithToken]]. On top of those inherited fields it adds a single required `token` field of type `str` [[target/app/models/schemas/users.py::UserWithToken]], making it suitable for responses that need to carry an authentication token alongside the user's profile data [[target/app/models/schemas/users.py]].

| Field | Type | Default |
|-------|------|---------|
| `token` | `str` |  |
| `username` | `str` |  |
| `email` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |

