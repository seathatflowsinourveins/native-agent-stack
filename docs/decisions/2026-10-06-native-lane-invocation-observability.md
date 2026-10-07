# 2026-10-06: native lane invocation observability

The overlap-token lane selects native Codex OTel result events for the live
tool stream, and native completed-item records for census attribution and
deduplication. This supports a finished foundation for north-star engineering
and research. The command center owns host application and read-back.

## Evidence and alternatives

Installed Codex 0.160.1 supports per-run dotted TOML overrides. Upstream pin
[openai/codex rust-v0.160.1, d27764b8](https://github.com/openai/codex/tree/d27764b82f7118f674371e6d6e76271d9d606edb)
defines the settings in `codex-rs/core/config.schema.json`,
`codex-rs/config/src/types.rs:599` and `core/src/config/otel.rs:9`.
Native conversation identity is emitted by
[`events/shared.rs:14`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/otel/src/events/shared.rs#L14),
and names/status/duration by
[`tool_result.rs:54`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/otel/src/tool_result.rs#L54).

**Functional execution, 2026-10-06:** one authorized throwaway native
`codex exec`, default service tier, gpt-6.1-sol/ultra, completed in 12.055 s
with exit 0. It requested one code-mode wrapper containing one context-mode
`ctx_search` and one RTK-leading shell command. Native completed items confirm
one completed MCP call and one shell completion, exit 0. Loki returned HTTP
200 with exactly one named nested MCP event, one `exec_command` event and one
outer `exec` event, all successful. The private retained CLI JSONL SHA256 is
`0459bef50ff9a9d90c3c98ff3de8c55b8fc13e457f7e1908d0c1c1a4652af908`.
This is prompted transport qualification, not organic adoption or token savings.

The nested event retains namespace `mcp__context_mode`, server `context-mode`
and tool `ctx_search`. The outer wrapper is counted separately as a tool result,
never as another MCP call. A native-record scanner remains valid for the census;
a new periodic fallback scanner for nested visibility is unnecessary on this
evidence. SDK notifications alone would not cover the existing native CLI fleet.
Parsing JavaScript references is rejected because references are not calls.

The installed Collector privacy pipeline was read back by SHA256
`abca05750aaddf9826a38686b9ea6717673e343d43b4afe7518d75ac3a7c9a26`.
It strips arguments and replaces log bodies before storage. Client max_bytes=0
suppresses tool-output bytes; it does not suppress arguments on local transport.
The probe used nonsensitive arguments. No host or client settings were changed.

## Supported backend integration

One dashboard, `Lanes`, joins the existing Grafana file provisioning path and
datasource UIDs. Its selectable windows are 1 h and 24 h. Native Codex
conversation IDs and Claude session IDs identify rows; current lane resource
labels are not qualified as a reliable mapping. Tool/server result rows,
started user turns, shell RTK-prefix share, Claude Skill calls and request
token categories stay separate. Codex request token fields come from
[`session_telemetry.rs:1106`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/otel/src/events/session_telemetry.rs#L1106).
Cache counters are not added to inclusive input totals.

hcom exposes status through its own JSON command, not through the native
client tool event stream. A bounded bridge reads selected fields from
`hcom list --json --name gore` and reuses the existing publisher's loopback
Loki JSON format. Native source:
[aannoo/hcom v0.7.27, 2c5f343b, list.rs:355](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/src/commands/list.rs#L355).
The bridge retains identity/name/status/age/unread count and recognized tool
context; it omits descriptions, directories, paths, arguments and arbitrary
context text. The existing persistent oneshot/timer carries the bridge; it
does not create a transient unit or an agent runner.

The format reuses
[Loki v3.7.8 JSON push](https://github.com/grafana/loki/blob/v3.7.8/docs/sources/reference/loki-http-api.md),
and the dashboard uses
[Grafana v13.2.3 file provisioning](https://github.com/grafana/grafana/tree/v13.2.3/docs/sources/administration/provisioning)
and native table transformations. The CC must seed the private canonical-root
registry at the data root before claiming full roster coverage. A read-only
bridge check using the fixed native census returned all sixteen registered
roots; fifteen had current hcom status and one remained unknown. Registry data
and native transcript identities are private and are not committed.

## Acceptance limits and overturn conditions

Three representative live LogQL checks returned HTTP 200: per-conversation
tool results (47 series), native input usage (51), and observed MCP results
plus dated tool inventory (162). Those observations prove query execution,
not deployed Grafana rendering. Zero inventory rows mean no visible results;
organic non-use requires confirmed exposure and full-window coverage. The
inventory is selected native MCP metadata from this Codex session; connector
app discovery and other lane/client exposure are unqualified. Refresh it at
the tools-wave MCP read-back. Plugin aliases stay separate.

Open gates: GPT review/CC ACK, host apply and dashboard read-back; canonical
root mapping and descendant-family joins; live Codex skill-read and Claude
RTK-first instrumentation; completed-turn counts; exposure/freshness gates for
zero tools; matching organic before/after windows. A rendered dashboard or
source-only draft closes none of the twelve native-bar token rows.

The status table shows latest recorded status with observation time and native
status age; it does not mask old active records automatically. An old recorded
active state is historical, not current process liveness. This was an independent
critic finding and is retained as a freshness gate rather than relabeled live.

Overturn native OTel if a later controlled native run confirms completed nested
calls but loses their named events after transport/flush/retention qualification,
or if an upstream harness demonstrates a more accurate lower-cost native route.
Then use the completed-item reader with the demonstrated gap recorded. Replace
the hcom bridge when maintained upstream exports the required status directly.
An organic run, a chosen owner regression, or a superior upstream-harness A/B
can reopen any exclusion; no exclusion is made here.

Completeness critic: identity coverage and exposure differ from nonzero event
transport. Preserve absent roster rows as unknown, native client cohorts and
request/result distinctions, separate Skill/read contracts and cache subsets,
and the interrupted full-suite comparison. These remain follow-up gates.

## Combined monitoring steps 6, 7 and 8 — 2026-10-06

The clock addition uses the existing native clock-offset-check output and
Collector0.162 journald/OTTL/Loki export. Sanitized rows retain only bounded
state, reason, presence and numeric offset/bound/reference age; raw journal,
resource, scope and body metadata are removed. Counts and clock log rows remain
separate. One Lanes panel shows historical signed offsets/error bounds and a
fresh latest state/offset availability. Missing/error offsets are not zero.
The3-minute freshness contract covers three expected60-second timer samples;
it is distinct from the native1,200-second reference-age warning. WARN compares
the50ms error bound; CRIT compares100ms absolute offset. A UI-only-1 marker
means No data and is never an emitted state or native offset. Latest failed
samples suppress preceding offsets as current while preserving history.
Pinned Loki3.7.8 last_over_time/filter/vector/on-label behavior and Grafana13.2.3
axis/value-mapping forms follow the native documentation/source. Config, query,
browser and threshold-override read-backs remain unverified until deployment.

Source correction: the first clock extraction statements used bare YAML
scalars containing a regex colon followed by whitespace. A config data read
raised a YAML ScannerError; the clock processor's statements now use quoted
YAML scalars, preserving the OTTL expressions. This correction changes source
serialization only. Native Collector/schema/query/browser checks remain pending.

The Lanes dashboard uses uid `cc-lanes`, the existing file provider, and native
conversation/session identities with the hcom name lookup. An `ecosystem_lane`
environment label is not authoritative identity: a historical sampled label
belonged to another native thread. Descendant joins remain pending. Window
selection is 1 h or 24 h. The refreshed 160-tool inventory is this one Codex
session's exposure and excludes connector-app discovery.

The collector change preserves native bounded source, hook, connection,
compaction and skill dimensions before metric aggregation. It keeps prompt,
argument and result bodies private. The gateway health route is model-free;
no gateway settings or database are read. Prometheus start-timestamp ingestion
needs the deployed `created-timestamp-zero-ingestion` flag and a newly born
single-turn series read-back. Until then its token panel says lower bound.
The generic backend renderer already enables both start timestamps and anchored
queries; that is not the observed ns2604 unit and is not a host apply receipt.

Native `systemctl --user show ns2604-prometheus.service -p ExecStart` confirmed
the deployed unit has the OTLP receiver and no created-timestamp flag. The exact
argument-preserving proposed drop-in is
`observability/collector/ns2604-prometheus-start-timestamps.conf.example`.
The install-plan now mirrors that exact argument-preserving startup proposal
under its Prometheus row. The co-op's ownership ruling keeps these monitoring
hunks in this PR; #723 retains its model/MinerU/QMD/code-index contracts and
rows. Landing order is #771, then #723, then this PR. Rebase after #723, keeping
its lines and handing any incompatible same-line requirement to the co-op.
No experimental anchored-query flag is added to the ns2604 proposal.

Correction: OmniRoute v3.8.51 already ships an optional GenAI OTLP trace sink
(`diegosouzapw/OmniRoute@v3.8.51`, `open-sse/services/routing/otel.ts:1–32`).
The earlier assertion that no exporter exists until v3.9 is withdrawn. Enabling
its sink environment and restart belong to CC. Gateway traces are not token
or MCP invocations. No host application is authorized by this source change.

Counter reconciliation receipts cover native Codex and Claude separately. Raw
registered Codex BEFORE [13:55Z,18:01Z):2,208 commands,2,069 context-mode calls,
45 ai-memory,8 chrome-devtools,1 Serena and1 promptfoo. These are not organic
counts. All-turn task naming, referenced co-op blocks, standing guidance,
first-turn exclusion and effective role exposure are required for organic use.
Thirty-two named roles have unknown effective grants. No zero-use, exclusion,
readiness or merged cross-client total is claimed.

Cheap critic fixes add native errors/hooks/connections, host CPU load and memory,
collector stream headroom and explicit pending ownership. GPU export remains with
the vllm-embed owner, unit failures with alerting/lm-qmd, client limit headroom and
gateway environment with CC, and the newest-complete GitHub feed with
github-ci-finalize (step12). Clock source pipeline is distinct from invocation
counts. Live panel query/browser read-back waits for CC ACK and host apply.

## J775 renderer corrections and accountable gates

The source-only J775 response to findings P2-5, P2-6, P2-7 and P3-8 keeps
deployment and acceptance pending. No local tests, render/build, validator,
model run or native scan was executed during paper operation. The parent
integrator owns regenerated dashboard copies, the registry-last commit and
one new head's CI. Local fixtures are source edits awaiting that CI, not
upstream Grafana or Loki acceptance.

All NativeStack2604 Prometheus panels that query `codex_turn_token_usage_sum`
receive a lower-bound title and description in `ns2604_dashboards.retarget`,
including the ecosystem per-minute/range panels and foundation token panel.
The already-qualified Lanes token panel follows the same renderer rule.
Qualification remains until the deployed start-timestamp flag and newly born
single-turn reconciliation pass; a range-edge extrapolation warning does not
replace this gate. No anchored-query flag is proposed for this host.

HCOM emits complete JSON rows, including explicit null age/unread fields for
a missing registered root. The table extracts each row, sorts native log Time
ascending, and groups identity using Grafana's `last` reducer for every field.
Every selected field therefore belongs to the same newest row, including its
nulls. It does not select each field's last non-null historical value.
Native sources fetched through `gh api --cache 1h`, exit 0, on 2026-10-06:
[Grafana v13.2.3 sortBy.ts:16](https://github.com/grafana/grafana/blob/v13.2.3/packages/grafana-data/src/transformations/transformers/sortBy.ts#L16)
defines `options.sort`, and
[fieldReducer.ts:622](https://github.com/grafana/grafana/blob/v13.2.3/packages/grafana-data/src/transformations/fieldReducer.ts#L622)
returns the final array element for `last`, including null. `lastNotNull` at
line 627 searches backwards and is intentionally excluded here. A source-level
sentinel was rejected because native nulls can be preserved directly.
Read-back must show present → missing-root and valid-number → unknown
transitions: latest status unknown, age/unread UNKNOWN, and a newer observation
time, without old numeric cells. The renderer contract fixtures and native
emitter transition fixtures do not replace this browser acceptance.

The RTK share zero-fills its numerator only from identities with a positive
observed classified-shell denominator, using LogQL `or on (identity)` and
`0 * denominator`. An all-non-RTK classified cohort has a measured zero share;
no classified denominator retains no value/UNKNOWN. A global `vector(0)` is
rejected because it invents an identity without classified observation.
Read-back must compare a non-RTK-only identity, a mixed identity and an identity
with no classified events in the same selected window. Native LogQL source:
[Loki v3.7.8 metric_queries.md](https://github.com/grafana/loki/blob/v3.7.8/docs/sources/query/metric_queries.md).

Folded storage finding 2 remains explicitly deferred to **CC as read-back
owner**. Reason: source-only work during paper operation cannot establish the
deployed retention limits, storage deletions or oldest retained sample age.
The completion gate requires sanitized, timestamped native read-back of:

- **Size-retention COUNT:** native `prometheus_tsdb_size_retentions_total`,
  whose counter counts block deletions due to the maximum-byte limit in
  [Prometheus v3.15.0 tsdb/db.go:478](https://github.com/prometheus/prometheus/blob/v3.15.0/tsdb/db.go#L478)
  (primary source read, exit 0). Record the counter and effective size/time
  retention limits; absence is UNKNOWN and the count is not invocation usage.
- **Oldest-sample AGE:** qualify the native source for the oldest retained
  sample timestamp, record that timestamp and observation time, and calculate
  their difference in seconds. A head-only timestamp is insufficient for a
  claim about all retained samples. Keep AGE UNKNOWN until this source is
  verified, including restart/persisted-block coverage and its relationship to
  the effective retention limits.

The pending-source panel names both COUNT and AGE, owner, deferral reason and
gate. A stream-count ceiling does not establish bounded retained TSDB storage.
Remaining folded work keeps accountable deferrals: unit failures are owned by
alerting/lm-qmd, pending integration and native unit-state read-back; GPU export
by vllm-embed, pending exporter sample and panel read-back; clock by CC's
CLOCK-PANEL worker, pending its separate source and numeric panel read-back;
SDK task attribution and the optional gateway OTLP sink by CC, pending native
identity qualification and environment/restart application. Client limit
headroom is owned by CC pending a native provider-status contract. No clock
panel is claimed implemented by this worker.

Overturn this renderer choice if native Grafana read-back loses a newest row's
nulls or a native LogQL read-back fails the observed-denominator zero/unknown
contract. Retain failed conditions rather than relabeling them accepted.

## J775b: complete provisioning qualification and reversible withdrawal

The command center's review retains file provisioning under Grafana v13.2.3.
Anonymous Viewer has no dashboard-administration path in the shipped profile.
Rollback therefore restores the previous `grafana-dashboards/lanes.json`.
Withdrawal removes only that file, temporarily changes `disableDeletion` to
false on `nativestack2604-token-layer`, and restarts Grafana in a permitted slot.
After the anonymous dashboard endpoint returns 404 for `cc-lanes`, restore
`disableDeletion: true` and restart/read back the provider. Preserve
`token-layer.json`, the provider, unrelated dashboards and the private registry.
The alternative of dashboard deletion through the UI is unavailable in this
profile. Native source: [Grafana v13.2.3 file provisioning](https://github.com/grafana/grafana/blob/v13.2.3/docs/sources/administration/provisioning/index.md).

Codex token qualification now lives in the installed standalone
`observability_config.py` and is shared with the maintained NativeStack2604
renderer. Both the direct template-copy publisher and generated dashboard path
qualify every panel using `codex_turn_token_usage_sum`, including token-layer
panels 6, 21 and 22. Qualifying only dashboards reached by the former renderer
missed that direct publisher. Keep the lower-bound titles and descriptions
until deployed start timestamps and a newly born single-turn reconciliation
pass; a source render alone cannot lift this gate.

Local integration evidence: all 12 `tests.test_ns2604_dashboards` tests pass,
including actual provisioning enumeration of every dashboard asset, all four
Codex-token dashboard UIDs, and standalone-script portability. `check_plan.py`
passes after the import loader avoids generated bytecode in configuration
assets. Both checks ran at nice 19. These are locally authored integration
checks, not upstream tests or deployed acceptance. No configuration was applied.
The README separately classifies all six retained 13000 references and requires
a compatible emitter checkout while its timer is enabled.

## Amendment (2026-10-07): one Prometheus startup carrier at landing

The co-op's A13 option B, confirmed by command-center item
`task-ns2604-coop-20261007T115959Z`, makes this PR compatible with A27's landed
contract at the named landing base `1f65867315b12138e09add6e443f42ad5dcd2274`.
This records compatibility, not a new feature selection or a host action.
The current startup carrier is the rendered `ns2604-prometheus.service`, built
from the plan row's complete `enable_features` list. Both
`created-timestamp-zero-ingestion` and `promql-extended-range-selectors`, the
rendered-unit reference, activation owner, native service-health checks and
main's notes remain intact. Source:
[A27 renderer at the named base](https://github.com/seathatflowsinourveins/native-agent-stack/blob/1f65867315b12138e09add6e443f42ad5dcd2274/evidence/artifacts/new-wsl-install-plan-20261002/config/observability_config.py#L175).

The earlier `startup_proposal` and its example are dated, superseded records.
Their original argument text and the 2026-10-06 native read-back observation
remain unchanged. The proposal has no apply gate, and both example `ExecStart`
lines are commented beneath an explicit DO NOT APPLY notice. Its remaining
read-back gate now refers to the rendered unit. An aligned, current drop-in
was the alternative; A13 rejected it because it would create a second startup
definition to keep synchronized with the authoritative template.

One recorded difference remains visible to the activation owner: the earlier
live `ExecStart` included `--web.enable-otlp-receiver`, whereas
[main's rendered-unit template](https://github.com/seathatflowsinourveins/native-agent-stack/blob/1f65867315b12138e09add6e443f42ad5dcd2274/evidence/artifacts/new-wsl-install-plan-20261002/config/ns2604-prometheus.service.example#L15)
omits it. No flag is restored by this amendment. In A13 the co-op reported a
read-only native API observation at approximately 11:52Z on 2026-10-07: the flag
was on and `prometheus_http_requests_total` for `/api/v1/otlp/v1/metrics` showed
0 requests over 22.07 hours of uptime. The command center separately reported
0 requests over 22.19 hours at 11:59:45Z, with the collector/native scrape jobs
UP and no known writer. These are attributed reports, not probes by this lane
or proof that a future writer cannot exist. The plan's collector metrics use
its Prometheus exporter and scrape jobs rather than this OTLP endpoint:
[collector exporter/pipelines](https://github.com/seathatflowsinourveins/native-agent-stack/blob/1f65867315b12138e09add6e443f42ad5dcd2274/evidence/artifacts/new-wsl-install-plan-20261002/config/otel.yaml#L270)
and [native scrape jobs](https://github.com/seathatflowsinourveins/native-agent-stack/blob/1f65867315b12138e09add6e443f42ad5dcd2274/evidence/artifacts/new-wsl-install-plan-20261002/config/prometheus.yaml#L17).

Activation remains a separate command-center host-window step, with read-back
of both features and the scrape jobs, and an inverse. Created-timestamp
negotiation and newly born single-turn reconciliation follow activation; they
are not landing gates. Lower-bound token qualifications remain until that
acceptance passes. Native evidence of an OTLP writer is a compatibility issue
for the activation owner, not permission to reactivate the superseded drop-in.
