# tags

This module defines the tags route for the API, creating a FastAPI `APIRouter` and registering a single endpoint on it [[target/app/api/routes/tags.py]]. It exposes a `get_all_tags` handler that responds to `GET /api/tags` requests, using FastAPI's dependency injection to receive a `TagsRepository` [[target/app/api/routes/tags.py::get_all_tags]]. The handler retrieves every tag from the database and returns the results wrapped in a `TagsInList` response object [[target/app/api/routes/tags.py::get_all_tags]].

## get_all_tags

Handles `GET /api/tags` requests, injecting a `TagsRepository` via FastAPI's dependency system [[target/app/api/routes/tags.py::get_all_tags]] [[target/app/api/dependencies/database.py::get_repository]]. It fetches all tags from the database through `tags_repo.get_all_tags()` and wraps the result in a `TagsInList` response [[target/app/api/routes/tags.py::get_all_tags]] [[target/app/models/schemas/tags.py::TagsInList]].

> **FastAPI deps:** get_repository

