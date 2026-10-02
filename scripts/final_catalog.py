#!/usr/bin/env python3
"""Build the final catalog: one row per layer of the dated new-WSL architecture edition with the source host's
selection of record, the blind clean-install recommendation, its cross-family (GPT-6.1 Sol) counterpart, the
standing picks and status that follow from the frozen agreement rule, and a per-layer gate ledger.

This is a read-only join. It judges no candidate, changes no verdict, pins no version and records no receipt: the
standing picks and the status column apply the agreement rule frozen before the cross-family run, as written
(``evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/agreement-rule.txt``), and the merit rule
of ``docs/decisions/2026-10-01-definitive-sota-wsl-program.md`` (decision 5). A pick both model families made stands
as the layer's pick for the new WSL; it is final once it passes acceptance on the new host and, where a pick only one
family made challenges it, the layer's measured comparison. Sources:

- ``catalogs/foundation/new-wsl-architecture-20261001.json``: the 37 rows, each winner (the source host's selection
  of record, which is bookkeeping and not a merit result), verdict, closure, gates, owner lane and upstream currency;
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json``: the blind Claude recommendation
  for the 20 foundation layers and the base distribution (picks, comparison arms, critic verdict);
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/selection-gpt.json`` when present: the
  blind GPT-6.1 Sol run on the same packets, criteria and prompts;
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/packets/``: candidate names, used only to normalize
  a pick that has no GitHub repository;
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/facts/``: the GitHub API facts captured
  for every packet candidate before the cross-family run (latest release, last default-branch commit, archived flag,
  license as information only), attached to each pick of either family;
- ``catalogs/landscape/new-host-grand-list.json``: each catalog layer's decision and open-gap counts, carried as
  context. A move of the grand list alone is reported as drift, not as a failure, because that list is regenerated
  whenever a receipt lands.

Modes: ``--check`` (default) recomputes both outputs and exits 1 when anything but the grand-list context differs
from the checked-in files; ``--write`` writes them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from . import host_receipts
    from .validate import PRIVATE_CONTENT
except ImportError:
    import host_receipts
    from validate import PRIVATE_CONTENT

ROOT = Path(__file__).resolve().parent.parent
EDITION = "catalogs/foundation/new-wsl-architecture-20261001.json"
SELECTION_DIR = "evidence/artifacts/new-wsl-clean-install-selection-20261001"
SELECTION = SELECTION_DIR + "/selection.json"
CROSS_FAMILY = SELECTION_DIR + "/cross-family/selection-gpt.json"
AGREEMENT_RULE = SELECTION_DIR + "/cross-family/agreement-rule.txt"
PACKETS = SELECTION_DIR + "/packets"
FACTS = SELECTION_DIR + "/cross-family/facts"
GRAND_LIST = "catalogs/landscape/new-host-grand-list.json"
PROGRAM = "docs/decisions/2026-10-01-definitive-sota-wsl-program.md"
OUT_JSON = "catalogs/foundation/final-catalog-20261001.json"
OUT_MD = "docs/final-catalog-20261001.md"
TRADING_RUN = ("The trading lane owner runs the blind method unchanged on the GPT lane after the pool resets at "
               "2026-10-03T17:14Z")

STATUSES = {
    "two_family_pick": "both families made the same picks and neither asks for a comparison: the standing picks on "
                       "source review; each installs by its upstream command and is final once it passes acceptance "
                       "on the new host",
    "shared_pick": "both families made the same picks, but one family's critic found source review undetermined; no "
                   "pick only one family made is left to compare, so the picks stand and are final once they pass "
                   "acceptance on the new host",
    "partial_comparison": "the families share some picks: those stand, and every pick only one family made, with the "
                          "blind Claude half's comparison arms, enters the layer's measured comparison on the new "
                          "host, whose preregistered result decides whether a challenger replaces or joins a "
                          "standing pick",
    "comparison": "the merit winner is undetermined (the families share no pick, or both ask for a comparison of the "
                  "same picks): the arms install fresh on the new WSL and the head-to-head selects",
    "pending_cross_family": "one model family has judged so far; the blind GPT-6.1 Sol half decides how the "
                            "recommendation folds",
    "owner_lane_run_pending": "a trading layer with no blind record yet: its selection of record is an unjudged "
                              "incumbent, and its owner runs the blind method unchanged on the GPT lane after the pool "
                              "resets at 2026-10-03T17:14Z",
    "no_blind_record": "a cross-cutting row the blind run did not cover: its selection of record is an unjudged "
                       "incumbent (the source host's bookkeeping), not a merit result",
}
GITHUB = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([^/\s#?]+)/([^/\s#?]+)", re.IGNORECASE)


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def sha256(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def github_key(url) -> str | None:
    match = GITHUB.match(url or "")
    if not match:
        return None
    repo = match.group(2)
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    return f"{match.group(1)}/{repo}".lower()


def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", (name or "").lower()).strip()


def packet_names(layer_id: str) -> list[str]:
    path = ROOT / PACKETS / (layer_id.replace(":", "_") + ".json")
    if not path.is_file():
        return []
    return [c.get("name", "") for c in json.loads(path.read_text(encoding="utf-8")).get("candidates", [])]


def load_facts() -> dict:
    """Repository key -> the captured upstream facts of that packet candidate."""
    facts = {}
    folder = ROOT / FACTS
    if not folder.is_dir():
        return facts
    for path in sorted(folder.glob("*.json")):
        for candidate in json.loads(path.read_text(encoding="utf-8")).get("candidates", {}).values():
            key = github_key(candidate.get("repository"))
            endpoints = candidate.get("endpoints")
            if not key or not endpoints:
                continue
            meta = next((v for k, v in endpoints.items() if k.count("/") == 2), {}) or {}
            release = next((v for k, v in endpoints.items() if k.endswith("/releases/latest")), {}) or {}
            commit = next((v for k, v in endpoints.items() if k.endswith("/commits?per_page=1")), {}) or {}
            facts[key] = {
                "latest_release": release.get("tag_name"),
                "released": (release.get("published_at") or "")[:10] or None,
                "last_commit": (commit.get("date") or "")[:10] or None,
                "archived": meta.get("archived"),
                "license": meta.get("license_spdx"),
                "captured_at": candidate.get("captured_at"),
            }
    return facts


def facts_digest() -> str | None:
    folder = ROOT / FACTS
    if not folder.is_dir():
        return None
    digest = hashlib.sha256()
    for path in sorted(folder.glob("*.json")):
        digest.update(path.name.encode() + b"\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return digest.hexdigest()


def pick_key(pick: dict, candidates: list[str]) -> str:
    """The frozen rule: a pick is its GitHub repository; a pick without one is its name. A name is matched to the
    packet candidate whose words it contains (a family may reorder words or append a role such as "primary"); the
    candidate with the most words wins, and an unmatched name stands as written."""
    repo = github_key(pick.get("repository"))
    if repo:
        return repo
    own = name_key(pick.get("name") or pick.get("component_id") or "")
    words = set(own.split())
    best = None
    for candidate in candidates:
        cand_words = set(name_key(candidate).split())
        if cand_words and cand_words <= words and (best is None or len(cand_words) > len(best[1])):
            best = (candidate, cand_words)
    return "name:" + (name_key(best[0]) if best else own)


def display(pick: dict) -> str:
    repo = github_key(pick.get("repository"))
    return repo if repo else (pick.get("name") or "").strip()


def record_entry(winner: dict) -> dict:
    currency = winner.get("upstream_currency") or {}
    return {
        "name": winner.get("component_id") or winner.get("name"),
        "repository": winner.get("repository"),
        "pin": winner.get("pin"),
        "latest_upstream": currency.get("latest_release"),
        "pin_is_latest": currency.get("pin_is_latest"),
    }


def pick_entry(pick: dict, facts: dict) -> dict:
    return {"name": pick.get("name"), "repository": pick.get("repository"), "install_command": pick.get("install_command"),
            "install_source": pick.get("install_source"), "upstream": facts.get(github_key(pick.get("repository")) or "")}


def blind_entry(row: dict, facts: dict) -> dict:
    return {
        "status": row["status"],
        "critic_verdict": row.get("critic_verdict"),
        "picks": [pick_entry(p, facts) for p in row.get("selection") or []],
        "comparison_arms": list(row.get("comparison_arms") or []),
        "deciding_comparison": row.get("deciding_comparison"),
    }


def gpt_entry(row: dict, facts: dict) -> dict:
    return {
        "status": row["status"],
        "critic_verdict": row.get("critic_verdict"),
        "picks": [pick_entry(p, facts) for p in row.get("picks") or []],
        "deciding_head_to_head": row.get("deciding_head_to_head"),
    }


def agreement(c_keys: set, c_status: str, g_keys: set, g_status: str) -> str:
    if c_keys == g_keys and c_status == g_status:
        return "agree"
    if c_keys & g_keys:
        return "overlap"
    return "differ"


def mentioned(label: str, arms: list[str]) -> bool:
    """True when one of the first family's arm descriptions already names this pick: its repository's name (or the pick's
    name), with hyphens and underscores read as spaces, appears there as whole words."""
    tail = re.sub(r"[-_]+", " ", label.rsplit("/", 1)[-1].lower()).strip()
    if not tail:
        return False
    pattern = re.compile(r"\b" + re.escape(tail) + r"\b")
    return any(pattern.search(re.sub(r"[-_]+", " ", arm.lower())) for arm in arms)


def fold(c_picks, c_keys, c_status, c_arms, g_picks, g_keys, g_status, verdict):
    """Apply the frozen fold as written. Returns (status, standing picks, shared picks, challengers, comparison arms)
    as display strings. A pick both families made stands with no status condition, since the rule attaches one only
    to the agree clause; a pick only one family made is a challenger in the layer's comparison, next to the first
    family's arms. A layer whose families share no pick, or agree on a comparison, has no standing pick."""
    labels = {}
    for pick in list(c_picks) + list(g_picks):
        labels.setdefault(pick["key"], pick["label"])

    def arms_with(keys):
        arms = list(c_arms)
        for key in sorted(keys):
            if not mentioned(labels[key], c_arms):
                arms.append(labels[key])
        return arms

    shared = [labels[k] for k in sorted(c_keys & g_keys)]
    if verdict == "agree" and c_status == "recommended":
        return "two_family_pick", shared, shared, [], []
    if verdict == "agree":
        return "comparison", [], shared, [], arms_with(c_keys | g_keys)
    if verdict == "overlap":
        contested = sorted((c_keys | g_keys) - (c_keys & g_keys))
        arms = arms_with(contested)
        return ("partial_comparison" if arms else "shared_pick"), shared, shared, [labels[k] for k in contested], arms
    return "comparison", [], [], [], arms_with(c_keys | g_keys)


def citation(gate: dict) -> str | None:
    for key in ("source_path", "url"):
        if gate.get(key):
            return gate[key]
    pending = gate.get("pending_source")
    if isinstance(pending, dict):
        return f"PR #{pending.get('pull_request')} ({pending.get('path')})"
    return None


def build() -> dict:
    edition = load(EDITION)
    selection = load(SELECTION)
    cross = load(CROSS_FAMILY) if (ROOT / CROSS_FAMILY).is_file() else None
    grand = load(GRAND_LIST)
    blind = {r["layer_id"]: r for r in selection["layers"]}
    gpt = {r["layer_id"]: r for r in (cross or {}).get("layers", [])}
    grand_layers = {r["layer_id"]: r for r in grand["layers"]}
    facts = load_facts()
    rows = []
    for row in edition["rows"]:
        layer_id = row["layer_id"]
        record = [record_entry(w) for w in row["winners"]]
        candidates = packet_names(layer_id)
        record_keys = {pick_key(w, candidates) for w in row["winners"]}
        ledger = [{"gate": g["text"], "kind": g["kind"], "source": citation(g)} for g in row.get("gates", [])]
        closure_missing = row.get("closure", {}).get("missing")
        if closure_missing:
            ledger.append({"gate": closure_missing, "kind": "closure", "source": EDITION})
        out = {
            "layer_id": layer_id, "catalog": row["catalog"], "title": row["title"], "owner_lane": row["owner_lane"],
            "selection_of_record": record, "record_verdict": row["verdict"],
            "record_evidence_class": row["evidence_class"],
            "blind": None, "cross_family": None, "agreement": None,
            "final": None, "disagreement_with_record": None, "gate_ledger": ledger, "grand_list": None,
        }
        if layer_id in grand_layers:
            g = grand_layers[layer_id]
            out["grand_list"] = {k: g.get(k) for k in ("decision", "verdict_status", "independent_review", "open_gaps",
                                                       "open_executable_now_gaps")}
        b = blind.get(layer_id)
        if b is None:
            status = "owner_lane_run_pending" if row["catalog"] == "us-equities" else "no_blind_record"
            ledger.append({"gate": TRADING_RUN if status == "owner_lane_run_pending" else
                           "No blind merit record: run the blind method on this row before any selection changes",
                           "kind": "merit_record", "source": SELECTION})
            out["final"] = {"status": status, "standing_picks": [], "comparison_arms": []}
            rows.append(out)
            continue
        out["blind"] = blind_entry(b, facts)
        c_status = "compare" if b["status"] == "compare" else "recommended"
        c_picks = [{"key": pick_key(p, candidates), "label": display(p)} for p in b.get("selection") or []]
        c_keys = {p["key"] for p in c_picks}
        c_arms = list(b.get("comparison_arms") or [])
        out["disagreement_with_record"] = {
            "blind_only": sorted(display(p) for p in b.get("selection") or [] if pick_key(p, candidates) not in record_keys),
            "record_only": sorted(k for k in record_keys if k not in c_keys),
        }
        x = gpt.get(layer_id)
        if x is None:
            out["final"] = {"status": "pending_cross_family", "standing_picks": [], "comparison_arms": c_arms,
                            "provisional_picks": [p["label"] for p in c_picks]}
            ledger.append({"gate": "The blind GPT-6.1 Sol half on the same packets, criteria and prompts",
                           "kind": "cross_family", "source": SELECTION})
        else:
            out["cross_family"] = gpt_entry(x, facts)
            g_status = "compare" if x["status"] == "compare" else "recommended"
            g_picks = [{"key": pick_key(p, candidates), "label": display(p)} for p in x.get("picks") or []]
            g_keys = {p["key"] for p in g_picks}
            verdict = agreement(c_keys, c_status, g_keys, g_status)
            out["agreement"] = verdict
            status, picks, shared, challengers, arms = fold(c_picks, c_keys, c_status, c_arms, g_picks, g_keys,
                                                            g_status, verdict)
            out["final"] = {"status": status, "standing_picks": picks, "shared_picks": shared,
                            "challengers": challengers, "comparison_arms": arms, "versus_record": None}
            if picks:
                labels = {}
                for p in c_picks + g_picks:
                    labels.setdefault(p["key"], p["label"])
                standing = c_keys & g_keys
                out["final"]["versus_record"] = {
                    "standing_only": sorted(labels[k] for k in standing - record_keys),
                    "record_only": sorted(k for k in record_keys if k not in standing),
                }
        status = out["final"]["status"]
        if status == "comparison":
            ledger.append({"gate": "Stage-2 head-to-head on the new WSL, every arm installed fresh by its upstream "
                                   "command; its result selects", "kind": "comparison", "source": PROGRAM})
        if status == "partial_comparison":
            ledger.append({"gate": "Stage-2 comparison on the new WSL, every arm installed fresh by its upstream "
                                   "command; its preregistered result decides whether a challenger replaces or joins "
                                   "the standing picks", "kind": "comparison", "source": PROGRAM})
        if out["final"]["standing_picks"]:
            ledger.append({"gate": "Install each standing pick by its upstream command on the new WSL and record its "
                                   "acceptance", "kind": "new_host", "source": SELECTION})
        rows.append(out)

    counts = {}
    for r in rows:
        counts[r["final"]["status"]] = counts.get(r["final"]["status"], 0) + 1
    agreements = {}
    for r in rows:
        if r["agreement"]:
            agreements[r["agreement"]] = agreements.get(r["agreement"], 0) + 1
    behind = sorted({f"{w['name']} {w['pin']} -> {w['latest_upstream']}" for r in rows for w in r["selection_of_record"]
                     if w.get("pin_is_latest") == "no" and w.get("latest_upstream")})
    inputs = {rel: sha256(rel) for rel in (EDITION, SELECTION, GRAND_LIST) + ((CROSS_FAMILY,) if cross else ())}
    if facts_digest():
        inputs[FACTS + "/"] = facts_digest()
    return {
        "schema_version": 1,
        "kind": "final_catalog",
        "date_utc": edition["edition"]["date_utc"],
        "meaning": ("Per layer: what the source host records (bookkeeping; an unjudged incumbent where no blind record "
                    "exists), what each blind model family picks, and the standing picks and status the frozen "
                    "agreement rule gives. A standing pick is the layer's pick for the new WSL clean install and is "
                    "final once it passes acceptance on the new host and, where challengers exist, the layer's "
                    "measured comparison. Nothing here installs, accepts or authorizes a candidate, and no selection "
                    "of record changes."),
        "statuses": STATUSES,
        "agreement_rule": AGREEMENT_RULE if cross else None,
        "cross_family": ({k: cross.get(k) for k in ("family", "run", "contamination_audit")} if cross else
                         {"status": "not_run"}),
        "inputs": inputs,
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "by_catalog": {c: sum(1 for r in rows if r["catalog"] == c) for c in ("foundation", "us-equities", "cross")},
            "final_status": dict(sorted(counts.items())),
            "agreement": dict(sorted(agreements.items())),
            "rows_where_blind_differs_from_record": sum(
                1 for r in rows if r["disagreement_with_record"] and (r["disagreement_with_record"]["blind_only"]
                                                                     or r["disagreement_with_record"]["record_only"])),
            "rows_with_standing_picks": sum(1 for r in rows if r["final"]["standing_picks"]),
            "rows_where_standing_picks_differ_from_record": sum(
                1 for r in rows if r["final"].get("versus_record") and (r["final"]["versus_record"]["standing_only"]
                                                                       or r["final"]["versus_record"]["record_only"])),
            "record_pins_behind_upstream": behind,
        },
    }


def md_cell(value) -> str:
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def next_gate(row: dict) -> str:
    preferred = {"two_family_pick": "new_host", "shared_pick": "new_host", "partial_comparison": "comparison",
                 "comparison": "comparison",
                 "pending_cross_family": "cross_family", "owner_lane_run_pending": "merit_record",
                 "no_blind_record": "merit_record"}[row["final"]["status"]]
    for gate in row["gate_ledger"]:
        if gate["kind"] == preferred:
            return gate["gate"]
    return row["gate_ledger"][0]["gate"] if row["gate_ledger"] else "—"


def render_md(data: dict) -> str:
    s = data["summary"]
    lines = [
        f"# Final catalog ({data['date_utc']})",
        "",
        "Generated by `scripts/final_catalog.py` from the dated new-WSL architecture edition, the blind clean-install "
        "selection, its cross-family run and the new-host grand list. Do not edit by hand; run "
        "`python3 scripts/final_catalog.py --write`. It judges nothing: the standing picks and statuses apply the "
        "agreement rule frozen before the cross-family run, as written. A pick both model families made stands as "
        "the layer's pick for the new WSL; it is final once it passes acceptance on the new host and, where "
        "challengers exist, the layer's measured comparison. No selection of record changes here.",
        "",
        f"Rows: {s['rows']} ({s['by_catalog']['foundation']} foundation, {s['by_catalog']['us-equities']} trading, "
        f"{s['by_catalog']['cross']} cross-cutting). Final status: "
        + ", ".join(f"`{k}` {v}" for k, v in s["final_status"].items())
        + ". Cross-family agreement: "
        + (", ".join(f"`{k}` {v}" for k, v in s["agreement"].items()) if s["agreement"] else "not run")
        + f". Rows with standing picks: {s['rows_with_standing_picks']}, of which "
        f"{s['rows_where_standing_picks_differ_from_record']} differ from the source host's record. Rows where the "
        f"blind Claude recommendation differs from that record: {s['rows_where_blind_differs_from_record']}.",
        "",
        "## Status meanings",
        "",
    ]
    for key, text in data["statuses"].items():
        lines.append(f"- `{key}`: {text}.")
    titles = (("foundation", "Foundation layers"), ("cross", "Cross-cutting rows"),
              ("us-equities", "Trading layers (owner: trading lane)"))
    for catalog, title in titles:
        lines += ["", f"## {title}", "",
                  "| Layer | Final status | Standing picks | Comparison arms (challengers) | Blind (Claude) | "
                  "GPT-6.1 Sol | Agreement | Source host's record | Next gate |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in (r for r in data["rows"] if r["catalog"] == catalog):
            final = r["final"]
            cell = md_cell(final["standing_picks"])
            if final.get("provisional_picks") and not final["standing_picks"]:
                cell = "provisional: " + md_cell(final["provisional_picks"])
            blind = r["blind"]
            blind_cell = "—" if blind is None else f"{blind['status']}: " + md_cell([display(p) for p in blind["picks"]])
            gpt = r["cross_family"]
            gpt_cell = "—" if gpt is None else f"{gpt['status']}: " + md_cell([display(p) for p in gpt["picks"]])
            record = md_cell([f"{github_key(w['repository']) or w['name']} {w['pin']}" for w in r["selection_of_record"]])
            if blind is None:
                record = "unjudged incumbent: " + record
            lines.append(f"| {md_cell(r['title'])} | `{final['status']}` | {cell} | {md_cell(final['comparison_arms'])} "
                         f"| {blind_cell} | {gpt_cell} | {md_cell(r['agreement'])} | {record} | {md_cell(next_gate(r))} |")
    lines += ["", "## Selection-of-record pins behind upstream", ""]
    lines += [f"- {md_cell(b)}" for b in s["record_pins_behind_upstream"]] or ["- none"]
    lines += ["", "## Inputs", "", "| File | sha256 |", "| --- | --- |"]
    lines += [f"| `{rel}` | `{digest}` |" for rel, digest in data["inputs"].items() if rel != GRAND_LIST]
    lines += ["", f"The grand-list context (`{GRAND_LIST}`: each layer's decision and open-gap counts) is in the JSON "
              "form only."]
    lines += ["", "## How to update this page", "",
              "Generated, not hand-edited. After an edition update, a change to the blind selection or its cross-family "
              "record, run `python3 scripts/final_catalog.py --write` and commit the outputs. A move of the grand list "
              "alone shows as drift in `--check` and is refreshed with the next write. `--check` runs in CI."]
    return "\n".join(lines) + "\n"


def without_context(data: dict) -> dict:
    """The output with the grand-list context removed, for the strict part of --check."""
    clone = json.loads(json.dumps(data))
    clone["inputs"].pop(GRAND_LIST, None)
    for row in clone["rows"]:
        row["grand_list"] = None
    return clone


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 if the checked-in outputs differ (default)")
    mode.add_argument("--write", action="store_true", help="write the outputs")
    args = parser.parse_args(argv)
    data = build()
    outputs = {OUT_JSON: json.dumps(data, indent=2, ensure_ascii=False) + "\n", OUT_MD: render_md(data)}
    for rel, text in outputs.items():
        for label, pattern in PRIVATE_CONTENT:
            if pattern.search(text):
                print(f"{rel}: {label} in generated output", file=sys.stderr)
                return 1
    if args.write:
        for rel, text in outputs.items():
            (ROOT / rel).write_text(text, encoding="utf-8")
            host_receipts.register_file(ROOT, rel)
        print(json.dumps({"status": "written", "rows": len(data["rows"]), "final_status": data["summary"]["final_status"]}))
        return 0
    if not (ROOT / OUT_JSON).is_file() or not (ROOT / OUT_MD).is_file():
        print(f"missing: run python3 scripts/final_catalog.py --write", file=sys.stderr)
        return 1
    committed = json.loads((ROOT / OUT_JSON).read_text(encoding="utf-8"))
    stale = []
    if without_context(committed) != without_context(data):
        stale.append(OUT_JSON)
    if (ROOT / OUT_MD).read_text(encoding="utf-8") != outputs[OUT_MD]:
        stale.append(OUT_MD)
    if stale:
        print("stale: " + ", ".join(stale) + " no longer match their inputs; run python3 scripts/final_catalog.py --write",
              file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "rows": len(data["rows"]), "grand_list_drift": committed != data}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
