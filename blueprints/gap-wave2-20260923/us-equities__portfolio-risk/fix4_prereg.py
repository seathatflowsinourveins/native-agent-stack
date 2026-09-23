#!/usr/bin/env python3
"""Fix round 4 (after the second independent Opus review): add dated preregistration addenda to the gap 14 and
gap 11 receipts before their new arms run. Existing preregistration fields are left untouched."""
import datetime as dt
import json
from pathlib import Path

EVID = Path(__file__).resolve().parents[3] / "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk"
NOW = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
ADD = {
    "14-parity-and-paper.json": (
        "Fix round 4 after the Opus review (LEAN arm executable here but not run): run the first arm of the next_check. "
        "A new C# algorithm (lean_parity/WeightScheduleParityAlgorithm.cs) replays raw/4-10/skfolio-fold-weights.json "
        "(sha256 30e9b17a989c288357889b4c4d91254450c2b52c97dca509ec20139161f81765) for meanrisk_min_variance and hrp_variance "
        "in native LEAN 985ef30 (the accepted patched build) on the same raw daily SPY/QQQ/IWM bars: 1,000,000 USD, the same "
        "sizing rule floor(equity x 0.99 x weight / close) with Decimal weights parsed from the float repr, sells submitted "
        "and filled before buys, liquidation at the 2021-03-31 close. Declared LEAN settings: ConstantFeeModel 1 USD per "
        "order; a close-fill model (FillModel subclass that fills market orders at the triggering daily bar's close at 16:00 "
        "New York, because LEAN's MarketOrder helper converts daily-resolution orders to MarketOnOpen/MarketOnClose); orders "
        "submitted with SubmitOrderRequest(OrderType.Market); margin account, leverage 1, immediate settlement; no fill-forward. "
        "Runs use the execution-realism bwrap sandbox (no network, read-only engine/data). Cases: (a) no_dividends, factor "
        "files hidden by a tmpfs over /data/equity/usa/factor_files, diffed against raw/4-10/nautilus-run-fix2; (b) dividends, "
        "LEAN's native raw-mode dividend cash, diffed against raw/4/nautilus-dividends-run-fix3 (peer DistributionModule); "
        "(c) negative control, fee 2 USD without dividends, diffed against fix2 and required to be reported as a mismatch. "
        "Criteria per optimizer in (a) and (b): fills equal exactly as a multiset of (16:00 New York timestamp, asset, side, "
        "quantity, fill price, fee), reading LEAN's native order-events JSON; rebalance decisions equal exactly (date, equity "
        "before, integer targets); every cash transition after each fill (and, in (b), each dividend credit with ex-date, "
        "asset, quantity and amount) equal exactly in order; total fees equal; ending cash equal exactly; final positions "
        "flat. Detection: mutation self-tests on copies of the LEAN outputs (fill price +0.0001, fill time +1 h, one fill "
        "removed, first cash transition +0.01, one fee +0.01, one dividend credit removed in (b)) must each be detected, and "
        "case (c) must be detected natively. Expected: (a) and (b) match exactly and (c) is detected. Any mismatch is reported "
        "with the first differing rows, not tolerated. Outcome: advanced at best, because the Alpaca paper-order arm stays "
        "deferred to its owner sota-workflow-resolution; LEAN runs exceeding 20 minutes are stopped and recorded."),
    "11-nautilus-study-episodes-fees.json": (
        "Fix round 4 after the Opus review (dividend-inclusive episodes feasible but not run): a new runner "
        "nautilus_episodes_dividends.py replays the fixed-fee case (FixedFeeModel 1 USD) of every invested candidate with the "
        "vendored peer DistributionModule (sha256 eefee070b0dbe6ad3a1e68755ca959b5fff081fad61af8b84902a438996b126b) per "
        "instrument, so native ex-date cash is credited for shares held at each ex-date instant (00:00 New York). An "
        "independent Decimal ledger merges fills (09:30 open prints, cent-rounded notionals as in fix round 2) and dividend "
        "credits chronologically and must match every native account transition, every module emission and every fill; "
        "episode returns include the credits for the episode's legs. Mutation self-tests (emission removed, emission amount "
        "+0.01, dividend account row removed, fill time +1 h) must each be detected. Reported per candidate: credited "
        "dividend cash and mean native net return per episode with dividends, beside the fixed-fee result without them. "
        "Expected: credited cash is close to the previously reported unmodelled_dividend_cash_usd (same ex-date rule), "
        "differing only by the module's per-share cent rounding; the difference is reported. Outcome stays advanced: the "
        "financing model and fill/liquidity realism clauses remain open."),
}
for name, text in ADD.items():
    path = EVID / name
    receipt = json.loads(path.read_text())
    if "fix_round_4_addendum" in receipt["preregistration"]:
        raise SystemExit(f"{name}: addendum already written")
    receipt["preregistration"]["fix_round_4_addendum"] = {
        "written_at": NOW,
        "label": "fix-round-4 preregistration, written after the second independent Opus review and before the fix-round-4 runs",
        "text": text}
    path.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
print(NOW)
