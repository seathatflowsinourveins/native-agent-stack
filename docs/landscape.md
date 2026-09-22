# Historical landscape and practice decisions — September 19, 2026

This dated snapshot retains earlier star counts, configuration and CI boundaries.
Use the [current grand catalog](../catalogs/landscape/README.md),
[native skill practice](native-skill-practice-20260921.md) and
[continuation guide](landscape-continuation.md) for current choices and next work.
Later memory maintenance and consolidation evidence supersedes the earlier
configuration described below; the original observations are preserved.

Checked September 19, 2026 against primary upstream releases, documentation and official model publishers. The machine-readable [landscape](../manifests/landscape.json) records release dates/pins and recent model research; [candidate decisions](../manifests/candidates.json) preserve the broader alternatives.

A “definitive” selection here means every selected component has an explicit role, provenance, native workflow and evidence boundary. It cannot mean a permanently complete list of every emerging repository or an independently won universal SOTA ranking.

## Foundations and why they are separate

| Foundation | Selected practice | Evidence / optional expansion |
| --- | --- | --- |
| Native agent runtime | Keep Codex/Astra and Claude/Opus accounts, native cache, tool discovery and compaction | Real tasks in both clients; account allowance remains external |
| Context selection | Focused rg/symbol lookup, Context Mode for selected output, RTK for supported commands, explicit artifact transformation | Raw diagnostics retained; no serial compressors or blanket prompt proxy |
| Exact code | Serena plus static code graphs and ast-grep | LSP/static semantics are different from execution traces |
| Automatic conceptual code retrieval | SocratiCode + Qdrant + local Nemotron/vLLM | Both-native-client retrieval and actual add/change/delete watcher proof |
| Documents | Explicit QMD collection, Markdown ingestion, selected public research | BM25 active; QMD GGUF semantic defaults and rerankers remain separate optional choices |
| Durable continuity | ai-memory project decisions/handoffs, bounded native capture, task records | No competing global memory daemon; no automatic backfill or LLM consolidation |
| Session archives | Explicitly scoped AgentsView snapshot and sync | Archive search is distinct from durable decision memory |
| Collaboration | One coordinator, bounded independent tasks, isolated writer worktrees, independent review | Worktrunk actual inventory; Beads/Dagu only when a durable queue/DAG is needed |
| Execution boundaries | Native client controls and explicit SRT policies | No automatic blanket trust; protected filesystem behavior checked |
| Verification | Task-specific checks, browser execution, structural diffs, shell analysis | Receipt tests do not replace product tests or provider inference |
| Publication provenance | Native release pins, official hashes, model revisions, license boundaries, typed receipts | Public snapshot excludes personal state; dependency/model redistribution is separate |
| Usage | Per-provider counters and exact artifact counts, with clearly separated scope | Whole-provider savings and billing reductions are not claimed |
| CI | Commit-pinned official checkout, read-only token, standard hosted runner, no model/secret/upload/cache jobs | Public offline validator run establishes evidence integrity only |

The native skill approach follows progressive disclosure: advertise concise skill descriptions, load details for the matching task, and avoid loading full catalogs into every prompt. See [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills) and [Claude best practices](https://code.claude.com/docs/en/best-practices). CI follows GitHub's guidance on immutable action pins and minimal permissions. [GitHub secure workflow reference](https://docs.github.com/en/actions/reference/security/secure-use).

## Recent starred repositories and alternatives

The timestamp-bearing GitHub star refresh found 337 repositories. WeKnora and Tech Leads Club skills were recent September 18 stars; SocratiCode was an older star with a September 16 release. Repository `pushed_at` is not a star timestamp or model release date.

- **WeKnora 0.8.0:** document warehouse, maintained Wiki and nine remote connectors with scheduled sync. No local folder watcher was established. Add it for a real document corpus/UI/connector requirement; SocratiCode already covers local code updates.
- **Tech Leads Club agent-skills:** selective skill source with MIT code and separately licensed CC-BY 4.0 maintainer skill content. Existing selected upstream skills suffice without another bulk catalog.
- **Dagu 2.16.6 / Beads 1.3.0:** use for tasks that need durable workflows or dependency queues. The September 20 Beads installation passed a scoped native lifecycle, claim persistence and dependency blocking/unblocking; it skips extra agent instructions/hooks and leaves ai-memory responsible for durable knowledge.
- **otel-tui 0.7.5:** now installed from the checksum-verified upstream release. Its native TUI received and displayed a synthetic loopback trace, then closed; production/native-provider telemetry and a persistent exporter were not part of that acceptance.
- **Agent Skills skills-ref 0.1.0:** installed from the official pinned source with `uv sync --locked`; validation, properties and prompt metadata passed on a selected skill. Upstream calls this a reference/demo implementation; it does not certify native client extension semantics.
- **ai-memory 2.3.2 maintenance:** native version, running executable, supported status, scoped search and configured direct MCP passed after an upstream backup and checksum-verified release replacement. Existing client hooks/routing remain intact; previous provider-task receipts retain their original version.
- **jCodeMunch 1.108.319:** now selected for explicitly scoped exact code retrieval, with both native clients completing the bounded task. Complete MCP search/source responses beat the whole-file baseline but were larger than an already known focused extraction. The native repeated-read estimate and six-tool schema payload are separate from exact provider savings. Upstream Dual-Use License 1.1 terms remain; this acceptance does not establish commercial deployment eligibility.
- **Headroom 0.37.0 MCP:** the official Python 3.13 tool installation with the MCP extra now has direct compression/retrieval/statistics acceptance. Exact recovery and failure retention passed; global and isolated synthetic savings ledgers remain separate. The prior local guard remains available.
- **Hindsight, EverOS, MemPalace, OpenViking, Cognee, Claude-mem, Mem0, Graphiti and LightRAG:** different archive, consolidation, resource-memory or graph designs. Many require extra models/accounts/databases. They remain explicit alternatives, not simultaneous default capture layers.
- **Syft 1.52.0 / OSV-Scanner 2.6.0:** current supply-chain candidates for a project with dependency/package artifacts. This publication has stdlib validation and upstream recipes, not a vendored runtime environment. No vulnerability-free certification is inferred from its secret scan.

The full candidate manifest includes native prospective commands and their prerequisites. They are marked unexecuted where appropriate.

The [supplemental native receipt](../evidence/receipts/upstream-native-tools-20260920.json)
and [memory maintenance receipt](../evidence/receipts/native-ai-memory-maintenance-20260920.json)
record the September 20 additions on their source Linux/WSL host separately from
the earlier landscape review. Importing these receipts does not qualify macOS,
VelaNext or another host. No lifetime token-savings counter or universal ranking
is inferred from adoption.

## Recent models and runtime compatibility

The dated publisher shortlist includes Qwen 3.8, DeepSeek V4.1 Flash, GLM 5.3, Kimi K3, Nemotron 3 Embed, Jina reranker 3.5, UEmbed 2B and CORE reranker 2B. Dates and certainty are retained individually. Very large sparse models still require storing their full weights; active parameter counts do not establish local fit. Hosted Astra/Opus do not provide downloadable HF weights or generic API credentials through a coding subscription.

**Nemotron-3-Embed-1B-BF16**, released July 16, is the model actually running for this code-RAG deployment: pinned revision, BF16 weights, 2,048 dimensions, mean pooling, and `query: `/`passage: ` prefixes. Other recent retrieval models were metadata/research candidates, not verified QMD drop-ins. QMD remains BM25; its compatible GGUF defaults are a separate route.

**Compatibility exception: vLLM.** Current upstream is 0.29.0. A clean native resolver succeeded, installation succeeded, and version/help returned 0.29.0. Actual GPU model initialization on this WSL machine failed with `RuntimeError: UVA is not available`. The service was stopped and NVIDIA's documented 0.25.0 configuration restored; a direct Desktop SocratiCode query then returned the correct code. The 0.29 candidate and failure receipt were retained locally. No dependency override or local runtime patch was used to manufacture a “latest” success.

Thus the active 0.25.0 pin is an explicit working compatibility choice, not mislabeled as newest. A future supported fix or different host can justify revisiting 0.29.0 with one bounded actual embedding/retrieval check. Version freshness alone does not replace that check.
