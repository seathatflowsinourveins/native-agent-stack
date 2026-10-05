"""Location-only report glue; never a CredData scorer or scanner runner.

Sources: Samsung/CredData@0b1940e171725ad8937311120b191602608a4801
benchmark/scanner/scanner.py:276-307 (exact path/span), meta_key.py:7-18;
betterleaks/betterleaks@81aff7a638638aae3a659845d089043e1d8fe9ac
report/finding.go (native report positions); native-agent-stack's P1 decision.
Modern reports cannot be loaded into CredData's legacy Gitleaks adapter for
quality scoring: its empty rule does not satisfy the current Category contract.
This module preserves native columns without claiming CredData column parity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re


class ReportError(ValueError):
    """Reject an incomplete/ambiguous report without echoing its contents."""


def _lexical_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        raise ReportError("invalid finding path")
    parts = value.split("/")
    components = parts[1:] if value.startswith("/") else parts
    if any(part in {".", "..", ""} for part in components):
        raise ReportError("ambiguous finding path")
    if "//" in value or "\\" in value or parts[0] in {".", ".."}:
        raise ReportError("ambiguous finding path")
    return PurePosixPath(value)


def _path(value: object, data_root: str | None) -> str:
    path = _lexical_path(value)
    if data_root is not None:
        root = _lexical_path(data_root)
        if not root.is_absolute() or root.name != "data":
            raise ReportError("data root must be an absolute data directory")
        if path.is_absolute():
            try:
                path = PurePosixPath("data") / path.relative_to(root)
            except ValueError:
                raise ReportError("finding outside data root") from None
        if len(path.parts) < 3 or path.parts[0] != "data" or path.parts.count("data") != 1:
            raise ReportError("finding outside CredData namespace")
    elif path.is_absolute():
        raise ReportError("history finding must be repository relative")
    return str(path)


def locations(report: object, *, data_root: str | None = None) -> dict:
    """Project []/null native reports; IDs/content never affect location identity.

    A caller must separately establish scan completion (exit0 under --exit-code0
    and a nonempty, newly written report). Null alone is not completion evidence.
    No filesystem resolution, metadata labels, corpus text or credential fields
    are accessed. History identity includes the full commit; CredData uses spans.
    """
    if data_root is not None:
        root = _lexical_path(data_root)
        if not root.is_absolute() or root.name != "data":
            raise ReportError("data root must be an absolute data directory")
    if report is None:
        report = []
    if not isinstance(report, list):
        raise ReportError("report must be an array or null")
    unique = set()
    spans = set()
    for finding in report:
        if not isinstance(finding, dict):
            raise ReportError("finding must be an object")
        try:
            path = _path(finding["File"], data_root)
            start, end = finding["StartLine"], finding["EndLine"]
            columns = (finding["StartColumn"], finding["EndColumn"])
        except KeyError:
            raise ReportError("finding missing required location") from None
        if any(type(n) is not int for n in (start, end, *columns)):
            raise ReportError("location coordinates must be integers")
        if start < 1 or end < start or min(columns) < 0 or (start == end and columns[1] < columns[0]):
            raise ReportError("invalid location coordinates")
        commit = ""
        if data_root is None:
            commit = finding.get("Commit")
            if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
                raise ReportError("history finding missing full SHA1 commit")
        unique.add((commit, path, start, end, *columns))
        spans.add((commit, path, start, end))
    rows = [dict(zip(("commit", "path", "start_line", "end_line", "start_column", "end_column"), item))
            for item in sorted(unique)]
    return {"schema_version": 1, "evidence_class": "local_integration",
            "scope": "history_locations" if data_root is None else "creddata_locations",
            "quality_scored": False, "finding_count": len(report),
            "unique_location_count": len(rows), "unique_line_span_count": len(spans),
            "duplicate_location_count": len(report) - len(rows), "locations": rows}


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReportError("duplicate JSON key")
        result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--data-root", help="absolute prepared CredData data directory; omit for git history")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        projected = locations(json.loads(args.report.read_text(), object_pairs_hook=_unique_keys),
                              data_root=args.data_root)
    except (OSError, UnicodeError, json.JSONDecodeError, ReportError):
        parser.exit(2, "report rejected: unreadable or invalid location metadata\n")
    args.output.write_text(json.dumps(projected, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
