# Native memory and RAG: active use and lifecycle monitoring

Verified September 21, 2026. The adopted project uses the existing native
Codex/Claude integrations. No competing memory daemon or replacement agent
harness was installed. The [memory landscape review](memory-landscape-maintenance.md)
records nine repository sources and their selection rationale.

The [September 23 scheduled observation](../observability/memory-scheduled-20260923.json)
now records an actual daily heartbeat and returned native checks. The existing
hourly learning scheduler applied two pages at 10:04:49 UTC; journal, proposal
records and scoped MCP reads agree. A later 11:05 response-decoding failure has
no persisted learning run and remains unresolved. The latest completed native
session's consolidation finished on attempt 1. No learning run was triggered
manually for this observation. These outcomes establish lifecycle execution,
not improved answer quality or token savings.

## September 30 scheduled follow-up: consolidation quota failure

**Host scope — added 2026-10-03 under 0c custody.** This section is a historical
2026-09-30 observation of a systemd-managed `agent-lab` memory stack, and its
receipt has no host field. The receipt's `ai-memory`, `qdrant-agent-lab` and
`nemotron-embed-agent-lab` units match the records of the WSL2 authoring laptop
(`wsl-authoring-20260923` in the [host registry](../adoption/host-roles.json);
its [September 26 embedding switch](../evidence/receipts/vllm-030-switch-laptop-20260926.json)
names the same embedding unit), not the workstation. This automation's
[September 27 receipt](../observability/memory-scheduled-20260927.json) records
the custom build `2.3.2-prefix-gpt6-f24f7181` from source `62e73148`, the
previously recorded source this receipt cites, whereas the
[component lock](../manifests/stack.json) records upstream 2.4.1 on the
workstation's memory unit since 2026-09-26. The observation predates the
[2026-10-02 two-host decision](decisions/2026-10-02-two-host-north-star-architecture.md),
whose scope is macOS and the workstation only. It is therefore not evidence
about the Mac's ai-memory 2.5.2 owner, that decision's singular memory owner,
the workstation or current consolidation health. Queue semantics after
the reviewed pin `353841d9` were not reviewed, including those of main's ai-memory
2.4.1 component lock and the Mac owner's 2.5.2.

The [September 30 receipt](../observability/memory-scheduled-20260930.json) records
the actual scheduled wake and a new failed consolidation. A scoped read-only
store query returned generation 17,318 in `failed` state after five attempts;
the last attempt ended at 08:58:10 UTC with provider HTTP 429
`usage_limit_reached`. Its error reports a reset at October 4, 06:59:07 UTC;
that historical timestamp is not a fresh quota check or a recovery guarantee.
Explicit native MCP readback confirmed the genuine session end at 08:49:54 UTC.
The ended generation and the later MCP observation count have different scopes.

Memory, Qdrant and embedding services still run, the native collector published
successfully, and all nine Prometheus targets were up. Inventory `llm_status`
changed from `ok` to `unavailable`; that metadata alone does not establish the
cause. No consolidation-specific firing alert was returned. Existing dashboard
service health and historical task checkpoints do not establish successful
consolidation. One semantic retrieval matched its original source; the unchanged
QMD setup note reuses the previous search/get evidence.

The upstream learning report still returns 83 historical runs and 19 approved
terminal proposals. Its unchanged aggregate is separate from the consolidation
queue. The hourly learning scheduler remains paused. No provider retry, account
switch, fake session-end event or database mutation was performed; preserve the
failed generation and qualify supported recovery after quota returns. Installed
selections, exact-savings unknowns and restart-evidence boundaries remain unchanged.

The available clean [upstream consolidation queue](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-store/src/session_consolidation.rs)
stops claiming a generation once it is `failed`. Its direct MCP
`memory_consolidate` interface accepts an exact session ID, but does not reset
that queue row; a later manual result must retain its separate provenance.
The source also has nested provider retries, so five queue attempts do not
establish the number of HTTP requests. Actual request count is unmeasured.
This is source review only: the installed custom build's equivalence is unknown,
and the previously recorded source ref could not be retrieved. No recovery
command was executed during this wake.

## September 28 scheduled follow-up

The [September 28 receipt](../observability/memory-scheduled-20260928.json) records
the next actual wake. Services and existing publications were healthy; the swap
warning was no longer firing. Learning remains paused, and the upstream report
still returns 83 runs and 19 approved terminal proposals. Its body matches the
retained September 27 result apart from the reporting-window timestamps.

Explicit native MCP retrieval confirmed the long Claude session ended at
01:22:54 UTC, and the scoped store records generation 31,006 completed at
01:26:43 on attempt 1. This proves recorded completion, not provider success or
improved answers. The MCP default selects completed sessions by start time;
it therefore returned the newer-starting September 26 short session. Source
inspection resolved that difference without restarting a client.

The previous evidence PR's secret scan detected seven upstream rejection
digests. Source review confirmed their SHA-256 construction. A separate,
exact-file/seven-value exception preserves unrelated credential detection;
the original failure, regression checks and bounded native scan are retained.

## September 27 scheduled follow-up

The [September 27 observation](../observability/memory-scheduled-20260927.json)
and [returned native results](../observability/memory-scheduled-results-20260927.json)
record the actual daily wake. Current local service/configuration reads confirm
the previously installed prefix-enabled ai-memory build, Nemotron memory
embeddings, vLLM 0.30.0 and Codex gpt-6-sol at medium effort. The hourly learning
scheduler has been intentionally paused since September 25. The table below and
September 21 configuration are historical; do not restore their older model,
embedding or scheduler settings over the current qualified setup.

Memory, Qdrant and embedding services were healthy; the existing collector
published successfully and all 9 Prometheus targets were up. The native report
returned 83 historical runs and 19 approved terminal proposals. The latest
captured completed session has no consolidation job. The latest completed job
is an older observation generation, completed September 24; it does not validate
the subsequent model change. One semantic excerpt and the QMD pause decision
matched their source. Exact session/lifetime savings remain unknown.

Stock ai-memory [v2.4.1](https://github.com/akitaonrails/ai-memory/releases/tag/v2.4.1)
still lacks the query/document prefixes required by this deployment. Independent
tagged-source review confirmed that its query-dispatch fix is already present in
the installed patch. Retain the current build pending a release containing
upstream #859 and isolated migration/retrieval qualification; this wake made no
runtime change. Existing gateway/swap warnings and missing journal output are
retained in the receipt. No restart persistence or new cross-client E2E is claimed.

## Historical September 21 installed selection

| Layer | Accepted upstream | Current qualification |
| --- | --- | --- |
| Shared memory | ai-memory 2.3.2 | Scoped native MCP, allowlisted hooks, local MiniLM embeddings, native Codex consolidation, hourly learning configuration. |
| Semantic code retrieval | SocratiCode 1.15.0 | Current stable release; both clients registered, direct project watcher active. 1.14.0 until the 2026-09-27 cutover ([receipt](../evidence/receipts/socraticode-1150-qualification-20260927.json)). |
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
| Hourly | ai-memory native learning and embedding-backfill configuration | September 23 journal and scoped store/MCP readback confirm two applied pages. A later response-decoding failure is retained; write completion does not establish improved learning quality. |
| Daily, existing 09:00 schedule | Native Codex task follow-up | September 23 heartbeat received at 13:01:02.931 UTC, with bounded current retrieval, source comparison and lifecycle checks. Trigger provenance is the native task envelope; independent scheduler dispatch metadata and restart persistence remain unknown. |

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

### Maintained-decision routing

After native compaction or resume, retrieve the latest maintained decision from
the verified project scope before describing deployed architecture. Check its
currency and original sources; a compacted summary can retain stale versions.
This is task-triggered retrieval, not an added startup hook or audit. Preserve
native compaction and caching.

For a maintained current decision whose exact path is unknown, use the adopted
project marker's workspace and project explicitly. Select the installed schema
before using optional fields; the example needs ai-memory 2.4.0 or later:

```text
memory_query(query="memory selection",
             workspace="agent-lab", project="agent-lab",
             pin_first=true, limit=2, answer=false)
memory_read_page(path="<exact path returned by memory_query>",
                 workspace="agent-lab", project="agent-lab")
```

These are supported MCP arguments, not shell syntax. Substitute the adopted
scope; never fall back to another project when the requested scope is missing.
The portable Mac installer still pins 2.3.2, whose schema lacks `pin_first`:
omit both `pin_first` and `answer`, which that schema also lacks, and use ordinary
scoped query followed by exact-path read. `answer=false` keeps this lookup
on the supported retrieval path without LLM answer synthesis. Read the exact page
when a returned snippet omits a required fact; keep source provenance visible.
Read a known exact path directly. `pin_first` prioritizes existing pins; it does
not create or maintain a pin, certify currency or make memory operating authority.
Check the full page's date, supersession and cited canonical sources before
acting. Widen the scoped query if the two results do not satisfy the task; retry
without `pin_first` when unrelated or stale pins crowd out relevant hits. A
miss in the first two is not evidence of absence. Upstream applies `pin_first`
only to a single-project query; it ignores it on `scopes`, `global` and `as_of`.
See [ai-memory v2.5.0's schema and ordering implementation](https://github.com/akitaonrails/ai-memory/blob/v2.5.0/crates/ai-memory-mcp/src/server.rs#L565).

The [Mac owner's report](decisions/2026-09-30-bounded-native-decision-routing.md)
found the maintained decision at rank three with the default query and first
with scoped `pin_first=true, limit=2`, followed by exact-path read. This establishes
reported retrieval ordering only. The official Mac ai-memory 2.5.0 control does
not inherit the historical local build's measured quality; Hindsight remains
isolated pending the amended paired comparison and existing promotion gates.

The [separate continuity follow-up](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384#issuecomment-5924447784)
reports failed tool-free recall after compaction, then correct deployed-version
and zero-savings recall in a distinct turn using exactly two native memory calls
(bounded scoped query and exact-page read). That is maintained-memory recovery;
the original compaction semantic gate remains failed. Successful PreCompact
dispatch does not establish durable attribution to the assigned session.

For another PC, use the chosen [adoption profile](../adoption/manifest.json) and
upstream recipes, native sign-in, explicit project scope and that host's own
evidence. Do not copy private client configurations or interpret this host's
receipt as another host's acceptance. A client file edit does not establish hot
reload in an already-running Desktop task, and no physical reboot is claimed.

The [retained results](../evidence/receipts/memory-landscape-lifecycle-20260921.json)
bind actual upstream output, current-client evidence, independent readback,
monitoring observations and the preserved failed observation.
