# jwt

This module centralises all JWT-related logic for the application, providing token creation and decoding utilities built on the `HS256` algorithm with a fixed one-week expiry window [[target/app/services/jwt.py]].

`create_jwt_token` is the low-level building block: it takes an arbitrary payload dictionary, computes an expiry timestamp by adding the supplied `expires_delta` to the current UTC time, merges in a `JWTMeta` record carrying that expiry and the module-level `JWT_SUBJECT` constant, and returns the resulting signed JWT string [[target/app/services/jwt.py::create_jwt_token]].

`create_access_token_for_user` sits one level above it, accepting a `User` object and a `secret_key`, extracting the username into a `JWTUser` struct, and delegating to `create_jwt_token` with the serialised payload and an expiry window derived from `ACCESS_TOKEN_EXPIRE_MINUTES` [[target/app/services/jwt.py::create_access_token_for_user]]. It returns the final signed JWT string to the caller [[target/app/services/jwt.py::create_access_token_for_user]].

`get_username_from_token` handles the reverse direction: it decodes a JWT string with the provided `secret_key`, wraps the payload in a `JWTUser` model, and returns the `username` field [[target/app/services/jwt.py::get_username_from_token]]. Decode failures raise `ValueError("unable to decode JWT token")`, and payload validation failures raise `ValueError("malformed payload in token")`, ensuring callers receive a clear signal for either class of problem [[target/app/services/jwt.py::get_username_from_token]].

## create_access_token_for_user

Accepts a `User` object and a `secret_key` string, then constructs a JWT payload by extracting the username into a `JWTUser` struct and serialising it to a dictionary [[target/app/services/jwt.py::create_access_token_for_user]]. Delegates token generation to `create_jwt_token`, passing the serialised payload, the secret key, and an expiry window derived from `ACCESS_TOKEN_EXPIRE_MINUTES` via `timedelta` [[target/app/services/jwt.py::create_access_token_for_user]]. Returns the resulting signed JWT string [[target/app/services/jwt.py::create_access_token_for_user]].

## create_jwt_token

Copies the caller-supplied `jwt_content` dictionary, computes an expiry timestamp by adding `expires_delta` to the current UTC time, then merges in a `JWTMeta` record carrying that expiry and the module-level `JWT_SUBJECT` constant [[target/app/services/jwt.py::create_jwt_token]]. The augmented payload is signed and encoded into a JWT string using `secret_key` and the module-level `ALGORITHM` constant, and that string is returned [[target/app/services/jwt.py::create_jwt_token]].

## get_username_from_token

Decodes a JWT token using the provided `secret_key` with a fixed algorithm, wraps the payload in a `JWTUser` model, and returns the `username` field from that model [[target/app/services/jwt.py::get_username_from_token]]. If `jwt.decode` fails, it raises `ValueError("unable to decode JWT token")` [[target/app/services/jwt.py::get_username_from_token]]. If the decoded payload fails `JWTUser` validation, it raises `ValueError("malformed payload in token")` [[target/app/services/jwt.py::get_username_from_token]].

> **Raises:** ValueError

