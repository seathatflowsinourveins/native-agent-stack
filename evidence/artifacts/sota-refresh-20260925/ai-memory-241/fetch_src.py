#!/usr/bin/env python3
"""Fetch files from akitaonrails/ai-memory at given refs via gh api (raw)."""
import subprocess, sys, pathlib
REPO = "akitaonrails/ai-memory"
out = pathlib.Path(__file__).resolve().parent / "src"
out.mkdir(exist_ok=True)
refs = sys.argv[1].split(",")
for path in sys.argv[2:]:
    for ref in refs:
        dest = out / f"{ref}__{path.replace('/', '_')}"
        if dest.exists():
            continue
        r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw",
                            f"repos/{REPO}/contents/{path}?ref={ref}"], capture_output=True)
        if r.returncode != 0:
            print("MISSING", ref, path, r.stderr.decode()[:200].strip())
            continue
        dest.write_bytes(r.stdout)
        print("OK", ref, path, len(r.stdout))
