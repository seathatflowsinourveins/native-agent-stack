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
The shared install-plan has no ExecStart text today; fixwave-defects owns its
concurrent edit, so that mirror awaits the named handoff rather than overwriting
it. No experimental anchored-query flag is added to the ns2604 proposal.

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
