#!/usr/bin/env python3
"""Merge the working files, GitHub freshness, and a review-lanes record into a
dated SOTA-convergence manifest with the exact key layout of
``catalogs/sota-convergence/manifest-20260922.json``.

No network access. All host-path fragments are removed from the manifest's
decoded string values (``sanitize_value``, walking dict/list/str, applied
*before* JSON serialization -- see its docstring for why sanitizing already-
serialized JSON text is unsafe) before the object is dumped, re-parsed with
``json.loads`` to prove the result is valid JSON, and leak-checked
(``assert_no_leak``); the writer refuses to write if a leak survives.

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
``2.0.0.dev0 (c6fbd1c)``), its pin is not an OS-distribution package pin
(e.g. ``255.4-1ubuntu8.17`` for systemd -- a distro package string compared
against an upstream tag is a category error even when the project's own
repository happens to be on GitHub), and its parsed leading version is lower
than GitHub's latest release/tag. Non-GitHub repositories, OS-package pins
(matched by an ``-NubuntuM`` / ``-Ndeb`` / ``+debN`` pin suffix, or by
component/entry id via ``--os-package-ids``, default ``["systemd"]``) and
``.devN`` commit-pinned components are excluded from the comparison rather
than silently counted as "behind" or "not behind" -- see ``classify_pin``. A
version merely *annotated* with a commit fingerprint (e.g.
``0.25.0 (702f4814...)``) is still compared normally: the fingerprint
documents provenance, it does not make the release incomparable.

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
# Capturing form used to derive a normalized owner/repo slug (see
# github_repo_slug below); stops at the next '/', '#' or '?' so a
# release/tree/tag suffix or a trailing slash never becomes part of the repo
# name.
GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#?]+)")
# A ".devN" pin (optionally annotated with "@ <commit>" or "(<commit>)") tracks a
# working commit, not a tagged release; its numeric prefix is not comparable to
# GitHub's latest release/tag. A version number merely *annotated* with a commit
# fingerprint (e.g. "0.25.0 (702f4814...)") is still a real, comparable release.
DEV_PIN_RE = re.compile(r"\.dev\d*\b", re.IGNORECASE)
# An OS-distribution package pin (Ubuntu/Debian style, e.g. "255.4-1ubuntu8.17"
# or "1.2.3-1deb11u1" / "1.2.3+deb11u1") is a distro package string, not an
# upstream release; it is never comparable to a GitHub tag even when the
# project's own repository field is a real GitHub URL (e.g. systemd/systemd).
OS_PIN_RE = re.compile(r"-\d+ubuntu\d*|-\d+deb\d*(?:u\d+)?|\+deb\d+u?\d*", re.IGNORECASE)
DEFAULT_OS_PACKAGE_IDS = ("systemd",)
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


def classify_pin(pin, repository, upstream_latest, component_id=None, os_package_ids=DEFAULT_OS_PACKAGE_IDS):
    """Return {"behind": bool, "excluded": bool, "reason": str|None}.

    ``os_package_ids`` is an explicit allow-list of component/entry ids
    (default ``("systemd",)``) that are always treated as OS-package pins,
    regardless of pin format, in addition to the ``OS_PIN_RE`` regex match on
    the pin string itself (Ubuntu/Debian suffix style)."""
    if not repository or not GITHUB_RE.match(repository):
        return {"behind": False, "excluded": True, "reason": "non_github_or_os_package"}
    if (component_id in (os_package_ids or ())) or (pin and OS_PIN_RE.search(pin)):
        return {"behind": False, "excluded": True, "reason": "os_package_pin"}
    if pin and DEV_PIN_RE.search(pin):
        return {"behind": False, "excluded": True, "reason": "commit_pinned"}
    pin_version = parse_version(pin)
    upstream_version = parse_version(upstream_latest)
    if pin_version is None or upstream_version is None:
        return {"behind": False, "excluded": False, "reason": "unversioned"}
    return {"behind": pin_version < upstream_version, "excluded": False, "reason": None}


def github_repo_slug(url: str):
    """Normalized 'owner/repo' slug for a GitHub URL.

    The capturing pattern stops at the next '/', '#' or '?', so a
    '/releases/tag/vX', '/tree/...' or trailing-slash alias for the same
    repository already resolves to the same owner/repo pair; '.git' is
    stripped and the result is lower-cased so a canonical URL and any of
    those alias forms normalize identically. Mirrors
    ``github_freshness.github_slug`` (kept independent here so this module
    has no import-time dependency on that sibling script -- both files are
    also loaded standalone, by file path, in tests/test_sota_convergence.py).
    """
    match = GITHUB_URL_RE.match(url or "")
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    if repo.lower().endswith(".git"):
        repo = repo[: -len(".git")]
    return f"{owner}/{repo}".lower()


def _repositories_by_slug(repositories: dict) -> dict:
    """slug -> freshness record, built from each record's own ``slug`` field
    when present (set by github_freshness.py) and otherwise derived from the
    dict key URL itself. First-seen wins, so this is deterministic for a
    fixed input dict."""
    index = {}
    for url, record in (repositories or {}).items():
        slug = None
        if isinstance(record, dict):
            slug = record.get("slug")
        slug = (slug or github_repo_slug(url) or "").lower() or None
        if slug and slug not in index:
            index[slug] = record
    return index


def repository_known(repository, repositories: dict) -> bool:
    """True when ``repository`` (by exact URL or by normalized GitHub slug)
    has a freshness record in ``repositories``."""
    repositories = repositories or {}
    if repository in repositories:
        return True
    slug = github_repo_slug(repository)
    return bool(slug and slug in _repositories_by_slug(repositories))


def compute_upstream(repository, repositories: dict) -> dict:
    repositories = repositories or {}
    record = repositories.get(repository)
    if record is None:
        slug = github_repo_slug(repository)
        if slug:
            record = _repositories_by_slug(repositories).get(slug)
    record = record or {}
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

def build_baseline_foundation(foundation_layers: dict, repositories: dict,
                               os_package_ids=DEFAULT_OS_PACKAGE_IDS) -> list:
    rows = []
    for layer in foundation_layers.get("layers", []):
        components = []
        for component in layer.get("components", []):
            repository = component.get("repository")
            pin = component.get("version") or component.get("pin")
            upstream = compute_upstream(repository, repositories)
            classification = classify_pin(pin, repository, upstream.get("latest"),
                                           component_id=component["id"], os_package_ids=os_package_ids)
            components.append({
                "id": component["id"], "repository": repository, "pin": pin,
                "upstream": upstream, "behind": classification["behind"],
                "excluded": classification["excluded"], "exclusion_reason": classification["reason"],
            })
        rows.append({"layer": layer["layer_id"], "title": layer.get("title", layer["layer_id"]),
                      "components": components})
    return rows


SELECTED_TRADING_DECISIONS = ("default", "conditional")


def build_baseline_trading(trading_by_layer: dict, repositories: dict,
                            os_package_ids=DEFAULT_OS_PACKAGE_IDS) -> list:
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
            classification = classify_pin(pin, repository, upstream.get("latest"),
                                           component_id=entry["id"], os_package_ids=os_package_ids)
            row = {
                "id": entry["id"], "repository": repository, "decision": entry.get("decision"),
                "pin": pin, "upstream": upstream, "behind": classification["behind"],
                "excluded": classification["excluded"], "exclusion_reason": classification["reason"],
            }
            # evidence_level (source_review / native_proven / ...) is the
            # execution classification; it is distinct from review_status
            # (a selection/pin confirmation) -- see recipes/sota-convergence-
            # practice.md's "Evidence classes". Carried through only when the
            # source catalogs/us-equities/*.json card sets it
            # (extract_layers.py already copies it verbatim into
            # trading-catalog.json / trading-by-layer.json).
            if entry.get("evidence_level") is not None:
                row["evidence_level"] = entry["evidence_level"]
            entries.append(row)
        rows.append({"layer": layer_id, "entries": entries})
    return rows


# ---------------------------------------------------------------------------
# Disposition and sanitization
# ---------------------------------------------------------------------------

PROPOSABLE_LABELS = frozenset({"not_adopted", "keep_but_compare", "targeted_candidate"})


def disposition(label, survives):
    """The lane proposes a label; two refuters try to break the proposal. A
    surviving not_adopted stays not adopted - survival never upgrades a label.

    ``label`` is validated against the fixed proposable set first: anything
    else (``None``, a typo, or a label a lane invented) is normalized to
    ``"unlabelled"`` before the survives logic runs, so an unrecognised label
    can never pass through unchanged into a promotable-looking value."""
    if label not in PROPOSABLE_LABELS:
        label = "unlabelled"
    if survives is None:
        return f"{label}_unverified"
    if not survives:
        return "refuted_" + label
    return {
        "not_adopted": "not_adopted_confirmed",
        "keep_but_compare": "keep_but_compare",
        "targeted_candidate": "targeted_candidate",
    }.get(label, "unlabelled")


# Host-path forms to redact. Patterns and coverage (Linux, macOS, Windows
# drive-letter and bare "\Users\" forms) mirror the "personal home path" /
# "Windows user path" checks in scripts/validate.py's PRIVATE_CONTENT list
# (adapted here, without validate.py's "/home/example" placeholder
# exemption, since this sanitizer's own contract -- see
# test_sanitize_removes_host_paths below -- redacts every /home/ occurrence,
# including any that happen to say "example").
HOST_PATH_PATTERNS = (
    re.compile(r"/home/[^\s\"']+"),
    re.compile(r"/Users/[^\s\"']+", re.IGNORECASE),
    re.compile(r"(?:[A-Za-z]:)?\\+Users\\+[^\s\"']+", re.IGNORECASE),
)
LEAK_MARKERS = ("/home/", "APCA")


def sanitize(text: str) -> str:
    for pattern in HOST_PATH_PATTERNS:
        text = pattern.sub("<host-path>", text)
    return text


def sanitize_value(value):
    """Recursively redact host paths from decoded values -- dict/list/str --
    walking the Python object *before* it is JSON-serialized. Applying
    ``sanitize`` to the already-serialized JSON text instead (the previous
    approach) can corrupt the output: a value like
    ``read "/home/example/file.json" before publishing`` is escaped by
    json.dumps as ``read \\"/home/example/file.json\\" before publishing``,
    and the host-path regex's character class does not exclude a backslash,
    so it consumes the backslash that escapes the closing quote and leaves
    an unescaped ``"`` behind -- invalid JSON that ``assert_no_leak`` alone
    would not catch. Sanitizing the raw Python string first means there are
    no JSON escape sequences to misread."""
    if isinstance(value, str):
        return sanitize(value)
    if isinstance(value, dict):
        return {key: sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value


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
                evidence = list(selected.get("evidence", []))
                if verdict is not None:
                    survives = verdict.get("survives")
                    vote_count = len(verdict.get("votes") or [])
                    if survives is False:
                        # The lane's proposed status change was refuted: the
                        # original selection/pin is confirmed as-is.
                        status_value = ("confirmed_default" if status_value in ("demotion_proposed", "unmaintained_signal")
                                         else "confirmed_pin")
                        notes[key].append(f"{selected['status']} proposed by {lane['lane']} lane, "
                                           "refuted by adversarial verification")
                    elif survives is None:
                        # Unknown verdict (no refuter vote, or a null in the
                        # lanes.json record): never treat this as a
                        # completed refutation -- that would silently upgrade
                        # an unreviewed status (e.g. "unmaintained_signal")
                        # to "confirmed_default". Keep it unverified instead.
                        status_value = f"{status_value}_unverified"
                        evidence.append(
                            f"{vote_count} adversarial vote(s) returned for {lane['lane']} lane's "
                            f"{selected['status']} proposal; verification outcome unknown (survives=null)"
                        )
                    # survives is True: the lane's proposed status change
                    # itself survived verification -- keep status_value as
                    # the lane proposed it (no note; this never upgrades
                    # beyond what the lane itself proposed).
                status[key] = {"status": status_value, "evidence": evidence,
                                "note": selected.get("note"), "lane": lane["lane"]}
                # Optional lane fields, carried through only when the lane's
                # selected item actually sets them -- never invented here.
                # build_manifest() copies these from ``status[key]`` onto the
                # merged components[]/entries[] the same way it already
                # copies "note"/"evidence".
                if "why_selected" in selected:
                    status[key]["why_selected"] = selected["why_selected"]
                if "comparison_that_would_overturn" in selected:
                    status[key]["comparison_that_would_overturn"] = selected["comparison_that_would_overturn"]
            for alt in layer.get("alternatives_keep_but_compare", []):
                alts[layer_id].append({**alt, "lane": lane["lane"]})
            for candidate in layer.get("new_candidates", []):
                verdict = verdicts.get((layer_id, candidate["repository"], "new_candidate"))
                survives = verdict["survives"] if verdict else None
                upstream_now = (compute_upstream(candidate["repository"], repositories)
                                 if repository_known(candidate["repository"], repositories)
                                 else candidate.get("upstream_now"))
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
# Deterministic ordering (so two runs against unchanged inputs, or the same
# lanes.json content with proposals/candidates written in a different order,
# diff cleanly)
# ---------------------------------------------------------------------------

# Rank used only as the primary sort key; ties (or rows without a "decision"
# field, e.g. foundation components) fall back to "id" and are otherwise
# untouched -- this does not change which rows are selected, only the order
# they are written in.
DECISION_RANK = {"default": 0, "conditional": 1}

# Candidates are grouped by disposition maturity: promotable-looking labels
# first, then their unverified form, then refuted, with an unknown/future
# disposition placed last (rather than raising) so a rerun still diffs
# cleanly instead of erroring.
CANDIDATE_DISPOSITION_RANK = {
    "targeted_candidate": 0,
    "keep_but_compare": 1,
    "not_adopted_confirmed": 2,
    "targeted_candidate_unverified": 3,
    "keep_but_compare_unverified": 4,
    "not_adopted_unverified": 5,
    "unlabelled_unverified": 6,
    "refuted_targeted_candidate": 7,
    "refuted_keep_but_compare": 8,
    "refuted_not_adopted": 9,
    "refuted_unlabelled": 10,
    "unlabelled": 11,
}


def row_item_sort_key(item):
    return (DECISION_RANK.get(item.get("decision"), 0), item["id"])


def candidate_sort_key(candidate):
    return (CANDIDATE_DISPOSITION_RANK.get(candidate["disposition"], 99), candidate.get("repository") or "")


def sorted_candidates(cands, layer_id):
    return sorted(cands.get(layer_id, []), key=candidate_sort_key)


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------

def format_observation_window(freshness_doc: dict) -> str:
    """Describe *when the freshness data was actually observed*, from the
    per-record ``observed_at`` timestamps github_freshness.py retains --
    never from ``generated_at`` (checkpoint/write time), which a resumed run
    rewrites on every invocation even when zero repositories were re-fetched
    (see github_freshness.build_document's ``fetched_this_run`` /
    ``retained_from_prior_runs`` counts and ``observation_window``).

    Prefers the top-level ``observation_window`` (present on any freshness
    file written by the current github_freshness.py); falls back to scanning
    ``repositories[*].observed_at`` directly for an older-format freshness
    file that predates that top-level field but still carries per-record
    dates."""
    window = freshness_doc.get("observation_window") or {}
    min_at, max_at = window.get("min"), window.get("max")
    if not (min_at and max_at):
        observed_dates = sorted(
            rec.get("observed_at") for rec in (freshness_doc.get("repositories") or {}).values()
            if isinstance(rec, dict) and rec.get("observed_at")
        )
        if observed_dates:
            min_at, max_at = observed_dates[0], observed_dates[-1]
    if not (min_at and max_at):
        return "observed at an unrecorded time (no per-record observed_at in the freshness snapshot)"
    if min_at[:19] == max_at[:19]:
        return f"observed {min_at[:19]}Z"
    return f"observed {min_at[:19]}Z to {max_at[:19]}Z"


def build_manifest(*, checked_at, manifest_id, scope, foundation_layers, trading_by_layer,
                    freshness_doc, lanes_doc, reconciliations, taxonomy,
                    os_package_ids=DEFAULT_OS_PACKAGE_IDS) -> dict:
    repositories = freshness_doc.get("repositories", {})
    baseline_foundation = build_baseline_foundation(foundation_layers, repositories, os_package_ids=os_package_ids)
    baseline_trading = build_baseline_trading(trading_by_layer, repositories, os_package_ids=os_package_ids)
    status, notes, alts, cands, gaps, calls, limits = merge_lanes(lanes_doc, repositories)

    # Fall back to deriving retained_from_prior_runs from count - fetched_this_run
    # for an older-format freshness file that predates these top-level fields
    # (mirrors format_observation_window's fallback), rather than reporting a
    # misleading 0 retained alongside a nonzero repository count.
    fetched_this_run = freshness_doc.get("fetched_this_run", 0)
    if "retained_from_prior_runs" in freshness_doc:
        retained_from_prior_runs = freshness_doc["retained_from_prior_runs"]
    else:
        retained_from_prior_runs = max(freshness_doc.get("count", 0) - fetched_this_run, 0)

    manifest = {
        "schema_version": 1, "id": manifest_id, "checked_at": checked_at, "scope": scope,
        "method": {
            "baseline": "extract_layers.py over catalogs/foundation/{manifest,decisions}.json, "
                        "manifests/stack.json and the catalogs/us-equities layer files, "
                        "consolidated into 12 trading layers (taxonomy below)",
            "freshness": f"authenticated GitHub REST metadata for {freshness_doc.get('count', 0)} "
                         f"repositories, {format_observation_window(freshness_doc)} "
                         f"(fetched_this_run={fetched_this_run}, "
                         f"retained_from_prior_runs={retained_from_prior_runs}): "
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
            component_row = {
                "id": component["id"], "repository": component["repository"], "pin": component["pin"],
                "upstream": component["upstream"], "pin_behind_upstream": component["behind"],
                "review_status": lane_status.get("status", "not_individually_reviewed"),
                "review_note": lane_status.get("note"),
                "evidence": lane_status.get("evidence", []) + notes.get((layer_id, component["repository"]), []),
            }
            # Optional lane fields: carried through only when the lane's
            # selected item actually set them on status[key] -- never invented.
            for field in ("why_selected", "comparison_that_would_overturn"):
                if field in lane_status:
                    component_row[field] = lane_status[field]
            components.append(component_row)
        components.sort(key=row_item_sort_key)
        manifest["foundation"].append({
            "layer": layer_id, "title": row["title"], "components": components,
            "alternatives_keep_but_compare": alts.get(layer_id, []),
            "candidates": sorted_candidates(cands, layer_id),
            "open_gaps": sorted(set(gaps.get(layer_id, []))),
        })

    for row in baseline_trading:
        layer_id = row["layer"]
        entries = []
        for entry in row["entries"]:
            lane_status = status.get((layer_id, entry["repository"]), {})
            row_entry = {
                "id": entry["id"], "repository": entry["repository"], "decision": entry["decision"],
                "pin": entry["pin"], "upstream": entry["upstream"], "pin_behind_upstream": entry["behind"],
                "review_status": lane_status.get("status", "not_individually_reviewed"),
                "review_note": lane_status.get("note"),
                "evidence": lane_status.get("evidence", []) + notes.get((layer_id, entry["repository"]), []),
            }
            if "evidence_level" in entry:
                row_entry["evidence_level"] = entry["evidence_level"]
            # Optional lane fields: carried through only when the lane's
            # selected item actually set them on status[key] -- never invented.
            for field in ("why_selected", "comparison_that_would_overturn"):
                if field in lane_status:
                    row_entry[field] = lane_status[field]
            entries.append(row_entry)
        entries.sort(key=row_item_sort_key)
        manifest["trading"].append({
            "layer": layer_id, "entries": entries,
            "alternatives_keep_but_compare": alts.get(layer_id, []),
            "candidates": sorted_candidates(cands, layer_id),
            "open_gaps": sorted(set(gaps.get(layer_id, []))),
        })

    known_layers = {row["layer"] for row in manifest["foundation"]} | {row["layer"] for row in manifest["trading"]}
    for layer_id in sorted(set(cands) | set(gaps) | set(alts)):
        if layer_id not in known_layers:
            manifest["trading"].append({
                "layer": layer_id, "entries": [],
                "alternatives_keep_but_compare": alts.get(layer_id, []),
                "candidates": sorted_candidates(cands, layer_id),
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
            and not str(component["review_status"]).endswith("_unverified")
        ),
        "pins_behind_upstream": sum(
            1 for row in all_rows for component in all_components(row) if component["pin_behind_upstream"]
        ),
        "candidates_total": sum(len(row["candidates"]) for row in all_rows),
        "pins_behind_upstream_unique_components": len(pins_behind_unique),
        "pins_behind_note": "components with a commit-pinned version (a parenthetical hash), a "
                             "non-GitHub repository, or an OS-distribution package pin (matched by "
                             "an -Nubuntu/-Ndeb/+debN pin suffix, or by id via --os-package-ids, "
                             "e.g. systemd even though its own repository is on GitHub) are excluded "
                             "from the pin-vs-upstream comparison rather than counted either way",
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
    parser.add_argument("--os-package-ids", nargs="*", default=list(DEFAULT_OS_PACKAGE_IDS),
                         help="Component/entry ids always excluded from pin-vs-upstream as OS-distribution "
                              "packages, regardless of pin format (default: %(default)s).")
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
        taxonomy=taxonomy, os_package_ids=tuple(args.os_package_ids),
    )

    # Sanitize the decoded object *before* serialization (see sanitize_value's
    # docstring for why sanitizing the serialized text instead can produce
    # invalid JSON), then prove the serialized result is valid JSON before
    # the leak check and the write.
    text = json.dumps(sanitize_value(manifest), indent=1)
    json.loads(text)
    assert_no_leak(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
