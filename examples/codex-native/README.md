# Codex agent examples

Portable copies of the agent-lab `.codex/agents/` definitions that mirror the
Claude roles in [`examples/claude-native/agents/`](../claude-native/agents/):

| Agent | Role | Sandbox |
| --- | --- | --- |
| `evidence-reviewer` | independent review of an assigned patch and its evidence; no edits | as declared in the file |
| `isolated-builder` | bounded implementation in its own worktree with a verified handoff | as declared in the file |

Copy the `.toml` files into the destination project's `.codex/agents/` and merge
[`config.agents.toml.example`](config.agents.toml.example) into `.codex/config.toml`.
The definitions carry `name`, `description`, `developer_instructions` and, where
set, `sandbox_mode`; they set no `model` or `model_reasoning_effort` and inherit
the session's configuration. Cross-family review and live coordination are
described in [the cooperation lanes recipe](../../recipes/claude-codex-cooperation-lanes.md).

Boundary: these files were deployed alongside the Claude agents but have no
end-to-end run of their own in the dated guide
(`docs/ultracode-token-routing-20260921.md`); the Codex evidence there is the
lane C bridge review run from Claude. Qualify a Codex agent per task before
relying on it.
