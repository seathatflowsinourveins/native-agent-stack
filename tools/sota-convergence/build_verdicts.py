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

Waves (2026-09-23 peer audit). Every dated wave's
``catalogs/sota-convergence/layer-verdicts-<run-id>.json`` is registered by
sha256 in ``catalogs/sota-convergence/layer-verdict-waves.json``. A row names
its wave through ``lanes.sealed_base`` (absent means the 2026-09-22 wave). The
current wave is the newest run id (lexicographic; dated ``YYYYMMDD`` ids sort
chronologically) present in the rows or the registry; every older wave is frozen.

Modes: ``--check`` (default) verifies every registered wave document (a) byte
for byte against its registered sha256 and (b) against the current rows whose
``lanes.sealed_base`` names that wave, and fails when a row names a wave with
no registered document. It regenerates only the current wave's document and
the handbook's generated block from the current rows. ``--check --run-id X``
verifies wave X alone. ``--write`` regenerates the current wave (or
``--run-id X`` when X is not older than the current wave), writes the handbook
block and registers the new sha256; it refuses to rewrite a frozen wave.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
# assert_no_leak/sanitize_value are reused (not reimplemented) from
# build_manifest.py, which owns the host-path/secret-marker leak contract for
# every generator under tools/sota-convergence/.
from build_manifest import assert_no_leak, sanitize_value  # noqa: E402

if str(HERE.parent.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent.parent))
# The grandfathered run ids are defined once, next to the rules they exempt (scripts/landscape.py).
from scripts.landscape import GRANDFATHERED_RUN_IDS  # noqa: E402

# Same character class scripts/landscape.py requires of lanes.<lane>.sealed_base
# (re.fullmatch(r"evidence/artifacts/layer-verdicts-[0-9A-Za-z]+", ...)) and
# record_verdicts.RUN_ID_PATTERN enforces on its own --run-id -- kept here as an
# equivalent, separately-defined check rather than an import, since
# record_verdicts.py already imports LEDGER_FILES from this module and an import
# the other way would be circular.
RUN_ID_PATTERN = re.compile(r"[0-9A-Za-z]+")


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise SystemExit(f"--run-id must match {RUN_ID_PATTERN.pattern!r} (got {run_id!r})")
    return run_id

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


DEFAULT_RUN_ID = "20260922"
WAVE_REGISTRY = "catalogs/sota-convergence/layer-verdict-waves.json"
SEALED_BASE_PREFIX = "evidence/artifacts/layer-verdicts-"
DEFAULT_CHECKED_AT = "2026-09-22"


def default_manifest(run_id: str) -> str:
    return f"catalogs/sota-convergence/manifest-{run_id}.json"


def default_out(run_id: str) -> str:
    return f"catalogs/sota-convergence/layer-verdicts-{run_id}.json"


def row_run_id(row: dict) -> str:
    """The wave a ledger row belongs to: the run id of its ``lanes.sealed_base``, or the
    2026-09-22 wave when the row carries none (scripts/landscape.py uses the same fallback)."""
    sealed_base = (row.get("lanes") or {}).get("sealed_base") or SEALED_BASE_PREFIX + DEFAULT_RUN_ID
    if not isinstance(sealed_base, str) or not sealed_base.startswith(SEALED_BASE_PREFIX):
        raise SystemExit(f"{row.get('catalog')}/{row.get('layer_id')}: malformed lanes.sealed_base {sealed_base!r}")
    return validate_run_id(sealed_base[len(SEALED_BASE_PREFIX):])


def ledger_rows(root: Path) -> list:
    """[(catalog, row), ...] in ledger order for both catalogs."""
    return [(catalog, row) for catalog, relative in LEDGER_FILES.items()
            for row in load_json(root / relative).get("layers", [])]


def load_registry(root: Path) -> dict:
    """run_id -> {run_id, path, manifest, checked_at, sha256}; empty when no wave is registered yet."""
    path = root / WAVE_REGISTRY
    if not path.is_file():
        return {}
    document = load_json(path)
    waves = {}
    for wave in document.get("waves", []):
        run_id = validate_run_id(wave["run_id"])
        if run_id in waves:
            raise SystemExit(f"{WAVE_REGISTRY}: duplicate wave {run_id}")
        if not re.fullmatch(r"[a-f0-9]{64}", wave.get("sha256") or ""):
            raise SystemExit(f"{WAVE_REGISTRY}: wave {run_id} needs a lowercase sha256")
        waves[run_id] = wave
    return waves


def registry_text(waves: dict) -> str:
    document = {
        "schema_version": 1,
        "generated_by": "tools/sota-convergence/build_verdicts.py",
        "scope": "One entry per layer-verdict wave document. Every wave older than the newest is frozen: "
                 "build_verdicts.py --check verifies it byte for byte against this sha256 and against the "
                 "ledger rows whose lanes.sealed_base names it, and --write refuses to rewrite it.",
        "waves": [waves[run_id] for run_id in sorted(waves)],
    }
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    assert_no_leak(text)
    return text


def default_checked_at(run_id: str) -> str:
    """A dated run id (YYYYMMDD) names its own checked_at; anything else keeps the 2026-09-22 default."""
    if re.fullmatch(r"[0-9]{8}", run_id):
        try:
            return date(int(run_id[:4]), int(run_id[4:6]), int(run_id[6:])).isoformat()
        except ValueError:
            pass
    return DEFAULT_CHECKED_AT


def normalized(value):
    """The JSON value a serialized document holds for ``value`` (sanitized, key order free)."""
    return json.loads(json.dumps(sanitize_value(value), sort_keys=True))


def same_json(left, right) -> bool:
    """Type-strict equality of two JSON values: Python's ``==`` treats 1, 1.0 and True as equal, so a
    type-only rewrite of a number or boolean in a frozen row would otherwise pass (the #135 gate compares
    frozen documents the same way)."""
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def build_document(root: Path, checked_at: str, *, run_id: str = DEFAULT_RUN_ID, manifest: str = None) -> dict:
    sota_doc = load_json(root / (manifest or default_manifest(run_id)))
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
        "id": f"layer-verdicts-{run_id}",
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
                         help="Verify every registered wave and regenerate the current one (default).")
    parser.add_argument("--checked-at", default=None,
                        help="checked_at of a newly written wave (default: the registered value, else the "
                             "date a YYYYMMDD run id names, else 2026-09-22).")
    parser.add_argument("--run-id", default=None,
                        help="Wave to write or check (default: --write the current wave; --check every wave). "
                             "Joined into the id field, the default --manifest "
                             "(catalogs/sota-convergence/manifest-<run-id>.json) and the default --out "
                             "(catalogs/sota-convergence/layer-verdicts-<run-id>.json).")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Override the dated sota manifest this joins (default: the registered one, else "
                             "derived from --run-id).")
    parser.add_argument("--out", type=Path, default=None,
                        help="Override the output layer-verdicts catalog path (default: the registered one, "
                             "else derived from --run-id).")
    return parser.parse_args(argv)


def relative_path(root: Path, value) -> str:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def render_outputs(root: Path, run_id: str, checked_at: str, manifest: str):
    """(document, json_text, current handbook text, regenerated handbook text) for one wave."""
    document = build_document(root, checked_at, run_id=run_id, manifest=manifest)
    # Sanitize once and render both outputs from the sanitized copy: the
    # handbook markdown table is built directly from field values (e.g.
    # overturn_when), so it needs the same host-path/secret-marker redaction
    # as the JSON document, not just a leak check on its own text.
    sanitized_document = sanitize_value(document)
    json_text = serialize(sanitized_document)
    handbook_text = (root / "docs/grand-catalog-handbook.md").read_text(encoding="utf-8")
    new_handbook_text = update_handbook(handbook_text, render_handbook_section(sanitized_document))
    assert_no_leak(new_handbook_text)
    return document, json_text, handbook_text, new_handbook_text


def check_frozen_rows(root: Path, run_id: str, wave: dict, rows: list, text: str) -> list:
    """(b): every current row naming ``run_id`` must equal its entry in the wave document."""
    problems = []
    try:
        document = json.loads(text)
    except ValueError as error:
        return [f"layer-verdicts wave {run_id} is not valid JSON: {error}"]
    published = {(catalog, entry.get("layer_id")): entry
                 for catalog, entries in (document.get("catalogs") or {}).items() for entry in entries}
    sota_index = sota_layer_index(load_json(root / (wave.get("manifest") or default_manifest(run_id))))
    for catalog, row in rows:
        if row_run_id(row) != run_id:
            continue
        entry = published.get((catalog, row["layer_id"]))
        if entry is None:
            problems.append(f"{catalog}/{row['layer_id']} names wave {run_id} but is absent from {wave['path']}")
        elif not same_json(normalized(build_verdict_row(row, sota_index.get(row["layer_id"], []))), entry):
            problems.append(f"{catalog}/{row['layer_id']} names wave {run_id} but differs from its frozen "
                            f"entry in {wave['path']} (re-record it under a new --run-id instead)")
    return problems


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    write_mode = bool(args.write) and not args.check
    requested = validate_run_id(args.run_id) if args.run_id is not None else None
    registry = load_registry(root)
    rows = ledger_rows(root)
    row_runs = {row_run_id(row) for _, row in rows}
    known = row_runs | set(registry)
    current = max(known) if known else DEFAULT_RUN_ID

    if write_mode:
        run_id = requested or current
        if run_id in GRANDFATHERED_RUN_IDS and run_id in registry:
            # Frozen whether or not a later wave exists yet: a grandfathered wave predates the
            # integrity rules, so its registered document is never regenerated or re-registered.
            raise SystemExit(f"layer-verdicts wave {run_id} is grandfathered and already registered in "
                             f"{WAVE_REGISTRY}; it is never rewritten -- record changed rows under a new --run-id")
        if run_id < current:
            raise SystemExit(f"layer-verdicts wave {run_id} is frozen (the current wave is {current}); "
                             "re-record changed rows under a new --run-id instead of rewriting it")
        wave = dict(registry.get(run_id) or {})
        manifest = relative_path(root, args.manifest) or wave.get("manifest") or default_manifest(run_id)
        out = relative_path(root, args.out) or wave.get("path") or default_out(run_id)
        checked_at = args.checked_at or wave.get("checked_at") or default_checked_at(run_id)
        document, json_text, _handbook, new_handbook_text = render_outputs(root, run_id, checked_at, manifest)
        out_path = root / out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_text, encoding="utf-8")
        (root / "docs/grand-catalog-handbook.md").write_text(new_handbook_text, encoding="utf-8")
        registry[run_id] = {"run_id": run_id, "path": out, "manifest": manifest, "checked_at": checked_at,
                            "sha256": hashlib.sha256(json_text.encode("utf-8")).hexdigest()}
        registry_path = root / WAVE_REGISTRY
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(registry_text(registry), encoding="utf-8")
        print(json.dumps({"status": "written", "run_id": run_id, "counts": document["counts"]}))
        return 0

    problems = []
    waves = [requested] if requested else sorted(known)
    counts = None
    for run_id in waves:
        wave = registry.get(run_id)
        if wave is None:
            problems.append(f"layer-verdicts wave {run_id} is named by ledger rows but has no registered "
                            f"document in {WAVE_REGISTRY} (run build_verdicts.py --write --run-id {run_id})")
            continue
        path = root / (relative_path(root, args.out) if args.out and requested else wave["path"])
        if not path.is_file():
            problems.append(f"layer-verdicts JSON differs from the generated output: {path} is missing")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != wave["sha256"]:
            problems.append(f"layer-verdicts wave {run_id} ({wave['path']}) differs from its registered sha256")
        text = data.decode("utf-8")
        problems.extend(check_frozen_rows(root, run_id, wave, rows, text))
        if run_id == current:
            manifest = relative_path(root, args.manifest) or wave.get("manifest") or default_manifest(run_id)
            checked_at = args.checked_at or wave.get("checked_at") or default_checked_at(run_id)
            document, json_text, handbook_text, new_handbook_text = render_outputs(root, run_id, checked_at,
                                                                                   manifest)
            counts = document["counts"]
            if text != json_text:
                problems.append(f"layer-verdicts JSON differs from the generated output: {path}")
            if handbook_text != new_handbook_text:
                problems.append("docs/grand-catalog-handbook.md generated verdicts section differs from the "
                                "generated output")
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(json.dumps({"status": "checked", "waves": waves, "current": current, "counts": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
