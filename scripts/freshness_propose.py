#!/usr/bin/env python3
"""Turn a scheduled catalog-freshness run's drift artifact into a reviewable,
report-only evidence branch: copy the artifact, write a
``scripts/validate.py``-shaped receipt, register every new file's hash, and
(only when it is still a tracked, non-build-artifact file) rebuild and rehash
the public explorer.

This module never selects, evaluates, or writes to a catalog file:
``catalogs/sota-convergence/*``, ``catalogs/landscape/*.json``,
``manifests/stack.json`` and ``layer-verdicts*`` stay owned by the separate
SOTA-convergence lane review (see ``recipes/sota-convergence-practice.md``).
It only ever adds files under ``evidence/artifacts/`` and
``evidence/receipts/``, and updates ``manifests/evidence.json``'s
registration and receipt list. It is invoked by the ``propose`` job in
``.github/workflows/catalog-freshness.yml``; see
``docs/decisions/2026-09-23-bot-pr-dispatch.md`` for why that job exists.

Every read/write here looks up a file by its ``path`` (or a receipt by its
``id``) rather than assuming a fixed position in ``manifests/evidence.json``'s
``files[]``/``receipts[]`` lists, and every hash registration is only ever
for a file this run itself creates or a file ``git ls-files`` currently
tracks -- so this keeps working whether or not ``docs/ecosystem/index.html``
is a tracked file or an untracked build artifact, and regardless of what
order ``files[]``/``receipts[]`` entries are kept in.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

try:
    from .host_receipts import register_file
    from .catalog_decisions import safe_file, unique_json
except ImportError:  # running as a plain script, not a package
    from host_receipts import register_file
    from catalog_decisions import safe_file, unique_json


RECEIPT_KIND = "upstream_provenance"
# Stack components already tracked by the freshness job's fixed CI-tool pin
# table (tests/test_catalog_freshness_pins.py) that are also manifests/
# stack.json component ids (actionlint and grype are pinned but are not
# stack components, so they are not usable as a receipt component_id).
FALLBACK_COMPONENT_IDS = ("gitleaks", "nautilus-trader", "syft", "zizmor")
_DRIFT_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|.*\|$")
_SEPARATOR_ROW = re.compile(r"\A\|[\s:|-]+\|\Z")
EXPLORER_PATH = "docs/ecosystem/index.html"


class FreshnessProposeError(ValueError):
    """A drift artifact or repository state this module cannot safely act on."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def drifted_component_ids(drift_md_text: str) -> list[str]:
    """Parse the ``| id | ... |`` drift-table body rows written by
    ``catalog-freshness.yml``'s "Diff the rebuilt manifest" step.

    Returns a sorted, de-duplicated list of ids, or ``[]`` when the report
    found no drift (its "No pin/upstream drift detected ..." sentence has no
    table at all).
    """
    ids: set[str] = set()
    in_table = False
    for line in drift_md_text.splitlines():
        stripped = line.strip()
        if not in_table:
            if stripped.startswith("| id "):
                in_table = True
            continue
        if not stripped.startswith("|"):
            break
        if _SEPARATOR_ROW.match(stripped):
            continue
        match = _DRIFT_ROW.match(stripped)
        if match:
            ids.add(match.group(1).strip())
    return sorted(ids)


def select_receipt_component_ids(drifted_ids, known_stack_ids) -> list[str]:
    """Component ids the receipt claims coverage over.

    Prefers this run's actual drifted ids, narrowed to ones
    ``manifests/stack.json`` still recognizes (a sota-convergence catalog id
    is not always a stack component id). Falls back to the freshness table's
    own fixed CI-tool stack components only when none of the drifted ids
    match a known stack component. Raises when neither set yields a known
    id, rather than emitting a receipt ``scripts/validate.py`` would reject.
    """
    matched = sorted(set(drifted_ids) & set(known_stack_ids))
    if matched:
        return matched
    fallback = sorted(set(FALLBACK_COMPONENT_IDS) & set(known_stack_ids))
    if fallback:
        return fallback
    raise FreshnessProposeError(
        "no drifted component id matches a known manifests/stack.json component, and none of the "
        "fixed fallback CI-tool ids (" + ", ".join(FALLBACK_COMPONENT_IDS) + ") are stack components either"
    )


def build_receipt(receipt_id: str, component_ids: list[str], drifted_component_count: int,
                   run_url: str, checked_at_utc: str) -> dict:
    """The evidence/receipts/*.json payload, shaped for scripts/validate.py's generic
    receipt rules (kind, claim, limitations, component_ids -- see scripts/validate.py's
    Validator.validate())."""
    return {
        "schema_version": 1,
        "id": receipt_id,
        "kind": RECEIPT_KIND,
        "component_ids": component_ids,
        "claim": (
            f"Scheduled catalog-freshness run ({run_url}) rebuilt the SOTA-convergence manifest and "
            f"found {drifted_component_count} component(s) with pin/upstream drift against the "
            "currently published manifest. This receipt, and the branch/PR it is registered from, are "
            "report-only: no catalogs/sota-convergence/*, catalogs/landscape/*.json, "
            "manifests/stack.json, or layer-verdicts* file was selected, evaluated, or changed by this "
            "run. A pin bump requires its own separately qualified receipt under evidence/artifacts/*/, "
            "produced by the existing SOTA-convergence lane review, not by this automation."
        ),
        "limitations": [
            "This is drift detection only: it reports that a pin or upstream 'latest' value differs "
            "from the published manifest; it does not evaluate, select, or adopt any candidate, and it "
            "changes no catalog selection file.",
            "component_ids lists only this run's drifted rows whose id is also a manifests/stack.json "
            "component (or, when none of this run's drifted ids match a stack component, a fixed "
            "fallback of the freshness table's own CI-tool stack components); it is not a claim that "
            "every drifted id in the full drift report was reviewed.",
            "The rebuilt manifest and drift table are read from this run's own catalog-freshness "
            "workflow artifact; this receipt does not independently re-fetch upstream sources.",
        ],
        "recorded_at_utc": checked_at_utc,
        "run_url": run_url,
        "drifted_component_count": drifted_component_count,
    }


def register_receipt(root: Path, receipt: dict, relative_path: str) -> None:
    """Upsert receipt's manifest-facing fields into manifests/evidence.json's
    receipts[], matched by id -- never by list position, since neither
    files[] nor receipts[] order is assumed stable across writers."""
    evidence_path = safe_file(root, "manifests/evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    entry = {
        "id": receipt["id"], "kind": receipt["kind"], "component_ids": receipt["component_ids"],
        "claim": receipt["claim"], "limitations": receipt["limitations"], "path": relative_path,
    }
    receipts = evidence.setdefault("receipts", [])
    for index, existing in enumerate(receipts):
        if isinstance(existing, dict) and existing.get("id") == entry["id"]:
            receipts[index] = entry
            break
    else:
        receipts.append(entry)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def is_git_tracked(root: Path, relative_path: str) -> bool:
    """True only if ``git ls-files`` currently tracks ``relative_path``.

    Used to gate the explorer rehash so this stays correct both before and
    after ``docs/ecosystem/index.html`` becomes an untracked build artifact;
    never assumes either state.
    """
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), "ls-files", "--error-unmatch", "--", relative_path],
        capture_output=True, text=True, timeout=10, check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == relative_path


def copy_artifact(root: Path, artifact_dir: Path, date_stamp: str) -> tuple[str, str]:
    """Copy the freshness job's drift.md and its newest manifest-*.json into
    evidence/artifacts/catalog-freshness-<date_stamp>/, returning their two
    repository-relative paths (drift, manifest)."""
    manifests = sorted(artifact_dir.glob("manifest-*.json"))
    if not manifests:
        raise FreshnessProposeError(f"no manifest-*.json found in {artifact_dir}")
    drift_source = artifact_dir / "drift.md"
    if not drift_source.is_file():
        raise FreshnessProposeError(f"drift.md not found in {artifact_dir}")
    destination_dir = safe_file_placeholder(root, f"evidence/artifacts/catalog-freshness-{date_stamp}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    drift_dest = destination_dir / "drift.md"
    manifest_dest = destination_dir / manifests[-1].name
    shutil.copyfile(drift_source, drift_dest)
    shutil.copyfile(manifests[-1], manifest_dest)
    return (
        drift_dest.resolve().relative_to(root.resolve()).as_posix(),
        manifest_dest.resolve().relative_to(root.resolve()).as_posix(),
    )


def safe_file_placeholder(root: Path, relative: str) -> Path:
    """Like catalog_decisions.safe_file, but for a path that may not exist yet
    (safe_file requires the final component to already be a file); used for a
    destination this module is about to create."""
    parts = PurePosixPath(relative)
    if parts.is_absolute() or str(parts) != relative or any(part in {".", "..", ".git"} for part in parts.parts):
        raise FreshnessProposeError(f"unsafe destination directory: {relative!r}")
    path = root
    for part in parts.parts:
        path = path / part
        if path.is_symlink():
            raise FreshnessProposeError(f"destination path traverses a symlink: {relative!r}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise FreshnessProposeError(f"destination path escapes the repository: {relative!r}")
    return path


def rebuild_explorer(root: Path, attempts: int = 3) -> None:
    """Rebuild docs/ecosystem/index.html and converge its registered hash.

    Registering the explorer's own hash only touches manifests/evidence.json's
    files[] entry, which scripts/build_ecosystem.py's EVIDENCE input-tracking
    explicitly excludes from the explorer's rendered content (only
    evidence.json's receipts[] feeds its output -- see build_data()'s
    "avoids generated-file self-reference" comment), so a single --write +
    register + --check pass should already converge; the retry bound is a
    safety margin, not evidence that more than one pass is ever needed.
    """
    last_returncode = None
    for _ in range(attempts):
        subprocess.run(["python3", "scripts/build_ecosystem.py", "--write"], cwd=root, check=True)
        register_file(root, EXPLORER_PATH)
        check = subprocess.run(["python3", "scripts/build_ecosystem.py", "--check"], cwd=root, check=False)
        if check.returncode == 0:
            return
        last_returncode = check.returncode
    raise FreshnessProposeError(
        f"scripts/build_ecosystem.py --check did not converge after {attempts} attempt(s) "
        f"(last exit {last_returncode})"
    )


def apply(root: Path, artifact_dir: Path, run_url: str, checked_at_utc: str | None = None) -> dict:
    """Build the artifact copy, receipt and registration for one catalog-freshness run.

    Returns a small JSON-serializable summary the calling workflow step reads
    (receipt path, artifact paths, resolved component_ids, and whether the
    explorer was rehashed).
    """
    checked_at_utc = checked_at_utc or utc_now()
    date_stamp = checked_at_utc[:10].replace("-", "")
    if not re.fullmatch(r"[0-9]{8}", date_stamp):
        raise FreshnessProposeError(f"checked_at_utc must start with an ISO date: {checked_at_utc!r}")

    drift_text = (artifact_dir / "drift.md").read_text(encoding="utf-8")
    drifted_ids = drifted_component_ids(drift_text)

    stack = json.loads(
        safe_file(root, "manifests/stack.json").read_text(encoding="utf-8"), object_pairs_hook=unique_json,
    )
    known_stack_ids = {
        component["id"] for component in stack.get("components", [])
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    component_ids = select_receipt_component_ids(drifted_ids, known_stack_ids)

    drift_relative, manifest_relative = copy_artifact(root, artifact_dir, date_stamp)

    receipt_id = f"catalog-freshness-{date_stamp}"
    receipt_relative = f"evidence/receipts/{receipt_id}.json"
    receipt = build_receipt(receipt_id, component_ids, len(drifted_ids), run_url, checked_at_utc)
    receipt_path = safe_file_placeholder(root, receipt_relative)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    # Register only files this job itself just created, or a file `git ls-files`
    # already tracks (the explorer rehash below) -- never a path assumed present.
    for relative in (drift_relative, manifest_relative, receipt_relative):
        register_file(root, relative)
    register_receipt(root, receipt, receipt_relative)

    rehashed_explorer = False
    if is_git_tracked(root, EXPLORER_PATH):
        rebuild_explorer(root)
        rehashed_explorer = True

    return {
        "receipt_id": receipt_id,
        "receipt_path": receipt_relative,
        "artifact_paths": [drift_relative, manifest_relative],
        "component_ids": component_ids,
        "drifted_component_count": len(drifted_ids),
        "rehashed_explorer": rehashed_explorer,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact-dir", type=Path, required=True,
                         help="Directory holding the downloaded catalog-freshness artifact "
                              "(drift.md and manifest-*.json).")
    parser.add_argument("--run-url", required=True,
                         help="The catalog-freshness run's own URL, recorded in the receipt's claim.")
    parser.add_argument("--checked-at-utc", default=None,
                         help="ISO-8601 UTC timestamp; defaults to now. Also fixes the date stamp used "
                              "in the receipt id and evidence directory name.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = apply(args.root.resolve(), args.artifact_dir.resolve(), args.run_url, args.checked_at_utc)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
