#!/usr/bin/env python3
"""Build the per-layer inputs a landscape sweep's workers read (offline by default, no model calls).

  build_inputs.py --work-dir W --freshness-manifest manifest-YYYYMMDD.json
                  [--scope W/scope.json] [--baseline-manifest catalogs/sota-convergence/manifest-YYYYMMDD.json]
                  [--seeds seeds.json] [--repo-root .]
                  [--contract-version 2 [--pull-upstream-facts]]

Reads the frozen scope (`saturation_ledger.py --scope`, default <work-dir>/scope.json), catalogs/landscape/
{foundation,us-equities}.json and research-state.json, the saturation ledger's last completed repository sweep, a
baseline manifest (default: that sweep's manifest_ref) whose candidates count as known, and a catalog-freshness manifest
(build_manifest.py over extract_layers.py + github_freshness.py output with an empty lanes record, or the
catalog-freshness workflow's artifact) for each winner's pin against upstream. Writes <work-dir>/inputs/<layer_id>.json
and <work-dir>/layers.json ([{catalog, layer_id, title, input}] in catalog order).

Each modality keeps its own history: a ledger sweep's modality is named by its layers' catalogs (repository for
foundation and us-equities, skills for skills; sweep_modality), and a run reads previous_sweep, and a repository run
its default baseline, from the last completed sweep of its own modality only. A modality with no completed sweep gets
an empty previous_sweep and no baseline, and the summary line names the sweep it read ("previous ... sweep none").

--seeds is an optional JSON object {"<layer_id>": ["candidate or note", ...]}: candidates other sessions asked this
sweep to assess, shown to the discovery workers as seeded_candidates. An unknown layer id is an error.

winners, alternatives and open_gaps are copied from the row's sealed verdict, which only a new verdict wave re-records
(tools/sota-convergence/README.md, "Record verdicts"), so an input dates them: verdict_checked_at is the row's
checked_at, verdict_note says which fields are sealed and where the current pin is (components_vs_upstream), and
open_gaps_followup joins the gap-wave owner ledgers (catalogs/landscape/gap-wave*--*.json, the ledgers
lane_packets.gap_receipts_index reads) onto the gaps shown: per gap, each distinct status a ledger recorded with its
receipts that exist in this checkout, the waves and the ledger ids. A ledger entry joins only when its index and text
equal the sealed open gap's; the summary line counts the ledger entries joined, those that match no sealed gap and
those for gaps beyond the five shown.

previous_sweep holds that sweep's survived and refuted repositories. A proposal it refuted only because a vote did
not return (saturation_ledger.py refuted_by_absence: no returned vote refutes it) is listed under not_adjudicated
instead, with not_adjudicated_note, so the next discovery round does not read it as refuted on merit.

The skills modality (README.md, Skills modality) builds the skills-* layers of catalogs/landscape/skills-lifecycle.json
instead, one per lifecycle task, keyed by skill (owner/repo@name) rather than repository:

  build_inputs.py --skills-scope [--repo-root .] > W/scope.json
  build_inputs.py --work-dir W --modality skills [--scope W/scope.json] [--seeds seeds.json] [--repo-root .]

--skills-scope prints the frozen scope in saturation_ledger.py --scope's format for the skills catalog (whose --scope
covers research-state.json's layers only): each task's requirement_sha256 (saturation_ledger.skills_requirement_sha256:
the sha256 of the canonical JSON of its lifecycle_task, requirement and overturn_when) under "skills/<layer_id>", and
the platform-profile hash, both with the ledger's own functions. A skills layer input carries modality "skills", the
task, the installed skills' adoption/skills/manifest.json pins and invocation flags, the task's sources with their pins
(and a stale source's maintenance record), and known_skills (the manifest's installed skills by repository, and its
excluded skills by the manifest's own source text, each comma-separated name kept whole). The task's text, its open
gaps and the installed skills' gap fields are passed whole, never cut. No freshness manifest is read. A run covers
one modality.

V2's blind facts never inherit facts from a candidate's catalog, adoption or sweep record. Without
--pull-upstream-facts every upstream value is null and every observation is pending/not_requested. The opt-in pulls
each distinct repository once in sorted order, through the maintained gh_api/hub_get transports (60 seconds per
request), then freezes upstream-facts-v2.json and shares its observations across all memberships. Source failures
remain pending and do not abort later members. Response and snapshot hashes bind complete canonical parsed JSON
(sorted keys, UTF-8, no separator whitespace), not raw HTTP bytes. GitHub commit dates come from the default branch;
Hub lastModified is kept separately and is not asserted to be a default-branch commit date. These observations are
inputs to the future script screen, never a maintenance verdict, model execution or provider-usage record.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_common import (  # noqa: E402
    MANIFEST_SECTION, REPO_ROOT, canon, ledger_module, load_json, sha256_bytes, slug, work_dir, write_json,
)

CATALOG_FILES = (("foundation", "foundation.json"), ("us-equities", "us-equities.json"))
REPOSITORY = "repository"  # --modality's repository modality (build_args.REPOSITORY_MODALITY)
NOT_ADJUDICATED_NOTE = ("refuted in that sweep only because a vote did not return (a missing vote counts as refuted); "
                        "no returned vote refuted these, so they were not refuted on merit")
COMPONENT_FIELDS = ("id", "repository", "pin", "upstream", "pin_behind_upstream", "pin_comparison")
# How many of a row's open gaps an input shows, and the length each is cut to.
GAPS_SHOWN, GAP_CLIP = 5, 300
# The gap-wave owner ledgers (tools/sota-convergence/lane_packets.py GAP_LEDGER_GLOB): per layer, each open gap of the
# sealed verdict by index and text, with the status and the receipts a later wave recorded for it.
GAP_LEDGER_GLOB = "catalogs/landscape/gap-wave*--*.json"
VERDICT_NOTE = ("winners, alternatives and open_gaps are this layer's sealed verdict as of verdict_checked_at; a "
                "verdict is not rewritten between verdict waves, so a pin or a gap in them can be out of date. "
                "components_vs_upstream[].pin is the pin the stack installs today. open_gaps_followup lists, by "
                "open_gaps index, what a later gap wave recorded for that gap (status, receipts, waves, ledgers); "
                "a gap without an entry has no follow-up on record.")
# The skills modality's catalog, its layers' catalog name and its source kinds.
SKILLS_CATALOG = "catalogs/landscape/skills-lifecycle.json"
SKILLS_MANIFEST = "adoption/skills/manifest.json"
SKILLS = "skills"
SOURCE_KINDS = ("github-skills-repo", "registry", "awesome-list")
SOURCE_FIELDS = ("source_id", "kind", "url", "pin")
# A source's optional maintenance record: the common block's maintenance rule applied when the catalog was checked
# (status stale: archived, or no default-branch commit in the 90 days before checked_at), with the API fact.
MAINTENANCE_FIELDS = ("status", "checked_at", "evidence")
MAINTENANCE_STATUSES = ("stale",)
# A skills layer's frozen requirement: these fields of its task (saturation_ledger.SKILLS_REQUIREMENT_FIELDS, whose
# skills_requirement_sha256 computes the hash).
SKILLS_REQUIREMENT_FIELDS = ("lifecycle_task", "requirement", "overturn_when")
# What a skills layer input shows of each installed skill's adoption/skills/manifest.json row.
INSTALLED_FIELDS = ("name", "source", "ref", "path", "skill_md_sha256", "description_chars", "status",
                    "upstream_disable_model_invocation", "claude_listing", "codex_enabled", "gap")
TASK_FIELDS = ("layer_id", "lifecycle_task", "requirement", "installed", "source_ids", "open_gaps", "overturn_when")
HEX40 = re.compile(r"[0-9a-f]{40}")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# U11 E summaries of declarative requirements from the unchanged acceptance plan, never its observed-status narrative.
# Source: blueprints/us-equities/engine-nautilus/acceptance-plan.md at 798ac445, sections 1-3, 4, and 5-6.
# NeutralFieldTests pins the SHA256 of the exact three section ranges; these sentences are summaries, not extracts.
ACCEPTANCE_REQUIREMENTS = {
    "retained-equity-replay": (
        "Replay the frozen equity tasks with declared identity, data, time, visibility, fill, distribution, cost and "
        "margin mappings; reproduce numeric accounting and independently reconcile the fixed fixture oracle.", "1"),
    "broker-state-failures": (
        "Offline, with a fake transport and injected clock and failures (no credentials or network): keep a durable "
        "intent/order/fill journal and deterministic numeric risk per account. Under frozen limits, exercise duplicate "
        "intent, lost response, rejection, partial/duplicate fills, cancel race, crash/restart, stale/session/risk, rate "
        "and disconnect, snapshot contradiction and kill boundaries, with zero duplicate economic effects or "
        "unexplained differences; retain each case's expected and actual results.", "4"),
    "separate-paper-adapters": (
        "Qualify each broker independently, only after its own offline suite passes: verify paper account and "
        "contract identity read-only, freeze numeric risk and request limits, run bounded submit/fill/cancel and "
        "reconnect/restart cases, reconcile durable state, cash and fees (including fee-posting timing), and apply "
        "the declared final order/position disposition with zero duplicate effects and no unexplained differences.", "5"),
}
UPSTREAM_FACT_FIELDS = ("latest_release", "released_at", "pushed_at", "archived", "disabled", "default_branch",
                        "head_commit", "head_committed_at", "last_modified", "gated")


def rows_by_layer(manifest: dict | None, catalog: str) -> dict:
    section = MANIFEST_SECTION[catalog]
    return {row.get("layer"): row for row in ((manifest or {}).get(section) or []) if isinstance(row, dict)}


def sweep_modality(sweep: dict) -> str | None:
    """The modality a ledger sweep ran, named by its layers' catalogs: "repository" when they are all foundation or
    us-equities layers, "skills" when they are all skills layers. None for a sweep with no layer or with layers of
    both, which neither modality's history takes (a run covers one modality)."""
    catalogs = {layer.get("catalog") for layer in (sweep or {}).get("layers") or [] if isinstance(layer, dict)}
    if catalogs and catalogs <= {catalog for catalog, _ in CATALOG_FILES}:
        return REPOSITORY
    return SKILLS if catalogs == {SKILLS} else None


def last_completed(ledger: dict, modality: str) -> dict | None:
    """The ledger's last completed sweep of that modality (sweep_modality). A repository run never reads a skills
    sweep, nor a skills run a repository sweep, whichever ran last."""
    completed = [sweep for sweep in ledger.get("sweeps") or [] if isinstance(sweep, dict)
                 and sweep.get("status") == "completed" and sweep_modality(sweep) == modality]
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


def gap_ledger_entries(repo: Path) -> tuple[list, int]:
    """Every gap entry of the gap-wave owner ledgers under ``repo``, in ledger path order, and the ledger count:
    {catalog, layer_id, index, text, status, receipts, waves, ledger}. receipts keeps the paths that are files in this
    checkout (lane_packets.gap_receipts_index applies the same rule)."""
    entries, ledgers = [], sorted(repo.glob(GAP_LEDGER_GLOB))
    for ledger_path in ledgers:
        ledger = load_json(ledger_path)
        waves = ledger.get("wave")
        waves = [waves] if isinstance(waves, str) else [wave for wave in waves or [] if isinstance(wave, str)]
        for layer in ledger.get("layers") or []:
            for gap in layer.get("gaps") or []:
                receipts = [receipt.get("path") for receipt in gap.get("receipts") or [] if isinstance(receipt, dict)]
                entries.append({
                    "catalog": layer.get("catalog"), "layer_id": layer.get("layer_id"), "index": gap.get("index"),
                    "text": gap.get("text"), "status": gap.get("status"),
                    "receipts": [path for path in receipts if isinstance(path, str) and (repo / path).is_file()],
                    "waves": waves, "ledger": ledger.get("id") or ledger_path.stem})
    return entries, len(ledgers)


def join_gap_followups(catalogs: dict, entries: list) -> tuple[dict, dict]:
    """(catalog, layer_id) -> the follow-up entries of that layer's shown open gaps, by index then ledger order, and
    the counts {joined, dropped, beyond} of ledger entries. An entry joins when the layer's sealed open_gaps[index]
    equals its text; ledgers that record the same status and receipts for a gap share one entry (waves and ledgers
    name them all). dropped counts the entries that match no sealed open gap (an unknown layer, another index or
    another text), beyond those that match a gap past the GAPS_SHOWN an input shows."""
    gaps = {(catalog, layer["layer_id"]): layer.get("open_gaps") or []
            for catalog, _ in CATALOG_FILES for layer in catalogs[catalog]["layers"]}
    followups, counts = {}, {"joined": 0, "dropped": 0, "beyond": 0}
    for entry in entries:
        key, index = (entry["catalog"], entry["layer_id"]), entry["index"]
        sealed = gaps.get(key)
        if (sealed is None or not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(sealed)
                or sealed[index] != entry["text"]):
            counts["dropped"] += 1
        elif index >= GAPS_SHOWN:
            counts["beyond"] += 1
        else:
            counts["joined"] += 1
            rows = followups.setdefault(key, [])
            same = next((row for row in rows if (row["index"], row["status"], row["receipts"])
                         == (index, entry["status"], entry["receipts"])), None)
            if same is None:
                rows.append({"index": index, "status": entry["status"], "receipts": entry["receipts"],
                             "waves": list(entry["waves"]), "ledgers": [entry["ledger"]]})
            else:  # two ledgers record the same status and receipts for this gap: one entry names both
                same["waves"] += [wave for wave in entry["waves"] if wave not in same["waves"]]
                same["ledgers"].append(entry["ledger"])
    return {key: sorted(rows, key=lambda row: row["index"]) for key, rows in followups.items()}, counts


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


def repository_identity(value, annotated=False) -> str | None:
    """The existing sweep_common canonical identity, restricted to repository candidates, not seed notes."""
    if isinstance(value, dict):
        value = value.get("repository") or value.get("repo")
    if not isinstance(value, str):
        return None
    if annotated:
        value = value.split(" (", 1)[0]
    repository = canon(value)
    if isinstance(repository, str) and re.fullmatch(r"https://github.com/[a-z0-9-]+/[a-z0-9._-]+", repository):
        return repository
    # The maintained source-review adapter already recognizes Hub model repositories and rejects Hub sections.
    from source_reviews import HUB, hub_model
    model = hub_model(repository)
    return f"{HUB}/{model}" if model else None


def field_record_sources(repo: Path, catalogs: dict, ledger: dict) -> dict:
    """Retained typed records only: manifests, independent reviews and every sweep's returned proposals.

    This extends the current manifest_layer_candidates/previous_by_layer joins without their V1 disposition or
    survival filters. Source references stay in the owner input; the blind screen does not read their labels/prose.
    """
    layer_catalog = {layer["layer_id"]: catalog for catalog, _ in CATALOG_FILES
                     for layer in catalogs[catalog]["layers"]}
    sources = {}

    def add(catalog, layer_id, values, ref, annotated=False, single=False):
        catalog = catalog or layer_catalog.get(layer_id)
        if layer_catalog.get(layer_id) != catalog:
            return
        for index, value in enumerate(values or []):
            repository = repository_identity(value, annotated)
            if repository:
                sources.setdefault((catalog, layer_id), []).append({
                    "repository": repository, "record": value if isinstance(value, dict) else {},
                    "ref": ref if single else f"{ref}/{index}"})

    paths = {path.relative_to(repo).as_posix() for path in (repo / "catalogs/sota-convergence").glob("manifest-*.json")}
    paths |= {"catalogs/landscape/candidate-quality-review.json", "catalogs/landscape/independent-discovery.json",
              "evidence/artifacts/blind-catalog-convergence-20260921/claude-final-layers.json",
              "evidence/artifacts/blind-catalog-convergence-20260921/codex-source-review.json"}
    for sweep in ledger.get("sweeps") or []:
        if sweep_modality(sweep) != REPOSITORY:
            continue
        if sweep.get("record_ref"):
            paths.add(sweep["record_ref"].split("#", 1)[0])
        for layer in sweep.get("layers") or []:
            if isinstance(layer.get("discovery_ref"), str):
                paths.add(layer["discovery_ref"].split("#", 1)[0])
    for rel in sorted(paths):
        path = (repo / rel).resolve()
        if not path.is_relative_to(repo.resolve()):
            raise ValueError(f"field source escapes the checkout: {rel}")
        if not path.is_file():
            continue
        document = load_json(path)
        if isinstance(document, list):  # retained second-family final layer review
            for index, layer in enumerate(document):
                for field in ("selected", "challengers"):
                    add(layer.get("catalog"), layer.get("layer_id"), layer.get(field),
                        f"{rel}#/{index}/{field}", annotated=True)
            continue
        for catalog, section in MANIFEST_SECTION.items():
            for index, layer in enumerate(document.get(section) or []):
                for field in ("components", "entries", "candidates", "alternatives_keep_but_compare", "alternatives"):
                    add(catalog, layer.get("layer"), layer.get(field), f"{rel}#/{section}/{index}/{field}")
        for index, layer in enumerate(document.get("layer_coverage") or []):
            add(layer.get("catalog"), layer.get("layer_id"), layer.get("challenger_repositories"),
                f"{rel}#/layer_coverage/{index}/challenger_repositories")
        for index, candidate in enumerate(document.get("candidates") or []):
            for layer in candidate.get("layers") or []:
                add(layer.get("catalog"), layer.get("layer_id"), [candidate], f"{rel}#/candidates/{index}", single=True)
        for index, layer in enumerate(document.get("layers") or []):
            for field in ("primary_stack", "strongest_challengers", "repositories", "proposed", "merged", "dropped"):
                add(layer.get("catalog"), layer.get("layer_id"), layer.get(field), f"{rel}#/layers/{index}/{field}")
        for layer_id, layer in (document.get("discovery") or {}).items():
            add(layer.get("catalog"), layer_id, layer.get("proposed"), f"{rel}#/discovery/{layer_id}/proposed")
        for layer_id, rounds in (document.get("raw") or {}).items():
            for round_name, record in rounds.items():
                for family in ("claude_discover", "gpt6_discover"):
                    returned = record.get(family) or {}
                    prefix = f"{rel}#/raw/{layer_id}/{round_name}/{family}"
                    if isinstance(returned.get("output"), dict):
                        returned, prefix = returned["output"], prefix + "/output"
                    add(None, layer_id, returned.get("proposed"), prefix + "/proposed")
    return sources


def eligible_field(catalog: str, layer: dict, baseline: dict, fresh: dict, ledger: dict, seeds: list,
                   sources: list, catalog_index=0, baseline_index=0, freshness_index=0) -> list[dict]:
    """One identity per repository, independently of catalog adoption, V1 refutations or discovery's six-row cap.

    Every member awaits the same V2 screen. Historical health/fit labels are observations, never a new exclusion.
    """
    members = {}
    layer_id = layer["layer_id"]

    def add(value, ref, legacy_refuted=False, retained_v2=False, returns_ref=None):
        retained_refs, retained_reason = [], None
        if retained_v2 and isinstance(value, dict) and "candidate_key" in value:
            # Revision 5 item 6 and PR #590: a previously validated opaque identity is still material.
            led = ledger_module(REPO_ROOT)
            repository, candidate_key = led.v2_frozen_identity(catalog, layer_id, value)
            if value.get("candidate_key") != candidate_key or value.get("evidence_key") != candidate_key \
                    or value.get("repository") != repository:
                raise ValueError("retained V2 field has a mismatched identity")
            retained_refs = [returns_ref + entry if entry.startswith("#") and returns_ref else entry
                             for entry in value.get("evidence_refs", [])]
            retained_reason = value.get("pending_reason")
        else:
            repository = repository_identity(value)
            if not repository:
                return
            candidate_key = f"{catalog}/{layer_id}/{slug(repository)}"
        member = members.setdefault(candidate_key, {
            "candidate_key": candidate_key, "repository": repository, "disposition": "admit_pending",
            "pending_reason": "awaiting_v2_screen", "exclusion_reason": None,
            "evidence_key": candidate_key, "evidence_refs": [], "material": True})
        for entry in [ref, *retained_refs]:
            if entry not in member["evidence_refs"]:
                member["evidence_refs"].append(entry)
        if retained_reason:
            member["pending_reason"] = retained_reason
        if legacy_refuted:
            member["pending_reason"] = "legacy_v1_refutation"

    for field in ("candidates", "winners", "alternatives"):
        for index, record in enumerate(layer.get(field) or []):
            add(record, f"catalogs/landscape/{catalog}.json#/layers/{catalog_index}/{field}/{index}")
    for label, record, row_index in (("baseline_manifest", baseline, baseline_index),
                                    ("freshness_manifest", fresh, freshness_index)):
        for field in ("components", "entries", "candidates", "alternatives_keep_but_compare", "alternatives"):
            for index, value in enumerate(record.get(field) or []):
                add(value, f"{label}#/{MANIFEST_SECTION[catalog]}/{row_index}/{field}/{index}")
    for sweep_index, sweep in enumerate(ledger.get("sweeps") or []):
        if sweep_modality(sweep) != REPOSITORY:
            continue
        for layer_index, old in enumerate(sweep.get("layers") or []):
            if (old.get("catalog"), old.get("layer_id")) != (catalog, layer_id):
                continue
            retained_v2 = old.get("contract_version") == 2
            fields = ("eligible_field", "proposed", "survived", "refuted", "pending") if retained_v2 else (
                "proposed", "survived", "refuted", "pending")
            for field in fields:
                for index, value in enumerate(old.get(field) or []):
                    add(value, f"catalogs/saturation/ledger.json#/sweeps/{sweep_index}/layers/{layer_index}/{field}/{index}",
                        legacy_refuted=field == "refuted" and sweep.get("contract_version", 1) == 1,
                        retained_v2=retained_v2, returns_ref=sweep.get("returns_ref"))
    for index, seed in enumerate(seeds):
        add(seed, f"seeded_candidates#/{layer_id}/{index}")
    for source in sources:
        add(source["repository"], source["ref"])
    return [dict(member, evidence_refs=sorted(member["evidence_refs"])) for _, member in sorted(members.items())]


def field_sha256(layer_input: dict) -> str:
    """Bind the frozen identities to requirement/platform scope; mutable screen states and adoption are not inputs."""
    binding = {key: layer_input[key] for key in (
        "contract_version", "catalog", "layer_id", "requirement_sha256", "platform_profiles_sha256")}
    binding["members"] = sorted(({"candidate_key": row["candidate_key"], "repository": row["repository"]}
                                 for row in layer_input["eligible_field"]), key=lambda row: row["candidate_key"])
    return sha256_bytes(json.dumps(binding, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def neutral_requirement(text: str, candidates: list, pinned_requirements=None) -> str:
    """Reuse the maintained verdict packet's prose reducer; no candidate's recorded selection becomes a requirement."""
    saved_path = sys.path[:]
    try:
        sys.path.insert(0, str(HERE.parent))
        import lane_packets
    finally:
        sys.path[:] = saved_path
    text = text or ""
    pins = pinned_requirements or []
    protected = {slug(pin.get("repository")) for pin in pins if pin.get("repository")}
    names = {pin["name"].lower() for pin in pins}
    candidates = [candidate for candidate in candidates if slug(candidate.get("repository")) not in protected
                  and str(candidate.get("name") or "").lower() not in names]
    # These are the actual user destination and fixed oracle from U11 E/AGENTS.md, not a tool-selected default.
    for pin in pins:
        name = re.escape(pin["name"])
        text = re.sub(rf"\bselected\s+({name})\s+destination\b", r"user-pinned \1 destination", text, flags=re.I)
        text = re.sub(rf"\bprior\s+({name})\s+oracle\b", r"fixed \1 oracle", text, flags=re.I)
    # The existing matcher accepts layer words so an owner fragment (loopx-project's "project") cannot turn a
    # capability clause into a selection sentence. Full candidate names and repository slugs still reduce.
    layer_words = re.findall(r"[A-Za-z0-9]+", text)
    return lane_packets.reduce_prose(text, lane_packets.candidate_matcher(candidates, layer_words=layer_words))


def pinned_requirements(requirement: str, runtime_target: dict) -> list[dict]:
    """The recorded user carve-out, only when the runtime target names that exact destination and the text needs it."""
    engine = runtime_target.get("engine") or {}
    if (engine.get("decision") != "selected_destination"
            or slug(engine.get("repository")) != "nautechsystems/nautilus_trader"):
        return []
    pins = (("NautilusTrader", "user_pinned_destination", "https://github.com/nautechsystems/nautilus_trader"),
            ("IBKR", "user_pinned_broker", None), ("Alpaca", "user_pinned_separate_adapter", "https://github.com/alpacahq/alpaca-py"),
            ("LEAN", "fixture_oracle", "https://github.com/quantconnect/lean"))
    return [{"name": name, "role": role, "repository": repository, "source_ref": "AGENTS.md#trading-north-star"}
            for name, role, repository in pins if re.search(rf"\b{re.escape(name)}\b", requirement or "", re.I)]


def acceptance_gates(runtime_target: dict, candidates: list, pins: list) -> list[dict]:
    """The shared gate, what any member must show; execution status and incumbent evidence are kept out."""
    plan = runtime_target.get("acceptance_plan") or "blueprints/us-equities/engine-nautilus/acceptance-plan.md"
    gates = []
    for row in runtime_target.get("next_acceptance") or []:
        gate_id = row.get("id")
        # A future explicit declaration takes precedence. Current rows have only an observed scope, so use the
        # reviewed plan's requirement clauses above rather than republishing their historical outcome prose.
        declaration = row.get("gate")
        declared = declaration.get("requirement") if isinstance(declaration, dict) else declaration
        requirement, section = ACCEPTANCE_REQUIREMENTS.get(gate_id, (None, None))
        gates.append({"id": gate_id, "requirement": neutral_requirement(declared or requirement or "", candidates, pins),
                      "source_ref": f"{plan}#section-{section}" if section else
                      f"catalogs/us-equities/runtime-target.json#/next_acceptance/{len(gates)}/gate",
                      "pending_reason": None if declared or requirement else "gate_requirement_not_recorded"})
    return gates


def neutral_platform_requirements(profiles) -> list[dict]:
    """U11V4 A/B target-host facts from adoption/manifest.json, without adoption evidence or paths."""
    fields = ("id", "os", "architecture")
    if not isinstance(profiles, list) or not profiles or any(
            not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not row[key].strip()
                                             for key in fields) for row in profiles):
        raise ValueError("V2 platform requirements need explicit id/os/architecture in every platform profile")
    if len({row["id"] for row in profiles}) != len(profiles):
        raise ValueError("V2 platform requirements need unique profile ids")
    return sorted(({key: row[key] for key in fields} for row in profiles), key=lambda row: row["id"])


def blind_fit_input(layer_input: dict, layer: dict, baseline: dict, fresh: dict, sources: list,
                    runtime_target: dict, platform_requirements: list) -> dict:
    """Identity, requirement and equally available primary-source surfaces; no adoption, installed pin or history prose.

    Latest upstream release facts describe technical capability, not the source host's pin of record. Unknown facts
    are explicit nulls for every member and cannot be converted into an exclusion by this producer.
    """
    candidates = []
    for member in layer_input["eligible_field"]:
        repository = member["repository"]
        from source_reviews import HUB, hub_model
        model = hub_model(repository)
        primary_sources = ([repository, repository + "/tree/main", f"{HUB}/api/models/{model}"] if model else
                           [repository, repository + "/releases", repository + "/commits"])
        candidates.append({"candidate_key": member["candidate_key"], "repository": repository,
                           "evidence_key": member["evidence_key"], **unknown_upstream_facts(),
                           "primary_sources": primary_sources,
                           "requirement_fit": None})
    names = [record for document in (layer,) for field in ("candidates", "winners", "alternatives")
             for record in document.get(field) or []]
    pins = pinned_requirements(layer_input.get("requirement"), runtime_target) if layer_input["catalog"] == "us-equities" else []
    requirement = neutral_requirement(layer_input.get("requirement"), candidates + names, pins)
    return {**{key: layer_input[key] for key in ("contract_version", "catalog", "layer_id", "requirement_sha256",
                                               "platform_profiles_sha256", "field_sha256")},
             "requirement": requirement, "candidates": candidates, "pinned_requirements": pins,
             "platform_requirements": platform_requirements,
             "platform_requirements_sha256": sha256_bytes(json.dumps(
                 platform_requirements, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
            "acceptance_gates": acceptance_gates(runtime_target, candidates + names, pins)
                                 if layer_input["catalog"] == "us-equities" else []}


def unknown_upstream_facts() -> dict:
    return {"upstream_now": dict.fromkeys(UPSTREAM_FACT_FIELDS),
            "upstream_observation": {"status": "pending", "pending_reason": "not_requested",
                                     "observed_at": None, "sources": []}}


def pull_upstream_facts(repository: str) -> dict:
    """One origin-independent procedure using existing transports, with no adoption records or cached facts.

    Reference: github_freshness.py gh_api/fetch_repository and source_reviews.py hub_get/hub_review at
    798ac445307e2cd8eba6e74d7722ac0e16da02c7. GET commits without sha reads the default branch:
    https://docs.github.com/en/rest/commits/commits#list-commits
    https://docs.github.com/en/rest/repos/repos#get-a-repository
    https://docs.github.com/en/rest/releases/releases#get-the-latest-release
    https://huggingface.co/docs/huggingface_hub/package_reference/hf_api#huggingface_hub.HfApi.model_info
    """
    saved_path = sys.path[:]
    try:
        sys.path.insert(0, str(HERE.parent))
        from github_freshness import gh_api
    finally:
        sys.path[:] = saved_path
    from source_reviews import GhError, HUB, hub_get, hub_model
    from urllib.parse import quote

    record = unknown_upstream_facts()
    facts, observation = record["upstream_now"], record["upstream_observation"]
    observation["observed_at"] = datetime.now(timezone.utc).isoformat()

    def github(path):
        returned, error = gh_api(path)
        if error is not None:
            raise GhError("upstream request failed")  # never copy native stderr/account state to blind input
        return returned

    def observe(url, read, paths, first=False):
        source = {"url": url, "status": "pending", "response_json_sha256": None, "pending_reason": "api_error"}
        observation["sources"].append(source)
        try:
            returned = read()
            source["response_json_sha256"] = sha256_bytes(json.dumps(
                returned, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            source["pending_reason"] = "malformed_response"
            if first:
                if not isinstance(returned, list):
                    raise ValueError("expected a commits list")
                returned = returned[0] if returned else {}
            if not isinstance(returned, dict):
                raise ValueError("expected a metadata object")
            for key, path in paths.items():
                value = returned
                for part in path.split("."):
                    value = value.get(part) if isinstance(value, dict) else None
                allowed = (bool,) if key in ("archived", "disabled") else (str, bool) if key == "gated" else (str,)
                facts[key] = value if isinstance(value, allowed) else None
            source.update(status="observed", pending_reason=None)
        except (GhError, OSError, ValueError, TypeError):
            # Missing repositories/releases, permission failures, rate limits and malformed JSON stay unknown.
            # Transport errors are deliberately not reprinted; URL/status/hash describe the frozen observation.
            pass

    model = hub_model(repository)
    if model:
        path = f"api/models/{quote(model, safe='/')}"
        observe(f"{HUB}/{path}", lambda: hub_get(path),
                {"head_commit": "sha", "last_modified": "lastModified", "disabled": "disabled", "gated": "gated"})
    else:
        base = f"repos/{slug(repository)}"
        observe(f"https://api.github.com/{base}", lambda: github(base),
                {key: key for key in ("archived", "disabled", "pushed_at", "default_branch")})
        commits = base + "/commits?per_page=1"
        observe(f"https://api.github.com/{commits}", lambda: github(commits),
                {"head_commit": "sha", "head_committed_at": "commit.committer.date"}, first=True)
        release = base + "/releases/latest"
        observe(f"https://api.github.com/{release}", lambda: github(release),
                {"latest_release": "tag_name", "released_at": "published_at"})
    pending = any(source["status"] == "pending" for source in observation["sources"])
    observation.update(status="pending" if pending else "observed", pending_reason="source_unavailable" if pending else None)
    return record


def freeze_upstream_facts(inputs: list, pull=False) -> dict:
    """Freeze a shared observation per unique identity before any blind input is written."""
    from source_reviews import repository_key

    repositories = sorted({candidate["repository"] for row in inputs for candidate in row["fit_projection"]["candidates"]})
    snapshot = {"schema_version": 1, "mode": "api_pull" if pull else "not_requested", "repositories": {}}
    observations = {}
    for repository in repositories:
        key = repository_key(repository)  # the maintained identity also folds Hub model URL casing
        if key not in observations:
            observations[key] = pull_upstream_facts(repository) if pull else unknown_upstream_facts()
        snapshot["repositories"][repository] = observations[key]
    digest = sha256_bytes(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    for row in inputs:
        for candidate in row["fit_projection"]["candidates"]:
            candidate.update(snapshot["repositories"][candidate["repository"]])
        for target in (row, row["fit_projection"]):
            target.update(upstream_facts_ref="upstream-facts-v2.json", upstream_facts_sha256=digest)
    return snapshot


def build_layer_inputs(catalogs: dict, research_state: dict, scope: dict, freshness: dict, baseline: dict | None,
                        ledger: dict, seeds=None, absent=None, followups=None, contract_version=1,
                        record_sources=None, runtime_target=None, platform_requirements=None) -> list[dict]:
    """One input object per landscape layer, in catalog order; raises on a layer missing from the frozen scope.
    ``absent(entry)`` says whether a refuted ledger entry is refuted by absence (main() passes the ledger's
    refuted_by_absence over this checkout's retained returns); without it every refuted entry stays refuted.
    ``followups`` is join_gap_followups' first value; without it every open_gaps_followup is empty."""
    if contract_version not in (1, 2):
        raise ValueError("contract_version must be 1 or 2")
    if contract_version == 2 and not platform_requirements:
        raise ValueError("V2 requires readable neutral platform requirements bound to the frozen scope")
    followups = followups or {}
    record_sources = record_sources or {}
    research = {(row["catalog"], row["layer_id"]): row for row in research_state.get("layers") or []}
    previous = previous_by_layer(last_completed(ledger, REPOSITORY), absent)
    all_ids = [layer["layer_id"] for catalog, _ in CATALOG_FILES for layer in catalogs[catalog]["layers"]]
    duplicates = sorted({layer_id for layer_id in all_ids if all_ids.count(layer_id) > 1})
    if duplicates:
        raise ValueError(f"layer ids repeat across catalogs (inputs/<layer_id>.json would collide): {duplicates}")
    seeds = check_seeds(seeds, all_ids)
    out, missing = [], []
    for catalog, _ in CATALOG_FILES:
        baseline_rows, fresh_rows = rows_by_layer(baseline, catalog), rows_by_layer(freshness, catalog)
        for layer_index, layer in enumerate(catalogs[catalog]["layers"]):
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
                "open_gaps": [gap[:GAP_CLIP] for gap in (layer.get("open_gaps") or [])[:GAPS_SHOWN]],
                "open_gaps_followup": followups.get((catalog, layer_id), []),
                "verdict_checked_at": layer.get("checked_at"),
                "verdict_note": VERDICT_NOTE,
                "overturn_when": (layer.get("overturn_when") or "")[:600],
                "previous_sweep": previous.get((catalog, layer_id), {}),
                "known_repositories": sorted(known),
                "seeded_candidates": list(seeds.get(layer_id, [])),
            })
            if contract_version == 2:
                row = out[-1]
                row["contract_version"] = 2
                row["eligible_field"] = eligible_field(catalog, layer, baseline_rows.get(layer_id, {}), fresh, ledger,
                    seeds.get(layer_id, []), record_sources.get((catalog, layer_id), []), layer_index,
                    next((i for i, r in enumerate((baseline or {}).get(MANIFEST_SECTION[catalog]) or [])
                          if r.get("layer") == layer_id), 0),
                    next((i for i, r in enumerate(freshness.get(MANIFEST_SECTION[catalog]) or [])
                          if r.get("layer") == layer_id), 0))
                row["field_sha256"] = field_sha256(row)
                row["known_repositories"] = sorted(slug(member["repository"]) for member in row["eligible_field"])
                row["fit_projection"] = blind_fit_input(row, layer, baseline_rows.get(layer_id, {}), fresh,
                                                        record_sources.get((catalog, layer_id), []), runtime_target or {},
                                                        platform_requirements)
                row["requirement"] = row["fit_projection"]["requirement"]
                row["pinned_requirements"] = row["fit_projection"]["pinned_requirements"]
                row["acceptance_gates"] = row["fit_projection"]["acceptance_gates"]
                for key in ("platform_requirements", "platform_requirements_sha256"):
                    row[key] = row["fit_projection"][key]
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
        if not isinstance(source, dict) or set(source) - {"maintenance"} != set(SOURCE_FIELDS):
            problems.append(f"skills catalog {label}: needs exactly source_id, kind, url and pin (and optionally "
                            "maintenance)")
            continue
        source_ids.append(source["source_id"])
        if source["kind"] not in SOURCE_KINDS:
            problems.append(f"skills catalog {label}: kind {source['kind']!r} is not one of {list(SOURCE_KINDS)}")
        if not HEX40.fullmatch(str(source["pin"])):
            problems.append(f"skills catalog {label}: pin must be a 40-hex commit")
        record = source.get("maintenance")
        if "maintenance" in source and not (
                isinstance(record, dict) and sorted(record) == sorted(MAINTENANCE_FIELDS)
                and record["status"] in MAINTENANCE_STATUSES and valid_date(record["checked_at"])
                and isinstance(record["evidence"], str) and record["evidence"].strip()):
            problems.append(f"skills catalog {label}: maintenance must be {{status: one of "
                            f"{list(MAINTENANCE_STATUSES)}, checked_at: YYYY-MM-DD, evidence: the API fact}}")
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


def valid_date(value) -> bool:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return bool(DATE.fullmatch(str(value)))


def skills_scope(catalog: dict, adoption: dict, led) -> dict:
    """The frozen scope of the skills layers in saturation_ledger.py --scope's format, with the ledger's functions
    (the requirement hash is saturation_ledger.skills_requirement_sha256, which --report and --append recompute)."""
    return {"platform_profiles_sha256": led.platform_profiles_sha256(adoption),
            "requirement_sha256": {f"{SKILLS}/{task['layer_id']}": led.skills_requirement_sha256(task)
                                   for task in catalog["tasks"]}}


def excluded_names(value) -> list[str]:
    """The skill names of one adoption/skills/manifest.json excluded entry. The committed manifest states them as one
    comma-separated string ("systematic-debugging, test-driven-development"); a list is taken item by item. Each name,
    or phrase ("reddit-automation and vendor-specific packs"), is stripped and kept whole."""
    items = value if isinstance(value, list) else str(value or "").split(",")
    return [name for name in (str(item).strip() for item in items) if name]


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
            excluded.setdefault(str(entry.get("source")), set()).update(excluded_names(entry.get("skills")))
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
            # Whole text: the catalog and the manifest are this repository's reviewed files, and a cut gap or overturn
            # condition would hide part of the requirement from the workers (repository layers keep their caps).
            "installed": [{field: pinned[name][field] for field in INSTALLED_FIELDS if field in pinned[name]}
                          for name in task["installed"]],
            "sources": [dict(sources[source_id]) for source_id in task["source_ids"]],
            "open_gaps": list(task.get("open_gaps") or []),
            "overturn_when": task.get("overturn_when") or "",
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
                        help="default: manifest_ref of the saturation ledger's last completed repository sweep")
    parser.add_argument("--seeds", type=Path)
    parser.add_argument("--contract-version", type=int, choices=(1, 2), default=1,
                        help="1: unchanged current sweep; 2: prepare the future neutral repository field")
    parser.add_argument("--pull-upstream-facts", action="store_true",
                        help="V2 repository input only: freeze one uniform GitHub/Hub API pull per repository; "
                             "otherwise all blind upstream facts stay null/pending")
    parser.add_argument("--modality", choices=("repository", SKILLS), default="repository",
                        help=f"repository: the landscape catalogs' layers (default); skills: the skills-* layers of "
                             f"{SKILLS_CATALOG}")
    parser.add_argument("--skills-scope", action="store_true",
                        help="print the skills layers' frozen scope (saturation_ledger.py --scope's format) and exit")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    if args.pull_upstream_facts and (args.contract_version != 2 or args.modality != REPOSITORY or args.skills_scope):
        parser.error("--pull-upstream-facts requires --contract-version 2 and repository inputs")
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
        if args.contract_version != 1:
            parser.error("the skills modality keeps contract version 1")
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
        previous_sweep = last_completed(ledger, REPOSITORY)  # a skills sweep is neither history nor baseline
        baseline_path = args.baseline_manifest
        if baseline_path is None and previous_sweep and previous_sweep.get("manifest_ref"):
            baseline_path = repo / previous_sweep["manifest_ref"]
        catalogs = {catalog: load_json(repo / "catalogs" / "landscape" / name) for catalog, name in CATALOG_FILES}
        led = ledger_module(REPO_ROOT)  # the ledger's rules from this checkout, applied to --repo-root's files
        scope = load_json(args.scope or work / "scope.json")
        platform_requirements = None
        if args.contract_version == 2:
            adoption = load_json(repo / "adoption/manifest.json")
            if led.platform_profiles_sha256(adoption) != scope.get("platform_profiles_sha256"):
                raise ValueError("V2 platform_profiles_sha256 differs from adoption/manifest.json; refreeze the scope")
            platform_requirements = neutral_platform_requirements(adoption.get("platform_profiles"))
        documents = {}
        target_of = led.ref_resolver(lambda path: documents[path] if path in documents
                                     else documents.setdefault(path, led.load_json(repo, path)))
        gap_entries, gap_ledgers = gap_ledger_entries(repo)
        followups, gap_counts = join_gap_followups(catalogs, gap_entries)
        inputs = build_layer_inputs(
            catalogs, load_json(repo / "catalogs" / "landscape" / "research-state.json"),
            scope, load_json(args.freshness_manifest),
            load_json(baseline_path) if baseline_path else None, ledger,
            load_json(args.seeds) if args.seeds else None,
            absent=lambda entry: led.refuted_by_absence(entry, target_of), followups=followups,
            contract_version=args.contract_version,
            record_sources=field_record_sources(repo, catalogs, ledger) if args.contract_version == 2 else None,
            runtime_target=load_json(repo / "catalogs/us-equities/runtime-target.json")
                           if args.contract_version == 2 and (repo / "catalogs/us-equities/runtime-target.json").is_file()
                            else None, platform_requirements=platform_requirements)
        if args.contract_version == 2:
            upstream_facts = freeze_upstream_facts(inputs, pull=args.pull_upstream_facts)
    except (ValueError, OSError, KeyError) as error:
        print(f"build_inputs.py: {error}", file=sys.stderr)
        return 2
    (work / "inputs").mkdir(exist_ok=True)
    if args.contract_version == 2:
        write_json(work / "upstream-facts-v2.json", upstream_facts)
    layers = []
    for layer_input in inputs:
        path = work / "inputs" / f"{layer_input['layer_id']}.json"
        screen_path = work / "inputs" / f"{layer_input['layer_id']}.fit-v2.json"
        if args.contract_version == 2:
            write_json(screen_path, layer_input.pop("fit_projection"))
        write_json(path, layer_input)
        layers.append({"catalog": layer_input["catalog"], "layer_id": layer_input["layer_id"],
                       "title": layer_input["title"], "input": str(path),
                       **({"contract_version": 2, "field_sha256": layer_input["field_sha256"],
                           "fit_input": str(screen_path), "facts_input": str(screen_path)}
                          if args.contract_version == 2 else {})})
    write_json(work / "layers.json", layers)
    print(f"{len(layers)} layers; {sum(1 for x in layers if x['catalog'] == 'foundation')} foundation; "
          f"previous repository sweep {(previous_sweep or {}).get('sweep_id') or 'none'}; "
          f"baseline {baseline_path.name if baseline_path else 'none'}; seeds for "
          f"{sum(1 for x in inputs if x['seeded_candidates'])} layer(s); "
          f"gap follow-ups: {gap_counts['joined']} joined from {gap_ledgers} ledger(s), {gap_counts['dropped']} dropped "
          f"(no sealed open gap with that index and text), {gap_counts['beyond']} for gaps beyond the {GAPS_SHOWN} shown")
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
    previous_sweep = last_completed(ledger, SKILLS)  # a repository sweep is never a skills run's history
    print(f"{len(layers)} skills layers from {SKILLS_CATALOG}; previous skills sweep "
          f"{(previous_sweep or {}).get('sweep_id') or 'none'}; seeds for "
          f"{sum(1 for x in inputs if x['seeded_candidates'])} layer(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
