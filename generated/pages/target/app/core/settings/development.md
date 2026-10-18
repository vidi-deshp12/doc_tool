# development

This module defines the development-environment configuration for the FastAPI application [[target/app/core/settings/development.py]]. It contains a single class, `DevAppSettings`, which extends `AppSettings` to provide settings tuned for local development [[target/app/core/settings/development.py::DevAppSettings]].

`DevAppSettings` overrides three fields from its parent: `debug` is set to `True`, `logging_level` is set to `logging.DEBUG` for verbose output, and `title` is set to `'Dev FastAPI example application'` to distinguish this environment from others [[target/app/core/settings/development.py::DevAppSettings]]. An inner `Config` class inherits from `AppSettings.Config` and directs the environment file loader to read from `.env` at startup, so local secrets and overrides are picked up automatically [[target/app/core/settings/development.py]].

In addition to those overrides, `DevAppSettings` inherits all fields defined on `AppSettings`, including `docs_url`, `openapi_url`, `redoc_url`, `api_prefix`, `jwt_token_prefix`, `secret_key`, `database_url`, `max_connection_count`, `min_connection_count`, `allowed_hosts`, `loggers`, `version`, `openapi_prefix`, and `app_env` [[target/app/core/settings/development.py::DevAppSettings]].

## DevAppSettings

`DevAppSettings` is a Pydantic model that extends `AppSettings` and provides configuration values tuned for a local development environment [[target/app/core/settings/development.py::DevAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. It sets `debug` to `True` and `logging_level` to `logging.DEBUG`, enabling verbose output during development [[target/app/core/settings/development.py::DevAppSettings]]. The `title` field is overridden to `'Dev FastAPI example application'` to distinguish this environment from others [[target/app/core/settings/development.py::DevAppSettings]]. An inner `Config` class inherits from `AppSettings.Config` and points the environment file loader at `.env`, so local secrets and overrides are read from that file at startup [[target/app/core/settings/development.py]].

Beyond the fields it explicitly overrides, `DevAppSettings` also carries all fields defined on `AppSettings`, including `docs_url` (`'/docs'`), `openapi_prefix` (`''`), `openapi_url` (`'/openapi.json'`), `redoc_url` (`'/redoc'`), `version` (`'0.0.0'`), `database_url` (`PostgresDsn`), `max_connection_count` (`10`), `min_connection_count` (`10`), `secret_key` (`SecretStr`), `api_prefix` (`'/api'`), `jwt_token_prefix` (`'Token'`), `allowed_hosts` (`['*']`), `loggers` (`('uvicorn.asgi', 'uvicorn.access')`), and `app_env` (defaulting to `AppEnvTypes.prod`) [[target/app/core/settings/development.py::DevAppSettings]] [[target/app/core/settings/app.py::AppSettings]].

| Field | Type | Default |
|-------|------|---------|
| `debug` | `bool` | `True` |
| `title` | `str` | `'Dev FastAPI example application'` |
| `logging_level` | `int` | `logging.DEBUG` |
| `docs_url` | `str` | `'/docs'` |
| `openapi_prefix` | `str` | `''` |
| `openapi_url` | `str` | `'/openapi.json'` |
| `redoc_url` | `str` | `'/redoc'` |
| `version` | `str` | `'0.0.0'` |
| `database_url` | `PostgresDsn` |  |
| `max_connection_count` | `int` | `10` |
| `min_connection_count` | `int` | `10` |
| `secret_key` | `SecretStr` |  |
| `api_prefix` | `str` | `'/api'` |
| `jwt_token_prefix` | `str` | `'Token'` |
| `allowed_hosts` | `List[str]` | `['*']` |
| `loggers` | `Tuple[str, str]` | `('uvicorn.asgi', 'uvicorn.access')` |
| `app_env` | `AppEnvTypes` | `AppEnvTypes.prod` |

