# security

This module provides password-security utilities for the application, centralising all cryptographic operations in one place [[target/app/services/security.py]]. It initialises a `passlib` `CryptContext` configured to use the bcrypt hashing scheme, which the hashing and verification functions share [[target/app/services/security.py]].

`generate_salt` produces a fresh random cryptographic salt on each call by invoking `bcrypt.gensalt()` and decoding the raw bytes into a UTF-8 string before returning it [[target/app/services/security.py::generate_salt]]. `get_password_hash` accepts a plain-text password and returns a bcrypt hash of it by delegating to the shared `pwd_context.hash` [[target/app/services/security.py::get_password_hash]]. `verify_password` takes a plain-text password alongside its stored hash, calls `pwd_context.verify` to compare them, and returns `True` on a match or `False` otherwise [[target/app/services/security.py::verify_password]]. Together, `get_password_hash` and `verify_password` form a complementary pair for storing and later authenticating user credentials [[target/app/services/security.py::get_password_hash]] [[target/app/services/security.py::verify_password]].

## generate_salt

Generates a new random cryptographic salt string by calling `bcrypt.gensalt()` and decoding the resulting bytes to a UTF-8 string before returning it [[target/app/services/security.py::generate_salt]].

## get_password_hash

Accepts a plain-text password and returns its hashed equivalent by delegating to `pwd_context.hash` [[target/app/services/security.py::get_password_hash]].

## verify_password

Accepts a plain-text password and its hashed counterpart, delegates to `pwd_context.verify` to check whether they match, and returns `True` if they do or `False` otherwise [[target/app/services/security.py::verify_password]].

