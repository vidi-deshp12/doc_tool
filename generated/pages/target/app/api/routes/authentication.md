# authentication

This module is the authentication route handler for the API, defining the `APIRouter` instance and the two endpoints responsible for user registration and login [[target/app/api/routes/authentication.py]].

The `register` function handles `POST /api/users` requests, accepting new user details as a `UserInCreate` payload embedded under the `"user"` key [[target/app/api/routes/authentication.py::register]]. Before persisting anything, it validates uniqueness by checking whether the requested username is already taken and raising an `HTTP 400` error if so, then repeating the same check for the email address [[target/app/api/routes/authentication.py::register]]. Once both checks pass, it creates the user record via the injected `UsersRepository`, mints a JWT using `jwt.create_access_token_for_user` with the application secret retrieved from the injected `AppSettings`, and returns a `UserInResponse` wrapping a `UserWithToken` containing the user's username, email, bio, image, and the new token [[target/app/api/routes/authentication.py::register]].

The `login` function handles `POST /api/users/login`, accepting credentials embedded under the `"user"` key [[target/app/api/routes/authentication.py::login]]. It looks up the account by email through the injected `UsersRepository`; if no matching account exists, it raises an `HTTP 400` error, and raises the same error if the supplied password fails the `check_password` verification [[target/app/api/routes/authentication.py::login]]. On success it mints a JWT via `jwt.create_access_token_for_user` using the secret from `settings.secret_key.get_secret_value()`, and returns a `UserInResponse` wrapping a `UserWithToken` with the user's credentials and the freshly issued token [[target/app/api/routes/authentication.py::login]].

The two endpoints share the same structural pattern: both depend on a `UsersRepository` injected via `get_repository`, both retrieve application configuration through `get_app_settings`, and both produce a `UserInResponse` as their successful response [[target/app/api/routes/authentication.py::register]] [[target/app/api/routes/authentication.py::login]].

## login

Handles `POST /api/users/login` requests, accepting login credentials embedded in the request body under the `user` key [[target/app/api/routes/authentication.py::login]] [[target/app/models/schemas/users.py::UserInLogin]]. It fetches the matching account by email via `users_repo.get_user_by_email`; if no account exists, it raises an `HTTP 400` error [[target/app/api/routes/authentication.py::login]] [[target/app/api/dependencies/database.py::get_repository]]. If the account is found but `user.check_password` returns false for the supplied password, the same `HTTP 400` error is raised [[target/app/api/routes/authentication.py::login]]. On success it mints a JWT via `jwt.create_access_token_for_user`, using the secret retrieved from `settings.secret_key.get_secret_value()` [[target/app/api/routes/authentication.py::login]] [[target/app/core/config.py::get_app_settings]]. It returns a `UserInResponse` wrapping a `UserWithToken` that carries the user's username, email, bio, image, and the newly created token [[target/app/api/routes/authentication.py::login]] [[target/app/models/schemas/users.py::UserInResponse]].

> **Raises:** wrong_login_error

> **FastAPI deps:** get_repository, get_app_settings

## register

Handles `POST /api/users` and returns a newly created user with a JWT access token [[route:POST /api/users]] [[target/app/api/routes/authentication.py::register]]. Accepts the new user's details as a `UserInCreate` body (embedded under the `"user"` key) [[target/app/models/schemas/users.py::UserInCreate]]. Before creating the user, it checks whether the requested username is already taken and raises `HTTPException` with HTTP 400 if so [[target/app/api/routes/authentication.py::register]]; it then performs the same uniqueness check for the email address and raises a second `HTTPException` with HTTP 400 if that is taken [[target/app/api/routes/authentication.py::register]]. Once both checks pass it persists the new user via `users_repo.create_user`, which is injected through `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. It then mints a JWT by calling `jwt.create_access_token_for_user` with the created user and the application secret, which is retrieved from injected `AppSettings` via `settings.secret_key.get_secret_value()` [[target/app/core/config.py::get_app_settings]]. The response is a `UserInResponse` wrapping a `UserWithToken` that carries the username, email, bio, image, and the newly issued token [[target/app/models/schemas/users.py::UserInResponse]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_repository, get_app_settings

