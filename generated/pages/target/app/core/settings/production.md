# production

This module defines the production-specific settings class for the application [[target/app/core/settings/production.py]]. It imports `AppSettings` from the core settings package and exposes a single class, `ProdAppSettings`, which specialises that base class for the production environment [[target/app/core/settings/production.py::ProdAppSettings]].

`ProdAppSettings` is a Pydantic model that extends `AppSettings` and overrides the inner `Config` class to load environment variables from a `prod.env` file, making it the authoritative source of configuration when the application runs in production [[target/app/core/settings/production.py::ProdAppSettings]]. All of its fields are inherited directly from `AppSettings` rather than redefined here [[target/app/core/settings/production.py::ProdAppSettings]]. General application metadata is covered by `title`, `version`, `debug`, `docs_url`, `openapi_url`, `redoc_url`, and `openapi_prefix` [[target/app/core/settings/production.py::ProdAppSettings]]. Database connectivity is configured through `database_url` (a `PostgresDsn` with no default, meaning it must be supplied by the environment), together with `max_connection_count` and `min_connection_count` [[target/app/core/settings/production.py::ProdAppSettings]]. Security is handled by `secret_key` (a `SecretStr` that likewise carries no default) and `jwt_token_prefix` [[target/app/core/settings/production.py::ProdAppSettings]]. Routing and host allowances are controlled by `api_prefix` and `allowed_hosts` [[target/app/core/settings/production.py::ProdAppSettings]]. Logging behaviour is governed by `logging_level` and the `loggers` tuple [[target/app/core/settings/production.py::ProdAppSettings]]. Finally, `app_env` is set to `AppEnvTypes.prod`, explicitly marking this class as targeting the production environment and distinguishing it from any development or test counterparts [[target/app/core/settings/production.py::ProdAppSettings]].

## ProdAppSettings

`ProdAppSettings` is a Pydantic model that extends `AppSettings` to provide the production environment configuration for the application [[target/app/core/settings/production.py::ProdAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. It inherits all fields from `AppSettings` and overrides the inner `Config` class to load environment variables from a `prod.env` file [[target/app/core/settings/production.py::ProdAppSettings]].

The full set of fields available on this class — all inherited from `AppSettings` — covers general application metadata: `title` (`str`, default `'FastAPI example application'`), `version` (`str`, default `'0.0.0'`), `debug` (`bool`, default `False`), `docs_url` (`str`, default `'/docs'`), `openapi_url` (`str`, default `'/openapi.json'`), `redoc_url` (`str`, default `'/redoc'`), and `openapi_prefix` (`str`, default `''`) [[target/app/core/settings/production.py::ProdAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. Database connectivity is configured through `database_url` (a `PostgresDsn` with no default), `max_connection_count` (`int`, default `10`), and `min_connection_count` (`int`, default `10`) [[target/app/core/settings/production.py::ProdAppSettings]]. Security settings are provided by `secret_key` (a `SecretStr` with no default) and `jwt_token_prefix` (`str`, default `'Token'`) [[target/app/core/settings/production.py::ProdAppSettings]]. Routing and host configuration is handled by `api_prefix` (`str`, default `'/api'`) and `allowed_hosts` (`List[str]`, default `['*']`) [[target/app/core/settings/production.py::ProdAppSettings]]. Logging behaviour is controlled by `logging_level` (`int`, default `logging.INFO`) and `loggers` (`Tuple[str, str]`, default `('uvicorn.asgi', 'uvicorn.access')`) [[target/app/core/settings/production.py::ProdAppSettings]]. Finally, `app_env` (`AppEnvTypes`, default `AppEnvTypes.prod`) identifies that this settings class targets the production environment [[target/app/core/settings/production.py::ProdAppSettings]].

| Field | Type | Default |
|-------|------|---------|
| `debug` | `bool` | `False` |
| `docs_url` | `str` | `'/docs'` |
| `openapi_prefix` | `str` | `''` |
| `openapi_url` | `str` | `'/openapi.json'` |
| `redoc_url` | `str` | `'/redoc'` |
| `title` | `str` | `'FastAPI example application'` |
| `version` | `str` | `'0.0.0'` |
| `database_url` | `PostgresDsn` |  |
| `max_connection_count` | `int` | `10` |
| `min_connection_count` | `int` | `10` |
| `secret_key` | `SecretStr` |  |
| `api_prefix` | `str` | `'/api'` |
| `jwt_token_prefix` | `str` | `'Token'` |
| `allowed_hosts` | `List[str]` | `['*']` |
| `logging_level` | `int` | `logging.INFO` |
| `loggers` | `Tuple[str, str]` | `('uvicorn.asgi', 'uvicorn.access')` |
| `app_env` | `AppEnvTypes` | `AppEnvTypes.prod` |

