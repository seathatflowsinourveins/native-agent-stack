"""Summarize the withheld-files check (withheld-{proposed,amended}-*.log) into withheld-check.json, from the logs.

usage: withheld_summary.py
"""
import json
import re
from pathlib import Path

X = Path(__file__).resolve().parent
WITHHELD = ["docs/decisions/2026-09-27-prompt-audit-resolution.md", "evidence/artifacts/prompt-audit-20260927/"]
out = {"withheld": WITHHELD}
for tree in ("proposed", "amended"):
    lines = (X / f"withheld-{tree}-validate.log").read_text().splitlines()
    assert lines[0] == "Publication validation failed:"
    paths = [ln.rsplit(": ", 1)[0] for ln in lines[1:] if not ln.startswith("files[")]
    assert all(ln.endswith(": file missing") for ln in lines[1:]), "a validate line is not 'file missing'"
    assert all(p == WITHHELD[0] or p.startswith(WITHHELD[1]) for p in paths), "a missing file is not withheld"
    out.setdefault("missing_entries", len(paths))
    assert out["missing_entries"] == len(paths)
    t = (X / f"withheld-{tree}-targeted.log").read_text()
    ran, ok = re.search(r"^Ran (\d+) tests", t, re.M).group(1), re.search(r"^OK \(skipped=(\d+)\)$", t, re.M)
    out.setdefault("targeted", f"Ran {ran} tests, OK (skipped={ok.group(1)})")
    assert out["targeted"] == f"Ran {ran} tests, OK (skipped={ok.group(1)})"
full = re.search(r"^OK \(skipped=(\d+)\)$", (X / "x5c-amend-targeted-tests.log").read_text(), re.M).group(1)
out["extra_skips"] = int(re.search(r"skipped=(\d+)", out["targeted"]).group(1)) - int(full)
diff = [ln for ln in (X / "withheld-amended-skips.txt").read_text().splitlines() if "is not in this clone" in ln
        or "baseline commit" in ln]
out["extra_skip_reasons"] = sorted({re.sub(r"^.*skipped '([^']*)'.*$", r"\1", ln)[:60] for ln in diff})
(X / "withheld-check.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out))
