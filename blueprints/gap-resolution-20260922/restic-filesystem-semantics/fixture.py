"""Build a scratch source tree exercising ACLs, xattrs, sparse files, hardlinks,
symlinks and unusual names, then capture a metadata manifest that a restic
backup/restore round trip can be diffed against.

Deterministic synthetic content only; no client or personal data.
"""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path


def build(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)

    # 1. plain file
    (root / "plain.txt").write_bytes(b"plain synthetic content\n")

    # 2. file with a POSIX ACL (extra rwx grant for the running uid, which is
    #    already implied by owner bits, so add a distinguishing mask entry)
    acl_file = root / "acl-file.txt"
    acl_file.write_bytes(b"acl synthetic content\n")
    uid = os.getuid()
    subprocess.run(["setfacl", "-m", f"u:{uid}:rwx", str(acl_file)], check=True)

    # 3. file with a user xattr
    xattr_file = root / "xattr-file.txt"
    xattr_file.write_bytes(b"xattr synthetic content\n")
    os.setxattr(xattr_file, "user.gap_check", b"restic-filesystem-semantics")

    # 4. sparse file: 10 MiB logical size, only a few real bytes written
    sparse_file = root / "sparse.bin"
    with open(sparse_file, "wb") as fh:
        fh.truncate(10 * 1024 * 1024)
        fh.seek(5 * 1024 * 1024)
        fh.write(b"middle-marker")

    # 5. hardlink pair
    hardlink_src = root / "hardlink-src.txt"
    hardlink_src.write_bytes(b"hardlinked synthetic content\n")
    hardlink_dst = root / "hardlink-dst.txt"
    os.link(hardlink_src, hardlink_dst)

    # 6. symlink (relative, to a sibling file)
    symlink_path = root / "symlink-to-plain.txt"
    os.symlink("plain.txt", symlink_path)

    # 7. unusual names: spaces, unicode, leading dot, embedded special chars
    (root / "space name.txt").write_bytes(b"space name content\n")
    (root / "unicode-é研究.md").write_bytes(
        "# synthetic unicode café 研究\n".encode()
    )
    (root / ".dotfile").write_bytes(b"dotfile content\n")
    (root / "special-chars_[1]-(2).txt").write_bytes(b"special chars content\n")

    # empty dir
    (root / "empty-dir").mkdir(exist_ok=True)


def manifest(root: Path, *, capture_ownership: bool = True) -> list[dict]:
    """Metadata manifest: path, kind, mode, size, sha256 (files), symlink
    target, hardlink inode-group id (local to this manifest), ACL text and
    xattr set. Ownership (uid/gid) captured only when requested, since a
    cross-filesystem (drvfs) restore target legitimately remaps ownership."""
    entries = []
    inode_map: dict[int, int] = {}
    for p in sorted(root.rglob("*")) :
        rel = p.relative_to(root).as_posix()
        st = p.lstat()
        kind = (
            "symlink" if stat.S_ISLNK(st.st_mode)
            else "directory" if stat.S_ISDIR(st.st_mode)
            else "file"
        )
        entry: dict = {"path": rel, "kind": kind, "mode": f"{stat.S_IMODE(st.st_mode):04o}"}
        if capture_ownership:
            entry["uid"] = st.st_uid
            entry["gid"] = st.st_gid
        if kind == "file":
            data = p.read_bytes()
            entry["size"] = len(data)
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            group = inode_map.setdefault(st.st_ino, len(inode_map))
            entry["inode_group"] = group
            try:
                names = os.listxattr(p, follow_symlinks=False)
                entry["xattrs"] = sorted(names)
                entry["xattr_values"] = {
                    n: os.getxattr(p, n, follow_symlinks=False).decode("utf-8", "replace")
                    for n in names
                }
            except OSError as exc:
                entry["xattrs_error"] = str(exc)
            try:
                acl = subprocess.run(
                    ["getfacl", "-p", "--omit-header", str(p)],
                    check=True, capture_output=True, text=True,
                ).stdout
                entry["acl"] = acl.strip()
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                entry["acl_error"] = str(exc)
        elif kind == "symlink":
            entry["target"] = os.readlink(p)
        entries.append(entry)
    return entries


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "manifest"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-ownership", action="store_true")
    args = parser.parse_args()
    if args.action == "build":
        build(args.root)
    else:
        m = manifest(args.root, capture_ownership=not args.no_ownership)
        text = json.dumps(m, indent=2, sort_keys=True)
        if args.out:
            args.out.write_text(text)
        else:
            print(text)
