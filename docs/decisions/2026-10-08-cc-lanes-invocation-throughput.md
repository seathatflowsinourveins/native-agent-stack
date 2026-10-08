# Claude throughput and per-tool invocation panels — 2026-10-08

CC assignment 9 after PAPER-WINDOW-CLOSED adds four panels to the existing `cc-lanes` dashboard, beside its lane-rate/cost views. This serves foundation readiness before intensive north-star research. It reuses the installed native clients, Collector, Loki and Grafana; no additional analytics backend, service installation or host publication is selected.

## Primary sources and selection

| Source | Pin and relevant implementation |
| --- | --- |
| Claude Code | Installed 2.1.294; [release tag](https://github.com/anthropics/claude-code/tree/v2.1.294) `71cdddec623889d38af14b7a489670a03186f659`; installed binary build identifies separate internal revision `8f033c6ebe3d82a87f502e199307f38f5d55ccca`. [Official monitoring schema](https://code.claude.com/docs/en/monitoring-usage) agrees with bounded installed-emitter inspection. |
| Codex | Installed 0.161.0, `rust-v0.161.0` / `979011409de0a60b52f179721948e65531d26144`; [tool_result.rs](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/otel/src/tool_result.rs) and [official OpenAI telemetry documentation](https://developers.openai.com/codex/config-advanced#observability-and-telemetry). |
| Loki | Installed 3.7.8 / `09e6ce2ff1bdc19763a10265b870c86f51c98655`; [range aggregation](https://grafana.com/docs/loki/latest/query/metric_queries/), [native API](https://grafana.com/docs/loki/latest/reference/loki-http-api/), pinned `pkg/logql/evaluator.go` and `syntax/syntax.y` for label matching, top-k and set union. |
| Grafana | Installed 13.2.3 / source tag `6193dc03311b631b9727b560d24369e683dc396e`; packaged running build `90ffed056f0884267356c12a0eeb72a022af53f1` is distinct. Pinned `packages/grafana-data/src/transformations/transformers/{labelsToFields,merge,organize}.ts` and `pkg/api/api.go`. |
| Chrome | Installed 154.0.8037.97; supported [headless screenshot operation](https://developer.chrome.com/docs/chromium/headless) inspected the isolated native Grafana candidate. |

The coordinator invoked the installed ECC `search-first` workflow and bounded primary-source readers. Existing family/count panels were the baseline; the missing capabilities were named per-tool rates and weighted request throughput. Extending native LogQL and Grafana JSON closes those gaps. A second observability stack or custom telemetry recorder would duplicate the installed exporters. Replace this choice if native schema changes or a supported upstream query produces a materially more accurate measure on the same records.

## Metric contract

Claude effective throughput is `1000 * sum(output_tokens) / sum(duration_ms)` over qualifying native `api_request` records in the selected 1h/24h count window. Positive durations and nonnegative output tokens define the same population for both sums. It remains grouped by native session, query source, derived actor and speed. The label explicitly says **includes prefill**. It is neither generation-only speed nor an average of individual request ratios. Absent speed becomes `normal (unset)` without removing requests. The Collector derives actor from request/resource context; actor is not a documented native Claude event attribute.

Both invocation panels count only completed result events: Claude `tool_result`, Codex `codex.tool_result`. Successful and failed results count; denied calls, permission decisions and connection events do not. Interrupted calls can be absent. Codex namespace and leaf name remain verbatim. Code-mode wrappers have distinct series and must not be added to nested-call rates as additional underlying invocations.

Claude's native MCP identity is JSON `tool_parameters.mcp_server_name` and `tool_parameters.mcp_tool_name`, gated by `OTEL_LOG_TOOL_DETAILS=1` for user-configured servers. `mcp_server_scope` is a configuration scope. The existing Collector already extracts and retains the safe names while deleting raw parameters; its configuration and native Claude template need no change. The dedicated MCP panel retains unnamed calls as `UNKNOWN`.

Session names use the latest valid native hcom lookup observation within the count window, through Loki's many-to-one label join. Empty identity/name or nonpositive timestamps cannot mask real throughput with zero. The set-union fallback keeps unmatched native session IDs. No static session-ID/name list is introduced. The table uses native Columns, Merge and Organize transforms, retaining identifying fields until merging and then hiding the duplicate correlation alias.

## Returned checks and boundaries

[The sanitized receipt](../../evidence/receipts/cc-lanes-invocation-throughput-20261008.json) retains native query outcomes, discriminating controls, browser observation and representative MCP server probes. Native Loki parser/query calls and Grafana's native datasource query endpoint returned successful nonempty data for all four panels. At the frozen 13:51:59.766Z window, the final observed vectors had 11/22/4/16 series. Controls with the relevant event absent, or the erroneous `speed="normal"` filter, returned zero rows and failed the same rows-present condition. No model request or broker operation was used for these checks.

The isolated Grafana 13.2.3 candidate rendered 19 current throughput rows in Chrome, with four actor classes, retained `normal (unset)`, a single table and `tok/s` units. This later live UI window is separate from the frozen 16-series API observation. Private session IDs and screenshots remain outside the checkout. The unchanged local dashboard integration suite passed 12 tests after regenerating the artifact; the earlier stale-render failure is retained. These are local integration checks, not an upstream test suite or a new provider run.

Actual hcom lookup records were absent in both tested 1h/24h host windows. Therefore live positive name enrichment and mixed named/unnamed frame rendering remain **unqualified**; the observed fallback is accepted. The latest recorded mapping is historical within the window, not freshness or process liveness. Equal conflicting maximum timestamps can select an encounter-dependent name; timestamp uniqueness is not established. CC host publication must qualify the mapping source and its positive read-back. No full organic window, exposure/savings claim, fast-tier A/B decision or all-tool execution coverage is claimed.

The eight MCP server probes passed one representative read-only operation each. The denominator is eight servers, not 126 schemas. ai-memory's global query establishes server health; implicit current-project routing is excluded after a cross-session scope error. QMD's metadata probe passes with no vector index. Graph coverage gaps remain reported. These limitations belong to their component owners.

## Corrections and completeness critic

Pinned Grafana source disproved the initial plan to join independent log/name frames directly: per-frame grouping did not establish a global unique lookup. Native LogQL enrichment plus the set fallback replaces that plan. The critic also identified the boolean-mask edge case: a zero timestamp could suppress a genuine fallback; positive-timestamp/name/identity guards now precede aggregation. Native UI inspection found that Merge names the value field `Value #A`, so the unit override now follows explicit Organize naming. A missing request produces no row, not an invented UNKNOWN row.

The independent source critic checked native schema distinctions, bool/set matching, latest-name ties, empty/stale lookup windows, wrapper counting and table frame completeness. The resolved findings and unqualified positive-name branch feed the next observability sweep. Landings and publication remain on the CC/5f cue; window closure did not authorize either.

