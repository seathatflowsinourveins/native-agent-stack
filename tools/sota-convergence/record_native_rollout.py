#!/usr/bin/env python3
"""Validate native-rollout receipts and, only when one qualifies, update a landscape
winner's pin/evidence_class/evidence_refs/platform_status.

Implements tools/sota-convergence/native-rollout-receipt.schema.json directly in
stdlib Python (no external JSON Schema library), the same convention as
adoption/host-receipt.schema.json's sibling scripts/host_receipts.py; kept in sync
with the schema file by tests/test_record_native_rollout.py.

This script never runs a command, contacts a network or reads a credential value:
it only reads a receipt file already written by whatever process actually did the
rollout, checks it, and (only with --write, and only when the receipt qualifies)
edits one already-selected catalogs/landscape/<catalog>.json winner in place.

Qualification for evidence_class "native_proven" (switch.md): tiers T2 (a real
workload, not a --version/--help probe) and T4 both "passed", and T5 "passed", and
-- when the target is a live service, not a bare CLI -- T6 also "passed". A
receipt's own evidence_class_claimed is never trusted directly; this script derives
the qualifying class itself from the tiers and refuses to write a stronger claim
than the tiers actually support.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# scripts/platform_status.py owns the one platform-status derivation rule scripts/landscape.py
# enforces as a ceiling (macos-arm64 always, linux-wsl2-x86_64 on a non-grandfathered row): a
# native-rollout receipt alone is not the host-receipt evidence that module actually requires,
# so record() below derives through it rather than assuming "accepted" from this receipt's own
# qualifying tiers, the same way tools/sota-convergence/record_verdicts.py's own
# platform_status_for helper does for the layer-verdict pipeline.
from scripts.platform_status import PLATFORMS, load_context  # noqa: E402
from scripts.platform_status import platform_status as derive_platform_status  # noqa: E402

# Same rule, same excluded set (df -h/du -h are functional, so -h is deliberately not here), as
# scripts/host_receipts.py's BARE_HELP_OR_VERSION: a T2 tier made only of `<program> <flag>`
# probes is not "a real workload" (switch.md), whatever its pass/fail result.
BARE_HELP_OR_VERSION = frozenset({"--help", "--version", "-V", "help", "version"})

SCHEMA_VERSION = 1
TIERS = ("T0", "T1", "T2", "T3", "T4", "T5", "T6")
RESULTS = {"passed", "failed", "unavailable"}
STATUSES = {"passed", "failed", "partial"}
INSTALL_CLASSES = {"tarball", "npm", "pip", "uv-tool", "native"}
DECISIONS = {"retain", "adjust", "keep_but_compare"}
EVIDENCE_CLASSES = {"native_proven", "local_integration", "synthetic", "source_review", "measured_comparison"}
SIGNATURE_KINDS = {"slsa_provenance", "gpg", "sigstore", "none"}
AGREEMENTS = {"same_result", "different_result", "not_rerun"}

SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
HOST_ID = re.compile(r"^[a-z0-9-]+-[0-9]{8}$")
ISO_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
STACK_HOME_PLACEHOLDER = "${STACK_HOME}"

# T2 (a real workload) and T4 (independent agreement) gate qualification for every
# component; T5 as well; T6 only when the rollout also touched a live service.
QUALIFYING_TIERS = ("T2", "T4", "T5")
SERVICE_QUALIFYING_TIER = "T6"


class ReceiptError(ValueError):
    """A receipt fails schema/business validation; carries every collected reason."""


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def _is_str(value) -> bool:
    return isinstance(value, str) and bool(value)


def _no_extra_keys(document, allowed: frozenset[str], errors: list[str], label: str) -> None:
    """Minor finding: the schema declares ``additionalProperties: false`` on every object below
    (top-level and every nested one), but this hand-written validator never enforced it, so a
    receipt with an extra (typo'd, or worse, disclosive) key still validated. Silently no-ops on
    a non-dict ``document``: the caller already records its own "must be an object" error."""
    if not isinstance(document, dict):
        return
    extra = sorted(set(document) - allowed)
    if extra:
        errors.append(f"{label}: unexpected field(s) {extra} (additionalProperties: false)")


CWD_PATTERN = re.compile(r"\$\{STACK_HOME\}|^/tmp|^\.$")


def validate_receipt(document) -> list[str]:
    """Every reason ``document`` does not satisfy native-rollout-receipt.schema.json;
    empty means valid. Never raises; always returns a list."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["receipt must be a JSON object"]
    _no_extra_keys(document, frozenset({
        "schema_version", "id", "kind", "status", "identity", "upstream", "install", "tiers",
        "independent", "switch", "decision", "evidence_class_claimed", "limitations",
        "retained_native_failures",
    }), errors, "receipt")

    _require(document.get("schema_version") == SCHEMA_VERSION and not isinstance(document.get("schema_version"), bool),
              errors, "schema_version must be 1")
    _require(_is_str(document.get("id")), errors, "id must be nonempty text")
    _require(document.get("kind") == "native_rollout", errors, 'kind must be "native_rollout"')
    _require(document.get("status") in STATUSES, errors, f"status must be one of {sorted(STATUSES)}")

    identity = document.get("identity")
    if not isinstance(identity, dict):
        errors.append("identity must be an object")
    else:
        _no_extra_keys(identity, frozenset({"component_id", "version", "host_id"}), errors, "identity")
        _require(_is_str(identity.get("component_id")), errors, "identity.component_id must be nonempty text")
        _require(_is_str(identity.get("version")), errors, "identity.version must be nonempty text")
        _require(isinstance(identity.get("host_id"), str) and bool(HOST_ID.fullmatch(identity["host_id"])),
                  errors, "identity.host_id must match <platform-id>-<yyyymmdd>")

    upstream = document.get("upstream")
    if not isinstance(upstream, dict):
        errors.append("upstream must be an object")
    else:
        _no_extra_keys(upstream, frozenset({"repo", "tag", "commit", "artifact_url", "sha256", "signature"}),
                        errors, "upstream")
        _require(_is_str(upstream.get("repo")), errors, "upstream.repo must be nonempty text")
        _require(_is_str(upstream.get("artifact_url")), errors, "upstream.artifact_url must be nonempty text")
        _require(isinstance(upstream.get("sha256"), str) and bool(SHA256.fullmatch(upstream["sha256"])),
                  errors, "upstream.sha256 must be 64 lowercase hex digits")
        has_tag, has_commit = "tag" in upstream, "commit" in upstream
        _require(has_tag or has_commit, errors, "upstream needs tag or commit (at least one)")
        if has_tag:
            # Minor finding: only presence was checked here; the schema also requires a string of
            # at least one character (upstream.tag {type: string, minLength: 1}), so "tag": 5 or
            # "tag": "" used to validate.
            _require(_is_str(upstream.get("tag")), errors, "upstream.tag must be nonempty text")
        if has_commit:
            _require(isinstance(upstream.get("commit"), str) and bool(SHA1.fullmatch(upstream["commit"])),
                      errors, "upstream.commit must be a full 40-hex-digit SHA")
        signature = upstream.get("signature")
        if signature is not None:
            if not isinstance(signature, dict) or signature.get("kind") not in SIGNATURE_KINDS:
                errors.append(f"upstream.signature.kind must be one of {sorted(SIGNATURE_KINDS)}")
            else:
                _no_extra_keys(signature, frozenset({"kind", "ref"}), errors, "upstream.signature")
                if signature["kind"] != "none" and not _is_str(signature.get("ref")):
                    errors.append('upstream.signature.ref is required unless kind is "none"')

    install = document.get("install")
    if not isinstance(install, dict):
        errors.append("install must be an object")
    else:
        _no_extra_keys(install, frozenset({"class", "root", "marker_sha256", "argv", "private_env_names"}),
                        errors, "install")
        _require(install.get("class") in INSTALL_CLASSES, errors, f"install.class must be one of {sorted(INSTALL_CLASSES)}")
        root = install.get("root")
        _require(isinstance(root, str) and STACK_HOME_PLACEHOLDER in root, errors,
                  f"install.root must contain the literal placeholder {STACK_HOME_PLACEHOLDER}, never a real host path")
        _require(isinstance(install.get("marker_sha256"), str) and bool(SHA256.fullmatch(install["marker_sha256"])),
                  errors, "install.marker_sha256 must be 64 lowercase hex digits")
        argv = install.get("argv")
        _require(isinstance(argv, list) and all(isinstance(item, str) for item in argv), errors,
                  "install.argv must be a list of strings")
        names = install.get("private_env_names")
        _require(isinstance(names, list) and all(isinstance(item, str) and ENV_NAME.fullmatch(item) for item in names),
                  errors, "install.private_env_names must be a list of ENV_VAR names, never values")

    tiers = document.get("tiers")
    tier_results: dict[str, str] = {}
    if not isinstance(tiers, list) or not tiers:
        errors.append("tiers must be a nonempty list")
    else:
        seen = set()
        for index, tier in enumerate(tiers):
            label = f"tiers[{index}]"
            if not isinstance(tier, dict):
                errors.append(f"{label} must be an object")
                continue
            _no_extra_keys(tier, frozenset({"tier", "commands", "result", "unavailable_reason"}), errors, label)
            tier_id = tier.get("tier")
            if tier_id not in TIERS:
                errors.append(f"{label}.tier must be one of {TIERS}")
            elif tier_id in seen:
                errors.append(f"tiers: duplicate tier {tier_id}")
            else:
                seen.add(tier_id)
                tier_results[tier_id] = tier.get("result")
            result = tier.get("result")
            _require(result in RESULTS, errors, f"{label}.result must be one of {sorted(RESULTS)}")
            reason = tier.get("unavailable_reason")
            if result == "unavailable":
                _require(_is_str(reason), errors, f"{label}.unavailable_reason is required when result is \"unavailable\"")
            else:
                _require(reason is None, errors, f"{label}.unavailable_reason must be absent unless result is \"unavailable\"")
            commands = tier.get("commands")
            if not isinstance(commands, list):
                errors.append(f"{label}.commands must be a list")
                continue
            if result == "passed" and not commands:
                errors.append(f"{label}.commands must be nonempty when result is \"passed\"")
            for command_index, command in enumerate(commands):
                clabel = f"{label}.commands[{command_index}]"
                if not isinstance(command, dict):
                    errors.append(f"{clabel} must be an object")
                    continue
                _no_extra_keys(command, frozenset({
                    "argv", "cwd", "env_names", "started_utc", "elapsed_s", "exit",
                    "stdout_sha256", "stderr_sha256", "assertion",
                }), errors, clabel)
                _require(isinstance(command.get("argv"), list) and command["argv"]
                          and all(isinstance(item, str) for item in command["argv"]), errors,
                          f"{clabel}.argv must be a nonempty list of strings")
                _require(_is_str(command.get("cwd")) and bool(CWD_PATTERN.search(command["cwd"])), errors,
                          f"{clabel}.cwd must be nonempty text matching {CWD_PATTERN.pattern!r} "
                          "(${STACK_HOME}, /tmp, or exactly '.')")
                env_names = command.get("env_names")
                _require(isinstance(env_names, list) and all(isinstance(item, str) and ENV_NAME.fullmatch(item)
                          for item in env_names), errors, f"{clabel}.env_names must be a list of ENV_VAR names")
                _require(isinstance(command.get("started_utc"), str) and bool(ISO_UTC.fullmatch(command["started_utc"])),
                          errors, f"{clabel}.started_utc must be an ISO UTC timestamp")
                elapsed = command.get("elapsed_s")
                _require(isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and elapsed >= 0,
                          errors, f"{clabel}.elapsed_s must be a nonnegative number")
                _require(isinstance(command.get("exit"), int) and not isinstance(command.get("exit"), bool),
                          errors, f"{clabel}.exit must be an integer")
                _require(isinstance(command.get("stdout_sha256"), str) and bool(SHA256.fullmatch(command["stdout_sha256"])),
                          errors, f"{clabel}.stdout_sha256 must be 64 lowercase hex digits")
                _require(isinstance(command.get("stderr_sha256"), str) and bool(SHA256.fullmatch(command["stderr_sha256"])),
                          errors, f"{clabel}.stderr_sha256 must be 64 lowercase hex digits")
                _require(_is_str(command.get("assertion")), errors, f"{clabel}.assertion must be nonempty text")

    independent = document.get("independent")
    if not isinstance(independent, dict):
        errors.append("independent must be an object")
    else:
        _no_extra_keys(independent, frozenset({"rerun_label", "agreement", "loki"}), errors, "independent")
        _require(_is_str(independent.get("rerun_label")), errors, "independent.rerun_label must be nonempty text")
        _require(independent.get("agreement") in AGREEMENTS, errors, f"independent.agreement must be one of {sorted(AGREEMENTS)}")
        if "loki" in independent:
            # Minor finding: loki's own items were never type-checked (the schema declares
            # independent.loki as {type: array, items: {type: string}}), so a non-string entry
            # (or a non-list value entirely) used to validate.
            _require(isinstance(independent.get("loki"), list) and all(isinstance(item, str) for item in independent["loki"]),
                      errors, "independent.loki must be a list of strings")

    switch = document.get("switch")
    if switch is not None:
        if not isinstance(switch, dict):
            errors.append("switch must be an object when present")
        else:
            _no_extra_keys(switch, frozenset({"txn", "ledger_seq", "surfaces", "window"}), errors, "switch")
            _require(_is_str(switch.get("txn")), errors, "switch.txn must be nonempty text")
            _require(isinstance(switch.get("ledger_seq"), list)
                      and all(isinstance(item, int) and not isinstance(item, bool) and item >= 1 for item in switch.get("ledger_seq", [])),
                      errors, "switch.ledger_seq must be a list of positive integers")
            # Minor finding: only "is a list" was checked; the schema also requires string items
            # (switch.surfaces {items: {type: string}}), so [1, 2] or [null] used to validate.
            _require(isinstance(switch.get("surfaces"), list) and all(isinstance(item, str) for item in switch.get("surfaces", [])),
                      errors, "switch.surfaces must be a list of strings")
            _require(_is_str(switch.get("window")), errors, "switch.window must be nonempty text")

    _require(document.get("decision") in DECISIONS, errors, f"decision must be one of {sorted(DECISIONS)}")
    _require(document.get("evidence_class_claimed") in EVIDENCE_CLASSES, errors,
              f"evidence_class_claimed must be one of {sorted(EVIDENCE_CLASSES)}")
    limitations = document.get("limitations")
    _require(isinstance(limitations, list) and limitations and all(_is_str(item) for item in limitations),
              errors, "limitations must be a nonempty list of nonempty text")
    failures = document.get("retained_native_failures")
    if not isinstance(failures, list):
        errors.append("retained_native_failures must be a list (may be empty)")
    else:
        for index, failure in enumerate(failures):
            flabel = f"retained_native_failures[{index}]"
            if not (isinstance(failure, dict) and failure.get("tier") in TIERS and _is_str(failure.get("note"))):
                errors.append(f"{flabel} must be an object with tier and note")
                continue
            _no_extra_keys(failure, frozenset({"tier", "note"}), errors, flabel)
    return errors


def tier_results_of(document: dict) -> dict[str, str]:
    return {tier["tier"]: tier.get("result") for tier in document.get("tiers", []) if isinstance(tier, dict)}


def tier_by_id(document: dict, tier_id: str) -> dict | None:
    for tier in document.get("tiers") or []:
        if isinstance(tier, dict) and tier.get("tier") == tier_id:
            return tier
    return None


def is_bare_help_or_version(argv) -> bool:
    """Whether ``argv`` (a receipt command's own argv list) is exactly one program and one help
    or version argument -- the same distinction scripts/host_receipts.py's
    BARE_HELP_OR_VERSION/bare_help_or_version already draws for host receipts, applied here to a
    native-rollout receipt's T2 commands."""
    return isinstance(argv, list) and len(argv) == 2 and argv[1] in BARE_HELP_OR_VERSION


def bare_t2_issue(document: dict) -> str | None:
    """None unless T2's own commands (when it is present and its result is "passed") are *all*
    bare --version/--help probes: switch.md requires T2 to be "a real workload", not a version
    check, so a T2 that never ran more than that must not qualify a rollout regardless of its
    recorded result."""
    t2 = tier_by_id(document, "T2")
    if t2 is None or t2.get("result") != "passed":
        return None
    commands = [c for c in (t2.get("commands") or []) if isinstance(c, dict)]
    if commands and all(is_bare_help_or_version(c.get("argv")) for c in commands):
        return "tier T2 is made only of bare --version/--help probes, not a real workload"
    return None


def qualifying_evidence_class(document: dict, *, service: bool) -> tuple[str | None, str]:
    """(evidence_class, reason). evidence_class is "native_proven" when every
    QUALIFYING_TIERS entry (T2, T4, T5), plus T6 when ``service``, is "passed" in
    ``document``, T2 is not made only of bare --version/--help probes, and
    ``independent.agreement`` is "same_result"; otherwise None and a reason naming the first
    unmet condition. The receipt's own status must also be "passed" -- an unavailable or failed
    overall receipt never qualifies regardless of individual tier results."""
    if document.get("status") != "passed":
        return None, f'receipt status is {document.get("status")!r}, not "passed"'
    results = tier_results_of(document)
    required = QUALIFYING_TIERS + ((SERVICE_QUALIFYING_TIER,) if service else ())
    for tier in required:
        if results.get(tier) != "passed":
            return None, f"tier {tier} is {results.get(tier)!r}, not \"passed\" (required: {', '.join(required)})"
    t2_issue = bare_t2_issue(document)
    if t2_issue:
        return None, t2_issue
    agreement = (document.get("independent") or {}).get("agreement")
    if agreement != "same_result":
        return None, f"independent.agreement is {agreement!r}, not \"same_result\""
    return "native_proven", "every required tier passed"


def find_winner(landscape: dict, catalog: str, layer_id: str, component_id: str):
    for layer in landscape.get("layers") or []:
        if not isinstance(layer, dict) or layer.get("catalog") != catalog or layer.get("layer_id") != layer_id:
            continue
        for winner in layer.get("winners") or []:
            if isinstance(winner, dict) and winner.get("component_id") == component_id:
                return layer, winner
    return None, None


def record(receipt: dict, landscape: dict, *, catalog: str, layer_id: str, receipt_ref: str,
           service: bool, platform: str, status_context=None) -> dict:
    """Report {qualifies, evidence_class, reason, changed[]} of updating the matching
    winner in ``landscape`` (mutated in place only when it qualifies); the caller
    decides whether to write ``landscape`` back to disk.

    A qualifying receipt updates the winner's ``pin`` to the receipt's own version (switch.md
    lists ``pin`` among the fields this tool updates) rather than requiring it to already equal
    the current pin: a receipt is exactly the authorization to move the pin to the version it
    tested, not merely more evidence for a version already pinned. The only identity check that
    gates this is ``component_id`` resolving to a real winner (``find_winner``) plus the tiers
    themselves qualifying (``qualifying_evidence_class``); this tool never runs a command or
    re-executes the receipt's own claims, so those two checks are the whole trust boundary.

    ``platform_status`` is updated only when ``status_context`` (a
    ``scripts.platform_status.StatusContext``, built once per run by the caller from real host
    receipts) is given, and only to what ``scripts.platform_status.platform_status`` itself
    derives for that platform -- never assumed "accepted" from this receipt's own qualifying
    tiers, which is a different, weaker evidence class than the reviewed host receipts that
    function actually requires (macos-arm64 always, and a non-grandfathered linux row). Without
    a status_context (e.g. a direct call in isolation, with no repository evidence available),
    platform_status is left untouched rather than guessed."""
    component_id = (receipt.get("identity") or {}).get("component_id")
    version = (receipt.get("identity") or {}).get("version")
    layer, winner = find_winner(landscape, catalog, layer_id, component_id)
    if winner is None:
        return {"qualifies": False, "evidence_class": None,
                "reason": f"no winner {component_id!r} in {catalog}/{layer_id}", "changed": []}
    evidence_class, reason = qualifying_evidence_class(receipt, service=service)
    if evidence_class is None:
        return {"qualifies": False, "evidence_class": None, "reason": reason, "changed": []}
    changed = []
    if winner.get("pin") != version:
        winner["pin"] = version
        changed.append("pin")
    if winner.get("evidence_class") != evidence_class:
        winner["evidence_class"] = evidence_class
        changed.append("evidence_class")
    refs = winner.setdefault("evidence_refs", [])
    if receipt_ref not in refs:
        refs.append(receipt_ref)
        changed.append("evidence_refs")
    if status_context is not None:
        platform_status = winner.setdefault("platform_status", {})
        derived = derive_platform_status(platform, winner, status_context).status
        if platform_status.get(platform) != derived:
            platform_status[platform] = derived
            changed.append(f"platform_status.{platform}")
    return {"qualifies": True, "evidence_class": evidence_class, "reason": reason, "changed": changed}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_validate(args) -> int:
    document = load_json(args.receipt)
    errors = validate_receipt(document)
    if errors:
        print("Receipt validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    print(json.dumps({"status": "passed", "id": document.get("id")}, sort_keys=True))
    return 0


def cmd_record(args) -> int:
    document = load_json(args.receipt)
    errors = validate_receipt(document)
    if errors:
        print("Refusing to record an invalid receipt:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    landscape = load_json(args.landscape)
    receipt_ref = args.receipt_ref or str(args.receipt)
    status_context = load_context(args.root)
    report = record(document, landscape, catalog=args.catalog, layer_id=args.layer_id,
                    receipt_ref=receipt_ref, service=args.service, platform=args.platform,
                    status_context=status_context)
    if not report["qualifies"]:
        print(json.dumps({"status": "not_qualified", **report}, sort_keys=True))
        return 3
    if args.write:
        # Minor finding: matches record_verdicts.py's own documented serialization
        # (json.dumps(..., ensure_ascii=False) + a trailing newline) -- the default
        # ensure_ascii=True would \u-escape any non-ASCII character already present in a
        # landscape file (e.g. us-equities.json, new-host-grand-list.json) on the very next
        # unrelated field this tool touches, a needless diff-noise regression on every write.
        args.landscape.write_text(json.dumps(landscape, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
        print(f"Reminder: {args.landscape} changed and is likely hash-listed in manifests/evidence.json "
              "(scripts/validate.py); re-pin it (e.g. python3 scripts/evidence_manifest.py and a manual "
              "sha256/bytes update, or the project's own re-pin helper) before that check passes again.",
              file=sys.stderr)
    print(json.dumps({"status": "qualified", "wrote": bool(args.write), **report}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="Check a receipt against native-rollout-receipt.schema.json")
    validate_parser.add_argument("receipt", type=Path)
    validate_parser.set_defaults(handler=cmd_validate)

    record_parser = sub.add_parser("record", help="Validate a receipt, then update a landscape winner if it qualifies")
    record_parser.add_argument("receipt", type=Path)
    record_parser.add_argument("--landscape", required=True, type=Path)
    record_parser.add_argument("--catalog", required=True)
    record_parser.add_argument("--layer-id", required=True)
    record_parser.add_argument("--receipt-ref", help="Path recorded in evidence_refs (default: the receipt's own --receipt path)")
    record_parser.add_argument("--service", action="store_true",
                                help="This component runs as a live service (systemd unit); also require tier T6")
    record_parser.add_argument("--platform", required=True, choices=sorted(PLATFORMS),
                                help="The winner's platform_status key to accept, e.g. linux-wsl2-x86_64 or "
                                     "macos-arm64 (scripts/landscape.py PLATFORM_KEYS); a receipt's host_id is a "
                                     "host nickname (evidence/hosts/<host_id>/), not a platform key, so it is "
                                     "never guessed from it")
    record_parser.add_argument("--root", type=Path, default=REPO_ROOT,
                                help="Repository checkout scripts/platform_status.py reads host receipts and "
                                     "manifests/evidence.json from (default: this script's own checkout, not "
                                     "--landscape's directory, which may be a fixture elsewhere in tests)")
    record_parser.add_argument("--write", action="store_true", help="Write the landscape file back; default is report-only")
    record_parser.set_defaults(handler=cmd_record)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError) as error:
        print(f"record_native_rollout: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
