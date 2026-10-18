# api

This module serves as the top-level assembly point for the articles section of the API, combining sub-routers from two sibling modules into a single unified router [[target/app/api/routes/articles/api.py]]. It creates a bare `APIRouter` instance and mounts both `articles_common.router` and `articles_resource.router` under the `/articles` prefix, so all article-related endpoints are grouped consistently [[target/app/api/routes/articles/api.py]]. The resulting `router` object is what higher-level application wiring will import to register every articles route in one step [[target/app/api/routes/articles/api.py]].

