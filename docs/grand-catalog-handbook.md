# Grand catalog handbook: foundation, runtimes and the north star

This is the handbook for the catalog as frozen on **September 22, 2026**. It covers
two catalogs: the **foundation** that every native Claude and Codex session runs
on (20 layers), and the **US-equities north star** that builds simulation, paper
and live trading on that foundation (12 layers). Every layer records its winning
repositories, the named alternatives, why the winners were chosen, the evidence
class behind that choice and the comparison that would overturn it. The
generated section at the end of this page holds those per-layer verdicts; this
prose explains how to read them, what they do not establish and how to rerun
them against a later landscape.

A selection answers a stated requirement with the evidence available on that
date. It is not a claim that a repository wins every benchmark, and it does not
certify that another PC is configured. Start from a reviewed Git revision and
the [landscape manifest](../catalogs/landscape/manifest.json).

| Measure (2026-09-22) | Value |
| --- | --- |
| Foundation layers / trading layers | 20 / 12 |
| Layers with a recorded verdict | 32 of 32 |
| Selected, versioned components | 69 |
| Foundation capability decisions | 54 |
| Repository identities in the discovery index | 844 |
| Trading gates established / total | 7 / 20 (no rung ready) |

Use the [offline explorer](ecosystem/index.html) for every candidate, alternative
and evidence file. Its counts come from the canonical identity index;
candidate-layer rows are not distinct repositories. Public stars and awesome
lists are discovery sources, not installation commands or proof of quality, and
not every child link of every awesome list has been evaluated.

### How the September 22 verdicts were produced

The foundation taxonomy was frozen at 20 layers by adding four layers that had
been folded into others: agent SDKs and runtime workers, MCP servers and client
surfaces, secrets and credentials, and git practice with GitHub automation.
Model routing, packaging and the dashboard remain cards inside existing layers.
The trading catalog keeps 12 layers; its four older domain rows (research memory,
workers and operations, market data, simulation and execution) survive as the
`group` of each trading row.

Each layer was given a stripped evidence packet. An Opus proposer selected the
winner set from retained evidence, and two Opus refuters attacked it from the
evidence and challenger angles, with one revision round after any refutation or
major finding.
The record tool then applied the rules in code: every recorded winner must name
its evidence class and the reason it beats the alternatives, and the tool derives
its platform status from that evidence class and supplies its install anchor. The dated
[convergence manifest](../catalogs/sota-convergence/manifest-20260922.json) was
refreshed from the same day's lane run. Sealed lane returns are under
`evidence/artifacts/layer-verdicts-20260922/claude/`. A row records one evidence class
for its whole winner set, chosen by the lane. The recorded trading run asked for the
weakest class among the winners; the foundation run did not. Read each winner's
`why_selected` for its own evidence.

The trading packets were rebuilt after the first recording. In the first run every
trading layer received its group's shared candidate list, so sibling layers chose from
identical candidates. Two intermediate layer-specific runs were superseded after
independent review found that manifest review labels still revealed the withheld
decision. The recorded trading verdicts come from the final run
(`lane_packets.py --trading-candidates manifest`). In that run each packet held the
convergence manifest's own entries for the layer, with evidence from their domain
cards. It carried no review labels and supplied the layer's taxonomy scope terms.
Evidence fields still correlate with the withheld decision: incumbent entries more
often carry native evidence and an install recipe, and some card role text says
"optional" or "fallback".
`identity-provenance` was re-run alone after the record step rejected its first
return. The foundation packets were identical in every run.

**The Codex lane did not run.** The account's usage limit was exhausted until
September 28, so every row records `lanes.agreement: codex_absent` with that gap
named. The verdicts are one model family's reading of retained evidence, checked
by refuters of the same family. They are not a cross-family convergence.

Earlier records remain linked for their own findings: the
[independent Claude adjudication](claude-blind-adjudication-20260921.md), the
[20-layer blind findings](blind-catalog-layer-findings-20260921.md), the
[September 22 reconciliation](catalog-reconciliation-20260922.md) and the
[comparison progress](comparison-progress-20260922.md), whose worker, retrieval,
memory and parity comparisons remain unresolved or blocked.

## What qualifies a selection

Evaluate repository quality against the task before investing in installation:

1. **Capability:** read the relevant implementation, documented interfaces and
   limitations at a source pin. Separate an advertised feature from our use of it.
2. **Evidence:** prefer relevant upstream tests/examples and actual returned
   behavior; distinguish those from our fixtures, integration tests and reviews.
3. **Maintenance and provenance:** inspect source/release history, dependency
   declarations and version compatibility. Recent activity and star counts do
   not establish maintainability or superiority by themselves.
4. **License and deployment fit:** record the declared license, required services,
   provider/account boundaries and platform assumptions. A license label is not
   a legal or complete dependency audit.
5. **Lifecycle and portability:** establish installation scope, useful operation,
   state ownership, restart, export/restore and rollback as required by the task.
6. **Quality and cost:** compare useful answers/results, omissions and failure
   handling on the same frozen workload; count ingestion, indexing, query,
   maintenance and failed attempts. Mark unmeasured cost or quality unknown.

The [candidate quality review](candidate-quality-review-20260921.md) records the
focused source checks. It does not assign invented aggregate scores. Reviewer
agreement is advisory: the coordinator checks each finding against original
sources and actual results. See the
[runtime review record](../blueprints/catalog-runtime-review/README.md) and the
[acceptance evidence policy](acceptance-evidence-policy.md).

Every recorded winner carries one evidence class. Read it before relying on the
winner:

| Evidence class | Meaning |
| --- | --- |
| `native_proven` | The component ran natively on the recorded host and a receipt retains the result |
| `local_integration` | Our own integration tests or a local run exercised it; upstream behavior is not re-established |
| `synthetic` | Only fixtures were exercised; no real workload or broker |
| `source_review` | Read at a source pin; nothing was executed |
| `measured_comparison` | A matched comparison on the same workload decided it (none recorded yet) |

Layer decisions use these labels:

| Decision | Meaning |
| --- | --- |
| Retain | The current choice stands on its evidence |
| Keep but compare | The current choice stands, but a named comparison is still owed |
| Adjust | The current choice changes in a recorded, bounded way |

Candidates carry the older dispositions (selected, conditional, unqualified,
overlap, out of scope, measured tradeoff, observed failure). A candidate is never
promoted by reviewer agreement, a newer release or a star count.

## Foundation selection by layer

The generated table below is authoritative for winners, pins, evidence classes
and overturn conditions. This summary adds what each layer still needs on a new
host. The [foundation ledger](../catalogs/landscape/foundation.json) holds the
full rows; the [convergence manifest](../catalogs/sota-convergence/manifest-20260922.json)
owns versions, and this table does not create a second package lock.

| Layer | Recorded winners (decision) | Next meaningful acceptance |
| --- | --- | --- |
| Native clients | Claude Code, Codex (retain) | Native sign-in, discovery, useful task and continuation per client |
| Instructions and skills | ECC selection, TypeSafe and OpenAI skills (adjust) | Relevant task use with source pins and explicit worker context |
| Workers | Claude Code, Codex, Worktrunk (keep but compare) | Owned writing worktrees, integration and independent evidence review |
| Isolation | Worktrunk, sandbox-runtime (retain) | Exercise the required restriction; worktrees do not enforce it |
| Code navigation | Serena, jCodeMunch, codebase-memory-mcp (retain) | Exact source retrieval and original-code confirmation |
| Document retrieval | QMD, Poppler (keep but compare) | Corpus- and format-specific retrieval and conversion checks |
| Semantic RAG | SocratiCode, Qdrant, vLLM (keep but compare) | Hardware-compatible embeddings, scoped indexing and real retrieval |
| Durable memory | ai-memory (keep but compare) | Scoped cross-client recall and restore; matched quality comparison still owed |
| Web research | Tavily CLI, agent-browser, OpenResearch (retain) | Actual source acquisition, attribution and task-specific completeness |
| Token efficiency | RTK, Headroom, ccusage (keep but compare) | Recoverable originals and matching usage categories; no blanket savings claim |
| Quality and evaluation | promptfoo, Playwright Test (retain) | Meaningful behavior checks; source validation is not model-quality evidence |
| CI and supply chain | zizmor, Syft, GitHub attestations (retain) | Actual scoped runs; an inventory is not a vulnerability verdict |
| Scheduling and supervision | systemd, Dagu (keep but compare) | Failure, cancellation and in-flight restart behavior |
| Hosting and services | FastAPI, PostgreSQL, Next.js (retain) | Reproduce the scoped application; production hosting is separate |
| Recovery and portability | Restic (keep but compare) | Empty-target install and off-host restore, then consumer verification |
| Observation and inference | OpenTelemetry Collector, Prometheus, Grafana (keep but compare) | Actual task/event delivery and recovery on the destination host |
| Agent SDKs and runtime workers | Codex SDK (retain) | A rerun of the matched three-arm worker comparison |
| MCP servers and client surfaces | MCPorter, MCP Inspector (retain) | Scoped server discovery and contract checks per client |
| Secrets and credentials | Gitleaks (keep but compare) | Full-coverage scanning and a credential-store decision per host |
| Git practice and GitHub automation | Worktrunk, Difftastic, gh CLI (retain; source review only) | Executed hosted runs of each automation lane |

Optional container platforms, cloud providers, inference gateways and alternative
orchestrators are not a universal startup bundle. Select them through the
[hosting comparison](hosting-container-practice.md) and their per-layer decisions.
This handbook does not start services, create schedules or select paid hosting.

## Runtime workers, SDKs and research applications

The agent-SDK layer's recorded winner is the `codex` component (Codex CLI and
SDK, 0.155.1). The exercised programmatic research worker uses its **Python SDK**
(`openai-codex`), explicitly selecting the native Codex binary. **OpenAI Agents SDK** and **Claude Agent
SDK** remain application-runtime candidates; the overturn condition is a matched
three-arm worker comparison. The locked environment includes `openai-codex`,
`openai`, `alpaca-py`, `duckdb` and `exchange-calendars`; the lock pins 36
distributions in total. Use the [SDK lock and native uv recipe](../adoption/sdk/README.md).

The [SDK, harness and runtime coverage sweep](../catalogs/sota-convergence/sdk-runtime-coverage-20260922.md)
examined agent SDKs, coding harnesses, durable runtimes, sandbox and worker
runtimes, dispatch frameworks and protocol SDKs beyond Claude and Codex. It
recorded 18 keep-but-compare, 7 not-adopted, 6 refuted and 6 targeted
candidates and one integrate-now item, with preregistered criteria and a
completeness critic. No candidate replaced an incumbent.

Native Claude workers and workflows, and a retained Codex-analysis to
Claude-review pair, complement that worker. Neither agreement nor a completed
model response proves the underlying source claim.

**DeerFlow is exercised only within a narrow boundary.** One unmodified, pinned
embedded `invoke_acp_agent` call used Codex ACP to review two existing receipts.
This did not qualify its planner, web-research pipeline, UI, persistent service,
integrated RAG or recovery. The adapter's `read-only` label mapped to
`workspaceWrite/on-request`, so observed read behavior does not establish
enforced read-only access. See the
[DeerFlow receipt](../blueprints/us-equities/deerflow/research-receipt.json).

| Requirement | Candidate escalation | Comparison needed before promotion |
| --- | --- | --- |
| Application-owned long-running agent state | Deep Agents / LangGraph | Same research task, source quality, checkpoint/interruption behavior and total usage |
| Native agent control across remote environments | OpenHands SDK / Agent Canvas | Actual ownership, isolation, cancellation and artifact recovery |
| Programmatic application integration | OpenAI Agents SDK / Claude Agent SDK / Microsoft Agent Framework | Required API/tools/events and lifecycle against the native baseline |
| Multi-host durable effects and long waits | Temporal / Restate | Host loss, retries, duplicate external effects and recovery |
| Python research flows or data assets | Prefect / Dagster | Real pipeline scheduling, lineage, backfills and operating burden |
| Specialized financial research assistant | Dexter and other domain research candidates | Source-grounded answers and point-in-time data boundaries; no execution inference |

Use one coordinator and bounded independent workers. Writers own separate
worktrees and the coordinator integrates. Give each worker its requirement,
revision, paths, relevant skill context, output contract and stop condition.
Record requested and resolved model and effort separately. On September 22 the
`opus` alias on this host moved from Opus 5 to Opus 5.5 part-way through a lane
run, so a packet's stamped model can differ from the model a child actually used. Preserve native
sign-ins and never copy authentication stores. A filesystem sandbox alone does
not remove inherited remote-tool access.

## Memory selection and the strongest relevant challengers

ai-memory remains the shared project-memory choice because scoped native
Codex/Claude use, bounded outcome capture, native Codex task consolidation and
isolated restoration have actual evidence. ai-memory's own internal LLM
consolidation was disabled in that test. The 52 restored pages comprised **one
ordinary decision and 51 System pages**, so that test does not represent a large
project corpus. Captured excerpts are bounded observations, not complete native
transcripts.

The priority comparison is ai-memory versus **Hindsight and Basic Memory** on
representative project decisions, superseded facts, failed approaches, exact
citations, no-answer cases and cross-project isolation. Use the same downstream
model/context budget, independent frozen answers, repeated runs and complete
ingestion/query/maintenance usage. Include deletion and empty-target restoration.
There is no completed matched quality/cost comparison yet.

A [tiny lexical lifecycle comparison](../blueprints/memory-lifecycle-probe/README.md)
passed 28 content checks for ai-memory and Basic Memory: writes, reads, updates
and current-search deletion, plus ai-memory restart/backup and Basic Memory
text-index rebuild. Its first ai-memory attempt failed a no-model-download
constraint; the corrected run explicitly disabled embeddings. Unequal recovery
checks and this three-note fixture do not settle semantic recall or justify a
memory-store migration.

Graphiti, Cognee and OpenViking are credible for temporal/relationship or broader
research-context requirements. Mem0 and Supermemory may fit application memory;
Letta Code changes the worker/runtime architecture. Claude-mem is an alternative
capture/retrieval stack. Review current local or multi-client support before
reusing an old cloud-only or Claude-only exclusion. Compare stores in isolated
test scopes, and do not silently add competing authoritative capture paths.

## Setting up a new machine

Follow [adoption/bootstrap.md](../adoption/bootstrap.md), one ordered page from a
pinned clone through native sign-in, rendered configuration, services, the status
report and a per-host receipt. Each step points at the component recipes rather
than repeating commands.

| Platform | Status | What exists |
| --- | --- | --- |
| Linux / WSL2 x86_64 | Accepted | [Platform page](../adoption/platforms/linux-wsl2.md), pinned `bootstrap-linux.sh` that fails closed on unpinned components, weekly hosted bootstrap lane |
| macOS arm64 | Drafted, not accepted | [Platform page](../adoption/platforms/macos-arm64.md), `bootstrap-macos.sh`, one [hosted-runner smoke run](../evidence/receipts/adoption-macos-hosted-smoke-20260922.json); nothing ran on a Mac workstation |

The macOS profile targets Apple Silicon with 24 GB of unified memory. Its
embedding backend is llama.cpp Metal serving embeddinggemma-300M. Moving to
Nemotron-3-Embed-1B on a 48 GB machine is the recorded upgrade. It is an open
gate, not a scheduled step: it needs a GGUF build upstream, a retrieval
comparison on the project corpus that favours it, and memory headroom on the
host.

Configuration comes from templates, not copied files. `tools/adoption/render_config.py`
renders `~/.claude/settings.json`, `~/.codex/config.toml` and the project Codex
configuration with host-specific paths, and `--check` confirms byte identity with
the live files. Credentials are never transferred; each host signs in natively.

| Order | Profile / action | Destination acceptance |
| --- | --- | --- |
| 1 | Pinned checkout and portable validators | Exact revision, intact hashes and explicit installation paths |
| 2 | `foundation-cpu` (or `macos-arm64-foundation`) | Native Codex/Claude sign-in, tool discovery, a useful QMD/context call and scoped memory retrieval |
| 3 | Shared skills and workers | One bounded source/build/review task with owned changes |
| 4 | `research-runtime` | Recreate the SDK lock in a new prefix and run the retained research fixture |
| 5 | `observability` and `recovery` when selected | Real event delivery and an isolated logical restore |
| 6 | `semantic-rag` when hardware fits | Actual inference, scoped index/watch queries and recovered state |
| 7 | `trading-nautilus` | Engine replay; each broker's operation is qualified separately |

The prerequisite report only detects executables and platform requirements. A
clean prefix on the existing host proves that prefix's reproducibility, not a
fresh distribution, a second physical PC, a GPU stack, credentials or all
services. See the [clean-install review](../blueprints/catalog-clean-install/README.md).
Do not synchronize a lock into a system or shared environment, because an exact
sync can remove packages outside that lock. Keep Desktop, native Linux Codex and
native Linux Claude account and configuration scopes separate.

## Foundation to the north star

The trading catalog reuses the foundation and adds data, strategy, risk and
broker-specific acceptance. Its 12 layers are grouped by the four older domain
rows. The [trading ledger](../catalogs/landscape/us-equities.json) holds the
recorded verdicts.

NautilusTrader 2.0.0rc5 is the selected destination engine and LEAN is the
frozen historical comparator. IBKR through Nautilus is the selected live-primary
broker path, with a separate Alpaca paper path. Neither broker path is accepted
for live use. A bounded engine replay or paper roundtrip does not establish
point-in-time universe quality, complete broker recovery or a winning strategy.
Use [runtime-target.json](../catalogs/us-equities/runtime-target.json) for the
destination's exact contracts.

The path from simulation to paper to live is tracked as a
[gate ladder](../catalogs/us-equities/gates-20260922.json) of 20 gates, each
naming its owner, evidence class, receipt and machine-checkable flip condition.
`python3 scripts/trading_gates.py --check` verifies the ladder arithmetically; a
status changes only through a dated commit after the checker lists the gate as a
flip candidate. On September 22:

| Rung | Established | Open |
| --- | --- | --- |
| Simulation | Offline equity replay, rc5 supply-chain scan, fail-closed snapshot gate (synthetic), exchange_calendars in the stack | SPY/LEAN parity (blocked on two unsupported mappings), dividend module, pre-2020 delisting, dated security identity, point-in-time news and filings, paid data arm |
| Paper | Alpaca paper smoke, broker-path alert rules (synthetic), credential handling | Adaptive-paper broker trial |
| Live | None | Leverage ladder 1x/2x/4x, native fault behaviour, IBKR local acceptance, explicit live go |

No rung is ready. Catalog inclusion does not authorize live configuration, paid
data or hosting, or orders.

## Repository automation and releases

The [GitHub automation handbook](github-automation.md) owns the check and
maintenance design. In brief:

- **Required on `main`:** `validate` (validators, the zizmor and actionlint
  workflow audit, the verdict check, the examples byte-identity check and the
  unit tests, which include the gate-ladder check), `token-report` and
  `secret-scan`. The main ruleset also blocks deletion and force-push and
  requires linear history and a pull request. Tags cannot be deleted or
  force-moved. These rulesets were applied on September 22 and observed live
  through the GitHub API; the generated rows for the CI and git-automation
  layers cite the records from before that application.
- **Report-only lanes:** the Monday `catalog-freshness` lane rebuilds the
  convergence manifest from current GitHub metadata and publishes pin drift as an
  artifact, without writing back. `supply-chain` inventories and scans the pinned
  rc5 install with Syft and Grype. `adoption-bootstrap` exercises the pinned
  bootstrap scripts on hosted runners.
- **Secret scanning coverage:** `secret-scan` fails on any finding. It uses
  reviewed, path- and key-scoped allowlists and skips files over 2 MB, so the
  generated explorer HTML is not scanned; its sources are. Its first hosted run
  timed out on full history before the size skip was added.
- **Releases:** pushing a `v*` tag runs `publish-catalog`, which archives the
  validated commit and attests both the archive and an SPDX SBOM. Verify a
  release with `gh attestation verify`.
- **Not activated, with recorded reasons:** CodeQL and Dependabot for Python
  requirements.

## How future sessions continue

Read this handbook, then only the evidence of the layer you are changing. Record
the checkout revision, host, requirement, current result, failed attempts and the
next check that could change the decision.

To rerun the verdicts against a later landscape, follow the
[convergence practice](../recipes/sota-convergence-practice.md) and the tooling in
[`tools/sota-convergence/`](../tools/sota-convergence/README.md):

1. Extract the layers and collect current GitHub metadata (`extract_layers.py`,
   `github_freshness.py`); the weekly freshness lane shows when this is due.
2. Refresh the dated convergence manifest: run the saved `sota-convergence`
   workflow, then `build_manifest.py` (see the tooling README).
3. Build stripped packets per layer with `lane_packets.py --trading-candidates
   manifest`, so each trading packet carries that layer's own manifest entries
   (the default `ledger` mode reproduces the first run's group-wide trading
   packets). Then run the Claude lane through the saved
   `layer-verdict-lane` workflow, which lives in the agent-lab repository's
   `.claude/workflows/`, not in this catalog.
4. Run the independent Codex lane (`codex_lane.py`) on the same packets without
   exposing the Claude returns.
5. Record both lanes with `record_verdicts.py`. A row is `same_winner` when both
   lanes name the same set of winner components. When they disagree, the row
   stays `pending_lanes` until an adjudication file is supplied.
6. Regenerate this page's tables with `build_verdicts.py --write` and check with
   `--check`.

Reopen a layer on a demonstrated gap, a changed requirement, relevant upstream
behavior or a challenger result. A new release, a star count or reviewer
agreement alone never promotes a candidate. Preserve historical records with
their dates and superseding links.

### Limits of the September 22 verdicts

- **No cross-family lane.** Every row is `codex_absent`. Run the Codex lane once
  the usage limit lifts and record the agreement per row.
- **Trading candidates are layer-specific; trading requirements are not.** Each
  trading packet held that layer's own manifest entries and scope terms. The four rows
  the first run had flagged for naming other layers' tools now name their own:
  - `security-supply-chain`: Syft, Grype and Gitleaks.
  - `data-quality-orchestration`: Dagu and Pandera.
  - `evaluation-experiments`: Inspect AI, MLflow and the agent retrieval benchmark.
  - `agents-models-workers`: the Codex native SDK, ai-memory and SocratiCode.

  The ledger's v1 `requirement`, `current_choice` and `decision` text is still shared
  across each group and was not re-derived per layer. Several trading rows record
  that their group requirement does not fit the layer. A candidate the manifest does
  not list for a layer cannot be chosen for it, so a missing tool is a manifest gap
  to fix at the next convergence run. `execution-broker` records the adaptive-paper
  Alpaca adapter and alpaca-py as `local_integration`. The adapter has placed no
  paper orders (its broker trial is pending), and the Nautilus IBKR adapter has no
  broker acceptance yet.
- **The two catalogs can pin different versions of one component.** Every trading
  winner's pin equals the convergence manifest's pin for that component id. Four
  foundation winners have no manifest component and record `unpinned`
  (`candidate:typesafe-ai-skills`, `candidate:openai-skills`,
  `candidate:actions-attest`, `candidate:cli-cli`). The trading
  `agents-models-workers` row records ai-memory v2.3.1, which is what its cited
  receipt executed. The foundation `durable-memory` row records 2.3.2 from later
  evidence. Upgrading one catalog's pin does not upgrade the other's.
- **Evidence strength varies by row.** One foundation row (`git-github-automation`)
  and two trading rows (`identity-provenance`, `evaluation-experiments`) record
  `source_review` winners. `data-quality-orchestration` records `synthetic`: Dagu ran
  natively, but Pandera ran only on fixtures. No winner rests on a
  `measured_comparison`, and every `keep_but_compare` row names the comparison it
  still owes.

The catalog is complete for its declared review set while comparative quality
remains open. New-host acceptance is recorded on that host; neither a cloned
receipt nor this page certifies it.

<!-- verdicts:begin -->
## Per-layer verdicts (generated)

Joins the landscape ledger's layer-verdict schema v2 rows with the dated SOTA-convergence manifest's per-layer components/entries and adoption/manifest.json's recipe_map. Rows are rendered as the ledger records them (recorded rows from the record tool, pending_lanes rows unchanged); this generator does not itself run a lane, select a winner or claim an execution result.

### foundation

| Layer | Group | Verdict status | Winner(s) + pin | Evidence class | Alternatives | Overturn when | Recipe anchor | Platform status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agent-sdks | - | recorded | codex @ 0.155.1 | native_proven | 4 | The verdict changes if a rerun of the matched three-arm worker comparison turns out better for c3. The rerun must use t… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| ci-supply-chain | - | recorded | zizmor @ 1.30.1; syft @ 1.52.0; candidate:actions-attest @ unpinned | native_proven | 5 | Any of the following would change the verdict. (a) Workflow-analysis slot: run python3 -m unittest discover -s tests -p… | blueprints/convergence-practice/ci-security/README.md, blueprints/us-equities/supply-chain/README.md, catalogs/foundation/automation.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| code-navigation | - | recorded | serena @ 2.0.0.dev0 @ c6fbd1c5932df2494ffa0020af5a9fbe80b82143; jcodemunch-mcp @ 1.108.319; codebase-memory-mcp @ 0.11.0 | native_proven | 2 | Overturn this verdict if a sealed task set in the target languages shows a different result. The seed is fixtures/befor… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| document-retrieval | - | recorded | qmd @ 2.8.3; poppler @ 26.09.0 | native_proven | 4 | Two results would change this verdict, either way:
1. A sealed, representative rerun of the QMD benchmark on blueprints… | blueprints/convergence-practice/document-ingestion/README.md, recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| durable-memory | - | recorded | ai-memory @ 2.3.2 | native_proven | 9 | The comparison named in blueprints/blind-catalog-convergence/memory-experiment.json (next_decision_changing_test) is ex… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| git-github-automation | - | recorded | worktrunk @ 0.79.0; difftastic @ 0.71.0; candidate:cli-cli @ unpinned | source_review | 1 | Owned worktrees: rerun blueprints/convergence-practice/wsl-native-tools/run.py, with tests/test_wsl_native_tools.py as … | docs/github-automation.md, recipes/README.md, recipes/native-upgrades-20260921.md | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| hosting-services | - | recorded | fastapi @ 0.141.1; postgresql @ 18.6; nextjs @ 16.3.5 | local_integration | 8 | Rerun the frozen acceptance for the same locked application and database under one chosen container lane (Docker Engine… | blueprints/convergence-practice/application-delivery/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| instructions-skills | - | recorded | candidate:typesafe-ai-skills @ unpinned; affaan-m/ECC @ dd6ee538aee0f548d4a6b520118f875431fd749e; candidate:openai-skills @ unpinned | local_integration | 7 | The verdict changes in two cases. First, if a concrete task exposes a missing procedure and a matched trial shows a pin… | catalogs/landscape/native-practice.json, recipes/claude-native-profile.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| isolation | - | recorded | worktrunk @ 0.79.0; sandbox-runtime @ 0.0.77 | native_proven | 5 | Change the boundary verdict if two things happen: a task requires hostile or untrusted code isolation, resource limits … | recipes/README.md, recipes/native-upgrades-20260921.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| mcp-surfaces | - | recorded | mcporter @ 0.13.13; mcp-inspector @ 2.7.0 | native_proven | 1 | Change the verdict only after an executed same-host comparison in which a challenger passes the use-stage acceptance th… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| native-clients | - | recorded | claude-code @ 2.1.278; codex @ 0.155.1 | native_proven | 3 | An application task needs structured events, custom tools or programmatic session control that the native CLI path cann… | recipes/README.md, recipes/claude-native-profile.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| observation-inference | - | recorded | opentelemetry-collector-contrib @ 0.161.0; prometheus @ 3.14.0; grafana @ 13.2.2 | native_proven | 10 | The verdict changes if the current Collector-to-Prometheus-to-Grafana path cannot answer a required trace or usage ques… | observability/README.md, observability/backends/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| quality-evaluation | - | recorded | promptfoo @ 0.123.1; playwright-test @ 1.63.0 | local_integration | 7 | First overturn: a defined tool-use or extraction requirement that cannot be expressed in the Promptfoo or Playwright la… | blueprints/convergence-practice/wsl-application/README.md, recipes/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| recovery-portability | - | recorded | restic @ 0.19.1 | native_proven | 6 | Three checks could change this verdict. (1) Re-run the blueprints/convergence-practice/offhost-restore/README.md or blu… | blueprints/us-equities/hosting/backup/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| scheduling-supervision | - | recorded | systemd @ 255.4-1ubuntu8.17; dagu @ 2.16.6 | native_proven | 4 | The verdict changes if a real workload needs host-loss survival, days-long waits or durable cross-host effects. The com… | blueprints/us-equities/hosting/README.md, blueprints/us-equities/worker-supervision/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| secrets-credentials | - | recorded | gitleaks @ 8.30.1 | native_proven | 1 | Change the verdict only if an executed comparison beats c1 on the same scope.

Option 1: extend blueprints/convergence-… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| semantic-rag | - | recorded | socraticode @ 1.14.0; qdrant @ 1.19.1; vllm @ 0.25.0 | native_proven | 5 | An executed comparison already exists outside the packet root: the agent-lab semantic-rag runner, <host-path>/run-arms.… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| token-efficiency | - | recorded | rtk @ 0.49.0; headroom @ 0.37.0; ccusage @ 20.0.24 | local_integration | 4 | Three checks would change this verdict.

(1) For RTK: `python3 scripts/native_token_ci.py --install --output <new direc… | recipes/README.md, recipes/native-upgrades-20260921.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| web-research | - | recorded | tavily-cli @ 0.1.8; agent-browser @ 0.38.1; openresearch @ 0.2.7 | native_proven | 5 | Two checks could change this verdict.

1. Browser lane: run agent-browser, Playwright CLI and a challenger (Browser Use… | recipes/README.md, recipes/native-upgrades-20260921.md, recipes/tavily.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| workers | - | recorded | claude-code @ 2.1.278; worktrunk @ 0.79.0; codex @ 0.155.1 | native_proven | 9 | The verdict changes in three cases.

1. A real task needs durable multi-host state, approval waits or effect recovery b… | recipes/README.md, recipes/claude-native-profile.md, recipes/native-upgrades-20260921.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |

### foundation (per-layer narrative)

#### Agent SDKs and runtime workers (agent-sdks)

- codex @ 0.155.1 — c4 (Codex SDK/CLI) is the only adopted candidate whose SDK interface has several retained native executions on this host, and it is the existing working integration. What was observed, from my own source review of the retained records:
(a) observability/session-e2e.md line 28 records 'Official Codex SDK `thread.turn(...).run()` | `completed`, Astra/OpenAI, 12,493 ms'. Line 30 records native SDK usage of input 40,369 and total 40,518.
(b) blueprints/us-equities/workers/README.md lines 3-7 say the official Python Codex SDK ran with the native Codex 0.155.1 binary and the task completed in 58,410 ms with Context Mode tool calls. Lines 39-41 name the SDK surface used: CodexClient.initialize, model_list, account/rateLimits/read, AsyncCodex.thread_start, thread.read, thread.turn and turn.run.
(c) adoption/paired/README.md line 15: 'Official Codex SDK, native GPT-6 Astra | Completed in 14,953 ms'.
(d) In the three-arm worker comparison (arm B, 'Codex SDK via native_worker.py'), evidence/artifacts/comparison-progress-20260922/worker-receipts-followup.json lines 113-151 show replays S1 and S2 'completed' with reported_completeness 1.
docs/foundation-closure-20260921.md lines 78 and 83 set the scope: 'Existing Codex SDK integration remains accepted only within its recorded tests' and 'Retain existing working integration; qualify a version change before promotion'. catalogs/foundation/decisions.json (agent-sdk-runtime-selection) keeps the selection 'conditional' with review_status 'source_review' for this taxonomy freeze.
Corrections to my earlier round:
- The executed SDK is the Python package openai-codex 0.154.0, which bundles CLI 0.154.0 and is run against the separately accepted native Codex 0.155.1 through --codex-bin (adoption/sdk/README.md line 5). The pin 0.155.1 is the CLI version. The npm @openai/codex-sdk 0.155.1 in source-observations.json has no recorded execution.
- The historical token-practice inventory row is no longer used as SDK evidence (its line 4 says 'historical_inventory' and line 62 says it is not fresh E2E passes).
The native_proven class applies only to the start/turn/run interface on this WSL host. Resume, cancellation and custom (non-MCP) tools are not shown for the SDK. On the one matched run, c4's cancellation returned no receipt (see alternatives), and that comparison is unresolved with no arm accepted.

Alternatives:
- Claude Agent SDK (measured_tradeoff) — Correction: c3 does have native execution in a retained matched run. The earlier round said 'no native run and no matched comparison'; that was wrong. The worker comparison's arms were native Claude CLI, 'Codex SDK via native_worker.py' and 'Claude Agent SDK' (summary.json lines 140-144; docs/comparison-progress-20260922.md line 29). In worker-receipts-followup.json, arm C replays S1 and S2 are 'success' with reported_completeness 1 (lines 177-216). That matches arm B (Codex), whose replays are 'completed' with completeness 1. On the cancel case, C3 returned 'interrupted', exit_code 130, usage 'unavailable_after_interrupt' (lines 217-238). B3 returned 'no_receipt', exit_signal SIGINT, usage 'not_requested' (lines 152-176). So on this one observation, c3 returned a cancellation record where c4 returned none. This is an unranked trade-off, not a win. The comparison is 'unresolved', publication_eligible false, 'Two judging rounds refuted claims; no arm accepted as a winner and no SDK adoption follows' (summary.json lines 133-151). Recovery is unrun and artifact acceptance lacks a pinned judge (followup line 244). Neither interruption record proves zero provider consumption (line 243). 'No worker or SDK becomes a new accepted default' (comparison-progress lines 56-57). The installation is still not qualified as a default: foundation-closure line 82 says 'not newly installed or qualified' (registry Python 0.2.157, GitHub 0.2.156, TypeScript 0.3.278), and lines 88-96 require effective settingSources and SDK stop_task semantics to be tested. The version of c3 that ran in the comparison is not recorded in the public index I read.
- OpenHands SDK (conditional) — docs/foundation-closure-20260921.md line 86 (1.49.2, pinned at commit 856d99d4) says 'Conditional for remote/container workers; does not improve the current local review merely by installation'. Its scope, remote isolated worker environments, is narrower than the current local worker need. The only evidence is version metadata (source-observations.json). It was not an arm in the 2026-09-22 worker comparison (summary.json lines 140-144), and no installation, run or comparison is recorded.
- LangGraph (unqualified) — Not adopted. docs/foundation-closure-20260921.md line 85 (1.2.11, pinned at commit ed384f3a) says 'Deferred unless building an application needing these semantics' (explicit state and checkpoints). No retained application needs graph checkpoints, and no execution is recorded.
- Temporal (out_of_scope) — Not adopted. docs/foundation-closure-20260921.md line 84 (Temporal Python 1.33.0) says 'Deferred until required; adds a service and distinct effect/recovery semantics'. It is a durable workflow engine for work across several hosts, not a per-worker agent SDK. Line 64 assigns scheduling and supervision to Dagu and Linux user services: 'Avoid multiple independent retry owners for one effect'. This corrects the earlier citation of lines 94-96, which concern worker recovery not establishing SDK cancellation. No execution is recorded.

Overturn when: The verdict changes if a rerun of the matched three-arm worker comparison turns out better for c3. The rerun must use the native_worker.py run path in blueprints/us-equities/workers/README.md (lines 27-36) for c4 and the Claude Agent SDK arm for c3. It must also execute the recovery case under blueprints/convergence-practice/worker-recovery/README.md and judge artifact acceptance with a pinned judge, both of which are unrun per worker-receipts-followup.json line 244. The result must be publication-eligible and show c3 matching c4 on replay completion while beating it on cancel/resume session control and complete provider usage. The c4 verdict is also reopened if either of the following happens:
- A Codex SDK resume or cancellation test at the promoted SDK version fails.
- A version change (openai-codex 0.154.0 to a newer release, or a switch to the npm @openai/codex-sdk) is promoted without its own native run.
The synthetic suite tests/fixtures/codex-lane/ (fake codex binary) cannot confirm or overturn native SDK behaviour.

Open gaps:
- Codex SDK session resume is not shown. Retained SDK runs cover thread_start/thread.turn/turn.run (blueprints/us-equities/workers/README.md lines 39-41; observability/session-e2e.md line 28). A grep for 'resume' in blueprints/us-equities/workers returned no matches. foundation-closure line 83 describes a start/run/resume interface only as merit.
- Codex SDK cancellation: in the matched run, B3 has arm_status 'no_receipt', SIGINT and usage 'not_requested' (worker-receipts-followup.json lines 152-176). workers/README.md lines 47-50 say the turn deadline is not a provider spending cap or proof of remote cancellation.
- The matched worker comparison is unresolved: recovery unrun, no pinned artifact judge, two judging rounds refuted, publication_eligible false (summary.json lines 133-151). No quality ranking of c3 against c4 follows.
- The executed SDK version is openai-codex 0.154.0 (bundling CLI 0.154.0), not 0.155.1. The npm @openai/codex-sdk 0.155.1 (source-observations.json) has no recorded execution. The packet's pin 0.155.1 is the native CLI version.
- Custom tools: the retained Codex SDK runs used Context Mode MCP tools (workers/README.md line 7; session-e2e.md line 29). No SDK-defined custom tool is shown for any arm.
- Claude Agent SDK effective settingSources, SDK stop_task cancellation, provider billing cessation and distributed exactly-once effects are untested (foundation-closure lines 88-96). An untested capability has not failed.
- Correction: decisions.json next_gap cites 'docs/foundation-closure-20260921.md lines 78-84'. The SDK table is at lines 80-86 (rows 82-86).
- Correction: the evidence/receipts/token-practice-coverage-20260920.json codex row is a 'historical_inventory' (line 4) and 'not 52 fresh end-to-end passes' (line 62). It is withdrawn as SDK evidence.
- The packet's c4 decisions include rows unrelated to agent SDK selection (lean-workflow-child-routing, native-memory-learning-maintenance, native-process-defaults and others). native-session-resume concerns native client sessions, not the SDK.
- All SDK executions are on one WSL host. adoption/sdk/README.md line 24 says the fresh-prefix acceptance 'is another prefix on the same WSL host, not a physical second-machine deployment'.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-agent-sdks-20260922; codex: -)

#### CI and supply chain (ci-supply-chain)

- zizmor @ 1.30.1 — The requirement (packet line 252) has four parts. Each winner has retained native evidence for a different part. I opened these repository records myself; I did not re-run or observe any command or hosted run.

(1) Pinned Action references and workflow-injection defects: zizmor 1.30.1 (c7). evidence/receipts/native-linux-zizmor-20260920.json lines 31-54 records a native directory-wide scan of .github/workflows that returned exit 0 with 0 findings. The same receipt records exit 14 with 3 findings (artipacked, template-injection, unpinned-uses) on the unchanged inert fixture, plus a unittest run with passed 2 and skipped 0. The fixture is tests/fixtures/workflow-security/unsafe.yml.txt (actions/checkout@main on line 10; injection on line 11). catalogs/foundation/decisions.json (offline-security-inventory) records it as accepted_within_scope. zizmor's pin evidence covers only `uses:` Action references. The curl-downloaded binaries are pinned by sha256sum steps in the workflows (e.g. .github/workflows/supply-chain.yml lines 66-91), not by any candidate. Scoped permissions are credited to zizmor only through its clean pass. The fixture itself declares `permissions: contents: read` (lines 4-5), and no retained negative control shows zizmor rejecting an over-broad permission. The scoped-permission evidence is configuration review: supply-chain.yml lines 19-20 and docs/catalog-provenance.md lines 20-24.

(2) Actual runtime inventory: Syft 1.52.0 (c3). blueprints/us-equities/supply-chain/receipt.json lines 9-10 and 55-85 record status passed_scoped_inventory_acceptance. Syft found 36 packages, the CycloneDX PURLs matched Syft, and all 36 installed dist-info entries matched. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json lines 13-16, 77-82 and 102-104 separately record a native Syft scan (exit 0) of the pinned NautilusTrader 2.0.0rc5 paper runtime's site-packages, which returned 21 packages. That scan has no dist-info cross-check.

(3) Attributable hosted output: actions/attest (c4). catalogs/foundation/automation.json lines 208-221 and docs/catalog-provenance.md lines 8-16 record hosted publication run 35541322881 at d0fe136. An independent download matched the catalog digest. Original/altered/original verification returned 0/1/0, and a non-main dispatch was skipped with zero steps. This attributes the published catalog archive to its origin. It does not attribute CI check results. Check attribution comes from the ruleset's pinned check source (automation.json lines 17-22: required checks validate and token-report, check_source_app_id 15368), which no candidate owns.

These results are documented native evidence for one host and one commit. They are not a measured comparison against the alternatives.
- syft @ 1.52.0 — The requirement (packet line 252) has four parts. Each winner has retained native evidence for a different part. I opened these repository records myself; I did not re-run or observe any command or hosted run.

(1) Pinned Action references and workflow-injection defects: zizmor 1.30.1 (c7). evidence/receipts/native-linux-zizmor-20260920.json lines 31-54 records a native directory-wide scan of .github/workflows that returned exit 0 with 0 findings. The same receipt records exit 14 with 3 findings (artipacked, template-injection, unpinned-uses) on the unchanged inert fixture, plus a unittest run with passed 2 and skipped 0. The fixture is tests/fixtures/workflow-security/unsafe.yml.txt (actions/checkout@main on line 10; injection on line 11). catalogs/foundation/decisions.json (offline-security-inventory) records it as accepted_within_scope. zizmor's pin evidence covers only `uses:` Action references. The curl-downloaded binaries are pinned by sha256sum steps in the workflows (e.g. .github/workflows/supply-chain.yml lines 66-91), not by any candidate. Scoped permissions are credited to zizmor only through its clean pass. The fixture itself declares `permissions: contents: read` (lines 4-5), and no retained negative control shows zizmor rejecting an over-broad permission. The scoped-permission evidence is configuration review: supply-chain.yml lines 19-20 and docs/catalog-provenance.md lines 20-24.

(2) Actual runtime inventory: Syft 1.52.0 (c3). blueprints/us-equities/supply-chain/receipt.json lines 9-10 and 55-85 record status passed_scoped_inventory_acceptance. Syft found 36 packages, the CycloneDX PURLs matched Syft, and all 36 installed dist-info entries matched. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json lines 13-16, 77-82 and 102-104 separately record a native Syft scan (exit 0) of the pinned NautilusTrader 2.0.0rc5 paper runtime's site-packages, which returned 21 packages. That scan has no dist-info cross-check.

(3) Attributable hosted output: actions/attest (c4). catalogs/foundation/automation.json lines 208-221 and docs/catalog-provenance.md lines 8-16 record hosted publication run 35541322881 at d0fe136. An independent download matched the catalog digest. Original/altered/original verification returned 0/1/0, and a non-main dispatch was skipped with zero steps. This attributes the published catalog archive to its origin. It does not attribute CI check results. Check attribution comes from the ruleset's pinned check source (automation.json lines 17-22: required checks validate and token-report, check_source_app_id 15368), which no candidate owns.

These results are documented native evidence for one host and one commit. They are not a measured comparison against the alternatives.
- candidate:actions-attest @ unpinned — The requirement (packet line 252) has four parts. Each winner has retained native evidence for a different part. I opened these repository records myself; I did not re-run or observe any command or hosted run.

(1) Pinned Action references and workflow-injection defects: zizmor 1.30.1 (c7). evidence/receipts/native-linux-zizmor-20260920.json lines 31-54 records a native directory-wide scan of .github/workflows that returned exit 0 with 0 findings. The same receipt records exit 14 with 3 findings (artipacked, template-injection, unpinned-uses) on the unchanged inert fixture, plus a unittest run with passed 2 and skipped 0. The fixture is tests/fixtures/workflow-security/unsafe.yml.txt (actions/checkout@main on line 10; injection on line 11). catalogs/foundation/decisions.json (offline-security-inventory) records it as accepted_within_scope. zizmor's pin evidence covers only `uses:` Action references. The curl-downloaded binaries are pinned by sha256sum steps in the workflows (e.g. .github/workflows/supply-chain.yml lines 66-91), not by any candidate. Scoped permissions are credited to zizmor only through its clean pass. The fixture itself declares `permissions: contents: read` (lines 4-5), and no retained negative control shows zizmor rejecting an over-broad permission. The scoped-permission evidence is configuration review: supply-chain.yml lines 19-20 and docs/catalog-provenance.md lines 20-24.

(2) Actual runtime inventory: Syft 1.52.0 (c3). blueprints/us-equities/supply-chain/receipt.json lines 9-10 and 55-85 record status passed_scoped_inventory_acceptance. Syft found 36 packages, the CycloneDX PURLs matched Syft, and all 36 installed dist-info entries matched. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json lines 13-16, 77-82 and 102-104 separately record a native Syft scan (exit 0) of the pinned NautilusTrader 2.0.0rc5 paper runtime's site-packages, which returned 21 packages. That scan has no dist-info cross-check.

(3) Attributable hosted output: actions/attest (c4). catalogs/foundation/automation.json lines 208-221 and docs/catalog-provenance.md lines 8-16 record hosted publication run 35541322881 at d0fe136. An independent download matched the catalog digest. Original/altered/original verification returned 0/1/0, and a non-main dispatch was skipped with zero steps. This attributes the published catalog archive to its origin. It does not attribute CI check results. Check attribution comes from the ruleset's pinned check source (automation.json lines 17-22: required checks validate and token-report, check_source_app_id 15368), which no candidate owns.

These results are documented native evidence for one host and one commit. They are not a measured comparison against the alternatives.

Alternatives:
- actionlint (overlap) — Version 1.7.12 checks workflow syntax, expressions and action usage. It executes no job (docs/github-automation.md lines 93-95). The validate job downloads the pinned release, verifies its archive SHA-256 and runs it across all workflows (lines 116-118). validate is a required check (catalogs/foundation/automation.json lines 18-21). There is retained evidence of rejections: its embedded shellcheck found two sudo/redirection warnings, which were fixed (github-automation.md lines 119-122), and a first run exited 1 on a runner-context misuse (docs/catalog-provenance.md line 170). None of the retained evidence shows it covering permission scoping, pin enforcement, inventory or attribution. It is a complementary correctness gate next to zizmor, not a winner for this requirement's parts.
- Trivy (unqualified) — The packet marks Trivy adopted, but its only evidence ref records decision 'defer_until_sbom_and_db_freshness_policy' with execution_status research_only (catalogs/us-equities/hosting-source-review.json lines 144-160). No native execution was retained, so Trivy is untested, not failed.
- Dependabot (conditional) — Hosted initial scans 35541330440 and 35541327481 succeeded and opened major proposals #29 and #30. Their hash failures correctly blocked integration (catalogs/foundation/automation.json lines 32-36; docs/github-automation.md lines 56-62). It keeps GitHub Actions SHA pins current but does not detect or enforce unpinned uses. It owns only GitHub Actions references: pip is not activated, and the curl-downloaded binaries are outside its scope (docs/github-automation.md lines 375-404). Weekly timing and a nonempty minor/patch group are unobserved (automation.json lines 264-266).
- gitleaks (conditional) — Native gitleaks accepted clean controls and rejected inert fixtures (catalogs/foundation/decisions.json, offline-security-inventory). Its capability is secret detection, which is the secrets-credentials layer's concern (decisions.json secrets-credentials-policy, review_status source_review with no new execution). The hosted secret-scan evidence is incomplete: the first hosted run was cancelled by its own timeout during the history scan (docs/github-automation.md lines 465-469). secret-scan is named only in the committed ruleset, not the applied one (lines 296-302). The sources conflict on its failure policy: automation.json says no fail threshold has been decided, while github-automation.md lines 296-298 says the job fails on any detection.
- Grype (conditional) — The packet marks Grype not adopted. Its binary is version- and SHA-256-pinned. CI checks GRYPE_VERSION 0.119.0 against GRYPE_SHA256 3fa2dc4b... with sha256sum before extraction (.github/workflows/supply-chain.yml lines 79-91). The native receipt records publisher_checksum_matched and github_asset_digest_matched true (scan-nautilus-rc5-20260922/receipt.json lines 46-51). The earlier claim that it is unpinned was wrong. The 'tracks latest' wording in docs/github-automation.md lines 310-314 is a policy for choosing the next pin, and it keeps Grype out of the freshness job's drift table. What is not pinned is the vulnerability database: `grype db update` fetches the latest DB and only its build time is recorded (receipt lines 56-70). The native scan returned 0 matches (status passed_scoped_scan_zero_findings). The requirement does not ask for vulnerability verdicts. In CI, sbom-vuln is report-only, never passes --fail-on, and the threshold is explicitly pending (github-automation.md lines 278-285 and 319-324). Its packet ref docs/acceptance-evidence-policy.md has no Grype mention.

Overturn when: Any of the following would change the verdict. (a) Workflow-analysis slot: run python3 -m unittest discover -s tests -p test_workflow_security.py -v. It must report passed 2 and skipped 0; a skip means the check did not run, because the class is skipUnless(zizmor) (tests/test_workflow_security.py line 16). Also run the directory-wide scan recorded in evidence/receipts/native-linux-zizmor-20260920.json line 31, because the unit test scans only validate.yml (lines 41-42). If the clean directory is no longer exit 0 with 0 findings, or tests/fixtures/workflow-security/unsafe.yml.txt no longer yields exit 14 with unpinned-uses and template-injection, c7 is overturned. A permission-defect fixture (e.g. permissions: write-all) does not exist yet. If one is added under tests/fixtures/workflow-security/ and zizmor fails to reject it while another analyzer does, the scoped-permission part moves to that analyzer. (b) Inventory slot: re-run Syft and an alternative (e.g. Trivy SBOM) on the prefixes in blueprints/us-equities/supply-chain/receipt.json and blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json. The slot changes if Syft's 36/36 dist-info agreement fails, or if the alternative matches it and also covers non-Python or native-library content. (c) Attribution slot: c4 is overturned if a new hosted publication run fails original/altered/original verification (expected 0/1/0) under the procedure in docs/catalog-provenance.md. (d) If the requirement adds vulnerability gating with a decided threshold and a pinned or recorded DB snapshot, compare Grype (c8) using blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json.

Open gaps:
- No retained negative control shows zizmor, or any candidate, rejecting an over-broad workflow permission. The only unsafe fixture declares contents: read (tests/fixtures/workflow-security/unsafe.yml.txt lines 4-5), and its findings are only artipacked, template-injection and unpinned-uses. The scoped-permission part rests on configuration review (supply-chain.yml lines 19-20; docs/catalog-provenance.md lines 20-24) and a clean zizmor pass.
- No candidate enforces pins beyond Action `uses:` references. Binary pins rely on inline sha256sum steps (supply-chain.yml lines 66-91). The native-foundation-e2e package set has no lock file; its pins are inline (docs/github-automation.md lines 326-329).
- Hosted-check attribution rests on the ruleset's check_source_app_id 15368 (automation.json lines 17-22), which no candidate owns. The attestation evidence covers the published catalog archive at d0fe136 only, and newer catalogs are not claimed to have been published (automation.json line 221).
- No retained hosted run IDs show supply-chain.yml sbom-vuln or a tag-triggered SBOM attestation succeeding.
- The committed .github/main-ruleset.json is recorded as reviewed but not applied. The applied ruleset still requires only validate and token-report (docs/github-automation.md lines 296-302).
- Weekly Dependabot timing, a nonempty minor/patch group and superseded-PR cancellation are unverified (automation.json lines 264-270).
- Syft coverage is installed Python metadata only. The 36/36 SDK receipt covers one prefix (receipt.json line 429), no vulnerability scanner (line 432), and no vendored native libraries (line 434). The 21-package runtime scan has no dist-info cross-check (scan receipt lines 172-177).
- The Grype vulnerability DB is not pinned. `grype db update` fetches the latest, and only its build time is recorded (scan receipt lines 56-70).
- Correction to the packet: Trivy (c2) is marked adopted, but its only evidence records a deferred, research-only decision. Grype (c8) is marked not adopted, but it is pinned and runs in supply-chain.yml.
- The sources conflict on gitleaks' failure policy: automation.json ('no fail threshold decided yet') vs docs/github-automation.md lines 296-298 ('fails on any detection').
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-ci-supply-chain-20260922; codex: -)

#### Code navigation (code-navigation)

- serena @ 2.0.0.dev0 @ c6fbd1c5932df2494ffa0020af5a9fbe80b82143 — This is my own source review, revised after the refuter findings. No TypeSafe inference results were supplied, so no provider judgment is retained. The requirement (packet line 205) is to retrieve exact source and references for changes, using a conceptual or structural index only when it answers the actual question.

(1) c5 Serena stays the default. evidence/receipts/foundation-native-20260920.json line 80 records that "Eight symbol/source/reference checks passed across fresh codex and claude-code MCP server contexts; exact Python parse_codex and CJS collect[0] source matched". Pin c6fbd1c5 is at line 72. The older receipt, evidence/receipts/native-context-memory.json lines 42-54, shows only that find_referencing_symbols and find_symbol completed with error null. It records no result content, and line 15 says it used an older CLI. catalogs/foundation/decisions.json lines 565-604 (language-symbols) marks Serena as selection "default", with the use stage accepted_within_scope.

(2) c2 jCodeMunch covers scoped indexed retrieval. evidence/receipts/native-jcodemunch-20260920.json lines 40-50 record exact o200k_base token counts:
- whole file: 5476
- focused function read: 601
- retrieval sequence: 861
- index plus retrieval: 1332
The retrieval sequence alone is 84.28% smaller than the whole file. Including indexing, it still beats the whole file, but it costs 731 tokens more than a known focused read. So the index wins only when it replaces broad reads, which matches the conditional requirement and the activation rule in decisions.json line 666.

(3) c3 codebase-memory-mcp takes the structural slot instead of ast-grep. It passed native static-graph runs on real repository source in two clients. In the Claude CLI 2.1.278 run (evidence/receipts/native-cli-gaps.json lines 49-110), search_graph returned collect in tools/ecosystem/linux-usage-report.cjs with an exact span, source_lines [91,127], lookup_matches 1 and not truncated. An outbound trace_path returned 4 direct callees. In Codex Desktop (evidence/receipts/desktop-cli-workflows.json lines 11-40), the search and trace both exited 0 with 4 callees. This gives both an exact source span and structural relations. ast-grep's retained evidence is only a match count on a fixture.

All results come from native execution on bounded single tasks. None is a cross-language or cross-repository benchmark, and the three tools were not compared against each other.
- jcodemunch-mcp @ 1.108.319 — This is my own source review, revised after the refuter findings. No TypeSafe inference results were supplied, so no provider judgment is retained. The requirement (packet line 205) is to retrieve exact source and references for changes, using a conceptual or structural index only when it answers the actual question.

(1) c5 Serena stays the default. evidence/receipts/foundation-native-20260920.json line 80 records that "Eight symbol/source/reference checks passed across fresh codex and claude-code MCP server contexts; exact Python parse_codex and CJS collect[0] source matched". Pin c6fbd1c5 is at line 72. The older receipt, evidence/receipts/native-context-memory.json lines 42-54, shows only that find_referencing_symbols and find_symbol completed with error null. It records no result content, and line 15 says it used an older CLI. catalogs/foundation/decisions.json lines 565-604 (language-symbols) marks Serena as selection "default", with the use stage accepted_within_scope.

(2) c2 jCodeMunch covers scoped indexed retrieval. evidence/receipts/native-jcodemunch-20260920.json lines 40-50 record exact o200k_base token counts:
- whole file: 5476
- focused function read: 601
- retrieval sequence: 861
- index plus retrieval: 1332
The retrieval sequence alone is 84.28% smaller than the whole file. Including indexing, it still beats the whole file, but it costs 731 tokens more than a known focused read. So the index wins only when it replaces broad reads, which matches the conditional requirement and the activation rule in decisions.json line 666.

(3) c3 codebase-memory-mcp takes the structural slot instead of ast-grep. It passed native static-graph runs on real repository source in two clients. In the Claude CLI 2.1.278 run (evidence/receipts/native-cli-gaps.json lines 49-110), search_graph returned collect in tools/ecosystem/linux-usage-report.cjs with an exact span, source_lines [91,127], lookup_matches 1 and not truncated. An outbound trace_path returned 4 direct callees. In Codex Desktop (evidence/receipts/desktop-cli-workflows.json lines 11-40), the search and trace both exited 0 with 4 callees. This gives both an exact source span and structural relations. ast-grep's retained evidence is only a match count on a fixture.

All results come from native execution on bounded single tasks. None is a cross-language or cross-repository benchmark, and the three tools were not compared against each other.
- codebase-memory-mcp @ 0.11.0 — This is my own source review, revised after the refuter findings. No TypeSafe inference results were supplied, so no provider judgment is retained. The requirement (packet line 205) is to retrieve exact source and references for changes, using a conceptual or structural index only when it answers the actual question.

(1) c5 Serena stays the default. evidence/receipts/foundation-native-20260920.json line 80 records that "Eight symbol/source/reference checks passed across fresh codex and claude-code MCP server contexts; exact Python parse_codex and CJS collect[0] source matched". Pin c6fbd1c5 is at line 72. The older receipt, evidence/receipts/native-context-memory.json lines 42-54, shows only that find_referencing_symbols and find_symbol completed with error null. It records no result content, and line 15 says it used an older CLI. catalogs/foundation/decisions.json lines 565-604 (language-symbols) marks Serena as selection "default", with the use stage accepted_within_scope.

(2) c2 jCodeMunch covers scoped indexed retrieval. evidence/receipts/native-jcodemunch-20260920.json lines 40-50 record exact o200k_base token counts:
- whole file: 5476
- focused function read: 601
- retrieval sequence: 861
- index plus retrieval: 1332
The retrieval sequence alone is 84.28% smaller than the whole file. Including indexing, it still beats the whole file, but it costs 731 tokens more than a known focused read. So the index wins only when it replaces broad reads, which matches the conditional requirement and the activation rule in decisions.json line 666.

(3) c3 codebase-memory-mcp takes the structural slot instead of ast-grep. It passed native static-graph runs on real repository source in two clients. In the Claude CLI 2.1.278 run (evidence/receipts/native-cli-gaps.json lines 49-110), search_graph returned collect in tools/ecosystem/linux-usage-report.cjs with an exact span, source_lines [91,127], lookup_matches 1 and not truncated. An outbound trace_path returned 4 direct callees. In Codex Desktop (evidence/receipts/desktop-cli-workflows.json lines 11-40), the search and trace both exited 0 with 4 callees. This gives both an exact source span and structural relations. ast-grep's retained evidence is only a match count on a fixture.

All results come from native execution on bounded single tasks. None is a cross-language or cross-repository benchmark, and the three tools were not compared against each other.

Alternatives:
- ast-grep (conditional) — ast-grep shares the conditional structural-code-lane decision with c3 (catalogs/foundation/decisions.json lines 606-654, selection conditional at line 613). Its only execution evidence is one JavaScript source fixture. The initial run on evidence/artifacts/usage-report.source.txt exited 1 with no match, because explicit .txt selection skipped language discovery (evidence/receipts/portable-cli-artifacts.json lines 53-68 and 125). A corrected --stdin run found 8 functions (lines 110-126). The receipt records a match count but no source spans or references. It also labels the run 'not an LLM invocation or general quality benchmark' (line 15). For the requirement's reference and structural parts, that is weaker than c3's recorded source span and call edges on real repository source. ast-grep needs no index, which may make it the cheaper exact syntactic search. That trade-off is unmeasured, so ast-grep stays a conditional lane and was not rejected on a measured result.
- CodeGraph (unqualified) — Not adopted in the packet (line 123). The only evidence is a README/license review at commit ba3c21e50d9129d2f5f3843ec3728868ae6d47a1. Its decision is 'alternative', and its speed and completeness claims need a relevant language/workload comparison. The audit records that no installation or native acceptance was performed, and its evidence_refs list is empty (catalogs/us-equities/star-audit.json lines 9884-9906). It is untested, not failed.

Overturn when: Overturn this verdict if a sealed task set in the target languages shows a different result. The seed is fixtures/before.py and fixtures/after.py (the Serena find_symbol fixture named in catalogs/us-equities/foundation-memory.json line 238), extended with real changed-source identifiers. Each arm must answer the same questions: symbol body, inbound references and outbound callers/callees, verified against the original source. The verdict changes if:
- ast-grep or CodeGraph returns more correct source or references than c3 or Serena at a lower combined cost of indexing, retrieval and maintenance;
- ast-grep answers the structural questions at c3's correctness without an index;
- c3's graph fails on target-language or changed-source coverage;
- jCodeMunch's index-plus-retrieval sequence stops beating a whole-file read, or its maintenance cost after symbol updates or deletions exceeds focused reads.

Open gaps:
- No cross-language or cross-repository benchmark establishes a best code retriever overall (packet limitations, lines 201-204).
- No executed comparison ranks c3 against c1. Replacing ast-grep with c3 in the winner set is a judgment about the depth of the recorded evidence, not a measured result.
- The overlap between c3 and Serena is unestablished. c3 recorded only outbound callees (native-cli-gaps.json line 82). Serena's reference outputs are summarized as passing (foundation-native-20260920.json line 80) with no content recorded. The earlier claim that they overlap is withdrawn.
- Serena's detailed per-check results sit in private evidence, recorded only by sha256 (foundation-native-20260920.json lines 420-423). Only the Python and TypeScript/CJS language servers were repaired and checked, and a passing configured server does not establish every language (decisions.json line 585).
- c3's static graph does not establish runtime call behavior. Its Claude run used an existing selected index, not a fresh index (native-cli-gaps.json line 110). The native Codex CLI attempt was quota-blocked before any tool use (lines 27-47).
- jCodeMunch was measured on a single bounded task. With indexing, it costs 1332 tokens, 731 more than a focused read. Symbol updates, deletions and recovery are not established (decisions.json lines 685 and 711-715).
- docs/token-native-saturation.md line 84 lists persistence for jCodeMunch, but the scoped-symbol-index decision's stage_refs list only use, install, restart and cleanup as accepted (decisions.json lines 690-715). Persistence is therefore not treated as established.
- The ast-grep evidence is one JavaScript fixture and records a match count only.
- CodeGraph has no installation or native acceptance.
- Serena's installed 2.0.0.dev0 snapshot differs from the latest stable v1.7.0 (packet lines 161-168).
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-code-navigation-20260922; codex: -)

#### Documents and ingestion (document-retrieval)

- qmd @ 2.8.3 — The requirement has two parts: controlled ingestion, and retrieving the original body before relying on a result. Two candidates cover them with native execution; no other candidate does.

c5 (QMD BM25) handles Markdown search and get. In catalogs/foundation/decisions.json (lines 721-765, scoped-document-bm25, selection "default"), native scoped QMD search/get passed. On the fixed twelve-query benchmark, the intended source was in the top three for 8 of 12 queries. The catalog repair returned exact source bodies. The later diagnostic, evidence/artifacts/foundation-rd-20260921/qmd-comparison.json, is one ordered native CLI run with exit_code 0. It reported:
- bm25: recall_at_3 0.5, mrr 0.508, average_latency_ms 5
- hybrid: recall_at_3 0.5, mrr 0.503, average_latency_ms 10328
- full: recall_at_5 0.5, average_latency_ms 75920
- vector: recall_at_3 0.25
So hybrid, full and vector modes gave no recall gain at much higher latency. docs/foundation-rd-readiness.md (line 29, lines 64-69) retains BM25 on this basis.

c2 (Poppler 26.09.0) handles controlled PDF ingestion. blueprints/convergence-practice/document-ingestion/README.md (lines 3-13, 34-47) records native pdftotext -bbox-layout runs on a frozen three-page corpus. They extracted exact text on every page and 24 table cells, and passed 8 positive and 4 absent queries, with source/page/coordinate citations. Input was fail-closed and results were capped at 3 records / 240 characters. blueprints/convergence-practice/wsl-document-ingestion/README.md (lines 3-9) shows a fresh native WSL run whose output is byte-identical to the Mac output.

Both winners are conditional on their scope: a small fixture corpus and one ordered diagnostic run. Neither is a universal ranking.
- poppler @ 26.09.0 — The requirement has two parts: controlled ingestion, and retrieving the original body before relying on a result. Two candidates cover them with native execution; no other candidate does.

c5 (QMD BM25) handles Markdown search and get. In catalogs/foundation/decisions.json (lines 721-765, scoped-document-bm25, selection "default"), native scoped QMD search/get passed. On the fixed twelve-query benchmark, the intended source was in the top three for 8 of 12 queries. The catalog repair returned exact source bodies. The later diagnostic, evidence/artifacts/foundation-rd-20260921/qmd-comparison.json, is one ordered native CLI run with exit_code 0. It reported:
- bm25: recall_at_3 0.5, mrr 0.508, average_latency_ms 5
- hybrid: recall_at_3 0.5, mrr 0.503, average_latency_ms 10328
- full: recall_at_5 0.5, average_latency_ms 75920
- vector: recall_at_3 0.25
So hybrid, full and vector modes gave no recall gain at much higher latency. docs/foundation-rd-readiness.md (line 29, lines 64-69) retains BM25 on this basis.

c2 (Poppler 26.09.0) handles controlled PDF ingestion. blueprints/convergence-practice/document-ingestion/README.md (lines 3-13, 34-47) records native pdftotext -bbox-layout runs on a frozen three-page corpus. They extracted exact text on every page and 24 table cells, and passed 8 positive and 4 absent queries, with source/page/coordinate citations. Input was fail-closed and results were capped at 3 records / 240 characters. blueprints/convergence-practice/wsl-document-ingestion/README.md (lines 3-9) shows a fresh native WSL run whose output is byte-identical to the Mac output.

Both winners are conditional on their scope: a small fixture corpus and one ordered diagnostic run. Neither is a universal ranking.

Alternatives:
- MarkItDown (conditional) — The only native evidence is one HTML fixture conversion. evidence/receipts/portable-cli-artifacts.json has argv 'markitdown fixtures/greeting.html' and 'markitdown_contains_heading': true. catalogs/foundation/decisions.json (lines 788-790) says base HTML acceptance does not imply the optional PDF/Office extras. blueprints/convergence-practice/document-ingestion/README.md (lines 15-17) keeps MarkItDown 0.1.7 only as a candidate for specific unmet needs. No retrieval, provenance or page-boundary check was run. Upstream metadata in the packet says the 0.1.7 pin is behind v0.1.8; I did not verify that. Keep it as a conditional HTML converter only.
- Context Hub (conditional) — This candidate covers a different scope: curated external developer documentation (catalogs/foundation/decisions.json lines 817-856, curated-developer-docs, conditional). It is not controlled ingestion of local source documents. docs/token-native-saturation.md (line 16) records that its retained comparison grew by 85 tokens. The packet marks it unmaintained_signal: last push 2026-05-31, latest release v0.1.4. Use it only for a named documentation gap, and inspect the primary source it returns.
- Docling (unqualified) — The only evidence is pinned upstream source review. catalogs/us-equities/foundation-memory.json (foundation-docling, lines 1134-1170) says 'commands are prospective and were not executed' and that table/unit extraction quality is unmeasured. Model weights carry separate licenses. The document-ingestion README (lines 118-123) says to adopt it only if it passes a frozen layout/OCR corpus with provenance and answer checks. That test has not been run, so it has not failed either.
- LlamaIndex (unqualified) — The only evidence is source review for the separate rag-pipeline layer. catalogs/us-equities/foundation-memory.json (foundation-llama_index, lines 983-1018) says commands are prospective and not executed. It notes the README now prioritizes LlamaParse, and that managed parsing may add cost or send data externally. No ingestion or retrieval fixture was run.

Overturn when: Two results would change this verdict, either way:
1. A sealed, representative rerun of the QMD benchmark on blueprints/us-equities/retrieval-evaluation/fixture.json, or a successor sealed corpus, with repeated warm/cold runs. It must show a non-BM25 mode, or another retriever, with useful recall@3/MRR gains at acceptable end-to-end latency. It must also include absent queries.
2. A frozen, license-permitted corpus of multi-column, table-heavy and scanned documents, run under the blueprints/convergence-practice/document-ingestion protocol. Check with python3 blueprints/convergence-practice/document-ingestion/audit.py and python3 -m unittest discover -s tests -p test_document_ingestion.py -v. It would overturn the verdict if Poppler fails the provenance/answer oracle while Docling or MarkItDown passes it at justified runtime cost.

Open gaps:
- The evidence covers a small designed, born-digital Latin-text PDF only. It does not cover OCR, scanned pages, multi-column filings, difficult tables or Office documents (document-ingestion README lines 13-14, 112-123).
- The QMD comparison is one ordered run on an index without a full-corpus seal (full_corpus_seal false), with a 12-query gold set. It establishes no general retrieval ranking and no token saving (qmd-comparison.json limits).
- Correction: two BM25 measurements should not be conflated. The decision's '8 of 12 in top three' comes from the earlier September 19 benchmark. The September 21 expanded-index diagnostic reports bm25 recall_at_3 0.5, which is 6 of 12. The index changed between them (qmd-comparison.json limits: 'expanded index differs from September19 baseline').
- No step joins the two winners end to end: Poppler extraction feeding a QMD index, then retrieval of the original body. They are qualified separately.
- MarkItDown's PDF/Office extras, and Docling's and LlamaIndex's ingestion paths, have not been executed. Untested is not failed.
- Whether Context Hub is current and maintained, and its value on documentation questions, is unestablished beyond the retained operation; that comparison grew by 85 tokens.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-document-retrieval-20260922; codex: -)

#### Durable memory (durable-memory)

- ai-memory @ 2.3.2 — ai-memory (c5) is the only candidate whose retained evidence shows native execution against this requirement. Retained observations from my source review: (1) docs/native-memory-rag-lifecycle.md 'Actual native use' (lines 29-41). A fresh native Claude task called memory_read_page and codebase_search and returned the current memory decision. Its exact 764-byte final reply was read back from the stored Stop observation, all nine lifecycle observations were present, and consolidation generation 9 completed on attempt 1. A running Codex task also used native ai-memory retrieval. This covers both clients. (2) docs/memory-landscape-maintenance.md 'Commands and observed results' (lines 129-139). The upstream installers were applied for both Claude and Codex hooks. `ai-memory doctor` reported captured sessions for both clients with `uncaptured: []`. There were two real scheduler admission ticks, both failing admission with no model call. Unchanged upstream tests passed: 4 auto_improve_schedule tests and 18 assistant_capture tests. The retained failures are an initial filter that selected zero tests and one rejected auto-improve proposal. (3) The packet's c5 decisions list same-host restore and synthetic off-host restore as accepted_within_scope, with 10 ai-memory and 4 Qdrant unchanged upstream tests. I did not open the restore receipts themselves, so that part is retained provider judgment. (4) blueprints/blind-catalog-convergence/memory-experiment.json and blueprints/memory-lifecycle-probe/README.md record a local synthetic lexical lifecycle. After an explicit-none embedding correction, ai-memory 2.3.2 passed write, overwrite, delete and restart. The first attempt failed because it started an unwanted model download. The decision was 'retain', scoped to three synthetic notes. Every other adopted candidate has pinned source review only (catalogs/landscape/candidate-quality-review.json: 'no new install, upstream test execution, native model operation, matched answer-quality comparison or recovery acceptance'), except Basic Memory's synthetic probe. Scope limit: this makes ai-memory the best-supported operational fit, not a demonstrated recall, learning or cost winner (candidate-quality-review.json lines 377, 382). The native evidence applies to installed 2.3.2 (source 353841d), not to the reviewed upstream head 5157c6b or to v2.4.0.

Alternatives:
- Basic Memory (conditional) — It is the only challenger with executed evidence, and that evidence is narrow. Pinned 0.23.2 passed the same three-note synthetic lexical write, overwrite and delete lifecycle, plus a text-only reindex (blueprints/memory-lifecycle-probe/README.md table, lines 13-19). That probe tested no hooks, no native Codex/Claude client integration, no cross-project isolation and no semantic recall. Its reindex 'is not a demonstration of restoring a lost database', and the recovery checks were unequal. AGPL-3.0 deployment fit is unreviewed (candidate-quality-review.json lines 466, 437). Its Claude session briefings and capture are source claims only.
- Mem0 (conditional) — The evidence is pinned source review only: no install, no upstream test run, no native operation, no matched answer-quality comparison and no recovery acceptance (candidate-quality-review.json line 564). It is documented as application user/session/agent memory. Its published evaluations do not transfer to this project's continuity task. It would be a second authoritative store without a demonstrated gap (docs/memory-landscape-maintenance.md line 42).
- Letta Code (unqualified) — It is a stateful runtime-and-memory harness, not a drop-in store. Adopting it would replace native Codex/Claude, which is outside this layer (docs/memory-landscape-maintenance.md line 45). Its evidence is pinned source review only (candidate-quality-review.json lines 739, 744).
- OpenViking (conditional) — It is a hierarchical context-filesystem unification candidate with pinned source review only. Benchmark transfer, migration and AGPL-3.0 deployment fit remain open (candidate-quality-review.json lines 909, 938). No executed capture, deletion or restore evidence was found.
- Graphiti (conditional) — It is a complementary temporal entity graph for entity/time queries, not a Codex/Claude project-memory lifecycle (docs/memory-landscape-maintenance.md line 41). It has pinned source review only. Extraction provenance, isolation and restore are unqualified (candidate-quality-review.json line 619).
- Cognee (conditional) — It is a graph/context research-corpus candidate. Its default LLM recipe uses OpenAI, and no local profile was qualified. Evidence is pinned source review only (candidate-quality-review.json lines 851, 856).
- Supermemory (conditional) — It is an application memory/profile/search API with pinned source review only. The cloud-only exclusion is stale. However, provider calls, export/restore, isolation and representative retrieval remain unqualified (candidate-quality-review.json lines 967, 972). Its published savings belong to its own benchmark (docs/memory-landscape-maintenance.md line 46).
- Hindsight (unqualified) — Not adopted. It is the priority challenger for retain/recall/reflect, with documented native Codex/Claude subscription providers. Its evidence is source review only, and published benchmarks are not a matched test of this project (candidate-quality-review.json line 497; docs/candidate-quality-review-20260921.md line 65). It is named in the next decision-changing test in memory-experiment.json, which has not been run.
- Claude-mem (overlap) — Not adopted. It is an overlapping capture/compression store with source review only. Running it beside ai-memory would duplicate automatic capture, and its scoped-capture fidelity and provider behavior are uncompared (candidate-quality-review.json line 679; docs/memory-landscape-maintenance.md line 44).

Overturn when: The comparison named in blueprints/blind-catalog-convergence/memory-experiment.json (next_decision_changing_test) is executed. It uses a preregistered representative memory corpus to compare Hindsight and Basic Memory against ai-memory, with a shared downstream model and context. It checks grounded answers, abstention, supersession, cross-project isolation and an actual clean-target restore. The verdict changes if it shows better source-grounded recall and usefulness with acceptable complete provider use, latency and capture/deletion/restore behavior. The existing blueprints/memory-lifecycle-probe (corpus.json and verify.py, re-checkable with `python3 blueprints/memory-lifecycle-probe/verify.py`) is only a three-note lexical baseline. It cannot overturn the verdict on its own.

Open gaps:
- No matched semantic recall or usefulness benchmark has been run for any candidate, ai-memory included. The winner is the best-supported operational fit, not a quality winner.
- Learned-write quality is unestablished. Scheduler admission failed both real ticks, and the one model review rejected its proposal for insufficient evidence.
- Assistant capture keeps sanitized excerpts capped at 2,000 bytes, not full transcripts. Claude prompt capture remains opted out.
- Exact session and lifetime token savings from memory are unknown.
- Installed ai-memory 2.3.2 (353841d) lags upstream v2.4.0 and the reviewed head 5157c6b. The native evidence does not qualify the newer revision.
- ai-memory's native restore and reindex were not run in the synthetic probe because of its process guard. Restore evidence comes from the separately recorded same-host and synthetic off-host acceptances. Lost-key, lost-account, physical-host and whole-stack recovery remain unqualified.
- Deletion evidence covers current search results only, not erasure from history, logs or backups.
- The scheduler covers every database project, while the current deployment has one adopted scope. Multi-project scope behavior is unqualified.
- No new-host (clean WSL or macOS) activation evidence exists for this layer.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-durable-memory-20260922; codex: -)

#### Git practice and GitHub automation (git-github-automation)

- worktrunk @ 0.79.0 — The requirement has three parts: owned worktrees, GitHub review/PR automation and structural diffs for changed code. Each winner covers a different part, but the evidence strength is uneven. I only reviewed sources; nothing here was executed now.

c4 (worktrunk) is the only winner with a "default" selection. catalogs/foundation/decisions.json lines 477-521 (owned-worktrees, selection "default" at line 487) record it as accepted_within_scope. manifests/evidence.json lines 582-590 (worktrunk-list, kind native_cli_e2e) and lines 1880-1893 (velanext-native-quality-tools-20260920, native_cli_e2e) record the earlier result: "Worktrunk0.78.0 created/listed/removed owned worktrees while refusing dirty removal without loss". That run used isolated synthetic Linux/WSL fixtures. The runner, blueprints/convergence-practice/wsl-native-tools/run.py lines 195-231, creates two worktrees with --no-hooks, removes the clean one, requires the dirty removal to fail (expected=1) with bytes preserved, and then checks that git keeps only the primary worktree.

c1 (difftastic) is selection "conditional" (decisions.json line 1360, deterministic-quality-tools lines 1351-1411), with a use stage accepted within the scope "native shell/structural comparison". Its backing evidence is portable-cli-artifacts (manifests/evidence.json lines 640-641, kind native_cli_e2e). That run was fixture-specific on fixtures/before.py and fixtures/after.py, which the receipt names at lines 36-37. It records normal difft exit 0 and --exit-code exit 1.

c2 (gh CLI) has no decision record and no pin (packet lines 54-68). Its evidence is dated local observations in docs/github-automation.md: native `gh attestation verify` exit 0 on 2026-09-20 (lines 128-135), a `gh api` GET of branch rules that verified settings only (lines 180-183), and documented ruleset maintenance commands (lines 187-200). The layer routing at decisions.json line 2960 assigns worktree lifecycle to worktrunk, GitHub operations to gh and structural diffs to difftastic. That layer record is selection "conditional" (line 2958) and source_review only, and it says no new execution was run.

Correction to my earlier proposal: no winner has retained execution evidence for PR creation, review or merge automation. gh's recorded runs cover supply-chain integrity and reading settings.
- difftastic @ 0.71.0 — The requirement has three parts: owned worktrees, GitHub review/PR automation and structural diffs for changed code. Each winner covers a different part, but the evidence strength is uneven. I only reviewed sources; nothing here was executed now.

c4 (worktrunk) is the only winner with a "default" selection. catalogs/foundation/decisions.json lines 477-521 (owned-worktrees, selection "default" at line 487) record it as accepted_within_scope. manifests/evidence.json lines 582-590 (worktrunk-list, kind native_cli_e2e) and lines 1880-1893 (velanext-native-quality-tools-20260920, native_cli_e2e) record the earlier result: "Worktrunk0.78.0 created/listed/removed owned worktrees while refusing dirty removal without loss". That run used isolated synthetic Linux/WSL fixtures. The runner, blueprints/convergence-practice/wsl-native-tools/run.py lines 195-231, creates two worktrees with --no-hooks, removes the clean one, requires the dirty removal to fail (expected=1) with bytes preserved, and then checks that git keeps only the primary worktree.

c1 (difftastic) is selection "conditional" (decisions.json line 1360, deterministic-quality-tools lines 1351-1411), with a use stage accepted within the scope "native shell/structural comparison". Its backing evidence is portable-cli-artifacts (manifests/evidence.json lines 640-641, kind native_cli_e2e). That run was fixture-specific on fixtures/before.py and fixtures/after.py, which the receipt names at lines 36-37. It records normal difft exit 0 and --exit-code exit 1.

c2 (gh CLI) has no decision record and no pin (packet lines 54-68). Its evidence is dated local observations in docs/github-automation.md: native `gh attestation verify` exit 0 on 2026-09-20 (lines 128-135), a `gh api` GET of branch rules that verified settings only (lines 180-183), and documented ruleset maintenance commands (lines 187-200). The layer routing at decisions.json line 2960 assigns worktree lifecycle to worktrunk, GitHub operations to gh and structural diffs to difftastic. That layer record is selection "conditional" (line 2958) and source_review only, and it says no new execution was run.

Correction to my earlier proposal: no winner has retained execution evidence for PR creation, review or merge automation. gh's recorded runs cover supply-chain integrity and reading settings.
- candidate:cli-cli @ unpinned — The requirement has three parts: owned worktrees, GitHub review/PR automation and structural diffs for changed code. Each winner covers a different part, but the evidence strength is uneven. I only reviewed sources; nothing here was executed now.

c4 (worktrunk) is the only winner with a "default" selection. catalogs/foundation/decisions.json lines 477-521 (owned-worktrees, selection "default" at line 487) record it as accepted_within_scope. manifests/evidence.json lines 582-590 (worktrunk-list, kind native_cli_e2e) and lines 1880-1893 (velanext-native-quality-tools-20260920, native_cli_e2e) record the earlier result: "Worktrunk0.78.0 created/listed/removed owned worktrees while refusing dirty removal without loss". That run used isolated synthetic Linux/WSL fixtures. The runner, blueprints/convergence-practice/wsl-native-tools/run.py lines 195-231, creates two worktrees with --no-hooks, removes the clean one, requires the dirty removal to fail (expected=1) with bytes preserved, and then checks that git keeps only the primary worktree.

c1 (difftastic) is selection "conditional" (decisions.json line 1360, deterministic-quality-tools lines 1351-1411), with a use stage accepted within the scope "native shell/structural comparison". Its backing evidence is portable-cli-artifacts (manifests/evidence.json lines 640-641, kind native_cli_e2e). That run was fixture-specific on fixtures/before.py and fixtures/after.py, which the receipt names at lines 36-37. It records normal difft exit 0 and --exit-code exit 1.

c2 (gh CLI) has no decision record and no pin (packet lines 54-68). Its evidence is dated local observations in docs/github-automation.md: native `gh attestation verify` exit 0 on 2026-09-20 (lines 128-135), a `gh api` GET of branch rules that verified settings only (lines 180-183), and documented ruleset maintenance commands (lines 187-200). The layer routing at decisions.json line 2960 assigns worktree lifecycle to worktrunk, GitHub operations to gh and structural diffs to difftastic. That layer record is selection "conditional" (line 2958) and source_review only, and it says no new execution was run.

Correction to my earlier proposal: no winner has retained execution evidence for PR creation, review or merge automation. gh's recorded runs cover supply-chain integrity and reading settings.

Alternatives:
- Codex for Claude review bridge (conditional) — Its only use stage is partial_acceptance. In catalogs/foundation/decisions.json, lines 386-387 give selection "optional" and review_status partial_acceptance, and lines 397 and 405 give the scope "One read-only native bridge backend task passed" and the next gap. manifests/evidence.json line 1464 says the bridge trial "used one backend task without an outer Claude interaction or matched baseline". The packet's own evidence_kind for c3 is "mixed". It is the only candidate with a review-oriented run, but that run is narrower than plugin integration and has no PR, ruleset or GitHub-operation evidence. Line 2960 limits it to "a concrete cross-client review task". Keep it conditional until an outer plugin invocation is qualified against a baseline.

Overturn when: Owned worktrees: rerun blueprints/convergence-practice/wsl-native-tools/run.py, with tests/test_wsl_native_tools.py as its offline guard. If the current worktrunk pin 0.79.0 fails its create/list/dirty-refusal/cleanup assertions, the verdict changes. It also changes if another worktree manager or plain `git worktree` passes the same assertions and adds crash cleanup without losing unrelated state. Structural diffs: a challenger diff tool beating difftastic on fixtures/before.py and fixtures/after.py (plus a larger changed-code set) overturns c1. Review/PR automation: no fixture exists. The verdict for that part stays open until someone creates and runs a matched PR-review comparison: gh direct, a qualified outer codex-for-claude invocation and a gh-aw read-only pilot, on the same change set. The workflow-security tests and `python3 scripts/validate.py` are regression gates only. They do not decide any overturn.

Open gaps:
- No winner has retained execution evidence for GitHub review/PR automation (PR creation, review or merge gating). gh's recorded runs are release download/attestation verify (docs/github-automation.md lines 100-106, 128-135) and a settings GET (lines 180-183). Only c3, a non-winner, has a review-oriented run, and it is partial.
- gh CLI has no decision record, lifecycle stage, pin or manifests/stack.json entry (packet lines 54-68; decisions.json lines 2971-2982).
- The worktrunk acceptance was observed on 0.78.0 in disposable synthetic repositories with hooks disabled (evidence.json lines 1886, 1888). The current pin 0.79.0 has not been re-qualified here.
- worktrunk crash cleanup without deleting unrelated or dirty state is not established (owned-worktrees next_gap).
- difftastic is selection conditional. Its acceptance is a single fixture pair (fixtures/before.py and after.py) and is recorded as 'not an LLM invocation or general quality benchmark' (evidence.json line 652).
- The layer decision git-github-automation-practice is selection conditional and source_review, and records no new execution for this freeze.
- The committed main-ruleset.json is documented as not yet applied (docs/github-automation.md lines 173-178, 357-360). The ruleset check verified settings, not an attempted blocked merge.
- There is no matched comparison between any winner and any challenger, and no review/PR comparison fixture exists. Stars and release recency are not quality evidence.
- codex lane absent for this layer
- unindexed alternative GitHub Agentic Workflows (gh-aw) https://github.com/github/gh-aw
- 2 lane citation(s) name no repository evidence file (an unresolved path or a generated index); the full citations are kept in the sealed lane return

Lanes: codex_absent (claude: foundation-git-github-automation-20260922; codex: -)

#### Application and service hosting (hosting-services)

- fastapi @ 0.141.1 — FastAPI 0.141.1 (c1), PostgreSQL 18.6 (c6) and Next.js 16.3.5 (c2) are the only adopted candidates with retained execution receipts for the requirement "run the selected local typed application and supporting services reproducibly". The capability decision is at catalogs/foundation/decisions.json:1636-1668 (id local-typed-application, layer_ids include hosting-services, selection "conditional", review_status "accepted_within_scope", evidence_ids native-application-delivery-20260920, mac-native-application-migration-20260920 and wsl-application-20260920). What was actually observed is local execution of the project's own acceptance suite on named fixtures. On the Mac, blueprints/convergence-practice/application-delivery/receipt.json records status "passed" (line 13), API tests passed 12 and failed 0 (lines 35-36), a passing production_build (line 57) and one browser workflow that passed with 0 failures (lines 59-60). On WSL, blueprints/convergence-practice/wsl-application/receipt.json records status "passed_with_explicit_platform_adaptations" (line 4) and passed 12, failed 0 (lines 108-109). In blueprints/convergence-practice/application-delivery/README.md lines 111-118, the browser-created record survived a native PostgreSQL stop/start and an API/Next restart byte-for-byte. Lines 145-152 record a separate empty-database migration reversal. Reproducibility comes from locked setup with make targets and pins (README lines 13-18 and 45-59). Account, state and deployment scope stay explicit: loopback only, local trust authentication for a synthetic fixture, and state kept in an ignored .runtime directory (README lines 41-43 and 127-133). I classify this as local integration: the project's own tests on a synthetic fixture. The packet labels it native_execution. It is neither upstream E2E nor production hosting. React (c11) was also exercised, but it is carried as a Next.js dependency rather than chosen as a separate component, so it is recorded as overlap to stay within the three-winner limit. Every container, managed-compute and gateway candidate has only source review, with native_acceptance "not_established" (catalogs/landscape/hosting-practice.json lines 18, 29, 40 and 52).
- postgresql @ 18.6 — FastAPI 0.141.1 (c1), PostgreSQL 18.6 (c6) and Next.js 16.3.5 (c2) are the only adopted candidates with retained execution receipts for the requirement "run the selected local typed application and supporting services reproducibly". The capability decision is at catalogs/foundation/decisions.json:1636-1668 (id local-typed-application, layer_ids include hosting-services, selection "conditional", review_status "accepted_within_scope", evidence_ids native-application-delivery-20260920, mac-native-application-migration-20260920 and wsl-application-20260920). What was actually observed is local execution of the project's own acceptance suite on named fixtures. On the Mac, blueprints/convergence-practice/application-delivery/receipt.json records status "passed" (line 13), API tests passed 12 and failed 0 (lines 35-36), a passing production_build (line 57) and one browser workflow that passed with 0 failures (lines 59-60). On WSL, blueprints/convergence-practice/wsl-application/receipt.json records status "passed_with_explicit_platform_adaptations" (line 4) and passed 12, failed 0 (lines 108-109). In blueprints/convergence-practice/application-delivery/README.md lines 111-118, the browser-created record survived a native PostgreSQL stop/start and an API/Next restart byte-for-byte. Lines 145-152 record a separate empty-database migration reversal. Reproducibility comes from locked setup with make targets and pins (README lines 13-18 and 45-59). Account, state and deployment scope stay explicit: loopback only, local trust authentication for a synthetic fixture, and state kept in an ignored .runtime directory (README lines 41-43 and 127-133). I classify this as local integration: the project's own tests on a synthetic fixture. The packet labels it native_execution. It is neither upstream E2E nor production hosting. React (c11) was also exercised, but it is carried as a Next.js dependency rather than chosen as a separate component, so it is recorded as overlap to stay within the three-winner limit. Every container, managed-compute and gateway candidate has only source review, with native_acceptance "not_established" (catalogs/landscape/hosting-practice.json lines 18, 29, 40 and 52).
- nextjs @ 16.3.5 — FastAPI 0.141.1 (c1), PostgreSQL 18.6 (c6) and Next.js 16.3.5 (c2) are the only adopted candidates with retained execution receipts for the requirement "run the selected local typed application and supporting services reproducibly". The capability decision is at catalogs/foundation/decisions.json:1636-1668 (id local-typed-application, layer_ids include hosting-services, selection "conditional", review_status "accepted_within_scope", evidence_ids native-application-delivery-20260920, mac-native-application-migration-20260920 and wsl-application-20260920). What was actually observed is local execution of the project's own acceptance suite on named fixtures. On the Mac, blueprints/convergence-practice/application-delivery/receipt.json records status "passed" (line 13), API tests passed 12 and failed 0 (lines 35-36), a passing production_build (line 57) and one browser workflow that passed with 0 failures (lines 59-60). On WSL, blueprints/convergence-practice/wsl-application/receipt.json records status "passed_with_explicit_platform_adaptations" (line 4) and passed 12, failed 0 (lines 108-109). In blueprints/convergence-practice/application-delivery/README.md lines 111-118, the browser-created record survived a native PostgreSQL stop/start and an API/Next restart byte-for-byte. Lines 145-152 record a separate empty-database migration reversal. Reproducibility comes from locked setup with make targets and pins (README lines 13-18 and 45-59). Account, state and deployment scope stay explicit: loopback only, local trust authentication for a synthetic fixture, and state kept in an ignored .runtime directory (README lines 41-43 and 127-133). I classify this as local integration: the project's own tests on a synthetic fixture. The packet labels it native_execution. It is neither upstream E2E nor production hosting. React (c11) was also exercised, but it is carried as a Next.js dependency rather than chosen as a separate component, so it is recorded as overlap to stay within the three-winner limit. Every container, managed-compute and gateway candidate has only source review, with native_acceptance "not_established" (catalogs/landscape/hosting-practice.json lines 18, 29, 40 and 52).

Alternatives:
- React (overlap) — React 19.3.0 was exercised in the same receipts as the UI layer under Next.js (application-delivery README lines 4 and 13). It is covered as a Next.js dependency, not a separately chosen hosting component. The packet marks review_status 'not_individually_reviewed', and the three-winner limit applies. It remains required inside the selected stack.
- Docker Compose (conditional) — Source review only (v5.5.1, pin 5f94fb0a), with native_acceptance 'not_established'. The rationale says its lifecycle value 'has not been compared with current service coordination' (catalogs/landscape/hosting-practice.json lines 20-30). The trigger in docs/hosting-container-practice.md line 11 is a selected multi-service OCI package; no such package is selected.
- Docker Engine / Moby (conditional) — Source review only (docker-v29.8.1, pin 464cd50c). The catalog says 'No matched result shows better reproduction or recovery than the accepted native services for this workload' (hosting-practice.json lines 9-19). The application README (lines 120-125) records that an official PostgreSQL container's bind mount stalled before guest boot; the full-stack receipt uses native PostgreSQL instead.
- Podman / Quadlet (conditional) — Source review only (v6.1.2, pin 04f3aa43), with native_acceptance 'not_established'. Image, networking, volume, GPU and Docker-API compatibility are 'workload-specific and unmeasured here' (hosting-practice.json lines 31-42). The trigger is a rootless or systemd-managed container requirement (docs/hosting-container-practice.md line 13), and none is defined.
- Dockerized IB Gateway (conditional) — This is a broker gateway rather than hosting for the typed application. Source review only; 'Image digest, sign-in, restart, API connectivity and broker reconciliation are not qualified' (hosting-practice.json lines 43-53). The Nautilus source uses a mutable 'stable' image tag, and dockerized_gateway in client configs raises ValueError (docs/hosting-container-practice.md lines 31-36). It belongs to the separately qualified IBKR paper path.
- Modal (conditional) — Managed cloud compute that needs a separate account, native login and compute budget. The catalog says 'modal run executes cloud code and may incur charges; not run here' and 'avoid permanent hosting until cost/egress policies are set' (catalogs/us-equities/agents-operations.json lines 606-645). Source review only (modal 1.5.5). It does not fit the local-application requirement, and no GPU or remote workload is defined.
- BentoML (out_of_scope) — A model-serving and packaging alternative (layers 'model-serving' and 'packaging', decision 'alternative'). Its commands are 'Prospective commands; not executed', and the catalog advises 'Prefer direct vLLM for a single supported model endpoint until packaging adds value' (catalogs/us-equities/agents-operations.json lines 564-604). It does not address hosting the typed application or its database.
- Dev Containers CLI (unqualified) — Researched as a dev-environment container boundary (wave 1, v0.89.0, commit 5dc75333). Every native command is marked 'source-confirmed recipe; not executed by this research pass'. The lock omits the base image, Dockerfile steps and application dependencies. The record states 'No container was built or executed' (adoption/research.json lines 324-411). There is no execution evidence for running the application or its services.

Overturn when: Rerun the frozen acceptance for the same locked application and database under one chosen container lane (Docker Engine plus Compose, or Podman/Quadlet), per the comparison_required text in catalogs/landscape/hosting-practice.json. The frozen acceptance is blueprints/convergence-practice/application-delivery/acceptance-plan.json and freeze.json: make verify with 12 API/database tests, the browser create/update workflow, and restart persistence. Measure installation, startup and rebuild time, resources, backup/restore of persistent state, interruption recovery and cleanup. Change the verdict only if that run passes every check the native lane passes and also closes a concrete gap such as isolated backup/restore or packaging. A new failure in the native receipts would also change the verdict. For the portability part, rerun python3 -m unittest discover -s blueprints/convergence-practice/application-delivery -p 'test_portability.py' -v. Separately, a defined production, remote-team or GPU requirement would open a targeted trial for Modal or a hosted provider.

Open gaps:
- The evidence does not accept production authentication or authorization, hosted or cloud deployment, production load, or independent-host database backup/restore (decisions.json lines 1660-1668; application-delivery README lines 135-139).
- Lifecycle stage 'recovery' is 'not_established' for Next.js (decisions.json line 1697). Recovery was not confirmed for the other components in the portion read.
- Migration reversal proves schema reversal, not recovery of user data or a production-safe rollback (application-delivery README lines 150-152).
- No container lane (Docker, Compose, Podman or Dev Containers) has any execution evidence against the application workload. The earlier PostgreSQL container bind-mount stall is recorded, but a named-volume container route was qualified separately and was not substituted.
- Native systemd/Dagu service supervision is the retained 'supporting services' lane in hosting-practice.json but is not a candidate in this packet, so this verdict does not cover it.
- Modal, BentoML and Dockerized IB Gateway have no executed commands. Cloud cost, account, broker sign-in, restart and reconciliation are unqualified.
- The SOTA components listed outside the candidate set (apple-container, mcp-inspector, mcporter, omniroute) were not evaluated here. hosting-practice.json limits say Apple Container evidence is platform-specific and does not qualify Linux engines.
- Evidence covers only the named Mac and WSL fixtures; another PC must produce its own receipts.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-hosting-services-20260922; codex: -)

#### Instructions and skills (instructions-skills)

- candidate:typesafe-ai-skills @ unpinned — The requirement (packet line 298) has two parts: concise canonical rules, and useful upstream procedures, without activating whole catalogs. No candidate supplies the canonical rules. On the evidence, those come from the project's own AGENTS/CLAUDE files; the community-practice-20260920.json layer map (lines 360-374) keeps the current project rules and copies. So the winners are chosen for the procedures part. c8, c4 and c3 are the only adopted candidates with retained evidence that named upstream skill files were installed with matching bytes and observed in a native client, and each is loaded per operation, not as a catalog. All three findings below are my own source review.

(1) c8 TypeSafe has the strongest evidence. catalogs/landscape/native-practice.json lines 32-69 record it pinned at 65a39f39, with its SKILL.md sha256 matching the upstream file. Fresh native source-review invocations completed in Claude Code 2.1.278 and Codex 0.155.1 (docs/native-skill-practice-20260921.md lines 116-126). blueprints/native-skill-practice/typesafe-result.json holds a provider diagnostic in which jev-1.13.0 got 7 of 8 cases right against 3 of 8 for exact-text-baseline-v1 (service_errors 0, promptfoo_exit_code 100).

(2) c4 ECC selects only two skills at 2b6e8397: search-first and iterative-retrieval. Installation with a matching source hash and single native Claude discovery were observed. The full hooks/rules bundle is explicitly not adopted (docs/foundation-closure-20260921.md line 21; catalogs/foundation/community-practice-20260920.json lines 112-113 and 313-341).

(3) c3 OpenAI covers two skills pinned at 49f948fa: gh-fix-ci and security-best-practices. Their SKILL.md hashes matched upstream and Claude init listed them. The unchanged gh-fix-ci inspect_pr_checks.py ran once, exited 0 and printed 'PR #55: no failing checks detected.' (native-practice.json lines 71-162).

This set differs from the project's own layer entry. docs/foundation-closure-20260921.md line 53 lists 'ECC; Anthropic skills; Agent Skills'. I did not select Anthropic skills (c2) because it is not adopted in the packet, and its only retained support is the line 26 claim that 'Existing Claude sync already exposes selected official skills', with no hash or discovery record. I did not select Agent Skills (c9) because it is a format validator that supplies no procedure. TypeSafe and OpenAI both have hash-plus-discovery records.

Evidence level: local integration and native discovery, plus one bounded provider diagnostic. Nothing here measures a task-quality improvement.
- affaan-m/ECC @ dd6ee538aee0f548d4a6b520118f875431fd749e — The requirement (packet line 298) has two parts: concise canonical rules, and useful upstream procedures, without activating whole catalogs. No candidate supplies the canonical rules. On the evidence, those come from the project's own AGENTS/CLAUDE files; the community-practice-20260920.json layer map (lines 360-374) keeps the current project rules and copies. So the winners are chosen for the procedures part. c8, c4 and c3 are the only adopted candidates with retained evidence that named upstream skill files were installed with matching bytes and observed in a native client, and each is loaded per operation, not as a catalog. All three findings below are my own source review.

(1) c8 TypeSafe has the strongest evidence. catalogs/landscape/native-practice.json lines 32-69 record it pinned at 65a39f39, with its SKILL.md sha256 matching the upstream file. Fresh native source-review invocations completed in Claude Code 2.1.278 and Codex 0.155.1 (docs/native-skill-practice-20260921.md lines 116-126). blueprints/native-skill-practice/typesafe-result.json holds a provider diagnostic in which jev-1.13.0 got 7 of 8 cases right against 3 of 8 for exact-text-baseline-v1 (service_errors 0, promptfoo_exit_code 100).

(2) c4 ECC selects only two skills at 2b6e8397: search-first and iterative-retrieval. Installation with a matching source hash and single native Claude discovery were observed. The full hooks/rules bundle is explicitly not adopted (docs/foundation-closure-20260921.md line 21; catalogs/foundation/community-practice-20260920.json lines 112-113 and 313-341).

(3) c3 OpenAI covers two skills pinned at 49f948fa: gh-fix-ci and security-best-practices. Their SKILL.md hashes matched upstream and Claude init listed them. The unchanged gh-fix-ci inspect_pr_checks.py ran once, exited 0 and printed 'PR #55: no failing checks detected.' (native-practice.json lines 71-162).

This set differs from the project's own layer entry. docs/foundation-closure-20260921.md line 53 lists 'ECC; Anthropic skills; Agent Skills'. I did not select Anthropic skills (c2) because it is not adopted in the packet, and its only retained support is the line 26 claim that 'Existing Claude sync already exposes selected official skills', with no hash or discovery record. I did not select Agent Skills (c9) because it is a format validator that supplies no procedure. TypeSafe and OpenAI both have hash-plus-discovery records.

Evidence level: local integration and native discovery, plus one bounded provider diagnostic. Nothing here measures a task-quality improvement.
- candidate:openai-skills @ unpinned — The requirement (packet line 298) has two parts: concise canonical rules, and useful upstream procedures, without activating whole catalogs. No candidate supplies the canonical rules. On the evidence, those come from the project's own AGENTS/CLAUDE files; the community-practice-20260920.json layer map (lines 360-374) keeps the current project rules and copies. So the winners are chosen for the procedures part. c8, c4 and c3 are the only adopted candidates with retained evidence that named upstream skill files were installed with matching bytes and observed in a native client, and each is loaded per operation, not as a catalog. All three findings below are my own source review.

(1) c8 TypeSafe has the strongest evidence. catalogs/landscape/native-practice.json lines 32-69 record it pinned at 65a39f39, with its SKILL.md sha256 matching the upstream file. Fresh native source-review invocations completed in Claude Code 2.1.278 and Codex 0.155.1 (docs/native-skill-practice-20260921.md lines 116-126). blueprints/native-skill-practice/typesafe-result.json holds a provider diagnostic in which jev-1.13.0 got 7 of 8 cases right against 3 of 8 for exact-text-baseline-v1 (service_errors 0, promptfoo_exit_code 100).

(2) c4 ECC selects only two skills at 2b6e8397: search-first and iterative-retrieval. Installation with a matching source hash and single native Claude discovery were observed. The full hooks/rules bundle is explicitly not adopted (docs/foundation-closure-20260921.md line 21; catalogs/foundation/community-practice-20260920.json lines 112-113 and 313-341).

(3) c3 OpenAI covers two skills pinned at 49f948fa: gh-fix-ci and security-best-practices. Their SKILL.md hashes matched upstream and Claude init listed them. The unchanged gh-fix-ci inspect_pr_checks.py ran once, exited 0 and printed 'PR #55: no failing checks detected.' (native-practice.json lines 71-162).

This set differs from the project's own layer entry. docs/foundation-closure-20260921.md line 53 lists 'ECC; Anthropic skills; Agent Skills'. I did not select Anthropic skills (c2) because it is not adopted in the packet, and its only retained support is the line 26 claim that 'Existing Claude sync already exposes selected official skills', with no hash or discovery record. I did not select Agent Skills (c9) because it is a format validator that supplies no procedure. TypeSafe and OpenAI both have hash-plus-discovery records.

Evidence level: local integration and native discovery, plus one bounded provider diagnostic. Nothing here measures a task-quality improvement.

Alternatives:
- Agent Skills reference tools (conditional) — Native execution was observed, but only as a format validator. catalogs/foundation/decisions.json lines 296-335 record that it 'accepted and rendered one selected skill', with selection 'conditional'. docs/native-skill-practice-20260921.md lines 43-44 record three selected directories passing skills-ref. It supplies no procedure. native-practice.json lines 216-227 say the tree has no SKILL.md to install, and that reference validation does not establish Claude/Codex discovery. foundation-closure line 53 lists it for this layer, which fits its role as the portable-format check, not a skill source.
- Shan Claude best practice (conditional) — Source review only: 'No example workflow, model task, hook or service was executed' (community-practice-20260920.json lines 120-181). It is the closest candidate to the 'concise instructions' part of the requirement, but only as a reference (docs/foundation-closure-20260921.md line 22). Its cross-model example is dated March 6 and names older models (lines 37-39). It installs no selected skill file. The formal review was at bde3f031. A later research sweep did read it at the packet pin 15969ed2 (docs/harness-rules-convergence-20260922.md line 10), but no hash or install record exists at that pin.
- Trail of Bits security skills (conditional) — native-practice.json lines 199-214 record decision 'conditional' on source review only (pin 32e34f81). The procedure has mandatory comprehensive reporting and history phases plus an optional namespaced plugin agent, which is heavier than the existing bounded review. It suits only selected security-sensitive diffs. No trial is retained.
- Vercel frontend skills (conditional) — native-practice.json lines 166-182 record decision 'conditional' on source review only (pin 063bee94). The UI review skill fetches mutable external rules, and the React guide has 70 rules. There is no demonstrated need in the current static catalog, and no trial is retained.
- Claude Code Templates (conditional) — It has a readiness hash check only, with no native discovery and no task trial. evidence/artifacts/claude-repository-evidence-20260921/results.json lines 8928-8972 record pin c840d6f6, status 'guidance-only' and 'the `concise-planning` skill text is installed'. In that record, sha256sum of $HOME/code/agent-lab/.claude/skills/concise-planning/SKILL.md exited 0 and contained the recorded hash ecd35e54..., with evidence_class 'readiness'. The record does not say the recorded hash was compared with the upstream file. recipes/README.md line 85 treats the repository as an optional reference for a matching task, with 'No all-agent pack installation or runtime E2E'. catalogs/foundation/decisions.json lines 238-293 give its use status as 'not_applicable', and community-practice-20260920.json has no entry for it. No native-client discovery is recorded, unlike the three winners.
- VoltAgent subagent collection (conditional) — Not adopted. It is a role-contract reference, not a skill source, and has source review only. community-practice-20260920.json lines 223-270 note that the reviewed code-reviewer role exposes Write/Edit/Bash, so the title does not make it read-only (docs/foundation-closure-20260921.md line 24). It was not executed.
- Anthropic webapp-testing skill (overlap) — Not adopted. native-practice.json lines 183-198 record that it overlaps the accepted agent-browser/Playwright lanes, and its blanket networkidle wait has shown no advantage (source review at pin 34040c9c). foundation-closure line 26 calls the repository an on-demand reference, and line 53 lists 'Anthropic skills' for this layer. Neither line is backed by a retained hash or discovery observation for a specific Anthropic skill, so it does not beat c8 or c3.

Overturn when: The verdict changes in two cases. First, if a concrete task exposes a missing procedure and a matched trial shows a pinned conditional candidate (c6, c10, c5, c7 or c1) or a new skill does better than the current procedure: more supported findings, fewer conflicts or less loaded context. The trial must follow blueprints/native-skill-practice/catalog-cases.json and promptfooconfig.yaml, and the candidate must work in native discovery and task execution. Second, if a winner's installed bytes stop matching the retained pins or it fails native discovery. To check that, rerun `node --test test-contract.cjs` from blueprints/native-skill-practice and the native receipt check in blueprints/native-skill-practice/native-receipt.json.

Open gaps:
- No winner supplies the 'concise canonical rules' half of the requirement. That half is covered by the project's own instruction files, not by any candidate repository, and no candidate was compared on it.
- This winner set differs from docs/foundation-closure-20260921.md line 53 (ECC; Anthropic skills; Agent Skills). The difference is not resolved by an executed comparison.
- No selected skill has a measured task-quality or cost improvement over a matched baseline.
- TypeSafe's 7/8 result comes from 8 selected cases and is not representative accuracy. On C4, jev-1.13.0 said contradicted with confidence 0.76, against a frozen label of insufficient. The comparator is literal containment (3/8), not a native coding-agent baseline.
- gh-fix-ci was exercised only on a clean-check path. security-best-practices has installation and discovery evidence only; its references name FastAPI 0.128.x and Next.js 16.1.x, while the foundation pins 0.141.1 and 16.3.5.
- ECC skills have no task-performance trial. Codex discovery for them is not recorded in the files read.
- For ECC dd6ee538 and Shan 15969ed2, the packet pins were read in a research sweep (harness-rules-convergence-20260922.md line 10). Hash identity and installation are established only at 2b6e8397 for ECC. Shan has no install record.
- c7's readiness check confirms that the installed file matches a recorded hash. The record does not show comparison with the upstream file or native discovery.
- The packet gives pin null for c3, c6, c8 and c10, although native-practice.json records source pins for them.
- Native discovery on another PC (a new WSL or macOS host) is not established.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-instructions-skills-20260922; codex: -)

#### Isolation (isolation)

- worktrunk @ 0.79.0 — The requirement has two parts: keep edits separate, and enforce a real filesystem/network boundary only when a task needs it. Worktrunk (c5) and sandbox-runtime (c6) are the only adopted candidates with native-execution evidence for those parts on this Linux/WSL host.

c5, Worktrunk, for edit separation. There are two separate native runs:
(a) Pinned 0.79.0 (observed 2026-09-21). evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json, lines 70-101: an upgrade from previous_version 0.78.0 to installed_version 0.79.0. The native wt switch --create, list and remove commands ran on an owned disposable fixture and each exited 0. listed_worktrees_before_cleanup was 2, after_cleanup_worktrees was 1, git_status_porcelain was empty and removed_worktree_directory_absent was true. Lines 103-114 record a local regression comparison against the upstream test oracle: baseline_behavior_passed false for 0.78.0 and candidate_behavior_passed true for 0.79.0. The upstream Rust test was read but not executed. The artifact's status is 'qualified-and-promoted-awaiting-independent-coordinator-review' (line 5).
(b) Pre-0.79.0 build, version not recorded (2026-09-20). evidence/receipts/token-native-retained-functional-20260920.json, check worktrunk-owned-lifecycle: created_worktrees 2, remaining_worktrees 1, hooks_disabled true, disposable_repository_only true.
Dirty-removal refusal is recorded only for Worktrunk 0.78.0 on VelaNext (manifests/evidence.json line 1886). It has not been re-shown on 0.79.0.

The catalogs disagree on Worktrunk's role. catalogs/foundation/decisions.json 'owned-worktrees' (line 487) says selection 'default', with stage_refs listing only 'use' (lines 512-518). docs/token-native-saturation.md line 121 says 'optional' with stages 'use, cleanup'. I treat it as the default for edit separation only, following the decision record. That record limits Worktrunk to edits: 'Worktrees isolate edits, not permissions, accounts, global settings or shared services.'

c6, sandbox-runtime 0.0.77, as the conditional enforced boundary.
Filesystem: evidence/receipts/runtime-tools.json (native_cli_e2e, 2026-09-19), lines 25-31. allowed_write_exit was 0, denied_read_exit 1, separate_denied_write_exit 1 and host_file_created false. The clean child environment had HOME and PATH only.
Network: evidence/receipts/native-sandbox-network-20260920.json (native_cli_e2e, passed). The allowed loopback request exited 0 and reached the server (server requests went from 0 to 1). The explicit-deny and default-deny requests each exited 22 with a proxy 403 and did not reach the server (server_total_requests 1).
decisions.json 'scoped-os-isolation' (lines 523-563) cites both receipts and records selection 'conditional'. That matches the requirement's 'only where the selected task requires enforced restrictions'.

All of this is dated native local execution within a stated scope. It is not a security certification.
- sandbox-runtime @ 0.0.77 — The requirement has two parts: keep edits separate, and enforce a real filesystem/network boundary only when a task needs it. Worktrunk (c5) and sandbox-runtime (c6) are the only adopted candidates with native-execution evidence for those parts on this Linux/WSL host.

c5, Worktrunk, for edit separation. There are two separate native runs:
(a) Pinned 0.79.0 (observed 2026-09-21). evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json, lines 70-101: an upgrade from previous_version 0.78.0 to installed_version 0.79.0. The native wt switch --create, list and remove commands ran on an owned disposable fixture and each exited 0. listed_worktrees_before_cleanup was 2, after_cleanup_worktrees was 1, git_status_porcelain was empty and removed_worktree_directory_absent was true. Lines 103-114 record a local regression comparison against the upstream test oracle: baseline_behavior_passed false for 0.78.0 and candidate_behavior_passed true for 0.79.0. The upstream Rust test was read but not executed. The artifact's status is 'qualified-and-promoted-awaiting-independent-coordinator-review' (line 5).
(b) Pre-0.79.0 build, version not recorded (2026-09-20). evidence/receipts/token-native-retained-functional-20260920.json, check worktrunk-owned-lifecycle: created_worktrees 2, remaining_worktrees 1, hooks_disabled true, disposable_repository_only true.
Dirty-removal refusal is recorded only for Worktrunk 0.78.0 on VelaNext (manifests/evidence.json line 1886). It has not been re-shown on 0.79.0.

The catalogs disagree on Worktrunk's role. catalogs/foundation/decisions.json 'owned-worktrees' (line 487) says selection 'default', with stage_refs listing only 'use' (lines 512-518). docs/token-native-saturation.md line 121 says 'optional' with stages 'use, cleanup'. I treat it as the default for edit separation only, following the decision record. That record limits Worktrunk to edits: 'Worktrees isolate edits, not permissions, accounts, global settings or shared services.'

c6, sandbox-runtime 0.0.77, as the conditional enforced boundary.
Filesystem: evidence/receipts/runtime-tools.json (native_cli_e2e, 2026-09-19), lines 25-31. allowed_write_exit was 0, denied_read_exit 1, separate_denied_write_exit 1 and host_file_created false. The clean child environment had HOME and PATH only.
Network: evidence/receipts/native-sandbox-network-20260920.json (native_cli_e2e, passed). The allowed loopback request exited 0 and reached the server (server requests went from 0 to 1). The explicit-deny and default-deny requests each exited 22 with a proxy 403 and did not reach the server (server_total_requests 1).
decisions.json 'scoped-os-isolation' (lines 523-563) cites both receipts and records selection 'conditional'. That matches the requirement's 'only where the selected task requires enforced restrictions'.

All of this is dated native local execution within a stated scope. It is not a security certification.

Alternatives:
- Apple Container (conditional) — Its native evidence is a persistence fixture on a Mac: one PostgreSQL row survived a stop/start in a named volume (catalogs/foundation/decisions.json 'mac-container-volume', lines 1779-1839; docs/token-native-saturation.md line 63). It does not test an enforced filesystem or network restriction, and it runs only on macOS. The record also keeps a failure (a Mac Documents bind mount stalled) and has recovery 'not_established'. Selection is 'optional'. It does not qualify isolation on Linux/WSL.
- Podman / Quadlet (unqualified) — The evidence is source review only. catalogs/landscape/hosting-practice.json (lines 32-42) records decision 'conditional' and native_acceptance 'not_established', with image, networking, volume, GPU and Docker-API compatibility unmeasured. docs/hosting-container-practice.md line 6 says 'No container trial in this review establishes that either wins or fails on our workload.' No container was installed or run. This is untested, not a failure.
- Docker Engine / Moby (unqualified) — The evidence is source review only. catalogs/landscape/hosting-practice.json (lines 9-19) records docker-v29.8.1 as 'conditional' with native_acceptance 'not_established', and says no matched result shows better reproduction or recovery than the accepted native services. docs/hosting-container-practice.md lines 24-29 warns of Desktop/engine conflicts in WSL. No isolation trial was run. This is untested, not a failure.
- E2B (unqualified) — The evidence is source review only. catalogs/us-equities/agents-operations.json (lines 647-686) records e2b@2.51.0 as 'conditional' for untrusted generated code that needs a VM boundary. Its commands are marked 'Prospective commands; not executed', its limitations say 'Import is not sandbox E2E', and it needs an account/API credential, a cloud budget and managed hosting. No run of an enforced boundary is retained.
- gVisor (out_of_scope) — Not adopted. catalogs/us-equities/hosting-source-review.json (lines 104-122) records release-20260914.0 with decision 'defer_oci_platform' and execution_status research-only. The entry says the stronger application-kernel boundary needs an OCI bundle/runtime plus workload and platform acceptance, and that no containerized hosting platform currently requires runsc. No runsc execution is retained.

Overturn when: Change the boundary verdict if two things happen: a task requires hostile or untrusted code isolation, resource limits or a VM/OCI boundary; and a challenger passes an executed comparison against sandbox-runtime. The challengers are gVisor runsc, rootless Podman/Quadlet, rootless Docker and E2B.

The comparison must repeat these assertions:
- the network assertions in evidence/receipts/native-sandbox-network-20260920.json;
- the filesystem assertions in evidence/receipts/runtime-tools.json: allowed write, denied read, a separate denied write, and no host file created;
- workload startup, resources, cleanup and host compatibility.
Record the result as lifecycle stages in blueprints/token-native-focus/saturation-audit.json.

For the Mac lane, apply the same checks to Apple Container using blueprints/convergence-practice/container-storage/README.md.

Change the Worktrunk verdict only if a recorded 0.79.0 dirty-state or crash-cleanup check shows loss of unrelated work, or if the catalog resolves its role as 'optional' rather than 'default'.

Open gaps:
- Worktrunk version attribution: the 2026-09-20 worktrunk-owned-lifecycle check records no version and ran before 0.79.0 was released (2026-09-21). The 0.79.0 create/list/remove qualification is only in orx-worktrunk-upgrades.json, whose status is 'awaiting-independent-coordinator-review'. Dirty-removal refusal is evidenced only for 0.78.0 on VelaNext (manifests/evidence.json line 1886).
- The catalogs disagree on Worktrunk's role. decisions.json line 487 says 'default' with stage_refs 'use' only. docs/token-native-saturation.md line 121 says 'optional' with stages 'use, cleanup'. This is unresolved.
- sandbox-runtime filesystem quirk: when a path overlaps allow-write and deny-read, the first write exited 0 into an ephemeral hidden sandbox mount, leaving the host unchanged, rather than being refused (runtime-tools.json line 30). Direct write denial is established only by the separate fixture.
- sandbox-runtime has no retained evidence for TLS, SOCKS, DNS rebinding, IPv6, remote-host traffic or general sandbox escape. The first immediate network request failed with exit 7 because of a proxy startup race, and the tested command needed bounded curl retries.
- The sandbox-runtime version label is inconsistent: hosting-source-review.json line 79 says the installed CLI --version prints 1.0.0 while package.json says 0.0.77. The same entry's execution_status reads research-only except existing-tool results, but the native_cli_e2e receipts are those existing-tool results.
- No candidate has hostile-workload, resource-limit or macOS isolation evidence.
- Worktrunk isolates edits only, not permissions, accounts, global settings or shared services. Crash cleanup is not established.
- Ordinary native, Dagu, Claude and Codex processes are not sandboxed automatically.
- Podman, Docker, E2B and gVisor are untested, not failed.
- Bubblewrap is missing from the candidates. hosting-source-review.json lines 123-141 record an isolated ai-memory restore on distro bubblewrap 0.9.0 with all namespaces unshared and a read-only host root. It is not a packet candidate (sota_components_not_in_candidates is empty), no receipt was opened, and it has no network allow/deny assertion. This is a coverage gap in the layer's candidate set.
- codex lane absent for this layer
- 1 lane citation(s) name no repository evidence file (an unresolved path or a generated index); the full citations are kept in the sealed lane return

Lanes: codex_absent (claude: foundation-isolation-20260922; codex: -)

#### MCP servers and client surfaces (mcp-surfaces)

- mcporter @ 0.13.13 — The two adopted candidates do different jobs, so both win: mcporter (c3) is the bridge and MCP Inspector (c1) is the direct stdio inspector and caller. The observations come from retained native-execution receipts, not from anything run in this review. mcporter: observability/restart-receipt.json lines 165-179 (bridge_recovery, version 0.13.13) record the upstream start printing "Single-user daemon started.", 11 tools discovered, and the execute call printing "bridge-recovered". automatic_recovery was false, and line 181 keeps the failed first attempts (stale daemon metadata refused, and a deliberate start that timed out after 45 seconds). MCP Inspector: evidence/receipts/token-native-retained-functional-20260920.json lines 84-106 (fresh-inspector-context-call, kind upstream_cli) record the Inspector invoking native Context Mode with exit_code 0, and the checks "expected process exit" and "42 computed" both passed. That receipt is a later write-up of September 20 evidence and was not rerun (line 15). It covers arithmetic only (line 18) and records no tools/list operation. blueprints/token-native-focus/saturation-audit.json marks the "use" stage accepted_within_scope for both: mcp-inspector at lines 4898-4903 and mcporter at lines 5016-5021. The same audit leaves mcporter's persistence, restart, cleanup and recovery stages not_established (lines 5023-5042). catalogs/foundation/decisions.json line 1851 has native-mcp-adapters accepted_within_scope. recipes/README.md lines 91-92 and 153-160 only document the Inspector tools/list command and say to follow it with a selected tool call. That is a documented procedure, not an observed run. The configure-and-policy part of the requirement rests on source review only: decisions.json lines 2872-2882 put mcp-surface-policy at review_status source_review with "no new execution was run". Configuration itself is documented through the native client paths, meaning the example merges or `codex mcp add` / `claude mcp add` (recipes/README.md lines 140-151), not through c1 or c3. Both winners stay conditional, as the catalog records.
- mcp-inspector @ 2.7.0 — The two adopted candidates do different jobs, so both win: mcporter (c3) is the bridge and MCP Inspector (c1) is the direct stdio inspector and caller. The observations come from retained native-execution receipts, not from anything run in this review. mcporter: observability/restart-receipt.json lines 165-179 (bridge_recovery, version 0.13.13) record the upstream start printing "Single-user daemon started.", 11 tools discovered, and the execute call printing "bridge-recovered". automatic_recovery was false, and line 181 keeps the failed first attempts (stale daemon metadata refused, and a deliberate start that timed out after 45 seconds). MCP Inspector: evidence/receipts/token-native-retained-functional-20260920.json lines 84-106 (fresh-inspector-context-call, kind upstream_cli) record the Inspector invoking native Context Mode with exit_code 0, and the checks "expected process exit" and "42 computed" both passed. That receipt is a later write-up of September 20 evidence and was not rerun (line 15). It covers arithmetic only (line 18) and records no tools/list operation. blueprints/token-native-focus/saturation-audit.json marks the "use" stage accepted_within_scope for both: mcp-inspector at lines 4898-4903 and mcporter at lines 5016-5021. The same audit leaves mcporter's persistence, restart, cleanup and recovery stages not_established (lines 5023-5042). catalogs/foundation/decisions.json line 1851 has native-mcp-adapters accepted_within_scope. recipes/README.md lines 91-92 and 153-160 only document the Inspector tools/list command and say to follow it with a selected tool call. That is a documented procedure, not an observed run. The configure-and-policy part of the requirement rests on source review only: decisions.json lines 2872-2882 put mcp-surface-policy at review_status source_review with "no new execution was run". Configuration itself is documented through the native client paths, meaning the example merges or `codex mcp add` / `claude mcp add` (recipes/README.md lines 140-151), not through c1 or c3. Both winners stay conditional, as the catalog records.

Alternatives:
- Awesome MCP servers registry (unqualified) — It is a discovery list, not a bridge, inspector or configuration tool, and it is not adopted. The catalog keeps registries in scope only as discovery input (decisions.json line 2873: 'treat unexamined registries as discovery input only'). It records this one as an 'unexamined source' whose listing 'does not establish adoption' (lines 2883-2885). The requirement also rules out adopting an unexamined registry entry. The only evidence ref is recipes/README.md, and it reviews no registry entry against a concrete MCP surface gap. The refuter's grep for awesome-mcp|punkpeye|registry matched only npm and context-hub registry lines, not an MCP server registry entry. The disposition is changed from out_of_scope to unqualified because the catalog's activation text keeps registries in scope as discovery input.

Overturn when: Change the verdict only after an executed same-host comparison in which a challenger passes the use-stage acceptance that the incumbents are actually recorded as passing, and an incumbent fails it or is weaker. Challengers include mcporter v0.14.0 (the upstream latest per the packet) or a registry-sourced bridge or inspector reviewed against a concrete MCP surface gap. blueprints/token-native-focus/saturation-audit.json names the stage map (mcp-inspector use at lines 4898-4903, mcporter use at lines 5016-5021). The acceptance content comes from the receipts those stages cite. For the bridge, observability/restart-receipt.json lines 165-179 require a daemon start, discovered tools, and an execute call returning the expected output. For the inspector, token-native-retained-functional-20260920.json lines 84-106 require a direct upstream stdio tool call with exit 0 and the expected computed result ("42 computed"). The audit does not record tools/list or mcporter recovery as accepted stages, so neither is required of challengers. The saturation audit says Inspector 2.7.0 was not recertified on the current host (line 4838), and the Inspector receipt was not rerun (receipt line 15). The incumbents mcporter 0.13.13 and Inspector 2.7.0 must therefore be rerun under the same metric in the same comparison. Their retained receipts alone do not count. `python3 scripts/validate_catalogs.py` must still pass; observability/restart-receipt.json line 200 records it as the catalog validator. A retained failure of either incumbent on this rerun would also overturn the verdict.

Open gaps:
- mcporter is pinned at 0.13.13 while upstream is at v0.14.0, released 2026-09-22 (packet c3.upstream). The newer version is not qualified.
- The Inspector version 2.7.0 comes only from the saturation audit (line 4834) and the recipe pin (recipes/README.md line 91). The retained operation receipt (token-native-retained-functional-20260920.json lines 84-106) names the component 'mcp-inspector' but records no version. The audit says current_host_recertified_by_this_audit is false (line 4838).
- No retained receipt records an Inspector tools/list call. tools/list appears only as a documented command (recipes/README.md lines 91 and 153-160).
- The Inspector evidence covers only launching the pinned npm Context Mode CLI for arithmetic. It does not certify the full client plugin, hooks, project-file scope or current desktop connection (receipt line 18). The receipt is a later write-up of September 20 evidence that was not rerun, and its raw captures are private, bound only by hashes (lines 15-16).
- The saturation audit leaves mcporter's persistence, restart, cleanup and recovery stages not_established (lines 5023-5042). The only recovery evidence is restart-receipt.json bridge_recovery. It shows automatic_recovery false and failed first attempts (line 181).
- The catalog's next gap is still open: qualify changed process roots and scoped registration recovery without disturbing unrelated consumers. The mcporter daemon is shared, so removing one registration is not an uninstall or an all-client cleanup.
- The configure-and-policy part (mcp-surface-policy) is source review only; decisions.json line 2882 says no new execution was run. The configuration artifacts exist but no config-application receipt was reviewed. examples/claude-mcp.json.example, examples/codex-mcp.toml.example and examples/mcporter.json.example were found by glob, and the native CLI registration is at recipes/README.md lines 140-151.
- No executed comparison exists between bridge or inspector alternatives, and no registry entry has been reviewed against a concrete gap.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-mcp-surfaces-20260922; codex: -)

#### Native clients (native-clients)

- claude-code @ 2.1.278 — Claude Code (c7) and Codex (c3) are the only adopted candidates with retained evidence from native execution on the existing signed-in accounts, which is what the requirement asks for. In evidence/artifacts/full-stack-convergence-20260921/native-client-results.json (lines 1-100), kind "actual_native_model_read_only_integration", Claude ran headless with "-p --output-format stream-json" and model_override null. It returned exit_code 0, is_error false, model_observed "claude-fable-5-1", tool_count 11 and provider_total_tokens 250492. docs/full-stack-convergence.md lines 25-35 record that both clients finished the same five-step read-only task with eleven tool results each and no tool-result failures: Codex 0.155.1 used GPT-6 Astra/ultra for 255,335 tokens, and Claude Code 2.1.278 used Fable 5.1 for 250,492. The layer row at line 47 is "Native clients | Codex and Claude native accounts and streaming output". catalogs/foundation/decisions.json lines 113-160 (native-source-tasks, default, accepted_within_scope, both component ids) and lines 1950-1979 (native-session-resume, conditional, accepted_within_scope) cover tool use and same-session resume. For resume, blueprints/convergence-practice/native-recovery/README.md lines 3-9 record one frozen synthetic Codex interruption that resumed the same thread and session, and line 25 notes a separate Claude CLI SIGINT/same-session continuation on WSL. docs/foundation-closure-20260921.md line 52 selects both clients and records that installed 2.1.278 / 0.155.1 match checked release metadata. The two clients are complementary rather than ranked: they use independent accounts and model families, and neither run had a matched baseline. So both are selected as native defaults, and no model-quality ranking is implied.
- codex @ 0.155.1 — Claude Code (c7) and Codex (c3) are the only adopted candidates with retained evidence from native execution on the existing signed-in accounts, which is what the requirement asks for. In evidence/artifacts/full-stack-convergence-20260921/native-client-results.json (lines 1-100), kind "actual_native_model_read_only_integration", Claude ran headless with "-p --output-format stream-json" and model_override null. It returned exit_code 0, is_error false, model_observed "claude-fable-5-1", tool_count 11 and provider_total_tokens 250492. docs/full-stack-convergence.md lines 25-35 record that both clients finished the same five-step read-only task with eleven tool results each and no tool-result failures: Codex 0.155.1 used GPT-6 Astra/ultra for 255,335 tokens, and Claude Code 2.1.278 used Fable 5.1 for 250,492. The layer row at line 47 is "Native clients | Codex and Claude native accounts and streaming output". catalogs/foundation/decisions.json lines 113-160 (native-source-tasks, default, accepted_within_scope, both component ids) and lines 1950-1979 (native-session-resume, conditional, accepted_within_scope) cover tool use and same-session resume. For resume, blueprints/convergence-practice/native-recovery/README.md lines 3-9 record one frozen synthetic Codex interruption that resumed the same thread and session, and line 25 notes a separate Claude CLI SIGINT/same-session continuation on WSL. docs/foundation-closure-20260921.md line 52 selects both clients and records that installed 2.1.278 / 0.155.1 match checked release metadata. The two clients are complementary rather than ranked: they use independent accounts and model families, and neither run had a matched baseline. So both are selected as native defaults, and no model-quality ranking is implied.

Alternatives:
- MCPorter native bridge (overlap) — It is an MCP bridge and inspection adapter used by the native clients, not a native coding client with accounts, models or resumable sessions. Its cited receipt, evidence/receipts/claude-upstream-checks-20260921.json, only lists 'mcporter' among 37 component_ids (line 25) under the claim of '38 native command rows', and its own limitation says '38 zero-exit rows are not 38 functional E2Es' (line 45). That receipt contains no per-row detail showing a coding or research task run through mcporter. The packet's decisions are 'conditional' (mcp-surface-policy is source_review only), and the pin 0.13.13 is behind upstream v0.14.0.
- Claude Agent SDK (unqualified) — docs/foundation-closure-20260921.md line 82 says it is the 'Preferred Claude SDK candidate when needed; not newly installed or qualified'. It also records that the PyPI 0.2.157 and GitHub 0.2.156 labels differ. catalogs/us-equities/agents-operations.json lines 1646-1683 give decision 'alternative' at evidence_level 'source_review', and the commands there are 'Prospective ... not executed'. The official docs also restrict claude.ai login use for third-party products. Lines 76-78 of the closure doc limit SDK use to applications that need structured events, custom tools or programmatic session control, a need the evidence does not show for this layer.
- OpenAI Agents SDK (unqualified) — catalogs/us-equities/agents-operations.json lines 1605-1643 give decision 'alternative' at evidence_level 'source_review' for v0.22.3. Its commands are prospective and were not executed, and its limitations include 'No provider API call or model comparison performed' and 'Does not inherit Codex account entitlement'. It is an API-backed agent loop, so it does not meet the requirement to use existing native accounts. It is not a subscription-backed Codex replacement (rationale line 1613). docs/foundation-closure-20260921.md lines 80-86 do not list it among the SDK candidates checked on 2026-09-21.

Overturn when: An application task needs structured events, custom tools or programmatic session control that the native CLI path cannot provide (the packet's existing_overturn_when), and a supported SDK (c2 Claude Agent SDK or c4 OpenAI Agents SDK) passes the same frozen task, account, effect and recovery checks. A qualifying check would be an SDK arm of python3 blueprints/convergence-practice/native-recovery/run.py (the documented native runner, which currently takes --codex and --run-dir only), or the same fixture as blueprints/convergence-practice/worker-recovery/README.md, run with native usage retained. A failed re-run of that native-recovery runner, or of the five-step read-only task, on a changed client version would also reopen the verdict.

Open gaps:
- No model-quality ranking between Claude Code and Codex: the five-step read-only task has no matched baseline (docs/full-stack-convergence.md line 37), and the older fixed-order comparison left cache state uncontrolled (lines 38-40).
- The Codex resume fixture ran on bundled Codex 0.155.0-alpha.9.2 on the Mac (native-recovery/README.md line 4), not on the 0.155.1 pin. Resume on 0.155.1 is not shown by this fixture.
- Crash, provider cancellation, whole-host and cross-host recovery, and billing cessation are not established (decisions.json lines 1973-1976; native-recovery/README.md lines 28-32).
- Neither SDK (c2, c4) has been installed or executed. Their suitability is untested, which is different from having failed.
- Activation on a new host (WSL or macOS on another PC) is not established by the source-host receipts (decisions.json line 142; claude-upstream-checks limitations line 46).
- MCPorter's pin 0.13.13 is behind upstream v0.14.0, and no per-row mcporter functional result was opened.
- In the public projection, Claude's tool_results have status null and is_error false (native-client-results.json lines 92-100). Completion is inferred from is_error and exit_code 0, not from an explicit 'completed' status like Codex's.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-native-clients-20260922; codex: -)

#### Observation and optional inference (observation-inference)

- opentelemetry-collector-contrib @ 0.161.0 — The requirement is to observe real native usage and service outcomes through one privacy-filtered local pipeline. The retained evidence shows native execution through OTel Collector Contrib (c8), then Prometheus (c9), then Grafana (c5). The provider judgments I kept are the packet's evidence_kind native_execution and the decision loopback-usage-observation, accepted_within_scope. In my own source review, docs/native-telemetry-resolution.md lines 11-45 records a real native Claude Code 2.1.278 task. It exported OTLP to the loopback Collector with content logging disabled. Its returned usage (Input 34, Cache creation 16,402, Cache read 14,959, Output 787) "matched the subsequent native Prometheus response exactly" (promtool query instant, lines 28-29). The Grafana Claude panel showed all four series. docs/dashboard-gap-resolution.md line 13 repeats this. docs/dashboard-rendered-acceptance.md line 30 records a native promtool `up` query that returned 1 for all seven scrape targets. observability/receipt.json lines 313-330 records a synthetic privacy canary: logs and metrics POST returned 200, forbidden_marker_absent true and metadata_channels_normalized true. Line 371 keeps the earlier failure, where metadata fell outside the attribute maps before the fix. catalogs/us-equities/agents-operations.json line 861 names the contrib distribution as the single process that carries the privacy transform. These three components are the minimal path from filtering to storage to rendering that the observed match went through. Loki, Alertmanager and ntfy are accepted parts of the same pipeline but add log retention or alert delivery beyond the usage observation itself. This is bounded, same-host native evidence, not a measured comparison against other stacks.
- prometheus @ 3.14.0 — The requirement is to observe real native usage and service outcomes through one privacy-filtered local pipeline. The retained evidence shows native execution through OTel Collector Contrib (c8), then Prometheus (c9), then Grafana (c5). The provider judgments I kept are the packet's evidence_kind native_execution and the decision loopback-usage-observation, accepted_within_scope. In my own source review, docs/native-telemetry-resolution.md lines 11-45 records a real native Claude Code 2.1.278 task. It exported OTLP to the loopback Collector with content logging disabled. Its returned usage (Input 34, Cache creation 16,402, Cache read 14,959, Output 787) "matched the subsequent native Prometheus response exactly" (promtool query instant, lines 28-29). The Grafana Claude panel showed all four series. docs/dashboard-gap-resolution.md line 13 repeats this. docs/dashboard-rendered-acceptance.md line 30 records a native promtool `up` query that returned 1 for all seven scrape targets. observability/receipt.json lines 313-330 records a synthetic privacy canary: logs and metrics POST returned 200, forbidden_marker_absent true and metadata_channels_normalized true. Line 371 keeps the earlier failure, where metadata fell outside the attribute maps before the fix. catalogs/us-equities/agents-operations.json line 861 names the contrib distribution as the single process that carries the privacy transform. These three components are the minimal path from filtering to storage to rendering that the observed match went through. Loki, Alertmanager and ntfy are accepted parts of the same pipeline but add log retention or alert delivery beyond the usage observation itself. This is bounded, same-host native evidence, not a measured comparison against other stacks.
- grafana @ 13.2.2 — The requirement is to observe real native usage and service outcomes through one privacy-filtered local pipeline. The retained evidence shows native execution through OTel Collector Contrib (c8), then Prometheus (c9), then Grafana (c5). The provider judgments I kept are the packet's evidence_kind native_execution and the decision loopback-usage-observation, accepted_within_scope. In my own source review, docs/native-telemetry-resolution.md lines 11-45 records a real native Claude Code 2.1.278 task. It exported OTLP to the loopback Collector with content logging disabled. Its returned usage (Input 34, Cache creation 16,402, Cache read 14,959, Output 787) "matched the subsequent native Prometheus response exactly" (promtool query instant, lines 28-29). The Grafana Claude panel showed all four series. docs/dashboard-gap-resolution.md line 13 repeats this. docs/dashboard-rendered-acceptance.md line 30 records a native promtool `up` query that returned 1 for all seven scrape targets. observability/receipt.json lines 313-330 records a synthetic privacy canary: logs and metrics POST returned 200, forbidden_marker_absent true and metadata_channels_normalized true. Line 371 keeps the earlier failure, where metadata fell outside the attribute maps before the fix. catalogs/us-equities/agents-operations.json line 861 names the contrib distribution as the single process that carries the privacy transform. These three components are the minimal path from filtering to storage to rendering that the observed match went through. Loki, Alertmanager and ntfy are accepted parts of the same pipeline but add log retention or alert delivery beyond the usage observation itself. This is bounded, same-host native evidence, not a measured comparison against other stacks.

Alternatives:
- Loki (conditional) — Loki is an accepted log store in the same pipeline, not a separate path. Correction: its packet evidence_ref, docs/native-telemetry-resolution.md, never mentions Loki. The Loki evidence I verified is observability/receipt.json lines 313-330, where the synthetic privacy canary returned loki_records 1. The usage match that meets the requirement went through Prometheus and Grafana, so Loki complements the winners rather than being required for usage observation. Its limits per agents-operations.json lines 1005-1008: no HA and no full transcript archive.
- Alertmanager (conditional) — Alertmanager covers alert routing, not usage observation. observability/receipt.json lines 303-312 records one firing and one resolved notification on a dedicated fixture, with external_delivery_tested false. agents-operations.json lines 1047-1050 limits it to the local alert path.
- ntfy (conditional) — ntfy is a local notification sink, not usage observation. docs/native-telemetry-resolution.md lines 86-97 records two unchanged upstream tests passing and a local renderer replay, which is local integration. No production webhook was observed after deployment, so formatting of the next real notification is unverified.
- AgentsView (conditional) — AgentsView is a session-history archive, not the privacy-filtered usage pipeline. docs/dashboard-gap-resolution.md line 11 records one native refresh of three selected sources (messages 3,193 to 3,697) and calls it a snapshot, not continuous ingestion. docs/token-native-saturation.md line 26 says automatic archive discovery remains unestablished. The pin 0.43.0 is behind upstream v0.44.0.
- otel-tui (conditional) — The only retained evidence is decisions.json lines 2077-2100: one synthetic loopback terminal trace was accepted. Its stated limitation is that synthetic acceptance is not production tracing completeness. The adopted Collector path has traces disabled (agents-operations.json line 882), so otel-tui serves diagnostic traces only.
- Claude HUD (overlap) — This is an optional status-line rendering that overlaps with native /usage. docs/foundation-closure-20260921.md lines 109-132 records a native PTY session where the HUD rendered model, project, context and usage. It explicitly does not prove exact billing reconciliation or every HUD statistic. decisions.json line 2136 says to use native usage for authoritative accounting.
- llama.cpp optional local inference (conditional) — llama.cpp is an optional model route that is qualified for one workload only. evidence/receipts/native-gpu-patch-20260920.json records one Qwen3.8-27B Q4_K_M partial-offload repair that passed 12 original tests on an RTX4090. The receipt calls it one fixture and one trial, with generation at 179.191 seconds against a 180-second cap. It is not an interactive default, and decisions.json line 2190 keeps native workers as the default.
- Phoenix (unqualified) — The packet marks Phoenix adopted, but the evidence is source review only. agents-operations.json lines 1246-1270 give the decision as conditional and state that the server launch is prospective, no app was instrumented, and auto-instrumentation can capture prompt and tool contents. There is no native execution or privacy canary.
- OpenLIT (unqualified) — OpenLIT is not adopted and was only source-reviewed. agents-operations.json lines 1155 and 1181-1184 state that nothing was installed, invoked or delivered. They also say it would duplicate collection and expand transcript processing.
- SGLang (unqualified) — SGLang is not adopted, and the only evidence is a prospective install and launch recipe (agents-operations.json lines 484-521). No workload was executed. The card says not to stack vLLM and SGLang as serial gateways.

Overturn when: The verdict changes if the current Collector-to-Prometheus-to-Grafana path cannot answer a required trace or usage question and an alternative wins an executed comparison. Traces are currently disabled (agents-operations.json line 882). An alternative such as Phoenix, OpenLIT, or Loki-first logs would need to pass that comparison. The comparison would run python3 -m pytest tests/test_observability.py tests/test_observability_backends_alerts.py and repeat the privacy canary from observability/receipt.json. It must show forbidden_marker_absent and exact counter reconciliation with a native task's returned usage, as in docs/native-telemetry-resolution.md, without duplicate capture. Separately, an optional model route changes only if blueprints/convergence-practice/gpu-inference/qualify.py passes on a frozen representative workload.

Open gaps:
- Traces are disabled and no trace database is deployed (agents-operations.json line 882), so the trace side of the requirement is covered only by a synthetic otel-tui trace.
- Privacy filters cover tested fields and trusted native instrumentation, not arbitrary-content DLP (observability/receipt.json line 24). The canary is synthetic.
- The exact usage match in docs/native-telemetry-resolution.md covers one Claude task. I did not verify an equivalent Codex match in the refs I read.
- Scheduled-service and reboot persistence, and missing task attribution, remain the next gap (decisions.json line 2036).
- The only qualified optional model route is llama.cpp on one single-task trial near its time cap. vLLM (pin behind upstream: 0.25.0 vs v0.30.0) and OmniRoute are outside the candidate set, and OmniRoute has unsuccessful gateway tasks (decisions.json lines 2241-2243).
- No production ntfy webhook was observed after the template deployment.
- No measured comparison against alternative observation stacks exists. Selection rests on bounded native acceptance on one host.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-observation-inference-20260922; codex: -)

#### Quality and evaluation (quality-evaluation)

- promptfoo @ 0.123.1 — Promptfoo (c2) and Playwright (c6) are the only candidates whose retained records verify changed behaviour through a returned native run: an evaluation for Promptfoo and a browser flow for Playwright. Both records also keep failures.

Other candidates also have failure-preserving native records, but they do not verify changed behaviour. ShellCheck and Difftastic have them in evidence/receipts/portable-cli-artifacts.json, but that receipt covers only a static shell check and a structural-diff exit code on fixtures. TypeSafe keeps its failed case C4, but that diagnostic ran inside Promptfoo.

Promptfoo evidence:
- docs/promptfoo-upstream-retrieval.md (lines 8-22) records a run of Promptfoo 0.123.1 through its native exec: provider on NVIDIA's unchanged upstream retrieval example. It returned all four paired documents first, one passing case, 0 failures and 0 errors.
- The same document limits the claim to compatibility with that upstream example; it is not a benchmark. Lines 70-73 only mention two earlier browser-automation failures in the report review (a stale ref and a wrong row-count expectation). It says they are kept in private evidence, which I did not check. They were not Promptfoo evaluation failures.
- blueprints/native-skill-practice/typesafe-result.json shows Promptfoo used as the evaluation harness. It kept promptfoo_exit_code 100 and every failing row: the exact-text baseline matched 3/8 labels and jev-1.13.0 matched 7/8, with the C4 disagreement retained. This directly meets the requirement's failure-preservation clause.

Playwright evidence:
- catalogs/foundation/decisions.json (deterministic-quality-tools, around lines 1352-1410) lists playwright-test use as accepted_within_scope. Its source path is blueprints/convergence-practice/wsl-application/README.md.
- That lane's receipt.json (lines 114-126) records `taskset -c 0-3 pnpm exec playwright test --config ../wsl-application/playwright.config.ts` with exit 0, passed 1, failed 0, retries 0, browser_assertions_changed false and page_errors 0. It also records full_failed_attempts_retained true (line 258).

Evidence class: both are local integrations of upstream tools and examples on this host, recorded as done. I reviewed the retained documents and receipts and reran nothing. This is not an unchanged upstream test suite and not a universal quality ranking.
- playwright-test @ 1.63.0 — Promptfoo (c2) and Playwright (c6) are the only candidates whose retained records verify changed behaviour through a returned native run: an evaluation for Promptfoo and a browser flow for Playwright. Both records also keep failures.

Other candidates also have failure-preserving native records, but they do not verify changed behaviour. ShellCheck and Difftastic have them in evidence/receipts/portable-cli-artifacts.json, but that receipt covers only a static shell check and a structural-diff exit code on fixtures. TypeSafe keeps its failed case C4, but that diagnostic ran inside Promptfoo.

Promptfoo evidence:
- docs/promptfoo-upstream-retrieval.md (lines 8-22) records a run of Promptfoo 0.123.1 through its native exec: provider on NVIDIA's unchanged upstream retrieval example. It returned all four paired documents first, one passing case, 0 failures and 0 errors.
- The same document limits the claim to compatibility with that upstream example; it is not a benchmark. Lines 70-73 only mention two earlier browser-automation failures in the report review (a stale ref and a wrong row-count expectation). It says they are kept in private evidence, which I did not check. They were not Promptfoo evaluation failures.
- blueprints/native-skill-practice/typesafe-result.json shows Promptfoo used as the evaluation harness. It kept promptfoo_exit_code 100 and every failing row: the exact-text baseline matched 3/8 labels and jev-1.13.0 matched 7/8, with the C4 disagreement retained. This directly meets the requirement's failure-preservation clause.

Playwright evidence:
- catalogs/foundation/decisions.json (deterministic-quality-tools, around lines 1352-1410) lists playwright-test use as accepted_within_scope. Its source path is blueprints/convergence-practice/wsl-application/README.md.
- That lane's receipt.json (lines 114-126) records `taskset -c 0-3 pnpm exec playwright test --config ../wsl-application/playwright.config.ts` with exit 0, passed 1, failed 0, retries 0, browser_assertions_changed false and page_errors 0. It also records full_failed_attempts_retained true (line 258).

Evidence class: both are local integrations of upstream tools and examples on this host, recorded as done. I reviewed the retained documents and receipts and reran nothing. This is not an unchanged upstream test suite and not a universal quality ranking.

Alternatives:
- Inspect AI (unqualified) — The evidence is source review only. catalogs/us-equities/agents-operations.json (lines 1282-1319) records evidence_level source_review. Its native_workflow says 'Prospective commands; not executed for this catalog', and its limit says 'Eval command would perform model calls; not run here.' There is no returned eval, frozen oracle or failure record. That catalog marks it 'default' for the us-equities agent-evaluation layer, but that is a selection claim, not an observed execution. docs/acceptance-evidence-policy.md is general policy with nothing specific to Inspect AI. Untested does not mean failed: it stays the named challenger for tool-use and extraction suites.
- MCP Inspector (out_of_scope) — evidence/receipts/token-native-retained-functional-20260920.json (lines 18 and 84-106) records one Inspector stdio call to Context Mode: exit 0, and the check '42 computed' passed. The receipt itself says this 'does not certify the complete client plugin, hooks, project-file scope or current desktop connection.' That qualifies an MCP inspection/adapter operation, not general changed-behaviour verification. The packet's review_status is not_individually_reviewed. The receipt is retrospective ('not rerun by this documentation update').
- ShellCheck (conditional) — The trade-off is scope, not missing execution. catalogs/foundation/decisions.json (deterministic-quality-tools, lines 1363-1407) lists ShellCheck use as accepted_within_scope and cites evidence_id portable-cli-artifacts (lines 1370-1374). That receipt, evidence/receipts/portable-cli-artifacts.json (lines 20-28), records `shellcheck fixtures/example.sh` with exit_code 0, expected_exit 0 and matched true. That is one clean run on one fixture, with no finding reported and no negative case exercised. The receipt limits itself to 'Fixture-specific native behavior, not an LLM invocation or general quality benchmark' (line 15). ShellCheck is a narrow static shell checker that complements the winners; it is not a changed-behaviour verification or evaluation lane.
- TypeSafe semantic skill (conditional) — blueprints/native-skill-practice/typesafe-result.json records a measured diagnostic. jev-1.13.0 matched 7/8 frozen labels against 3/8 for the exact-text baseline, with 0 service errors and a median latency of 171.5 ms. Case C4 disagrees: the model answered contradicted where the frozen label is insufficient, at confidence 0.76. The failure is kept (passed false; the limitations say to 'preserve as a failure requiring source review'). The file's own limitations name 'Eight selected diagnostic cases, not representative' and a weak comparator, and say there is 'no calibrated threshold... or automatic selection authority'. docs/native-skill-practice-20260921.md (lines 98-114) and catalogs/landscape/native-practice.json (lines 50-69) confirm the judgments are advisory. TypeSafe supplies semantic judgments inside a verification flow; it is not the harness itself, and this diagnostic ran through Promptfoo.
- Difftastic (conditional) — The trade-off is scope, not missing execution. catalogs/foundation/decisions.json (deterministic-quality-tools, lines 1363-1407) lists Difftastic use as accepted_within_scope and cites evidence_id portable-cli-artifacts. That receipt, evidence/receipts/portable-cli-artifacts.json, keeps a failed expectation. The initial `difft --color never fixtures/before.py fixtures/after.py` returned exit_code 0 against expected_exit 1, matched false (lines 30-41). The corrected `difft --exit-code ...` returned exit_code 1 against expected 1 (lines 127-139). Line 16 notes that 'Difft default exit 0 was normal', which is a matter of exit semantics rather than a defect. The run shows only that a structural diff was detected on a before/after fixture. Difftastic is a review aid, not a behaviour check or evaluation harness.
- Official OpenAI CI and security skills (conditional) — catalogs/landscape/native-practice.json (lines 95-124) records one run of the unchanged gh-fix-ci helper inspect_pr_checks.py against PR 55. It exited 0 with stdout 'PR #55: no failing checks detected.' An independent gh query returned five SUCCESS checks. Failure-log extraction, repair quality and native-agent activation remain explicitly unqualified. For security-best-practices, finding quality and false-positive control are unmeasured (docs/native-skill-practice-20260921.md lines 12-13 and 151-153). These are procedure skills layered on CI, not the verification lane, and their failure path is untested.
- MLflow (unqualified) — The evidence is source review only. catalogs/us-equities/agents-operations.json (lines 1688-1725) records evidence_level source_review, prospective commands marked not executed, and the limit 'No tracking server or experiment recorded by this task.' Its role there is experiment tracking and lineage, not changed-behaviour verification. That entry is marked conditional: 'Add when strategy/feature experiments require a durable registry'.

Overturn when: First overturn: a defined tool-use or extraction requirement that cannot be expressed in the Promptfoo or Playwright lanes. Inspect AI (c1) would then run as a prospective `inspect eval`, at inspect-ai==0.3.266 per catalogs/us-equities/agents-operations.json. It must use the same frozen oracle, blueprints/native-skill-practice/catalog-cases.json, and be compared with the existing arm, blueprints/native-skill-practice/promptfooconfig.yaml. It overturns this verdict only if it matches at least as many frozen labels, keeps every failing row and its exit status, and gives failure inspection that is at least as usable.

Second overturn: a rerun of the unchanged Playwright test in blueprints/convergence-practice/wsl-application/ (per its README and receipt.json) fails, or its assertions change.

Open gaps:
- No unchanged upstream Promptfoo or Playwright test suite was run. The evidence is an upstream example with a local assertion, plus a local application lane that uses an unchanged Playwright spec.
- The Promptfoo evidence is 4/4 on NVIDIA's four-pair example plus an 8-case diagnostic. Neither is a held-out model-quality evaluation, and no universal ranking follows from them.
- Inspect AI and MLflow have no executed result. Untested does not mean failed.
- ShellCheck has one clean fixture run with no finding and no negative case. Difftastic has a structural-diff exit-code check only. Neither has evidence as a behaviour-verification lane.
- The gh-fix-ci failing-log path, repair quality and security-skill finding quality are unqualified.
- TypeSafe case C4 disagrees with its frozen label and is unresolved as a model error. Its threshold is uncalibrated.
- The two catalogs conflict. agents-operations.json marks Inspect AI 'default' and Promptfoo 'alternative' for the us-equities agent-evaluation layer, while the foundation evidence favours Promptfoo. No executed comparison between them exists.
- Correction from round 1: returned native output for ShellCheck and Difftastic does exist, in evidence/receipts/portable-cli-artifacts.json. I had wrongly treated it as absent, and c4 and c7 are now reclassified as local_integration. The winner basis is restated as changed-behaviour verification with failure retention, not 'only native execution with failures'.
- Correction from round 1: docs/promptfoo-upstream-retrieval.md only mentions the stale-ref and row-count failures (lines 70-73), which it says are in private evidence. They came from browser automation of the report, not from the Promptfoo evaluation, and I did not check them.
- Correction carried from round 1: c6's ref docs/dashboard-rendered-acceptance.md never mentions Playwright. Its Promptfoo row (line 33) describes an older two-case echo evaluation, which docs/promptfoo-upstream-retrieval.md supersedes. The Playwright support comes from the decision's source_path, the wsl-application README and receipt.json.
- Correction carried from round 1: the Promptfoo operation in the 20260920 receipt (fresh-promptfoo-local) is a two-assertion echo run with zero model calls. It is not model-quality evidence.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-quality-evaluation-20260922; codex: -)

#### Recovery and portability (recovery-portability)

- restic @ 0.19.1 — Change in this revision: uv (c1) is no longer a co-winner. The winner set is Restic (c4) alone, so winner_evidence_class native_proven applies only to evidence that was actually executed. Restic is the only adopted candidate with retained native execution evidence. evidence/receipts/native-offhost-restic-20260920.json (kind native_cli_e2e) records a fresh GitHub-hosted runner, run 35537533416, conclusion success, using restic 0.19.1 with sha256 20d4142678d0d95ec11a4759def1b73fd9190abc9ca19e4b62d067c0b387e639. The runner ran 7 unchanged upstream tests at source 6aa3a516 with 0 failures. It rejected a wrong password with exit 12 and 0 restored files. `check --read-data` exited 0 and reported "no errors were found". It then restored two exact snapshot IDs with exits 0 and 0. The complete path/type/length/sha256/mode oracle passed over 6 files and 1048747 bytes. An independent review matched 24 downloaded reports and confirmed the ciphertext was unchanged. catalogs/foundation/decisions.json supports two further restore scopes, with Restic as a component in both. First, same-host restore (lines 1890-1948, evidence_scope at line 1915): selected public bytes, ai-memory/FTS state and Qdrant snapshot/query results survived a same-host backup and restore; an independent physical host is unestablished (line 1917). Second, fresh hosted destination (lines 2480-2515, line 2501): two fresh hosted jobs passed ai-memory and Qdrant backup, encrypted transfer and empty-target restore, checked with actual scoped memory queries and Qdrant state/query equality. adoption/lifecycle.md lines 257-279 give the native `restic snapshots/check/restore` recipe and keep keys out of the catalog, which fits the requirement not to copy authentication stores. The oracles are local integration checks, the state is synthetic, and review_status is confirmed_conditional. The requirement's other half, "reproduce selected tools", has no candidate with retained execution evidence. uv (c1) is the retained SDK lock lane, but all its evidence is source review. adoption/research.json lines 235-267 mark all 8 uv commands "not executed by this research pass". The clean-install proof in docs/portable-userspace-install-20260921.md uses npm, upstream archives and native installers, and contains no uv invocation. So that half is recorded as an open gap and is not credited to any winner.

Alternatives:
- uv (conditional) — adoption/research.json line 221 records the decision required_reuse_existing_native_python_layer. Line 222 limits its scope to syncing the accepted SDK package versions from a hash-bearing requirements lock into a new environment. It is the retained Python SDK lock lane, not a proven tool-reproduction or recovery path. All 8 native commands at lines 235-267, including `uv --version` and `uv pip sync --require-hashes`, are marked "source-confirmed recipe; not executed by this research pass". binary_downloaded_or_verified and signature_verified are both false (lines 277-278). Line 280 reports "Installed uv --version returned 0.12.17" as a read-only observation, which conflicts with the not-executed status of the same command at lines 237-238, and no receipt is retained for it. Line 281 assigns fresh-environment installation and acceptance evidence to the coordinator. docs/portable-userspace-install-20260921.md contains no uv match (grep \buv\b returned nothing), and its clean-install tools were not installed with uv. uv is kept as the conditional SDK lock lane pending a fresh-environment hash-locked sync acceptance.
- mise (conditional) — adoption/research.json lines 76-104 record the decision optional_native_tool_layer_not_required_for_current_uv_only_adoption. Line 87 says the current SDK can be reproduced with uv. Line 94 says a tool-manager lock does not replace the SDK hash lock. mise's lock/install commands are unexecuted source-confirmed recipes. Its checksum metadata matched, but no binary was downloaded or signature-verified. No native install or restore evidence was retained.
- chezmoi (conditional) — adoption/research.json lines 414-473 record the decision defer_optional_selected_dotfile_management, limited to explicitly selected non-secret files. Broad home-directory or authentication-store capture is excluded, and the requirement forbids copying auth stores anyway. The checksum metadata matched, but the signature was not verified and no chezmoi command was executed.
- Litestream (conditional) — catalogs/us-equities/hosting-source-review.json lines 186-202 record the decision defer_until_continuous_replication_requirement and the status research_only. Litestream adds a standing writer that creates _litestream_lock in the source database. The review states that native ai-memory backup plus restic already covers the bounded need. The v0.5 restore lacks the older Age encryption. No execution was retained.
- Devbox (overlap) — Not adopted. adoption/research.json lines 522-569 record the decision defer_nix_environment_platform. Devbox changes the host environment model and overlaps the uv SDK lane. Only checksum-list metadata was checked; nothing was downloaded, executed or signature-verified.
- Determinate Nix installer (out_of_scope) — Not adopted. adoption/research.json lines 624-667 record the decision defer_privileged_platform_installation. It is a privileged system installer, not an SDK lock or state-recovery tool, and the current native/WSL setup does not need it. Only the GitHub asset digest was recorded; nothing was downloaded or verified.

Overturn when: Three checks could change this verdict. (1) Re-run the blueprints/convergence-practice/offhost-restore/README.md or blueprints/convergence-practice/offhost-app-state/README.md recipe with matching inputs. If it shows Restic data loss or an oracle mismatch that Litestream's (c5) `restore -integrity-check full` avoids in an executed side-by-side run on the same state and host, Restic would be demoted for SQLite application state. (2) A fresh-environment hash-locked sync following the adoption/research.json uv recipe (`uv venv` then `uv pip sync --require-hashes --no-build` into a new prefix, then `uv pip check`) that passes on the target host would add uv (c1) as a native_proven co-winner for SDK reproduction. (3) An executed multi-language or system-dependency case where mise (c3) or a Devbox/Nix profile (c7/c6) passes locked install, restore, resume and cleanup while uv cannot cover it would promote that alternative for tool reproduction.

Open gaps:
- No candidate's retained evidence shows that the selected tools reproduce on a new host. The clean-install proof in docs/portable-userspace-install-20260921.md uses npm, upstream archives and native installers, and no candidate in this packet covers it.
- uv has no fresh-environment sync acceptance. All 8 of its commands are marked not executed (adoption/research.json lines 235-267). The 0.12.17 version observation at line 280 conflicts with that status and has no receipt. The '36-package' lock (line 230) has no acceptance receipt among the evidence_refs.
- Restic recovery is proven only on synthetic state and hosted runners inside one GitHub administrative domain. The ai-memory/Qdrant proof at decisions.json line 1915 is same-host only; the fresh-hosted proof is line 2501. Independent physical host, lost-account/password recovery, production data, whole-stack recovery, reboot and power loss remain unestablished.
- UID/GID, timestamps, ACL/xattrs, sparse files, links, Windows filesystems and long-term retention are not qualified for Restic.
- Snapshots are sequential, not atomic across applications, and native-client rebinding after a restore is not established.
- Restic recovery on macOS or on a new WSL PC is not established by these receipts.
- uv, mise, chezmoi, Litestream, Devbox and the Nix installer have no native execution evidence. They are untested, not failed.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-recovery-portability-20260922; codex: -)

#### Scheduling and supervision (scheduling-supervision)

- systemd @ 255.4-1ubuntu8.17 — I picked systemd (c1) and Dagu (c3) together because each covers part of the requirement and neither covers all of it. They are the only adopted candidates with native execution records, and each record's review_status is accepted_within_scope.

- **systemd (c1):** In catalogs/foundation/decisions.json, decision owned-process-deadlines (lines 1533-1574) records that the Linux user manager terminated a TERM-ignoring parent and its descendants. It kept the timeout failure, and a separate fresh run was accepted. Decision native-child-interruption-recovery (lines 2324-2383) records automatic systemd cleanup of descendants after an abrupt parent-runtime failure. The checkpoint was unchanged and there was one local effect. Together these cover the 'bounded process trees, cancellation' part of the requirement.
- **Dagu (c3):** Decision checkpointed-workflow-resume (lines 1576-1634) records three things. Native cancel/retry kept one checkpoint on both Mac and WSL. The job ran to completion after the SSH client was terminated. A selected subset of unchanged official Dagu retry tests passed on fresh hosted runners.
- **Both together:** Decision owned-guest-scheduled-reboot (lines 2385-2478) lists both components. A systemd user-manager timer automatically resumed the same Dagu run after an orderly reboot of a disposable guest. The checkpoint was preserved and there was one local effect. That covers 'visible history' and 'recoverable effects'.

The observed class is native execution of the pinned upstream tools on synthetic local workloads plus local integration. The decision records themselves label the planner and the guest experiment as local synthetic integration coverage, not production workloads. docs/foundation-rd-readiness.md line 26 independently records the same retained selection ('Dagu/user-service supervision within their recorded scopes'). This is my own review of the decision records. I did not open the receipts underneath them.
- dagu @ 2.16.6 — I picked systemd (c1) and Dagu (c3) together because each covers part of the requirement and neither covers all of it. They are the only adopted candidates with native execution records, and each record's review_status is accepted_within_scope.

- **systemd (c1):** In catalogs/foundation/decisions.json, decision owned-process-deadlines (lines 1533-1574) records that the Linux user manager terminated a TERM-ignoring parent and its descendants. It kept the timeout failure, and a separate fresh run was accepted. Decision native-child-interruption-recovery (lines 2324-2383) records automatic systemd cleanup of descendants after an abrupt parent-runtime failure. The checkpoint was unchanged and there was one local effect. Together these cover the 'bounded process trees, cancellation' part of the requirement.
- **Dagu (c3):** Decision checkpointed-workflow-resume (lines 1576-1634) records three things. Native cancel/retry kept one checkpoint on both Mac and WSL. The job ran to completion after the SSH client was terminated. A selected subset of unchanged official Dagu retry tests passed on fresh hosted runners.
- **Both together:** Decision owned-guest-scheduled-reboot (lines 2385-2478) lists both components. A systemd user-manager timer automatically resumed the same Dagu run after an orderly reboot of a disposable guest. The checkpoint was preserved and there was one local effect. That covers 'visible history' and 'recoverable effects'.

The observed class is native execution of the pinned upstream tools on synthetic local workloads plus local integration. The decision records themselves label the planner and the guest experiment as local synthetic integration coverage, not production workloads. docs/foundation-rd-readiness.md line 26 independently records the same retained selection ('Dagu/user-service supervision within their recorded scopes'). This is my own review of the decision records. I did not open the receipts underneath them.

Alternatives:
- Prefect (unqualified) — The only evidence is source review. catalogs/us-equities/agents-operations.json lines 361-401 give decision 'alternative' and evidence_level source_review; the commands are marked 'Prospective commands; not executed'; its limitations say 'No flow is supplied or scheduled here.' The same record says to 'Choose instead of Dagu for the first scheduler, not an extra coordinator above it', so it would replace Dagu rather than add to it. It also needs a persistent server/database. Nothing records a cancellation, process-tree, checkpoint or reboot result for Prefect.
- Dagster (out_of_scope) — catalogs/us-equities/agents-operations.json lines 403-440 give it the 'data-orchestration' layer only (not durable-jobs). Its role is 'Partitioned data assets, lineage and backfills' and its rationale says 'not needed just to start three agents'. It is source review only and its commands were not executed. It needs an asset-definitions project and a metadata database. Nothing records process-tree supervision or recovery.
- Restate (unqualified) — catalogs/us-equities/hosting-source-review.json lines 28-47 give decision 'defer_new_service' with execution_status research_only. The record says it 'duplicates manual Dagu research coordination and adds persistence/auth/SDK operation', and that durable replay does not prove external exactly-once effects. Its license is BUSL-1.1 with a use-grant limit. The same file (line 60) says to pick Temporal or Restate, not both. Nothing records native execution.
- Temporal (conditional) — It is the recorded escalation path, but it has not been exercised. catalogs/us-equities/agents-operations.json lines 318-359 call it 'Preferred escalation when jobs must survive host loss, await approvals or span days; heavier than the present bounded worker', with source_review evidence and unexecuted commands. catalogs/us-equities/hosting-source-review.json line 60 records the production burden (persistence and visibility databases, schema upgrades, payload encryption, auth) and says start-dev is developer evidence only. docs/foundation-rd-readiness.md line 26 keeps it keep-but-compare until a durable cross-host requirement exceeds the accepted native path. The current evidence does not show that requirement.

Overturn when: The verdict changes if a real workload needs host-loss survival, days-long waits or durable cross-host effects. The comparison is a challenger arm (Temporal preferred over Restate, per hosting-source-review.json line 60) run through the same declared effect/retry/recovery cases as the accepted fixtures: blueprints/convergence-practice/job-recovery/fixture.py (checkpointed cancel/retry), blueprints/convergence-practice/service-reboot/plan.json with run.py (orderly reboot resume), and blueprints/us-equities/worker-supervision/fixture.py (process-tree deadline). The challenger must pass all cases with acceptable operational burden, or the Dagu+systemd arm must fail a case the challenger passes. A retained failure of Dagu 2.17.0 (the upstream latest) on the same checkpoint/reboot cases would also reopen the Dagu pin.

Open gaps:
- Dagu is pinned at 2.16.6 but upstream latest is v2.17.0 (packet pin_behind_upstream=true). No result for 2.17.0 is recorded.
- All accepted runs used synthetic local workloads: one WSL host, Mac/WSL cancellation, and one orderly reboot of a disposable guest. Physical-PC reboot, power loss, host or user-manager crash, off-host recovery and production workloads are not established (decisions.json lines 2347-2352 and 2405-2412).
- Remote provider cancellation, billing cessation and distributed or external exactly-once effects (for example broker orders) are not established by any candidate's evidence.
- catalogs/us-equities/agents-operations.json line 281 says 'Scheduling remains inactive', and hosting-source-review.json line 21 says the service 'runs server, not scheduler' (dated 2026-09-19). The later guest reboot used a bounded systemd timer, but no recurring production schedule of real jobs is recorded.
- Neither docs/foundation-convergence-20260921.md (lines 97-99) nor this review supplies an observed daily maintenance trigger or restart persistence on the real host.
- Prefect, Dagster, Restate and Temporal have no native execution evidence. Their suitability relative to Dagu is unmeasured, not failed.
- claude-code and beads also carry scheduling-supervision decisions (native-child-interruption-recovery, native-workflow-graceful-recovery, dependency-task-queue), but they are outside this packet's candidate list and I did not judge them.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-scheduling-supervision-20260922; codex: -)

#### Secrets and credentials (secrets-credentials)

- gitleaks @ 8.30.1 — c1 (gitleaks 8.30.1) is the only adopted candidate, so it is the only possible winner. The native_proven class applies to the detection half of the requirement only. For that half there is native execution evidence. blueprints/convergence-practice/wsl-native-tools/receipt.json (lines 10-25) records native_attempts 2 and names receipt-wsl-hardened.json as the current native receipt (lines 12-13). In the hardened receipt, blueprints/convergence-practice/wsl-native-tools/receipt-wsl-hardened.json lines 368-384, gitleaks 8.30.1 produced positive_findings 1 with rule github-pat on an inert fixture and negative_findings 0 on the clean control. The same lines show fully_redacted true and status passed (line 380). The run was on Linux WSL2 and scanned in directory mode. The current runner, blueprints/convergence-practice/wsl-native-tools/run.py, raises an error unless there is exactly one github-pat finding (lines 35-36). It invokes `gitleaks dir ... --redact=100` at line 178. The original runner, executed-run-v1.py lines 34-38, has the same check. catalogs/foundation/decisions.json lines 1412-1469 (offline-security-inventory, accepted_within_scope) link this evidence to the layer. The second half of the requirement is keeping sign-ins and credentials off the checkout. It has no executed check and rests on policy plus source review only. The layer decision, catalogs/foundation/decisions.json lines 2909-2948, has review_status source_review at line 2918 and says "no new execution was run to freeze this taxonomy layer" at line 2927. The policy it relies on is adoption/manifest.json line 428, "authentication_transfer": "native_login_on_target_only". This corrects the earlier citation of line 419, which reads "research-specification". I kept the provider's 'conditional' selection because my source review supports it. I did not strengthen it.

Alternatives:
- OpenBao (unqualified) — OpenBao is not adopted and has no execution, installation or comparison evidence. catalogs/foundation/decisions.json calls it "an unused, unqualified candidate" (line 2929) and says it has "no lifecycle stage at all" (line 2939). Correction: the packet cites adoption/manifest.json as OpenBao's evidence, but a case-insensitive grep of that file finds no OpenBao entry. The only related line is the authentication_transfer policy at line 428. OpenBao is a secret store, not a scanner, so it would not replace detection before publication. It would matter only if a recorded need to share secrets across hosts or operators existed, and none does. It is untested, not failed.

Overturn when: Change the verdict only if an executed comparison beats c1 on the same scope.

Option 1: extend blueprints/convergence-practice/wsl-native-tools/run.py with a competing-scanner arm. Today it reads only the gitleaks and worktrunk binaries (line 169) and needs --prefix and --work (lines 248-249). Then run `python3 blueprints/convergence-practice/wsl-native-tools/run.py --prefix <install-prefix> --work <work-dir>` on the same inert positive fixture and clean control. The competitor must produce exactly one redacted finding and zero clean-control findings, and it must also catch more planted secret classes or git-history secrets, or beat gitleaks on redaction or false-positive rate.

Option 2: record a concrete need to share secrets across hosts or operators. Then install and query OpenBao, or a comparable secret manager, for that scenario against the native_login_on_target_only policy (adoption/manifest.json line 428).

Open gaps:
- The 'keep sign-ins and credentials off the checkout' half of the requirement has no executed check. It rests on a policy (adoption/manifest.json line 428) and a source_review decision (catalogs/foundation/decisions.json lines 2918 and 2927). The native_proven class covers detection only.
- The gitleaks evidence is one synthetic github-pat fixture and one clean control, scanned in directory mode ('gitleaks dir', run.py line 178) on Linux WSL2. Git-history scanning, other secret types and false-positive rates are unmeasured. The receipt excludes certification for arbitrary repositories and Mac acceptance (receipt.json line 56).
- Secret scanning does not prove that no secret exists anywhere (decisions.json line 1439).
- Native login state and account credentials are not inventoried as a component (decisions.json line 2930). Broker credential handling is left to a trading gate outside this layer.
- GitHub attestation endpoints returned 404 for gitleaks. The publisher checksum, archive digest and license checks passed, but there is no attestation claim (receipt.json line 58).
- No competing secret scanner or secret manager has been compared. run.py has no arm for a second scanner. OpenBao has no evidence in its cited reference.
- zizmor and syft appear as layer-adjacent components but are not candidates. Their evidence covers workflow and dependency controls, not secret detection.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-secrets-credentials-20260922; codex: -)

#### Semantic code retrieval (semantic-rag)

- socraticode @ 1.14.0 — Source review, my own. The requirement asks for a scoped local index, a compatible embedding service and recoverable state. The only path that covers it is SocratiCode (c7), using vLLM-served Nemotron embeddings (c8) and storing them in Qdrant (c1). The evidence is:
- a retained native execution,
- one sealed measured comparison against a lexical baseline, whose closure is unresolved,
- local integration checks.
No measured comparison exists against the packet's alternative candidates (c2 to c6).

What was observed:
(a) evidence/receipts/native-rag.json, kind native_model_e2e, recorded 2026-09-19T04:55:03Z.
- Codex (gpt-6-astra) and Claude (claude-opus-5[1m]) each ran one successful codebase_search with limit 1. Both returned tools/ecosystem/linux-usage-report.cjs lines 2-39 with score 0.6429.
- The index held 35 files and 139 chunks in collection codebase_72cfa87c5abf, status green.
- Nemotron-3-Embed-1B-BF16 returned 2048 finite dimensions with norm 1.0000000207936353.
- Automatic watching picked up an add, an update and a delete, each in about 3.0 s.

(b) Sealed comparison, 2026-09-22. It lives outside the packet root, in <host-path>/agent-lab.
- File: runner-temp/semantic-rag/out/verdict.json, protocol_id semantic-rag-executed-20260922-v2r, computed_by tools/compare/semantic/run-arms.mjs.
- Arm A (SocratiCode+Qdrant+vLLM): span_hit_at_5 0.85, mrr_at_10 0.7416666666666666, p95 141 ms, peak RSS 120 MB, restore_pass null.
- Arm B (jCodeMunch lexical): span_hit_at_5 0.25, mrr_at_10 0.14750000000000002, p95 88 ms, peak RSS 68 MB, restore_pass 1.
- final_status is "unresolved". docs/tasks/2026-09-22-executed-comparisons.md lines 368-385 record n=20 sealed questions, 3 repeats with byte-identical quality, and no power calculation.
- In quality, the embedding route clearly beats the lexical baseline. That lexical baseline is not one of this packet's candidates.

(c) Recovery is only partly established.
- In catalogs/foundation/decisions.json lines 857-925, Qdrant recovery is accepted_within_scope and SocratiCode recovery is not_established.
- <host-path>/restore-A.json lines 4-11 shows three Qdrant-snapshot/restic restore cycles with values 0, 1, 0. Attempt 1 failed with "replay span lists differed after restore" even though the snapshot checksum matched (lines 18-33). The task record, line 376, says ranks 9 and 10 swapped for one question.

(d) docs/hf-memory-model-qualification.md lines 50-68: NVIDIA's upstream retrieval example ran against local vLLM and put all four intended documents at rank 1. docs/native-memory-rag-lifecycle.md lines 13-15 give the pins SocratiCode 1.14.0, Qdrant 1.19.1 and vLLM 0.25.0.

Kept from provider judgments without opening their receipts: the Qdrant same-host and synthetic off-host restore decisions in the packet (c1.decisions).
- qdrant @ 1.19.1 — Source review, my own. The requirement asks for a scoped local index, a compatible embedding service and recoverable state. The only path that covers it is SocratiCode (c7), using vLLM-served Nemotron embeddings (c8) and storing them in Qdrant (c1). The evidence is:
- a retained native execution,
- one sealed measured comparison against a lexical baseline, whose closure is unresolved,
- local integration checks.
No measured comparison exists against the packet's alternative candidates (c2 to c6).

What was observed:
(a) evidence/receipts/native-rag.json, kind native_model_e2e, recorded 2026-09-19T04:55:03Z.
- Codex (gpt-6-astra) and Claude (claude-opus-5[1m]) each ran one successful codebase_search with limit 1. Both returned tools/ecosystem/linux-usage-report.cjs lines 2-39 with score 0.6429.
- The index held 35 files and 139 chunks in collection codebase_72cfa87c5abf, status green.
- Nemotron-3-Embed-1B-BF16 returned 2048 finite dimensions with norm 1.0000000207936353.
- Automatic watching picked up an add, an update and a delete, each in about 3.0 s.

(b) Sealed comparison, 2026-09-22. It lives outside the packet root, in <host-path>/agent-lab.
- File: runner-temp/semantic-rag/out/verdict.json, protocol_id semantic-rag-executed-20260922-v2r, computed_by tools/compare/semantic/run-arms.mjs.
- Arm A (SocratiCode+Qdrant+vLLM): span_hit_at_5 0.85, mrr_at_10 0.7416666666666666, p95 141 ms, peak RSS 120 MB, restore_pass null.
- Arm B (jCodeMunch lexical): span_hit_at_5 0.25, mrr_at_10 0.14750000000000002, p95 88 ms, peak RSS 68 MB, restore_pass 1.
- final_status is "unresolved". docs/tasks/2026-09-22-executed-comparisons.md lines 368-385 record n=20 sealed questions, 3 repeats with byte-identical quality, and no power calculation.
- In quality, the embedding route clearly beats the lexical baseline. That lexical baseline is not one of this packet's candidates.

(c) Recovery is only partly established.
- In catalogs/foundation/decisions.json lines 857-925, Qdrant recovery is accepted_within_scope and SocratiCode recovery is not_established.
- <host-path>/restore-A.json lines 4-11 shows three Qdrant-snapshot/restic restore cycles with values 0, 1, 0. Attempt 1 failed with "replay span lists differed after restore" even though the snapshot checksum matched (lines 18-33). The task record, line 376, says ranks 9 and 10 swapped for one question.

(d) docs/hf-memory-model-qualification.md lines 50-68: NVIDIA's upstream retrieval example ran against local vLLM and put all four intended documents at rank 1. docs/native-memory-rag-lifecycle.md lines 13-15 give the pins SocratiCode 1.14.0, Qdrant 1.19.1 and vLLM 0.25.0.

Kept from provider judgments without opening their receipts: the Qdrant same-host and synthetic off-host restore decisions in the packet (c1.decisions).
- vllm @ 0.25.0 — Source review, my own. The requirement asks for a scoped local index, a compatible embedding service and recoverable state. The only path that covers it is SocratiCode (c7), using vLLM-served Nemotron embeddings (c8) and storing them in Qdrant (c1). The evidence is:
- a retained native execution,
- one sealed measured comparison against a lexical baseline, whose closure is unresolved,
- local integration checks.
No measured comparison exists against the packet's alternative candidates (c2 to c6).

What was observed:
(a) evidence/receipts/native-rag.json, kind native_model_e2e, recorded 2026-09-19T04:55:03Z.
- Codex (gpt-6-astra) and Claude (claude-opus-5[1m]) each ran one successful codebase_search with limit 1. Both returned tools/ecosystem/linux-usage-report.cjs lines 2-39 with score 0.6429.
- The index held 35 files and 139 chunks in collection codebase_72cfa87c5abf, status green.
- Nemotron-3-Embed-1B-BF16 returned 2048 finite dimensions with norm 1.0000000207936353.
- Automatic watching picked up an add, an update and a delete, each in about 3.0 s.

(b) Sealed comparison, 2026-09-22. It lives outside the packet root, in <host-path>/agent-lab.
- File: runner-temp/semantic-rag/out/verdict.json, protocol_id semantic-rag-executed-20260922-v2r, computed_by tools/compare/semantic/run-arms.mjs.
- Arm A (SocratiCode+Qdrant+vLLM): span_hit_at_5 0.85, mrr_at_10 0.7416666666666666, p95 141 ms, peak RSS 120 MB, restore_pass null.
- Arm B (jCodeMunch lexical): span_hit_at_5 0.25, mrr_at_10 0.14750000000000002, p95 88 ms, peak RSS 68 MB, restore_pass 1.
- final_status is "unresolved". docs/tasks/2026-09-22-executed-comparisons.md lines 368-385 record n=20 sealed questions, 3 repeats with byte-identical quality, and no power calculation.
- In quality, the embedding route clearly beats the lexical baseline. That lexical baseline is not one of this packet's candidates.

(c) Recovery is only partly established.
- In catalogs/foundation/decisions.json lines 857-925, Qdrant recovery is accepted_within_scope and SocratiCode recovery is not_established.
- <host-path>/restore-A.json lines 4-11 shows three Qdrant-snapshot/restic restore cycles with values 0, 1, 0. Attempt 1 failed with "replay span lists differed after restore" even though the snapshot checksum matched (lines 18-33). The task record, line 376, says ranks 9 and 10 swapped for one question.

(d) docs/hf-memory-model-qualification.md lines 50-68: NVIDIA's upstream retrieval example ran against local vLLM and put all four intended documents at rank 1. docs/native-memory-rag-lifecycle.md lines 13-15 give the pins SocratiCode 1.14.0, Qdrant 1.19.1 and vLLM 0.25.0.

Kept from provider judgments without opening their receipts: the Qdrant same-host and synthetic off-host restore decisions in the packet (c1.decisions).

Alternatives:
- Hugging Face Hub native CLI (conditional) — This candidate supports pinning and verifying model files. It is neither the serving path nor the index. hf 1.32.0 checked 15 Nemotron files at revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 (docs/hf-memory-model-qualification.md lines 43-48; evidence/receipts/hf-memory-models-20260921.json line 24). It kept the native warning about 33 extra local metadata files (same receipt, line 18). It shares the local-embedding-runtime decision with vLLM (catalogs/foundation/decisions.json lines 927-975). It is needed for reproducible model inputs, but it does not answer queries.
- Haystack (unqualified) — The only evidence is a pinned source review, and the commands were never run (catalogs/us-equities/foundation-memory.json lines 946-981). It belongs to the rag-pipeline layer for financial documents, not to conceptual code search. The catalog marks it 'conditional' and notes 'No financial corpus pipeline or performance proof yet'. It has no code-index, embedding-compatibility or recovery evidence, and it was not an arm of the 2026-09-22 sealed semantic-rag comparison.
- pgvector (conditional) — The only evidence is a source review. The catalog's own limitation says: 'Adds no benefit to current Qdrant code index unless a specific SQL integration need is established.' Its use depends on a future PostgreSQL service (catalogs/us-equities/foundation-memory.json lines 1057-1092). It was not an arm of any executed comparison.
- code-memory (unqualified) — The only evidence is a source review; it was never installed or trialled. At commit 5a8db166 the review found 'No measured resource, retrieval or maintenance advantage'. It also noted:
- The default Jina weights are licensed CC-BY-NC-4.0.
- The loader enables remote model code without pinning a revision.
- Two freshness concerns are source-level only and were not reproduced (docs/blind-catalog-source-adjudication-20260921.md lines 5-45).
The sealed Codex review lists it as 'provisional_source_based_selection_not_adopted' (codex-source-review.json line 253). It was not an arm of the executed 2026-09-22 comparison.
- LanceDB (unqualified) — Not adopted. The only evidence is a source review. The catalog decision is 'alternative', for local research corpora, and its commands were not run. The x86 wheel requires AVX2/FMA/F16C. There is no code-index, embedding or recovery evidence (catalogs/us-equities/foundation-memory.json lines 1094-1132). Nothing in the evidence shows it meets the requirement better than Qdrant.

Overturn when: An executed comparison already exists outside the packet root: the agent-lab semantic-rag runner, <host-path>/run-arms.mjs. Its usage lines 17-21 cover the seal, run, restore and assemble subcommands, with the sealed protocol in tools/compare/semantic/protocol.sealed.json. It is checked by <host-path>/{sealed-protocol,span-matching,closure-and-isolation,latency-stats,closure-script}.test.mjs, run with `node --test tests/compare` (cwd agent-lab, 93 pass per docs/tasks/2026-09-22-executed-comparisons.md line 373). Its 2026-09-22 result is final_status "unresolved". Any of these would change the verdict:
1. A challenger arm meets the sealed overturn conjunction under a new protocol_id and closure returns overturn. The conjunction is at least 2/20 better on both span_hit_at_5 and mrr_at_10, no worse on p95 latency and peak RSS, and restore_pass 1 (run-arms.mjs lines 794 and 877-902). The challenger could be code-memory @5a8db166, or a LanceDB- or pgvector-backed index run through the same runner: `node tools/compare/semantic/run-arms.mjs run --protocol <p> --arm B --repeats 3 --out-dir <dir>`, then `restore` and `assemble`.
2. The incumbent's own restore repeats. Running `node tools/compare/semantic/run-arms.mjs restore --protocol <p> --arm A --out-dir <dir>` could return 0 on every attempt. The incumbent floor would then fire (armA.restore_pass === 0), and the Qdrant recoverable-state claim would count as failed rather than unresolved. It returned 0, 1, 0 in restore-A.json.
3. A native vLLM upgrade attempt at the latest upstream v0.30.0 initializes and reproduces the four first-ranked results in docs/hf-memory-model-qualification.md lines 50-68. That would change the c8 pin, not the winner set.

Open gaps:
- Quality: the only measured comparison is against a lexical baseline, with n=20 and no power calculation. Its final_status is 'unresolved'. None of the packet candidates c2 to c6 has been an executed arm.
- Recoverable state: the incumbent returned restore_pass null, from attempts 0, 1, 0. Two of three Qdrant-snapshot/restic cycles changed the replay span lists; the task record (line 376) describes the change as ranks 9 and 10 swapped for one question. The snapshot checksum matched in both cycles. SocratiCode recovery is not_established (decisions.json lines 902-906). Byte-identical restored retrieval is therefore not established.
- Weakness in the sealed protocol: the incumbent floor tests `=== 0`, so a null incumbent restore escapes the floor. The task record (executed-comparisons.md lines 380-381) says fixing this needs a new protocol_id.
- The native two-client evidence from 2026-09-19 is one question per client, not a recall benchmark.
- No opened source records whether vLLM v0.30.0 (upstream latest per the packet metadata) was tried. Its status is unknown. Version 0.29.0 had an actual host initialization failure (docs/native-memory-rag-lifecycle.md line 15).
- Nemotron-3-Embed-8B-BF16 and EmbeddingGemma have not been qualified for this route. The live service uses a 4,096-token context, not the model card's 32,768.
- The code-memory freshness concerns are source-level implications, not reproduced failures.
- Watcher freshness was outside the scope of the sealed comparison. Arm A's index_build_s was a warm re-index.
- Another project, a full-service restart and new-PC/macOS activation each need their own scope. SocratiCode's AGPL-3.0 licence obligations were not assessed.
- No token-saving or provider-usage comparison is established.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-semantic-rag-20260922; codex: -)

#### Context and usage efficiency (token-efficiency)

- rtk @ 0.49.0 — This verdict comes from my own review of the retained sources. No TypeSafe inference results were supplied. The requirement has three parts: supply useful task context, keep originals recoverable, and measure artifact reductions separately from provider usage. In this revision, ccusage replaces Context Mode because it is the only adopted candidate that covers the measurement part. I no longer use the 'default' selection in native-process-defaults as support. That decision is scoped to the native-clients and instructions-skills layers (catalogs/foundation/decisions.json lines 163-171). Inside token-efficiency, every decision is 'conditional' (lines 1144-1147, 1199-1202, 1313-1317).

RTK (c4) supplies context and recovers originals. I reviewed the clean-CI fixture source (scripts/native_token_ci.py lines 211-235). It checks that both commit subjects survive compaction, and that `rtk proxy git log -2` stdout is identical to the raw `git log -2` output (check 'rtk-proxy-exact-stdout'). A retained record says the hosted clean install ran 41 native commands and 14 checks on local fixtures (docs/full-stack-convergence.md lines 132-137). There is one exact artifact pair, a Git log going from 537 to 178 o200k_base tokens (docs/token-practice.md line 107). Its lifecycle row accepts the use stage only, with 1 retained pair (docs/token-native-saturation.md line 109).

Headroom (c5) covers recoverable originals directly. Owned synthetic MCP compression and retrieval passed, and so did isolated install, restart and uninstall (decisions.json line 1214). After restart it restored identical original content (token-native-saturation.md lines 3-10). Its lifecycle row accepts install, use, persistence, restart, cleanup and recovery, with 11 retained pairs (line 82). Measured pairs: the direct summary used 19,714 tokens against 36,625, with exact recovery available, and a guarded log fixture used 191 against 26,529 (token-practice.md lines 231-234). The retained counterexample is 2,732 tokens against a 5,105-token original, rising to 18,777 when the full original was also fetched (lines 215-217).

ccusage (c1) covers the measurement part. Its decision capability is 'Read native provider usage without mixing counter scopes', based on offline native usage parsing and scoped current-session observations (decisions.json lines 1309-1328). The gap follow-up confirms the offline parsing (token-practice.md lines 291-294). The pinned 20.0.24 upgrade passed its selected upstream subset of 34 cases (full-stack-convergence.md lines 124-130, listed 'respectively'). Artifact counts are kept separate from provider usage, because RTK, Context Mode and Headroom counters are estimates and not provider accounting (token-practice.md lines 150-156).

What was observed: local integration and synthetic fixtures, one native RTK artifact pair, Headroom's owned-fixture recovery, and ccusage offline parsing. None of this establishes a causal or lifetime provider saving.
- headroom @ 0.37.0 — This verdict comes from my own review of the retained sources. No TypeSafe inference results were supplied. The requirement has three parts: supply useful task context, keep originals recoverable, and measure artifact reductions separately from provider usage. In this revision, ccusage replaces Context Mode because it is the only adopted candidate that covers the measurement part. I no longer use the 'default' selection in native-process-defaults as support. That decision is scoped to the native-clients and instructions-skills layers (catalogs/foundation/decisions.json lines 163-171). Inside token-efficiency, every decision is 'conditional' (lines 1144-1147, 1199-1202, 1313-1317).

RTK (c4) supplies context and recovers originals. I reviewed the clean-CI fixture source (scripts/native_token_ci.py lines 211-235). It checks that both commit subjects survive compaction, and that `rtk proxy git log -2` stdout is identical to the raw `git log -2` output (check 'rtk-proxy-exact-stdout'). A retained record says the hosted clean install ran 41 native commands and 14 checks on local fixtures (docs/full-stack-convergence.md lines 132-137). There is one exact artifact pair, a Git log going from 537 to 178 o200k_base tokens (docs/token-practice.md line 107). Its lifecycle row accepts the use stage only, with 1 retained pair (docs/token-native-saturation.md line 109).

Headroom (c5) covers recoverable originals directly. Owned synthetic MCP compression and retrieval passed, and so did isolated install, restart and uninstall (decisions.json line 1214). After restart it restored identical original content (token-native-saturation.md lines 3-10). Its lifecycle row accepts install, use, persistence, restart, cleanup and recovery, with 11 retained pairs (line 82). Measured pairs: the direct summary used 19,714 tokens against 36,625, with exact recovery available, and a guarded log fixture used 191 against 26,529 (token-practice.md lines 231-234). The retained counterexample is 2,732 tokens against a 5,105-token original, rising to 18,777 when the full original was also fetched (lines 215-217).

ccusage (c1) covers the measurement part. Its decision capability is 'Read native provider usage without mixing counter scopes', based on offline native usage parsing and scoped current-session observations (decisions.json lines 1309-1328). The gap follow-up confirms the offline parsing (token-practice.md lines 291-294). The pinned 20.0.24 upgrade passed its selected upstream subset of 34 cases (full-stack-convergence.md lines 124-130, listed 'respectively'). Artifact counts are kept separate from provider usage, because RTK, Context Mode and Headroom counters are estimates and not provider accounting (token-practice.md lines 150-156).

What was observed: local integration and synthetic fixtures, one native RTK artifact pair, Headroom's owned-fixture recovery, and ccusage offline parsing. None of this establishes a causal or lifetime provider saving.
- ccusage @ 20.0.24 — This verdict comes from my own review of the retained sources. No TypeSafe inference results were supplied. The requirement has three parts: supply useful task context, keep originals recoverable, and measure artifact reductions separately from provider usage. In this revision, ccusage replaces Context Mode because it is the only adopted candidate that covers the measurement part. I no longer use the 'default' selection in native-process-defaults as support. That decision is scoped to the native-clients and instructions-skills layers (catalogs/foundation/decisions.json lines 163-171). Inside token-efficiency, every decision is 'conditional' (lines 1144-1147, 1199-1202, 1313-1317).

RTK (c4) supplies context and recovers originals. I reviewed the clean-CI fixture source (scripts/native_token_ci.py lines 211-235). It checks that both commit subjects survive compaction, and that `rtk proxy git log -2` stdout is identical to the raw `git log -2` output (check 'rtk-proxy-exact-stdout'). A retained record says the hosted clean install ran 41 native commands and 14 checks on local fixtures (docs/full-stack-convergence.md lines 132-137). There is one exact artifact pair, a Git log going from 537 to 178 o200k_base tokens (docs/token-practice.md line 107). Its lifecycle row accepts the use stage only, with 1 retained pair (docs/token-native-saturation.md line 109).

Headroom (c5) covers recoverable originals directly. Owned synthetic MCP compression and retrieval passed, and so did isolated install, restart and uninstall (decisions.json line 1214). After restart it restored identical original content (token-native-saturation.md lines 3-10). Its lifecycle row accepts install, use, persistence, restart, cleanup and recovery, with 11 retained pairs (line 82). Measured pairs: the direct summary used 19,714 tokens against 36,625, with exact recovery available, and a guarded log fixture used 191 against 26,529 (token-practice.md lines 231-234). The retained counterexample is 2,732 tokens against a 5,105-token original, rising to 18,777 when the full original was also fetched (lines 215-217).

ccusage (c1) covers the measurement part. Its decision capability is 'Read native provider usage without mixing counter scopes', based on offline native usage parsing and scoped current-session observations (decisions.json lines 1309-1328). The gap follow-up confirms the offline parsing (token-practice.md lines 291-294). The pinned 20.0.24 upgrade passed its selected upstream subset of 34 cases (full-stack-convergence.md lines 124-130, listed 'respectively'). Artifact counts are kept separate from provider usage, because RTK, Context Mode and Headroom counters are estimates and not provider accounting (token-practice.md lines 150-156).

What was observed: local integration and synthetic fixtures, one native RTK artifact pair, Headroom's owned-fixture recovery, and ccusage offline parsing. None of this establishes a causal or lifetime provider saving.

Alternatives:
- Context Mode (conditional) — Context Mode overlaps RTK in the in-layer decision selected-context-processing, where it is only 'conditional' (catalogs/foundation/decisions.json lines 1140-1153). The evidence on this requirement is weak. Its lifecycle row accepts use and restart only, with no recovery stage and 0 retained artifact pairs (docs/token-native-saturation.md line 73). The only paired native trials have opposite signs: Codex went from 135,217 to 119,998 tokens (11.26% fewer), while Claude went from 292,561 to 368,121 (25.83% more), with uncontrolled cache and plugin availability (docs/token-practice.md lines 83-92). The six-attempt selective-policy pilot made zero Context Mode calls (decisions.json line 1163). Its counter text mixes retained-history and conversation scopes (docs/full-stack-convergence.md lines 140-141), so it does not meet the measurement part. On the positive side, both native clients passed a Context Mode/jCodeMunch task with six successful MCP calls (token-native-saturation.md line 18). Its 'default' status belongs to native-process-defaults, which is scoped to the native-clients and instructions-skills layers (decisions.json lines 163-171), not to this layer.
- Repomix (conditional) — Repomix handles selected-file handoff. The clean-CI fixture packs exact selected originals and checks their fidelity ('repomix-source-fidelity-and-selection'). The separate --compress output is structural only (scripts/native_token_ci.py lines 271-294). Its one artifact pair is 3,697 -> 663 tokens, recorded as a 'Lossy outline versus complete pack' (docs/token-practice.md line 112). Its limitation reads 'Compression omits implementation detail and is not adequate evidence for correctness' (catalogs/us-equities/foundation-memory.json line 323). Its lifecycle row accepts the use stage only (docs/token-native-saturation.md line 107). The reviewed snapshot is v1.18.0 at commit 6c5ead0d (foundation-memory.json lines 302-303), while the pin is 1.18.1, whose selected upstream subset passed 148 cases (docs/full-stack-convergence.md lines 124-130). The packet gives its review_status as not_individually_reviewed. It is narrower than RTK or Headroom for general task context.
- TOON (measured_tradeoff) — The packet marks TOON as not adopted, although docs/full-stack-convergence.md line 56 lists 'measured TOON' as layer practice. That conflict is for upstream resolution; I follow the packet. The measured counterexample covers the full catalog of 502 identities. Exact o200k_base counts rose from 59,792 compact-JSON tokens to 66,815 TOON tokens (7,023 more), so the guard kept compact JSON. The native tokenx heuristic had instead reported 13,137 fewer tokens (docs/token-practice.md lines 129-142). One smaller artifact did shrink, from 1,664 to 1,307 (line 108). The CI strict decode round trip passes (scripts/native_token_ci.py lines 297-310). TOON is only useful case by case, per artifact.
- Claude Token Efficient (overlap) — Not adopted. The only review read the README and license (review_depth readme_license_overview) at commit 0d30a6db. It classified the repository as overlaps_established: a short instruction file for reduced verbosity, whose recurring instruction tokens and upstream-only benchmarks prevent a savings claim. There was no installation, inference or native acceptance (catalogs/us-equities/star-audit.json lines 4506-4526). It does not address recoverable originals or separated measurement.

Overturn when: Three checks would change this verdict.

(1) For RTK: `python3 scripts/native_token_ci.py --install --output <new directory>` reports status failed for the rtk component on pin 0.49.0. For example, 'rtk-proxy-exact-stdout' or 'rtk-preserves-both-commit-subjects' fails. The script is at scripts/native_token_ci.py lines 211-235 and 313-361. tests/test_native_token_ci.py stubs rtk_fixture, so it cannot detect this.

(2) For Headroom and ccusage: a new fixture under fixtures/ plus a python3 runner, which does not exist yet. It would need to show a Headroom 0.37.0 or 0.38.0 exact-original recovery failure, or ccusage 20.0.24 mixing counter scopes, or ccusage failing to parse child or attempt usage.

(3) For the whole set: a frozen matched-task comparison, repeated with controlled cache warmth and plugin availability. It would need to show that Context Mode, Repomix or TOON preserves the required facts and raw-original recovery while using less complete provider usage, all attempts and child workers included, than the winning arm on the same task. No repository fixture holds that comparison. It must be built and executed before it can overturn anything.

Open gaps:
- No matched baseline exists for the current native tasks. The only paired trials are one fixed-order pair per client, with opposite signs (Codex -11.26%, Claude +25.83%) (docs/token-practice.md lines 83-92).
- Exact whole-PC lifetime provider savings are unmeasured for every candidate (docs/full-stack-convergence.md lines 147-150).
- Headroom recovery is established on owned synthetic MCP fixtures only. Automatic interception of agent traffic is not configured (catalogs/foundation/decisions.json lines 1214-1217). The pin is 0.37.0 while upstream is v0.38.0 (packet candidate c5, pin_behind_upstream true). I found no retained record that qualifies 0.38.0.
- The repository has no runnable regression fixture for Headroom or Context Mode. The clean CI covers only rtk, qmd, repomix and toon (scripts/native_token_ci.py lines 328-329).
- ccusage child/attempt coverage is unresolved (decisions.json line 1336). Its evidence covers offline parsing and one scoped session, with the use stage only and 0 retained pairs (docs/token-native-saturation.md line 66).
- The foundation gateway RTK/lite previews failed required semantic checks. General CLI acceptance does not repair those failures (decisions.json line 1166).
- RTK's only native artifact pair is one fixed six-commit Git log. Its lifecycle row accepts the use stage only (token-native-saturation.md line 109).
- jCodeMunch and QMD are SOTA components outside this candidate set and were not ranked here.
- Activation on a new host (another WSL or macOS PC) is not established for any winner.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-token-efficiency-20260922; codex: -)

#### Web research (web-research)

- tavily-cli @ 0.1.8 — Each of the three winners has retained native-execution evidence for a different part of the requirement. The scope is bounded, and no candidate was measured against another.

c8, Tavily CLI 0.1.8, covers attributable web search and extraction. evidence/receipts/native-tavily-cli-20260920.json (lines 180-267) records `tvly search` with exit 0 and result_count 4. The search was domain-filtered (`--include-domains developers.openai.com,code.claude.com`, `--max-results 4`, lines 185-192), so its official-source results hold by construction and do not show open-web completeness. The same receipt records `tvly extract` with exit 0, result_count 1 and failed_count 0. A later task in evidence/receipts/native-tavily-session-20260920.json ran an unfiltered IBKR search that returned 3 sources, but intended_adapter_guide_found was false. Direct extraction of the known Nautilus IBKR URL returned 1 result with no failures. Only Search and Extract were exercised.

c1, agent-browser, covers bounded page interaction. evidence/receipts/desktop-cli-workflows.json (lines 4 and 42-61) records a native_model_e2e run in an active Codex Desktop task on fixtures/greeting.html. Snapshot refs @e2/@e3 were used for fill and click, all_exit_codes was 0, the status "Hello, Publication Codex Desktop!" was observed, the screenshot was visually inspected and the owned session was closed. docs/dashboard-rendered-acceptance.md line 28 adds a second observation of a real Dagu browser stream.

c7, OpenResearch at the packet pin 0.2.7, covers discovery and retrieval of public papers. evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json (lines 3-59) records the 2026-09-21 upgrade from 0.2.4 to 0.2.7. After it, `orx --no-telemetry discover keyword 'retrieval augmented generation memory' --limit 3` ran with exit 0 and result_count 3. `orx --no-telemetry paper 2609.05760 --full` ran with exit 0 and returned 69752 UTF-8 bytes. The unchanged upstream ui/tests/markdownTarget.test.mjs passed 7, failed 0 and skipped 0. recipes/native-upgrades-20260921.md line 13 records the same acceptance. An earlier full retrieval (`orx --no-telemetry paper 2608.02583 --full`, 63560 bytes, in evidence/receipts/token-practice-gap-followup-20260920.json lines 195-200) is dated 2026-09-20, before the 0.2.7 promotion, and records no version. It supports the capability but not the 0.2.7 pin.

All three are bounded CLIs with no standing research-agent stack. catalogs/foundation/decisions.json (lines 1048-1138 and 2278-2322) retains each as selection conditional with review_status accepted_within_scope. That is a retained provider or catalog judgment, not my own finding.
- agent-browser @ 0.38.1 — Each of the three winners has retained native-execution evidence for a different part of the requirement. The scope is bounded, and no candidate was measured against another.

c8, Tavily CLI 0.1.8, covers attributable web search and extraction. evidence/receipts/native-tavily-cli-20260920.json (lines 180-267) records `tvly search` with exit 0 and result_count 4. The search was domain-filtered (`--include-domains developers.openai.com,code.claude.com`, `--max-results 4`, lines 185-192), so its official-source results hold by construction and do not show open-web completeness. The same receipt records `tvly extract` with exit 0, result_count 1 and failed_count 0. A later task in evidence/receipts/native-tavily-session-20260920.json ran an unfiltered IBKR search that returned 3 sources, but intended_adapter_guide_found was false. Direct extraction of the known Nautilus IBKR URL returned 1 result with no failures. Only Search and Extract were exercised.

c1, agent-browser, covers bounded page interaction. evidence/receipts/desktop-cli-workflows.json (lines 4 and 42-61) records a native_model_e2e run in an active Codex Desktop task on fixtures/greeting.html. Snapshot refs @e2/@e3 were used for fill and click, all_exit_codes was 0, the status "Hello, Publication Codex Desktop!" was observed, the screenshot was visually inspected and the owned session was closed. docs/dashboard-rendered-acceptance.md line 28 adds a second observation of a real Dagu browser stream.

c7, OpenResearch at the packet pin 0.2.7, covers discovery and retrieval of public papers. evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json (lines 3-59) records the 2026-09-21 upgrade from 0.2.4 to 0.2.7. After it, `orx --no-telemetry discover keyword 'retrieval augmented generation memory' --limit 3` ran with exit 0 and result_count 3. `orx --no-telemetry paper 2609.05760 --full` ran with exit 0 and returned 69752 UTF-8 bytes. The unchanged upstream ui/tests/markdownTarget.test.mjs passed 7, failed 0 and skipped 0. recipes/native-upgrades-20260921.md line 13 records the same acceptance. An earlier full retrieval (`orx --no-telemetry paper 2608.02583 --full`, 63560 bytes, in evidence/receipts/token-practice-gap-followup-20260920.json lines 195-200) is dated 2026-09-20, before the 0.2.7 promotion, and records no version. It supports the capability but not the 0.2.7 pin.

All three are bounded CLIs with no standing research-agent stack. catalogs/foundation/decisions.json (lines 1048-1138 and 2278-2322) retains each as selection conditional with review_status accepted_within_scope. That is a retained provider or catalog judgment, not my own finding.
- openresearch @ 0.2.7 — Each of the three winners has retained native-execution evidence for a different part of the requirement. The scope is bounded, and no candidate was measured against another.

c8, Tavily CLI 0.1.8, covers attributable web search and extraction. evidence/receipts/native-tavily-cli-20260920.json (lines 180-267) records `tvly search` with exit 0 and result_count 4. The search was domain-filtered (`--include-domains developers.openai.com,code.claude.com`, `--max-results 4`, lines 185-192), so its official-source results hold by construction and do not show open-web completeness. The same receipt records `tvly extract` with exit 0, result_count 1 and failed_count 0. A later task in evidence/receipts/native-tavily-session-20260920.json ran an unfiltered IBKR search that returned 3 sources, but intended_adapter_guide_found was false. Direct extraction of the known Nautilus IBKR URL returned 1 result with no failures. Only Search and Extract were exercised.

c1, agent-browser, covers bounded page interaction. evidence/receipts/desktop-cli-workflows.json (lines 4 and 42-61) records a native_model_e2e run in an active Codex Desktop task on fixtures/greeting.html. Snapshot refs @e2/@e3 were used for fill and click, all_exit_codes was 0, the status "Hello, Publication Codex Desktop!" was observed, the screenshot was visually inspected and the owned session was closed. docs/dashboard-rendered-acceptance.md line 28 adds a second observation of a real Dagu browser stream.

c7, OpenResearch at the packet pin 0.2.7, covers discovery and retrieval of public papers. evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json (lines 3-59) records the 2026-09-21 upgrade from 0.2.4 to 0.2.7. After it, `orx --no-telemetry discover keyword 'retrieval augmented generation memory' --limit 3` ran with exit 0 and result_count 3. `orx --no-telemetry paper 2609.05760 --full` ran with exit 0 and returned 69752 UTF-8 bytes. The unchanged upstream ui/tests/markdownTarget.test.mjs passed 7, failed 0 and skipped 0. recipes/native-upgrades-20260921.md line 13 records the same acceptance. An earlier full retrieval (`orx --no-telemetry paper 2608.02583 --full`, 63560 bytes, in evidence/receipts/token-practice-gap-followup-20260920.json lines 195-200) is dated 2026-09-20, before the 0.2.7 promotion, and records no version. It supports the capability but not the 0.2.7 pin.

All three are bounded CLIs with no standing research-agent stack. catalogs/foundation/decisions.json (lines 1048-1138 and 2278-2322) retains each as selection conditional with review_status accepted_within_scope. That is a retained provider or catalog judgment, not my own finding.

Alternatives:
- Playwright CLI (overlap) — Native execution was observed, but the retained evidence is weaker than agent-browser's. In evidence/receipts/token-practice-gap-followup-20260920.json, the first `open <file-url>` failed with initial_file_navigation_exit_code 1 and 'Access to file protocol is blocked' (lines 148-149). browser-open is listed in failed_attempts_retained (lines 106-107). The run recovered only by serving the same fixture bytes over loopback HTTP (line 150), after which 7 HTTP steps succeeded and returned "Hello, Playwright!" (lines 136-137). The fill and click steps targeted fixed CSS selectors (`fill #name`, `click #greet`, `eval document.querySelector('#status')`, lines 142-144), not snapshot refs. Snapshots were only written to files (lines 141 and 145). The run used an existing Chrome and alpha Playwright dependencies 1.64.0-alpha-1789764292000 (lines 19 and 123-125), with no browser download or arbitrary-site test. It has no model-driven run and no second observation. Both tools sit under the same bounded-browser-operations decision in catalogs/foundation/decisions.json (lines 1048-1096). No head-to-head comparison was measured, so it stays an overlapping conditional lane rather than a loser.
- Cua Driver (unqualified) — The packet marks this candidate adopted: true, but its only evidence is a source review. catalogs/landscape/upstream-snapshot.json (added_reviews, around lines 5832-5977) records adoption_status conditional_source_review_only and says it was not installed or adopted. There is no installed or executed Cua task, recovery test, latency/cost comparison, permission-lifecycle check or new-host reproduction. Its role is cross-application desktop computer use, which is wider than the bounded page interaction this layer requires. The record states it did not fail a fair comparison; it is untested, not failed. The external Cua README ref was not opened.
- Crawl4AI (unqualified) — The packet marks this candidate adopted: true, but its only evidence, catalogs/us-equities/star-audit.json (around lines 5960-5981), records decision "alternative" at review_depth readme_license_overview. That entry says no installation, model inference or native acceptance was performed. It frames Crawl4AI as a possible licensed-document ingestion lane that would need to preserve provenance and source restrictions. No retained retrieval result exists.
- Firecrawl MCP (unqualified) — Not adopted. catalogs/us-equities/star-audit.json (around lines 3958-3979) holds only a README/license review, with no installation or native acceptance. It would need an explicit choice to accept hosted/API costs and fetched-content rights. No evidence shows it retrieves attributable sources better than Tavily on the same queries.
- Browser Use (unqualified) — Not adopted. catalogs/us-equities/star-audit.json (around lines 2608-2629) holds only a README/license review, with no installation or native acceptance. It is a browser agent that uses hosted browser/model services, which conflicts with the requirement for no standing research-agent stack. Its credentials and proxies would be separate choices.

Overturn when: Two checks could change this verdict.

1. Browser lane: run agent-browser, Playwright CLI and a challenger (Browser Use or Cua Driver) on fixtures/greeting.html, then on a representative selected external page. A challenger would win if it completes the snapshot/ref fill-click-verify sequence with equal correctness and better session recovery or runtime/cost.

2. Retrieval lane: build a frozen primary-source fixture under fixtures/ with known expected sources, including the retained IBKR miss from evidence/receipts/native-tavily-session-20260920.json (intended_adapter_guide_found false) and an unfiltered open-web query. Then compare Tavily search/extract, OpenResearch discover/paper and a challenger (Firecrawl MCP or Crawl4AI) on attributable-source completeness, extraction failures and total runtime/cost. That fixture does not exist yet, so this check cannot run until it is built.

A regression in a changed release of Tavily, agent-browser or OpenResearch (upstream v0.2.8 against the 0.2.7 pin), measured on the same commands, would also overturn the verdict.

Open gaps:
- No measured comparison exists between any two candidates in this layer. Each winner is qualified only for its own native operation.
- Tavily Map, Crawl and Research are unqualified. The 4-result search that found official sources was domain-filtered (native-tavily-cli-20260920.json lines 190-191). The unfiltered IBKR search missed the intended Nautilus adapter guide (native-tavily-session-20260920.json, intended_adapter_guide_found false). Open-web search completeness is therefore not established.
- The two Tavily records differ. docs/ecosystem/tavily-receipt.json records a 3-result search and says extraction was not exercised. The later evidence/receipts/native-tavily-cli-20260920.json records 4 search results and 1 extraction with 0 failures. Only the latter supports the decision's 'four sources/one extraction' wording.
- Browser-session recovery and compatibility with arbitrary websites are not established for agent-browser or Playwright CLI.
- OpenResearch 0.2.7 has one three-paper discovery, one full-paper retrieval (2609.05760, 69752 bytes) and 7 unchanged Markdown UI tests. The earlier retrieval of 2608.02583 has no recorded version and predates the 0.2.7 promotion. The Rust CLI suite was not run because cargo/rustc were absent. Handling of missing or ambiguous sources and research quality are not assessed. The pin is behind upstream v0.2.8, which is unqualified.
- No frozen primary-source retrieval fixture exists under fixtures/, blueprints/ or tests/ for this layer. The retrieval half of the overturn comparison has no runnable path yet.
- The packet marks c3 (Cua Driver) and c5 (Crawl4AI) as adopted: true. Their own evidence records c3 as conditional_source_review_only ('not installed or adopted') and c5 as decision 'alternative' with no native acceptance. This packet/catalog inconsistency is unresolved.
- docs/full-stack-convergence.md line 55 lists the Web research components as 'Tavily, Context Hub, HF, OpenResearch'. Context Hub and HF are not packet candidates, yet the packet reports sota_components_not_in_candidates as []. Their standing in this layer is unjudged.
- No token savings are claimed or measured.
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-web-research-20260922; codex: -)

#### Workers and task ownership (workers)

- claude-code @ 2.1.278 — The packet requirement (line 574) is: 'Delegate bounded independent work, preserve owned edits and actual failed results, and integrate only after relevant review.' The winners split that requirement between them. No single candidate other than c12 covers all of it.

c12 (Claude native workers) covers delegation, owned edits and retained failures, all from native execution:
- decisions.json `owned-native-child`: one foreground native Opus child repaired its owned file; twelve frozen tests and independent exhaustive checks passed.
- decisions.json `native-child-interruption-recovery`: covers cancellation, same-child continuation, a parent SIGKILL, systemd cgroup containment and finalization.
- worker-recovery/README.md lines 3-17 and 210-235: the accepted inherited-role trial passed in 42.656 s with two CLI invocations, one child, three runs of that same child and one final effect. The 12 frozen sources were unchanged; its frozen inputs are native-exact-read-freeze.json.
- Earlier failed and partial trials are kept (lines 19-26, 115-130, 192-208).
- `native-workflow-graceful-recovery` (a reviewer stop kept a failed child with a null result) is a local integration fixture, not native product evidence (packet lines 499-500).
- docs/foundation-convergence-20260921.md lines 49-54 records one native Workflow in which both workers returned.

c7 (Worktrunk) covers the isolation that keeps owned edits intact:
- decisions.json lines 478-499 (`owned-worktrees`): native create/list/remove passed, and removal of a dirty worktree was refused without loss.
- docs/full-stack-convergence.md lines 124-130: Worktrunk 0.79.0's native old/new comparison confirmed the corrected child working directory, but its Rust suite is unrun.
- The packet labels c7 evidence_kind 'measured_comparison' (line 170).

c11 (Codex native workers) is the second-family native runtime. Its own evidence is narrower:
- docs/full-stack-convergence.md lines 25-34: a five-step read-only native task with eleven tool results and no tool-result failures (Codex 0.155.1, 255,335 consumed tokens).
- Packet line 352 (`native-session-resume`): Codex on Mac resumed the same session to finish an unchanged single checkpoint.
- The returned cross-family review (recipes/claude-codex-foreground-review.md lines 20-29, Codex status 0) ran through the c8 companion path. It is joint c8+c11 review evidence, not c11 evidence alone.
- c11 has no delegated owned-write, crash-recovery or integration fixture, and it is not_individually_reviewed (packet line 386).
- docs/foundation-closure-20260921.md lines 77-78 keeps the existing Codex SDK integration accepted only within its recorded tests; line 83 requires a version change to be qualified.

This is a default based on native execution within the recorded scope, with the c12 graceful-recovery part being local integration. No head-to-head measured comparison against challengers was run.
- worktrunk @ 0.79.0 — The packet requirement (line 574) is: 'Delegate bounded independent work, preserve owned edits and actual failed results, and integrate only after relevant review.' The winners split that requirement between them. No single candidate other than c12 covers all of it.

c12 (Claude native workers) covers delegation, owned edits and retained failures, all from native execution:
- decisions.json `owned-native-child`: one foreground native Opus child repaired its owned file; twelve frozen tests and independent exhaustive checks passed.
- decisions.json `native-child-interruption-recovery`: covers cancellation, same-child continuation, a parent SIGKILL, systemd cgroup containment and finalization.
- worker-recovery/README.md lines 3-17 and 210-235: the accepted inherited-role trial passed in 42.656 s with two CLI invocations, one child, three runs of that same child and one final effect. The 12 frozen sources were unchanged; its frozen inputs are native-exact-read-freeze.json.
- Earlier failed and partial trials are kept (lines 19-26, 115-130, 192-208).
- `native-workflow-graceful-recovery` (a reviewer stop kept a failed child with a null result) is a local integration fixture, not native product evidence (packet lines 499-500).
- docs/foundation-convergence-20260921.md lines 49-54 records one native Workflow in which both workers returned.

c7 (Worktrunk) covers the isolation that keeps owned edits intact:
- decisions.json lines 478-499 (`owned-worktrees`): native create/list/remove passed, and removal of a dirty worktree was refused without loss.
- docs/full-stack-convergence.md lines 124-130: Worktrunk 0.79.0's native old/new comparison confirmed the corrected child working directory, but its Rust suite is unrun.
- The packet labels c7 evidence_kind 'measured_comparison' (line 170).

c11 (Codex native workers) is the second-family native runtime. Its own evidence is narrower:
- docs/full-stack-convergence.md lines 25-34: a five-step read-only native task with eleven tool results and no tool-result failures (Codex 0.155.1, 255,335 consumed tokens).
- Packet line 352 (`native-session-resume`): Codex on Mac resumed the same session to finish an unchanged single checkpoint.
- The returned cross-family review (recipes/claude-codex-foreground-review.md lines 20-29, Codex status 0) ran through the c8 companion path. It is joint c8+c11 review evidence, not c11 evidence alone.
- c11 has no delegated owned-write, crash-recovery or integration fixture, and it is not_individually_reviewed (packet line 386).
- docs/foundation-closure-20260921.md lines 77-78 keeps the existing Codex SDK integration accepted only within its recorded tests; line 83 requires a version change to be qualified.

This is a default based on native execution within the recorded scope, with the c12 graceful-recovery part being local integration. No head-to-head measured comparison against challengers was run.
- codex @ 0.155.1 — The packet requirement (line 574) is: 'Delegate bounded independent work, preserve owned edits and actual failed results, and integrate only after relevant review.' The winners split that requirement between them. No single candidate other than c12 covers all of it.

c12 (Claude native workers) covers delegation, owned edits and retained failures, all from native execution:
- decisions.json `owned-native-child`: one foreground native Opus child repaired its owned file; twelve frozen tests and independent exhaustive checks passed.
- decisions.json `native-child-interruption-recovery`: covers cancellation, same-child continuation, a parent SIGKILL, systemd cgroup containment and finalization.
- worker-recovery/README.md lines 3-17 and 210-235: the accepted inherited-role trial passed in 42.656 s with two CLI invocations, one child, three runs of that same child and one final effect. The 12 frozen sources were unchanged; its frozen inputs are native-exact-read-freeze.json.
- Earlier failed and partial trials are kept (lines 19-26, 115-130, 192-208).
- `native-workflow-graceful-recovery` (a reviewer stop kept a failed child with a null result) is a local integration fixture, not native product evidence (packet lines 499-500).
- docs/foundation-convergence-20260921.md lines 49-54 records one native Workflow in which both workers returned.

c7 (Worktrunk) covers the isolation that keeps owned edits intact:
- decisions.json lines 478-499 (`owned-worktrees`): native create/list/remove passed, and removal of a dirty worktree was refused without loss.
- docs/full-stack-convergence.md lines 124-130: Worktrunk 0.79.0's native old/new comparison confirmed the corrected child working directory, but its Rust suite is unrun.
- The packet labels c7 evidence_kind 'measured_comparison' (line 170).

c11 (Codex native workers) is the second-family native runtime. Its own evidence is narrower:
- docs/full-stack-convergence.md lines 25-34: a five-step read-only native task with eleven tool results and no tool-result failures (Codex 0.155.1, 255,335 consumed tokens).
- Packet line 352 (`native-session-resume`): Codex on Mac resumed the same session to finish an unchanged single checkpoint.
- The returned cross-family review (recipes/claude-codex-foreground-review.md lines 20-29, Codex status 0) ran through the c8 companion path. It is joint c8+c11 review evidence, not c11 evidence alone.
- c11 has no delegated owned-write, crash-recovery or integration fixture, and it is not_individually_reviewed (packet line 386).
- docs/foundation-closure-20260921.md lines 77-78 keeps the existing Codex SDK integration accepted only within its recorded tests; line 83 requires a version change to be qualified.

This is a default based on native execution within the recorded scope, with the c12 graceful-recovery part being local integration. No head-to-head measured comparison against challengers was run.

Alternatives:
- Beads (conditional) — This is native execution, but only for queue semantics. In the decisions.json `dependency-task-queue` entry, native Beads persisted task claims and dependency transitions in one fixture. The same entry says a queue is not worker cancellation, distributed lease correctness or acceptance of a restored task effect, and records the beads stage 'recovery' as 'not_established'. Beads adds ordering on top of workers; it does not delegate, isolate or integrate work itself. Use it only when tasks have real ordering to gate.
- Codex for Claude companion (conditional) — recipes/claude-codex-foreground-review.md lines 20-37 records one foreground /codex:review that returned (Codex status 0; companion 1.0.6 @ db52e28f). This is the review half of the joint c8+c11 cross-family review evidence. The packet's `companion-backend` entry is only partial_acceptance, from one read-only bridge backend task (packet lines 298-306). The companion does not expose Codex model, effort or token totals (recipe line 34). Its SessionEnd hook shuts down the workspace broker without checking which session owns it (lines 41-46). Background and concurrent same-workspace use are unqualified. It is a review lane that invokes c11, not a worker runtime.
- DeerFlow (conditional) — The native evidence covers a different revision and is read-only. blueprints/us-equities/deerflow/research-receipt.json records one embedded invoke_acp_agent research prompt at 42334f26, not the reviewed 656db122. That record says the ACP 'read-only' mode actually maps to workspaceWrite/on-request. native-receipt.json covers model-free discovery only. There is no owned-edit, post-review integration, recovery or matched-comparison evidence. candidate-quality-review.json also records disposition 'conditional' (line 85).
- Deep Agents (conditional) — Source review only, at c9926b1a. candidate-quality-review.json records disposition 'conditional' (line 147); this lane uses the same value. That review records no install, upstream test run, native model operation, matched quality comparison or recovery acceptance. docs/candidate-quality-review-20260921.md line 44 calls it a serious challenger, pending the same source-research task, permission boundaries, recovery and a full cost comparison. The condition cannot be met until it is executed against the frozen worker cases.
- OpenHands SDK (conditional) — Source review only. candidate-quality-review.json records disposition 'conditional' (line 203) for its review at 9bc452eb. Installation, native-account compatibility, interruption/recovery and a matched cost comparison are open. docs/foundation-closure-20260921.md line 86 separately pins version 1.49.2 at tree 856d99d4 and makes it conditional on needing remote or container workers; installing it alone does not improve local review. The two reviewed revisions are not reconciled, and neither was executed.
- OpenHands Agent Canvas (conditional) — Source review only, at 2f8539de. candidate-quality-review.json records disposition 'conditional' (line 261). It is a possible host for the existing native Claude and Codex workers, not a replacement for them. Hosting, account boundaries, persistence and migration are unqualified (docs/candidate-quality-review-20260921.md line 46).
- Microsoft Agent Framework (conditional) — Source review only, at 98a982a1. candidate-quality-review.json records disposition 'conditional' (line 319) and says it closes a source-review coverage gap, not a demonstrated runtime gap. A required application workflow and deployment must be qualified before it is added.
- LangGraph (conditional) — docs/foundation-closure-20260921.md line 85 defers LangGraph 1.2.11 unless an application needs explicit state or checkpoint semantics. docs/foundation-rd-readiness.md line 26 keeps it keep-but-compare. The packet's `agent-sdk-runtime-selection` entry lists it as an unqualified candidate. No execution evidence is retained.
- Temporal (out_of_scope) — Not adopted, and this layer does not currently require cross-host durable ownership. catalogs/us-equities/hosting-source-review.json lines 48-64 records the Temporal server at v1.32.0 with decision 'defer_new_service'. It notes that a production service adds persistence/visibility databases, schema upgrades, payload encryption, auth and archival, and that native start-dev is developer evidence only. That file says to use Temporal only if requirements outgrow existing Dagu, and to choose it or Restate rather than both. Its execution_status is research_only. docs/foundation-closure-20260921.md line 84 separately defers the Temporal Python SDK 1.33.0 until cross-host durable ownership or replay is required. docs/foundation-rd-readiness.md line 26 keeps it keep-but-compare.

Overturn when: The verdict changes in three cases.

1. A real task needs durable multi-host state, approval waits or effect recovery beyond what native workers provide. A challenger (Deep Agents, OpenHands SDK, LangGraph or Temporal) would then have to pass the same frozen cases as the native arms: cancellation, same-identity continuation, parent-crash containment, an unchanged checkpoint with exactly one effect, and owned-file repair verified by frozen tests. The frozen inputs are blueprints/convergence-practice/worker-recovery/native-exact-read-plan.json and native-exact-read-freeze.json, the receipt is native-exact-read-receipt.json, and the owned-file cases are blueprints/convergence-practice/native-worker/plan.json and checks.json. The challenger must match or beat the native Claude and Codex arms, with complete usage retained.

2. c11 is demoted to a review-only role if a Codex native worker run on the native-worker fixture (plan.json/checks.json) fails the owned-file repair.

3. The Worktrunk default changes if a crash-cleanup test removes unrelated or dirty state.

Open gaps:
- Worker reliability is established on one same-host synthetic fixture only. Host or user-manager crash, independent-host recovery, remote provider cancellation, billing cessation and distributed exactly-once effects remain unqualified (worker-recovery/README.md lines 13-17).
- The accepted trial did not exercise the exact rewritten-listing approval, so its success cannot be attributed solely to that rule (worker-recovery/README.md lines 225-227). Complete parent, child and retry usage is unknown (lines 232-235).
- Native Workflow recovery usage views differ by 205,701 tokens, and complete accounting is unresolved (docs/foundation-convergence-20260921.md lines 95-97).
- c11 has no delegated owned-write, crash-recovery or integration fixture of its own. Its review evidence is the joint c8+c11 companion path, and its review_status is not_individually_reviewed. The packet's `lean-workflow-child-routing` entry also says the Codex agent examples have no end-to-end run of their own.
- c12's `native-workflow-graceful-recovery` is a local integration fixture, not an unchanged upstream product test.
- Worktrunk's Rust suite is unrun (docs/full-stack-convergence.md line 130). docs/token-native-saturation.md line 121 lists worktrunk as 'optional' while the packet says confirmed_default. The `owned-worktrees` entry does not separate native Git worktree operations from Worktrunk-specific behavior. Crash cleanup is unproven (packet line 165).
- Beads recovery is 'not_established' (decisions.json `dependency-task-queue`).
- The OpenHands SDK has two unreconciled reviewed revisions: 9bc452eb in candidate-quality-review and 856d99d4 / 1.49.2 in foundation-closure line 86.
- No head-to-head measured comparison exists between native workers and Deep Agents, OpenHands SDK/Agent Canvas, Microsoft Agent Framework, DeerFlow at 656db122, LangGraph or Temporal.
- No worker evidence has been collected on another PC (a new WSL or macOS host).
- codex lane absent for this layer

Lanes: codex_absent (claude: foundation-workers-20260922; codex: -)


### us-equities

| Layer | Group | Verdict status | Winner(s) + pin | Evidence class | Alternatives | Overturn when | Recipe anchor | Platform status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agents-models-workers | foundation-memory | recorded | codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0; foundation-ai-memory @ v2.3.1; foundation-socraticode @ v1.14.0 | native_proven | 19 | The verdict would change in any of these four cases.

1. A preregistered held-out set of financial-document and code qu… | blueprints/us-equities/workers/receipt.json, evidence/receipts/native-memory.json, evidence/receipts/native-rag.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| backtesting-engine | engines-strategies | recorded | nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e); lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f | native_proven | 4 | Re-run the SPY one_zero parity case with the retained harness scripts blueprints/us-equities/engine-nautilus/spy-parity… | blueprints/us-equities/engine/README.md, evidence/receipts/native-nautilus-v2-20260920.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| data-quality-orchestration | agents-operations | recorded | dagu @ v2.16.6; data-pandera @ v0.33.1; source 62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6 | synthetic | 2 | Two checks could change this verdict.

Orchestration (Dagu): a Temporal or other orchestrator arm must repeat the check… | blueprints/us-equities/hosting/README.md, catalogs/landscape/us-equities.json | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| evaluation-experiments | agents-operations | recorded | foundation-agent-retrieval-bench @ v0.2.1; inspect-ai @ inspect-ai0.3.266; source ec4dfc6953784dc45b79de3147530c89868c6e26; data-mlflow @ v3.16.1; source 32792afe5b0183fce10532d3a023f5cfa8612d09 | source_review | 4 | The verdict changes if a new retained receipt shows a better result for another arm:

- **Retrieval evaluation:** c5 (m… | catalogs/landscape/us-equities.json | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| execution-broker | engines-strategies | recorded | adaptive-paper-alpaca-adapter @ 7e7eefe28315f3de3aa4dc75cc8b6524f70829cb (blueprints/us-equities/adaptive-paper); alpaca-py @ 0.44.0 | local_integration | 4 | Reopen the choice in any of these cases:
- A bounded regular-session paper trial of the adaptive lane fails fresh cash/… | blueprints/us-equities/adaptive-paper/receipt.json, blueprints/us-equities/order-contract/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| identity-provenance | data-research | recorded | data-dvc @ 3.67.1; source 356dfa03278058b02df42124f243c2c345329dae | source_review | 8 | The verdict changes on an executed comparison over the existing synthetic fixtures blueprints/us-equities/nanosecond-re… | catalogs/landscape/us-equities.json | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| market-data-reference | data-research | recorded | data-alpaca-py @ v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28; data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a; data-exchange-calendars @ 4.13.2; source dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a | native_proven | 9 | Market data: replay the frozen request contract blueprints/us-equities/alpaca-historical/plan.json against c14 Databent… | blueprints/us-equities/catalyst-provenance/receipt.json, blueprints/us-equities/data/receipt.json, catalogs/landscape/us-equities.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| observability-hosting | agents-operations | recorded | opentelemetry-collector-contrib @ v0.161.0; prometheus @ v3.14.0; restic @ v0.19.1; publisher-signed linux/amd64 release asset | native_proven | 11 | The current evidence already shows SDK result records in Loki only, so the earlier Loki trigger has been replaced. Any … | blueprints/us-equities/hosting/backup/README.md, observability/README.md, observability/backends/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| portfolio-risk | engines-strategies | recorded | skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee | native_proven | 3 | Reopen the verdict if either of two runs on the frozen inputs in blueprints/us-equities/research-evaluation/plan.json t… | blueprints/us-equities/research-evaluation/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| research-factors-ml | engines-strategies | recorded | skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee | native_proven | 23 | Reopen the verdict in either of two cases. First, if `python3 -m unittest discover -s tests -p test_research_evaluation… | blueprints/us-equities/research-evaluation/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| security-supply-chain | agents-operations | recorded | grype @ v0.119.0; syft @ v1.52.0; gitleaks @ v8.30.1 | native_proven | 2 | The verdict changes if either of two things happens. First, a new dated receipt under blueprints/us-equities/supply-cha… | blueprints/us-equities/supply-chain/README.md, blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json, recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| storage-compute | data-research | recorded | data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa | native_proven | 9 | Two checks could change the verdict.

1. Regression check (runnable now in the DuckDB-adopted environment): the DuckDB … | blueprints/us-equities/data/receipt.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |

### us-equities (per-layer narrative)

#### Agents, models and workers (agents-models-workers)

- codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0 — This is my own review of the retained receipts, re-read in the revision round. No provider or TypeSafe judgment was supplied, so none is carried forward. I picked the three adopted candidates whose retained evidence shows native execution closest to the layer requirement: a native worker plus durable memory and exact code retrieval that work across native clients.

(1) c20 codex-native-sdk. blueprints/us-equities/workers/receipt.json (kind native_model_e2e, recorded 2026-09-19) records one successful research task. Evidence: run.status completed (line 25), configured model gpt-6-astra and provider openai, 58410 ms, 135311 total tokens (lines 24-47). It returned exact counts: 3943 engine data points, 3 simulated orders and 23 DeerFlow skills (lines 51-58). The native primitives observed were initialize, model/list, account/rateLimits/read, thread/start, thread/read, turn/start and turn.run (lines 97-105). The same receipt keeps two follow-up scope checks. In both, the native turn completed (native_turn_status completed, lines 135 and 172) but the file-extraction task failed (extraction_task_succeeded false, lines 136 and 173). Across all three native turns: successful_research_tasks 1, blocked_file_extraction_tasks 2, and 204091 total tokens including the failed tasks (lines 208-220). The successful research task depended on Context Mode (c11). It was defined as 'focused Context Mode extraction' (line 50) and ran ctx_execute 3 times and ctx_stats once, while one ctx_execute_file call failed (lines 59-85, 111). So this is evidence of worker plus Context Mode, not of the SDK worker alone. blueprints/us-equities/routing/astra-receipt.json records native_worker_remains_default true. blueprints/us-equities/workers/policy.md and native_worker.py lines 76-79 set a read_only sandbox, ApprovalMode.deny_all and the policy as developer instructions.

(2) c7 ai-memory. evidence/receipts/native-memory.json records native Codex 0.155.1 (gpt-6-astra) and native Claude 2.1.277 (claude-opus-5[1m]) each reading the same scoped durable page through MCP memory_read_page with exit 0. Claude received the cross-client handoff, and 8 and 9 lifecycle observations were recorded. evidence/receipts/native-context-memory.json adds a fresh memory_status call that completed in both clients. Only the Claude call records explicit workspace and project agent-lab (lines 119-124); the Codex entry has no scope fields (lines 92-97). evidence/receipts/desktop-direct-rag.json also reports a direct read of decisions/shared-project-memory.md, but its ai_memory_provenance says this was a coordinator observation. The receipt's source hash supports only the SocratiCode result (lines 27-29), so that read is weaker than hash-bound evidence.

(3) c12 SocratiCode. evidence/receipts/native-rag.json records native Codex and native Claude each running codebase_search (limit 1) and returning the same location: tools/ecosystem/linux-usage-report.cjs lines 2-39, score 0.6429. The index held 35 files and 139 chunks built with real local 2048-dimension embeddings, and automatic add, update and delete watching was observed. evidence/receipts/desktop-direct-rag.json repeats that result, hash-bound, on vLLM 0.25.0.

All three are native executions of narrow tasks. None is a measured comparison, and none covers dated financial sources.
- foundation-ai-memory @ v2.3.1 — This is my own review of the retained receipts, re-read in the revision round. No provider or TypeSafe judgment was supplied, so none is carried forward. I picked the three adopted candidates whose retained evidence shows native execution closest to the layer requirement: a native worker plus durable memory and exact code retrieval that work across native clients.

(1) c20 codex-native-sdk. blueprints/us-equities/workers/receipt.json (kind native_model_e2e, recorded 2026-09-19) records one successful research task. Evidence: run.status completed (line 25), configured model gpt-6-astra and provider openai, 58410 ms, 135311 total tokens (lines 24-47). It returned exact counts: 3943 engine data points, 3 simulated orders and 23 DeerFlow skills (lines 51-58). The native primitives observed were initialize, model/list, account/rateLimits/read, thread/start, thread/read, turn/start and turn.run (lines 97-105). The same receipt keeps two follow-up scope checks. In both, the native turn completed (native_turn_status completed, lines 135 and 172) but the file-extraction task failed (extraction_task_succeeded false, lines 136 and 173). Across all three native turns: successful_research_tasks 1, blocked_file_extraction_tasks 2, and 204091 total tokens including the failed tasks (lines 208-220). The successful research task depended on Context Mode (c11). It was defined as 'focused Context Mode extraction' (line 50) and ran ctx_execute 3 times and ctx_stats once, while one ctx_execute_file call failed (lines 59-85, 111). So this is evidence of worker plus Context Mode, not of the SDK worker alone. blueprints/us-equities/routing/astra-receipt.json records native_worker_remains_default true. blueprints/us-equities/workers/policy.md and native_worker.py lines 76-79 set a read_only sandbox, ApprovalMode.deny_all and the policy as developer instructions.

(2) c7 ai-memory. evidence/receipts/native-memory.json records native Codex 0.155.1 (gpt-6-astra) and native Claude 2.1.277 (claude-opus-5[1m]) each reading the same scoped durable page through MCP memory_read_page with exit 0. Claude received the cross-client handoff, and 8 and 9 lifecycle observations were recorded. evidence/receipts/native-context-memory.json adds a fresh memory_status call that completed in both clients. Only the Claude call records explicit workspace and project agent-lab (lines 119-124); the Codex entry has no scope fields (lines 92-97). evidence/receipts/desktop-direct-rag.json also reports a direct read of decisions/shared-project-memory.md, but its ai_memory_provenance says this was a coordinator observation. The receipt's source hash supports only the SocratiCode result (lines 27-29), so that read is weaker than hash-bound evidence.

(3) c12 SocratiCode. evidence/receipts/native-rag.json records native Codex and native Claude each running codebase_search (limit 1) and returning the same location: tools/ecosystem/linux-usage-report.cjs lines 2-39, score 0.6429. The index held 35 files and 139 chunks built with real local 2048-dimension embeddings, and automatic add, update and delete watching was observed. evidence/receipts/desktop-direct-rag.json repeats that result, hash-bound, on vLLM 0.25.0.

All three are native executions of narrow tasks. None is a measured comparison, and none covers dated financial sources.
- foundation-socraticode @ v1.14.0 — This is my own review of the retained receipts, re-read in the revision round. No provider or TypeSafe judgment was supplied, so none is carried forward. I picked the three adopted candidates whose retained evidence shows native execution closest to the layer requirement: a native worker plus durable memory and exact code retrieval that work across native clients.

(1) c20 codex-native-sdk. blueprints/us-equities/workers/receipt.json (kind native_model_e2e, recorded 2026-09-19) records one successful research task. Evidence: run.status completed (line 25), configured model gpt-6-astra and provider openai, 58410 ms, 135311 total tokens (lines 24-47). It returned exact counts: 3943 engine data points, 3 simulated orders and 23 DeerFlow skills (lines 51-58). The native primitives observed were initialize, model/list, account/rateLimits/read, thread/start, thread/read, turn/start and turn.run (lines 97-105). The same receipt keeps two follow-up scope checks. In both, the native turn completed (native_turn_status completed, lines 135 and 172) but the file-extraction task failed (extraction_task_succeeded false, lines 136 and 173). Across all three native turns: successful_research_tasks 1, blocked_file_extraction_tasks 2, and 204091 total tokens including the failed tasks (lines 208-220). The successful research task depended on Context Mode (c11). It was defined as 'focused Context Mode extraction' (line 50) and ran ctx_execute 3 times and ctx_stats once, while one ctx_execute_file call failed (lines 59-85, 111). So this is evidence of worker plus Context Mode, not of the SDK worker alone. blueprints/us-equities/routing/astra-receipt.json records native_worker_remains_default true. blueprints/us-equities/workers/policy.md and native_worker.py lines 76-79 set a read_only sandbox, ApprovalMode.deny_all and the policy as developer instructions.

(2) c7 ai-memory. evidence/receipts/native-memory.json records native Codex 0.155.1 (gpt-6-astra) and native Claude 2.1.277 (claude-opus-5[1m]) each reading the same scoped durable page through MCP memory_read_page with exit 0. Claude received the cross-client handoff, and 8 and 9 lifecycle observations were recorded. evidence/receipts/native-context-memory.json adds a fresh memory_status call that completed in both clients. Only the Claude call records explicit workspace and project agent-lab (lines 119-124); the Codex entry has no scope fields (lines 92-97). evidence/receipts/desktop-direct-rag.json also reports a direct read of decisions/shared-project-memory.md, but its ai_memory_provenance says this was a coordinator observation. The receipt's source hash supports only the SocratiCode result (lines 27-29), so that read is weaker than hash-bound evidence.

(3) c12 SocratiCode. evidence/receipts/native-rag.json records native Codex and native Claude each running codebase_search (limit 1) and returning the same location: tools/ecosystem/linux-usage-report.cjs lines 2-39, score 0.6429. The index held 35 files and 139 chunks built with real local 2048-dimension embeddings, and automatic add, update and delete watching was observed. evidence/receipts/desktop-direct-rag.json repeats that result, hash-bound, on vLLM 0.25.0.

All three are native executions of narrow tasks. None is a measured comparison, and none covers dated financial sources.

Alternatives:
- Context Mode (conditional) — Native execution is established, and c20's one successful research task depended on it. In that task ctx_execute completed 3 times and ctx_stats once, while one ctx_execute_file call failed the project-root restriction (workers/receipt.json lines 50, 59-85, 111). By client: ctx_execute_file succeeded only in the historical Codex run (native-context-memory.json lines 55-60). The fresh Claude startup shows ctx_execute and memory_status only (lines 113-126). component-history.json line 116 says Claude's file processing 'corrected FILE_PATH to FILE_CONTENT', so Claude ctx_execute_file success is not established. observability/restart-receipt.json shows 11 direct Desktop tools, 14 successful correlated results and doctor PASS. Inside the SDK worker, both ctx_execute_file follow-ups failed: one on the project root, one because approval policy 'never' blocked the scoped override (receipt.json lines 132-206). Context Mode reported estimated_tokens_saved 0 at the captured checkpoint (receipt.json line 94). It is a tool-output extraction lane that the worker uses, not durable project, code or financial-source retrieval. That is why it complements the winner set rather than joining it.
- Serena (overlap) — Exact symbol and reference retrieval ran natively. In Codex, find_symbol and find_referencing_symbols completed, but only status is recorded (native-context-memory.json lines 41-54). For Claude, component-history.json lines 98-104 record 'Actual fetch symbol and 3 references retrieved.' as prose. No path, lines or score was returned, unlike SocratiCode's matched two-client receipt. The installed version is 2.0.0.dev0 @ c6fbd1c5932df2494ffa0020af5a9fbe80b82143, not the packet pin v1.7.0. It complements c12 as the exact-identifier lane.
- foundation-codebase-memory-mcp (overlap) — The static graph search and trace ran from Claude CLI (native-cli-gaps.json) and Codex Desktop (desktop-cli-workflows.json), and both returned collect at lines 91-127 with 4 callees. The native Codex CLI attempt was blocked by usage_limit_exceeded before any tool ran; that is untested, not failed. It is a static-graph fallback with runtime_execution_trace false, and it overlaps c12 and c9.
- Qdrant (overlap) — Qdrant was observed only as the vector store under SocratiCode: collection codebase_72cfa87c5abf, status green, with add, update and delete persisted (native-rag.json; component-history.json external_offline health 200). It was not exercised as an independent retrieval lane, and no financial-document corpus exists.
- vllm (conditional) — This is the embedding runtime under c12. Version 0.25.0 produced 2048 finite normalized floats (native-rag.json; desktop-direct-rag.json active_model_service_version 0.25.0). The 0.29.0 upgrade installed but failed at startup on this WSL host with 'RuntimeError: UVA is not available', and 0.25.0 was restored (vllm-compatibility.json). The upstream v0.30.0 is untested. It is supporting infrastructure, not a worker or retrieval lane.
- omniroute (conditional) — One two-sentence text Responses request completed: 136 total tokens and 3.001 s. It followed an HTTP 400 version rejection and a client 499 disconnect, and neither of those reported provider usage. No tools, hooks, MCP, memory, compaction or worker parity were exercised. astra-receipt.json records native_worker_remains_default true. health-receipt.json is a status-only HTTP 200 check. The gateway strips max_output_tokens, so it provides no enforceable budget.
- codex-acp (conditional) — One embedded ACP research prompt completed: 42345 cumulative tokens and a 31027 ms native turn (research-receipt.json). The 'read-only' mode ID actually maps to workspaceWrite with approvalPolicy on-request, so strict filesystem read-only is not established. native-receipt.json lists the license as Apache-2.0, while the packet says NOASSERTION. The SDK worker (c20) is the route that enforces read_only and deny_all (native_worker.py lines 76-79).
- deerflow (conditional) — Discovery showed a health 200 and 23 skills (native-receipt.json). One invoke_acp_agent embedded call completed with the correct counts (research-receipt.json). No planner, UI, scheduler, persistent service, memory or RAG integration was exercised. It returns only text and discards usage. The run used development commit 42334f26 (backend 2.1.0-rc0), not stable v2.0.0.
- RTK (measured_tradeoff) — This is tool-output compaction, not retrieval or a worker. One six-commit artifact went from 533 to 176 o200k tokens (66.98% removed), while native Claude short commands showed zero estimated reduction (component-history.json; artifact-reductions.json). Automatic Codex RTK was not established.
- foundation-repomix (measured_tradeoff) — It builds lossy handoff bundles. The native CLI ran on selected fixtures (portable-cli-artifacts.json, repomix_contains_selected_paths true), and one real artifact went from 3679 to 645 o200k tokens as a lossy outline (component-history.json). It was not demonstrated in native Claude or native Codex, and it cannot recover sources on its own.
- foundation-toon (out_of_scope) — It is a serialization format, not a worker, memory or retrieval lane. The fixture roundtrip matched (toon_roundtrip_equal true). One real JSON file went from 30414 to 23635 o200k tokens, but a nested fixture grew from 69 to 94 (component-history.json).
- langgraph (unqualified) — The packet card reports only source review and an import smoke test. No agent graph or durable checkpoint was run. InMemorySaver loses state on restart. The GitHub sdk==0.4.4 README is a different package from the langgraph 1.2.11 core pin. It is untested, not failed.
- foundation-pageindex (unqualified) — There is only source review; no financial-document tree-retrieval run was retained. The pin v0.2.18 is behind upstream v0.2.19. The publisher's benchmark is not this system's evaluation. It is untested, not failed.
- Graphiti (unqualified) — There is only source review. No graph deployment, extraction-accuracy check or temporal assertion exists here, and the default examples need model API credentials. It is untested, not failed.
- foundation-pgvector (unqualified) — There is only source review. A build is not activation of the database extension. It shows no demonstrated benefit over the running Qdrant index without a specific SQL integration need.
- foundation-agent-retrieval-bench (unqualified) — It speaks to the measurable-retrieval-quality gap, but no benchmark download or evaluation was performed. Its 427 examples across 25 repositories are code-only, not financial documents. There is only source review.
- loopx-project/loopx (unqualified) — This is a non-adopted newcomer: evidence_refs is empty and there is no pin. The restart- and quota-surviving worker in the packet note is not demonstrated. It is untested, not failed.
- gastownhall/beads (unqualified) — This is a non-adopted newcomer with no retained evidence in this packet. No measured reduction in rework compared with the current coordinator exists.
- jdx/mise (out_of_scope) — This is a non-adopted runtime-pinning tool with no retained evidence. It addresses environment reproduction, not an agent, model, worker or retrieval lane.

Overturn when: The verdict would change in any of these four cases.

1. A preregistered held-out set of financial-document and code queries, run through both native clients at the same context budget, shows a non-winner lane (Serena, codebase-memory-mcp, PageIndex or Graphiti) beating SocratiCode or ai-memory. It must do so on exact-source recall, abstention and measured task cost while keeping scope and source recovery. No such fixture exists yet in the retained evidence.

2. A fresh native rerun of blueprints/us-equities/workers/native_worker.py fails the research task on current pins. Use the documented invocation (blueprints/us-equities/workers/README.md lines 32-36): the SDK environment's python with native_worker.py run and --codex-bin, --codex-home, --workspace, --prompt, a new --receipt path and --turn-deadline-seconds 180. All of these arguments are required by argparse (native_worker.py lines 109-118, 133-134), and the openai_codex import needs the SDK environment, not system python3. The offline command python3 -m unittest tests.test_observability checks only the worker's telemetry and observation helpers, not the turn.

3. A new restart or quota-interruption check on the us-equities worker shows another candidate (LoopX, or DeerFlow with codex-acp) preserving worker state where the native SDK worker loses it. tests/test_worker_recovery.py is only a template: it exercises blueprints/convergence-practice/worker-recovery/stage.py, not the c20 worker.

4. A fresh cross-client ai-memory page read fails on the pinned v2.3.1 or on upstream v2.4.0.

Open gaps:
- Retrieval quality has not been measured independently. Each winner's receipt covers one query or one page. The packet's own limitation reports exact-source recall at three of 8/12 on twelve curated queries, which is a bounded diagnostic, not a holdout.
- No financial-source corpus with as-of, source or tenant metadata has been indexed or retrieved. Everything retrieved was project code or project memory.
- In the SDK worker, all three native turns completed. Only 1 research task succeeded; the 2 ctx_execute_file follow-up extraction tasks failed (receipt.json lines 132-220). ctx_execute already works in SDK plugin transport (3 completions in the successful task). What remains unresolved is file extraction: ctx_execute_file under the project-root restriction, and the scoped override that needs normal native MCP approval under deny_all.
- The c20 success evidence is inseparable from c11: the research task was defined as Context Mode extraction. No retained run shows the SDK worker completing a research task without Context Mode.
- ctx_execute_file success in native Claude is not established; only the historical Codex run records it.
- The ai-memory evidence establishes explicit agent-lab scope only for the Claude memory_status call. The Codex memory_status entry records no scope fields. The Desktop direct page read is a coordinator observation not bound by the receipt hash.
- Model identity for the worker, gateway and ACP runs is configured or reported, not independently attested by the provider. No reroute notifications were collected for the SDK worker.
- No durable queue, scheduler or restart-surviving worker state is demonstrated for the us-equities worker. workers/README.md line 51 says it is not a persistent queue or retry service.
- ai-memory's pin v2.3.1 is behind upstream v2.4.0, and v2.4.0 is untested. The Claude memory receipt used 2.1.277; the later fresh startup used 2.1.278.
- The native Codex CLI run of codebase-memory was blocked by quota (usage_limit_exceeded). That is untested, not a failure.
- Read-only filesystem mode does not restrict inherited MCP or remote-tool mutation authority (receipt.json line 110; workers/README.md lines 53-57).
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-agents-models-workers-20260922; codex: -)

#### Backtesting engine (backtesting-engine)

- nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e) — This is my own review of the retained source files. No TypeSafe inference results were supplied, so none were used. The packet's cards and the refuters' findings are treated as claims, and I checked them against the files.

c5, NautilusTrader 2.0.0rc5
- catalogs/us-equities/runtime-target.json names it as the destination the requirement asks for: engine.decision "selected_destination", tag v2.0.0rc5, source_commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e.
- evidence/receipts/native-nautilus-v2-20260920.json records a native execution of the unchanged upstream synthetic EUR/USD quickstart (source_unchanged true). Accepted runs run-3 and run-4 both exited 0 with 10000 iterations, 902 orders, 902 fills and 451 positions. Ending cash was 1000431.00000 against starting cash of 1000000.00, and all positions were flat. account.csv was byte-identical across the two runs. Runs run-1 and run-2 produced empty reports and are retained as failures. This is native execution, but of synthetic FX, not US equities.
- US-equity scope comes from local integrations, not upstream tests. blueprints/us-equities/engine-nautilus/equity-replay/receipt.json covers 15 AAPL bars with 10 filled orders and reconciled cash: baseline ending cash 99866.60, stress 99855.60.
- blueprints/us-equities/engine-nautilus/spy-parity/verdict.json records the SPY one_zero comparison against the LEAN oracle. It is complete but BLOCKED. Of its 29 checks, 4 FAIL (ordinals 12, 16, 21 and 22). All four are attributed to the unsupported mappings market_on_open_proxy and distributions_and_cash in spy-parity/mapping-manifest.json, and unexplained_residue is 0.0000.
- c5 is the default because of the destination decision and the native engine receipt. It is not the default because of accepted equity parity.

c4, LEAN at 985ef30ad3ac774218c5ac516b4cb0aa2655730f
- The requirement says to keep LEAN as the prior oracle. The receipt that directly supports that role is blueprints/us-equities/historical-simulation/receipt.json. spy-parity/mapping-manifest.json lines 47-54 bind it as oracle.receipt, and runtime-target.json line 102 lists it in accepted_reference_paths.
- It records kind native_cli_e2e, source_pin 985ef30 and status accepted_for_known_stress_exposure_and_margin_mechanics_only.
- Its one_zero command exited 0. That case bought and sold 304 SPY with fills at 323.58 and 291.69, dividends 428.64 and end_cash_usd 90734.080. That end cash is the expected value used in verdict.json checks 21 and 22.
- blueprints/us-equities/engine/receipt.json records a native source build (exit 0, 7855 warnings, 0 errors). It also records the unmodified bundled backtest, which reached Completed with 3943 data points, 3 orders submitted and filled, and an order_list_hash that matches upstream.
- blueprints/us-equities/engine/resolution-receipt.json records the patched rebuild. Its order_list_hash also matched, its launcher advisory audit reported 0 vulnerable packages, and the Alpaca adapter compiled. No broker orders were submitted (broker_orders_submitted 0).

Both winners have native-execution receipts. None of these receipts establishes acceptance of a US-equity strategy, a broker connection or engine parity.
- lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f — This is my own review of the retained source files. No TypeSafe inference results were supplied, so none were used. The packet's cards and the refuters' findings are treated as claims, and I checked them against the files.

c5, NautilusTrader 2.0.0rc5
- catalogs/us-equities/runtime-target.json names it as the destination the requirement asks for: engine.decision "selected_destination", tag v2.0.0rc5, source_commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e.
- evidence/receipts/native-nautilus-v2-20260920.json records a native execution of the unchanged upstream synthetic EUR/USD quickstart (source_unchanged true). Accepted runs run-3 and run-4 both exited 0 with 10000 iterations, 902 orders, 902 fills and 451 positions. Ending cash was 1000431.00000 against starting cash of 1000000.00, and all positions were flat. account.csv was byte-identical across the two runs. Runs run-1 and run-2 produced empty reports and are retained as failures. This is native execution, but of synthetic FX, not US equities.
- US-equity scope comes from local integrations, not upstream tests. blueprints/us-equities/engine-nautilus/equity-replay/receipt.json covers 15 AAPL bars with 10 filled orders and reconciled cash: baseline ending cash 99866.60, stress 99855.60.
- blueprints/us-equities/engine-nautilus/spy-parity/verdict.json records the SPY one_zero comparison against the LEAN oracle. It is complete but BLOCKED. Of its 29 checks, 4 FAIL (ordinals 12, 16, 21 and 22). All four are attributed to the unsupported mappings market_on_open_proxy and distributions_and_cash in spy-parity/mapping-manifest.json, and unexplained_residue is 0.0000.
- c5 is the default because of the destination decision and the native engine receipt. It is not the default because of accepted equity parity.

c4, LEAN at 985ef30ad3ac774218c5ac516b4cb0aa2655730f
- The requirement says to keep LEAN as the prior oracle. The receipt that directly supports that role is blueprints/us-equities/historical-simulation/receipt.json. spy-parity/mapping-manifest.json lines 47-54 bind it as oracle.receipt, and runtime-target.json line 102 lists it in accepted_reference_paths.
- It records kind native_cli_e2e, source_pin 985ef30 and status accepted_for_known_stress_exposure_and_margin_mechanics_only.
- Its one_zero command exited 0. That case bought and sold 304 SPY with fills at 323.58 and 291.69, dividends 428.64 and end_cash_usd 90734.080. That end cash is the expected value used in verdict.json checks 21 and 22.
- blueprints/us-equities/engine/receipt.json records a native source build (exit 0, 7855 warnings, 0 errors). It also records the unmodified bundled backtest, which reached Completed with 3943 data points, 3 orders submitted and filled, and an order_list_hash that matches upstream.
- blueprints/us-equities/engine/resolution-receipt.json records the patched rebuild. Its order_list_hash also matched, its launcher advisory audit reported 0 vulnerable packages, and the Alpaca adapter compiled. No broker orders were submitted (broker_orders_submitted 0).

Both winners have native-execution receipts. None of these receipts establishes acceptance of a US-equity strategy, a broker connection or engine parity.

Alternatives:
- cvxportfolio (unqualified) — Its only evidence is a source-review reference to an external README at pin 1.5.1. That file is outside the repository, and I could not open it. My reasons here come from the packet's card_limitations ('Research simulator is not an order gateway'; 'Prospective workflow is unexecuted'), not from the README. The repository retains no execution, cash reconciliation or LEAN parity case for it, so nothing shows it meets the requirement for broker-specific execution boundaries or reproducible equity accounting. At most it could be a portfolio-policy research layer on top of the engine.
- lumiwealth/lumibot (unqualified) — It is not adopted, and the packet gives it evidence_kind null and evidence_refs []. I reviewed no source for it, so the evidence_class value only reflects that the schema has no 'none' option; the real basis is an unreviewed packet note. That note describes the comparison that would qualify it: the SPY one_zero parity case against LEAN with reconciled cash, plus a paper roundtrip. Neither has been executed. Untested is not the same as failed.
- whchien/ai-trader (unqualified) — It is not adopted, and the packet gives it evidence_kind null and evidence_refs []. I reviewed no source for it; the evidence_class value only reflects the schema's lack of a 'none' option. The packet note describes it at most as a bounded MCP research interface that would not replace the runtime. No execution is recorded.
- nkaz001/hftbacktest (unqualified) — It is not adopted, and the packet gives it evidence_kind null and evidence_refs []. I reviewed no source for it; the evidence_class value only reflects the schema's lack of a 'none' option. The packet note says it models limit-order queue position and latency, which would matter only for intraday execution experiments and not for the current protocol of daily-bar decisions with a t+1 open entry. That scope argument is the packet's claim, not my own. Because the layer scope terms include backtesting and execution-experiment, I record it as unqualified rather than out of scope. No execution is recorded.

Overturn when: Re-run the SPY one_zero parity case with the retained harness scripts blueprints/us-equities/engine-nautilus/spy-parity/run.py and compare.py. Keep the preregistered spy-parity/tolerances.json and mapping-manifest.json, and use the LEAN oracle blueprints/us-equities/historical-simulation/receipt.json (case one_zero, end_cash_usd 90734.080). Also re-run the harness tests in tests/test_spy_parity.py.

Reopen the runtime choice (c5) in either of two cases:
1. A Nautilus-native market-on-open fill and dividend-cash posting mechanism is added, and fill_price_usd, end_cash or native_end_cash still fail with an unattributed residue.
2. A non-adopted engine (for example Lumibot) passes all 29 checks on the same frozen case while Nautilus stays BLOCKED.

Reopen LEAN's oracle role (c4) if a fresh run of the pinned 985ef30 build on the frozen plan.json and input hashes does not reproduce the one_zero values in historical-simulation/receipt.json (fills 323.58 and 291.69, dividends 428.64, end cash 90734.080).

Open gaps:
- SPY/LEAN parity is not accepted. blueprints/us-equities/engine-nautilus/spy-parity/verdict.json is BLOCKED with 4 failed checks: entry fill price delta 0.2900, exit fill price delta -0.4550, reconciled end cash delta -226.4800, and native end cash delta -655.120, which includes -428.64 of unposted distributions. catalogs/us-equities/runtime-target.json reports the next_acceptance status as reported_execution_blocked_review_incomplete.
- The pinned Nautilus wheel has no market-on-open fill mechanism and no dividend-cash posting mechanism. spy-parity/mapping-manifest.json records both mappings as unsupported: AT_THE_OPEN orders are rejected in the probes, and the symbol scan found no dividend crediting. Closing this gap needs either an engine-side mechanism or a newly preregistered mapping.
- The parity verdict covers only the one_zero case on the source host. The stressed and margin cases (one_stress, two_zero, two_stress, adaptive_stress, over_limit) remain blocked by the costs_and_rounding_stress and margin_and_adaptive_state mappings in mapping-manifest.json. evidence/artifacts/comparison-progress-20260922/summary.json line 186 says there is no destination-machine qualification.
- The LEAN oracle's inputs are the bundled upstream LEAN SPY sample, not an acquired vendor dataset (historical-simulation/receipt.json line 27). The receipt's status limits acceptance to known stress exposure and margin mechanics.
- The native Nautilus receipt covers synthetic FX only. It does not cover US-equity corporate actions, a point-in-time universe or historical movers. The AAPL replay (equity-replay/receipt.json) is a local integration with 15 bars and synthetic scheduled close fills, and it avoids corporate-action dates.
- The IBKR adapter has no local broker acceptance: runtime-target.json records local_broker_acceptance not_established. Native broker fault behaviour during a live connection is also unqualified.
- blueprints/us-equities/engine/resolution-receipt.json records that the Alpaca adapter path needs a product-347 entitlement that was not exercised, and that the unmodified adapter build still resolved 2 advisory pairs.
- Nautilus 2.0.0rc5 is a prerelease. The packet's c5 upstream metadata gives v1.231.0 as the latest non-prerelease; I did not verify that against a repository file.
- No strategy has been qualified with causal data, costs and independent reconciliation. Profitability is not established.
- Correction to the packet's group-level limitation that 'SPY/LEAN dividend/cash parity is still planned': the comparison has since been executed and returned BLOCKED (evidence/artifacts/comparison-progress-20260922/summary.json rows[6], lines 171-189). The gap is now an unaccepted result, not an unrun comparison.
- Correction to my earlier proposal: it said no retained LEAN receipt contained the run that produced the one_zero expected values. That was wrong. blueprints/us-equities/historical-simulation/receipt.json is that run, and it is now cited.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-backtesting-engine-20260922; codex: -)

#### Data quality and orchestration (data-quality-orchestration)

- dagu @ v2.16.6 — The layer covers both data quality and orchestration, so I picked one winner for each half. The two do not overlap.

c3, Dagu v2.16.6 (orchestration), has retained native CLI evidence:
- blueprints/us-equities/hosting/receipt.json (kind native_cli_e2e, checked_at 2026-09-19) records a publisher checksum match and a 3-step `dagu start` run that exited 0 and succeeded.
- The same receipt records an exit-23 failure fixture (status failed, dependent step aborted), a native `dagu stop` cancellation (stop_exit 0, status aborted), and prior_history_rows_preserved true after a service restart.
- It shows model_calls 0 and broker_calls 0, and it keeps the earlier schema and env-passthrough failures.
- blueprints/us-equities/research-runtime/receipt.json (native_model_e2e, observed 2026-09-19T16:21:52Z) records the Dagu packet and order_table steps succeeding, with final_validation_exit_codes [0, 0] (lines 36-46).

The Dagu evidence therefore covers supervised processes, failure and cancellation status, retained failed attempts, restart history and no broker authority. It does not cover model telemetry. The Prometheus/Loki usage match in research-runtime/receipt.json (line 112) belongs to a standalone Claude report (line 15; workflow "independent_report" at line 70) that ran outside the Dagu graph. paired_model_workflow_executed is false (line 54), so that match is not Dagu evidence.

c4, pandera 0.33.1 (data quality): the packet's only ref is an upstream README URL, which I could not open. My own source review found a local fail-closed gate described in blueprints/us-equities/data/README.md.
- good-gate-result.json has status pass, row_count 4, all 12 named checks passing, and pins pandera 0.33.1.
- bad-gate-result.json fails exactly valid_trading_session, volume_integral_non_negative, observed_at_not_future, high_ge_max_open_close and unique_symbol_session, matching data/README.md lines 76-78.
- tests/test_promotion_gate.py runs these fixtures only through the gate's isolated venv (lines 1-4 and 90-92).
- Per data/README.md lines 94-117, the paper runtime reads the gate JSON and also hashes the --snapshot file against input_sha256 (promotion_gate_mismatch). The README says the runtime does not import pandera. That is the project's claim; I did not open runner.py.

The pandera evidence is synthetic CSV fixtures only, so the winner-set class is synthetic.
- data-pandera @ v0.33.1; source 62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6 — The layer covers both data quality and orchestration, so I picked one winner for each half. The two do not overlap.

c3, Dagu v2.16.6 (orchestration), has retained native CLI evidence:
- blueprints/us-equities/hosting/receipt.json (kind native_cli_e2e, checked_at 2026-09-19) records a publisher checksum match and a 3-step `dagu start` run that exited 0 and succeeded.
- The same receipt records an exit-23 failure fixture (status failed, dependent step aborted), a native `dagu stop` cancellation (stop_exit 0, status aborted), and prior_history_rows_preserved true after a service restart.
- It shows model_calls 0 and broker_calls 0, and it keeps the earlier schema and env-passthrough failures.
- blueprints/us-equities/research-runtime/receipt.json (native_model_e2e, observed 2026-09-19T16:21:52Z) records the Dagu packet and order_table steps succeeding, with final_validation_exit_codes [0, 0] (lines 36-46).

The Dagu evidence therefore covers supervised processes, failure and cancellation status, retained failed attempts, restart history and no broker authority. It does not cover model telemetry. The Prometheus/Loki usage match in research-runtime/receipt.json (line 112) belongs to a standalone Claude report (line 15; workflow "independent_report" at line 70) that ran outside the Dagu graph. paired_model_workflow_executed is false (line 54), so that match is not Dagu evidence.

c4, pandera 0.33.1 (data quality): the packet's only ref is an upstream README URL, which I could not open. My own source review found a local fail-closed gate described in blueprints/us-equities/data/README.md.
- good-gate-result.json has status pass, row_count 4, all 12 named checks passing, and pins pandera 0.33.1.
- bad-gate-result.json fails exactly valid_trading_session, volume_integral_non_negative, observed_at_not_future, high_ge_max_open_close and unique_symbol_session, matching data/README.md lines 76-78.
- tests/test_promotion_gate.py runs these fixtures only through the gate's isolated venv (lines 1-4 and 90-92).
- Per data/README.md lines 94-117, the paper runtime reads the gate JSON and also hashes the --snapshot file against input_sha256 (promotion_gate_mismatch). The README says the runtime does not import pandera. That is the project's claim; I did not open runner.py.

The pandera evidence is synthetic CSV fixtures only, so the winner-set class is synthetic.

Alternatives:
- Temporal (conditional) — The only evidence is an upstream README URL that I did not open (source_review). No local execution, failure, cancellation or restart receipt exists. blueprints/us-equities/hosting.md lines 41-42 say Temporal is not a prerequisite for the completed native proof and was not added. The candidate card notes that unlimited default activity retries are unsafe for quota errors or uncertain broker writes. It stays conditional on a demonstrated in-flight or durable-workflow requirement that Dagu fails. It is untested, not failed.
- modal (unqualified) — The only evidence is a PyPI URL that I did not open (source_review). The card says `modal run` executes paid cloud code and was not run, and that native subscription credentials must not be assumed to belong in cloud containers. There is no local receipt for managed compute, identity, cancellation or usage accounting. It is untested, not failed.

Overturn when: Two checks could change this verdict.

Orchestration (Dagu): a Temporal or other orchestrator arm must repeat the checks in blueprints/us-equities/hosting/receipt.json against blueprints/us-equities/hosting/research-evidence.yaml. Those checks are the exit-23 failure fixture, native cancellation and history after a service restart. The arm must also resume an in-flight step after a host or service kill, which Dagu's receipt does not prove. It overturns the verdict only if the candidate passes all of these, with no duplicate effect owners and no broker authority, while Dagu fails the in-flight check.

Data quality (pandera): run `python3 -m unittest tests/test_promotion_gate.py` with the gate's isolated venv present or PROMOTION_GATE_PYTHON set. The FixtureGateRuns class must report zero skips; a skipped class counts as not run, not as a pass. It overturns the verdict if the gate misclassifies any fixture in blueprints/us-equities/data/fixtures/, or if a real-schema snapshot contains a seeded defect that the pandera gate passes and an alternative validator catches.

Open gaps:
- Dagu: resuming an in-flight step after a restart or host loss is not established. The restart check proves only that completed history is preserved.
- Dagu: no model step has run under Dagu with matching telemetry. paired_model_workflow_executed is false and the Codex allowance was at 100 percent. The Prometheus/Loki match belongs to a standalone Claude report (research-runtime/receipt.json lines 15, 54, 70, 112). There is also no model-worker queue and no continuous off-host hosting.
- The auth state conflicts between sources. hosting/receipt.json records Basic auth, with anonymous requests getting 401. hosting.md line 3 still says 'authenticated local research run history', and research-runtime/receipt.json line 56 has private_auth_preserved true. The current hosting/README.md says auth.mode is none and anonymous API reads return 200. The receipts and hosting.md therefore predate the current auth configuration.
- Pandera: validated only on synthetic CSV fixtures. There is no production bars/universe ingest, and the duckdb:// input path is source-only.
- The fixture tests in tests/test_promotion_gate.py are skipped whenever the gate venv is absent, so a green run on another host does not establish that fixtures are classified correctly.
- The claim that the paper runtime never imports pandera comes from the project README (data/README.md lines 94-96). I did not verify it in runner.py.
- Neither Temporal nor Modal has any local execution evidence, so they are untested, not failed.
- Local Dagu subprocess cancellation is not the same as cancelling a provider request (hosting.md lines 47-48).
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-data-quality-orchestration-20260922; codex: -)

#### Evaluation and experiments (evaluation-experiments)

- foundation-agent-retrieval-bench @ v0.2.1 — I judged the candidates against the layer title and its layer_scope_terms: evaluation, agent-evaluation, experiment-tracking, progressive-evaluation and validation-reporting. Together the three winners cover retrieval evaluation, agent-task evaluation and experiment tracking. Only c7 has executed evidence.

c7 (agent-retrieval-bench v0.2.1) has two retained runs of different kinds.

- **Upstream replay (native, recorded host macOS arm64).** blueprints/convergence-practice/arb-trace2code/README.md (lines 3-11, 28 and 36) and receipt.json record an offline replay of the complete 101-case v2_trace2code release. The replay is code-file retrieval from failure traces. It used the unmodified lexical and BM25 evaluators at commit b487f3866cc13dd971819cb902517a6a50282404. Results were lexical Recall@5 0.343234 / MRR 0.207453 and BM25 Recall@5 0.222772 / MRR 0.163848. 15 upstream tests passed.
- **Local integration (no host recorded).** blueprints/convergence-practice/local-fixture/evaluation-receipt.json has kind executed_frozen_public_document_retrieval_fixture (line 67). It ranked 15 public documents from the native-agent-stack repository at base commit bf99d340 against 24 source-authored queries: 20 positive and 4 no-gold. BM25 MRR was 0.9666666666666666 and Recall@1 0.95; lexical MRR was 0.9 and Recall@1 0.8. The run had provider_calls 0 and execution_exit_code 0. This receipt records no host or OS, and it has no abstention metric (lines 43, 70).

Neither run evaluates financial documents.

c2 (inspect-ai 0.3.266) is the candidate whose role, "Programmable task/solver/scorer evaluations", best fits evaluating an agent's task outcome. c6 (phoenix) is also tagged agent-evaluation, but as a trace-inspection workspace. c7 evaluates retrieval only. c2's evidence is source review only: catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json records installation_performed false and model_calls 0 (lines 124-125).

c1 (data-mlflow v3.16.1, commit 32792afe5b0183fce10532d3a023f5cfa8612d09) covers experiment tracking with an exact source pin. It is source review only; catalogs/us-equities/data-research.json lines 779-817 mark its sqlite workflow as prospective.

The weakest class in the winner set is therefore source_review.
- inspect-ai @ inspect-ai0.3.266; source ec4dfc6953784dc45b79de3147530c89868c6e26 — I judged the candidates against the layer title and its layer_scope_terms: evaluation, agent-evaluation, experiment-tracking, progressive-evaluation and validation-reporting. Together the three winners cover retrieval evaluation, agent-task evaluation and experiment tracking. Only c7 has executed evidence.

c7 (agent-retrieval-bench v0.2.1) has two retained runs of different kinds.

- **Upstream replay (native, recorded host macOS arm64).** blueprints/convergence-practice/arb-trace2code/README.md (lines 3-11, 28 and 36) and receipt.json record an offline replay of the complete 101-case v2_trace2code release. The replay is code-file retrieval from failure traces. It used the unmodified lexical and BM25 evaluators at commit b487f3866cc13dd971819cb902517a6a50282404. Results were lexical Recall@5 0.343234 / MRR 0.207453 and BM25 Recall@5 0.222772 / MRR 0.163848. 15 upstream tests passed.
- **Local integration (no host recorded).** blueprints/convergence-practice/local-fixture/evaluation-receipt.json has kind executed_frozen_public_document_retrieval_fixture (line 67). It ranked 15 public documents from the native-agent-stack repository at base commit bf99d340 against 24 source-authored queries: 20 positive and 4 no-gold. BM25 MRR was 0.9666666666666666 and Recall@1 0.95; lexical MRR was 0.9 and Recall@1 0.8. The run had provider_calls 0 and execution_exit_code 0. This receipt records no host or OS, and it has no abstention metric (lines 43, 70).

Neither run evaluates financial documents.

c2 (inspect-ai 0.3.266) is the candidate whose role, "Programmable task/solver/scorer evaluations", best fits evaluating an agent's task outcome. c6 (phoenix) is also tagged agent-evaluation, but as a trace-inspection workspace. c7 evaluates retrieval only. c2's evidence is source review only: catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json records installation_performed false and model_calls 0 (lines 124-125).

c1 (data-mlflow v3.16.1, commit 32792afe5b0183fce10532d3a023f5cfa8612d09) covers experiment tracking with an exact source pin. It is source review only; catalogs/us-equities/data-research.json lines 779-817 mark its sqlite workflow as prospective.

The weakest class in the winner set is therefore source_review.
- data-mlflow @ v3.16.1; source 32792afe5b0183fce10532d3a023f5cfa8612d09 — I judged the candidates against the layer title and its layer_scope_terms: evaluation, agent-evaluation, experiment-tracking, progressive-evaluation and validation-reporting. Together the three winners cover retrieval evaluation, agent-task evaluation and experiment tracking. Only c7 has executed evidence.

c7 (agent-retrieval-bench v0.2.1) has two retained runs of different kinds.

- **Upstream replay (native, recorded host macOS arm64).** blueprints/convergence-practice/arb-trace2code/README.md (lines 3-11, 28 and 36) and receipt.json record an offline replay of the complete 101-case v2_trace2code release. The replay is code-file retrieval from failure traces. It used the unmodified lexical and BM25 evaluators at commit b487f3866cc13dd971819cb902517a6a50282404. Results were lexical Recall@5 0.343234 / MRR 0.207453 and BM25 Recall@5 0.222772 / MRR 0.163848. 15 upstream tests passed.
- **Local integration (no host recorded).** blueprints/convergence-practice/local-fixture/evaluation-receipt.json has kind executed_frozen_public_document_retrieval_fixture (line 67). It ranked 15 public documents from the native-agent-stack repository at base commit bf99d340 against 24 source-authored queries: 20 positive and 4 no-gold. BM25 MRR was 0.9666666666666666 and Recall@1 0.95; lexical MRR was 0.9 and Recall@1 0.8. The run had provider_calls 0 and execution_exit_code 0. This receipt records no host or OS, and it has no abstention metric (lines 43, 70).

Neither run evaluates financial documents.

c2 (inspect-ai 0.3.266) is the candidate whose role, "Programmable task/solver/scorer evaluations", best fits evaluating an agent's task outcome. c6 (phoenix) is also tagged agent-evaluation, but as a trace-inspection workspace. c7 evaluates retrieval only. c2's evidence is source review only: catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json records installation_performed false and model_calls 0 (lines 124-125).

c1 (data-mlflow v3.16.1, commit 32792afe5b0183fce10532d3a023f5cfa8612d09) covers experiment tracking with an exact source pin. It is source review only; catalogs/us-equities/data-research.json lines 779-817 mark its sqlite workflow as prospective.

The weakest class in the winner set is therefore source_review.

Alternatives:
- data-river (conditional) — Covers progressive evaluation, but only for online or streaming learning. Its own card says immediate synthetic labels are invalid for financial online evaluation and require modelling of delayed labels, corrections and restarts. Nothing was executed (catalogs/us-equities/data-research.json lines 1304-1340).
- foundation-mteb (unqualified) — An embedding and retrieval evaluator that has never been run here; its commands are prospective. The 2.21.0 pin is behind upstream 2.21.6, and the reviewed commit is a default-branch snapshot that can differ from the tag. Unlike c7, it has no retained run on the frozen local fixture (catalogs/us-equities/foundation-memory.json lines 1210-1245).
- phoenix (conditional) — Tagged for both the observability and agent-evaluation layers, as a trace UI plus evaluation workspace, so it overlaps the observability layer. Server launch is prospective, no app has been instrumented and no judge calls were made. The catalog card gives the license as Elastic-2.0 with restrictions, while the packet's upstream metadata says NOASSERTION. Auto-instrumentation can capture prompt and tool contents (catalogs/us-equities/agents-operations.json lines 1239-1280).
- promptfoo (conditional) — Not a candidate in this packet; it appears in the foundation quality-evaluation packet. Its us-equities card (agents-operations.json lines 1321-1361) tags it agent-evaluation and security, with evidence_level source_review and prospective commands. A retained execution does exist. evidence/artifacts/promptfoo-nemotron-upstream-20260921/qualification.json records a promptfoo 0.123.1 eval with exit_code 0: 1 case passed, 0 failed, 0 errors, with retained recovery and failure notes. That run was NVIDIA's four-query embedding-retrieval example against a local vLLM endpoint with a locally authored assertion. Its own limitations say it is not held-out qualification, and it evaluates no agent task. It is recorded in challenger_preferred and is not promoted.

Overturn when: The verdict changes if a new retained receipt shows a better result for another arm:

- **Retrieval evaluation:** c5 (mteb) runs on the frozen input blueprints/convergence-practice/local-fixture/fixture.json with the same corpus-manifest.json hashes and cutoffs 1/3/5. The run must exit 0 with Recall@1/3/5 and full-ranking MRR that can be recomputed from the ranked paths. It must either beat c7's ARB BM25 result (MRR 0.9666666666666666) or add abstention coverage for the 4 no-gold queries.
- **Agent evaluation:** the matched comparison of c2 inspect-ai and promptfoo on that fixture, as described in challenger_preferred, has one of two outcomes. Either c2 fails its recorded next acceptance (mock model, deterministic scoring, bounded concurrency/retries, retained failure log, interruption and resume, 0 provider calls), or promptfoo meets the same acceptance while c2 does not. In either case c2 is replaced.
- **Experiment tracking:** a c1 local sqlite run fails to record the fixture receipt's parameters, metrics and artifact hashes. c1 is then demoted in favour of a measured alternative.

Open gaps:
- lane claude prefers non-adopted promptfoo (https://github.com/promptfoo/promptfoo): requires A matched run over the frozen fixture blueprints/convergence-practice/local-fixture/fixture.json (fixture_sha256 aea5e9616fb19eb1d2fd58ecfadf88ff087d7d2e79b4a70bc9f88207af9d0402, with corpus-manifest.json) using a mock model and 0 provider calls, with two arms: c2 inspect-ai 0.3.266 and promptfoo 0.123.1. Each arm must score deterministically under bounded concurrency/retries, retain a failure log and survive interruption and resume. Record the exit code, per-case scores recomputable from rankings.json, and resume success. The comparison is decided on those observed results; lane agreement does not count.
- inspect-ai, mlflow (both cards), river, mteb and phoenix have no retained execution; their evidence is source review only.
- c7's upstream replay is code-file retrieval on a recorded macOS arm64 host. Its local-fixture run is public-document retrieval with no host recorded. Neither covers financial documents, agent task outcomes, abstention, or a recorded run on this WSL host.
- promptfoo's retained run is a four-query embedding-retrieval example with a locally authored assertion. The record does not name the host OS; it shows only a local 127.0.0.1 vLLM endpoint. It does not establish agent-task evaluation.
- The packet requirement text is shared by the group: native identity, supervising owned processes, and keeping research workers away from broker execution. No candidate has evidence of process supervision or of withholding broker authority.
- No candidate has retained evidence for validation-reporting, or for progressive evaluation with delayed labels on financial data.
- Pin discrepancies remain unresolved. c7's packet evidence_ref is snapshot 07014c9, while the executed release commit is b487f38 (the receipt records an identical source tree). For c2, the packet's upstream.latest 'release/2025-11-28' does not match the PyPI pin 0.3.266. For c6, upstream.latest refers to a different package (@arizeai/phoenix-mcp@4.3.13).
- c6's license conflicts between sources: the packet says NOASSERTION and the catalog card says Elastic-2.0.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-evaluation-experiments-20260922; codex: -)

#### Execution and broker adapters (execution-broker)

- adaptive-paper-alpaca-adapter @ 7e7eefe28315f3de3aa4dc75cc8b6524f70829cb (blueprints/us-equities/adaptive-paper) — Picked on retained evidence, not on project claims.

c5 (adaptive-paper-alpaca-adapter) is one of two broker-specific execution boundaries in the selected NautilusTrader 2.0.0rc5 destination; c7, the native IBKR adapter, is the other. c5 is the only one with retained local-integration evidence inside that destination. c7 has local_broker_acceptance "not_established" (catalogs/us-equities/runtime-target.json lines 46-49).

What the c5 receipt shows (blueprints/us-equities/adaptive-paper/receipt.json):
- Engine NautilusTrader 2.0.0rc5 (pin 1b0a49d2...) with alpaca-py 0.44.0 (pin cc4cb3b7...).
- Status "local_integration_passed_new_broker_trial_pending".
- Full repository suite: run 895 / passed 893 / skipped 2.
- 42 unchanged upstream Nautilus adapter-template tests passed; the receipt says these are "not Alpaca broker E2E".
- native_capacity is a synthetic-broker run: 180 submissions, 90 roundtrips, broker_connections 0, paper_orders 0.
- broker_readiness is "not_started" (regular_session_window_unavailable).
- The later changes_since blocks are evidence class SYN; the last reports "Ran 1729 tests / OK (skipped=5)".

blueprints/us-equities/adaptive-paper/README.md describes c5's deterministic risk and ledger boundaries: fsynced SQLite intents, stable IDs, no blind retry, a shared 200/minute budget with a 180/minute submission ceiling, and a whole-share native Equity model.

c4 is alpaca-py 0.44.0, the SDK that carries c5's quotes, order updates and paper REST requests. c1 has the same repository and commit and is recorded as an overlap. This SDK is the only one with observed paper order execution:
- blueprints/us-equities/paper-e2e-20260921/readiness.json line 6 records sdk alpaca-py 0.44.0 at source_commit cc4cb3b7ba50ae250e621983c2779047fb16bb28.
- blueprints/us-equities/paper-e2e-20260921/paper-receipt.json (evidence_kind native_alpaca_paper) records 2 write attempts: an SPY buy filled at 770.70 and a sell filled at 770.62, with realized_gross_pnl_usd "-0.08".
- A separate fresh reconciliation made 5 GETs: positions 0, open_orders 0, cash_delta_usd "-0.08", which matches the reported PnL.
- Completed-trial recovery made 0 additional writes.
- catalogs/us-equities/runtime-target.json names this receipt as the Alpaca native_paper_receipt.

That smoke ran through blueprints/us-equities/alpaca-paper/paper_runner.py, not through Nautilus. It is native evidence for the SDK path, not for the c5 adapter.

The winner set's weakest class is local_integration (c5).
- alpaca-py @ 0.44.0 — Picked on retained evidence, not on project claims.

c5 (adaptive-paper-alpaca-adapter) is one of two broker-specific execution boundaries in the selected NautilusTrader 2.0.0rc5 destination; c7, the native IBKR adapter, is the other. c5 is the only one with retained local-integration evidence inside that destination. c7 has local_broker_acceptance "not_established" (catalogs/us-equities/runtime-target.json lines 46-49).

What the c5 receipt shows (blueprints/us-equities/adaptive-paper/receipt.json):
- Engine NautilusTrader 2.0.0rc5 (pin 1b0a49d2...) with alpaca-py 0.44.0 (pin cc4cb3b7...).
- Status "local_integration_passed_new_broker_trial_pending".
- Full repository suite: run 895 / passed 893 / skipped 2.
- 42 unchanged upstream Nautilus adapter-template tests passed; the receipt says these are "not Alpaca broker E2E".
- native_capacity is a synthetic-broker run: 180 submissions, 90 roundtrips, broker_connections 0, paper_orders 0.
- broker_readiness is "not_started" (regular_session_window_unavailable).
- The later changes_since blocks are evidence class SYN; the last reports "Ran 1729 tests / OK (skipped=5)".

blueprints/us-equities/adaptive-paper/README.md describes c5's deterministic risk and ledger boundaries: fsynced SQLite intents, stable IDs, no blind retry, a shared 200/minute budget with a 180/minute submission ceiling, and a whole-share native Equity model.

c4 is alpaca-py 0.44.0, the SDK that carries c5's quotes, order updates and paper REST requests. c1 has the same repository and commit and is recorded as an overlap. This SDK is the only one with observed paper order execution:
- blueprints/us-equities/paper-e2e-20260921/readiness.json line 6 records sdk alpaca-py 0.44.0 at source_commit cc4cb3b7ba50ae250e621983c2779047fb16bb28.
- blueprints/us-equities/paper-e2e-20260921/paper-receipt.json (evidence_kind native_alpaca_paper) records 2 write attempts: an SPY buy filled at 770.70 and a sell filled at 770.62, with realized_gross_pnl_usd "-0.08".
- A separate fresh reconciliation made 5 GETs: positions 0, open_orders 0, cash_delta_usd "-0.08", which matches the reported PnL.
- Completed-trial recovery made 0 additional writes.
- catalogs/us-equities/runtime-target.json names this receipt as the Alpaca native_paper_receipt.

That smoke ran through blueprints/us-equities/alpaca-paper/paper_runner.py, not through Nautilus. It is native evidence for the SDK path, not for the c5 adapter.

The winner set's weakest class is local_integration (c5).

Alternatives:
- NautilusTrader (native IBKR socket adapter) (conditional) — This is a broker-specific boundary inside the selected destination, and runtime-target.json names it the IBKR selected_path (lines 46-49). It has no local broker evidence: local_broker_acceptance is "not_established". Its limitation says adapter installation does not establish socket access, paper order behavior, cancellation races or reconnect reconciliation. The packet's limitations for c7 add that no local paper or live session has been run against this adapter. Its only evidence_ref is external documentation (nautilustrader.io), which this lane did not open. It stays conditional on a first IBKR paper session with reconciliation. It is untested, not failed.
- LEAN Alpaca brokerage (conditional) — blueprints/us-equities/engine/resolution-receipt.json shows native dotnet builds of the pinned adapter (1973f616...). The unmodified build had exit 0 with 2 advisory pairs; the source-integrated build had exit 0 with 0 advisory pairs. Its remaining_external_boundary is "not_exercised_requires_operator_entitlement_and_broker_authorization", with broker_orders_submitted 0. The bundled backtest used a brokerage_model that is "Unchanged upstream default; not Alpaca". The native class covers compilation only, not initialization, connectivity or reconciliation. The adapter serves the legacy LEAN runtime, not the selected Nautilus destination, and the LEAN oracle requirement does not depend on this brokerage.
- hkuds/vibe-trading (unqualified) — Not adopted, with no retained evidence_refs, pin or upstream metadata. The packet note describes a proposed comparison against the existing Alpaca lifecycle cases, not an executed result. Nothing establishes that it beats the current adapter.
- pydantic/pydantic (unqualified) — Not adopted, with no retained evidence_refs. The packet note proposes a strict typed order-intent schema but records no run. blueprints/us-equities/order-contract/README.md already describes a dependency-free offline boundary that rejects unknown fields, floats, booleans, duplicate keys and fractional quantities, with nine focused tests reported passed. Nothing retained shows malformed intents that this boundary accepts and a pydantic schema would reject.

Overturn when: Reopen the choice in any of these cases:
- A bounded regular-session paper trial of the adaptive lane fails fresh cash/position reconciliation, submits duplicate writes, or breaches its frozen numeric limits. The trial is python3 blueprints/us-equities/adaptive-paper/runner.py paper, then recover, with the required --env-file (the broker credential file) and --output. The paper command also needs a passing, hash-matched --gate-result and --snapshot from blueprints/us-equities/data/promotion_gate.py.
- tests/test_alpaca_paper.py, tests/test_adaptive_paper_safety.py, tests/test_adaptive_paper_recovery.py or tests/test_adaptive_paper_transport.py fails in the pinned runtime.
- An IBKR paper session through the Nautilus adapter (c7) passes ownership, partial/cancel/reconnect and reconciliation cases with evidence that exceeds the Alpaca lane. That would promote c7 into the winner set.
- A challenger records fewer failures on the same lifecycle fixtures: the c2 sdk_order_gate/reconciliation, or a c3 strict schema over tests/test_order_contract.py.

Open gaps:
- The Nautilus-integrated adaptive Alpaca adapter (c5) has placed no broker order. broker_readiness is "not_started", and native_capacity used broker_connections 0 and paper_orders 0 (adaptive-paper/receipt.json).
- The only observed paper orders (2 writes, one SPY roundtrip) went through blueprints/us-equities/alpaca-paper/paper_runner.py, not through the Nautilus LiveNode path.
- No native in-flight fault has been exercised: partial fill, cancel, reject, disconnect, crash or an uncertain order. The paper-e2e README reports 27 synthetic lifecycle tests for these paths, and runtime-target.json lists in-flight native failure cases as open.
- IBKR local broker acceptance is not_established (runtime-target.json lines 46-49), so no IBKR paper session exists.
- alpaca-py 0.44.0 serializes qty and limit_price as floats and drops advanced_instructions (order-contract/README.md). Exact decimal preservation at the wire has not been established.
- Continuous operation, Elite 1000/minute throughput, SIP entitlement and the LEAN SPY dividend/cash parity are not established. runtime-target.json reports the latest parity comparison as BLOCKED.
- The G-f cancel-then-replace and gap-risk stop features are opt-in SYN only, with no broker-observed receipt (receipt.json changes_since_g_f_round8).
- The adaptive paper command is additionally gated on a passing promotion-gate result (receipt.json; runner.py lines 1029-1036). No retained evidence shows that gate passing for a paper trial.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-execution-broker-20260922; codex: -)

#### Identity, provenance and lineage (identity-provenance)

- data-dvc @ 3.67.1; source 356dfa03278058b02df42124f243c2c345329dae — The layer is "Identity, provenance and lineage". Its scope terms include data-versioning, reproducibility and snapshot-store, and its requirement asks for exact reproducible analytical snapshots. DVC (c2) is the adopted candidate aimed most directly at that. Its catalog card at catalogs/us-equities/data-research.json (entry data-dvc, lines 692-736) lists the layers data-versioning and reproducibility. It says DVC "pins exact raw/curated snapshots and preprocessing dependencies" (line 704). It also states two limits: content hashes prove identity, not point-in-time correctness (line 724), and the snapshot must already carry knowledge-cutoff metadata (line 721). DVC can therefore wrap the project's snapshot contract but cannot replace it. The evidence class is source_review only. The packet evidence ref is the upstream README at commit 356dfa03, which this lane could not open, and the card's native_workflow is labelled "Prospective and UNEXECUTED" (line 711). DVC has not been run here. The only executed local evidence for this layer comes from two project-local blueprints, and neither uses DVC or any other candidate. The first is blueprints/us-equities/nanosecond-replay/receipt.json (kind native_cli_e2e: six exit_code 0 entries and four expected exit_code 2 entries). The second is blueprints/us-equities/point-in-time/receipt.json (kind native_cli_e2e, observed 2026-09-19, DuckDB 1.5.5: seven exit_code 0 entries and four exit_code 2 entries, synthetic=true, entitlement_verified=false). Both materialize synthetic hash-manifest snapshots and select them only against a pinned digest (nanosecond-replay README lines 65-71). They define the contract a DVC wrapper would have to preserve; they are not evidence for DVC. This revision drops OpenLineage (c5) from the winner set. Row 49 of blueprints/us-equities/architecture/README.md limits OpenLineage to "demonstrated transformation/lineage needs". The c5 card itself says OpenLineage is "not a persistent lineage server, scheduler or dataset version store". No source read here shows a lineage need that the existing manifest, source hashes and SQL hashes fail to meet.

Alternatives:
- data-openlineage (conditional) — OpenLineage matches the data-lineage and metadata-events scope terms. blueprints/us-equities/architecture/README.md line 49 admits it only for demonstrated transformation or lineage needs, and adds that lineage alone does not prove time correctness. The packet card says the client and specification are not a persistent lineage server, scheduler or dataset version store. Its catalog requirements (catalogs/us-equities/data-research.json line 844) also need dataset-version and knowledge-cutoff facets that nobody has defined yet. The project's pinned-digest manifest already records source and SQL hashes for each selection (nanosecond-replay README lines 65-68), and no source read here shows a lineage need that manifest fails to meet. The evidence is source_review only: the README at 8ad5c14c was not opened, and the example at line 838 is marked UNEXECUTED.
- cosign (conditional) — cosign covers the provenance scope term only as signature and identity verification of artifacts. Its role in the packet is artifact signing for software supply chains. It provides no data versioning, snapshot restore or lineage. It could become relevant if snapshot manifest digests later need signing, but that use is untested. The packet card says no signing or identity flow was initiated, and that not all upstreams publish signatures. The evidence is source_review of the v3.1.3 README, which was not opened here.
- data-kafka (conditional) — Kafka matches the replay-log scope term as a durable partitioned event log. Its packet card limits it in three ways: ordering is partition-local, transactions do not make external sinks exactly-once, and the single-node synthetic replay is only a prospective smoke check. It adds a broker service without providing dataset versioning or lineage. The packet's existing_overturn_when requires local throughput or concurrency measurements before adding a server, and none are recorded. The evidence is source_review of the README at 26b251a4, which was not opened here.
- foundation-socraticode (out_of_scope) — This is the only native_proven candidate, but its receipts cover semantic code retrieval and index freshness, not market-data identity or snapshot provenance. evidence/receipts/native-rag.json claims both native clients retrieved correct project code. evidence/receipts/desktop-direct-rag.json records a Desktop codebase_search, evidence/receipts/vllm-compatibility.json an embedding-server compatibility attempt, and evidence/receipts/artifact-reductions.json text reductions. Its match to the index-freshness scope term concerns code indexes, so the native proof does not carry over to this layer's data requirement.
- data-arcticdb (conditional) — ArcticDB is a versioned dataframe store, which overlaps DVC's snapshot role. The packet card says it is BSL-1.1 source-available, with an unresolved question about production and business use. The card also says storage version time is not proof of market information availability. The evidence is source_review of the README at e620d857 only, not opened here, and no execution is recorded.
- data-mlflow (conditional) — MLflow covers model lineage and experiment tracking, a narrower slice than data identity and snapshot reproducibility. Its card says no experiments were run and that the example records only a synthetic local metric (catalogs/us-equities/data-research.json lines 798-808). Autologging does not capture every data revision, so MLflow depends on a data-versioning layer such as c2 rather than replacing it. The evidence is source_review only.
- data-iceberg (conditional) — Iceberg is a snapshot-store table format for multi-engine object storage. Its card says catalog creation alone would not prove append, multi-writer conflict handling, cross-engine compatibility or time travel. It also says storage snapshots do not imply past information availability (catalogs/us-equities/data-research.json lines 888-891). Adopting it adds a catalog and storage backend without a demonstrated multi-engine need. The evidence is source_review only, and the PyIceberg example is marked UNEXECUTED (line 880).
- data-lakefs (not a packet candidate) (conditional) — lakeFS is not in the packet, although it matches the object-store-versioning and data-branches scope terms. Its catalog card (catalogs/us-equities/data-research.json lines 737-778) says the quickstart is a local demonstration, not a pinned production server or high-availability proof. The card also says lakeFS commits do not make independently updated external databases part of one atomic financial snapshot, and that retention and garbage collection can remove artifacts needed for replay. It needs a server, backend and access policy, and no need for concurrent team branches has been demonstrated. The evidence is source_review only.

Overturn when: The verdict changes on an executed comparison over the existing synthetic fixtures blueprints/us-equities/nanosecond-replay/fixture.json and blueprints/us-equities/point-in-time/fixture.json. The baseline is the existing regression suite, `python3 -m unittest tests.test_nanosecond_replay tests.test_point_in_time -v`. It must run under the interpreter built from adoption/sdk/requirements-linux-x86_64-py313.lock, which pins duckdb==1.5.5 and pandas==3.0.6, and it must report zero skipped tests. Both suites skip without pandas or DuckDB, and the blueprint READMEs say a skip is not acceptance. The comparison puts the materialized snapshot under DVC 3.67.1 tracking in a new private repository and repeats the exercise with PyIceberg 0.12.0 and ArcticDB v6.26.0. Any of these outcomes would overturn the verdict: DVC fails to restore byte-identical snapshot files with the same snapshot_sha256 and per-cutoff selection/SQL hashes; another arm reproduces the snapshots with no more added services and no license restriction while adding a verified capability the manifest lacks; or a documented lineage need appears that the hash manifest cannot meet and OpenLineage 1.53.0 local events (no transport) satisfy it. The third outcome would promote c5 to a co-winner.

Open gaps:
- DVC has not been installed or run in this repository. Its catalog native_workflow is labelled prospective and UNEXECUTED, so the single winner rests on source review only.
- No evidence shows that DVC-tracked snapshots preserve the project hash-manifest contract (snapshot_sha256, pinned-digest selection, source and SQL hashes) recorded in the nanosecond-replay and point-in-time receipts.
- No lineage need has been demonstrated beyond what the manifest and selection hashes record. OpenLineage's dataset-version and knowledge-cutoff facets are undefined and untested.
- Content hashes and lineage metadata do not establish historical availability, as-known eligibility, permanent security identity, corporate-action completeness or licensing rights (packet limitations; point-in-time receipt limitations).
- Symbol mapping and an actual historical universe remain unaccepted (nanosecond-replay README lines 61-63). Both project-local receipts are synthetic, with entitlement_verified=false in the point-in-time receipt.
- It is unverified whether a private DVC remote can hold licensed market data within the entitlement.
- delta-rs (catalogs/us-equities/data-research.json line 901 onward, snapshot-store) is another non-packet entry that matches this layer's scope. It was not evaluated beyond its header lines.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-identity-provenance-20260922; codex: -)

#### Market data and reference (market-data-reference)

- data-alpaca-py @ v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28 — This is my own review of the retained local receipts, revised after re-reading the evidence the refuters cited. It does not restate any provider verdict, since the packet withholds the prior decision and rationale. These three adopted candidates are the only ones with retained native-execution evidence for the parts of the requirement they cover. Every other adopted candidate has only a GitHub README reference, which I did not read.

c9 alpaca-py covers daily bars and corporate actions. The packet lists only its README for c9, and the c9 card (packet lines 240 and 246) still says evidence_kind source_review and "No account, entitlement, data request or order was exercised by this catalog." A later receipt contradicts that card: blueprints/us-equities/authenticated-data/native-receipt.json, kind native_cli_e2e, observed 2026-09-20. Running blueprints/us-equities/alpaca-historical/collect.py against the frozen request plan blueprints/us-equities/alpaca-historical/plan.json fetched 25 AAPL daily bars (SIP feed, raw adjustment) over 3 pages and 2 corporate actions over 2 pages. The receipt records 5 HTTP 200 pages, the terminal page observed for both stages, and exit 0. authenticated-data/compare.py found 25 of 25 raw closes equal and both numeric action values equal to the frozen LEAN probe, with 1 cash currency unknown. The native boundary is narrower than a full SDK path (native-receipt.json lines 198-201 and 215-219). The upstream calls are the low-level StockHistoricalDataClient.get("/stocks/bars") and CorporateActionsClient.get("/corporate-actions") with explicit queries. Pagination and the provenance/validation bridge are custom. Pinned private _session and _retry seams capture the response bytes and disable native retries. The status is still "bounded_acquisition_accepted_reconciliation_partially_open", and historical_coverage_established is false.

c6 EdgarTools covers SEC filing indexes and headers. It does not cover fundamentals. blueprints/us-equities/catalyst-provenance/receipt.json keeps the dated failures: an empty-proxy ValueError, then HTTP 403. blueprints/us-equities/catalyst-provenance/access-resolution.json (lines 31-56) records the native edgar.get_filings(2020,1,form='8-K',amendments=True,filing_date='2020-03-02') call after the contact correction: exit 0, HTTP 200, 371 index rows (8-K 362, 8-K/A 9) representing 360 unique accessions, and a gzip source of 5079824 bytes with a recorded SHA256. Lines 104-112 show the custom repository adapter catalyst.py rejecting data of unknown availability: the historical packet as of 2020-03-03T00:00:00Z has eligible_count 0, with 5 exclusions marked before_first_availability. That rejection is done by repository code, not by EdgarTools. No XBRL, company-facts or fundamentals path was exercised.

c13 exchange_calendars covers sessions and timezones. blueprints/us-equities/data/summarize_backtest.py calls the XNYS session_open and session_close, and blueprints/us-equities/data/receipt.json records the resulting 2013-10-07 session as 13:30 to 20:00 UTC. evidence/receipts/exchange-calendars-native-check-20260922.json independently reproduces those values with 4.13.2 (exit 0) and confirms the source pin dbe38b1f. That receipt states it does not show that data/receipt.json or historical-simulation/receipt.json invoked the package internally. blueprints/us-equities/workers/requirements.txt pins exchange-calendars==4.13.2.

These are three complementary layers, not one universal winner. Each rests on a small bounded sample.
- data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a — This is my own review of the retained local receipts, revised after re-reading the evidence the refuters cited. It does not restate any provider verdict, since the packet withholds the prior decision and rationale. These three adopted candidates are the only ones with retained native-execution evidence for the parts of the requirement they cover. Every other adopted candidate has only a GitHub README reference, which I did not read.

c9 alpaca-py covers daily bars and corporate actions. The packet lists only its README for c9, and the c9 card (packet lines 240 and 246) still says evidence_kind source_review and "No account, entitlement, data request or order was exercised by this catalog." A later receipt contradicts that card: blueprints/us-equities/authenticated-data/native-receipt.json, kind native_cli_e2e, observed 2026-09-20. Running blueprints/us-equities/alpaca-historical/collect.py against the frozen request plan blueprints/us-equities/alpaca-historical/plan.json fetched 25 AAPL daily bars (SIP feed, raw adjustment) over 3 pages and 2 corporate actions over 2 pages. The receipt records 5 HTTP 200 pages, the terminal page observed for both stages, and exit 0. authenticated-data/compare.py found 25 of 25 raw closes equal and both numeric action values equal to the frozen LEAN probe, with 1 cash currency unknown. The native boundary is narrower than a full SDK path (native-receipt.json lines 198-201 and 215-219). The upstream calls are the low-level StockHistoricalDataClient.get("/stocks/bars") and CorporateActionsClient.get("/corporate-actions") with explicit queries. Pagination and the provenance/validation bridge are custom. Pinned private _session and _retry seams capture the response bytes and disable native retries. The status is still "bounded_acquisition_accepted_reconciliation_partially_open", and historical_coverage_established is false.

c6 EdgarTools covers SEC filing indexes and headers. It does not cover fundamentals. blueprints/us-equities/catalyst-provenance/receipt.json keeps the dated failures: an empty-proxy ValueError, then HTTP 403. blueprints/us-equities/catalyst-provenance/access-resolution.json (lines 31-56) records the native edgar.get_filings(2020,1,form='8-K',amendments=True,filing_date='2020-03-02') call after the contact correction: exit 0, HTTP 200, 371 index rows (8-K 362, 8-K/A 9) representing 360 unique accessions, and a gzip source of 5079824 bytes with a recorded SHA256. Lines 104-112 show the custom repository adapter catalyst.py rejecting data of unknown availability: the historical packet as of 2020-03-03T00:00:00Z has eligible_count 0, with 5 exclusions marked before_first_availability. That rejection is done by repository code, not by EdgarTools. No XBRL, company-facts or fundamentals path was exercised.

c13 exchange_calendars covers sessions and timezones. blueprints/us-equities/data/summarize_backtest.py calls the XNYS session_open and session_close, and blueprints/us-equities/data/receipt.json records the resulting 2013-10-07 session as 13:30 to 20:00 UTC. evidence/receipts/exchange-calendars-native-check-20260922.json independently reproduces those values with 4.13.2 (exit 0) and confirms the source pin dbe38b1f. That receipt states it does not show that data/receipt.json or historical-simulation/receipt.json invoked the package internally. blueprints/us-equities/workers/requirements.txt pins exchange-calendars==4.13.2.

These are three complementary layers, not one universal winner. Each rests on a small bounded sample.
- data-exchange-calendars @ 4.13.2; source dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a — This is my own review of the retained local receipts, revised after re-reading the evidence the refuters cited. It does not restate any provider verdict, since the packet withholds the prior decision and rationale. These three adopted candidates are the only ones with retained native-execution evidence for the parts of the requirement they cover. Every other adopted candidate has only a GitHub README reference, which I did not read.

c9 alpaca-py covers daily bars and corporate actions. The packet lists only its README for c9, and the c9 card (packet lines 240 and 246) still says evidence_kind source_review and "No account, entitlement, data request or order was exercised by this catalog." A later receipt contradicts that card: blueprints/us-equities/authenticated-data/native-receipt.json, kind native_cli_e2e, observed 2026-09-20. Running blueprints/us-equities/alpaca-historical/collect.py against the frozen request plan blueprints/us-equities/alpaca-historical/plan.json fetched 25 AAPL daily bars (SIP feed, raw adjustment) over 3 pages and 2 corporate actions over 2 pages. The receipt records 5 HTTP 200 pages, the terminal page observed for both stages, and exit 0. authenticated-data/compare.py found 25 of 25 raw closes equal and both numeric action values equal to the frozen LEAN probe, with 1 cash currency unknown. The native boundary is narrower than a full SDK path (native-receipt.json lines 198-201 and 215-219). The upstream calls are the low-level StockHistoricalDataClient.get("/stocks/bars") and CorporateActionsClient.get("/corporate-actions") with explicit queries. Pagination and the provenance/validation bridge are custom. Pinned private _session and _retry seams capture the response bytes and disable native retries. The status is still "bounded_acquisition_accepted_reconciliation_partially_open", and historical_coverage_established is false.

c6 EdgarTools covers SEC filing indexes and headers. It does not cover fundamentals. blueprints/us-equities/catalyst-provenance/receipt.json keeps the dated failures: an empty-proxy ValueError, then HTTP 403. blueprints/us-equities/catalyst-provenance/access-resolution.json (lines 31-56) records the native edgar.get_filings(2020,1,form='8-K',amendments=True,filing_date='2020-03-02') call after the contact correction: exit 0, HTTP 200, 371 index rows (8-K 362, 8-K/A 9) representing 360 unique accessions, and a gzip source of 5079824 bytes with a recorded SHA256. Lines 104-112 show the custom repository adapter catalyst.py rejecting data of unknown availability: the historical packet as of 2020-03-03T00:00:00Z has eligible_count 0, with 5 exclusions marked before_first_availability. That rejection is done by repository code, not by EdgarTools. No XBRL, company-facts or fundamentals path was exercised.

c13 exchange_calendars covers sessions and timezones. blueprints/us-equities/data/summarize_backtest.py calls the XNYS session_open and session_close, and blueprints/us-equities/data/receipt.json records the resulting 2013-10-07 session as 13:30 to 20:00 UTC. evidence/receipts/exchange-calendars-native-check-20260922.json independently reproduces those values with 4.13.2 (exit 0) and confirms the source pin dbe38b1f. That receipt states it does not show that data/receipt.json or historical-simulation/receipt.json invoked the package internally. blueprints/us-equities/workers/requirements.txt pins exchange-calendars==4.13.2.

These are three complementary layers, not one universal winner. Each rests on a small bounded sample.

Alternatives:
- Databento (conditional) — The only evidence is a README reference, which I did not read. No account, data request, corporate-action retrieval or ts_record handling was run. The packet notes that an exchange-specific feed is not consolidated US coverage and that redistribution is restricted. It might close the gaps in point-in-time definitions and corporate actions, but only a measured replay of blueprints/us-equities/alpaca-historical/plan.json against the alpaca-py receipt could show that.
- Massive Python client (conditional) — The only evidence is a README reference, which I did not read. No request was run. The packet card (lines 175-176) says the free tier does not grant commercial use, redistribution or every endpoint, and that ticker/date filters do not prove a complete historical universe. It has no acquisition receipt to compare with the alpaca-py 25-bar, 2-action receipt.
- data-feast (out_of_scope) — This is a downstream feature store, not a source of licensed observations. The only evidence is a README reference. Per the packet, point-in-time retrieval by event time does not exclude late corrections, and freshness and skew need separate evidence. No local run is retained.
- data-dlt (conditional) — It is loading glue with only a README reference and no retained pipeline run. The packet notes that schema inference is not a financial data-quality contract and that watermark extraction can miss late revisions. The retained acquisitions use their own collectors: alpaca-historical/collect.py and catalyst-provenance/catalyst.py.
- data-gdeltdoc (conditional) — This community news wrapper has only a README reference and no query run. Per the packet, GDELT first-seen time is not publication time or tradable-availability time, and results are not exhaustive. Without a separate availability gate it fails the requirement to reject data whose availability is unknown.
- data-fredapi (conditional) — This macro/vintage wrapper has only a README reference. The packet card (line 209) says its latest checked release is from 2024 and that no data request was run. Vintage selection and intraday release time are unverified.
- data-kafka (out_of_scope) — This is event-log infrastructure, not an observation source. The only evidence is a README reference. The packet notes that single-node synthetic replay is only a smoke check, and no throughput or concurrency measurement justifies adding a server.
- QuestDB (conditional) — This is a storage server. The packet says the catalog never installed or started it, and the only evidence is a README reference. Dedup/upsert can overwrite corrections. Correction: the only retained Parquet output (blueprints/us-equities/data/receipt.json) summarizes LEAN bundled simulated order events, with scope "not broker fills". It is not a market-data snapshot. So the reason not to default to QuestDB is that no storage measurement or need is demonstrated, not that an existing market-data store proves one is unnecessary.
- atilaahmettaner/tradingview-mcp (unqualified) — It is not adopted and has no evidence refs. The packet note sets its entry condition: documented data rights plus a demonstrated as-of query reconciled against retained Alpaca news timestamps. Nothing retained meets that condition.

Overturn when: Market data: replay the frozen request contract blueprints/us-equities/alpaca-historical/plan.json against c14 Databento and c7 Massive. That plan holds the AAPL bars and corporate-actions queries, the 25 expected sessions and the action_comparison_targets, and alpaca-historical/collect.py executed it. Extend the plan with a delisting, a ticker reuse and a split or dividend, and reconcile each arm with blueprints/us-equities/authenticated-data/compare.py or an equivalent. The verdict changes if a challenger records the feed, UTC timestamps, permanent identity, complete corporate actions including dividend currency, and as-known availability with auditable raw hashes at measured, acceptable cost, and alpaca-py does not.

SEC: the EdgarTools default changes if `python3 -m unittest tests.test_catalyst_provenance` stops passing (13 tests were recorded in catalyst-provenance/receipt.json). It also changes if a rerun of `python3 blueprints/us-equities/catalyst-provenance/catalyst.py packet --run <acquisition run> --as-of 2020-03-03T00:00:00Z` admits a filing whose availability is unknown. That rerun needs a private acquisition run from `catalyst.py acquire`, so a fresh checkout must first repeat the SEC acquisition. A demonstrated fundamentals/XBRL need that EdgarTools fails would also change it.

Calendars: the default changes if a multi-year XNYS holiday and half-day check with exchange_calendars 4.13.2 disagrees with the official exchange schedule.

Open gaps:
- The alpaca-py receipt covers only 25 AAPL daily bars (2020-08-03 to 2020-09-04) and 2 corporate actions. historical_coverage_established is false, dividend currency is unknown for 1 cash action, and neither original historical availability nor a survivorship-free universe is established (authenticated-data/native-receipt.json lines 63, 107, 128, 221).
- The packet's c9 card (evidence_kind source_review; 'No account, entitlement, data request or order was exercised by this catalog', packet lines 240 and 246) is stale: the later native-receipt.json shows a native acquisition. Until the catalog card is reconciled with that receipt, the c9 native classification rests on an out-of-packet file.
- The alpaca-py native boundary is the low-level GET/auth/URL transport, reached through pinned private _session/_retry seams, with custom pagination and a custom provenance bridge. The SDK's high-level request objects and native retry behavior were not exercised (native-receipt.json lines 198-201 and 215-219).
- EdgarTools evidence covers one 2020 Q1 8-K/8-K/A form index (371 rows, 360 accessions), 5 SGML headers and one offline HTML-to-markdown parse of a pinned upstream fixture. No retained receipt exercises fundamentals, XBRL or company facts, and the packet card warns that company facts carry later revisions (packet line 139).
- The 5 acquired SEC headers are rejected at the 2020-03-03 cutoff and qualify only at their 2026-09-19 local first observation, so no historical as-known SEC dataset exists. The temporal gate is custom repository code (access-resolution.json lines 104-166).
- exchange_calendars evidence confirms one XNYS session (2013-10-07). The reproduction receipt explicitly does not show that data/receipt.json or historical-simulation/receipt.json invoked the package internally, and historical-simulation/receipt.json's 104-session attribution is only its own descriptive string. Holidays, half days, extended hours and halts are not covered.
- No measured comparison exists between the market-data providers (alpaca-py, Databento, Massive).
- No news, macro-vintage (FRED/ALFRED) or alternative-data source has retained execution evidence.
- No receipt I read establishes data licensing or redistribution rights for the acquired observations.
- codex lane absent for this layer
- unindexed alternative sec-api-io/sec-api-python https://github.com/SEC-API-io/sec-api-python
- unindexed alternative rossod4/quantlab https://github.com/Rossod4/quantlab

Lanes: codex_absent (claude: us-equities-market-data-reference-20260922; codex: -)

#### Observability and hosting (observability-hosting)

- opentelemetry-collector-contrib @ v0.161.0 — This is my source review of retained native receipts. I did not run a measured comparison. The three winners cover the collector pipeline, native-client metrics with alert-based supervision, and the only recoverable-state proof. Loki (c6) must be deployed with them, as explained below.

c14 (OpenTelemetry Collector contrib v0.161.0): observability/receipt.json lines 78-80 record 'otelcol-contrib validate' exit 0. Real native Codex 0.155.1 and Claude 2.1.278 tasks each exited 0 with the correct fixture answer (lines 164-201). The receipt records collected_turn_histogram_matches_native_usage=true (line 182) and collected_request_logs_and_metrics_match=true (line 201). The collector's file_log/sdk_receipts receiver delivered two SDK receipt records, and the total stayed at 80770 after a collector restart (lines 246-255).

Correction from the refuters: the 80770 figure comes from a Loki LogQL query (lines 122-127), not Prometheus. native_turn_histogram_observed is false (line 227). Completed SDK result usage records are therefore retained only in Loki today.

c5 (Prometheus v3.14.0): observability/backends/receipt.json records config validation exit 0 and a final_rule_count of 8 (lines 115-116). The restart persistence check (synthetic_fixture true, restart_exit_code 0, prometheus_historical_sample true; lines 85-98) ran under the earlier six-rule scope (line 117, original_acceptance_rule_count 6 at line 158). Prometheus scrapes the collector-native target (observability/receipt.json line 118) and holds the native collector series (token_selection source query on job collector-native, 2134 series, lines 349-355). It carries the only natively proven supervision and alert path: EcosystemAcceptanceTargetDown produced 1 firing and 1 resolved notification to a local inbox (lines 303-311). The retained values ["7","7"] come from a synthetic privacy canary, not an inference task (line 314).

c8 (Restic v0.19.1): blueprints/us-equities/hosting/backup/receipt.json records verified signed checksums (line 28) and backup exit 0 for 22 files and 160642 bytes. 'check --read-data' reported 'no errors were found'. restore --verify restored 160642 bytes, the sha256sum check reported 22 OK lines, and the independent byte comparison matched 22 files. The retention dry run kept 1 snapshot and removed 0 (lines 33-97). The scope is only 22 static public reference files with live_databases 0 (lines 15, 36). No Loki, Prometheus or broker/order journal was backed up (line 125).

Weakest class across the winners: native_proven. The receipt's retained_failed_attempts list (lines 370-375) is the acceptance author's prose. It is not collected telemetry, so I do not count it as evidence for the 'failed attempts' clause.
- prometheus @ v3.14.0 — This is my source review of retained native receipts. I did not run a measured comparison. The three winners cover the collector pipeline, native-client metrics with alert-based supervision, and the only recoverable-state proof. Loki (c6) must be deployed with them, as explained below.

c14 (OpenTelemetry Collector contrib v0.161.0): observability/receipt.json lines 78-80 record 'otelcol-contrib validate' exit 0. Real native Codex 0.155.1 and Claude 2.1.278 tasks each exited 0 with the correct fixture answer (lines 164-201). The receipt records collected_turn_histogram_matches_native_usage=true (line 182) and collected_request_logs_and_metrics_match=true (line 201). The collector's file_log/sdk_receipts receiver delivered two SDK receipt records, and the total stayed at 80770 after a collector restart (lines 246-255).

Correction from the refuters: the 80770 figure comes from a Loki LogQL query (lines 122-127), not Prometheus. native_turn_histogram_observed is false (line 227). Completed SDK result usage records are therefore retained only in Loki today.

c5 (Prometheus v3.14.0): observability/backends/receipt.json records config validation exit 0 and a final_rule_count of 8 (lines 115-116). The restart persistence check (synthetic_fixture true, restart_exit_code 0, prometheus_historical_sample true; lines 85-98) ran under the earlier six-rule scope (line 117, original_acceptance_rule_count 6 at line 158). Prometheus scrapes the collector-native target (observability/receipt.json line 118) and holds the native collector series (token_selection source query on job collector-native, 2134 series, lines 349-355). It carries the only natively proven supervision and alert path: EcosystemAcceptanceTargetDown produced 1 firing and 1 resolved notification to a local inbox (lines 303-311). The retained values ["7","7"] come from a synthetic privacy canary, not an inference task (line 314).

c8 (Restic v0.19.1): blueprints/us-equities/hosting/backup/receipt.json records verified signed checksums (line 28) and backup exit 0 for 22 files and 160642 bytes. 'check --read-data' reported 'no errors were found'. restore --verify restored 160642 bytes, the sha256sum check reported 22 OK lines, and the independent byte comparison matched 22 files. The retention dry run kept 1 snapshot and removed 0 (lines 33-97). The scope is only 22 static public reference files with live_databases 0 (lines 15, 36). No Loki, Prometheus or broker/order journal was backed up (line 125).

Weakest class across the winners: native_proven. The receipt's retained_failed_attempts list (lines 370-375) is the acceptance author's prose. It is not collected telemetry, so I do not count it as evidence for the 'failed attempts' clause.
- restic @ v0.19.1; publisher-signed linux/amd64 release asset — This is my source review of retained native receipts. I did not run a measured comparison. The three winners cover the collector pipeline, native-client metrics with alert-based supervision, and the only recoverable-state proof. Loki (c6) must be deployed with them, as explained below.

c14 (OpenTelemetry Collector contrib v0.161.0): observability/receipt.json lines 78-80 record 'otelcol-contrib validate' exit 0. Real native Codex 0.155.1 and Claude 2.1.278 tasks each exited 0 with the correct fixture answer (lines 164-201). The receipt records collected_turn_histogram_matches_native_usage=true (line 182) and collected_request_logs_and_metrics_match=true (line 201). The collector's file_log/sdk_receipts receiver delivered two SDK receipt records, and the total stayed at 80770 after a collector restart (lines 246-255).

Correction from the refuters: the 80770 figure comes from a Loki LogQL query (lines 122-127), not Prometheus. native_turn_histogram_observed is false (line 227). Completed SDK result usage records are therefore retained only in Loki today.

c5 (Prometheus v3.14.0): observability/backends/receipt.json records config validation exit 0 and a final_rule_count of 8 (lines 115-116). The restart persistence check (synthetic_fixture true, restart_exit_code 0, prometheus_historical_sample true; lines 85-98) ran under the earlier six-rule scope (line 117, original_acceptance_rule_count 6 at line 158). Prometheus scrapes the collector-native target (observability/receipt.json line 118) and holds the native collector series (token_selection source query on job collector-native, 2134 series, lines 349-355). It carries the only natively proven supervision and alert path: EcosystemAcceptanceTargetDown produced 1 firing and 1 resolved notification to a local inbox (lines 303-311). The retained values ["7","7"] come from a synthetic privacy canary, not an inference task (line 314).

c8 (Restic v0.19.1): blueprints/us-equities/hosting/backup/receipt.json records verified signed checksums (line 28) and backup exit 0 for 22 files and 160642 bytes. 'check --read-data' reported 'no errors were found'. restore --verify restored 160642 bytes, the sha256sum check reported 22 OK lines, and the independent byte comparison matched 22 files. The retention dry run kept 1 snapshot and removed 0 (lines 33-97). The scope is only 22 static public reference files with live_databases 0 (lines 15, 36). No Loki, Prometheus or broker/order journal was backed up (line 125).

Weakest class across the winners: native_proven. The receipt's retained_failed_attempts list (lines 370-375) is the acceptance author's prose. It is not collected telemetry, so I do not count it as evidence for the 'failed attempts' clause.

Alternatives:
- Loki (conditional) — Loki is a required co-store for the winners, not an optional overlap. It is the only backend where completed SDK result usage records were queried: LogQL returned total_tokens 80770 (observability/receipt.json lines 122-127, 246-255), and native_turn_histogram_observed is false (line 227). Its config check passed with exit 0 and the synthetic log persisted after one restart (observability/backends/receipt.json lines 85-98). It is outside the three-winner cap only because Prometheus also carries the native-client collector series and the only proven alert route (1 firing, 1 resolved). That priority is my judgment. No comparison was measured. Receipts contain no retained failed-run records for Loki, the same as for Prometheus. The lack of high availability and backup applies to both stores: the restic scope excluded live Loki and Prometheus (backup receipt line 125), and backends receipt line 106 says single-host persistence is not replication or an off-host backup.
- opentelemetry-collector (overlap) — This is the core runtime inside the adopted contrib distribution (c14). The packet (line 400) says the standalone otelcol core binary was not separately exercised. observability/receipt.json lists only otelcol-contrib, so c13 has no native evidence of its own apart from c14. I downgraded its class to source_review.
- Grafana (conditional) — Grafana provides visualization, not retention or recovery. Readiness returned 200, and the provisioned dashboard and datasources were present after one restart. agent-browser rendered the dashboard. However, the screenshot predates the SDK panel (observability/receipt.json line 292), and grafana_tag_build_commit_equal is false. Use it for operator views on top of the stores.
- alertmanager (conditional) — Only the local alert path is proven: amtool check-config returned exit 0, and the Prometheus to Alertmanager to ntfy route produced 1 firing and 1 resolved notification (observability/receipt.json lines 93-95, 303-311). external_delivery_tested is false. Alertmanager is needed for notification routing but does not retain telemetry or recover state.
- ntfy (conditional) — Only local retained-inbox delivery is proven: readiness returned 200, the synthetic message persisted after restart, and the bundled alertmanager template worked. No external delivery was tested. ntfy is a notification sink, not a telemetry store or recovery mechanism.
- sandbox-runtime (conditional) — Filesystem restriction was proven natively: the allowed write exited 0, the denied read exited 1, the separate denied write exited 1, and no host file was created. Network denial was configured but not exercised (evidence/receipts/runtime-tools.json line 13). Network denial is what would withhold broker reachability from research workers, so no candidate proves the requirement's 'without broker execution authority' clause. sandbox-runtime is not a VM boundary.
- opensandbox (unqualified) — The packet has source review only, and I did not open its external README. The pin server/v0.2.3 is behind upstream release-1.1.0. There is no local execution receipt, and help or import output does not prove isolation.
- e2b (unqualified) — Source review only, and I did not open the external README. An import check is not sandbox E2E, and the self-host guide targets AWS/GCP. There is no native receipt.
- modal (out_of_scope) — Modal is managed paid cloud compute. 'modal run' was not executed and could incur charges, and catalog inclusion does not authorize paid hosting. The evidence is source review of a PyPI page I did not open, and the pin and latest versions disagree (1.5.5 against v1.3.1).
- mlflow (unqualified) — Source review only, and I did not open the external README. No tracking server was run. MLflow targets experiment and model lineage, not operational telemetry or recovery.
- phoenix (unqualified) — Source review only, and I did not open the external README. The server launch is prospective and no app was instrumented. The license is ELv2 with restrictions, and the provider-hiding flag is not an inference authorization boundary.

Overturn when: The current evidence already shows SDK result records in Loki only, so the earlier Loki trigger has been replaced. Any of the following would change the verdict, and each needs a recorded native run, not agreement between lanes.

(1) Replace c5 with c6: a native rerun of the fixtures/observability-check.json acceptance in which Loki alone retains both the native Codex and Claude usage and the SDK receipt records, and a Loki-ruler alert routed through Alertmanager reproduces 1 firing and 1 resolved notification. That would make Prometheus redundant.

(2) Remove the Loki dependency and confirm c5: a rerun in which the SDK turn histogram is observed in Prometheus (native_turn_histogram_observed true) and matches the native usage.

(3) Displace c8: a new restic receipt at blueprints/us-equities/hosting/backup/receipt.json that fails 'check --read-data' or the restore byte comparison, or a same-scope alternative that backs up live Prometheus/Loki state with a verified restore.

Open gaps:
- Completed SDK result usage records are retained only in Loki (c6): LogQL returned 80770, and native_turn_histogram_observed is false. The winner set depends on c6 being deployed with it.
- No backend was observed retaining failed-attempt or failed-run records. retained_failed_attempts in observability/receipt.json lines 370-375 is the acceptance author's prose, not collected telemetry. The requirement's 'failed attempts' clause therefore has no native proof.
- Recoverable state is proven only for 22 static public reference files with live_databases 0. There is no backup of Prometheus, Loki, SQLite or any broker/order journal, and no application-consistent database restore.
- There is no off-host backup, and separate_key_escrow is not_configured. Host or volume loss is unprotected. The restic retention policy was run only as a dry run (1 snapshot kept, 0 removed). No backup timer or service is enabled.
- The backend restart persistence checks ran under the earlier six-rule scope, not the final 8-rule configuration, and used synthetic fixtures. Retention was not aged out.
- The only retained Prometheus value query is a synthetic privacy canary with values ["7","7"]. Prometheus holds the native-client collector series, but the receipt does not name which backend held the matched Codex turn histogram.
- No backend has high availability. The single WSL host depends on the user service manager.
- Sandbox network denial was not exercised, so no candidate proves that research workers are blocked from broker execution authority.
- No external alert delivery was tested (external_delivery_tested is false).
- Process supervision is shown only by 'systemctl --user is-active' for six services and the target-down alert. There is no evidence of in-flight workload recovery.
- No measured comparison between candidates was run. The priority of Prometheus over Loki in the three-winner cap is my judgment.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-observability-hosting-20260922; codex: -)

#### Portfolio and risk (portfolio-risk)

- skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee — c3 (skfolio) is the only adopted candidate with retained local execution evidence. What was actually observed comes from blueprints/us-equities/research-evaluation/receipt.json (kind "native_cli_e2e", observed_utc 2026-09-19T22:59:04Z, status "accepted_for_causal_raw_price_label_control_only"). In that run, the installed upstream skfolio 1.2.9 WalkForward was called with 252/63/6 and reduce_test=True on SPY/QQQ/IWM session rows. It produced 20 development folds, 21 frozen selections and 6605 candidate records. The run command exited 0 with empty stderr (0 bytes). The focused tests reported "12 passed" and the full suite "214 passed, 0 skipped". The dependency check reported "All 19 installed packages compatible." An independent review verified 42 private artifact hashes with 0 mismatches and reported no blocking findings. The receipt records a walkforward_source_sha256 and reviewed revision c99fcf71349e2df4a7a1033ee85ca2e9ced9abee. The README "Observed native results" section also says "This accepts the splitter used here, not every skfolio optimizer." The native evidence therefore covers skfolio's chronological validation splitter in a raw-price label study. It does not cover skfolio's portfolio optimizers, risk measures, portfolio P&L or pre-trade risk enforcement. skfolio is selected because it is the only portfolio-layer candidate whose own component has actually run here. It is not selected because it has been shown to satisfy the full portfolio-and-risk requirement. The other three candidates rely on GitHub README URLs, which this lane could not open.

Alternatives:
- cvxportfolio (unqualified) — The only evidence is a source review of an upstream README URL (https://github.com/cvxgrp/cvxportfolio/blob/1.5.1/README.rst), and this lane could not open it locally. No local receipt, test or fixture under the repository runs cvxportfolio. The packet card says its multi-period policy/cost-model workflow is unexecuted, that its simulator may download risk-free data when cash returns are absent, and that optimizer feasibility is not execution feasibility. It is also GPL-3.0, while skfolio is BSD-3-Clause. Its multi-period transaction/holding-cost modelling is scope that the skfolio splitter receipt does not cover, so it remains a comparison target rather than a rejected tool.
- empyrical-reloaded (unqualified) — Supported only by a source review of an upstream README URL (https://github.com/stefan-jansen/empyrical-reloaded/blob/0.5.12/README.md), which this lane did not open. No local execution receipt exists. The packet card records an import-name collision with the older empyrical package and says the pandas-datareader integration is incompatible with Python >=3.12. That matters because the accepted research environment is Python 3.13.15, per receipt.json runtime.python. It computes return/risk metrics only; it does not do portfolio construction or chronological validation.
- quantstats (overlap) — Supported only by a source review of an upstream README URL (https://github.com/ranaroussi/quantstats/blob/v0.0.81/README.md), which this lane did not open. No local execution receipt exists. It produces descriptive return-period tear sheets and overlaps c2's metric role. The packet card says it does not fix leakage, trial selection, fills or accounting errors, and it assumes a 252-period convention. It is a reporting aid, not portfolio or risk construction.

Overturn when: Reopen the verdict if either of two runs on the frozen inputs in blueprints/us-equities/research-evaluation/plan.json turns out differently. First: a native skfolio optimizer/risk-measure run on those inputs, with tests added alongside tests/test_research_evaluation.py and run as `python3 -m unittest discover -s tests -p test_research_evaluation.py -v`, fails or cannot express the required cost or constraint semantics. Second: an equivalently receipted native cvxportfolio (c1) run on the same plan produces cost-aware multi-period results with a reproducible cash ledger and passing boundary tests that skfolio cannot match. Either outcome would promote c1 or demote c3. A regression in the existing focused suite, or a WalkForward source hash that no longer matches the receipt, would also reopen c3.

Open gaps:
- The skfolio native evidence covers only the WalkForward splitter in a raw-price label study. No skfolio optimizer, risk measure or portfolio weight output has been executed (README.md, 'This accepts the splitter used here, not every skfolio optimizer').
- No candidate provides deterministic pre-trade numeric risk enforcement or broker reconciliation. The receipt limitations state there is 'No cash/position/fee/dividend reconciliation or new LEAN engine execution'.
- The receipt says its labels are not portfolio P&L, total return, annualized return or Sharpe; the cost proxy is a fixed 20bp round trip. Only 11 completed reserved episodes per candidate exist, with no alpha or superiority claim.
- No integration of any candidate with the selected NautilusTrader 2.0.0rc5 destination is evidenced.
- The packet shows the skfolio pin (1.2.9) behind upstream v1.3.0, and v1.3.0 has not been accepted natively.
- cvxportfolio, empyrical-reloaded and quantstats have no local execution receipts, so their fitness is untested, which is not the same as failed.
- No executed comparison exists between any pair of candidates on the same frozen inputs.
- Native acceptance is limited to a Linux/WSL Python 3.13.15 environment (receipt limitations).
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-portfolio-risk-20260922; codex: -)

#### Research, factors and ML (research-factors-ml)

- skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee — c23 (skfolio) is the only candidate in this layer with an executed research-evaluation receipt. blueprints/us-equities/research-evaluation/receipt.json (kind native_cli_e2e, observed 2026-09-19T22:59:04Z, status "accepted_for_causal_raw_price_label_control_only") records a native run of skfolio 1.2.9 WalkForward (252/63/6, reduce_test=True) on bundled LEAN SPY/QQQ/IWM daily data. The run, command run-1 in the separate skfolio venv, exited 0. It produced 20 chronological development folds, 21 frozen selections and 6605 candidate records. The plan was frozen before prices were parsed (plan sha256 b8d1beba...), and every training label exit preceded its evaluation cutoff. The receipt's independent_review (lines 1780-1791) is "accepted". It verified 42 artifact hashes with 0 mismatches, 21 selection hashes, 21 training-exit boundaries and 6605 ledger records, and recorded 12 focused tests passed with no blocking findings. Its scope was a read-only code and evidence review with no scoring rerun. The receipt also records a full-tests command, `$SDK_PYTHON -m unittest discover -s tests -q`, with result "214 passed, 0 skipped" (receipt lines 1578-1589; README lines 66-67). That run is this repository's own local test suite under the working SDK interpreter. It is not skfolio's upstream test suite, so it is local-integration evidence. This is the causal, cost-aware chronological validation leg of the requirement, within a narrow scope. The labels are raw-price labels under a fixed 20bp round-trip cost proxy, not portfolio P&L, and there are only 11 reserved episodes per candidate. The reserved momentum20 selection (0.118407% after the cost proxy) came in below the equal-weight control (0.162293%), so no alpha is claimed. The requirement's independent-reconciliation leg is not met. The receipt states "No cash/position/fee/dividend reconciliation or new LEAN engine execution" (line 1773). The evidence consists of one native execution plus an independent review of one control study, and it does not show that skfolio outperforms the other libraries.

Alternatives:
- scikit-learn (conditional) — The packet evidence is only the upstream README at 1.9.1, which I did not open. The research-evaluation receipt shows scikit-learn 1.9.1 installed as a locked dependency of the native skfolio run. No scikit-learn baseline model or TimeSeriesSplit was exercised on its own. It should be retained as the foundation skfolio builds on, but it is not established as a separate winner.
- data-sktime (unqualified) — It overlaps with skfolio on temporal splits and evaluation. The only evidence is an upstream README, which I did not open, and there is no native run on the frozen research-evaluation plan.
- alphalens-reloaded (unqualified) — It is the closest role match for cross-sectional factor IC and turnover, but the evidence is source review only. The packet card says the prospective workflow is unexecuted. The PyPI 0.4.6 pin differs from the GitHub 0.4.5 latest tag, and IC excludes all costs.
- Qlib (unqualified) — The evidence is source review only. The bundled workflow targets CSI300 with China-style costs and limits, and US compatibility is not proven. The upstream data download is unverified, and the prospective workflow is unexecuted.
- statsmodels (unqualified) — The evidence is source review only, and the prospective workflow is unexecuted. Statistical significance does not establish economic profitability.
- arch (unqualified) — It adds volatility, bootstrap, SPA and MCS tools, but the evidence is source review only and the workflow is unexecuted. The license label is ambiguous (NCSA vs Other).
- data-tsfresh (unqualified) — The evidence is source review only. Feature searches carry leakage and multiple-testing risk, and no fold-local run was observed.
- data-river (unqualified) — The evidence is source review only. The card notes that progressive validation with immediate labels is invalid for delayed financial outcomes, and no run was observed.
- data-statsforecast (unqualified) — The evidence is source review only. The bundled airline data is a method demo, and no financial forecast was evaluated.
- chronos (unqualified) — The evidence is source review only. The card records that no inference or GPU compatibility check was performed, and generic benchmarks do not establish US-equity alpha.
- timesfm (unqualified) — The evidence is source review only. The 3.0 weights carry a non-commercial license, and the card describes only a synthetic API example with no finance evaluation.
- data-arcticdb (out_of_scope) — It is versioned dataframe storage. None of the packet's layer_scope_terms (packet lines 777-819) names storage, so it is a data-layer dependency rather than a factor, ML, research or document method. The evidence is source review only, and it carries BSL-1.1 licensing restrictions.
- data-edgartools (conditional) — Its native-proven SEC filing acquisition fits the layer's document-research scope term as an input. access-resolution.json (native_cli_e2e) records 371 index entries (360 unique accessions) and five headers rejected at the historical cutoff, and receipt.json records an earlier SEC 403. It supports causal-data provenance for catalyst research but performs no factor or model evaluation and does not meet the cost-aware chronological validation leg.
- deerflow (conditional) — It is an optional research-orchestration host, which is in the layer's scope terms. research-receipt.json (native_model_e2e) shows one embedded ACP evidence-review task completed with correct counts. There is no planner, UI or persistent service, and ACP 'read-only' maps to workspaceWrite. It hosts research but performs no factor or ML evaluation.
- foundation-qmd (conditional) — It is in scope under the document-retrieval scope term. native-cli-gaps.json shows the Claude qmd workflow passed (BM25, score 0.86), while the Codex attempt was quota-blocked and not exercised. That proves Markdown document retrieval for research notes, but it performs no causal or cost-aware factor or model evaluation, so it supports the research workflow rather than qualifying a strategy.
- foundation-markitdown (conditional) — It is in scope under the document-ingestion scope term. portable-cli-artifacts.json shows only a local HTML conversion (markitdown_contains_heading true), and the PDF and Office extras are unproven. It performs no factor or model evaluation.
- vllm (conditional) — It is in scope under the model-serving scope term. vllm-compatibility.json (kind compatibility_attempt, not an E2E acceptance) records that 0.29.0 installed but GPU startup failed on WSL with "RuntimeError: UVA is not available". The receipt limits this to "a host-specific failure", not a general unusability claim. Active 0.25.0 was restored, and direct retrieval passed (desktop-direct-rag.json). The native pass covers only 0.25.0 embedding and retrieval serving. The runtime is behind upstream, and there is no research inference or serving benchmark.
- foundation-haystack (unqualified) — It is in scope under the rag-pipeline scope term, but the evidence is source review only (not opened by this lane). There is no financial corpus pipeline, no native run and no performance proof.
- foundation-docling (unqualified) — It is in scope under the document-ingestion scope term, but the evidence is source review only (not opened by this lane). PDF, table and unit extraction quality is unmeasured, and there is no native run.
- foundation-sentence-transformers (unqualified) — It is in scope under the model-sdk scope term, but the evidence is source review only (not opened by this lane). Compatibility with the current vLLM service is not established, and there is no native run.
- ray-serve (unqualified) — It is in scope under the model-serving scope term, but the evidence is source review only (not opened by this lane). There is no distributed performance or failover acceptance, and no demonstrated need at the current single-host research scale.
- shiyu-coder/kronos (unqualified) — It is not adopted, and its packet evidence_refs are empty. A retained source review exists in catalogs/us-equities/star-audit.json (lines 10832-10869: targeted_candidate, source commit 67b630e6, review_level source_review). That review states "No installation, model inference, broker call or native acceptance was performed". It also says the fine-tuning config defaults to Qlib cn_data/csi300 with overlapping lookback ranges, which is "not a turnkey US-equity validation or broker path". No chronological cost-adjusted evaluation was executed.
- tradermonty/claude-trading-skills (unqualified) — It is not adopted, and its packet evidence_refs are empty. A retained source review exists in catalogs/us-equities/star-audit.json (lines 4459-4494: targeted_candidate, source commit 8f787ab2, selected files including skills/backtest-expert/SKILL.md). That review states "No installation, model inference, broker call or native acceptance was performed" and that scripts and data sources still require independent evaluation. It is a financial-research-skills review aid, not a factor or ML evaluator. No retained receipt shows its checklist catching a defect.

Overturn when: Reopen the verdict in either of two cases. First, if `python3 -m unittest discover -s tests -p test_research_evaluation.py -v` (tests/test_research_evaluation.py) fails against blueprints/us-equities/research-evaluation/evaluate.py. Second, if a competing splitter or evaluator is executed on the same frozen blueprints/us-equities/research-evaluation/plan.json inputs, or on the broad-universe protocol (blueprints/us-equities/broad-universe/protocol.json with tests/test_broad_universe_evaluate.py), and it matches skfolio's boundary audit while adding event-interval purge/embargo or cost-aware factor diagnostics that skfolio lacks. Candidate competitors are sktime (c3), scikit-learn TimeSeriesSplit (c22), alphalens-reloaded IC/turnover (c4) and Qlib (c24).

Open gaps:
- The requirement's independent-reconciliation leg is unmet for this layer. The skfolio receipt states "No cash/position/fee/dividend reconciliation or new LEAN engine execution" (receipt.json line 1773). Its independent_review was a read-only code and hash review with no scoring rerun.
- No factor, model or feature library other than skfolio's WalkForward splitter was executed. alphalens, sktime, statsmodels, arch, tsfresh, river, statsforecast, chronos, timesfm and Qlib all rest on source review only.
- The skfolio receipt covers a three-ETF raw-price label control (SPY, QQQ, IWM). It does not cover a point-in-time equity universe, total returns, portfolio P&L or fills.
- The 214-test result is this repository's local suite run under the SDK interpreter (receipt lines 1578-1589). It is not an upstream skfolio test run, so skfolio's own upstream tests were not exercised in the retained evidence.
- WalkForward's six-row gap is not an event-interval purge engine. The receipt states that a six-row gap plus interval assertions does not prove independent samples (line 1776).
- The reserved 2021Q1 segment has been inspected and can no longer be called untouched. With 11 completed episodes per candidate there is no statistical alpha claim, and the selected momentum20 underperformed the equal-weight control after the cost proxy.
- No executed comparison exists between skfolio and any other candidate, so this is a single native proof, not a measured winner.
- In-scope document, RAG, serving and SDK candidates (c9, c14, c17, c21) have no native run. c1 and c19 are native-proven only for narrow retrieval and HTML-conversion cases. c8 is native-proven only for 0.25.0 retrieval serving.
- Kronos (c16) and claude-trading-skills (c13) have only star-audit source reviews with no installation or execution.
- The pin is inconsistent. The card pin and receipt say 1.2.9, the packet evidence_ref README is v1.2.8, and the upstream latest is v1.3.0.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-research-factors-ml-20260922; codex: -)

#### Security and supply chain (security-supply-chain)

- grype @ v0.119.0 — Judged against the layer title and scope terms (security, sbom, secrets, vulnerability-analysis), because the packet notes the requirement text is shared across the group. Only three candidates have retained native execution evidence, and each one covers a different scope term. I reviewed these receipts myself. None of this comes from provider judgment. (1) c4 syft covers the SBOM. blueprints/us-equities/supply-chain/receipt.json (id syft-sdk-inventory-20260919, status passed_scoped_inventory_acceptance) records native Syft 1.52.0. It ran inside a read-only, network-isolated bubblewrap namespace, exited 0 and found 36 Python packages. Package name/version/PURL agreed 36/36 between the Syft and CycloneDX 1.7 outputs, and 36/36 matched installed dist-info. License metadata was present for 34/36 packages and SPDX expressions for 31/36. (2) c2 grype covers vulnerability analysis. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (status passed_scoped_scan_zero_findings, observed 2026-09-22T07:43:37Z) records Syft 1.52.0 plus Grype 0.119.0 run against the pinned NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages). The database was schema v6.1.9, built 2026-09-22T06:30:41Z. All commands exited 0, with runtime_grype_matches 0 and adapter_grype_matches 0. The Grype archive checksum matched both the publisher list and GitHub's asset digest; signature_verified is false. (3) c3 gitleaks covers secrets. evidence/receipts/runtime-tools.json (recorded 2026-09-19T04:55:03Z, kind native_cli_e2e) records a gitleaks exit_code of 0, commits_scanned 22, bytes_scanned 1174704 (approximate), findings 0, and redaction '100 percent'. Of the other adopted candidates, OpenBao (c1) and cosign (c5) have only source_review references to upstream READMEs, and I could not open those. No retained receipt shows either one running.
- syft @ v1.52.0 — Judged against the layer title and scope terms (security, sbom, secrets, vulnerability-analysis), because the packet notes the requirement text is shared across the group. Only three candidates have retained native execution evidence, and each one covers a different scope term. I reviewed these receipts myself. None of this comes from provider judgment. (1) c4 syft covers the SBOM. blueprints/us-equities/supply-chain/receipt.json (id syft-sdk-inventory-20260919, status passed_scoped_inventory_acceptance) records native Syft 1.52.0. It ran inside a read-only, network-isolated bubblewrap namespace, exited 0 and found 36 Python packages. Package name/version/PURL agreed 36/36 between the Syft and CycloneDX 1.7 outputs, and 36/36 matched installed dist-info. License metadata was present for 34/36 packages and SPDX expressions for 31/36. (2) c2 grype covers vulnerability analysis. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (status passed_scoped_scan_zero_findings, observed 2026-09-22T07:43:37Z) records Syft 1.52.0 plus Grype 0.119.0 run against the pinned NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages). The database was schema v6.1.9, built 2026-09-22T06:30:41Z. All commands exited 0, with runtime_grype_matches 0 and adapter_grype_matches 0. The Grype archive checksum matched both the publisher list and GitHub's asset digest; signature_verified is false. (3) c3 gitleaks covers secrets. evidence/receipts/runtime-tools.json (recorded 2026-09-19T04:55:03Z, kind native_cli_e2e) records a gitleaks exit_code of 0, commits_scanned 22, bytes_scanned 1174704 (approximate), findings 0, and redaction '100 percent'. Of the other adopted candidates, OpenBao (c1) and cosign (c5) have only source_review references to upstream READMEs, and I could not open those. No retained receipt shows either one running.
- gitleaks @ v8.30.1 — Judged against the layer title and scope terms (security, sbom, secrets, vulnerability-analysis), because the packet notes the requirement text is shared across the group. Only three candidates have retained native execution evidence, and each one covers a different scope term. I reviewed these receipts myself. None of this comes from provider judgment. (1) c4 syft covers the SBOM. blueprints/us-equities/supply-chain/receipt.json (id syft-sdk-inventory-20260919, status passed_scoped_inventory_acceptance) records native Syft 1.52.0. It ran inside a read-only, network-isolated bubblewrap namespace, exited 0 and found 36 Python packages. Package name/version/PURL agreed 36/36 between the Syft and CycloneDX 1.7 outputs, and 36/36 matched installed dist-info. License metadata was present for 34/36 packages and SPDX expressions for 31/36. (2) c2 grype covers vulnerability analysis. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (status passed_scoped_scan_zero_findings, observed 2026-09-22T07:43:37Z) records Syft 1.52.0 plus Grype 0.119.0 run against the pinned NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages). The database was schema v6.1.9, built 2026-09-22T06:30:41Z. All commands exited 0, with runtime_grype_matches 0 and adapter_grype_matches 0. The Grype archive checksum matched both the publisher list and GitHub's asset digest; signature_verified is false. (3) c3 gitleaks covers secrets. evidence/receipts/runtime-tools.json (recorded 2026-09-19T04:55:03Z, kind native_cli_e2e) records a gitleaks exit_code of 0, commits_scanned 22, bytes_scanned 1174704 (approximate), findings 0, and redaction '100 percent'. Of the other adopted candidates, OpenBao (c1) and cosign (c5) have only source_review references to upstream READMEs, and I could not open those. No retained receipt shows either one running.

Alternatives:
- openbao (unqualified) — Its only evidence is the upstream README URL at v2.6.2, marked source_review, and I could not open it (it is not in the local worktree and I have no web access). The packet's card_limitations say no server config is supplied, no service starts, and no dev-mode recipe is offered. There is no retained receipt showing OpenBao storing, issuing or rotating the broker credential environment variables. The secret-lifecycle role is untested. That means it is not qualified, not that it failed.
- cosign (conditional) — Its only evidence is the upstream README URL at v3.1.3, marked source_review, and I could not open it. Neither retained receipt performed a signature check: signature_verified is false for the Syft archive in blueprints/us-equities/supply-chain/receipt.json and for the Grype archive in scan-nautilus-rc5-20260922/receipt.json. Only checksums were matched. Cosign targets exactly that gap, but no cosign verify run with a pinned identity is recorded. It should become a default only after it is run on a signed upstream artifact.

Overturn when: The verdict changes if either of two things happens. First, a new dated receipt under blueprints/us-equities/supply-chain/ records a native OpenBao run or a cosign verify run that stores or verifies the broker credential environment variables or a release signature with a pinned identity. That would add evidence to one of those candidates and could displace a scanner from the three-winner set. Second, `python3 -m pytest tests/test_supply_chain_scan.py` stops passing on the Grype receipt (commands with nonzero exit, a finding count that does not match the disposition-table length, or a personal-path regression). That would demote c2. A re-scan against a newer Grype database that returns unresolved matches, or a gitleaks re-run on the current repository range with findings or an operational error, would also re-open the verdict for c2 or c3.

Open gaps:
- No release signature or build provenance is verified. signature_verified is false for both the Syft and Grype archives, and only checksums matched.
- No secret-lifecycle management was run. Nothing shows the broker credential environment variables being stored, scoped, rotated or kept out of research workers' reach (the shared-requirement clause about no broker execution authority is unproven for this layer).
- The gitleaks receipt (2026-09-19, 22 commits, 0 findings) does not name the scanned repository or commit range, and it predates the 2026-09-22 supply-chain work. Current-repository secret-scan coverage is not established.
- The Grype zero-match result covers only Python package metadata against the 2026-09-22T06:30:41Z database snapshot. It does not cover bundled Rust/Cython extensions, host OS packages, transitive shared libraries or IBKR-side software. No recurring scan is recorded.
- The Syft inventory (36 packages, equity-worker-sdk) and the Grype runtime scan (21 packages, NautilusTrader venv) are different targets. Whole-host SBOM coverage is not established.
- No license-compliance policy exists. License metadata is present for 34/36 packages and SPDX expressions for 31/36, and some license fields are unparsed.
- The raw SBOM and Grype outputs are kept outside the repository. Only their sha256 hashes and byte counts are recorded, so I could not check the recorded counts against the raw files.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-security-supply-chain-20260922; codex: -)

#### Storage and compute (storage-compute)

- data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa — DuckDB (c4) is the only in-scope storage/compute candidate whose retained evidence records an actual execution. c10 (toon) also has a native CLI roundtrip, but it is a model-context serialization format and is out of scope for this layer.

Native execution (packet evidence_refs):
- blueprints/us-equities/data/receipt.json (kind native_cli_e2e, recorded_date 2026-09-19) records blueprints/us-equities/data/summarize_backtest.py running over bundled LEAN simulated order events. It reports 6 events, 3 distinct orders (filled 3, submitted 3), XNYS sample session 2013-10-07, source_sha256 8e22c0052e1e...192de and parquet_sha256 48ec550a9677...f66d.
- The script refuses to overwrite an existing Parquet output (lines 17-18). It casts fillPrice and fillQuantity to DECIMAL(20, 8) and writes zstd Parquet (lines 20-25). It then reads the Parquet back and counts from the re-read view (lines 26-28).
- blueprints/us-equities/research-runtime/receipt.json (native_model_e2e, observed 2026-09-19T16:21:52Z) records Dagu steps packet and order_table as succeeded, with the same parquet_sha256 48ec550a...f66d. That receipt does not name the script. The link is blueprints/us-equities/research-runtime/prepare-evidence.yaml line 10, where the order_table step runs summarize_backtest.py. So the matching hash shows the same script producing the same bytes from the bundled sample on a second recorded invocation. It is not an independent reproduction: the research-runtime receipt records no source_sha256 and no run id links the two.
- blueprints/us-equities/workers/requirements.txt pins duckdb==1.5.5, matching the packet pin.

Synthetic fixture only: blueprints/us-equities/financial-data/receipt.json offline verification records an exact DECIMAL(38,12) Parquet roundtrip on artificial fixtures. Its live SEC request failed with http_403. Its availability_policy, "max(acceptance_at, first_observed_at of both source snapshots)", is recorded under live_acquisition (line 21), not under the offline checks.

Supplementary native evidence (outside the packet's c4 refs, which I opened this round):
- blueprints/us-equities/catalyst-dataset/native-receipt.json (native_cli_e2e, component_ids edgartools and duckdb 1.5.5): DuckDB materialized retained real SEC header metadata to Parquet, with repeat_parquet_bytes_identical true (line 89). As-of queries returned eligible_counts [0,0,1,4,5] (line 80), and the historical as_of 2020-03-03 gave 0 eligible headers (line 87). That is fail-closed rejection of availability that was not observed.
- blueprints/us-equities/broad-universe/receipt.json records "real entitled provider data (read-only GETs)" (line 6). Its evaluation run used duckdb_version 1.5.5, elapsed_s 71.138, an events.parquet of 3532983 rows and 24195741 bars from 2016-01-04 to 2026-09-18 (lines 1069-1096).

Together these fit the layer terms columnar-compute, parquet and local-store, plus the requirement for reproducible snapshots with availability gating.

Alternatives:
- data-dlt (unqualified) — The only evidence is an upstream README URL (source_review), with no local run. Its card warns that schema inference is not a financial data-quality contract and that watermark-only extraction can miss late revisions. No acquisition or immutable-capture run is retained.
- data-iceberg (conditional) — The only evidence is a README URL (source_review). Its card states that creating a catalog would not prove append, multi-writer conflict handling, cross-engine compatibility or time travel, and none of these was executed. The group overturn text allows a lake only after local throughput or concurrency measurements justify it, and no such measurement is retained.
- ray-serve (out_of_scope) — Distributed compute and model serving do not address storage of source-identifiable observations or exact snapshots. The evidence is a README URL only, and its card says no distributed performance or failover acceptance was performed.
- QuestDB (conditional) — A server-based time-series store with source_review evidence only. Its card says the catalog did not install or start a server and that dedup/upsert can overwrite corrections. Replacing embedded DuckDB would need local throughput or concurrency measurements, and none is retained.
- ClickHouse (conditional) — The evidence is a README URL only. Its card says the local SQL command is prospective, with no server, cluster, throughput or reliability evidence, and that eventual merges and deduplication are not an immutable revision ledger. The pin is behind upstream: v26.8.7.19-lts is pinned against the latest v26.9.2.8-stable.
- data-arrow (overlap) — Arrow is an interchange format and library, and its card warns that time units and encodings can be coerced during conversion. Its only evidence is a README URL. The retained native Parquet write and read-back ran through DuckDB (summarize_backtest.py lines 20-28; catalyst-dataset native-receipt.json line 49 entrypoints), not through a separately evidenced Arrow path.
- Pandera (conditional) — Pandera would complement storage as a schema-contract gate before a snapshot is promoted, but it is not a store or compute engine. Its card says the demonstration checked only synthetic keys and quantities and that fail-closed promotion is still implementation work. The packet's evidence ref is a README URL only.
- foundation-toon (out_of_scope) — Toon is a compact serialization format for model context, not storage or compute for market data. It does have a native execution: evidence/receipts/portable-cli-artifacts.json records a CLI encode/decode fixture roundtrip with toon_roundtrip_equal true. evidence/receipts/component-history.json records native_claude and native_codex as 'not independently demonstrated', and a nested fixture that grew from 69 to 94 tokens.
- data-feast (conditional) — A feature store with README-only evidence. Its card says event-time point-in-time retrieval does not exclude late corrections, and that materialization freshness and skew need separate operational evidence. No local run is retained.

Overturn when: Two checks could change the verdict.

1. Regression check (runnable now in the DuckDB-adopted environment): the DuckDB class in tests/test_catalyst_dataset.py. It is skipped unless duckdb imports (line 189) and covers deterministic Parquet, exclusive materialization and refusal of null or backdated availability. The second part of this check is the repeat materialize/query sequence of blueprints/us-equities/catalyst-dataset/dataset.py recorded in blueprints/us-equities/catalyst-dataset/native-receipt.json lines 77-80. If the pinned DuckDB 1.5.5 stopped producing byte-identical repeat Parquet, or stopped returning eligible_counts [0,0,1,4,5] for the recorded as-of values, c4 would lose its reproducibility and availability-gating basis.

2. Store comparison (not runnable as written): no harness exists that runs DuckDB against QuestDB, ClickHouse, Iceberg or Arrow+Pandera on the same real snapshot. summarize_backtest.py takes LEAN order-event JSON (lines 14, 20). tests/test_financial_data.py uses fixtures built into the module. Both need new code before they can take a market-data snapshot. Such a harness, applied to the retained real-provider bar set behind blueprints/us-equities/broad-universe/receipt.json, would overturn DuckDB if an alternative met a stated ingest/query latency or concurrent-reader requirement that embedded DuckDB misses while preserving exact decimal/UTC values and fail-closed availability. An Arrow or Pandera path would be added as a co-winner only if it supplied a fail-closed schema or availability gate that DuckDB lacks.

Open gaps:
- Within the packet's c4 evidence_refs, no licensed market-data acquisition reached this layer. blueprints/us-equities/financial-data/receipt.json records the live SEC request as http_403 (lines 22, 30-35). Outside those refs, blueprints/us-equities/catalyst-dataset/native-receipt.json covers DuckDB over retained real SEC header metadata, and blueprints/us-equities/broad-universe/receipt.json covers DuckDB over real entitled provider daily bars. Neither establishes feed entitlement, survivorship-free coverage or complete history (packet limitations, lines 384 and 387).
- The packet's own native DuckDB run covers 6 bundled LEAN simulated order events and one XNYS session. It does not cover market observations, feed identity or corporate actions (blueprints/us-equities/data/receipt.json).
- Historical point-in-time reconstruction is not established. financial-data/receipt.json line 24 records historical_point_in_time_reconstruction false. In catalyst-dataset/native-receipt.json, availability rejection covers observation cutoffs only: the retained run's first observation is not historical dissemination (limitations line 10).
- No comparative throughput, concurrency or scale measurement exists for any store. The only DuckDB scale observation is a single run: broad-universe/receipt.json lines 1072-1078 record elapsed_s 71.138 for an evaluation that wrote a 3532983-row events.parquet. It was not compared against another store.
- Decimal/timestamp schema enforcement and immutable snapshot selection remain application responsibilities (c4 card limitation, packet line 103).
- The research-runtime receipt's matching parquet_sha256 comes from the same script over the same bundled sample. It is not an independently sourced reproduction.
- No comparison was executed between DuckDB and Arrow, QuestDB, ClickHouse or Iceberg, and no harness exists for one.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-storage-compute-20260922; codex: -)
<!-- verdicts:end -->
