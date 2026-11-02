# articles

`target/app/services/articles.py` is a small service module that collects article-related business logic — existence checks, slug generation, and ownership authorization — in one place [[target/app/services/articles.py]].

`check_article_exists` is an asynchronous helper that determines whether an article identified by a given slug is present in the data store [[target/app/services/articles.py::check_article_exists]]. It accepts an `ArticlesRepository` instance and a `slug` string, delegates the actual lookup to `articles_repo.get_article_by_slug`, and returns `False` if `EntityDoesNotExist` is raised or `True` if the call succeeds [[target/app/services/articles.py::check_article_exists]].

`get_slug_for_article` is a thin utility that converts a plain article title into a URL-friendly slug by delegating entirely to a `slugify` call and returning the result directly [[target/app/services/articles.py::get_slug_for_article]]. It performs no additional logic of its own [[target/app/services/articles.py::get_slug_for_article]].

`check_user_can_modify_article` is an authorization helper that decides whether a given user may modify an article by comparing `article.author.username` with `user.username`, returning `True` when they match and `False` otherwise [[target/app/services/articles.py::check_user_can_modify_article]]. Ownership is determined solely by that username equality check, with no external dependencies beyond its two arguments [[target/app/services/articles.py::check_user_can_modify_article]].

Together the three functions form a lightweight service layer: `get_slug_for_article` produces the slug used to identify an article, `check_article_exists` verifies that a slug resolves to a real record, and `check_user_can_modify_article` enforces that only the article's author may alter it [[target/app/services/articles.py]].

## check_article_exists

`check_article_exists` is an asynchronous function that checks whether an article identified by a given slug exists in the data store [[target/app/services/articles.py::check_article_exists]]. It accepts an `ArticlesRepository` instance and a `slug` string as its two parameters [[target/app/services/articles.py::check_article_exists]].

The function attempts to fetch the article by delegating to `articles_repo.get_article_by_slug`, passing the provided slug [[target/app/services/articles.py::check_article_exists]]. If that call raises an `EntityDoesNotExist` exception, the function catches it and returns `False`, indicating the article was not found [[target/app/services/articles.py::check_article_exists]]. If no exception is raised, the function returns `True`, confirming the article exists [[target/app/services/articles.py::check_article_exists]].

## check_user_can_modify_article

`check_user_can_modify_article` is a small authorization helper that determines whether a given user has permission to modify an article [[target/app/services/articles.py::check_user_can_modify_article]]. It accepts two parameters: an `Article` instance and a `User` instance [[target/app/services/articles.py::check_user_can_modify_article]]. It returns a `bool` — `True` if the article's author username matches the supplied user's username, and `False` otherwise [[target/app/services/articles.py::check_user_can_modify_article]]. The check is a direct equality comparison between `article.author.username` and `user.username`, meaning ownership is determined solely by matching usernames [[target/app/services/articles.py::check_user_can_modify_article]]. The function carries no decorators, raises no exceptions, and has no external dependencies beyond its two arguments [[target/app/services/articles.py::check_user_can_modify_article]].

## get_slug_for_article

`get_slug_for_article` is a small utility function defined in the articles service that converts an article title into a URL-friendly slug [[target/app/services/articles.py::get_slug_for_article]]. It accepts a single argument, `title`, typed as a `str`, and returns a `str` [[target/app/services/articles.py::get_slug_for_article]]. Internally it delegates entirely to a `slugify` call, passing the title through and returning the result directly [[target/app/services/articles.py::get_slug_for_article]]. It carries no decorators, raises no exceptions, and performs no additional logic of its own [[target/app/services/articles.py::get_slug_for_article]].

