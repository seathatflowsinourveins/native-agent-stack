#!/usr/bin/env python3
"""Write the 2026-09-27 edition of docs/token-efficiency-stack.json from the sanitized cards.

Each row whose component has a card gains a `card` object condensed from that card by
field selection (no claim is truncated), with every block labelled by its evidence
class. The other rows gain an explicit "no card in this edition" marker. Pins are not
copied into rows: scripts/build_ecosystem.py joins manifests/stack.json at build time,
and `recorded_pin` only records which pin the card describes. Findings from the GPT-6
review are carried with the status established by checking each one against its
source; corrections this edition applies are named in the finding's note.

Usage: condense.py --repo-root ROOT   (reads and rewrites ROOT/docs/token-efficiency-stack.json)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EDITION = "2026-09-27"
BUNDLE = "evidence/artifacts/token-stack-cards-20260927"
TOPIC = "docs/token-efficiency-stack.json"
STACK = "manifests/stack.json"
NO_CARD = "no card in this edition"

CLASS = {
    "upstream": "upstream provenance (GitHub releases/latest API reads and pinned upstream sources, checked 2026-09-26)",
    "native_adaptation": ("repository configuration review (Claude and Codex wiring as recorded in this repository's "
                          "templates, recipes and receipts on 2026-09-26; not a new host check)"),
    "adapted_performance": "one evidence class per figure; figures are never summed across classes, lanes or scopes",
    "native_counter": "native counter (tool-reported figure in the tool's own unit and method; not an o200k_base count)",
    "native_snapshot": "upstream estimate (tool-retained history snapshot; scopes can nest and are never added)",
    "invoke_rates": ("local integration (transcript counts over the dated window; a command can count for several "
                     "tools; Codex sessions without the context-mode block are excluded negative controls)"),
    "gpt6_review": ("model review (GPT-6 astra at effort max over the card's retained sources): judgment, not "
                    "execution; each finding carries the status found by checking it against its source"),
}

ADDRESSED = "addressed in the final card text"
REPAIRED = "resolved in the review's repair round"
CORRECTED = "corrected in this edition's row"
CARRIED = "carried with the discrepancy named"
NOT_CARRIED = "not carried into this row"

# (tool, finding index) -> (status, note). Each note names the source checked.
FINDING_STATUS = {
    ("agentsview", 0): (REPAIRED, "The review's resolution records the four assembly dispositions."),
    ("agentsview", 1): (REPAIRED, "The review's resolution cites the retained projects and session-list reads."),
    ("ai-memory", 0): (REPAIRED, "The install recommendation now adds the ai-memory-cli package selector."),
    ("ai-memory", 1): (NOT_CARRIED, "The row omits stack_entry.freshness. evidence/artifacts/"
                       "ai-memory-241-codex-capture-20260926/README.md records the user's 2026-09-26 hook trust and "
                       "a Codex capture through 2.4.1; PreCompact execution stays unverified."),
    ("ai-memory", 2): (CARRIED, "e2e_returned_results.records_total_note gives all three counts."),
    ("ai-memory", 3): (REPAIRED, "The assessment calls 54 the card's reported figure, reconciliation open."),
    ("ast-grep", 0): (REPAIRED, "The limitation now describes the preliminary --allow-custom-languages scan."),
    ("ccusage", 0): (REPAIRED, "The review's resolution records the five dispositions applied at assembly."),
    ("codebase-memory-mcp", 0): (ADDRESSED, "q3_fixture.false_positive now gives true edges as 0.38-0.95."),
    ("codebase-memory-mcp", 1): (REPAIRED, "The fix text discloses 9 of 12 callers and 7 of 12 at a 0.5 cutoff."),
    ("jcodemunch-mcp", 0): (CORRECTED, "Commands use the retained records' $RR/jcodemunch-mcp root, the root "
                            "the argv of every jcodemunch-* record in returned-results-subset.json uses."),
    ("mcporter", 0): (CORRECTED, "The assessment names the workflow_children_with_lanes_block population."),
    ("qmd", 0): (CORRECTED, "The PASS wording is removed from the payload and fidelity_status records the "
                 "refutation; evidence/artifacts/token-e2e-codex-20260926/receipt.json corrections_to_296 "
                 "confirms the wrong-document retrieval."),
    ("qmd", 1): (CORRECTED, "fidelity.correction replaces the repeated historical PASS."),
    ("qmd", 2): (CARRIED, "e2e_returned_results.records_total_note gives all three counts."),
    ("qmd", 3): (REPAIRED, "The assessment calls 31 the card's reported figure, reconciliation open."),
    ("repomix", 0): (CORRECTED, "The PASS wording is removed from the payload and fidelity_status records the "
                     "superseded pass; records repomix-08-mcp-grep-full and repomix-09-mcp-grep-compress "
                     "return 1 and 0 matches for the status_body definition."),
    ("rtk", 0): (ADDRESSED, "The payload cites record codex-34-o200k-compare, which reports 356 -> 341."),
    ("rtk", 1): (ADDRESSED, "The eligibility keeps the lossy qualification (7 of 10 commit subjects)."),
    ("rtk", 2): (ADDRESSED, "shortfall_cause says the 16,493 skipped commands are not classified by cause."),
    ("serena", 0): (ADDRESSED, "invoke_rates.live_otel lists client codex_exec, server serena, 4 calls."),
    ("toon", 0): (ADDRESSED, "shortfall_cause calls the handbook's 5-record minimum a local heuristic."),
    ("toon", 1): (REPAIRED, "new_since_pin narrows the stderr claim to invalid-argument usage."),
}

# Verified replacements for card text that a finding refuted (tool, field) -> (old, new).
TEXT_CORRECTIONS = {
    ("qmd", "payload0"): ("; answer verified (PASS)", ""),
    ("repomix", "payload0"): ("; all 47 function names verified (PASS)", ""),
    ("mcporter", "assessment"): ("the lanes-block population", "the workflow_children_with_lanes_block population"),
    ("jcodemunch-mcp", "commands"): ("<scratch>/rr/", "$RR/"),
}
FIDELITY_STATUS = {
    "qmd": ("refuted: wrong-document retrieval. The retrieved catalogs/us-equities/engines-strategies.md does not "
            "answer the release re-pin question (evidence/artifacts/token-e2e-codex-20260926/receipt.json, "
            "corrections_to_296). The token counts stand; they are not evidence of a successful retrieval."),
    "repomix": ("refuted: superseded false pass. --compress dropped the multi-line def status_body; records "
                "repomix-08-mcp-grep-full and repomix-09-mcp-grep-compress return 1 and 0 matches. The token "
                "counts stand as a size comparison only."),
}
FIDELITY_CORRECTION = {
    "qmd": ("The card's 'answer verified (PASS)' repeats the historical #296 release re-pin answer, refuted as "
            "wrong-document retrieval (corrections_to_296); the isolated-index integration passes on its own "
            "records."),
    "repomix": ("The card's 'all 47 function names verified (PASS)' is the superseded #296 pass; --compress "
                "dropped def status_body (records repomix-08-mcp-grep-full, repomix-09-mcp-grep-compress)."),
}
RECORDS_TOTAL_NOTE = {
    "ai-memory": ("The card reports 54. The source's ai-memory component summary and its ai-memory-* records count "
                  "48; filtering every record by component_ids gives 59 (adds cross-tool client records). "
                  "Exact reconciliation is open."),
    "qmd": ("The card reports 31. The source's qmd component summary and its qmd-* records count 30; filtering "
            "every record by component_ids gives 36 (adds cross-tool client records). Exact reconciliation is open."),
}


def replace_once(text: str, key) -> str:
    old, new = TEXT_CORRECTIONS[key]
    if old not in text:
        raise SystemExit(f"{key}: expected card text is absent; recheck the correction")
    return text.replace(old, new)


def upstream(card):
    block = card["upstream"]
    wiring = [{"client": client, "how": value.get("how"), "url": value.get("url")}
              for client, value in block.get("recommended_wiring", {}).items()]
    out = {"evidence_class": CLASS["upstream"], "latest_release": block["latest_release"],
           "latest_date": block["latest_date"]}
    if block.get("latest_release_url"):
        out["latest_release_url"] = block["latest_release_url"]
    out.update(behind_by=block["behind_by"], recommended_install=block["recommended_install"],
               recommended_wiring=wiring, new_since_pin=block.get("new_since_pin", []),
               limitations=block.get("limitations", []))
    return out


def adaptation(tool, card):
    block = card["native_adaptation"]
    assessment = block["assessment"]
    if (tool, "assessment") in TEXT_CORRECTIONS:
        assessment = replace_once(assessment, (tool, "assessment"))
    deviations = [{key: item[key] for key in ("what", "why", "fix") if item.get(key)}
                  for item in block.get("deviations_from_upstream", [])]
    return {"evidence_class": CLASS["native_adaptation"], "claude_wiring": block["claude_wiring"],
            "codex_wiring": block["codex_wiring"], "lane_rule": block["lane_rule"], "deviations": deviations,
            "pending_fixes": block.get("pending_fixes", []), "assessment": assessment}


def e2e(tool, card):
    block = card["e2e_returned_results"]
    commands = []
    for command in block["upstream_commands"]:
        text = command["cmd"]
        if (tool, "commands") in TEXT_CORRECTIONS and TEXT_CORRECTIONS[(tool, "commands")][0] in text:
            text = replace_once(text, (tool, "commands"))
        commands.append({"cmd": text, "exit": command.get("exit"), "returned": command.get("returned")})
    fidelity = dict(block["fidelity"])
    if tool in FIDELITY_CORRECTION:
        fidelity["result"] = fidelity["result"].split(";", 1)[1].strip() if ";" in fidelity["result"] else ""
        fidelity["correction"] = FIDELITY_CORRECTION[tool]
    out = {"evidence_class": block["evidence_class"], "status": block["status"], "reason": block["reason"],
           "run_utc": block["run_utc"], "fidelity": fidelity, "commands": commands,
           "records_total": block["records_total"]}
    if tool in RECORDS_TOTAL_NOTE:
        out["records_total_note"] = RECORDS_TOTAL_NOTE[tool]
    out["cited_records"] = [record["id"] for record in block["records_shown"]]
    out["records_source"] = f"{BUNDLE}/returned-results-subset.json"
    return out


def performance(tool, card):
    block = card["adapted_performance"]
    entries = []
    for index, row in enumerate(block["exact_comparisons"]):
        entry = {key: row.get(key) for key in ("lane", "payload", "before_tokens", "after_tokens", "change_pct",
                                              "encoding", "eligibility", "evidence_class", "first_seen",
                                              "last_seen")}
        if index == 0 and (tool, "payload0") in TEXT_CORRECTIONS:
            entry["payload"] = replace_once(entry["payload"], (tool, "payload0"))
            entry["fidelity_status"] = FIDELITY_STATUS[tool]
        entries.append(entry)
    out = {"evidence_class": CLASS["adapted_performance"], "per_payload_and_lane": entries}
    if block.get("native_counter"):
        out["native_counter"] = {"evidence_class": CLASS["native_counter"], **block["native_counter"]}
    if block.get("native_snapshot"):
        out["native_snapshots"] = [{"evidence_class": CLASS["native_snapshot"],
                                    **{key: value for key, value in snapshot.items() if key != "tool"}}
                                   for snapshot in block["native_snapshot"]]
    if block.get("shortfall_cause"):
        out["shortfall_cause"] = block["shortfall_cause"]
    if block.get("q3_fixture"):
        out["q3_fixture"] = block["q3_fixture"]
    return out


def invoke(card, method):
    block = card["invoke_rates"]
    if block["method"] != method:
        raise SystemExit(f"{card['tool']}: invoke method differs from the edition's shared method")
    window = block["window"]
    out = {"evidence_class": CLASS["invoke_rates"],
           "window": f"{window['last_36h_start']} to {window['now']} (last 36 h)",
           "populations": [{"population": name, **counts} for name, counts in block["populations"].items()]}
    if block.get("live_otel"):
        out["live_otel"] = block["live_otel"]
    out["arm_b_native"] = block["arm_b_native"]
    return out


def review(tool, card):
    block = card["gpt6_review"]
    final = block["final_verdict"]
    findings = []
    for index, finding in enumerate(block.get("findings", [])):
        status, note = FINDING_STATUS[(tool, index)]
        item = {"severity": finding.get("severity"), "field": finding.get("field"), "status": status}
        if status not in (ADDRESSED, REPAIRED):
            # The issue text explains a correction or an open discrepancy; addressed ones stay in the card.
            item["issue"] = finding.get("issue")
        item["note"] = note
        findings.append(item)
    models = sorted({f"{run.get('model')} at effort {run.get('effort')}"
                     for run in block.get("harness", {}).values() if isinstance(run, dict)})
    return {"evidence_class": CLASS["gpt6_review"], "review_verdict": block["verdict"],
            "final_verdict": final["verdict"], "summary": final["summary"],
            "gaps": [{key: gap[key] for key in ("gap", "action", "evidence") if gap.get(key)}
                     for gap in final.get("gaps", [])],
            "findings": findings, "claims_verified": len(final.get("claims_verified", [])),
            "claims_holding": sum(1 for claim in final.get("claims_verified", []) if claim.get("result") == "holds"),
            "runs": sorted(block.get("harness", {})), "models": models,
            "source": f"{BUNDLE}/gpt6-reviews.json"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.repo_root
    topic = json.loads((root / TOPIC).read_text(encoding="utf-8"))
    stack = {component["id"]: component
             for component in json.loads((root / STACK).read_text(encoding="utf-8"))["components"]}
    cards = {}
    for path in sorted((root / BUNDLE / "cards").glob("*.json")):
        if path.name != "index.json":
            raw = path.read_bytes()
            cards[path.stem] = (json.loads(raw), {"path": f"{BUNDLE}/cards/{path.name}", "bytes": len(raw),
                                                 "sha256": hashlib.sha256(raw).hexdigest()})
    used = set()
    methods = sorted({card["invoke_rates"]["method"] for card, _ in cards.values()})
    if len(methods) != 1:
        raise SystemExit("cards disagree on the invoke-rate method")
    for row in topic["rows"]:
        tool = row["component_id"]
        row.pop("card", None)
        if tool not in cards:
            row["card"] = {"status": NO_CARD, "edition": EDITION}
            continue
        card, source = cards[tool]
        used.add(tool)
        pinned = stack[tool]["version"]
        if not card["pin"].startswith(pinned):
            raise SystemExit(f"{tool}: the card's pin text does not start with the stack version {pinned}")
        missing = {(tool, index) for index in range(len(card["gpt6_review"].get("findings", [])))} - set(FINDING_STATUS)
        if missing:
            raise SystemExit(f"{tool}: findings without a checked status: {sorted(missing)}")
        row["card"] = {"status": "present", "edition": EDITION, "recorded_pin": pinned, "source": source,
                       "upstream": upstream(card), "native_adaptation": adaptation(tool, card),
                       "e2e_returned_results": e2e(tool, card), "adapted_performance": performance(tool, card),
                       "invoke_rates": invoke(card, methods[0]), "gpt6_review": review(tool, card)}
    without_row = sorted(set(cards) - used)
    topic["scope"] = topic["scope"].split(" The 2026-09-27 edition", 1)[0] + (
        " The 2026-09-27 edition adds a per-tool card to %d rows (upstream, native adaptation, E2E returned "
        "results, adapted performance per payload and lane, invoke rates and GPT-6 review, each labelled with its "
        "evidence class) and an explicit no-card marker to the other %d. Versions come from manifests/stack.json "
        "when the page is built; a drift note appears where a card describes another pin."
        % (len(used), len(topic["rows"]) - len(used)))
    topic["edition"] = {
        "date_utc": EDITION,
        "previous": {"synthesized_date_utc": topic.get("synthesized_date_utc"),
                     "source_revision": topic.get("source_revision")},
        "added_field": "card",
        "card_rows": len(used), "rows_without_card": len(topic["rows"]) - len(used),
        "pin_policy": ("Rows carry no version or repository. scripts/build_ecosystem.py joins each component_id to "
                       "manifests/stack.json when the page is built; card.recorded_pin is the pin the card "
                       "describes, and a differing stack pin renders a drift note instead of editing the card."),
        "evidence_policy": ("Each card block names its evidence class: upstream provenance, repository configuration "
                            "review, local integration (upstream commands on the source host with returned data), "
                            "exact artifact comparisons (o200k_base), native counters, upstream estimates and "
                            "model review. Figures stay in their own class, lane and scope and are never summed. "
                            "Historical host results are not a new host's acceptance."),
        "invoke_rates_method": methods[0],
        "cards_without_row": [{"tool": tool, "card": cards[tool][1]["path"],
                               "reason": ("No manifests/stack.json component: the topic joins only selected stack "
                                          "components. tools/token-report/token_manifest.py pins it at 3.4.0 as the "
                                          "o200k_base tokenizer behind every exact comparison; the card records "
                                          "upstream 4.0.0 (2026-08-16).")}
                              for tool in without_row],
        "source_paths": [f"{BUNDLE}/README.md", f"{BUNDLE}/cards/index.json", f"{BUNDLE}/returned-results-subset.json",
                         f"{BUNDLE}/invoke-by-tool.json", f"{BUNDLE}/gpt6-reviews.json"],
    }
    added = json.dumps([topic["edition"], [row["card"] for row in topic["rows"]]], ensure_ascii=False)
    if "1.1M" in added:
        # tests/test_context_mode_practice_docs.py requires that label on every quoted 1.1M figure.
        raise SystemExit("a new card string quotes 1.1M; attach the upstream-rendered figure label first")
    text = json.dumps(topic, indent=2, ensure_ascii=True) + "\n"
    (root / TOPIC).write_text(text, encoding="utf-8")
    print(json.dumps({"rows": len(topic["rows"]), "card_rows": len(used), "without_card": len(topic["rows"]) - len(used),
                      "cards_without_row": without_row, "bytes": len(text.encode())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
