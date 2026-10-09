"""Shared page text projection from the native portable recipe.

Reference implementation: tools/north-star/build_readiness.py render.portable
at 164c071fec2e78d738746b73c4c4768e83cf1c62, lines 364-375. The native
home/UUID/task substitutions and recursive value semantics are retained here
because that nested helper is not an importable API. No native reader is loaded.
Account filtering comes from tools/local-pages/build_pages.py ACCOUNT_URL at
the same pin; urllib.parse supplies host/path normalization for owner links.
"""

import re
from typing import Any
from urllib.parse import unquote, urlsplit


ACCOUNT_URL = re.compile(r"https?://(?:claude\.ai/artifact|chatgpt\.com/|chat\.openai\.com/)[^\s<>\"']*", re.I)
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)


def is_account_url(value: Any) -> bool:
    """Classify the existing account-artifact scope using parsed URLs."""
    if not isinstance(value, str):
        return False
    if ACCOUNT_URL.search(value):
        return True
    try:
        parsed = urlsplit(value)
        host = unquote(parsed.hostname or "").lower()
        path = unquote(parsed.path).lower()
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and (host in {"chatgpt.com", "chat.openai.com"} or host == "claude.ai" and path.startswith("/artifact"))


def sanitize(value: Any) -> Any:
    """Project source values without changing the input or reading any files."""
    if isinstance(value, str):
        value = re.sub(r"/home/[^/\s\"'<>]+|/Users/[^/\s\"'<>]+", "${USER_HOME}", value)
        value = re.sub(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", "${LOCAL_SESSION_ID}", value, flags=re.IGNORECASE)
        value = re.sub(r"task-[a-z0-9]{8}-[a-z0-9]{6}", "${LOCAL_TASK_HANDLE}", value, flags=re.IGNORECASE)
        value = ACCOUNT_URL.sub("[account artifact omitted]", value)
        return _URL.sub(lambda match: "[account artifact omitted]" if is_account_url(match.group()) else match.group(), value)
    if isinstance(value, dict):
        return {key: sanitize(child) for key, child in value.items()}
    if isinstance(value, list):
        return [sanitize(child) for child in value]
    return value


def text(value: Any) -> str:
    """Normalize a page label after applying the shared source projection."""
    return sanitize(str(sanitize(value) if value is not None else "Unspecified in source"))
