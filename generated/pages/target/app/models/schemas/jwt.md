# jwt

This module defines the Pydantic schema classes used to represent the structured payload of a JWT token [[target/app/models/schemas/jwt.py]]. It imports `datetime` from the standard library and `BaseModel` from Pydantic, which both defined classes inherit from [[target/app/models/schemas/jwt.py]].

`JWTMeta` captures the standard claims portion of a token, carrying two required fields: `exp`, typed as `datetime`, which records when the token expires, and `sub`, typed as `str`, which identifies the token's subject [[target/app/models/schemas/jwt.py::JWTMeta]]. Because neither field has a default value, both must be supplied when constructing an instance [[target/app/models/schemas/jwt.py::JWTMeta]].

`JWTUser` represents the identity payload embedded in the token, holding a single required `username` field typed as `str` [[target/app/models/schemas/jwt.py::JWTUser]]. Together, the two classes separate the generic token metadata (`JWTMeta`) from the application-specific user identity (`JWTUser`), giving each concern its own validated structure [[target/app/models/schemas/jwt.py::JWTMeta]] [[target/app/models/schemas/jwt.py::JWTUser]].

## JWTMeta

`JWTMeta` is a Pydantic model class defined in the JWT schemas module [[target/app/models/schemas/jwt.py::JWTMeta]]. It inherits directly from `BaseModel`, making it a Pydantic-validated data structure [[target/app/models/schemas/jwt.py::JWTMeta]]. The class carries two fields: `exp`, typed as `datetime`, which represents the token expiry, and `sub`, typed as `str`, which represents the subject of the token [[target/app/models/schemas/jwt.py::JWTMeta]]. No default values are defined for either field, so both are required when constructing an instance [[target/app/models/schemas/jwt.py::JWTMeta]].

| Field | Type | Default |
|-------|------|---------|
| `exp` | `datetime` |  |
| `sub` | `str` |  |

## JWTUser

`JWTUser` is a Pydantic model class defined in the JWT schemas module [[target/app/models/schemas/jwt.py::JWTUser]]. It inherits from `BaseModel`, making it a Pydantic-validated data structure [[target/app/models/schemas/jwt.py::JWTUser]]. The class declares a single field, `username`, typed as `str`, with no default value [[target/app/models/schemas/jwt.py::JWTUser]]. Its purpose is to represent the identity payload carried inside a JWT token, holding just enough information to identify the authenticated user [[target/app/models/schemas/jwt.py]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |

