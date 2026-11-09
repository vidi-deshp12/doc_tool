# errors

The [`errors.py`](target/app/db/errors.py) module serves as the home for database-layer exception types used across the application [[target/app/db/errors.py]]. It defines a single custom exception, `EntityDoesNotExist`, which extends Python's built-in `Exception` and carries no additional fields or methods beyond what it inherits [[target/app/db/errors.py::EntityDoesNotExist]]. Its sole responsibility is to signal that a requested entity could not be found in the database, making it a lightweight sentinel rather than a data-carrying object [[target/app/db/errors.py::EntityDoesNotExist]].

## EntityDoesNotExist

`EntityDoesNotExist` is a custom exception class that extends Python's built-in `Exception` [[target/app/db/errors.py::EntityDoesNotExist]]. It is defined in [`errors.py`](target/app/db/errors.py) and carries no additional fields or methods beyond what it inherits from `Exception` [[target/app/db/errors.py::EntityDoesNotExist]]. Its sole responsibility is to signal that a requested entity could not be found in the database [[target/app/db/errors.py::EntityDoesNotExist]]. It is not a Pydantic model [[target/app/db/errors.py::EntityDoesNotExist]].

