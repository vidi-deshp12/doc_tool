# profiles

This module defines the `Profile` domain model, which represents the public-facing profile data for a user [[target/app/models/domain/profiles.py]]. It contains a single class that captures the fields needed to describe a user's profile as seen by other users [[target/app/models/domain/profiles.py::Profile]].

The `Profile` class inherits from `RWModel`, which supplies shared Pydantic configuration and automatic camelCase field aliasing used across all domain models in the project [[target/app/models/domain/profiles.py::Profile]]. It declares four fields: `username` is a required string with no default, `bio` is a string that defaults to an empty value, `image` is an optional string defaulting to `None` to represent the absence of a profile picture, and `following` is a boolean defaulting to `False` that indicates whether the currently authenticated user is following this profile [[target/app/models/domain/profiles.py::Profile]]. Because `Profile` is a Pydantic model, all of these fields are validated at construction time and serialized according to the aliasing rules inherited from `RWModel` [[target/app/models/domain/profiles.py::Profile]].

## Profile

`Profile` is a Pydantic domain model that represents a user's public-facing profile [[target/app/models/domain/profiles.py::Profile]]. It inherits from `RWModel`, which provides shared configuration and camelCase aliasing for all domain models in this project [[target/app/models/domain/rwmodel.py::RWModel]].

The class declares four fields [[target/app/models/domain/profiles.py::Profile]]. `username` is a required `str` with no default. `bio` is a `str` that defaults to an empty string `""`. `image` is an `Optional[str]` that defaults to `None`, allowing it to be absent when no profile picture has been set. `following` is a `bool` that defaults to `False`, indicating whether the currently authenticated user follows this profile.

Because it is a Pydantic model, all fields are validated on construction and serialized according to the aliasing rules inherited from `RWModel` [[target/app/models/domain/profiles.py::Profile]] [[target/app/models/domain/rwmodel.py::RWModel]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |
| `following` | `bool` | `False` |

