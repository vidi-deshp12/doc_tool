# common

[`target/app/models/common.py`](target/app/models/common.py) is a shared module that provides two lightweight Pydantic mixins intended to be composed into domain models throughout the application [[target/app/models/common.py]].

`DateTimeModelMixin` attaches `created_at` and `updated_at` timestamp fields to any model that inherits from it [[target/app/models/common.py::DateTimeModelMixin]]. Both fields are typed as `datetime.datetime` and default to `None` at the class level, with a pre-validation hook supplying a live `datetime.datetime.now()` call whenever a value is not explicitly provided [[target/app/models/common.py::DateTimeModelMixin]]. This means inheriting models receive accurate creation and update timestamps automatically without any extra wiring at the call site [[target/app/models/common.py::DateTimeModelMixin]].

`IDModelMixin` adds a single integer identity field to models that need one [[target/app/models/common.py::IDModelMixin]]. The field is declared as `id_` in Python to avoid shadowing the built-in `id`, but is aliased to `"id"` so that it serialises and deserialises under the conventional key expected by API consumers and database rows [[target/app/models/common.py::IDModelMixin]]. The default value of `0` means the field is always present and safe to read even before a real database-assigned identifier has been attached [[target/app/models/common.py::IDModelMixin]].

The two mixins are independent of each other and can be combined freely; a domain model that needs both a stable identity and automatic timestamps simply inherits from both [[target/app/models/common.py::DateTimeModelMixin]] [[target/app/models/common.py::IDModelMixin]].

## DateTimeModelMixin

`DateTimeModelMixin` is a Pydantic model that serves as a reusable mixin for attaching timestamp fields to other models [[target/app/models/common.py::DateTimeModelMixin]]. It inherits from `BaseModel`, making it a first-class Pydantic model whose fields participate in validation and serialization [[target/app/models/common.py::DateTimeModelMixin]]. The class is defined in [`target/app/models/common.py`](target/app/models/common.py) across lines 6–15 [[target/app/models/common.py::DateTimeModelMixin]].

It declares two fields, `created_at` and `updated_at`, both typed as `datetime.datetime` and both defaulting to `None` at the class level [[target/app/models/common.py::DateTimeModelMixin]]. Because those defaults are `None` rather than real datetimes, the mixin relies on a validator to supply a live timestamp whenever no explicit value is passed in [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. That validator, `default_datetime`, is a class-level method decorated with `@validator("created_at", "updated_at", pre=True)`, so Pydantic invokes it before type coercion for both fields [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. It returns the incoming `value` unchanged when one is provided, or falls back to `datetime.datetime.now()` when `value` is falsy [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. The practical effect is that any model inheriting from `DateTimeModelMixin` will automatically receive a current timestamp for `created_at` and `updated_at` whenever those fields are omitted [[target/app/models/common.py::DateTimeModelMixin]] [[target/app/models/common.py::DateTimeModelMixin::default_datetime]].

| Field | Type | Default |
|-------|------|---------|
| `created_at` | `datetime.datetime` | `None` |
| `updated_at` | `datetime.datetime` | `None` |

### default_datetime

`default_datetime` is a class-level validator method defined on the [`DateTimeModelMixin`](target/app/models/common.py::DateTimeModelMixin) class [[target/app/models/common.py::DateTimeModelMixin]]. It is decorated with `@validator("created_at", "updated_at", pre=True)`, meaning Pydantic invokes it before type coercion for both the `created_at` and `updated_at` fields [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. The method accepts `cls` as its first argument — consistent with a Pydantic class validator — along with `value`, typed as `datetime.datetime`, which holds the incoming field value [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. It returns a `datetime.datetime`: either the supplied `value` if one is provided, or the result of `datetime.datetime.now()` as a fallback when `value` is falsy [[target/app/models/common.py::DateTimeModelMixin::default_datetime]]. In practice this ensures that `created_at` and `updated_at` are never left empty — any model inheriting from [`DateTimeModelMixin`](target/app/models/common.py::DateTimeModelMixin) will automatically receive a current timestamp for either field when no explicit value is given [[target/app/models/common.py::DateTimeModelMixin]].

## IDModelMixin

`IDModelMixin` is a Pydantic model mixin that inherits from `BaseModel` and is designed to be composed into other models that need an integer identity field [[target/app/models/common.py::IDModelMixin]]. It defines a single field, `id_`, typed as `int` and defaulting to `0`, which is exposed under the JSON alias `"id"` [[target/app/models/common.py::IDModelMixin]]. The use of `id_` rather than `id` as the Python attribute name avoids shadowing the built-in, while the alias ensures the field serialises and deserialises correctly under the conventional `"id"` key [[target/app/models/common.py::IDModelMixin]].

| Field | Type | Default |
|-------|------|---------|
| `id_` | `int` | `Field(0, alias='id')` |

