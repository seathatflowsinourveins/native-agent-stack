# Native invoke identity: IR-1 / IR-2

This source follows #775 and applies nothing. It serves foundation monitoring
for the north-star research. Use the stack's existing Collector/Grafana/Loki
provisioning; no additional collector, agent or model run is introduced.

## Where hook labels were lost

At installed Codex0.160.1, the completed counter and duration histogram receive
the same native five dimensions: hook_name, source, status, handler_type and
execution_mode. hook_name is a lifecycle enum, not a particular hook script.
[Emission at d27764b8 hook_runtime.rs:931](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/src/hook_runtime.rs#L931),
[tag construction:985](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/src/hook_runtime.rs#L985).

The older deployed Collector drops them. #775f2cab814 already sanitizes and
preserves them before aggregation and retention at config/otel.yaml318–360.
Its native-agent-telemetry name is an instrumentation-scope rename, not a
different emitter. Do not change ACKed #775 or duplicate its preservation fix.
This overlay adds only `event`, copied from the validated lifecycle hook_name
after privacy. Both counter and histogram retain the alias; unrelated streams
are unchanged. The actual observed histogram is
codex_hooks_run_duration_ms_milliseconds_bucket, with matching sum/count.

**These labels cannot attribute a hook to Headroom, context-mode or any other
repository.** A panel may show lifecycle events and typed sources. It must keep
script/repository identity unavailable until a native source or qualified
native-record join supplies it. An event alias is not that missing identity.
Headroom's standalone compress/retrieve mode is measured on MCP calls, separately
from provider-proxy readiness hooks.

## Claude session and actor

Native Claude2.1.292 skill/hook events in a bounded later sanitized-record sample
already retain log `session.id`. Loki exposes dotted fields as structured
metadata with underscores, so use session_id rather than expecting an index
label. This later observation does not rewrite the earlier CC six-hour result.
[Official standard attributes](https://code.claude.com/docs/en/monitoring-usage#standard-attributes),
[skill/hook contracts](https://code.claude.com/docs/en/monitoring-usage#skill-activated-event),
[Loki3.7.8 OTLP normalization](https://github.com/grafana/loki/blob/v3.7.8/docs/sources/shared/otel.md#format-considerations).
Claude's public release source is not its closed implementation; the inspected
help, release notes, official contracts and retained keys do not establish an
exact main/subagent actor for these event classes.

#775 derives actors for tools/API events, but leaves skill/hook actor absent.
The follower uses the existing conservative main_or_subagent category, or
workflow only with an actual retained workflow.run_id. It cannot manufacture
exact actor identity from neighboring timestamps. No additional session-id
retention is needed for the demonstrated log-record field. A resource-only
producer would require a separately verified copy-before-privacy path.

## Codex exec / SDK lane identity: CC window item

Codex's native resource builder includes the upstream EnvResourceDetector and
therefore supports OTEL_RESOURCE_ATTRIBUTES. The Collector already retains
ecosystem.lane. Missing lane attribution must be supplied at the actual owned
launch; never derive it from cwd, model or another lane's record.
[Codex provider.rs:363](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/otel/src/provider.rs#L363),
[locked SDK0.31.0](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/Cargo.lock#L11118),
[native environment detector](https://github.com/open-telemetry/opentelemetry-rust/blob/v0.31.0/opentelemetry-sdk/src/resource/env.rs#L9).

An explicit native TypeScript SDK environment replaces inherited process.env;
the CC must preserve and add identity in that effective map, not just in the
parent shell. Preserve native-provider and explicit21128 worker route contracts.
No launch/client environment is edited by this source.
[SDK exec.ts:176–198](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/sdk/typescript/src/exec.ts#L176).

## Apply and evidence boundary

After co-op delta read, green CI and exact-head CC ACK, the CC merges the overlay
through native repeated --config input **after** #775's source. It preserves
the complete ordinary OTLP log/metric pipeline lists, adding only the two named
processors. F09 and other pipeline inputs remain separate. A standalone overlay
cannot replace the base privacy configuration.
[Contrib0.162 transform configuration](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/processor/transformprocessor/README.md#advanced-config),
[native OTTL set](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/pkg/ottl/ottlfuncs/func_set.go#L34).

Read back hook_name,event on the native counter and histogram, equal to the
actual lifecycle event; check that non-hook dimensions and totals stay intact.
Query Claude skill/hooks by session_id and derived actor, labeling ambiguity.
Check each affected exec/SDK role's true lane resource keys and returned native
identity. Missing fields are unknown, not zero. Raw event totals remain separate
from qualified organic counts and requested smokes.

Record the activation time: adding event changes counter/histogram series
identity and supplies no historical backfill. Partial24-hour windows remain
unknown/incomplete, never measured zero. Keep the7-day p95 comparison disabled
until sufficient complete baseline history exists. Client activity, wired state
and qualified prompt provenance remain required before organic-use notices.

Rollback removes only this follower overlay and the reviewed launch additions,
restoring the prior ACKed configuration while preserving queues, cursors and
observations. It does not withdraw #775 or fabricate historical attribution.
