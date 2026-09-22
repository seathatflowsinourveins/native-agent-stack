# US-equities grand catalog

This is the **trading architecture catalog**. General Codex/Claude runtimes,
workers, skills, memory, retrieval, efficiency and operations are maintained in
the separate [foundation catalog](../foundation/README.md). Trading work reuses
that foundation and adds data, strategy, risk and broker-specific requirements.

The [current four-layer comparisons](../landscape/us-equities.json) explain the
selected roles and meaningful alternatives using later retained evidence. The
[offline comparison view](../../docs/ecosystem/index.html#landscape) also preserves
every historical candidate card. Current target selection takes precedence over
old default labels; source-only proposals remain unqualified until executed.

The current selected destination is **NautilusTrader 2.0.0rc5 with IBKR**, plus a
separately validated **Alpaca** data/paper-execution boundary. LEAN remains the
accepted historical comparison engine. See the [current target and official
capability record](runtime-target.json) and updated [north star](../../blueprints/us-equities/north-star.md).
The [next acceptance plan](../../blueprints/us-equities/engine-nautilus/acceptance-plan.md)
binds equity replay to retained SPY inputs, an independent economic oracle and
separate broker fault/paper gates. Earlier research waves below retain their
original decisions and evidence.

The [September 21 paper and simulation review](paper-practice-20260921.md)
records current Alpaca account rate evidence, selected official SDK probes and
the reasons for retaining or comparing the CLI, MCP and simulation alternatives.
Its bounded operational paper lane uses 120 requests/minute against the observed
200/minute account limit; Elite's advertised 1,000 is API calls, not fills.

The [current token-practice audit](../../docs/token-practice.md) maps the
then-selected 52 components to their evidence levels and records ten exact artifact comparisons
plus four accepted native coding trials. Catalog inclusion does not supply a
per-repository token-saving value.

**Dated decision catalog: September 20, 2026.** The north star is native research → reproducible backtesting → independently accepted IBKR and Alpaca paper workflows. This is an examined selection across layers, not a universal final SOTA ranking or a claim that every listed framework runs together.

The catalog has **152 baseline repository decision cards covering 147 unique GitHub repositories**, and **20 model entries**. The [combined repository index](repository-index.md) now contains **513 repository identities**, including all 342 public stars and 171 beyond that snapshot. Its [typed decision union](decision-index.json) validates baseline cards, component/candidate records and explicitly registered research supplements together; 1,067 source pointers preserve their different evidence depths. The historical 453-row index remains dated reference material.

The newest [security-identity review](security-identity-review.md) examines Alpaca,
Zipline, Qlib, NautilusTrader, LEAN and WRDS. It separates engine identity/lifetime
representation from historically available source data. WRDS is the sole new
conditional reference, with licensed access unestablished. See the [native identity
wave](../../blueprints/us-equities/identity-readiness/README.md) for its bounded
probe, observation ledger and explicit remaining universe/revision requirements.

The preceding [authenticated-data review](authenticated-data-review.md) challenges
Massive, Databento, OpenFIGI, ArcticDB, Pandera and OpenBB. It records historical
identity, revision, availability and licensing limits from pinned source files.
Only OpenFIGI adds a new reference identity; no additional framework is adopted.
The [native acquisition wave](../../blueprints/us-equities/authenticated-data/README.md)
links its own commands, results and open gates.

The [September 20 selected review](data-readiness-review.json) records six current
repository/API decisions. The [data-readiness wave](../../blueprints/us-equities/data-readiness/README.md)
uses retained SEC sources and LEAN corporate-action data. One additional catalog
identity, pandas-datareader, is explicitly omitted as an equity-data shortcut;
catalog growth does not imply installation.

The [recorded convergence program](../../blueprints/us-equities/convergence-program/README.md)
retains 36 bounded decisions across foundation, trading/data and hosting, with two
challenge rounds per matrix. Its [coverage map](../../blueprints/us-equities/convergence-program/coverage.md)
relates the dated acceptance to current selections and open requirements. Native historical simulation
results and the grand dashboard are linked separately from source-only candidates.

The [next simulation/SEC wave](../../blueprints/us-equities/simulation-research/README.md)
adds native chronological selection evidence and EdgarTools adoption with explicit
data-access boundaries. Existing source-only catalog cards gain only the native
capabilities established by their linked receipts.

The [native acceptance follow-up](../../blueprints/us-equities/acceptance-wave/README.md)
adds scoped evidence for LEAN, DuckDB and the already installed Alpaca SDK. Its
[next research protocol](../../blueprints/us-equities/acceptance-wave/research-protocol.md)
targets daily/intraday catalyst and extreme-mover research. This advances existing
choices without claiming a new source census or accepted historical market dataset.

The [factor/feed and market-regime design](../../blueprints/us-equities/acceptance-wave/factors-regimes.md)
maps seven complementary source families and proposed automatic selection among
validated strategies. Those feeds and selector remain pending acquisition/acceptance.

The latest [architecture wave](architecture/README.md) reviews 40 finalist records across foundation, trading and governance lanes, plus official Alpaca sources. It refreshes all public stars and audits 12 complete awesome-list snapshots without treating 6,939 unassessed discovery links as reviewed repositories. Read the [roles, selected stack and promotion gates](../../blueprints/us-equities/architecture/README.md) and [native Astra/Claude review evidence](../../blueprints/us-equities/architecture/receipt.json).

## Read the layer you need

Gate ladder: [`gates-20260922.json`](gates-20260922.json) records the sim → paper → live gates with owner, evidence class, receipt path and flip condition; `python3 scripts/trading_gates.py --check` verifies them arithmetically (nothing is flipped by the checker).

| Layer | Cards | Guide / structured manifest |
| --- | ---: | --- |
| Token efficiency, memory, retrieval, document ingestion | 36 | [foundation-memory](foundation-memory.md) · [JSON](foundation-memory.json) |
| Agents, OmniRoute, SDKs, orchestration, hosting, security, telemetry | 42 | [agents-operations](agents-operations.md) · [JSON](agents-operations.json) |
| Market/reference/filing data, storage, quality, lineage | 36 | [data-research](data-research.md) · [JSON](data-research.json) |
| Engines, broker adapters, portfolios, statistics, strategy research | 38 | [engines-strategies](engines-strategies.md) · [JSON](engines-strategies.json) |
| Current model choices and older compatible baselines | 20 | [Models](models.md) · [JSON](models.json) |

Start with the [north-star architecture](../../blueprints/us-equities/north-star.md), [native commands and direct results](native-workflows.md), [harness contract](../../blueprints/us-equities/harness-contract.json), and [machine-readable catalog manifest](manifest.json).

The earlier [research and native acceptance review](convergence-review.md) links
27 source-review finalists, refreshed HF metadata, actual private-state recovery,
the preserved retrieval misses, the native SDK dependency inventory and a fresh
Claude critique with independently reconciled usage. Its [machine-readable
summary](convergence-review.json) preserves every remaining gate.

## Recommended convergence

Use the selected native capabilities from the foundation catalog. Keep **DuckDB/Parquet + exchange calendars** for deterministic data work and **LEAN** as the accepted source-built comparison engine. Advance the requested **NautilusTrader 2.0.0rc5 / IBKR** destination with its own scoped evidence; **Alpaca** requires a separate adapter because the official Nautilus integration list has none. The Alpaca SDK's authenticated data receipts remain read-only evidence. QuantStats is a proposed reporting layer; selected statistical/ML tools follow only after point-in-time data exists.

**OmniRoute** remains an optional route with explicit model fidelity and usage checks; **DeerFlow** remains a research orchestration candidate whose backend, ACP discovery and later bounded native task have separate [receipts](../../blueprints/us-equities/deerflow/research-receipt.json). Add document RAG, a temporal graph, durable scheduling, remote sandboxes or managed hosting only for a concrete requirement. A healthy endpoint, installed SDK or paper simulator is not a complete automated trading runtime.

## What the evidence establishes

- Native Astra SDK research used Context Mode and returned useful results. All three turns, including failed file-scope checks, have usage receipts: 202,164 input / 176,000 cached input / 1,927 output. Cache reuse is 87.06%, not a net-savings comparison.
- Native LEAN source build and unchanged bundled backtest passed: 3,943 data points, 3 simulated orders, 13/13 local-data requests. Data transformed through DuckDB/Parquet successfully.
- New native QMD catalog retrieval produced 490 tokens versus 6,398 for the full model-guide output: 5,908 fewer, 92.34% less retrieved text. Both artifacts and upstream tokenizer replay are retained.
- Native HF discovery returned 17 model metadata records and 11 model cards. Only separately cited earlier/native runs establish inference; model-card retrieval does not.
- New catalog recipes are prospective unless their referenced receipt explicitly establishes execution. Those early recipes did not accept broker execution, strategy edge or a deterministic risk service. Later Alpaca authenticated read-only acquisition and identity receipts establish only their bounded observed access. A later manual research DAG and authenticated local Dagu history host were accepted; this is not unattended trading.

The later [native observability receipt](../../observability/receipt.json) establishes actual Codex/Claude log and metric export through the local Collector. [Backend evidence](../../observability/backends/receipt.json) covers Prometheus, Loki, Grafana and local alert delivery. These are bounded local runtime results; trace storage, broker monitoring, external alerts and maximum/net token-savings claims remain outside acceptance.

## Starred repositories and beyond

The September 20 native public-endpoint refresh contained **342 public stars**, with
zero added, removed or renamed identity pairs since the previous refresh. The
[refresh receipt](../../blueprints/us-equities/authenticated-data/public-stars-refresh.json)
preserves the identity hash and scope. The card-membership ledger and 105
beyond-star baseline card identities remain in [coverage.json](coverage.json);
the [complete star audit](star-audit.md) and typed union include subsequent
additions. A recorded disposition is distinct from code review or native execution.

Source review covered official metadata, README/license text and relevant API/source documentation at the date and depth stated per record. It did not deeply benchmark all 342 stars or every project beyond them. Repository freshness, stars, model launch dates and author benchmarks do not establish superiority. The catalog exposes missing acceptance work rather than turning a list into a deployment claim.

## Decision and evidence vocabulary

| Field | Meaning |
| --- | --- |
| default | Recommended responsibility in the selected path; actual installation/acceptance is stated separately |
| conditional | Add when the stated workload, entitlement or evaluation justifies it |
| alternative | Competing implementation; do not stack it by default |
| watch | Relevant research or integration lead with unresolved adoption issues |
| excluded | Not eligible for the selected path under current compatibility, lifecycle, license or user constraints |
| native_proven | Only the cited local receipt scope ran; may be a CLI/health/sample proof, not model or broker E2E |
| source_review | Primary-source examination and proposed commands; no new runtime acceptance |

Every card supplies role, selection reason, version/source, license, US-equity/Alpaca fit, requirements, limitations, source links and native workflow entry points. Commands without pins are moving upstream examples; lock the selected versions before deployment. Keep each candidate in its own compatible environment. Never concatenate the catalog into a global installer.

## Freshness findings that change decisions

- TimesFM 3.0 weights are non-commercial; Apache 2.5 remains the conditional forecasting baseline. Jina reranker 3.5 also has a non-commercial license.
- Letta V1 is retired; current work lives in letta-ai/letta-code. Daytona’s current SDK is distinct from its last public core, whose development moved private.
- SGLang 0.5.20 requires CUDA 13; the working local vLLM 0.25 service is retained after the recorded 0.29 WSL failure.
- Lumibot release license/setup metadata conflict; Fincept has additional commercial restrictions. Vectorbt’s Commons Clause and separate PRO product are explicit.
- GitHub latest-release tags can refer to SDKs/plugins rather than core packages. Mem0, LangGraph, OpenBB, Darts and forecasting models need artifact-specific version labels.

The underlying source citations and precise scopes appear in the layer guides. See [publication coverage history](../../docs/convergence-audit.md) for the earlier, smaller audit.

## Subsequent native gap resolution

See the [resolution ledger](../../blueprints/us-equities/gap-resolution.md) for real DeerFlow→native Astra inference, the patched LEAN/adaptor build, Dagu workflow hosting and the current gateway/account boundary. Historical receipts above retain their original scope and counts.

The [bounded source follow-up](source-followup.md) refreshed the unchanged public-star identities and four adopted release pins. Two additional observability alternatives expand the index to 453; neither was installed. The follow-up also distinguishes abtop modes that can invoke a model from its private model-free JSON snapshot.

The later [research-runtime evidence](../../blueprints/us-equities/research-runtime/receipt.json) adds real Dagu packet/Parquet preparation and a standalone Claude report. The new paired Astra run is allowance-blocked and the SEC acquisition returned HTTP 403. [Restic acceptance](../../blueprints/us-equities/hosting/backup/receipt.json) establishes only a same-host backup and verified restore of selected static public files; it does not establish off-host or live-database recovery.
