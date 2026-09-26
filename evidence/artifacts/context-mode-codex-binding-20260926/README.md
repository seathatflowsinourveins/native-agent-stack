# context-mode's project binding under Codex (2026-09-26)

Host: `nativestack-5975wx-20260925`, the WSL2 workstation (Ubuntu 24.04.5, x86_64). Node 24.21.0,
codex-cli 0.155.1.

## Question

The 2026-09-26 cross-family review of #289 found a problem. With the template's project-scoped
context-mode binding removed, a Codex session's context-mode server can resolve another worktree.

- Does that hold for the pinned plugin?
- Which template-level binding gives each concurrent session its own directory, without a host path?

## Sources (read at their pins)

- **context-mode, plugin revision `6f0cc684`:**
  - `.codex-plugin/mcp.json` starts `node ./start.mjs` with `"cwd": "."`.
  - `start.mjs` sets `CONTEXT_MODE_PROJECT_DIR` from its start directory, unless that directory is a
    plugin install path.
  - `src/util/project-dir.ts` `resolveProjectDir`, under the `codex` platform, tries
    `CONTEXT_MODE_PROJECT_DIR`, then the newest Codex session log that is under 5 minutes old, then
    `PWD`, then the process directory.
  - `src/executor.ts` runs `ctx_execute` shell code in that directory.
  - The npm `context-mode@1.0.169` CLI (`cli.bundle.mjs`) starts the server without `start.mjs`.
- **Codex `rust-v0.155.1`:**
  - `codex-rs/codex-mcp/src/plugin_config.rs` joins a plugin server's relative `cwd` to the plugin root.
  - `codex-rs/rmcp-client/src/stdio_server_launcher.rs` (`LocalStdioServerLauncher`) starts a server
    that has no `cwd` in the fallback directory. `codex-rs/core/src/session/mcp_runtime.rs` sets that
    directory to the session's own `cwd`.
  - `codex-rs/rmcp-client/src/utils.rs` passes only `DEFAULT_ENV_VARS` plus the server's own `env`, so
    no `PWD` reaches the server.
  - `codex-rs/config/src/types.rs` `PluginMcpServerConfig`: user config can turn a plugin's server off
    but cannot change how it is launched.

## Checks

| File | Evidence class | What ran |
| --- | --- | --- |
| [`upstream-resolver-tests.txt`](upstream-resolver-tests.txt), [`upstream-resolver-tests-rerun.txt`](upstream-resolver-tests-rerun.txt), [`upstream-resolver-tests-rerun.provenance.txt`](upstream-resolver-tests-rerun.provenance.txt) | Upstream test | context-mode's own tests for the resolver: the first run, and a rerun that retains how it ran |
| [`binding_check.original.py`](binding_check.original.py), [`results.json`](results.json), [`results-rerun.json`](results-rerun.json), [`results-rerun.provenance.txt`](results-rerun.provenance.txt) | Local integration check | 12 real context-mode servers, three launch forms: the first run and a rerun |
| [`template_readback.py`](template_readback.py), [`template-readback.json`](template-readback.json), [`template-readback-rerun.json`](template-readback-rerun.json), [`template-readback-rerun.provenance.txt`](template-readback-rerun.provenance.txt) | Native read-back | The rendered template, read back through Codex: the first run and a rerun |
| [`provenance_rerun.py`](provenance_rerun.py) | Driver | Reran each of the three checks once, unchanged, and printed the `*.provenance.txt` files |
| [`binding_check.py`](binding_check.py), [`deadline_control.py`](deadline_control.py), [`deadline-control.json`](deadline-control.json) | Synthetic fixture | The request-deadline fix to the local integration check, against a stub server |

The Codex registration on this host itself is read back in
[`../token-coverage-20260926/codex-readback.json`](../token-coverage-20260926/codex-readback.json).

The first runs kept their output but not all of their provenance. `provenance_rerun.py` reran each
check once, from 2026-09-26T06:49:39Z to 06:50:09Z, and retained its command, the environment where it
sets one, the interpreter or the node and npm versions, the UTC start and end, the exit status and
hashes. What only the session that ran the first runs reported is marked as such below.

### Upstream tests

```sh
npm test -- tests/util/codex-session-cwd-resolution.test.ts tests/util/project-dir.test.ts \
  tests/integration/project-dir-strict.test.ts --reporter=verbose
```

- **First run** ([`upstream-resolver-tests.txt`](upstream-resolver-tests.txt)): 3 files, 69 passed,
  1 skipped (the Bun variant). The `pretest` build ran first (tsc, esbuild,
  `assert-bundle`, `assert-asymmetric-drift`). The output keeps only vitest's `Start at 22:30:22`, in
  the host's local time. The run's UTC times and exit code, the clone's revision and status, and the
  environment were not retained. The session that ran it reported a scratch copy of the clone at
  `6f0cc684` with two self-healed files restored from `HEAD`, `HOME` in a scratch directory and `CI`
  unset. The rerun records these conditions for itself.
- **Rerun** ([`upstream-resolver-tests-rerun.txt`](upstream-resolver-tests-rerun.txt), provenance in
  [`upstream-resolver-tests-rerun.provenance.txt`](upstream-resolver-tests-rerun.provenance.txt)),
  2026-09-26T06:50:03Z to 06:50:09Z, exit 0:
  - **Where:** a copy of this host's Codex plugin clone, whose `git rev-parse HEAD` is
    `6f0cc6841c687e754059f36714a11233fda1a02b`.
  - **Preparation:** `git status --porcelain` listed `.claude-plugin/plugin.json` and `hooks/hooks.json`
    as modified. `start.mjs`'s self-heal rewrites them, and upstream's `assert-asymmetric-drift` pretest
    step rejects such rewrites. Both were restored from `HEAD`, and the status was empty when the run
    started.
  - **Environment, and nothing else:** `PATH` (node's directory, `/usr/bin`, `/bin`), `HOME` and
    `TMPDIR` in the work directory, `LANG`, `TZ=UTC`, `NO_COLOR` and npm's update check turned off, so
    no `CI` variable. Node v24.21.0, npm 11.19.0.
  - **Result:** the same 69 passed and 1 skipped. The output matches the first run's apart from
    durations, vitest's start time and one trailing blank line.
  - **After the run,** `git status` listed `cli.bundle.mjs` and `server.bundle.mjs` as modified: the
    `pretest` build rewrote both bundles in the copy.
- **Coverage:** only these three upstream files were selected. Among their tests:
  - "returns meta.cwd from the most-recently-modified session.jsonl";
  - "falls back to Codex session log when no workspace env is set", which lets a session log win over
    the server's own directory;
  - "falls back to Codex Desktop session log before poisoned plugin cwd";
  - "honors CONTEXT_MODE_PROJECT_DIR env (universal escape hatch)".

### Local integration check (`results.json`)

```sh
python binding_check.py --plugin-src ~/.codex/plugins/cache/context-mode/context-mode/1.0.169 \
  --npm-src ~/.local/share/codex-ecosystem/tools/context-mode-1.0.169/lib/node_modules/context-mode \
  --node ~/.local/share/codex-ecosystem/bin/node --work <empty scratch directory>
```

- **Runs.** Both came from the script as it ran then, kept byte for byte as
  [`binding_check.original.py`](binding_check.original.py) (sha256
  `0c6ed66d8ec370b2f3a3bac30bb8bfdc945f62d062af5d7db42fb2779f810c32`; the rerun's provenance names it
  `binding_check.py`). [`binding_check.py`](binding_check.py) has since changed how it bounds a request
  (below).
  - **First run** ([`results.json`](results.json)): its 12 calls started between 02:27:58Z and
    02:28:09Z. Its command line, interpreter, end time and exit code were not retained.
  - **Rerun** ([`results-rerun.json`](results-rerun.json), provenance in
    [`results-rerun.provenance.txt`](results-rerun.provenance.txt)): the command above, Python 3.13.15,
    06:49:56Z to 06:50:02Z, exit 0, empty stderr. Its 12 calls are identical to the first run's apart
    from their start times.
- **Setup.** Both packages are copied into the scratch directory first. `HOME` points at a scratch
  home, which holds two fresh Codex session logs, one each for `wt-a` and `wt-b`.
- **Launch.** Each server gets the variables Codex passes and the directory Codex would give it.
- **Probe.** Each server is asked `ctx_execute(language="shell", code="pwd")` over MCP stdio, with
  Codex's `clientInfo`.
- **Repetitions.** Every form is launched once per session, and the whole set runs twice: once with
  `wt-b`'s log newest, once with `wt-a`'s.

| Launch form | Directory Codex gives it | Answers in its own session's worktree |
| --- | --- | --- |
| The plugin's server (`node ./start.mjs`) | the plugin root | 2 of 4: always the newest log's worktree |
| Upstream's manual Codex form (`context-mode` CLI, no `cwd`) | the session's | 2 of 4: always the newest log's worktree |
| This repair's form (`node <npm install>/start.mjs`, no `cwd`) | the session's | 4 of 4 |

The two forms that fail are the discriminating control. They run the same check without the binding
and fail it.

- **Packages.** `start.mjs` is byte-identical in the plugin clone and in the npm install (sha256
  `0324441841b2…`). The two server bundles differ: the npm release is a different source revision
  from the plugin pin. Every server exited 0 and wrote nothing to stderr.

### Request deadline (`deadline-control.json`)

The cross-family verification of this change found that `Server.request` in the script as it ran
bounded each wait for the next message, not the whole request, so a server that kept sending other
messages could hold a request past its bound. `binding_check.py` now checks the time left before every
wait and raises once it has run out; `main()` records that as the call's error and still closes the
server.

```sh
python deadline_control.py binding_check.original.py binding_check.py
```

The control loads `Server` from each script, starts a stub server that sends a notification every 10 ms
for 300 ms before it answers, and sends it one request bounded at 50 ms. At 2026-09-26T09:59:19Z, with
Python 3.13.15:

- `binding_check.original.py` returned the answer after 323 ms, having taken 31 messages;
- `binding_check.py` raised `queue.Empty` after 50 ms, having taken 3;
- in both, the stub exited 0 with an empty stderr once the server was closed.

The times vary from run to run. The real-server rerun took 6 s in all, far inside the 90 s bound of
each request, so the deadline did not bear on its results. The fixed script has not been rerun against
the real servers.

### Template read-back (`template-readback.json`)

```sh
python template_readback.py --checkout <this repository> \
  --plugin ~/.codex/plugins/cache/context-mode/context-mode/1.0.169 --work <empty scratch directory>
```

- **First run** ([`template-readback.json`](template-readback.json)): Codex 0.155.1 (`codex_version`)
  and the results below. Its times, interpreter, exit code and the template's hash were not retained.
- **Rerun** ([`template-readback-rerun.json`](template-readback-rerun.json), provenance in
  [`template-readback-rerun.provenance.txt`](template-readback-rerun.provenance.txt)): Python 3.13.15,
  06:49:39Z to 06:49:56Z, exit 0, empty stderr, and output byte-identical to the first run's. It read
  `adoption/templates/codex.config.template.toml` with sha256
  `1044688dd6c1d4f82441edc349b60d6b1d182d30e6cea8bd5fc9f06b119f7146`, rendered with
  `adoption/hosts/example.json` (sha256 `7ec6a782…`) by `tools/adoption/render_config.py` (sha256
  `d9502772…`).
- **Codex home:** a scratch `CODEX_HOME` with a copy of the plugin.
- **Results:**
  - The rendered template: Codex 0.155.1 accepts it and lists one `context-mode` server. That server
    is the template's own: `node … start.mjs`, with no working directory.
  - Without the plugin-server override: the same result. In 0.155.1 a same-named user entry already
    takes precedence; the override keeps that explicit.
  - The plugin alone (the state before this repair): the plugin's server, started in the plugin root.
  - In all three configurations, headroom's registration carries the template's four variables.

## Limits

- **No native Codex session was run.** Neither form has been exercised in real concurrent Codex
  sessions. Codex's directory choice comes from its source and its own read-back; the servers were
  started by `binding_check.py`, which copies what Codex passes.
- **Hosts are not changed yet.** Neither this host's `~/.codex/config.toml` nor the main checkout's
  untracked project config has been changed. Until the template is applied, fresh worktrees still
  get the plugin's server.
- **`start.mjs` can write to the user's Claude configuration directory** (`$CLAUDE_CONFIG_DIR`, else
  `~/.claude`). Wherever it runs, its self-heal ("Layer 3 + 4", "Layer 5b", "Layer 5c" and "Layer 4" in
  `start.mjs`, sha256 `0324441841b2…`, and `scripts/heal-installed-plugins.mjs`) repairs the
  context-mode entries of `plugins/installed_plugins.json` and of `settings.json`'s `enabledPlugins`;
  under `plugins/cache`, resets an absolute `start.mjs` path in each registered context-mode install's
  `.claude-plugin/plugin.json` to its `${CLAUDE_PLUGIN_ROOT}` placeholder and removes stale `.mcp.json`
  files from the context-mode version directories; and deploys `hooks/context-mode-cache-heal.mjs` and
  registers it as a `SessionStart` hook in `settings.json` when it is missing. The plugin's own server runs the same
  `start.mjs`, so this form adds no new kind of write there, and it skips one: the registry forward-heal
  ("Layer 1"), which can point Claude's registry at a newer version directory beside it, runs only from a
  `plugins/cache/<marketplace>/<plugin>/<version>` directory. `start.mjs` also normalizes the hook files of
  the package it runs from ("Layer 5"), here the npm install, whose `hooks/hooks.json` and
  `.claude-plugin/plugin.json` on this host already hold no `${CLAUDE_PLUGIN_ROOT}` placeholder. In the
  local integration check, these writes went to the scratch home and the scratch package copies.
- **Sanitization.** Scratch paths are replaced with placeholders and the home directory with `~`. The
  servers' stderr files were empty and are not published. `provenance_rerun.py` prints the work
  directory as `<work>`, the scratch home in it as `<work-home>`, node's directory as `<node-dir>`, the
  checkout as `<this repository>` and the home directory as `~`, and refuses to write output that still
  holds a UUID or a home path. `deadline_control.py` prints no path.
