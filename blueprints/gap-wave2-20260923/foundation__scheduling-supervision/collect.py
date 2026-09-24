#!/usr/bin/env python3
"""Copy the raw outputs a receipt cites into the layer's evidence directory.

Text files are copied with the host home path replaced by `$HOME` and every UUID-shaped
identifier (Codex thread ids, Prefect flow-run ids, Temporal run ids) replaced by a stable
`<uuid-N>` placeholder, consistently across one collection; binary files are not copied. The manifest lists, per file, the sha256 of the raw original and of the committed
sanitized copy, so the retained cache original can be matched if inspected.

Usage: collect.py SRC_DIR DEST_DIR PATTERN [PATTERN ...]
"""

import hashlib
import json
import re
import socket
from pathlib import Path
import sys

HOME = str(Path.home())
# Privacy sweep 2026-09-23 (PR #132 review): the host username (as a whole word) and the host name are also
# replaced; the manifest names these substitutions only when they occurred.
USER = re.compile(r"(?<![A-Za-z0-9])" + re.escape(Path.home().name) + r"(?![A-Za-z0-9])")
HOST = socket.gethostname()
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)


def main():
    src, dest, patterns = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {"source_dir": str(src).replace(HOME, "$HOME"),
                "substitution": "host home path -> $HOME; UUID-shaped identifiers -> <uuid-N> (same id, same N)", "files": []}
    placeholders = {}
    swept = {"host username -> <user>": 0, "host name -> <host>": 0}

    def uuid_sub(match):
        return placeholders.setdefault(match.group(0).lower(), f"<uuid-{len(placeholders) + 1}>")
    for pattern in patterns:
        for path in sorted(src.glob(pattern)):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            text, users = USER.subn("<user>", UUID.sub(uuid_sub, text.replace(HOME, "$HOME")))
            swept["host username -> <user>"] += users
            swept["host name -> <host>"] += text.count(HOST)
            clean = text.replace(HOST, "<host>").encode("utf-8")
            rel = path.relative_to(src)
            out = dest / str(rel).replace("/", "__")
            out.write_bytes(clean)
            manifest["files"].append({"source": str(rel), "committed_as": out.name, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                                      "committed_sha256": hashlib.sha256(clean).hexdigest(), "bytes": len(clean)})
    if any(swept.values()):
        manifest["substitution"] += "".join(f"; {k}" for k, v in swept.items() if v) + " (privacy sweep 2026-09-23)"
    manifest["uuid_placeholders"] = len(placeholders)
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(dest, len(manifest["files"]))


if __name__ == "__main__":
    main()
