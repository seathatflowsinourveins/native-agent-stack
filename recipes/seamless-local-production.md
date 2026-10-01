# Local daemon, messaging and memory qualification

This composition uses maintained native clients and supported upstream interfaces.
It is a bounded local qualification, not acceptance of every foundation layer or
either paper broker. Keep existing services and unrelated sessions intact.

## Selected sources

| Capability | Pin and source | Integration boundary |
|---|---|---|
| Codex daemon and session queues | [Codex 0.159.3](https://github.com/openai/codex/tree/rust-v0.159.3), commit `01fc69f4026735edfdf6789820549727a4867b11` | Complete native package; PID-backed daemon and native queue commands |
| Managed cross-client messaging | [Agent Relay 13.0.0](https://github.com/AgentWorkforce/relay/tree/v13.0.0), commit `d8e1a188ac8988be59b6fa447856516de292a195` | Installed local transport; automatic Codex PTY submission is held |
| Local message persistence | [Relaycast 8.14.0](https://github.com/AgentWorkforce/relaycast/tree/v8.14.0), commit `4d0c22afb8edb80841a5ad00d60b8de065f57570` | Documented native HTTP engine, isolated with Docker loopback port publishing |
| Memory integration | [Hindsight coding agents 0.8.0](https://github.com/vectorize-io/hindsight/tree/f9d9e2ab88bd237a81bba12f0ac5cf173aafd46c) | Official Codex/Claude installer and native hook review |
| Memory backend | [Hindsight 0.10.2](https://github.com/vectorize-io/hindsight/tree/v0.10.2) | Separate native embed profile, explicit project bank and local provider route |

Preserve Codex Sol/Ultra coordination, Sol/Max primary workers, explicit model
choices and Astra/Max escalation. Preserve Claude Opus/Max and Ultracode; leave
the global effort environment variable unset.

## Codex native lifecycle

Use the complete pinned package's executable, rather than an extracted binary:

```sh
rtk codex features enable daemon_auto_start
rtk codex app-server daemon bootstrap
rtk codex app-server daemon version
rtk codex queue --thread THREAD_UUID --message 'Owned acceptance nonce'
```

The [daemon README](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/app-server-daemon/README.md)
documents pinned updates and updater settings. Set `autoUpdateEnabled: false`
through its documented settings file while qualifying a pin. Avoid restarting
a shared daemon while other sessions use it. Independent embedded sessions also
watch persisted queues; a missing shared daemon does not establish missing
queue support.

## Private Relay project

Run from the owned private runtime directory. Use its project and credential
home, preserving provider `HOME`:

```sh
export AGENT_RELAY_PROJECT="$STACK_PRODUCTION_ROOT"
export AGENT_RELAY_HOME="$STACK_PRODUCTION_ROOT/state/relay-home"
export AGENT_RELAY_BROKER_PORT=0
export AGENT_RELAY_TELEMETRY_DISABLED=1
export RELAY_BASE_URL=http://127.0.0.1:8787
export RELAYCAST_BASE_URL=http://127.0.0.1:8787
rtk agent-relay workspace create local-stack --base-url "$RELAYCAST_BASE_URL"
rtk agent-relay node up --no-spawn --background --broker-name nas-production
rtk agent-relay node agent spawn codex --runtime pty --name codex-peer --cwd "$OWNED_WORKTREE"
rtk agent-relay node agent spawn 'claude --effort max' --runtime pty --name claude-peer --cwd "$OWNED_WORKTREE"
rtk agent-relay node agent list --status
rtk agent-relay node down
```

Do not reveal workspace keys. Native creation stores them in a 0600 credential
store. Explicit project selection prevents an enclosing project marker from
selecting another namespace. Keep the project's canonical `.agentworkforce/relay`
state: Relay 13's agent spawn and list commands do not expose `--state-dir` and
do not use the up command's state override. Attach and delivery controls have
different options; inspect their own installed help. Port zero is the upstream-supported atomic bind
path and avoids its unbounded preflight TCP probe.

The [native dotenv bootstrap](https://github.com/AgentWorkforce/relay/blob/v13.0.0/packages/cli/src/cli/bootstrap.ts#L53)
loads a credential-free `.env` from the invocation working directory. Persist
the namespace and local endpoint variables there, preserving provider `HOME`.
An owned [systemd user service](https://github.com/systemd/systemd-stable/blob/v255.4/man/systemd.service.xml)
can run the supported foreground `node up --no-spawn` command with that working
directory, the existing ecosystem launchers first in `PATH`, and
`Restart=on-failure`. This is a native configuration composition; Relay does
not supply a service installer. Release owned peers before a broker handoff.

Use `mode: wait` for ordinary peer messages. Check actual receiving turns and
native read/delivery receipts; sending establishes enqueue only. Peer messages
provide data and do not grant new authority. Codex PTY injection uses extra
config flags that exclude implicit shared-daemon attachment; do not force a
remote session that drops the injected Relay MCP configuration.

The 0.159.3 PTY trial exposed an unsubmitted ordinary DM in the Codex composer.
Relay marks delivery read after [echo verification](https://github.com/AgentWorkforce/relay/blob/v13.0.0/crates/broker/src/pty_worker.rs#L2200)
and [automatic acknowledgment](https://github.com/AgentWorkforce/relay/blob/v13.0.0/crates/broker/src/runtime/worker_events.rs#L797),
which can precede a receiving model turn. Preserve the successful peer exchange
and the later failure separately. Claude completed an idle authority-denial
probe, but that does not qualify Codex submission or reconnect behavior.

Do not silently select `--runtime native`: its selected
[`@ai-sdk/harness-codex` bridge](https://unpkg.com/@ai-sdk/harness-codex@1.0.40/dist/bridge/package.json)
bundles Codex 0.144.5, and its adapter disables web search when omitted. Ultra
inheritance is unverified. The promising native queue listener in
[PR 1864](https://github.com/AgentWorkforce/relay/pull/1864) is closed and unmerged.
Installed 13.0.0 and its current main provide no verified remedy meeting the
selected client-parity contract. Keep managed Codex push held.

The upstream deployment Docker image requires a public HTTPS authority and
rejects loopback. For local-only operation, compose the documented
[native engine installation](https://github.com/AgentWorkforce/relaycast/blob/v8.14.0/docs/self-hosting.md)
with the [official Node container pattern](https://github.com/nodejs/docker-node/blob/main/README.md)
and [Docker loopback publication](https://docs.docker.com/engine/network/port-publishing/).
This local composition is not an upstream turnkey Compose profile. Retain
engine database state across scoped restart; inspect published host addresses.

## Memory promotion

The supported integration installation is:

```sh
rtk npx --yes @vectorize-io/hindsight-coding-agents@0.8.0 install codex claude-code --server self-hosted --api-url http://127.0.0.1:3711
```

The installer merges owned hooks and MCP entries; installation does not prove
capture or trust. Review exact changed Codex definitions through native `/hooks`.
Qualify extraction, correction, isolation and independent recovery before
enabling capture in owned projects. Then check actual fresh-client capture and
recollection before broader promotion. This first qualification explicitly maps
the marker-free production and owned qualification folders to one bank, with
`resolveWorktrees: false` and `optInOnly: true`; it leaves the original marked
checkout unchanged. The incumbent's existing native allowlist drops every event
in those unmarked folders before spooling. Do not invent a project hook override:
Codex ignores project hook-state overrides and Claude merges hook sources.

For a later approved repository-wide cutover, use native marker admission and
explicit bank mapping to retain one authoritative session writer. Unrelated
projects remain inert to Hindsight; retain incumbent state for reference and
rollback. No global uninstall is needed. The current cold-start bound is
`seedLimit: 20` and `maxParallelRetains: 2`, supported by integration 0.8.0. Its
earlier default 300-commit seed produced an oversized operation and timeouts;
input estimates are not provider usage. Automatic knowledge-page readiness
remains a separate gate from successful capture and reflect retrieval.

Native capture and independent recollection passed for Codex headless and
shared-daemon sessions and for Claude Opus/Max. The backend also passed
extraction, correction, bank isolation, native API/PostgreSQL recovery and an
independent export/import. One earlier stored hourly knowledge-page cron completed
automatically with 5,045 content characters. A later live check found all five
pages stale after their latest refreshes failed. One native manual Conventions
refresh on the unchanged route failed at the same 300-second wall limit. Upstream
pauses automatic refresh after failure until an explicit refresh succeeds; page
freshness is held separately from retention and retrieval. The
[live recovery observation](../evidence/artifacts/hindsight-live-page-recovery-20261001/receipt.json)
retains the failed operation and the
[upstream failure-pause contract](https://github.com/vectorize-io/hindsight/pull/4618).
The
[backend and Claude evidence](../evidence/artifacts/hindsight-production-backend-20261001/README.md)
keeps these scopes distinct from the unresolved cold git seed.

The earlier timeout repair used `HINDSIGHT_EMBED_API_LLM_TIMEOUT`, which the
installed Embed 0.10.2 forwards unchanged and the API does not read. Correct
native profile keys are `HINDSIGHT_API_LLM_TIMEOUT` and the retain-specific
`HINDSIGHT_API_RETAIN_LLM_TIMEOUT`. Client `maxParallelRetains` does not bound
server extraction concurrency: the server separately reads
`HINDSIGHT_API_LLM_MAX_CONCURRENT` and
`HINDSIGHT_API_RETAIN_LLM_MAX_CONCURRENT`. The corrected bounded attempt uses
300-second global/retain deadlines and server concurrency 2/1, preserving the
existing Astra/Max provider route. The cold seed did not finish within the
25-minute qualification window. Supported cancellation marked its parent and
child operations cancelled; native API recovery then cleared the lingering task
while preserving the same PostgreSQL process and captured memories. The
[follow-up receipt](../evidence/artifacts/hindsight-native-cap-repair-20261001/receipt.json)
retains the failed conditions, cancellation and recovery separately.
The automatic cold bootstrap is held with `autoSeed: false` after the corrected
attempt remained unfinished for 25 minutes and the native worker reported a
stuck extraction backoff. Session retention, memory retrieval and existing page
crons stay enabled; no further cold trigger is issued until qualification passes.
A [fresh cross-family recall](../evidence/receipts/hindsight-cross-family-native-recall-20261001.json)
also returned Claude's synthetic 53-record fact to native Codex, with Claude-source
provenance. Its first reflect call timed out after 300 seconds; a narrower second
call succeeded. This proves the scoped retrieval and preserves its latency limit.
After preserving these proofs, supported native deletion removed exactly eight
owned disposable qualification documents. Independent reads confirmed all eight
absent and all six other documents preserved. The
[cleanup receipt](../evidence/artifacts/hindsight-native-qualification-cleanup-20261001/receipt.json)
records native background work separately: cached page prose and history are
not synchronously purged, and their cleanup is not claimed here.
API source is under
[`hindsight-api-slim`](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-api-slim/hindsight_api/config.py),
not the older directory used by the first draft's API citations.

For startup recovery, an owned systemd oneshot and timer invoke only the
supported `hindsight-embed -p PROFILE daemon start`. The
[native manager](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-embed/hindsight_embed/daemon_embed_manager.py#L712-L818)
checks health, locks profile startup and preserves foreign listeners. Healthy
repeat start and timer execution returned exit 0; native scoped recovery passed
separately. The helper uses `Type=oneshot`, `RemainAfterExit=no` and
`KillMode=process`: the native profile manager owns the detached backend and
its supported `daemon stop`. Default systemd cgroup cleanup terminated a fresh
isolated backend despite a successful start command. The corrected helper kept
the fresh backend healthy after completing. This intentional manager ownership
follows the [native detachment path](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-embed/hindsight_embed/daemon_embed_manager.py#L148)
and [systemd kill settings](https://github.com/systemd/systemd-stable/blob/v255.4/man/systemd.kill.xml#L63);
systemd generally discourages process mode when it owns daemon lifecycle.
The [helper receipt](../evidence/receipts/seamless-native-helper-recovery-20261001.json)
retains the failed baseline, corrected fresh and repeat starts, and native
fixture cleanup. The two-minute ensure interval is local configuration, not a new upstream
recovery guarantee or a physical-host reboot test.

Codex's supported per-server `mcp_servers.hindsight.tool_timeout_sec` is now 360,
above the integration's 330-second reflect tool deadline. The
[native connection manager](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/codex-mcp/src/connection_manager.rs#L1014)
still uses the smaller limit when a caller supplies its own deadline. Native
configuration parsing passed; no new model run was made after this setting,
so the earlier 300-second failure is retained rather than called repaired.

## Acceptance boundaries

Run unchanged upstream commands and preserve failed attempts. The actual Relay
default test run had one 5-second lifecycle timeout; a focused 30-second retry
passed in 8.81 seconds and does not make that default run green. Upstream
`smoke:prod` passed against the local engine, but covers action/message transport,
not model quality or automatic native-client delivery. The remaining selected
foundation, native capture, recovery and independently qualified paper-broker
gates must retain their own evidence.
