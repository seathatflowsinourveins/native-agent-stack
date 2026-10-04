# Decision: an OmniRoute account pool for GPT-6 lanes: a source build of release/v3.8.51 with an upstream fix and an upstream feature, a keyless loopback service and Codex wiring (2026-09-27)

**Status: decided by the user and installed on the NativeStack WSL2 workstation on 2026-09-27; this change records
it.** The coordinator session built, installed and verified the gateway before this record was written. This change
touches no host. The gateway is adopted for pooled GPT-6 access. Native Codex stays the max-quality default, and the
agent-sdks layer default is unchanged (decision 6).

**Scope:**
- new: this record; [`evidence/artifacts/omniroute-gateway-20260927/`](../../evidence/artifacts/omniroute-gateway-20260927/README.md);
  the values-free unit template `adoption/templates/systemd/omniroute.service` with its structural test
  `tests/test_omniroute_gateway_unit.py`; a narrow `.gitignore` exception for this evidence directory's `*.jsonl`.
- changed:
  - `docs/foundation-stack.md`: its 3.8.50-only statements are scoped to 3.8.50, and a short section describes this
    build;
  - `manifests/stack.json`: the omniroute component records the running build without changing its release pin
    (decision 7);
  - `catalogs/foundation/manifest.json`: the native-clients layer text;
  - the `omniroute` entry of `adoption/credential-inventory.json` and its row in `docs/secret-storage.md`.
- untouched:
  - the host;
  - the Codex templates (`adoption/templates/codex.*.toml`, the Codex-templates unit's scope);
  - the trading lane's `blueprints/us-equities/routing/`;
  - `catalogs/foundation/decisions.json`;
  - the landscape freshness snapshot;
  - the Windows OmniRoute 3.8.50 gateway of `docs/native-dashboards.md`.

Upstream prefixes used below:
- `OR` = https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3
- `OR50` = https://github.com/diegosouzapw/OmniRoute/blob/5458026c216f77a3da68ea49152dc33470cfe2cb (tag v3.8.50)
- `CX` = https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs

**About the settings synthesis.** The coordinator's settings synthesis of 2026-09-27 and its verified research
rows are not retained in this repository. That covers the K, U and X items named below. This record uses them only
as recommendations it adopts or declines, and says so where it does.

**What backs the claims.** The upstream mechanisms and defaults this record relies on are cited at their pins, and
live observations point to retained outputs. Some statements rest only on the coordinator's report: the Evidence
section lists the observations whose outputs are not retained, and other reported facts say so where they appear.

## Context

The user's direction on 2026-09-27 (UTC, intent quoted from the session):
- about 05:05Z, the account pool and its purpose: "with omniroute organize all the accs and its native built token
  efficiency practice, we can powering the sota repos, runtimes, even trading runtimes etc in north star, and we will
  not need to spend the context for tracking noise of gpt6 usage". Earlier: "consider the full codex lane move to
  omniroute".
- about 05:40Z, the build: "go ahead install the v3.8.51 branch and wire codex".
- about 06:05Z, the posture: "we need passwardless workflow as previous stated and open the dashboard, we are llm
  native frictionless".
- about 06:30Z, the accounts: four Codex accounts were added through OmniRoute's own OAuth flow. Codex's own
  `~/.codex/auth.json` was never imported.
- about 06:55Z, the workload: multi-hour GPT-6-heavy convergence through SOTA harness frameworks, with GPT-6 powering
  runtime workers.

OmniRoute's published release was ruled out. npm `latest` is 3.8.50, and 3.8.51 is unpublished
([`upstream-state.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-state.txt)). 3.8.50 has two
problems for this lane:
- **The effort clamp.** 3.8.50 clamps any model missing from its effort table to `xhigh`: `MAX_EFFORT_BY_MODEL[model]
  ?? "xhigh"` (OR50 `open-sse/executors/codex.ts` L346-347), and that table has no GPT-6 entry. So a `max` lane
  runs at `xhigh`.
- **The hook sandbox escape.** 3.8.50 carries the pre-request hook sandbox escape GHSA-9p9m-h9rj-rhhg. The advisory
  is unpublished; commit a58000c7 (#14916) fixes it.

The head of upstream's default branch `release/v3.8.51`, commit `a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3`, handles
effort differently. `getCodexAliasEffortCap` caps `gpt-6-astra` at `ultra` (OR
`open-sse/executors/codex/reasoningSuffix.ts` L11-31, from d92bc8ef #13026 and f026a613 #14677), and the wire effort
for `ultra` is `max` (OR `open-sse/executors/codex.ts` L354-355 and L1463).

That commit had two defects on this host.

1. **Every `/v1` inference route answered HTTP 500 on the host's Node 24.** The coordinator observed this with
   `scripts/route_repro.py.txt`, whose status lines are reported, not retained. Codex shows an HTTP 500 from its
   provider as "We’re currently experiencing high demand" (CX `codex-api/src/api_bridge.rs` L157-158 and
   `protocol/src/error.rs` L160-161). The retained client events of a 06:32Z probe show five reconnects and a failed
   turn with that message
   ([`probe-lane-client-events.json`](../../evidence/artifacts/omniroute-gateway-20260927/probe-lane-client-events.json)).
   They do not show whether the gateway raised the 500 itself or passed on an upstream one, or which build served
   them.
   - **The cause.** `withDeadlineSignal` (OR `open-sse/utils/earlyStreamKeepalive.ts:341`, added by 8c05ec42 #14808
     on 2026-09-25) builds `new Request(request, {signal, headers})`. Next 16.3.5's app-route runtime hands
     `dynamic: auto` routes a Proxy (`proxyNextRequest`, `next/dist/server/route-modules/app-route/module.js`
     L626-629). On the newer Node lines the `Request` constructor then reads the input's private `#state` through that
     Proxy.
   - **The corrected reproduction**
     ([`proxy-repro-independent.txt`](../../evidence/artifacts/omniroute-gateway-20260927/proxy-repro-independent.txt))
     gives each arm its own `Request`. A Proxy-wrapped POST and GET fail with the `#state` TypeError on Node 24.21.0
     (undici 7.29.1) and Node 26.10.0 (undici 8.10.2); Node 26 is upstream's Docker base, `FROM node:26-trixie-slim`
     at `Dockerfile` L2. The same cases construct on Node 22.23.3 (undici 6.28.1).
   - **A flaw in the first reproduction.** The coordinator's first reproduction,
     [`proxy-repro.txt`](../../evidence/artifacts/omniroute-gateway-20260927/proxy-repro.txt), shared one POST body
     between its arms. Its Node 22 "already been used" error came from that shared body, not from the Proxy. That was a
     finding of this record's cross-family review.
   - **What this means.** Node 22 is within upstream's engines (`>=22.22.2 <23 || >=24.0.0 <27`) and might avoid the
     construction failure, but the gateway was not run on it.

   Three upstream fixes were open on 2026-09-26, all unreviewed: #14872, #14886 and #14904.
2. **Codex's standalone `web.run` POSTs `<base_url>/alpha/search` and got 404.** The peer's parity probe found this.
   Upstream #13788 serves that route. It is labelled `deferred-v3.8.52` and adds two files, the route and its test.
   Its second commit is the maintainer's own "sanitize unexpected internal errors". A source build was therefore
   needed whatever the Node line.

Upstream's own CI is red on `a58000c7`. Issue #14866 "Release branch not green: release/v3.8.51" is open. At
07:58Z these check runs had failed ([`upstream-state.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-state.txt)):
- "Release acceptance";
- all four Node 24 compat test shards;
- one Node 26 compat shard (three were cancelled);
- the promptfoo injection guard;
- the garak probes.

## Decision

1. **The build: `release/v3.8.51` at `a58000c7` plus two upstream PRs, built with upstream's scripts.**
   - **#14904** (head `b94e2dba`) is applied as `22fb9f15` (the fix) and `bf025564` (its changelog fragment). It was
     chosen over #14872 and #14886 on test coverage:
     - a Proxy POST with a byte-exact body and headers;
     - deadline-controller recovery;
     - client-abort propagation;
     - a body-less GET case.

     It also preserves `redirect` and adds the changelog fragment. A fix in the code, rather than a pin to one Node
     line, also covers upstream's Node 24 and 26 targets.
   - **#13788** (head `6c799005`) is applied as `b9f0d76e` and `dd6e9607`.
   - **Fidelity of the picks.** Each applied commit has the same stable patch-id as its upstream commit. The build
     head's tree is `6f3f9a23068b6640b1084682dba6aab144ddbdc2`
     ([`cherry-pick-fidelity.txt`](../../evidence/artifacts/omniroute-gateway-20260927/cherry-pick-fidelity.txt)).
   - **Build steps.** Upstream's own scripts
     ([`build-provenance.json`](../../evidence/artifacts/omniroute-gateway-20260927/build-provenance.json)
     `commands`) with Node 24.21.0 and npm 11.19.0:
     1. `npm ci`;
     2. `npm run build:release`, which sets `BUILD_SHA` from git;
     3. `npm run build:cli-api`;
     4. `npm pack`;
     5. `OMNIROUTE_ALLOW_CANARY_BUILD=1 npm run check:pack-artifact`. It passes, and reports a recorded canary
        because the head is not on the release line;
     6. `npm install --global --prefix <new prefix>`;
     7. `npm rebuild` with the host's `--allow-scripts` list (`docs/foundation-stack.md`).
   - **The running build.** `BUILD_SHA` is `dd6e9607e`, and the tarball's sha256 is `039df693…6a675d` (full value in
     the provenance). The prefix is `~/.local/share/codex-ecosystem/tools/omniroute-3.8.51-a58000c7-pr14904-pr13788`.
   - **Rollback.** The superseded build `bf0255649` (#14904 only) and the plain `a58000c7` prefix are kept.
   - **Also in the catalog, not exercised here.** The build's catalog also carries `gpt-6-sol`, capped at `ultra`,
     and `gpt-6-luna`, capped at `max` (OR `open-sse/executors/codex/reasoningSuffix.ts` L11-31). This record
     exercised only `gpt-6-astra`.
2. **The service: a `systemd --user` unit on loopback**
   ([`omniroute.service`](../../evidence/artifacts/omniroute-gateway-20260927/omniroute.service); template
   `adoption/templates/systemd/omniroute.service`).
   - **Command.** `ExecStart=<prefix>/bin/omniroute serve --port 20128 --no-open --no-tray`, with
     `Restart=on-failure`, `UMask=0077` and `NoNewPrivileges=true`.
   - **Addresses.** Loopback only: 127.0.0.1 on ports 20128, 20131 and 20132. A read-only observation at 10:40Z,
     after every probe, found exactly these three listeners among the unit's processes, and no other process on
     those ports
     ([`gateway-readonly-observation.txt`](../../evidence/artifacts/omniroute-gateway-20260927/gateway-readonly-observation.txt)).
     What sets each bind:
     - 20128, the server: `OMNIROUTE_SERVER_HOST`, else `0.0.0.0` (OR `bin/cli/utils/serverHost.mjs` L16-26). The
       environment file sets it to 127.0.0.1.
     - 20132, the live dashboard WebSocket: `LIVE_WS_HOST`, else 127.0.0.1, on `LIVE_WS_PORT`, else 20132 (OR
       `src/server/ws/liveServer.ts` L50-54 and L713-714).
     - 20131, the embed WebSocket proxy: `EMBED_WS_PROXY_HOST`, else `LIVE_WS_HOST`, else 127.0.0.1, on
       `EMBED_WS_PROXY_PORT`, else 20131 (OR `src/lib/services/embedWsProxy.ts` L35-36, L240-242 and L256-257;
       `.env.example` L2302-2308 warns that a non-loopback value bypasses the local-only policy).

     The two WebSocket listeners stay on loopback only while `LIVE_WS_HOST` and `EMBED_WS_PROXY_HOST` are unset.
     The unit does not set them, `make_server_env.py.txt` does not write them into `server.env`, and the 10:40Z
     observation found both listeners on loopback.
   - **No `--no-recovery`.** Upstream labels it "Disable auto-restart on crash (debugging mode)" (OR
     `bin/cli/locales/en.json` L255). The default in-process supervisor runs under systemd's `Restart=on-failure`;
     its `--max-restarts` default is 2 (OR `bin/cli/commands/serve.mjs` L64-65, `en.json` L256).
   - **No secret in the unit; the unit adds its secrets only through `EnvironmentFile=`.** The unit reads
     `%h/.local/share/omniroute/server.env`, which lives inside `DATA_DIR`.
     - **How it was made.** `scripts/make_server_env.py.txt` generated it with `O_EXCL` at mode 0600 in a 0700
       directory, without printing values. `scripts/make_passwordless.py.txt` then made the decision-5 change.
     - **What it holds.** Generated `JWT_SECRET`, `API_KEY_SECRET` and `STORAGE_ENCRYPTION_KEY` (and
       `STORAGE_ENCRYPTION_KEY_VERSION`), plus non-secret `DATA_DIR`, `PORT`, `OMNIROUTE_SERVER_HOST=127.0.0.1` and
       `REQUIRE_API_KEY=false`.
     - **Its format.** Plain `NAME=value` lines. That is the layout and format of upstream's own bootstrap, which
       persists generated secrets to `{DATA_DIR}/server.env` as `NAME=value` lines (OR
       `scripts/build/bootstrap-env.mjs` L1-19 and L183-186).

     A systemd user service also inherits the user manager's environment (systemd.exec(5), "Environment variables in
     spawned processes"). `serve` then hands its whole environment to the server child, so any credential exported
     into the user manager would reach the gateway. The same holds for bind settings: a `LIVE_WS_HOST` or
     `EMBED_WS_PROXY_HOST` in the manager could move a WebSocket listener off loopback, and the `_PORT` variables
     could move a port. Keep credentials and these four variables out of the manager: list its variable names with
     `systemctl --user show-environment | cut -d= -f1`.

     Why `EnvironmentFile=` fits here:
     - **The file format.** systemd v255 drops `export NAME=value` lines, and this file has none. Its parser keeps
       `export NAME` as the key
       ([`src/basic/env-file.c` L75-95](https://github.com/systemd/systemd/blob/v255/src/basic/env-file.c#L75-L95)).
       The `EnvironmentFile=` loader then discards, with an error in the log, every assignment whose name is not
       valid ([`src/core/execute.c` L773-787](https://github.com/systemd/systemd/blob/v255/src/core/execute.c#L773-L787);
       [`src/basic/env-util.c` L542-554](https://github.com/systemd/systemd/blob/v255/src/basic/env-util.c#L542-L554),
       L78-90 and [L28-50](https://github.com/systemd/systemd/blob/v255/src/basic/env-util.c#L28-L50); all at v255).
       The repository's credential stores use the `export` form, so no unit points at them.
     - **The exposure.** This departs from `docs/secret-storage.md` step 9, which says services pass `--env-file`
       and do not use `EnvironmentFile=`, because `EnvironmentFile=` puts values into `/proc/<pid>/environ`. The
       exposure is the same with any loader, including upstream's own:
       - the `omniroute` CLI loads its env files into `process.env` (OR `bin/omniroute.mjs` L134-216);
       - `serve` spawns the server with `{...process.env, …}` (OR `bin/cli/commands/serve.mjs` L281-298);
       - so the secrets are in the server process's environment either way.

       This is the same accepted exception that `docs/secret-storage.md` ("Process environment") and the
       `grafana-admin` inventory entry record for Grafana's loopback unit.
   - **Non-secret `Environment=` lines.** The template gives each its own one-line reason:
     - `OMNIROUTE_MEMORY_MB=16384`: upstream accepts 64..16384 inclusive (OR `scripts/build/runtime-env.mjs` L19).
     - `CODEX_CLIENT_VERSION=0.157.1`: the installed client. It is the fallback for paths that do not forward the
       caller's version. `getCodexClientVersion` reads this variable, else the built-in default (OR
       `open-sse/config/codexClient.ts` L13 and L29-34), and `getCodexClientVersionFromHeaders` returns the
       caller's own version, or null so callers fall back to `getCodexClientVersion` (L36-83). The built-in
       default is 0.156.1 (OR `src/shared/constants/codexClient.ts` L6).
     - `STREAM_READINESS_TIMEOUT_MS=600000` and `STREAM_READINESS_MAX_TIMEOUT_MS=600000`: the defaults are 80000 and
       180000 (OR `src/shared/utils/runtimeTimeouts.ts` L24-25). The adaptive readiness budget starts from the first
       and never exceeds the second (OR `open-sse/utils/streamReadinessPolicy.ts` L198), and the content-stall
       watchdog reuses that budget (OR `open-sse/handlers/chatCore.ts` L6395-6399). So the defaults would abort a
       max-effort turn that reasons longer than that before its first content.
     - `STREAM_ACTIVE_TIMEOUT_MS=3600000`: the default is 1260000, or 21 minutes (OR `runtimeTimeouts.ts` L21).
       Upstream documents it as a hard cap that upstream byte activity never resets, disabled by 0 (OR
       `open-sse/config/constants.ts` L31-33).
     - `CLI_ALLOW_CONFIG_WRITES=false`: the default is true (OR `src/shared/services/cliRuntime.ts` L1077-1078).
       Templates stay the single writer of Codex and Claude configuration.
   - **Local adaptation: an `lsof` shim on the unit's `PATH`.** It is
     [`scripts/lsof-shim.sh.txt`](../../evidence/artifacts/omniroute-gateway-20260927/scripts/lsof-shim.sh.txt) and
     changes no upstream code. Here is the failure it works around:
     - `serve`'s port preflight (OR `bin/cli/commands/serve.mjs` L252-261, from f8f923e8 #14538) calls
       `findListeningPids()` (OR `bin/cli/utils/pid.mjs` L73-99).
     - That function returns `null` whenever `lsof` exits non-zero, and `lsof` exits 1 when nothing listens.
     - The preflight then bind-probes a free port, leaves `busyPids` null and reads `busyPids.length`.
     - So `serve` exits on every start with a free port.

     The shim maps "exit 1 with no output" to 0, so discovery returns `[]` and upstream's bind probe still guards the
     port. Remove it once upstream handles the null case.
3. **Gateway settings, applied through the settings API and read back**
   ([`gateway-settings-readback.json`](../../evidence/artifacts/omniroute-gateway-20260927/gateway-settings-readback.json)).
   - `sessionAffinityTtlMs = 14400000` (4 h). At the default 0, each turn of a Codex conversation can land on a
     different pooled account and lose prompt-cache continuity (OR `docs/guides/CODEX-CLI-CONFIGURATION.md`,
     "Session affinity"; the validated range is 0..86400000).
   - `providerStrategies.codex = {fallbackStrategy: "round-robin", stickyRoundRobinLimit: 1}`.
     - Direct provider calls select by `providerStrategies[provider].fallbackStrategy`, else `fallbackStrategy`, else
       `"fill-first"` (OR `src/sse/services/auth.ts` L1952-1957).
     - Affinity runs first: a connection chosen by session affinity skips the strategy (OR `src/sse/services/auth.ts`
       L1995-1997).
     - `stickyRoundRobinLimit` keeps one target for that many consecutive successes before rotating (default 3: OR
       `src/lib/db/settings.ts` L159 and `src/sse/services/auth.ts` L1998-2001).
       Upstream says to set the combo override to 1 "for one-request rotation" (OR `docs/routing/AUTO-COMBO.md`
       L354-357). This record applies the same value to the codex provider strategy, which direct provider calls
       read before the global setting (OR `src/sse/services/auth.ts` L1999-2000).
     - There is no combo and no router alias. Codex sends `cx/gpt-6-astra`, and the gateway logged the upstream model
       as `gpt-6-astra` (`probe-lane-run2.json`, `gateway-effort-rows.json`).
   - `promptCacheAffinityEnabled = true`, the default, is kept (OR `src/lib/db/settings.ts` L163).
   - Compression stays off: `enabled=false` and `defaultMode="off"`, the defaults (OR
     `open-sse/services/compression/types.ts` L421-423, which `getCompressionSettings` spreads under the stored
     values at `src/lib/db/compression.ts` L663-664).
   - `exclusions = ["codex/*"]`. `a58000c7` removed 3.8.50's native-passthrough compression bypass, and upstream's own
     comment names this exclusion as the remedy (OR `open-sse/handlers/chatCore.ts` L1429-1449).
   - The Thinking Budget mode is `passthrough`, the default (OR `open-sse/services/thinkingBudget.ts` L65-67).
     `auto` strips the client's reasoning fields before upstream (L8-9, L19).
   - `mcpEnabled=false` and `a2aEnabled=false`.
4. **Codex wiring**
   ([`codex-provider-block.toml`](../../evidence/artifacts/omniroute-gateway-20260927/codex-provider-block.toml),
   [`codex-omniroute-profile.toml`](../../evidence/artifacts/omniroute-gateway-20260927/codex-omniroute-profile.toml)).
   - **Base config.** `~/.codex/config.toml` holds `[model_providers.omniroute]`:
     - `base_url = "http://127.0.0.1:20128/v1"`;
     - `env_key = "OMNIROUTE_API_KEY"`;
     - `requires_openai_auth = false`;
     - `wire_api = "responses"`;
     - `supports_standalone_web_search = true`.

     The fields are those of `ModelProviderInfo` (CX `model-provider-info/src/lib.rs` L136-196). `supports_websockets`
     is left at its default, false (L192), because OmniRoute's WebSocket bridge does not forward the caller's Codex
     version (OR `src/app/api/internal/codex-responses-ws/route.ts` L718).
   - **The `omniroute` profile.** `~/.codex/omniroute.config.toml` sets:
     - model `cx/gpt-6-astra` and provider `omniroute`;
     - effort `max`;
     - `web_search = "live"`;
     - `[features] standalone_web_search = true`;
     - `shell_snapshot = false`. Codex writes the exported environment into 0644 shell snapshots
       (`codex-rs/shell-command/src/shell_snapshot_exports.rs` at rust-v0.157.1, as #387 found).
   - **The launcher.** `~/.local/share/codex-ecosystem/bin/codex-omniroute` exports `OMNIROUTE_API_KEY=local-loopback`
     unless the inventory store holds a key, then runs `exec codex -p omniroute`. The value is a placeholder, which the
     keyless gateway accepts.
   - **Worker lanes.** They use #387's lane-local `CODEX_HOME` with the same provider fields
     (`tools/sota-convergence/landscape-sweep/README.md`, "GPT-6 through OmniRoute").
   - **Not decided here.** The settings synthesis recommends moving the provider block out of the host base config
     into the profile (its K2), so base config matches `adoption/templates/codex.config.template.toml`. That is the
     Codex-templates unit's scope, not this record's.
5. **Passwordless and keyless, by the user's decision.**
   - **The settings.** `requireLogin=false`, `REQUIRE_API_KEY=false` and `INITIAL_PASSWORD` removed. While first-time
     setup is incomplete, a set `INITIAL_PASSWORD` makes upstream mark setup complete and force `requireLogin=true`
     as a headless deploy (OR `src/lib/db/settings.ts` L301-311: `!settings.setupComplete &&
     process.env.INITIAL_PASSWORD`).
   - **Recorded risk.** Any local process can call the management API, including hook registration.
     - With login off, the management policy admits an anonymous `auth-disabled` subject on paths that are not always
       protected (OR `src/server/authz/policies/management.ts` L261-266).
     - `/api/middleware/` is only loopback-gated (OR `src/server/authz/routeGuard.ts` L79).
     - Its `POST` registers hooks (OR `src/app/api/middleware/hooks/route.ts` L79), and hooks can read and rewrite
       prompts.
     - The `a58000c7` isolated-realm fix closes the sandbox escape, but not hook registration itself.
     - Inference keys are advisory.
   - **Mitigation.** The bind is loopback only, on a single-user workstation: all three listeners were on 127.0.0.1
     at 10:40Z (decision 2, "Addresses").
   - **Overturn.** Any multi-user or non-loopback exposure, or any untrusted local process.
   - **What the user overrode.** The settings synthesis recommended requiring the key and the login (its K7 and U2).
     The user's 06:05Z direction overrides that.
6. **What "adopted" covers, and the gate that stays.**
   - **The gateway lane's uses.** The landscape sweep, on the user's direction, through #387's lane
     (`build_args.py --gpt6-provider omniroute`). The peer's 8-check mechanical parity probe on build `dd6e9607e` is
     recorded in the message of merged commit `b9abcc5f` (#387): stage rc 0 and codex rc 0; the shell tool; MCP
     `ctx_execute`; `--output-schema`; usage; effort `max` in the rollout and `max`/`max` in the gateway's
     `call_logs`; `web.run` reaching `/v1/alpha/search` with no 404.
   - **The gate for the agent-sdks default.** The preregistered three-arm workers comparison remains the acceptance gate
     for any catalog change to the agent-sdks layer default (`docs/grand-catalog-handbook.md:602`; the full condition is
     `verdict_overturn_when` of the `agent-sdks` layer in `catalogs/landscape/foundation.json`). This record changes
     no layer verdict.
   - **Two other checks that are not that gate:**
     - the peer's mechanical probe;
     - `omniroute-codex-max-parity`, the gateway-parity experiment sketched in the settings synthesis (its X1). It is
       not frozen in this repository and has not run.

     Native Codex remains the max-quality default until a preregistered comparison says otherwise.
7. **Repository records.**
   - **`manifests/stack.json` cannot express this build.** A component has one `version` and one `source_pin`, and
     `scripts/landscape.py` requires both to equal the dated landscape freshness snapshot. There is no field for
     cherry-picks. So the omniroute pin stays the published release 3.8.50 (`5458026c`). The component's `freshness`
     and `command_scope` record the base commit, the picks and `BUILD_SHA`, and point here. `upstream_sources` gains
     the base commit and the two PRs.
   - **The unit template is values-free.** Prefix placeholders stand in for paths, no secret is written in it, and
     the only secrets it adds come through `EnvironmentFile=`. It mirrors the installed unit's directives, apart from
     `Description=`, with one addition: `Environment=OMNIROUTE_SERVER_HOST=127.0.0.1`. `omniroute serve` binds
     `0.0.0.0` when that variable is unset (OR `bin/cli/utils/serverHost.mjs` L16-26), and the keyless posture needs
     loopback. On the workstation the environment file already sets the same value. Each `Environment=` line carries
     its own one-line reason, which the structural test enforces.
   - **The inventory.** The `omniroute` entry describes a keyless loopback gateway with an optional per-lane key.

## Evidence

Retained outputs: [`evidence/artifacts/omniroute-gateway-20260927/`](../../evidence/artifacts/omniroute-gateway-20260927/README.md).
The classes are kept separate.

- **Live provider execution through the gateway (native Codex 0.157.1 at max, 2026-09-27).** The lane probe and the
  effort rows ran on `bf0255649` (`a58000c7` + #14904), the build before the running one. They predate the
  `dd6e9607e` service start at 07:19:46Z, and the provenance records `bf0255649` as superseded at 07:19:45Z. The search
  probes ran on `dd6e9607e`. The two builds differ in two files, the `/v1/alpha/search` route and its test
  ([`build-delta.txt`](../../evidence/artifacts/omniroute-gateway-20260927/build-delta.txt)), so the `/v1/responses`
  results below are expected to hold on `dd6e9607e`. That is an inference from the diff; the lane probe was not rerun
  on `dd6e9607e`, and the peer's reported probe there is the only check of it.
  - **Probe run 2**
    ([`probe-lane-run2.json`](../../evidence/artifacts/omniroute-gateway-20260927/probe-lane-run2.json)):
    - `codex exec` exited 0, the shell tool returned the marker and the final answer was the marker;
    - turn 1 had 312 reasoning tokens and read 0 from cache;
    - turn 2 read 13,568 of 14,206 input tokens from cache, on the same account as turn 1;
    - the rollout's `turn_context` shows `cx/gpt-6-astra` at `max`;
    - the gateway's call-log listing holds each of the two requests twice. The pattern is consistent with the list
      route's merge of in-memory entries with persisted rows (OR `src/app/api/usage/call-logs/route.ts` L116-226),
      but the ids are withheld, so it is not proven. The evidence README gives the arithmetic.
  - **Effort**
    ([`gateway-effort-rows.json`](../../evidence/artifacts/omniroute-gateway-20260927/gateway-effort-rows.json)):
    - the gateway's `call_logs` show `reasoning_effort_requested=max` and `reasoning_effort_upstream=max` on both
      reasoning turns, 06:59:07Z for run 1 and 07:00:03Z for run 2;
    - the writer fills these columns only for rows whose reasoning observation is `encrypted` (OR
      `src/lib/usage/callLogs.ts` L646-653), which is consistent with the nulls on the three rows without reasoning;
    - neither call-log API returns the columns. Both map persisted rows with `mapSummaryRow`, which has no effort
      field (OR `src/lib/usage/callLogs.ts` L457-508, L1021 and L1040), and the list route's in-memory entries carry
      none either (OR `src/app/api/usage/call-logs/route.ts` L141-174, L186-215). So a read-only SQLite select read
      these columns only;
    - run 1's client usage (27,996 input tokens,
      [`probe-lane-client-events.json`](../../evidence/artifacts/omniroute-gateway-20260927/probe-lane-client-events.json))
      exceeds its one row (13,806), so at least one follow-up request of run 1 has no `call_logs` row. This record
      does not explain that.
  - **Search**
    ([`probe-search-profile-only.json`](../../evidence/artifacts/omniroute-gateway-20260927/probe-search-profile-only.json),
    [`gateway-search-log.jsonl`](../../evidence/artifacts/omniroute-gateway-20260927/gateway-search-log.jsonl),
    [`gateway-readonly-observation.txt`](../../evidence/artifacts/omniroute-gateway-20260927/gateway-readonly-observation.txt)):
    - the route is `web.run` → `/v1/alpha/search` → `duckduckgo-free`;
    - the answer, v3.8.50, is the latest published release ([`upstream-state.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-state.txt));
    - both searches returned 0 results, one a `site:` query and one a plain query, and GPT-6 fetched the page through
      an MCP tool instead;
    - the gateway logged exactly those two queries, and its `call_logs` hold one row per search under the path
      `/v1/search`, where the free provider records it (OR `open-sse/handlers/search.ts` L1625-1638). An earlier
      version of this record said `/v1/alpha/search` writes no `call_logs` rows; the probe had looked only for that
      path.
  - **Peer parity:** 8 of 8 mechanical checks on `dd6e9607e` (decision 6). It is reported in #387's merged commit
    message; its outputs are not retained here.
  - **Reported by the coordinator, outputs not retained:**
    - `scripts/route_repro.py.txt`'s status lines, with every `/v1` inference route answering HTTP 500 on the
      `a58000c7` build (defect 1). Only Codex's side of a 06:32Z probe is retained;
    - that run 1 landed on a different account from run 2. No retained output holds run 1's gateway rows.
- **Unchanged upstream tests, on a non-release tree:**
  - **26 route and keepalive test files on `a58000c7` + #14904**, run with upstream's runner:
    - 184 of 186 pass, 0 fail;
    - 2 skipped, both upstream's own skips ("ReadableStream error simulation hangs in Node.js test runner");
    - #14904's two cases pass: the Proxy-wrapped request and the body-less GET.

    Sources: [`upstream-tests-route-keepalive.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-tests-route-keepalive.txt),
    [`upstream-tests-route-keepalive-detail.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-tests-route-keepalive-detail.txt).
    The exact command line and the list of the 26 files are reported, not retained.
  - **Reported by the coordinator, outputs not retained:**
    - `tests/unit/early-stream-keepalive.test.ts` at 25 of 26 on the `a58000c7` source, where the Proxy case fails
      with the production error, and 26 of 26 with the fix;
    - upstream's `issue-8674-alpha-search` test at 10 of 10, with keepalive still 26 of 26.
  - **Upstream's `npm run test:unit` on the `dd6e9607e` tree, first stage**
    ([`upstream-test-unit-summary.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-test-unit-summary.txt),
    [`upstream-test-unit-failures.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-test-unit-failures.txt)):
    - 43,522 tests: 43,460 pass, 31 fail, 31 skipped;
    - 30 of the failures also fail in the same 21 files on bare `a58000c7`: base reds (#14866);
    - the 31st comes from #13788: `tests/unit/hard-session-lease-bypass-inventory.test.ts:348` finds an unclassified
      connection-query site in the new `/v1/alpha/search` route;
    - #14904 adds no failure.

    Stage 1's failures stopped the script's `&&` chain, so the dashboard stage and `test:unit:serial` did not run.
- **Local integration:**
  - the settings read-back;
  - the installed unit and service state;
  - the build's identity: `BUILD_SHA`, `--version` and the tarball digests;
  - the cherry-pick patch-ids and tree
    ([`installed-build-identity.txt`](../../evidence/artifacts/omniroute-gateway-20260927/installed-build-identity.txt),
    [`cherry-pick-fidelity.txt`](../../evidence/artifacts/omniroute-gateway-20260927/cherry-pick-fidelity.txt));
  - the two builds' source difference ([`build-delta.txt`](../../evidence/artifacts/omniroute-gateway-20260927/build-delta.txt));
  - an independent read-only observation at 10:40Z, after every probe: the unit's listeners and the search rows in
    `call_logs`
    ([`gateway-readonly-observation.txt`](../../evidence/artifacts/omniroute-gateway-20260927/gateway-readonly-observation.txt)).

  The compiled-output check (the fixed construction in 2 places and the Proxy-input form in 0, with the old build the
  reverse) is reported, not retained.
- **Synthetic fixture:** the `Request`-over-`Proxy` reproduction on three Node runtimes. The corrected
  `proxy-repro-independent.txt` supersedes the first `proxy-repro.txt`, which is kept with its flaw noted.
- **Source review:** every upstream line cited above, read at its stated pin: OmniRoute `a58000c7` or `5458026c`,
  Codex `rust-v0.157.1`, systemd `v255`, and Next.js 16.3.5 in the build's `node_modules`. The OmniRoute files cited
  for the call-log listing, the effort columns and the search rows are the same in `dd6e9607e`.
- **Structural validation:** `tests/test_omniroute_gateway_unit.py` checks the template's shape and that it renders to
  the recorded installed unit.

Nothing here is a fidelity-parity result, and none of it certifies another host.

**Not established.** Fidelity parity with native Codex beyond the checks above is not established. These divergences
at `a58000c7` × codex 0.157.1 are known from source and unmeasured here:
- **`reasoning.context: "all_turns"` is dropped.** Codex sends it for Responses Lite models (CX
  `core/src/client.rs` L859-878), and the gateway keeps only `effort` and `summary` (OR `open-sse/executors/codex.ts`
  L1467-1484).
- **Instructions and a summary are injected.** A placeholder `instructions` fills an empty one on native passthrough
  (OR `open-sse/executors/codex.ts` L1362-1369), and `summary: "auto"` fills a missing summary (L366, L374-393).
- **Encrypted arguments are cleared.** Codex clears `encrypted_function_args` for non-OpenAI providers (CX
  `core/src/client.rs` L897-954).
- **Compaction runs locally.** Behind the gateway, compaction runs locally, not remotely: Codex reports remote
  compaction as unsupported for a non-OpenAI, non-Azure provider (CX `model-provider/src/provider.rs` L410-423).

The effort check has no failing control in this record. No clamping 3.8.50 build was probed, and the 3.8.50 clamp
rests on source (OR50 `open-sse/executors/codex.ts` L346-347).

## Alternatives considered

- **Native Codex only.** One account per session. It stays the max-quality default until a preregistered comparison.
- **OmniRoute 3.8.50 from npm.** Rejected: the `xhigh` clamp and the hook sandbox escape.
- **Waiting for npm 3.8.51** (the settings synthesis's U1). Superseded by the user's 05:40Z direction to install the
  branch. The re-pin trigger below keeps that path open.
- **The other open fixes for defect 1:**
  - **#14872** (head `396e1ad2`) and **#14886** (head `86b75f7d`) were not chosen; #14904 has the widest test coverage
    (decision 1).
  - **Running the gateway on Node 22.** Not tried. The corrected fixture constructs there, but defect 2 needed a
    source build anyway. A code fix also covers upstream's Node 24 and 26 targets.
- **CLIProxyAPI v7.3.19 and thezillo/codex-proxy v0.3.7.** These are from the 2026-09-26 runtime-worker discovery,
  which reported that CLIProxyAPI stores tokens unencrypted; this record did not re-check that.
- **Requiring the key and the login** (the settings synthesis's K7 and U2). Overridden by the user (decision 5).
- **The subshell loader in `ExecStart=` instead of `EnvironmentFile=`.** Not needed: the file has no `export` lines,
  which systemd v255 would drop, and the process-environment exposure is the same (decision 2).
- **`--no-recovery`.** Rejected; upstream labels it a debugging mode.
- **Deriving `CODEX_CLIENT_VERSION` from `codex --version` at start** (the settings synthesis's K4). Not taken for this
  unit, which pins the installed value. The template takes it as a placeholder, and the value must follow the Codex
  pin (limitations).
- **`OMNIROUTE_MEMORY_MB=12288`,** the settings synthesis's provisional value. The installed unit uses upstream's
  maximum 16384 on this 102 GiB host. Neither value is measured under the sweep (overturn).

## Overturn conditions

- **Re-pin.** Upstream merges a #14904-equivalent and #13788 into `release/v3.8.51`, or tags or publishes 3.8.51.
  Rebuild from that upstream commit or npm, drop the cherry-picks and the local build record, and move the
  `manifests/stack.json` pin.
- **The comparison favours native.** If the three-arm comparison or a preregistered gateway-parity run favours native
  Codex, the gateway serves framework traffic only.
- **Search.** A search-backend bake-off (SearXNG, wigolo, DuckDuckGo, native; no Tavily) changes the search provider.
- **Load.** Any heap abort or admission 503 shed under the sweep: resize, or run N instances with separate
  `DATA_DIR`s (upstream `docs/guides/DOCKER_GUIDE.md`, scale-out).
- **Posture.** Any multi-user or non-loopback exposure, or any untrusted local process: turn `requireLogin` and
  `REQUIRE_API_KEY` back on and issue per-lane keys.
- **Upstream fixes the preflight.** Upstream handling `findListeningPids() === null` in `serve`'s preflight: remove
  the `lsof` shim.
- **Codex pin changes.** Update `CODEX_CLIENT_VERSION` and rerun the probe.

## Limitations and residuals

- **Upstream CI is red on the base** (#14866). The build is a recorded canary, not a release.
- **#13788 fails one upstream inventory test.** The route's connection-query site is unclassified in
  `tests/unit/hard-session-lease-bypass-inventory.test.ts`. The coordinator's summary says the guard postdates the PR,
  which was opened 2026-09-15; this record did not check that. Upstream must classify the site when it merges #13788.
  It is not patched locally.
- **Two upstream unit stages did not run.** The dashboard stage and `test:unit:serial` never ran on this tree.
- **The lane probe ran on the previous build.** The effort and cache results come from `bf0255649`. They carry to
  `dd6e9607e` by the two-file source difference, not by a rerun (Evidence).
- **One request of run 1 has no `call_logs` row.** Run 1's client usage exceeds its one row, and this record does
  not explain the gap (Evidence).
- **Key separation is not achieved.** `server.env` sits inside `DATA_DIR`, so a raw copy of the directory carries the
  key to its own encrypted tokens. Upstream's native backup copies only `storage.sqlite`, `settings.json`,
  `combos.json` and `providers.json` (OR `bin/cli/commands/backup.mjs` L27-32), so its backups carry no key. Moving
  the secrets out of `DATA_DIR` is a migration, not a regeneration.
- **The inherited manager environment is not isolated.** The unit cannot stop credentials exported into the user
  manager from reaching the service (decision 2). Only the manager's own environment hygiene prevents it.
- **The server secrets have no inventory entry.** `JWT_SECRET`, `API_KEY_SECRET` and `STORAGE_ENCRYPTION_KEY` are not
  in `adoption/credential-inventory.json`. Adding them also means adding the names to the secret-path guard (the
  test `test_inventory_secret_names_are_all_guarded` in `tests/test_secret_path_guard.py`), with a failing-first
  control. That is a separate change.
- **The exclude filter is absent.** The Codex profile has `shell_snapshot = false`, but not the
  `[shell_environment_policy.filters]` exclude for `OMNIROUTE_API_KEY` that the settings synthesis recommends (its
  K3). This is moot with the placeholder, but becomes live if a real per-lane key is ever set.
- **The search backend is weak.** `duckduckgo-free` returned few or no results, and none for `site:` queries.
- **The client version is pinned by hand.** `CODEX_CLIENT_VERSION` is a literal in the installed unit, so it must
  follow the Codex pin.
  - **Update 2026-09-30.** The announced version may run ahead of the installed Codex when a released model needs it:
    both units now carry 0.159.1 while the installed Codex is 0.157.1, because the gateway's live codex catalog is
    queried with the announced version and lists `gpt-6.1-sol` only from 0.159.x on. A Codex client that reports its
    own version keeps it on inference. See [the 2026-09-30 record](2026-09-30-omniroute-rebuild.md), Decision 3.
- **One host.** These are this workstation's results. The trading lane's `blueprints/us-equities/routing/README.md:26`
  still says no Linux gateway is proposed, and `catalogs/foundation/surfaces.json` still describes the Windows
  gateway. Those files are not edited here.

## Updates

- 2026-10-03: for the landscape sweep and for cross-family research and review, see [the route settlement](2026-10-03-sweep-gpt6-route-settlement.md); line 318 still states the default.
