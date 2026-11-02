# api

This module serves as the top-level assembly point for the articles section of the API, creating a single `APIRouter` instance and mounting two sub-routers under the `/articles` URL prefix [[target/app/api/routes/articles/api.py]]. It imports `articles_common` and `articles_resource` from the same package and delegates their routes into the combined router, meaning all article-related endpoints — both shared/common logic and resource-specific operations — are unified here before being registered with the broader application [[target/app/api/routes/articles/api.py]].

