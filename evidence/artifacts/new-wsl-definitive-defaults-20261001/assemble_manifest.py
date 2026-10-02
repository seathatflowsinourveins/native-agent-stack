#!/usr/bin/env python3
"""Build definitive-manifest.json: one row per slot of the new WSL architecture, across both catalogs.

It reads the two committed compact documents, settlements and convergence decisions in this folder and writes a flat table next to them. The output is
deterministic: running it again over unchanged inputs writes the same bytes.

Usage: assemble_manifest.py [--check]
"""
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FOUNDATION = HERE / "foundation-definitive.compact.json"
TRADING = HERE / "trading" / "trading-definitive.compact.json"
SETTLEMENTS = HERE / "settlements.json"
CONVERGENCE = HERE / "convergence.json"
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


def norm(url):
    # Repository matching follows convergence/combine.py and RULE.md, including the distribution's image URL.
    u = (url or "").strip().lower().rstrip("/")
    parts = urlsplit(u)
    if parts.netloc in ("github.com", "www.github.com"):
        return "/".join(parts.path.strip("/").split("/")[:2])
    return u


def installs(row):
    return bool(row["default"]) and not row["installs_nothing_extra"]


# A row the convergence data resolves states its current basis; the first round's text moves to resolution.first_round_record.
BASIS = {"final": "both families: the Claude record and the blind GPT samples",
         "installed_on_critic": "kept or added on a blind critic's verdict",
         "not_installed": "not installed: resolved by the rule or a blind critic",
         "split": "split: decided by the named measurement, nothing installed until it returns"}
STALE_GPT = "pending: the blind GPT-6.1 Sol run"


def gpt_status(sid, row, outcome, repos, layer):
    """The GPT family's current status on a resolved row, from its layer's entry in combined.json (RULE.md and amendment 1)."""
    samples = layer["gpt_samples_present"]
    if not samples:
        raise ValueError(f"convergence {sid}: combined.json holds no blind GPT sample for layer {row['layer_id']}")
    if outcome == "final":
        # Where amendment 1 leaves the first sample uncounted, the two Sol-ultra orders are the whole GPT side.
        if layer["g1_counted"] and samples == 3:
            return "returned: at least two of three blind GPT samples"
        if not layer["g1_counted"] and samples == 2 and layer["orders_present"] == 2:
            return "returned: both blind Sol-ultra orders"
        raise ValueError(f"convergence {sid}: combined.json holds {samples} GPT samples for layer {row['layer_id']}, not the set a final row needs")
    named = {norm(repo): count for key in ("claude_only", "gpt_only", "single_gpt_votes") for repo, count in layer[key]}
    counts = [named[repo] for repo in repos if repo in named]
    if len(counts) > 1:
        raise ValueError(f"convergence {sid}: more than one repository in combined.json: {'; '.join(repos)}")
    if counts:
        return f"returned: {counts[0]} of {samples} blind GPT samples"
    if row["row_kind"] == "added":
        return "returned: named by the critic or the added-slot round, not by the layer's blind samples"
    if repos:
        raise ValueError(f"convergence {sid}: repository not in combined.json: {'; '.join(repos)}")
    # A first-round default that installs nothing has no repository for a sample to name.
    return f"returned: 0 of {samples} blind GPT samples"


def verify_evidence(ref, sid):
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError(f"convergence {sid}: evidence path and sha256 required")
    path = ROOT / ref["path"]
    if not path.is_file():
        raise ValueError(f"convergence {sid}: evidence missing: {ref['path']}")
    if sha(path) != ref["sha256"]:
        raise ValueError(f"convergence {sid}: evidence sha256 mismatch: {ref['path']}")


def apply_convergence(rows, layers):
    data = json.loads(CONVERGENCE.read_text(encoding="utf-8"))
    for source in ("rule", "combined"):
        verify_evidence(data[source], source)
    combined = {layer["layer_id"]: layer for layer in json.loads((ROOT / data["combined"]["path"]).read_text(encoding="utf-8"))["rows"]}
    by_slot = {row["slot_id"]: row for row in rows}
    by_layer = {(layer["catalog"], layer["layer_id"]): [] for layer in layers}
    for row in rows:
        by_layer[row["catalog"], row["layer_id"]].append(row)
    added_jobs = {}
    for added in data["added_slots"]:
        sid, lid = added["slot_id"], added["layer_id"]
        if sid in by_slot:
            raise ValueError(f"convergence {sid}: duplicate added slot")
        matches = [layer for layer in layers if layer["layer_id"] == lid]
        if len(matches) != 1:
            raise ValueError(f"convergence {sid}: unknown or ambiguous layer: {lid}")
        layer = matches[0]
        row = rows_of(layer["catalog"], layer, {"slot_id": sid, "row_kind": "added", "default": added["default"]})[0]
        by_slot[sid] = row
        by_layer[layer["catalog"], lid].append(row)
        added_jobs[sid] = added.get("job")
    rows[:] = [row for layer in layers for row in by_layer[layer["catalog"], layer["layer_id"]]]
    decisions = {}
    for decision in data["decisions"] + data["added_slots"]:
        sid = decision["slot_id"]
        if sid not in by_slot:
            raise ValueError(f"convergence {sid}: decision for unknown slot")
        if sid in decisions:
            raise ValueError(f"convergence {sid}: duplicate decision")
        decisions[sid] = decision
    for sid in data["jobs"]:
        if sid not in by_slot:
            raise ValueError(f"convergence {sid}: job for unknown slot")
    measurements = {}
    for row in rows:
        sid = row["slot_id"]
        if sid not in decisions:
            raise ValueError(f"convergence {sid}: missing decision")
        job = data["jobs"].get(sid, added_jobs.get(sid))
        if not isinstance(job, str) or not job.strip():
            raise ValueError(f"convergence {sid}: missing job")
        row["job"] = job
        decision = decisions[sid]
        outcome = decision.get("outcome")
        if outcome not in ("final", "installed_on_critic", "not_installed", "split", "kept"):
            raise ValueError(f"convergence {sid}: unknown outcome: {outcome}")
        resolution = {key: decision[key] for key in ("outcome", "by", "votes", "evidence", "reason", "covered_by") if key in decision}
        row["resolution"] = resolution
        # Both are read before a branch below changes the row: the inherited status, and the repository that was judged.
        inherited = {"claude": row["claude"], "gpt": row["gpt"], "label": row["label"]}
        repos = [norm(repo) for repo in row["repository"].split(";") if norm(repo)]
        if outcome in ("installed_on_critic", "split") and "critic" not in decision:
            raise ValueError(f"convergence {sid}: critic evidence required")
        for key in ("critic", "evidence"):
            if key in decision:
                verify_evidence(decision[key], sid)
                resolution["evidence"] = decision[key]
        if outcome == "final":
            final = {norm(repo) for repo in combined.get(row["layer_id"], {}).get("final", [])}
            if not repos or any(repo not in final for repo in repos):
                raise ValueError(f"convergence {sid}: final repository not in combined.json: {row['repository']}")
            row.update({"state": "definitive", "definitive": True, "measurement": None})
        elif outcome == "installed_on_critic":
            row.update({"state": "resolved", "definitive": False, "measurement": None})
        elif outcome in ("not_installed", "split"):
            resolution["former_default"] = {"name": row["default"], "repository": row["repository"]}
            row.update({"state": "resolved" if outcome == "not_installed" else "split", "definitive": False,
                        "repository": "", "installs_nothing_extra": True})
            if not decision.get("reason"):
                raise ValueError(f"convergence {sid}: reason required")
            if outcome == "not_installed":
                row.update({"default": "Not installed: " + decision["reason"], "measurement": None})
            else:
                for key in ("arms", "deciding_measurement", "measurement_id"):
                    if not decision.get(key):
                        raise ValueError(f"convergence {sid}: split requires {key}")
                    resolution[key] = decision[key]
                mid = decision["measurement_id"]
                if mid in measurements and measurements[mid] != decision["arms"]:
                    raise ValueError(f"convergence {sid}: inconsistent arms for measurement {mid}")
                measurements[mid] = decision["arms"]
                row.update({"default": "Not installed until the deciding measurement returns",
                            "measurement": {"returned": False, "receipts": []}})
        elif not decision.get("reason"):
            raise ValueError(f"convergence {sid}: kept decision requires a reason")
        if outcome != "kept":
            layer = combined.get(row["layer_id"])
            if layer is None:
                raise ValueError(f"convergence {sid}: layer not in combined.json: {row['layer_id']}")
            added = row["row_kind"] == "added"
            # A decision may state the GPT side itself where the row has no repository for a sample to name.
            row.update({"claude": "not judged in the first round" if added else row["claude"],
                        "gpt": decision.get("gpt_status") or gpt_status(sid, row, outcome, repos, layer),
                        "label": BASIS[outcome]})
            if not added:
                resolution["first_round_record"] = inherited
        elif row["catalog"] == "us-equities" and row["gpt"].startswith(STALE_GPT):
            # The blind GPT round judged the 21 foundation packets only; a trading row never waits on it.
            resolution["first_round_record"] = inherited
            row["gpt"] = "not judged: the blind GPT round covered the 21 foundation packets only"
    for correction in data["hygiene"]:
        sid, field = correction["slot_id"], correction["field"]
        if sid not in by_slot:
            raise ValueError(f"convergence {sid}: hygiene for unknown slot")
        row = by_slot[sid]
        if field not in row:
            raise ValueError(f"convergence {sid}: unknown hygiene field: {field}")
        if field == "repository":
            if correction.get("judged_as") != row["repository"]:
                raise ValueError(f"convergence {sid}: hygiene judged_as differs from repository")
            row["resolution"]["judged_repository"] = row["repository"]
        row[field] = correction["value"]
        reason = row["resolution"].get("reason", "")
        row["resolution"]["reason"] = (reason + "; " if reason else "") + correction["reason"]
    jobs = {}
    for row in rows:
        sid = row["slot_id"]
        if installs(row):
            if row["job"] in jobs:
                raise ValueError(f"convergence {sid}: installed job also owned by {jobs[row['job']]}: {row['job']}")
            jobs[row["job"]] = sid
        if row["state"] == "split" or (row["measurement"] and not row["measurement"]["returned"]):
            if installs(row) or row["repository"] or not row["installs_nothing_extra"]:
                raise ValueError(f"convergence {sid}: pending measurement installs something")
        if row["resolution"]["outcome"] == "not_installed":
            if row["repository"] or not row["installs_nothing_extra"]:
                raise ValueError(f"convergence {sid}: not_installed row installs something")
            covered = row["resolution"].get("covered_by")
            if covered == "not needed":
                continue
            if not isinstance(covered, list) or not covered:
                raise ValueError(f"convergence {sid}: covered_by must name covering slots or not needed")
            for owner in covered:
                if owner not in by_slot:
                    raise ValueError(f"convergence {sid}: covered_by names unknown slot: {owner}")
                if not installs(by_slot[owner]):
                    raise ValueError(f"convergence {sid}: covered_by {owner} installs nothing")
    return data


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
    convergence = apply_convergence(rows, layers)
    by_kind, by_state = {}, {}
    for r in rows:
        by_kind[r["row_kind"]] = by_kind.get(r["row_kind"], 0) + 1
        state = r.get("state") or "open"
        by_state[state] = by_state.get(state, 0) + 1
    doc = {
        "schema_version": 1, "kind": "new-wsl-definitive-manifest", "date_utc": "2026-10-01",
        "meaning": "one default per slot for the clean install of the new WSL distribution; a definitive default is the slot's install decision, "
                   "agreed by both model families, and is not a merit acceptance",
        "decision_rule": "A foundation first-round default is definitive when it is in the Claude record and in enough blind GPT samples "
                         f"under the combination rule ({convergence['rule']['path']} and its amendment 1); a contested one is resolved by a blind "
                         "Claude critic or split to a named measurement. A decision-round default is definitive when both deciders of both families "
                         "name it and both critics return converged, and a split is settled by the measurement the critics name.",
        "decision_rule_before_amendment_2": foundation["decision_rule"],
        "no_install_rule": foundation["no_install_rule"],
        "not_claimed": foundation["not_claimed"],
        "sources": {"foundation": {"file": FOUNDATION.name, "sha256": sha(FOUNDATION)},
                    "us-equities": {"file": "trading/" + TRADING.name, "sha256": sha(TRADING), "owner": trading["owner"]},
                    "settlements": {"file": SETTLEMENTS.name, "sha256": sha(SETTLEMENTS)},
                    "convergence": {"file": CONVERGENCE.name, "sha256": sha(CONVERGENCE)},
                    "rule": convergence["rule"], "combined": convergence["combined"]},
        "counts": {"layers": len(layers), "slots": len(rows), "definitive": sum(1 for r in rows if r["definitive"]), "by_row_kind": by_kind,
                   "by_state": by_state, "installed": sum(1 for r in rows if installs(r))},
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
