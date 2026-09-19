# Native Agent Stack

A current, evidence-backed reference for native **Codex + Claude Code**, with scoped memory, automatic local code RAG, context-efficient retrieval and reproducible upstream workflows.

**Snapshot: September 19, 2026.** This repository records a tested selection and its limits. It is not a claim that every available framework is installed or that an independent universal SOTA benchmark has been won.

The **[US-equities grand catalog](catalogs/us-equities/README.md)** now covers
**147 unique repositories in 152 layer decision cards**, **20 model entries**,
and an auditable **337-star coverage ledger**. Its combined index includes
**479 repository identities** across all 337 public stars and 142 beyond them,
with typed, validated pointers to decisions and evidence. The latest
[architecture research wave](catalogs/us-equities/architecture/README.md) adds
source reviews, awesome-list coverage and official Alpaca constraints.
Start with the [current roles and architecture](blueprints/us-equities/architecture/README.md),
[north-star architecture](blueprints/us-equities/north-star.md)
and [native commands with direct results](catalogs/us-equities/native-workflows.md).

The [complete star audit](catalogs/us-equities/star-audit.md) records every starred repository; the [latest gap-resolution ledger](blueprints/us-equities/gap-resolution.md) links the new runtime proofs. The earlier [coverage audit](docs/convergence-audit.md) distinguishes the full starred-list metadata refresh from individual repository decisions and local execution, and records newly found research leads outside the original comparison.

The [US-equities foundation](blueprints/us-equities/README.md) extends this stack
with native Astra SDK workers, DeerFlow/ACP, OmniRoute recipes, LEAN backtesting
and a DuckDB/Parquet data path. It records actual native results and leaves
Alpaca paper execution explicitly pending; local Dagu research hosting now has
[workflow and restart evidence](blueprints/us-equities/hosting/README.md). The new
[local observability profile](observability/README.md) connects native client
telemetry to retained metrics/logs, dashboards and local notifications.

The earlier [research-runtime acceptance](blueprints/us-equities/research-runtime/README.md)
adds a fresh native LEAN → Dagu → DuckDB packet and a real standalone Claude
Opus 5 report, with **14,583 tokens reconciled against native telemetry**.
Its selected packet is **4,813 → 643 tokens** (86.64% less selected text, not
net provider savings). [Restic backup/restore](blueprints/us-equities/hosting/backup/README.md)
recovered 22/22 selected public files. The later [paired native acceptance](adoption/paired/README.md)
completed fresh LEAN → Dagu → DuckDB → Astra → Claude after native sign-in, using
the recreated SDK: **20,776 Astra tokens and 16,293 Claude tokens**. Its selected
packet measured **4,823 → 640 tokens**; this is not net provider savings.
SEC acquisition retains its HTTP 403 failure.

The [September 19 convergence review](catalogs/us-equities/convergence-review.md)
adds selected source reviews beyond the refreshed stars, current publisher model
metadata, [encrypted application-state recovery](blueprints/us-equities/state-recovery/README.md),
and a [frozen retrieval evaluation](blueprints/us-equities/retrieval-evaluation/README.md).
The lexical baseline retrieved the intended source in the top three for **8/12
questions**; its misses remain visible. This is a bounded selection review with
explicit open gates, not a claim of universal completeness.

## What is here

- **47 adopted components** across native clients, context, retrieval, memory, collaboration, browser work, verification, isolation, usage accounting, research hosting, backtesting, backup, dependency inventory and local observability.
- **19 researched alternatives** with adoption decisions, model requirements and prospective commands.
- A [six-candidate portability comparison](adoption/research.md), with 41 selected primary source files and a native uv adoption decision.
- **Four extended catalog layers** covering foundations/memory/RAG, agents/hosting/operations, data, and strategy/engine research; source review remains distinct from native execution.
- Pinned upstream recipes and inactive configuration examples. Native accounts, tool discovery, caching and compaction remain native.
- Sanitized receipts from real local CLI, MCP, GPU and agent runs. Original account stores, raw conversations and private machine state are not distributed.
- Offline evidence validation in ordinary GitHub Actions. CI does not invoke models or claim to reproduce a local GPU/subscription run.

## Demonstrated results

| Workflow | Recorded result |
| --- | --- |
| Context Mode, durable memory and native lifecycle integration | Successful native Codex and Claude tasks; exact limits in receipts |
| SocratiCode → Qdrant → local Nemotron embeddings | 35 files / 139 chunks; both native agents retrieved relevant code |
| Automatic code-index freshness | File add/change/delete observed in about 3 seconds each, without manual refresh |
| Local embedding inference | 2048 finite normalized values from a pinned July 2026 Nemotron model |
| Native browser/document/static-graph integration | Claude and this Codex Desktop task passed; the separate native Codex CLI follow-up was account-limit blocked |
| Source-history scan and command isolation | Recorded 22-commit source scan: zero secret findings; permitted/protected filesystem behavior exercised |
| Native Codex/Claude → local observability | Real native tasks exported logs/metrics; seven scrape targets up, six backend persistence checks, one firing and one resolved local notification |
| Host resource visibility | Eight native metric families and 23 series for CPU, memory, load and the WSL root filesystem; not the Windows physical backing disk |
| Fresh native Astra SDK telemetry | One completed Context Mode call; 40,369 input (26,240 cached subset), 149 output; all six native histogram categories reconciled and the atomic receipt reached Loki |
| Selected observability artifact | 188,769 → 500 tokens with `gpt-tokenizer 3.4.0` / `o200k_base`; task-specific selection, not provider savings |
| Native catalog retrieval | 6,398 → 490 tokens for the selected TimesFM evidence: 5,908 fewer, 92.34% less retrieved text; not provider savings |
| Native Astra SDK / LEAN / deterministic data path | Actual worker inference; 3,943 backtest points and 3 simulated orders; JSON→Parquet→SQL accepted, with explicit remaining trading gaps |
| Exact original retrieved-text comparison | 2,731 → 491 tokens: 2,240 fewer, 82.02% smaller; **not overall provider savings** |

The [Desktop restart acceptance](observability/desktop-restart.md) confirms direct Context Mode tools and correlated parent logs. The earlier [session follow-up](observability/session-e2e.md) remains dated evidence of the pre-restart limitations. Saved Context Mode counters and selected-artifact measurements remain separate from provider usage.

The public source fixture removes personal path literals and independently recounts to **2,730 → 491 tokens**. Historical original numbers are retained separately, avoiding a false byte-for-byte reproduction claim.

## Start here

1. Start with [new-machine adoption](adoption/README.md), the [continuation manifest](adoption/manifest.json) and [future update protocol](adoption/update.md). The SDK now has a native uv hash lock and fresh-prefix acceptance; historical results remain scoped to their original host.
2. Follow the [native installation and workflows](recipes/README.md). Choose the profile appropriate to your project; use your own native client login and project paths.
3. Adopt the inactive [examples](examples/) deliberately. They contain no credentials, blanket trust settings or active machine-specific configuration.
4. Validate the portable repository:

```bash
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
python3 -m unittest discover -s tests -v
```

To reproduce the public text measurement with the same upstream tokenizer:

```bash
npm install --prefix .runtime/tokenizer --ignore-scripts --no-audit --no-fund gpt-tokenizer@3.4.0
TOKENIZER_PREFIX="$PWD/.runtime/tokenizer" node scripts/recount-tokens.cjs
```

The actual provider/GPU runs are opt-in native workflows requiring your own account allowance and hardware. No account grant, model weights, runtime fork or forced proxy is bundled.

## Keep the distinctions

- **Installed** means a package or selected reference exists; **native CLI E2E** means useful input→output behavior ran; **native model E2E** means an actual client called it and returned useful results.
- A smaller selected artifact, local embedding tokens, cache reuse and provider usage are different measurements. No paired whole-provider savings claim is established.
- Memory pages are untrusted historical evidence. Keep project scope, bounded capture and canonical instructions authoritative.
- A working CLI bridge does not prove Desktop tool loading. The separate [restart acceptance](observability/desktop-restart.md) established direct Context Mode tools and correlated parent logs in this task; final parent usage attribution remains separate.
- The observability profile retains local metrics/logs and local notifications. It does not add a trace database, external alert destination, paid cloud host or connected broker. A [fresh SDK follow-up](observability/session-e2e.md) resolved the earlier missing native histogram; its receipt and metrics represent the same usage and must not be added together. Explicit loopback OTLP settings are not a claim that all native client telemetry is local.

See the [evidence manifest](manifests/evidence.json), [complete component manifest](manifests/stack.json), and [native replay guide](docs/evidence.md). Original project glue and publication files use the MIT license; upstream products, dependencies, models and any attributed material retain their own licenses. See [licensing](licenses/README.md).
