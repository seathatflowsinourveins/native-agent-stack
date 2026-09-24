#!/usr/bin/env python3
"""Create a detached git worktree at a given revision with every prior
landscape-verdict/label selection stripped, so a lane can review candidates
without knowing what a previous run (or the checked-in ledger) already chose.

``--source`` is an existing git checkout, ``--rev`` any commit-ish it can
resolve, ``--dest`` a path that does not yet exist. This tool runs
``git worktree add --detach <dest> <rev>`` from ``--source`` and then mutates
files only inside ``<dest>`` -- ``--source`` itself, and every other worktree
of it, are never touched. The caller removes the worktree afterward with
``git worktree remove --force <dest>`` (from ``--source``, or any other
worktree of the same repository); this tool does not remove it itself.

What is stripped, and how each strip is recorded in
``<dest>/BLIND-MANIFEST.json``:

- **Removed outright** (recorded under ``removed_files``, one entry per file
  actually deleted): ``evidence/artifacts/layer-verdicts-*/`` (recursively),
  ``catalogs/sota-convergence/layer-verdicts-*.json``,
  ``docs/grand-catalog-handbook.md``, ``docs/ecosystem/index.html``,
  ``docs/ecosystem/manifest.json``, and the files that name each layer's
  current winners throughout: ``catalogs/landscape/{component-evidence-matrix,
  new-host-grand-list,blind-convergence}.json``,
  ``catalogs/sota-convergence/manifest-*.json`` and
  ``catalogs/sota-convergence/sdk-runtime-coverage-*``.
- **Ledger candidate order**: each ledger row's ``candidates`` list is sorted
  by lowercased ``(repository, name)`` before anything else is stripped (the
  checked-in order lists the selected incumbent first), so every recorded
  ``candidates/{index}`` pointer names the exported position.
- **The layer-verdict schema v2 fields** of both ledgers
  (``catalogs/landscape/{foundation,us-equities}.json``): every row is reset
  to ``verdict_status: "pending_lanes"`` with empty ``winners``/
  ``alternatives``, a ``pending``/absent ``lanes`` object and an empty
  ``verdict_overturn_when`` -- ``requirement``, ``evidence_refs``,
  ``overturn_when`` and every other non-label v1 field are kept untouched.
- **The v1 label fields** of the same two ledgers' rows: ``current_choice``,
  ``decision``, ``rationale`` at the row level, and ``disposition``,
  ``rationale``, ``review_status`` on each ``candidates[]`` entry -- removed
  (the key itself, not blanked), so a reviewer sees the requirement and the
  candidate names/repositories/evidence but not which one was already
  chosen or why.
- **Every JSON file under ``catalogs/``** (this also covers the two ledgers
  above, redundantly but harmlessly, since those keys are already gone by
  the time this pass runs): the keys ``selection``, ``decision``,
  ``disposition``, ``current_choice`` and ``review_status`` are removed
  wherever they appear, at any nesting depth, regardless of their value;
  and the winner/incumbent keys in ``CATALOGS_NONEMPTY_KEYS`` (``winners``,
  ``incumbents``, ``why_selected`` ...) wherever their value is non-empty.
- **Every JSON file under ``blueprints/``**: the same five keys are removed
  only when the value itself is a label from a closed selection vocabulary
  (``is_label_value``/``LABEL_VALUES`` below, enumerated from every string
  value actually found under these keys in ``blueprints/`` -- not just an
  illustrative subset), or a string that itself states a selection: it
  contains "selected", matches "keep ... selected", or opens with
  "retain"/"adopt"/"reject"/"defer" (case-insensitively, at a word boundary
  -- e.g. ``"Retain current catalog pin..."``, ``"retain installed offline
  request baseline; reject advanced fields locally"``). A mapping/rule
  structure under one of these keys, or an unrelated data or procedural
  value such as ``"top_20"`` or ``"Submission is deferred by session, not by
  bar count..."``, is left untouched.
- **The lane-derived v2 verdict fields ``open_gaps`` and
  ``overturn_protocol``** on every ledger row (``PENDING_LANES`` below):
  these two are written from the lanes' own sealed returns exactly like
  ``winners``/``alternatives`` (record_verdicts.process_row), and
  ``open_gaps`` entries and ``overturn_protocol.arms`` routinely name a
  lane's winner or a disagreement between the lanes by name -- so they are
  reset to ``[]`` and ``{"fixture_paths": [], "metric": "", "arms": []}``
  alongside the other pending-lanes fields, not left in place.

Nothing here re-derives, judges or replaces a stripped value; this is a
mechanical redaction pass over a detached worktree, run once per blind
review.

Each stripped value's hash is HMAC-SHA256 keyed by a random 32-byte key
generated fresh for this run (never a plain unsalted ``sha256(value)``): a
small closed vocabulary of label strings would otherwise let a lane
dictionary-attack ``old_sha256`` straight back to the original value. The
key is never written under ``<dest>`` -- ``run_blind_checkout`` returns it
(``hmac_key_hex``) and ``main`` writes it to ``<dest>.hmac-key`` next to
(not inside) the worktree, for an operator who wants to verify a hash
later; pass the same key explicitly (``hmac_key=bytes.fromhex(...)``) to
reproduce another run's hashes for comparison, or omit it for a fresh
random key per call (two calls against the same source/rev then agree on
every ``removed_files``/``stripped_fields`` *path* but not on
``old_sha256``, since each drew its own key).

``rev`` is resolved to a full commit SHA (``git rev-parse <rev>^{commit}``,
from ``--source``) before the worktree is created, and the manifest records
that resolved SHA plus the originally requested ``rev`` string -- not
``--source``'s absolute host path, which the manifest never carries.

Caveats this tool does not itself close (documented, not solved, here):
the destination is a ``git worktree`` of
``--source``, so it shares that repository's object store -- ``git log``,
``git diff`` or ``git show HEAD:<path>`` run inside ``<dest>`` can still
recover every stripped value from history; a lane given raw git access
(rather than just the working tree) is not blind. Run this only into a
lane sandbox that denies ``git`` (or export the worktree with
``git archive`` instead of handing over the worktree itself) if that
matters for the review.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sys
import subprocess
from pathlib import Path

LEDGER_RELATIVE_FILES = (
    "catalogs/landscape/foundation.json",
    "catalogs/landscape/us-equities.json",
)

# Keys stripped unconditionally, at any depth, from every JSON file under
# catalogs/ (this list intentionally omits "rationale", which the ledger-row
# rule below already owns for the two ledgers specifically -- "rationale" is
# not stripped from an arbitrary catalogs/ file that is not one of the two
# ledgers, since it is not on this task's data-vs-label boundary there).
CATALOGS_UNCONDITIONAL_KEYS = frozenset({"selection", "decision", "disposition", "current_choice", "review_status"})

# Keys that name a layer's current winner/incumbent directly (2026-09-24 blindness review, F1): stripped at
# any depth from every JSON file under catalogs/ whenever the value is non-empty. An empty value ([], {}, "",
# None) states no selection and is left in place, so the ledger rows' pending-lanes ``winners: []`` reset
# survives and a second strip pass finds nothing (idempotence). Each strip is recorded in stripped_fields.
CATALOGS_NONEMPTY_KEYS = frozenset({
    "winners", "incumbents", "incumbent_decision_ids", "incumbent_decisions_path", "coordinator_disposition",
    "claude_final_disposition", "why_selected", "current_selection_record", "dual_lane_same_winner",
})

# The original five keys, but under blueprints/ they are stripped only when the
# value is itself a label (see is_label_value); a mapping/rule value or a
# plain data value (e.g. "top_20") under one of these keys is left alone.
# Deliberately not extended with CATALOGS_NONEMPTY_KEYS: the blueprint label vocabulary
# and its classification test cover exactly these five keys.
BLUEPRINT_CONDITIONAL_KEYS = frozenset({"selection", "decision", "disposition", "current_choice", "review_status"})

LEDGER_ROW_LABEL_KEYS = ("current_choice", "decision", "rationale")
# evidence_kind: a selected candidate must carry a strong kind, so it marks the winners (round 5, N5).
LEDGER_CANDIDATE_LABEL_KEYS = ("disposition", "rationale", "review_status", "evidence_kind")

PENDING_LANES = {
    "verdict_status": "pending_lanes",
    "winners": [],
    "alternatives": [],
    "lanes": {"claude": {"run_id": "", "sealed_sha256": ""},
              "codex": {"run_id": "", "sealed_sha256": ""}, "agreement": "pending"},
    "verdict_overturn_when": "",
    # open_gaps and overturn_protocol are also written by record_verdicts.process_row
    # from the lanes' own returns (a losing/disagreeing lane's alternative, why a
    # winner was or was not recorded, or which arm a lane's overturn protocol names)
    # -- both are v2 verdict fields that name a prior selection just as directly as
    # winners/alternatives, so they reset the same way.
    "open_gaps": [],
    "overturn_protocol": {"fixture_paths": [], "metric": "", "arms": []},
}

REMOVE_GLOBS = (
    "evidence/artifacts/layer-verdicts-*",
    "catalogs/sota-convergence/layer-verdicts-*.json",
    "docs/grand-catalog-handbook.md",
    "docs/ecosystem/index.html",
    "docs/ecosystem/manifest.json",
    # Files that name each layer's current winners/incumbents throughout (2026-09-24 blindness review, F1):
    # removed outright, also from an allowlisted export.
    "catalogs/landscape/component-evidence-matrix.json",
    "catalogs/landscape/new-host-grand-list.json",
    "catalogs/landscape/blind-convergence.json",
    "catalogs/sota-convergence/manifest-*.json",
    "catalogs/sota-convergence/sdk-runtime-coverage-*",
    # Code and data that assert or name the incumbents, removed even if a packet referenced them (binding
    # re-review L8; cross-family review F3).
    "tools/sota-convergence/reconciliations-*.json",
    # Membership lists and earlier verdict records that isolate a layer's winner among its adopted candidates
    # (blindness re-review N1, per-layer subtraction check): the stack manifest, upstream snapshots, the
    # saturation audit and the 2026-09-21 convergence and repository-evidence runs.
    "manifests/stack.json",
    "catalogs/landscape/upstream-snapshot.json",
    "catalogs/us-equities/star-audit.json",
    "catalogs/foundation/automation.json",
    "blueprints/token-native-focus/saturation-audit.json",
    "evidence/artifacts/claude-repository-evidence-*",
    "evidence/artifacts/blind-catalog-convergence-*",
    "evidence/artifacts/claude-upstream-checks-*/results.json",
    "evidence/artifacts/full-stack-convergence-*/component-coverage.json",
    "evidence/artifacts/full-stack-convergence-*/selected-upstream-releases.json",
    # Selection and membership records an id-aware check found isolating winners (independent review of #145,
    # round 4, F1 and F3): the adoption profiles and recipe map (the installed stack), the foundation decision
    # index, the selected us-equities runtime target and the north-star "Selected path" table it points to.
    # lane_packets.py --withhold-labels drops packet references to every removed path (removed_from_blind_export).
    "adoption/manifest.json",
    "catalogs/foundation/decisions.json",
    "catalogs/us-equities/runtime-target.json",
    "blueprints/us-equities/north-star.md",
    "tests/test_catalogs.py",
    "tests/test_new_host_grand_list.py",
    "tests/test_handbook_summary.py",
)

# The closed-vocabulary enum labels found under selection/decision/disposition/
# current_choice/review_status in this repository's blueprints/, plus short free-text
# labels. Longer free text is classified by LABEL_TEXT_SHA256 / DATA_VALUE_SHA256 above
# and by the rules below; rules, plans and data values (e.g. "top_20", "all_events", a
# procedural "Divide by 10,000 exactly ..." rule) stay.
LABEL_VALUES = frozenset({
    "default", "selected", "conditional", "optional", "candidate", "trial",
    "retain", "keep_but_compare", "adjust", "confirmed_default", "selected_destination",
    "adopt_within_scope", "reject_evidence", "defer",
    "advisory_supported", "advisory_contradicted", "advisory_insufficient",
    "advisory_supported retained; reviewer concurs",
    "advisory_contradicted retained; reviewer concurs",
    "advisory_insufficient retained; reviewer concurs",
    "qualified_within_isolated_synthetic_scope",
    "retain_2.3.1_pending_functional_acceptance",
    "source-reviewed-not-executed",
    "language alternative only",
})
# Free-text blueprint values classified by review, keyed by the sha256 of the exact
# string so the classification does not repeat the text. LABEL_TEXT_SHA256 values
# state a selection that no rule below catches; DATA_VALUE_SHA256 values are rules,
# plans or data that must survive (one of them, a corpus methodology statement, would
# otherwise be caught by the "selected" rule). tests/test_blind_checkout.py fails on any
# value under these keys in this repository's blueprints/ that is neither a label by
# rule nor listed here, so a new value is classified when it appears.
LABEL_TEXT_SHA256 = frozenset({
    "557291dc290010e2e286e4de20b4e72ac1f8f5583719cbb3e9364d79b0477186",
    "6b8d0f36c12c9163c12a5b05fe32d5175e12e656e7a526063ed32c701d6f49d6",
    "6bef11d967221994271c977a708462542dd9ad5ff330f913c28ac6dde824b7e9",
    "c0a00234303c3efdd7148d7728960af4ad23acf20e29b02f94d382432c735ec7",
})
DATA_VALUES = frozenset({"all_events", "top_20"})
DATA_VALUE_SHA256 = frozenset({
    "012c690424af3c14cb13030a4c2194070e0fb677fe9907532fbe49e07bc6b3e5",
    "174568cc67e1432b30d6730f3d3243da4203a9bff622d7bf699f96bfd5415d20",
    "1b972c71588a18625a1c9dedd011fd90310acd9f7efd665dad0e19d66aca8311",
    "347f6d65a9422f007fd4d1c845e495c4101bde8c23409e6c7caf4f25301265e9",
    "388940becf7468779450b62e70eddbbdd655a727ea8acf2bd15b7120bf153067",
    "42561a847ba882e19d74f40a934ee65177cdb17673c58ce0684143a78c9d59b0",
    "4444a1b9ddb5e7c15f4eb74c561af0c2a145ed3cfebd275b13b6291789d697ab",
    "52732b56eb266b6fdf7f76b95cea82782909ae9bd3c70ac26d7b934659935691",
    "5324a7f7ae5265609bd6f7f7bf2290d672a9129ece57226eadd80752e5c21c4a",
    "536872dc694dc0e5b4dfe7650333a233a719de15ab0cee7cc4b19b6a22c90fb3",
    "55a8a37e8d36a0549c10adb28d6009af325e13b3bc3af8bae71a75b341607fb4",
    "657f763f81b27a3861692477c80aa4877bf68ecf9674494ee3cc28d614f8171d",
    "838e8a1e99bdbf418375a870265da399f0ea25a8604bbed0664ae7b174d1ee39",
    "9215e5ac002eef37310b201aee09e1529529100e366ac5e7344cbe28be87f901",
    "a7ded62bcdb4aca0dfea4efa56fa3d966c90f3f6112aecf15a96f9e83b0dc660",
    "c58491dcc532424f96a294d48cbbe13e70d8c60a7163c81985ccdbae5d087083",
    "cfd9480d64d27f55bccb60b6835b8dd1ed55cc075e107a88e37ef4f3ba22b8c9",
    "feb6292b38cf6da7a453ee6d98d34450ad5f8db235c5f86e7d923487dded2819",
    "feda2f5cad22987636d2b6e43e37ece78a3fe964c37edfc2e2f9456d86f1ff1f",
})
_SELECTED_WORD = re.compile(r"selected", re.IGNORECASE)
_KEEP_SELECTED = re.compile(r"\bkeep\b.*\bselected\b", re.IGNORECASE)
# Free text stating a retain/adopt/reject/defer decision typically opens with that verb
# (e.g. "Retain current catalog pin...", "retain installed offline request baseline;
# reject advanced fields locally", "adopt_within_scope"); a rule or plan sentence about
# unrelated subject matter does not start this way, so this prefix check does not
# reach into procedural/data strings such as "Submission is deferred by session...".
_RETAIN_ADOPT_REJECT_DEFER_PREFIX = re.compile(r"^(retain|adopt|reject|defer)\b", re.IGNORECASE)


def hmac_sha256_of(value, key: bytes) -> str:
    """Keyed hash of ``value``, used instead of a plain ``sha256(value)`` so a
    label drawn from a small closed vocabulary cannot be dictionary-attacked
    back to its original string from the manifest alone -- the key is never
    written under ``<dest>`` (see ``run_blind_checkout``/``main``)."""
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hmac.new(key, text.encode("utf-8"), hashlib.sha256).hexdigest()


def is_label_value(value) -> bool:
    """True when ``value`` names a selection rather than carrying data --
    a closed-vocabulary label string, or free text that itself states a
    selection. A non-string value (a mapping/rule structure, a list, a
    number) is never a label."""
    if not isinstance(value, str):
        return False
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    if value in DATA_VALUES or digest in DATA_VALUE_SHA256:
        return False
    if value in LABEL_VALUES or digest in LABEL_TEXT_SHA256:
        return True
    if _SELECTED_WORD.search(value) or _KEEP_SELECTED.search(value):
        return True
    if _RETAIN_ADOPT_REJECT_DEFER_PREFIX.match(value):
        return True
    return False


def neutral_candidate_key(candidate) -> tuple:
    """Sort key for a ledger row's candidates that ignores every label: the checked-in ledgers list the
    selected incumbent first on every row (2026-09-24 blindness review, F2), so the original order is itself
    a label."""
    if not isinstance(candidate, dict):
        return ("", "", json.dumps(candidate, sort_keys=True))
    return (str(candidate.get("repository") or "").lower(), str(candidate.get("name") or "").lower())


def strip_ledger_row(row: dict, pointer_prefix: str, stripped: list, hmac_key: bytes) -> None:
    # Reorder first, so every candidates/{index} pointer recorded below names the exported position.
    if isinstance(row.get("candidates"), list):
        row["candidates"] = sorted(row["candidates"], key=neutral_candidate_key)
    for key, default in PENDING_LANES.items():
        if row.get(key) != default:
            if key in row:
                stripped.append({"path": f"{pointer_prefix}/{key}", "old_sha256": hmac_sha256_of(row[key], hmac_key)})
            row[key] = json.loads(json.dumps(default)) if isinstance(default, (list, dict)) else default
    for key in LEDGER_ROW_LABEL_KEYS:
        if key in row:
            stripped.append({"path": f"{pointer_prefix}/{key}", "old_sha256": hmac_sha256_of(row[key], hmac_key)})
            del row[key]
    for index, candidate in enumerate(row.get("candidates") or []):
        if not isinstance(candidate, dict):
            continue
        for key in LEDGER_CANDIDATE_LABEL_KEYS:
            if key in candidate:
                stripped.append({"path": f"{pointer_prefix}/candidates/{index}/{key}",
                                  "old_sha256": hmac_sha256_of(candidate[key], hmac_key)})
                del candidate[key]


def strip_ledger_document(document: dict, relative_path: str, stripped: list, hmac_key: bytes) -> None:
    for index, row in enumerate(document.get("layers") or []):
        if isinstance(row, dict):
            strip_ledger_row(row, f"{relative_path}#/layers/{index}", stripped, hmac_key)


def _is_empty_value(value) -> bool:
    return value is None or (isinstance(value, (str, list, dict)) and len(value) == 0)


def _walk_strip(node, path_prefix: str, stripped: list, keys: frozenset, *, only_labels: bool,
                hmac_key: bytes, nonempty_keys: frozenset = frozenset()) -> None:
    if isinstance(node, dict):
        for key in list(node.keys()):
            pointer = f"{path_prefix}/{key}"
            value = node[key]
            named = nonempty_keys(key, value) if callable(nonempty_keys) else key in nonempty_keys
            if (key in keys and (not only_labels or is_label_value(value))) or \
                    (named and not _is_empty_value(value)):
                stripped.append({"path": pointer, "old_sha256": hmac_sha256_of(value, hmac_key)})
                del node[key]
                continue
            _walk_strip(value, pointer, stripped, keys, only_labels=only_labels, hmac_key=hmac_key,
                        nonempty_keys=nonempty_keys)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _walk_strip(item, f"{path_prefix}/{index}", stripped, keys, only_labels=only_labels, hmac_key=hmac_key,
                        nonempty_keys=nonempty_keys)


# Keys that record a role rather than evidence (2026-09-24 blindness re-review N1, measured with a per-layer
# subtraction check): a selection, retention, challenger or default label, a rationale or recommendation, or an
# earlier run's verdict. Stripped wherever their value is non-empty, under catalogs/ and adoption/.
# The selected_/retained_/coordinator_ prefixes are no longer patterns (independent review of #145, R4-REG-1 and
# F7): they also removed retrieval data (selected_sources, selected_primary_files, retained_failure) and exercised
# checks (retained_helper_check, coordinator_owned_qualification). The label keys among them, measured on the
# 2026-09-23 export, are listed instead.
ROLE_LABEL_KEYS = frozenset({
    "default_profile", "selected_path", "selected_skills", "selected_component", "selected_components",
    "retained_comparison_engine", "retained_choice", "chosen", "coordinator_disposition", "coordinator_selection",
    "coordinator_verdict"})
ROLE_KEY = re.compile(r"^(chosen|incumbents?|winners?|challengers?)(_|$)"
                      r"|challenger|why_not_default|why_selected|why_primary|adoption_recommendation|^rationale$"
                      r"|disposition|sota_verdict|primary_stack|case_for_challenger|would_change_choice"
                      r"|current_selection|final_disposition|dual_lane_same_winner|^selected_component")
# An object that records an observed run is evidence, whatever its key (R4-REG-1).
EVIDENCE_OBJECT_KEYS = frozenset({"observed_at", "reported_on", "exit_code", "sha256", "source_sha256"})
# Under evidence/, only an earlier run's verdict fields go: receipts use selected_* for data (selected files).
EVIDENCE_VERDICT_KEYS = frozenset({
    "sota_verdict", "primary_stack", "strongest_challengers", "why_primary_for_requirement",
    "strongest_case_for_challenger", "test_that_would_change_choice", "coordinator_disposition",
    "claude_final_disposition", "why_selected", "winners", "incumbents", "challenger_repositories"})


def _is_evidence_object(value) -> bool:
    return isinstance(value, dict) and bool(EVIDENCE_OBJECT_KEYS & set(value))


def _role_key(key, value=None) -> bool:
    if not isinstance(key, str):
        return False
    if key in CATALOGS_NONEMPTY_KEYS or key in ROLE_LABEL_KEYS:
        # Named labels go whatever their value holds (review of 52344da8: the evidence-object exemption applies only
        # to keys matched by the ROLE_KEY pattern).
        return True
    return bool(ROLE_KEY.search(key)) and not _is_evidence_object(value)


# A selection of candidates recorded in evidence: the upstream-check crosswalk (F1) and an observation's
# selected_repositories (review of 52344da8: it named the durable-memory winner alone). Receipts' other
# selected_* keys are data (selected files, sources, steps) and stay.
EVIDENCE_SELECTION_KEY = re.compile(r"^selected_(?:component|repositor|tool|candidate|stack)")


def _evidence_verdict_key(key, value=None) -> bool:
    return isinstance(key, str) and (key in EVIDENCE_VERDICT_KEYS or bool(EVIDENCE_SELECTION_KEY.match(key)))


def strip_catalog_unconditional(document, relative_path: str, stripped: list, hmac_key: bytes) -> None:
    _walk_strip(document, relative_path, stripped, CATALOGS_UNCONDITIONAL_KEYS, only_labels=False, hmac_key=hmac_key,
                nonempty_keys=_role_key)


def strip_adoption_roles(document, relative_path: str, stripped: list, hmac_key: bytes) -> None:
    _walk_strip(document, relative_path, stripped, frozenset(), only_labels=False, hmac_key=hmac_key,
                nonempty_keys=_role_key)


def strip_evidence_verdicts(document, relative_path: str, stripped: list, hmac_key: bytes) -> None:
    _walk_strip(document, relative_path, stripped, frozenset(), only_labels=False, hmac_key=hmac_key,
                nonempty_keys=_evidence_verdict_key)


def strip_blueprint_labels(document, relative_path: str, stripped: list, hmac_key: bytes) -> None:
    _walk_strip(document, relative_path, stripped, BLUEPRINT_CONDITIONAL_KEYS, only_labels=True, hmac_key=hmac_key)


def git(args, cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=str(cwd), check=True,
                                capture_output=True, text=True)
    return completed.stdout


def resolve_commit(source: Path, rev: str) -> str:
    """The full commit SHA ``rev`` names in ``source``, so the manifest records
    a stable identifier instead of a caller-relative ref like ``HEAD`` or a
    branch name that can move after the checkout is made."""
    return git(["rev-parse", f"{rev}^{{commit}}"], cwd=source).strip()


def create_worktree(source: Path, resolved_rev: str, dest: Path) -> None:
    if dest.exists():
        raise SystemExit(f"--dest already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "--detach", str(dest), resolved_rev], cwd=source)


def _glob_regex(pattern: str):
    # A REMOVE_GLOBS pattern as Path.glob reads it: "*" never crosses "/".
    return re.compile("".join("[^/]*" if part == "*" else re.escape(part) for part in re.split(r"(\*)", pattern)))


REMOVE_REGEXES = tuple(_glob_regex(pattern) for pattern in REMOVE_GLOBS)


def removed_from_blind_export(relative: str) -> bool:
    """Whether the repository-relative path ``relative`` (or a directory above it) is one REMOVE_GLOBS removes."""
    parts = relative.split("/")
    prefixes = ["/".join(parts[:depth]) for depth in range(1, len(parts) + 1)]
    return any(regex.fullmatch(prefix) for regex in REMOVE_REGEXES for prefix in prefixes)


def remove_paths(root: Path, removed: list) -> None:
    for pattern in REMOVE_GLOBS:
        for match in sorted(root.glob(pattern)):
            if match.is_dir():
                for file in sorted(p for p in match.rglob("*") if p.is_file()):
                    removed.append(file.relative_to(root).as_posix())
                shutil.rmtree(match)
            elif match.is_file():
                removed.append(match.relative_to(root).as_posix())
                match.unlink()


def iter_json_files(root: Path, subdir: str):
    base = root / subdir
    if not base.is_dir():
        return []
    return sorted(p for p in base.rglob("*.json") if p.is_file())


def _rewrite_if_changed(path: Path, before: str, document) -> None:
    after = json.dumps(document, sort_keys=True)
    if after != before:
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def strip_worktree(dest: Path, hmac_key: bytes) -> dict:
    """Mutate every file already checked out under ``dest`` in place; return
    the ``BLIND-MANIFEST.json`` payload (not written by this function).
    ``hmac_key`` keys every ``old_sha256`` recorded for a stripped value; pass
    the same key to compare two runs' hashes, or a fresh one (the default in
    ``run_blind_checkout``) each time hash secrecy from ``<dest>`` matters
    more than cross-run comparability."""
    removed_files: list = []
    stripped_fields: list = []

    remove_paths(dest, removed_files)

    for relative in LEDGER_RELATIVE_FILES:
        path = dest / relative
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        before = json.dumps(document, sort_keys=True)
        strip_ledger_document(document, relative, stripped_fields, hmac_key)
        _rewrite_if_changed(path, before, document)

    for path in iter_json_files(dest, "catalogs"):
        relative = path.relative_to(dest).as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        before = json.dumps(document, sort_keys=True)
        strip_catalog_unconditional(document, relative, stripped_fields, hmac_key)
        _rewrite_if_changed(path, before, document)

    for path in iter_json_files(dest, "blueprints"):
        relative = path.relative_to(dest).as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        before = json.dumps(document, sort_keys=True)
        strip_blueprint_labels(document, relative, stripped_fields, hmac_key)
        _rewrite_if_changed(path, before, document)

    for tree, strip in (("adoption", strip_adoption_roles), ("evidence", strip_evidence_verdicts)):
        for path in iter_json_files(dest, tree):
            relative = path.relative_to(dest).as_posix()
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError):
                continue
            before = json.dumps(document, sort_keys=True)
            strip(document, relative, stripped_fields, hmac_key)
            _rewrite_if_changed(path, before, document)

    return {
        "schema_version": 1,
        "removed_files": sorted(removed_files),
        "stripped_fields": sorted(stripped_fields, key=lambda item: item["path"]),
    }


def run_blind_checkout(source: Path, rev: str, dest: Path, hmac_key: bytes = None) -> dict:
    """``hmac_key`` defaults to a fresh random 32-byte key (never persisted
    under ``dest``); pass an explicit key only when two runs' ``old_sha256``
    values must be directly comparable and the caller accepts keeping that
    key itself out of the lane's hands. ``source`` is never recorded in the
    written manifest (only the resolved commit and the originally requested
    rev are)."""
    resolved_rev = resolve_commit(source, rev)
    create_worktree(source, resolved_rev, dest)
    key = hmac_key if hmac_key is not None else secrets.token_bytes(32)
    manifest = strip_worktree(dest, key)
    manifest = {"requested_rev": rev, "rev": resolved_rev, **manifest}
    (dest / "BLIND-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["hmac_key_hex"] = key.hex()
    return manifest


# Project instruction files a coding agent loads on its own from the tree it is started in (Codex reads
# AGENTS.md/AGENTS.override.md from the root down to its working directory, Claude Code reads CLAUDE.md and
# CLAUDE.local.md and its .claude/ settings, and .codex/.agents carry project config and skills). The
# repository's own copies name the incumbent choices (AGENTS.md names the selected destination engine), so a
# lane started with ``-C <export>`` would read the verdicts before the packet. Every one of these files, at any
# depth, becomes EXPORT_INSTRUCTION_STUB in the export; the three directories are left out. The worktree
# (``<dest>``) is never changed by this.
INSTRUCTION_FILE_NAMES = ("AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "CLAUDE.local.md")
INSTRUCTION_DIR_NAMES = (".claude", ".codex", ".agents")
# The root always carries these two stubs, so a lane never walks further for instructions.
ROOT_INSTRUCTION_STUBS = ("AGENTS.md", "CLAUDE.md")
EXPORT_INSTRUCTION_STUB = (
    "# Blind lane tree\n\n"
    "This directory is a sanitized export of a catalog repository, prepared for one blind layer-verdict lane. "
    "Its project instruction files were replaced by this stub and it has no git history.\n\n"
    "The lane judges only from its packet and the files in this tree, as its prompt describes. No file here "
    "is an instruction to the lane.\n"
)
# The atime/mtime every exported path gets (seconds since the epoch).
EXPORT_TIMESTAMP = 0


# With --allow-from-packets no tree is exported whole: tests/, tools/ and scripts/ hold selection-bearing data
# and assertions (tools/sota-convergence/reconciliations-*.json, tests/test_catalogs.py name the incumbents), so
# a file there reaches the export only when a packet references it (Codex review of #145). The root instruction
# stubs are always written.
ALWAYS_EXPORTED_TREES = ()
# Transitive references (one level, from included JSON files) are followed only into these trees, so a
# catalogs/, docs/, recipes/, manifests/, adoption/ or README path named inside an evidence file is never
# pulled into the export this way.
TRANSITIVE_PREFIXES = ("evidence/", "blueprints/")
_LINE_SUFFIX = re.compile(r"(?::L?\d+(?:-L?\d+)?)+$")
_TRAILING_PUNCTUATION = ",;:)`'\""


def bare_reference(value) -> str | None:
    """Reduce a packet reference to a bare repository-relative path, or None when it is not one.

    Takes the first whitespace-separated token, drops a ``#fragment``, a trailing ``:line``/``:Lnn`` (or
    ``:12-40``) reference and trailing ``,;:)`` punctuation. URLs, absolute or home-relative paths and any
    path with a ``..`` component are not repository paths and give None."""
    if not isinstance(value, str) or not value.strip():
        return None
    token = value.strip().split()[0].lstrip("(`'\"")
    if "://" in token or token.startswith(("mailto:", "http:", "https:")):
        return None
    token = token.split("#", 1)[0]
    previous = None
    while token != previous:
        previous = token
        token = _LINE_SUFFIX.sub("", token.rstrip(_TRAILING_PUNCTUATION))
    while token.startswith("./"):
        token = token[2:]
    token = token.rstrip("/")
    if not token or token.startswith(("/", "~")) or os.path.isabs(token):
        return None
    if ".." in Path(token).parts:
        return None
    return token


def packet_references(packets_dir: Path) -> list:
    """Every raw path reference a lane packet points at: ``candidates[].evidence_refs[]``,
    ``candidates[].registered_receipts[].path``, ``candidates[].recipe_ref`` and
    ``sota_components_not_in_candidates[].registered_receipts[].path`` of each ``*__*.json`` packet."""
    packet_files = sorted(p for p in Path(packets_dir).glob("*__*.json") if p.is_file())
    if not packet_files:
        raise SystemExit(f"--allow-from-packets {packets_dir} has no *__*.json packet files")
    references: list = []

    def receipts(entry):
        for receipt in entry.get("registered_receipts") or []:
            if isinstance(receipt, dict):
                references.append(receipt.get("path"))

    for packet_file in packet_files:
        packet = json.loads(packet_file.read_text(encoding="utf-8"))
        for candidate in packet.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            references.extend(candidate.get("evidence_refs") or [])
            receipts(candidate)
            references.append(candidate.get("recipe_ref"))
        for component in packet.get("sota_components_not_in_candidates") or []:
            if isinstance(component, dict):
                receipts(component)
    return references


def _expand_reference(root: Path, relative: str) -> set:
    """The repository-relative files (and symlinks) ``relative`` names under ``root``: itself, or, for a
    real directory, everything below it (not following symlinked directories)."""
    path = root / relative
    if path.is_symlink() or path.is_file():
        return {relative}
    if not path.is_dir():
        return set()
    found = set()
    for directory, dirs, files in os.walk(path, followlinks=False):
        for name in files + [d for d in dirs if (Path(directory) / d).is_symlink()]:
            found.add((Path(directory) / name).relative_to(root).as_posix())
    return found


def _string_values(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _string_values(value)
    elif isinstance(node, list):
        for value in node:
            yield from _string_values(value)


def build_allowlist(dest: Path, packets_dir: Path) -> dict:
    """The export allowlist for ``dest`` (the stripped worktree) from the lane packets in ``packets_dir``.

    Returns ``files`` (repository-relative paths to export), ``missing_refs`` (packet references with no
    path in ``dest``, sorted) and ``transitive_refs`` (the evidence/ and blueprints/ paths added from
    included JSON files, one level only, sorted)."""
    files: set = set()
    missing: set = set()
    for raw in packet_references(packets_dir):
        relative = bare_reference(raw)
        if relative is None:
            continue
        if not os.path.lexists(dest / relative):
            missing.add(relative)
            continue
        files |= _expand_reference(dest, relative)
    for tree in ALWAYS_EXPORTED_TREES:
        files |= _expand_reference(dest, tree)
    transitive: set = set()
    transitive_files: set = set()
    # One level: only the files selected above are scanned; files added here are not scanned in turn.
    for relative in sorted(files):
        path = dest / relative
        if not relative.endswith(".json") or path.is_symlink() or not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        for value in _string_values(document):
            reference = bare_reference(value)
            if reference is None or not reference.startswith(TRANSITIVE_PREFIXES):
                continue
            if not os.path.lexists(dest / reference):
                continue
            added = _expand_reference(dest, reference) - files
            if added:
                transitive.add(reference)
                transitive_files |= added
    files |= transitive_files
    return {"files": files, "missing_refs": sorted(missing), "transitive_refs": sorted(transitive)}


PROSE_SUFFIXES = (".md", ".markdown", ".txt", ".rst")
LEDGER_EXPORTS = {"foundation": "catalogs/landscape/foundation.json", "us-equities": "catalogs/landscape/us-equities.json"}
QUALITY_REVIEW_EXPORT = "catalogs/landscape/candidate-quality-review.json"


def align_exported_prose(export: Path, packets_dir: Path) -> int:
    """Give the exported ledger rows and quality-review layer entries the packets' reduced requirement, limitations
    and overturn text, and drop the quality review's evidence_gap (the catalog's analysis of its current choice):
    the sentences a packet withholds were otherwise exported verbatim (round 5, N2). Returns the entries changed."""
    packets = {}
    for packet_file in sorted(Path(packets_dir).glob("*__*.json")):
        packet = json.loads(packet_file.read_text(encoding="utf-8"))
        packets[(packet.get("catalog"), packet.get("layer_id"))] = packet
    changed = 0

    def rewrite(relative, update):
        nonlocal changed
        path = export / relative
        if path.is_symlink() or not path.is_file():
            return
        document = json.loads(path.read_text(encoding="utf-8"))
        changed += update(document)
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def ledger(catalog):
        def update(document):
            count = 0
            for row in document.get("layers") or []:
                packet = packets.get((catalog, row.get("layer_id")))
                if isinstance(row, dict) and packet is not None:
                    row.update({"requirement": packet.get("requirement"), "limitations": packet.get("limitations"),
                                "overturn_when": packet.get("existing_overturn_when")})
                    count += 1
            return count
        return update

    def quality(document):
        count = 0
        for entry in document.get("layer_coverage") or []:
            if not isinstance(entry, dict):
                continue
            packet = packets.get((entry.get("catalog"), entry.get("layer_id")))
            entry.pop("evidence_gap", None)
            entry["requirement"] = packet.get("requirement") if packet else None
            entry["overturn_when"] = packet.get("existing_overturn_when") if packet else None
            count += 1
        return count

    for catalog, relative in LEDGER_EXPORTS.items():
        rewrite(relative, ledger(catalog))
    rewrite(QUALITY_REVIEW_EXPORT, quality)
    return changed


def redact_selection_prose(export: Path, packets_dir: Path) -> dict:
    """Drop, from every exported prose file (outside fenced code), each sentence that uses a selection word and
    names a candidate of any packet: "Serena is the selected navigation layer" states the current choice before a
    lane reads the evidence (independent review of #145, round 4, F3: such a sentence reached 24 of the 30 scored
    layers through a directly cited or one-level transitive file). The term set is the union over all packets, so
    what is dropped does not depend on which candidate won. Returns {export-relative file: sentences dropped}."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from lane_packets import candidate_matcher, states_choice
    candidates = []
    for packet_file in sorted(Path(packets_dir).glob("*__*.json")):
        candidates.extend(json.loads(packet_file.read_text(encoding="utf-8")).get("candidates") or [])
    if not candidates:
        return {}
    matcher = candidate_matcher(candidates)

    def choice(sentence):
        return states_choice(sentence, matcher)

    redacted = {}
    for path in sorted(export.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in PROSE_SUFFIXES \
                or path.name in INSTRUCTION_FILE_NAMES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines, dropped = _redact_blocks(text.split("\n"), choice)
        if dropped:
            path.write_text("\n".join(lines), encoding="utf-8")
            redacted[path.relative_to(export).as_posix()] = dropped
    return redacted


# A Markdown line that starts its own block: a list item, heading, table row or quote.
_BLOCK_START = re.compile(r"^(\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+|>\s*|\|))")


def _redact_blocks(lines: list, states_choice) -> tuple:
    """(lines, sentences dropped): each prose block (a paragraph or list item with its wrapped continuation
    lines) is read as one text, so a sentence wrapped over two lines is still one sentence, and a block that loses
    a sentence is written back on one line. A table is one unit: when any row states the choice, the whole table
    goes, so no single broken row marks the winner (review of 52344da8). Fenced code is kept as it is."""
    out, dropped, fenced, block, table = [], 0, False, [], []

    def flush_block():
        nonlocal dropped
        if not block:
            return
        match = _BLOCK_START.match(block[0])
        prefix = match.group(1) if match else block[0][:len(block[0]) - len(block[0].lstrip())]
        content = " ".join([block[0][len(prefix):].strip()] + [line.strip() for line in block[1:]])
        sentences = re.split(r"(?<=[.!?;])\s+", content)
        kept = [sentence for sentence in sentences if not states_choice(sentence)]
        if len(kept) == len(sentences):
            out.extend(block)
        else:
            dropped += len(sentences) - len(kept)
            if kept:
                out.append(prefix + " ".join(kept))
        block.clear()

    def flush_table():
        nonlocal dropped
        if not table:
            return
        rows = [row for row in table if not re.fullmatch(r"\s*\|?[\s:|-]*\|?\s*", row)]
        if any(states_choice(row) for row in rows):
            dropped += len(rows)
        else:
            out.extend(table)
        table.clear()

    for line in lines:
        fence = line.lstrip().startswith("```")
        if fenced or fence:
            flush_block()
            flush_table()
            out.append(line)
            if fence:
                fenced = not fenced
            continue
        if line.lstrip().startswith("|"):
            flush_block()
            table.append(line)
            continue
        flush_table()
        if not line.strip():
            flush_block()
            out.append(line)
            continue
        if _BLOCK_START.match(line) or not block:
            flush_block()
        block.append(line)
    flush_block()
    flush_table()
    return out, dropped


def export_tree(dest: Path, export: Path, allow_from_packets: Path = None) -> dict:
    """Copy the stripped worktree to ``export`` without ``.git`` or ``BLIND-MANIFEST.json``: the worktree's
    ``.git`` reaches the source repository's history, where ``git show <rev>:<path>`` recovers every
    stripped value, and the manifest is the operator's audit trail. Lanes are given this copy.

    In the export only, every project instruction file (INSTRUCTION_FILE_NAMES, at any depth) is replaced
    by EXPORT_INSTRUCTION_STUB and every INSTRUCTION_DIR_NAMES directory is left out. Returns the
    export-relative paths of both, sorted. Without ``allow_from_packets``, Markdown prose elsewhere
    (README.md, docs/, blueprints/ and others) is copied unchanged and can still name the incumbent choices.

    With ``allow_from_packets`` (a lane-packets directory), the export holds only the paths those packets
    reference, one level of evidence/ and blueprints/ paths named inside included JSON files and the root
    instruction stubs (see build_allowlist); the result then also carries
    ``allowlisted_files`` (count), ``missing_refs`` (sorted list) and ``transitive_refs`` (count).

    Every regular file, directory and symlink in the export gets the same fixed atime/mtime (0), so a
    stripped file cannot be told apart from an untouched one by its timestamp."""
    if export.exists():
        raise SystemExit(f"--export {export} already exists")
    removed_dirs: list = []
    allowlist = build_allowlist(dest, allow_from_packets) if allow_from_packets is not None else None
    allowed_files = allowlist["files"] if allowlist is not None else None
    allowed_dirs: set = set()
    if allowed_files is not None:
        for relative in allowed_files:
            parts = relative.split("/")
            for depth in range(1, len(parts)):
                allowed_dirs.add("/".join(parts[:depth]))

    def ignore(directory, names):
        skipped = set(shutil.ignore_patterns(".git", "BLIND-MANIFEST.json")(directory, names))
        for name in names:
            if name in INSTRUCTION_DIR_NAMES:
                skipped.add(name)
                removed_dirs.append((Path(directory) / name).relative_to(dest).as_posix())
            elif allowed_files is not None and name not in skipped:
                path = Path(directory) / name
                relative = path.relative_to(dest).as_posix()
                if path.is_dir() and not path.is_symlink():
                    if relative not in allowed_dirs:
                        skipped.add(name)
                elif relative not in allowed_files:
                    skipped.add(name)
        return skipped

    shutil.copytree(dest, export, symlinks=True, ignore=ignore)
    # A symlink that is absolute or resolves outside the export would let a lane read the original checkout
    # or host files, past both label stripping and instruction replacement (Codex review of #145): removed.
    removed_links: list = []
    export_root = export.resolve()
    for directory, dirs, files in os.walk(export, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            if not path.is_symlink():
                continue
            target = os.readlink(path)
            resolved = (path.parent / target).resolve()
            if os.path.isabs(target) or not (resolved == export_root or export_root in resolved.parents):
                path.unlink()
                removed_links.append(path.relative_to(export).as_posix())
    replaced: list = []
    # os.walk without followlinks: a symlinked directory in the tree may point outside the export, and
    # nothing outside the export is ever written.
    for directory, dirs, files in os.walk(export, followlinks=False):
        # An instruction name can be a symlink to a directory, which os.walk lists in dirs (Codex review of
        # #145), or even a real directory: every form is replaced by the stub.
        for name in sorted(set(dirs + files) & set(INSTRUCTION_FILE_NAMES)):
            path = Path(directory) / name
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            if name in dirs:
                dirs.remove(name)
            path.write_text(EXPORT_INSTRUCTION_STUB, encoding="utf-8")
            replaced.append(path.relative_to(export).as_posix())
    for name in ROOT_INSTRUCTION_STUBS:
        root_file = export / name
        if root_file.is_symlink() or not root_file.is_file():
            if root_file.is_symlink() or root_file.is_file():
                root_file.unlink()
            elif root_file.is_dir():
                shutil.rmtree(root_file)
            root_file.write_text(EXPORT_INSTRUCTION_STUB, encoding="utf-8")
            if name not in replaced:
                replaced.append(name)
    aligned = align_exported_prose(export, allow_from_packets) if allow_from_packets is not None else 0
    redacted = redact_selection_prose(export, allow_from_packets) if allow_from_packets is not None else {}
    # A stripped (rewritten) file would otherwise carry a newer mtime than an untouched one.
    for directory, dirs, files in os.walk(export, topdown=False, followlinks=False):
        for name in files + dirs:
            path = Path(directory) / name
            if path.is_symlink():
                if os.utime in os.supports_follow_symlinks:
                    os.utime(path, (EXPORT_TIMESTAMP, EXPORT_TIMESTAMP), follow_symlinks=False)
            else:
                os.utime(path, (EXPORT_TIMESTAMP, EXPORT_TIMESTAMP))
    os.utime(export, (EXPORT_TIMESTAMP, EXPORT_TIMESTAMP))
    result = {"replaced_instruction_files": sorted(replaced), "removed_instruction_dirs": sorted(removed_dirs),
              "removed_escaping_symlinks": sorted(removed_links)}
    if allowlist is not None:
        result.update({"allowlisted_files": len(allowed_files), "missing_refs": allowlist["missing_refs"],
                       "transitive_refs": len(allowlist["transitive_refs"]),
                       "redacted_prose_sentences": sum(redacted.values()), "redacted_prose_files": len(redacted),
                       "aligned_prose_entries": aligned})
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True, help="An existing git checkout.")
    parser.add_argument("--rev", required=True, help="Any commit-ish --source can resolve.")
    parser.add_argument("--dest", type=Path, required=True, help="Must not already exist.")
    parser.add_argument("--export", type=Path,
                        help="Also copy the stripped tree here without .git or BLIND-MANIFEST.json (must not exist); "
                             "hand this copy, not the worktree, to the lanes.")
    parser.add_argument("--allow-missing-refs", action="store_true",
                        help="Keep an export although the packets reference paths it lacks (refused by default).")
    parser.add_argument("--allow-from-packets", type=Path, metavar="PACKETS_DIR",
                        help="With --export: export only the paths the lane packets PACKETS_DIR/*__*.json reference, "
                             "one level of evidence/ and blueprints/ paths named in included JSON files, and the root "
                             "instruction stubs (no tree is exported whole).")
    args = parser.parse_args(argv)
    if args.allow_from_packets is not None and args.export is None:
        parser.error("--allow-from-packets requires --export")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    source = args.source.resolve()
    dest = args.dest.resolve()
    export = args.export.resolve() if args.export else None
    packets = args.allow_from_packets.resolve() if args.allow_from_packets else None
    if export is not None and export.exists():
        raise SystemExit(f"--export {export} already exists")
    if export is not None:
        # The blind lanes and the adjudicator refuse an export outside the shared root rule, so refuse it before
        # any work (independent review of #145, O3).
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from codex_lane import root_issue
        for candidate in (Path(os.path.abspath(args.export)), export):
            issue = root_issue(candidate)
            if issue:
                raise SystemExit(f"--export {issue}; place the blind export at least four directories deep (not /, "
                                 "/home, /tmp or a home directory itself) and outside every repository")
        # Git history would recover every stripped label (re-review N5): refuse an export inside a repository.
        for ancestor in export.parents:
            if (ancestor / ".git").exists():
                raise SystemExit(f"--export {export} is inside the git repository {ancestor}; place it outside every "
                                 "repository")
    if export is not None:
        # The export must not overlap the worktree or the source (R4-REG-8).
        for label, other in (("--dest", dest), ("--source", source)):
            if export == other or other in export.parents or export in other.parents:
                raise SystemExit(f"--export {export} overlaps {label} {other}; place it elsewhere")
    if packets is not None:
        packet_references(packets)  # refuses a directory without packets before the worktree is created
    manifest = run_blind_checkout(source, args.rev, dest)
    sanitized = export_tree(dest, export, allow_from_packets=packets) if export is not None else None
    if sanitized is not None and sanitized.get("missing_refs") and not args.allow_missing_refs:
        # A packet pointing a lane at a file the export lacks (independent review of #145, F4/OPS-1): build the
        # packets with lane_packets.py --withhold-labels, which drops references to removed files.
        missing = sanitized["missing_refs"]
        shutil.rmtree(export)
        # The worktree goes too, so a rerun is not refused with "--dest already exists" (review of 52344da8).
        subprocess.run(["git", "worktree", "remove", "--force", str(dest)], cwd=str(source), capture_output=True)
        raise SystemExit(f"the packets reference {len(missing)} path(s) the export lacks ({', '.join(missing[:10])}); "
                         "rebuild them with lane_packets.py --withhold-labels, or pass --allow-missing-refs")
    key_path = dest.parent / f"{dest.name}.hmac-key"
    # Owner-only, created exclusively: the key reverses the keyed hashes over a small
    # vocabulary, so no lane that can read the parent directory may read it.
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(manifest.pop("hmac_key_hex") + "\n")
    print(json.dumps({"removed_files": len(manifest["removed_files"]),
                       "stripped_fields": len(manifest["stripped_fields"]),
                       "hmac_key_path": str(key_path),
                       "export": str(export) if export is not None else None,
                       "export_instruction_files_replaced": sanitized["replaced_instruction_files"] if sanitized else None,
                       "export_instruction_dirs_removed": sanitized["removed_instruction_dirs"] if sanitized else None,
                       "export_escaping_symlinks_removed": sanitized["removed_escaping_symlinks"] if sanitized else None,
                       "export_allowlisted_files": sanitized.get("allowlisted_files") if sanitized else None,
                       "export_missing_refs": sanitized.get("missing_refs") if sanitized else None,
                       "export_transitive_refs": sanitized.get("transitive_refs") if sanitized else None,
                       "export_redacted_prose_sentences": sanitized.get("redacted_prose_sentences") if sanitized else None},
                      sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
