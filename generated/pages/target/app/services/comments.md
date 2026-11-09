# comments

This module provides authorization logic for comment operations, importing the `Comment` and `User` domain models to support its work [[target/app/services/comments.py]]. It exposes a single function, `check_user_can_modify_comment`, which accepts a `Comment` and a `User` and returns `True` only when the comment's author username matches the given user's username, enforcing the rule that a user may only modify their own comments [[target/app/services/comments.py::check_user_can_modify_comment]].

## check_user_can_modify_comment

Accepts a `Comment` and a `User` and returns `True` only when the comment's author username matches the given user's username, effectively enforcing that a user may only modify their own comments [[target/app/services/comments.py::check_user_can_modify_comment]].

