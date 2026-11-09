# articles

This module provides a small set of article-related service utilities that sit between the API layer and the database and domain models [[target/app/services/articles.py]]. It imports from the repository, domain models, and error types to support three focused helper functions [[target/app/services/articles.py]].

The `check_article_exists` function accepts an `ArticlesRepository` and a slug string, delegating the lookup to `articles_repo.get_article_by_slug` and returning `True` if the article is found or `False` if an `EntityDoesNotExist` exception is raised [[target/app/services/articles.py::check_article_exists]]. This makes it a safe, boolean-returning guard that callers can use without handling database exceptions themselves [[target/app/services/articles.py::check_article_exists]].

The `check_user_can_modify_article` function complements the existence check by enforcing ownership: it compares the article's author username against the requesting user's username and returns `True` only when they match [[target/app/services/articles.py::check_user_can_modify_article]]. Together, these two functions form a natural pair — first confirming an article exists, then confirming the acting user is allowed to change it [[target/app/services/articles.py::check_article_exists]] [[target/app/services/articles.py::check_user_can_modify_article]].

Finally, `get_slug_for_article` handles the transformation of a raw article title into a URL-friendly slug by delegating directly to the `slugify` library [[target/app/services/articles.py::get_slug_for_article]], keeping slug generation consistent and centralised across any code that needs to derive a slug from a title [[target/app/services/articles.py::get_slug_for_article]].

## check_article_exists

Accepts an `ArticlesRepository` and a slug string, then attempts to fetch the matching article by calling `articles_repo.get_article_by_slug` [[target/app/services/articles.py::check_article_exists]]. Returns `True` if the article is found, or `False` if an `EntityDoesNotExist` exception is raised during the lookup [[target/app/services/articles.py::check_article_exists]].

## check_user_can_modify_article

Compares the article's author username against the provided user's username and returns `True` if they match, `False` otherwise [[target/app/services/articles.py::check_user_can_modify_article]].

## get_slug_for_article

Accepts a article title string and returns a URL-friendly slug by delegating directly to `slugify` [[target/app/services/articles.py::get_slug_for_article]].

