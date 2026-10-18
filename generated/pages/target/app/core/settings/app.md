# app

This module defines the primary runtime configuration layer for the FastAPI application, housing a single class that centralises every setting the server needs to start and operate [[target/app/core/settings/app.py]].

`AppSettings` is a Pydantic model that extends `BaseAppSettings` with all the fields required to run the FastAPI server, connect to a PostgreSQL database, and control logging [[target/app/core/settings/app.py::AppSettings]]. Its inner `Config` class sets `validate_assignment = True`, so Pydantic re-validates any field value that is reassigned after the object is constructed, preventing silent misconfiguration at runtime [[target/app/core/settings/app.py::AppSettings]].

The class groups its fields by concern. Seven fields describe the FastAPI application itself: `title`, `version`, `debug`, `docs_url`, `openapi_url`, `redoc_url`, and `openapi_prefix`, each carrying a sensible default such as `"FastAPI example application"` for the title and `"0.0.0"` for the version [[target/app/core/settings/app.py::AppSettings]]. Database connectivity is handled by `database_url` (a `PostgresDsn` that carries no default and must therefore be supplied from the environment), alongside `max_connection_count` and `min_connection_count`, both defaulting to `10` [[target/app/core/settings/app.py::AppSettings]]. Security is covered by `secret_key` (a `SecretStr` with no default), `api_prefix` (defaulting to `"/api"`), `jwt_token_prefix` (defaulting to `"Token"`), and `allowed_hosts` (a `List[str]` that defaults to `["*"]`) [[target/app/core/settings/app.py::AppSettings]]. Logging behaviour is governed by `logging_level` (defaulting to `logging.INFO`) and `loggers`, a two-element tuple that names the `"uvicorn.asgi"` and `"uvicorn.access"` loggers by default [[target/app/core/settings/app.py::AppSettings]].

Two members build on those fields. The `fastapi_kwargs` property assembles the seven FastAPI metadata fields into a `Dict[str, Any]` in precisely the keyword-argument form expected by the FastAPI constructor, with no side effects, making it the single authoritative source for wiring settings into the application instance [[target/app/core/settings/app.py::AppSettings]]. The `configure_logging` method sets up the full logging pipeline: it replaces the root logger's handlers with an `InterceptHandler` that forwards standard-library log records into Loguru, attaches a per-level `InterceptHandler` to each logger named in `self.loggers`, and then calls `logger.configure` to register `sys.stderr` as the sole Loguru sink at the configured level [[target/app/core/settings/app.py::AppSettings]]. Together, `fastapi_kwargs` and `configure_logging` mean that `AppSettings` is not merely a passive data container — it actively participates in bootstrapping both the web server and the logging infrastructure [[target/app/core/settings/app.py::AppSettings]].

## AppSettings

`AppSettings` is a Pydantic model that holds the complete runtime configuration for the application, extending `BaseAppSettings` with all the settings needed to run the FastAPI server, connect to the database, and control logging [[target/app/core/settings/app.py::AppSettings]] [[target/app/core/settings/base.py::BaseAppSettings]]. It is defined in [`target/app/core/settings/app.py`](target/app/core/settings/app.py) across lines 12–57 and its `Config` inner class sets `validate_assignment = True`, meaning Pydantic re-validates field values whenever they are reassigned after construction [[target/app/core/settings/app.py::AppSettings]].

The class inherits from `BaseAppSettings` and adds seventeen fields of its own [[target/app/core/settings/app.py::AppSettings]] [[target/app/core/settings/base.py::BaseAppSettings]]. The FastAPI application metadata fields are `title` (default `"FastAPI example application"`), `version` (default `"0.0.0"`), `debug` (default `False`), `docs_url` (default `"/docs"`), `openapi_url` (default `"/openapi.json"`), `redoc_url` (default `"/redoc"`), and `openapi_prefix` (default `""`) [[target/app/core/settings/app.py::AppSettings]]. Database connectivity is configured through `database_url` (a `PostgresDsn` with no default, so it must be supplied from the environment), `max_connection_count` (default `10`), and `min_connection_count` (default `10`) [[target/app/core/settings/app.py::AppSettings]]. Security-related fields are `secret_key` (a `SecretStr` with no default), `api_prefix` (default `"/api"`), `jwt_token_prefix` (default `"Token"`), and `allowed_hosts` (a `List[str]` defaulting to `["*"]`) [[target/app/core/settings/app.py::AppSettings]]. Logging is governed by `logging_level` (default `logging.INFO`) and `loggers`, a `Tuple[str, str]` whose default value names the `"uvicorn.asgi"` and `"uvicorn.access"` loggers [[target/app/core/settings/app.py::AppSettings]]. The field `app_env` is also present, typed as `AppEnvTypes` with a default of `AppEnvTypes.prod` [[target/app/core/settings/app.py::AppSettings]].

The class exposes two members beyond its fields. The `fastapi_kwargs` property assembles a `Dict[str, Any]` from the seven FastAPI metadata fields — `debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version` — in the exact keyword-argument form expected by the FastAPI constructor, with no side effects [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. The `configure_logging` method sets up the application's logging pipeline by replacing the root logger's handlers with an `InterceptHandler` that forwards standard-library log records to Loguru, then attaches a per-level `InterceptHandler` to each logger named in `self.loggers`, and finally calls `logger.configure` to register `sys.stderr` as the sole Loguru sink at `self.logging_level` [[target/app/core/settings/app.py::AppSettings::configure_logging]].

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

`configure_logging` is an instance method on `AppSettings` that sets up the application's logging pipeline by routing all log output through Loguru [[target/app/core/settings/app.py::AppSettings::configure_logging]]. It takes no arguments beyond `self` and returns `None` [[target/app/core/settings/app.py::AppSettings::configure_logging]].

The method begins by replacing the root logger's handlers with a single `InterceptHandler` instance, which intercepts standard-library log records and forwards them to Loguru [[target/app/core/settings/app.py::AppSettings::configure_logging]]. It then iterates over `self.loggers` — a collection of named loggers defined on the `AppSettings` class — and attaches a fresh `InterceptHandler` configured with `self.logging_level` to each one [[target/app/core/settings/app.py::AppSettings]] [[target/app/core/settings/app.py::AppSettings::configure_logging]]. Finally, it calls `logger.configure` to register a single Loguru sink pointing at `sys.stderr`, also gated by `self.logging_level`, which makes `sys.stderr` the authoritative output destination for all forwarded records [[target/app/core/settings/app.py::AppSettings::configure_logging]].

The method raises no exceptions of its own and carries no decorators [[target/app/core/settings/app.py::AppSettings::configure_logging]]. Its three notable dependencies are `InterceptHandler`, `logging.getLogger` from the standard library, and Loguru's `logger.configure` [[target/app/core/settings/app.py::AppSettings::configure_logging]].

### fastapi_kwargs

`fastapi_kwargs` is a read-only property on the `AppSettings` class that assembles and returns a `Dict[str, Any]` containing the core configuration values needed to initialise a FastAPI application [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. It takes no arguments beyond `self` and collects seven fields from the enclosing settings object: `debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version` [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. Because it is decorated with `@property`, callers access it as an attribute rather than a method call, and it always returns a freshly constructed dictionary reflecting the current state of the `AppSettings` instance [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. It raises no exceptions, calls no external functions, and has no side effects — its sole responsibility is to package the relevant `AppSettings` fields into the keyword-argument form expected by the FastAPI constructor [[target/app/core/settings/app.py::AppSettings]] [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]].

