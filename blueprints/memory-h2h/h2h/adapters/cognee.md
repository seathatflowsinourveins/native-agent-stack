# Cognee adapter: v1.6.2

Target: [`topoteretes/cognee` v1.6.2](https://github.com/topoteretes/cognee/releases/tag/v1.6.2),
commit [`ba3631f2ed363a6ea50d649c34c56885af6b36fe`](https://github.com/topoteretes/cognee/tree/ba3631f2ed363a6ea50d649c34c56885af6b36fe).
The distribution declares `version = "1.6.2"` and Python `>=3.10,<3.15`
in [pyproject.toml, lines 1–10](https://github.com/topoteretes/cognee/blob/v1.6.2/pyproject.toml#L1-L10).
The adapter checks installed distribution metadata and the API health version.

The baseline uses the default extraction pipeline, default HYBRID_COMPLETION
retrieval, and default SQLite, LanceDB, and Ladybug stores. Storage locations,
model routes, the common `k`, and the documented local single-user deployment
posture are supplied by the harness. `onlyContext=true` is an explicit output
selection required by the common-answerer experiment: it returns retrieved
context without having Cognee generate an answer. It does not use the native
default `only_context=False`; this exception is recorded rather than called a
default setting. No chunk sizes, extraction prompts, retrieval lane depths,
relevance thresholds, session distillation, or database tuning are supplied.

This is a source build and an offline contract check. Cognee was not installed
or run, and no host service was queried. Native ingestion/recall acceptance and
benchmark scores belong to the coordinator's subsequent runs.

## References read before implementation

* Cognee's own [evaluation harness README, lines 1–49](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/eval_framework/README.md#L1-L49)
  describes corpus construction, QA, and evaluation. Its
  [corpus executor, lines 67–81](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/eval_framework/corpus_builder/corpus_builder_executor.py#L67-L81)
  establishes the clean-store, add, process sequence. We adopt that sequence
  through the documented REST operations. Its `chunk_size=1024`, `TextChunker`,
  corpus deduplication, and custom task pipeline are **upstream benchmark
  setting, not applied**; the normal cognify endpoint supplies its own defaults.
* Cognee's [BEAM report, lines 47–75](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/eval_framework/beam/REPORT.md#L47-L75)
  ingests with add/cognify, maps a conversation batch to a document, and preserves
  turn order and timestamps. We take the conversation-to-document mapping and
  preserve the input session date and turn order. BEAM's per-turn JSON chunks,
  cleanup/compression, global context index, session distillation, and
  question-type answer prompts are **upstream benchmark setting, not applied**.
  The [published fixed configuration, lines 4–22](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/eval_framework/beam/report_artifacts/100k_fixed/beam_hybrid_completion_20_20_qa_v1_config.json#L4-L22)
  sets `chunks_top_k=20`, `entities_top_k=20`, and question-type prompts; each is
  **upstream benchmark setting, not applied**. Its reported scores are not this
  default API baseline.
* The external reference is
  [`vectorize-io/agent-memory-benchmark`, commit f618ed7b1f0eb9cad7b42e876f91a42f0eadb150,
  src/memory_bench/memory/cognee.py](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/cognee.py#L14-L32).
  We take its ordered per-document add followed by cognify sequence
  ([lines 98–116](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/cognee.py#L98-L116))
  and its observation that access-controlled responses can group results under
  `search_result`. Its OpenAI `gpt-4o-mini`, FastEmbed
  `BAAI/bge-small-en-v1.5`, dimensions `384`
  ([lines 46–86](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/cognee.py#L46-L86)),
  `chunk_size=512`, `chunks_per_batch=1`, `CHUNKS`, and hard-coded `top_k=50`
  ([lines 115–132](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/cognee.py#L115-L132))
  are **upstream benchmark setting, not applied**. We do not reuse its global
  environment mutations or global prune operations.

## Installation and native self-hosted launch

The pinned README's installation instruction is, verbatim:

> `uv pip install "cognee[gliner]"`

Source: [README.md, lines 86–92](https://github.com/topoteretes/cognee/blob/v1.6.2/README.md#L86-L92).
Apply the distribution's declared release pin to that supported command:

```sh
uv pip install "cognee[gliner]==1.6.2"
```

For a run that always supplies an LLM route, the base package is sufficient:
`uv pip install "cognee==1.6.2"`. Upstream explicitly describes the base
`pip install cognee` package in
[README.md, line 162](https://github.com/topoteretes/cognee/blob/v1.6.2/README.md#L162).
The GLiNER extra does not force local extraction when an LLM key is configured.
Install into the interpreter that runs the harness; the adapter never installs
packages or builds an image.

The harness also requires `httpx` as a direct adapter dependency; the Cognee
package alone is not the complete harness installation. Install it with
`uv pip install "httpx>=0.28.1"`, using the same declared requirement as
[Cognee's dev dependency group, pyproject.toml lines 416–419](https://github.com/topoteretes/cognee/blob/v1.6.2/pyproject.toml#L416-L419).
The offline test supplies an HTTPX fixture, so its successful run does not
claim that HTTPX or Cognee is installed in the test interpreter.

The server uses the exact native application and server options from the
release's self-hosted [entrypoint.sh, lines 53–62](https://github.com/topoteretes/cognee/blob/v1.6.2/entrypoint.sh#L53-L62):

> `exec gunicorn -w 1 -k uvicorn.workers.UvicornWorker -t 30000 --bind=$BIND_ADDRESS:$HTTP_PORT --log-level error --access-logfile - --error-logfile - cognee.api.client:app`

The adapter executes Gunicorn through `sys.executable -m gunicorn` so that it
uses the checked Python environment, substitutes `127.0.0.1:<H2H_PORT>` for the
bind address, and preserves every other server option above. Gunicorn and
Uvicorn are package dependencies in
[pyproject.toml, lines 101–102](https://github.com/topoteretes/cognee/blob/v1.6.2/pyproject.toml#L101-L102).
The native application performs startup migrations in its lifespan
([client.py, lines 101–114](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/client.py#L101-L114));
no separately authored initialization pipeline is used.

`H2H_PORT` is a harness variable, not a Cognee parameter. It must be an unused
per-adapter port; reserved host ports are rejected. A brief bind check fails
before making requests to an existing listener; its `reuse_port=False` follows
the upstream socket ownership rule in
[client.py, lines 499–507](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/client.py#L499-L507).

Local API authentication is selected with
`ENABLE_BACKEND_ACCESS_CONTROL=false`. Upstream explicitly documents this
single-user posture and its difference from the multi-tenant default in
[README.md, lines 255–265](https://github.com/topoteretes/cognee/blob/v1.6.2/README.md#L255-L265)
and [minimal-docker-compose.md, lines 22–27](https://github.com/topoteretes/cognee/blob/v1.6.2/docs/minimal-docker-compose.md#L22-L27):

> `ENABLE_BACKEND_ACCESS_CONTROL: "false"`

The process and all memory directories are private to this adapter. This
deployment choice changes authentication and response wrapping, not the
selected retrieval strategy or embedded store providers. Readiness uses
`GET /health`, documented in
[minimal-docker-compose.md, lines 37–43](https://github.com/topoteretes/cognee/blob/v1.6.2/docs/minimal-docker-compose.md#L37-L43).
Its `status`, `health`, and `version` response fields are defined in
[get_health_router.py, lines 13–28](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/health/routers/get_health_router.py#L13-L28).
The startup wait is bounded, and an early server exit is an error.
Native stderr is inherited so Gunicorn import and bind failures remain visible
even before Cognee creates its log files. The adapter does not capture that
stream to a credential-bearing file.

## Model routes, secrets, and defaults

Both roles accept OpenAI-compatible HTTP base URLs. The LLM endpoint must also
support the structured graph and summary outputs expected by Cognee; its
default `litellm_native` framework uses schema-native output or a prompted JSON
fallback, described in
[llm/config.py, lines 101–112](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/llm/config.py#L101-L112).

| Child environment parameter | Value and pinned upstream contract |
| --- | --- |
| `LLM_PROVIDER` | `openai`, the native default: `llm_provider: str = "openai"` in [llm/config.py, lines 109–112](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/llm/config.py#L109-L112). |
| `LLM_MODEL` | `openai/<ModelRoute.model>`; the provider prefix selects LiteLLM's OpenAI handler while the supplied model names the endpoint's model. The native OpenAI configuration example is [.env.template, lines 17–20](https://github.com/topoteretes/cognee/blob/v1.6.2/.env.template#L17-L20), and the model is passed into LiteLLM in [native_adapter.py, lines 254–260](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/llm/structured_output_framework/litellm_native/native_adapter.py#L254-L260). |
| `LLM_ENDPOINT`, `LLM_API_KEY` | The route's base URL and the value resolved from its `api_key_env`, only in the child environment. The documented names are quoted in [.env.template, lines 9–20](https://github.com/topoteretes/cognee/blob/v1.6.2/.env.template#L9-L20); `api_base=endpoint` and `api_key=api_key` are used in [native_adapter.py, lines 254–260](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/llm/structured_output_framework/litellm_native/native_adapter.py#L254-L260). |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | Default provider `openai`, with `openai/<ModelRoute.model>` selecting the common model route. Native defaults are `DEFAULT_EMBEDDING_PROVIDER = "openai"`, `DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-large"` in [embeddings/config.py, lines 19–20](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/vector/embeddings/config.py#L19-L20). |
| `EMBEDDING_ENDPOINT`, `EMBEDDING_API_KEY` | Base URL and key from the embedding route's named variable. Names and key reuse behavior are documented in [.env.template, lines 108–113](https://github.com/topoteretes/cognee/blob/v1.6.2/.env.template#L108-L113). The engine forwards `"model": self.model`, `"api_key": self.api_key`, `"api_base": self.endpoint` in [LiteLLMEmbeddingEngine.py, lines 218–225](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/vector/embeddings/LiteLLMEmbeddingEngine.py#L218-L225). |

ModelRoute contains an environment variable **name**, never a credential.
Its model is the endpoint's literal identifier, matching the common
OpenAI-compatible answerer's interpretation. The additional `openai/` prefix
is only for Cognee's LiteLLM dispatch. Review checked the apparent double-prefix
case against the pin's lockfile-resolved LiteLLM 1.96.2: its
[provider resolver, lines 529–530](https://github.com/BerriAI/litellm/blob/v1.96.2/litellm/litellm_core_utils/get_llm_provider_logic.py#L529-L530)
removes exactly the first prefix. Thus an endpoint model literally named
`openai/shared-chat` requires `openai/openai/shared-chat` in Cognee's config;
normalizing it would change the endpoint model and break the fixed interface.
This correction is covered by an offline route-shape test.
The adapter resolves that name in memory, validates the URL, injects the native
child variable, and writes no key file. Credentials are not command
arguments, notes, or request bodies. Only a small set of Python runtime
environment variables is inherited; Cognee settings, remote database routes,
mock flags, stage overrides, and unrelated credentials are excluded. The
parent environment is not changed. Adapter HTTP requests ignore proxy
environment settings and target its loopback API.

Review corrected an additional configuration-isolation gap: cleaning the
subprocess environment alone does not prevent Cognee from loading a discovered
`.env`, which overrides even preset variables. The adapter writes an empty
0600 `empty.env` inside each private run directory and sets the documented
`COGNEE_ENV_FILE` selector to that exact path. Upstream quotes “that exact file,
no search” in [shared/env_file.py, lines 15–20](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/shared/env_file.py#L15-L20)
and implements `dotenv.load_dotenv(_resolved, override=True)` in
[lines 112–122](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/shared/env_file.py#L112-L122).
The selected file contains no credentials or settings. This prevents ancestor
or package-side configuration from replacing the benchmark's routes, paths,
or native defaults; no ambient credential file is read.

With a supplied LLM, an explicit embedding route is required: otherwise the
native default reuses the LLM key against the default OpenAI embedder rather
than the harness endpoint. With no routes, the untouched native defaults use
GLiNER extraction and local FastEmbed. An embedding route without an LLM uses
GLiNER extraction with that embedding route. `needs_llm` is conservatively true
before start and reflects the configured LLM role after start.

There is no embedding dimension or connection-test override. Review initially
flagged the unknown-model `3072` fallback in
[embeddings/config.py, lines 139–155](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/vector/embeddings/config.py#L139-L155).
That warning alone does **not** establish a dimension incompatibility: the
normal pipeline probes a real embedding and synchronizes its dimension in
[setup_and_check_environment.py, lines 50–94](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/pipelines/layers/setup_and_check_environment.py#L50-L94)
and [llm/utils.py, lines 233–259](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/llm/utils.py#L233-L259).
The default probe remains enabled. Unknown model token limits still use the
native cap and warning in
[input_limit.py, lines 108–135](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/vector/embeddings/input_limit.py#L108-L135).
The adapter does not invent a token limit or replace the default LiteLLM
embedding engine with a differently configured provider.

## Ingestion and recall contracts

The full paths are registered in
[client.py, lines 384–390](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/client.py#L384-L390):

> `app.include_router(get_add_router(), prefix="/api/v1/add", tags=["add"])`
>
> `app.include_router(get_cognify_router(), prefix="/api/v1/cognify", tags=["cognify"])`
>
> `app.include_router(get_search_router(), prefix="/api/v1/search", tags=["search"])`

| Operation and parameters actually sent | Upstream quotation and source |
| --- | --- |
| `POST /api/v1/add`, multipart `data` and `datasetName` | The self-hosted example sends `-F "data=@note.txt"` and `-F "datasetName=main_dataset"` in [minimal-docker-compose.md, lines 46–51](https://github.com/topoteretes/cognee/blob/v1.6.2/docs/minimal-docker-compose.md#L46-L51). `data` means files to upload and `datasetName` names the target dataset, created when missing, in [get_add_router.py, lines 90–96 and 118–141](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/add/routers/get_add_router.py#L90-L141). The default is `run_in_background=False` ([lines 106–108](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/add/routers/get_add_router.py#L106-L108)); no background flag is sent. |
| `POST /api/v1/cognify`, JSON `datasets: [dataset_name]` | The self-hosted example uses `'{"datasets": ["main_dataset"]}'` in [minimal-docker-compose.md, lines 53–56](https://github.com/topoteretes/cognee/blob/v1.6.2/docs/minimal-docker-compose.md#L53-L56). The DTO documents dataset names, `run_in_background=False`, default KnowledgeGraph, `chunk_size=None`, and default chunk batch size in [get_cognify_router.py, lines 43–117](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/cognify/routers/get_cognify_router.py#L43-L117). Only `datasets` is sent. |
| `POST /api/v1/search`, JSON `query`, `datasets`, `topK`, `onlyContext` | The DTO defines `query` as the required question, `datasets` as dataset names, `top_k=15`, and `only_context` as context instead of an answer in [get_search_router.py, lines 26–87](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/search/routers/get_search_router.py#L26-L87). The quote for context output is: “No LLM call is made and nothing is written to the session.” `topK` is the harness's common `k`; `onlyContext` is true. |
| Default search strategy | `search_type` has `default=SearchType.HYBRID_COMPLETION` in [get_search_router.py, lines 26–34](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/search/routers/get_search_router.py#L26-L34). The adapter omits this parameter to preserve the default and its native fallbacks. |

CamelCase is the native JSON wire convention; request DTOs also accept
snake_case, documented in [DTO.py, lines 1–8 and 27–33](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/DTO.py#L1-L33).
Each session is uploaded as one UTF-8 `.txt` document containing its session ID,
unchanged date string, and the original turns labeled by role. The adapter adds
and completes cognify for each session before moving to the next supplied
session. It does not sort or rewrite dates, deduplicate turns, compress
assistant messages, or create simulated answers.

Blocking add returns a single PipelineRunInfo
([add.py, lines 345–367](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/add/add.py#L345-L367));
blocking cognify returns a mapping from dataset ID to PipelineRunInfo
([cognify.py, lines 241–249](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/cognify/cognify.py#L241-L249)).
Only `PipelineRunCompleted` or `PipelineRunAlreadyCompleted` counts as completed
ingestion; names are defined in
[PipelineRunInfo.py, lines 26–43](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/pipelines/models/PipelineRunInfo.py#L26-L43).
HTTP errors and incomplete/failed pipeline responses propagate. A namespace
that has received no sessions returns no retrieved items without querying an
empty graph; a server-side search failure after ingestion is not scored as an
empty successful retrieval.

Context output is the original rendered user prompt, including the question
and retrieval context, or the bare context when no prompt was built. It is
forwarded unchanged to the common answerer. The semantics are documented in
[SearchResultPayload.py, lines 89–100](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/search/models/SearchResultPayload.py#L89-L100)
and in the search DTO above. It is not Cognee's generated answer.

The local single-user response is a list of raw contexts. Access-controlled
responses instead wrap each dataset's context in `search_result`; this
distinction was verified in
[search/methods/search.py, lines 634–702](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/search/methods/search.py#L634-L702),
correcting the initial assumption that every response uses the external
benchmark's dataset wrapper. The adapter handles both, preserves structured
contexts as JSON, and invents neither source session IDs nor scores. Those
fields remain `()` and `None` because the selected rendered-prompt response
does not report them as structured source-session evidence.

`question_date` is not sent: the selected SearchPayloadDTO has no date field.
Session dates remain available in the ingested text. No temporal pipeline is
enabled. Common `k` is passed as `topK`; native hybrid retrieval caps each lane
at `min(top_k, 10)` and can fall back to graph retrieval, as documented in
[search.py, lines 41–61 and 215–218](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/search/search.py#L215-L218).
No retriever-specific options are used to enlarge those defaults. Also, the
search router's prose says references default true while the actual DTO has
`default=False`
([get_search_router.py, lines 120–123 and 229](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/search/routers/get_search_router.py#L120-L123));
the adapter omits the option and follows the executable DTO default.

## LLM work, GLiNER, storage, and reset isolation

With an LLM route, graph extraction and summarization are the two main
chunk-level operations. The default task combines them in
[extract_graph_and_summarize.py, lines 23–37](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/graph/extract_graph_and_summarize.py#L23-L37).
Each chunk is passed to graph extraction
([extract_graph_from_data.py, lines 224–232](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/graph/extract_graph_from_data.py#L224-L232))
and summary extraction
([summarize_text.py, lines 55–58](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/summarization/summarize_text.py#L55-L58)).
Budget roughly two structured LLM operations per chunk, plus the native
connection probes once per fresh process, with retries or further extraction
work increasing the total. There is no fixed session-to-chunk ratio. The
selected PipelineRunInfo does not have an LLM-call-count field
([lines 9–16](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/pipelines/models/PipelineRunInfo.py#L9-L16));
`IngestStats.llm_calls` stays `None`. Context-only recall still embeds the query
but does not make an answer-generation LLM call.

The `gliner` extra supplies local extraction dependencies, not a different
database. Under `GRAPH_EXTRACTOR=auto`, a usable LLM key selects the LLM path;
without one, the GLiNER demo extracts both graph and summaries without LLM
calls. Embeddings still run. These rules are explicitly documented in
[cognify.py, lines 229–239](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/v1/cognify/cognify.py#L229-L239)
and [gliner_demo/tasks.py, lines 1–12](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/tasks/graph/gliner_demo/tasks.py#L1-L12).
With no model routes, native embeddings fall back to FastEmbed
`BAAI/bge-small-en-v1.5`
([embeddings/config.py, lines 203–224](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/vector/embeddings/config.py#L203-L224)).
Upstream can install the GLiNER runtime automatically on first use; installing
the extra beforehand is its supported preparation path
([pyproject.toml, lines 242–248](https://github.com/topoteretes/cognee/blob/v1.6.2/pyproject.toml#L242-L248)).
The source build itself performs no such installation or model download.

Every launch gets a fresh directory under the supplied private `workdir`:

| Environment path and stored state | Pinned source |
| --- | --- |
| `DATA_ROOT_DIRECTORY` (`data/`): uploaded source text and data files | `data_root_directory` is a configurable base path in [base_config.py, lines 23–27](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/base_config.py#L23-L27); relocation is documented in [minimal-docker-compose.md, lines 86–93](https://github.com/topoteretes/cognee/blob/v1.6.2/docs/minimal-docker-compose.md#L86-L93). |
| `SYSTEM_ROOT_DIRECTORY` (`system/`): relational metadata, dataset/user records, pipeline records, graph, and vectors | Default SQLite `db_provider = "sqlite"` and derived `system/databases` path: [relational/config.py, lines 16–40](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/relational/config.py#L16-L40). Ladybug `graph_database_provider` and derived path: [graph/config.py, lines 45–62 and 91–99](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/graph/config.py#L45-L99). LanceDB `vector_db_provider = "lancedb"` and `system/databases/cognee.lancedb`: [vector/config.py, lines 28–37 and 83–86](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/vector/config.py#L28-L86). |
| `CACHE_ROOT_DIRECTORY` (`cache/`) and `COGNEE_LOGS_DIR` (`logs/`): native caches and logs | Both settings are defined in [base_config.py, lines 24–27](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/base_config.py#L24-L27). |

The default session cache is also SQLite, with a cache database beside the
relational database, described in
[cache/config.py, lines 13–20 and 51–53](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/infrastructure/databases/cache/config.py#L13-L53).
It therefore follows the fresh system directory rather than a host Redis
service. The only adapter-created file is the empty configuration selector
described above; upstream creates its own stores and logs during native runs.

`reset(namespace)` stops only the process group created by this adapter,
closes its HTTP client, and launches a new process with new data, system,
cache, and log directories. This also discards process-local caches and
session history; changing only a dataset filter in a shared local graph would
not provide the same isolation. The local posture can ignore dataset scoping
([search/methods/search.py, lines 148–152](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/search/methods/search.py#L148-L152)),
so physical store isolation is essential. Namespace mismatch is rejected
before any ingestion/recall request. Reusing a namespace still allocates a
fresh store; old directories are retained for inspection but never reopened.
`stop()` leaves these private artifacts for the coordinator to manage. The
native app drains work and closes cached database engines on shutdown
([client.py, lines 156–180](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/api/client.py#L156-L180)).

## Open upstream reports and documented limits

Reviewed from the GitHub issue API on 2026-10-01:

* [#5254](https://github.com/topoteretes/cognee/issues/5254), open: concurrent
  processes sharing a local LanceDB store can leave partial ingestion and
  duplicate vector IDs. Separate stores and sequential session requests avoid
  sharing a store between adapters; native internal batching remains at its
  default. The issue tracks the proposed #5253 fix.
* [#5222](https://github.com/topoteretes/cognee/issues/5222), open: hybrid recall
  returns unrelated passages for noise queries and misses some exact
  identifiers. Its measurements were on 1.6.1, not a reproduction on 1.6.2.
  No local threshold or lexical reranking is added to change the baseline.
* Empty or uncognified datasets can produce NoDataError; the pinned behavior
  is defined in [search/methods/search.py, lines 547–589](https://github.com/topoteretes/cognee/blob/v1.6.2/cognee/modules/search/methods/search.py#L547-L589).
  Completion is checked before recall, and server errors are preserved.

A LongMemEval-specific conversation serialization schema, a universal LLM
call count per session, and a question-date parameter were not found in the
cited interfaces, README, evaluation sources, or the
[v1.6.2 release notes](https://github.com/topoteretes/cognee/releases/tag/v1.6.2).
The documented file-ingestion contract is therefore used for the transparent
session transcript mapping described above. The exact question-date string
is accepted by the fixed harness interface but is not translated into an
undocumented upstream parameter. No installed Cognee client was queried in
this source-only task.

## Offline validation

```sh
python3 -B -m unittest blueprints/memory-h2h/tests/test_adapter_cognee.py
```

Observed on Python 3.13.15 with the core builder's actual `h2h.types` available:
22 tests, `OK`, exit code **0**. These are locally authored contract checks,
not Cognee's upstream evaluation suite or native execution acceptance.
Fixtures replace HTTPX, sockets, subprocess launch/signals, and installed
distribution metadata. They check the native server argument vector,
loopback port selection, secret transport, default-setting hygiene,
multipart add, blocking cognify completion, context-only search and its
untuned strategy, response shapes, fresh-store reset including repeated
namespaces, the empty dotenv selector's path/mode/content, and failure/cleanup
paths. No memory service is installed,
started, stopped, or contacted by the tests. If `h2h.types` has not yet been
written, the test contains an in-memory copy of the fixed interface and
creates no replacement source file.
