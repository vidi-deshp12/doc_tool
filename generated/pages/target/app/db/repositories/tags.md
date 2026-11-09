# tags

This module defines the data-access layer for tag records in the application [[target/app/db/repositories/tags.py]]. It imports from the shared `queries` object and from `BaseRepository`, establishing the foundation for all database interaction [[target/app/db/repositories/tags.py]].

The single class it exports, `TagsRepository`, extends `BaseRepository` and is responsible for managing tag records in the database [[target/app/db/repositories/tags.py::TagsRepository]]. It exposes two asynchronous methods that together cover the two fundamental tag operations: writing new tags and reading all existing ones [[target/app/db/repositories/tags.py::TagsRepository]].

The first method, `create_tags_that_dont_exist`, accepts a sequence of tag strings and persists any that are not yet stored, delegating to `queries.create_new_tags` and passing the repository's active connection along with the tags reshaped into a list of `{"tag": tag}` dicts [[target/app/db/repositories/tags.py::TagsRepository::create_tags_that_dont_exist]]. It returns nothing, making it a pure write operation [[target/app/db/repositories/tags.py::TagsRepository::create_tags_that_dont_exist]].

The second method, `get_all_tags`, retrieves every tag from the database by calling `queries.get_all_tags` with the repository's active connection, then flattens the result by extracting the first element of each row and returning the whole set as a `List[str]` [[target/app/db/repositories/tags.py::TagsRepository::get_all_tags]]. Together, these two methods give callers everything they need to keep the tag table consistent and to enumerate its full contents [[target/app/db/repositories/tags.py::TagsRepository]].

## TagsRepository

`TagsRepository` is a database repository class that inherits from `BaseRepository` and is responsible for managing tag records in the database [[target/app/db/repositories/tags.py::TagsRepository]] [[target/app/db/repositories/base.py::BaseRepository]]. It is not a Pydantic model [[target/app/db/repositories/tags.py::TagsRepository]]. The class defines two asynchronous methods [[target/app/db/repositories/tags.py::TagsRepository]].

The first, `create_tags_that_dont_exist`, accepts a sequence of tag strings and persists any that do not yet exist by delegating to `queries.create_new_tags`, passing the repository's active connection alongside the tags mapped into a list of `{"tag": tag}` dicts [[target/app/db/repositories/tags.py::TagsRepository::create_tags_that_dont_exist]]. It returns nothing [[target/app/db/repositories/tags.py::TagsRepository::create_tags_that_dont_exist]].

The second, `get_all_tags`, queries the database for all tags by calling `queries.get_all_tags` with the repository's active connection [[target/app/db/repositories/tags.py::TagsRepository::get_all_tags]]. It returns a flat `List[str]` by extracting the first element from each row in the result set [[target/app/db/repositories/tags.py::TagsRepository::get_all_tags]].

### create_tags_that_dont_exist

Accepts a sequence of tag strings and persists any that do not yet exist by delegating to `queries.create_new_tags`, passing the repository's active connection alongside the tags mapped into a list of `{"tag": tag}` dicts [[target/app/db/repositories/tags.py::TagsRepository::create_tags_that_dont_exist]]. It is an `async` method on [`TagsRepository`](target/app/db/repositories/tags.py::TagsRepository) and returns nothing [[target/app/db/repositories/tags.py::TagsRepository::create_tags_that_dont_exist]].

### get_all_tags

Asynchronously queries the database for all tags by calling `queries.get_all_tags` with the repository's active connection [[target/app/db/repositories/tags.py::TagsRepository::get_all_tags]]. Returns a flat `List[str]` by extracting the first element from each row in the result set [[target/app/db/repositories/tags.py::TagsRepository::get_all_tags]].

