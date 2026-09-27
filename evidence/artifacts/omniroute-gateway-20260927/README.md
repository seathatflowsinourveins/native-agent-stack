# OmniRoute account pool: build, service, Codex wiring and probes (2026-09-27)

These are the retained outputs behind [the decision](../../../docs/decisions/2026-09-27-omniroute-account-pool.md). The
gateway is a `systemd --user` service on loopback. It runs a source build of OmniRoute `release/v3.8.51` at
`a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3` with two upstream PRs cherry-picked:
- #14904 as `22fb9f15` and `bf025564`;
- #13788 as `b9f0d76e` and `dd6e9607`.

Its `BUILD_SHA` is `dd6e9607e`. The repository's values-free unit template is
[`adoption/templates/systemd/omniroute.service`](../../../adoption/templates/systemd/omniroute.service).

**Where and with what.** The NativeStack WSL2 workstation, 2026-09-27 UTC:
- Node 24.21.0 and npm 11.19.0;
- codex-cli 0.157.1;
- systemd 255.

Four Codex accounts are pooled through OmniRoute's own OAuth. Account identities are withheld here, and no output in
this directory names one.

**How it was staged.** The coordinator's [`scripts/stage_evidence.py.txt`](scripts/stage_evidence.py.txt) staged the
files, keeping whitelisted fields only:
- commit ids, digests and versions;
- test summaries;
- the effort columns of `/v1` rows and cache-read counts;
- same-or-different account relations, never ids or hashes of ids;
- the settings read-back;
- the gateway's `SEARCH` log lines.

The record's author re-scanned every file before publishing it. There are no emails, account or connection ids,
UUIDs, headers, request bodies, credential values or personal paths. The only bearer text is the placeholder
`local-loopback`, in a script. Paths are masked: `~` is the home directory and `$SCRATCH` a private scratch
directory. The unit file uses systemd's own `%h`. The record's author added ten files, all read-only
observations, reruns or copies:
- six observations: `cherry-pick-fidelity.txt`, `installed-build-identity.txt`, `upstream-state.txt`,
  `upstream-test-unit-failures.txt`, `upstream-tests-route-keepalive-detail.txt` and
  `proxy-repro-independent.txt`;
- the coordinator's suite summary: `upstream-test-unit-summary.txt`;
- three script records: `lsof-shim.sh.txt`, `make_server_env.py.txt` and `make_passwordless.py.txt`.

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
  - `tests/unit/early-stream-keepalive.test.ts` at 25 of 26 on the `a58000c7` source (the Proxy case fails with the
    production TypeError) and 26 of 26 with #14904: the red-to-green control for defect 1;
  - upstream's `issue-8674-alpha-search` test at 10 of 10;
  - the exact command line and the 26-file selection of the route and keepalive run (its totals, skips and #14904
    cases are retained);
  - the compiled-output check: the fixed `Request` construction in 2 places and the Proxy-input form in 0, with the
    old build the reverse;
  - the peer's 8-check parity probe on `dd6e9607e`, recorded in the message of merged commit `b9abcc5f` (#387).
- **No failing control for the effort metric.** No clamping 3.8.50 gateway was probed in this record. The 3.8.50
  clamp rests on source ([`codex.ts` L346-347 at v3.8.50](https://github.com/diegosouzapw/OmniRoute/blob/5458026c216f77a3da68ea49152dc33470cfe2cb/open-sse/executors/codex.ts#L346-L347)).
- **No host change by this record.** The coordinator installed and configured everything before this directory was
  written.

## Records

| File | Evidence class | What it shows |
| --- | --- | --- |
| [`build-provenance.json`](build-provenance.json) | local integration (build provenance) | Everything needed to identify the build: the base branch and commit; both cherry-picks with their upstream commits, PR heads, the commits they were applied as and their state on 2026-09-27; both builds with tarball sha256 (`bf0255649` superseded at 07:19:45Z, `dd6e9607e` running); the toolchain; upstream's build commands; and the two lines of the pack gate, where the canary was accepted with `OMNIROUTE_ALLOW_CANARY_BUILD=1`. |
| [`cherry-pick-fidelity.txt`](cherry-pick-fidelity.txt) | local integration, read-only `git` | Each of the four applied commits has the same `git patch-id --stable` as its upstream commit. It also gives the build head's parent chain down to `a58000c7` and its tree, `6f3f9a23…`. A re-verifier who cherry-picks the four upstream commits onto `a58000c7` gets that tree. |
| [`installed-build-identity.txt`](installed-build-identity.txt) | independent observation (read-only) | The tarball digests equal the provenance. The installed `dist/BUILD_SHA` is `dd6e9607e`, and `omniroute --version` prints `3.8.51`. The installed unit is byte-identical to [`omniroute.service`](omniroute.service) (`diff` rc 0). The service is `active`/`running`, started 07:19:46Z, with 0 restarts, and `/api/health` returned `ok`. |
| [`upstream-state.txt`](upstream-state.txt) | live upstream metadata (`npm view`, `git ls-remote`, `gh api`) | At 07:58Z: npm `latest` is 3.8.50; `release/v3.8.51` is at `a58000c7`; #14904, #13788 (`deferred-v3.8.52`), #14872 and #14886 are open and unmerged; #14866 is open; the latest release is v3.8.50. The check runs on `a58000c7` include failures (Release acceptance, Node 24 and Node 26 compat shards, promptfoo, garak). |
| [`proxy-repro.txt`](proxy-repro.txt) | synthetic fixture (root-cause reproduction; first attempt, flawed) | The coordinator's first ten-line Node script, kept as it ran. Node 24.21.0/undici 7.29.1 and Node 26.10.0/undici 8.10.2 fail the proxied construction with the `#state` TypeError. Its two arms share one POST body, and the raw arm consumes it first. So its Node 22.23.3/undici 6.28.1 "already been used" result comes from that shared body, not from the Proxy, and it does not show that a runtime switch cannot help. The GPT-6 review of this record found this; the next row supersedes it. |
| [`proxy-repro-independent.txt`](proxy-repro-independent.txt) | synthetic fixture (corrected rerun by the record's author) | Each arm builds its own `Request`, POST and GET, and is rebuilt with `new Request(input, {signal, headers})` as `withDeadlineSignal` does. On Node 24.21.0 and 26.10.0 the proxied cases fail with the `#state` TypeError and the raw cases construct. On Node 22.23.3 all four construct. So defect 1 is specific to the newer Node lines here. The gateway was not run on Node 22. |
| [`upstream-tests-route-keepalive.txt`](upstream-tests-route-keepalive.txt) | unchanged upstream tests, non-release tree | TAP summary of 26 upstream route and keepalive test files on `a58000c7` + #14904, run with upstream's `node --test` runner: 186 tests, 184 pass, 0 fail, 2 skipped. The exact command line and the list of 26 files are reported by the coordinator and not retained, so the selection itself is reported, not retained. |
| [`upstream-tests-route-keepalive-detail.txt`](upstream-tests-route-keepalive-detail.txt) | unchanged upstream tests (extraction by the record's author) | The same run's totals, taken from its private TAP. The two skipped tests are upstream's own skips ("ReadableStream error simulation hangs in Node.js test runner"), and there are 0 `not ok` lines. #14904's two cases pass: `withDeadlineSignal accepts a Proxy-wrapped request (Next.js proxyNextRequest)` and `withDeadlineSignal keeps a body-less GET request valid`. |
| [`upstream-test-unit-summary.txt`](upstream-test-unit-summary.txt) | unchanged upstream tests, non-release tree (the coordinator's summary, verbatim) | Upstream's `npm run test:unit` on the `dd6e9607e` tree, Node 24.21.0. The summary says 07:45Z to 08:17Z, but the run actually spanned about 07:31Z to 08:03Z (see the next row). There were 43,522 tests: 43,460 pass, 31 fail, 31 skipped. The same 21 failing files were rerun on bare `a58000c7`: 225 tests, 195 pass, 30 fail, the same 30 failures (base reds; #14866). The one added failure comes from #13788: `hard-session-lease-bypass-inventory.test.ts:348`, which has an unclassified connection-query site in the new `/v1/alpha/search` route. It is an inventory classification gap, not patched locally. #14904 adds no failure. The summary calls the run the "full unit suite"; see the next row. |
| [`upstream-test-unit-failures.txt`](upstream-test-unit-failures.txt) | unchanged upstream tests (extraction by the record's author) | The runner's own totals, copied from the private output. It also lists the 21 failing files and the 31 failing names on the build, and diffs them with the base's 30: exactly one name is added. The output holds one totals block, so stage 1's failures stopped the script's `&&` chain. Upstream's dashboard stage and `test:unit:serial` did not run. A dated correction places the run at about 07:31Z to 08:03Z, from the process's elapsed time and the output file's mtime. |
| [`omniroute.service`](omniroute.service) | local integration (installed state) | The installed unit. It holds no secret; the secrets it adds come through `EnvironmentFile=`, and it also inherits the user manager's environment. Most non-secret `Environment=` lines carry a reason comment; `OMNIROUTE_MEMORY_MB` has none here, and the template gives every line its own. It also shows the `lsof` shim on `PATH`, `serve --port 20128 --no-open --no-tray` without `--no-recovery`, `Restart=on-failure`, `UMask=0077` and `NoNewPrivileges=true`. |
| [`gateway-settings-readback.json`](gateway-settings-readback.json) | local integration (settings API read-back) | The applied settings: `sessionAffinityTtlMs` 14400000; codex `round-robin` with sticky limit 1; `promptCacheAffinityEnabled` true; `requireLogin` false; compression disabled and off, with the `codex/*` exclusion; Thinking Budget `passthrough`; MCP and A2A off. |
| [`codex-provider-block.toml`](codex-provider-block.toml) | local integration (installed client config) | `[model_providers.omniroute]` as installed in `~/.codex/config.toml`: the loopback `/v1` base URL, `env_key`, `requires_openai_auth = false`, `wire_api = "responses"` and `supports_standalone_web_search = true`. `supports_websockets` is unset. |
| [`codex-omniroute-profile.toml`](codex-omniroute-profile.toml) | local integration (installed client config) | The `omniroute` profile: `cx/gpt-6-astra` at `max`, `web_search = "live"`, `standalone_web_search` on and `shell_snapshot` off. |
| [`probe-lane-run2.json`](probe-lane-run2.json) | live provider execution through the gateway | `codex exec` through the launcher exited 0 after 25.2 s. The shell tool returned the marker, and the final answer was the marker. Client usage was 28,012 input tokens (13,568 cached), 390 output and 312 reasoning. The gateway rows show turn 1 with 312 reasoning tokens and 0 cache reads, and the follow-up with 13,568 cache reads of 14,206 input on the same account as turn 1. Run 1, at 06:59Z, landed on a different account. The follow-up appears twice in this API listing (07:00:03Z with no requested model, and 07:00:11Z); the database select below has one row for it. The duplicate is not explained. |
| [`gateway-effort-rows.json`](gateway-effort-rows.json) | live provider execution (the gateway's own `call_logs`, read-only select) | The five `/v1` rows from 06:58Z to 07:01Z. Both reasoning turns (06:59:07Z for run 1 and 07:00:03Z for run 2) have `effort_requested=max` and `effort_upstream=max`. The columns are null on two short calls, `/v1/chat/completions` at 06:58:40Z (21 input tokens) and `/v1/responses` at 06:58:42Z (22), and on the cached follow-up. No API exposes these columns. |
| [`probe-search-profile-only.json`](probe-search-profile-only.json) | live provider execution through the gateway | The profile's own web-search keys, with no `-c` overrides. There were 2 `web_search` items, each with 0 results (one a `site:` query, one plain), 1 error item and 1 MCP tool call; the final answer is v3.8.50 with the release page URL. Usage was 143,526 input tokens (94,464 cached), 1,222 output and 620 reasoning. The file labels the run "07:3xZ"; the gateway log dates its two queries 07:28:18Z and 07:28:31Z. |
| [`gateway-search-log.jsonl`](gateway-search-log.jsonl) | live provider execution (gateway log) | The last 8 `SEARCH` lines, 07:20:21Z to 07:28:31Z, from more than one probe, all `duckduckgo-free`. `/v1/alpha/search` writes no `call_logs` rows, so this log is the gateway-side record. Each line means the search handler ran; a request answered with 404 would leave no line. |
| [`scripts/`](scripts/) | record | The drivers as run, with paths masked: `probe_lane.py`, `probe_search.py`, `effort_rows.py` (a read-only SQLite select of non-sensitive columns), `apply_settings.py`, `read_settings.py`, `route_repro.py`, `list_connections.py` (counts only) and `stage_evidence.py`, which built this directory. Also `make_server_env.py` and `make_passwordless.py`, which generate and adjust the service environment file and print no values, and `lsof-shim.sh`, the installed `PATH` shim (decision 2). The records are verbatim. One docstring overstates its source: `make_passwordless.py` says `settings.ts` forces `requireLogin=true` whenever `INITIAL_PASSWORD` is set, but the upstream condition also requires incomplete first-time setup (`!settings.setupComplete`, `src/lib/db/settings.ts` L301-311 at `a58000c7`). |

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
  - `sha256sum` of a kept tarball against the provenance.
- **Gateway behaviour.** Rerun [`read_settings.py`](scripts/read_settings.py.txt),
  [`probe_lane.py`](scripts/probe_lane.py.txt) and [`effort_rows.py`](scripts/effort_rows.py.txt) with their masked
  paths filled in. A new run is a new observation. It does not replay or certify these results.

This host's results are not another host's acceptance.
