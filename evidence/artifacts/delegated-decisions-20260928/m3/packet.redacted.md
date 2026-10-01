Read-only judgment. Use no tools beyond reading this prompt, no network, and edit nothing. The evidence below is quoted with sources, supplied by a Claude coordinator; weigh it and say if any of it is insufficient.

DECISION M3: the user's global ~/.claude/CLAUDE.md line 40 (a bullet under "Quality comes first:") reads:
<user-level ~/.claude/CLAUDE.md:40 before the M3 edit, sha256 ed158c83488e43c523595efffc73bf6fca2e7dca1a514b25da4b0965091e55dd>
Should the version go? Candidates: keep as is; "Opus at effort max for …"; "the latest Opus at effort max for …"; other (give the exact text).

EVIDENCE:
1. Claude Code model-config docs (code.claude.com/docs/en/model-config:36, :61): the opus alias "Uses the latest Opus model for complex reasoning tasks"; "Aliases point to the recommended version for your provider and update over time." What opus resolves to depends on provider and client version (Opus 4.6 on Microsoft Foundry, per the same page).
2. Anthropic prompt-audit guidance (anthropics/skills@33375500:skills/claude-api/shared/prompt-audit.md:127-141): it covers CLAUDE.md, lists "version numbers" as volatile specifics that "nothing re-checks", says "pinned model names silently degrade after the next release", and recommends "State the current rule".
3. Every setting that selects a model in the repository is already version-less: agent definitions use model: opus, and the settings template uses "opus[1m]". The repository's portable copy of this very file says "Opus at effort max for design, build, …" (examples/claude-native/CLAUDE.md:41).
4. The recorded policy is to always run the latest model (docs/decisions/2026-09-25-model-fallback-guard.md:68-70, 119-120). A version-pinned allowlist was rejected because "The next Opus release would then stay excluded until someone edits the list". In an observed incident, children that requested opus silently ran claude-opus-4-8 while a review was recorded as "verified on 5.5".
5. Open PR #434 (docs/decisions/2026-09-27-model-currency.md:79-80, 207) records that a loopback gateway on this host lists no claude-opus-5-5, and infers that an Opus lane routed through it would run on Opus 5. With "Opus 5.5" in the rule, such a lane is visibly off-policy; with "Opus", it is not. The user asked for "only the latest state-of-the-art models, including those released in the past weeks" (#434 :3-4).
6. The prose line drives the explicit model parameter a coordinator chooses for workers (AGENTS.md:35 requires "an explicit task-matched model" on every agent call), so it is not inert.
7. Peers took no position.
8. An independent Claude reviewer refuted "drop to 'Opus'" because a bare family name admits any Opus and drops the "latest" constraint.

OUTPUT:
- DECISION: keep | opus | latest-opus | other (give the exact text);
- the reasons, citing evidence numbers;
- one measurable overturn condition.
