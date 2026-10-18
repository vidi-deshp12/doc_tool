# authentication

The [`authentication.py`](target/app/services/authentication.py) module is a small service-layer helper that provides uniqueness checks for the two primary user identity fields: username and email [[target/app/services/authentication.py]]. It contains no route definitions or authorization decorators — its two functions are plain async utilities intended to be called by other parts of the application, such as user registration logic, before persisting a new account [[target/app/services/authentication.py]].

Both functions follow the same pattern: they accept a `UsersRepository` instance and a string value to look up, attempt a database query through the repository, and return a `bool` indicating whether the value is already in use [[target/app/services/authentication.py::check_username_is_taken]] [[target/app/services/authentication.py::check_email_is_taken]].

[`check_username_is_taken`](target/app/services/authentication.py::check_username_is_taken) queries the repository for a user matching the given username via `repo.get_user_by_username` [[target/app/services/authentication.py::check_username_is_taken]]. If the lookup raises `EntityDoesNotExist`, the username is available and the function returns `False`; if the query succeeds without raising, it returns `True` [[target/app/services/authentication.py::check_username_is_taken]].

[`check_email_is_taken`](target/app/services/authentication.py::check_email_is_taken) works identically but targets the email field, delegating to `repo.get_user_by_email` [[target/app/services/authentication.py::check_email_is_taken]]. A caught `EntityDoesNotExist` signals the email is available and yields `False`, while a successful lookup yields `True` [[target/app/services/authentication.py::check_email_is_taken]].

The two functions are closely parallel by design: the only structural difference between them is which repository method is called and which field is queried, making the module a consistent and predictable pair of availability checks [[target/app/services/authentication.py::check_username_is_taken]] [[target/app/services/authentication.py::check_email_is_taken]].

## check_email_is_taken

`check_email_is_taken` is an asynchronous function that determines whether a given email address is already registered in the system [[target/app/services/authentication.py::check_email_is_taken]]. It accepts a `UsersRepository` instance and an email string as its two parameters, and returns a `bool` [[target/app/services/authentication.py::check_email_is_taken]].

Internally, it attempts to look up a user by the provided email address via `repo.get_user_by_email` [[target/app/services/authentication.py::check_email_is_taken]]. If no matching user is found, an `EntityDoesNotExist` exception is caught and the function returns `False`, indicating the email is available [[target/app/services/authentication.py::check_email_is_taken]]. If the call succeeds without raising that exception, the function returns `True`, indicating the email is already taken [[target/app/services/authentication.py::check_email_is_taken]].

## check_username_is_taken

`check_username_is_taken` is an asynchronous function that determines whether a given username is already registered in the system [[target/app/services/authentication.py::check_username_is_taken]]. It accepts a `UsersRepository` instance (`repo`) and a `username` string as its two parameters, and returns a `bool` [[target/app/services/authentication.py::check_username_is_taken]].

The function works by attempting to fetch a user record that matches the provided username via `repo.get_user_by_username` [[target/app/services/authentication.py::check_username_is_taken]]. If that lookup raises an `EntityDoesNotExist` exception — meaning no matching user was found — the function catches it and returns `False`, indicating the username is available [[target/app/services/authentication.py::check_username_is_taken]]. If no exception is raised, the lookup succeeded and the function returns `True`, indicating the username is already taken [[target/app/services/authentication.py::check_username_is_taken]].

There are no route decorators or authorization decorators on this function; it is a plain service-layer helper intended to be called by other parts of the application that need to validate username uniqueness before, for example, registering a new user [[target/app/services/authentication.py]].

