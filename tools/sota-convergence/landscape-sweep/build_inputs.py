#!/usr/bin/env python3
"""Build the per-layer inputs a landscape sweep's workers read (no network, no model calls).

  build_inputs.py --work-dir W --freshness-manifest manifest-YYYYMMDD.json
                  [--scope W/scope.json] [--baseline-manifest catalogs/sota-convergence/manifest-YYYYMMDD.json]
                  [--seeds seeds.json] [--repo-root .]

Reads the frozen scope (`saturation_ledger.py --scope`, default <work-dir>/scope.json), catalogs/landscape/
{foundation,us-equities}.json and research-state.json, the saturation ledger's last completed sweep, a baseline
manifest (default: that sweep's manifest_ref) whose candidates count as known, and a catalog-freshness manifest
(build_manifest.py over extract_layers.py + github_freshness.py output with an empty lanes record, or the
catalog-freshness workflow's artifact) for each winner's pin against upstream. Writes <work-dir>/inputs/<layer_id>.json
and <work-dir>/layers.json ([{catalog, layer_id, title, input}] in catalog order).

--seeds is an optional JSON object {"<layer_id>": ["candidate or note", ...]}: candidates other sessions asked this
sweep to assess, shown to the discovery workers as seeded_candidates. An unknown layer id is an error.

previous_sweep holds that sweep's survived and refuted repositories. A proposal it refuted only because a vote did
not return (saturation_ledger.py refuted_by_absence: no returned vote refutes it) is listed under not_adjudicated
instead, with not_adjudicated_note, so the next discovery round does not read it as refuted on merit.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_common import MANIFEST_SECTION, REPO_ROOT, ledger_module, load_json, slug, work_dir, write_json  # noqa: E402

CATALOG_FILES = (("foundation", "foundation.json"), ("us-equities", "us-equities.json"))
NOT_ADJUDICATED_NOTE = ("refuted in that sweep only because a vote did not return (a missing vote counts as refuted); "
                        "no returned vote refuted these, so they were not refuted on merit")
COMPONENT_FIELDS = ("id", "repository", "pin", "upstream", "pin_behind_upstream", "pin_comparison")


def rows_by_layer(manifest: dict | None, catalog: str) -> dict:
    section = MANIFEST_SECTION[catalog]
    return {row.get("layer"): row for row in ((manifest or {}).get(section) or []) if isinstance(row, dict)}


def last_completed(ledger: dict) -> dict | None:
    completed = [sweep for sweep in ledger.get("sweeps") or [] if sweep.get("status") == "completed"]
    return completed[-1] if completed else None


def check_seeds(seeds, layer_ids) -> dict:
    if seeds is None:
        return {}
    if not isinstance(seeds, dict) or not all(isinstance(v, list) and all(isinstance(x, str) for x in v)
                                              for v in seeds.values()):
        raise ValueError('--seeds must be a JSON object {"<layer_id>": ["...", ...]}')
    unknown = sorted(set(seeds) - set(layer_ids))
    if unknown:
        raise ValueError(f"--seeds names layers that are not in the landscape catalogs: {unknown}")
    return seeds


def build_layer_inputs(catalogs: dict, research_state: dict, scope: dict, freshness: dict, baseline: dict | None,
                       ledger: dict, seeds=None, absent=None) -> list[dict]:
    """One input object per landscape layer, in catalog order; raises on a layer missing from the frozen scope.
    ``absent(entry)`` says whether a refuted ledger entry is refuted by absence (main() passes the ledger's
    refuted_by_absence over this checkout's retained returns); without it every refuted entry stays refuted."""
    research = {(row["catalog"], row["layer_id"]): row for row in research_state.get("layers") or []}
    previous_sweep = last_completed(ledger)
    previous = {}
    for layer in (previous_sweep or {}).get("layers") or []:
        refuted = [entry for entry in layer.get("refuted") or []]
        not_adjudicated = [entry["repo"] for entry in refuted if absent is not None and absent(entry)]
        previous[(layer.get("catalog"), layer.get("layer_id"))] = {
            "sweep_id": previous_sweep.get("sweep_id"),
            "survived": [entry["repo"] for entry in layer.get("survived") or []],
            "refuted": [entry["repo"] for entry in refuted if entry["repo"] not in not_adjudicated],
            **({"not_adjudicated": not_adjudicated, "not_adjudicated_note": NOT_ADJUDICATED_NOTE}
               if not_adjudicated else {})}
    all_ids = [layer["layer_id"] for catalog, _ in CATALOG_FILES for layer in catalogs[catalog]["layers"]]
    duplicates = sorted({layer_id for layer_id in all_ids if all_ids.count(layer_id) > 1})
    if duplicates:
        raise ValueError(f"layer ids repeat across catalogs (inputs/<layer_id>.json would collide): {duplicates}")
    seeds = check_seeds(seeds, all_ids)
    out, missing = [], []
    for catalog, _ in CATALOG_FILES:
        baseline_rows, fresh_rows = rows_by_layer(baseline, catalog), rows_by_layer(freshness, catalog)
        for layer in catalogs[catalog]["layers"]:
            layer_id = layer["layer_id"]
            key = f"{catalog}/{layer_id}"
            known = {slug(item.get("repository")) for field in ("candidates", "alternatives", "winners")
                     for item in layer.get(field) or []}
            known |= {slug(item.get("repository")) for item in baseline_rows.get(layer_id, {}).get("candidates") or []}
            known.discard("")
            fresh = fresh_rows.get(layer_id, {})
            components = [{field: item.get(field) for field in COMPONENT_FIELDS if field in item}
                          for item in (fresh.get("components") or fresh.get("entries") or [])]
            state = research.get((catalog, layer_id), {})
            requirement = (scope.get("requirement_sha256") or {}).get(key)
            if not requirement:
                missing.append(key)
            out.append({
                "catalog": catalog, "layer_id": layer_id, "title": layer.get("title"),
                "requirement": layer.get("requirement"),
                "research_status": state.get("status"), "next_action": state.get("next_action"),
                "requirement_sha256": requirement, "platform_profiles_sha256": scope.get("platform_profiles_sha256"),
                "winners": [{field: winner.get(field) for field in ("component_id", "repository", "pin",
                                                                     "evidence_class", "platform_status")
                             if winner.get(field) is not None} for winner in layer.get("winners") or []],
                "alternatives": [{field: alt.get(field) for field in ("name", "repository", "disposition")}
                                 for alt in layer.get("alternatives") or []],
                "upstream_checked_at": freshness.get("checked_at"),
                "components_vs_upstream": components,
                "open_gaps": [gap[:300] for gap in (layer.get("open_gaps") or [])[:5]],
                "overturn_when": (layer.get("overturn_when") or "")[:600],
                "previous_sweep": previous.get((catalog, layer_id), {}),
                "known_repositories": sorted(known),
                "seeded_candidates": list(seeds.get(layer_id, [])),
            })
    if missing:
        raise ValueError(f"the frozen scope has no requirement_sha256 for {missing}; refreeze it with "
                         "saturation_ledger.py --scope")
    if not scope.get("platform_profiles_sha256"):
        raise ValueError("the frozen scope has no platform_profiles_sha256")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", default=os.environ.get("SWEEP_WORK_DIR"))
    parser.add_argument("--freshness-manifest", type=Path, required=True)
    parser.add_argument("--scope", type=Path, help="default <work-dir>/scope.json")
    parser.add_argument("--baseline-manifest", type=Path,
                        help="default: manifest_ref of the saturation ledger's last completed sweep")
    parser.add_argument("--seeds", type=Path)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    try:
        work = work_dir(args.work_dir)
        repo = args.repo_root.resolve()
        ledger = load_json(repo / "catalogs" / "saturation" / "ledger.json")
        baseline_path = args.baseline_manifest
        if baseline_path is None and last_completed(ledger) and last_completed(ledger).get("manifest_ref"):
            baseline_path = repo / last_completed(ledger)["manifest_ref"]
        catalogs = {catalog: load_json(repo / "catalogs" / "landscape" / name) for catalog, name in CATALOG_FILES}
        led = ledger_module(REPO_ROOT)  # the ledger's rules from this checkout, applied to --repo-root's files
        documents = {}
        target_of = led.ref_resolver(lambda path: documents[path] if path in documents
                                     else documents.setdefault(path, led.load_json(repo, path)))
        inputs = build_layer_inputs(
            catalogs, load_json(repo / "catalogs" / "landscape" / "research-state.json"),
            load_json(args.scope or work / "scope.json"), load_json(args.freshness_manifest),
            load_json(baseline_path) if baseline_path else None, ledger,
            load_json(args.seeds) if args.seeds else None,
            absent=lambda entry: led.refuted_by_absence(entry, target_of))
    except (ValueError, OSError, KeyError) as error:
        print(f"build_inputs.py: {error}", file=sys.stderr)
        return 2
    (work / "inputs").mkdir(exist_ok=True)
    layers = []
    for layer_input in inputs:
        path = work / "inputs" / f"{layer_input['layer_id']}.json"
        write_json(path, layer_input)
        layers.append({"catalog": layer_input["catalog"], "layer_id": layer_input["layer_id"],
                       "title": layer_input["title"], "input": str(path)})
    write_json(work / "layers.json", layers)
    print(f"{len(layers)} layers; {sum(1 for x in layers if x['catalog'] == 'foundation')} foundation; "
          f"baseline {baseline_path.name if baseline_path else 'none'}; seeds for "
          f"{sum(1 for x in inputs if x['seeded_candidates'])} layer(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
