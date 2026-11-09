# queries

This module serves as the single entry point for all database queries in the application, loading them at import time from the `sql` directory that lives alongside the file [[target/app/db/queries/queries.py]]. It uses the `aiosql` library together with the `asyncpg` driver adapter to parse every `.sql` file found in that directory and expose their named queries as a single `queries` object [[target/app/db/queries/queries.py]]. Because the object is built once when the module is first imported, the rest of the application can access any named query simply by referencing an attribute on `queries`, with no further registration or setup required [[target/app/db/queries/queries.py]].

