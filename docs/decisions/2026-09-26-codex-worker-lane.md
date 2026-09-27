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

## 2026-09-27 addendum: Custom agents and Context Hub

**Scope:** custom-agent developer instructions and the worker profile's Context
Hub opt-outs, with the dated repair below for MCP startup and approval settings. The worker
installer, base Codex template, AGENTS template and gateway profile already exist.
This addendum records new repository changes and local checks; the historical
host receipts above retain their original scope.

**[F4 RTK guidance carrier](2026-09-26-token-practice-f1-f9.md#f4-codex-rtk-guidance-2026-09-26).** The three files under `examples/codex-native/agents/` already define
`evidence-reviewer`, `isolated-builder` and `semantic-evidence-reviewer`. Append
[rtk-ai/rtk `v0.50.0`, `hooks/rtk-awareness-full.md`](https://github.com/rtk-ai/rtk/blob/v0.50.0/hooks/rtk-awareness-full.md)
verbatim and the existing marked exceptions from `codex.AGENTS.template.md` to
each role's `developer_instructions`. Preserve its original task instructions,
model/effort inheritance and parent sandbox authority. **2026-09-27 erratum:**
the semantic reviewer's `sandbox_mode = "read-only"` has no effect at this pin.
A role file cannot set or narrow the sandbox:
[`role.rs:36–48`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L36-L48)
lists the allowed overrides,
[`119–126`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L119-L126)
builds the projected layer, and
[`182–189`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agent/role.rs#L182-L189)
clones the parent configuration. All three roles inherit the parent's sandbox.
Launch the parent with `-s read-only` to enforce read-only access for a semantic
reviewer; its no-edit rule is a prompt instruction. The trusted-project
template's `danger-full-access` parent passes that authority to its children.
At openai/codex `rust-v0.157.1`,
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
detect home identity. The dated amendments in the
[recipe](../../recipes/README.md#context-hub-opt-out) and
[macOS guide](../../adoption/platforms/macos-arm64.md) make this profile the one
unconditional carrier; ordinary invocations retain the home-only environment rule.

**Profile environment merge gate: passed for a profile-v2 file.** At `rust-v0.157.1`,
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
These are structural validation; no upstream tests were modified.

`CodexIntegrationTests.test_worker_profile_sets_chub_opt_outs_in_an_isolated_home`
is local integration with installed `codex-cli 0.157.1`, using scratch `HOME` and
`CODEX_HOME`, an allowlisted environment and no provider or MCP execution. It
now asserts `chubdir=unset` and the separate override path, demonstrating that
the profile leaves `CHUB_DIR` unchanged. The override directory exists. **2026-09-27
erratum:** the original two subcases did not print or assert `CHUB_DIR`, so the
earlier passing runs established only the other environment values. For both cases, actual
shell output is asserted as follows (the base opts in to make the control visible):

| Configuration | Telemetry | Feedback | Other base `set` | Base filter |
| --- | --- | --- | --- | --- |
| Base only | `1` | `1` | kept | excluded |
| `-p stack-worker` | `0` | `0` | kept | excluded |
| Profile plus explicit telemetry `-c` override | `1` | `0` | kept | excluded |

Before the profile change, four worker/override subcases failed with feedback
still `1`; both base controls passed. With the change all six cases passed for
the original four-field probe. Returned commands and summaries appear below;
the later repair run also checks `CHUB_DIR` and sandbox availability.

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

Two HOME-overriding launchers **do not receive these opt-outs**:
[`tools/sota-convergence/codex_lane.py`](../../tools/sota-convergence/codex_lane.py)
(`ISOLATION_ARGS`, `child_env`) and
[`gpt6-family-tiering-20260926/run_arm.py`](../../blueprints/convergence-practice/gpt6-family-tiering-20260926/run_arm.py)
(`CODEX_ARGV`, the per-call environment). They pass `--ignore-user-config` and
omit `-p stack-worker`. Follow-up for those lane owners: pass
`-c 'shell_environment_policy.set.CHUB_TELEMETRY="0"'` and
`-c 'shell_environment_policy.set.CHUB_FEEDBACK="0"'`, citing the pinned
[Codex environment builder](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/shell_environment.rs)
and [Context Hub switches](https://github.com/andrewyng/context-hub/blob/v0.1.4/cli/src/lib/telemetry.js),
then qualify their `codex exec` login-shell path. This template repair does not
change those launchers or claim they are covered by the gateway sweep.

Recheck the sources and native test when Codex profile loading or Context Hub's
environment switches change. Fresh named-role execution and any token-savings
comparison remain separate qualification work.

### 2026-09-27 repair: Worktree MCP settings

The worker profile adds partial `[mcp_servers.serena]` and
`[mcp_servers.codebase-memory]` tables with `startup_timeout_sec = 60`.
[`RawMcpServerConfig.startup_timeout_sec`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/config.schema.json)
defines the setting; [`rmcp_client.rs:103`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/rmcp_client.rs#L103)
sets the 30-second default consumed by
[`connection_manager.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/connection_manager.rs).
The partial tables retain user-scope commands. The header's existing layering
rule still applies: profile 21 < project 25 < `-c` 30. This is configuration
coverage for worktrees; successful server startup awaits the coordinator's host
matrix rerun after adoption.

The project template sets jcodemunch's `default_tools_approval_mode = "approve"`
and `enabled_tools = ["route", "menu", "order"]`, retaining its project scope
from [the scope decision, item 2](2026-09-25-codex-mcp-scope.md).
[`mcp/mod.rs:89–98`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/mcp/mod.rs#L89-L98)
auto-approves `Approve`; the same tag's config schema defines
`RawMcpServerConfig` and `McpServerToolConfig`. jgravelle/jcodemunch-mcp
`1.108.319`, commit `8f7b34abe16fb459e0bf1c04747d584216dfe32e`, defines this
front door in [`counter.py`](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/counter.py).
[`server.py:5500–5511`](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py#L5500-L5511)
makes `order` read-only by default (`allow_state_change=false`), but explicit
`true` permits state-changing catalog actions. `route` defaults `execute=false`
and [rejects state-changing automatic dispatch](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py#L5535-L5577).
The allowlist limits the exposed tools; it is not an enforced read-only boundary.
No user-scope jcodemunch entry or host configuration is changed here.

### Returned local evidence, 2026-09-27

These are returned unittest summaries, not generated acceptance claims. Run
commands from the checkout root. Historical build runs below preceded the
repair and retain their original scope and output. The original template/hash
checks are **structural validation**:

```text
rtk python3 -m unittest tests.test_codex_agents
before role payload edits: exit=1
Ran 1 test in 0.001s
FAILED (failures=3)
after role edits and correcting the hash separator: exit=0
Ran 1 test in 0.001s
OK

rtk python3 -m unittest tests.test_codex_worker_lane.TemplateTests.test_profile_template
before profile edit: exit=1
Ran 1 test in 0.001s
FAILED (failures=1)
None != {'set': {'CHUB_TELEMETRY': '0', 'CHUB_FEEDBACK': '0'}}
```

The original environment merge control is **local native integration with
synthetic inputs**, using installed Codex 0.157.1 and no provider or MCP call:

```text
NAS_CODEX_INTEGRATION=1 rtk python3 -m unittest tests.test_codex_worker_lane.CodexIntegrationTests.test_worker_profile_sets_chub_opt_outs_in_an_isolated_home
before profile edit: exit=1
Ran 1 test in 0.765s
FAILED (failures=4)
Actual failing output: ['telemetry=1', 'feedback=1', 'base=kept', 'filter=absent']

NAS_CODEX_INTEGRATION=1 rtk python3 -m unittest tests.test_codex_worker_lane.TemplateTests.test_profile_template tests.test_codex_worker_lane.CodexIntegrationTests.test_worker_profile_sets_chub_opt_outs_in_an_isolated_home
after profile edit: exit=0
Ran 2 tests in 0.724s
OK
```

The second command combines one structural check with one native integration
check. Its six native cases checked the four fields shown above; preservation
of `CHUB_DIR` was not yet observed. One later combined run
(`NAS_CODEX_INTEGRATION=1 rtk python3 -m unittest tests.test_codex_agents tests.test_codex_worker_lane`)
exceeded its 55-second outer limit. It returned no completed unittest result
and is not passing evidence. These **two separate commands** completed instead:

```text
NAS_CODEX_INTEGRATION=0 rtk python3 -m unittest -v tests.test_codex_agents tests.test_codex_worker_lane
exit=0
Ran 55 tests in 23.014s
OK (skipped=8)

NAS_CODEX_INTEGRATION=1 rtk python3 -m unittest -v tests.test_codex_worker_lane.CodexIntegrationTests
exit=0
Ran 8 tests in 32.551s
OK
```

The first command covers structural validation and locally authored synthetic
fixtures; the second covers the same eight native tests skipped in the first.
There were 55 distinct tests, not 63. An independent coordinator rerun of the
pre-repair build state, with `TMPDIR=/var/tmp/claude-w3-codex-agents`, confirmed collection
and native execution (local integration evidence, supplied 2026-09-27 ~14:00Z):

```text
python3 -m unittest -v tests.test_codex_agents tests.test_codex_worker_lane
exit=0
Ran 55 tests in 22.392s
OK (skipped=8)

NAS_CODEX_INTEGRATION=1 python3 -m unittest -v tests.test_codex_worker_lane.CodexIntegrationTests
exit=0
Ran 8 tests in 32.455s
OK
```

Both the custom-agent payload test and the CHUB native method were collected.
All eight native methods passed, including the CHUB and per-project jcodemunch
registration methods. These reruns precede the repair's new controls.

**Repair controls.** All repair unittest runs set
`TMPDIR=/var/tmp/claude-w3-codex-agents`. New template controls are structural
validation; `SandboxProbeControlTests` uses synthetic subprocess results;
the CHUB observation test executes the native sandbox. Each added control failed
before its correction:

| Command (after `rtk python3 -m unittest -v`) | Before correction | After correction |
| --- | --- | --- |
| `tests.test_codex_worker_lane.TemplateTests.test_worker_startup_timeouts_layer_over_user_servers` | exit 1; `Ran 1 test in 0.002s`; `FAILED (failures=2)`; both tables absent | exit 0; `Ran 1 test in 0.001s`; `OK` |
| `tests.test_codex_worker_lane.TemplateTests.test_project_jcodemunch_approves_only_read_front_door` | exit 1; `Ran 1 test in 0.001s`; `FAILED (failures=1)`; approval mode absent | exit 0; `Ran 1 test in 0.001s`; `OK` |
| `tests.test_codex_worker_lane.SandboxProbeControlTests` | exit 1; `Ran 2 tests in 0.009s`; `FAILED (failures=1)`; unavailable sandbox asserted failure | covered by the three-test run below |
| `tests.test_codex_worker_lane.CodexIntegrationTests.test_worker_profile_sets_chub_opt_outs_in_an_isolated_home` with `NAS_CODEX_INTEGRATION=1` | exit 1; `Ran 1 test in 0.919s`; `FAILED (failures=6)`; `chubdir` absent from output | covered by the three-test run below |

```text
NAS_CODEX_INTEGRATION=1 rtk python3 -m unittest -v tests.test_codex_worker_lane.SandboxProbeControlTests tests.test_codex_worker_lane.CodexIntegrationTests.test_worker_profile_sets_chub_opt_outs_in_an_isolated_home
exit=0
Ran 3 tests in 0.873s
OK
```

The probe now collects all six runs, uses the sibling's 120-second timeout,
and skips when every sandbox invocation fails. Partial failures remain failures.
The CHUB_DIR path is asserted internally but no scratch path is published here.
The first repair native-class run
(`NAS_CODEX_INTEGRATION=1 rtk python3 -m unittest -v tests.test_codex_worker_lane.CodexIntegrationTests`)
returned exit 1, `Ran 8 tests in 22.040s`, `FAILED (failures=2)`. Two older
fixtures reported `invalid transport`: they lacked base registrations for the
profile's new partial tables.
The corrected fixtures register both user-scope servers before loading the
profile, following the pinned config schema. The completed checks are:

```sh
export TMPDIR=/var/tmp/claude-w3-codex-agents
NAS_CODEX_INTEGRATION=0 rtk python3 -m unittest -v tests.test_codex_agents tests.test_codex_worker_lane
NAS_CODEX_INTEGRATION=1 rtk python3 -m unittest -v tests.test_codex_worker_lane.CodexIntegrationTests
NAS_CODEX_INTEGRATION=0 rtk python3 -m unittest -v tests.test_render_config
```

Returned results, in that order:

```text
exit=0
Ran 59 tests in 26.667s
OK (skipped=8)

exit=0
Ran 8 tests in 34.110s
OK

exit=0
Ran 21 tests in 0.608s
OK
```

The 59-test run covers structural checks and synthetic fixtures; the native
eight cover its skips and passed after the fixture correction. Rendering is
local integration with synthetic host settings. **Unchanged upstream tests,
live provider execution, Context Hub network runs and token measurements: none.**
The `codex exec` login-shell environment path was not separately qualified.
F4 duplication in a spawned role when user AGENTS already contains F4 remains
unverified; one block per role file does not establish one block per child rollout.

## 2026-09-27 addendum: Required start-up

**Status: decided; the repository side only. Not applied to any host.** It settles the `required = true` knob that
the [start-up allowances addendum](#addendum-2026-09-27-start-up-allowances-the-gateway-profile-and-four-base-keys)
left for a measured trial; that addendum's text stays as the dated state. Codex paths below were read at
`rust-v0.157.1` (commit `36650394c5b38c2990ccf2a3457165ca3e9d9726`, tag object `ac0e23e5`) with `gh api` on
2026-09-27.

**Problem.** A peer measurement relayed on 2026-09-27 (its artifact is not retained on this branch): on the OmniRoute
gateway route, serena and codebase-memory were missing from GPT-6's first-turn tools and appeared after a 75 s sleep
in the same turn. The source explains it:
- Every enabled server starts in the background, and a session start waits only for servers marked `required`
  ([`connection_manager.rs` L246-251](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/connection_manager.rs#L246-L251);
  [`required.rs` L15-59](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/connection_manager/required.rs#L15-L59),
  called at `core/src/session/mcp_runtime.rs` L148 and awaited with `?` at `core/src/session/session.rs` L1860-1867).
- Each model request rebuilds the tool list. A server that is not required and is still starting gets one shared
  grace from the first build, 1 s by default
  ([`mcp/mod.rs` L195](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/mcp/mod.rs#L195)),
  and is then left out of that request
  ([`tool_catalog.rs` L251-277](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/connection_manager/tool_catalog.rs#L251-L277)).
  A fresh `codex exec` has no cached catalog.
- The built-in OpenAI provider supports websockets (`model-provider-info/src/lib.rs` L549), and its start-up prewarm
  builds a tool list and opens the socket before the first turn. A custom provider defaults to no websockets (L190-192;
  the gateway profile leaves the key unset), and the prewarm returns at once (`core/src/session_startup_prewarm.rs`
  L198-208, `core/src/client.rs` L1020-1028). The native route hides the race by timing; the gateway route does not.
- A handshake probe of the installed servers from this worktree (stdio `initialize` and `tools/list`, not a Codex
  run): serena answered `initialize` in 1.53-2.24 s (24 tools), codebase-memory in 1.20-1.25 s (17 tools), three runs
  each, each timed from that server's own launch. The grace ends 1 s after Codex's first tool-list build instead
  ([`tool_catalog.rs` L252-258](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/connection_manager/tool_catalog.rs#L252-L258)),
  and in the race test's two failing-first runs below (fixture servers, template without `required`) the first
  request left 1.63 s and 1.69 s after `codex` started. Serena's slower starts (up to 2.24 s) fall past that point.
  These runs do not show codebase-memory's 1.20-1.25 s missing it; that it was missing on the gateway route rests on
  the relayed peer measurement. Both are far inside the template's `startup_timeout_sec = 60`, which Codex applies
  to each start-up step separately, not as one overall deadline: the client start, `initialize` and the first tool
  listing
  ([`rmcp_client.rs` L354](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/rmcp_client.rs#L354),
  [L946](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/rmcp_client.rs#L946) and
  [L1015](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/rmcp_client.rs#L1015)).

**Decision.**
1. The worker profile's partial `[mcp_servers.serena]` and `[mcp_servers.codebase-memory]` tables gain
   `required = true`
   ([`mcp_types.rs` L233-235](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/mcp_types.rs#L233-L235):
   "When `true`, `codex exec` exits with an error if this MCP server fails to initialize"). Every `-p stack-worker`
   session start, `codex debug prompt-input` included (it starts a thread, `core/src/prompt_debug.rs` L72-74), waits
   for both and stops with "required MCP servers failed to initialize: <name>: <error>" (`required.rs` L51-58) when
   one does not start. Starting includes the first tool listing (`required.rs` L31 awaits the client that
   `start_server_task` returns after `initialize` and `tools/list`, `rmcp_client.rs` L908-1020), and each of its
   steps has the server's own `startup_timeout_sec` (60 s in the template). A worker never runs without these tools.
2. `mcp_optional_startup_grace_ms` stays unset (alternatives below).
3. `tools/adoption/apply_codex_lane.py`: the dry run's rehearsal makes the two optional again for its one
   `-p stack-worker` read, with `-c mcp_servers.<name>.required=false` (session flags 30 outrank the profile 21), and
   says so. Its scratch `HOME` cannot start codebase-memory: codebase-memory-mcp 0.11.0 keeps one account daemon and
   refuses a second cache directory (measured below). The apply's read-back and `prove_codex_lane.py`'s profile
   check start both under the account's `HOME`, as a worker does. A failure keeps the whole required-server error
   and the names read from it, best effort (`required_failure` in the run record), and points to the rollback.
4. The landscape sweep's gateway lane copies the profile verbatim and sets only `CODEX_HOME`, so it inherits the
   wait. Its staging check already accepts partial tables for servers the rendered host config defines.

**Evidence, 2026-09-27, codex-cli 0.157.1 on the workstation.** Every unittest run set
`TMPDIR=/var/tmp/claude-codex-startup`, and each check ran before its change as well as after. The structural row's
before run shows its template assertion discriminates; the two native rows' before runs are the behavioural
failing-first evidence; the synthetic row's before run failed only because the helpers did not exist yet:

| Check, in `tests/test_codex_worker_lane.py` | Class | Before | After |
| --- | --- | --- | --- |
| `TemplateTests.test_worker_startup_timeouts_layer_over_user_servers` | structural | template without `required`: exit 1, `Ran 1 test`, `FAILED (failures=3)` | exit 0, `Ran 12 tests` (`TemplateTests`), `OK` |
| `CodexIntegrationTests.test_required_servers_start_before_the_first_request_on_a_custom_provider` | native integration, synthetic inputs | template without `required`: exit 1, `FAILED (failures=2)`; first request at 1.63 s, not after the servers' 5 s, and a serena that cannot start did not stop the run (exit 0). With the strengthened check (below), on a copy of the tree whose template lacks the two `required` lines: exit 1, `FAILED (failures=3)`; first request at 1.69 s, the first turn's tool list lacked `mcp__serena__fixture_serena` and `mcp__codebase_memory__fixture_codebase_memory`, so it did not differ from the control's, and the serena that cannot start again did not stop the run | exit 0, `Ran 1 test`, `OK`, and in the class run below |
| `CodexIntegrationTests.test_real_app_server_apply_and_byte_exact_rollback` | native integration, synthetic inputs | script without the relaxation: exit 1, `FAILED (failures=1)`; the dry run's rehearsal, under the real codex, failed with "required MCP servers failed to initialize: codebase-memory: handshaking with MCP server failed: connection closed: initialize response". This is the behavioural failing-first evidence for the relaxation. | exit 0, `Ran 1 test`, `OK` |
| `ApplyFlowTests`, `RequiredStartTests` | synthetic | script without the helpers: exit 1, `Ran 21 tests`, `FAILED (errors=3)`, all three `AttributeError` for the missing `required_servers`, `relaxed_required_flags` and `required_start_failures`: absent code, not a behavioural failure | exit 0, `Ran 21 tests`, `OK` |
| `RequiredStartTests` and `ApplyFlowTests.test_the_dry_run_relaxes_required_servers_and_the_apply_read_back_starts_them` (GPT-6 repair round) | synthetic | the reviewed head's script (`a5296a3c`) under the new tests: exit 1, `Ran 4 tests`, `FAILED (failures=2)`; it read a multiline error as `['codebase-memory']`, dropping serena, and its read-back message lacked the whole error | exit 0, `Ran 4 tests`, `OK`; with all of `ApplyFlowTests`: `Ran 22 tests`, `OK` |

- The race test runs the real codex under `bwrap --unshare-net` with scratch homes, fixture stdio MCP servers that
  answer `initialize` after 5 s, and a fake Responses endpoint on loopback; no sign-in, gateway, model or real server.
  `gpt-6-astra` runs in code mode, where MCP tools are deferred nested tools: the first request names none of them and
  carries only the guidance Codex adds when deferred tools exist (`code-mode-protocol/src/description.rs` L15 and
  L291-293), which shows that at least one deferred tool is present, not which. So the endpoint answers the first
  request with a code-mode `exec` call whose script lists `ALL_TOOLS` by name and names no tool itself, and the
  second request carries that list in its `custom_tool_call_output`. This follows upstream's own code-mode tests at
  `rust-v0.157.1`: `core/tests/suite/code_mode.rs` `run_code_mode_turn_with_builder` (L264-293) and
  `code_mode_exports_all_tools_metadata_for_namespaced_mcp_tools` (L7133-7175), with `ev_custom_tool_call` from
  `core/tests/common/responses.rs` (L975-985). With the profile, the first request left after 5 s with the guidance
  and the first turn listed `mcp__serena__fixture_serena` and `mcp__codebase_memory__fixture_codebase_memory`. With
  `required` relaxed (the control), it left before 5 s without the guidance, and the first turn listed only the
  built-in tools. The two lists differ by exactly those two names. With serena unable to start, the run exited
  non-zero before any request. The check is on the first turn's tools as `exec` sees them; the first request's
  body itself names no MCP tool.
- Three older native tests registered the two servers as `/bin/false` or a stub and failed once the template changed
  (`FAILED (failures=3)`); they now register fixture servers. `NAS_CODEX_INTEGRATION=1 python3 -m unittest -v
  tests.test_codex_worker_lane.CodexIntegrationTests`: exit 0, `Ran 9 tests`, `OK` before the race test was
  strengthened, after it, and after the GPT-6 repair round (that run without `-v`).
- Measured probe of the installed codebase-memory-mcp (not a Codex run): with a scratch `HOME` it answered nothing in
  30 s and printed "CBM could not start because the active account daemon uses a different cache directory ... Close
  all CBM sessions and commands, then retry with one consistent CBM_CACHE_DIR."; with the account's `HOME` it answered
  in 1.2 s.
- The apply's read-back and the prove script's profile check start both servers from cwd `/` (serena runs with
  `--project-from-cwd`). The same stdio probe from `/` with the account's `HOME` (not a Codex run): serena answered
  `initialize` in 1.47-1.53 s (24 tools), codebase-memory in 1.20-1.25 s (17 tools), three runs each. The host apply
  itself has not run.
- Release data (`gh api`, 2026-09-27): the latest stable release is `rust-v0.157.1` (published 2026-09-26). The
  newest prereleases, `rust-v0.158.0-alpha.15.3` and `rust-v0.159.0-alpha.9`, keep the 1 s grace, `required` and the
  error text, and add per-server `startup_readiness` (PR #47935, merged 2026-09-24): it lets a cached catalog satisfy
  start-up, and that cache lives in one process's memory, so a fresh `codex exec` gains nothing.

**Alternatives considered:**
- **`mcp_optional_startup_grace_ms = 0`** (`config/src/config_toml.rs` L318-322: "Set to 0 to disable the shared
  grace and wait for each server's configured `startup_timeout_sec` instead"). Rejected: it waits for every optional
  server, SocratiCode's 120 s included, and still runs without a server that fails. A positive value is one shared cap
  for all of them.
- **A per-prompt `mcp://` mention** such as `[$serena](mcp://serena)` (`core/src/session/turn.rs` L936-948, read by
  `tool_catalog.rs` L231-233). It waits for that server for one turn but does not fail the run, and every brief
  would have to carry it. Untested here.
- **`startup_readiness`:** prerelease only, and it does not cover a fresh process.
- **Relaxing the apply's read-back too:** rejected; that read-back is the check that the servers start where
  workers run.

**Overturn conditions:**
- A Codex release whose readiness or catalog cache covers a fresh process, or with a longer default grace: re-measure
  the first request and reconsider the wait.
- Measured start-up failures that make `required = true` fail real worker runs (codebase-memory under another `HOME`,
  a serena start past 60 s): fix the start, or drop `required` for that server and record the lost tools.
- The peer's retained gateway probe, rerun after the host re-apply, still missing either tool on the first turn.

**Limitations and residuals:**
- The peer's gateway measurement is relayed, not retained; after the coordinator re-applies the profile, the peer
  reruns its gateway probe (pass: both tools present and completing on the first turn).
- A worker whose `HOME` is not the account's cannot start codebase-memory while the account daemon runs. It used to
  run without the tools; now its session start fails: at once if the server exits, or when the stalled step's 60 s
  timeout ends if it hangs (the probe above saw no answer in 30 s).
- Every `-p stack-worker` launch now holds its first request until both servers have started, their first tool
  listing included. The timings here are observations, not the added delay: the probe's `initialize` times (serena
  1.53-2.24 s, codebase-memory 1.20-1.25 s, each from its own launch) and, without `required`, the race test's first
  request at 1.63 s and 1.69 s after `codex` started. The optional grace starts at the first tool-list build, after
  the required wait
  ([`session.rs` L1860-1868](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/session/session.rs#L1860-L1868),
  [`tool_catalog.rs` L251-277](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-mcp/src/connection_manager/tool_catalog.rs#L251-L277)),
  so an optional server still starting then can add the shared 1 s grace on top. The added delay depends on how
  long the required servers take and on the optional servers still starting.
- The workstation's installed `stack-worker.config.toml` predates this template, so the dry run and the apply refuse
  it ("exists and differs from the template") and never overwrite it. The host step, after merge and in a quiet
  window with no Codex process: move that file aside privately, run the dry run, then apply.
- **Unchanged upstream tests: not run.** The relevant tests at `rust-v0.157.1` (commit `36650394`):
  - `core/tests/suite/mcp_optional_startup_grace.rs` L40 `optional_mcp_startup_grace_controls_initial_turn_tool_catalog`
    (four cases: a custom grace omits a pending server and admits a ready one; a zero grace waits for server start-up
    and respects the start-up timeout);
  - `codex-mcp/src/connection_manager_tests.rs` L2871
    `capture_binding_skips_pending_optional_servers_after_configured_shared_startup_grace`, L3027
    `capture_binding_waits_for_optional_startup_when_shared_grace_is_disabled` and L3120
    `capture_binding_shares_optional_startup_grace_across_connection_sets`;
  - `core/tests/suite/managed_threads_tests.rs` L30 `dropping_startup_cleans_up_while_required_mcp_is_stalled`
    (start-up waits for a stalled `required` server);
  - `exec/tests/suite/mcp_required_exit.rs` L9 `exits_non_zero_when_required_mcp_server_fails_to_initialize`
    (`codex exec` exits non-zero with "required MCP servers failed to initialize: <name>").

  The documented invocation is `just test -p codex-core`, `-p codex-mcp` or `-p codex-exec` with the test name as a
  filter (upstream `AGENTS.md` L66-67; the `justfile` recipe, L87-88, runs `cargo nextest run --no-fail-fast`), on
  the Rust 1.95.0 that `codex-rs/rust-toolchain.toml` pins. This host has no Rust toolchain: `cargo`, `rustc`,
  `rustup`, `just` and `cargo-nextest` are not on `PATH` and `~/.rustup` is empty (probe, 2026-09-27), and none was
  installed for this. Two of the tests skip without network (`skip_if_no_network!`, `mcp_optional_startup_grace.rs`
  L43 and `managed_threads_tests.rs` L31), so a run has to record its skips. The race test above is our local
  integration check, not a substitute for them.
- **Live provider or model runs, gateway runs and token measurements: none.**
