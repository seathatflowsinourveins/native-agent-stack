#!/usr/bin/env python3
"""Copy a LEAN parity run into raw/<dest> for publication: UTF-8 text files only, host home path replaced by $HOME
and the host name by HOST-redacted, with pre/post hashes in raw/REDACTIONS.json. Binary files and LEAN's large full
result JSON (charts) are not copied; their sha256 values are listed in <dest>/NOT_COPIED.json."""
import hashlib
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw"
SKIP_NAMES = {"WeightScheduleParityAlgorithm.json"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main(source, dest):
    source, target_root = Path(source).resolve(), RAW / dest
    if target_root.exists():
        raise SystemExit("destination exists")
    home, host = str(Path.home()), socket.gethostname()
    log_path = RAW / "REDACTIONS.json"
    log = json.loads(log_path.read_text())
    entries, skipped = log.setdefault("lean_parity_redacted", []), []
    for f in sorted(p for p in source.rglob("*") if p.is_file()):
        rel = f.relative_to(source)
        data = f.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is None or f.name in SKIP_NAMES or f.stat().st_size > 1_000_000:
            skipped.append({"path": str(rel), "bytes": len(data), "sha256": sha(data)})
            continue
        clean = text.replace(home, "$HOME").replace(host, "HOST-redacted")
        out = target_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(clean, encoding="utf-8")
        if clean != text:
            entries.append({"path": str(out.relative_to(ROOT)), "sha256_before": sha(data),
                            "sha256_after": sha(clean.encode("utf-8")), "replaced": ["host home path -> $HOME", "host name -> HOST-redacted"]})
    (target_root / "NOT_COPIED.json").write_text(json.dumps(
        {"source": str(source).replace(home, "$HOME"), "reason": "binary or LEAN full result JSON (charts) over 1 MB; kept in the cache",
         "files": skipped}, indent=2) + "\n")
    log_path.write_text(json.dumps(log, indent=2) + "\n")
    print(json.dumps({"copied_to": str(target_root.relative_to(ROOT)), "not_copied": len(skipped)}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
