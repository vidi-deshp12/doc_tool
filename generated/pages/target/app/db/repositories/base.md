# base

This module defines the shared foundation for all database repository classes in the application [[target/app/db/repositories/base.py]]. It contains a single class, `BaseRepository`, which acts as the root of the repository hierarchy without declaring any base classes of its own [[target/app/db/repositories/base.py::BaseRepository]].

`BaseRepository` is a plain Python class whose constructor accepts a single `conn` parameter of type `Connection` and stores it as the private instance attribute `_conn`, with no additional logic or side effects [[target/app/db/repositories/base.py::BaseRepository]]. This stored connection is the live database connection that all methods in the class hierarchy rely on [[target/app/db/repositories/base.py::BaseRepository]].

Public access to that connection is provided through the read-only `connection` property, decorated with `@property`, which returns `_conn` as a `Connection` instance [[target/app/db/repositories/base.py::BaseRepository]]. Because no setter is defined, the connection cannot be reassigned after construction, giving subclasses and callers a controlled, uniform interface to the injected connection [[target/app/db/repositories/base.py::BaseRepository]].

## BaseRepository

`BaseRepository` is a plain Python class (not a Pydantic model) that serves as the shared foundation for all database repository classes in the application [[target/app/db/repositories/base.py::BaseRepository]]. It declares no base classes of its own, acting as the root of the repository hierarchy [[target/app/db/repositories/base.py::BaseRepository]].

The class holds a single field, the private instance attribute `_conn`, which is assigned during construction and carries the live database connection for use by all methods in the class hierarchy [[target/app/db/repositories/base.py::BaseRepository::__init__]]. The constructor accepts exactly one parameter, `conn` of type `Connection`, and stores it as `_conn` with no additional logic, decorators, or raised exceptions [[target/app/db/repositories/base.py::BaseRepository::__init__]].

Public access to that connection is exposed through the `connection` property, which is decorated with `@property` and returns the stored `_conn` as a `Connection` instance [[target/app/db/repositories/base.py::BaseRepository::connection]]. Because the property provides no setter, the connection is effectively read-only after construction, giving subclasses and callers a controlled, uniform interface to the injected connection without allowing direct reassignment [[target/app/db/repositories/base.py::BaseRepository::connection]] [[target/app/db/repositories/base.py::BaseRepository]].

### __init__

The `__init__` method is the constructor for the `BaseRepository` class, responsible for initialising a new repository instance with a database connection [[target/app/db/repositories/base.py::BaseRepository::__init__]]. It accepts a single parameter `conn` of type `Connection` and stores it as the private instance attribute `_conn`, making the connection available to all methods in the class hierarchy [[target/app/db/repositories/base.py::BaseRepository::__init__]]. The method returns `None` and contains no decorators, raised exceptions, or additional calls beyond the attribute assignment [[target/app/db/repositories/base.py::BaseRepository::__init__]]. By capturing the connection at construction time, `BaseRepository` establishes the shared database access pattern that all concrete repository subclasses inherit [[target/app/db/repositories/base.py::BaseRepository]].

### connection

The `connection` property belongs to the `BaseRepository` class and provides read-only access to the underlying database connection object [[target/app/db/repositories/base.py::BaseRepository::connection]]. Decorated with `@property`, it exposes the private `_conn` attribute as a public interface without allowing direct assignment [[target/app/db/repositories/base.py::BaseRepository::connection]]. It takes no arguments beyond `self` and returns a `Connection` instance [[target/app/db/repositories/base.py::BaseRepository::connection]]. Its role within `BaseRepository` is to give subclasses and callers a controlled, uniform way to access the connection that was injected into the repository at construction time [[target/app/db/repositories/base.py::BaseRepository]] [[target/app/db/repositories/base.py::BaseRepository::connection]].

