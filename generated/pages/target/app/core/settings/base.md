# base

This module establishes the foundational configuration layer for the application by defining two classes that work together [[target/app/core/settings/base.py]]. `AppEnvTypes` is a standard Python `Enum` that enumerates the three deployment environments the application recognises — `prod`, `dev`, and `test` — each carrying a matching string value [[target/app/core/settings/base.py::AppEnvTypes]]. `BaseAppSettings` is a Pydantic `BaseSettings` subclass that acts as the root configuration class from which environment-specific settings classes are intended to inherit [[target/app/core/settings/base.py::BaseAppSettings]]. Because it extends `BaseSettings`, it can automatically populate field values from environment variables or a `.env` file, as declared in its inner `Config` class [[target/app/core/settings/base.py::BaseAppSettings]]. The two classes are directly coupled: `BaseAppSettings` declares a single field, `app_env`, typed as `AppEnvTypes` with a default of `AppEnvTypes.prod`, meaning the application assumes a production context unless the environment explicitly overrides it [[target/app/core/settings/base.py::BaseAppSettings]] [[target/app/core/settings/base.py::AppEnvTypes]].

## AppEnvTypes

`AppEnvTypes` is a plain Python `Enum` subclass (not a Pydantic model) that enumerates the three deployment environments the application recognises [[target/app/core/settings/base.py::AppEnvTypes]]. It declares three `str`-typed members: `prod` with value `"prod"`, `dev` with value `"dev"`, and `test` with value `"test"` [[target/app/core/settings/base.py::AppEnvTypes]]. It carries no additional fields beyond those three members, and it inherits no extra behaviour beyond what the standard library `Enum` provides [[target/app/core/settings/base.py::AppEnvTypes]].

| Field | Type | Default |
|-------|------|---------|
| `prod` | `str` | `'prod'` |
| `dev` | `str` | `'dev'` |
| `test` | `str` | `'test'` |

## BaseAppSettings

`BaseAppSettings` is a Pydantic model that serves as the base configuration class for the application, inheriting from `BaseSettings` [[target/app/core/settings/base.py::BaseAppSettings]]. Because it extends `BaseSettings`, it can automatically read field values from environment variables and a `.env` file, which is configured via the inner `Config` class with `env_file = ".env"` [[target/app/core/settings/base.py::BaseAppSettings]]. It declares a single field, `app_env`, typed as `AppEnvTypes` with a default value of `AppEnvTypes.prod`, making production the assumed environment unless overridden [[target/app/core/settings/base.py::BaseAppSettings]].

| Field | Type | Default |
|-------|------|---------|
| `app_env` | `AppEnvTypes` | `AppEnvTypes.prod` |

