# Claude usage: native transition events and ledger values

Use the official Prometheus Python client's textfile serializer and atomic
writer, feeding upstream node_exporter, and extend the existing Lanes dashboard
builder. Keep acquisition with the CC's fenced, bounded 15-minute one-word
probe. The lane builds and tests an adapter from synthetic captures only.
Deployment and live event coverage remain the CC's read-back after landing.

## SOTA sources

| Source and immutable pin | Contract adopted |
| --- | --- |
| [prometheus/node_exporter v1.12.1](https://github.com/prometheus/node_exporter/blob/6044da783597cc3b57aef7580ddcdcff58a4ee99/README.md#textfile-collector), `6044da783597cc3b57aef7580ddcdcff58a4ee99`, README Textfile Collector and `collector/textfile.go` | Batch metrics from final `*.prom` files; no exposition sample timestamps |
| [prometheus/client_python v0.26.0](https://github.com/prometheus/client_python/blob/9b6b971f903e7a08f88da5a95048b7a2a28f55a5/prometheus_client/exposition.py#L475), `9b6b971f903e7a08f88da5a95048b7a2a28f55a5`, `write_to_textfile` | Native serialization and same-filesystem atomic publication; isolated CollectorRegistry |
| [anthropics/claude-agent-sdk-python v0.2.165](https://github.com/anthropics/claude-agent-sdk-python/blob/f7529348747235da34af3ed202251228ff31db08/src/claude_agent_sdk/_internal/message_parser.py#L356), `f7529348747235da34af3ed202251228ff31db08`, parser and `types.py` RateLimitInfo | Raw `rate_limit_info`, optional camelCase fields, fractional utilization and epoch seconds; transitions rather than snapshots |
| [anthropics/claude-code v2.1.296](https://github.com/anthropics/claude-code/tree/2301018b1f61073c501a8e7a4813ef48c239163b), `2301018b1f61073c501a8e7a4813ef48c239163b`; [official headless docs](https://code.claude.com/docs/en/headless) and installed `--help` | Print/stream-json interface, no tools, dontAsk, local setting sources and one turn; version/help read only, no probe |
| [grafana/grafana v13.2.3](https://github.com/grafana/grafana/blob/6193dc03311b631b9727b560d24369e683dc396e/docs/sources/visualizations/panels-visualizations/visualizations/bar-gauge/index.md), `6193dc03311b631b9727b560d24369e683dc396e`; `packages/grafana-data/src/valueFormats/categories.ts` and `dateTimeFormatters.ts` | Native bar gauge, `percentunit` fraction scale, explicit 0..1 range, millisecond datetime formatting |
| [prometheus/prometheus v3.15.0](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/configuration/unit_testing_rules.md), `5241a27fe3c6983549fccc32f6e65917408c63cd`, native `promtool test rules` | Execute the actual generated panel expressions against synthetic series; prove rejected utilization is 1.0 and stale values disappear |

The official PyPI universal wheel's SHA-256 is
`fa93d06737aa02bacd05794768508bb97d2fbee28cb3bca04eaae92f0ca953d6`.
The script uses a PEP 723 version pin; CI installs that wheel with hash checking.
No additional listening service, credential-dependent collector or custom
Prometheus writer is introduced.

Private source references are `coordination/cc-native-practice-20261009/w5_guard.py`
(source SHA-256 `ce5a71d94df2dbc71b6585260804d637c13047fc5a3a15fe2db8c6e9ac9b8ef5`)
and `coordination/api-actions-20261008/harness/common.py`
(source SHA-256 `dc612c7342428ce44dc0feffbe5fc3849ac7f61641ef929f87158813e982c73a`), especially `totals`,
`settle_unknown` and `void`. Only source and allowlisted ledger schema/amounts
were inspected; their credential runtime was never imported or executed. The
adapter follows original-debit settlement attribution and exposes unknown
settlements as an uncertain subset. Pre-key rows need the CC-confirmed legacy
alias to enter a key's column. Provider-console snapshots do not add charges.
Settlement credits can be negative: the values-only ledger read exposed a
signed reconciliation adjustment, and a fail-before regression verifies its
effect on the key's accounted charges. Debit reservations stay nonnegative.

## Comparison and correction

The existing builder, upstream node_exporter and official Python client supply
the presentation and publication primitives. A tiny loopback HTTP exporter
would add a service lifecycle without improving this 15-minute batch source.
[dolead/claude-prometheus-exporter](https://github.com/dolead/claude-prometheus-exporter/tree/8a8ce092ea9f9c9e4c30da79872fb2599da5df96)
uses an Admin API credential and identity labels; it does not supply the Max
subscription event contract. [steipete/CodexBar](https://github.com/steipete/CodexBar/tree/cd24c380e10075f6f1141cdc4fa139b16133621d)
has credential/PTY acquisition routes outside this lane's authorized fixture
window. Neither was installed or run. The adapter implements only the missing
allowlisted event-to-metric and ledger-to-metric seams.

The reference guard defaults missing utilization to zero. That fallback is
incorrect for these panels: rejection must render 1.0, while absence of an
allowed window remains unknown. Native events may omit either window; a new
transition without utilization cannot refresh the last numeric observation.
Unscoped rejection deliberately shows conservative exhaustion for both windows
and carries an assumption metric. It is not a measurement that both windows
are full. API charges, pending reservations, uncertain subsets, provider
snapshots and subscription headroom remain distinct.

Replace this adapter's acquisition seam if upstream ships a maintained,
credential-free Max event collector that satisfies the same opaque-label,
bounded-probe and unknown/stale contracts. Compare the same allowed, warning,
rejected, missing and malformed fixtures before adoption. Do not substitute
statusline percentages or API-equivalent cost for Max fraction utilization.

## Reproduced evidence and limits

| Claim | Evidence class | Reproduction |
| --- | --- | --- |
| Upstream event, publication and Grafana contracts at the pins above | `source_review` | Public pinned source reads; installed Claude version/help only |
| Exhausted/rejected limits serialize as 1.0; missing allowed utilization never becomes zero; older events preserve freshness | `synthetic` | `tests.test_claude_usage_metrics` through native Prometheus serialization/parser |
| Metrics/state contain opaque indexes and numbers only; no identity, prompt, response or raw alias | `synthetic` | Poisoned stream/ledger fixture and output/state assertions |
| Charges, reservations, original-debit attribution, uncertain subsets, snapshots, legacy attribution and persistent indexes | `synthetic` | Offline ledger fixtures, including malformed financial rows suppressing partial totals |
| Generated row placement, stable panel IDs, units, instant queries, staleness and OmniRoute links | `local_integration` | Builder tests and `observability/ns2604_dashboards.py --check` |
| Real dashboard queries return exhausted-account 1.0, reset milliseconds and API-edge 1.0, while excluding stale data | `synthetic` | Native Prometheus v3.15.0 `promtool test rules`, driven by the builder's expressions |
| Adapter accounting matches the existing producer for the authorized ledger projection | `local_integration` | Values-only projection of 621 rows and three columns; exact numeric comparison to the producer's accounting without importing its runtime |

The initial 21 tests failed before implementation (absent adapter and row).
After implementation those 21 contracts passed using the pinned client in an
isolated interpreter; the added signed-credit contract then failed before its
fix. A malformed optional-child rejection regression also failed before its fix.
The native query test uses the official release archive, SHA-256
`2a542df32eac02ee17b9d844fb2aa1de00dafa5476579ba8a3ba862e9d572ea0`, verified
against GitHub's release-asset digest before extracting only `promtool`.
This is fixture evidence, not a live subscription probe,
Grafana rendering session, credential read, installation or provider billing
reconciliation. Main's externally assigned shard-6 failure from the #913 pin is
tracked by its owner; this slice does not change that pin.

Final focused validation: 41 tests passed (24 feature contracts plus 17 existing
dashboard contracts), including the optional native Prometheus query test.
FULL `python3 scripts/validate.py` passed for 70 components, 11,302 hashed files,
4 profiles and 239 receipts. `actionlint -color` (kjanat v1.17.0) and
`zizmor --no-config --no-ignores --persona regular --strict-collection .`
(v1.30.1) exited 0. The normal dashboard renderer produced the committed copy.
