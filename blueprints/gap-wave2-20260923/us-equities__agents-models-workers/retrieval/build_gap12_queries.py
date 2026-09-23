#!/usr/bin/env python3
"""Build the gap-12 source-recovery query set with exhaustive, pattern-defined gold.

Each query is a natural-language description of a code concern. Its gold set is
EVERY line in the frozen corpus (scripts/*.py at the base commit) matched by the
query's regex. Relevance is therefore operationally defined by the pattern, and the
gold list is exhaustive for that definition (computed by a full scan, not judged).
The query text deliberately avoids naming the matched identifier where possible.

Usage: build_gap12_queries.py CORPUS_ROOT OUT_JSON
"""
import hashlib
import json
import re
import sys
from pathlib import Path

QUERIES = [
    ("dupkey", "Where does the code load JSON while rejecting duplicate object keys?", r"object_pairs_hook"),
    ("sha256", "Every place that computes a SHA-256 digest of bytes or text.", r"hashlib\.sha256"),
    ("subproc", "Every place that launches an external process or command.", r"subprocess\.(run|check_output|Popen|call)\("),
    ("envread", "Every place that reads the process environment variables.", r"os\.environ|os\.getenv"),
    ("urlparse", "Every place that splits a URL into its scheme, host and path components.", r"urlsplit\("),
    ("argparse", "Every command-line argument parser that is constructed.", r"argparse\.ArgumentParser\("),
    ("recompile", "Every precompiled regular expression pattern.", r"re\.compile\("),
    ("sysexit", "Every place the program terminates by raising an exit status.", r"raise SystemExit"),
    ("filerel", "Every place that locates the repository relative to the running script file.", r"Path\(__file__\)"),
    ("writes", "Every place that writes text or bytes to a file on disk.", r"\.write_text\(|\.write_bytes\("),
    ("glob", "Every recursive filesystem pattern walk over files.", r"\.glob\(|\.rglob\(|glob\.glob"),
    ("htmlesc", "Where is text escaped before being inserted into HTML?", r"html\.escape"),
    ("tempdir", "Where is a temporary working directory created?", r"tempfile\."),
    ("exccls", "Every custom exception class declared for validation failures.", r"^class \w+\((ValueError|Exception|RuntimeError|TypeError)\)"),
    ("isodate", "Every place that parses an ISO-8601 date or timestamp string.", r"fromisoformat|strptime"),
    ("urlcheck", "Functions that validate a URL is public HTTPS or a loopback address.", r"def (https|https_url|public_url|loopback_url)\("),
    ("require", "Small helper functions that raise an error when a condition is false.", r"def require\("),
    ("canonical", "Functions that produce a canonical, deterministic JSON serialization.", r"def canonical(_json)?\("),
    ("gitrev", "Where does the code ask git for the current revision or top-level directory?", r"rev-parse"),
    ("digestdef", "Helper functions that return a hex digest for a file or byte string.", r"def digest\("),
    ("png", "Where are PNG image signatures or structures checked?", r"x89PNG|is_structural_png\("),
    ("pdf", "Where is PDF file framing (header and end-of-file marker) checked?", r"%PDF|%%EOF"),
    ("pointer", "Functions that resolve a JSON-pointer-like path inside a document.", r"def pointer\("),
    ("uniquejson", "Functions used as JSON object hooks that reject repeated keys.", r"def unique_json\(|def _json_without_duplicates\("),
    ("loopback", "Where are localhost or 127.0.0.1 hostnames recognised?", r"127\.0\.0\.1|localhost"),
    ("dateregex", "Regular expressions that match a calendar date in year-month-day form.", r"\\d\{4\}-\\d\{2\}-\\d\{2\}"),
    ("hexregex", "Regular expressions that match a 64-character lowercase hex checksum.", r"\[0-9a-f\]\{64\}|\[a-f0-9\]\{64\}"),
    ("archive", "Where is a tar archive opened or inspected?", r"tarfile"),
    ("printjson", "Every place that prints a JSON result document to standard output.", r"print\(json\.dumps"),
    ("which", "Where does the code check whether a command is installed on PATH?", r"shutil\.which"),
    ("csvread", "Where are CSV report rows read?", r"csv\.DictReader"),
    ("render", "Where is the final HTML page rendered from data?", r"def render\("),
]


def main() -> int:
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    files = sorted(p for p in root.glob("scripts/*.py"))
    corpus = {str(p.relative_to(root)): p.read_text(encoding="utf-8").splitlines() for p in files}
    items = []
    for qid, text, pattern in QUERIES:
        rx = re.compile(pattern)
        gold = [{"file": f, "line": i + 1} for f, lines in corpus.items()
                for i, line in enumerate(lines) if rx.search(line)]
        if not gold:
            raise SystemExit(f"empty gold for {qid}")
        items.append({"id": qid, "query": text, "gold_pattern": pattern,
                      "gold_locations": gold, "gold_count": len(gold)})
    corpus_sha = hashlib.sha256("".join(
        f"{f}\n{hashlib.sha256(chr(10).join(l).encode()).hexdigest()}\n" for f, l in corpus.items()
    ).encode()).hexdigest()
    doc = {"description": __doc__.strip().splitlines()[0], "corpus_files": list(corpus),
           "corpus_manifest_sha256": corpus_sha, "query_count": len(items), "queries": items}
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"queries": len(items), "gold_total": sum(i["gold_count"] for i in items),
                      "corpus_files": len(corpus)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
