# strings

This module is a central registry of human-readable API error and status messages used throughout the application [[target/app/resources/strings.py]]. It defines a flat collection of string constants, each assigned a short English phrase that describes a specific error condition or constraint violation [[target/app/resources/strings.py]].

The constants cover four broad concerns. First, resource existence checks: whether a user, article, or comment can be found at all [[target/app/resources/strings.py]]. Second, ownership and permission guards: confirming that the requesting user is actually the author of an article before allowing a mutation [[target/app/resources/strings.py]]. Third, account and authentication errors: bad login credentials, a username or email already taken, a missing or malformed token, and a token with an unrecognised prefix [[target/app/resources/strings.py]]. Fourth, social-graph constraints: preventing a user from following or unfollowing themselves, signalling when a follow relationship does not yet exist or already does, and similarly tracking whether an article has already been favourited [[target/app/resources/strings.py]].

Because all message text lives in one place, any part of the codebase that needs to return an error to a client can import a constant from here rather than spelling out the phrase inline, keeping the wording consistent across the API [[target/app/resources/strings.py]].

