# Source review, 2026-09-27

## Round 2 research before changes

The supplied eval-framework reports select **OpenHands/benchmarks** at
`405bae7140d7e961a75f4910a0b2e7069731db96`, its SDK submodule at
`43376f1868ffd702746080714a59c16d3f69ec12`, and `swebench==4.1.0`.
The documented source install is recursive submodule initialization followed by
`make build` (its Makefile runs `uv sync --dev`). The source of truth for the verdict is SWE-bench's
Docker evaluation, reached through `swebench-eval`; its process exit alone is
not a task verdict. Sources:
[installation](https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/README.md),
[benchmark commands](https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/benchmarks/swebench/README.md),
[conversion and report handling](https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/benchmarks/swebench/eval_infer.py).
Harbor `v0.23.0` is the runner-up; its Terminal-Bench task contract differs from
this coding-worker SWE-bench contract. Popularity was discovery information only.

Preflight found neither an installed OpenHands SDK nor SWE-bench in the current
interpreter; no executable or native runtime claim is made. The SDK `v1.49.6`
release notes and pinned source were re-read. Public web-open was unavailable;
public source fetching through context-mode worked. The skills.sh leaderboard
was reachable and listed TDD and verification; no install was performed.
The installed search-first/find-skills procedures informed discovery. Source
review confirms the SDK's condenser returns plain text, while agent actions use
native tool calling; no JSON-mode response format is needed.

The round-2 contract supplies resource ownership, GPT-6-only routing, gateway
JSON restrictions and the pending shared skills installer interface. Supporting
SDK sources are `llm/llm.py:1580-1642`, `llm/options/responses_options.py`,
`context/condenser/llm_summarizing_condenser.py:224-229,420-423`,
`skills/skill.py:848-932`, and `tool/builtins/invoke_skill.py:38-123`, all at
`fcc102a697874d54a357e36004e02c95040dbdc0`.
Only recipe-local adapters/contract tests change; upstream graders and tests
remain upstream. Research and returned test logs stay outside the checkout
until sanitized evidence is retained. No host install, service or model run is
authorized in this build.

This recipe is a source-backed integration proposal, not an adopted runtime or a
new model run. The user selected OpenHands for a bounded coding-worker trial.
The existing foundation catalog still describes SDK alternatives as unselected;
this task does not change that catalog or transfer historical 1.49.4 acceptance.

Research used the installed search-first and find-skills procedures, primary
GitHub release/tree/raw sources, PyPI release metadata and GHCR manifest bytes.
Web pages were indexed with context-mode and queried there; large source trees
were processed with ctx_execute. The skills.sh leaderboard was inspected for
discovery only; selection comes from adoption/skills/manifest.json, including
the pinned tdd and verification-before-completion skills. No skill was installed.
The current Python interpreter has no OpenHands package installed, so native
help/import checks are unavailable under this recipe-only authorization.

SDK v1.49.6 resolves to fcc102a697874d54a357e36004e02c95040dbdc0. The exact source
examples used are `01_standalone_sdk/01_hello_world.py`, `07_mcp_integration.py`,
`14_context_condenser.py`, `05_skills_and_plugins/01_loading_agentskills/main.py`
and the SDK event/LLM/MCP implementations. README.md contains immutable links.
SDK wheels were downloaded as source artifacts and their bytes verified against
PyPI's SHA256; they were not installed or imported. The dependency requirements
were exported with the installed uv 0.12.17 from the unchanged upstream uv.lock.

FastMCP 3.2.0 at 665514e19a78543709be85b4261153bbe98e882f confirms the
`server_name_tool_name` namespace. QMD v2.8.3 source confirms QMD_CONFIG_DIR,
INDEX_PATH and native collection add/update. The four-collection index is built
in attempt-owned state; a native PreToolUse hook requires explicit collection
arguments, lexical searches and rerank:false, avoiding embedding dependencies.

The initial offline contract was written before this directory existed:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_runtime_worker_openhands.py -v`.
Exit 1: `Ran 6 tests`; `FAILED (failures=2, errors=4)`. Missing recipe files caused
the failures. Retained returned output is in evidence/fail-first.txt, with only
private filesystem prefixes replaced. This is local structural evidence.

## Decisions and corrections

| Observation | Decision / prevention |
| --- | --- |
| DockerWorkspace is a RemoteWorkspace; Conversation selects RemoteConversation. | Treat its LLM and stdio MCP execution as container-side. A host Python caller does not imply host LLM calls. |
| DockerWorkspace's native launch does not specify the required host publication address. | Run the standalone SDK entirely inside the digest-pinned agent-server image, without an HTTP listener or published ports. |
| The published python image uses the PyInstaller binary target, not the Dockerfile's source target. | Install the two published wheels into an owned mounted venv; never assume /agent-server/.venv exists. |
| The source package's isolated build requires setuptools>=83 outside the main runtime lock. | Use hashed SDK/tools wheels and exported runtime hashes. Bootstrap hashed build tools and disable build isolation. |
| PyPI func-timeout 4.3.5 contains only an sdist. | A proposed all-binary dependency install would fail. Permit hash-checked sdists with preinstalled pinned build tools and no dependency/build downloads outside the requirement files. |
| A guessed QMD src/mcp.ts URL and guessed flat SDK event source paths returned not-found. | Inspect the pinned repository tree before citing paths. Those misses are not absence evidence. |
| SDK MCPServer has no enabled_tools/disabled_tools fields; unknown imported fields are dropped. | Translate limits into Agent.filter_tools_regex. Never pass Codex-only approval/tool keys as SDK configuration. |
| The SDK condenser disables ordinary streaming for summaries. | Omit temperature everywhere. Dynamic per-call headers remain in the LLM generate/agenerate adapter; retain this upstream behavior. |
| Serena's --project-from-cwd needs .git or its project config; the plain frozen fixture has neither. Its default project metadata would also violate the allowed diff. | At c6fbd1c5932df2494ffa0020af5a9fbe80b82143 use supported --project /workspace, SERENA_HOME and project_serena_folder_location outside the fixture. The offline regression test failed on the original template before this fix; native startup remains unmeasured. |
| A container venv interpreter link can dangle when dereferenced on the host. | Check the link entry with lexists on the host, and perform executable/import checks inside the image. |
| A truncated native summary or a timed-out cleanup could erase a failed attempt's receipt. | Two regression tests reproduced the failures. Guard summary parsing; preserve the primary return code and independently record whether the exact owned container was removed. |
| LLM.max_message_chars is declared, but the pinned standalone SDK path does not consume it. | Removed it as a claimed context limit; rely on the terminal's implemented truncation/offload, Serena answer cap, bounded retrieval and condenser. |
| Publication validation treated a container-owned Serena home/config path as a possible personal home path. | Preserve the scoped location and express the directory and filename separately with Path joining. The retained publication-first.txt records the failed check; the shared validator was not changed. |

These corrections are kept here because this builder owns only this recipe and
its unit test. The coordinator can promote general lessons to the shared
docs/harness-defaults.md anti-pattern log. No shared file was edited.

## Round 2 integration decisions and anti-pattern log

| Proven issue / source finding | Correction and evidence boundary |
| --- | --- |
| Round-1 check.py computed task correctness using a local synthetic fixture. The round-2 adapter tests first failed with five failures and two errors. | Replace it with shape validation and a relay of the official SWE-bench report; known-pass/fail/malformed controls remain synthetic adapter checks, never an upstream run. |
| A local passed:true field alone was accepted as a task verdict. The new receipt control failed on that behavior. | receipt.py re-reads the official OpenHands.RUN_ID.json report and requires successful conversion/grader processes plus an upstream-resolved ID. |
| Existing resource labels and arbitrary model overrides did not meet the new contract; the new controls produced eight failures. | Require the exact owner label and rw-openhands prefix, retain zero published ports, reject non-GPT-6 routes and unsafe configured output/sampling modes. |
| Native SWE-bench creation supplies sweb.eval names and no labels; native Docker grading has no label/name override argument. | e2e/docker_grader.py adapts only ContainerCollection.create. Official tests/grading remain unchanged. No new volumes/networks/build intermediates are allowed. Actual Docker acceptance is pending. |
| The official converter strips setup-file changes and can skip malformed rows. | Prevalidate one exact instance; retain original and converted patches. No local replacement converter or test verdict is added. |
| The benchmark SDK's DockerWorkspace runs a remote conversation and cannot carry a host LLM subclass into the agent-server process. | Retain the standalone 1.49.6 worker inside its image; keep the report-pinned SDK submodule isolated in the grading environment. Describe inference as an adaptation, not unchanged swebench-infer. |
| The proposed GatewayLLM subclass bypassed SDK 1.49.6 native registration: AgentBase.get_all_llms uses type(obj) is LLM. LocalConversation uses that registry for aggregate metrics and condenser context binding. | Keep exact native LLM objects and scope header wrapping to their public generate/agenerate methods. The regression control failed first on the missing transport context; it covers sync/async calls, stable affinity, fresh keys and restoration. This is synthetic compatibility evidence, not native accounting acceptance. |
| A plain clone exposes newer refs. SWE-bench 4.1.0 test_spec/python.py:274-292 removes the remote/newer tags, expires reflogs and prunes unreachable objects. | Follow that upstream history boundary before the worker sees its checkout. This adaptation removes all tags and confirms surviving refs equal base_commit; task dependency/Conda setup still needs host acceptance. |
| Project skills options/manifest are absent on this branch. Earlier manual links bypassed the newly required lifecycle. | Call only tools/adoption/install_skills.py with the runtime-worker manifest, --project-dir and --agent universal. Mark pending the coordinator's skills PR; no fallback. The invocation control failed first with the missing helper. |
| Vercel skills 1.7.0 project installation also writes a root skills-lock.json. Only excluding .agents would leak installer bookkeeping into the graded patch. | Reserve both paths before installation, use root-anchored Git exclusions and read-only mounts. The added controls failed first with three failures, then verify Git's actual ignore behavior and that conflicts refuse installation. |
| The SDK skill implementation was initially looked up at a guessed tools/skill path and returned 404. | The existing recipe citation resolves it to sdk/tool/builtins/invoke_skill.py at fcc102a; a failed URL is not capability absence. |
| Publication scanning interpreted slash-separated discovery-scope prose as a personal home path, including its first correction-log quotation. | Spell the three scopes as words in both documentation and the correction log. Do not weaken the shared scanner. Shared evidence hashes still require coordinator re-registration. |
| The recipe-only cache check missed four ignored scripts bytecode files elsewhere in the checkout; their generating process was not observed. | The final sweep covers the whole checkout. Remove only the identified generated files and empty directory; independently confirm sys.dont_write_bytecode and repeat the sweep. No source file outside the assigned paths was changed. |

Additional exact sources: SWE-bench 4.1.0
[repository setup](https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/test_spec/python.py#L274-L292),
[Docker creation](https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/docker_build.py#L516),
[report schema](https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/reporting.py#L127-L142),
[local dataset loader](https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/utils.py#L133-L177).
The 4.1.0 wheel hash in pins.json was verified against returned wheel bytes;
six inspected grading/resource source files matched the v4.1.0 tag.
No downloaded package was installed or executed.

The SDK's tool serializer sets strict:false for function tools at
tool/tool.py:776-804. The condenser emits plain text. Thus this selected
structured-output path needs neither json_object nor a strict JSON schema.
Actual gateway acceptance remains unmeasured. Header merging at
llm/options/common.py:26-44 preserves the caller's extra_headers.
The registration correction follows
[AgentBase.get_all_llms](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/agent/base.py#L739-L775)
and [LocalConversation registration](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L1566-L1579).
Both exact source sections were independently re-read after the researcher's
finding; the native SDK was not installed or executed.

The final skills transport review also inspected Vercel skills v1.7.0 at
7407f3893ad4dceab546ac002c3ef806e4000c73:
[universal placement](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/agents.ts#L815-L822),
[project install bookkeeping](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/add.ts#L2130-L2160),
and [local lock writer](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/local-lock.ts#L65-L122).
A project install writes skills-lock.json at the workspace root in addition
to .agents/skills. Excluding only the skill directory would submit installer
bookkeeping to the grader. The adapter must reserve and exclude both root paths;
preexisting task files at those paths are a conflict, not installer ownership.
The pending shared installer PR must still confirm its exact output contract.

These new corrections remain recipe-local under the assigned file ownership;
the coordinator can promote general entries into docs/harness-defaults.md.

## Round 3: native dispatch, arm repair and trust boundaries (2026-09-27)

Inputs were the coordinator's rw3 OpenHands review, security review, integration
research and common requirements. The common requirements supersede the older
two-slash route and downstream-20128 counting suggestions. Eight Claude findings
were present (five major, three minor); no blocker was listed. Security finding
numbers in the verification record are their one-based positions in the review.

The installed client was inspected first: Python 3.13.15, uv 0.12.17,
curl 8.5.0, gh 2.101.0 and Git 2.43.0. Docker and OpenHands were not found on
PATH; the current interpreter had no OpenHands SDK package. These are scoped
observations, not claims that the host lacks them. The GitHub v1.49.6 release
was read, followed by pinned source files using read-only gh api calls.
Shell-network gh calls failed; Context Mode's read-only gh transport succeeded.
The skills.sh leaderboard was inspected for discovery. The installed tdd,
verification-before-completion, search-first and find-skills instructions were
used subject to the user's no-delegation/no-install rule. No package or skill
was installed, no container was started, and neither gateway was contacted.

The existing maintained SDK/server pin remains the selected source. No new
agent loop, HTTP server, grader, model client or verdict implementation was
introduced. The new dispatch adapter performs the recommended native REST
start/get/final-response operations and retains host status, cancellation and
official grading around them. It is an integration adaptation, not unchanged
upstream execution.

### Source index used by the repair

Each numbered source names the repository, pin and exact file/line scope.
Abbreviated pins elsewhere in this recipe resolve to these entries.

| ID | Primary source | Behavior used |
| --- | --- | --- |
| R1 | [OpenHands/software-agent-sdk@fcc102a697874d54a357e36004e02c95040dbdc0 openhands-agent-server/openhands/agent_server/conversation_router.py:72-86,105-228,257-321](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-agent-server/openhands/agent_server/conversation_router.py#L72-L321) | Native serialization example, count/search, get/final response, start and interrupt. |
| R2 | [Same SDK pin, openhands-sdk/openhands/sdk/conversation/request.py:64-72,105-147,212-228,317-347](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/conversation/request.py#L64-L347) | run=true, required workspace, bound iterations, tags/hooks and Agent validation. |
| R3 | [Same SDK pin, openhands-agent-server/openhands/agent_server/__main__.py:74-135,240-285](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-agent-server/openhands/agent_server/__main__.py#L74-L135) | Supported module preloading, including PyInstaller; authenticated bind default. |
| R4 | [Same SDK pin, openhands-agent-server/openhands/agent_server/docker/Dockerfile:7-9,301-305,343,570-590](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-agent-server/openhands/agent_server/docker/Dockerfile#L570-L590) | UID/GID 10001 and distinct source/binary ENTRYPOINTs. |
| R5 | [Same SDK pin, openhands-sdk/openhands/sdk/llm/llm.py:442-446,1130-1138,1588-1642](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/llm.py#L1130-L1138), [llm/options/common.py:26-46](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/llm/options/common.py#L26-L46), [agent/base.py:739-775](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/agent/base.py#L739-L775) | Raw response, public call kwargs, header merging and exact native LLM registration. |
| R6 | [Same SDK pin, openhands-sdk/openhands/sdk/utils/pydantic_secrets.py:24-37,48-68](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/utils/pydantic_secrets.py#L24-L68) | Explicit serialization context for the fixed keyless gateway placeholder. |
| R7 | [BerriAI/litellm@v1.93.0 litellm/llms/openai/responses/transformation.py:262-272](https://github.com/BerriAI/litellm/blob/v1.93.0/litellm/llms/openai/responses/transformation.py#L262-L272) | Returned headers in raw_response._hidden_params. |
| R8 | [OpenHands/benchmarks@405bae7140d7e961a75f4910a0b2e7069731db96 Makefile:33-42](https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/Makefile#L33-L42), [pyproject.toml:6,97-99](https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/pyproject.toml#L97-L99), [.python-version:1](https://github.com/OpenHands/benchmarks/blob/405bae7140d7e961a75f4910a0b2e7069731db96/.python-version#L1), uv.lock | Native sync, build requirements, Python selection; unchanged lock SHA256 287a42d2157d044ca0f5e723fe3a05c1e4bdf6413049370360226374db6d7e8c. Installed uv 0.12.17 sync --help confirms --python, --locked, --no-build-isolation and --inexact. |
| R9 | [OpenHands/software-agent-sdk@43376f1868ffd702746080714a59c16d3f69ec12 openhands-sdk/pyproject.toml:36-38](https://github.com/OpenHands/software-agent-sdk/blob/43376f1868ffd702746080714a59c16d3f69ec12/openhands-sdk/pyproject.toml#L36-L38); openhands-tools/pyproject.toml:26-28; openhands-agent-server/pyproject.toml:27-29; openhands-workspace/pyproject.toml:19-21 | The separate benchmark submodule requires setuptools>=61 and wheel. Retain its pin and the recipe's hashed build tools. |
| R10 | [SWE-bench/SWE-bench@v4.1.0 swebench/harness/test_spec/python.py:271-292](https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/test_spec/python.py#L271-L292), [test_spec/test_spec.py:106-120](https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/test_spec/test_spec.py#L106-L120), [docker_build.py:516-524](https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/docker_build.py#L516-L524), [reporting.py:127-157](https://github.com/SWE-bench/SWE-bench/blob/v4.1.0/swebench/harness/reporting.py#L127-L157) | Branch exceptions, history boundary, instance tag/name, unchanged container resources and official verdict report. |
| R11 | [docker/docker-py@7.1.0 docker/models/resource.py:28-33](https://github.com/docker/docker-py/blob/7.1.0/docker/models/resource.py#L28-L33) | Image.id identity check before official container creation. |
| R12 | [docker/docs@4e9a5751518ed8223a8dcde53693badddd72604f content/manuals/engine/network/firewall-iptables.md:22-24,48-95](https://github.com/docker/docs/blob/4e9a5751518ed8223a8dcde53693badddd72604f/content/manuals/engine/network/firewall-iptables.md#L22-L95), [port-publishing.md:186-192](https://github.com/docker/docs/blob/4e9a5751518ed8223a8dcde53693badddd72604f/content/manuals/engine/network/port-publishing.md#L186-L192) | DOCKER-USER policy and internal-bridge host reachability. Rootless namespace placement and effective filtering are host gates, not established here. |
| R13 | [diegosouzapw/OmniRoute@a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3 src/lib/usage/callLogs.ts:646-653](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L646-L653), [src/sse/handlers/chatHelpers.ts:1172-1184](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/sse/handlers/chatHelpers.ts#L1172-L1184) | Encrypted-reasoning effort fields and X-Correlation-Id response header. Entry database/model values follow the common contract and require verification against the host's patched build. |
| R14 | [Same OmniRoute pin, src/app/api/analytics/compression/route.ts:13-24](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/app/api/analytics/compression/route.ts#L13-L24), [src/lib/db/compressionAnalytics.ts:52-55](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/db/compressionAnalytics.ts#L52-L55) | Authenticated since=all snapshot; separate totalRequests/totalTokensSaved delta. |
| R15 | [git/git@v2.43.0 Documentation/git.txt:708-724](https://github.com/git/git/blob/v2.43.0/Documentation/git.txt#L708-L724), [Documentation/diff-options.txt:830-840](https://github.com/git/git/blob/v2.43.0/Documentation/diff-options.txt#L830-L840) | Disable system/global config and external diff/textconv during host patch export. |
| R16 | [SDK@fcc102a697874d54a357e36004e02c95040dbdc0 openhands-tools/openhands/tools/terminal/terminal/subprocess_terminal.py:144-170](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-tools/openhands/tools/terminal/terminal/subprocess_terminal.py#L144-L170) | Terminal inherits process environment and UID. A writable SDK trace is not independent evidence. |
| R17 | Repository baseline 17460572, adoption/bootstrap-linux.sh:240,439,457 and adoption/pins-linux-x86_64.json; scripts/validate.py:25-29 | Selected node/python-tool mount layout and publication identifier policy. No other lane's files changed. |
| R18 | [python/cpython@v3.13.15 Doc/library/os.rst:1087-1092,1272-1296,1317-1373](https://github.com/python/cpython/blob/v3.13.15/Doc/library/os.rst#L1272-L1373) | Descriptor-relative opens, platform no-follow/directory flags and descriptor stat used by the bounded reader. Linux symlink/FIFO rejection is exercised locally. |

### Round-3 corrections and remaining decisions

| Finding or mistaken assumption | Correction and verification path |
| --- | --- |
| Older review used sharedgw/cx/... and proposed counting engines-on at 20128. | The common contract overrides both: one slash, entry 20129 only for engines-on. Round 01/02 red-green tests; host matching remains unobserved. |
| Integration research assumed the source image ENTRYPOINT and found no per-call extension. | Pinned R3/R4 show the binary ENTRYPOINT and supported module preload. Preserve ENTRYPOINT; preload the transport wrapper. No native startup claim. |
| Default model_dump was assumed to serialize the dummy gateway key. | R6 masks secrets by default. Explicit expose_secrets serializes only the fixed placeholder; server auth is not in the request body. |
| A guessed Dockerfile path returned not-found. | Resolved the pinned repository tree to R4; the failed path was not absence evidence. |
| Guessed node22 and uv-tools paths did not match adoption. | R17 requires node24.21.0 and python-tools. Resolved-path allowlist tests cover the corrected selected roots. |
| An initial host-green run failed on a lazy e2e import after the test loader restored sys.path. | Moved the shared import to module load. Preserve both failed and passing runs in round3-commands.json. |
| Duplicate start could release the running attempt's reservation. | A red-green lifecycle control now retains status/reservation and never resubmits the POST. |
| Retrying result after collection could replace the official receipt with a transport failure. | Round 16 reproduced the overwritten-verdict path; collected results now return the retained host receipt without another API/grader call. Native result retrieval is a GET (R1). |
| Result could proceed without confirmed server removal. | Red-green export control now stops before Git/grading until the exact owned server is gone. |
| Literal synthetic UUIDs triggered the publication session-data rule. | Reuse that rule in the unit test; construct the fixture UUID at runtime. Round 14 red/green retains the original failure with the synthetic value redacted. The shared validator is unchanged. |
| Upstream .python-version selects 3.12 while the recipe seeds build tools into 3.13. | Explicit --python keeps uv sync on the seeded interpreter (R8, installed help); round 15 red/green catches omission. This prevents ambiguous selection; no interpreter replacement was executed or observed here. |
| Trace persistence shares the model terminal's UID (R16). | Bounded no-follow reads, untrusted labels and evidence_complete=false. Separate observer qualification is declined in this round because no tested source-backed deployment is available. Native dispatch does not currently export the legacy standalone callback trace. |
| Host-loopback protection cannot be inferred from rootless mode, internal networks or MCP filters. | Disable remote MCPs, require scoped networks plus fresh external probe evidence. DOCKER-USER is source-backed (R12); its host rootless realization is deferred. A JSON assertion alone is not firewall proof. |
| A pinned top-level grader is not a dependency/build lock. | Check upstream uv.lock bytes; hash-seed build tools; locked nonisolated sync with pinned uv; no pre-commit hook install. Grader host build execution remains a disclosed declined part of S7. |
| Official grading options had local memory/CPU/PID changes. | Remove them per R10/common requirements. Digest identity gates/names/labels are transport adaptations; no grading-equivalence claim until official controls run. |

The evidence remains offline adapter/synthetic evidence. Full upstream acceptance,
independent trace qualification, rootless filtering, installed imports and model
behavior are not inferred from these tests. General anti-pattern promotion and
evidence hash registration remain coordinator-owned.
