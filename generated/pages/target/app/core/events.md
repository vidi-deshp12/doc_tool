# events

[`target/app/core/events.py`](target/app/core/events.py) is a module responsible for wiring up the application's database lifecycle — specifically, producing the startup and shutdown handlers that connect to and disconnect from the database at the appropriate moments in a FastAPI application's lifecycle [[target/app/core/events.py]].

The module exposes two factory functions. `create_start_app_handler` accepts a `FastAPI` instance and an `AppSettings` configuration object and returns a `Callable` [[target/app/core/events.py::create_start_app_handler]]. The callable it returns is an async function that, when invoked, calls `connect_to_db` with the application and settings, establishing the database connection [[target/app/core/events.py::create_start_app_handler]]. By closing over both arguments at construction time, the handler defers the actual connection work until the application starts up [[target/app/core/events.py]].

The companion function, `create_stop_app_handler`, accepts only a `FastAPI` instance and returns a `Callable` suited for registration as an on-shutdown handler [[target/app/core/events.py::create_stop_app_handler]]. The inner async function it produces is decorated with `@logger.catch`, which intercepts and logs any exceptions raised during teardown, and calls `close_db_connection` with the application instance to cleanly close the database connection [[target/app/core/events.py::create_stop_app_handler]].

Together, the two factory functions follow the same structural pattern: each captures its arguments in a closure, builds an async inner callable that performs the real work, and returns that callable for the application to register on its startup and shutdown hooks [[target/app/core/events.py::create_start_app_handler]] [[target/app/core/events.py::create_stop_app_handler]].

## create_start_app_handler

`create_start_app_handler` is a factory function that accepts a `FastAPI` application instance and an `AppSettings` configuration object, and returns a `Callable` [[target/app/core/events.py::create_start_app_handler]]. The returned callable is an async inner function named `start_app` which, when invoked, connects the application to its database by calling `connect_to_db` with the provided `app` and `settings` arguments [[target/app/core/events.py::create_start_app_handler]]. This pattern allows the startup handler to close over the application and settings at construction time, deferring the actual connection until the handler is called during the application lifecycle [[target/app/core/events.py]].

## create_stop_app_handler

`create_stop_app_handler` is a factory function that accepts a `FastAPI` application instance as its sole argument and returns a `Callable` [[target/app/core/events.py::create_stop_app_handler]]. Its purpose is to produce a shutdown handler suitable for registration with the application's lifecycle events [[target/app/core/events.py::create_stop_app_handler]]. Internally, it defines an async inner function named `stop_app` that is decorated with `@logger.catch` — a decorator that intercepts and logs any exceptions raised during execution — and when invoked, calls `close_db_connection` with the `app` instance to tear down the database connection [[target/app/core/events.py::create_stop_app_handler]]. The outer function returns this inner `stop_app` callable directly, allowing the caller to register it as an on-shutdown handler [[target/app/core/events.py::create_stop_app_handler]].

