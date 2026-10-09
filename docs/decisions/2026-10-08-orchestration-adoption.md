# Orchestration adoption on this host — 2026-10-08

Keep hcom for the co-op's native lane transport and launch path. Wire Claude
agent teams, Claude workflows and agent-orchestrator through their vendor
interfaces, with the owner gates below. These are four decisions about distinct
jobs; installation, configured routing, recorded execution and organic use in a
fresh owning session remain separate claims.

The foundation action serves recoverable coordination of engineering and
research workers supporting US-equities research and historical simulation.
It supplies no strategy or broker qualification. The base is
`aba02ec3456d383bcc2fc72883db098f9be7918a`. This PR records evidence and future
acceptance; it applies no host settings, launches no model task and authorizes
no new AO route. Landing belongs to 5f after the CC cue.

The accompanying [sanitized evidence record](2026-10-08-orchestration-adoption.json)
contains the source hashes, returned native projections, unknown counters,
failed conditions and pending gates.

## Measurement boundary

The co-op's `command-center/pages/adoption-now.json`, generated
`2026-10-08T23:42:51Z`, covers 24 hours and reports 63 Claude sessions and 841
Codex conversations. Its SHA256 is
`5de97cf238b3d28aa9f7d5110a05857204a847b0c75cda8971de8e142e362e36`.
Every number taken from that snapshot refers to those exact bytes, retained
privately before the next hourly refresh. The producer's SHA256 is
`10784aa8862eaed3a5e0520ecdb2eb58cdf0277f4bab62f8868a86b703954408`.

That producer defines seven MCP-based layer groups. Claude's server rates use
`tool_result` with `tool_name="mcp_tool"`; Codex's use `codex.tool_result` with a
nonempty MCP server name. None of the four orchestration layers appears in
those groups. Their native invocation rates are **unmeasured**, rather than
zero. CLI message/lifecycle records, native team/workflow metadata and AO
receipts supplement the dashboard; they do not become its count of record.
The CC/co-op owns any producer/schema extension.

The CC's later measurement ruling assigns Claude-native `Agent`, `Workflow`,
`SendMessage` and `Monitor` tool results by role, and Codex `spawn_agent` by
lane, to that producer. These proposed native counts supplement its original
MCP-only definition. This record leaves the producer unchanged.

### Proposed hcom and AO measures

Use the same half-open 24-hour interval `[start, end)` as the hourly snapshot,
but retain native source and attribution separately. These are proposals,
not new collectors, queries run against the host store or measured rates.

| Native source | Proposed measure | What the measure cannot establish |
| --- | --- | --- |
| hcom 0.7.28 event store / supported `events_v` fields, [event append/read source](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/src/db/events.rs) | Count unique native `life` events with action `ready`; count `launch_failed` and `launch_blocked` separately. Preserve batch, instance, initiating `by` and event time. Ready is emitted on the first status transition, not every polling read. | Ready is not a successful model turn or completed engineering task. A current instance list is not a historical 24-hour census. |
| hcom [kill command](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/src/commands/kill.rs) and [stop lifecycle](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/src/hooks/common.rs) | Count unique stopped lifecycle events whose reason is `killed`, preserving the initiator and target role. Deduplicate by source segment and native event id, including archived segments if that is the declared window coverage. | A recorded kill includes cleanup of an untracked instance; it does not independently prove PID exit, tab closure or worktree cleanup. Those require the separate native inverse observation. |
| AO v0.13.5 [native access logger](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/backend/internal/httpd/log.go) and [generated API](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/backend/internal/httpd/apispec/openapi.yaml) | Count native `http request` log entries for `POST /api/v1/sessions` (`spawnSession`) by response class; retain request id, method, normalized path, status and duration only. Join an approved project/session receipt to its owning role; unresolved attribution stays unknown. | Successful API admission does not prove a worker model turn, organic selection or automatic feedback delivery. Health/status GETs are not orchestration invocations; exclude remote address, errors with private detail and request/response bodies. |
| AO [SCM observer diagnostics](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/backend/internal/observe/scm/observer.go) and [feedback reducer](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/backend/internal/lifecycle/reactions.go) | Count existing observer failure/rate-limit/lifecycle-ack diagnostics separately, with sanitized session/project attribution and native file/offset identity. Keep successful feedback and poll counts unknown unless an actual native delivery/counter receipt supplies them. | Default diagnostics do not emit a complete successful-poll/delivery census. Dedup/accounted feedback outcomes also include prior sends or exhausted attempt budgets; do not count them as new sends. |

For each native source, declare log/store retention and complete interval
coverage, role-map revision, missing attribution, failures and read boundaries.
Report counts with eligible fresh owning-role session denominators only when
those denominators exist. Never sum overlapping snapshots or infer an organic
invoke from a control log alone. CC/co-op decides the native ingestion and
attribution wiring; no new exporter or logging setting is implemented here.

## Decisions and ownership

| Layer | Decision | Distinct job and owning role | Evidence and remaining boundary |
| --- | --- | --- | --- |
| hcom | KEEP | Co-op launches owned native lanes and transports cross-session messages; Claude and Codex coordinators consume the vendor hooks. | Native 0.7.28 status reports valid configuration, `wt-tmux`, and both client hooks installed. Fresh `orch-records` readiness is event 64738, batch `7f70b0bb`; its live Codex instance has hooks and process bound. Routine peer request 63840 and reply 63854 have delivered recipients and a causal reply link. This proves the current Codex lane path and actual peer transport, with fresh Claude acceptance still pending. |
| Claude agent teams | WIRE | A Claude coordinator uses named peers, native team coordination and parallel independent reasoning within its own task. Co-op and CC own their respective team scope. | Native teams are enabled by the selected user experimental flag. Team metadata exists, but the current shared-root team lead cannot yet be attributed to the owning role or an organic fresh task. Wire the vendor's task-selection instruction at the owning coordinator scope; the already-set flag is not the missing step. |
| Claude workflows | WIRE | A Claude coordinator delegates a dependency graph, records node execution and recovers staged work. CC and co-op own their respective routing; API-actions is a separately measured role. | Native workflow history is attributable to the CC. Execution history does not establish the task's trigger or fresh-session organic use. The shared CC/co-op project's higher-precedence local `ultracode=false` suppresses the vendor's automatic route despite project `ultracode=true`. Resolve that owner-scoped override through the supported setting before re-measuring. |
| agent-orchestrator | WIRE | The PR-feedback owner routes durable SCM observations to one bounded live worker, rather than manually carrying each CI/review opportunity. 5f continues to own landing. | Installed v0.13.5 release provenance, native `dev` version and stopped status are distinct facts. Prior sandbox and PR observation passed; the native Codex proposal failed on account quota in three turns and its runtime/import inverse completed. Native feedback policies and project/worker rules are the supported route; availability, exact config ACK and a fresh native worker proof remain owner gates. |

No layer is retired merely because MCP telemetry omits it. These jobs have
different boundaries: cross-client lane transport, same-client peer
coordination, dependency-graph execution and durable SCM-to-worker feedback.
The record does not establish a quality or cost winner between them. The
decision would change if a matched, owner-scoped task showed another retained
layer performing the entire distinct job through its native supported path.
Ordinary vendor subagents and native Claude cross-session messaging are also
candidate classes for the narrower coordination tasks. The proposed boundaries
do not prove exclusivity or justify teams for work a single subagent can finish.

## Vendor routing and sources

| Layer | Maintained source and pin | Routing interface |
| --- | --- | --- |
| hcom | [aannoo/hcom v0.7.28](https://github.com/aannoo/hcom/tree/b2a7c192003e7fd67ed93265289e4ac36276f965), `b2a7c192003e7fd67ed93265289e4ac36276f965`; `README.md`, `src/hooks/codex.rs` | Vendor launch-time hooks and injected instructions. Keep native launch, ready, delivery and reply evidence; a command's exit alone does not prove delivery. |
| Agent teams | [anthropics/claude-code v2.1.295](https://github.com/anthropics/claude-code/tree/602df92bf481ed904533e95c09f740f40aab5aed), `602df92bf481ed904533e95c09f740f40aab5aed`; `CHANGELOG.md` sections 2.1.178 and 2.1.295; [official agent-team instructions](https://code.claude.com/docs/en/agent-teams) | Native experimental flag plus the vendor's coordinator instructions for selecting parallel team work and giving peers bounded ownership/context. Put the selected instruction in the owning coordinator's supported instruction scope, not a task prompt that names tools. |
| Workflows | Same Claude tag/commit; `CHANGELOG.md`; [official workflow instructions](https://code.claude.com/docs/en/workflows#let-claude-decide-with-ultracode), [settings precedence](https://code.claude.com/docs/en/settings) | Supported persistent `ultracode` setting or `/effort ultracode`. Reconcile the controlling local setting in the owner scope. Native `/workflow-authoring` is for authoring scripts; it is not itself an execution trigger. |
| agent-orchestrator | [OrchestratorInc/agent-orchestrator v0.13.5](https://github.com/OrchestratorInc/agent-orchestrator/tree/c95ae361eee48d33c2f443c6d2fe69c445f548a8), `c95ae361eee48d33c2f443c6d2fe69c445f548a8`; `docs/scm-observer.md`, `docs/cli/README.md`, `backend/internal/domain/projectconfig.go`, generated `backend/internal/httpd/apispec/openapi.yaml` | Vendor typed project configuration, role rules and native CI/review forwarding policies resolved for a live session. `claim-pr` records ownership; it does not check out or verify a PR head. Whole-object `set-config` is not a safe partial update to an existing project. |

Claude 2.1.178 removed `TeamCreate`/`TeamDelete`: enabled sessions have an
implicit team and named Agent peers start directly. A test requiring those
removed tools would test an obsolete interface. Public source commit and
installed executable build identity are recorded separately.
The linked vendor documentation was observed on 2026-10-08 and is mutable;
the release commit pins the changelog, not those pages. No exact packaged
team-routing block was extracted from the installed executable, and no
separately named vendor team-routing skill or hook is claimed. Before applying
the instruction-based WIRE, retain the selected vendor instruction text with a
content hash at the owner scope; this draft does not satisfy that content pin.

Saved workflow examples and their checksums are repository reference evidence.
Their absence from the selected runtime workflow directories does not remove
native automatically generated workflows. The historical agent-lab source
locator was unavailable to this read; checksum consistency is not current
upstream execution or runtime installation.

## Fresh-session proof

These are pending native acceptance tasks, not results from this PR. The input
states an engineering outcome, scope and acceptance, with no orchestration tool
names or invocation instructions. The vendor route and owning role choose the
mechanism. Record session creation time and role, source/configuration revision,
native invocation/completion metadata, usage scope and inverse. Retain failures
and unknown usage. Explicit forced invocations and this record's read-only
inventory remain separate from organic-use evidence.

| Layer/client | Natural task and native proof | Discriminating condition |
| --- | --- | --- |
| hcom / Claude | In a new co-op coordinator session, resolve a bounded engineering task requiring a separate owned native lane. Observe vendor launch/ready metadata, injected hook binding, a delivered request and its causal reply. | The receiving lane exists but lacks a bound hook or the request has no delivery/reply; reject the positive proof despite sender exit 0. |
| hcom / Codex | Run the same bounded coordination outcome in a fresh owning Codex role through its supported hcom hook. Preserve real role/instance/session identity, readiness, recipient and reply link. | A system launch notice or a stale idle event alone cannot satisfy the delivery predicate. |
| Teams / Claude | After the owner installs a scoped native instruction block based on the vendor criteria, give the coordinator independent competing hypotheses with read-only peer ownership. Require named peers, actual peer-to-peer native communication and returned findings accepted by the owning coordinator; retain shared task claiming/dependencies when that native surface is available. | A task with one serial work stream should stay with one agent; a lead-only team configuration or parallel workers without native peer coordination cannot prove team collaboration. |
| Teams / Codex | Native Claude teams are not a Codex interface. A Codex lane can communicate with a Claude owning team through hcom; count that as transport, not native Codex team adoption. | Codex collaboration-tool activity cannot be relabelled as Claude team usage. |
| Workflows / Claude | After the owner reconciles the local automatic-route setting, give a fresh coordinator a multi-stage task whose later stage depends on prior evidence. Observe a native workflow with its owner, dependency stages, agent metadata and completion/recovery artifact. | A saved script, configured switch, journal mtime or an explicit `/workflow` request alone cannot prove fresh organic selection and successful staged execution. |
| Workflows / Codex | A Codex lane hands the staged outcome to the owning Claude coordinator through hcom; attribute native graph execution to Claude and transport to Codex/hcom. A Codex node would require its own adapter source and acceptance binding before being claimed. | A Codex subagent run cannot be relabelled as native Claude workflow execution. |
| AO / Codex | After a usable approved route and exact config ACK, let the PR-feedback owner assign one fresh isolated worker an outcome at a verified PR head. The native observer forwards a real authorized CI/review opportunity; a native worker returns a nonempty bounded proposal. | A disabled-forwarding policy must suppress the same opportunity. Check native sandbox before task, count escalation requests/denials, and stop/inverse on quota or budget failure. No merge/push is granted by this record. |
| AO / Claude | If that harness is selected by its owner, repeat the native observer-to-worker task with the vendor Claude adapter and its native account/configuration. | Codex sandbox/observer history does not qualify Claude authentication, permissions, delivery or model execution. |

For KEEP/WIRE invocation rates, the CC/co-op must supply native per-role
measurement alongside the existing MCP count of record. Do not infer zero from
an omitted series or count journal updates as successful model calls.

## Workflow measures and gates

The existing baseline belongs to codex-token-parity:
`research/token-efficiency-20261008/WORKFLOW-BASELINE-20261008.json` in private
research state. This record creates no replacement baseline and reports no
measured workflow improvement. Re-measure after owner-approved wiring against
the same definitions: uncached input/turn and cache-read share, rebuild events,
subagent first-request uncached tokens, defects caught before cue by the
required pre-cue tool and upstream J8 review, ready-to-landed PR time, daily
minimum Windows available memory, and invocation rate by owning role. Count
cumulative/provider/cache counters once and preserve missing values.

Final G5 catalog row/revision bindings remain pending its landing. The latest
observed closure check is `rc=2`; no current G5 row is invented. The final
record must bind each layer's actual landed row before a cue. The co-op also
must schedule both designated reads and provide the exact pre-cue tool. CI,
those reads, the pre-cue result, owner routing decisions and the CC cue remain
required. A draft PR or a passing publication validator closes none of them.

Completeness review must check owning-role attribution, fresh/explicit trigger
separation, both clients, native observer inverse and metadata-versus-execution
limits. Source review and retained fixtures are not a new live model run.
