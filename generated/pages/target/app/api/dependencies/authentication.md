# authentication

This module provides the complete authentication dependency layer for the FastAPI application, handling JWT Bearer token extraction, validation, and user resolution for both required and optional authentication scenarios [[target/app/api/dependencies/authentication.py]].

The foundation is `RWAPIKeyHeader`, a subclass of FastAPI's `APIKeyHeader` that overrides `__call__` to catch any `StarletteHTTPException` raised by the parent and re-raise it as an application-level `HTTPException` with the detail message set to `strings.AUTHENTICATION_REQUIRED`, ensuring a consistent error shape across the API [[target/app/api/dependencies/authentication.py::RWAPIKeyHeader]].

Token extraction is handled by two complementary functions. `_get_authorization_header` splits the raw header value on a space, verifies the prefix matches the configured `jwt_token_prefix`, and returns the bare token string, raising an HTTP 403 exception if either check fails [[target/app/api/dependencies/authentication.py::_get_authorization_header]]. `_get_authorization_header_optional` wraps that logic: when a header is present it delegates to `_get_authorization_header`, and when none is supplied it returns an empty string instead of raising an error, relying on `RWAPIKeyHeader` configured with `auto_error=False` to make the header absence non-fatal [[target/app/api/dependencies/authentication.py::_get_authorization_header_optional]]. The factory function `_get_authorization_header_retriever` selects between these two by returning `_get_authorization_header` when `required=True` or `_get_authorization_header_optional` when `required=False` [[target/app/api/dependencies/authentication.py::_get_authorization_header_retriever]].

User resolution follows the same required/optional pattern. `_get_current_user` decodes the JWT using the app's secret key to extract a username, raises HTTP 403 if the payload is malformed, then fetches the matching `User` from `UsersRepository`, raising a second HTTP 403 if no such user exists [[target/app/api/dependencies/authentication.py::_get_current_user]]. `_get_current_user_optional` provides the relaxed variant: it uses `_get_authorization_header_retriever` with `required=False`, and when no token is present it returns `None` rather than raising, delegating to `_get_current_user` only when a token is actually provided [[target/app/api/dependencies/authentication.py::_get_current_user_optional]].

The public entry point for route authors is `get_current_user_authorizer`, a factory that returns `_get_current_user` when `required=True` (the default) or `_get_current_user_optional` when `required=False`, yielding a `Callable` ready to be declared as a FastAPI dependency that enforces or relaxes authentication depending on the needs of each route [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]].

## RWAPIKeyHeader

`RWAPIKeyHeader` is a subclass of FastAPI's external `APIKeyHeader` security class [[target/app/api/dependencies/authentication.py::RWAPIKeyHeader]]. It is not a Pydantic model and declares no additional fields of its own [[target/app/api/dependencies/authentication.py::RWAPIKeyHeader]]. Its sole behavioural addition is an overridden `__call__` method that delegates to the parent's `__call__` implementation by awaiting `super().__call__(request)` [[target/app/api/dependencies/authentication.py::RWAPIKeyHeader::__call__]]. When the parent raises a `StarletteHTTPException`, the override catches it and re-raises it as an `HTTPException` carrying the same status code but with the detail message replaced by `strings.AUTHENTICATION_REQUIRED`, giving the application a consistent, application-level error response for missing or invalid API keys [[target/app/api/dependencies/authentication.py::RWAPIKeyHeader::__call__]].

### __call__

Delegates to the parent class's `__call__` implementation by awaiting `super().__call__(request)` [[target/app/api/dependencies/authentication.py::RWAPIKeyHeader::__call__]]. If the parent raises a `StarletteHTTPException`, it is caught and re-raised as a `HTTPException` with the same status code but with the detail message replaced by `strings.AUTHENTICATION_REQUIRED` [[target/app/api/dependencies/authentication.py::RWAPIKeyHeader::__call__]].

> **Raises:** starlette.exceptions.HTTPException

## _get_authorization_header

Extracts and validates the Bearer-style token from an incoming API key header by splitting the raw header value on a space and returning the token portion [[target/app/api/dependencies/authentication.py::_get_authorization_header]]. It depends on `get_app_settings` to retrieve the configured JWT token prefix used for comparison [[target/app/core/config.py::get_app_settings]]. If the header value cannot be split into exactly two parts, it raises an `HTTPException` with HTTP 403 [[target/app/api/dependencies/authentication.py::_get_authorization_header]]. If the prefix portion does not match `settings.jwt_token_prefix`, it raises a second `HTTPException` with HTTP 403 [[target/app/api/dependencies/authentication.py::_get_authorization_header]]. On success, the bare token string (without the prefix) is returned [[target/app/api/dependencies/authentication.py::_get_authorization_header]].

> **Raises:** starlette.exceptions.HTTPException

> **FastAPI deps:** get_app_settings

## _get_authorization_header_optional

When an `Authorization` header is present, it delegates to `_get_authorization_header` to validate and extract the token, forwarding both the raw header value and the injected application settings [[target/app/api/dependencies/authentication.py::_get_authorization_header_optional]]. When no header is supplied, it returns an empty string rather than raising an error, making the credential optional [[target/app/api/dependencies/authentication.py::_get_authorization_header_optional]]. Application settings are provided via `get_app_settings` [[target/app/core/config.py::get_app_settings]], and the header is read without forcing an error on absence thanks to `RWAPIKeyHeader` configured with `auto_error=False` [[target/app/api/dependencies/authentication.py::_get_authorization_header_optional]].

> **FastAPI deps:** get_app_settings

## _get_authorization_header_retriever

Returns `_get_authorization_header` when `required` is `True`, or `_get_authorization_header_optional` when `required` is `False`, acting as a factory that selects the appropriate authorization header retriever based on whether the header is mandatory [[target/app/api/dependencies/authentication.py::_get_authorization_header_retriever]].

## _get_current_user

Decodes the JWT `token` using the app's secret key to extract a username, raising an `HTTPException` with status 403 if the token payload is malformed [[target/app/api/dependencies/authentication.py::_get_current_user]] [[target/app/api/dependencies/authentication.py::_get_authorization_header_retriever]] [[target/app/core/config.py::get_app_settings]]. If the token is valid, it fetches and returns the corresponding `User` from the database via `users_repo` [[target/app/api/dependencies/authentication.py::_get_current_user]] [[target/app/api/dependencies/database.py::get_repository]]. A second `HTTPException` with status 403 is raised if no user matching the extracted username exists in the repository [[target/app/api/dependencies/authentication.py::_get_current_user]].

> **Raises:** starlette.exceptions.HTTPException

> **FastAPI deps:** _get_authorization_header_retriever, get_repository, get_app_settings

## _get_current_user_optional

Resolves the current user from an optional Bearer token, returning `None` when no token is present rather than raising an error [[target/app/api/dependencies/authentication.py::_get_current_user_optional]]. It injects a `UsersRepository` via `get_repository` [[target/app/api/dependencies/database.py::get_repository]], retrieves an authorization header through `_get_authorization_header_retriever` configured with `required=False` [[target/app/api/dependencies/authentication.py::_get_authorization_header_retriever]], and receives application settings via `get_app_settings` [[target/app/core/config.py::get_app_settings]]. When a token is present, it delegates to `_get_current_user` with the repository, token, and settings to perform the actual lookup and return a `User` [[target/app/api/dependencies/authentication.py::_get_current_user_optional]].

> **FastAPI deps:** _get_authorization_header_retriever, get_repository, get_app_settings

## get_current_user_authorizer

Returns `_get_current_user` when `required` is `True` (the default), or `_get_current_user_optional` when `required` is `False`, allowing callers to select between mandatory and optional authentication [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The returned `Callable` is intended for use as a FastAPI dependency that enforces or relaxes the authentication requirement depending on the route [[target/app/api/dependencies/authentication.py]].

