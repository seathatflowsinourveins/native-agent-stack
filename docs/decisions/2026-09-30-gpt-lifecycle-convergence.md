# Native GPT lifecycle and task convergence

This host keeps native Codex as its GPT worker engine and uses OmniRoute only
through the explicitly selected Responses route. The bounded GitHub example
uses the official upstream Action. Add an external orchestration loop when a
specific task needs a capability beyond native threads and turns; source review
alone does not justify replacing a qualified worker.

The implementation is isolated from the frozen shared checkout. Live Claude
ownership covers global activation, default-harness carriers and skills, the
SDK/roster branches and gateway changes. This task does not claim those owners'
pending work as newly accepted. The second-machine work remains deferred while
this host is finished.

## Primary sources and selection

| Source | Pin and role |
| --- | --- |
| [Codex](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5) | CLI/Python SDK 0.159.2; native worker lifecycle and counters. Installed CLI and its release changelog were independently checked. |
| [Codex Action](https://github.com/openai/codex-action/tree/86365089eb2b84e0a8fb0717b304f8bdcb13b20e) | v1.12; supported GitHub job integration, explicit CLI/model/effort, Responses endpoint and schema. |
| [Claude Code](https://github.com/anthropics/claude-code/tree/ec44ca97dc86c33d934c8d55b24959aabf076871) | 2.1.285; installed native peer discovery/messaging, supported by [the official messaging contract](https://code.claude.com/docs/en/cross-session-messaging). |
| [RTK](https://github.com/rtk-ai/rtk/tree/1d87b8e719ce0a50c223cd93ca64dd16921f9aec) | v0.50.0; the hosted example uses its verified release archive in a job-local directory. |
| [Gitleaks](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md#configuration) | Installed 8.30.1; supported rule-level AND allowlist, limited to exact independently verified source-file digests and three artifact paths. |
| [LangGraph](https://github.com/langchain-ai/langgraph/tree/49cce0ca852be4cfb567a1cbe0e511ff325a1682) | 1.2.12; source-reviewed option for application-owned checkpoints across research stages. Not installed or promoted here. |
| [Deep Agents](https://github.com/langchain-ai/deepagents/tree/6bf780284ec49789613df20d85866a0ad981e579) | 0.7.20; source-reviewed application-loop challenger with skills, filesystem middleware and subagents. Not installed or promoted here. |

An Astra/Max researcher reconciled this consequential framework choice. Its
recommendation was accepted only where the installed client and immutable
primary sources support it. Framework agreement is not execution acceptance.
Search First and native skill discovery supplied candidate leads; skill popularity
did not establish adoption. The existing selected-skill qualification is reused;
this task does not install the full research catalog or rerun its model trials.

## Use each native surface for its task

| Lifecycle need | Selected surface | Acceptance boundary |
| --- | --- | --- |
| Source research and convergence | Existing frozen-task/evidence contract, with bounded native research workers | Preserve primary pins, failed conditions, held-out criteria and independently checked results. |
| Engineering PR review | Native Codex exec in an owned read-only checkout through the selected OmniRoute Responses route | Record exact head/merge-base, actual terminal result and independently verified findings. |
| Application runtime worker | Official Codex Python SDK/app-server | Native thread start/resume/fork, streamed item events, steering/interruption, approvals and schema output are source capabilities; qualify each required behavior through the intended route. |
| GitHub job | [Pinned official Action example](../../examples/gpt-native-github/README.md) | Native upstream unit checks and offline workflow analysis are separate from hosted runner/endpoint/model acceptance. |
| Durable multi-stage research | Existing qualified recovery lane first; LangGraph only for a concrete checkpoint gap | `sync`, `async` and `exit` durability have different crash windows. Checkpointing does not prove native child/provider cancellation. |
| Browser/server task | Existing task-specific OpenHands or other maintained recipe | Preserve each recipe's independent observer, dependency, tool and task-quality gates. |

The official Python SDK source implements native stateful lifecycle primitives
([API](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/api.py),
[result collector](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/_run.py)).
Dynamic tools remain experimental. LangGraph's documented durability adds
application state, while Deep Agents creates another agent loop; its planning is
opt-in since 0.7 and filesystem permissions do not confine arbitrary sandbox
execution. These are capability-specific choices, not universal upgrades.

The existing SDK branch at `404b821cd3af25800ea418dc6145cc5cb6fe33c5`
retains real same-host tool execution and fresh-process thread resume through
`cx/gpt-6-astra-max`, with native cumulative thread usage counted once. Its receipt
is [source-pinned branch evidence](https://github.com/seathatflowsinourveins/native-agent-stack/blob/404b821cd3af25800ea418dc6145cc5cb6fe33c5/evidence/artifacts/runtime-sdk-20260930/receipt.json).
It is not present in the integration's `11227bf` baseline and is not promoted by
this document. The unchanged SDK suite still records exit 1: one formatter
assertion failed, 266 tests passed and 38 were skipped. Live interrupt/reconnect,
an actually declined approval, independent per-request gateway/backend identity
and whole-roster research quality remain separate gates.

The newer runtime owner's [PR 551 decision at `ef90678`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ef90678c199a53bb43344fedec2fbcd5b6bf5c58/docs/decisions/2026-09-30-omniroute-runtime-workers.md)
retains a native Claude callsite: the parent discovered skill metadata, read its
body and launched the SDK worker once; the child task test passed. Its
[caller receipt](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ef90678c199a53bb43344fedec2fbcd5b6bf5c58/evidence/receipts/omniroute-claude-callsite-20260930.json)
records actual `Read` and `Bash`, with `Skill` available but not called. This is
retained branch evidence, not another execution here. The same owner's
[runtime receipt](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ef90678c199a53bb43344fedec2fbcd5b6bf5c58/evidence/receipts/omniroute-runtime-workers-20260930.json)
records successful primary-thread resume and fresh recovery, but its deadline
case only requested interruption and closed locally. It does not observe the
terminal interrupted event, reconnect that interrupted thread or exercise an
actual approval decline. Native Max request/tool carriage is observed; backend
identity remains unknown. These narrower results supersede an undifferentiated
claim that runtime dispatch is wholly pending, without closing every lifecycle
gate.

## Carry token practice into the task

Keep the task prefix stable and detailed material on demand. The portable task
loads the selected source packet, project rules and necessary skills; it does
not preload the catalog or assume workstation tools exist in a fresh CI home.
Use original reads for known sources, exact search for identifiers, and bounded
context-mode processing for large outputs. Use the named retrieval index only
when its collection points to the intended checkout and corpus. No unrelated
QMD collection was refreshed in this task.

Preserve native caching, deferred tool discovery, compaction and model choices.
Choose Sol/Max for bounded ordinary workers and retain explicitly requested
roles; this owner's consequential PR review uses Astra/Max. Describe the requested
route and backend observation separately. Do not force custom cache keys, model
tiers, lossy payload transforms or global effort changes on a running session.

Count one authoritative usage view per invocation. Cached input and reasoning
output are subsets of the corresponding Codex totals. Resumed SDK thread totals
are cumulative; adding them again double counts. Keep gateway observations and
native worker counters separate until their correlation is qualified. For Claude,
ordinary input, cache creation and cache reads are disjoint. A generated answer
is not telemetry. Unknown preparation, parent, researcher, retry or provider
usage stays unknown, so this task makes no whole-workflow savings claim.

Two dated accounting corrections matter:

- At current main, `child-usage.mjs` gained advisor accounting in
  [commit 6bbef3c](https://github.com/seathatflowsinourveins/native-agent-stack/blob/6bbef3c65f69af35348297c0beefa535054fbc91/examples/claude-native/workflows/child-usage.mjs).
  Detailed `children[].lanes.measurement.usage` carries `advisor_iterations`,
  `advisor_totals`, `totals_including_advisor` and `complete`. Legacy
  `children[].usage` and `by_resolved_model` remain executor-only. Do not add the
  detailed combined total to either legacy view. The existing synthetic checker
  returned 216 passed, 0 failed; it measures parser consistency, not savings.
- Current main's [gateway rebuild receipt](../../evidence/artifacts/omniroute-rebuild-20260930/receipt.json)
  retains zero changed tokens over eight headerless native Codex request bodies.
  Its lossy arm removed 908 of 265,483 tokens while losing 47 path occurrences,
  a hex identifier and an error line. That is insufficient acceptance for lossy
  compression on the native Codex lane. Preserve the exact payload contract.

Claude tool search through a custom `ANTHROPIC_BASE_URL` requires separate native
qualification of `tool_reference` forwarding; changing that setting blindly can
replace deferred discovery with more startup context. The live runtime owner
retains that integration. [Official tool-search behavior](https://code.claude.com/docs/en/mcp#configure-tool-search).

## Acceptance and ownership handoff

The [bounded plan](../../evidence/artifacts/gpt-lifecycle-convergence-20260930/plan.json)
names sources, ownership, tasks, quality rules, stop conditions and usage limits.
Native Claude messaging returned two queued deliveries. A separately observed
default-harness owner reply identified owned files and offered read-only GPT PR
reviews. A send alone is not agreement; the runtime peer's handback remains a
separate observation. Owner-provided timestamps do not establish execution order.

Fresh [native coordination and the Gate-A owner handback](../../evidence/artifacts/gpt-lifecycle-convergence-20260930/resolution-coordination.json)
confirm working native sign-ins and the current host boundary. U6 is unmerged,
no quiet window has been announced, and the default-harness owner retains one
B1 host batch from the accepted revision after owner go. Source-only work can
continue. No sign-in reset or host/global application is needed to repair this
PR; all shared hot-file edits belong in its final commit. Recipient permission
rules remain binding even when our dedicated coordination process uses the
user-authorized autonomous mode.

The portable workflow uses immutable checkout, read-only permissions, explicit
model/effort, a fresh job-local Codex home, schema output, a bounded manual task
and a job-local RTK binary whose archive matches the upstream checksum. Task
controls come from the reviewed dispatch revision in a separate checkout, so an
older inspection head neither needs nor supplies the prompt and schema. This
uses upstream checkout's supported side-by-side `path` contract and the Action's
absolute file inputs. No hosted
runner, public gateway or workflow is activated by placing an example here.
Hosted reachability, bearer acceptance, model routing, effort and structured
output must qualify together on the intended runner. The Action does not export
native usage as an output: its only output is `final-message`.

The unchanged Action install, type check, test and build commands returned exit
0: 143 tests passed and one Docker-socket test skipped. All 30 tracked source,
test and distribution files remained byte-identical to the pinned revision.
These upstream fixtures use fake Codex execution and do not qualify a provider
or hosted job. The independent verifier checked original log hashes and source
bytes rather than rerunning the suite.

One native Codex review through OmniRoute completed at the two frozen PR heads.
It accepted PR 540 within that scope and returned a source-verified P2 for PR 542:
the shared template renders Sol defaults on the separately pinned, unqualified
Mac client. An independent in-memory reproduction confirmed the finding; the
default-harness owner retains its repair. Requested Astra/Max routing was
recorded, while backend identity and effective effort remain unobserved.

The same offline pedantic workflow audit passed after its retained first failure,
with one analyzer-suppressed check. Native integrity, catalog, guide and scoped
convergence checks also passed. Companion receipts preserve actual output and
limitations. They qualify only their declared task and environment; the final
convergence checker validates recorded consistency and hashes, not truth.

The [repaired hosted Linux job](../../evidence/artifacts/gpt-lifecycle-convergence-20260930/hosted-ci-repaired.json)
then passed its full 8,623-test suite with 806 native skips at head `5e2bbc0`.
The later Mac validation passed its 472 selected checks with 29 skips and its
full 8,623-test suite with 1,116 skips. Other bootstrap jobs remained queued.
The separate dependency scan
failed in unchanged owner-managed locks. Neither the repository suite nor the
read-only host wiring observation qualifies the inactive hosted GPT workflow.

The dependency owner's [PR 546 at `4a09c9c`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/4a09c9c5f1e5fdb5555d4c916666f12e089cf09f)
relocks OpenHands to urllib3 2.8.0 and PyJWT 2.15.0. Its native OSV job passed;
the historical Mac Next lock receives a separate, dated scan exception. This
does not add those advisory exceptions to the ordinary scan. Required CI,
cross-family review and owner merge remain open; dependent branches should
update from accepted main afterward. No login or root-owned relock is needed.

Native GitHub observation subsequently confirmed the dependency-owner merge
at `8fc86119eacfd5be9b8a139e1ed167d85748091b`. The isolated integration updates
from that accepted main revision; it does not author a second lock repair.

The new [source-backed SDK control experiment](../../examples/gpt-native-controls/README.md)
observed terminal interruption after a model reasoning delta, successful
same-thread recovery in a fresh process, and an actual approval callback decline
followed by a native declined command and an absent sentinel. Two task threads
and one recovery completed with exit 0. Recovery and decline processes were
independently witnessed alive then gone; the first interrupted process's PID
lifecycle remains unobserved. A single observer repair is retained. Interrupted
usage, remote provider cancellation, complete attempt usage and backend identity
remain unknown. This closes those specific SDK control gates on this host,
without promoting whole-roster quality, hosted execution or the future B1 batch.
The separately dispatched Astra/Max verifier confirmed the original native
events, source/plan hashes, thread equality, later process observations and usage
subsets. Its [42-check event audit and retained limits](../../evidence/artifacts/gpt-lifecycle-convergence-20260930/native-controls-verification.json)
are independent of the worker's own oracle checks. No provider calls were
repeated. The scoped four-observation convergence record also preserves the
first observer's failed acceptance despite its command exit 0.

## Next north-star handoff

After the freeze owner accepts the host/default-harness changes, give the trading
owner one bounded research proposal with the exact corpus cutoff, point-in-time
sources, hypothesis, task paths, deterministic test commands and output schema.
Require source-grounded correctness and the appropriate native worker lifecycle
before interpreting token or cost comparisons. Preserve the selected
[NautilusTrader 2.0.0rc5 destination and separate IBKR/Alpaca gates](../../catalogs/us-equities/runtime-target.json).
Native workers support research; numerical simulation, risk and order state stay
deterministic. This foundation change does not advance a strategy or broker gate.

## Corrections verified in this turn

| Earlier lead or attempt | Correction and verification path |
| --- | --- |
| Guessed repository owner returned HTTP 404, including a repeated publication lookup. | Native `gh repo view --json nameWithOwner` identified `seathatflowsinourveins/native-agent-stack`; its native `gh api .../commits/main` returned `11227bf`. Use the discovered identity for subsequent calls. |
| A diff over foundation paths appeared to show SDK work already merged. | The SDK source is under shared/trading paths. Exact path comparison and receipt absence at `11227bf` show 12 relevant changed files in the separate `404b821c` branch. |
| Old guidance described blanket omission of Claude advisor usage. | Read current `transcriptUsage` and detailed measurement fields at the merged source; distinguish them from legacy executor-only summaries. |
| Native `pnpm --version` failed with exit 127. | Qualification uses the repository-pinned pnpm 10.33.0 in an owned prefix; the workstation PATH is unchanged. |
| The first stricter workflow audit found an unnamed job. | Add the job's descriptive name, preserve the original exit 11, and rerun the same offline pedantic native audit. |
| Publication review found task controls loaded from the inspected head. | Use the pinned checkout's supported side-by-side paths and the Action's file inputs; keep controls at the dispatch revision and inspection at the immutable task head. The repeated workflow audit is an offline check, not a hosted job. |
| The native commit gate flagged five credential-source filename digests. | Original pinned blobs and the independent verifier establish the two exact file hashes. Add an upstream-supported whole-line AND exception for those values in the three exact artifacts; preserve the first refusal and subsequent native no-findings result. No scan or hook is bypassed. |
| A PR evidence-table label was used in the convergence schema. | The native checker rejected `source_review`; schema line 77 defines `discovery` for the refused lookup. The initial draft and exit 1 are retained; the corrected record passes. |
| Scoped validation missed repository-wide discovery of the rejected JSON draft. | CI and the native `--all-recorded` check failed at discovery. Preserve the first draft byte-for-byte as `convergence-first.json.failed`, with its explicit rejected-artifact link, rather than declaring an invalid draft as an accepted experiment. Validator lines 225-238 define JSON record discovery. |
| The added dashboard gate omitted `kind` and exceeded the state limit. | Both native hosted suites retained eight dashboard errors. `progress.py:46-49,168-175` requires the kind and at most 160 characters. Repair only the owned gate row; the unchanged 17-test dashboard module passes. The earlier broad validation did not exercise this renderer contract. |
| Context-mode refused an outside-workspace diagnostic file. | Keep the refusal; do not change permissions or use another context-mode executor to bypass it. Retain private originals and publish bounded sanitized native observations. |
| A dedicated Claude print process had neither prompt nor stdin input. | The installed client returned exit 1 and its explicit input requirement. Use the documented one-shot `-p` with explicit prompt input; the corrected bounded native coordination completed. Failed-attempt usage remains unknown. |
| A sanitized coordination receipt retained native message identifiers. | Publication validation rejected a possible local session identifier. Keep those identifiers in the private hash-bound capture and publish only recipient roles and returned queue outcomes. |
| All-recorded discovery ran before refreshing hashes for in-progress edits. | The native checker rejected the changed manifest inputs. Re-register owned files after edits and before the final integrity/convergence check; keep the failed condition without changing the checker. |
| Native GitHub job-log download refused terminal escape sequences. | Installed `gh api --help` confirms `--allow-escape-sequences`; use it only to retain original bytes in a private file. Publish bounded footer observations and hashes, without displaying control sequences. |
| The first SDK observer treated the main thread's child list as complete. | Pinned async SDK startup offloads to a worker thread; kernel proc section 3.7 defines a per-thread list. Repair only the observer to inspect all tasks; preserve the first unobserved PID lifecycle and unchanged native source. |
| The first control convergence draft described a failed observer without a failed observation. | The checker rejected the mismatch. Preserve the rejected bytes and add the real observer observation with exit 0 but failed quality; the four-observation record passes. |
| Initial independent queries expected the declined item in persisted history and an unwrapped command string. | These original captures omit that declined item and shell-quote the request. Audit the actual native SDK event and decoded wrapper; retain initial query failures and their unknown exit codes. |
| The latest macOS failure was attributed to the pipe-buffer assertion. | Original `full-suite-macos.log` L9736 names `FAIL linear` and L9753 accounts for one failed Node case. The wrapper's `stdout[-4000:]` clips an earlier case label. An independent Astra/Max verifier confirmed the original digest and source; adopt the owner fix in PR #556 through rebase. Preserve the two unnecessary Linux pipe probes as synthetic diagnostics, without calling them macOS or model acceptance. |
| A Claude coordination command passed the `crossSessionInbound` setting as a CLI option. | Installed Claude 2.1.286 rejected the option with exit 1. Official cross-session documentation specifies per-call `--settings`; the corrected earlier invocation completed. Recipient policies remain intact. |
| A later JSON-mode coordination process timed out with empty captures. | Retain the actual exit 124, 210-second bound and unknown delivery/usage. An independent verifier confirmed empty captures and the documented observable stream mode; a subsequent compact owner handback is separate evidence, not zero usage or complete delivery proof. |

## October 1 source resolution and remaining rollout

The [source resolution receipt](../../evidence/artifacts/gpt-lifecycle-convergence-20260930/resolution-20261001.json)
retains the corrected macOS cause, independent verification and owner boundaries.
PR #556 changes the timing oracle that failed at the old head. Rebase onto the
owner's main revision and qualify the new head; evaluating the old rounded timing
samples against the replacement predicate is source review, not a new macOS run.
The Gate A owner keeps the test and wrapper. No competing diagnostic patch is
made.

Codex 0.159.3 is a new source-review snapshot. Its exact net tree delta changes the
version and TUI account-security reminders; the SDK and app-server contracts are
unchanged. Native controls remain qualified specifically on 0.159.2. The owner
assigns 0.159.3 to a post-window qualification unit, preserving native sign-ins and
sealed model arms. The unchanged SDK suite's formatter-driver failure is retained.

The native GitHub metadata checks expose a concrete deployment gap: the required
worker variables and bearer secret are absent and no self-hosted runner is
registered. Prepare the supported Action and runner lifecycle for owner review;
runner placement and isolation must satisfy the existing endpoint contract before
activation. Keep U6, single B1, actual hosted execution, backend evidence and
task-specific skill quality as separate acceptance gates. This source resolution
does not claim full host finalization.

Rollback removes only owned example/integration artifacts and diagnostic state;
global configurations, native accounts, human sessions and other-owner work are
preserved. Future source drift reopens the relevant task gate rather than making
this dated result universally current.
