# errors

This module serves as the errors definition layer for the database package, providing a dedicated place to declare database-specific exception types [[target/app/db/errors.py]]. It defines a single class, `EntityDoesNotExist`, which inherits directly from Python's built-in `Exception` and adds no extra fields or methods of its own [[target/app/db/errors.py::EntityDoesNotExist]]. Its sole responsibility, as declared in its docstring, is to be raised whenever a requested entity cannot be located in the database [[target/app/db/errors.py::EntityDoesNotExist]].

## EntityDoesNotExist

`EntityDoesNotExist` is a custom exception class defined in the errors module [[target/app/db/errors.py]]. It inherits directly from Python's built-in `Exception` class and carries no additional fields or methods of its own [[target/app/db/errors.py::EntityDoesNotExist]]. It is not a Pydantic model [[target/app/db/errors.py::EntityDoesNotExist]]. Its sole purpose, as stated in its docstring, is to be raised when an entity cannot be found in the database [[target/app/db/errors.py::EntityDoesNotExist]].

