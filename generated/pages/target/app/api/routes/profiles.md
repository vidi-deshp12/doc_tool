# profiles

This module is the FastAPI router responsible for all user-profile endpoints, defining three route handlers that together cover reading a profile, following a user, and unfollowing a user [[target/app/api/routes/profiles.py]].

The simplest of the three is [`retrieve_profile_by_username()`](target/app/api/routes/profiles.py::retrieve_profile_by_username), which handles `GET /{username}` and exists purely to wrap a resolved profile in a response envelope [[target/app/api/routes/profiles.py::retrieve_profile_by_username]]. All the real work — extracting the username from the URL and fetching the corresponding `Profile` object — is delegated to the `get_profile_by_username_from_path` dependency before the handler body even runs, leaving the function body as a single `return ProfileInResponse(profile=profile)` statement [[target/app/api/routes/profiles.py::retrieve_profile_by_username]].

The other two handlers, [`follow_for_user()`](target/app/api/routes/profiles.py::follow_for_user) and [`unsubscribe_from_user()`](target/app/api/routes/profiles.py::unsubscribe_from_user), are mirror images of each other and both require authentication [[target/app/api/routes/profiles.py::follow_for_user]] [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. Each receives three injected dependencies — the target `Profile` from the path, the authenticated `User`, and a `ProfilesRepository` for database access — and each applies the same pair of guard checks before touching the database [[target/app/api/routes/profiles.py::follow_for_user]] [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. The first guard blocks a user from following or unfollowing themselves by comparing usernames and raising an `HTTPException` with HTTP 400 if they match [[target/app/api/routes/profiles.py::follow_for_user]] [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. The second guard prevents redundant operations: `follow_for_user` rejects the request when `profile.following` is already `True`, and `unsubscribe_from_user` rejects it when `profile.following` is `False`, both with HTTP 400 [[target/app/api/routes/profiles.py::follow_for_user]] [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

When the guards pass, `follow_for_user` calls `profiles_repo.add_user_into_followers` to persist the relationship and returns a `ProfileInResponse` with `following` overridden to `True` [[target/app/api/routes/profiles.py::follow_for_user]], while `unsubscribe_from_user` calls `profiles_repo.remove_user_from_followers` and returns the same envelope with `following` overridden to `False` [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. In both cases the returned profile is a copy of the resolved object with only the `following` field patched, so the response always reflects the state after the operation [[target/app/api/routes/profiles.py::follow_for_user]] [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

## follow_for_user

`follow_for_user` is an asynchronous route handler registered on `POST /api/profiles/{username}/follow` that allows an authenticated user to follow another user's profile [[target/app/api/routes/profiles.py::follow_for_user]] [[route:POST /api/profiles/{username}/follow]].

It accepts three injected parameters: `profile`, a `Profile` object resolved from the URL path by `get_profile_by_username_from_path` [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]; `user`, the currently authenticated `User` supplied by `get_current_user_authorizer` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]; and `profiles_repo`, a `ProfilesRepository` instance provided by `get_repository` [[target/app/api/dependencies/database.py::get_repository]].

Before performing the follow operation, the handler applies two guard checks [[target/app/api/routes/profiles.py::follow_for_user]]. First, if the authenticated user's username matches the target profile's username, it raises an `HTTPException` with HTTP 400, preventing a user from following themselves [[target/app/api/routes/profiles.py::follow_for_user]]. Second, if the target profile is already marked as followed (`profile.following` is truthy), it raises another `HTTPException` with HTTP 400, preventing a duplicate follow relationship [[target/app/api/routes/profiles.py::follow_for_user]].

When both checks pass, the handler calls `profiles_repo.add_user_into_followers` with `target_user=profile` and `requested_user=user` to persist the new follow relationship in the database [[target/app/api/routes/profiles.py::follow_for_user]]. It then returns a `ProfileInResponse` constructed from a copy of the profile with `following` overridden to `True`, reflecting the newly established follow state in the response [[target/app/api/routes/profiles.py::follow_for_user]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository, get_profile_by_username_from_path

## retrieve_profile_by_username

`retrieve_profile_by_username` is an asynchronous route handler registered on `GET /{username}` that returns a single user profile wrapped in a response envelope [[route:GET /api/profiles/{username}]] [[target/app/api/routes/profiles.py::retrieve_profile_by_username]]. It is decorated with `router.get("/{username}", response_model=ProfileInResponse, name="profiles:get-profile")`, which binds it to the router under the name `profiles:get-profile` and declares `ProfileInResponse` as the serialisation schema for the outgoing JSON [[target/app/api/routes/profiles.py::retrieve_profile_by_username]].

The function accepts a single parameter, `profile`, which is not supplied by the caller directly but is resolved through FastAPI's dependency injection system via `Depends(get_profile_by_username_from_path)` [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]] [[target/app/api/routes/profiles.py::retrieve_profile_by_username]]. All the work of extracting the `username` path segment and looking up the corresponding `Profile` object is therefore delegated entirely to `get_profile_by_username_from_path` before the handler body runs [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]].

The function body is a single statement: it constructs and returns a `ProfileInResponse` instance whose `profile` field is set to the resolved `Profile` object [[target/app/api/routes/profiles.py::retrieve_profile_by_username]]. No additional transformation, validation, or error-raising logic lives inside the handler itself; any exceptions related to a missing or invalid username would be raised upstream by the dependency [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]].

> **FastAPI deps:** get_profile_by_username_from_path

## unsubscribe_from_user

The `unsubscribe_from_user` function is an asynchronous route handler registered on `DELETE /{username}/follow` that allows an authenticated user to unfollow another user's profile [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. It is decorated with `router.delete` using the route name `profiles:unsubscribe-from-user` and a response model of `ProfileInResponse` [[route:DELETE /api/profiles/{username}/follow]].

The function accepts three dependency-injected parameters: `profile`, a `Profile` object resolved from the URL path [[target/app/api/dependencies/profiles.py::get_profile_by_username_from_path]]; `user`, the currently authenticated `User` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]; and `profiles_repo`, a `ProfilesRepository` instance used to execute database operations [[target/app/api/dependencies/database.py::get_repository]].

Before performing any unfollow action, the handler applies two guard checks [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. First, it raises an `HTTPException` with status 400 if the authenticated user attempts to unfollow themselves — that is, when `user.username` matches `profile.username` [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. Second, it raises a second `HTTPException` with status 400 if the current user is not already following the target profile, indicated by `profile.following` being falsy [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

When both guards pass, it calls `profiles_repo.remove_user_from_followers` with the target profile and the requesting user to persist the unfollow [[target/app/api/routes/profiles.py::unsubscribe_from_user]]. The function then returns a `ProfileInResponse` wrapping a copy of the profile with `following` set to `False`, reflecting the updated relationship state [[target/app/api/routes/profiles.py::unsubscribe_from_user]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository, get_profile_by_username_from_path

