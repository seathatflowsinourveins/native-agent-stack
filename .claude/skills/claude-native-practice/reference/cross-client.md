# Claude Code and Codex: one practice, native execution per client

Ruled: command center, 2026-10-09 ~14:2xZ (layer 3 as the landing rule for every author; layers 1 and 2 here). Index: [slots.md](slots.md).

## 1. Procedure

Instructions as a short AGENTS.md map into versioned docs, and Agent Skills loaded by progressive disclosure; both clients read both.

Sources: <https://agentskills.io/specification>, <https://developers.openai.com/codex/skills>, <https://developers.openai.com/codex/guides/agents-md>, <https://openai.com/index/harness-engineering/>

## 2. Native execution

Each client runs the procedure with its own mechanism; nothing is ported between them.

Sources: <https://developers.openai.com/codex/subagents>, <https://developers.openai.com/codex/hooks>, <https://developers.openai.com/codex/noninteractive>, <https://developers.openai.com/codex/plugins>

## 3. Gate

A deep multi-agent review of every PR by the other model family, each finding given a landing-time disposition, precision tracked per family per week.

Sources: <https://claude.com/blog/code-review>, <https://www.anthropic.com/research/multiagent-systems>

## Native mechanism per client

| Need | Claude Code 2.1.295 | Codex 0.161.0 |
| --- | --- | --- |
| Delegation with fresh context | subagents (Agent tool), saved Workflows | subagents (explorer and custom agents) |
| Completion gate | Stop hook returning decision block; stop_hook_active bounds the loop | Stop hook returning decision block; stop_hook_active in the input |
| Structured headless result | `claude -p --json-schema` | `codex exec --output-schema` |
| Machine-readable event stream | `--output-format stream-json` | `codex exec --json` |
| Packaged capability | plugins (skills, agents, hooks, MCP) | `codex plugin add` (skills, MCP) |
| Native review | `/review-changes` (saved Workflow), `/code-review` in the main session | `codex review --base <ref>` or `--commit <sha>` |
| Clean-context run for an eval | a fresh subagent or `claude -p` session | `codex exec --ephemeral` |
