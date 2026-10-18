# tags

This module defines the tags route for the API, exporting a single `APIRouter` instance and one endpoint handler [[target/app/api/routes/tags.py]]. The sole function it defines, `get_all_tags`, is an asynchronous route handler registered on the router as a GET request that returns a response modelled as `TagsInList` under the name `tags:get-all` [[target/app/api/routes/tags.py::get_all_tags]]. It receives a `TagsRepository` instance through FastAPI's dependency injection system, which is resolved automatically at request time via `get_repository(TagsRepository)` [[target/app/api/routes/tags.py::get_all_tags]]. The handler delegates all data retrieval to that injected repository by calling its `get_all_tags()` method, then wraps the resulting collection in a `TagsInList` object before returning it to the caller [[target/app/api/routes/tags.py::get_all_tags]]. No additional logic, error handling, or decorators beyond the route registration itself are present in the module [[target/app/api/routes/tags.py]].

## get_all_tags

`get_all_tags` is an asynchronous route handler registered on the router as a GET request, returning a response modelled as `TagsInList` under the name `tags:get-all` [[target/app/api/routes/tags.py::get_all_tags]]. It accepts a single injected parameter, `tags_repo`, which is a `TagsRepository` instance supplied by FastAPI's dependency injection system via `get_repository(TagsRepository)` [[target/app/api/dependencies/database.py::get_repository]]. The function delegates to `tags_repo.get_all_tags()` to fetch all tags from the underlying data store, then wraps the result in a `TagsInList` object before returning it [[target/app/api/routes/tags.py::get_all_tags]]. No exceptions are explicitly raised within the function body, and no additional decorators beyond the route registration are present [[target/app/api/routes/tags.py]]. The route is served at `GET /api/tags` [[route:GET /api/tags]].

> **FastAPI deps:** get_repository

