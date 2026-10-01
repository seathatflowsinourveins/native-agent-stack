"""Credential-source selection and the Alpaca paper-only guard, shared by
`runner.py` and `market_research.py`.

Two explicit sources, chosen with `--credentials`:

  - `env-file` (the default, unchanged): the private `0600` file named by
    `--env-file`, read only through `credential_guard.open_verified()` by each
    loader's own `credentials(path)`.
  - `keychain-env`: `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` as injected
    into this one process by `secret run APCA_API_KEY_ID APCA_API_SECRET_KEY
    -- CMD` (macOS login Keychain; `secret` exports the two names and `exec`s
    CMD, so only that command and its children receive them). Both names are
    removed from this process's environment as soon as they are read, so a
    child this process starts later does not inherit them.

Both sources are paper-only. The base URL is pinned to `PAPER_BASE_URL`; an
`APCA_API_BASE_URL` in the process environment (either source) or in the env
file (`env-file`) that is anything other than that exact URL (an optional
trailing `/` aside) is refused before any broker request: the live trading
host with `REASON_LIVE_HOST`, every other value with `REASON_NOT_PAPER`.

Every refusal is one of the fixed `REASON_*` codes below. None carries a
value, a path, a host name or upstream exception text, and none is raised
from inside an `except` block, so no original exception is attached as
`__context__` (see `credential_guard`'s module docstring for why `from None`
alone is not enough).

What `keychain-env` cannot tell: whether a value is a paper key rather than a
live key (the paper pin makes a live key fail authentication at the paper
host instead of trading live), and where a value came from when the tool
that loaded it leaves no trace. It refuses the case it can see: an env-file
loader that records, in the environment it hands down, which file (or
directory holding one) it applied (`ENV_FILE_LOADER_MARKERS`), when that
location is inside a Git worktree (a `.git` entry, directory or file, at the
location or any ancestor). `set -a; . ./.env`, `env $(cat .env)`,
`uv run --env-file` given as a flag, `docker run --env-file`, mise's
`[env] _.file` and a dotenv loader inside a wrapper script leave no such
marker and are not detected.

Stdlib only (`os`, `urllib.parse`), so importing it adds nothing to either
caller's import graph.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_TRADING_HOST = "api.alpaca.markets"

KEY_ID_VARIABLE = "APCA_API_KEY_ID"
SECRET_KEY_VARIABLE = "APCA_API_SECRET_KEY"
BASE_URL_VARIABLE = "APCA_API_BASE_URL"

SOURCE_ENV_FILE = "env-file"
SOURCE_KEYCHAIN_ENV = "keychain-env"
SOURCES = (SOURCE_ENV_FILE, SOURCE_KEYCHAIN_ENV)

REASON_LIVE_HOST = "alpaca_paper_only:live_host"
REASON_NOT_PAPER = "alpaca_paper_only:not_paper_host"
REASON_ENV_MISSING = "keychain_env:missing"
REASON_ENV_PARTIAL = "keychain_env:partial"
REASON_ENV_EMPTY = "keychain_env:empty"
REASON_ENV_INVALID = "keychain_env:invalid_value"
REASON_ENV_WORKTREE = "keychain_env:worktree"
REASON_UNKNOWN_SOURCE = "credential_source:unknown"

# An Alpaca key id or secret is a short printable-ASCII token; anything longer
# than this is not one.
MAX_VALUE_CHARS = 256

# Environment variables through which an env-file loader names the file (or
# the directory holding it) it applied to the environment it hands down.
# DIRENV_DIR's value carries a leading "-"; UV_ENV_FILE may name several
# whitespace-separated files. Only these names are read; a named location is
# checked for a `.git` ancestor and never opened.
ENV_FILE_LOADER_MARKERS = ("DIRENV_FILE", "DIRENV_DIR", "UV_ENV_FILE", "PIPENV_DOTENV_LOCATION",
                           "MISE_ENV_FILE")


class CredentialSourceError(RuntimeError):
    """A credential source was refused. The message is always one of the
    fixed `REASON_*` codes above, never a value or a path."""


def paper_base_url_reason(value):
    """`None` when `value` is absent (`None`) or exactly `PAPER_BASE_URL`
    (an optional trailing `/` aside); otherwise the fixed reason code."""
    if value is None:
        return None
    if isinstance(value, str) and value.rstrip("/") == PAPER_BASE_URL:
        return None
    return REASON_LIVE_HOST if _hostname(value) == LIVE_TRADING_HOST else REASON_NOT_PAPER


def require_paper_base_url(value):
    reason = paper_base_url_reason(value)
    if reason is not None:
        raise CredentialSourceError(reason)


def _hostname(value):
    """Lower-cased host of `value`, or `None` when it has none or cannot be
    parsed. The parse error is dropped here, never re-raised."""
    if not isinstance(value, str):
        return None
    try:
        return urlsplit(value.strip()).hostname
    except ValueError:
        return None


def selection_error(source, env_file):
    """The argparse message for an inconsistent `--credentials`/`--env-file`
    pair, or `None`. Carries no value and no path."""
    if source == SOURCE_ENV_FILE and env_file is None:
        return "--credentials env-file (the default) requires --env-file"
    if source == SOURCE_KEYCHAIN_ENV and env_file is not None:
        return "--env-file cannot be combined with --credentials keychain-env"
    return None


def _value_reason(value):
    if not value:
        return REASON_ENV_EMPTY
    if (len(value) > MAX_VALUE_CHARS or not value.isascii() or not value.isprintable()
            or any(character.isspace() for character in value)):
        return REASON_ENV_INVALID
    return None


def _has_git_ancestor(location):
    """True when `location` or any ancestor holds a `.git` entry. A missing
    entry (or a non-directory component) means no; any other failure to
    look (permission, loop, ...) fails closed as yes."""
    current = location
    while True:
        try:
            os.lstat(os.path.join(current, ".git"))
            return True
        except (FileNotFoundError, NotADirectoryError):
            pass
        except (OSError, ValueError):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def _marker_locations(environ):
    for name in ENV_FILE_LOADER_MARKERS:
        value = environ.get(name)
        if not value:
            continue
        if name == "DIRENV_DIR":
            value = value.removeprefix("-")
        tokens = value.split() if name == "UV_ENV_FILE" else []
        for location in (value, *tokens):
            if location:
                yield location


def _worktree_marker_reason(environ, cwd):
    for location in _marker_locations(environ):
        if not os.path.isabs(location):
            if cwd is None:
                try:
                    cwd = os.getcwd()
                except OSError:
                    return REASON_ENV_WORKTREE
            location = os.path.join(cwd, location)
        try:
            candidates = (os.path.abspath(location), os.path.realpath(location))
        except (OSError, ValueError):
            return REASON_ENV_WORKTREE
        if any(_has_git_ancestor(candidate) for candidate in candidates):
            return REASON_ENV_WORKTREE
    return None


def keychain_env_credentials(environ=None, *, cwd=None):
    """Return `(key_id, secret_key)` from the process environment `secret
    run` populated, after removing both names from it.

    Refused, in this order: a non-paper `APCA_API_BASE_URL`; neither name set
    (`missing`); only one set (`partial`); either set but empty (`empty`);
    either not a single printable-ASCII token of at most `MAX_VALUE_CHARS`
    characters (`invalid_value`); an env-file loader marker naming a location
    inside a Git worktree (`worktree`). `environ` defaults to `os.environ`
    and `cwd` (used only to resolve a relative marker) to the current
    directory."""
    environ = os.environ if environ is None else environ
    key = environ.pop(KEY_ID_VARIABLE, None)
    secret = environ.pop(SECRET_KEY_VARIABLE, None)
    reason = paper_base_url_reason(environ.get(BASE_URL_VARIABLE))
    if reason is None and key is None and secret is None:
        reason = REASON_ENV_MISSING
    if reason is None and (key is None or secret is None):
        reason = REASON_ENV_PARTIAL
    if reason is None:
        reason = _value_reason(key) or _value_reason(secret)
    if reason is None:
        reason = _worktree_marker_reason(environ, cwd)
    if reason is not None:
        raise CredentialSourceError(reason)
    return key, secret


def select_credentials(source, env_file, *, env_file_loader, environ=None, cwd=None):
    """Return `(key_id, secret_key)` from the selected source, paper-only
    either way. `env_file_loader(path)` is the caller's own guarded env-file
    loader; it enforces the file's `APCA_API_BASE_URL` itself, and its own
    exceptions pass through unchanged. Every refusal made here is a
    `CredentialSourceError`."""
    environ = os.environ if environ is None else environ
    if source == SOURCE_KEYCHAIN_ENV:
        return keychain_env_credentials(environ, cwd=cwd)
    if source != SOURCE_ENV_FILE:
        raise CredentialSourceError(REASON_UNKNOWN_SOURCE)
    require_paper_base_url(environ.get(BASE_URL_VARIABLE))
    return env_file_loader(env_file)
