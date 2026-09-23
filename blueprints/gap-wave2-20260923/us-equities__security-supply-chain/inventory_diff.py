#!/usr/bin/env python3
"""Gap 7: recompute the Syft vs Trivy package inventory difference from the committed raw files.

Inputs: raw/compare/syft.summary.json (package_list) and raw/compare/trivy.json
(Results[].Packages). Output: raw/compare/inventory-diff.json with the raw
(name, version) difference and the difference after PEP 503 name normalization
(lowercase, runs of '-', '_' and '.' replaced by '-').
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CMP = REPO / "evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/raw/compare"


def pep503(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def compute() -> dict:
    syft = json.loads((CMP / "syft.summary.json").read_text())
    trivy = json.loads((CMP / "trivy.json").read_text())
    s = {(n, v) for _t, n, v in syft["package_list"]}
    t = {(p["Name"], p["Version"]) for r in trivy.get("Results", []) for p in r.get("Packages", [])}
    sn = {(pep503(n), v) for n, v in s}
    tn = {(pep503(n), v) for n, v in t}
    return {
        "inputs": ["raw/compare/syft.summary.json#package_list", "raw/compare/trivy.json#Results[].Packages"],
        "normalization": "PEP 503: re.sub(r'[-_.]+', '-', name).lower(); versions compared verbatim",
        "syft_packages": len(s), "trivy_packages": len(t),
        "raw": {"syft_only": sorted(s - t), "trivy_only": sorted(t - s), "both": len(s & t)},
        "normalized": {"syft_only": sorted(sn - tn), "trivy_only": sorted(tn - sn), "both": len(sn & tn)},
    }


def main() -> None:
    out = compute()
    (CMP / "inventory-diff.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("syft_packages", "trivy_packages", "raw", "normalized")}))


if __name__ == "__main__":
    main()
