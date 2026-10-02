# Two-host architecture for starting North Star R&D

Decision date: 2026-10-02. Source baseline:
`18eea2c1de992b46c266d79ef0cc40f93c9fb943`.
Scope: **macOS and the workstation only**. This is the resolved operating design
for the user's North Star R&D request, with a current source review and a local
offline starting check. It is not a new blind comparison or proof that every
component is the best on every workload.

## Decision and start boundary

**Start offline R&D with the existing native engineering core.** Use GPT-6.1 Sol
at native Ultra for the coordinator and default workers, native Claude for its
established companion role, and bounded Astra escalation for a consequential
decision, conflicting evidence, or a hard failure unresolved by evidence-led
Sol diagnosis. Every worker receives an objective, exact revision, owned paths,
acceptance command and compact evidence handoff. One writer owns each checkout
or shared service.

The first R&D unit is the existing SPY `one_stress` costs-and-rounding mapping.
The current-source synthetic starter suite passed 179 tests with exit 0.
Historical `one_zero` engine parity remains accepted only at its original
scope. Five other scenario mappings, realistic execution and separate broker
acceptance remain open. Memory replacement, Pi promotion, an SDK upgrade and a
complete optional-tool sweep are not prerequisites for this offline unit.

**The two-host design is resolved; workstation activation is not attested by
this Mac review.** The current maintained source identifies no surviving
preregistered replacement for the removed WSL test environment. The user's
confirmation identifies the present environment as macOS, without identifying
a current workstation distro or transport. Historical workstation receipts
and visible hardware do not fill that gap. No remote settings were changed.

## Responsibilities on the two hosts

| Boundary | macOS | Workstation |
| --- | --- | --- |
| Native clients | Interactive coordination, source review, bounded coding and local deterministic checks; retain native Codex and Claude sign-ins | Same native task contract in its own accepted OS/WSL environment; authenticate locally and verify effective model/effort there |
| Compute | Small reproducible fixtures and analysis | Planned home for substantial replay, datasets and GPU workloads after that environment's native acceptance |
| Source and ownership | Canonical Git revision, one coordinator, separate owned checkouts, reviewed PR integration | Pull the same accepted revision; return exact input/output hashes, commands, exit codes and runtime identity |
| Durable context | Retain the existing ai-memory 2.5.2 owner and scoped reads; canonical decisions stay in Git | Use only an explicitly configured, supported memory endpoint with verified scope; otherwise versioned decision files and an outbox, never another host's localhost |
| Gateway | Use the existing owner-controlled OmniRoute endpoint for SDK/runtime requests | Same routing contract; placement, credentials and restart remain with the existing service owner |
| Research state | Review immutable snapshots, provenance, experiment contracts and results | Run only the owned frozen experiment; write deterministic results and resumable checkpoints |
| Recovery | Native session continuation plus scoped state backup and rollback | Verify task cancellation, restart, storage and output recovery on the actual destination |

These are two physical host roles, not two copies of every service. The gateway
and memory owners remain singular. This decision does not relocate them or
activate additional capture engines. Native authentication stores, histories and
credential databases never travel through source synchronization.

## Runtime and model contract

| Runtime | Final role | Acceptance boundary |
| --- | --- | --- |
| Codex CLI and its native SDK/app-server surfaces | Default engineering coordinator and workers; Sol Ultra | Native auth, caching, compaction and tool behavior; configuration readback does not establish an executed model |
| Claude Code | Native companion for research, review and task-appropriate work under the existing Claude policy | Preserve its own model/effort, authentication and native orchestration; a GPT worker does not change Claude's model |
| GPT-6 Astra | Bounded specialist when a recorded trigger warrants it | Give one concrete question and acceptance criterion; no automatic whole-task escalation |
| OpenAI Agents SDK / OpenAI client SDK | Application code requiring structured tools, events, handoffs or sessions | Route through explicit OmniRoute configuration; no silent direct-provider fallback; native Ultra is not an API enum |
| Pi | Optional extensible SDK/RPC worker, retained at trial status | Use only for a task needing Pi's extension or process-control surface; current upstream review does not promote its older trial |
| Other harnesses | Existing task-specific alternatives, including OpenHands or durable workflow frameworks | No blanket installation or additional orchestrator; select only for a demonstrated application or recovery requirement |
| Evaluation | Existing project tests first; promptfoo for gateway comparisons, Inspect/Harbor for applicable agent evaluations | Use the upstream harness and a frozen oracle; synthetic success, model execution and host acceptance remain distinct |

The [official native model guidance](https://learn.chatgpt.com/docs/models#gpt-61-sol)
supports Sol reasoning through Ultra, subject to account/client availability.
Standard and Fast are available; Ultrafast support is described as forthcoming.
The [API model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
instead lists `low`, `medium`, `high`, `xhigh` and `max`, and requires
Responses for tool calling. Match the actual endpoint's schema and verify the
effective upstream route; never translate a native UI label by assumption.

For this user's two-host task, explicit Sol/Ultra worker selection supersedes
the older general Sol/Max worker default in the
[September 30 routing record](2026-09-30-sol-primary-quality-defaults.md).
On a supported native client, the portable launch is:

```sh
codex -m gpt-6.1-sol \
  -c 'model_reasoning_effort="ultra"' \
  -c 'agents.default_subagent_model="gpt-6.1-sol"' \
  -c 'agents.default_subagent_reasoning_effort="ultra"' \
  -c 'service_tier="default"'
```

The same overrides followed by `features list` loaded successfully on macOS
Codex 0.160.0 without a generation request. That is a configuration/CLI check,
not inference or workstation acceptance. The attempted
`codex --strict-config features list` exited 1 because that subcommand does not
support `--strict-config`; the failed attempt is retained, not counted as passed.

The Mac parent defaults were corrected from Astra/low to Sol/Ultra; its generic
worker defaults already selected Sol/Ultra. The incompatible Ultrafast override
was removed. A later safe readback observed the native default tier written
explicitly as `default`; its writer was not attributed and that later setting
was preserved. TOML parsing, the CLI read, file mode and targeted-byte checks
were verified. This does not alter the model of an already-running session.

## Current sources, accepted pins and upgrade decisions

Fresh upstream metadata is a source-review input. Repository locks, dated host
receipts and the latest upstream release are separate facts.

| Component | Observed or accepted baseline | Current official source reviewed | Disposition for starting R&D |
| --- | --- | --- | --- |
| Codex | Mac binary 0.160.0; main stack manifest still 0.159.3 | [0.160.0](https://github.com/openai/codex/releases/tag/rust-v0.160.0), October 1 | Use installed native client; reconcile source pin through its owner, without transferring older execution claims |
| Claude Code | Mac binary 2.1.287; main stack manifest 2.1.284 | [2.1.287](https://github.com/anthropics/claude-code/releases/tag/v2.1.287), October 1 | Retain native installation and companion policy; new-host acceptance remains local |
| Shared memory | Mac owner ai-memory 2.5.2; older main component lock 2.4.1 | [2.5.2](https://github.com/akitaonrails/ai-memory/releases/tag/v2.5.2), October 1 | Retain one existing owner; lifecycle and comparative quality limitations remain |
| Local inference | Retained Mac Ollama 0.34.4 | [0.35.0](https://github.com/ollama/ollama/releases/tag/v0.35.0), September 28 | Retain measured control; decision-model additions do not prove memory-profile compatibility |
| Pi | Open [PR 524](https://github.com/seathatflowsinourveins/native-agent-stack/pull/524), 0.99.1 trial | [1.0.0](https://github.com/earendil-works/pi/releases/tag/v1.0.0), October 1 | Optional trial; package identity, runtime and SDK-extension changes need affected acceptance before upgrade |
| Agents SDK | Prior scoped OmniRoute check used 0.22.3 | [0.23.1](https://github.com/openai/openai-agents-python/releases/tag/v0.23.1), October 2 | Preserve the accepted lock until an application needs the update |
| OpenAI Python | Prior scoped OmniRoute check used 3.23.0 | [3.24.0](https://github.com/openai/openai-python/releases/tag/v3.24.0), October 2 | Review request-routing changes in the actual gateway adapter before an update |
| RTK | Retained 0.50.0 integration | [0.51.0](https://github.com/rtk-ai/rtk/releases/tag/v0.51.0), October 2 | Hold upgrade until argument boundaries, explicit shell scripts, hooks and exit-code preservation pass |
| QMD / Context Mode | 2.8.3 / 1.0.169 | [QMD 2.8.3](https://github.com/tobi/qmd/releases/tag/v2.8.3), [Context Mode 1.0.169](https://github.com/mksglu/context-mode/releases/tag/v1.0.169) | Retain scoped retrieval/output handling; no new index or global rewrite |

The runtime choices above are a dated, evidence-backed operating selection.
They are not a claim of global comparative superiority or full-stack readiness.
Hindsight/coding-agents remain isolated. No memory replacement, provider-model
trial, frozen unsafe benchmark or new service was started by this unit.

### Pi compatibility is explicit

The old `badlogic/pi-mono` locator redirects to
[earendil-works/pi](https://github.com/earendil-works/pi).
At 1.0.0 the package is
[`@earendil-works/pi-coding-agent`](https://github.com/earendil-works/pi/blob/v1.0.0/packages/coding-agent/package.json)
and requires Node >=22.19.0. Use official pinned registry/release artifacts,
with a lock and digest, when a future task activates it.

[SDK integration](https://github.com/earendil-works/pi/blob/v1.0.0/packages/coding-agent/docs/sdk.md)
is in-process TypeScript; [RPC](https://github.com/earendil-works/pi/blob/v1.0.0/packages/coding-agent/docs/rpc.md)
is a long-lived JSONL subprocess interface. SDK sessions do not automatically
load the CLI's built-in codemode, tool-search and MCP extensions: register and
bind them through the documented API when required.
[Provider login](https://github.com/earendil-works/pi/blob/v1.0.0/packages/coding-agent/docs/providers.md)
belongs to Pi's own provider configuration; it is not proof of transferable
Codex or Claude authentication.

The [0.99.1 trial at its exact revision](https://github.com/seathatflowsinourveins/native-agent-stack/blob/530238710157c6160741a0e9b9f757aecda0a726/blueprints/convergence-practice/pi-omni-trial-20260929/README.md)
records 28 successful small fixture runs through OmniRoute, including one
interrupted/resumed run. It also records higher token use with the added stack,
confounded cache comparisons and no savings conclusion. Those historical
results neither accept 1.0.0 nor justify replacing the native default.

## Coverage of the complete foundation

All twenty foundation layer IDs keep a clear role. Existing catalogs and
receipts remain the detailed authority; this table does not relabel optional
or partial acceptance as complete.

| Layers | Role in the final architecture |
| --- | --- |
| native-clients; workers | Native Codex/Claude, explicit Sol Ultra task envelope and bounded specialists |
| instructions-skills | Small canonical instructions; relevant pinned skills loaded on demand |
| isolation; git-github-automation | Owned checkouts, native restrictions where needed, GitHub-reviewed integration |
| code-navigation; document-retrieval; semantic-rag | Exact source first; scoped graph/QMD/semantic retrieval only with coverage and source verification |
| durable-memory | One scoped memory owner plus versioned canonical decisions |
| web-research | Primary sources and authorized native browser research with provenance |
| token-efficiency | Native caching/compaction, Context Mode and RTK; measured savings only |
| agent-sdks; mcp-surfaces | Explicit SDK/gateway boundary and task-scoped native MCP registration |
| quality-evaluation; ci-supply-chain | Independent deterministic oracles, upstream harnesses, locked artifacts and repository checks |
| scheduling-supervision; hosting-services | Existing owned job/service lifecycle only when the project needs it |
| recovery-portability; observation-inference | Checkpoints, restore and cancellation evidence; truthful telemetry and local-runtime scope |
| secrets-credentials | Native per-host sign-in and scoped secret delivery; no credential replication |

## North Star execution order

1. **Offline implementation now.** Preserve the frozen LEAN oracle and
   tolerances; implement `costs_and_rounding_stress` for `one_stress` in
   `blueprints/us-equities/engine-nautilus/spy-parity/` with its existing
   tests. Resolve the current trading writer before editing the shared task.
   The latest source handoff did not identify that writer, so this foundation
   unit does not overwrite the implementation checkout.
2. **Workstation activation before workstation execution.** Its owner records
   the surviving environment, exact source and pinned artifacts; verifies
   native auth/model/effort, required Python/engine compatibility, storage,
   cancellation and restart; then executes the frozen scenario there. GPU
   acceptance is needed only for a workload that actually uses the GPU.
3. **Research data and simulation.** Immutable raw snapshots, Parquet/DuckDB
   and exchange-calendar-aware features follow the existing
   [North Star blueprint](../../blueprints/us-equities/north-star.md).
   Models propose research; deterministic code owns numeric, risk and order state.
   Extend the remaining four margin/adaptive cases separately.
4. **Broker-specific paper acceptance.** Follow the
   [current acceptance plan](../../blueprints/us-equities/engine-nautilus/acceptance-plan.md)
   and [paper policy](../paper-lane-policy.md). IBKR step 1 is historical
   read-only acceptance; steps 2–4 remain open. The historical Alpaca
   roundtrip does not establish in-flight fault recovery or continuous operation.
   Live trading remains a separate scope.

### Validation, limits and overturn conditions

At source baseline `18eea2c1`, `python3 scripts/validate.py` passed its
integrity/scope checks: 69 components, 9,315 hashed files, four profiles and
186 receipts. In an owned clean checkout, with an owned sibling `TMPDIR`
outside the repository,
`python3 -m unittest tests.test_spy_parity -v` passed 179 tests, exit 0.
These are repository/synthetic checks. No separate engine, broker, GPU or
candidate-model execution was launched; the research workers' provider activity
is outside those check counts.

Three bounded research workers returned useful interim source findings, then
hit the provider usage limit before their final handoffs. This unit therefore
does not claim a completed independent review or new blind cross-family
convergence. Whole-task token cost, failed-attempt usage and net savings remain
unknown. The preserved historical native and SDK receipts retain their own
revisions and scopes; this closeout does not add their counts together.

A concrete workload failure, a demonstrated compatibility/security fix, or a
matched representative comparison can reopen the relevant component decision.
It does not reopen the entire ecosystem by default. Workstation identity,
native lifecycle, model-route settlement and full-stack readiness remain
separate acceptance facts. No new experiment is queued by this decision.

Rollback of this source change is its documentation commit. The private Mac
receipt records the exact targeted configuration change and prior values;
rollback must preserve any subsequent unrelated edit. The previous Astra/low
values are historical rollback data, not the selected operating policy.
