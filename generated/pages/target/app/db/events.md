# events

`target/app/db/events.py` is a module responsible for managing the lifecycle of the application's PostgreSQL connection pool [[target/app/db/events.py]]. It defines exactly two async functions — `connect_to_db` and `close_db_connection` — that are intended to be called at application startup and shutdown respectively [[target/app/db/events.py::connect_to_db]] [[target/app/db/events.py::close_db_connection]].

`connect_to_db` takes a `FastAPI` instance and an `AppSettings` object, uses `asyncpg.create_pool` to open a pool of PostgreSQL connections sized according to `settings.min_connection_count` and `settings.max_connection_count`, and stores the resulting pool on `app.state.pool` so that the rest of the application can reach it for the duration of its lifetime [[target/app/db/events.py::connect_to_db]]. Any failure inside `asyncpg.create_pool` — such as an unreachable host or invalid credentials — propagates directly to the caller, since the function catches no exceptions of its own [[target/app/db/events.py::connect_to_db]].

`close_db_connection` is the symmetric counterpart: it accepts only the `FastAPI` instance, retrieves the same `app.state.pool` that `connect_to_db` placed there, and awaits its `close()` method to tear the pool down cleanly [[target/app/db/events.py::close_db_connection]]. Both functions bracket their core operation with `loguru` log messages — one before and one after — so that connection events appear in the application's log output [[target/app/db/events.py::connect_to_db]] [[target/app/db/events.py::close_db_connection]]. Because both functions use `await`, they must be called from an asynchronous context, which aligns with FastAPI's async startup and shutdown event hooks [[target/app/db/events.py::connect_to_db]] [[target/app/db/events.py::close_db_connection]].

## close_db_connection

`close_db_connection` is an asynchronous function that tears down the database connection pool for the application [[target/app/db/events.py::close_db_connection]]. It accepts a single parameter, `app`, typed as `FastAPI`, which provides access to the application's shared state [[target/app/db/events.py::close_db_connection]]. The function returns `None` [[target/app/db/events.py::close_db_connection]].

When called, it first emits an informational log message indicating that the database connection is being closed, then awaits `app.state.pool.close()` to shut down the connection pool, and finally logs a second message confirming the connection has been closed [[target/app/db/events.py::close_db_connection]]. Because it uses `await`, it must be called from within an asynchronous context [[target/app/db/events.py::close_db_connection]]. No exceptions are explicitly raised or caught within the function body, and it carries no decorators [[target/app/db/events.py::close_db_connection]].

## connect_to_db

`connect_to_db` is an asynchronous function that establishes a PostgreSQL connection pool and attaches it to the FastAPI application's shared state [[target/app/db/events.py::connect_to_db]]. It accepts two parameters: `app`, a `FastAPI` instance, and `settings`, an `AppSettings` object that carries database configuration such as the database URL and connection pool bounds [[target/app/db/events.py::connect_to_db]].

When called, the function logs a "Connecting to PostgreSQL" message before attempting the connection, then invokes `asyncpg.create_pool` with the database URL (converted to a string via `str`) along with `min_size` and `max_size` drawn from `settings.min_connection_count` and `settings.max_connection_count` respectively [[target/app/db/events.py::connect_to_db]]. The resulting pool is stored on `app.state.pool`, making it accessible to the rest of the application for the duration of its lifetime [[target/app/db/events.py::connect_to_db]]. Once the pool is ready, a second log entry confirms that the connection has been established [[target/app/db/events.py::connect_to_db]].

The function returns `None` and declares no exceptions of its own, though failures in `asyncpg.create_pool` (for example an unreachable host or invalid credentials) would propagate to the caller [[target/app/db/events.py::connect_to_db]].

