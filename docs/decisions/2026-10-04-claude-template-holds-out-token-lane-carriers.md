# Decision: the shared template and the default install hold out the token-lane carriers, a re-apply retires them, and jCodeMunch registers at user scope in both user templates (2026-10-04)

**Decided by:** the user's directive of 2026-10-04 in reply to the report that the full token stack cost 1.12 times the
no-token arm in the repository's own harness: "WE NEED THE CLEAN SOTA INSTALL, THE A/B TEST ITSELF SHOULD BE SOTA EXECUTE
WITH UPSTREAMCOMMANDS, YOUR ADAPTION AND TESTING METHODS MAYNOT BE SOTA ALIGNED WITH UPSTREMA REPOS FOR FULL RESOLUTION,
PLEASE FINALIZE OUR ECOSYSTEM WSL AS SOON AS POSSIBILE AT FULL SPEED RESOLUTED AT HIGEST QUALIY". The command center
(session `wsl-architecture-design`) decided the same day that NativeStack follows NativeStack2604, so the carriers leave the
shared template too, and asked for this change; session native-agent-stack-99's unit U9 carried it out. It extends
`docs/decisions/2026-10-04-new-wsl-clean-default-holdouts.md`, which held the carriers out of the new distribution only and
left the shared template unchanged.

**Scope:**

- `adoption/templates/claude.settings.template.json`, `tools/adoption/install_claude_profile.py`,
  `tools/adoption/apply_claude_settings.py`, `adoption/hooks/claude/README.md` and `held-out-hook-entries.json`;
- `tools/adoption/codex_config_prune.py` (new);
- jCodeMunch in `adoption/mcp/claude-user.json`, `adoption/templates/codex.config.template.toml`,
  `adoption/templates/codex.AGENTS.template.md` and the two 2604 additions files it leaves;
- the carrier entry of `adoption/new-wsl/client-config-map.json`, the tests, `adoption/bootstrap.md`, two lines of
  `docs/token-session-handbook.md` and the counts of `docs/decisions/2026-10-02-new-wsl-client-configuration.md`.

## Decisions

1. **The shared Claude settings template registers neither carrier hook.** The SubagentStart and the SessionStart entries are
   out of `claude.settings.template.json`, so no host that renders the template gets them. The carrier files stay in the
   repository, byte-pinned in `adoption/hooks/claude/SHA256SUMS`, labelled as held out pending the upstream A/B.
2. **`install_claude_profile.py` copies the nine carrier files only when `--hook NAME` names them** (`HELD_OUT_HOOKS`; the
   default map `HOOKS` is the three guards). An unknown name is refused as before.
3. **A re-apply retires the carrier hooks a host already has.** `apply_claude_settings.py` combines hooks per event and never
   dropped a base hook, so changing the template alone would leave NativeStack's live SubagentStart entry running. A merge
   now removes the hook objects that run `token-lanes-subagent-start.py` or `token-lanes-session-start.py` from a
   `.claude/hooks/` directory, unless the template passed carries the same command or `--keep-held-out-hooks` is given. "Run"
   means the file is the executable or the script operand of a python interpreter (the first word that is not an option) and
   nothing else runs but a trailing `|| true`, the shape of the shipped entries; a hook that merely mentions the path
   (`sha256sum <path>`, an argument of another script, an `echo`) or runs something else beside the carrier is the host's own and
   is kept (a cross-family read found that the first matcher, any shell word naming the file, deleted such a hook; the
   replacement is tested against nine commands that mention a path and eight that run one). A group
   or event left empty is dropped, every other hook keeps its value and order, and a second merge changes nothing. On a copy
   of NativeStack's live settings of 2026-10-04 the merge removes exactly one hook, the SubagentStart carrier, and with
   `--keep-held-out-hooks` it stays.
4. **Opting in is one documented step** (`adoption/hooks/claude/README.md`): install the files with `--hook`, then
   `apply_claude_settings.py --template adoption/hooks/claude/held-out-hook-entries.json`, and apply the default template with
   `--keep-held-out-hooks` from then on.
5. **Codex's removed feature flags are dropped through Codex's own writer.** A template re-apply never removes a key, and the
   installed Codex lists `plugin_hooks` as `removed` (default false; `Stage::Removed` at rust-v0.160.0,
   `codex-rs/features/src/lib.rs` L1474-L1479), so NativeStack's `features.plugin_hooks = true` is a stale no-op. The new
   `codex_config_prune.py` reads `codex features list` for the removed names and deletes the matching keys of the base
   `[features]` table with `config/batchWrite` (value null, `expectedVersion`, the writer `apply_codex_lane.py` uses). It is a dry
   run by default; `--apply` refuses while a codex process runs, backs up `config.toml` (0600) first and reads the result back. On
   NativeStack today its dry run names `plugin_hooks` and nothing else. The tests drive `--apply` against a fake app-server; as
   native execution, on 2026-10-04 at 20:07Z `--apply` also ran against the real `codex app-server` (codex-cli 0.159.3) on a
   scratch copy of NativeStack's `config.toml`: it deleted exactly the `plugin_hooks = true` line, read the result back through
   `config/read`, wrote a 0600 backup, a second dry run found nothing to prune, and the live `config.toml` kept its hash. That run
   pointed `--codex-process-name` at a name no process has, because five other codex processes were running; the live apply must
   not, and stays a quiet-window host step.
6. **jCodeMunch is registered at user scope in both shared user templates**, on the user's directive of the same day that every
   fresh session starts with the tools ready (`docs/decisions/2026-10-04-new-wsl-jcodemunch-user-scope.md`, which keeps the
   measured cost visible). The repository's own tests require the Claude and Codex user-scope sets to mirror each other, so the
   entry is in `adoption/mcp/claude-user.json` and in the Codex user template (the per-project Codex entry moved to user scope:
   approval mode, the three front-door verbs, a 60 s start-up allowance, the savings opt-out). The 2604 builder reads both
   templates, so its additions files no longer carry it. `jcodemunch` shares serena's lane in the Codex AGENTS template
   (`serena` or `jcodemunch` for exact symbols and references), which needed one shortened phrase to stay under the 8,192-byte
   budget; applying the changed block to `~/.codex/AGENTS.md` is an instruction-file edit that waits for the user's yes.

## Applying it on NativeStack (host steps, after the pull request merges)

1. `python3 tools/adoption/install_claude_profile.py --only guard` (the three default hooks; no carrier file) and the settings
   apply the host already uses, `apply_claude_settings.py` with the rendered template: the SubagentStart carrier entry goes.
   The seven carrier files already in `~/.claude/hooks/` stay and do nothing; delete them if wanted.
2. `python3 tools/adoption/codex_config_prune.py` (read the dry run), then `--apply` in a quiet window.
3. Register jcodemunch for Codex, which NativeStack lacks. `apply_codex_lane.py` does not do it (its `owned_edits` says
   registering servers is not that lane's job); two steps do, and a scratch Codex home on 2026-10-04 (codex-cli 0.159.3) showed
   them complete the template's entry: `codex mcp add jcodemunch --env RTK_TELEMETRY_DISABLED=1 --env JCODEMUNCH_SHARE_SAVINGS=0
   --env PATH=<the template's PATH> -- <ECO_ROOT>/bin/jcodemunch-mcp` writes the command and the environment, then the
   template's three other keys (`startup_timeout_sec = 60`, `enabled_tools = ["route", "menu", "order"]`,
   `default_tools_approval_mode = "approve"`) go in through Codex's config writer (`config/batchWrite`, the path
   `codex_config_prune.py` uses) or by editing `[mcp_servers.jcodemunch]` while no codex process runs; `codex mcp get jcodemunch`
   then lists all of them. NativeStack's Claude Code registration already exists and is not changed; its three extra local
   switches (context providers, git blame, AI summaries off) stay as they are.
4. A fresh session on NativeStack: confirm no `token-lanes` hook fires (hook counts of the session record) and that
   `claude mcp get jcodemunch` and `codex mcp get jcodemunch` are connected.

## Alternatives considered

- **Drop the carrier files from the repository.** Rejected: the user's directive keeps them labelled and byte-pinned until the
  command center's A/B at the operating point decides, and the files are the reference an opt-in uses.
- **Make the applier keep every base hook** (its earlier rule) **and retire by hand on NativeStack.** Rejected: any host that
  applied an older template would keep the carrier forever, and a hand edit leaves no record.
- **A one-off script that edits `~/.codex/config.toml`.** Rejected for the generic upstream-driven tool above: the next flag
  Codex removes is handled by the same command, and the edit goes through the writer Codex's own clients use.
- **jCodeMunch in the Codex user template only.** Rejected: `McpCodexParityTests` makes the two user-scope sets mirror each
  other, and a Claude shared template without it would leave a new host's Claude sessions without the tool the Codex sessions
  have.

## What would overturn it

- The user's instruction to restore a carrier, or to remove jCodeMunch or narrow its scope.
- The command center's A/B at the operating point measuring a carrier arm with a net saving: the two hook entries move back into
  the template from `held-out-hook-entries.json`, and the applier's retirement list shrinks to the file that is not restored.
