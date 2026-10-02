#!/usr/bin/env python3
"""Assemble the definitive round's record from a private run directory, under decision-rule.txt.

Writes into this folder:
- ``selection.json``: per unit and slot, each family's post-critic pick, the agreement, the adjudications where they ran,
  and the slot's outcome: ``definitive`` (one field key or NONE), ``measurement`` (two finalists and the measurement
  that settles them) or ``user_pin_conflict`` (a definitive result that differs from a user pin, put to the user);
- ``dossiers/<contender>.json``: the verified dossiers, sanitized (no host paths);
- ``run-record.json``: every attempt with exit, duration and returned usage, the sha256 of each private original, and a
  contamination audit of the raw returns.

Usage: assemble.py --work <private run dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_round as rr  # noqa: E402

USER_PINS = {"gpt-gateway": "diegosouzapw/omniroute", "agent-runtime-worker": "openhands/software-agent-sdk",
             "deep-research-harness": "assafelovic/gpt-researcher"}
PRIVATE = re.compile(r"/(?:Users|home|private/tmp|var/folders)/[^\s\"']+")
LEAK_TERMS = ("native-agent-stack", "seathatflowsinourveins")


def scrub(value):
    if isinstance(value, str):
        return PRIVATE.sub("<private>", value)
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    return value


def key_to_contender(unit: dict) -> dict:
    return {f["key"]: f["contender"] for f in unit["field"]}


def outcome(unit: dict, slot: dict, picks: dict, adjudications: list) -> dict:
    keys = key_to_contender(unit)
    c, g = picks["claude"], picks["gpt"]
    if c is not None and c == g:
        result = {"status": "definitive", "basis": "both families", "default": c}
    else:
        resolved = [a["resolved_default"] for a in adjudications if a.get("result")]
        if len(adjudications) == 4 and len(resolved) == 4 and len(set(resolved)) == 1 and resolved[0] is not None:
            result = {"status": "definitive", "basis": "adjudicated (four of four)", "default": resolved[0]}
        else:
            finalists = sorted({x for x in (c, g) if x})
            measurement = next((a["result"].get("settling_measurement") for a in adjudications
                                if a.get("result") and a["result"].get("settling_measurement")), None)
            result = {"status": "measurement", "basis": "unsettled after adjudication", "finalists": finalists,
                      "settling_measurement": measurement}
    if result["status"] == "definitive":
        result["contender"] = None if result["default"] == "NONE" else keys.get(result["default"])
        pin = USER_PINS.get(slot["slot_id"])
        if pin and result["contender"] != pin:
            result = dict(result, status="user_pin_conflict", user_pin=pin)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--work", required=True, type=Path)
    args = parser.parse_args(argv)
    work = args.work.resolve()
    selection, attempts, originals = [], [], []
    for unit in rr.units():
        fams = {fam: rr.family_picks(work, fam, unit["unit_id"]) for fam in ("claude", "gpt")}
        slots = []
        for slot in unit["slots"]:
            picks = {fam: fams[fam]["picks"].get(slot["slot_id"]) for fam in fams}
            adj = []
            for fam in ("claude", "gpt"):
                for order in ("AB", "BA"):
                    p = work / "adjudications" / fam / f"{rr.safe(unit['unit_id'])}.{slot['slot_id']}.{order}.json"
                    if p.is_file():
                        adj.append(rr.load(p))
            slots.append({"slot_id": slot["slot_id"], "question": slot["question"], "picks": picks,
                          "agreement": "agree" if picks["claude"] is not None and picks["claude"] == picks["gpt"] else "differ",
                          "adjudications": [{k: a.get(k) for k in ("family", "order", "return_a_family", "resolved_default")}
                                            | {"choice": (a.get("result") or {}).get("choice")} for a in adj],
                          "outcome": outcome(unit, slot, picks, adj)})
        selection.append({"unit_id": unit["unit_id"], "field": [{k: f[k] for k in ("key", "name", "contender")}
                                                                for f in unit["field"]], "slots": slots})
    for path in sorted(work.rglob("*.json")):
        if path.parts[-2:] and "clones" in path.parts:
            continue
        rel = path.relative_to(work).as_posix()
        if rel.startswith(("raw/", "decisions/", "critics/", "adjudications/", "dossiers/")):
            originals.append({"file": rel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            try:
                record = rr.load(path)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(record, dict) and "attempts" in record:
                attempts.append({"file": rel, "attempts": record["attempts"]})
    leaks = []
    for raw in sorted((work / "raw").rglob("*")) if (work / "raw").exists() else []:
        if raw.is_file():
            text = raw.read_text(encoding="utf-8", errors="replace")
            for term in LEAK_TERMS:
                if term in text:
                    leaks.append({"file": raw.relative_to(work).as_posix(), "term": term})
    (HERE / "dossiers").mkdir(exist_ok=True)
    for path in sorted((work / "dossiers").glob("*.json")):
        rec = rr.load(path)
        rr.dump(HERE / "dossiers" / path.name, scrub({"contender": rec["contender"], "revision": rec["meta"],
                                                       "dossier": rec.get("dossier"), "repaired": rec.get("repaired"),
                                                       "verification": [v.get("result") for v in rec["verification"]]}))
    counts = {}
    for u in selection:
        for s in u["slots"]:
            counts[s["outcome"]["status"]] = counts.get(s["outcome"]["status"], 0) + 1
    rr.dump(HERE / "selection.json", scrub({"schema_version": 1, "kind": "definitive_round_selection",
                                            "decision_rule": "decision-rule.txt", "counts": counts, "units": selection}))
    rr.dump(HERE / "run-record.json", scrub({"schema_version": 1, "kind": "definitive_round_run_record",
                                             "attempts": attempts, "private_originals": originals,
                                             "contamination_audit": {"terms": list(LEAK_TERMS), "hits": leaks}}))
    print(json.dumps({"slots": sum(len(u["slots"]) for u in selection), "outcomes": counts, "leaks": len(leaks)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
