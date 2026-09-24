#!/usr/bin/env python3
"""Copy fix-round raw outputs into the evidence tree for publication.

Usage: collect_evidence.py DEST_DIR SRC[:NAME] ...
Each file is published with two textual substitutions, both recorded per file
in DEST_DIR/COLLECTED.json with the sha256 of the raw original and of the
published bytes: the host home directory is replaced by $HOME, and UUID-shaped
identifiers (promptfoo result ids, Claude session ids, Inspect ids) are
replaced by <uuid-redacted>, because the publication validator rejects
UUID-shaped strings as possible local session identifiers. CRLF pairs are
normalised to LF so the committed blob equals the hashed working-tree bytes.
"""
import hashlib
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
# Privacy sweep 2026-09-23 (PR #132 review): the host username is also replaced, as a whole word.
USER = re.compile(r"(?<![A-Za-z0-9])" + re.escape(os.path.basename(HOME)) + r"(?![A-Za-z0-9])")
# RFC 1918 addresses (not package versions like ==10.4.0.35, not dotted names like 10.0.0.1.nip.io) -> <lan-ip>.
LAN = re.compile(r"(?<![\w.])(?<!==)(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}(?!\.?[\w])")
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
dest = sys.argv[1]
record = json.load(open(os.path.join(dest, "COLLECTED.json"))) if os.path.exists(os.path.join(dest, "COLLECTED.json")) else {}


def publish(src, rel):
    raw = open(src, "rb").read()
    text = raw.decode("utf-8")
    homes = text.count(HOME)
    text = text.replace(HOME, "$HOME")
    text, uuids = UUID.subn("<uuid-redacted>", text)
    text, users = USER.subn("<user>", text)
    text, lans = LAN.subn("<lan-ip>", text)
    crlf = text.count("\r\n")
    text = text.replace("\r\n", "\n")
    out = os.path.join(dest, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(text)
    record[rel] = {"source": src.replace(HOME, "$HOME"), "raw_sha256": hashlib.sha256(raw).hexdigest(),
                   "published_sha256": hashlib.sha256(text.encode()).hexdigest(),
                   "home_path_replacements": homes, "uuid_redactions": uuids, "crlf_to_lf": crlf}
    if users:
        record[rel]["user_replacements"] = users
    if lans:
        record[rel]["lan_ip_replacements"] = lans


for arg in sys.argv[2:]:
    src, _, name = arg.partition(":")
    if os.path.isdir(src):
        for base, _, files in os.walk(src):
            for f in sorted(files):
                p = os.path.join(base, f)
                publish(p, os.path.join(name or os.path.basename(src.rstrip("/")), os.path.relpath(p, src)))
    else:
        publish(src, name or os.path.basename(src))
json.dump(dict(sorted(record.items())), open(os.path.join(dest, "COLLECTED.json"), "w"), indent=1)
print(len(record), "files recorded")
