#!/usr/bin/env python3
"""Merge the working files, GitHub freshness, and a review-lanes record into a
dated SOTA-convergence manifest with the exact key layout of
``catalogs/sota-convergence/manifest-20260922.json``.

No network access. All host-path fragments are removed from the serialized
output before it is written; the writer refuses to write if a leak survives
sanitization (see ``sanitize`` / ``assert_no_leak``).

Baseline (pins vs. upstream) is computed here, directly from
``foundation-layers.json``, ``trading-by-layer.json`` and the freshness
snapshot -- there is no separate baseline file to keep in sync. Foundation
components are used as-is (``manifests/stack.json`` already lists only
in-use components). Trading entries are filtered to ``decision`` in
``{default, conditional}`` -- the catalog's current selected baseline;
``alternative``/``watch``/``excluded`` entries stay in trading-by-layer.json
for discovery but are only promoted into a manifest row through the lane
candidate/alternative mechanism, never by catalog membership alone.

Pin-vs-upstream rule: a component/entry counts as ``pin_behind_upstream``
only when its repository is a GitHub URL, its pin is not a ``.devN``
commit-tracking pin (e.g. ``2.0.0.dev0 @ c6fbd1c...`` or
``2.0.0.dev0 (c6fbd1c)``), and its parsed leading version is lower than
GitHub's latest release/tag. Non-GitHub repositories (including bare
OS-package pins such as systemd) and ``.devN`` commit-pinned components are
excluded from the comparison rather than silently counted as "behind" or
"not behind" -- see ``classify_pin``. A version merely *annotated* with a
commit fingerprint (e.g. ``0.25.0 (702f4814...)``) is still compared
normally: the fingerprint documents provenance, it does not make the
release incomparable.

Disposition rule: a lane proposes a label; two adversarial refuters try to
break the proposal. A surviving ``not_adopted`` stays not adopted --
survival never upgrades a label. See ``disposition``.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

GITHUB_RE = re.compile(r"^https?://github\.com/")
# A ".devN" pin (optionally annotated with "@ <commit>" or "(<commit>)") tracks a
# working commit, not a tagged release; its numeric prefix is not comparable to
# GitHub's latest release/tag. A version number merely *annotated* with a commit
# fingerprint (e.g. "0.25.0 (702f4814...)") is still a real, comparable release.
DEV_PIN_RE = re.compile(r"\.dev\d*\b", re.IGNORECASE)
VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


class LeakDetected(ValueError):
    """A sanitized manifest still contains a host path or a known secret prefix."""


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pin-vs-upstream
# ---------------------------------------------------------------------------

def parse_version(text):
    if not text:
        return None
    match = VERSION_RE.search(text)
    if not match:
        return None
    return tuple(int(g) if g else 0 for g in match.groups())


def classify_pin(pin, repository, upstream_latest):
    """Return {"behind": bool, "excluded": bool, "reason": str|None}."""
    if not repository or not GITHUB_RE.match(repository):
        return {"behind": False, "excluded": True, "reason": "non_github_or_os_package"}
    if pin and DEV_PIN_RE.search(pin):
        return {"behind": False, "excluded": True, "reason": "commit_pinned"}
    pin_version = parse_version(pin)
    upstream_version = parse_version(upstream_latest)
    if pin_version is None or upstream_version is None:
        return {"behind": False, "excluded": False, "reason": "unversioned"}
    return {"behind": pin_version < upstream_version, "excluded": False, "reason": None}


def compute_upstream(repository, repositories: dict) -> dict:
    record = (repositories or {}).get(repository) or {}
    release = record.get("latest_release") or {}
    return {
        "latest": release.get("tag") or record.get("latest_tag"),
        "released_at": (release.get("published_at") or "")[:10] or None,
        "prerelease": release.get("prerelease"),
        "pushed_at": (record.get("pushed_at") or "")[:10] or None,
        "stars": record.get("stargazers_count"),
        "license": record.get("license"),
        "archived": record.get("archived"),
        "renamed_to": record.get("renamed_to"),
    }


# ---------------------------------------------------------------------------
# Baseline: foundation-layers.json + trading-by-layer.json + freshness
# ---------------------------------------------------------------------------

def build_baseline_foundation(foundation_layers: dict, repositories: dict) -> list:
    rows = []
    for layer in foundation_layers.get("layers", []):
        components = []
        for component in layer.get("components", []):
            repository = component.get("repository")
            pin = component.get("version") or component.get("pin")
            upstream = compute_upstream(repository, repositories)
            classification = classify_pin(pin, repository, upstream.get("latest"))
            components.append({
                "id": component["id"], "repository": repository, "pin": pin,
                "upstream": upstream, "behind": classification["behind"],
                "excluded": classification["excluded"], "exclusion_reason": classification["reason"],
            })
        rows.append({"layer": layer["layer_id"], "title": layer.get("title", layer["layer_id"]),
                      "components": components})
    return rows


SELECTED_TRADING_DECISIONS = ("default", "conditional")


def build_baseline_trading(trading_by_layer: dict, repositories: dict) -> list:
    """Only 'default' and 'conditional' catalog decisions are the current
    selected baseline; 'alternative', 'watch' and 'excluded' entries stay
    discoverable in trading-by-layer.json but are not promoted into the
    manifest's rows -- a newcomer earns a place only through the lane
    candidate/alternative mechanism, never by being catalogued."""
    rows = []
    for layer_id in sorted(trading_by_layer.get("layers", {})):
        entries = []
        for entry in trading_by_layer["layers"][layer_id]:
            if entry.get("decision") not in SELECTED_TRADING_DECISIONS:
                continue
            repository = entry.get("repository")
            pin = entry.get("version_or_commit") or entry.get("pin")
            upstream = compute_upstream(repository, repositories)
            classification = classify_pin(pin, repository, upstream.get("latest"))
            entries.append({
                "id": entry["id"], "repository": repository, "decision": entry.get("decision"),
                "pin": pin, "upstream": upstream, "behind": classification["behind"],
                "excluded": classification["excluded"], "exclusion_reason": classification["reason"],
            })
        rows.append({"layer": layer_id, "entries": entries})
    return rows


# ---------------------------------------------------------------------------
# Disposition and sanitization
# ---------------------------------------------------------------------------

def disposition(label, survives):
    """The lane proposes a label; two refuters try to break the proposal. A
    surviving not_adopted stays not adopted - survival never upgrades a label."""
    if survives is None:
        return f"{label}_unverified"
    if not survives:
        return "refuted_" + (label or "unlabelled")
    return {
        "not_adopted": "not_adopted_confirmed",
        "keep_but_compare": "keep_but_compare",
        "targeted_candidate": "targeted_candidate",
    }.get(label, label or "unlabelled")


HOST_PATH_RE = re.compile(r"/home/[^\s\"']+")
LEAK_MARKERS = ("/home/", "APCA")


def sanitize(text: str) -> str:
    return HOST_PATH_RE.sub("<host-path>", text)


def assert_no_leak(text: str) -> None:
    for marker in LEAK_MARKERS:
        if marker in text:
            raise LeakDetected(f"sanitized manifest still contains {marker!r}")


# ---------------------------------------------------------------------------
# Lane merge
# ---------------------------------------------------------------------------

def merge_lanes(lanes_doc: dict, repositories: dict):
    """Returns (status, notes, alts, cands, gaps, calls, limits) indexed as in
    the original prototype: status/notes by (layer, repository), the rest by layer."""
    status = {}
    notes = defaultdict(list)
    alts = defaultdict(list)
    cands = defaultdict(list)
    gaps = defaultdict(list)
    calls = {}
    limits = {}
    for lane in lanes_doc.get("lanes", []):
        result = lane["result"]
        calls[lane["lane"]] = result.get("calls")
        limits[lane["lane"]] = result.get("limits")
        verdicts = {(p["layer"], p["repository"], p["kind"]): p for p in lane.get("proposals", [])}
        for layer in result.get("layers", []):
            layer_id = layer["layer_id"]
            for selected in layer.get("selected", []):
                key = (layer_id, selected["repository"])
                verdict = verdicts.get((layer_id, selected["repository"], selected["status"]))
                status_value = selected["status"]
                if verdict is not None and not verdict["survives"]:
                    status_value = ("confirmed_default" if status_value in ("demotion_proposed", "unmaintained_signal")
                                     else "confirmed_pin")
                    notes[key].append(f"{selected['status']} proposed by {lane['lane']} lane, "
                                       "refuted by adversarial verification")
                status[key] = {"status": status_value, "evidence": selected.get("evidence", []),
                                "note": selected.get("note"), "lane": lane["lane"]}
            for alt in layer.get("alternatives_keep_but_compare", []):
                alts[layer_id].append({**alt, "lane": lane["lane"]})
            for candidate in layer.get("new_candidates", []):
                verdict = verdicts.get((layer_id, candidate["repository"], "new_candidate"))
                survives = verdict["survives"] if verdict else None
                upstream_now = (compute_upstream(candidate["repository"], repositories)
                                 if candidate["repository"] in repositories else candidate.get("upstream_now"))
                votes = [{"lens": i, "refuted": v["refuted"], "confidence": v.get("confidence"),
                          "reasoning": v.get("reasoning", "")[:400]}
                         for i, v in enumerate(verdict["votes"])] if verdict else []
                cands[layer_id].append({
                    "repository": candidate["repository"], "source": candidate.get("source"),
                    "demonstrated_gap": candidate.get("demonstrated_gap"),
                    "proposed_label": candidate.get("proposed_label"),
                    "comparison_that_would_overturn": candidate.get("comparison_that_would_overturn"),
                    "evidence": candidate.get("evidence", []), "upstream_now": upstream_now,
                    "adversarial_verification": {"survives": survives, "votes": votes},
                    "disposition": disposition(candidate.get("proposed_label"), survives),
                    "lane": lane["lane"],
                })
            for gap in layer.get("open_gaps", []):
                gaps[layer_id].append(gap)
    return status, notes, alts, cands, gaps, calls, limits


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------

def build_manifest(*, checked_at, manifest_id, scope, foundation_layers, trading_by_layer,
                    freshness_doc, lanes_doc, reconciliations, taxonomy) -> dict:
    repositories = freshness_doc.get("repositories", {})
    baseline_foundation = build_baseline_foundation(foundation_layers, repositories)
    baseline_trading = build_baseline_trading(trading_by_layer, repositories)
    status, notes, alts, cands, gaps, calls, limits = merge_lanes(lanes_doc, repositories)

    manifest = {
        "schema_version": 1, "id": manifest_id, "checked_at": checked_at, "scope": scope,
        "method": {
            "baseline": "extract_layers.py over catalogs/foundation/{manifest,decisions}.json, "
                        "manifests/stack.json and the catalogs/us-equities layer files, "
                        "consolidated into 12 trading layers (taxonomy below)",
            "freshness": f"authenticated GitHub REST metadata for {freshness_doc.get('count', 0)} "
                         f"repositories fetched {(freshness_doc.get('generated_at') or '')[:19]}Z: "
                         "stars, pushed_at, latest release/tag, head, license, archived, rename",
            "review": "review lanes from a lanes.json record (schema: lanes[].result.layers[], "
                       "lanes[].proposals[]); every proposed change adversarially verified "
                       "(votes[].refuted); one completeness critic",
            "rule": "evidence, not agreement or recency; a newer release is information, "
                    "not a reason to upgrade",
        },
        "taxonomy": taxonomy, "foundation": [], "trading": [],
        "critic": lanes_doc.get("critic"), "lane_calls": calls, "lane_limits": limits,
    }

    for row in baseline_foundation:
        layer_id = row["layer"]
        components = []
        for component in row["components"]:
            lane_status = status.get((layer_id, component["repository"]), {})
            components.append({
                "id": component["id"], "repository": component["repository"], "pin": component["pin"],
                "upstream": component["upstream"], "pin_behind_upstream": component["behind"],
                "review_status": lane_status.get("status", "not_individually_reviewed"),
                "review_note": lane_status.get("note"),
                "evidence": lane_status.get("evidence", []) + notes.get((layer_id, component["repository"]), []),
            })
        manifest["foundation"].append({
            "layer": layer_id, "title": row["title"], "components": components,
            "alternatives_keep_but_compare": alts.get(layer_id, []),
            "candidates": cands.get(layer_id, []),
            "open_gaps": sorted(set(gaps.get(layer_id, []))),
        })

    for row in baseline_trading:
        layer_id = row["layer"]
        entries = []
        for entry in row["entries"]:
            lane_status = status.get((layer_id, entry["repository"]), {})
            entries.append({
                "id": entry["id"], "repository": entry["repository"], "decision": entry["decision"],
                "pin": entry["pin"], "upstream": entry["upstream"], "pin_behind_upstream": entry["behind"],
                "review_status": lane_status.get("status", "not_individually_reviewed"),
                "review_note": lane_status.get("note"),
                "evidence": lane_status.get("evidence", []) + notes.get((layer_id, entry["repository"]), []),
            })
        manifest["trading"].append({
            "layer": layer_id, "entries": entries,
            "alternatives_keep_but_compare": alts.get(layer_id, []),
            "candidates": cands.get(layer_id, []),
            "open_gaps": sorted(set(gaps.get(layer_id, []))),
        })

    known_layers = {row["layer"] for row in manifest["foundation"]} | {row["layer"] for row in manifest["trading"]}
    for layer_id in sorted(set(cands) | set(gaps) | set(alts)):
        if layer_id not in known_layers:
            manifest["trading"].append({
                "layer": layer_id, "entries": [],
                "alternatives_keep_but_compare": alts.get(layer_id, []),
                "candidates": cands.get(layer_id, []),
                "open_gaps": sorted(set(gaps.get(layer_id, []))),
                "note": "layer id named by a review lane outside the baseline taxonomy",
            })

    manifest["reconciliations"] = []
    for item in reconciliations:
        entry = dict(item)
        if entry.get("repository"):
            entry["upstream"] = compute_upstream(entry["repository"], repositories)
        manifest["reconciliations"].append(entry)

    all_rows = manifest["foundation"] + manifest["trading"]

    def all_components(row):
        return row.get("components", row.get("entries", []))

    pins_behind_unique = {
        component["id"] for row in all_rows for component in all_components(row)
        if component["pin_behind_upstream"]
    }
    manifest["counts"] = {
        "foundation_layers": len(manifest["foundation"]),
        "trading_layers": len([r for r in manifest["trading"] if r.get("entries")]),
        "components_confirmed": sum(
            1 for row in all_rows for component in all_components(row)
            if str(component["review_status"]).startswith("confirmed")
        ),
        "pins_behind_upstream": sum(
            1 for row in all_rows for component in all_components(row) if component["pin_behind_upstream"]
        ),
        "candidates_total": sum(len(row["candidates"]) for row in all_rows),
        "pins_behind_upstream_unique_components": len(pins_behind_unique),
        "pins_behind_note": "components with a commit-pinned version (a parenthetical hash) or a "
                             "non-GitHub repository (including OS packages) are excluded from the "
                             "pin-vs-upstream comparison rather than counted either way",
        "candidates_by_disposition": dict(Counter(
            candidate["disposition"] for row in all_rows for candidate in row["candidates"]
        )),
    }
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", type=Path, default=None,
                         help="Directory holding foundation-layers.json, trading-by-layer.json and "
                              "github-freshness.json; used as the default base for those three flags.")
    parser.add_argument("--foundation-layers", type=Path, default=None)
    parser.add_argument("--trading-by-layer", type=Path, default=None)
    parser.add_argument("--freshness", type=Path, default=None)
    parser.add_argument("--lanes", type=Path, required=True)
    parser.add_argument("--reconciliations", type=Path, default=HERE / "reconciliations-20260922.json")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--checked-at", required=True)
    parser.add_argument("--id", dest="manifest_id", required=True)
    parser.add_argument("--scope", default=None)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    work_dir = args.work_dir
    foundation_layers_path = args.foundation_layers or (work_dir / "foundation-layers.json" if work_dir else None)
    trading_by_layer_path = args.trading_by_layer or (work_dir / "trading-by-layer.json" if work_dir else None)
    freshness_path = args.freshness or (work_dir / "github-freshness.json" if work_dir else None)
    if not (foundation_layers_path and trading_by_layer_path and freshness_path):
        raise SystemExit("provide --work-dir, or all of --foundation-layers/--trading-by-layer/--freshness")

    foundation_layers = load_json(foundation_layers_path)
    trading_by_layer = load_json(trading_by_layer_path)
    freshness_doc = load_json(freshness_path)
    lanes_doc = load_json(args.lanes)
    reconciliations = load_json(args.reconciliations).get("reconciliations", [])
    taxonomy = trading_by_layer.get("taxonomy", {})

    scope = args.scope or (
        f"Dated per-layer SOTA repository convergence for the foundation "
        f"({len(foundation_layers.get('layers', []))} layers) and the US-equities trading "
        f"destination ({len(taxonomy)} consolidated layers). Selections are the catalogs' "
        "reviewed defaults confirmed against current upstream metadata; new names are labelled "
        "keep_but_compare or targeted_candidate only, never promoted. Inclusion is not "
        "installation, E2E or superiority."
    )

    manifest = build_manifest(
        checked_at=args.checked_at, manifest_id=args.manifest_id, scope=scope,
        foundation_layers=foundation_layers, trading_by_layer=trading_by_layer,
        freshness_doc=freshness_doc, lanes_doc=lanes_doc, reconciliations=reconciliations,
        taxonomy=taxonomy,
    )

    text = sanitize(json.dumps(manifest, indent=1))
    assert_no_leak(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
