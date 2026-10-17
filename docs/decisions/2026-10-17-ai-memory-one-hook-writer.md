# Decision: ai-memory's own installer is the one writer of its hooks (2026-10-17)

**Status:** adopted in PR (b) condition 4, under the CC's ruling D1 (hcom #9109, 2026-10-17). Hooks on a host are the
CC's act. The hook diff this change makes to the client configuration's render goes to the CC for review before it
lands.

**Supersedes**, by this record, without editing either source:

1. The builder's private receipt RECEIPT-model-picks-20261016.md, lines 123-124 (a record outside the repository, cited
   by name only; read 2026-10-17). It kept the client
   configuration's eight ai-memory hooks (through the `~/.local/bin` link), recorded that the eight setup wrote through
   the lib path were removed as duplicates, and warned against re-running `ai-memory setup` or `install-hooks`.
2. Synthesis X11 as it applied to ai-memory's hooks. X11's resolution is that "an upstream writer may run once, after
   which `new_wsl_client_config.py --check` must pass"
   (`evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json`:465). The memory-owner row applied it at
   `evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json`:1644 at 90471d63, in the "Client wiring"
   sentence: never run install-mcp, or install-hooks for Claude Code, and let ai-memory's installer write Codex's hooks
   once. X11's rule for every other entry is unchanged.

## Decision

ai-memory 3.1.0's own installer writes ai-memory's hooks in both clients, and nothing else does. The installer is the
vendor's `install.sh`, then `ai-memory setup --yes --agent claude-code --agent codex`, then `ai-memory install-hooks
--agent claude-code --no-capture-prompts --apply` (the plan's memory-owner row, stage A of this PR).

- **Claude Code:** `tools/adoption/new_wsl_client_config.py` no longer wires its eight ai-memory hook pieces. The map
  entry `claude/settings/hook/*/*${AI_MEMORY_BIN}*` is `not_wired` and declares no names, so no sentence of the
  instruction blocks changes.
- **Codex:** the tool already wrote no `~/.codex/hooks.json` (map entry `codex/hooks/hook/*`). That entry now names
  3.1.0's installer, and the `codex/config/hooks.state*` entry no longer says "once".
- **MCP entries:** the tool keeps rendering both MCP entries, in exactly the form setup writes, so the two agree. See the
  2026-10-17 addendum of [2026-10-02-new-wsl-client-configuration.md](2026-10-02-new-wsl-client-configuration.md).
  Setup keeps an existing session-aware Claude entry (akitaonrails/ai-memory@11ca7c5b
  crates/ai-memory-cli/src/commands/setup.rs:961-962, install_mcp.rs:922-952). It upserts the whole Codex table with the
  same url and bearer variable (install_mcp.rs:1909-1925).

## Why a run-once rule cannot hold

Every citation below is at akitaonrails/ai-memory@11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea (tag v3.1.0, object
8daaf928), under `crates/ai-memory-cli/src/commands/`.

- **setup** wires each agent through `wire_agent` (setup.rs:941-1016). That runs install-mcp (960-981), then
  install-hooks with `apply: true`, Global scope and `no_capture_prompts: false` (982-1002), then install-skills. Setup
  has no flag that skips the hooks (SetupArgs, cli.rs:1967-2003).
- **upgrade** refreshes the staged hook scripts and re-runs `install-hooks --agent <name> --apply` for every staged agent
  (upgrade.rs:858-892). It skips Claude Code only when `~/.claude/settings.json` carries no ai-memory hook (866-884 and
  894-914). Its arguments carry no capture flag (916-933).
- **run's auto-wire** installs hooks and MCP once per harness, binary version and config location (run_autowire.rs:1-19).
  The hook install is `apply: true` with no capture flag (320-335), so an upgrade re-wires on the next managed launch.
- **The overlay** drops every prior entry that carries ai-memory's hook signature and appends its own, keeping
  third-party hooks (install_hooks.rs:2053-2081 `is_ai_memory_hook_entry`, 2083-2106 `overlay_event_hooks`;
  uninstall.rs:1155-1164 `hook_command_is_ours`). The client configuration's template lines carry that signature
  (`<bin> --data-dir ... hook --event ... --agent claude-code --server-url ...`).
- **This repository's merge** never drops or reorders a base hook. It skips only a template hook whose shell words
  equal a base hook's (`tools/adoption/apply_claude_settings.py` `merge_hooks`, :229-269).

So whenever the two writers' commands differ, by binary path, data dir, URL or the Stop hook's capture suffix, each
renderer apply after an ai-memory write adds a second copy. Each ai-memory write after a renderer apply removes the
renderer's copies and puts back its own. Setup embeds the resolved binary, `std::env::current_exe()`
(render_shared.rs:2094-2125 and 2235-2251). NativeHorizonNY reached 16 Claude hooks this way on 2026-10-16, with the
render's `~/.local/bin` link against setup's `~/.local/lib` file. With one writer, a re-run of setup, upgrade, run or
the renderer leaves exactly one set.

The regression test D1 asks for lands in this PR. `tests/test_new_wsl_client_config.py` `OneHookWriterTests` merges the
renderer's settings with a print-mode capture of 3.1.0's own Claude hooks through `merge_settings`. It asserts exactly
the upstream hook set, with no duplicate.

## Prompt capture (ruling D5): off

- **Route.** Setup passes `no_capture_prompts: false` (setup.rs:982-997) and has no capture flag. A first apply installs
  Claude Code's `UserPromptSubmit` capture hook (install_hooks.rs:1247-1260). The row therefore runs `ai-memory
  install-hooks --agent claude-code --no-capture-prompts --apply` right after setup, in the same step, even when setup
  fails (cli.rs:3262-3267). That keeps the hold-out of recipes/README.md:382-383 and the template's eight events.
- **Persistence.** A later bare apply (setup, upgrade or run's auto-wire) keeps the opt-out while an ai-memory hook stays
  in Claude's settings. It reads the state from ai-memory's own entries (install_hooks.rs:148-158 and 1263-1274).
- **Boundary.** If every ai-memory hook is removed from Claude's settings, the next bare apply falls back to capture on
  (install_hooks.rs:1257-1260). The CC puts the choice to the owner; it changes only if the owner says so.
- **Scope (the CC's ruling G4, hcom #14261, 2026-10-17).** D5 covers Claude Code's settings hooks only, with two known
  limits. The hooks of an enabled ai-memory plugin bypass the opt-out: setup then leaves the settings-file hooks, MCP
  entry and skills alone (setup.rs:947-958), and `--no-capture-prompts` does not reach the plugin's own hooks. Codex
  capture has no upstream opt-out: `--no-capture-prompts` is documented for Claude Code's `UserPromptSubmit` hook only
  (cli.rs:3262-3270). Setup also wires Claude with capture on for the moment between its own install-hooks and the
  row's opt-out.

## Token delivery (ruling D4) and its recorded residual (ruling G2)

- **What the repository carries.** Codex's entry names `bearer_token_env_var = "AI_MEMORY_AUTH_TOKEN"` and carries no
  token (install_mcp.rs:1924-1925). Codex takes an MCP bearer only from an environment variable it names, reading it
  from its own process environment and refusing an unset or empty one
  (openai/codex@83086188ae0614bd882818ff1aa23f3194962012 codex-rs/codex-mcp/src/rmcp_client.rs:877-905). That is why the
  token is an environment variable.
- **How the token arrives.** On NativeHorizonNY the host launcher `~/.local/bin/codex-lane` exports it from ai-memory's
  owner-only token file and runs codex. That launcher is host state, outside the repository.
- **Hooks.** ai-memory's hooks do not take the token from the environment: `--apply` persists it under the data dir and
  the hooks read it there (install_hooks.rs:676-754; setup.rs:20-23).
- **Recorded residual (the CC's ruling G2, hcom #14261, 2026-10-17).** Traced in source at 83086188, not measured: the
  exported variable reaches every hook process of that Codex session, ai-memory's, rtk's and any trusted project or
  plugin hook alike. Codex snapshots its whole process environment when it builds its hooks
  (codex-rs/hooks/src/registry.rs:79). It starts each hook command from an empty environment and replays that snapshot
  into it, filtering only its own `NON_INHERITABLE_ENV_VARS` (codex-rs/hooks/src/engine/command_runner.rs:424-436;
  codex-rs/protocol/src/shell_environment.rs:15-22), which do not include this variable. The shells' `inherit = "none"`
  covers shells only. The CC accepts this as a residual within the same user's trust boundary: the service listens on
  loopback only and its token file is already owner-only for that user. The export must stay out of every global
  environment (shell profile, user manager), so only a codex-lane session carries it. Whether `$CODEX_HOME/.env`
  (codex-rs/arg0/src/lib.rs:268-288) loads before the snapshot was not traced; the repository uses the launcher.

## Consequences

- **Codex hook order.** Every re-apply appends ai-memory's entries after third-party ones (install_hooks.rs:2083-2106).
  Codex keys each trust entry by file, event, group index and hook index
  (`adoption/templates/codex.config.template.toml`:199-204, the `[hooks.state]` keys), and stores a hash of the event,
  matcher and command (codex_hook_trust.rs:1-9). So a re-apply after rtk's hooks can move ai-memory's groups and leave
  them untrusted until a `/hooks` review. The row's no-start step writes ai-memory's Codex hooks ahead of rtk's, but the
  normal install that follows runs the deferred setup, which is such a re-apply: a no-start host then ends with
  ai-memory's groups after rtk's, unlike a fresh normal install.
- **Hosts that carry the renderer's hooks.** A host that still carries the renderer's link-path hooks keeps them until
  ai-memory's installer next writes. NativeHorizonNY is one. The host step is the CC's: one `ai-memory install-hooks
  --agent claude-code --no-capture-prompts --apply`.
- **Setup's Codex approval mode (the CC's ruling G1, hcom #14261, 2026-10-17).** Setup writes
  `default_tools_approval_mode = "approve"` into Codex's ai-memory table unconditionally, on every write of that table
  (install_mcp.rs:1923, in `codex_upsert_mcp_server`, 1872-1932, which hands the table to `upsert_toml_mcp_server`).
  So on a host where setup runs, the key is set whether or not the client configuration's
  `--with-authorization-settings` was given.
  The CC accepts and records it: it matches this host's `approval_policy = "never"` posture, where Codex refuses an
  unannotated tool call unless its approval mode approves it. Nothing strips the key afterwards, because a second writer
  of it would break D1. An issue asking ai-memory to put the key behind an option is drafted for the owner's or the CC's
  filing; this record does not file it.
