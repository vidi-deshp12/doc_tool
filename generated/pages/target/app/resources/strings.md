# strings

This module serves as a centralised registry of human-readable API error and status messages used throughout the application [[target/app/resources/strings.py]]. All entries are plain string constants, making it the single place to update user-facing text without touching business logic [[target/app/resources/strings.py]].

The constants fall into several thematic groups. A set of messages handles user and article existence checks, covering cases where a user or article cannot be found, where an article already exists, and where the requesting user is not the author of an article [[target/app/resources/strings.py]]. Authentication and registration errors are also represented, including a message for incorrect login credentials, and separate messages for a username or email that is already taken [[target/app/resources/strings.py]].

Follow and subscription actions have their own dedicated strings, distinguishing between attempting to follow oneself, attempting to unfollow oneself, trying to unfollow a user who is not yet followed, and trying to follow a user who is already followed [[target/app/resources/strings.py]]. Token validation is covered by two constants: one for an unsupported authorisation type prefix and one for a payload that cannot be validated [[target/app/resources/strings.py]].

Finally, the module includes messages for favouriting actions — signalling that an article is already favourited or that it has not been favourited — as well as a message for a comment that does not exist, and a general authentication-required notice [[target/app/resources/strings.py]].

