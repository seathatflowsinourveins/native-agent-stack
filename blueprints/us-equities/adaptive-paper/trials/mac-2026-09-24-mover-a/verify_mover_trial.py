"""Offline re-check of one committed mover paper trial directory (stdlib only).

Integrity and consistency, without broker or network access:
- the config's sha256 equals the receipt's ``config_sha256`` and the plan's (``check.json``);
- the receipt's ``scan_sha256`` equals the plan's and the engine scan hash in ``scan.sha256``;
- the receipt is flat and ``pnl_consistent``, and the final reconciliation (the native loop's
  end, or the forced recovery's when the loop handed off) has ``cash_match`` and
  ``positions_match`` true with 0 open orders;
- a ``mover-recovery.json``, when present, passed flat with the same reconciliation;
- the ledger readback agrees with the receipt: every leg flat, the same number of filled
  orders, and the same realized P&L to the cent.

It then prints the recorded outcome (status and force reason) without judging it: the frozen
acceptance criteria are in FREEZE.md.

    python verify_mover_trial.py DIR
"""
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    d = Path(sys.argv[1])
    configs = sorted(d.glob("config-mover-*.json"))
    if len(configs) != 1:
        raise SystemExit("expected one config-mover-*.json")
    receipt = json.loads((d / "mover-paper.json").read_text())
    plan = json.loads((d / "check.json").read_text())
    readback = json.loads((d / "ledger-readback.json").read_text())
    scans = dict(reversed(line.split()) for line in (d / "scan.sha256").read_text().splitlines() if line.strip())
    failures = []

    def expect(name, ok):
        print(("ok   " if ok else "FAIL ") + name)
        if not ok:
            failures.append(name)

    config_sha = sha(configs[0])
    expect("config sha256 = receipt config_sha256 = plan config_sha256",
           receipt.get("config_sha256") == plan.get("config_sha256") == config_sha)
    expect("receipt scan_sha256 = plan scan_sha256 = scan.sha256 (scan.json)",
           receipt.get("scan_sha256") == plan.get("scan_sha256") == scans.get("scan.json"))
    expect("receipt flat", receipt.get("flat") is True)
    totals = receipt.get("totals") or {}
    expect("receipt pnl_consistent", totals.get("pnl_consistent") is True)
    reconciliation = receipt.get("reconciliation") or {}
    final = reconciliation.get("end") or (reconciliation.get("recovery") or {}).get("reconciliation") or {}
    expect("final reconciliation cash_match and positions_match, 0 open orders",
           final.get("cash_match") is True and final.get("positions_match") is True and final.get("open_orders") == 0)
    recovery_file = d / "mover-recovery.json"
    if recovery_file.exists():
        recovery = json.loads(recovery_file.read_text())
        rec = recovery.get("reconciliation") or {}
        expect("recover proof passed flat with cash_match and positions_match",
               recovery.get("status") == "passed" and recovery.get("flat") is True
               and rec.get("cash_match") is True and rec.get("positions_match") is True)
    expect("readback: every leg flat", readback["totals"]["all_legs_flat"] is True)
    receipt_pnl = Decimal(str(totals.get("realized_pnl_usd", "nan")))
    readback_pnl = Decimal(readback["totals"]["realized_pnl_usd"])
    expect("readback realized P&L = receipt realized P&L (to the cent)", abs(receipt_pnl - readback_pnl) < Decimal("0.01"))
    engine_filled = sum(1 for s in receipt.get("symbols", [])
                        for o in [s.get("entry") or {}] + (s.get("exits") or [])
                        if o.get("ledger_status") == "filled")
    recovery_filled = len(((reconciliation.get("recovery") or {}).get("exit_attempt_client_ids") or []))
    expect("readback filled intents = receipt engine fills + recovery exits",
           readback["totals"]["filled_intents"] == engine_filled + recovery_filled)
    print("recorded outcome:", json.dumps({k: receipt.get(k) for k in ("status", "force_reason", "evidence_class")}))
    print("FAILED" if failures else "PASSED", len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
