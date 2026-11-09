# profiles

The module [`target/app/models/domain/profiles.py`](target/app/models/domain/profiles.py) defines the domain-layer representation of a user profile [[target/app/models/domain/profiles.py]]. It imports `Optional` from the standard library and `RWModel` from the project's shared domain model base, which together support the single class it exposes [[target/app/models/domain/profiles.py]].

That class, `Profile`, is a Pydantic model that captures the information associated with a user profile [[target/app/models/domain/profiles.py::Profile]]. It inherits from `RWModel`, picking up the shared serialisation behaviour that base class provides to all domain models [[target/app/models/domain/profiles.py::Profile]]. The class declares four fields: `username`, a required `str` that uniquely identifies the profile; `bio`, a `str` that defaults to an empty string; `image`, an `Optional[str]` that defaults to `None` to allow a profile to exist without a photo; and `following`, a `bool` that defaults to `False` to indicate whether the currently authenticated user follows this profile [[target/app/models/domain/profiles.py::Profile]].

## Profile

`Profile` is a Pydantic model that represents a user profile in the domain layer [[target/app/models/domain/profiles.py::Profile]]. It inherits from `RWModel` [[target/app/models/domain/rwmodel.py::RWModel]], which provides shared serialisation behaviour for domain models [[target/app/models/domain/rwmodel.py::RWModel]].

The class declares four fields [[target/app/models/domain/profiles.py::Profile]]. `username` is a required `str` with no default [[target/app/models/domain/profiles.py::Profile]]. `bio` is a `str` that defaults to an empty string [[target/app/models/domain/profiles.py::Profile]]. `image` is an `Optional[str]` that defaults to `None`, allowing the profile to exist without a photo [[target/app/models/domain/profiles.py::Profile]]. `following` is a `bool` that defaults to `False`, indicating whether the current user follows this profile [[target/app/models/domain/profiles.py::Profile]].

| Field | Type | Default |
|-------|------|---------|
| `username` | `str` |  |
| `bio` | `str` | `''` |
| `image` | `Optional[str]` | `None` |
| `following` | `bool` | `False` |

