# Native hosting path

A native Dagu user service now provides authenticated local research run history.
Its accepted workflow, failure/cancellation checks and restart result are in the
[hosting receipt and replay guide](hosting/README.md). Other new tool acceptance
processes exited when work completed. Existing memory/RAG services keep their own scoped
lifecycle. No new cloud resources, paid hosts, public ports or standing trading
service were created. Dagu binds loopback and runs the status server only; its UI
cannot submit or edit jobs. Restarting this conversation is unnecessary for the native
commands; old Desktop tool catalogs still need their normal reload to gain newly
registered tools.

Use the native SDK for bounded on-demand research workers and the pinned LEAN
launcher for deterministic backtests. A research launch environment must exclude
broker secrets, and its own MCP permissions must be reviewed. The SDK environment
argument is an overlay, not isolation. Reuse the installed tools from explicit
paths; do not install a second gateway or copy account stores.

DeerFlow's loopback Gateway has been started and stopped successfully. Its current
discovery profile disables models, tools, memory and scheduling and uses an
in-memory database; running it forever would not provide a durable research
service. Before hosting it, deliberately configure persistent storage, auth,
process restart behavior, a non-host-shell sandbox and the intended model route.
The full browser application also needs its native frontend/reverse proxy, which
were not installed for backend acceptance. [Native recipe](deerflow/README.md)

For an eventual always-on paper system, a dedicated Linux machine/service account
is the next hosting boundary. Choose local versus managed hosting once uptime,
recovery and spend requirements are known. Keep one engine order writer per
account/strategy scope, a persistent order journal, broker reconciliation on
restart, independent risk checks and a kill switch. Research workers can be
stopped without disabling broker-state recovery. A gateway's expiring A2A task
record or an LLM retry is not durable execution state.

The native LEAN engine source-build/backtest path needs no paid QuantConnect
account. Initializing its Alpaca adapter separately requires the documented
[QuantConnect entitlement](engine/resolution.md#remaining-account-and-runtime-boundaries). LEAN CLI
local engine commands require Docker and the documented QuantConnect account
tier. QuantConnect-managed cloud hosting has its own account/tier requirements;
neither path was enabled here. No managed-host deployment result is
claimed. Docker, Kubernetes, Temporal and Redis are not prerequisites for the
completed native proof and were not added speculatively.

Before a standing trading service, use the patched dependency build and
exercise restart/reconnect and duplicate-order handling in paper mode, establish
data entitlements and session rules, and check actual model-worker cancellation
and usage reporting. Local Dagu subprocess cancellation is distinct from provider
request cancellation. These are unresolved trading-runtime requirements, not
checks that this documentation marks passed.
