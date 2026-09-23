"""Convert retained .gz third-party downloads to plain UTF-8 and redact UUID-shaped tokens.

scripts/validate.py only inspects UTF-8 text and rejects UUID-shaped strings as possible local
session identifiers. The UUIDs here are third-party page/element/release identifiers, not local
sessions, but they are redacted to keep publication checks strict. Original (pre-redaction)
hashes are recorded in raw/REDACTIONS.json. Usage: python3 publish_raw.py RAW_DIR [EXTRA_FILE_IN_RAW_DIR ...]
(fix round 2 added the optional extra files; the default targets are unchanged)
"""
import gzip, hashlib, json, re, sys
from pathlib import Path

UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
HOMEISH = re.compile(r"/(?:home|Users)/(?!example(?:/|\b))(?=[A-Za-z0-9_.-])")
raw = Path(sys.argv[1])
ledger_path = raw / "REDACTIONS.json"
ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
# Fix round 2: with extra file names, publish only those (re-processing an already published file would
# overwrite its original hash in the ledger); without them, the original targets are unchanged.
targets = [raw / n for n in sys.argv[2:]] or (sorted(raw.glob("*.gz")) + [raw / "17-pypi-sec-api.json"])
for src in targets:
    data = gzip.decompress(src.read_bytes()) if src.suffix == ".gz" else src.read_bytes()
    text = data.decode("utf-8")
    red, n = UUID.subn("<uuid-redacted>", text)
    # Fix round 2: third-party URL paths shaped like a home directory (nasdaqtrader links of the form slash-home-slash-index.jsp)
    # trip scripts/validate.py's personal-home-path rule; redact them the same way and count them.
    red, h = HOMEISH.subn("/<home-path-redacted>/", red)
    dst = src.with_suffix("") if src.suffix == ".gz" else src
    dst.write_text(red, encoding="utf-8")
    if src.suffix == ".gz":
        src.unlink()
    ledger[dst.name] = {"original_sha256": hashlib.sha256(data).hexdigest(), "original_bytes": len(data),
                        "uuid_redactions": n, **({"home_path_redactions": h} if h else {}), "published_sha256": hashlib.sha256(red.encode()).hexdigest()}
ledger_path.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
print(json.dumps({k: v.get("uuid_redactions") for k, v in ledger.items()}))
