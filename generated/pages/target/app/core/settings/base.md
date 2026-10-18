# base

This module defines the foundational building blocks for application configuration, combining a plain enumeration of environment names with a Pydantic-based settings class [[target/app/core/settings/base.py]].

`AppEnvTypes` is a Python `Enum` subclass that enumerates the three valid deployment environments: `prod`, `dev`, and `test`, each carrying a matching string value [[target/app/core/settings/base.py::AppEnvTypes]]. It is not a Pydantic model, serving purely as a controlled vocabulary for environment names [[target/app/core/settings/base.py::AppEnvTypes]].

`BaseAppSettings` extends Pydantic's `BaseSettings` to act as the root configuration class for the application [[target/app/core/settings/base.py::BaseAppSettings]]. It declares a single field, `app_env`, typed as `AppEnvTypes` and defaulting to `AppEnvTypes.prod`, so the application assumes a production environment unless explicitly told otherwise [[target/app/core/settings/base.py::BaseAppSettings]]. The two classes are directly coupled: `AppEnvTypes` is the declared type of `BaseAppSettings.app_env`, meaning every settings instance is constrained to one of the three named environments [[target/app/core/settings/base.py::AppEnvTypes]] [[target/app/core/settings/base.py::BaseAppSettings]]. Because `BaseAppSettings` inherits from `BaseSettings`, its field values can be populated from environment variables or from the `.env` file specified in its inner `Config` class [[target/app/core/settings/base.py::BaseAppSettings]] [[target/app/core/settings/base.py]].

## AppEnvTypes

`AppEnvTypes` is a plain Python `Enum` subclass defined in the application's base settings module, used to represent the set of valid deployment environment names [[target/app/core/settings/base.py::AppEnvTypes]]. It is not a Pydantic model [[target/app/core/settings/base.py::AppEnvTypes]]. The class declares three string-valued members: `prod` with value `"prod"`, `dev` with value `"dev"`, and `test` with value `"test"` [[target/app/core/settings/base.py::AppEnvTypes]].

| Field | Type | Default |
|-------|------|---------|
| `prod` | `str` | `'prod'` |
| `dev` | `str` | `'dev'` |
| `test` | `str` | `'test'` |

## BaseAppSettings

`BaseAppSettings` is a Pydantic settings model that extends `BaseSettings`, making it the root configuration class for the application [[target/app/core/settings/base.py::BaseAppSettings]]. It declares a single field, `app_env`, typed as `AppEnvTypes` with a default value of `AppEnvTypes.prod`, meaning the application environment defaults to production unless overridden [[target/app/core/settings/base.py::BaseAppSettings]]. Because it is a Pydantic model built on `BaseSettings`, its field values can be populated from environment variables or from the `.env` file declared in its inner `Config` class [[target/app/core/settings/base.py::BaseAppSettings]] [[target/app/core/settings/base.py]].

| Field | Type | Default |
|-------|------|---------|
| `app_env` | `AppEnvTypes` | `AppEnvTypes.prod` |

