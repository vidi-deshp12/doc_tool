# base

This module defines the foundational settings infrastructure for the application, combining an environment enumeration with a base Pydantic configuration class [[target/app/core/settings/base.py]].

`AppEnvTypes` is a plain Python `Enum` subclass that enumerates the three deployment environments the application recognises: `prod`, `dev`, and `test`, each holding a matching string value [[target/app/core/settings/base.py::AppEnvTypes]]. It carries no additional fields or methods beyond these three constants [[target/app/core/settings/base.py::AppEnvTypes]].

`BaseAppSettings` inherits from Pydantic's `BaseSettings` and acts as the root configuration class that environment-specific settings classes are expected to build upon [[target/app/core/settings/base.py::BaseAppSettings]]. It declares a single field, `app_env`, typed as `AppEnvTypes` with a default of `AppEnvTypes.prod`, directly tying the two definitions in this module together [[target/app/core/settings/base.py::BaseAppSettings]]. An inner `Config` class instructs Pydantic to populate field values from a `.env` file, allowing deployment environment to be controlled without changing source code [[target/app/core/settings/base.py]].

## AppEnvTypes

`AppEnvTypes` is a plain Python `Enum` subclass, not a Pydantic model, that enumerates the three deployment environments the application recognises [[target/app/core/settings/base.py::AppEnvTypes]]. It defines three string-typed members: `prod` with value `"prod"`, `dev` with value `"dev"`, and `test` with value `"test"` [[target/app/core/settings/base.py::AppEnvTypes]]. The class carries no additional fields or methods beyond these three enumeration constants [[target/app/core/settings/base.py::AppEnvTypes]].

| Field | Type | Default |
|-------|------|---------|
| `prod` | `str` | `'prod'` |
| `dev` | `str` | `'dev'` |
| `test` | `str` | `'test'` |

## BaseAppSettings

`BaseAppSettings` is a Pydantic model that serves as the base configuration class for the application, inheriting from `BaseSettings` [[target/app/core/settings/base.py::BaseAppSettings]]. It declares a single field, `app_env`, of type `AppEnvTypes`, with a default value of `AppEnvTypes.prod` [[target/app/core/settings/base.py::BaseAppSettings]]. The inner `Config` class instructs Pydantic to load environment variables from a `.env` file [[target/app/core/settings/base.py]].

| Field | Type | Default |
|-------|------|---------|
| `app_env` | `AppEnvTypes` | `AppEnvTypes.prod` |

