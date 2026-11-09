# articles

This module provides FastAPI dependency functions used to resolve article-related concerns — lookup, filtering, and permission enforcement — for the articles API layer [[target/app/api/dependencies/articles.py]].

The `get_article_by_slug_from_path` dependency handles article retrieval by reading a slug from the URL path and querying the database through an injected `ArticlesRepository` [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. Authentication is optional at this stage, so both anonymous and authenticated callers are supported, with the authenticated user's identity forwarded to the repository query when present [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. If no article matches the slug, the internal `EntityDoesNotExist` exception is translated into an HTTP 404 response [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]].

The `check_article_modification_permissions` dependency builds on `get_article_by_slug_from_path` by also requiring a fully authenticated user, then delegating the authorization decision to `check_user_can_modify_article` [[target/app/api/dependencies/articles.py::check_article_modification_permissions]]. If that check fails, an HTTP 403 Forbidden exception is raised using a message from the `strings` resource module, ensuring that only permitted users can mutate an article [[target/app/api/dependencies/articles.py::check_article_modification_permissions]].

The `get_articles_filters` dependency operates independently of the other two, collecting up to five optional query-string parameters — a tag, an author name, a favorited-by username, and pagination `limit` and `offset` values — and packing them into a single `ArticlesFilters` object that callers can consume [[target/app/api/dependencies/articles.py::get_articles_filters]]. Minimum bounds are enforced by FastAPI's `Query` validator before the object is constructed [[target/app/api/dependencies/articles.py::get_articles_filters]].

## check_article_modification_permissions

Verifies that the currently authenticated user has permission to modify a given article, raising an `HTTPException` with HTTP 403 Forbidden if the check fails [[target/app/api/dependencies/articles.py::check_article_modification_permissions]]. It resolves the target article via `get_article_by_slug_from_path` and the acting user via `get_current_user_authorizer`, both injected through FastAPI's `Depends` mechanism [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]] [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The authorization decision is delegated to `check_user_can_modify_article`, and when that returns falsy the exception is raised with a detail message drawn from the `strings` module [[target/app/api/dependencies/articles.py::check_article_modification_permissions]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_article_by_slug_from_path, get_current_user_authorizer

## get_article_by_slug_from_path

Fetches an article by its URL path slug, delegating to `articles_repo.get_article_by_slug` with the slug and the optionally authenticated user [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. The slug is extracted from the request path and must be at least one character long [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]]. Authentication is optional, resolved via `get_current_user_authorizer(required=False)`, meaning the endpoint is accessible to anonymous users but will pass along the identity of an authenticated one [[target/app/api/dependencies/authentication.py::get_current_user_authorizer]]. The repository is injected through `get_repository(ArticlesRepository)` [[target/app/api/dependencies/database.py::get_repository]]. If no matching article exists, the caught `EntityDoesNotExist` exception is re-raised as an HTTP 404 [[target/app/api/dependencies/articles.py::get_article_by_slug_from_path]].

> **Raises:** fastapi.HTTPException

> **FastAPI deps:** get_current_user_authorizer, get_repository

## get_articles_filters

Collects optional query-string filters (`tag`, `author`, `favorited`) and validated pagination parameters (`limit`, `offset`) from the request, enforcing a minimum of 1 for `limit` and 0 for `offset` via FastAPI's `Query` [[target/app/api/dependencies/articles.py::get_articles_filters]]. It packages all five values into an `ArticlesFilters` object and returns it [[target/app/api/dependencies/articles.py::get_articles_filters]].

