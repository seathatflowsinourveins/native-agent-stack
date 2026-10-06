# DeepAgents persisted research-worker trial

Event export now uses native
[LangChain serialization](https://github.com/langchain-ai/langchain/blob/04ac76c07ec173a44e3e57de54861d0b637e3299/libs/core/langchain_core/load/dump.py),
which replaces registered secrets with references. The
[post-trial check](../../evidence/artifacts/native-runtime-role-resolution-20260930/secret-aware-serialization.json)
retains the CodeQL finding and native redaction/checkpoint acceptance.
Original model runs remain bound to archived executed sources; this fix is
not a new provider run. Private conversation/tool text stays private.

This candidate exercises a research worker with task-selected skills, one explicit
specialist and native SQLite continuation. Retain native Codex/Claude coordination,
the accepted Codex worker and Dagu. Installation and offline checks do not qualify
provider execution or promote this candidate to a default.

`worker.py` composes supported upstream APIs without a custom orchestration loop:

- DeepAgents **0.7.21**, [source `4394bcd0`](https://github.com/langchain-ai/deepagents/tree/4394bcd00b8eb46e7c423939643a0dfcfb5d8773),
  [`create_deep_agent`](https://github.com/langchain-ai/deepagents/blob/4394bcd00b8eb46e7c423939643a0dfcfb5d8773/libs/deepagents/deepagents/graph.py),
  [`FilesystemBackend`](https://github.com/langchain-ai/deepagents/blob/4394bcd00b8eb46e7c423939643a0dfcfb5d8773/libs/deepagents/deepagents/backends/filesystem.py)
  and supported harness profiles.
- LangChain OpenAI **1.6.7**, [source `026c3da2`](https://github.com/langchain-ai/langchain/blob/026c3da2b615abe52f8446e37de460b844d07a43/libs/partners/openai/langchain_openai/chat_models/base.py).
  Each `ChatOpenAI` instance uses the supplied `--base-url` (default from the
  checked-out install plan's `config/gpt-gateway-topology.json` gateway.endpoint,
  fallback `http://127.0.0.1:21128/v1`), `cx/gpt-6.1-sol-max`, Responses, reasoning
  `{"effort": "max"}`, `use_previous_response_id=False`, request timeout 120
  seconds and zero retries. The caller supplies an existing credential through
  an environment-variable name; the recipe does not copy native client sign-ins.
  WSL distributions share networking; implicit defaults avoid NativeStack's
  ports 20128 and 20129. Every NativeStack2604 invocation explicitly passes
  `--base-url http://127.0.0.1:21128/v1`, regardless of worker revision.
  Complete both [model-free gateway preflights](../omniroute-codex-sdk/README.md#2604-gateway-preflights)
  before dispatch.
- SQLite checkpoint package **3.1.1**, [matched release source `b2926a0f`](https://github.com/langchain-ai/langgraph/tree/b2926a0ff9589c28c7e01fe7cdbb337b86d5a4b4/libs/checkpoint-sqlite).
  The published wheel SHA-256 is
  `8505c54c94a658080525d7e6780fdd4e0c078ff2566b30d399c02cc9f9af1c63`;
  its sdist is `6fcb20db4c37ef7aad52f29b539eb98c38e2dad6fab7c2446a2a9db24f37a70e`.
  Matching package metadata alone does not establish source identity: the
  earlier LangGraph `49cce0ca` source differs from these published bytes.

Each model sends `X-OmniRoute-Session-Id: nas-deepagents-omniroute-<UUID hex>`
through LangChain's pinned `default_headers` interface. The main model and
specialist keep distinct fresh tags, held for each model instance. OmniRoute's
[`session_tag` persistence](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/src/lib/usage/callLogs.ts#L741)
and prefix filter at :995-996 support census attribution. Distinct tags do not
guarantee distinct effective reasoning-replay keys: the pinned
[`sessionAffinityKey` takes priority](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/handlers/chatCore.ts#L1093).
Replay isolation remains unqualified. Count attempts and distinct model tags separately from worker
invocations. `--describe` reports the prefix, not a live request or census result.

The main worker and named `source-reviewer` each receive their own configured
Sol/Max model. A native harness profile disables implicit general-purpose
subagents and the `execute` tool. Native `ToolCallLimitMiddleware` limits `task`
to one call per run and raises on excess calls; configuration caps concurrency
at two and graph recursion at 32. Keep SQLite outside the model-visible
workspace, with one local writer, and enable `LANGGRAPH_STRICT_MSGPACK=true`.
Filesystem virtual paths do not provide OS confinement; the pinned
[`FilesystemBackend` warning](https://github.com/langchain-ai/deepagents/blob/4394bcd00b8eb46e7c423939643a0dfcfb5d8773/libs/deepagents/deepagents/backends/filesystem.py#L132-L136)
states this explicitly. The fixture also preserves the separate
[`LocalShellBackend` source](https://github.com/langchain-ai/deepagents/blob/4394bcd00b8eb46e7c423939643a0dfcfb5d8773/libs/deepagents/deepagents/backends/local_shell.py)
for the source comparison. No shell or MCP tools are added to this trial.

## Private installation and commands

Use an owned private directory outside every checkout. `RECIPE`, `TRIAL_STATE`,
`WORKSPACE`, `CHECKPOINT` and `PROMPT_FILE` below are caller-selected absolute
paths. Set `TRIAL_PYTHON` to `$TRIAL_STATE/integration-venv/bin/python`.

```sh
rtk uv pip compile "$RECIPE/requirements.in" --python-version 3.13 \
  --generate-hashes --output-file "$RECIPE/requirements.lock" --no-emit-index-url
rtk uv venv --python 3.13 "$TRIAL_STATE/integration-venv"
rtk uv pip sync --python "$TRIAL_PYTHON" --require-hashes "$RECIPE/requirements.lock"
rtk uv pip check --python "$TRIAL_PYTHON"
rtk "$TRIAL_PYTHON" "$RECIPE/worker.py" --workspace "$WORKSPACE" \
  --base-url http://127.0.0.1:21128/v1 \
  --checkpoint "$CHECKPOINT" --thread-id research-trial \
  --skill /skills --api-key-env OMNIROUTE_WORKER_API_KEY --describe
```

`--describe` reads package versions and prints configuration only. It performs
no graph execution, authentication check or provider call. Before an authorized
trial, supply the existing child credential under `OMNIROUTE_WORKER_API_KEY`
without logging its value and prepare the frozen task and source files.
The retained historical trial used the coordinator's owned reverse observer at
`http://127.0.0.1:25371/v1` for description and execution. The current 2604 commands
target 21128 explicitly. Description prints the selected endpoint separately
from the retained underlying lane; it does not verify provider identity.

```sh
rtk timeout --signal=TERM --kill-after=5s 600s "$TRIAL_PYTHON" \
  "$RECIPE/worker.py" --workspace "$WORKSPACE" --checkpoint "$CHECKPOINT" \
  --base-url http://127.0.0.1:21128/v1 \
  --thread-id research-trial --skill /skills \
  --api-key-env OMNIROUTE_WORKER_API_KEY --prompt-file "$PROMPT_FILE"
```

The external native deadline owns process termination. Retain stdout/stderr,
arguments, timestamps and exit status; recover full original output through
RTK's reported recovery path when it truncates the display. The script emits
native graph updates, including nested updates when returned, and checkpoint
message state. Original `AIMessage` usage metadata stays in those events; do not
sum overlapping parent, child or observer counters.

Exit the first process and close its saver before starting a second invocation
with the same SQLite path and `configurable.thread_id`. `--inspect` reconstructs
the graph and emits `get_state` without a model call. A continuation supplies
only the new prompt; SQLite restores the prior message state. This tests
cross-process continuation, not arbitrary interruption during a tool effect.

## Task-selected skill and acceptance

The frozen fixture selects only the upstream
[`research` skill at `c55ee460`](https://github.com/mattpocock/skills/tree/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/engineering/research)
from the existing worker skill catalog. Copy the unchanged selected directory
into the owned workspace as `/skills/research`; record its original tree/file
hashes. Pass its parent `/skills` as the discovery root: native SkillsMiddleware
scans `/skills/<name>/SKILL.md`. Keep that root limited to the one selected skill.
Its instructions guide primary-source investigation and delegated
Markdown findings. The bounded trial selects synchronous native `task`
delegation; it does not establish the skill's background-agent workflow.

Before any provider call, the integrating coordinator freezes the exact fixture,
prompts, source hashes and deterministic oracle in `acceptance-plan.json`:

1. Stage the pinned FilesystemBackend, LocalShellBackend and SQLite source files,
   a source manifest, the selected skill and an unpredictable fixture marker
   under `/inputs/`.
2. Require an observed skill read, one `source-reviewer` task and its cited
   `/artifacts/specialist.md`. The main output records source-supported claims
   and exact quotes; the oracle verifies values and quote/source byte matches.
3. Observe the original marker in native checkpoint messages, then remove its
   input. A separate process using the same database/thread writes the marker
   from its restored conversation without rereading inputs or delegating.
4. A different thread or empty SQLite database must lack the marker; the same
   artifact oracle must reject missing or wrong output. These controls are
   local integration fixtures, separate from upstream tests.

MCP integration remains unqualified. Add a native adapter only for a demonstrated
tool gap and give that integration its own acceptance.

## Preparation evidence

On September 30, 2026, the owned Python **3.13.15** baseline reported all three
primary packages absent. Native hashed resolution and sync installed **62**
packages; `uv pip check` exited **0**. The integration uses
`langchain-openai` **1.6.7** (OpenAI SDK **3.22.1**).

The separate unchanged DeepAgents source environment retained its native
`uv.lock`, including `langchain-openai` **1.1.14** (OpenAI SDK **2.28.0**).
The supported upstream
[`Makefile`](https://github.com/langchain-ai/deepagents/blob/4394bcd00b8eb46e7c423939643a0dfcfb5d8773/libs/deepagents/Makefile)
command was:

```sh
rtk make test TEST_FILE='tests/unit_tests/middleware/test_skills_middleware.py tests/unit_tests/middleware/test_skills_middleware_async.py tests/unit_tests/middleware/test_subagent_middleware_init.py tests/unit_tests/test_subagents.py tests/unit_tests/test_graph.py' PYTEST_EXTRA='-n 2'
```

It retained the upstream socket gate and reported **361 passed, 1 xfailed in
12.93s**, exit **0**. Test-file and source-lock hashes, both dependency contexts,
and the recovered original output are retained privately.

Native [OSV Scanner 2.6.0](https://github.com/google/osv-scanner/releases/tag/v2.6.0)
scanned all **62** integration packages with no ignores and returned `results: []`,
exit **0**. Its first attempt rejected the `.lock` filename (exit **127**); the
successful attempt scanned a byte-identical private `requirements.txt` copy.
Both original attempts remain in the private preparation logs. These results
establish their named offline checks only; live provider, skill/delegation and
continuation acceptance require the frozen model trial and its controls.

Native offline `SkillsMiddleware.before_agent` found exactly `research` under
`/skills`, with zero load errors. The absent `/absent-skills` control returned no
skills and a native `path_not_found` error; the earlier incorrect
`/skills/research` root returned none. Both independently constructed model
instances used the explicit observer endpoint and requested Responses with
reasoning `max`; a patched HTTP transport rejected any attempted network call.
`--inspect` reconstructed the graph and returned an empty native checkpoint,
exit **0**. These checks establish discovery and configuration only. The earlier
hardcoded endpoint and incorrect skill root are retained as failed review
conditions rather than passed provider evidence.

The original broad API metadata probe was condensed by RTK; its complete stdout
is not valid machine JSON. Preserve that limitation and use only its intact
fields. Configuration descriptions and all model-event captures use
`rtk proxy` to retain complete native JSON.

The initial frozen model trial used a recursion override of **24** and failed
with native `GraphRecursionError`, exit **1**, after approximately **325 seconds**.
It produced both artifacts and one returned specialist task. The unchanged
oracle also rejected a **262-character** SQLite quote: it was an exact source
substring but exceeded the frozen **240-character** bound. Original events,
state, artifacts, usage and failures remain retained; no synthetic completion
event replaces the failed run.

The bounded repair raises only the native graph step override to **32**.
Upstream [`graph.py` sets 9,999](https://github.com/langchain-ai/deepagents/blob/4394bcd00b8eb46e7c423939643a0dfcfb5d8773/libs/deepagents/deepagents/graph.py#L974-L976)
and an unchanged
[`subagent test` exercises a 5,000-step native configuration](https://github.com/langchain-ai/deepagents/blob/4394bcd00b8eb46e7c423939643a0dfcfb5d8773/libs/deepagents/tests/unit_tests/test_subagents.py#L871-L954).
The repaired process uses the existing SQLite/thread and one new coordinator
instruction, with no new specialist task or marker read. Keep the same source
fixture and oracle, record the changed prompt/configuration before execution,
and retain the 600-second deadline and all other bounds.

The saved-context repair exited **0** in **30.88 seconds**. Exact concatenation
of original and repair event bytes passed every check in the unchanged initial
oracle, exit **0**, including one total returned specialist task and the actual
native completion checkpoint. The corrected SQLite quote is **13 characters**
and remains an exact source substring. The original failed attempt retains its
failed status.

After the marker input was removed, a fresh process reconstructed the graph
and observed the saved marker with no pending nodes. A separate continuation
process exited **0** in **13.59 seconds** and wrote the exact remembered marker.
The unchanged resume oracle passed all three checks using only the new native
events, including no `read_file` or `task` call. The initial missing-artifact,
different-thread marker-presence, missing-resume-artifact and wrong-resume-marker
controls each exited **2** under their respective unchanged oracle phase.
The native continuation artifact was restored byte for byte, and the same
resume oracle passed again. All source and selected-skill hashes still matched.

The integrating revisions preserve the example's exact worker bytes:

| Worker commit | Integration commit | Worker SHA-256 |
| --- | --- | --- |
| `2b4a534b` | [`37cb7cc7`](https://github.com/seathatflowsinourveins/native-agent-stack/commit/37cb7cc7b225c39ab5ac53bba8ec8a661ad7f940) | `31cf9ede2a8f248d20fa18a8ca8abb51b616620caa4f37730c2025f30e8bb90f` |
| `94876f26` | [`d626e03d`](https://github.com/seathatflowsinourveins/native-agent-stack/commit/d626e03d51d4cc3e9e290ada8b87224b7a234a1d) | `66ae2bba78773b52abdd4a312965579d7c2a1b888f54c3e7f1e9776a957ff0ec` |

Native usage below includes only `graph_update` AI messages, deduplicated by
stable ID across all three attempts. Checkpoint snapshots and previously seen
message IDs are excluded. All **27** distinct AI messages returned usage.

| Attempt | AI messages | Input tokens | Output tokens | Cache-read subset | Reasoning subset |
| --- | ---: | ---: | ---: | ---: | ---: |
| Failed initial | 22 | 300,536 | 7,422 | 254,592 | 4,130 |
| Saved-context repair | 3 | 33,483 | 556 | 13,696 | 337 |
| Continuation | 2 | 23,330 | 170 | 22,656 | 98 |

Cache and reasoning are subsets; do not add them to token totals. Count wire
request attempts separately from the coordinator's independent observer, and
do not add observer usage to these native counters. Complete provider usage and
billing remain unknown. This qualifies the named repaired research task and
cross-process continuation; it does not establish arbitrary interrupted-tool
replay, OS confinement, a comparative winner or a global default.
