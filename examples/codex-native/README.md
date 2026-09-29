# Codex agent examples

Portable copies of the agent-lab `.codex/agents/` definitions that mirror the
Claude roles in [`examples/claude-native/agents/`](../claude-native/agents/):

| Agent | Role | Sandbox |
| --- | --- | --- |
| `evidence-reviewer` | independent review of an assigned patch and its evidence; no edits | inherited from the session (the file sets none) |
| `isolated-builder` | bounded implementation in its own worktree with a verified handoff | inherited from the session (the file sets none) |
| `stack-researcher` | bounded research from the sources a task names, with source-cited findings returned inline; no edits. A user-wide carrier: see the [2026-09-29 section](#2026-09-29-stack-role-carriers) | inherited from the session (a role file cannot set one) |
| `stack-verifier` | re-runs the commands a task names and returns a verdict per claim; never fixes; no web search. A user-wide carrier: see the [2026-09-29 section](#2026-09-29-stack-role-carriers) | inherited from the session (a role file cannot set one) |

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
native templates carry the custom-agent developer instructions; no new role or installer is needed
(superseded on 2026-09-29: [stack role carriers](#2026-09-29-stack-role-carriers)).
[`tests/test_codex_agents.py`](../../tests/test_codex_agents.py) checks the parsed
developer payload of every template against the existing F4 block and the pinned
upstream text's SHA-256. This is structural validation, not a new
spawned-agent run or a measured token saving. See the
[decision addendum](../../docs/decisions/2026-09-26-codex-worker-lane.md#2026-09-27-addendum-custom-agents-and-context-hub).

## 2026-09-29: Stack role carriers

This section supersedes the sentence of the 2026-09-27 section above that says "no new role or installer is needed",
and the matching sentence of the
[2026-09-27 decision addendum](../../docs/decisions/2026-09-26-codex-worker-lane.md#2026-09-27-addendum-custom-agents-and-context-hub).
The token-adoption E2E launches Codex sub-agents that pass `agent_type` `stack-researcher` (`seed-binding-1`, `-2`, `-3` and `-5` in its
[preregistration](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json)), and an unknown `agent_type` fails the spawn
([`role.rs:51-60`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L51-L60)). No template carried that
role. Two carriers are therefore added, `stack-researcher` and `stack-verifier`, the Codex counterparts of the Claude carriers
[`stack-researcher.md`](../../adoption/agents/claude/stack-researcher.md) and [`stack-verifier.md`](../../adoption/agents/claude/stack-verifier.md).

- **Files.** The sources are
  [`adoption/agents/codex/stack-researcher.toml`](../../adoption/agents/codex/stack-researcher.toml) and
  [`stack-verifier.toml`](../../adoption/agents/codex/stack-verifier.toml) in the same directory; the copies in [`agents/`](agents/) are
  byte-identical mirrors. [`tests/test_codex_agents.py`](../../tests/test_codex_agents.py) compares them and pins the digests below. The same two digests are in [`adoption/agents/codex/SHA256SUMS`](../../adoption/agents/codex/SHA256SUMS) (`sha256sum` format; `sha256sum --check --strict SHA256SUMS` from that directory passes), which the installer reads before it copies a file, and the rules the tests and the installer share are in [`tools/adoption/codex_roles.py`](../../tools/adoption/codex_roles.py).
- **Keys and pins.** Each file carries exactly `name`, `description`, `model`, `model_reasoning_effort` and `developer_instructions`.
  The pins, `gpt-6-astra` at `max`, equal the route of every Codex task in the frozen preregistration (the test derives that set from the
  file). Codex shows them in the `spawn_agent` tool text as the role's locked settings
  ([`role.rs:294-334`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L294-L334)).
- **Descriptions.** One line each, naming no tool. The same tool text lists every role's description to every parent, so a description that
  named a tool would steer arms differently; the test checks both against the frozen no-tool-names denylist of the preregistration.
- **Instructions.** The role text, one blank line, then the F4 block verbatim. The text is adapted from the Claude carriers sentence by
  sentence: 17 sentences of the researcher and 16 of the verifier are kept byte for byte and pinned by the test, and the Claude-only names
  (`ToolSearch`, `WebFetch`, `Bash`, `omitClaudeMd` and the others the test lists) are absent. Three rules are added:
  one agent (a role file cannot remove the collaboration tools,
  [`role.rs:80-126`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L80-L126), so the child is told not to
  spawn, message or follow up with other agents); working directory (a task's own instruction wins, and `cwd` goes to context-mode only for a
  directory other than the launch directory, which the server is already bound to: the "Codex workers" bullet of
  [the handbook](../../docs/token-session-handbook.md#context-mode-executor-and-session-store); the frozen M13 leg reads sentinel files with
  no explicit `cwd`); and `jq` output among the exact command shapes (the F4 exceptions list six commands). The verifier also says that it
  does not use web search.
- **Registration.** Discovery only. Codex loads every `*.toml` under `$CODEX_HOME/agents/` (`load_agent_roles` in
  [`loader.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/agent-roles/src/loader.rs)), so the roles carry no
  `[agents.<name>]` table and neither `config.toml` nor the `stack-worker` profile changes; a test checks the repository templates for role
  tables, and [`config.agents.toml.example`](config.agents.toml.example) still registers only the two older roles. Do not copy these two into
  a project `.codex/agents/`: a project copy would load in every trusted session of that checkout, not only in the E2E's. On a host the files
  belong at `$CODEX_HOME/agents/<name>.toml`, mode 0600 in a 0700 directory.
  [`tools/adoption/apply_codex_lane.py`](../../tools/adoption/apply_codex_lane.py) installs them there: create-only, never over a differing
  file, its dry run copies them into a scratch home and reads the result back through `codex doctor --json`, and rollback removes only what
  that run created. The `roles` row of [`prove_codex_lane.py`](../../tools/adoption/prove_codex_lane.py) checks the installed state.
- **Registration modes considered.** A per-launch `-c agents.<role>.config_file=<absolute path>` also works by source reading:
  `load_agent_roles` reads `[agents.<name>]` tables from every enabled layer, session flags included, and a declared `config_file` must be an
  absolute path ([`loader.rs:35-73,192-206`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/agent-roles/src/loader.rs#L35-L206);
  the session-flags layer has no config folder,
  [`state.rs:218-231`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/state.rs#L218-L231)). It is not used: the
  E2E's sub-agent launches would then differ from the RUNBOOK's launch command, and the roles would exist only for the proof, not as installed
  practice. A project `.codex/agents/` copy is not used either (above). Neither alternative was run in a session.
- **Effect and limits.** The user layer's config folder is `$CODEX_HOME`, so a session that loads that home's user configuration discovers the
  two roles, with or without `-p stack-worker`, and its `spawn_agent` tool then lists both and accepts `agent_type`
  ([`spec_plan.rs:1271`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/tools/spec_plan.rs#L1271): `expose_agent_type`
  when the configured roles are not empty). Read from source, `--ignore-user-config` still keeps that layer's file and therefore its folder
  ([`loader/mod.rs:503-519`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/loader/mod.rs#L503-L519)), so a session
  started that way is predicted to discover the roles too; that prediction has not been run. A role file cannot set the sandbox, an MCP
  allowlist, tools or web search (`role.rs:36-48`, as in the 2026-09-27 correction above), so read-only access is a prompt rule that only the
  parent's `-s read-only` enforces, and the verifier's no-web rule is a prompt rule too. The child starts from a clone of the parent's
  configuration, as above.
- **Evidence class.** Structural validation only: the stem set, byte-identical mirrors, the digests below, the closed key set, the pins
  against the frozen Codex tasks, description lane-neutrality, the F4 block, the kept sentences, the Claude-only names and a mutation control
  for every rule. No Codex session has spawned either role, and nothing here measures a token saving.

| File | SHA-256 |
| --- | --- |
| `stack-researcher.toml` | `ac77b1624fc0ac264ff5b9807e05889d20137440dea9c016441bba38b1ea8c00` |
| `stack-verifier.toml` | `281d7e8b985414d072396cc613a75adb3740570ebaaefd1a437ff2c099d5f2bd` |

The adoption source and its mirror hold these bytes; a later change to either needs a new dated section here, new rows in `SHA256SUMS` and new rows in the test.
