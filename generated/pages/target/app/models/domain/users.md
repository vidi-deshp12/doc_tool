# users

This module defines the user domain models for the application, providing both a lightweight representation for in-memory use and a richer record type for database persistence [[target/app/models/domain/users.py]].

`User` is the base domain model, inheriting from `RWModel` and declaring four fields: the required `username` and `email` strings, a `bio` string that defaults to an empty string, and an optional `image` string that defaults to `None` [[target/app/models/domain/users.py::User]]. It captures only the data needed to describe a user at the application layer, without any identity or credential information [[target/app/models/domain/users.py::User]].

`UserInDB` extends `User` by also inheriting from `IDModelMixin` and `DateTimeModelMixin`, adding an integer `id_` field (aliased to `"id"` for serialisation), `created_at` and `updated_at` datetime fields, and two credential fields — `salt` and `hashed_password` — both defaulting to empty strings [[target/app/models/domain/users.py::UserInDB]]. This makes `UserInDB` the complete picture of a stored user row, combining profile data with the identity and timestamp information managed by the mixins [[target/app/models/domain/users.py::UserInDB]].

The two password methods on `UserInDB` work in tandem: `change_password` generates a fresh salt, concatenates it with the supplied plain-text password, hashes the result, and mutates the instance's `salt` and `hashed_password` fields in place [[target/app/models/domain/users.py::UserInDB]]; `check_password` then mirrors that process at verification time by prepending the stored salt to the candidate password before delegating the comparison to `security.verify_password`, ensuring the raw password is never compared directly [[target/app/models/domain/users.py::UserInDB]].

## User

`User` is a Pydantic domain model defined in [`target/app/models/domain/users.py`](target/app/models/domain/users.py) that represents an application user [[target/app/models/domain/users.py::User]]. It inherits from [`RWModel`](target/app/models/domain/rwmodel.py::RWModel), the project's base Pydantic class [[target/app/models/domain/rwmodel.py::RWModel]] [[target/app/models/domain/users.py::User]].

The class declares four fields [[target/app/models/domain/users.py::User]]. `username` and `email` are both required `str` fields with no default value [[target/app/models/domain/users.py::User]]. `bio` is a `str` that defaults to an empty string, allowing it to be omitted when constructing a user [[target/app/models/domain/users.py::User]]. `image` is an `Optional[str]` that defaults to `None`, meaning a user may or may not have a profile image [[target/app/models/domain/users.py::User]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `email` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |

## UserInDB

`UserInDB` is a Pydantic model that represents a user record as it is stored in the database, extending the base `User` type with identity, timestamp, and credential fields [[target/app/models/domain/users.py::UserInDB]]. It inherits from three bases: `IDModelMixin`, `DateTimeModelMixin`, and `User` [[target/app/models/domain/users.py::UserInDB]]. From `IDModelMixin` it gains an `id_` field of type `int`, declared with `Field(0, alias="id")` so that it serialises to and from the key `"id"` [[target/app/models/common.py::IDModelMixin]] [[target/app/models/domain/users.py::UserInDB]]. From `DateTimeModelMixin` it gains `created_at` and `updated_at`, both typed as `datetime.datetime` and defaulting to `None` [[target/app/models/common.py::DateTimeModelMixin]] [[target/app/models/domain/users.py::UserInDB]]. From `User` it inherits `username: str`, `email: str`, `bio: str` (defaulting to `""`), and `image: Optional[str]` (defaulting to `None`) [[target/app/models/domain/users.py::User]] [[target/app/models/domain/users.py::UserInDB]]. On top of those inherited fields, `UserInDB` itself defines two credential fields: `salt: str` (defaulting to `""`) and `hashed_password: str` (defaulting to `""`) [[target/app/models/domain/users.py::UserInDB]].

The class exposes two methods for managing passwords. `change_password` accepts a plain-text `password: str`, generates a fresh cryptographic salt via `security.generate_salt()`, assigns it to `self.salt`, then concatenates that salt with the password and stores the result of `security.get_password_hash()` in `self.hashed_password`, mutating the instance in place and returning `None` [[target/app/models/domain/users.py::UserInDB::change_password]]. `check_password` accepts a candidate `password: str` and returns a `bool` indicating whether it matches the stored credentials; it prepends `self.salt` to the supplied password and delegates the cryptographic comparison to `security.verify_password`, ensuring the password is never compared in its raw form [[target/app/models/domain/users.py::UserInDB::check_password]].

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

`change_password` is an instance method on the [`UserInDB`](target/app/models/domain/users.py::UserInDB) class that updates a user's stored credentials in place [[target/app/models/domain/users.py::UserInDB::change_password]]. It accepts a single parameter, `password: str`, and returns `None` [[target/app/models/domain/users.py::UserInDB::change_password]]. When called, it first generates a fresh cryptographic salt by invoking `security.generate_salt()` and assigns the result to `self.salt`, ensuring that each password change produces a unique salt rather than reusing any prior value [[target/app/models/domain/users.py::UserInDB::change_password]]. It then concatenates that salt with the plain-text password and passes the combined string to `security.get_password_hash()`, storing the resulting hash in `self.hashed_password` [[target/app/models/domain/users.py::UserInDB::change_password]]. No exceptions are declared in the method itself, and no value is returned to the caller; the effect is a direct mutation of the [`UserInDB`](target/app/models/domain/users.py::UserInDB) instance's `salt` and `hashed_password` fields [[target/app/models/domain/users.py::UserInDB::change_password]].

### check_password

The [`check_password()`](target/app/models/domain/users.py:19) method belongs to the [`UserInDB`](target/app/models/domain/users.py::UserInDB) class and verifies whether a given plain-text password matches the stored credentials for that user [[target/app/models/domain/users.py::UserInDB::check_password]]. It accepts a single argument, `password: str`, which is the candidate password to validate [[target/app/models/domain/users.py::UserInDB::check_password]]. The method returns a `bool` indicating whether the password is correct [[target/app/models/domain/users.py::UserInDB::check_password]]. Internally, it prepends the instance's `salt` to the supplied password and passes the combined string along with `self.hashed_password` to `security.verify_password`, delegating the actual cryptographic comparison to that utility [[target/app/models/domain/users.py::UserInDB::check_password]]. This salting step means the password is never compared in its raw form; the salt is incorporated before hashing is verified, which is a standard technique for defending against precomputed hash attacks [[target/app/models/domain/users.py::UserInDB::check_password]].

