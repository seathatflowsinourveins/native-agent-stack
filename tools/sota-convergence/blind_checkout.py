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
  ``docs/grand-catalog-handbook.md``, ``docs/ecosystem/index.html`` and
  ``docs/ecosystem/manifest.json``.
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
  wherever they appear, at any nesting depth, regardless of their value.
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

# The same five keys, but under blueprints/ they are stripped only when the
# value is itself a label (see is_label_value); a mapping/rule value or a
# plain data value (e.g. "top_20") under one of these keys is left alone.
BLUEPRINT_CONDITIONAL_KEYS = CATALOGS_UNCONDITIONAL_KEYS

LEDGER_ROW_LABEL_KEYS = ("current_choice", "decision", "rationale")
LEDGER_CANDIDATE_LABEL_KEYS = ("disposition", "rationale", "review_status")

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


def strip_ledger_row(row: dict, pointer_prefix: str, stripped: list, hmac_key: bytes) -> None:
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


def _walk_strip(node, path_prefix: str, stripped: list, keys: frozenset, *, only_labels: bool,
                hmac_key: bytes) -> None:
    if isinstance(node, dict):
        for key in list(node.keys()):
            pointer = f"{path_prefix}/{key}"
            value = node[key]
            if key in keys and (not only_labels or is_label_value(value)):
                stripped.append({"path": pointer, "old_sha256": hmac_sha256_of(value, hmac_key)})
                del node[key]
                continue
            _walk_strip(value, pointer, stripped, keys, only_labels=only_labels, hmac_key=hmac_key)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _walk_strip(item, f"{path_prefix}/{index}", stripped, keys, only_labels=only_labels, hmac_key=hmac_key)


def strip_catalog_unconditional(document, relative_path: str, stripped: list, hmac_key: bytes) -> None:
    _walk_strip(document, relative_path, stripped, CATALOGS_UNCONDITIONAL_KEYS, only_labels=False, hmac_key=hmac_key)


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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True, help="An existing git checkout.")
    parser.add_argument("--rev", required=True, help="Any commit-ish --source can resolve.")
    parser.add_argument("--dest", type=Path, required=True, help="Must not already exist.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    source = args.source.resolve()
    dest = args.dest.resolve()
    manifest = run_blind_checkout(source, args.rev, dest)
    key_path = dest.parent / f"{dest.name}.hmac-key"
    # Owner-only, created exclusively: the key reverses the keyed hashes over a small
    # vocabulary, so no lane that can read the parent directory may read it.
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(manifest.pop("hmac_key_hex") + "\n")
    print(json.dumps({"removed_files": len(manifest["removed_files"]),
                       "stripped_fields": len(manifest["stripped_fields"]),
                       "hmac_key_path": str(key_path)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
