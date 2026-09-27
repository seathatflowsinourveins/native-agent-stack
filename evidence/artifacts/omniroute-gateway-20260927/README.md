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
directory. The unit file uses systemd's own `%h`. The record's author added six files, all read-only observations
or copies:
- three observations: `cherry-pick-fidelity.txt`, `installed-build-identity.txt` and `upstream-state.txt`;
- three script records: `lsof-shim.sh.txt`, `make_server_env.py.txt` and `make_passwordless.py.txt`.

## What was not done

- **No fidelity parity with native Codex beyond the listed checks.** Known divergences at `a58000c7` × codex 0.157.1
  remain unmeasured: `reasoning.context: "all_turns"` is dropped, placeholder `instructions` and `summary: "auto"` are
  injected, Codex clears `encrypted_function_args` for non-OpenAI providers, and compaction behind the gateway runs
  locally. None of the following ran:
  - the settings synthesis's preregistered `omniroute-codex-max-parity` experiment;
  - a rerun of the three-arm workers comparison that gates the agent-sdks layer (`docs/grand-catalog-handbook.md:602`).
- **Upstream CI is red on the base commit.** Issue [#14866](https://github.com/diegosouzapw/OmniRoute/issues/14866),
  "Release branch not green: release/v3.8.51", is open. [`upstream-state.txt`](upstream-state.txt) lists the failing
  check runs. The build is a recorded canary: upstream's pack gate accepted it only with
  `OMNIROUTE_ALLOW_CANARY_BUILD=1`.
- **Full upstream unit suite.** A full upstream `npm run test:unit` on the built tree was still running when this
  directory was written. Its summary is pending, and no pass count is claimed for it.
- **Reported, not retained.** The coordinator observed the following, but their outputs are not in this directory:
  - `tests/unit/early-stream-keepalive.test.ts` at 25 of 26 on the `a58000c7` source (the Proxy case fails with the
    production TypeError) and 26 of 26 with #14904: the red-to-green control for defect 1;
  - upstream's `issue-8674-alpha-search` test at 10 of 10;
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
| [`proxy-repro.txt`](proxy-repro.txt) | synthetic fixture (root-cause reproduction) | A ten-line Node script: `new Request(proxiedRequest, init)` fails and the raw `Request` works. Node 24.21.0/undici 7.29.1 and Node 26.10.0/undici 8.10.2 fail with the `#state` TypeError, and Node 22.23.3/undici 6.28.1 fails with "already been used". A runtime switch does not fix defect 1. |
| [`upstream-tests-route-keepalive.txt`](upstream-tests-route-keepalive.txt) | unchanged upstream tests, non-release tree | TAP summary of 26 upstream route and keepalive test files on `a58000c7` + #14904, run with upstream's own `node --test` flags: 186 tests, 184 pass, 0 fail, 2 skipped. Per-test lines stay in the private TAP, which holds local paths. |
| [`omniroute.service`](omniroute.service) | local integration (installed state) | The installed unit. Secrets come only through `EnvironmentFile=`, and each non-secret `Environment=` line has a reason comment. It also shows the `lsof` shim on `PATH`, `serve --port 20128 --no-open --no-tray` without `--no-recovery`, `Restart=on-failure`, `UMask=0077` and `NoNewPrivileges=true`. |
| [`gateway-settings-readback.json`](gateway-settings-readback.json) | local integration (settings API read-back) | The applied settings: `sessionAffinityTtlMs` 14400000; codex `round-robin` with sticky limit 1; `promptCacheAffinityEnabled` true; `requireLogin` false; compression disabled and off, with the `codex/*` exclusion; Thinking Budget `passthrough`; MCP and A2A off. |
| [`codex-provider-block.toml`](codex-provider-block.toml) | local integration (installed client config) | `[model_providers.omniroute]` as installed in `~/.codex/config.toml`: the loopback `/v1` base URL, `env_key`, `requires_openai_auth = false`, `wire_api = "responses"` and `supports_standalone_web_search = true`. `supports_websockets` is unset. |
| [`codex-omniroute-profile.toml`](codex-omniroute-profile.toml) | local integration (installed client config) | The `omniroute` profile: `cx/gpt-6-astra` at `max`, `web_search = "live"`, `standalone_web_search` on and `shell_snapshot` off. |
| [`probe-lane-run2.json`](probe-lane-run2.json) | live provider execution through the gateway | `codex exec` through the launcher exited 0 after 25.2 s. The shell tool returned the marker, and the final answer was the marker. Client usage was 28,012 input tokens (13,568 cached), 390 output and 312 reasoning. The gateway rows show turn 1 with 312 reasoning tokens and 0 cache reads, and the follow-up with 13,568 cache reads of 14,206 input on the same account as turn 1. Run 1, at 06:59Z, landed on a different account. The follow-up appears twice in this API listing (07:00:03Z with no requested model, and 07:00:11Z); the database select below has one row for it. The duplicate is not explained. |
| [`gateway-effort-rows.json`](gateway-effort-rows.json) | live provider execution (the gateway's own `call_logs`, read-only select) | The five `/v1` rows from 06:58Z to 07:01Z. Both reasoning turns (06:59:07Z for run 1 and 07:00:03Z for run 2) have `effort_requested=max` and `effort_upstream=max`. The columns are null on two short calls, `/v1/chat/completions` at 06:58:40Z (21 input tokens) and `/v1/responses` at 06:58:42Z (22), and on the cached follow-up. No API exposes these columns. |
| [`probe-search-profile-only.json`](probe-search-profile-only.json) | live provider execution through the gateway | The profile's own web-search keys, with no `-c` overrides. There were 2 `web_search` items, each with 0 results (one a `site:` query, one plain), 1 error item and 1 MCP tool call; the final answer is v3.8.50 with the release page URL. Usage was 143,526 input tokens (94,464 cached), 1,222 output and 620 reasoning. The file labels the run "07:3xZ"; the gateway log dates its two queries 07:28:18Z and 07:28:31Z. |
| [`gateway-search-log.jsonl`](gateway-search-log.jsonl) | live provider execution (gateway log) | The last 8 `SEARCH` lines, 07:20:21Z to 07:28:31Z, from more than one probe, all `duckduckgo-free`. `/v1/alpha/search` writes no `call_logs` rows, so this log is the gateway-side record. Each line means the search handler ran; a request answered with 404 would leave no line. |
| [`scripts/`](scripts/) | record | The drivers as run, with paths masked: `probe_lane.py`, `probe_search.py`, `effort_rows.py` (a read-only SQLite select of non-sensitive columns), `apply_settings.py`, `read_settings.py`, `route_repro.py`, `list_connections.py` (counts only) and `stage_evidence.py`, which built this directory. Also `make_server_env.py` and `make_passwordless.py`, which generate and adjust the service environment file and print no values, and `lsof-shim.sh`, the installed `PATH` shim (decision 2). |

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
