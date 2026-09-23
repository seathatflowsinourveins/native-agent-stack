#!/usr/bin/env python3
"""Publication sanitization of raw outputs (run before make_receipts.py so receipt hashes match).

- host home path -> $HOME; /mnt/<drive>/Users/<name> -> /mnt/<drive>/Users/$WINUSER
- dash-encoded home slugs (codebase-memory project names such as "home-<user>-.cache-...") -> "home-$USER-..."
  (fix round 3, round-4 review finding 3; the literal-path replacement above does not match the slug form)
- UUIDs (daemon generations, connection ids) -> uuid-<n>, numbered per file in order of first appearance, so
  equality/inequality between ids inside one file is preserved.
"""
import pathlib
import re
import sys

HOME = str(pathlib.Path.home())
HOME_SLUG = HOME.strip("/").replace("/", "-") + "-"  # e.g. home-<user>-
HOME_SLUG_SAFE = "-".join(HOME.strip("/").split("/")[:-1] + ["$USER"]) + "-"  # e.g. home-$USER-
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
root = pathlib.Path(sys.argv[1])
for p in sorted(root.rglob("*")):
    if not p.is_file():
        continue
    t = p.read_text(errors="strict")
    o = t.replace(HOME, "$HOME")
    o = o.replace(HOME_SLUG, HOME_SLUG_SAFE)
    o = re.sub(r"/mnt/([A-Za-z])/Users/[A-Za-z0-9_.-]+", r"/mnt/\1/Users/$WINUSER", o)
    ids = {}
    o = UUID.sub(lambda m: ids.setdefault(m.group(0).lower(), f"uuid-{len(ids) + 1}"), o)
    if o != t:
        p.write_text(o)
        print(f"{p}: {len(ids)} uuids mapped")
