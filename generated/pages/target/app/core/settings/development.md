# development

The [`development.py`](target/app/core/settings/development.py) module defines the development-environment configuration for the FastAPI application by providing a single class, `DevAppSettings` [[target/app/core/settings/development.py]].

[`DevAppSettings`](target/app/core/settings/development.py::DevAppSettings) is a Pydantic model that extends `AppSettings` to supply development-specific overrides [[target/app/core/settings/development.py::DevAppSettings]]. It sets `debug` to `True`, gives the application the title `"Dev FastAPI example application"`, and raises `logging_level` to `logging.DEBUG` so that verbose log output is emitted during local development [[target/app/core/settings/development.py::DevAppSettings]]. Its inner `Config` class subclasses `AppSettings.Config` and points `env_file` to `".env"`, which causes Pydantic to load environment variables from that file when the application runs in development mode [[target/app/core/settings/development.py::DevAppSettings]].

Beyond those overrides, `DevAppSettings` inherits the complete set of fields from `AppSettings` [[target/app/core/settings/development.py::DevAppSettings]]. Those inherited fields cover database connectivity (`database_url`, `max_connection_count`, `min_connection_count`), security (`secret_key`, `jwt_token_prefix`), API routing (`api_prefix`, `openapi_prefix`, `openapi_url`, `docs_url`, `redoc_url`), network access (`allowed_hosts`), logging targets (`loggers`), versioning (`version`), and the active environment indicator `app_env` [[target/app/core/settings/development.py::DevAppSettings]].

## DevAppSettings

`DevAppSettings` is a Pydantic model that extends `AppSettings` to provide development-specific configuration for the FastAPI application [[target/app/core/settings/development.py::DevAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. It overrides `debug` to `True` and sets `title` to `"Dev FastAPI example application"`, and raises `logging_level` to `logging.DEBUG` for verbose output [[target/app/core/settings/development.py::DevAppSettings]]. Its inner `Config` class subclasses `AppSettings.Config` and points `env_file` to `".env"`, meaning environment variables are loaded from that file in development [[target/app/core/settings/development.py::DevAppSettings]].

Beyond what it overrides, `DevAppSettings` inherits the full set of fields defined on `AppSettings` [[target/app/core/settings/app.py::AppSettings]]: `docs_url` (`"/docs"`), `openapi_prefix` (`""`), `openapi_url` (`"/openapi.json"`), `redoc_url` (`"/redoc"`), `version` (`"0.0.0"`), `database_url` (`PostgresDsn`), `max_connection_count` (`10`), `min_connection_count` (`10`), `secret_key` (`SecretStr`), `api_prefix` (`"/api"`), `jwt_token_prefix` (`"Token"`), `allowed_hosts` (`["*"]`), `loggers` (`("uvicorn.asgi", "uvicorn.access")`), and `app_env` (defaulting to `AppEnvTypes.prod`) [[target/app/core/settings/development.py::DevAppSettings]].

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

