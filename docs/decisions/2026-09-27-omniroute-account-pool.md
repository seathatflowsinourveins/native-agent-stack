# Decision: an OmniRoute account pool for GPT-6 lanes: a source build of release/v3.8.51 with two upstream fixes, a keyless loopback service and Codex wiring (2026-09-27)

**Status: decided by the user and installed on the NativeStack WSL2 workstation on 2026-09-27; this change records
it.** The coordinator session built, installed and verified the gateway before this record was written. This change
touches no host. The gateway is adopted for pooled GPT-6 access. Native Codex stays the max-quality default, and the
agent-sdks layer default is unchanged (decision 6).

**Scope:**
- new: this record; [`evidence/artifacts/omniroute-gateway-20260927/`](../../evidence/artifacts/omniroute-gateway-20260927/README.md);
  the values-free unit template `adoption/templates/systemd/omniroute.service` with its structural test
  `tests/test_omniroute_gateway_unit.py`.
- changed:
  - `docs/foundation-stack.md`: its 3.8.50-only statements are scoped to 3.8.50, and a short section describes this
    build;
  - `manifests/stack.json`: the omniroute component records the running build without changing its release pin
    (decision 7);
  - `catalogs/foundation/manifest.json`: the native-clients and observation-inference layer text;
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

Two facts ruled out the published release. OmniRoute's npm `latest` is 3.8.50, and 3.8.51 is unpublished
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

1. **Every `/v1` inference route answered HTTP 500.** Codex reports this as "high demand". The cause is
   `withDeadlineSignal` (OR `open-sse/utils/earlyStreamKeepalive.ts:341`, added by 8c05ec42 #14808 on 2026-09-25).
   It builds `new Request(request, {signal, headers})`. Next 16.3.5's app-route runtime hands `dynamic: auto` routes a
   Proxy (`proxyNextRequest`, `next/dist/server/route-modules/app-route/module.js` L626-629). The `Request`
   constructor then reads the input's private `#state` through that Proxy. The reproduction fails on all three Node
   lines ([`proxy-repro.txt`](../../evidence/artifacts/omniroute-gateway-20260927/proxy-repro.txt)):
   - Node 24.21.0 (undici 7.29.1) and Node 26.10.0 (undici 8.10.2, upstream's Docker base) throw the `#state`
     TypeError;
   - Node 22.23.3 (undici 6.28.1) throws "already been used".

   So a runtime switch cannot fix it. Three upstream fixes were open on 2026-09-26, all unreviewed: #14872, #14886 and
   #14904.
2. **Codex's standalone `web.run` POSTs `<base_url>/alpha/search` and got 404.** The peer's parity probe found this.
   Upstream #13788 serves that route. It is labelled `deferred-v3.8.52` and adds two files, the route and its test.
   Its second commit is the maintainer's own "sanitize unexpected internal errors".

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

     It also preserves `redirect` and adds the changelog fragment.
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
   - **Addresses.** Loopback only: 127.0.0.1 on ports 20128, 20131 and 20132.
   - **No `--no-recovery`.** Upstream labels it "Disable auto-restart on crash (debugging mode)". The default
     in-process supervisor (two restarts) runs under systemd's `Restart=on-failure`.
   - **Secrets through `EnvironmentFile=` only.** The unit reads `%h/.local/share/omniroute/server.env`, which lives
     inside `DATA_DIR`.
     - **How it was made.** `scripts/make_server_env.py.txt` generated it with `O_EXCL` at mode 0600 in a 0700
       directory, without printing values. `scripts/make_passwordless.py.txt` then made the decision-5 change.
     - **What it holds.** Generated `JWT_SECRET`, `API_KEY_SECRET` and `STORAGE_ENCRYPTION_KEY` (and
       `STORAGE_ENCRYPTION_KEY_VERSION`), plus non-secret `DATA_DIR`, `PORT`, `OMNIROUTE_SERVER_HOST=127.0.0.1` and
       `REQUIRE_API_KEY=false`.
     - **Its format.** Plain `NAME=value` lines. That is the layout and format of upstream's
     own bootstrap, which persists generated secrets to `{DATA_DIR}/server.env` as `NAME=value` lines (OR
     `scripts/build/bootstrap-env.mjs` L1-19 and L183-186).

     Two reasons make `EnvironmentFile=` safe here:
     - **The file format.** systemd v255 drops `export NAME=value` lines (`src/basic/env-util.c` L28-50, the settings
       research's row 34), and this file has none. The repository's credential stores use the `export` form, so no
       unit points at them.
     - **The exposure.** OmniRoute reads these values from its process environment. They are therefore in
       `/proc/<pid>/environ` with any loader, the subshell loader included. That is the same accepted inconsistency
       the `grafana-admin` inventory entry and `docs/secret-storage.md` ("Process environment") record for Grafana's
       loopback unit. `docs/secret-storage.md` step 9's "do not use `EnvironmentFile=`" covers services that accept
       `--env-file`.
   - **Non-secret `Environment=` lines, each with its reason in the unit:**
     - `OMNIROUTE_MEMORY_MB=16384`: upstream accepts 64..16384 inclusive, `scripts/build/runtime-env.mjs` L19.
     - `CODEX_CLIENT_VERSION=0.157.1`: the installed client. It is the fallback for paths that do not forward the
       caller's version (OR `src/shared/constants/codexClient.ts`).
     - `STREAM_READINESS_TIMEOUT_MS=600000` and `STREAM_READINESS_MAX_TIMEOUT_MS=600000`: the defaults are 80000 and
       180000 (OR `src/shared/utils/runtimeTimeouts.ts` L24-25). The content-stall watchdog reuses them, and they would
       abort a max-effort turn that reasons before its first content.
     - `STREAM_ACTIVE_TIMEOUT_MS=3600000`: the default is 1260000, or 21 minutes, and it is never reset by upstream
       bytes (L21).
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
     - Affinity runs first.
     - `docs/routing/AUTO-COMBO.md` recommends sticky 1 for one-model rotation.
     - There is no combo and no router alias. Codex calls `cx/gpt-6-astra` directly, which is K1 of the settings
       synthesis.
   - `promptCacheAffinityEnabled = true`, the default, is kept.
   - Compression stays off: `enabled=false` and `defaultMode="off"`, the seeded defaults.
   - `exclusions = ["codex/*"]`. `a58000c7` removed 3.8.50's native-passthrough compression bypass, and upstream's own
     comment names this exclusion as the remedy (OR `open-sse/handlers/chatCore.ts` L1429-1449).
   - The Thinking Budget mode is `passthrough`, the default. `auto` strips reasoning.
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
   - **Not decided here.** The settings synthesis (K2) recommends moving the provider block out of the host base
     config into the profile, so base config matches `adoption/templates/codex.config.template.toml`. That is the
     Codex-templates unit's scope, not this record's.
5. **Passwordless and keyless, by the user's decision.**
   - **The settings.** `requireLogin=false`, `REQUIRE_API_KEY=false` and `INITIAL_PASSWORD` removed. When
     `INITIAL_PASSWORD` is set, OR `src/lib/db/settings.ts` L301-311 forces `requireLogin=true` as a headless deploy.
   - **Recorded risk.** Any local process can call the management API, including hook registration. Hooks can read
     and rewrite prompts. The `a58000c7` isolated-realm fix closes the sandbox escape, but not hook registration
     itself. Inference keys are advisory.
   - **Mitigation.** The bind is loopback only, on a single-user workstation.
   - **Overturn.** Any multi-user or non-loopback exposure, or any untrusted local process.
   - **What the user overrode.** The settings synthesis recommended requiring the key and the login (K7, U2, and the
     settings research's rows 2, 24 and 25). The user's 06:05Z direction overrides that.
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
     - the settings synthesis's preregistered `omniroute-codex-max-parity` experiment (X1), which has not run.

     Native Codex remains the max-quality default until a preregistered comparison says otherwise.
7. **Repository records.**
   - **`manifests/stack.json` cannot express this build.** A component has one `version` and one `source_pin`, and
     `scripts/landscape.py` requires both to equal the dated landscape freshness snapshot. There is no field for
     cherry-picks. So the omniroute pin stays the published release 3.8.50 (`5458026c`). The component's `freshness`
     and `command_scope` record the base commit, the picks and `BUILD_SHA`, and point here. `upstream_sources` gains
     the base commit and the two PRs.
   - **The unit template is values-free.** Prefix placeholders stand in for paths, and secrets arrive only through
     `EnvironmentFile=`.
   - **The inventory.** The `omniroute` entry describes a keyless loopback gateway with an optional per-lane key.

## Evidence

Retained outputs: [`evidence/artifacts/omniroute-gateway-20260927/`](../../evidence/artifacts/omniroute-gateway-20260927/README.md).
The classes are kept separate.

- **Live provider execution through the gateway (native Codex 0.157.1 at max, 2026-09-27):**
  - **Probe run 2**
    ([`probe-lane-run2.json`](../../evidence/artifacts/omniroute-gateway-20260927/probe-lane-run2.json)):
    - `codex exec` exited 0, the shell tool returned the marker and the final answer was the marker;
    - turn 1 had 312 reasoning tokens and read 0 from cache;
    - turn 2 read 13,568 of 14,206 input tokens from cache, on the same account as turn 1;
    - run 1 landed on a different account (round-robin across sessions).
  - **Effort**
    ([`gateway-effort-rows.json`](../../evidence/artifacts/omniroute-gateway-20260927/gateway-effort-rows.json)):
    - the gateway's `call_logs` show `reasoning_effort_requested=max` and `reasoning_effort_upstream=max` on both
      reasoning turns (06:59:07Z and 07:00:03Z);
    - no API exposes these columns (OR `src/lib/usage/callLogs.ts` L634-652), so a read-only SQLite select read these
      columns only;
    - the Codex rollout's `turn_context` showed `cx/gpt-6-astra` at `max`.
  - **Search**
    ([`probe-search-profile-only.json`](../../evidence/artifacts/omniroute-gateway-20260927/probe-search-profile-only.json),
    [`gateway-search-log.jsonl`](../../evidence/artifacts/omniroute-gateway-20260927/gateway-search-log.jsonl)):
    - the route is `web.run` → `/v1/alpha/search` → `duckduckgo-free`;
    - the answer, v3.8.50, is the latest published release ([`upstream-state.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-state.txt));
    - both searches returned 0 results, one a `site:` query and one a plain query, and GPT-6 fetched the page through
      an MCP tool instead;
    - `/v1/alpha/search` writes no `call_logs` rows.
  - **Peer parity:** 8 of 8 mechanical checks on `dd6e9607e` (decision 6). It is reported in #387's merged commit
    message; its outputs are not retained here.
- **Unchanged upstream tests, on a non-release tree:**
  - 26 route and keepalive test files on `a58000c7` + #14904 with upstream's own runner: 184 of 186 pass, 0 fail, 2
    skipped ([`upstream-tests-route-keepalive.txt`](../../evidence/artifacts/omniroute-gateway-20260927/upstream-tests-route-keepalive.txt)).
  - The coordinator also reported:
    - `tests/unit/early-stream-keepalive.test.ts` at 25 of 26 on the `a58000c7` source, where the Proxy case fails
      with the production error, and 26 of 26 with the fix;
    - upstream's `issue-8674-alpha-search` test at 10 of 10, with keepalive still 26 of 26.

    Those outputs are not retained, so they count as reported, not retained.
  - The full upstream `npm run test:unit` on the built tree is recorded in the evidence README, or marked pending there.
- **Local integration:**
  - the settings read-back;
  - the installed unit and service state;
  - the build's identity: `BUILD_SHA`, `--version` and the tarball digests;
  - the cherry-pick patch-ids and tree
    ([`installed-build-identity.txt`](../../evidence/artifacts/omniroute-gateway-20260927/installed-build-identity.txt),
    [`cherry-pick-fidelity.txt`](../../evidence/artifacts/omniroute-gateway-20260927/cherry-pick-fidelity.txt)).

  The compiled-output check (the fixed construction in 2 places and the Proxy-input form in 0, with the old build the
  reverse) is reported, not retained.
- **Synthetic fixture:** the ten-line `Request`-over-`Proxy` reproduction on three Node runtimes (`proxy-repro.txt`).
- **Source review:** every upstream line cited above, read at `a58000c7` or `5458026c`.
- **Structural validation:** `tests/test_omniroute_gateway_unit.py` checks the template's shape and that it renders to
  the recorded installed unit.

Nothing here is a fidelity-parity result, and none of it certifies another host.

**Not established.** Fidelity parity with native Codex beyond the checks above is not established. The settings
research (rows 2 and 5) records these divergences at `a58000c7` × 0.157.1:
- `reasoning.context: "all_turns"` is dropped;
- placeholder `instructions` and `summary: "auto"` are injected;
- Codex clears `encrypted_function_args` for non-OpenAI providers;
- compaction behind the gateway runs locally, not remotely.

The effort check has no failing control in this record. No clamping 3.8.50 build was probed, and the 3.8.50 clamp
rests on source (OR50 `open-sse/executors/codex.ts` L346-347).

## Alternatives considered

- **Native Codex only.** One account per session. It stays the max-quality default until a preregistered comparison.
- **OmniRoute 3.8.50 from npm.** Rejected: the `xhigh` clamp and the hook sandbox escape.
- **Waiting for npm 3.8.51.** This was U1 of the settings synthesis. Superseded by the user's 05:40Z direction to
  install the branch. The re-pin trigger below keeps that path open.
- **The other open fixes for defect 1:**
  - **#14872** (head `396e1ad2`) and **#14886** (head `86b75f7d`) were not chosen; #14904 has the widest test coverage
    (decision 1).
  - **A Node runtime switch.** Refuted by the reproduction.
- **CLIProxyAPI v7.3.19 and thezillo/codex-proxy v0.3.7.** These are from the 2026-09-26 runtime-worker discovery.
  CLIProxyAPI stores tokens unencrypted.
- **Requiring the key and the login** (K7, U2). Overridden by the user (decision 5).
- **The subshell loader in `ExecStart=` instead of `EnvironmentFile=`** (the settings research's row 34). Not needed:
  the file has no `export` lines, and the process-environment exposure is the same.
- **`--no-recovery`.** Rejected; upstream labels it a debugging mode.
- **Deriving `CODEX_CLIENT_VERSION` from `codex --version` at start** (K4). Not taken for this unit, which pins the
  installed value. The value must follow the Codex pin (limitations).
- **`OMNIROUTE_MEMORY_MB=12288`,** the research's provisional value. The installed unit uses upstream's maximum 16384
  on this 102 GiB host. Neither value is measured under the sweep (overturn).

## Overturn conditions

- **Re-pin.** Upstream merges a #14904-equivalent and #13788 into `release/v3.8.51`, or tags or publishes 3.8.51.
  Rebuild from that upstream commit or npm, drop the cherry-picks and the local build record, and move the
  `manifests/stack.json` pin.
- **The comparison favours native.** If the three-arm comparison or the X1 parity experiment favours native Codex,
  the gateway serves framework traffic only.
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
- **Key separation is not achieved.** `server.env` sits inside `DATA_DIR`, so a raw copy of the directory carries the
  key to its own encrypted tokens. That is the key separation the settings research's row 27 asks for, and it is not
  achieved here. Upstream's native backups exclude `.env` and `server.env` (row 33). Moving the secrets out is a
  migration, not a regeneration.
- **The server secrets have no inventory entry.** `JWT_SECRET`, `API_KEY_SECRET` and `STORAGE_ENCRYPTION_KEY` are not
  in `adoption/credential-inventory.json`. Adding them also means adding the names to the secret-path guard (the
  test `test_inventory_secret_names_are_all_guarded` in `tests/test_secret_path_guard.py`), with a failing-first
  control. That is a separate change.
- **The exclude filter is absent.** The Codex profile has `shell_snapshot = false`, but not
  `[shell_environment_policy.filters] "OMNIROUTE_API_KEY" = "exclude"` (K3). This is moot with the placeholder, but
  becomes live if a real per-lane key is ever set.
- **The search backend is weak.** `duckduckgo-free` returned few or no results, and none for `site:` queries.
- **The client version is pinned by hand.** `CODEX_CLIENT_VERSION` is a literal, so it must follow the Codex pin.
- **One host.** These are this workstation's results. The trading lane's `blueprints/us-equities/routing/README.md:26`
  still says no Linux gateway is proposed, and `catalogs/foundation/surfaces.json` still describes the Windows
  gateway. Those files are not edited here.
