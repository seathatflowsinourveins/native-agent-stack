# CC lane rates, estimated costs and gateway routing dimensions

CC080508Z rows 6/9 add source-only panels to the existing cc-lanes dashboard.
The landing rebase follows CC091807Z onto main e450e378.
The generated dashboard remains provisioned by the repository's existing native
Grafana recipe. Host publication and service restarts belong to the command center.

- Native tool-result and Codex API-attempt rates use the producer's ecosystem_lane
  label. Result records include failures; API attempts include retries. Neither is
  a completed-turn or MCP-only count.
- Claude estimated API cost uses its native USD counter. Codex estimated turn cost
  uses its native micro-USD counter, converted by 1,000,000. Each counter's rate or
  increase is calculated before aggregation across writers. Cost sources are kept
  separate; absent series are unknown. Codex enrichment is provider-conditional.
  Prometheus increase extrapolates window boundaries, so incomplete cost coverage
  is not a mathematically guaranteed lower bound or the subscription bill.
- Gateway routing rates use provider/model and vendor HTTP status/outcome. Native
  gateway spans lack lane/session parentage and do not set OTel span status. HTTP
  status zero means unknown. These rates are not assigned to client lanes.
- Main's #848 already supplies all five span_metrics dimensions, including
  omniroute.routing.status, omniroute.routing.outcome and gen_ai.provider.name.
  Its exact flow-form line and comment are retained; this PR has no collector
  YAML delta after the landing rebase.

Correction recorded at the landing rebase: the initially added connector-metric
exceptions were in transform/privacy, which runs in the direct OTLP metrics
pipeline. Gateway/Harbor connector output instead uses metrics/spans and only
transform/metric_export_privacy, whose run-label guard retains these dimensions.
No shipped producer is bound to sending traces.span.metrics.calls/duration as
direct OTLP metrics through transform/privacy. The ineffective exceptions and
their changes to the generic allowlist conditions were dropped. The original
synthetic test established dimension export, not causality from those exceptions.

The installed collector's validate command checks the source configuration.
The existing unittest fixture now sends synthetic routing spans through that
native collector and confirms equal groups add while provider/status/outcome
remain separate. These are local integration checks on synthetic input; they
do not establish deployed gateway export or complete usage. Deployment, exporter
activation, first samples and cost coverage remain host read-back boundaries.

Sources reviewed October 8, 2026:

- [Collector contrib v0.162.0 spanmetricsconnector](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.162.0/connector/spanmetricsconnector/README.md):
  supported additional dimensions, default metrics and native aggregation.
- [GenAI conventions 06ec68e722c45a7218e23ea1bc1339fe4e21ecae](https://github.com/open-telemetry/semantic-conventions-genai/blob/06ec68e722c45a7218e23ea1bc1339fe4e21ecae/docs/gen-ai/client-inference.md):
  gen_ai.provider.name; conventions remain Development.
- [OmniRoute c1e30b7676975feb298b49eff6ff58923c04b89e](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/services/routing/otel.ts#L193):
  vendor routing attributes and fresh event trace IDs. The routing fields are
  vendor extensions, not standardized GenAI attributes.
- [Codex 979011409de0a60b52f179721948e65531d26144](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/otel/src/events/session_telemetry.rs#L368):
  native conditional cost emission in micro-USD; [counter name](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/otel/src/metrics/names.rs#L42).
- [Claude Code official monitoring](https://code.claude.com/docs/en/monitoring-usage#cost-counter):
  native estimated cost and request accounting.
- [Prometheus rate/increase](https://prometheus.io/docs/prometheus/latest/querying/functions/#increase):
  reset handling, aggregation order and boundary extrapolation.
