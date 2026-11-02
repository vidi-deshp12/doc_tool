# users

This module defines the FastAPI router for the authenticated user resource, exposing two endpoints that allow a logged-in user to retrieve and update their own profile [[target/app/api/routes/users.py]].

The `retrieve_current_user` handler is registered on `GET ""` (resolved to `GET /api/user` by the application's route prefix) and returns the current user's profile together with a freshly minted JWT access token [[target/app/api/routes/users.py::retrieve_current_user]]. It depends on `get_current_user_authorizer()` to resolve the authenticated `User` and on `get_app_settings` to obtain the secret key used when calling `jwt.create_access_token_for_user`, then wraps the result in a `UserInResponse` containing a `UserWithToken` [[target/app/api/routes/users.py::retrieve_current_user]].

The `update_current_user` handler is registered on `PUT ""` (resolved to `PUT /api/user`) and performs a guarded profile update before returning the same kind of response [[target/app/api/routes/users.py::update_current_user]]. It accepts a `UserInUpdate` request body (embedded under the JSON key `"user"`), the authenticated `User`, a `UsersRepository` for database access, and application settings [[target/app/api/routes/users.py::update_current_user]]. Before touching the database, it runs two uniqueness checks: if the incoming username differs from the current one and is already taken, it raises an `HTTPException` with HTTP 400; it applies the same guard to the incoming email address [[target/app/api/routes/users.py::update_current_user]]. Only when both checks pass does it call `users_repo.update_user` to persist the changes, after which it mints a new token and returns a `UserInResponse` wrapping the updated `UserWithToken` [[target/app/api/routes/users.py::update_current_user]].

The two handlers share a common response shape — `UserInResponse` containing `UserWithToken` — and both issue a fresh JWT on every successful request, ensuring the token in the response always reflects the current state of the user record [[target/app/api/routes/users.py::retrieve_current_user]] [[target/app/api/routes/users.py::update_current_user]].

## retrieve_current_user

`retrieve_current_user` is an async FastAPI route handler that serves the `GET /api/user` endpoint [[route:GET /api/user]] [[target/app/api/routes/users.py::retrieve_current_user]]. It is registered on the router via the `@router.get("", response_model=UserInResponse, name="users:get-current-user")` decorator, which declares `UserInResponse` as the serialisation model for the response [[target/app/api/routes/users.py::retrieve_current_user]].

The function accepts two injected dependencies: an authenticated `User` object resolved by `get_current_user_authorizer()` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]], and an `AppSettings` instance resolved by `get_app_settings` [[target/app/core/config.py::get_app_settings]]. Both are wired through FastAPI's `Depends` mechanism [[target/app/api/routes/users.py::retrieve_current_user]].

Once the authenticated user is available, the function generates a fresh JWT access token by calling `jwt.create_access_token_for_user`, passing the user object and the application secret key retrieved from `settings.secret_key.get_secret_value()` [[target/app/api/routes/users.py::retrieve_current_user]]. It then constructs and returns a `UserInResponse` wrapping a `UserWithToken` that bundles the user's `username`, `email`, `bio`, `image`, and the newly issued token [[target/app/models/schemas/users.py::UserInResponse]] [[target/app/api/routes/users.py::retrieve_current_user]]. No exceptions are explicitly raised within the function body itself [[target/app/api/routes/users.py::retrieve_current_user]].

> **FastAPI deps:** get_current_user_authorizer, get_app_settings

## update_current_user

`update_current_user` is an asynchronous route handler registered on `PUT /api/user` that updates the profile of the currently authenticated user and returns a fresh JWT alongside the updated profile data [[target/app/api/routes/users.py::update_current_user]] [[route:PUT /api/user]].

It is decorated with `router.put("", response_model=UserInResponse, name="users:update-current-user")`, which binds it to the PUT method and declares `UserInResponse` as the FastAPI response model [[target/app/api/routes/users.py::update_current_user]] [[target/app/models/schemas/users.py::UserInResponse]].

The function accepts four injected parameters [[target/app/api/routes/users.py::update_current_user]]. `user_update` is a `UserInUpdate` body embedded under the JSON key `"user"`, carrying the fields the caller wishes to change [[target/app/models/schemas/users.py::UserInUpdate]]. `current_user` is the already-authenticated `User` object resolved by `get_current_user_authorizer()` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. `users_repo` is a `UsersRepository` instance supplied by `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. `settings` provides application-level configuration, including the secret key used to sign tokens [[target/app/core/config.py::get_app_settings]].

Before performing any update, the function runs two uniqueness checks [[target/app/api/routes/users.py::update_current_user]]. If a new username is provided and differs from the current one, it calls `check_username_is_taken`; if that username is already in use, it raises an `HTTPException` with HTTP 400 and a "username taken" detail [[target/app/api/routes/users.py::update_current_user]]. Similarly, if a new email is provided and differs from the current one, it calls `check_email_is_taken`; if that email is already in use, it raises a second `HTTPException` with HTTP 400 and an "email taken" detail [[target/app/api/routes/users.py::update_current_user]].

If both checks pass, the function calls `users_repo.update_user`, passing the current user object and the flattened update fields, to persist the changes [[target/app/api/routes/users.py::update_current_user]]. It then calls `jwt.create_access_token_for_user` with the updated user and the application secret key (retrieved via `settings.secret_key.get_secret_value()`) to mint a new access token [[target/app/api/routes/users.py::update_current_user]] [[target/app/core/config.py::get_app_settings]].

Finally, the handler constructs and returns a `UserInResponse` wrapping a `UserWithToken` that bundles the user's updated `username`, `email`, `bio`, `image`, and the freshly issued `token` [[target/app/api/routes/users.py::update_current_user]] [[target/app/models/schemas/users.py::UserInResponse]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository, get_app_settings

