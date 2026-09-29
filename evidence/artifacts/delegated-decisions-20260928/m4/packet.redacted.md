Read-only judgment. Use no network and edit nothing. Files in this directory: SKILL.md (obra/superpowers verification-before-completion, pinned at 8ca22dba, blob sha256 2befe7fc…), AGENTS.md (this repository's instructions, origin/main), and skills-trial-excerpt.md (the trial's in-force rules, including "A trial skill shows measurable harm, or gives instructions that conflict with CLAUDE.md/AGENTS.md once actually read in full → remove it immediately").

Question: read SKILL.md in full. Does it give instructions that conflict with AGENTS.md in the sense of that removal rule? Candidates to test, not conclusions to accept:
- SKILL.md "If you haven't run the verification command in this message, you cannot claim it passes" and "RUN: Execute the FULL command (fresh, complete)" against AGENTS.md "Reuse passing evidence when its inputs still match and run only checks needed for a concrete gap";
- "When To Apply … Moving to next task / Delegating to agents / ANY positive statement" against AGENTS.md's bounded-work rule ("do not add intake … Stop only for …");
- anything else you find in a full read.

For each candidate, say whether it is a real conflict (following one instruction necessarily violates the other in a realistic case; give the case) or compatible (a reading satisfies both; give the reading), with line quotes from both files.

Output:
- VERDICT: conflict | no-conflict | partial (name which lines);
- one paragraph of reasons;
- the smallest consistent disposition under the trial's own rules: remove now, keep, or keep with a recorded reading. Do not propose editing the vendored text.
