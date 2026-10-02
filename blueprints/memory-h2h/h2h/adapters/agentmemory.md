**agentmemory adapter — v0.9.29, source review dated 2026-10-02**

Target: [rohitg00/agentmemory v0.9.29][release], resolved to
`2d38dafede67d0d4ed920cde94d2106e98825b8a` by the [tag reference][tag].
`build()` implements the fixed `h2h.types.MemoryAdapter` interface using
`POST /agentmemory/observe` and `POST /agentmemory/search`. It uses Python's
standard library and `httpx`; no agentmemory client package is required.
Imports perform no network or process operations. No memory system was installed
or run during this source build.

The installed-client check (`command -v agentmemory`) found no executable. The
[v0.9.29 release notes][release] were read before the pinned source and README.
Docker CLI **29.8.1**, `docker run --help`, `docker stop --help`,
`docker container ls --help`, and `docker --help` were inspected without
contacting a daemon. Its GitHub release-note lookup returned 404; the pinned
CLI source and command documentation below supply the transport/lifecycle
evidence. The [annotated v29.8.1 tag][docker-tag] resolves to
`4a63305d74332de5ceba7fcbccbc3cbb7412f5ba`. All eight cited Docker files were
checked byte-for-byte against the earlier research snapshot and are unchanged;
the citations now point to the installed release's source. Runtime assumptions
below are source conclusions, not live acceptance.

**References read before implementation.** The native
[benchmark/longmemeval-bench.ts:40–45][transcript] uses
`.map((t) => \`${t.role}: ${t.content}\`).join("\\n")`. This adapter adopts that
transcript format and its one-record-per-session representation. The benchmark
[141–180][bench-ingest] creates fresh indexes/MockKV per question and inserts
internal `CompressedObservation` records directly, with the entire transcript as
`narrative`; that internal ingestion shortcut is not applied. The live HTTP load
benchmark [258–267][load-ingest] posts `content`/`type` to `/remember`, and
[320–328][load-search] posts `query`/`limit` to `/smart-search`; it supplies a
reference for JSON HTTP transport and error checking, not our selected endpoints.
The additional official [eval/runner/adapters/agentmemory.ts:47–91][eval-adapter]
uses those same endpoints, observation-to-session provenance, and overfetching.
This adapter takes its provenance discipline but returns the selected search
API's own session IDs and text.

The requested Vectorize reference was inspected at
`vectorize-io/agent-memory-benchmark@f618ed7b1f0eb9cad7b42e876f91a42f0eadb150`.
No agentmemory adapter was found in its [complete, nontruncated tree][vectorize-tree]
or [provider registry:1–40][vectorize-registry]. No implementation was borrowed
from another system's adapter.

| Setting in an upstream benchmark | Disposition |
| --- | --- |
| Full-transcript internal narrative, manual type/title/importance/facts, embeddings of only the first 512 characters ([141–180][bench-ingest]) | **upstream benchmark setting, not applied**; observations go through the public REST capture/compression path. |
| `HybridSearch(..., 0.4, 0.6, 0.0, false)` and search limit `20` ([185–200][bench-search]) | **upstream benchmark setting, not applied**; production weights and retrieval behavior remain native, and `k` is the common harness limit. |
| Exclude four abstention categories ([127–133][bench-filter]) | **upstream benchmark setting, not applied**; dataset selection belongs to the common harness. |
| CLI benchmark defaults to `bm25`, while other modes instantiate local embeddings ([305–315][bench-mode]) | **upstream benchmark setting, not applied**; provider detection follows supplied model routes and native defaults. |
| `type: "eval-session"`, `concepts: [s.id]`, limit `Math.max(k * 10, 50)` and session deduplication ([47–91][eval-adapter]) | **upstream benchmark setting, not applied**; this adapter makes no overfetch or recall postprocessing changes. |

**Installation and self-hosted launch.** The coordinator prepares a local Linux
Docker image from the **unmodified** pinned
[deploy/coolify/Dockerfile:1–32][dockerfile]. It specifies
`ARG AGENTMEMORY_VERSION=0.9.29`, `ARG III_VERSION=0.11.2`, and
`ARG III_SDK_VERSION=0.11.2`. Its exact upstream installation command is:

```sh
npm install "@agentmemory/agentmemory@${AGENTMEMORY_VERSION}" --omit=optional --no-fund --no-audit
```

This is quoted from [Dockerfile:17–20][docker-install], with the version argument
defaulting to `0.9.29`. Upstream also documents
`npm install -g @agentmemory/agentmemory` in [README:108–113][npm-install]; its
release-pinned form is `npm install -g @agentmemory/agentmemory@0.9.29`.
The image route isolates the server's homedir, preferences, `.env` lookup and
pidfiles as well as its store. The README explicitly describes building the
self-hosted Dockerfile in [deploy/coolify/README.md:39–43][coolify-build]. From a
checkout of the tag, the coordinator can produce the required local image with:

```sh
docker build --file deploy/coolify/Dockerfile --tag agentmemory-h2h:0.9.29 deploy/coolify
```

Docker's [build reference:24,40,64–78][docker-build] documents `--file` as
"Name of the Dockerfile", `--tag` as "Name and optionally a tag in the
`name:tag` format", the context positional argument, and the default Buildx
backend. Preparation is a coordinator action; `start()` never builds or installs.
The image's base-image/dependency resolution follows upstream's Dockerfile;
an image digest is not certified by these offline tests.

`start(workdir, llm, embed)` creates a private generation directory beneath the
provided workdir, launches the stock native CLI inside this image, and waits for
`GET /agentmemory/health` to report `service: "agentmemory"` and
`version: "0.9.29"`. The [health handler:266–298][health] defines those fields and
registers `http_method: "GET"`, `api_path: "/agentmemory/health"`.
The lifecycle uses these documented options; Docker citations are pinned to
`docker/cli@4a63305d74332de5ceba7fcbccbc3cbb7412f5ba`.

| Command / option used | Upstream quote and source |
| --- | --- |
| `docker run --name NAME` | "Assign a name to the container" ([man:514–527][docker-name]). Each generation gets a fresh UUID name. |
| `--rm` | "Automatically remove the container ... when it exits" ([man:620–624][docker-rm]). Bind-mounted stores remain inspection artifacts. |
| `--pull never` | "Do not pull the image ... produce an error if the image does not exist" ([run:566–605][docker-pull]). |
| `--network host` | "Use the host's network stack inside the container" ([man:529–540][docker-network]). This makes the supplied host-loopback model endpoints reachable. |
| `--mount type=bind,source=...,target=/data` and a config mount with `readonly` | "source ... location on the host", "target ... destination inside the container" ([run:242–265][docker-mount]); `source`, `target`, `readonly` are specified in [man:468–485][docker-mount-options]. Only the fresh store and its launch config are mounted. |
| `--entrypoint /usr/bin/tini IMAGE -- agentmemory ...` | "Overwrite the default entrypoint", with options passed as positional command arguments ([run:932–975][docker-entrypoint]). Upstream installs `tini` and uses `/usr/bin/tini --` ([Dockerfile:11–12,32][dockerfile]). |
| `--env NAME` | "checks the value ... in your local environment and passes it to the container", without an `=` ([run:626–640][docker-env]). Only mapped provider and transport variables are forwarded. |
| `--no-healthcheck` | "Disable any container-specified HEALTHCHECK" ([run:83][docker-healthcheck]). The image's [fixed-port check:29–30][dockerfile] would probe a different server after port relocation. The adapter checks its own allocated port. |
| `DOCKER_CONFIG=workdir/docker-config` | "To specify a different directory, use the DOCKER_CONFIG environment variable" ([docker:216–230][docker-config]). Host credential/config files are not selected. |
| Optional `DOCKER_HOST=unix:///absolute/socket` | "Unix socket", example `unix:///var/run/docker.sock`; `DOCKER_HOST` selects the daemon socket ([docker:427–449][docker-host]). The adapter accepts local absolute Unix socket paths only. |
| Native `agentmemory --port P --data-dir /data` | CLI default command: "Start agentmemory worker"; `--port` documents offsets `N+1`, `N+2`, `N+46023`; `--data-dir` stores engine state ([cli:168–214][cli-options], [README:250–255][data-dir]). |
| `docker stop --timeout 20 NAME` | After the grace period the owned container is forcibly stopped; "The --timeout flag sets the number of seconds to wait" ([stop:20–61][docker-stop]). The adapter never invokes the native global `agentmemory stop`. |
| `docker container ls --all --filter name=NAME --format "{{.ID}}"` after a failed stop | `--all` means "Show all containers"; `--filter` means "Filter output based on conditions" ([ls:14–16,40–43][docker-ls-options]); `name` "matches on all or part of a container's name" ([118–139][docker-ls-name]); `--format` uses a Go template and `.ID` means "Container ID" ([391–424][docker-ls-format]). Only a successful empty result for the full UUID name proves absence. |

The platform entrypoint is replaced by the native CLI because that entrypoint
[writes and prints an HMAC secret and rewrites the engine configuration][platform-entrypoint].
The stock CLI supplies the default localhost API with no server secret configured.
Provider keys are read only at runtime from `ModelRoute.api_key_env`, placed only
in the child process environment, and passed through `--env NAME`. Neither argv,
launch YAML nor logs written by this adapter contains a provider key. `HOME` and
`CODEX_HOME` are not reassigned. Ambient memory/provider/proxy settings are not
inherited, so they cannot replace the release's defaults.

This route requires a **local Linux Docker daemon**. A supplied `DOCKER_HOST`
must be `unix:///` followed by an absolute socket path, without authority,
query, fragment, NUL, carriage return or newline; TCP, SSH, named-pipe and malformed
endpoints fail before launch. Without a supplied endpoint, Docker uses its
[documented default local Unix socket][docker-host]. `DOCKER_CONTEXT` and host
Docker configuration are not inherited. Locality is required because bind-mount
sources live on the daemon host ([run:242–265][docker-mount]), while this adapter's
port checks, readiness and supplied loopback model routes address the local host.

`H2H_PORT=P` must be **1024–19512**; the documented native quartet uses REST `P`,
streams `P+1`, viewer `P+2`, and the engine bus `P+46023`. All four must be free.
Binding probes check availability without requesting an existing server's API;
they release their sockets before Docker starts, so allocation races remain
possible. The transport settings use IPv4 loopback consistently.

An upstream defect requires explicit transport configuration: the CLI's
`--port` only sets `III_REST_PORT` ([245–247][cli-port]), while
`renderIiiConfig` rewrites only store paths ([424–443][cli-config]). The engine
template still hardcodes ports ([iii-config:1–37][native-config]); this is open
[#1245][issue-port]. The adapter copies the native YAML values, relocates only
REST/streams/CORS addresses, and explicitly configures the mandatory
`iii-worker-manager`'s port/loopback host. The launch file is mounted at
`/opt/agentmemory/iii-config.yaml`: upstream's
[config selection:400–417][cli-config] explicitly prefers `cwd/iii-config.yaml`
as a user override. Its documented `--data-dir` then rewrites the two store
paths into `/data` using the same upstream rendering path.

For engine configuration, agentmemory pins `iii-hq/iii@iii/v0.11.2`, commit
`2b445957701f94dc5f56f900af314e9d59f3b0f7`. Its
[configuration guide:46–54][iii-ports] shows
`name: iii-worker-manager`, `config.port: 49134`, and the HTTP worker's port.
The [actual manager schema:49–65][iii-manager] declares `port` and `host`;
[registration:225][iii-mandatory] makes it mandatory, and
[builder:456–493][iii-builder] respects an explicit entry without adding a
second manager. REST `config.port`/`config.host` are documented as TCP port and
network interface in [guide:145–176][iii-http]; streams `config.port`/`host` are
documented in [183–195][iii-stream]. No top-level engine `port` is written: the
[pinned schema:28–35][iii-schema] accepts only `modules` and `workers`, despite
the guide's stale top-level example. All storage, memory, queue, observability,
compression and ranking defaults are retained. This is transport/store isolation,
not a replacement implementation of a memory feature.

**Ingestion and recall contract.** `ingest` preserves the supplied session order;
the common harness supplies chronological order. Each session produces one
JSON request:

```json
{
  "hookType": "prompt_submit",
  "sessionId": "DATASET_SESSION_ID",
  "project": "memory-h2h",
  "cwd": "/data",
  "timestamp": "DATASET_DATE_STRING_UNCHANGED",
  "data": {"prompt": "user: ...\nassistant: ..."}
}
```

The [REST handler:300–337][observe] requires the strings
`"hookType, sessionId, project, cwd, and timestamp"`, forwards `data`, returns
201, and registers `api_path: "/agentmemory/observe"`, `http_method: "POST"`.
The [HookPayload contract:139–160][hook-payload] documents the hook name and
`data: unknown`. [observe.ts:129–131][prompt-field] explicitly extracts
`d["prompt"]` into `raw.userPrompt` for `prompt_submit`; synthetic compression
identifies that hook as `conversation` ([12–20][synthetic-type]). The entire
transcript is submitted, without adapter truncation or custom chunking. Source
roles are preserved as transcript labels; this is one submitted conversation
transcript, whose native provenance channel is `user`, rather than a reconstruction
of distinct native role events. A conversation-turn mapping beyond this generic
observation contract is not documented in the cited REST/HookPayload sources.

The observation interface implicitly creates a session from the payload when
needed and sets `startedAt` from its timestamp ([268–299][implicit-session]).
It synchronously awaits the default synthetic write, BM25 insertion, vector
insertion attempt and stream writes before returning `observationId`
([302–360][observe-index]). The adapter checks that acknowledgement and HTTP and
application errors. It does not call session start/end, summarize or internal
index interfaces; session end would introduce asynchronous lifecycle fanout
([api.ts:659–696][session-end], [events.ts:96–144][session-events]).

**Material default:** synthetic compression sets `facts: []`, `concepts: []`,
`importance: 5`, `confidence: 0.3` and
`narrative: truncate(narrativeParts.join(" | "), 400)`
([compress-synthetic.ts:72–106][synthetic]). Its truncation function uses
JavaScript `s.length` and `s.slice(0, n - 1) + "\u2026"`, so at most **400 UTF-16
code units of each session transcript**, including an ellipsis when truncated,
survive in the searchable narrative. The observation write
replaces its raw KV record with the synthetic record ([316–329][observe-index]).
The official internal LongMemEval benchmark bypasses this limitation; the
adapter exposes it as the pinned system's default behavior. It does not enable
`AGENTMEMORY_AUTO_COMPRESS` or retrieve the original dataset text to repair it.

Recall posts `{"query": QUERY, "limit": k}` to `/agentmemory/search`.
The [API handler:403–488][search] documents both fields, requires a nonempty
query and positive integer limit, and registers `http_method: "POST"`.
The adapter accepts `1 <= k <= 100`, matching the native
`MAX_LIMIT = 100` ([search.ts:382–395][search-limit]). Optional `format`,
`project`, `cwd`, `token_budget`, and `agentId` are omitted. The default
`format = 'full'` ([433–440][search-format]) returns
`{observation, score, sessionId}` items ([587–601][search-result]) inside
`{format, results, tokens_used, tokens_budget, truncated}`
([673–688][search-return]). Every `Retrieved.text` serializes the returned
observation to UTF-8 JSON, preserving its text, timestamp and other native
fields; provenance and score come from the reported result fields. No raw-data
expansion, secondary endpoint, reranking or deduplication is added. Hybrid
ranking applies to this primary recall function when vectors exist
([search.ts:17–26][hybrid-primary]). `question_date` is not sent: the cited REST
request schema exposes no as-of/question-date field. Session timestamps remain
available in the returned observations.

**Model routes and costs.** Both roles support OpenAI-compatible HTTP(S) base
URLs, including bases ending in `/v1`. Chat uses `OPENAI_BASE_URL`,
`OPENAI_MODEL`, `OPENAI_API_KEY`: [config.ts:86–97][llm-config] returns the OpenAI
provider configuration, and [openai.ts:26–40,58–67][llm-provider] documents/uses
those variables. The [shared URL builder:90–128][openai-urls] appends
`/chat/completions` without doubling `/v1`.

An explicit embedding route sets `EMBEDDING_PROVIDER=openai`,
`OPENAI_EMBEDDING_BASE_URL`, `OPENAI_EMBEDDING_MODEL`, and
`OPENAI_EMBEDDING_API_KEY`. [config.ts:250–277][embedding-config] documents
provider detection; [embedding/openai.ts:25–85][embedding-provider] documents
these overrides and resolves their values. The same
[URL builder:131–142][embedding-url] selects `/embeddings`.
**Independent base URLs and models work; independent credentials do not work
when a chat key is also configured.** The factory explicitly passes
`OPENAI_API_KEY` ([embedding/index.ts:30–46][embedding-factory]), which wins over
the documented embedding-specific key ([openai.ts:60–68][embedding-provider]).
This source-confirmed defect is open [#1435][issue-key] and [#1119][issue-key-old].
`start` therefore requires both supplied routes to name the **same** credential
environment variable; different references fail before launch. Embedding-only
mode leaves `OPENAI_API_KEY` absent, so the native embedding-specific fallback
works without configuring a chat provider.

For custom embedding models, the documented `OPENAI_EMBEDDING_DIMENSIONS` must
be supplied as the model's actual width. Native
[dimension resolution:15–45][dimensions] knows only three OpenAI model names
(also recognized after a provider prefix) and otherwise guesses 1536. The
fixed `ModelRoute` carries no dimensions; `start` refuses an unrecognized model
without a positive native dimensions setting. It forwards that metadata without
changing model vectors or any ranking option. Open [#1373][issue-width] describes
this wrong-width failure. Upstream [vector insertion:121–155][vector-soft-fail]
soft-fails embedding errors, and [the provider guard:52–74][dimension-guard]
checks output width. Consequently observation acknowledgement alone cannot prove
that the vector index populated; the coordinator must inspect real runtime
acceptance. The adapter makes no test query to either model endpoint.

`needs_llm = False` means the chosen synchronous observe/search functions do not
require a chat LLM: per-observation chat compression is off by default
([config.ts:424–432][compression-default]). That default path makes **zero chat
compression calls per submitted session**; with embeddings configured it attempts
one embedding for the synthetic observation ([observe:323–328][observe-index],
[search:124–134][vector-soft-fail]). Background jobs retain upstream defaults;
consolidation defaults on when a provider is configured
([config.ts:398–421][consolidation-default]). Their total calls are not reported
by these endpoints, so `IngestStats.llm_calls` remains `None`. With neither route
supplied, [config.ts:159–172][noop] selects `noop`, and
[embedding detection/factory][embedding-config] selects no embedding provider;
the runtime is BM25/synthetic. The README's claim of default local embeddings
does not override those pinned source paths. With a chat route but no explicit
embedding route, native key detection selects OpenAI embeddings at the chat URL
with its native default `text-embedding-3-small`; this behavior is recorded in
ingestion notes.

**Reset and on-disk state.** Every `reset`, including a repeated namespace,
closes the old HTTP client, stops only its UUID-named container, and starts a new
container against a fresh data directory. No old data directory is mounted into
the new instance. The namespace guard prevents using another namespace through
the Python adapter. Both in-memory indexes and persisted state are isolated;
project filtering alone is not used as the reset boundary. Older generations
remain beneath workdir for coordinator inspection and are never reused.

Container ownership follows the UUID name even after the `docker run` client
exits. The pinned Docker [run.go:205–244][docker-attach-exit] starts a container
before an attach-stream error can return, so client exit does not prove server
exit. Cleanup always attempts to stop the owned container. A failed stop is
accepted only if the scoped all-states name query succeeds with empty output,
proving that `--rm` already removed it. The documented substring name match is
conservative: any match, query failure or query timeout preserves ownership and
prevents a replacement launch. Cleanup can be retried using the same name.

The native template's file-backed stores are `state_store.db` and `stream_store`
([iii-config.yaml:10–37][native-config]); the CLI rewrites their paths into the
mounted data directory ([424–443][cli-config]). They contain session and memory
state, compressed observations, streams and the persisted indexes. Index
persistence stores its BM25/vector shards through the same KV store
([index-persistence.ts:188–231][persisted-indexes]). Launch YAML and a private
Docker CLI configuration directory also exist under workdir. Server preferences,
pidfiles and any other homedir metadata live in the disposable container
filesystem ([cli.ts:571–616][pidfiles], [config.ts:20–39][env-file]); no host
homedir is mounted. `stop` leaves the bound artifacts and removes the owned
container. It makes no global process kill, Compose teardown or host-service
operation.

**Open issues, corrections and acceptance limits.** Open issues verified through
GitHub on 2026-10-02 are [#1245][issue-port] (port config), [#1435][issue-key] and
[#1119][issue-key-old] (embedding credential override), and [#1373][issue-width]
(custom model dimensions). Their relevant defects were checked against the pinned
code rather than accepting issue descriptions as proof.

Research correction recorded this turn: advertising `--port` does not establish
that the engine binds that port; explicit upstream-supported worker configuration
settled the contradiction. Astra/Max source review was triggered by the conflicting
CLI/README and engine evidence. It rejected a launch using the flag alone, then
accepted the revised config route for transport/store isolation after inspecting
config selection, manager schema/registration and mandatory-worker insertion.
This acceptance is source-only. It is not proof of a successfully launched server.

Another source correction: issue #1245 says `iii-exec` starts only after source
changes, but the pinned engine [exec.rs:67–98][exec-watcher] attempts its pipeline
at boot *after* initializing its watcher. The npm image lacks the stock `src/`
watch root, so that upstream background watcher may fail before spawning the
relative `node dist/index.mjs` command. The error is logged without terminating
the engine ([worker.rs:45–64][watcher-error]); the CLI imports its own worker
after engine readiness ([cli.ts:1454–1459][cli-worker]). The adapter leaves this
stock packaging behavior intact. The generated config was checked against the
source and offline fixtures, not by running the engine.

Lifecycle correction recorded this turn: the first implementation equated
Docker-client exit with container absence and allowed arbitrary `DOCKER_HOST`
values. Pinned Docker start/attach source and daemon-socket/bind-mount docs
disproved those assumptions. The revised implementation retains UUID ownership
until a successful stop or successful empty scoped query, and limits launch to
local Linux Unix-socket endpoints. Regression controls failed against the earlier
implementation (exit 1) before these repairs. The first added fixture also tried
to place NUL in `os.environ`, which the OS rejects before adapter validation;
it was corrected to a newline fixture. A plain RTK-prefixed `docker --help`
returned RTK's own help; `rtk proxy docker --help` recovered native CLI help.
The bounded Astra/Max follow-up source review accepted the revised cleanup and
locality changes and independently returned **27 tests, OK, exit 0** using the
Python 3.13 command below. Its acceptance covers pinned source and mocked
behavior; live launch/cleanup acceptance remains with the coordinator.

Upstream leaves a turn-role/date normalization contract for submitted session
transcripts, a vector-success acknowledgement, and total per-session LLM call
accounting unspecified in the chosen REST interfaces. The adapter preserves
dataset dates as supplied and reports the known truncation, key and dimensions
constraints. Lifecycle, provider reachability, filesystem ownership and retrieval
quality need coordinator runtime acceptance.

**Offline verification.** `test_adapter_agentmemory.py` contains 27 local
integration fixtures that stub HTTP, subprocesses, socket binding and filesystem
creation. They verify exact request bodies, full-transcript submission, date and
role preservation, default response parsing, application errors, credential
references, custom dimensions, explicit transport config, version checking,
namespace/store replacement, local Docker endpoints, cleanup after client exit,
and conservative failed-stop handling. They never access a running
system or model endpoint. Tests use ports 8300, 8301, 8310–8312 and 54333 only as
stubbed values. The test file has an in-memory copy of the fixed interface if the
core builder's `h2h/types.py` is not present; it never writes that file.

The initial plain `python3 -B -m unittest` invocation failed before tests because
the base Python had no `httpx`. Running the same test command in a temporary,
isolated environment with the allowed dependency `httpx==0.28.1` passed:

```sh
rtk env UV_CACHE_DIR=/tmp/memory-h2h-agentmemory-uv UV_NO_CONFIG=1 uv run --offline --no-project --python 3.13 --with httpx==0.28.1 python3 -B -m unittest blueprints/memory-h2h/tests/test_adapter_agentmemory.py
```

Returned result: **27 tests, OK, exit 0**, Python **3.13.15**. The explicit Python
selection is required because the earlier unqualified uv rerun selected 3.14.
These locally authored fixtures are
distinct from unchanged upstream tests and live memory-system acceptance.

[release]: https://github.com/rohitg00/agentmemory/releases/tag/v0.9.29
[tag]: https://api.github.com/repos/rohitg00/agentmemory/git/ref/tags/v0.9.29
[transcript]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/benchmark/longmemeval-bench.ts#L40-L45
[bench-ingest]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/benchmark/longmemeval-bench.ts#L141-L180
[bench-search]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/benchmark/longmemeval-bench.ts#L185-L200
[bench-filter]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/benchmark/longmemeval-bench.ts#L127-L133
[bench-mode]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/benchmark/longmemeval-bench.ts#L305-L315
[load-ingest]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/benchmark/load-100k.ts#L258-L267
[load-search]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/benchmark/load-100k.ts#L320-L328
[eval-adapter]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/eval/runner/adapters/agentmemory.ts#L47-L91
[vectorize-tree]: https://api.github.com/repos/vectorize-io/agent-memory-benchmark/git/trees/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150?recursive=1
[vectorize-registry]: https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/__init__.py#L1-L40
[dockerfile]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/deploy/coolify/Dockerfile#L1-L32
[docker-install]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/deploy/coolify/Dockerfile#L17-L20
[npm-install]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/README.md#L108-L113
[coolify-build]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/deploy/coolify/README.md#L39-L43
[docker-tag]: https://api.github.com/repos/docker/cli/git/tags/477f1252f2391a2b34fdce2e7bd03a0eee660005
[docker-build]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/image_build.md#L24-L78
[health]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/triggers/api.ts#L266-L298
[docker-name]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/man/docker-run.1.md#L514-L527
[docker-rm]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/man/docker-run.1.md#L620-L624
[docker-pull]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/container_run.md#L566-L605
[docker-network]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/man/docker-run.1.md#L529-L540
[docker-mount]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/run.md#L242-L265
[docker-mount-options]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/man/docker-run.1.md#L468-L485
[docker-entrypoint]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/run.md#L932-L975
[docker-env]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/container_run.md#L626-L640
[docker-healthcheck]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/container_run.md#L83
[docker-config]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/docker.md#L216-L230
[docker-host]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/docker.md#L427-L449
[docker-stop]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/container_stop.md#L20-L61
[docker-ls-options]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/container_ls.md#L14-L43
[docker-ls-name]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/container_ls.md#L118-L139
[docker-ls-format]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/docs/reference/commandline/container_ls.md#L391-L424
[docker-attach-exit]: https://github.com/docker/cli/blob/4a63305d74332de5ceba7fcbccbc3cbb7412f5ba/cli/command/container/run.go#L205-L244
[cli-options]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/cli.ts#L168-L214
[data-dir]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/README.md#L250-L255
[platform-entrypoint]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/deploy/coolify/entrypoint.sh#L18-L98
[cli-port]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/cli.ts#L245-L247
[cli-config]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/cli.ts#L400-L443
[native-config]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/iii-config.yaml#L1-L61
[iii-ports]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/docs/how-to/configure-engine.mdx#L46-L54
[iii-manager]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/engine/src/workers/worker/mod.rs#L49-L65
[iii-mandatory]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/engine/src/workers/worker/mod.rs#L225
[iii-builder]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/engine/src/workers/config.rs#L456-L493
[iii-http]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/docs/how-to/configure-engine.mdx#L145-L176
[iii-stream]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/docs/how-to/configure-engine.mdx#L183-L195
[iii-schema]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/engine/src/workers/config.rs#L28-L35
[observe]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/triggers/api.ts#L300-L337
[hook-payload]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/types.ts#L139-L160
[prompt-field]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/observe.ts#L129-L131
[synthetic-type]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/compress-synthetic.ts#L12-L20
[implicit-session]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/observe.ts#L268-L299
[observe-index]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/observe.ts#L302-L360
[session-end]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/triggers/api.ts#L659-L696
[session-events]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/triggers/events.ts#L96-L144
[synthetic]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/compress-synthetic.ts#L72-L106
[search]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/triggers/api.ts#L403-L488
[search-limit]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/search.ts#L382-L395
[search-format]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/search.ts#L433-L440
[search-result]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/search.ts#L587-L601
[search-return]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/search.ts#L673-L688
[hybrid-primary]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/search.ts#L17-L26
[llm-config]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/config.ts#L86-L97
[llm-provider]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/providers/openai.ts#L26-L67
[openai-urls]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/providers/_openai-shared.ts#L90-L128
[embedding-config]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/config.ts#L250-L277
[embedding-provider]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/providers/embedding/openai.ts#L25-L85
[embedding-url]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/providers/_openai-shared.ts#L131-L142
[embedding-factory]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/providers/embedding/index.ts#L30-L46
[dimensions]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/providers/embedding/_dimensions.ts#L15-L45
[vector-soft-fail]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/functions/search.ts#L121-L155
[dimension-guard]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/providers/embedding/index.ts#L52-L74
[compression-default]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/config.ts#L424-L432
[consolidation-default]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/config.ts#L398-L421
[noop]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/config.ts#L159-L172
[persisted-indexes]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/state/index-persistence.ts#L188-L231
[pidfiles]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/cli.ts#L571-L616
[env-file]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/config.ts#L20-L39
[exec-watcher]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/engine/src/workers/shell/exec.rs#L67-L98
[watcher-error]: https://github.com/iii-hq/iii/blob/2b445957701f94dc5f56f900af314e9d59f3b0f7/engine/src/workers/shell/worker.rs#L45-L64
[cli-worker]: https://github.com/rohitg00/agentmemory/blob/v0.9.29/src/cli.ts#L1454-L1459
[issue-port]: https://github.com/rohitg00/agentmemory/issues/1245
[issue-key]: https://github.com/rohitg00/agentmemory/issues/1435
[issue-key-old]: https://github.com/rohitg00/agentmemory/issues/1119
[issue-width]: https://github.com/rohitg00/agentmemory/issues/1373
