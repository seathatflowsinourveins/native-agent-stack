Read-only judgment. Use no tools beyond reading this prompt, no network, and edit nothing. The evidence below is quoted with sources, supplied by a Claude coordinator; weigh it and say if any of it is insufficient.

DECISION M1/M2: should the trigger of this user-level instruction line (the user's global ~/.claude/CLAUDE.md, line 5, loaded by Claude Opus 5.5 in Claude Code 2.1.283 in every project) be narrowed?
CURRENT LINE: <user-level ~/.claude/CLAUDE.md:5 before the M3 edit, sha256 12c2d129ca32b22d83688d32e49fb9a73b572c6895aabf7f825b8639f2af5248>
PROPOSED: "Before any action, research" -> "Before you write, build, install or adopt anything, research", and "for every action." -> "for each such step."
NEIGHBOURING LINES (15-16): <user-level ~/.claude/CLAUDE.md:15 before the M3 edit, sha256 192815f85245c4321d6f4a8825e8f40586086b849c930f004766ab52113517f9>
<user-level ~/.claude/CLAUDE.md:16 before the M3 edit, sha256 c6907f6967d0e8c8bf6cdddad4485098749301f7a98212df506b15b020dfeb40>

EVIDENCE:
1. Anthropic, prompting Claude Opus 5.5 (platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5): "Claude Opus 5.5 tends to get to work quickly, and on loosely specified tasks it helps to tell the model to look through the relevant sources before acting … one sentence in the system prompt makes it look around before it changes anything". Its sample sentence: "Before taking any action, explore broadly with tool calls …" (for workflow automation across connected apps).
2. Claude Code memory docs (code.claude.com/docs/en/memory): "Specific, concise, well-structured instructions work best."; "Make instructions more specific. 'Use 2-space indentation' works better than 'format code nicely.'"; when two rules contradict, Claude may pick one arbitrarily.
3. Claude Code best practices (code.claude.com/docs/en/best-practices): "Treat CLAUDE.md like code: review it when things go wrong, prune it regularly, and test changes by observing whether Claude's behavior actually shifts."
4. The user's recorded words behind the rule (docs/decisions/2026-09-25-top-rule-sota-sources.md:18-25): "NEVER SELF WRITTEN EVER AGAIN WITHOUT SOTA REPOS, … INSTALL DIRECTLY OR REFERENCING, ALL ACTION NEED SOTA REFERENCES BACKED". The trigger event was self-written trading strategy arms with a recorded session loss. On 2026-09-28 the user asked for the rule stated "simple and clean … with research convergence first", and later delegated this decision "with evidence manifest, research convergence and consensus with peer sessions".
5. The finding came from Claude Code 2.1.283's /doctor prompt-audit, run headless: the "any action / every action" wording is broader than the rule's subject (install, build, write). No retained record shows over-application; the trivial-step case (research before reads or answers) is only a hypothetical in the audit's own return.
6. A repository rule (docs/decisions/2026-09-26-harness-rules-cleanup.md:15-16) says "Decided wording stays verbatim wherever it appears: the top rule". The repository copy AGENTS.md:3 must match the user-level paragraph, and changing it goes through the owner of PR #444.
7. The peer sessions took no position. They left it to the user, who delegated it.
8. An independent Claude reviewer refuted "adopt the narrowing" for these reasons: single-family judgment; no behavior test; ground (1) conflicts with the Opus 5.5 "Before taking any action" sample; and no recorded harm.

OUTPUT:
- DECISION: keep | adopt-proposed | adopt-other (give the exact text);
- the reasons, citing evidence numbers;
- one overturn condition that is measurable.
