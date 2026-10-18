# authentication

This module defines the authentication routes for the API, housing the two endpoints responsible for user login and registration [[target/app/api/routes/authentication.py]]. It creates a single `APIRouter` instance that both handlers are attached to, and all imports — schemas, repository classes, JWT utilities, settings, and uniqueness-check helpers — are consolidated here to support those two operations [[target/app/api/routes/authentication.py]].

The `login` function is an async route handler bound to `POST /login` that authenticates an existing user [[target/app/api/routes/authentication.py::login]]. It receives the caller's credentials from the request body, looks up the matching account via `users_repo.get_user_by_email`, and verifies the submitted password with `user.check_password` [[target/app/api/routes/authentication.py::login]]. To avoid leaking information about whether an account exists, both a missing account and a wrong password are surfaced through the same generic 400 Bad Request error [[target/app/api/routes/authentication.py::login]]. When credentials are valid, a JWT is minted with `jwt.create_access_token_for_user` using the application secret key, and the handler returns a `UserInResponse` wrapping a `UserWithToken` that carries the user's `username`, `email`, `bio`, `image`, and the new `token` [[target/app/api/routes/authentication.py::login]].

The `register` function is an async route handler bound to `POST ""` (the router's root) with a 201 Created status, and it creates a brand-new user account [[target/app/api/routes/authentication.py::register]]. Before persisting anything, it runs two uniqueness checks — one for the requested username and one for the requested email — and raises an HTTP 400 error immediately if either is already in use [[target/app/api/routes/authentication.py::register]]. If both checks pass, it calls `users_repo.create_user` to persist the record, then generates a JWT in exactly the same way `login` does, returning an identical `UserInResponse` / `UserWithToken` structure so that a successful registration delivers a ready-to-use token in the same shape as a successful login [[target/app/api/routes/authentication.py::register]].

The two handlers share a common output contract: both return `UserInResponse` wrapping `UserWithToken`, both generate the JWT through `jwt.create_access_token_for_user` with the secret sourced from `AppSettings`, and both depend on the same `UsersRepository` and `get_repository` injection pattern — making the module a self-contained boundary for all authentication concerns [[target/app/api/routes/authentication.py::login]] [[target/app/api/routes/authentication.py::register]].

## login

The `login` function is an asynchronous route handler registered on `POST /api/users/login` via the `@router.post("/login", response_model=UserInResponse, name="auth:login")` decorator [[target/app/api/routes/authentication.py::login]] [[route:POST /api/users/login]]. It accepts three injected parameters: `user_login`, a `UserInLogin` value read from the request body under the `"user"` key; `users_repo`, a `UsersRepository` instance supplied by the `get_repository` dependency; and `settings`, an `AppSettings` instance supplied by `get_app_settings` [[target/app/api/routes/authentication.py::login]] [[target/app/api/dependencies/database.py::get_repository]] [[target/app/core/config.py::get_app_settings]].

The function begins by constructing an `HTTPException` with a 400 Bad Request status, which is reused for any failed login attempt so that callers cannot distinguish between a missing account and a wrong password [[target/app/api/routes/authentication.py::login]]. It then attempts to fetch the user record from the database by calling `users_repo.get_user_by_email` with the email supplied in the request body; if no matching record exists, an `EntityDoesNotExist` exception is caught and the generic `wrong_login_error` is raised in its place [[target/app/api/routes/authentication.py::login]]. If a record is found, `user.check_password` is called with the submitted password, and the same `wrong_login_error` is raised if the check fails [[target/app/api/routes/authentication.py::login]].

On success, a JWT is minted by calling `jwt.create_access_token_for_user`, passing the user object and the application secret key retrieved via `settings.secret_key.get_secret_value()` [[target/app/api/routes/authentication.py::login]] [[target/app/core/config.py::get_app_settings]]. The function returns a `UserInResponse` wrapping a `UserWithToken` that carries the user's username, email, bio, image, and the newly created token [[target/app/api/routes/authentication.py::login]].

> **Raises:** wrong_login_error

> **FastAPI deps:** get_repository, get_app_settings

## register

`register` is an async function that handles new user registration, bound to the `POST /api/users` route with a 201 Created status code and a `UserInResponse` response model [[target/app/api/routes/authentication.py::register]] [[route:POST /api/users]].

It accepts three injected parameters: `user_create`, a `UserInCreate` object extracted from the request body under the key `"user"`; `users_repo`, a `UsersRepository` instance provided by the `get_repository` dependency; and `settings`, an `AppSettings` instance provided by `get_app_settings` [[target/app/api/routes/authentication.py::register]] [[target/app/api/dependencies/database.py::get_repository]] [[target/app/core/config.py::get_app_settings]].

Before creating any record, the function performs two uniqueness checks: it raises an `HTTPException` with HTTP 400 if the requested username is already taken, and raises a second `HTTPException` with HTTP 400 if the requested email address is already in use [[target/app/api/routes/authentication.py::register]].

If both checks pass, it persists the new user by calling `users_repo.create_user` with the fields unpacked from `user_create`, then generates a JWT access token by calling `jwt.create_access_token_for_user` using the newly created user and the application's secret key retrieved via `settings.secret_key.get_secret_value()` [[target/app/api/routes/authentication.py::register]] [[target/app/core/config.py::get_app_settings]].

Finally, it returns a `UserInResponse` wrapping a `UserWithToken` that carries the user's `username`, `email`, `bio`, `image`, and the freshly minted `token` [[target/app/api/routes/authentication.py::register]] [[route:POST /api/users]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_repository, get_app_settings

