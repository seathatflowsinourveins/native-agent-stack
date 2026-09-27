# OpenHands coding runtime worker

This recipe uses OpenHands SDK **1.49.6** for one frozen SWE-bench coding task
through OmniRoute. **Official SWE-bench 4.1.0 supplies the task verdict**, using
the conversion and grading pipeline selected by OpenHands/benchmarks at
405bae7140d7e961a75f4910a0b2e7069731db96. [check.py](e2e/check.py) only validates
transport and relays the official report. Local contract tests cannot establish
an upstream E2E pass.

Round 2 is **awaiting host execution and the coordinator's skills PR**. No
package was installed, container/service started, model called, or upstream
grader executed in this build. The SDK owns the agent loop, tools, skills,
native trace and condensation. All agent/LLM/MCP execution stays in an owned
container; the grader uses separate official test containers. The worker never
receives this checkout, the frozen oracle row, or a Docker socket.

## Sources, pins and installation

[pins.json](pins.json) keeps the worker's existing artifact pins and the new
grader pins. [research.md](research.md) records research and corrections.

| Component | Exact selected pin | Role |
| --- | --- | --- |
| OpenHands Software Agent SDK | v1.49.6 / fcc102a697874d54a357e36004e02c95040dbdc0 | Standalone coding worker |
| OpenHands/benchmarks | 405bae7140d7e961a75f4910a0b2e7069731db96 | Native output conversion and official grading integration |
| Benchmark SDK submodule | 43376f1868ffd702746080714a59c16d3f69ec12 | Preserved in the benchmark's separate environment |
| SWE-bench | 4.1.0 | Official Docker tests and resolved_ids verdict |
| Harbor, runner-up | v0.23.0 | Not selected: Terminal-Bench has a different task contract |

The two SDK revisions are intentionally separate. The grader environment keeps
the report's exact submodule; it does not silently upgrade to the worker SDK.
The worker's inference is an explicitly local adaptation of the [standalone
example][hello] and the benchmark's [issue prompt and patch export][benchmark-infer].
It is not an unchanged swebench-infer run. The official grader's patch
application, tests, scoring and report logic remain unchanged.

The primary fits this coding task because its converter accepts actual
OpenHands patches and invokes the official SWE-bench harness.
[Harbor's OpenHands adapter][harbor] is a maintained alternative; selecting its
Terminal-Bench tasks would change the oracle. Stars and installation counts
were discovery signals only. This choice follows the supplied eval-framework
reports, particularly report2's W8a mapping.

[install.sh](install.sh) preserves the round-1 worker installation: the
[official package path][getting-started], pinned published SDK/tools wheels,
[requirements.lock](requirements.lock), [build-requirements.lock](build-requirements.lock),
and a content-addressed agent-server image, used as a Python runtime with its
server entrypoint replaced. [install-container.sh](install-container.sh) runs
inside that image. The source archive, upstream lock, requirements and image
configuration hashes are verified before use. The image is:

~~~text
ghcr.io/openhands/agent-server@sha256:02ef66fdf0b22a40b0b55c5cca8d1790cfd260c5069f7c0b99edc1b505d5ab37
~~~

It selects Linux amd64 manifest
ec7ed86f4021a21e161815853156521b44929d913f2e6ee06a173ef2f660aa12
and image config 39426d8ce5c3ecaf6829063ec8ccfe5c289f049ae007fb14d89317b3982d196f.
The image metadata records Python 3.13.15 and uv 0.12.15. No image was pulled
here. The retained [wheel/source comparison](evidence/wheel-source-comparison.json)
is artifact evidence only.

The worker install follows the upstream lock's dependency export plus hashed
published wheels. It bootstraps locked build tools before the hash-required
install without build isolation; func-timeout is an sdist. Installation checks
package versions/imports, not model behavior. SDK source builds, published binary
images and importable wheels are different installation paths; this recipe
retains the qualified artifact choices from round 1.

[install-grader.sh](install-grader.sh), called by the host installer, clones
OpenHands/benchmarks into the owned prefix, checks out the exact commit,
initializes its submodules and runs **make build**, the [documented install][benchmark-install].
The [pinned Makefile][benchmark-make] runs uv sync --dev and installs its own
development hooks in that isolated checkout. The script verifies the submodule
before and after installation, refuses tracked modifications, checks that
uv.lock/pyproject.toml did not drift, and verifies swebench==4.1.0. Grader source
and SDK state remain separate from this repository. No alternative grader is
installed as fallback.

The prefix is $HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6;
private state is $HOME/.local/state/native-agent-stack/runtime-workers/openhands.
Every trial gets a fresh attempt directory. Failed attempts remain available.
The grader source install has its own isolated venv and cache. The worker venv's
interpreter link resolves inside the pinned image, not necessarily on the host.

## Model and gateway contract

[config/worker.json](config/worker.json) selects **cx/gpt-6-astra-max** for the
coding/judgment loop and condenser. OPENHANDS_MODEL can select another cx/gpt-6
family alias; [recipe.py](recipe.py) rejects Claude and other model families.
OmniRoute does not serve claude-opus-5-5. The official SWE-bench grader is
deterministic and makes no LLM judgment request.

| Setting | Native SDK interface | Recipe behavior |
| --- | --- | --- |
| Gateway | LLM.base_url and api_key | Host reference http://127.0.0.1:20128/v1; actual rootless-container URL http://10.0.2.2:20128/v1; keyless placeholder local-loopback |
| Model | LLM.model, model_canonical_name | LiteLLM openai/ provider prefix is added before cx/gpt-6-astra-max |
| Effort/API | LLM.api_mode, reasoning_effort | Responses, max; no automatic chat fallback |
| Structured actions | ToolDefinition.to_responses_tool | Native function tools, strict:false; no JSON response format |
| Sampling | LLM.temperature | Omitted, including summaries; values at or below 0.1 are rejected |
| Affinity | LLM.extra_headers | Stable x-omniroute-session for one conversation and its condenser |
| Idempotency | Public generate/agenerate kwargs | Fresh Idempotency-Key per logical call; upstream internal retries retain it |
| Context | LLMSummarizingCondenser | 80 events / 60,000 input-token trigger, keep_first=2 |
| Bounds | Native SDK run/request fields | 40 iterations, 1,200-second worker deadline, 16,384 output tokens, two retries, 180-second request timeout |

The gateway owner's cognee 1.6.1 measurements establish that JSON-object mode
needs the word “json” in input messages; system text moves to instructions.
Strict JSON schemas need additionalProperties:false on every object.
This recipe chooses **tool calling** for structured actions, following
[the pinned serializer][tool-serialization]. It does not issue JSON-object or
JSON-schema calls. Its [native condenser][condenser] consumes ordinary summary
text. No gateway/schema acceptance is inferred from these offline checks.

[worker.py](worker.py) changes only the public LLM generation boundary to supply
headers; the upstream serialization, retries and condenser remain native.
The adapter scopes its method wrapping to one worker process and restores the
methods afterward. Agent and condenser keep exact native LLM objects:
[SDK registration][llm-discovery] explicitly checks type(obj) is LLM, and
[conversation setup][llm-registration] uses that registry for native metrics
and condenser context. A subclass would silently skip this registration.
[SDK header merging][header-merging] preserves per-call headers. Actual
wire-level header stability, fresh logical call keys, max effort, streaming and
tool results still require host observation. Gateway log columns available to
this recipe cannot independently prove header/session attribution.

## MCP and skills lifecycle

[config/mcp.template.json](config/mcp.template.json) retains the native command
selection from the repository's adopted client templates.
[recipe.py](recipe.py) translates tool limits into Agent.filter_tools_regex;
Codex-only approval/allowlist keys are not passed as SDK configuration.
The locked FastMCP uses the server_name_tool_name namespace and the worker
requires multiple servers. See [MCP config][mcp-config] and [agent filtering][agent-base].

| Server | Scope |
| --- | --- |
| context-mode | Native stdio; ctx_upgrade and ctx_purge excluded |
| serena | Native stdio, explicit /workspace, dashboard off, external attempt-owned metadata |
| jcodemunch | Native stdio; route, menu and order only |
| qmd | Native stdio; query/get/multi_get/status over exactly four named catalog/document collections |
| ai-memory | Existing HTTP endpoint; query/read_page/recent/status/briefing only |
| socraticode | Native stdio; search/status/list_projects/health; watcher manual; existing local embedder |
| headroom | Configured but disabled; no measured remaining gap justifies it for this trial |

Serena state and QMD indices live under the attempt's MCP state.
[qmd-setup.py](qmd-setup.py) uses native collection add/update only on the four
mounted document directories. [mcp_guard.py](mcp_guard.py) requires explicit
collections, lexical searches and rerank:false. There is no OmniRoute embedder.
[config/host.example.json](config/host.example.json) describes the private,
mode-0600 paths file; no credentials or authentication-store mounts are needed.

**Skills installation has exactly one path**, executed from OPENHANDS_STACK_ROOT:

~~~sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/adoption/install_skills.py \
  --manifest blueprints/runtime-workers/skills/manifest.json \
  --project-dir "$WORKER_WORKSPACE" --agent universal
~~~

The new project-dir/agent options and runtime-worker manifest are **pending the
coordinator's skills PR** in this worktree. The call and regression test are
present now. Missing manifest/options fail the trial; there is no global,
copy, symlink or alternate installer fallback. The old
[config/skills.lock.json](config/skills.lock.json) records round-1 provenance only
and is no longer read for installation, loading or receipt decisions.

The expected manifest contract is a skills array with name and
skill_md_sha256, including tdd and verification-before-completion. The installer
owns the project-local .agents/skills tree. The host verifies those bytes and
mounts .agents read-only; [native load_skills_from_dir][skills-loader] discovers
them and AgentContext.skills exposes them progressively. Public, home and project
auto-discovery stays disabled. Discovery mismatches fail startup.
The [upstream project installer][skills-local-lock] also writes skills-lock.json
at the workspace root. Both installer paths are excluded from the worker patch
and mounted read-only when present. A frozen task already containing .agents or
skills-lock.json is rejected before installation so its own files stay intact.
Additional artifacts from the pending shared installer must be reviewed at
integration; the recipe does not assume that extension has been accepted.

Each attempt records the **actual names listed at start** in
worker/skills-startup.json and input/skills.json, rather than claiming a fixed
28-skill list in advance of the pending manifest. The E2E requires successful
native **ObservationEvent / invoke_skill / skill_name** results for tdd and
verification-before-completion, corroborated by the SDK's persisted trace.
[InvokeSkillTool][invoke-skill] returns the rendered skill content and records
the invocation. A name in config, startup listing or the task prompt alone
does not prove activation. No activation was observed in this build.

## Frozen task and official verdict

Before host acceptance, select one original SWE-bench Verified row from a
recorded dataset revision; retain the complete JSON-list or JSONL row, its
source revision and SHA256 outside every worktree. The [official loader][swe-dataset]
accepts both formats. OPENHANDS_TASK_FILE and OPENHANDS_TASK_SHA256 identify
these frozen bytes. A concrete instance/revision is a remaining host input;
the recipe does not invent a replacement benchmark task.

[e2e/task.py](e2e/task.py) validates the hash, single-instance scope, repository,
base commit and native test fields. Only the issue, repository and base commit
enter the worker's prompt. Gold patch, test patch and test-name oracle fields
remain outside every worker mount. The worker gets a checkout at the frozen
base commit with protected Git/skill metadata. This bare-checkout adaptation
does not claim the benchmark's preinstalled Conda testbed; dependency and native
test availability must be established for the selected task.

After inference, [host.py](host.py) exports the worker's staged diff against
that base commit using the benchmark's [native patch pattern][benchmark-infer]
into output.jsonl. The adapter rejects missing, malformed, duplicate or
wrong-instance predictions before upstream conversion. Empty patches remain
valid submissions that the official grader can fail.

The primary pipeline is split at the official converter/grader boundary:

~~~sh
# In the pinned benchmark environment; paths below are private attempt paths.
swebench-eval "$OUTPUT_JSONL" --dataset "$FROZEN_DATASET" \
  --run-id "$RUN_ID" --workers 1 --no-modal --skip-evaluation
python /path/to/recipe/e2e/docker_grader.py \
  --dataset_name "$FROZEN_DATASET" --predictions_path "$PREDICTIONS_JSONL" \
  --instance_ids "$INSTANCE_ID" --run_id "$RUN_ID" --max_workers 1 \
  --split test --timeout 1800 --namespace swebench \
  --cache_level instance --clean false --modal false
~~~

The first command is the unchanged [OpenHands converter][benchmark-eval].
The second executes the **unchanged swebench.harness.run_evaluation CLI**,
the same module invoked by swebench-eval. [docker_grader.py](e2e/docker_grader.py)
adapts only the [Docker creation boundary][swe-container] for names, ownership
labels and resource limits. The split allows the native cache/cleanup flags,
which swebench-eval does not expose. There is no local test grader.

The benchmark converter intentionally removes edits to pyproject.toml,
tox.ini and setup.py. Both original output.jsonl and converted
output.swebench.jsonl are retained with hashes; host acceptance must examine
any filtered changes. SWE-bench writes OpenHands.RUN_ID.json plus per-instance
report.json and test output in its native logs. [receipt.py](receipt.py)
re-reads that official report; resolved_ids supplies the verdict. A grader
exit code of zero alone is insufficient. Missing/conflicting/malformed report
fields leave the verdict unknown. [check.py](e2e/check.py) returns 0 for an
upstream-resolved ID, 1 for an upstream negative outcome, and 2 for invalid
transport; input-only mode reports ready_to_grade without a correctness claim.

The old e2e/fixture-repo, frozen.json and task.txt are retained solely as
historical round-1 artifacts. They are not mounted or executed in this E2E.

## Ownership, ports and coordinator execution

Every created container has prefix **rw-openhands-** and label
**com.native-agent-stack.owner=gpt6-omniroute-framework-integration**.
No named volume or custom network is created; worker persistence uses owned
bind mounts. The grader rejects new volume/network/build operations and uses
official prebuilt SWE-bench images. Their actual resolved digests must be
recorded during host acceptance; the native per-instance image tags are not
claimed here to be immutable artifacts.

| Port/resource | Mapping |
| --- | --- |
| Worker, install, QMD and grader containers | No host ports published; no worker HTTP service configured |
| Permitted future worker listener allocation | 127.0.0.1:3730–3799 only |
| Existing gateway dependency | Host 127.0.0.1:20128; container access 10.0.2.2:20128 |
| Existing ai-memory / local embedder dependencies | 10.0.2.2:49474 / 10.0.2.2:18232; not created by this recipe |
| S3 memory arms and cognee | 3710–3729, 5433–5439 and 3800–3819 remain unallocated by this worker |

On the coordinator's host, after the shared skills PR and a frozen native task:

~~~sh
export OPENHANDS_HOST_FILE=/absolute/private/openhands-host.json
export OPENHANDS_STACK_ROOT=/absolute/native-agent-stack
export OPENHANDS_TASK_FILE=/absolute/private/frozen-instance.jsonl
export OPENHANDS_TASK_SHA256='<sha256-of-the-retained-original-row>'
bash blueprints/runtime-workers/openhands/install.sh
OPENHANDS_MODEL=cx/gpt-6-astra-max bash blueprints/runtime-workers/openhands/run-e2e.sh
~~~

The existing rootless Docker context is required. The worker uses container
UID 0 mapped to the host user, dropped capabilities, no-new-privileges,
a read-only image and temporary /root and /tmp. The worker and grader have
4 CPU, 8 GiB and 384 PID limits; the grader uses the existing rootless socket
from the host, never a worker socket mount. Its process deadline is 2,400
seconds in addition to the upstream per-instance test timeout.

Cleanup removes only each exact literal container name, then independently
checks absence. There is no global prune or upstream broad cleanup helper.
The grader's instance cache/clean=false setting retains images. Native logs
and failures stay in private attempt state. A hard-killed host may still need
literal-name cleanup; reboot/crash recovery has not been accepted.
Inspect only the owner label and the relevant rw-openhands attempt before
recovering. Do not remove shared Docker, gateway, native sign-ins or MCP state.

## Evidence and remaining gates

[Round-2 verification](evidence/round2-verification.md) records fail-first and
final commands, exits and returned output. The unit suite provides **local
synthetic transport controls**, including known-pass, known-fail, malformed,
missing, duplicate and conflicting results. It tests the shared installer
invocation, GPT-6 routing and resource adapter. None is reported as an unchanged
upstream test or a live model evaluation.

The read-only gateway receipt still reads only the nine authorized call_logs
columns and never sums window rows into an exclusive worker cost. Native
metrics and full traces remain private. Unknown usage stays unknown.
Attribution, byte/token counts, cache subsets and provider spending are separate.

Host checks remaining: install/import compatibility in both pinned environments;
frozen dataset source/instance and testbed compatibility; official pass/fail
controls using retained gold/empty patches before a real worker patch; actual
grader image digests; container ownership/cleanup; native MCP startup and tool
limits; exact skill listing and both activation observations; gateway headers,
Responses/tool behavior and requested/upstream max effort. Native MCP aggregate
startup is 30 seconds even when individual server timeouts are longer.
No matched A/B, skill ablation, token savings, full upstream SDK suite or
crash-recovery acceptance has been performed. A future comparison must freeze
the same task/oracle, environment, models, tools and cache policy across arms.

The coordinator owns shared manifests. Changed round-1 evidence hashes require
re-registration in manifests/evidence.json after integration; this builder edits
only this recipe and its assigned test. Publication validation is still run and
its actual result is retained even when that shared-file boundary prevents a
clean hash check.

[release]: https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.49.6
[sdk-readme]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/README.md#L49-L81
[hello]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/examples/01_standalone_sdk/01_hello_world.py#L10-L29
[makefile]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/Makefile#L34-L41
[getting-started]: https://docs.openhands.dev/sdk/getting-started
[docker-runtime]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-agent-server/openhands/agent_server/docker/Dockerfile#L39-L47
[docker-uv]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-agent-server/openhands/agent_server/docker/Dockerfile#L402-L403
[docker-sync]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-agent-server/openhands/agent_server/docker/Dockerfile#L128-L140
[image-targets]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-agent-server/openhands/agent_server/docker/Dockerfile#L564-L598
[image-matrix]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/.github/workflows/server.yml#L281-L339
[remote-example]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/examples/02_remote_agent_server/02_convo_with_docker_sandboxed_server.py#L92-L97
[docker-workspace]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-workspace/openhands/workspace/docker/workspace.py#L218-L251
[sdk-pyproject]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/pyproject.toml#L41-L43
[uv-build]: https://docs.astral.sh/uv/pip/compatibility/#pep-517-build-isolation
[llm-config]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/llm.py#L340-L470
[llm-effort]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/llm.py#L537-L549
[llm-copy]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/llm.py#L783-L798
[llm-generate]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/llm.py#L1580-L1643
[responses-options]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/options/responses_options.py#L26-L97
[conversation]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/conversation/conversation.py#L120-L204
[condenser]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py#L48-L154
[condenser-example]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/examples/01_standalone_sdk/14_context_condenser.py#L64-L83
[terminal]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-tools/openhands/tools/terminal/definition.py#L175-L200
[terminal-constants]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-tools/openhands/tools/terminal/constants.py#L18-L21
[model-features]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/utils/model_features.py#L190-L200
[mcp-config]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/mcp/config.py#L497-L530
[agent-base]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/agent/base.py#L153-L158
[fastmcp-config]: https://github.com/PrefectHQ/fastmcp/blob/665514e19a78543709be85b4261153bbe98e882f/src/fastmcp/client/transports/config.py#L25-L125
[fastmcp-namespace]: https://github.com/PrefectHQ/fastmcp/blob/665514e19a78543709be85b4261153bbe98e882f/src/fastmcp/server/transforms/namespace.py#L44-L62
[serena-cli]: https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/cli.py#L369-L383
[serena-home]: https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/config/serena_config.py#L65-L78
[serena-project]: https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/config/serena_config.py#L928-L936
[serena-loader]: https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/config/serena_config.py#L1050-L1104
[qmd-config]: https://github.com/tobi/qmd/blob/v2.8.3/src/collections.ts#L112-L125
[qmd-store]: https://github.com/tobi/qmd/blob/v2.8.3/src/store.ts#L636-L653
[qmd-cli]: https://github.com/tobi/qmd/blob/v2.8.3/src/cli/qmd.ts#L4451-L4479
[qmd-schema]: https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L320-L369
[hooks]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/examples/01_standalone_sdk/33_hooks/main.py#L51-L64
[skills-example]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/examples/05_skills_and_plugins/01_loading_agentskills/main.py#L72-L146
[skills-loader]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L848-L903
[invoke-skill]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/tool/builtins/invoke_skill.py#L25-L139
[local-mcp]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L1356-L1379
[upstream-tests]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/.github/workflows/tests.yml#L117
[canvas]: https://github.com/OpenHands/OpenHands/blob/7dc6805406ea3c76cb4a3ce407c3c72d481b0ac6/README.md#L139-L150
[unittest-runner]: https://github.com/python/cpython/blob/v3.13.15/Lib/unittest/runner.py
[unittest-main]: https://github.com/python/cpython/blob/v3.13.15/Lib/unittest/main.py
[sqlite-readonly]: https://docs.python.org/3.13/library/sqlite3.html#how-to-work-with-sqlite-uris

[benchmark-install]: https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/README.md
[benchmark-make]: https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/Makefile
[benchmark-infer]: https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/benchmarks/swebench/run_infer.py
[benchmark-eval]: https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/benchmarks/swebench/eval_infer.py
[harbor]: https://github.com/harbor-framework/harbor/blob/v0.23.0/src/harbor/agents/installed/openhands_sdk.py
[swe-dataset]: https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/utils.py#L133-L177
[swe-container]: https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/docker_build.py#L470-L536
[tool-serialization]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/tool/tool.py#L776-L804
[header-merging]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/options/common.py#L26-L44
[llm-discovery]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/agent/base.py#L739-L775
[llm-registration]: https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L1566-L1579
[skills-local-lock]: https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/add.ts#L2130-L2160
