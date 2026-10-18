# profiles

This module serves as the profile-resolution dependency layer for the FastAPI application, providing a reusable injectable function that route handlers can declare to receive a fully resolved `Profile` object from the URL path [[target/app/api/dependencies/profiles.py]].

The single function it defines, `get_profile_by_username_from_path`, is an asynchronous FastAPI dependency that accepts a `username` extracted from the URL path (required to be at least one character long), an optional representation of the currently authenticated caller, and a `ProfilesRepository` instance for database access [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]. The authentication parameter is resolved with `required=False`, so the function handles both authenticated and anonymous callers without raising an error when no session is present [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]].

At runtime the function delegates to the repository's `get_profile_by_username` method, forwarding both the `username` and the optional requesting user so that the repository layer can personalise the result — for example, by indicating whether the caller already follows the target account [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]. If the repository finds no matching record and raises `EntityDoesNotExist`, the function catches that exception and re-raises it as an `HTTPException` carrying a `404 Not Found` status code [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]. When the lookup succeeds, it returns a `Profile` object ready for use by whichever route handler declared this dependency [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]].

## get_profile_by_username_from_path

`get_profile_by_username_from_path` is an asynchronous FastAPI dependency function that fetches a user profile by username and returns it for use in route handlers [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]].

It accepts three injected parameters: a `username` string extracted from the URL path (enforced to be at least one character long), an optional `user` representing the currently authenticated caller, and a `profiles_repo` providing access to profile data [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]. The `user` parameter is resolved through `get_current_user_authorizer` with `required=False`, meaning the function can serve both authenticated and anonymous requests without failing if no session is present [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The `profiles_repo` is resolved through `get_repository`, which supplies a `ProfilesRepository` instance bound to the current database session [[target/app/api/dependencies/database.py::get_repository]].

At runtime, the function delegates to `profiles_repo.get_profile_by_username`, passing both the `username` and the optional `requested_user` — the latter allows the repository layer to personalise the returned profile (for example, to indicate whether the requesting user already follows the target) [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]. If the repository signals that no matching user exists by raising `EntityDoesNotExist`, the function catches it and re-raises an `HTTPException` with a `404 Not Found` status code [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]. On success it returns a `Profile` object [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository

