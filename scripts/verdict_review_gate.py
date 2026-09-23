#!/usr/bin/env python3
"""Required PR check: a changed layer-verdict row merges only with its sealed cross-family review.

The catalog has a single human maintainer, so required approvals cannot be the control
(docs/decisions/2026-09-22-github-automation-closure.md, "verdict-review-gate (2026-09-23)").
This check compares the landscape ledger rows (``build_verdicts.LEDGER_FILES``, the ledgers the
published wave documents are generated from; the head's ``catalogs/landscape/manifest.json#/catalogs``
must name exactly those) at ``--base`` (resolved to its merge base with the head) with the head checkout, keyed by
``(catalog, layer_id, run_id)`` where ``run_id`` comes from ``lanes.sealed_base``
(``scripts/landscape.py`` ``run_id_of``; absent means the grandfathered 2026-09-22 wave), and
lists every row added or changed in ``VERDICT_FIELDS`` (``winners`` including ``platform_status``,
``lanes``, ``verdict_status`` and the published ``alternatives``, ``verdict_overturn_when``,
``overturn_protocol`` and ``open_gaps``).

For each changed row outside ``GRANDFATHERED_RUN_IDS`` it requires, at the head:

- the wave document registered by sha256 in ``catalogs/sota-convergence/layer-verdict-waves.json``;
- ``<sealed_base>/run-manifest.json`` registered in ``manifests/evidence.json`` with its sha256,
  listing the row (``landscape.run_manifest_row_issue``) and equal to the row's
  ``lanes.run_manifest_sha256``;
- each sealed lane return present at ``<sealed_base>/<lane>/<lane run id>.json``, equal to the row's
  ``sealed_sha256`` and registered in ``manifests/evidence.json`` with that sha256 (an unsealed lane
  is accounted for as rejected or missing by the run manifest), from its lane's model family, and
  the two families distinct;
- the agreement recomputed from the sealed returns (same ``packet_sha256``; ``same_winner``
  exactly when the ``winner_keys`` sets are equal) equal to the recorded one (review finding 1);
- the sealed packet both lanes judged (review finding 6, #124's layout): the run manifest entry's
  ``packet_sha256``, found through the manifest's ``retained_packets`` under
  ``<sealed_base>/packets/`` (``RETAINED_PACKETS_DIR``), listed in ``packets/SHA256SUMS`` (equal to
  the manifest's ``packets_sha256sums``) and carrying no withheld key at any depth; the row's
  winners equal the chosen lane's ``winner_keys`` resolved through it; without it the row fails
  closed;
- a recorded ``disagree`` row: its sealed, registered adjudication in which judges of both lane
  families agree in both presentation orders with no refuting vote, and ``judge_adjudication``,
  bound by ``lanes.adjudication_sha256`` and by the run manifest entry's ``adjudication``;
- a recorded ``codex_absent`` row: a ``docs/decisions/`` record carrying the line
  ``single-lane-authorization: <catalog>/<layer_id>`` and bound by
  ``lanes.single_lane_decision_sha256`` (review finding 2).

Each winner's ``repository``, ``recipe_ref``, ``evidence_class``, ``why_selected`` and packet ``pin``
must be what ``record_verdicts.build_winners`` copies from the chosen lane and the packet; the
published ``alternatives``, ``verdict_overturn_when`` and ``overturn_protocol`` must be the ones
``record_verdicts`` derives from the sealed returns (``open_gaps`` is not re-derived); and
every changed ``platform_status`` value must be what ``scripts/platform_status.py``
``platform_status()`` derives; a row whose only change is ``platform_status`` needs nothing else. A changed
grandfathered row is reported and passes here (``build_verdicts.py --check`` freezes it). Every
row of the base keeps a row at the head whose run id is not older, never moves from a new wave back
to the grandfathered one and changes only to the newest registered wave (review of #123, finding 1).
Every wave registry entry at the base except the newest, and every grandfathered entry, must be
unchanged at the head, with its document (review finding 4). Rows, wave documents and the registry
are compared on parsed values, so a pure reformat is not a change (finding 3). When a row, a wave or any path under
``VERDICT_PATHSPECS`` changed, ``scripts/landscape.py`` and ``tools/sota-convergence/build_verdicts.py
--check`` then run on the head.

The gate's own rules are trusted only from the base: CI runs the base commit's copy of this script
against the head checkout (``--root``), and a change to a verdict row, wave or sealed artifact fails
when the same comparison also changes a ``TRUST_PATHS`` file, so a weakening of the rules has to land
(and be seen) in its own pull request first. Exit 0 prints one line when nothing of that changed;
otherwise every violation is printed with its row key and the exit code is 1 (2 for an unresolvable
revision or an unreadable or malformed base or head ledger, manifest or wave registry).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "sota-convergence"
for _path in (ROOT, TOOL_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# Reused, not reimplemented: the landscape validator owns the row-key, grandfathering, run-manifest,
# family and adjudication rules; the verdict tools own the ledger/registry paths and packet format.
from scripts.landscape import (  # noqa: E402
    DEFAULT_SEALED_BASE, GRANDFATHERED_RUN_IDS, LANE_FAMILIES, LANES, MANIFEST, RUN_MANIFEST_NAME,
    SEALED_BASE_PREFIX, judge_adjudication, lane_model_issue, run_id_of, run_manifest_row_issue,
)
from scripts import platform_status as platform_evidence  # noqa: E402
from scripts.catalog_decisions import safe_file  # noqa: E402
from scripts.host_receipts import evidence_files  # noqa: E402
from build_manifest import sanitize_value  # noqa: E402
from build_verdicts import LEDGER_FILES, WAVE_REGISTRY  # noqa: E402
from record_verdicts import (  # noqa: E402
    build_alternatives, canonical, choose_overturn_protocol, derive_component_id, load_canonical_index,
    parse_sha256sums, safe_identity,
)

# Review finding 6, aligned with the tooling owner's #124 (claude/verdict-integrity-2-20260923,
# scripts/landscape.py and tools/sota-convergence/record_verdicts.py): a new wave retains the packets
# both lanes judged under <sealed_base>/packets/ with their SHA256SUMS, and its run manifest lists
# them in retained_packets [{name, sha256}] with the SHA256SUMS text in packets_sha256sums. A row's
# packet is resolved through its run-manifest entry (packet_sha256) and that listing, never through
# an assumed file name. The names are #124's; keep them equal (tests/test_verdict_review_gate.py
# compares them with scripts/landscape.py once #124 defines them there).
RETAINED_PACKETS_DIR = "packets"
SEALED_PACKETS_DIR = RETAINED_PACKETS_DIR  # the name this gate used before #124 fixed it
PACKET_SUMS_NAME = "SHA256SUMS"
RUN_MANIFEST_RETAINED_PACKETS = "retained_packets"
RUN_MANIFEST_PACKET_SUMS = "packets_sha256sums"
RUN_MANIFEST_ADJUDICATION = "adjudication"
# #124's withheld-key policy (scripts/landscape.py is_withheld_packet_key): at any depth of a sealed
# packet a key is withheld when it is a popularity/recency key (one of POPULARITY_RECENCY_FIELDS,
# any key ending in _at, or one naming a POPULARITY_TOKENS signal), an UPSTREAM_RELEASE_FIELDS or
# COPY_WITHHELD_FIELDS key, or names a WITHHELD_KEY_TOKENS token (latest, release, newcomer,
# pin_behind). Only the packet's own top-level checked_at (its build date, PACKET_OWN_KEYS) is kept.
# #124's requirement-gated archived/license keys and label checks stay with scripts/landscape.py.
POPULARITY_RECENCY_FIELDS = ("stars", "forks", "watchers", "pushed_at", "released_at")
POPULARITY_TOKENS = ("star", "fork", "watcher", "subscriber", "download", "popular", "trending")
UPSTREAM_RELEASE_FIELDS = ("latest", "prerelease", "latest_flag")
COPY_WITHHELD_FIELDS = ("pin_behind_upstream", "newcomer", "note")
WITHHELD_KEY_TOKENS = ("latest", "release", "newcomer", "pin_behind")
PACKET_OWN_KEYS = ("checked_at",)
# The row fields #124's record_verdicts.py writes under lanes: the sha256 of the wave's run manifest,
# of a sealed adjudication (a disagree row) and of the single-lane decision record (review finding 2).
RUN_MANIFEST_SHA256_FIELD = "run_manifest_sha256"
ADJUDICATION_SHA256_FIELD = "adjudication_sha256"
SINGLE_LANE_DECISION_SHA256_FIELD = "single_lane_decision_sha256"
SINGLE_LANE_DECISION_DIR = "docs/decisions/"
SINGLE_LANE_MARKER = "single-lane-authorization:"
WAVE_DOCUMENT_PREFIX = "catalogs/sota-convergence/layer-verdicts-"
VERDICT_FIELDS = ("winners", "lanes", "verdict_status", "alternatives", "verdict_overturn_when",
                  "overturn_protocol", "open_gaps")
# The alternative fields build_verdicts.build_verdict_row publishes in the wave document.
PUBLISHED_ALTERNATIVE_FIELDS = ("name", "repository", "disposition", "why_not_default", "evidence_class", "source")
# The code the gate's verdict depends on (this script, what it imports and runs, and the workflow
# that runs it). A pull request that changes one of these and a verdict row, wave or sealed artifact
# in the same comparison fails: the rules change first, on its own.
# The list covers every repository module the gate and the validators it runs import, transitively
# (scripts/host_receipts.py imports scripts/validate.py), and the rule inputs they read from a
# checkout: the lane-provenance registry scripts/landscape.py reads from --root, the host-receipt
# schema scripts/host_receipts.py reads and the lane-return schema record_verdicts.py reads.
# tests/test_verdict_review_gate.py derives the imports and those paths from the modules themselves.
TRUST_PATHS = (
    "scripts/verdict_review_gate.py", "scripts/landscape.py", "scripts/platform_status.py",
    "scripts/catalog_decisions.py", "scripts/host_receipts.py", "scripts/validate.py",
    "tools/sota-convergence/build_verdicts.py", "tools/sota-convergence/record_verdicts.py",
    "tools/sota-convergence/build_manifest.py", "tools/sota-convergence/lane_packets.py",
    "tools/sota-convergence/lane-return.schema.json", "tools/sota-convergence/lane-provenance.json",
    "adoption/host-receipt.schema.json", ".github/workflows/validate.yml",
)
# Any change under these paths runs the repository validators even when no row changed: a PR
# that only deletes or rewrites a sealed lane file must still meet scripts/landscape.py.
VERDICT_PATHSPECS = (SEALED_BASE_PREFIX + "*", "catalogs/landscape/", "catalogs/sota-convergence/")
REPO_VALIDATORS = (
    ("scripts/landscape.py", ("scripts/landscape.py", "--root")),
    ("tools/sota-convergence/build_verdicts.py --check",
     ("tools/sota-convergence/build_verdicts.py", "--check", "--root")),
)


class RevisionError(ValueError):
    """A --base or --head revision git cannot resolve."""


class ReadError(ValueError):
    """A file the comparison needs exists but cannot be read or parsed (the gate fails closed)."""


def git_environment():
    # Inherited Git routing variables must not select another repository (scripts/validate.py idiom).
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], env=git_environment(), capture_output=True,
                          check=check)


def resolve(root, revision):
    result = git(root, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}", check=False)
    if result.returncode != 0:
        raise RevisionError(f"cannot resolve revision {revision!r}")
    return result.stdout.decode().strip()


def merge_base(root, base, head):
    result = git(root, "merge-base", base, head, check=False)
    return result.stdout.decode().strip() if result.returncode == 0 and result.stdout.strip() else base


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Side:
    """Read access to one side of the comparison: a commit through ``git show`` or a checkout."""

    def __init__(self, root, commit=None):
        self.root, self.commit = Path(root), commit

    def read(self, path):
        if self.commit is not None:
            # Absent from the tree is None; any other failure to read an object that exists is an error,
            # so a read failure cannot pass for "the base had no wave registry".
            if git(self.root, "cat-file", "-e", f"{self.commit}:{path}", check=False).returncode != 0:
                return None
            result = git(self.root, "show", f"{self.commit}:{path}", check=False)
            if result.returncode != 0:
                raise ReadError(f"cannot read {path} at {self.commit[:12]}: "
                                f"{result.stderr.decode(errors='replace').strip()}")
            return result.stdout
        try:
            target = safe_file(self.root, path)
        except ValueError:
            return None
        return target.read_bytes() if target.is_file() else None

    def json(self, path):
        """The parsed file, None when absent; a file that exists but is not JSON raises ReadError."""
        data = self.read(path)
        if data is None:
            return None
        try:
            return json.loads(data)
        except ValueError as error:
            where = self.commit[:12] if self.commit is not None else "the head"
            raise ReadError(f"{path} at {where} is not JSON ({error})") from None


def row_waves(catalog, row):
    """(run id of lanes.sealed_base, every wave the row names). The second mirrors landscape.py: a
    lane run id ``<catalog>-<layer_id>-<run-id>`` names a wave too, so emptying sealed_base
    cannot make a new-wave row grandfathered."""
    lanes = row.get("lanes") if isinstance(row.get("lanes"), dict) else {}
    sealed_base = lanes.get("sealed_base") or DEFAULT_SEALED_BASE
    run_id = (run_id_of(sealed_base) if isinstance(sealed_base, str) and sealed_base.startswith(SEALED_BASE_PREFIX)
              else None)
    prefix = f"{catalog}-{row.get('layer_id')}-"
    named = {run_id}
    for lane in LANES:
        lane_run = (lanes.get(lane) or {}).get("run_id") if isinstance(lanes.get(lane), dict) else None
        if isinstance(lane_run, str) and lane_run.startswith(prefix):
            named.add(lane_run[len(prefix):])
    return run_id, named


def load_rows(side):
    """{(catalog, layer_id, run_id): row} for every ledger row carrying the verdict fields. The rows
    come from build_verdicts.LEDGER_FILES, the files the published wave documents are generated
    from, never from the manifest (which a pull request could point at a decoy ledger)."""
    rows = {}
    for catalog, path in sorted(LEDGER_FILES.items()):
        document = side.json(path) or {}
        for row in document.get("layers") or []:
            if not (isinstance(row, dict) and isinstance(row.get("layer_id"), str)
                    and "winners" in row and "lanes" in row):
                continue
            run_id, _named = row_waves(catalog, row)
            rows[(row.get("catalog", catalog), row["layer_id"], run_id)] = row
    return rows


def ledger_binding_violations(head):
    """The head's landscape manifest must name exactly build_verdicts.LEDGER_FILES: scripts/landscape.py
    validates the ledgers the manifest names, and the published verdicts come from LEDGER_FILES."""
    manifest = head.json(MANIFEST)
    catalogs = manifest.get("catalogs") if isinstance(manifest, dict) else None
    if catalogs == LEDGER_FILES:
        return []
    return [{"row": "repository", "message": f"{MANIFEST}#/catalogs is {catalogs!r}, not the ledgers the published "
             f"verdicts are generated from ({LEDGER_FILES!r}); scripts/landscape.py would validate other files "
             "than the ones build_verdicts.py publishes"}]


def load_waves(side):
    """run_id -> registry entry at this side (empty when the registry is absent or malformed)."""
    document = side.json(WAVE_REGISTRY) or {}
    waves = {}
    for entry in document.get("waves") or []:
        if isinstance(entry, dict) and isinstance(entry.get("run_id"), str):
            waves[entry["run_id"]] = entry
    return waves


def label(key):
    return f"{key[0]}/{key[1]}@{key[2]}"


def without_platform_status(winners):
    if not isinstance(winners, list):
        return winners
    return [{k: v for k, v in winner.items() if k != "platform_status"} if isinstance(winner, dict) else winner
            for winner in winners]


def change_kind(old, new):
    if old is None:
        return "added"
    if all(old.get(field) == new.get(field) for field in VERDICT_FIELDS):
        return None
    if (all(old.get(field) == new.get(field) for field in VERDICT_FIELDS if field != "winners")
            and without_platform_status(old.get("winners")) == without_platform_status(new.get("winners"))):
        return "platform_status"
    return "changed"


def is_withheld_packet_key(key):
    """Whether #124's --withhold-labels policy withholds ``key`` at any depth of a sealed packet."""
    lowered = key.lower() if isinstance(key, str) else ""
    return (lowered in POPULARITY_RECENCY_FIELDS or lowered.endswith("_at")
            or any(token in lowered for token in POPULARITY_TOKENS)
            or lowered in UPSTREAM_RELEASE_FIELDS or lowered in COPY_WITHHELD_FIELDS or lowered == "notes"
            or any(token in lowered for token in WITHHELD_KEY_TOKENS))


def withheld_packet_keys(packet):
    """Labels ("candidates[].upstream.stars", ...) of every withheld key the packet carries, at any
    depth; the packet's own top-level PACKET_OWN_KEYS are kept."""
    found = set()

    def walk(value, label):
        if isinstance(value, dict):
            for key, item in value.items():
                path = f"{label}.{key}" if label else str(key)
                if not label and isinstance(key, str) and key.lower() in PACKET_OWN_KEYS:
                    continue
                if is_withheld_packet_key(key):
                    found.add(path)
                    continue
                walk(item, path)
        elif isinstance(value, list):
            for item in value:
                walk(item, f"{label}[]")

    walk(packet, "")
    return sorted(found)


def retained_packet_name(manifest, packet_sha256, catalog, layer_id):
    """(issue, name) of the run manifest's retained_packets entry holding ``packet_sha256``."""
    retained = manifest.get(RUN_MANIFEST_RETAINED_PACKETS) if isinstance(manifest, dict) else None
    if not isinstance(retained, list):
        return f"the run manifest has no {RUN_MANIFEST_RETAINED_PACKETS} list naming the packets it retains", None
    names = [item.get("name") for item in retained
             if isinstance(item, dict) and item.get("sha256") == packet_sha256]
    if not names:
        return (f"the row's packet (packet_sha256 {packet_sha256}) is not listed in the run manifest's "
                f"{RUN_MANIFEST_RETAINED_PACKETS}"), None
    preferred = f"{catalog}__{layer_id}.json"
    name = preferred if preferred in names else names[0]
    posix = PurePosixPath(name) if isinstance(name, str) else None
    if posix is None or posix.name != name or name in {"", ".", ".."} or not name.endswith(".json"):
        return f"the run manifest's retained packet name {name!r} is not a plain .json file name", None
    return None, name


def sealed_packet(head, sealed_base, catalog, layer_id, manifest=None, manifest_entry=None):
    """(issue, candidates_by_key, packet_sha256) for the sealed packet the row's lanes judged, the
    one place the packet resolution lives (review finding 6, #124's layout). The packet is the
    run manifest entry's packet_sha256, found through the manifest's retained_packets under
    <sealed_base>/packets/, with packets/SHA256SUMS equal to the manifest's packets_sha256sums and
    listing it, and it carries no withheld key. ``issue`` is None when all of that holds."""
    directory = f"{sealed_base}/{RETAINED_PACKETS_DIR}"
    if not isinstance(manifest_entry, dict):
        return (f"the row's sealed packet cannot be resolved: {catalog}/{layer_id} has no valid entry in its "
                f"run manifest {sealed_base}/{RUN_MANIFEST_NAME}"), None, None
    packet_sha256 = manifest_entry.get("packet_sha256")
    if not isinstance(packet_sha256, str) or not packet_sha256:
        return f"the run manifest records no packet_sha256 for {catalog}/{layer_id}", None, None
    issue, name = retained_packet_name(manifest, packet_sha256, catalog, layer_id)
    if issue:
        return issue, None, None
    path = f"{directory}/{name}"
    packet_bytes, sums_bytes = head.read(path), head.read(f"{directory}/{PACKET_SUMS_NAME}")
    if packet_bytes is None or sums_bytes is None:
        return (f"the wave's sealed packets ({path} and {directory}/{PACKET_SUMS_NAME}) are absent, so the "
                "row's winners cannot be resolved from the packet both lanes judged; failing closed"), None, None
    actual = sha256(packet_bytes)
    if actual != packet_sha256:
        return f"{path} (sha256 {actual}) is not the run manifest's packet_sha256 {packet_sha256}", None, None
    with tempfile.TemporaryDirectory() as scratch:
        sums_path = Path(scratch) / PACKET_SUMS_NAME
        sums_path.write_bytes(sums_bytes)
        listed = parse_sha256sums(sums_path).get(name)
    if listed != actual:
        return f"{path} (sha256 {actual}) is not the one {directory}/{PACKET_SUMS_NAME} lists", None, None
    if sums_bytes.decode("utf-8", errors="replace") != manifest.get(RUN_MANIFEST_PACKET_SUMS):
        return (f"{directory}/{PACKET_SUMS_NAME} is not the run manifest's {RUN_MANIFEST_PACKET_SUMS}"), None, None
    try:
        packet = json.loads(packet_bytes)
    except ValueError:
        return f"{path} is not JSON", None, None
    if not isinstance(packet, dict):
        return f"{path} is not a JSON object", None, None
    withheld = withheld_packet_keys(packet)
    if withheld:
        return (f"{path} carries withheld keys {withheld}; a new wave's lanes judge --withhold-labels packets"), \
            None, None
    candidates = {candidate.get("key"): candidate for candidate in (packet.get("candidates") or [])
                  if isinstance(candidate, dict)}
    return None, candidates, actual


def resolved_component_ids(winner_keys, candidates):
    """(component ids, unknown keys) for a lane's winner_keys through the sealed packet."""
    unknown = sorted(key for key in winner_keys if key not in candidates)
    return sorted({derive_component_id(candidates[key]) for key in winner_keys if key in candidates}), unknown


def two_family_adjudication_issue(raw, chosen_lanes):
    """Independent of judge_adjudication: judges of both lane families each cover both
    presentation orders, every judgment prefers one lane and none carries a refuting vote. A
    third-family judge is recorded but not required. Returns (issue, winner_lane)."""
    judgments = raw.get("judgments") if isinstance(raw, dict) else None
    if not isinstance(judgments, list) or not judgments:
        return "the adjudication records no judgments", None
    orders, lanes = {}, set()
    for judgment in judgments:
        if not isinstance(judgment, dict):
            return "an adjudication judgment is not an object", None
        if judgment.get("refuting_votes") != 0:
            return f"a judgment carries refuting_votes {judgment.get('refuting_votes')!r}", None
        judge = judgment.get("judge") if isinstance(judgment.get("judge"), dict) else {}
        orders.setdefault(judge.get("family"), set()).add(judgment.get("claude_position"))
        lanes.add(judgment.get("preferred_lane"))
    missing = [f"{family} (orders {sorted(orders.get(family, set()) - {None})})"
               for family in sorted(set(LANE_FAMILIES.values())) if orders.get(family) != {"A", "B"}]
    if missing:
        return ("the adjudication needs judges of both lane families in both presentation orders; missing: "
                + ", ".join(missing)), None
    if len(lanes) != 1 or not lanes <= chosen_lanes:
        return f"the adjudication's judgments do not all prefer one lane (preferred: {sorted(map(str, lanes))})", None
    return None, next(iter(lanes))


class RowCheck:
    def __init__(self, head, key, row, registered, waves, violations):
        self.head, self.key, self.row = head, key, row
        self.registered, self.waves, self.violations = registered, waves, violations
        self.lanes = row.get("lanes") if isinstance(row.get("lanes"), dict) else {}

    def fail(self, message):
        self.violations.append({"row": label(self.key), "message": message})

    def registered_file(self, path, what):
        """The file's bytes when it exists at the head and manifests/evidence.json registers it with
        its sha256; None (after recording the violation) otherwise."""
        data = self.head.read(path)
        if data is None:
            self.fail(f"{what} {path} is missing")
            return None
        record = self.registered.get(path)
        if record is None:
            self.fail(f"{what} {path} is not registered in manifests/evidence.json")
            return None
        if record.get("sha256") != sha256(data):
            self.fail(f"{what} {path}: manifests/evidence.json registers sha256 {record.get('sha256')} but the file "
                      f"is {sha256(data)}")
            return None
        return data

    def run(self):
        catalog, layer_id, run_id = self.key
        sealed_base = self.lanes.get("sealed_base")
        if run_id is None or not isinstance(sealed_base, str):
            self.fail("a new-wave row needs lanes.sealed_base evidence/artifacts/layer-verdicts-<run-id>")
            return
        self.check_wave(run_id)
        manifest, manifest_entry = self.check_run_manifest(sealed_base, run_id)
        returns = self.check_lanes(sealed_base, run_id, manifest_entry)
        recomputed, packet_sha256 = self.recompute_agreement(returns, manifest_entry)
        agreement, status = self.lanes.get("agreement"), self.row.get("verdict_status")
        self.check_adjudication_binding(sealed_base, manifest_entry, agreement, status)
        issue, candidates, sealed_packet_sha256 = sealed_packet(self.head, sealed_base, catalog, layer_id,
                                                                manifest, manifest_entry)
        if issue:
            self.fail(issue)
        elif packet_sha256 is not None and sealed_packet_sha256 != packet_sha256:
            self.fail(f"the sealed packet's sha256 {sealed_packet_sha256} is not the packet_sha256 the lanes judged "
                      f"({packet_sha256})")
            candidates = None
        if returns:
            self.check_overturn_protocol(returns)
        if status != "recorded":
            if self.row.get("winners"):
                self.fail(f"a {status!r} row carries winners; only a recorded verdict names winners")
            if self.row.get("alternatives") or self.row.get("verdict_overturn_when"):
                self.fail(f"a {status!r} row carries alternatives or verdict_overturn_when; record_verdicts.py "
                          "publishes them only with a recorded verdict")
            return
        chosen = None
        if agreement == "same_winner":
            chosen = "claude"
        elif agreement == "codex_absent":
            chosen = "claude"
            self.check_single_lane()
        elif agreement == "disagree":
            chosen = self.check_adjudication(sealed_base, packet_sha256, set(returns))
        else:
            self.fail(f"a recorded verdict needs agreement same_winner, disagree or codex_absent (got {agreement!r})")
        if chosen is None or chosen not in returns or candidates is None or recomputed != agreement:
            return
        expected, unknown = resolved_component_ids(returns[chosen].get("winner_keys") or [], candidates)
        if unknown:
            self.fail(f"the {chosen} lane's winner_keys {unknown} are not candidates of the sealed packet")
            return
        winners = [winner for winner in self.row.get("winners") or [] if isinstance(winner, dict)]
        actual = sorted(str(winner.get("component_id")) for winner in winners)
        if actual != expected:
            self.fail(f"row winners {actual} are not the {chosen} lane's winner_keys resolved through the sealed "
                      f"packet ({expected})")
            return
        self.check_winner_fields(returns[chosen], chosen, winners, candidates)
        self.check_published_alternatives(returns, chosen, winners)

    def check_winner_fields(self, sealed_return, lane, winners, candidates):
        """The fields record_verdicts.build_winners copies from the chosen lane and the packet."""
        chosen = {derive_component_id(candidates[key]): candidates[key]
                  for key in sealed_return.get("winner_keys") or [] if key in candidates}
        pins = {component_id: candidate.get("pin") for component_id, candidate in chosen.items()}
        why_selected = sanitize_value(sealed_return.get("why_selected"))
        ledger_path = LEDGER_FILES.get(self.key[0])
        for winner in winners:
            component_id = winner.get("component_id")
            candidate = chosen.get(component_id) or {}
            if winner.get("repository") != candidate.get("repository"):
                self.fail(f"winner {component_id}: repository {winner.get('repository')!r} is not the sealed packet "
                          f"candidate's {candidate.get('repository')!r}")
            recipe_ref = candidate.get("recipe_ref") or ledger_path
            if winner.get("recipe_ref") != recipe_ref:
                self.fail(f"winner {component_id}: recipe_ref {winner.get('recipe_ref')!r} is not {recipe_ref!r} "
                          "(the sealed packet candidate's, else the row's ledger)")
            if winner.get("evidence_class") != sealed_return.get("winner_evidence_class"):
                self.fail(f"winner {component_id}: evidence_class {winner.get('evidence_class')!r} is not the {lane} "
                          f"lane's winner_evidence_class {sealed_return.get('winner_evidence_class')!r}")
            if winner.get("why_selected") != why_selected:
                self.fail(f"winner {component_id}: why_selected differs from the sealed {lane} lane return")
            if pins.get(component_id) and winner.get("pin") != pins[component_id]:
                self.fail(f"winner {component_id}: pin {winner.get('pin')!r} is not the sealed packet's "
                          f"{pins[component_id]!r}")

    def check_published_alternatives(self, returns, lane, winners):
        """The alternatives and verdict_overturn_when record_verdicts.py derives from the sealed
        returns, compared on the fields the wave document publishes."""
        try:
            identities, aliases = load_canonical_index(self.head.root)
        except (OSError, KeyError, TypeError, ValueError) as error:
            self.fail(f"the canonical repository index cannot be loaded to derive the alternatives ({error!r})")
            return
        computed, _gaps = build_alternatives(returns, identities, aliases, None, None)
        winner_ids = {canonical(safe_identity(winner.get("repository")), aliases) for winner in winners
                      if safe_identity(winner.get("repository"))}
        expected = [alternative for alternative in sanitize_value(computed)
                    if canonical(safe_identity(alternative["repository"]), aliases) not in winner_ids]

        def published(alternatives):
            return [{field: alternative.get(field) for field in PUBLISHED_ALTERNATIVE_FIELDS}
                    if isinstance(alternative, dict) else alternative for alternative in alternatives or []]

        if published(self.row.get("alternatives")) != published(expected):
            self.fail(f"alternatives are not the ones record_verdicts.py derives from the sealed lane returns "
                      f"(expected {[a.get('repository') for a in expected]}, got "
                      f"{[a.get('repository') for a in self.row.get('alternatives') or [] if isinstance(a, dict)]}, "
                      f"compared on {', '.join(PUBLISHED_ALTERNATIVE_FIELDS)})")
        overturn = sanitize_value(returns[lane].get("overturn_when"))
        if self.row.get("verdict_overturn_when") != overturn:
            self.fail(f"verdict_overturn_when differs from the sealed {lane} lane return's overturn_when")

    def check_overturn_protocol(self, returns):
        try:
            expected = sanitize_value(choose_overturn_protocol(returns))
        except (KeyError, TypeError):
            expected = None
        if self.row.get("overturn_protocol") != expected:
            self.fail("overturn_protocol is not the one record_verdicts.py chooses from the sealed lane returns")

    def check_wave(self, run_id):
        entry = self.waves.get(run_id)
        if entry is None:
            self.fail(f"wave {run_id}'s document is not registered in {WAVE_REGISTRY}")
            return
        path = entry.get("path")
        data = self.head.read(path) if isinstance(path, str) else None
        if data is None:
            self.fail(f"wave {run_id}'s registered document {path!r} is missing")
        elif sha256(data) != entry.get("sha256"):
            self.fail(f"wave {run_id}'s document {path} differs from its sha256 in {WAVE_REGISTRY}")

    def check_run_manifest(self, sealed_base, run_id):
        """(run manifest, the row's entry in it); either is None after recording why. The row's
        lanes.run_manifest_sha256 must be the sha256 of that run manifest (#124)."""
        catalog, layer_id, _ = self.key
        path = f"{sealed_base}/{RUN_MANIFEST_NAME}"
        data = self.registered_file(path, "the run manifest")
        if data is None:
            return None, None
        stored = self.lanes.get(RUN_MANIFEST_SHA256_FIELD)
        if stored is None:
            self.fail(f"lanes.{RUN_MANIFEST_SHA256_FIELD} is absent; a new-wave row is bound to the run manifest "
                      f"it was recorded with ({path}, {sha256(data)})")
        elif stored != sha256(data):
            self.fail(f"lanes.{RUN_MANIFEST_SHA256_FIELD} {stored} is not the sha256 of {path} ({sha256(data)})")
        try:
            manifest = json.loads(data)
        except ValueError:
            self.fail(f"{path} is not JSON")
            return None, None
        # The whole lanes object (with each lane normalized to an object), so a run_manifest_row_issue
        # that also binds lanes.adjudication_sha256 (#124) sees it.
        lanes_field = {**self.lanes, **{lane: self.lanes.get(lane) if isinstance(self.lanes.get(lane), dict) else {}
                                        for lane in LANES}}
        issue = run_manifest_row_issue(manifest, run_id, catalog, layer_id, lanes_field)
        if issue:
            self.fail(issue)
            return manifest, None
        return manifest, next(entry for entry in manifest["packets"] if isinstance(entry, dict)
                              and (entry.get("catalog"), entry.get("layer_id")) == (catalog, layer_id))

    def check_adjudication_binding(self, sealed_base, manifest_entry, agreement, status):
        """#124: a sealed adjudication (a recorded disagreement or a sealed split) is bound by the row's
        lanes.adjudication_sha256 and by the run manifest entry's adjudication {outcome, sealed, sha256};
        a recorded disagree row must carry it, and only a disagree row may."""
        stored = self.lanes.get(ADJUDICATION_SHA256_FIELD)
        if agreement == "disagree" and status == "recorded" and stored is None:
            self.fail(f"lanes.{ADJUDICATION_SHA256_FIELD} is absent; a recorded disagree row binds its sealed "
                      "adjudication")
            return
        if stored is None:
            listed = ((manifest_entry or {}).get(RUN_MANIFEST_ADJUDICATION) or {})
            if isinstance(listed, dict) and listed.get("outcome") == "sealed":
                self.fail(f"the run manifest lists a sealed adjudication but the row has no "
                          f"lanes.{ADJUDICATION_SHA256_FIELD}")
            return
        if agreement != "disagree":
            self.fail(f"lanes.{ADJUDICATION_SHA256_FIELD} is only meaningful on a disagree row (agreement "
                      f"{agreement!r})")
            return
        claude_run = (self.lanes.get("claude") or {}).get("run_id") if isinstance(self.lanes.get("claude"), dict) else None
        path = f"{sealed_base}/adjudication/{claude_run}.json"
        data = self.head.read(path)
        if data is None:
            self.fail(f"lanes.{ADJUDICATION_SHA256_FIELD} names an adjudication but {path} is missing")
        elif sha256(data) != stored:
            self.fail(f"lanes.{ADJUDICATION_SHA256_FIELD} {stored} is not the sha256 of {path} ({sha256(data)})")
        if manifest_entry is None:
            return
        listed = manifest_entry.get(RUN_MANIFEST_ADJUDICATION)
        if not (isinstance(listed, dict) and listed.get("outcome") == "sealed" and listed.get("sha256") == stored):
            self.fail(f"the run manifest's adjudication of {self.key[0]}/{self.key[1]} ({listed!r}) is not the sealed "
                      f"adjudication lanes.{ADJUDICATION_SHA256_FIELD} names ({stored})")

    def check_lanes(self, sealed_base, run_id, manifest_entry):
        catalog, layer_id, _ = self.key
        returns = {}
        for lane in LANES:
            field = self.lanes.get(lane) if isinstance(self.lanes.get(lane), dict) else {}
            sealed = field.get("sealed_sha256")
            if not sealed:
                outcome = ((manifest_entry or {}).get("lanes") or {}).get(lane) or {}
                if manifest_entry is not None and outcome.get("outcome") not in ("rejected", "missing"):
                    self.fail(f"the unsealed {lane} lane is not recorded as rejected or missing in the run manifest")
                continue
            expected_run = f"{catalog}-{layer_id}-{run_id}"
            if field.get("run_id") != expected_run:
                self.fail(f"lanes.{lane}.run_id must be {expected_run!r} (got {field.get('run_id')!r})")
                continue
            path = f"{sealed_base}/{lane}/{expected_run}.json"
            data = self.head.read(path)
            if data is None:
                self.fail(f"the sealed {lane} lane return {path} is missing")
                continue
            if sha256(data) != sealed:
                self.fail(f"lanes.{lane}.sealed_sha256 {sealed} is stale: {path} is {sha256(data)}")
                continue
            if self.registered_file(path, f"the sealed {lane} lane return") is None:
                continue
            try:
                sealed_return = json.loads(data)
            except ValueError:
                self.fail(f"the sealed {lane} lane return {path} is not JSON")
                continue
            if not isinstance(sealed_return, dict):
                self.fail(f"the sealed {lane} lane return {path} is not an object")
                continue
            issue = lane_model_issue(lane, sealed_return.get("model"))
            if issue:
                self.fail(f"the sealed {lane} lane return: {issue}")
            returns[lane] = sealed_return
        families = [(ret.get("model") or {}).get("family") if isinstance(ret.get("model"), dict) else None
                    for ret in returns.values()]
        if len(families) == 2 and families[0] == families[1]:
            self.fail(f"both lane returns come from the same model family {families[0]!r}; the two lanes must be "
                      "distinct families")
        return returns

    def recompute_agreement(self, returns, manifest_entry):
        """(recomputed agreement, the packet_sha256 both lanes judged) from the sealed returns."""
        recorded = self.lanes.get("agreement")
        packets = {lane: ret.get("packet_sha256") for lane, ret in returns.items()}
        packet_sha256 = None
        if len(set(packets.values())) > 1:
            self.fail(f"the sealed lane returns judged different packets ({packets}); agreement cannot be recomputed")
            return None, None
        if packets:
            packet_sha256 = next(iter(packets.values()))
            listed = (manifest_entry or {}).get("packet_sha256")
            if manifest_entry is not None and listed != packet_sha256:
                self.fail(f"the lanes' packet_sha256 {packet_sha256} is not the run manifest's packet ({listed})")
        keys = {}
        for lane, ret in returns.items():
            winner_keys = ret.get("winner_keys")
            if not (isinstance(winner_keys, list) and all(isinstance(key, str) for key in winner_keys)):
                self.fail(f"the sealed {lane} lane return has no winner_keys list")
                return None, packet_sha256
            keys[lane] = set(winner_keys)
        if len(keys) == 2:
            recomputed = "same_winner" if keys["claude"] == keys["codex"] else "disagree"
        elif "claude" in keys:
            recomputed = "codex_absent"
        else:
            recomputed = "pending"
        if recomputed != recorded:
            self.fail(f"lanes.agreement is {recorded!r} but the sealed lane returns recompute to {recomputed!r} "
                      f"(winner_keys: {({lane: sorted(value) for lane, value in keys.items()})})")
        return recomputed, packet_sha256

    def check_adjudication(self, sealed_base, packet_sha256, sealed_lanes):
        claude_run = (self.lanes.get("claude") or {}).get("run_id")
        path = f"{sealed_base}/adjudication/{claude_run}.json"
        data = self.registered_file(path, "the disagree row's sealed adjudication")
        if data is None:
            return None
        try:
            raw = json.loads(data)
        except ValueError:
            self.fail(f"{path} is not JSON")
            return None
        issue, winner = two_family_adjudication_issue(raw, sealed_lanes)
        if issue:
            self.fail(f"{path}: {issue}")
            winner = None
        issue, result = judge_adjudication(raw, grandfathered=False, packet_sha256=packet_sha256)
        if issue:
            self.fail(f"{path}: {issue}")
            return None
        if result["winner_lane"] is None:
            self.fail(f"{path} is a split and cannot record a winner"
                      + (f" ({result['split_reason']})" if result.get("split_reason") else ""))
            return None
        return winner

    def check_single_lane(self):
        catalog, layer_id, _ = self.key
        path = self.lanes.get("single_lane_decision")
        if not isinstance(path, str) or not path:
            self.fail("a recorded codex_absent row needs lanes.single_lane_decision")
            return
        posix = PurePosixPath(path)
        name = posix.name
        if (path.startswith(SEALED_BASE_PREFIX) or path.startswith(WAVE_DOCUMENT_PREFIX)
                or path in {entry.get("path") for entry in self.waves.values()}
                or (name.startswith("layer-verdicts-") and name.endswith(".json")) or name == RUN_MANIFEST_NAME):
            self.fail(f"lanes.single_lane_decision {path!r} is a wave document, run manifest or sealed verdict "
                      "artifact, not a decision record")
            return
        if (posix.is_absolute() or ".." in posix.parts or path != posix.as_posix()
                or not path.startswith(SINGLE_LANE_DECISION_DIR)):
            self.fail(f"lanes.single_lane_decision {path!r} must be a file under {SINGLE_LANE_DECISION_DIR}")
            return
        data = self.head.read(path)
        if data is None:
            self.fail(f"lanes.single_lane_decision {path!r} does not exist")
            return
        stored = self.lanes.get(SINGLE_LANE_DECISION_SHA256_FIELD)
        if stored is None:
            self.fail(f"lanes.{SINGLE_LANE_DECISION_SHA256_FIELD} is absent; a recorded codex_absent row binds its "
                      f"decision record {path} ({sha256(data)})")
        elif stored != sha256(data):
            self.fail(f"lanes.{SINGLE_LANE_DECISION_SHA256_FIELD} {stored} does not match {path} ({sha256(data)})")
        wanted = f"{SINGLE_LANE_MARKER} {catalog}/{layer_id}"
        if wanted not in (line.strip() for line in data.decode("utf-8", errors="replace").splitlines()):
            self.fail(f"{path} has no line {wanted!r} authorizing this row alone")


def platform_status_violations(key, old, new, context):
    violations = []
    old_winners = {winner.get("component_id"): winner for winner in old.get("winners") or [] if isinstance(winner, dict)}
    for winner in new.get("winners") or []:
        if not isinstance(winner, dict):
            continue
        before = (old_winners.get(winner.get("component_id")) or {}).get("platform_status") or {}
        declared = winner.get("platform_status") if isinstance(winner.get("platform_status"), dict) else {}
        for platform in platform_evidence.PLATFORMS:
            if declared.get(platform) == before.get(platform):
                continue
            derived = platform_evidence.platform_status(platform, winner, context)
            if declared.get(platform) != derived.status:
                violations.append({"row": label(key), "message": (
                    f"winner {winner.get('component_id')}: platform_status.{platform} changed to "
                    f"{declared.get(platform)!r} but scripts/platform_status.py derives {derived.status!r} "
                    f"({derived.reason}) from the registered receipts")})
    return violations


def json_equivalent(before, after):
    """True when two file contents are equal as bytes, or both parse as JSON to equal values (review
    of #123, finding 3: a pure formatting change of a generated document is not a value change)."""
    if before == after:
        return True
    if before is None or after is None:
        return False
    try:
        return json.loads(before) == json.loads(after)
    except ValueError:
        return False


def registry_values(entry):
    """A wave registry entry without its document sha256, which a pure reformat of the document changes."""
    return {key: value for key, value in entry.items() if key != "sha256"} if isinstance(entry, dict) else entry


def registry_equivalent(before, after):
    """json_equivalent for the wave registry, ignoring each entry's document sha256 (the entries'
    sha256 against their documents is checked by wave_freeze_violations and build_verdicts.py)."""
    def values(data):
        document = json.loads(data)
        if isinstance(document, dict) and isinstance(document.get("waves"), list):
            document = {**document, "waves": [registry_values(entry) for entry in document["waves"]]}
        return document

    if json_equivalent(before, after):
        return True
    if before is None or after is None:
        return False
    try:
        return values(before) == values(after)
    except ValueError:
        return False


def wave_freeze_violations(base, head, base_waves, head_waves):
    """Review finding 4: every base registry entry except the newest (and every grandfathered one)
    is unchanged at the head, and so is the document it registers, compared on parsed values: a
    reformatted document passes when its registry sha256 is updated to the reformatted bytes
    (build_verdicts.py --check then decides whether the reformat is the generator's)."""
    violations = []
    newest = max(base_waves) if base_waves else None
    for run_id, entry in sorted(base_waves.items()):
        if run_id == newest and run_id not in GRANDFATHERED_RUN_IDS:
            continue
        where = f"wave {run_id}"
        path = entry.get("path")
        head_entry = head_waves.get(run_id)
        base_document = base.read(path) if isinstance(path, str) else None
        head_document = head.read(path) if isinstance(path, str) else None
        same_document = json_equivalent(base_document, head_document)
        if head_entry is None or registry_values(head_entry) != registry_values(entry) or (
                head_entry.get("sha256") != entry.get("sha256") and not same_document):
            violations.append({"row": where, "message": f"the frozen registry entry of wave {run_id} in "
                               f"{WAVE_REGISTRY} was changed or removed (only the newest wave may change)"})
        elif base_document != head_document and (
                head_document is None or sha256(head_document) != head_entry.get("sha256")):
            violations.append({"row": where, "message": f"the frozen wave {run_id}'s registry sha256 "
                               f"{head_entry.get('sha256')} is not the sha256 of its document {path}"})
        if isinstance(path, str) and not same_document:
            violations.append({"row": where, "message": f"the frozen wave document {path} was rewritten"})
    return violations


def wave_rank(run_id):
    """Order of run ids: the grandfathered wave (or no parseable sealed base) is the oldest; later
    waves are dated run ids and sort as text."""
    return (0, "") if run_id is None or run_id in GRANDFATHERED_RUN_IDS else (1, run_id)


def row_continuity_violations(base_rows, head_rows, head_waves):
    """Review of #123, finding 1: a row of the base cannot disappear, roll back to an older wave or to
    the grandfathered one, or move to any wave other than the newest registered one (where it then
    needs the full new-wave evidence, as an added key). Each (catalog, layer_id) has one row."""
    def by_layer(rows):
        layers = {}
        for key in rows:
            layers.setdefault(key[:2], []).append(key)
        return layers

    base_layers, head_layers = by_layer(base_rows), by_layer(head_rows)
    registered = [run_id for run_id in head_waves if run_id not in GRANDFATHERED_RUN_IDS]
    newest = max(registered) if registered else None
    violations = []
    for layer, keys in sorted(head_layers.items()):
        if len(keys) > 1:
            violations.append({"row": f"{layer[0]}/{layer[1]}", "message": (
                f"the head ledger holds {len(keys)} rows for this layer "
                f"({', '.join(sorted(label(key) for key in keys))}); a layer has one row")})
    for layer, base_keys in sorted(base_layers.items()):
        head_keys = head_layers.get(layer) or []
        for base_key in base_keys:
            if not head_keys:
                violations.append({"row": label(base_key), "message": (
                    "the row present at the base is missing at the head; a verdict row is never deleted")})
                continue
            _run, base_named = row_waves(base_key[0], base_rows[base_key])
            base_grandfathered = all(wave in GRANDFATHERED_RUN_IDS for wave in base_named)
            for head_key in head_keys:
                before, after = base_key[2], head_key[2]
                if before == after:
                    continue
                _run, head_named = row_waves(head_key[0], head_rows[head_key])
                if not base_grandfathered and all(wave in GRANDFATHERED_RUN_IDS for wave in head_named):
                    message = (f"the row moves from wave {before} back to the grandfathered wave {after}; a "
                               "new-wave verdict never rolls back to grandfathered content")
                elif wave_rank(after) < wave_rank(before):
                    message = (f"the row moves from wave {before} to the older wave {after}; a verdict row's "
                               "run id never goes back")
                elif after != newest:
                    message = (f"the row moves from wave {before} to wave {after}, which is not the newest "
                               f"registered wave ({newest or 'no new wave is registered'}); a row moves only to "
                               "the newest registered wave")
                else:
                    continue
                violations.append({"row": label(base_key), "message": message})
    return violations


def changed_verdict_paths(head_root, base):
    """Paths under VERDICT_PATHSPECS that differ between ``base`` and the head checkout (tracked
    changes and untracked files)."""
    specs = [f":(glob){spec}**" if spec.endswith("/") else f":(glob){spec}/**" for spec in VERDICT_PATHSPECS]
    tracked = git(head_root, "diff", "--name-only", "--no-renames", base, "--", *specs, check=False)
    untracked = git(head_root, "ls-files", "--others", "--exclude-standard", "--", *specs, check=False)
    return sorted({line for result in (tracked, untracked) if result.returncode == 0
                   for line in result.stdout.decode().splitlines() if line})


def changed_trust_paths(head_root, base):
    """TRUST_PATHS files that differ between ``base`` and the head checkout."""
    tracked = git(head_root, "diff", "--name-only", "--no-renames", base, "--", *TRUST_PATHS, check=False)
    untracked = git(head_root, "ls-files", "--others", "--exclude-standard", "--", *TRUST_PATHS, check=False)
    return sorted({line for result in (tracked, untracked) if result.returncode == 0
                   for line in result.stdout.decode().splitlines() if line})


def run_repo_validators(head_root):
    violations = []
    for name, (script, *arguments) in REPO_VALIDATORS:
        result = subprocess.run([sys.executable, str(ROOT / script), *arguments, str(head_root)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-20:])
            violations.append({"row": "repository", "message": f"{name} failed (exit {result.returncode}):\n{tail}"})
    return violations


def evaluate(root, base, head_root=None, *, validators=run_repo_validators):
    """The gate's report for ``base`` (a resolved commit) against the checkout at ``head_root``."""
    root = Path(root)
    head_root = Path(head_root or root)
    base_side, head_side = Side(root, base), Side(head_root)
    base_rows, head_rows = load_rows(base_side), load_rows(head_side)
    base_waves, head_waves = load_waves(base_side), load_waves(head_side)
    changes, violations = [], []
    registered = evidence_files(head_root)
    context = None
    for key, row in sorted(head_rows.items(), key=lambda item: tuple(map(str, item[0]))):
        kind = change_kind(base_rows.get(key), row)
        if kind is None:
            continue
        _run_id, named = row_waves(key[0], row)
        grandfathered = all(wave in GRANDFATHERED_RUN_IDS for wave in named)
        changes.append({"row": label(key), "kind": kind, "grandfathered": grandfathered})
        if grandfathered:
            continue
        # Every changed platform value of a non-grandfathered row must be the one the receipts derive;
        # a change to platform_status alone needs nothing else.
        context = context or platform_evidence.load_context(head_root)
        violations.extend(platform_status_violations(key, base_rows.get(key) or {}, row, context))
        if kind != "platform_status":
            RowCheck(head_side, key, row, registered, head_waves, violations).run()
    removed = [label(key) for key in sorted(set(base_rows) - set(head_rows), key=lambda k: tuple(map(str, k)))]
    violations.extend(row_continuity_violations(base_rows, head_rows, head_waves))
    violations.extend(wave_freeze_violations(base_side, head_side, base_waves, head_waves))
    # Compared on parsed values (finding 3): a regenerated wave document or registry that only
    # changes formatting (and the document sha256 it records) is not a wave change.
    waves_changed = ({run_id: registry_values(entry) for run_id, entry in base_waves.items()}
                     != {run_id: registry_values(entry) for run_id, entry in head_waves.items()}) or any(
        not json_equivalent(base_side.read(entry["path"]), head_side.read(entry["path"]))
        for entry in list(base_waves.values()) + list(head_waves.values()) if isinstance(entry.get("path"), str))
    violations.extend(ledger_binding_violations(head_side))
    artifacts = changed_verdict_paths(head_root, base)
    # A sealed artifact counts by its bytes (they are hashed); a generated catalog document by its
    # parsed values, so a pure reformat of it is not a verdict change.
    value_changes = [path for path in artifacts if path.startswith(SEALED_BASE_PREFIX)
                     or not (registry_equivalent if path == WAVE_REGISTRY else json_equivalent)(
                         base_side.read(path), head_side.read(path))]
    touched = bool(changes or removed or waves_changed or artifacts)
    # A verdict change is a row, a wave or a sealed/published verdict artifact; an edit to the
    # ledgers' other fields (catalogs/landscape/) may land together with a rules change.
    verdict_changed = bool(changes or removed or waves_changed
                           or any(not path.startswith("catalogs/landscape/") for path in value_changes))
    trust = changed_trust_paths(head_root, base)
    if verdict_changed and trust:
        violations.append({"row": "repository", "message": (
            f"this change edits verdict rows, waves or sealed verdict artifacts and also the gate's trust base "
            f"({', '.join(trust)}); land the rules change in its own pull request first")})
    if touched and validators is not None:
        violations.extend(validators(head_root))
    return {"base": base, "changes": changes, "removed": removed, "waves_changed": waves_changed,
            "changed_paths": artifacts, "value_changed_paths": value_changes, "trust_paths_changed": trust,
            "touched": touched, "violations": violations,
            "status": "failed" if violations else "passed"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository checkout (default: this one).")
    parser.add_argument("--base", required=True,
                        help="Base revision; compared at its merge base with the head (CI: the PR's base sha, "
                             "or the pushed range's previous commit).")
    parser.add_argument("--head", default=None,
                        help="Head revision (default: the checkout at --root as it is, which CI checks out at the "
                             "PR merge commit; a revision is checked out into a temporary detached worktree).")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    return parser.parse_args(argv)


def print_report(report, as_json):
    if as_json:
        print(json.dumps(report, indent=1, sort_keys=True))
        return
    if not report["touched"] and not report["violations"]:
        print(f"verdict-review-gate: no verdict rows changed (base {report['base'][:12]})")
        return
    for change in report["changes"]:
        note = "; grandfathered: reported, frozen by build_verdicts.py --check" if change["grandfathered"] else ""
        print(f"changed {change['row']} ({change['kind']}{note})")
    for row in report["removed"]:
        print(f"removed {row}")
    if report["changed_paths"]:
        print(f"{len(report['changed_paths'])} verdict path(s) changed; the repository validators ran")
    for violation in report["violations"]:
        print(f"VIOLATION {violation['row']}: {violation['message']}")
    print(f"verdict-review-gate: {report['status']} ({len(report['changes'])} changed row(s), "
          f"{len(report['violations'])} violation(s))")


def main(argv=None):
    args = parse_args(argv)
    root = args.root.resolve()
    worktree = None
    try:
        head = resolve(root, args.head or "HEAD")
        base = merge_base(root, resolve(root, args.base), head)
        head_root = root
        if args.head is not None:
            worktree = tempfile.mkdtemp(prefix="verdict-review-gate-")
            git(root, "worktree", "add", "--quiet", "--detach", worktree, head)
            head_root = Path(worktree)
        report = evaluate(root, base, head_root)
    except (RevisionError, ReadError) as error:
        print(f"verdict-review-gate: {error}")
        return 2
    finally:
        if worktree is not None:
            git(root, "worktree", "remove", "--force", worktree, check=False)
    print_report(report, args.json)
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
