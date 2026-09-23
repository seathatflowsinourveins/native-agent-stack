"""Copy existing raw outputs cited by the document-retrieval gap-wave-2 receipts into the evidence dir.
Host paths -> $HOME, UUID session ids -> <session-id-redacted>. Records source and committed sha256.
Binary or third-party files are recorded hash-only (not committed) with a reason."""
import hashlib, json, os, re, datetime
HOME = os.path.expanduser("~")
SRC = os.path.join(HOME, ".cache/gap-wave2-20260923/document-retrieval")
DST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "raw")
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
commit = {  # relative path under SRC -> gap
 "bench-out/run-cold-1.json": 0, "bench-out/run-cold-1.stderr": 0, "bench-out/run-cold-2.json": 0,
 "bench-out/run-cold-2.stderr": 0, "bench-out/run-cold-3.json": 0, "bench-out/run-cold-3.stderr": 0,
 "bench-out/nocol.json": 0, "bench-out/nocol.stderr": 0,
 "freshness-corpus/doc1.md": 2, "freshness-corpus/doc2.md": 2, "freshness-corpus/doc3.md": 2,
 "freshness-corpus/doc4.md": 2, "freshness-corpus/doc5-epsilon.md": 2,
 "pdf-fixtures/make_multicol.py": 3, "pdf-fixtures/multicol-layout.txt": 3, "pdf-fixtures/multicol-plain.txt": 3,
 "pdf-fixtures/scanned-only.txt": 3,
 "e2e-blind/arm-noretrieval.out": 5, "e2e-blind/arm-withretrieval.out": 5,
}
hash_only = {
 "qmd-disposable/catalog-snapshot.sqlite": (0, "1.7 MB copy of the sealed snapshot; sealed original stays outside the repo"),
 "pdf-fixtures/multicol.pdf": (3, "PDF; repository validator requires a PDF review record for committed PDFs"),
 "pdf-fixtures/lumen-qualification.pdf": (3, "copy of checked-in blueprints/convergence-practice/document-ingestion/corpus/lumen-qualification.pdf"),
 "pdf-fixtures/scanpage-1.png": (3, "render of the checked-in lumen PDF page 1"),
 "pdf-fixtures/scanpage-2.png": (3, "render of the checked-in lumen PDF page 2"),
 "pdf-fixtures/scanned-only.pdf": (3, "PDF; image-only wrap of scanpage-1.png; validator requires a PDF review record"),
 "pdf-fixtures/annual-report.pdf": (3, "third-party copyrighted PDF (Berkshire Hathaway 2022 letter); public URL in receipt"),
 "pdf-fixtures/annual-report-layout.txt": (3, "full pdftotext output of third-party copyrighted text; only the cited lines are committed as annual-report-layout.excerpt.txt"),
 "mk-fixtures/fixture.docx": (4, "binary; validator scans committed evidence as UTF-8"),
 "mk-fixtures/fixture.xlsx": (4, "binary; validator scans committed evidence as UTF-8"),
 "mk-fixtures/fixture.pptx": (4, "binary; validator scans committed evidence as UTF-8"),
 "mk-fixtures/fixture.pdf": (4, "copy of checked-in lumen-qualification.pdf"),
}
def sha(b): return hashlib.sha256(b).hexdigest()
def mtime(p): return datetime.datetime.fromtimestamp(os.stat(p).st_mtime, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
entries = []
for rel, gap in commit.items():
    p = os.path.join(SRC, rel); raw = open(p, "rb").read()
    text = raw.decode("utf-8").replace(HOME, "$HOME")
    redacted = len(UUID.findall(text)); text = UUID.sub("<session-id-redacted>", text)
    dest = rel
    if rel.endswith(".json"):  # a not-JSON capture (e.g. empty stdout) is retained as .json.txt
        try: json.loads(text)
        except ValueError: dest = rel + ".txt"
    out = os.path.join(DST, dest); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(text)
    entries.append({"gap_index": gap, "source": "$HOME/.cache/gap-wave2-20260923/document-retrieval/" + rel,
        "source_sha256": sha(raw), "source_bytes": len(raw), "source_mtime_utc": mtime(p),
        "committed_path": "raw/" + dest, "committed_sha256": sha(text.encode()),
        "sanitized": {"home_path_to_$HOME": HOME in raw.decode(), "uuid_session_ids_redacted": redacted}})
# excerpt of third-party layout text: only lines the receipt cites
lay = os.path.join(SRC, "pdf-fixtures/annual-report-layout.txt"); lines = open(lay, encoding="utf-8").read().splitlines()
keep = [f"{i+1}: {l}" for i, l in enumerate(lines) if i < 8 or 63 <= i <= 64 or "Warren E. Buffett" in l or "Charlie Munger, my long-time partner" in l]
ex = "# Lines of annual-report-layout.txt (sha256 %s) lines 1-8 and 64-65 (performance table header, first rows and summary rows) plus the lines matching the two phrases cited in receipt 3; line-numbered.\n" % sha(open(lay, "rb").read()) + "\n".join(keep) + "\n"
open(os.path.join(DST, "pdf-fixtures/annual-report-layout.excerpt.txt"), "w").write(ex)
entries.append({"gap_index": 3, "source": "$HOME/.cache/gap-wave2-20260923/document-retrieval/pdf-fixtures/annual-report-layout.txt",
    "committed_path": "raw/pdf-fixtures/annual-report-layout.excerpt.txt", "committed_sha256": sha(ex.encode()),
    "note": "excerpt only: table lines 1-8 and 64-65 plus the two phrase-matching lines; remaining third-party text not committed"})
for rel, (gap, why) in hash_only.items():
    p = os.path.join(SRC, rel); raw = open(p, "rb").read()
    entries.append({"gap_index": gap, "source": "$HOME/.cache/gap-wave2-20260923/document-retrieval/" + rel,
        "source_sha256": sha(raw), "source_bytes": len(raw), "source_mtime_utc": mtime(p), "committed_path": None, "not_committed_reason": why})
json.dump({"generated_by": "store_raw.py during the 2026-09-23 reconciliation round (copies existing files only; no check re-run)",
    "mtime_note": "source_mtime_utc is the file's last-modification time on this host, used as the only surviving wall-clock evidence of when each step wrote its output.",
    "files": entries}, open(os.path.join(DST, "raw-manifest.json"), "w"), indent=2)
open(os.path.join(DST, "raw-manifest.json"), "a").write("\n")
print(len(entries), "entries")
