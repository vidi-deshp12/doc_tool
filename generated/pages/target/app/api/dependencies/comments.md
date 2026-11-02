# comments

This module provides two FastAPI dependency functions that together handle comment lookup and write-access control for comment-related routes [[target/app/api/dependencies/comments.py]].

`get_comment_by_id_from_path` is an async dependency that resolves a single comment from the request path, scoped to a specific article [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. It accepts a `comment_id` integer path parameter (constrained to be at least 1), an `Article` resolved from the path slug, an optionally authenticated `User`, and a `CommentsRepository` instance — all wired through FastAPI's `Depends` mechanism [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. The actual database lookup is delegated to `comments_repo.get_comment_by_id`, passing the resolved comment ID, article, and user [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. If the comment is not found, the repository raises `EntityDoesNotExist`, which this function catches and converts into an `HTTPException` with a `404 Not Found` status, preventing the route handler from receiving a missing comment [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

`check_comment_modification_permissions` is a synchronous dependency that enforces write-access control on a resolved comment [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. It depends directly on `get_comment_by_id_from_path` to obtain the target comment, and on `get_current_user_authorizer()` (with authentication required) to obtain the calling user [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. The permission decision is delegated to the `check_user_can_modify_comment` helper; if that helper returns a falsy value, this function immediately raises an `HTTPException` with `403 Forbidden`, halting the request before the route handler runs [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. On success it returns `None`, allowing the route to proceed [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

The two functions form a chain: `check_comment_modification_permissions` builds on `get_comment_by_id_from_path`, so any route that requires modification permissions automatically also gets comment resolution and 404 handling as part of the same dependency graph [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]] [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

## check_comment_modification_permissions

`check_comment_modification_permissions` is a FastAPI dependency function that enforces write-access control on a comment, returning `None` on success and raising an `HTTPException` with a `403 Forbidden` status if the requesting user is not permitted to modify the comment [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

It accepts two injected arguments: a `Comment` object resolved by `get_comment_by_id_from_path`, and a `User` object resolved by `get_current_user_authorizer()`, both wired through FastAPI's `Depends` mechanism [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]] [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The resolved comment is the one identified by the path parameter of the enclosing route, and the resolved user is the currently authenticated caller [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

The function delegates the actual permission check to `check_user_can_modify_comment(comment, user)`; if that helper returns a falsy value, `HTTPException` is raised immediately with `HTTP_403_FORBIDDEN` and a detail string drawn from the `strings` module, preventing the route handler from executing [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_comment_by_id_from_path

## get_comment_by_id_from_path

`get_comment_by_id_from_path` is an async FastAPI dependency function that retrieves a single comment by its ID, scoped to a specific article [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

It accepts four injected parameters: `comment_id`, an integer path parameter constrained to be at least 1; `article`, resolved by delegating to `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]; `user`, an optionally authenticated caller resolved via `get_current_user_authorizer(required=False)` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]; and `comments_repo`, a `CommentsRepository` instance provided through `get_repository` [[target/app/api/dependencies/database.py::get_repository]].

The function delegates the actual database lookup to `comments_repo.get_comment_by_id`, passing the resolved `comment_id`, `article`, and `user` [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. It returns a `Comment` on success [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. If the comment does not exist, the repository raises `EntityDoesNotExist`, which this function catches and converts into an HTTP 404 response by raising `fastapi.HTTPException` [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

