"""Shared fail-closed guard for an Alpaca paper-credential env file.

Both `runner.credentials()` and `market_research.credentials()` call
`open_verified()` before any line of the file is read, so the ownership,
permission, and Git-worktree-location rules cannot drift between the two
loaders. Every failure raises `CredentialGuardError` with one fixed message
(`GUARD_DENIED`) -- never the checked path, its basename, or any exception
text that could carry a path -- so no failure mode can leak filesystem
layout.

Only stdlib imports (`os`, `stat`, `pathlib`) so importing it never pulls
heavier modules (sqlite3, fcntl, threading, ...) into either caller.

What is (and is not) guaranteed
--------------------------------
The location, ownership, and permission rules are bound to the exact
directory-entry traversal that produces the returned file descriptor: from
`/`, each intermediate path component is opened with
`O_DIRECTORY | O_NOFOLLOW` via `dir_fd` chaining (never by string-pathname
lookup on an already-resolved path), and the final component is opened with
`O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_NOCTTY` the same way. A symlink
substituted at *any* position after the one-time initial resolution --
including an ancestor directory, not only the final file -- makes the
matching `dir_fd`-relative open fail with `ELOOP` or `ENOTDIR`, which this
module turns into the same fixed `CredentialGuardError`. This closes the
classic gap where checks are computed against a resolved pathname string and
the open happens against that string again later: here, once a directory
component's fd is open, every check and every subsequent open on that
subtree is by `dir_fd`, so nothing between the checks and the read can
substitute a different directory or file for the one already verified.

What is explicitly NOT guaranteed:
  - **External Git worktrees.** Worktree detection only recognizes an
    ancestor `.git` entry (a directory in an ordinary clone, or the pointer
    file `git worktree add` leaves in a linked worktree). A tree configured
    purely through `GIT_DIR`/`GIT_WORK_TREE` environment variables or
    `core.worktree`, with no `.git` entry anywhere in the credential file's
    own ancestor chain, is Git-tracked but invisible to this check. There is
    no general, file-local way to detect that case.
  - **A same-shaped replacement file.** If an attacker can atomically
    replace the target name with a *different* regular file that itself
    already satisfies every rule (owned by you, mode 0600, one link, in a
    directory you own that is not group/other-writable, outside any
    ancestor `.git`) at the instant of the real `open()` syscall, that
    replacement is indistinguishable from the legitimate file and is
    accepted -- there is no TOCTOU here (the fd that gets read is the exact
    fd whose metadata was just checked), but content substitution by a
    cooperating, equally-privileged actor is out of scope for a filesystem
    permission check.
  - **Concurrent privileged tampering after the descriptor is returned.**
    Checks run once, at open time, against the descriptor this call
    returns; nothing continues to monitor the file while the caller reads
    it.

Hard links: a target with more than one link (`st_nlink != 1`) is refused,
since a second, differently-located name for the same inode would let a
file that looks compliant at one path be simultaneously reachable (and
possibly git-tracked) at another.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

# A single, fixed, path-free error message reused for every rejection. Never
# interpolate a path, basename, or upstream OSError's `.filename`/`.strerror`
# into it -- see the module docstring's leak-avoidance guarantee.
GUARD_DENIED = (
    "credential_file_permissions: refused; the env file must exist, be a regular "
    "file with exactly one hard link, mode exactly 0600, owned by you, in a "
    "directory you own that is not group- or world-writable, and outside any "
    "Git worktree"
)

# Directories may be group/other readable+executable (0755) but never
# group- or other-writable.
_PARENT_FORBIDDEN_BITS = 0o022


class CredentialGuardError(RuntimeError):
    """A guard rule refused the credential path. The message is always the
    fixed `GUARD_DENIED` string -- never file content, a path, or a
    basename."""


def _hook(stage, name):
    """No-op by default. Tests monkeypatch this module attribute
    (`patch.object(credential_guard, "_hook", ...)`) to deterministically
    inject a filesystem mutation between a specific traversal step and the
    syscall that step is about to make, simulating a real race without
    relying on actual concurrent timing. `stage` is one of "pre_dir_open",
    "pre_file_open", or "pre_file_fstat"; `name` is the path component (or,
    for "pre_file_fstat", the opened fd) relevant to that stage."""


def _ancestor_has_git_entry(dir_fd) -> bool:
    """True if `dir_fd` (an already-open directory descriptor) itself
    contains a `.git` entry (directory or file, never followed) -- i.e.
    this specific already-verified directory is a Git worktree root. Any
    stat outcome other than a clean "not found" is treated as "yes" (fail
    closed): a permission error or other anomaly must not be read as
    absence."""
    try:
        os.stat(".git", dir_fd=dir_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _check_parent_directory(info) -> None:
    if not stat.S_ISDIR(info.st_mode):
        raise CredentialGuardError(GUARD_DENIED)
    if info.st_uid != os.getuid() or (stat.S_IMODE(info.st_mode) & _PARENT_FORBIDDEN_BITS) != 0:
        raise CredentialGuardError(GUARD_DENIED)


def _check_file_metadata(info) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise CredentialGuardError(GUARD_DENIED)
    if info.st_nlink != 1:
        raise CredentialGuardError(GUARD_DENIED)
    if info.st_uid != os.getuid():
        raise CredentialGuardError(GUARD_DENIED)
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise CredentialGuardError(GUARD_DENIED)


def _target_components(path, *, follow_symlinks: bool):
    """Return (directory_component_names, final_name) for `path`, computed
    exactly once. `follow_symlinks=True` fully resolves the path first
    (runner's existing behavior: the rules apply to whatever the symlink
    chain currently points at). `follow_symlinks=False` never dereferences a
    symlink -- only a syntactic (`os.path.normpath`) absolute form is
    computed, so a symlinked component is left in place for the traversal
    below to refuse with O_NOFOLLOW (market_research's existing behavior).

    Either way this one-time computation is *not* itself the security
    boundary: `open_verified` re-derives every guarantee from the
    `dir_fd`-bound traversal, so anything that changes after this function
    returns is caught there, not here.
    """
    given = Path(path)
    if follow_symlinks:
        try:
            resolved = given.resolve(strict=True)
        except OSError:
            raise CredentialGuardError(GUARD_DENIED) from None
    else:
        base = given if given.is_absolute() else Path.cwd() / given
        resolved = Path(os.path.normpath(str(base)))
    parts = resolved.parts
    if not parts or parts[0] != os.sep:
        raise CredentialGuardError(GUARD_DENIED)
    return parts[1:-1], (parts[-1] if len(parts) > 1 else None)


def open_verified(path, *, follow_symlinks: bool):
    """Verify every fail-closed rule and return an open, read-only binary
    file object for `path`; the caller owns it and must close it (a `with`
    block is the usual way).

    Every rule below is bound to the traversal that produces the returned
    descriptor (see the module docstring for exactly what that does and
    does not guarantee), and every failure raises `CredentialGuardError`
    with the single fixed `GUARD_DENIED` message, strictly before any byte
    of file content is read:
      1. every ancestor directory opens as a real directory, never a
         symlink (`O_DIRECTORY | O_NOFOLLOW`), and is checked for an
         ancestor `.git` entry;
      2. the immediate parent directory is owned by you and not group- or
         other-writable;
      3. the final component opens as a regular file, never a symlink
         (`O_NOFOLLOW`), never blocking on a FIFO or special file
         (`O_NONBLOCK`), never becoming a controlling terminal
         (`O_NOCTTY`);
      4. that file has exactly one hard link, is owned by you, and its
         mode is exactly 0600.

    `follow_symlinks=True` first resolves `path` (runner's existing
    behavior: a symlink to the real file is tolerated, and the rules apply
    to its target). `follow_symlinks=False` leaves a symlinked component in
    place so the traversal below refuses it outright (market_research's
    existing O_NOFOLLOW behavior) instead of resolving it.
    """
    dir_names, file_name = _target_components(path, follow_symlinks=follow_symlinks)
    if file_name is None:
        raise CredentialGuardError(GUARD_DENIED)

    try:
        root_fd = os.open(os.sep, os.O_DIRECTORY | os.O_RDONLY)
    except OSError:
        raise CredentialGuardError(GUARD_DENIED) from None

    opened = [root_fd]
    try:
        current_fd = root_fd
        if _ancestor_has_git_entry(current_fd):
            raise CredentialGuardError(GUARD_DENIED)
        for name in dir_names:
            _hook("pre_dir_open", name)
            try:
                next_fd = os.open(name, os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY, dir_fd=current_fd)
            except OSError:
                raise CredentialGuardError(GUARD_DENIED) from None
            opened.append(next_fd)
            current_fd = next_fd
            if _ancestor_has_git_entry(current_fd):
                raise CredentialGuardError(GUARD_DENIED)

        parent_info = os.fstat(current_fd)
        _check_parent_directory(parent_info)

        _hook("pre_file_open", file_name)
        try:
            file_fd = os.open(file_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY,
                               dir_fd=current_fd)
        except OSError:
            raise CredentialGuardError(GUARD_DENIED) from None
    finally:
        for fd in opened:
            os.close(fd)

    try:
        _hook("pre_file_fstat", file_fd)
        info = os.fstat(file_fd)
        _check_file_metadata(info)
    except BaseException:
        os.close(file_fd)
        raise
    # O_NONBLOCK only changes semantics for a FIFO/device/socket open; POSIX
    # defines no effect on a regular file (already enforced by
    # _check_file_metadata above), so the read the caller does through this
    # object is an ordinary blocking read.
    return os.fdopen(file_fd, "rb")
