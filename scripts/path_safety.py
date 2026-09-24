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

    A symlink is tolerated only when BOTH:
      - it sits directly under the filesystem root (its own parent is
        ``path.anchor``, i.e. ``/``); and
      - that parent directory (so, in practice, ``/`` itself) is owned by
        root (``uid == 0``) and not group- or world-writable.

    That is exactly the shape of a system-installed link such as macOS's
    ``/tmp -> /private/tmp``, ``/var -> /private/var`` or
    ``/etc -> /private/etc``. Checking the *link's own* mode would do
    nothing -- a symlink's own permission bits are not what gate replacing
    it (Linux does not even enforce them: lstat reports 0o777 for every
    symlink regardless of any chmod); what actually controls whether an
    unprivileged account can repoint or replace the link is whether it can
    write to the directory the link lives in, which is why the parent
    directory is what gets checked, not the link. Restricting tolerance to
    links directly under ``/`` also means a root-owned link deeper in the
    tree -- for example a hard link to, or a copy of, a relative framework
    link such as macOS's ``Versions/Current`` planted somewhere under
    ``/tmp`` -- is never tolerated merely because *it* happens to be
    root-owned: only the fixed, single-hop system boundary is.

    It is never granted based on the value of ``$TMPDIR`` or any other
    environment variable, and it is never granted merely because a symlink
    sits at or above ``tempfile.gettempdir()`` -- an attacker who can set
    ``$TMPDIR`` or plant a symlink there (for example ``/tmp/shared``
    pointing wherever they like) gets no exemption. Every other symlink,
    anywhere in the path, is refused, exactly like the unconditional walk
    this helper replaces.

    A ``..`` component is refused unconditionally: it can otherwise walk
    back out of an already-checked prefix without ever crossing a symlink.
    """
    path = Path(path).absolute()
    if ".." in path.parts:
        raise ValueError(message)
    root = Path(path.anchor)
    candidate = root
    for part in path.relative_to(root).parts:
        candidate /= part
        if candidate.is_symlink():
            if candidate.parent != root:
                raise ValueError(message)
            info = root.lstat()
            if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise ValueError(message)
    return path
