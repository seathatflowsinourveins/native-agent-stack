# Codex agent examples

Portable copies of the agent-lab `.codex/agents/` definitions that mirror the
Claude roles in [`examples/claude-native/agents/`](../claude-native/agents/):

| Agent | Role | Sandbox |
| --- | --- | --- |
| `evidence-reviewer` | independent review of an assigned patch and its evidence; no edits | inherited from the session (the file sets none) |
| `isolated-builder` | bounded implementation in its own worktree with a verified handoff | inherited from the session (the file sets none) |

Copy the `.toml` files into the destination project's `.codex/agents/` and merge
[`config.agents.toml.example`](config.agents.toml.example) into `.codex/config.toml`.
The example also registers each role under `[agents."<name>"]` with `config_file`
and `description`, the shape a research child quoted from the Codex config
reference on 2026-09-22; that registration is unverified on an installed CLI (the
installed 0.155.1 binary contains the strings `config_file`,
`developer_instructions` and `max_concurrent_threads_per_session`, a string scan,
not a parse test), and which `description` Codex shows when both the table entry
and the `.toml` file carry one is untested, so confirm both against the installed
version before relying on them.
The definitions carry `name`, `description` and `developer_instructions`; they set
no `model`, `model_reasoning_effort` or `sandbox_mode` and inherit the session's
configuration, so the reviewer's no-edit rule is a prompt instruction, not an
enforced sandbox. Cross-family review and live coordination are
described in [the cooperation lanes recipe](../../recipes/claude-codex-cooperation-lanes.md).

Boundary: these files were deployed alongside the Claude agents but have no
end-to-end run of their own in the dated guide
(`docs/ultracode-token-routing-20260921.md`); the Codex evidence there is the
lane C bridge review run from Claude. Qualify a Codex agent per task before
relying on it.
