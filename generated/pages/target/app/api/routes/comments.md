# comments

This module is the FastAPI router that handles all comment-related HTTP endpoints for articles, defining three route handlers mounted on a shared `APIRouter` instance [[target/app/api/routes/comments.py]].

`list_comments_for_article` services `GET /api/articles/{slug}/comments` and returns every comment associated with the article identified by the URL slug [[target/app/api/routes/comments.py::list_comments_for_article]]. The article is resolved from the path via a shared dependency, and the caller may be either authenticated or anonymous — authentication is optional at this endpoint [[target/app/api/routes/comments.py::list_comments_for_article]]. The handler delegates to the repository and wraps the result in a `ListOfCommentsInResponse` before returning it to the caller [[target/app/api/routes/comments.py::list_comments_for_article]].

`create_comment_for_article` services `POST /api/articles/{slug}/comments` and responds with HTTP 201 on success [[target/app/api/routes/comments.py::create_comment_for_article]]. Unlike the listing endpoint, it requires a fully authenticated user; the comment body is taken from the request payload under the key `"comment"`, the target article is resolved from the path slug, and persistence is delegated to the `CommentsRepository` [[target/app/api/routes/comments.py::create_comment_for_article]]. The newly persisted comment is returned serialised as a `CommentInResponse` [[target/app/api/routes/comments.py::create_comment_for_article]].

`delete_comment_from_article` services `DELETE /api/articles/{slug}/comments/{comment_id}` and responds with HTTP 204 No Content, returning no body [[target/app/api/routes/comments.py::delete_comment_from_article]]. Before the handler body runs, a route-level dependency enforces that the caller is authorised to modify the target comment; the comment itself is resolved from the path's `{comment_id}` segment, and the handler delegates removal to the repository with a single awaited call [[target/app/api/routes/comments.py::delete_comment_from_article]].

All three handlers share the same structural pattern: article and comment objects are resolved through path-based dependencies, database access flows through a `CommentsRepository` injected via `get_repository`, and authentication state is obtained through the same authoriser dependency — configured as required or optional depending on the operation [[target/app/api/routes/comments.py]].

## create_comment_for_article

`create_comment_for_article` is an asynchronous route handler that creates a new comment on a specific article [[target/app/api/routes/comments.py::create_comment_for_article]]. It is registered on the router as a POST endpoint returning HTTP 201 on success, with its response serialised as `CommentInResponse` and named `comments:create-comment-for-article` [[route:POST /api/articles/{slug}/comments]].

The function accepts four injected parameters. `comment_create` carries the comment payload, embedded in the request body under the key `"comment"` and typed as `CommentInCreate` [[target/app/models/schemas/comments.py::CommentInCreate]]. `article` is resolved from the URL's `{slug}` segment via the `get_article_by_slug_from_path` dependency [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. `user` is the currently authenticated caller, obtained through `get_current_user_authorizer()`, which means an authenticated user is required to reach this handler [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. `comments_repo` is a `CommentsRepository` instance supplied by the `get_repository` dependency [[target/app/api/dependencies/database.py::get_repository]].

The body of the function delegates persistence to `comments_repo.create_comment_for_article`, passing the comment body text, the resolved article, and the resolved user [[target/app/api/routes/comments.py::create_comment_for_article]]. The newly created comment is then wrapped in a `CommentInResponse` and returned to the caller [[target/app/models/schemas/comments.py::CommentInResponse]].

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

## delete_comment_from_article

`delete_comment_from_article` is an async route handler that removes a single comment from an article [[target/app/api/routes/comments.py::delete_comment_from_article]]. It is registered on the `DELETE /{comment_id}` sub-path and handles the route `DELETE /api/articles/{slug}/comments/{comment_id}` [[route:DELETE /api/articles/{slug}/comments/{comment_id]]]. The route is configured to respond with HTTP 204 No Content on success and uses a plain `Response` class so no body is serialised [[target/app/api/routes/comments.py::delete_comment_from_article]].

The function accepts two injected dependencies. The `comment` parameter is resolved by `get_comment_by_id_from_path`, which looks up the target comment from the path [[target/app/api/dependencies/comments.py::get_comment_by_id_from_path]]. The `comments_repo` parameter is a `CommentsRepository` instance supplied by `get_repository` [[target/app/api/dependencies/database.py::get_repository]].

Before the handler body executes, `check_comment_modification_permissions` is enforced as a route-level dependency, ensuring the caller is authorised to modify the comment [[target/app/api/dependencies/comments.py::check_comment_modification_permissions]]. The body itself consists of a single awaited call to `comments_repo.delete_comment`, passing the resolved comment object, and the function returns `None` [[target/app/api/routes/comments.py::delete_comment_from_article]].

> **FastAPI deps:** check_comment_modification_permissions, get_comment_by_id_from_path, get_repository

## list_comments_for_article

`list_comments_for_article` is an asynchronous route handler that services the `GET /api/articles/{slug}/comments` endpoint, returning all comments associated with a given article [[target/app/api/routes/comments.py::list_comments_for_article]] [[route:GET /api/articles/{slug}/comments]]. It is registered on the router via the `@router.get` decorator with a `response_model` of `ListOfCommentsInResponse` and the name `"comments:get-comments-for-article"` [[target/app/api/routes/comments.py::list_comments_for_article]].

The function accepts three injected parameters via FastAPI's dependency system [[target/app/api/routes/comments.py::list_comments_for_article]]. The first, `article`, is resolved by `get_article_by_slug_from_path`, which looks up the article from the URL's `{slug}` path segment [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. The second, `user`, is an optional `User` resolved by `get_current_user_authorizer(required=False)`, meaning the endpoint is accessible to both authenticated and anonymous callers [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The third, `comments_repo`, is a `CommentsRepository` instance provided by `get_repository` [[target/app/api/dependencies/database.py::get_repository]].

The body of the function awaits a single repository call, `comments_repo.get_comments_for_article`, passing both the resolved article and the (possibly absent) user [[target/app/api/routes/comments.py::list_comments_for_article]]. The resulting list of comments is wrapped in a `ListOfCommentsInResponse` object, which is both the declared return type and the schema used to serialise the HTTP response [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]] [[target/app/api/routes/comments.py::list_comments_for_article]].

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

