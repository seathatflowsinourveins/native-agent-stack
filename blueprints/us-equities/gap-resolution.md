# Gap-resolution results — September 19, 2026

This update closes bounded research, build and local-hosting gaps. It does not
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
| Provider-level token savings | Cached-input counters and smaller retrieved artifacts are different measurements | A paired, same-task/quality usage comparison including coordinator, failed calls and retries before asserting net savings |

The earlier reproducible QMD selection remains **6,398 → 490 tokens**, or
**5,908 fewer / 92.34% less selected text**, measured with `gpt-tokenizer 3.4.0`
`o200k_base`. That is not a provider billing reduction. The new DeerFlow task's
cached input is already part of its input total; reasoning output is already
part of output. Do not add either subset a second time.

## Persistence and future sessions

Native tools, local patches, public recipes and scoped project instructions are
saved. The Dagu user service is enabled and survives conversation changes; it
schedules no work and stops when its Windows/WSL host stops. Accepted native
commands can run in this session. Existing Desktop tasks keep their current MCP
tool catalogs; newly registered tools use normal client discovery/reload. Other
projects require explicit scoped adoption, and future model tasks still need
fresh account-readiness checks.

The complete star ledger and the 140-repository core catalog are complementary:
an individual source disposition is not an installation decision. Candidates
such as Vibe-Trading, ai-trader and provider-free OCR delegation now have specific
source findings and prospective workflows, with runtime acceptance left visible.
No fixed list can establish permanent or universal state-of-the-art superiority.
