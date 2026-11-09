# database

This module provides FastAPI dependency functions that wire database connectivity into route handlers [[target/app/api/dependencies/database.py]]. It imports FastAPI's `Depends`, asyncpg's `Connection` and `Pool` types, and the project's `BaseRepository` to build a layered dependency chain [[target/app/api/dependencies/database.py]].

The chain starts with `_get_db_pool`, which retrieves the application-level connection pool by reading `request.app.state.pool` and returning it directly to its caller [[target/app/api/dependencies/database.py::_get_db_pool]]. One level up, `_get_connection_from_pool` takes that pool — injected automatically by FastAPI via `_get_db_pool` — and acquires a single connection from it using `pool.acquire()`, yielding the connection as an async context manager so it is returned to the pool as soon as the request finishes [[target/app/api/dependencies/database.py::_get_connection_from_pool]].

At the top of the chain sits `get_repository`, a factory function that accepts any `BaseRepository` subclass and produces a FastAPI-compatible dependency function ready to be used with `Depends` [[target/app/api/dependencies/database.py::get_repository]]. The inner function it returns injects a live database connection through the pool chain and instantiates the requested repository type with that connection, so each request receives a fresh repository instance bound to its own connection [[target/app/api/dependencies/database.py::get_repository]]. Because the inner function closes over the `repo_type` argument, a single call to `get_repository` can be reused across many routes while always producing the correct repository type [[target/app/api/dependencies/database.py::get_repository]].

## _get_connection_from_pool

Acquires a database connection from the pool using `pool.acquire()` and yields it to the caller as an async context manager, returning it to the pool automatically when the caller is done [[target/app/api/dependencies/database.py::_get_connection_from_pool]]. The `pool` parameter is injected by FastAPI's dependency system via `_get_db_pool` [[target/app/api/dependencies/database.py::_get_db_pool]].

> **FastAPI deps:** _get_db_pool

## _get_db_pool

Retrieves the database connection pool attached to the application state [[target/app/api/dependencies/database.py::_get_db_pool]] by reading `request.app.state.pool` and returning it directly to the caller [[target/app/api/dependencies/database.py::_get_db_pool]].

## get_repository

A factory that accepts a `BaseRepository` subclass and returns a FastAPI-compatible dependency function [[target/app/api/dependencies/database.py::get_repository]]. The inner function uses `Depends` to inject a database connection obtained from the connection pool, then instantiates the requested repository type with that connection [[target/app/api/dependencies/database.py::get_repository]]. The returned callable closes over `repo_type` so each call produces a fresh repository instance bound to the resolved connection [[target/app/api/dependencies/database.py::get_repository]].

