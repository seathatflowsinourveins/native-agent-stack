#!/usr/bin/env python3
"""Repository MADR policy around native Git and PyYAML; no historical retrofit.

Sources: adr/madr@2475fe1973f66a12aaf58a91d8fa7b42c0f5ea3d:template/adr-template.md;
yaml/pyyaml@49790e73684bebad1df05ef8d828fa12f685bffb:lib/yaml/__init__.py:117-125;
https://git-scm.com/docs/git-log/2.53.0 and /docs/git-ls-tree/2.53.0.
The extra fields, landing selector and index are repository-specific policy.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import subprocess

INDEX = "docs/decisions/decision-metadata-index.json"
ANCHOR = "docs/decisions/2026-10-05-ci-decision-metadata.md"
SELECTOR = {"main_ref": "origin/main", "anchor": ANCHOR,
            "method": "first-parent-path-introduction"}
FIELDS = ("status", "date", "decision-makers", "consulted", "review_by",
          "evidence_class", "overturn_when")
EVIDENCE_CLASSES = {"source_review", "native_proven", "local_integration", "synthetic"}
RECORD = re.compile(r"docs/decisions/\d{4}-\d{2}-\d{2}-.+\.md\Z")


class MetadataError(ValueError):
    pass


def git(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(["git", "-c", "log.follow=false", *arguments],
                                cwd=root, text=True, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MetadataError("native Git unavailable or timed out") from error
    if result.returncode:
        raise MetadataError(f"native Git {arguments[0]} failed (exit {result.returncode})")
    return result.stdout


def resolve_baseline(root: Path) -> dict:
    """Resolve the main snapshot once; squash landing makes introduction its final tree."""
    try:
        if git(root, "rev-parse", "--is-shallow-repository").strip() != "false":
            raise MetadataError("full Git history is required")
        main_sha = git(root, "rev-parse", "--verify", SELECTOR["main_ref"] + "^{commit}").strip()
        arrivals = git(root, "log", "--first-parent", "--diff-merges=first-parent",
                       "--diff-filter=A", "--reverse", "--no-patch", "--no-renames",
                       "--format=%H", main_sha, "--", ANCHOR).splitlines()
        if not arrivals:
            return {"state": "pending_landing", "main_sha": main_sha}
        landing_sha = arrivals[0]
        if not re.fullmatch(r"[0-9a-f]{40,64}", landing_sha):
            raise MetadataError("Git did not return a landing commit")
        paths = git(root, "ls-tree", "-r", "--name-only", "-z", landing_sha,
                    "--", "docs/decisions").split("\0")
        return {"state": "resolved", "main_sha": main_sha, "landing_sha": landing_sha,
                "paths": {p for p in paths if RECORD.fullmatch(p)}}
    except MetadataError as error:
        return {"state": "unknown", "error": str(error)}


def iso_date(value: object, field: str) -> date:
    # SafeLoader returns date for date-only YAML, datetime for timestamps with a time.
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise MetadataError(f"{field} must be a date-only ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise MetadataError(f"{field} is not a valid calendar date") from error


def parse_record(path: Path) -> dict:
    """Use upstream safe_load; only repository policy is authored here."""
    try:
        import yaml
    except ImportError as error:
        raise MetadataError("PyYAML 6.0.3 is required for the explicit metadata mode") from error
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---":
            raise MetadataError("YAML frontmatter is required")
        end = lines.index("---", 1)
        metadata = yaml.safe_load("\n".join(lines[1:end]))
    except (OSError, UnicodeError, yaml.YAMLError, ValueError) as error:
        raise MetadataError("invalid or unterminated YAML frontmatter") from error
    if not isinstance(metadata, dict):
        raise MetadataError("frontmatter must be a mapping")
    for field in FIELDS:
        if field not in metadata:
            raise MetadataError(f"missing {field}")
    for field in ("status", "overturn_when"):
        if not isinstance(metadata[field], str) or not metadata[field].strip():
            raise MetadataError(f"{field} must be nonempty text")
    for field in ("decision-makers", "consulted"):
        value = metadata[field]
        if isinstance(value, str):
            valid = bool(value.strip())
        else:
            valid = isinstance(value, list) and bool(value) and all(
                isinstance(item, str) and item.strip() for item in value)
        if not valid:
            raise MetadataError(f"{field} must be nonempty text or a list of names")
    if not isinstance(metadata["evidence_class"], str) or metadata["evidence_class"] not in EVIDENCE_CLASSES:
        raise MetadataError("evidence_class must name a repository evidence class")
    decided = iso_date(metadata["date"], "date")
    review = iso_date(metadata["review_by"], "review_by")
    if not 0 <= (review - decided).days <= 90:
        raise MetadataError("review_by must be from 0 through 90 days after date")
    indexed = {field: metadata[field] for field in FIELDS}
    indexed.update(date=decided.isoformat(), review_by=review.isoformat())
    return indexed


def check(root: Path, *, write_index: bool = False) -> dict:
    baseline = resolve_baseline(root)
    public_baseline = {k: v for k, v in baseline.items() if k != "paths"}
    result = {"baseline": public_baseline, "status": baseline["state"], "errors": []}
    if baseline["state"] != "resolved":
        return result
    result["baseline"]["grandfathered_records"] = len(baseline["paths"])
    records = {}
    for path in sorted((root / "docs/decisions").glob("*.md")):
        relative = path.relative_to(root).as_posix()
        if RECORD.fullmatch(relative) and relative not in baseline["paths"]:
            try:
                records[relative] = parse_record(path)
            except MetadataError as error:
                result["errors"].append(f"{relative}: {error}")
    expected = {"schema_version": 1, "baseline": SELECTOR, "records": records}
    if not result["errors"]:
        try:
            index_path = root / INDEX
            if write_index:
                index_path.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            elif json.loads(index_path.read_text(encoding="utf-8")) != expected:
                result["errors"].append("decision metadata index is stale; run --write-index")
        except (OSError, UnicodeError, ValueError) as error:
            result["errors"].append("decision metadata index is missing or invalid")
    result.update(status="invalid" if result["errors"] else "passed", indexed_records=len(records))
    return result


def exit_code(result: dict) -> int:
    return {"passed": 0, "invalid": 1, "pending_landing": 2, "unknown": 3}[result["status"]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write-index", action="store_true", help="Refresh eligible metadata after R5 lands")
    args = parser.parse_args(argv)
    result = check(args.root, write_index=args.write_index)
    print(json.dumps(result, sort_keys=True))
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
