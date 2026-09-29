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
Correction, 2026-09-27: the runtime lock security relock at the end of this file
restricts the lock to linux x86_64 and upgrades four packages, so the lock is no
longer that unchanged export.

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

## Runtime lock security relock (2026-09-27)

requirements.lock is now a **local integration lock for linux/amd64 only**:
upstream v1.49.6's uv.lock, resolved for linux x86_64 with uv's `environments`
setting, plus four security upgrades. It is no longer the unchanged upstream
export. OSV-Scanner 2.6.0 reported 14 advisories in five packages, both in CI run
36351247754 and locally with the same pinned binary on the previous lock. No
upstream fix exists yet. v1.49.6 (published 2026-09-25 at fcc102a) is still the
latest release, and main at 3311ba9eec5044f40ab5d0b3d7eddc9f7e1e2d14 pins the same
five flagged versions and keeps the cryptography constraint described below.
cryptography needs no upgrade: the restriction leaves only upstream's linux
50.0.0, which fixes all three of its advisories. Returned outputs are retained in
[evidence/relock-2026-09-27.txt](evidence/relock-2026-09-27.txt); its section F
holds the final lock.

Scope, corrected 2026-09-28 (F18): this relock changes only the recipe venv
under the install prefix. The image's server binary is a PyInstaller build from
upstream's unchanged uv.lock, which still pins anyio 4.11.0, click 8.1.8, pypdf
6.14.2 and soupsieve 2.8.4 (SDK@fcc102a
`openhands-agent-server/openhands/agent_server/docker/Dockerfile:129,139,146-158,583-590`).
[evidence/agent-server-image-grype-20260928.json](evidence/agent-server-image-grype-20260928.json)
records the digest scan and its limits.

The installed uv 0.12.17 reproduced the previous lock byte for byte in the
unchanged upstream workspace, whose uv.lock matches the pinned SHA256:

    uv export --frozen --format requirements.txt --no-header --no-annotate \
      --package openhands-tools --no-emit-workspace

That output equals the lock's first 2,856 lines; adding `--no-dev` gives the same
bytes. The last four lines are appended from pins.json `wheels`, in file order,
as `<name> @ <url> \` followed by `    --hash=sha256:<sha256>`. Together they give
the previous SHA256, c4ca55604ea0bc85e74ccaa8b2c5bf9fa7b17cec35b830eda653025cb90ebd56.

In a scratch copy of that workspace, one line was added to the existing
`[tool.uv]` table of the root pyproject.toml; nothing else in the workspace
changed:

    environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]

The pinned linux/amd64 image (pins.json `image.platform`) is the recipe's only
install target. The setting and lockfile preferences follow
[astral-sh/uv@0.12.17 docs/concepts/resolution.md:142-173 and 303-309](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/resolution.md#L142-L173).
The relock uses the existing uv.lock as preferences. The workspace's relative
`exclude-newer = "7 days"` would make an unpinned selection depend on the run
time, so the upgrades are version-pinned:

    uv lock --upgrade-package anyio==4.14.2 --upgrade-package click==8.5.0 \
      --upgrade-package pypdf==6.19.0 --upgrade-package soupsieve==2.9.2

The coordinator reproduced the relock builder's uv.lock from a fresh copy of the
unchanged workspace with that line added: SHA256
30e608b1fdb091db1609e8261a787020df12e0350911079cc2177c772a9ccffd, byte for byte,
and `uv lock --check` exits 0. uv printed the four updates and
`Updated cryptography v48.0.1, v50.0.0 -> v50.0.0`, which is the darwin x86_64
fork leaving the resolved environment. It removed cython, macholib, pefile,
pyobjc-framework-pubsub, pywin32 and pywin32-ctypes from uv.lock. The export and
wheel append above then give SHA256
02d0a7f058d08d28d0fb3f7344ed9b042bf5a317607454faf4bbb210af7fa394:

| Package | Previous | New | Advisories (fixed in) |
| --- | --- | --- | --- |
| anyio | 4.11.0 | 4.14.2 | GHSA-82r6-8w77-94w6, GHSA-5p39-cfhj-2xmp (4.14.2) |
| click | 8.1.8 | 8.5.0 | PYSEC-2026-2132 (8.3.3) |
| cryptography | 48.0.1 for darwin x86_64, 50.0.0 elsewhere | 50.0.0 (the darwin line leaves the lock) | PYSEC-2026-3552 (50.0.0); PYSEC-2026-3553, PYSEC-2026-3554 (49.0.0) |
| pypdf | 6.14.2 | 6.19.0 | PYSEC-2026-3655, PYSEC-2026-3656, PYSEC-2026-3912 (6.15.0); PYSEC-2026-3913 (6.16.0); PYSEC-2026-3910, PYSEC-2026-3911 (6.16.1) |
| soupsieve | 2.8.4 | 2.9.2 | GHSA-gjv8-xp57-g29c, GHSA-j934-xhv5-fg8f (2.9.0) |

A scratch classification checked every other change. It mapped each hash to its
file through the upstream uv.lock and evaluated markers with packaging 26.3 for
linux x86_64 under CPython and PyPy 3.12 to 3.15:

- No other package changed version, and none was added.
- Six entries were removed, and none applies on linux x86_64: colorama 0.4.6,
  pywin32 311 and pywin32-ctypes 0.2.3 (win32), cryptography 48.0.1 (darwin
  x86_64), pyobjc-framework-pubsub 11.1 (darwin) and cython 3.1.4
  (`platform_system != 'darwin' and sys_platform == 'darwin'`).
- The export adds `platform_machine == 'x86_64' and sys_platform == 'linux'` to
  every exported marker, including those of the 330 same-version entries; none
  of them changes linux x86_64 applicability. The 159 pyobjc entries remain: uv
  keeps their upstream `platform_system == 'darwin'` term beside the Linux
  marker, and the combined markers never hold there.
- 1,694 hash lines were removed from 129 same-version entries. All are wheels for
  other platforms: macOS, Windows, iOS, Android, and Linux on aarch64, armv7l,
  i686, ppc64le, riscv64 and s390x. No sdist or linux x86_64 wheel hash was
  removed, and none was added.

anyio stops at 4.14.2 because 4.15.x requires typing_extensions>=4.16.0 below
Python 3.15, and typing-extensions 4.15.0 stays locked. A dry run that also
released typing-extensions selected anyio 4.15.1. soupsieve 2.10 was uploaded on
2026-09-24, inside the seven-day window.

The restriction replaces a constraint override. cryptography 48.0.1 existed only
on the darwin x86_64 fork, which the image never installs, yet OSV-Scanner's
`--no-resolve` requirements.txt scan still reported that marker-gated line. In
the universal resolution, `uv lock --upgrade-package cryptography` printed
`Updated cryptography v48.0.1, v50.0.0 -> v48.0.1` under pyproject.toml:18,
`"cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'"`.
The fork collapsed, which would downgrade Linux. That line stays unchanged and
now falls outside the resolved environment. Deleting it was tried only in
scratch and declined. An intermediate universal relock of the other four
packages (SHA256 da0d550f1e03d42ef2d1f4fe31a608eb8abdb796ecb9354d30457875f2172d71)
left the three cryptography advisories open; it is superseded, and its outputs
stay in the evidence file. So is a five-package variant that also moved
cryptography to 50.0.1 (uv.lock b3e8a6f4..., requirements.lock f215ac9f...;
evidence sections C to E): the linux 50.0.0 already carries every fix.

The consistency check used a Python 3.13.15 scratch venv and the
install-container.sh sequence, with UV_NO_CONFIG=1:

- build-requirements.lock with `--require-hashes --no-deps --only-binary :all:`
  exited 0;
- the runtime lock with `--require-hashes --no-deps --no-build-isolation` exited
  0 (`Installed 175 packages`: anyio 4.14.2, click 8.5.0, cryptography 50.0.0,
  pypdf 6.19.0, soupsieve 2.9.2); func-timeout 4.3.5 is its only sdist;
- `uv pip check` exited 0 (`All installed packages are compatible`).

A runtime-lock install with `--only-binary=:all:` exits 1, because PyPI has only
sdists for func-timeout 4.3.x, as recorded above. Without UV_NO_CONFIG=1, step 1
run inside the workspace exits 2: the workspace's `constraint-dependencies`
(`starlette>=0.49.1`) is not a hashed `==` pin. The script's import check, run
offline under bwrap (`--unshare-net`), printed `SDK/tools 1.49.6 imports passed;
no model request`. These are host scratch checks. The image installation, model
behavior and runtime paths through the upgraded packages remain unmeasured.

Overturn conditions: return to the unchanged upstream export once an SDK release
pins fixed versions; add linux aarch64 to `environments` if the recipe adds an
arm64 image.

| Proven issue | Correction |
| --- | --- |
| `UV_NO_CONFIG=1` also stops `uv lock` from reading the workspace pyproject.toml. Installed help: "Avoid discovering configuration files (`pyproject.toml`, `uv.toml`)". The first relock printed `Resolving despite existing lockfile due to removal of global exclude newer` and chose soupsieve 2.10 from inside the seven-day window. | Relock without it so `[tool.uv]` applies; `uv lock --check` on the unchanged workspace exits 0. Keep UV_NO_CONFIG=1 only for the `uv pip install` steps, as install-container.sh does. |
| In the universal resolution, `--upgrade-package cryptography` collapsed the marker-split fork to the constrained 48.0.1. | Read every `Updated` and `Removed` line before accepting a relock. Resolve only the recipe's install environment with `environments` instead of deleting an upstream constraint, and classify every removed or re-marked line. |
| The coordinator's decision to keep cryptography at 50.0.0 reached the relock builder after it had relocked five packages from an earlier instruction (evidence section C). | A decision that changes a brief goes out as one message naming what it replaces. The final lock was reproduced from the unchanged workspace before commit (evidence section F). |

## Takeover phase 1 corrections (2026-09-28)

These are offline repairs on the round-3 head 45d40f6c. The network and
isolation design (egress policy, arm endpoints, MCP endpoints) is phase 2 and is
unchanged here. Red and green unit runs are in
[evidence/phase1-commands.json](evidence/phase1-commands.json). SDK sources are
at fcc102a; paths are abbreviated below and given in full in README.md.

| Finding | Correction and source |
| --- | --- |
| F16: a run that ended `stuck` or at the iteration limit skipped grading and exited 3. | Status `stuck`, or status `error` whose newest `ConversationErrorEvent` has source `environment` and code `MaxIterationsReached`, now exports and officially grades the partial patch and exits 1, never 0. Sources: `state.py:48-79`, `local_conversation.py:727-733,753-755,2021-2043,2339-2360`, `conversation_error.py:11-42`, `event_router.py:68-139`, `event_service.py:456-460`, `models.py:95-99`. Any other error stays ungraded with exit 3. |
| F17: receipt trace, skill, MCP and version fields were read from `/run-output`, which the model can write. | The REST event store is not an independent source either: the terminal runs under the server's UID (`subprocess_terminal.py:157-170`), and the server reads persisted events from files it re-indexes from disk (`event_service.py:420-431`, `event_store.py:144-169,320-362`). Those fields are now `not_collected` with the reason (receipt schema 4). The server-reported agent-limit value only selects exit 1 or 3. |
| F18: the README implied the relock covered the image. | The relock covers only the recipe venv; see the scope note in the relock section. [The digest scan receipt](evidence/agent-server-image-grype-20260928.json) records grype 0.119.0 counts and the cataloger's PyInstaller boundary. |
| F19: host loopback access still had to be enabled for the gateway. | **Overturned** for the reference host by read-only checks on 2026-09-28: its rootless `docker.service` sets `DOCKERD_ROOTLESS_ROOTLESSKIT_DISABLE_HOST_LOOPBACK=false`, and the running rootlesskit has no `--disable-host-loopback` flag. The upstream default is still to disable it (moby/moby@a46e6fa7 `contrib/dockerd-rootless.sh:23-24,170-173`, identical to the installed 29.8.1 script), so a new host repeats both checks. The open item is the egress limit (phase 2). |
| F20: round-1 files were no longer used. | `git grep` at 45d40f6c found no reference outside evidence logs and manifests/evidence.json. Removed config/skills.lock.json, e2e/frozen.json, e2e/task.txt and e2e/fixture-repo/. |
| The server env file was not checked for the session key. Without one the server binds only its container loopback (`__main__.py:282-285`, `config.py:24`). | Preflight parses the file's variable names with Docker's env-file rules (docker/cli@v29.8.1 `pkg/kvfile/kvfile.go:92-124`) and requires `OH_SESSION_API_KEYS_0`. Values are never extracted, printed or logged. |
| The published port was fixed at 3730, which PR #428's crawl4ai recipe also uses by default. | `--port` accepts integers in 3730..3799, as PR #428's `host.py:44-45` does at 3ad8ba2. The default stays 3730 and the resolver uses 3740. The port is stored in status.json and checked again by dispatch. |

A follow-up commit applied the coordinator's decisions of 2026-09-28. Red and
green runs are in
[evidence/phase1-followup-commands.json](evidence/phase1-followup-commands.json).

| Item | Decision and source |
| --- | --- |
| F16 forgery bound | The newest-`ConversationErrorEvent` design stays. The strict alternative, exit 3 for every `error`, would label every honest iteration-limit run an infrastructure failure. `dispatch.py` `PERMITTED_TERMINATIONS` keeps a label only as a refinement of the REST status, so exit 0 requires REST `finished`. A planted event can move exit 3 to 1 and no further. The README states the residual and the analysis rule: exit 1 and exit 3 are both non-success, and reruns re-queue only exit 3. |
| `install()` image identity, open after phase 1 | Fixed. Both a plain and a `--platform linux/amd64` inspect must list the exact pinned ref in `.RepoDigests`. The plain `.Id` must be the index digest (containerd store) or the config digest (classic store). On containerd the platform `.Id` and `.Descriptor.digest` must be manifest `ec7ed86f...`; on classic the platform `.Id` must be the config and no descriptor may appear. Sources: moby docker-v29.8.1@464cd50c `daemon/containerd/image_inspect.go:28,71-73,95,97`; `daemon/images/image_inspect.go:59`, `daemon/images/image.go:160-197`, `daemon/internal/image/store.go:152,160`, `daemon/internal/image/fs.go:120`, `daemon/internal/distribution/pull_v2.go:431-434,705-747,845-867`; `api/swagger.yaml:1826-1850`. Inspect with `--platform` needs Engine API v1.49 (`api/docs/CHANGELOG.md:175-180`). On the containerd store no field reports the config digest. That covers inspect, history (`daemon/containerd/image_history.go:113-115`) and the manifest summary (`api/swagger.yaml:8216-8335`). The content-addressed platform manifest binds the config there. The Docker containerd image-store page (docker/docs@3c117d8e `content/manuals/engine/storage/containerd.md`) does not describe image IDs. |
| Empty `OH_SESSION_API_KEYS_0=` value | Documented residual, because preflight compares only the name: it reads the file, but never checks, logs or returns the value. SDK@fcc102a `env_parser.py:183-197` turns it into a one-item list holding an empty string, and `__main__.py:30-48` then treats authentication as enabled. |
| Unused `run_worker`, `record_event`, `observations()` | Kept, because references remain: `worker.py:202,232`, and `observations` is used in `tests/test_runtime_worker_openhands.py`. |

Open finding from this phase, not changed here:

- The module-qualified event kind string is source-reviewed only. If the live
  server used a different kind, the agent-limit check would fail closed to
  exit 3.

## Takeover phase 2 corrections (2026-09-28)

This phase is an offline build on efa73f40 following the coordinator's
phase-2 plan: section 1 (isolation design) and items E1, E2, E3 and E5. Item
E4, resolver mode, goes to a follow-up PR. The phase ran unit tests with Docker
mocked plus read-only host observations, then the repository's validate-job
checks and full unit suite in a network namespace with only loopback. Each
failure there also occurs at the base. It created no attempt network or
container and made no gateway or model request.
- Commands and outputs:
  [evidence/phase2-commands.json](evidence/phase2-commands.json).
- The choice and its alternatives:
  [decision record](../../../docs/decisions/2026-09-28-openhands-resolver-isolation.md).
- Full detail: README.md, [Security posture](README.md#security-posture).

| Finding | Correction and source |
| --- | --- |
| The phase-1 contract was a DOCKER-USER rule plus an operator receipt (R12 and the host-loopback row in the round-2 log above). An L4 rule to the gateway port cannot separate `/v1/*` from `/api/*` on the same port, and its placement in the rootlesskit namespace was never probed. | **Replaced by O1 (E1).** `$S-int` is created with `--internal`, IPv6 off and gateway mode `isolated`; `$S-gw` is a normal bridge; a pinned proxy joins both. The same docker/docs@4e9a5751 page that R12 cites for the caveat also gives the remedy: `port-publishing.md:186-192` ("No address is assigned to the bridge when the network is created with gateway mode `isolated`"), with the options at `:121-131`. If the option is rejected, the attempt fails closed with no retry on plain `--internal`. Networks are read back through a fixed `--format` template. R12's DOCKER-USER mechanism is superseded; the row stays as history. |
| F19 (host loopback), overturned for this host in phase 1. | No longer a design input. O1 relies on host loopback for the proxy's upstream and keeps the agent-server off it through the internal network. |
| Each arm's base URL pointed at its gateway port directly. | **Both arms now use `http://gw:8081/v1`.** The proxy's upstream is `10.0.2.2:20128` for control or `10.0.2.2:20129` for engines-on, taken from `recipe.arm_config`. Engines-on accepts only the seven recorded combos (`allow-lossy`, the default, plus `fw-ccr`, `fw-codex-responses`, `fw-headroom`, `fw-lite`, `fw-rtk` and `fw-session-dedup`); control sends no compression header. Control stays the default arm until the #431 A/B. |
| New: the gateway proxy. | **Composed locally; no upstream ships it.** Directive sources are nginx.org `ngx_http_core_module` (`location` matching on the normalized URI, `=` exact match, `limit_except`, where GET also allows HEAD), `ngx_http_proxy_module` (`proxy_pass` with a URI, `proxy_pass_request_headers`, and `proxy_set_header`, where an empty value is not passed) and `ngx_http_rewrite_module` (`if`, false only for "" or "0"), all fetched 2026-09-28. Source lines are from nginx/nginx@release-1.30.5 (4556c714): `ngx_http_proxy_module.c:1240-1251,1365-1384` shows arguments are appended even to a fixed URI, hence `if ($is_args) { return 403; }`; `:1301-1303,1417-1418` shows empty headers are skipped; `ngx_http_variables.c:1609-1624` defines `$is_args`. |
| The proxy image needed a pin. | `ghcr.io/nginx/nginx-unprivileged@sha256:ed04ec1f…`, tag observed `1.30.5-alpine`. The SHA-256 of the registry's index, linux/amd64 manifest (`f4522a5f…`) and config (`61640a44…`, user 101, revision 588b4cbc) bytes equals each digest. A pull by index digest reported "Image is up to date", and `pinned_image_identity` returned the containerd store. The digest has not been vulnerability-scanned (plan gate G2). |
| The session key came from a coordinator-supplied file (E2). | **Generated per attempt** with Python's `secrets` module. Two files, `<stem>.server.env` (Docker env-file syntax) and `<stem>.headers`, are written with `O_CREAT\|O_EXCL\|O_NOFOLLOW` at 0600 under `<state>/secrets/` (0700). The key is never in argv, and no full inspect is run. The files are deleted after confirmed container removal and kept while removal is unconfirmed. **Deviation:** the pointer variables `OPENHANDS_SERVER_ENV` and `OPENHANDS_HEADERS` are retired, because the paths derive from the validated identity. This also ends the phase-1 empty-value residual. The inventory row is `openhands-session` (`generated_local`). |
| The container environment list. | **Deviation:** `OPENHANDS_COMPRESSION` was added to the plan's closed list, so the request serializer and the server's preload rebuild the arm selection the host checked. |
| Native routes were checked by path only (E3). | Each route is now paired with exactly one method: POST `/api/conversations` and `.../interrupt`, and GET for the conversation, the final response and the error-event search. Any other pair is refused before curl runs. |
| No proof of containment before a model runs. | **P0-P2 probe and dispatch gate.** `e2e/netprobe.py` runs in the pinned agent image with the model-container hardening. The host writes the receipt `isolation-probe.json` at 0600, bound to the two network IDs and the two container IDs. `dispatch.py start` requires it to be at most 900 s old and to match the live IDs, the rendered-config hash and the probe-script hash. The run receipt moves to schema 6, with an `isolation` summary carrying no IDs or addresses. |
| MCP endpoints on the host. | ai-memory and socraticode stay disabled, now with the reason that they are unreachable by design under O1. The proxy has no route to either. |
| Addition, not a plan item. | `host.py teardown` removes a prepared attempt after a probe-only run and retries unconfirmed removals. It refuses while a conversation may be live or the serial reservation names the attempt. |

Open items from this phase:

- **Not run:** the live P0-P2 probe, and the P3-P5 model calls, which exist as
  documented steps and a skeleton. G7's P3 half was not enforced in code;
  *(repair round)* the dispatch gate now requires the coordinator's recorded
  stage-gates file.
- **Unprobed:**
  - gateway mode `isolated` under rootless Docker 29.8.1;
  - nginx under `--read-only` with `--entrypoint nginx`;
  - body framing and streaming under the header allowlist;
  - the container `--format` template, checked live only for its network
    counterpart.
- **P2 is strict** about IPv6. Any non-loopback IPv6 address, including a
  link-local one, fails it. *(Corrected in the repair round.)* This build also
  added each network's subnet `.1` as a target and refused to probe when an
  attempt container held one. On the isolated `$S-int` the server always holds
  `.1`, because moby allocates no gateway there, so every live probe would
  have refused. Targets now come only from recorded IPAM gateways. The attempt
  containers' own addresses are excluded and recorded by role, and never
  cause a refusal.
- **Still open from the plan:**
  - G2, the image scans;
  - G5, the model surface: a `/v1` body can pick any model the arm serves.
    *(Repair round)* The dispatch gate now reads each reachable store
    read-only and refuses providers outside a per-arm allowlist, including
    row-less no-auth and anonymous-fallback providers that settings leave
    enabled. It has not run against the live stores;
  - F10, the client peer the gateway logs;
  - normal-bridge containers such as cognee-live still reach host loopback.
- **Outside this recipe's paths:** the repository's secret-path guard covers
  the `secrets/` directory since #468 (merged 2026-09-28, `11a23f1b`): readers,
  copies and searches of it, its files and a glob in it are blocked, and the
  settings template denies `Read` of it. `docker exec` into the agent-server and
  a full `docker inspect` of it still show the key (recorded guard gap).

## Repair round (2026-09-28)

Two independent reviews of e45c3cd1 returned changes-needed: a headless Claude
review and a GPT-6 review. This single repair round adds commits on top of
e45c3cd1 and nothing else. Every code item had a failing test first. Each red run
and each fixed commit's suite, re-run from `git archive`, is in
[evidence/repair-round-commands.json](evidence/repair-round-commands.json). No
container, network, gateway or model request was made. The G5 tests read
synthetic sqlite stores, and an audit hook showed that the suite opened nothing
under the live OmniRoute data directories.

| Finding | Correction and source |
| --- | --- |
| R1 (Claude blocker; GPT-6 containment-grader, high). The official grader ran the model's patch on Docker's default bridge, which reaches host loopback. | **Grading has no network (9302ec23).** Every grader container gets network mode `none`, "No networking for this container" (docker/docker-py@7.1.0 `docker/models/containers.py:686-694`). The adapter refuses other options, checks the SDK create body (`api/container.py:445-457`, `types/containers.py:351`) and refuses to grade a container whose inspect shows another network. moby@docker-v29.8.1 records mode `none` as the single network `none` and refuses to connect it elsewhere (`daemon/create.go:251`, `daemon/container_operations.go:202-204,363-406`). Verdicts are offline verdicts (SWE-bench@v4.1.0 `test_spec/python.py:443-444`, `test_spec/test_spec.py:55-60`). |
| R2 (Claude, medium). Every live probe would have refused its own server: the isolated network has no gateway, so the server holds `.1`, which the probe targeted. | **Targets come only from recorded IPAM gateways (92de42e8).** moby@464cd50c skips the gateway in isolated mode (`bridge_linux.go:700-713`, `network.go:1594-1602`). The attempt containers' own addresses are excluded and recorded by role, never refused. The fixtures now model the isolated network. |
| R4 (Claude, low). P2 counted timeouts as containment, tried TCP only and asserted no route table. | **Stronger P2 (92de42e8).** A positive control to `gw:8081` runs first. Off-subnet pairs must fail with `ENETUNREACH` or `EHOSTUNREACH`. One DNS datagram (RFC 1035 4.1.1-4.1.2) to 10.0.2.3:53 (rootlesskit@v3.1.0 `docs/network.md:81-82`) must get no answer. `/proc/net/route` (linux@v6.18 `net/ipv4/fib_trie.c:2940-3000`) must hold no default or gateway route. |
| Addendum b (Claude C4, info). DNS negatives did not tell `EAI_AGAIN` from `EAI_NONAME`. | The resolver's error class is recorded in the observation and the receipt (92de42e8). The pass condition stays "no address resolved". |
| R6 (Claude, low) and GPT-6 probe-receipt-trust (low). G7, G2 and G5 held only in documents, and the gate trusted `passed` flags. | **Recorded stage gates and re-derived counts (185de718).** The gate re-derives P0-P2 from the recorded counts and refuses a contradictory receipt. It also requires the host-owned `stage-gates.json` with P3 (plus P4 and P5 for engines-on), G2 for both pinned images and G5, each bound to the proxy image and template. In the docs commit the README calls P0-P2 bounded observations and states the trusted-producer limit. |
| R3/G5 (Claude, high). The request body picks the model, and nothing enforced G5. | **G5 at every start (726849b3).** The gate reads each store the arm reaches read-only and refuses providers outside the host file's per-arm allowlist. Row-less no-auth and anonymous-fallback providers must be disabled in settings, and routing combos are refused. Sources: OmniRoute@045aa81f3 and @dd6e9607e, listed in the decision record. |
| R5 (Claude, low). "Pass `correlation_ids={run_id}`." | **Not applied as written (5a0b0a54).** At both builds `/v1/responses` hands `handleChat` a fresh `randomUUID()` (`src/app/api/v1/responses/route.ts:193,213`, `src/shared/utils/requestId.ts:100-102`, `src/sse/handlers/chat.ts:436`), and `call_logs.correlation_id` stores it (`open-sse/handlers/chatCore/attemptLogging.ts:611`, `src/lib/usage/callLogs.ts:713,786,801`). Only `/v1/chat/completions` keeps a caller ID (`route.ts:292-322`). The recipe fixes `/v1/responses`, so the filter would drop every row; entry 11 of the evidence shows it turning the fixture's usage into `empty_window`. Receipts keep time-window attribution, and the attribution string now says why. A regression test counts rows with gateway-generated IDs. P3's correlation check moved to a `/v1/chat/completions` call. |
| GPT-6 session-key-logging (low). "Never in output or logs" was too strong: the model can put the key into a request line, and the combined log keeps it. | The host side (8080) logs time, method and status only (`ingress`; nginx release-1.30.5 `ngx_http_log_module.c:170-171,230-232`). The README now says the driver does not intentionally log the key. The agent side's access log and request-bound error entries (`ngx_http_request.c:4103-4107`) can still hold it, and the retained proxy log survives key-file deletion. |
| GPT-6 gw-8080 (info). "Only three routes are reachable" was false: nginx listens on every interface, so the agent reaches `gw:8080`. | Every such claim now says that three routes reach OmniRoute and that `gw:8080` reaches only the agent's own server: README, decision record, MCP policy reasons and the netprobe docstring. |
| GPT-6 nginx-headers (info). The header description omitted fields nginx generates. | The README lists the defaults (`ngx_http_proxy_module.c:747-757`, merged at `:4210-4228`). At release-1.30.5 these are the generated `Content-Length` or `Transfer-Encoding: chunked` and an empty, so omitted, `Connection`, with no `Connection: close`. It also lists the framing refusals (`ngx_http_request.c:2034-2064`). |
| C9 (Claude, medium). The decision record said isolation "holds by construction" and the narrowing said "no host access". | The record now separates three parts. The agent-server's containment and grading's lack of a network hold by construction. What the three routes reach is G5's checked gateway state. Nothing has been observed live. Narrowing condition 2 names the proxy routes, the session key, G5 and offline grading, and G5 joins the narrowing's overturn list. |
| Addendum a (GPT-6 session-key-lifecycle wording). "Values stay unread" was inaccurate. | `check_server_env`, the README and this file now say that the host reads the file and compares only the variable name, and never logs or returns the value (5a0b0a54 and the docs commit). |
| Found while editing P3. P3 expected model `cx/gpt-6-astra-max` in the row, but the receipt matches the routed model. | P3 now expects `gpt-6-astra-max`, the value `receipt.summarize_gateway` matches. |

Open after the repair round:
- **Live and unrun:** P0-P5, G2's scans and G5 against the live stores. The
  stage-gates file does not exist, so `dispatch.py start` refuses. G5 will
  likely refuse the live stores until three things are done. The ten no-auth
  providers must be blocked and the four anonymous-fallback providers disabled
  in both gateways' settings. Routing combos must be removed.
- **Source-derived only:** that off-subnet connects on the rootless isolated
  network fail with `ENETUNREACH` or `EHOSTUNREACH`, and that nginx accepts the
  `ingress` log format (no running nginx has parsed the template).
- **Per-attempt usage attribution** needs a host-trusted capture of
  OmniRoute's returned ID or an upstream change. The agent side's access log
  could record `$upstream_http_x_correlation_id`. The streaming
  `/v1/responses` route passes no extra headers to its early response, though,
  so that capture may miss streamed calls. Until one is shown, receipts
  include concurrent callers of the same model and path.
- **Grading is offline:** an evaluation that needs downloads fails. The gold
  and negative controls run under the same condition.
- **G5's limits:** it cannot see a Codex connection's app-server opt-in
  (`open-sse/executors/codex.ts:415-439`). It counts inactive rows as served. Its
  provider lists are tied to the two builds read.
