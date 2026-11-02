# events

[`target/app/db/events.py`](target/app/db/events.py) is a small lifecycle module responsible for managing the PostgreSQL connection pool used by the FastAPI application [[target/app/db/events.py]]. It defines exactly two async functions — `connect_to_db` and `close_db_connection` — which together form a matched pair: one to open the pool at startup and one to shut it down on exit [[target/app/db/events.py::connect_to_db]] [[target/app/db/events.py::close_db_connection]].

[`connect_to_db()`](target/app/db/events.py::connect_to_db) accepts a `FastAPI` application instance and an `AppSettings` configuration object, uses them to call `asyncpg.create_pool` with the database URL and the configured minimum and maximum connection counts, and stores the resulting pool on `app.state.pool` so the rest of the application can reach it for the lifetime of the process [[target/app/db/events.py::connect_to_db]]. [`close_db_connection()`](target/app/db/events.py::close_db_connection) is the counterpart: it takes only the `FastAPI` instance, awaits `app.state.pool.close()` to tear down that same pool, and returns `None` [[target/app/db/events.py::close_db_connection]].

Both functions are `async` and must be awaited by the caller, making them natural fits for FastAPI's startup and shutdown lifecycle event hooks [[target/app/db/events.py::connect_to_db]] [[target/app/db/events.py::close_db_connection]]. Each function also brackets its work with a pair of `loguru` log messages — one before the operation begins and one after it completes — providing an observable trace of connection pool activity in application logs [[target/app/db/events.py::connect_to_db]] [[target/app/db/events.py::close_db_connection]].

## close_db_connection

`close_db_connection` is an asynchronous function that tears down the database connection pool for a running FastAPI application [[target/app/db/events.py::close_db_connection]]. It accepts a single parameter, `app`, typed as `FastAPI`, which provides access to the application's shared state [[target/app/db/events.py::close_db_connection]]. The function returns `None` [[target/app/db/events.py::close_db_connection]].

When called, it first logs an informational message indicating that the database connection is being closed, then awaits `app.state.pool.close()` to asynchronously shut down the connection pool, and finally logs a second message confirming the connection has been closed [[target/app/db/events.py::close_db_connection]]. Because it is declared `async`, it must be awaited by the caller — typically as part of a FastAPI shutdown lifecycle event [[target/app/db/events.py::close_db_connection]]. No exceptions are explicitly raised by the function itself, and it carries no decorators [[target/app/db/events.py::close_db_connection]].

## connect_to_db

`connect_to_db` is an asynchronous function that establishes a PostgreSQL connection pool and attaches it to the application's state [[target/app/db/events.py::connect_to_db]]. It accepts two parameters: a `FastAPI` application instance (`app`) and an `AppSettings` configuration object (`settings`) [[target/app/db/events.py::connect_to_db]]. The function returns `None` [[target/app/db/events.py::connect_to_db]].

When called, it first logs a "Connecting to PostgreSQL" message, then awaits `asyncpg.create_pool`, passing the database URL (converted to a string via `str(settings.database_url)`) along with `settings.min_connection_count` and `settings.max_connection_count` as the minimum and maximum pool sizes [[target/app/db/events.py::connect_to_db]]. The resulting pool is stored on `app.state.pool`, making it accessible to the rest of the application for the lifetime of the process [[target/app/db/events.py::connect_to_db]]. Once the pool is ready, a second log message confirms that the connection has been established [[target/app/db/events.py::connect_to_db]].

