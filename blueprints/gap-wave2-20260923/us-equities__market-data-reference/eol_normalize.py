"""Round-3 integrity fix: rewrite published raw text files with LF endings (what git stores under
.gitattributes '* text=auto eol=lf') and record the change in raw/REDACTIONS.json.
Usage: python3 eol_normalize.py RAW_DIR FILE [FILE ...]"""
import hashlib, json, sys
from pathlib import Path
raw = Path(sys.argv[1]); ledger_path = raw / "REDACTIONS.json"; ledger = json.loads(ledger_path.read_text())
for n in sys.argv[2:]:
    p = raw / n; b = p.read_bytes(); lf = b.replace(b"\r\n", b"\n")
    p.write_bytes(lf)
    e = ledger.setdefault(n, {})
    e.update(eol_normalized_to_lf=True, crlf_published_sha256=hashlib.sha256(b).hexdigest(), crlf_count=b.count(b"\r\n"), published_sha256=hashlib.sha256(lf).hexdigest())
    print(n, b.count(b"\r\n"), hashlib.sha256(lf).hexdigest()[:12])
ledger_path.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
