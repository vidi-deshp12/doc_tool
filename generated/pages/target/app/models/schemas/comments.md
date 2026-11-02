# comments

This module defines the Pydantic schemas used to validate and serialise comment data at the API boundary [[target/app/models/schemas/comments.py]]. All three classes inherit from `RWSchema`, which provides the shared base configuration and camelCase aliasing behaviour common to all schemas in the project [[target/app/models/schemas/comments.py::CommentInCreate]] [[target/app/models/schemas/comments.py::CommentInResponse]] [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]].

`CommentInCreate` represents the inbound payload for creating a new comment, exposing a single `body` field of type `str` that carries the comment's text content [[target/app/models/schemas/comments.py::CommentInCreate]]. On the response side, `CommentInResponse` wraps a single `Comment` domain object in a `comment` field, providing the schema for an API response that returns one comment [[target/app/models/schemas/comments.py::CommentInResponse]]. When multiple comments need to be returned, `ListOfCommentsInResponse` is used instead; it holds a `comments` field typed as `List[Comment]`, serialising the full collection to the caller [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. Together, the three schemas cover the complete lifecycle of comment data flowing in and out of the API [[target/app/models/schemas/comments.py]].

## CommentInCreate

`CommentInCreate` is a Pydantic model used to represent the data required when creating a new comment [[target/app/models/schemas/comments.py::CommentInCreate]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which serves as its base class. The model defines a single field, `body`, typed as `str`, which holds the text content of the comment being created [[target/app/models/schemas/comments.py::CommentInCreate]].

| Field | Type | Default |
|-------|------|---------|
| `body` | `str` |  |

## CommentInResponse

`CommentInResponse` is a Pydantic model defined in [`target/app/models/schemas/comments.py`](target/app/models/schemas/comments.py) that represents the schema for a single comment returned in an API response [[target/app/models/schemas/comments.py::CommentInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared base configuration for read/write schemas in this application [[target/app/models/schemas/comments.py::CommentInResponse]]. The model declares a single field, `comment`, typed as `Comment`, which holds the comment data to be serialised in the response body [[target/app/models/schemas/comments.py::CommentInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `comment` | `Comment` |  |

## ListOfCommentsInResponse

`ListOfCommentsInResponse` is a Pydantic model that represents the schema for returning a list of comments in an API response [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. It inherits from `RWSchema` [[target/app/models/schemas/rwschema.py::RWSchema]], which provides the shared configuration and aliasing behaviour common to all response schemas in this project [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]]. The class defines a single field, `comments`, typed as `List[Comment]`, which holds the collection of comment objects to be serialised and returned to the caller [[target/app/models/schemas/comments.py::ListOfCommentsInResponse]].

| Field | Type | Default |
|-------|------|---------|
| `comments` | `List[Comment]` |  |

