# OpenHands coding runtime worker

Round 3 provides a source-backed **native agent-server REST dispatch** for a
frozen SWE-bench task with two explicit gateway arms. SDK/server **1.49.6** owns
the agent loop. **SWE-bench 4.1.0** alone supplies the task verdict through the
pinned OpenHands/benchmarks converter and official Docker harness. This repair
ran offline contract tests only. No installation, container, model, gateway
request or official grading run was performed. The 2026-09-28 phase-1 repair
added offline fixes and pulled the pinned image only to scan its digest. It
started no container and made no model or gateway request
([research.md](research.md#takeover-phase-1-corrections-2026-09-28)). The
2026-09-28 phase-2 build replaced the DOCKER-USER firewall contract with the
O1 topology: a per-attempt internal network in gateway mode `isolated` and a
pinned nginx allowlist proxy ([Security posture](#security-posture); the
[decision record](../../../docs/decisions/2026-09-28-openhands-resolver-isolation.md)).
It ran offline tests with Docker mocked and pulled the nginx image by digest.
It created no container or network and made no model or gateway request
([research.md](research.md#takeover-phase-2-corrections-2026-09-28)).

**Host acceptance is still open.** Before any model runs, a P0-P2 isolation
probe must pass on the live topology; it has not run yet
([Isolation probe](#isolation-probe-p0-p2-and-the-dispatch-gate)). The model's terminal runs under the server's UID, so it can write
both `/run-output` and the server's persisted event store. Receipts therefore
record trace, skill, MCP and version fields as `not_collected`, with the reason,
instead of reading them from either place (SDK@fcc102a
`openhands-tools/openhands/tools/terminal/terminal/subprocess_terminal.py:157-170`,
`openhands-agent-server/openhands/agent_server/event_service.py:420-431`,
`openhands-sdk/openhands/sdk/conversation/event_store.py:144-169,320-362`).
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
and runtime lock hashes. No framework version changed in round 3.

**The runtime-lock relock covers only the recipe venv.** requirements.lock is a
linux/amd64 security relock of the upstream export with five dependency
upgrades, reproduced from the unchanged upstream workspace
([research.md](research.md#runtime-lock-security-relock-2026-09-27); PyJWT 2.14.0 is the
fifth, added on 2026-09-30: [research.md](research.md#runtime-lock-pyjwt-relock-2026-09-30)). It builds
the venv under the install prefix. That venv serializes the request, runs the
`mcp_guard.py` hook and comes first on the server container's PATH. The server
process itself is the image's PyInstaller binary
`/usr/local/bin/openhands-agent-server`. Upstream builds it from its unchanged
uv.lock with `uv sync --frozen` (SDK@fcc102a
`openhands-agent-server/openhands/agent_server/docker/Dockerfile:129,139,146-158,583-590`).
That lock, whose SHA256 is pins.json `uv_lock`, still pins anyio 4.11.0, click 8.1.8,
pypdf 6.14.2, soupsieve 2.8.4 and PyJWT 2.13.0, the five versions the relock replaces.

[agent-server-image-grype-20260928.json](evidence/agent-server-image-grype-20260928.json)
records a grype 0.119.0 scan of the pinned linux/amd64 digest, with a database
built 2026-09-28T06:42:30Z. It found 1,464 unique matches in 164 package
versions: Critical 32, High 168, Medium 208, Low 57, Negligible 780 and
Unknown 219. The flagged packages are Debian packages, openvscode-server npm
modules and Node, Docker/containerd Go binaries and the base Python interpreter.
The cataloger does not unpack the PyInstaller archive, so the scan neither
confirms nor excludes the lock versions inside the binary: the four the 2026-09-27 relock replaced, and PyJWT 2.13.0,
which the 2026-09-30 relock replaced in the venv only. The receipt
lists grype's advisories for those exact versions as lock evidence. On this
host's containerd image store, `docker image inspect` reports the index digest
as the image ID, so the receipt verifies the platform manifest and config
digests instead.

`install()` checks the pulled image on either Docker image store before any
container starts. It runs two inspects, one plain and one with
`--platform linux/amd64`. The primary check is that both list the exact pinned
reference in `.RepoDigests`; otherwise it raises `image_repo_digest_mismatch`.
The plain `.Id` must then be the index digest (containerd store) or the config
digest (classic store); any other value is refused with
`image_configuration_hash_mismatch`. A wrong platform manifest raises
`image_platform_manifest_mismatch`. `installation.json` records the store.

| Check | containerd image store | Classic store |
| --- | --- | --- |
| Plain `.Id` | index `sha256:02ef66fd...` | config `sha256:39426d8c...` |
| Platform `.Id` | manifest `sha256:ec7ed86f...` | config `sha256:39426d8c...` |
| Platform `.Descriptor.digest` | manifest `sha256:ec7ed86f...` | absent |
| Config digest | not reported; bound by the content-addressed manifest, as in the scan receipt | checked as `.Id` |
| Platform manifest | checked | not retained; the pinned index names it |

Sources: moby docker-v29.8.1 (464cd50c, the engine commit this host reports)
`daemon/containerd/image_inspect.go:28,71-73,95,97` for the containerd store.
For the classic store: `daemon/images/image_inspect.go:59`,
`daemon/images/image.go:160-197`, `daemon/internal/image/store.go:152,160`
and `daemon/internal/image/fs.go:120`. A classic pull by index digest verifies
the index and the selected platform manifest, then records the pinned index
reference in RepoDigests
(`daemon/internal/distribution/pull_v2.go:431-434,705-747,845-867`). Inspect
with `--platform` needs Engine API v1.49 or later
(`api/docs/CHANGELOG.md:175-180`). The moby client at the same tag refuses the
option below that version (`client/image_inspect.go:33-36`), so an older daemon
fails the install before any container starts. The Engine API reference still
describes `Id` as the config digest (`api/swagger.yaml:1826-1850`). The earlier
config-only check followed that description, so it would have refused the
pinned pull on this host. Docker's containerd image-store page says that store
is the default for fresh Engine 29 installations (docker/docs@3c117d8e
`content/manuals/engine/storage/containerd.md:11-14`). It does not describe
image IDs, so the moby source is the citation here.

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

`OPENHANDS_ARM=control|engines-on` defaults to `control`, and `--arm` overrides
it. Control stays the default until the #431 A/B selects the engines arm.
`OPENHANDS_MODEL`, `OPENHANDS_BASE_URL` and `OPENHANDS_COMPRESSION` are
optional explicit overrides that must match the selected arm. The control arm
retains the existing `cx/gpt-6-*` variant support; the engines-on arm admits
only the exact one-slash route below. LiteLLM prepends `openai/` for its
provider selection.

Both arms give the agent the same base URL, `http://gw:8081/v1`: the attempt's
proxy on the internal run network ([Security posture](#security-posture)).
Each attempt's proxy forwards to exactly one gateway, rendered from the arm:

| Arm | Agent base URL | Proxy upstream | Requested model | Compression header |
| --- | --- | --- | --- | --- |
| control | `http://gw:8081/v1` | `http://10.0.2.2:20128/v1` | `cx/gpt-6-astra-max` | absent |
| engines-on | `http://gw:8081/v1` | `http://10.0.2.2:20129/v1` | `sharedgw/gpt-6-astra-max` | `x-omniroute-compression: <combo>`, default `allow-lossy` |

engines-on accepts one of the seven combos recorded for the 20129 gateway
(`recipe.COMPRESSION_COMBOS`): `allow-lossy`, `fw-ccr`, `fw-codex-responses`,
`fw-headroom`, `fw-lite`, `fw-rtk` and `fw-session-dedup`. An unrecorded combo
is refused, and so is any compression value on control. The proxy, not the SDK,
sends the header: its allowlist replaces whatever the agent sends for
`x-omniroute-compression`, `X-Correlation-Id` and `x-omniroute-session` with the
attempt's fixed values. The agent therefore cannot switch arm or combo, or forge
the correlation and session values the gateway receives. On the recipe's
`/v1/responses` path the pinned gateways log their own correlation ID instead,
so usage is not joined on the run id ([Usage accounting](#usage-accounting)).
The LLM key stays the placeholder `local-loopback`, and `OMNIROUTE_API_KEY` is
never sent.

Both arms use Responses, `reasoning_effort=max`, native function tools, omitted
temperature, a 40-iteration limit and a 1,200-second conversation deadline.
Configured effort other than max, a cross-arm URL/model pairing, Claude routes,
two-slash gateway slugs and JSON response-format modes are refused.

The exact switches are:

```sh
export OPENHANDS_ARM=control
export OPENHANDS_MODEL=cx/gpt-6-astra-max
export OPENHANDS_BASE_URL=http://gw:8081/v1
```

```sh
export OPENHANDS_ARM=engines-on
export OPENHANDS_MODEL=sharedgw/gpt-6-astra-max
export OPENHANDS_BASE_URL=http://gw:8081/v1
export OPENHANDS_COMPRESSION=allow-lossy   # optional; any recorded combo
```

The receipt stores the arm, base URL, proxy upstream, requested/routed model,
compression combo, expected path and **header names only**. A stable `x-omniroute-session` binds the conversation and
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
pin, and prepares **one arm at a time**. Preparation clones the task at its
SWE-bench base-commit branch, installs the shared project skills, builds the
scoped lexical QMD index and serializes the native request. It then builds the
attempt's O1 topology, starts the authenticated native server behind the proxy
and runs the P0-P2 isolation probe. Preparation can be long and belongs in a
background Bash task. The skills manifest/installer PR must be available;
there is no global-skill fallback.

Set these private inputs outside all worktrees:

- `OPENHANDS_HOST_FILE`: filled mode-0600 [host template](config/host.example.json),
  including the per-arm `gateway_providers` allowlists; `dispatch.py start`
  also reads it ([G5](#g5-gateway-provider-preflight)).
- `OPENHANDS_STACK_ROOT`: stack checkout with the shared skill installer/manifest.
- `OPENHANDS_TASK_FILE`, `OPENHANDS_TASK_SHA256`: frozen original SWE-bench row.
- `OPENHANDS_GRADER_IMAGE_FILE`, `OPENHANDS_GRADER_IMAGE_SHA256`: frozen image pin.

The coordinator does not supply the agent-server's session key; each attempt
generates its own (plan E2). After both attempt networks exist,
`host.generate_session_files` takes one value from Python's `secrets` module
and writes two files in
`$HOME/.local/state/native-agent-stack/runtime-workers/openhands/secrets/`
(mode 0700). Each file is created with `O_CREAT|O_EXCL|O_NOFOLLOW` at mode
0600, so an existing file or a planted symlink is refused:

- `<run-id>-<arm>.server.env`: the single line `OH_SESSION_API_KEYS_0=<value>`
  in Docker env-file syntax, passed to the server as `--env-file`;
- `<run-id>-<arm>.headers`: `X-Session-API-Key: <value>`, which curl reads
  with `-H @file`.

The driver never puts the value in argv and does not intentionally log or print
it. That is not a guarantee that no log holds it: the model can read the key
inside its container (the accepted design) and place it in any request it sends
through the proxy. The agent side's access log keeps whole request lines, and
so do request-bound error-log entries on both listeners (nginx
release-1.30.5 `src/http/ngx_http_request.c:4103-4107`). The host side's access
log keeps only time, method and status. Teardown retains the proxy log, and
deleting the key files does not remove such copies. The server is never read
with a full `docker inspect`, because its Config.Env holds the key; containers
are read only through fixed `--format` templates. `teardown_attempt` deletes both
files once the proxy and server are confirmed removed. While either removal is
unconfirmed the files stay, so the server they belong to can still be reached
and cleaned up. The server listens on every container interface only when a
key is set (SDK@fcc102a `openhands-agent-server/openhands/agent_server/__main__.py:282-285`,
`config.py:24`), and it checks the `X-Session-API-Key` header
(`dependencies.py:19`). Before the server starts, the host reads the env file
and compares only the variable name, using Docker's env-file rules
(docker/cli@v29.8.1 `pkg/kvfile/kvfile.go:92-124`); the value is never logged
or returned. The
inventory row is `openhands-session` in
[docs/secret-storage.md](../../../docs/secret-storage.md) and
[adoption/credential-inventory.json](../../../adoption/credential-inventory.json).

**Deviation from the plan (E2).** The plan kept the pointer variables
`OPENHANDS_SERVER_ENV` and `OPENHANDS_HEADERS`. They are retired. Both paths
derive from the validated run id and arm alone, so neither a caller's
environment nor `status.json` can redirect the key files, and a generated key
is never empty (the phase-1 empty-value residual no longer applies).

Container environment, and only these names: `HOME=/state/home`, `PATH`,
`PYTHONDONTWRITEBYTECODE`, `UV_PYTHON_DOWNLOADS`, `OPENHANDS_OWNED_CONTAINER`,
`OPENHANDS_RUN_ID`, `OPENHANDS_ARM`, `OPENHANDS_MODEL`, `OPENHANDS_BASE_URL`,
`OPENHANDS_COMPRESSION`, `OH_ENABLE_VSCODE`, `OH_CONVERSATIONS_PATH`,
`OH_WORKSPACE_PATH` and `OH_BASH_EVENTS_DIR`, plus `OH_SESSION_API_KEYS_0` from
the env file on the server only. Never `OMNIROUTE_API_KEY`, and never a `GH_*`
or `GITHUB_*` name. **Deviation from the plan:** its closed list has no
`OPENHANDS_COMPRESSION`. It is added so the request serializer and the
server's preload rebuild the same arm selection the host checked. Without it
an engines-on attempt with a non-default combo would render a different
selection in the container. The value is a recorded combo name or empty, never
a credential, and the proxy overwrites the header in any case.

```sh
RECIPE="$PWD/blueprints/runtime-workers/openhands"
export OPENHANDS_RUN_ID=rw-openhands-trial-001
rtk env PYTHONDONTWRITEBYTECODE=1 python3 "$RECIPE/host.py" prepare \
  --prefix "$HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6" \
  --state "$HOME/.local/state/native-agent-stack/runtime-workers/openhands" \
  --run-id "$OPENHANDS_RUN_ID" --arm "$OPENHANDS_ARM"
```

`--port` selects the proxy's published loopback port, the host's only way into
the attempt (`127.0.0.1:<port>` to the proxy's 8080, which forwards to the
server's 8000). It must be an integer in 3730..3799, the range PR #428's
crawl4ai recipe enforces (`host.py:44-45` at 3ad8ba2), and defaults to 3730 for
this SWE-bench worker. The resolver uses 3740 (`--port 3740`). Preparation
records the port in the host-owned `status.json`; `dispatch.py` has no port
flag, reads it from there and checks the range again before any request.

Preparation exits 0 only when the probe passed. `dispatch.py start` accepts the
probe receipt for 900 seconds. If more time passes, re-run the probe on the
same prepared attempt; it never generates a run id:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 python3 "$RECIPE/host.py" probe \
  --prefix "$HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6" \
  --state "$HOME/.local/state/native-agent-stack/runtime-workers/openhands" \
  --run-id "$OPENHANDS_RUN_ID" --arm "$OPENHANDS_ARM"
```

A prepared attempt that will not start a conversation now is removed with
`host.py teardown` and the same identity flags
([live probe sequence](#live-probe-sequence-coordinator-not-run-yet)).

No conversation starts until the coordinator has run P3 on the running gateway
build and recorded it, with G2 and G5, in the host-owned stage-gates file (plan
gate G7). `dispatch.py start` refuses without that file; see
[the gate](#isolation-probe-p0-p2-and-the-dispatch-gate). After that, the
workflow child runs exactly these three Bash commands after preparation:

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
`http://127.0.0.1:<port>`, the proxy's host-side listener (8080), which
forwards everything to `<run-id>-<arm>-server:8000` on the internal network:
POST `/api/conversations`, GET `/api/conversations/<uuid>`, then GET
`/api/conversations/<uuid>/agent_final_response`. After an `error` status it
also calls GET `/api/conversations/<uuid>/events/search` with
`kind=openhands.sdk.event.conversation_error.ConversationErrorEvent`,
`sort_order=TIMESTAMP_DESC` and `limit=1`. At the deadline it calls POST
`/api/conversations/<uuid>/interrupt`. Each route is paired with its one
method (plan E3): POST starts or interrupts a conversation, and GET only
reads. Any other method/path pair is refused before curl runs. `start` first
requires a fresh probe receipt bound to the live topology
([gate](#isolation-probe-p0-p2-and-the-dispatch-gate)); a refusal prints
`failure_stage: probe`, exits 3 and changes nothing. Start is asynchronous. The
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
At the deadline it calls the native interrupt route and tears the attempt down:
the proxy, the server and both attempt networks, each by exact name. Result
captures the native final response privately, confirms container removal, then
exports the candidate patch and invokes official grading.
A native final message alone is never a task verdict. Sources: SDK@fcc102a
`conversation_router.py:304-321`; SWE-bench@v4.1.0 `reporting.py:127-157`.

An agent-limit end still grades its partial patch. The SDK ends a detected loop
with status `stuck`. An exhausted iteration budget ends with status `error` and
a `ConversationErrorEvent` whose source is `environment` and code is
`MaxIterationsReached` (SDK@fcc102a `openhands-sdk/openhands/sdk/conversation/state.py:48-79`,
`conversation/impl/local_conversation.py:727-733,753-755,2021-2043,2339-2360`,
`event/conversation_error.py:11-42`). For `error`, result reads the newest error
event through the native search route while the server still runs
(`openhands-agent-server/openhands/agent_server/event_router.py:68-139`,
`event_service.py:456-460`, `models.py:95-99`). Only exactly that kind, source
and code counts as `max_iterations_reached`; any other error stays ungraded and
exits 3. The receipt records `agent_termination`, and an agent-limit end exits 1
even when its partial patch resolves the task.

`finish_result` keeps a termination label only if it refines the REST
`execution_status`. `finished` stays `finished`, `stuck` stays `stuck`, and
`error` may become `max_iterations_reached`. Any other pairing becomes an
ungraded `error`. Only REST `finished` can set `worker_exit_code` 0, so exit 0
never depends on the event store.

**Residual (F16).** The error-event page is not independent evidence. The
model's terminal runs as the server's user (SDK@fcc102a
`openhands-tools/openhands/tools/terminal/terminal/subprocess_terminal.py:157-170`).
The server serves events from files in the conversation store, reads them back
and rebuilds a stale index from disk
(`openhands-sdk/openhands/sdk/conversation/event_store.py:144-169,320-362`,
`openhands-agent-server/openhands/agent_server/event_service.py:420-431`). A
planted `MaxIterationsReached` event can therefore turn an ungraded native
error (exit 3) into a graded agent-limit end (exit 1). No planted event can
reach exit 0. Tests cover both the 3-to-1 move and planted success-looking
events. Treating every `error` as exit 3 would remove this move. It would also
label every honest iteration-limit run an infrastructure failure, a systematic
bias larger than this bounded forgery.

**Analysis rule.** Every A/B or acceptance tally counts exit 1 and exit 3 alike
as non-success, and a rerun policy may re-queue only exit 3. A forged 3-to-1
move therefore cannot improve an arm's success rate; at most it suppresses a
rerun.
A receipt with `upstream_resolved: true` that exited 1 is not a success.

| Final exit code | Meaning |
| --- | --- |
| 0 | Official task resolved and all required evidence complete |
| 1 | Official unresolved or empty-patch verdict, or an officially graded partial patch after `stuck` or `max_iterations_reached` |
| 2 | Incomplete evidence, including a resolved task whose trace evidence is `not_collected` |
| 3 | Setup/infrastructure failure, other native error, deadline, grading error/incomplete bucket, or transport failure |

Preparation/start/wait exit 0 means that operation succeeded, not that the task
passed. Duplicate starts do not resubmit a native POST. Retrying a collected
result returns its retained receipt without another API or grader call. A host reservation
serializes dispatches from this recipe. It does not exclude unrelated gateway
clients. Interrupted attempts retain their files; cleanup removes the named
owned containers and attempt networks only, never uses prune, and records
whether each removal was confirmed. The coordinator must reclaim a stale
reservation only after confirming its recorded containers and networks are
gone. The selected port must be available. PR #428's
crawl4ai recipe defaults to 3730, 3731, 3732 and 3734 (its README at 3ad8ba2);
stop it or choose another port in the range before preparing this recipe.

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
required effort columns. IDs are discarded before returning rows. Receipts use
**time window + model + path** at the entry gateway and state the
concurrent-caller limitation. Two sources could have narrowed that, and neither
can:
- The proxy's fixed `X-Correlation-Id` does not reach the row. At
  OmniRoute@045aa81f3 and @dd6e9607e, whose files here are identical,
  `/v1/responses` passes a fresh `randomUUID()` to `handleChat`
  (`src/app/api/v1/responses/route.ts:193,213`,
  `src/shared/utils/requestId.ts:100-102`, `src/sse/handlers/chat.ts:436`). That
  ID is what `call_logs.correlation_id` stores
  (`open-sse/handlers/chatCore/attemptLogging.ts:611`,
  `src/lib/usage/callLogs.ts:713,786,801`). Only `/v1/chat/completions` keeps
  a caller's ID (`src/app/api/v1/chat/completions/route.ts:292-322`). Matching
  the run id on this path would drop every row and report false zeros, so
  receipts do not (repair R5; a regression test pins this).
- The private native capture of returned IDs may lack headers on streaming
  paths and shares the model's trust boundary.

Per-arm totals sum
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
**disabled**. Their host services would bypass the framework's tool filter,
and under O1 they are unreachable by design: the internal run network has no
route to host services, only three `/v1` routes reach the gateway, and the
proxy's other listener, `gw:8080`, reaches only the agent's own server
([config/mcp-policy.json](config/mcp-policy.json)). The host template still
fixes `AI_MEMORY_URL` and `EMBED_URL` because the MCP template renders them.
Neither address is reachable from the internal network; P2 checks every host
listener. context-mode, Serena, jCodeMunch and lexical QMD remain
container-local; headroom remains disabled. The host mount allowlist accepts only selected
adoption tool roots and the four document roots, resolves symlinks before
checking, and rejects authentication stores and every ancestor of the host home.
No tool can execute directly on the host through this registration.

Every authoritative status/window/verdict file is outside model mounts.
Receipt creation reads nothing from the worker output or the server state
directory; fields that would need them are `not_collected`. The only file the
host reads back from worker output is the serialized request, copied with a
bounded regular-file read (O_NOFOLLOW on every path component) before any model
runs. The server-reported agent-limit classification can never produce a pass,
and nothing can cause `evidence_complete=true`. The network isolation below is
composed locally from documented Docker network options and nginx directives;
no upstream ships it. Until the live P0-P2 probe has run on this host, it is a
design with offline tests, not host evidence.

### O1 topology

The phase-2 plan (section 1, item E1) replaces the earlier DOCKER-USER
firewall contract with a topology built per attempt. Every resource is named
from `S=<run-id>-<arm>` and carries the owner label
`com.native-agent-stack.owner=gpt6-omniroute-framework-integration`. Below,
`D` is `docker --context rootless`:

```sh
D network create --internal --ipv6=false -o com.docker.network.bridge.gateway_mode_ipv4=isolated --label <owner> $S-int
D network create --ipv6=false --label <owner> $S-gw
D run --detach --name $S-server <hardening> --network=$S-int --env-file <state>/secrets/$S.server.env ...  # no --publish
D create --pull=never --name $S-proxy --platform linux/amd64 --label <owner> --network=$S-gw \
  --publish 127.0.0.1:<port>:8080 --read-only --tmpfs /tmp:rw,nosuid,nodev,mode=1777 --cap-drop=ALL \
  --security-opt=no-new-privileges --pids-limit 64 --memory 256m \
  --mount type=bind,src=<result>/proxy/nginx.conf,dst=/etc/nginx/nginx.conf,readonly \
  --entrypoint nginx <pins.json gateway_proxy ref> -g 'daemon off;'
D network connect --alias gw $S-int $S-proxy
D start $S-proxy
```

- **Server.** The agent-server joins `$S-int` only and publishes nothing. Its
  hardening is unchanged: UID/GID 10001, all capabilities dropped,
  no-new-privileges, a read-only root, a tmpfs home, and CPU, memory and PID
  limits. Its only standing peer is the proxy, which it reaches as `gw`; the
  P1/P2 probe container joins `$S-int` only while a probe runs (`prepare` or
  `host.py probe`).
- **Order.** The proxy is created after the server starts, and connected to
  `$S-int` before it starts, so nginx resolves `$S-server` when it loads.
  A created container joins its configured networks when it runs, and
  `network connect --alias` adds a network-scoped name (docs.docker.com
  `container run` and `network connect`, fetched 2026-09-28).
- **Read-back.** `create_topology` reads each network back through a fixed
  `--format` template. It requires the bridge driver, `Internal` true on
  `$S-int` and false on `$S-gw`, `EnableIPv6` false, the owner label, a 64-hex
  ID, and gateway mode `isolated` on `$S-int`.
- **Fail closed.** If `network create` rejects the isolated option, the
  attempt fails with `attempt_int_network_create_failed`. It never retries
  with plain `--internal`.
- **Why isolated.** docker/docs@4e9a5751518ed8223a8dcde53693badddd72604f
  `content/manuals/engine/network/port-publishing.md:186-192` states the
  problem and the remedy: "Mode `isolated` can only be used when the network is
  also created with CLI flag `--internal`, or equivalent. An address is
  normally assigned to the bridge device in an `internal` network. So,
  processes on the Docker host can access the network, and containers in the
  network can access host services listening on that bridge address (including
  services listening on "any" host address, `0.0.0.0` or `::`). No address is
  assigned to the bridge when the network is created with gateway mode
  `isolated`." The options are listed at `:121-131`. How rootless Docker
  29.8.1 applies the mode has only been source-reviewed; P2 is the evidence.
- **Teardown.** The proxy, the server, `$S-int` and `$S-gw` are removed by
  exact name, never by prune, with a confirmed-removal record for each.
  Container logs are kept first; the proxy's access log records the denied
  requests.

Host loopback stays reachable from containers on the reference host, and O1
relies on it: the proxy reaches the gateway through 10.0.2.2. The host's
rootless `docker.service` sets
`DOCKERD_ROOTLESS_ROOTLESSKIT_DISABLE_HOST_LOOPBACK=false`, and the running
rootlesskit has no `--disable-host-loopback` flag (read-only checks,
2026-09-28). The upstream default does disable it (moby/moby@a46e6fa7
`contrib/dockerd-rootless.sh:23-24,170-173`, identical to the installed 29.8.1
script), so a new host must set the variable to `false` and repeat both
checks. Per the phase-2 synthesis, any container on a normal bridge network,
the proxy included, can then address every host-loopback listener through
10.0.2.2. The internal network is what keeps the agent-server and its tools
away from them. A daemon-wide `--disable-host-loopback` was rejected. It would
cut off every container, the proxy included, and leave the host's
non-loopback addresses reachable
([decision record](../../../docs/decisions/2026-09-28-openhands-resolver-isolation.md)).

Official grader containers are not on the attempt networks and have **no
network at all**. `e2e/docker_grader.py` creates each one with network mode
`none`, "No networking for this container" (docker/docker-py@7.1.0, the grader
lock's SDK, `docker/models/containers.py:686-694`). It enforces this at three
points:
- it refuses any upstream network, network-mode, networking-config or
  network-disabled option;
- it refuses any SDK create body whose `HostConfig.NetworkMode` is not `none`
  (`api/container.py:445-457`, `types/containers.py:351`);
- it refuses to grade when the created container's inspect shows a mode other
  than `none` or any network besides `none`, and removes that container.

moby/moby@docker-v29.8.1 records mode `none` as the single network entry `none`
at create (`daemon/create.go:251`, `daemon/container_operations.go:363-406`).
It also refuses to connect such a container to another network (`:202-204`).
Grading therefore has no path to the host's loopback listeners, the gateways or
the internet.

This is a fail-closed deviation from the upstream grading environment. The
evaluation script re-runs the repository's install command
(SWE-bench@v4.1.0 `test_spec/python.py:443-444`), and the script sets
`-uxo pipefail` but not `-e` (`test_spec/test_spec.py:55-60`). An install step
that must download therefore fails, and the tests run against the image's
preinstalled environment. A verdict that depends on network access during
evaluation is an offline verdict, not an unchanged-environment verdict. The
official gold and known-negative controls for the selected instance run under
the same condition. **Overturn:** give graders a separately probed internal
network, with its own P0-P2-style receipt, and record that before using it.

### Gateway proxy allowlist

[config/proxy-nginx.conf](config/proxy-nginx.conf) is **composed locally**
from documented nginx directives. No upstream ships this file, and its tests
are our integration checks, not upstream acceptance. The closest upstream
reference for a `/v1`-only front is OmniRoute's split-port bridge allowlist
(`src/lib/apiBridgeServer.ts:16-24,198-207` at 045aa81f3). That reference is
cited as reviewed in the phase-2 synthesis; this build did not re-read it. The
template narrows the idea to three exact routes with fixed methods and fixed
upstream URIs:

| Agent request to `gw:8081` | Forwarded as |
| --- | --- |
| POST `/v1/responses` | POST `http://10.0.2.2:<arm port>/v1/responses` |
| POST `/v1/chat/completions` | POST `http://10.0.2.2:<arm port>/v1/chat/completions` |
| GET or HEAD `/v1/models` | the same method to `http://10.0.2.2:<arm port>/v1/models` |
| any other path or method, or any query string | 403 from the proxy |

`<arm port>` is 20128 on control and 20129 on engines-on; one proxy serves one
arm. These are the only routes that reach the gateway, not the only ones the
agent can reach: nginx listens on every proxy interface, so the agent can also
use the host side below as `gw:8080`, which forwards every path to its own
agent-server.

- **Paths.** `location =` is an exact match that ends the search. Locations
  are matched against the normalized URI, after decoding `%XX`, resolving `.`
  and `..` and compressing adjacent slashes (nginx.org `ngx_http_core_module`,
  `location`, fetched 2026-09-28). A `proxy_pass` that carries a URI replaces
  the matching part of the normalized URI with its own (`ngx_http_proxy_module`,
  `proxy_pass`). Each route therefore forwards one fixed upstream path,
  whatever the request's raw form. Dot-segment and `%2e` forms that normalize
  to `/api/*` fall through to the 403 fallback.
- **Methods.** Each route has one `limit_except` block with `deny all`.
  "Allowing the GET method makes the HEAD method also allowed"
  (`ngx_http_core_module`, `limit_except`).
- **Query strings.** A `proxy_pass` with a URI still appends the request's
  arguments (nginx/nginx@release-1.30.5, 4556c714,
  `src/http/modules/ngx_http_proxy_module.c:1240-1251,1365-1384`). The
  server-level `if ($is_args) { return 403; }` refuses every query string.
  `$is_args` is `?` exactly when arguments exist
  (`src/http/ngx_http_variables.c:1609-1624`). A variable condition is false
  only when its value is an empty string or "0" (nginx.org
  `ngx_http_rewrite_module`, `if`, fetched 2026-09-28), so `?0` is refused too.
- **Headers.** The template sets `proxy_pass_request_headers off`; the
  directive "Indicates whether the header fields of the original request are
  passed to the proxied server" (`ngx_http_proxy_module`). Of the agent's
  fields, only the three the template copies reach the gateway. The gateway
  receives the fields the template sets:
  - a fixed `Host`;
  - `Content-Type`, `Accept` and `Idempotency-Key`, copied from the request;
  - `Authorization: Bearer local-loopback`;
  - `X-Correlation-Id` and `x-omniroute-session`, fixed to the run id;
  - `x-omniroute-compression`, fixed to the arm's combo.

  nginx adds its own defaults for any name the template leaves unset
  (`ngx_http_proxy_module.c:747-757`, merged at `:4210-4228`). At
  release-1.30.5 these are the body framing it generates itself,
  `Content-Length` or `Transfer-Encoding: chunked` (`:750-751`), and empty
  `Connection`, `TE`, `Keep-Alive`, `Expect` and `Upgrade` (`:749,752-755`).
  "If the value of a header field is an empty string then this field will not
  be passed" (`proxy_set_header`; source
  `ngx_http_proxy_module.c:1301-1303,1417-1418`). So no `Connection` field is
  sent; the `Connection: close` in older documentation is not the pinned
  behaviour. Before proxying, nginx refuses `Transfer-Encoding` on HTTP/1.0,
  `Transfer-Encoding` together with `Content-Length` (400 each) and any
  transfer coding other than `chunked` (501)
  (`src/http/ngx_http_request.c:2034-2064`); live framing is still P3's to
  show. Control's empty combo sends no compression header either. The
  agent cannot forge the correlation or session value, choose a compression
  plan, or send `X-Forwarded-For`, `X-Real-IP` or any other `x-omniroute-*`
  control header.
- **Host side.** Port 8080 forwards every path to `$S-server:8000` and
  refuses no arguments, because the driver's error-event search carries a
  query string. The host reaches it through `127.0.0.1:<port>`. The agent can
  also reach it as `gw:8080`, which leads only to the agent's own server and
  gives it nothing it lacks. Its access log uses the `ingress` format (time,
  method and status) instead of combined, which logs the whole request line as
  `$request` (`src/http/modules/ngx_http_log_module.c:230-232`).
- **Rendering.** `render_proxy_config` fills `@PORT@`, `@SERVER@`, `@RUN@` and
  `@COMPRESSION@` from `recipe.arm_config` and the attempt identity. It refuses:
  - a selection that differs from `arm_config`'s own output;
  - any value outside its pattern (`2012[89]`, the attempt's server name, the
    run-id pattern, or a recorded combo or empty);
  - a template whose placeholder set changed.

  The rendered file is host-owned at `runs/<run-id>/<arm>/proxy/nginx.conf`,
  outside every model mount. It is written with `O_EXCL|O_NOFOLLOW` at mode
  0644, because the image's non-root user reads the bind mount. Its SHA-256
  goes into `status.json` and the probe receipt, and both the probe and the
  gate recompute it.
- **Image.** `pins.json` `gateway_proxy` is
  `ghcr.io/nginx/nginx-unprivileged@sha256:ed04ec1ff34502c339ee5c3ae3f855442398edc1d05591e2b98981dcbbd20b1e`,
  an OCI index (tag observed `1.30.5-alpine`), with linux/amd64 manifest
  `sha256:f4522a5f…`, config `sha256:61640a44…` (user 101) and source
  nginx/docker-nginx-unprivileged@588b4cbc. It was verified three ways:
  - the SHA-256 of the registry's index, manifest and config bytes equals each
    digest;
  - `install` pulls it by digest;
  - `pinned_image_identity` finds it in the containerd store.

  Proxy launches use `--pull=never` ([evidence](evidence/phase2-commands.json)).
  The digest has not been vulnerability-scanned (plan gate G2).

Proxy residuals:
- The proxy can reach every host-loopback port by design, so a compromised
  nginx would have host-loopback reach. It runs a static, pinned, non-root,
  read-only configuration.
- A `/v1` request body reaches the gateway unchanged and can select any model
  the arm serves. The G5 preflight below bounds which providers that can be.
- Three things are unprobed, and P3 and P5 cover them: `--entrypoint nginx`
  under `--read-only`; body framing and streaming under the header allowlist;
  and gateway paths the SDK might use beyond the three routes. No running
  nginx has parsed the template yet, including the host side's `ingress` log
  format; the first live `prepare` does.
- The retained proxy log can hold the session key if the model puts it in a
  request line on the agent side, or in any request that produces a
  request-bound error entry.

### G5: gateway provider preflight

Some OmniRoute executors on the `/v1` path spawn local processes (plan N6;
`open-sse/executors/devin-cli.ts:29`, `devin-cli-agentic.ts:1`,
`auggie.ts:26`, `zcodeProtocol.ts:1`, `open-sse/services/qoderCli.ts:1` and
`open-sse/vendor/codex-chatgpt-web/process.ts:2` at 045aa81f3). A model
reaching one of them would reach the host. So at every `dispatch.py start`,
before any Docker read, the gate checks which providers each gateway store the
arm reaches can serve:
- **Stores.** Control reads the 20128 store
  (`~/.local/share/omniroute/storage.sqlite`). Engines-on reads the 20129 store
  (`omniroute-fw`) and also the 20128 store, because 20129 forwards to 20128.
  Each store is checked against its own arm's allowlist.
- **Allowlists.** They come from the host file's `gateway_providers`: control
  `codex`, engines-on `openai-compatible-responses-*`. Only a trailing `*` is
  a wildcard. `dispatch.py start` therefore also needs `OPENHANDS_HOST_FILE`.
- **Reads.** The store is opened with sqlite `mode=ro` and `query_only`. Four
  statements run: `SELECT provider FROM provider_connections`, which reads no
  credential column; `SELECT count(*) FROM combos`; and one value read each for
  the settings keys `blockedProviders` and `noAuthFallbackDisabledProviders`.
  The settings namespace also holds secrets, so no other key is read.
- **Refusals.** The gate refuses when:
  - a provider row falls outside the allowlist;
  - any routing combo exists (its targets are not read);
  - a no-auth provider is named, by id or alias, in neither the allowlist nor
    `blockedProviders`;
  - an anonymous-fallback provider is named in neither the allowlist nor
    `noAuthFallbackDisabledProviders`.

The settings keys matter because a provider row is not the only way in.
OmniRoute serves its ten no-auth providers with a synthetic credential and no
row, unless `blockedProviders` names them (`src/sse/services/auth.ts:1193-1201`,
`noAuthProviderSettings.ts:5-18`, `src/shared/utils/noAuthProviders.ts:19-31`).
Those ten include the subprocess-backed devin-cli-agentic, auggie and zcode,
plus codex-app-server. Four anonymous-fallback providers (opencode-zen,
opencode-go, pollinations and kilocode) are also served without a row, unless
`noAuthFallbackDisabledProviders` names them (`auth.ts:739-800`). A row-only
check would pass while all of these stay reachable. Both lists are copied from
OmniRoute 045aa81f3 (20128) and dd6e9607e (20129), where the files are
identical. A gateway upgrade must re-read them.

**Consequence.** The gate refuses until the operator disables those providers
in each store's OmniRoute settings. The coordinator's read-only observation on
2026-09-28 found six codex rows on 20128 and one
`openai-compatible-responses-<uuid>` node on 20129. It did not read settings or
combos, so whether the live stores pass is unknown. The unit tests use fixture
stores only.

**Limits.**
- A codex connection can opt into an app-server transport
  (`providerSpecificData.codexTransport`, behind
  `OMNIROUTE_CODEX_APP_SERVER_ENABLED`; `open-sse/executors/codex.ts:415-439`).
  G5 does not read `provider_specific_data`, which may hold key material, so it
  cannot see that opt-in.
- Inactive rows count as served.
- Routing combos are refused, not resolved.

### Isolation probe (P0-P2) and the dispatch gate

The vehicle is [e2e/netprobe.py](e2e/netprobe.py), a locally composed
standard-library script. It runs in the pinned agent-server image with the
same hardening as every model container (`docker_args`), as `$S-probe-gw` on
`$S-gw` and `$S-probe-int` on `$S-int`. Its only mounts are the SDK venv and
the recipe (read-only) and a private output directory. It sends raw request
targets through `http.client`. It records only the status, the
`x-omniroute-route-class` value and errno names, never reads a response body,
and exits nonzero at the first unexpected result. The internal probe runs only
after P0 passed.

| Probe | From | Passes when |
| --- | --- | --- |
| P0, negative control | `$S-gw` | GET `http://10.0.2.2:<arm port>/v1/models` returns 200 with route class `CLIENT_API`, and GET `/api/settings` returns a response with route class `MANAGEMENT`. This shows the vehicle can see the gateway and its management surface. |
| P1, management isolation | `$S-int` | GET `http://gw:8081/v1/models` returns 200 with `CLIENT_API`. Each of the plan's 26 denied method/target pairs returns 403 with no route-class header, so the proxy refused it rather than the gateway. The pairs cover management paths, dot-segment and `%2e` variants, case and slash variants, query strings and wrong methods. |
| P2, direct reachability | `$S-int` | A positive control first: a TCP connect to `gw:8081` succeeds. Then no address and port pair accepts a TCP connect, and every pair outside the run subnet fails for want of a route (`ENETUNREACH` or `EHOSTUNREACH`), not by timing out. One DNS datagram to 10.0.2.3:53 gets no answer, and fails the same way. `example.com`, `github.com` and `host.docker.internal` do not resolve, while `gw` and `$S-server` do. The container has no non-loopback IPv6 address, and `/proc/net/route` holds no default route and no route via a gateway. |

P2's targets are computed on the host at probe time:
- **Addresses:**
  - 10.0.2.2, 10.0.2.3, 172.17.0.1, 10.0.0.1 and 10.255.255.254;
  - every non-loopback host IPv4 address from `ip -4 -o addr`;
  - each gateway that an attempt network's IPAM actually records.
- **Ports:** every TCP listener from `ss -ltnH`, plus 53.

`$S-int` records no gateway. moby@464cd50c (docker-v29.8.1) skips gateway
allocation in isolated mode (`daemon/libnetwork/drivers/bridge/bridge_linux.go:700-713`,
`daemon/libnetwork/network.go:1594-1602`), so the server, the first endpoint,
holds the subnet's `.1`. The attempt containers' own addresses (the server's
and the proxy's on `$S-int`, the proxy's on `$S-gw`) are removed from the
targets. The receipt records, by role, any that coincided with a target; they
never stop the probe. The host passes the run subnet to the probe, and the
host-side verdict classifies each pair as inside or outside it from the
expected list, never from the probe's own record.

The route-table check reads the main table only, as the kernel writes it
(linux@v6.18 `net/ipv4/fib_trie.c:2940-3000`). For the three names that must
not resolve, the receipt keeps the resolver's error class, such as `EAI_NONAME`
or `EAI_AGAIN`. The pass condition is still only that no address resolved.
Network inspect values are context only; the failed connects are the evidence.

P0-P2 are bounded observations, not proof of every path:
- they run in probe containers on the attempt networks, not in the
  agent-server's own network namespace;
- UDP is tried only as the one DNS datagram to 10.0.2.3:53;
- no probe sends a request body, so body framing under the header allowlist is
  source-reviewed only;
- no probe makes a successful LLM request. P3 and P5 cover the last two live.

The gate re-derives the verdict from the recorded counts and refuses a
contradictory receipt. It still trusts the host that wrote the receipt: a
consistent receipt forged, or re-dated, by the owning user would pass. No
model write path to it exists.

The receipt is `runs/<run-id>/<arm>/isolation-probe.json`: mode 0600,
host-owned and outside every model mount. It holds:
- mechanism `internal-isolated+nginx-v1-allowlist`, `run_id` and `arm`;
- `run_network_id`, `gw_network_id`, `server_container_id` and
  `proxy_container_id`;
- `proxy_image`, `proxy_config_sha256` and `probe_script_sha256`;
- `upstream` (`10.0.2.2:<arm port>`), `host_ingress` (`127.0.0.1:<port>`) and
  `verified_at`;
- the probe containers' exit codes, target counts and excluded roles, the
  P0/P1/P2 counts, error-name counts and booleans, and `passed`.

`dispatch.py start`, including the `host.py run` path, calls `verify_isolation`
before it takes the serial reservation. The gate requires:
- an owner-only regular file (0600, no symlink, outside the checkout);
- `verified_at` between 0 and 900 seconds old;
- the expected mechanism, identity, upstream, ingress and proxy image;
- the current rendered config's hash, which must also equal `status.json`'s,
  and the current netprobe hash;
- passed P0, P1 and P2, re-derived from the recorded counts rather than the
  `passed` flags: both exit codes 0, every request observed and matched, a
  non-empty target set, every pair observed and failed with a named error,
  every off-subnet pair unreachable, the positive control connected, no DNS
  answer, every name matched, and no IPv6 address, default route or gateway
  route. A contradictory receipt is refused;
- the recorded stage gates below;
- the [G5 provider preflight](#g5-gateway-provider-preflight) for every store
  the arm reaches;
- the four IDs equal to the live selected-field reads.

A refusal prints `failure_stage: probe`, exits 3 and changes nothing. The run
receipt (schema 6) carries an `isolation` summary without IDs, addresses or
the run id.

**Stage gates (plan G7's P3 half, G2 and G5).** The gate also requires
`<state>/stage-gates.json`. The coordinator writes it after observing those
gates live; this recipe only reads it. Until it exists, `dispatch.py start`
and `host.py run` refuse, so prepare, read the probe receipt and tear down
instead. The file must be owner-only (0600) and outside the checkout:

```json
{"schema": "openhands-stage-gates-v1",
 "g2": {"<pins.json image.ref>": {"passed": true, "recorded_at": "<ISO time>"},
        "<pins.json gateway_proxy.ref>": {"passed": true, "recorded_at": "<ISO time>"}},
 "probes": {"p3": {"passed": true, "recorded_at": "<ISO time>", "gateway_build": "<commit>",
                   "proxy_image": "<pins.json gateway_proxy.ref>",
                   "proxy_template_sha256": "<SHA-256 of config/proxy-nginx.conf>"},
            "p4": "<same shape>", "p5": "<same shape>"},
 "g5": {"control": {"passed": true, "recorded_at": "<ISO time>"}, "engines-on": "<same shape>"}}
```

The control arm needs P3; engines-on also needs P4 and P5. No record may be
dated after the check. A probe record binds to the pinned proxy image and the
current proxy template, so changing either needs new records. The gateway
build is recorded, but this code cannot tell which build is running.

### P3-P5: documented, not run

P3-P5 are live model calls. This build wrote them as the steps below and a
skeleton, `netprobe.p3_control_call`, which raises `NotImplementedError`. None
of them has run.

- **P3, control arm.** One SDK LLM call with one tool definition, from a
  throwaway container on `$S-int` with the recipe's LLM config, through `gw` to
  20128. The call also sends a forged `X-Correlation-Id`, an `X-Forwarded-For`
  and one `x-omniroute-*` control header. A second call adds a query string; it
  must get the proxy's 403 and leave no `call_logs` row. The first call's row
  must show:
  - `/v1/responses`, status 200 and the routed model the receipt matches,
    `gpt-6-astra-max`;
  - effort max, both requested and sent upstream;
  - a gateway-generated correlation value, neither the forged one nor the run
    id, because `/v1/responses` ignores a caller's `X-Correlation-Id` at the
    pinned builds ([Usage accounting](#usage-accounting)).

  A third call shows the proxy's replacement: one POST `/v1/chat/completions`
  with the same forged header. That route keeps a caller's ID, so its row,
  whatever its status, must carry the run id. The streamed tool call must
  parse, body framing must work under the header allowlist, and the usage
  must equal the row. Record the client peer the gateway logged (F10). The
  proxy's agent-side access log must show exactly these three requests.
- **P4, engines-on arm.** The same through a proxy bound to 20129, plus these
  checks:
  - a stacked lossy plan appears in the compression analytics;
  - reasoning max appears in 20128's outbound request;
  - which headers survive nginx and the 20129-to-20128 hop;
  - whether `prompt_cache_key` is forwarded;
  - the cached-input ratio against control.
- **P5, SDK compatibility.** Encrypted reasoning include, `prompt_cache_key`
  and the tool schema. After one full short conversation, the proxy access log
  must show no denied path, or each denied path must be triaged. LiteLLM paths
  such as `/v1/responses/{id}` or `input_tokens` are unaudited.

### Live probe sequence (coordinator; not run yet)

**Prerequisites.** The probe runs only through the full preparation path:
clone, skills, QMD setup, server and proxy. It therefore needs:
- a successful `host.py install` of this revision, so both images are present
  by digest;
- #429's skills manifest under `OPENHANDS_STACK_ROOT`, or preparation stops
  at `skills_program_pending_pr`;
- the private inputs above, including a frozen task row and grader image pin;
- a free port. 3740 stays clear of crawl4ai's defaults.

P0 sends two live GET requests to the selected gateway port (`/v1/models` and
`/api/settings`) by design. P1 sends one allowlisted GET `/v1/models` through
the proxy.

```sh
export PATH="$HOME/.local/share/codex-ecosystem/tools/docker-rootless-29.8.1/bin:$PATH"
RECIPE="$PWD/blueprints/runtime-workers/openhands"
PREFIX="$HOME/.local/share/codex-ecosystem/tools/openhands-1.49.6"
STATE="$HOME/.local/state/native-agent-stack/runtime-workers/openhands"
OWNER=label=com.native-agent-stack.owner=gpt6-omniroute-framework-integration
export OPENHANDS_RUN_ID=rw-openhands-probe-001 OPENHANDS_ARM=control
# 1. Nothing owned is left over: both lists are empty.
docker --context rootless ps -a --filter "$OWNER" --format '{{.Names}}'
docker --context rootless network ls --filter "$OWNER" --format '{{.Name}}'
# 2. Topology, server and proxy, then P0-P2. Exit 0 only when the probe passed.
rtk env PYTHONDONTWRITEBYTECODE=1 python3 "$RECIPE/host.py" prepare --prefix "$PREFIX" --state "$STATE" \
  --run-id "$OPENHANDS_RUN_ID" --arm "$OPENHANDS_ARM" --port 3740
# 3. The verdict and counts only; the IDs stay private.
python3 -c 'import json, sys; r = json.load(open(sys.argv[1])); print(json.dumps({k: r.get(k) for k in ("passed", "exit_codes", "targets", "p0", "p1", "p2")}))' \
  "$STATE/runs/$OPENHANDS_RUN_ID/$OPENHANDS_ARM/isolation-probe.json"
# 4. Tear down without a conversation. Exit 0 only when all four removals are confirmed.
rtk env PYTHONDONTWRITEBYTECODE=1 python3 "$RECIPE/host.py" teardown --prefix "$PREFIX" --state "$STATE" \
  --run-id "$OPENHANDS_RUN_ID" --arm "$OPENHANDS_ARM"
# 5. Both lists are empty again, and neither key file exists.
docker --context rootless ps -a --filter "$OWNER" --format '{{.Names}}'
docker --context rootless network ls --filter "$OWNER" --format '{{.Name}}'
for kind in server.env headers; do test ! -e "$STATE/secrets/$OPENHANDS_RUN_ID-$OPENHANDS_ARM.$kind" && echo "$kind deleted"; done
```

A failed probe exits 3 from `prepare` and tears the attempt down itself. Step 3
still reads its receipt if the probe got far enough to write one, and step 4
retries any unconfirmed removal.
`host.py teardown` refuses, without any Docker call, while `status.json` shows
`starting`, `running` or `terminal`, or while the serial reservation names the
attempt. It turns a `prepared` status into `torn_down`, which both
`dispatch.py start` and `host.py probe` refuse.

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

`e2e/docker_grader.py` adapts names, ownership labels and the network mode
(`none`; see [Security posture](#security-posture)) only. It adds **no memory,
CPU, PID, capability or user changes** to the official grading container. Gold
patch and known-negative official controls must run under the frozen image, with
no network, before a worker verdict is accepted. `e2e/check.py` relays the actual report; an
error/incomplete bucket is infrastructure, not a model-negative tally.

Host work remaining: native installation and import acceptance; shared skills
PR; frozen task/image selection; the live P0-P2 probe on the O1 topology
([sequence](#live-probe-sequence-coordinator-not-run-yet)), then P3, and P4
and P5 before any engines-on run; a vulnerability scan of both image digests
(plan gate G2); port availability; native server health/auth/OpenAPI/preload
startup through the proxy; actual tool names/skills/MCP use; response-header
capture for streaming and condenser calls; entry-database matching and max
effort; official positive/negative grading controls; independent trace
observation; cancellation/cleanup recovery. No A/B or savings result is
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
