# common

[`target/app/models/common.py`](target/app/models/common.py) is a shared utilities module that defines two small Pydantic mixins intended to be composed into domain models elsewhere in the application [[target/app/models/common.py]].

The first mixin, [`DateTimeModelMixin`](target/app/models/common.py::DateTimeModelMixin), extends Pydantic's `BaseModel` and adds automatic timestamp tracking through two fields, `created_at` and `updated_at`, both typed as `datetime.datetime` [[target/app/models/common.py::DateTimeModelMixin]]. Because both fields are declared as non-optional yet default to `None`, each carries a `# type: ignore` comment to suppress the resulting type-checker conflict [[target/app/models/common.py::DateTimeModelMixin]]. A `pre=True` validator named `default_datetime` runs before Pydantic's own coercion on both fields and replaces any falsy incoming value with `datetime.datetime.now()`, ensuring that timestamps are always populated at construction time when no explicit value is supplied [[target/app/models/common.py::DateTimeModelMixin]].

The second mixin, [`IDModelMixin`](target/app/models/common.py::IDModelMixin), also extends `BaseModel` directly and contributes a single integer identity field [[target/app/models/common.py::IDModelMixin]]. The field is named `id_` in Python to avoid shadowing the built-in, but is aliased to `"id"` so that incoming JSON payloads using the conventional key deserialise correctly [[target/app/models/common.py::IDModelMixin]]. It defaults to `0` and is designed to be mixed into any model that needs a shared, aliased numeric identifier [[target/app/models/common.py::IDModelMixin]].

The two mixins are complementary but independent: a domain model can inherit from one, the other, or both, composing timestamps and identity onto whatever Pydantic model needs them [[target/app/models/common.py]].

## DateTimeModelMixin

`DateTimeModelMixin` is a Pydantic model mixin defined in [`target/app/models/common.py`](target/app/models/common.py) that adds automatic timestamp tracking to any model that inherits from it [[target/app/models/common.py::DateTimeModelMixin]]. It extends Pydantic's `BaseModel` directly [[target/app/models/common.py::DateTimeModelMixin]].

The class declares two fields: `created_at` and `updated_at`, both typed as `datetime.datetime` with a default of `None` [[target/app/models/common.py::DateTimeModelMixin]]. Because the declared type is non-optional but the default is `None`, each field carries a `# type: ignore` comment to suppress the type-checker conflict [[target/app/models/common.py::DateTimeModelMixin]].

Both fields are governed by the `default_datetime` validator, which runs before Pydantic's own type coercion and applies to both `created_at` and `updated_at` [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. Whenever either field receives a falsy value — such as `None` or no value at all — the validator substitutes the current date and time via `datetime.datetime.now()`, otherwise it passes the supplied value through unchanged [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. The practical effect is that both timestamps are guaranteed to be populated at the moment of object construction whenever no explicit value is provided [[target/app/models/common.py::DateTimeModelMixin::default_datetime]].

| Field | Type | Default |
|-------|------|---------|
| `created_at` | `datetime.datetime` | `None` |
| `updated_at` | `datetime.datetime` | `None` |

### default_datetime

`default_datetime` is a Pydantic validator method defined on the [`DateTimeModelMixin`](target/app/models/common.py::DateTimeModelMixin) class [[target/app/models/common.py::DateTimeModelMixin]]. It is decorated with `@validator("created_at", "updated_at", pre=True)`, meaning it runs before Pydantic's own type coercion and applies to both the `created_at` and `updated_at` fields [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. The method accepts a single input `value` of type `datetime.datetime` and returns a `datetime.datetime` [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. Its logic is straightforward: if `value` is falsy (i.e. `None` or not provided), it falls back to the current date and time by calling `datetime.datetime.now()`, otherwise it passes `value` through unchanged [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. This ensures that `created_at` and `updated_at` are never left empty, automatically defaulting to the moment of object construction when no explicit timestamp is supplied [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. The `# noqa: N805` comment on `cls` acknowledges the linter warning about using `cls` instead of `self` in a method that is technically a classmethod by Pydantic's validator convention, and `# noqa: WPS110` suppresses a style warning on the parameter name `value` [[target/app/models/common.py::DateTimeModelMixin::default_datetime]].

## IDModelMixin

`IDModelMixin` is a Pydantic model that serves as a reusable mixin for attaching a numeric identifier to other models [[target/app/models/common.py::IDModelMixin]]. It inherits directly from `BaseModel` and is itself a Pydantic model [[target/app/models/common.py::IDModelMixin]]. It declares a single field, `id_`, typed as `int` and defaulting to `0`, which is exposed under the alias `"id"` so that JSON payloads using the conventional `id` key deserialise correctly into the Python-safe attribute name `id_` [[target/app/models/common.py::IDModelMixin]]. Because it is defined as a standalone mixin rather than a full domain model, it is intended to be mixed into other classes that need a shared, aliased integer identity field [[target/app/models/common.py]].

| Field | Type | Default |
|-------|------|---------|
| `id_` | `int` | `Field(0, alias='id')` |

