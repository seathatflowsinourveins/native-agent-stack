# Native workers and optional research routes

This contains native worker recipes and an accepted OmniRoute Astra route for US-equities research. On September 19, 2026, the existing gateway completed one two-sentence Astra evidence task: **HTTP 200, 81 input tokens + 55 output tokens = 136**, with zero reported cached, cache-write or reasoning tokens. [astra-receipt.json](astra-receipt.json) preserves the initial version rejection, interrupted SDK attempt and successful completion separately. Their unreported provider usage remains unknown; 136 is the successful request's total, not the whole repair session's total.

The native worker, other gateway examples and policy fragments below remain prospective unless their dated evidence is explicitly cited. This subtree does not install a scheduler, submit orders, enforce an account budget or change native clients' account/model defaults.

## Evidence and pins

| Route | Recorded result and limit |
| --- | --- |
| Native Codex → OpenAI → `gpt-6-astra` | September 19, 2026 native tool task and separate official companion read-only task passed. This is the preferred worker backend. Current quota and authorization still need checking at dispatch. |
| OmniRoute → Claude OAuth → `claude-opus-5` | September 18 exact-model Messages and native file/shell task passed. Requested route was `claude/claude-opus-5`. Gateway context reported 200K; 1M context, deferred tools, compaction and multi-agent equivalence were not established. |
| OmniRoute → Ollama | Explicit `ollama-local/qwen3.8:27b-mtp-q4_K_M` chat/tool roundtrip passed September 18. Returned model was `qwen3.8:27b-mtp-q4_K_M`. |
| FreeLLMAPI → custom Ollama | Explicit `qwen3.827b-mtp-q4km` chat/tool roundtrip passed September 18. Returned model was `qwen3.8:27b-mtp-q4_K_M`; `X-Routed-Via` identified the custom route. |
| OmniRoute → Codex OAuth → GPT-6 Astra | September 19 completed native Responses stream: requested `cx/gpt-6-astra`, returned `gpt-6-astra`, provider header `cx`, model header `gpt-6-astra`, 136 reported tokens. Simple text fidelity passed; tools, compaction, deferred tools, full context and worker parity remain unproved. FreeLLMAPI → Astra remains unverified. |

Historical route results were inspected in the existing host's sanitized routing records; they were not rerun or copied as raw transcripts. Broader native component evidence is in [the stack evidence manifest](../../../manifests/evidence.json). Neither historical success nor an advertised model list certifies current provider readiness.

| Upstream | Installed/reviewed pin | License and current release check |
| --- | --- | --- |
| [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute/releases/tag/v3.8.50) | npm `omniroute@3.8.50`; source `5458026c216f77a3da68ea49152dc33470cfe2cb` | MIT; latest release lookup September 19 still resolved to v3.8.50, published August 26. |
| [tashfeenahmed/freellmapi](https://github.com/tashfeenahmed/freellmapi/releases/tag/v0.11.0) | Official Windows desktop v0.11.0; source `955e9cf6413314d461d8130f695a81b8c5f246fe` | MIT; latest release lookup September 19 resolved to v0.11.0, published September 16. |
| [openai/codex](https://github.com/openai/codex/releases/tag/rust-v0.155.1) | Native 0.155.1 | Apache-2.0; preserve the user's native configuration and login. |
| [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc/tree/v1.0.6) | Optional official companion 1.0.6; source `db52e28f4d9ded852ab3942cea316258ae4ef346` | Apache-2.0; existing native Codex backend, separate from gateway routing. |

The recorded deployment uses existing Windows gateways reachable from WSL loopback. There is no proposed second Linux gateway installation. For a new host, the native OmniRoute package is `npm install --global --prefix "$TOOLS_PREFIX/omniroute-3.8.50" omniroute@3.8.50`; FreeLLMAPI is the selected official desktop asset from its pinned release. Review upstream setup rather than copying another machine's state or account stores.

## Accepted OmniRoute Astra route

The user completed the gateway's normal interactive Codex authorization. No native
provider credential store was read, imported or copied. The first Responses
attempt then returned HTTP 400 because this OmniRoute release advertised its
bundled Codex client default, **0.149.0**.

Upstream explicitly supports the deployment variable `CODEX_CLIENT_VERSION` and
documents keeping it aligned with the actual installed client. The Windows native
client reported **0.155.0**; the separate Linux native client reported **0.155.1**.
The existing Windows launcher now derives its value from that Windows executable
on each start. This uses the shipped compatibility setting and does not patch
provider checks, install an unshipped release or invent a client version.
Caller-supplied `Version` alone is ineffective here: v3.8.50 overwrites it. The
unshipped `release/v3.8.51` source proposes caller forwarding; it was not installed.
See [upstream deployment-version guidance](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/src/shared/constants/codexClient.ts),
[supported environment lookup](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/open-sse/config/codexClient.ts),
and the portable [launcher fragment](omniroute-codex-version.ps1.example).

Before restart, upstream `/api/monitoring/health` reported zero in-flight, active
and queued requests. The native stop command returned a failure and the listener
became unreachable. Windows then blocked loading the saved PowerShell script.
No execution policy was changed: the existing gateway was restored with the
installed upstream Node `serve --port 20128 --no-open --no-tray --no-recovery`
command, the same private `DATA_DIR` and authentication, loopback binding, and the
derived version. Final native health was **200 / healthy**, with zero active or
queued requests. The startup-fragment change persists for the existing launcher;
running it remains subject to the host's normal script policy.

An initial retry exposed a separate test-client mistake: the official SDK's
`with_raw_response.create(...)` returns `LegacyAPIResponse`, which is not a
context manager. That submitted request ended as gateway HTTP **499**, client
disconnected. Its provider usage was unavailable; gateway zero counters are not
proof that the provider consumed zero tokens. After changing to the official
`with_streaming_response.create(...)` context manager, one additional authorized
request completed in **3.001 seconds** with the exact requested route. No model
fallback or additional unchanged retry occurred.

The exact returned text was:

> The local simulation summarized 6 LEAN order events into 3 distinct orders, and the source-build backtest processed 3,943 points with zero failed data requests. This does not establish paper-trading readiness because no broker connection was made or validated.

For a deliberate replay, use the already installed official SDK environment and
the existing local gateway inference key in `OMNIROUTE_API_KEY`; this is not an
OpenAI provider API key. Choose a new private output directory outside the repo.

```sh
"$WORKER_PYTHON" "$STACK_REPO/blueprints/us-equities/routing/omniroute-astra.py" \
  --base-url http://127.0.0.1:20128/v1 \
  --output-dir "$PRIVATE_RUN/astra-replay"
```

[omniroute-astra.py](omniroute-astra.py) is a portable adaptation of the successful
private script, with the same upstream SDK streaming call and exact
[request](omniroute-astra-request.json). It adds output containment and a route
identity check; those guard changes did not trigger another inference. SDK retries
are disabled. The 60-second SDK timeout is a transport timeout, not a token or
spending cap. Raw events may contain request IDs and must stay private. Requested
model, returned model and gateway headers agree, but are not independent provider
attestation. The two-sentence task validates supplied facts; it did not retrieve
market data or exercise a broker, model tools, native hooks, memory or compaction.

## Native Codex worker default

Use the existing native executable and selected native home. Set `PROJECT_ROOT`, `PROMPT_FILE`, `RESULT_FILE` and `STREAM_FILE` to absolute paths owned by this research run. Do not change `CODEX_HOME` globally or import authentication between Desktop, CLI and gateways.

```sh
codex --version
CODEX_HOME="$NATIVE_CODEX_HOME" codex login status
CODEX_HOME="$NATIVE_CODEX_HOME" timeout --signal=TERM --kill-after=10s 300s \
  codex exec --sandbox read-only -C "$PROJECT_ROOT" --json \
  -o "$RESULT_FILE" - < "$PROMPT_FILE" > "$STREAM_FILE"
```

This preserves the configured model/provider and requests a read-only local shell/filesystem sandbox. That sandbox does not remove mutation authority from inherited MCP tools, hooks or remote services. Before a research dispatch, select an explicit research tool profile with no broker/order capabilities and review inherited hooks. Verify the actual session reports `gpt-6-astra` before attributing its result to Astra; a native default can change. The timeout bounds the local process lifetime, **not provider billing or guaranteed server-side cancellation**. No hooks or trust checks are bypassed. Explicit cancellation belongs to the owning native session or companion job.

The optional upstream companion can start, poll and cancel a bounded task without an outer Claude model turn. `PLUGIN_ROOT` must be the actual installed official plugin directory; retain its normal native environment and selected Codex home:

```sh
node "$PLUGIN_ROOT/scripts/codex-companion.mjs" task --background --fresh --json \
  --cwd "$PROJECT_ROOT" 'Read the selected public research artifact and return its source identifiers, date, and stated units. Do not modify files.'
# Use the actual job ID returned above, never a saved example ID.
node "$PLUGIN_ROOT/scripts/codex-companion.mjs" status "$JOB_ID" --wait \
  --timeout-ms 30000 --poll-interval-ms 1000 --json --cwd "$PROJECT_ROOT"
node "$PLUGIN_ROOT/scripts/codex-companion.mjs" result "$JOB_ID" --json --cwd "$PROJECT_ROOT"
# Only if this owned job needs cancellation:
node "$PLUGIN_ROOT/scripts/codex-companion.mjs" cancel "$JOB_ID" --json --cwd "$PROJECT_ROOT"
```

Retain the disabled automatic stop-review gate. The existing narrow Claude deny rule `Agent(codex:codex-rescue)` prevents the plugin's separate proactive Sonnet agent; the companion's task label `rescue` does not itself indicate that agent ran. These examples do not add or change permission rules.

## Inactive native gateway policy fragments

Every `.example` file is inert. JSON has no environment-variable expansion. Do not copy fragments over whole configurations. Before applying a native endpoint update, use the normal local dashboard/management authentication, inspect the current relevant fields, and merge only the intended change. Management credentials and inference credentials can have different scopes; this blueprint contains neither.

| File | Native surface | Intended scope |
| --- | --- | --- |
| [omniroute-thinking.json.example](omniroute-thinking.json.example) | `PUT /api/settings/thinking-budget` | `mode: passthrough` preserves client reasoning/thinking fields. This is a shared setting: review other clients before applying. |
| [omniroute-affinity.json.example](omniroute-affinity.json.example) | `PATCH /api/settings` | Optional `sessionAffinityTtlMs: 3600000`; the supported field is milliseconds. It helps keep a multi-turn conversation on one connection when account pools are deliberately enabled. This value is proposed, not active. |
| [omniroute-baseline-headers.curl.example](omniroute-baseline-headers.curl.example) | Native curl request headers | Disable compression and gateway response-cache use for this request; skip gateway memory/skills injection. Provider prefix caching remains a different mechanism. |
| [freellmapi-compression.json.example](freellmapi-compression.json.example) | `PUT /api/settings/compression` | `mode: off`; other saved engine settings need not be removed. |
| [freellmapi-cache.json.example](freellmapi-cache.json.example) | `PUT /api/cache/config` | `enabled: false`; this is a shared persisted response-cache setting. |
| [omniroute-qwen-request.json.example](omniroute-qwen-request.json.example) | `POST /v1/chat/completions` | Explicit previously observed local route. No automatic cloud substitution. |
| [freellmapi-qwen-request.json.example](freellmapi-qwen-request.json.example) | `POST /v1/chat/completions` | Explicit previously observed local model ID. |
| [openai-astra-request.json.example](openai-astra-request.json.example) | **Direct official OpenAI Responses API only** | Current cache field example. Requires separately authorized API access; native ChatGPT login is not treated as an API key. Not a proven OmniRoute payload. |

OmniRoute header syntax is documented in its [API reference](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/docs/reference/API_REFERENCE.md); reasoning behavior in [Thinking Budget](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/docs/guides/THINKING_BUDGET.md); affinity in [Codex configuration](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/docs/guides/CODEX-CLI-CONFIGURATION.md). FreeLLMAPI's native update handlers are [settings.ts](https://github.com/tashfeenahmed/freellmapi/blob/v0.11.0/server/src/routes/settings.ts) and [cache.ts](https://github.com/tashfeenahmed/freellmapi/blob/v0.11.0/server/src/routes/cache.ts).

These proposed curl commands assume a separately provisioned private curl authentication config for the selected gateway. Its contents are not supplied, inspected or generated here. Keeping it outside the repository also avoids putting a key in a command argument or public log.

```sh
ROUTING_DIR="$PROJECT_ROOT/blueprints/us-equities/routing"
# Optional local Qwen request: run only when an actual inference check is intended.
curl --fail-with-body --silent --show-error \
  --config "$PRIVATE_OMNIROUTE_CURL_AUTH" \
  --config "$ROUTING_DIR/omniroute-baseline-headers.curl.example" \
  -H 'Content-Type: application/json' \
  --data-binary "@$ROUTING_DIR/omniroute-qwen-request.json.example" \
  http://127.0.0.1:20128/v1/chat/completions \
  -D "$PRIVATE_ROUTE_HEADERS" -o "$PRIVATE_ROUTE_RESPONSE"

# Alternative route; do not chain the two gateways.
curl --fail-with-body --silent --show-error \
  --config "$PRIVATE_FREELLMAPI_CURL_AUTH" \
  -H 'Content-Type: application/json' \
  --data-binary "@$ROUTING_DIR/freellmapi-qwen-request.json.example" \
  http://127.0.0.1:31415/v1/chat/completions \
  -D "$PRIVATE_ROUTE_HEADERS" -o "$PRIVATE_ROUTE_RESPONSE"
```

FreeLLMAPI's compression/cache baseline must already have been selected through its supported settings. Do not assume OmniRoute-specific headers configure FreeLLMAPI. Treat HTTP errors, missing usage, route mismatch and rejected model IDs as failures to investigate, not invitations to change accounts or silently fall back.

For identity checks, retain requested model, returned model, provider route headers, native session model, timestamp and tool-result linkage. OmniRoute reports `X-OmniRoute-Provider`/`X-OmniRoute-Model`; FreeLLMAPI reports `X-Routed-Via`. Its [Claude alias mapper](https://github.com/tashfeenahmed/freellmapi/blob/v0.11.0/server/src/services/anthropic-map.ts) can resolve Claude-looking names to the available local model. No `claude*` compatibility alias is permitted as evidence of real Anthropic access. An application must actually enforce this identity check; a documentation rule alone is not fail-closed software.

## Responses, caching and cost boundaries

OmniRoute accepts native Responses at `/v1/responses`. Its Codex backend also offers a dedicated WebSocket path, but that requires its own Codex OAuth connection. Preserve Responses items, tool-call IDs, opaque reasoning and client compaction behavior. Chat conversion is not evidence of complete native Codex fidelity. The [Codex executor](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/open-sse/executors/codex.ts) strips `max_tokens`, `max_output_tokens` and `prompt_cache_retention`; an output-token cap in a client request is therefore not an enforceable spending ceiling on that backend.

Official GPT-6 Astra uses `prompt_cache_options.ttl: "30m"`; cache writes are charged. Keep uncached input, cache writes, cached reads and output/reasoning categories separate according to the actual API's usage schema. Preserve stable prefixes/tool schemas, and review cache boundary controls before changing them. The direct API example does not certify these fields survive a gateway or apply to a native subscription invoice. [Official prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)

`gpt-6-astra` does not support reasoning effort `none`. Its supported mid-conversation `configuration_update` mechanism can preserve a stable prefix when changing effort, subject to documented compatibility limits. It is not enabled by this blueprint or assumed supported by OmniRoute. [Official Astra guidance](https://developers.openai.com/api/docs/guides/latest-model)

Gateway response caching, provider prefix caching and artifact compression have different behavior. For market research, preserve timestamps, source revisions, filing periods, units, signs, decimal precision and citations before any transformation. Keep response caching and lossy prompt rewriting off for the fidelity baseline. Context Mode/RTK estimates and upstream marketing reduction ranges are not net provider savings. Measure named artifacts with a named tokenizer separately from actual per-request/worker usage, including failures and retries.

## Bounded research queue contract

The following is a proposed operational contract, not a claimed installed scheduler:

1. The coordinator submits a concrete read-only research task with source scope, as-of time, required result schema, owner, deadline and cancellation handle. Limit the queue and active workers explicitly in the chosen native scheduler; a suggested initial maximum is three workers, subject to the account's actual capacity.
2. Workers return source-linked evidence and uncertainty. Use deterministic code for financial arithmetic. Reject stale or mismatched periods/units before synthesis. Keep untrusted retrieved content separate from task instructions.
3. Preserve task states (`queued`, `running`, `completed`, `failed`, `cancelled`) and distinguish process timeout from confirmed upstream cancellation. Stop new dispatch after unchanged quota/authentication failures; do not retry across accounts automatically.
4. Retain per-worker provider usage and exact model identity. Cached input and reasoning output can be subsets of larger counters; avoid double counting. Shared subscription limits are not controlled by a per-process worker cap or timeout.
5. Results go to a reviewable research artifact. Broker credentials, order endpoints, account transfers and unattended trading actions are outside this queue. No gateway plugin, A2A skill or tool catalog is allowed to expand that boundary implicitly.

OmniRoute's [A2A interface](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/docs/frameworks/A2A-SERVER.md) is disabled by default and documents a five-minute task TTL. Its cloud-agent APIs require management authentication. Neither replaces a durable research queue or proves native Codex worker orchestration is configured here.

## Verification performed for this change

The original model-free check made exactly one anonymous GET to each supported health endpoint: OmniRoute `/api/health` and FreeLLMAPI `/readyz`. Both returned HTTP 200 on September 19, 2026. [That receipt](health-receipt.json) retains its original scope. The later Astra resolution above separately records actual model requests, the native version-setting change, restart failures and recovery, and the successful Responses stream; it does not rewrite the earlier check as inference.

The remaining checks are repository validation, example parsing, whitespace and privacy scans. A static example that parses is not a new gateway or native-worker E2E. New deployments require normal upstream installation, account/project consent and one appropriately scoped acceptance task before claiming readiness.
