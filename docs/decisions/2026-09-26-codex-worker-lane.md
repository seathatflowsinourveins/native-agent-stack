# Decision: the Codex worker lane: Codex's own config writer, RTK's text inline with this catalog's exceptions, and a max-effort worker profile (2026-09-26)

**Status: decided; the repository side is in this change. Not yet applied to any host.** The workstation applies it
in a coordinated quiet window with `tools/adoption/apply_codex_lane.py`, then runs `tools/adoption/prove_codex_lane.py`.
Its dry run on the workstation's real Codex home passed, and wrote nothing there
([evidence](../../evidence/artifacts/codex-worker-lane-20260926/README.md)).

**Scope:**
- new: `tools/adoption/apply_codex_lane.py`, `tools/adoption/prove_codex_lane.py`,
  `adoption/templates/codex.AGENTS.template.md`, `adoption/templates/codex.stack-worker.config.toml`,
  `tests/test_codex_worker_lane.py` with its fixtures, this record and its evidence;
- changed: one comment in `adoption/templates/codex.config.template.toml`, `scripts/codex_quota.py` (its
  app-server client takes a caller's argv and environment and keeps the server's error object, which it never
  prints), `recipes/README.md` and `docs/token-session-handbook.md`.
- untouched: `scripts/adoption_status.py`, whose RTK check (#368) is reused as it is; jCodeMunch's scope (below);
  every Claude-side file.

## Context

Three gaps kept GPT-6 Codex workers from running inside the harness with the token stack, all confirmed on the
workstation (codex-cli 0.157.1) before this change:

1. **context-mode bound to the wrong directory.** A Codex session outside the main checkout used the plugin's
   own server, which starts in the plugin cache and then follows the newest session log. From the main checkout,
   an untracked project config pinned every session to the checkout. `codex mcp get context-mode --json` showed
   `cwd` as the plugin cache and as the checkout. The template already has the fix: #333's session-bound entry,
   which is the cm-deep plan's step 3 (H4). No host had it.
2. **RTK's instructions never reached the model.** The global `AGENTS.md` held one `@<CODEX_HOME>/RTK.md` line,
   the form `rtk init -g --codex` writes. Codex expands no `@` reference (`codex-rs/core/src/agents_md.rs` at
   `rust-v0.157.1`), so `codex debug prompt-input` showed the path and 0 lines of RTK text or of the top rule.
3. **Workers could not call three token-stack servers.** Under `approval_policy = "never"`, a `codex exec` worker's
   `ai-memory` `memory_query` was refused with "MCP tool call requires approval, but approval policy is never".
   There was also no worker profile.

## Decision

1. **Codex's own writer for `config.toml`.** The script sends `config/batchWrite` to `codex app-server` over
   stdio, with the `expectedVersion` that a `config/read` in the same session returned
   (`app-server-protocol/src/protocol/v2/config.rs` `ConfigBatchWriteParams`, `ConfigEdit`, `ConfigReadParams`;
   `app-server/src/config_manager_service.rs` `apply_edits`). It uses the quota probe's app-server client
   (`scripts/codex_quota.py`), not a new one. Probed on 0.157.1 against scratch homes:
   - A stale version is refused with `configVersionConflict`.
   - Comments and integer types survive, and only the edited tables change.
   - A wrong type is refused. An unknown key under `mcp_servers.<id>` is accepted, so the script sends only its
     own key paths and reads every one back.
   - A `null` value deletes a key, but leaves the empty table header behind. Rollback therefore deletes the
     shallowest table the run created, and the integration test restores the file byte for byte.
   - `--profile` is refused for `app-server` (`cli/src/main.rs` `profile_v2_for_subcommand`), and `apply_edits`
     refuses any file but the user config. So the profile is a plain atomic create, and a project config is a host
     step.
2. **The context-mode entry is the template's, exactly as the cm-deep plan's step 3 requires.** That means upstream
   `start.mjs` from the npm pin through `${ECO_ROOT}/bin/node`, no `cwd`, `startup_timeout_sec = 60`,
   `default_tools_approval_mode = "approve"`, the `RTK_TELEMETRY_DISABLED`, `PATH` and `CONTEXT_MODE_PLATFORM`
   env keys, and `[plugins."context-mode@context-mode".mcp_servers.context-mode] enabled = false`. The same write
   adds headroom's two Hugging Face offline variables, the host residual of the 2026-09-25 decision's addendum
   (item 3). The entry is interim: it goes when upstream binds a Codex session to its own directory.
3. **`AGENTS.md` carries the text itself.** Codex reads one global file: `AGENTS.override.md` when it has text,
   else `AGENTS.md` (the Codex AGENTS.md guide, read 2026-09-26). The block has three parts:
   - the top rule (120 words, marker `native-agent-stack:top-rule`);
   - rtk-ai/rtk v0.50.0's `hooks/rtk-awareness-full.md`, verbatim (tag commit `1d87b8e7`, sha256 `278274ef…`,
     byte-identical to this host's `RTK.md`);
   - a marked exceptions block.

   The exceptions block is needed because an explicit `rtk` prefix skips `exclude_commands`
   (`src/discover/registry.rs:1690-1693` at v0.50.0). Its sources:
   - the recipe's four hook exclusions (`git show REV:path` in any form, `diff`, `git branch`);
   - the full-save study's fifth: standalone `jq`, where 60 of 152 rewrites were truncated to 40 lines of 120
     characters;
   - a complete `git log`, and `find` on a path that may be missing (both in the recipe);
   - no `rtk` before a shell builtin. Upstream issue #3969 is open and its fix #4175 is not merged (checked with
     `gh api` on 2026-09-26). On this host `rtk cd /tmp && echo REACHED`, `rtk export` and `rtk source` all exit 127.

   The upstream text stays verbatim, so `scripts/adoption_status.py`'s check (RTK.md's text inline in what Codex
   reads) passes unchanged. rtk's own `@RTK.md` line is kept, so `rtk init --codex --uninstall` still finds it.
4. **The worker profile, `stack-worker.config.toml`.** Codex 0.134.0 and later layer a profile over `config.toml`
   (`$CODEX_HOME/<name>.config.toml`: `config/src/loader/mod.rs:286-330`, precedence 21; the Codex advanced-config
   page, read 2026-09-26). The layer is deep-merged, so a profile table that names only `enabled_tools` amends the
   user-scope server (`codex -p stack-worker mcp get ai-memory --json` shows the merged entry).
   - **`model = "gpt-6-astra"`, `model_reasoning_effort = "max"`.** `max` is what every GPT-6 step here runs at:
     the control arm A0 of the GPT-6 tiering preregistration (#359, `blueprints/convergence-practice/
     gpt6-family-tiering-20260926`), which has not run. It is also the child effort of the
     [max-effort decision](2026-09-23-max-effort-default.md). The user default stays `ultra`, the Codex
     counterpart of an orchestrating main loop. For `gpt-6-astra`, `ultra` does not send `max`: the request
     carries the catalog's `multi_agent_reasoning_effort`, which is `xhigh` (`codex debug models --bundled`;
     `ModelInfo::resolve_reasoning_effort` in `protocol/src/openai_models/reasoning_effort.rs`, applied in
     `core/src/client.rs` `build_reasoning`). The model-visible input also differs (`core/src/session/
     multi_agents.rs`):
     - at `ultra`, "Proactive multi-agent delegation is active";
     - at `max`, "Do not spawn sub-agents unless the user or applicable AGENTS.md/skill instructions explicitly
       ask".

     That second line is this harness's no-second-layer rule for children.
   - **The launch pins model, effort and web search too.** A project `.codex/config.toml` outranks a profile file
     (`config/src/config_layer_source.rs`: profile 21, project 25), and `-c` outranks both (session flags, 30).
     So every worker starts with `codex exec -p stack-worker -m gpt-6-astra -c model_reasoning_effort="max" -c
     web_search="live" ...`, and the profile is a convenience that carries the tool settings below.
     `prove_codex_lane.py` starts its workers exactly so (`apply_codex_lane.worker_pins`, read from the profile
     template), and the apply prints the command.
   - **`web_search = "live"`.** Exec's default is `cached`, an index only (the recipe's codex row), and a
     read-only or workspace-write sandbox keeps it (the Codex config reference defaults to `live` only for a
     full-access sandbox). A lane that must not browse passes `-c web_search="disabled"`.
   - **Read tools approved for three servers.** ai-memory 2.4.1 (23 tools), Headroom 0.37.0 (3 tools) and
     SocratiCode 1.14.0 (`server.tool` registrations) declare no MCP tool annotations. Under the default `auto`
     mode Codex then requires approval for every call (`core/src/mcp_tool_call.rs` `requires_mcp_tool_approval`),
     which `approval_policy = "never"` refuses. Serena's and qmd's read tools carry `readOnlyHint` and pass. This
     was read through `codex app-server` `mcpServerStatus/list`.

     So these three servers get `default_tools_approval_mode = "approve"` with `enabled_tools` limited to read
     tools. Both keys are confirmed in `config/src/mcp_types.rs` at the tag and in the Codex config reference.
     The tool lists come from each server's own tool descriptions:
     - ai-memory's writes and its LLM-backed `memory_explore` are left out;
     - SocratiCode's graph and symbol tools are left out, because with `SOCRATICODE_WATCHER=auto` they build a
       missing graph as a side effect (`dist/tools/graph-tools.js:29-44`).
   - **`ctx_upgrade` and `ctx_purge` are disabled for workers.** `ctx_upgrade` returns the `context-mode upgrade`
     command (`src/server.ts:4269-4290` at `6f0cc684`), and upgrade's `configureAllHooks` removes
     `[mcp_servers.context-mode]` from `config.toml` (`src/cli.ts:1892`; `src/adapters/codex/index.ts:879-887`).
     `ctx_purge` deletes indexed content.
5. **Profile scope, not user scope, for these tool settings.** The full-save plan's step A8 wrote them to user scope.
   The profile keeps interactive sessions' tool surfaces as they are, and it keeps a lane that approves writes
   interactively working. The cost: a Codex session run without `-p stack-worker` still gets the refusals.
6. **jCodeMunch stays project-scoped.** The adoption plan's D14 (a disabled user entry, enabled in the profile) is
   not adopted. [Decision 2 of the Codex MCP scope record](2026-09-25-codex-mcp-scope.md) keeps it project-scoped
   until a retrieval comparison on Codex calls shows it materially ahead of Serena and SocratiCode. That condition
   is unmet: the 2026-09-25 counts were 15 jCodeMunch calls against 33 Serena and 7 SocratiCode, and hit@5 was
   0.25 against SocratiCode's 0.85 (`adoption/bootstrap.md`). The profile would put jCodeMunch's "prefer me"
   instructions into exactly the max-quality lanes.

## Evidence

The workstation, 2026-09-26, codex-cli 0.157.1: [`evidence/artifacts/codex-worker-lane-20260926/`](../../evidence/artifacts/codex-worker-lane-20260926/README.md).

- **Source.** Every Codex file cited here hashes the same as `openai/codex` at `rust-v0.157.1` (`gh api`). The
  rtk, context-mode and SocratiCode files are at the pins named above.
- **Dry run on the real Codex home.** It exited 0 and the rehearsal passed. `config.toml`, `AGENTS.md`, `RTK.md`
  and `hooks.json` had the same hashes and mtimes afterwards, and no profile was created.
- **Prove before apply, on the real home.** It failed as expected, 2 pass and 5 fail:
  - top-rule lines 0;
  - `rtk_instructions_inline` false;
  - context-mode's `cwd` was the plugin cache from `/` and the checkout from the checkout.

  Blind isolation and RTK exactness passed. `rtk git show` returned 8,248 of 21,300 bytes.
- **Rehearsal on a scratch home (copies of this host's three files; no `auth.json`).**
  - apply, a second apply ("already in place"), rollback (both files byte-identical, profile removed) and a second
    rollback ("already") all behaved as intended;
  - prove passed 7 of 7 after apply, with a scratch project standing in for the main checkout after the host step.
- **Live rehearsal (real model calls, on the real home, through `-c` overrides; no Codex file changed).**
  - two concurrent workers each got their own directory from `ctx_execute pwd`;
  - `memory_query` completed with the profile's keys and was refused without them;
  - a worker given the block as project `AGENTS.md` ran `rtk git status --short` and then
    `rtk proxy git show HEAD:big.txt`, byte-exact (21,300 bytes).

  An earlier prompt that did not name the shell tool had that worker read the blob through `ctx_execute`. The
  prove prompt now names the shell tool.
- **Effort and precedence read-backs.** The bundled catalog gives `gpt-6-astra` a `multi_agent_reasoning_effort`
  of `xhigh`. In a trusted scratch project whose config sets `ultra`, `-p stack-worker` still rendered proactive
  delegation, so the project won over the profile, and adding `-c model_reasoning_effort="max"` rendered the
  no-spawn sentence.
- **Tests.** `tests/test_codex_worker_lane.py`: templates, block handling, and apply, rollback and conflict flows
  against a fake codex (synthetic), and the pinned worker command line. The prove verdicts run on events from real
  `codex exec --json` runs. Two opt-in tests with the real codex (`NAS_CODEX_INTEGRATION=1`) passed on the
  workstation: the app-server apply and byte-exact rollback, and the project-over-profile precedence with the pins
  winning.

**Evidence classes:**
- source review: the protocol, loader, approval and rtk/context-mode/SocratiCode reads;
- local integration check: the dry run, the rehearsals, the opt-in test and `prove_codex_lane.py`, including
  `--live` after the real apply;
- synthetic: the fake-codex tests.

Nothing here is host acceptance. The runner's JSON declares `evidence_class: "local integration check"` and
`host_acceptance: false`. Under [the acceptance evidence policy](../acceptance-evidence-policy.md), acceptance
requires the official pinned installation and upstream commands, with retained invocation arguments, actual
returned output and exit statuses, and declared sanitization. A passing local runner summary cannot replace that
evidence.

## Alternatives considered

- **u4's tomlkit editor.** Rejected: it is not Codex's writer, it has no version guard, and it fails review-u4
  #4/#5.
- **`codex mcp add`.** Rejected: it replaces the whole `[mcp_servers]` table (`ReplaceMcpServers`) and resets fields
  it does not take (review-u4 #5).
- **RTK.md verbatim alone.** Rejected: its "the prefix is always safe" is wrong for the exceptions above.
- **A rewritten RTK text.** Rejected: it drops upstream alignment and fails the `adoption_status` check.
- **Removing rtk's `@RTK.md` line.** Rejected: rtk owns it.
- **Per-tool `approval_mode` instead of `enabled_tools`.** Rejected: it keeps write tools listed, and they are
  refused anyway.
- **Tool settings at user scope.** Rejected; see decision 5.
- **The Codex-cache launcher.** Rejected: it has the Layer 1 cross-write hazard (cm-deep plan, H4).
- **rtk's Codex hook.** Still not qualified (the recipe).
- **jCodeMunch in the profile.** Rejected; see decision 6.

## Overturn conditions

- An rtk release that contains #4175: re-copy the upstream text and drop the builtin line. A release that applies
  `exclude_commands` to explicit `rtk` commands: drop the matching exceptions.
- Upstream context-mode binding a Codex session to its own directory, or Codex letting user config set a plugin
  server's `cwd`: drop the interim entry.
- A Codex release whose writer can edit a project config: script the host step.
- ai-memory, Headroom or SocratiCode declaring read-only annotations: drop that server's approval setting and
  `enabled_tools`. A pinned upgrade that renames tools, such as SocratiCode 1.15.0: re-check the lists.
- A measured comparison showing that a lower effort, or `ultra`, matches `max` for these lanes at lower cost: the
  tiering decision covers mechanical extraction only, and changes that stage's own command, not this profile.
- jCodeMunch meeting Decision 2's condition.

## Limitations and residuals

- **Runner retention.** `live_checks` examines native events in memory but retains only verdicts, worker exits,
  elapsed time, timeout/cleanup failures and usage. Native events, full invocation arguments and returned output
  are discarded. Sanitized event retention is deferred: retaining model/tool payloads needs an explicit field and
  redaction policy, and this bounded repair does not establish one. The JSON declares these omissions; its
  summaries can still contain unredacted local paths and must remain private. This remains a local integration
  limitation even when every verdict passes.
- **Not applied.** The host changes wait for the coordinated window, and the host step (removing three tables from
  the main checkout's untracked `.codex/config.toml`) is manual.
- **Sessions without the profile.** They keep the approval refusals for the three servers, and they keep
  `ctx_upgrade` approved.
- **Claude-side writes.** After the apply, `start.mjs` writes its Layer 3/4 files under the Claude configuration
  directory, as the plugin's own server already does (cm-deep plan, row 19b).
- **The live rehearsal was not the applied state.** It expressed the post-apply state as `-c` overrides, and gave
  the block as a project `AGENTS.md`, not the global file.
- **The rtk-worker result is one run.** It measures behaviour, not a guarantee.
- **The profile depends on the user-scope servers.** It amends servers the user template registers; on a home
  without them, `-p stack-worker` fails. The dry run's read-back catches that.
