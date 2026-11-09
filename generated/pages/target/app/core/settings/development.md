# development

This module defines the development environment configuration for the FastAPI application [[target/app/core/settings/development.py]]. It imports Python's `logging` module and `AppSettings` from the application's core settings, then provides a single class that tailors those base settings for local development use [[target/app/core/settings/development.py]].

The sole component defined here is `DevAppSettings`, a Pydantic model that extends `AppSettings` and supplies development-specific defaults [[target/app/core/settings/development.py::DevAppSettings]]. It overrides three fields from the base class: `debug` is set to `True`, `title` is set to `"Dev FastAPI example application"`, and `logging_level` is set to `logging.DEBUG` so that verbose output is produced during development [[target/app/core/settings/development.py::DevAppSettings]]. An inner `Config` class inherits from `AppSettings.Config` and points to a `.env` file, allowing environment variables to be loaded from disk when running in development mode [[target/app/core/settings/development.py]].

All remaining configuration fields — including database connection parameters, API routing prefixes, JWT settings, allowed hosts, and logger names — are inherited unchanged from `AppSettings` and remain fully available on `DevAppSettings` [[target/app/core/settings/development.py::DevAppSettings]].

## DevAppSettings

`DevAppSettings` is a Pydantic model that extends `AppSettings` and provides development-specific configuration defaults for the FastAPI application [[target/app/core/settings/development.py::DevAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. It overrides `debug` to `True` and sets `title` to `"Dev FastAPI example application"`, and sets `logging_level` to `logging.DEBUG` for verbose output during development [[target/app/core/settings/development.py::DevAppSettings]]. It defines an inner `Config` class that inherits from `AppSettings.Config` and points to a `.env` file for environment variable loading [[target/app/core/settings/development.py]].

Beyond its own three overrides, `DevAppSettings` inherits the full set of fields from `AppSettings` [[target/app/core/settings/app.py::AppSettings]], including `docs_url` (`"/docs"`), `openapi_prefix` (`""`), `openapi_url` (`"/openapi.json"`), `redoc_url` (`"/redoc"`), `version` (`"0.0.0"`), `database_url` (a `PostgresDsn`), `max_connection_count` (`10`), `min_connection_count` (`10`), `secret_key` (a `SecretStr`), `api_prefix` (`"/api"`), `jwt_token_prefix` (`"Token"`), `allowed_hosts` (`["*"]`), `loggers` (a `Tuple[str, str]` of `"uvicorn.asgi"` and `"uvicorn.access"`), and `app_env` (defaulting to `AppEnvTypes.prod`) [[target/app/core/settings/development.py::DevAppSettings]].

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

