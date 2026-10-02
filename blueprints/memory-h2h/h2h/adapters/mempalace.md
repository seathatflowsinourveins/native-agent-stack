# MemPalace adapter — v3.10.0

This adapter uses MemPalace's documented conversation miner and search through
its native HTTP MCP server. It targets
[`MemPalace/mempalace@v3.10.0`](https://github.com/MemPalace/mempalace/tree/v3.10.0),
commit `22fd87f09c19d5ffb2d6966486483353937931c0`. The annotated tag resolves to
that commit in the [GitHub tag object](https://api.github.com/repos/MemPalace/mempalace/git/tags/aec66e540fc44a00c77d8004df06707572dbe634).
The release was published September 16, 2026; sources and open issues were read
October 2, 2026. No MemPalace installation or service was executed for this build.
The system Python was 3.13.15; its package metadata and import lookup did not find
MemPalace. Capability evidence below is pinned source review, not native execution.

## Installation and launch

The [v3.10.0 release's Install section](https://github.com/MemPalace/mempalace/releases/tag/v3.10.0)
quotes the exact pinned command:

```sh
pip install -U mempalace==3.10.0
```

The tagged README recommends an isolated CLI installation, quoting
`uv tool install mempalace` at
[`README.md:80–85`](https://github.com/MemPalace/mempalace/blob/v3.10.0/README.md#L80-L85).
The pinned equivalent is `uv tool install mempalace==3.10.0`. Installation is the
coordinator's responsibility. MemPalace's own dependencies live with its CLI;
the adapter uses only the standard library and the harness's `httpx` dependency.
No MemPalace client library, custom server, or embedding implementation is used.

`start` launches this argument vector, with a fresh private palace under the
supplied `workdir` and the integer port from `H2H_PORT`:

```text
mempalace serve --host 127.0.0.1 --port <H2H_PORT> --palace <private-generation>/palace
```

The native console entry point is quoted as
`mempalace = "mempalace.cli:main"` in
[`pyproject.toml:57–59`](https://github.com/MemPalace/mempalace/blob/v3.10.0/pyproject.toml#L57-L59).
The full command and every flag are declared by
[`cli/parser.py:549–561`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/cli/parser.py#L549-L561):
`serve`, `--host` (default `127.0.0.1`), `--port` (default `8765`), and
`--palace` (overrides config/env). The official deployment guide describes
`serve` as a foreground wrapper around `mempalace-mcp --transport http` and
documents the host/port flags at
[`remote-server.md:120–160`](https://github.com/MemPalace/mempalace/blob/v3.10.0/website/guide/remote-server.md#L120-L160).
On this POSIX harness, it execs the server so process termination reaches the
server itself: [`cmd_serve.py:200–209`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/cli/cmd_serve.py#L200-L209).
`stop` terminates only the adapter's `Popen` child, waits, and kills that child
if it does not exit. It closes its HTTP client and is idempotent.

Readiness uses `GET /healthz`, quoted as “returns `200 ok` without a token” in
[`remote-server.md:205–211`](https://github.com/MemPalace/mempalace/blob/v3.10.0/website/guide/remote-server.md#L205-L211)
and implemented in [`http.py:398–402`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/http.py#L398-L402).
The adapter's readiness deadline is 60 seconds; HTTP tool requests have a
600-second transport timeout. These bound the harness's waiting; they do not
change extraction, indexing, embedding, or ranking settings.

## Native HTTP MCP contract

Every MCP request goes to `POST /mcp`. The native handler parses a JSON request
body and returns JSON, rather than requiring an SSE parser:
[`http.py:1029–1055`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/http.py#L1029-L1055),
[`http.py:1087–1097`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/http.py#L1087-L1097).
The endpoint is also documented at
[`remote-server.md:162–179`](https://github.com/MemPalace/mempalace/blob/v3.10.0/website/guide/remote-server.md#L162-L179).
Loopback requires no bearer token when none is supplied; the native wrapper
only auto-generates a token for a non-loopback bind:
[`cmd_serve.py:116–150`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/cli/cmd_serve.py#L116-L150).

The adapter sends `jsonrpc: "2.0"`, an incrementing `id`, `method`, and `params`.
For initialization it sends `method: "initialize", params: {}`; this is
explicitly supported by the native dispatcher, which chooses its default
`protocolVersion` and returns `serverInfo.name` and `serverInfo.version`:
[`protocol.py:672–717`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/protocol.py#L672-L717).
The returned name/version must be `mempalace`/`3.10.0`. The next request is
`method: "notifications/initialized", params: {}`, without an `id`; native
notifications return no response body and HTTP 202:
[`protocol.py:720–722`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/protocol.py#L720-L722),
[`http.py:1087–1095`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/http.py#L1087-L1095).

Tool requests use `method: "tools/call"` and
`params: {"name": <tool>, "arguments": <object>}`. The handler validates the
two fields at [`protocol.py:738–752`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/protocol.py#L738-L752)
and wraps the tool's dictionary in JSON text under `result.content`:
[`protocol.py:832–846`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/protocol.py#L832-L846).
The adapter checks HTTP errors, JSON-RPC errors/response IDs, MCP tool errors,
and native result dictionaries. Failures are raised instead of being scored as
an empty successful retrieval. Native tool payloads have no configurable
per-system tuning added by the adapter.

## Conversation ingestion and recall

For each `Session`, in the list order supplied by the coordinator, the adapter
writes one Claude.ai-compatible JSON conversation export (native plaintext for
zero/singleton turns, as explained below) and synchronously calls:

```json
{"name": "mempalace_mine", "arguments": {"source": "<private-session-file.json>", "mode": "convos"}}
```

The official reference states, “`mode='convos'` also accepts a single conversation
file” and “Wraps the same in-process miners the CLI uses”:
[`mcp-tools.md:160–174`](https://github.com/MemPalace/mempalace/blob/v3.10.0/website/reference/mcp-tools.md#L160-L174).
Every supplied argument (`source`, `mode: "convos"`) is declared in
[`schemas.py:448–473`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/schemas.py#L448-L473).
The implementation calls `convo_miner.mine_convos` in process at
[`tools_write.py:710–722`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/tools_write.py#L710-L722).
This is the documented `mempalace mine <file> --mode convos` operation exposed
over MCP; the CLI parameters are independently declared at
[`parser.py:159–177`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/cli/parser.py#L159-L177).
One-file calls preserve session order without depending on native directory
traversal. Session and namespace IDs never become filesystem path components.

The export uses `chat_messages`, with `role: "user" | "assistant"` and string
`content`. These exact input fields are accepted by the pinned normalizer:
[`normalize.py:616–664`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/normalize.py#L616-L664).
Both conversation roles are included. Each content value contains the envelope
`[Session date: <original date string>]\n<original turn content>` so dates are
actually ingested and can be retrieved. The date string is never parsed or
reformatted. The export also records the original session ID as `uuid` and the
original date as `created_at`; the normalizer reads only the message list from
this object, so these export fields are provenance, not native date filtering
or a promise of reported session IDs. Recall adds no facts from these fields.

For a singleton turn, the adapter instead writes a UTF-8 `.txt` transcript:
`> [Session date: <date>]\n<content>` for a user, or the same text without the
`> ` marker for an assistant. An empty session gets an empty `.txt` file, with
no fabricated date/ID metadata. Plaintext is an explicitly supported conversation
format at [`mining.md:35–48`](https://github.com/MemPalace/mempalace/blob/v3.10.0/website/guide/mining.md#L35-L48);
the rendering mirrors the native `> user`/assistant representation at
[`normalize.py:1000–1029`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/normalize.py#L1000-L1029).
The normalizer returns no conversations for empty input and passes plaintext
through at [`normalize.py:212–227`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/normalize.py#L212-L227).
The same `source`/`mode` mine request is used for both formats.

All optional mine arguments are omitted: `wing`, `agent`, `limit`, `dry_run`,
and `extract` retain upstream defaults, including `extract="exchange"`.
The signature/defaults are quoted in
[`tools_write.py:646–678`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/tools_write.py#L646-L678).
The normalizer converts user turns to `>` markers followed by assistant text:
[`normalize.py:1000–1027`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/normalize.py#L1000-L1027).
Native chunking uses exchange pairs when at least three `>` lines exist and
otherwise paragraph chunks, at
[`convo_miner.py:298–331`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/convo_miner.py#L298-L331).
The native conversation minimum is 30 characters; chunk size comes from native
config, with no adapter override:
[`convo_miner.py:1024–1035`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/convo_miner.py#L1024-L1035).

Recall calls only:

```json
{"name": "mempalace_search", "arguments": {"query": "<benchmark question>", "limit": 5}}
```

The example `5` is replaced by the harness's `k`; accepted range is 1–100.
`query` and `limit` are documented at
[`mcp-tools.md:61–74`](https://github.com/MemPalace/mempalace/blob/v3.10.0/website/reference/mcp-tools.md#L61-L74),
with the numeric limits in
[`schemas.py:286–301`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/schemas.py#L286-L301).
The adapter leaves `candidate_strategy="vector"`, optional context, room/wing
filters, thresholds, and ranking at native defaults:
[`tools_read.py:551–564`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/tools_read.py#L551-L564),
[`tools_read.py:643–667`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/tools_read.py#L643-L667).
Questions are sent intact to native query sanitization; upstream can shorten a
query beyond its 250-character threshold:
[`query_sanitizer.py:28–59`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/query_sanitizer.py#L28-L59).

`Retrieved.text` is the native result's `text`, unchanged; `score` is its
`similarity` when present. Reported `source_path` or `source_file` is mapped to
the ingested session's original ID; unknown/unreported sources produce an empty
`session_ids` tuple. No content-match guesses or additional store reads occur.
These returned fields are defined at
[`query.py:326–338`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/searcher/query.py#L326-L338).
`question_date` is not sent as `since` or `before`: both compare wall-clock
`filed_at`, and applying a historical question date would exclude memories
ingested for this run. Their semantics are quoted at
[`schemas.py:313–329`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/mcp_server/schemas.py#L313-L329).

## Model routes, defaults, and isolation

`needs_llm=False`: default exchange mining and memory search do not use a
generative LLM. The optional `llm` route is unused, and does not enable LLM
extraction or reranking. MemPalace does separately support an OpenAI-compatible
LLM provider for optional entity refinement, documented in
[`llm_client.py:277–282`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/llm_client.py#L277-L282);
that optional operation is outside this adapter. `IngestStats.llm_calls=0`
describes this chosen path; embedding requests are not generative LLM calls.
The miner's default exchange path is specified in
[`convo_miner.py:875–908`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/convo_miner.py#L875-L908).

With `embed=None`, native config selects `minilm` and the documented bundled
Chroma backend. The actual config fallback is quoted at
[`config.py:1303–1325`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/config.py#L1303-L1325);
Chroma's default local storage is documented at
[`configuration.md:23–58`](https://github.com/MemPalace/mempalace/blob/v3.10.0/website/guide/configuration.md#L23-L58).
When the coordinator explicitly supplies `embed`, MemPalace can use that
OpenAI-compatible route through its supported provider, quoted as
“`openai-compat` — embeddings served by any OpenAI-compatible `/v1/embeddings`
endpoint” at [`embedding.py:24–33`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/embedding.py#L24-L33).
This is an explicit harness route, not an inferred default or benchmark tuning.
The adapter uses exactly these documented environment settings:

| Environment setting | Value source | Pinned definition |
| --- | --- | --- |
| `MEMPALACE_CONFIG_DIR` | Fresh private generation's `config/` | [`config.py:1–13`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/config.py#L1-L13) |
| `MEMPALACE_PALACE_PATH` | Fresh private generation's `palace/` | [`configuration.md:183–205`](https://github.com/MemPalace/mempalace/blob/v3.10.0/website/guide/configuration.md#L183-L205) |
| `MEMPALACE_EMBEDDING_MODEL` | `openai-compat`, only when `embed` is supplied | [`config.py:1303–1325`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/config.py#L1303-L1325) |
| `MEMPALACE_EMBEDDING_API_URL` | `embed.base_url` | [`config.py:1490–1498`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/config.py#L1490-L1498) |
| `MEMPALACE_EMBEDDING_API_MODEL` | `embed.model` | [`config.py:1500–1507`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/config.py#L1500-L1507) |
| `MEMPALACE_EMBEDDING_API_KEY` | Read the environment variable named by `embed.api_key_env`, if set | [`config.py:1509–1517`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/config.py#L1509-L1517) |

Bare-host, `/v1`, and full `/embeddings` URLs are normalized by upstream itself:
[`embedding.py:624–630`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/embedding.py#L624-L630).
Keys go only into the child's environment; no key or environment snapshot is
written to disk or command arguments. Process stdout/stderr go to `DEVNULL`.
Inherited `MEMPALACE_*`/`MEMPAL_DIR` overrides are removed before setting the
private paths and explicitly supplied embedding route. The harness process's
environment is never changed. No `HOME`/`CODEX_HOME` override is used.

Every `reset(namespace)` terminates the old child and launches a new one on the
same assigned port, with a newly created mode-0700 generation directory, empty
config, and empty palace. This also happens when the namespace is repeated.
It clears source/session mappings and rejects operations for a prior namespace.
It does not issue broad deletion requests or open the host's existing palace.
The private config override prevents defaults from reading the host's existing
config, people map, identity, and associated auxiliary state. Fresh-process
isolation also discards process-global Chroma/embedding caches. Older private
generations remain on disk for coordinator-owned cleanup and are unreachable
through the active server.

On disk are the serialized session exports, MemPalace's private config/server
registration and any auxiliary files it creates, and Chroma's palace with
verbatim drawer text, metadata, embeddings, SQLite and index files. The native
metadata/upsert path is shown at
[`convo_miner.py:711–749`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/convo_miner.py#L711-L749).
Local Chroma is an embedded store; no second database service is launched.

## Reference harnesses and limitations

The upstream LongMemEval raw baseline was read first. It uses a shared
`chromadb.EphemeralClient`, deleting/recreating its collection per question:
[`longmemeval_bench.py:91–155`](https://github.com/MemPalace/mempalace/blob/v3.10.0/benchmarks/longmemeval_bench.py#L91-L155).
It joins **user turns only** in session mode and writes directly with
`collection.add`, carrying `corpus_id`/`timestamp`:
[`longmemeval_bench.py:163–225`](https://github.com/MemPalace/mempalace/blob/v3.10.0/benchmarks/longmemeval_bench.py#L163-L225).
We take its clean-per-question isolation principle; we use the documented
native conversation miner to meet this harness's both-role ingestion contract.
We do not copy its direct Chroma writes, user-only corpus, or special retrievers.

**Upstream benchmark setting, not applied:** raw's `n_results=50`, session/turn
granularity, the benchmark's collection name/metadata schema, alternate
`--embed-model` choices, keyword weighting, `aaak`, room boosts, hybrid-v1/v2/v3/v4,
palace/diary/full retrievers, query expansion and optional LLM reranking. Source:
[`longmemeval_bench.py:163–225`](https://github.com/MemPalace/mempalace/blob/v3.10.0/benchmarks/longmemeval_bench.py#L163-L225),
[`longmemeval_bench.py:3265–3358`](https://github.com/MemPalace/mempalace/blob/v3.10.0/benchmarks/longmemeval_bench.py#L3265-L3358).
Optional diary mode makes one call per uncached session containing user turns
([`longmemeval_bench.py:2370–2431`](https://github.com/MemPalace/mempalace/blob/v3.10.0/benchmarks/longmemeval_bench.py#L2370-L2431));
this adapter enables none of it. Upstream acknowledges hybrid-v4 tuning against
known misses at [`BENCHMARKS.md:84–94`](https://github.com/MemPalace/mempalace/blob/v3.10.0/benchmarks/BENCHMARKS.md#L84-L94).

**Source correction:** upstream prose says raw retrieves 10
([`HYBRID_MODE.md:35–38`](https://github.com/MemPalace/mempalace/blob/v3.10.0/benchmarks/HYBRID_MODE.md#L35-L38));
the pinned executable defaults to 50 at `longmemeval_bench.py:163`. Neither value
overrides this harness's common `k`. Upstream reported retrieval recall is not
answer accuracy, as explicitly stated at
[`BENCHMARKS.md:44–68`](https://github.com/MemPalace/mempalace/blob/v3.10.0/benchmarks/BENCHMARKS.md#L44-L68).

A MemPalace adapter was **not found in the inspected tree, README, or provider
registry** of `vectorize-io/agent-memory-benchmark` at commit
`f618ed7b1f0eb9cad7b42e876f91a42f0eadb150`. The complete provider registry is
[`memory/__init__.py:1–40`](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/__init__.py#L1-L40).
There was consequently no second-system adapter to adopt from that source.

Native API limitations retained in this source build:

- Mining returns a human-readable `output` string, rather than a structured
  stored-session/drawer count or LLM usage. `IngestStats.sessions` counts
  successfully completed per-session mine requests, not a verified count of
  stored sessions. Native skip/dedup/chunk behavior stays intact; no summary
  string is treated as usage accounting.
- Export dates are not carried into drawer chronology for `.json`/plaintext exports.
  `_extract_authored_at` reads only top-level timestamps in `.jsonl` files, then
  falls back to native filing time:
  [`convo_miner.py:595–625`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/convo_miner.py#L595-L625),
  [`convo_miner.py:726–734`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/convo_miner.py#L726-L734).
  The unchanged dataset date is therefore ingested as transcript text.
- **Research correction and acceptance:** the draft used JSON exports for all
  sessions. The source critic rejected the assumption that this faithfully
  normalizes zero/singleton sessions: the JSON parser requires two recognized
  messages and otherwise indexes raw serialization. The parser requirement is at
  [`normalize.py:640–644`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/normalize.py#L640-L644),
  and fallback is at
  [`normalize.py:212–227`](https://github.com/MemPalace/mempalace/blob/v3.10.0/mempalace/normalize.py#L212-L227).
  The repair uses documented plaintext for these cases. Three added offline
  tests verify empty input, singleton user Unicode/newlines, and singleton
  assistant Unicode/newlines. The corrected suite passes all 26 tests; this is
  local contract acceptance, with native execution still unverified.
- A conversation-level `question_date`/as-of search parameter, original dataset
  session IDs in search results, and default-miner generative-LLM usage counters
  were not found in the pinned mine/search documentation and schemas cited
  above. Source filename
  provenance is the supported session-ID bridge; default source review supports
  zero generative calls, rather than an upstream metering counter.

The predefined Astra/Max source-researcher role handled the bounded upstream
reference and completeness reviews. The review triggers were conflicting
benchmark prose/executable defaults and native ingestion fidelity. The final
source review accepted the plaintext repair and closed its empty/singleton
blocker; the native MCP, reset, and model-route contracts were also accepted
against pinned source. This records source-review acceptance separately from
the 26 passing local fixtures and the unexecuted live qualification.

Open upstream reports affecting relevant paths, checked October 2, 2026:

- [#2468](https://github.com/MemPalace/mempalace/issues/2468), **open**: re-mining a
  JSONL conversation assigns its newest timestamp to earlier exchanges. This
  reinforces the chronology limitation; the adapter does not manufacture
  per-exchange times.
- [#2175](https://github.com/MemPalace/mempalace/issues/2175), **open**: the search
  candidate pool depends on requested result count, so changing `k` can change
  which top result appears. The coordinator must use the same `k` across systems;
  this adapter does not increase candidate counts or rerank separately.
- [#2622](https://github.com/MemPalace/mempalace/issues/2622), **open**: resetting a
  Chroma System can close a client under still-live collection handles. Adapter
  reset uses a new process/store instead of manipulating Chroma client caches.

## Offline validation

Run from the worktree root:

```sh
python3 -B -m unittest blueprints/memory-h2h/tests/test_adapter_mempalace.py
```

These are locally authored contract fixtures, not upstream tests or live
MemPalace acceptance. They replace the HTTP dependency with a standard-library
stub and mock `Popen`, so they need no installed MemPalace/httpx, no network,
no listener, and no host service. They check the native command, MCP envelopes,
export fields, per-session request ordering, default omission, route handling,
source provenance, reset isolation, version/failure propagation and owned-child
cleanup. If core `h2h/types.py` is absent, the test file supplies the fixed
interface in memory only and never creates a replacement source file.
The command above returned exit 0, `Ran 26 tests`, `OK`, on Python 3.13.15.
Live native ingestion, retrieval, persistence, and model routing remain for
the coordinator to qualify on the installed pinned system.
