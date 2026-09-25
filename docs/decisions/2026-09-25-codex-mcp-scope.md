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
  `mcpServers.context-mode`) does not itself declare.
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
3. **Drop context-mode's project-scope `cwd`/`CONTEXT_MODE_PROJECT_DIR` override.** It is not
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

**Addendum, 2026-09-25, later.** headroom's user-scope registration, in this host's Codex and Claude configs and in the Codex template, now sets `HEADROOM_OFFLINE=1` and `DO_NOT_TRACK=1`. headroom-ai 0.37.0 enables its usage beacon by default, and `HEADROOM_OFFLINE` switches off all its egress (see `offline.py` and `telemetry/beacon.py` in the installed package). `codex mcp get headroom --json` lists both variable names, and the server still serves its three tools. headroom stays on 0.37.0: the 0.39.0 qualification found its log summaries lossy, with a misleading omission count.

## Evidence class

**`native_proven` for the wiring change** (steps 1–3 above, on the real host). For `--pinned-versions`, the evidence is `synthetic` (54 unit tests in `tests/test_adoption_status.py`, run on this branch) plus the native run in step 4. The ai-memory workspace/project-name resolution for worktree agents (`.ai-memory.toml` is untracked) remains a named residual; it does not affect registration.
