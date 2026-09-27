# OmniRoute account pool: build, service, Codex wiring and probes (2026-09-27)

These are the retained outputs behind [the decision](../../../docs/decisions/2026-09-27-omniroute-account-pool.md). The
gateway is a `systemd --user` service on loopback. It runs a source build of OmniRoute `release/v3.8.51` at
`a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3` with two upstream PRs cherry-picked:
- #14904 as `22fb9f15` and `bf025564`;
- #13788 as `b9f0d76e` and `dd6e9607`.

Its `BUILD_SHA` is `dd6e9607e`. The lane probe and the effort rows ran on the build before it, `bf0255649`; see
[Which build served each live observation](#which-build-served-each-live-observation). The repository's values-free
unit template is [`adoption/templates/systemd/omniroute.service`](../../../adoption/templates/systemd/omniroute.service).

**Where and with what.** The NativeStack WSL2 workstation, 2026-09-27 UTC:
- Node 24.21.0 and npm 11.19.0;
- codex-cli 0.157.1;
- systemd 255.

Four Codex accounts are pooled through OmniRoute's own OAuth. Account identities are withheld here, and no output in
this directory names one.

**How it was staged.**
- The coordinator's [`scripts/stage_evidence.py.txt`](scripts/stage_evidence.py.txt) wrote nine files:
  `build-provenance.json`, `proxy-repro.txt`, `upstream-tests-route-keepalive.txt`, `gateway-effort-rows.json`,
  `gateway-settings-readback.json`, `gateway-search-log.jsonl`, `omniroute.service`, `codex-provider-block.toml` and
  `codex-omniroute-profile.toml`. Its step 8 copied eight script records into `scripts/`. It keeps whitelisted fields
  only:
  - commit ids, digests and versions;
  - test summaries;
  - the effort columns of `/v1` rows and cache-read counts;
  - the settings read-back;
  - the gateway's `SEARCH` log lines.
- `upstream-test-unit-summary.txt` is the coordinator's suite summary, copied verbatim.
- The coordinator first derived `probe-lane-run2.json` and `probe-search-profile-only.json` by hand. That step was
  not declared, and it dropped one of run 2's four gateway rows. The record's author re-derived both files from the
  same private outputs with [`scripts/derive_probe_records.py.txt`](scripts/derive_probe_records.py.txt), which also
  wrote `probe-lane-client-events.json`. The script's sanitization:
  - a gateway row keeps every field `probe_lane.py` printed except `conn_hash`, a 6-hex hash of the connection id. The
    hash becomes `account`, one letter per distinct connection;
  - an events summary keeps event and item counts, error messages, command exit codes, whether the command output
    and the final answer are the marker, and the usage. Thread ids, item ids, commands, outputs and reasoning text are
    dropped;
  - the search record keeps each `web_search` query with its result count, and the MCP call's server, tool, URL
    argument and status, but not its result. It keeps the first sentence of the error item; the rest of that item
    names a local path.

The record's author re-scanned every file before publishing it. There are no emails, account or connection ids,
hashes of ids, UUIDs, headers, request bodies, credential values or personal paths. The only bearer text is the
placeholder `local-loopback`, in a script. Paths are masked: `~` is the home directory and `$SCRATCH` a private
scratch directory. The unit file uses systemd's own `%h`. The record's author added seventeen files, all read-only
observations, reruns, derivations or copies:
- eight observations: `cherry-pick-fidelity.txt`, `installed-build-identity.txt`, `upstream-state.txt`,
  `upstream-test-unit-failures.txt`, `upstream-tests-route-keepalive-detail.txt`, `proxy-repro-independent.txt`,
  `gateway-readonly-observation.txt` and `build-delta.txt`;
- the three probe records derived by `derive_probe_records.py`;
- the coordinator's suite summary: `upstream-test-unit-summary.txt`;
- five script records: `lsof-shim.sh.txt`, `make_server_env.py.txt`, `make_passwordless.py.txt`,
  `derive_probe_records.py.txt` and `observe_gateway.py.txt`.

## Which build served each live observation

| Observation | Time (UTC) | Build | Basis |
| --- | --- | --- | --- |
| The failed lane probe | 06:32:01Z | not retained | [`probe-lane-client-events.json`](probe-lane-client-events.json) holds only Codex's side. |
| Lane probe runs 1 and 2; the effort rows | 06:58:40Z to 07:00:11Z | `bf0255649` (`a58000c7` + #14904) | These predate the `dd6e9607e` service start at 07:19:46Z ([`installed-build-identity.txt`](installed-build-identity.txt)), and [`build-provenance.json`](build-provenance.json) records `bf0255649` as superseded at 07:19:45Z. |
| The two search probes | 07:20:12Z and 07:28:01Z | `dd6e9607e` | The same process ran from 07:19:46Z with 0 restarts. That was observed at 07:57Z (`installed-build-identity.txt`) and at 10:40Z ([`gateway-readonly-observation.txt`](gateway-readonly-observation.txt)). |
| Listeners and search call-log rows | observed 10:40:04Z | `dd6e9607e` | The same observations. |

[`build-delta.txt`](build-delta.txt) shows that the two builds differ in two files: the `/v1/alpha/search` route and
its test. So the `/v1/responses` effort and cache results are expected to hold on the running build. That is an
inference from the diff, and this record did not rerun the lane probe on `dd6e9607e`. The peer's 8-check probe on
`dd6e9607e` includes effort `max`/`max` in `call_logs`. It is reported in the message of merged commit `b9abcc5f`
(#387) and not retained here.

## What was not done

- **No fidelity parity with native Codex beyond the listed checks.** Known divergences at `a58000c7` × codex 0.157.1
  remain unmeasured: `reasoning.context: "all_turns"` is dropped, placeholder `instructions` and `summary: "auto"` are
  injected, Codex clears `encrypted_function_args` for non-OpenAI providers, and compaction behind the gateway runs
  locally. None of the following ran:
  - `omniroute-codex-max-parity`, the gateway-parity experiment sketched in the coordinator's settings synthesis
    (not retained or frozen in this repository);
  - a rerun of the three-arm workers comparison that gates the agent-sdks layer (`docs/grand-catalog-handbook.md:602`).
- **Upstream CI is red on the base commit.** Issue [#14866](https://github.com/diegosouzapw/OmniRoute/issues/14866),
  "Release branch not green: release/v3.8.51", is open. [`upstream-state.txt`](upstream-state.txt) lists the failing
  check runs. The build is a recorded canary: upstream's pack gate accepted it only with
  `OMNIROUTE_ALLOW_CANARY_BUILD=1`.
- **Only the first stage of upstream's unit script ran.** `npm run test:unit` chains three `node --test` stages
  with `&&`, and stage 1's 31 failures stopped the chain. The dashboard stage and `test:unit:serial` did not run, and
  their results are unknown ([`upstream-test-unit-failures.txt`](upstream-test-unit-failures.txt)).
- **One upstream test fails because of the picks and is not patched.** #13788's new route adds a connection-query
  site that the hard-session-lease inventory guard does not classify
  (`tests/unit/hard-session-lease-bypass-inventory.test.ts:348`).
- **Reported, not retained.** The coordinator observed the following, but their outputs are not in this directory:
  - defect 1's gateway-side symptom: `route_repro.py`'s status lines, with every `/v1` inference route answering
    HTTP 500 on the `a58000c7` build. `probe-lane-client-events.json` keeps Codex's side of the 06:32Z probe: five
    reconnects and a failed turn, all with the "high demand" message. Codex 0.157.1 shows that message for an
    HTTP 500 from its provider (`codex-rs/codex-api/src/api_bridge.rs` L157-158 at `rust-v0.157.1`). The events do
    not show whether the gateway raised the 500 or passed on an upstream one, or which build served them;
  - that probe run 1 landed on a different account from run 2. No retained output holds run 1's gateway rows;
  - `tests/unit/early-stream-keepalive.test.ts` at 25 of 26 on the `a58000c7` source (the Proxy case fails with the
    production TypeError) and 26 of 26 with #14904: the red-to-green control for defect 1;
  - upstream's `issue-8674-alpha-search` test at 10 of 10;
  - the exact command line and the 26-file selection of the route and keepalive run (its totals, skips and #14904
    cases are retained);
  - the compiled-output check: the fixed `Request` construction in 2 places and the Proxy-input form in 0, with the
    old build the reverse;
  - the peer's 8-check parity probe on `dd6e9607e`, recorded in the message of merged commit `b9abcc5f` (#387).
- **Run 1's follow-up request has no `call_logs` row.** Run 1's client usage is 27,996 input tokens
  (`probe-lane-client-events.json`). Its one row in `gateway-effort-rows.json`, at 06:59:07Z, holds 13,806 of them
  and the run's 293 reasoning tokens. So at least one follow-up request of run 1 has no row in that select. Run 2's
  follow-up has its row. This record does not explain the gap.
- **No failing control for the effort metric.** No clamping 3.8.50 gateway was probed in this record. The 3.8.50
  clamp rests on source ([`codex.ts` L346-347 at v3.8.50](https://github.com/diegosouzapw/OmniRoute/blob/5458026c216f77a3da68ea49152dc33470cfe2cb/open-sse/executors/codex.ts#L346-L347)).
- **No host change by this record.** The coordinator installed and configured everything before this directory was
  written. The record's author's own observations are read-only.

## Records

Upstream line numbers below without a pin are at `a58000c7`. The files they cite, `src/lib/usage/callLogs.ts`,
`src/app/api/usage/call-logs/route.ts` and `open-sse/handlers/search.ts`, are the same in `dd6e9607e`.

| File | Evidence class | What it shows |
| --- | --- | --- |
| [`build-provenance.json`](build-provenance.json) | local integration (build provenance) | Everything needed to identify the build: the base branch and commit; both cherry-picks with their upstream commits, PR heads, the commits they were applied as and their state on 2026-09-27; both builds with tarball sha256 (`bf0255649` superseded at 07:19:45Z, `dd6e9607e` running); the toolchain; upstream's build commands; and the two lines of the pack gate, where the canary was accepted with `OMNIROUTE_ALLOW_CANARY_BUILD=1`. |
| [`cherry-pick-fidelity.txt`](cherry-pick-fidelity.txt) | local integration, read-only `git` | Each of the four applied commits has the same `git patch-id --stable` as its upstream commit. It also gives the build head's parent chain down to `a58000c7` and its tree, `6f3f9a23…`. A re-verifier who cherry-picks the four upstream commits onto `a58000c7` gets that tree. |
| [`build-delta.txt`](build-delta.txt) | local integration, read-only `git` | `git diff` from `bf0255649` to `dd6e9607e`: two files, `src/app/api/v1/alpha/search/route.ts` and `tests/unit/issue-8674-alpha-search.test.ts`, with 415 insertions. |
| [`installed-build-identity.txt`](installed-build-identity.txt) | independent observation (read-only) | The tarball digests equal the provenance. The installed `dist/BUILD_SHA` is `dd6e9607e`, and `omniroute --version` prints `3.8.51`. The installed unit is byte-identical to [`omniroute.service`](omniroute.service) (`diff` rc 0). The service is `active`/`running`, started 07:19:46Z, with 0 restarts, and `/api/health` returned `ok`. |
| [`gateway-readonly-observation.txt`](gateway-readonly-observation.txt) | independent observation (read-only, 10:40Z, after every probe) | The same process as above: started 07:19:46Z, 0 restarts. The unit's three processes listen on `127.0.0.1:20128`, `127.0.0.1:20131` and `127.0.0.1:20132` and nowhere else, and no other process holds those ports. `call_logs` holds 8 rows of the `duckduckgo-free` provider from 07:20:21Z to 07:28:32Z, each with path `/v1/search`, `requestType` `search` and status 200. Each row follows one `SEARCH` line by about its own duration. |
| [`upstream-state.txt`](upstream-state.txt) | live upstream metadata (`npm view`, `git ls-remote`, `gh api`) | At 07:58Z: npm `latest` is 3.8.50; `release/v3.8.51` is at `a58000c7`; #14904, #13788 (`deferred-v3.8.52`), #14872 and #14886 are open and unmerged; #14866 is open; the latest release is v3.8.50. The check runs on `a58000c7` include failures (Release acceptance, Node 24 and Node 26 compat shards, promptfoo, garak). |
| [`proxy-repro.txt`](proxy-repro.txt) | synthetic fixture (root-cause reproduction; first attempt, flawed) | The coordinator's first ten-line Node script, kept as it ran. Node 24.21.0/undici 7.29.1 and Node 26.10.0/undici 8.10.2 fail the proxied construction with the `#state` TypeError. Its two arms share one POST body, and the raw arm consumes it first. So its Node 22.23.3/undici 6.28.1 "already been used" result comes from that shared body, not from the Proxy, and it does not show that a runtime switch cannot help. The GPT-6 review of this record found this; the next row supersedes it. |
| [`proxy-repro-independent.txt`](proxy-repro-independent.txt) | synthetic fixture (corrected rerun by the record's author) | Each arm builds its own `Request`, POST and GET, and is rebuilt with `new Request(input, {signal, headers})` as `withDeadlineSignal` does. On Node 24.21.0 and 26.10.0 the proxied cases fail with the `#state` TypeError and the raw cases construct. On Node 22.23.3 all four construct. So defect 1 is specific to the newer Node lines here. The gateway was not run on Node 22 or Node 26. |
| [`upstream-tests-route-keepalive.txt`](upstream-tests-route-keepalive.txt) | unchanged upstream tests, non-release tree | TAP summary of 26 upstream route and keepalive test files on `a58000c7` + #14904, run with upstream's `node --test` runner: 186 tests, 184 pass, 0 fail, 2 skipped. The exact command line and the list of 26 files are reported by the coordinator and not retained, so the selection itself is reported, not retained. |
| [`upstream-tests-route-keepalive-detail.txt`](upstream-tests-route-keepalive-detail.txt) | unchanged upstream tests (extraction by the record's author) | The same run's totals, taken from its private TAP. The two skipped tests are upstream's own skips ("ReadableStream error simulation hangs in Node.js test runner"), and there are 0 `not ok` lines. #14904's two cases pass: `withDeadlineSignal accepts a Proxy-wrapped request (Next.js proxyNextRequest)` and `withDeadlineSignal keeps a body-less GET request valid`. |
| [`upstream-test-unit-summary.txt`](upstream-test-unit-summary.txt) | unchanged upstream tests, non-release tree (the coordinator's summary, verbatim) | Upstream's `npm run test:unit` on the `dd6e9607e` tree, Node 24.21.0. The summary says 07:45Z to 08:17Z, but the run actually spanned about 07:31Z to 08:03Z (see the next row). There were 43,522 tests: 43,460 pass, 31 fail, 31 skipped. The same 21 failing files were rerun on bare `a58000c7`: 225 tests, 195 pass, 30 fail, the same 30 failures (base reds; #14866). The one added failure comes from #13788: `hard-session-lease-bypass-inventory.test.ts:348`, which has an unclassified connection-query site in the new `/v1/alpha/search` route. It is an inventory classification gap, not patched locally. #14904 adds no failure. The summary calls the run the "full unit suite"; see the next row. |
| [`upstream-test-unit-failures.txt`](upstream-test-unit-failures.txt) | unchanged upstream tests (extraction by the record's author) | The runner's own totals, copied from the private output. It also lists the 21 failing files and the 31 failing names on the build, and diffs them with the base's 30: exactly one name is added. The output holds one totals block, so stage 1's failures stopped the script's `&&` chain. Upstream's dashboard stage and `test:unit:serial` did not run. A dated correction places the run at about 07:31Z to 08:03Z, from the process's elapsed time and the output file's mtime. |
| [`omniroute.service`](omniroute.service) | local integration (installed state) | The installed unit. It holds no secret; the secrets it adds come through `EnvironmentFile=`, and it also inherits the user manager's environment. Most non-secret `Environment=` lines carry a reason comment; `OMNIROUTE_MEMORY_MB` has none here, and the template gives every line its own. It also shows the `lsof` shim on `PATH`, `serve --port 20128 --no-open --no-tray` without `--no-recovery`, `Restart=on-failure`, `UMask=0077` and `NoNewPrivileges=true`. |
| [`gateway-settings-readback.json`](gateway-settings-readback.json) | local integration (settings API read-back) | The applied settings: `sessionAffinityTtlMs` 14400000; codex `round-robin` with sticky limit 1; `promptCacheAffinityEnabled` true; `requireLogin` false; compression disabled and off, with the `codex/*` exclusion; Thinking Budget `passthrough`; MCP and A2A off. |
| [`codex-provider-block.toml`](codex-provider-block.toml) | local integration (installed client config) | `[model_providers.omniroute]` as installed in `~/.codex/config.toml`: the loopback `/v1` base URL, `env_key`, `requires_openai_auth = false`, `wire_api = "responses"` and `supports_standalone_web_search = true`. `supports_websockets` is unset. |
| [`codex-omniroute-profile.toml`](codex-omniroute-profile.toml) | local integration (installed client config) | The `omniroute` profile: `cx/gpt-6-astra` at `max`, `web_search = "live"`, `standalone_web_search` on and `shell_snapshot` off. |
| [`probe-lane-client-events.json`](probe-lane-client-events.json) | live provider execution through the gateway (Codex's side only) | Client events of the two `probe_lane.py` runs before run 2. The 06:32:01Z run: five "Reconnecting... n/5" errors and a failed turn, all with "We're currently experiencing high demand, which may cause temporary errors.", and no usage. Run 1, started 06:58:50Z: the shell tool returned the marker, the final answer was the marker, and usage was 27,996 input tokens (13,568 cached), 374 output and 293 reasoning. The probe's gateway listing for these runs was not kept. |
| [`probe-lane-run2.json`](probe-lane-run2.json) | live provider execution through the gateway (build `bf0255649`) | Run 2, started 06:59:46Z. `codex exec` through the launcher exited 0 after 25.2 s. The shell tool returned the marker, and the final answer was the marker. Client usage was 28,012 input tokens (13,568 cached), 390 output and 312 reasoning. The rollout's `turn_context` shows `cx/gpt-6-astra` at `max`. The gateway's call-log listing holds four rows since the start, all on one account. Turn 1 has 312 reasoning tokens and 0 cache reads. The follow-up read 13,568 of 14,206 input tokens from cache. `effort_fields` is empty on every row; `probe_lane.py` also writes `{}` when the detail call fails (L111-116). See the next paragraph for why each request is listed twice. |
| [`gateway-effort-rows.json`](gateway-effort-rows.json) | live provider execution (the gateway's own `call_logs`, read-only select; build `bf0255649`) | The five `/v1` rows from 06:58Z to 07:01Z. Two are reasoning turns: 06:59:07Z is run 1's turn 1, with the run's 293 reasoning tokens, and 07:00:03Z is run 2's. Both have `effort_requested=max` and `effort_upstream=max`. The columns are null on two short calls, `/v1/chat/completions` at 06:58:40Z (21 input tokens) and `/v1/responses` at 06:58:42Z (22), and on run 2's cached follow-up. The writer fills both columns only for a row whose reasoning observation is `encrypted` (`src/lib/usage/callLogs.ts` L646-653), which is consistent with those nulls. Neither call-log API returns the columns, so a read-only SQLite select read them. `getCallLogs` (L1021) and `getCallLogById` (L1040) map their rows with `mapSummaryRow` (L457-508), and the list route adds in-memory entries (`src/app/api/usage/call-logs/route.ts` L141-174, L186-215); none of these has an effort field. |
| [`probe-search-profile-only.json`](probe-search-profile-only.json) | live provider execution through the gateway (build `dd6e9607e`) | Started 07:28:01Z. It used the profile's own web-search keys, with no `-c` overrides, as the coordinator ran it; the events file does not record the mode. The events hold 2 `web_search` items, each with 0 results (one a `site:` query, one plain), and 2 command executions. They also hold 1 MCP call, `context-mode` `ctx_fetch_and_index` of the release page. The one error item is Codex's warning "Under-development features enabled: standalone_web_search." The final answer is v3.8.50 with the release page URL. Usage was 143,526 input tokens (94,464 cached), 1,222 output and 620 reasoning. The gateway's `SEARCH` lines after the start are exactly the two queries, at 07:28:18Z and 07:28:31Z. |
| [`gateway-search-log.jsonl`](gateway-search-log.jsonl) | live provider execution (gateway log; build `dd6e9607e`) | The last 8 `SEARCH` lines, 07:20:21Z to 07:28:31Z, from more than one probe, all `duckduckgo-free`. Each line means the free provider ran (`open-sse/handlers/search.ts` L1606); a request answered with 404 would leave no line. The provider also records each search in `call_logs` under the path `/v1/search` (L1625-1638), and `gateway-readonly-observation.txt` holds those 8 rows. An earlier version of this record said that `/v1/alpha/search` writes no `call_logs` rows. That came from `probe_search.py`, which looks only for `alpha/search` in the path. |
| [`scripts/`](scripts/) | record | The drivers as run, with paths masked: `probe_lane.py`, `probe_search.py`, `effort_rows.py` (a read-only SQLite select of non-sensitive columns), `apply_settings.py`, `read_settings.py`, `route_repro.py`, `list_connections.py` (counts only) and `stage_evidence.py`. The last one wrote the nine files named under "How it was staged". The directory also holds `make_server_env.py` and `make_passwordless.py`, which generate and adjust the service environment file and print no values, and `lsof-shim.sh`, the installed `PATH` shim (decision 2). The record's author added `derive_probe_records.py`, which derived the three probe records, and `observe_gateway.py`, the read-only observation. The records are verbatim. Two docstrings misstate their source. `make_passwordless.py` says `settings.ts` forces `requireLogin=true` whenever `INITIAL_PASSWORD` is set, but the upstream condition also requires incomplete first-time setup (`!settings.setupComplete`, `src/lib/db/settings.ts` L301-311 at `a58000c7`). `effort_rows.py` cites `callLogs.ts:634-652` for the effort columns, but the lines that fill them are L646-653. |

**Why run 2's listing has four rows for two requests.** In each pair, one row carries the request's start time, a
null `requestedModel`, a `cacheCreation` token key and null `cacheSource` and formats. That row's start plus its
duration lands on the other row's timestamp:
- 06:59:48.943Z + 14,532 ms = 07:00:03.475Z, and the other row is at 07:00:03.480Z;
- 07:00:03.875Z + 7,469 ms = 07:00:11.344Z, and the other row is at 07:00:11.351Z.

The other row carries `requestedModel` `codex/gpt-6-astra`, a `cacheWrite` key and `cacheSource` `upstream`. Only these
rows are in the database select (`gateway-effort-rows.json`). That matches upstream's list route
(`src/app/api/usage/call-logs/route.ts` L116-226):
- it merges in-memory entries, active and recently completed, with the persisted rows (L218);
- a completed in-memory entry carries the start time, a null `requestedModel` and null `cacheSource` and formats
  (L186-215);
- a persisted row is mapped by `mapSummaryRow`, which names the cache-creation count `cacheWrite`
  (`src/lib/usage/callLogs.ts` L479) and defaults `cacheSource` to `upstream` (L483);
- the route drops a completed in-memory entry only when its id equals a persisted row's id (L180).

The ids are withheld, so this pairing is consistent with the source, not proven.

## How to re-verify

- **Upstream state:**
  - `gh api repos/diegosouzapw/OmniRoute/pulls/14904 --jq '.state,.merged_at,.head.sha'`, and the same for 13788;
  - `gh api repos/diegosouzapw/OmniRoute/issues/14866 --jq .state`;
  - `npm view omniroute dist-tags`;
  - `git ls-remote https://github.com/diegosouzapw/OmniRoute refs/heads/release/v3.8.51`.

  Any change there can trigger the decision's re-pin condition.
- **The build tree.** Clone upstream and fetch the two PR heads. Check out `a58000c7` and cherry-pick `07a6317b2`,
  `b94e2dba4`, `24bbadbad` and `6c7990058` in that order. Then compare `git rev-parse HEAD^{tree}` with
  `6f3f9a23068b6640b1084682dba6aab144ddbdc2`. Commit ids and `BUILD_SHA` differ on a rebuild, because the committer
  and time differ; the tree does not.
- **The installed state:**
  - `systemctl --user cat omniroute.service` against [`omniroute.service`](omniroute.service);
  - `<prefix>/lib/node_modules/omniroute/dist/BUILD_SHA`;
  - `sha256sum` of a kept tarball against the provenance;
  - `ss -Hltn` for the three loopback listeners, or [`observe_gateway.py`](scripts/observe_gateway.py.txt), which
    also ties them to the unit's cgroup and lists the search rows.
- **Gateway behaviour.** Rerun [`read_settings.py`](scripts/read_settings.py.txt),
  [`probe_lane.py`](scripts/probe_lane.py.txt) and [`effort_rows.py`](scripts/effort_rows.py.txt) with their masked
  paths filled in. A new run is a new observation. It does not replay or certify these results.
- **The probe records.** [`derive_probe_records.py`](scripts/derive_probe_records.py.txt) needs the private probe
  outputs, so only the coordinator can rerun it. Its checks are in the script: run 2's usage equals its events file,
  the row count equals the listing's own count, and the `SEARCH` lines equal the `web_search` queries.

This host's results are not another host's acceptance.
