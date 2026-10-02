#!/usr/bin/env python3
"""Build the final catalog record of 2026-10-01: the blind GPT-6.1 Sol half of the clean-install selection, per row.

Per row of the dated new-WSL architecture edition it records the picks the blind GPT-6.1 Sol half named, the picks the
blind Claude Opus 5.5 half named (#589), how the two sets compare under the agreement rule frozen before the GPT run,
and the source host's selection of record as bookkeeping.

This record is not an install list. Nothing in it installs, accepts or authorizes a candidate, no row in it is a
default, and it schedules no comparison. The install record is the definitive manifest of the new-WSL definitive round
(#602, ``evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json``, decided in
``docs/decisions/2026-10-01-new-wsl-definitive-defaults.md``). The generator names that manifest and never reads it,
so ``--check`` does not depend on it.

It is a read-only join: it judges no candidate, changes no verdict, pins no version and records no receipt. Its fold
extends the frozen rule (``evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/agreement-rule.txt``)
in two places (``EXTENSIONS``), so its agreement classes are not the rule applied exactly as written; every row both
halves judged also carries the class the rule's text gives as written. The rule's fold attaches install and comparison
consequences to each class; this record does not carry them out. Sources:

- ``catalogs/foundation/new-wsl-architecture-20261001.json``: the 37 rows, each winner (the source host's selection
  of record, which is bookkeeping and not a merit result) with its pin, and the row's verdict;
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json``: the blind Claude half for the 20
  foundation layers and the base distribution (picks, status, critic verdict, the comparison arms it recorded);
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/selection-gpt.json`` when present: the
  blind GPT-6.1 Sol half on the same packets, criteria and prompts;
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/agreement-rule.txt``: hashed, so a change
  to the rule fails ``--check`` until the outputs are regenerated;
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/packets/``: candidate names, used only to normalize a
  pick that has no GitHub repository (the second extension);
- ``evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/facts/``: the GitHub API facts captured
  for every packet candidate before the cross-family run (latest release, last default-branch commit, archived flag,
  license as information only), attached to each pick of either half;
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
OUT_JSON = "catalogs/foundation/final-catalog-20261001.json"
OUT_MD = "docs/final-catalog-20261001.md"
# Named, never read: the install record is outside this join (no --check coupling).
INSTALL_RECORD = {
    "manifest": "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json",
    "decision": "docs/decisions/2026-10-01-new-wsl-definitive-defaults.md",
    "pull_request": 602,
}

SCOPE = ("The record of the blind GPT-6.1 Sol half of the clean-install selection of 2026-10-01 and of its comparison "
         "with the blind Claude Opus 5.5 record of the same day (#589). It is not an install list: no row in it is an "
         "installed tool or a default, a pick both halves named is agreement on source review and not an install "
         "decision, and nothing in it schedules a comparison. The install record is the definitive manifest (#602).")
MEANING = ("Per layer: the picks each blind half named, which of them both halves named and which only one named, the "
           "agreement class the generator gives (the frozen rule, extended in two places) next to the class the rule's "
           "text gives as written, and the source host's selection of record (bookkeeping; an unjudged incumbent where "
           "neither half judged the row). Evidence only: nothing here installs, accepts or authorizes a candidate, and "
           "no selection of record changes.")
EVIDENCE_CLASS = ("Source review by model judges with adversarial critics in two model families. Neither half installed "
                  "or measured a candidate, and the judges of both halves received instruction files that name some of "
                  "the candidates, so agreement on the layers of those tools is not independent evidence (decision "
                  "record, \"Blindness, and its limit\").")
FOLD_NOTE = ("The rule's fold (its sixth line) attaches install and comparison consequences to each class. This record "
             "does not carry them out: it reports what each half named and the class, and every slot's install "
             "decision is the definitive manifest's.")
QUOTED_NOTE = ("The source host's record column quotes each winner's name and pin from the edition: bookkeeping, not a "
               "merit result. Commentary inside a quoted pin, such as what the new distribution installs, is the "
               "edition's wording, not this record's.")

CLASSES = {
    "same_picks_both_recommended": "both halves named the same picks and both recommended them (agreement class "
                                   "agree)",
    "same_picks_both_compare": "both halves named the same picks and both asked for a comparison of them (agreement "
                               "class agree)",
    "same_picks_split_status": "both halves named the same picks; one recommended them and the other asked for a "
                               "comparison. The rule's text classifies this case as neither agree nor overlap; the "
                               "generator calls it overlap (first extension)",
    "some_picks_shared": "the halves share at least one pick and their pick sets differ (agreement class overlap)",
    "no_picks_shared": "the halves share no pick (agreement class differ)",
    "pending_cross_family": "only the blind Claude half judged this layer, so there is no GPT record to compare",
    "owner_lane_run_pending": "a trading layer outside the blind run of 2026-10-01: neither half judged it, and its "
                              "selection of record is an unjudged incumbent; #589 left its blind run to the trading "
                              "lane owner",
    "no_blind_record": "a cross-cutting row outside the blind run: neither half judged it, and its selection of record "
                       "is an unjudged incumbent (the source host's bookkeeping), not a merit result",
}
EXTENSIONS = {
    "equal_sets_unequal_statuses": (
        "Equal pick sets with unequal statuses. The rule's agree needs equal statuses and its overlap needs unequal "
        "sets, so the text as written leaves the case unclassified; the generator classifies it as overlap"),
    "packet_name_matching": (
        "Names matched to packet candidates. The rule normalizes a pick without a GitHub repository by its name; the "
        "generator matches the name to the packet candidate whose words it contains, which drops a role suffix such as "
        "\", primary\" or \", fallback\". Compared as written (lowercase, whitespace collapsed), names that differ by "
        "such a suffix are different picks"),
}
FIELDS = {
    "selection_of_record": "the source host's winners with their pins, quoted from the edition (bookkeeping)",
    "blind": "the blind Claude Opus 5.5 half (#589): status, critic verdict, picks with captured upstream facts, and "
             "the comparison arms it recorded",
    "cross_family": "the blind GPT-6.1 Sol half: status, critic verdict and picks with captured upstream facts",
    "agreement": "the class the generator gives: agree, overlap or differ, with the two extensions",
    "agreement_as_written": "the class the rule's text gives as written: agree, overlap, differ, or unclassified where "
                            "its definitions cover neither agree nor overlap",
    "extensions_applied": "the extensions that changed this row's class or its split of the picks",
    "pick_sets.class": "the row's evidence class (see classes)",
    "pick_sets.named_by_both": "picks both halves named",
    "pick_sets.named_by_claude_only": "picks only the blind Claude half named",
    "pick_sets.named_by_gpt_only": "picks only the blind GPT half named",
    "pick_sets.fold_comparison_set": "the set the frozen fold's comparison clause derives from the two halves, kept "
                                     "for reading them side by side; this record schedules no comparison. A Claude "
                                     "arm names a pick only by the pick's full owner/name (or full name), so an arm "
                                     "described in words and the pick it describes can both appear",
    "pick_sets.versus_record": "picks both halves named that the source host's record lacks, and record entries that "
                               "are not among them",
    "disagreement_with_record": "the blind Claude half against the source host's record",
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
    """The generator's normalization: a pick is its GitHub repository; a pick without one is its name, matched to the
    packet candidate whose words it contains (a family may reorder words or append a role such as "primary"; this
    matching is the second extension). The candidate with the most words wins, and an unmatched name stands as
    written."""
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


def written_key(pick: dict) -> str:
    """The rule's normalization as written: a pick is its GitHub repository; a pick without one is its name, lowercase
    with whitespace collapsed and nothing matched or dropped. (A GitHub URL reduces to owner/name in both readings;
    the tests check that every pick URL in the two records is a plain repository URL, where the two forms agree.)"""
    repo = github_key(pick.get("repository"))
    if repo:
        return repo
    return "name:" + " ".join((pick.get("name") or pick.get("component_id") or "").lower().split())


def display(pick: dict) -> str:
    repo = github_key(pick.get("repository"))
    return repo if repo else (pick.get("name") or "").strip()


def record_entry(winner: dict) -> dict:
    """A winner of the source host's record: name, repository and pin only. Its upstream currency stays in the edition,
    whose wording there speaks of switches and comparisons that are not this record's."""
    return {
        "name": winner.get("component_id") or winner.get("name"),
        "repository": winner.get("repository"),
        "pin": winner.get("pin"),
    }


def pick_entry(pick: dict, facts: dict) -> dict:
    return {"name": pick.get("name"), "repository": pick.get("repository"),
            "upstream": facts.get(github_key(pick.get("repository")) or "")}


def blind_entry(row: dict, facts: dict) -> dict:
    return {
        "status": row["status"],
        "critic_verdict": row.get("critic_verdict"),
        "picks": [pick_entry(p, facts) for p in row.get("selection") or []],
        "comparison_arms": list(row.get("comparison_arms") or []),
    }


def gpt_entry(row: dict, facts: dict) -> dict:
    return {
        "status": row["status"],
        "critic_verdict": row.get("critic_verdict"),
        "picks": [pick_entry(p, facts) for p in row.get("picks") or []],
    }


def agreement(c_keys: set, c_status: str, g_keys: set, g_status: str) -> str:
    """The generator's class: the frozen classes, with equal sets and unequal statuses counted as overlap (the first
    extension)."""
    if c_keys == g_keys and c_status == g_status:
        return "agree"
    if c_keys & g_keys:
        return "overlap"
    return "differ"


def agreement_as_written(c_keys: set, c_status: str, g_keys: set, g_status: str) -> str:
    """The class the rule's text gives as written; keys must come from written_key."""
    if c_keys == g_keys:
        return "agree" if c_status == g_status else "unclassified"
    if c_keys & g_keys:
        return "overlap"
    return "differ"


def shape(c_keys: set, g_keys: set) -> tuple:
    return c_keys == g_keys, len(c_keys & g_keys), len(c_keys), len(g_keys)


def extensions_applied(c_picks, c_status, g_picks, g_status) -> list[str]:
    c_keys, g_keys = {p["key"] for p in c_picks}, {p["key"] for p in g_picks}
    used = set()
    if c_keys == g_keys and c_status != g_status:
        used.add("equal_sets_unequal_statuses")
    if shape(c_keys, g_keys) != shape({p["written"] for p in c_picks}, {p["written"] for p in g_picks}):
        used.add("packet_name_matching")
    return [e for e in EXTENSIONS if e in used]


def classify(c_keys: set, c_status: str, g_keys: set, g_status: str) -> str:
    if c_keys == g_keys:
        if c_status != g_status:
            return "same_picks_split_status"
        return "same_picks_both_recommended" if c_status == "recommended" else "same_picks_both_compare"
    return "some_picks_shared" if c_keys & g_keys else "no_picks_shared"


def mentioned(label: str, arms: list[str]) -> bool:
    """True when one of the Claude half's arm descriptions names this pick by its full owner/name (for a pick without
    a GitHub repository, its full name): lowercase, whitespace collapsed, matched as one token that no letter, digit,
    dot, hyphen or underscore extends on either side. "mattpocock/skills" is not named by "trailofbits/skills", and
    "mksglu/context-mode" is not named by "Context Mode"."""
    target = " ".join((label or "").lower().split())
    if not target:
        return False
    pattern = re.compile(r"(?<![a-z0-9._-])" + re.escape(target) + r"(?![a-z0-9_-]|\.[a-z0-9])")
    return any(pattern.search(" ".join(arm.lower().split())) for arm in arms)


def fold(c_picks, c_keys, c_status, c_arms, g_picks, g_keys, g_status, labels=None):
    """Split the two halves' picks and derive the set the frozen fold's comparison clause names.

    Returns (class, named by both, named by the Claude half only, named by the GPT half only, fold comparison set) as
    display strings. The fold comparison set follows the clause's text: nothing where both halves recommended the same
    picks; the Claude half's recorded arms plus every pick of either half where both asked for a comparison of the same
    picks; the Claude half's recorded arms plus every pick only one half named where the halves overlap (including the
    first extension's equal sets); every pick of either half where they share none. A pick an arm already names by its
    full owner/name is not added again. The set is the rule's derivation, kept for reading the halves side by side; no
    comparison is scheduled from it."""
    if labels is None:
        labels = {}
        for pick in list(c_picks) + list(g_picks):
            labels.setdefault(pick["key"], pick["label"])

    def arms_with(base, keys):
        arms = list(base)
        for key in sorted(keys):
            if not mentioned(labels[key], base):
                arms.append(labels[key])
        return arms

    status = classify(c_keys, c_status, g_keys, g_status)
    both = [labels[k] for k in sorted(c_keys & g_keys)]
    c_only = [labels[k] for k in sorted(c_keys - g_keys)]
    g_only = [labels[k] for k in sorted(g_keys - c_keys)]
    if status == "same_picks_both_recommended":
        fold_set = []
    elif status == "same_picks_both_compare":
        fold_set = arms_with(c_arms, c_keys | g_keys)
    elif status == "no_picks_shared":
        fold_set = arms_with([], c_keys | g_keys)
    else:
        fold_set = arms_with(c_arms, c_keys ^ g_keys)
    return status, both, c_only, g_only, fold_set


def empty_pick_sets(status: str, claude_only=None) -> dict:
    return {"class": status, "named_by_both": [], "named_by_claude_only": list(claude_only or []),
            "named_by_gpt_only": [], "fold_comparison_set": [], "versus_record": None}


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
        out = {
            "layer_id": layer_id, "catalog": row["catalog"], "title": row["title"], "owner_lane": row["owner_lane"],
            "selection_of_record": record, "record_verdict": row["verdict"],
            "record_evidence_class": row["evidence_class"],
            "blind": None, "cross_family": None,
            "agreement": None, "agreement_as_written": None, "extensions_applied": [],
            "pick_sets": None, "disagreement_with_record": None, "grand_list": None,
        }
        if layer_id in grand_layers:
            g = grand_layers[layer_id]
            out["grand_list"] = {k: g.get(k) for k in ("decision", "verdict_status", "independent_review", "open_gaps",
                                                       "open_executable_now_gaps")}
        b = blind.get(layer_id)
        if b is None:
            out["pick_sets"] = empty_pick_sets("owner_lane_run_pending" if row["catalog"] == "us-equities"
                                               else "no_blind_record")
            rows.append(out)
            continue
        out["blind"] = blind_entry(b, facts)
        c_status = "compare" if b["status"] == "compare" else "recommended"
        c_picks = [{"key": pick_key(p, candidates), "written": written_key(p), "label": display(p)}
                   for p in b.get("selection") or []]
        c_keys = {p["key"] for p in c_picks}
        c_arms = list(b.get("comparison_arms") or [])
        out["disagreement_with_record"] = {
            "blind_only": sorted(display(p) for p in b.get("selection") or [] if pick_key(p, candidates) not in record_keys),
            "record_only": sorted(k for k in record_keys if k not in c_keys),
        }
        x = gpt.get(layer_id)
        if x is None:
            out["pick_sets"] = empty_pick_sets("pending_cross_family", sorted(p["label"] for p in c_picks))
            rows.append(out)
            continue
        out["cross_family"] = gpt_entry(x, facts)
        g_status = "compare" if x["status"] == "compare" else "recommended"
        g_picks = [{"key": pick_key(p, candidates), "written": written_key(p), "label": display(p)}
                   for p in x.get("picks") or []]
        g_keys = {p["key"] for p in g_picks}
        # A name matched to a packet candidate is shown as the candidate's name, without either half's role suffix.
        by_candidate = {"name:" + name_key(c): c for c in candidates}
        labels = {}
        for p in c_picks + g_picks:
            labels.setdefault(p["key"], by_candidate.get(p["key"], p["label"]))
        out["agreement"] = agreement(c_keys, c_status, g_keys, g_status)
        out["agreement_as_written"] = agreement_as_written({p["written"] for p in c_picks}, c_status,
                                                           {p["written"] for p in g_picks}, g_status)
        out["extensions_applied"] = extensions_applied(c_picks, c_status, g_picks, g_status)
        status, both, c_only, g_only, fold_set = fold(c_picks, c_keys, c_status, c_arms, g_picks, g_keys, g_status,
                                                      labels)
        shared = c_keys & g_keys
        out["pick_sets"] = {
            "class": status, "named_by_both": both, "named_by_claude_only": c_only, "named_by_gpt_only": g_only,
            "fold_comparison_set": fold_set,
            "versus_record": {
                "named_by_both_not_in_record": sorted(labels[k] for k in shared - record_keys),
                "record_not_named_by_both": sorted(k for k in record_keys if k not in shared),
            },
        }
        rows.append(out)

    def tally(values):
        counts = {}
        for value in values:
            if value:
                counts[value] = counts.get(value, 0) + 1
        return dict(sorted(counts.items()))

    inputs = {rel: sha256(rel) for rel in (EDITION, SELECTION, GRAND_LIST) + ((CROSS_FAMILY,) if cross else ())}
    rule_sha = sha256(AGREEMENT_RULE) if (ROOT / AGREEMENT_RULE).is_file() else None
    if rule_sha:
        inputs[AGREEMENT_RULE] = rule_sha
    if facts_digest():
        inputs[FACTS + "/"] = facts_digest()
    return {
        "schema_version": 2,
        "kind": "final_catalog",
        "date_utc": edition["edition"]["date_utc"],
        "scope": SCOPE,
        "install_record": INSTALL_RECORD,
        "meaning": MEANING,
        "evidence_class": EVIDENCE_CLASS,
        "classes": CLASSES,
        "fields": FIELDS,
        "agreement_rule": {"path": AGREEMENT_RULE, "sha256": rule_sha, "extensions": EXTENSIONS, "fold": FOLD_NOTE},
        "cross_family": ({k: cross.get(k) for k in ("family", "run", "contamination_audit")} if cross else
                         {"status": "not_run"}),
        "inputs": inputs,
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "by_catalog": {c: sum(1 for r in rows if r["catalog"] == c) for c in ("foundation", "us-equities", "cross")},
            "class": tally(r["pick_sets"]["class"] for r in rows),
            "agreement": tally(r["agreement"] for r in rows),
            "agreement_as_written": tally(r["agreement_as_written"] for r in rows),
            "extensions_applied": {e: [r["layer_id"] for r in rows if e in r["extensions_applied"]] for e in EXTENSIONS},
            "rows_where_blind_differs_from_record": sum(
                1 for r in rows if r["disagreement_with_record"] and (r["disagreement_with_record"]["blind_only"]
                                                                     or r["disagreement_with_record"]["record_only"])),
            "rows_with_picks_named_by_both": sum(1 for r in rows if r["pick_sets"]["named_by_both"]),
            "rows_where_picks_named_by_both_differ_from_record": sum(
                1 for r in rows if r["pick_sets"]["versus_record"]
                and (r["pick_sets"]["versus_record"]["named_by_both_not_in_record"]
                     or r["pick_sets"]["versus_record"]["record_not_named_by_both"])),
        },
    }


def md_cell(value) -> str:
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def half_cell(half) -> str:
    if half is None:
        return "—"
    verdict = f" ({half['critic_verdict']})" if half.get("critic_verdict") else ""
    return f"{half['status']}{verdict}: " + md_cell([display(p) for p in half["picks"]])


def agreement_cell(row: dict) -> str:
    if not row["agreement"]:
        return "—"
    if row["agreement_as_written"] == row["agreement"]:
        return row["agreement"]
    return f"{row['agreement']} (as written: {row['agreement_as_written']})"


def counts(mapping: dict) -> str:
    return ", ".join(f"`{k}` {v}" for k, v in mapping.items()) if mapping else "none"


def render_md(data: dict) -> str:
    s = data["summary"]
    install = data["install_record"]
    rule = data["agreement_rule"]
    lines = [
        f"# Final catalog ({data['date_utc']}): the blind GPT half of the clean-install selection and its comparison "
        "with the Claude record",
        "",
        "**This is not an install list.** It records which picks each blind model family named for each row of the "
        "2026-10-01 architecture edition and how the two sets compare under the agreement rule frozen before the GPT "
        "run. No row here is an installed tool or a default; a pick both halves named is agreement on source review, "
        "not an install decision; and nothing here schedules a comparison. The install record is the definitive "
        f"manifest (#{install['pull_request']}): `{install['manifest']}`, decided in `{install['decision']}`.",
        "",
        "Generated by `scripts/final_catalog.py` from the dated new-WSL architecture edition, the blind Claude Opus 5.5 "
        "record, the blind GPT-6.1 Sol record, the agreement rule and the new-host grand list. Do not edit by hand; run "
        "`python3 scripts/final_catalog.py --write`. It judges nothing, and no selection of record changes here. "
        + QUOTED_NOTE + " Evidence class: " + data["evidence_class"],
        "",
        f"Rows: {s['rows']} ({s['by_catalog']['foundation']} foundation, {s['by_catalog']['us-equities']} trading, "
        f"{s['by_catalog']['cross']} cross-cutting). Class: {counts(s['class'])}. Agreement as generated: "
        f"{counts(s['agreement'])}; under the rule's text as written: {counts(s['agreement_as_written'])}. Rows where "
        f"both halves named at least one pick: {s['rows_with_picks_named_by_both']}, of which "
        f"{s['rows_where_picks_named_by_both_differ_from_record']} differ from the source host's record. Rows where "
        f"the blind Claude record differs from that record: {s['rows_where_blind_differs_from_record']}.",
        "",
        "## The agreement rule and its two extensions",
        "",
        f"The rule frozen before the GPT run is `{rule['path']}` (sha256 `{rule['sha256'] or 'missing'}`). It "
        "normalizes a pick to its repository URL, or by its name where it has no GitHub URL; compares the Claude picks "
        "after the critics with the GPT picks after the GPT critic; gives each half the status compare or recommended; "
        "and defines three classes: agree (equal pick sets and equal statuses), overlap (at least one shared pick, "
        "sets not equal) and differ (no shared pick). The generator's fold extends that text in two places, so its "
        "classes are not the rule applied exactly as written:",
        "",
    ]
    for number, (key, text) in enumerate(rule["extensions"].items(), start=1):
        layers = s["extensions_applied"].get(key) or []
        lines.append(f"{number}. {text}. Rows it changes: " + (", ".join(f"`{x}`" for x in layers) or "none") + ".")
    lines += ["", "Each judged row shows both classes in its Agreement column. " + rule["fold"], "", "## Class meanings",
              ""]
    for key, text in data["classes"].items():
        lines.append(f"- `{key}`: {text}.")
    titles = (("foundation", "Foundation layers"), ("cross", "Cross-cutting rows"),
              ("us-equities", "Trading layers (owner: trading lane)"))
    for catalog, title in titles:
        lines += ["", f"## {title}", "",
                  "| Layer | Class | Agreement | Named by both halves | Named by the Claude half only | Named by the GPT "
                  "half only | Claude Opus 5.5 half | GPT-6.1 Sol half | Source host's record (edition text) |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in (r for r in data["rows"] if r["catalog"] == catalog):
            sets = r["pick_sets"]
            record = md_cell([f"{github_key(w['repository']) or w['name']} {w['pin']}" for w in r["selection_of_record"]])
            if r["blind"] is None:
                record = "unjudged incumbent: " + record
            lines.append(
                f"| {md_cell(r['title'])} | `{sets['class']}` | {agreement_cell(r)} "
                f"| {md_cell(sets['named_by_both'])} | {md_cell(sets['named_by_claude_only'])} "
                f"| {md_cell(sets['named_by_gpt_only'])} | {half_cell(r['blind'])} | {half_cell(r['cross_family'])} "
                f"| {record} |")
    lines += ["", "## Inputs", "", "| File | sha256 |", "| --- | --- |"]
    lines += [f"| `{rel}` | `{digest}` |" for rel, digest in data["inputs"].items() if rel != GRAND_LIST]
    lines += ["", f"The grand-list context (`{GRAND_LIST}`: each layer's decision and open-gap counts), each half's "
              "comparison arms and the fold comparison set are in the JSON form only."]
    lines += ["", "## How to update this page", "",
              "Generated, not hand-edited. After an edition update, a change to either half's record, the agreement "
              "rule or the captured facts, run `python3 scripts/final_catalog.py --write` and commit the outputs. A move "
              "of the grand list alone shows as drift in `--check` and is refreshed with the next write. `--check` runs "
              "in CI."]
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
        print(json.dumps({"status": "written", "rows": len(data["rows"]), "class": data["summary"]["class"]}))
        return 0
    if not (ROOT / OUT_JSON).is_file() or not (ROOT / OUT_MD).is_file():
        print("missing: run python3 scripts/final_catalog.py --write", file=sys.stderr)
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
