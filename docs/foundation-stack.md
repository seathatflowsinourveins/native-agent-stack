# Portable native foundation

This is the selected memory, retrieval and token-efficiency setup for native Codex and Claude, with an optional OmniRoute gateway. Start with [adoption](../adoption/README.md), retain the [component pins](../manifests/stack.json), and use the [owned lifecycle recipes](../adoption/lifecycle.md). A new PC collects its own results; importing this catalog does not qualify its accounts, GPU, hooks or client sessions. This is a dated selection, not a claim that the whole LLM ecosystem has a final best stack.

The foundation wave's [acceptance receipt](../evidence/receipts/foundation-native-20260920.json) is the result authority. At this guide's drafting checkpoint, native/client checks and exact-dedup acceptance were still being assembled. The scoped memory/RAG checks and fresh Serena Python/CJS contexts passed; the isolated Linux OmniRoute installation/start/restart/plaintext-restore/stop checks also passed without provider calls. Gateway baseline counters were zero for compression and cache. RTK and lite previews failed required semantic checks. A native Codex gateway request with a provider-prefixed model returned 400; subsequent gateway provider probes returned quota 429 for Codex and Claude. Those failures remain evidence. Installation, local preview, model routing and an actual successful native task are separate stages.

## Select one useful lane

| Need | Selected repositories and pins | Default scope / acceptance |
| --- | --- | --- |
| Durable decisions and continuity | [ai-memory 2.3.2](https://github.com/akitaonrails/ai-memory/releases/tag/v2.3.2) | One explicitly scoped shared store; fresh native hook events plus exact page retrieval and owned restore. Routine capture is not a complete transcript. |
| Find documentation | [QMD 2.8.3](https://github.com/tobi/qmd/releases/tag/v2.8.3) | Named BM25 index and selected Markdown collection; search then read the returned source. No embedding model is needed for this lane. |
| Conceptual code search | [SocratiCode 1.14.0](https://github.com/giancarloerra/SocratiCode), [Qdrant 1.19.1](https://github.com/qdrant/qdrant/releases/tag/v1.19.1), [vLLM 0.25.0](https://github.com/vllm-project/vllm/releases/tag/v0.25.0) | One project, local embeddings and persistent vectors; exact returned source plus automatic add/change/delete observation. |
| Symbols and references | [Serena](https://github.com/oraios/serena/tree/c6fbd1c5932df2494ffa0020af5a9fbe80b82143) | Enable Python and TypeScript where used; test each actual extension/language. A Bash-only server does not establish Python/TypeScript support. |
| Reduce selected tool context | [RTK](https://github.com/rtk-ai/rtk/releases/tag/v0.49.0), [Context Mode](https://github.com/mksglu/context-mode), [jCodeMunch](https://github.com/jgravelle/jcodemunch-mcp/releases/tag/v1.108.319), [Headroom](https://github.com/chopratejas/headroom) | Choose the smallest representation satisfying the task; preserve full output/recovery and signed comparisons. These do not automatically intercept every client call. |
| Optional gateway | [OmniRoute 3.8.50](https://github.com/diegosouzapw/OmniRoute/releases/tag/v3.8.50) | Separate process-level route and scoped inference key. Local lifecycle can pass while provider acceptance remains unavailable. |

Native client sign-ins, generation models, caching, compaction and existing project MCP remain the default. OmniRoute conversational memory is a separate optional injection store; it does not replace ai-memory or the code index. Do not chain competing gateways or activate every catalog alternative.

## Install into explicit owned locations

Use native Node 24, Python 3.13, uv, Git and the chosen release tools. Set absolute paths for `STACK_HOME`, `PROJECT_ROOT`, `PRIVATE_RUN_DIR` and `MCPORTER_CONFIG`; keep private logs/configuration outside Git. Read only the selected recipe. Shell variables do not expand inside JSON, TOML or systemd units.

For release archives such as ai-memory, RTK and Qdrant, use the [upstream archive procedure](../recipes/README.md#official-release-archives), selecting the actual OS/architecture asset and checking its published digest. For example, discover ai-memory's assets with:

```sh
gh release view v2.3.2 --repo akitaonrails/ai-memory --json tagName,assets
```

For npm/uv tools, retain versioned prefixes, package metadata and the installation output. The following is a clean, selected QMD install; it stops if the prefix already exists:

```sh
(
  set -eu
  : "${STACK_HOME:?Set an absolute private stack location}"
  case "$STACK_HOME" in /*) ;; *) exit 2 ;; esac
  prefix="$STACK_HOME/tools/qmd-2.8.3"
  test ! -e "$prefix"
  npm install --global --prefix "$prefix" @tobilu/qmd@2.8.3
  "$prefix/bin/qmd" --version
)
```

The [component installation table](../recipes/README.md#component-catalog-install-and-check) gives the other pinned commands, including isolated SocratiCode npm installation, Serena's pinned `uvx` source, and the vLLM virtual environment. Keep supported package postinstall behavior; a dependency installation or version result alone is not a working server check.

## Memory and lexical retrieval

Initialize ai-memory with `ai-memory init`, then apply the selected fields from [its configuration example](../examples/ai-memory-config.toml.example) before starting capture: embeddings `none`, no startup backfill, no assistant capture, and no session-end consolidation. Leave an unused LLM provider unset; literal `llm_provider="none"` is not valid. Merge the [project marker](../examples/ai-memory-project.toml.example) with explicit workspace/project scope. Keep one data/config location shared by the server and hooks.

```sh
ai-memory serve --transport http --bind 127.0.0.1:49374 \
  --workspace local --project native-agent-stack
```

Register the existing service using either the project configuration examples or upstream installers, avoiding duplicate server names:

```sh
ai-memory install-mcp --client codex --apply
ai-memory install-mcp --client claude-code --apply
ai-memory install-hooks --agent codex \
  --server-url http://127.0.0.1:49374 --capture-mode allowlist --apply
ai-memory install-hooks --agent claude-code \
  --server-url http://127.0.0.1:49374 --capture-mode allowlist --no-capture-prompts --apply
ai-memory install-instructions --target AGENTS.md
```

Run each installer in its intended native configuration home and preserve non-managed content. Hooks are global additions gated by the project marker. Codex at this pin has no corresponding prompt-capture disable flag; do not call it zero capture. Review a fresh session's actual captured event metadata and project/session identity. Static MCP callers pass both workspace and project; session-aware clients may derive them. For a deliberate memory fixture, use the [native write/search/read sequence](../recipes/README.md#project-memory), then the [owned backup/empty-target restore](../adoption/lifecycle.md#stateful-persistence-and-recovery). Do not write routine activity as durable pages.

For documentation, add only the chosen collection to a fresh named index, then use BM25 and retrieve the returned URI:

```sh
qmd --index "$QMD_INDEX" collection add "$PROJECT_ROOT/docs" \
  --name "$QMD_COLLECTION" --mask '**/*.md'
qmd --index "$QMD_INDEX" update
qmd --index "$QMD_INDEX" search 'native memory scope' \
  -c "$QMD_COLLECTION" -n 3 --format json
qmd --index "$QMD_INDEX" get "$RETURNED_QMD_URI"
qmd --index "$QMD_INDEX" status
```

Reopen the same index and repeat an exact source lookup to test persistence. Zero vectors/pending embeddings are expected in BM25 mode. `embed`, semantic `query` and `vsearch` are separate model-enabled choices. After changing documents run `update`; removal of an owned test collection uses `qmd --index "$QMD_INDEX" collection remove "$QMD_COLLECTION"` and does not authorize deleting other indices.

## Local semantic code search and exact symbols

Use [local semantic setup](../recipes/README.md#local-semantic-code-search) and the [Qdrant](../examples/qdrant.yaml.example), [MCPorter](../examples/mcporter.json.example) and native client examples. The selected embedding model is [Nemotron-3-Embed-1B-BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16), revision `c0c9fea93ea424587517f2c59e20db9f1d6bf615`, with 2048 dimensions. Model acquisition is an actual download; local vLLM needs a compatible GPU. Its 0.29.0 WSL startup failed with unavailable UVA in the recorded acceptance, so the working 0.25.0 remains a compatibility pin, not the newest release.

```sh
qdrant --config-path "$QDRANT_CONFIG" --disable-telemetry
# Run the embedding server in a second terminal or its reviewed user unit.
vllm serve "$MODEL_DIRECTORY" \
  --served-model-name nvidia/Nemotron-3-Embed-1B-BF16 \
  --host 127.0.0.1 --port 8231 --max-model-len 4096 --max-num-seqs 4 \
  --gpu-memory-utilization 0.16 --enforce-eager --no-enable-log-requests
```

SocratiCode's supported `lmstudio` adapter points to `http://127.0.0.1:8231/v1` here; this does not require LM Studio. Use `QDRANT_MODE=external`, the local Qdrant URL, the exact model/dimensions, and `query: ` / `passage: ` prefixes. Preserve trailing spaces. Each MCP entry has the selected absolute project cwd; exclude credentials, transcripts, dependencies and unrelated projects. QMD remains the Markdown lane.

```sh
mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_health \
  --args '{}' --output text --no-oauth
INDEX_ARGS=$(python3 -c 'import json,sys; print(json.dumps({"projectPath":sys.argv[1]}))' "$PROJECT_ROOT")
mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_index \
  --args "$INDEX_ARGS" --output text --no-oauth
mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_status \
  --args "$INDEX_ARGS" --output text --no-oauth
```

Indexing is asynchronous: wait for completion before `codebase_search`. Retain a finite 2048-value embedding, the exact returned source match, and scoped add/change/delete watcher evidence. Restart owned services and retrieve again; use the existing [Qdrant restore receipt](../blueprints/us-equities/state-recovery/qdrant/receipt.json) as a method reference, not the new host's result. Close only owned stdio clients; MCPorter may serve other active tasks.

Serena is the exact-symbol lane. On a project without a Serena configuration, its upstream setup accepts repeated language flags:

```sh
uvx --from git+https://github.com/oraios/serena@c6fbd1c5932df2494ffa0020af5a9fbe80b82143 \
  serena project create --language python --language typescript "$PROJECT_ROOT"
uvx --from git+https://github.com/oraios/serena@c6fbd1c5932df2494ffa0020af5a9fbe80b82143 \
  serena start-mcp-server --context codex --project "$PROJECT_ROOT"
```

For an existing project merge the required `language_servers` entries into `.serena/project.yml` rather than overwriting its exclusions/settings. The observed project uses `[bash, python, typescript]`; TypeScript handles JavaScript/CJS. Normal pinned upstream activation installed TypeScript 5.9.3 and typescript-language-server 5.1.3 in Serena's resource directory; Python uses pyright 1.1.403 through its managed `uvx` command. Use `--context claude-code` for Claude. Test a known Python symbol and a known TypeScript/JavaScript symbol with `find_symbol`, then compare returned lines to source. Check `.cjs` separately if the project uses it; successful `.ts` support does not prove every JavaScript extension. This wave's fresh contexts returned exact Python/CJS bodies and incoming references; callees inside a function are not incoming references. The [MCP inspection example](../recipes/README.md#native-project-mcp) shows direct `tools/call` without a generation-model request. A fresh native server is necessary after configuration changes; existing Desktop connections do not automatically reload.

## Native token tools and actual client acceptance

Keep the [native token practice](token-practice.md), [focused jCodeMunch recipe](../recipes/README.md#focused-jcodemunch-retrieval), [Headroom recipe](../recipes/README.md#headroom-native-compression-and-recovery) and [Context Mode repair](../recipes/README.md#retained-context-mode) as the detailed command authority. Use the existing upstream plugins/hooks and one fitting context lane. Do not pre-load the grand catalog into each task.

```sh
rtk gain --help
rtk gain
headroom savings --json
mcporter --config "$MCPORTER_CONFIG" call context-mode.ctx_stats \
  --args '{}' --output text --no-oauth
```

jCodeMunch uses upstream `order` with `action:"get_session_stats"`; capture before/after in the same native MCP process. Retrieve an exact indexed symbol and compare its bytes with a focused source read, including search/source envelopes and cold-index overhead. Headroom requires compression plus complete retrieval when the task needs original information. Its 0.37.0 field named lifetime has a 30-day report-window limit. Do not add isolated-fixture ledger increments to the working-host ledger.

A real native acceptance starts a bounded task in each already signed-in client, uses a configured project read and exact source retrieval, validates the answer independently, and resumes that same session once when supported. Keep the established native policy; do not change accounts, providers or global trust just for a check. Save full private returned streams, argv, exit, session identity and all successful/failed tool calls. Preserve failed attempts in usage totals. Compare required facts before counting a representation as useful. The [existing native client recipe](../recipes/README.md#native-client-acceptance) and [previous final receipt](../evidence/receipts/native-token-stack-final-20260920.json) establish the method, not a new execution.

## Optional OmniRoute installation and bounded gateway acceptance

OmniRoute 3.8.50 requires Node `>=22.22.2 <23` or `>=24 <27`. Install with upstream npm into a fresh prefix, then use a separate private `DATA_DIR`; preserve actual provider connections and credentials in their own native stores.

```sh
(
  set -eu
  : "${OMNIROUTE_PREFIX:?Set a new absolute owned prefix}"
  case "$OMNIROUTE_PREFIX" in /*) ;; *) exit 2 ;; esac
  test ! -e "$OMNIROUTE_PREFIX"
  npm install --global --prefix "$OMNIROUTE_PREFIX" --include=optional omniroute@3.8.50
  "$OMNIROUTE_PREFIX/bin/omniroute" --version
)
DATA_DIR="$OMNIROUTE_DATA" OMNIROUTE_SERVER_HOST=127.0.0.1 \
  "$OMNIROUTE_PREFIX/bin/omniroute" serve --port "$OMNIROUTE_PORT" --no-open --no-tray --daemon
DATA_DIR="$OMNIROUTE_DATA" "$OMNIROUTE_PREFIX/bin/omniroute" status
curl --fail --silent --show-error "$OMNIROUTE_URL/api/health"
```

Use a root URL without `/v1`, an unused loopback port, and private stable secrets from the [upstream setup](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/docs/guides/SETUP_GUIDE.md). The server otherwise binds `0.0.0.0`. Node/package startup must also work under the host's native executable lookup; the recorded Windows repair restored process-local executable extensions after an invalid PATHEXT. Do not generalize that repair to unrelated hosts.

The released generated command is `omniroute api compression post-api-compression-preview --body @preview.json`; generic `api get PATH`, `status --json`, and `doctor --json` are unsupported. A returned JSON error can accompany exit 0. The compression CLI's MCP route returned 503 when MCP was disabled. Do not enable global MCP to read counters. The legacy compression settings handler rejects the CLI machine credential; the supported dashboard `POST /api/auth/login` with the existing private password creates an `auth_token` cookie accepted by the settings API. Keep it only in a private HTTP session/cookie jar.

Authenticated management operations are:

| Operation | Exact endpoint / body |
| --- | --- |
| Preserve baseline settings | `GET /api/settings/compression` and `GET /api/keys`; retain sanitized policy plus private rollback values. |
| Create selected inference key | `POST /api/keys` with name, `scopes:["self:usage"]`, and explicit `allowedConnections` UUIDs; retain returned secret privately. |
| Constrain that key before use | `PATCH /api/keys/{id}` with `modelAccessMode:"restricted"`, exact `allowedModels`/connections, `compressionEnabled` and `cacheDefaultMode:"bypass"` for compression-only comparison. |
| Preview without global changes | `POST /api/compression/preview` with `messages`, explicit engine and required facts; see below. |
| Explicit global change | `PUT /api/settings/compression`; supplied top-level keys are partial updates, supplied nested objects replace their stored row. Read back and retain exact rollback values. |

Per-key compression is opt-out only. A true key cannot override globally disabled compression; a false key does not disable independent reactive compaction when global compression is enabled. Therefore a global change is not wholly isolated to the new key. Preview first; use an isolated instance or restore-before-baseline for a strict comparison. Memory injection, response cache, SLM compression and remote embedding selection are separate optional features.

RTK's actual preview shrank 447→14 tokens but dropped a required success sentinel; lite's 447→444 damaged underscore/case fidelity. Both fail the information contract. The source-supported next candidate uses only exact session dedup:

```json
{
  "engineId": "session-dedup",
  "messages": [{"role": "tool", "content": "<unchanged public fixture>"}],
  "fuzzyDedup": {"enabled": false},
  "fidelityGate": {"enabled": true}
}
```

Exact dedup keeps the first occurrence and substitutes later equal suffix blocks of at least three lines/80 characters. A single message with unique final facts can correctly produce no saving. A separate two-copy history fixture tests the eligible repeated-block case; its result must not replace the single-message baseline. Retain all sentinels, the intact first occurrence, `originalTokens`, `compressedTokens`, validation, warnings and fallback fields. Calculate the signed difference yourself because preview `tokensSaved` clamps negative values to zero. Legacy direct RTK/lite preview can return damaged text with failed validation; validation is not automatic rollback. Preview is not provider answer-fidelity or billing evidence.

For Claude, the documented process route is `ANTHROPIC_BASE_URL="$OMNIROUTE_URL" ANTHROPIC_AUTH_TOKEN="$OMNIROUTE_API_KEY" claude --model "$EXACT_CLAUDE_MODEL"`. Keep the native configuration home and model identity. OmniRoute's generic Claude launcher forces a 190000-token compaction window, so it does not preserve an existing larger native setting.

For Codex, `omniroute launch-codex --remote "$OMNIROUTE_URL" -- ...` injects a Responses provider. Its token precedence is explicit `--api-key`, active context credential, then environment; an active context can shadow a trial environment key. Use a private in-memory launch or the launcher's [documented direct provider overrides](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.50/bin/cli/commands/launch-codex.mjs) without printing credentials. Native passthrough currently retains the raw request model: `codex/gpt-6-astra` routed to Codex but reached the backend with the prefix and failed 400. The supported prepared correction is a single router alias, authenticated `PUT /api/models/alias` with `{"alias":"gpt-6-astra","model":"codex/gpt-6-astra"}`, then native `exec --model gpt-6-astra` at the same explicit effort. Preserve any prior alias, confirm readback and constrain the trial key. This is distinct from the model-deprecation settings map. Alias writes can sync to cloud when a cloud URL is configured; the observed server had no configured cloud URL.

Actual later provider probes returned Codex and Claude quota 429, so do not claim a passing gateway native task or retry the unchanged limits. The 3.8.50 executor also caps unknown-model reasoning effort at xhigh, including passthrough. It cannot certify preservation of Astra max/ultra. Native Codex passthrough skips router compression. Exact model, effort, tool behavior and continuation need actual accepted results once capacity is available; do not substitute a cheaper model to manufacture a pass.

For owned lifecycle, preserve the same DATA_DIR/secrets through restart. Upstream `backup create --name NAME --encrypt --key-file FILE` creates encrypted backups, but the released native restore command only recognizes plaintext filenames and can print completion without restoring encrypted files. This wave independently decrypted/checked the encrypted backup and separately accepted a plaintext native restore; do not claim native encrypted restore passed. Before `stop`, verify `$OMNIROUTE_DATA/server/.pid` belongs to this launch: absent PID state can trigger a fallback targeting port 20128. `update --apply` installs into npm's default global prefix and is unsuitable for this isolated prefix. After closing only the owned process, `npm uninstall --global --prefix "$OMNIROUTE_PREFIX" omniroute` retires the package while preserving separate data/evidence. That is a retirement recipe, not an executed uninstall in this wave: the package remains installed, the owned acceptance process is stopped, and its final data/receipts are archived. Never erase working router counters as cleanup.

## Reconcile returned results with observation

| Evidence | Native source and exact scope | What it establishes |
| --- | --- | --- |
| Client usage | Complete Codex/Claude stream and final native session usage, including failed attempts/resume | Actual returned consumption; cached tokens are a subset/category, not an additional saving to add. |
| Hook/MCP execution | Exact session and writer metadata in ai-memory/Context Mode and matching observer events | Those calls/events were observed; opaque wrapper events do not identify an inner tool by themselves. |
| Local RAG | Qdrant collection/index payload and embedding response from the selected local endpoints | Real retrieval and local embedding work, not avoided provider tokens. |
| RTK/Context Mode/Headroom/jCodeMunch | Direct upstream before/after results with process, ledger and window | Native estimates within that scope; snapshots and overlapping reductions are not additive. |
| Gateway usage | Authenticated `GET /api/usage/analytics?range=all&apiKeyIds=<trial-key-id>` | All retained raw/rolled-up gateway usage for that key, subject to retention; not final provider billing. |
| Gateway compression | `GET /api/analytics/compression?since=all` | Persisted saving rows plus `totalSkipped`/`bySkipReason`, validation fallbacks and `realUsage`; no per-key filter. `period` is ignored by this handler. |
| Gateway cache | `GET /api/cache`, field `semanticCache` | SQLite hits/misses/tokensSaved. `/api/cache/stats` supplies only in-memory LRU statistics. |

Join observer events to the exact returned session/writer and a bounded interval. Compare successful calls and every provider response; leave unmatched startup events explicitly unattributed. A live service or increasing global counter is not independent proof of this task. Keep raw streams, request/response bodies, identifiers and hashes private; publish only the scoped facts and limitations. The [observability guide](../observability/README.md) documents existing native exporters and query methods.

Report exact artifact comparisons as original versus complete returned representation under the same tokenizer and required-fact check. Add cold setup, schemas and recovery overhead where relevant. Keep provider consumption separate from estimates and per-tool cache subsets. Save negative/no-op cases. The [lifetime reporter](../tools/token-report/README.md) retains these categories; refresh its native inputs after a meaningful accepted change, without replaying model tasks on every future session.
