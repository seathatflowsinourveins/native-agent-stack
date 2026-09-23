#!/usr/bin/env python3
"""Copy the paper-arm round outputs (rounds 5-8 and the pre-registration dry run) into the
layer's raw/ directory with host identifiers sanitized, and print path/sha256/bytes JSON.

Sanitization: each round's temporary HOME (<scratch>/home) -> <temp-home>, the real home
directory -> $HOME, the host name -> <host>, user@host (restic) -> <user>@<host>,
UUIDs (collector service.instance.id) -> <uuid>. Unsanitized originals stay in the scratch
directories under $HOME/.cache/gap-wave2-20260923/observability-hosting/ (recovery path).
"""
import glob, hashlib, json, os, re, socket, sys

HOME = os.path.expanduser("~")
HOST = socket.gethostname()
USER = os.path.basename(HOME)
CACHE = f"{HOME}/.cache/gap-wave2-20260923/observability-hosting"
DEST = "evidence/artifacts/gap-wave2-20260923/us-equities__observability-hosting/raw"
SKIP_SUFFIX = (".db", ".db-wal", ".db-shm", ".sock")


def sanitize(text, scratch):
    text = text.replace(f"{scratch}/home", "<temp-home>")
    text = text.replace(HOME, "$HOME").replace(HOST, "<host>")
    text = text.replace(f"{USER}@<host>", "<user>@<host>")
    # collector service.instance.id UUIDs trip the publication validator's session-id rule
    return re.sub(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", "<uuid>", text, flags=re.I)


def copy(src, dst, scratch, out):
    data = open(src, "rb").read()
    try:
        data = sanitize(data.decode(), scratch).encode()
    except UnicodeDecodeError:
        print("skip binary", src, file=sys.stderr)
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "wb").write(data)
    out.append({"path": dst, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})


out = []
for n in (5, 6, 7, 8):
    R = f"{CACHE}/paper-arm-{n}"
    D = f"{DEST}/paper-arm-round{n}"
    files = sorted(glob.glob(f"{R}/logs/*") + glob.glob(f"{R}/cfg/*") + [f"{R}/dagu/dags/obsgap-paper.yaml"]
                   + glob.glob(f"{R}/dagu/logs/obsgap-paper/**/*.out", recursive=True)
                   + glob.glob(f"{R}/dagu/logs/obsgap-paper/**/*.err", recursive=True)
                   + glob.glob(f"{R}/work/result.json"))
    for f in files:
        if os.path.isfile(f) and not f.endswith(SKIP_SUFFIX):
            rel = os.path.relpath(f, R)
            if rel.startswith("dagu/logs/"):
                rel = "dagu-step-logs/" + os.path.basename(f)
            copy(f, f"{D}/{rel}", R, out)
    console = f"{CACHE}/paper-arm-{n}.console"
    if os.path.isfile(console):
        copy(console, f"{D}/console.txt", R, out)
dry = f"{CACHE}/paper-sim-dry"
for f in ("out.log", "err.log", "result.json"):
    if os.path.isfile(f"{dry}/{f}"):
        copy(f"{dry}/{f}", f"{DEST}/paper-sim-dry/{f}", dry, out)
print(json.dumps(out, indent=1))
