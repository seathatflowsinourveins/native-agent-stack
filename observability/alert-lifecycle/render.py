#!/usr/bin/env python3
"""Render native F09 config from an authoritative configured unit roster.

Sources: opentelemetry-collector-contrib v0.162.0 receiver/systemdreceiver/
config.go, metadata.yaml, scraper.go; exporter/prometheusexporter/README.md;
processor/filterprocessor and transformprocessor; OTTL metric/datapoint contexts.
Prometheus recording rules: prometheus v3.15.0 native rule-file format.
JSON is native YAML input. This renders config only; it never starts a receiver.
Expected records are configuration, never observed unit state or recovery.
Unit kind, arming and recovery contracts are explicit policy. Reused one-shot
and timer services remain unarmed while completion is unknown; inactive is
not evidence that a job completed successfully. The native receiver supplies
unit active state, not a last-success or timer completion contract.
The DRILL example is synthetic configuration, not W2 qualification. The 15s
collection/scrape and rule-evaluation intervals describe observation metadata,
not a service/job/timer cadence. Native last-success evidence is not provided
by this receiver; cadence and W2 identity remain subject to the CC answer.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
JOB = "ns2604-user-unit-state"
EXPECTED = "ns2604_user_unit_expected"
CLASSES = {"PaperLaneUnitDown", "StackUnitDown"}
SEVERITIES = {"warning", "critical"}
UNIT_KINDS = {"continuous", "oneshot", "timer-service", "drill"}
RECOVERY_CONTRACTS = {"active", "failure-cleared", "unknown"}
UNIT_FIELDS = {"name", "failure_class", "severity", "unit_kind", "armed",
               "recovery_contract", "completion_contract"}
UNIT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,230}\.service\Z")


def validate_policy(value):
    if not isinstance(value, dict) or set(value) != {"host", "listen", "units"}:
        raise ValueError("policy permits only host, listen, units")
    if value["host"] != "NativeStack2604":
        raise ValueError("host must be NativeStack2604")
    listen = value["listen"]
    if not isinstance(listen, str) or not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", listen):
        raise ValueError("listen must be an explicit 127.0.0.1 port")
    if not 1024 <= int(listen.rsplit(":", 1)[1]) <= 65535:
        raise ValueError("listen requires an unprivileged valid TCP port")
    units = value["units"]
    if not isinstance(units, list) or not units:
        raise ValueError("units must be a nonempty configured roster")
    names = set()
    for unit in units:
        if not isinstance(unit, dict) or set(unit) != UNIT_FIELDS:
            raise ValueError("unit requires name, failure_class, severity, unit_kind, armed, "
                             "recovery_contract, completion_contract")
        name = unit["name"]
        if not isinstance(name, str) or not UNIT_NAME.fullmatch(name) or name.endswith("@.service") or name.count("@") > 1:
            raise ValueError("unit requires a concrete safe .service name, no template/glob")
        if name in names:
            raise ValueError("duplicate configured unit")
        names.add(name)
        if not isinstance(unit["failure_class"], str) or not isinstance(unit["severity"], str) or unit["failure_class"] not in CLASSES or unit["severity"] not in SEVERITIES:
            raise ValueError("unsupported failure_class or severity")
        if not isinstance(unit["unit_kind"], str) or unit["unit_kind"] not in UNIT_KINDS:
            raise ValueError("unsupported unit_kind")
        if not isinstance(unit["armed"], bool):
            raise ValueError("armed must be an explicit boolean")
        if not isinstance(unit["recovery_contract"], str) or unit["recovery_contract"] not in RECOVERY_CONTRACTS:
            raise ValueError("unsupported recovery_contract")
        if unit["completion_contract"] != "unknown":
            raise ValueError("completion_contract is unknown until an upstream-backed contract exists")
        if unit["armed"] and unit["recovery_contract"] == "unknown":
            raise ValueError("an unknown recovery contract cannot be armed")
        if unit["unit_kind"] == "continuous" and unit["recovery_contract"] == "failure-cleared":
            raise ValueError("continuous services require active recovery; failure-cleared is W2-only")
        if unit["unit_kind"] in {"oneshot", "timer-service"}:
            if unit["armed"] or unit["recovery_contract"] != "unknown":
                raise ValueError("reused one-shot/timer services remain unarmed with unknown completion/recovery")
        if unit["unit_kind"] == "drill" and unit["recovery_contract"] != "failure-cleared":
            raise ValueError("drill requires the explicit failure-cleared recovery contract")
        if unit["unit_kind"] == "drill" and name != "paper-drill-w2.service":
            raise ValueError("only the CC-named W2 origin may use the drill contract")
    return deepcopy(value)


def receiver_config(policy):
    policy = validate_policy(policy)
    host = json.dumps(policy["host"])
    return {
        "receivers": {"systemd/f09": {
            "scope": "user", "collection_interval": "15s",
            "units": [unit["name"] for unit in policy["units"]],
            "metrics": {
                "systemd.unit.state": {"enabled": True},
                "systemd.service.cpu.time": {"enabled": False},
                "systemd.service.memory.usage": {"enabled": False},
                "systemd.service.memory.usage.max": {"enabled": False},
                "systemd.service.restarts": {"enabled": False},
            },
        }},
        "processors": {
            "filter/f09": {"error_mode": "propagate", "metrics": {
                "metric": ['name != "systemd.unit.state"'],
            }},
            "transform/f09": {"error_mode": "propagate", "metric_statements": [
                {"context": "datapoint", "statements": [
                    'set(attributes["unit"], resource.attributes["systemd.unit.name"])',
                    f'set(attributes["host"], {host})',
                    'set(attributes["state"], attributes["systemd.unit.active_state"])',
                    'keep_keys(attributes, ["host", "unit", "state"])',
                ]},
                {"context": "resource", "statements": ['keep_keys(attributes, [])']},
                {"context": "metric", "statements": [
                    'convert_sum_to_gauge() where type == METRIC_DATA_TYPE_SUM',
                ]},
            ]},
        },
        "exporters": {"prometheus/f09": {
            "endpoint": policy["listen"], "send_timestamps": True,
            "metric_expiration": "1m", "without_scope_info": True,
            "translation_strategy": "UnderscoreEscapingWithoutSuffixes",
            "resource_to_telemetry_conversion": {"enabled": False},
        }},
        "service": {"pipelines": {"metrics/f09": {
            "receivers": ["systemd/f09"],
            "processors": ["memory_limiter", "filter/f09", "transform/f09", "batch"],
            "exporters": ["prometheus/f09"],
        }}},
    }


def prometheus_rules(policy, template):
    policy = validate_policy(policy)
    if not isinstance(template, dict) or set(template) != {"groups"} or not isinstance(template["groups"], list):
        raise ValueError("rules template requires a native groups list")
    for group in template["groups"]:
        if not isinstance(group, dict) or not isinstance(group.get("rules"), list):
            raise ValueError("rules group requires a rules list")
        if any(not isinstance(rule, dict) or not isinstance(rule.get("expr"), str) for rule in group["rules"]):
            raise ValueError("rules require native rule objects with an expression")
        if any(rule.get("record") == EXPECTED for rule in group["rules"]):
            raise ValueError("expected roster records belong only to the renderer")
    rules = [{"record": EXPECTED, "expr": f'vector({int(unit["armed"])})', "labels": {
        "host": policy["host"], "unit": unit["name"],
        "failure_class": unit["failure_class"], "severity": unit["severity"],
        "unit_kind": unit["unit_kind"], "recovery_contract": unit["recovery_contract"],
        "completion_contract": unit["completion_contract"],
    }} for unit in policy["units"]]
    return {"groups": [{"name": "ns2604-f09-configured-roster", "interval": "15s", "rules": rules},
                       *deepcopy(template["groups"])]}


def prometheus_scrape(policy):
    policy = validate_policy(policy)
    return {"scrape_configs": [{"job_name": JOB, "scrape_interval": "15s",
                                "honor_timestamps": True,
                                "static_configs": [{"targets": [policy["listen"]]}]}]}


def encoded(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=reject_duplicate_keys)


def write_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(encoded(value))
    os.chmod(path, 0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=HERE / "policy.example.json")
    parser.add_argument("--rules-template", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check", action="store_true", help="compare committed receiver example without writing")
    args = parser.parse_args()
    try:
        policy = validate_policy(load(args.policy))
        receiver = receiver_config(policy)
        if args.check:
            if (HERE / "receiver.example.json").read_text() != encoded(receiver):
                raise ValueError("receiver example differs from rendered policy")
        if args.output_dir:
            if not args.rules_template or not args.rules_template.is_absolute():
                raise ValueError("output requires an absolute --rules-template source")
            rules = prometheus_rules(policy, load(args.rules_template))
            write_private(args.output_dir / "receiver.json", receiver)
            write_private(args.output_dir / "rules.json", rules)
            write_private(args.output_dir / "scrape.json", prometheus_scrape(policy))
        elif not args.check:
            raise ValueError("provide --check or --output-dir and --rules-template")
    except (ValueError, OSError, TypeError) as error:
        parser.exit(2, f"F09 render refused: {error}\n")
    print(json.dumps({"configured_units": len(policy["units"]),
                      "armed_units": sum(unit["armed"] for unit in policy["units"]),
                      "held_completion_units": sum(unit["unit_kind"] in {"oneshot", "timer-service"}
                                                   for unit in policy["units"]),
                      "host": policy["host"],
                      "scrape_job": JOB, "mode": "config-only", "checked": args.check}, sort_keys=True))


if __name__ == "__main__":
    main()
