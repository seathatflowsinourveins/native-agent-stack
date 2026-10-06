# Worker defaults select the NativeStack2604 gateway

Date: 2026-10-06. Lane: foundation. Status: configuration selection locally
checked; native execution limits are recorded below.

Direction: command-center item `task-ns2604-coop-20261006T043449Z`, relayed in the co-op's scoped lane assignment.

The command center reported that NativeStack and NativeStack2604 share WSL
networking and that NativeStack uses loopback ports 20128 and 20129. The
canonical install-plan topology assigns NativeStack2604's gateway to
`http://127.0.0.1:21128/v1`. A worker's implicit 20128 default could therefore
select the other distribution's service. This fix serves the north-star action
of routing bounded foundation/trading engineering jobs to their intended host.

All three standalone Python examples read the checked-out plan's nonsecret
`config/gpt-gateway-topology.json` field `gateway.endpoint`, which is already
present on main at ecfa11276. A46's checked-out reader and the Promptfoo endpoint
reader are source proposals in open draft #723 at 84c79f7f. This implementation
reads main's canonical data directly. Missing, malformed or legacy-20128/20129
topology defaults fall back to 21128. The candidate
uses the Codex worker's existing port-qualified HTTP loopback `/v1` contract.
Explicit endpoint overrides retain their existing behavior. DeepAgents'
configuration description reports the selected default as its underlying lane.

The alternative was replacing the two literals alone. Reading the canonical
field keeps future approved topology changes in one place while retaining a
portable fallback for copies of the examples without that asset. Topology path
lookup occurs inside the guarded default reader, so a shallow copy such as
`/worker.py` also reaches the fallback. The skill's commands use that guarded
default. Every NativeStack2604 invocation explicitly passes its 21128 flag,
regardless of reader revision, and both model-free gateway preflights precede
dispatch. Current skill/README commands follow that rule; Claude uses its native
Anthropic-root `--gateway` flag. The reader remains a fallback.
Historical trial plans and receipts keep their original addresses.

At the initial reviewed head 1942acb12, four fixture tests executed the actual Codex argument parser and DeepAgents
configuration-description branch with inert SDK/provider imports. They cover
canonical and missing topology, a configured alternate endpoint, explicit
overrides, legacy 20128 and malformed JSON/URL fields. Provider/runtime
constructors are forbidden in those tests. This is local/synthetic
configuration evidence, not native provider acceptance.

At that initial head, two existing cases also passed with the real pinned SDK and bundled CLI:
runtime configuration and native metadata preflight/catalog cleanup. The
preflight asserts no model inference and no gateway HTTP requests. These are
repository integration tests with synthetic catalog/observer fixtures, not
unchanged upstream tests. Two unclosed-file ResourceWarnings occurred in that
passing native run and are retained. The initial default-loader review found
a missing malformed-URL case; it was corrected using the existing URL contract
and rechecked before the initial publication. Those returned observations remain
in the receipt. The P3 corrections add 20129 rejection and a shallow-copy import
fixture. The root's separate recheck passed all five configuration cases in
0.045s and both bounded real SDK/CLI metadata cases in 1.036s. The native run
again returned two unclosed-file ResourceWarnings; no resource-closure,
provider or unchanged-upstream acceptance claim follows.

The stale-default inventory also found
`examples/omniroute-codex-sdk/enhancements.md:6,86-87` and the two explicit
`WORKER_BASE_URL` arguments in `runtime-worker.yaml:20,29` at ecfa11276.
The fold corrects the documented normal binding to 21128 and marks it required
in the graph. Both commands still honor deliberate caller overrides. A focused
fixture renders each actual command with the documented binding and exercises
the real CLI parser; it fails against the former 20128 binding. This is
configuration coverage, not a new Dagu graph execution.

A root-env `${WORKER_BASE_URL:-...}` default was considered but rejected:
pinned Dagu leaves unavailable variables unresolved before operator expansion.
The supported required-binding recipe avoids claiming an unset-variable
default. The earlier fold left the Claude bridge default for a scoped follow-up.
The token-audit assignment now adds its canonical topology reader, 21128 fallback
and explicit `--gateway` override. It removes `/v1` from the OpenAI-shaped endpoint
because Claude appends `/v1/messages` to its root. Another owner-scoped default,
`tools/sota-convergence/landscape-sweep/build_args.py:116,696` retains both its
20128 default URL and fallback host. These source paths are at ecfa11276.
Historical trial plans and receipts remain historical evidence. The proposed
Claude route in open draft #723 still awaits its canonical owner's decision.

The same bounded assignment adds supported census markers to DeepAgents and the
Claude SDK bridge. LangChain `default_headers` and Claude's official
`ANTHROPIC_CUSTOM_HEADERS` through SDK `options.env` send the gateway-native
`X-OmniRoute-Session-Id`. Prefixes `nas-deepagents-omniroute-` and
`nas-claude-runtime-sdk-` plus fresh UUID hex fit the pinned gateway's 128-character
cap and persist as `call_logs.session_tag`. Each DeepAgents model keeps its own
configured census tag; Claude keeps one fresh invocation tag. Stable global tags
and arbitrary unpersisted headers were rejected. Distinct model tags and call
attempts are not worker-invocation counts.

Review correction, 2026-10-06: the earlier inference that distinct census tags
guarantee separate reasoning-replay scopes was too strong. At the pinned gateway,
`reasoningReplaySessionKey` uses `sessionAffinityKey` before the marker fallback;
the affinity selector recognizes other session headers or body/input-derived
keys. Narrow the claim to distinct configured tags and source-supported census
attribution. Effective replay isolation and live delivery remain unqualified;
no affinity header or routing behavior is added. Original fixture outputs and
failed attempts remain recorded. The earlier shared-tag fixture was superseded
for marker uniqueness; it was never a native proof of replay isolation.

Eight current synthetic configuration checks and all 26 existing repository
Claude SDK integration cases pass. The native upstream wheel is installed only
in task-private uv state, without building. Its bundled CLI reports 2.1.285,
above the official header interface's 2.1.227 minimum. An initial offline-cache
attempt failed and is retained; the private install and later offline check
passed. No gateway/model request was made. Live marker persistence remains an
after-relaunch qualification, not an inference from constructor fixtures.

Overturn the fallback when the command center adopts a different canonical
NativeStack2604 endpoint. Requalify default selection when the topology schema,
worker packaging path or URL contract changes. A different model route,
requested effort, gateway release, provider identity or live-provider success
requires its own acceptance; this change qualifies configuration selection.

Sources:

- `native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:evidence/artifacts/new-wsl-install-plan-20261002/config/gpt-gateway-topology.json:2,9` defines the schema and endpoint.
- `native-agent-stack@84c79f7f92f61972a46aa470a4f299017bc82768:evidence/artifacts/new-wsl-install-plan-20261002/accept.sh:2596` reads the checked-out asset for SkillSpector; it selects a model, not an endpoint.
- [Endpoint reader in open draft #723](https://github.com/seathatflowsinourveins/native-agent-stack/blob/84c79f7f92f61972a46aa470a4f299017bc82768/evidence/artifacts/new-wsl-install-plan-20261002/config/promptfoo-gateway.cjs#L8) selects `gateway.endpoint`; it is a pinned source proposal.
- [Python 3.13 pathlib parents](https://docs.python.org/3.13/library/pathlib.html#pathlib.PurePath.parents) defines the indexed ancestor sequence used by the guarded lookup; [path joining](https://docs.python.org/3.13/library/pathlib.html#operators) preserves explicit absolute topology fixtures.
- `native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:examples/omniroute-codex-sdk/worker.py:92` provides the existing URL contract.
- [Dagu value-resolution specification](https://github.com/dagu-org/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/specs/006-value-resolution-env.md#L393) and [undefined-variable handling](https://github.com/dagu-org/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/internal/cmn/value/expand.go#L146) support the required root-env binding.
- [Pinned Codex SDK](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python) and the existing `native-agent-stack@ecfa11276:examples/omniroute-codex-sdk/test_worker.py:502,774` support the bounded native configuration/preflight checks.
- [Pinned DeepAgents API](https://github.com/langchain-ai/deepagents/tree/4394bcd00b8eb46e7c423939643a0dfcfb5d8773) and [LangChain OpenAI base_url](https://github.com/langchain-ai/langchain/blob/026c3da2b615abe52f8446e37de460b844d07a43/libs/partners/openai/langchain_openai/chat_models/base.py) remain the example's supported runtime APIs.
- `langchain-ai/langchain@026c3da2b615abe52f8446e37de460b844d07a43:libs/partners/openai/langchain_openai/chat_models/base.py:1016,1464-1468` supports request default headers.
- `anthropics/claude-agent-sdk-python@f2204bb956bab02907aaf3cb88eb9dead28eaa35:src/claude_agent_sdk/types.py:2124-2127;_internal/transport/subprocess_cli.py:819-825` passes worker-scoped environment. [Official Claude header interface](https://code.claude.com/docs/en/env-vars), read 2026-10-06.
- `diegosouzapw/OmniRoute@2f42a9ac19d1a247ec9ce5473b790843724b3061:open-sse/services/conversationTracker.ts:453,462-468;open-sse/handlers/chatCore.ts:1082-1095,1127-1133;src/lib/usage/callLogs.ts:741,804-821,995-996` defines marker handling, persistence and filtering; `src/sse/services/sessionAffinityPin.ts:197-215` plus `chatCore.ts:1093-1095` refute guaranteed replay isolation from those tags. [UUID generation](https://docs.python.org/3.13/library/uuid.html#uuid.uuid4) supplies distinct identifiers without credential or path content.
