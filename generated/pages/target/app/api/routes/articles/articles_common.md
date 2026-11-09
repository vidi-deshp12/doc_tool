# articles_common

This module defines a shared FastAPI `router` and three route handler functions that together cover the article feed and favouriting features of the API [[target/app/api/routes/articles/articles_common.py]].

The first handler, `get_articles_for_user_feed`, serves `GET /api/articles/feed` and returns a paginated, personalised feed for the currently authenticated user [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. It accepts `limit` and `offset` query parameters (with sensible defaults drawn from `DEFAULT_ARTICLES_LIMIT` and `DEFAULT_ARTICLES_OFFSET`) and delegates the actual database retrieval to `ArticlesRepository`, wrapping the results in a `ListOfArticlesInResponse` that carries the total article count [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]].

The second handler, `mark_article_as_favorite`, serves `POST /api/articles/{slug}/favorite` [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. It resolves the target article from the URL slug, verifies the user is authenticated, and — provided the article is not already favourited — persists the relationship via the repository and returns an `ArticleInResponse` reflecting `favorited: True` and an incremented `favorites_count` [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. Attempting to favourite an already-favourited article results in an `HTTP 400` error [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]].

The third handler, `remove_article_from_favorites`, mirrors that logic in reverse, serving `DELETE /api/articles/{slug}/favorite` [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. When the article is currently favourited it removes the relationship and returns an `ArticleInResponse` with `favorited` patched to `False` and `favorites_count` decremented by one; if the article was not favourited to begin with, it raises `HTTP 400` [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

All three handlers share the same dependency wiring pattern: the article (where applicable) is resolved from the path slug, the acting user is supplied by `get_current_user_authorizer`, and the `ArticlesRepository` is injected via `get_repository` [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]] [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]] [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

## get_articles_for_user_feed

Handles `GET /api/articles/feed` by fetching the authenticated user's personalised article feed [[route:GET /api/articles/feed]] [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. It requires a valid authenticated user via [`get_current_user_authorizer()`](target/app/api/dependencies/authentication.py::get_current_user_authorizer) and an `ArticlesRepository` instance supplied by [`get_repository`](target/app/api/dependencies/database.py::get_repository). Pagination is controlled by `limit` (minimum 1, defaults to `DEFAULT_ARTICLES_LIMIT`) and `offset` (minimum 0, defaults to `DEFAULT_ARTICLES_OFFSET`) [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. It delegates the database query to `articles_repo.get_articles_for_user_feed`, passing the resolved `user`, `limit`, and `offset` [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. Each returned article is converted to an `ArticleForResponse` via its `.dict()` representation, then the full list is wrapped in a [`ListOfArticlesInResponse`](target/app/models/schemas/articles.py::ListOfArticlesInResponse) that also carries the total count [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]].

> **FastAPI deps:** get_current_user_authorizer, get_repository

## mark_article_as_favorite

Handles `POST /api/articles/{slug}/favorite` to mark an article as a favourite for the authenticated user [[route:POST /api/articles/{slug}/favorite]] [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. The article is resolved from the URL slug via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]], the acting user is supplied by `get_current_user_authorizer` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]], and the repository is injected through `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. When the article is not yet favourited, it calls `articles_repo.add_article_into_favorites` to persist the relationship and returns an `ArticleInResponse` whose embedded article reflects `favorited: True` and an incremented `favorites_count` [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]] [[target/app/models/schemas/articles.py::ArticleInResponse]]. If the article is already favourited, it raises `HTTPException` with HTTP 400 [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

## remove_article_from_favorites

Handles `DELETE /api/articles/{slug}/favorite` to remove an article from the current user's favorites [[route:DELETE /api/articles/{slug}/favorite]] [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. The article is resolved from the URL slug via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]], the authenticated user is injected by `get_current_user_authorizer` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]], and the repository is provided by `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. When `article.favorited` is `True`, it calls `articles_repo.remove_article_from_favorites` then builds and returns an `ArticleInResponse` whose embedded article has `favorited` patched to `False` and `favorites_count` decremented by one [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]] [[target/app/models/schemas/articles.py::ArticleInResponse]]. If the article is not already favorited, it raises `HTTPException` with status `400 Bad Request` [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

