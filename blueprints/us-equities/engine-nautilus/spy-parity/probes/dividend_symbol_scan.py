#!/usr/bin/env python3
"""Retained scan: every ``dividend`` symbol the installed 2.0.0rc5 wheel carries.

This is the evidence behind the ``distributions_and_cash`` mapping row. It scans
both layers of the installed distribution and prints every case-insensitive
``dividend`` match, so the manifest cites what is actually present rather than a
summary of it:

* the interface stubs and shipped Python modules, by file and line;
* the compiled ``_libnautilus`` extension, by byte offset with a bounded
  printable context, since the Rust layer ships as one binary with no source.

Binary matches are context slices, not symbol declarations: a name appearing in
the extension only shows that the string is present, never that a postable
backtest cash event exists.

Run it under the pinned interpreter:

    "$NENV/bin/python" -I .../probes/dividend_symbol_scan.py
"""
from __future__ import annotations

import importlib.metadata
import json
import re
import sys
from pathlib import Path

TEXT_PATTERN = re.compile(r"dividend", re.IGNORECASE)
BINARY_PATTERN = re.compile(rb"dividend", re.IGNORECASE)
CONTEXT = 40
PRINTABLE = re.compile(rb"[^\x20-\x7e]")


def scan_text(root: Path) -> list:
    matches = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".py", ".pyi") or not path.is_file():
            continue
        for number, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
            if TEXT_PATTERN.search(line):
                matches.append({"file": str(path.relative_to(root)), "line": number,
                                "text": line.strip()[:200]})
    return matches


def scan_binary(path: Path) -> list:
    blob = path.read_bytes()
    seen, matches = set(), []
    for found in BINARY_PATTERN.finditer(blob):
        start = max(0, found.start() - CONTEXT)
        chunk = blob[start:found.end() + CONTEXT]
        context = PRINTABLE.sub(b".", chunk).decode("ascii")
        if context in seen:
            continue
        seen.add(context)
        matches.append({"offset": found.start(), "matched": found.group().decode("ascii"),
                        "context": context})
    return matches


def main() -> dict:
    import nautilus_trader

    root = Path(nautilus_trader.__file__).resolve().parent
    extensions = sorted(root.glob("*.so"))
    binary = []
    for extension in extensions:
        binary += [dict(m, file=extension.name) for m in scan_binary(extension)]
    text = scan_text(root)
    suffixes = [p.suffix for p in root.rglob("*") if p.suffix in (".py", ".pyi")]
    return {"probe": "dividend_symbol_scan",
            "engine_version": importlib.metadata.version("nautilus_trader"),
            "python": sys.version.split()[0],
            "scanned_root": str(root),
            "scanned_files": {"py": suffixes.count(".py"), "pyi": suffixes.count(".pyi"),
                              "so": [e.name for e in extensions]},
            "source_match_count": len(text), "source_matches": text,
            "binary_match_count": len(binary), "binary_matches": binary}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
