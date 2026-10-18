# users

This module defines the API routes responsible for reading and updating the currently authenticated user's profile [[target/app/api/routes/users.py]]. It creates a single `APIRouter` instance and registers two route handlers on it, both of which require an authenticated caller and both of which return the user's data together with a freshly minted JWT access token [[target/app/api/routes/users.py]].

The first handler, `retrieve_current_user`, is registered on `GET ""` under the name `"users:get-current-user"` and declares `UserInResponse` as its response model [[target/app/api/routes/users.py::retrieve_current_user]]. It receives the authenticated `User` object via `get_current_user_authorizer()` and the application configuration via `get_app_settings`, then calls `jwt.create_access_token_for_user` with the user and the unwrapped secret key to produce a token [[target/app/api/routes/users.py::retrieve_current_user]]. It wraps the result in a `UserInResponse` containing a `UserWithToken` carrying the user's `username`, `email`, `bio`, `image`, and the new token, and returns it without raising any exceptions of its own [[target/app/api/routes/users.py::retrieve_current_user]].

The second handler, `update_current_user`, is registered on `PUT ""` under the name `"users:update-current-user"` and shares the same `UserInResponse` response model [[target/app/api/routes/users.py::update_current_user]]. It accepts four injected dependencies: the update payload embedded in the request body under the key `"user"`, the resolved `current_user` from `get_current_user_authorizer`, a `UsersRepository` instance from `get_repository`, and application settings from `get_app_settings` [[target/app/api/routes/users.py::update_current_user]]. Before writing anything, it performs two uniqueness guards: if the requested username differs from the current one and is already taken, it raises an `HTTPException` with a 400 status code, and the same check is applied to the email field [[target/app/api/routes/users.py::update_current_user]]. Once both guards pass, it delegates the database write to `users_repo.update_user`, mints a fresh token for the updated user, and returns a `UserInResponse` wrapping a `UserWithToken` with the updated profile fields and the new token [[target/app/api/routes/users.py::update_current_user]].

The two handlers are closely parallel in structure: both authenticate the caller through the same dependency, both sign a new token using the same secret-key retrieval pattern, and both produce an identical response shape, with `update_current_user` adding the uniqueness validation and persistence steps on top of what `retrieve_current_user` already does [[target/app/api/routes/users.py::retrieve_current_user]] [[target/app/api/routes/users.py::update_current_user]].

## retrieve_current_user

`retrieve_current_user` is an async route handler registered on the router as a GET request that returns the currently authenticated user along with a fresh JWT access token [[target/app/api/routes/users.py::retrieve_current_user]] [[route:GET /api/user]].

It accepts two injected dependencies: `user`, a `User` instance resolved by `get_current_user_authorizer()`, and `settings`, an `AppSettings` instance resolved by `get_app_settings` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]] [[target/app/core/config.py::get_app_settings]]. The decorator registers this handler under the name `"users:get-current-user"` and declares `UserInResponse` as the response model, so FastAPI will validate and serialize the return value accordingly [[target/app/api/routes/users.py::retrieve_current_user]].

Inside the function, a new access token is minted by calling `jwt.create_access_token_for_user`, passing the authenticated `user` object and the application secret key retrieved via `settings.secret_key.get_secret_value()` [[target/app/api/routes/users.py::retrieve_current_user]]. The secret value is explicitly coerced to a plain `str` before being passed, which is the standard way to unwrap a Pydantic `SecretStr` [[target/app/api/routes/users.py::retrieve_current_user]].

The function then constructs and returns a `UserInResponse` wrapping a `UserWithToken` that carries the user's `username`, `email`, `bio`, `image`, and the freshly generated `token` [[target/app/api/routes/users.py::retrieve_current_user]]. No exceptions are explicitly raised within the function body itself; any authentication failure would be raised upstream inside `get_current_user_authorizer` before this handler is ever entered [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]].

> **FastAPI deps:** get_current_user_authorizer, get_app_settings

## update_current_user

`update_current_user` is an asynchronous route handler registered on `PUT /api/user` that allows the currently authenticated user to update their own profile [[route:PUT /api/user]] [[target/app/api/routes/users.py::update_current_user]].

It accepts four injected parameters [[target/app/api/routes/users.py::update_current_user]]. The `user_update` argument carries the fields the client wishes to change, embedded in the request body under the key `"user"` [[target/app/api/routes/users.py::update_current_user]]. The `current_user` argument is populated by FastAPI's dependency system using `get_current_user_authorizer`, which authenticates the caller and resolves them to a `User` object [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The `users_repo` argument is a `UsersRepository` instance provided by `get_repository`, giving access to user-related database operations [[target/app/api/dependencies/database.py::get_repository]]. Finally, `settings` supplies application-wide configuration, including the secret key used to sign tokens, and is resolved via `get_app_settings` [[target/app/core/config.py::get_app_settings]].

Before persisting any changes, the function performs two uniqueness checks [[target/app/api/routes/users.py::update_current_user]]. If the incoming update includes a new username that differs from the current one and that username is already taken, it raises an `HTTPException` with a 400 status code [[target/app/api/routes/users.py::update_current_user]]. The same guard applies to the email field: if a new email is supplied and it belongs to another account, a second `HTTPException` is raised with a 400 status code [[target/app/api/routes/users.py::update_current_user]].

Once both checks pass, the function delegates the actual database write to `users_repo.update_user`, passing the resolved `current_user` alongside all fields from the update payload [[target/app/api/routes/users.py::update_current_user]]. After saving, it mints a fresh JWT access token for the updated user, signing it with the application secret retrieved from `settings` [[target/app/core/config.py::get_app_settings]] [[target/app/api/routes/users.py::update_current_user]].

The function returns a `UserInResponse` object wrapping a `UserWithToken` that contains the user's updated `username`, `email`, `bio`, and `image` fields together with the newly issued token [[target/app/api/routes/users.py::update_current_user]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository, get_app_settings

