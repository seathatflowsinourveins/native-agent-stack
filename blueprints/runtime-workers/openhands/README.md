# OpenHands coding runtime worker

Round 3 provides a source-backed **native agent-server REST dispatch** for a
frozen SWE-bench task with two explicit gateway arms. SDK/server **1.49.6** owns
the agent loop. **SWE-bench 4.1.0** alone supplies the task verdict through the
pinned OpenHands/benchmarks converter and official Docker harness. This repair
ran offline contract tests only. No installation, container, model, gateway
request or official grading run was performed.

**Host acceptance is still open.** A verified firewall is required before model
execution. SDK trace, skill and version files remain worker-reported because the
terminal shares the server's UID. They cannot establish independent acceptance;
`evidence_complete` deliberately stays false until an independent observer is
qualified. A resolved official task therefore currently exits 2, not 0. This is
an explicit acceptance gap, not a failed model task.

[research.md](research.md) records primary-source checks and corrections.
[round3-verification.md](evidence/round3-verification.md) records every applicable
finding and the exact offline commands, outputs and exit codes. Earlier rounds
remain historical evidence; their standalone/no-listener descriptions are
superseded by this round.

## Sources and installation

| Component | Pin | Purpose |
| --- | --- | --- |
| OpenHands/software-agent-sdk | `fcc102a697874d54a357e36004e02c95040dbdc0`, v1.49.6 | Native SDK request types and agent-server |
| Agent-server image | `ghcr.io/openhands/agent-server@sha256:02ef66fdf0b22a40b0b55c5cca8d1790cfd260c5069f7c0b99edc1b505d5ab37` | Linux amd64 binary server and Python runtime |
| OpenHands/benchmarks | `405bae7140d7e961a75f4910a0b2e7069731db96` | Official conversion and grading commands |
| Benchmark SDK submodule | `43376f1868ffd702746080714a59c16d3f69ec12` | Unchanged separate grader dependency |
| SWE-bench | v4.1.0 | Official tests and `resolved_ids` |
| uv for host grader installation | 0.12.17 | Existing adopted executable; no automatic installation |

The native server uses the image's **own ENTRYPOINT**. The published binary target
is `openhands-agent-server/openhands/agent_server/docker/Dockerfile:580-590`.
The source target at lines 570-576 has a
different ENTRYPOINT. Do not assume the image contains the source-target venv.
Request generation uses the separately installed SDK/tools wheels in the same
image, with network disabled. [pins.json](pins.json) preserves the image, wheel
and runtime lock hashes. No framework version changed in round 3. The runtime
lock is a linux/amd64 security relock of the upstream export with four
dependency upgrades, reproduced from the unchanged upstream workspace
([research.md](research.md#runtime-lock-security-relock-2026-09-27)).

[install.sh](install.sh) installs the worker through the existing hash-required
wheel/runtime locks and preinstalled hashed build tools. The install container
can write only the worker venv and owned cache; the recipe snapshot is mounted
read-only with no writable parent alias. The installer uses container root for
these owned writes; model processes use upstream UID/GID 10001.

[install-grader.sh](install-grader.sh) retains the pinned host checkout/submodule
and uses the upstream Makefile's `uv sync --dev` operation with supported
`--locked --no-build-isolation --inexact` flags. It first installs hashed build
requirements, verifies the unchanged upstream `uv.lock` hash, checks uv 0.12.17,
sets `UV_PYTHON_DOWNLOADS=never`, explicitly selects the seeded venv interpreter
with `--python`, and checks the final SWE-bench version. The upstream
`.python-version:1` selects 3.12; the explicit interpreter keeps the recipe's
3.13 environment and its hashed build tools together. The
Makefile's unrestricted sync and development-hook installation are not invoked.
Sources: OpenHands/benchmarks@405bae7 `Makefile:33-42`, `pyproject.toml:97-99`;
SDK@43376f1 package build-system sections listed in pins.json; installed
`uv 0.12.17 sync --help`. Host build execution remains a disclosed residual;
containerizing this host-side grader without changing its interpreter/Docker
transport has not been qualified.

Prefix: `$HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6`.
Private state: `$HOME/.local/state/native-agent-stack/runtime-workers/openhands`.
Failed attempts are retained. The coordinator runs installation and acceptance.

## Arms

`OPENHANDS_ARM=control|engines-on` defaults to `control`. `--arm` overrides it.
`OPENHANDS_MODEL` and `OPENHANDS_BASE_URL` are optional explicit overrides that
must match the selected arm. The control arm retains the existing `cx/gpt-6-*`
variant support; the engines-on arm admits only the exact one-slash route below.
LiteLLM prepends `openai/` for its provider selection.

| Arm | Container base URL | Requested model | Compression header |
| --- | --- | --- | --- |
| control | `http://10.0.2.2:20128/v1` | `cx/gpt-6-astra-max` | absent |
| engines-on | `http://10.0.2.2:20129/v1` | `sharedgw/gpt-6-astra-max` | `x-omniroute-compression: allow-lossy` |

Both arms use Responses, `reasoning_effort=max`, native function tools, omitted
temperature, a 40-iteration limit and a 1,200-second conversation deadline.
Configured effort other than max, a cross-arm URL/model pairing, Claude routes,
two-slash gateway slugs and JSON response-format modes are refused.

The exact switches are:

```sh
export OPENHANDS_ARM=control
export OPENHANDS_MODEL=cx/gpt-6-astra-max
export OPENHANDS_BASE_URL=http://10.0.2.2:20128/v1
```

```sh
export OPENHANDS_ARM=engines-on
export OPENHANDS_MODEL=sharedgw/gpt-6-astra-max
export OPENHANDS_BASE_URL=http://10.0.2.2:20129/v1
```

No separate compression toggle is needed. The arm adds/removes the header.
The receipt stores the arm, base URL, requested/routed model, expected path and
**header names only**. A stable `x-omniroute-session` binds the conversation and
condenser. `server_transport.py` loads through the native `--import-modules`
option and supplies a fresh Idempotency-Key per logical `generate/agenerate`
call, retaining upstream retries and exact native LLM types. It also captures
returned correlation IDs privately where LiteLLM exposes response headers.
Sources: SDK@fcc102a `llm/llm.py:442-446,1130-1138,1588-1642`,
`llm/options/common.py:26-46`, `agent/base.py:739-775`,
`agent_server/__main__.py:74-135,240-273`; LiteLLM@v1.93.0
`litellm/llms/openai/responses/transformation.py:262-272`.

## Workflow dispatch

The coordinator first installs the recipe, supplies the frozen task and image
pin, completes the network gate described below, and prepares **one arm at a
time**. Preparation clones the task at its SWE-bench base-commit branch,
installs the shared project skills, builds the scoped lexical QMD index,
serializes the native request and starts the authenticated native server.
Preparation can be long and belongs in a background Bash task. The skills
manifest/installer PR must be available; there is no global-skill fallback.

Set these private inputs outside all worktrees:

- `OPENHANDS_HOST_FILE`: filled mode-0600 [host template](config/host.example.json).
- `OPENHANDS_STACK_ROOT`: stack checkout with the shared skill installer/manifest.
- `OPENHANDS_TASK_FILE`, `OPENHANDS_TASK_SHA256`: frozen original SWE-bench row.
- `OPENHANDS_GRADER_IMAGE_FILE`, `OPENHANDS_GRADER_IMAGE_SHA256`: frozen image pin.
- `OPENHANDS_SERVER_ENV`: mode-0600 file containing only this attempt's
  `OH_SESSION_API_KEYS_0` setting. No shared service/provider secrets.
- `OPENHANDS_HEADERS`: mode-0600 file containing the corresponding
  `X-Session-API-Key` header. Commands use curl's `-H @file`; no inline key.

```sh
RECIPE="$PWD/blueprints/runtime-workers/openhands"
export OPENHANDS_RUN_ID=rw-openhands-trial-001
rtk env PYTHONDONTWRITEBYTECODE=1 python3 "$RECIPE/host.py" prepare \
  --prefix "$HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6" \
  --state "$HOME/.local/state/native-agent-stack/runtime-workers/openhands" \
  --run-id "$OPENHANDS_RUN_ID" --arm "$OPENHANDS_ARM"
```

The workflow child runs exactly these three Bash commands after preparation:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 python3 "$RECIPE/dispatch.py" start --run-id "$OPENHANDS_RUN_ID" --arm "$OPENHANDS_ARM"
rtk env PYTHONDONTWRITEBYTECODE=1 python3 "$RECIPE/dispatch.py" wait --run-id "$OPENHANDS_RUN_ID" --arm "$OPENHANDS_ARM"
rtk env PYTHONDONTWRITEBYTECODE=1 python3 "$RECIPE/dispatch.py" result --run-id "$OPENHANDS_RUN_ID" --arm "$OPENHANDS_ARM"
```

Run `wait` and `result` through the child's background Bash facility; the grader
may take longer than a foreground tool timeout. Observe native completion or
read `status.json`. Each command prints one JSON object including `run_id`,
`arm`, `receipt`, `failure_stage`, `task_passed`, and `evidence_complete`.
The deterministic host paths are:

```text
$HOME/.local/state/native-agent-stack/runtime-workers/openhands/runs/<run-id>/<arm>/status.json
$HOME/.local/state/native-agent-stack/runtime-workers/openhands/runs/<run-id>/<arm>/receipt.json
```

The adapter uses curl to call these exact upstream routes on
`http://127.0.0.1:3730`: POST `/api/conversations`, GET
`/api/conversations/<uuid>`, then GET
`/api/conversations/<uuid>/agent_final_response`. Start is asynchronous. The
native SDK constructs `StartConversationRequest` and calls
`model_dump(exclude_defaults=True, mode="json", context={"expose_secrets": True})`;
only the fixed keyless gateway placeholder is exposed. It includes workspace,
`initial_message.run=true`, native agent/condenser/MCP/hook configuration,
`max_iterations=40`, and lowercase source/dispatch/arm tags. Preparation checks
`/health`, `/docs`, and the request fields in live `/openapi.json`.
Sources: SDK@fcc102a `conversation_router.py:72-86,163-228,257-287`,
`sdk/conversation/request.py:64-72,105-147,212-228,317-347`,
`sdk/utils/pydantic_secrets.py:24-37,48-68`.

Polling treats only finished/error/stuck as terminal; idle is not completion.
At the deadline it calls the native interrupt route and removes the exact owned
server. Result captures the native final response privately, confirms container
removal, then exports the candidate patch and invokes official grading.
A native final message alone is never a task verdict. Sources: SDK@fcc102a
`conversation_router.py:304-321`; SWE-bench@v4.1.0 `reporting.py:127-157`.

| Final exit code | Meaning |
| --- | --- |
| 0 | Official task resolved and all required evidence complete |
| 1 | Official unresolved or empty-patch verdict |
| 2 | Incomplete evidence, including a resolved task with untrusted trace evidence |
| 3 | Setup/infrastructure failure, deadline, grading error/incomplete bucket, or transport failure |

Preparation/start/wait exit 0 means that operation succeeded, not that the task
passed. Duplicate starts do not resubmit a native POST. Retrying a collected
result returns its retained receipt without another API or grader call. A host reservation
serializes dispatches from this recipe. It does not exclude unrelated gateway
clients. Interrupted attempts retain their files; cleanup removes named owned
containers only, never uses prune, and records whether removal was confirmed.
The coordinator must reclaim a stale reservation only after confirming its
recorded container is gone. Port 3730 must be available; another recipe using
that port must be stopped before this one is prepared.

Invocation counts use existing pipelines: on Claude, child usage and OTel Bash
events whose command contains `dispatch.py`, the `start` subcommand and
`--run-id` (allow shell quoting and whitespace); on OpenHands, JSON access logs for
POST `/api/conversations`, plus native count/search endpoints. Run IDs also
travel in native tags. Poll/result calls are separate from invocation counts.
Native `server.log` is captured on result/cleanup and stays private. Sources:
SDK@fcc102a `conversation_router.py:105-162`, `logging_config.py:55-106`;
repository `adoption/templates/claude.settings.template.json:15` and
`observability/collector/collector.yaml:74`. No collector change is required.

## Usage accounting

The only usage authority is the selected arm's **entry** gateway, opened with
SQLite `?mode=ro` and `PRAGMA query_only=ON`:

| Arm | Entry database | Expected entry row model/path |
| --- | --- | --- |
| control | `$HOME/.local/share/omniroute/storage.sqlite` | `gpt-6-astra-max`, `/v1/responses` |
| engines-on | `$HOME/.local/share/omniroute-fw/storage.sqlite` | `gpt-6-astra-max`, `/v1/responses` |

For a retained control variant the routed model is the suffix after `cx/`.
The coordinator must verify both database paths and the actual entry row model
and path on the host. A missing/mismatched database produces unknown usage.
Never add forwarded 20128 rows to engines-on 20129 rows.

Reads are restricted to timestamp, path, status, model, tokens_in,
tokens_cache_read, tokens_reasoning and correlation_id, plus the two explicitly
required effort columns. IDs are discarded before returning rows. The private
native capture may lack headers on streaming paths and shares the model's trust
boundary, so receipts conservatively use **time window + model + path** at the
entry gateway. They state the concurrent-caller limitation. Per-arm totals sum
each matched row once, including failed calls; if any requested counter is
missing, totals remain null. Cache-read tokens are an input subset, not an
additional cost. No output-token or complete-provider-cost total is invented.

Rows with positive returned reasoning tokens expose their logged effort; both
requested and upstream effort must be max for `effort_verified`. Zero and
unknown reasoning counts are reported separately. Null effort columns are not
evidence that effort was omitted: OmniRoute@a58000c
`src/lib/usage/callLogs.ts:646-653` fills them only for encrypted reasoning.
Correlation response headers are defined in the same pin's
`src/sse/handlers/chatHelpers.ts:1172-1184`.

For engines-on, the host records before/after
`GET /api/analytics/compression?since=all` snapshots and reports only their
`totalRequests` and `totalTokensSaved` deltas, separately from call-log usage.
Optional `OPENHANDS_COMPRESSION_HEADERS` points to a mode-0600 management-header
file if that endpoint requires authentication. Missing counters, auth failure
or reset keep the delta null. These global analytics can include other callers;
they do not establish measured semantic quality or provider-token savings.
Sources: OmniRoute@a58000c `src/app/api/analytics/compression/route.ts:13-24`,
`src/lib/db/compressionAnalytics.ts:52-55`.

## Security posture

All model-controlled shell, file and stdio MCP execution stays in the rootless
container, under non-root UID/GID 10001, with capabilities dropped,
no-new-privileges, read-only root, and an attempt-local temporary home. The model
has no Docker socket, host authentication directory, oracle dataset or grader
checkout. The task's Git metadata and installed skills are read-only mounts.
Host patch export disables system/global Git config, external diff and textconv
so candidate attributes cannot select host-global executable filters.
Sources: SDK@fcc102a `agent_server/docker/Dockerfile:7-9,301-305,343`;
Git@v2.43.0 `Documentation/git.txt:708-724`, `diff-options.txt:830-840`.

MCP allowlists are not network security. ai-memory HTTP and socraticode are
**disabled** because their host services would bypass the framework's tool
filter. context-mode, Serena, jCodeMunch and lexical QMD remain container-local;
headroom remains disabled. The host mount allowlist accepts only selected
adoption tool roots and the four document roots, resolves symlinks before
checking, and rejects authentication stores and every ancestor of the host home.
No tool can execute directly on the host through this registration.

Model launches require `rw-openhands-egress-control` or
`rw-openhands-egress-engines-on`. The supported policy mechanism is Docker's
**DOCKER-USER iptables chain**, with explicit destination/port rules before
Docker accepts forwarding. Host INPUT must also deny traffic from the worker
bridge; IPv6 is disabled. Only the selected gateway endpoint is allowed. Plain
`--internal` alone is insufficient because an internal bridge may still reach
host listeners. Source: docker/docs@4e9a5751518ed8223a8dcde53693badddd72604f
`content/manuals/engine/network/firewall-iptables.md:22-24,48-95` and
`port-publishing.md:186-192`.

The coordinator must provision and **independently probe** that policy in the
rootless daemon's network namespace. The repair does not change daemon-wide
firewalls. `model_network` fails closed without a fresh, host-owned mode-0600
policy receipt whose network ID matches Docker inspect and whose allowed TCP
endpoint is exactly the selected arm. The host template has per-arm receipt
paths. The receipt schema is:

```json
{
  "mechanism": "docker-user-iptables",
  "network_id": "<actual Docker network ID>",
  "verified_at": "<UTC timestamp within the preceding 15 minutes>",
  "allowed_tcp": ["10.0.2.2:20128"],
  "default_deny": true,
  "host_input_denied": true,
  "ipv6_disabled": true,
  "gateway_reachable": true,
  "other_host_ports_denied": true
}
```

For engines-on only the endpoint changes to port 20129. This schema is an
operator evidence gate, not a firewall implementation or proof by itself. Keep
the actual rule dump and probe outputs privately; reject access to the other
arm, ai-memory, Qdrant, embedder and other worker listeners before any model run.
Docker was not found on this repair sandbox's PATH, so rootless rule placement,
packet behavior and post-restart policy persistence remain unverified. This is
a host setup gate, not an instruction to accept loopback exposure. Official
grader containers retain upstream options; the coordinator must separately
qualify their host-service isolation without misrepresenting altered test
conditions as an unchanged environment.

Every authoritative status/window/verdict file is outside model mounts. Files
read from worker output use bounded regular-file reads with O_NOFOLLOW on every
path component, and are labelled worker-reported. The remaining shared-UID
trace limitation is explicit at the top of this document; counterfeit events
cannot cause `evidence_complete=true`. This round does not invent an isolation
mechanism unsupported by the pin.

## Official grading and remaining host gates

The task comes from a frozen original SWE-bench row with an externally supplied
SHA256. Clone branch selection uses the pinned `REPO_BASE_COMMIT_BRANCH` mapping
(SWE-bench@v4.1.0 `test_spec/python.py:271-277`). Oracle patches and private tests
are never mounted in the worker. The retained bare checkout and 40 iterations
remain inference adaptations; this is not unchanged `swebench-infer`.

The image bundle contains `instance_id`, the exact upstream instance `tag`, an
immutable `ref` (`docker.io/swebench/<instance-image>@sha256:<digest>`), and its
registry `source`. The coordinator freezes its SHA256 and pre-pulls the digest.
Before grading, host code verifies RepoDigests/platform/Id, retags it locally to
the upstream name and passes the checked image ID to the adapter. Creation
rechecks that identity; mutable pulls and builds are refused. Sources:
SWE-bench@v4.1.0 `test_spec/test_spec.py:106-120`, `docker_build.py:516-524`;
docker/docker-py@7.1.0 `docker/models/resource.py:28-33`.

`e2e/docker_grader.py` adapts names and ownership labels only. It adds **no memory,
CPU, PID, capability or user changes** to the official grading container. Gold
patch and known-negative official controls must run under the frozen image
before a worker verdict is accepted. `e2e/check.py` relays the actual report; an
error/incomplete bucket is infrastructure, not a model-negative tally.

Host work remaining: native installation and import acceptance; shared skills
PR; frozen task/image selection; rootless firewall proof and port availability;
native server health/auth/OpenAPI/preload startup; actual tool names/skills/MCP
use; response-header capture for streaming and condenser calls; entry-database
matching and max effort; official positive/negative grading controls; independent
trace observation; cancellation/cleanup recovery. No A/B or savings result is
claimed until these observations exist.

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
