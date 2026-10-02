# ai-memory v2.5.2 adapter

`build()` returns `name="ai-memory"`, `needs_llm=False`. It uses the native
server's zero chat-LLM defaults with **`AI_MEMORY_EMBEDDING_PROVIDER=local`**.
`build_llm()` returns `name="ai-memory-llm"`, `needs_llm=True`: the same local
encoder plus the supplied chat route and a synchronous, default single-page
`memory_consolidate` call after each nonempty session. Neither builder answers
the benchmark question. Retrieved title/snippets go to the common answerer.

Pin: [akitaonrails/ai-memory v2.5.2](https://github.com/akitaonrails/ai-memory/releases/tag/v2.5.2),
annotated tag `af8c6820bbbcca0b8d3604d7b2d59c0e0263ea85`, resolving to commit
[`7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83`](https://github.com/akitaonrails/ai-memory/commit/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83).
The module imports the fixed interface from `h2h.types`, uses only the Python
standard library and `httpx`, and has no import-time process or network activity.

## Reference implementations read first

1. Official [evals/README.md](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/README.md)
   and its retrieval implementation: take the hook event/body shapes, chronological
   replay, and unchanged `[session date: …]` prefix from
   [ingest.rs lines 68–130](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L68-L130);
   take synchronous `/hook/batch` and acknowledgement handling from
   [lines 159–187](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L159-L187).
   Take stateless HTTP `tools/call`, Accept header, JSON/SSE handling, title/snippet
   output, and provenance from
   [query.rs lines 118–191](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/query.rs#L118-L191)
   and [lines 210–243](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/query.rs#L210-L243).
   Take native `serve` and copying an existing local model into a new store from
   [server.rs lines 83–108](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/server.rs#L83-L108).
2. Vectorize's adapter was **not found in the complete tree (`truncated=false`)
   or provider registry** at
   [`vectorize-io/agent-memory-benchmark@f618ed7b1f0eb9cad7b42e876f91a42f0eadb150`](https://github.com/vectorize-io/agent-memory-benchmark/tree/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150).
   [Provider registry lines 1–35](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/__init__.py#L1-L35)
   contains no ai-memory entry; no provider implementation was borrowed.
3. Read [docs/benchmarks/README.md lines 14–26](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/benchmarks/README.md#L14-L26),
   [September local report lines 1–19](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/benchmarks/longmemeval-s-2026-09-01-local.md#L1-L19),
   and [R2 report lines 40–63](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/benchmarks/retrieval-ab-r2.md#L40-L63).
   Published local `hit@5=0.815` is a 2.4 release-candidate result at
   `79fea4009e74cf83561c6e2170dccef80360c079` (470 scored, 30 abstentions excluded),
   not a v2.5.2 result or a LongMemEval official-judge answer score. No published
   number is used as acceptance evidence for this adapter.

## Installation and lifecycle

The v2.5.2 [release installation section](https://github.com/akitaonrails/ai-memory/releases/tag/v2.5.2)
quotes:

```sh
cargo install --locked --git https://github.com/akitaonrails/ai-memory --tag v2.5.2
```

The source of that exact release recipe is
[release.yml lines 552–554](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/.github/workflows/release.yml#L552-L554):
`cargo install --locked --git https://github.com/akitaonrails/ai-memory --tag ${GITHUB_REF_NAME}`.
The coordinator installs a **native** binary with the default local-embeddings
feature; the source builder does not install it or launch a server.

`start(workdir, llm, embed)` requires `H2H_PORT`, checks the binary with
`ai-memory --version`, rejects anything except `ai-memory 2.5.2`, creates a
private child data directory under `workdir`, and launches:

```sh
ai-memory serve --transport http --bind 127.0.0.1:<H2H_PORT> --data-dir <private-directory>
```

Every command/parameter above comes from the pinned native interface:

| Used item | Quoted upstream definition |
| --- | --- |
| `ai-memory --version` | [cli.rs lines 9–11](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/cli.rs#L9-L11): `#[command(name = "ai-memory", version, about, long_about = None)]`. |
| `--data-dir` | [cli.rs lines 13–18](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/cli.rs#L13-L18): “Override the data directory”, `#[arg(long, global = true)]`. |
| `serve --transport http --bind` | [cli.rs lines 2850–2856](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/cli.rs#L2850-L2856): “Transport to expose the MCP server on”; “Bind address for `--transport http`”. The official [eval launcher lines 100–108](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/server.rs#L100-L108) uses these exact arguments. |
| Stateless HTTP | [cli.rs lines 2913–2922](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/cli.rs#L2913-L2922): “Off by default — the HTTP transport is stateless and returns plain JSON”. No `--http-stateful`, initialization exchange, or session header is added. |
| `GET /healthz` readiness | [serve.rs lines 2710–2714](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/commands/serve.rs#L2710-L2714): `"/healthz"`, `get(|| async { ... { "status": "ok" } ... })`. |
| No machine bearer on loopback | [cli.rs lines 2857–2862](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/cli.rs#L2857-L2862): unauthenticated override is “Unnecessary for loopback binds”. The adapter binds only `127.0.0.1`. |

The process environment inherits only ordinary execution settings (`PATH`,
locale, time zone, and Windows executable settings). Ambient ai-memory
configuration, provider credentials, proxy settings, and server URLs are
excluded. Config normally loads from `<data_dir>/config.toml`, which is absent
in each new private directory; see
[config.rs lines 1608–1628](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/config.rs#L1608-L1628):
“defaults → file → env → CLI” and `probe_data_dir.join("config.toml")`.
The adapter writes no key or configuration file.

`reset(namespace)` first stops and reaps **only its owned child**, closes its
HTTP client, clears session attribution, then starts the same documented server
on the same supplied port with a **new private data directory**. Even resetting
the same namespace creates a new store. Each hook/query also names workspace
`longmemeval` and a safe UUID-derived question project. The previous wiki, SQLite,
raw data, `_global` preferences, and handoffs cannot be reached by the new
server. A caller cannot ingest/query another namespace without resetting.
Only the three immutable local-model files listed in
[local-embeddings.md lines 65–82](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/local-embeddings.md#L65-L82)
are copied from the preceding store, following the official eval launcher's
model seeding pattern. Models are upstream checksum-verified. No old memory,
config, or log file is copied.

`stop()` terminates/reaps only the owned child and closes the client; it is
idempotent. Stores remain under `workdir` for inspection; the coordinator can
remove that private experiment directory afterward. A child that cannot be
reaped prevents launching its replacement. Readiness has a 600-second bound
for the initial model download; the HTTP request timeout is 960 seconds.
Upstream's default per-completion deadline is **300 seconds**, defined at
[ai-memory-llm/src/lib.rs lines 35–39](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-llm/src/lib.rs#L35-L39).
These are adapter lifecycle/request deadlines, not server memory settings.

## Conversation ingestion

The adapter preserves the caller's time-ordered sessions and turn order. It
uses `POST /hook/batch` with **one item at a time**:

```json
[
  {
    "url": "/hook?event=user-prompt-submit&agent=claude-code&workspace=longmemeval&project=<question-project>&session_id=<original-id>",
    "body": {
      "session_id": "<original-id>",
      "cwd": "<private-store>/conversation",
      "hook_event_name": "UserPromptSubmit",
      "prompt": "[session date: <dataset date unchanged>] <user content>"
    }
  }
]
```

| Used endpoint/parameter | Quoted upstream source |
| --- | --- |
| `POST /hook/batch`, array of `{url, body}` | [router.rs lines 710–721](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-hooks/src/router.rs#L710-L721): “same `{url, body}` pair a single `POST /hook` would carry”; “only the query is read here”. [Route registration line 610](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-hooks/src/router.rs#L610) names the POST handler. |
| `event`, `agent=claude-code`, `workspace`, `project`, query/body `session_id`, `cwd` | [eval ingest.rs lines 71–89](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L71-L89): `/hook?event={event}&agent=claude-code&workspace=...&project=...&session_id=...`, body `{"session_id": session_id, "cwd": cwd}`. Dynamic values are URL-encoded. |
| `session-start`, `hook_event_name=SessionStart`, `source=startup` | [eval ingest.rs lines 92–99](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L92-L99): `push("session-start", ..., {"hook_event_name": "SessionStart", "source": "startup"})`. |
| `user-prompt-submit`, `hook_event_name=UserPromptSubmit`, `prompt` and date prefix | [eval ingest.rs lines 100–108](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L100-L108): `"prompt": format!("[session date: {date}] {}", turn.content)`. |
| Assistant `stop`, `hook_event_name=Stop` | [eval ingest.rs lines 110–119](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L110-L119): `push("stop", ..., {"hook_event_name": "Stop", ...})`. The opt-in marker and capture flag are omitted; see defaults below. |
| `session-end`, `hook_event_name=SessionEnd`, `reason=exit` | [eval ingest.rs lines 125–129](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L125-L129): `push("session-end", ..., {"hook_event_name": "SessionEnd", "reason": "exit"})`. |
| `accepted`, optional `accepted_indices`, optional `failed_index` | [router.rs lines 724–740](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-hooks/src/router.rs#L724-L740): “Contiguous leading prefix committed, oldest-first”; indexed acknowledgements name committed items and failed processing. Malformed acknowledgements or processing failures raise; zero accepted retries before the next event, bounded to 60 attempts with the official [500-ms interval](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L181-L187). |

Singleton batches keep subsequent events from overtaking a rate-limited event;
batch side effects are complete before acknowledgement, unlike `/hook`'s
asynchronous `202`: [router.rs lines 798–803](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-hooks/src/router.rs#L798-L803)
quotes “processed INLINE” and “side effects ... stay inside the response window”.
This changes delivery granularity, not a memory setting. Unknown roles and
duplicate native IDs are rejected before replay. The adapter never imports
local agent histories or invokes hooks installed on this host.

**Default assistant capture is off.**
[config.rs lines 384–391](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/config.rs#L384-L391)
states “when off the marker is stripped and the Stop stays empty”; default
`capture_assistant: false` is at
[lines 958–965](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/config.rs#L958-L965).
Consequently both builders ingest user text and replay assistant Stop metadata;
**assistant text cannot enter memory through this interface with defaults**.
This limitation is also returned in `IngestStats.notes`. Assistant text is never
relabelled as user text to bypass it. The adapter sends user prompts intact and
leaves sanitization/truncation to the native system.

## Recall and LLM consolidation

`retrieve` sends `POST /mcp`, header `Accept: application/json, text/event-stream`,
and this stateless JSON-RPC request, exactly following
[eval query.rs lines 118–137](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/query.rs#L118-L137):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "memory_query",
    "arguments": {
      "query": "<question unchanged>",
      "workspace": "longmemeval",
      "project": "<question-project>",
      "limit": 5
    }
  }
}
```

IDs increment per adapter instance. The only recall arguments are documented
in [QueryArgs lines 564–580](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-mcp/src/server.rs#L564-L580):
`query`, `limit` (“default 10, max 100”), and explicit `workspace`/`project`
(“Static MCP clients must pass both”). `limit=k` is the common harness's request;
the adapter rejects values outside 1–100, matching the native
[clamp at line 2530](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-mcp/src/server.rs#L2530).
JSON and SSE text responses are decoded as in
[eval query.rs lines 153–191](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/query.rs#L153-L191);
the adapter checks the requested ID and raises on HTTP, JSON-RPC, or tool errors.

Return `hits`, then `raw_hits`, preserving native order and exact title/snippet
text (including HTML marks), at most `k` records. This is the official eval's
[flattening order at lines 210–237](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/query.rs#L210-L237).
The `Retrieved.text` format is `title + "\n" + snippet`. Fields are defined in
[PageHit lines 778–788](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-store/src/reader.rs#L778-L788)
and [ObservationHit lines 946–958](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-store/src/reader.rs#L946-L958):
`path`, `title`, `snippet`, `rank`, and raw `session_id`. `Retrieved.score`
preserves the reported `rank` (**lower is better**), without sorting again.
Page `sessions/<uuid>.md` and raw session UUIDs map back to original dataset IDs;
other pages have empty provenance. The native UUID/UUIDv5-OID mapping is
[ids.rs lines 91–95](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-core/src/ids.rs#L91-L95)
and is mirrored by [eval ingest.rs lines 41–47](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L41-L47).
No follow-up full-page reads, reranking, or system-generated answer are requested.
The new private store contains no supplemental `_global` preference context;
that surface is described at
[server.rs lines 2512–2519](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-mcp/src/server.rs#L2512-L2519).

`question_date` is not passed as `as_of`. Native `as_of` filters the memory
store's **ingestion/version timeline**, requires an ISO-8601 instant, and
disables vector, graph, and raw fallback; see
[QueryArgs lines 620–629](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-mcp/src/server.rs#L620-L629).
Replayed LongMemEval dates remain unchanged in user text, following the own
benchmark, rather than being confused with current ingestion times.

For `build_llm()`, after the final acknowledged SessionEnd, the same `/mcp`
transport calls `tools/call` with `name="memory_consolidate"` and
`arguments={"session_id": "<native UUID>"}`. The only argument used is documented
at [ConsolidateArgs lines 1117–1128](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-mcp/src/server.rs#L1117-L1128):
“UUID of the session to consolidate”; omitted `dry_run` and `multi_page` both
default false. This is the documented manual ingestion/consolidation route:
[docs/usage.md line 110](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/usage.md#L110).
The response is awaited; no background queue polling or SQL modification is
needed. Source execution at
[server.rs lines 3465–3482](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-mcp/src/server.rs#L3465-L3482)
awaits the default single-page consolidator. Empty, lifecycle-only sessions
skip manual consolidation, following the default behavior described in
[llm-providers.md lines 11–15](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/llm-providers.md#L11-L15).

## Model routes, defaults, and costs

| Configuration item | Source and applied behavior |
| --- | --- |
| Local embeddings | [local-embeddings.md lines 3–20](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/local-embeddings.md#L3-L20): `AI_MEMORY_EMBEDDING_PROVIDER=local`, in-process `all-MiniLM-L6-v2`, 384 dimensions; “As of 2.0 this is the default”; explicit local “hard-fails if unavailable”. Applied to both builders. |
| Default first boot | The unset-provider best-effort path can start without vectors until a later restart. Explicit local awaits model fetch/load and fails if unavailable: [serve.rs lines 2436–2488](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/commands/serve.rs#L2436-L2488). This requested explicit setting prevents silently benchmarking FTS-only. |
| Chat route | `build_llm()` applies `AI_MEMORY_LLM_PROVIDER=openai-compat`, `AI_MEMORY_LLM_BASE_URL=llm.base_url`, `AI_MEMORY_LLM_MODEL=llm.model`, and optional `LLM_API_KEY` copied in process memory from the variable named by `llm.api_key_env`. Names/base/model are documented at [llm-providers.md lines 118–153](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/llm-providers.md#L118-L153). **OpenAI-compatible chat endpoints are supported.** URLs containing embedded credentials are rejected. Keyless compat is explicit upstream behavior: [factory.rs lines 79–81](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-llm/src/factory.rs#L79-L81), `OptionalApiKey { env_var: "LLM_API_KEY" }`. |
| Embedding route | The system also supports OpenAI-compatible embedding endpoints, but they require explicit model/dimension: [llm-providers.md lines 188–204](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/llm-providers.md#L188-L204). These two builders deliberately use the requested default **local** encoder, so a supplied `embed` route is unused and recorded in stats notes. No embedding URL/key/dimension override is applied. |
| Chat-LLM, reranker, assistant capture, SessionEnd queue | Defaults are respectively absent, absent, false, false in [config.rs lines 948–966](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/config.rs#L948-L966). `build()` preserves all four. `build_llm()` adds only the supplied chat route and manual consolidation; reranking, capture, and SessionEnd queue stay at defaults. |
| Other memory options | Retention, maintenance, retrieval, search, slots, and consolidation inherit native defaults: [config.rs lines 972–980](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/config.rs#L972-L980). No benchmark tuning is applied. |

The default variant makes **zero generative LLM calls**. Local encoding runs in
process at ingestion/page writes and recall. The LLM variant makes one manual
single-page consolidation request per nonempty session; source
[consolidator.rs lines 245–265](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-consolidate/src/consolidator.rs#L245-L265)
builds one request and calls `complete_structured_with_retry`, so roughly one
completion for that explicit call, with potentially additional retry attempts.
This is **not a total server LLM-call estimate**: the native background review
scheduler is enabled by default, with a 3,600-second interval, at most one session
per tick, and a 600-second minimum session age;
[config.rs lines 1148–1157](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-cli/src/config.rs#L1148-L1157)
defines those defaults. The tool documentation at
[server.rs lines 3505–3507](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-mcp/src/server.rs#L3505-L3507)
states that configured servers also schedule background review. This adapter
preserves that behavior, which can add calls in a sufficiently long-lived
namespace. Awaiting manual consolidation does not establish that all background
work has finished. Native HTTP responses do not report the total call count:
`IngestStats.llm_calls=None` for both builders. Adapter elapsed ingestion seconds
include acknowledged writes and, in the LLM variant, the awaited consolidation;
the stats notes also disclose the possibility of background review.

The following settings are explicitly **upstream benchmark setting, not applied**:

- `AI_MEMORY_CAPTURE_ASSISTANT=true` and `capture_assistant=1` plus the
  `_ai_memory_assistant` excerpt marker: official
  [server.rs lines 107–108](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/server.rs#L107-L108)
  and [ingest.rs lines 78–79, 110–119](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/ingest.rs#L78-L119).
  They violate the requested default capture behavior.
- FTS baseline `AI_MEMORY_EMBEDDING_PROVIDER=none`: official
  [server.rs lines 119–127](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/server.rs#L119-L127).
  This task selects its documented local configuration instead.
- The fixed eval bearer `ai-memory-eval-token`: official
  [server.rs lines 16–17](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/server.rs#L16-L17)
  and [launch line 107](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/server.rs#L107).
  A private loopback server uses the documented anonymous local mode.
- A/B candidate reranking, server env overrides, and extra query knobs:
  [server.rs lines 45–62](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/server.rs#L45-L62)
  and [query.rs lines 114–122](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/evals/src/retrieval/query.rs#L114-L122).
  No matrix override, `pin_first`, `include_superseded`, `answer`, or similar
  non-default recall option is used.

## Disk state, upstream issue, and documentation limits

Native on-disk layout is documented at
[README.md lines 432–445](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/README.md#L432-L445):
“One Rust binary ... owns one data directory”, `wiki/` is git-versioned markdown,
`db/` contains SQLite indexes/FTS/entities/embeddings, `models/` contains the
local encoder cache, and `logs/` contains rolling tracing output. `raw/` is
reserved for sanitized managed-workstream transcript segments; this adapter
uses ordinary hook replay and does not create managed-workstream transcripts.
Retained namespaces therefore consume disk until the coordinator removes
`workdir`. LLM provider keys exist only in the child environment, never in an
adapter-written file.

Open issue observed on 2026-10-02 UTC:
[#1041, “drop_subagent_captures drops the whole top-level Claude Code session when it is launched with `--agent`”](https://github.com/akitaonrails/ai-memory/issues/1041).
The reporter names v2.5.2 and an `agent_type` payload triggering subagent policy.
It affects conversation ingestion, is still open, and was not independently
reproduced here. This replay omits the reported agent/subagent markers.

Upstream leaves full-fidelity two-role conversation import **under default
assistant-capture settings** unavailable on this chosen interface. Exact
provider call counts and a historical session/question-date replay parameter
are not documented by the used hook/query interfaces; the adapter does not
invent them. Source-pinned correction to older prose: benchmark docs describe
a general 2-KB capture boundary, but v2.5.2's current durable-body sanitizer
sets a **16-KiB** ceiling, with event-specific smaller limits:
[sanitize.rs lines 47–50, 357–360](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-core/src/sanitize.rs#L47-L50)
and [sanitization call site](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/crates/ai-memory-core/src/sanitize.rs#L357-L360).
The adapter follows native processing rather than imposing the old prose cap.

## Offline verification

The source-builder installed binary reports `ai-memory 2.4.2`; `--help`,
`serve --help`, and the [v2.4.2 changelog](https://github.com/akitaonrails/ai-memory/blob/v2.4.2/CHANGELOG.md#L10-L80)
were checked before reading the pinned v2.5.2 definitions. The adapter's version
guard rejects that older binary. No memory system was installed or served, and
no existing host service was queried, started, or stopped.

Run from the worktree root:

```sh
python3 -B -m unittest blueprints/memory-h2h/tests/test_adapter_ai_memory.py
```

The tests stub every HTTP and subprocess operation; their ports are synthetic
values 61234–61236 and no socket is opened. They cover native launch arguments,
default/env isolation, local model seeding, version rejection, private reset,
readiness failures, owned-process cleanup, chronological hook/body shapes,
acknowledgement retries and failures, default assistant omission, manual default
consolidation, namespace guards, JSON/SSE decoding, title/snippet/provenance/rank
mapping, and unsupported `k`. If the core file is absent, the test uses the
provided fixed interface in memory, never writes a replacement `h2h/types.py`,
and switches to the real interface when that file exists. The HTTP package is
stubbed too, so the tests need no installed memory system or HTTP dependency.

Result: **37 offline tests passed**, Python 3.13.15, exit code 0. These are
locally authored request/lifecycle contract checks, not upstream tests or
evidence that local embeddings, consolidation, recall quality, or LongMemEval's
official judge ran successfully. Live execution remains the coordinator's work.

Source-review corrections recorded this turn: the initial draft conflated the
documented `llm_timeout_secs = 900` example with the actual 300-second default;
the verification path was `config.rs`'s `DEFAULT_REQUEST_TIMEOUT_SECS` reference
to the constant in `ai-memory-llm/src/lib.rs:39`, corroborated by
[llm-providers.md lines 323–325](https://github.com/akitaonrails/ai-memory/blob/v2.5.2/docs/llm-providers.md#L323-L325).
The completeness review also caught an overly broad one-call-per-session cost
statement; reading `AutoImproveSchedulerSettings::default` and the
`memory_auto_improve` description established the additional default background
work. Both claims are corrected above; no native option was changed.
