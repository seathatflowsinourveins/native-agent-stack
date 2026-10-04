# Decision: Codex MCP servers move to user scope so worktree workers get them; a value-free pinned-version check joins `--client-wiring` (2026-09-25)

**Status: decided and applied on the workstation `nativestack-5975wx-20260925`, 2026-09-25.** The host side was applied with the native `codex mcp add` (this host has no `adoption/hosts/<host>.json` for `tools/adoption/render_config.py`), and read back from a fresh worktree; see [Application on this host](#application-on-this-host-2026-09-25).

**Scope:** `scripts/adoption_status.py`, `tests/test_adoption_status.py`,
`adoption/templates/codex.config.template.toml`,
`adoption/templates/project.codex.config.template.toml`, this record, and this host's `~/.codex/config.toml` (user scope, not checked in). Does not touch
`adoption/mcp/claude-user.json` (Claude's own user-scope MCP set is unchanged), `.ai-memory.toml`,
or `AGENTS.md`/`CLAUDE.md` (the ai-memory workspace/project-name residual, recorded under Evidence class, is
named but not fixed here).

## Context

- PR #264 added `--client-wiring` to `scripts/adoption_status.py` and stated its own residual:
  "the check proves each tool is present, not that it is at its pinned version." PR #251 added
  `version_probe` to the platform pins files and the bootstrap scripts that consume it, for the
  same reason `--client-wiring` exists: a value-free way to answer a yes/no readiness question
  from data already checked into the repository.
- `WIRED_MCP_SERVERS = ("serena", "socraticode", "ai-memory")` in `scripts/adoption_status.py`
  (origin/main). `client_wiring.complete` requires, per server, `codex["mcp_servers_present"][name]
  or project["codex_mcp_servers_present"][name]` — `codex` reads `$CODEX_HOME/config.toml`
  (`~/.codex` by default), `project` reads `<repo-root>/.codex/config.toml`.
- On this host, `~/.codex/config.toml` has no `[mcp_servers]` table (`grep -n '^\['
  ~/.codex/config.toml`, read-only). `<repo>/.codex/config.toml` has all five servers
  (`serena`, `socraticode`, `ai-memory`, `jcodemunch`, `context-mode`) with absolute paths, and
  is untracked: `git ls-files .codex/config.toml` → empty; `.git/info/exclude` lists `/.codex/` as
  "NativeStack host-only configuration." `git worktree add` only materializes tracked content, so
  a fresh worktree has neither file populated with these servers.
- `.claude/settings.json`, by contrast, **is** tracked (`git ls-files .claude/settings.json` →
  `.claude/settings.json`) and already carries the depth/concurrency env this repository commits
  with Ultracode on, so the `project.settings_depth_and_concurrency` half of the same `project`
  group is unaffected — the bug is Codex-specific.
- `codex mcp add --help` (codex-cli 0.155.1, read-only) has no `--scope`, `--cwd` or `--project`
  flag; only `-c/--config`, `--env`, `--url`, `--enable`/`--disable`, and OAuth options. The
  project-scope entries observed above were authored by `tools/adoption/render_config.py`
  rendering `adoption/templates/project.codex.config.template.toml`, not by `codex mcp add`.
- developers.openai.com/codex/config-advanced ("Project config files (`.codex/config.toml`)",
  fetched 2026-09-25): "Codex walks from the project root to your current working directory and
  loads every `.codex/config.toml` it finds." A linked worktree is its own project root; the walk
  never reaches the main checkout's directory.
- `adoption/mcp/claude-user.json` already registers `serena` (stdio, `--project-from-cwd`, no
  `cwd` field) and `ai-memory` (http, no project field) at Claude **user** scope
  (`adoption/bootstrap.md` step 4a, `claude mcp add --scope user`). `docs/decisions/
  2026-09-23-claude-user-profile.md`'s 2026-09-25 addendum already decided jCodeMunch stays out of
  user scope for the opposite reason: its own MCP instruction text ("prefer it over Read/Grep/
  Glob/Bash") would load into every session and contradict this catalog's `rg`/Serena/SocratiCode
  routing, backed by a measured hit@5 comparison (0.25 vs. 0.85) and this host's own transcript
  counts (15 jCodeMunch calls vs. 33 Serena, 7 SocratiCode).
- `codex mcp list --json` (read-only, this host) confirms `serena` and `socraticode` already carry
  no `"cwd"` (`null`) in their live registration, and `ai-memory` is a bare
  `streamable_http` URL with no project field at all. `context-mode`'s live entry, uniquely, does
  carry `"cwd"` and `CONTEXT_MODE_PROJECT_DIR` pinned to the main checkout's literal path — an
  override the plugin's own bundled manifest
  (`~/.codex/plugins/cache/context-mode/context-mode/1.0.169/.claude-plugin/plugin.json`,
  `mcpServers.context-mode`) does not itself declare. *Corrected 2026-09-26:* that file is the Claude
  plugin manifest. The Codex one, `.codex-plugin/mcp.json`, declares `"cwd": "."`, which Codex resolves
  to the plugin root; see the [2026-09-26 addendum](#addendum-2026-09-26-cross-family-review-repair).
- `adoption/pins-linux-x86_64.json`'s `version_probe.method` values are `"exec"` (a command+args
  to run) and `"npm-metadata"` (context-mode: "No version flag: every argv other than its named
  subcommands and `--help` falls through to starting its MCP stdio server"). `socraticode` has no
  entry in this pins file at all (a prior receipt: "manual --ignore-scripts recipe per
  recipes/README.md, not a pins-file entry").

## Decision

1. **Move `serena`, `socraticode` and `ai-memory` MCP registrations from Codex project scope to
   Codex user scope, and add `headroom`, `codebase-memory` and `qmd` there too, mirroring the Claude user-scope set the token-efficiency owner registered on 2026-09-25** (`adoption/templates/codex.config.template.toml`), removing them from
   `adoption/templates/project.codex.config.template.toml`. All three already resolve their
   project from Codex's own launch cwd (serena's `--project-from-cwd`), an external service
   (socraticode's Qdrant/LM Studio), or not at all (ai-memory's bare URL) — none of the three
   registrations carries a project-specific path today, so relocating them changes only which
   config file Codex reads them from, not how they behave once running. The three additions carry no
   `cwd` or env either. headroom's `--proxy-url http://127.0.0.1:1` is a dead proxy URL, so it reroutes
   no model traffic. codebase-memory indexes only on an explicit `index_repository` call, and its host
   config keeps `auto_index=false` and `ui_enabled=false`; never run its `install` subcommand, which
   edits client configs. qmd serves the named `native-agent-stack-catalog` index. SocratiCode keeps its
   pinned, versioned `dist/index.js` path, because the recipe creates no `bin/` link for it, so a pin
   move updates the template and the host together.
   **Overturn condition:** a project in this catalog needs a Codex user profile that also opens
   other projects which must not have these three available, or a future Codex release adds a
   documented project-scope write path to `codex mcp add` (checked via `codex mcp add --help` and
   the Codex changelog at the next upgrade).
2. **`jcodemunch` stays project-scoped, unchanged.** The reasoning in `docs/decisions/
   2026-09-23-claude-user-profile.md`'s 2026-09-25 addendum for Claude applies to Codex without
   modification: the MCP instruction text is client-agnostic, and Codex reads the same `AGENTS.md`
   routing guidance Claude does. `jcodemunch` is not in `WIRED_MCP_SERVERS`, so its continued
   worktree-unavailability does not affect `client_wiring.complete`.
   **Overturn condition:** a retrieval comparison run against current Codex usage on this host
   shows jCodeMunch materially outperforming Serena/SocratiCode for Codex-issued calls
   specifically (the 2026-09-25 comparison this reasoning extends was measured on Claude Code
   transcripts).
3. **Superseded on 2026-09-26; see the [addendum](#addendum-2026-09-26-cross-family-review-repair).**
   **Drop context-mode's project-scope `cwd`/`CONTEXT_MODE_PROJECT_DIR` override.** It is not
   required by anything in the plugin's own bundled manifest, it is not part of
   `WIRED_MCP_SERVERS`, and as currently written it can only ever name the main checkout — neither
   worktree-portable nor safely promotable to user scope unmodified. Let the plugin's own
   already-user-scope, `cwd`-free registration apply everywhere.
   **Overturn condition:** a concrete cross-worktree or cross-session context-mode retrieval miss
   is observed, and passing an explicit `project` argument on the affected `ctx_search`/
   `ctx_batch_execute` calls (already a supported parameter) is shown insufficient to recover it.
4. **Add an opt-in `--pinned-versions` flag to `scripts/adoption_status.py`**, parallel to
   `--client-wiring`: for the selected profile's `component_ids`, look up each id in this
   platform's `adoption/pins-<os>-<arch>.json`, and for a pin whose `version_probe.method` is
   exactly `"exec"`, resolve its declared `command` via `PATH` only and run it with its declared
   `args`, `stdin` from `/dev/null`, a bounded timeout (the pin's own `timeout_seconds` or 30s),
   and compare stdout+stderr against the pinned version using the same bounded `"exact"` and numeric `"minimum"` rules
   `adoption/bootstrap-linux.sh`'s `version_output_matches` already uses. A component with no pin
   for this platform, or whose declared method is not `"exec"` (`"npm-metadata"`, or any future
   undeclared method), is reported **unchecked** and is never executed — this is the same
   boundary `adoption/bootstrap-linux.sh` and `adoption/bootstrap-macos.sh` already draw around
   context-mode and socraticode, reused rather than reimplemented. Output is booleans, counts, and
   version strings only (component ids and pinned/observed versions are already public, checked-in
   data; no path, credential, or free-form file text is emitted). The flag composes with
   `--client-wiring`; the exit code is unchanged, matching `--client-wiring`'s own contract.
   **Overturn condition:** `"npm-metadata"` version checking is later wanted from this script too
   (mirroring the bootstrap scripts' `npm ls --global --prefix <ecosystem-tools-dir> --depth=0
   --json <package>`); `adoption_status.py` has no concept of an ecosystem install prefix today,
   so that would need either adopting one or a documented convention for locating an npm package's
   metadata from `PATH` alone.

## Evidence

- **codex-cli 0.155.1**, this host, read-only: `codex --version`, `codex --help`, `codex mcp
  --help`, `codex mcp add --help`, `codex mcp list --help`, `codex mcp get --help`, `codex mcp
  list --json`.
- **developers.openai.com/codex/config-advanced**, fetched 2026-09-25: "Project config files
  (`.codex/config.toml`)", "Config and state locations", "Hooks" (the same four-location pattern —
  `~/.codex/hooks.json`, `~/.codex/config.toml`, `<repo>/.codex/hooks.json`,
  `<repo>/.codex/config.toml` — confirms the project-root-to-cwd walk applies uniformly to
  hooks and `mcp_servers` alike).
- **developers.openai.com/codex/config-reference**, fetched 2026-09-25: `config.toml` key
  reference (`mcp_servers.<id>`, `plugins.<plugin>.mcp_servers.<server>.*`,
  `projects.<path>.trust_level`).
- **developers.openai.com/codex/mcp** (mirrored at learn.chatgpt.com/docs/extend/mcp), fetched
  2026-09-25: STDIO server fields (`command`, `args`, `env`, `env_vars`, `cwd`, defined as
  "optional: Working directory to start the server from") and Streamable HTTP server fields
  (`url`, `auth`, `bearer_token_env_var`, `http_headers`, `env_http_headers`,
  `http_headers_helper` — no project field).
- **This repository, `origin/main`**: `scripts/adoption_status.py`, `tests/test_adoption_status.py`,
  `adoption/manifest.json` (`token-efficiency` profile), `adoption/pins-linux-x86_64.json`,
  `adoption/bootstrap-linux.sh` (`write_version_report`, the `exec`/`npm-metadata` case split),
  `adoption/bootstrap.md`, `adoption/templates/codex.config.template.toml`,
  `adoption/templates/project.codex.config.template.toml`, `adoption/mcp/claude-user.json`,
  `recipes/README.md`, `docs/decisions/2026-09-23-claude-user-profile.md`.
- **This host, read-only**: `~/.codex/config.toml`, `<repo>/.codex/config.toml` (restricted grep,
  no key/token/secret/password lines printed, `[mcp_servers.*]` blocks only), `.git/info/exclude`,
  `git ls-files`/`git ls-tree -r --name-only origin/main`, the context-mode plugin's cached
  `.claude-plugin/plugin.json`.

## Alternatives rejected

- **Leave registration at project scope and have each worktree write its own
  `.codex/config.toml`.** Rejected: nothing generates or seeds that file for a throwaway `/tmp`
  worktree today, and doing so would mean re-resolving and re-writing every host-specific absolute
  path (`${ECO_ROOT}`, `${HOST_PATH}`, `${AI_MEMORY_URL}`, `${QDRANT_URL}`, `${EMBED_URL}`) per
  worktree, for servers that do not need a project-specific path at all.
  This would also multiply, not remove, the untracked-file problem `.git/info/exclude` already
  names as host-only configuration.
- **Symlink or bind-mount the main checkout's `.codex/config.toml` into each worktree.** Rejected:
  outside `scripts/adoption_status.py`'s and the templates' own scope, host-specific (WSL2 bind
  mounts and symlink support differ across the macOS/Linux targets this catalog supports), and
  still pins `CONTEXT_MODE_PROJECT_DIR`/any future project-specific field to the main checkout for
  every worktree, the same one-literal-path failure mode §3.5 already rejects for context-mode.
- **Wait for a `codex mcp add --scope project` flag.** Rejected for now: not available in
  codex-cli 0.155.1 (`codex mcp add --help`, read-only, this host); tracked as this decision's own
  overturn condition (§ Decision 1) rather than blocking the fix on an unreleased feature.
- **Extend `--pinned-versions` to also check `"npm-metadata"`-method pins by shelling out to `npm
  ls`.** Rejected for this patch: `adoption/bootstrap-linux.sh`'s `npm-metadata` case runs `npm ls
  --global --prefix "$ecosystem_root/tools/$id-$version"`, which depends on knowing the
  ecosystem's own install-prefix convention — a piece of state `scripts/adoption_status.py`
  deliberately does not carry (it checks `PATH` presence only, per its own docstring). Recorded as
  this decision's overturn condition instead of implemented speculatively.

## Comparisons that would overturn this

See the four **Overturn condition** entries under Decision, above; each names the concrete
observation or Codex/upstream change that would revisit that specific line item independently of
the other three.

## Application on this host (2026-09-25)

These checks ran on `nativestack-5975wx-20260925` after the ai-memory 2.4.0 production window closed. Each check reads through the consuming tool rather than grepping files.

*Retention note, 2026-09-26.* The outputs of steps 1 to 4 were not kept, so the narrative below is an unretained host report. The retained results are in [`evidence/artifacts/token-coverage-20260926/`](../../evidence/artifacts/token-coverage-20260926/README.md):

- four later runs of the step 3 coverage check in the host's environment, each reporting `client_wiring.complete: true` with `project.codex_mcp_servers_present` false for serena, socraticode and ai-memory: the coordinator's (00:04:37Z), this repair's rerun (02:39:52Z), and two runs by drivers that retain how they ran (04:47:40Z and 06:42:52Z). That value is also false when a project config exists without those servers, so the runs show that each checkout's project config, if any, registered none of the three; only the 04:47:40Z and 06:42:52Z runs also checked, with retained output, that their checkout had no project Codex config at all;
- the discriminating control for those runs (06:42:50Z): the same check with `CODEX_HOME` set to a new empty directory, so with no Codex user scope, reports `complete: false`, with `codex.mcp_servers_present` false for all three servers;
- Codex's own read-back of the `headroom` and `context-mode` registrations.

None of the runs reproduces step 4's sets: the pins had moved by then (#291, #299, #307). The MCPorter tool counts and ai-memory's `/healthz` remain unretained.

1. **Before.** In a fresh detached worktree at `origin/main`:
   - `codex mcp list --json` listed only `['context-mode']`, which comes from its plugin.
   - `scripts/adoption_status.py --profile token-efficiency --client-wiring --json --repo-root <fresh worktree>` reported `client_wiring.complete: false`, with `codex.mcp_servers_present` false for serena, socraticode and ai-memory.
2. **Applied.** `codex mcp add` registered serena, ai-memory (`--url http://127.0.0.1:49474/mcp`), socraticode, headroom, codebase-memory and qmd in `~/.codex/config.toml`, using exactly the launchers and env names in `adoption/templates/codex.config.template.toml`. Its `${ECO_ROOT}` is this host's `~/.local/share/codex-ecosystem`. The main checkout's untracked project config was left as rendered: it holds identical definitions and takes precedence there. A re-render from the new project template reduces it to `jcodemunch`.
3. **After, in the same fresh worktree:**
   - `codex mcp list --json` listed `ai-memory, codebase-memory, context-mode, headroom, qmd, serena, socraticode`.
   - `client_wiring.complete` became **true**.
   - Each stdio server was started with the same launcher from that worktree and listed its tools through MCPorter's ad-hoc stdio mode: serena 23, socraticode 26, headroom 3, codebase-memory 17, qmd 4.
   - ai-memory's `/healthz` returned 200.
4. **`--pinned-versions`**, same run:
   - matched: codex, claude-code, qmd;
   - mismatched: rtk, markitdown, ai-memory, mcporter. These are the host moves ahead of their pin-move PRs: rtk 0.50.0, markitdown 0.1.8, ai-memory 2.4.0 and mcporter 0.14.1, applied by the cleanup session. The check reports intended divergence until the pins move.
   - unchecked: context-mode, repomix, headroom, toon, ccusage, serena, socraticode. context-mode's probe is `npm-metadata`, and the others have no entry in `adoption/pins-linux-x86_64.json`, which is the bootstrap-completion follow-up.

**Addendum, 2026-09-25, later (corrected 2026-09-26).** headroom's user-scope registration, in this host's Codex and Claude configs and in the Codex template, now sets `HEADROOM_OFFLINE=1` and `DO_NOT_TRACK=1`. headroom-ai 0.37.0 enables its usage beacon by default.

- **What `HEADROOM_OFFLINE` covers.** It switches off the beacon, the update check and the usage reporter (`offline.py`, `telemetry/beacon.py`). It does not switch off model downloads in `headroom mcp serve`: only proxy startup calls `apply_offline_env()`, which sets the Hugging Face offline variables. The 2026-09-26 addendum therefore adds those variables to the template. This paragraph first said that `HEADROOM_OFFLINE` switched off all of headroom's egress.
- **Read-backs.** Both read-backs on 2026-09-25 were unretained host reports: that `codex mcp get headroom --json` listed both variable names, and that the server still served its three tools. Codex's read-back on 2026-09-26 is retained ([`codex-readback.json`](../../evidence/artifacts/token-coverage-20260926/codex-readback.json)). The Claude-side change has no retained read-back.
- **Version.** headroom stays on 0.37.0. The 0.39.0 qualification, since retained in [`headroom-039-qualification-20260925.json`](../../evidence/receipts/headroom-039-qualification-20260925.json) (#307), found its log summaries lossy, with an omission count that includes kept lines.

## Addendum, 2026-09-26 (cross-family review repair)

A cross-family review of #289, #297, #300 and #303 found the defects below. This repair fixes them. The session that ran the review reported Codex CLI 0.155.1 with `gpt-6-astra` at reasoning effort max; the review's own output is not retained.

1. **Decision 3 is reversed: context-mode gets a session-bound user-scope server.**
   - **The defect.** The context-mode plugin's Codex manifest, `.codex-plugin/mcp.json` at `6f0cc684`, starts `node ./start.mjs` with `"cwd": "."`. Codex 0.155.1 joins that `cwd` to the plugin root (`codex-mcp/src/plugin_config.rs`). Upstream `start.mjs` refuses a plugin-install directory as the project, so it sets no `CONTEXT_MODE_PROJECT_DIR`. The resolver then takes the newest Codex session log. With two concurrent sessions in different worktrees, one session's `ctx_execute` shell commands run in the other's worktree.
   - **The fix.** `adoption/templates/codex.config.template.toml` now registers `[mcp_servers.context-mode]` at user scope with no `cwd`. It runs the pinned npm install's upstream `start.mjs` with `node`, and the plugin's own server is set to `enabled = false`; the plugin stays enabled for its hooks and skills. Codex starts a server without `cwd` in the session's own directory (`LocalStdioServerLauncher`), and `start.mjs` binds `CONTEXT_MODE_PROJECT_DIR` to it. A template cannot express this through the plugin: Codex's `PluginMcpServerConfig` lets user config enable or disable a plugin's server but not change how it is launched. The bare `context-mode` CLI, upstream's manual Codex form, starts the server without `start.mjs` and falls back to the newest session log as well.
   - **The evidence** is in [`evidence/artifacts/context-mode-codex-binding-20260926/`](../../evidence/artifacts/context-mode-codex-binding-20260926/README.md):
     - upstream's own resolver tests at `6f0cc684`: 69 passed, 1 skipped;
     - a local integration check of real servers answering `pwd`: 4 of 4 bound with this form, 2 of 4 for the plugin's server and 2 of 4 for the bare CLI, each of those two always following the newest log;
     - Codex's read-back of the rendered template;
     - this host's plugin server, which Codex reports starting in the plugin root ([`codex-readback.json`](../../evidence/artifacts/token-coverage-20260926/codex-readback.json)).
   - **Limits.** No real concurrent Codex sessions were run. Codex's launch directory comes from its source and read-backs. The npm package's server bundle is a different source revision from the plugin pin; `start.mjs` is byte-identical in both. Like the plugin's server, `start.mjs`'s self-heal can write under the Claude configuration directory; the binding evidence's limits list what it writes. The template path names the npm pin (`tools/context-mode-1.0.169`), so it must move with that pin; `tests/test_render_config.py` now checks this for every versioned tool path in the templates, and that the template's context-mode entry has no `cwd` and the plugin's own server stays off.
   - **Residual.** Neither this host's `~/.codex/config.toml` nor the main checkout's untracked project config has been changed. Until they are, fresh worktrees still get the plugin's server. `--client-wiring` cannot show this: it checks that the context-mode plugin is enabled, not where its server binds, so the 02:39:52Z, 04:47:40Z and 06:42:52Z runs reported `complete: true` after Codex's read-back at 02:24:15Z had found this host's server to be the plugin's.
   - **Overturn condition.** Any of: upstream context-mode resolves a Codex session's own directory without an environment binding (for example from MCP roots); Codex lets user config set a plugin server's working directory; or a native two-session Codex run shows this form resolving the wrong worktree.
2. **`--pinned-versions` requires exit 0, and kills whole process groups.** A probe that exits nonzero is now reported as checked and not matching, as the bootstrap's `FAILED (exit N)` is, even when its diagnostics contain the pinned version. Before, a probe exiting 42 with the pin in its error text matched. Each probe now mirrors `adoption/bootstrap-linux.sh`'s `run_version_probe`:
   - It runs in its own session and process group, with its output in temporary files, so a leftover child holding the output open cannot delay the result.
   - When the bound expires, the group gets TERM, then KILL 2 s later. Before, only the probe process itself was killed on timeout, and its children kept running.
   - Whatever the probe left running is killed once it exits.
   - SIGINT, SIGTERM and SIGHUP all kill the running group before the check exits, as the bootstrap's `EXIT` trap stops its probe's group when that script is interrupted. A signal the check started with ignored, as under `nohup`, stays ignored, as it does for the bootstrap (item 5). An interruption is let through only while the check waits for the probe, inside the block whose cleanup kills the group (item 6).

   Stdout and stderr are now searched as two streams, as the bootstrap's `grep` searches two files. `tests/test_adoption_status.py` grows from 57 to 62 tests. The five new tests fail against the pre-repair script and pass after the repair ([retained runs](../../evidence/artifacts/token-coverage-20260926/pinned-versions-regression-tests.txt)).
3. **headroom's MCP server gets the Hugging Face offline variables.** The template's headroom entry now also sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, and so do the recipe's commands (`recipes/README.md`) and `docs/token-efficiency-stack.json`.
   - **Why.** headroom-ai 0.37.0's `mcp serve` (`cli/mcp.py`) never calls `apply_offline_env()`, while its compress path can load the Kompress model through `hf_hub_download` and `from_pretrained`.
   - **Not verified.** The template variables were not tested with an empty cache and a blocked network. This host's headroom environment has no onnxruntime, torch or transformers, so Kompress is unavailable there, and such a run could not reach the download path.
   - **Not covered.** The MCP server compresses under a Claude model name (`ccr/mcp_server.py`), whose token counter is tiktoken's `o200k_base` (`tokenizers/registry.py`, `_create_anthropic`), and on a cold cache tiktoken downloads that vocabulary on first use. None of the four variables stops that; headroom bounds the load (`HEADROOM_TIKTOKEN_LOAD_TIMEOUT_SECONDS`, default 10) and then estimates (`tokenizers/tiktoken_counter.py`).
   - **Residual.** This host's live Codex registration still lacks the two variables. Claude's user-scope registration was made with the 2026-09-25 recipe command, which did not set them, and has no read-back here.
4. **Evidence retained.** See the retention note under [Application on this host](#application-on-this-host-2026-09-25) and the corrected addendum above. The grand-dashboard gate `token-efficiency-wiring` now reads "7 versions unchecked" instead of "7 without Linux pins". At that checkpoint, six components had no Linux pin and context-mode's pin declared an `npm-metadata` probe.
5. **Independent review of this repair: two more defects, both fixed.**
   - **An ignored signal was replaced.** The first version of this repair installed its SIGTERM and SIGHUP handlers whatever the check inherited, so under `nohup` a SIGHUP ended the check with status 129 and no report. The bootstrap keeps running then: bash cannot trap a signal that was ignored on entry, and CPython likewise installs its SIGINT handler only when SIGINT starts at its default action. `signals_interrupt_probes` now changes SIGTERM and SIGHUP only while they are at their default action and puts them back afterwards, so an ignored signal stays ignored and another handler stays in place. The process-level tests now start each check with exactly the dispositions they test, so a runner that inherits SIGINT ignored (a background job of a non-interactive shell) or SIGHUP ignored (`nohup`) no longer changes their result. `tests/test_adoption_status.py` grows from 62 to 66 tests. The new tests fail against the first version of this repair (143 and 129 for SIGTERM and SIGHUP ignored on entry) and pass after the fix, including from `nohup` and background-job runners, where the first version's interruption test errors after 20 s ([retained runs](../../evidence/artifacts/token-coverage-20260926/signal-disposition-regression-tests.txt)).
   - **A run's premise was not backed.** The first version's retention note said the coverage runs came from checkouts with no project Codex config. `project.codex_mcp_servers_present` is also false when a project config lists none of the three servers, so the note and the evidence README now say only what the reports show.
6. **Cross-family verification of this repair: one more defect in the check and one in the binding evidence, both fixed.**
   - **An interruption could still leave a probe running.** `run_version_probe` armed the group kill only once `subprocess.Popen` had returned the probe's process, so a SIGTERM that arrived after the fork but before that return ended the check with status 143 and left the probe running past its bound. A first fix held interruptions back while the process was created and while its group was killed; SIGINT, while at its default action, now goes through the same handler and still raises `KeyboardInterrupt`. Interrupting a probe run at the start of each line in turn then found the same window at the other end: after the wait, the kill began its hold only after two lines of its `finally` block and two of `held_interrupts`, and an interruption on any of them left the group running. `run_version_probe` now holds interruptions from before the process is created until its group has been killed and reaped, and lets them through only while it waits for the probe, inside the block whose cleanup kills the group (`interrupts_released`). `tests/test_adoption_status.py` grows from 66 to 72 tests. One of them interrupts a probe run at the start of each line that `run_version_probe` and its helpers execute, one line per run, until the KILL has been sent; it skips a `try` statement's own line, a NOP where CPython never runs a signal handler. The new tests fail against the script before each fix and pass after it, including from `nohup` and background-job runners ([first fix](../../evidence/artifacts/token-coverage-20260926/interrupt-window-regression-tests.txt), [final](../../evidence/artifacts/token-coverage-20260926/interrupt-window-every-line-regression-tests.txt)).
   - **The binding check's request bound.** `binding_check.py` bounded each wait for the next message, not the whole request, so a server that kept sending other messages could hold a request past its bound. It now checks the time left before every wait. The retained real-server results came from the script as it ran, kept as `binding_check.original.py`, and the fixed script has not been rerun against real servers. Against a stub that answers only after 300 ms of notifications, the original accepted the answer despite a 50 ms bound, and the fixed script gave up at 50 ms ([`deadline-control.json`](../../evidence/artifacts/context-mode-codex-binding-20260926/deadline-control.json)).
   - **Retained provenance.** The two evidence READMEs now mark what only the session that ran a check reported. Reruns retain the provenance the first runs lacked: `provenance_rerun.py` for the three binding checks, and `wiring_control.py` for a coverage run that fails with an empty Codex home beside one that passes.

## Evidence class

*Corrected 2026-09-26.* This section first called the wiring change `native_proven` from steps 1–3, but their outputs were not retained, so those steps are host reports.

- **Wiring.** Retained native runs of this repository's own check on the real host (not upstream tests) show `client_wiring.complete: true` while each checkout's project Codex config, if any, registered none of the three servers, and its discriminating control, with an empty Codex home in place of the user scope, reports `complete: false`; see the retention note.
- **`--pinned-versions`.** The 72 unit tests in `tests/test_adoption_status.py` use synthetic fixtures (local scripts and processes). The same retained runs also cover it: by the session's account, the 02:39:52Z run used the first version of this repair's script; the 04:47:40Z run used the version before the interrupt-window fixes, and the 06:42Z wiring control the first of those fixes, as their retained output records. No coverage run used the final script, whose later changes affect only a probe that is interrupted.
- **context-mode binding.** See the 2026-09-26 addendum for its evidence classes.
- **ai-memory scoping.** The ai-memory workspace/project-name resolution for worktree agents (`.ai-memory.toml` is untracked) remains a named residual; it does not affect registration.
