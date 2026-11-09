# comments

This module is the data-access layer for comment persistence, importing the connection primitives, query catalogue, base repository infrastructure, and the domain models it needs to operate [[target/app/db/repositories/comments.py]].

Its sole export is `CommentsRepository`, a class that extends `BaseRepository` and centralises every database operation involving comments [[target/app/db/repositories/comments.py::CommentsRepository]]. During initialisation the class sets up the database connection through the parent and also constructs a `ProfilesRepository` instance that it keeps as an internal collaborator, allowing it to resolve author profiles whenever it needs to materialise a full domain object [[target/app/db/repositories/comments.py::CommentsRepository]].

The private helper `_get_comment_from_db_record` is the single point where a raw database row is converted into a `Comment` domain object: it reads the scalar fields directly from the record and then calls out asynchronously to the embedded `ProfilesRepository` to attach the author's profile, ensuring that follow-relationship state is always reflected correctly from the perspective of the requesting user [[target/app/db/repositories/comments.py::CommentsRepository]]. Every public method that must return a `Comment` routes through this helper, giving the class a consistent hydration path [[target/app/db/repositories/comments.py::CommentsRepository]].

The four public methods cover the full lifecycle of a comment. `create_comment_for_article` inserts a new row and immediately hydrates it into a domain object so the caller receives a complete result in one asynchronous step [[target/app/db/repositories/comments.py::CommentsRepository]]. `get_comment_by_id` looks up a single comment by its numeric identifier and the parent article slug, raising `EntityDoesNotExist` if no matching row is found [[target/app/db/repositories/comments.py::CommentsRepository]]. `get_comments_for_article` retrieves every comment attached to an article by slug, mapping each row through the shared helper [[target/app/db/repositories/comments.py::CommentsRepository]]. Finally, `delete_comment` permanently removes the row corresponding to a given `Comment` object [[target/app/db/repositories/comments.py::CommentsRepository]].

## CommentsRepository

`CommentsRepository` is a database repository class responsible for all comment-related persistence operations, extending `BaseRepository` [[target/app/db/repositories/comments.py::CommentsRepository]] [[target/app/db/repositories/base.py::BaseRepository]].

On initialisation, it delegates connection setup to the parent class and additionally creates a `ProfilesRepository` instance stored as `self._profiles_repo`, which is used internally to resolve comment author profiles [[target/app/db/repositories/comments.py::CommentsRepository::__init__]]. It is not a Pydantic model [[target/app/db/repositories/comments.py::CommentsRepository]].

The private helper `_get_comment_from_db_record` constructs a `Comment` domain object from a raw database row, reading `id`, `body`, `created_at`, and `updated_at` directly from that row, then asynchronously resolving the author's profile via `self._profiles_repo.get_profile_by_username` so that follow relationships are correctly reflected from the requesting user's perspective [[target/app/db/repositories/comments.py::CommentsRepository::_get_comment_from_db_record]].

New comments are persisted by `create_comment_for_article`, which writes the row to the database and immediately hydrates it into a full `Comment` domain object through `_get_comment_from_db_record`, making the entire operation fully asynchronous [[target/app/db/repositories/comments.py::CommentsRepository::create_comment_for_article]]. A single comment can be retrieved by its numeric ID and parent article slug using `get_comment_by_id`, which raises `EntityDoesNotExist` when no matching row is found [[target/app/db/repositories/comments.py::CommentsRepository::get_comment_by_id]]. All comments belonging to an article can be fetched at once through `get_comments_for_article`, which queries by slug and maps each returned row to a domain object via the same helper [[target/app/db/repositories/comments.py::CommentsRepository::get_comments_for_article]]. Finally, `delete_comment` permanently removes a comment from the database given a `Comment` object as its target [[target/app/db/repositories/comments.py::CommentsRepository::delete_comment]].

### __init__

Initialises the repository by delegating connection setup to the parent class via `super().__init__(conn)`, then creates a `ProfilesRepository` instance with the same connection and stores it as `self._profiles_repo` for use by comment-related operations [[target/app/db/repositories/comments.py::CommentsRepository::__init__]].

### _get_comment_from_db_record

Constructs and returns a `Comment` domain object from a raw database record and a resolved author profile [[target/app/db/repositories/comments.py::CommentsRepository::_get_comment_from_db_record]]. It reads `id`, `body`, `created_at`, and `updated_at` directly from the `comment_row` record [[target/app/db/repositories/comments.py::CommentsRepository::_get_comment_from_db_record]]. The author profile is resolved asynchronously by delegating to `self._profiles_repo.get_profile_by_username`, passing `author_username` and `requested_user` so that the returned profile reflects the perspective of the requesting user (e.g. whether they follow the author) [[target/app/db/repositories/comments.py::CommentsRepository::_get_comment_from_db_record]].

### create_comment_for_article

Inserts a new comment row into the database by delegating to `queries.create_new_comment` with the connection, the comment body, the article's slug, and the author's username [[target/app/db/repositories/comments.py::CommentsRepository::create_comment_for_article]]. The resulting row is then hydrated into a full `Comment` domain object via `self._get_comment_from_db_record`, passing the raw row, the author username extracted from that row, and the requesting user [[target/app/db/repositories/comments.py::CommentsRepository::create_comment_for_article]]. Both calls are awaited, making the method fully asynchronous from database write through to domain-model construction [[target/app/db/repositories/comments.py::CommentsRepository]].

### delete_comment

Permanently removes a comment from the database by delegating to `queries.delete_comment_by_id` with the repository's active connection, the comment's `id_`, and its author's username [[target/app/db/repositories/comments.py::CommentsRepository::delete_comment]]. It is a method of `CommentsRepository` and accepts a single keyword-only `Comment` object as its target [[target/app/db/repositories/comments.py::CommentsRepository]].

### get_comment_by_id

Fetches a single comment by its numeric ID and the parent article, executing the database lookup via `queries.get_comment_by_id_and_slug` using the article's slug [[target/app/db/repositories/comments.py::CommentsRepository::get_comment_by_id]]. When a matching row is found, it delegates construction of the domain object to `self._get_comment_from_db_record`, passing the raw row, the author's username, and the optionally supplied requesting user [[target/app/db/repositories/comments.py::CommentsRepository::get_comment_by_id]]. If no row is returned, it raises `EntityDoesNotExist` with a message that includes the missing `comment_id` [[target/app/db/errors.py::EntityDoesNotExist]].

> **Raises:** EntityDoesNotExist

### get_comments_for_article

Retrieves all comments for the given article by querying the database using the article's slug [[target/app/db/repositories/comments.py::CommentsRepository::get_comments_for_article]]. For each returned row, it delegates to `_get_comment_from_db_record`, passing the row, the row's `author_username`, and the optional `user` as the requesting user, then collects the results into the returned list [[target/app/db/repositories/comments.py::CommentsRepository::get_comments_for_article]].

