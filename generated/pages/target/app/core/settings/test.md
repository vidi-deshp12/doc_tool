# test

This module defines the test-environment configuration for the FastAPI application [[target/app/core/settings/test.py]]. It contains a single class, `TestAppSettings`, which extends `AppSettings` and overrides a focused set of fields with values designed for automated testing [[target/app/core/settings/test.py::TestAppSettings]].

`TestAppSettings` is a Pydantic model that fixes several settings to make test runs deterministic and self-contained [[target/app/core/settings/test.py::TestAppSettings]]. The `debug` flag is enabled and `title` is set to `"Test FastAPI example application"`, clearly marking the running instance as a test build [[target/app/core/settings/test.py::TestAppSettings]]. The `secret_key` is hardcoded to the literal `SecretStr("test_secret")`, ensuring that any cryptographic operations produce consistent, reproducible results across all test runs [[target/app/core/settings/test.py::TestAppSettings]]. Both `max_connection_count` and `min_connection_count` are capped at `5`, keeping the database connection pool deliberately small during testing [[target/app/core/settings/test.py::TestAppSettings]]. The `logging_level` is set to `logging.DEBUG` so that the full log output is available when diagnosing test failures [[target/app/core/settings/test.py::TestAppSettings]].

One field is intentionally left without a default: `database_url`, typed as `PostgresDsn`, must be supplied externally — for example via an environment variable — even in the test environment [[target/app/core/settings/test.py::TestAppSettings]]. All remaining fields (`docs_url`, `openapi_prefix`, `openapi_url`, `redoc_url`, `version`, `api_prefix`, `jwt_token_prefix`, `allowed_hosts`, `loggers`, and `app_env`) are inherited from `AppSettings` without modification [[target/app/core/settings/test.py::TestAppSettings]].

## TestAppSettings

`TestAppSettings` is a Pydantic model that extends `AppSettings` and provides a fixed, test-friendly configuration for the FastAPI application [[target/app/core/settings/test.py::TestAppSettings]] [[target/app/core/settings/app.py::AppSettings]]. It overrides several base-class fields with values suited to an automated test environment [[target/app/core/settings/test.py::TestAppSettings]].

The `debug` field is set to `True` and `title` is set to `"Test FastAPI example application"`, identifying the running instance as a test build [[target/app/core/settings/test.py::TestAppSettings]]. The `secret_key` is fixed at the literal value `SecretStr("test_secret")`, making cryptographic operations deterministic and reproducible across test runs [[target/app/core/settings/test.py::TestAppSettings]]. Both `max_connection_count` and `min_connection_count` are set to `5`, keeping the connection pool small during testing [[target/app/core/settings/test.py::TestAppSettings]]. The `logging_level` is set to `logging.DEBUG` so that all log output is visible when running tests [[target/app/core/settings/test.py::TestAppSettings]]. The `database_url` field of type `PostgresDsn` is declared without a default, meaning it must be supplied externally (for example via an environment variable) even in the test environment [[target/app/core/settings/test.py::TestAppSettings]].

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

