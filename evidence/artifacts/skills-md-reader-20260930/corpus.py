#!/usr/bin/env python3
"""Every SKILL.md of the skills catalog's GitHub sources at their catalog pins, read-only (depth-1 partial git fetches,
no gh REST calls), written as one JSON file {"<owner/repo>@<pin12>:<path>": {"blob": <git blob id>, "mode": <mode>,
"base64": <bytes>}} plus an index digest on stdout.

  corpus.py <catalog skills-lifecycle.json> <git work dir> <out corpus.json>

Only regular-file blobs (git modes 100644 and 100755) are read; a symlinked SKILL.md (120000) is listed with its mode
and no bytes. Each blob's bytes are checked against its git blob id. Prints per-source counts, the total and the
sha256 of the sorted "<key> <mode> <blob id>" lines (the corpus index digest)."""

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

CATALOG, ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0",
       "HOME": str(ROOT / "home"), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=ENV, check=check, timeout=900)


corpus, report, failures = {}, [], 0
for source in json.loads(CATALOG.read_text(encoding="utf-8"))["sources"]:
    url, pin = source["url"], source.get("pin") or ""
    if not url.startswith("https://github.com/") or len(pin) != 40:
        continue
    full = url[len("https://github.com/"):]
    repo = ROOT / full.replace("/", "__")
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        git(repo, "init", "-q")
        git(repo, "remote", "add", "origin", url)
    done = git(repo, "fetch", "-q", "--depth", "1", "--filter=blob:limit=1m", "origin", pin, check=False)
    if done.returncode:
        failures += 1
        report.append(f"{full}@{pin[:12]}: fetch exit {done.returncode}")
        continue
    listing = git(repo, "ls-tree", "-r", "-z", pin).stdout.decode("utf-8", "surrogateescape").split("\0")
    count = 0
    for record in listing:
        if not record:
            continue
        meta, path = record.split("\t", 1)
        mode, kind, blob = meta.split()
        if kind != "blob" or not (path == "SKILL.md" or path.endswith("/SKILL.md")):
            continue
        key = f"{full}@{pin[:12]}:{path}"
        entry = {"blob": blob, "mode": mode}
        if mode in ("100644", "100755"):
            data = git(repo, "cat-file", "blob", blob).stdout
            if hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() != blob:
                failures += 1
                report.append(f"{key}: bytes do not hash to the blob id")
                continue
            entry["base64"] = base64.b64encode(data).decode()
        corpus[key] = entry
        count += 1
    report.append(f"{full}@{pin[:12]}: {count} SKILL.md")
OUT.write_text(json.dumps(corpus, sort_keys=True), encoding="utf-8")
index = "".join(f"{key} {entry['mode']} {entry['blob']}\n" for key, entry in sorted(corpus.items()))
print("\n".join(report))
print("total", len(corpus), "regular", sum("base64" in entry for entry in corpus.values()), "fetch_failures", failures)
print("index_sha256", hashlib.sha256(index.encode("utf-8", "surrogateescape")).hexdigest())
sys.exit(1 if failures else 0)
