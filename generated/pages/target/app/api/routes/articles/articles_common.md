# articles_common

This module defines a FastAPI `APIRouter` and registers three route handlers that together cover the user feed and article-favouriting features of the articles API [[target/app/api/routes/articles/articles_common.py]].

`get_articles_for_user_feed` handles `GET /feed` and returns a paginated list of articles tailored to the authenticated user [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. It accepts `limit` and `offset` as query parameters — bounded by `DEFAULT_ARTICLES_LIMIT` and `DEFAULT_ARTICLES_OFFSET` respectively — alongside an injected `User` (enforcing authentication) and an `ArticlesRepository` for database access [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. The handler delegates the fetch to the repository, converts each result into an `ArticleForResponse`, and returns the whole list wrapped in a `ListOfArticlesInResponse` that includes a total count [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]].

`mark_article_as_favorite` handles `POST /{slug}/favorite` and lets an authenticated user favourite a specific article [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. It resolves the target article by slug from the URL path, obtains the current user via the authorizer, and receives an `ArticlesRepository` through the repository factory [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. If the article is not yet favourited, it persists the relationship via `add_article_into_favorites`, then returns an `ArticleInResponse` reflecting the updated state with `favorited` set to `True` and `favorites_count` incremented by one [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. If the article is already favourited, it raises an `HTTPException` with HTTP 400 Bad Request rather than creating a duplicate [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]].

`remove_article_from_favorites` is the mirror image, handling `DELETE /{slug}/favorite` to unfavourite an article [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. It shares the same three injected dependencies — article by slug, authenticated user, and repository — and guards against removing a favourite that was never set [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. When the article is currently favourited, it calls `remove_article_from_favorites` on the repository and returns an `ArticleInResponse` with `favorited` set to `False` and `favorites_count` decremented by one; otherwise it raises an `HTTPException` with HTTP 400 Bad Request [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

All three handlers share the same structural pattern: they depend on `get_current_user_authorizer` to ensure only authenticated callers can proceed, and on `get_repository(ArticlesRepository)` to obtain a consistent database session, keeping route logic decoupled from both authentication and persistence concerns [[target/app/api/routes/articles/articles_common.py]].

## get_articles_for_user_feed

`get_articles_for_user_feed` is an asynchronous route handler registered on `GET /feed` with a response model of `ListOfArticlesInResponse` and the route name `articles:get-user-feed-articles` [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. It is bound to the HTTP path `GET /api/articles/feed` [[route:GET /api/articles/feed]].

The function accepts four injected parameters [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. `limit` and `offset` are integer query parameters with defaults drawn from `DEFAULT_ARTICLES_LIMIT` and `DEFAULT_ARTICLES_OFFSET`; `limit` must be at least 1 and `offset` must be at least 0 [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. `user` is resolved via `get_current_user_authorizer()`, which enforces that the caller is authenticated before the handler runs [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. `articles_repo` is an `ArticlesRepository` instance injected through `get_repository`, giving the handler access to database operations [[target/app/api/dependencies/database.py::get_repository]].

The body delegates the data fetch to `articles_repo.get_articles_for_user_feed`, passing the resolved `user`, `limit`, and `offset`, which returns only articles relevant to that authenticated user's feed [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. Each returned article is then converted into an `ArticleForResponse` instance by unpacking the article's dictionary representation [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]]. Finally, the handler wraps the list and a total count into a `ListOfArticlesInResponse` object and returns it [[target/app/api/routes/articles/articles_common.py::get_articles_for_user_feed]].

> **FastAPI deps:** get_current_user_authorizer, get_repository

## mark_article_as_favorite

`mark_article_as_favorite` is an asynchronous FastAPI route handler registered on `POST /{slug}/favorite` that allows an authenticated user to mark an article as a favourite [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]] [[route:POST /api/articles/{slug}/favorite]].

It accepts three injected dependencies: the target `Article`, resolved by slug from the URL path [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]; the currently authenticated `User`, obtained via the authorizer [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]; and an `ArticlesRepository` instance supplied by the repository factory [[target/app/api/dependencies/database.py::get_repository]]. It returns an `ArticleInResponse` wrapping the updated article state [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]].

The function first checks whether the article is already favourited; if it is not, it calls `articles_repo.add_article_into_favorites` to persist the relationship, then constructs the response by calling `article.copy` with `favorited` set to `True` and `favorites_count` incremented by one, passing the result through `ArticleForResponse.from_orm` into `ArticleInResponse` [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]]. If the article is already favourited, the function raises an `HTTPException` with HTTP 400 Bad Request rather than duplicating the favourite [[target/app/api/routes/articles/articles_common.py::mark_article_as_favorite]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

## remove_article_from_favorites

`remove_article_from_favorites` is an async HTTP handler registered on `DELETE /{slug}/favorite` with the response model `ArticleInResponse` and the route name `articles:unmark-article-favorite` [[route:DELETE /api/articles/{slug}/favorite]] [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

It accepts three injected dependencies: an `Article` resolved from the URL slug [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]], the currently authenticated `User` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]], and an `ArticlesRepository` instance used to interact with the articles data store [[target/app/api/dependencies/database.py::get_repository]].

When the article is already marked as a favourite by the user (`article.favorited` is truthy), the handler awaits `articles_repo.remove_article_from_favorites` to persist the removal [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]]. It then constructs the return value by copying the article with `favorited` set to `False` and `favorites_count` decremented by one, wrapping the result via `ArticleForResponse.from_orm` into an `ArticleInResponse` [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

If the article is not currently favourited, the handler raises an `HTTPException` with HTTP 400 Bad Request and a descriptive detail string rather than attempting the removal [[target/app/api/routes/articles/articles_common.py::remove_article_from_favorites]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer, get_repository

