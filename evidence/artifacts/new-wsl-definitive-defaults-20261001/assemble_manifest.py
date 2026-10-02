#!/usr/bin/env python3
"""Build definitive-manifest.json: one row per slot of the new WSL architecture, across both catalogs.

It reads the two committed compact documents and settlements in this folder and writes a flat table next to them. The output is
deterministic: running it again over unchanged inputs writes the same bytes.

Usage: assemble_manifest.py [--check]
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FOUNDATION = HERE / "foundation-definitive.compact.json"
TRADING = HERE / "trading" / "trading-definitive.compact.json"
SETTLEMENTS = HERE / "settlements.json"
OUT = HERE / "definitive-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def family_status(slot, family):
    fam = (slot.get("families") or {}).get(family)
    if fam:
        return fam.get("status", "returned")
    block = slot.get(family)
    if isinstance(block, dict):
        return block.get("status", "returned")
    return "not judged"


def rows_of(catalog, layer, slot):
    """One row per default. A slot that holds several roles, or names several tools with distinct roles, gives one row each."""
    if "roles" in slot:
        out = []
        for role in slot["roles"]:
            out.extend(rows_of(catalog, layer, dict(role, slot_id=f"{slot['slot_id']}/{role['slot_id']}")))
        return out
    default = slot.get("default")
    if isinstance(default, list):
        out = []
        for part in default:
            tail = "".join(c if c.isalnum() else "-" for c in part["name"].lower()).strip("-")[:32]
            out.extend(rows_of(catalog, layer, dict(slot, default=part, slot_id=f"{slot['slot_id']}/{tail}")))
        return out
    default = default or {}
    name = default.get("name", "")
    if "installs_nothing_extra" in default:
        nothing = bool(default["installs_nothing_extra"])
    else:
        nothing = name.lower().startswith(("no ", "not installed", "none"))
    # A slot whose single finalist the first round upheld is a first-round row, whichever catalog it is in.
    kind = "first_round" if slot["row_kind"] == "judged" and slot.get("decision_stage") == "first_round" else slot["row_kind"]
    state = ("definitive" if slot.get("definitive") else "measurement" if slot.get("decided_by_measurement_at_user_request")
             else "split" if slot.get("split") else "")
    return [{
        "catalog": catalog, "layer_id": layer["layer_id"], "slot_id": slot["slot_id"], "row_kind": kind,
        "default": name, "repository": default.get("repository", ""), "installs_nothing_extra": nothing,
        "definitive": bool(slot.get("definitive")), "label": slot.get("label") or slot.get("reason", ""),
        "state": state,
        "measurement": {"returned": False, "receipts": []} if state in ("split", "measurement") else None,
        # Whether the default coincides with what the owning lane's record already names. The trading lane states it per
        # slot; the foundation rows do not carry it yet (None), and the record names the foundation's coincidences in prose.
        "coincides_with_lane_record": (slot.get("lane_record") or {}).get("coincides"),
        "claude": family_status(slot, "claude"), "gpt": family_status(slot, "gpt"),
    }]


def apply_settlements(rows):
    seen = set()
    for settlement in json.loads(SETTLEMENTS.read_text(encoding="utf-8")):
        sid = settlement["slot_id"]
        matches = [row for row in rows if row["slot_id"] == sid]
        if len(matches) != 1 or matches[0]["state"] not in ("split", "measurement"):
            raise ValueError(f"settlement {sid}: not a split or measurement row")
        if sid in seen:
            raise ValueError(f"settlement {sid}: duplicate slot")
        seen.add(sid)
        if not settlement["receipts"]:
            raise ValueError(f"settlement {sid}: no receipts")
        for receipt in settlement["receipts"]:
            path = ROOT / receipt["path"]
            if not path.is_file():
                raise ValueError(f"settlement {sid}: receipt missing: {receipt['path']}")
            if sha(path) != receipt["sha256"]:
                raise ValueError(f"settlement {sid}: receipt sha256 mismatch: {receipt['path']}")
        matches[0].update({"state": "measurement", "default": settlement["default"]["name"],
                           "repository": settlement["default"]["repository"], "installs_nothing_extra": False,
                           "definitive": False, "label": settlement["label"],
                           "measurement": {"returned": True, "receipts": settlement["receipts"]}})


def build():
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    trading = json.loads(TRADING.read_text(encoding="utf-8"))
    rows = []
    for layer in foundation["layers"] + foundation["cross_rows"]:
        for slot in layer["slots"]:
            rows.extend(rows_of("foundation", layer, slot))
    for layer in trading["layers"]:
        for pin in trading.get("pinned_requirements", []):
            if pin["owner"] == layer["layer_id"]:
                rows.append({"catalog": "us-equities", "layer_id": layer["layer_id"],
                             "slot_id": "pinned/" + "".join(c if c.isalnum() else "-" for c in pin["name"].lower()).strip("-")[:40],
                             "row_kind": "pinned", "default": pin["name"], "repository": "", "installs_nothing_extra": False,
                             "definitive": False, "label": "a requirement the user selected; carried with its committed receipts, never judged",
                             "state": "", "measurement": None,
                             "claude": "not judged", "gpt": "not judged"})
        for slot in layer.get("slots", []):
            rows.extend(rows_of("us-equities", layer, slot))
    apply_settlements(rows)
    layers = [{"catalog": "foundation", "layer_id": l["layer_id"], "owns": l["owns"], "uses": l["uses"]}
              for l in foundation["layers"] + foundation["cross_rows"]]
    layers += [{"catalog": "us-equities", "layer_id": l["layer_id"], "owns": l["owns"], "uses": l["uses"]} for l in trading["layers"]]
    by_kind = {}
    for r in rows:
        by_kind[r["row_kind"]] = by_kind.get(r["row_kind"], 0) + 1
    doc = {
        "schema_version": 1, "kind": "new-wsl-definitive-manifest", "date_utc": "2026-10-01",
        "meaning": "one default per slot for the clean install of the new WSL distribution; a definitive default is the slot's install decision, "
                   "agreed by both model families, and is not a merit acceptance",
        "decision_rule": foundation["decision_rule"],
        "no_install_rule": foundation["no_install_rule"],
        "not_claimed": foundation["not_claimed"],
        "sources": {"foundation": {"file": FOUNDATION.name, "sha256": sha(FOUNDATION)},
                    "us-equities": {"file": "trading/" + TRADING.name, "sha256": sha(TRADING), "owner": trading["owner"]},
                    "settlements": {"file": SETTLEMENTS.name, "sha256": sha(SETTLEMENTS)}},
        "counts": {"layers": len(layers), "slots": len(rows), "definitive": sum(1 for r in rows if r["definitive"]), "by_row_kind": by_kind},
        "pinned_requirements": {"us-equities": trading.get("pinned_requirements", [])},
        "no_blind_default_today": {"us-equities": trading.get("no_blind_default_today", [])},
        "layers": layers, "slots": rows,
    }
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    try:
        text = build()
    except ValueError as error:
        print(error)
        sys.exit(1)
    if "--check" in sys.argv[1:]:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("definitive-manifest.json is stale: run assemble_manifest.py")
            sys.exit(1)
        print("definitive-manifest.json is current")
    else:
        OUT.write_text(text, encoding="utf-8")
        doc = json.loads(text)
        print("layers", doc["counts"]["layers"], "| slots", doc["counts"]["slots"], "| definitive", doc["counts"]["definitive"], "|", doc["counts"]["by_row_kind"])
