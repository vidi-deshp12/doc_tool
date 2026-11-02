# profiles

This module defines the domain model for user profiles in the application [[target/app/models/domain/profiles.py]]. It contains a single class, `Profile`, which is a Pydantic model that inherits from `RWModel` to gain shared base validation and serialisation behaviour used across the domain layer [[target/app/models/domain/profiles.py::Profile]].

`Profile` declares four fields that together describe a user's public profile: `username` is a required `str` with no default, `bio` is a `str` that defaults to an empty string, `image` is an `Optional[str]` that defaults to `None`, and `following` is a `bool` that defaults to `False` [[target/app/models/domain/profiles.py::Profile]].

## Profile

`Profile` is a Pydantic domain model that represents a user profile in the application [[target/app/models/domain/profiles.py::Profile]]. It inherits from `RWModel`, which provides shared base configuration for read/write models across the domain layer [[target/app/models/domain/rwmodel.py::RWModel]].

The class declares four fields: `username` is a required `str` with no default, `bio` is a `str` that defaults to an empty string, `image` is an `Optional[str]` that defaults to `None`, and `following` is a `bool` that defaults to `False` [[target/app/models/domain/profiles.py::Profile]]. Because it extends `RWModel`, it is a Pydantic model and inherits any base validation and serialisation behaviour that `RWModel` provides [[target/app/models/domain/rwmodel.py::RWModel]] [[target/app/models/domain/profiles.py::Profile]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |
| `following` | `bool` | `False` |

