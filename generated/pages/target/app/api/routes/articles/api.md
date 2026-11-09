# api

This file serves as the top-level article routing aggregator for the API, combining two sub-routers into a single unified `APIRouter` instance [[target/app/api/routes/articles/api.py]]. It imports from both `articles_common` and `articles_resource` and mounts each under the `/articles` prefix, so all article-related endpoints are grouped together and exposed through one router [[target/app/api/routes/articles/api.py]]. The resulting `router` object is what gets registered elsewhere in the application to activate all article routes [[target/app/api/routes/articles/api.py]].

