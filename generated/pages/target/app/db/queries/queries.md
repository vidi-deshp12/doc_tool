# queries

This module initialises the shared `queries` object that all database-access code in the application relies on [[target/app/db/queries/queries.py]]. It uses `aiosql` to load every SQL file found in the `sql` subdirectory sitting alongside this file, binding them to the `asyncpg` driver so each named query becomes a callable Python method [[target/app/db/queries/queries.py]]. The path is resolved at import time using `pathlib.Path(__file__).parent`, which makes the location portable regardless of where the process is launched from [[target/app/db/queries/queries.py]]. The resulting `queries` object is the single entry point through which the rest of the application executes its database operations [[target/app/db/queries/queries.py]].

