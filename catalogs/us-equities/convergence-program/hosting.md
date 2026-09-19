# Hosting, orchestration and operations convergence

Keep one owner for each responsibility: Dagu for manual research workflow
dependencies/history, native Codex and Claude SDKs for model sessions, systemd
for Linux process supervision, explicit sandbox profiles for access, and native
observation/backup tools for telemetry and recovery. This review adds one actual
operational acceptance and keeps broader hosting claims gated.

The [machine-readable review](hosting.json) records two rounds, 12 candidate
repositories, three discovery inputs, 70 selected source files with immutable
commits and SHA-256, platform distinctions, native commands and adoption gates.
Discovery lists nominate projects; selected upstream source and observed behavior
determine decisions. This is a dated bounded review, not an exhaustive SOTA claim.
No package was installed or upgraded, and this lane made no model or broker call.

| Repository | Latest GitHub stable release checked September 19, 2026 | Decision and reason |
| --- | --- | --- |
| [Dagu](https://github.com/dagucloud/dagu) | 2.16.6 · September 14 | Retain. Existing manual pipeline/history is accepted; scheduler and distributed-worker adoption remain separate. |
| [DeerFlow](https://github.com/bytedance/deer-flow) | 2.0.0 · June 25 | Optional research harness. Current main declares 2.1.0-rc0 and has checkpoint configuration that requires process restart. |
| [OmniRoute](https://github.com/diegosouzapw/OmniRoute) | 3.8.50 · August 26 | Keep exact accepted routes. Current A2A history is best-effort; it does not establish durable live-task recovery. |
| [Codex](https://github.com/openai/codex) | 0.155.1 · September 18 | Retain native SDK/app-server lifecycle. The existing SDK 0.154.0 intentionally selects CLI 0.155.1. |
| [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) | 0.2.156 · September 18 | Retain explicit tools/settings and streaming interrupt support. GitHub release, Python package and bundled CLI versions are distinct. |
| [Temporal](https://github.com/temporalio/temporal) | 1.32.0 · September 11 | Defer until a concrete unmet durable-workflow requirement justifies its server/database/worker operations. |
| [bubblewrap](https://github.com/containers/bubblewrap) | 0.12.0 · August 26 | Retain reviewed Linux isolation profiles; command arguments determine the boundary. |
| [systemd](https://github.com/systemd/systemd) | 261.3 · September 10 | Adopt the scoped supervision recipe using existing distribution 255.4; no upgrade. |
| [Lima](https://github.com/lima-vm/lima) | 2.2.0 · July 21 | Optional Linux VM for a demonstrated macOS development need; no GPU or uptime parity claim. |
| [restic](https://github.com/restic/restic) | 0.19.1 · July 5 | Retain encrypted app-consistent recovery. Off-host destination and key-recovery acceptance remain open. |
| [process-compose](https://github.com/F1bonacc1/process-compose) | 1.122.0 · August 17 | Investigate only for a Mac development supervision need; avoid a second Linux workflow/process owner. |
| [OTel Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib) | 0.161.0 · September 15 | Retain observation and investigate delivery durability. Persisted file offsets do not by themselves protect downstream delivery. |

Release metadata is freshness evidence. Current main source review does not
prove a feature exists in the accepted installed version. Licenses and specific
test/implementation evidence are recorded per repository in the JSON; none of
the inspected upstream test definitions is represented as a newly passing test.

## What these rounds changed

Round one separated native research-session controls from workflow durability.
Dagu's server, scheduler and coordinator are distinct roles. DeerFlow already
embeds LangGraph and has additional application/checkpoint operations. OmniRoute
current source now writes optional SQLite task history, but catches persistence
errors while keeping live tasks in memory with a five-minute default TTL. These
findings favor clear boundaries over adding a second orchestration framework.

Round two compared host lifecycle and recovery primitives. The official Devbox
service-manager implementation provided a useful lead to process-compose;
its health probes and shutdown behavior are relevant to portable development,
but do not replace a sandbox or durable engine. The upstream OTel fault-tolerant
example explicitly combines file-offset storage with a persistent export queue.
Existing telemetry visibility should therefore be followed by a disposable
outage/replay test before claiming delivery resilience.

## Actual native addition

The [supervision recipe and direct output](../../../blueprints/us-equities/worker-supervision/README.md)
use a unique transient systemd user unit. A synthetic parent, child and grandchild
all ignored SIGTERM. At `RuntimeMaxSec=4s`, followed by `TimeoutStopSec=1s`, native
systemd reported `Result=timeout`, `ExecMainStatus=9` and CLI exit **1**. All three
original PID/starttime identities were absent and the cgroup was removed.

While active, native cgroup files reported `memory.max=67108864`, `pids.max=16`
and `cpu.max=25000 100000`. These prove configured limits; saturation and OOM
behavior were not tested. A separate explicitly launched fresh service exited
**0**. No persistent unit, timer, scheduler or existing service was changed.
An independent review reconciled the fixture, observer and retained evidence.

This is Linux/WSL2 process-lifecycle acceptance. It does not prove interrupted
application-state recovery, automatic retries, provider cancellation or stopped
billing. The recipe has not silently been applied to every existing worker.

## Next bounded gates

1. Connect a selected worker's native interrupt operation to its supervisor;
   retain partial results, terminal status and complete provider usage. Do not
   retry side-effecting work merely because its process disappeared.
2. Prove telemetry buffering and replay with a separate disposable collector,
   synthetic record IDs and an unavailable sink; inspect loss/duplication and
   disk bounds without changing the current observation service.
3. Select an authorized off-host backup destination, key custody and recovery
   objectives, then restore app-consistent state into a fresh isolated target.

macOS remains a development/client profile with source-reviewed alternatives.
The current WSL host is accepted only for the linked local operations. An
always-on Linux host needs its own native sign-in, boot/restart, resource,
network, telemetry and restore evidence; none was provisioned by this review.

For token efficiency, send workers a bounded immutable evidence packet and
role-scoped tools, preserve native caching and count failures/retries. Historical
packet reductions and exact provider usage are different measurements. This
hosting review does not measure a counterfactual whole-task saving.
