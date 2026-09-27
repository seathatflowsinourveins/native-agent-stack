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

## Addendum 2026-09-27: start-up allowances, the gateway profile and four base keys

**Status: decided; the repository side only. Not applied to any host.** Inputs: the 2026-09-27 settings synthesis
(codex rows 1-10 and 16-22, conflicts K1-K5 and K11), the workstation's verified gateway wiring of the same day, and
the token-stack verdict gaps serena#3, socraticode#2 and #3, jcodemunch-mcp#1 and #2, headroom#2, ai-memory#1 and
context-mode#1. Codex paths below were read at `rust-v0.157.1` (tag object `ac0e23e5`), OmniRoute paths at `5458026c`
(v3.8.50) or `a58000c7` (release/v3.8.51), all fetched with `gh api` on 2026-09-27.

1. **The lane also owns two start-up allowances.** When serena or socraticode is registered, the batchWrite sets the
   template's `startup_timeout_sec` (60 and 120 s). `codex mcp add` has no timeout option (its `--help`), so a server
   it registered waits the 30 s default (`codex-mcp/src/rmcp_client.rs` L103 and L342); the verdict evidence found
   both user entries without a value while the template and the main checkout's project file had one. Rollback
   treats these keys like headroom's.
2. **The gateway profile is opt-in and installed like the worker profile.** `--omniroute-profile` creates
   `$CODEX_HOME/omniroute.config.toml` from `adoption/templates/codex.omniroute.config.toml`: only when absent,
   journaled, removed by rollback only while it still holds the template. The profile file is a second user layer
   (`config/src/loader/mod.rs` L286-334), so it carries the whole route and the base template stays gateway-free (K2):
   - `cx/gpt-6-astra` with no gateway alias (K1; OmniRoute `docs/guides/CODEX-CLI-CONFIGURATION.md` L150-161);
   - upstream's provider block with the literal port 20128 (the same guide, L22-41), `env_key` plus
     `env_key_instructions` naming inventory id `omniroute` (K3), and `supports_websockets` unset (K5;
     `model-provider-info/src/lib.rs` L190-192);
   - the keyed `[shell_environment_policy.filters]` exclude for the key (`config/src/shell_environment_policy.rs`
     L28-35 and L106-110), `supports_standalone_web_search` with the under-development `standalone_web_search`
     feature (`features/src/lib.rs` L1115-1120), and `shell_snapshot = false`
     (`shell-command/src/shell_snapshot_exports.rs`; the landscape sweep's GPT-6 probe found the key in a 0644
     snapshot).

   A base `config.toml` that still carries the gateway route is reported as a host step, not written: the lane sends
   only keys it owns. The step lists the `[model_providers.omniroute]` table, a top-level `model_provider =
   "omniroute"` and a `cx/` model, the form upstream's guide puts in `config.toml` (L26-41), to be deleted together.
   A `model_provider` left without its table stops every launch without the profile with "Model provider `omniroute`
   not found" (measured). Its read-back renders the prompt input with and without `-p omniroute`.

   The profile does not choose the gateway build, but it names what a build needs. The bundled catalog runs
   `gpt-6-astra` on Responses Lite (`models-manager/models.json` L4-23), which sends no hosted tools
   (`core/src/tools/spec_plan.rs` L598-601; the unchanged upstream test `core/tests/suite/responses_lite.rs`
   L328-370 asserts `web.run` present and hosted `web_search` absent, read, not run). A search therefore goes to the
   provider-relative `alpha/search` (`codex-api/src/endpoint/search.rs` L14-15), which OmniRoute serves only with
   upstream PR #13788, open and labelled `deferred-v3.8.52` on 2026-09-27. Upstream PR #14904, also open, reports
   HTTP 500 for every `/v1/responses` request on `release/v3.8.51`. Commit `a58000c7` itself caps `gpt-6-astra` at
   `ultra`, one level above `max` (`open-sse/executors/codex/reasoningSuffix.ts` L1-31).
3. **Base keys (the synthesis's PR-F, H4 and H7).** `web_search = "live"` (`core/src/config/mod.rs` L2659-2670 and
   L3050-3094), `check_for_update_on_startup = false` (`config/src/config_toml.rs` L520-523, with the pin in
   `manifests/stack.json`), `[features] shell_snapshot = false` (`features/src/lib.rs` L1007-1012: stable, on by
   default; without a snapshot each command runs as `shell -lc`, the login shell a snapshot would have captured,
   `core/src/tools/runtimes/mod.rs` L268-276), and `[agents] default_subagent_reasoning_effort = "max"`
   (`config_toml.rs` L723-724; `core/src/agent/child_config.rs` L196-250), with a comment that `max_depth` is
   ignored for V2 models such as `gpt-6-astra`. The four dated `[projects]` trust entries are gone: none of the
   directories exists on the recording host, and nothing else in this catalog names them. The workstation's own
   `~/.codex/config.toml` already carried each of these keys on 2026-09-27 (a read of key names and these values
   only), so the template now matches it there.
4. **Template and recipe text for the token gaps.** `INCLUDE_DOT_FILES` (SocratiCode v1.14.0 `README.md` L1579) and
   the approval-never refusal (`core/src/mcp_tool_call.rs` L1610-1614 and L2436-2466) are stated where the servers
   are registered. The jCodeMunch recipe now works from the project template, not `codex mcp add`, which writes the
   user config:
   - it installs the server into the ecosystem prefix, where the template runs `${ECO_ROOT}/bin/jcodemunch-mcp`
     (bootstrap step 4's uv-tool layout);
   - it copies only the rendered `[mcp_servers.jcodemunch]` tables into the opted-in checkout or worktree. The whole
     project template also sets `approval_policy`, `sandbox_mode`, `[agents]` and a shell `PATH`, and a project
     file outranks the user config and its profiles (`config/src/config_layer_source.rs` L33-51);
   - it keeps that file, which holds host paths, out of commits through the repository's private `info/exclude`
     (git `gitrepository-layout`); the repository's `.gitignore` does not list `.codex/`.

   The headroom recipe gains its Codex registration line.

**Evidence, 2026-09-27, codex-cli 0.157.1 on the workstation:**
- **Local integration check, scratch Codex homes** under `bwrap --unshare-net` with a private `/tmp`, no sign-in and
  no gateway:
  - With the rendered base template and both profiles, `codex --strict-config -p omniroute exec` stopped at "Missing
    environment variable" for the gateway key, followed by the profile's instructions. So the configuration was
    accepted and the provider came from the profile layer. Without a profile the same command reached the network
    step, and `-p omniroute debug prompt-input` rendered the no-spawn sentence of `max`. The strict read goes
    through `exec` because `codex debug` refuses the flag at 0.157.1 ("`--strict-config` is not supported for `codex
    debug`"), so the synthesis's check "`codex --strict-config -p omniroute debug prompt-input`" cannot run as
    written.
  - `codex --strict-config -p stack-worker exec` fails with "invalid transport" on that profile's first
    `[mcp_servers.*]` table, with main's templates too. Strict mode validates each configuration file on its own as a
    whole `ConfigToml` (`config/src/loader/mod.rs` L594-600 and L625-645), and the profile's server tables name no
    command or URL. The synthesis's advice to always pass `--strict-config` (codex row 6) therefore cannot apply to
    stack-worker lanes as designed.
  - `omniroute run codex --model` defines the provider inline and adds the model as
    `-c model_providers.omniroute.model=...` (`bin/cli/commands/launch-codex.mjs` L173-194). With that exact flag
    set, Codex ignores the model key with a warning and runs another model, and under `--strict-config` it refuses
    to start with "unknown configuration field `model_providers.omniroute.model` in -c/--config override". Strict
    mode checks the override layer on its own (`config/src/loader/mod.rs` L257-258 and L647-669), so the verifier's
    "`--strict-config` rejects it" holds for the launcher. The same key passed alone is only warned about: that
    layer has an empty provider name and fails to deserialize (`config/src/config_toml.rs` L979-983 and L992-1001),
    and a layer that fails reports no ignored field (`config/src/strict_config.rs` L97-110). A first draft of this
    addendum probed only the lone key and reached the opposite conclusion; the cross-family review below caught it.
  - `codex mcp add headroom --env ...` printed "Added global MCP server" and kept the other servers'
    `startup_timeout_sec` (rewritten as floats).
  - The opt-in tests (`NAS_CODEX_INTEGRATION=1`) passed: the real app-server writes serena's allowance and rollback
    restores the file byte for byte; `--strict-config -p omniroute exec` names the missing key; and through `codex -p
    omniroute sandbox`, a fixture key reaches the command without the profile's filter and not with it, while the
    base config's `set` reaches it in both arms (a failing-first control). Three more cover the recipe's claims:
    - strict mode refuses the launcher's flag set, while the lone key is only warned about;
    - `-p stack-worker` fails under `--strict-config`, while the same home renders its prompt input without it;
    - the recipe's jCodeMunch step, copied into a trusted checkout, registers the server there, and an unrelated
      directory lists none.
- **Synthetic:**
  - the fake-codex apply, dry-run and rollback tests of the new keys and the profile, including the host step for
    base selectors;
  - a render test that runs the recipe's own `sed` range on the rendered project template.
- **Source review:** the paths above.
- **Cross-family review:** one round of GPT-6 (`cx/gpt-6-astra` at max through the local gateway, read-only)
  reported four defects in the first draft, and each was reproduced before it was fixed:
  - the jCodeMunch step copied the project template's permissions;
  - the host step missed base selectors;
  - the launcher claim rested on the lone key;
  - the install path did not match the template.

Nothing here is host acceptance or a model run.

**Alternatives considered:**
- **A `${OMNIROUTE_PORT}` placeholder that `render_config.py` renders.** Rejected (K2): it fails every host without the
  value, and 20128 is upstream's default.
- **The provider block in the base template, or in `-c` flags for interactive use.** Rejected: every session would
  route through the gateway, and the base config would stop matching the template.
- **`auth = { command = ... }` instead of `env_key`.** Kept as an arm of the preregistered comparison (K3).
- **Deleting a base `[model_providers.omniroute]` through batchWrite.** Rejected: the lane writes only keys it owns,
  and a deleted table needs a new rollback form.
- **The landscape sweep's lane-home builder reading this template.** Not done: that builder takes the model and URL as
  arguments and has its own tests. `tests/test_codex_worker_lane.py` compares every provider and feature key it
  writes with the profile's instead.
- **Installing the whole rendered project template for jCodeMunch.** Rejected: the project layer would replace the
  user's approval policy, sandbox, agents and shell `PATH` in that directory, against the codex row's "preserve the
  existing ... approval policy and sandbox settings" in `recipes/README.md`.

**Overturn conditions:**
- An OmniRoute release or a Codex pin change that alters the provider fields, the effort clamp or standalone search:
  re-read the sources and rerun the opt-in tests.
- A preregistered same-task comparison in which the gateway matches native Codex at `max`: max lanes may move to the
  route; the profile itself does not change.
- A Codex release whose `--strict-config` accepts partial profile server tables: add a strict read-back of the
  stack-worker lane.
- `codex mcp add` gaining a timeout option: the registration recipe sets the allowances and the writer can drop them.

**Not decided here:** the interactive effort (`ultra` or `max`), approving read tools one by one in interactive
sessions, and a host's own trust entries are user decisions. The latency of a login shell per command, now that
the snapshot is off, is unmeasured. The stack-worker knobs `mcp_optional_startup_grace_ms = 0`, `required = true` and
a pinned `model_reasoning_summary` wait for their measured trial.

## Addendum 2026-09-27: workstation apply, proof and the completed A0 control

The coordinator's watcher applied the lane to the workstation's real `~/.codex`
at **2026-09-27T07:51:52Z**, the first moment with no Codex process. The retained
[`apply.txt`](../../evidence/artifacts/codex-worker-lane-host-20260927/apply.txt)
confirms the quiet precondition and the installed/read-back files; the exact
watcher timestamp is coordinator-supplied. Afterwards the coordinator privately
backed up the main checkout's untracked `.codex/config.toml` and removed the
three context-mode tables named by the documented host step. No private backup
or active configuration is published.

**2026-09-27 revision erratum:** the local `apply_codex_lane.py` / `prove_codex_lane.py` revision was **main before #395; exact commit not retained**; the [#395 start-up allowances](#addendum-2026-09-27-start-up-allowances-the-gateway-profile-and-four-base-keys) are not part of this apply and remain pending until a dry run and apply at the current revision.

The [six sanitized records and evidence table](../../evidence/artifacts/codex-worker-lane-host-20260927/README.md)
retain the initial 6/7 proof with its project-binding failure, the corrected
**7/7 static proof**, and **12/12 with `--live` (five real model calls)**. The
apply/read-backs are local integration on the real Codex home; the five worker
calls additionally constitute live provider execution. They do not accept other
hosts or become unchanged upstream tests. The records retain runner summaries,
not full native events, complete invocation records or outer command exit
statuses, so the earlier formal host-acceptance limitation still applies.

The proof runner now adds an installed-skill check. A sixth worker reads one
SKILL.md from `~/.agents/skills` (or `--skill-file`); completed native tool output
must match its actual first line, and the result records the successful route.
Context-mode's [v1.0.169 `evaluateProjectContainment`](https://github.com/mksglu/context-mode/blob/v1.0.169/src/security.ts#L766)
(compiled to `security.js`, following [#852](https://github.com/mksglu/context-mode/issues/852))
can refuse a file outside the worker directory, so an ordinary `rtk cat` shell
read is accepted. No permission policy is relaxed. The event contract comes from
[openai/codex `rust-v0.157.1` exec events](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/exec/src/exec_events.rs);
the user skill location follows the [official skill documentation](https://developers.openai.com/codex/skills/).
The historical 12/12 run predates this addition. Its new control cases are
synthetic unittest events, not evidence of a sixth live call.

**Dated update to Decision 4's “which has not run”:** the tiering preregistration's
A0 control has now run. [The receipt published with #397](../../evidence/artifacts/gpt6-family-tiering-20260927/README.md)
and its [run record](../../evidence/artifacts/gpt6-family-tiering-20260927/run-record.json)
record `gpt-6-astra` at `max`, **25 successful calls**, exit 0, from
2026-09-27T07:09:02.343Z to 07:13:45.011Z. This is live provider execution of the
frozen mechanical-extraction experiment. It does not change the worker profile
or establish tiering for general worker tasks; its findings and limits stay in
that experiment's receipt. The earlier sentence remains the dated historical
state, with this addendum supplying its update.

## 2026-09-27 addendum: PR-E custom agents and Context Hub

**Scope:** the remaining PR-E items from full-save plan section 3.1. The worker
installer, base Codex template, AGENTS template and gateway profile already exist.
This addendum records new repository changes and local checks; the historical
host receipts above retain their original scope.

**F4 carrier.** The three files under `examples/codex-native/agents/` already define
`evidence-reviewer`, `isolated-builder` and `semantic-evidence-reviewer`. Append
[rtk-ai/rtk `v0.50.0`, `hooks/rtk-awareness-full.md`](https://github.com/rtk-ai/rtk/blob/v0.50.0/hooks/rtk-awareness-full.md)
verbatim and the existing marked exceptions from `codex.AGENTS.template.md` to
each role's `developer_instructions`. Preserve its original task instructions,
model/effort inheritance and sandbox settings. At openai/codex `rust-v0.157.1`,
[`agent_role_config.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/agent-roles/src/agent_role_config.rs)
parses these files and validates developer instructions,
[`discovery.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/agent-roles/src/discovery.rs)
finds agent TOML files,
[`loader.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/agent-roles/src/loader.rs)
resolves their roles, and
[`core/src/agent/role.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs)
applies developer instructions as bounded role overrides. No additional custom
agent, orchestration layer or installation mechanism is required.

**Context Hub scope.** Put `CHUB_TELEMETRY = "0"` and `CHUB_FEEDBACK = "0"` in
`codex.stack-worker.config.toml` under `[shell_environment_policy.set]`. Workers
whose `HOME` or `CHUB_DIR` differs from the user's can miss that user's
`~/.chub/config.yaml`: Context Hub `v0.1.4`
[`cli/src/lib/config.js`](https://github.com/andrewyng/context-hub/blob/v0.1.4/cli/src/lib/config.js)
resolves that directory, and
[`cli/src/lib/telemetry.js`](https://github.com/andrewyng/context-hub/blob/v0.1.4/cli/src/lib/telemetry.js)
honours each environment opt-out before loading configuration. Selecting this
worker profile opts out for shell commands even with a shared home. It does not
detect home identity. Ordinary user configuration keeps its existing scope.

**[nv] resolved: yes, in a profile-v2 file.** At `rust-v0.157.1`,
[`config/src/loader/mod.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/loader/mod.rs)
loads `$CODEX_HOME/stack-worker.config.toml` as a second user configuration layer
over `config.toml`. The field is part of
[`config_toml.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/config_toml.rs),
and [`shell_environment_policy.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/shell_environment_policy.rs)
accepts `set` as a string map.
[`protocol/src/shell_environment.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/shell_environment.rs)
applies those overrides when building a command's environment.
[`cli/src/debug_sandbox.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/cli/src/debug_sandbox.rs)
uses that environment builder for `codex sandbox`, which supplies the local
execution check. This answer concerns the separate profile file selected by
`-p stack-worker`, not a legacy `[profiles.stack-worker]` table.
[`config_layer_source.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/config_layer_source.rs)
assigns base user/profile/project/session-flag precedence 20/21/25/30: project
settings and explicit flags can override these values. They are defaults for the
worker lane, not an enforced egress boundary.

**Evidence classes.** `tests.test_codex_agents` checks every role's parsed F4
payload against the existing template and the pinned upstream hash.
`tests.test_codex_worker_lane.TemplateTests.test_profile_template` checks the
profile's two string values. Both failed before the corresponding changes.
These are repository integration checks; no upstream tests were modified.

`CodexIntegrationTests.test_worker_profile_sets_chub_opt_outs_in_an_isolated_home`
is local integration with installed `codex-cli 0.157.1`, using scratch `HOME` and
`CODEX_HOME`, an allowlisted environment and no provider or MCP execution. It
repeats with `CHUB_DIR` unset and separately overridden. For both cases, actual
shell output is asserted as follows (the base opts in to make the control visible):

| Configuration | Telemetry | Feedback | Other base `set` | Base filter |
| --- | --- | --- | --- | --- |
| Base only | `1` | `1` | kept | excluded |
| `-p stack-worker` | `0` | `0` | kept | excluded |
| Profile plus explicit telemetry `-c` override | `1` | `0` | kept | excluded |

Before the profile change, four worker/override subcases failed with feedback
still `1`; both base controls passed. With the change all six cases pass.
Run the covering modules with:

```sh
NAS_CODEX_INTEGRATION=1 python3 -m unittest tests.test_codex_agents tests.test_codex_worker_lane
```

The fixtures and unittest checks are locally authored; this is neither an
unchanged upstream test run nor live provider execution. No agent adherence,
Context Hub network behaviour, token saving or new host adoption is claimed.

**Adoption limits.** `apply_codex_lane.py` already reads the profile template and
installs its bytes; it still refuses a differing installed profile. Updating a
host's existing profile is a separate reviewed adoption step. The gateway sweep
selects `stack-worker` in its lane home, so it receives these defaults from that
profile. The interactive `omniroute` profile and base user template receive no
new unconditional CHUB setting. Changing only `CODEX_HOME` does not itself
change Context Hub's `HOME`/`CHUB_DIR` lookup. F4 changes are portable examples;
the existing copy/registration recipe remains the deployment path.

Recheck the sources and native test when Codex profile loading or Context Hub's
environment switches change. Fresh named-role execution and any token-savings
comparison remain separate qualification work.
