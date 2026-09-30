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

The skills modality (README.md, Skills modality) builds the skills-* layers of catalogs/landscape/skills-lifecycle.json
instead, one per lifecycle task, keyed by skill (owner/repo@name) rather than repository:

  build_inputs.py --skills-scope [--repo-root .] > W/scope.json
  build_inputs.py --work-dir W --modality skills [--scope W/scope.json] [--seeds seeds.json] [--repo-root .]

--skills-scope prints the frozen scope in saturation_ledger.py --scope's format for the skills catalog (whose --scope
covers research-state.json's layers only): each task's requirement_sha256, the sha256 of the canonical JSON of its
lifecycle_task, requirement and overturn_when, under "skills/<layer_id>", and the platform-profile hash, both with
the ledger's own functions. A skills layer input carries modality "skills", the task, the installed skills'
adoption/skills/manifest.json pins and invocation flags, the task's sources with their pins, and known_skills (the
manifest's installed skills by repository and its excluded skills by source, as it states them). No freshness
manifest is read. A run covers one modality.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_common import MANIFEST_SECTION, REPO_ROOT, ledger_module, load_json, slug, work_dir, write_json  # noqa: E402

CATALOG_FILES = (("foundation", "foundation.json"), ("us-equities", "us-equities.json"))
NOT_ADJUDICATED_NOTE = ("refuted in that sweep only because a vote did not return (a missing vote counts as refuted); "
                        "no returned vote refuted these, so they were not refuted on merit")
COMPONENT_FIELDS = ("id", "repository", "pin", "upstream", "pin_behind_upstream", "pin_comparison")
# The skills modality's catalog, its layers' catalog name and its source kinds.
SKILLS_CATALOG = "catalogs/landscape/skills-lifecycle.json"
SKILLS_MANIFEST = "adoption/skills/manifest.json"
SKILLS = "skills"
SOURCE_KINDS = ("github-skills-repo", "registry", "awesome-list")
# A skills layer's frozen requirement: these fields of its task, hashed as saturation_ledger.py hashes a
# research-state row (sha256 of the canonical JSON).
SKILLS_REQUIREMENT_FIELDS = ("lifecycle_task", "requirement", "overturn_when")
# What a skills layer input shows of each installed skill's adoption/skills/manifest.json row.
INSTALLED_FIELDS = ("name", "source", "ref", "path", "skill_md_sha256", "description_chars", "status",
                    "upstream_disable_model_invocation", "claude_listing", "codex_enabled", "gap")
TASK_FIELDS = ("layer_id", "lifecycle_task", "requirement", "installed", "source_ids", "open_gaps", "overturn_when")
HEX40 = re.compile(r"[0-9a-f]{40}")


def rows_by_layer(manifest: dict | None, catalog: str) -> dict:
    section = MANIFEST_SECTION[catalog]
    return {row.get("layer"): row for row in ((manifest or {}).get(section) or []) if isinstance(row, dict)}


def last_completed(ledger: dict, catalog: str | None = None) -> dict | None:
    """The ledger's last completed sweep; with `catalog`, the last completed sweep with a layer of that catalog (a
    skills run reads the last skills sweep, whatever repository sweeps followed it)."""
    completed = [sweep for sweep in ledger.get("sweeps") or [] if sweep.get("status") == "completed"
                 and (catalog is None or any(layer.get("catalog") == catalog for layer in sweep.get("layers") or []))]
    return completed[-1] if completed else None


def previous_by_layer(previous_sweep: dict | None, absent=None) -> dict:
    """(catalog, layer_id) -> that sweep's survived, refuted and not_adjudicated entries (see build_layer_inputs)."""
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
    return previous


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
    previous = previous_by_layer(last_completed(ledger), absent)
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


# --------------------------------------------------------------------------- the skills modality


def check_skills_catalog(catalog: dict, manifest: dict) -> list[str]:
    """Problems of catalogs/landscape/skills-lifecycle.json against the pinned skills manifest."""
    problems = []
    if catalog.get("kind") != "skills-lifecycle" or catalog.get("schema_version") != 1:
        problems.append("skills catalog: kind must be skills-lifecycle with schema_version 1")
    source_ids = []
    for position, source in enumerate(catalog.get("sources") or []):
        label = f"sources[{position}] {source.get('source_id') if isinstance(source, dict) else source!r}"
        if not isinstance(source, dict) or sorted(source) != ["kind", "pin", "source_id", "url"]:
            problems.append(f"skills catalog {label}: needs exactly source_id, kind, url and pin")
            continue
        source_ids.append(source["source_id"])
        if source["kind"] not in SOURCE_KINDS:
            problems.append(f"skills catalog {label}: kind {source['kind']!r} is not one of {list(SOURCE_KINDS)}")
        if not HEX40.fullmatch(str(source["pin"])):
            problems.append(f"skills catalog {label}: pin must be a 40-hex commit")
    repeated = sorted({sid for sid in source_ids if source_ids.count(sid) > 1})
    if repeated:
        problems.append(f"skills catalog: source ids repeat: {repeated}")
    pinned = {entry.get("name") for entry in manifest.get("skills") or [] if isinstance(entry, dict)}
    layer_ids = []
    for position, task in enumerate(catalog.get("tasks") or []):
        if not isinstance(task, dict) or sorted(task) != sorted(TASK_FIELDS):
            problems.append(f"skills catalog tasks[{position}]: needs exactly {list(TASK_FIELDS)}")
            continue
        layer_id = task["layer_id"]
        layer_ids.append(layer_id)
        if layer_id != f"skills-{task['lifecycle_task']}":
            problems.append(f"skills catalog tasks[{position}]: layer_id {layer_id} is not skills-<lifecycle_task>")
        unpinned = sorted(set(task["installed"]) - pinned)
        if unpinned:
            problems.append(f"skills catalog {layer_id}: installed names skills {SKILLS_MANIFEST} does not pin: "
                            f"{unpinned}")
        unknown = sorted(set(task["source_ids"]) - set(source_ids))
        if unknown:
            problems.append(f"skills catalog {layer_id}: unknown source ids {unknown}")
    repeated = sorted({layer_id for layer_id in layer_ids if layer_ids.count(layer_id) > 1})
    if repeated:
        problems.append(f"skills catalog: layer ids repeat: {repeated}")
    if not layer_ids:
        problems.append("skills catalog: no tasks")
    return problems


def skills_scope(catalog: dict, adoption: dict, led) -> dict:
    """The frozen scope of the skills layers in saturation_ledger.py --scope's format, with the ledger's functions."""
    return {"platform_profiles_sha256": led.platform_profiles_sha256(adoption),
            "requirement_sha256": {f"{SKILLS}/{task['layer_id']}": led.sha256_bytes(led.canonical(
                {field: task.get(field) for field in SKILLS_REQUIREMENT_FIELDS})) for task in catalog["tasks"]}}


def known_skills(manifest: dict) -> dict:
    """The manifest's installed skills by source repository and its excluded skills by the manifest's own source text.
    An excluded entry can name several repositories and phrases ("openai/skills, anthropics/skills"; "the figma and
    notion skills"), so no owner/repo@name pair is inferred from it: the words stay as the manifest states them."""
    installed, excluded = {}, {}
    for entry in manifest.get("skills") or []:
        if isinstance(entry, dict) and entry.get("name"):
            installed.setdefault(str(entry.get("source")), set()).add(str(entry["name"]))
    for entry in manifest.get("excluded") or []:
        if isinstance(entry, dict):
            excluded.setdefault(str(entry.get("source")), set()).update(str(name) for name in entry.get("skills") or [])
    return {"installed": {source: sorted(names) for source, names in sorted(installed.items())},
            "excluded": {source: sorted(names) for source, names in sorted(excluded.items())}}


def build_skills_inputs(catalog: dict, manifest: dict, scope: dict, ledger: dict, seeds=None, absent=None) -> list:
    """One input object per skills-* layer, in catalog order (the skills modality; see the module docstring)."""
    problems = check_skills_catalog(catalog, manifest)
    if problems:
        raise ValueError("; ".join(problems))
    tasks = catalog["tasks"]
    seeds = check_seeds(seeds, [task["layer_id"] for task in tasks])
    previous = previous_by_layer(last_completed(ledger, SKILLS), absent)
    pinned = {entry["name"]: entry for entry in manifest.get("skills") or [] if isinstance(entry, dict)}
    sources = {source["source_id"]: source for source in catalog["sources"]}
    known = known_skills(manifest)
    out, missing = [], []
    for task in tasks:
        layer_id = task["layer_id"]
        requirement = (scope.get("requirement_sha256") or {}).get(f"{SKILLS}/{layer_id}")
        if not requirement:
            missing.append(f"{SKILLS}/{layer_id}")
        out.append({
            "catalog": SKILLS, "layer_id": layer_id, "title": f"Skills: {task['lifecycle_task']}", "modality": SKILLS,
            "lifecycle_task": task["lifecycle_task"], "requirement": task["requirement"],
            "requirement_sha256": requirement, "platform_profiles_sha256": scope.get("platform_profiles_sha256"),
            "installed": [{field: (pinned[name][field][:300] if field == "gap" else pinned[name][field])
                           for field in INSTALLED_FIELDS if field in pinned[name]} for name in task["installed"]],
            "sources": [dict(sources[source_id]) for source_id in task["source_ids"]],
            "open_gaps": [gap[:300] for gap in (task.get("open_gaps") or [])[:5]],
            "overturn_when": (task.get("overturn_when") or "")[:600],
            "skills_catalog_checked_at": catalog.get("checked_at"),
            "skills_manifest_checked_at": manifest.get("checked_at"),
            "previous_sweep": previous.get((SKILLS, layer_id), {}),
            "known_skills": known,
            "seeded_candidates": list(seeds.get(layer_id, [])),
        })
    if missing:
        raise ValueError(f"the frozen scope has no requirement_sha256 for {missing}; freeze it with "
                         "build_inputs.py --skills-scope")
    if not scope.get("platform_profiles_sha256"):
        raise ValueError("the frozen scope has no platform_profiles_sha256")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work-dir", default=os.environ.get("SWEEP_WORK_DIR"))
    parser.add_argument("--freshness-manifest", type=Path, help="required for repository layers")
    parser.add_argument("--scope", type=Path, help="default <work-dir>/scope.json")
    parser.add_argument("--baseline-manifest", type=Path,
                        help="default: manifest_ref of the saturation ledger's last completed sweep")
    parser.add_argument("--seeds", type=Path)
    parser.add_argument("--modality", choices=("repository", SKILLS), default="repository",
                        help=f"repository: the landscape catalogs' layers (default); skills: the skills-* layers of "
                             f"{SKILLS_CATALOG}")
    parser.add_argument("--skills-scope", action="store_true",
                        help="print the skills layers' frozen scope (saturation_ledger.py --scope's format) and exit")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    if args.skills_scope:
        try:
            repo = args.repo_root.resolve()
            scope = skills_scope(load_json(repo / SKILLS_CATALOG), load_json(repo / "adoption" / "manifest.json"),
                                 ledger_module(REPO_ROOT))
        except (ValueError, OSError, KeyError, TypeError) as error:
            print(f"build_inputs.py: {error}", file=sys.stderr)
            return 2
        print(json.dumps(scope, indent=1, sort_keys=True))
        return 0
    if args.modality == SKILLS:
        if args.freshness_manifest or args.baseline_manifest:
            parser.error("--freshness-manifest and --baseline-manifest describe repository layers; the skills "
                         "modality reads its pins from the skills catalog")
        return skills_main(args)
    if args.freshness_manifest is None:
        parser.error("--freshness-manifest is required for repository layers")
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


def skills_main(args) -> int:
    """build_inputs.py --modality skills: the skills-* layer inputs and layers.json (rows carry modality)."""
    try:
        work = work_dir(args.work_dir)
        repo = args.repo_root.resolve()
        ledger = load_json(repo / "catalogs" / "saturation" / "ledger.json")
        led = ledger_module(REPO_ROOT)
        documents = {}
        target_of = led.ref_resolver(lambda path: documents[path] if path in documents
                                     else documents.setdefault(path, led.load_json(repo, path)))
        inputs = build_skills_inputs(
            load_json(repo / SKILLS_CATALOG), load_json(repo / SKILLS_MANIFEST),
            load_json(args.scope or work / "scope.json"), ledger, load_json(args.seeds) if args.seeds else None,
            absent=lambda entry: led.refuted_by_absence(entry, target_of))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"build_inputs.py: {error}", file=sys.stderr)
        return 2
    (work / "inputs").mkdir(exist_ok=True)
    layers = []
    for layer_input in inputs:
        path = work / "inputs" / f"{layer_input['layer_id']}.json"
        write_json(path, layer_input)
        layers.append({"catalog": layer_input["catalog"], "layer_id": layer_input["layer_id"],
                       "title": layer_input["title"], "input": str(path), "modality": SKILLS})
    write_json(work / "layers.json", layers)
    print(f"{len(layers)} skills layers from {SKILLS_CATALOG}; seeds for "
          f"{sum(1 for x in inputs if x['seeded_candidates'])} layer(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
