"""Independent exact permissions for synthetic Architecture test sources.

These grants are fixture code, never inferred from a selecting catalog/index.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
G5 = "research/coverage-gap-20261008/grand-catalog/start-closure-1-20261008T2140Z/class-ruling-20261009T0031Z/g5-landscape-evidence-2026-10-08.tar.zst"
REFRESH = "research/fullspeed-20261008/g5-stars-gap/local-pages/refresh-receipt.json"

def policy_fixture(path):
    document = json.loads((REPO / "tools/local-pages/source_policy.json").read_text())
    exact = {
        "architecture_manifest": ("repo", ["catalogs/landscape/manifest.json"]),
        "architecture_catalog": ("repo", ["catalogs/landscape/foundation.json", "catalogs/landscape/us-equities.json"]),
        "architecture_supplement": ("repo", ["catalogs/landscape/supplement.json", "catalogs/landscape/upstream-snapshot.json"]),
        "architecture_static": ("repo", ["catalogs/landscape/component-evidence-matrix.json"]),
        "architecture_registry": ("repo", ["manifests/evidence.json", "manifests/stack.json", "adoption/manifest.json"]),
        "architecture_readiness": ("repo", ["catalogs/north-star/readiness.json"]),
        "architecture_receipt": ("repo", ["evidence/receipts/exact-fixture.json", "evidence/receipts/redirected/receipt.json",
                                           "evidence/receipts/matrix-e2e.json", "evidence/receipts/older.json", "evidence/receipts/newer.json",
                                           "evidence/artifacts/exact/receipt.json", "evidence/hosts/fixture/receipt.json"]),
        "architecture_projection": ("state", [
            "coordination/command-center/pages/cc-now.json",
            "coordination/command-center/pages/adoption-now.json",
            "coordination/command-center/pages/automation-projection.json",
            "coordination/command-center/pages/host-receipts-index.json", REFRESH]),
        "architecture_skill_manifest": ("repo", ["adoption/skills/manifest.json"]),
        "architecture_design": ("user", [".agents/skills/frontend-design/SKILL.md"]),
        "architecture_g5_asset": ("state", [G5]),
    }
    document["architecture"] = {
        role: [{"root": root, "path": relative} for relative in paths]
        for role, (root, paths) in exact.items()
    }
    document["architecture_families"] = {
        "architecture_adoption_snapshot": {
            "root": "state",
            "directory": "coordination/ns2604-coop/notes/adoption-evidence-20261008",
            "filename": r"adoption-now-[a-f0-9]{16}\.json",
        }
    }
    path.write_text(json.dumps(document))
    return path

