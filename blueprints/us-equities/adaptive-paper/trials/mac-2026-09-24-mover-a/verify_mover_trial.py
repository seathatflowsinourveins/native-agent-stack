"""Offline re-check of one committed mover paper trial directory (stdlib only).

Integrity (each must pass), without broker or network access:
- the config's sha256 equals the receipt's ``config_sha256`` and the plan's (``check.json``);
- the receipt's ``scan_sha256`` equals the plan's and the engine scan hash in ``scan.sha256``;
- a flat receipt's totals are ``pnl_consistent``;
- the ledger readback agrees with the receipt: the same flat state, the same number of filled
  orders (engine fills plus recovery exits), and the same realized P&L to the cent.

It then prints the recorded outcome without judging it (status, force reason, flat state, the
final reconciliation and every committed recovery receipt); the frozen acceptance criteria are
in FREEZE.md and the README states the result against them.

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
    configs = sorted(p for p in d.glob("config-mover-*.json") if "recover" not in p.name)
    if len(configs) != 1:
        raise SystemExit("expected one trial config-mover-*.json")
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
    totals = receipt.get("totals") or {}
    expect("readback flat state = receipt flat state", readback["totals"]["all_legs_flat"] is receipt.get("flat"))
    readback_pnl = Decimal(readback["totals"]["realized_pnl_usd"])
    if receipt.get("flat"):
        expect("receipt pnl_consistent", totals.get("pnl_consistent") is True)
        receipt_pnl = Decimal(str(totals.get("realized_pnl_usd")))
        expect("readback realized P&L = receipt realized P&L (to the cent)", abs(receipt_pnl - readback_pnl) < Decimal("0.01"))
    else:
        # Open legs: the receipt leaves realized P&L unset; compare the ledger's own realized delta.
        ledger_pnl = Decimal(str(totals.get("ledger_realized_pnl_delta_usd")))
        expect("not flat: readback realized P&L = receipt ledger_realized_pnl_delta_usd", abs(ledger_pnl - readback_pnl) < Decimal("0.01"))
    reconciliation = receipt.get("reconciliation") or {}
    engine_filled = sum(1 for s in receipt.get("symbols", [])
                        for o in [s.get("entry") or {}] + (s.get("exits") or [])
                        if o.get("ledger_status") == "filled")
    recovery_filled = len(((reconciliation.get("recovery") or {}).get("exit_attempt_client_ids") or []))
    expect("readback filled intents = receipt engine fills + recovery exits",
           readback["totals"]["filled_intents"] == engine_filled + recovery_filled)
    final = reconciliation.get("end") or (reconciliation.get("recovery") or {}).get("reconciliation")
    print("outcome:", json.dumps({"status": receipt.get("status"), "force_reason": receipt.get("force_reason"),
                                  "flat": receipt.get("flat"), "final_reconciliation": final,
                                  "evidence_class": receipt.get("evidence_class")}))
    for path in sorted(d.glob("mover-recovery*.json")):
        rec = json.loads(path.read_text())
        print(f"recovery {path.name}:", json.dumps({k: rec.get(k) for k in ("status", "flat", "errors")}))
    print("FAILED" if failures else "PASSED", len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
