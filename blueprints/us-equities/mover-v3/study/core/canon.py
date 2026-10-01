"""Canonical serialization, hashing and the atomic results write (run_discipline.once)."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path


def dumps(obj) -> str:
    """The protocol's canonical form: json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_obj(obj) -> str:
    return sha256_bytes(dumps(obj).encode("utf-8"))


def sha256_file(path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def clean(x):
    """Floats that JSON cannot carry (nan, inf) become None, recursively."""
    if isinstance(x, float):
        return None if (math.isnan(x) or math.isinf(x)) else x
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


class ResultsExist(Exception):
    pass


def atomic_write_results(path, obj, replace_uncited: str | None = None) -> str:
    """Write one results file atomically: temporary file, fsync, rename. Refuses to replace an existing
    results file (a stage has at most one). Returns the sha256 of the bytes written.

    replace_uncited (review round 14, Codex P2): the sha256 of an existing file that no run-log line cites (a run
    killed between this rename and its log line). The caller has checked that no line cites a results file; the
    retry recomputes from the same sealed inputs and replaces exactly that file, and its line records the replaced
    sha256. Any other existing file is refused."""
    path = Path(path)
    if path.exists() and (replace_uncited is None or sha256_file(path) != replace_uncited):
        raise ResultsExist(f"{path.name}: a results file already exists for this run")
    data = (json.dumps(clean(obj), sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return sha256_bytes(data)
