# Project verify skill — 2026-10-06

Status: draft repository adoption. Post-land evidence-only commit firing remains
pending; this is model guidance, not an enforcement hook or passed invocation.

The project `.claude/skills/verify/SKILL.md` supplies the repository-specific
acceptance steps for Claude's named verify convention. The upstream
[2.1.286 changelog entry](https://github.com/anthropics/claude-code/blob/v2.1.292/CHANGELOG.md?plain=1#L567)
describes pre-commit guidance with docs-only/tests-only exceptions. The
[2.1.0 entry](https://github.com/anthropics/claude-code/blob/v2.1.292/CHANGELOG.md?plain=1#L7204)
documents hot reload. The installed client is2.1.292. No client setting or hook
changes are needed for this project artifact.

Authorship follows the installed
[Anthropic skill-creator](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md)
capture/draft/validate/review procedure. The installed creator digest matches
the selected pin. A locked native authoring session invoked skill-creator; an
initial source-checking turn-limit failure is retained privately, followed by a
successful scoped draft/quick-validation pass. Review corrected the distinction
between native commit classification and repository acceptance policy.

`native-agent-stack@67c6b6f94b456a3a7b5d28bb1fa34625a808d316:AGENTS.md:21–22`
requires publication validation for changed evidence/manifests and scoped
experiment consistency for new convergence claims. This skill applies the
publication check to code changes as well. Tests follow touched behavior and
`docs/lanes.md:40–67`; only existing relevant modules/classes are selected.
All checks run at nice19, with bytecode writes disabled in the skill commands,
and report their actual exit codes. The skill does not fetch, install, repair,
stage, commit, alter configuration or update evidence hashes.

The north-star action is reliable source and acceptance discipline for complex
system implementation and US-equities research/historical simulation, with
numeric/risk/order state remaining deterministic
(`blueprints/us-equities/AGENTS.md#trading-north-star`). Source, integration and
fixture checks remain distinct from unchanged upstream tests and native model
acceptance. Codex writers retain their explicit acceptance commands; this Claude
project skill is not a Codex installation.

Alternatives were the existing prose-only acceptance rule and a committing hook.
Keep the existing rule for both clients; add the upstream-native named skill for
Claude without a new hook or permission change. No skill-used campaign is run
under the user's190307Z rule. Acceptance for this draft is creator artifact
validation and the actual nice19 repository validator. One evidence-only commit
after landing must confirm invocation in native records. Revisit if that fails,
the upstream convention changes, or read-only checks are insufficient; do not
describe draft validation as that later confirmation.
