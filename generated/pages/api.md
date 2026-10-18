# API Endpoints

<!-- Request model column is blank when the handler body-parameter annotation
     could not be resolved to an in-repo Pydantic model (known gap). -->

| Method | Path | Status | Handler | FastAPI Deps | Request model | Response models |
|--------|------|--------|---------|--------------|---------------|-----------------|
| GET | `/api/articles` | 200 | [list_articles](target/app/api/routes/articles/articles_resource.md) | get_articles_filters, get_current_user_authorizer, get_repository |  | ListOfArticlesInResponse |
| POST | `/api/articles` | 201 | [create_new_article](target/app/api/routes/articles/articles_resource.md) | get_current_user_authorizer, get_repository | ArticleInCreate | ArticleInResponse |
| GET | `/api/articles/feed` | 200 | [get_articles_for_user_feed](target/app/api/routes/articles/articles_common.md) | get_current_user_authorizer, get_repository |  | ListOfArticlesInResponse |
| DELETE | `/api/articles/{slug}` | 204 | [delete_article_by_slug](target/app/api/routes/articles/articles_resource.md) | check_article_modification_permissions, get_article_by_slug_from_path, get_repository |  |  |
| GET | `/api/articles/{slug}` | 200 | [retrieve_article_by_slug](target/app/api/routes/articles/articles_resource.md) | get_article_by_slug_from_path |  | ArticleInResponse |
| PUT | `/api/articles/{slug}` | 200 | [update_article_by_slug](target/app/api/routes/articles/articles_resource.md) | check_article_modification_permissions, get_article_by_slug_from_path, get_repository | ArticleInUpdate | ArticleInResponse |
| GET | `/api/articles/{slug}/comments` | 200 | [list_comments_for_article](target/app/api/routes/comments.md) | get_article_by_slug_from_path, get_current_user_authorizer, get_repository |  | ListOfCommentsInResponse |
| POST | `/api/articles/{slug}/comments` | 201 | [create_comment_for_article](target/app/api/routes/comments.md) | get_article_by_slug_from_path, get_current_user_authorizer, get_repository | CommentInCreate | CommentInResponse |
| DELETE | `/api/articles/{slug}/comments/{comment_id}` | 204 | [delete_comment_from_article](target/app/api/routes/comments.md) | check_comment_modification_permissions, get_comment_by_id_from_path, get_repository |  |  |
| DELETE | `/api/articles/{slug}/favorite` | 200 | [remove_article_from_favorites](target/app/api/routes/articles/articles_common.md) | get_article_by_slug_from_path, get_current_user_authorizer, get_repository |  | ArticleInResponse |
| POST | `/api/articles/{slug}/favorite` | 200 | [mark_article_as_favorite](target/app/api/routes/articles/articles_common.md) | get_article_by_slug_from_path, get_current_user_authorizer, get_repository |  | ArticleInResponse |
| GET | `/api/profiles/{username}` | 200 | [retrieve_profile_by_username](target/app/api/routes/profiles.md) | get_profile_by_username_from_path |  | ProfileInResponse |
| DELETE | `/api/profiles/{username}/follow` | 200 | [unsubscribe_from_user](target/app/api/routes/profiles.md) | get_current_user_authorizer, get_repository, get_profile_by_username_from_path |  | ProfileInResponse |
| POST | `/api/profiles/{username}/follow` | 200 | [follow_for_user](target/app/api/routes/profiles.md) | get_current_user_authorizer, get_repository, get_profile_by_username_from_path |  | ProfileInResponse |
| GET | `/api/tags` | 200 | [get_all_tags](target/app/api/routes/tags.md) | get_repository |  | TagsInList |
| GET | `/api/user` | 200 | [retrieve_current_user](target/app/api/routes/users.md) | get_current_user_authorizer, get_app_settings |  | UserInResponse |
| PUT | `/api/user` | 200 | [update_current_user](target/app/api/routes/users.md) | get_current_user_authorizer, get_repository, get_app_settings | UserInUpdate | UserInResponse |
| POST | `/api/users` | 201 | [register](target/app/api/routes/authentication.md) | get_repository, get_app_settings | UserInCreate | UserInResponse |
| POST | `/api/users/login` | 200 | [login](target/app/api/routes/authentication.md) | get_repository, get_app_settings | UserInLogin | UserInResponse |
