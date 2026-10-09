# SDK and runtime-worker adoption record — 2026-10-08

Status: both designated reads at 45cbdbad4439dba6422fc6617eceee58502a8aaf
request changes. This prepared revision carries both reads' findings, the
retention rule and the owner's four-stage structure; one combined head follows
local checks. Owner decisions,
G5 release binding, revised-head CI, pre-cue and the CC's cue precede 5f landing.

[Decisions](../../evidence/artifacts/sdk-runtime-adoption-20261008/decisions.json)
records ten DEFER rows pending the four-stage owner gates.
[Observations](../../evidence/artifacts/sdk-runtime-adoption-20261008/observations.json)
binds source pins, current installations, native counter responses and retained
qualification. DEFER preserves a candidate below an adoption claim while its
requirement or activation is unsettled.

All five previous RETIRE proposals are withdrawn under
[the landed retention rule](2026-10-07-clean-upstream-install-finalizes-a-candidate.md),
rules 4–5 at lines 67–73: low use is an installation gap first; a component leaves
only for a better-evidenced upstream replacement for the same job or an official
install shown unable to work on this host. Neither was established here.
No environment, source, lock, skill, unit or historical receipt is removed.

## Corrected native measurement

The original record wrongly generalized an omission in the CC producer into
“SDK and worker use is unmeasured.” That claim is withdrawn. The old MCP-only
snapshot remains historical evidence, SHA-256
5de97cf238b3d28aa9f7d5110a05857204a847b0c75cda8971de8e142e362e36.
The current producer, SHA-256
efff86d46ee7b76d1634d067a5c53126a0120294bbf38372f4318677d556a2a9,
includes codex_sdk_ts and codex-app-server, with sdk:<service>:<lane> rows.
The co-op-retained immutable SDK snapshot is now bound at
notes/adoption-evidence-20261008/adoption-now-e129759fe91ffbb1.json,
SHA-256 e129759fe91ffbb133de2719a7d5194fe96ac65c44b222adf7fdd4d65af0e872,
generated 2026-10-09T01:39:38Z. Its sdk:codex_sdk_ts:unlabelled row has 80
conversations within a native Codex population of 931; it records 107 context-mode
and 18 Serena calls in that SDK row. These are native source counts, not proof
of package-version or organic owning-role attribution. Every stage4 binds this
immutable snapshot, while the fixed-time detailed SDK aggregates remain separate.
This lane did not rerun or edit the hourly producer.

Read-only native Loki queries at 2026-10-09T01:06:56Z used one fixed 24-hour
end time. Exact LogQL and response SHA-256 values are retained in observations.

| Native lane | 24-hour result | Attribution and counting unit |
| --- | --- | --- |
| codex_sdk_ts | 138,109 events; 708 codex.tool_result records; 80 conversations with a tool result | ecosystem_lane absent; events are not invocations, and the shared service does not allocate every conversation to a package or capability-gate job. |
| codex-sdk-receipt | 0 events | Native receipt-spool series only; does not mean zero Python SDK use. |
| codex-app-server | 30 events | No client/originator or owning-role attribution in the returned aggregate. |
| claude-code with query_source=sdk | 540 events | SDK-source/headless path; not joined to owning role, package pin or the specific gateway trial. |

Every decision row names its measurement lane and per-role result. Unknown
role/job attribution is null with the specific join missing. The native SDK
counts remain measured. CLAUDE_CODE_ENTRYPOINT=sdk-py identifies the Python SDK
subprocess route; query_source=sdk counts alone do not prove that all events
came from the installed package. OpenHands and research runtimes retain native
per-job metrics, but their 24-hour role projections are not joined.
[The invoke-rate definition](2026-09-26-tool-invoke-rates.md) separates the
SDK receipt spool from native client tool results.

## Four stages per tool

Every row in decisions.json now has the same four separately evidenced stages:

1. Final candidate: PENDING until G5 lands, with the landed foundation row and
   pinned upstream maintenance/release/code-quality/benchmark evidence it
   actually has. Today's invoke count is not selection evidence.
2. Wiring: vendor clean install, exact pin, native route per Claude/Codex client
   and inverse. Existing routes, missing acceptance and unsupported inverses
   are distinguished; no user-scope configuration or new glue is deployed.
3. Fresh session: ordinary task by the owning role without SDK/tool names.
   Native route, oracle and role-attributed organic counters must be retained.
   Explicit probes and unlabelled aggregate counts are not this evidence.
4. Invoke measurement: the hourly immutable adoption snapshot against the
   2026-10-08 baseline, with each counting unit and missing role join stated.
   These numbers inform monitoring; they do not select or remove candidates.

All ten outcomes are DEFER while final G5 candidate/owning-role evidence is
pending. A final candidate with low use becomes WIRE through its vendor route;
KEEP follows demonstrated organic use at stage3 or4. The live provider is
preserved, rather than incorrectly retired or prematurely marked adopted.

## Role slots and memory-cost gate

Stage1 now names each tool's role slot, its landed/provisional incumbent and
overlap disposition. The evaluator's SDK provider is a distinct job; standalone
TypeScript and Python local-session adapters do not become parallel defaults.
Claude control, graph/checkpoint, remote coding and research-loop candidates
remain alternatives until their upstream-quality/requirement evidence settles.
GPT Researcher and DeerFlow overlap in the gatherer slot; the research owner
ranks alternatives in the subsequent catalog write after G5.

Every stage2 records per-session/process-tree PSS from smaps_rollup, whether a
shared HTTP/streamable-HTTP copy is supported, and owning-role loading policy.
No component-specific PSS was measured in this revision, so values remain null,
with an explicit measurement gap and ADOPT-NOW disallowed. An absent/idle process
is not a zero-cost measurement. The source role-MCP trial report is retained at
SHA-256 f0afc2c734b3ad1b70e68cd38d3c844c7f4b1338cc030c8fc40fc88db1e53989;
whole-profile measurements do not establish an SDK/library's own footprint.

Vendor gptr-mcp documents STDIO/SSE/streamable-HTTP deployment and DeerFlow has
a native HTTP service, so shared service is source-supported in principle,
with client/state/lifecycle acceptance pending. A shared HTTP copy for the
other SDK/library child-process routes is not qualified at these pins. Load
only into owning roles and use alwaysLoad:false where the client supports it.
User-scope changes require a reviewed CC diff; none is deployed here.

## Per-surface decisions

| Surface and exact installation scope | Decision | Job, evidence and missing gate |
| --- | --- | --- |
| promptfoo openai:codex-sdk provider: 0.123.1 bundles SDK 0.153.4; installed CLI 0.124.0 bundles SDK 0.156.1 | DEFER; live dependency retained | Actual capability-gate evaluator dependency; native SDK counters are stage-4 baseline. T-GATE supplies fresh role attribution; final G5 candidate binding remains pending. |
| Standalone TypeScript SDK 0.160.0 at ${USER_HOME}/.local/share/new-wsl-native-stack/tools/codex-sdk | DEFER | Retain separately from provider bundles; generic telemetry does not identify this package path. T-TS requires a real Node application job. |
| Python SDK worker 0.160.0 at examples/omniroute-codex-sdk/worker.py and its script lock | DEFER; host wiring named | Existing Claude coordinator's bounded caller, vendor lifecycle and native skill. Code defaults to 21128; historical acceptance used 20128. Final G5 candidate and T-PY host acceptance remain pending. |
| Claude SDK 0.2.163 at ${USER_HOME}/.local/share/new-wsl-native-stack/tools/claude-agent-sdk | DEFER | Programmatic session-control candidate. No invocable coordinator route or demonstrated application gap licenses WIRE. T-CLAUDE. |
| OpenAI Agents SDK candidate, no installation found in bounded inventory | DEFER | Landed unqualified caller-owned API-loop candidate; missing install does not license retirement. T-CANDIDATE. |
| OpenHands layer: selected agent-runtime-worker SDK/tools 1.53.0; separate openhands-source/.venv editable metadata 1.50.1/source 1.53.0 | DEFER | Preserve both environments and owned-job oracle. Unit selects agent-runtime-worker; source environment is separately qualified. T-OH. |
| Deep Agents isolated SDK 0.7.23 at ${STATE_ROOT}/research/fullspeed-20261008/sdk-harness-ready/g5-rd-tools/langchain-ai__deepagents/runtime | DEFER | Filesystem fixture at this pin; preserve separate 0.7.21 live continuation trial. No rule-5 replacement evidence. T-DEEP. |
| Claude gateway SDK trial 0.2.162 at examples/claude-runtime-sdk/worker.py and lock | DEFER | Source-derived trial with unverified/failed gateway boundaries; trial failure does not prove official install failure. T-CLAUDE, separately scoped. |
| GPT Researcher checkoutv3.7.0 / pyproject 0.16.0 and selected gptr-mcp route | DEFER to research owner | Existing MCP pin and activation gate plus CLI evidence. No change to landed browser/retrieval selection. T-GPTR. |
| DeerFlow 2.1.0 embedded runtime and proposed HTTP skill | DEFER to research owner | Preserve native research results; owner selects new HTTP activation. G5 inverse remains NEEDS-FIX. T-DEER. |

Ten decision rows include the two distinct TypeScript deployments; OpenHands'
two environments belong to one layer. Deferred rows do not carry a final
KEEP/WIRE/RETIRE acceptance. Their owner decisions remain open.

The TypeScript caller is verified in
[run_gate.py](../../tools/capability-gate/run_gate.py) at lines 2–4 and 21–23,
and the [capability-gate contract](../../tools/capability-gate/README.md).
The pinned driver is
[promptfoo/promptfoo 0.123.1](https://github.com/promptfoo/promptfoo/tree/0.123.1);
its provider uses the bundled SDK and native codex_sdk_ts originator.
Installed metadata binds both versions in observations. Retention preserves this
demonstrated dependency, without asserting a framework winner or inferring
which bundle produced every shared-service event.

## Vendor routes and retained boundaries

Claude SDK 0.2.163 pins
[1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7](https://github.com/anthropics/claude-agent-sdk-python/tree/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7).
types.py:2297 confirms setting_sources=None loads defaults and skills=None
leaves CLI defaults active. These govern an SDK session; they do not dispatch
it from a coordinator. The former W2 label resolved only to an external costed
plan, not an executable adoption route, and is removed from the justification.
The separate gateway trial pins
[f2204bb956bab02907aaf3cb88eb9dead28eaa35](https://github.com/anthropics/claude-agent-sdk-python/tree/f2204bb956bab02907aaf3cb88eb9dead28eaa35);
its [verification](../../examples/claude-runtime-sdk/verification.md) leaves
live route, activation and recovery open. OpenAI Agents' separate source
candidate pins
[26345c1e45ebede8e2fc9b0bc7341dedab5e01fc](https://github.com/openai/openai-agents-python/tree/26345c1e45ebede8e2fc9b0bc7341dedab5e01fc).

The Python worker uses
[openai/codex@a956835d020762cb2b570053af06f643a11c0ecc](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python).
The existing thin integration supplies bounded child lifecycle, private native
results and selected skill/MCP setup around the vendor loop. Its source-backed
gap and actual failures are recorded by the
[October 3 integration decision](2026-10-03-omniroute-sdk-worker-0160.md) and
[coordinator skill](../../.claude/skills/omniroute-runtime-worker/SKILL.md):63–65.
The vendor Claude project Skill instructions are retained independently of the
Codex execution SDK: instruction snapshot SHA-256
44ef73f373fd7a38205e9af4c78289bf7c20c7975b03081d9061cb671d7cfded,
1650 bytes, source https://code.claude.com/docs/en/skills.md, locators
“Extend Claude with skills,” “Test the skill,” and “Choose where skills load.”
The exact relevant vendor excerpts are embedded in observations and retained
under the record's durable evidence directory. The selected project Skill bytes
are separately bound at aba02ec3456d383bcc2fc72883db098f9be7918a:
SHA-256 feacd5b6324649e3fff16d4f7f469f994e2984dccbb462f84e6fa8bf8e93da48,
3840 bytes. This is an immutable instruction capture, not a claim of closed-source
CLI-release/source equality. The skill's stale 20128 prose is the concrete host instruction
gap; worker.py:42 already defaults to 21128. The
[historical receipt](../../evidence/receipts/omniroute-sdk-worker-0160-20261003.json):1918
queried 127.0.0.1:20128/v1/models, which qualifies that historical route only.
No live 21128 SDK task receipt is retained for this row. No 20128 request was made
during this revision. Host preflight precedes an authorized bounded 21128 task;
it does not prove useful task completion or writing dispatch.

GPT Researcher's 317-byte
[vendor skill](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/skills/gpt-researcher/SKILL.md)
already targets
[assafelovic/gptr-mcp@63884773685b1f12c7f0d9e283b3d71a5b9b5fda](https://github.com/assafelovic/gptr-mcp/tree/63884773685b1f12c7f0d9e283b3d71a5b9b5fda).
The pinned README supplies pip install -r requirements.txt and python server.py
(default STDIO). The [existing consensus](2026-10-02-new-wsl-layer-consensus.md):122
requires resolved/pinned dependencies, native STDIO handshake, five-tool
discovery, useful results in both applicable clients and bounded start/stop/removal.
Nonprotocol stdout on direct start and the SSE-only tester remain limits.
The profile exposes no accepted gptr-mcp surface. No substitute server or glue
is created; research-owner selection and that existing gate precede activation.

DeerFlow's
[vendor HTTP skill](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/SKILL.md)
and scripts/chat.sh use DEERFLOW_URL, default localhost:2026, from which gateway
and /api/langgraph routes derive. G5 action /rows/48,
row 86c6347b193efc3a8df5, verifies installation via
cd <v2.1.0-source>/backend; uv sync --locked and check via
make -C <source>/backend test. Its inverse is NEEDS-FIX:
reset_session_pool returns the retired pool and does not close it; source-informed
cleanup is not a proved vendor uninstall. Additional embedded research evidence
records 3 search witnesses,13 fetch witnesses,11 matching citations and 197,818 native
tokens at SHA-256 bc49079455731ec759af7148d42e67599626986b855449de0e1e614d5867d419.
Its role/client is absent, and embedded output does not qualify HTTP.

The [September 30 Deep Agents trial](../../examples/deepagents-omniroute/README.md)
pins 0.7.21 at 4394bcd00b8eb46e7c423939643a0dfcfb5d8773. It retains failed initial
live research, successful saved-context repair and fresh-process SQLite
continuation. The 0.7.23 filesystem fixture at 9f4bdf7c8b8bfc86877729d80ed286bd71d78706
is narrower. G5 deepagents-code0.1.83 at caaa7e7c12d214afa5cf0a1afed8eb6232aa6f7b
is a third product/pin. Their evidence scopes remain distinct.

## Withdrawn retirement and future repair

Every former retirement target has WITHDRAWN in the decision artifact, including
its installation or example scope. Retirement step: none. Inverse: no action,
because no installed file or configuration was removed. Any future retirement
must first satisfy rule 5, then identify its target, dependents, removal, pinned
restore and re-acceptance before a cue.

Known future repair procedures, not executed here:

- Standalone TypeScript0.160.0: vendor npm install @openai/codex-sdk@0.160.0
  in its owned environment, then the pinned thread API/installed-client override
  check. Preserve independent promptfoo bundles.
- Claude 0.2.163: vendor PyPI install in an owned Python environment and the
  pinned quick-start/native session check after a real application requirement.
  The separate 0.2.162 gateway trial restores through its existing uv script
  lock and preflight, without promoting its live gateway boundaries.
- OpenHands selected package environment: Python 3.13 venv, then the existing
  installer's uv pip install --python <env>/bin/python -c <pinned-constraints>
  openhands-sdk==1.53.0 openhands-tools==1.53.0. Vendor make build/uv sync --dev
  at 54daf056bd863bb46f922a2fe9324dd736b37ff6 restores source metadata 1.53.0.
  No supported procedure preserves the stale1.50.1/source 1.53.0 mix.
- Deep 0.7.23: retained receipt's uv venv --python 3.13 <runtime> and
  uv pip install --python <runtime>/bin/python deepagents==0.7.23, followed by
  its exact filesystem oracle. The separate 0.7.21 trial restores through its
  committed hash-required lock and own describe/continuation contract.

## Fresh-session settling tests

Use an ordinary real task without SDK/tool names in its prompt. Retain native
route/provider selection, owning role/client, package/config pin, result oracle,
usage and terminal lifecycle. Qualification probes are not organic adoption.
Inference remains subject to the existing owner/budget/credential gates.

| Test | Applicable owner/client | Evidence that settles the gap |
| --- | --- | --- |
| T-GATE | Native Claude/Codex capability evaluator | Configured driver selects its pinned vendor SDK provider; task oracle plus role/conversation join. Count events, tool results and conversations separately. Do not infer pinned 0.123.1 execution from current 0.124.0 executable. |
| T-TS | Real Node application caller | Demonstrate public thread-API requirement and actual standalone package path, then vendor start/run/resume acceptance. |
| T-PY | Fresh Claude foundation coordinator | Existing native skill selects 21128 worker; host-qualified useful result, private native-result, role attribution, usage and close record. Writing has a separate gate; no invented same-family Codex SDK caller. |
| T-CLAUDE | Application requiring programmatic Claude control | Vendor-shipped example/route plus concrete requirement; child skill settings alone do not justify coordinator glue. Gateway trial has its own live gate. |
| T-CANDIDATE | API handoff/guardrail application | Owner selects needed application job, then vendor install and loop acceptance. Missing installation is not rejection. |
| T-OH | Declared isolated/remote coding job | Distinguish both environments; vendor forced terminal subprocess test under timeout 600, then authorized native-unit task with requests_to_model > 0, exact file oracle and owner-role join. |
| T-DEEP | Application-owned graph/checkpoint job | Pin-specific oracle, saved-state/fresh-process continuation when required; filesystem-only evidence does not pass the older trial or dcode CLI job. |
| T-GPTR | Research-owner selected Claude/Codex role | Existing STDIO/environment/five-tool/lifecycle gate, useful results per applicable client, then ordinary-task vendor skill selection and retrieval/citation witnesses. |
| T-DEER | Research-owner selected HTTP-skill role | Vendor service at DEERFLOW_URL, health/thread/run completion, useful research oracle and caller/job join; preserve inverse NEEDS-FIX and distinguish embedded use. |

## Landed catalog and workflow reconciliation

The landed foundation.json SHA-256 is
868d193a31080ab913400725140bd0d01e0afe97e28564fd12777f737d22951a at base
aba02ec3456d383bcc2fc72883db098f9be7918a.

- /layers/2 workers retains native Claude/Codex and owned worktrees.
- /layers/8 web-research retains browser/retrieval; another autonomous loop is
  not currently needed. Research runtimes defer to the owner's final list/gap.
- /layers/16 agent-sdks retains Codex; Claude/OpenHands and application-runtime
  alternatives remain unselected/source-reviewed.

This record changes no landed catalog selection. The proposed Python wire
repairs an existing host deployment boundary; The live provider is retained as a
dependency. G5 #878 remains OPEN at observed head
083800f288ee7a0a4e836ff06279538d0332b8e2. Final release/asset binding is pending;
candidate pointers are not landed G5 acceptance. Its retained action file
SHA-256 is d78bae7f30c83395c475ca5359022ec7e3db7cbb6a8e288ad1674a2d1ff73020.

Reuse workflow baseline
c6e9f24e207520b1dfa1d83f094b9d7c8996dbd6cd1d9019a0c4f115e7407ad8.
No runtime changed and no post-change saving is claimed. Both artifacts use the
same acceptance labels. Old-head CI (28 successful, 8 skipped) is historical;
revised-head CI remains pending. Both reads' findings, pre-cue/upstream reviewer,
owner decisions, G5 release and CC cue remain explicit gates.
