#!/usr/bin/env python3
"""Validate one inactive historical WSL artifact; never execute its commands."""

import argparse
import ast
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tomllib

if __package__:
    from .validate import Validator, _json_without_duplicates
else:
    from validate import Validator, _json_without_duplicates


LEAF = "blueprints/convergence-practice/wsl-retrieval/"
POLICY = LEAF + "archive-policy-20261002.json"
RECORD = LEAF + "experiment.json"
RECORD_SHA = "a029dc2d8de56dd387202e5bffc341ad9d0a163e93f7bc01954b932f4ecf0244"
POINTER = "/frozen_inputs/evaluation/3"
RUNNER = LEAF + "run.py"
ORIGINAL_SHA = "be852ce99501f5bc4567b846b90fb0e91d91de77b0eafbd3b72bb4484a2f7d12"
SNAPSHOT = LEAF + "run-future-before-archive-20261002.py.txt"
GUARDED_SHA = "728f4e52d6929cde6ef64c731f9c6aeb06e21703616ceb2face33ee10996c116"
LOCK = LEAF + "package-lock.json"
LOCK_SHA = "5c51ee65cc477f2c1488a38ff5cad1c0a737f81a5b61bbd70d5edc4d15bfc3bb"
CONFIG = ".github/osv-scanner-frozen-wsl-retrieval.toml"
ADVISORY = "GHSA-vfj7-8cjw-p6xm"
REFUSAL = "archived_qmd_activation_denied"
ISSUED = "2026-10-03T00:00:00Z"
EXPIRES = "2026-11-02T00:00:00Z"
WORKFLOW_SHA = '3a390947f34d0b244dee7adfe97ade5b4e22cc9cc130dde94c2d852d39aeb7da'
OWNER = "https://github.com/seathatflowsinourveins/native-agent-stack/issues/384"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file(root, name):
    validator = Validator(root)
    path = validator.path(name, "archive artifact")
    require(path is not None, "; ".join(validator.errors))
    return path


def read_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=_json_without_duplicates)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_pairs(value, pointer=""):
    if isinstance(value, dict):
        if set(value) == {"path", "sha256"}:
            yield pointer, value
        else:
            for key, item in value.items():
                escaped = key.replace("~", "~0").replace("/", "~1")
                yield from artifact_pairs(item, pointer + "/" + escaped)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from artifact_pairs(item, pointer + "/" + str(index))


def check(root, now=None):
    require(not Path(root).is_symlink(), "archive root: symlinks are forbidden")
    policy = read_json(file(root, POLICY))
    expected = {
        "schema_version": "wsl-retrieval-archival-binding/1",
        "source_revision": "999eebd76f57f459294fa4c3d5626676aff66451",
        "owner_issue": OWNER,
        "issued_utc": ISSUED,
        "expires_utc": EXPIRES,
        "activation_allowed": False,
        "automatic_renewal": False,
        "record": {"path": RECORD, "sha256": RECORD_SHA},
        "pointer": POINTER,
        "declared_artifact": {"path": RUNNER, "sha256": ORIGINAL_SHA},
        "snapshot": {"path": SNAPSHOT, "sha256": ORIGINAL_SHA},
        "guarded_runner": {"path": RUNNER, "sha256": GUARDED_SHA},
        "lock": {"path": LOCK, "sha256": LOCK_SHA},
        "scanner_config": CONFIG,
        "advisory": ADVISORY,
        "workflow": {"path": ".github/workflows/security-scan.yml", "sha256": WORKFLOW_SHA},
    }
    require(policy == expected and type(policy.get("activation_allowed")) is bool
            and type(policy.get("automatic_renewal")) is bool,
            "archive policy: exact versioned scope required")
    issued = datetime.fromisoformat(policy["issued_utc"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(policy["expires_utc"].replace("Z", "+00:00"))
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None, "archive clock: UTC-aware time required")
    require(issued <= now < expires and expires - issued <= timedelta(days=90),
            "archive policy: not active or expired")
    require(digest(file(root, ".github/workflows/security-scan.yml")) == WORKFLOW_SHA,
            "archive scanner: reviewed workflow changed")
    record_path = file(root, RECORD)
    require(digest(record_path) == RECORD_SHA, "archive record: original bytes changed")
    record = read_json(record_path)
    original = record["frozen_inputs"]["evaluation"][3]
    require(original == expected["declared_artifact"], "archive binding: declared pair changed")
    require(digest(file(root, SNAPSHOT)) == ORIGINAL_SHA, "archive snapshot: bytes changed")
    runner = file(root, RUNNER)
    require(digest(runner) == GUARDED_SHA, "archive guard: reviewed bytes changed")
    body = next(n.body for n in ast.parse(runner.read_bytes()).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    parsed = next(i for i, n in enumerate(body) if isinstance(n, ast.Assign)
                  and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute)
                  and n.value.func.attr == "parse_args")
    guard = ast.parse("if args.mode == 'qmd':\n    parser.error('" + REFUSAL + "')").body[0]
    require(ast.dump(body[parsed + 1]) == ast.dump(guard), "archive guard: early unconditional refusal required")
    preflight = ast.parse("archive_preflight(parser)").body[0]
    require(ast.dump(body[parsed + 2]) == ast.dump(preflight), "archive guard: independent early preflight required")
    require(digest(file(root, LOCK)) == LOCK_SHA, "archive lock: original bytes changed")
    pairs = list(artifact_pairs(record))
    require(sum(pointer == POINTER for pointer, _ in pairs) == 1, "archive binding: exactly one pointer required")
    for pointer, artifact in pairs:
        path = SNAPSHOT if pointer == POINTER else artifact["path"]
        require(digest(file(root, path)) == artifact["sha256"], "archive historical artifact: bytes changed")

    config = tomllib.loads(file(root, CONFIG).read_text())
    require(set(config) == {"IgnoredVulns"} and len(config["IgnoredVulns"]) == 1,
            "archive scanner: exactly one advisory and no overrides required")
    ignore = config["IgnoredVulns"][0]
    require(set(ignore) == {"id", "reason", "ignoreUntil"} and ignore["id"] == ADVISORY
            and str(ignore["reason"]).strip() and isinstance(ignore["ignoreUntil"], datetime)
            and ignore["ignoreUntil"].tzinfo is not None and ignore["ignoreUntil"] == expires,
            "archive scanner: advisory/reason/expiry mismatch")
    ordinary = tomllib.loads(file(root, ".github/osv-scanner.toml").read_text())
    require(not {ADVISORY, "CVE-2026-93687"} & {entry["id"] for entry in ordinary.get("IgnoredVulns", [])},
            "archive scanner: ordinary advisory suppression forbidden")
    require("braces" not in {str(entry.get("name", "")).lower()
                            for entry in ordinary.get("PackageOverrides", [])},
            "archive scanner: ordinary package override forbidden")
    inventory = read_json(file(root, ".github/osv-scanner-lockfiles.json"))["lockfiles"]
    require(len({entry["path"] for entry in inventory}) == len(inventory), "archive scanner: duplicate lock path")
    require([entry for entry in inventory if entry.get("config") == CONFIG]
            == [{"path": LOCK, "config": CONFIG}], "archive scanner: exact single lock scope required")
    require(all(entry.get("config") in (None, CONFIG, ".github/osv-scanner-frozen-macos.toml")
                for entry in inventory), "archive scanner: unknown config partition")
    return {"record": RECORD, "pointer": POINTER, "declared_path": RUNNER,
            "declared_sha256": ORIGINAL_SHA, "resolved_snapshot": SNAPSHOT,
            "current_guard_sha256": GUARDED_SHA, "expires_utc": EXPIRES,
            "historical_artifact_pairs_checked": len(pairs)}


def validate_archive(root, now=None):
    try:
        witness = check(root, now)
        return {"valid": True, "errors": [], "archival_binding": witness}
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration, SyntaxError) as error:
        message = str(error) if isinstance(error, ValueError) else "archive policy: unreadable or invalid artifact"
        return {"valid": False, "errors": [message]}


def resolve_evaluation(root, record_path, record_sha, pointer, artifact):
    """No fallback: this function is called only for the one historical slot."""
    require(record_path == RECORD and record_sha == RECORD_SHA and pointer == POINTER
            and artifact == {"path": RUNNER, "sha256": ORIGINAL_SHA},
            "archive binding: exact original record/pointer/pair required")
    result = validate_archive(root)
    require(result["valid"], "; ".join(result["errors"]))
    return file(root, SNAPSHOT), result["archival_binding"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_archive(args.root)
    print(json.dumps(result, sort_keys=True) if args.json else ("valid" if result["valid"] else "; ".join(result["errors"])))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
