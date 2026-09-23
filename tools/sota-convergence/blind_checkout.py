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
  (``is_label_value`` below) -- a string equal to one of a short fixed set
  (``default``, ``selected``, ``conditional``, ``optional``, ``candidate``,
  ``trial``, ``retain``, ``keep_but_compare``, ``adjust``,
  ``confirmed_default``, ``selected_destination``), or a string that itself
  states a selection (contains "selected", or matches "keep ... selected").
  A mapping/rule structure under one of these keys, or an unrelated data
  value such as ``"top_20"``, is left untouched.

Nothing here re-derives, judges or replaces a stripped value; this is a
mechanical redaction pass over a detached worktree, run once per blind
review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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
}

REMOVE_GLOBS = (
    "evidence/artifacts/layer-verdicts-*",
    "catalogs/sota-convergence/layer-verdicts-*.json",
    "docs/grand-catalog-handbook.md",
    "docs/ecosystem/index.html",
    "docs/ecosystem/manifest.json",
)

LABEL_VALUES = frozenset({
    "default", "selected", "conditional", "optional", "candidate", "trial",
    "retain", "keep_but_compare", "adjust", "confirmed_default", "selected_destination",
})
_SELECTED_WORD = re.compile(r"selected", re.IGNORECASE)
_KEEP_SELECTED = re.compile(r"\bkeep\b.*\bselected\b", re.IGNORECASE)


def sha256_of(value) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_label_value(value) -> bool:
    """True when ``value`` names a selection rather than carrying data --
    a closed-vocabulary label string, or free text that itself states a
    selection. A non-string value (a mapping/rule structure, a list, a
    number) is never a label."""
    if not isinstance(value, str):
        return False
    if value in LABEL_VALUES:
        return True
    if _SELECTED_WORD.search(value) or _KEEP_SELECTED.search(value):
        return True
    return False


def strip_ledger_row(row: dict, pointer_prefix: str, stripped: list) -> None:
    for key, default in PENDING_LANES.items():
        if row.get(key) != default:
            if key in row:
                stripped.append({"path": f"{pointer_prefix}/{key}", "old_sha256": sha256_of(row[key])})
            row[key] = json.loads(json.dumps(default)) if isinstance(default, (list, dict)) else default
    for key in LEDGER_ROW_LABEL_KEYS:
        if key in row:
            stripped.append({"path": f"{pointer_prefix}/{key}", "old_sha256": sha256_of(row[key])})
            del row[key]
    for index, candidate in enumerate(row.get("candidates") or []):
        if not isinstance(candidate, dict):
            continue
        for key in LEDGER_CANDIDATE_LABEL_KEYS:
            if key in candidate:
                stripped.append({"path": f"{pointer_prefix}/candidates/{index}/{key}",
                                  "old_sha256": sha256_of(candidate[key])})
                del candidate[key]


def strip_ledger_document(document: dict, relative_path: str, stripped: list) -> None:
    for index, row in enumerate(document.get("layers") or []):
        if isinstance(row, dict):
            strip_ledger_row(row, f"{relative_path}#/layers/{index}", stripped)


def _walk_strip(node, path_prefix: str, stripped: list, keys: frozenset, *, only_labels: bool) -> None:
    if isinstance(node, dict):
        for key in list(node.keys()):
            pointer = f"{path_prefix}/{key}"
            value = node[key]
            if key in keys and (not only_labels or is_label_value(value)):
                stripped.append({"path": pointer, "old_sha256": sha256_of(value)})
                del node[key]
                continue
            _walk_strip(value, pointer, stripped, keys, only_labels=only_labels)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _walk_strip(item, f"{path_prefix}/{index}", stripped, keys, only_labels=only_labels)


def strip_catalog_unconditional(document, relative_path: str, stripped: list) -> None:
    _walk_strip(document, relative_path, stripped, CATALOGS_UNCONDITIONAL_KEYS, only_labels=False)


def strip_blueprint_labels(document, relative_path: str, stripped: list) -> None:
    _walk_strip(document, relative_path, stripped, BLUEPRINT_CONDITIONAL_KEYS, only_labels=True)


def git(args, cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=str(cwd), check=True,
                                capture_output=True, text=True)
    return completed.stdout


def create_worktree(source: Path, rev: str, dest: Path) -> None:
    if dest.exists():
        raise SystemExit(f"--dest already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "add", "--detach", str(dest), rev], cwd=source)


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


def strip_worktree(dest: Path) -> dict:
    """Mutate every file already checked out under ``dest`` in place; return
    the ``BLIND-MANIFEST.json`` payload (not written by this function)."""
    removed_files: list = []
    stripped_fields: list = []

    remove_paths(dest, removed_files)

    for relative in LEDGER_RELATIVE_FILES:
        path = dest / relative
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        before = json.dumps(document, sort_keys=True)
        strip_ledger_document(document, relative, stripped_fields)
        _rewrite_if_changed(path, before, document)

    for path in iter_json_files(dest, "catalogs"):
        relative = path.relative_to(dest).as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        before = json.dumps(document, sort_keys=True)
        strip_catalog_unconditional(document, relative, stripped_fields)
        _rewrite_if_changed(path, before, document)

    for path in iter_json_files(dest, "blueprints"):
        relative = path.relative_to(dest).as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        before = json.dumps(document, sort_keys=True)
        strip_blueprint_labels(document, relative, stripped_fields)
        _rewrite_if_changed(path, before, document)

    return {
        "schema_version": 1,
        "removed_files": sorted(removed_files),
        "stripped_fields": sorted(stripped_fields, key=lambda item: item["path"]),
    }


def run_blind_checkout(source: Path, rev: str, dest: Path) -> dict:
    create_worktree(source, rev, dest)
    manifest = strip_worktree(dest)
    manifest = {"source": str(source), "rev": rev, **manifest}
    (dest / "BLIND-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    print(json.dumps({"removed_files": len(manifest["removed_files"]),
                       "stripped_fields": len(manifest["stripped_fields"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
