# users

[`target/app/models/schemas/users.py`](target/app/models/schemas/users.py) is the schema module responsible for defining the Pydantic models that govern user-related data flowing into and out of the API [[target/app/models/schemas/users.py]]. It imports from both the domain layer and a shared base schema, then assembles five models that cover every user-facing operation: login, registration, partial update, token-bearing representation, and API response wrapping [[target/app/models/schemas/users.py]].

The foundation for incoming credential payloads is [`UserInLogin`](target/app/models/schemas/users.py::UserInLogin), which inherits from `RWSchema` and declares exactly two fields — `email: EmailStr` and `password: str` — representing the data a user submits to authenticate [[target/app/models/schemas/users.py::UserInLogin]]. Registration builds directly on top of this: [`UserInCreate`](target/app/models/schemas/users.py::UserInCreate) extends `UserInLogin`, inheriting both credential fields and adding `username: str`, making it the superset schema required when opening a new account [[target/app/models/schemas/users.py::UserInCreate]].

For profile edits, [`UserInUpdate`](target/app/models/schemas/users.py::UserInUpdate) takes a different approach — it inherits from `BaseModel` directly rather than from `RWSchema`, and declares all five of its fields (`username`, `email`, `password`, `bio`, and `image`) as `Optional` with `None` defaults, supporting partial-update semantics where only the fields a caller supplies carry meaningful values [[target/app/models/schemas/users.py::UserInUpdate]].

On the response side, [`UserWithToken`](target/app/models/schemas/users.py::UserWithToken) extends the domain `User` class, inheriting its `username`, `email`, `bio`, and `image` fields and adding a single required `token: str` field, so that an authenticated user's data and their session token travel together as one object [[target/app/models/schemas/users.py::UserWithToken]]. That object is then wrapped by [`UserInResponse`](target/app/models/schemas/users.py::UserInResponse), which inherits from `RWSchema` and exposes a single field `user: UserWithToken`, forming the outermost envelope the API returns to callers after a successful login or registration [[target/app/models/schemas/users.py::UserInResponse]].

## UserInCreate

`UserInCreate` is a Pydantic model defined in the users schema module that represents the data required to register a new user [[target/app/models/schemas/users.py::UserInCreate]]. It extends `UserInLogin`, inheriting that base class's `email: EmailStr` and `password: str` fields [[target/app/models/schemas/users.py::UserInLogin]]. On top of those inherited fields, `UserInCreate` adds a single field of its own, `username: str`, making it the superset schema used during account creation [[target/app/models/schemas/users.py::UserInCreate]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `email` | `EmailStr` |  |
| `password` | `str` |  |

## UserInLogin

`UserInLogin` is a Pydantic model defined in the users schema module [[target/app/models/schemas/users.py]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which serves as its base class. The class carries two fields: `email`, typed as `EmailStr` for validated email input, and `password`, typed as a plain `str` [[target/app/models/schemas/users.py::UserInLogin]]. Together these fields represent the credentials a user submits when logging in [[target/app/models/schemas/users.py::UserInLogin]].

| Field | Type | Default |
|-------|------|---------|
| `email` | `EmailStr` |  |
| `password` | `str` |  |

## UserInResponse

`UserInResponse` is a Pydantic model [[target/app/models/schemas/users.py::UserInResponse]] that inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], placing it within the schema layer responsible for structuring API responses [[target/app/models/schemas/users.py]]. It declares a single field, `user`, typed as `UserWithToken`, which carries the authenticated user's data together with their token [[target/app/models/schemas/users.py::UserInResponse]]. Because it extends `RWSchema`, it inherits that base's camelCase auto-aliasing behaviour for all fields [[target/app/models/schemas/rwschema.py::RWSchema]]. The class body is intentionally minimal — its entire contract is expressed through that one field declaration [[target/app/models/schemas/users.py::UserInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `user` | `UserWithToken` |  |

## UserInUpdate

`UserInUpdate` is a Pydantic model used to represent an optional, partial update to a user record [[target/app/models/schemas/users.py::UserInUpdate]]. It inherits directly from `BaseModel` [[target/app/models/schemas/users.py::UserInUpdate]]. All five of its fields — `username` (`Optional[str]`), `email` (`Optional[EmailStr]`), `password` (`Optional[str]`), `bio` (`Optional[str]`), and `image` (`Optional[HttpUrl]`) — default to `None`, meaning a caller may supply any subset of fields and omit the rest [[target/app/models/schemas/users.py::UserInUpdate]]. Because every field is optional, the model naturally supports partial-update semantics where only the provided fields need to carry meaningful values [[target/app/models/schemas/users.py::UserInUpdate]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `Optional[str]` | `None` |
| `email` | `Optional[EmailStr]` | `None` |
| `password` | `Optional[str]` | `None` |
| `bio` | `Optional[str]` | `None` |
| `image` | `Optional[HttpUrl]` | `None` |

## UserWithToken

`UserWithToken` is a Pydantic model defined in [`target/app/models/schemas/users.py`](target/app/models/schemas/users.py) that extends the domain [`User`](target/app/models/domain/users.py) class to carry an authentication token alongside the standard user fields [[target/app/models/schemas/users.py::UserWithToken]]. It inherits the `username`, `email`, `bio`, and `image` fields from its base class [[target/app/models/domain/users.py::User]] [[target/app/models/schemas/users.py::UserWithToken]]. The only field it adds directly is `token`, typed as a plain `str` with no default, making it required at construction time [[target/app/models/schemas/users.py::UserWithToken]]. Because `is_pydantic_model` is `true`, Pydantic validates all fields — both inherited and newly declared — when an instance is created [[target/app/models/schemas/users.py::UserWithToken]].

| Field | Type | Default |
|-------|------|---------|
| `token` | `str` |  |
| `username` | `str` |  |
| `email` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |

