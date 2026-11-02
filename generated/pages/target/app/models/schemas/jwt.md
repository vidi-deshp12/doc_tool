# jwt

This module defines the Pydantic schemas used to represent the structured data carried inside a JSON Web Token [[target/app/models/schemas/jwt.py]]. It contains two models that together cover the two concerns of a JWT payload: token metadata and user identity [[target/app/models/schemas/jwt.py::JWTMeta]] [[target/app/models/schemas/jwt.py::JWTUser]].

`JWTMeta` is a Pydantic `BaseModel` that captures the standard metadata fields of a JWT, namely `exp` (a `datetime` representing the token's expiration time) and `sub` (a `str` representing the token's subject, typically a user identifier) [[target/app/models/schemas/jwt.py::JWTMeta]]. `JWTUser` is a second Pydantic `BaseModel` that holds only a single `username` string, representing the authenticated user's identity as extracted from the token payload [[target/app/models/schemas/jwt.py::JWTUser]]. The two models are complementary: `JWTMeta` carries the validity and ownership claims of the token itself, while `JWTUser` carries just enough information to identify who the token belongs to [[target/app/models/schemas/jwt.py::JWTMeta]] [[target/app/models/schemas/jwt.py::JWTUser]].

## JWTMeta

`JWTMeta` is a Pydantic model that serves as a schema for JWT (JSON Web Token) metadata [[target/app/models/schemas/jwt.py::JWTMeta]]. It inherits from `BaseModel`, making it a Pydantic-validated data class [[target/app/models/schemas/jwt.py::JWTMeta]]. The model declares two fields: `exp`, typed as `datetime`, which represents the token's expiration time, and `sub`, typed as `str`, which represents the token's subject (typically a user identifier) [[target/app/models/schemas/jwt.py::JWTMeta]].

| Field | Type | Default |
|-------|------|---------|
| `exp` | `datetime` |  |
| `sub` | `str` |  |

## JWTUser

`JWTUser` is a Pydantic model that extends `BaseModel` [[target/app/models/schemas/jwt.py::JWTUser]]. It is defined in [`target/app/models/schemas/jwt.py`](target/app/models/schemas/jwt.py) and contains a single field, `username`, typed as `str` [[target/app/models/schemas/jwt.py::JWTUser]]. Its purpose is to represent the user identity payload carried inside a JWT token, holding just enough information — a username string — to identify the authenticated subject [[target/app/models/schemas/jwt.py::JWTUser]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |

