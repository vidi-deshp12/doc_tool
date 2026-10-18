# production

This module defines the production configuration layer for the application [[target/app/core/settings/production.py]]. It contains a single class, `ProdAppSettings`, which extends `AppSettings` to provide production-specific settings [[target/app/core/settings/production.py::ProdAppSettings]].

`ProdAppSettings` inherits all configuration fields from `AppSettings` and overrides only the inner `Config` class, redirecting the environment file loader to read from `prod.env` instead of any development default [[target/app/core/settings/production.py::ProdAppSettings]]. Because all fields come from the parent, the class itself adds no new fields — its sole contribution is that file-path binding [[target/app/core/settings/production.py]].

The inherited fields cover every concern the application needs at runtime. Application behaviour is controlled by `debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version` [[target/app/core/settings/production.py::ProdAppSettings]]. Database connectivity is governed by `database_url`, `max_connection_count`, and `min_connection_count` [[target/app/core/settings/production.py::ProdAppSettings]]. Security and routing are handled through `secret_key`, `api_prefix`, `jwt_token_prefix`, and `allowed_hosts` [[target/app/core/settings/production.py::ProdAppSettings]]. Logging behaviour is shaped by `logging_level` and `loggers` [[target/app/core/settings/production.py::ProdAppSettings]]. Finally, `app_env` is fixed to `AppEnvTypes.prod`, so any code that branches on environment type will recognise this settings object as belonging unambiguously to production [[target/app/core/settings/production.py::ProdAppSettings]].

## ProdAppSettings

`ProdAppSettings` is a Pydantic model that extends `AppSettings` to provide production-specific configuration [[target/app/core/settings/production.py::ProdAppSettings]]. It inherits directly from `AppSettings` and overrides the inner `Config` class to point the environment file loader at `prod.env` [[target/app/core/settings/production.py]].

All fields are inherited from `AppSettings` [[target/app/core/settings/app.py::AppSettings]]. On the application side these include `debug` (`bool`, default `False`), `docs_url` (`str`, default `'/docs'`), `openapi_prefix` (`str`, default `''`), `openapi_url` (`str`, default `'/openapi.json'`), `redoc_url` (`str`, default `'/redoc'`), `title` (`str`, default `'FastAPI example application'`), and `version` (`str`, default `'0.0.0'`) [[target/app/core/settings/production.py::ProdAppSettings]]. Database connectivity is governed by `database_url` (`PostgresDsn`), `max_connection_count` (`int`, default `10`), and `min_connection_count` (`int`, default `10`) [[target/app/core/settings/production.py::ProdAppSettings]]. Security fields include `secret_key` (`SecretStr`), `api_prefix` (`str`, default `'/api'`), `jwt_token_prefix` (`str`, default `'Token'`), and `allowed_hosts` (`List[str]`, default `['*']`) [[target/app/core/settings/production.py::ProdAppSettings]]. Logging is configured through `logging_level` (`int`, default `logging.INFO`) and `loggers` (`Tuple[str, str]`, default `('uvicorn.asgi', 'uvicorn.access')`) [[target/app/core/settings/production.py::ProdAppSettings]]. Finally, `app_env` (`AppEnvTypes`) is fixed to `AppEnvTypes.prod`, marking this settings object as belonging to the production environment [[target/app/core/settings/production.py::ProdAppSettings]].

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

