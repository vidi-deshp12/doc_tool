# authentication

[`target/app/services/authentication.py`](target/app/services/authentication.py) is a small service module that provides uniqueness checks for user credentials during registration [[target/app/services/authentication.py]]. It contains two asynchronous functions, `check_username_is_taken` and `check_email_is_taken`, both of which follow the same pattern: they accept a `UsersRepository` instance and a credential string, delegate a lookup to the repository, and return a `bool` indicating whether the credential is already in use [[target/app/services/authentication.py::check_username_is_taken]] [[target/app/services/authentication.py::check_email_is_taken]].

[`check_username_is_taken`](target/app/services/authentication.py::check_username_is_taken) calls `repo.get_user_by_username` with the provided username and returns `True` if the call succeeds, meaning a matching user already exists [[target/app/services/authentication.py::check_username_is_taken]]. If the repository raises `EntityDoesNotExist` — signalling that no such user was found — the function catches the exception and returns `False` instead [[target/app/services/authentication.py::check_username_is_taken]].

[`check_email_is_taken`](target/app/services/authentication.py::check_email_is_taken) mirrors this behaviour for email addresses, delegating to `repo.get_user_by_email` and applying the same exception-as-signal convention: a raised `EntityDoesNotExist` means the email is unclaimed and yields `False`, while a successful lookup yields `True` [[target/app/services/authentication.py::check_email_is_taken]]. Both functions rely entirely on the repository layer for data access and use `EntityDoesNotExist` as their sole control-flow signal, keeping the service layer free of direct database concerns [[target/app/services/authentication.py::check_username_is_taken]] [[target/app/services/authentication.py::check_email_is_taken]].

## check_email_is_taken

`check_email_is_taken` is an asynchronous function that checks whether a given email address is already registered in the system [[target/app/services/authentication.py::check_email_is_taken]]. It accepts a `UsersRepository` instance (`repo`) and an email string, and returns a `bool` [[target/app/services/authentication.py::check_email_is_taken]].

The function delegates the lookup to `repo.get_user_by_email`, passing the provided email as a keyword argument [[target/app/services/authentication.py::check_email_is_taken]]. If no matching user exists, `get_user_by_email` raises an `EntityDoesNotExist` exception, which the function catches and uses as a signal to return `False` [[target/app/services/authentication.py::check_email_is_taken]]. If the call completes without raising — meaning a user with that email was found — the function returns `True` [[target/app/services/authentication.py::check_email_is_taken]].

## check_username_is_taken

`check_username_is_taken` is an asynchronous function that determines whether a given username is already registered in the system [[target/app/services/authentication.py::check_username_is_taken]]. It accepts a `UsersRepository` instance (`repo`) and a `username` string as its two parameters, and returns a `bool` [[target/app/services/authentication.py::check_username_is_taken]].

The function works by attempting to look up the provided username via `repo.get_user_by_username` [[target/app/services/authentication.py::check_username_is_taken]]. If that call raises an `EntityDoesNotExist` exception — meaning no matching user was found — the function catches it and returns `False` [[target/app/services/authentication.py::check_username_is_taken]]. If the lookup succeeds without raising, the function returns `True`, indicating the username is already taken [[target/app/services/authentication.py::check_username_is_taken]].

