"""Shared fail-closed guard for an Alpaca paper-credential env file.

Both `runner.credentials()` and `market_research.credentials()` call
`open_verified()` before any line of the file is read, so the ownership,
permission, and Git-worktree-location rules cannot drift between the two
loaders. Every failure raises `CredentialGuardError` with one of a small,
fixed set of `REASON_*` reason codes (all sharing the `credential_file_
permissions:` prefix runner's tests assert) -- never the checked path, its
basename, or any exception text that could carry a path -- so no failure
mode can leak filesystem layout, and an operator can still tell *which*
rule was violated without that leak.

Only stdlib imports (`os`, `stat`, `errno`, `io`, `pathlib`) so importing it never
pulls heavier modules (sqlite3, fcntl, threading, ...) into either caller.

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
matching `dir_fd`-relative open fail with `ELOOP` or `ENOTDIR`.

Every ancestor directory from `/` down through -- but not including -- the
immediate parent is checked with the OpenSSH `safe_path`/`secure_filename`
model as a *container*: it must be owned by root or by the caller, and if it
is group- or world-writable it must also carry the sticky bit (`S_ISVTX`,
e.g. a `1777 /tmp`). A writable, non-sticky ancestor anywhere in that chain
is refused outright, regardless of what it contains -- this is what stops an
attacker who can write to `/shared` from renaming a victim-owned
`/shared/private` (already opened and checked) into `/shared/repo` (which
has a `.git`): `/shared` itself fails the ancestor check the moment it is
opened, before the file is ever reached, and does not depend on where the
attacker later moves anything.

The immediate parent -- the directory the file's own name lives in -- is
held to a *stricter*, non-excusable rule instead: owned by exactly the
caller (root ownership does not excuse it here) and never group- or
other-writable, with no sticky-bit exception. This is why a private,
caller-owned directory *under* `/tmp` still passes (it is independently
checked by this stricter rule, one level down from `/tmp` itself, which is
only ever a passed-through container) while `/tmp/file` and `/file` do not:
`/tmp` and `/` are acceptable ancestors, never acceptable parents.

Each ancestor's `.git` check (and each ancestor's own ownership/writability
check) runs once, at the moment that ancestor's own descriptor is opened --
not continuously, and not as a property of the path as a whole. Another uid
permitted to create entries in a sticky, world-writable ancestor (e.g.
`/tmp`) can still create a new `.git` entry there *after* that ancestor was
already inspected and passed; this is not an atomic, held-for-the-duration
guarantee about the location, only a check performed at each ancestor's own
inspection time. It does not let that other uid bypass any file's own
ownership/mode/hard-link checks, nor relocate an already-opened, already-
verified descriptor.

What is explicitly NOT guaranteed:
  - **External Git worktrees.** Worktree detection only recognizes an
    ancestor `.git` entry (a directory in an ordinary clone, or the pointer
    file `git worktree add` leaves in a linked worktree). A tree configured
    purely through `GIT_DIR`/`GIT_WORK_TREE` environment variables or
    `core.worktree`, with no `.git` entry anywhere in the credential file's
    own ancestor chain, is Git-tracked but invisible to this check. There is
    no general, file-local way to detect that case. Likewise, a bind mount
    that makes a repository subdirectory appear at a path with no `.git`
    ancestor in its own mount namespace is invisible to this check; that
    requires mount authority (or an existing mount) to set up.
  - **A same-shaped replacement file.** If an attacker can atomically
    replace the target name with a *different* regular file that itself
    already satisfies every rule (owned by you, mode 0600, one link, an
    ancestor chain that passes) at the instant of the real `open()`
    syscall, that replacement is indistinguishable from the legitimate file
    and is accepted -- there is no TOCTOU here (the fd that gets read is the
    exact fd whose metadata was just checked), but content substitution by
    an equally-privileged actor who can already write there is out of scope
    for a filesystem permission check. `runner.credentials()`
    (`follow_symlinks=True`) documents this same acceptance for the
    symlink case it deliberately tolerates: if the symlink's target changes
    between the initial resolve and the traversal, the rules simply apply
    to whatever now-compliant file is actually opened.
  - **Concurrent privileged tampering after the descriptor is returned.**
    Checks run once, at open time, against the descriptor this call
    returns; nothing continues to monitor the file while the caller reads
    it.

Hard links: a target with more than one link (`st_nlink != 1`) is refused,
since a second, differently-located name for the same inode would let a
file that looks compliant at one path be simultaneously reachable (and
possibly git-tracked) at another.

Error content: every failure is built and raised *after* any internal
`try/except` has already exited (see `_try` below), specifically so Python
never attaches the original, possibly path-bearing exception as
`__context__` on the raised `CredentialGuardError` -- setting `__cause__`
via `from None` alone does not clear `__context__`, since the interpreter
re-populates it at the `raise` statement itself if one is still executing
inside a handler.
"""
from __future__ import annotations

import errno
import io
import os
import stat
from pathlib import Path

_PREFIX = "credential_file_permissions"

# Fixed, path-free reason codes. Every one starts with `_PREFIX` so
# runner.credentials()'s tests (which only assert that substring) keep
# passing regardless of which specific rule fired.
REASON_MISSING = f"{_PREFIX}:missing"
REASON_NOT_REGULAR = f"{_PREFIX}:not_regular"
REASON_SYMLINK = f"{_PREFIX}:symlink"
REASON_OWNER = f"{_PREFIX}:owner"
REASON_MODE = f"{_PREFIX}:mode"
REASON_HARDLINK = f"{_PREFIX}:hardlink"
REASON_WORKTREE = f"{_PREFIX}:worktree"
REASON_ANCESTOR = f"{_PREFIX}:ancestor"
REASON_PARENT_OWNER = f"{_PREFIX}:parent_owner"
REASON_PARENT_MODE = f"{_PREFIX}:parent_mode"
REASON_ENCODING = f"{_PREFIX}:encoding"
REASON_SIZE = f"{_PREFIX}:size"

# The size cap both loaders enforce by reading at most this many bytes plus
# one from the already-open descriptor, never by trusting an earlier
# fstat-reported size (which a concurrent writer could grow past).
MAX_CREDENTIAL_BYTES = 65536

# Directories may be group/other readable+executable (0755) but never
# group- or other-writable, unless the sticky bit excuses it (see module
# docstring).
_WRITABLE_BITS = 0o022


class CredentialGuardError(RuntimeError):
    """A guard rule refused the credential path. The message is always one
    of the fixed `REASON_*` codes above -- never file content, a path, or a
    basename, and never carries the original exception as `__context__` or
    `__cause__` (see the module docstring)."""


def _hook(stage, name):
    """No-op by default. Tests monkeypatch this module attribute
    (`patch.object(credential_guard, "_hook", ...)`) to deterministically
    inject a filesystem mutation between a specific traversal step and the
    syscall that step is about to make, simulating a real race without
    relying on actual concurrent timing. `stage` is one of "pre_dir_open",
    "pre_file_open", or "pre_file_fstat"; `name` is the path component (or,
    for "pre_file_fstat", the opened fd) relevant to that stage."""


def _try(func, *args, **kwargs):
    """Run `func(*args, **kwargs)`, returning `(result, reason)`.

    On success, `reason` is `None`. On failure, `result` is `None` and
    `reason` is a fixed `REASON_*` code chosen from the exception actually
    raised -- `OSError` (covering "not found", permission, and every other
    ordinary open/stat failure), `RuntimeError` (a circular symlink:
    `Path.resolve(strict=True)` raises this, not `OSError`, on the native
    Python 3.12 runtime), and `ValueError` (e.g. an embedded NUL byte in the
    path). The original exception is fully consumed inside this function's
    `except` clauses and never returned or re-raised: callers raise a fresh
    `CredentialGuardError(reason)` themselves, from their own, already-clean
    control flow (outside any `except` block), which is what keeps
    `__context__` clear -- see the module docstring.
    """
    try:
        return func(*args, **kwargs), None
    except OSError as error:
        return None, (REASON_SYMLINK if error.errno == errno.ELOOP else REASON_MISSING)
    except RuntimeError:
        return None, REASON_SYMLINK
    except ValueError:
        return None, REASON_MISSING


def _is_symlink_component(dir_fd, name) -> bool:
    """Best-effort refinement used only on an already-failed directory-open:
    on Linux, opening a *symlinked* directory component with
    `O_DIRECTORY | O_NOFOLLOW` surfaces as `ENOTDIR`, not `ELOOP` (unlike
    the final, non-`O_DIRECTORY` component, which does get `ELOOP` and so
    is already reported as `REASON_SYMLINK` by `_try`). Without this, such
    a component would fall into the generic `REASON_MISSING` bucket even
    though it is specifically a symlink. One extra `lstat`, only on this
    failure path (never the common success path), tells the two apart.

    Round-5 fix: catches `(OSError, ValueError, UnicodeError)`, not only
    `OSError` -- `name` can itself carry a NUL byte (`ValueError`) or a
    surrogate that cannot round-trip through the filesystem encoding
    (`UnicodeEncodeError`, whose `.object` attribute would otherwise retain
    the ancestor component name). Either way this function must still
    return a plain bool so the caller's already-sanitized `REASON_MISSING`
    code applies, rather than letting a new, unsanitized exception escape
    from this refinement step."""
    try:
        info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except (OSError, ValueError, UnicodeError):
        return False
    return stat.S_ISLNK(info.st_mode)


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


def _check_ancestor_directory(info, *, reason_owner, reason_writable) -> None:
    """The OpenSSH `safe_path`/`secure_filename` rule, applied to one
    already-opened ancestor directory (root included): owned by root or the
    caller, and -- if group- or world-writable -- sticky. See the module
    docstring for why this specific combination is what makes `/tmp`
    trustworthy as a container while an ordinary attacker-writable shared
    directory is refused outright, independent of what it contains or what
    gets renamed into it afterward."""
    if not stat.S_ISDIR(info.st_mode):
        raise CredentialGuardError(reason_owner)
    if info.st_uid not in (0, os.getuid()):
        raise CredentialGuardError(reason_owner)
    mode = stat.S_IMODE(info.st_mode)
    if (mode & _WRITABLE_BITS) != 0 and not (mode & stat.S_ISVTX):
        raise CredentialGuardError(reason_writable)


def _check_parent_directory(info) -> None:
    """The credential file's own containing directory must be private, not
    merely an acceptable *container*: owned by exactly the caller (root
    ownership does not excuse it here the way it excuses a container
    ancestor -- this is the directory the file's own name lives in), and
    never group- or other-writable, with no sticky-bit exception. This is
    what makes `/tmp` itself an acceptable ancestor to pass through but
    never an acceptable parent: a private, caller-owned subdirectory of
    `/tmp` still passes (it is independently checked by this same rule),
    but `/tmp/file` and `/file` do not."""
    if not stat.S_ISDIR(info.st_mode):
        raise CredentialGuardError(REASON_PARENT_OWNER)
    if info.st_uid != os.getuid():
        raise CredentialGuardError(REASON_PARENT_OWNER)
    if (stat.S_IMODE(info.st_mode) & _WRITABLE_BITS) != 0:
        raise CredentialGuardError(REASON_PARENT_MODE)


def _check_file_metadata(info) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise CredentialGuardError(REASON_NOT_REGULAR)
    if info.st_nlink != 1:
        raise CredentialGuardError(REASON_HARDLINK)
    if info.st_uid != os.getuid():
        raise CredentialGuardError(REASON_OWNER)
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise CredentialGuardError(REASON_MODE)


def _target_components(path, *, follow_symlinks: bool):
    """Return (directory_component_names, final_name) for `path`, computed
    exactly once. `follow_symlinks=True` fully resolves the path first
    (runner's existing behavior: the rules apply to whatever the symlink
    chain currently points at). `follow_symlinks=False` never dereferences a
    symlink and never lexically collapses a `..` component (unlike
    `os.path.normpath`, which would silently skip over an intermediate
    symlinked component named by a `..` segment without ever refusing it,
    contradicting the "a symlinked component is always refused" guarantee)
    -- any `..` component is refused outright instead.

    Either way this one-time computation is *not* itself the security
    boundary: `open_verified` re-derives every guarantee from the
    `dir_fd`-bound traversal, so anything that changes after this function
    returns is caught there, not here.
    """
    given = Path(path)
    if follow_symlinks:
        resolved, reason = _try(given.resolve, strict=True)
        if reason:
            raise CredentialGuardError(reason)
    else:
        if given.is_absolute():
            base = given
        else:
            cwd, reason = _try(Path.cwd)
            if reason:
                raise CredentialGuardError(reason)
            base = cwd / given
        if ".." in base.parts:
            raise CredentialGuardError(REASON_SYMLINK)
        resolved = base
    parts = resolved.parts
    if not parts or parts[0] != os.sep:
        raise CredentialGuardError(REASON_MISSING)
    return parts[1:-1], (parts[-1] if len(parts) > 1 else None)


def open_verified(path, *, follow_symlinks: bool):
    """Verify every fail-closed rule and return an open, read-only binary
    file object for `path`; the caller owns it and must close it (a `with`
    block is the usual way).

    Every rule below is bound to the traversal that produces the returned
    descriptor (see the module docstring for exactly what that does and
    does not guarantee), and every failure raises `CredentialGuardError`
    with one of the fixed `REASON_*` codes, strictly before any byte of
    file content is read:
      1. every ancestor directory from `/` down opens as a real directory,
         never a symlink (`O_DIRECTORY | O_NOFOLLOW`; a symlinked directory
         component is reported as `symlink`, not `missing`); is checked for
         an ancestor `.git` entry (`worktree`); every ancestor up to but not
         including the immediate parent must be owned by root or the
         caller, group/other-writable only if sticky (`ancestor`); the
         immediate parent must be owned by exactly the caller and never
         group/other-writable, with no sticky exception (`parent_owner`/
         `parent_mode`);
      2. the final component opens as a regular file, never a symlink
         (`O_NOFOLLOW`), never blocking on a FIFO or special file
         (`O_NONBLOCK`), never becoming a controlling terminal
         (`O_NOCTTY`);
      3. that file has exactly one hard link, is owned by you, and its
         mode is exactly 0600.

    `follow_symlinks=True` first resolves `path` (runner's existing
    behavior: a symlink to the real file is tolerated, and the rules apply
    to its target). `follow_symlinks=False` leaves a symlinked component in
    place so the traversal below refuses it outright (market_research's
    existing O_NOFOLLOW behavior) instead of resolving it.
    """
    dir_names, file_name = _target_components(path, follow_symlinks=follow_symlinks)
    if file_name is None:
        raise CredentialGuardError(REASON_MISSING)

    root_fd, reason = _try(os.open, os.sep, os.O_DIRECTORY | os.O_RDONLY)
    if reason:
        raise CredentialGuardError(reason)

    opened = [root_fd]
    try:
        current_fd = root_fd
        if dir_names:
            _check_ancestor_directory(os.fstat(current_fd), reason_owner=REASON_ANCESTOR,
                                       reason_writable=REASON_ANCESTOR)
        else:
            # The file sits directly in "/" -- root is the immediate parent,
            # not merely a container ancestor, so the strict (not
            # sticky-excused) parent rule applies here too: this rejects
            # "/file" the same way it rejects "/tmp/file".
            _check_parent_directory(os.fstat(current_fd))
        if _ancestor_has_git_entry(current_fd):
            raise CredentialGuardError(REASON_WORKTREE)
        for index, name in enumerate(dir_names):
            is_immediate_parent = index == len(dir_names) - 1
            _hook("pre_dir_open", name)
            next_fd, reason = _try(os.open, name, os.O_DIRECTORY | os.O_NOFOLLOW | os.O_RDONLY, dir_fd=current_fd)
            if reason:
                # A symlinked directory component surfaces as ENOTDIR here
                # (unlike the final, non-O_DIRECTORY component, which gets
                # ELOOP and so is already REASON_SYMLINK) -- refine the
                # generic code on this failure path only.
                if reason == REASON_MISSING and _is_symlink_component(current_fd, name):
                    reason = REASON_SYMLINK
                raise CredentialGuardError(reason)
            opened.append(next_fd)
            current_fd = next_fd
            if is_immediate_parent:
                _check_parent_directory(os.fstat(current_fd))
            else:
                _check_ancestor_directory(os.fstat(current_fd), reason_owner=REASON_ANCESTOR,
                                           reason_writable=REASON_ANCESTOR)
            if _ancestor_has_git_entry(current_fd):
                raise CredentialGuardError(REASON_WORKTREE)

        _hook("pre_file_open", file_name)
        file_fd, reason = _try(os.open, file_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY,
                                dir_fd=current_fd)
        if reason:
            raise CredentialGuardError(reason)
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
    #
    # Built in two steps rather than one `os.fdopen(file_fd, "rb")` call, so
    # cleanup never closes the same fd twice. `io.FileIO(file_fd, "rb",
    # closefd=True)` does NOT take ownership of `file_fd` until it returns
    # successfully -- if its own construction fails, CPython leaves
    # `file_fd` open (verified against CPython's `_io.FileIO.__init__`),
    # so that failure is handled here with a plain `os.close(file_fd)`.
    # Once `raw` exists, it *does* own the fd; a later failure (wrapping it
    # in a `BufferedReader`) is handled by closing that already-constructed
    # `raw` object instead, never the bare integer again -- closing both
    # would double-close the same fd, which either raises `EBADF` (masking
    # the real error) or, worse, closes an unrelated fd the OS has since
    # reused for something else.
    try:
        raw = io.FileIO(file_fd, "rb", closefd=True)
    except BaseException:
        os.close(file_fd)
        raise
    try:
        return io.BufferedReader(raw)
    except BaseException:
        raw.close()
        raise
