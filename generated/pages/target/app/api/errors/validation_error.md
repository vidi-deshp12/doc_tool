# validation_error

This module provides validation-error handling infrastructure for the FastAPI application [[target/app/api/errors/validation_error.py]]. Its central piece is `http422_error_handler`, an asynchronous function that intercepts HTTP 422 Unprocessable Entity errors and converts them into a consistent JSON response [[target/app/api/errors/validation_error.py::http422_error_handler]].

The handler accepts a `Request` object (left intentionally unused, hence the `_` name) and an `exc` argument typed as either a `RequestValidationError` or a `ValidationError`, covering both FastAPI-level and Pydantic-level validation failures [[target/app/api/errors/validation_error.py::http422_error_handler]]. It calls `exc.errors()` to extract the structured list of validation problems and wraps that list under an `"errors"` key before returning a `JSONResponse` with status code `HTTP_422_UNPROCESSABLE_ENTITY` [[target/app/api/errors/validation_error.py::http422_error_handler]].

Beyond the handler itself, the module also patches the OpenAPI schema at import time by rewriting the `"properties"` entry of `validation_error_response_definition` so that the `"errors"` field is described as an array of `ValidationError` schema references — keeping the auto-generated API documentation consistent with the actual response shape [[target/app/api/errors/validation_error.py]].

## http422_error_handler

`http422_error_handler` is an asynchronous function that handles HTTP 422 Unprocessable Entity errors by converting validation exceptions into a structured JSON response [[target/app/api/errors/validation_error.py::http422_error_handler]].

It accepts two parameters: a `Request` object (unused, indicated by the `_` name) and an `exc` argument typed as either a `RequestValidationError` or a `ValidationError` [[target/app/api/errors/validation_error.py::http422_error_handler]]. The function calls `exc.errors()` to retrieve the list of validation error details and wraps them under an `"errors"` key [[target/app/api/errors/validation_error.py::http422_error_handler]]. It then returns a `JSONResponse` with that payload and a status code of `HTTP_422_UNPROCESSABLE_ENTITY` [[target/app/api/errors/validation_error.py::http422_error_handler]].

