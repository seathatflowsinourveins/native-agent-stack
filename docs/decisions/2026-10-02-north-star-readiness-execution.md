# North Star foundation readiness execution

Decision date: 2026-10-02. Implementation source:
`a2ad39abd8c6827069395682f50d5058492a0f34` (PR 610), building on the
[two-host architecture](2026-10-02-two-host-north-star-architecture.md) at
`18eea2c1de992b46c266d79ef0cc40f93c9fb943`.
Scope: macOS plus the surviving NativeStack WSL2 destination, supporting
U.S.-equities research, simulation and separate IBKR/Alpaca paper acceptance.
This record reconciles source and readiness dispositions; it performs no host
activation, upgrade, model evaluation or broker operation.

## Selected execution boundary

Use native GPT-6.1 Sol at Ultra for the coordinator and default workers in this
two-host task. Give each worker an objective, exact revision, owned paths,
acceptance command and compact evidence handoff. Astra receives one bounded
question only for a consequential decision, conflicting primary evidence or a
hard failure unresolved by evidence-led Sol diagnosis. Preserve native Claude's
companion policy, native sign-ins, caching, compaction and permission settings.
The task's explicit Sol/Ultra policy supersedes the older general worker Max
default at this scope.

The deterministic offline North Star work can proceed with the existing native
core and frozen project oracles. A complete optional-tool sweep, SDK upgrade,
memory replacement or Pi promotion is not a prerequisite. Required Mac and
NativeStack WSL2 host/model/account/lifecycle acceptance remains unverified until
observed at that destination. The two-host design and source sync do not prove
remote transport, native authentication or workstation execution.

Retain the single shared ai-memory 2.5.2 owner and Ollama 0.34.4 measured control.
Hindsight 0.10.2/coding-agents 0.8.0 remain isolated. Do not activate a second
capture engine or depend on another host's localhost. Use verified project scope
for shared memory; versioned decisions and an outbox provide the fallback where
the supported endpoint is unavailable.

SDK application requests use the existing owner-controlled OmniRoute endpoint
with an explicit provider/endpoint, locked dependencies, bounded deadlines and
task cache/session scope. Disable separate SDK tracing; request no duplicate
gateway memory and safe compression. No silent direct-provider fallback is
selected. Requested compression headers do not prove applied policy or savings.
The gateway source boundary is recorded as base
`52823517533cfceec7abef2ff3e6285a19fe4121` plus upstream PRs 13788 and 15167;
`0585aba5589d5a1f49243a13a8db249558e7c9e3` is a carried PR revision, not an
independently fingerprinted full live-runtime commit. This source reconciliation
does not rebuild, relocate or promote the service.

## Versions and retained evidence

The official release locators below are the dated source review already recorded
in the architecture decision. Observed binaries, accepted pins and current
upstream releases are separate evidence levels. The shared component manifest
remains the pin authority; its owner reconciles official artifact and
compatibility provenance before changing a pin.

| Component | Evidence retained | Execution disposition |
| --- | --- | --- |
| Codex | Mac observed 0.160.0; 0.159.3 remains the older accepted stack pin; [official 0.160.0](https://github.com/openai/codex/releases/tag/rust-v0.160.0) reviewed | Use the observed native installation. Historical 0.159.3 runtime claims retain their original scope; no new-host acceptance is implied. |
| Claude Code | Mac observed 2.1.287; 2.1.284 remains the older accepted stack pin; [official 2.1.287](https://github.com/anthropics/claude-code/releases/tag/v2.1.287) reviewed | Retain native companion policy. Version observation does not establish an upgraded runtime's complete lifecycle. |
| Agents SDK / OpenAI Python | Accepted scoped OmniRoute protocol check: 0.22.3 / 3.23.0, 27/27; upstream [0.23.1](https://github.com/openai/openai-agents-python/releases/tag/v0.23.1) / [3.24.0](https://github.com/openai/openai-python/releases/tag/v3.24.0) reviewed | Preserve the accepted application lock until an affected application needs a qualified update. Native Ultra is not an API reasoning enum. Earlier nonstream and stream timeouts remain failures. |
| Shared memory / local inference | Retained official ai-memory 2.5.2 / Ollama 0.34.4 control | Preserve the current owner and corpus. Private API and explicit-read/compact/resume receipts do not close representative native lifecycle, quality or settlement gates. |
| Pi | Historical 0.99.1 trial; upstream [earendil-works/pi 1.0.0](https://github.com/earendil-works/pi/releases/tag/v1.0.0) reviewed | Optional unpromoted trial. The new package `@earendil-works/pi-coding-agent` requires Node >=22.19.0. SDK extension binding, provider authentication, cancellation and resume need affected acceptance before activation. |

The [Pi package and SDK contract](https://github.com/earendil-works/pi/blob/v1.0.0/packages/coding-agent/package.json)
and the architecture decision retain the package migration, SDK/RPC distinction
and extension-loading limits. Pi's historical fixture runs do not accept 1.0.0;
confounded cache comparisons and higher token use supply no savings conclusion.
Official artifacts, pinned versions/digests and rollback paths are prerequisites
for any later installation or update.

## All twenty layers remain in scope

The [foundation manifest](../../catalogs/foundation/manifest.json) retains exactly
these layer IDs: `native-clients`, `instructions-skills`, `workers`, `isolation`,
`code-navigation`, `document-retrieval`, `semantic-rag`, `durable-memory`,
`web-research`, `token-efficiency`, `quality-evaluation`, `ci-supply-chain`,
`scheduling-supervision`, `hosting-services`, `recovery-portability`,
`observation-inference`, `agent-sdks`, `mcp-surfaces`, `secrets-credentials`, and
`git-github-automation`. A layer remains represented when its runtime is optional
or its host activation is incomplete. Catalog inclusion conveys no installation
or operator authority.

## Maintained gate dispositions

The following 21 classes carry the dated owner-ledger snapshot associated with
canonical source `6652b78e272b92d31842b4791a130e4339be8609` and the maintained page
generated 2026-10-02T15:09:45Z. A scoped exact read of
`decisions/production-foundation-20260930.md` generated 2026-10-02T16:05:14Z
reconfirmed the retained selection and open host/lifecycle boundaries. These are
carried records, with original per-gate dates retained in private evidence;
this source edit does not rerun or rewrite the owner ledger. The canonical
[owner thread](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384)
and its linked decision files remain the maintained evidence authority.

“Selected requirement” means acceptance is needed when extending the named
selected operation or host; it does not block unrelated offline implementation.
“Promotion requirement” is needed for a replacement or full-stack quality claim.
“Optional candidate excluded” retains its unresolved status and supplies no
passed gate. Configuration/API verification stays at that evidence level.

| Gate | Class and retained status | Execution disposition and remaining evidence |
| --- | --- | --- |
| G01 | Native Codex RTK interception — verified | Selected requirement. Reuse exact scoped 0.50.0 evidence; preserve the 0.49.0 regression and intentional exit 128. Changed versions/hosts require interception and failure-preservation checks. |
| G02 | Canonical directives and installed catalog coherence — partial | Selected requirement. Guarded source synchronization and native consumption retain their dates. Source copies do not activate host globals or close strict consumption partials. |
| G03 | Maintained decisions after compaction/resume — partial | Selected requirement. Explicit-read/actual-compact/fresh-process/read proof carries six facts on its earlier control. Tool-free recall and representative cross-client continuation remain open. |
| G04 | Bounded native MCP discovery — verified configuration | Selected requirement when using MCP. Verify the actual bounded native call at the intended client/provider; preserve earlier approval-policy denials. |
| G05 | History/as-of and TTL lifecycle — verified API | Selected requirement for those memory operations. Synthetic scoped version/expiry acceptance does not establish native session lifecycle. |
| G06 | Related-link graph lifecycle — verified API | Selected requirement for linked recall. Scoped forward/backlink checks do not close real-corpus reference completeness or native workflow. |
| G07 | Shared handoff/message lifecycle — verified API | Selected requirement for cross-session handoff. Ended-sender/fresh-receiver claim-once API proof is distinct from native next-session consumption. |
| G08 | Cited synthesis and reranking — partial | Selected requirement for synthesis/reranked answers. Preserve synthesis 26/27, invalid JSON, 20s fallback and native shim/latency failures; qualify representative citations and answer quality. |
| G09 | Consolidation/improvement lifecycle — enabled, unverified | Selected requirement before claiming durable native learning. Preserve timeouts, zero accepted proposals, unknown rejection origin/settlement and unproved effective policy; representative review/approval/recovery remains open. |
| G10 | Intended native capture/managed workstream — partial | Selected requirement. Scoped capture and supported failure-event wiring do not prove complete successful/failed-tool delivery, normalized outcomes or managed native continuity. |
| G11 | Capture queue and real-corpus reference backlog — open | Selected requirement for completion claims. Preserve scoped/global counters separately; observe owned completion/errors and resolve references without destructive broad repair. |
| G12 | Safe benchmark ownership and teardown — partial | Promotion requirement. Preserve startup timeouts and later bounded startup observation; owned child reap does not attest escaped descendants or provider settlement. Never run the frozen unsafe benchmark. |
| G13 | Refreshed production C3/C4/D2h quality control — blocked | Promotion requirement. Preregister a surviving host and ownership-safe same-host paired control with frozen statistical gates before comparative claims. |
| G14 | Hindsight neutral comparison and blind promotion — partial | Optional candidate excluded from the selected profile. Private API/health receipts do not supply a neutral current-control comparison or blind cross-family adoption convergence. |
| G15 | Agentmemory full-profile isolation — blocked | Optional candidate excluded. Official supported data, home/environment and process isolation remains required before any candidate trial or promotion. |
| G16 | Ollama 0.35 strict parity/retrieval equivalence — blocked | Optional candidate upgrade excluded. Retain 0.34.4 and the failed predeclared strict gate; investigate state/order confounds before a separately qualified update. |
| G17 | Candidate PostgreSQL/pgvector maintenance alignment — partial | Optional candidate maintenance excluded. Official artifact and private restore/restart checks retain their scope; no selected-memory migration or native replacement acceptance follows. |
| G18 | Clean WSL host execution/native authentication — blocked | Selected two-host requirement. Preregister the surviving NativeStack WSL2 environment and verify native clients, supported scope/endpoints, required services, rollback and local authentication. Removed throwaway-host 35 pass/29 skip/0 fail is not destination acceptance. |
| G19 | Workstation and combined Mac workload — open | Selected workload requirement when that workload is scheduled. Observe real storage/cancellation/restart and representative resource pressure; GPU acceptance is required only for an actual GPU workload. Keep current hardware without measured purchase justification. |
| G20 | Whole-task usage and token-efficiency comparison — open | Requirement for usage/savings claims. Include children, retries and cache semantics without adding overlapping counters. Whole-task usage, provider settlement, applied compression and net savings remain unknown. |
| G21 | QMD Metal warning interpretation — verified configuration | Selected retrieval requirement. Observed offloading addresses the compiler warning only; top-three relevance misses, rerank latency and index freshness remain separate unqualified claims. |

The [offline runtime qualification](2026-10-02-north-star-runtime-qualification.md)
adds two fresh-process stress comparisons, two native initial-margin-refusal
comparisons and pinned-SDK recovery acceptance at their exact source/host scopes.
The [host and paper activation packet](2026-10-02-north-star-host-paper-activation.md)
records supported next steps and missing destination/account prerequisites.
These additions preserve the 21 carried gate dispositions above.

The corrected-harness update on2026-10-03 retains the original source results
and adds new prospective two-process qualifications: stress142/142 each with a
case-consistent receipt ID, and native refusal98/98 each with exact retained
cached/callback event agreement. The production historical CLI separately
verifies136/136 checks against eight unchanged archived sources, without a new
engine. See the dated stress/refusal receipts in the runtime record; these
repairs do not change the21foundation dispositions or grant host/paper admission.

Full production/full-stack readiness remains **false**. Optional exclusions do
not reduce that claim to a passed subset. Separate research data, realistic
simulation and broker-specific paper faults remain trading acceptance gates;
neither the foundation reconciliation nor historical broker receipts closes them.
Vela/VelaNext is retired, and no surviving memory executor is accepted by these
carried receipts.

## Evidence, privacy and acceptance

Keep all historical failed attempts, partials and raw returns at their original
version, host and scope. Reuse matching accepted evidence; run only the checks
needed for a changed input or concrete gap. A generated presentation, catalog
validator, version check or source review cannot certify native/model/broker
execution. Unknown whole-task usage and net savings remain unknown.

Publish sanitized source revisions, upstream locators, operation scopes,
acceptance totals and limitations. Personal host paths, credentials, native
authentication stores and raw histories stay in private task evidence. Source
sync carries project guidance, never native accounts or active shared services.
One designated owner retains each global setting, account, service and history.

For this source change, validate catalogs, the foundation manifest and its
existing contract tests; compare all 20 IDs with the baseline, check all 21 gate
classes and public privacy boundaries, and run `git diff --check`. The coordinator
registers shared hashes/pins and runs the required repository checks at the
integrated revision. These checks validate source consistency only; unresolved
host, lifecycle, quality, provider and paper gates keep their stated status.

Rollback is the scoped documentation/catalog commit. Any later runtime change
requires its own owner-reviewed official artifacts, compatibility acceptance and
guarded rollback; this record authorizes no shared-service mutation.
