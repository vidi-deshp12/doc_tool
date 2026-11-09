# comments

This module provides FastAPI dependency functions for resolving and authorizing comment resources in the API layer [[target/app/api/dependencies/comments.py]].

The first dependency, [`get_comment_by_id_from_path`](target/app/api/dependencies/comments.py::get_comment_by_id_from_path), fetches a single comment by its integer path parameter `comment_id`, scoped to the article identified by the URL slug [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. It resolves the parent article and optionally identifies the requesting user (authentication is not required), then delegates the actual database lookup to `CommentsRepository` [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. If no matching comment exists, it catches `EntityDoesNotExist` and re-raises it as an `HTTPException` with a 404 status code [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

The second dependency, [`check_comment_modification_permissions`](target/app/api/dependencies/comments.py::check_comment_modification_permissions), builds directly on [`get_comment_by_id_from_path`](target/app/api/dependencies/comments.py::get_comment_by_id_from_path) by declaring it as a FastAPI dependency alongside the currently authenticated user [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. It passes both the resolved comment and the authenticated user to `check_user_can_modify_comment` to determine whether the operation is permitted [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. If that check fails, it raises an `HTTPException` with a 403 Forbidden status and a "user is not author" detail message, preventing unauthorized modifications [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

Together, the two functions form a layered authorization chain: the first handles resource resolution and existence checks, while the second enforces ownership rules on top of the resolved resource [[target/app/api/dependencies/comments.py]].

## check_comment_modification_permissions

Resolves a `Comment` via [`get_comment_by_id_from_path`](target/app/api/dependencies/comments.py::get_comment_by_id_from_path) and the currently authenticated `User` via [`get_current_user_authorizer`](target/app/api/dependencies/authentication.py::get_current_user_authorizer) as FastAPI dependencies [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. It calls `check_user_can_modify_comment` with those two values to determine whether the user has permission to modify the comment [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. If the check fails, it raises an `HTTPException` with a `403 Forbidden` status and a "user is not author" detail message [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_comment_by_id_from_path

## get_comment_by_id_from_path

Fetches a single comment by its integer path parameter `comment_id` (minimum value 1), scoped to the article resolved from the URL slug [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. It resolves the parent article via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]] and optionally identifies the requesting user through `get_current_user_authorizer(required=False)`, meaning authentication is not mandatory [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The `CommentsRepository` is injected via `get_repository` [[target/app/api/dependencies/database.py::get_repository]], and the actual database lookup is delegated to `comments_repo.get_comment_by_id` with all three resolved values passed as arguments [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. If the comment does not exist, `EntityDoesNotExist` is caught and re-raised as an `HTTPException` with a 404 status code [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

