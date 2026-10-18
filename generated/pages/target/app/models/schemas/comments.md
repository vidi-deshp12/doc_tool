# comments

This module defines the Pydantic schemas used for serialising and deserialising comment data at the API boundary [[target/app/models/schemas/comments.py]]. All three classes inherit from `RWSchema`, which supplies the shared configuration and field-aliasing behaviour common across the application's request and response schemas [[target/app/models/schemas/comments.py::CommentInCreate]] [[target/app/models/schemas/comments.py::CommentInResponse]] [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]].

`CommentInCreate` represents the payload sent when creating a comment, exposing a single `body` field typed as `str` to carry the comment's text content [[target/app/models/schemas/comments.py::CommentInCreate]]. On the response side, `CommentInResponse` wraps a single `Comment` domain object in a `comment` field, forming the envelope returned when the API responds with one comment [[target/app/models/schemas/comments.py::CommentInResponse]]. When the API needs to return multiple comments at once, `ListOfCommentsInResponse` serves as the corresponding envelope, holding a `comments` field typed as `List[Comment]` [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. Together, the three schemas cover the full set of comment-related data shapes — creation input, single-item response, and multi-item response — that the API layer requires [[target/app/models/schemas/comments.py]].

## CommentInCreate

`CommentInCreate` is a Pydantic model defined in the comments schema module [[target/app/models/schemas/comments.py]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared configuration and aliasing behaviour common to all request/response schemas in this codebase. The class itself declares a single field, `body`, typed as a plain `str`, representing the text content of a comment being created [[target/app/models/schemas/comments.py::CommentInCreate]].

| Field | Type | Default |
|-------|------|---------|
| `body` | `str` |  |

## CommentInResponse

`CommentInResponse` is a Pydantic model defined in the comments schema module [[target/app/models/schemas/comments.py]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides shared schema behaviour across the application. The class declares a single field, `comment`, typed as `Comment`, representing a comment object to be returned in an API response [[target/app/models/schemas/comments.py::CommentInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `comment` | `Comment` |  |

## ListOfCommentsInResponse

`ListOfCommentsInResponse` is a Pydantic model that serves as the response envelope for a collection of comments [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared base configuration for response and request schemas in this project. The class declares a single field, `comments`, typed as `List[Comment]`, which holds the list of comment objects to be returned in the response [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. No additional fields or overrides are defined beyond this inherited base [[target/app/models/schemas/comments.py]].

| Field | Type | Default |
|-------|------|---------|
| `comments` | `List[Comment]` |  |

