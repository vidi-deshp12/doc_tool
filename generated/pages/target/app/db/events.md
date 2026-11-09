# events

This module manages the lifecycle of the asyncpg database connection pool for the FastAPI application [[target/app/db/events.py]]. It defines two functions that are intended to be called at application startup and shutdown respectively [[target/app/db/events.py::connect_to_db]] [[target/app/db/events.py::close_db_connection]].

The `connect_to_db` function establishes an asyncpg connection pool and attaches it to `app.state.pool` so the rest of the application can access it [[target/app/db/events.py::connect_to_db]]. It derives the pool configuration from an `AppSettings` instance, converting `settings.database_url` to a string and passing `settings.min_connection_count` and `settings.max_connection_count` as the lower and upper bounds for the pool size [[target/app/db/events.py::connect_to_db]]. Progress is recorded via `logger.info` both before and after the pool is created [[target/app/db/events.py::connect_to_db]].

The `close_db_connection` function handles the complementary teardown: it logs a message, closes the pool stored on the application state, and logs a confirmation once the shutdown is complete [[target/app/db/events.py::close_db_connection]]. Together the two functions ensure the connection pool is cleanly opened and closed around the application's lifespan [[target/app/db/events.py::connect_to_db]] [[target/app/db/events.py::close_db_connection]].

## close_db_connection

Logs a message, closes the asyncpg connection pool stored on the application state, and logs a confirmation once the pool is shut down [[target/app/db/events.py::close_db_connection]].

## connect_to_db

Establishes an asyncpg connection pool and attaches it to `app.state.pool` for use by the application [[target/app/db/events.py::connect_to_db]]. It converts `settings.database_url` to a string and passes `settings.min_connection_count` and `settings.max_connection_count` as the pool size bounds to `asyncpg.create_pool` [[target/app/db/events.py::connect_to_db]]. Progress is logged via `logger.info` before and after the pool is created [[target/app/db/events.py::connect_to_db]].

