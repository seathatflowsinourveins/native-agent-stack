# OpenHands coding runtime worker

This is a **recipe awaiting host execution** for OpenHands Software Agent SDK
1.49.6, powered by the local OmniRoute gateway. The SDK owns the agent loop,
tools, conversations, skills and context condensation. The worker repairs one
frozen Python fixture in an owned copy. It never receives this repository as its
coding workspace. This addition does not change the foundation catalog's adoption
status, install software, start services, pull an image, or perform a model run.

## Pinned sources and artifacts

The primary is [OpenHands/software-agent-sdk v1.49.6][release], commit
`fcc102a697874d54a357e36004e02c95040dbdc0`. [pins.json](pins.json) contains full
URLs and hashes. Source/archive and lock hashes were computed from returned
upstream bytes; wheel hashes came from version-specific PyPI release metadata
and were independently checked against downloaded wheel bytes. GHCR index,
platform manifest and config hashes were computed over registry responses. The
config's `OPENHANDS_BUILD_GIT_SHA` and `OPENHANDS_BUILD_GIT_REF` match this tag.

| Artifact | SHA256 |
| --- | --- |
| Commit-addressed source tarball | `2d3006de86eaec690a82e497fcd4459816637afe6e53f7da87783183792148a8` |
| Upstream `uv.lock` | `d13a41b86c48e66e1719b19d8e2d3a315abfab87c257fb18881ce4e31075c910` |
| Published agent-server `1.49.6-python` multiarchitecture index | `02ef66fdf0b22a40b0b55c5cca8d1790cfd260c5069f7c0b99edc1b505d5ab37` |
| Selected Linux amd64 image manifest | `ec7ed86f4021a21e161815853156521b44929d913f2e6ee06a173ef2f660aa12` |
| Linux amd64 image config | `39426d8ce5c3ecaf6829063ec8ccfe5c289f049ae007fb14d89317b3982d196f` |
| `openhands_sdk-1.49.6-py3-none-any.whl` | `3b4701f125925e804929ab02b61fe2fe10b4fb1e7d723a2c4afdea35566328bb` |
| `openhands_tools-1.49.6-py3-none-any.whl` | `11e57a6635fd93c9f1fed14f804ab6f24a4873f75a2d35f0d1c3e57df2c51c87` |

The image reference used by every container invocation is
`ghcr.io/openhands/agent-server@sha256:02ef66fdf0b22a40b0b55c5cca8d1790cfd260c5069f7c0b99edc1b505d5ab37`,
with `--platform linux/amd64`. Docker verifies its content-addressed blobs; the
installer also checks the resolved image configuration ID. The pinned image
includes Python 3.13.15, Node 24.21.0 and uv 0.12.15. These facts come from the
[Dockerfile language runtime, lines 39–47][docker-runtime], [uv copy, lines
402–403][docker-uv], and the returned image metadata. No image was pulled here.

All 295 comparable SDK Python files and 93 tools Python files in the downloaded
wheels matched their corresponding files at the pinned commit. The compact
[byte-comparison record](evidence/wheel-source-comparison.json) is artifact
evidence, not execution.

## Supported installation paths and the choice

Upstream's [README, lines 49–81][sdk-readme] shows the standalone SDK API and
directs source development to `make build`. Its [Makefile, lines 34–41][makefile]
runs `uv sync --dev` and installs Git hooks. The [container source build, lines
128–140][docker-sync] copies the four workspace packages and root lockfile, then
uses `uv sync --frozen --no-editable`. The [official getting-started
guide][getting-started], read 2026-09-27, documents the package path
`pip install -U openhands-sdk openhands-tools` and optional workspace/server
packages. This recipe pins those two published packages and their dependencies.

The selected path runs the standalone SDK **inside the pinned agent-server
image**, overriding its entrypoint. There is no agent-server HTTP listener, port
publication or host workspace execution. The agent loop, LLM calls and every
stdio MCP subprocess run in that container; HTTP MCP calls originate there too.
Host code only provisions owned files, invokes rootless Docker, copies fixture
bytes, supervises deadlines and reads the permitted gateway log columns.

This choice addresses two details found at the tag:

- `DockerWorkspace` is a `RemoteWorkspace`; the [remote example, lines
  92–97][remote-example] explicitly asserts `RemoteConversation`. Creating that
  object from host Python does not keep the LLM loop on the host. Its [native
  launch, lines 218–251][docker-workspace] publishes a port without an explicit
  host IP. The chosen listener-free path needs no port from the 3700–3799 range.
- The published `python` image uses the **binary** target, according to the
  [release matrix, lines 281–339][image-matrix]. Its entrypoint launches a
  PyInstaller server executable. The source venv exists only in the [separate
  source targets, lines 564–598][image-targets]. Therefore the installer creates
  its own importable SDK venv inside the image, in a mounted owned prefix.

[install.sh](install.sh) is idempotent and uses `set -euo pipefail`, `umask 077`,
no sudo and the existing `rootless` Docker context. It verifies prerequisites,
private host inputs, installed skill hashes and requirement-file hashes before
download/install. It verifies the source archive and `uv.lock` SHA256, pulls only
the digest pin, and invokes [install-container.sh](install-container.sh).

The prefix is `$HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6`; durable
private state is `$HOME/.local/state/native-agent-stack/runtime-workers/openhands/`.
Owned directories are mode 0700 and files inherit the restrictive umask. The
venv is for the image's interpreter, so its Python symlink may not resolve on the
host. Install logs are retained in separate `install-attempts/attempt-*` folders.
Docker's content store remains owned by the separately provisioned rootless
daemon; temporary container files disappear with that container.

[requirements.lock](requirements.lock) is an unchanged dependency export from
the upstream lock, with only the two published workspace-package wheel references
and their hashes appended. It was produced using uv 0.12.17:

```sh
uv export --locked --no-dev --package openhands-tools --no-emit-workspace \
  --no-editable --no-annotate --no-header --format requirements-txt \
  --output-file requirements-dependencies.lock >/dev/null
```

An ordinary isolated source build could fetch `setuptools>=83` outside that
lock ([SDK pyproject, lines 41–43][sdk-pyproject]). Conversely, requiring all
binary dependencies would fail: locked `func-timeout==4.3.5` has only a source
distribution. [build-requirements.lock](build-requirements.lock) therefore
bootstraps setuptools 80.9.0, wheel 0.46.3 and packaging 26.3 from hashes in the
same upstream lock. `uv pip install --require-hashes --no-deps
--no-build-isolation` then uses the complete exported requirements. There is no
unlocked dependency or build-dependency resolution. A missing build prerequisite
fails visibly. This follows [uv's documented build-isolation escape hatch][uv-build].
`uv pip check` and SDK/tool imports are installation checks, never a model trial.

## Model, headers and native context features

[config/worker.json](config/worker.json) retains the requested host-side reference
URL `http://127.0.0.1:20128/v1`. [recipe.py](recipe.py) renders
`http://10.0.2.2:20128/v1` for the actual container-side LLM calls, following the
coordinator's measured rootless networking facts. No gateway configuration is
changed. The only API-key value is the keyless placeholder `local-loopback`.

| Setting | Upstream key and source at the SDK commit | Recipe behavior |
| --- | --- | --- |
| Model and gateway | `LLM.model`, `base_url`, `api_key`; [standalone example][hello] | Default `cx/gpt-6-astra-max`; override with `OPENHANDS_MODEL`. The LiteLLM `openai/` provider prefix is added by the driver and stripped before the gateway request. |
| Responses endpoint | `LLM.api_mode`, `model_canonical_name`, `capability_overrides`; [llm.py:408–439][llm-config] | Explicit `responses` and canonical `openai/gpt-6`; reasoning and Responses capabilities are set explicitly for the alias. |
| Maximum effort | `LLM.reasoning_effort`; [llm.py:537–549][llm-effort], [responses_options.py:58–86][responses-options] | Send `max` on Responses; gateway alias suffix also pins max. Never send `auto`. |
| Sampling/cache safety | `LLM.temperature`; [llm.py:369–380][llm-config] | Omit temperature entirely, including condenser calls. The legacy exact semantic cache is not relied on. |
| Affinity and idempotency | `LLM.extra_headers`; [llm.py:442–445][llm-config]; public [generate/agenerate:1580–1643][llm-generate] | One private `x-omniroute-session` per conversation, shared by agent/condenser; fresh `Idempotency-Key` per logical SDK call. Native retries retain that logical call's key. |
| Streaming | `LLM.stream`, `Conversation.token_callbacks`; [llm.py:464–470][llm-config], [Conversation signature][conversation] | Agent streaming enabled with a token callback. Native condenser disables ordinary streaming because it consumes a whole summary; [condenser:83–95][condenser]. Temperature is absent so the low-temperature streaming condition does not apply to summaries. |
| Context summary | `Agent.condenser=LLMSummarizingCondenser`; [example 14][condenser-example], [condenser:48–78,99–154][condenser] | `max_size=80` events, `keep_first=2`, `max_tokens=60000`; preserve initial task/system context and summarize older events. This is an input-pressure threshold, not a total-spend cap. |
| Output and run bounds | `LLM.max_output_tokens`, `num_retries`, `timeout`; [llm.py:340–407][llm-config]; `Conversation.max_iteration_per_run` [conversation][conversation] | 16,384 output tokens, 2 retries, 180-second request timeout; 40 agent iterations and a 1,200-second container deadline. |
| Terminal output recovery | `TerminalObservation.to_llm_content`, `MAX_CMD_OUTPUT_SIZE`, `full_output_save_dir`; [definition:175–200,320–330][terminal], [constants:18–21][terminal-constants] | Native 30,000-character truncation saves full output in the conversation's private observation persistence directory. |

The tiny header adapter subclasses `LLM` only at its public generation methods.
It keeps the upstream agent loop, serialization, retry implementation and
condenser. Upstream [model_copy:783–798][llm-copy] preserves the subclass, and the
condenser calls `generate`/`agenerate` at [lines 229 and 423][condenser]. This
behavior was source-reviewed; actual gateway headers still need host observation.

The upstream [GPT-6 model feature note:190–200][model-features] warns about tools
plus reasoning effort on chat completions. The coordinator measured that this
gateway handles that combination on 2026-09-27; the recipe nevertheless uses the
supported Responses path. Switching to chat is not an automatic fallback. A
future chat-only adaptation must rely on the max alias and omit request effort.
Model currency is configurable, not claimed to be permanently settled.

No gateway compression, dedup, semantic-cache or contextBudget changes are made.
There is no OmniRoute embedder. The task's small size may never trigger the
condenser; configured condensation and observed condensation are separate claims.
The SDK declares `LLM.max_message_chars`, but source inspection found no active
consumer of that field in this standalone generation path. It is therefore not
used as a claimed universal MCP-output cap. The terminal's real truncation/offload,
Serena's answer limit, bounded retrieval and condenser provide the containment.

## MCP and skills

Launch commands are derived from this checkout's
[base Codex template](../../../adoption/templates/codex.config.template.toml) and
[stack-worker limits](../../../adoption/templates/codex.stack-worker.config.toml).
Those files intentionally omit project-scoped jCodeMunch; its command and
`route/menu/order` front door come from the
[project template](../../../adoption/templates/project.codex.config.template.toml).
No command was guessed. [config/mcp.template.json](config/mcp.template.json) uses
the SDK's `mcp_config` and [MCPServer transport/command/args/env/cwd/url fields,
lines 497–530][mcp-config]. All stdio servers start in `/workspace`.

The SDK does not implement Codex `enabled_tools`, `disabled_tools` or approval
keys in MCPServer; imported unknown fields are dropped at [lines 626–664][mcp-config].
[recipe.py](recipe.py) therefore translates [mcp-policy.json](config/mcp-policy.json)
into native `Agent.filter_tools_regex`, applied both at initialization and MCP
tool updates ([agent/base.py:153–158,565–568,960–978][agent-base]). Locked FastMCP
3.2.0 uses one underscore, `server_name_tool_name`, for multi-server configs
([transport][fastmcp-config], [namespace implementation][fastmcp-namespace]).
The worker refuses a singleton config rather than silently losing those prefixes.

| Server | Scope / allowed tools |
| --- | --- |
| context-mode | Native pinned Node command; `CONTEXT_MODE_PROJECT_DIR=/workspace`; `ctx_upgrade` and `ctx_purge` excluded. |
| serena | Native `start-mcp-server --transport stdio --context codex`, adapted to supported `--project /workspace` because the fixture has no Git metadata. Dashboard/GUI disabled. `SERENA_HOME=/state/mcp/serena/home`; metadata lives outside the fixture using `project_serena_folder_location`. |
| jcodemunch | Native `jcodemunch-mcp`; only `route`, `menu`, `order`; private `CODE_INDEX_PATH=/state/mcp/jcodemunch`; savings sharing disabled. This front door is not a read-only sandbox, as the project template notes. |
| qmd | Native `qmd --index native-agent-stack-catalog mcp`; only `query`, `get`, `multi_get`, `status`. Fresh owned index contains exactly `foundation-docs`, `foundation-adoption`, `us-equities-foundation`, `us-equities-catalog`. |
| ai-memory | HTTP `http://10.0.2.2:49474/mcp`; only `memory_query`, `memory_read_page`, `memory_recent`, `memory_status`, `memory_briefing`. |
| socraticode | Native pinned Node command; only `codebase_search`, `codebase_status`, `codebase_list_projects`, `codebase_health`; `SOCRATICODE_WATCHER=manual`. Local embedding endpoint is `10.0.2.2:18232/v1`, never OmniRoute. |
| headroom | Configured but disabled. Its conditional allowlist is exactly `headroom_compress`, `headroom_retrieve`, `headroom_stats`. Native output offload and condensation already contain this task's output; no remaining gap justifies another layer. |

Serena's pinned source explains why cwd inference fails on a plain fixture
([cli.py:369–383][serena-cli]), its actual `SERENA_HOME` key
([config:65–78][serena-home]) and the external project metadata template
([config:928–936][serena-project]). The native loader fills missing defaults and
requires `projects: []` ([config:1050–1104][serena-loader]). The private copy of
[serena_config.yml](config/serena_config.yml) also bounds default answers to
30,000 characters. No host Serena configuration is changed.

QMD uses [QMD_CONFIG_DIR][qmd-config] and [INDEX_PATH][qmd-store] for attempt-owned
state. [qmd-setup.py](qmd-setup.py) executes native [collection add and update][qmd-cli]
against only the four mounted document directories. A native SDK
[PreToolUse hook][hooks] requires explicit `collections`, typed lexical
`searches` and `rerank:false` for QMD query calls, following the
[v2.8.3 MCP schema][qmd-schema]. Retrieval therefore needs no embedding/model
download. The model only receives useful excerpts, not the full catalog.

The 28 skills in [config/skills.lock.json](config/skills.lock.json) retain the
revisions and SKILL.md hashes from
[adoption/skills/manifest.json](../../../adoption/skills/manifest.json).
Installation verifies `$HOME/.agents/skills/<name>/SKILL.md` and creates prefix
symlinks to the existing directories. Containers mount each resolved directory
read-only at `/skills/<name>`; no skill content is copied or edited. The driver
uses native `load_skills_from_dir` and `AgentContext.skills`, as in the
[loading-skills example][skills-example]. SDK [skill loading:848–903][skills-loader]
and [InvokeSkillTool][invoke-skill] preserve progressive disclosure and supporting
resources. All pinned names must be discovered or startup fails. Public skill
auto-fetch, unrelated home/project skill discovery and built-in memory are off;
the configured ai-memory read tools remain available. This keeps source pins
and context scope explicit.

## Coordinator execution and lifecycle

Fill [config/host.example.json](config/host.example.json) into a private file
outside every checkout, owned by the current user with mode 0600. It contains
paths and local service addresses, **no secrets**. `mcp_readonly_mounts` must
include each existing executable/dependency directory needed by the template
commands, at its original absolute path so wrappers, symlinks and shebangs work.
Supply a container-compatible `HOST_PATH`; do not mount a whole home directory,
authentication directory, Docker socket or unrelated checkout. Scope each QMD
mount to the named document directory. The recipe starts no production service.

After review, on the coordinator's host:

```sh
export OPENHANDS_HOST_FILE=/absolute/private/openhands-host.json
bash blueprints/runtime-workers/openhands/install.sh
# Optional model-currency override; otherwise the JSON default is used.
OPENHANDS_MODEL=cx/gpt-6-astra-max bash blueprints/runtime-workers/openhands/run-e2e.sh
```

Installation and runs use container UID 0 **inside rootless Docker**, which maps
owned bind-mount writes to the calling host user. They drop all capabilities,
set no-new-privileges, use a read-only image filesystem and temporary private
`/root`/`/tmp` mounts. The worker gets only its writable fixture, private
conversation output and MCP state; recipes, venv, skills and document sources
are read-only. The Docker socket is never mounted. Agent containers have 4 CPU,
8 GiB and 384 PID limits. SDK and model execution cannot fall back to the host.

Every E2E gets a new `runs/attempt-*` directory; failed attempts remain. Normal
exit, timeout, SIGINT and SIGTERM attempt removal of the exact named container,
then record independent absence/removal status. Cleanup errors preserve the
primary exit code and fail the evidence-complete gate. All owned containers
carry `native-agent-stack.runtime-worker=openhands`; after an uncatchable host
crash, inspect that label and remove only the specific abandoned attempt.
Hard-kill/reboot recovery has not been qualified. Resume means a new attempt
from the frozen fixture; no interrupted trial is silently relabelled successful.
Rollback removes only the owned prefix/state when no labelled container uses
them. Shared rootless Docker, gateway, MCP installations and native sign-ins are
not modified or uninstalled.

## Frozen task, checker and receipts

[e2e/fixture-repo](e2e/fixture-repo/) contains one intentionally failing unittest,
a README spec and `range_utils.py`. [frozen.json](e2e/frozen.json) fixes all initial
file hashes, the one-test count, test command and sole allowed changed file.
The initial contract test was written and run before this recipe existed:
**exit 1, six tests, two failures and four missing-file errors**; the sanitized
returned output is [evidence/fail-first.txt](evidence/fail-first.txt).

`run-e2e.sh` first verifies the failing baseline inside the pinned image. The
worker must invoke `tdd`, run the unchanged failing test before editing, repair
the implementation and rerun the test. The callback retains native ActionEvent
and ObservationEvent fields with fixture byte inventories. [check.py](e2e/check.py)
runs in a separate container with **network disabled** and read-only inputs. It
requires a genuine failing terminal observation while the fixture was unchanged,
an allowed nonempty diff, unchanged test/README bytes, and a fresh passing run of
exactly one test with no skipped/expected-failure cases. Empty, incomplete,
extra-file, symlink, edited-test and wrong-answer results fail. This is an oracle
for a cooperative coding task, not a security proof against a worker deliberately
tampering with its own process or Python's test machinery.
The local checker follows CPython 3.13.15's [unittest runner][unittest-runner]
and [test-result exit handling][unittest-main]; it additionally enforces the
frozen file and test-count contract.

[receipt.py](receipt.py) reads the live
`$HOME/.local/share/omniroute/storage.sqlite` with SQLite URI `mode=ro` and
`query_only`, following the [official read-only URI example][sqlite-readonly].
Its only SELECT accesses `call_logs` columns `timestamp`, `path`,
`status`, `model`, `reasoning_effort_requested`, `reasoning_effort_upstream`,
`tokens_in`, `tokens_cache_read`, `tokens_reasoning`, limited to the run window.
There is no other table/column read, no schema introspection, and no prompt or
request identifier export. Missing/unknown counters remain null.

Rows are **window evidence**, potentially including concurrent callers; the
allowed columns cannot establish exclusive session attribution. The receipt
does not sum them into a worker cost. It records observed package versions,
sanitized gateway rows, actual native MCP observations/errors, successful skill
observations, checker results and container cleanup. Configured tools/skills
are not counted as used. Request/session/tool-call IDs, host paths, email
addresses, raw output and conversations stay out of the receipt.

The command exits zero only when the task passes and the evidence includes
observed matching model/Responses/max gateway rows, native SDK versions and
events, successful `tdd` use and confirmed container cleanup. A changed gateway
log schema or unavailable log database leaves evidence incomplete rather than
pretending zero usage. Full native persistence, command output and failures stay
in the private attempt directory; only its `receipt.json` is designed for public
review.

## Evidence and remaining host checks

| Evidence class | What exists here |
| --- | --- |
| Upstream source/release review | Exact SDK/app pins, executable/install formats, configuration keys, image topology, native MCP/skill/context behavior. [research.md](research.md) records decisions, limitations and corrected assumptions. |
| Artifact verification | Source/lock/wheel/GHCR response hashes; matching wheel/source Python files; exported requirement hashes. No container or package installation. |
| Local structural and synthetic checks | [tests/test_runtime_worker_openhands.py](../../../tests/test_runtime_worker_openhands.py) validates config, model override, headers, tool limits, QMD guard, fixture oracle, restricted SQLite query and failure preservation. [Verification record](evidence/verification.md) retains commands and returned results. Positive controls use synthetic events, not a model transcript. |
| Upstream test execution | **Not run.** Native CI uses `CI=true uv run python -m pytest -vvs` ([tests.yml:117][upstream-tests]); relevant unchanged suites are model features, the summarizing condenser, local conversation MCP and InvokeSkillTool. The production recipe does not install upstream test/dev dependencies. |
| Host/provider acceptance | **Not run.** No installation, image execution, gateway request, live database read, native MCP launch or model-produced fixture repair happened in this build. |

Host acceptance must establish wheel/sdist installation and import compatibility,
all mounted MCP executables/dependencies and language servers, all 28 skill
loads, tool enumeration/limits, stable affinity and fresh idempotency headers,
Responses/tool streaming, requested/upstream effort, actual test-first repair,
gateway schema compatibility and cleanup. The SDK's aggregate MCP startup limit
is 30 seconds ([local_conversation.py:123,1356–1379][local-mcp]); a server's
`timeout=120` is **not** a promise of a 120-second aggregate startup allowance.
Cold startup may need a separately reviewed upstream-supported provider adapter.
No native savings, cross-host portability, uncatchable-crash recovery or complete
upstream suite acceptance is claimed.

The OpenHands app, now Agent Canvas, is pinned for comparison at v1.24.0,
`7dc6805406ea3c76cb4a3ce407c3c72d481b0ac6`. Its [README ownership table, lines
139–150][canvas], assigns the frontend/backend selection/local stack orchestration
to Canvas and the agent/runtime APIs to this SDK. From those boundaries, Canvas
adds no required capability to this bounded coding worker. It is **not installed**.

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
