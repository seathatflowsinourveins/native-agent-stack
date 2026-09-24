# Independent review round 2 (Codex CLI 0.155.1, model gpt-6-astra, codex exec --sandbox read-only --ephemeral, 2026-09-23)

Prompt:

    You are an independent read-only reviewer (round 2). Repository: current directory, branch claude/g2-portfolio-risk-20260923. A first review (evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/raw/review/codex-review-round1.md) raised findings; commits b6e9e30 and 397db4d claim to resolve them. Verify ONLY whether each round-1 finding is actually resolved, using `git diff b482b86 397db4d -- blueprints/gap-wave2-20260923 evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/*.json evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/README.md` and the fix-round raw outputs (raw/4-10/nautilus-run-fix1, raw/6/nautilus-risk-run-fix1, raw/11/nautilus-episodes-run-fix1). Also check: results.json equals receipt outcomes; outcomes marked settled close every clause of gap_text; preregistration written_at and fix_round_addendum timestamps precede the results they govern. Do not run heavy commands. Output a concise list: each round-1 finding -> resolved / not resolved (with evidence), then any NEW blocking/major issue. If none, say so.

Final message:

1. **Missing decisions — resolved.** [Length checks now precede `zip`]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_portfolio.py:233). Both optimizers reconcile 22 decisions; removed, shortened and extended lists fail.

2. **False-positive risk fills — resolved.** [Rejections now fail reconciliation]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_risk.py:127), and controls require actual fills. Injected rejections and missing fills fail.

3. **Intermediate cash errors — resolved.** [The complete cash sequence is compared]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_risk.py:147). First- and middle-transition corruptions fail; retained limits/control runs reconcile 10/13 transitions.

4. **Wrong instrument/time — not resolved (major).** Wrong instruments and dates fail, but [risk]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_risk.py:138) and [episode]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_episodes.py:147) checks discard time of day. Moving risk fills from 16:00→15:00 passes both arms; moving episode fills from 09:30→10:30 passes all twelve cases. Actual retained fills have the expected times.

5. **Gap 4 overclaimed closure — resolved.** [Outcome is now `advanced`]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/4-nautilus-weights-accounting.json:139), explicitly retaining financing and liquidity gaps.

6. **Gap 3 completeness/mismatch claims — resolved.** [Outcome and limits are corrected]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/3-evaluate-rerun-hash-compare.json:82): `advanced`, four unregenerated artifacts, and two mismatches from unknown compile inputs.

7. **Gap 9 single-run criterion — not resolved (major).** [The receipt still declares `settled`]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/9-matched-four-candidate-runner.json:126). Disclosure and a matching later rerun cannot establish the original single-run condition or recover the deleted successful output.

8. **Gap 11 substituted arm — resolved.** [The slippage model is restored]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/nautilus_episodes.py:114), with a labelled addendum. All 2,850 slippage fills differ from corresponding fixed-arm fills by exactly one tick.

9. **Gap 1 constraint amendment — resolved as disclosure.** [The receipt explicitly records `NoCash` replacing `LeverageLimit(1)`]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/1-candidate-libs-execution.json:95), including that no advance amendment existed.

10. **Annualization label — not resolved in the runner (minor).** The receipt adds a correct explanation, but [the unchanged runner still emits “calendar years”]($HOME/code/nas-wt-g2-portfolio-risk/blueprints/gap-wave2-20260923/us-equities__portfolio-risk/gap9_matched.py:80).

11. **Extended-plan dates — resolved by documented erratum.** [The receipt identifies the stale frozen text and correct executed dates]($HOME/code/nas-wt-g2-portfolio-risk/evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/5-extended-reserved-significance.json:105); the runner uses `data_start..reserved_end`.

All **12 outcomes match `results.json`**. Gap 9 remains unsupported as settled; no additional unclosed `gap_text` clause was found among the other settled receipts. Recorded preregistration/addendum timestamps precede their governed runs, corroborated by commit ordering; raw outputs lack execution wall-clock timestamps.

**No new blocking or major issue.** Verification used file inspection and lightweight reconciliation replays, without engine reruns.