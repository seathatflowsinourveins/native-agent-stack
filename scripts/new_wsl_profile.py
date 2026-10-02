#!/usr/bin/env python3
"""Read W-PROF for a handbook consumer; validate structure without provisioning.

Reference implementations at 20ea4ae23: adoption_status.py's bounded JSON/path
contract and build_ecosystem.py's source-data adapter. --json returns the original
contract, including nulls and blocking gaps. A successful exit validates that
contract; it does not qualify an installation or choose a comparison winner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

try:
    from .adoption_status import InvalidManifest, recipe_path, require, unique_json
except ImportError:
    from adoption_status import InvalidManifest, recipe_path, require, unique_json


SOURCE_PATH = "adoption/new-wsl-profile.json"
DEFAULTS_MANIFEST = "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"
EVIDENCE_CLASS = "source_review_recommendations"
VERSION_FLOOR_RULE = ("The pin is the last qualified release and a floor; the bootstrap installs the pin and keeps a newer "
                      "existing install; the receipt records the installed version; a release newer than the pin counts as "
                      "installed and not yet qualified until its acceptance command has passed on that host.")
ACCEPTANCE_CLASSES = {"documented_upstream_example_not_executed", "upstream_test_command_not_executed"}
ENTRY_FIELDS = {"name", "layer_id", "owner_layer_id", "status", "repository", "pin", "checksum",
                "install", "acceptance", "stage", "position", "blocking_gaps", "evidence_refs",
                "provisioning_status"}
# The step the bootstrap does not perform: each native client moves to the current release with its own command, and
# the receipt then records these three facts for it.
NATIVE_UPDATE_CLIENTS = {"codex", "claude-code"}
NATIVE_UPDATE_FIELDS = {"command", "help_observation", "sources", "order", "on_refusal", "after_update",
                        "execution_status", "receipt_fields"}
RECEIPT_FIELDS = {"floor", "version_after_native_update", "acceptance_result_on_that_version"}
# The gate for a second systemd distribution is the recipe's W5 paired record; it stays UNRUN until it is observed on
# the real distribution.
PAIRED_PROOF_ID = "paired-systemd-distribution-proof"


def strings(value):
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def https_url(value):
    if not isinstance(value, str) or any(char.isspace() for char in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname) and url.username is None
                and url.password is None and not url.query and not url.fragment and "\\" not in value)
    except ValueError:
        return False


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def validate_native_update(row, update):
    """A native client moves to the current release by its own command; a source review leaves that step unrun."""
    name = row["name"]
    require(isinstance(update, dict) and NATIVE_UPDATE_FIELDS.issubset(update),
            f"{name}: native update fields are incomplete")
    require(all(filled(update[field]) for field in ("command", "help_observation", "order", "on_refusal", "after_update")),
            f"{name}: native update contains an invalid field")
    require(strings(update["sources"]) and bool(update["sources"])
            and all(source.startswith("https://") or "://" not in source for source in update["sources"]),
            f"{name}: native update sources must be repository paths or HTTPS URLs")
    require(update["execution_status"] == "UNRUN", f"{name}: a source review cannot run the native update")
    receipt = update["receipt_fields"]
    require(isinstance(receipt, dict) and set(receipt) == RECEIPT_FIELDS and all(filled(item) for item in receipt.values()),
            f"{name}: the receipt records exactly the floor, the version after the native update and the acceptance "
            "result on that version")


def validate_host_prerequisites(items):
    """Declare the release target and the paired proof; the proof's status for the real distribution stays UNRUN."""
    require(isinstance(items, list) and bool(items), "host_prerequisites must be a nonempty array")
    seen = {}
    for item in items:
        require(isinstance(item, dict) and filled(item.get("id")) and item["id"] not in seen,
                "each host prerequisite needs one unique id")
        seen[item["id"]] = item
        require(filled(item.get("requirement")) and filled(item.get("gate_source")),
                f"{item['id']}: host prerequisite needs its statement and its gate source")
        require(all(item.get(key) is None or strings(item[key]) for key in ("observations", "sources")),
                f"{item['id']}: observations and sources must be text lists")
        require(all(re.fullmatch(r"https://[A-Za-z0-9.-]+/\S*", source) for source in item.get("sources") or []),
                f"{item['id']}: sources must be HTTPS URLs")
    paired = seen.get(PAIRED_PROOF_ID)
    require(paired is not None, "the paired proof for two systemd distributions must be declared")
    require(paired.get("execution_status") == "UNRUN",
            "the paired proof stays UNRUN until it is observed on the real distribution")
    rehearsal = paired.get("rehearsal")
    require(isinstance(rehearsal, dict) and filled(rehearsal.get("result")) and filled(rehearsal.get("scope"))
            and isinstance(rehearsal.get("record"), str)
            and re.fullmatch(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+", rehearsal["record"])
            and ".." not in rehearsal["record"].split("/"),
            "the paired proof must name its rehearsal record by repository path")


def validate_profile(data, source_path=SOURCE_PATH, profile_id=None):
    require(isinstance(data, dict), "source profile must be an object")
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "source profile schema_version must be 1")
    require(data.get("source_path") == source_path, "source profile path does not match its pointer")
    require(isinstance(data.get("profile_id"), str) and bool(data["profile_id"]), "profile_id is missing")
    require(profile_id is None or data["profile_id"] == profile_id, "source profile id does not match")
    require(isinstance(data.get("source_head"), str)
            and re.fullmatch(r"[0-9a-f]{40}", data["source_head"]), "source_head must be a full git SHA")
    require(data.get("evidence_class") == EVIDENCE_CLASS, "source review evidence class is required")
    order = data.get("stage_order")
    require(strings(order) and bool(order) and len(order) == len(set(order)), "stage_order is invalid")
    boundary = data.get("boundary")
    require(isinstance(boundary, dict) and boundary.get("new_host_acceptance_verified") is False,
            "source review cannot assert new-host acceptance")
    entries = data.get("entries")
    require(isinstance(entries, list) and bool(entries), "entries must be a nonempty array")
    names = set()
    for row in entries:
        require(isinstance(row, dict) and ENTRY_FIELDS.issubset(row), "entry fields are incomplete")
        name = row["name"]
        require(isinstance(name, str) and bool(name.strip()) and name not in names,
                "each named tool or control must have exactly one owner")
        names.add(name)
        if row.get("version_policy") is not None:
            require(row["version_policy"] == VERSION_FLOOR_RULE, "entry must use the shared version floor rule")
        if row.get("component_id") in NATIVE_UPDATE_CLIENTS or row.get("native_update") is not None:
            validate_native_update(row, row.get("native_update"))
        text = json.dumps(row)
        if "floor" in text:
            require(not re.search(r"\b(?:does|do) not qualify\b", text),
                    "entry contradicts the version floor rule")
        require(isinstance(row["layer_id"], str) and bool(row["layer_id"])
                and row["layer_id"] == row["owner_layer_id"], "entry has conflicting owners")
        require(row["status"] in {"picked", "head-to-head-arm"}, "entry status is invalid")
        require(row["stage"] in order and type(row["position"]) is int and row["position"] > 0,
                "entry stage or position is invalid")
        require(strings(row["blocking_gaps"]) and strings(row["evidence_refs"]), "entry references are invalid")
        require(isinstance(row["provisioning_status"], str) and bool(row["provisioning_status"]),
                "provisioning_status is missing")
        require(type(row.get("default_install")) is bool, "default_install must be explicit")
        if row["status"] == "head-to-head-arm":
            require(row["default_install"] is False and row.get("default_precedence") is None,
                    "comparison arms have no default installation or precedence")
        require(row["repository"] is None or https_url(row["repository"]), "repository URL is invalid")
        require(row["pin"] is None or isinstance(row["pin"], str) and bool(row["pin"]), "pin is invalid")
        missing = row["repository"] is None or row["pin"] is None
        checksum = row["checksum"]
        require(isinstance(checksum, dict)
                and {"algorithm", "value", "source", "kind"}.issubset(checksum), "checksum fields are incomplete")
        missing |= any(checksum[key] is None for key in ("algorithm", "value", "source", "kind"))
        if not any(checksum[key] is None for key in ("algorithm", "value", "source", "kind")):
            size = {"sha256": 64, "sha512": 128, "git-sha1": 40}.get(checksum["algorithm"])
            require(size is not None and isinstance(checksum["value"], str)
                    and re.fullmatch(r"[0-9a-f]{%d}" % size, checksum["value"]), "checksum is invalid")
            require(checksum["kind"] in {"artifact", "lock", "source"}, "checksum kind is invalid")
        for key in ("install", "acceptance"):
            step = row[key]
            require(isinstance(step, dict) and {"command", "source"}.issubset(step), key + " fields are incomplete")
            for field in ("command", "source"):
                require(step[field] is None or isinstance(step[field], str) and bool(step[field].strip()),
                        key + " contains an invalid field")
                missing |= step[field] is None
        acceptance = row["acceptance"]
        require("evidence_class" in acceptance, "acceptance evidence class is missing")
        require(acceptance["evidence_class"] is None or acceptance["evidence_class"] in ACCEPTANCE_CLASSES,
                "acceptance must remain a documented, unexecuted example or test")
        missing |= acceptance["evidence_class"] is None
        require(not acceptance["command"] or not re.search(r"(^|\s)--(version|help)(\s|$)", acceptance["command"]),
                "version/help checks do not qualify as acceptance")
        require(not missing or bool(row["blocking_gaps"]), "missing evidence requires a blocking gap")
    validate_host_prerequisites(data.get("host_prerequisites"))
    return data


def validate_default_installs(data, slots):
    """A split or measurement slot has no install decision until it is resolved."""
    for slot in slots:
        if slot.get("state") in {"split", "measurement"}:
            for row in data.get("entries", []):
                if (row["layer_id"] == slot["layer_id"]
                        and (row.get("comparison_group") or row["status"] == "head-to-head-arm")):
                    require(not row.get("default_install"),
                            f"{row['name']}: default installation awaits the measurement for {slot['slot_id']}")


def load_profile(root: Path, source_path=SOURCE_PATH, profile_id=None):
    """Generator adapter: read only the pointed-to, repository-confined contract."""
    root = root.resolve()
    path = recipe_path(root, source_path)
    require(path.is_file(), "source profile is unavailable")
    require(path.stat().st_size <= 1_048_576, "source profile exceeds the one MiB limit")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    validate_profile(data, source_path, profile_id)
    manifest = recipe_path(root, DEFAULTS_MANIFEST)
    if manifest.is_file():
        require(manifest.stat().st_size <= 1_048_576, "defaults manifest exceeds the one MiB limit")
        defaults = json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
        require(isinstance(defaults, dict) and isinstance(defaults.get("slots"), list),
                "defaults manifest needs a slot inventory")
        validate_default_installs(data, defaults["slots"])
    return data


def summarize(data):
    entries = data["entries"]
    gaps = [row for row in entries if row["blocking_gaps"]]
    return {"path": data["source_path"], "profile_id": data["profile_id"], "source_head": data["source_head"],
            "evidence_class": data["evidence_class"], "entries": len(entries),
            "entries_with_blocking_gaps": len(gaps), "status": "source_review_incomplete" if gaps else "source_review",
            "default_install": [row["name"] for row in entries if row["default_install"]],
            "new_host_acceptance_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="Return the full source contract for a generator")
    args = parser.parse_args(argv)
    try:
        data = load_profile(args.root)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        message = str(error) if isinstance(error, InvalidManifest) else "source profile is not valid readable JSON"
        print(message, file=sys.stderr)
        return 2
    print(json.dumps(data if args.json else summarize(data), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
