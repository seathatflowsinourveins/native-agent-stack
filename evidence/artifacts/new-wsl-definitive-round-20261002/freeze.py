#!/usr/bin/env python3
"""Write preregistration.json: the sha256 of every frozen input of the definitive round and the time it was recorded.
Run once, before the first dossier or decision; --check verifies that nothing frozen has changed since."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ["criteria.txt", "units.json", "contenders.json", "build_units.py", "dossier-prompt.txt", "dossier-schema.json",
          "verify-prompt.txt", "verify-schema.json", "decide-prompt.txt", "decide-schema.json", "critic-prompt.txt",
          "critic-schema.json", "adjudicate-prompt.txt", "adjudicate-schema.json", "decision-rule.txt",
          "clean-room.json", "run_round.py"]
UPSTREAM = ["evidence/artifacts/new-wsl-definitive-defaults-20261001/criteria.txt",
            "evidence/artifacts/new-wsl-definitive-defaults-20261001/foundation-definitive.compact.json",
            "evidence/artifacts/upstream-audit-20261002/observations.json"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current() -> dict:
    return {"frozen": [{"file": f, "sha256": digest(HERE / f)} for f in FROZEN],
            "upstream_inputs": [{"file": f, "sha256": digest(ROOT / f)} for f in UPSTREAM]}


def main() -> int:
    target = HERE / "preregistration.json"
    if "--check" in sys.argv[1:]:
        recorded = json.loads(target.read_text(encoding="utf-8"))
        now = current()
        changed = [x["file"] for x, y in zip(recorded["frozen"] + recorded["upstream_inputs"],
                                              now["frozen"] + now["upstream_inputs"]) if x != y]
        print(json.dumps({"status": "changed" if changed else "unchanged", "changed": changed}))
        return 1 if changed else 0
    if target.exists():
        print("preregistration.json exists; it is never rewritten", file=sys.stderr)
        return 1
    data = {"schema_version": 1, "kind": "definitive_round_preregistration",
            "recorded_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "criteria_identical_to": "evidence/artifacts/new-wsl-definitive-defaults-20261001/criteria.txt",
            **current()}
    if data["frozen"][0]["sha256"] != data["upstream_inputs"][0]["sha256"]:
        print("criteria.txt differs from the #591 criteria", file=sys.stderr)
        return 1
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "recorded", "recorded_at_utc": data["recorded_at_utc"], "files": len(FROZEN)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
