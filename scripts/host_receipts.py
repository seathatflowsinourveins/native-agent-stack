#!/usr/bin/env python3
"""Record, validate, review and summarize per-host evidence acceptance receipts.

One receipt is one component x one host x one lifecycle stage
(``adoption/host-receipt.schema.json``). This CLI never uploads anything: it
only runs locally supplied commands, writes JSON under ``evidence/hosts/``,
and registers those files in ``manifests/evidence.json``. See
``docs/contributing-evidence.md`` for the full contribution flow.

The ``validate`` rules below are implemented directly in stdlib Python (no
external JSON Schema library) and are kept in sync with
``adoption/host-receipt.schema.json`` by ``tests/test_host_receipts.py``,
which compares this module's required-key and enum constants against the
schema file.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from .validate import PRIVATE_CONTENT
    from .catalog_decisions import InvalidDecisionIndex, safe_file, unique_json
except ImportError:  # running as a plain script, not a package
    from validate import PRIVATE_CONTENT
    from catalog_decisions import InvalidDecisionIndex, safe_file, unique_json


SCHEMA_RELATIVE_PATH = "adoption/host-receipt.schema.json"
STAGES = {"install", "use", "restart", "recovery", "persistence", "cleanup"}
RESULTS = {"pass", "fail", "partial", "not_runnable"}
EVIDENCE_CLASSES = {"native_proven", "local_integration", "synthetic"}
REVIEW_KINDS = {"self", "independent_session", "codex_lane", "human"}
REVIEW_VERDICTS = {"agree", "disagree", "needs_changes"}

HOST_ID_PATTERN = re.compile(r"^[a-z0-9-]+-[0-9]{8}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ISO_UTC_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
ID_PATTERN = re.compile(
    r"^[a-z0-9-]+-[0-9]{8}--[A-Za-z0-9][A-Za-z0-9._/-]*--"
    r"(install|use|restart|recovery|persistence|cleanup)--[0-9]{8}$"
)

TOP_LEVEL_REQUIRED = [
    "schema_version", "id", "kind", "host", "catalog_revision", "component_id",
    "stage", "commands", "tool_versions", "observed_at_utc", "result", "claim",
    "limitations", "evidence_class", "reviews",
]
HOST_REQUIRED = ["host_id", "platform_id", "os", "architecture", "second_physical_machine"]
COMMAND_REQUIRED = ["cmd", "exit", "duration_s", "output_sha256", "output_excerpt"]
REVIEW_REQUIRED = ["kind", "ref", "verdict", "at_utc"]

DEFAULT_TIMEOUT_S = 120
MAX_EXCERPT_CHARS = 400


class InvalidHostReceipt(ValueError):
    """One or more host-receipt validation failures; messages avoid echoing secrets."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    return Path(__file__).resolve().parents[1]


def load_json(root: Path, relative: str) -> dict:
    path = safe_file(root, relative)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=5, check=False,
    )
    revision = result.stdout.strip()
    if result.returncode != 0 or not SHA_PATTERN.fullmatch(revision):
        raise InvalidHostReceipt("could not resolve a 40-hex catalog_revision from git rev-parse HEAD")
    return revision


def sanitize(text: str) -> str:
    """Replace $HOME with ~ and the current username with <user>; never raises."""
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    try:
        user = os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser()
    except Exception:
        user = None
    if user:
        text = re.sub(re.escape(user), "<user>", text)
    for _description, pattern in PRIVATE_CONTENT:
        text = pattern.sub("[redacted]", text)
    return text


def stack_component_ids(root: Path) -> set[str]:
    try:
        stack = load_json(root, "manifests/stack.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return set()
    return {component.get("id") for component in stack.get("components", []) if isinstance(component, dict)}


def stack_component_version(root: Path, component_id: str) -> str | None:
    try:
        stack = load_json(root, "manifests/stack.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return None
    for component in stack.get("components", []):
        if isinstance(component, dict) and component.get("id") == component_id:
            version = component.get("version")
            return version if isinstance(version, str) else None
    return None


def stack_component_string_commands(root: Path, component_id: str) -> list[str]:
    try:
        stack = load_json(root, "manifests/stack.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return []
    for component in stack.get("components", []):
        if isinstance(component, dict) and component.get("id") == component_id:
            return [item for item in component.get("commands", []) if isinstance(item, str)]
    return []


def landscape_component_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    landscape_dir = root / "catalogs" / "landscape"
    if not landscape_dir.is_dir():
        return ids
    for path in sorted(landscape_dir.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        for layer in document.get("layers", []) if isinstance(document, dict) else []:
            if not isinstance(layer, dict):
                continue
            for winner in layer.get("winners", []):
                if isinstance(winner, dict) and isinstance(winner.get("component_id"), str):
                    ids.add(winner["component_id"])
    return ids


def platform_ids(root: Path) -> set[str]:
    try:
        manifest = load_json(root, "adoption/manifest.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return set()
    return {
        profile.get("id")
        for profile in manifest.get("platform_profiles", [])
        if isinstance(profile, dict)
    }


def evidence_files(root: Path) -> dict[str, dict]:
    try:
        evidence = load_json(root, "manifests/evidence.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return {}
    result = {}
    for record in evidence.get("files", []):
        if isinstance(record, dict) and isinstance(record.get("path"), str):
            result[record["path"]] = record
    return result


def register_file(root: Path, relative_path: str) -> None:
    """Append or update relative_path in manifests/evidence.json files[] with its current hash."""
    evidence_path = safe_file(root, "manifests/evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    target = safe_file(root, relative_path)
    raw = target.read_bytes()
    record = {"path": relative_path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    files = evidence.setdefault("files", [])
    for index, existing in enumerate(files):
        if isinstance(existing, dict) and existing.get("path") == relative_path:
            files[index] = record
            break
    else:
        files.append(record)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- record


def run_command(cmd: str, cwd: Path, timeout: int) -> tuple[int, str, float]:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        exit_code = completed.returncode
        output = (completed.stdout or "") + (completed.stderr or "")
    except subprocess.TimeoutExpired as error:
        exit_code = 124
        output = ((error.stdout or "") if isinstance(error.stdout, str) else "") + \
                  ((error.stderr or "") if isinstance(error.stderr, str) else "") + \
                  f"\n[host_receipts: command timed out after {timeout}s]"
    duration = time.monotonic() - start
    return exit_code, output, duration


def cmd_record(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    host_id = args.host_id
    if not HOST_ID_PATTERN.fullmatch(host_id):
        print(f"error: --host-id {host_id!r} must match ^[a-z0-9-]+-[0-9]{{8}}$")
        return 2
    if args.stage not in STAGES:
        print(f"error: --stage must be one of {sorted(STAGES)}")
        return 2
    if args.evidence_class not in EVIDENCE_CLASSES:
        print(f"error: --evidence-class must be one of {sorted(EVIDENCE_CLASSES)}")
        return 2

    known_platforms = platform_ids(root)
    if known_platforms and args.platform_id not in known_platforms:
        print(f"error: --platform-id {args.platform_id!r} is not a known adoption/manifest.json platform_profiles id")
        return 2

    commands_to_run: list[str] = []
    if args.from_stack_commands:
        stack_commands = stack_component_string_commands(root, args.component_id)
        if not stack_commands:
            print(f"error: no plain-string commands found for component {args.component_id!r} in manifests/stack.json")
            return 2
        commands_to_run.extend(stack_commands)
    commands_to_run.extend(args.cmd or [])
    if not commands_to_run:
        print("error: no commands provided; pass --cmd and/or --from-stack-commands")
        return 2

    catalog_revision = git_head(root)
    observed_at = utc_now()
    date_stamp = observed_at[:10].replace("-", "")

    command_records = []
    for cmd in commands_to_run:
        exit_code, output, duration = run_command(cmd, cwd=root, timeout=args.timeout)
        sanitized = sanitize(output)
        command_records.append({
            "cmd": cmd,
            "exit": exit_code,
            "duration_s": round(duration, 3),
            "output_sha256": hashlib.sha256(output.encode("utf-8", "surrogateescape")).hexdigest(),
            "output_excerpt": sanitized[:MAX_EXCERPT_CHARS],
        })

    result = "pass" if all(record["exit"] == 0 for record in command_records) else "fail"

    receipt_id = f"{host_id}--{args.component_id}--{args.stage}--{date_stamp}"
    limitations = args.limitation or [
        "Recorded receipt covers only the listed commands; it does not establish full "
        "component functional acceptance beyond what these commands exercise.",
    ]
    claim = args.claim or (
        f"On host {host_id} ({args.platform_id}), {len(command_records)} command(s) were run for "
        f"component {args.component_id!r} at stage {args.stage!r}; overall result {result}."
    )
    tool_versions = {}
    declared_version = stack_component_version(root, args.component_id)
    if declared_version:
        tool_versions[args.component_id] = declared_version

    receipt = {
        "schema_version": 1,
        "id": receipt_id,
        "kind": "host_acceptance",
        "host": {
            "host_id": host_id,
            "platform_id": args.platform_id,
            "os": args.os or _default_os(),
            "architecture": args.architecture or _default_architecture(),
            "second_physical_machine": bool(args.second_physical_machine),
        },
        "catalog_revision": catalog_revision,
        "component_id": args.component_id,
        "stage": args.stage,
        "commands": command_records,
        "tool_versions": tool_versions,
        "observed_at_utc": observed_at,
        "result": result,
        "claim": claim,
        "limitations": limitations,
        "evidence_class": args.evidence_class,
        "reviews": [
            {"kind": "self", "ref": "scripts/host_receipts.py record", "verdict": "agree", "at_utc": observed_at},
        ],
    }
    if args.hardware_profile_ref:
        receipt["host"]["hardware_profile_ref"] = args.hardware_profile_ref

    relative_path = f"evidence/hosts/{host_id}/{receipt_id}.json"
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    register_file(root, relative_path)
    print(relative_path)
    return 0


def _default_os() -> str:
    import platform as _platform
    return _platform.system().lower()


def _default_architecture() -> str:
    import platform as _platform
    return _platform.machine().lower()


# ------------------------------------------------------------------------- review


def cmd_review(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    receipt_file = Path(args.receipt)
    if not receipt_file.is_absolute():
        receipt_file = root / receipt_file
    try:
        relative_path = receipt_file.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        print("error: --receipt must be inside the repository root")
        return 2
    path = safe_file(root, relative_path)
    receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    if args.kind not in REVIEW_KINDS:
        print(f"error: --kind must be one of {sorted(REVIEW_KINDS)}")
        return 2
    if args.verdict not in REVIEW_VERDICTS:
        print(f"error: --verdict must be one of {sorted(REVIEW_VERDICTS)}")
        return 2
    receipt.setdefault("reviews", []).append({
        "kind": args.kind, "ref": args.ref, "verdict": args.verdict, "at_utc": utc_now(),
    })
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    register_file(root, relative_path)
    print(relative_path)
    return 0


# ----------------------------------------------------------------------- validate


def _iter_receipt_files(root: Path):
    hosts_dir = root / "evidence" / "hosts"
    if not hosts_dir.is_dir():
        return
    for host_dir in sorted(hosts_dir.iterdir()):
        if not host_dir.is_dir():
            continue
        for path in sorted(host_dir.glob("*.json")):
            yield host_dir.name, path


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_receipt_shape(receipt, label: str, errors: list[str]) -> None:
    if not isinstance(receipt, dict):
        errors.append(f"{label}: expected a JSON object")
        return
    for key in TOP_LEVEL_REQUIRED:
        _require(key in receipt, errors, f"{label}: missing required key {key!r}")
    _require(receipt.get("schema_version") == 1, errors, f"{label}: schema_version must be 1")
    _require(receipt.get("kind") == "host_acceptance", errors, f"{label}: kind must be 'host_acceptance'")
    _require(isinstance(receipt.get("id"), str) and bool(ID_PATTERN.fullmatch(receipt["id"])), errors,
              f"{label}: id must match <host_id>--<component_id>--<stage>--<yyyymmdd>")

    host = receipt.get("host")
    if isinstance(host, dict):
        for key in HOST_REQUIRED:
            _require(key in host, errors, f"{label}.host: missing required key {key!r}")
        _require(isinstance(host.get("host_id"), str) and bool(HOST_ID_PATTERN.fullmatch(host["host_id"])),
                  errors, f"{label}.host.host_id: must match ^[a-z0-9-]+-[0-9]{{8}}$")
        _require(isinstance(host.get("second_physical_machine"), bool), errors,
                  f"{label}.host.second_physical_machine: must be boolean")
    else:
        errors.append(f"{label}.host: expected a JSON object")

    _require(isinstance(receipt.get("catalog_revision"), str) and bool(SHA_PATTERN.fullmatch(receipt["catalog_revision"])),
              errors, f"{label}.catalog_revision: must be a 40-hex commit SHA")
    _require(isinstance(receipt.get("component_id"), str) and bool(receipt["component_id"]), errors,
              f"{label}.component_id: must be nonempty text")
    _require(receipt.get("stage") in STAGES, errors, f"{label}.stage: must be one of {sorted(STAGES)}")

    commands = receipt.get("commands")
    if isinstance(commands, list) and commands:
        for index, command in enumerate(commands):
            command_label = f"{label}.commands[{index}]"
            if not isinstance(command, dict):
                errors.append(f"{command_label}: expected a JSON object")
                continue
            for key in COMMAND_REQUIRED:
                _require(key in command, errors, f"{command_label}: missing required key {key!r}")
            _require(isinstance(command.get("exit"), int) and not isinstance(command.get("exit"), bool),
                      errors, f"{command_label}.exit: must be an integer")
            _require(isinstance(command.get("output_sha256"), str) and bool(SHA256_PATTERN.fullmatch(command["output_sha256"])),
                      errors, f"{command_label}.output_sha256: must be 64-hex")
            excerpt = command.get("output_excerpt")
            _require(isinstance(excerpt, str) and len(excerpt) <= MAX_EXCERPT_CHARS, errors,
                      f"{command_label}.output_excerpt: must be text of at most {MAX_EXCERPT_CHARS} characters")
    else:
        errors.append(f"{label}.commands: must be a nonempty array")

    _require(isinstance(receipt.get("tool_versions"), dict), errors, f"{label}.tool_versions: must be an object")
    _require(isinstance(receipt.get("observed_at_utc"), str) and bool(ISO_UTC_PATTERN.fullmatch(receipt["observed_at_utc"])),
              errors, f"{label}.observed_at_utc: must be an ISO-8601 UTC timestamp")
    _require(receipt.get("result") in RESULTS, errors, f"{label}.result: must be one of {sorted(RESULTS)}")
    _require(isinstance(receipt.get("claim"), str) and bool(receipt["claim"]), errors, f"{label}.claim: must be nonempty text")

    limitations = receipt.get("limitations")
    _require(isinstance(limitations, list) and bool(limitations)
              and all(isinstance(item, str) and item for item in limitations), errors,
              f"{label}.limitations: must be a nonempty array of nonempty strings")

    _require(receipt.get("evidence_class") in EVIDENCE_CLASSES, errors,
              f"{label}.evidence_class: must be one of {sorted(EVIDENCE_CLASSES)}")

    reviews = receipt.get("reviews")
    if isinstance(reviews, list) and reviews:
        for index, review in enumerate(reviews):
            review_label = f"{label}.reviews[{index}]"
            if not isinstance(review, dict):
                errors.append(f"{review_label}: expected a JSON object")
                continue
            for key in REVIEW_REQUIRED:
                _require(key in review, errors, f"{review_label}: missing required key {key!r}")
            _require(review.get("kind") in REVIEW_KINDS, errors, f"{review_label}.kind: must be one of {sorted(REVIEW_KINDS)}")
            _require(review.get("verdict") in REVIEW_VERDICTS, errors,
                      f"{review_label}.verdict: must be one of {sorted(REVIEW_VERDICTS)}")
    else:
        errors.append(f"{label}.reviews: must be a nonempty array")

    for layer_ref in receipt.get("layer_refs", []) if isinstance(receipt.get("layer_refs"), list) else []:
        if not isinstance(layer_ref, dict) or not layer_ref.get("catalog") or not layer_ref.get("layer_id"):
            errors.append(f"{label}.layer_refs: each entry needs nonempty 'catalog' and 'layer_id'")


def validate_receipt_cross_references(root: Path, host_dir_name: str, path: Path, receipt: dict,
                                       errors: list[str], known_platforms: set[str],
                                       known_stack_ids: set[str], known_landscape_ids: set[str],
                                       known_files: dict[str, dict]) -> None:
    label = path.relative_to(root).as_posix()
    if not isinstance(receipt, dict):
        return

    host = receipt.get("host") if isinstance(receipt.get("host"), dict) else {}
    platform_id = host.get("platform_id")
    if known_platforms and platform_id not in known_platforms:
        errors.append(f"{label}: host.platform_id {platform_id!r} is not a known adoption/manifest.json platform_profiles id")

    component_id = receipt.get("component_id")
    if (known_stack_ids or known_landscape_ids) and component_id not in known_stack_ids and component_id not in known_landscape_ids:
        errors.append(f"{label}: component_id {component_id!r} is not a known manifests/stack.json or landscape winners component id")

    receipt_id = receipt.get("id", "")
    host_id = host.get("host_id", "")
    _require(host_dir_name == host_id, errors, f"{label}: directory {host_dir_name!r} does not match host.host_id {host_id!r}")
    _require(path.stem == receipt_id, errors, f"{label}: filename {path.stem!r} does not match id {receipt_id!r}")
    if isinstance(receipt_id, str) and ID_PATTERN.fullmatch(receipt_id):
        id_host_id = receipt_id.split("--", 1)[0]
        _require(id_host_id == host_id, errors, f"{label}: id host segment {id_host_id!r} does not match host.host_id {host_id!r}")

    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    result = receipt.get("result")
    if result == "pass":
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                continue
            exit_code = command.get("exit")
            expected = command.get("expected_exit", 0)
            if exit_code != expected:
                errors.append(f"{label}.commands[{index}]: result is 'pass' but exit {exit_code!r} != expected {expected!r}")

    catalog_revision = receipt.get("catalog_revision")
    if isinstance(catalog_revision, str) and SHA_PATTERN.fullmatch(catalog_revision):
        try:
            check = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(root), "cat-file", "-e", f"{catalog_revision}^{{commit}}"],
                capture_output=True, timeout=5, check=False,
            )
            if check.returncode not in (0, 1):
                pass  # git unavailable/unexpected error; skip this bonus check rather than fail spuriously
            elif check.returncode == 1:
                errors.append(f"{label}: catalog_revision {catalog_revision} is not a commit present in this checkout")
        except (OSError, subprocess.TimeoutExpired):
            pass

    relative_receipt_path = path.relative_to(root).as_posix()
    registered = known_files.get(relative_receipt_path)
    if registered is None:
        errors.append(f"{label}: receipt is not registered in manifests/evidence.json files[]")
    else:
        raw = path.read_bytes()
        actual_sha256 = hashlib.sha256(raw).hexdigest()
        if registered.get("sha256") != actual_sha256:
            errors.append(f"{label}: manifests/evidence.json files[] sha256 does not match the receipt bytes")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeError:
        content = path.read_bytes().decode("latin-1")
    for description, pattern in PRIVATE_CONTENT:
        if pattern.search(content):
            errors.append(f"{label}: contains possible {description}")


def cmd_validate(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    known_platforms = platform_ids(root)
    known_stack_ids = stack_component_ids(root)
    known_landscape_ids = landscape_component_ids(root)
    known_files = evidence_files(root)

    errors: list[str] = []
    count = 0
    for host_dir_name, path in _iter_receipt_files(root):
        count += 1
        label = path.relative_to(root).as_posix()
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
        except (OSError, UnicodeError, ValueError, InvalidDecisionIndex) as error:
            errors.append(f"{label}: invalid JSON ({type(error).__name__})")
            continue
        validate_receipt_shape(receipt, label, errors)
        validate_receipt_cross_references(
            root, host_dir_name, path, receipt, errors,
            known_platforms, known_stack_ids, known_landscape_ids, known_files,
        )

    if errors:
        print(f"Host receipt validation failed ({len(errors)} error(s) across {count} receipt(s)):")
        for error in errors:
            print(f"- {error}")
        return 1
    print(json.dumps({"status": "passed", "receipts": count}, sort_keys=True))
    return 0


# ------------------------------------------------------------------------ summary


def build_summary(root: Path) -> dict:
    """Aggregate every recorded host receipt by component x platform.

    Each platform bucket additionally reports
    ``independently_reviewed_native_proven_pass_stages``: the sorted list of
    lifecycle stages with at least one receipt that is ``result: pass``,
    ``evidence_class: native_proven`` and carries a non-``self`` review with
    verdict ``agree``. Callers needing that stricter combination (for example
    ``scripts/component_matrix.py``'s macOS-acceptance flip rule) can check
    that list directly instead of re-deriving it from raw receipts.
    """
    components: dict[str, dict] = {}
    for _host_dir_name, path in _iter_receipt_files(root):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
        except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
            continue
        component_id = receipt.get("component_id")
        platform_id = (receipt.get("host") or {}).get("platform_id")
        stage = receipt.get("stage")
        result = receipt.get("result")
        evidence_class = receipt.get("evidence_class")
        observed_at = receipt.get("observed_at_utc")
        if not isinstance(component_id, str) or not isinstance(platform_id, str):
            continue
        component_bucket = components.setdefault(component_id, {"platforms": {}})
        platform_bucket = component_bucket["platforms"].setdefault(
            platform_id, {
                "stages": {}, "latest_observed_at_utc": None, "independently_reviewed_passes": 0,
                "independently_reviewed_native_proven_pass_stages": set(),
            },
        )
        stage_counts = platform_bucket["stages"].setdefault(
            stage, {"pass": 0, "fail": 0, "partial": 0, "not_runnable": 0},
        )
        if result in stage_counts:
            stage_counts[result] += 1
        if isinstance(observed_at, str):
            current_latest = platform_bucket["latest_observed_at_utc"]
            if current_latest is None or observed_at > current_latest:
                platform_bucket["latest_observed_at_utc"] = observed_at
        reviews = receipt.get("reviews") if isinstance(receipt.get("reviews"), list) else []
        independently_reviewed = any(
            isinstance(review, dict) and review.get("kind") != "self" and review.get("verdict") == "agree"
            for review in reviews
        )
        if result == "pass" and independently_reviewed:
            platform_bucket["independently_reviewed_passes"] += 1
            if evidence_class == "native_proven" and isinstance(stage, str):
                platform_bucket["independently_reviewed_native_proven_pass_stages"].add(stage)

    for component_bucket in components.values():
        for platform_bucket in component_bucket["platforms"].values():
            platform_bucket["independently_reviewed_native_proven_pass_stages"] = sorted(
                platform_bucket["independently_reviewed_native_proven_pass_stages"]
            )

    return {"generated_at_utc": utc_now(), "components": components}


def cmd_summary(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    summary = build_summary(root)
    components = summary["components"]
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for component_id in sorted(components):
            for platform_id in sorted(components[component_id]["platforms"]):
                bucket = components[component_id]["platforms"][platform_id]
                stage_text = ", ".join(
                    f"{stage}={counts}" for stage, counts in sorted(bucket["stages"].items())
                )
                print(f"{component_id} @ {platform_id}: {stage_text} "
                      f"(latest={bucket['latest_observed_at_utc']}, "
                      f"independently_reviewed_passes={bucket['independently_reviewed_passes']})")
    return 0


# --------------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate every recorded host receipt")
    validate_parser.add_argument("--root", type=Path, default=None)
    validate_parser.set_defaults(func=cmd_validate)

    record_parser = subparsers.add_parser("record", help="Run commands and record a new host receipt")
    record_parser.add_argument("--root", type=Path, default=None)
    record_parser.add_argument("--host-id", required=True)
    record_parser.add_argument("--platform-id", required=True)
    record_parser.add_argument("--component-id", required=True)
    record_parser.add_argument("--stage", required=True, choices=sorted(STAGES))
    record_parser.add_argument("--hardware-profile-ref", default=None)
    record_parser.add_argument("--second-physical-machine", action="store_true")
    record_parser.add_argument("--cmd", action="append", default=[])
    record_parser.add_argument("--from-stack-commands", action="store_true")
    record_parser.add_argument("--claim", default=None)
    record_parser.add_argument("--limitation", action="append", default=[])
    record_parser.add_argument("--evidence-class", required=True, choices=sorted(EVIDENCE_CLASSES))
    record_parser.add_argument("--os", default=None)
    record_parser.add_argument("--architecture", default=None)
    record_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    record_parser.set_defaults(func=cmd_record)

    review_parser = subparsers.add_parser("review", help="Append an independent review to an existing receipt")
    review_parser.add_argument("--root", type=Path, default=None)
    review_parser.add_argument("--receipt", required=True)
    review_parser.add_argument("--kind", required=True, choices=sorted(REVIEW_KINDS))
    review_parser.add_argument("--ref", required=True)
    review_parser.add_argument("--verdict", required=True, choices=sorted(REVIEW_VERDICTS))
    review_parser.set_defaults(func=cmd_review)

    summary_parser = subparsers.add_parser("summary", help="Summarize recorded host receipts")
    summary_parser.add_argument("--root", type=Path, default=None)
    summary_parser.add_argument("--json", action="store_true")
    summary_parser.set_defaults(func=cmd_summary)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
