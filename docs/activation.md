# Activation and future sessions

Configuration on disk and tools callable by a running client are separate facts. The September 19 evidence establishes the following:

| Host or layer | Observed state | What a future session needs |
| --- | --- | --- |
| Native Linux Codex and Claude | Core Context Mode, scoped ai-memory and SocratiCode workflows completed in actual agent tasks | Start the client in the configured project with its native account and local services available |
| Active Codex Desktop task | Direct ai-memory retrieval and SocratiCode search worked; native QMD, graph and browser workflows also completed | Check the new task's actual tool catalog; do not infer direct availability from a successful CLI bridge |
| Context Mode in this Desktop task | Installed skill plus successful upstream MCPorter bridge; no direct Context Mode tools exposed in this task | A newly started task may load registered tools; verify discovery before claiming direct activation |
| Automatic code RAG | The explicitly selected project's watcher persisted add/change/delete changes in Qdrant | Keep the native MCP watcher and local embedding/vector services running; adopt another project explicitly |
| Document retrieval | An explicit QMD collection provided BM25 search and source retrieval | Refresh the chosen collection when documents change; this is separate from the code watcher |
| Shared memory | Project scope, native capture hooks and cross-client retrieval exercised | Use the matching project scope and installed routing skills; do not treat another project's state as global |
| Windows and Linux configuration | Separate native configuration roots | Configure each host deliberately; a Linux registration does not prove a Windows client loaded it |

A new task is appropriate after changing startup configuration or tool registration. Restarting does not replenish an account allowance. The additional native Codex CLI document/graph/browser attempt was quota-blocked; the current Desktop task and native Claude completed those workflows separately.

These practices persist through the installed project instructions, native registrations and service configuration. They do not automatically index all future repositories or start every optional tool. The public examples are inactive templates, not copies of the original machine's active settings. Follow the [native recipes](../recipes/README.md) to adopt the stack for another project.

See the [evidence boundaries](evidence.md) and individual receipts for the exact host, execution level and remaining limits.

## Native observation profile

The [local observation guide](../observability/README.md) records six enabled native
user services and real Codex/Claude child-process telemetry from this Desktop task.
User-level native configurations are saved; the existing Desktop process was not
restarted or hot-reloaded. Fresh native launchers and SDK/ACP examples assign unique
process identities. Future native SDK launches can publish atomic bounded result
metadata through `ECOSYSTEM_SDK_OBSERVATION_DIR`; missing usage remains unknown.
The SDK native histogram was not observed, so its separately labeled file-receiver
receipt panel is used for reported usage. Other hosts/client homes need explicit
configuration and observed acceptance. No global MCP hot-reload claim is made.
