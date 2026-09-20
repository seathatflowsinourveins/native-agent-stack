"""Deterministic synthetic state; nothing here reads client or personal data."""
from __future__ import annotations
import hashlib
from pathlib import Path
import stat


def files(snapshot: int) -> dict[str, tuple[bytes, int]]:
    if snapshot not in (1, 2):
        raise ValueError("snapshot must be 1 or 2")
    result = {
        "documents/notes/café-研究.md": ("# Synthetic handoff\nKeep café and 研究 paths intact.\n".encode(), 0o640),
        "blobs/data.bin": (bytes(range(256)) * 4096, 0o600),
        "empty": (b"", 0o600),
        "state/decision.json": (f'{{"revision":{snapshot},"scope":"synthetic"}}\n'.encode(), 0o600),
        "tools/check.sh": (b"#!/bin/sh\n# Synthetic permission fixture; never executed.\n", 0o750),
    }
    if snapshot == 1:
        result["state/deleted.txt"] = (b"Only in snapshot one.\n", 0o640)
    else:
        result["state/added.txt"] = (b"Only in snapshot two.\n", 0o640)
    return result


def materialize(root: Path, snapshot: int) -> None:
    """Write only a newly created fixture, or the known snapshot-one fixture."""
    if snapshot == 1:
        root.mkdir(mode=0o750)
    elif manifest(root) != expected_manifest(1):
        raise ValueError("snapshot-one fixture changed before the frozen transition")
    expected = files(snapshot)
    if snapshot == 2:
        (root / "state/deleted.txt").unlink()
    for name, (data, mode) in expected.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
    (root / "empty-directory").mkdir(exist_ok=True)
    for path in [root, *(p for p in root.rglob("*") if p.is_dir())]:
        path.chmod(0o750)


def expected_manifest(snapshot: int) -> list[dict]:
    result = {".": {"path": ".", "kind": "directory", "mode": "0750"},
              "empty-directory": {"path": "empty-directory", "kind": "directory", "mode": "0750"}}
    for name, (data, mode) in files(snapshot).items():
        for parent in Path(name).parents:
            if str(parent) != ".":
                result[str(parent)] = {"path": str(parent), "kind": "directory", "mode": "0750"}
        result[name] = {"path": name, "kind": "file", "mode": f"{mode:04o}",
                        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return [result[k] for k in sorted(result)]


def manifest(root: Path) -> list[dict]:
    result = []
    for p in [root, *sorted(root.rglob("*"))]:
        info = p.lstat()
        name = "." if p == root else p.relative_to(root).as_posix()
        mode = f"{stat.S_IMODE(info.st_mode):04o}"
        if stat.S_ISREG(info.st_mode):
            raw = p.read_bytes()
            result.append({"path": name, "kind": "file", "mode": mode,
                           "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        elif stat.S_ISDIR(info.st_mode):
            result.append({"path": name, "kind": "directory", "mode": mode})
        else:
            raise ValueError("fixture contains a symlink or unsupported file type")
    return sorted(result, key=lambda item: item["path"])


def assert_restored(root: Path, snapshot: int) -> list[dict]:
    actual = manifest(root)
    if actual != expected_manifest(snapshot):
        raise ValueError("restored path/type/byte/hash/mode manifest does not match frozen snapshot")
    return actual
