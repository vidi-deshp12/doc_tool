# http_error

This module provides a custom HTTP error handler for a FastAPI application [[target/app/api/errors/http_error.py]]. It defines a single function, `http_error_handler`, which accepts an incoming request and an `HTTPException`, then formats the exception's detail into a structured `{"errors": [...]}` list and returns a `JSONResponse` carrying the exception's original status code [[target/app/api/errors/http_error.py::http_error_handler]]. The module imports `HTTPException` from FastAPI along with Starlette's `Request` and `JSONResponse` types, which are the building blocks that `http_error_handler` relies on to receive the error and produce a consistently shaped response [[target/app/api/errors/http_error.py]].

## http_error_handler

Accepts a request (ignored) and an `HTTPException`, then wraps the exception's detail in an `{"errors": [...]}` list and returns a `JSONResponse` using the exception's status code [[target/app/api/errors/http_error.py::http_error_handler]].

