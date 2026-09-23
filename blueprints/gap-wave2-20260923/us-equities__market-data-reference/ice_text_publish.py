"""Fix round 3: publish the two archived ICE press releases as tag-stripped text only.

Guarded gitleaks flagged the full HTML (generic-api-key: the ir.theice.com site's embedded public Q4
API key, in a <script> block and in a widget URL). The full HTML stays in the cache; this writes the
same text archive_calendar_check.text_of() extracts (scripts, styles and tags removed), records the
original HTML sha256 in raw/REDACTIONS.json, and removes the published HTML copies.
Usage: python3 ice_text_publish.py CACHE_DIR RAW_DIR
"""
import hashlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from archive_calendar_check import text_of  # noqa: E402

# Same rules as publish_raw.py (added after scripts/validate.py flagged Business Wire's "/home/<id>" URL path).
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
HOMEISH = re.compile(r"/(?:home|Users)/(?!example(?:/|\b))(?=[A-Za-z0-9_.-])")

cache, raw = Path(sys.argv[1]), Path(sys.argv[2])
ledger_path = raw / "REDACTIONS.json"
ledger = json.loads(ledger_path.read_text())
for stem in ("ice-bush-20250108195503", "ice-carter-20241230155348"):
    src = cache / f"{stem}.html"
    data = src.read_bytes()
    text = text_of(data.decode("utf-8", errors="replace")) + "\n"
    text, n_uuid = UUID.subn("<uuid-redacted>", text)
    text, n_home = HOMEISH.subn("/<home-path-redacted>/", text)
    dst = raw / f"14-wayback-{stem}.txt"
    dst.write_text(text, encoding="utf-8")
    old = raw / f"14-wayback-{stem}.html"
    if old.exists():
        old.unlink()
    ledger.pop(old.name, None)
    ledger[dst.name] = {"original_sha256": hashlib.sha256(data).hexdigest(), "original_bytes": len(data),
                        "published_as": "tag-stripped text (scripts, styles and tags removed); full HTML withheld because guarded gitleaks flagged the site's embedded public Q4 API key (generic-api-key)",
                        "uuid_redactions": n_uuid, "home_path_redactions": n_home,
                        "published_sha256": hashlib.sha256(text.encode()).hexdigest()}
ledger_path.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
print(json.dumps({k: ledger[k]["published_sha256"][:12] for k in ledger if k.startswith("14-wayback-ice")}))
