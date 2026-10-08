# QMD shared native transport — 2026-10-08

Both portable client templates connect their existing `qmd` entries to QMD's
native Streamable HTTP service at `http://127.0.0.1:21851/mcp`. This replaces the
per-session stdio launch while preserving the server name and all four tools:
`get`, `multi_get`, `query` and `status`.

The dated trigger is the command-center pilot acceptance and rollout request on
2026-10-08. The practice follows the native vendor transport and selected PSS
observation below. Deployment uses the controlled setup window with registration
before-images, native readiness checks and the scoped inverse. Template landing
requires the explicit configuration-owner cue; publishing the template performs
no user-level configuration change.

## Sources and acceptance scope

- [tobi/qmd v2.8.3](https://github.com/tobi/qmd/tree/facd35e01359e59d938bc9418e93fb9318addee3),
  commit `facd35e01359e59d938bc9418e93fb9318addee3`. The vendor README documents
  native shared HTTP; installed `dist/mcp/server.js` provides `/mcp`, `/health`
  and the four native operations. Package version, installed help and the
  release tag's peeled commit agree. No proxy, bridge or fork is introduced.
- [openai/codex 0.161.0](https://github.com/openai/codex/tree/979011409de0a60b52f179721948e65531d26144),
  `config/src/mcp_types.rs`, `config/src/merge.rs` and `cli/src/mcp_cmd.rs`.
  Native URL-only registrations support Streamable HTTP. Configuration layers
  recursively merge tables; adding a URL over an existing stdio command fails
  bootstrap. Native `codex mcp add qmd --url ...` is a global same-name upsert,
  distinct from a process-only launch overlay.
- Native Linux PSS observations use `/proc/<pid>/smaps_rollup`. Actual client
  readbacks and one successful `status` call on each of two native **Codex**
  lanes corroborate the four-tool surface and shared lexical index. The pilot
  used the temporary `qmdshared` alias with the old stdio entry disabled.
  The final template retains `qmd`; final-name registration and Claude runtime
  acceptance remain setup-window checks.

The source pilot receipt has SHA256
`6e99f2ceed60ba926b2e07b169fbaecf0e0cce64f6250c8b9a6b54e143e4d883`.
Its retained before/after observation hashes are
`af4369e8f3ed9aef17a52de75062a9b5c763f65665a2d2ba6acb09a69e7ad5a5`
and `05b5d5bf71e5bc0639df27028ceefdc035cd90dc847e3b9e5510669f5b4e301d`.
This public projection omits private launch prompts, account/session identifiers,
process IDs, command arrays, host paths and raw client records.

The portable Claude MCP specification uses the same HTTP endpoint as Codex.
Its existing installer already generates native user-scope HTTP registration;
changing the portable file does not hand-edit a user's registration store. The
native-input map retains the QMD slot while removing stdio command overrides and
the obsolete Codex command-leaf selector. The dated source projection remains
separate from runtime acceptance. The installer processes every server in its
selected input; a host QMD-only change therefore uses direct native commands or
a QMD-only input, rather than replacement of the full server set.

## Native pilot receipt

Samples were taken at `2026-10-08T17:19:34Z` and
`2026-10-08T17:28:34Z` using the same native process-memory observer.
The unit is Linux `kB` from `smaps_rollup`, with 1024 bytes per unit.

| Measured cohort | Before PSS (kB) | After PSS (kB) | Matched process rows before → after |
| --- | ---: | ---: | --- |
| Two selected lanes' own QMD processes | 29,801 | 0 | 4 → 0 |
| Shared QMD service processes | 48,077 | 55,768 | 2 → 2 |
| Selected cohort plus shared service | 77,878 | 55,768 | 6 → 2 |

The observed net reduction is **22,110 kB for two lanes**:
`29,801 - (55,768 - 48,077)`. Matched rows include launcher/backend processes;
they are not independent server counts. A third lane relaunched between the
samples, so whole-host totals are confounded and are not used as this result.
This small observation is not extrapolated to the host or fleet.

Both native status smokes returned 425 documents across four collections, no
vector index and 425 documents awaiting embeddings. The shared service preserves
the existing lexical index, `QMD_FORCE_CPU=1` and unset `INDEX_PATH`. This is
transport/status and selected-process memory evidence. Retrieval quality, query
concurrency, model-loaded memory and provider usage were not measured. The earlier
official-MCP-SDK pilot with an embedding-bearing index is a separate observation.

| Claim | Evidence class | Bound |
| --- | --- | --- |
| Two native Codex lanes use shared HTTP and pass `status` | `native_proven` | Temporary alias; four tools; actual readbacks and native responses |
| Selected process-memory reduction | `native_proven` | Two timed samples; selected cohort; disclosed host confound |
| Vendor transport, same-name upsert and merge behavior | `source_review` / `native_proven` | Pinned source and bounded native parse/help checks; no global upsert run by the lane |
| Template rendering and TOML shape | `local_integration` | Existing renderer checks; no host apply or provider invocation |

## Service lifecycle receipt

The owned pilot service was installed and started, with native unit verification,
manager reload and startup returning zero. Its installed unit hash is
`c52f37fc48913a9c5c04d0fdea4528fec67ed6feed6ce7923f579c8c194e606b`.
It was active with zero restarts, and `/health` returned HTTP 200. Boot autostart
was **not enabled** by the pilot.

The reviewed service settings are:

```ini
Type=simple
Environment=QMD_FORCE_CPU=1
UnsetEnvironment=INDEX_PATH
Restart=on-failure
RestartSec=5
TimeoutStartSec=30
TimeoutStopSec=20
KillMode=control-group
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
ExecStartPost=/usr/bin/curl --fail --silent --show-error --retry 10 --retry-delay 1 --retry-connrefused --retry-max-time 20 --max-time 3 http://127.0.0.1:21851/health
```

The native foreground server command is:

```sh
qmd --index native-agent-stack-catalog-lex mcp --http --host 127.0.0.1 --port 21851
```

The command center owns the installation-prefix binding, service startup and
any boot-persistence choice in the setup window. Startup `/health` checks HTTP
health; native tools-list/status checks establish client readiness. These point
checks and restart-on-failure do not establish continuous availability or
recovery after an intentional stop. The template alone does not install, start
or qualify a service on another host.

## Setup and inverse

Before expanded client relaunch, the command center starts/checks the owned
service, captures exact per-server and lane-launch before-images, and replaces
the old transport. URL-only overlay merging must not leave `command`, `args` or
stdio environment fields beside `url`. Preserve existing server metadata,
permissions, model/tier/account choices and every other MCP entry. Both final
native client registrations must retain all four tools under `qmd` without a
duplicate private stdio process. The Claude user-scope change uses `claude mcp`
CLI commands in that window; no manual registration-file editing is part of
this change. The two pilot aliases stay until that controlled relaunch.

For the template inverse, restore only its prior block:

```toml
[mcp_servers.qmd]
command = "${ECO_ROOT}/bin/qmd"
args = ["--index", "native-agent-stack-catalog", "mcp"]
```

Restore the corresponding portable Claude entry as well:

```json
"qmd": {
  "type": "stdio",
  "command": "${ECO_ROOT}/bin/qmd",
  "args": ["--index", "native-agent-stack-catalog", "mcp"],
  "env": {}
}
```

For repository rendering, restore the QMD command override and command-leaf
selector from the pre-change map, then append the resulting native count
projection. Preserve earlier dated observations; do not rewrite their counts.

For an applied host inverse, restore the exact captured QMD transport and
selected lane-launch fragments through supported native configuration tooling.
After clients have reverted, stop/disable only `native-stack-qmd-shared.service`,
remove only that newly installed owned unit if directed, then reload the user
manager. Preserve vendor packages, both indexes, model data, native sign-ins and
all other MCP services. Reverting this template alone does not restore a live
user configuration. Native client `status`, catalog and lifecycle checks after
the inverse remain required.

Keep the direct native route if the final-name/client checks lose capabilities,
duplicate backends remain, lifecycle fails, or the operational dependency costs
more than its measured saving. Other sharing candidates remain at their existing
held or trial status; this decision authorizes QMD's template route only.
