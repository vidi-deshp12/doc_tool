# articles_common

This module defines a FastAPI `APIRouter` and registers three route handlers that together cover the user feed and article-favouriting features of the articles API [[target/app/api/routes/articles/articles_common.py]].

The first handler, `get_articles_for_user_feed`, is mounted on `GET /feed` and returns a paginated list of articles scoped to the authenticated user's feed [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. It accepts `limit` and `offset` query parameters — both validated by FastAPI's `Query` with minimum bounds and module-level defaults — and resolves the current user and an `ArticlesRepository` instance through dependency injection [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. After awaiting the repository call, it converts each result into an `ArticleForResponse` and wraps the list and its count into a `ListOfArticlesInResponse`, which is also the declared `response_model` [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]].

The second handler, `mark_article_as_favorite`, is mounted on `POST /{slug}/favorite` and allows an authenticated user to favourite a specific article [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. It resolves the target article from the URL slug, the current user, and a repository, all via `Depends` [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. When the article has not yet been favourited, it persists the relationship and returns an `ArticleInResponse` whose embedded `ArticleForResponse` reflects `favorited` set to `True` and `favorites_count` incremented by one, computed in-memory with `article.copy` rather than a second database round-trip [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. If the article is already favourited, the handler raises an `HTTPException` with HTTP 400 [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]].

The third handler, `remove_article_from_favorites`, is the mirror image of the second, mounted on `DELETE /{slug}/favorite` [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. It resolves the same three dependencies and checks whether the article is currently favourited [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. If it is, it awaits the repository removal and returns an `ArticleInResponse` with `favorited` set to `False` and `favorites_count` decremented by one [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. If the article was not favourited to begin with, it raises an `HTTPException` with HTTP 400 [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

All three handlers share the same dependency resolution pattern — authentication via `get_current_user_authorizer()` and database access via `get_repository(ArticlesRepository)` — and the two favouriting handlers additionally share slug-based article resolution via `get_article_by_slug_from_path`, making the module a cohesive set of related article-feed and favouriting endpoints built on a common injection foundation [[target/app/api/routes/articles/articles_common.py]].

## get_articles_for_user_feed

`get_articles_for_user_feed` is an asynchronous route handler registered on `GET /api/articles/feed` that returns a paginated list of articles tailored to the authenticated user's feed [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]] [[route:GET /api/articles/feed]].

It accepts two optional integer query parameters, `limit` and `offset`, both validated with FastAPI's `Query` — `limit` must be at least 1 and `offset` at least 0, with default values drawn from module-level constants [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. Authentication is enforced through the `user` parameter, which is resolved by injecting `get_current_user_authorizer()` via FastAPI's `Depends` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The repository used to query articles is likewise injected by `get_repository(ArticlesRepository)` [[target/app/api/dependencies/database.py::get_repository]].

Inside the handler, it awaits a call to `articles_repo.get_articles_for_user_feed`, passing the resolved `user`, `limit`, and `offset` to retrieve only the articles relevant to that user [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. Each returned article is then converted into an `ArticleForResponse` instance by unpacking the article's fields as a dictionary [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. The handler wraps the resulting list and its count into a `ListOfArticlesInResponse` object, which is also the declared `response_model` on the route decorator, and returns it [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]] [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]].

> **FastAPI deps:** get_current_user_authorizer, get_repository

## mark_article_as_favorite

`mark_article_as_favorite` is an async POST endpoint registered at `/api/articles/{slug}/favorite` that allows an authenticated user to mark a specific article as a favourite [[route:POST /api/articles/{slug}/favorite]] [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]].

It is decorated with `router.post("/{slug}/favorite", response_model=ArticleInResponse, name="articles:mark-article-favorite")`, which registers the route and declares that successful responses conform to the `ArticleInResponse` schema [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]] [[target/app/models/schemas/articles.py::ArticleInResponse]].

The function accepts three injected dependencies: the target `Article`, resolved from the URL's `{slug}` path parameter via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]; the currently authenticated `User`, supplied by `get_current_user_authorizer()` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]; and an `ArticlesRepository` instance for database access, provided by `get_repository(ArticlesRepository)` [[target/app/api/dependencies/database.py::get_repository]].

When the article has not yet been favourited by the user, the function calls `articles_repo.add_article_into_favorites` to persist the relationship, then constructs and returns an `ArticleInResponse` whose embedded `ArticleForResponse` reflects the updated state — `favorited` set to `True` and `favorites_count` incremented by one — without re-querying the database, using `article.copy` to produce the updated view [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]].

If the article is already favourited (`article.favorited` is truthy), the function raises an `HTTPException` with HTTP 400, signalling that the article has already been added to the user's favourites [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. The function's declared return type is `ArticleInResponse` [[target/app/models/schemas/articles.py::ArticleInResponse]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

## remove_article_from_favorites

`remove_article_from_favorites` is an asynchronous route handler registered on `DELETE /api/articles/{slug}/favorite` [[route:DELETE /api/articles/{slug}/favorite]] [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. It is decorated with `router.delete("/{slug}/favorite", response_model=ArticleInResponse, name="articles:unmark-article-favorite")`, which binds it to the delete verb and declares `ArticleInResponse` as the serialisation shape for successful responses [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]] [[target/app/models/schemas/articles.py::ArticleInResponse]].

The function accepts three injected parameters [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. `article` is resolved by `get_article_by_slug_from_path`, which looks up the article from the URL path segment `{slug}` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. `user` is resolved by `get_current_user_authorizer()`, which enforces that the caller is authenticated [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. `articles_repo` is an `ArticlesRepository` instance supplied by `get_repository`, providing database access [[target/app/api/dependencies/database.py::get_repository]].

At runtime the function checks whether the resolved article is already marked as favourited by the current user [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. If it is, the handler awaits `articles_repo.remove_article_from_favorites` to persist the removal, then constructs and returns an `ArticleInResponse` whose embedded article has `favorited` set to `False` and `favorites_count` decremented by one [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]] [[target/app/models/schemas/articles.py::ArticleInResponse]]. If the article is not currently favourited, the function raises an `HTTPException` with HTTP 400 instead of returning a value [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

