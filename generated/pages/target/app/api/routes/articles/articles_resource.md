# articles_resource

This module defines the FastAPI router and all five route handlers that together form the articles REST API [[target/app/api/routes/articles/articles_resource.py]]. A single `APIRouter` instance named `router` is declared at module level and each handler is attached to it via decorator, so the full set of CRUD operations for articles lives in one place [[target/app/api/routes/articles/articles_resource.py]].

The `list_articles` handler serves `GET /api/articles` and accepts optional filtering and pagination parameters — tag, author, favorited, limit, and offset — alongside an optionally authenticated user, delegating the actual database query to `ArticlesRepository.filter_articles` before returning a `ListOfArticlesInResponse` envelope containing the converted articles and their count [[target/app/api/routes/articles/articles_resource.py::list_articles]]. Authentication is optional on this endpoint, meaning unauthenticated callers can still retrieve articles, though the repository may tailor results when a user identity is present [[target/app/api/routes/articles/articles_resource.py::list_articles]].

The `create_new_article` handler serves `POST /api/articles` and requires an authenticated user [[target/app/api/routes/articles/articles_resource.py::create_new_article]]. It derives a URL slug from the submitted title and checks for a duplicate before writing; if a conflicting slug is found it raises an HTTP 400 error before any persistence occurs, otherwise it delegates to `articles_repo.create_article` and returns the newly created article wrapped in an `ArticleInResponse` [[target/app/api/routes/articles/articles_resource.py::create_new_article]].

The `retrieve_article_by_slug` handler serves `GET /api/articles/{slug}` and contains no lookup logic of its own — the article is fully resolved from the path segment by the `get_article_by_slug_from_path` dependency before the handler body runs, and the handler simply converts the injected ORM object into an `ArticleInResponse` via `ArticleForResponse.from_orm` [[target/app/api/routes/articles/articles_resource.py::retrieve_article_by_slug]].

The `update_article_by_slug` handler serves `PUT /api/articles/{slug}` and shares the same slug-resolution dependency as the retrieval handler, receiving the existing article ready to use [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]]. Both this handler and `delete_article_by_slug` declare `check_article_modification_permissions` as a route-level dependency in their decorators, so FastAPI enforces the authorisation check before either handler body executes [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]] [[target/app/api/routes/articles/articles_resource.py::delete_article_by_slug]]. When a new title is supplied, `update_article_by_slug` recomputes the slug from it; all fields from the update payload are then spread as keyword arguments into `articles_repo.update_article`, and the result is returned as an `ArticleInResponse` [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]].

The `delete_article_by_slug` handler serves `DELETE /api/articles/{slug}`, responds with HTTP 204 No Content, and its entire body is a single awaited call to `articles_repo.delete_article` with the resolved article, returning `None` afterwards [[target/app/api/routes/articles/articles_resource.py::delete_article_by_slug]].

## create_new_article

`create_new_article` is an asynchronous FastAPI route handler registered on `POST /api/articles` that creates a new article and returns its representation to the caller [[target/app/api/routes/articles/articles_resource.py::create_new_article]] [[route:POST /api/articles]].

The function accepts three injected parameters: `article_create`, an `ArticleInCreate` body payload embedded under the JSON key `"article"` [[target/app/models/schemas/articles.py::ArticleInCreate]]; `user`, the currently authenticated user resolved by `get_current_user_authorizer()` [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]; and `articles_repo`, an `ArticlesRepository` instance provided by `get_repository` [[target/app/api/dependencies/database.py::get_repository]].

On entry, a URL slug is derived from the incoming title, then the repository is queried to check whether an article with that slug already exists [[target/app/api/routes/articles/articles_resource.py::create_new_article]]. If one does, the function raises an `HTTPException` with HTTP 400 before any write occurs [[target/app/api/routes/articles/articles_resource.py::create_new_article]].

When the slug is free, the function delegates persistence to `articles_repo.create_article`, passing the slug, title, description, body, the resolved author, and any tags from the request payload [[target/app/api/routes/articles/articles_resource.py::create_new_article]] [[target/app/models/schemas/articles.py::ArticleInCreate]]. The newly persisted article is then wrapped with `ArticleForResponse.from_orm` and returned inside an `ArticleInResponse` envelope, which is also the declared `response_model` on the decorator [[target/app/api/routes/articles/articles_resource.py::create_new_article]] [[target/app/models/schemas/articles.py::ArticleInResponse]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository

## delete_article_by_slug

`delete_article_by_slug` is an asynchronous route handler that processes `DELETE` requests to `/api/articles/{slug}`, responding with HTTP 204 No Content on success [[route:DELETE /api/articles/{slug}]] [[target/app/api/routes/articles/articles_resource.py::delete_article_by_slug]]. Before the handler body runs, FastAPI enforces a permission check via `check_article_modification_permissions`, declared as a route-level dependency in the decorator, ensuring that only authorised callers can remove an article [[target/app/api/dependencies/articles.py::check_article_modification_permissions]]. The function accepts two injected parameters: an `Article` instance resolved by `get_article_by_slug_from_path` (which looks up the article from the `{slug}` path segment) and an `ArticlesRepository` instance supplied by `get_repository(ArticlesRepository)` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]] [[target/app/api/dependencies/database.py::get_repository]]. The entire body is a single awaited call to `articles_repo.delete_article`, passing the resolved article, after which the function returns `None` and FastAPI sends the empty 204 response [[target/app/api/routes/articles/articles_resource.py::delete_article_by_slug]].

> **FastAPI deps:** check_article_modification_permissions, get_article_by_slug_from_path, get_repository

## list_articles

`list_articles` is an asynchronous route handler that serves the `GET /api/articles` endpoint, registered via the `router.get` decorator with a response model of `ListOfArticlesInResponse` [[target/app/api/routes/articles/articles_resource.py::list_articles]] [[route:GET /api/articles]].

It accepts three injected dependencies: `articles_filters`, an `ArticlesFilters` object built by `get_articles_filters` that carries filtering and pagination parameters (tag, author, favorited, limit, offset) [[target/app/api/dependencies/articles.py::get_articles_filters]]; `user`, an optional `User` resolved by `get_current_user_authorizer(required=False)`, meaning the endpoint is accessible without authentication [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]; and `articles_repo`, an `ArticlesRepository` instance provided by `get_repository` for database access [[target/app/api/dependencies/database.py::get_repository]].

The function awaits `articles_repo.filter_articles`, passing all filter fields from `articles_filters` together with the optionally resolved `user` as `requested_user`, allowing the repository to tailor results to the caller's perspective (for example, to mark favourites) [[target/app/api/routes/articles/articles_resource.py::list_articles]]. Each article returned by the repository is then converted to a response-safe shape via `ArticleForResponse.from_orm` [[target/app/api/routes/articles/articles_resource.py::list_articles]].

Finally, it constructs and returns a `ListOfArticlesInResponse` containing the converted articles list and a count equal to the number of retrieved articles [[target/app/models/schemas/articles.py::ListOfArticlesInResponse]] [[target/app/api/routes/articles/articles_resource.py::list_articles]].

> **FastAPI deps:** get_articles_filters, get_current_user_authorizer, get_repository

## retrieve_article_by_slug

`retrieve_article_by_slug` is an asynchronous route handler registered on `GET /{slug}` (mounted under the articles router, resolving to `GET /api/articles/{slug}`) that retrieves a single article by its URL slug and returns it as a structured response [[target/app/api/routes/articles/articles_resource.py::retrieve_article_by_slug]] [[route:GET /api/articles/{slug}]]. It is decorated with `router.get("/{slug}", response_model=ArticleInResponse, name="articles:get-article")`, which binds it to the GET method, declares the expected response shape, and registers it under the name `articles:get-article` [[target/app/api/routes/articles/articles_resource.py::retrieve_article_by_slug]].

The function accepts a single parameter, `article`, which is injected by FastAPI's dependency system via `Depends(get_article_by_slug_from_path)` — meaning FastAPI calls that dependency automatically, resolving and validating the article from the `slug` path segment before this handler runs [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. The handler itself contains no manual lookup logic; the resolved `Article` ORM object arrives ready to use [[target/app/api/routes/articles/articles_resource.py::retrieve_article_by_slug]].

The return value is an [`ArticleInResponse`](target/app/models/schemas/articles.py::ArticleInResponse) instance constructed by wrapping the injected ORM object with `ArticleForResponse.from_orm(article)`, converting it from the ORM representation into the serialisable schema shape that FastAPI validates against the declared `response_model` [[target/app/models/schemas/articles.py::ArticleInResponse]] [[target/app/api/routes/articles/articles_resource.py::retrieve_article_by_slug]].

> **FastAPI deps:** get_article_by_slug_from_path

## update_article_by_slug

`update_article_by_slug` is an asynchronous route handler that processes `PUT` requests to `/api/articles/{slug}`, allowing a client to update an existing article [[route:PUT /api/articles/{slug}]] [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]].

It accepts three injected parameters: `article_update`, an [`ArticleInUpdate`](target/app/models/schemas/articles.py::ArticleInUpdate) instance carrying the fields to be changed, embedded in the request body under the key `"article"` [[target/app/models/schemas/articles.py::ArticleInUpdate]]; `current_article`, the existing `Article` object resolved from the URL's `{slug}` segment by [`get_article_by_slug_from_path`](target/app/api/dependencies/articles.py::get_article_by_slug_from_path) [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]; and `articles_repo`, an `ArticlesRepository` instance supplied by [`get_repository`](target/app/api/dependencies/database.py::get_repository) [[target/app/api/dependencies/database.py::get_repository]].

Before the handler body executes, FastAPI runs [`check_article_modification_permissions`](target/app/api/dependencies/articles.py::check_article_modification_permissions) as a route-level dependency declared in the decorator, ensuring only authorised callers can modify the article [[target/app/api/dependencies/articles.py::check_article_modification_permissions]] [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]].

Inside the handler, if `article_update.title` is present, a new slug is derived from it; otherwise the slug is left as `None` [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]]. The repository's `update_article` method is then awaited with the current article, the computed slug, and all fields from `article_update` spread as keyword arguments [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]].

The function returns an [`ArticleInResponse`](target/app/models/schemas/articles.py::ArticleInResponse) built from the updated article, converting the ORM object via `ArticleForResponse.from_orm` [[target/app/models/schemas/articles.py::ArticleInResponse]] [[target/app/api/routes/articles/articles_resource.py::update_article_by_slug]].

> **FastAPI deps:** check_article_modification_permissions, get_article_by_slug_from_path, get_repository

