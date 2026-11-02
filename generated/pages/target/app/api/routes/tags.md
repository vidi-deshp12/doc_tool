# tags

The module [`target/app/api/routes/tags.py`](target/app/api/routes/tags.py) is a FastAPI router file responsible for exposing tag-related HTTP endpoints [[target/app/api/routes/tags.py]]. It defines a single `APIRouter` instance and registers one route handler on it [[target/app/api/routes/tags.py]].

The only function defined in this module is [`get_all_tags`](target/app/api/routes/tags.py::get_all_tags), an asynchronous route handler bound to `GET /api/tags` [[target/app/api/routes/tags.py::get_all_tags]]. It receives a `TagsRepository` instance through FastAPI's dependency injection mechanism, delegating the database wiring to `get_repository(TagsRepository)` so the handler itself never constructs its own database connection [[target/app/api/routes/tags.py::get_all_tags]]. The handler awaits `tags_repo.get_all_tags()` to fetch all tags from the data store, then wraps the result in a `TagsInList` instance which is both the return value and the declared response model governing JSON serialisation [[target/app/api/routes/tags.py::get_all_tags]]. No authentication or authorisation decorators are applied, meaning the endpoint is publicly accessible as written, and no exceptions are explicitly raised within the function body [[target/app/api/routes/tags.py]].

## get_all_tags

`get_all_tags` is an asynchronous route handler registered on `GET /api/tags` [[target/app/api/routes/tags.py::get_all_tags]] [[route:GET /api/tags]]. It accepts a single injected parameter, `tags_repo`, which is a `TagsRepository` instance provided by FastAPI's dependency injection system via `get_repository(TagsRepository)` [[target/app/api/dependencies/database.py::get_repository]]. The function awaits a call to `tags_repo.get_all_tags()` to retrieve all tags from the underlying data store, then wraps the result in a `TagsInList` instance before returning it [[target/app/api/routes/tags.py::get_all_tags]]. The declared response model is `TagsInList`, which governs how the JSON response is serialised for the caller [[target/app/models/schemas/tags.py::TagsInList]]. No exceptions are explicitly raised within the function body, and no authorization decorators are present [[target/app/api/routes/tags.py]].

> **FastAPI deps:** get_repository

