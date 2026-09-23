#!/usr/bin/env python3
"""Shared symlink-ancestor refusal, reused by every collector/verifier that
must trust a caller-supplied path but not any symlink a co-resident,
unprivileged account could have planted along it.

Standalone by design (only stdlib ``pathlib``/``stat``) so blueprint scripts
that are executed via ``importlib.util.spec_from_file_location`` -- never a
regular package import -- can load this file the same way they already load
each other's siblings, without adding a dependency on the ``scripts``
package being importable from their working directory.
"""
from __future__ import annotations

from pathlib import Path
import stat


def refuse_untrusted_symlinks(path, message: str) -> Path:
    """Return ``path`` (absolute, unresolved) after refusing it if any
    component -- any ancestor, or the leaf itself -- is a symlink that is
    not a trusted OS-level boundary link.

    A symlink is tolerated only when it is owned by root (``uid == 0``) and
    is not group- or world-writable. That is exactly the shape of a
    system-installed link such as macOS's ``/tmp -> /private/tmp``,
    ``/var -> /private/var`` or ``/etc -> /private/etc``: root-owned, mode
    not writable by anyone else. It is never granted based on the value of
    ``$TMPDIR`` or any other environment variable, and it is never granted
    merely because a symlink sits at or above ``tempfile.gettempdir()`` --
    an attacker who can set ``$TMPDIR`` or plant a symlink there (for
    example ``/tmp/shared`` pointing wherever they like) gets no exemption.
    Every other symlink, anywhere in the path, is refused, exactly like the
    unconditional walk this helper replaces.

    A ``..`` component is refused unconditionally: it can otherwise walk
    back out of an already-checked prefix without ever crossing a symlink.
    """
    path = Path(path).absolute()
    if ".." in path.parts:
        raise ValueError(message)
    candidate = Path(path.anchor)
    for part in path.relative_to(path.anchor).parts:
        candidate /= part
        if candidate.is_symlink():
            info = candidate.lstat()
            if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise ValueError(message)
    return path
