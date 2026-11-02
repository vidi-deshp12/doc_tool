# production

This module defines the production configuration layer for the application [[target/app/core/settings/production.py]]. It contains a single class, `ProdAppSettings`, which extends `AppSettings` to provide production-specific settings [[target/app/core/settings/production.py::ProdAppSettings]].

`ProdAppSettings` is a Pydantic model that inherits all fields from `AppSettings` without modification, adding only a nested `Config` class that overrides `env_file` to point at `prod.env`, so that environment variables are sourced from that file at runtime [[target/app/core/settings/production.py::ProdAppSettings]]. Through inheritance, it carries FastAPI application metadata such as `title`, `version`, `docs_url`, `openapi_url`, `redoc_url`, and `openapi_prefix` [[target/app/core/settings/production.py::ProdAppSettings]]. Database connectivity is governed by `database_url` (a `PostgresDsn`), `max_connection_count`, and `min_connection_count` [[target/app/core/settings/production.py::ProdAppSettings]]. Security is handled via `secret_key` (a `SecretStr`) and `jwt_token_prefix` [[target/app/core/settings/production.py::ProdAppSettings]]. Routing is controlled by `api_prefix` and `allowed_hosts`, while logging behaviour is set through `logging_level` and `loggers` [[target/app/core/settings/production.py::ProdAppSettings]]. The `app_env` field defaults to `AppEnvTypes.prod`, which identifies this class as the active settings object when the application runs in production [[target/app/core/settings/production.py::ProdAppSettings]].

## ProdAppSettings

`ProdAppSettings` is a Pydantic model that extends `AppSettings`, providing the production-specific configuration layer for the application [[target/app/core/settings/production.py::ProdAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. It is defined in [`target/app/core/settings/production.py`](target/app/core/settings/production.py) and inherits all fields from its parent [[target/app/core/settings/production.py::ProdAppSettings]]. The inner `Config` class extends `AppSettings.Config` and sets `env_file = "prod.env"`, meaning environment variables are loaded from a `prod.env` file at runtime [[target/app/core/settings/production.py::ProdAppSettings]].

Through inheritance, `ProdAppSettings` carries all fields defined on `AppSettings` [[target/app/core/settings/app.py::AppSettings]]. These include FastAPI application metadata fields — `title` (default `'FastAPI example application'`), `version` (default `'0.0.0'`), `docs_url` (default `'/docs'`), `openapi_url` (default `'/openapi.json'`), `redoc_url` (default `'/redoc'`), and `openapi_prefix` (default `''`) — alongside a `debug` flag defaulting to `False` [[target/app/core/settings/production.py::ProdAppSettings]]. Database connectivity is configured via `database_url` (a `PostgresDsn`), `max_connection_count` (default `10`), and `min_connection_count` (default `10`) [[target/app/core/settings/production.py::ProdAppSettings]]. Security settings include `secret_key` (a `SecretStr`) and `jwt_token_prefix` (default `'Token'`) [[target/app/core/settings/production.py::ProdAppSettings]]. Routing is governed by `api_prefix` (default `'/api'`) and `allowed_hosts` (default `['*']`) [[target/app/core/settings/production.py::ProdAppSettings]]. Logging behaviour is controlled by `logging_level` (default `logging.INFO`) and `loggers` (a `Tuple[str, str]` defaulting to `('uvicorn.asgi', 'uvicorn.access')`) [[target/app/core/settings/production.py::ProdAppSettings]]. Finally, the `app_env` field is of type `AppEnvTypes` and defaults to `AppEnvTypes.prod`, marking this settings class as the production environment variant [[target/app/core/settings/production.py::ProdAppSettings]].

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

