#!/usr/bin/env python3
"""Fix round 3 (after the independent Opus review): add dated preregistration addenda to the gap 1 and gap 4
receipts before their reruns. Existing preregistration fields are left untouched."""
import datetime as dt
import json
from pathlib import Path

EVID = Path(__file__).resolve().parents[3] / "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk"
NOW = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ADD = {
    "1-candidate-libs-execution.json": (
        "Fix round 3 after the Opus review (runner-hash binding): rerun all three libraries with the committed, unchanged "
        "gap1_libs.py (sha256 902d15efbf4dc04a383bed5d9f8193ae052c4e5e9051ccd5527c634faad5bcef) and common.py "
        "(sha256 0fe887db31f6cc437129b90aea0d83380b322c5bbde35179b336b8763e6c00cb) into raw/1/fix3-rerun. Expected: each "
        "output JSON is byte-identical to the committed raw/1/<lib>.json, which binds the attempt-2 empyrical-reloaded and "
        "quantstats outputs to the committed runner by reproduction. Detection: sha256 comparison per file; any difference is "
        "reported per library and that committed output is then bound only to the unretained pre-edit runner. Outcome stays "
        "settled only if all three reproduce."),
    "4-nautilus-weights-accounting.json": (
        "Fix round 3 after the Opus review (dividend arm not mutation-tested): nautilus_portfolio_dividends.py moves its "
        "existing comparisons into one check function (same comparisons, plus explicit denial and flat-end checks) and adds "
        "mutation self-tests on copies of the native reports: wrong instrument, 1900 fill time, one-hour fill time shift, "
        "corrupted first account transition, corrupted first nonzero dividend account transition, removed dividend account row, "
        "corrupted emission amount, removed emission, shifted emission ex_date, injected module error, corrupted decision equity "
        "and removed decisions; plus a ledger fee +0.01 USD perturbation. Every mutation and the perturbation must be detected, "
        "or the runner exits non-zero. Rerun into raw/4/nautilus-dividends-run-fix3. Expected: economic results identical to "
        "fix round 2 (ending cash 2207656.15 / 2451556.98). Outcome stays advanced (financing and liquidity not exercised)."),
}
for name, text in ADD.items():
    path = EVID / name
    receipt = json.loads(path.read_text())
    if "fix_round_3_addendum" in receipt["preregistration"]:
        raise SystemExit(f"{name}: addendum already written")
    receipt["preregistration"]["fix_round_3_addendum"] = {
        "written_at": NOW,
        "label": "fix-round-3 preregistration, written after the independent Opus review and before the fix-round-3 reruns",
        "text": text}
    path.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
print(NOW)
