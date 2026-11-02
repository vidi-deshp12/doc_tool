# authentication

This module defines the authentication routes for the API, exposing two POST endpoints that handle user login and registration [[target/app/api/routes/authentication.py]]. It creates a single `APIRouter` instance that both handlers are attached to, and all authentication-related HTTP traffic flows through this file [[target/app/api/routes/authentication.py]].

The `login` function handles credential verification for existing users [[target/app/api/routes/authentication.py::login]]. It receives the submitted email and password from the request body, looks up the matching user record via the injected `UsersRepository`, and raises an HTTP 400 error if either the email is not found or the password fails verification [[target/app/api/routes/authentication.py::login]]. On success, it mints a JWT access token using the application secret key and returns the user's profile data bundled with that token in a `UserInResponse` [[target/app/api/routes/authentication.py::login]].

The `register` function handles the creation of new user accounts [[target/app/api/routes/authentication.py::register]]. Before persisting anything, it runs two uniqueness checks against the repository — one for the requested username and one for the requested email — raising an HTTP 400 error if either is already taken [[target/app/api/routes/authentication.py::register]]. If both checks pass, it delegates record creation to `users_repo.create_user`, then immediately mints a JWT access token for the new user using the same approach as `login`, and returns a `UserInResponse` wrapping a `UserWithToken` so the caller is authenticated from the moment of registration [[target/app/api/routes/authentication.py::register]].

The two handlers share the same structural pattern: both accept a `UsersRepository` and `AppSettings` via FastAPI dependency injection, and both produce a `UserInResponse` containing a `UserWithToken` — meaning the token-issuance logic is symmetric across login and registration [[target/app/api/routes/authentication.py::login]] [[target/app/api/routes/authentication.py::register]].

## login

The `login` function is an asynchronous POST endpoint handler registered at `/api/users/login` that authenticates a user and returns a signed JWT token [[target/app/api/routes/authentication.py::login]] [[route:POST /api/users/login]].

It accepts three injected parameters: `user_login` of type `UserInLogin`, which carries the submitted credentials and is bound from the request body under the JSON key `"user"` [[target/app/models/schemas/users.py::UserInLogin]]; `users_repo`, a `UsersRepository` instance provided by the `get_repository` dependency [[target/app/api/dependencies/database.py::get_repository]]; and `settings` of type `AppSettings`, supplied by `get_app_settings` [[target/app/core/config.py::get_app_settings]].

The function first attempts to look up the user by the email address found in `user_login`, querying the repository asynchronously [[target/app/api/routes/authentication.py::login]]. If no matching record exists, the repository raises `EntityDoesNotExist`, which the handler catches and re-raises as an HTTP 400 error [[target/app/api/routes/authentication.py::login]]. If the record is found but the supplied password does not pass the `check_password` verification, the same HTTP 400 error is raised again [[target/app/api/routes/authentication.py::login]].

On successful authentication, the function creates a JWT access token by calling `jwt.create_access_token_for_user`, passing the user object and the application secret key retrieved via `settings.secret_key.get_secret_value()` [[target/app/core/config.py::get_app_settings]] [[target/app/api/routes/authentication.py::login]]. It then constructs and returns a `UserInResponse` wrapping a `UserWithToken` that includes the user's username, email, bio, image, and the newly issued token [[target/app/models/schemas/users.py::UserInResponse]] [[target/app/api/routes/authentication.py::login]].

> **Raises:** wrong_login_error

> **FastAPI deps:** get_repository, get_app_settings

## register

`register` is an asynchronous route handler that processes new user registrations [[target/app/api/routes/authentication.py::register]]. It is registered on the router via a `POST` decorator targeting the `/api/users` endpoint, configured to return HTTP 201 on success and serialise its output as a `UserInResponse` [[route:POST /api/users]] [[target/app/models/schemas/users.py::UserInResponse]].

The function accepts three injected parameters [[target/app/api/routes/authentication.py::register]]. The first, `user_create`, carries the incoming registration payload and is typed as `UserInCreate`, embedded in the request body under the JSON key `"user"` [[target/app/models/schemas/users.py::UserInCreate]]. The second, `users_repo`, is a `UsersRepository` instance supplied by FastAPI's dependency injection through `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. The third, `settings`, provides application-wide configuration and is resolved via `get_app_settings` [[target/app/core/config.py::get_app_settings]].

Before creating the user, the function performs two uniqueness checks [[target/app/api/routes/authentication.py::register]]. If the requested username is already in use, it raises an `HTTPException` with HTTP 400 [[target/app/api/routes/authentication.py::register]]. If the requested email address is already taken, it raises a second `HTTPException` with HTTP 400 [[target/app/api/routes/authentication.py::register]].

Once both checks pass, the function creates the user record by delegating to `users_repo.create_user` with the validated payload fields [[target/app/api/routes/authentication.py::register]]. It then mints a JWT access token by calling `jwt.create_access_token_for_user`, passing the new user and the application secret key retrieved from `settings` [[target/app/api/routes/authentication.py::register]] [[target/app/core/config.py::get_app_settings]]. Finally, it constructs and returns a `UserInResponse` wrapping a `UserWithToken` that bundles the user's profile fields together with the freshly issued token [[target/app/models/schemas/users.py::UserInResponse]] [[target/app/api/routes/authentication.py::register]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_repository, get_app_settings

