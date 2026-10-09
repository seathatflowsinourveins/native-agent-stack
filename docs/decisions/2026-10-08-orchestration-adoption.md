# Orchestration adoption on this host — 2026-10-08, revised 2026-10-09

The current outcome is **DEFER for each of the four tools** while final-candidate
G5 quality bindings and organic owning-role evidence remain open. Each tool
has four stages: final candidate, wiring, fresh-session evidence and invoke
measurement. Upstream quality decides selection; today's invocation counts
are stage-4 baseline only. A final candidate with low use advances to WIRE;
KEEP requires organic use in stage 3 or 4. Low use is not a retirement reason.

This foundation record supports recoverable coordination of engineering and
research workers used for US-equities research and historical simulation. It
qualifies no strategy or broker operation. The base is
`aba02ec3456d383bcc2fc72883db098f9be7918a`; both designated reads examined
`021e1a875d13cdd713856784b4dbc3dec86acd88`. The subsequent CC and GPT delta
reads examined `0ad947f6fd5023b2a21eadae2837349d4b313886`; their full artifact
hashes are bound in `review_sources.cc_delta` and `review_sources.gpt_delta`.
This revision carries both reads and changes records only. The CC cues landing
through 5f after the required checks and both new-head micro reads.

The [decision JSON](2026-10-08-orchestration-adoption.json) binds the measurements
to each decision. The [native evidence receipt](2026-10-08-orchestration-native-evidence.json),
SHA256 `8a27c364b4a2a84e6fbfaa397461a3aab08c2a87bd08256947c740312ea835cb`,
retains fixed-window hcom results, selection SQL, attribution rules, source pins
and installed Claude source selectors.

## Measurement sources and denominators

Every count below refers to the indicated frozen file and its SHA256.
`coordination/` and `research/` locators resolve under the state root
`~/.local/state/native-agent-stack`; `docs/` locators resolve in this
repository checkout. The JSON and native receipt also declare that root.

The exact [CC frozen snapshot](extra/adoption-cc-2ebc30ce3527d025.json) is
retained in this PR: 60,603 bytes, SHA256
`2ebc30ce3527d025dad39d65293d3020620192c4f0d2987cf3988461254836a0`.
It maps to `measurements.cc_read_snapshot` and the new-head review packet's
`extra/adoption-cc-2ebc30ce3527d025.json`. Its denominators and comparison counts
are unchanged. The other frozen files remain at the named state locators.

| Source | Capture and population | SHA256 |
| --- | --- | --- |
| `coordination/ns2604-coop/notes/adoption-evidence-20261008/adoption-now-5de97cf238b3d28a.json` | Historical 24 h ending 2026-10-08T23:42:51Z; 63 Claude sessions, 841 Codex conversations | `5de97cf238b3d28aa9f7d5110a05857204a847b0c75cda8971de8e142e362e36` |
| `coordination/command-center/pages/adoption-cc-20261009T0008Z.json` | CC read snapshot, 24 h ending 2026-10-09T00:08:43Z; 69 Claude sessions, 844 Codex conversations | `2ebc30ce3527d025dad39d65293d3020620192c4f0d2987cf3988461254836a0` |
| `coordination/ns2604-coop/notes/adoption-evidence-20261008/adoption-now-8682d1d326f29798.json` | Hourly snapshot, 24 h ending 2026-10-09T00:31:25Z; 70 Claude sessions, 850 Codex conversations | `8682d1d326f2979802efa32d156d9db14dba3ce04273328b6b48a0e227533ac7` |
| `coordination/ns2604-coop/notes/adoption-evidence-20261008/adoption-now-e129759fe91ffbb1.json` | SDK-inclusive hourly snapshot, 24 h ending 2026-10-09T01:39:38Z; 79 Claude sessions, 931 Codex/SDK conversations | `e129759fe91ffbb133de2719a7d5194fe96ac65c44b222adf7fdd4d65af0e872` |

The historical 5de97cf2 producer, SHA256
`10784aa8862eaed3a5e0520ecdb2eb58cdf0277f4bab62f8868a86b703954408`,
defined seven MCP groups and omitted native orchestration. UNMEASURED was
correct for those bytes. The later snapshots add client-native tool-result
counts; the old omission is not their present coverage.

The current reviewed CC-owned producer is
`coordination/command-center/cc-tools/adoption_invoke.py`, SHA256
`efff86d46ee7b76d1634d067a5c53126a0120294bbf38372f4318677d556a2a9`.
A frozen copy is named in the decision JSON. It postdates the two native
snapshots, whose files do not embed a producer hash; that current hash is not
assigned as their generating revision. Its SDK extension labels
`codex_sdk_ts` and `codex-app-server` as `sdk:<service>:<lane>`.
The new e129759f hourly source now supplies the SDK-inclusive counters.
This lane neither runs nor edits the producer.

### Claude native counters by role

Cells show **CC read snapshot → later hourly snapshot**, in that order.
Each named owning role has one observed session in each snapshot. The other
Claude bucket changes from 65 to 66. Zero means no matching aggregate emitted
for that measured role/tool; it does not describe use outside the captured
scope. The CC name is bound by
[the composition record](2026-10-06-cc-orchestration-composition.md), line 3.

| Role | Observed sessions | Agent | SendMessage | Monitor | Workflow |
| --- | ---: | ---: | ---: | ---: | ---: |
| CC / wsl-architecture-design | 1 → 1 | 57 → 59 | 311 → 319 | 150 → 149 | 11 → 11 |
| co-op / ns2604-coop | 1 → 1 | 8 → 8 | 248 → 252 | 61 → 64 | 0 → 0 |
| api-actions | 1 → 1 | 4 → 4 | 38 → 41 | 0 → 0 | 0 → 0 |
| native-agent-stack-1a | 1 → 1 | 0 → 0 | 11 → 12 | 1 → 2 | 1 → 1 |
| other Claude sessions | 65 → 66 | 21 → 21 | 0 → 0 | 0 → 0 | 0 → 0 |

The co-op also has CronCreate 24, CronDelete 11 and CronList 6 in each file.
These are event counts, not eligible fresh-task denominators. Agent includes
ordinary subagents; SendMessage includes cross-session messages. Neither is a
named-team-only count. Workflow is native invocation evidence; tool results
alone do not classify organic triggers, successful stages or accepted output.
Monitor counts monitoring operations, rather than completed orchestration.

For Codex, the two files respectively report spawn_agent **589 → 587**,
send_message **7,247 → 7,219**, followup_task **1,078 → 1,075**. These are
separate counters: collaboration is not spawning. In 8682d1d3 the current
`kiri` label has two observed conversations, spawn_agent 1, send_message 12 and
followup_task 1. Current role labels and retained telemetry limit attribution.
A shifted 24-hour window can reduce a count. Never sum these snapshots or
equate their populations with eligible fresh owning sessions.

The latest e129759f snapshot has these separately bound baselines; every named
role still has one observed session, and the other-Claude bucket has 75.

| Role | Agent | SendMessage | Monitor | Workflow |
| --- | ---: | ---: | ---: | ---: |
| CC / wsl-architecture-design | 58 | 356 | 147 | 11 |
| co-op / ns2604-coop | 8 | 281 | 76 | 0 |
| api-actions | 4 | 54 | 0 | 0 |
| native-agent-stack-1a | 0 | 17 | 5 | 2 |
| other Claude sessions | 30 | 0 | 0 | 0 |

Its non-SDK Codex totals are spawn_agent 574, send_message 7,060 and
followup_task 1,032. The `kiri` label has three observed conversations and
2/23/4 respectively. The separate `sdk:codex_sdk_ts:unlabelled` population has
80 conversations with tool results and 165 native orchestration results:
spawn_agent 53, send_message 54, followup_task 9, list_agents 11, wait_agent 38.
This SDK bucket has no identified owning role. Native service counts are not
organic adoption or model-success proof, and are not added to earlier snapshots.
No labelled codex-app-server aggregate was emitted in this file; broader use
outside capture is unknown. The hcom read below retains its earlier fixed
window rather than being relabelled with this later end time.

### hcom's native 24-hour role counts

The native receipt uses the same 24-hour interval as 8682d1d3:
`[2026-10-08T00:31:25Z, 2026-10-09T00:31:25Z)`. A read-only, query-only SQLite
transaction fixed high event ID 65430. The window contains 29,791 events:
410 lifecycle, 27,150 status and 2,231 messages. There are 135 ready,
0 launch_failed, 2 launch_blocked, 136 stopped and 119 stopped records with
reason `killed`. All 34 native tool/tag role rows are in the receipt.

| Selected target role | Ready | Launch failed | Launch blocked | Stopped | Killed reason | Messages sent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| codex:orch-records | 5 | 0 | 0 | 5 | 5 | 66 |
| codex:sdk-harness-ready | 3 | 0 | 1 | 2 | 1 | 39 |
| codex:overlap-token | 7 | 0 | 0 | 7 | 6 | 36 |
| claude:github-ci-finalize-read | 3 | 0 | 0 | 3 | 3 | 11 |
| claude:fixwave-mcp | 1 | 0 | 0 | 1 | 1 | 2 |

Ready/failure attribution uses the recorded batch and exact target membership.
Stopped attribution uses its native snapshot. Sender/status attribution uses
native creation/session/stop lifespans, not short names or a current-only list.
All 147 overlapping lifespans have matching native batch labels with no
missing/conflicting labels. Unrecorded intermediate tag changes remain unknown.

**Target use does not establish the co-op's initiating-role rate.** Initiators
remain unknown for 129/135 ready and 131/136 stopped records. Delivery/reply
metadata is not recipient-role acceptance or timing. A `killed` record can
include already-dead/untracked cleanup; it is not independent PID/tab/worktree
inverse proof. The coordinator reproduced native totals and every role's
stopped/killed aggregate. Later delivery metadata/current rows can change a
live projection digest. No archive recovery, model success or organic trigger
is inferred from this read.

The `delivered_metadata` predicate counts a present/non-null stored
`msg_delivered_to` field, including serialized empty lists `[]`. Its 2,096
message rows are stored metadata; the CC delta read reports 1,612 rows with a
recipient. Neither value proves delivery timing or recipient-role acceptance.
The 2,139 stored recipient members are a sum of list members, not distinct
delivered messages. These definitions are also recorded in the native receipt;
the frozen aggregates remain unchanged.

## Four stages per tool

| Layer | Outcome and owning job | Stage-4 baseline | Remaining stage-1/3 evidence |
| --- | --- | --- | --- |
| hcom | **DEFER** — co-op lane launch and cross-session transport | Native fixed-window role table and narrower hook/transport point evidence | G5 quality row; natural fresh owning-role task, actual client/hook/readiness, delivered request and causal reply |
| Claude agent teams | **DEFER** — CC/co-op named peers, separate contexts, native peer communication and lead synthesis | Agent/SendMessage proxies in both frozen native snapshots | G5 quality row; owner-gated role scoping and fresh named-peer communication/accepted findings |
| Claude workflows | **DEFER** — CC/co-op staged native dependency graph and same-session recovery; API-actions separately scoped | CC Workflow 11 in all three native snapshots; native-agent-stack-1a 1 in 2ebc/8682, 2 in e129 | G5 quality row; requested/available/active session state and fresh natural graph selection/completion/recovery |
| agent-orchestrator | **DEFER** — PR-feedback owner's durable SCM-to-worker route; 5f owns landing | Pinned synthetic/native-observation/quota/inverse receipts; full live invocation rate UNMEASURED | G5 quality row; approved route/config/head, native feedback/proposal, sandbox/denial and inverse proof |

### Stage 1 — final candidate and upstream quality

Each catalog row/path/id/revision is PENDING until G5 lands. Available quality
inputs are the pinned vendor sources/releases below and, for AO, the earlier
scoped comparison and fixture receipts. No matched quality winner is newly
established here. G5's maintained-source, release, published benchmark,
code-quality and head-to-head evidence where present must decide final
candidacy. Today's counts and installation status are not selection inputs.
No better-evidenced same-job replacement is named without that adjudication.

Each slot has one pending `current_choice`; installed candidates are not a
clean final default list yet. The catalog owner supplies the final ranking.

| Role slot | Installed candidate | Overlap disposition before G5 adjudication |
| --- | --- | --- |
| co-op cross-client lane lifecycle/transport | hcom | Claude cross-session messaging and AO-owned lifecycle are alternatives for their narrower overlapping scope, not parallel defaults |
| Claude coordinator peer exploration/synthesis | agent teams | Ordinary native subagents, cross-session messaging and workflow fan-out are alternatives; current native baseline already covers narrower independent work |
| Claude coordinator dependency graph/recovery | workflows | Subagents/teams and Dagu command DAGs overlap parts of the job; alternative ranking pending, no parallel default |
| PR-feedback owner SCM-to-worker delivery | agent-orchestrator | Existing co-op/5f GitHub loop and manual native relay/workflows are alternatives; 5f remains sole landing owner |

These entries are source review and scoped retained evidence, checked
2026-10-09; they do not establish matched comparative winners. A landed
quality adjudication or material release/capability correction can overturn
them. The catalog owner's proposed revisit path is daily catalog-freshness and
saturation-ledger reopen triggers, including its index and
`docs/g5-refresh-procedure.md`; this procedure is **pending #878 landing**.
Invoke volume cannot change the quality rank.

### Stage 2 — clean native install, per-client integration and inverse

Commands below are supported recipes, not installs performed by this revision.
Source pins are in the next section and each JSON wiring stage. Existing
version/status observations do not replace a clean installation receipt.

| Tool | Clean native command/pin | Integration by client | Inverse and current evidence |
| --- | --- | --- | --- |
| hcom | Vendor release installer: `curl -fsSL https://github.com/aannoo/hcom/releases/download/v0.7.28/hcom-installer.sh \| sh`; installer SHA256 `75c1560785799881c265ae02ccb247bc6f0742835d716452f7d82071fe8bd638` | Claude/Codex vendor per-run hooks and injected instructions; no substitute task-prompt routing | `hcom kill <owned-lane>` plus independent process/tab/writer-lock exit; co-op owns worktree cleanup. Fresh inverse and selected installation-withdrawal recipe remain pending; killed metadata alone does not pass |
| Claude agent teams | `claude install 2.1.295`; installed build/content pins below, native install help confirms version target | User-scope `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` currently loads implicit teams in every Claude session. Approved-plan peer selection/coordination is shipped; CC/co-op role scoping is pending and owner-gated. Codex uses a separately attributed hcom handoff | Owner requests native peer stop and verifies acknowledgement/exit/cleanup. For the proposed role-scoping change, remove added role overrides and restore the original user-scope teams variable to `1`. Fresh task and role-scope inverses remain pending |
| Claude workflows | Same unchanged native Claude install; no separate workflow package | User-scope `enableWorkflows=true` currently loads workflows in every Claude session. Role scoping is pending and owner-gated; Ultracode session `--settings`/`apply_flag_settings`, requested/available/active and model availability are separate | For proposed role scoping, remove added role overrides and restore the original user-scope `enableWorkflows=true`. Restore per-task Ultracode flags separately, cancel own nodes and verify completion/exit. Fresh inverse pending |
| agent-orchestrator | Pinned v0.13.5 Linux x64 AppImage, verified native extraction and local `--bundle` recipe below; pinned c95ae361 installer SHA256 `463366604181029d8cdb16cbc1a5d8771eaf4bc498594b09759a5b42b79bee7d` | Codex native config/feedback with isolated account, home and sandbox; Claude adapter separately owner-selected and qualified | Stop the owned user service, then owned `ao stop --timeout 10s --json`, independent own-container exit/removal/import withdrawal; old native-stop137 and Docker0 outcomes remain distinct. No fresh deployment |

The AO payload is the upstream [v0.13.5 Linux x64 AppImage](https://github.com/OrchestratorInc/agent-orchestrator/releases/download/v0.13.5/agent-orchestrator-linux-x64.AppImage),
asset ID `621487952`, SHA256
`5f4262c1b5fad5e63c0b1291d5a2e4c878c953496f5ca430edfe4c061987bf28`.
The [release metadata](https://api.github.com/repos/OrchestratorInc/agent-orchestrator/releases/tags/v0.13.5)
was checked 2026-10-09: target c95ae361 and the asset digest match; the release
reports `immutable=false`, so the checksum must be enforced. This digest
belongs to the AppImage, not to a `resources/` tar archive.

The pinned [vendor installer](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/scripts/setup-self-hosted.sh#L90-L107)
supports `--bundle` and validates a gzip tar rooted at `resources/`; its local
bundle branch does not verify a checksum. Its default stable branch selects
`/releases/latest` and cannot pin this payload. The recipe below uses the
vendor's [native extraction and resource discovery](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/scripts/setup-self-hosted.sh#L141-L170)
to prepare unchanged resources for that supported interface. It applies to
Linux x86_64 and has not been executed by this revision.

The owner supplies absolute paths for the pinned installer, exact AppImage,
empty owned extraction directory, output bundle, install prefix, data root and
run file through the seven `AO_PIN_*` variables below. A failed checksum stops
the recipe. The derived archive's separate checksum is retained before the
owner installation; its digest is pending because no archive is created here.
The AppImage checksum pins the upstream payload before archive preparation.

```bash
set -eu
printf '%s  %s\n' \
  463366604181029d8cdb16cbc1a5d8771eaf4bc498594b09759a5b42b79bee7d \
  "$AO_PIN_INSTALLER" | sha256sum -c -
printf '%s  %s\n' \
  5f4262c1b5fad5e63c0b1291d5a2e4c878c953496f5ca430edfe4c061987bf28 \
  "$AO_PIN_APPIMAGE" | sha256sum -c -
test -d "$AO_PIN_STAGE"
test -z "$(ls -A "$AO_PIN_STAGE")"
chmod +x "$AO_PIN_APPIMAGE"
(cd "$AO_PIN_STAGE"; "$AO_PIN_APPIMAGE" --appimage-extract >/dev/null)
AO_PIN_DAEMON="$(find "$AO_PIN_STAGE" -path '*/resources/daemon/ao' -type f -print -quit)"
test -n "$AO_PIN_DAEMON"
AO_PIN_RESOURCES="$(dirname "$(dirname "$AO_PIN_DAEMON")")"
tar -czf "$AO_PIN_BUNDLE" -C "$(dirname "$AO_PIN_RESOURCES")" resources
sha256sum "$AO_PIN_BUNDLE" > "$AO_PIN_BUNDLE.sha256"
sha256sum -c "$AO_PIN_BUNDLE.sha256"
AO_HOST_INSTALL_DIR="$AO_PIN_PREFIX" AO_DATA_DIR="$AO_PIN_DATA" \
  AO_RUN_FILE="$AO_PIN_RUN_FILE" \
  bash "$AO_PIN_INSTALLER" --bundle "$AO_PIN_BUNDLE" --install-only
```

The memory gate uses `smaps_rollup` PSS, not binary size or RSS. At
2026-10-09T01:48:37.106663Z, native session metadata identified these live
Claude parent processes and procfs confirmed their executable identity.
The receipt retains each rollup digest and scope.

| Native parent role | Observed PSS (kB) | Coverage |
| --- | ---: | --- |
| CC / wsl-architecture-design | 582,073 | Parent process only |
| co-op / ns2604-coop | 577,507 | Parent process only |
| api-actions | 515,465 | Parent process only |
| native-agent-stack-1a | 534,463 | Parent process only |

These are common client costs, not incremental team/workflow costs or complete
peer/MCP trees. Do not assign or sum them once per native feature. Isolated
hcom hook/runner PSS, team/graph incremental/peer PSS and live AO daemon/worker
PSS remain unknown. Those missing component figures keep ADOPT-NOW blocked.

For context only, the per-role MCP trial report
`research/coverage-gap-20261008/O3/ROLE-MCP-TRIAL-PLAN-20261008/ROLE-MCP-TRIAL-REPORT-20261009.md`,
SHA256 `f0afc2c734b3ad1b70e68cd38d3c844c7f4b1338cc030c8fc40fc88db1e53989`,
reports whole owned-lane after-task PSS: A 1,431,973 kB, B structural scout
674,966 kB, B supplied artifact 837,623 kB and C 947,334 kB. These were
different tasks/one run each; they are neither per-tool orchestration PSS nor
matched memory savings. The figures are retained in their own scope.

The native hcom event store is shared while CLI/hooks run per use; no separate
HTTP MCP server is proposed. Teams/workflows use owning Claude sessions and
shared installed code pages, not a separately qualified shared MCP daemon.
AO documents a local HTTP daemon serving owned sessions; its daemon/worker
cost split still needs measurement and is not a claimed MCP transport.
**Teams and workflows are currently active host-wide.** The CC verified
user-scope `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` at
`~/.claude/settings.json:35` and `enableWorkflows=true` at `:535`, as recorded
in its delta read (SHA256
`69119fd821ddab7fda786a8b374ccfa89db43aa43cd81edb49b9fd5714860357`).
The pinned CHANGELOG section 2.1.178 describes one implicit team per enabled
session; dispositions rows[17] and rows[123] agree, as checked by the CC.
This lane neither reads nor edits client configuration.

Role-scoped loading is **pending and owner-gated**. The proposed change moves
the teams flag from user scope to approved CC/co-op launches only; API-actions
is outside Teams' owning scope. Workflow enablement would likewise move from
user scope to approved CC/co-op launches and separately approved API-actions
workflow use. The exact supported launch recipes and fresh scope checks remain
pending. Each JSON wiring stage records the inverse: remove added role launch
overrides and restore the original user-scope activation. Native interfaces
have no MCP `alwaysLoad` setting; any later selected MCP exposure must use
per-role sets and `alwaysLoad: false` where supported.

### Stage 3 — natural fresh owning-role evidence

All four tools remain PENDING here. The named tests below and in each JSON
stage require a natural task with no orchestration names in its input,
actual owning role/client/session creation, native route choice, useful accepted
work, counter evidence and scoped inverse. Source templates, generic native
tool calls and transport receipts do not close this stage.

### Stage 4 — invocation baseline and re-measurement

The separately hashed tables above provide today's baseline by observed role.
The 2026-10-08 MCP-only file supplies the historical baseline; its missing
native series was UNMEASURED, so a numerical increase from zero is not valid.
Native hcom target events are now measured, its initiating-owner organic use
remains unknown, and AO's complete live rate remains UNMEASURED. A later
matched snapshot after wiring must retain the same counter/role scope and
fresh natural-task evidence. Generic counts do not authorize KEEP or select
the final candidate.

Transport request 63840 and causal reply 63854 establish narrower delivered
point evidence. Their original selection trigger is unknown. Readiness and
hook binding for the fresh orch-records launch do not by themselves meet the
owning-role organic criterion. The previous KEEP wording is withdrawn under
the four-stage ruling; hcom remains DEFER until the required gates establish
its final-candidate and adoption outcome.

Ordinary native subagents and Claude cross-session messaging remain candidate
classes for narrower tasks. These job boundaries do not prove exclusive
capability or a quality/cost winner. No layer is retired because an aggregate
omits it.

## Pinned vendor instructions and session scope

hcom source is [aannoo/hcom v0.7.28](https://github.com/aannoo/hcom/tree/b2a7c192003e7fd67ed93265289e4ac36276f965),
`b2a7c192003e7fd67ed93265289e4ac36276f965`: `README.md`, `src/db/events.rs`,
`src/hooks/common.rs`, `src/commands/kill.rs` and `src/hooks/codex.rs`.
This canonical list matches the decision JSON and native receipt. The receipt's
hashed `sources` subset is the three measurement-semantic files: events,
common hooks and kill; interface sources are not claimed as extra measured files.
Its per-run native hooks remain the supported launch/transport route.

The installed Claude executable `versions/2.1.295`, build `07e8f67ea328`,
is pinned by full-file SHA256
`4503bfe11a6c7fcc1e0b39b5e0d347c04248f750b03b0977b3ad6b531fe6f358`.
Source ranges below are zero-based bytes, end-exclusive, hashed before
interpolation; full selectors and independent span checks are in the receipt.

| Shipped source | Byte range | Content SHA256 |
| --- | --- | --- |
| Approved-plan named-peer selection helper | 222621541–222621762 | `ce55db19fe73e044b9032af59cc569b0f350e3d2eb736246a078a8abc24f8a5b` |
| Team Coordination reminder | 219305232–219306000 | `63f06d2e02c1e0cfb096b2e252616753c63108dcda0e749ee0d37bf58f7cbd73` |
| TeammateIdle input schema | 207519342–207519578 | `3f5e1954b4af338efcc38141c0d3e66c3c92d318d9e49d634b9f1b619842b199` |
| TaskCreated input schema | 207519578–207519896 | `3c01d5747a5cdb55df2bacd341b96e8d4411fefc92c40f1d51ae821ddfd60e8c` |
| Ultracode session schema | 208317678–208318041 | `40e7f6683e96ac4dfcf30753566cd4933267dd4d3187810eecc3bcfbd4086a9e` |

The vendor selection text, resolving its pinned Agent-name interpolation, is:

> If this plan can be broken down into multiple independent tasks, consider spawning named teammates with the Agent tool (pass a `name`) to parallelize the work.

It is appended to an approved-plan result only when its native flag and
`lF()==="default"` guard hold. This is a shipped conditional routing instruction
for the intended CC/co-op scope, not an unconditional startup router or an
invented packaged skill. Host-wide feature activation is recorded above;
natural selection by a fresh owning-role task remains pending.
The coordinator verified the selection and coordination source bytes. The
teammate reminder supplies native lead/peer communication instructions.

TeammateIdle and TaskCreated are declared input schemas, not evidence of hook
execution or a peer-spawn mechanism. Selected settings have no such configured
hooks. This scope does not adopt shared task claiming/dependencies:
`claude:env:CLAUDE_CODE_ENABLE_TODO_TOOLS` remains declined in
`catalogs/foundation/upstream-surface-dispositions.json`, SHA256
`2c9847e1460661e953d59add75e82808c9e2ea33e46fc0fc67c4c375f38187f3`.
The task-list addition is conditional; flag absence alone is not universal
model/account unavailability proof.

**Ultracode's declared contract is session-scoped.** Supported `--settings`
or `apply_flag_settings` control requests can request it; interactive toggles
do not persist it. Workflows and a supporting model must be available. Native
state distinguishes `ultracodeRequested`, `ultracodeAvailable` and active
`ultracode`. Previously observed project=true/local=false file values are
configuration observations; they do not prove actual session suppression or a
persistent route. The earlier inference is withdrawn. Dispositions row 188's
broader carrier wording is flagged to its catalog owner, with this native pin,
rather than edited in this record.

Public release [anthropics/claude-code v2.1.295](https://github.com/anthropics/claude-code/tree/602df92bf481ed904533e95c09f740f40aab5aed),
`602df92bf481ed904533e95c09f740f40aab5aed`, pins `CHANGELOG.md`.
Section 2.1.178 removed TeamCreate/TeamDelete; enabled sessions use implicit
teams and named Agent peers. Public source commit, installed build and mutable
vendor documentation have separate evidence scopes.

Original journal total 131 and the .941942Z mtime are withdrawn as adoption
support: their aggregation was not reproducible across mutable project state.
The frozen native Workflow counters replace that proxy. No journal count,
mtime or saved example is promoted into completed workflow/model acceptance.

## AO extends the earlier bounded record

This [v0.13.5 source/staged-evidence extension](https://github.com/OrchestratorInc/agent-orchestrator/tree/c95ae361eee48d33c2f443c6d2fe69c445f548a8),
`c95ae361eee48d33c2f443c6d2fe69c445f548a8`, extends
[the earlier AO adoption record](2026-10-08-ao-adoption.md), SHA256
`7369ff144bff56f19cecfd16a60034d138ff55f1d86f287ae2f0c8f7327a5862`.
It supersedes that record's old latest-release wording, not its historical
v0.13.4 `e8a77577c14b015b947057d67c9171a78cdd5099` evidence or owner bounds.
0134 outcomes do not qualify 0135 coding, restart or changed-head behavior.

The earlier outer ceiling is three sessions through 2026-10-14T03:28Z,
on small PRs only.
This staged case is narrower: one isolated observe/propose worker. Approved
native sign-in, an owned container/writable home, prohibition on shared worker
home, one poller per AO-owned PR and the dated 30-second exception remain.
The CC-supplied deployment guard reads `gh api rate_limit` and runs native
`ao stop` when REST-core remaining falls below 500. This is a deployment
control, not tested daemon enforcement or a running guard in this record.
Separate GraphQL allowance/consumption observation remains; no new GraphQL
threshold is invented. R9/config/route/owner gates and
5f landing on the CC cue remain. Deployment stays owner-controlled and the
quota pause is retained.

Native `version` returns `dev`; release provenance is a separate pin. Retained
receipt SHA256
`51ba6ac9088ad19d0dbf236257f5e9523341609987ff5a8257464a72400f9481`
reports sandbox/PR observation passed, three quota-failed proposal turns and
zero successful proposals/native tools. Usage and poll counts remain unknown.
Its native `ao stop` returned **137**; Docker stop and removal each returned
**0**, and independent state was exited/Running=false/Pid=0/ExitCode=0.
Container/import withdrawal completed. A successful standalone native-stop
command is not claimed.

Vendor sources are `docs/scm-observer.md`, `docs/cli/README.md`, typed
`backend/internal/domain/projectconfig.go` and generated OpenAPI. Native
project/role rules and CI/review policies supply the route. `claim-pr` does
not check out or verify a head; whole-object `set-config` is not a partial
patch. Access logger `backend/internal/httpd/log.go` can count spawnSession
POST admission by response class; observer diagnostics and
`backend/internal/lifecycle/reactions.go` do not provide a complete successful
poll/delivery census. These proposed measures remain unimplemented. Default
feedback text does not expand the owner's authorized worker actions.

## Named fresh-session tests

These are pending acceptance tasks, not runs by this revision. Input states a
normal outcome, scope and acceptance, with no orchestration tool names. Retain
fresh owner/client/session identity, task selection, native source/config,
returned work, counter scope and inverse. Explicit forced invocations remain
separate. Each decision also carries its own named tests in the JSON.

| Test/client | Required native proof | Control |
| --- | --- | --- |
| HCOM-CLAUDE-NATURAL-OWNER | Owning fresh co-op task naturally selects an owned lane; bind hook, readiness, delivered request and causal reply | Sender exit0/system notice without recipient/reply fails |
| HCOM-CODEX-NATURAL-OWNER | Same natural coordination outcome in fresh owning Codex role, with actual role/client/task-selection evidence | Stale readiness or missing native hook/delivery fails |
| TEAMS-CLAUDE-NATURAL-PEERS | Owner-authorized shipped route selects named peers; actual peer-to-peer communication and accepted findings | Lead-only config or ordinary subagents without native peer coordination fails |
| TEAMS-CODEX-CLAUDE-HANDOFF | Native collaboration attributed to owning Claude coordinator; Codex/hcom handoff separately bound | Codex collaboration is not native Claude teams |
| WORKFLOW-CLAUDE-SESSION-NATURAL | Requested/available/active session state, fresh native graph stages, accepted output and recovery | Saved script, file flag, mtime or forced invocation alone fails |
| WORKFLOW-CODEX-CLAUDE-HANDOFF | Codex/hcom handoff bound to owning Claude graph; a Codex node needs separate adapter acceptance | Codex subagents alone do not prove Claude workflow execution |
| AO-CODEX-NATIVE-PR-FEEDBACK | After approved usable route/config ACK: one verified head, native feedback/proposal, pre-task sandbox, denial counts and inverse | Disabled-forwarding control; stop/inverse on quota/budget failure |
| AO-CLAUDE-NATIVE-PR-FEEDBACK | If owner selects it, independently qualify Claude account/config/permissions, native delivery/proposal and inverse | Codex/synthetic receipts do not qualify Claude |

## Checks, correction custody and gates

The original 14+10 targeted module runs read neither changed document. They
are unrelated regression checks, not document acceptance. Publication
validation checks integrity/private-content scope; JSON parsing and direct
source/counter comparisons check their stated properties, not empirical
adoption. No new model qualification, exporter or test runner is created.

Both original designated reads requested changes. Their per-role/source/organic
findings converge; they are not double-counted as distinct defects. The old
head's pre-cue result was rc0 with zero modified existing test files; it is not
a new-head result. J8 was skipped for records-only in the co-op's packet, not
reported as a reviewer pass. The new head requires its own checks and both
delta reads, then the CC cue and 5f landing.

G5 row/path/id/revision remains explicitly pending for every decision. The
catalog owner receives the session-scope correction rather than a hot-file
edit. The existing workflow baseline remains with codex-token-parity at
`research/token-efficiency-20261008/WORKFLOW-BASELINE-20261008.json`.
No measured workflow improvement is claimed. After owner-approved wiring,
reuse the same definitions for uncached input/cache share, rebuild events,
first child input, pre-cue/J8 defects, PR cycle time, Windows memory minimum
and per-role native invocation counters. Unknown usage remains unknown.

Completeness review retains ordinary subagents/native cross-session messaging,
per-client attribution, conditional source versus execution, live counter
coverage, session activation and independent inverse as open comparison/test
boundaries. The optional public-doc HTTP403 probe and recovered local source
query/tool-schema failures are retained separately from successful evidence.
