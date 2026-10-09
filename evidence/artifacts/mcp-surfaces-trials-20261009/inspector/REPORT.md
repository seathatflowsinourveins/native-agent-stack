# Inspector 2.10.1 against mcporter 0.14.2

**Proposed default: mcporter 0.14.2 for scripted MCP access on this host.**
Inspector's experimental `mcpdo` is a verified overlap and is faster on the two
warm tasks measured here. mcporter uses less persistent and command-plus-daemon
PSS, and needed less time for the single cold discovery. Under this lane's memory
gate, those measured costs and mcpdo's upstream experimental status favor
mcporter. This is a proposed disposition, not an adoption or configuration switch.
Grand-catalog owns the later catalog disposition; fresh-session and owner gates
remain separate from this comparison.

The result is **PASS-SCOPED / PROPOSE-MCPORTER**. All 42 timed task operations
succeeded. Tool discovery returned identical names and input schemas in all 11
cold/warm comparisons. The numeric status results matched exactly in 8 of 10
warm pairs; two pairs differed only in the live `observations` count. The server
is shared with active sessions, so these count differences do not establish a
client defect or full result equivalence. The retained evidence includes both
differences rather than treating them as exact parity.

## Verified sources and quality

- [Inspector 2.10.1 release](https://github.com/modelcontextprotocol/inspector/releases/tag/2.10.1),
  published 2026-10-08, resolves to
  `0d2bc1d91ce177ea8d497ee3efe91bcc59e40a1c`. Its release notes describe the patch
  restoring npm's default Inspector bin after adding `mcpdo`.
- The [pinned mcpdo guide](https://github.com/modelcontextprotocol/inspector/blob/0d2bc1d91ce177ea8d497ee3efe91bcc59e40a1c/clients/mcpdo/README.md)
  explicitly labels the bundled, implicit-daemon connection CLI experimental.
  The [pinned package](https://github.com/modelcontextprotocol/inspector/blob/0d2bc1d91ce177ea8d497ee3efe91bcc59e40a1c/package.json)
  supplies the `mcpdo` and Inspector binaries. The installed client reports
  `2.10.1`; host Node `v24.21.0` satisfies its `>=22.19.0` requirement.
- [Inspector's tag-pin CI](https://github.com/modelcontextprotocol/inspector/actions/runs/37730418763)
  succeeded. Its build job passed validation including fast tests, the two
  externalized-dependency guards, cross-client smokes, and Storybook tests. Its
  coverage job passed the per-file 90% gate on all four dimensions. These are
  reproduced upstream CI observations, not a local rerun of the source suite.
  The separate [SDK Watch run](https://github.com/modelcontextprotocol/inspector/actions/runs/37734413577)
  failed its Claude review/staging analysis job; not every workflow at the pin
  passed.
- The installed mcporter package and native `--version` agree on `0.14.2`.
  [Its v0.14.2 source](https://github.com/openclaw/mcporter/tree/aa0f55f9bffcde9d2070c86145f37d4dd3525f6c)
  resolves through annotated tag `a031fc437df4bfb3b1c4362d479026a5045805bc` to
  commit `aa0f55f9bffcde9d2070c86145f37d4dd3525f6c`.
  [Tag-pin CI](https://github.com/openclaw/mcporter/actions/runs/36819995965)
  passed Ubuntu, Node 26, Windows, and macOS jobs. The inspected Ubuntu job
  passed `pnpm check`, docs build, and coverage tests.
  [Release asset verification](https://github.com/openclaw/mcporter/actions/runs/36905665366)
  also succeeded. The existing host package was not replaced.

Exact source URLs, CI job/step observations, npm integrity, and installation
receipts are retained in [receipt.json](receipt.json).

## Install, native check, and executed inverse

The vendor guide supports `npm install -g @modelcontextprotocol/inspector`.
The trial applied that mechanism at the exact pin with a lane-owned npm prefix:

```sh
npm install --global --prefix <lane-prefix>/install @modelcontextprotocol/inspector@2.10.1 --no-audit --no-fund
<lane-prefix>/install/bin/mcpdo --help
npm uninstall --global --prefix <lane-prefix>/install @modelcontextprotocol/inspector --no-audit --no-fund
```

All three returned zero. After the inverse, the package directory and all three
Inspector bin aliases were verified absent. The exact npm tarball was then
reinstalled with npm for the comparison and root's separate conformance checks.
The retained 1,541,080-byte archive has SHA-256
`1786803aaf058445aaf647973e848f7a5c17391b99bd6e17ddb01b63d4ae7c96`;
its npm SHA-1 and SHA-512 integrity also match the registry metadata.

Both tools ran in private native daemon namespaces. Inspector used
`MCP_INSPECTOR_DAEMON_DIR=<lane-prefix>/d` and
`MCP_STORAGE_DIR=<lane-prefix>/s`; mcporter used
`MCPORTER_DAEMON_DIR=<lane-prefix>/m`. The
[Inspector daemon paths](https://github.com/modelcontextprotocol/inspector/blob/0d2bc1d91ce177ea8d497ee3efe91bcc59e40a1c/clients/mcpdo/src/daemon/paths.ts)
and [mcporter daemon paths](https://github.com/openclaw/mcporter/blob/aa0f55f9bffcde9d2070c86145f37d4dd3525f6c/src/daemon/paths.ts)
at their pins support these isolation variables. Each private daemon was stopped
after the trial, and native stopped status was verified. User client configs,
skill registrations, production daemons, and credential values were untouched.

## Same-task results

Both clients targeted the actual host's unauthenticated ai-memory MCP endpoint,
`http://127.0.0.1:29374/mcp`, under the same alias `trial-ai-memory`.
No test server, protocol adapter, or alternative MCP implementation was written.
Equivalent vendor config fixtures contained the same endpoint; their native
formats differ. mcporter additionally set `imports: []` and
`lifecycle: "keep-alive"`; mcpdo retains the named connection by default.
Inspector negotiated its native `legacy` era. This comparison does not assert
identical client initialization capabilities or a protocol-version matrix.

The requests were `tools/list` and `tools/call` of `memory_status` with `{}`.
Both discovered the same 23 tools and the same optional nullable
`project`/`workspace` schema, with no required input properties. The status
request reads numeric counters only. Inspector preserved the MCP content
envelope; mcporter's `--output json` decoded its JSON text. The measurement
script compares the decoded counts and canonical tool-name/input-schema digest,
not the clients' formatting wrappers.

Ten warm pairs per task alternated client order. One cold discovery per client
preceded them; mcpdo's cold cost includes its explicit connect command. Wall time
includes common process launch, stdout drain, and PSS sampling overhead. These
are measured end-to-end native CLI latencies on this active host, not estimates
of transport-only latency.

| Measured quantity | Inspector mcpdo 2.10.1 | mcporter 0.14.2 |
|---|---:|---:|
| Cold discovery, one sample | 1,072.5 ms | 842.6 ms |
| Warm tools/list, median of 10 | 302.9 ms | 464.1 ms |
| Warm memory_status, median of 10 | 402.9 ms | 504.9 ms |
| tools/list command + daemon peak PSS, median | 124.1 MiB | 118.7 MiB |
| memory_status command + daemon peak PSS, median | 126.8 MiB | 114.6 MiB |
| Persistent daemon PSS, before warm tasks | 66.9 MiB | 58.2 MiB |
| Persistent daemon PSS, after warm tasks | 80.4 MiB | 72.7 MiB |

PSS comes from `/proc/<pid>/smaps_rollup`, sampled at a nominal 25 ms period.
The transient metric includes that client's process tree and its private daemon.
Persistent samples include the daemon process tree only. The existing shared
HTTP server is excluded from both arms: these are incremental session costs,
not total host or server memory. Both daemon PIDs remained stable through the
timed run. Inspector was approximately 35% faster for warm discovery and 20%
faster for the warm status call, with the higher memory costs shown above.

[measurements.json](measurements.json) retains individual timings, PSS counts,
safe counters, schema digests, cleanup checks, and all 20 normalized comparison
verdicts. [measure.py](measure.py) is the replayable measurement orchestration.
[attempts.json](attempts.json) records the excluded instrumentation failure and
native argument-placement mistakes with their corrections.

## Retention, routing, and adoption boundaries

The separate [persistence.json](persistence.json) records native named-connection
metadata across both task types and a repeated task pair. It does not inspect
HTTP session tokens or equate a stable process with a stable HTTP session.
mcpdo retained one named connection with unchanged `connectedAt`. mcporter
retained its discovery connection and added a second connection on the first
status call. Repeating both task types kept the same one-connection Inspector
set and the same two-connection mcporter set with unchanged generations. Both
private daemons were stopped afterward. These connection observations are
separate from the timing table, and do not prove HTTP session-token identity.

The npm package ships upstream's
[mcpdo routing skill](https://github.com/modelcontextprotocol/inspector/blob/0d2bc1d91ce177ea8d497ee3efe91bcc59e40a1c/skills/mcpdo/SKILL.md).
Its lane-installed bytes have SHA-256
`a79042f432014263f84d1e5c16a3a6704c76f3cf6368534fe2d133684a4f4e16`.
The parent owns the independent unnamed fresh-session execution proof. Source
presence, a named CLI invocation, or a proposed user-config diff is not that
proof. No host routing skill was registered and no candidate is ADOPT-NOW here.

The two read-only HTTP tasks do not establish parity for OAuth, stdio process
retention, remote network behavior, resources, prompts, generated CLIs/types,
MCP Apps, modern protocol features, or Inspector's web/TUI clients. The retained
default recommendation weighs the measured latency/memory tradeoff and vendor
status within that boundary; it is not a claim that either tool is best for
every MCP task. apify/mcpc is outside the comparison.

## Artifact handling and replay

Public captures replace the personal home prefix with `/home/example` and
replace opaque native connection identifiers with stable `connection-NN`
labels. [redaction.json](redaction.json) distinguishes the SHA-256 of each raw
capture retained in the private lane prefix from its committed redacted bytes.
Raw CLI-output SHA-256 fields in the timing rows refer to the captured output,
not to the redacted JSON artifact. Package archive integrity is unaffected.

The public scripts accept `TRIAL_ROOT` and optional `MCPORTER_BIN`; defaults use
the current user's lane prefix and the native command on PATH. Copy the two
checked-in config fixtures to that prefix. Set the three private namespace
variables as described above and run the scripts under `nice -n 10 ionice -c2
-n7 timeout 600 python3`. Each script checks the namespace variables before
starting or stopping a daemon. The retained measured run used the recorded
version pins and equivalent native configuration fixtures; the public changes
only parameterize paths and redact identifiers.
