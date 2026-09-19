# Native hosting path

Current installations are persistent local tools; their acceptance processes
exited when work completed. Existing memory/RAG services keep their own scoped
lifecycle. No new cloud resources, paid hosts, public ports or standing trading
service were created. Restarting this conversation is unnecessary for the native
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

The native source-build LEAN path needs no paid QuantConnect account. LEAN CLI
local engine commands require Docker and the documented QuantConnect account
tier. QuantConnect-managed cloud hosting has its own account/tier requirements;
neither path was enabled here. No managed-host deployment result is
claimed. Docker, Kubernetes, Temporal and Redis are not prerequisites for the
completed native proof and were not added speculatively.

Before a standing service, resolve the recorded LEAN dependency advisories,
exercise restart/reconnect and duplicate-order handling in paper mode, establish
data entitlements and session rules, and check actual model-worker cancellation
and usage reporting. These are unresolved trading-runtime requirements, not
checks that this documentation marks passed.
