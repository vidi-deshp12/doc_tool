# profiles

This module defines the FastAPI router for user profile operations, registering three route handlers under the profiles API [[target/app/api/routes/profiles.py]].

The `retrieve_profile_by_username` function handles `GET /api/profiles/{username}` requests, resolving the target profile via the `get_profile_by_username_from_path` dependency and wrapping the result in a `ProfileInResponse` envelope before returning it [[target/app/api/routes/profiles.py::retrieve_profile_by_username]].

The `follow_for_user` function handles `POST /api/profiles/{username}/follow`, allowing an authenticated user to follow another profile [[target/app/api/routes/profiles.py::follow_for_user]]. It shares the same three dependencies as the other write operations — the path-resolved profile via `get_profile_by_username_from_path`, the acting user via `get_current_user_authorizer`, and a `ProfilesRepository` via `get_repository` — a pattern repeated across both mutation handlers [[target/app/api/routes/profiles.py::follow_for_user]]. Before recording the follow, it guards against two invalid states: the authenticated user attempting to follow themselves, and the profile already being followed, raising `HTTPException` with `HTTP_400_BAD_REQUEST` in either case [[target/app/api/routes/profiles.py::follow_for_user]]. On success it calls `profiles_repo.add_user_into_followers` and returns a `ProfileInResponse` with `following` set to `True` [[target/app/api/routes/profiles.py::follow_for_user]].

The `unsubscribe_from_user` function mirrors this structure for `DELETE /api/profiles/{username}/follow`, applying the same self-action and precondition guards — raising `HTTP_400_BAD_REQUEST` when the user tries to unfollow themselves or is not currently following the target [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. On success it calls `profiles_repo.remove_user_from_followers` and returns a `ProfileInResponse` with `following` set to `False` [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

## follow_for_user

Handles `POST /api/profiles/{username}/follow` to let an authenticated user follow another profile [[route:POST /api/profiles/{username}/follow]] [[target/app/api/routes/profiles.py::follow_for_user]]. The target profile is resolved from the URL path parameter via `get_profile_by_username_from_path` [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]], the acting user is authenticated via `get_current_user_authorizer` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]], and a `ProfilesRepository` is injected via `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. It raises `HTTPException` with `HTTP_400_BAD_REQUEST` if the authenticated user attempts to follow themselves [[target/app/api/routes/profiles.py::follow_for_user]]. It also raises `HTTPException` with `HTTP_400_BAD_REQUEST` if the profile is already followed by the requesting user [[target/app/api/routes/profiles.py::follow_for_user]]. On success, it calls `profiles_repo.add_user_into_followers` to record the follow relationship [[target/app/api/routes/profiles.py::follow_for_user]], then returns a `ProfileInResponse` wrapping a copy of the profile with `following` set to `True` [[target/app/models/schemas/profiles.py::ProfileInResponse]] [[target/app/api/routes/profiles.py::follow_for_user]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository, get_profile_by_username_from_path

## retrieve_profile_by_username

Handles `GET /api/profiles/{username}` requests, resolving the target profile via the `get_profile_by_username_from_path` dependency injected through FastAPI's `Depends` mechanism [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]. It wraps the resolved `Profile` object in a `ProfileInResponse` envelope and returns it [[target/app/models/schemas/profiles.py::ProfileInResponse]] [[target/app/api/routes/profiles.py::retrieve_profile_by_username]].

> **FastAPI deps:** get_profile_by_username_from_path

## unsubscribe_from_user

Handles the `DELETE /api/profiles/{username}/follow` route to unfollow a user [[route:DELETE /api/profiles/{username}/follow]] [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. The target profile is resolved from the URL path parameter via `get_profile_by_username_from_path`, the authenticated caller is supplied by `get_current_user_authorizer`, and a `ProfilesRepository` instance is injected via `get_repository` [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]] [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]] [[target/app/api/dependencies/database.py::get_repository]]. It raises `HTTPException` with `HTTP_400_BAD_REQUEST` when the authenticated user attempts to unfollow themselves [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. It also raises `HTTPException` with `HTTP_400_BAD_REQUEST` when the authenticated user is not currently following the target profile [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. On success, it calls `profiles_repo.remove_user_from_followers` to persist the unfollow, then returns a `ProfileInResponse` containing a copy of the profile with `following` set to `False` [[target/app/models/schemas/profiles.py::ProfileInResponse]] [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository, get_profile_by_username_from_path

