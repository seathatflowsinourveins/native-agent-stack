VERDICT: changes-needed

1. **should-fix — [decision record:439](<worktree>/docs/decisions/2026-09-27-prompt-audit-resolution.md:439): distinguish the configured turn limit from the returned count.**  
   The record says “at most 10 turns,” but [results-r3-compact.json:1021](<worktree>/evidence/artifacts/prompt-audit-20260927/x9-round3/results-r3-compact.json:1021) reports:
   ```text
   arm=c case=K5 exit=0 result_subtype=success num_turns=11
   ```
   The harness passes `--max-turns 10` at `run_arm_r3.sh:31`. **Fix:** say “configured with `--max-turns 10`” and note that one result reported 11 turns. Refresh the decision record’s manifest entry afterward.

No other concrete defect found in the requested scope.

Verified:

- X5b matches the operator’s paragraph byte for byte. `CLAUDE.md` contains the selected X9 text followed by main’s unchanged Compact Instructions.
- All six token-receipt rows match their source bytes, words, lines and SHA-256; installed `gpt-tokenizer 3.4.0` reproduces their token counts.
- X9 retally: **four valid votes for `g`**, confidences **0.91, 0.90, 0.60, 0.60**. Other checked figures agree with retained evidence.
- Lane A, `harness-defaults.md:7`, and the AN-13 row are consistent with their supporting files. The wait-setting description also matches the [official reference](https://code.claude.com/docs/en/env-vars).
- Privacy review covered 70 files; no private values or inventories found.
- All 152 required PR paths are registered correctly; no unrelated manifest entries changed.
- Dashboard signature and other source bounds remain unchanged. The new test fails against main’s reader. With the manifest read allowed, both implementations produce identical 104-row snapshots.

**Unchecked:** reconstruction requiring withheld original reports/transcripts—including AN-13 finding counts, event recounts, original-answer regrading, transcript-derived usage/audits, and historical freeze chronology. Retained summaries support these claims but do not permit independent reconstruction.

Key commands and exit codes:

| Command/check | Exit and result |
|---|---|
| `rtk python3 -B -m unittest tests.test_adoption_docs_consistency tests.test_install_claude_profile` | **0** — 95 tests, 4 skipped |
| `rtk python3 -B scripts/validate.py` | **0** — 7,806 hashed files, 161 receipts |
| `rtk python3 -B -m unittest tests.test_grand_dashboard` | **0** — 17 tests |
| New dashboard test against main, loaded in memory | **1**, expected size-limit failure |
| `rtk sha256sum -c prereg-r3.sha256` | **0** |
| `rtk python3 -B grader_selftest.py` | **0** — 33/33 |
| Current / frozen order checkers | **0 / 1**, as documented; injected mismatch also **1** |
| Exposure scanner | **1**, documented names/pattern matches; independent privacy check **0** |
| Read-only Python comparisons, retallies and pinned tokenizer checks | **0** |
| `rtk git diff --check 9e036e7d..HEAD` | **2** — trailing spaces in retained `judge-{AB,BA}.txt:67` |
| Revision/blob reads and final `rtk git status --short` | **0** — correct revisions; clean worktree |

No repository files were changed.