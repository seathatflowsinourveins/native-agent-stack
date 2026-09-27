# Decision: Claude harness settings, role agents and dispatch rules (2026-09-27)

**Decided by:** a workflow unit on host `nativestack-5975wx-20260925`, carrying out the verified items of the
2026-09-27 settings synthesis (its PR-A, PR-C and PR-D groups, plus the token gaps `serena#2`, `ai-memory#2` and
`codebase-memory-mcp#2`) that are not user decisions. The synthesis and its four verified area reports are
scratch inputs, not retained receipts; every claim below cites its primary source instead. Branch
`claude/claude-harness-settings-20260927`, based on `origin/main@5f3a7c21`, checked against Claude Code 2.1.283
and codex-cli 0.157.1.

**The user's rules this carries out.** The host's global instructions (`~/.claude/CLAUDE.md`, "Workers,
Ultracode and agent teams") put "Opus 5.5 at effort max for design, build, research, review, verification and
synthesis", allow "Sonnet or Haiku only for pure command wrappers, mechanical extraction and probes", and name
four dispatch modes, agent teams among them. The verified orchestration report records the user's turn of
05:25Z asking for Opus on the preregistration and verification workflows ("never damage quality").

**Scope:**
- `adoption/agents/claude/isolated-builder.md` and `stack-verifier.md`, their byte-identical copies in
  `examples/claude-native/agents/`, and a new third copy of all ten definitions in `.claude/agents/`;
- `adoption/templates/claude.settings.template.json` and `.claude/settings.json`;
- `scripts/hooks/secret_path_guard.py` and `adoption/hooks/claude/SHA256SUMS`;
- `tools/adoption/render_config.py`, `adoption/pins-macos-arm64.json` (one note), `adoption/mcp/claude-user.json`
  (its comment), `adoption/bootstrap.md` and `adoption/platforms/macos-arm64.md`;
- `examples/claude-native/CLAUDE.md`, `examples/claude-native/workflows/` (README, `test-envelope.mjs`,
  `test-contract-mutations.mjs`, `SHA256SUMS`), `recipes/claude-native-ultracode.md` and
  `recipes/claude-codex-cooperation-lanes.md`;
- `docs/secret-storage.md`, `docs/harness-defaults.md` (appended cells), an addendum to
  [`2026-09-26-stack-agents-role-dispatch.md`](2026-09-26-stack-agents-role-dispatch.md), and tests.

Nothing is installed or applied on a host by this change. Applying the template, installing the guard and the
agents, and re-registering MCP servers are separate, coordinated host steps.

## Decision

| # | Change | Primary source |
| --- | --- | --- |
| 1 | `isolated-builder` and `stack-verifier` declare `model: opus`; the role tables and routing rows say so. Sonnet stays only for `source-scout`'s extraction and command running; Haiku is not routed | The user's rules above; [sub-agents](https://code.claude.com/docs/en/sub-agents), "Choose a model" |
| 2 | `isolated-builder` no longer declares `isolation: worktree`. Its brief names an owned checkout the coordinator prepared at the exact base (normally `git worktree add --no-track <path> -b <branch> <base>`); before the first edit it compares that checkout's `git rev-parse --show-toplevel` with its starting directory's and stops when they match, when no path is named or when `HEAD` is not the base | [sub-agents](https://code.claude.com/docs/en/sub-agents): frontmatter `isolation` branches "from your default branch rather than the parent session's `HEAD`", and "A subagent starts in the main conversation's current working directory", where `cd` does not persist; the 2026-09-25 `core.hooksPath` rewrite in the [anti-pattern log](../harness-defaults.md#upstream-verification-and-compounding-learning); `git-rev-parse(1)` |
| 3 | `.claude/agents/` holds byte-identical copies of the ten installed definitions | [sub-agents](https://code.claude.com/docs/en/sub-agents), "Choose the subagent scope": project agents (priority 3) outrank user agents (priority 4); "Check them into version control" |
| 4 | No read-only role may declare `memory` | [sub-agents](https://code.claude.com/docs/en/sub-agents), "Enable persistent memory": "Read, Write, and Edit tools are automatically enabled" |
| 5 | The settings template keeps both model-fallback guards (`CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK=1`, `switchModelsOnFlag: false`, already present and now asserted) and adds: the home and tool credential-store `Read` denies, each with its Context Mode `**/` twin; `Edit(~/.bashrc)`, `Edit(~/.profile)` and `Edit(~/.zshrc)`; `Agent(claude-code-guide)`; nine destructive-git denies; `BASH_MAX_TIMEOUT_MS=1800000`; and `statusLine.refreshInterval: 5`. The project settings gain the same credential-store denies | [permissions](https://code.claude.com/docs/en/permissions) (Read/Edit scope, trailing ` *`, "not a security boundary"); [permission modes](https://code.claude.com/docs/en/permission-modes) ("Deny rules block in every mode"); [sub-agents](https://code.claude.com/docs/en/sub-agents) (`claude-code-guide` runs on Haiku; an `Agent(name)` deny works for built-ins); [env vars](https://code.claude.com/docs/en/env-vars) and [tools reference](https://code.claude.com/docs/en/tools-reference) (the Bash ceiling and what happens at a timeout); [status line](https://code.claude.com/docs/en/statusline) and jarrodwatts/claude-hud `v0.8.0` `README.md` (`refreshInterval`); `model-config` "Automatic model fallback" and [the fallback-guard record](2026-09-25-model-fallback-guard.md); corroboration: trailofbits/claude-code-config `2109be9` `settings.json` |
| 6 | The secret-path guard blocks a reader, copy or search of a home credential file or a Codex shell snapshot (`credential_file_read`), never a mention | [Secret storage, "Home and tool credential stores"](../secret-storage.md#home-and-tool-credential-stores-2026-09-27); openai/codex `rust-v0.157.1` `codex-rs/shell-command/src/shell_snapshot_exports.rs` |
| 7 | The portable instructions carry the user's four dispatch modes and the named-spawn rule: with agent teams on, a named spawn becomes a teammate at the lead's effort in the lead's working directory without its definition's `skills` or `isolation`; name spawns only for teammates; opt a run out with `claude --settings '{"env":{"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS":"0"}}'` | [sub-agents, "Subagent names"](https://code.claude.com/docs/en/sub-agents#subagent-names); [agent teams](https://code.claude.com/docs/en/agent-teams) ("Teammates inherit the lead's effort level", `skills` not applied, `-p` spawns no teammates, the `"0"` override and `--settings` precedence) |
| 8 | The Ultracode recipe adds the dispatch facts, verification patterns (a)-(h), the prefix-sharing condition and the Codex depth note; the workflows README adds a brief contract and keeps lane text in saved-workflow packets until a Workflow child is observed receiving the SubagentStart block | [workflows](https://code.claude.com/docs/en/workflows); [best practices](https://code.claude.com/docs/en/best-practices); anthropics/claude-code `7779afb` `plugins/code-review/commands/code-review.md`; arXiv:2512.08296 v3; Anthropic, [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system); [hooks, SubagentStart](https://code.claude.com/docs/en/hooks#subagentstart); [the carrier record](2026-09-27-token-lanes-subagent-start.md); openai/codex `rust-v0.157.1` `codex-rs/config/src/config_toml.rs` L719-720 |
| 9 | The cooperation recipe gives the headless cross-family review form: `codex exec -s read-only -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live" -o <file> "<prompt>" < /dev/null`, one review and one repair round | codex-cli 0.157.1 `codex exec --help`; the stdin and `web_search` rows of the [anti-pattern log](../harness-defaults.md#upstream-verification-and-compounding-learning) |
| 10 | Token gap `ai-memory#2`: the template's eight ai-memory hook commands run `${AI_MEMORY_BIN}`, which `render_config.py` renders as `${ECO_ROOT}/tools/ai-memory-<version>/ai-memory` from the selected platform's pins file (`--platform`, default: this machine) unless the host supplies the binary it runs | akitaonrails/ai-memory `v2.4.1` `docs/install.md`: "Native hook commands invoke the installed binary directly"; `adoption/pins-linux-x86_64.json` (2.4.1) and `adoption/pins-macos-arm64.json` (2.3.2); the pins-file naming in `scripts/adoption_status.py` (`PIN_OS_ALIASES`) |
| 11 | Token gap `serena#2`: Serena's optional hooks are not added to the template (below) | oraios/serena `c6fbd1c` `src/serena/hooks.py`; the [Serena client guide](https://oraios.github.io/serena/02-usage/030_clients.html) |
| 12 | Token gap `codebase-memory-mcp#2`: registration stays a manual, per-host step and no shipped agent grants the server's tools (below) | `adoption/mcp/claude-user.json` comment; [Codex MCP scope record](2026-09-25-codex-mcp-scope.md) |
| 13 | `PortableTopRuleTests` re-baselines the portable instructions to 1,205 words | Item 7 did not fit the 925-word ceiling (below) |

## Serena hooks (`serena#2`)

The client guide documents four opt-in Claude Code hooks, `serena-hooks remind`, `auto-approve`, `activate` and
`cleanup`, as "an alpha feature", and the installed Serena at the stack pin ships them (`serena-hooks --help`).
Read at `c6fbd1c`, `src/serena/hooks.py`:

- `remind` (PreToolUse, empty matcher) returns `permissionDecision: "deny"` after three consecutive grep calls,
  three code-file reads or four mixed ones without a Serena symbolic call, at most once per two-minute window
  (`PreToolUseRemindAboutSymbolicToolsHook`, lines 123-160 and 456-530). `source-scout`, `stack-verifier` and
  every `blind-*` role have no Serena tool, and Serena answers for the parent session's checkout, not a
  builder's worktree ([role-dispatch record](2026-09-26-stack-agents-role-dispatch.md)), so the hook would deny
  reads those roles cannot replace.
- `activate` (SessionStart) injects "activate it using Serena's activate_project tool ... Follow this instruction
  before doing anything else" (lines 574-588), while the `claude-code` context this stack registers is
  `single_project: true` with `activate_project` disabled (`src/serena/resources/config/contexts/claude-code.yml`,
  cited in the role-dispatch record's evidence).
- `auto-approve` acts only in `acceptEdits` and `auto` modes (lines 596-633); the template runs
  `bypassPermissions`, and it would pre-approve Serena's symbol-edit tools, which the builder deliberately lacks.
- `cleanup` only removes the others' session data.

Overturn: a preregistered trial on frozen symbol-navigation tasks, with and without `remind`, `reset` and
`cleanup` scoped to roles that hold Serena tools, shows higher Serena use with no drop in correctness and no
blocked read in a role without Serena. The existing token-lanes block already routes symbol work to Serena.

## codebase-memory-mcp (`codebase-memory-mcp#2`)

No platform pins file installs codebase-memory-mcp; `recipes/README.md` installs the v0.11.0 release by hand. A
portable user-scope entry would therefore name an absent binary on a new host, and a user-scope server loads its
instructions into every session (the 2026-09-25 jCodeMunch precedent in `claude-user.json`). The Claude side is
gated instead: a host that installed it registers it by hand, and the template comment says how. No shipped
agent's exact tool list gains its tools: alternative 5 of the role-dispatch record grants a lane only with a
written route and measured use, and no call from any shipped agent has been recorded. The Codex template entry
belongs to the Codex unit. Overturn: a pinned install on each platform plus a recorded useful call from each
intended agent.

## Evidence

| Claim | Class | Source |
| --- | --- | --- |
| The agent contract, role tables and copies agree | `local_integration` | `node test-envelope.mjs` (253 passed), `node test-contract-mutations.mjs` (68 passed), `python3 -m unittest tests.test_install_claude_profile`, also with PyYAML through `uv run --with pyyaml` |
| The builder contract fails closed | `local_integration`, failing-first | three mutations fail the suite: the builder regains `isolation: worktree`, drops its own-checkout comparison, or stops refusing to edit |
| The hook commands follow the platform pin | `local_integration`, failing-first | `AiMemoryBinTests`: four failures against the template at `5f3a7c21`, none after |
| The guard blocks the new readers and passes the clients | `local_integration` | `tests.test_secret_path_guard` blocked, allowed and recorded-gap tables |
| Documented behaviour of named spawns, teammates, memory, scopes, permissions and timeouts | `source_review` | the Claude Code pages cited above, read 2026-09-27 against 2.1.283 |

No native run backs this record: neither role has run on Opus, no Workflow child has been observed with the
SubagentStart block, and the host still runs the previous agents, guard and settings.

## Effect on frozen preregistrations

- **Token-practice E2E** ([`token-adoption-e2e-20260926`](../../evidence/artifacts/token-adoption-e2e-20260926/README.md)):
  its B arm binds `isolated-builder` and `stack-verifier` stages to `model: 'sonnet'`, and its runbook says "Keep
  `isolation: worktree`". After this change the builder gets no harness-created tree in B (it uses the prepared
  owned checkout, as A and A0 already do), and the user's rule asks for Opus on build and verification. Its own
  rule applies: "Amend and merge the protocol first if a prerequisite requires changing an input." This record
  does not edit that frozen protocol.
- **Role-dispatch comparison:** amended before any run by the
  [2026-09-27 addendum](2026-09-26-stack-agents-role-dispatch.md#addendum-2026-09-27-opus-builder-and-verifier-no-frontmatter-isolation).

## Alternatives

1. **Keep `isolation: worktree`, or pass `isolation` on each call.** Rejected: both branch from the default
   branch, not the exact base, and the field rewrote the shared `core.hooksPath` on 2026-09-25.
2. **A `WorktreeCreate` hook.** Deferred to a probe: the four checks of the worktrees page plus two builders
   spawned at once from different bases, with `core.hooksPath` still relative afterwards.
3. **A linked-worktree-only check** (`--git-dir` against `--git-common-dir`). Rejected: it refuses the prepared
   clones the E2E protocol allows, while the hazard is the coordinator's own checkout.
4. **Guard patterns that block any mention of these paths.** Rejected: they would block `ssh -i`, `kubectl
   --kubeconfig` and the `chmod` of Codex snapshots in every session.
5. **A version-only ai-memory placeholder.** Rejected: a Mac that keeps its running ai-memory in stage 1 of the
   [single-writer decision](2026-09-27-mac-single-writer-staged.md) needs another path, not another version.
6. **Portable instructions within 925 words.** Rejected: a 344-word Workers section still dropped rules of the
   user's text, and the section needs about 600 words.
7. **A PreToolUse guard against named spawns of these roles.** Waits on a probe: the hooks reference lists
   `prompt`, `description`, `subagent_type` and `model` for the Agent tool, not `name`.

## Open user decisions (unchanged here)

Carve-outs for `~/.ssh/config`, `known_hosts` and `*.pub`; moving the trading paragraphs out of `AGENTS.md`;
auto mode against `bypassPermissions`; interactive Codex effort; the OmniRoute build, login and usage
credential; replacing codex-plugin-cc if it is still stale on 2026-10-06; the claude.ai connector; the host's
Codex `tmp` trust entry; and per-tool MCP approvals in interactive Codex.

## Acceptance and overturn

- **Opus roles.** Re-qualify `isolated-builder` and `stack-verifier` on Opus in the amended role-dispatch
  comparison. Only the user changes the model rule.
- **No frontmatter isolation.** Restore native isolation only after alternative 2's probe passes.
- **Named-spawn rule.** Add the guard of alternative 7 when a probe shows `name` in the hook input; revisit
  the rule if the docs change how a named spawn launches.
- **Word budget.** Revisit with a `/context` measurement of the instruction surface per session and per child.
- **Template settings.** Remove a deny when it blocks a required task in the documented permission-posture
  trial; `BASH_MAX_TIMEOUT_MS` falls back if a verifier holds a worker for 30 minutes without a result.

## Limitations

- The host is unchanged: `~/.claude/agents/`, `~/.claude/hooks/secret_path_guard.py` and
  `~/.claude/settings.json` still hold the previous versions, so `test_host_profile_copy_is_verbatim` fails on
  this host until the guard step of `install_claude_profile.py` runs.
- The deny rules and the guard are not a security boundary: `grep -r` inside a directory, a subprocess that
  opens a file itself and a program such as `sqlite3` on the gateway database pass.
- The `//mnt/*/Users/*/...` rules assume WSL2's default automount root.
- The Codex depth statement is source reading at `rust-v0.157.1`, not a run.
