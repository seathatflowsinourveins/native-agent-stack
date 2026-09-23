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
  version, so binding cannot be judged.

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
except ImportError:  # running as a plain script, not a package
    import host_receipts


DEFAULT_MAX_AGE_DAYS = 30
FLAGS = ("stale", "pin_moved", "no_bound_receipt", "no_current_pin")


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


def assess(summary: dict, pins_for, now: datetime, max_age_days: int) -> dict:
    """Pure core: ``summary`` is ``host_receipts.build_summary()`` output and ``pins_for`` maps a
    component id to ``(pins, pin_source)``. Returns the report dict."""
    rows = []
    for component_id in sorted(summary.get("components") or {}):
        pins, pin_source = pins_for(component_id)
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
            flags = []
            if not pins:
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
                             "reason": unbound_reason(entry, pins)} for entry in unbound],
                "flags": flags,
            })
    rows.sort(key=lambda row: (row["platform_id"], row["component_id"]))
    counts = {flag: sum(1 for row in rows if flag in row["flags"]) for flag in FLAGS}
    return {
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_age_days": max_age_days,
        "rows": rows,
        "flag_counts": counts,
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


def render_text(report: dict) -> str:
    lines = [f"Receipt staleness at {report['generated_at_utc']} (window {report['max_age_days']} days): "
             f"{len(report['rows'])} component x platform bucket(s), {report['flagged']} flagged."]
    for row in report["rows"]:
        latest = row["latest_bound"]
        latest_text = ("no bound receipt" if latest is None else
                       f"latest bound {latest['observed_at_utc']} ({latest['age_days']} days, {latest['result']}, "
                       f"version {latest['component_version']})")
        flags = ", ".join(row["flags"]) or "ok"
        lines.append(f"{row['platform_id']}  {row['component_id']}: {latest_text}; pins {row['current_pins']} "
                     f"({row['pin_source']}); {row['bound_receipts']}/{row['receipts']} bound; {flags}")
        if row["pin_moved_hosts"]:
            lines.append(f"    re-record at the current pin: {', '.join(row['pin_moved_hosts'])}")
        for entry in row["unbound"]:
            lines.append(f"    unbound: {entry['path']} (version {entry['component_version']}, {entry['reason']})")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS,
                        help=f"flag a latest bound receipt older than this (default {DEFAULT_MAX_AGE_DAYS})")
    parser.add_argument("--now", help="evaluate ages at this UTC time (YYYY-MM-DDTHH:MM:SSZ); default: the clock")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--out", type=Path, help="also write the printed report to this file (outside the checkout)")
    args = parser.parse_args(argv)
    if args.max_age_days < 0:
        parser.error("--max-age-days must be zero or more")
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
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 2
    report = assess(summary, lambda component_id: current_pins(root, component_id), now, args.max_age_days)
    text = json.dumps(report, indent=1, sort_keys=True) if args.json else render_text(report)
    print(text)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
