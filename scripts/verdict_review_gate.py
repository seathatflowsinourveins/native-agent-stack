#!/usr/bin/env python3
"""Required PR check: a changed layer-verdict row must be consistent with the sealed cross-family review its wave registers.

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
  ``lanes.single_lane_decision_sha256`` (review finding 2), already present with the same bytes at
  the base, so an authorization lands in its own earlier pull request (fourth review, G2);
- a ``verdict_status`` equal to the one ``record_verdicts.py`` writes for that evidence
  (``recorded`` for agreeing lanes, an adjudicated disagreement or an authorized single lane,
  unless no indexed alternative remains; else ``pending_lanes``; never ``no_selection``), so a
  recorded verdict cannot be withdrawn by relabelling its row (third review, finding 1).

Each winner, apart from ``platform_status``, must be exactly what ``record_verdicts.build_winners``
writes from the chosen lane, the packet and the row's candidates (``repository``, ``recipe_ref``,
``evidence_class``, ``why_selected``, ``evidence_refs`` and ``pin``, and no other key); the
published ``alternatives``, ``verdict_overturn_when`` and ``overturn_protocol`` must be the ones
``record_verdicts`` derives from the sealed returns (``open_gaps`` is not re-derived), and deriving
them with the base's canonical repository index must give the same result as with the head's. Every
changed ``platform_status`` value must be what ``scripts/platform_status.py`` ``platform_status()``
derives for the winner's sealed pin and evidence_refs (fourth review, G1): the packet candidate's pin,
else a pin the base's row candidates already carry, else ``unpinned``, and the chosen lane's
``winner_evidence_refs``. A changed value may also claim no more than the same derivation gives from
only the evidence refs and host receipts that are already at the base with the same bytes and
registered there with that sha256 (fifth review): evidence or a receipt that raises a status lands in
its own earlier pull request, like a single-lane authorization. A row whose only change is
``platform_status`` needs nothing else. A changed
grandfathered row is reported and passes here (``build_verdicts.py --check`` freezes it). Every
row of the base keeps a row at the head whose run id is not older, never moves from a new wave back
to the grandfathered one and changes only to the newest registered wave (review of #123, finding 1).
Every wave registry entry at the base except the newest, and every grandfathered entry, must be
unchanged at the head, with its document (review finding 4); when the head registers a wave newer
than the base's newest, that newest entry is frozen too, its sha256 included, with its document byte
for byte (review of #135, M1). Frozen values compare type-strictly (``same_value``: 1, 1.0 and true
differ). The SOTA manifest every base entry
registers (``manifest``), the newest included, must keep its pointer and its parsed value at the head
(fifth review): a registered wave's published ``sota_components`` come from it. Rows, wave documents and the registry
are compared on parsed values without duplicate keys, so a pure reformat is not a change
(finding 3). When a row, a wave or any path under
``VERDICT_PATHSPECS`` changed, ``scripts/landscape.py`` and ``tools/sota-convergence/build_verdicts.py
--check`` then run on the head.

The sealed files are self-attested: the gate checks that a row is consistent with the sealed returns
its wave registers and that their declared model families differ, not that a cross-family review
actually ran (the decision record's accepted residual). The gate's own rules are trusted only from the base: CI runs the base commit's copy of this script
against the head checkout (``--root``), and a change to a verdict row, wave or sealed artifact fails
when the same comparison also changes a ``TRUST_PATHS`` file, so a weakening of the rules has to land
(and be seen) in its own pull request first. Exit 0 prints one line when nothing of that changed;
otherwise every violation is printed with its row key and the exit code is 1 (2 for an unresolvable
revision, an unreadable or malformed base or head ledger, manifest or wave registry, or a git
command that fails while listing the changed paths or a base tree, or while finding the merge base).
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
from scripts.catalog_decisions import identity, safe_file, unique_json  # noqa: E402
from scripts.host_receipts import evidence_files  # noqa: E402
from build_manifest import sanitize_value  # noqa: E402
from build_verdicts import LEDGER_FILES, WAVE_REGISTRY  # noqa: E402
from record_verdicts import (  # noqa: E402
    build_alternatives, build_winners, canonical, choose_overturn_protocol, derive_component_id,
    index_v1_candidates_by_repository, parse_sha256sums, safe_identity, v1_pin_text,
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
# tests/test_verdict_review_gate.py derives both: the imports by walking the modules' ast, and the
# files read by recording every open() (a sys.addaudithook) while the gate judges a fixture and the
# validators check this checkout. Every head-side read must be a TRUST_PATHS file or verdict data the
# gate binds (HEAD_DATA_BINDINGS), so a new rule input cannot be read from the head unnoticed.
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
# Head-side files the gate reads that are verdict data, not rules, each with what binds it; the
# read-derivation test fails on any other head-side read outside TRUST_PATHS.
HEAD_DATA_BINDINGS = (
    ("catalogs/landscape/", "the ledgers (compared with the base row by row) and the landscape manifest "
     "(must name build_verdicts.LEDGER_FILES; its repository index is compared with the base's)"),
    ("catalogs/sota-convergence/", "the wave registry and documents (registered by sha256; every wave but the "
     "newest frozen) and each registered wave's SOTA manifest (frozen, the newest included)"),
    (SEALED_BASE_PREFIX, "sealed lane returns, packets, adjudications and run manifests (bound by the row's "
     "sha256 fields and manifests/evidence.json)"),
    ("manifests/evidence.json", "the evidence registration the sealed files and receipts are checked against (a "
     "raised platform_status also against the base's)"),
    ("evidence/", "evidence files a sealed citation names (a raised platform_status needs them byte-identical at "
     "the base and registered there)"),
    ("evidence/hosts/", "host receipts (platform_status derives from receipts bound to the sealed pin; a raised "
     "value only from receipts byte-identical at the base and registered there)"),
    (SINGLE_LANE_DECISION_DIR, "single-lane authorizations (must be byte-identical at the base)"),
    ("catalogs/us-equities/decision-index.json", "the canonical repository index (the derived alternatives and "
     "status must be the same with the base's index)"),
    ("adoption/manifest.json", "its platform_profiles, a platform_status rule input (RULE_INPUT_FIELDS)"),
)
# Rule inputs held in a head-side data file: (path, top-level key, what reads it). A change to one in
# the same comparison as a verdict change fails like a TRUST_PATHS change; the rest of the file is data.
RULE_INPUT_FIELDS = (
    ("adoption/manifest.json", "platform_profiles",
     "scripts/host_receipts.py platform_profile_map: the host os/architecture a receipt's platform_id binds, "
     "which decides whether it counts for platform_status"),
)
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
    """The merge base of ``base`` and ``head``; ``base`` itself when they share no history (git exits 1
    with no output, as for unrelated or cut-off histories: comparing with the base tip then reports
    more changes, not fewer). Any other git failure raises RevisionError (exit 2), not a fallback."""
    result = git(root, "merge-base", base, head, check=False)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.decode().strip()
    if result.returncode == 1 and not result.stdout.strip():
        return base
    raise RevisionError(f"git merge-base {base[:12]} {head[:12]} failed (exit {result.returncode}): "
                        f"{result.stderr.decode(errors='replace').strip()}")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_id(data, length):
    """The git object id of a blob holding ``data`` (sha1, or sha256 for a 64-hex object format)."""
    digest = hashlib.sha256 if length == 64 else hashlib.sha1
    return digest(b"blob %d\0" % len(data) + data).hexdigest()


class Side:
    """Read access to one side of the comparison: a commit through ``git show`` or a checkout."""

    def __init__(self, root, commit=None):
        self.root, self.commit = Path(root), commit

    def read(self, path):
        if self.commit is not None:
            # Absent from the tree is None; a failure to list the tree or to read an object that exists
            # is an error, so a read failure cannot pass for "the base had no wave registry" (`git
            # cat-file -e` exits 128 both for an absent path and for a broken repository).
            listing = git(self.root, "ls-tree", "-z", "--full-tree", self.commit, "--", path, check=False)
            if listing.returncode != 0:
                raise ReadError(f"cannot list {path} at {self.commit[:12]}: "
                                f"{listing.stderr.decode(errors='replace').strip()}")
            entries = [entry.split(b"\t", 1) for entry in listing.stdout.split(b"\0") if entry]
            if not any(len(entry) == 2 and entry[1].decode(errors="replace") == path
                       and entry[0].split()[1:2] == [b"blob"] for entry in entries):
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

    def blob_ids(self, paths):
        """{path: git blob id} of every path of ``paths`` that is a blob in this commit's tree, from one
        ``git ls-tree`` (a failing listing raises ReadError)."""
        paths = sorted({path for path in paths if isinstance(path, str) and path})
        if self.commit is None or not paths:
            return {}
        listing = git(self.root, "ls-tree", "-z", "--full-tree", self.commit, "--", *paths, check=False)
        if listing.returncode != 0:
            raise ReadError(f"cannot list {len(paths)} evidence path(s) at {self.commit[:12]}: "
                            f"{listing.stderr.decode(errors='replace').strip()}")
        found = {}
        for entry in listing.stdout.split(b"\0"):
            meta, _tab, name = entry.partition(b"\t")
            fields = meta.split()
            if len(fields) == 3 and fields[1] == b"blob":
                found[name.decode(errors="replace")] = fields[2].decode()
        return found

    def json(self, path):
        """The parsed file, None when absent; a file that exists but is not JSON (or repeats an object key) raises ReadError."""
        data = self.read(path)
        if data is None:
            return None
        try:
            return strict_json(data)
        except ValueError as error:
            where = self.commit[:12] if self.commit is not None else "the head"
            raise ReadError(f"{path} at {where} is not JSON ({error})") from None


def canonical_index(side):
    """(identities, aliases) of the canonical repository index at this side: the lines
    record_verdicts.load_canonical_index runs, read through ``side`` so the base's index can be
    compared with the head's."""
    manifest = side.json(MANIFEST)
    index = side.json(manifest["sources"]["repository_index"])
    if not isinstance(index, dict):
        raise ValueError(f"the repository index {manifest['sources']['repository_index']!r} is absent")
    aliases = index.get("aliases", {}) or {}
    identities = {identity(row["repository"]) for row in index.get("records", [])}
    return identities, aliases


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
    if all(same_value(old.get(field), new.get(field)) for field in VERDICT_FIELDS):
        return None
    if (all(same_value(old.get(field), new.get(field)) for field in VERDICT_FIELDS if field != "winners")
            and same_value(without_platform_status(old.get("winners")), without_platform_status(new.get("winners")))):
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
        packet = strict_json(packet_bytes)
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
    def __init__(self, head, key, row, registered, waves, violations, base=None, base_row=None):
        self.head, self.key, self.row = head, key, row
        self.registered, self.waves, self.violations = registered, waves, violations
        # The base side and the base's row for the same (catalog, layer_id), whatever its run id.
        self.base, self.base_row = base, base_row if isinstance(base_row, dict) else {}
        self.lanes = row.get("lanes") if isinstance(row.get("lanes"), dict) else {}
        # component_id -> {"pin", "evidence_refs"} the sealed evidence binds (check_winner_fields);
        # platform_status is derived from these, never from the head winner's own values (G1).
        self.sealed_bindings = {}
        self.index_diverged = False

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
        self.check_status(status, recomputed, returns, candidates, sealed_base, packet_sha256)
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

    def check_status(self, status, recomputed, returns, candidates, sealed_base, packet_sha256):
        """Review of #123 (third round), finding 1: the row's verdict_status must be the one
        record_verdicts.py writes for the sealed evidence, so a row the evidence supports as recorded
        cannot be relabelled pending_lanes (or no_selection) with its winners cleared. record_verdicts.py
        never writes no_selection for a new wave."""
        if status == "no_selection":
            self.fail("a new-wave row cannot be 'no_selection': record_verdicts.py never writes it (it writes "
                      "'recorded' or 'pending_lanes' from the sealed evidence)")
            return
        expected, reason = self.expected_status(recomputed, returns, candidates, sealed_base, packet_sha256)
        if expected is not None and status != expected:
            self.fail(f"verdict_status is {status!r} but record_verdicts.py writes {expected!r} for the sealed "
                      f"evidence ({reason})")

    def expected_status(self, recomputed, returns, candidates, sealed_base, packet_sha256):
        """(status record_verdicts.py writes, why), derived from the sealed evidence alone; (None, why)
        when the evidence is too broken to derive it (that is already a violation)."""
        if recomputed is None:
            return None, "the agreement cannot be recomputed"
        if recomputed == "pending":
            return "pending_lanes", "no sealed claude lane return"
        if recomputed == "same_winner":
            chosen, why = "claude", "both lanes name the same winners"
        elif recomputed == "codex_absent":
            if self.single_lane_issues(binding=False):
                return "pending_lanes", ("codex lane absent and no single-lane decision record, unchanged since "
                                         "the base, names this layer")
            chosen, why = "claude", "codex lane absent, single-lane decision record names this layer"
        else:
            chosen, why = self.adjudicated_lane(sealed_base, packet_sha256, set(returns))
            if chosen is None:
                return "pending_lanes", why
        if candidates is None or chosen not in returns:
            return None, "the sealed packet cannot be resolved"
        keys = returns[chosen].get("winner_keys") or []
        if any(key not in candidates for key in keys):
            return None, "the chosen lane's winner_keys are not all packet candidates"
        repositories = [candidates[key].get("repository") for key in keys]
        try:
            remaining = self.derived_alternatives(returns, repositories)
        except (OSError, KeyError, TypeError, ValueError):
            return None, "the canonical repository index cannot be loaded"
        if not remaining:
            return "pending_lanes", f"{why}, but no indexed alternative remains"
        return "recorded", why

    def adjudicated_lane(self, sealed_base, packet_sha256, sealed_lanes):
        """(winner lane, why) of the disagree row's sealed adjudication; (None, why) when there is none,
        it is a split, or it does not meet judge_adjudication and the two-family rule."""
        claude_run = (self.lanes.get("claude") or {}).get("run_id") if isinstance(self.lanes.get("claude"), dict) else None
        data = self.head.read(f"{sealed_base}/adjudication/{claude_run}.json")
        if data is None:
            return None, "the lanes disagree and no sealed adjudication exists"
        try:
            raw = strict_json(data)
        except ValueError:
            return None, "the sealed adjudication is not valid JSON"
        issue, result = judge_adjudication(raw, grandfathered=False, packet_sha256=packet_sha256)
        if issue or result.get("winner_lane") is None:
            return None, "the sealed adjudication is a split or invalid"
        issue, winner = two_family_adjudication_issue(raw, sealed_lanes)
        if issue or winner != result["winner_lane"]:
            return None, "the sealed adjudication does not meet the two-family rule"
        return winner, f"the sealed adjudication chooses the {winner} lane"

    def derived_alternatives(self, returns, winner_repositories):
        """The alternatives record_verdicts.py publishes: build_alternatives over the sealed returns,
        without any that is (canonically) one of the winners. The canonical repository index is a
        head-side rule input (its identities and aliases decide which alternatives remain, and so the
        status), so the same derivation with the base's index must agree (fourth review, G3): an index
        change that alters a changed row's derivation lands in its own pull request first."""
        def derive(index):
            identities, aliases = index
            computed, _gaps = build_alternatives(returns, identities, aliases, None, None)
            winner_ids = {canonical(safe_identity(repository), aliases) for repository in winner_repositories
                          if safe_identity(repository)}
            return [alternative for alternative in sanitize_value(computed)
                    if canonical(safe_identity(alternative["repository"]), aliases) not in winner_ids]

        head = derive(canonical_index(self.head))
        if self.base is not None:
            try:
                base = derive(canonical_index(self.base))
            except (OSError, KeyError, TypeError, ValueError):
                base = None
            if base != head and not self.index_diverged:
                self.index_diverged = True
                self.fail("the head's canonical repository index (catalogs/landscape/manifest.json "
                          "sources.repository_index) derives other alternatives for this row than the base's "
                          f"(base {[a.get('repository') for a in base or []] if base is not None else 'unloadable'}, "
                          f"head {[a.get('repository') for a in head]}); land the index change in its own pull "
                          "request first")
        return head

    def check_winner_fields(self, sealed_return, lane, winners, candidates):
        """Each winner, apart from platform_status, is exactly what record_verdicts.build_winners
        writes (fourth review, G1): repository and recipe_ref from the packet candidate, evidence_class,
        why_selected and evidence_refs (normalized against the head) from the chosen lane, the pin
        from the packet, else the row's v1 candidate, else "unpinned", and no other key. Records
        self.sealed_bindings: the pin and evidence_refs platform_status is derived from. A pin the
        packet does not carry binds receipts only when the base's row candidates already carry it,
        so a pull request cannot introduce a pin (with a matching candidate) that raises a status."""
        ledger_path = LEDGER_FILES.get(self.key[0])
        try:
            expected = sanitize_value(build_winners(sealed_return, candidates, ledger_path,
                                                    # The no-packet-pin fallback comes from the BASE row's
                                                    # candidates (sixth review): a candidates-only pin change
                                                    # then fails the pin check and must land in its own PR.
                                                    index_v1_candidates_by_repository(self.base_row or self.row),
                                                    self.head.root,
                                                    [], status_context=None))
        except (KeyError, TypeError, ValueError) as error:
            self.fail(f"the {lane} lane return's winners cannot be built as record_verdicts.py does ({error!r})")
            return
        base_v1 = index_v1_candidates_by_repository(self.base_row)
        expected_by_id = {winner["component_id"]: winner for winner in expected}
        by_key = {derive_component_id(candidates[key]): candidates[key]
                  for key in sealed_return.get("winner_keys") or [] if key in candidates}
        for winner in winners:
            component_id = winner.get("component_id")
            want = expected_by_id.get(component_id) or {}
            candidate = by_key.get(component_id) or {}
            if winner.get("repository") != want.get("repository"):
                self.fail(f"winner {component_id}: repository {winner.get('repository')!r} is not the sealed packet "
                          f"candidate's {want.get('repository')!r}")
            if winner.get("recipe_ref") != want.get("recipe_ref"):
                self.fail(f"winner {component_id}: recipe_ref {winner.get('recipe_ref')!r} is not "
                          f"{want.get('recipe_ref')!r} (the sealed packet candidate's, else the row's ledger)")
            if winner.get("evidence_class") != want.get("evidence_class"):
                self.fail(f"winner {component_id}: evidence_class {winner.get('evidence_class')!r} is not the {lane} "
                          f"lane's winner_evidence_class {want.get('evidence_class')!r}")
            if winner.get("why_selected") != want.get("why_selected"):
                self.fail(f"winner {component_id}: why_selected differs from the sealed {lane} lane return")
            if winner.get("evidence_refs") != want.get("evidence_refs"):
                self.fail(f"winner {component_id}: evidence_refs {winner.get('evidence_refs')!r} are not the sealed "
                          f"{lane} lane's winner_evidence_refs as record_verdicts.py normalizes them "
                          f"({want.get('evidence_refs')!r})")
            if winner.get("pin") != want.get("pin"):
                source = ("the sealed packet's" if candidate.get("pin")
                          else "the one record_verdicts.py writes without a packet pin (the row's v1 candidate pin, "
                               "else 'unpinned'):")
                self.fail(f"winner {component_id}: pin {winner.get('pin')!r} is not {source} {want.get('pin')!r}")
            extra = sorted(set(winner) - set(want) - {"platform_status"}) if want else []
            if extra:
                self.fail(f"winner {component_id}: carries {extra}, which record_verdicts.build_winners does not write")
            if not want:
                continue
            pin = want["pin"]
            if not candidate.get("pin") and pin != v1_pin_text(base_v1.get(want.get("repository"))):
                # Not sealed and not already carried at the base: it binds no receipt.
                pin = "unpinned"
            self.sealed_bindings[component_id] = {"pin": pin, "evidence_refs": list(want.get("evidence_refs") or [])}

    def check_published_alternatives(self, returns, lane, winners):
        """The alternatives and verdict_overturn_when record_verdicts.py derives from the sealed
        returns, compared on the fields the wave document publishes."""
        try:
            expected = self.derived_alternatives(returns, [winner.get("repository") for winner in winners])
        except (OSError, KeyError, TypeError, ValueError) as error:
            self.fail(f"the canonical repository index cannot be loaded to derive the alternatives ({error!r})")
            return

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
            manifest = strict_json(data)
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
                sealed_return = strict_json(data)
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
            raw = strict_json(data)
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

    def single_lane_issues(self, binding=True):
        """Why the row's lanes.single_lane_decision does not authorize a single-lane verdict ([] when
        it does): a docs/decisions/ record carrying the line
        ``single-lane-authorization: <catalog>/<layer_id>``, bound by lanes.single_lane_decision_sha256
        (checked only with ``binding``; a row cannot escape its recorded status by dropping the hash)."""
        catalog, layer_id, _ = self.key
        path = self.lanes.get("single_lane_decision")
        if not isinstance(path, str) or not path:
            return ["a recorded codex_absent row needs lanes.single_lane_decision"]
        posix = PurePosixPath(path)
        name = posix.name
        if (path.startswith(SEALED_BASE_PREFIX) or path.startswith(WAVE_DOCUMENT_PREFIX)
                or path in {entry.get("path") for entry in self.waves.values()}
                or (name.startswith("layer-verdicts-") and name.endswith(".json")) or name == RUN_MANIFEST_NAME):
            return [f"lanes.single_lane_decision {path!r} is a wave document, run manifest or sealed verdict "
                    "artifact, not a decision record"]
        if (posix.is_absolute() or ".." in posix.parts or path != posix.as_posix()
                or not path.startswith(SINGLE_LANE_DECISION_DIR)):
            return [f"lanes.single_lane_decision {path!r} must be a file under {SINGLE_LANE_DECISION_DIR}"]
        data = self.head.read(path)
        if data is None:
            return [f"lanes.single_lane_decision {path!r} does not exist"]
        issues = []
        # Fourth review, G2: the authorization must already be at the base, byte for byte, so it lands
        # (and is seen) in its own earlier pull request, never in the one adding the row it authorizes.
        base_data = self.base.read(path) if self.base is not None else None
        if base_data is None:
            issues.append(f"lanes.single_lane_decision {path!r} is not at the base: a single-lane authorization "
                          "lands in its own pull request before the verdict it authorizes")
        elif base_data != data:
            issues.append(f"lanes.single_lane_decision {path!r} differs from its base copy (base sha256 "
                          f"{sha256(base_data)}, head {sha256(data)}): an authorization is edited in its own pull "
                          "request first")
        stored = self.lanes.get(SINGLE_LANE_DECISION_SHA256_FIELD)
        if not binding:
            pass
        elif stored is None:
            issues.append(f"lanes.{SINGLE_LANE_DECISION_SHA256_FIELD} is absent; a recorded codex_absent row binds "
                          f"its decision record {path} ({sha256(data)})")
        elif stored != sha256(data):
            issues.append(f"lanes.{SINGLE_LANE_DECISION_SHA256_FIELD} {stored} does not match {path} ({sha256(data)})")
        wanted = f"{SINGLE_LANE_MARKER} {catalog}/{layer_id}"
        if wanted not in (line.strip() for line in data.decode("utf-8", errors="replace").splitlines()):
            issues.append(f"{path} has no line {wanted!r} authorizing this row alone")
        return issues

    def check_single_lane(self):
        for issue in self.single_lane_issues():
            self.fail(issue)


UNBOUND_WINNER = {"pin": "unpinned", "evidence_refs": []}


class BaseTrust:
    """Which evidence files a raised platform_status may rest on (fifth review): a file that is at the
    base with the same bytes as at the head and that the base's manifests/evidence.json registers with
    that sha256. A sealed winner_evidence_refs citation is normalized against the head, and host
    receipts are read from the head, so without this a pull request could add (and register) the file
    a sealed citation names, or a receipt, and raise a status in the same comparison."""

    def __init__(self, base, head):
        self.base, self.head, self.cache, self._base_registry = base, head, {}, None

    def base_registry(self):
        if self._base_registry is None:
            document = self.base.json("manifests/evidence.json") if self.base is not None else None
            files = document.get("files") if isinstance(document, dict) else None
            self._base_registry = {record["path"]: record.get("sha256") for record in files or []
                                   if isinstance(record, dict) and isinstance(record.get("path"), str)}
        return self._base_registry

    def trusted(self, paths):
        """The subset of ``paths`` that is base-trusted as above."""
        paths = {path for path in paths if isinstance(path, str)}
        missing = sorted(path for path in paths if path not in self.cache)
        if missing:
            blobs = self.base.blob_ids(missing) if self.base is not None else {}
            registry = self.base_registry() if blobs else {}
            for path in missing:
                data = self.head.read(path) if path in blobs else None
                self.cache[path] = (data is not None and blobs[path] == git_blob_id(data, len(blobs[path]))
                                    and registry.get(path) == sha256(data))
        return {path for path in paths if self.cache[path]}

    def context(self, context, evidence_refs, component_id=None, platform_id=None):
        """(the StatusContext restricted to base-trusted receipts and evidence refs, the untrusted
        registered refs and ``component_id``'s untrusted ``platform_id`` receipts) for a winner citing
        ``evidence_refs``."""
        receipts = {entry.get("path") for component in (context.summary.get("components") or {}).values()
                    if isinstance(component, dict)
                    for bucket in (component.get("platforms") or {}).values() if isinstance(bucket, dict)
                    for entry in bucket.get("receipts") or [] if isinstance(entry, dict)}
        refs = {ref.split("#", 1)[0] for ref in evidence_refs or [] if isinstance(ref, str)}
        refs = {path for path in refs if path in context.registered_paths}
        trusted = self.trusted(receipts | refs)
        summary = {**context.summary, "components": {
            component_id: {**component, "platforms": {
                platform_id: {**bucket, "receipts": [entry for entry in bucket.get("receipts") or []
                                                     if isinstance(entry, dict) and entry.get("path") in trusted]}
                if isinstance(bucket, dict) else bucket
                for platform_id, bucket in (component.get("platforms") or {}).items()}}
            if isinstance(component, dict) else component
            for component_id, component in (context.summary.get("components") or {}).items()}}
        restricted = platform_evidence.StatusContext(summary=summary, registered_paths=frozenset(refs & trusted))
        own = {entry.get("path") for entry in platform_evidence._platform_receipts(context.summary, component_id,
                                                                                  platform_id)}
        return restricted, sorted(((own & receipts) | refs) - trusted - {None})


def platform_status_violations(key, old, new, context, sealed_bindings, trust=None):
    """Every changed platform value must be the one platform_status() derives for the winner's
    SEALED pin and evidence_refs (fourth review, G1), never the head winner's own: a winner whose
    sealed evidence cannot be resolved is derived as unpinned with no evidence_refs. With ``trust``
    (a BaseTrust), the value may also rank no higher than the derivation from base-trusted evidence
    refs and receipts alone (fifth review)."""
    violations = []
    old_winners = {winner.get("component_id"): winner for winner in old.get("winners") or [] if isinstance(winner, dict)}
    for winner in new.get("winners") or []:
        if not isinstance(winner, dict):
            continue
        old_winner = old_winners.get(winner.get("component_id")) or {}
        before = old_winner.get("platform_status") or {}
        declared = winner.get("platform_status") if isinstance(winner.get("platform_status"), dict) else {}
        sealed = {**winner, **sealed_bindings.get(winner.get("component_id"), UNBOUND_WINNER)}
        # An unchanged value is skipped only when what it is derived from is unchanged too (sixth
        # review): a new pin or new evidence behind the same declared status must be re-derived.
        binding_changed = not old_winner or any(not same_value(winner.get(field), old_winner.get(field))
                                                for field in ("pin", "evidence_refs", "evidence_class"))
        for platform in platform_evidence.PLATFORMS:
            if declared.get(platform) == before.get(platform) and not binding_changed:
                continue
            derived = platform_evidence.platform_status(platform, sealed, context)
            if declared.get(platform) != derived.status:
                violations.append({"row": label(key), "message": (
                    f"winner {winner.get('component_id')}: platform_status.{platform} changed to "
                    f"{declared.get(platform)!r} but scripts/platform_status.py derives {derived.status!r} "
                    f"({derived.reason}) from the registered receipts bound to the sealed pin "
                    f"{sealed.get('pin')!r} and evidence_refs {sealed.get('evidence_refs')!r}")})
                continue
            if trust is None:
                continue
            restricted, untrusted = trust.context(context, sealed.get("evidence_refs"), winner.get("component_id"),
                                                  platform)
            supported = platform_evidence.platform_status(platform, sealed, restricted)
            rank = platform_evidence.STATUS_RANK
            if rank.get(declared.get(platform), len(rank)) > rank[supported.status]:
                violations.append({"row": label(key), "message": (
                    f"winner {winner.get('component_id')}: platform_status.{platform} changed to "
                    f"{declared.get(platform)!r}, which the head's evidence derives, but only {supported.status!r} "
                    f"({supported.reason}) follows from the evidence refs and host receipts already at the base "
                    f"with the same bytes and registered there with that sha256 (not at the base, changed or "
                    f"unregistered there: {untrusted}); land the evidence or receipt in its own pull request "
                    "first")})
    return violations


def strict_json(data):
    """json.loads that rejects a duplicate object key (catalog_decisions.unique_json raises a
    ValueError): json.loads alone keeps the last value, so a rewrite that adds an earlier duplicate
    holding other content would still compare equal."""
    return json.loads(data, object_pairs_hook=unique_json)


def same_value(before, after):
    """Type-strict equality of parsed JSON values (review of #135, L5): Python's == makes 1, 1.0 and
    True equal (and so {"a": 1} and {"a": true}), so frozen values are compared as their canonical JSON
    text, which keeps the type of every number and boolean."""
    return json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)


def json_equivalent(before, after):
    """True when two file contents are equal as bytes, or both parse as JSON, without duplicate
    keys, to equal values (review of #123, finding 3: a pure formatting change of a generated
    document is not a value change), compared type-strictly (same_value)."""
    if before == after:
        return True
    if before is None or after is None:
        return False
    try:
        return same_value(strict_json(before), strict_json(after))
    except ValueError:
        return False


def registry_values(entry):
    """A wave registry entry without its document sha256, which a pure reformat of the document changes."""
    return {key: value for key, value in entry.items() if key != "sha256"} if isinstance(entry, dict) else entry


def registry_equivalent(before, after):
    """json_equivalent for the wave registry, ignoring each entry's document sha256 (the entries'
    sha256 against their documents is checked by wave_freeze_violations and build_verdicts.py)."""
    def values(data):
        document = strict_json(data)
        if isinstance(document, dict) and isinstance(document.get("waves"), list):
            document = {**document, "waves": [registry_values(entry) for entry in document["waves"]]}
        return document

    if json_equivalent(before, after):
        return True
    if before is None or after is None:
        return False
    try:
        return same_value(values(before), values(after))
    except ValueError:
        return False


def wave_freeze_violations(base, head, base_waves, head_waves):
    """Review finding 4: every base registry entry except the newest (and every grandfathered one)
    is unchanged at the head, and so is the document it registers, compared on parsed values: a
    reformatted document passes when its registry sha256 is updated to the reformatted bytes
    (build_verdicts.py --check then decides whether the reformat is the generator's).

    Review of #135, M1: once the head registers a wave newer than the base's newest, the base's
    newest (non-grandfathered) wave stops being current, and build_verdicts.py --check then verifies
    only its own rows and registry sha256, while every wave document holds all rows. So in that case
    the base's newest entry is frozen outright: its registry entry, sha256 included, and its document
    byte for byte (so also its parsed value)."""
    violations = []
    newest = max(base_waves) if base_waves else None
    superseded = newest is not None and any(run_id > newest for run_id in head_waves)
    for run_id, entry in sorted(base_waves.items()):
        where = f"wave {run_id}"
        path = entry.get("path")
        head_entry = head_waves.get(run_id)
        if run_id == newest and run_id not in GRANDFATHERED_RUN_IDS:
            if not superseded:
                continue
            later = ", ".join(sorted(later_id for later_id in head_waves if later_id > newest))
            if head_entry is None or not same_value(head_entry, entry):
                violations.append({"row": where, "message": (
                    f"the registry entry of wave {run_id}, the base's newest, was changed or removed (its sha256 "
                    f"included) while this change registers the newer wave(s) {later}; a superseded wave is frozen")})
            base_document = base.read(path) if isinstance(path, str) else None
            head_document = head.read(path) if isinstance(path, str) else None
            if isinstance(path, str) and base_document != head_document:
                violations.append({"row": where, "message": (
                    f"the wave document {path} of wave {run_id}, the base's newest, was rewritten while this change "
                    f"registers the newer wave(s) {later}; a superseded wave's document is frozen byte for byte")})
            continue
        base_document = base.read(path) if isinstance(path, str) else None
        head_document = head.read(path) if isinstance(path, str) else None
        same_document = json_equivalent(base_document, head_document)
        if head_entry is None or not same_value(registry_values(head_entry), registry_values(entry)) or (
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


def registered_manifest(run_id, entry):
    """The SOTA manifest a registry entry names (build_verdicts.py's default when it names none)."""
    manifest = entry.get("manifest") if isinstance(entry, dict) else None
    return manifest or f"catalogs/sota-convergence/manifest-{run_id}.json"


def sota_manifest_violations(base, head, base_waves, head_waves):
    """Fifth review: build_verdicts.py publishes each row's ``sota_components`` (pin, upstream,
    review_status, pin_behind_upstream) from the SOTA manifest its wave registers, and the newest
    wave's document may be regenerated. So the manifest every base registry entry names, the newest
    included, keeps its pointer and its parsed value at the head. A wave registered first in this
    comparison brings its manifest with it (the recorded residual)."""
    violations = []
    for run_id, entry in sorted(base_waves.items()):
        path = registered_manifest(run_id, entry)
        head_entry = head_waves.get(run_id)
        if head_entry is not None and registered_manifest(run_id, head_entry) != path:
            violations.append({"row": f"wave {run_id}", "message": (
                f"the registered SOTA manifest of wave {run_id} moved from {path} to "
                f"{registered_manifest(run_id, head_entry)}; a registered wave's manifest is frozen")})
        if not json_equivalent(base.read(path), head.read(path)):
            violations.append({"row": f"wave {run_id}", "message": (
                f"the SOTA manifest {path} registered by wave {run_id} was changed; its published "
                "sota_components come from it, so a registered wave's manifest is frozen (record a new wave)")})
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


def changed_paths(head_root, base, pathspecs):
    """Paths matching ``pathspecs`` that differ between ``base`` and the head checkout (tracked
    changes and untracked files). A git command that fails raises ReadError (exit 2): an unlisted
    change must not pass for "nothing changed" and skip the trust-base rule or the validators. The
    listings are NUL-separated (-z), so a path with a space, a newline or a non-ASCII byte is listed
    as itself, not C-quoted."""
    paths = set()
    for arguments in (("diff", "--name-only", "-z", "--no-renames", base),
                      ("ls-files", "-z", "--others", "--exclude-standard")):
        result = git(head_root, *arguments, "--", *pathspecs, check=False)
        if result.returncode != 0:
            raise ReadError(f"git {arguments[0]} failed in {head_root} (exit {result.returncode}): "
                            f"{result.stderr.decode(errors='replace').strip()}")
        paths.update(os.fsdecode(name) for name in result.stdout.split(b"\0") if name)
    return sorted(paths)


def changed_verdict_paths(head_root, base):
    """Paths under VERDICT_PATHSPECS that differ between ``base`` and the head checkout."""
    return changed_paths(head_root, base, [f":(glob){spec}**" if spec.endswith("/") else f":(glob){spec}/**"
                                           for spec in VERDICT_PATHSPECS])


def changed_trust_paths(head_root, base):
    """TRUST_PATHS files that differ between ``base`` and the head checkout."""
    return changed_paths(head_root, base, TRUST_PATHS)


def changed_rule_input_fields(base, head):
    """``path#/key`` of every RULE_INPUT_FIELDS value that differs between the two sides (parsed
    without duplicate keys; a malformed file is a ReadError)."""
    changed = []
    for path, key, _reader in RULE_INPUT_FIELDS:
        values = [document.get(key) if isinstance(document, dict) else None
                  for document in (base.json(path), head.json(path))]
        if not same_value(values[0], values[1]):
            changed.append(f"{path}#/{key}")
    return changed


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
    base_by_layer = {key[:2]: row for key, row in base_rows.items()}
    context, trust = None, BaseTrust(base_side, head_side)
    for key, row in sorted(head_rows.items(), key=lambda item: tuple(map(str, item[0]))):
        kind = change_kind(base_rows.get(key), row)
        if kind is None:
            continue
        _run_id, named = row_waves(key[0], row)
        grandfathered = all(wave in GRANDFATHERED_RUN_IDS for wave in named)
        changes.append({"row": label(key), "kind": kind, "grandfathered": grandfathered})
        if grandfathered:
            continue
        # A changed row meets every sealed-evidence rule. A change to platform_status alone needs
        # nothing else: its row is still resolved against the sealed evidence, but only for the pin
        # and evidence_refs the platform values derive from (its other findings are not reported).
        check = RowCheck(head_side, key, row, registered, head_waves,
                         violations if kind != "platform_status" else [], base_side, base_by_layer.get(key[:2]))
        check.run()
        # Every changed platform value of a non-grandfathered row must be the one the receipts bound to
        # the winner's sealed pin and evidence_refs derive.
        context = context or platform_evidence.load_context(head_root)
        violations.extend(platform_status_violations(key, base_rows.get(key) or {}, row, context,
                                                     check.sealed_bindings, trust))
    removed = [label(key) for key in sorted(set(base_rows) - set(head_rows), key=lambda k: tuple(map(str, k)))]
    violations.extend(row_continuity_violations(base_rows, head_rows, head_waves))
    violations.extend(wave_freeze_violations(base_side, head_side, base_waves, head_waves))
    violations.extend(sota_manifest_violations(base_side, head_side, base_waves, head_waves))
    # Compared on parsed values (finding 3): a regenerated wave document or registry that only
    # changes formatting (and the document sha256 it records) is not a wave change.
    waves_changed = not same_value({run_id: registry_values(entry) for run_id, entry in base_waves.items()},
                                   {run_id: registry_values(entry) for run_id, entry in head_waves.items()}) or any(
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
    rule_inputs = changed_rule_input_fields(base_side, head_side)
    if verdict_changed and (trust or rule_inputs):
        violations.append({"row": "repository", "message": (
            f"this change edits verdict rows, waves or sealed verdict artifacts and also the gate's trust base "
            f"({', '.join(trust + rule_inputs)}); land the rules change in its own pull request first")})
    if touched and validators is not None:
        violations.extend(validators(head_root))
    return {"base": base, "changes": changes, "removed": removed, "waves_changed": waves_changed,
            "changed_paths": artifacts, "value_changed_paths": value_changes, "trust_paths_changed": trust,
            "rule_inputs_changed": rule_inputs,
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
