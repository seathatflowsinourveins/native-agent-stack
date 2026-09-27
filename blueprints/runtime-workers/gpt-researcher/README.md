# GPT Researcher deep-research runtime worker

This recipe runs the unchanged GPT Researcher **v3.7.0** SDK through the host
OmniRoute gateway, with free DuckDuckGo discovery, local BM25 context selection,
and scoped MCP research tools. Research quality is scored by the pinned upstream
DeepResearch-Bench-II evaluator; the local checker only validates transport.
It is a recipe for coordinator installation and
measurement. No framework installation, gateway call, service start or host
configuration change was performed while building it. Source review and offline
integration checks do not establish host acceptance.

## Pin and install decision

| Artifact | Pin / SHA256 provenance |
| --- | --- |
| Release | [v3.7.0](https://github.com/assafelovic/gpt-researcher/releases/tag/v3.7.0), commit `0957c301ed06c2a5857b834358c7227c739041d4` |
| Selected source | [Commit archive](https://codeload.github.com/assafelovic/gpt-researcher/tar.gz/0957c301ed06c2a5857b834358c7227c739041d4), SHA256 `0363b2e46629ee3add884212d09e6a56d9f7602c2adadff506910191b4c84c5c`, computed from downloaded bytes twice; not an upstream signature |
| Package metadata | `gpt-researcher==0.16.0`, Python >=3.12 ([pyproject.toml:25–31](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/pyproject.toml#L25-L31)) |
| Rejected PyPI wheel | `gpt_researcher-0.16.0-py3-none-any.whl`, SHA256 `392432eea1757fa16462604e6579e425d57aa83f7d1ecc622a5807ada94fc043` |
| PyPI sdist reference | `gpt_researcher-0.16.0.tar.gz`, SHA256 `5892dcd1f6e03b5f6c26eb24f33e5959c599cd06027eceed692e00d2e147035c` |
| PyPI hash authority | [0.16.0 JSON metadata](https://pypi.org/pypi/gpt-researcher/0.16.0/json); wheel bytes independently verified; sdist hash is metadata only |
| Dependency locks | No upstream `uv.lock`/`poetry.lock` exists at this tag. The three `*-requirements.lock`/`requirements.lock` files are local integration locks generated with uv 0.12.17 and PyPI artifact hashes. Exact hashes and upstream metadata hashes are in [pins.json](pins.json). |

The nominally matching PyPI wheel differs in **55 of 122** shared Python files,
and lacks both `context/select.py` and `context/lexical.py`. It cannot provide the
release's BM25 feature. The source install is therefore necessary. The comparison,
discovery channels, rejected assumptions and fail-first observation are recorded
in [research.md](research.md). This is a user-selected candidate, not a new claim
that it outperformed the repository's accepted native workers.

Supported upstream paths at this tag:

| Path | Upstream reference | Decision |
| --- | --- | --- |
| Native source + venv + requirements | [Getting started:58–90](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/docs/docs/gpt-researcher/getting-started/getting-started.md#L58-L90), [CLI:9–26](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/docs/docs/gpt-researcher/getting-started/cli.md#L9-L26) | Selected, using the tag's PEP 517 package metadata and hash-locked dependencies |
| Poetry source installation | [Getting started:90](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/docs/docs/gpt-researcher/getting-started/getting-started.md#L90) | Supported; no upstream lock supplied |
| Published Python package | [README:140](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/README.md#L140) | Rejected due to measured source mismatch |
| Docker build / Compose | [Dockerfile:3,33–35,64](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/Dockerfile#L3), [Compose:4,28](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/docker-compose.yml#L4), [Docker guide:17–22](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/docs/docs/gpt-researcher/getting-started/getting-started-with-docker.md#L17-L22) | Upstream references mutable images. No container is selected, pulled, or launched; no image digest is asserted. |

`install.sh` uses the already installed `uv` and `/usr/bin/python3.12` (or
`GPTR_PYTHON` pointing to another existing Python 3.12). The checked lock target is
**Linux x86_64 / CPython 3.12**. Other Python 3.12+ versions/platforms need their
own resolved lock and qualification. Nothing installs Python or uses sudo.
Source archives and every dependency download are checked against SHA256.
Build tools are installed from the hashed build lock first; source builds disable
build isolation and dependency resolution, preventing unpinned build downloads.

The owned prefix is `$HOME/.local/share/codex-ecosystem/tools/gpt-researcher-3.7.0`.
It contains the source, `venv`, `proxy-venv`, and the separately locked
`grader-source`/`grader-venv`. The proxy venv is necessary:
FastMCP 4.0.10 requires MCP 2, while GPT Researcher requires MCP <2. Caches, runs,
configuration and stores use
`$HOME/.local/state/native-agent-stack/runtime-workers/gpt-researcher/`, mode 0700,
with umask 077. Repeating installation verifies artifacts and converges the same
owned prefixes. A file lock serializes install attempts. No shared executable,
native client account, existing MCP service or gateway configuration is changed.

## Gateway and native context configuration

[config.template.json](config.template.json) is rendered privately by the E2E
runner. The default model lives in `run-e2e.sh` and can be changed with
`GPTR_MODEL`; it is never embedded as a constant in the Python adapter.

| Setting | Value and source |
| --- | --- |
| `FAST_LLM`, `SMART_LLM`, `STRATEGIC_LLM` | `openai:${GPTR_MODEL}`, default `cx/gpt-6-astra-max`; [config.py:85–97,203–220](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/config/config.py#L85-L97) |
| `OPENAI_BASE_URL`, `LLM_KWARGS.base_url`, `api_key` | `http://127.0.0.1:20128/v1`, placeholder `local-loopback`; [utils/llm.py:99–117](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/utils/llm.py#L99-L117), [generic/base.py:167–174](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/llm_provider/generic/base.py#L167-L174) |
| `LLM_KWARGS.use_responses_api`, `output_version` | `true`, `v0`: LangChain OpenAI 1.6.6 supports Responses and preserves the string format GPT Researcher consumes; [chat_models/base.py:1274–1300](https://github.com/langchain-ai/langchain/blob/langchain-openai%3D%3D1.6.6/libs/partners/openai/langchain_openai/chat_models/base.py#L1274-L1300), [GPT consumer:361–398](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/llm_provider/generic/base.py#L361-L398) |
| `LLM_KWARGS.temperature`, `reasoning_effort` | `null`, so omitted from provider parameters ([LangChain:1551–1580](https://github.com/langchain-ai/langchain/blob/langchain-openai%3D%3D1.6.6/libs/partners/openai/langchain_openai/chat_models/base.py#L1551-L1580)). Rely on the gateway's measured `-max` alias. Do not set native `REASONING_EFFORT=max`: its enum only accepts low/medium/high ([config.py:225–231](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/config/config.py#L225-L231)). |
| `LLM_KWARGS.default_headers` | Stable random `x-omniroute-session` per run, shared by nested researchers; [LangChain:1016,1467](https://github.com/langchain-ai/langchain/blob/langchain-openai%3D%3D1.6.6/libs/partners/openai/langchain_openai/chat_models/base.py#L1016). Its value stays private. |
| `streaming`, `max_retries`, `timeout` | `true`, `0`, `180` through `LLM_KWARGS`. GPT Researcher's separate retry loop remains ([utils/llm.py:120–143](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/utils/llm.py#L120-L143)); the run has an overall deadline. |
| `RETRIEVER` | Base `duckduckgo`; actual run `duckduckgo,mcp`, supported comma parsing at [config.py:189–199](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/config/config.py#L189-L199). DuckDuckGo needs `ddgs`, explicitly included in the lock ([retriever:29–49](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/retrievers/duckduckgo/duckduckgo.py#L29-L49)). No Tavily, paid search key or Searx service is used. |
| `CONTEXT_FILTER` | `keyword`: local dependency-free BM25, no model/API/embeddings; [select.py:1–36,99–101](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/context/select.py#L1-L36). Do not select `auto`, which can activate Jev with an inherited key. |
| `KEYWORD_MAX_RESULTS`, `KEYWORD_RELATIVE_THRESHOLD`, `COMPRESSION_THRESHOLD` | `16`, `0.5`, `8000` through environment, read at [select.py:34–35,71](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/context/select.py#L34-L35); native keyword chunks are 1000 characters with 100-character overlap ([lexical.py:77–103](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/context/lexical.py#L77-L103)). |
| `FAST_TOKEN_LIMIT`, `SMART_TOKEN_LIMIT`, `STRATEGIC_TOKEN_LIMIT` | Declared 6000 / 12000 / 8000 in [defaults:14–16](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/config/variables/default.py#L14-L16). SMART is consumed by report generation; STRATEGIC is used on query fallback ([query_processing.py:117–149](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/actions/query_processing.py#L117-L149)). FAST has no runtime consumer found in this pin. |
| `LLM_KWARGS.max_tokens` | **12000 global ceiling**, overriding per-call defaults. This bounds otherwise unbounded query/MCP calls and replaces deep research's hard-coded 4000-token cap ([deep_research.py:373–381](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/skills/deep_research.py#L373-L381)). It is the effective ceiling for all roles; do not claim the declared 6000/8000 values independently apply. Reasoning tokens use this budget too. |
| `BROWSE_CHUNK_MAX_LENGTH`, `SUMMARY_TOKEN_LIMIT` | Set to 4096 / 700 as requested. These are declared upstream keys ([defaults:17–19](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/config/variables/default.py#L17-L19)); no runtime consumers were found at this pin. BM25's actual bounds above provide containment. |
| Deep research and concurrency | `DEEP_RESEARCH_BREADTH=3`, `DEPTH=2`, `CONCURRENCY=2`; [deep_research.py:253–255](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/skills/deep_research.py#L253-L255). `MAX_ITERATIONS=3`, `MAX_SEARCH_RESULTS_PER_QUERY=5`, `MAX_SCRAPER_WORKERS=4`; native defaults/consumers in [defaults](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/config/variables/default.py) and [browser.py:28–34](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/skills/browser.py#L28-L34). |

[gateway.py](gateway.py) supplies a stable random `x-omniroute-session` for
the complete report conversation, including the grader, and a fresh
`Idempotency-Key` for each SDK generation. Its process-local
`GenericLLMProvider.from_provider` adapter injects LangChain's supported
`http_client` and `http_async_client`; HTTPX request hooks attach the headers
after request construction. This is necessary because JSON configuration cannot
contain live HTTP clients. The original factory is restored and both clients
close on exit. References:
[GPT Researcher factory](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/llm_provider/generic/base.py#L146-L158),
[LangChain client injection](https://github.com/langchain-ai/langchain/blob/langchain-openai%3D%3D1.6.6/libs/partners/openai/langchain_openai/chat_models/base.py#L1022-L1034),
[HTTPX hooks](https://github.com/encode/httpx/blob/0.28.1/docs/advanced/event-hooks.md).

The adapter rejects non-`cx/gpt-6` models, unexpected model endpoints,
temperature <=0.1, `json_object`, and strict schemas with open nested objects.
Worker temperature is omitted and SDK retries are disabled. GPT Researcher's
outer retry loop issues new generation attempts with fresh keys; replay
deduplication across that loop is not claimed. Native MCP structured calls use
[tool calling](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/mcp/research.py#L65-L79).
DRB-II uses a closed strict schema matching its original rubric-result prompt,
with `additionalProperties:false` on every object. No gateway Claude route is
configured. Judge default: `cx/gpt-6-astra-max`, configurable via
`GPTR_JUDGE_MODEL`; worker roles use `GPTR_MODEL`, with the same default.

**Remaining structured-output gap:** upstream query/deep-planning methods
request JSON as free text and parse it with `json_repair`; there is no
schema-selection hook in this pinned recipe. They do not send the gateway's
problematic `json_object` mode, but their JSON structure is not constrained at
generation time. No custom planner or prompt classifier was invented. The
gateway owner's cognee 1.6.1 observations inform these transport constraints;
wire behavior, max effort and headers still need independent observation for
this worker. Its authorized database columns cannot prove header values.
Gateway compression and semantic-cache settings are not changed.

## MCP policy and skills

GPT Researcher supports stdio and streamable HTTP connections, but its converter
drops unknown keys such as `enabled_tools` and `cwd`
([mcp/client.py:41–181](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/mcp/client.py#L41-L181)).
Its automatic selection of three relevant tools is not enforcement. Also,
`Config.__init__` resets `mcp_servers` ([config.py:53–62](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/config/config.py#L53-L62));
the runner supplies `GPTResearcher(mcp_configs=...)` explicitly, which deep
research propagates to children ([deep_research.py:442–453](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/skills/deep_research.py#L442-L453)).

[mcp_proxy.py](mcp_proxy.py) is minimal **local integration glue**, following
FastMCP **4.0.10**, commit `34597af15256dad0935809fb4b7959bd4eaf3e59`:
[create_proxy reference](https://github.com/PrefectHQ/fastmcp/blob/v4.0.10/docs/servers/providers/proxy.mdx#L260-L275),
[filter lists and enforce calls](https://github.com/PrefectHQ/fastmcp/blob/v4.0.10/docs/servers/middleware.mdx#L751-L768).
One stdio proxy per server forwards the exact launch commands from
[codex.config.template.toml](../../../adoption/templates/codex.config.template.toml)
with limits from [the stack-worker profile](../../../adoption/templates/codex.stack-worker.config.toml).
It starts no listening service. The proxy middleware filters discovery **and**
execution, blocks resources/prompts, and fails oversized tool output at 32000
characters so the model must narrow the request. This is containment, not a
compression-savings claim.

| Server | Active policy |
| --- | --- |
| context-mode | `ctx_fetch_and_index`, `ctx_search`, `ctx_index`, `ctx_execute`, `ctx_execute_file`, `ctx_batch_execute`; `ctx_upgrade` and `ctx_purge` denied. Native launch env and cwd bind the project to private `WORKER_CWD`. |
| qmd | `query`, `get`; collections `foundation-docs`, `foundation-adoption`, `us-equities-foundation`, `us-equities-catalog`. Lexical-only searches, rerank off, <=5 results; reads require `qmd://collection/path`, <=120 lines. Docids, ambiguous paths, globs, other collections and out-of-scope error suggestions are rejected. This preserves local-only retrieval; no embedding gateway exists. [QMD v2.8.3 query/get source](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L330-L468). |
| ai-memory | `memory_query`, `memory_read_page`, `memory_recent`, `memory_status`, `memory_briefing`; every call gets the private explicit workspace and project. Global/cross-project queries and server-generated answers are disabled; result limits are bounded. The installed MCP schema requires both scope fields for static clients. |
| socraticode | Inactive for this non-coding role. Policy retains exactly `codebase_search`, `codebase_status`, `codebase_list_projects`, `codebase_health` and `SOCRATICODE_WATCHER=manual`. |
| serena / jcodemunch | Not loaded: this is a research worker. No launch commands invented. |
| headroom | Inactive: native BM25 plus bounded tool responses are selected. Policy retains only `headroom_compress`, `headroom_retrieve`, `headroom_stats` if a later measured gap justifies it. |

`context-mode` execution tools retain the authority of their native launch;
project binding and tool allowlists are not a new operating-system sandbox.
The existing QMD index must already cover the four named collections; the recipe
neither reindexes unrelated directories nor installs MCP servers.
Its private `QMD_CONFIG_DIR` and `QMD_INDEX_PATH` explicitly retain the existing
named catalog under the worker's isolated XDG environment. Upstream accepts
`QMD_CONFIG_DIR` ([collections.ts:112–125](https://github.com/tobi/qmd/blob/v2.8.3/src/collections.ts#L112-L125))
and `INDEX_PATH` ([store.ts:636–653](https://github.com/tobi/qmd/blob/v2.8.3/src/store.ts#L636-L653)).
Context-mode uses its supported `CONTEXT_MODE_DIR` for worker-owned session,
content and statistics stores; `CONTEXT_MODE_PROJECT_DIR` binds the project
([1.0.169 session/db.ts](https://github.com/mksglu/context-mode/blob/v1.0.169/src/session/db.ts)).
The SDK's stdio environment is a whitelist, so these keys are explicitly passed
to each backend; they are not assumed to survive through inherited XDG variables.

No runtime **SKILL.md loader was found** in v3.7.0 release notes or non-test
Python. The official [outer-agent skill](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/skills/gpt-researcher/SKILL.md)
teaches Codex/Claude to call GPT Researcher; the internal `skills/` directory
contains Python components. Native installation/help remains untested here, so
this is a scoped source finding. The worker's startup record lists
`skills_at_start.listed_at_start=[]`, and receipts retain
`activation_events=[]`. This local declaration is not a native skill event.
The E2E currently cannot prove SKILL.md activation, and no skill installation
or activation is claimed.

If a qualified future runtime adds SKILL.md loading, the only permitted project
installation call is the coordinator's installer below. These options are
**pending the skills-program PR**; this recipe does not execute the call for
v3.7.0. The regression test checks the documented future call and the empty
current inventory.

```sh
# From the repository root; worker_workspace is the private worker workspace.
PYTHONDONTWRITEBYTECODE=1 python3 tools/adoption/install_skills.py \
  --manifest blueprints/runtime-workers/skills/manifest.json \
  --project-dir "$worker_workspace" --agent universal
```

Activation acceptance then requires actual `skill-trigger` or `skill-load`
events in the framework's own trace, with the loaded skill name and source
revision. Files on disk, discovery lists and our receipt declarations alone
do not prove activation. Do not add invented framework events or symlinks.

## Upstream verdict and frozen task

The primary grader is [DeepResearch-Bench-II](https://github.com/imlrz/DeepResearch-Bench-II/tree/b38f360603db9531b102aef8c166cedb8509b6f6),
pinned exactly to **`b38f360603db9531b102aef8c166cedb8509b6f6`**, as selected by
the supplied upstream eval-framework reports. [pins.json](pins.json) freezes the
downloaded commit archive, upstream `uv.lock`, evaluator, client, aggregator
and dataset hashes. `install.sh` follows its [documented `uv sync` installation](https://github.com/imlrz/DeepResearch-Bench-II/blob/b38f360603db9531b102aef8c166cedb8509b6f6/README.md#L287),
using `uv sync --locked`, the existing Python 3.12 and a separate owned venv.
The upstream lock pins requests 2.32.5 and python-docx 1.2.0; it is distinct from
our worker dependency locks. Native installation/build acceptance remains
unrun, including upstream project build dependencies.

Runner-up [DeepResearch Bench I](https://github.com/Ayanami0730/deep_research_bench/tree/852f4022d1f98fb707222e395405136e8f0e8d52)
is pinned to **`852f4022d1f98fb707222e395405136e8f0e8d52`**. It supplies RACE
report quality and FACT citation scoring, including Jina retrieval/refetching.
DRB-II was selected because its frozen information, analysis and presentation
rubrics directly fit this worker, without adding that separate citation
pipeline and refetch drift. Neither benchmark executes the direct worker, so
report export remains a documented local adapter.

[e2e/task.json](e2e/task.json) selects upstream **idx 12**, “Research Report on
AI-Enhanced Portfolio Management,” English, CC BY 4.0. The original dataset row
has 43 information, 7 analysis and 6 presentation rubric items. The worker
receives the unchanged upstream `prompt`, including its blocked-reference
rules; the grader receives the unchanged raw JSONL row. Full dataset, row and
prompt SHA256 are checked before generation. This is a single research
benchmark task, with no broker or order operation. It does not establish
full-suite quality or official leaderboard comparability.

[e2e/check.py](e2e/check.py) only rejects missing, empty, non-text or invalid
UTF-8 reports and exports the original bytes as
`frozen-reports/gptr/idx-12.md`. It gives no quality verdict. The old local
Python-fact assertion grader has been removed. The adapter in
[e2e/grader.py](e2e/grader.py) invokes these unchanged upstream entry points:

```sh
python run_evaluation.py --pdf_dir frozen-reports \
  --tasks_jsonl tasks-and-rubrics.jsonl --out_jsonl drb-result.jsonl \
  --max_workers 1 --max_retries 2 --chunk_size 0
python aggregate_scores.py --input drb-result.jsonl \
  --tasks-file tasks-and-rubrics.jsonl --output-prefix scores
```

The runnable adapter also sets a private log path and `--max_paper_chars` to
the actual report length so the upstream reader does not silently truncate it.
It wraps only [`gpt_client.requests.post`](https://github.com/imlrz/DeepResearch-Bench-II/blob/b38f360603db9531b102aef8c166cedb8509b6f6/gpt_client.py#L85-L109)
for headers/strict output and supplies GPT-6 judge configuration; rubric prompts,
native validation, all `-1/0/1` scores and aggregation stay upstream.

DRB-II supplies scores, **not a universal binary pass threshold**. Its five
native CSVs are the metric authority. The adapter rejects missing, duplicate,
wrong-task, error or malformed native rows before aggregation; an all-zero or
all-blocked result remains an upstream low score. Upstream can exit zero with
missing inputs and append error rows, so process exit alone is insufficient.
Known-pass/high-score, known-fail/zero-or-blocked-score and malformed controls
exercise this transport contract without claiming a real model evaluation.

## Ports, ownership and lifecycle

| Resource | Mapping / ownership |
| --- | --- |
| Worker SDK and grader | No listener; no container, volume or network is created |
| MCP policy proxies | stdio only; no worker port |
| Existing OmniRoute dependency | `127.0.0.1:20128/v1`; external gateway, never rebound by this recipe |
| Allowed future worker listeners | `127.0.0.1:3730-3799` only; none allocated here |

Ports 3710–3729 and 5433–5439 belong to the S3 memory arms; 3800–3819 belongs to
cognee. Every future Docker container, volume and network must have both the
name prefix `rw-gpt-researcher-` and the label
`com.native-agent-stack.owner=gpt6-omniroute-framework-integration`.
Cleanup must select a literal owned name or that owner label; never
`docker system prune`. This native recipe has no Docker cleanup commands.

After coordinator installation, create a private 0600 `host.json` from
[host.template.json](host.template.json) at the owned state root, supplying
this host's existing paths and memory scope. `GPTR_HOST_FILE` can point to
another private file outside the checkout. Then run `bash run-e2e.sh`.
Both model overrides must remain GPT-6 gateway IDs. The runner clears inherited
provider configuration, disables dotenv discovery and Python bytecode, and
preserves native MCP HOME. DRB-II refuses a `.env` in its owned run/source paths
before importing its client.

Runs are serialized. Research and grading each have a 30-minute deadline;
the outer process-group deadline is 3700 seconds, followed by a 20-second kill
grace period. Each attempt uses a fresh private directory; failures, raw
reports/source text, framework events, native evaluator output, CSVs and logs
remain there. Host cancellation/descendant cleanup must still be observed.

[receipt.py](e2e/receipt.py) rereads the frozen task, original exported report,
actual upstream result rows and native CSVs, verifies artifact hashes, and
publishes only metrics and sanitized metadata. `execution_complete=true`
means grading completed; it is not a quality pass. Gateway and QMD observations
are reported separately and never substitute for upstream scores. The original
benchmark prompt is not extended merely to force a QMD call.

The gateway observer reads only the nine already authorized `call_logs`
columns through SQLite `mode=ro`; the connection is explicitly closed.
Time-window rows do not establish exclusive caller attribution, and worker and
judge usage may overlap. No counters are summed. DRB-II's successful-batch usage
omits failed attempts; retain that limitation and separate provider counters.
Public receipts omit raw report/rubric text, host paths and request/session IDs.

## Evidence and remaining host checks

Round-1 [offline-verification.json](e2e/offline-verification.json) is historical
local evidence for the removed checker. The actual round-2 fail-first and final
results are in [round2-verification.json](e2e/round2-verification.json), including
the publication validator's stale shared-manifest hash failure and the
coordinator handoff. Round-2 controls cover unchanged report
export, high/low/malformed upstream rows, frozen bytes, dynamic headers, strict
nested schemas, GPT-6 route restrictions, scoped MCP policy, missing-grader
receipts and the conditional skills installation contract. They are integration
tests, not upstream research acceptance:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_runtime_worker_gpt_researcher.py -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate.py
```

No framework/grader installation, service startup, live model run or A/B
experiment was performed in this round. The coordinator still needs to run the
native installation, `bash run-upstream-tests.sh`, and real E2E; observe free
retrieval, scoped MCP1/MCP2 operation, Responses streaming, both worker and judge
headers/effort, and process cleanup. Native planner JSON constraints and
SKILL.md activation remain the explicit source gaps described above.

For an A/B comparison, freeze the same upstream task row, judge model,
generation bounds and tool policy across arms; retain both original reports
under separate arm directories and let the same upstream evaluator/aggregator
score them. Counterbalance order and preserve failed attempts and unknown
usage. No locally authored score or unmeasured improvement claim replaces
that comparison. GPT-6 judging differs from upstream's GPT-5.5 default.

Recovery starts by inspecting retained failed attempts. Retirement removes
only the literal owned prefix/state after preserving required evidence. This
bounded recipe work does not change dashboard or shared adoption manifests.
