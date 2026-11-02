# queries

This module initialises the shared `queries` object used throughout the application by loading all SQL statements from the `sql` subdirectory adjacent to the file, using the `asyncpg` driver adapter [[target/app/db/queries/queries.py]]. It relies on `aiosql` to parse those SQL files and expose each named query as a callable attribute, and on `pathlib` to construct the directory path in a platform-independent way [[target/app/db/queries/queries.py]]. The resulting `queries` object is built once at import time and is the single point of access for all database operations defined in the project's SQL files [[target/app/db/queries/queries.py]].

