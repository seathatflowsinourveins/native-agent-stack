- **DECISION:** latest-opus. Replace line 40 of ~/.claude/CLAUDE.md with exactly:
  `  - The latest Opus at effort max for design, build, research, review, verification and synthesis.`

- **Reasons:**
  - **The version number goes against the rule the user set.** The recorded policy is to always run the latest model. It rejected a version-pinned list because the next Opus release would stay excluded until someone edited it (4). The user asked for only the latest models, including ones released in the past few weeks (5). Writing "Opus 5.5" in the prose is that same kind of pin. After the next release, a 5.5 worker would still satisfy line 40 while breaking the policy. Anthropic's audit guidance says this about CLAUDE.md directly: version numbers are details nothing re-checks, pinned model names silently fall behind after the next release, and the fix is to "State the current rule" (2). The current rule is "latest", not a number.
  - **Plain "Opus" drops that rule.** It accepts any Opus (8). The opus alias itself depends on provider and client version; on Microsoft Foundry it gives Opus 4.6 (1). Under plain "Opus", the claude-opus-4-8 substitution (4) and the likely Opus 5 gateway lane (5) would both count as compliant. The line guides which model a coordinator passes to workers (6), so looser wording risks looser worker choices, not just looser text.
  - **"The latest Opus" is the only candidate that works both now and later.** Today it flags the same cases the pin flags: 4-8 and Opus 5 are both older than 5.5 (4, 5). After the next release it keeps flagging stale lanes, which the pin cannot do. It also matches the repository's model settings, which already carry no version (3), without claiming those aliases always point to the newest model (1).
  - **The consistency argument points the other way.** Evidence 3 favors moving the portable copy (examples/claude-native/CLAUDE.md:41, which says plain "Opus") to "the latest Opus". It does not favor lowering the global line to plain "Opus", which has the gap described in 8.
  - **Limit, not a reason against:** no wording controls which model actually runs. The alias still resolves differently by provider (1), and in the incident a review was recorded as "verified on 5.5" while children ran claude-opus-4-8 (4). Whether a run followed the rule can only be shown from the model ID that run actually used, not from this line.

- **Overturn condition:** Put a version back, alone or next to "latest", if a paired dispatch test shows the pin picks the right model more often. The test: same host, client version and provider, at least 20 worker runs per wording. Overturn if, under "The latest Opus", a smaller share of runs record the newest Opus released at test time as their resolved model ID than under "Opus 5.5" (one-sided Fisher exact test, p < 0.05).

- **Insufficient evidence:**
  - 5 is an inference from an open, unmerged PR about one host's gateway, not an observed Opus 5 run.
  - 6 says the line drives model choice but gives no sample of actual dispatches.
  - 4 quotes a decision record rather than the run's own record, and does not separate the wording's effect from how the alias resolved.
  - 3 claims "every setting" is version-less without listing them.
  - 8 is one Claude reviewer's argument, not a measurement.
  - 7 carries no weight.
  - Nothing tests whether coordinators read "latest" as the newest release or as the newest on their own provider (1).
