# security

This module is a focused security utility layer responsible for password hashing and verification [[target/app/services/security.py]]. It configures a shared `pwd_context` using `passlib`'s `CryptContext` with bcrypt as the hashing scheme, and all three of its functions delegate their core cryptographic work to either that context or the `bcrypt` library directly [[target/app/services/security.py]].

`generate_salt` produces a fresh cryptographic salt as a plain UTF-8 string by calling `bcrypt.gensalt()` and decoding the resulting bytes [[target/app/services/security.py::generate_salt]]. It takes no arguments and has no side effects, making it a simple, self-contained utility [[target/app/services/security.py::generate_salt]].

`get_password_hash` accepts a plain-text password string and returns its hashed form by forwarding the work entirely to `pwd_context.hash` [[target/app/services/security.py::get_password_hash]]. It contains no branching logic and raises no exceptions of its own, acting as a thin wrapper around the configured context [[target/app/services/security.py::get_password_hash]].

`verify_password` takes a plain-text password and a stored hash, and returns a boolean indicating whether they match, delegating entirely to `pwd_context.verify` for the comparison [[target/app/services/security.py::verify_password]]. Like its siblings, it introduces no additional logic or exception handling beyond what the underlying context provides [[target/app/services/security.py::verify_password]].

Together, the three functions form a cohesive, thin abstraction over `bcrypt` and `passlib`, keeping all cryptographic policy in one place through the shared `pwd_context` [[target/app/services/security.py]].

## generate_salt

`generate_salt` is a small utility function that produces a new cryptographic salt as a plain string [[target/app/services/security.py::generate_salt]]. It takes no arguments and returns a `str` [[target/app/services/security.py::generate_salt]]. Internally it delegates to `bcrypt.gensalt` to generate the salt, then calls `.decode()` on the result to convert the raw bytes into a UTF-8 string before returning it [[target/app/services/security.py::generate_salt]]. No exceptions are declared, no decorators are applied, and the function carries no side effects [[target/app/services/security.py::generate_salt]].

## get_password_hash

`get_password_hash` is a small utility function that accepts a single argument, `password` (a plain-text string), and returns its hashed equivalent as a string [[target/app/services/security.py::get_password_hash]]. It delegates the hashing work entirely to `pwd_context.hash`, which performs the actual cryptographic transformation [[target/app/services/security.py::get_password_hash]]. The function has no decorators, raises no exceptions of its own, and contains no branching logic — it is a thin, single-purpose wrapper around the configured password context [[target/app/services/security.py]].

## verify_password

`verify_password` is a small security utility that checks whether a plain-text password matches a previously hashed one [[target/app/services/security.py::verify_password]]. It accepts two string parameters — `plain_password`, the raw password to test, and `hashed_password`, the stored hash to compare against — and returns a `bool` indicating whether they match [[target/app/services/security.py::verify_password]]. Internally it delegates entirely to `pwd_context.verify`, passing both strings through to that method, so the hashing algorithm and verification logic are governed by whatever `pwd_context` is configured with in the module [[target/app/services/security.py]]. The function raises no exceptions of its own and has no decorators [[target/app/services/security.py::verify_password]].

