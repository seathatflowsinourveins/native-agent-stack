"""Replace the host name and login name in committed raw files with
placeholders ("<hostname>", "<user>"). collect_raw.py replaced host paths and
UUIDs but left Temporal worker/CLI identities ("<pid>@<hostname>",
"temporal-cli:<user>@<hostname>") and Dagu service-registry host fields in
plaintext; neither string appears anywhere in the repository at base 41d39b3.
Base64 payloads were checked separately and hold neither string.

Detection: after replacement the script re-reads every file in the raw
directory and exits non-zero if either original string is still present, so a
missed occurrence fails the run rather than passing silently.

  sanitize_host_identity.py <evidence-raw-dir>
"""
import getpass
import json
import socket
import sys
from pathlib import Path


def main():
    raw = Path(sys.argv[1])
    host = socket.gethostname()
    user = getpass.getuser()
    pairs = [(f"{user}@{host}", "<user>@<hostname>"), (host, "<hostname>")]
    changed = {}
    for path in sorted(raw.iterdir()):
        if not path.is_file():
            continue
        text = path.read_text()
        new = text
        for old, repl in pairs:
            new = new.replace(old, repl)
        if new != text:
            changed[path.name] = text.count(host)
            path.write_text(new)
    leftover = [p.name for p in raw.iterdir() if p.is_file()
                and (host in p.read_text() or f"{user}@" in p.read_text())]
    print(json.dumps({"files_changed": changed, "leftover": leftover}, indent=1))
    if leftover:
        raise SystemExit("host identity still present")


if __name__ == "__main__":
    main()
