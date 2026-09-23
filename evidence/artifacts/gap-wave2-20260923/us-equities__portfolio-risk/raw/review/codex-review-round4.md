Three findings; the committed economic results reproduce.

1. **[P2] Failed controls can count as successful cross-engine detection** — [compare.py:216]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/lean_parity/compare.py:216). Any `ValueError` becomes `detected=True`, including failures before cross-engine comparison. Injecting a runtime error into both fee-2 controls—or making their native fills inconsistent with their LEAN ledgers—still produced exit `0` and `all_criteria_met=True`. Require successful completion and internal consistency before accepting a cross-engine mismatch. The committed controls correctly fail on the actual $2-versus-$1 fee difference.

2. **[P2] Dividend reconciliation ignores cash-credit timestamps** — [nautilus_episodes_dividends.py:176]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_episodes_dividends.py:176). Account reconciliation compares only balances; emission reconciliation also omits actual emission timestamps. Shifting the first nonzero dividend account timestamp from midnight to 01:00 passed for all four candidates. This cannot enforce the preregistered midnight credit convention. Compare timestamps alongside balances and validate emission instants. **The committed timestamps themselves are correct.**

3. **[P3] Receipt overstates the hashed input count** — [finish_receipts.py:340]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/finish_receipts.py:340). The generator and receipt 14 claim **1,476** mounted engine/data files; committed [run.json:6]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw/14/lean-parity-run/run.json:6) records **1,465**. Generate this count from the run record.

| Requested category | Assessment |
|---|---|
| Cross-engine comparison and controls | Finding 1. All four committed parity cases match; all 26 mutations fail at cross-engine comparisons while passing LEAN’s internal consistency check. |
| LEAN close-fill model and submission | **No findings.** The custom model, direct market submission, and accounting-only scope are accurately disclosed. |
| Receipt/README numbers | Finding 3. No other numerical discrepancies found; episode accounting, dividend rounding, and parity results reproduce. |
| Outcomes | **No findings.** 14/11 advanced, 1/2 settled, and 9 advanced `local_integration` are supported with the stated remaining checks. |
| Overclaim, timestamps, provenance | Finding 2 concerns validation coverage. No additional findings: preregistration precedes the recorded runs, and artifact/source hashes and new redaction records match. |

Verification used retained raw files and in-memory mutations. No engines were rerun and no files were modified.
