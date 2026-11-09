# users

This module defines the domain-level user models used throughout the application [[target/app/models/domain/users.py]]. It imports shared mixins and the base `RWModel` from sibling packages, as well as the `security` service for password operations [[target/app/models/domain/users.py]].

The central type is `User`, a Pydantic model that represents an application user in memory [[target/app/models/domain/users.py::User]]. It inherits from `RWModel`, which supplies shared configuration such as automatic camelCase aliasing [[target/app/models/domain/users.py::User]]. The class carries four fields: `username` and `email` are required strings, `bio` is an optional string defaulting to an empty string, and `image` is an `Optional[str]` defaulting to `None` [[target/app/models/domain/users.py::User]].

`UserInDB` extends `User` to represent a user record as it exists in the database [[target/app/models/domain/users.py::UserInDB]]. It composes three base classes — `IDModelMixin`, `DateTimeModelMixin`, and `User` — gaining an integer primary-key field `id_` aliased to `"id"`, plus `created_at` and `updated_at` datetime fields, in addition to all four fields inherited from `User` [[target/app/models/domain/users.py::UserInDB]]. On top of those, `UserInDB` adds its own `salt` and `hashed_password` string fields, both defaulting to an empty string, which together store the credential material for the record [[target/app/models/domain/users.py::UserInDB]].

Two methods on `UserInDB` encapsulate all password logic. `change_password` mutates the instance in place by generating a fresh salt via `security.generate_salt`, storing it, then computing the hash of the salt-concatenated plain-text password via `security.get_password_hash` and writing the result into `hashed_password` [[target/app/models/domain/users.py::UserInDB]]. `check_password` verifies a supplied plain-text password by concatenating the stored salt with it and delegating to `security.verify_password` alongside the stored hash, returning `True` on a match and `False` otherwise [[target/app/models/domain/users.py::UserInDB]]. Together these two methods mean that no code outside this model needs to interact directly with the security service for user credential management [[target/app/models/domain/users.py::UserInDB]].

## User

`User` is a Pydantic domain model defined in [`target/app/models/domain/users.py`](target/app/models/domain/users.py) that represents an application user [[target/app/models/domain/users.py::User]]. It inherits from `RWModel` [[target/app/models/domain/rwmodel.py::RWModel]], which provides shared configuration such as camelCase aliasing for all domain models [[target/app/models/domain/rwmodel.py::RWModel]].

The class declares four fields [[target/app/models/domain/users.py::User]]: `username` and `email` are required `str` fields with no default value, while `bio` is an optional `str` that defaults to an empty string, and `image` is typed `Optional[str]` and defaults to `None` [[target/app/models/domain/users.py::User]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `email` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |

## UserInDB

`UserInDB` is a Pydantic model that represents a user record as it is stored in the database [[target/app/models/domain/users.py::UserInDB]]. It inherits from three base classes: `IDModelMixin`, `DateTimeModelMixin`, and `User` [[target/app/models/domain/users.py::UserInDB]]. From `IDModelMixin` it gains an `id_` field of type `int`, declared with `Field(0, alias="id")` so that it maps to the JSON key `"id"` [[target/app/models/common.py::IDModelMixin]]. From `DateTimeModelMixin` it gains `created_at` and `updated_at` fields, both typed as `datetime.datetime` and defaulting to `None` [[target/app/models/common.py::DateTimeModelMixin]]. From `User` it inherits `username` and `email` (both `str`), `bio` (a `str` defaulting to `""`), and `image` (an `Optional[str]` defaulting to `None`) [[target/app/models/domain/users.py::User]]. On top of those inherited fields, `UserInDB` adds two fields of its own: `salt` and `hashed_password`, both typed as `str` and defaulting to `""` [[target/app/models/domain/users.py::UserInDB]].

The class exposes two methods for managing credentials. `change_password` updates the instance in place by generating a fresh salt via `security.generate_salt`, storing it in `self.salt`, then hashing the concatenation of that salt and the supplied plain-text password via `security.get_password_hash` and storing the result in `self.hashed_password`; the method returns nothing [[target/app/models/domain/users.py::UserInDB::change_password]]. `check_password` verifies a supplied plain-text password by concatenating `self.salt` with it and delegating to `security.verify_password` together with `self.hashed_password`, returning `True` on a match and `False` otherwise [[target/app/models/domain/users.py::UserInDB::check_password]].

| Field | Type | Default |
|-------|------|---------|
| `salt` | `str` | `''` |
| `hashed_password` | `str` | `''` |
| `id_` | `int` | `Field(0, alias='id')` |
| `created_at` | `datetime.datetime` | `None` |
| `updated_at` | `datetime.datetime` | `None` |
| `username` | `str` |  |
| `email` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |

### change_password

Updates `self.salt` with a freshly generated salt via `security.generate_salt`, then stores the result of hashing the concatenated salt and new password in `self.hashed_password` via `security.get_password_hash` [[target/app/models/domain/users.py::UserInDB::change_password]]. Both mutations are performed directly on the [`UserInDB`](target/app/models/domain/users.py::UserInDB) instance and the method returns nothing [[target/app/models/domain/users.py::UserInDB::change_password]].

### check_password

Verifies whether a plain-text password matches the stored credentials by concatenating the instance's salt with the provided `password` string and delegating to `security.verify_password` along with `self.hashed_password`, returning `True` if they match and `False` otherwise [[target/app/models/domain/users.py::UserInDB::check_password]].

