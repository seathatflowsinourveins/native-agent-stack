#!/usr/bin/env python3
"""Fix-round preregistration (written after the independent review, before the fix-round checks ran).

Adds a separate `fix_round_preregistration` block to receipts 5, 12 and 7. The
original `preregistration` blocks are left untouched. Refuses to overwrite an
existing fix-round block so the timestamp cannot be moved later.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EV = REPO / "evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain"
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
LABEL = "fix round after independent Opus review; written before the fix-round checks ran"

GL = {
    "written_at": NOW, "label": LABEL,
    "expectation": ("(1) Every blob larger than 2 MB reachable from HEAD (the 163 docs/ecosystem/index.html versions "
                    "skipped by the 2 MB cap at ba3e7c2, plus any added since) is written with git cat-file into a "
                    "private temp directory and scanned with gitleaks-guarded dir --config .gitleaks.toml in batches "
                    "that stay under the guard's 600 s limit. Expected findings are content-digest-shaped values "
                    "(hex40/hex64) that also occur in other tracked files, as in the HEAD version. (2) Merge-resolution "
                    "content is scanned with gitleaks-guarded git --log-opts '--merges --diff-merges=first-parent HEAD' "
                    "--max-target-megabytes 2, which shows each merge's diff against its first parent (a superset of "
                    "resolution-only content); expected exit 0 or only findings already classified."),
    "criteria": [
        "size exclusion closed only if every listed blob is scanned (batch exit 0 or 1, never a final 75/143) and the scanned count equals the listed count",
        "each finding is classified by rule, value shape and whether the value occurs in HEAD-tracked files other than docs/ecosystem/index.html; any finding that is not digest-shaped or not found elsewhere is reported as unclassified and keeps the exclusion open",
        "oversized-blob detection method: a copy of one listed blob with an appended runtime-generated synthetic token (github-pat shape) must yield one more finding than the unmodified blob",
        "merge-resolution detection method: a temp repo whose merge resolution alone introduces a runtime-generated synthetic token; the default gitleaks git scan is expected to miss it and the --diff-merges=first-parent scan must find it",
        "merge-resolution exclusion closed only if the first-parent merge scan covers every merge commit reachable from HEAD (count cross-checked with git rev-list --merges --count HEAD) and its findings are classified",
        "the clauses 'does not certify that no secrets exist' (gap 5) and 'detection of every secret type' (gap 12) cannot be closed by a pattern scanner; if they are the only remainder the outcome stays advanced and names them as permanent limits",
    ],
}
CMP = {
    "written_at": NOW, "label": LABEL,
    "expectation": ("Committing the osv-scanner venv output (osv.json) shows results [] for the 21-package SBOM; the "
                    "quoted 'No known vulnerabilities found' is expected to come from pip-audit's stderr, not osv-scanner, "
                    "and is re-attributed. A committed helper recomputes the Syft vs Trivy inventory difference from the "
                    "committed raw files, both raw and after PEP 503 name normalization."),
    "criteria": [
        "osv arm: committed osv.json has an empty results array and osv-venv exit=0 in exits.log",
        "inventory arm: the normalized (PEP 503: lowercase, runs of [-_.] to '-') symmetric difference is empty; the raw difference is reported as found",
        "if the normalized difference is non-empty the receipt changes from settled to advanced",
    ],
}


def add(idx: int, block: dict) -> None:
    p = next(EV.glob(f"{idx}-*.json"))
    r = json.loads(p.read_text())
    if "fix_round_preregistration" in r:
        raise SystemExit(f"{p.name} already has a fix-round preregistration")
    r["fix_round_preregistration"] = block
    p.write_text(json.dumps(r, indent=2) + "\n")
    print(p.name, NOW)


for i in (5, 12):
    add(i, GL)
add(7, CMP)
