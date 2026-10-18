# users

This module defines the domain models for application users, providing both a lightweight representation for general use and a richer persistence-ready form [[target/app/models/domain/users.py]].

`User` is the base domain model for an application user, inheriting from `RWModel` to pick up shared Pydantic base configuration [[target/app/models/domain/users.py::User]]. It declares four fields: `username` and `email` are required strings, `bio` is a string that defaults to an empty string, and `image` is an `Optional[str]` defaulting to `None` to represent users who have not set a profile image [[target/app/models/domain/users.py::User]]. All fields are validated at instantiation according to their declared types [[target/app/models/domain/users.py::User]].

`UserInDB` extends `User` with two additional base classes — `IDModelMixin` and `DateTimeModelMixin` — and two fields of its own, making it the model used when a user record must be read from or written to the database [[target/app/models/domain/users.py::UserInDB]]. The `IDModelMixin` contributes an integer `id_` field aliased to `"id"`, and `DateTimeModelMixin` contributes `created_at` and `updated_at` timestamps [[target/app/models/domain/users.py::UserInDB]]. On top of those inherited fields, `UserInDB` adds `salt` and `hashed_password`, both strings defaulting to empty, which hold the credential material that is intentionally absent from the plain `User` model [[target/app/models/domain/users.py::UserInDB]].

Two methods on `UserInDB` encapsulate all password handling. `change_password` generates a fresh salt, stores it on `self.salt`, then hashes the concatenation of that salt and the supplied plaintext password into `self.hashed_password`, mutating the object in place [[target/app/models/domain/users.py::UserInDB]]. `check_password` prepends `self.salt` to the supplied plaintext password before delegating to `security.verify_password` for comparison against `self.hashed_password`, returning a boolean result [[target/app/models/domain/users.py::UserInDB]]. Together these two methods make `UserInDB` the sole site in the codebase where raw passwords are turned into stored credentials and where stored credentials are verified [[target/app/models/domain/users.py::UserInDB]].

## User

`User` is a Pydantic domain model that represents an application user [[target/app/models/domain/users.py::User]]. It inherits from `RWModel` [[target/app/models/domain/rwmodel.py::RWModel]], which provides shared base configuration for domain models [[target/app/models/domain/rwmodel.py::RWModel]].

The class declares four fields [[target/app/models/domain/users.py::User]]. `username` and `email` are required `str` fields with no default value [[target/app/models/domain/users.py::User]]. `bio` is a `str` field that defaults to an empty string, making it optional to supply at construction time [[target/app/models/domain/users.py::User]]. `image` is typed as `Optional[str]` and defaults to `None`, indicating a user may or may not have a profile image [[target/app/models/domain/users.py::User]].

Because `User` is a Pydantic model, all fields are validated at instantiation according to their declared types [[target/app/models/domain/users.py::User]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `email` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |

## UserInDB

`UserInDB` is a Pydantic model that represents a user record as it is stored in the database, extending three base classes — `IDModelMixin`, `DateTimeModelMixin`, and `User` — to assemble the full set of fields needed for persistence and authentication [[target/app/models/domain/users.py::UserInDB]]. It is confirmed to be a Pydantic model [[target/app/models/domain/users.py::UserInDB]].

From `IDModelMixin` it inherits the `id_` field, typed as `int` and aliased to `"id"` with a default of `0` [[target/app/models/common.py::IDModelMixin]]. From `DateTimeModelMixin` it inherits `created_at` and `updated_at`, both typed as `datetime.datetime` and defaulting to `None` [[target/app/models/common.py::DateTimeModelMixin]]. From `User` it inherits `username` and `email` (both `str`), `bio` (`str`, defaulting to `""`), and `image` (`Optional[str]`, defaulting to `None`) [[target/app/models/domain/users.py::UserInDB]]. On top of those inherited fields, `UserInDB` declares two fields of its own: `salt` and `hashed_password`, both typed as `str` and defaulting to an empty string, which together hold the salted credential material that never appears in the plain `User` model [[target/app/models/domain/users.py::UserInDB]].

The class exposes two methods for working with that credential material. `change_password` accepts a plaintext `password: str` and returns `None`; it generates a fresh cryptographic salt, assigns it to `self.salt`, then combines the salt with the password and stores the resulting hash in `self.hashed_password`, so every call produces a freshly salted hash and mutates the object in place without raising any exceptions of its own [[target/app/models/domain/users.py::UserInDB::change_password]]. `check_password` also accepts a plaintext `password: str` and returns a `bool`; it prepends `self.salt` to the supplied password and delegates to `security.verify_password` alongside `self.hashed_password`, making the method itself responsible for assembling the salted input before comparison [[target/app/models/domain/users.py::UserInDB::check_password]]. Together, these two methods mean that `UserInDB` is the sole site where raw passwords are turned into stored credentials and where stored credentials are verified [[target/app/models/domain/users.py::UserInDB::change_password]] [[target/app/models/domain/users.py::UserInDB::check_password]].

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

`change_password` is a method on the [`UserInDB`](target/app/models/domain/users.py::UserInDB) class that updates the stored credentials for a user in place [[target/app/models/domain/users.py::UserInDB::change_password]]. It accepts a single argument, `password: str`, and returns `None` [[target/app/models/domain/users.py::UserInDB::change_password]]. When called, it first generates a new cryptographic salt by invoking `security.generate_salt()` and assigns it to `self.salt`, then immediately combines that salt with the provided plaintext password and passes the concatenated string to `security.get_password_hash()`, storing the result in `self.hashed_password` [[target/app/models/domain/users.py::UserInDB::change_password]]. This design ensures that every password change produces a freshly salted hash, so two users with the same password — or the same user changing to a repeated password — will not produce identical stored values [[target/app/models/domain/users.py::UserInDB::change_password]]. The method mutates the object directly and raises no exceptions of its own [[target/app/models/domain/users.py::UserInDB::change_password]].

### check_password

`check_password` is an instance method on the `UserInDB` class that verifies whether a given plain-text password matches the stored hashed credential [[target/app/models/domain/users.py::UserInDB::check_password]]. It accepts a single parameter, `password` of type `str`, alongside the implicit `self` reference, and returns a `bool` indicating whether the password is valid [[target/app/models/domain/users.py::UserInDB::check_password]]. Internally, it delegates to `security.verify_password`, passing the concatenation of `self.salt` and the supplied `password` as the first argument, and `self.hashed_password` as the second, so the salt is prepended to the raw password before comparison [[target/app/models/domain/users.py::UserInDB::check_password]]. This design means the salt is not stored separately from the verification logic — the method itself is responsible for assembling the salted input before handing it off to the underlying security utility [[target/app/models/domain/users.py::UserInDB]] [[target/app/models/domain/users.py::UserInDB::check_password]]. No exceptions are declared, no decorators are applied, and the method has no other dependencies beyond the `security` module it calls [[target/app/models/domain/users.py::UserInDB::check_password]].

