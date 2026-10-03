# Native runtime enhancements

Use this kit by default for foundation OmniRoute workers dispatched by Claude,
with selected skills, MCP tools, native agents and a readiness gate. The official
SDK owns execution, tools, compaction, resume and interruption. The worker retains
Sol/Max on port 20128; native parent sessions retain their accounts.

## Prepare an owned worker

Keep the task in its assigned worktree and use a new private Codex home. Install
task-selected skills through the [existing native installer](../../blueprints/runtime-workers/skills/README.md);
`--check-only` verifies installed source identity. Skills are not plugin, MCP,
hook or workflow installations. The broad 136-skill trial remains distinct from
task-specific acceptance.

Render [runtime.config.template.toml](runtime.config.template.toml) into the new
home's `config.toml`. The existing single-template renderer supports this without
reading a host-value file:

```sh
rtk proxy python3 -c 'import sys; from pathlib import Path; sys.path.insert(0,"tools/adoption"); from render_config import render_one; print(render_one(Path(sys.argv[1]),dict(zip(("ECO_ROOT","WORKER_STATE"),sys.argv[2:]))),end="")' \
  examples/omniroute-codex-sdk/runtime.config.template.toml \
  "$ECO_ROOT" "$WORKER_STATE"
```

Write that output only to the new owned home. Place the supplied
[role](agents/runtime-judge.toml) at `<worker-home>/agents/runtime-judge.toml`.
Use 0700 directories and 0600 configuration/role files. For an existing home,
keep its native tool/plugin/hook configuration and apply only reviewed selected
keys through its native config writer; do not replace its configuration with
this starter. Optional services use their existing native recipes.

The starter selects maintained Context Mode with a required startup, native
Serena read tools with worker-scoped state, live web search, native hook
support and at most three concurrent child threads. Generic children use Sol/Max;
the bounded consequential judge explicitly uses Astra/Max. The child's native
provider remains the scoped OmniRoute provider. Generic children inherit the
explicit parent model and effort. Leave native `default_subagent_model` and
`default_subagent_reasoning_effort` unset in this scoped kit: spawn validates
default names against its native catalog before applying a role's gateway alias.
Enabling native hooks does not
install a hook or establish that it ran. Adopt hooks through their own native
installers; Claude's hook format belongs to the Claude coordinator.

This starter and the worker override disable the unused curated-plugin sync with
`features.plugins=false`. Native skills/MCP remain available; plugin-provided
skill roots are excluded. See the [source-based choice](../../docs/decisions/2026-10-03-omniroute-sdk-worker-0160.md).

Codex 0.160.0 app-server does not apply the CLI's selected named profile, even
though the SDK exposes launch-argument overrides. Keep selected settings in the
worker home's native configuration and process overrides. A profile flag or
legacy `profile=` key is not a substitute.

## Check readiness, then execute

```sh
rtk uv run --locked --script examples/omniroute-codex-sdk/worker.py \
  --workspace "$WORKER_PROJECT" --codex-home "$WORKER_CODEX_HOME" \
  --preflight --require-mcp context-mode \
  --timeout 60
```

Check the live gateway's `/v1/models` catalog for the exact route first; the
default `cx/gpt-6.1-sol-max` requires the carried OmniRoute PR #15167. Add
`--require-skill NAME` only after the documented installer has installed that
selected skill in the private home used by this task. A new home with no
installed skill uses no skill requirement. Add task-required server and skill
names with repeated requirement flags. The
metadata-only preflight reports requested and native effective model/provider/effort,
compact skill and MCP discovery, and configured agent names. It emits one compact
record by default; `--catalog-details` exposes the full sanitized discovery catalog
for a diagnostic preflight. It requests no model turn and returns
failure for missing requirements. Its tool catalog is discovery evidence;
nullable native runtime status stays unknown. A real MCP call and native child
task need separate acceptance.

Use the normal [worker invocation](README.md) after readiness. Keep skill bodies
and tool schemas on demand, preserve native caching and count each thread's
latest cumulative usage once. Preserve a failed run's original return before
selecting retry or fresh recovery.

## Automate with Dagu

[runtime-worker.yaml](runtime-worker.yaml) uses maintained Dagu 2.16.6 to run
readiness before one bounded SDK task. Export `STACK_ROOT`, `WORKER_PROJECT`,
`WORKER_CODEX_HOME`, `WORKER_TASK_FILE`, `WORKER_BASE_URL` (normally
`http://127.0.0.1:20128/v1`) and a new private `WORKER_RESULT` path.
The task comes from the owned input file rather than a scheduler prompt.
Keep skill requirements in the task's graph configuration: add
`--require-skill NAME` only after the documented installer and `--check-only`
verification for that home/project. The reusable graph requires Context Mode
and has no fixed skill requirement; `using-superpowers` belongs to the
September 30 historical trial. Keep Dagu's state in its own private directory.
The graph explicitly imports these
six task bindings through native root `env`; Dagu filters other inherited
variables before step execution:

```sh
rtk dagu validate --dagu-home "$WORKER_DAGU_STATE" \
  "$STACK_ROOT/examples/omniroute-codex-sdk/runtime-worker.yaml"
rtk dagu start --context local --dagu-home "$WORKER_DAGU_STATE" \
  --run-id "$WORKER_RUN_ID" \
  "$STACK_ROOT/examples/omniroute-codex-sdk/runtime-worker.yaml"
```

One active run, a 600-second worker deadline and a 720-second graph deadline
bound the graph. The commands use `rtk proxy uv` to retain complete JSONL results.
There is no automatic retry
of model writes and no schedule or scheduler installation. The existing
[selected-step recovery recipe](../../blueprints/convergence-practice/job-recovery/README.md)
is separate evidence for deterministic checkpoint reuse. A schedule requires its
own frequency, scheduler lifecycle and observed run.

## Claude workflows and further tools

The native Claude coordinator uses the [selected workflow and role recipe](../claude-native/workflows/README.md)
for source research, isolated implementation and independent verification. Its
native Bash stage can dispatch this worker or Dagu graph. Keep explicit
task-matched models, Max effort and role dispatch as that recipe specifies.
Use its supported installer for agents, hooks and workflows, and the native MCP
registration for selected coordinator tools. These parent features do not
automatically transfer into the external SDK process.

For code navigation, retrieval, browser automation, memory or observability,
choose the relevant existing foundation recipe and require its native server
when needed. A recorded installation or an advertised tool count does not
establish service execution or model-mediated quality. The separate Claude SDK
bridge retains its failed route status.

## Observed acceptance

The [September 30 receipt](../../evidence/receipts/omniroute-runtime-enhancements-20260930.json)
records a successful bounded Dagu graph: Sol/Max read the selected skill, called
Context Mode and Serena, and dispatched one Astra/Max judge through the same
OmniRoute provider. The judge ran the unchanged upstream fixture's test exactly
once with exit 0; the parent completed, SDK cleanup closed, and fixture hashes
matched. Independent source and artifact review accepted this integration.

The [scoped experiment](../../blueprints/convergence-practice/omniroute-runtime-enhancements/experiment.json)
retains the initial environment failure and 300-second timeout. The successful
rerun followed [its recorded repair plan](rerun-plan.json). Usage remains separate
per native thread; observer totals corroborate those counters. This acceptance
covers these selected calls and a manual graph run. Installed skills, native
hook support and optional scheduler/tool recipes keep their own execution gates.

## Primary sources

- [Codex SDK and exactly pinned request internals](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python),
  `AsyncCodexClient.request`, `generated/v2_all.py`, version 0.160.0.
- [Native app-server profile boundary](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/main.rs#L1263)
  and [child provider inheritance](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/agent/child_config.rs#L130).
- [Native spawn-default validation order](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/agent/child_config.rs#L196-L235)
  and [role model overrides](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/agent/role.rs#L177-L191).
- [Native MCP configuration](https://developers.openai.com/codex/mcp), [native agent fields](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/config_toml.rs#L479).
- [Context Mode 1.0.169](https://github.com/mksglu/context-mode/tree/589d8214d56740a28b5f7bf63167743d586b0b40),
  native stdio entry as reviewed in `adoption/templates/codex.config.template.toml`.
- [Serena selected source](https://github.com/oraios/serena/tree/c6fbd1c5932df2494ffa0020af5a9fbe80b82143),
  native `start-mcp-server` integration from the same adoption template; selected
  read tools and worker-scoped state do not qualify all language servers.
- [Dagu 2.16.6 native graph example](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/examples/embedded/local/workflow.yaml)
  and [native root environment import](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/internal/spec/dag.go#L694-L710).
  The repository's pinned native job-recovery recipe qualifies a separate recovery scope.
- [Claude native workflows](https://code.claude.com/docs/en/workflows); the
  repository's vendored scripts retain their reviewed agent-lab pins and bytes.
