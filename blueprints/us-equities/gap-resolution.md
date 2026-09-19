# Gap-resolution results — September 19, 2026

This update closes bounded research, build, local-hosting and observability gaps. It does not
claim every catalog repository is installed, every source file was reviewed,
net provider-token savings were measured, or an autonomous trading system is
ready. The selected operating mode remains research/backtesting before Alpaca
paper execution.

| Area | Direct result | Evidence / native replay |
| --- | --- | --- |
| Star coverage | 337 public stars accounted for: 51 prior records, 268 README/license overviews and 18 selected-file reviews; 14 targeted candidates | [Complete decisions and exact review depth](../../catalogs/us-equities/star-audit.md) |
| DeerFlow → native Astra | One upstream ACP invocation completed in 31.027 seconds; 41,737 input, 24,320 cached input, 608 output tokens | [Commands and policy limits](deerflow/README.md), [receipt](deerflow/research-receipt.json) |
| LEAN dependency graph | Seven original advisory/package pairs resolved by an explicit local patch; native runtime audits report zero vulnerable packages in the launcher and source-integrated adapter | [Exact patches, locks, audits and commands](engine/resolution.md) |
| Deterministic replay | Unchanged bundled backtest: 3,943 data points, three simulated orders, six events, same original order-list hash | [Native result](engine/resolution-receipt.json) |
| Official Alpaca adapter | Original library and patched source-integration variant compiled; no broker initialization or order submitted | [Runtime entitlement boundary](engine/resolution.md#remaining-account-and-runtime-boundaries) |
| Native hosting | Dagu 2.16.6 completed the three-step research DAG; failure and cancellation states persisted after service restart; anonymous API 401 / authenticated 200 | [Commands, service and receipt](hosting/README.md) |
| Native client telemetry | Codex: 40,745 input including 14,080 cached; 95 output. Claude: 4 ordinary input, 24,283 cache creation, 43,726 cache read, 519 output | [Local monitoring and reconciliation](../../observability/README.md), [receipt](../../observability/receipt.json) |
| Local observation services | Collector 0.161.0 → Prometheus 3.14.0 / Loki 3.7.8 → Grafana 13.2.2; seven scrape targets up and six backend persistence checks passed | [Native backend commands and evidence](../../observability/backends/README.md) |
| Local alert delivery | Alertmanager 0.34.1 → ntfy 2.28.0: one firing and one resolved notification from an owned failure fixture | [Notification scope and receipt](../../observability/receipt.json); no external destination |
| SDK observation | Two actual native SDK tasks completed, totaling 40,187 + 40,583 = 80,770 input-plus-output tokens; native histogram remained unobserved, including a bounded flush attempt | [Worker observation boundary](workers/README.md#local-observation-and-native-usage) |
| Optional OmniRoute Astra | HTTP 200, response.completed, exact Astra route; completed request reported 81 input +55 output =136 tokens; earlier failed-attempt usage remains unknown | [Native SDK command and all attempts](routing/astra-receipt.json) |

The recorded upstream operations include `dagu start/history/stop`, `dotnet
build/restore/list package`, the unchanged LEAN launcher, and DeerFlow's
`build_invoke_acp_agent_tool(...).ainvoke`. Exact parameters, pins, actual outputs,
retained failures and limits are linked above. Historical receipts stay intact;
later proofs do not retroactively turn discovery checks into inference.

## Remaining requirements

| Requirement | Why it remains | Concrete next boundary |
| --- | --- | --- |
| Broker access and data rights | No paper credentials were configured for this acceptance; the official LEAN Alpaca runtime also validates a QuantConnect product entitlement | Authorized private Alpaca paper credentials, feed selection, and valid QuantConnect entitlement before that adapter is initialized |
| Strategy and risk specification | No universe, holding horizon, position/loss limits or validated strategy has been approved | A versioned research specification, held-out validation and explicit numeric risk parameters |
| Actual trading execution/recovery | No broker order writer, journal, reconciliation, kill switch or paper reconnect/duplicate-order acceptance has been deployed | Implement and accept those controls in paper mode before any standing trading service |
| ACP permission fidelity | ACP 1.12.0 calls its preset `read-only`, but native events show `workspaceWrite` with on-request approvals | Use the existing native SDK's strict read-only setting when that enforcement is required; do not infer safety from the ACP label |
| Full research application hosting | The DeerFlow proof invokes its embedded native tool; it does not run a durable planner, browser UI or scheduler | Select persistent storage, auth, sandbox/tool scope and operational requirements only when the full application is needed |
| Context Mode file-tool scope | Trusted native Context Mode calls work; one ephemeral SDK file-tool transport override still requires normal MCP approval | Use the accepted scoped native lane; reload/approve a new client registration through its normal flow |
| SDK native metric delivery | Completed task receipts and correlated logs exist, but the native SDK turn histogram was not observed | Use the separately scoped metadata-only receipt ingestion described in the monitoring receipt; the later helper change has offline checks, not a fresh inference run |
| Existing Desktop exporter activation | The accepted native tasks were fresh child processes; the already-running Desktop process was not restarted or hot-reloaded | Observe export from an intended fresh Desktop process/session before claiming that host is covered |
| Off-host operations | Local services, retained samples and notifications do not provide always-on hosting, replication, an off-host backup or external paging | Add only the required hosting/notification destination with separate authorization and acceptance |
| Provider-level token savings | Cached-input counters and smaller retrieved artifacts are different measurements | A paired, same-task/quality usage comparison including coordinator, failed calls and retries before asserting net savings |

The earlier reproducible QMD selection remains **6,398 → 490 tokens**, or
**5,908 fewer / 92.34% less selected text**, measured with `gpt-tokenizer 3.4.0`
`o200k_base`. That is not a provider billing reduction. The new DeerFlow task's
cached input is already part of its input total; reasoning output is already
part of output. Do not add either subset a second time.

The observability selection is separately **188,769 → 500 tokens** with the same
`gpt-tokenizer 3.4.0` / `o200k_base` encoding. It selects native token-category
information from a large retained metric artifact for one question; it is not
lossless telemetry compression, a provider-token comparison or maximum savings.
The two later SDK observation tasks are separate from the earlier three-turn
research aggregate and from the DeerFlow task; no whole-session total is implied.

## Persistence and future sessions

Native tools, local patches, public recipes and scoped project instructions are
saved. Dagu and the local observation services survive conversation changes while
the user service manager remains active; they do not keep Windows/WSL running.
Dagu schedules no work. Collector/storage/dashboard/rule evaluation itself uses
no model calls. The observation profile is one local metrics/log/alert path, with
no additional LLM trace platform or paid hosting. Accepted native
commands can run in this session. Existing Desktop tasks keep their current MCP
tool catalogs; newly registered tools use normal client discovery/reload. Other
projects require explicit scoped adoption, and future model tasks still need
fresh account-readiness checks.

The unchanged 337-public-star snapshot and the 144-repository core catalog are
complementary. The combined index has 451 identities, including 114 beyond stars:
an individual source disposition is not an installation decision. Candidates
such as Vibe-Trading, ai-trader and provider-free OCR delegation now have specific
source findings and prospective workflows, with runtime acceptance left visible.
No fixed list can establish permanent or universal state-of-the-art superiority.
