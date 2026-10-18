# comments

[`target/app/api/routes/comments.py`](target/app/api/routes/comments.py) is the FastAPI router module responsible for all comment-related HTTP endpoints, grouping three route handlers that together cover listing, creating, and deleting comments on articles [[target/app/api/routes/comments.py]].

The module declares a shared `APIRouter` instance onto which all three handlers are registered, and it imports the domain models, request/response schemas, repository class, and dependency functions that each handler needs [[target/app/api/routes/comments.py]].

`list_comments_for_article` handles `GET` requests and returns every comment associated with a given article, serialised as a `ListOfCommentsInResponse` [[target/app/api/routes/comments.py::list_comments_for_article]]. It resolves the target article from the URL slug and accepts an optional authenticated user, so both anonymous and logged-in callers may retrieve comments [[target/app/api/routes/comments.py::list_comments_for_article]]. All data access is delegated to an injected `CommentsRepository` [[target/app/api/routes/comments.py::list_comments_for_article]].

`create_comment_for_article` handles `POST` requests and persists a new comment, responding with HTTP 201 and the saved comment wrapped in a `CommentInResponse` [[target/app/api/routes/comments.py::create_comment_for_article]]. Unlike the listing handler, it requires a fully authenticated user — the caller must be logged in before the function body executes [[target/app/api/routes/comments.py::create_comment_for_article]]. The comment text is received as a JSON body field aliased to `"comment"` and typed as `CommentInCreate`, and the handler passes it along with the resolved article and user to the repository's create method [[target/app/api/routes/comments.py::create_comment_for_article]].

`delete_comment_from_article` handles `DELETE /{comment_id}` requests and removes the identified comment, returning HTTP 204 No Content with an empty body [[target/app/api/routes/comments.py::delete_comment_from_article]]. It enforces ownership or authorisation through `check_comment_modification_permissions`, which is wired as a route-level dependency in the decorator so it runs before the handler body is reached [[target/app/api/routes/comments.py::delete_comment_from_article]]. The target `Comment` object is resolved from the path by a dedicated dependency, and the single line of business logic is an awaited call to `comments_repo.delete_comment` [[target/app/api/routes/comments.py::delete_comment_from_article]].

All three handlers share the same structural pattern: dependencies resolve the article, the user, and a `CommentsRepository` instance before the handler body runs, keeping each function body to one or two lines that delegate entirely to the repository layer [[target/app/api/routes/comments.py]].

## create_comment_for_article

`create_comment_for_article` is an asynchronous route handler registered on `POST /api/articles/{slug}/comments` that creates a new comment for a specific article and returns the saved comment wrapped in a response envelope [[target/app/api/routes/comments.py::create_comment_for_article]] [[route:POST /api/articles/{slug}/comments]].

It is decorated with `router.post`, configured to respond with HTTP 201 Created and to serialise its output as a `CommentInResponse` [[target/app/api/routes/comments.py::create_comment_for_article]].

The function accepts four injected parameters. The comment payload arrives as a JSON body field aliased to `"comment"` and typed as `CommentInCreate` [[target/app/api/routes/comments.py::create_comment_for_article]]. The target article is resolved from the URL path slug via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. The authenticated user is obtained through `get_current_user_authorizer()`, which enforces that the caller is logged in [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. A `CommentsRepository` instance is injected via `get_repository`, providing the data-access layer for comments [[target/app/api/dependencies/database.py::get_repository]].

In its body, the handler calls `comments_repo.create_comment_for_article` with the comment's text, the resolved article, and the current user, awaiting the persisted comment [[target/app/api/routes/comments.py::create_comment_for_article]]. It then wraps the result in a `CommentInResponse` and returns it, which FastAPI serialises as the HTTP 201 response [[target/app/api/routes/comments.py::create_comment_for_article]].

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

## delete_comment_from_article

`delete_comment_from_article` is an asynchronous route handler registered on the `DELETE /{comment_id}` endpoint, returning HTTP 204 No Content on success [[route:DELETE /api/articles/{slug}/comments/{comment_id}]] [[target/app/api/routes/comments.py::delete_comment_from_article]]. The handler resolves its `comment` parameter by injecting the result of `get_comment_by_id_from_path`, which looks up the target `Comment` object from the path [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. The `comments_repo` parameter is supplied by `get_repository(CommentsRepository)`, providing a `CommentsRepository` instance backed by the active database session [[target/app/api/dependencies/database.py::get_repository]]. Before the handler body executes, `check_comment_modification_permissions` runs as a route-level dependency declared in the decorator, ensuring only authorised callers may proceed [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. The function body contains a single awaited call to `comments_repo.delete_comment`, passing the resolved `Comment` object, after which it returns `None` and the framework emits the 204 response [[target/app/api/routes/comments.py::delete_comment_from_article]].

> **FastAPI deps:** check_comment_modification_permissions, get_comment_by_id_from_path, get_repository

## list_comments_for_article

`list_comments_for_article` is an asynchronous route handler that retrieves all comments for a given article and returns them as a structured response [[target/app/api/routes/comments.py::list_comments_for_article]]. It is registered on the router as a GET endpoint at the path inherited by the comments router, with a response model of `ListOfCommentsInResponse` and the name `comments:get-comments-for-article` [[route:GET /api/articles/{slug}/comments]].

The function accepts three injected dependencies. The first resolves the target article from the URL slug via `get_article_by_slug_from_path`, producing an `Article` instance [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. The second resolves the currently authenticated user through `get_current_user_authorizer` called with `required=False`, meaning an unauthenticated request is permitted and `user` will be `Optional[User]` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The third injects a `CommentsRepository` instance via `get_repository`, providing database access for comment queries [[target/app/api/dependencies/database.py::get_repository]].

The body delegates entirely to the repository, calling `comments_repo.get_comments_for_article` with the resolved article and optional user, then wraps the result in a `ListOfCommentsInResponse` before returning it [[target/app/api/routes/comments.py::list_comments_for_article]]. No exceptions are explicitly raised within the function itself; any error handling for a missing or invalid slug is the responsibility of the `get_article_by_slug_from_path` dependency [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]].

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

