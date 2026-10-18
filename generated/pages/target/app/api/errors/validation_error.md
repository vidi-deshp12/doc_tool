# validation_error

This module centralises validation-error handling for the FastAPI application, defining both the error handler function and the corresponding OpenAPI schema shape [[target/app/api/errors/validation_error.py]].

The single function it exposes, `http422_error_handler`, is an async handler that accepts an unused `Request` object and an `exc` parameter typed as either `RequestValidationError` or `ValidationError` [[target/app/api/errors/validation_error.py::http422_error_handler]]. When invoked, it calls `exc.errors()` to retrieve the structured list of validation failures and wraps that list under an `"errors"` key [[target/app/api/errors/validation_error.py::http422_error_handler]]. It then returns a `JSONResponse` carrying HTTP status 422 (Unprocessable Entity), ensuring that clients always receive validation feedback in a consistent, machine-readable format [[target/app/api/errors/validation_error.py::http422_error_handler]].

Beyond the handler itself, the module also patches `validation_error_response_definition` at import time, setting its `"properties"` to describe an `"errors"` array whose items reference the standard `ValidationError` OpenAPI schema — so the shape of the 422 response body is reflected accurately in the generated API documentation as well [[target/app/api/errors/validation_error.py]].

## http422_error_handler

`http422_error_handler` is an async function that handles validation errors by converting them into a structured JSON response [[target/app/api/errors/validation_error.py::http422_error_handler]]. It accepts two parameters: an unused `Request` object (named `_`) and `exc`, which may be either a `RequestValidationError` or a `ValidationError` [[target/app/api/errors/validation_error.py::http422_error_handler]]. The function calls `exc.errors()` to extract the list of validation error details and wraps them under an `"errors"` key [[target/app/api/errors/validation_error.py::http422_error_handler]]. It returns a `JSONResponse` with HTTP status code 422 (Unprocessable Entity), making the error detail available to the client in a consistent format [[target/app/api/errors/validation_error.py::http422_error_handler]].

