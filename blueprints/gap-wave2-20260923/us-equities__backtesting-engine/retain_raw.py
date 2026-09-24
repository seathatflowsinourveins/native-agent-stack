#!/usr/bin/env python3
"""Copy raw outputs into the layer evidence directory with host paths replaced by $HOME
and the machine hostname by $HOSTNAME.

Usage: retain_raw.py SRC DEST_NAME [SRC DEST_NAME ...]
Prints one JSON line per file: {"path", "sha256", "bytes", "source_sha256", "home_replaced"}.
"""
import hashlib
import json
import os
import socket
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[3] / "evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/raw"
HOME = os.path.expanduser("~")


def main(argv):
    if len(argv) % 2:
        raise SystemExit("pairs of SRC DEST_NAME required")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for src, name in zip(argv[::2], argv[1::2]):
        data = Path(src).read_bytes()
        out = data.replace(HOME.encode(), b"$HOME").replace(socket.gethostname().encode(), b"$HOSTNAME")
        target = EVIDENCE / name
        target.write_bytes(out)
        print(json.dumps({"path": str(target.relative_to(EVIDENCE.parents[4])),
                          "sha256": hashlib.sha256(out).hexdigest(), "bytes": len(out),
                          "source_sha256": hashlib.sha256(data).hexdigest(),
                          "home_replaced": out != data}))


if __name__ == "__main__":
    main(sys.argv[1:])
