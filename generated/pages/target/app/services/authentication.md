# authentication

This module provides authentication-related helper utilities for checking whether user credentials are already registered in the system [[target/app/services/authentication.py]]. It imports `EntityDoesNotExist` from the database errors layer and relies on `UsersRepository` to perform its lookups [[target/app/services/authentication.py]].

The `check_email_is_taken` function accepts a `UsersRepository` and an email string, queries the repository for a matching user, and returns `True` if one is found or `False` if `EntityDoesNotExist` is raised [[target/app/services/authentication.py::check_email_is_taken]]. Similarly, `check_username_is_taken` calls `repo.get_user_by_username` and returns `True` when the username is already registered, or `False` when `EntityDoesNotExist` is raised, indicating the username is available [[target/app/services/authentication.py::check_username_is_taken]]. Both functions share the same pattern of translating a repository-level `EntityDoesNotExist` exception into a plain boolean result, giving callers a clean availability check without needing to handle exceptions directly [[target/app/services/authentication.py::check_email_is_taken]] [[target/app/services/authentication.py::check_username_is_taken]].

## check_email_is_taken

Accepts a `UsersRepository` and an email string, then queries the repository for a matching user [[target/app/services/authentication.py::check_email_is_taken]]. Returns `True` if a user with that email exists, or `False` if `EntityDoesNotExist` is raised by `repo.get_user_by_email` [[target/app/services/authentication.py::check_email_is_taken]].

## check_username_is_taken

Queries the repository for a user matching the given username by calling `repo.get_user_by_username` [[target/app/services/authentication.py::check_username_is_taken]]. Returns `False` if `EntityDoesNotExist` is raised, indicating the username is available, and `True` if the lookup succeeds, indicating the username is already taken [[target/app/services/authentication.py::check_username_is_taken]].

