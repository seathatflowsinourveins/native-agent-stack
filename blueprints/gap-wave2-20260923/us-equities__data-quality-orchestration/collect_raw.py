"""Copy cited raw outputs from the cache prefix into the layer's evidence
directory, replacing the host home path with $HOME and every UUID (Temporal
run/request identifiers) with a stable per-invocation placeholder
"uuid-redacted-<n>" (the publication scan treats UUIDs as local session
identifiers). Base64 strings (Temporal payload "data" fields) are decoded,
sanitized the same way and re-encoded, because a plaintext replacement misses
encoded payloads (review finding, fix round 2). Print a JSON map of
committed name -> {sha256 of the committed (sanitized) bytes, sha256 of the
original bytes, source path with $HOME}.

  collect_raw.py <evidence-raw-dir> <dest-name>=<source-path> [...]
"""
import base64
import binascii
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def main():
    dest_dir = Path(sys.argv[1])
    dest_dir.mkdir(parents=True, exist_ok=True)
    home = os.path.expanduser("~")
    out = {}
    uuid_re = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
    mapping = {}

    def redact(match):
        key = match.group(0).lower()
        mapping.setdefault(key, f"uuid-redacted-{len(mapping) + 1}")
        return mapping[key]
    b64_re = re.compile(r'"([A-Za-z0-9+/]{12,}={0,2})"')
    b64_fixed = {"count": 0}

    def fix_b64(match):
        token = match.group(1)
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return match.group(0)
        clean = uuid_re.sub(redact, decoded.replace(home, "$HOME"))
        if clean == decoded:
            return match.group(0)
        b64_fixed["count"] += 1
        return '"' + base64.b64encode(clean.encode("utf-8")).decode("ascii") + '"'

    for pair in sys.argv[2:]:
        name, src = pair.split("=", 1)
        raw = Path(src).read_bytes()
        before = b64_fixed["count"]
        text = b64_re.sub(fix_b64, raw.decode("utf-8"))
        text = uuid_re.sub(redact, text.replace(home, "$HOME"))
        (dest_dir / name).write_text(text)
        out[name] = {"sha256": hashlib.sha256(text.encode()).hexdigest(),
                     "original_sha256": hashlib.sha256(raw).hexdigest(),
                     "source": src.replace(home, "$HOME"),
                     "uuids_redacted": len(uuid_re.findall(raw.decode("utf-8"))),
                     "base64_payloads_sanitized": b64_fixed["count"] - before}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
