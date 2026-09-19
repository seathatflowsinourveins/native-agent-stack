# Activation and future sessions

Configuration on disk and tools callable by a running client are separate facts. The September 19 evidence establishes the following:

| Host or layer | Observed state | What a future session needs |
| --- | --- | --- |
| Native Linux Codex and Claude | Core Context Mode, scoped ai-memory and SocratiCode workflows completed in actual agent tasks | Start the client in the configured project with its native account and local services available |
| Active Codex Desktop task | Direct ai-memory retrieval and SocratiCode search worked; native QMD, graph and browser workflows also completed | Check the new task's actual tool catalog; do not infer direct availability from a successful CLI bridge |
| Context Mode in the restarted Desktop task | Later restart acceptance discovered 11 direct tools and exercised direct calls; correlated parent logs arrived | A new host/task needs its own discovery and exporter check; see the dated restart receipt |
| Automatic code RAG | The explicitly selected project's watcher persisted add/change/delete changes in Qdrant | Keep the native MCP watcher and local embedding/vector services running; adopt another project explicitly |
| Host capacity | Native Collector exported eight metric families and 23 series for CPU, memory, load and root-filesystem usage | Keep the selected receiver and metrics pipeline active; this observes the WSL environment, not the Windows physical backing disk |
| Document retrieval | An explicit QMD collection provided BM25 search and source retrieval | Refresh the chosen collection when documents change; this is separate from the code watcher |
| Shared memory | Project scope, native capture hooks and cross-client retrieval exercised | Use the matching project scope and installed routing skills; do not treat another project's state as global |
| Windows and Linux configuration | Separate native configuration roots | Configure each host deliberately; a Linux registration does not prove a Windows client loaded it |

A new task is appropriate after changing startup configuration or tool registration. Restarting does not replenish an account allowance. The additional native Codex CLI document/graph/browser attempt was quota-blocked; the current Desktop task and native Claude completed those workflows separately.

These practices persist through the installed project instructions, native registrations and service configuration. They do not automatically index all future repositories or start every optional tool. The public examples are inactive templates, not copies of the original machine's active settings. Follow the [native recipes](../recipes/README.md) to adopt the stack for another project.

See the [evidence boundaries](evidence.md) and individual receipts for the exact host, execution level and remaining limits.

## Native observation profile

The [local observation guide](../observability/README.md) records native user
services and real Codex/Claude child-process telemetry launched from Desktop.
The [current-session follow-up](../observability/session-e2e.md) resolves the
prior SDK histogram gap: one fresh Astra task completed in **12,493 ms**, and all
six native Prometheus token categories matched its final native usage. The
current atomic receipt writer also produced an observation that reached Loki.
[Exact follow-up receipt](../observability/followup-receipt.json).

The native AppServer analytics gate needed `analytics.enabled=true`. The
follow-up added this once to each selected native-user/Desktop configuration
only where the setting was unset, retaining explicit false values and the
already configured loopback OTLP endpoints. It added no helper-specific metric
flag or exporter override. This enables the accepted native pipeline for fresh
processes; it does **not** establish that all first-party telemetry stays local.

Fresh native launchers and SDK/ACP examples assign unique process identities.
SDK runs can additionally publish atomic bounded result metadata through
`ECOSYSTEM_SDK_OBSERVATION_DIR`; unavailable usage stays unknown. Native usage,
OTLP histograms and file observations are alternative views of the same turn,
not amounts to add. Two earlier SDK observations were imported summaries; the
new third observation was automatically written by the current helper.

The earlier follow-up preceded a Desktop restart and found no correlated parent
exporter records or direct Context Mode tools. The later
[restart acceptance](../observability/desktop-restart.md) supersedes those gaps:
11 direct Context Mode tools were discovered, actual calls succeeded, and
correlated parent logs arrived. This does not make every new process or host
accepted. Follow [new-machine adoption](../adoption/README.md) for a separate
client discovery/export check; there is no global MCP hot-reload claim.

A saved Context Mode snapshot covered **9h55m of the retained bridge connection**:
**50 calls, 208 KB entered context and zero estimated tokens saved**. It is not
usage for the whole Desktop task, every client or the provider account. The
separate 188,769 → 500-token artifact selection does not change that counter.
