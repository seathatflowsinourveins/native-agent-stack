# SOTA repository convergence — 2026-09-22

One dated, per-layer list of the repositories this stack actually selects, confirmed
against current upstream metadata, with every newcomer from the 342 starred
repositories, the 35 awesome lists and a bounded 2026 web sweep examined and given a
typed disposition. `manifest-20260922.json` carries the machine-readable record with
pins, upstream state, evidence citations, adversarial verdicts and the critic's gaps.

Rules: evidence, not agreement or recency. A newer release is information, not a
reason to upgrade. Nothing here is promoted; a newcomer can only be `targeted_candidate`
or `keep_but_compare`, and only against a gap the catalogs already name. Inclusion is
not installation, E2E or superiority.

**Result in one line:** no reviewed selection was overturned; 396/396 upstream
repositories are alive and unarchived; 15 component pins have a newer upstream release
(information only); 34 candidate records (33 distinct repositories; microsoft/SkillOpt was
proposed in two layers) were examined and **one** earned `targeted_candidate`
(snyk/agent-scan, for agent/MCP/skill supply-chain scanning); the trading catalog card
for the engine layer was reconciled with the declared NautilusTrader destination.

The critic's caveat stands beside that line: ten foundation layers have no decision at
`selection=default` (semantic RAG, web research, token efficiency, quality & evaluation,
CI & supply chain, scheduling & supervision, hosting, observation & inference, isolation
at profile level, instructions & skills by inheritance) — they run on conditional, optional
or trial selections — and five trading layers have no natively proven default
(evaluation, portfolio, identity, data quality, market data beyond filings/calendars).
The full list is `manifest-20260922.json#/critic/layers_without_confirmed_selection`.

## Foundation — 16 layers (native Claude Code + Codex harness)

Pins are `manifests/stack.json`; "now" is the GitHub latest release on 2026-09-22. The two
component columns are an editorial split (the stack has no selected/supporting field);
each component's `review_status` is in the manifest.

| Layer | Core components (pin → now) | Further stack components | Disposition of newcomers |
| --- | --- | --- | --- |
| Native clients | claude-code 2.1.278 · codex 0.155.1 · ai-memory 2.3.2 → 2.4.0 · context-mode 1.0.169 · qmd 2.8.3 · rtk 0.49.0 | — | — |
| Instructions & skills | native discovery + selected upstream skills: ECC (search-first, iterative-retrieval), skills-ref 0.1.0, tavily-cli 0.1.8 | claude-code-templates, claude-code-best-practice (reference) | google/skills not adopted (Google-product skills); anthropics/skills, claude-plugins-official, financial-services, SkillOpt refuted (no named gap) |
| Workers | claude-code, codex, worktrunk 0.79.0, beads 1.3.0 (conditional), codex-for-claude 1.0.6 | systemd | codex-for-claude (openai/codex-plugin-cc) head 2026-07-08: lane noted 2.5 quiet months and proposed nothing; open-multi-agent, agent-orchestrator not adopted |
| Isolation | worktrunk 0.79.0, sandbox-runtime 0.0.77 | apple-container 1.4.1 | dagger/container-use refuted |
| Code navigation | serena 2.0.0.dev0 (c6fbd1c) · ast-grep 0.45.3 · ripgrep 14.1.0 (in use, not pinned — see reconciliations) | jcodemunch-mcp 1.108.319, codebase-memory-mcp 0.11.0, repomix 1.18.1, socraticode 1.14.0, qdrant 1.19.1, toon 4.1.1, mcp-inspector, mcporter | — |
| Document retrieval | qmd 2.8.3 (BM25) · markitdown 0.1.7 → 0.1.8 · poppler 26.09 | context-hub 0.1.4 (head 2026-05-31) | — |
| Semantic RAG | socraticode 1.14.0 → Nemotron embed via vllm 0.25.0 → 0.29.0 → qdrant 1.19.1 | huggingface-hub 1.32.0, ai-memory, restic | all decisions conditional by design (critic) |
| Durable memory | ai-memory 2.3.2 → 2.4.0 (scoped capture/read/write/backup) | qdrant, restic | MemTensor/MemOS not adopted (no gap; layer populated) |
| Web research | tavily-cli 0.1.8 · agent-browser 0.38.1 · playwright-cli 0.1.21 · openresearch 0.2.7 → 0.2.8 | — | tavily crawl/map/research modes unqualified (critic) |
| Token efficiency | rtk 0.49.0 · context-mode 1.0.169 · headroom 0.37.0 → 0.38.0 (renamed headroomlabs-ai/headroom) · ccusage 20.0.24 | jcodemunch, qmd, repomix, toon | yvgude/lean-ctx refuted (10-star third-party benchmark only) |
| Quality & evaluation | promptfoo 0.123.1 · difftastic 0.71.0 · shellcheck 0.11.0 · zizmor 1.30.1 · playwright-test 1.63.0 | fastapi, nextjs, react, postgresql (local typed-app surfaces), gitleaks, syft, skills-ref | alibaba/open-code-review refuted; critic: split app surfaces out of this layer |
| CI & supply chain | gitleaks 8.30.1 · syft 1.52.0 · zizmor 1.30.1 | qmd, repomix, rtk, toon | **snyk/agent-scan → targeted_candidate** (agent/MCP/skill scanning has no incumbent); anchore/grype refuted here (already a trading default) |
| Scheduling & supervision | dagu 2.16.6 → 2.17.0 · systemd (user units) · beads 1.3.0 (`keep_but_compare`) | claude-code, codex | dbos-transact-py, healthchecks, uptime-kuma refuted (no gap) |
| Hosting & services | omniroute 3.8.50 (optional gateway, trial) · fastapi 0.141.1 · nextjs 16.3.5 · react 19.3.0 · postgresql 18.6 | mcp-inspector 2.7.0, mcporter 0.13.13, apple-container | — |
| Recovery & portability | restic 0.19.1 (conditional; `keep_but_compare`, targeted-candidate label still supported) · ai-memory · dagu · qdrant snapshots · systemd | claude-code, codex | borgbackup/borg not adopted (peer of restic); mise, backrest refuted |
| Observation & inference | prometheus 3.14.0 · grafana 13.2.2 · loki 3.7.8 · alertmanager 0.34.1 · otel-collector-contrib 0.161.0 · otel-tui 0.7.5 · ntfy 2.28.0 · ccusage · claude-hud 0.8.0 · agentsview 0.43.0 → 0.44.0 | vllm, llama-cpp b11057, huggingface-hub, omniroute | VictoriaMetrics not adopted (Prometheus-compatible peer); abtop refuted |

## Trading — 12 consolidated layers (US-equities destination)

The 134 fine-grained catalog tags collapse into these layers (`manifest-20260922.json#/taxonomy`).
Pins are the catalog cards; the north star is `catalogs/us-equities/runtime-target.json`.

| Layer | Catalog `default` entries (pin → now) | Catalog `conditional` entries | Disposition of newcomers |
| --- | --- | --- | --- |
| Market data & reference | alpaca-py 0.44.0 (SIP entitled, 2016→) · edgartools 5.58.0 · exchange_calendars 4.13.2 | databento, fredapi (`unmaintained_signal`), gdeltdoc, massive, questdb, kafka, dlt, feast | FinanceDatabase, FinanceToolkit, findatapy not adopted (no PIT identity, no delisting history); royelee/delist-detection refuted (1 star) |
| Identity & provenance | dvc 3.67.1 · socraticode 1.14.0 | arcticdb, iceberg, openlineage, mlflow, cosign, kafka | **open gate**: dated security identity (235 ticker collisions, no listing/delisting dates) — no repository closes it; it is an entitled-source schema question |
| Storage & compute | duckdb 1.5.5 · pandera 0.33.1 | arrow, clickhouse, iceberg, questdb, dlt, feast, ray-serve, toon | — |
| Data quality & orchestration | pandera 0.33.1 | dagu 2.16.6 → 2.17.0, modal, temporal | Point72/csp refuted; critic: no fail-closed gate implemented yet |
| Research, factors & ML | edgartools 5.58.0 · markitdown 0.1.7 · qmd 2.8.3 · vllm 0.25.0 | skfolio 1.2.9 → 1.3.0, statsmodels, arch, sktime, statsforecast, tsfresh, alphalens-reloaded, qlib, chronos, timesfm, scikit-learn, arcticdb, river, deerflow, docling, haystack, sentence-transformers, ray-serve | mlfinlab refuted; Kronos stays `keep_but_compare` with its stale signal affirmed (last push 2026-04-13); mlfinpy remains a `watch` card; standing evidence is the frozen broad-universe negative result |
| Backtesting engine | card: LEAN 985ef30 (`default`, demotion to frozen comparator confirmed) · **reconciliation: NautilusTrader 2.0.0rc5 is the selected destination** per runtime-target (card still `alternative` 1.231.0; GitHub latest non-prerelease v1.231.0) | cvxportfolio | pysystemtrade, BacktestingCore not adopted; hftbacktest, pybroker refuted; backtrader stale (no push 12 months) |
| Execution & broker | alpaca-py 0.44.0 · lean-alpaca 1973f61 (`default` card; reference only after the engine reconciliation) · **reconciliation:** custom deterministic Alpaca adapter (adaptive-paper) and NautilusTrader IBKR adapter (selected, acceptance not established) — neither has a card | — | Vibe-Trading, fitbro refuted; no second order writer |
| Portfolio & risk | quantstats 0.0.81 (source review) · skfolio 1.2.9 → 1.3.0 (native proven, conditional) | cvxportfolio, empyrical-reloaded (`unmaintained_signal`) | quantopian/empyrical stale (no push 12 months) |
| Evaluation & experiments | inspect-ai 0.3.266 | mlflow, phoenix (behind), mteb (behind), river, agent-retrieval-bench | SkillOpt refuted; critic: whole layer is source-review only |
| Agents, models & workers | codex 0.155.1 · claude-code 2.1.278 · ai-memory 2.3.1 → 2.4.0 · context-mode · serena 1.7.0 · socraticode · qdrant · rtk · vllm 0.25.0 → 0.29.0 | codex-acp, deerflow, langgraph, omniroute, graphiti, pageindex, pgvector, repomix, toon, codebase-memory-mcp, agent-retrieval-bench | `catalogs/us-equities/models.json` (20 entries, unchanged): defaults gpt-6-astra, claude-opus-5[1m], nvidia/Nemotron-3-Embed-1B; claude-fable-5-1 is `excluded` in that dated catalog although current sessions run it by user choice |
| Observability & hosting | prometheus · grafana · loki · alertmanager · otel-collector(-contrib) 0.161.0 · ntfy · restic · sandbox-runtime | e2b, opensandbox (behind), modal, mlflow, phoenix | critic: no broker-path alert rule yet |
| Security & supply chain | gitleaks 8.30.1 · syft 1.52.0 · grype 0.119.0 | cosign, openbao | critic: NautilusTrader rc5 tree and the Alpaca adapter never scanned |

## Beyond the stars

- **Star audit**: all 342 public stars keep an explicit disposition (51 already covered,
  156 alternative, 50 overlap established, 53 outside north star, 14 targeted candidates,
  13 obsolete/ineligible, 5 other). The 14 targeted candidates were re-read: Kronos,
  Vibe-Trading, ai-trader, tradingview-mcp, claude-trading-skills, dbhub, SkillOpt,
  open-code-review, abtop, mise, loopx, beads, restic, pydantic. None was promoted;
  restic and beads are already stack components under conditional decisions, loopx
  still resolves to the same repository id.
- **Awesome lists**: 35 starred; 9 are outside the north star, 15 overlap established
  references, 10 are alternatives, 1 is discovery-only (awesome-mac). The 26 lists inside the north star were read at their
  current README and every github link was subtracted from a 388-entry normalised
  inventory of what the catalogs already carry (alpacahq/marketstore and twopirllc/pandas-ta
  answered 404 and could not be evaluated). Every candidate that survived that subtraction
  and a quality screen (FinanceDatabase, FinanceToolkit, findatapy, pysystemtrade, hftbacktest,
  pybroker, mlfinlab, csp, borg, backrest, healthchecks, uptime-kuma, VictoriaMetrics,
  MemOS, container-use, agent-orchestrator, google/skills, anthropics/skills) was examined
  and refuted or not adopted for want of a demonstrated gap. Four link-only lists have
  had no push in 12 months (awesome-actions, awesome-shell, awesome-design-patterns,
  Awesome-Design-Tools).
- **2026 newcomers** (bounded WebSearch, 18 queries): lean-ctx, dbos-transact-py, MemOS,
  Claude Code Dynamic Workflows (already native), BacktestingCore, delist-detection,
  snyk/agent-scan. Only agent-scan names a gap with no incumbent.
- **Upstream health**: 396 repositories, 0 archived, 0 errors, 1 rename
  (chopratejas/headroom → headroomlabs-ai/headroom), 8 with no push in 12 months
  (four awesome lists, backtrader, empyrical, mlfinpy, gdelt-doc-api).

## Reconciliations recorded

1. `backtesting-engine`: the engines-strategies card still says `lean=default`,
   `nautilustrader=alternative 1.231.0`; the runtime target, adaptive-paper practice and
   equity replay run on NautilusTrader 2.0.0rc5. The manifest records the destination
   and demotes the card to comparator. 2.0.0 final has not shipped.
2. `execution-broker`: no IBKR entry existed at default/conditional; the manifest records
   the Nautilus IBKR adapter (selected, unaccepted) and the custom Alpaca adapter.
3. `code-navigation`: ripgrep 14.1.0 is mandated and in use but is not a stack component.

## What would overturn a selection

Each `keep_but_compare` alternative and every refuted newcomer carries a
`comparison_that_would_overturn` in the manifest. The recurring shapes: a measured
same-task provider-token comparison (token efficiency), a dated identity dataset that
resolves the 235 collisions (identity), a completed SPY/LEAN parity run (engine), a
broker-specific recovery case passed by a community adapter (execution), and an
adversarial recovery fixture passed by a compression tool (context tools).

## Method and limits

Baseline from `catalogs/foundation/decisions.json`, `manifests/stack.json` and the four
`catalogs/us-equities` layer files; freshness from authenticated GitHub REST metadata for
396 repositories (2026-09-22 04:08 UTC); three native Opus/high review lanes with bounded
`gh api` / WebFetch / WebSearch budgets (103 gh calls, 2 fetches, 18 searches); every
proposal verified by two Opus/high refuters; one completeness critic; then an independent
native evidence review of this record against the manifest. 150 workflow children in
total. The Codex foreground review lane was attempted three times (branch diff, retry,
prose-only commit) and the native `codex review` run exposed the cause: the ChatGPT
account's usage limit is exhausted until 2026-09-26 15:41 ET, so cross-family review of
this record is **not established** and no credits were purchased.
The freshness snapshot, lane outputs, 150-child usage record and Codex streams are private
working files, so the 396/0/8 repository figures and the child count are not reproducible
from the public files alone. Not done: release-note reading for the 15 behind pins, any install, run, benchmark or
license-file inspection (GitHub reports NOASSERTION for serena, ccusage, borg). The
private working files stay under the host's state directory.
