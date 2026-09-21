# Qualified native memory and retrieval

The September 21 qualification separates durable memory, documentation search,
code retrieval and their upstream interfaces. Installed ai-memory 2.3.2,
SocratiCode 1.14.0, QMD 2.8.3 and Qdrant 1.19.1 matched their published releases
at review time. This is a dated, tested selection, not a universal ranking.

The [native qualification receipt](../evidence/receipts/native-memory-rag-alignment-20260921.json)
binds the returned commands, model checksums, isolated restore, retrieval repair
and independent dashboard observations. Download unchanged private command
returns from the local [full report](http://127.0.0.1:17500/token-savings.html#native).

## Which interface answers which question

| Layer | Upstream interface | Qualified use |
| --- | --- | --- |
| Shared durable memory | [ai-memory wiki](http://127.0.0.1:49374/web/w/agent-lab/agent-lab) | Project tree, System grouping, Markdown, metadata, links and FTS5 search |
| Semantic memory | ai-memory `memory_query` MCP tool | Scoped FTS/entity/vector fusion over the shared wiki, using local MiniLM |
| Conceptual source-code retrieval | SocratiCode MCP | Hybrid dense/sparse retrieval over this project's actual source files |
| Code relationships | [upstream graph export](http://127.0.0.1:17500/socraticode-graph.html) | Files/Symbols navigation in an explicit snapshot; search, layout, impact and PNG controls are available but not functionally qualified here |
| Vector storage | [Qdrant collections](http://127.0.0.1:16333/dashboard#/collections) | Select the configured project collection; inspect points, configuration and native maintenance tabs |
| Local Markdown | scoped QMD CLI | BM25 retrieval of the selected documentation collection; zero vectors is intentional in this separate lane |
| Operating status | [foundation Grafana](http://127.0.0.1:13000/d/native-foundation-data) | Local integration panels over native metadata, including memory embedding coverage and provider modes |

The wiki's browser search remains FTS5 even when MCP semantic retrieval is
enabled. The observed wiki contains one ordinary decision and 51 System pages;
52 pages does not mean 52 curated decisions. Its larger observation count is
capture history, not consolidated durable knowledge. LLM consolidation remains
disabled. Do not turn incidental activity into durable pages merely to populate
a dashboard. Maintain canonical rules in AGENTS/CLAUDE and use upstream memory
skills for explicitly requested durable knowledge and handoffs.

## Concrete repairs and returned results

The prior code index included an independent nested publication checkout.
The same semantic query ranked copied retrieval receipts above the real source.
Appending `/packaging-repo/` and `/runner-temp/` to the project's upstream
`.socraticodeignore` let the native watcher remove that contamination;
`codebase_update` then confirmed the reconciled state. Native Qdrant went from 7,431 to 196 points; a complete payload
scan found zero excluded paths and retained the actual implementation. The same
query then ranked `tools/ecosystem/linux-usage-report.cjs` first. This is one
observed relevance repair, not an aggregate recall benchmark.

The refreshed upstream graph contains 26 files, three file edges, 254 symbols
and 318 calls. Its generation receipt supplies the snapshot date. The graph's
Files/Symbols and layout features belong to the unchanged upstream export;
the served snapshot does not automatically regenerate whenever the index changes.

ai-memory now uses its supported in-process local model. Startup returned
`embedded=52`, `failed=0`, one scope; a scoped follow-up returned:

```json
{"embedded":0,"skipped":52,"failed":0,"would_embed":0,"provider":"local","model":"all-MiniLM-L6-v2","dim":384}
```

For the actual query `switching between coding assistants`, native CLI text
search returned `[]`, while the current Desktop MCP returned the existing shared
project-memory decision first. All latest pages had embeddings and unresolved
embedding failures were zero. This verifies the activated semantic path on one
query; it does not establish broad retrieval quality or language-model savings.

Native backup and restore into a separate private directory passed. All 52
restored latest-page paths and body hashes matched the immutable native backup.
The live store continues capturing and can change after that backup. The initial
restore was correctly refused while another ai-memory process was running; the
owned service was stopped briefly, the isolated restore completed, then the
service restarted with local embeddings. A request made before model loading
finished failed and is retained. The expected V62 checksum warning is covered by
upstream compatibility logic and its regression test; read-only checks found
migration 64, zero missing page windows and zero window-invariant mismatches.

## Upstream commands for another selected project

Use the native [installation recipe](../recipes/README.md#project-memory), one
private data directory and explicit project markers. Back up existing data
before a configuration change. The following commands use operator-selected
paths and scope; they are not a startup script to rerun every session.

```sh
ai-memory --data-dir "$MEMORY_DATA" backup --to "$PRIVATE_BACKUP"
# Merge embedding_provider="local" into the existing config; preserve other fields.
# Reload the owned memory service and wait for its listener/model readiness.
ai-memory --data-dir "$MEMORY_DATA" embed --workspace "$WORKSPACE" --project "$PROJECT" --dry-run
ai-memory --data-dir "$MEMORY_DATA" embed --workspace "$WORKSPACE" --project "$PROJECT"
ai-memory --data-dir "$MEMORY_DATA" status --json
ai-memory --data-dir "$MEMORY_DATA" search 'selected query' --workspace "$WORKSPACE" --project "$PROJECT" --json
```

For MCP, call `memory_query` with that explicit workspace/project in static
clients. Session-aware clients use their supported identity routing. For code,
adapt the [ignore example](../examples/socraticodeignore.example), call upstream
`codebase_update`, inspect native status, and rerun a real task query against
the source. Generate the graph with `codebase_graph_visualize` using
`mode="interactive", open=false`; retain the returned file unchanged.

Rollback to memory `embedding_provider="none"` restores text-only retrieval
after a service reload without deleting pages. Provider/model/dimension triples
are stored separately. The code index uses Nemotron's required query/passage
prefixes through SocratiCode. ai-memory's compatible endpoint adapter lacks
separate prefix configuration, so directly reusing that endpoint would not
satisfy the model's retrieval preprocessing contract. The native local provider
avoids that mismatch. vLLM stays at qualified 0.25.0 because 0.29.0 failed on
this WSL GPU with `UVA is not available`; keep that recorded compatibility pin.

## Source and acceptance boundaries

Use [ai-memory local embeddings](https://github.com/akitaonrails/ai-memory/blob/v2.3.2/docs/local-embeddings.md),
[bundled wiki usage](https://github.com/akitaonrails/ai-memory/blob/v2.3.2/docs/usage.md),
[read-only API capabilities](https://github.com/akitaonrails/ai-memory/blob/v2.3.2/docs/frontend-api.md),
[SocratiCode ignore rules](https://github.com/giancarloerra/SocratiCode/blob/v1.14.0/README.md#ignore-rules)
and [Qdrant collection inspection](https://api.qdrant.tech/api-reference/collections/get-collection).
The separate rich ai-memory admin frontend requires its own upstream deployment
and authentication; it is not the bundled wiki. No replacement frontend was
installed. Qdrant's ANN-recall, snapshot and cluster tabs were observed, not
claimed as exercised benchmarks or cluster recovery. Existing native hook/client
acceptance remains dated; this wave qualifies the shared backend and current
Desktop retrieval without repeating provider model trials.
