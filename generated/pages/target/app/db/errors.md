# errors

This module serves as a dedicated home for database-related exception types used across the application [[target/app/db/errors.py]]. It defines a single class, `EntityDoesNotExist`, which inherits directly from Python's built-in `Exception` and adds no extra fields or methods [[target/app/db/errors.py::EntityDoesNotExist]]. Its purpose is narrow and explicit: it is raised whenever a requested entity cannot be found in the database, making lookup failures distinguishable from other error conditions by catching this specific type [[target/app/db/errors.py::EntityDoesNotExist]].

## EntityDoesNotExist

`EntityDoesNotExist` is a plain Python exception class defined in [`target/app/db/errors.py`](target/app/db/errors.py) [[target/app/db/errors.py]]. It inherits directly from the built-in `Exception` and carries no additional fields or methods [[target/app/db/errors.py::EntityDoesNotExist]]. Its sole purpose, as stated in its docstring, is to be raised when an entity cannot be found in the database [[target/app/db/errors.py::EntityDoesNotExist]]. It is not a Pydantic model [[target/app/db/errors.py::EntityDoesNotExist]].

