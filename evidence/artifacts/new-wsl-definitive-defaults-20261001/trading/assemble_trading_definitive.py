#!/usr/bin/env python3
"""Assemble the trading lane's definitive-defaults rows for the single new-WSL manifest (trading lane, 2026-10-01).

Shape: trading-ownership.json (12 us-equities layers: owns, uses) plus, per owned slot, `default`, `alternatives`,
`evidence` and `overturn_check`, with each model family's status under the preregistered decision rule ("a slot's default
is definitive when both deciders of both families name it and both critics return converged; a split is settled by the
measurement the critics name").

Inputs (all under <definitive-dir>):
  trading-ownership.json                 the one-owner map (pinned, judged, uses, no_blind_default_today rows)
  round1/claude-returns.json             merit round, Claude family (wf_4d2dd504-4a2): judges and critics
  round1/packets/*.json                  round-one packets (requirement text)
  round2/claude-returns.json             decision round, Claude family (wf_01bd02cf-b21), written by --save-round2
  round2/packets/*.order-1.json          decision packets (slot question)
The GPT family's returns are added when they exist (round2/gpt/<slot>.order-N.json, <slot>.critic.json); until then each
slot carries gpt.status "pending" and definitive false.

    assemble_trading_definitive.py <definitive-dir> --save-round2 <journal.jsonl>
    assemble_trading_definitive.py <definitive-dir>            # writes trading-definitive.json
"""
import hashlib
import json
import re
import sys
from pathlib import Path

D = Path(sys.argv[1])
R1, R2 = D / "round1", D / "round2"
ROUND1_RUN, ROUND2_RUN = "wf_4d2dd504-4a2", "wf_01bd02cf-b21"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if len(sys.argv) == 4 and sys.argv[2] == "--save-round2":
    labels, out = {}, {"run": ROUND2_RUN, "deciders": [], "critics": []}
    for line in open(sys.argv[3]):
        e = json.loads(line)
        if e.get("type") == "started":
            labels[e["key"]] = e["label"]
        elif e.get("type") == "result" and e.get("result") is not None:
            lab = labels[e["key"]]
            kind, slot, *rest = lab.split(":")
            row = {"label": lab, "slot_id": slot, "return": e["result"]}
            if kind == "decide":
                row["order"] = int(rest[0].split("-")[1])
                out["deciders"].append(row)
            elif kind == "critic":
                out["critics"].append(row)
    out["deciders"].sort(key=lambda r: (r["slot_id"], r["order"]))
    out["critics"].sort(key=lambda r: r["slot_id"])
    (R2 / "claude-returns.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"deciders {len(out['deciders'])}, critics {len(out['critics'])}, sha256 {sha(R2 / 'claude-returns.json')}")
    sys.exit(0)

own = json.loads((D / "trading-ownership.json").read_text())
r1 = json.loads((R1 / "claude-returns.json").read_text())
r2 = json.loads((R2 / "claude-returns.json").read_text())
J1 = {L["layer_id"].split(":", 1)[1]: L for j in r1["judges"] for L in j["return"]["layers"]}
C1 = {L["layer_id"].split(":", 1)[1]: L for c in r1["critics"] for L in c["return"]["layers"]}
DEC2 = {}
for row in r2["deciders"]:
    DEC2.setdefault(row["slot_id"], {})[row["order"]] = row["return"]
CRIT2 = {row["slot_id"]: row["return"] for row in r2["critics"]}
STRIP = re.compile(r"\s*\(C\d+\)\s*$")


def clean(name):
    return STRIP.sub("", name).strip()


def gpt_status(slot):
    g = R2 / "gpt"
    orders = [g / f"{slot}.order-{n}.json" for n in (1, 2)]
    crit = g / f"{slot}.critic.json"
    if all(p.exists() for p in orders) and crit.exists():
        ds = [json.loads(p.read_text()) for p in orders]
        c = json.loads(crit.read_text())
        names = {d["default"]["name"] for d in ds}
        return {"status": "returned", "defaults": sorted(names), "deciders_agree": len(names) == 1,
                "critic_verdict": c.get("verdict"), "default_after_review": c.get("default_after_review")}
    return {"status": "pending",
            "requested": "2026-10-01T21:39Z, new-wsl-catalog-20261001/claude-owner-response.md (round-one and round-two packets)",
            "capacity_at_request": "OmniRoute pool: all six accounts at 100 of 100 weekly, read 2026-10-01 ~21:57Z, earliest reset "
                                   "2026-10-03T17:14Z; the native-login Codex lane is scheduled by the Codex owner"}


def round1_slot(slot):
    j, c = J1[slot], C1[slot]
    picks = [{"name": clean(s["name"]), "repository": s["repository"], "role": s["role"],
              "install_command": s["install_command"], "install_source": s["install_source"],
              "confidence": s["confidence"], "installs_nothing_extra": False} for s in j["selection"]]
    alts = [{"name": clean(n["name"]), "reason": n["reason"]} for n in j["not_selected"]]
    alts += [{"name": clean(x["name"]), "reason": f"excluded ({x['criterion']}): {x['fact']}"} for x in j["excluded"]]
    ev = [{"url": b["url"], "shows": b["shows"], "from": "round-one judge"} for s in j["selection"] for b in s["basis"]]
    ev += [{"url": f["url"], "shows": f["claim"], "from": "round-one critic, checked"} for f in c["checked_facts"] if f["holds"]]
    corrected = [{"url": f["url"], "claim": f["claim"]} for f in c["checked_facts"] if not f["holds"]]
    return {"picks": picks, "alternatives": alts, "evidence": ev, "corrected_claims": corrected,
            "overturn_check": c["deciding_comparison"] or j["deciding_comparison"],
            "critic_findings": c["findings"],
            "claude": {"round": 1, "run": ROUND1_RUN, "method": "merit judge plus adversarial critic (#589 method)",
                       "single_finalist": len(picks) == 1 or slot == "strategy-qualification-statistics",
                       "critic_verdict": c["verdict"],
                       "status": "converged" if c["verdict"] == "upheld" else "undetermined"}}


def round2_slot(slot):
    ds, c = DEC2[slot], CRIT2.get(slot)
    d1, d2 = ds.get(1), ds.get(2)
    names = {d["default"]["key"]: d["default"]["name"] for d in (d1, d2) if d}
    agree = d1 is not None and d2 is not None and d1["default"]["key"] == d2["default"]["key"]
    base = d1 or d2
    dft = dict(base["default"])
    finalists = json.loads((R2 / "packets" / f"{slot}.order-1.json").read_text())["finalists"]
    chosen = next(f for f in finalists if f["key"] == dft["key"])
    dft["installs_nothing_extra"] = bool(chosen.get("installs_nothing_extra", False))
    alts, seen = [], set()
    for d in (d1, d2):
        for a in (d or {}).get("alternatives", []):
            if a["key"] not in seen:
                seen.add(a["key"])
                alts.append({"name": a["name"], "reason": a["reason"]})
    ev = [{"url": f["url"], "shows": f["fact"], "from": f"round-two decider, order {n}",
           "rechecked_now": f["rechecked_now"]} for n, d in ((1, d1), (2, d2)) if d for f in d["deciding_facts"]]
    corrected = []
    if c:
        ev += [{"url": f["url"], "shows": f["claim"], "from": "round-two critic, checked"} for f in c["checked_facts"] if f["holds"]]
        corrected = [{"url": f["url"], "claim": f["claim"]} for f in c["checked_facts"] if not f["holds"]]
    verdict = c["verdict"] if c else None
    status = "converged" if (agree and verdict == "converged") else ("split" if verdict == "split" else
                                                                     ("revised" if verdict == "revised" else "incomplete"))
    return {"default": dft, "alternatives": alts, "evidence": ev, "corrected_claims": corrected,
            "overturn_check": (c or {}).get("overturn_check") or base["overturn_check"],
            "decider_overturn_checks": [d["overturn_check"] for d in (d1, d2) if d],
            "decided_on": sorted({d["decided_on"] for d in (d1, d2) if d}),
            "decided_by_criterion": [d["decided_by_criterion"] for d in (d1, d2) if d],
            "confidence": [d["confidence"] for d in (d1, d2) if d],
            "evidence_gaps": sorted({g for d in (d1, d2) if d for g in d["evidence_gaps"]}),
            "critic_findings": (c or {}).get("findings", []),
            "deciding_measurement_if_split": (c or {}).get("deciding_measurement_if_split", ""),
            "default_after_review": (c or {}).get("default_after_review"),
            "claude": {"round": 2, "run": ROUND2_RUN, "method": "two deciders in seeded orders plus one critic (definitive-defaults method)",
                       "defaults_named": sorted(set(names.values())), "deciders_agree": agree, "critic_verdict": verdict,
                       "status": status}}


IBC_NOTE = {
    "maintenance_risk": "The selected image bundles IBC (github.com/IbcAlpha/IBC) for login, 2FA and dialog automation. IBC was "
                        "archived on 2026-09-01 (archivedAt 2026-09-01T00:49:34Z, observed by the round-one critic), so no upstream "
                        "remains to ship fixes such as its August 2026 auto-restart and Gateway v1048 changes. The image owner is "
                        "evaluating a replacement controller (ibctl, issue #366) but has not adopted one.",
    "overturn_check_addition": "Re-run this slot when the image adopts a maintained controller or an IBC fork, when an IB Gateway "
                               "release breaks IBC's login, 2FA or daily auto-restart handling with no fix in the image, or when "
                               "NautilusTrader's DockerizedIBGateway changes its default container.",
    "install_pin_note": "The repository's docker-compose.yml builds ./latest (image :latest); the :stable tag comes from the README's "
                        "sample compose and must be pinned explicitly (round-one critic finding)."}

# Whether a default coincides with a component the trading lane's record already names. The record is the architecture
# edition's 12 trading rows: catalogs/foundation/new-wsl-architecture-20261001.json, winners per row, on origin/main
# 85543efe. The keys are slot ids, or slot/role. A default that coincides cannot be shown to be free of current-use influence.
LANE_RECORD = {
    "market-data-provider": ("alpaca-py", "pinned broker path; the default follows from the preregistered no-install rule"),
    "sec-filings": ("edgartools", None),
    "exchange-calendars": ("exchange-calendars", None),
    "research-data-versioning": ("DVC", None),
    "analytical-storage/engine": ("duckdb", None),
    "analytical-storage/snapshot-table-layer": ("status quo (the record has no snapshot component)",
                                                "the default follows from the preregistered no-install rule"),
    "backtest-oracle": ("lean", None),
    "portfolio-construction": ("skfolio", None),
    "experiment-tracking": ("MLflow", None),
}
NOT_ON_RECORD = {
    "market-data-validation": "the record names pandera for this row; the default is Pointblank",
    "factor-research": "Qlib is not on the record",
    "ib-gateway-runtime": "no IB Gateway runtime is on the record",
    "performance-analytics": "no performance-analytics library is on the record",
    "strategy-qualification-statistics": "neither arch nor purgedcv is on the record",
}


def lane_record(key):
    if key in LANE_RECORD:
        comp, note = LANE_RECORD[key]
        return {"coincides": True, "record_component": comp,
                "note": "freedom from current-use influence is not shown" + (f"; {note}" if note else "")}
    return {"coincides": False, "record_component": None, "note": NOT_ON_RECORD[key]}


SLOT_RE = re.compile(r"^slot ([a-z0-9-]+) \((judged|no blind default today)\)")
layers = []
for L in own["layers"]:
    row = {"layer_id": L["layer_id"], "owns": L["owns"], "uses": L["uses"], "slots": []}
    for o in L["owns"]:
        m = SLOT_RE.match(o)
        if not m:
            continue
        slot, kind = m.group(1), m.group(2)
        if kind != "judged":
            nb = next(x for x in own["no_blind_default_today"] if x["slot"] == slot)
            row["slots"].append({"slot_id": slot, "row_kind": "no_blind_default_today", "default": None, "alternatives": [],
                                 "evidence": [], "overturn_check": nb["reason"], "definitive": False})
            continue
        entry = {"slot_id": slot, "row_kind": "judged"}
        if slot == "analytical-storage":
            a = round1_slot(slot)
            duck = next(p for p in a["picks"] if p["name"].startswith("DuckDB"))
            snap = round2_slot("snapshot-table-layer")
            entry["roles"] = [
                {"role": "engine", "default": duck, "alternatives": [x for x in a["alternatives"]],
                 "evidence": [e for e in a["evidence"]], "overturn_check": a["overturn_check"],
                 "families": {"claude": dict(a["claude"], status="converged", note="engine role settled in round one: DuckDB was "
                              "selected and upheld; only the snapshot role went to round two"), "gpt": gpt_status("analytical-storage")}},
                {"role": "snapshot-table-layer", **{k: snap[k] for k in ("default", "alternatives", "evidence", "overturn_check")},
                 "families": {"claude": snap["claude"], "gpt": gpt_status("snapshot-table-layer")},
                 "detail": {k: snap[k] for k in ("decided_on", "decided_by_criterion", "confidence", "evidence_gaps",
                                                 "critic_findings", "corrected_claims", "decider_overturn_checks",
                                                 "deciding_measurement_if_split", "default_after_review")}}]
            entry["roles"][0]["decision_stage"] = "first_round"
            entry["roles"][1]["decision_stage"] = "decision_round"
            entry["roles"][0]["lane_record"] = lane_record("analytical-storage/engine")
            entry["roles"][1]["lane_record"] = lane_record("analytical-storage/snapshot-table-layer")
            entry["definitive"] = False
        elif slot in DEC2:
            s = round2_slot(slot)
            entry.update({k: s[k] for k in ("default", "alternatives", "evidence", "overturn_check")})
            entry["families"] = {"claude": s["claude"], "gpt": gpt_status(slot)}
            entry["decision_stage"] = "decision_round"
            entry["lane_record"] = lane_record(slot)
            entry["detail"] = {k: s[k] for k in ("decided_on", "decided_by_criterion", "confidence", "evidence_gaps",
                                                 "critic_findings", "corrected_claims", "decider_overturn_checks",
                                                 "deciding_measurement_if_split", "default_after_review")}
            entry["definitive"] = False
        else:
            a = round1_slot(slot)
            if len(a["picks"]) == 1:
                entry["default"] = a["picks"][0]
            else:
                entry["default"] = None
                entry["defaults_by_role"] = a["picks"]
            entry.update({k: a[k] for k in ("alternatives", "evidence", "overturn_check")})
            entry["families"] = {"claude": a["claude"], "gpt": gpt_status(slot)}
            entry["decision_stage"] = "first_round"
            entry["lane_record"] = lane_record(slot)
            entry["detail"] = {"critic_findings": a["critic_findings"], "corrected_claims": a["corrected_claims"]}
            entry["definitive"] = False
            if slot == "ib-gateway-runtime":
                entry.update(IBC_NOTE)
                entry["overturn_check"] = entry["overturn_check"] + " " + IBC_NOTE["overturn_check_addition"]
        row["slots"].append(entry)
    layers.append(row)

doc = {
    "schema_version": 1,
    "kind": "layer-ownership-with-definitive-defaults",
    "catalog": "us-equities",
    "date_utc": "2026-10-01",
    "owner": own["owner"],
    "rule": own["rule"],
    "trading_rule": own["trading_rule"],
    "decision_rule": "a slot's default is definitive when both deciders of both families name it and both critics return "
                     "converged; a split is settled by the measurement the critics name (preregistered, round2/preregistration.json)",
    "no_install_rule": "an option that installs nothing extra is the default unless a measured gain excludes zero",
    "definitive_now": "none: the Claude family has returned for every judged slot, and the GPT family has not; every slot's "
                      "'definitive' stays false until its GPT returns agree",
    "not_claimed": "no candidate is installed or measured by these rounds; a default decided on documented fit says so",
    "counts": {"judged_slots": 13, "decisions": 14, "default_rows": 15,
               "explained": "13 trading-specific slots were judged. analytical-storage has two roles (engine, decided in the "
                            "first round; snapshot-table-layer, decided in the decision round), so 14 decisions. "
                            "strategy-qualification-statistics names two tools in two roles (arch, purgedcv), so 15 default rows. "
                            "Pinned requirements: 3. No blind default today: 2."},
    "blindness": {
        "checked": "what the Claude deciders could see, checked on 2026-10-01 after the reviewers of #591 raised it",
        "packets": "no current-use wording in the 13 first-round packets (grep for today, currently, in use, installed, "
                   "incumbent, adopted, of record: 0 hits). In the round-two packets the only hit is the Alpaca finalist's "
                   "'already installed for the selected broker path', a fact of the user-pinned broker path given for the "
                   "preregistered no-install rule.",
        "agent_definitions": "the stack-researcher definition and the SubagentStart token-lanes block name none of the "
                             "trading candidates (grep on origin/main 85543efe)",
        "project_instructions": "AGENTS.md, which every Claude agent loads through CLAUDE.md, names NautilusTrader, Alpaca and "
                                "LEAN ('dated LEAN/Alpaca receipts remain comparison evidence')",
        "web": "the repository is public, and the deciders had web and GitHub access; the prompts forbade local files, not "
               "the web, so reading the lane's record that way is not excluded",
        "consequence": "nine of the fifteen defaults coincide with the lane's record, and for these freedom from current-use "
                       "influence is not shown (each slot's lane_record). Six do not coincide: Pointblank (the record names "
                       "pandera), Qlib, the Dockerized IB Gateway, fincore, arch and purgedcv. The GPT family's agreement is the "
                       "stronger independence check where its runs load no project document (project_doc_max_bytes=0, as in "
                       "the foundation round's runner)."},
    "decision_stages": {"first_round": "one blind judge and one adversarial critic (#589 merit method), a single finalist "
                                       "upheld by the critic; the same stage as the foundation's first-round rows",
                        "decision_round": "two blind deciders with the finalists in seeded orders, then one critic "
                                          "(definitive-defaults method), for slots the first round left contested"},
    "sources": {
        "ownership": {"path": "trading-ownership.json", "sha256": sha(D / "trading-ownership.json")},
        "round1": {"run": ROUND1_RUN, "returns": "round1/claude-returns.json", "sha256": sha(R1 / "claude-returns.json"),
                   "preregistration_sha256": sha(R1 / "preregistration.json")},
        "round2": {"run": ROUND2_RUN, "returns": "round2/claude-returns.json", "sha256": sha(R2 / "claude-returns.json"),
                   "preregistration_sha256": sha(R2 / "preregistration.json")},
    },
    "layers": layers,
    "pinned_requirements": own["pinned_requirements"],
    "no_blind_default_today": own["no_blind_default_today"],
    "overlaps_resolved": own["overlaps_resolved"],
}
HOST = str(D) + "/"


def scrub(x):
    """Replace this host's path to the decision directory with a placeholder (no host path or user name leaves it)."""
    if isinstance(x, str):
        return x.replace(HOST, "<definitive-20261001>/")
    if isinstance(x, list):
        return [scrub(v) for v in x]
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items()}
    return x


doc = scrub(doc)
doc["path_placeholder"] = ("<definitive-20261001>/ is the trading lane's decision directory (packets, preregistrations, "
                           "returns); its files travel with this document")
assert str(Path.home()) not in json.dumps(doc) and Path.home().name not in json.dumps(doc), "host path or user name left"
out = D / "trading-definitive.json"
out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def compact_slot(s):
    keep = {"slot_id": s["slot_id"], "row_kind": s["row_kind"], "definitive": s.get("definitive", False)}
    if "decision_stage" in s:
        keep["decision_stage"] = s["decision_stage"]
    if "lane_record" in s:
        keep["lane_record"] = s["lane_record"]
    if s["row_kind"] != "judged":
        keep["reason"] = s["overturn_check"]
        return keep
    if "roles" in s:
        keep["roles"] = [compact_slot(dict(r, slot_id=r["role"], row_kind="judged")) for r in s["roles"]]
        return keep
    d = s.get("default")
    keep["default"] = ({k: d[k] for k in ("name", "repository", "install_command", "installs_nothing_extra") if k in d} if d else
                       [{k: p[k] for k in ("name", "repository", "role", "install_command", "installs_nothing_extra")}
                        for p in s["defaults_by_role"]])
    keep["alternatives"] = [{"name": a["name"], "reason": a["reason"][:400]} for a in s["alternatives"]]
    keep["evidence"] = [{"url": e["url"], "shows": e["shows"][:300], "from": e["from"]} for e in s["evidence"][:8]]
    keep["evidence_items_in_full_file"] = len(s["evidence"])
    keep["overturn_check"] = s["overturn_check"]
    keep["families"] = s["families"]
    for k in ("maintenance_risk", "install_pin_note"):
        if k in s:
            keep[k] = s[k]
    return keep


compact = {k: doc[k] for k in ("schema_version", "catalog", "date_utc", "owner", "rule", "trading_rule", "decision_rule",
                               "no_install_rule", "definitive_now", "not_claimed", "counts", "blindness", "decision_stages", "sources",
                               "path_placeholder")}
compact["kind"] = "layer-ownership-with-definitive-defaults (compact view of trading-definitive.json)"
compact["layers"] = [{"layer_id": L["layer_id"], "owns": L["owns"], "uses": L["uses"],
                      "slots": [compact_slot(s) for s in L["slots"]]} for L in doc["layers"]]
for k in ("pinned_requirements", "no_blind_default_today", "overlaps_resolved"):
    compact[k] = doc[k]
(D / "trading-definitive.compact.json").write_text(json.dumps(compact, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("compact sha256", sha(D / "trading-definitive.compact.json"), (D / "trading-definitive.compact.json").stat().st_size, "bytes")
summary = []
for L in layers:
    for s in L["slots"]:
        if "roles" in s:
            for r in s["roles"]:
                summary.append((f"{s['slot_id']}/{r['role']}", r["default"]["name"] if r["default"] else None,
                                r["families"]["claude"]["status"], r["families"]["gpt"]["status"]))
        elif s["row_kind"] == "judged":
            name = s["default"]["name"] if s.get("default") else " + ".join(p["name"] for p in s.get("defaults_by_role", []))
            summary.append((s["slot_id"], name, s["families"]["claude"]["status"], s["families"]["gpt"]["status"]))
        else:
            summary.append((s["slot_id"], None, s["row_kind"], "-"))
for row in summary:
    print(" | ".join(str(x) for x in row))
print("sha256", sha(out))
