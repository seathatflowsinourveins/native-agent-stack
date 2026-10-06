# Repair native dashboard acceptance and retain honest event units (2026-10-06)

Decision: repair draft #775's seven Opus findings, then add the P0-3 native
token-event panels to that same draft. The command center applies reviewed
host changes after the co-op's GPT read and ACK; this work does not deploy,
change permissions, restart services or claim a live after measurement.

North-star action served: make fresh-session engineering and research tool use
observable while keeping native exported records, counters and deduplicated
census items in their original units. The detailed contracts and primary
sources are in [native-dashboard-data.md](../native-dashboard-data.md).

Acceptance now checks that the oneshot actually ran and independently reads
the three native Dagu histories without cache or Loki push. Empty native
history is valid; a failed read is rejected. The plan declares its installed
user units, waits for Grafana readiness, uses a long-lived source checkout and
documents full rollback. WSL2 loopback can reach the legacy distribution on
13000; this distribution's reviewed Grafana route remains 21301. The HTTP
status panel describes the Collector endpoint it actually checks.

Selected count owners: Loki's native log-entry queries for retained MCP and
RTK-prefix result records; Prometheus's native hook completion counter for
scrape-based lifecycle/status increases; Claude's native completion fields
for aggregate outcome sums. Sources: Loki v3.7.8
[`metric_queries.md`](https://github.com/grafana/loki/blob/v3.7.8/docs/sources/query/metric_queries.md),
Grafana v13.2.3
[`dashboard.go:127-141`](https://github.com/grafana/grafana/blob/6193dc03311b631b9727b560d24369e683dc396e/pkg/services/provisioning/dashboards/dashboard.go#L127),
Codex 0.160.1
[`names.rs:61-62`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/otel/src/metrics/names.rs#L61)
and [`hook_runtime.rs:931`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/src/hook_runtime.rs#L931),
plus Claude Code 2.1.291's current
[official hook-event schema](https://code.claude.com/docs/en/monitoring-usage#hook-execution-complete-event),
checked 2026-10-06. Dagu v2.18.2 native `history --help` and the existing
first-party emitter establish the supported history read; native CLI execution
and source review remain separate from the local synthetic acceptance tests.

RTK-prefix panels explicitly do not count total rewrites. Codex's
`codex_hooks_run_total` was found by read-only live query, but its existing
lifecycle labels are stripped before the coordinated #779 retention change.
Missing lifecycle displays as unknown. Hook-named logs are qualified partial
diagnostics; approval source is not an RTK identity. Claude completion records
can describe multiple matching hook commands, so sum the native outcome fields.
Missing data remains unobserved. Counter increases can miss first positive
samples or absent exports. No panel establishes per-processor RTK/ai-memory
firings, deduplicated fleet use, token savings or current readiness.

Alternatives rejected: counting every hook log as one firing contradicts the
native producer; labelling all RTK prefixes as rewrites conflates explicit
use and hook effects; filling empty panels with zero invents coverage;
accepting a service success state without independent Dagu history can pass
before any valid observation. Native logs and metric counters complement the
fixed before census and are never summed into it.

Focused repair checks returned 0: dashboard tests 8, grand-dashboard tests 23,
native-data tests 43, render --check, plan checker, shell syntax and diff
whitespace. Two newly authored acceptance regressions failed before the repair
and passed afterwards. A read-only emitter run returned native histories
4/1/0 with observed/observed/no-history states; five GPT and four Claude
backend queries returned success, including empty series. These are native
read-back or local integration evidence, not deployment or organic after proof.
The previous full-suite failures and static validator timeout are not passes;
final full validation and the exact base failure comparison remain deferred
outside the paper windows. Parent registration/commits follow those checks.

Completeness critic: source/log/metric/span separation, deduplication,
first-scrape loss and per-processor attribution remain distinct. The next
scoped sweep checks upstream telemetry-schema changes and supported native
notification capture. Overturn a selected query if actual post-apply read-back
misses its producer, duplicates observations, or a maintained native facility
supplies a more complete representation with the same information contract.
Every-lane after rows require the actual applied revision and a fresh matched
window. Coordinate the rebase with #723 and #779; the second landing takes
main's evidence registry and re-registers its own paths rather than hand-merging.
