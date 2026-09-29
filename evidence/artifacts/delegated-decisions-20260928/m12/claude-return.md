DECISION: keep

REASONS:
1. The broad scope is what the user asked for. The user's recorded words are "ALL ACTION NEED SOTA REFERENCES BACKED" (4). The current line already carries the "research convergence first" framing the user requested on 2026-09-28 (4). The proposal would replace that scope with four verbs. The user delegated the decision "with evidence manifest, research convergence and consensus with peer sessions" (4), and there is no consensus for a change: the peer sessions took no position (7) and the only independent review rejected the narrowing (8).
2. No defect has been shown. No retained record shows the rule being over-applied. The case of researching before trivial steps is only a hypothetical raised by a text audit, not observed behavior (5). The upstream advice is to review CLAUDE.md "when things go wrong" and to test changes by observing whether behavior shifts (3). Nothing has gone wrong, and neither wording has a behavior test (8).
3. Anthropic's model-specific guidance does not treat "any action" as a defect. Its own Opus 5.5 sample sentence starts "Before taking any action", because the model "tends to get to work quickly" (1). The advice to be specific (2) is a fair general point. But the conflict between rules it warns about has not been shown here: the neighbouring lines already limit research (<user-level ~/.claude/CLAUDE.md:15 fragment, redacted>) and rule out diagnostic campaigns <user-level ~/.claude/CLAUDE.md:16 fragment, redacted> (lines 15-16).
4. The risks are uneven. The only recorded harm was the rule being under-applied: self-written strategy arms with a recorded session loss (4). Over-application is only hypothetical (5). A fixed list of four verbs leaves other steps (for example removing a component or running an experiment) open to interpretation. So narrowing gives up coverage of a failure that actually happened to avoid one that has never been seen.
5. Process: the top rule is decided wording that stays verbatim, the repository copy must match it, and changes go through the owner of PR #444 (6). Editing only the user-level line would break that match.

OVERTURN CONDITION: Adopt the proposed text, and change the repository copy in the same edit through the PR #444 owner (6), if a retained paired behavior test meets all of these conditions:
- It runs Claude Code 2.1.283 with Opus 5.5, and the top-rule line is the only difference between the two arms.
- It uses at least 20 fixed tasks per arm. Each task mixes steps that only read or answer with at least one step that writes, builds, installs or adopts.
- A non-Claude judge scores it blind from the transcripts.
- Under the current line, research or skill-discovery calls come before at least 20% of the read-only or answer-only steps.
- Under the proposed line, the share of write, build, install or adopt steps that are researched and cite a source is no lower than under the current line.

INSUFFICIENT EVIDENCE:
- 5: the "no retained record" claim does not say what was searched or over what period, and the /doctor audit output is paraphrased, not quoted.
- 1 and 4: both quotes are cut with "…", so any qualifying text around "any action" and "ALL ACTION" is not visible. The Opus 5.5 sample is for automating workflows across connected apps, not for coding agents.
- 6: neither the current text of the repository copy nor the PR #444 owner's position is shown, so whether the two copies match word for word today is unverified.
- 8: it is unclear what "ground (1)" refers to, and the reviewer's own output is not quoted.
- 3: no behavior test exists for either wording.
