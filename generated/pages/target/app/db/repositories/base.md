# base

[`target/app/db/repositories/base.py`](target/app/db/repositories/base.py) is a small foundational module that imports `Connection` from `asyncpg` and defines the single class `BaseRepository`, which acts as the shared base for all database repository classes in the project [[target/app/db/repositories/base.py]]. `BaseRepository` declares no parent classes of its own, keeping it a plain Python class [[target/app/db/repositories/base.py::BaseRepository]]. It accepts an asyncpg `Connection` instance at construction time and stores it in the private attribute `_conn`, making the active database connection available to every subclass that needs to run queries [[target/app/db/repositories/base.py::BaseRepository]]. A read-only `connection` property exposes `_conn` to those subclasses without requiring them to reference the private attribute directly, providing a clean and consistent interface to the underlying connection [[target/app/db/repositories/base.py::BaseRepository]].

## BaseRepository

`BaseRepository` is a plain Python class (not a Pydantic model) that serves as the foundation for all database repository classes in the project [[target/app/db/repositories/base.py::BaseRepository]]. It declares no base classes of its own [[target/app/db/repositories/base.py::BaseRepository]].

At construction time it accepts an asyncpg `Connection` instance and stores it in the private attribute `_conn`, making it available to any subclass that needs to execute queries [[target/app/db/repositories/base.py::BaseRepository::__init__]]. A `connection` property exposes `_conn` as read-only access to that underlying `Connection` object, so subclasses can retrieve the active connection without directly referencing the private attribute [[target/app/db/repositories/base.py::BaseRepository::connection]].

### __init__

Accepts an asyncpg `Connection` instance and stores it as the private attribute `_conn` for use by subclasses [[target/app/db/repositories/base.py::BaseRepository::__init__]].

### connection

Returns the private `_conn` attribute as the repository's active database connection, providing read-only access to the underlying `Connection` object stored at construction time [[target/app/db/repositories/base.py::BaseRepository::connection]].

