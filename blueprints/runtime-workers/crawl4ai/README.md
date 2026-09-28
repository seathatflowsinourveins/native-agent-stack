# Crawl4AI runtime worker — recipe, not host acceptance

This worker uses **unclecode/crawl4ai v0.9.4** for crawling, filtered Markdown and
structured extraction. The native Python library performs one explicitly selected
frozen LLM extraction arm per run, with **Promptfoo 0.123.1** supplying the task-quality verdict.
The authenticated rootless Docker service offers the upstream
API and MCP endpoints to other workers. This is a foundation-lane recipe prepared
for coordinator review; no packages were installed, images pulled, services
started, gateway calls made, or live gateway database read during construction.

Two upstream limitations affect the requested configuration. The reviewed server
does not expose the per-call LLM options needed for the gateway header/temperature
contract, so container consumers use non-LLM crawling and FIT Markdown. Also,
the WebSocket bridge appears incompatible with its declared MCP SDK message
envelope. Both endpoints are configured and the E2E observes both. SSE is the required
dispatch transport; WebSocket results are diagnostic and remain unqualified. The recipe does not patch
the upstream runtime or turn either limitation into a pass.

## Workflow dispatch

After the coordinator installs the reviewed snapshot, a workflow child runs the
following Bash sequence. The run ID identifies an immutable request; repeating
`start` with the same arm/input returns its status, while reusing it for a
different request is refused. `start` writes `status.json` and an incomplete
`receipt.json` before launching background work. Every operation prints one JSON
object containing the deterministic receipt path:
`$HOME/.local/state/native-agent-stack/runtime-workers/crawl4ai/runs/<run-id>/receipt.json`.

```bash
rtk bash blueprints/runtime-workers/crawl4ai/dispatch.sh start --run-id crawl-control-001 --arm control
rtk bash blueprints/runtime-workers/crawl4ai/dispatch.sh wait --run-id crawl-control-001 --arm control --timeout 55
rtk bash blueprints/runtime-workers/crawl4ai/dispatch.sh result --run-id crawl-control-001 --arm control
```

Repeat `wait` while the returned state is `starting` or `running`; a wait is
bounded to 55 seconds. Then read the printed receipt path. `start` exit 0 means
submission accepted. For `wait`/`result`, exit **0 = pass, 2 = setup failure,
3 = negative upstream verdict, 4 = incomplete evidence** (including work still
running). A setup exception produces a receipt with an error class, without the
exception's private text. A host file lock serializes extraction attempts so the
two arms cannot overlap the fixed fixture/container ports. A killed dispatcher
leaves its incomplete status for investigation; it never silently resubmits.

For engines-on, finish the control run and use the same sequence with
`--run-id crawl-engines-001 --arm engines-on`. The default `--kind extraction`
runs the frozen native Python extraction/Promptfoo trial; it is not an arbitrary
web extraction schema. Its upstream basis is
[unclecode/crawl4ai@133e1d92, pricing example:15–53](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/docs/examples/llm_extraction_openai_pricing.py#L15-L53).
The detached status wrapper is local integration using
[CPython@v3.12.12, subprocess.py](https://github.com/python/cpython/blob/v3.12.12/Lib/subprocess.py).

For general non-LLM crawling, the native REST fallback is also dispatched through
Bash. Start the persistent container first, then run:

```bash
rtk bash blueprints/runtime-workers/crawl4ai/dispatch.sh start --run-id crawl-page-001 --arm control --kind crawl --url https://example.com/
rtk bash blueprints/runtime-workers/crawl4ai/dispatch.sh wait --run-id crawl-page-001 --arm control --timeout 55
rtk bash blueprints/runtime-workers/crawl4ai/dispatch.sh result --run-id crawl-page-001 --arm control
```

This sends `POST /crawl/job`, expects 202, and polls `GET /crawl/job/{task_id}`;
completed native results go to the adjacent private `result.json`. It accepts
HTTPS seed URLs and offers no hook, JavaScript, provider or LLM strategy argument.
The job ID stays private and never enters the receipt. Native status and per-page
`success` fields own this verdict; it makes no GPT calls and claims no graded
content accuracy. Sources:
[job.py:60–64,114–149](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/deploy/docker/job.py#L114-L149),
[api.py:587–605,997–1078](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/deploy/docker/api.py#L997-L1078).

Register the recommended native MCP transport from the consumer's project directory
on the host (the builder has not run this):

```bash
rtk python3 "$HOME/.local/share/codex-ecosystem/tools/crawl4ai-0.9.4/recipe/mcp-config.py" config
rtk python3 "$HOME/.local/share/codex-ecosystem/tools/crawl4ai-0.9.4/recipe/mcp-config.py" register
```

`register` calls `claude mcp add-json crawl4ai --scope local` with explicit
`type: sse`, the private host port, a 180000 ms timeout and `headersHelper`.
Only Claude invokes the helper's `headers` action, reading the existing 0600
token on connection/reconnection. The config contains no token value. Do not
invoke `headers` interactively. The installed Claude 2.1.283 help confirms
`add-json` and local scope; headersHelper is documented in
[anthropics/claude-code@v2.1.283, CHANGELOG.md:5048,6971](https://github.com/anthropics/claude-code/blob/v2.1.283/CHANGELOG.md#L5048)
and [official MCP documentation](https://code.claude.com/docs/en/mcp).
Explicit SSE follows
[self-hosting.md:404–419](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/docs/md_v2/core/self-hosting.md#L404-L419)
and avoids probing HTTP against the unrestricted SSE route at
[mcp_bridge.py:241–253](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/deploy/docker/mcp_bridge.py#L241-L253).

The role's tools grant is `mcp__crawl4ai__md`, `mcp__crawl4ai__crawl`, with
`mcpServers: [crawl4ai]` sharing the parent's connection. Load those tools via
`ToolSearch "select:mcp__crawl4ai__md,mcp__crawl4ai__crawl"`. Use `md` with
`f=fit|raw|bm25` (`q` for bm25), or non-LLM `crawl`. Do not grant the five other
advertised tools or send `f=llm`/`provider`. Each workflow `agent()` uses its role's
`agentType`, explicit model and `effort: 'max'`. These are consumer grants, not
server-enforced restrictions. Native frontmatter and monitoring semantics are
documented in [subagents](https://code.claude.com/docs/en/sub-agents) and
[monitoring usage](https://code.claude.com/docs/en/monitoring-usage).

Count invocations in the existing `child-usage.mjs` transcript lane (server key
`crawl4ai`) and independently through OTel `claude_code.tool_result` with
`OTEL_LOG_TOOL_DETAILS=1`, grouped by MCP server/tool and child where available.
Bash dispatch operations appear as Bash tool events. On the server, compare
Gunicorn access logs for `/crawl/job`, `/crawl`, `/md` and native extraction logs;
MCP calls proxy to REST via
[mcp_bridge.py:39–82](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/deploy/docker/mcp_bridge.py#L39-L82).
These overlapping client/server observations are never added together. The host
acceptance must observe one successful child SSE call, its transcript/OTel event
and the matching native access-log/metric increment. Argument logging includes
URLs, so keep that telemetry private.

## Arms

`CRAWL4AI_ARM=control|engines-on` selects the arm; the default is **control**.
An explicit `--arm` on dispatch takes precedence. The environment overrides
`CRAWL4AI_MODEL` and `CRAWL4AI_BASE_URL` must agree with the selected arm.
`CRAWL4AI_CONTAINER_BASE_URL` is derived and exported by `container.sh`, not an
unvalidated input. LiteLLM adds `openai/` to the model string.

| Arm | Host URL | Derived container URL | Model | Gateway-only extra header |
| --- | --- | --- | --- | --- |
| control | `http://127.0.0.1:20128/v1` | `http://10.0.2.2:20128/v1` | `cx/gpt-6-astra-max` | none |
| engines-on | `http://127.0.0.1:20129/v1` | `http://10.0.2.2:20129/v1` | `sharedgw/gpt-6-astra-max` | `x-omniroute-compression: allow-lossy` |

Both arms request **max**. The engines route has exactly one slash. Control also
retains the previously supported `cx/gpt-6-*` overrides. The optional historical
`comparison` arm uses `CRAWL4AI_COMPARISON_MODEL=cx/gpt-6-sol` at medium, through
20128; it does not replace either required arm. The local common requirements
and coordinator's supplied gateway observation define these routes; this repair
does not claim a new gateway measurement. `run.json` and the receipt name the
arm, base URL, model, expected effort and header names without header values.

## Usage accounting

Usage is read once at the selected arm's entry gateway, using SQLite `?mode=ro`:
control/comparison uses `~/.local/share/omniroute/storage.sqlite`; engines-on uses
`~/.local/share/omniroute-fw/storage.sqlite`. The reader verifies that the file
exists before opening it and never creates a database. The coordinator must
confirm the engines database belongs to the running 20129 instance. Its forwarded
20128 rows are excluded. No receipt sums gateways or adds cache/reasoning subsets
to input tokens.

A native OpenAI client injected into LiteLLM attaches a synchronous HTTPX response
hook to capture `X-Correlation-Id` per wire response. IDs remain in memory, are
matched against the entry database, and are stripped from receipts. If capture
is incomplete, attribution falls back to **window + model + path at the entry
gateway**, explicitly marked as potentially concurrent. The allowlisted fields
are `timestamp`, `path`, `status`, `model`, `tokens_in`, `tokens_cache_read`,
`tokens_reasoning`, `correlation_id`, plus `reasoning_effort_requested` and
`reasoning_effort_upstream` required by the effort contract. No other table or
column is read. Sources: the hash-verified **unclecode-litellm==1.81.13** wheel,
`litellm/llms/openai/openai.py:741–790` (client injection), and
[encode/httpx@0.28.1, event-hooks.md:1–52](https://github.com/encode/httpx/blob/0.28.1/docs/advanced/event-hooks.md#L1-L52).
The wheel SHA256 is in pins.json.

`allowed_openai_params=['reasoning_effort']` preserves the effort parameter in
the fork's `litellm/utils.py:3925–3942,4677–4689`, even though
[Crawl4AI utils.py:1820–1837](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/crawl4ai/utils.py#L1820-L1837)
enables `drop_params`. LiteLLM and OpenAI client retries are zero. For rows with
reasoning tokens greater than zero, both logged efforts must equal the arm's
expected effort. Rows with zero returned reasoning are counted separately;
unknown counters or missing effort on reasoning-bearing rows make evidence
incomplete. Null effort alone does not prove that the request omitted effort:
[OmniRoute@a58000c7, callLogs.ts:642–653](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L642-L653)
sets those fields only for encrypted reasoning observations.

Engines-on separately samples `GET /api/analytics/compression?since=all` before
and after extraction. Only `totalRequests` and `totalTokensSaved` are retained as
nonnegative counter deltas. Resets, unavailable/auth-refused endpoints and unknown
values yield incomplete evidence, never zero savings. These service-wide deltas
may include concurrent traffic and are not provider-token or causal savings.
Sources: [analytics route:13–24](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/app/api/analytics/compression/route.ts#L13-L24)
and [compressionAnalytics.ts:613–617](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/db/compressionAnalytics.ts#L613-L617).
This source pin is the installed gateway's documented base; host patch behavior
still needs observation.

## Security posture

The extraction model produces structured data; it receives no host shell, Python
execution tool, MCP client or arbitrary hook. The recipe grants calling children
only the two non-LLM Crawl4AI tools above. Caller role tools outside this recipe
remain the coordinator's responsibility. Host-owned run/grade/status files live
outside the container's writable crawl/cache/Redis mounts, and raw provider or
server content never supplies receipt routing or usage evidence.

The runtime container drops all capabilities and adds only `CHOWN`,
`DAC_OVERRIDE`, `SETUID`, `SETGID` for secret/bootstrap ownership and the native
supervisor's appuser transition. It uses `no-new-privileges:true`, a read-only
root, dedicated writable stores and a restricted `/tmp` tmpfs. Redis, Gunicorn
and its browser run as appuser. Bootstrap/supervisor retain container root because
the rootless mapping makes host-owned 0600 secret mounts unreadable to appuser.
The wrapper temporarily owns only the dedicated mount roots for chmod, then
returns them to appuser. Sources:
[Crawl4AI Dockerfile:180–209](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/Dockerfile#L180-L209),
[entrypoint.sh:8–39](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/deploy/docker/entrypoint.sh#L8-L39),
[Compose spec@914ec15, 05-services.md:171,1839,1955,2029](https://github.com/compose-spec/compose-spec/blob/914ec15d1fa498969c0df5c1d672306db3256089/05-services.md#L171).
The coordinator must test startup/restart under those restrictions. These limits
apply to the crawler service; the unchanged upstream grader is not containerized
or given additional runtime limits by this repair.

**Residual network risk:** this recipe does not implement a per-port firewall for
host-loopback access. The reviewed rootless Docker mechanism is daemon-wide
`--disable-host-loopback`, not a per-container port allowlist
([moby/moby@v28.5.1, dockerd-rootless.sh:89–130,147–162](https://github.com/moby/moby/blob/v28.5.1/contrib/dockerd-rootless.sh#L89-L162)).
Docker is unavailable in the builder environment, so no installed-runtime
per-port capability is claimed. Automatic daemon/network changes are declined
in this worktree-only round. Persistent crawling keeps native internal-address
denial and hooks disabled; only the transient fixture project enables internal
URLs. A compromised renderer, or that broad E2E override, may still reach other
host listeners through 10.0.2.2. Before admitting untrusted workloads, the
coordinator must measure isolation and use supported explicit service forwarders
with host-loopback disabled, or an isolated internal network. Authenticated MCP
tool grants and URL checks do not establish that network boundary.

Python dependencies remain hash-locked wheel-only installs. The grader now uses
`npm ci --ignore-scripts` against its integrity lock, following
[npm/cli@v11.19.0, npm-ci.md:15–24](https://github.com/npm/cli/blob/v11.19.0/docs/lib/content/commands/npm-ci.md#L15-L24).
No lifecycle script is implicitly re-enabled to make a failed host install pass.

## Pins and artifact provenance

The [release](https://github.com/unclecode/crawl4ai/releases/tag/v0.9.4) resolves to
commit **`133e1d92e37885dfccc03ea2e3687d06c98b7ceb`**. Machine-readable pins are in
[pins.json](pins.json); the independent registry observation is in
[registry-evidence.json](registry-evidence.json).

| Artifact | SHA256 |
| --- | --- |
| Official Docker image, Linux amd64 manifest | `048848e548fad60c670bd656cbb3eb204fd999709a30365d3697c411ce50796d` |
| Official multi-platform image index for tag `0.9.4` | `9021b3cb5c6f12570bbcd5395638495e0a06969b3148e377b953d174af2ebc9b` |
| Crawl4AI 0.9.4 PyPI wheel | `46779c8a93b35c7c5f9be9642ddef5e7b515e36b094639bb8e1e418bf0266179` |
| Derived 95-distribution Python 3.12 wheel lock | `515633e3e9a1c94fc4bf9479f67983ccdc673b0a0f8fe04f27237fc10a53a701` |
| Playwright 1.63.0 Linux x86_64 wheel | `ad21bc07516b187965a7521c5cf0df0bd657b17482eaad74335272d35a2b07de` |
| Headless Chromium 153.0.8010.12 / revision 1243 archive | `a9da028861a0cf789ff25c2fed45f5f1aaf969ed9247835b6a7821a4f7af9d1d` |
| FFmpeg revision 1011 Linux archive | `ebc74fc5b94830176a3c2914ae96bd8bc7f6a91f4f33890230f84a172ee61ccc` |

Registry manifest bytes were hashed and matched to their `Docker-Content-Digest`;
the image config labels version 0.9.4. Its BuildKit SLSA provenance names the
release commit and [upstream build](https://github.com/unclecode/crawl4ai/actions/runs/35859470077/attempts/1).
This verifies the source association declared by upstream; no signature or runtime
claim is implied. The installer pulls the architecture-specific digest, never a
mutable tag. Docker verifies the downloaded content-addressed layers.

Wheel digests come from the [PyPI release metadata](https://pypi.org/pypi/crawl4ai/0.9.4/json)
and are enforced by `uv pip sync --require-hashes --only-binary :all:`. The tag's
[`uv.lock`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/uv.lock) has SHA256
`c672410c737e3085cae56d948854596284b7ac55066a97d9241d91913e3bb8e9`, but predates
the release's `unclecode-litellm==1.81.13` requirement. Using it unchanged would
select the wrong LiteLLM distribution. [research.md](research.md) records this
gap, the exact metadata-only lock command, failed attempts, and corrections.
The derived lock is explicitly local evidence.

Browser URLs and revisions were read from the verified Playwright wheel, then
the upstream CDN responses were streamed into SHA256. These measured hashes are
not upstream-published signed checksums. [browser-artifacts.json](browser-artifacts.json)
retains URLs, sizes and digests. The installer verifies the archives before
exposing them through a temporary loopback mirror and invoking the unchanged
Playwright installer with `PLAYWRIGHT_DOWNLOAD_HOST`. No unchecked browser
download is needed. Headless Chromium is sufficient for this worker's native
headless browser; Firefox, WebKit and browser OS-dependency installation are
outside this recipe.

## Supported installation and the selected deployment

The tag's [README:249–305](https://github.com/unclecode/crawl4ai/blob/v0.9.4/README.md#L249-L305)
documents PyPI installation, browser setup, explicit `python -m playwright install
chromium`, and editable source installation. Its [container instructions:314–333](https://github.com/unclecode/crawl4ai/blob/v0.9.4/README.md#L314-L333)
document the upstream image and port 11235. The [Dockerfile:129–184](https://github.com/unclecode/crawl4ai/blob/v0.9.4/Dockerfile#L129-L184)
builds the package/API dependencies and browser assets. We use that image directly
and a separate hash-locked native venv: API/MCP runtime dependencies stay inside
Docker while host extraction has its own Python dependency closure.

The coordinator can run these commands after reviewing this directory:

```bash
bash blueprints/runtime-workers/crawl4ai/install.sh
bash blueprints/runtime-workers/crawl4ai/container.sh start
bash blueprints/runtime-workers/crawl4ai/container.sh status
rtk bash blueprints/runtime-workers/crawl4ai/dispatch.sh start --run-id crawl-control-001 --arm control
bash blueprints/runtime-workers/crawl4ai/container.sh stop
```

`install.sh` requires existing Linux x86_64, Python 3.12, uv 0.12.17, rootless
Docker and Compose, plus Node >=22.22.0 and npm for Promptfoo. It performs no sudo
operation and installs no host OS packages. The upstream
[npm installation](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/installation.md)
uses the reviewed [grader/package-lock.json](grader/package-lock.json):
`npm ci --ignore-scripts --prefix "$NAS_CRAWL4AI_PREFIX/grader"
--cache "$NAS_CRAWL4AI_STATE/cache/npm" --no-audit --no-fund`.
All 942 dependency entries have registry SHA512 integrity. The lock's SHA256 is
checked against pins.json before installation. The executable is
`grader/node_modules/.bin/promptfoo`; unexpected versions are refused. The lock
was generated with npm 11.19.0 in metadata-only mode: no packages or scripts ran.
The coordinator must verify that the fresh install supports the unchanged
standalone grader, including any native modules, with lifecycle scripts disabled.
The native prefix is `$HOME/.local/share/codex-ecosystem/tools/crawl4ai-0.9.4`.
Owned state lives under
`$HOME/.local/state/native-agent-stack/runtime-workers/crawl4ai/`, with mode 0700
directories and a private 0600 `host.json`. The template
[config/host.example.json](config/host.example.json) contains placeholders only;
the installed file supplies actual executable paths, ports and working directory.
It is retained on repeat installs. Default ports are API 3730, fixture 3731,
browser mirror 3732 and transient E2E API 3734, all published/bound on 127.0.0.1.
`host.py` accepts only four distinct integer ports in **3730..3799**. Ports
3710..3729 and 5433..5439 belong to S3; 3800..3819 belongs to cognee. The existing
20128/20129 gateways are client destinations. The upstream container's internal 11235
API and internal Redis listener are not published as host worker listeners.

The venv has its own `.cache/ms-playwright` reference to the worker's private
browser store. Crawl databases, logs, model/tokenizer caches, temporary files,
run artifacts, and container crawl/cache/Redis stores are separately scoped.
Container browser binaries stay at their baked image path. Persistent and E2E
container stores are separate. Mapped appuser-owned 0700 leaf directories are
left to container startup on a repeated install; the host installer does not
descend into them.

For additional native Python usage after installation, source the installed
`recipe/common.sh` to select these caches and invoke
`$NAS_CRAWL4AI_PREFIX/venv/bin/python`; use the native classes/settings in
`worker.py` as the pinned extraction example. The environment file is a shell
fragment with no credentials, not a replacement for the host's account stores.

`install.sh` generates and retains independent random `api_token`, `secret_key`
and `redis_password` files under the private state `secrets/` directory. They are
0600, outside every repository, never printed and never included in a Compose
environment file. The upstream [entrypoint:9–37](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/entrypoint.sh#L9-L37)
reads its token/password secret mounts; our short startup wrapper reads the JWT
signing key privately. [Auth middleware:432–448](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/server.py#L432-L448)
protects API/MCP HTTP and WebSocket routes, using [Bearer token verification](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/auth_gate.py#L75-L126).
Upstream intentionally leaves health and UI shells public. Authenticated MCP
clients must send `Authorization: Bearer <privately loaded token>`; do not put
credentials in URLs or committed client configurations.

The image normally uses `appuser` ([Dockerfile:224](https://github.com/unclecode/crawl4ai/blob/v0.9.4/Dockerfile#L224)).
Compose starts the entrypoint as root **inside rootless Docker** so it can read
host-owned secret mounts and initialize only the three dedicated container stores.
The upstream supervisor retains `user=appuser` for Redis and Gunicorn. Its
[deployment template:18–32](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/supervisord.conf#L18-L32)
is adapted only for a second explicit loopback listener and native logging.
Gunicorn's [repeatable bind and log settings](https://github.com/benoitc/gunicorn/blob/23.0.0/gunicorn/config.py)
listen on the container interface plus `127.0.0.1:11235`: the latter is required
by [MCP's internal HTTP proxy](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/server.py#L1183-L1190).
There is no wildcard listener in the recipe. The service has one Gunicorn worker,
2 CPUs, 3 GiB memory, 512 PIDs, 1 GiB shared memory and bounded Docker logs.

Lifecycle is explicit: the two Compose projects/containers are named
`rw-crawl4ai-persistent` and `rw-crawl4ai-e2e`; their networks are
`rw-crawl4ai-persistent-net` and `rw-crawl4ai-e2e-net`. Every container and network
has `com.native-agent-stack.owner=gpt6-omniroute-framework-integration`.
There are no Docker volume objects: all storage uses the dedicated bind
directories shown in Compose. `stop` removes only the literal container/network
names for its selected project and keeps those directories. No broad Docker
cleanup is used. Rerunning install keeps credentials and private host settings, reuses
verified archives, and syncs the same pins. No daemon, global Docker config,
production service or sign-in is changed. Removal of mapped-UID container stores
requires cleanup from the rootless container identity before deleting the owned
prefix/state; no broad deletion command is supplied. Crash/reboot recovery and
second-host operation remain unmeasured.

## LLM and token-efficiency settings

[config/worker.json](config/worker.json) is the secret-free native configuration.
[worker.py](worker.py) follows the official [structured extraction example:15–53](https://github.com/unclecode/crawl4ai/blob/v0.9.4/docs/examples/llm_extraction_openai_pricing.py#L15-L53).

| Setting | Configuration and upstream source |
| --- | --- |
| Model/provider | Config `arms[arm].model`, overridden by `CRAWL4AI_MODEL`, defaults to the selected arm route; `LLMConfig.provider` receives `openai/` plus that value. [`async_configs.py:2346–2409`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/async_configs.py#L2346-L2409). The engines-on model is restricted to the common contract's one-slash route. |
| Native gateway | `LLMConfig.base_url` is the selected arm's 20128/20129 loopback URL, `api_token=local-loopback`; the key is the gateway's non-secret placeholder. Same source as above. |
| Container gateway | `LLM_PROVIDER`, `LLM_API_KEY`, `OPENAI_BASE_URL` and `LLM_BASE_URL` use the selected arm's `container_base_url`; [`deploy/docker/utils.py:114–138`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/utils.py#L114-L138), [`293–316`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/utils.py#L293-L316). Configured for the host network, but container LLM calls remain outside the qualified contract described below. |
| Arm effort | Control and engines-on both send `reasoning_effort=max` with `allowed_openai_params=["reasoning_effort"]`, preserving the parameter despite upstream `drop_params=True`. See the wheel/file references under Usage accounting. |
| Optional legacy comparison | `arms.comparison` retains `cx/gpt-6-sol` and medium effort through 20128, explicitly selected with `--arm comparison`. This is separate from the required max/max arm pair. |
| Sampling and headers | `LLMExtractionStrategy.extra_args` carries `temperature=None`, stable `x-omniroute-session` per arm/conversation and fresh `Idempotency-Key` per page/logical call. [`extraction_strategy.py:598–617,685–691`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/extraction_strategy.py#L598-L691), [official header example:23–25](https://github.com/unclecode/crawl4ai/blob/v0.9.4/docs/examples/llm_extraction_openai_pricing.py#L23-L25). The explicit None overrides the otherwise hidden temperature 0.01 in [`utils.py:1825–1837`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/utils.py#L1825-L1837); the verified LiteLLM fork drops None before serialization. |
| Structured output | `extra_args.response_format` overrides the native `json_object` default with `json_schema`, `strict:true`, and the frozen schema's `additionalProperties:false` on every object. All properties are required. The user instruction contains JSON. This follows the gateway owner's supplied cognee 1.6.1 observation: a system-only JSON mention is insufficient after it becomes instructions. The native parser reads message content, so this recipe uses strict schema rather than assuming native tool-call parsing. |
| Transport | Native LiteLLM `completion()` uses chat completions, not a Crawl4AI Responses path. The selected extraction implementation expects a complete `response.choices[0].message`; streaming is not enabled. Omitting temperature is the compatible gateway-cache choice. The owner's measured gateway accepts these GPT-6 chat requests; actual wire headers/omission remain host observations. |
| Content selection | `DefaultMarkdownGenerator(content_filter=PruningContentFilterLXML(...))`, `threshold=0.35`, `threshold_type=fixed`, `min_word_threshold=1`; exclude nav/footer/aside; pass only nonempty `fit_markdown` to extraction. [Upstream FIT guide:43–90](https://github.com/unclecode/crawl4ai/blob/v0.9.4/docs/md_v2/core/fit-markdown.md#L43-L90). |
| Budgets | One page per strategy, `apply_chunking=False`, `extra_args.max_tokens=3000`, timeout 180 s. A local 6000-character/4096-estimated-token guard with `word_token_rate=1.3` bounds the one extraction unit. LiteLLM `num_retries=0`, `max_retries=0`, an OpenAI client with `max_retries=0`, and native `LLMConfig.backoff_max_attempts=1` bound calls. [`extraction_strategy.py:556–617,774–835`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/extraction_strategy.py#L556-L617). No silent truncation. |
| Cache/state | `CrawlerRunConfig.cache_mode=CacheMode.BYPASS` for measurement; `CRAWL4_AI_BASE_DIRECTORY` scopes native databases/logs. [`async_database.py:17–21`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/async_database.py#L17-L21). Filtering bytes are retained independently from provider counters; gateway compression/cache settings remain unchanged. |

Model validation allows `cx/gpt-6-*` on control/comparison and exactly
`sharedgw/gpt-6-astra-max` on engines-on. It rejects cross-arm, two-slash and
non-GPT-6 routes before resources start. Promptfoo grades the frozen answers
deterministically, without model calls.

The two-phase crawl/filter/extract sequence prevents the upstream crawler's
[empty-FIT fallback](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/async_webcrawler.py#L925-L935)
from sending unfiltered content to the model. Raw extraction returns and filtered
Markdown stay in private run artifacts; only deterministic products and sanitized
measurements leave the worker. These byte counts are not claimed token savings.
No embedder or embedding endpoint is configured: the pruning filter is local.

The Docker API has an important narrower boundary. [`/crawl` always deserializes
request configs as untrusted](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/server.py#L974-L976),
and [the allowed types exclude LLM strategies/configs](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/async_configs.py#L181-L199).
The separate [`/llm` implementation](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/api.py#L239-L251)
and [`md` LLM branch](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/api.py#L362-L376)
do not expose `extra_args`. They therefore cannot be presented as satisfying
the required custom headers/temperature omission. Native extraction is the selected
LLM path. A future server release exposing those settings would reopen the
container LLM qualification; current consumer guidance uses `md` FIT/raw/BM25 and
non-LLM `crawl` only.

## MCP and skills boundary

The upstream service mounts SSE at `/mcp/sse` with POST `/mcp/messages/`, and
WebSocket at `/mcp/ws` ([bridge:197–256](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/mcp_bridge.py#L197-L256)).
Default consumer URLs are `http://127.0.0.1:3730/mcp/sse` and
`ws://127.0.0.1:3730/mcp/ws`. Authentication comes from the caller's private host
configuration/token reader. Recommend only `md` and `crawl` in a consumer's tool
allowlist; upstream additionally advertises HTML, screenshots, PDF, JavaScript and
ask tools, so discovery of the server alone is not a tool-limit policy.

No external MCP-client loader or SKILL.md loader was found in the reviewed tag's
source tree/release/CLI sources. Installed-client verification is pending. Thus
there are **no loaded stack MCP servers or linked skill directories inside
Crawl4AI**. [config/mcp-policy.json](config/mcp-policy.json) records this explicitly,
along with the calling workers' required tool limits and exact launch commands
read from the two supplied adoption templates. It is a consumer contract, not
invented Crawl4AI configuration:

- context-mode excludes `ctx_upgrade` and `ctx_purge`, with its project bound to
  the calling worker's directory.
- ai-memory exposes only the five specified read tools; SocratiCode exposes the
  four specified read tools and uses `SOCRATICODE_WATCHER=manual`.
- QMD requests select the four named collections explicitly; its server launch
  is the template's named index. This is not a claimed server-side collection ACL.
- Headroom's three tools are conditional on otherwise-uncontained outputs.
  FIT Markdown supplies this worker's own containment.
- Serena/jCodeMunch apply to coding consumers. There is no jCodeMunch launch entry
  in the two supplied templates, and no invented launch command is supplied.

The pinned stack skill manifest was inspected. Skill discovery also found an
[official Crawl4AI skill archive](https://github.com/unclecode/crawl4ai/blob/v0.9.4/docs/md_v2/assets/crawl4ai-skill.zip)
whose embedded skill is version 0.7.4, dated 2025-01-19. It teaches a calling agent
how to use Crawl4AI. It is not evidence that Crawl4AI consumes SKILL.md, and is not
silently installed as a replacement for the already pinned `$HOME/.agents/skills`.

The startup inventory is **`[]`**: the selected native runtime has no discovered
SKILL.md loader or skill-list API. `run.json` and the sanitized receipt explicitly
record this limit. No `skill-trigger` or `skill-load` events are claimed; E2E skill
activation is not applicable to this crawler. A future calling-agent integration
must retain its own framework trace showing a listed skill's trigger/load event;
an installed directory or a recipe-emitted message cannot prove activation.

For a **calling agent that loads SKILL.md**, the only installation path in this
recipe is the coordinator's installer, pending the skills PR that supplies the
new manifest and project/universal options. From the repository root, with that
agent's external workspace selected:

```bash
python3 tools/adoption/install_skills.py \
  --manifest blueprints/runtime-workers/skills/manifest.json \
  --project-dir "$NAS_CRAWL4AI_WORKSPACE" --agent universal
```

The crawler installer does not invoke this conditional command because it has no
skill loader. The unit contract asserts this exact supported lifecycle in the
recipe; no direct copy, symlink or ad-hoc skill download is introduced.

The WebSocket concern is specific: [the bridge passes bare JSONRPCMessage
objects](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/mcp_bridge.py#L209-L237),
while its declared `mcp>=1.18.0,<2` dependency's [server](https://github.com/modelcontextprotocol/python-sdk/blob/v1.18.0/src/mcp/server/lowlevel/server.py#L597-L601)
and [session reader](https://github.com/modelcontextprotocol/python-sdk/blob/v1.18.0/src/mcp/shared/session.py#L330-L353)
expect SessionMessage wrappers. This is a source compatibility concern, not a
runtime failure already measured against the image. The E2E retains the WebSocket outcome as diagnostic evidence. SSE, authentication,
and native extraction remain required; no WebSocket success is inferred.

## Frozen E2E and receipts

[e2e/fixtures/](e2e/fixtures/) contains three authored local HTML product pages
with current facts and distracting archived offers/navigation. The input is a
synthetic fixture. [schema.json](e2e/schema.json), [expected.json](e2e/expected.json)
were frozen before any provider run. **The verdict comes from the unchanged
Promptfoo 0.123.1 `is-json` and `equals` assertions**, configured in
[assertions.json](e2e/assertions.json). `equals` uses upstream deep strict equality
against all 18 fields in `expected.json`, including types and page order. Neither
Python nor JavaScript supplies a custom scorer. The native extraction adapter
removes only Crawl4AI's `error:false` metadata and retains its raw response file.
Expected answers never enter the LLM prompt.

The supplied W8d report selects Promptfoo's HTTP provider as its primary mapping.
At this Crawl4AI pin, `/crawl` explicitly excludes `LLMConfig` and
`LLMExtractionStrategy` from its untrusted configuration loader
([source](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/crawl4ai/async_configs.py#L181)).
The adopted supported alternative is Promptfoo's
[standalone output grading](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/configuration/expected-outputs/index.md#running-assertions-directly-on-outputs)
over the native Python trial results. The runner-up,
[Crawl4AI v0.9.4 extraction regression](https://github.com/unclecode/crawl4ai/blob/v0.9.4/tests/regression/test_reg_extraction.py),
checks five fixed products with CSS extraction; it does not exercise GPT-6 or
OmniRoute and was not chosen as the A/B quality grader.

[check.py](e2e/check.py) only transports a file's UTF-8 text into the documented
JSON string-array format. Its exit 0 certifies transport, never quality; wrong,
empty and malformed outputs reach the upstream grader unchanged. The runner
[grade.py](e2e/grade.py) invokes:

```bash
promptfoo eval --assertions assertions.json --model-outputs <outputs.json> \
  --no-cache --no-share --no-write --no-progress-bar --no-table \
  --max-concurrency 1 -o <promptfoo.json>
```

The actual executable is the private pinned installation. Both CLI pass threshold
and failure exit code are fixed to 100; config/log/cache paths are scoped to the
private run directory. Before model calls, the same adapter and assertions run
known-pass, wrong-price and malformed-JSON controls, expecting exit **0/100/100**.
Each arm retains the full upstream report, stdout/stderr, exit code and hashes
binding its input and frozen assertions. Missing, modified or empty reports fail
the receipt gate. The receipt reads upstream success fields rather than scoring
the answer again. Standalone EchoProvider counters are not model usage.

`run-e2e.sh` uses the installed prefix and private working directory, serves the
frozen pages on host loopback, and starts only the separate `rw-crawl4ai-e2e`
Compose project. The fixture container reaches that host listener through
`10.0.2.2`. Its explicit `CRAWL4AI_ALLOW_INTERNAL_URLS=true` is a broad upstream
[egress override](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/egress_broker.py#L34-L35),
confined to this transient project and removed by the cleanup path. The persistent
service retains the upstream internal-address denial.

The runner performs unauthenticated denial controls, authenticated API FIT crawling,
SSE and WebSocket initialization/tool calls, then three sequential native extraction
calls for the selected arm. It retains every attempt in a fresh private run directory,
including failures, filtered Markdown, raw extraction results, native logs, time
windows and cleanup outcome. It never retries an entire trial to replace a failed
receipt. Retries are disabled; any extra observed gateway call still makes the
exact-three-call routing gate fail for review. No automatic model promotion occurs.

[e2e/receipt.py](e2e/receipt.py) uses the selected arm's entry database and
the allowlisted fields documented under Usage accounting. Public receipts contain
hashes and sanitized observations, never raw logs, host paths, credential values,
correlation IDs, or session/request identifiers. The native container log's
`POST /md` count includes direct REST probes and MCP requests together. It is a
route cross-check and never an inferred MCP tool count. Native `CallToolRequest`
counts and the authenticated SSE probe remain separate. Skills remain “none
observed.”
Inputs, schema/oracle, worker/configuration, browser metadata, dependency lock and
deployment files are hashed for reproducibility.

## Evidence classes and remaining host checks

| Class | Available evidence / boundary |
| --- | --- |
| Upstream source read | Release/commit, registry provenance, supported installation/configuration, native filtering/extraction and auth/MCP source. This is the basis for the recipe, not native acceptance. |
| Structural/offline checks | Round-1 evidence stays in `verification.json`. Round-3 failing-first and final output is in `verification-round3.json`; previous rounds remain historical; checks cover request configuration, ports/ownership, transport, grader-report binding and receipt redaction. |
| Upstream grader execution | Installed Promptfoo 0.123.1 runs the unchanged assertions on synthetic positive/negative controls. This is actual upstream grader execution, with no new model execution or host installation. |
| Synthetic fixtures | Three authored pages and a frozen exact oracle. Offline positive data is the oracle itself and never described as a provider result. |
| Local host integration | Pending: install/reinstall, Playwright launch, private modes and mapped UID behavior, hardened container startup, protected API, SSE dispatch, diagnostic WebSocket transport, model extraction, headers/effort, native logs, receipt generation and cleanup/restart. |
| Unchanged upstream tests | Not run in this builder. The upstream MCP socket example informed our probe; the SSE example's stale URL was not relabeled as passed. Docker pytest suites and any broader upstream acceptance remain separate coordinator work. |

The existing coordinator host facts are inputs, not measurements repeated here.
The gateway DB's allowed columns do not include request headers or temperature, so
the receipt cannot independently prove header retention, sampling omission or
wire-level forwarding through both gateways. Correlation matching narrows receipt attribution when all response headers are captured. Those require the gateway owner's bounded
observation; the builder does not access forbidden columns. Container LLM request
controls, WebSocket compatibility, broader crawl quality, real websites, persistent
session behavior, causal token savings and model-currency decisions remain open.

Run the local contracts with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover
-s tests -p test_runtime_worker_crawl4ai.py`, with `TMPDIR` set to the assigned
scratch directory inside the owned worktree; remove it after the run. Promptfoo 0.123.1 must already be on PATH for the
native grader checks; those checks explicitly skip if it is unavailable. Run
`PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate.py` afterward. The coordinator
owns re-registering changed hashes in the shared evidence manifest; this builder
edits only the recipe and its assigned unit test.
