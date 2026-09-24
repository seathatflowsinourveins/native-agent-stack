"""Shared fail-closed guard for an Alpaca paper-credential env file.

Both `runner.credentials()` and `market_research.credentials()` call
`open_verified()` before any line of the file is read, so the ownership,
permission, and Git-worktree-location rules cannot drift between the two
loaders. This module never returns file content and never raises an error
that includes file content -- only path-shaped and stat-shaped facts.

Only stdlib imports (`os`, `stat`, `pathlib`) so importing it never pulls
heavier modules (sqlite3, fcntl, threading, ...) into either caller.

TOCTOU: the pre-open `lstat` (identity, type, symlink-ness) is re-checked
against an `fstat` of the file actually opened, the way
`tools/credentials/alpaca_rate_limit_probe.py:read_env_file` does, so a swap
between the check and the read cannot substitute a different file. The open
itself uses O_NONBLOCK so a FIFO placed at the path can never hang the
caller -- and in the normal case a FIFO is already refused by the pre-open
`lstat` regular-file check before `open()` is ever reached.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path


class CredentialGuardError(RuntimeError):
    """A guard rule refused the credential path. The message never contains
    file content -- only the path's own name, where relevant."""


def inside_git_worktree(path: Path) -> bool:
    """Walk parents for a `.git` entry (directory in a normal clone, file in
    a linked worktree). `path` should already be fully resolved so a symlinked
    parent directory cannot hide the real location."""
    current = path.parent
    while True:
        if (current / ".git").exists() or (current / ".git").is_symlink():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def open_verified(path, *, follow_symlinks: bool):
    """Verify every fail-closed rule and return an open, read-only binary
    file object for `path`; the caller owns it and must close it (a `with`
    block is the usual way).

    Rules, all raising `CredentialGuardError` with no file content, checked
    strictly before any byte is read:
      1. the path stats (an unreadable/missing path fails closed);
      2. it is a regular file -- never a symlink, FIFO, device, or directory;
         a FIFO is refused here, before `open()`, so it can never hang;
      3. it is owned by the current effective user;
      4. its mode is exactly 0600;
      5. it does not live inside a Git worktree (walking up from its
         resolved directory for a `.git` entry).

    `follow_symlinks=True` first resolves `path` (runner's existing
    behavior: the rules apply to the resolved target, matching a caller that
    already tolerates a symlink to the real file). `follow_symlinks=False`
    refuses a symlinked path outright (market_research's existing
    O_NOFOLLOW behavior) instead of resolving it.

    Every rule is re-applied to the fstat of the file descriptor actually
    opened (not only the earlier lstat), and compared against that earlier
    lstat by (device, inode), closing the TOCTOU window between the check
    and the open.
    """
    target = Path(path).resolve() if follow_symlinks else Path(path)
    try:
        before = os.lstat(target)
    except OSError:
        raise CredentialGuardError(
            "credential_file_permissions: cannot stat the env file; "
            "create it at a private path outside this repository with `chmod 600`") from None
    if not follow_symlinks and stat.S_ISLNK(before.st_mode):
        raise CredentialGuardError(
            "credential_file_permissions: env file must not be a symlink; "
            "point at the real file directly")
    if not stat.S_ISREG(before.st_mode):
        raise CredentialGuardError(
            "credential_file_permissions: env file must be a regular file")

    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise CredentialGuardError(
            "credential_file_permissions: cannot open the env file; "
            "create it at a private path outside this repository with `chmod 600`") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino):
            raise CredentialGuardError(
                "credential_file_permissions: env file changed while it was being checked")
        if info.st_uid != os.getuid():
            raise CredentialGuardError(
                "credential_file_permissions: env file is not owned by the current user; "
                "chown it to your own account (never share a paper credential file)")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise CredentialGuardError(
                "credential_file_permissions: env file mode must be exactly 0600; "
                f"run `chmod 600 {target.name}`")
        if inside_git_worktree(target.resolve()):
            raise CredentialGuardError(
                "credential_file_permissions: env file must live outside any Git worktree; "
                "move it to a private, non-repository path (e.g. under your home config directory)")
    except BaseException:
        os.close(fd)
        raise
    # O_NONBLOCK only changes semantics for a FIFO/device/socket open; POSIX
    # defines no effect on a regular file, so the subsequent read() below
    # (and the one in each caller) is an ordinary blocking read.
    return os.fdopen(fd, "rb")
