# Usage and cost (`observation-inference`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## usage-cost-monitoring

**Status:** default. **Default:** Native OpenTelemetry export (claude_code.* metrics and events) into the local collector, Prometheus, Loki and Grafana

- **Route:** Cost counters are estimates, never the bill; /usage, /cost and /stats for interactive checks
- **Alternatives, ranked:** 1. ccusage/ccusage (historical local counters); 2. kenn-io/agentsview (session archive); 3. Native /usage and the status line; 4. openlit/openlit, only if it closes a measured gap
- **Rejected:** openlit/openlit as the default (it closes no measured gap); agentops-ai/agentops; langfuse/mcp-server-langfuse; Treating estimated cost counters as the bill
- **Evidence:** monitoring-usage.md; cost-usage-O5, O7, O8; Observed: eight claude_code_* metric names in Prometheus with current samples
- **Notes:** Adjudicated mixed: native default, with ccusage and agentsview ranked first among alternatives; the refuter upheld it. Owed: a fixed-window same-task reconciliation of native counters against ccusage. Scope verified: not covered are Actions under WIF (read the Console organisation's usage), ultrareview cloud runs (usage credits) and `--bare` workers; under the subscription `claude_code_cost_usage` is API-list-price value, not spend; the series carry effort, query_source, model, type and ecosystem_lane. Integrity preconditions: the prompt and response content gates stay off (OTEL_LOG_ASSISTANT_RESPONSES explicitly false); because the template sets OTEL_LOG_TOOL_DETAILS=1, the collector's tool-name and privacy allowlists are required; backends stay on loopback and no log or event export with values goes into the public repository.
- **Overturn when:** A measured gap the native path cannot close (for example per-lane cost attribution the counters lack).
