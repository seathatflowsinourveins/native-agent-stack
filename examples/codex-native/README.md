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
The two definitions above carry `name`, `description` and `developer_instructions`; they set
no `model`, `model_reasoning_effort` or `sandbox_mode` and inherit the session's
configuration, so the reviewer's no-edit rule is a prompt instruction, not an
enforced sandbox. Cross-family review and live coordination are
described in [the cooperation lanes recipe](../../recipes/claude-codex-cooperation-lanes.md).

Boundary: these files were deployed alongside the Claude agents but have no
end-to-end run of their own in the dated guide
(`docs/ultracode-token-routing-20260921.md`); the Codex evidence there is the
lane C bridge review run from Claude. Qualify a Codex agent per task before
relying on it.

## 2026-09-27: Custom-agent instruction refresh

The repository has three custom-agent templates: the two listed above and
[`semantic-evidence-reviewer`](agents/semantic-evidence-reviewer.toml). That third
role contains `sandbox_mode = "read-only"`, but **that field has no effect at
`rust-v0.157.1`**. Dated correction (2026-09-27):
[`role.rs:36–48,119–126`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L36-L48)
does not include sandbox authority in its bounded overrides; the child starts
with a [clone of the parent config](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L182-L189).
A role file cannot set or narrow the sandbox. All three roles inherit the parent
session's sandbox. Run the parent with `-s read-only` to enforce read-only access
for the semantic reviewer; the reviewers' no-edit rules are prompt instructions.
The trusted-project template's `danger-full-access` parent also passes that
authority to its children.

This refresh adds the [F4 RTK guidance block](../../docs/decisions/2026-09-26-token-practice-f1-f9.md#f4-codex-rtk-guidance-2026-09-26) to all three
`developer_instructions`: [RTK v0.50.0's awareness text](https://github.com/rtk-ai/rtk/blob/v0.50.0/hooks/rtk-awareness-full.md)
verbatim, followed by the marked exceptions already in the
[Codex AGENTS template](../../adoption/templates/codex.AGENTS.template.md).
The existing role instructions still bound what each agent may do.

Verified at **openai/codex `rust-v0.157.1`**:
[`agent_role_config.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/agent-roles/src/agent_role_config.rs)
parses the role file and validates `developer_instructions`,
[`loader.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/agent-roles/src/loader.rs)
loads declared and discovered roles, and
[`core/src/agent/role.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs)
applies their developer instructions as bounded role overrides. These existing
native templates carry the custom-agent developer instructions; no new role or installer is needed.
[`tests/test_codex_agents.py`](../../tests/test_codex_agents.py) checks the parsed
developer payload of every template against the existing F4 block and the pinned
upstream text's SHA-256. This is structural validation, not a new
spawned-agent run or a measured token saving. See the
[decision addendum](../../docs/decisions/2026-09-26-codex-worker-lane.md#2026-09-27-addendum-custom-agents-and-context-hub).
