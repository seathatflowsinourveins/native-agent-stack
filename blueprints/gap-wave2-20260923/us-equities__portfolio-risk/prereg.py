#!/usr/bin/env python3
"""Write preregistration skeletons for the portfolio-risk gap-wave-2 receipts.

Run once before any check executes. Each skeleton carries the gap text hash, the
expectation and the decision criteria; results are added later by finish_receipt.py.
"""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVID = ROOT / "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk"

PREREG = {
    0: ("skfolio-cpcv-prior-estimator", {
        "expectation": "On the frozen plan.json inputs (sha256 b8d1beba...), development daily close-to-close returns 2015-01-02..2020-12-31 as in run_optimizer.py, skfolio 1.2.9 in the requirements.lock venv (Python 3.13.15) runs CombinatorialPurgedCV(n_folds=10, n_test_folds=2, purged_size=6, embargo_size=0) with cross_val_predict on two MeanRisk estimators whose prior is explicit: EmpiricalPrior(covariance_estimator=LedoitWolf()) and EmpiricalPrior(covariance_estimator=ShrunkCovariance()). Each yields 45 splits and 9 test paths. A reserved fit on the last 252+6 development sessions with the same explicit priors predicts 2021Q1 weights. The results file hash is retained and committed.",
        "criteria": "settled iff: (a) CombinatorialPurgedCV reports n_splits==45 and n_test_paths==9 and cross_val_predict returns 9 population paths for each explicit-prior MeanRisk; (b) the fitted estimators' prior_estimator_.covariance_estimator_ are instances of LedoitWolf and ShrunkCovariance respectively and the LedoitWolf shrinkage_ is recorded; (c) every reserved weight vector is finite, non-negative and sums to 1 within 1e-6; (d) the nine LEAN input hashes are unchanged; (e) results.json sha256 is retained and the file committed. Any exception or count mismatch is not_settled. Detection: exact integer comparisons of n_splits/n_test_paths/path counts and isinstance checks on the fitted objects; a wrong estimator or split count raises an assertion in the runner.",
    }),
    1: ("candidate-libs-execution", {
        "expectation": "A new uv venv (Python 3.13.15) synced with --require-hashes from requirements-libs.lock pinning cvxportfolio==1.5.1, empyrical-reloaded==0.5.12 and quantstats==0.0.81 (plus skfolio 1.2.9) imports all three. On the frozen plan.json SPY/QQQ/IWM raw daily returns: cvxportfolio runs a native SinglePeriodOptimization minimum-variance policy (FullCovariance, LongOnly, LeverageLimit(1)) through policy.execute at 2021-01-04 and a MarketSimulator backtest over 2021Q1; empyrical-reloaded and quantstats compute annual return, annual volatility, Sharpe, Sortino and max drawdown on the equal-weight development return series.",
        "criteria": "settled iff each of the three library steps exits 0 in its own process, asserts its pinned version via importlib.metadata, produces finite outputs, and its command, exit code and output sha256 are recorded with the output committed. Any non-zero exit is recorded verbatim and that library is not_settled. Detection: separate processes per library, version assertion and math.isfinite checks that raise on NaN/inf.",
    }),
    2: ("walkforward-source-hash-match", {
        "expectation": "The installed skfolio 1.2.9 file skfolio/model_selection/_walk_forward.py in the lock venv hashes to the receipt's walkforward_source_sha256 f85cbe8b..., and `git show c99fcf71349e2df4a7a1033ee85ca2e9ced9abee:src/skfolio/model_selection/_walk_forward.py` of the skfolio repository hashes to the same value.",
        "criteria": "settled iff all three hashes (installed file, receipt value, upstream git blob at c99fcf71) are computed and the pairwise comparison result is recorded, whether match or mismatch; a mismatch is reported as a finding. Detection: the same hashing is applied to the file at skfolio tag v1.3.0 (or another revision) as a negative control; if that file differs, the comparison is shown able to report a mismatch.",
    }),
    3: ("evaluate-rerun-hash-compare", {
        "expectation": "A fresh Python 3.13.15 venv synced from requirements.lock re-runs evaluate.py on plan.json into a fresh directory. Scoring artifacts without clocks (candidate-ledger.json, 21 selection files, run-1.stdout.txt, run-1.stderr.txt) match the retained hashes byte for byte. freeze.json differs only in frozen_utc and results.json only in freeze_sha256 (which depends on freeze.json). Setup logs (venv/sync/compile/check/freeze stdout/stderr) differ where they embed paths or timings.",
        "criteria": "settled iff all 42 retained entries are compared (match, mismatch-explained or not-regenerable listed individually), every scoring artifact (ledger, 21 selections, stdout, stderr) matches or its mismatch is shown by a normalized semantic diff to leave every scored value unchanged, and the regenerated scoring artifacts are committed (ledger gzip-compressed) so they are no longer private. Detection: exact sha256 comparison per file; for mismatches a JSON diff after removing only the declared clock/hash fields must be empty or the item counts as unexplained.",
    }),
    4: ("nautilus-weights-accounting", {
        "expectation": "The skfolio reserved (2021Q1) and development-fold MeanRisk and HRP weights run through a native NautilusTrader 2.0.0rc5 BacktestEngine (CASH account, three Equity instruments on raw LEAN SPY/QQQ/IWM daily bars) with a per-order FixedFeeModel ($1 per order). Rebalancing at each fold's first test session to integer shares, the run reports cash, positions, fees and P&L, and an independent Decimal ledger reconciles every fill price, quantity, fee and cash transition against the weights. Dividend cash for ex-dates in the span is computed from the LEAN factor files as an unmodelled amount. Expected outcome: advanced, because dividend-inclusive bars depend on the dividend simulation module preregistered by peer session sota-workflow-resolution.",
        "criteria": "advanced iff the native run exits 0 and the independent ledger matches every native fill, fee and account balance exactly and the ending cash plus positions equals initial capital plus realized plus unrealized P&L; settled would additionally need dividend-inclusive accounting, which this unit does not own. not_settled on any unreconciled transition. Detection: per-transition exact Decimal equality; an injected one-cent fee perturbation in the self-test must make the reconciliation fail.",
    }),
    5: ("extended-reserved-significance", {
        "expectation": "A new frozen plan (plan-extended.json) reserves 2012-10-01..2013-09-30 on the same bundled LEAN SPY/QQQ/IWM data (data_start 2011-03-23, after the QQQQ->QQQ map change; warm-up 120 sessions; selector trained on the last 252 decision sessions before a six-session exclusion). This window precedes the research-evaluation study's 2014 data start, precedes the broad-universe protocol's 2016-01-04 warm-up, and ends before the 2013-10-07..11 week used by the LEAN engine samples. evaluate.py's unchanged label/choose/summaries functions (imported, file hash recorded) score it exactly once, giving at least 30 completed episodes per candidate. Predeclared test: primary two-sided one-sample t-test (scipy.stats.ttest_1samp) on paired per-episode differences net_proxy(selected rule) - net_proxy(equal-weight control), alpha 0.05; secondary two-sided Wilcoxon signed-rank on the same differences; descriptive one-sample t-tests of each invested candidate's net_proxy mean against 0 with Holm correction. No promotion, tuning or rerun follows from any result.",
        "criteria": "settled iff the frozen plan and this preregistration are committed before the single scoring run, the run exits 0 with >=30 completed episodes per candidate, and the predeclared test statistics and p-values are reported. A second scoring run is forbidden; a failed run is reported as not_settled with its error. Detection: the runner refuses an existing output directory and writes its freeze before parsing prices; the episode count check raises below 30.",
    }),
    6: ("nautilus-riskengine-denial", {
        "expectation": "In a native NautilusTrader 2.0.0rc5 backtest, the skfolio reserved HRP target orders pass a RiskEngineConfig with max_notional_per_order of 45000 USD per instrument and max_order_submit_rate '4/00:00:01', while a deliberately oversized SPY order (about 60000 USD notional) is denied with an OrderDenied event whose reason names the notional limit, and a burst of extra orders at the same timestamp beyond the submit rate is denied. A control arm without limits fills the same oversized order. Final positions equal the sum of filled orders only.",
        "criteria": "settled iff: (a) all within-limit target orders fill; (b) the oversized order produces OrderDenied mentioning notional, has no fill and leaves positions unchanged; (c) the control arm fills that same order (proving the probe can detect a missing denial); (d) at least one order beyond the submit rate is denied with a rate reason; (e) native positions and cash reconcile to an independent ledger of filled orders. If (d) is not observed, outcome is advanced with the rate clause named as remaining.",
    }),
    7: ("skfolio-130-upgrade", {
        "expectation": "Stale-pin upgrades are assigned to the SOTA refresh wave; its merged receipt evidence/artifacts/sota-refresh-20260923/pins-runtime/skfolio.json (PR #87) re-ran the WalkForward optimizer acceptance on skfolio 1.3.0 against the frozen inputs. No check is run here.",
        "criteria": "covered_elsewhere iff the cited receipt exists on origin/main and covers the 1.3.0 install and WalkForward/optimizer rerun; clauses it leaves (hash-locked install, README tag update) are named in limits.",
    }),
    9: ("matched-four-candidate-runner", {
        "expectation": "One preregistered run of matched_runner.py in the hashed candidate-libs venv applies all four candidates to the same plan.json development daily returns, the same skfolio WalkForward(252, 63, purged 6, reduce_test) folds and the same 20bp-per-fold fully-invested round-trip cost proxy: skfolio MeanRisk minimum variance and cvxportfolio SinglePeriodOptimization minimum variance each produce fold weights from the training window only; the resulting out-of-sample net return series (plus an equal-weight control) are scored by skfolio Portfolio measures, empyrical-reloaded and quantstats with common metrics (annualized return, annualized volatility, Sharpe, Sortino, max drawdown), all with 252 periods per year and zero risk-free rate. No winner, promotion or statistical claim.",
        "criteria": "settled iff the single run exits 0, reports every metric for every (series, library) cell as finite, records fold boundaries showing each weight used only training-window data (train_last < test_first - purged gap), and commits the output with its hash. Cross-library metric differences are reported, not adjudicated. Detection: the runner asserts fold boundaries and metric finiteness and exits non-zero on violation.",
    }),
    10: ("nautilus-optimizer-pnl", {
        "expectation": "Same native NautilusTrader run as gap 4: MeanRisk and HRP fold weights, FixedFeeModel $1/order, reconciled portfolio P&L reported beside skfolio's descriptive (daily-rebalanced, cost-free) fold returns over the same sessions.",
        "criteria": "settled iff for both optimizers the native run exits 0, every native fill, fee and account balance equals the independent ledger exactly, ending equity equals initial capital plus reconciled P&L, and the descriptive skfolio return is reported beside the reconciled Nautilus return with the difference decomposed into rebalancing convention, integer-share residual cash and fees. Detection as in gap 4.",
    }),
    11: ("nautilus-study-episodes-fees", {
        "expectation": "Every observed evaluation episode of the retained research-evaluation study (development folds and reserved 2021Q1, all five candidates, taken from the regenerated candidate ledger of gap 3) is executed in native NautilusTrader 2.0.0rc5: buy integer shares for 100000 USD notional at the t+1 open, sell at the t+6 open, using synthetic open-print bars. Cases: FixedFeeModel $1/order; and $1/order plus OneTickSlippageFillModel. Financing is explicitly zero (CASH account, long only, no borrowing; rc5 backtest modules offer only FX rollover and CFD swap financing). Per-candidate mean net return per episode is compared with the study's gross label and the fixed 20bp proxy. Expected outcome: advanced, because dividend-inclusive bars depend on the peer's dividend simulation module and no equity financing model exists to exercise.",
        "criteria": "advanced iff both cases exit 0, every fill reconciles to the ledger's entry/exit open prices (plus declared slippage) and integer shares, and the comparison table against the 20bp proxy is reported; settled would additionally need dividend-inclusive bars and a financing model. Detection: per-episode Decimal reconciliation; a mismatch raises.",
    }),
    14: ("parity-and-paper", {
        "expectation": "The Nautilus-versus-LEAN weight-schedule parity is covered under the peer session sota-workflow-resolution's SPY/LEAN parity preregistration, and Alpaca paper order submission with RiskEngine limits is a broker-contact lane owned by that same peer. No broker contact or paper-account call is made by this unit.",
        "criteria": "deferred with owner sota-workflow-resolution; the local RiskEngine denial evidence from gap 6 is cited as a partial input only.",
    }),
}


def main():
    units = json.loads(Path(sys.argv[1]).read_text())
    unit = next(u for u in units if u["layer_id"] == "portfolio-risk")
    gaps = {g["index"]: g for g in unit["gaps"]}
    written_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    EVID.mkdir(parents=True, exist_ok=True)
    for index, (slug, prereg) in PREREG.items():
        gap = gaps[index]
        path = EVID / f"{index}-{slug}.json"
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
        receipt = {
            "id": f"gap-wave2-20260923-us-equities-portfolio-risk-{index}-{slug}",
            "catalog": "us-equities", "layer_id": "portfolio-risk", "gap_index": index,
            "gap_text": gap["text"],
            "gap_text_sha256": hashlib.sha256(gap["text"].encode("utf-8")).hexdigest(),
            "next_check": gap["next_check"],
            "preregistration": {"written_at": written_at, **prereg},
            "commands": [], "results": {}, "outcome": None, "evidence_class": None,
            "limits": [], "checked_at": None,
        }
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
