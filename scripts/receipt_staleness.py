#!/usr/bin/env python3
"""Report host receipts that are old or no longer bound to the current pin.

Read-only. Per platform and component with at least one receipt under ``evidence/hosts/``,
this lists the latest receipt *bound* to a current pin and its age, and flags:

- ``stale``: the latest bound receipt is older than ``--max-age-days`` (default 30);
- ``pin_moved``: for at least one host and stage, that host's newest schema-valid receipt on this
  platform records a version that matches no current pin (a pin bump retired it and the host
  has not re-recorded at the new pin; see adoption/update.md "Moving a host to a new release").
  Older receipts at a retired pin stay in the tree and stay listed under ``unbound``, but they
  do not raise the flag once the same host has a newer receipt at the current pin, so the flag
  clears when the host is done;
- ``no_bound_receipt``: receipts exist but none matches a current pin;
- ``no_current_pin``: neither a landscape winner nor ``manifests/stack.json`` gives a
  version, so binding cannot be judged;
- ``stack_alias``: the component id is a ``manifests/stack.json`` id sharing its repository with a
  differently named landscape winner (``host_receipts.winner_stack_aliases``; the row's
  ``alias_of`` names the winner) and at least one of the row's receipts is not grandfathered.
  scripts/platform_status.py joins receipts by the winner's own id, so these receipts never bind
  and are never judged against the stack version; re-record under the winner id.

A row whose receipts are all grandfathered alias receipts (``host_receipts.GRANDFATHERED_ALIAS_RECEIPTS``
paths whose recorded claim still matches the entry's ``claim_sha256``; ``host_receipts.py validate`` accepts exactly
those) is informational, not flagged: it keeps ``alias_of``, has ``grandfathered: true`` and
``info: ["stack_alias_grandfathered"]``, and counts under the report's ``info_counts``, so a
permanent, validated exemption does not keep the report ``flagged``. Such a receipt still never binds.

"Bound" follows scripts/platform_status.py: a schema-valid receipt whose host os/architecture
match the platform profile and whose ``tool_versions[component_id]`` matches a current pin
(``host_receipts.pin_matches``). The current pins are the component's landscape winner pins
(``host_receipts.winner_pins``) or, when no layer selects it, its ``manifests/stack.json``
version, the same fallback ``host_receipts.py record`` uses.

Age depends on the clock, so this report is deliberately separate from the generated matrix
(``scripts/component_matrix.py --check`` stays deterministic) and it never writes into the
repository. ``.github/workflows/receipt-staleness.yml`` runs it on a schedule and uploads the
output as an artifact. It always exits 0 unless its own inputs are unreadable (exit 2); it
is a signal for a maintainer, not a gate.

  python3 scripts/receipt_staleness.py                    # text report
  python3 scripts/receipt_staleness.py --json --out "$RUNNER_TEMP/receipt-staleness.json"
  python3 scripts/receipt_staleness.py --max-age-days 14 --now 2026-10-01T00:00:00Z
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from . import host_receipts
    from . import organic_use
except ImportError:  # running as a plain script, not a package
    import host_receipts
    import organic_use


DEFAULT_MAX_AGE_DAYS = 30
FLAGS = ("stale", "pin_moved", "no_bound_receipt", "no_current_pin", "stack_alias")
INFO = ("stack_alias_grandfathered",)


def parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if not host_receipts.ISO_UTC_PATTERN.fullmatch(value):
        raise ValueError(f"--now must look like 2026-09-23T00:00:00Z, got {value!r}")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def current_pins(root: Path, component_id: str) -> tuple[list[str], str]:
    """The pins a receipt for ``component_id`` may bind to, and where they came from."""
    winners = sorted(host_receipts.winner_pins(root, component_id))
    if winners:
        return winners, "landscape_winner"
    stack = host_receipts.stack_component_version(root, component_id)
    if isinstance(stack, str) and stack.strip():
        return [stack.strip()], "stack_manifest"
    return [], "none"


def is_bound(entry: dict, pins: list[str]) -> bool:
    return bool(entry.get("shape_ok") and entry.get("platform_identity_ok")
                and any(host_receipts.pin_matches(entry.get("component_version"), pin) for pin in pins))


def assess(summary: dict, pins_for, now: datetime, max_age_days: int,
           aliases: dict[str, tuple[str, ...]] | None = None, grandfathered_paths=frozenset()) -> dict:
    """Pure core: ``summary`` is ``host_receipts.build_summary()`` output, ``pins_for`` maps a
    component id to ``(pins, pin_source)``, ``aliases`` is ``host_receipts.winner_stack_aliases()``
    (a stack id -> the winner id(s) it aliases; its receipts never bind) and ``grandfathered_paths``
    is ``host_receipts.grandfathered_alias_paths()`` (alias receipts reported as info, not flagged).
    Returns the report dict."""
    aliases = aliases or {}
    grandfathered_paths = set(grandfathered_paths or ())
    rows = []
    for component_id in sorted(summary.get("components") or {}):
        alias_of = list(aliases.get(component_id) or ())
        pins, pin_source = ([], "stack_alias") if alias_of else pins_for(component_id)
        platforms = (summary["components"][component_id] or {}).get("platforms") or {}
        for platform_id in sorted(platforms):
            entries = [entry for entry in (platforms[platform_id] or {}).get("receipts") or []
                       if isinstance(entry, dict)]
            if not entries:
                continue
            bound = [entry for entry in entries if is_bound(entry, pins)]
            unbound = [entry for entry in entries if entry not in bound]
            latest = max(bound, key=lambda entry: (entry.get("observed_at_utc") or "", entry.get("path") or ""),
                         default=None)
            age = host_receipts.receipt_age_days(latest.get("observed_at_utc"), now) if latest else None
            flags, info = [], []
            grandfathered = bool(alias_of) and all(entry.get("path") in grandfathered_paths for entry in entries)
            if grandfathered:
                info.append("stack_alias_grandfathered")
            elif alias_of:
                flags.append("stack_alias")
            elif not pins:
                flags.append("no_current_pin")
            else:
                if latest is None:
                    flags.append("no_bound_receipt")
                elif age is None or age > max_age_days:
                    flags.append("stale")
                if moved_hosts(entries, pins):
                    flags.append("pin_moved")
            rows.append({
                "platform_id": platform_id,
                "component_id": component_id,
                "current_pins": pins,
                "pin_source": pin_source,
                "alias_of": alias_of,
                "grandfathered": grandfathered,
                "receipts": len(entries),
                "bound_receipts": len(bound),
                "latest_bound": None if latest is None else {
                    "path": latest.get("path"),
                    "observed_at_utc": latest.get("observed_at_utc"),
                    "age_days": age,
                    "result": latest.get("result"),
                    "stage": latest.get("stage"),
                    "component_version": latest.get("component_version"),
                },
                "pin_moved_hosts": moved_hosts(entries, pins) if pins else [],
                "unbound": [{"path": entry.get("path"), "component_version": entry.get("component_version"),
                             "observed_at_utc": entry.get("observed_at_utc"),
                             "reason": ("stack_alias_grandfathered" if entry.get("path") in grandfathered_paths
                                        else "stack_alias") if alias_of else unbound_reason(entry, pins)}
                            for entry in unbound],
                "flags": flags,
                "info": info,
            })
    rows.sort(key=lambda row: (row["platform_id"], row["component_id"]))
    counts = {flag: sum(1 for row in rows if flag in row["flags"]) for flag in FLAGS}
    return {
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_age_days": max_age_days,
        "rows": rows,
        "flag_counts": counts,
        "info_counts": {item: sum(1 for row in rows if item in row["info"]) for item in INFO},
        "flagged": sum(1 for row in rows if row["flags"]),
        "status": "flagged" if any(row["flags"] for row in rows) else "current",
    }


def moved_hosts(entries: list[dict], pins: list[str]) -> list[str]:
    """``host_id/stage`` for each host and stage whose newest judgeable receipt is at a retired pin.

    Only schema-valid receipts whose platform identity matches are judgeable; an invalid or
    wrong-platform receipt neither raises nor clears the flag."""
    newest: dict[tuple[str, str], dict] = {}
    for entry in entries:
        if not (entry.get("shape_ok") and entry.get("platform_identity_ok")):
            continue
        key = (str(entry.get("host_id")), str(entry.get("stage")))
        order = (entry.get("observed_at_utc") or "", entry.get("path") or "")
        if key not in newest or order > (newest[key].get("observed_at_utc") or "", newest[key].get("path") or ""):
            newest[key] = entry
    return sorted(f"{host}/{stage}" for (host, stage), entry in newest.items() if not is_bound(entry, pins))


def unbound_reason(entry: dict, pins: list[str]) -> str:
    if not entry.get("shape_ok"):
        return "schema_invalid"
    if not entry.get("platform_identity_ok"):
        return "platform_identity_mismatch"
    if not pins:
        return "no_current_pin"
    return "pin_moved"


def assess_organic(root: Path, now: datetime, client_versions: dict | None = None,
                   client_contexts: dict | None = None) -> list[dict]:
    """Report registered organic observations separately from host acceptance.

    Default client comparisons use declared catalog versions, not live host
    discovery. An owner can supply a current version without changing host config.
    A changed landscape hash alone is not a reopen: retain actual later ledger
    reopen records for the observation's layers. This writes no sweep.
    """
    records = organic_use.load_records(root)
    if not records:
        return []
    stack = json.loads((root / "manifests/stack.json").read_text())
    versions = {item["id"]: item.get("version") for item in stack.get("components", [])}
    ledger = json.loads((root / "catalogs/saturation/ledger.json").read_text())
    overrides = client_versions or {}
    contexts = client_contexts or {}
    rows = []
    for record in records:
        client_id = record["client"]["id"]
        client_version = overrides.get(client_id, versions.get(client_id))
        sweeps = ledger.get("sweeps", [])
        baseline_index = next((index for index, sweep in enumerate(sweeps)
                               if sweep.get("sweep_id") == record["recheck"]["sweep_id"]), None)
        reopens = [sweep["sweep_id"] for sweep in sweeps[baseline_index + 1:]
                   if any(f"{layer.get('catalog')}/{layer.get('layer_id')}" in record["layer_ids"]
                          and layer.get("reopen") for layer in sweep.get("layers", []))] if baseline_index is not None else []
        context_keys = ("mode", "model", "effective_effort", "effective_tier", "route", "config_sha256")
        # Arm, runtime mode and treatment identities can differ within a client.
        # Supply current context for an exact observation block, never pool it.
        current_context = contexts.get(record["block_ref"], {})
        unknown_context = [f"client_{key}" for key in context_keys
                           if current_context.get(key) is None or record["client"].get(key) is None]
        flags = organic_use.recheck(record, versions.get(record["component_id"]),
                                    client_version, now, landscape_reopened=bool(reopens))
        if any(current_context.get(key) is not None and record["client"].get(key) is not None
               and current_context[key] != record["client"][key] for key in context_keys):
            flags.append("organic_context_changed")
        not_checked = (["tool_pin"] if record["component_pin"] is None
                       or versions.get(record["component_id"]) is None else []) \
                      + (["client_version"] if client_version is None else []) \
                      + (["landscape_sweep"] if baseline_index is None else []) + unknown_context
        rows.append({
            "component_id": record["component_id"], "platform_id": record["platform_id"],
            "layer_ids": record["layer_ids"], "client": record["client"], "arm": record["arm"],
            "receipt_ref": record["receipt_ref"], "observed_at_utc": record["observed_at_utc"],
            "block_ref": record["block_ref"], "receipt_sha256": record["receipt_sha256"],
            "state": record["state"], "verdict": record["verdict"],
            "current_tool_pin": versions.get(record["component_id"]),
            "current_tool_pin_source": "declared_catalog",
            "current_client_version": client_version,
            "client_version_source": "owner_supplied" if client_id in overrides else "declared_catalog",
            "current_client_context": {key: current_context.get(key) for key in context_keys},
            "current_client_context_source": "owner_supplied" if current_context else "not_supplied",
            "max_age_days": record["recheck"]["max_age_days"], "landscape_reopen_sweeps": reopens,
            "not_checked": not_checked, "flags": flags,
            "binding_status": "requires_recheck" if flags else "unknown" if not_checked else "current",
            "saturation_trigger_active": True,
        })
    by_ref = {record["block_ref"]: (record, row) for record, row in zip(records, rows)}
    for old_ref, (old, old_row) in by_ref.items():
        previous = old
        visited = {old_ref}
        while True:
            successors = [record for record in records
                          if (record.get("supersedes") or {}).get("ref") == previous["block_ref"]]
            if len(successors) != 1:
                break  # forks and incomplete successors do not discharge a current recheck
            new = successors[0]
            if new["block_ref"] in visited:
                break
            visited.add(new["block_ref"])
            same_scope = all(previous[key] == new[key] for key in
                             ("component_id", "platform_id", "arm", "task_scope", "layer_ids")) \
                         and previous["client"]["id"] == new["client"]["id"] \
                         and previous["client"].get("mode") == new["client"].get("mode")
            reviewed = new["stage"] == "qualification" and new["state"] == "complete" \
                       and new["verdict"] in ("READY", "NOT-READY", "EXCLUDED") \
                       and new["qualification"]["status"] == "complete" \
                       and new["review"]["status"] == "reviewed" \
                       and new["adjudication"]["status"] == "adjudicated"
            if not (same_scope and reviewed and new["supersedes"]["sha256"] == previous["receipt_sha256"]):
                break
            if by_ref[new["block_ref"]][1]["binding_status"] == "current":
                old_row["saturation_trigger_active"] = False
                old_row["discharged_by"] = new["block_ref"]
                break
            previous = new  # a unique reviewed chain can reach a later current leaf
    return rows


def render_text(report: dict) -> str:
    lines = [f"Receipt staleness at {report['generated_at_utc']} (window {report['max_age_days']} days): "
             f"{len(report['rows'])} component x platform bucket(s), {report['flagged']} flagged."]
    for row in report["rows"]:
        latest = row["latest_bound"]
        latest_text = ("no bound receipt" if latest is None else
                       f"latest bound {latest['observed_at_utc']} ({latest['age_days']} days, {latest['result']}, "
                       f"version {latest['component_version']})")
        flags = ", ".join(row["flags"]) or "ok"
        if row.get("info"):
            flags += f" (info: {', '.join(row['info'])})"
        pins_text = (f"alias of winner {', '.join(row['alias_of'])}, never bound" if row.get("alias_of")
                     else f"pins {row['current_pins']} ({row['pin_source']})")
        lines.append(f"{row['platform_id']}  {row['component_id']}: {latest_text}; {pins_text}; "
                     f"{row['bound_receipts']}/{row['receipts']} bound; {flags}")
        if row["pin_moved_hosts"]:
            lines.append(f"    re-record at the current pin: {', '.join(row['pin_moved_hosts'])}")
        for entry in row["unbound"]:
            lines.append(f"    unbound: {entry['path']} (version {entry['component_version']}, {entry['reason']})")
    for row in report.get("organic_use", []):
        flags = ", ".join(row["flags"]) or "no known recheck trigger"
        lines.append(f"organic {row['component_id']} / {row['client']['id']} / {row['arm']}: "
                     f"{row['state']}; {flags}; client comparison {row['client_version_source']}; "
                     f"not checked: {', '.join(row['not_checked']) or 'none'}; {row['receipt_ref']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS,
                        help=f"flag a latest bound receipt older than this (default {DEFAULT_MAX_AGE_DAYS})")
    parser.add_argument("--now", help="evaluate ages at this UTC time (YYYY-MM-DDTHH:MM:SSZ); default: the clock")
    parser.add_argument("--client-version", action="append", default=[], metavar="ID=VERSION",
                        help="owner-supplied current client version for organic rechecks; default: catalog version")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--out", type=Path, help="also write the printed report to this file (outside the checkout)")
    args = parser.parse_args(argv)
    if args.max_age_days < 0:
        parser.error("--max-age-days must be zero or more")
    client_versions = {}
    for value in args.client_version:
        identifier, separator, version = value.partition("=")
        if not separator or not identifier or not version or identifier in client_versions:
            parser.error("--client-version needs a unique nonempty ID=VERSION")
        client_versions[identifier] = version
    root = args.root.resolve()
    out = args.out.resolve() if args.out is not None else None
    if out is not None and (out == root or root in out.parents):
        parser.error(f"--out must be outside the checkout ({root}); this report never writes into it")
    try:
        now = parse_now(args.now)
    except ValueError as error:
        parser.error(str(error))
    try:
        summary = host_receipts.build_summary(root)
        organic_rows = assess_organic(root, now, client_versions)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 2
    report = assess(summary, lambda component_id: current_pins(root, component_id), now, args.max_age_days,
                    host_receipts.winner_stack_aliases(root), host_receipts.grandfathered_alias_paths(root))
    if organic_rows:
        report["organic_use"] = organic_rows
    text = json.dumps(report, indent=1, sort_keys=True) if args.json else render_text(report)
    print(text)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
