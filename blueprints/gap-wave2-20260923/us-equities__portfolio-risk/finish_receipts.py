#!/usr/bin/env python3
"""Fill the post-run fields of the portfolio-risk gap-wave-2 receipts (preregistration left untouched),
then regenerate results.json from the receipts. Every cited raw artifact is re-hashed from disk."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVID = ROOT / "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk"
BP = "blueprints/gap-wave2-20260923/us-equities__portfolio-risk"
RAW = "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw"
VL = "$HOME/.cache/gap-wave2-20260923/portfolio-risk/venv-lock/bin/python"
VB = "$HOME/.cache/gap-wave2-20260923/portfolio-risk/venv-libs/bin/python"
VN = "$HOME/.cache/gap-wave2-20260923/portfolio-risk/venv-nautilus/bin/python"
LEAN = "LEAN_SOURCE=$HOME/.local/share/codex-ecosystem/tools/lean-985ef30"

REVIEW = {
    1: "minor: runner used NoCash instead of the preregistered LeverageLimit(1) -> disclosed as a deviation in limits",
    3: "major: settled overclaimed (4 unregenerated setup artifacts; 2 mismatches from unknown input) -> outcome changed to advanced and limits corrected",
    4: "major: settled overclaimed (financing and liquidity in gap text) -> outcome advanced; major: nautilus_portfolio.py zip without length check -> count check and mutation self-tests added, fix-round rerun reconciles",
    5: "minor: plan-extended.json inherited stale 2014-2021 corporate-action text -> disclosed (plan is frozen, not edited)",
    6: "major: rejections could satisfy positive controls; intermediate cash and wrong-instrument/time fills escaped -> rejections fail, fill-based criteria, full cash sequence, instrument/date checks and mutation self-tests added; fix-round rerun passes",
    9: "major: single-run criterion vs an earlier unread dry run -> disclosed and determinism rerun matched byte for byte; round 2 judged it still unresolved, so the outcome is advanced; minor: quantstats CAGR convention mislabelled -> corrected in the receipt; the runner string is left unchanged so the committed output stays bound to the executed runner hash",
    10: "major (shared with gap 4): decisions zip without length check -> fixed; fix-round rerun reconciles with every mutation detected",
    11: "major: preregistered slippage case replaced by a per-share case without an addendum -> slippage case restored in a labelled fix round, per-share kept as an added arm; major: fills not checked for instrument/time -> checks and mutation self-tests added",
}

ROUND2 = {
    4: "round-2: wrong-time fills (time of day) not detected -> exact fill times enforced, one-hour shift mutation added, fix round 2 reran",
    6: "round-2: time-of-day shift passed the risk probe -> exact 16:00 fill time enforced; fix round 2 reran with the shift mutation detected",
    10: "round-2: same exact-time fix as gap 4; fix round 2 reran",
    11: "round-2: 09:30 to 10:30 shift passed -> exact 09:30 fill time enforced; fix round 2 reran with the shift mutation detected",
    9: "round-2: single-run finding still unresolved -> outcome changed to advanced; runner label left unchanged (hash binding)",
}


ROUND3 = {
    1: "minor: committed runner hash was not the runner of the attempt-2 empyrical-reloaded/quantstats outputs -> fix round 3 reran all three libraries with the committed runner (902d15ef...); every output is byte-identical to the committed file",
    4: "major: dividend arm had no mutation or fee self-tests although fix round 2 claimed a time-shift mutation -> fix round 3 added 12 mutations and a fee perturbation to the dividend runner, reran, all detected, economics identical; the fix-round-2 note is corrected; minor: stale 'moved to settled' limit removed",
    5: "minor: a new driver is an equivalent substitute for 'run evaluate.py once', not a stronger check -> outcome downgraded to advanced; no rescoring (the preregistration forbids a second scoring of the window)",
    11: "minor: '1300 episodes ran in native Nautilus' overclaimed -> 905 invested episodes (4 candidates) reached the engine; cash's 260 had no legs; README and limits corrected",
    14: "minor: LEAN arm was labelled covered by the peer's SPY fixture -> relabelled 'not run (executable here)'; outcome stays deferred on the Alpaca broker arm",
}

ROUND4 = {
    1: "minor: next_check step 1 (venv-libs) and the venv-lock/venv-nautilus/skfolio-clone setup ran 06:30:05Z-06:30:31Z, before the 06:32:44Z preregistration, with no timestamps or creation record -> setup timestamps added from file birth times, post-hoc package-set provenance committed under raw/setup (creation commands of venv-lock and venv-nautilus not retained), README corrected; minor: checked_at moved to the fix-round-3 reproduction it relies on; the NoCash deviation note now states the settled criteria do not depend on the constraint set",
    2: "minor: result recorded only in a new wave receipt -> a dated later_checks entry in blueprints/us-equities/research-evaluation/receipt.json now records the comparison result and links this receipt; its historical independent_review block is left unchanged",
    9: "minor: project-authored matched runner labelled native_proven -> relabelled local_integration",
    11: "minor: dividend-inclusive episodes were feasible and not run -> fix round 4 ran them natively with the vendored DistributionModule (all 4 invested candidates reconcile; credited cash equals the cent-rounded estimate exactly); outcome stays advanced on financing and fill/liquidity realism",
    14: "major: the LEAN arm was executable here and was skipped -> fix round 4 ran it in native LEAN: fills, decisions, cash sequence, fees, dividend credits and ending cash equal the Nautilus reports exactly for both optimizers with and without dividends; the fee-2 control and all mutations were detected; outcome deferred -> advanced, Alpaca paper arm deferred to sota-workflow-resolution",
}

ROUND4_CODEX = {
    4: "not raised for gap 4, applied from the gap 11 finding: the dividend arm's own check compares account balances, not timestamps -> disclosed in limits; the gap 14 LEAN comparison checked every account timestamp of this run (16:00 fills, 00:00 dividend instants) against LEAN",
    11: "P2: dividend reconciliation ignored account-row and emission timestamps (a row shifted to 01:00 passed) -> timestamps compared, 2 timestamp mutations added, review rerun fix4b with identical economics",
    14: "P2: a failed or internally inconsistent control could count as a cross-engine detection -> LEAN-internal and cross-engine checks separated, broken-control self-tests added, compare rerun (fix4b); P3: receipt claimed 1,476 mounted files but run.json records 1,465 -> count generated from run.json",
}


def load(rel):
    return json.loads((ROOT / rel).read_text())


def artifacts(*paths):
    out = []
    for rel in paths:
        p = ROOT / rel
        files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
        for f in files:
            out.append({"path": str(f.relative_to(ROOT)), "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
    return out


def fill():
    r0 = load(f"{RAW}/0/cpcv-results.json")
    r1 = {k: load(f"{RAW}/1/{k}.json") for k in ("cvxportfolio", "empyrical-reloaded", "quantstats")}
    r3 = load(f"{RAW}/3/compare.json")
    r9 = load(f"{RAW}/9/matched-results.json")
    n410 = load(f"{RAW}/4-10/nautilus-run-fix2/summary.json")
    n4 = load(f"{RAW}/4/nautilus-dividends-run-fix3/summary.json")
    n6 = load(f"{RAW}/6/nautilus-risk-run-fix2/summary.json")
    r5 = load(f"{RAW}/5/scoring-run/results.json")
    n11 = load(f"{RAW}/11/nautilus-episodes-run-fix2/summary.json")
    n11d = load(f"{RAW}/11/nautilus-episodes-dividends-run-fix4b/summary.json")
    lp = load(f"{RAW}/14/lean-parity-compare-fix4b.json")
    mismatch = {row["artifact"]: row["status"] for row in r3["rows"] if row["status"] != "match"}
    lw = r0["arms"]["meanrisk_empiricalprior_ledoitwolf"]
    sc = r0["arms"]["meanrisk_empiricalprior_shrunkcovariance"]
    m9 = r9["series"]
    mr, hrp = n410["optimizers"]["meanrisk_min_variance"], n410["optimizers"]["hrp_variance"]
    return {
        0: {
            "commands": [
                {"cmd": f"cd $REPO && {VL} {BP}/gap0_cpcv.py --out {RAW}/0/cpcv-results.json", "exit": 0,
                 "started_utc": "2026-09-23T06:35:15Z", "stdout_sha256_line": "8ecb70aba555aff3b3b5504e34b3ee97c0f6fb3956afe01d1b42545ba3f1ba86"}],
            "results": {
                "cv": r0["cv"], "development_observations": r0["development_observations"],
                "ledoitwolf": {k: lw[k] for k in ("cpcv_paths", "cpcv_sharpe_mean", "cpcv_sharpe_std", "fitted_covariance_estimator", "fitted_shrinkage", "reserved_weights")},
                "shrunkcovariance": {k: sc[k] for k in ("cpcv_paths", "cpcv_sharpe_mean", "cpcv_sharpe_std", "fitted_covariance_estimator", "fitted_shrinkage", "reserved_weights")},
                "cpcv_path_observations_each": lw["cpcv_path_observations"][0],
                "inputs_unchanged": r0["inputs_unchanged"],
                "results_sha256": hashlib.sha256((ROOT / f"{RAW}/0/cpcv-results.json").read_bytes()).hexdigest(),
                "criteria_check": "a) n_splits 45, n_test_paths 9, 9 paths per arm; b) fitted covariance estimators LedoitWolf (shrinkage_ recorded) and ShrunkCovariance; c) reserved weights finite, non-negative, sum 1; d) inputs unchanged; e) results committed with hash."},
            "outcome": "settled", "evidence_class": "native_proven",
            "limits": ["Same three ETFs and raw close-to-close returns as the original receipt; CPCV path Sharpe values are descriptive, not a skill claim.",
                       "embargo_size 0 was preregistered; the 6-row purge matches the plan's label horizon.",
                       "One run; no repeat was needed for the preregistered structural criteria."],
            "raw": [f"{RAW}/0", f"{BP}/gap0_cpcv.py", f"{BP}/common.py"],
            "checked_at": "2026-09-23T06:35:15Z"},
        1: {
            "commands": [
                {"cmd": "(setup, creation command not retained) uv venv $CACHE/venv-lock and $CACHE/venv-nautilus", "exit": 0,
                 "started_utc": "venv-lock 2026-09-23T06:30:05Z, venv-nautilus 06:30:13Z (directory birth times; before the 06:32:44Z preregistration)",
                 "provenance": "post-hoc (fix round 4): venv-lock's package set equals the pins of blueprints/us-equities/research-evaluation/requirements.lock and venv-nautilus's equals the accepted tools/nautilus-2.0.0rc5 install (raw/setup/package-set-comparison.txt); whether --require-hashes was used for these two is not recorded"},
                {"cmd": f"uv pip compile {BP}/requirements-libs.in --python $PY3_13_15 --generate-hashes --no-header --output-file {BP}/requirements-libs.lock", "exit": 0,
                 "started_utc": "about 2026-09-23T06:30:20Z (lock file mtime; exact start not captured; before the preregistration)"},
                {"cmd": f"uv venv --python $PY3_13_15 $CACHE/venv-libs && uv pip sync --python $CACHE/venv-libs/bin/python --require-hashes {BP}/requirements-libs.lock", "exit": 0,
                 "started_utc": "2026-09-23T06:30:25Z (venv birth time; libs-sync.stderr written 06:30:26Z; before the preregistration)",
                 "output": "raw/setup/libs-sync.stderr.txt",
                 "network_downloads": "scs 41.2MiB, curl-cffi 12.9MiB, highspy 4.8MiB, cvxpy 4.2MiB from pypi.org (other wheels from the local uv cache)"},
                {"cmd": f"env HOME=$CACHE/tmphome {VB} {BP}/gap1_libs.py --lib <lib> --out {RAW}/1/<lib>.json --workdir $CACHE/g1-work-<lib>",
                 "attempt_1_utc": "2026-09-23T06:36:16Z", "attempt_1_exit": {"cvxportfolio": 1, "empyrical-reloaded": 1, "quantstats": 1},
                 "attempt_1_cause": "temporary HOME broke the default LEAN path (FileNotFoundError before any library call); stderr kept in raw/1/attempt-1-failed",
                 "attempt_2_utc": "2026-09-23T06:36:28Z", "attempt_2_exit": {"cvxportfolio": 0, "empyrical-reloaded": 0, "quantstats": 0},
                 "attempt_3_utc": "2026-09-23T06:36:54Z", "attempt_3": "cvxportfolio only, exit 0, after relabelling result.volatility (per-period) and adding result.annualized_volatility; attempt-2 output kept in raw/1/attempt-2-mislabelled",
                 "runner_binding_note": "empyrical-reloaded and quantstats outputs come from attempt 2, before the attempt-3 edit; the pre-edit runner was not retained. Fix round 3 below binds them to the committed runner by reproduction."},
                {"cmd": f"for lib in cvxportfolio empyrical-reloaded quantstats; do env HOME=$CACHE/tmphome {LEAN} {VB} {BP}/gap1_libs.py --lib $lib --out {RAW}/1/fix3-rerun/$lib.json --workdir $CACHE/g1-fix3-work-$lib; done",
                 "exit": {"cvxportfolio": 0, "empyrical-reloaded": 0, "quantstats": 0}, "started_utc": "2026-09-23T07:32:01Z",
                 "purpose": "fix round 3 (preregistered 07:31:52Z): rerun with the committed runner gap1_libs.py sha256 902d15efbf4dc04a383bed5d9f8193ae052c4e5e9051ccd5527c634faad5bcef and common.py sha256 0fe887db31f6cc437129b90aea0d83380b322c5bbde35179b336b8763e6c00cb",
                 "byte_identical_to_committed": {"cvxportfolio": "5b5c1b7a35f1eb98648248b9c3edc96f5ea37482e3fcc90272595976dde7ccbd",
                                                 "empyrical-reloaded": "4dd2c430accf3a3217324367662865536954d15aec4f880c5117ca40340fd756",
                                                 "quantstats": "aad9d74592c89b4bc4fd2dcbd55ae1f84fee9cc06630771f922c91d3e01f339e"},
                 "detection": "per-file sha256 comparison; the retained attempt-2 cvxportfolio.json (sha256 cf369c13...) differs from the final file, so the comparison can report a difference"}],
            "results": {k: {"version": v["version"], "result": v["result"]} for k, v in r1.items()},
            "outcome": "settled", "evidence_class": "native_proven",
            "limits": ["cvxportfolio is exercised as a minimum-variance SinglePeriodOptimization and a cost-free MarketSimulator backtest on user-provided forward-aligned returns; its transaction/holding cost models and data downloads are not exercised.",
                       "empyrical-reloaded and quantstats compute metrics on the equal-weight development series only; quantstats reports/tear sheets are not generated.",
                       "cvxportfolio is GPL-3.0; adoption is not decided here.",
                       "Disclosed deviation (found by the independent review): the preregistration named LongOnly plus LeverageLimit(1); the runner used LongOnly plus NoCash (full investment) because a pure minimum-variance objective that may hold cash is trivially all cash. No amendment was written before the run. The settled criteria (each pinned library installs hash-locked, runs on the frozen returns, exits 0 and its outputs are recorded) do not depend on the constraint set; the minimum-variance weights reported are for LongOnly plus NoCash only.",
                       "Runner binding (Opus review, fix round 3): the attempt-2 empyrical-reloaded and quantstats outputs were produced by a pre-edit runner that was not retained; the committed runner reproduces all three outputs byte for byte, which binds the committed outputs to it by reproduction, not by the original execution.",
                       "Order of setup (second Opus review, fix round 4): the first step of the next_check (create the pinned venv) and the lock compile ran at about 06:30:20-06:30:26Z, before the 06:32:44Z preregistration; the preregistration therefore preceded the library runs, not the environment setup. Setup timestamps come from file birth/modify times (raw/setup/setup-timeline.txt)."],
            "raw": [f"{RAW}/1", f"{RAW}/setup", f"{BP}/gap1_libs.py", f"{BP}/requirements-libs.in", f"{BP}/requirements-libs.lock"],
            "checked_at": "2026-09-23T07:32:01Z (start of the fix-round-3 reproduction the receipt relies on; library runs first executed 06:36:16Z-06:36:54Z)"},
        2: {
            "commands": [
                {"cmd": "git clone --filter=blob:none --no-checkout https://github.com/skfolio/skfolio $CACHE/skfolio-src", "exit": 0},
                {"cmd": f"bash {BP}/gap2_hash_compare.sh > {RAW}/2/hash-compare.txt", "exit": 0},
                {"cmd": "(fix round 4) add a dated later_checks entry with the comparison result and a link to this receipt to blueprints/us-equities/research-evaluation/receipt.json",
                 "exit": 0, "started_utc": "2026-09-23T16:09:34Z", "note": "additive field only; the historical independent_review block is unchanged"}],
            "results": {"installed_sha256": "f85cbe8b5a3ff4705a7ab6d35eacdbfafc11b09ec3cc1458fd4a2cf98c563397",
                        "receipt_walkforward_source_sha256": "f85cbe8b5a3ff4705a7ab6d35eacdbfafc11b09ec3cc1458fd4a2cf98c563397",
                        "git_show_c99fcf71_sha256": "f85cbe8b5a3ff4705a7ab6d35eacdbfafc11b09ec3cc1458fd4a2cf98c563397",
                        "c99fcf71_is_tag": "v1.2.9", "comparison": "installed == receipt == upstream c99fcf71 (byte-identical, diff reports identical)",
                        "negative_control": "git show b500f88~1 file sha256 0a881afb... differs; diff against the installed file is 8 lines, so the comparison can report a mismatch",
                        "v1_3_0_same_file": True},
            "outcome": "settled", "evidence_class": "source_review",
            "limits": ["Recording (second Opus review, fix round 4): the comparison result is now recorded in the original receipt as blueprints/us-equities/research-evaluation/receipt.json later_checks[0] (added 2026-09-23T16:09:34Z, linking this receipt). Its independent_review block describes the original review and is left unchanged; the later check was reviewed in this wave's Codex rounds 1-2 and the Opus review, which reproduced two of the three hashes. Round 1 (before fix round 4) recorded the result only in this receipt.",
                       "Hashing checks byte identity of one source file, not the rest of the installed distribution."],
            "raw": [f"{RAW}/2", f"{BP}/gap2_hash_compare.sh", "blueprints/us-equities/research-evaluation/receipt.json"],
            "checked_at": "2026-09-23T06:33Z (exact second not captured; between the 06:32:48Z preregistration commit and the 06:33:39Z gap 3 start)"},
        3: {
            "commands": [{"cmd": f"bash {BP}/gap3_rerun.sh $CACHE/g3-wave", "exit": 0, "started_utc": "2026-09-23T06:33:39Z",
                          "step_exits": {"compile": 0, "compile-final": 0, "venv": 0, "sync-final": 0, "check": 0, "freeze": 0, "run-1": 0}},
                         {"cmd": f"python3 {BP}/gap3_compare.py $CACHE/g3-wave > {RAW}/3/compare.json", "exit": 0}],
            "results": {"counts": r3["counts"], "non_matching": mismatch, "reconstruction": r3["semantic"],
                        "scoring_artifacts": "candidate-ledger.json, 21 selection files, run-1.stdout.txt and run-1.stderr.txt match the retained sha256 byte for byte; freeze.json and results.json reproduce the retained hashes exactly after substituting the retained public frozen_utc (and the resulting freeze hash), so all 26 run-1 artifacts are reproduced",
                        "setup_logs": "venv/sync-final/check/freeze/compile-final stderr differ only in host paths and timings; the initial DuckDB compile input is unknown (guess differs); api stdout/stderr and the first sync were not regenerated because their commands are not recorded",
                        "regenerated_artifacts_committed": f"{RAW}/3/regenerated (ledger stored uncompressed, sha256 08ea5309... equal to the retained hash; setup logs with $HOME substitution; see raw/REDACTIONS.json)"},
            "outcome": "advanced", "evidence_class": "local_integration",
            "limits": ["Remaining (why advanced, per the independent review): 4 of the 42 retained entries (setup/api.stdout, setup/api.stderr, setup/sync.stdout, setup/sync.stderr) have no recorded command and were not regenerated, so they remain private; of the 7 setup-log mismatches, 5 are host-path/timing text (venv, sync-final, check, freeze stderr; compile-final stderr timing) and 2 (initial compile stdout/stderr) come from an unknown DuckDB-era input. Every scoring artifact (ledger, 21 selections, results, freeze, stdout, stderr) is reproduced and committed.",
                       "This replay re-scores inspected evidence; it does not reset the 2021Q1 reserved segment's status."],
            "raw": [f"{RAW}/3", f"{BP}/gap3_rerun.sh", f"{BP}/gap3_compare.py", f"{RAW}/review"],
            "checked_at": "2026-09-23T06:33:39Z"},
        4: {
            "commands": [
                {"cmd": f"{VL} {BP}/weights_export.py --out {RAW}/4-10/skfolio-fold-weights.json", "exit": 0},
                {"cmd": f"{LEAN} {VN} {BP}/nautilus_portfolio.py --weights {RAW}/4-10/skfolio-fold-weights.json --out {RAW}/4-10/nautilus-run --self-test-fee-perturbation",
                 "exit": 0, "started_utc": "2026-09-23T06:41:44Z", "note": "round 1 dividend-free arm (shared with gap 10); outputs removed from the tree after the fix round, retained in git at b482b86"},
                {"cmd": f"{LEAN} {VN} {BP}/nautilus_portfolio.py --weights {RAW}/4-10/skfolio-fold-weights.json --out {RAW}/4-10/nautilus-run-fix1 --self-test-fee-perturbation",
                 "exit": 0, "started_utc": "2026-09-23T07:12:14Z", "note": "fix round 1: decision-count check and mutation self-tests added; identical economic results; outputs in git at 8bab001"},
                {"cmd": f"{LEAN} {VN} {BP}/nautilus_portfolio.py --weights {RAW}/4-10/skfolio-fold-weights.json --out {RAW}/4-10/nautilus-run-fix2 --self-test-fee-perturbation",
                 "exit": 0, "started_utc": "2026-09-23T07:22:10Z", "note": "fix round 2 (07:22Z, after the round-2 review): exact 16:00/09:30 New York fill times enforced and a one-hour time-shift mutation added; economic results identical to fix round 1; fix-round-1 outputs retained in git at 8bab001"},
                {"cmd": f"{LEAN} {VN} {BP}/nautilus_portfolio_dividends.py --weights {RAW}/4-10/skfolio-fold-weights.json --out {RAW}/4/nautilus-dividends-run-fix2",
                 "exit": 0, "started_utc": "2026-09-23T07:22:11Z", "note": "dividend-inclusive arm, fix round 2 (07:22Z, after the round-2 review): exact 16:00 New York fill times enforced. Correction (Opus review): this runner had no mutation self-test and no fee perturbation at fix round 2, so the round-2 time-shift criterion was not met for this arm until fix round 3. Outputs retained in git at dbcfef1."},
                {"cmd": f"{LEAN} {VN} {BP}/nautilus_portfolio_dividends.py --weights {RAW}/4-10/skfolio-fold-weights.json --out {RAW}/4/nautilus-dividends-run-fix3",
                 "exit": 0, "started_utc": "2026-09-23T07:32:41Z", "note": "dividend-inclusive arm, fix round 3 (preregistered 07:31:52Z, after the Opus review): checks moved into one function with explicit denial and flat-end checks; 12 mutation self-tests and a ledger fee +0.01 USD perturbation, each required to be detected (the runner exits non-zero otherwise). Economic summary identical to fix round 2; account.csv, modules.json and decisions.json byte-identical, fills.csv and positions.csv identical after UUID redaction."},
                {"cmd": f"{LEAN} {VN} {BP}/nautilus_portfolio_dividends.py --weights {RAW}/4-10/skfolio-fold-weights.json --out {RAW}/4/nautilus-dividends-run",
                 "exit": 0, "started_utc": "2026-09-23T06:49:18Z", "note": "first dividend-inclusive run; outputs in git at 8bab001",
                 "development_attempts": "attempt 1 exit 1: 63 late_module_emission errors (no engine timestamp at 00:00 ex instants); attempt 2 exit 1: ledger ordered same-instant distributions by asset name while the venue applies them in module order (detected by the transition check); attempt 3 reconciled; see raw/4/development-attempts/NOTE.txt"}],
            "results": {
                "dividend_free_arm": {k: {x: v[x] for x in ("orders", "fees_usd", "ending_cash_native", "ending_cash_ledger", "total_pnl_usd", "cash_transitions_matched", "decisions_matched", "unmodelled_dividend_cash_usd", "positions_realized_pnl_sum")} for k, v in n410["optimizers"].items()},
                "fee_perturbation_self_test_detected": {k: bool(v["detected"]) for k, v in n410["self_test"].items()},
                "dividend_inclusive_arm": {k: {x: v[x] for x in ("fills_matched", "account_transitions_matched", "distribution_credits", "nonzero_distribution_credits", "dividend_cash_usd", "fees_usd", "ending_cash_native", "ending_cash_ledger", "total_pnl_usd", "native_total_return", "decisions_matched", "open_positions", "final_shares")} for k, v in n4["optimizers"].items()},
                "vendored_distribution_module": n4["vendored_distribution_module"],
                "addendum_criteria_check": "both optimizers exit 0, zero module errors, emissions equal ledger credits, every account transition (fills and distributions) and decision equity equal the ledger, flat at the end",
                "fix_round_mutation_self_tests_detected": {k: {m: bool(x) for m, x in v.items()} for k, v in n410["mutation_self_tests"].items()},
                "dividend_arm_mutation_self_tests_detected_fix3": {k: {m: bool(x) for m, x in v.items()} for k, v in n4["mutation_self_tests"].items()},
                "dividend_arm_mutation_detection_messages_fix3": n4["mutation_self_tests"],
                "dividend_arm_fee_perturbation_detected_fix3": {k: v["detected"] for k, v in n4["self_test"].items()}},
            "outcome": "advanced", "evidence_class": "local_integration",
            "limits": ["Remaining (why advanced, per the independent review): the gap text also names financing and liquidity; this run is a long-only CASH account with no financing model exercised, and fills are at the raw close with unlimited modelled depth (no partial fills, spread or impact).",
                       "Timestamp coverage (applied from the Codex round-4 finding on gap 11): the dividend arm's own check compares account balances and emission ex-dates, not account-row or emission timestamps. The gap 14 LEAN comparison (raw/14/lean-parity-compare-fix4b.json) compared every account row of raw/4/nautilus-dividends-run-fix3 as (New York time, balance) against native LEAN, and all 16:00 fill rows and 00:00 dividend instants matched; that is the timestamp evidence for this run.",
                       "Committed Nautilus fills/positions CSVs had engine event UUIDs replaced by 'uuid-redacted' for publication (raw/REDACTIONS.json lists pre/post hashes); summary report_sha256 values refer to the pre-redaction CSVs.",
                       "The late addendum (written 2026-09-23T06:48:07Z, after the dividend-free results and before the dividend-inclusive arm) set a 'settled' criterion for the dividend arm; that criterion is met, but the outcome is advanced because the gap text also names financing and liquidity.",
                       "The dividend arm's checks were first mutation-tested in fix round 3 (07:32Z); the round-1 to round-2 dividend runs used the same comparisons without self-tests. Emission amounts are now compared as Decimal values rather than strings.",
                       "Distribution events come from the vendored peer module's derive_events (LEAN factor files); the ledger shares that derivation, so per-share amounts are cross-checked only through the peer's own accepted external check, not independently here.",
                       "Fills are retrospective at the raw daily close with unlimited modelled depth; no partial fills, spread, impact, halts or broker session rules.",
                       "Native position-level realized_pnl sums differ from the exactly reconciled cash P&L by 0.01 USD in the dividend-free arm (1009391.94 vs 1009391.95; 1279895.58 vs 1279895.57); account cash, fills and fees reconcile exactly.",
                       "Retained public LEAN sample data; not a point-in-time or broker-qualified dataset."],
            "raw": [f"{RAW}/4-10/skfolio-fold-weights.json", f"{RAW}/4-10/nautilus-run-fix2", f"{RAW}/4-10/development-run-1", f"{RAW}/4", f"{RAW}/review",
                    f"{BP}/weights_export.py", f"{BP}/nautilus_portfolio.py", f"{BP}/nautilus_portfolio_dividends.py", f"{BP}/vendored/distribution_module.py", f"{BP}/fix3_prereg.py"],
            "checked_at": "2026-09-23T07:32:43Z"},
        5: {
            "commands": [
                {"cmd": f"{LEAN} {VL} {BP}/gap5_extended.py --out $CACHE/g5-harness-test --harness-test-plan $CACHE/harness-test-plan.json", "exit": 0,
                 "note": "harness test on the already-inspected 2016-10..2017-09 development window before the frozen run; output kept in raw/5/harness-test"},
                {"cmd": f"{LEAN} {VL} {BP}/gap5_extended.py --out {RAW}/5/scoring-run", "exit": 0, "started_utc": "2026-09-23T06:44:25Z",
                 "note": "the single scoring run; driver and plan committed at 1c6d261 (06:44:20Z) before it"}],
            "results": {"selected_from_training": r5["selection"]["chosen"], "train": [r5["selection"]["train_first"], r5["selection"]["train_last"]],
                        "reserved": [r5["selection"]["test_first"], r5["selection"]["test_last"]],
                        "completed_episodes_per_candidate": {c: v["observed_episodes"] for c, v in r5["reserved_candidates"].items()},
                        "mean_net_cost_proxy_label": {c: v["mean_net_cost_proxy_label"] for c, v in r5["reserved_candidates"].items()},
                        "primary_test": r5["primary_test"], "secondary_wilcoxon": r5["secondary_wilcoxon"],
                        "secondary_per_candidate_vs_zero": r5["secondary_per_candidate_vs_zero"],
                        "not_used_by_broad_universe": "broad-universe protocol.json chronology starts its warm-up at 2016-01-04 (development 2017-2021, validation 2022-2023, reserved 2024-2026-08-14)",
                        "repository_scan": "rg over the repository found no SPY/QQQ/IWM use of 2012-10..2013-09; the only hits were FOXA/NWSA minute files in execution-realism inputs; the LEAN engine sample week 2013-10-07..11 lies after the window"},
            "outcome": "advanced", "evidence_class": "local_integration",
            "limits": ["Remaining (why advanced, per the Opus review): the next_check says 'run evaluate.py once'. evaluate.py's main() is hard-wired to plan.json, so its unchanged label/choose/summaries/check functions are imported by a new driver that re-implements panel loading, the anchor, the training index and episode selection. That is an equivalent substitute, not a stronger check. This window may not be scored again (the preregistration forbids a second scoring), so settling needs a plan-path-parameterised evaluate.py run once on a fresh unused window, or a preregistered equivalence proof of the driver against evaluate.py on already-inspected data.",
                       "The window precedes the development period (selector trained on 2011-09..2012-09); public bundled data is not demonstrated globally unseen, and only session dates (not prices) were counted before the freeze.",
                       "The primary test fails to reject (p=0.979); 49 non-overlapping five-session episodes per candidate on three ETFs cannot support an alpha, superiority or promotion claim.",
                       "Raw-price labels with the 20bp proxy; no dividends, fills or financing.",
                       "The frozen plan-extended.json inherited corporate_action_policy text naming 2014-01-02..2021-03-31 (stale copy); the executed check_auxiliary used the plan's data_start..reserved_end (2011-03-23..2013-09-30)."],
            "raw": [f"{RAW}/5", f"{BP}/gap5_extended.py", f"{BP}/plan-extended.json"],
            "checked_at": "2026-09-23T06:44:25Z"},
        6: {
            "commands": [{"cmd": f"{LEAN} {VN} {BP}/nautilus_risk.py --weights {RAW}/4-10/skfolio-fold-weights.json --out {RAW}/6/nautilus-risk-run-fix2",
                          "exit": 0, "started_utc": "2026-09-23T07:22:12Z", "fix_round_2": "fix round 2 (07:22Z, after the round-2 review): exact 16:00/09:30 New York fill times enforced and a one-hour time-shift mutation added; economic results identical to fix round 1; fix-round-1 outputs retained in git at 8bab001",
                          "fix_round": "after the independent review: rejections fail the probe, fills checked for instrument and date, full cash sequence compared, criteria a/c use actual fills, mutation self-tests added; round 1 (06:43:06Z, same criteria outcome) outputs retained in git at b482b86",
                          "development_attempts": "one earlier scratch run failed in the harness (fills report index not reset, KeyError client_order_id) after the engine had run; fixed with reset_index and rerun"}],
            "results": {"criteria": n6["criteria"], "limits": n6["limits"],
                        "limits_arm_denied": n6["arms"]["limits"]["denied"], "control_arm_denied": n6["arms"]["control"]["denied"],
                        "burst_filled": {"limits": n6["arms"]["limits"]["burst_filled"], "control": n6["arms"]["control"]["burst_filled"]},
                        "reconciliation": {a: v["reconciliation"] for a, v in n6["arms"].items()},
                        "mutation_self_tests_detected": {a: {m: bool(x) for m, x in v["mutation_self_tests"].items()} for a, v in n6["arms"].items()}},
            "outcome": "advanced", "evidence_class": "local_integration",
            "limits": ["Every preregistered criterion (a-e) passed, but the gap text also names broker reconciliation: positions reconcile against the simulated venue only. Broker-reported fill reconciliation needs the paper lane owned by peer session sota-workflow-resolution, so the outcome is advanced, not settled.",
                       "Submit-rate throttling is observed at backtest clock resolution (six orders at one timestamp); live-clock behaviour is not tested.",
                       "The known upstream test defect (bare matches! on denial variants) is unaffected; this run asserts the denial reason strings directly."],
            "raw": [f"{RAW}/6", f"{BP}/nautilus_risk.py", f"{RAW}/review"],
            "checked_at": "2026-09-23T07:22:12Z"},
        7: {
            "commands": [{"cmd": "git log origin/main -1 -- evidence/artifacts/sota-refresh-20260923/pins-runtime/skfolio.json; git show origin/main:evidence/artifacts/sota-refresh-20260923/pins-runtime/skfolio.json | sha256sum", "exit": 0, "output": "raw/7/citation-check.txt"}],
            "results": {"covered_by": "evidence/artifacts/sota-refresh-20260923/pins-runtime/skfolio.json (merged in #87, commit 43bb931 on origin/main)",
                        "cited_result": "skfolio 1.3.0 WalkForward optimizer acceptance rerun on the frozen inputs: verdict qualified, development Sharpe 0.778/0.846 and reserved weights reproduced to the 1.2.9 receipt's 3-decimal precision",
                        "this_unit_observation": "gap 2 found the WalkForward source file byte-identical between v1.2.9 (c99fcf71) and v1.3.0"},
            "outcome": "covered_elsewhere", "evidence_class": "source_review",
            "limits": ["The cited 1.3.0 install was an unlocked live PyPI resolve, not a --require-hashes install, and the research-evaluation README tag was not updated; both clauses remain with the SOTA refresh lane.",
                       "No check was run by this unit for this gap."],
            "raw": [f"{RAW}/7"], "checked_at": "2026-09-23T06:51:21Z"},
        9: {
            "commands": [{"cmd": f"env HOME=$CACHE/tmphome {LEAN} {VB} {BP}/gap9_matched.py --out {RAW}/9/matched-results.json --workdir $CACHE/g9-run/work",
                          "exit": 0, "started_utc": "2026-09-23T06:38:23Z",
                          "development_attempts": "two scratch dry runs before the preregistered run: the first failed at the skfolio max_drawdown call (TypeError) after weights were computed and before any metric was written; the second exited 0 and its output was deleted without being read"},
                         {"cmd": f"env HOME=$CACHE/tmphome {LEAN} {VB} {BP}/gap9_matched.py --out $CACHE/g9-determinism/out.json --workdir $CACHE/g9-determinism/work",
                          "exit": 0, "started_utc": "2026-09-23T07:13Z (approximate; exact second not captured)", "purpose": "fix round: determinism check requested by the independent review's single-run finding",
                          "output_sha256": "7170a4c548fcb9acf4ee6a172edcba1f8e584fe2afe0b7daf716fe10d320d4b1", "equals_preregistered_run_output": True}],
            "results": {"folds": len(r9["folds"]), "first_fold": {k: r9["folds"][0][k] for k in ("train_first", "train_last", "test_first", "test_last", "train_rows", "cvxportfolio_history_rows")},
                        "max_abs_weight_difference_skfolio_vs_cvxportfolio": r9["max_abs_weight_difference_skfolio_vs_cvxportfolio"],
                        "metrics": {s: {lib: v[lib] for lib in ("skfolio.measures", "empyrical-reloaded", "quantstats")} | {"observations": v["observations"], "total_compounded_return": v["total_compounded_return"]} for s, v in m9.items()},
                        "cross_library_notes": "volatility, Sharpe and max drawdown agree across skfolio.measures, empyrical-reloaded and quantstats to 4 decimals; annualized return differs by definition (arithmetic x252 vs CAGR) and Sortino differs in the 4th decimal (downside-deviation convention). Correction: the runner's conventions string calls quantstats CAGR calendar-year based; the retained value 0.13034584390844106 follows observation-count annualization (252/1252), per the independent review.",
                        "versions": r9["versions"]},
            "outcome": "advanced", "evidence_class": "local_integration",
            "limits": ["Evidence class (second Opus review, fix round 4): gap9_matched.py is a project-authored integration harness around the skfolio and cvxportfolio optimizers and three metric libraries, so the class is local_integration (was native_proven).",
                       "Why advanced (round-2 independent review): every arm of the next_check ran and the metrics are reported, but the preregistered single-execution condition was broken by a successful scratch dry run whose output was deleted unread; a later identical rerun cannot restore that condition. Remaining: a fresh preregistration whose first execution is the reported run.",
                       "Disclosed deviation from 'one preregistered run': a successful scratch dry run preceded it (output deleted unread). The script and common.py hashes were unchanged between that dry run and the preregistered run, nothing was tuned, and a fix-round rerun reproduced the preregistered output byte for byte (sha256 7170a4c5...), so no run could have been selected among differing results.",
                       "Optimizer candidates are skfolio and cvxportfolio (both minimum variance); empyrical-reloaded and quantstats participate as metric libraries on the same series, so 'common metrics per candidate' means per (series, metric library).",
                       "The cost proxy is the plan's 20bp per fully invested holding, charged once per fold; it is not turnover-based.",
                       "No winner, promotion or significance claim; equal weight had the highest Sharpe on this development span."],
            "raw": [f"{RAW}/9", f"{BP}/gap9_matched.py", f"{RAW}/review"],
            "checked_at": "2026-09-23T06:38:23Z"},
        10: {
            "commands": [{"cmd": f"{LEAN} {VN} {BP}/nautilus_portfolio.py --weights {RAW}/4-10/skfolio-fold-weights.json --out {RAW}/4-10/nautilus-run-fix2 --self-test-fee-perturbation",
                          "exit": 0, "started_utc": "2026-09-23T07:22:10Z", "fix_round_2": "fix round 2 (07:22Z, after the round-2 review): exact 16:00/09:30 New York fill times enforced and a one-hour time-shift mutation added; economic results identical to fix round 1; fix-round-1 outputs retained in git at 8bab001",
                          "history": "round 1 at 06:41:44Z (outputs in git at b482b86) and an earlier scratch run (development-run-1) gave identical economic results and a byte-identical account.csv; the fix round added the decision-count check and mutation self-tests"}],
            "results": {k: {"orders": v["orders"], "fees_usd": v["fees_usd"], "reconciled_total_pnl_usd": v["total_pnl_usd"],
                            "native_total_return": v["native_total_return"],
                            "skfolio_descriptive_total_return_daily_rebalanced_cost_free": v["skfolio_descriptive_total_return_daily_rebalanced_cost_free"],
                            "frictionless_fractional_buy_and_hold_total_return": v["frictionless_fractional_buy_and_hold_total_return"],
                            "cash_transitions_matched": v["cash_transitions_matched"], "fills_matched": v["fills_matched"]}
                        for k, v in n410["optimizers"].items()} | {
                "decomposition": "descriptive (daily rebalanced, cost free) -> fractional buy-and-hold within folds at the same rebalance closes isolates the rebalancing convention (and the 2020-12-31..2021-01-04 session skfolio skips); fractional -> native isolates integer shares, the 1% cash buffer and 1 USD fees",
                "span": "rebalance closes 2016-01-12 .. 2021-01-04, liquidation 2021-03-31 close; 20 development folds plus the reserved 2021Q1 weights",
                "mutation_self_tests_detected": {k: {m: bool(x) for m, x in v.items()} for k, v in n410["mutation_self_tests"].items()},
                "fee_perturbation_self_test_detected": {k: bool(v["detected"]) for k, v in n410["self_test"].items()}},
            "outcome": "settled", "evidence_class": "local_integration",
            "limits": ["Raw prices: dividends are not credited in this arm (unmodelled 132234.25 / 107478.79 USD); the dividend-inclusive version is gap 4's second arm.",
                       "Daily-close fills with unlimited modelled depth; not an execution-quality claim.",
                       "Position-level realized_pnl sums differ from the cash P&L by 0.01 USD (native rounding); cash, fills and fees reconcile exactly.",
                       "Descriptive, not a performance claim: no significance testing or promotion."],
            "raw": [f"{RAW}/4-10", f"{BP}/weights_export.py", f"{BP}/nautilus_portfolio.py", f"{RAW}/review"],
            "checked_at": "2026-09-23T07:22:10Z"},
        11: {
            "commands": [{"cmd": f"{LEAN} {VN} {BP}/nautilus_episodes.py --ledger {RAW}/3/regenerated/run-1/candidate-ledger.json.gz --out {RAW}/11/nautilus-episodes-run",
                          "exit": 0, "started_utc": "2026-09-23T06:46:18Z", "note": "round 1: fixed and per-share cases only (the preregistered slippage case was omitted); outputs in git at b482b86",
                          "development_attempts": "first scratch attempt failed constructing the strategy (Strategy.log is read-only); second scratch run exited 0 with economic results identical to round 1"},
                         {"cmd": f"gzip -n -9 -c {RAW}/3/regenerated/run-1/candidate-ledger.json > $CACHE/ledger-fix1.json.gz && {LEAN} {VN} {BP}/nautilus_episodes.py --ledger $CACHE/ledger-fix1.json.gz --out {RAW}/11/nautilus-episodes-run-fix1",
                          "attempt_1_utc": "2026-09-23T07:12:24Z", "attempt_1_exit": 1,
                          "attempt_1_cause": "the restored slippage case produced sub-cent notionals; the native USD account settles each fill rounded to the cent and the ledger did not, so the transition check failed (raw/11/fix1-attempt-1.stderr.txt)",
                          "attempt_2_utc": "2026-09-23T07:12:56Z", "attempt_2_exit": 0, "attempt_2_change": "ledger rounds each fill notional to the cent (half-even); fixed and per-share results unchanged; outputs in git at 8bab001"},
                         {"cmd": f"{LEAN} {VN} {BP}/nautilus_episodes.py --ledger $CACHE/ledger-fix1.json.gz --out {RAW}/11/nautilus-episodes-run-fix2",
                          "exit": 0, "started_utc": "2026-09-23T07:22:13Z", "note": "fix round 2 (07:22Z, after the round-2 review): exact 16:00/09:30 New York fill times enforced and a one-hour time-shift mutation added; economic results identical to fix round 1; fix-round-1 outputs retained in git at 8bab001"},
                         {"cmd": f"{LEAN} {VN} {BP}/nautilus_episodes_dividends.py --ledger {RAW}/3/regenerated/run-1/candidate-ledger.json --no-dividend-summary {RAW}/11/nautilus-episodes-run-fix2/summary.json --out $CACHE/episodes-dividends-attempt1",
                          "exit": 0, "started_utc": "2026-09-23T16:07:28Z", "finished_utc": "2026-09-23T16:07:29Z",
                          "note": "fix round 4 (preregistered 16:01:45Z, after the second Opus review): fixed-fee case with the vendored DistributionModule per instrument; first and only execution; outputs copied to raw/11/nautilus-episodes-dividends-run-fix4 (fills.csv engine UUIDs redacted afterwards, see raw/REDACTIONS.json)"},
                         {"cmd": f"{LEAN} {VN} {BP}/gap11_dividend_rounding_check.py {RAW}/3/regenerated/run-1/candidate-ledger.json $CACHE/episodes-dividends-attempt1/summary.json",
                          "exit": 0, "started_utc": "2026-09-23T16:07:49Z", "output": "raw/11/dividend-rounding-check.stdout.txt",
                          "purpose": "explain credited-minus-unmodelled: the earlier estimate used unrounded per-share amounts; with per-share rounded half-even to the cent it must equal the native credited cash exactly"},
                         {"cmd": f"{LEAN} {VN} {BP}/nautilus_episodes_dividends.py --ledger {RAW}/3/regenerated/run-1/candidate-ledger.json --no-dividend-summary {RAW}/11/nautilus-episodes-run-fix2/summary.json --out $CACHE/episodes-dividends-rerun1",
                          "exit": 0, "started_utc": "2026-09-23T16:34:25Z", "finished_utc": "2026-09-23T16:34:28Z",
                          "note": "fix-round-4 review rerun (preregistered 16:33:32Z in 81e1c86, after the Codex round-4 review finding 2): account rows compared as (timestamp, balance) and emission instants checked against 00:00 New York on each ex-date; 2 timestamp mutations added (8 per candidate, all detected); economic results identical to the first fix-round-4 run; outputs in raw/11/nautilus-episodes-dividends-run-fix4b (the reported results), first run kept in raw/11/nautilus-episodes-dividends-run-fix4"}],
            "results": {c: {"episodes": v["episodes"], "invested_episodes": v["invested_episodes"], "mean_gross_price_label": v["mean_gross_price_label"],
                            "mean_net_cost_proxy_label_20bp": v["mean_net_cost_proxy_label"], "unmodelled_dividend_cash_usd": v["unmodelled_dividend_cash_usd"],
                            "cases": {k: {x: y for x, y in cv.items() if x != "report_sha256"} for k, cv in v["cases"].items()}}
                        for c, v in n11["candidates"].items()} | {"financing": n11["financing"], "cases": n11["cases"],
                "dividends_fix4": {"case": n11d["case"], "distribution_events": n11d["distribution_events"],
                                   "candidates": {c: {k: v[k] for k in ("episodes", "orders", "account_rows", "distribution_credits", "nonzero_distribution_credits",
                                                                       "credited_dividend_cash_usd", "previously_reported_unmodelled_dividend_cash_usd",
                                                                       "credited_minus_unmodelled_usd", "total_pnl_usd", "fixed_case_total_pnl_without_dividends_usd",
                                                                       "mean_native_net_return_per_episode_with_dividends",
                                                                       "mean_native_net_return_per_episode_without_dividends",
                                                                       "dividend_contribution_per_episode", "alerts_fired")}
                                                  | {"mutation_self_tests_detected": {m: bool(x) for m, x in v["mutation_self_tests"].items()}}
                                                  for c, v in n11d["candidates"].items() if v.get("orders")},
                                   "cash_candidate": "no invested episode; engine not needed",
                                   "reported_run": "raw/11/nautilus-episodes-dividends-run-fix4b (timestamp-checked review rerun)",
                                   "rounding_check": "credited cash equals the unrounded-estimate recomputed with per-share rounded half-even to the cent, exactly, for all 4 candidates (raw/11/dividend-rounding-check.stdout.txt)",
                                   "inputs_unchanged": n11d["inputs_unchanged"]}},
            "outcome": "advanced", "evidence_class": "local_integration",
            "limits": ["The one-tick slippage case uses a 0.0001 USD tick (LEAN opens have sub-penny values), so its slippage is negligible; the per-share fee case was added without an amendment in round 1 and is labelled as an added arm in the fix-round addendum.",
                       "The round-1 command read raw/3/regenerated/run-1/candidate-ledger.json.gz; that gzip was later decompressed in place for publication (raw/REDACTIONS.json records both hashes; the decompressed ledger sha256 is 08ea5309...). Committed fills/orders files had engine event UUIDs replaced by 'uuid-redacted'; summary report_sha256 values refer to the pre-redaction CSVs.",
                       "Dividend clause (second Opus review, fix round 4): dividend-inclusive episode accounting now ran natively for the fixed-fee case of all 4 invested candidates with the vendored peer DistributionModule; every fill, module emission (amount, quantity, ex-date and emission instant) and account transition (timestamp and balance) reconciles and all 8 mutations per candidate were detected. The first fix-round-4 run compared balances only; the Codex round-4 review showed a dividend row shifted to 01:00 would have passed, so the review rerun added timestamp checks and two timestamp mutations, with identical economics. Only the fixed-fee case was run with dividends (not the slippage or per-share cases). Remaining: any financing model (rc5 has none for cash equities; financing is only declared zero for a long-only CASH account), and realistic fills, liquidity and capacity (synthetic open-print bars fill at the raw open with unlimited depth).",
                       "PerContractFeeModel uses 0.01 USD per share because USD Money has two decimals; it is an illustrative broker-like fee, not a quote.",
                       "Native effective cost versus the gross label is about 0.2-1.2 bp per episode against the 20bp proxy; this compares fee models, not execution quality.",
                       "Scope of native execution (Opus review): 905 invested episodes across 4 candidates (equalweight 260, momentum120 227, momentum20 206, momentum60 212) reached the engine in each case; the cash candidate's 260 episodes have no legs and were not run through the engine (0 orders)."],
            "raw": [f"{RAW}/11", f"{BP}/nautilus_episodes.py", f"{BP}/nautilus_episodes_dividends.py", f"{BP}/gap11_dividend_rounding_check.py", f"{RAW}/review"],
            "checked_at": "2026-09-23T16:34:25Z"},
        14: {
            "commands": [{"cmd": "git log origin/main -1 -- blueprints/us-equities/engine-nautilus/spy-parity/{receipt-v2,verdict-v2,dividend-module-receipt}.json; git show ... | sha256sum", "exit": 0, "output": "raw/14/citation-check.txt"},
                         {"cmd": f"python3 {BP}/lean_parity/run.py --lean-source $HOME/.local/share/codex-ecosystem/tools/lean-985ef30 --dotnet $HOME/.local/share/codex-ecosystem/tools/dotnet-equity10/dotnet --weights {RAW}/4-10/skfolio-fold-weights.json --out $CACHE/lean-parity-attempt1",
                          "exit": 0, "started_utc": "2026-09-23T16:03:50Z", "finished_utc": "2026-09-23T16:04:09Z",
                          "note": "fix round 4 (preregistered 16:01:45Z in 21899c4): first and only execution; 1 csc compile and 6 LEAN launcher runs (3 cases x 2 optimizers), each exit 0 inside Bubblewrap (no network, read-only engine/SDK/data, empty environment); every mounted engine/data file hash-unchanged (count in results, from run.json); outputs copied to raw/14/lean-parity-run with $HOME/host-name redaction (raw/REDACTIONS.json lean_parity_redacted), LEAN's >1 MB full result JSONs and the DLL listed with sha256 in raw/14/lean-parity-run/NOT_COPIED.json",
                          "output": ["raw/14/lean-parity-run.stdout.txt", "raw/14/lean-parity-run.stderr.txt", "raw/14/lean-parity-run/run.json"]},
                         {"cmd": f"python3 {BP}/lean_parity/compare.py --lean-out $CACHE/lean-parity-attempt1 --nautilus-base {RAW}/4-10/nautilus-run-fix2 --nautilus-dividends {RAW}/4/nautilus-dividends-run-fix3 --out $CACHE/lean-parity-attempt1-compare-dev.json",
                          "exit": 0, "started_utc": "2026-09-23T16:05Z (approximate; exact second not captured)", "output": "raw/14/lean-parity-compare-first-on-cache.json",
                          "note": "first comparison, on the cache copy"},
                         {"cmd": f"python3 {BP}/lean_parity/compare.py --lean-out {RAW}/14/lean-parity-run --nautilus-base {RAW}/4-10/nautilus-run-fix2 --nautilus-dividends {RAW}/4/nautilus-dividends-run-fix3 --out {RAW}/14/lean-parity-compare.json",
                          "exit": 0, "started_utc": "2026-09-23T16:06:06Z", "output": ["raw/14/lean-parity-compare.json", "raw/14/lean-parity-compare.stdout.txt"],
                          "note": "same comparison on the committed, redacted copy; every match, detection and mutation result is identical to the first comparison"},
                         {"cmd": f"python3 {BP}/lean_parity/compare.py --lean-out {RAW}/14/lean-parity-run --nautilus-base {RAW}/4-10/nautilus-run-fix2 --nautilus-dividends {RAW}/4/nautilus-dividends-run-fix3 --out {RAW}/14/lean-parity-compare-fix4b.json",
                          "exit": 0, "started_utc": "2026-09-23T16:33:57Z", "output": ["raw/14/lean-parity-compare-fix4b.json", "raw/14/lean-parity-compare-fix4b.stdout.txt"],
                          "note": "fix-round-4 review rerun (preregistered 16:33:32Z in 81e1c86, after the Codex round-4 review finding 1): LEAN-internal checks separated from cross-engine checks; the fee-2 control and each mutation count only when the internal checks pass and a cross-engine check raises; broken-control self-tests (runtime error injected, native fill inconsistent with the ledger) are not counted as detections. No LEAN rerun. These are the reported results."}],
            "results": {
                "lean_parity": {case: {key: ({"match": v["match"], **v["result"], "mutation_self_tests_detected": {m: bool(x) for m, x in v["mutation_self_tests"].items()}}
                                             if case != "control_fee2" else {"detected_as_mismatch": v["detected"], "difference": v["difference"][:240]})
                                       for key, v in d.items()} for case, d in lp["cases"].items()},
                "lean_parity_all_criteria_met": lp["all_criteria_met"],
                "broken_control_self_tests": {key: v["broken_control_self_tests"] for key, v in lp["cases"]["control_fee2"].items()},
                "mounted_engine_and_data_files_hash_unchanged": {"count": lp["lean_run"]["mounted_input_files"], "unchanged": lp["lean_run"]["mounted_inputs_unchanged"]},
                "lean_parity_summary": "Native LEAN 985ef30 and native NautilusTrader 2.0.0rc5 produce identical fills (time, asset, side, quantity, price, fee), rebalance decisions (equity and integer targets), cash sequences, total fees and ending cash for both optimizers: 2009391.95 / 2279895.57 USD without dividends and 2207656.15 / 2451556.98 USD with dividends (LEAN native raw-mode dividends versus the peer DistributionModule: 63 credits each, 138948.42 / 111669.90 USD). The fee-2 control is reported as a cross-engine mismatch with LEAN-internal checks passing, broken controls are not counted, and every mutation passes the LEAN-internal checks and is detected by a cross-engine comparison.",
                "alpaca_paper": "deferred: submitting Alpaca paper orders through Nautilus and reconciling broker fills is a broker-contact lane owned by sota-workflow-resolution; this unit makes no broker or paper-account call",
                "local_partial_input": "gap 6 shows RiskEngine notional and rate denials with simulated-venue reconciliation"},
            "outcome": "advanced", "evidence_class": "local_integration",
            "limits": ["Remaining (blocker named): the second arm of the next_check, Alpaca paper orders through Nautilus with RiskEngine limits and reconciliation of broker-reported fills, needs broker contact, which is reserved for peer session sota-workflow-resolution (owner). Broker-specific execution and deterministic pre-trade enforcement against a broker therefore remain open.",
                       "Declared LEAN conventions (preregistered): a project-authored close-fill model (FillModel subclass filling market orders at the triggering daily bar's close at 16:00 New York) replaces LEAN's default daily-order conversion to MarketOnOpen/MarketOnClose; orders are submitted with SubmitOrderRequest(OrderType.Market); margin account with leverage 1 and immediate settlement stands in for Nautilus's CASH account; no fill-forward. Parity is therefore shown for accounting under matched fill conventions, not for LEAN's default fill behaviour.",
                       "The no-dividend case hides LEAN's factor files with a tmpfs so LEAN emits no dividends (0 dividend rows observed); the dividend case uses LEAN's native raw-mode dividend credits and 63 dividend rows were observed per optimizer, so each case exercised what it claims.",
                       "Deviation from the preregistration: LEAN exposes cash to the algorithm only after all same-instant dividends are applied, so dividend cash is compared per ex-date instant (57 instants), while individual credits are compared by (ex-date, asset, quantity, amount); fills are compared per transition.",
                       "Evidence class local_integration: the C# algorithm, fill model, runner and comparison are project-authored; both engines are unmodified native builds. The LEAN build is the previously accepted patched 985ef30 engine.",
                       "Same 3 ETFs, daily bars and 22 decisions (21 fold rebalances plus the final liquidation) as gaps 4/10; no financing, borrowing, partial fills or liquidity limits are modelled in either engine."],
            "raw": [f"{RAW}/14", f"{BP}/lean_parity"], "checked_at": "2026-09-23T16:06:06Z"},
    }


def main():
    specs = fill()
    results = {}
    for path in sorted(EVID.glob("*.json")):
        if path.name == "results.json":
            continue
        receipt = json.loads(path.read_text())
        spec = specs[receipt["gap_index"]]
        receipt["independent_review"] = {
            "reviewer": "Codex CLI 0.155.1 (gpt-6-astra), codex exec --sandbox read-only --ephemeral, one bounded call",
            "record": ["evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw/review/codex-review-round1.md",
                       "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw/review/codex-review-round2.md"],
            "round_2": ROUND2.get(receipt["gap_index"], "no round-2 finding for this gap"),
            "findings_and_resolution": REVIEW.get(receipt["gap_index"], "no finding for this gap"),
            "round_3": {"record": "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw/review/opus-review-round3.json",
                        "resolution": ROUND3.get(receipt["gap_index"], "no round-3 finding for this gap")},
            "round_4": {"record": "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw/review/opus-review-round4.json",
                        "resolution": ROUND4.get(receipt["gap_index"], "no round-4 finding for this gap")},
            "round_4_codex": {"record": "evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw/review/codex-review-round4.md",
                              "reviewer": "Codex CLI (codex exec --sandbox read-only --ephemeral), one bounded call on commits 6ed9709..a4cbcf8",
                              "resolution": ROUND4_CODEX.get(receipt["gap_index"], "no finding for this gap")}}
        receipt.update(commands=spec["commands"], results=spec["results"], outcome=spec["outcome"],
                       evidence_class=spec["evidence_class"], limits=spec["limits"], checked_at=spec["checked_at"],
                       raw_artifacts=artifacts(*spec["raw"]))
        path.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    for path in sorted(EVID.glob("*.json")):
        if path.name == "results.json":
            continue
        receipt = json.loads(path.read_text())
        results[str(receipt["gap_index"])] = {"outcome": receipt["outcome"], "receipt": str(path.relative_to(ROOT))}
    ordered = {k: results[k] for k in sorted(results, key=int)}
    (EVID / "results.json").write_text(json.dumps({"catalog": "us-equities", "layer_id": "portfolio-risk",
                                                    "generated_from": "receipt outcome fields by finish_receipts.py",
                                                    "results": ordered}, indent=2) + "\n")
    print(json.dumps({k: v["outcome"] for k, v in ordered.items()}))


if __name__ == "__main__":
    main()
