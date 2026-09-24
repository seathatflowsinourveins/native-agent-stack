#!/usr/bin/env python3
"""Redact local identifiers from committed raw outputs, in place, keeping within-file
correspondence: each distinct UUID becomes <id-N> (N by first appearance in that file);
/home/<user> -> $HOME; /mnt/<d>/Users/<name> -> /mnt/<d>/Users/<user>;
`ls -l` owner and group columns -> <user> <group>; this host's name -> <host> (both added fix round 2).
Usage: redact_raw.py FILE..."""
import re, socket, sys
HOST = socket.gethostname()
LS_L = re.compile(r"^([-dlcbps][rwxsStT-]{9}[.+@]?\s+\d+\s+)(\S+)\s+(\S+)(\s+\d)", re.M)
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
for path in sys.argv[1:]:
    text = open(path, encoding="utf-8", errors="surrogateescape").read()
    ids = {}
    text = UUID.sub(lambda m: ids.setdefault(m.group(0).lower(), f"<id-{len(ids) + 1}>"), text)
    text = re.sub(r"/home/[A-Za-z0-9_.-]+", "$HOME", text)
    text = re.sub(r"(/mnt/[A-Za-z]/Users/)[A-Za-z0-9_.-]+", r"\1<user>", text, flags=re.I)
    text = re.sub(r"([A-Za-z]:[/\\]+Users[/\\]+)[A-Za-z0-9_.-]+", r"\1<user>", text, flags=re.I)
    if HOST:
        text = text.replace(HOST, "<host>")
    text = LS_L.sub(r"\1<user> <group>\4", text)
    open(path, "w", encoding="utf-8", errors="surrogateescape").write(text)
    print(path.rsplit("/", 1)[-1], "uuids_redacted:", len(ids))
