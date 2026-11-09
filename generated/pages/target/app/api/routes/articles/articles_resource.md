# articles_resource

This module defines the FastAPI `router` and the five route-handler functions that together implement the core articles REST API [[target/app/api/routes/articles/articles_resource.py]].

`list_articles` handles `GET /api/articles` and returns a paginated, filtered collection of articles wrapped in a `ListOfArticlesInResponse` envelope [[target/app/api/routes/articles/articles_resource.py::list_articles]]. It accepts an optional authenticated caller so that unauthenticated requests are also permitted, resolves filter parameters (tag, author, favorited, limit, offset), and maps each result through `ArticleForResponse.from_orm` before building the final response [[target/app/api/routes/articles/articles_resource.py::list_articles]].

`create_new_article` handles `POST /api/articles` and requires an authenticated user [[target/app/api/routes/articles/articles_resource.py::create_new_article]]. It derives a URL-safe slug from the incoming title and raises an `HTTPException` with status `400` if an article with that slug already exists; otherwise it persists the article and returns it inside an `ArticleInResponse` envelope [[target/app/api/routes/articles/articles_resource.py::create_new_article]].

`retrieve_article_by_slug` handles `GET /api/articles/{slug}`, resolving the target article from the URL path, converting it with `ArticleForResponse.from_orm`, and returning it wrapped in an `ArticleInResponse` [[target/app/api/routes/articles/articles_resource.py::retrieve_article_by_slug]].

`update_article_by_slug` handles `PUT /api/articles/{slug}` [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]]. Before the handler body executes, write-access is enforced by `check_article_modification_permissions`; a new slug is derived from the updated title when one is provided, and the remaining update fields are forwarded to the repository before the result is returned in an `ArticleInResponse` [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]].

`delete_article_by_slug` handles `DELETE /api/articles/{slug}` and responds with HTTP 204 No Content [[target/app/api/routes/articles/articles_resource.py::delete_article_by_slug]]. Like the update handler, it enforces `check_article_modification_permissions` as a route-level dependency before delegating the permanent removal to the articles repository [[target/app/api/routes/articles/articles_resource.py::delete_article_by_slug]].

## create_new_article

Handles the `POST /api/articles` route to create a new article on behalf of an authenticated user [[route:POST /api/articles]] [[target/app/api/routes/articles/articles_resource.py::create_new_article]]. It accepts the article payload as an embedded request body under the key `"article"`, typed as `ArticleInCreate` [[target/app/models/schemas/articles.py::ArticleInCreate]], and resolves the current user and the articles repository via FastAPI dependency injection [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]] [[target/app/api/dependencies/database.py::get_repository]]. A URL-safe slug is derived from the incoming title, then the repository is queried to check whether an article with that slug already exists; if it does, an `HTTPException` with status `400` is raised [[target/app/api/routes/articles/articles_resource.py::create_new_article]]. When the slug is free, the article is persisted via `articles_repo.create_article`, passing the slug, title, description, body, authenticated user as author, and tags [[target/app/api/routes/articles/articles_resource.py::create_new_article]]. The persisted article is wrapped with `ArticleForResponse.from_orm` and returned inside an `ArticleInResponse` envelope [[target/app/models/schemas/articles.py::ArticleInResponse]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository

## delete_article_by_slug

Handles the `DELETE /api/articles/{slug}` route, responding with HTTP 204 No Content on success [[route:DELETE /api/articles/{slug}]] [[target/app/api/routes/articles/articles_resource.py::delete_article_by_slug]]. The target article is resolved from the URL slug via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]], and `check_article_modification_permissions` is enforced as a route-level dependency before the handler body executes [[target/app/api/dependencies/articles.py::check_article_modification_permissions]]. An `ArticlesRepository` is injected through `get_repository` [[target/app/api/dependencies/database.py::get_repository]], and the resolved article is permanently deleted by delegating to `articles_repo.delete_article` [[target/app/api/routes/articles/articles_resource.py::delete_article_by_slug]].

> **FastAPI deps:** check_article_modification_permissions, get_article_by_slug_from_path, get_repository

## list_articles

Handles `GET /api/articles` and returns a paginated, filtered list of articles wrapped in a `ListOfArticlesInResponse` envelope [[route:GET /api/articles]] [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]]. It resolves filtering parameters (tag, author, favorited, limit, offset) via `get_articles_filters` [[target/app/api/dependencies/articles.py::get_articles_filters]], an optional authenticated user via `get_current_user_authorizer(required=False)` so unauthenticated callers are permitted [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]], and the article repository via `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. It calls `articles_repo.filter_articles` with all resolved filter values and the optional `requested_user`, then maps each result through `ArticleForResponse.from_orm` before constructing the final response with both the article list and its count [[target/app/api/routes/articles/articles_resource.py::list_articles]].

> **FastAPI deps:** get_articles_filters, get_current_user_authorizer, get_repository

## retrieve_article_by_slug

Handles `GET /api/articles/{slug}` requests, resolving the target article via the `get_article_by_slug_from_path` dependency injected into the `article` parameter [[route:GET /api/articles/{slug}]] [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. It converts the resolved `Article` ORM object into a response-safe form using `ArticleForResponse.from_orm`, wraps it in an `ArticleInResponse`, and returns it [[target/app/api/routes/articles/articles_resource.py::retrieve_article_by_slug]] [[target/app/models/schemas/articles.py::ArticleInResponse]].

> **FastAPI deps:** get_article_by_slug_from_path

## update_article_by_slug

Handles `PUT /api/articles/{slug}` to update an existing article [[route:PUT /api/articles/{slug}]] [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]]. The update payload is accepted as an embedded body field aliased to `"article"` and typed as `ArticleInUpdate` [[target/app/models/schemas/articles.py::ArticleInUpdate]]. The article to be modified is resolved from the URL slug via `get_article_by_slug_from_path` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]], and write access is enforced before the handler runs via the `check_article_modification_permissions` dependency [[target/app/api/dependencies/articles.py::check_article_modification_permissions]]. A new slug is derived from the updated title when a title is provided, otherwise `None` is passed [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]]. The resolved slug and the remaining update fields (spread from `article_update.dict()`) are forwarded to `articles_repo.update_article`, which is injected via `get_repository` [[target/app/api/dependencies/database.py::get_repository]]. The updated article is then wrapped with `ArticleForResponse.from_orm` and returned inside an `ArticleInResponse` envelope [[target/app/models/schemas/articles.py::ArticleInResponse]].

> **FastAPI deps:** check_article_modification_permissions, get_article_by_slug_from_path, get_repository

