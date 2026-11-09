# comments

This module defines the Pydantic request and response schemas for comment-related API operations [[target/app/models/schemas/comments.py]]. It imports `Comment` from the domain layer and `RWSchema` as the shared base, then builds three schema classes on top of them [[target/app/models/schemas/comments.py]].

`CommentInCreate` handles the input side: it validates the payload when a new comment is submitted, exposing a single `body` field of type `str` that holds the comment text [[target/app/models/schemas/comments.py::CommentInCreate]]. On the output side, `CommentInResponse` wraps a single `Comment` domain object in a `comment` field, forming the envelope returned by the API for a single-comment response [[target/app/models/schemas/comments.py::CommentInResponse]]. When multiple comments must be returned, `ListOfCommentsInResponse` takes over, holding a `List[Comment]` under a `comments` field [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. All three classes inherit from `RWSchema`, which supplies the shared serialisation configuration common to every request and response schema in the application [[target/app/models/schemas/comments.py::CommentInCreate]] [[target/app/models/schemas/comments.py::CommentInResponse]] [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]].

## CommentInCreate

`CommentInCreate` is a Pydantic model responsible for validating the input payload when a new comment is created [[target/app/models/schemas/comments.py::CommentInCreate]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared base configuration for request/response schemas in this application [[target/app/models/schemas/comments.py::CommentInCreate]]. The model declares a single field, `body`, typed as `str`, which holds the text content of the comment being submitted [[target/app/models/schemas/comments.py::CommentInCreate]].

| Field | Type | Default |
|-------|------|---------|
| `body` | `str` |  |

## CommentInResponse

`CommentInResponse` is a Pydantic model defined in [`target/app/models/schemas/comments.py`](target/app/models/schemas/comments.py) that represents the schema for a single comment returned in an API response [[target/app/models/schemas/comments.py::CommentInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared base configuration for request/response schemas in this project [[target/app/models/schemas/comments.py::CommentInResponse]]. The class declares a single field, `comment`, typed as `Comment`, which holds the comment object to be wrapped and returned [[target/app/models/schemas/comments.py::CommentInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `comment` | `Comment` |  |

## ListOfCommentsInResponse

`ListOfCommentsInResponse` is a Pydantic model defined in the comments schema module that serves as a response envelope for returning multiple comments [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared serialisation behaviour common to response and request schemas in this codebase [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. The model declares a single field, `comments`, typed as `List[Comment]`, which holds the collection of comment objects to be returned in a response [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `comments` | `List[Comment]` |  |

