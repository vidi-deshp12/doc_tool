# common

[`target/app/models/common.py`](target/app/models/common.py) is a shared Pydantic utilities module that provides two reusable mixin classes for domain models throughout the application [[target/app/models/common.py]]. It imports `datetime`, `pydantic.BaseModel`, `pydantic.Field`, and `pydantic.validator` to support the behaviour defined in those mixins [[target/app/models/common.py]].

`IDModelMixin` is a Pydantic `BaseModel` subclass whose sole responsibility is to supply a standard integer identity field to any model that inherits from it [[target/app/models/common.py::IDModelMixin]]. It declares a single field `id_` typed as `int` with a default of `0` and an alias of `"id"`, so that an external source such as a database row or JSON payload can supply the conventional `"id"` key while the Python attribute remains `id_` to avoid shadowing the built-in `id` function [[target/app/models/common.py::IDModelMixin]].

`DateTimeModelMixin` is a second Pydantic `BaseModel` subclass that mixes timestamp-tracking behaviour into other models [[target/app/models/common.py::DateTimeModelMixin]]. It declares two `datetime.datetime` fields, `created_at` and `updated_at`, both defaulting to `None` [[target/app/models/common.py::DateTimeModelMixin]]. A `pre` validator named `default_datetime` is attached to both fields and ensures they are always populated with a meaningful value: it returns the supplied value unchanged when it is truthy, and falls back to `datetime.datetime.now()` when the value is absent or falsy, so timestamps are set automatically at instantiation even if the caller omits them [[target/app/models/common.py::DateTimeModelMixin::default_datetime]].

The two mixins are designed to be combined with one another and with application-specific models through multiple inheritance, giving any downstream model a consistent identity field and automatic timestamp population without repeating that logic in each model [[target/app/models/common.py::IDModelMixin]] [[target/app/models/common.py::DateTimeModelMixin]].

## DateTimeModelMixin

`DateTimeModelMixin` is a Pydantic model that mixes timestamp-tracking behaviour into other models [[target/app/models/common.py::DateTimeModelMixin]]. It inherits from `BaseModel` [[target/app/models/common.py::DateTimeModelMixin]] and declares two fields: `created_at` and `updated_at`, both typed as `datetime.datetime` and defaulting to `None` [[target/app/models/common.py::DateTimeModelMixin]]. A `pre` validator named `default_datetime` is attached to both fields; it returns the supplied value unchanged when it is truthy, and falls back to the current datetime via `datetime.datetime.now()` when the value is absent or falsy [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. This ensures that both timestamps are always populated with a meaningful value at the time of model instantiation even if the caller omits them [[target/app/models/common.py::DateTimeModelMixin::default_datetime]].

| Field | Type | Default |
|-------|------|---------|
| `created_at` | `datetime.datetime` | `None` |
| `updated_at` | `datetime.datetime` | `None` |

### default_datetime

A Pydantic `pre` validator applied to the `created_at` and `updated_at` fields of [`DateTimeModelMixin`](target/app/models/common.py::DateTimeModelMixin), it returns the provided value unchanged if truthy, or falls back to the current datetime via `datetime.datetime.now()` if the value is absent or falsy [[target/app/models/common.py::DateTimeModelMixin::default_datetime]].

## IDModelMixin

`IDModelMixin` is a Pydantic model mixin that extends Pydantic's `BaseModel` [[target/app/models/common.py::IDModelMixin]]. Its sole responsibility is to provide a reusable integer identity field to any model that inherits from it [[target/app/models/common.py::IDModelMixin]].

It declares one field, `id_`, typed as `int` with a default value of `0` and an alias of `"id"` [[target/app/models/common.py::IDModelMixin]]. The alias means that when data is parsed from an external source (such as a database row or JSON payload), the key `"id"` maps onto the Python attribute `id_` [[target/app/models/common.py::IDModelMixin]]. The underscore suffix on `id_` avoids shadowing Python's built-in `id` function while still accepting the conventional `"id"` key from outside [[target/app/models/common.py::IDModelMixin]].

| Field | Type | Default |
|-------|------|---------|
| `id_` | `int` | `Field(0, alias='id')` |

