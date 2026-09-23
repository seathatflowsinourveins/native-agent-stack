#!/usr/bin/env python3
"""Make committed raw outputs publishable under scripts/validate.py: decompress .gz files (the validator
inspects UTF-8 text only) and redact engine-generated UUIDs (event ids), recording pre/post hashes."""
import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw"
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
log_path = RAW / "REDACTIONS.json"
log = json.loads(log_path.read_text()) if log_path.exists() else {"decompressed": [], "uuid_redacted": []}
for gz in sorted(RAW.rglob("*.gz")):
    data = gzip.decompress(gz.read_bytes())
    target = gz.with_suffix("")
    target.write_bytes(data)
    log["decompressed"].append({"from": str(gz.relative_to(ROOT)), "gz_sha256": hashlib.sha256(gz.read_bytes()).hexdigest(),
                                "to": str(target.relative_to(ROOT)), "sha256": hashlib.sha256(data).hexdigest()})
    gz.unlink()
for f in sorted(p for p in RAW.rglob("*") if p.is_file() and p.name != "REDACTIONS.json"):
    text = f.read_text(encoding="utf-8")
    count = len(UUID.findall(text))
    if count:
        before = hashlib.sha256(f.read_bytes()).hexdigest()
        f.write_text(UUID.sub("uuid-redacted", text), encoding="utf-8")
        log["uuid_redacted"].append({"path": str(f.relative_to(ROOT)), "uuids_replaced": count, "sha256_before": before,
                                     "sha256_after": hashlib.sha256(f.read_bytes()).hexdigest()})
log_path.write_text(json.dumps(log, indent=2) + "\n")
print(len(log["decompressed"]), "decompressed;", len(log["uuid_redacted"]), "files redacted")
