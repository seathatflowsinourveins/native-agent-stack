# Native Codex SDK worker through OmniRoute

This foundation worker can be called from a native Claude coordinator. It uses
the maintained Codex harness through the official Python SDK, with Sol/max as
the primary worker and an invocation-scoped OmniRoute Responses provider.
The existing Codex integration remains the incumbent; this example does not
select a winner in the separate SDK comparison.

## Call from a native Claude coordinator

The PEP 723 scripts and adjacent locks pin `openai-codex==0.159.2`, including
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
`max` at launch and turn start. Preserving the native prefix is important for
cache reuse; no prompt rewrite, extra skill carrier or outer agent loop is added.

Pass one bounded task on stdin. The worker emits a compact `thread_ready` JSON
line before the turn, then a result with the final answer, item counts and native
usage. To retain the actual full tool items, add `--native-result` with a new
private output path. The writer creates it with mode 0600 and refuses overwrite.
Raw tool output and private thread IDs stay outside public evidence.

`--sandbox workspace-write` and `--approval-mode deny_all` are the defaults:
native tools can work within the selected sandbox, and approval requests are
denied. The supported `auto_review` mode is available for a caller that has
qualified its native approval reviewer and accounting. This is separate from an
explicit Astra judgment stage. The worker preserves existing native MCP/tool
configuration; an empty private Codex home does not qualify those integrations.

Use `--codex-bin` only for an explicit matching native 0.159.2 binary. An omitted
`--codex-home` inherits the native home; supplying it scopes worker configuration
and recoverable state to the child process. The example neither reads nor copies
authentication stores. The selected keyless loopback gateway owns its upstream
account handling; for another accepted gateway configuration, `--api-key-env`
names an existing credential variable without accepting or printing its value.

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
child. Unknown usage stays unknown. Native provider retries remain native;
`--no-provider-retries` disarms request/stream retries for a measured attempt.
The example runs one Python process per invocation and keeps persistent native
state available for resume. Cleanup terminates only its owned app-server child.

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
resume, cumulative counters, deadline interruption, kernel-observed owned-child
exit and private original-result retention. Missing terminal events and an
unsupported `wire_api` are discriminating negative controls. They are not
unchanged upstream tests, live model runs or a full SDK/framework comparison.

The first local oracle failed with `KeyError: 'tools'`. Original tagged source
and actual wire inspection corrected it: Sol/Astra use native ResponsesLite,
which carries `input[].type=additional_tools`; absence of a top-level `tools`
field does not mean tools are absent. Those prefix item IDs hash visible payloads
within the thread, so native retry/resume preserves their identity. The corrected
oracle checks that native form and preserves it unchanged.

The pinned SDK emits `ResourceWarning` for unclosed stdout/stderr handles in
repeated same-Python-process fixture calls. Its native `close()` closes stdin,
terminates/waits for its app-server and joins readers; it does not explicitly
close stdout/stderr. The standalone invocation and kernel PID checks bound the
owned process lifecycle. A long-running in-process SDK pool is not qualified by
this example. The existing upstream qualification also retains its one unrelated
formatter-driver test failure; no whole-suite passing claim is made here.

## Sources and installation

- [openai/codex `rust-v0.159.2`](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python),
  immutable commit `ff6aec96948b70d94983af2641a6b67c94faeff5`: maintained SDK,
  its constructor/resume/turn-control examples and native installation commands.
- [SDK transport/configuration](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py)
  and [native provider fields](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/model-provider-info/src/lib.rs):
  child-only CLI overrides, native lifecycle, Responses, headers and optional
  environment-key authentication.
- [Native namespaced model matching](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/models-manager/src/manager.rs#L763)
  and [bundled model metadata](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/models-manager/models.json):
  the single `cx/` namespace and `-max` suffix retain the longest-matching native
  Sol/Astra capability row; this does not attest the gateway's backend routing.
- [Native ResponsesLite prefix assembly](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/client.rs#L902)
  and [SSE fixture helpers](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/tests/common/responses.rs#L753):
  native tool/prefix preservation and the source of the authored local fixture.
- [Published SDK 0.159.2](https://pypi.org/pypi/openai-codex/0.159.2/json): wheel
  SHA-256 `03c5a0d7c1da9edc4b62d7b4973d6e8199ce9462a7dec9c6dc9d75a2a88d3786`.
  The adjacent locks are generated by supported `uv add --script` and
  `uv lock --script` commands; execution uses `uv run --locked --script`.
- [Existing SDK installation and source qualification](https://github.com/seathatflowsinourveins/native-agent-stack/blob/404b821cd3af25800ea418dc6145cc5cb6fe33c5/evidence/artifacts/runtime-sdk-20260930/receipt.json):
  preserved matching SDK/CLI pins, native custom-provider reference,
  21 unchanged published Python source files and retained upstream test results.
