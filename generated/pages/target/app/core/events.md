# events

This module serves as the FastAPI application lifecycle coordinator, providing factory functions that produce the startup and shutdown event handlers responsible for managing the database connection [[target/app/core/events.py]].

`create_start_app_handler` accepts a `FastAPI` application instance and an `AppSettings` configuration object, constructing and returning an inner async callable named `start_app` [[target/app/core/events.py::create_start_app_handler]]. When that callable is invoked during application startup, it establishes the database connection by delegating to `connect_to_db` with the same `app` and `settings` references [[target/app/core/events.py::create_start_app_handler]]. The returned `Callable` is designed to be registered directly as a startup event handler on the FastAPI application [[target/app/core/events.py]].

`create_stop_app_handler` mirrors this pattern for teardown: it accepts a `FastAPI` instance and returns a `Callable` that, when invoked, closes the application's database connection by delegating to `close_db_connection` [[target/app/core/events.py::create_stop_app_handler]]. The inner `stop_app` coroutine is decorated with `@logger.catch`, ensuring that any exception raised during shutdown is captured and logged rather than allowed to propagate [[target/app/core/events.py::create_stop_app_handler]].

Together, the two factory functions form a symmetric pair — one for opening and one for closing the database connection — giving the application a clean, handler-based contract for its full lifecycle [[target/app/core/events.py]].

## create_start_app_handler

Accepts a `FastAPI` application instance and an `AppSettings` configuration object, then constructs and returns an inner async callable, `start_app` [[target/app/core/events.py::create_start_app_handler]]. When invoked, that callable connects the application to the database by calling `connect_to_db` with the same `app` and `settings` arguments [[target/app/core/events.py::create_start_app_handler]]. The returned `Callable` is intended to be registered as a startup event handler on the FastAPI application [[target/app/core/events.py]].

## create_stop_app_handler

Accepts a `FastAPI` instance and returns a `Callable` that, when invoked, closes the application's database connection [[target/app/core/events.py::create_stop_app_handler]]. The returned `stop_app` coroutine delegates teardown to `close_db_connection`, passing the same `app` reference through [[target/app/core/events.py::create_stop_app_handler]]. The inner coroutine is decorated with `@logger.catch`, so any exception it raises is captured and logged rather than propagated [[target/app/core/events.py::create_stop_app_handler]].

