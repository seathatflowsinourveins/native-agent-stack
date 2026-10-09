# SDK and runtime-worker adoption record — 2026-10-08

Status: the designated micro reads at 62426cf9fe81ebf7766fad9a7a139dd5bc575088
request record corrections. This revision carries those corrections and the
earlier combined delta fixes on the authorized records-only rebase head.
The landed retention rule and four-stage structure govern. Owner decisions,
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
of package-version or organic owning-role attribution. Every stage 4 binds this
immutable snapshot, while the fixed-time detailed SDK aggregates remain separate.
This lane did not rerun or edit the hourly producer.

Read-only native Loki queries used the fixed evaluation time
1791508016000000000 ns, 2026-10-09T01:06:56Z, and a 24-hour range. The six
original responses are retained byte for byte below; each filename contains its
verified SHA-256. Exact LogQL and the fixed-time query arguments are bound in
observations. Each result retains its own counting unit.

| Native lane | 24-hour result and retained witness | Attribution and counting unit |
| --- | --- | --- |
| codex_sdk_ts | 138,109 events ([event response][L-TS-E]) | ecosystem_lane absent; events are not invocations. |
| codex_sdk_ts | 708 codex.tool_result records ([tool-result response][L-TS-T]) | Tool results across the shared service; no package or capability-gate job allocation. |
| codex_sdk_ts | 80 conversations with a tool result ([conversation response][L-TS-C]) | Distinct conversations with tool results, separate from all conversation starts. |
| codex-sdk-receipt | 0 returned series events ([receipt response][L-PY]) | Empty vector for this native receipt-spool query; does not establish zero Python SDK use. |
| codex-app-server | 30 events ([app-server response][L-AS]) | No client/originator or owning-role attribution in the returned aggregate. |
| claude-code with query_source=sdk | 540 events ([SDK-source response][L-CL]) | SDK-source/headless events; package-pin and gateway-trial attribution remain separate gaps. |

[L-TS-E]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/typescript_sdk_events.cdaa239e16af4499f87dd4b41886eca64f87af4d3e51fed940b4da280dd8a76d.loki.json
[L-TS-T]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/typescript_sdk_tool_results.ad183319137c43fad6a30453c71ecdab7499e19007cbc23c533ee1f609d9fbbe.loki.json
[L-TS-C]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/typescript_sdk_conversations.5155c4089174502e28aa676fab0bdc793108d25ddb4e8c7440ad8f73893ca542.loki.json
[L-PY]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/python_sdk_receipt_events.145e231eda2d3d1d9210bc829f05580c149d5047eaffe3c39294967ec43fe11e.loki.json
[L-AS]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/app_server_events_by_client.f5a6eac9d40b5d5233694fc8f8e773a632f6f0dc7a426a262453ed5e03894b66.loki.json
[L-CL]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/claude_sdk_query_sources.1dcaf1644038547fca635340996755bae05edba9bdf0ef27143851f31d31df77.loki.json

The fixed-time [Claude SDK role response][L-CL-R] reproduces 115
skills-lifecycle events, 80 api-actions events and 345 unlabelled events: 195 of
the 540 events carry an ecosystem_lane label. These are role-labelled events;
package path, gateway-trial membership and organic task completion remain
unavailable. Each affected stage 4 binds the role distribution and states the
remaining join separately.

The [all-identified-conversation response][L-TS-A] records 108 distinct SDK
conversations, while the tool-result subset above contains 80. The [hourly
response][L-TS-H] records conversation presence in each preceding one-hour
interval, evaluated hourly from 2026-10-08T03:00:00Z through 2026-10-09T01:00:00Z.

| Hour ending, UTC | Identified conversations present in preceding hour |
| --- | --- |
| 2026-10-08T04:00:00Z | 9 |
| 2026-10-08T05:00:00Z | 100 |
| 2026-10-08T19:00:00Z | 1 |

The returned series contains these three samples. A conversation can appear in
more than one hourly slot, so 9 + 100 + 1 is not the distinct total of 108.
This baseline captures one concentrated burst and a later active conversation;
it establishes neither a sustained daily rate nor a zero total after the burst
leaves a moving window. Monitoring must use a new dated witness after expiry.

[L-CL-R]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/claude_sdk_events_by_role.af7cc227152d2d87e50cae7f89994011224195379726fd0a050f27d284771b58.loki.json
[L-TS-A]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/typescript_sdk_identified_conversations_all.80e8b32fd74f310b697bb38fafbc39d06e4169c44ee93023d2d4aa79ceccb860.loki.json
[L-TS-H]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/loki/typescript_sdk_identified_conversations_hourly.287ac95d39a71118e42fec6ec616a0d70f1554661990fe983f886f1836e54c77.loki.json

Every decision row names its measurement lane and per-role result. Native
ecosystem_lane labels are bound where present; missing package/job attribution
is null with the specific join missing. CLAUDE_CODE_ENTRYPOINT=sdk-py identifies the Python SDK
subprocess route; query_source=sdk counts alone do not prove that all events
came from the installed package. OpenHands and research runtimes retain native
per-job metrics, but their 24-hour role projections are not joined.
The fixed-window [OpenHands start projection][L-OH] binds one start for the
selected unit. A start does not establish completion or an organic owning-role
job. The earlier three-start observation is unavailable to this revision.
[The invoke-rate definition](2026-09-26-tool-invoke-rates.md) separates the
SDK receipt spool from native client tool results.

[L-OH]: ../../evidence/artifacts/sdk-runtime-adoption-20261008/openhands-job-starts.aef22b0794253231a919111201c2ad3854339480edf7da10d566aa8b572bae62.json

## Four stages per tool

Every row in decisions.json now has the same four separately evidenced stages:

1. Candidate binding: the landed selection governs unless a cited superseding
   decision replaces it. New candidate acceptance and G5 release binding remain
   PENDING, with the landed decision sources and pinned upstream maintenance,
   release, code-quality and benchmark evidence each row actually has. Today's
   invoke count is not selection evidence.
2. Wiring: vendor clean install, exact pin, native route per Claude/Codex client
   and inverse. Existing routes, missing acceptance and unsupported inverses
   are distinguished; no user-scope configuration or new glue is deployed.
3. Fresh session: ordinary task by the owning role without SDK/tool names.
   Native route, oracle and role-attributed organic counters must be retained.
   Explicit probes and unlabelled aggregate counts are not this evidence.
4. Invoke measurement: the hourly immutable adoption snapshot against the
   2026-10-08 baseline, with each counting unit and missing role join stated.
   These numbers inform monitoring; they do not select or remove candidates.

All ten new acceptance outcomes are DEFER while final G5 candidate/owning-role
evidence is pending. Existing landed selections continue to govern. A final
candidate with low use becomes WIRE through its vendor route; KEEP follows
demonstrated organic use at stage 3 or 4. The live provider dependency is retained.

## Role slots and memory-cost gate

Stage 1 names each tool's role slot, its governing landed incumbent and
overlap disposition. The evaluator's SDK provider is a distinct job; standalone
TypeScript and Python local-session adapters do not become parallel defaults.
The landed Claude SDK selection remains in force while an additional
programmatic application job awaits requirement and acceptance evidence.
Graph/checkpoint, remote coding and additional research-loop proposals overlap
existing slots under rule B and need a declared remaining gap or superseder.
GPT Researcher remains the baseline and DeerFlow the selected second independent
gatherer under [the October 1 defaults][D01] and [October 2 consensus][C02].
The research owner records the final alternative ranking in the catalog write
after G5; this record supplies no superseding decision.

Every stage 2 records per-session/process-tree PSS from smaps_rollup, whether a
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
| promptfoo openai:codex-sdk provider: 0.123.1 bundles SDK 0.153.4; installed CLI 0.124.0 bundles SDK 0.156.1 | DEFER; live dependency retained | Capability-gate evaluator dependency on the selected Codex surface ([D01]:57; [C02]:165–167). Distinct evaluator job; G5 /rows/88 is TRIAL, NEEDS-FIX, pin 0.124.1. The installed executable/version gate is unresolved. T-GATE supplies fresh role attribution. |
| Standalone TypeScript SDK 0.160.0 at ${USER_HOME}/.local/share/new-wsl-native-stack/tools/codex-sdk | DEFER | Selected Codex consumer surface ([D01]:57; [C02]:165–167); overlaps the Python adapter for local-session jobs under rule B. Retain separately from provider bundles; generic telemetry does not identify this package path. T-TS requires a real Node application job. |
| Python SDK worker 0.160.0 at examples/omniroute-codex-sdk/worker.py and its script lock | DEFER; host wiring named | Selected Codex consumer surface ([D01]:57; [C02]:165–167); overlaps the standalone adapter under rule B. Existing Claude coordinator's bounded caller, vendor lifecycle and native skill. Code defaults to 21128; historical acceptance used 20128. T-PY host acceptance remains pending. |
| Claude SDK 0.2.163 at ${USER_HOME}/.local/share/new-wsl-native-stack/tools/claude-agent-sdk | DEFER for additional application acceptance | Landed Claude SDK selection governs ([D01]:56; [C02]:162–164 retains the native Claude client and supplies no SDK superseder). Application-builder programmatic control needs a concrete gap and executable route; child settings do not dispatch a coordinator. T-CLAUDE. |
| OpenAI Agents SDK candidate, no installation found in bounded inventory | DEFER | Caller-owned API-loop candidate; overlap with selected native SDKs requires a declared application gap ([D01]:56–57; [C02]:162–167). Missing installation does not license retirement. T-CANDIDATE. |
| OpenHands layer: selected agent-runtime-worker SDK/tools 1.53.0; separate openhands-source/.venv editable metadata 1.50.1/source 1.53.0 | DEFER for new pin/environment acceptance | Existing OpenHands worker selection governs ([D01]:134; [C02]:168–175, whose comparison baseline is 1.50.1). Preserve both environments and owned-job oracle; current package 1.53.0 qualification is separate from a replacement decision. The selected unit's 1.50.1 header is stale. T-OH. |
| Deep Agents isolated SDK 0.7.23 at ${STATE_ROOT}/research/fullspeed-20261008/sdk-harness-ready/g5-rd-tools/langchain-ai__deepagents/runtime | DEFER | Application research/trial owner; filesystem fixture at this pin and separate 0.7.21 continuation trial. Worker/gatherer overlaps need a remaining gap under rule B ([D01]:134–135; [C02]:168–179). No replacement decision. T-DEEP. |
| Claude gateway SDK trial 0.2.162 at examples/claude-runtime-sdk/worker.py and lock | DEFER | Application agent builder; additional route overlaps the selected Claude SDK ([D01]:56; [C02]:162–164 supplies no SDK superseder). Source-derived trial with unverified/failed gateway boundaries; trial failure does not prove official installation failure. T-CLAUDE, separately scoped; coordinator dispatch remains unadopted. |
| GPT Researcher checkout v3.7.0 / pyproject 0.16.0 and selected gptr-mcp route | DEFER for new activation acceptance | Selected baseline gatherer ([D01]:135; [C02]:176–179). Existing MCP pin and activation gate plus CLI evidence; additional loops overlap this job under rule B. T-GPTR. |
| DeerFlow 2.1.0 embedded runtime and vendor HTTP skill | DEFER for new activation acceptance | Selected second independent gatherer ([D01]:135; [C02]:176–179). Preserve native research results; new HTTP activation and G5 inverse NEEDS-FIX remain owner gates. Additional loops overlap under rule B. T-DEER. |

Ten decision rows include the two distinct TypeScript deployments; OpenHands'
two environments belong to one layer. DEFER applies to new acceptance in this
record. The cited landed selections govern until a superseding decision is
cited. Owner decisions and the final post-G5 catalog ranking remain open.

The TypeScript caller is verified in
[run_gate.py](../../tools/capability-gate/run_gate.py) at lines 2–4 and 21–23,
and the [capability-gate contract](../../tools/capability-gate/README.md).
The pinned driver is
[promptfoo/promptfoo 0.123.1](https://github.com/promptfoo/promptfoo/tree/0.123.1);
its provider uses the bundled SDK and native codex_sdk_ts originator.
Installed metadata binds both versions in observations. run_gate.py requires
the `promptfoo` executable at 0.123.1 while PATH resolves to the 0.124.0 package,
whose metadata SHA-256 is
deb8f6569cd90b7ceb17dd57bc051bcd17401bf489ab2dd4019448ffaf37e101.
The delta read's earlier prefix inspection reported only `pf`; the bounded
2026-10-09T03:47:45.822281+00:00 capture found valid `promptfoo` and `pf` symlinks in that
0.123.1 prefix. The version check timed out after 20 seconds, and the gate was
not run. Observations records this correction; current pinned execution remains
unqualified. G5 /rows/88's 0.124.1 candidate remains TRIAL/NEEDS-FIX and does not
settle the executable/version gate. Retention preserves the verified caller
dependency. Shared-service events lack per-bundle attribution.

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
cleanup is not a proved vendor uninstall. Additional embedded research metadata
is cited at SHA-256 bc49079455731ec759af7148d42e67599626986b855449de0e1e614d5867d419.
Its response bytes are outside this packet, so its detailed counters are
unavailable to this read. Role/client attribution is absent, and embedded output
does not qualify HTTP.

The [September 30 Deep Agents trial](../../examples/deepagents-omniroute/README.md)
pins 0.7.21 at 4394bcd00b8eb46e7c423939643a0dfcfb5d8773. It retains failed initial
live research, successful saved-context repair and fresh-process SQLite
continuation. The 0.7.23 filesystem fixture at 9f4bdf7c8b8bfc86877729d80ed286bd71d78706
is narrower. G5 deepagents-code 0.1.83 at caaa7e7c12d214afa5cf0a1afed8eb6232aa6f7b
is a third product/pin. Their evidence scopes remain distinct.

## Withdrawn retirement and future repair

The decision artifact records the withdrawal globally:
`retirement_rule.withdrawn_previous_proposals` is 5, `retirements` is empty,
and `steps_executed` is 0. All ten decision rows are DEFER. The installation and
example scopes remain recorded in their rows. Retirement step: none. Inverse:
no action, because no installed file or configuration was removed. Any future retirement
must first satisfy rule 5, then identify its target, dependents, removal, pinned
restore and re-acceptance before a cue.

Known future repair procedures, not executed here:

The retained `observations.offline_parser_check` binds uv 0.12.22's offline
parser result: `uv venv` rejects `--python3.13` with return code 2; the corrected
`uv venv --python 3.13 --help` returns 0. Clean-install commands use
`--python 3.13`. This validates option parsing; no environment creation or
installation was performed by that check.

- Standalone TypeScript 0.160.0: vendor npm install @openai/codex-sdk@0.160.0
  in its owned environment, then the pinned thread API/installed-client override
  check. Preserve independent promptfoo bundles.
- Claude 0.2.163: vendor PyPI install in an owned Python environment and the
  pinned quick-start/native session check after a real application requirement.
  The separate 0.2.162 gateway trial restores through its existing uv script
  lock and preflight, without promoting its live gateway boundaries.
- OpenHands 1.53.0 source environment: vendor `make build` runs `uv sync --dev`
  at [54daf056bd863bb46f922a2fe9324dd736b37ff6](https://github.com/OpenHands/software-agent-sdk/blob/54daf056bd863bb46f922a2fe9324dd736b37ff6/Makefile#L34-L37),
  Makefile:34–37. [SDK metadata](https://github.com/OpenHands/software-agent-sdk/blob/54daf056bd863bb46f922a2fe9324dd736b37ff6/openhands-sdk/pyproject.toml#L3)
  and [tools metadata](https://github.com/OpenHands/software-agent-sdk/blob/54daf056bd863bb46f922a2fe9324dd736b37ff6/openhands-tools/pyproject.toml#L3)
  each declare 1.53.0 at line 3; this supported source sync restores coherent
  metadata. The existing [installer plan](../../evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json):4307–4310
  instead exports and installs 1.50.1 constraints.
  The historical 1.53.0 export has a local host witness at
  `${USER_HOME}/.local/share/new-wsl-native-stack/tools/openhands-source/openhands-1.53.0-constraints.txt`.
  The recorded witness metadata is 58,784 bytes, SHA-256
  77f59a5d9403594b8c78be40a0bf5d20a95353ab68a4dcfde518933d6260f17e,
  mtime 2026-10-08T02:38:32Z. Observations records this source under
  `openhands_constraints_witness` with availability `LOCAL_HOST_WITNESS_ONLY`.
  The witness remains outside the repository's scanned tree. Its dependency set
  was not run here; the historical source export does not establish current
  deployment or acceptance. No export, installation or restore was performed
  in this revision. Both installed environments remain preserved pending scoped
  restore acceptance. The stale 1.50.1/source 1.53.0 mix is not a supported
  restore target.
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
| T-GATE | Native Claude/Codex capability evaluator | Resolve the recorded executable/version gap, then retain configured vendor SDK provider selection, task oracle and role/conversation join. Count events, tool results and conversations separately. G5 /rows/88 pin 0.124.1 is pending candidate acceptance. |
| T-TS | Real Node application caller | Demonstrate public thread-API requirement and actual standalone package path, then vendor start/run/resume acceptance. |
| T-PY | Fresh Claude foundation coordinator | Existing native skill selects 21128 worker; host-qualified useful result, private native-result, role attribution, usage and close record. Writing has a separate gate; no invented same-family Codex SDK caller. |
| T-CLAUDE | Application requiring programmatic Claude control | Vendor-shipped example/route plus concrete requirement; child skill settings alone do not justify coordinator glue. Gateway trial has its own live gate. |
| T-CANDIDATE | API handoff/guardrail application | Owner selects needed application job, then vendor install and loop acceptance. Missing installation is not rejection. |
| T-OH | Declared isolated/remote coding job | Distinguish both environments; vendor forced terminal subprocess test under timeout 600, then authorized native-unit task with requests_to_model > 0, exact file oracle and owner-role join. |
| T-DEEP | Application research/trial owner | Declare the graph/checkpoint job and retain pin-specific oracle, saved-state/fresh-process continuation when required; filesystem-only evidence does not pass the older trial or dcode CLI job. |
| T-GPTR | Research-owner selected Claude/Codex role | Existing STDIO/environment/five-tool/lifecycle gate, useful results per applicable client, then ordinary-task vendor skill selection and retrieval/citation witnesses. |
| T-DEER | Research-owner selected HTTP-skill role | Vendor service at DEERFLOW_URL, health/thread/run completion, useful research oracle and caller/job join; preserve inverse NEEDS-FIX and distinguish embedded use. |

## Landed catalog and workflow reconciliation

The pinned foundation.json capture at base
aba02ec3456d383bcc2fc72883db098f9be7918a has SHA-256
868d193a31080ab913400725140bd0d01e0afe97e28564fd12777f737d22951a
and is byte-identical at the authorized rebase target
58080c6b435d14c57f5b9e0bbbc0658add41c8d9. Its frozen rows state:

- /layers/2/current_choice selects native Claude/Codex workers with owned
  Worktrunk worktrees, optional Beads and qualified cross-client review, and an
  opt-in semantic-evidence-reviewer. This field does not name OpenHands as a
  selected worker.
- /layers/8/current_choice selects agent-browser, selected Playwright CLI
  operations, OpenResearch literature retrieval and Tavily CLI search/extract
  skills. Its rationale says another autonomous research loop is not currently
  needed to replace that path; the field does not name the two gatherers.
- /layers/16/current_choice selects Codex SDK/CLI for supported start/run/resume
  and calls Claude Agent SDK, OpenHands SDK, Temporal and LangGraph
  source-reviewed, unselected alternatives. The only winner is openai/codex.

The `current_choice` source locators in
[foundation.json](../../catalogs/landscape/foundation.json) are lines 604,
2267 and 4566 respectively; the web-research rationale is at line 2269.

These frozen descriptions differ from the governing selections in [D01] and
[C02]: OpenHands worker ([D01]:134; [C02]:168–175), GPT Researcher baseline and
DeerFlow second independent gatherer ([D01]:135; [C02]:176–179), and definitive
Claude Agent SDK alongside Codex SDK/exec/app-server ([D01]:56–57;
[C02]:162–167 supplies no SDK superseder). This is catalog drift requiring
re-recording. The [October 3 drift correction][D03]:22–40 requires a new run id
and sealed cross-family review for changed frozen verdict rows. The affected
rows retain their recorded wording until that separate re-record; this revision
changes no catalog row.

[D01]: 2026-10-01-new-wsl-definitive-defaults.md
[C02]: 2026-10-02-new-wsl-layer-consensus.md
[D03]: 2026-10-03-foundation-catalog-drift.md

The retained source SHA-256 values are
1b59e7b2100199d2b3a2125a811c7959c11dc55be9d029d4c0f676bbd9059ff5 for [D01]
and a3a0e724c2997ce1323b87b07f80e72e57d50d9bb1ce75f4a4a356409225be39 for [C02].
The [D03] source SHA-256 is
a4c5ddf98c9fa778d07b60507a183818b1d243dda789bc06ee8bcd612fcbcedb.
The landed selection governs unless a cited superseding decision changes it;
this record cites none. Rule B flags the same-job overlaps in each affected row,
and the final ranking belongs to the post-G5 catalog write.

The Python worker's recorded host-boundary repair and retained live provider
dependency await their separate acceptance gates. G5 #878 remains OPEN at observed head
083800f288ee7a0a4e836ff06279538d0332b8e2. Final release/asset binding is pending;
candidate pointers are not landed G5 acceptance. Its retained action file
SHA-256 is d78bae7f30c83395c475ca5359022ec7e3db7cbb6a8e288ad1674a2d1ff73020.

Reuse workflow baseline
c6e9f24e207520b1dfa1d83f094b9d7c8996dbd6cd1d9019a0c4f115e7407ad8.
No runtime changed and no post-change saving is claimed. Both artifacts use the
same acceptance labels. Old-head CI is historical;
revised-head CI remains pending. Both reads' findings, pre-cue/upstream reviewer,
owner decisions, G5 release and CC cue remain explicit gates.

The designated CC pre-cue entrypoint is
`${STATE_ROOT}/coordination/command-center/cc-tools/base_tests_at_head.sh`, 2,870 bytes,
SHA-256 82a2f507b773258f6beb1e727b12cfa5101e8ffb2d5dc520c5ccabde228fedf5.
Its header at lines 2–9 defines the repository/base/head contract and supported
`unittest` runner. Acceptance remains PENDING until the external receipt binds
the authorized base 58080c6b435d14c57f5b9e0bbbc0658add41c8d9 and the full revised
head to that entrypoint's result.
