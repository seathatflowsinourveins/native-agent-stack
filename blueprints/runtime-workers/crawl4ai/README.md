# Crawl4AI runtime worker — recipe, not host acceptance

This worker uses **unclecode/crawl4ai v0.9.4** for crawling, filtered Markdown and
structured extraction. The native Python library performs the two frozen LLM
extraction trials, with **Promptfoo 0.123.1** supplying the task-quality verdict.
The authenticated rootless Docker service offers the upstream
API and MCP endpoints to other workers. This is a foundation-lane recipe prepared
for coordinator review; no packages were installed, images pulled, services
started, gateway calls made, or live gateway database read during construction.

Two upstream limitations affect the requested configuration. The reviewed server
does not expose the per-call LLM options needed for the gateway header/temperature
contract, so container consumers use non-LLM crawling and FIT Markdown. Also,
the WebSocket bridge appears incompatible with its declared MCP SDK message
envelope. Both endpoints are configured and the E2E checks both, but successful
WebSocket operation remains an unresolved host gate. The recipe does not patch
the upstream runtime or turn either limitation into a pass.

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
bash blueprints/runtime-workers/crawl4ai/run-e2e.sh
bash blueprints/runtime-workers/crawl4ai/container.sh stop
```

`install.sh` requires existing Linux x86_64, Python 3.12, uv 0.12.17, rootless
Docker and Compose, plus Node >=22.22.0 and npm for Promptfoo. It performs no sudo
operation and installs no host OS packages. The upstream
[npm installation](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/installation.md)
is pinned with `npm install --global --prefix "$NAS_CRAWL4AI_PREFIX/grader"
--cache "$NAS_CRAWL4AI_STATE/cache/npm" --no-audit --no-fund promptfoo@0.123.1`.
The private prefix's `grader/bin/promptfoo` is the E2E executable; an unexpected
version is refused. The npm dependency closure is resolved at install time, unlike
the frozen Python wheel lock; a transitive npm lock remains a reproducibility gap.
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
20128 gateway is a client destination. The upstream container's internal 11235
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
| Model/provider | Config `llm.model`, overridden by `CRAWL4AI_MODEL`, defaults to `cx/gpt-6-astra-max`; `LLMConfig.provider` receives `openai/` plus that value. [`async_configs.py:2346–2409`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/async_configs.py#L2346-L2409). No model identifier is hard-coded in worker code. |
| Native gateway | `LLMConfig.base_url=http://127.0.0.1:20128/v1`, `api_token=local-loopback`; the key is the gateway's non-secret placeholder. Same source as above. |
| Container gateway | `LLM_PROVIDER`, `LLM_API_KEY`, `OPENAI_BASE_URL` and `LLM_BASE_URL=http://10.0.2.2:20128/v1`; [`deploy/docker/utils.py:114–138`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/utils.py#L114-L138), [`293–316`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/deploy/docker/utils.py#L293-L316). Configured for the host network, but container LLM calls remain outside the qualified contract described below. |
| Primary effort | Gateway `-max` alias; no body effort is sent. The supplied gateway-owner verdict establishes alias behavior; Crawl4AI itself does not implement that alias. |
| Comparison effort | Config `comparison.model=cx/gpt-6-sol`, overridable by `CRAWL4AI_COMPARISON_MODEL`; `extra_args.reasoning_effort=medium`. Both arms must pass the same oracle and have matching gateway effort observations. |
| Sampling and headers | `LLMExtractionStrategy.extra_args` carries `temperature=None`, stable `x-omniroute-session` per arm/conversation and fresh `Idempotency-Key` per page/logical call. [`extraction_strategy.py:598–617,685–691`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/extraction_strategy.py#L598-L691), [official header example:23–25](https://github.com/unclecode/crawl4ai/blob/v0.9.4/docs/examples/llm_extraction_openai_pricing.py#L23-L25). The explicit None overrides the otherwise hidden temperature 0.01 in [`utils.py:1825–1837`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/utils.py#L1825-L1837); the verified LiteLLM fork drops None before serialization. |
| Structured output | `extra_args.response_format` overrides the native `json_object` default with `json_schema`, `strict:true`, and the frozen schema's `additionalProperties:false` on every object. All properties are required. The user instruction contains JSON. This follows the gateway owner's supplied cognee 1.6.1 observation: a system-only JSON mention is insufficient after it becomes instructions. The native parser reads message content, so this recipe uses strict schema rather than assuming native tool-call parsing. |
| Transport | Native LiteLLM `completion()` uses chat completions, not a Crawl4AI Responses path. The selected extraction implementation expects a complete `response.choices[0].message`; streaming is not enabled. Omitting temperature is the compatible gateway-cache choice. The owner's measured gateway accepts these GPT-6 chat requests; actual wire headers/omission remain host observations. |
| Content selection | `DefaultMarkdownGenerator(content_filter=PruningContentFilterLXML(...))`, `threshold=0.35`, `threshold_type=fixed`, `min_word_threshold=1`; exclude nav/footer/aside; pass only nonempty `fit_markdown` to extraction. [Upstream FIT guide:43–90](https://github.com/unclecode/crawl4ai/blob/v0.9.4/docs/md_v2/core/fit-markdown.md#L43-L90). |
| Budgets | One page per strategy, `apply_chunking=False`, `extra_args.max_tokens=3000`, timeout 180 s. A local 6000-character/4096-estimated-token guard with `word_token_rate=1.3` bounds the one extraction unit. Both LiteLLM `num_retries=0` and native `LLMConfig.backoff_max_attempts=1` bound calls. [`extraction_strategy.py:556–617,774–835`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/extraction_strategy.py#L556-L617). No silent truncation. |
| Cache/state | `CrawlerRunConfig.cache_mode=CacheMode.BYPASS` for measurement; `CRAWL4_AI_BASE_DIRECTORY` scopes native databases/logs. [`async_database.py:17–21`](https://github.com/unclecode/crawl4ai/blob/v0.9.4/crawl4ai/async_database.py#L17-L21). Filtering bytes are retained independently from provider counters; gateway compression/cache settings remain unchanged. |

Both configurable model routes must be `cx/gpt-6-*`; `model_for` rejects Claude
and other families before a call or container start. The primary quality role
defaults to `cx/gpt-6-astra-max`, with `cx/gpt-6-sol`/medium as the explicit A/B
comparison. There is no additional model-based judge: Promptfoo grades the frozen
answers deterministically, and makes no gateway calls while grading.

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
runtime failure already measured against the image. The E2E retains a failed
WebSocket gate if it occurs and continues the independent native model arms.

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
calls per model arm. It retains every attempt in a fresh private run directory,
including failures, filtered Markdown, raw extraction results, native logs, time
windows and cleanup outcome. It never retries an entire trial to replace a failed
receipt. Retries are disabled; any extra observed gateway call still makes the
exact-three-call routing gate fail for review. No automatic model promotion occurs.

[e2e/receipt.py](e2e/receipt.py) reads only `call_logs` from the live gateway DB
through a read-only SQLite connection. Its SQL and authorizer permit exactly:
`timestamp`, `path`, `status`, `model`, `reasoning_effort_requested`,
`reasoning_effort_upstream`, `tokens_in`, `tokens_cache_read`, `tokens_reasoning`.
It never discovers schema or reads other tables/columns. Returned rows are scoped
to each arm's wall-clock window, not uniquely attributed conversations. Concurrent
same-model traffic makes qualification inconclusive; the gate requires exactly
three matching successful rows with max/medium upstream effort respectively.
Unknown counters remain null. Cache-read and reasoning counters are not summed
into input totals.

Public receipts contain hashes and allowed sanitized fields, never raw logs,
host paths, emails, credential values or session/request identifiers. Native
container logs supply MCP request-type and HTTP-route counts. Because the upstream
bridge does not log tool names, the receipt distinguishes an inferred `md` route
from a tool name actually observed in framework logs, and separates both from
our client probe outcomes. Skills remain “none observed,” not fabricated calls.
Inputs, schema/oracle, worker/configuration, browser metadata, dependency lock and
deployment files are hashed for reproducibility.

## Evidence classes and remaining host checks

| Class | Available evidence / boundary |
| --- | --- |
| Upstream source read | Release/commit, registry provenance, supported installation/configuration, native filtering/extraction and auth/MCP source. This is the basis for the recipe, not native acceptance. |
| Structural/offline checks | Round-1 evidence stays in `verification.json`. Round-2 failing-first and final output is in `verification-round2.json`; checks cover request configuration, ports/ownership, transport, grader-report binding and receipt redaction. |
| Upstream grader execution | Installed Promptfoo 0.123.1 runs the unchanged assertions on synthetic positive/negative controls. This is actual upstream grader execution, with no new model execution or host installation. |
| Synthetic fixtures | Three authored pages and a frozen exact oracle. Offline positive data is the oracle itself and never described as a provider result. |
| Local host integration | Pending: install/reinstall, Playwright launch, private modes and mapped UID behavior, container startup, protected API, both MCP transports, model extraction, headers/effort, native logs, receipt generation and cleanup/restart. |
| Unchanged upstream tests | Not run in this builder. The upstream MCP socket example informed our probe; the SSE example's stale URL was not relabeled as passed. Docker pytest suites and any broader upstream acceptance remain separate coordinator work. |

The existing coordinator host facts are inputs, not measurements repeated here.
The gateway DB's allowed columns do not include request headers or temperature, so
the receipt cannot independently prove header retention, sampling omission or
exclusive per-session attribution. Those require the gateway owner's bounded
observation; the builder does not access forbidden columns. Container LLM request
controls, WebSocket compatibility, broader crawl quality, real websites, persistent
session behavior, causal token savings and model-currency decisions remain open.

Run the local contracts with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover
-s tests -p test_runtime_worker_crawl4ai.py`, with `TMPDIR` set to the assigned
external scratch directory. Promptfoo 0.123.1 must already be on PATH for the
native grader checks; those checks explicitly skip if it is unavailable. Run
`PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate.py` afterward. The coordinator
owns re-registering changed hashes in the shared evidence manifest; this builder
edits only the recipe and its assigned unit test.
