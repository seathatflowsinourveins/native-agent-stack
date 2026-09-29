RECHECK: open items

Paths: W = `<worktree>`, LA = `W/evidence/artifacts/prompt-audit-20260927/lane-a`, REC = `W/docs/decisions/2026-09-28-top-rule-templates.md`.

Only G1 blocks the push; everything else is a nit.

- **G1: fixed in the working tree, but blocking until commit b1210eaa is rewritten.**
  - `LA/final/audit_selftest_a2.py:31-32`, `LA/final/adjudication/audit_selftest_final.py:36-38` and `void_patterns_final.py:27` now read `&lt;agent-id-N&gt;`. No match for `\ba[0-9a-f]{16}\b` remains in the 138 files. The scanner count went from 6 to 0 (`review/exposure-scan-*.txt`).
  - `git grep` still finds all three ids in b1210eaa: three in `audit_selftest_final.py`, two in `audit_selftest_a2.py` and one in `void_patterns_final.py`. Fold the repair into b1210eaa before the first push. A new commit on top would leave the ids reachable through the pushed SHAs.
  - The packager's refusal (`package_lane_a.py:71-74`) can only fire on `verbatim=True` copies, because `clean()` at :64 masks every id first. It has no recorded failing run; the scanner's 6 → 0 is the real control.
- **G2 / C1: fixed**, REC:12. At 46184751, 8315274f, eb678281 and 4a610e18, both templates and the test have identical blobs. `harness-defaults.md` differs only at 46184751, and the merge-base is 4a610e18.
- **G3: fixed**, `LA/README.md:14`. `W/docs/lanes.md:149` supports the acknowledgement requirement.
- **G4: fixed**, `W/docs/harness-defaults.md:129-130` (now two rows), REC:18 and `LA/final/adjudication/antipattern-rows.md:4-5`. I did not check the receipts in #444.
- **G5 / C6: fixed**, `LA/README.md:66-79` and both adjudications' `sent-sha256.json` notes. My recount agrees: 21 files flagged, 9 naming a settings file.
- **C2: fixed**, REC:42.
- **C3: fixed**, REC:115-118. `LA/adjudication/attempt1/gpt6-usage.json` parses only the `turn.completed` usage.
- **C4: fixed**, REC:71 and :78-80. `LA/review/verify-negative-control.txt` shows 2 mismatches and exit 1 on 4a610e18.
- **C5: fixed**, `LA/README.md:32`.
- **C7: fixed**, REC:7, :102-103 and :160.
- **C8: row fixed, record not (nit).**
  - `harness-defaults.md:130` now matches the evidence: `LA/adjudication/attempt2/judge-actions.json` shows the RTK read as each judge's second command, and `LA/review/rtk-read-facts.json` supports the round-1 read.
  - REC:56 still says "a pattern that matched the Codex runtime's own startup read of `~/.codex/RTK.md`", which contradicts both.
  - REC:130's "The repair round fixed every finding" overstates the result until REC:56 is reworded and b1210eaa is rewritten.

**New defect introduced by the repair**

1. **nit: `LA/README.md:52-57` and `LA/review/hash_match_report.py:28-31`.**
   - The hash accounting covers `frozen-final.sha256` and the `sent-sha256.json` lists, but never `LA/final/frozen-a2.sha256`. Neither the README, the report script nor REC mentions that file.
   - Two of its files no longer match their frozen hashes: `audit_selftest_a2.py`, which this repair edited, and `build_lane_a2.py`.
   - The README's list "The copies that differ do so only because of placeholders" names neither file.
   - Fix: add `frozen-a2.sha256` to the report, and name both files in the README list.

**Not checkable here:** whether the differences in `build_lane_a2.py` and in the prompts are only placeholders. The originals are private.
