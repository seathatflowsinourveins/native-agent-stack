# Native memory and RAG: active use and lifecycle monitoring

Verified September 21, 2026. The adopted project uses the existing native
Codex/Claude integrations. No competing memory daemon or replacement agent
harness was installed. The [memory landscape review](memory-landscape-maintenance.md)
records nine repository sources and their selection rationale.

## Installed selection

| Layer | Accepted upstream | Current qualification |
| --- | --- | --- |
| Shared memory | ai-memory 2.3.2 | Scoped native MCP, allowlisted hooks, local MiniLM embeddings, native Codex consolidation, hourly learning configuration. |
| Semantic code retrieval | SocratiCode 1.14.0 | Current stable release; both clients registered, direct project watcher active. |
| Vector store | Qdrant 1.19.1 | Current stable release; existing native loopback service and persistent project collection. |
| Local embedding inference | vLLM 0.25.0 with pinned NVIDIA Nemotron-3-Embed-1B-BF16 | Retained qualified version. Newer 0.29.0 has an actual host initialization failure; newer is not automatically usable. |
| Exact source navigation | Serena 2.0.0.dev0 at c6fbd1c5932df2494ffa0020af5a9fbe80b82143 | Current native symbol lookup returned the original scope-selection implementation. |
| Documentation retrieval | QMD 2.8.3 | Current stable release; explicit project BM25 collection. Zero vectors is intentional for this lane. |

Exact accepted pins remain in [stack.json](../manifests/stack.json). The
[vLLM compatibility receipt](../evidence/receipts/vllm-compatibility.json)
retains the failed 0.29.0 attempt and recovery to 0.25.0. The observed eager,
single-GPU BF16 path has no demonstrated need for the unrelated 0.25.1 fixes.
Track the unreleased SocratiCode [collection-creation race fix](https://github.com/giancarloerra/SocratiCode/pull/177)
and [logging/shutdown changes](https://github.com/giancarloerra/SocratiCode/pull/179)
when a stable release or observed problem merits qualification.

## Actual native use

The running Codex task used native ai-memory retrieval, SocratiCode semantic
search and Serena symbol lookup. Search returned the real
`tools/ecosystem/linux-usage-report.cjs`; the returned source spans matched the
file on disk. This is useful retrieval on one real question, not a general recall
benchmark or measured provider-token saving.

A fresh native Claude task discovered and called both `memory_read_page` and
`codebase_search`. It returned the current memory setup decision and the same
usage-report source, then exited successfully after four turns. Its exact
764-byte final reply was independently read back from the stored Stop observation;
all nine lifecycle observations were present, and consolidation generation 9
completed on attempt 1. Provider input, cache creation, cache reads and output
are recorded separately in the receipt.

The first local readback incorrectly compared a text UUID with an upstream
16-byte SQLite BLOB, yielding an empty result. Correct typed lookup resolved
the apparent capture failure. Prefer native MCP/CLI readback; any direct database
observation must follow the pinned source schema. A zero-row query is not proof
that a hook failed.

Native Codex discovery reports the three project MCP integrations enabled in
both homes; native Claude reports them connected. Executable targets and shared
skills exist, and allowlisted capture admits the adopted project while rejecting
an unrelated directory. Registration, connection, actual use and stored lifecycle
outcomes remain separate evidence.

## Monitoring already running

| Cadence | Existing native path | What it proves |
| --- | --- | --- |
| Every two minutes | systemd native-data timer; upstream memory/QMD commands and Qdrant API; Loki publication | Fresh inventory and returned metadata. Actual timer invocations and HTTP 204 publication were observed. The oneshot service is normally inactive between successful runs. |
| Continuous scrape | Existing Prometheus, Collector and Grafana | Configured service/transport alerts and native runtime counters; not retrieval correctness. |
| Hourly | ai-memory native learning and embedding-backfill configuration | Prior actual scheduler admission is retained. A later hourly tick is still unproved in this receipt; no new learned-write quality claim. |
| Daily, existing 09:00 schedule | Native Codex task follow-up | Updated to check scoped memory retrieval, real completed-session/learning outcomes, source agreement and selected RAG freshness. Updated configuration is verified; its next scheduler-triggered execution is not claimed. |

The daily follow-up reuses valid upstream tests and historical add/change/delete,
client-use and recovery evidence while their inputs match. A changed source,
scope, model, configuration or observed failure calls for the affected check,
not another whole-stack startup audit. Native agent launches are repeated only
when they resolve a concrete client-lifecycle uncertainty.

The existing progress publisher had been reading an older working checkout. A
native systemd service drop-in now selects the canonical catalog checkout; the
publisher implementation is byte-identical, and the old checkout's uncommitted
work is preserved. Its existing 30-second timer and private cache remain in use.
The new checkpoint must be observed in Loki after publication before treating
the dashboard as current; a successful unit-file edit alone is insufficient.

The native project MCP profiles use `SOCRATICODE_WATCHER=auto`. The one-shot
MCPorter reporting profile deliberately uses watcher and auto-resume **off** so
bounded reads terminate. Its disabled-watcher message is not a broken native
integration. An active watcher and chunk count alone do not prove edits propagated;
compare a returned excerpt with its current source and preserve separate graph
freshness and recovery boundaries.

The task follow-up remains quiet for unchanged healthy state and reports meaningful
failures, changes or required action. It runs while the local app and computer
are available; it is not off-host monitoring. See the [official scheduling guide](https://learn.chatgpt.com/docs/automations?surface=app).

## Supported observation commands

Use the project marker and registered native MCP tools for scoped memory and RAG:

```text
memory_read_page(path="decisions/native-memory-learning-maintenance.md",
                 workspace="agent-lab", project="agent-lab")
codebase_status(projectPath="/absolute/adopted/project")
codebase_search(projectPath="/absolute/adopted/project", limit=1,
                query="collect native Linux and Desktop usage separately")
```

These are MCP argument examples, not shell commands. Native shell observations:

```sh
ai-memory auto-improve-report --workspace agent-lab --project agent-lab --json
qmd --index agent-lab-docs search 'Current native memory and RAG' -c agent-lab-docs -n 2
qmd --index agent-lab-docs get qmd://agent-lab-docs/tasks/2026-09-21-memory-rag-lifecycle.md
systemctl --user show ai-memory.service qdrant-agent-lab.service nemotron-embed-agent-lab.service --property=ActiveState --property=UnitFileState --property=Result
systemctl --user show ecosystem-native-data.timer --property=ActiveState --property=LastTriggerUSec
```

For another PC, use the chosen [adoption profile](../adoption/manifest.json) and
upstream recipes, native sign-in, explicit project scope and that host's own
evidence. Do not copy private client configurations or interpret this host's
receipt as another host's acceptance. A client file edit does not establish hot
reload in an already-running Desktop task, and no physical reboot is claimed.

The [retained results](../evidence/receipts/memory-landscape-lifecycle-20260921.json)
bind actual upstream output, current-client evidence, independent readback,
monitoring observations and the preserved failed observation.
