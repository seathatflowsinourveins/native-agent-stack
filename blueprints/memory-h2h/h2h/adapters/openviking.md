# OpenViking adapter evidence

Target: [`volcengine/OpenViking` v0.4.22](https://github.com/volcengine/OpenViking/tree/v0.4.22),
commit `e8716760934d95ef73414484a45bfe475b9296e2` (verified with the GitHub tag-ref API).
`build()` returns an independent adapter with `name="openviking"`,
`version="v0.4.22"`, and `needs_llm=True`. The adapter uses the documented HTTP
API with `httpx`; it imports no OpenViking SDK and performs no import-time I/O.

## Reference implementations read first

- OpenViking's own [LongMemEval importer, lines 247–274](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/import_to_ov.py#L247-L274):
  `create_session()`, message `parts=[{"type": "text", "text": msg["text"]}]`,
  parsed session time plus one second per turn, and `commit_session()`.
  The adapter adopts these operations and the timestamp conversion. It preserves
  turn content and role, sorts sessions stably by their parsed dataset dates,
  and waits for each commit before ingesting the next session.
- The importer's [task polling, lines 306–313](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/import_to_ov.py#L306-L313):
  `get_task(task_id)` until `status == "completed"`. The adapter adopts this
  completion condition and reports failed/cancelled tasks as ingestion failures.
- OpenViking's own [LongMemEval recall, lines 389–409](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/run_eval.py#L389-L409):
  `find(question, target_uri=.../memories, limit=...)`, followed by `read(uri,
  offset=0, limit=-1)`. The adapter adopts find and visible reads,
  omitting the benchmark's non-default target scope and read parameters whose
  values are already defaults. The common
  harness owns answer generation and LongMemEval judging.
- OpenViking was **not found in the complete tree or provider registry** of
  `vectorize-io/agent-memory-benchmark` at
  `f618ed7b1f0eb9cad7b42e876f91a42f0eadb150`:
  [tree API](https://api.github.com/repos/vectorize-io/agent-memory-benchmark/git/trees/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150?recursive=1),
  [registry, lines 1–40](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/__init__.py#L1-L40).
  Consequently there was no OpenViking adapter to reuse from that reference.

## Installation and private server lifecycle

Upstream's [release verification checklist, lines 179–183](https://github.com/volcengine/OpenViking/blob/v0.4.22/RELEASE.md#L179-L183)
quotes `pip install openviking==<version>`. With this task's release substituted:

```sh
pip install openviking==0.4.22
```

This is a coordinator prerequisite. No OpenViking package was installed or run
while building this adapter. The source-build preflight found no `openviking`
distribution, `openviking` executable, or `ov` executable in the builder's
default Python/command environment. The pinned [release notes](https://github.com/volcengine/OpenViking/releases/tag/v0.4.22)
were read before the tagged interface source.

`start(workdir, llm, embed)` requires both routes, their key environment variable
names to exist, an installed `openviking-server`, and an integer `H2H_PORT` in
`1..65535`. Each launch creates a private `openviking-*` directory underneath
`workdir`, writes `ov.conf`, and runs the following argument vector with that
directory as its working directory:

```sh
openviking-server --config /private/run/ov.conf --host 127.0.0.1 --port H2H_PORT_VALUE
```

The executable and **every flag** are documented in
[deployment, lines 42–60](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/guides/03-deployment.md#L42-L60):
`--config` selects `ov.conf`, `--host` defaults to `127.0.0.1`, and `--port`
selects the bind port. [`pyproject.toml`, lines 204–206](https://github.com/volcengine/OpenViking/blob/v0.4.22/pyproject.toml#L204-L206)
defines the installed `openviking-server` entry point. The adapter uses
`H2H_PORT`, rather than assuming the upstream port default.

The startup probe is `GET /ready`, without parameters. Upstream quotes
“Returns 200 when all configured subsystems are ready and 503 otherwise” and
documents response `"status": "ready"` in
[System API, lines 136–176](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/07-system.md#L136-L176).
Transport timeouts (60 seconds per request), readiness polling (120 seconds
overall), and task polling (3600 seconds overall) bound harness operations;
they do not change OpenViking's model, extraction, or retrieval configuration.

`stop()` closes this adapter's HTTP client and terminates only its own `Popen`
handle, waits ten seconds, and kills that same process if necessary. It is
idempotent. It does not attach to a pre-existing server. Lifecycle operations
were tested with mocked subprocesses and HTTP responses only.

## Configuration parameters and model routes

Only connection settings and the private storage location are written:

```json
{
  "vlm": {
    "provider": "openai",
    "model": "LLM_ROUTE_MODEL",
    "api_base": "LLM_ROUTE_BASE_URL",
    "api_key": "${LLM_ROUTE_KEY_ENV}"
  },
  "embedding": {
    "dense": {
      "provider": "openai",
      "model": "EMBED_ROUTE_MODEL",
      "api_base": "EMBED_ROUTE_BASE_URL",
      "api_key": "${EMBED_ROUTE_KEY_ENV}"
    }
  },
  "storage": {"workspace": "/private/run/data"}
}
```

`vlm`, `embedding.dense`, and their `provider`, `model`, `api_base`, and
`api_key` fields are quoted in the upstream
[OpenAI configuration example, lines 169–188](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/guides/01-configuration.md#L169-L188)
and the [server configuration field table, lines 120–137](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/configuration/01-server.md#L120-L137).
**Both the LLM and embedding role accept OpenAI-compatible base URLs.** No
provider-specific key is required by the adapter. For a service that ignores
authentication, the coordinator can supply a synthetic nonempty key through
the named variable, as the VLM config still requires a key
([validation, lines 323–334](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking_cli/utils/config/vlm_config.py#L323-L334)).

The quoted `${ENV}` form is resolved by upstream
[`load_json_config`, lines 83–88](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking_cli/utils/config/config_loader.py#L83-L88):
`raw = os.path.expandvars(raw)`. The adapter checks variable names and their
presence, inherits the subprocess environment, and writes only names in
placeholders. It never reads a key value, copies a credential file, or writes
keys into configuration/arguments. URLs with credentials, query strings, or
fragments are rejected. `$` in route URLs/model names is rejected because
upstream expands variables across the whole configuration text.

`storage.workspace` and the omitted local backend defaults are documented in
[server configuration, lines 197–207](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/configuration/01-server.md#L197-L207):
`agfs.backend=local`, `vectordb.backend=local`, and vector dimensions follow
Embedding. No extraction policy, worker count, retry count, threshold, reranker,
encoding format, or embedding dimension is overridden.

**Embedding compatibility boundary:** the fixed `ModelRoute` has no dimension
field. Upstream recognizes dimensions for `text-embedding-ada-002` (1536),
`text-embedding-3-small` (1536), and `text-embedding-3-large` (3072)
([schema resolution, lines 512–527](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking_cli/utils/config/embedding_config.py#L512-L527));
an unrecognized OpenAI model name ultimately uses the 2048 schema fallback
([lines 589–594](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking_cli/utils/config/embedding_config.py#L589-L594)).
The embedder independently probes the model output dimension
([lines 190–205](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking/models/embedder/openai_embedders.py#L190-L205)).
Thus an arbitrary compatible embedding endpoint still needs output consistent
with upstream's default schema; compatibility with a different-width custom
model is unverified. The adapter preserves these defaults instead of supplying
a custom dimension or silently renaming the model. Upstream states dimensions
“must match model output and existing collections” in the field table above.

## Ingestion and recall request contract

All successful data responses must have `{"status":"ok","result":...}`.
Upstream defines that envelope in
[API overview, lines 220–234](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/01-overview.md#L220-L234).
HTTP errors and malformed successful responses fail the operation; they are
not counted as empty retrievals.

| Operation | Exact wire request and upstream quotation |
|---|---|
| Create a session | `POST /api/v1/sessions`, JSON `{}`. `session_id` defaults to `None`, which creates a generated ID. [Sessions parameters, lines 43–47](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/05-sessions.md#L43-L47); [HTTP endpoint/examples, lines 63–79](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/05-sessions.md#L63-L79). |
| Add each turn | `POST /api/v1/sessions/{session_id}/messages` with `role`, `parts: [{"type":"text","text":turn.content}]`, and top-level `created_at`. Roles/parts: [Sessions, lines 1028–1035](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/05-sessions.md#L1028-L1035); exact part/date mapping: [benchmark, lines 261–271](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/import_to_ov.py#L261-L271); HTTP `created_at: Optional[str] = None`: [request model, lines 138–148](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking/server/routers/sessions.py#L138-L148); endpoint: [router, lines 715–727](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking/server/routers/sessions.py#L715-L727). SDK `options` is **not** a nested HTTP field. |
| Commit | `POST /api/v1/sessions/{session_id}/commit`, JSON `{}`. `keep_recent_count` defaults to `0`; `reset_context` defaults to `false`. [Sessions parameters, lines 1362–1368](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/05-sessions.md#L1362-L1368); [endpoint, lines 1377–1391](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/05-sessions.md#L1377-L1391). |
| Wait for the commit | `GET /api/v1/tasks/{task_id}`, no query parameters. Task ID and default `include_events=false`: [Tasks, lines 13–47](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/17-tasks.md#L13-L47). Only `completed` succeeds; pending/running/cancelling continue, failed/cancelled fail. |
| Find contexts | `POST /api/v1/search/find` with `query` and `limit:k`. Endpoint: [Retrieval, lines 113–124](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/06-retrieval.md#L113-L124); query and omitted default target/context-type fields: [lines 55–76](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/06-retrieval.md#L55-L76); `limit: int = DEFAULT_LIMIT`: [request schema, lines 125–140](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking/server/routers/search.py#L125-L140). Upstream's default limit is 10 ([lines 5–13](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/06-retrieval.md#L5-L13)); the common harness supplies `k`. Isolation comes from the fresh workspace. |
| Read the returned text | `GET /api/v1/content/read?uri=RETURNED_URI`, no other parameters. `offset=0`, `limit=-1`, `raw=false` remain defaults. [Content parameters, lines 138–155](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/12-content.md#L138-L155); [progressive retrieval HTTP example, lines 1124–1139](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/06-retrieval.md#L1124-L1139). |
| Directory hit | If read returns the documented `400 INVALID_ARGUMENT` with `details.expected="file"`, `details.actual="directory"`, call `GET /api/v1/content/overview?uri=RETURNED_URI`. Structured mismatch: Content lines 151–153 above; directory overview endpoint: progressive retrieval lines 1133–1135 above. Other read errors propagate. |

Dates remain unchanged in the supplied `Session` objects. The wire timestamp
mapping matches the importer: parse `%Y/%m/%d (%a) %H:%M`, add turn-index
seconds, and use `isoformat()`. Unsupported date strings fail before any HTTP
ingestion, rather than silently assigning today's date. `question_date` does
not add a retrieval filter: `find` defaults have none, and filtering memory
processing timestamps by a historical question date would hide newly ingested
memories. The upstream evaluation's unfiltered call is cited above.

An accepted commit must report a task ID. A documented empty commit with
`status="skipped"`, `task_id=null` needs no polling
([Sessions, lines 1339–1349](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/05-sessions.md#L1339-L1349)).
No extra global queue barrier is applied: upstream's
[`TaskTracker._finalize_task`, lines 737–761](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking/service/task_tracker.py#L737-L761)
refuses finalization while task-owned work remains. This matches its own
benchmark's completion polling.

Returned `Retrieved.text` is the default visible content/overview, and `score`
is the score reported by find. The default memory/resource/skill result groups
are flattened in upstream's own iteration order
([`FindResult.__iter__`, lines 335–339](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking_cli/retrieve/types.py#L335-L339)),
up to the common `k`. There is no adapter-side rerank or text budget.
Default `MatchedContext` does not report dataset session IDs
([result schema, lines 83–108](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/06-retrieval.md#L83-L108));
`Retrieved.session_ids` therefore stays empty. Generated server session IDs
are not invented as dataset provenance.

## Defaults, isolation, disk, and LLM work

**Upstream benchmark setting, not applied:** explicit user-memory `target_uri`
([evaluation, lines 389–394](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/run_eval.py#L389-L394));
`telemetry=True` on commit
([importer line 274](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/import_to_ov.py#L274));
parallel/submission concurrency 16 and deferred waits
([README, lines 29–36](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/README.md#L29-L36));
excluding `.abstract.md` and `.overview.md` hits
([evaluation, lines 162–177](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/run_eval.py#L162-L177));
extra client-side reranking and character-budget filtering
([lines 413–424](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/run_eval.py#L413-L424));
the README's 50-candidate/10-reranked/30000-character configuration
([lines 62–74](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/README.md#L62-L74)).
The script's 10/10/4000 context constants are likewise benchmark policy,
not server defaults
([lines 24–28](https://github.com/volcengine/OpenViking/blob/v0.4.22/benchmark/longmemeval/openviking/run_eval.py#L24-L28)).

Correction during source review: the initial implementation copied the
benchmark's explicit memory target. That is a non-default recall option, so it
was removed after checking the tagged request schema (`target_uri=""`,
`context_type=None`, cited above). A regression fixture now checks that recall
sends only `query`/`limit` and preserves all three native result groups. Fresh
workspace isolation makes a benchmark-specific target restriction unnecessary.

`reset(namespace)` stops the previous owned subprocess and launches another
with a **new storage workspace**, including on repeated reset of the same
namespace. The new process cannot access another question's previous filesystem,
vector index, queue, sessions, user memories, or working summaries through its
configured store. Only the current namespace may call ingest/retrieve. This
is harness orchestration using the documented private workspace, rather than
an upstream reset endpoint. Old run directories are retained as private
artifacts until the coordinator removes `workdir`. The release warns that
legacy `namespace` isolation configuration is ignored; this adapter does not
depend on it ([v0.4.22 migration note 4](https://github.com/volcengine/OpenViking/releases/tag/v0.4.22)).

Disk contains the local RAGFS data/metadata, native local vector indexes,
session messages and archived messages, generated `.abstract.md`/
`.overview.md`, memory files, and commit-task records. Session layout is
documented in [Sessions, lines 1527–1548](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/05-sessions.md#L1527-L1548);
task persistence in [Tasks, line 26](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/17-tasks.md#L26);
the default QueueFS database is
`{storage.workspace}/_system/queue/queue.db`
([AGFS config, lines 399–403](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking_cli/utils/config/agfs_config.py#L399-L403)).
The adapter also retains its placeholder-only `ov.conf` and captured
`server.log` in each private run directory.

Ingestion needs the LLM for working-memory summaries, long-term extraction,
and dedup/merge decisions. Upstream describes the summary call
([session source, lines 280–289](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking/session/session.py#L280-L289))
and the extraction/dedup pipeline
([session concepts, lines 135–154](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/concepts/08-session.md#L135-L154)).
It does not publish a fixed per-session LLM call budget: extraction is batched
([source, lines 2402–2449](https://github.com/volcengine/OpenViking/blob/v0.4.22/openviking/session/session.py#L2402-L2449)),
and actual model work depends on extracted memories and retries. `find` embeds
the query and omits search's LLM intent-analysis/query-expansion step
([Retrieval, lines 5–25](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/06-retrieval.md#L5-L25)).
Default task responses show token usage, not an aggregate call count
([Tasks example, lines 157–188](https://github.com/volcengine/OpenViking/blob/v0.4.22/docs/en/api/17-tasks.md#L157-L188));
`IngestStats.llm_calls=None`. Session counts and elapsed ingestion seconds are
measured by the adapter.

## Open issues and validation limits

Open GitHub reports checked on 2026-10-02; none was reproduced by this source build:

- [#5514](https://github.com/volcengine/OpenViking/issues/5514), explicitly v0.4.22:
  fenced model-generated operation blocks fail session extraction with
  `failure_kind=parse_error`. The adapter surfaces failed commit tasks.
- [#5515](https://github.com/volcengine/OpenViking/issues/5515), explicitly v0.4.22:
  list-valued working-memory content can crash summarization/commit.
- [#5526](https://github.com/volcengine/OpenViking/issues/5526), explicitly v0.4.22:
  a missing working-memory section `op` can preserve stale content. This
  concerns update paths; the adapter normally commits each imported session once.
- [#5544](https://github.com/volcengine/OpenViking/issues/5544), explicitly v0.4.22:
  session-aware `search` planner output can override a memory-only scope.
  The report says its equivalent `find` succeeds; this adapter follows the
  upstream benchmark's `find` operation while keeping its default scope.
- [#5433](https://github.com/volcengine/OpenViking/issues/5433), reported against
  0.4.21 / CLI 0.4.22.dev0: actor-peer filtering may include another peer's
  memories. Applicability to release v0.4.22 is unverified. Fresh workspaces
  avoid relying on peer filtering for question isolation.

Offline check:

```sh
python3 -B -m unittest blueprints/memory-h2h/tests/test_adapter_openviking.py
```

The first attempt under the default Python 3.13 environment failed at import
because `httpx` was absent (exit 1). With an existing installed `httpx` supplied
through `PYTHONPATH`, the same command initially ran 14 tests, OK, exit 0.
After the default-scope correction above, the rerun ran **15 tests, OK, exit 0**. No package
installation, network request, server execution, or host-service operation was
needed. MockTransport fixtures check the wire contract and subprocess fixtures
check private configuration, reset isolation, and owned-process cleanup. These
are locally authored integration checks, not OpenViking upstream acceptance
tests or a measured benchmark run. Live server/model acceptance, custom
embedding-width compatibility, and actual recall quality remain for the
coordinator's system runs.
