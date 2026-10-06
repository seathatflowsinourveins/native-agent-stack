"""Public fragment identifiers from Microsoft's supported UUIDv5 recipe.

Ported from nativestack-practice@a7b8018524575cabbd979e6f2e1c84ee6e94700f:
checks/check-terminal-profiles.py:39–44. Official recipe:
https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions
(last updated2025-11-12; checked2026-10-06).
The namespace is a public platform constant, not a client/session identifier.
"""
import uuid

FRAGMENT_NAMESPACE = uuid.UUID(hex="f65ddb7e706b44998a5040313caf510a")
FRAGMENT_FOLDER = "NativeStack"


def derived_guid(folder: str, name: str) -> str:
    application = uuid.uuid5(FRAGMENT_NAMESPACE, folder.encode("UTF-16LE").decode("ASCII"))
    return "{" + str(uuid.uuid5(application, name.encode("UTF-16LE").decode("ASCII"))) + "}"
