# GPT Researcher deep-research runtime worker

This recipe runs the unchanged GPT Researcher **v3.7.0** SDK through the host
OmniRoute gateway, with free DuckDuckGo discovery, local BM25 context selection,
and scoped MCP research tools. It is a recipe for coordinator installation and
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
It contains the source, `venv`, and `proxy-venv`. The second venv is necessary:
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

**Header gap:** static `default_headers` supports affinity, but a fresh
`Idempotency-Key` per logical call cannot be generated by this pin's JSON config.
LangChain exposes programmatic HTTP-client hooks, but GPT Researcher's nested
researchers reload JSON rather than sharing a supported client-factory hook.
The recipe does not reuse a constant idempotency key across calls. Retry dedup is
therefore unqualified and duplicate retries can cost tokens. Temperature is
omitted; streaming is enabled. The gateway owner's supplied measurements support
the max alias and tool requests; actual headers, omission, Responses string
compatibility and effort at this framework pin still require host observation.
Gateway compression/semantic-cache settings are not modified or relied on.

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

No runtime **SKILL.md loader was found** in the tag's release notes or non-test
Python. The official [outer-agent skill](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/skills/gpt-researcher/SKILL.md)
teaches Codex/Claude to call GPT Researcher; the internal `skills/` directory
contains Python components. The pinned skills in
[adoption/skills/manifest.json](../../../adoption/skills/manifest.json), already
installed at `$HOME/.agents/skills`, are therefore not symlinked into an invented
directory. Receipts explicitly record no observed SKILL.md usage. Native help
after installation remains part of validating this qualified absence claim.

## Coordinator operation and frozen acceptance

After review, the coordinator can run `bash install.sh`. Then create a private
`host.json` from [host.template.json](host.template.json) at the state root above,
fill in this host's existing prefixes, native PATH, checkout and memory workspace/project,
and set mode 0600. Host paths are never committed. `GPTR_HOST_FILE` can point to
another private 0600 file outside the checkout. The worker clears inherited
provider configuration, disables dotenv loading, and retains native MCP HOME.

Run `bash run-e2e.sh` from this directory. `GPTR_MODEL` overrides the default
gateway model. Changing model/config/oracle starts a new acceptance condition;
keep failures. There is no intake or additional approval built into the recipe.
Runs are serialized, internal execution has a 30-minute deadline, and a 1900-second
process-group deadline kills lingering descendants. Every attempt gets a new
private directory; ordinary errors and outer deadline failures retain a receipt.
No service remains intentionally running. Do not claim cancellation cleanup until
the coordinator has checked actual descendant processes on the host.

[e2e/task.json](e2e/task.json) freezes a real deep-research question about
CPython **3.12.0**: PEP 695, PEP 701, and removal of `distutils` under PEP 632.
[check.py](e2e/check.py) was written before any native run. It requires the three
explicit fact statements as bullet lines and >=3 distinct fetched HTTPS URLs
from the allowed primary domains. Fragment variants do not inflate the count;
outside-domain URLs, absent pages and snippets fail. The native SDK's actual
`get_research_sources()` entries with substantial `raw_content` prove page
retrieval; merely visiting/searching/mentioning a URL does not. The checker never
fetches missing citations to repair a report. DuckDuckGo's tag implementation
caps snippets and forces actual scraping
([retriever:4–29](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/retrievers/duckduckgo/duckduckgo.py#L4-L29)).

DuckDuckGo's `query_domains` filter is currently a TODO; nested deep researchers
also do not propagate that argument. The report oracle enforces primary-domain
citations, but this is **not an outbound network domain allowlist**. MCP results
from the local catalog are process context and must not appear as Python fact
citations. Native MCP tool selection may skip QMD; acceptance requires a logged
QMD execution with a nonempty returned result, so a skipped call fails visibly.

Private attempts retain the raw report, source text, framework logs/events,
stdout/stderr and actual check result. [receipt.py](e2e/receipt.py) independently
re-evaluates the checker and reads only the nine authorized `call_logs` columns
from the live gateway database through SQLite `mode=ro`. It never reads another
table, schema metadata or credential store. Rows are limited to the run window;
with no session/request identifiers permitted, overlapping caller attribution
remains uncertain. Counters are retained per row without summing cache subsets.
At least one matching successful Responses/max row corroborates a pass; zero
rows, missing effort, unavailable DB, absent QMD evidence or failed research do
not pass. Public receipts contain no raw content, host paths, emails or IDs;
unexpected gateway strings are redacted and citation URLs are hashed.

## Evidence and remaining host work

| Class | Status / interpretation |
| --- | --- |
| Upstream source read | Tag, primary release/package metadata, byte comparison, provider/MCP implementation and frozen fact references inspected. [research.md](research.md) records provenance. |
| Structural/local integration tests | `python3 -m unittest discover -s tests -p test_runtime_worker_gpt_researcher.py -v`: **4 passed**, exit 0. Fail-first exit 1 is retained in [offline-red.txt](e2e/offline-red.txt); exact pass output and publication validation are in [offline-verification.json](e2e/offline-verification.json). Checker/proxy/receipt controls are synthetic and never native acceptance. |
| Unchanged upstream tests | Not run here because installation is reserved for the coordinator. After install, run `bash run-upstream-tests.sh`; selected names and exact command are retained in that script. It does not make a model request. |
| Host installation / live E2E | Not run. Validate import/build dependencies, free retrieval availability, mixed MCP1/MCP2 transport compatibility, scoped server behavior, Responses streaming/string output, actual headers and effort, citation quality, and timeout/process cleanup. |
| Token efficiency | Native BM25, bounded retrieval and tool counts configured. No measured saving, complete per-run provider attribution, GPU run or new upstream acceptance is asserted. |

To recover, inspect the private failed attempt before rerunning installation or
E2E. Do not delete failures to obtain a green receipt. Retirement consists only
of removing this recipe's owned prefix/state after archiving required evidence;
the recipe never stops or removes existing production services. No dashboard,
shared manifest or catalog adoption status is edited by this bounded worker.
