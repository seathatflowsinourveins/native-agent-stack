# Independent review round 1 (Codex CLI 0.155.1, model gpt-6-astra, codex exec --sandbox read-only --ephemeral, 2026-09-23)

Prompt:

    You are an independent read-only reviewer. Repository: the current directory (branch claude/g2-portfolio-risk-20260923, base 41d39b3). Review ONLY:
    - evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/ (12 receipts *.json, results.json, README.md, raw/)
    - blueprints/gap-wave2-20260923/us-equities__portfolio-risk/ (runner scripts)
    Each receipt has gap_text, next_check, preregistration, commands, results, outcome, limits. Rules the receipts must obey:
    1. "settled" only if every arm of next_check (or a stronger check) was executed AND the evidence closes every clause of gap_text; otherwise "advanced" naming what remains.
    2. Preregistration written_at precedes results; late addenda labelled.
    3. Each probe reported as passing must be able to detect the failure it rules out.
    4. results.json must equal receipt outcomes.
    5. Claims in results/limits must match the raw outputs they cite (check numbers against raw/ files).
    Look for: overclaimed outcomes, numbers that do not match raw files, reconciliation logic in the runner scripts that could pass vacuously (e.g. comparisons that are always true, checks skipped), leakage across train/test boundaries in gap0_cpcv.py, gap9_matched.py, weights_export.py, gap5_extended.py, and accounting errors in nautilus_portfolio.py, nautilus_portfolio_dividends.py, nautilus_risk.py, nautilus_episodes.py.
    Raw files were decompressed and engine UUIDs redacted after the runs (raw/REDACTIONS.json).
    Do not run heavy commands; reading files and small python/json inspections are fine. Output a concise list of findings, each with severity (blocking/major/minor), file:line or JSON path, and the evidence. If none, say so.

Final message:

- **Major — Missing decisions still “reconcile.”** [nautilus_portfolio.py:233]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_portfolio.py:233) uses `zip` without checking lengths, then reports the expected snapshot count. Removing every decision from the retained HRP data still passes and reports **22 decisions matched**.

- **Major — Risk checks can report fills that never occurred.** [nautilus_risk.py:188]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_risk.py:188) treats absence of `OrderDenied` as proof that targets/control orders filled. Rejected orders are excluded from reconciliation at lines 127–128, so rejection can satisfy these purported positive controls.

- **Major — Intermediate cash errors escape reconciliation.** [nautilus_risk.py:141]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_risk.py:141) checks only initial cash, final cash and row count. An in-memory **$12,345.67** corruption of the first retained limits-arm cash transition still passes.

- **Major — Wrong-instrument/time fills escape detection.** [nautilus_episodes.py:142]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_episodes.py:142) omits instrument and timestamp comparisons; `nautilus_risk.py:136` has the same omission. Changing a retained episode fill from `SPY.SIM` in 2016 to `WRONG.SIM` in 1900 still passes episode reconciliation.

- **Major — Gap 4 overclaims closure.** [4-nautilus-weights-accounting.json:114]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/4-nautilus-weights-accounting.json:114) declares `settled`, although `gap_text` includes liquidity and `limits[3]` explicitly retains unlimited depth without partial fills, spread or impact. Under rule 1, this remains `advanced`.

- **Major — Gap 3 overclaims completeness and mismatch explanations.** [3-evaluate-rerun-hash-compare.json:82]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/3-evaluate-rerun-hash-compare.json:82) declares `settled` despite four unregenerated artifacts. Its limit calls all seven setup mismatches path/timing differences, while `results.setup_logs` admits the original compile input is unknown. The scoring reproduction succeeds, but full closure remains unsupported.

- **Major — Gap 9 violates its single-run criterion.** [9-matched-four-candidate-runner.json:19]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/9-matched-four-candidate-runner.json:19) records an earlier successful execution whose output was deleted, plus a failed attempt. Calling the successful output unread does not establish the preregistered single-run condition supporting `settled`.

- **Major — Gap 11 silently replaces a preregistered arm.** [11-nautilus-study-episodes-fees.json:11]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/11-nautilus-study-episodes-fees.json:11) requires fixed fees and fixed fees plus `OneTickSlippageFillModel`. The runner/raw results instead use fixed and per-share fees, without a labelled addendum; the specified slippage arm remains unexecuted.

- **Minor — Gap 1 changes optimization constraints without recording an amendment.** [gap1_libs.py:41]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/gap1_libs.py:41) uses `NoCash`; the receipt preregisters `LeverageLimit(1)`. Full investment changes the feasible set from one permitting cash.

- **Minor — Annualization convention is mislabeled.** [gap9_matched.py:80]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/gap9_matched.py:80) describes quantstats CAGR as calendar-year based. The retained value **0.13034584390844106** exactly follows observation-based annualization with `252/1252`; calendar-span annualization gives approximately **0.1303010059**.

- **Minor — Extended-plan policy dates are stale.** [plan-extended.json:42]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/plan-extended.json:42) specifies corporate-action checks over 2014–2021, whereas the experiment and executed checks cover 2011–2013.

No concrete train/test leakage was found. All 12 outcomes match `results.json`, and all 170 listed artifact hashes verify.