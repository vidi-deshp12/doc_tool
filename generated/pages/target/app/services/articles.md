# articles

[`target/app/services/articles.py`](target/app/services/articles.py) is a service module that provides three focused helper functions for working with articles, sitting between the HTTP layer and the data-access layer without containing any route registration or framework decorators [[target/app/services/articles.py]].

The first function, `check_article_exists`, is an asynchronous helper that reports whether an article identified by a given slug is present in the data store [[target/app/services/articles.py::check_article_exists]]. It accepts an `ArticlesRepository` instance and a `slug` string, delegates the lookup to `articles_repo.get_article_by_slug`, and converts an `EntityDoesNotExist` exception into a `False` return value rather than propagating it to the caller, returning `True` when no exception is raised [[target/app/services/articles.py::check_article_exists]].

The second function, `get_slug_for_article`, is a small synchronous utility that converts a plain article title into a URL-friendly slug by delegating entirely to a `slugify` call and returning its result unchanged [[target/app/services/articles.py::get_slug_for_article]]. It carries no side effects and raises no exceptions of its own [[target/app/services/articles.py::get_slug_for_article]].

The third function, `check_user_can_modify_article`, determines whether a given user has permission to modify a specific article by comparing the article's author username with the provided user's username, returning `True` on a match and `False` otherwise [[target/app/services/articles.py::check_user_can_modify_article]]. It depends only on the two domain objects passed in — an `Article` and a `User` — with no additional dependencies or raised exceptions [[target/app/services/articles.py::check_user_can_modify_article]].

Together, the three functions form a cohesive set of article-related business-logic utilities: one derives a slug from a title, one checks whether that slug already exists in the repository, and one enforces ownership before a modification is allowed [[target/app/services/articles.py]].

## check_article_exists

`check_article_exists` is an asynchronous helper function that reports whether an article identified by a given slug is present in the data store [[target/app/services/articles.py::check_article_exists]]. It accepts two parameters: an `ArticlesRepository` instance used to perform the lookup, and a `slug` string that identifies the article to search for [[target/app/services/articles.py::check_article_exists]].

The function delegates the actual retrieval to `articles_repo.get_article_by_slug`, passing the slug as a keyword argument [[target/app/services/articles.py::check_article_exists]]. If that call raises an `EntityDoesNotExist` exception — indicating no matching article was found — the function catches it and returns `False` [[target/app/services/articles.py::check_article_exists]]. If the call completes without raising, the article exists and the function returns `True` [[target/app/services/articles.py::check_article_exists]].

The function carries no route-registration or authorization decorators, and it surfaces no exceptions to its caller: the only exception it handles (`EntityDoesNotExist`) is caught internally and converted into the boolean result [[target/app/services/articles.py::check_article_exists]].

## check_user_can_modify_article

The `check_user_can_modify_article` function determines whether a given user has permission to modify a specific article by comparing the article's author username with the provided user's username [[target/app/services/articles.py::check_user_can_modify_article]]. It accepts two parameters: an `Article` instance and a `User` instance [[target/app/services/articles.py::check_user_can_modify_article]]. It returns a `bool` — `True` if the article's author username matches the user's username, and `False` otherwise [[target/app/services/articles.py::check_user_can_modify_article]]. There are no decorators, raised exceptions, or additional dependencies beyond the two domain objects passed in [[target/app/services/articles.py::check_user_can_modify_article]].

## get_slug_for_article

`get_slug_for_article` is a small utility function that converts an article title into a URL-friendly slug [[target/app/services/articles.py::get_slug_for_article]]. It accepts a single parameter, `title`, of type `str`, and returns a `str` [[target/app/services/articles.py::get_slug_for_article]]. Internally it delegates all transformation work to a `slugify` call, passing the title directly and returning the result unchanged [[target/app/services/articles.py::get_slug_for_article]]. The function has no decorators, raises no exceptions of its own, and carries no side effects [[target/app/services/articles.py::get_slug_for_article]].

