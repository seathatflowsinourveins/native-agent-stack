# memsearch v0.4.21 adapter

This arm uses memsearch's documented **Python client**, with the requested local
ONNX embedding profile and a private Milvus Lite database. The upstream client
library and its dependencies are permitted system dependencies; the adapter
itself uses only the Python standard library. Importing or building the adapter
does not import memsearch or access the network.

The release resolves to commit
[`2a4652fa086fbd45e92bfd8da7781ebe1642baa7`](https://github.com/zilliztech/memsearch/commit/2a4652fa086fbd45e92bfd8da7781ebe1642baa7).
The tagged [package metadata, lines 5–16](https://github.com/zilliztech/memsearch/blob/v0.4.21/pyproject.toml#L5-L16)
names `memsearch`, specifies `version = "0.4.21"`, and lists Python 3.13.
The [release notes](https://github.com/zilliztech/memsearch/releases/tag/v0.4.21)
include the fix preventing read paths from creating missing collections.

## Install and launch

Upstream's literal install example is:

> `pip install "memsearch[onnx]"` — "ONNX Runtime — bge-m3 int8, CPU, no API key"

Source: [getting-started.md, lines 11–24](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/getting-started.md#L11-L24).
The provider also documents
> `uv add 'memsearch[onnx]'`

in [embeddings/onnx.py, lines 1–5](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/embeddings/onnx.py#L1-L5).
For the coordinator's existing Python environment, constrain that documented
distribution to the required release:

```sh
python3 -m pip install 'memsearch[onnx]==0.4.21'
```

The `==0.4.21` constraint is an adaptation of the upstream install example,
supported by the release metadata above; upstream does not print that literal
pinned command. Install into the interpreter running the harness. The adapter
uses `sys.executable`, and checks `importlib.metadata.version("memsearch") ==
"0.4.21"` before constructing a client in every child. No installation occurs
inside `start`.

`start` allocates a private `memsearch-*` directory within `workdir` and runs a
short-lived Python child that imports and constructs the documented client:

```python
from memsearch import MemSearch

memory = MemSearch(
    paths=[private_memory_directory],
    embedding_provider="onnx",
    milvus_uri=private_milvus_db_path,
)
```

Upstream's entry-point example is [python-api.md, lines 3–12](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L3-L12).
The child bridge adapts the documented `asyncio.run(main())` pattern
([lines 329–337](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L329-L337));
the subprocess and JSON envelope are harness plumbing, with no additional
memsearch API or daemon. `memory.close()` runs after startup, indexing, search,
and failures inside those operations.

**Launch limitation:** this embedded Milvus Lite profile has no documented
memsearch HTTP listener. `H2H_PORT` is unused, and no loopback port is allocated
by the adapter. A URI ending in `.db` is the documented local route
([python-api.md, lines 45–53](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L45-L53)).
The generic harness requirement to expose every arm on `H2H_PORT` cannot be
implemented through this upstream interface. The open request for a resident
`memsearch serve --socket/--http` is [issue #780](https://github.com/zilliztech/memsearch/issues/780).
No custom HTTP server is added. Milvus Lite may manage its own internal child;
the upstream close implementation releases its database handle and attempts to
release that Lite server ([store.py, lines 405–418](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/store.py#L405-L418)).

## Public interface and parameter evidence

These are the only memsearch calls and parameters used. The adapter invokes no
memsearch HTTP endpoints or CLI commands.

| Call or field | Quoted upstream specification | Pinned source |
| --- | --- | --- |
| `MemSearch(paths=...)` | `paths`: "Directories or files to index" | [python-api.md:45](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L45) |
| `embedding_provider="onnx"` | "Embedding backend"; the supported list includes `"onnx"` | [python-api.md:46](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L46) |
| `milvus_uri=.../milvus.db` | "local `.db` path for Milvus Lite" | [python-api.md:51](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L51) |
| `await memory.index_file(path)` | "Index a single file. Returns the number of chunks indexed." `path`: "Path to a markdown file" | [python-api.md:147–161](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L147-L161) |
| `await memory.search(query, top_k=k)` | `query`: "Natural-language search query"; `top_k`: "Maximum number of results" | [python-api.md:165–176](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L165-L176) |
| Returned `content` | "The chunk text" | [python-api.md:178–189](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L178-L189) |
| Returned `source` | "Path to the source markdown file" | [python-api.md:178–189](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L178-L189) |
| Returned `score` | "Relevance score (higher is better)" | [python-api.md:178–189](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L178-L189) |
| `memory.close()` | "Release the Milvus connection and other resources." | [python-api.md:275–281](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L275-L281) |

Each session becomes one UTF-8 Markdown file, with its session ID, unchanged
dataset date string, and every user/assistant turn in its original order:

```markdown
# Session <session_id>

Date: <unchanged dataset session date>

user: <unchanged content>

assistant: <unchanged content>
```

Upstream documents saving exchanges as Markdown before indexing
([python-api.md, lines 302–326](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L302-L326)).
It does not specify a LongMemEval conversation schema. The role/date wrapper
above is harness serialization, not an upstream summarization format. Filenames
use an ordinal and a hash of the session ID, so dataset IDs cannot select paths.
The child awaits `index_file` for each path in the supplied session order.
It indexes only that file, propagates its failures, and leaves chunking to
memsearch ([core.py, lines 159–200](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L159-L200)).
Writing all input files before this loop does not expose later files to the
earlier `index_file` calls. A failed ingestion requires `reset` before recall.

Recall returns the full reported chunk `content` and `score` without extra
ranking, truncation, expansion or rereading source files. A reported source path
is mapped to the original session ID only when it exactly matches a file this
instance indexed. Missing/unmapped sources produce empty `session_ids`; no gold
answer-session labels are consulted. `question_date` is unused: the documented
search signature has no date parameter
([core.py, lines 222–264](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L222-L264)).
Dates are stored in the original Markdown, but are not guaranteed to occur in
every retrieved chunk. Headings inside turns participate in the normal chunker;
large sections can split, and the stored record has no separate date field
([chunker.py:93–139](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/chunker.py#L93-L139),
[core.py:495–505](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L495-L505)).

## Defaults, routes and reference harnesses

**Verified default distinction:** the Python API's default provider is
`"openai"`, as both its constructor and the tagged evaluation explain
([core.py:58–75](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L58-L75),
[evaluation/README.md:117–120](https://github.com/zilliztech/memsearch/blob/v0.4.21/evaluation/README.md#L117-L120)).
The configuration guide's description of ONNX as "default"
([configuration.md:123–131](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/home/configuration.md#L123-L131))
must not be generalized to Python. This adapter explicitly selects ONNX because
the task requests that profile; `"local"` is a separate sentence-transformers
provider ([embeddings/__init__.py:24–46](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/embeddings/__init__.py#L24-L46)).

All remaining retrieval/indexing settings are untouched: ONNX model
`gpahal/bge-m3-onnx-int8`, provider batch size 32 and tokenizer limit 8192
([onnx.py:22–66](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/embeddings/onnx.py#L22-L66));
chunk size 1500, overlap 2, default collection `memsearch_chunks`, no ignore
rules, and disabled optional reranker
([core.py:58–88](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L58-L88)).
Search uses upstream's dense cosine + BM25 hybrid search and its default RRF
([store.py:242–297](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/store.py#L242-L297)).
The Python constructor directly uses its arguments, so the adapter does not
inherit host/global CLI TOML settings ([core.py:77–97](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L77-L97)).

No generative LLM is involved in this ingestion/recall path. Indexing embeds
chunks, and search embeds the query
([core.py:202–214](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L202-L214),
[core.py:247–264](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L247-L264)).
Thus the source establishes zero generative calls per session; upstream does
not expose a call-usage counter, so `IngestStats.llm_calls` remains `None` under
the fixed interface. The `llm` argument is unused, including when the common
runner supplies it. Optional `compact` would use an LLM, but it is not invoked
([python-api.md:199–220](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L199-L220)).

**OpenAI-compatible routes:** the selected ONNX embedding role cannot use one.
`start(..., embed=route)` raises a clear error; the coordinator must supply
`embed=None` for this arm. The upstream factory forwards `base_url` only to its
OpenAI provider ([embeddings/__init__.py:97–110](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/embeddings/__init__.py#L97-L110)).
The alternative OpenAI provider documents `embedding_base_url`, but changing
providers would change the requested profile
([python-api.md:45–50](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L45-L50)).
There is no LLM endpoint to configure in the chosen path. No route key is read,
passed, printed or written by this adapter.

The following reference implementations were examined before implementation:

- **Own embedding evaluation:** [evaluation/README.md:15–25](https://github.com/zilliztech/memsearch/blob/v0.4.21/evaluation/README.md#L15-L25)
  uses Markdown memory logs and memsearch's heading chunker. Adopted: native
  Markdown indexing and the evaluated ONNX provider. Its corpus is private
  ([lines 5–7](https://github.com/zilliztech/memsearch/blob/v0.4.21/evaluation/README.md#L5-L7)).
  **Upstream benchmark setting, not applied:** removing comments and chunks
  shorter than 50 characters; query generation/translation using an LLM.
- **Own executable reranking evaluation:**
  [evaluation/rerank_evaluate.py:88–122](https://github.com/zilliztech/memsearch/blob/v0.4.21/evaluation/rerank_evaluate.py#L88-L122)
  and [reranking-evaluation.md:31–49](https://github.com/zilliztech/memsearch/blob/v0.4.21/evaluation/reranking-evaluation.md#L31-L49).
  Adopted: the distinction between ordinary search and an optional reranking
  experiment. **Upstream benchmark setting, not applied:** frozen Chinese
  BGE-M3 top-10 candidates reused in English; Jev `jev-1.13.0`; Voyage
  `rerank-3`, `top_k=10`, `truncation=false`. This arm performs fresh native
  search for each question and leaves optional reranking disabled.
- **Vectorize reference:** no memsearch adapter was found in the recursive
  repository tree or [provider registry](https://github.com/vectorize-io/agent-memory-benchmark/blob/f618ed7b1f0eb9cad7b42e876f91a42f0eadb150/src/memory_bench/memory/__init__.py#L1-L40)
  at commit `f618ed7b1f0eb9cad7b42e876f91a42f0eadb150`. No memsearch-specific
  request format was taken from it. This is a bounded finding about that
  revision, not a claim about all integrations.

## Isolation and disk state

`reset(namespace)` selects a newly allocated question directory and a new
Milvus Lite URI inside this instance's private root, even for repeated resets
of the same namespace. It clears the source mapping and rejects operations for
any earlier namespace. All subsequent calls pass only the new directory and
database. This implements upstream's documented strongest isolation:

> "Each user gets a physically separate database file."

Source: [python-api.md, lines 450–460](https://github.com/zilliztech/memsearch/blob/v0.4.21/docs/python-api.md#L450-L460).
An empty ingestion returns no results locally because v0.4.21's native search
requires an existing collection ([core.py:247](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L247)).
Each child closes the upstream client before exit; `stop` forgets the adapter's
active state and is idempotent. It does not stop host services or delete caller
files. Earlier private stores stay on disk for the coordinator's cleanup, and
the adapter provides no interface to reconnect to them.

Disk holds the raw role/date-labelled Markdown transcripts and the derived
Milvus chunks, vectors, source/heading/line metadata and BM25 index
([core.py:495–505](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L495-L505),
[store.py:152–178](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/store.py#L152-L178)).
The `.db` URI can be a file or directory: Lite 3.x uses a directory
([store.py:50–65](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/store.py#L50-L65)).
Upstream constrains Lite/pymilvus versions without fully pinning dependencies
([pyproject.toml:18–29](https://github.com/zilliztech/memsearch/blob/v0.4.21/pyproject.toml#L18-L29)).
Model assets are separate from conversation storage: the default ONNX model is
approximately 558 MB and normally caches under `~/.cache/huggingface/hub/`
([evaluation/README.md:98–115](https://github.com/zilliztech/memsearch/blob/v0.4.21/evaluation/README.md#L98-L115),
[lines 135–138](https://github.com/zilliztech/memsearch/blob/v0.4.21/evaluation/README.md#L135-L138)).
The provider tries cache-only reads first, then downloads missing assets
([onnx.py:69–116](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/embeddings/onnx.py#L69-L116)).
`start` may therefore download model assets on the coordinator's first actual
run. The public constructor does not supply a cache-directory or model-revision
parameter; those defaults are not patched by the adapter.

## Open upstream issues and verification scope

The following issues were open when read on 2026-10-02. Their reports are leads,
not independently reproduced acceptance findings:

- [#779](https://github.com/zilliztech/memsearch/issues/779): API/config provider
  remains OpenAI despite descriptions of ONNX defaults. Explicit ONNX selection
  resolves this for the requested arm; the tagged source verifies the distinction.
- [#780](https://github.com/zilliztech/memsearch/issues/780): requests official
  resident server mode and reports Lite locking plus repeated model-load cost.
  This adapter serializes operations, uses private databases, and calls upstream
  `close`; it does not promise warm resident-server latency.
- [#750](https://github.com/zilliztech/memsearch/issues/750): unpaginated
  `indexed_sources()` can exceed a gRPC limit during whole-directory cleanup.
  The issue reports Zilliz Cloud and leaves Lite unverified. This adapter uses
  `index_file`, which does not invoke whole-directory cleanup; the per-source
  hash query remains upstream-owned
  ([core.py:159–200](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/core.py#L159-L200),
  [store.py:353–372](https://github.com/zilliztech/memsearch/blob/v0.4.21/src/memsearch/store.py#L353-L372)).
- [#747](https://github.com/zilliztech/memsearch/issues/747): intermittent macOS
  ONNX Runtime aborts after indexing, attributed by the reporter to telemetry
  during process exit. Defaults remain unchanged; a nonzero child exit fails
  ingestion even if some records were written.

Capability verification found no installed `memsearch` executable or
distribution, then examined the v0.4.21 release notes, tagged source and tagged
docs. No installed-client help or runtime acceptance is claimed. Conflicting
provider-default descriptions and the embedded/HTTP launch mismatch triggered
an Astra/Max source review; it accepted the explicit requested ONNX profile and
documented embedded route, while retaining the `H2H_PORT` limitation above.

Offline verification command, from the worktree root:

```sh
python3 -B -m unittest blueprints/memory-h2h/tests/test_adapter_memsearch.py
```

The authored tests stub subprocess execution and execute the exact bridge with
a fake upstream client. They verify public constructor parameters, ordered
`index_file` awaits, `search(query, top_k=k)`, full-text/provenance mapping,
fresh-store reset, release enforcement and `close()` on operation failure.
These are synthetic integration checks, not unchanged upstream tests or live
memory-system/model acceptance. No memory system was installed, no service or
model was run, and no prohibited port was used during this source build.
