#!/usr/bin/env python3
"""Consume the per-layer Claude/Codex lane returns produced against
``lane_packets.py``'s packets and record them onto the layer-verdict schema
v2 rows in ``catalogs/landscape/{foundation,us-equities}.json``.

Nothing here selects a winner: a lane already produced ``winner_keys``,
``why_selected`` and the rest of the lane-return contract (see the PR-5
lane contract's "Lane return" section). This tool only validates each lane
file (rejecting -- and treating as absent -- one that fails a schema or
recording rule, never aborting the run), seals the accepted lane returns as
retained evidence, derives the row's winner/alternative fields deterministically
from the packet and the lane returns, and writes the result back into the two
ledger files, never touching any v1 field: the winning lane's ``overturn_when``
goes to the v2-owned ``verdict_overturn_when`` (empty unless a verdict is
recorded), because the dated quality comparison mirrors the v1 text.

Inputs (read, never modified):

- ``<work-dir>/packets/<catalog>__<layer_id>.json`` and
  ``<work-dir>/packets/SHA256SUMS`` -- written by the sibling ``lane_packets.py``
  unit; consumed here only to resolve candidate metadata (``component_id``,
  ``pin``, ``recipe_ref``, ``adopted``) and to verify a lane return's
  ``packet_sha256``.
- ``<work-dir>/{claude,codex}/<catalog>__<layer_id>.json`` -- one lane return
  per lane per layer (see the lane-return contract in the PR-5 lane contract).
- ``<adjudications>/<catalog>__<layer_id>.json`` (optional, ``--adjudications``)
  -- ``{"winner_lane": "claude"|"codex"|null, "why": str, "evidence_refs": [...],
  "judgments": [{"claude_position": "A"|"B", "preferred_position": "A"|"B",
  "preferred_lane": "claude"|"codex", "refuting_votes": int}, ...]}``, used only
  when the two lanes disagree on the winner set. The judgments must cover both
  presentation orders; ``winner_lane`` must be the lane every judgment chose
  with no refutation, or null when they split.
- ``catalogs/landscape/manifest.json#/sources/repository_index`` -- the
  canonical repository identity index, used only to decide whether an
  alternative's repository is indexed (an unindexed alternative is moved into
  ``open_gaps`` rather than rejecting the lane).

Outputs (``--write`` only; ``--check``, the default-safe verification mode,
recomputes everything in memory and exits 1 on any difference without
writing):

- The two ledger files, rewritten with ``json.dumps(doc, indent=2,
  ensure_ascii=False)`` + a trailing newline -- the exact serialization
  already used for these hand-maintained files, so every untouched byte
  (including field order) stays identical.
- ``evidence/artifacts/layer-verdicts-20260922/<lane>/<run_id>.json`` -- each
  accepted lane return, reserialized deterministically (``sort_keys=True,
  indent=1`` + newline; the same "written verbatim" convention every other
  generator in this toolset uses, subject to the same leak defense).
- ``evidence/artifacts/layer-verdicts-20260922/adjudication/<run_id>.json`` --
  the adjudication record, when a disagreement was resolved by one or when a
  counterbalanced adjudication split (the row then stays ``pending_lanes``).

Outside the grandfathered 2026-09-22 wave, ``--write`` also seals the wave's packets and their
SHA256SUMS under ``<sealed_base>/packets/`` and ``<sealed_base>/run-manifest.json``; it refuses once
that manifest exists unless ``--append-rows`` names only rows absent from it, and never overwrites
a sealed file with other bytes. Each row of the wave stores ``lanes.run_manifest_sha256`` (and,
when an adjudication was sealed for it, ``lanes.adjudication_sha256``), which scripts/landscape.py
verifies in CI together with the row's agreement and winners against its sealed returns.

A lane file that fails validation is reported (layer id, lane, failing rule)
and treated as absent for that layer; this never aborts the run, but the
process exits 1 at the end if any lane file was rejected (in either mode).
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
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reused, not reimplemented: build_manifest.py owns the host-path/secret-leak
# contract for every generator under tools/sota-convergence/; build_verdicts.py
# owns which two files are the landscape ledger.
from build_manifest import assert_no_leak, sanitize_value  # noqa: E402
from build_verdicts import LEDGER_FILES, WAVE_REGISTRY, load_registry  # noqa: E402

# scripts/landscape.py owns the layer-verdict schema v2 enums and the sealed-
# file path convention (evidence/artifacts/layer-verdicts-20260922/<lane>/
# <run_id>.json); scripts/catalog_decisions.py owns repository identity.
# REPO_ROOT (this checkout), not the data ``--root``, is what makes these
# importable -- the two can differ in tests, where ``--root`` is a fixture
# tempdir that only carries the data files these tools operate on.
from scripts.landscape import (  # noqa: E402
    DISPOSITIONS, WINNER_EVIDENCE_CLASSES, OVERTURN_MARKERS, https_url,
    RUN_MANIFEST_NAME, RETAINED_PACKETS_DIR, is_grandfathered_run, judge_adjudication,
    lane_model_issue, lane_provenance_issue, load_lane_provenance_registry,
    lane_provenance_registry_issue, registered_provenance_entry, claude_refutation_issue,
    packet_component_id, parse_retained_sha256sums, single_lane_authorizes, single_lane_decision_path_issue,
    withheld_packet_keys,
)
# One platform-status rule for every caller (2026-09-23 peer audit, item 6): scripts/platform_status.py
# (catalog PR #117) derives each platform's status from the host receipts and registered evidence;
# scripts/landscape.py and scripts/component_matrix.py call the same function.
from scripts.platform_status import PLATFORMS, load_context, platform_status  # noqa: E402
from scripts.catalog_decisions import identity, canonical, load, safe_file  # noqa: E402

LANES = ("claude", "codex")
# Default run id for the sealed 2026-09-22 wave, exactly like
# scripts/landscape.py's own sealed-path template (validate_verdict_row,
# derived from the row's own lanes.<lane>.run_id) and build_verdicts.py's own
# "-20260922" output names -- not derived from --checked-at, which only sets
# the per-row checked_at date. A later run passes ``--run-id`` (see
# parse_args/main) to write a new dated wave without touching this sealed
# one; these two module-level names stay as the defaults so the checked-in
# 2026-09-22 fixtures and tests that reference record_verdicts.VERDICT_DATE /
# record_verdicts.SEALED_BASE keep working unchanged.
VERDICT_DATE = "20260922"
SEALED_BASE = f"evidence/artifacts/layer-verdicts-{VERDICT_DATE}"

# Same character class scripts/landscape.py requires of lanes.<lane>.sealed_base
# (re.fullmatch(r"evidence/artifacts/layer-verdicts-[0-9A-Za-z]+", ...)); checked at
# argument parsing so a run-id containing "-", "/" or ".." is rejected before any
# sealed file is written, rather than surfacing only when landscape.py runs later.
RUN_ID_PATTERN = re.compile(r"[0-9A-Za-z]+")


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise SystemExit(f"--run-id must match {RUN_ID_PATTERN.pattern!r} (got {run_id!r})")
    return run_id


def checked_at_for(run_id: str, checked_at=None) -> str:
    """``--checked-at`` when given (an ISO date), else the dated run id's own date."""
    if checked_at is not None:
        try:
            return date.fromisoformat(checked_at).isoformat()
        except ValueError:
            raise SystemExit(f"--checked-at must be an ISO date YYYY-MM-DD (got {checked_at!r})") from None
    if re.fullmatch(r"[0-9]{8}", run_id):
        try:
            return date(int(run_id[:4]), int(run_id[4:6]), int(run_id[6:])).isoformat()
        except ValueError:
            pass
    raise SystemExit(f"--run-id {run_id!r} is not a YYYYMMDD date; pass --checked-at YYYY-MM-DD")


def sealed_base_for(run_date: str) -> str:
    return f"evidence/artifacts/layer-verdicts-{run_date}"


SCHEMA_PATH = Path(__file__).resolve().parent / "lane-return.schema.json"
# The Claude lane's workflow is vendored here (2026-09-23 peer audit); a new-wave Claude return's
# provenance.workflow_sha256 must equal this SHA256SUMS entry for its workflow file, so the lane
# a verdict came from can be rerun from the catalog alone.
VENDORED_WORKFLOW_SUMS = "examples/claude-native/workflows/SHA256SUMS"
VENDORED_WORKFLOW_DIR = "examples/claude-native/workflows/"
# The Codex lane code a new-wave return's provenance must hash to, in the checkout being recorded.
CODEX_LANE_FILES = {"codex_lane_py_sha256": "tools/sota-convergence/codex_lane.py",
                    "prompt_sha256": "tools/sota-convergence/lane-prompt.md"}


def load_lane_code(root: Path) -> dict:
    """What a new-wave return's provenance is checked against at record time: the registered
    lane code (scripts/landscape.py LANE_PROVENANCE_REGISTRY, which CI re-checks), the vendored
    workflow SHA256SUMS and this checkout's current codex_lane.py / lane-prompt.md hashes."""
    current = {}
    for field, relative in CODEX_LANE_FILES.items():
        path = root / relative
        current[field] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {"registry": load_lane_provenance_registry(root),
            "vendored_sums": parse_sha256sums(root / VENDORED_WORKFLOW_SUMS), "codex_current": current}


def _schema_properties():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    props = schema["properties"]

    def object_props(node):
        if node.get("type") == "object" or "properties" in node:
            return set(node.get("properties", {}))
        for option in node.get("anyOf", []) + node.get("oneOf", []):
            if isinstance(option, dict) and option.get("properties"):
                return set(option["properties"])
        return set()

    return {
        "top": set(props), "model": object_props(props["model"]),
        "alternative": object_props(props["alternatives"]["items"]),
        "challenger": object_props(props["challenger_preferred"]),
        "overturn_protocol": object_props(props["overturn_protocol"]),
    }


SCHEMA_PROPERTIES = _schema_properties()


def require_known_properties(value: dict, allowed: set, label: str):
    extra = sorted(set(value) - allowed)
    require_lane(not extra, f"{label} has properties outside the lane-return schema: {', '.join(extra)}")


class LaneRejected(ValueError):
    """A lane return file failed schema or recording-rule validation and is
    treated as absent for its layer (never aborts the run)."""


def require_lane(condition, message):
    if not condition:
        raise LaneRejected(message)


def nonempty_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_identity(value):
    """``identity()`` without raising -- used for membership/dedupe checks on
    lane-authored text that has not been through catalog_decisions.py's own
    confined validation (e.g. an alternative repository may not even be a
    GitHub URL)."""
    try:
        return identity(value)
    except (ValueError, TypeError):
        return None


def load_canonical_index(root: Path):
    """The same three lines scripts/landscape.py's build_landscape() uses to
    build its own identities/aliases (lines ~206-208) -- kept inline rather
    than imported because they are not their own function there, but not
    reimplemented as anything more than that lookup."""
    manifest = load(root, "catalogs/landscape/manifest.json")
    index = load(root, manifest["sources"]["repository_index"])
    aliases = index.get("aliases", {}) or {}
    identities = {identity(row["repository"]) for row in index.get("records", [])}
    return identities, aliases


def parse_sha256sums(path: Path) -> dict:
    """``sha256sum``-format lines ("<hash>  <filename>"); tolerant of a
    leading "*" (binary mode) or a "packets/" path prefix -- keyed by the
    bare packet filename either way."""
    sums = {}
    if not path.is_file():
        return sums
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, filename = parts
        sums[Path(filename.lstrip("*")).name] = digest.strip().lower()
    return sums


def load_packet(packet_path: Path):
    try:
        return load_json(packet_path)
    except (OSError, UnicodeError, ValueError):
        return None


def validate_lane_return(path: Path, *, lane, catalog, layer_id, candidates_by_key,
                          packet_sha256sums, packet_filename, grandfathered=True,
                          lane_code=None) -> dict:
    """Full structural + "rules beyond the JSON schema" validation of one
    lane-return file. Raises LaneRejected on the first failing rule; the
    caller treats that lane as absent for this layer and never aborts.

    Outside the grandfathered 2026-09-22 wave (``grandfathered=False``) the return must also
    declare ``model.family`` matching its lane (claude: anthropic, codex: openai) with a model
    name matching that family, and carry its ``provenance``, which must name registered lane
    code (``lane_code``: load_lane_code(root)): a Claude return's (workflow_path,
    workflow_sha256) a registry entry whose vendored file's current SHA256SUMS entry is that
    hash; a Codex return the current codex_lane.py and lane-prompt.md hashes of this checkout."""
    try:
        data = load_json(path)
    except (OSError, UnicodeError, ValueError) as error:
        raise LaneRejected(f"unreadable or invalid JSON: {error}") from error

    require_lane(isinstance(data, dict), "lane return must be a JSON object")
    require_known_properties(data, SCHEMA_PROPERTIES["top"], "lane return")
    require_lane(data.get("schema_version") == 1, "schema_version must be 1")
    require_lane(data.get("lane") == lane, f"lane field must be {lane!r}")
    require_lane(data.get("catalog") == catalog, f"catalog field must be {catalog!r}")
    require_lane(data.get("layer_id") == layer_id, f"layer_id field must be {layer_id!r}")

    packet_sha256 = data.get("packet_sha256")
    require_lane(isinstance(packet_sha256, str) and bool(re.fullmatch(r"[a-f0-9]{64}", packet_sha256)),
                 "packet_sha256 must be a lowercase 64-digit hash")
    expected_hash = packet_sha256sums.get(packet_filename)
    require_lane(expected_hash is not None, f"packets/SHA256SUMS has no entry for {packet_filename}")
    require_lane(packet_sha256 == expected_hash, "packet_sha256 does not match packets/SHA256SUMS")

    model = data.get("model")
    require_lane(isinstance(model, dict) and nonempty_str(model.get("name")) and nonempty_str(model.get("effort")),
                 "model must be an object with nonempty name and effort")
    require_known_properties(model, SCHEMA_PROPERTIES["model"], "model")
    if not grandfathered:
        issue = lane_model_issue(lane, model)
        require_lane(issue is None, str(issue))
        provenance = data.get("provenance")
        issue = lane_provenance_issue(lane, provenance)
        require_lane(issue is None, str(issue))
        code = lane_code or {"registry": {}, "vendored_sums": {}, "codex_current": {}}
        issue = lane_provenance_registry_issue(lane, provenance, code["registry"])
        require_lane(issue is None, str(issue))
        if lane == "claude":
            entry = registered_provenance_entry(lane, provenance, code["registry"])
            vendored = entry.get("vendored_path")
            require_lane(isinstance(vendored, str) and vendored.startswith(VENDORED_WORKFLOW_DIR)
                         and code["vendored_sums"].get(vendored[len(VENDORED_WORKFLOW_DIR):])
                         == provenance["workflow_sha256"],
                         f"provenance.workflow_sha256 is not the {VENDORED_WORKFLOW_SUMS} entry of the vendored "
                         f"copy the registry names for {provenance['workflow_path']}: the lane must run the "
                         "currently vendored workflow bytes")
        else:
            for field, relative in CODEX_LANE_FILES.items():
                require_lane(code["codex_current"].get(field) == provenance[field],
                             f"provenance.{field} is not the sha256 of this checkout's {relative}: the return "
                             "was produced by other codex lane code")
        if lane == "claude":
            # The lane seals only a final both lenses left unrefuted (layer-verdict-lane.js); a
            # return whose summary shows a refuted or unknown final, or none, is never recorded.
            issue = claude_refutation_issue(data.get("refutation"))
            require_lane(issue is None, str(issue))

    winner_keys = data.get("winner_keys")
    require_lane(isinstance(winner_keys, list) and 1 <= len(winner_keys) <= 3
                 and all(nonempty_str(key) for key in winner_keys)
                 and len(winner_keys) == len(set(winner_keys)),
                 "winner_keys must be 1-3 unique nonempty keys")
    for key in winner_keys:
        candidate = candidates_by_key.get(key)
        require_lane(candidate is not None and candidate.get("adopted") is True,
                     f"winner key {key!r} is not an adopted packet candidate")

    why_selected = data.get("why_selected")
    require_lane(isinstance(why_selected, str) and len(why_selected) >= 60,
                 "why_selected must be at least 60 characters")

    winner_evidence_class = data.get("winner_evidence_class")
    require_lane(winner_evidence_class in WINNER_EVIDENCE_CLASSES, "winner_evidence_class is unknown")

    winner_evidence_refs = data.get("winner_evidence_refs")
    require_lane(isinstance(winner_evidence_refs, list) and all(isinstance(item, str) for item in winner_evidence_refs),
                 "winner_evidence_refs must be a list of text")

    # The contract asks why_selected to cite at least one evidence path; the lane may
    # leave winner_evidence_refs empty rather than guess, so a repository-style path
    # token anywhere in the text (or one of its own cited paths) satisfies it.
    cited_paths = [citation_path(item) for item in winner_evidence_refs]
    require_lane(any(path and path in why_selected for path in cited_paths)
                 or bool(_PATH_TOKEN.search(why_selected)),
                 "why_selected must cite at least one evidence path")

    alternatives = data.get("alternatives")
    require_lane(isinstance(alternatives, list) and bool(alternatives), "alternatives must be a nonempty list")
    why_not_defaults = set()
    for alternative in alternatives:
        require_lane(isinstance(alternative, dict), "alternative must be an object")
        require_known_properties(alternative, SCHEMA_PROPERTIES["alternative"], "alternative")
        require_lane(alternative.get("key") is None or nonempty_str(alternative.get("key")),
                     "alternative key must be text or null")
        require_lane(nonempty_str(alternative.get("name")), "alternative name must be nonempty text")
        require_lane(https_url(alternative.get("repository")), "alternative repository must be an https URL")
        require_lane(alternative.get("disposition") in DISPOSITIONS, "alternative disposition is unknown")
        why_not = alternative.get("why_not_default")
        require_lane(isinstance(why_not, str) and len(why_not) >= 30,
                     "alternative why_not_default must be at least 30 characters")
        why_not_defaults.add(why_not)
        require_lane(alternative.get("evidence_class") in WINNER_EVIDENCE_CLASSES,
                     "alternative evidence_class is unknown")
        evidence_refs = alternative.get("evidence_refs")
        require_lane(isinstance(evidence_refs, list) and all(isinstance(item, str) for item in evidence_refs),
                     "alternative evidence_refs must be a list of text")
    require_lane(why_selected not in why_not_defaults,
                 "why_selected must differ from every alternative's why_not_default")

    adopted_non_winner = [c for c in candidates_by_key.values()
                          if c.get("adopted") and c.get("key") not in winner_keys]
    alt_keys = {alt.get("key") for alt in alternatives if alt.get("key")}
    alt_repo_ids = {safe_identity(alt.get("repository")) for alt in alternatives} - {None}
    for candidate in adopted_non_winner:
        matched = candidate.get("key") in alt_keys or safe_identity(candidate.get("repository")) in alt_repo_ids
        require_lane(matched, f"adopted candidate {candidate.get('key')!r} is missing from alternatives")

    challenger = data.get("challenger_preferred")
    if challenger is not None:
        require_lane(isinstance(challenger, dict), "challenger_preferred must be an object or null")
        require_lane(challenger.get("key") is None or nonempty_str(challenger.get("key")),
                     "challenger_preferred key must be text or null")
        require_lane(nonempty_str(challenger.get("name")), "challenger_preferred name must be nonempty text")
        require_known_properties(challenger, SCHEMA_PROPERTIES["challenger"], "challenger_preferred")
        require_lane(https_url(challenger.get("repository")), "challenger_preferred repository must be an https URL")
        require_lane(nonempty_str(challenger.get("why")), "challenger_preferred why must be nonempty text")
        required_comparison = challenger.get("required_comparison")
        require_lane(isinstance(required_comparison, str)
                     and any(marker in required_comparison for marker in OVERTURN_MARKERS),
                     "challenger_preferred required_comparison must name a fixtures/blueprints/tests path "
                     "or a runnable command")

    overturn_when = data.get("overturn_when")
    require_lane(isinstance(overturn_when, str) and any(marker in overturn_when for marker in OVERTURN_MARKERS),
                 "overturn_when must name a fixture/blueprint/test path or a runnable command")

    overturn_protocol = data.get("overturn_protocol")
    require_lane(isinstance(overturn_protocol, dict), "overturn_protocol must be an object")
    require_known_properties(overturn_protocol, SCHEMA_PROPERTIES["overturn_protocol"], "overturn_protocol")
    require_lane(isinstance(overturn_protocol.get("fixture_paths"), list)
                 and all(isinstance(item, str) for item in overturn_protocol["fixture_paths"]),
                 "overturn_protocol.fixture_paths must be a list of text")
    require_lane(isinstance(overturn_protocol.get("metric"), str), "overturn_protocol.metric must be text")
    require_lane(isinstance(overturn_protocol.get("arms"), list), "overturn_protocol.arms must be a list")

    for field in ("open_gaps", "sources_read", "limits"):
        values = data.get(field)
        require_lane(isinstance(values, list) and all(isinstance(item, str) for item in values),
                     f"{field} must be a list of text")

    return data


def derive_component_id(candidate: dict) -> str:
    # One rule with scripts/landscape.py, which recomputes a new-wave row's winners from its sealed returns.
    return packet_component_id(candidate)


def component_ids_for(lane_data: dict, candidates_by_key: dict) -> set:
    return {derive_component_id(candidates_by_key[key]) for key in lane_data["winner_keys"]
            if key in candidates_by_key}


def platform_status_for(evidence_class: str, evidence_refs=(), status_context=None, *,
                        component_id=None, pin=None) -> dict:
    """Per-platform status of one winner. ``status_context`` None is the grandfathered 2026-09-22
    rule, kept only so --check reproduces that frozen wave (linux from the lane's own evidence
    class, macos-arm64 untested); otherwise every platform's status is
    scripts/platform_status.py ``platform_status(platform_id, winner, status_context)``, with
    ``status_context`` from one ``load_context(root)`` per run."""
    if status_context is None:
        if evidence_class in {"native_proven", "measured_comparison"}:
            linux_status = "accepted"
        elif evidence_class in {"local_integration", "synthetic"}:
            linux_status = "conditional"
        else:
            linux_status = "not_established"
        return {"linux-wsl2-x86_64": linux_status, "macos-arm64": "untested"}
    winner = {"component_id": component_id, "pin": pin, "evidence_class": evidence_class,
              "evidence_refs": list(evidence_refs or ())}
    return {platform_id: platform_status(platform_id, winner, status_context).status
            for platform_id in PLATFORMS}


def v1_pin_text(v1_candidate: dict) -> str | None:
    """The real v1 candidate schema (``catalogs/landscape/{foundation,
    us-equities}.json``'s ``candidates[]``) never had a ``v1_pin`` field --
    a pin/version text, when a lane recorded one at all, lives under
    ``source_pin`` (a commit/tag string) or, for a handful of rows,
    ``revision``. ``source_pin`` is preferred when both are present."""
    if not isinstance(v1_candidate, dict):
        return None
    return v1_candidate.get("source_pin") or v1_candidate.get("revision") or None


def index_v1_candidates_by_repository(row: dict) -> dict:
    """repository -> v1 candidate dict, first-seen wins, built from the
    ledger row's own (untouched) ``candidates[]`` -- the packet's candidates
    carry the same ``repository`` string verbatim from these (see the PR-5
    lane contract's packet shape), so a plain string match is exact."""
    index: dict = {}
    for candidate in row.get("candidates") or []:
        repository = candidate.get("repository") if isinstance(candidate, dict) else None
        if repository and repository not in index:
            index[repository] = candidate
    return index


# A lane cites evidence as a reader would ("docs/x.md:107-130",
# "catalogs/y.json#L564-L603 (decision id ...)", "adoption/receipt.json lines 10-11").
# The ledger's evidence_refs are bare canonical repository paths (scripts/landscape.py
# evidence() -> scripts/catalog_decisions.safe_file), so the row keeps the file path and
# the sealed lane return keeps the full anchored citation. A citation that resolves to no
# repository file (for example one naming the lane packet itself) is counted, never kept.
# Generated publication indexes are not evidence, and citing one from a ledger row makes the
# explorer embed a hash of a file that embeds the explorer's own hash (no fixed point).
GENERATED_INDEXES = frozenset({"manifests/evidence.json", "docs/ecosystem/index.html"})
_PATH_TOKEN = re.compile(r"(?<![\w/.-])[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.[A-Za-z0-9]+")
_LINE_SUFFIX = re.compile(r":[0-9L][0-9L,\-]*$")


def citation_path(citation: str) -> str:
    text = citation.strip()
    if text.startswith("https://"):
        return text.split()[0]
    text = text.split(None, 1)[0] if text else ""
    text = text.split("#", 1)[0]
    text = _LINE_SUFFIX.sub("", text)
    return text.rstrip(".,;)")


def normalize_evidence_refs(citations, root: Path):
    """Return (paths, unresolved): unique canonical repository file paths or safe
    https URLs in first-seen order, and the citations that resolve to neither."""
    paths, unresolved = [], []
    for citation in citations or []:
        if not isinstance(citation, str):
            continue
        path = citation_path(citation)
        ok = False
        if path.startswith("https://"):
            ok = https_url(path)
        elif path and path not in GENERATED_INDEXES:
            try:
                ok = safe_file(root, path).is_file()
            except ValueError:
                ok = False
        if ok:
            if path not in paths:
                paths.append(path)
        else:
            unresolved.append(citation)
    return paths, unresolved


def build_winners(lane_data: dict, candidates_by_key: dict, ledger_path: str,
                   v1_candidates_by_repository: dict, root: Path = None, unresolved: list = None,
                   status_context=None) -> list:
    why_selected = lane_data["why_selected"]
    evidence_class = lane_data["winner_evidence_class"]
    if root is None:
        evidence_refs = list(lane_data.get("winner_evidence_refs") or [])
    else:
        evidence_refs, missing = normalize_evidence_refs(lane_data.get("winner_evidence_refs"), root)
        if unresolved is not None:
            unresolved.extend(missing)
    winners = []
    for key in lane_data["winner_keys"]:
        candidate = candidates_by_key[key]
        # manifest pin (the packet's own join), else the winning candidate's
        # real v1 pin text (source_pin, else revision) if any, else
        # "unpinned" -- the contract's three-step fallback for "pin".
        v1_candidate = v1_candidates_by_repository.get(candidate.get("repository"))
        pin = candidate.get("pin") or v1_pin_text(v1_candidate) or "unpinned"
        component_id = derive_component_id(candidate)
        winners.append({
            "component_id": component_id,
            "repository": candidate.get("repository"),
            "pin": pin,
            "evidence_class": evidence_class,
            "why_selected": why_selected,
            "evidence_refs": evidence_refs,
            "recipe_ref": candidate.get("recipe_ref") or ledger_path,
            "platform_status": platform_status_for(evidence_class, evidence_refs, status_context,
                                                   component_id=component_id, pin=pin),
        })
    return winners


def build_alternatives(valid: dict, identities: set, aliases: dict, root: Path = None, unresolved: list = None):
    """Union of both lanes' alternatives by normalized repository slug,
    Claude's entry first -- first-seen wins, matching the "first-seen wins"
    dedupe pattern used elsewhere in this toolset. An alternative whose
    repository is not in the canonical index is dropped into open_gaps
    instead of being rejected."""
    seen = {}
    open_gaps = []
    for lane in LANES:
        data = valid.get(lane)
        if not data:
            continue
        for alternative in data.get("alternatives") or []:
            repository = alternative.get("repository")
            slug = safe_identity(repository)
            dedupe_key = canonical(slug, aliases) if slug else f"__unindexed__:{repository}"
            if dedupe_key in seen:
                continue
            if slug is None or canonical(slug, aliases) not in identities:
                open_gaps.append(f"unindexed alternative {alternative.get('name')} {repository}")
                seen[dedupe_key] = None
                continue
            seen[dedupe_key] = {
                "name": alternative.get("name"), "repository": repository,
                "disposition": alternative.get("disposition"),
                "why_not_default": alternative.get("why_not_default"),
                "evidence_class": alternative.get("evidence_class"),
                "evidence_refs": (list(alternative.get("evidence_refs") or []) if root is None
                                  else _normalized(alternative.get("evidence_refs"), root, unresolved)),
                "source": f"lane:{lane}",
            }
    alternatives = [value for value in seen.values() if value is not None]
    return alternatives, open_gaps


def _normalized(citations, root: Path, unresolved):
    paths, missing = normalize_evidence_refs(citations, root)
    if unresolved is not None:
        unresolved.extend(missing)
    return paths


def is_nonempty_protocol(protocol) -> bool:
    return isinstance(protocol, dict) and bool(
        protocol.get("fixture_paths") or protocol.get("metric") or protocol.get("arms"))


def choose_overturn_protocol(valid: dict) -> dict:
    claude = valid.get("claude")
    if claude and is_nonempty_protocol(claude.get("overturn_protocol")):
        return claude["overturn_protocol"]
    codex = valid.get("codex")
    if codex:
        return codex["overturn_protocol"]
    return claude["overturn_protocol"]


def load_adjudication(adjudications_dir, catalog, layer_id, issues: list = None, *, grandfathered=True,
                      packet_sha256=None):
    """Return the adjudication for one layer, or None. A file that exists but is
    malformed is reported through ``issues`` (never silently ignored). The rules live in
    scripts/landscape.py judge_adjudication, which CI re-applies to the sealed copy: outside the
    grandfathered wave every judgment names its judge (model, family) and a stripped-packet hash
    equal to ``packet_sha256`` (this layer's packets/SHA256SUMS entry), and a winner needs both lane families in both presentation orders (else a split)."""
    if adjudications_dir is None:
        return None
    path = Path(adjudications_dir) / f"{catalog}__{layer_id}.json"
    if not path.is_file():
        return None

    def reject(reason):
        if issues is not None:
            issues.append({"catalog": catalog, "layer_id": layer_id, "lane": "adjudication", "reason": reason})
        return None

    try:
        raw = load_json(path)
    except (OSError, UnicodeError, ValueError) as error:
        return reject(f"unreadable or invalid JSON: {error}")
    issue, result = judge_adjudication(raw, grandfathered=grandfathered, packet_sha256=packet_sha256)
    if issue is not None:
        return reject(issue)
    return {"raw": raw, **result}


def relativize_source(entry: str, root: Path, lane_roots=()) -> str:
    """A lane records the absolute paths it opened. Only a path under one of the
    checkouts the lane was given as its repository root (``--lane-repo-root``) is
    rewritten to its repository-relative form, and only when that file exists here;
    a trailing note is kept. Every other absolute path is left for sanitize_value to
    redact, so a file from another checkout is never attributed to this repository."""
    if not isinstance(entry, str) or not entry.startswith("/"):
        return entry
    for lane_root in lane_roots:
        prefix = str(lane_root).rstrip("/") + "/"
        if not entry.startswith(prefix):
            continue
        remainder = entry[len(prefix):]
        head, _, rest = remainder.partition(" ")
        path_part = _LINE_SUFFIX.sub("", head.split("#", 1)[0])
        try:
            if path_part and safe_file(root, path_part).is_file():
                return remainder
        except ValueError:
            pass
    return entry


def with_relative_sources(data: dict, root: Path, lane_roots=()) -> dict:
    result = dict(data)
    result["sources_read"] = [relativize_source(entry, root, lane_roots)
                              for entry in data.get("sources_read") or []]
    return result


def sealed_text(data: dict) -> str:
    sanitized = sanitize_value(data)
    text = json.dumps(sanitized, sort_keys=True, indent=1) + "\n"
    assert_no_leak(text)
    return text


def process_row(row: dict, root: Path, catalog: str, layer_id: str, work_dir: Path, checked_at: str,
                 adjudications_dir, identities: set, aliases: dict, sha256sums: dict, rejections: list,
                 lane_roots=(), run_date: str = VERDICT_DATE, sealed_base: str = SEALED_BASE,
                 outcomes: dict = None, single_lane_decision: str = None, status_context=None,
                 lane_code=None, failures: dict = None) -> list:
    """Mutate ``row`` in place with whatever the valid lane returns for this
    layer establish; return the list of (absolute path, text) sealed/
    adjudication files this row's processing needs written. Returns an empty
    list -- and leaves ``row`` completely untouched -- when neither lane file
    exists for this layer. ``outcomes`` (when given) receives this layer's
    per-lane outcome for the run manifest: sealed, rejected with reasons, failed with the reason its
    lane runner listed in ``failures`` ((lane, catalog, layer_id) -> reason), or missing."""
    grandfathered = is_grandfathered_run(run_date)
    if not grandfathered and status_context is None:
        # A new wave must derive platform status from receipts; never fall back to the legacy rule silently.
        raise ValueError(f"process_row({catalog}__{layer_id}): run {run_date} needs a platform-status context")
    lane_paths = {lane: work_dir / lane / f"{catalog}__{layer_id}.json" for lane in LANES}
    outcome = {lane: missing_outcome(failures, lane, catalog, layer_id) for lane in LANES}
    if outcomes is not None:
        outcomes[(catalog, layer_id)] = outcome
    if not any(path.is_file() for path in lane_paths.values()):
        return []

    def reject_lane(lane, reason):
        rejections.append({"catalog": catalog, "layer_id": layer_id, "lane": lane, "reason": reason})
        outcome[lane] = {"outcome": "rejected", "reasons": [reason]}

    packet_filename = f"{catalog}__{layer_id}.json"
    packet_path = work_dir / "packets" / packet_filename
    packet = load_packet(packet_path)
    packet_mismatch = None
    if packet is not None:
        actual = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        if packet_filename not in sha256sums:
            packet_mismatch = f"packets/SHA256SUMS has no entry for {packet_filename}"
        elif sha256sums[packet_filename] != actual:
            packet_mismatch = f"packet file packets/{packet_filename} does not match packets/SHA256SUMS"
    candidates_by_key = {c["key"]: c for c in packet.get("candidates", [])} if packet else {}
    v1_candidates_by_repository = index_v1_candidates_by_repository(row)

    valid = {}
    for lane, path in lane_paths.items():
        if not path.is_file():
            continue
        try:
            if packet is None:
                raise LaneRejected(f"packet missing or invalid: packets/{packet_filename}")
            if packet_mismatch:
                raise LaneRejected(packet_mismatch)
            valid[lane] = validate_lane_return(
                path, lane=lane, catalog=catalog, layer_id=layer_id, candidates_by_key=candidates_by_key,
                packet_sha256sums=sha256sums, packet_filename=packet_filename, grandfathered=grandfathered,
                lane_code=lane_code)
        except LaneRejected as error:
            reject_lane(lane, str(error))

    if not grandfathered and len(valid) == 2 and valid["claude"]["model"]["family"] == valid["codex"]["model"]["family"]:
        # Unreachable while each lane's family is fixed, kept so the two-family rule cannot lapse.
        reject_lane("codex", "the codex lane must come from a different model family than the claude lane")
        del valid["codex"]

    if not valid:
        return []

    run_id = f"{catalog}-{layer_id}-{run_date}"
    sealed_writes = []
    lanes_field = {"claude": {"run_id": "", "sealed_sha256": ""}, "codex": {"run_id": "", "sealed_sha256": ""}}
    for lane in list(valid):
        try:
            text = sealed_text(with_relative_sources(valid[lane], root, lane_roots))
        except ValueError as error:  # LeakDetected: a marker survived sanitization
            reject_lane(lane, f"sealing refused: {error}")
            del valid[lane]
            continue
        lanes_field[lane] = {"run_id": run_id, "sealed_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        outcome[lane] = {"outcome": "sealed", **lanes_field[lane]}
        sealed_writes.append((root / sealed_base / lane / f"{run_id}.json", text))
    if not valid:
        return []

    if "claude" in valid and "codex" in valid:
        agreement = ("same_winner"
                     if component_ids_for(valid["claude"], candidates_by_key)
                     == component_ids_for(valid["codex"], candidates_by_key) else "disagree")
    elif "claude" in valid:
        agreement = "codex_absent"
    else:
        # Codex-only is not one of the row's own recording paths (the
        # contract names only "Codex only -> codex_absent"); fold it into
        # the "neither lane ran" pending state -- Codex's return is still
        # sealed above for later reuse (e.g. once Claude also runs), but no
        # winner is recorded from a single non-Claude lane.
        agreement = "pending"

    open_gaps: list = []

    def add_gap(text):
        if text and text not in open_gaps:
            open_gaps.append(text)

    for lane, data in valid.items():
        challenger = data.get("challenger_preferred")
        if challenger:
            add_gap(f"lane {lane} prefers non-adopted {challenger.get('name')} "
                     f"({challenger.get('repository')}): requires {challenger.get('required_comparison')}")

    chosen_lane = None
    adjudication_sha256 = None
    winners, alternatives = [], []
    verdict_status = "pending_lanes"
    verdict_overturn_when = ""

    if agreement == "same_winner":
        chosen_lane = "claude"
        for lane in LANES:
            for gap in valid[lane].get("open_gaps") or []:
                add_gap(gap)
        verdict_status = "recorded"
    elif agreement == "codex_absent":
        # One model family alone never records a winner (2026-09-23 peer audit) unless the dated
        # docs/decisions/ record passed with --allow-single-lane carries the explicit line
        # "single-lane-authorization: <catalog>/<layer_id>" for this layer (review of #122, finding 2).
        decision_bytes = (root / single_lane_decision).read_bytes() if single_lane_decision else None
        if decision_bytes is not None and single_lane_authorizes(
                decision_bytes.decode("utf-8", errors="replace"), catalog, layer_id):
            chosen_lane = "claude"
            for gap in valid["claude"].get("open_gaps") or []:
                add_gap(gap)
            add_gap(f"codex lane absent for this layer; recorded from the claude lane alone under "
                    f"{single_lane_decision}")
            verdict_status = "recorded"
        else:
            add_gap("codex lane absent for this layer; a single-family winner needs --allow-single-lane "
                    "with a dated docs/decisions/ record carrying the line "
                    f"'single-lane-authorization: {catalog}/{layer_id}'")
            verdict_status = "pending_lanes"
    elif agreement == "disagree":
        # The contract's "<ids>" is the same "winner component_ids" the
        # agreement check above compares, not the packet-local candidate
        # keys ("c1"/"c2") -- a reader of the ledger row cannot otherwise
        # tell which repositories actually disagreed, since packet keys are
        # opaque and the packet itself is not part of the retained record.
        ids_text = (f"claude={','.join(sorted(component_ids_for(valid['claude'], candidates_by_key)))}; "
                    f"codex={','.join(sorted(component_ids_for(valid['codex'], candidates_by_key)))}")
        adjudication = load_adjudication(adjudications_dir, catalog, layer_id, rejections,
                                         grandfathered=grandfathered,
                                         packet_sha256=sha256sums.get(packet_filename))
        adjudication_text = None
        if adjudication is not None and not grandfathered:
            # The adjudication must have compared exactly the lane returns sealed here (Codex review of #145):
            # a lane rerun after assemble would otherwise inherit a winner_lane its judges never saw.
            current = {lane: hashlib.sha256(lane_paths[lane].read_bytes()).hexdigest() for lane in LANES}
            if adjudication["raw"].get("lane_returns_sha256") != current:
                rejections.append({"catalog": catalog, "layer_id": layer_id, "lane": "adjudication",
                                   "reason": "the adjudication's lane_returns_sha256 does not name the lane "
                                             "returns being sealed; rerun adjudicate inputs and assemble"})
                adjudication = None
        if adjudication is not None:
            try:
                adjudication_text = sealed_text(adjudication["raw"])
            except ValueError as error:  # LeakDetected
                rejections.append({"catalog": catalog, "layer_id": layer_id, "lane": "adjudication",
                                   "reason": f"sealing refused: {error}"})
                adjudication = None
        if adjudication is not None and adjudication["winner_lane"] in valid:
            chosen_lane = adjudication["winner_lane"]
            for gap in valid[chosen_lane].get("open_gaps") or []:
                add_gap(gap)
            adjudication_relative = f"{sealed_base}/adjudication/{run_id}.json"
            sealed_writes.append((root / sealed_base / "adjudication" / f"{run_id}.json", adjudication_text))
            adjudication_sha256 = hashlib.sha256(adjudication_text.encode("utf-8")).hexdigest()
            outcome["adjudication"] = {"outcome": "sealed", "sha256": adjudication_sha256}
            add_gap(f"lanes disagreed: {ids_text}; adjudicated by {adjudication_relative}")
            verdict_status = "recorded"
        elif adjudication is not None and adjudication["winner_lane"] is None:
            adjudication_relative = f"{sealed_base}/adjudication/{run_id}.json"
            sealed_writes.append((root / sealed_base / "adjudication" / f"{run_id}.json", adjudication_text))
            adjudication_sha256 = hashlib.sha256(adjudication_text.encode("utf-8")).hexdigest()
            outcome["adjudication"] = {"outcome": "sealed", "sha256": adjudication_sha256}
            tally = adjudication["tally"]
            reason = f"; {adjudication['split_reason']}" if adjudication.get("split_reason") else ""
            add_gap(f"lanes disagreed: {ids_text}; the counterbalanced adjudication did not agree "
                    f"(claude {tally['claude']}, codex {tally['codex']}, {adjudication['refuted']} refuted; "
                    f"{adjudication_relative}{reason}); an executed comparison must decide it")
            verdict_status = "pending_lanes"
        else:
            add_gap(f"lanes disagreed: {ids_text}; adjudication pending")
            verdict_status = "pending_lanes"
    else:  # agreement == "pending" (Claude absent; Codex may or may not be present)
        if "codex" in valid:
            add_gap("claude lane absent for this layer")
        verdict_status = "pending_lanes"

    # An unindexed alternative named by either lane belongs in open_gaps
    # regardless of whether a winner was actually recorded this run (a
    # disagree-pending or codex-only/claude-absent row can still name one);
    # gating this on verdict_status == "recorded" would silently drop it.
    unresolved_citations: list = []
    alternatives_computed, unindexed_gaps = build_alternatives(valid, identities, aliases, root,
                                                               unresolved_citations)
    for gap in unindexed_gaps:
        add_gap(gap)

    if verdict_status == "recorded" and chosen_lane:
        data = valid[chosen_lane]
        winners = build_winners(data, candidates_by_key, LEDGER_FILES[catalog], v1_candidates_by_repository,
                                root, unresolved_citations,
                                status_context=None if grandfathered else status_context)
        # The losing lane (or a lane's own list) can name a winner as an alternative;
        # a recorded row never lists its winner among its alternatives.
        winner_ids = {canonical(safe_identity(w["repository"]), aliases) for w in winners
                      if safe_identity(w.get("repository"))}
        alternatives = [alt for alt in alternatives_computed
                        if canonical(safe_identity(alt["repository"]), aliases) not in winner_ids]
        verdict_overturn_when = data["overturn_when"]
        if not alternatives:
            # scripts/landscape.py requires at least one alternative for a recorded verdict.
            add_gap("no indexed alternative remains for this verdict; recording deferred")
            winners, verdict_overturn_when, verdict_status = [], "", "pending_lanes"

    if unresolved_citations:
        add_gap(f"{len(unresolved_citations)} lane citation(s) name no repository evidence file (an "
                f"unresolved path or a generated index); the full citations are kept in the sealed lane return")

    overturn_protocol = choose_overturn_protocol(valid)

    row["verdict_status"] = verdict_status
    row["winners"] = sanitize_value(winners)
    row["alternatives"] = sanitize_value(alternatives)
    row["open_gaps"] = sanitize_value(open_gaps)
    row["verdict_overturn_when"] = sanitize_value(verdict_overturn_when)
    row["overturn_protocol"] = sanitize_value(overturn_protocol)
    row["lanes"] = {"claude": lanes_field["claude"], "codex": lanes_field["codex"], "agreement": agreement}
    # Recorded only when this run's sealed base differs from the default 2026-09-22
    # wave (scripts/landscape.py falls back to that default when the key is absent),
    # so a --run-id-less run stays byte-for-byte identical to the sealed ledger; a
    # later wave's rows carry the base a reader (or landscape.py's own verifier)
    # needs to find their sealed files under evidence/artifacts/layer-verdicts-<run-id>/.
    if sealed_base != SEALED_BASE:
        row["lanes"]["sealed_base"] = sealed_base
    if agreement == "codex_absent" and verdict_status == "recorded":
        row["lanes"]["single_lane_decision"] = single_lane_decision
        row["lanes"]["single_lane_decision_sha256"] = hashlib.sha256(decision_bytes).hexdigest()
    if adjudication_sha256 is not None and not grandfathered:
        # A new wave binds the sealed adjudication (recorded or split) to the row (review of #122,
        # finding 3); the grandfathered wave's rows keep their committed shape.
        row["lanes"]["adjudication_sha256"] = adjudication_sha256
    row["checked_at"] = checked_at

    assert_no_leak(json.dumps({
        "winners": row["winners"], "alternatives": row["alternatives"], "open_gaps": row["open_gaps"],
        "verdict_overturn_when": row["verdict_overturn_when"], "overturn_protocol": row["overturn_protocol"],
    }, sort_keys=True))

    return sealed_writes


def validate_single_lane_decision(root: Path, path):
    """--allow-single-lane PATH must be an existing, confined, dated file under docs/decisions/;
    only the layers it names on a ``single-lane-authorization: <catalog>/<layer_id>`` line are recorded."""
    if path is None:
        return None
    path = Path(path).as_posix()
    issue = single_lane_decision_path_issue(root, path)
    if issue is not None:
        raise SystemExit(f"--allow-single-lane: {issue}")
    return path


def missing_outcome(failures, lane, catalog, layer_id) -> dict:
    """A lane with no return file for a layer: failed with its runner's reason when the lane's
    failures.json lists the layer, else missing."""
    reason = (failures or {}).get((lane, catalog, layer_id))
    return {"outcome": "failed", "reasons": [reason]} if reason else {"outcome": "missing"}


LANE_FAILURES_NAME = "failures.json"


def load_lane_failures(work_dir: Path) -> dict:
    """(lane, catalog, layer_id) -> reason from each ``<work-dir>/<lane>/failures.json``
    (``{"failures": [{"catalog", "layer_id", "reason"}]}``, written by claude_lane.py and codex_lane.py
    for a layer the lane ran but returned nothing sealable for)."""
    failures = {}
    for lane in LANES:
        path = work_dir / lane / LANE_FAILURES_NAME
        if not path.is_file():
            continue
        try:
            items = load_json(path).get("failures")
            for item in items:
                reason = item["reason"]
                if not (isinstance(reason, str) and reason.strip()):
                    raise TypeError("empty reason")
                failures[(lane, item["catalog"], item["layer_id"])] = reason
        except (OSError, ValueError, AttributeError, TypeError, KeyError) as error:
            raise SystemExit(f"{path} must be {{\"failures\": [{{catalog, layer_id, reason}}]}}: {error}") from error
    return failures


LEAK_REDACTED_REASON = "reason withheld: it carries a secret or host-path marker that survived sanitization"


def manifest_reason(reason: str) -> str:
    """A rejection reason as the run manifest records it: sanitized, and replaced by a fixed note
    when it still carries a leak marker (a sealing refusal quotes the offending text)."""
    text = sanitize_value(reason)
    try:
        assert_no_leak(json.dumps(text))
    except ValueError:
        return LEAK_REDACTED_REASON
    return text


def manifest_value(value):
    if isinstance(value, dict):
        return {key: (manifest_value(item) if key != "reasons" else [manifest_reason(r) for r in item])
                for key, item in value.items()}
    return value


def packet_name(catalog: str, layer_id: str) -> str:
    return f"{catalog}__{layer_id}.json"


def wave_input_names(work_dir: Path) -> set:
    """Packet file names with an input in the work dir: a packets/ file or a lane return file."""
    names = set()
    for directory in (work_dir / "packets", *(work_dir / lane for lane in LANES)):
        if directory.is_dir():
            names |= {path.name for path in directory.glob("*__*.json") if path.is_file()}
    return names


def missing_append_inputs(work_dir: Path, only) -> list:
    """The --append-rows names without any packet or lane input in the work dir (review of catalog
    #124): such a row would otherwise be dropped silently while --write reported success."""
    if only is None:
        return []
    return sorted(only - wave_input_names(work_dir))


def wave_packet_names(work_dir: Path, only=None) -> set:
    """The packets of this run: the packets/ files, the SHA256SUMS names and any lane file without a
    packet; restricted to ``only`` (a set of packet file names) under --append-rows."""
    packets_dir = work_dir / "packets"
    names = {path.name for path in packets_dir.glob("*__*.json")} if packets_dir.is_dir() else set()
    names |= set(parse_sha256sums(packets_dir / "SHA256SUMS"))
    for lane in LANES:
        lane_dir = work_dir / lane
        if lane_dir.is_dir():
            names |= {path.name for path in lane_dir.glob("*__*.json")}
    return names if only is None else names & only


def run_manifest_document(work_dir: Path, run_date: str, sealed_base: str, outcomes: dict, rejections: list,
                          *, failures=None, only=None, previous=None) -> dict:
    """Every packet of this run, each with its actual sha256 and both lane outcomes, the packets
    retained under <sealed_base>/packets/ (``retained_packets`` and ``packets_sha256sums``, the
    retained SHA256SUMS text) and every rejection. Under --append-rows, ``previous`` is the wave's
    existing manifest without the appended rows: its entries, retained packets, SHA256SUMS lines and
    rejections are carried over unchanged and the appended rows' are added."""
    packets_dir = work_dir / "packets"
    names = wave_packet_names(work_dir, only)
    sums_path = packets_dir / "SHA256SUMS"
    entries, retained = [], []
    for name in sorted(names):
        catalog, layer_id = name[:-len(".json")].split("__", 1)
        packet_path = packets_dir / name
        outcome = outcomes.get((catalog, layer_id)) or {
            lane: missing_outcome(failures, lane, catalog, layer_id) for lane in LANES}
        digest = hashlib.sha256(packet_path.read_bytes()).hexdigest() if packet_path.is_file() else None
        entry = {"catalog": catalog, "layer_id": layer_id, "packet_sha256": digest,
                 "lanes": {lane: manifest_value(outcome[lane]) for lane in LANES}}
        adjudication = [manifest_reason(item["reason"]) for item in rejections
                        if (item["catalog"], item["layer_id"], item["lane"]) == (catalog, layer_id, "adjudication")]
        if outcome.get("adjudication"):
            # A sealed adjudication's sha256 is listed like a sealed return's (review of the #122 fix round).
            entry["adjudication"] = dict(outcome["adjudication"])
        elif adjudication:
            entry["adjudication"] = {"outcome": "rejected", "reasons": adjudication}
        entries.append(entry)
        if digest is not None:
            retained.append({"name": name, "sha256": digest})
    rejection_items = [dict(item, reason=manifest_reason(item["reason"])) for item in rejections]
    work_sums = sums_path.read_text(encoding="utf-8") if sums_path.is_file() else ""
    if only is None and previous is None:
        sums_text = work_sums
    else:
        lines = {filename: f"{digest}  {filename}" for filename, digest in parse_sha256sums(sums_path).items()
                 if filename in names}
        if previous is not None:
            kept = {Path(line.split(None, 1)[1].lstrip("*")).name: line
                    for line in (previous.get("packets_sha256sums") or "").splitlines() if len(line.split(None, 1)) == 2}
            lines = {**{name: line for name, line in kept.items() if name not in names}, **lines}
            entries = [entry for entry in previous.get("packets") or []
                       if packet_name(entry.get("catalog"), entry.get("layer_id")) not in names] + entries
            retained = [item for item in previous.get("retained_packets") or [] if item.get("name") not in names] + retained
            rejection_items = [item for item in previous.get("rejections") or []
                               if packet_name(item.get("catalog"), item.get("layer_id")) not in names] + rejection_items
        sums_text = "".join(lines[name] + "\n" for name in sorted(lines))
    entries.sort(key=lambda entry: packet_name(entry.get("catalog"), entry.get("layer_id")))
    retained.sort(key=lambda item: item["name"])
    return {
        "schema_version": 1, "run_id": run_date, "sealed_base": sealed_base,
        "generated_by": "tools/sota-convergence/record_verdicts.py",
        "packets_sha256sums": sums_text,
        "retained_packets": retained,
        "packets": entries,
        "rejections": rejection_items,
    }


def run_manifest_text(work_dir: Path, run_date: str, sealed_base: str, outcomes: dict, rejections: list,
                      **kwargs) -> str:
    return sealed_text(run_manifest_document(work_dir, run_date, sealed_base, outcomes, rejections, **kwargs))


def parse_append_rows(values) -> set:
    rows = set()
    for value in values or []:
        for item in value.split(","):
            item = item.strip()
            if not item:
                continue
            catalog, _, layer_id = item.partition("/")
            if catalog not in LEDGER_FILES or not layer_id:
                raise SystemExit(f"--append-rows entries are <catalog>/<layer_id> (got {item!r})")
            rows.add((catalog, layer_id))
    return rows


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--checked-at", default=None,
                        help="ISO date stamped on every re-recorded row. Default: the --run-id's date "
                             "(YYYYMMDD -> YYYY-MM-DD); a run id that is not a date needs it explicitly.")
    parser.add_argument("--run-id", required=True,
                        help="Run id suffix for a wave's run_id (<catalog>-<layer_id>-<run-id>) and its "
                             "sealed evidence directory (evidence/artifacts/layer-verdicts-<run-id>/). Required: "
                             "there is no default wave. A grandfathered run id (20260922) can be --check'ed, but "
                             "--write refuses it once --root holds that wave (its sealed directory or a "
                             "registered wave document). Pass the same value to --check as was used for --write.")
    parser.add_argument("--adjudications", type=Path, default=None)
    parser.add_argument("--allow-single-lane", default=None, metavar="PATH",
                        help="Dated decision record under docs/decisions/ (YYYY-MM-DD or YYYYMMDD in its file "
                             "name) that authorizes recording a codex_absent layer from the Claude lane alone; "
                             "only layers named on a 'single-lane-authorization: <catalog>/<layer_id>' line are "
                             "recorded, and the path and its sha256 are stored on the row as "
                             "lanes.single_lane_decision(_sha256). Without it a codex_absent layer stays "
                             "pending_lanes.")
    parser.add_argument("--append-rows", action="append", default=[], metavar="CATALOG/LAYER_ID[,...]",
                        help="Record only these rows (repeatable or comma-separated). A new wave's --write "
                             "refuses once its run-manifest.json exists unless every row named here is absent "
                             "from that manifest; the manifest then keeps its entries and gains these rows. "
                             "Pass the same values to --check.")
    parser.add_argument("--lane-repo-root", action="append", default=[], metavar="PATH",
                        help="Absolute checkout path a lane was given as its repository root; sources_read "
                             "entries under it are recorded repository-relative (repeatable; pass the same "
                             "values to --check).")
    # Mutually exclusive and required, matching the contract's "--write |
    # --check": previously both were independent store_true flags, so
    # omitting both silently ran --check and passing both silently preferred
    # --check -- argparse now rejects either ambiguity up front. Passing the
    # same flag more than once (e.g. a caller building argv defensively) is
    # still fine; only *both distinct* flags together is rejected.
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Write the ledger and sealed evidence files.")
    mode.add_argument("--check", action="store_true",
                       help="Recompute and compare against the checked-in ledger without writing.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    work_dir = args.work_dir.resolve()
    write_mode = bool(args.write) and not args.check

    identities, aliases = load_canonical_index(root)
    sha256sums = parse_sha256sums(work_dir / "packets" / "SHA256SUMS")
    run_date = validate_run_id(args.run_id)
    checked_at = checked_at_for(run_date, args.checked_at)
    sealed_base = sealed_base_for(run_date)
    grandfathered = is_grandfathered_run(run_date)
    if write_mode and grandfathered and ((root / sealed_base).exists() or run_date in load_registry(root)):
        # A grandfathered wave predates the integrity rules and is frozen as committed: never
        # re-record it (or add a run manifest to it), whether or not a later wave exists yet.
        raise SystemExit(f"--run-id {run_date} is a grandfathered wave already held under --root "
                         f"({sealed_base} or {WAVE_REGISTRY}); it is frozen -- record under a new --run-id")
    append_rows = parse_append_rows(args.append_rows)
    only = {packet_name(catalog, layer_id) for catalog, layer_id in append_rows} if append_rows else None
    absent_inputs = missing_append_inputs(work_dir, only)
    if absent_inputs:
        raise SystemExit(f"--append-rows names rows with no packet or lane input in {work_dir}: "
                         + ", ".join(name[:-len(".json")].replace("__", "/", 1) for name in absent_inputs))
    manifest_path = root / sealed_base / RUN_MANIFEST_NAME
    previous = None
    if not grandfathered and manifest_path.is_file():
        # A sealed new wave is never rewritten (review of #122, finding 3): a --write may only add rows
        # the existing manifest does not hold, and --check recomputes that same append.
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        held = {packet_name(entry.get("catalog"), entry.get("layer_id")) for entry in existing.get("packets") or []
                if isinstance(entry, dict)}
        if write_mode:
            if only is None:
                raise SystemExit(f"{sealed_base}/{RUN_MANIFEST_NAME} already exists: a sealed wave is never "
                                 "re-recorded; name rows absent from it with --append-rows, or record under a "
                                 "new --run-id")
            overlap = sorted(only & held)
            if overlap:
                raise SystemExit(f"--append-rows names rows the run manifest of wave {run_date} already holds: "
                                 + ", ".join(overlap))
        if only is not None:
            previous = dict(existing, packets=[entry for entry in existing.get("packets") or []
                                               if packet_name(entry.get("catalog"), entry.get("layer_id")) not in only])
    single_lane_decision = validate_single_lane_decision(root, args.allow_single_lane)
    status_context = load_context(root)
    lane_code = load_lane_code(root)
    failures = load_lane_failures(work_dir)

    rejections: list = []
    sealed_writes: list = []
    documents = {}
    outcomes: dict = {}

    for catalog, relative in LEDGER_FILES.items():
        path = root / relative
        original_text = path.read_text(encoding="utf-8")
        document = json.loads(original_text)
        documents[catalog] = (path, original_text, document)
        known = {row["layer_id"] for row in document.get("layers", [])}
        missing_rows = sorted(layer_id for named_catalog, layer_id in append_rows
                              if named_catalog == catalog and layer_id not in known)
        if missing_rows:
            raise SystemExit(f"--append-rows names {catalog} rows absent from its ledger: {', '.join(missing_rows)}")
        for row in document.get("layers", []):
            if append_rows and (catalog, row["layer_id"]) not in append_rows:
                continue
            sealed_writes.extend(process_row(
                row, root, catalog, row["layer_id"], work_dir, checked_at, args.adjudications,
                identities, aliases, sha256sums, rejections, tuple(args.lane_repo_root),
                run_date=run_date, sealed_base=sealed_base, outcomes=outcomes,
                single_lane_decision=single_lane_decision, status_context=status_context,
                lane_code=lane_code, failures=failures))

    # Survivorship: every packet of the run and each lane's outcome (sealed, rejected with its
    # reasons, failed with its runner's reason, or missing) is sealed next to the returns, with the
    # packets themselves, so a dropped dissent leaves a trace and every packet a lane or judge saw can
    # be re-read. A grandfathered wave gets none: its manifest could not list that run's rejections.
    if not grandfathered:
        manifest = run_manifest_document(work_dir, run_date, sealed_base, outcomes, rejections,
                                         failures=failures, only=only, previous=previous)
        # The same rule landscape.py applies to a sealed wave, checked before anything is written: the
        # retained SHA256SUMS lists exactly the retained packets with their actual sha256, including
        # packets no lane returned for (re-review of catalog #124). Otherwise --write would seal a wave
        # CI rejects, and a sealed wave is never re-recorded.
        sums_issue, sums_listed = parse_retained_sha256sums(manifest["packets_sha256sums"])
        retained_sha = {item["name"]: item["sha256"] for item in manifest["retained_packets"]}
        if sums_issue is not None:
            raise SystemExit(f"packets/SHA256SUMS {sums_issue}; rebuild it with lane_packets.py")
        if sums_listed != retained_sha:
            differing = sorted(name for name in set(sums_listed) | set(retained_sha)
                               if sums_listed.get(name) != retained_sha.get(name))
            raise SystemExit("packets/SHA256SUMS must list exactly the retained packets and their sha256 "
                             f"(differs for {differing}); rebuild it with lane_packets.py")
        packets_dir = work_dir / "packets"
        for item in manifest["retained_packets"]:
            if only is not None and item["name"] not in only:
                continue  # carried over from the existing manifest; already retained
            text = (packets_dir / item["name"]).read_text(encoding="utf-8")
            withheld = withheld_packet_keys(json.loads(text))
            if withheld:
                raise SystemExit(f"packets/{item['name']} carries withheld keys {withheld}: a new wave's lanes "
                                 "judge packets built with lane_packets.py --withhold-labels")
            sealed_writes.append((root / sealed_base / RETAINED_PACKETS_DIR / item["name"], text))
        sealed_writes.append((root / sealed_base / RETAINED_PACKETS_DIR / "SHA256SUMS", manifest["packets_sha256sums"]))
        manifest_text = sealed_text(manifest)
        sealed_writes.append((manifest_path, manifest_text))
        manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
        # Every row of this wave is bound to the manifest it is recorded with (an append re-binds the
        # wave's earlier rows to the extended manifest, whose earlier entries it carries unchanged).
        for _path, _text, document in documents.values():
            for row in document.get("layers", []):
                lanes = row.get("lanes")
                if isinstance(lanes, dict) and lanes.get("sealed_base") == sealed_base:
                    lanes["run_manifest_sha256"] = manifest_sha256

    ledger_outputs = {}
    for catalog, (path, original_text, document) in documents.items():
        new_text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        ledger_outputs[catalog] = (path, new_text, new_text != original_text)

    ok = not rejections
    if write_mode:
        if not grandfathered:
            # Never overwrite a sealed file with other bytes; only the manifest and the retained
            # SHA256SUMS are extended by an append.
            replaceable = {manifest_path, root / sealed_base / RETAINED_PACKETS_DIR / "SHA256SUMS"}
            conflicts = sorted(sealed_path.relative_to(root).as_posix() for sealed_path, text in sealed_writes
                               if sealed_path not in replaceable and sealed_path.is_file()
                               and sealed_path.read_text(encoding="utf-8") != text)
            if conflicts:
                raise SystemExit("refusing to overwrite sealed files with different bytes: " + ", ".join(conflicts))
        for sealed_path, text in sealed_writes:
            sealed_path.parent.mkdir(parents=True, exist_ok=True)
            sealed_path.write_text(text, encoding="utf-8")
        for path, text, _changed in ledger_outputs.values():
            path.write_text(text, encoding="utf-8")
        print(json.dumps({"status": "written", "rejections": len(rejections)}, sort_keys=True))
    else:
        changed = sorted(catalog for catalog, (_, _, is_changed) in ledger_outputs.items() if is_changed)
        if changed:
            print("layer-verdict ledger differs from the recomputed output: " + ", ".join(changed))
            ok = False
        for sealed_path, text in sealed_writes:
            relative = sealed_path.relative_to(root).as_posix()
            if not sealed_path.is_file() or sealed_path.read_text(encoding="utf-8") != text:
                print(f"sealed file differs from the recomputed output: {relative}")
                ok = False
        if ok:
            print(json.dumps({"status": "checked", "rejections": len(rejections)}, sort_keys=True))

    for item in rejections:
        print(f"rejected lane file: {item['catalog']}__{item['layer_id']} [{item['lane']}]: {item['reason']}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
