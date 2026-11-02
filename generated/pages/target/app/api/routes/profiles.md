# profiles

This module defines the FastAPI router for user profile operations, exposing three HTTP endpoints under the `/api/profiles/` prefix [[target/app/api/routes/profiles.py]]. A single `APIRouter` instance groups all three handlers, which together cover reading a profile, following a user, and unfollowing a user [[target/app/api/routes/profiles.py]].

The `retrieve_profile_by_username` handler responds to `GET /{username}` and is the simplest of the three: it accepts a `Profile` object already resolved from the URL path segment by the `get_profile_by_username_from_path` dependency, wraps it in a `ProfileInResponse` envelope, and returns it immediately without any additional logic [[target/app/api/routes/profiles.py::retrieve_profile_by_username]]. Any failure due to an unknown username surfaces from that dependency before the handler body is ever reached [[target/app/api/routes/profiles.py::retrieve_profile_by_username]].

The `follow_for_user` handler responds to `POST /{username}/follow` and requires an authenticated caller [[target/app/api/routes/profiles.py::follow_for_user]]. In addition to the resolved `Profile`, it injects the current `User` and a `ProfilesRepository` for database access [[target/app/api/routes/profiles.py::follow_for_user]]. It enforces two guard conditions before writing anything: it rejects the request with HTTP 400 if the caller and target share the same username, and it rejects it again with HTTP 400 if the profile is already being followed [[target/app/api/routes/profiles.py::follow_for_user]]. When both guards pass, it calls `profiles_repo.add_user_into_followers` to persist the relationship, then returns a `ProfileInResponse` carrying a copy of the profile with `following` forced to `True` [[target/app/api/routes/profiles.py::follow_for_user]].

The `unsubscribe_from_user` handler is the mirror of `follow_for_user`, responding to `DELETE /{username}/follow` [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. It injects the same three dependencies and applies the same self-referential guard, but its second guard checks the opposite condition — it raises HTTP 400 if the caller is *not* currently following the target [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. If both guards pass, it calls `profiles_repo.remove_user_from_followers` to persist the unfollow, then returns a `ProfileInResponse` with `following` explicitly set to `False` [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

All three handlers share the same response shape — `ProfileInResponse` — which FastAPI also uses to generate the OpenAPI schema for each route [[target/app/api/routes/profiles.py]].

## follow_for_user

`follow_for_user` is an async POST endpoint registered at `/api/profiles/{username}/follow` that allows an authenticated user to follow another user's profile [[target/app/api/routes/profiles.py::follow_for_user]] [[route:POST /api/profiles/{username}/follow]].

The function accepts three injected parameters: a `Profile` object resolved from the URL path, a `User` object representing the currently authenticated caller, and a `ProfilesRepository` instance for database access [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]] [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]] [[target/app/api/dependencies/database.py::get_repository]].

Before performing any write, the function enforces two guard conditions: it raises an `HTTPException` with HTTP 400 if the authenticated user attempts to follow themselves (comparing `user.username` against `profile.username`), and it raises a second `HTTPException` with HTTP 400 if the profile is already being followed (checked via `profile.following`) [[target/app/api/routes/profiles.py::follow_for_user]].

When both guards pass, the function calls `profiles_repo.add_user_into_followers` with the target profile and the requesting user to persist the follow relationship [[target/app/api/routes/profiles.py::follow_for_user]].

It then returns a `ProfileInResponse` wrapping a copy of the profile with `following` forced to `True`, reflecting the newly established relationship [[target/app/models/schemas/profiles.py::ProfileInResponse]] [[target/app/api/routes/profiles.py::follow_for_user]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository, get_profile_by_username_from_path

## retrieve_profile_by_username

`retrieve_profile_by_username` is an async route handler registered on `GET /{username}` (mounted under `/api/profiles/`) that returns a single user profile [[target/app/api/routes/profiles.py::retrieve_profile_by_username]] [[route:GET /api/profiles/{username}]]. It accepts one parameter, `profile`, which is injected by FastAPI's dependency system via `get_profile_by_username_from_path` — that dependency is responsible for resolving the `{username}` path segment into a `Profile` object before the handler is called [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]. The handler itself does no additional logic: it wraps the resolved `Profile` in a `ProfileInResponse` envelope and returns it directly [[target/app/api/routes/profiles.py::retrieve_profile_by_username]] [[target/app/models/schemas/profiles.py::ProfileInResponse]]. The decorator declares `ProfileInResponse` as the response model, so FastAPI uses that schema for both serialization and the generated OpenAPI spec [[target/app/models/schemas/profiles.py::ProfileInResponse]] [[target/app/api/routes/profiles.py]]. No exceptions are raised inside the function body itself; any failure (for example an unknown username) would surface from the dependency before this handler is reached [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]].

> **FastAPI deps:** get_profile_by_username_from_path

## unsubscribe_from_user

`unsubscribe_from_user` is an asynchronous route handler registered on `DELETE /api/profiles/{username}/follow` that allows an authenticated user to stop following another user's profile [[target/app/api/routes/profiles.py::unsubscribe_from_user]] [[route:DELETE /api/profiles/{username}/follow]].

It accepts three FastAPI-injected parameters: the target `Profile` resolved from the URL path, the currently authenticated `User`, and a `ProfilesRepository` instance for database access [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]] [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]] [[target/app/api/dependencies/database.py::get_repository]].

Before performing any action, the function runs two guard checks: it raises an `HTTPException` with HTTP 400 if the authenticated user is attempting to unsubscribe from themselves, and it raises a second `HTTPException` with HTTP 400 if the current user is not already following the target profile [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

If both guards pass, it calls `profiles_repo.remove_user_from_followers` to persist the unfollow action in the database [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

It returns a `ProfileInResponse` wrapping a copy of the resolved profile with its `following` field explicitly set to `False`, reflecting the updated relationship state [[target/app/models/schemas/profiles.py::ProfileInResponse]] [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository, get_profile_by_username_from_path

