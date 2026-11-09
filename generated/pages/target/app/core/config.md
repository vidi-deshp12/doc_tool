# config

This module serves as the central configuration entry point for the application, mapping each supported environment type to its corresponding settings class and exposing a cached factory function for retrieving the active settings [[target/app/core/config.py]]. The `environments` dictionary ties the `AppEnvTypes` enum values — `dev`, `prod`, and `test` — to `DevAppSettings`, `ProdAppSettings`, and `TestAppSettings` respectively, so the correct settings class can be looked up by environment name [[target/app/core/config.py]].

The `get_app_settings` function acts as the single access point for application configuration: it reads the `app_env` field from a `BaseAppSettings` instance to identify the current environment, uses that value as a key into the `environments` mapping, and instantiates the matching settings class [[target/app/core/config.py::get_app_settings]]. Because it is decorated with `@lru_cache`, the instantiation happens only once and every subsequent call receives the same cached `AppSettings` object [[target/app/core/config.py::get_app_settings]]. This design means the rest of the application can call `get_app_settings` freely without repeatedly constructing settings objects or re-reading environment variables [[target/app/core/config.py::get_app_settings]].

## get_app_settings

Reads the `app_env` field from a `BaseAppSettings` instance to determine the current environment, then looks up the matching settings class in the `environments` mapping and instantiates it [[target/app/core/config.py::get_app_settings]]. The `@lru_cache` decorator ensures the result is computed only once and reused on subsequent calls [[target/app/core/config.py::get_app_settings]]. Returns the resulting `AppSettings` instance for the detected environment [[target/app/core/config.py::get_app_settings]].

