# test

This module defines the test-environment configuration for the application, importing the necessary types and the base settings class to support a single override model [[target/app/core/settings/test.py]].

`TestAppSettings` is a Pydantic model that extends `AppSettings` and provides a fixed, test-oriented configuration for the application [[target/app/core/settings/test.py::TestAppSettings]]. It overrides several fields with safe, predictable defaults suitable for a test environment, ensuring that tests run against a known, controlled baseline rather than production values [[target/app/core/settings/test.py::TestAppSettings]]. Specifically, `debug` defaults to `True` and `title` is set to `"Test FastAPI example application"`, while `secret_key` is hardcoded as a `SecretStr` holding `"test_secret"` [[target/app/core/settings/test.py::TestAppSettings]]. The `database_url` field is typed as `PostgresDsn` but carries no default, meaning it must be supplied by the test environment at runtime [[target/app/core/settings/test.py::TestAppSettings]]. Both `max_connection_count` and `min_connection_count` are fixed at `5`, and `logging_level` defaults to `logging.DEBUG` so that all log output is visible during test runs [[target/app/core/settings/test.py::TestAppSettings]]. All remaining fields — including `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `version`, `api_prefix`, `jwt_token_prefix`, `allowed_hosts`, `loggers`, and `app_env` — are inherited directly from `AppSettings` and retain their own defaults [[target/app/core/settings/test.py::TestAppSettings]].

## TestAppSettings

`TestAppSettings` is a Pydantic model that extends `AppSettings` and provides a fixed, test-oriented configuration for the application [[target/app/core/settings/test.py::TestAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. It overrides several fields with safe, predictable defaults suitable for a test environment [[target/app/core/settings/test.py::TestAppSettings]].

The class declares `debug` as `bool` defaulting to `True`, and `title` as `str` set to `"Test FastAPI example application"` [[target/app/core/settings/test.py::TestAppSettings]]. The `secret_key` field is typed as `SecretStr` and is hardcoded to `SecretStr("test_secret")`, while `database_url` is typed as `PostgresDsn` with no default, meaning it must be supplied externally [[target/app/core/settings/test.py::TestAppSettings]]. Both `max_connection_count` and `min_connection_count` are `int` fields set to `5`, and `logging_level` is an `int` defaulting to `logging.DEBUG` [[target/app/core/settings/test.py::TestAppSettings]].

The remaining fields — `docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `version`, `api_prefix`, `jwt_token_prefix`, `allowed_hosts`, `loggers`, and `app_env` — are inherited from `AppSettings` and carry their own defaults [[target/app/core/settings/test.py::TestAppSettings]] [[target/app/core/settings/app.py::AppSettings]].

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

