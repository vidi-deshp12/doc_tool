# comments

This module provides two FastAPI dependency functions that together handle comment lookup and write-access control for the comments subsystem of the API [[target/app/api/dependencies/comments.py]].

`get_comment_by_id_from_path` is an async dependency that resolves a single comment from the current HTTP request [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. It extracts a numeric comment ID from the URL path (constrained to be at least 1), resolves the parent article via a delegated dependency, optionally identifies the requesting user (allowing unauthenticated callers by passing `required=False`), and obtains a `CommentsRepository` instance for data access — all through FastAPI's `Depends` mechanism [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. The actual database lookup is delegated to the repository's `get_comment_by_id` method; if the comment does not exist, the resulting `EntityDoesNotExist` exception is caught and re-raised as an `HTTPException` with HTTP 404, ensuring callers receive a well-formed error response rather than an unhandled exception [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

`check_comment_modification_permissions` builds directly on top of `get_comment_by_id_from_path` to enforce write-access control [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. It injects the resolved `Comment` via `get_comment_by_id_from_path` and a fully authenticated `User` via `get_current_user_authorizer()` (authentication is required here, unlike in the lookup dependency) [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. The body delegates the permission decision to `check_user_can_modify_comment`; if that helper returns a falsy value, the function raises an `HTTPException` with HTTP 403 and an author-mismatch detail message, immediately halting the request [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

The two functions are designed to compose: route handlers that need both a resolved comment object and a guarantee that the caller may modify it can declare `check_comment_modification_permissions` as their sole dependency, which in turn pulls in `get_comment_by_id_from_path` automatically [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]] [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

## check_comment_modification_permissions

`check_comment_modification_permissions` is a FastAPI dependency function that enforces write-access control on a comment, returning `None` on success and raising an `HTTP 403 Forbidden` exception if the requesting user is not authorised to modify it [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

It accepts two injected parameters: a `Comment` object resolved by `get_comment_by_id_from_path`, which looks up the target comment from the request path, and a `User` object resolved by `get_current_user_authorizer()`, which identifies and authenticates the caller [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]] [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. Both parameters are wired through FastAPI's `Depends` mechanism, so the framework resolves them automatically before the function body executes [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

The body delegates the actual permission check to `check_user_can_modify_comment`, passing the resolved comment and user [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. If that helper returns a falsy result, the function raises an `HTTPException` with status code `403` and an author-mismatch detail message, immediately halting the request [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_comment_by_id_from_path

## get_comment_by_id_from_path

`get_comment_by_id_from_path` is an async FastAPI dependency function that looks up a single comment by its numeric ID and returns it, raising a 404 if no matching comment is found [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

It accepts four injected parameters [[target/app/api/dependencies/comments.py]]. The `comment_id` is an integer extracted from the URL path, constrained to be greater than or equal to 1 via `Path(..., ge=1)` [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. The `article` parameter is resolved by delegating to `get_article_by_slug_from_path`, which fetches the article that the comment belongs to from the current request path [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. The `user` parameter is resolved by `get_current_user_authorizer` called with `required=False`, meaning the caller does not need to be authenticated — an anonymous request is permitted and `user` will be `None` in that case [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The `comments_repo` parameter is a `CommentsRepository` instance injected through `get_repository`, providing the data-access layer for comments [[target/app/api/dependencies/database.py::get_repository]].

The function delegates the actual database lookup to `comments_repo.get_comment_by_id`, passing the resolved `comment_id`, `article`, and `user` [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. If the comment does not exist, `EntityDoesNotExist` is caught and re-raised as an `HTTPException` with HTTP status 404, so the caller receives a well-formed error response rather than an unhandled exception [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

