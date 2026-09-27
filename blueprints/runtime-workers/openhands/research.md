# Source review, 2026-09-27

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
