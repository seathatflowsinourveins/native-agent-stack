#!/usr/bin/env python3
"""Project the 2026-09-27 per-tool evidence cards into the token topic rows.

Reads cards/<tool>.json and invoke_by_tool.json beside this file and writes, or checks,
three things in docs/token-efficiency-stack.json:

- the five card fields of each row that has a card: upstream, native_adaptation,
  adapted_performance, invoke_rates and gpt6_review;
- that row's evidence_card identity (path, sha256, bytes of the complete card);
- the document's evidence_cards block.

Every other field of the topic is left as it is. The projection is deterministic: no
network, no model and no clock. Run it from any directory:

    python3 evidence/artifacts/token-stack-cards-20260927/project_topic.py --check
    python3 evidence/artifacts/token-stack-cards-20260927/project_topic.py --write
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOPIC = "docs/token-efficiency-stack.json"
EDITION = "2026-09-27"
FIELDS = ("upstream", "native_adaptation", "adapted_performance", "invoke_rates", "gpt6_review")
NOT_SELECTED = {
    "gpt-tokenizer": ("Not a selected component in manifests/stack.json, and the explorer accepts topic rows only "
                      "for selected components. tools/token-report/token_manifest.py pins it (3.4.0) as the exact "
                      "o200k_base counter behind every comparison."),
}


def relative(path):
    return path.relative_to(ROOT).as_posix()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def project(card):
    """The five topic fields of one card: each is the card section of the same name, except
    native_adaptation omits stack_entry and gpt6_review omits the reviewer's check log."""
    native = {key: value for key, value in card["native_adaptation"].items() if key != "stack_entry"}
    review = card["gpt6_review"]
    final = review.get("final_verdict") or {}
    return {
        "upstream": card["upstream"],
        "native_adaptation": native,
        "adapted_performance": card["adapted_performance"],
        "invoke_rates": card["invoke_rates"],
        "gpt6_review": {
            "verdict": review["verdict"],
            "findings": review.get("findings") or [],
            "resolutions": review.get("resolutions") or [],
            "final_verdict": {
                "verdict": final.get("verdict"),
                "summary": final.get("summary"),
                "gaps": final.get("gaps") or [],
                "claims_verified": [{"claim": claim.get("claim"), "result": claim.get("result")}
                                    for claim in final.get("claims_verified") or []],
                "skills_used": final.get("skills_used") or [],
                "token_tools_used": final.get("token_tools_used") or [],
            },
            "harness": review.get("harness") or {},
        },
    }


def card_identity(path):
    raw = path.read_bytes()
    return {"path": relative(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def cards_block(index, with_cards, without_cards, invoke):
    return {
        "edition": EDITION,
        "readme": relative(HERE / "README.md"),
        "projection": relative(Path(__file__).resolve()),
        "fields": list(FIELDS),
        "projection_rule": ("Each field is the evidence card's section of the same name, except that "
                            "native_adaptation omits stack_entry (manifests/stack.json holds it) and gpt6_review "
                            "omits the reviewer's check log (checked) and keeps each verified claim's text and "
                            "result without its evidence pointer. evidence_card identifies the complete card."),
        "rows_with_cards": with_cards,
        "rows_without_cards": without_cards,
        "cards_without_rows": [{"tool": tool, "card": relative(HERE / "cards" / (tool + ".json")), "reason": reason}
                               for tool, reason in sorted(NOT_SELECTED.items())
                               if any(item["tool"] == tool for item in index)],
        "evidence_classes": {
            "upstream": "GPT-6 upstream source review; every fact carries its URL.",
            "native_adaptation": "GPT-6 assessment of this repository's recipes, templates and host wiring, with repository paths.",
            "adapted_performance.exact_comparisons": "Exact o200k_base artifact comparisons, one per payload and lane.",
            "adapted_performance.native_counter": "The tool's own counter over its fixture window.",
            "adapted_performance.native_snapshot": "Upstream retained-history estimates at the observed time.",
            "invoke_rates.populations": "Transcript-derived invocation attempts and agents invoking, per population, over invoke_window.",
            "invoke_rates.live_otel": "Live OTel/Loki series over the series' own window.",
            "gpt6_review": ("GPT-6 review of an earlier assembly of the card against its cited sources, and its final "
                            "verdict on the native adaptation, given after the assembler edit. resolutions holds the "
                            "repair round's dispositions: an edit, or a deferral (text starting with 'deferred'). The "
                            "cards were re-assembled after the review, so a finding without a disposition can already "
                            "be applied in the published field; the README's findings table gives each finding's "
                            "status in the published card (applied, partial or open)."),
        },
        "invoke_window": invoke["window"],
        "invoke_evidence_class": invoke["evidence_class"],
        "invoke_method": invoke["method"],
        "codex_negative_control_sessions": invoke["codex_negative_control_sessions"],
        "boundary": ("These classes are never summed: an exact comparison, a counter window, an invoke population "
                     "and a verdict answer different questions over different windows. Invoke counts are attempts, "
                     "not success rates or savings. The arm-B native rows stay pending until the preregistered "
                     "E2E runs. The GPT-6 card reviews (2026-09-27, 01:37Z to 02:04Z with the repair round) read an "
                     "earlier assembly: the coordinator edited the assembler at 02:09:55Z and wrote the published "
                     "cards at 03:27:02Z, so a finding can quote field text the card no longer has. For example, "
                     "serena's empty-series finding is applied: its live OTel series holds codex_exec -> serena, "
                     "4 calls. The cards' README gives the status of all 23 findings in the published cards: 13 "
                     "applied, 5 partial, 5 open. Card references to <scratch>/, ../rr/, ../html-report/ and "
                     "../cbm-q3/ name the coordinator's private working set, which this repository does not "
                     "retain."),
    }


def projected(topic):
    index = load(HERE / "cards/index.json")
    cards = {item["tool"]: HERE / "cards" / (item["tool"] + ".json") for item in index}
    result = json.loads(json.dumps(topic))
    with_cards, without_cards = [], []
    for row in result["rows"]:
        path = cards.get(row["component_id"])
        for field in FIELDS + ("evidence_card",):
            row.pop(field, None)
        if path is None:
            without_cards.append(row["component_id"])
            continue
        row.update(project(load(path)))
        row["evidence_card"] = card_identity(path)
        with_cards.append(row["component_id"])
    unplaced = sorted(set(cards) - set(with_cards) - set(NOT_SELECTED))
    if unplaced:
        raise SystemExit("cards without a topic row or a recorded reason: " + ", ".join(unplaced))
    block = cards_block(index, with_cards, without_cards, load(HERE / "invoke_by_tool.json"))
    if "evidence_cards" in result:
        result["evidence_cards"] = block
        return result
    ordered = {}
    for key, value in result.items():
        ordered[key] = value
        if key == "scope":
            ordered["evidence_cards"] = block
    return ordered


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="fail if the topic differs from the projection")
    mode.add_argument("--write", action="store_true", help="rewrite the topic with the projection")
    args = parser.parse_args(argv)
    target = ROOT / TOPIC
    current = target.read_text(encoding="utf-8")
    expected = encode(projected(json.loads(current)))
    if args.write:
        target.write_text(expected, encoding="utf-8")
        print(f"wrote {TOPIC}")
        return 0
    if current != expected:
        print(f"{TOPIC} differs from the projection of {relative(HERE / 'cards')}; run --write")
        return 1
    print(f"{TOPIC} matches the projection of {relative(HERE / 'cards')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
