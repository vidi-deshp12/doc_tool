# jwt

This module defines the Pydantic schemas used to represent the structured data carried inside JSON Web Tokens [[target/app/models/schemas/jwt.py]]. It imports `datetime` from the standard library and `BaseModel` from Pydantic, which both schema classes build upon [[target/app/models/schemas/jwt.py]].

`JWTMeta` is a Pydantic model that captures the standard metadata fields of a JWT [[target/app/models/schemas/jwt.py::JWTMeta]]. It declares two required fields: `exp`, typed as `datetime`, which holds the token's expiration time, and `sub`, typed as `str`, which carries the subject of the token — typically a user identifier [[target/app/models/schemas/jwt.py::JWTMeta]]. Because neither field has a default value, both must be supplied whenever an instance is constructed [[target/app/models/schemas/jwt.py::JWTMeta]].

`JWTUser` is a companion Pydantic model that represents the user identity extracted from a JWT [[target/app/models/schemas/jwt.py::JWTUser]]. It holds a single field, `username`, typed as `str`, carrying just enough information to identify the authenticated subject once a token has been decoded [[target/app/models/schemas/jwt.py::JWTUser]].

Together, the two models separate concerns cleanly: `JWTMeta` covers the token-level properties such as expiry and subject, while `JWTUser` carries the application-level identity derived from that token [[target/app/models/schemas/jwt.py::JWTMeta]] [[target/app/models/schemas/jwt.py::JWTUser]].

## JWTMeta

`JWTMeta` is a Pydantic model that serves as a schema for JWT (JSON Web Token) metadata [[target/app/models/schemas/jwt.py::JWTMeta]]. It inherits from `BaseModel`, making it a Pydantic-validated data class [[target/app/models/schemas/jwt.py::JWTMeta]].

The model declares two fields: `exp`, typed as `datetime`, which represents the token's expiration time, and `sub`, typed as `str`, which represents the subject of the token (typically a user identifier) [[target/app/models/schemas/jwt.py::JWTMeta]]. No default values are defined for either field, meaning both are required when constructing an instance of this model [[target/app/models/schemas/jwt.py::JWTMeta]].

| Field | Type | Default |
|-------|------|---------|
| `exp` | `datetime` |  |
| `sub` | `str` |  |

## JWTUser

`JWTUser` is a Pydantic model that extends `BaseModel` [[target/app/models/schemas/jwt.py::JWTUser]]. It is defined in the JWT schemas module and carries a single field, `username`, typed as `str` [[target/app/models/schemas/jwt.py::JWTUser]]. Its purpose is to represent the user identity extracted from a JWT token, holding just enough information — the username — to identify the authenticated subject [[target/app/models/schemas/jwt.py]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |

