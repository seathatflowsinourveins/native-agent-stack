# Native skill evaluation preregistration

Frozen at 2026-09-30 05:46:35 UTC, before any model execution in this workstream.

[OpenAI's evaluation recipe](https://developers.openai.com/blog/eval-skills) calls for concrete success checks, actual captured traces and a focused 10–20-prompt set. The [pinned Anthropic evaluator workflow](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md) contributes same-prompt baseline and realistic near-miss checks. This is a bounded native integration evaluation, not an unchanged upstream test suite.

The frozen [case record](preregistered-cases.json) contains ten writing-for-agents prompts, exercised in Codex and Claude, four additional search-first executions and one Claude baseline: 25 planned fresh executions. Writing positives target AGENTS.md and CLAUDE.md instructions; negatives are ordinary human prose, explanation or lookup, even where a filename or adjacent keyword appears. Explicit native invocation prefixes differ by client. Claude's search-first listing stays name-only and its positive is explicit.

Codex uses gpt-6.1-sol with ultra reasoning in a read-only native exec session. Claude uses opus with max effort, existing project instructions and settings, fresh nonpersistent print sessions, and denied mutation/delegation tools. Native client controls, actual returned output, per-case checks, outer exits and separate usage scopes will be retained. Raw JSONL and private paths remain outside the repository.

Claude 2.1.285's installed help states `--disable-slash-commands Disable all skills`. The [official CLI reference](https://code.claude.com/docs/en/cli-reference) describes the session control. The baseline uses that real flag with the identical w02 prompt, model, effort, working directory, permissions and remaining configuration. This disables all skills and commands, so it is an all-skills baseline rather than a selected-skill ablation. Startup inventory and the actual trace must demonstrate the control worked.

A positive requires native invocation or a successful full instruction read; a mention is insufficient. Outcomes are judged independently against the frozen checks. Every failure remains visible. A passing baseline does not establish skill improvement, and one repetition per arm does not establish variance or comprehensive qualification of the selected 28 skills.
