"""Gap 7 fix round 2: rights clauses for the LEAN/QuantConnect bundled data this layer compared against.

Usage: python3 lean_rights.py LEAN_CHECKOUT QC_TERMS_HTML
Each clause is located by an exact anchor; missing anchors are listed and the script exits 1.
"""
import hashlib, html as H, json, re, subprocess, sys
from pathlib import Path

lean, qc = Path(sys.argv[1]), Path(sys.argv[2])


def flat(s):
    return re.sub(r"\s+", " ", s)


def page_text(p):
    s = p.read_text(encoding="utf-8", errors="replace")
    t = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", re.sub(r"<(script|style).*?</\1>", "", s, flags=re.S))))
    return re.sub(r"(\|\s*)+", "| ", t)


def clause(text, anchor, before=0, after=400):
    i = text.find(anchor)
    return None if i < 0 else text[max(0, i - before): i + len(anchor) + after].strip()


git = lambda *a: subprocess.run(["git", "-C", str(lean), *a], capture_output=True, text=True).stdout.strip()
used = ["Data/equity/usa/daily/aapl.zip", "Data/equity/usa/daily/ibm.zip", "Data/equity/usa/daily/spy.zip"]
lic = flat((lean / "LICENSE").read_text())
eq = flat((lean / "Data/equity/readme.md").read_text())
qct = page_text(qc)
anchors = {
    "lean_license_grant": (lic, "2. Grant of Copyright License.", 0, 520),
    "lean_license_redistribution": (lic, "4. Redistribution.", 0, 300),
    "lean_license_copyright_line": (lic, "Copyright 2014 QuantConnect Corporation", 0, 0),
    "lean_equity_data_source": (eq, "QuantConnect hosts US Equity Data (market 'USA') provided by", 0, 160),
    "qc_site_license": (qct, "2.1 License.", 0, 220),
    "qc_site_restrictions": (qct, "2.2 Certain Restrictions.", 0, 420),
    "qc_site_redistribute": (qct, "(xv) modify, distribute, redistribute or translate underlying works based on the Site", 0, 0),
}
out = {"lean_head": git("rev-parse", "HEAD"), "lean_head_date": git("log", "-1", "--format=%cI"),
       "files_used_by_this_layer": {f: {"tracked_in_git": bool(git("ls-files", f)),
                                        "sha256": hashlib.sha256((lean / f).read_bytes()).hexdigest()} for f in used},
       "data_specific_license_files": sorted(str(p.relative_to(lean)) for p in (lean / "Data").rglob("*")
                                             if p.is_file() and re.search(r"licen[cs]e|copying|notice|terms", p.name, re.I)),
       "data_readmes_mentioning_license_or_redistribution": sorted(str(p.relative_to(lean)) for p in (lean / "Data").rglob("*.md")
                                                                    if re.search(r"licen[cs]|redistribut", p.read_text(errors="replace"), re.I)),
       "clauses": {}, "missing_anchors": []}
for k, (txt, a, b, n) in anchors.items():
    c = clause(txt, a, b, n)
    out["clauses"][k] = c
    if c is None:
        out["missing_anchors"].append(k)
# Detection self-test: a made-up anchor must be reported missing.
out["self_test_missing_anchor_detected"] = clause(lic, "Data is licensed separately under", 0, 0) is None
print(json.dumps(out, indent=1, ensure_ascii=False))
sys.exit(1 if out["missing_anchors"] else 0)
