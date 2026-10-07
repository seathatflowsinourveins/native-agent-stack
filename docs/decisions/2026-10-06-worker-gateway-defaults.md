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

## Amendment (2026-10-07): contract v2

The command center's reviewed gateway-default plan revision 3.1 supersedes the
topology-reader and literal fallback selection above for runtime holders. The
original 124 lines remain unchanged at `e2c569b52c79356d3d5a4ba9a80fee62b359e741`,
SHA-256 `5b19c7ce457a23391beac9f6f02b8ed8ac2576880b72b4997125049e50dfe96e`.
This is a contract decision and implementation amendment. Its fixtures, host
activation, launch-context proof cells, effective-endpoint read-back and live
provider qualification remain separate evidence; this section claims none ran.

The selected rule is one host record and one contract in every gateway holder.
The shipped `tools/omniroute/host_gateway.py write` activates
`<passwd home>/.config/agent-stack-host/gateway.json` only after verifying exactly
one IPv4 listener on the exact address, a visible owning PID and, when named,
membership in the gateway unit's cgroup. A free port cannot establish ownership.
The record binds its endpoint to the host name and the installation's machine-id
hash. Missing, malformed, unreadable or foreign records refuse; a missing or
invalid installation identity also refuses. Darwin remains deferred until a
cited installation identity is reviewed.

A normal invocation takes its endpoint from that record. An explicit endpoint
equal to the record is accepted; another endpoint requires
`--unrecorded-gateway-reason TEXT`. Each holder checks its own gateway-variable
tuple through the same rule. Unexpanded placeholders and conflicting values
refuse. The record comes from the passwd home, independent of environment home
selectors or a distribution-name variable. A `--gateway-check` tripwire executes
before SDK imports; an old checkout rejects the option and stops the launch
chain. A normal run adds a bounded TCP probe. Spawned children carry loopback
`NO_PROXY`/`no_proxy`, and supported Python clients use `trust_env=False` and
`follow_redirects=False`. The Codex child must report the resolved effective
provider endpoint through `config/read` before a turn, both on start and resume.
A missing or mismatched key refuses: V2 has no waiver or residual success path.

The contract covers the Codex, DeepAgents and Claude example workers; the trading
native worker and Astra router; the landscape-sweep stager and executor; the host
tool; the OpenHands host-side holder family; the token snapshot reader and
gateway-record observer. Shell research, observability rendering, Codex lane
installation and new-host rendering delegate to the shipped tool. The final
holder registry and parity checks are a retirement prerequisite; a new holder
must be registered rather than inheriting an unexamined route. Native-provider
paths without a loopback endpoint read no gateway record.

K2's earlier rejection of a mandatory per-host template placeholder at
`native-agent-stack@0d5e6506434fab598dee861c749a22e628beb75a:docs/decisions/2026-09-26-codex-worker-lane.md:339-340`
is overturned on this date for runtime holders: sharing a loopback made an
upstream default inadequate authority for host selection. K2 remains in force
for the source template's bytes. The reviewed client and lane renderers rewrite
that template from the activated host record and preserve its match rule. This
scope does not change native coordinator accounts or make generic client
configuration a runtime route selector. The similarly named K2 launch-context
cell in the plan means the hcom/tmux pane; it is a separate identifier.

The convergence compared three designs. A's portable host-written record won
with C's tripwire, negative controls and listener/connect acceptance. B's minimal
host-class/topology-reader delta retained host-specific classification and
fallback authority. C's per-run kernel ownership selection embedded this PC's
ports, unit names and topology path in shared code. Its blocking soak conflicted
with the owner's rule. Contract v2 instead verifies ownership when publishing
and accepting the record; runtime callers read the record and probe the resolved
endpoint. No local trial or waiting interval establishes adoption.

The GPT judge's P1 findings are mapped to the reviewed plan's requirements:

| Judge finding | Contract correction | Required proof; not claimed by this amendment |
| --- | --- | --- |
| #1 environment override ignored | Holder-specific variables, including `WORKER_BASE_URL`, are checked; unexpanded values refuse | T12, T14, environment matrix, P3a |
| #2 any listener accepted then IPv4 recorded | Exact IPv4 address, one visible PID and named-unit cgroup ownership | T16, P9 |
| #3 free port sufficient to publish | Own listener required; existing record preserved without `--replace`; atomic replacement | T16, H1 read-back |
| #5 child endpoint unenforced | Mandatory V2 on start/resume; Codex-home checks and Claude settings precedence | T25, T17c/T17d/T17p, T27, P14/P15, GW-07 |
| #6 transport origin unconstrained | Child loopback bypass; supported Python clients disable environment routing and redirects | T17/T17d with zero skips |
| #13 retirement omits consumers | Registered holders, executable F-row read-backs and one disposition per host-copy group | P16, GW-05, GW-06 |

Overturn this selection if a host record is lost or overwritten more than once,
if a required worker account or sandbox cannot see its passwd home, or if GW-11
observes a foreign listener on a recorded port. The first condition reopens a
host-name-keyed repository table; the second reopens a system-owned record location;
the third reopens ownership enforcement. Requalification binds to the exact
reviewed code, activated host record, child endpoint and deployment. Retirement
keeps its pre-delete and post-unregister read-backs separate; a dated re-label
never replaces an executable consumer check.

Sources for this amendment:

- Reviewed gateway-default plan revision 3.1, sections 2.1, 2.5, 5 and 7;
  SHA-256 `8ce35229f4b1628e274675b1ab6fa283a240ecaf6ae9165e7dbe7fb7b6424cc3`.
  Its github-ci-finalize change set sections 2, 4 and 6 has SHA-256
  `e97a5a0d8014613213038b9fa5f83d2ba115350fc7861ba88ec78fdb3a4ab6fd`.
  These are approved design inputs, not executed proof receipts.
- The converged design's alternatives table, section 2, is superseded where the
  reviewed plan strengthens installation binding and mandatory V2 read-back.
- [Python 3.13 passwd lookup](https://docs.python.org/3.13/library/pwd.html#pwd.getpwuid)
  and [host name](https://docs.python.org/3.13/library/socket.html#socket.gethostname)
  supply the host-local lookup primitives; [systemd machine-id format](https://www.freedesktop.org/software/systemd/man/latest/machine-id.html)
  supplies the installation-identity format, read 2026-10-07.
- [Git grep at 2.53.0](https://github.com/git/git/blob/v2.53.0/Documentation/git-grep.adoc#L31) supplies the tracked-text
  scans in the legacy-port ratchet. It unions the main scope with the living
  new-WSL plan, preserving historical lines and reporting stale allowances.
- [Dagu 2.18.2 release](https://github.com/dagu-org/dagu/releases/tag/v2.18.2)
  is the plan's DAG pin. Unset-variable expansion and unit-context execution
  remain V10 until native observations establish them.
