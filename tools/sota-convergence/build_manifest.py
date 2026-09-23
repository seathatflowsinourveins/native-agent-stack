#!/usr/bin/env python3
"""Merge the working files, GitHub freshness, and a review-lanes record into a
dated SOTA-convergence manifest with the exact key layout of
``catalogs/sota-convergence/manifest-20260922.json`` (``schema_version, id,
checked_at, scope, method, taxonomy, foundation, trading, lane_groupings,
citation_review, critic, lane_calls, lane_limits, reconciliations, counts``),
plus ``unmatched_lane_items`` (after ``lane_groupings``): every lane
``selected[]`` item at a foundation/trading layer that lands on no card row
(see ``collect_unmatched_lane_items``), published instead of silently
dropped.
``citation_review`` (G6) is an optional overlay of an independent citation
review's findings onto the rows they name -- see ``apply_citation_review``;
always present, ``{"general": []}`` when ``--citation-review`` is not given.
``trading[]``
rows are exactly the taxonomy layer ids from
``trading-by-layer.json#/taxonomy``, in taxonomy order; a review-lane layer id
outside the foundation/taxonomy baseline (e.g. a "beyond" lane's own grouping
like ``awesome-list-convergence``) is never folded into ``trading[]`` -- it is
carried verbatim into ``lane_groupings`` instead, see ``build_manifest``.

No network access. All host-path fragments, and any bare session UUID, are
removed from the manifest's decoded string values (``sanitize_value``,
walking dict/list/str, applied *before* JSON serialization -- see its
docstring for why sanitizing already-serialized JSON text is unsafe) before
the object is dumped, re-parsed with ``json.loads`` to prove the result is
valid JSON, and leak-checked (``assert_no_leak``); the writer refuses to
write if a leak survives.

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
documents provenance, it does not make the release incomparable. A row whose
pin was not compared (any exclusion above, or ``unversioned``) publishes
``pin_behind_upstream: null`` with ``pin_comparison: "not_compared"`` and a
``pin_comparison_reason``, never a definite false; a lane's
``pin_behind_upstream`` status on an OS-package pin is published as
``distro_managed`` (see ``reconcile_status_with_pin``). A tag-only upstream
whose tag is not version-shaped is flagged under ``upstream.latest_flag``
instead of being published as ``upstream.latest``.

Lane entries join cards on ``(layer, repo_join_key(repository))`` -- the
normalized GitHub slug -- so a ``/releases/tag/...`` or ``/tree/...`` card URL
keeps the lane review of the plain URL. A cited path inside the catalog
checkout (``--checkout-root``, default: this repository) is published
repository-relative; only paths outside it are redacted.

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
# The catalog repository checkout this tool runs from: the default
# --checkout-root, whose paths are published repository-relative.
REPO_ROOT = HERE.parents[1]

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


def repo_join_key(repository):
    """Join key for a repository string: its normalized GitHub slug when it
    is a GitHub URL, else the string itself. Every lane-entry-to-card join
    (the status index, a selected item's verdict lookup, the per-layer
    repository-share count) uses this, so a card whose repository is a
    ``/releases/tag/...`` or ``/tree/...`` alias still meets the lane entry
    that cited the plain repository URL (2026-09-23 citation review, the two
    high tooling findings: 15 lane reviews were silently dropped by an
    exact-string join)."""
    return github_repo_slug(repository) or repository


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


LATEST_TAG_NOT_A_RELEASE = "tag_listing_only_not_version_shaped"


def compute_upstream(repository, repositories: dict) -> dict:
    repositories = repositories or {}
    record = repositories.get(repository)
    if record is None:
        slug = github_repo_slug(repository)
        if slug:
            record = _repositories_by_slug(repositories).get(slug)
    record = record or {}
    release = record.get("latest_release") or {}
    latest = release.get("tag") or record.get("latest_tag")
    flagged_tag = None
    if not release.get("tag") and latest and parse_version(latest) is None:
        # No release channel, and the tag-listing fallback is not
        # version-shaped: github_freshness.py reads repos/{slug}/tags?per_page=1,
        # which returns the first tag in the API's name order, not the newest
        # release (postgres/postgres yields "release-6-3", a historical sort
        # artifact; 2026-09-23 citation review). Flag it instead of
        # publishing it as upstream.latest.
        flagged_tag, latest = latest, None
    upstream = {
        "latest": latest,
        "released_at": (release.get("published_at") or "")[:10] or None,
        "prerelease": release.get("prerelease"),
        "pushed_at": (record.get("pushed_at") or "")[:10] or None,
        "stars": record.get("stargazers_count"),
        "license": record.get("license"),
        "archived": record.get("archived"),
        "renamed_to": record.get("renamed_to"),
    }
    if flagged_tag is not None:
        upstream["latest_flag"] = {"tag": flagged_tag, "reason": LATEST_TAG_NOT_A_RELEASE}
    return upstream


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
    candidate/alternative mechanism, never by being catalogued.

    Rows are built from ``taxonomy`` (in its own key order, i.e. the order
    ``trading-by-layer.json#/taxonomy`` lists its layers in), not from
    ``layers`` (whose key set is normally identical but is not the
    authoritative one): this guarantees ``trading[]`` rows are exactly the
    12 taxonomy layer ids, one row per id even when a layer happens to have
    zero selected entries, so scripts/landscape.py's exact-coverage check
    over trading[].layer never sees an extra or a missing id.

    ``layers`` and ``taxonomy`` key sets are only "normally identical", not
    guaranteed identical, so a layer id present in ``layers`` but absent
    from ``taxonomy`` is checked explicitly: if any such orphan id holds a
    selected ("default" or "conditional") entry, that entry would silently
    vanish -- it is not a lane-named id, so lane_groupings (sourced from the
    lanes document, not from trading_by_layer) cannot recover it either.
    Raises ``ValueError`` naming the offending layer/entry ids rather than
    dropping them; an orphan layer holding only non-selected decisions
    (never promoted into a manifest row from any layer) does not raise."""
    layers = trading_by_layer.get("layers", {})
    taxonomy_ids = set(trading_by_layer.get("taxonomy", {}))
    orphan_selected = [
        (layer_id, entry.get("id"))
        for layer_id in set(layers) - taxonomy_ids
        for entry in layers.get(layer_id, [])
        if entry.get("decision") in SELECTED_TRADING_DECISIONS
    ]
    if orphan_selected:
        raise ValueError(
            "trading_by_layer['layers'] has selected (default/conditional) "
            "entries under layer id(s) absent from trading_by_layer['taxonomy'], "
            "which build_baseline_trading only iterates: "
            f"{sorted(orphan_selected)}. These are not lane-named, so "
            "lane_groupings cannot recover them either -- add the layer id to "
            "taxonomy, or change/relabel the entries, before rebuilding."
        )
    rows = []
    for layer_id in trading_by_layer.get("taxonomy", {}):
        entries = []
        for entry in layers.get(layer_id, []):
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
# Bare session-id detector: duplicated (not imported -- this module is
# loaded standalone by file path in tests/test_sota_convergence.py's
# load_module, with no import-time dependency on scripts/) from
# scripts/validate.py's PRIVATE_CONTENT "local session identifier" pattern
# (scripts/validate.py line 27). A UUID's dash-grouped 8-4-4-4-12 hex shape
# never matches a 40-hex git SHA, a 64-hex sha256 digest, or a short hex id
# (e.g. a 7-char commit abbreviation) -- none of those carry the dashes.
SESSION_UUID_RE = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.IGNORECASE)

# A /tmp/<anything> path chain that contains a session-scoped directory -- a
# UUID segment, a "claude-<uid>" segment (Claude Code's per-session scratch
# directory naming), or a "...scratchpad..." segment -- is redacted the same
# way a /home or /Users path already is. A bare /tmp path with none of those
# markers is not inherently private and is left alone.
TMP_SESSION_PATH_RE = re.compile(
    r"/tmp/[^\s\"']*(?:" + SESSION_UUID_RE.pattern + r"|claude-\d+|scratchpad)[^\s\"']*",
    re.IGNORECASE,
)

HOST_PATH_PATTERNS = (
    re.compile(r"/home/[^\s\"']+"),
    re.compile(r"/Users/[^\s\"']+", re.IGNORECASE),
    re.compile(r"(?:[A-Za-z]:)?\\+Users\\+[^\s\"']+", re.IGNORECASE),
)
LEAK_MARKERS = ("/home/", "APCA")


def _path_basename(path_part: str) -> str:
    """Last non-empty '/'- or '\\'-separated segment of ``path_part``, so a
    redacted host path still names the file/pointer target a citation
    refers to, instead of losing it entirely (see G5 -- a bare
    ``<host-path>`` token made 223 evidence citations in a real manifest
    unresolvable: the reader can no longer tell which of hundreds of files
    under the redacted directory a citation named)."""
    normalized = path_part.replace("\\", "/")
    segments = [segment for segment in normalized.split("/") if segment]
    return segments[-1] if segments else path_part


# Trailing prose punctuation the host-path patterns' ``[^\s"']+`` class
# swallows after a bare directory (e.g. "worktree <checkout-dir>),"); it is
# split off only to recognise the checkout root itself, then re-appended.
_TRAILING_PROSE_PUNCTUATION = ".,;:)]}"
CHECKOUT_ROOT_TOKEN = "<checkout>"


def _host_path_sub(work_dir: str | None, checkout_roots=()):
    """Return a ``re.sub`` replacement callable that redacts the directory
    portion of a matched host path but keeps its basename and any trailing
    ``#/json/pointer`` verbatim -- ``<work-dir>/basename[#pointer]`` when the
    match falls inside the private ``--work-dir`` (or the shared parent of
    the individually-provided foundation/trading/freshness paths), else the
    generic ``<host-path>/basename[#pointer]``. /tmp session-scratch paths
    and bare session UUIDs are redacted separately, in full, by
    ``sanitize`` -- unaffected by this (see its docstring).

    A match inside one of ``checkout_roots`` (a checkout of this catalog
    repository) instead keeps its full repository-relative path
    (``manifests/stack.json``, ``blueprints/us-equities/broad-universe/README.md``),
    since only the checkout location, not the in-repository path, is
    private: a basename alone collapsed distinct same-named files (two
    different ``README.md`` citations) into one unresolvable token
    (2026-09-23 citation review). The checkout root itself becomes
    ``<checkout>``. The work dir takes precedence when both contain a path."""
    normalized_work_dir = work_dir.replace("\\", "/").rstrip("/") if work_dir else None
    normalized_roots = sorted(
        {root.replace("\\", "/").rstrip("/") for root in (checkout_roots or ()) if root},
        key=len, reverse=True,
    )

    def _replace(match: re.Match) -> str:
        full = match.group(0)
        path_part, has_pointer, pointer = full.partition("#")
        suffix = f"#{pointer}" if has_pointer else ""
        normalized_path = path_part.replace("\\", "/")
        segments = [segment for segment in normalized_path.split("/") if segment]
        # A home-directory root ("/home/<user>", "/Users/<user>") has no file
        # basename worth keeping: its last segment IS the username, which the
        # redaction exists to remove, so it collapses to the bare token.
        if len(segments) <= 2 and segments[:1] in (["home"], ["Users"]):
            return "<host-path>" + suffix
        in_work_dir = bool(normalized_work_dir) and (
            normalized_path == normalized_work_dir or normalized_path.startswith(normalized_work_dir + "/"))
        if not in_work_dir:
            for root in normalized_roots:
                if normalized_path.startswith(root + "/"):
                    relative = normalized_path[len(root) + 1:]
                    if relative.strip("/"):
                        return relative + suffix
                    return CHECKOUT_ROOT_TOKEN + suffix
                stripped = normalized_path.rstrip(_TRAILING_PROSE_PUNCTUATION)
                if stripped == root:
                    return CHECKOUT_ROOT_TOKEN + normalized_path[len(stripped):] + suffix
        basename = _path_basename(path_part)
        token = "<work-dir>" if in_work_dir else "<host-path>"
        return f"{token}/{basename}" + suffix

    return _replace


def sanitize(text: str, work_dir: str | None = None, checkout_roots=()) -> str:
    """Redact host-path fragments from ``text``.

    A ``/tmp`` session-scratch path (a UUID, ``claude-<uid>`` or
    ``scratchpad`` segment -- see ``TMP_SESSION_PATH_RE``) is scrubbed to a
    bare ``<host-path>`` token, unchanged from before this function grew
    basename-preservation (G5): a session-scoped scratch path is not a
    stable citation target the way a file under the review's own working
    directory is, so there is no basename worth keeping. A Linux/macOS/
    Windows *user* host path (``HOST_PATH_PATTERNS``) instead keeps its
    basename and any ``#/json/pointer`` suffix via ``_host_path_sub``, using
    ``<work-dir>`` when ``work_dir`` is given and the path falls inside it.
    A bare session UUID left over outside any path (e.g. quoted directly in
    lane prose) is scrubbed last, to a distinct ``<session-id>`` token.
    A path inside one of ``checkout_roots`` keeps its repository-relative
    path instead (see ``_host_path_sub``); the default ``()`` keeps the
    previous behaviour for callers that pass none."""
    text = TMP_SESSION_PATH_RE.sub("<host-path>", text)
    replace = _host_path_sub(work_dir, checkout_roots)
    for pattern in HOST_PATH_PATTERNS:
        text = pattern.sub(replace, text)
    text = SESSION_UUID_RE.sub("<session-id>", text)
    return text


def sanitize_value(value, work_dir: str | None = None, checkout_roots=()):
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
        return sanitize(value, work_dir=work_dir, checkout_roots=checkout_roots)
    if isinstance(value, dict):
        return {key: sanitize_value(item, work_dir=work_dir, checkout_roots=checkout_roots)
                for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item, work_dir=work_dir, checkout_roots=checkout_roots) for item in value]
    return value


def assert_no_leak(text: str) -> None:
    for marker in LEAK_MARKERS:
        if marker in text:
            raise LeakDetected(f"sanitized manifest still contains {marker!r}")
    # Defense in depth for the same pattern scripts/validate.py line 27
    # rejects a publication on: refuse if any bare session UUID survived
    # sanitize()'s scrub, whatever text carried it in.
    if SESSION_UUID_RE.search(text):
        raise LeakDetected("sanitized manifest still contains a bare session UUID")
    # Defense in depth, symmetric with the UUID check above: sanitize()
    # redacts a /tmp session-scoped path on any of TMP_SESSION_PATH_RE's
    # three markers (a UUID segment, a "claude-<uid>" segment, or a
    # "...scratchpad..." segment), but only the UUID marker was re-checked
    # here -- so a claude-<uid>/scratchpad path carrying no UUID would pass
    # this refusal gate even if sanitize() were bypassed or narrowed. Refuse
    # on the same pattern sanitize() itself scrubs.
    if TMP_SESSION_PATH_RE.search(text):
        raise LeakDetected("sanitized manifest still contains a session-scoped /tmp path")


# ---------------------------------------------------------------------------
# Lane merge
# ---------------------------------------------------------------------------

# A lane's selected[] item is split in merge_lanes into the merged status
# fields (repository/status/evidence/note, which this tool reconciles with the
# adversarial verdicts) and ``lane_item``: every other field the lane set,
# copied verbatim and never invented (why_selected,
# comparison_that_would_overturn, role, catalog_id, catalog_pin, upstream_now,
# and any future field). Where it lands depends on the row:
#   - a foundation components[] or trading entries[] row already carries the
#     baseline pin/upstream computed from manifests/stack.json and
#     github-freshness.json, so it takes only ROW_LANE_FIELDS -- a second,
#     lane-copied pin/upstream representation next to the baseline one would
#     be a conflicting duplicate;
#   - a lane_groupings[] selected row has no baseline to fall back on (the
#     grouping id is a lane's own, e.g. the "beyond" lane's
#     unmaintained-reference-material), so it takes the whole lane_item.
MERGED_SELECTED_KEYS = ("repository", "status", "evidence", "note")
ROW_LANE_FIELDS = ("why_selected", "comparison_that_would_overturn")


# A refuted "demotion_proposed"/"unmaintained_signal" proposal must not be
# resolved to a hardcoded "confirmed_default" -- that promotes a component
# past its own governing baseline decision (G2; a conditional-selection
# component like agentskills was observed promoted this way). merge_lanes
# has no baseline (foundation-layers.json decisions / trading entry.decision)
# to resolve the real class from, so it emits this marker with the original
# proposed status recorded in the entry's own note/evidence; build_manifest()
# resolves it per row kind, see resolve_refuted_marker.
REFUTED_TO_CONFIRMED_MARKER = "refuted_to_confirmed"


def _entry_verified(verdict) -> bool:
    """True only for "a matching proposal with survives true or false"
    (G1's own phrasing) -- a proposal record with an unknown outcome
    (``survives: null``, e.g. no refuter voted) exists but did not verify
    anything, so it must not outrank an entry with no proposal at all."""
    return verdict is not None and verdict.get("survives") is not None


def merge_lanes(lanes_doc: dict, repositories: dict):
    """Returns (status, notes, alts, cands, gaps, calls, limits) indexed as in
    the original prototype: status/notes by (layer, repository), the rest by
    layer.

    ``status[(layer_id, repository)]`` keeps every lane's contribution for
    that key (G1: two lanes independently selecting the same layer/repository
    -- e.g. a "foundation" lane's and a "beyond" lane's own headroom row --
    is a real observed shape, not an error) under ``status[key]["entries"]``,
    one dict per contributing lane:
    ``{lane, catalog_id, status, verified, evidence, note, lane_item}``.
    ``build_manifest()`` picks the entry that lands on a foundation/trading/
    lane_groupings row by a documented deterministic precedence
    (``select_row_review``) and preserves every other lane's entry verbatim
    under that row's ``other_lane_reviews``; nothing here decides a winner
    or drops an entry -- that needs row-kind context (foundation vs. trading
    vs. lane_groupings) this function does not have.

    ``status[key]`` also still carries the flat ``status``/``evidence``/
    ``note``/``lane``/``lane_item`` fields the previous single-entry
    prototype returned (mirroring the *first* recorded entry for that key):
    every existing lanes.json fixture has at most one lane per
    (layer, repository), so this is exactly the old behaviour in every case
    that previously worked; it exists only so direct callers of this
    function (as opposed to build_manifest(), which reads ``entries``) keep
    working unchanged on a single-lane key."""
    status = {}
    notes = defaultdict(list)
    alts = defaultdict(list)
    cands = defaultdict(list)
    gaps = defaultdict(list)
    calls = {}
    limits = {}
    for lane in lanes_doc.get("lanes", []):
        lane_name = lane["lane"]
        result = lane["result"]
        calls[lane_name] = result.get("calls")
        limits[lane_name] = result.get("limits")
        proposals = lane.get("proposals", [])
        # Exact (layer, repository, kind) match, as before, plus a
        # (repository, kind) index (G3): a lane's adversarial verdict is
        # itself about the repository and the proposed status, not about a
        # particular layer -- when the *same* lane proposes the *same*
        # status for the *same* repository in a second layer with no
        # layer-specific verdict of its own, the first verdict applies
        # there too (sorted by layer id, so a rerun is deterministic even if
        # more than one other layer happens to carry a verdict).
        # Verdicts are joined to selected items and candidates on
        # repo_join_key (normalized slug), not the exact URL string, so a
        # proposal citing the plain URL still meets a selected item or
        # candidate citing a release/tree alias of it, and vice versa.
        verdicts_exact = {(p["layer"], repo_join_key(p["repository"]), p["kind"]): p for p in proposals}
        verdicts_by_repo_kind = defaultdict(list)
        for p in proposals:
            verdicts_by_repo_kind[(repo_join_key(p["repository"]), p["kind"])].append((p["layer"], p))
        for layer in result.get("layers", []):
            layer_id = layer["layer_id"]
            for selected in layer.get("selected", []):
                repository = selected["repository"]
                # The returned status index stays keyed by the exact
                # (layer, repository) string for direct callers;
                # build_manifest() re-indexes it by repo_join_key
                # (index_status_by_join_key) before joining it to cards.
                key = (layer_id, repository)
                status_orig = selected["status"]
                verdict = verdicts_exact.get((layer_id, repo_join_key(repository), status_orig))
                shared_from = None
                if verdict is None:
                    shared = sorted(verdicts_by_repo_kind.get((repo_join_key(repository), status_orig), []),
                                     key=lambda pair: pair[0])
                    if shared:
                        shared_from, verdict = shared[0]
                status_value = status_orig
                evidence = list(selected.get("evidence", []))
                if verdict is not None:
                    survives = verdict.get("survives")
                    vote_count = len(verdict.get("votes") or [])
                    if survives is False:
                        # The lane's proposed status change was refuted: the
                        # original selection/pin is confirmed as-is. A
                        # demotion/unmaintained-signal refutation cannot be
                        # resolved to a concrete confirmed_* class here (see
                        # REFUTED_TO_CONFIRMED_MARKER) -- everything else
                        # (e.g. a refuted pin_behind_upstream dismissal)
                        # keeps the previous "confirmed_pin" resolution,
                        # which needs no baseline to be correct.
                        status_value = (REFUTED_TO_CONFIRMED_MARKER
                                         if status_value in ("demotion_proposed", "unmaintained_signal")
                                         else "confirmed_pin")
                        refuted_note = (f"{status_orig} proposed by {lane_name} lane, "
                                        "refuted by adversarial verification")
                        notes[key].append(refuted_note)
                        evidence.append(refuted_note)
                    elif survives is None:
                        # Unknown verdict (no refuter vote, or a null in the
                        # lanes.json record): never treat this as a
                        # completed refutation -- that would silently upgrade
                        # an unreviewed status (e.g. "unmaintained_signal")
                        # to "confirmed_default". Keep it unverified instead.
                        status_value = f"{status_value}_unverified"
                        evidence.append(
                            f"{vote_count} adversarial vote(s) returned for {lane_name} lane's "
                            f"{status_orig} proposal; verification outcome unknown (survives=null)"
                        )
                    # survives is True: the lane's proposed status change
                    # itself survived verification -- keep status_value as
                    # the lane proposed it (no note; this never upgrades
                    # beyond what the lane itself proposed).
                    if shared_from is not None:
                        evidence.append(f"verdict shared from layer {shared_from}")
                entry = {
                    "lane": lane_name,
                    # The adversarial outcome of this item's matching
                    # proposal (True/False/None); None also when the lane
                    # made no proposal for it (then "verified" is False).
                    "survives": verdict.get("survives") if verdict is not None else None,
                    # The exact repository string this lane cited, kept so a
                    # lane_groupings row joined on repo_join_key still
                    # publishes a URL the lane actually wrote.
                    "repository": repository,
                    # G4: the lane's own card identity, when it set one --
                    # distinguishes two components/entries that share one
                    # repository in one layer (e.g. an execution-broker
                    # "alpaca-py" card and its sibling "data-alpaca-py"
                    # card). Also still carried through generically inside
                    # lane_item below, since it is not one of
                    # MERGED_SELECTED_KEYS.
                    "catalog_id": selected.get("catalog_id"),
                    "status": status_value,
                    "verified": _entry_verified(verdict),
                    "evidence": evidence,
                    "note": selected.get("note"),
                    # Every other field the lane set on this selected item,
                    # verbatim and never invented; build_manifest() decides
                    # per row kind which of them land (ROW_LANE_FIELDS on
                    # taxonomy rows, all of them on lane_groupings rows).
                    "lane_item": {
                        field: value for field, value in selected.items() if field not in MERGED_SELECTED_KEYS
                    },
                }
                bucket = status.setdefault(key, {"entries": []})
                bucket["entries"].append(entry)
                if "status" not in bucket:
                    bucket["status"] = entry["status"]
                    bucket["evidence"] = entry["evidence"]
                    bucket["note"] = entry["note"]
                    bucket["lane"] = entry["lane"]
                    bucket["lane_item"] = entry["lane_item"]
            for alt in layer.get("alternatives_keep_but_compare", []):
                alts[layer_id].append({**alt, "lane": lane_name})
            for candidate in layer.get("new_candidates", []):
                verdict = verdicts_exact.get((layer_id, repo_join_key(candidate["repository"]), "new_candidate"))
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
                    "lane": lane_name,
                })
            for gap in layer.get("open_gaps", []):
                gaps[layer_id].append(gap)
    return status, notes, alts, cands, gaps, calls, limits


# ---------------------------------------------------------------------------
# Row-level lane precedence (G1), catalog-id matching (G4) and the
# refuted-to-confirmed marker resolution (G2)
# ---------------------------------------------------------------------------

def resolve_refuted_marker(status_value, *, row_kind, selection=None, decision=None):
    """Resolve ``REFUTED_TO_CONFIRMED_MARKER`` to the concrete class the row
    would carry absent the (refuted) demotion/unmaintained-signal proposal --
    the component/entry's own governing baseline decision, never upgraded
    past it (G2). Any other status value passes through unchanged.

    - ``row_kind="foundation"``: ``selection`` is the governing
      foundation-layers.json decision's ``selection`` for this component
      (``default`` -> ``confirmed_default``, ``conditional`` ->
      ``confirmed_conditional``, anything else, e.g. ``optional`` ->
      ``confirmed_selected``).
    - ``row_kind="trading"``: ``decision`` is the entry's own
      trading-by-layer.json ``decision``, mapped the same way.
    - ``row_kind="lane_groupings"`` (or anything else): there is no baseline
      to resolve from -- a lane_groupings row is the lane's own grouping,
      not a catalog selection -- so it always resolves to
      ``confirmed_as_selected``.
    """
    if status_value != REFUTED_TO_CONFIRMED_MARKER:
        return status_value
    if row_kind == "foundation":
        return {"default": "confirmed_default", "conditional": "confirmed_conditional"}.get(
            selection, "confirmed_selected")
    if row_kind == "trading":
        return {"default": "confirmed_default", "conditional": "confirmed_conditional"}.get(
            decision, "confirmed_selected")
    return "confirmed_as_selected"


def select_row_review(entries, *, owning_lane=None):
    """Pick the one entry (of possibly several lanes' entries matched to the
    same row) that supplies a row's review_status/review_note/evidence/
    lane_item, by G1's documented, deterministic precedence:

    (a) an entry that was adversarially verified (``entry["verified"]``,
        i.e. a matching proposal with ``survives`` true or false) beats an
        unverified one;
    (b) among equals, the lane that owns the catalog (``owning_lane`` --
        the foundation lane for a foundation row, the trading lane for a
        trading row, ``None``/no owner for a lane_groupings row) beats any
        other lane;
    (c) tie -> lexical lane name.

    Returns ``(chosen, others)``; ``others`` is every other entry, in the
    same precedence order, for the row's ``other_lane_reviews``. Nothing is
    dropped -- every entry passed in is chosen or returned in ``others``."""
    def sort_key(entry):
        verified_rank = 0 if entry["verified"] else 1
        owner_rank = 0 if owning_lane and entry["lane"] == owning_lane else 1
        return (verified_rank, owner_rank, entry["lane"])

    ordered = sorted(entries, key=sort_key)
    return ordered[0], ordered[1:]


def match_lane_entries(entries, *, card_id):
    """G4: match a card's lane entries by ``catalog_id`` first, falling back
    to every entry with no ``catalog_id`` set (which applies to every card
    sharing that repository/layer, since it named none of them specifically).
    Returns ``(matched, matched_by_repository_only)``."""
    by_id = [entry for entry in entries if entry["catalog_id"] == card_id]
    if by_id:
        return by_id, False
    by_repository = [entry for entry in entries if entry["catalog_id"] is None]
    return by_repository, bool(by_repository)


def other_lane_review(entry, *, row_kind, selection=None, decision=None):
    return {
        "lane": entry["lane"],
        "status": resolve_refuted_marker(entry["status"], row_kind=row_kind, selection=selection, decision=decision),
        "evidence": entry["evidence"],
        "note": entry["note"],
        "lane_item": entry["lane_item"],
    }


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


# Restrictiveness rank used only to resolve foundation_decision_selection_map
# when more than one decision in a layer names the same component (see its
# docstring) -- lower rank wins, i.e. the *weakest* confirmed_* class
# resolve_refuted_marker would map it to. A selection outside this map
# (typo, or a future label) ranks the same as "optional": resolve_refuted_
# marker's own "anything else" branch already maps both to the same
# confirmed_selected class, so treating them identically here changes
# nothing about the resolved output.
SELECTION_RESTRICTIVENESS_RANK = {"optional": 0, "conditional": 1, "default": 2}


def foundation_decision_selection_map(foundation_layers: dict) -> dict:
    """``(layer_id, component_id) -> selection`` from every
    foundation-layers.json decision (``default``/``conditional``/``optional``/
    ...). Used only to resolve ``REFUTED_TO_CONFIRMED_MARKER`` (G2) to a
    component's own governing baseline class, never past it.

    A component named by more than one decision in the same layer resolves
    to the MOST RESTRICTIVE selection among all decisions naming it
    (``SELECTION_RESTRICTIVENESS_RANK``: ``optional`` < ``conditional`` <
    ``default``), never simply the first one listed in ``decisions[]``
    order -- the previous first-listed-wins rule (via ``dict.setdefault``)
    could silently resolve a refuted demotion to ``confirmed_default`` when
    a stricter co-occurring ``conditional`` decision also named the same
    component, purely because that decision happened to be listed second.
    No foundation-layers.json decision set observed so far actually
    disagrees this way (every set checked so far names a component from
    only one decision, or from decisions that already agree), so this was a
    latent defect, not one triggered by the current data -- but the rule is
    still wrong on its own terms and must not depend on decisions[] order."""
    selection_map = {}
    ranks = {}
    for layer in foundation_layers.get("layers", []):
        layer_id = layer.get("layer_id")
        for decision in layer.get("decisions", []):
            selection = decision.get("selection")
            rank = SELECTION_RESTRICTIVENESS_RANK.get(selection, 0)
            for component_id in decision.get("component_ids", []):
                key = (layer_id, component_id)
                if key not in ranks or rank < ranks[key]:
                    ranks[key] = rank
                    selection_map[key] = selection
    return selection_map


def index_status_by_join_key(status: dict) -> dict:
    """Re-index merge_lanes' exact-string ``status[(layer, repository)]`` by
    ``(layer, repo_join_key(repository))``, concatenating the entries of
    every exact key that normalizes to the same slug (in the status dict's
    own insertion order, so the result is deterministic for a fixed
    lanes.json). This is the index every lane-entry-to-card and
    lane_groupings join reads; an exact-string join silently dropped the lane
    review of any card whose repository carried a /releases/tag/ or /tree/
    suffix while the lane cited the plain URL."""
    index = {}
    for (layer_id, repository), bucket in status.items():
        joined = index.setdefault((layer_id, repo_join_key(repository)), {"entries": []})
        joined["entries"].extend(bucket["entries"])
    return index


def _repository_share_counts(cards) -> Counter:
    return Counter(repo_join_key(card["repository"]) for card in cards)


# Pin-comparison states published on every foundation/trading row. A pin the
# generator could not compare (classify_pin reason commit_pinned,
# os_package_pin, non_github_or_os_package or unversioned) is published as
# pin_behind_upstream=None with pin_comparison="not_compared" and the reason,
# never as a definite False (2026-09-23 citation review, tooling finding on
# ECC/claude-code-templates).
PIN_COMPARED = "compared"
PIN_NOT_COMPARED = "not_compared"


def pin_comparison_fields(classification: dict) -> dict:
    """``pin_behind_upstream``/``pin_comparison``[/``pin_comparison_reason``]
    for a row, from a ``classify_pin`` result."""
    if classification["excluded"] or classification["reason"] is not None:
        return {"pin_behind_upstream": None, "pin_comparison": PIN_NOT_COMPARED,
                "pin_comparison_reason": classification["reason"]}
    return {"pin_behind_upstream": classification["behind"], "pin_comparison": PIN_COMPARED}


# A lane's pin_behind_upstream status on a row whose pin is an
# OS-distribution package (classify_pin reason os_package_pin) compares a
# distro package string with an upstream release tag -- the category error
# the pin rule already excludes. Publishing it as review_status next to a
# not_compared pin contradicts the row's own pin state (2026-09-23 citation
# review, systemd finding), so it is published as DISTRO_MANAGED_STATUS
# instead, the lane's original status kept in the row's evidence.
DISTRO_MANAGED_STATUS = "distro_managed"
PIN_BEHIND_STATUSES = ("pin_behind_upstream", "pin_behind_upstream_unverified")
# Any other contradiction between a lane's pin claim and the row's own
# computed pin fields (2026-09-23 critic-gap recheck: phoenix pin_behind_upstream
# with pin_behind_upstream false, lean-alpaca and inspect-ai pin_behind_upstream
# on a not_compared pin, opensandbox confirmed_conditional with
# pin_behind_upstream true) is published as PIN_STATUS_DISPUTED_STATUS: the
# generator does not pick a side, the lane's claim stays in the row evidence
# and in ``disputed_lane_status``.
PIN_STATUS_DISPUTED_STATUS = "pin_status_disputed"
UNVERIFIED_SUFFIX = "_unverified"


def _unverified_suffix(status_value) -> str:
    return UNVERIFIED_SUFFIX if str(status_value).endswith(UNVERIFIED_SUFFIX) else ""


def lane_status_asserts_current_pin(lane_status) -> bool:
    """True when a lane's own selected[] status (before the refuted-marker
    resolution) states the pin as current: a lane-returned ``confirmed_*``
    status (the lane would have said ``pin_behind_upstream`` otherwise) or a
    ``confirmed_pin`` from a refuted pin_behind_upstream proposal. A
    ``REFUTED_TO_CONFIRMED_MARKER`` (a refuted demotion/unmaintained signal)
    confirms only the selection and makes no pin claim."""
    return str(lane_status or "").startswith("confirmed")


def reconcile_status_with_pin(status_value, pin_fields: dict, lane_status=None, lane=None):
    """Return ``(status, note)``: ``status`` never contradicts the row's own
    pin state; ``note`` (or None) records a remapping in the row evidence.

    ``lane_status`` is the lane's raw status before
    ``resolve_refuted_marker`` (default: ``status_value``). The row's pin
    state is read only when ``pin_fields`` carries ``pin_behind_upstream``:

    - a pin_behind_upstream status on an OS-package pin -> ``distro_managed``;
    - a pin_behind_upstream status on a row whose computed
      ``pin_behind_upstream`` is not true (false, or null for a pin that was
      not compared) -> ``pin_status_disputed``;
    - a lane status asserting the pin as current
      (``lane_status_asserts_current_pin``) on a row whose computed
      ``pin_behind_upstream`` is true -> ``pin_status_disputed``.

    The ``_unverified`` suffix is kept in every mapping."""
    lane_status = status_value if lane_status is None else lane_status
    suffix = _unverified_suffix(status_value)
    if (pin_fields.get("pin_comparison_reason") == "os_package_pin"
            and status_value in PIN_BEHIND_STATUSES):
        mapped = DISTRO_MANAGED_STATUS + status_value[len("pin_behind_upstream"):]
        return mapped, (f"lane status {status_value} published as {mapped}: an OS-distribution "
                        "package pin is not compared with upstream release tags")
    if "pin_behind_upstream" not in pin_fields:
        return status_value, None
    behind = pin_fields["pin_behind_upstream"]
    disputed = ((status_value in PIN_BEHIND_STATUSES and behind is not True)
                or (lane_status_asserts_current_pin(lane_status) and behind is True))
    if not disputed:
        return status_value, None
    mapped = PIN_STATUS_DISPUTED_STATUS + suffix
    pin_state = f"pin_behind_upstream {json.dumps(behind)}, pin_comparison {pin_fields.get('pin_comparison')}"
    if pin_fields.get("pin_comparison_reason"):
        pin_state += f", pin_comparison_reason {pin_fields['pin_comparison_reason']}"
    who = f"{lane} lane " if lane else "lane "
    return mapped, (f"{who}status {status_value} published as {mapped}: it contradicts the row's "
                    f"computed pin fields ({pin_state}); the lane's claim is kept in this row's "
                    "evidence and disputed_lane_status")


def _classification_of(baseline_row: dict) -> dict:
    return {"behind": baseline_row["behind"], "excluded": baseline_row["excluded"],
            "reason": baseline_row["exclusion_reason"]}


def _build_card_row(card, *, layer_id, status, row_kind, repo_counts, selection=None, decision=None,
                     base_fields, landed=None):
    """Shared foundation-components[]/trading-entries[] row assembly: match
    this card's lane entries (G4), pick the row's own entry by G1 precedence
    (``select_row_review``), resolve a refuted-to-confirmed marker (G2)
    against this card's own baseline class, and preserve every other lane's
    entry verbatim under ``other_lane_reviews``.

    ``status`` is the join index from ``index_status_by_join_key``, looked up
    on ``(layer_id, repo_join_key(card["repository"]))``; a caller passing
    merge_lanes' exact-string index directly still matches on the exact
    ``(layer_id, card["repository"])`` key as before.

    ``landed`` (a set, optional) collects ``id()`` of every lane entry this
    row published (chosen or other_lane_reviews), so ``build_manifest`` can
    publish the entries no card row took (``collect_unmatched_lane_items``)."""
    bucket = (status.get((layer_id, repo_join_key(card["repository"])))
              or status.get((layer_id, card["repository"])))
    entries = bucket["entries"] if bucket else []
    matched, by_repository_only = match_lane_entries(entries, card_id=card["id"])
    row = dict(base_fields)
    if not matched:
        row["review_status"] = "not_individually_reviewed"
        row["review_note"] = None
        row["evidence"] = []
        return row
    owning_lane = "foundation" if row_kind == "foundation" else "trading"
    chosen, others_within_matched = select_row_review(matched, owning_lane=owning_lane)
    # G1: `matched` only ever holds entries selected by match_lane_entries
    # (the by-id match, or the by-repository-only fallback when no entry
    # named this card's id). A card-less entry (catalog_id None) from another
    # lane that sits alongside a by-id match never triggers the fallback, so
    # it is preserved here rather than dropped: it applies to this card too.
    # An entry whose catalog_id names a DIFFERENT card in this layer belongs
    # to that card's own row (where match_lane_entries selects it by id) and
    # is not folded in here -- folding it would publish one card's lane
    # review under another card. Nothing at this (layer, repository) key is
    # lost: every entry lands on the card(s) it names or, card-less, on all.
    matched_ids = {id(entry) for entry in matched}
    others = others_within_matched + [
        entry for entry in entries
        if id(entry) not in matched_ids and entry["catalog_id"] in (None, card["id"])
    ]
    if landed is not None:
        landed.update(id(entry) for entry in [chosen, *others])
    evidence = list(chosen["evidence"])
    if by_repository_only:
        sharing = repo_counts.get(repo_join_key(card["repository"]), repo_counts.get(card["repository"], 0))
        if sharing > 1:
            evidence.append(f"lane entry matched by repository only; {sharing} cards share it")
    review_status, pin_note = reconcile_status_with_pin(
        resolve_refuted_marker(chosen["status"], row_kind=row_kind, selection=selection, decision=decision),
        base_fields, lane_status=chosen["status"], lane=chosen["lane"])
    if pin_note:
        evidence.append(pin_note)
    row["review_status"] = review_status
    if review_status.startswith(PIN_STATUS_DISPUTED_STATUS):
        row["disputed_lane_status"] = chosen["status"]
    row["review_note"] = chosen["note"]
    row["evidence"] = evidence
    row["review_lane"] = chosen["lane"]
    if others:
        other_reviews = []
        for other in others:
            review = other_lane_review(other, row_kind=row_kind, selection=selection, decision=decision)
            review["status"], other_pin_note = reconcile_status_with_pin(
                review["status"], base_fields, lane_status=other["status"], lane=other["lane"])
            if other_pin_note:
                review["evidence"] = list(review["evidence"]) + [other_pin_note]
            if review["status"].startswith(PIN_STATUS_DISPUTED_STATUS):
                review["disputed_lane_status"] = other["status"]
            other_reviews.append(review)
        row["other_lane_reviews"] = other_reviews
    for field in ROW_LANE_FIELDS:
        if field in chosen["lane_item"]:
            row[field] = chosen["lane_item"][field]
    return row


UNMATCHED_NO_CARD = "no_card_with_repository_in_layer"
UNMATCHED_CATALOG_ID = "catalog_id_names_no_card"


def collect_unmatched_lane_items(status: dict, landed: set, rows_by_layer: dict) -> list:
    """Every lane ``selected[]`` entry at a foundation/trading layer that no
    card row published (neither as the row's own review nor under its
    other_lane_reviews), instead of dropping it silently (2026-09-23
    critic-gap recheck: 10 of critic-models-sources' 22 items, including a
    surviving demotion, and 4 original-lane items vanished this way).

    ``status`` is the ``index_status_by_join_key`` index, ``landed`` the
    ``id()`` set ``_build_card_row`` filled, ``rows_by_layer`` maps a
    foundation/trading layer id to ``(catalog, cards)``. A lane-grouping
    layer id (not in ``rows_by_layer``) is skipped: every such entry already
    lands in ``lane_groupings``. ``reason`` is ``no_card_with_repository_in_layer``
    when no card in the layer shares the repository, else
    ``catalog_id_names_no_card`` (the lane's catalog_id names no card that
    shares it). Sorted by (layer, lane, repository, catalog_id)."""
    items = []
    for (layer_id, join_key), bucket in status.items():
        if layer_id not in rows_by_layer:
            continue
        catalog, cards = rows_by_layer[layer_id]
        sharing = [card for card in cards if repo_join_key(card["repository"]) == join_key]
        for entry in bucket["entries"]:
            if id(entry) in landed:
                continue
            items.append({
                "catalog": catalog, "layer": layer_id, "lane": entry["lane"],
                "repository": entry["repository"], "catalog_id": entry["catalog_id"],
                # No card row, so no baseline decision to resolve a refuted
                # demotion marker against (resolve_refuted_marker's
                # lane_groupings branch).
                "status": resolve_refuted_marker(entry["status"], row_kind="unmatched"),
                "survives": entry.get("survives"), "verified": entry["verified"],
                "reason": UNMATCHED_CATALOG_ID if sharing else UNMATCHED_NO_CARD,
                "evidence": entry["evidence"], "note": entry["note"], "lane_item": entry["lane_item"],
            })
    items.sort(key=lambda item: (item["layer"], item["lane"], item["repository"], item["catalog_id"] or ""))
    return items


# A plain ``\bID\b`` regex boundary treats a hyphen as a non-word character,
# so it does NOT protect against a hyphen-adjacent substring collision (e.g.
# "alpaca-py" inside "data-alpaca-py", or "card-one" inside "data-card-one"
# from either direction) -- re.search(r"\balpaca-py\b", "data-alpaca-py")
# matches, because the '-' right before "alpaca-py" is itself a word
# boundary. ``_id_named_in`` instead excludes a preceding/following
# word-or-hyphen character, so a card id only matches when it appears as a
# hyphen-delimited whole segment, not as part of a longer sibling id.
def _id_named_in(id_lower: str, haystack: str) -> bool:
    pattern = r"(?<![\w-])" + re.escape(id_lower) + r"(?![\w-])"
    return re.search(pattern, haystack) is not None


def _component_field_targets(finding: dict, rows: list) -> list:
    """Rows named by a finding's own ``component`` field (review schema
    ``manifest-citation-review/1``, 2026-09-23): used only when the
    single-card resolution in ``apply_citation_review`` finds no unique
    card. A finding may name several layers ("a, b", "a; b",
    "multiple (a, b/x)") and several components ("x, y (layer)"); it
    attaches to every card whose id is named, as a hyphen-delimited whole
    segment (``_id_named_in``), in ``component``, within every row whose
    layer id is named the same way in ``layer`` -- or within every row of
    the finding's catalog when ``layer`` names none (e.g. "multiple").
    Returns ``[(layer_row, card), ...]`` in manifest order; empty when the
    finding has no ``component`` field or names no card."""
    component_text = str(finding.get("component") or "").lower()
    if not component_text:
        return []
    layer_text = str(finding.get("layer") or "").lower()
    named_rows = [r for r in rows if _id_named_in(str(r["layer"]).lower(), layer_text)]
    targets = []
    for layer_row in named_rows or rows:
        for card in layer_row.get("components", layer_row.get("entries", [])):
            if card.get("id") and _id_named_in(str(card["id"]).lower(), component_text):
                targets.append((layer_row, card))
    return targets


def apply_citation_review(manifest: dict, citation_review_doc) -> None:
    """G6: overlay an independent citation review's findings onto the
    manifest rows they name, at ``manifest["citation_review"]``. Data only --
    never edits a row's own ``why_selected``/``review_status``/etc.

    Each finding with ``catalog`` in ``{"foundation", "trading"}`` (a
    ``reviewer: "tooling"`` finding always has ``catalog: "tooling"`` in this
    artifact's schema and is ignored here -- it reviews this tool's own
    code/docs/tests, not a manifest row) is resolved to at most one row:
    ``layer`` (splitting a free-text ``"layer/component"`` or
    ``"multiple/..."`` value on ``"/"`` and taking the first segment as a
    candidate layer id) must name a real foundation/trading layer; within
    that layer, a card is matched first by its own id appearing as a
    hyphen-delimited whole segment in the finding's ``repository``/``claim``
    text (``_id_named_in`` -- a plain ``\\bID\\b`` regex boundary does NOT
    suffice here, since a hyphen is a non-word character and a plain
    boundary still fires inside a longer sibling id from either direction,
    e.g. ``alpaca-py`` inside ``data-alpaca-py`` or ``card-one`` inside
    ``data-card-one``; ``_id_named_in`` instead excludes a preceding/
    following word-or-hyphen character, so a substring collision like that
    cannot cross-match the wrong card), and only when no id matches at all,
    by the card's repository slug appearing, with the same
    ``_id_named_in`` boundary protection, in that same text (a plain
    substring check here has the identical collision, e.g.
    ``example/alpha`` inside ``example/alpha-extended``). A finding that
    resolves to zero or more than one card this way, but carries its own
    ``component`` field, is attached to every card that field names in the
    layers its ``layer`` field names (``_component_field_targets``). A
    finding that still resolves to no card is not silently dropped: it is
    appended, unchanged, to ``manifest["citation_review"]["general"]``
    instead."""
    manifest["citation_review"] = {"general": []}
    findings = list((citation_review_doc or {}).get("findings", []))
    considered = [f for f in findings if f.get("catalog") in ("foundation", "trading")]
    rows_flagged = set()
    attached = 0
    general = []
    for finding in considered:
        rows = manifest["foundation"] if finding["catalog"] == "foundation" else manifest["trading"]
        layer_field = str(finding.get("layer") or "")
        candidate_layer_id = layer_field.split("/", 1)[0].strip()
        layer_row = next((r for r in rows if r["layer"] == candidate_layer_id), None)
        card = None
        if layer_row is not None:
            haystack = " ".join(str(finding.get(f) or "") for f in ("repository", "claim")).lower()
            cards = layer_row.get("components", layer_row.get("entries", []))
            id_matches = [
                c for c in cards
                if c.get("id") and _id_named_in(str(c["id"]).lower(), haystack)
            ]
            if len(id_matches) == 1:
                card = id_matches[0]
            elif not id_matches:
                # Same collision class as the id branch above, and the
                # same fix: a plain substring `in` check has no boundary
                # protection at all, so a shorter sibling's slug (e.g.
                # "example/alpha") spuriously matches inside a longer
                # sibling's slug substring (e.g. "example/alpha-extended")
                # naming only the longer one. Reuse ``_id_named_in`` --
                # "/" is not a word-or-hyphen character, so it is already
                # a valid boundary on either side of a slug.
                slug_matches = [
                    c for c in cards
                    if github_repo_slug(c.get("repository"))
                    and _id_named_in(github_repo_slug(c.get("repository")), haystack)
                ]
                if len(slug_matches) == 1:
                    card = slug_matches[0]
        targets = [(layer_row, card)] if card is not None else _component_field_targets(finding, rows)
        if not targets:
            general.append(dict(finding))
            continue
        for target_row, target_card in targets:
            overlay = {
                "reviewer": finding.get("reviewer"), "severity": finding.get("severity"),
                "claim": finding.get("claim"), "fix": finding.get("fix"),
                # G6 asymmetry fix: carry the exact citation locators too (this
                # review round exists to preserve them) -- without these, a
                # row-attached finding was not traceable back to its cited
                # line the way a citation_review.general entry already was.
                "file": finding.get("file"), "line": finding.get("line"), "evidence": finding.get("evidence"),
            }
            if "component" in finding:
                # The finding's own component list, so a finding attached to
                # several rows still shows every row it named.
                overlay["component"] = finding.get("component")
            target_card.setdefault("citation_review", []).append(overlay)
            rows_flagged.add((finding["catalog"], target_row["layer"], target_card.get("id")))
        attached += 1
    for rows in (manifest["foundation"], manifest["trading"]):
        for row in rows:
            for card in row.get("components", row.get("entries", [])):
                if "citation_review" in card:
                    card["citation_review"].sort(key=lambda f: (f["reviewer"] or "", f["severity"] or "", f["claim"] or ""))
    # str(): a finding's line may be an int or a commit-qualified string
    # ("594 at a275ebc"); mixed types must not raise.
    general.sort(key=lambda f: (f.get("reviewer") or "", f.get("layer") or "", str(f.get("line") or ""),
                                f.get("claim") or ""))
    manifest["citation_review"]["general"] = general
    manifest["counts"]["citation_review"] = {
        # findings_in_artifact/out_of_scope make the in-scope subset
        # reconcilable against the artifact alone (a reviewer="tooling"
        # finding, catalog="tooling", reviews this tool's own code/docs/
        # tests, not a manifest row, and is out of scope here by design --
        # but was previously dropped with no trace in counts at all).
        "findings_in_artifact": len(findings),
        "findings": len(considered),
        "out_of_scope": len(findings) - len(considered),
        # attached (total findings actually attached to a row) can exceed
        # rows_flagged (distinct rows touched) whenever more than one
        # finding names the same row, and can be lower than it when one
        # finding's component field names several rows -- both are needed so
        # findings == attached + general is checkable from the manifest
        # alone, without walking every card's citation_review[].
        "attached": attached,
        "rows_flagged": len(rows_flagged),
        "general": len(general),
    }


def build_manifest(*, checked_at, manifest_id, scope, foundation_layers, trading_by_layer,
                    freshness_doc, lanes_doc, reconciliations, taxonomy,
                    os_package_ids=DEFAULT_OS_PACKAGE_IDS, citation_review=None) -> dict:
    repositories = freshness_doc.get("repositories", {})
    baseline_foundation = build_baseline_foundation(foundation_layers, repositories, os_package_ids=os_package_ids)
    baseline_trading = build_baseline_trading(trading_by_layer, repositories, os_package_ids=os_package_ids)
    status, notes, alts, cands, gaps, calls, limits = merge_lanes(lanes_doc, repositories)
    # Every lane-entry join below reads this slug-keyed index, never the
    # exact-string status keys (see index_status_by_join_key).
    status = index_status_by_join_key(status)
    foundation_selection = foundation_decision_selection_map(foundation_layers)
    landed = set()

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
        "taxonomy": taxonomy, "foundation": [], "trading": [], "lane_groupings": [],
        # Filled in below by collect_unmatched_lane_items, in position.
        "unmatched_lane_items": [],
        # Placeholder; filled in by apply_citation_review() below (G6). Set
        # here, in position, so the key stays "... lane_groupings,
        # citation_review, critic ..." even before that call runs --
        # reassigning a dict key in place never moves its position.
        "citation_review": {"general": []},
        "critic": lanes_doc.get("critic"), "lane_calls": calls, "lane_limits": limits,
    }

    for row in baseline_foundation:
        layer_id = row["layer"]
        repo_counts = _repository_share_counts(row["components"])
        components = []
        for component in row["components"]:
            base_fields = {
                "id": component["id"], "repository": component["repository"], "pin": component["pin"],
                "upstream": component["upstream"], **pin_comparison_fields(_classification_of(component)),
            }
            selection = foundation_selection.get((layer_id, component["id"]))
            components.append(_build_card_row(
                component, layer_id=layer_id, status=status, row_kind="foundation",
                repo_counts=repo_counts, selection=selection, base_fields=base_fields, landed=landed,
            ))
        components.sort(key=row_item_sort_key)
        manifest["foundation"].append({
            "layer": layer_id, "title": row["title"], "components": components,
            "alternatives_keep_but_compare": alts.get(layer_id, []),
            "candidates": sorted_candidates(cands, layer_id),
            "open_gaps": sorted(set(gaps.get(layer_id, []))),
        })

    for row in baseline_trading:
        layer_id = row["layer"]
        repo_counts = _repository_share_counts(row["entries"])
        entries = []
        for entry in row["entries"]:
            base_fields = {
                "id": entry["id"], "repository": entry["repository"], "decision": entry["decision"],
                "pin": entry["pin"], "upstream": entry["upstream"], **pin_comparison_fields(_classification_of(entry)),
            }
            if "evidence_level" in entry:
                base_fields["evidence_level"] = entry["evidence_level"]
            entries.append(_build_card_row(
                entry, layer_id=layer_id, status=status, row_kind="trading",
                repo_counts=repo_counts, decision=entry.get("decision"), base_fields=base_fields,
                landed=landed,
            ))
        entries.sort(key=row_item_sort_key)
        manifest["trading"].append({
            "layer": layer_id, "entries": entries,
            "alternatives_keep_but_compare": alts.get(layer_id, []),
            "candidates": sorted_candidates(cands, layer_id),
            "open_gaps": sorted(set(gaps.get(layer_id, []))),
        })

    # trading[] rows are now exactly the taxonomy layer ids (build_baseline_trading
    # above), so a review lane's own grouping id (e.g. the "beyond" lane's
    # "awesome-list-convergence") is never a foundation or taxonomy layer id.
    # Appending it as a fake trading row (the previous behaviour) is what made
    # scripts/landscape.py's `require(seen == expected, "comparison coverage
    # must exactly match all foundation and domain layers")` fail: trading[]
    # gained rows outside the 12-layer taxonomy it is defined to mirror
    # exactly. Such an id, and everything a lane reported under it, is carried
    # verbatim into its own "lane_groupings" row instead -- nothing is
    # dropped, it just stops masquerading as a taxonomy layer.
    known_layers = {row["layer"] for row in manifest["foundation"]} | {row["layer"] for row in manifest["trading"]}
    rows_by_layer = {row["layer"]: ("foundation", row["components"]) for row in baseline_foundation}
    rows_by_layer.update({row["layer"]: ("trading", row["entries"]) for row in baseline_trading})
    manifest["unmatched_lane_items"] = collect_unmatched_lane_items(status, landed, rows_by_layer)
    # A lane_groupings row has no baseline card list to match a lane entry's
    # catalog_id against (see match_lane_entries for foundation/trading), so
    # every distinct catalog_id an entry set (None included) at a given
    # (layer, repository) becomes its own selected[] row here -- the same
    # G4 card-disambiguation principle, applied without a baseline.
    # ``status`` is the repo_join_key index, so entries citing a release/tree
    # alias and the plain URL of one repository form one group; the group's
    # sort key is the lexically first repository string a lane cited, and
    # the published repository is the chosen entry's own citation (both are
    # that single string whenever every lane cited the same URL).
    status_by_layer = defaultdict(list)
    for (status_layer_id, _join_key), bucket in status.items():
        by_catalog_id = defaultdict(list)
        for entry in bucket["entries"]:
            by_catalog_id[entry["catalog_id"]].append(entry)
        for catalog_id, entries in by_catalog_id.items():
            first_repository = min(entry["repository"] for entry in entries)
            status_by_layer[status_layer_id].append((first_repository, catalog_id, entries))

    lane_grouping_layer_ids = sorted(
        (set(cands) | set(gaps) | set(alts) | set(status_by_layer)) - known_layers
    )
    for layer_id in lane_grouping_layer_ids:
        selected = []
        lane_names = set()
        groups = sorted(status_by_layer.get(layer_id, []), key=lambda g: (g[0], g[1] or ""))
        for _first_repository, catalog_id, entries in groups:
            # No foundation/trading owning lane applies to a lane's own
            # grouping (G1 rule (b) is moot here); ties fall straight to
            # rule (c), the lexical lane name.
            chosen, others = select_row_review(entries, owning_lane=None)
            selected_row = {
                "repository": chosen["repository"],
                "status": resolve_refuted_marker(chosen["status"], row_kind="lane_groupings"),
                "evidence": chosen["evidence"], "note": chosen["note"],
                "review_lane": chosen["lane"],
            }
            # A lane_groupings row has no baseline pin/upstream field to fall
            # back on the way a foundation/trading row does, so every field
            # the lane set (role, catalog_id, catalog_pin, upstream_now,
            # why_selected, comparison_that_would_overturn, ...) is the
            # evidence a grouping like "unmaintained-reference-material"
            # exists to record -- carried through verbatim, never invented,
            # and never overriding the merged status fields.
            for field, value in sorted(chosen.get("lane_item", {}).items()):
                if field not in selected_row:
                    selected_row[field] = value
            if others:
                selected_row["other_lane_reviews"] = [
                    other_lane_review(o, row_kind="lane_groupings") for o in others
                ]
            selected.append(selected_row)
            for entry in entries:
                if entry.get("lane"):
                    lane_names.add(entry["lane"])
        layer_alts = alts.get(layer_id, [])
        layer_candidates = sorted_candidates(cands, layer_id)
        for source in (layer_alts, layer_candidates):
            for item in source:
                if item.get("lane"):
                    lane_names.add(item["lane"])
        manifest["lane_groupings"].append({
            "layer": layer_id,
            # A single contributing lane is the observed case (see
            # tests/test_sota_convergence.py); a joined, sorted string is
            # used instead of erroring if more than one lane ever reports
            # the same non-taxonomy grouping id, so a rerun still diffs
            # cleanly rather than raising.
            "lane": ", ".join(sorted(lane_names)) if lane_names else None,
            "selected": selected,
            "alternatives_keep_but_compare": layer_alts,
            "candidates": layer_candidates,
            "open_gaps": sorted(set(gaps.get(layer_id, []))),
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

    all_cards = [card for row in all_rows for card in all_components(row)]
    other_reviews = [review for card in all_cards for review in card.get("other_lane_reviews", [])]
    pins_behind_unique = {
        component["id"] for row in all_rows for component in all_components(row)
        if component["pin_behind_upstream"]
    }
    manifest["counts"] = {
        "foundation_layers": len(manifest["foundation"]),
        "trading_layers": len([r for r in manifest["trading"] if r.get("entries")]),
        "trading_layers_note": "trading_layers counts only taxonomy layers with at least one "
                                "selected entry, unlike foundation_layers (which counts every row); "
                                "trading[] itself always has one row per taxonomy id, so "
                                "len(manifest[\"trading\"]) can exceed trading_layers whenever a "
                                "taxonomy layer happens to have zero selected entries",
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
        "pins_behind_upstream_by_review_status": dict(sorted(Counter(
            card["review_status"] for card in all_cards if card["pin_behind_upstream"]
        ).items())),
        "review_status_pin_behind_upstream": sum(
            1 for card in all_cards if card["review_status"] in PIN_BEHIND_STATUSES),
        "pin_status_disputed": sum(
            1 for card in all_cards if card["review_status"].startswith(PIN_STATUS_DISPUTED_STATUS)),
        "pin_status_disputed_by_lane_status": dict(sorted(Counter(
            card["disputed_lane_status"] for card in all_cards if "disputed_lane_status" in card
        ).items())),
        "other_lane_reviews_pin_status_disputed": sum(
            1 for review in other_reviews if review["status"].startswith(PIN_STATUS_DISPUTED_STATUS)),
        "pin_status_note": "pins_behind_upstream counts the generator's computed pin fields; "
                           "pins_behind_upstream_by_review_status splits those rows by published review_status. "
                           "A row's review_status is pin_behind_upstream[_unverified] only when its computed "
                           "pin_behind_upstream is true, so review_status_pin_behind_upstream equals the "
                           "pin_behind_upstream[_unverified] share of that split; a lane pin claim the computed "
                           "fields contradict is published as pin_status_disputed[_unverified] (the lane's claim in "
                           "disputed_lane_status and the row evidence) or, on an OS-package pin, distro_managed",
        "pins_behind_note": "components with a commit-pinned version (a parenthetical hash), a "
                             "non-GitHub repository, or an OS-distribution package pin (matched by "
                             "an -Nubuntu/-Ndeb/+debN pin suffix, or by id via --os-package-ids, "
                             "e.g. systemd even though its own repository is on GitHub) are excluded "
                             "from the pin-vs-upstream comparison rather than counted either way",
        "pins_not_compared": sum(
            1 for row in all_rows for component in all_components(row)
            if component["pin_comparison"] == PIN_NOT_COMPARED
        ),
        "pins_not_compared_by_reason": dict(sorted(Counter(
            component["pin_comparison_reason"] for row in all_rows for component in all_components(row)
            if component["pin_comparison"] == PIN_NOT_COMPARED
        ).items())),
        "pins_not_compared_note": "rows whose pin the generator could not compare with upstream "
                                  "(the exclusions above, plus a pin or upstream latest with no "
                                  "parseable version, reason unversioned) carry pin_behind_upstream "
                                  "null and pin_comparison not_compared, never a definite false",
        "candidates_by_disposition": dict(Counter(
            candidate["disposition"] for row in all_rows for candidate in row["candidates"]
        )),
        "lane_groupings": len(manifest["lane_groupings"]),
        "lane_grouping_candidates": sum(len(g["candidates"]) for g in manifest["lane_groupings"]),
        "unmatched_lane_items": len(manifest["unmatched_lane_items"]),
        "unmatched_lane_items_by_lane": dict(sorted(Counter(
            item["lane"] for item in manifest["unmatched_lane_items"]).items())),
        "lane_groupings_note": "every foundation/trading-scoped count above (candidates_total, "
                                "candidates_by_disposition, components_confirmed, pins_behind_upstream, "
                                "pins_behind_upstream_unique_components) is computed from all_rows = "
                                "manifest['foundation'] + manifest['trading'] only, and so excludes "
                                "lane_groupings[].selected rows the same way it excludes "
                                "lane_groupings[].candidates; candidates inside lane_groupings (a "
                                "review-lane grouping id outside the foundation/taxonomy baseline, e.g. "
                                "an awesome-list survey) are counted only in lane_grouping_candidates; "
                                "counts.citation_review (computed below, by apply_citation_review) is the "
                                "same way scoped -- its rows_flagged/attached only ever count a foundation/"
                                "trading row, never a lane_groupings[].selected row, since apply_citation_review "
                                "only walks manifest['foundation'] and manifest['trading']",
    }
    apply_citation_review(manifest, citation_review)
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
    parser.add_argument("--citation-review", type=Path, default=None,
                         help="Optional independent citation-review artifact (schema: "
                              "{findings: [{reviewer, catalog, severity, layer, repository, "
                              "file, line, claim, evidence, fix}, ...]}); overlaid onto the "
                              "matching foundation/trading rows at manifest['citation_review'] "
                              "(G6) -- data only, never edits a row's own fields.")
    parser.add_argument("--checkout-root", dest="checkout_roots", type=Path, action="append", default=None,
                         help="A checkout of this catalog repository that lane citations point into; a cited "
                              "path under it is published repository-relative (e.g. manifests/stack.json) "
                              "rather than redacted to <host-path>/<basename>. Repeatable. Default: the "
                              "checkout this tool runs from.")
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
    citation_review = load_json(args.citation_review) if args.citation_review else None
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
        citation_review=citation_review,
    )

    # A host path under the private --work-dir (or, when the three inputs
    # were instead given individually, their shared parent directory) is
    # redacted to "<work-dir>/<basename>" rather than the generic
    # "<host-path>/<basename>" (G5) -- both keep the basename and any JSON
    # pointer suffix; see sanitize()'s docstring.
    if work_dir:
        work_dir_for_sanitize = str(work_dir.resolve())
    else:
        parents = {p.resolve().parent for p in (foundation_layers_path, trading_by_layer_path, freshness_path)}
        work_dir_for_sanitize = str(parents.pop()) if len(parents) == 1 else None

    # Sanitize the decoded object *before* serialization (see sanitize_value's
    # docstring for why sanitizing the serialized text instead can produce
    # invalid JSON), then prove the serialized result is valid JSON before
    # the leak check and the write.
    checkout_roots = [str(root.resolve()) for root in (args.checkout_roots or [REPO_ROOT])]
    text = json.dumps(sanitize_value(manifest, work_dir=work_dir_for_sanitize, checkout_roots=checkout_roots),
                      indent=1)
    json.loads(text)
    assert_no_leak(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
