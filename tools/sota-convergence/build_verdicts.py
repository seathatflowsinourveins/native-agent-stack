#!/usr/bin/env python3
"""Join the landscape ledger's layer-verdict schema v2 rows with the dated
SOTA-convergence manifest and adoption/manifest.json's recipe_map, and write
the result deterministically to
``catalogs/sota-convergence/layer-verdicts-20260922.json``; also refresh the
generated per-layer verdict tables between the ``<!-- verdicts:begin -->`` /
``<!-- verdicts:end -->`` markers in ``docs/grand-catalog-handbook.md`` (added
at the end of the file, under a "## Per-layer verdicts (generated)" heading,
if the markers are not already present).

No network access; every input is a repository-relative file already checked
into ``catalogs/`` and ``adoption/``. This generator never selects a winner,
runs a lane or claims an execution result -- it only republishes whatever the
ledger rows and the sota manifest already record, in a fixed deterministic
shape (``json.dumps(..., sort_keys=True)``).

Modes: ``--check`` (default) recomputes both outputs in memory and exits 1 on
any difference from what is currently checked in; ``--write`` recomputes and
writes them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
# assert_no_leak/sanitize_value are reused (not reimplemented) from
# build_manifest.py, which owns the host-path/secret-marker leak contract for
# every generator under tools/sota-convergence/.
from build_manifest import assert_no_leak, sanitize_value  # noqa: E402

MARKER_BEGIN = "<!-- verdicts:begin -->"
MARKER_END = "<!-- verdicts:end -->"
HANDBOOK_HEADING = "## Per-layer verdicts (generated)"

LEDGER_FILES = {
    "foundation": "catalogs/landscape/foundation.json",
    "us-equities": "catalogs/landscape/us-equities.json",
}
STATUS_ORDER = ("pending_lanes", "recorded", "no_selection")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sota_layer_index(sota_doc: dict) -> dict:
    """layer_id -> [{id, pin, upstream, review_status, pin_behind_upstream}, ...],
    joined from the sota manifest's foundation[].components and
    trading[].entries -- the only fields this generator republishes from
    there, per the task's join contract."""
    index = {}
    for row in sota_doc.get("foundation", []):
        index[row["layer"]] = [
            {"id": component["id"], "pin": component.get("pin"), "upstream": component.get("upstream"),
             "review_status": component.get("review_status"),
             "pin_behind_upstream": component.get("pin_behind_upstream")}
            for component in row.get("components", [])
        ]
    for row in sota_doc.get("trading", []):
        index[row["layer"]] = [
            {"id": entry["id"], "pin": entry.get("pin"), "upstream": entry.get("upstream"),
             "review_status": entry.get("review_status"),
             "pin_behind_upstream": entry.get("pin_behind_upstream")}
            for entry in row.get("entries", [])
        ]
    return index


def platform_status_summary(winners: list) -> dict:
    summary: dict = {}
    for winner in winners:
        for platform, status in (winner.get("platform_status") or {}).items():
            summary.setdefault(platform, []).append(status)
    return summary


def build_verdict_row(row: dict, sota_components: list) -> dict:
    winners = row.get("winners") or []
    alternatives = row.get("alternatives") or []
    recipe_refs = sorted({winner["recipe_ref"] for winner in winners if winner.get("recipe_ref")})
    return {
        "layer_id": row["layer_id"],
        "title": row.get("title"),
        "group": row.get("group"),
        "verdict_status": row.get("verdict_status"),
        "winners": [
            {"component_id": winner.get("component_id"), "repository": winner.get("repository"),
             "pin": winner.get("pin"), "evidence_class": winner.get("evidence_class"),
             "why_selected": winner.get("why_selected"), "recipe_ref": winner.get("recipe_ref"),
             "platform_status": winner.get("platform_status")}
            for winner in winners
        ],
        "alternatives": [
            {"name": alt.get("name"), "repository": alt.get("repository"),
             "disposition": alt.get("disposition"), "why_not_default": alt.get("why_not_default"),
             "evidence_class": alt.get("evidence_class"), "source": alt.get("source")}
            for alt in alternatives
        ],
        "overturn_when": row.get("overturn_when"),
        "verdict_overturn_when": row.get("verdict_overturn_when") or "",
        "overturn_protocol": row.get("overturn_protocol"),
        "lanes": row.get("lanes"),
        "open_gaps": row.get("open_gaps") or [],
        "recipe_refs": recipe_refs,
        "platform_status_summary": platform_status_summary(winners),
        "sota_components": sota_components,
        "checked_at": row.get("checked_at"),
    }


def build_document(root: Path, checked_at: str) -> dict:
    sota_doc = load_json(root / "catalogs/sota-convergence/manifest-20260922.json")
    sota_index = sota_layer_index(sota_doc)
    # adoption/manifest.json's recipe_map is joined implicitly: a winner's own
    # recipe_ref is already validated (scripts/landscape.py) to resolve there
    # or to an existing path; this generator republishes the ref as-is rather
    # than re-deriving membership, so a stale ref surfaces as a landscape.py
    # failure, not a silently different verdict document.
    load_json(root / "adoption/manifest.json")

    catalogs, counts = {}, {}
    for catalog, relative in LEDGER_FILES.items():
        ledger = load_json(root / relative)
        rows = [build_verdict_row(row, sota_index.get(row["layer_id"], [])) for row in ledger.get("layers", [])]
        rows.sort(key=lambda item: item["layer_id"])
        catalogs[catalog] = rows
        counts[catalog] = {
            "layers": len(rows),
            "by_status": {status: sum(1 for r in rows if r["verdict_status"] == status) for status in STATUS_ORDER},
        }

    return {
        "schema_version": 1,
        "id": "layer-verdicts-20260922",
        "checked_at": checked_at,
        "generated_by": "tools/sota-convergence/build_verdicts.py",
        "scope": "Joins the landscape ledger's layer-verdict schema v2 rows with the dated SOTA-convergence "
                 "manifest's per-layer components/entries and adoption/manifest.json's recipe_map. Rows are "
                 "rendered as the ledger records them (recorded rows from the record tool, pending_lanes rows "
                 "unchanged); this generator does not itself run a lane, select a winner or claim an "
                 "execution result.",
        "catalogs": catalogs,
        "counts": counts,
    }


def serialize(document: dict) -> str:
    text = json.dumps(sanitize_value(document), indent=1, sort_keys=True)
    json.loads(text)  # prove the sanitized result is still valid JSON before the leak check
    assert_no_leak(text)
    return text + "\n"


def truncate(text, limit=120) -> str:
    text = text or "-"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def winner_summary(row: dict) -> str:
    if not row["winners"]:
        return "-"
    return "; ".join(f"{w.get('component_id') or '?'} @ {w.get('pin') or '?'}" for w in row["winners"])


def evidence_class_summary(row: dict) -> str:
    classes = sorted({w.get("evidence_class") for w in row["winners"] if w.get("evidence_class")})
    return ", ".join(classes) if classes else "-"


def platform_summary(row: dict) -> str:
    parts = [f"{platform}: {','.join(sorted(set(statuses)))}"
             for platform, statuses in sorted(row["platform_status_summary"].items())]
    return "; ".join(parts) if parts else "-"


def recipe_anchor(row: dict) -> str:
    return ", ".join(row["recipe_refs"]) if row["recipe_refs"] else "-"


def render_table(catalog: str, rows: list) -> str:
    header = ["Layer", "Group", "Verdict status", "Winner(s) + pin", "Evidence class",
              "Alternatives", "Overturn when", "Recipe anchor", "Platform status"]
    lines = [f"### {catalog}", "", "| " + " | ".join(header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        # A pending row (no lane has run yet) renders as "pending", not the
        # internal "pending_lanes" verdict_status string.
        status = "pending" if row["verdict_status"] == "pending_lanes" else row["verdict_status"]
        lines.append("| " + " | ".join([
            row["layer_id"], row.get("group") or "-", status, winner_summary(row),
            evidence_class_summary(row), str(len(row["alternatives"])),
            truncate(row.get("verdict_overturn_when") or row.get("overturn_when")), recipe_anchor(row),
            platform_summary(row),
        ]) + " |")
    return "\n".join(lines)


def render_winner_line(winner: dict) -> str:
    return f"- {winner.get('component_id') or '?'} @ {winner.get('pin') or '?'} — {winner.get('why_selected') or '-'}"


def render_alternative_line(alternative: dict) -> str:
    return (f"- {alternative.get('name') or '?'} ({alternative.get('disposition') or '?'}) — "
            f"{alternative.get('why_not_default') or '-'}")


def render_lanes_line(row: dict) -> str:
    lanes = row.get("lanes") or {}
    agreement = lanes.get("agreement") or "-"
    claude_run = (lanes.get("claude") or {}).get("run_id") or "-"
    codex_run = (lanes.get("codex") or {}).get("run_id") or "-"
    return f"Lanes: {agreement} (claude: {claude_run}; codex: {codex_run})"


def render_row_narrative(row: dict) -> str:
    """A ``recorded`` row gets a full ``#### <title> (<layer_id>)`` block
    (winner(s), alternatives, the full untruncated ``overturn_when``, open
    gaps, lane agreement + both run ids); every other row (``pending_lanes``
    or ``no_selection``) renders as a single "pending -- ..." bullet line,
    since there is nothing yet to narrate beyond why it is still open."""
    if row["verdict_status"] != "recorded":
        gaps = "; ".join(row.get("open_gaps") or []) or "no lane has run"
        label = "no selection" if row["verdict_status"] == "no_selection" else "pending"
        return f"- **{row.get('title') or row['layer_id']}** ({row['layer_id']}): {label} — {gaps}"
    lines = [f"#### {row.get('title') or row['layer_id']} ({row['layer_id']})", ""]
    lines.extend(render_winner_line(winner) for winner in row["winners"])
    lines.append("")
    lines.append("Alternatives:")
    if row["alternatives"]:
        lines.extend(render_alternative_line(alt) for alt in row["alternatives"])
    else:
        lines.append("- none")
    lines.append("")
    lines.append(f"Overturn when: {row.get('verdict_overturn_when') or row.get('overturn_when') or '-'}")
    lines.append("")
    lines.append("Open gaps:")
    gaps = row.get("open_gaps") or []
    if gaps:
        lines.extend(f"- {gap}" for gap in gaps)
    else:
        lines.append("- none")
    lines.append("")
    lines.append(render_lanes_line(row))
    return "\n".join(lines)


def render_narrative(catalog: str, rows: list) -> str:
    # "###" (one level above each row's own "#### <title> (<layer_id>)"
    # block, and distinct from render_table's own "### {catalog}" table
    # heading) so this section heading actually nests above its rows in the
    # rendered Markdown outline instead of sitting at the same level as them.
    parts = [f"### {catalog} (per-layer narrative)", ""]
    for row in rows:
        parts.append(render_row_narrative(row))
        parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


def render_handbook_section(document: dict) -> str:
    parts = [HANDBOOK_HEADING, "", document["scope"], ""]
    for catalog in ("foundation", "us-equities"):
        parts.append(render_table(catalog, document["catalogs"][catalog]))
        parts.append("")
        parts.append(render_narrative(catalog, document["catalogs"][catalog]))
        parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


def update_handbook(text: str, section: str) -> str:
    # ``block`` deliberately carries no trailing newline of its own -- the
    # single newline that follows MARKER_END is supplied once, either by the
    # untouched ``post`` remainder (markers already present) or by the
    # appended "\n" below (markers added for the first time). Folding that
    # newline into ``block`` itself would double on every subsequent run,
    # since ``post`` already contains the newline the previous run left
    # behind (non-idempotent output --check would then never converge).
    block = f"{MARKER_BEGIN}\n{section}{MARKER_END}"
    if MARKER_BEGIN in text and MARKER_END in text:
        pre = text.split(MARKER_BEGIN, 1)[0]
        post = text.split(MARKER_END, 1)[1]
        return pre + block + post
    if not text.endswith("\n"):
        text += "\n"
    if not text.endswith("\n\n"):
        text += "\n"
    return text + block + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=HERE.parent.parent)
    parser.add_argument("--write", action="store_true", help="Write the generated outputs.")
    parser.add_argument("--check", action="store_true",
                         help="Recompute and compare against the checked-in outputs (default).")
    parser.add_argument("--checked-at", default="2026-09-22")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    write_mode = bool(args.write) and not args.check

    document = build_document(root, args.checked_at)
    # Sanitize once and render both outputs from the sanitized copy: the
    # handbook markdown table is built directly from field values (e.g.
    # overturn_when), so it needs the same host-path/secret-marker redaction
    # as the JSON document, not just a leak check on its own text.
    sanitized_document = sanitize_value(document)
    json_text = serialize(sanitized_document)
    handbook_path = root / "docs/grand-catalog-handbook.md"
    handbook_text = handbook_path.read_text(encoding="utf-8")
    new_handbook_text = update_handbook(handbook_text, render_handbook_section(sanitized_document))
    assert_no_leak(new_handbook_text)

    out_path = root / "catalogs/sota-convergence/layer-verdicts-20260922.json"

    if write_mode:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_text, encoding="utf-8")
        handbook_path.write_text(new_handbook_text, encoding="utf-8")
        print(json.dumps({"status": "written", "counts": document["counts"]}))
        return 0

    ok = True
    if not out_path.exists() or out_path.read_text(encoding="utf-8") != json_text:
        print(f"layer-verdicts JSON differs from the generated output: {out_path}")
        ok = False
    if handbook_text != new_handbook_text:
        print("docs/grand-catalog-handbook.md generated verdicts section differs from the generated output")
        ok = False
    if not ok:
        return 1
    print(json.dumps({"status": "checked", "counts": document["counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
