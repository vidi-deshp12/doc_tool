# users

This module defines the complete set of request and response schemas for user-related API operations, building on Pydantic for validation and the project's shared `RWSchema` base class [[target/app/models/schemas/users.py]].

The login flow begins with `UserInLogin`, which captures the two credentials a user submits at sign-in: a validated `email` field typed as `EmailStr` and a plain `password` string, both inherited by schemas further up the hierarchy [[target/app/models/schemas/users.py::UserInLogin]]. Registration extends that foundation through `UserInCreate`, which inherits `email` and `password` from `UserInLogin` and adds the required `username` field, making it the complete three-field schema needed to create a new account [[target/app/models/schemas/users.py::UserInCreate]].

On the response side, `UserWithToken` extends the domain `User` class, inheriting its `username`, `email`, `bio`, and `image` fields and adding a single required `token` string so that authenticated responses can carry both profile data and the session token in one object [[target/app/models/schemas/users.py::UserWithToken]]. That combined representation is then wrapped by `UserInResponse`, whose sole field is a `user` typed as `UserWithToken`; this outer envelope is what the API actually returns to callers after a successful login or registration [[target/app/models/schemas/users.py::UserInResponse]].

Account updates are handled separately by `UserInUpdate`, which inherits directly from `BaseModel` rather than `RWSchema` and declares all five editable fields — `username`, `email`, `password`, `bio`, and `image` — as optional with `None` defaults [[target/app/models/schemas/users.py::UserInUpdate]]. Because every field is optional, a caller may send any subset of changes, and an empty payload remains valid while only explicitly supplied fields carry update intent [[target/app/models/schemas/users.py::UserInUpdate]].

## UserInCreate

`UserInCreate` is a Pydantic model defined in the users schema module [[target/app/models/schemas/users.py::UserInCreate]]. It extends `UserInLogin` [[target/app/models/schemas/users.py::UserInLogin]], inheriting the `email` (`EmailStr`) and `password` (`str`) fields from that base class [[target/app/models/schemas/users.py::UserInCreate]]. It adds one field of its own, `username` (`str`), making it the schema used when registering a new user with all three credentials present [[target/app/models/schemas/users.py::UserInCreate]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `email` | `EmailStr` |  |
| `password` | `str` |  |

## UserInLogin

`UserInLogin` is a Pydantic model that represents the data a user submits when logging in [[target/app/models/schemas/users.py::UserInLogin]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides shared serialisation behaviour for all schema classes in the project. The model declares two fields: `email`, typed as `EmailStr` for validated email input, and `password`, typed as a plain `str` [[target/app/models/schemas/users.py::UserInLogin]].

| Field | Type | Default |
|-------|------|---------|
| `email` | `EmailStr` |  |
| `password` | `str` |  |

## UserInResponse

`UserInResponse` is a Pydantic model [[target/app/models/schemas/users.py::UserInResponse]] that inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], the project's base schema class. Its sole field is `user`, typed as `UserWithToken`, which wraps the authenticated user data along with their token for inclusion in API responses [[target/app/models/schemas/users.py::UserInResponse]]. As a subclass of `RWSchema`, it inherits any aliasing or serialisation behaviour that base class provides [[target/app/models/schemas/rwschema.py::RWSchema]] [[target/app/models/schemas/users.py]].

| Field | Type | Default |
|-------|------|---------|
| `user` | `UserWithToken` |  |

## UserInUpdate

`UserInUpdate` is a Pydantic model that represents a partial update payload for a user account [[target/app/models/schemas/users.py::UserInUpdate]]. It inherits directly from `BaseModel` and all five of its fields are optional, meaning a caller may supply any combination of them without providing the rest [[target/app/models/schemas/users.py::UserInUpdate]]. The fields are `username` (`Optional[str]`, defaulting to `None`), `email` (`Optional[EmailStr]`, defaulting to `None`), `password` (`Optional[str]`, defaulting to `None`), `bio` (`Optional[str]`, defaulting to `None`), and `image` (`Optional[HttpUrl]`, defaulting to `None`) [[target/app/models/schemas/users.py::UserInUpdate]]. Because every field defaults to `None`, an empty payload is valid and only the fields explicitly provided in a request carry meaningful update intent [[target/app/models/schemas/users.py::UserInUpdate]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `Optional[str]` | `None` |
| `email` | `Optional[EmailStr]` | `None` |
| `password` | `Optional[str]` | `None` |
| `bio` | `Optional[str]` | `None` |
| `image` | `Optional[HttpUrl]` | `None` |

## UserWithToken

`UserWithToken` is a Pydantic model defined in the users schema module that extends the domain `User` class [[target/app/models/schemas/users.py::UserWithToken]]. It inherits from `User` [[target/app/models/domain/users.py::User]], gaining the fields `username` (str), `email` (str), `bio` (str, defaulting to an empty string), and `image` (Optional[str], defaulting to None) [[target/app/models/schemas/users.py::UserWithToken]]. On top of those inherited fields, it adds a single required field `token` of type `str`, making it suitable for responses that need to carry an authentication token alongside the user's profile data [[target/app/models/schemas/users.py::UserWithToken]].

| Field | Type | Default |
|-------|------|---------|
| `token` | `str` |  |
| `username` | `str` |  |
| `email` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |

