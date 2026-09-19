# Native commands and direct results

These commands distinguish actual recorded runs from prospective integration.
The catalog's candidate commands are upstream entry points; unversioned examples
can move and must be locked before a reproducible deployment. They do not claim
every catalogued framework was installed or executed.

## Use the catalog without loading all of it

The native QMD CLI has a dedicated local index and two deliberately scoped
collections on the authoring host. To adopt a different checkout, set
`STACK_REPO` to that checkout and add these collections to your own index:

```bash
qmd --index native-agent-stack-catalog collection add \
  "$STACK_REPO/catalogs/us-equities" --name us-equities-catalog --mask '**/*.md'
qmd --index native-agent-stack-catalog collection add \
  "$STACK_REPO/blueprints/us-equities" --name us-equities-foundation --mask '**/*.md'
qmd --index native-agent-stack-catalog update
qmd --index native-agent-stack-catalog search timesfm -c us-equities-catalog -n 2 --json
qmd --index native-agent-stack-catalog get qmd://us-equities-catalog/models.md:268:27
```

Collection creation, search and source retrieval completed with exit **0**. The
recorded search returned the model guide. The selected source distinguishes
TimesFM 3.0's non-commercial weights from Apache-licensed 2.5. Line positions
belong to the frozen snapshot; use fresh search hits and section positions after
edits. Refresh the index when its tracked files change. This profile downloads no
QMD models and has no provider call; it is lexical retrieval, not semantic RAG.

```bash
TOKENIZER_PREFIX="$TOKENIZER_PREFIX" node scripts/recount-tokens.cjs --catalog
```

Using upstream `gpt-tokenizer@3.4.0`, encoding `o200k_base`, the direct result was:

```text
full source:       6398 tokens
selected source:    490 tokens
removed:           5908 tokens
reduction:         92.34135667396062%
```

This compares full-document output with selected source output for this bounded
question. It is not an exact Astra tokenizer, provider bill or matched whole-task
savings trial. [Receipt](retrieval-receipt.json),
[full source](../../evidence/artifacts/catalog-models.full.txt),
[selected source](../../evidence/artifacts/catalog-models.selected.txt),
[search result](../../evidence/artifacts/catalog-search.json).

## Current model discovery

```bash
hf models info nvidia/Nemotron-3-Embed-1B-BF16 \
  --expand sha,createdAt,lastModified,cardData,safetensors --format json
hf models card google/timesfm-3.0-pytorch --text --format human
```

Native HF CLI **1.32.0** returned **17/17** selected model metadata records and
**11** model cards, all exit **0**. Revisions, exact commands and bounded outputs
are in the [research receipt](research-receipt.json). These calls downloaded no
weights and performed no inference. The model catalog separates announcement,
first-weight and research-paper dates from repository creation/card edits.

## Native runtime evidence

| Upstream workflow | Direct recorded result | Exact replay and limits |
| --- | --- | --- |
| Native Codex SDK → configured GPT-6 Astra → Context Mode | Useful research task completed in 58,410 ms; 3 execute calls and 1 stats call succeeded; file-scope attempt failed | [Worker commands/receipt](../../blueprints/us-equities/workers/README.md) |
| All three native SDK turns, including two failed file checks | 202,164 input; 176,000 cached input; 1,927 output; 204,091 total | Cache share 87.06%; not net token savings |
| DeerFlow SDK + native Gateway | 0 configured models, 23 skills; health200/protected-models401 | [DeerFlow commands](../../blueprints/us-equities/deerflow/README.md) |
| Maintained Codex ACP | Protocol1 session discovery, configured Astra/high/read-only; zero prompt calls | Full DeerFlow inference remains unproved |
| OmniRoute / FreeLLMAPI health | HTTP200 / HTTP200, no inference in this health check | [Routing guide](../../blueprints/us-equities/routing/README.md); historical Opus/Qwen separate |
| Native LEAN source build/backtest | 3,943 data points; 3 simulated orders; 13/13 local data requests; matching upstream order hash | [Engine commands](../../blueprints/us-equities/engine/README.md); advisories unresolved |
| DuckDB JSON → Parquet → SQL + XNYS calendar | 6 events / 3 distinct simulated orders; session13:30–20:00UTC | [Data commands](../../blueprints/us-equities/data/README.md) |
| Existing automatic local code RAG | 35 files / 139 chunks; add/change/delete about3s each | [Baseline results](../../docs/direct-results.md); scope is the adopted starter project |

The existing native Codex/Claude tools and hooks have separate earlier receipts.
The SDK token totals cover only the three recorded SDK turns; they exclude the
coordinator and catalog-research agents and are not the total cost of this task.
This catalog expansion did not rerun Claude or deploy a broker. A fresh Desktop
session discovers newly registered tools; installed CLIs can be used now. New
projects need their own memory/index scope. The existing native Astra SDK worker
already used Context Mode in this task, but its file-tool override still needs
normal native MCP approval. Direct `ctx_*` tools are absent from the current
Desktop catalog; the native MCPorter bridge works.

## Verify the published artifacts

```bash
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
python3 -m unittest discover -s tests
```

These are offline structural, reference, hash, privacy and validation-regression
checks. They do not rerun provider inference, GPU services, market data or orders.
