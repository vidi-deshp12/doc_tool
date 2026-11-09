# comments

[`target/app/api/routes/comments.py`](target/app/api/routes/comments.py) defines the FastAPI router responsible for all comment-related HTTP endpoints, mounting three route handlers that together cover the full create/read/delete lifecycle for article comments [[target/app/api/routes/comments.py]].

The first handler, [`create_comment_for_article`](target/app/api/routes/comments.py::create_comment_for_article), serves `POST /api/articles/{slug}/comments` and is the only route that requires an authenticated user; it reads the comment body from the request as a `CommentInCreate` payload, resolves the target article from the URL slug, persists the new comment via `CommentsRepository`, and returns the result wrapped in a `CommentInResponse` with HTTP 201 [[target/app/api/routes/comments.py::create_comment_for_article]].

The second handler, [`list_comments_for_article`](target/app/api/routes/comments.py::list_comments_for_article), serves `GET /api/articles/{slug}/comments` and relaxes the authentication requirement — a caller may be authenticated or anonymous — resolving the article from the slug and delegating retrieval to `CommentsRepository`, then returning all comments wrapped in a `ListOfCommentsInResponse` [[target/app/api/routes/comments.py::list_comments_for_article]].

The third handler, [`delete_comment_from_article`](target/app/api/routes/comments.py::delete_comment_from_article), serves `DELETE /api/articles/{slug}/comments/{comment_id}` and enforces `check_comment_modification_permissions` as a dependency before the handler body runs, ensuring only authorised callers can proceed; it resolves the target comment from the path, delegates deletion to `CommentsRepository`, and responds with HTTP 204 No Content [[target/app/api/routes/comments.py::delete_comment_from_article]].

All three handlers share a common pattern: the article or comment is resolved from path parameters by dedicated dependency functions, a `CommentsRepository` instance is injected via `get_repository`, and the actual database work is fully delegated to that repository, keeping the route handlers thin [[target/app/api/routes/comments.py]].

## create_comment_for_article

Handles `POST /api/articles/{slug}/comments`, creating a new comment and returning it wrapped in a `CommentInResponse` [[route:POST /api/articles/{slug}/comments]] [[target/app/api/routes/comments.py::create_comment_for_article]]. The comment body is read from the request as a `CommentInCreate` instance embedded under the key `"comment"` [[target/app/models/schemas/comments.py::CommentInCreate]]. The target article is resolved from the URL slug via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]], and the authenticated user is injected by `get_current_user_authorizer` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. A `CommentsRepository` instance is provided through `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. It delegates persistence to `comments_repo.create_comment_for_article`, passing the comment body, article, and user, then wraps the result in a `CommentInResponse` and returns it with HTTP 201 [[target/app/api/routes/comments.py::create_comment_for_article]] [[target/app/models/schemas/comments.py::CommentInResponse]].

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

## delete_comment_from_article

Handles `DELETE /api/articles/{slug}/comments/{comment_id}` and returns HTTP 204 No Content on success [[route:DELETE /api/articles/{slug}/comments/{comment_id}]] [[target/app/api/routes/comments.py::delete_comment_from_article]]. The target comment is resolved from the path via `get_comment_by_id_from_path`, and a `CommentsRepository` instance is injected via `get_repository` [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]] [[target/app/api/dependencies/database.py::get_repository]]. Before the handler body runs, `check_comment_modification_permissions` is enforced as a FastAPI dependency, guarding the route against unauthorised callers [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. The sole side effect is an awaited call to `comments_repo.delete_comment`, passing the resolved comment, which performs the actual deletion [[target/app/api/routes/comments.py::delete_comment_from_article]].

> **FastAPI deps:** check_comment_modification_permissions, get_comment_by_id_from_path, get_repository

## list_comments_for_article

Handles `GET /api/articles/{slug}/comments`, returning all comments for a given article wrapped in a [`ListOfCommentsInResponse`](target/app/models/schemas/comments.py::ListOfCommentsInResponse) [[route:GET /api/articles/{slug}/comments]] [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. The article is resolved from the URL slug via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]], and an optional authenticated user is resolved via `get_current_user_authorizer(required=False)`, meaning authentication is accepted but not enforced [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. A `CommentsRepository` is injected through `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. It awaits `comments_repo.get_comments_for_article` with the resolved article and optional user, then constructs and returns a [`ListOfCommentsInResponse`](target/app/models/schemas/comments.py::ListOfCommentsInResponse) from the result [[target/app/api/routes/comments.py::list_comments_for_article]] [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]].

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

