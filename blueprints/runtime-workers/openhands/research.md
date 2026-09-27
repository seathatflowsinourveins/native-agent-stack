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
