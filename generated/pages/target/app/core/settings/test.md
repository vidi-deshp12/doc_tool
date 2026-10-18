# test

This module defines the test-environment configuration for the FastAPI application by providing a single class, `TestAppSettings`, which inherits from `AppSettings` [[target/app/core/settings/test.py::TestAppSettings]]. Its sole purpose is to replace production defaults with safe, deterministic values that are appropriate for running tests [[target/app/core/settings/test.py]].

`TestAppSettings` is a Pydantic model that overrides a targeted subset of the fields defined by its parent class [[target/app/core/settings/test.py::TestAppSettings]]. Debug mode is enabled via `debug: bool = True` and `logging_level` is fixed to `logging.DEBUG`, ensuring that test runs produce verbose output [[target/app/core/settings/test.py::TestAppSettings]]. The application title is set to the static string `"Test FastAPI example application"` and `secret_key` is hardcoded as `SecretStr("test_secret")`, removing any dependency on real or environment-supplied secrets [[target/app/core/settings/test.py::TestAppSettings]]. Both connection-pool bounds, `max_connection_count` and `min_connection_count`, are fixed at `5`, while `database_url` is declared as a bare `PostgresDsn` field with no default, so it must be provided explicitly at instantiation time [[target/app/core/settings/test.py::TestAppSettings]]. All remaining fields — including `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `version`, `api_prefix`, `jwt_token_prefix`, `allowed_hosts`, `loggers`, and `app_env` — are inherited from `AppSettings` without modification [[target/app/core/settings/test.py::TestAppSettings]].

## TestAppSettings

`TestAppSettings` is a Pydantic model that provides test-specific configuration for the FastAPI application by inheriting from `AppSettings` [[target/app/core/settings/test.py::TestAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. It overrides several base-class fields to supply safe, predictable defaults suited for a test environment rather than production [[target/app/core/settings/test.py::TestAppSettings]].

The class sets `debug` to `True` and `logging_level` to `logging.DEBUG`, ensuring verbose output during test runs [[target/app/core/settings/test.py::TestAppSettings]]. The application title is fixed to `"Test FastAPI example application"` and `secret_key` is set to the static value `SecretStr("test_secret")`, avoiding any dependency on real secrets [[target/app/core/settings/test.py::TestAppSettings]]. Both `max_connection_count` and `min_connection_count` are set to `5`, and `database_url` is declared as a `PostgresDsn` field with no default, meaning it must be supplied at instantiation time [[target/app/core/settings/test.py::TestAppSettings]].

The remaining fields — `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `version`, `api_prefix`, `jwt_token_prefix`, `allowed_hosts`, `loggers`, and `app_env` — are inherited from `AppSettings` without override [[target/app/core/settings/test.py::TestAppSettings]] [[target/app/core/settings/app.py::AppSettings]].

| Field | Type | Default |
|-------|------|---------|
| `debug` | `bool` | `True` |
| `title` | `str` | `'Test FastAPI example application'` |
| `secret_key` | `SecretStr` | `SecretStr('test_secret')` |
| `database_url` | `PostgresDsn` |  |
| `max_connection_count` | `int` | `5` |
| `min_connection_count` | `int` | `5` |
| `logging_level` | `int` | `logging.DEBUG` |
| `docs_url` | `str` | `'/docs'` |
| `openapi_prefix` | `str` | `''` |
| `openapi_url` | `str` | `'/openapi.json'` |
| `redoc_url` | `str` | `'/redoc'` |
| `version` | `str` | `'0.0.0'` |
| `api_prefix` | `str` | `'/api'` |
| `jwt_token_prefix` | `str` | `'Token'` |
| `allowed_hosts` | `List[str]` | `['*']` |
| `loggers` | `Tuple[str, str]` | `('uvicorn.asgi', 'uvicorn.access')` |
| `app_env` | `AppEnvTypes` | `AppEnvTypes.prod` |

