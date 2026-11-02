# main

This module serves as the application entry point for the FastAPI service, defining the factory function that assembles the application and immediately invoking it to produce the module-level `app` instance [[target/app/main.py]].

The sole function defined here, `get_application`, is a factory that constructs and fully configures a `FastAPI` application instance, returning it ready for use [[target/app/main.py::get_application]]. It begins by retrieving application settings and using them to configure logging [[target/app/main.py::get_application]]. A `FastAPI` instance is then created using keyword arguments drawn from those settings [[target/app/main.py::get_application]].

Once the base application is created, `get_application` attaches CORS middleware configured with settings-driven allowed hosts, permitting all HTTP methods and headers and enabling credentials [[target/app/main.py::get_application]]. Lifecycle management is handled by registering event handlers for both `"startup"` and `"shutdown"` events: the startup handler is produced by `create_start_app_handler` (receiving both the application and settings), while the shutdown handler is produced by `create_stop_app_handler` (receiving only the application) [[target/app/main.py::get_application]]. Error handling is wired up by registering two exception handlers — one for `HTTPException` and one for `RequestValidationError` — each mapped to a dedicated handler function [[target/app/main.py::get_application]]. The API router is then mounted under the prefix defined in settings, completing the assembly before the configured `FastAPI` instance is returned [[target/app/main.py::get_application]].

At module level, `get_application` is called immediately so that the resulting `app` object is available for import by an ASGI server or other consumers [[target/app/main.py]].

## get_application

`get_application` is a factory function that constructs and fully configures the FastAPI application instance, returning it ready for use [[target/app/main.py::get_application]]. It begins by retrieving application settings and immediately using them to configure logging [[target/app/main.py::get_application]]. A `FastAPI` instance is then created using keyword arguments drawn from those settings [[target/app/main.py::get_application]].

CORS middleware is attached to the application with settings-driven allowed hosts, permitting all methods and headers and enabling credentials [[target/app/main.py::get_application]]. Lifecycle event handlers are registered for both `"startup"` and `"shutdown"` events: the startup handler is produced by `create_start_app_handler`, receiving both the application and settings, while the shutdown handler is produced by `create_stop_app_handler`, receiving only the application [[target/app/main.py::get_application]].

Two exception handlers are registered: one for `HTTPException` and one for `RequestValidationError`, mapping each to a dedicated handler function [[target/app/main.py::get_application]]. Finally, the API router is mounted onto the application under the prefix defined in settings, and the fully assembled `FastAPI` instance is returned [[target/app/main.py::get_application]].

