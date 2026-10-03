#!/usr/bin/env python3
"""Write preregistration.json: the sha256 of every frozen input of the definitive round and the time it was recorded.
Run once, before the first dossier or decision; --check verifies that nothing frozen has changed since, except through
the recorded amendments (preregistration-amendment-<n>.json, applied in order: each change must start from the hash its
predecessor left, and each added file must still have its recorded hash)."""
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


def amendments() -> list:
    paths = sorted(HERE.glob("preregistration-amendment-*.json"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def check(recorded: dict) -> dict:
    expected = {x["file"]: x["sha256"] for x in recorded["frozen"]}
    upstream = {x["file"]: ROOT / x["file"] for x in recorded["upstream_inputs"]}
    breaks, amended = [], []
    for a in amendments():
        # A relocated upstream input is read from a copy in this folder, which must keep the frozen hash.
        for rel in a.get("relocated_upstream") or []:
            upstream[rel["file"]] = HERE / rel["copy"]
            amended.append(f"{rel['file']} read from {rel['copy']} (amendment {a['amendment']})")
        # Amendment 1 names one changed file at its top level; later amendments list "changes" and "added".
        changes = a.get("changes") or ([{k: a[k] for k in ("file", "sha256_before", "sha256_after")}]
                                       if a.get("file") else [])
        for ch in changes:
            if expected.get(ch["file"]) != ch["sha256_before"]:
                breaks.append(f"{ch['file']}: amendment {a['amendment']} starts from a hash nothing earlier left")
            expected[ch["file"]] = ch["sha256_after"]
            amended.append(f"{ch['file']} (amendment {a['amendment']})")
        for add in a.get("added") or []:
            # Amendment 5: an addition may not replace a file that is already frozen; that must be a change.
            if add["file"] in expected:
                breaks.append(f"{add['file']}: amendment {a['amendment']} adds a file that is already frozen")
                continue
            expected[add["file"]] = add["sha256"]
            amended.append(f"{add['file']} (added by amendment {a['amendment']})")
    changed = [f for f, sha in expected.items() if not (HERE / f).is_file() or digest(HERE / f) != sha]
    changed += [x["file"] for x in recorded["upstream_inputs"]
                if not upstream[x["file"]].is_file() or digest(upstream[x["file"]]) != x["sha256"]]
    status = "chain_broken" if breaks else "changed" if changed else "unchanged"
    return {"status": status, "changed": changed, "breaks": breaks, "amended": amended}


def main() -> int:
    target = HERE / "preregistration.json"
    if "--check" in sys.argv[1:]:
        result = check(json.loads(target.read_text(encoding="utf-8")))
        print(json.dumps(result))
        return 0 if result["status"] == "unchanged" else 1
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
