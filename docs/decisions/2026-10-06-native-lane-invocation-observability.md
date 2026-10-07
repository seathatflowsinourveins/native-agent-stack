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

## Amendment (2026-10-07): clock serialization correction

The following correction is appended under the landing read's F3 requirement;
its wording is retained verbatim rather than inserted into an earlier section.

Source correction: the first clock extraction statements used bare YAML
scalars containing a regex colon followed by whitespace. A config data read
raised a YAML ScannerError; the clock processor's statements now use quoted
YAML scalars, preserving the OTTL expressions. This correction changes source
serialization only. Native Collector/schema/query/browser checks remain pending.

## Amendment (2026-10-07): landed privacy contracts and invoke-column sources

This records the F1 compatibility changes and their limits at the reviewed
head `41d1249f319b5d1f77480b8065be9ea6093401a5`; it does not change the recorded
native observations or declare host activation. The landing read's first
suggestion to restore the dotted metric dimensions was superseded by the
co-op's execution of main's tests. Main's contract is authoritative for this
compatibility repair; green CI alone is not an acceptance of a changed policy.

Compared with f2cab814, the ordinary and plural-hook aggregation and retention
lists in both collector copies drop `skill.name`, `agent.name`, `plugin.name`,
`mcp_server.name`, and `mcp_tool.name`. Main at `53f90edc` requires the four
registry/agent removals through `tests/test_observability_tool_names.py:39,42`
and `:161-168` (introduced at a464d2884); the aggregate and keep lists must
agree and those categories must not be metric datapoint labels. `plugin.name`
is not literally in those two test lists: its removal was additional alignment
with main's native metric/log separation, not an individually mandated
assertion. The native bounded `server`, `tool`, `tool_name`, `skill`, status and
plural-hook lifecycle fields remain. Validated dotted names remain on logs.

The SDK-receipt deletion statement at `collector.yaml:128` and plan
`config/otel.yaml:131` retains the original 15 exclusions and adds 18
source/hook/count/timing/connection fields. This is required by main's
`test_derived_keys_cannot_be_supplied_and_receipts_carry_no_names`,
`tests/test_observability_tool_names.py:142-152`: the receipt exclusion plus
derived-key clearing must cover the complete shared log-allowlist tail and
call_id. Registry-shaped values alone do not prove native-client provenance.
The new fields therefore remain available to native logs, while a file-based
SDK receipt cannot forge hook executions or registry names through them.

The #775-added native writer expectation changes three agent-labelled streams
to two session streams: session-a's workflow-subagent and general-purpose
streams collapse when agent.name is dropped; session-b remains a different
writer. `tests/test_observability_writer_identity.py:515-527` asserts two
points without an agent-name label, Claude totals 60/14, Codex totals
2000/4000 and startup-phase counts 4/4. The latter totals are unchanged from
main at `1f658673:487,490,493`; no landed total assertion is relaxed.

The table below uses the focused read's definition: each column has a
configured surviving carrier. It does not assert that every client emits every
field, that recorded prefixes prove actual rewritten execution, that a skill
activation proves successful organic execution, or that invocation rows join
one-to-one to token usage. Unlabelled SDK/exec activity and unavailable native
identity remain unknown. These LogQL/PromQL examples are source queries, not
new live measurements. G means `observability/collector/collector.yaml` at
41d1249f; its plan copy carries the same keys (log keeper P:301 versus G:298,
metric keepers P:359-360 versus G:356-357). NativeStack2604 metric names below
have no ecosystem_ prefix; the workstation exporter adds that namespace.

| Column | Surviving native carrier and key; keeper | Query reading it | Move and privacy scope |
| --- | --- | --- | --- |
| lane | resource ecosystem.lane, normalized ecosystem_lane; G:241 logs,309 metrics,454 exporter | `sum by (ecosystem_lane) (increase(codex_mcp_call_total[1h]))` | No lost lane dimension; only supplied/valid lane tags are attributable. Missing SDK tags are unknown. |
| client | tool_result/codex.tool_result resource service.name and derived client; G:159,193-194,241,298 | `sum by (client) (count_over_time({service_name=~"claude-code|codex-app-server|codex_exec|codex_cli_rs"} | event_name=~"tool_result|codex.tool_result" [1h]))` | Log source before and after; client was already excluded from metric attributes by main's derived-key contract. |
| MCP server | result logs mcp_server.name -> mcp_server_name; G:142,174,199,298; server is permitted in native metrics G:343,356 but emission is not proven | `sum by (client,mcp_server_name) (count_over_time({service_name=~"claude-code|codex-app-server|codex_exec|codex_cli_rs"} | event_name=~"tool_result|codex.tool_result" | mcp_server_name!="" [1h]))` | Dotted metric identity moves to validated logs. The retained native MCP metric read-back has no server label, so metric attribution by server is unproven; a keep-list alone is not an emitting source. Main registry list:39 and metric exclusion:167-168 do not remove the log carrier. |
| tool | result logs tool_name/tool_namespace and mcp_tool.name -> mcp_tool_name; G:143,175,200,298; native tool/tool_name remains G:343,356 | `sum by (tool_namespace,tool_name,mcp_tool_name) (count_over_time({service_name=~"claude-code|codex-app-server|codex_exec|codex_cli_rs"} | event_name=~"tool_result|codex.tool_result" [1h]))` | Dotted MCP tool metric name moves to validated logs; ordinary native tool labels remain. Same main registry exclusion applies only to metrics. |
| skill | native Claude skill_activated skill.name -> skill_name, guarded G:201 and retained298; metric skill is permitted343,356, with no proven named emitting source | `sum by (skill_name,invocation_trigger) (count_over_time({service_name="claude-code"} | event_name="skill_activated" | skill_name!="" [1h]))` | Dotted metric identity moves to activation logs; model-typed Skill input is not exported (README:532). Codex aggregate injection/shadow counters have no proven named successful-use identity; neither a skill metric nor an identity is manufactured from the permitted key. |
| hook runs | Codex codex.hooks.run/duration with bounded hook_name,source,status,handler_type,execution_mode; G:316-325,346,357; Claude hook_execution_complete num_hooks/outcomes G:281-286,298 | `sum by (ecosystem_lane,hook_name,status) (increase(codex_hooks_run_total[1h]))`; `sum by (ecosystem_lane,hook_event) (sum_over_time({service_name="claude-code"} | event_name="hook_execution_complete" | unwrap num_hooks | __error__="" [1h]))` | No native hook-count dimension removed. Lifecycle is not script/repository identity; a configuration-derived join remains separate and ambiguous matches unknown. |
| shell through rtk | recorded tool-result shell_rtk boolean, derived G:145-146/177-178, bounded212 and kept298 | `sum by (service_name,shell_rtk) (count_over_time({service_name=~"claude-code|codex-app-server|codex_exec|codex_cli_rs"} | event_name=~"tool_result|codex.tool_result" | shell_rtk=~"true|false" [1h]))` | No metric move. This is submitted-parameter/prefix classification, not proof of actual Claude hook rewrites or every shell form; actual execution requires the vendor audit/native-record join. |
| tokens | configured codex.sse_event/response.completed input_token_count/output_token_count/cached_token_count and Claude api_request input/output/cache fields; G:298,343,356; event queries lanes_dashboard.py:124-135 | `sum by (conversation_id) (sum_over_time({service_name=~"codex-app-server|codex_exec|codex_cli_rs"} | event_name="codex.sse_event" | event_kind="response.completed" | unwrap input_token_count | __error__="" [1h]))`; Claude uses api_request/input_tokens | Configured token categories/model labels survive; this table does not re-measure the native field schema. Cache categories keep their client's counter contract; no native/cache/tool-estimate summation and no invented per-invocation token join. |

COLUMNS: all derivable

That conclusion is configured-carrier coverage only, as in the focused read.
Named successful Codex skill use, per-repository hook-script identity and actual
Claude rewrite share are not established by these surviving fields and remain
explicitly unmeasured. Those limits existed independently of the five dotted
metric removals. Organic acceptance still needs the qualified native oracle.
The Lanes MCP queries at lanes_dashboard.py:119-122,169 use retained Loki names;
the complete INVOKE-RATES report/panels remain separately prepared, not claimed
deployed by this source table.

The source-table critic corrected two allowlist-to-emission promotions in this
amendment: retained `server` and `skill` keys are permissions, not evidence that
the provider supplies them. The retained MCP metric read-back
`native-readback-20261007T014848Z.json` (sha256
`c463e768ac6d85e52a2eaddd82e069b1ce8fe4f3d285458cca38495181556e2f`)
has no server label; the prepared invoke design already records generic-tool
ambiguity. Server attribution uses validated logs. Named Claude skill
activation also uses logs; Codex aggregate skill counters do not establish
named successful skill use. No new live measurement is claimed by the queries.

HOOK-LABELS-2 patch ce50ed8c is a log-guard/allowlist patch, not a metric-list
patch. Read-only git apply --check at 41d1249f returned 0: these metric removals
did not make its context fail. Semantic composition is still required: that
patch introduces ten additional log keys without extending SDK exclusions.
A newly prepared follow-up must retain the current 33-key exclusion and clear
the new provenance keys from receipts, with forgery controls, rather than
resurrect the removed metric dimensions. No patch or host configuration was
applied during this check; CC owns the reviewed merged-base composition.

## Amendment (2026-10-07): run-metric privacy and isolated render acceptance

Finding F2 is repaired in configuration, with main's run-correlation test
restored byte-for-byte. The contract landed in #408 at
`ec8a48927c5d2536a57884f7f163c2d13770e7e2`,
`observability/collector/README.md:109-114`: metrics gain no run,
tool-invocation or cost labels. The task key therefore leaves the span resource
keeper, Prometheus exporter resource-label list and all four derived-metric
connector resource lists in both collector copies. A native OTTL guard on
every Prometheus metric export path also removes prohibited resource, scope
and datapoint dimensions before conversion and batching; an exporter cannot
restore the run key from another signal context. Task metadata remains on
logs, where the collector README's existing exact and whole-run LogQL filters
read `ecosystem_task_id`.

This removes per-task filtering of the newly derived response/phase metrics.
None of #775's provisioned dashboard queries selects `ecosystem_task_id`,
`ecosystem.task.id` or `task_id`; their lane/client/token queries keep their
sources. A caller requiring a per-task response or usage view must use a
supplied native log event, for example
`{service_name=~"codex-app-server|codex_exec|codex_cli_rs"} | ecosystem_task_id="<run>"`,
then select that event's kind, count or native usage field. Per-task phase
timing supplied only as a metric becomes unavailable; a missing phase log is
unknown, not re-created from the unlabelled series. No per-task metric label
or invented log-to-metric join is retained. The command center confirmed
that its fresh-session run-key queries already use log events only
(item task-ns2604-coop-20261007T132835Z).

Findings F6 and F7 remove an unnecessary agentsview version literal from the
new health-check comment. The canonical pin remains in the stack manifest;
the health route is unchanged and no new repin location is introduced.

Finding F8 preserves the landed isolated-render contract at
`tests/test_new_wsl_client_config.py:639-654`. The Grafana renderer and its
render-only checker can validate a private candidate without inspecting a
live user-unit installation. `grafana-check --installed-units` explicitly adds
the existing byte comparison for installation acceptance; all three acceptance
calls and their plan mirrors opt in. Placeholder and dashboard checks remain
unconditional, and the installed check rejects both absent and differing unit
bytes. The service and timer templates are unchanged from reviewed f2cab814.
This follows the existing repository render/install split in
`install.sh:722-725` and `observability/grand-dashboard/install.py:25-29`;
it neither installs nor activates a host unit.
