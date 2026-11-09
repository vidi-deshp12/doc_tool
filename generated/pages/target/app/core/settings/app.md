# app

[`target/app/core/settings/app.py`](target/app/core/settings/app.py) is the runtime configuration module for the application, importing logging utilities, Pydantic types, and the `InterceptHandler` from the project's logging support before defining the single class that governs all live settings [[target/app/core/settings/app.py]].

The central definition is `AppSettings`, a Pydantic model that inherits from `BaseAppSettings` and holds every configurable value the application needs at runtime [[target/app/core/settings/app.py::AppSettings]]. Because `validate_assignment` is enabled, Pydantic re-validates any field value whenever it is reassigned after the object is first constructed [[target/app/core/settings/app.py::AppSettings]]. The fields are organised around four concerns: FastAPI application metadata (`debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version`), database connectivity (`database_url` as a required `PostgresDsn`, `max_connection_count`, and `min_connection_count`), security (`secret_key` as a required `SecretStr`, `api_prefix`, `jwt_token_prefix`, and `allowed_hosts`), and logging (`logging_level` and the `loggers` tuple naming the two Uvicorn loggers) [[target/app/core/settings/app.py::AppSettings]]. The `app_env` field, typed as `AppEnvTypes` with a production default, is inherited from `BaseAppSettings` rather than declared directly in this class [[target/app/core/settings/app.py::AppSettings]].

`AppSettings` also exposes two methods that act on those fields. The `configure_logging` method wires the application's logging pipeline by replacing the root logger's handlers with a single `InterceptHandler`, attaching per-name `InterceptHandler` instances at `self.logging_level` to each logger listed in `self.loggers`, and registering a single `sys.stderr` sink through `logger.configure` [[target/app/core/settings/app.py::AppSettings]]. The `fastapi_kwargs` method assembles the FastAPI metadata fields into a plain dictionary so that it can be unpacked directly as keyword arguments when the FastAPI application instance is constructed [[target/app/core/settings/app.py::AppSettings]]. Together, the two methods mean that `AppSettings` is not merely a passive data container: it actively initialises both the logging subsystem and the web framework from the same source of truth [[target/app/core/settings/app.py::AppSettings]].

## AppSettings

`AppSettings` is a Pydantic model that holds the full runtime configuration for the application, inheriting from `BaseAppSettings` [[target/app/core/settings/app.py::AppSettings]] [[target/app/core/settings/base.py::BaseAppSettings]]. It enables `validate_assignment`, meaning Pydantic re-validates field values whenever they are reassigned after construction [[target/app/core/settings/app.py::AppSettings]].

The class carries fields covering four broad concerns [[target/app/core/settings/app.py::AppSettings]]. For FastAPI application metadata it defines `debug` (default `False`), `docs_url` (default `"/docs"`), `openapi_prefix` (default `""`), `openapi_url` (default `"/openapi.json"`), `redoc_url` (default `"/redoc"`), `title` (default `"FastAPI example application"`), and `version` (default `"0.0.0"`) [[target/app/core/settings/app.py::AppSettings]]. For the database it defines `database_url` as a `PostgresDsn` (required, no default), `max_connection_count` (default `10`), and `min_connection_count` (default `10`) [[target/app/core/settings/app.py::AppSettings]]. For security it holds `secret_key` as a `SecretStr` (required, no default), `api_prefix` (default `"/api"`), `jwt_token_prefix` (default `"Token"`), and `allowed_hosts` as a `List[str]` (default `["*"]`) [[target/app/core/settings/app.py::AppSettings]]. For logging it stores `logging_level` (default `logging.INFO`) and `loggers` as a `Tuple[str, str]` naming the two Uvicorn loggers (default `("uvicorn.asgi", "uvicorn.access")`) [[target/app/core/settings/app.py::AppSettings]]. Additionally, `app_env` typed as `AppEnvTypes` with a default of `AppEnvTypes.prod` is inherited from `BaseAppSettings` [[target/app/core/settings/app.py::AppSettings]] [[target/app/core/settings/base.py::BaseAppSettings]].

The `configure_logging` method replaces the root logger's handlers with a single `InterceptHandler` instance, attaches per-name `InterceptHandler` instances at `self.logging_level` to each logger named in `self.loggers`, and finally calls `logger.configure` to register a single sink pointing to `sys.stderr` at `self.logging_level` [[target/app/core/settings/app.py::AppSettings::configure_logging]]. The `fastapi_kwargs` method assembles and returns a dictionary mapping `debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version` to their current field values, intended to be unpacked directly as keyword arguments when the FastAPI application is constructed [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]] [[target/app/core/settings/app.py::AppSettings]].

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

### configure_logging

Replaces the root logger's handlers with a single `InterceptHandler` instance, then iterates over every logger name in `self.loggers` and attaches a per-name `InterceptHandler` configured with `self.logging_level` [[target/app/core/settings/app.py::AppSettings::configure_logging]]. Finally, it calls `logger.configure` to register a single sink pointing to `sys.stderr` at `self.logging_level` [[target/app/core/settings/app.py::AppSettings::configure_logging]].

### fastapi_kwargs

Assembles and returns a dictionary of FastAPI application configuration values drawn from the `AppSettings` instance, mapping keys such as `debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version` to their corresponding settings fields [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. The returned dict is intended to be unpacked directly as keyword arguments when constructing the FastAPI application [[target/app/core/settings/app.py::AppSettings]].

