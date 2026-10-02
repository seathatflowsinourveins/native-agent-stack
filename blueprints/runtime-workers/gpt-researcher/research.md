> Historical source research for rounds 1–2. Round-3 policy, dispatch, retry and
> accounting corrections are in [README.md](README.md) and
> [round3-verification.json](round3-verification.json); earlier host execution
> authority and overlapping-usage descriptions below are superseded.

# Source review — 2026-09-27

## Round 2 source decisions (recorded before implementation)

The supplied `eval-frameworks/report.md` and `report2.md` select
[DeepResearch-Bench-II at b38f360603db9531b102aef8c166cedb8509b6f6](https://github.com/imlrz/DeepResearch-Bench-II/tree/b38f360603db9531b102aef8c166cedb8509b6f6)
for this direct report-producing worker. Adopt its unchanged evaluator prompt,
rubric scoring and aggregation through the README's `uv sync` installation.
The runner-up is [DeepResearch Bench I at 852f4022d1f98fb707222e395405136e8f0e8d52](https://github.com/Ayanami0730/deep_research_bench/tree/852f4022d1f98fb707222e395405136e8f0e8d52):
RACE/FACT adds reference-report and citation-refetch contracts; it is not the
selected information/analysis/presentation rubric contract. Neither supplies a
direct GPT Researcher runner. Keep only report export, gateway transport and
malformed-output rejection as local glue; remove the local fact-string verdict.

Installed-client preflight found no GPT Researcher, OpenAI SDK or HTTPX in the
builder's Python. No install or native acceptance is claimed. Release v3.7.0
notes and exact source were rechecked. Search-first and find-skills discovery
found the official outer-agent GPT Researcher skill again in the skills.sh
search API; it does not establish an internal SKILL.md loader. No skill install
was run. GitHub CLI authentication/network and web.open were unavailable;
context-mode HTTPS fetched exact public source bytes into external scratch.
The mapping's maintenance evidence is discovery evidence, not measured quality.

Transport references are GPT Researcher `GenericLLMProvider.from_provider`
at the existing source pin; [LangChain OpenAI 1.6.6 client injection](https://github.com/langchain-ai/langchain/blob/langchain-openai%3D%3D1.6.6/libs/partners/openai/langchain_openai/chat_models/base.py#L1022-L1034);
[HTTPX 0.28.1 request hooks](https://github.com/encode/httpx/blob/0.28.1/docs/advanced/event-hooks.md);
and DRB-II `gpt_client.py:85-138`. These expose the narrowly scoped transport
seams needed for headers without editing upstream source. DRB-II's prompt
specifies `results[]` objects with rubric_item, score (-1/0/1), reason and
evidence; a closed JSON schema can enforce that existing wire contract.
Native MCP calls already use `bind_tools`; native planner JSON is otherwise
prompted free text with json_repair, a remaining upstream constraint gap.

Use the upstream dataset's unchanged English task 12, including its original
blocked-reference rules. Freeze full dataset, raw row and prompt SHA256 before
any run. Keep scores as upstream scores: the evaluator defines no global binary
pass threshold. Unit controls here test transport only and are not benchmark
acceptance. No A/B superiority is claimed without matched real runs.

Round-2 anti-pattern handoff for the coordinator's shared log (outside this
worker's edit scope): exact fact strings in a locally written checker cannot
provide the requested upstream research-quality verdict. The old four-test
suite passed unchanged (exit 0), demonstrating only its local contracts.
Missing evaluator rows and native evaluator error rows must also fail transport
completion even when upstream's CLI exits zero. Controls below are retained
with actual fail-first output after execution.

Additional observed corrections: the read-only SQLite connection context in
round 1 closed transactions but not the connection (Python emitted an unclosed
connection ResourceWarning); use `contextlib.closing` and preserve the value-free
read-only control. A synthetic native-CSV receipt control exposed that matching
two report copies did not bind them to previously captured scores when both
copies changed. It failed with `Changed report wrongly accepted alongside old
upstream scores`, exit 1. The adapter now records the original report SHA256 and
rechecks it against both exports and the worker result; the same control and the
unit report-binding control then passed. These checks validate transport only.

The exact DRB-II archive and each pinned file were independently verified
against archive members. Unchanged `aggregate_scores.py` was executed on three
synthetic controls using the frozen upstream task: score 1 produced total 1.0
and blocked_rate 0.0; score 0 produced 0.0/0.0; score -1 produced 0.0/1.0.
Every native aggregation command exited 0. This is execution of the upstream
aggregation component, not a new model evaluation or benchmark-quality result.

`PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate.py` found stale SHA256/byte
counts for the twelve modified, already registered recipe/test files. The
coordinator owns `manifests/evidence.json`, outside this worker's bounded file
ownership. Keep this actual failure in the round-2 receipt; the coordinator
must re-register the final owned files and new adapter/evidence files before
publication. Do not replace that result with an imagined passing validation.

## Round 1 source review (historical)

Scope: a recipe only, on the foundation lane; no installation, provider request,
service startup or git metadata changes. This worker is not adopted by catalog
inclusion. Installed-client check: `importlib.util.find_spec('gpt_researcher')`
returned false. Native help/tests therefore remain host work. Reviewed release
notes next, then the tag source, then dependency source and official docs.

## Decisions and primary sources

- Selected by the user's brief: [GPT Researcher v3.7.0](https://github.com/assafelovic/gpt-researcher/releases/tag/v3.7.0),
  lightweight tag commit `0957c301ed06c2a5857b834358c7227c739041d4`.
- [Tag pyproject](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/pyproject.toml#L25-L31)
  declares version `0.16.0`, Python >=3.12. The [PyPI metadata](https://pypi.org/pypi/gpt-researcher/0.16.0/json)
  supplies wheel/sdist digests. A byte comparison of 122 Python files in the wheel
  against the tag found 67 identical, 55 different. The wheel has neither
  `context/lexical.py` nor `context/select.py`. Use the tag archive, not that wheel.
  The archive digest in pins.json is a local SHA256 of actual downloaded bytes,
  not an upstream signature. The tag has no uv.lock or poetry.lock.
- [Native source install](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/docs/docs/gpt-researcher/getting-started/getting-started.md#L58-L90)
  and [SDK use](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/README.md#L140-L175)
  are the integration references. Generate a local dependency lock from the
  unchanged tag metadata; label it as local integration, not an upstream lock.
- [LLM overrides](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/utils/llm.py#L83-L117)
  reach [ChatOpenAI](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/llm_provider/generic/base.py#L167-L174).
  [LangChain OpenAI 1.6.6](https://github.com/langchain-ai/langchain/blob/langchain-openai%3D%3D1.6.6/libs/partners/openai/langchain_openai/chat_models/base.py#L1274-L1300)
  supports Responses plus `output_version=v0`, required for GPT Researcher's string
  consumer. `temperature: null` is omitted from request parameters (L1551-1580).
- [Keyword filter](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/context/select.py#L1-L36)
  is local BM25 with no embedding model/API. Its supported value is `keyword`,
  not `BM25`. Native `auto` may select a paid service when a key is inherited;
  select `keyword` explicitly.
- [MCP conversion](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/mcp/client.py#L41-L181)
  passes connection fields only and exposes all discovered tools. Native relevance
  selection is not an authorization boundary. A policy file alone cannot enforce
  the stack-worker limits. Research a maintained filtering proxy before wiring.
- Installed search-first and find-skills procedures were used. The
  [skills directory](https://skills.sh/) and its search endpoint found the
  [official GPT Researcher skill](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/skills/gpt-researcher/SKILL.md).
  It teaches an outer agent to invoke GPT Researcher. No internal SKILL.md loader
  was found in this tag's non-test Python or release notes; `gpt_researcher/skills`
  contains Python components. Do not copy or symlink our skill manifest into an
  invented runtime skill directory. Popularity was discovery only.
- The frozen oracle comes from the [Python 3.12 release notes](https://docs.python.org/3.12/whatsnew/3.12.html),
  [PEP 695](https://peps.python.org/pep-0695/), [PEP 701](https://peps.python.org/pep-0701/),
  and [PEP 632](https://peps.python.org/pep-0632/). The facts concern 3.12.0,
  irrespective of later edits to those pages.

Retrieval: context-mode fetch/index and search, plus bounded ctx_execute primary
source comparisons. Shell `gh api` could not connect; context-mode HTTPS worked.
No host package or skill was installed. Read `adoption/manifest.json`, update
guide, convergence architecture, harness defaults, acceptance policy, token
practice, foundation worker/SDK layers and both Codex MCP templates.

## Anti-pattern handoff

These corrections belong in the coordinator's shared anti-pattern log; this
worker is restricted to its recipe and test.

| Assumption rejected | Evidence and prevention |
| --- | --- |
| Equal tag/package version means equal source | Actual wheel/tag comparison above; source archive pin is mandatory for BM25. |
| A config `enabled_tools` key limits GPT Researcher MCP tools | The converter drops it; expose only tools enforced by a source-backed proxy. |
| A directory called skills loads SKILL.md | Checked release and Python loader paths; it contains built-in Python research components. |

## Fail-first observation

Before this directory existed:
`python3 -m unittest discover -s tests -p test_runtime_worker_gpt_researcher.py -v`
returned exit **1**, `Ran 1 test`, `FAILED (failures=1)`;
assertion: `False is not true : README.md`.
Full returned output is in `e2e/offline-red.txt`, with only the worktree path
replaced by `<checkout>`. This is a local structural test, not upstream acceptance.

## Lock resolution and additional source checks

The retained `requirements.in` contains the 140 dependencies read from the
verified tag's `project.dependencies`, plus explicit `ddgs`,
`langchain-openai==1.6.6`, `langchain-mcp-adapters==0.3.2`, build tools and
`pytest==9.1.1`/`pytest-asyncio==1.4.0` for unchanged native tests. Upstream
`requirements.txt:62` supplies the otherwise missing MCP adapter dependency;
`retrievers/duckduckgo/duckduckgo.py:31` imports ddgs. No package was installed.

For each of `requirements`, `proxy-requirements`, `build-requirements`, the
resolution command was uv 0.12.17:

```sh
uv pip compile <name>.in --python-version 3.12 \
  --python-platform x86_64-unknown-linux-gnu --generate-hashes \
  --no-header --no-annotate --output-file <name>.lock
```

The resolver cache was scoped to a temporary directory inside this recipe and
removed afterwards. Initial native resolution returned `Resolved 193 packages
in 1.63s`, exit 0. Adding the unchanged upstream test runners returned
`Resolved 197 packages in 787ms`, exit 0. The final lock hashes are in pins.json;
the installer never re-resolves. Registry digests prove downloaded-byte identity,
not runtime compatibility or acceptance. `--no-build-isolation` keeps build
dependencies inside the separately verified build lock.

The MCP gap is filled by the maintained [FastMCP 4.0.10 proxy](https://github.com/PrefectHQ/fastmcp/blob/v4.0.10/docs/servers/providers/proxy.mdx#L260-L275)
and its [list/call middleware reference](https://github.com/PrefectHQ/fastmcp/blob/v4.0.10/docs/servers/middleware.mdx#L751-L768).
Its MCP2 dependency requires the separate proxy venv. Source inspection of
FastMCP's `MCPConfigTransport` confirms a single-server config delegates directly
without adding a tool-name prefix. The registry-verified fastmcp-slim wheel was
read without installation to confirm the public middleware/result APIs.

Further corrections: QMD `get` returns an embedded resource on success, not
structured content ([v2.8.3 server.ts:462](https://github.com/tobi/qmd/blob/v2.8.3/src/mcp/server.ts#L462));
the proxy must inspect `is_error` to suppress out-of-collection suggestions.
The native FAST/SUMMARY/BROWSE config keys have no runtime consumer found at this
tag; the README distinguishes declarations from effective BM25/global limits.
`researcher.py:910,922` records prefetched URLs without raw_content; the scraper
records actual raw_content, so the oracle does not count prefetched mentions.

Initial `python3 scripts/validate.py` returned exit 1:

```text
Publication validation failed:
blueprints/runtime-workers/gpt-researcher/.research/fastmcp-slim.whl: cannot inspect as UTF-8 publication text
blueprints/runtime-workers/gpt-researcher/.research/source.tar.gz: cannot inspect as UTF-8 publication text
```

Those temporary research downloads and caches were removed, retaining resolution
inputs and measured hashes. This failed publication check is preserved separately
from subsequent verification; it was not a framework execution failure.

Final environment check: MCP's stdio environment whitelist does not include XDG
keys. QMD's existing index therefore gets explicit private `QMD_CONFIG_DIR` and
`INDEX_PATH` overrides ([v2.8.3 collections.ts:112](https://github.com/tobi/qmd/blob/v2.8.3/src/collections.ts#L112),
[store.ts:636](https://github.com/tobi/qmd/blob/v2.8.3/src/store.ts#L636)).
Context-mode gets explicit worker-owned `CONTEXT_MODE_DIR` and project binding;
these are native [v1.0.169 settings](https://github.com/mksglu/context-mode/blob/v1.0.169/src/session/db.ts#L126).
No native shared catalog or credential configuration was read or changed.

Installed ai-memory tool-schema inspection showed that static MCP clients must
supply both `workspace` and `project`. The proxy supplies both from the private
host file, removes alternative `scopes`, sets `global=false` and `answer=false`,
and bounds results. The offline policy control checks an attempted global or
alternate-workspace override. This is a schema read, not an actual memory call.
