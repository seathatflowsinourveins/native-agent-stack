#!/usr/bin/env python3
"""Join the already-recorded landscape verdicts, lifecycle decisions, host
receipts and gap crosswalk into one per-component independent-review and
E2E-status view.

This never selects a winner, records a receipt or runs a lane; it only joins
what ``catalogs/landscape/{foundation,us-equities}.json``,
``catalogs/foundation/decisions.json``, ``scripts/host_receipts.py`` receipts
and ``catalogs/landscape/gap-crosswalk-92bb279.json`` (optional) already say,
and writes the result deterministically to
``catalogs/landscape/component-evidence-matrix.json`` and
``docs/component-evidence-matrix.md``.

Modes: ``--check`` (default) recomputes both outputs in memory and exits 1 on
any difference from the checked-in files, or on a flip-rule violation (a
declared ``platform_status`` above what ``scripts/platform_status.py`` derives,
for the platforms in ``landscape.ENFORCED_PLATFORMS``); ``--write`` recomputes
and writes them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from . import host_receipts
    from . import platform_status as platform_evidence
    from .catalog_decisions import InvalidDecisionIndex, load, safe_file, unique_json
    from .landscape import ENFORCED_PLATFORMS, PLATFORM_KEYS
    from .validate import PRIVATE_CONTENT
except ImportError:  # running as a plain script, not a package
    import host_receipts
    import platform_status as platform_evidence
    from catalog_decisions import InvalidDecisionIndex, load, safe_file, unique_json
    from landscape import ENFORCED_PLATFORMS, PLATFORM_KEYS
    from validate import PRIVATE_CONTENT


CHECKED_AT = "2026-09-22"
SCOPE = (
    "Per-component independent-review status and per-platform E2E state, joined from "
    "catalogs/landscape/{foundation,us-equities}.json winners/alternatives, "
    "catalogs/foundation/decisions.json lifecycle stage_refs, scripts/host_receipts.py receipts "
    "and the gap crosswalk (open executable_now gaps per layer, when present). It never selects "
    "a winner or records a receipt; it is a read-only join of evidence recorded elsewhere."
)
LANDSCAPE_FILES = {
    "foundation": "catalogs/landscape/foundation.json",
    "us-equities": "catalogs/landscape/us-equities.json",
}
DECISIONS_FILE = "catalogs/foundation/decisions.json"
GAP_CROSSWALK_FILE = "catalogs/landscape/gap-crosswalk-92bb279.json"
STACK_FILE = "manifests/stack.json"
ADJUDICATION_TEMPLATE = "evidence/artifacts/layer-verdicts-20260922/adjudication/{catalog}-{layer_id}-20260922.json"

OUTPUT_JSON = "catalogs/landscape/component-evidence-matrix.json"
OUTPUT_MD = "docs/component-evidence-matrix.md"

INDEPENDENT_REVIEW_STATES = {
    "dual_lane_same_winner", "dual_lane_adjudicated", "pending_lanes", "single_lane",
}


# --------------------------------------------------------------------------- loading


def load_optional(root: Path, relative: str):
    """Return the parsed JSON document at ``relative``, or ``None`` if absent/unreadable."""
    try:
        path = safe_file(root, relative)
    except InvalidDecisionIndex:
        return None
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    except (OSError, UnicodeError, ValueError):
        return None


def decisions_by_component(decisions_doc: dict | None) -> dict[str, list[dict]]:
    result: dict[str, set[tuple[str, str]]] = {}
    for decision in (decisions_doc or {}).get("decisions", []) or []:
        lifecycle = decision.get("lifecycle") if isinstance(decision, dict) else None
        for ref in (lifecycle or {}).get("stage_refs", []) or []:
            if not isinstance(ref, dict):
                continue
            component_id = ref.get("component_id")
            stage = ref.get("stage")
            status = ref.get("status")
            if not isinstance(component_id, str) or not isinstance(stage, str) or not isinstance(status, str):
                continue
            result.setdefault(component_id, set()).add((stage, status))
    return {
        component_id: [{"stage": stage, "status": status} for stage, status in sorted(pairs)]
        for component_id, pairs in result.items()
    }


def gap_counts_by_layer(gap_crosswalk_doc: dict | None) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for layer in (gap_crosswalk_doc or {}).get("layers", []) or []:
        if not isinstance(layer, dict):
            continue
        catalog = layer.get("catalog")
        layer_id = layer.get("layer_id")
        if not isinstance(catalog, str) or not isinstance(layer_id, str):
            continue
        open_executable_now = sum(
            1 for gap in layer.get("gaps", []) or []
            if isinstance(gap, dict) and gap.get("status") == "open" and gap.get("category") == "executable_now"
        )
        counts[(catalog, layer_id)] = open_executable_now
    return counts


def open_gap_counts_by_layer(gap_crosswalk_doc: dict | None) -> dict[tuple[str, str], int]:
    """Open gaps of any category (the crosswalk's status "open"), so a layer whose only open gap
    waits on a login, hardware or a user decision is not shown as having none."""
    counts: dict[tuple[str, str], int] = {}
    for layer in (gap_crosswalk_doc or {}).get("layers", []) or []:
        if isinstance(layer, dict) and isinstance(layer.get("catalog"), str) and isinstance(layer.get("layer_id"), str):
            counts[(layer["catalog"], layer["layer_id"])] = sum(
                1 for gap in layer.get("gaps", []) or [] if isinstance(gap, dict) and gap.get("status") == "open")
    return counts


def repository_to_component_id(stack_doc: dict | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for component in (stack_doc or {}).get("components", []) or []:
        if not isinstance(component, dict):
            continue
        repository = component.get("repository")
        component_id = component.get("id")
        if isinstance(repository, str) and isinstance(component_id, str):
            mapping.setdefault(repository, component_id)
    return mapping


# ---------------------------------------------------------------------- classification


def classify_independent_review(layer: dict) -> str:
    if layer.get("verdict_status") == "pending_lanes":
        return "pending_lanes"
    agreement = (layer.get("lanes") or {}).get("agreement")
    if agreement == "same_winner":
        return "dual_lane_same_winner"
    if agreement == "disagree":
        return "dual_lane_adjudicated"
    return "single_lane"


def find_adjudication_ref(root: Path, catalog: str, layer_id: str, layer: dict) -> str | None:
    candidate = ADJUDICATION_TEMPLATE.format(catalog=catalog, layer_id=layer_id)
    if (root / candidate).is_file():
        return candidate
    for gap in layer.get("open_gaps", []) or []:
        if isinstance(gap, str) and candidate in gap:
            return candidate
    return None


# --------------------------------------------------------------------- receipts join


def platform_receipt_info(receipts_summary: dict, component_id: str, platform_key: str) -> dict:
    component_bucket = receipts_summary.get("components", {}).get(component_id, {})
    platform_bucket = component_bucket.get("platforms", {}).get(platform_key)
    if not platform_bucket:
        return {"pass": 0, "fail": 0, "independently_reviewed_pass": 0, "independently_reviewed_fail": 0,
                "dissented": 0, "latest": None}
    stages = platform_bucket.get("stages", {}) or {}
    total_pass = sum(counts.get("pass", 0) for counts in stages.values() if isinstance(counts, dict))
    total_fail = sum(counts.get("fail", 0) for counts in stages.values() if isinstance(counts, dict))
    return {
        "pass": total_pass,
        "fail": total_fail,
        "independently_reviewed_pass": platform_bucket.get("independently_reviewed_passes", 0),
        "independently_reviewed_fail": platform_bucket.get("independently_reviewed_fails", 0),
        "dissented": platform_bucket.get("dissented", 0),
        "latest": platform_bucket.get("latest_observed_at_utc"),
    }


def build_winner(winner: dict, decisions: dict[str, list[dict]], receipts_summary: dict,
                 status_context: platform_evidence.StatusContext | None = None):
    """Per-platform catalog status, the status the evidence derives (scripts/platform_status.py),
    receipt counts and e2e_state. ``host_verified`` means the derived status is ``accepted``
    on the strength of a host receipt; otherwise e2e_state is the declared catalog status."""
    component_id = winner.get("component_id")
    if status_context is None:
        status_context = platform_evidence.StatusContext(summary=receipts_summary, registered_paths=frozenset())
    platforms: dict[str, dict] = {}
    violations: list[str] = []
    for platform_key in sorted(PLATFORM_KEYS):
        catalog_status = (winner.get("platform_status") or {}).get(platform_key, "untested")
        derived = platform_evidence.platform_status(platform_key, winner, status_context)
        host_verified = derived.status == "accepted" and any(
            ref.startswith("evidence/hosts/") for ref in derived.receipt_refs)
        platforms[platform_key] = {
            "catalog_status": catalog_status,
            "derived_status": derived.status,
            "derived_reason": derived.reason,
            "host_receipts": platform_receipt_info(receipts_summary, component_id, platform_key),
            "e2e_state": "host_verified" if host_verified else catalog_status,
        }
        if platform_key in ENFORCED_PLATFORMS:
            error = platform_evidence.declared_status_error(platform_key, catalog_status, winner, status_context)
            if error:
                violations.append(error)
    built = {
        "component_id": component_id,
        "repository": winner.get("repository"),
        "pin": winner.get("pin"),
        "evidence_class": winner.get("evidence_class"),
        "lifecycle_stages": decisions.get(component_id, []),
        "platforms": platforms,
    }
    return built, violations


def build_alternative(alternative: dict, repo_to_component: dict[str, str], receipts_summary: dict) -> dict:
    repository = alternative.get("repository")
    component_id = repo_to_component.get(repository) if isinstance(repository, str) else None
    e2e_state = "not_run"
    if isinstance(component_id, str):
        component_bucket = receipts_summary.get("components", {}).get(component_id)
        if component_bucket:
            any_reviewed = any(
                (platform_bucket or {}).get("independently_reviewed_native_proven_pass_stages")
                for platform_bucket in component_bucket.get("platforms", {}).values()
            )
            e2e_state = "host_verified" if any_reviewed else "receipts_recorded"
    return {
        "name": alternative.get("name"),
        "repository": repository,
        "disposition": alternative.get("disposition"),
        "evidence_class": alternative.get("evidence_class"),
        "e2e_state": e2e_state,
    }


def build_row(root: Path, catalog: str, layer: dict, decisions: dict[str, list[dict]],
              gap_counts: dict[tuple[str, str], int], receipts_summary: dict,
              repo_to_component: dict[str, str], open_gap_counts: dict[tuple[str, str], int] | None = None,
              status_context: platform_evidence.StatusContext | None = None):
    layer_id = layer.get("layer_id")
    independent_review = classify_independent_review(layer)
    adjudication_ref = find_adjudication_ref(root, catalog, layer_id, layer)

    winners = []
    flip_violations: list[str] = []
    for winner in layer.get("winners", []) or []:
        built, violations = build_winner(winner, decisions, receipts_summary, status_context)
        winners.append(built)
        flip_violations.extend(f"{catalog}/{layer_id} winner {built['component_id']!r}: {violation}"
                               for violation in violations)

    alternatives = [
        build_alternative(alternative, repo_to_component, receipts_summary)
        for alternative in layer.get("alternatives", []) or []
    ]

    row = {
        "catalog": catalog,
        "layer_id": layer_id,
        "title": layer.get("title"),
        "verdict_status": layer.get("verdict_status"),
        "independent_review": independent_review,
        "adjudication_ref": adjudication_ref,
        "open_executable_now_gaps": gap_counts.get((catalog, layer_id)),
        "open_gaps": (open_gap_counts or {}).get((catalog, layer_id)),
        "winners": winners,
        "alternatives": alternatives,
    }
    return row, flip_violations


# --------------------------------------------------------------------------- document


def build_document(root: Path):
    decisions_doc = load_optional(root, DECISIONS_FILE)
    decisions = decisions_by_component(decisions_doc)
    gap_doc = load_optional(root, GAP_CROSSWALK_FILE)
    gap_counts = gap_counts_by_layer(gap_doc)
    open_gap_counts = open_gap_counts_by_layer(gap_doc)
    stack_doc = load_optional(root, STACK_FILE)
    repo_to_component = repository_to_component_id(stack_doc)
    status_context = platform_evidence.load_context(root)
    receipts_summary = status_context.summary

    rows: list[dict] = []
    flip_violations: list[str] = []
    for catalog, relative in LANDSCAPE_FILES.items():
        landscape_doc = load_optional(root, relative)
        if landscape_doc is None:
            continue
        for layer in landscape_doc.get("layers", []) or []:
            if not isinstance(layer, dict):
                continue
            row, row_flip_violations = build_row(
                root, catalog, layer, decisions, gap_counts, receipts_summary, repo_to_component, open_gap_counts,
                status_context,
            )
            rows.append(row)
            flip_violations.extend(row_flip_violations)

    rows.sort(key=lambda row: (row["catalog"], row["layer_id"]))

    needs_host: dict[str, list[dict]] = {platform_key: [] for platform_key in sorted(PLATFORM_KEYS)}
    for row in rows:
        for winner in row["winners"]:
            for platform_key, entry in winner["platforms"].items():
                if entry["e2e_state"] not in ("accepted", "host_verified"):
                    needs_host[platform_key].append({
                        "catalog": row["catalog"],
                        "layer_id": row["layer_id"],
                        "component_id": winner["component_id"],
                        "e2e_state": entry["e2e_state"],
                    })
    for platform_key in needs_host:
        needs_host[platform_key].sort(key=lambda entry: (entry["catalog"], entry["layer_id"], entry["component_id"]))

    needs_independent_review = [
        {"catalog": row["catalog"], "layer_id": row["layer_id"], "independent_review": row["independent_review"]}
        for row in rows if row["independent_review"] in ("pending_lanes", "single_lane")
    ]

    totals = {
        "layers": len(rows),
        "winners": sum(len(row["winners"]) for row in rows),
        "alternatives": sum(len(row["alternatives"]) for row in rows),
        "dual_lane_same_winner": sum(1 for row in rows if row["independent_review"] == "dual_lane_same_winner"),
        "dual_lane_adjudicated": sum(1 for row in rows if row["independent_review"] == "dual_lane_adjudicated"),
        "pending_lanes": sum(1 for row in rows if row["independent_review"] == "pending_lanes"),
        "single_lane": sum(1 for row in rows if row["independent_review"] == "single_lane"),
    }

    document = {
        "schema_version": 1,
        "checked_at": CHECKED_AT,
        "scope": SCOPE,
        "rows": rows,
        "summary": {
            "totals": totals,
            "needs_host": needs_host,
            "needs_independent_review": needs_independent_review,
        },
    }
    return document, flip_violations


# ------------------------------------------------------------------------- rendering


def serialize(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def assert_no_private_content(text: str) -> None:
    for description, pattern in PRIVATE_CONTENT:
        if pattern.search(text):
            raise SystemExit(f"component_matrix: generated output contains possible {description}; aborting")


def render_markdown(document: dict) -> str:
    lines = [
        "# Component evidence matrix",
        "",
        f"Generated {document['checked_at']} by `python3 scripts/component_matrix.py --write` from "
        "`catalogs/landscape/component-evidence-matrix.json`. " + document["scope"],
        "",
        "## Totals",
        "",
        "| Metric | Count |",
        "| --- | --- |",
    ]
    totals = document["summary"]["totals"]
    for key in (
        "layers", "winners", "alternatives",
        "dual_lane_same_winner", "dual_lane_adjudicated", "pending_lanes", "single_lane",
    ):
        lines.append(f"| {key} | {totals[key]} |")
    lines += [
        "",
        "## Per-layer",
        "",
        "Each winner shows, for linux-wsl2-x86_64 / macos-arm64, its `e2e_state` and host receipts as "
        "[pass/fail/independently reviewed pass/independently reviewed fail], plus `dissented N` when a "
        "reviewer's latest verdict is disagree or needs_changes. Receipt counts ignore pins; the derived "
        "status in the JSON binds receipts to the winner's current pin.",
        "",
        "| Layer | Independent review | Winners: e2e_state [receipts] (linux-wsl2-x86_64 / macos-arm64) |",
        "| --- | --- | --- |",
    ]

    def platform_cell(entry: dict) -> str:
        counts = entry.get("host_receipts") or {}
        cell = (f"{entry.get('e2e_state', '-')} [{counts.get('pass', 0)}/{counts.get('fail', 0)}/"
                f"{counts.get('independently_reviewed_pass', 0)}/{counts.get('independently_reviewed_fail', 0)}]")
        if counts.get("dissented"):
            cell += f" dissented {counts['dissented']}"
        return cell

    for row in document["rows"]:
        winner_cells = []
        for winner in row["winners"]:
            linux_cell = platform_cell(winner["platforms"].get("linux-wsl2-x86_64", {}))
            macos_cell = platform_cell(winner["platforms"].get("macos-arm64", {}))
            winner_cells.append(f"{winner['component_id']} ({linux_cell} / {macos_cell})")
        adjudication = f" (adjudication: `{row['adjudication_ref']}`)" if row["adjudication_ref"] else ""
        lines.append(
            f"| `{row['catalog']}/{row['layer_id']}` | {row['independent_review']}{adjudication} "
            f"| {'; '.join(winner_cells) if winner_cells else '-'} |"
        )
    lines += ["", "## Needs host evidence", "", (
        "Winners whose per-platform `e2e_state` is neither `accepted` nor `host_verified`, grouped by "
        "platform. This is the list other WSL/macOS machines should work through with "
        "[`docs/contributing-evidence.md`](contributing-evidence.md). `macos-arm64` entries stay here "
        "until a Mac records receipts that `scripts/platform_status.py` accepts and the layer rows are "
        "re-recorded."
    ), ""]
    for platform_key in sorted(document["summary"]["needs_host"]):
        entries = document["summary"]["needs_host"][platform_key]
        lines.append(f"### {platform_key}")
        lines.append("")
        if not entries:
            lines.append("None.")
        else:
            for entry in entries:
                lines.append(
                    f"- `{entry['catalog']}/{entry['layer_id']}`: `{entry['component_id']}` "
                    f"(catalog/e2e state: {entry['e2e_state']})"
                )
        lines.append("")
    lines += ["## Needs independent review", "", (
        "Rows whose `independent_review` is `pending_lanes` (a dual-lane disagreement that the "
        "counterbalanced adjudication did not resolve) or `single_lane` (no second lane recorded)."
    ), ""]
    needs_review = document["summary"]["needs_independent_review"]
    if not needs_review:
        lines.append("None.")
    else:
        for entry in needs_review:
            lines.append(f"- `{entry['catalog']}/{entry['layer_id']}`: {entry['independent_review']}")
    lines += [
        "",
        "## How to update this page",
        "",
        "This page and `catalogs/landscape/component-evidence-matrix.json` are generated, not hand-edited. "
        "After adding host receipts, a decision, a gap-crosswalk regeneration or a landscape verdict update, "
        "run `python3 scripts/component_matrix.py --write` and commit both files. "
        "`python3 scripts/component_matrix.py --check` (run in CI) recomputes both outputs and also enforces "
        "the flip rule, which `scripts/landscape.py` enforces too through the same function "
        "(`scripts/platform_status.py`): a declared `macos-arm64` `platform_status` may not claim more than "
        "the recorded evidence supports. `accepted` needs a host receipt for that platform at stage `use` or "
        "`install` that is `result: pass` and `evidence_class: native_proven`, records the winner's current "
        "pin in `tool_versions`, declares `host.second_physical_machine: true`, has `host.os`/"
        "`host.architecture` consistent with `adoption/manifest.json`'s `platform_profiles[]` entry, and "
        "carries an `agree` review from a reviewer identity other than the recorder's with no standing "
        "`disagree`/`needs_changes` review; a later such receipt that fails supersedes it. `conditional` needs "
        "any pin-bound passing receipt. Never edit `platform_status` in the landscape files to make this page "
        "pass; add the underlying host receipt instead, following "
        "[`docs/contributing-evidence.md`](contributing-evidence.md).",
        "",
    ]
    return "\n".join(lines)


# -------------------------------------------------------------------------------- main


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write", action="store_true", help="Write the generated outputs.")
    parser.add_argument("--check", action="store_true",
                         help="Recompute and compare against the checked-in outputs (default).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    write_mode = bool(args.write) and not args.check

    document, flip_violations = build_document(root)
    json_text = serialize(document)
    md_text = render_markdown(document)
    assert_no_private_content(json_text)
    assert_no_private_content(md_text)

    json_path = root / OUTPUT_JSON
    md_path = root / OUTPUT_MD

    if write_mode:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")
        # Keep manifests/evidence.json's registered hashes for these two generated
        # outputs current: otherwise any contributor who adds a receipt/review and
        # reruns --write leaves scripts/validate.py reporting a stale hash for them.
        host_receipts.register_file(root, OUTPUT_JSON)
        host_receipts.register_file(root, OUTPUT_MD)
        print(json.dumps({
            "status": "written", "rows": len(document["rows"]),
            "flip_rule_violations": len(flip_violations),
        }, sort_keys=True))
        return 0

    ok = True
    if not json_path.exists() or json_path.read_text(encoding="utf-8") != json_text:
        print(f"component-evidence-matrix JSON differs from the generated output: {json_path}")
        ok = False
    if not md_path.exists() or md_path.read_text(encoding="utf-8") != md_text:
        print(f"component-evidence-matrix markdown differs from the generated output: {md_path}")
        ok = False
    if flip_violations:
        print(f"flip-rule violation(s) ({len(flip_violations)}):")
        for violation in flip_violations:
            print(f"- {violation}")
        ok = False

    if not ok:
        return 1
    print(json.dumps({"status": "checked", "rows": len(document["rows"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
