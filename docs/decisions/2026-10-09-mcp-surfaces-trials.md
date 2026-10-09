# MCP conformance and CLI overlap trial, 2026-10-09

**Propose mcporter 0.14.2 as the default for scripted MCP access on this host.**
On the same two read-only tasks and endpoint, it used less persistent and
command-plus-daemon PSS. Its single cold discovery was also faster. Inspector
2.10.1's experimental `mcpdo` improved warm latency, so that benefit remains
explicit in the comparison. This is a trial proposal for the later catalog
review; it does not change a client registration or promote either candidate.

The API-surface sweep supplied the discovery trigger. The verdict rests on the
vendor releases, installed clients, native harness results and measurements
below. [The evidence entrypoint](../../evidence/artifacts/mcp-surfaces-trials-20261009/README.md)
binds the complete records and their publication boundaries.

## Primary sources

- [modelcontextprotocol/conformance v0.1.16](https://github.com/modelcontextprotocol/conformance/tree/21a9a2febd7100d7c17ac1021ee7f2ed9f66a1e0):
  `README.md`, `src/index.ts`, `src/scenarios/index.ts`,
  `src/scenarios/client/initialize.ts`, `src/scenarios/server/lifecycle.ts`,
  `src/scenarios/server/client-helper.ts`, and `.github/workflows/ci.yml`.
  The [release-pin CI](https://github.com/modelcontextprotocol/conformance/actions/runs/23662264662)
  succeeded. The README labels the framework unstable.
- [modelcontextprotocol/inspector 2.10.1](https://github.com/modelcontextprotocol/inspector/tree/0d2bc1d91ce177ea8d497ee3efe91bcc59e40a1c):
  `clients/mcpdo/README.md` describes the experimental implicit-daemon CLI;
  `package.json` supplies the published binaries.
  [Release notes](https://github.com/modelcontextprotocol/inspector/releases/tag/2.10.1)
  describe its npm default-bin correction.
  [Release-pin build and coverage CI](https://github.com/modelcontextprotocol/inspector/actions/runs/37730418763)
  passed. Its separate SDK Watch analysis failed and is retained separately.
- [openclaw/mcporter v0.14.2](https://github.com/openclaw/mcporter/tree/aa0f55f9bffcde9d2070c86145f37d4dd3525f6c):
  `README.md` and the installed native CLI define the baseline access route.
  The retained receipt binds its private-daemon configuration and source checks.
  [Release-pin CI](https://github.com/openclaw/mcporter/actions/runs/36819995965)
  and [release verification](https://github.com/openclaw/mcporter/actions/runs/36905665366)
  passed. The installed version is 0.14.2.
- [Linux proc_pid_smaps(5)](https://man7.org/linux/man-pages/man5/proc_pid_smaps.5.html)
  defines PSS. Measurements read `Pss` from each owned process's
  `smaps_rollup`; they exclude the shared server.
- [Official Codex non-interactive documentation](https://developers.openai.com/codex/noninteractive)
  supplies the native fresh `codex exec --ephemeral --json` route. The actual
  installed 0.162.0 CLI was checked for its supported flags.

## Scoped conformance result

Conformance 0.1.16 was installed through npm at its exact version. Its official
49,842-byte package has SHA-256
`f936f57efb5372dba650ea1a6a2186d8fb61660357c8ab09954221da3f12f9af`.
The source build and `npm run check` passed, as did 29 tests in three native
test files. Native release-pin CI is retained as a separate upstream observation.
The source dev install reported dependency advisories; those counts are recorded
without claiming vulnerability triage or remediation.

At the supported `2025-11-25` filter, the actual ai-memory and hindsight HTTP
registrations passed initialization, ping and tools/list: six successful checks.
Only metadata was requested. Four of the role's six host servers use stdio in
the installed profile; this HTTP-only harness did not test them. The separately
proposed QMD HTTP endpoint was already documented unavailable by the sweep and
failed three probes. Those failures are an availability gap, with no QMD protocol
verdict.

Both native clients passed the client initialization leg. Their retained checks
record `protocolVersionSent=2025-11-25`, with one successful assertion and one
informational result per client. The first attempts had zero checks: mcporter
needed its ad hoc HTTP flag, and Inspector needed the positional URL before
options. Corrected native runs are retained alongside both setup failures.
The small shell adapter only places the conformance-supplied URL into Inspector's
native argument position; it implements no MCP messages.

This release accepts `2025-03-26`, `2025-06-18`, `2025-11-25`, `draft` and
`extension` as protocol filters. The retained v0.1.16
`server --scenario server-initialize --spec-version 2026-07-28` refusal
establishes only that invocation's boundary. It executes and scores neither
of the original frozen `--requirements 2026-07-28` legs below.

The [frozen acceptance declaration](../../evidence/artifacts/new-wsl-install-plan-20261002/config/mcp-conformance-accept.sh)
at repository revision `b7dfe638fc825a52ff4e7d1a9ccf2fde7de889fd` pins
`@modelcontextprotocol/conformance@0.2.0-alpha.11` (line 8), with separate client
and server invocations (lines 57 and 54). Its SHA-256 is
`1084b5a567c2c6df7b0443c6547661aad81f91882b56001708efb11c81f8987d`. The
[install-plan target selection](../../evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json)
at line 4998 declares the destination selectors without a default destination;
line 5000 fixes source commit `c321dd32035556e6769d3724a8ee97d87c3faaac`.
The package's primary npm metadata independently gives that same source commit.
The [pinned upstream requirements declaration](https://github.com/modelcontextprotocol/conformance/blob/c321dd32035556e6769d3724a8ee97d87c3faaac/README.md#conformance-requirements)
defines the revision-frozen requirement sets.

| Original frozen leg | Frozen runtime pin / requirement revision | Declared requirement invocation | Intended target | Disposition |
| --- | --- | --- | --- | --- |
| Client | `@modelcontextprotocol/conformance@0.2.0-alpha.11`, source `c321dd32035556e6769d3724a8ee97d87c3faaac`; requirements `2026-07-28` | `npx --offline --yes --ignore-scripts @modelcontextprotocol/conformance@0.2.0-alpha.11 client --command "$MCP_CONFORMANCE_CLIENT_COMMAND" --requirements 2026-07-28 "${extra[@]}"` | Owner-selected scenario-driven MCP client command or fixture inside the qualified isolated loopback namespace; selector `MCP_CONFORMANCE_CLIENT_COMMAND` is unbound for this frozen trial | `NOT_ESTABLISHED`: not run at the frozen revision |
| Server | `@modelcontextprotocol/conformance@0.2.0-alpha.11`, source `c321dd32035556e6769d3724a8ee97d87c3faaac`; requirements `2026-07-28` | `npx --offline --yes --ignore-scripts @modelcontextprotocol/conformance@0.2.0-alpha.11 server --url "$MCP_CONFORMANCE_SERVER_URL" --requirements 2026-07-28 "${extra[@]}"` | Owner-selected HTTP MCP server endpoint supplied by a qualified startup adapter or fixture inside the isolated loopback namespace; selector `MCP_CONFORMANCE_SERVER_URL` is unbound for this frozen trial | `NOT_ESTABLISHED`: not run at the frozen revision |

The optional `extra` arguments are only the explicitly supplied expected-failure
baseline declared by the helper. Neither destination selector was bound for a
frozen invocation in this trial. The helper's isolation/target guards remain
applicable; the 2025 live endpoints and simple client adapters do not qualify
a destination for either frozen leg.

`PASS_SCOPED_2025-11-25_TRIAL` maps only to the retained v0.1.16
initialization, ping and discovery observations. Those 2025 observations execute
neither the frozen client nor the frozen server requirement set. Both original
legs remain `NOT_ESTABLISHED`, so the original two-leg requirement is
**not satisfied** by the scoped verdict. No frozen harness was run for this
record correction.

## Same-task comparison

Both arms used `http://127.0.0.1:29374/mcp`, the same tool arguments and an
isolated configuration with imports disabled. Private daemon directories kept
production daemons outside the experiment. There were 42 successful timed
operations: one cold discovery per arm and ten alternating warm pairs for each
of tools/list and `memory_status {}`.

| Observation | Inspector 2.10.1 / mcpdo | mcporter 0.14.2 |
| --- | ---: | ---: |
| Cold tools/list, one observation | 1,072.530 ms | 842.592 ms |
| Warm tools/list, median of 10 | 302.928 ms | 464.061 ms |
| Warm memory_status, median of 10 | 402.880 ms | 504.859 ms |
| tools/list command plus private daemon, median peak PSS | 124.1 MiB | 118.7 MiB |
| memory_status command plus private daemon, median peak PSS | 126.8 MiB | 114.6 MiB |
| Persistent daemon PSS, before → after | 66.9 → 80.4 MiB | 58.2 → 72.7 MiB |

All eleven discovery comparisons had the same 23 tool names and input-schema
digest. Eighteen of twenty normalized warm pairs matched exactly. Two status
pairs differed only in the shared server's live observations counter. They are
retained as differences; full response equality is not claimed.

Native retention observations found one stable mcpdo connection and two stable
mcporter connections split by task type. They establish retained connections,
with HTTP session-token identity untested. Both private daemons were stopped
and their stopped state verified. These timing observations are a single-host
pilot; one cold pair does not establish a latency distribution.

The memory gate makes mcporter's measured PSS the stronger basis for the
proposed default. Inspector's 35% faster warm discovery and 20% faster warm
status call remain useful evidence for a later comparison. Its experimental
upstream status and unresolved native routing keep it at TRIAL. The overlap
verdict is `KEEP_MCPORTER_SCOPED`.

## Adoption stages and boundaries

| Stage | Conformance 0.1.16 | Inspector 2.10.1 |
| --- | --- | --- |
| Quality at the pin | Native build/check/29 cases and upstream CI retained; unstable warning and source dev advisory counts retained | Release-pin build/coverage/native smokes retained; experimental mcpdo and separate SDK Watch failure retained |
| Vendor install and native check | Exact npm prefix install; host initialize check passes | Exact vendor npm prefix install; native CLI check passes and paired operations pass |
| Executed inverse | Prefix npm uninstall returned 0 and binary absence verified; exact package reinstalled for the trial | Prefix npm uninstall returned 0 and all package/binary paths absent; exact archive reinstalled for the trial |
| Fresh unnamed reach | Not proven | Not proven |
| Measured memory | Owned command-tree PSS retained for native operations | Private daemon plus command PSS measured on the same tasks |
| Disposition | TRIAL, no promotion | TRIAL, proposed overlap disposition favors mcporter |

The vendor source dev install had a side effect: lefthook 2.1.4 uses `INIT_CWD`
and created a caller-worktree example config and Git hook. Its non-force vendor
uninstall returned 0; both generated files were verified absent. Reproduction
uses the vendor's `CI=1` skip behavior and runs npm ci from the source directory.
This correction is part of the inverse evidence.

The fresh native Codex child received an unnamed diagnostic task. Its completed
tool calls selected mcporter. The discovery shell found only mcporter despite
trial prefixes being placed on the launch PATH, and its diagnostic reported
`fetch failed` without an HTTP status. The 180-second observation bound ended
the child before successful task completion. Candidate reach, shell access and
fresh proof remain open. No model prose or reasoning is published as evidence.

No item is ADOPT-NOW. Native vendor routing, successful fresh-session proof,
the unresolved dated conformance boundary and owner decisions precede any new
default deployment. The two designated reads, required CI, pre-cue check and
CC cue precede a landing through 5f. Grand-catalog owns the catalog disposition.

The proposal would be overturned by a pinned Inspector release that passes
those gates and demonstrates a better memory/latency tradeoff on the same tasks
and a representative multi-server workload. A supported frozen conformance
revision and native stdio transport route would also expand this trial's scope.
