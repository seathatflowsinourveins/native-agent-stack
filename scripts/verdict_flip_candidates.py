#!/usr/bin/env python3
"""Report layer winners whose evidence-derived per-platform status outranks what
catalogs/landscape/{foundation,us-equities}.json currently declares.

Read-only and report-only: this never edits a landscape file, a verdict or a
``platform_status`` field. For every winner and platform in both catalogs it calls
``scripts/platform_status.py``'s ``platform_status()`` -- the one function
``scripts/landscape.py``, ``scripts/component_matrix.py`` and
``tools/sota-convergence/record_verdicts.py`` all use for this -- and lists every row where
the recorded host receipts and evidence now support a stronger status than the row declares,
with the receipts that qualify. A flip only happens when someone runs
``tools/sota-convergence/record_verdicts.py`` to re-record that layer through its own lane
process; this script cannot do that and does not try to.

``scripts/component_matrix.py --check`` already fails CI when a declared ``macos-arm64``
status *exceeds* the evidence (the flip rule, enforced only for
``scripts/landscape.ENFORCED_PLATFORMS``). This is the opposite and unenforced direction:
a declaration that is merely *behind* the evidence is allowed by that rule (a weaker,
not-yet-re-recorded status is conservative, never wrong) and for the platform(s) outside
``ENFORCED_PLATFORMS`` (currently ``linux-wsl2-x86_64``) nothing else surfaces it either. This
script covers both platforms so a Linux row that could now flip is visible too, not just macOS.

Exit code: 0 whenever the two landscape files can be read and parsed as JSON, whatever it
finds -- this is a report, not a gate. Nonzero only when the input itself is
missing/unreadable/malformed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from . import platform_status as platform_evidence
    from .landscape import PLATFORM_KEYS
except ImportError:  # running as a plain script, not a package
    import platform_status as platform_evidence
    from landscape import PLATFORM_KEYS

ROOT = Path(__file__).resolve().parent.parent
LANDSCAPE_FILES = {
    "foundation": "catalogs/landscape/foundation.json",
    "us-equities": "catalogs/landscape/us-equities.json",
}


def find_candidates(root: Path, context: platform_evidence.StatusContext | None = None) -> list[dict]:
    """One entry per (catalog, layer, winner, platform) whose derived status outranks the
    declared ``platform_status``. Raises ``OSError``/``ValueError`` on unreadable or
    non-JSON input; a malformed-but-parseable document (missing fields) is tolerated and
    simply skipped for the affected winner/platform, since this is a report, not a gate."""
    if context is None:
        context = platform_evidence.load_context(root)
    candidates: list[dict] = []
    for catalog, relative in LANDSCAPE_FILES.items():
        document = json.loads((root / relative).read_text(encoding="utf-8"))
        for layer in document.get("layers", []) or []:
            if not isinstance(layer, dict):
                continue
            layer_id = layer.get("layer_id")
            for winner in layer.get("winners", []) or []:
                if not isinstance(winner, dict) or not isinstance(winner.get("component_id"), str):
                    continue
                component_id = winner["component_id"]
                declared_map = winner.get("platform_status") if isinstance(winner.get("platform_status"), dict) else {}
                for platform_key in sorted(PLATFORM_KEYS):
                    declared = declared_map.get(platform_key, "untested")
                    derived = platform_evidence.platform_status(platform_key, winner, context)
                    declared_rank = platform_evidence.STATUS_RANK.get(declared, -1)
                    derived_rank = platform_evidence.STATUS_RANK.get(derived.status, 0)
                    if derived_rank > declared_rank:
                        candidates.append({
                            "catalog": catalog,
                            "layer_id": layer_id,
                            "component_id": component_id,
                            "platform": platform_key,
                            "declared_status": declared,
                            "derived_status": derived.status,
                            "reason": derived.reason,
                            # The receipts behind the derived status: reviewed use passes for accepted, the
                            # supporting passes (install-only among them) for conditional (#164 review, item 4).
                            "supporting_receipts": list(derived.receipt_refs),
                        })
    candidates.sort(key=lambda c: (c["catalog"], c["layer_id"], c["component_id"], c["platform"]))
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        candidates = find_candidates(root)
    except (OSError, ValueError) as error:
        print(f"verdict_flip_candidates: malformed input ({type(error).__name__}: {error})", file=sys.stderr)
        return 1

    document = {
        "schema_version": 1,
        "scope": (
            "Report-only: layer-winner-platform rows whose recorded evidence "
            "(scripts/platform_status.py) now supports a stronger platform_status than "
            "catalogs/landscape/{foundation,us-equities}.json declares. Covers both platforms "
            "(scripts/landscape.ENFORCED_PLATFORMS gates only macos-arm64 in the other "
            "direction). This tool selects nothing, records nothing and changes no verdict; a "
            "flip needs tools/sota-convergence/record_verdicts.py to re-record the layer "
            "through its own lane process."
        ),
        "flip_instructions": (
            "For each row below, re-record the named catalog/layer with "
            "tools/sota-convergence/record_verdicts.py so its lane process can write the "
            "stronger platform_status; this report only lists candidates, it does not flip "
            "anything itself."
        ),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
