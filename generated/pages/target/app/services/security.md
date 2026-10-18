# security

[`target/app/services/security.py`](target/app/services/security.py) is a small password-security utility module that centralises hashing and verification behind a shared `passlib` context [[target/app/services/security.py]]. At module level it constructs a `CryptContext` instance named `pwd_context`, configured to use the `bcrypt` scheme, which the two hashing functions both delegate to [[target/app/services/security.py]].

`generate_salt` is a standalone helper that produces a fresh cryptographic salt and returns it as a plain UTF-8 string by calling `bcrypt.gensalt().decode()`; it takes no arguments and has no dependencies beyond the `bcrypt` library itself [[target/app/services/security.py::generate_salt]].

`get_password_hash` accepts a single plain-text `password` string and returns its hashed form by passing it directly to `pwd_context.hash`, with no branching or additional logic of its own [[target/app/services/security.py::get_password_hash]].

`verify_password` complements `get_password_hash` by accepting both a `plain_password` and a `hashed_password` and returning a boolean indicating whether they match, delegating the comparison entirely to `pwd_context.verify` [[target/app/services/security.py::verify_password]]. None of the three functions carry decorators, raise exceptions, or produce side effects [[target/app/services/security.py]].

## generate_salt

`generate_salt` is a small utility function that generates a new cryptographic salt and returns it as a plain string [[target/app/services/security.py::generate_salt]]. It takes no arguments [[target/app/services/security.py::generate_salt]]. Internally it calls `bcrypt.gensalt()` to produce the salt, then immediately calls `.decode()` on the result to convert the bytes value into a UTF-8 string before returning it [[target/app/services/security.py::generate_salt]]. The declared return type is `str` [[target/app/services/security.py::generate_salt]]. It carries no decorators, raises no exceptions, and has no dependencies beyond the `bcrypt` library [[target/app/services/security.py]].

## get_password_hash

`get_password_hash` is a small utility function that takes a single string argument `password` and returns a hashed string representation of it [[target/app/services/security.py::get_password_hash]]. It delegates entirely to `pwd_context.hash`, passing the plain-text password through and returning the result directly [[target/app/services/security.py::get_password_hash]]. The function is defined at the module level in [`target/app/services/security.py`](target/app/services/security.py) and carries no decorators, raises no exceptions of its own, and has no branching logic [[target/app/services/security.py]].

## verify_password

`verify_password` is a function that checks whether a plain-text password matches a previously hashed password, returning `True` if they match and `False` otherwise [[target/app/services/security.py::verify_password]]. It accepts two string arguments: `plain_password`, the raw password to check, and `hashed_password`, the stored hash to compare against [[target/app/services/security.py::verify_password]]. Internally, it delegates the comparison to `pwd_context.verify`, passing both values directly and returning its result without any additional logic [[target/app/services/security.py::verify_password]]. No decorators, exceptions, or side effects are present in this function [[target/app/services/security.py]].

