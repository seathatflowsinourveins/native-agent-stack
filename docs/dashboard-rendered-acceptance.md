# Rendered dashboard acceptance — 2026-09-21

The installed interfaces were exercised in actual browsers, screenshots were
inspected, and displayed values were compared with upstream commands or APIs.
An HTTP 200 alone was not the acceptance condition. These are selected native
operations and local integration checks, not every upstream repository's test
suite or proof that the whole foundation is finalized.

The authoring PC's [screenshot and returned-result review](http://127.0.0.1:17500/dashboard-review.html)
contains the private screenshots, exact selected commands and downloadable
returned output. Public evidence retains sanitized findings and hash bindings;
private session content and host paths stay off GitHub.

## What was actually observed

| Interface | Operation and independent result | Remaining boundary |
| --- | --- | --- |
| ai-memory | Expanded System, searched, opened the real decision; native status: 53 latest pages, zero missing vectors; native doctor found capture for both Codex and Claude | Only one ordinary decision; other pages are session/maintenance records. LLM consolidation is disabled. |
| Qdrant | Opened project collection and points; native collection API: green, 225 points, dense dimension 2048 plus sparse vectors | Vector inventory is not retrieval-quality evaluation. |
| SocratiCode | Regenerated with upstream `codebase_graph_visualize`, opened Files/Symbols and file search; 29 files, 5 edges, 266 symbols, 323 calls | Explicit export; the previous served export had 26 files. A cache-busting URL was needed to observe the new bytes. |
| Serena | Native `get_current_config` agrees with rendered agent-lab, LSP-ready, Codex context and 24 active tools | Port belongs to this MCP process. Zero Serena memories is consistent with ai-memory being the shared memory of record. |
| AgentsView | Native session lists reconcile 14 parent sessions with 17 including children; UI analytics: 3,193 messages | Retained scoped archive, last synced about ten hours before inspection; not live ingestion. |
| Dagu | Selected Last 30 days and opened a real run; `dagu history --last 30d --format json`: 9 runs, 6 succeeded, 2 failed, 1 aborted | Today is empty. A preset-only URL failed; use the date picker or complete dated URL returned by the UI. |
| OmniRoute | Upstream REST command and UI show 31 requests and 57,720 consumed tokens in the returned 30-day scope; Compression All time shows 3 skipped/off records and 0 saved tokens | Direct Codex/Claude traffic is separate. `--period all` returned `30d`. High-level compression status failed because the optional MCP endpoint is disabled. |
| agent-browser | Separate observer viewed a real Dagu browser stream and activity events; native session metadata matched | Observing the dashboard's own tab recurses. Owned test browsers were closed afterward. |
| Grafana | Exact panel queries matched native memory/Qdrant/QMD results; split the unusable 15-column table into inventory, model health and provenance | Our integration panels. Claude has no current telemetry series; absence is not zero usage or savings. |
| Prometheus | Executed `up` in the UI and native `promtool query instant`: seven scrape targets returned 1 | Scraping is not provider or whole-ecosystem E2E. |
| Alertmanager | Expanded real alert; native `amtool alert query` agreed on the FreeLLMAPI readiness warning | Optional Windows gateway is not running; alert was preserved, not silenced. |
| ntfy | Native `subscribe --poll --since all` and rendered topic show 23 retained records, including the same gateway warning | Feed delivery works; desktop notification permission is separate. Existing message formatting has missing-instance/spacing defects. |
| Promptfoo | Opened a result detail and re-exported the existing evaluation with native `promptfoo export eval` | Two passing local echo fixtures, zero tokens, historical evaluation. This is not model-quality or memory-quality evidence. |

Counts are dated observations and can advance with real use. No new workflow,
notification, inference request, memory topic page or synthetic savings was
created to make a dashboard appear populated.

## ai-memory's actual upstream interface

The bundled wiki intentionally groups `sessions/`, underscore-prefixed trees and
bookkeeping pages under collapsed **System**, and excludes them from Recent
Activity. The footer **read-only** is intentional. Browser search at
`/web/search?q=...` is **global FTS search**, even when opened from a project page.
Use explicit scope for CLI/MCP search or the documented API:

```sh
ai-memory status --json
ai-memory doctor --workspace agent-lab --project agent-lab --since-days 1 --json
ai-memory search 'Shared project memory' --workspace agent-lab --project agent-lab --json
```

The unquoted search returned two existing matches; the quoted phrase returned
one. These are different FTS queries, not evidence of a search discrepancy.
`status` is database-wide; scoped MCP status independently returned 53 pages.
`doctor` reports per-harness coverage, not a bijection of every native session
file with a captured session.

The visible deployment decision still described version 2.3.1 and disabled
embeddings. The upstream `memory_feedback` operation flagged it **stale** for
lint review against the actual 2.3.2/local MiniLM configuration. Its body was not
silently rewritten or replaced with generated filler.

There is **no richer official admin SPA to install** in reviewed release
`353841d91618d20b110b208de284a74d0b960379` or reviewed main
`1fe32bc2be32490ebf614c86eb9ab45718dcceb1`. `--web-ui-dir` serves an externally
supplied SPA; it does not download one. The sibling `ai-memory-web` repository
is the marketing site. Native Codex-backed consolidation is supported upstream,
but enabling it also affects automatic processing; this dashboard review did
not enable all-scope model-based writes.

Sources: [wiki grouping](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-web/src/routes/project.rs),
[global web search](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-web/src/routes/search.rs),
[scoped API](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/docs/frontend-api.md),
[proposed, unimplemented web editor](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/docs/companion-crates.md),
[native provider setup](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/docs/llm-providers.md).

## Presentation repairs and future sessions

Grafana now separates a five-column inventory, an ai-memory-only model/coverage
table, and command/scope details. Rows no longer expand around long wrapped
text. **Stored** includes vectors for superseded page versions; **Missing** means
latest pages without vectors; **Failures** means unresolved embedding failures.
Fresh observation timestamps use a neutral color, not Grafana's default numeric
threshold color. Unknown values remain unknown.

Use the real scope and date controls in upstream UIs. Do not import unrelated
session archives, create demonstration jobs, or reroute native client traffic
to populate charts. CLI/MCP-only catalog entries do not acquire a web dashboard
through catalog inclusion. This review establishes the operations above and
retains the actual gaps; it does not establish universal SOTA superiority.
