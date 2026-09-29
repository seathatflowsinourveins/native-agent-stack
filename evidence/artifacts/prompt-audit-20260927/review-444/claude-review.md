VERDICT: changes-needed

I reviewed the worktree at `<worktree>` (commit 0779e91a). None of the findings blocks the applied edits. All of them are in the decision record or the evidence text.

1. **should-fix: M4 is handed to the user although its own evidence says it is project work.**
   - `<worktree>/docs/decisions/2026-09-27-prompt-audit-resolution.md:585-586` says: "M3 and M4: the other user-level findings are the user's decisions."
   - `<worktree>/evidence/artifacts/prompt-audit-20260927/an13/README.md:36` says: "Residual … `isolated-builder` still preloads it (`.claude/agents/isolated-builder.md:9`). The project-side options left are ending the trial or not preloading it there." Line 9 is `- verification-before-completion`.
   - The quoted user direction asks to "resolute all in your end".
   - Fix: record M4 as a project-side residual and name the preload.

2. **should-fix: a host result is stated with no retained output.**
   - Record `:246-248` says: "On this workstation it ran after #458 merged … `tools/adoption/prove_codex_lane.py` passed 7 of 7."
   - No receipt for this run is in the tree. The only apply receipt, `evidence/artifacts/codex-worker-lane-host-20260927/apply.txt`, comes from #406 on 2026-09-27.
   - `<worktree>/docs/acceptance-evidence-policy.md:57-60` requires the argument vectors, times, exit codes and stdout/stderr to be kept.
   - Fix: add a sanitized receipt and cite it, or say the output was not retained.

3. **should-fix: the round-3 judge audit has no retained control showing it can fire.**
   - Record `:482` says "No judgment had a voiding hit".
   - `x9-round3/` keeps no run of `void_patterns_r3.py` or `audit_r3.py` on planted accesses, and none on a clean run of the same runtime. `audit_r3.py:28` mentions "a self-test writes elsewhere", but no self-test is published.
   - Such a control is required by `acceptance-evidence-policy.md:42-53` and by the log rule at `docs/harness-defaults.md:130`.
   - The outcome stands either way: with a void, step 2 still picks `g` on correct statuses, 10 to 8. What is unproven is the "blind" assurance.
   - Fix: publish the control, or state that none ran.

4. **should-fix: changes made after the freeze are not all disclosed.**
   - Record `:463-476` and `x9-round3/README.md:53-64` list three builder changes.
   - Diffing `make_x9_round3.frozen.py` against `make_x9_round3.py` shows more:
     - answer heads are cut to 200 characters instead of 240;
     - the status sentence is dropped when the answer head starts with it;
     - the probe lines' "arm 0, " becomes "in the current line's worktree, ";
     - scratchpad paths are scrubbed;
     - the sources JSON is compacted.
   - Fix: list these changes too.

5. **should-fix: the behavior-change claim is broader than what was measured.**
   - Record `:20-21` says: "Round 3 (2026-09-28) measured one, for X9 only".
   - Against the line it replaced, the applied text tied on all three preregistered metrics. In `analysis-r3.json` (per-arm "0" vs "g"), wrong statuses are 0 and 0, correct statuses 10 and 10, non-answers 0 and 0.
   - Only descriptive counts moved: runs naming a command went from 10 to 7, runs reading settings files from 5 to 7, and cost from $1.98 to $2.44.
   - The 10-to-8 gap is between the two candidate texts, not against the current line.
   - Fix: state that plainly.

6. **nit: two wording errors at `:557-559`.**
   - "Every obligation of the old line stays, verbatim" is contradicted by the next sentence: the heading clause survives in substance, not verbatim.
   - "the consistency tests read … the dispatch pointer" is inaccurate. The pointer is read by `tests/test_install_claude_profile.py:660-662`; `tests/test_adoption_docs_consistency.py:848` reads only the link.

7. **nit: advisor calls at `:535`.**
   - "The two judges and the researcher each made one server-side advisor call" should say the two Claude judges.
   - Carry over the caveat from `x9-round3/README.md:97-98` that the advisor's own model usage is not in these figures.

8. **nit: one unexplained flag in the judge actions.**
   - In `x9-round3/judges/judge-actions.json`, the third claude-BA action lists `outside_paths` `["/Users","/home","/tmp"]`.
   - These come from the judge's own Grep pattern; the path it searched was its own input. So the record's statement at `:482-483` that no judge opened an outside path is true.
   - Nothing in the record or README explains the flag.

**Verified and holding**
- **X5b** (`AGENTS.md:3`) is byte-identical to `user-level-top-rule.txt` (sha256 b4081c9b…).
- **S1**: the facts in `facts-s1.json`, the `### SOTA sources` heading in the template, the `sota-sources` job name, and the `validate.yml` citations (`:544-545` on this base, `:335-336` at f508ffba) all check out.
- **`harness-defaults.md:7`**: it now matches the template's heading, and no current file keeps the old heading.
- **Conflict resolutions**: `CLAUDE.md:1-8` equals `x9-round2/arms/CLAUDE.g.md`, followed by main's unchanged `## Compact Instructions` section. Main's log rows are intact.
- **New AN-13 row**: it has five non-empty cells and "this log" as its enforcement, and its figures match `an13-runs.json`.
- **X9 tally**, recomputed from the returns and the mapping: `g` wins 4 of 4, with confidences 0.91, 0.90, 0.60 and 0.60, and no voids.
- **Round-3 figures**: all match the retained files, including the per-arm table, costs, usage, wall times, token receipts and lane A's verdicts and confidences.
- **Agent types**: `blind-adjudicator` for the Claude judges, `stack-researcher` for the sources, `evidence-reviewer` for lane A's Claude lane.
- **Preregistration hashes**: every one matches except the three disclosed differences.
- **Dashboard change**:
  - Every other source keeps the 2,000,000-byte bound.
  - The `read(root, relative)` signature and the snapshot's output are unchanged.
  - The new test fails on main's reader and would catch both a global raise and an unbounded manifest.
  - The "about 60 files" margin fits: this branch added 148 files for 30,594 bytes.

**Could not check**
- **Unsupplied outputs**: the grader self-test's 33 of 33 (the file does hold 33 cases), the exposure scan's 16 files, and `check_orders_r3.py`'s negative control.
- **Full suite**: it ran on 14c91f02, not on 0779e91a.
- **AN-13 upstream claims**: I did not read the env-vars page or check the absence claim "not in the client's CHANGELOG" (`an13/README.md:18-20`). The client's own stderr line does corroborate the 600 s default and the `0` setting.
- **"Skill" wording**: whether `/doctor prompt-audit` is a skill, as the new row's title says, or a built-in command.
- **Tested vs applied configuration**: the runs used a 4-line `CLAUDE.md` at ba1700ad and the old `AGENTS.md`, not the files as applied.
- **Timing and live state**: no independent timestamp shows the freeze came before the first counted run, and I could not see the current live ruleset.
- **Withheld transcripts**: the audit, the judge actions and the Claude usage cannot be recomputed from the package.

Token tools: Context Mode `ctx_execute` for diffs, JSON recomputation and scans; Read and Grep for known lines.
