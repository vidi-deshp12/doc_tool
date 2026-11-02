# config

This module serves as the central configuration entry point for the application, mapping environment identifiers to their corresponding settings classes and exposing a single cached accessor for the active configuration [[target/app/core/config.py]]. It defines an `environments` dictionary that associates each `AppEnvTypes` variant — `dev`, `prod`, and `test` — with the matching settings class (`DevAppSettings`, `ProdAppSettings`, or `TestAppSettings` respectively) [[target/app/core/config.py]].

The sole function defined here, `get_app_settings`, acts as a cached factory: it reads the current environment from `BaseAppSettings`, looks up the appropriate class in the `environments` mapping, instantiates it, and returns the resulting `AppSettings` object [[target/app/core/config.py::get_app_settings]]. Because it is decorated with `@lru_cache`, this resolution happens only once per process lifetime — every subsequent call receives the same cached instance without re-reading the environment [[target/app/core/config.py::get_app_settings]]. The function takes no parameters and its return type is declared as `AppSettings` [[target/app/core/config.py::get_app_settings]].

## get_app_settings

`get_app_settings` is a cached factory function that reads the current application environment and returns the appropriate `AppSettings` configuration object [[target/app/core/config.py::get_app_settings]]. It is decorated with `@lru_cache`, meaning the result is computed only once and reused on every subsequent call [[target/app/core/config.py::get_app_settings]]. Internally, it instantiates `BaseAppSettings` to read the `app_env` value, then looks up the matching settings class in an `environments` mapping and calls it to produce the final `AppSettings` instance [[target/app/core/config.py::get_app_settings]]. The function takes no parameters and its declared return type is `AppSettings` [[target/app/core/config.py::get_app_settings]].

