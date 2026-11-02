# app

The [`app.py`](target/app/core/settings/app.py) module defines the primary runtime configuration for the application, housing a single class that consolidates every setting the web server, database, authentication, and logging subsystems require [[target/app/core/settings/app.py]].

[`AppSettings`](target/app/core/settings/app.py::AppSettings) is a Pydantic model that extends `BaseAppSettings` to add all of those runtime settings in one place [[target/app/core/settings/app.py::AppSettings]]. Its fields are organised around four concerns. For the FastAPI layer it declares `debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version`, all carrying sensible defaults so the server can start without explicit overrides [[target/app/core/settings/app.py::AppSettings]]. For the database it requires a `database_url` typed as `PostgresDsn` — meaning the application cannot start without it — and accepts `max_connection_count` and `min_connection_count`, both defaulting to `10` [[target/app/core/settings/app.py::AppSettings]]. For authentication it requires a `secret_key` of type `SecretStr` alongside `api_prefix`, `jwt_token_prefix`, and `allowed_hosts` [[target/app/core/settings/app.py::AppSettings]]. For logging it holds `logging_level` and a two-element `loggers` tuple naming the Uvicorn loggers that should be intercepted [[target/app/core/settings/app.py::AppSettings]]. An inner `Config` class enables `validate_assignment`, so Pydantic enforces type constraints on any field that is updated after the object is constructed, not only at initialisation time [[target/app/core/settings/app.py::AppSettings]].

The class exposes two behaviours that the rest of the application consume directly. The `fastapi_kwargs` read-only property packages the seven FastAPI-relevant fields into a plain dictionary that can be unpacked straight into the FastAPI constructor, keeping instantiation boilerplate out of the application factory [[target/app/core/settings/app.py::AppSettings]]. The `configure_logging` method wires the root logger and each logger named in `self.loggers` to Loguru's `InterceptHandler`, then adds a Loguru sink writing to `sys.stderr` at `self.logging_level`, so every intercepted log record is ultimately funnelled through a single handler [[target/app/core/settings/app.py::AppSettings]].

## AppSettings

`AppSettings` is a Pydantic model that serves as the central configuration class for the application, extending `BaseAppSettings` to add all runtime settings needed by the web server, database, authentication, and logging subsystems [[target/app/core/settings/app.py::AppSettings]] [[target/app/core/settings/base.py::BaseAppSettings]].

Its fields cover four broad concerns. For the FastAPI application itself, it declares `debug` (default `False`), `docs_url` (default `"/docs"`), `openapi_prefix` (default `""`), `openapi_url` (default `"/openapi.json"`), `redoc_url` (default `"/redoc"`), `title` (default `"FastAPI example application"`), and `version` (default `"0.0.0"`) [[target/app/core/settings/app.py::AppSettings]]. For the database, it requires a `database_url` of type `PostgresDsn` with no default, and accepts `max_connection_count` and `min_connection_count`, both `int` defaulting to `10` [[target/app/core/settings/app.py::AppSettings]]. For authentication, it requires a `secret_key` of type `SecretStr`, an `api_prefix` defaulting to `"/api"`, a `jwt_token_prefix` defaulting to `"Token"`, and an `allowed_hosts` list defaulting to `["*"]` [[target/app/core/settings/app.py::AppSettings]]. For logging, it holds `logging_level` (default `logging.INFO`) and `loggers`, a two-element `Tuple[str, str]` defaulting to `("uvicorn.asgi", "uvicorn.access")` [[target/app/core/settings/app.py::AppSettings]]. The inner `Config` class enables `validate_assignment`, meaning Pydantic enforces type constraints whenever a field is updated after construction [[target/app/core/settings/app.py::AppSettings]]. It also inherits `app_env` of type `AppEnvTypes` (defaulting to `AppEnvTypes.prod`) from `BaseAppSettings` [[target/app/core/settings/base.py::BaseAppSettings]].

The class exposes two behaviours. The `fastapi_kwargs` read-only property packages the seven FastAPI-relevant fields — `debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version` — into a plain `Dict[str, Any]` that can be unpacked directly into the FastAPI constructor, without calling any external functions or producing side effects [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. The `configure_logging` method wires up the application's logging infrastructure by routing both the root logger and each logger named in `self.loggers` through Loguru's `InterceptHandler`, and then establishes a Loguru sink writing to `sys.stderr` at `self.logging_level`, so that all intercepted records are ultimately handled in one place [[target/app/core/settings/app.py::AppSettings::configure_logging]].

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

The [`configure_logging`](target/app/core/settings/app.py::AppSettings::configure_logging) method belongs to [`AppSettings`](target/app/core/settings/app.py::AppSettings) and returns `None` [[target/app/core/settings/app.py::AppSettings::configure_logging]]. Its purpose is to wire up the application's logging infrastructure by routing standard-library loggers through Loguru's interception mechanism [[target/app/core/settings/app.py::AppSettings::configure_logging]].

It first replaces the root logger's handlers with a bare `InterceptHandler()` instance, ensuring that any log records emitted through the root are captured [[target/app/core/settings/app.py::AppSettings::configure_logging]]. It then iterates over `self.loggers` — a collection of named logger identifiers declared on the parent class — and for each one retrieves the corresponding `logging.Logger` via `logging.getLogger`, replacing its handlers with an `InterceptHandler` constructed at `self.logging_level` [[target/app/core/settings/app.py::AppSettings::configure_logging]]. This allows per-named-logger level control while still funneling records into Loguru [[target/app/core/settings/app.py::AppSettings::configure_logging]].

Finally, the method calls `logger.configure` with a single handler that writes to `sys.stderr` at `self.logging_level`, establishing the Loguru sink that all intercepted records ultimately reach [[target/app/core/settings/app.py::AppSettings::configure_logging]]. The method takes no arguments beyond `self` and produces no return value [[target/app/core/settings/app.py::AppSettings::configure_logging]].

### fastapi_kwargs

`fastapi_kwargs` is a read-only property on the [`AppSettings`](target/app/core/settings/app.py::AppSettings) class, decorated with `@property` [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. It takes no arguments beyond `self` and returns a `Dict[str, Any]` [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. Its sole purpose is to package the relevant configuration fields of the settings object into a plain dictionary that can be passed directly as keyword arguments to the FastAPI application constructor [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. The returned dictionary includes seven entries: `debug`, `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `title`, and `version`, each drawn from the corresponding attribute on the `AppSettings` instance [[target/app/core/settings/app.py::AppSettings::fastapi_kwargs]]. It raises no exceptions, calls no external functions, and has no side effects — it is a pure aggregation of already-held instance state [[target/app/core/settings/app.py::AppSettings]].

