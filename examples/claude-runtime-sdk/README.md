# Claude SDK workers through OmniRoute

This is a thin integration of the official Claude Agent SDK, pinned to
[`anthropics/claude-agent-sdk-python` v0.2.162](https://github.com/anthropics/claude-agent-sdk-python/tree/f2204bb956bab02907aaf3cb88eb9dead28eaa35)
(`f2204bb956bab02907aaf3cb88eb9dead28eaa35`). The
[release](https://github.com/anthropics/claude-agent-sdk-python/releases/tag/v0.2.162)
bundles Claude Code 2.1.285. The SDK owns the agent loop, tool execution,
native context/cache/compaction and sessions. Our script supplies worker-scoped
transport, a bounded lifecycle and value-free observations.

The default candidate `dva/claude-opus-5-max` is an advertised OmniRoute Claude
route, pending live qualification. Its name does not attest the serving provider
or model, and advertised Opus 5 is different from the native coordinator's
Opus 5.5. This integration does not select a framework winner or certify every
installed skill, hook, plugin, MCP server or background workflow. The coordinator
retains its native session and authentication.

## Installation and configuration

Use the installed uv 0.12.17 and the committed PEP 723 script lock. These are the
[supported uv script commands](https://docs.astral.sh/uv/guides/scripts/#locking-dependencies);
the package installation is the SDK's
[official PyPI installation](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/README.md#installation).

```sh
rtk uv lock --script examples/claude-runtime-sdk/worker.py --check
rtk uv run --frozen --script examples/claude-runtime-sdk/worker.py --preflight
```

Preflight makes no provider request. It reports selected options, package pin,
loopback port and capability configuration without printing paths, settings or
credentials. `CLAUDE_CODE_EFFORT_LEVEL` must be absent from the launcher process:
the native variable can override the explicit `effort="max"`. Remove it only from
the worker launch environment when needed; do not change the coordinator's
environment or settings. The standalone worker adopts OmniRoute's pinned
[`buildClaudeEnv`](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/bin/cli/commands/launch.mjs#L23)
transport: it removes inherited `ANTHROPIC_*` from its own process, sets the
loopback Anthropic root (normally `http://127.0.0.1:20128`, without `/v1`), enables
native gateway model discovery and supplies the documented `omniroute-no-auth`
sentinel for a keyless loopback gateway. An authenticated gateway may use
`--gateway-token-env APPLICATION_BINDING`: the runtime copies that opaque
application-specific value into the native child option without printing it.
Missing bindings and attempted native `ANTHROPIC_*` credential reuse fail closed.
The SDK merges child options onto its process environment, so the filtering
occurs in the standalone worker before connection; importing `run_worker` into
an unrelated application is not a qualified isolation boundary.

The native coordinator environment is unaffected. The launcher source's fixed
190,000-token compaction window is excluded; native context policy is retained.
Use the selected host's native credential recipe. This script does not read
authentication stores, select accounts, restart OmniRoute or configure a remote
service. A sentinel is transport setup, not gateway/provider readiness evidence.

The modern-python skill's statement that PEP 723 scripts have no lockfile was
checked against installed `uv lock --help`: uv 0.12.17 supports `--script`, and
the official script guide documents `worker.py.lock`. The native command is the
source of truth for this correction.

## Full native capabilities with conditional skills

[`ClaudeAgentOptions`](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/src/claude_agent_sdk/types.py)
uses the `claude_code` system prompt preset, an explicit Claude-family model,
`effort="max"`, a selected cwd and `setting_sources=["user", "project"]` by
default. The `tools` option stays unset, retaining the full native toolset.
`--allow-tool` changes permission auto-approval, not tool availability;
`dontAsk` retains native deny rules and denies requests that lack permission.
No bypass mode is introduced.

Installed skill metadata is discovered through those native sources. `--skill
all` exposes every discovered skill, and repeated `--skill NAME` enables an exact
task-matched selection; the SDK loads bodies when the model invokes a skill.
Read a selected `SKILL.md` before acting. Use the repository's
[skill lifecycle](../../adoption/skills/lifecycle.md) to install, update, activate
or recover skills. This runner does not duplicate the skill catalog or preload
all bodies. Native subagent `skills:` fields preload bodies and remain a separate
role definition: do not copy the whole main-session selection into each child.
See the [official SDK skill guide](https://platform.claude.com/docs/en/agent-sdk/skills)
and pinned [`_apply_skills_defaults`](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/src/claude_agent_sdk/_internal/transport/subprocess_cli.py).

Choose sources deliberately. For a clean acceptance fixture, `--setting-source
project` excludes user settings while keeping project configuration. Select local
plugins explicitly with `--plugin PATH`; the SDK's supported local plugin format
can supply skills, agents, hooks and MCP servers. `--mcp-config PATH` adds a native
MCP configuration, and the selected settings retain their native hooks and
subagent definitions. The script does not read or reserialize those settings,
inject a fixed context window, disable compaction, or replace native discovery.
Actual hook/MCP/plugin activation needs an observed worker run.

## Run, interrupt and recover

Supply a prompt on stdin and an isolated owned cwd. A run contains one native
SDK query and no retries. The native client handles additional model/tool turns.
The runner observes the first native result, so independent background jobs need
their own completion and usage qualification.

```sh
rtk uv run --frozen --script examples/claude-runtime-sdk/worker.py \
  --cwd "$WORKER_CHECKOUT" --setting-source project \
  --skill search-first --allow-tool Read --timeout 180 \
  --result-output "$PRIVATE_RUN/returned.txt" < "$PRIVATE_RUN/prompt.txt"
```

`--interrupt-after SECONDS` sends one supported `ClaudeSDKClient.interrupt()`
request. A timeout sends that native interrupt, drains for up to four seconds,
then uses the SDK's shielded subprocess cleanup. Connection has the same overall
deadline; native cleanup has its own termination/kill grace. This does not prove
remote-provider cancellation or reverse external effects. A later run may use
`--resume SESSION_UUID` with the same cwd and native session storage. Inspect
completed effects before resuming; there is no automatic resubmission.
`--fork-session` uses the native fork option when explicitly requested.

Stdout contains a sanitized summary: native session ID, init capability
names/counts, tool-call names/IDs/counts, selected Skill name, tool-result
IDs/error flags, result length/hash, last-result state and numeric usage.
Returned text is optional, written only to a new 0600 file specified by
`--result-output`; keep that file and raw logs outside the checkout. SDK exception
text, prompts, tool inputs/outputs, settings, paths and credential values are
omitted. Publish only a separately reviewed compact receipt.

Native `model_usage` is retained as the latest session snapshot; snapshots are
never added. `usage` from the last result stays separate. Cache read/write
categories are not added to input tokens, native cost is not a billing claim,
and missing counters/cost remain unknown. Executor/advisor/provider complete
usage requires independent reconciliation; these SDK fields do not imply that
an advisor run was captured.

The current Devin bridge's
[`estimateTokens`](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/executors/devin-agentic/types.ts#L54)
uses a text-length estimate. Its
[`serializer`](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/executors/devin-agentic/serializer.ts)
also caps individual tool results at 65,536 characters and marks truncation.
These route behaviors require a workload-specific information-contract check;
SDK-emitted counters do not prove provider measurements or native cache reuse.
An empty/zero native snapshot after a failed request is not proof of zero spend.

## Validation scope

The local tests are synthetic configuration/lifecycle/accounting checks against
the pinned SDK types and transport. They contain discriminating wrong-route,
wrong-family, token-binding, missing-result, cancellation and cumulative-snapshot cases. They
are not unchanged upstream tests or live provider evidence.

```sh
rtk uv run --frozen --script examples/claude-runtime-sdk/worker.py --preflight
rtk uv run --with claude-agent-sdk==0.2.162 \
  python -m unittest discover -s examples/claude-runtime-sdk/tests -v
rtk uv run --with claude-agent-sdk==0.2.162 \
  python examples/claude-runtime-sdk/tests/check_controls.py --disarm-route
# The disarmed route check must fail (exit 1).
rtk uv run --with claude-agent-sdk==0.2.162 \
  python examples/claude-runtime-sdk/tests/check_controls.py
# The same armed oracle must pass (exit 0).
```

Unchanged upstream tests are run from the exact pinned official checkout using
its documented developer installation and `.github/workflows/test.yml` command.
They are recorded separately from the local fixtures and from the coordinator's
bounded OmniRoute live acceptance. A valid model response alone does not qualify
tools, task-selected skills, MCP/plugin/hooks, recovery, usage completeness or
the matched three-arm SDK selection gate.
