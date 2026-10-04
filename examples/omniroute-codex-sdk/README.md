# Native Codex SDK worker through OmniRoute

For task-selected MCP, native child agents and automation, use the
[native enhancement kit](enhancements.md) and its metadata readiness gate.
The [bounded live acceptance](../../evidence/receipts/omniroute-runtime-enhancements-20260930.json)
covers selected skill/MCP use, one Astra/Max judge and a completed Dagu graph.

This foundation worker can be called from a native Claude coordinator. It uses
the maintained Codex harness through the official Python SDK, with Sol/max as
the primary worker and an invocation-scoped OmniRoute Responses provider.
The existing Codex integration remains the incumbent; this example does not
select a winner in the separate SDK comparison.

The [October 3 refresh receipt](../../evidence/receipts/omniroute-sdk-worker-0160-20261003.json)
records current 0.160.0 checks. September 30 receipts below retain their original
0.159.2 execution and are historical evidence.
The builder's nested Codex sandbox caused two shell startup failures; the
coordinator's separate non-nested read-only run completed one shell command
with exit 0 and output `13`, as retained in the refresh receipt.
The builder's completed task also retained one MCP `Transport closed` failure;
writing (`workspace-write`) dispatch is not yet qualified at 0.160.0.

## Call from a native Claude coordinator

The PEP 723 scripts and adjacent locks pin `openai-codex==0.160.0`, including
its matching native CLI. In the native Claude session, use its `Bash` tool to run
the following command from the repository root. `WORKER_PROJECT` is the owned
task worktree with the selected project `.agents/skills`; `PRIVATE_WORKER_HOME`
is an existing independent private Codex configuration/state directory prepared
through the selected adoption recipe. `WORKER_TASK` contains the bounded task
and its artifact/test contract. Pass only that task, not the coordinator's whole
conversation. `PRIVATE_NATIVE_RESULT` names a new private artifact path.

```sh
rtk uv run --locked --script examples/omniroute-codex-sdk/worker.py \
  --workspace "$WORKER_PROJECT" \
  --codex-home "$PRIVATE_WORKER_HOME" \
  --prompt "$WORKER_TASK" \
  --native-result "$PRIVATE_NATIVE_RESULT"
```

This subprocess contract scopes the provider to the SDK worker; native Claude
and Codex coordinator sessions retain their account routes and configuration.
Source: [Claude native Bash/tool usage](https://code.claude.com/docs/en/overview),
the official SDK launch contract and the provider sources below. A source-backed
caller recipe is distinct from observing an actual Claude `Bash` invocation;
retain that native invocation before claiming Claude-side execution acceptance.

The [September30 native callsite receipt](../../evidence/receipts/omniroute-claude-callsite-20260930.json)
now retains that observation: native Opus5.5/Max discovered and read the project
dispatcher, called this worker through Bash, and the full native SDK result
shows one unchanged `npm test` command with exit0. This bounded read-only call
qualifies the caller path; the separate Claude SDK gateway bridge remains a trial.

The default endpoint is the selected loopback gateway at port 20128. An owned
reverse observer can be supplied with `--base-url`; the worker never changes
gateway compression engines or native coordinator configuration. The default
model is the explicit `cx/gpt-6.1-sol-max` route, with native reasoning effort
`max` requested at launch and turn start. This route requires an OmniRoute build
carrying [PR #15167](https://github.com/diegosouzapw/OmniRoute/pull/15167);
published 3.8.51 alone does not establish that capability. Check the live
`/v1/models` catalog for the exact route before dispatch. Client-requested effort,
gateway-forwarded effort and backend identity are separate evidence; the worker
does not verify the latter two. Preserving the native prefix is important for
cache reuse; no prompt rewrite, extra skill carrier or outer agent loop is added.

`--effort` accepts `max` and `ultra`, with `max` retained as the compatibility
default. Ultra requires a suffixless model. Add
`--model cx/gpt-6.1-sol --effort ultra` to the command above or to
a resumed invocation to select native Ultra. The worker passes the selection to
its child launch configuration and the SDK's native `ReasoningEffort` at turn start, and emits
it as `requested_effort`. The worker preserves accepted model and effort inputs;
the default model remains `cx/gpt-6.1-sol-max`. The checked OmniRoute HTTP carry
prioritizes force rules, then recognized model suffixes, then body effort.
Before native startup, the worker rejects Ultra with an effort-bearing model
ending in `-none`, `-low`, `-medium`, `-high`, `-xhigh`, `-max`, `-ultra`, `(max)`
or `(ultra)`, following the pinned suffix parser below. This includes the default
model paired with `--effort ultra`; supply the suffixless model explicitly.
Qualify the gateway's installed build and force rules separately.

Native model metadata controls ordinary inference normalization. The bundled
Sol6.1 metadata maps Ultra to `xhigh`; other models can resolve it differently.
Native orchestration mode depends on V2 and its native hint/catalog messages.
A preflight `effective_config.model_reasoning_effort` value records native
config-read selection; delivered effort and active orchestration require
separate observation. See the pinned effort and orchestration sources below.

Pass one bounded task on stdin. The worker emits a compact `thread_ready` JSON
line before the turn, then a result with the final answer, item counts and native
usage. To retain the actual full tool items, add `--native-result` with a new
private output path. The writer reserves it with `O_EXCL` and mode 0600 before
SDK startup or thread creation, so an existing destination refuses before the
turn. It fills the file with the completed native result, or a sanitized failure
record if the operation fails before completion.
Raw tool output and private thread IDs stay outside public evidence.

`--sandbox workspace-write` and `--approval-mode deny_all` are the defaults:
native tools can work within the selected sandbox, and approval requests are
denied. The supported `auto_review` mode is available for a caller that has
qualified its native approval reviewer and accounting. This is separate from an
explicit Astra judgment stage. The worker preserves existing native MCP/tool
configuration; an empty private Codex home does not qualify those integrations.

Use `--codex-bin` only for an explicit matching native 0.160.0 binary. An omitted
`--codex-home` inherits the native home; supplying it scopes worker configuration
and recoverable state to the child process. The example neither reads nor copies
authentication stores. The selected keyless loopback gateway owns its upstream
account handling; for another accepted gateway configuration, `--api-key-env`
names an existing credential variable without accepting or printing its value.
The worker excludes that validated name through native
`shell_environment_policy.filters` and disables shell snapshots for the keyed
child; the starter home also excludes `OMNIROUTE_API_KEY`. It enables both the
custom provider's `supports_standalone_web_search` capability and the native
`standalone_web_search` feature, matching the repository's OmniRoute profile.
These settings preserve the native search path; provider endpoint readiness
still needs its own live qualification.

## Resume, judgment and recovery

Retain the native thread ID privately and resume with the same project, worker
home and route:

```sh
rtk uv run --locked --script examples/omniroute-codex-sdk/worker.py \
  --workspace "$WORKER_PROJECT" \
  --codex-home "$PRIVATE_WORKER_HOME" \
  --resume "$WORKER_THREAD_ID" \
  --prompt -
```

Use Astra/max explicitly for consequential architecture, conflicting primary
evidence or a failure remaining after one bounded Sol repair. Record the trigger
and acceptance result with that task, then pass `--model cx/gpt-6-astra-max`.
Explicit model choices are retained; the example never silently retries with
another model or claims that an advertised model is an entitlement check.

One overall deadline bounds initialization, thread start/resume and the turn.
On a deadline the caller requests the native turn interrupt, then closes its SDK
child after its retained startup operation settles. If the cleanup bound expires,
it reports `cleanup_status="unresolved"` and exits nonzero; an embedding loop
can continue the owned cleanup while it remains running. Unknown usage stays
unknown. Native provider retries remain native;
`--no-provider-retries` disarms request/stream retries for a measured attempt.
The example runs one Python process per invocation and keeps persistent native
state available for resume. Cleanup terminates only its owned app-server child.

The runtime overrides and starter home set `features.plugins=false`, because
this worker uses native skills and MCP rather than plugins. This directly gates
the curated-plugin startup sync, including its Git/HTTP fallback paths. It removes
plugin-provided skill roots; native project and user skill discovery remain.
The [dated decision](../../docs/decisions/2026-10-03-omniroute-sdk-worker-0160.md)
compares the remote-auth and requirements-policy alternatives. This setting and
direct PID observations do not certify global network isolation or descendant
cleanup.

After a terminal `content_filter` stop, explain the limitation and choose a
permitted alternative or unrelated authorized task. Resume the same thread only
for that explicit continuation, retaining native filter guidance. The wrapper
does not automatically resubmit the blocked task or create a fresh thread to
discard its guidance. Native retries may add guidance to the persisted prefix.

## Skills and token practice

For installing or activating selected skills, use
[the existing lifecycle](../../adoption/skills/lifecycle.md) and
[the runtime-worker skill recipe](../../blueprints/runtime-workers/skills/README.md).
Use the selected installer and manifest rather than another skill loader. Codex
discovers project `.agents/skills` and applies its native skill description and
invocation policies. A Claude-only bridge read explicitly by a worker is an
explicit read, not proof of Codex implicit discovery. Keep the availability,
actual instruction read and task outcome as separate observations.

RTK, context-mode and other selected tools follow their existing task conditions
and native configuration. Load the selected `SKILL.md` before using its workflow;
do not preload every skill body or enable every optional MCP service. The example
sets context-mode's existing project-directory carrier only for its child.

The emitted `usage.total` is a cumulative native thread snapshot, including past
turns on resume. `usage.last` is the last model response, not a complete multi-call
turn sum. Count the latest cumulative snapshot once, or difference comparable
snapshots. Cached input and reasoning output are subsets; never add them again.
These native snapshots do not establish complete gateway/provider usage, cache
billing, backend identity or a measured compression benefit.

## Local checks and their limits

```sh
rtk uv run --locked --script examples/omniroute-codex-sdk/test_worker.py
```

These authored local integration fixtures use the real pinned SDK and native CLI
against an authored loopback SSE provider. They check request model/effort,
own-request headers, native tool carriage, stable cache/prefix identity across
ordinary resume, cumulative counters, deadline interruption, kernel-observed
direct app-server PID exit and private original-result retention. Six preflight
tests cover native MCP/skill/role discovery, missing/disabled/empty/error catalogs,
metadata deadlines, CLI requirement rules and compact output. Runtime-version
rejection uses the current SDK pin in its negative control. A gateway-config guard
keeps `model_catalog_url` absent, and a content-filter fixture checks terminal
failure and one/six retained guidance items with native retries disabled/enabled.
The production override is asserted directly and exercised in a fixture home
without a `[features]` table. Delayed real native startup fixtures cover both
worker and preflight deadlines, including an unresolved cleanup bound. A
post-turn read failure preserves the completed native result already saved.
Six additional B3 tests cover the gateway credential filters and search switches
in the process overrides/starter template, refusal of an existing native-result
destination before thread creation, and a private failure record after an
incomplete turn.
The effort checks use native config-read for both selections, observe the
unchanged SDK turn receiving its native enum, and inspect the synthetic wire
request after model-owned normalization. Start/resume subtests include starting
with the default Max route, then resuming that thread with
`--model cx/gpt-6.1-sol --effort ultra`. They observe the real thread read passing
the worker's model/provider check, the resumed `requested_effort`, native
`ReasoningEffort.ultra` turn argument and normalized wire effort `xhigh`.
These fixtures retain the real pinned SDK/CLI and return authored SSE responses;
they do not qualify model switching at a live gateway. Argument checks reject
invalid effort and Ultra with every listed effort suffix, accept suffixless
Ultra, and retain the default/resume `max` behavior. The suite contains 30 tests.
The other fixture homes also disable plugins, and teardown checks that no
`.tmp/plugins-clone-*` directories remain. No descendant-process or global egress
assertion is made. Missing terminal events and an
unsupported `wire_api` are discriminating negative controls. They are not
unchanged upstream tests, live model runs or a full SDK/framework comparison.

The first local oracle failed with `KeyError: 'tools'`. Original tagged source
and actual wire inspection corrected it: Sol/Astra use native ResponsesLite,
which carries `input[].type=additional_tools`; absence of a top-level `tools`
field does not mean tools are absent. Those prefix item IDs hash visible payloads
within the thread. Absent a `content_filter` stop, ordinary resume preserves the
tested cache key and tool prefix. Filter recovery can add developer guidance and
change the input prefix. The corrected
oracle checks that native form and preserves it unchanged.

The pinned SDK emits `ResourceWarning` for unclosed stdout/stderr handles in
repeated same-Python-process fixture calls. Its native `close()` closes stdin,
terminates/waits for its app-server and joins readers; it does not explicitly
close stdout/stderr. The standalone invocation and kernel PID checks observe
direct app-server exit in the tested cases; descendant cleanup remains
unobserved. A long-running in-process SDK pool is not qualified by
this example. Four expected argparse usage blocks come from explicit CLI
rejection controls; ResourceWarnings and those blocks are retained in acceptance
output. Optional `auto_review`, a long-lived SDK pool and a scheduled Dagu run keep
their own acceptance gates. The existing upstream qualification also retains its one unrelated
formatter-driver test failure; no whole-suite passing claim is made here.

## Sources and installation

- [openai/codex `rust-v0.160.0`](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python),
  immutable commit `a956835d020762cb2b570053af06f643a11c0ecc`: maintained SDK,
  its constructor/resume/turn-control examples and native installation commands.
- [SDK transport/configuration](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/client.py)
  and [native provider fields](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/model-provider-info/src/lib.rs):
  child-only CLI overrides, native lifecycle, Responses, headers and optional
  environment-key authentication.
- [Native effort enum](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/generated/v2_all.py#L3694),
  [SDK turn input](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/api.py#L724)
  and [unchanged enum serialization test](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/tests/test_client_rpc_methods.py#L267):
  native `max` and `ultra` selections through the maintained SDK API.
- [Native Ultra normalization](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/protocol/src/openai_models/reasoning_effort.rs#L10)
  and [native orchestration mode conditions](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/session/multi_agents.rs#L77):
  supported model-owned effort override, then native fallback, with orchestration
  separately conditional on V2 and native hint/catalog messages.
- [OmniRoute effort precedence](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/open-sse/executors/codex.ts#L1414)
  and [recognized model suffixes](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/open-sse/executors/codex/reasoningSuffix.ts):
  force rule, then model suffix, then body effort at the declared owner carry;
  input selection alone does not establish its installed state or actual delivery.
- [Native namespaced model matching](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/models-manager/src/manager.rs#L873)
  and [bundled model metadata](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/models-manager/models.json):
  the single `cx/` namespace and `-max` suffix retain the longest-matching native
  Sol/Astra capability row; this does not attest the gateway's backend routing.
- [Native ResponsesLite prefix assembly](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/client.rs#L902)
  and [SSE fixture helpers](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/tests/common/responses.rs#L753):
  native tool/prefix preservation and the source of the authored local fixture.
- [Published SDK 0.160.0](https://pypi.org/pypi/openai-codex/0.160.0/json): wheel
  SHA-256 `61d2d855ca2ebedfd51280fbeb60ff31fc47ccbd55ebce186505e3f3da096921`.
  The adjacent locks are generated by supported `uv add --script` and
  `uv lock --script` commands; execution uses `uv run --locked --script`.
- [Historical September 30 SDK installation and source qualification](https://github.com/seathatflowsinourveins/native-agent-stack/blob/404b821cd3af25800ea418dc6145cc5cb6fe33c5/evidence/artifacts/runtime-sdk-20260930/receipt.json):
  preserved matching SDK/CLI pins, native custom-provider reference,
  21 unchanged published Python source files at 0.159.2 and retained upstream
  test results. Those results do not qualify the 0.160.0 wheel or runtime.
- [Pinned curated-plugin sync gate](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core-plugins/src/manager.rs#L743-L763)
  and [boolean feature schema](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/config.schema.json#L7038).
- [Content-filter guidance and native retries](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/responses_retry.rs#L66-L171).

Preflight relies on exactly pinned SDK internals (`AsyncCodexClient` and generated
request types), which are excluded from the package-root public API. The PID
observations also use pinned private attributes and must be rechecked on every
pin move. OpenAI describes the Python SDK as a stable release while its underlying
[app-server command remains experimental and unsupported for production workloads](https://learn.chatgpt.com/docs/mcp-server.md).
This example qualifies bounded research/integration work within that boundary.
