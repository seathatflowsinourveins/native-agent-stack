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
and `description`. Verified against the Codex source at tag `rust-v0.155.1`
(`codex-rs/agent-roles/src/agent_role_config.rs`, `loader.rs`, `discovery.rs`;
lines retained in `evidence/artifacts/harness-rules-convergence-20260922/codex-agent-roles-source.json`):
every `.toml` under the agents directory is discovered even without a table
entry, a declared `config_file` is not loaded twice, the file's `description`
wins over the table's, duplicate names in one layer warn, and a description is
required. `config_file` resolves against the folder that holds `config.toml`, so
the value is `agents/<name>.toml`, not `.codex/agents/<name>.toml` (a Codex
Lane C review confirmed the schema on `codex-cli 0.155.1` and caught that path).
Not yet exercised as a spawned role in a Codex session on this profile.
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
