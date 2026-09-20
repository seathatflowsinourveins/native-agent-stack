# Native commands and direct results

These commands distinguish actual recorded runs from prospective integration.
The catalog's candidate commands are upstream entry points; unversioned examples
can move and must be locked before a reproducible deployment. They do not claim
every catalogued framework was installed or executed.

## Use the catalog without loading all of it

The native QMD CLI has a dedicated local index. These two catalog/foundation
collections are the portable setup below; the authoring host also has a third,
explicitly scoped observation collection. To adopt a different checkout, set
`STACK_REPO` to that checkout and add only the selected collections:

```bash
qmd --index native-agent-stack-catalog collection add \
  "$STACK_REPO/catalogs/us-equities" --name us-equities-catalog --mask '**/*.md'
qmd --index native-agent-stack-catalog collection add \
  "$STACK_REPO/blueprints/us-equities" --name us-equities-foundation --mask '**/*.md'
qmd --index native-agent-stack-catalog update
qmd --index native-agent-stack-catalog search timesfm -c us-equities-catalog -n 2 --format json
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

## Recorded model discovery

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
| Maintained Codex ACP | Protocol1 session discovery, configured Astra/high/read-only; zero prompt calls | Later [embedded native inference completed](../../blueprints/us-equities/deerflow/research-receipt.json); strict read-only sandbox was not provided by ACP |
| OmniRoute / FreeLLMAPI health | HTTP200 / HTTP200, no inference in this health check | [Routing guide](../../blueprints/us-equities/routing/README.md); historical Opus/Qwen separate |
| Native LEAN source build/backtest | 3,943 data points; 3 simulated orders; 13/13 local data requests; matching upstream order hash | [Engine commands](../../blueprints/us-equities/engine/README.md); [local dependency patches and native audits completed](../../blueprints/us-equities/engine/resolution.md) |
| DuckDB JSON → Parquet → SQL + XNYS calendar | 6 events / 3 distinct simulated orders; session13:30–20:00UTC | [Data commands](../../blueprints/us-equities/data/README.md) |
| Existing automatic local code RAG | 35 files / 139 chunks; add/change/delete about3s each | [Baseline results](../../docs/direct-results.md); scope is the adopted starter project |

The existing native Codex/Claude tools and hooks have separate earlier receipts.
The SDK token totals cover only the three recorded SDK turns; they exclude the
coordinator and catalog-research agents and are not the total cost of this task.
The original catalog expansion did not rerun Claude or deploy a broker; the subsequent observability acceptance ran bounded native Codex and Claude tasks without broker access. After registration,
restart and verify discovery on that host; CLI readiness is host-specific. New
projects need their own memory/index scope. The existing native Astra SDK worker
already used Context Mode in the recorded task, but its file-tool override needed
normal native MCP approval. Direct `ctx_*` tools were absent from that original
Desktop catalog. The later [restart acceptance](../../observability/desktop-restart.md)
records direct tool discovery; the native MCPorter bridge remains a separately
scoped option. A historical discovery receipt does not establish another host's
current tool availability.

## Verify the published artifacts

```bash
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
python3 -m unittest discover -s tests
```

These are offline structural, reference, hash, privacy and validation-regression
checks. They do not rerun provider inference, GPU services, market data or orders.

The [local Dagu workflow](../../blueprints/us-equities/hosting/README.md) subsequently ran the deterministic summary and both evidence validators, then retained successful/failed/cancelled history across a service restart. [Current gap ledger](../../blueprints/us-equities/gap-resolution.md).

The later [OmniRoute Astra receipt](../../blueprints/us-equities/routing/astra-receipt.json) records one completed exact-model text response (81 input +55 output), the supported native-client-version configuration and both earlier failures. Failed-attempt provider usage is unknown; no aggregate savings or hook/tool parity is inferred.

## Adopted local observability

The [native observability receipt](../../observability/receipt.json) records actual native Codex/Claude tasks and exporter reconciliation. The [backend receipt](../../observability/backends/receipt.json) records the separate Collector, retained metrics/log stores, dashboard/query and local-alert checks. See the [operations cards](agents-operations.json) for exact versions, licenses and portable upstream command entry points.

The installed Collector is `otelcol-contrib`, built from core and contrib sources and distributed through the official collector-releases repository. Commands such as `otelcol-contrib validate --config="$OTEL_CONFIG"`, `promtool check config "$PROMETHEUS_CONFIG"` and `amtool check-config "$ALERTMANAGER_CONFIG"` check reviewed configuration; they are not substitutes for delivery evidence. Existing records keep setup failures and initial metric identity limitations visible. No trace database, external notification destination, broker integration or measured maximum/net provider-token savings is implied.

## Source follow-up is separate from runtime acceptance

The [source follow-up receipt](source-followup-receipt.json) records an earlier public-star identity comparison and GitHub stable-release metadata, plus focused source examination. That dated snapshot contained337 public stars and453 combined identities; use the [current typed index](decision-index.json) for subsequent counts. No model, service, backup or optional exporter ran for that review. Prospective node_exporter/OpenLIT commands in the cards do not inherit the adopted Collector receipts. The [follow-up decisions](source-followup.md) retain the earlier restic boundary; later [public-file backup](../../blueprints/us-equities/hosting/backup/README.md) and [application-state restore](../../blueprints/us-equities/state-recovery/README.md) passed their scoped native drills. Independent off-host recovery remains pending.

## Authenticated historical data

The [AAPL acquisition recipe](../../blueprints/us-equities/alpaca-historical/README.md)
uses native Alpaca-py GET transport and a bounded provenance adapter. Its
[accepted receipt](../../blueprints/us-equities/authenticated-data/native-receipt.json)
records25daily bars/3pages and2corporate actions/2pages, allHTTP200. The25raw
closes match the frozen LEAN reference; missing dividend currency remains explicit.
The [identity-readiness wave](../../blueprints/us-equities/identity-readiness/README.md)
records eight HTTP200 responses across the retained original capture and one
saved-token continuation. Four query chains completed; native DuckDB preserved
ten distinct query observations, nine locally qualified and one quarantined.
Historical and just-before-observation cutoffs select zero. Its original failed
normalization is retained. Current metadata and retrospective data do not establish
historical universe completeness or strategy merit; the exact commands and source
anchors are in the wave's [receipt](../../blueprints/us-equities/identity-readiness/native-receipt.json).

## Catalyst convergence and native research comparison

The [current wave](../../blueprints/us-equities/catalyst-convergence/README.md)
records six fixed native Requests acquisitions, offline EdgarTools qualification,
DuckDBParquet materialization and independent replay. Its
[exact command receipt](../../blueprints/us-equities/lifecycle-sample/native-receipt.json)
reports three supported lifecycle claims and historical/before-first/first/last
selection counts0/0/1/3. These are local observer semantics; historical coverage
and original revisions remain unknown.

The [frozen protocol receipt](../../blueprints/us-equities/catalyst-experiment/receipt.json)
records synthetic DuckDB cutoffs0/1/1/3, stable earlier selection under a future
perturbation, and exact one-nanosecond arithmetic. It is not empirical strategy merit.

The [native comparison](../../blueprints/us-equities/research-efficiency/README.md)
uses actual AsyncCodex and Claude print-mode calls on eight frozen documents.
Codex full/focused totals were38,102/22,691 and38,130/25,069, both pairs accepted.
Claude totals were44,595/20,136 and45,652/24,562; both full answers exceeded the
frozen word cap. All semantic answers passed blinded grading. Commands, complete
available usage and failures remain in the receipt; no pooled or causal savings
claim follows from this bounded study.
