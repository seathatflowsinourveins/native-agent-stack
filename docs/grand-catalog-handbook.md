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
evidence and challenger angles, with one revision round after any refutation.
The record tool then applied the rules in code: every recorded winner must name
its evidence class and the reason it beats the alternatives, and the tool derives
its platform status from that evidence class and supplies its install anchor. The dated
[convergence manifest](../catalogs/sota-convergence/manifest-20260922.json) was
refreshed from the same day's lane run. Sealed lane returns are under
`evidence/artifacts/layer-verdicts-20260922/claude/`.

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
3. Build stripped packets per layer with `lane_packets.py`, each carrying that
   layer's own candidates. Then run the Claude lane through the saved
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
- **Trading packets carried group-level candidates.** Every trading packet was
  built from its group's shared candidate list, not the layer's own tools. Four
  rows record the resulting mismatch in their `open_gaps`:
  - `security-supply-chain` recorded Codex SDK, Dagu and OpenTelemetry instead of
    Syft, Grype and Gitleaks.
  - `data-quality-orchestration` has no Pandera candidate.
  - `evaluation-experiments` omits Inspect AI, promptfoo and MLflow.
  - `agents-models-workers` carries the research-memory candidates.

  Treat these four winners as unreliable, and the other eight trading rows as
  drawn from a group-wide set, until the packets are rebuilt with
  layer-specific candidates and the lane is rerun. Until then, the trading cards
  and the gate ladder are the reference for those layers.
- **Recorded pins can lag.** The trading `agents-models-workers` row cites older
  foundation pins, for example ai-memory 2.3.1 and Serena 1.7.0. The convergence
  manifest owns current versions.
- **Evidence strength varies by row.** Three foundation winners and three trading
  winners are `source_review` only, and no winner rests on a
  `measured_comparison`. Every `keep_but_compare` row names the comparison it
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
| agents-models-workers | foundation-memory | recorded | foundation-ai-memory @ v2.3.1; foundation-serena @ v1.7.0; foundation-qmd @ v2.8.3 | native_proven | 18 | Only one retained check is runnable today: the frozen QMD baseline, `CI=true node blueprints/us-equities/retrieval-eval… | catalogs/us-equities/foundation-memory.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| backtesting-engine | engines-strategies | recorded | nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e); lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f | local_integration | 15 | Reopen the verdict if any of these occurs:

1. Nautilus fails the frozen SPY/LEAN parity comparison after the distribut… | blueprints/us-equities/engine/README.md, catalogs/us-equities/runtime-target.json | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| data-quality-orchestration | agents-operations | recorded | candidate:anthropics-claude-code @ unpinned; dagu @ v2.16.6; loki @ v3.7.8 | native_proven | 18 | Any of the following would change the verdict.

- c2 over c9: a fresh native run of blueprints/us-equities/workers/nati… | blueprints/us-equities/hosting/README.md, docs/foundation-closure-20260921.md, observability/backends/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| evaluation-experiments | agents-operations | recorded | codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0; candidate:anthropics-claude-code @ unpinned; dagu @ v2.16.6 | native_proven | 17 | The verdict changes if a challenger passes an executed comparison under the same conditions. The challenger would be De… | blueprints/us-equities/hosting/README.md, catalogs/us-equities/agents-operations.json, docs/foundation-closure-20260921.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| execution-broker | engines-strategies | recorded | nautilus-ibkr-adapter @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e); alpaca-py @ 0.44.0; lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f | source_review | 11 | Reopen the verdict if either of these checks fails.

(1) SPY/LEAN parity: a qualified rerun of the preregistered compar… | blueprints/us-equities/engine/README.md, blueprints/us-equities/order-contract/README.md, catalogs/us-equities/runtime-target.json | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| identity-provenance | data-research | recorded | alpaca-py @ 0.44.0; data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa; data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a | native_proven | 12 | An executed comparison on one frozen plan of representative securities would change the verdict. The plan must include … | blueprints/us-equities/order-contract/README.md, catalogs/us-equities/data-research.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| market-data-reference | data-research | recorded | data-alpaca-py @ v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28; data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa; data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a | native_proven | 13 | Acquisition (c9): the repository currently has no runnable challenger arm. blueprints/us-equities/authenticated-data/co… | catalogs/us-equities/data-research.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| observability-hosting | agents-operations | recorded | codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0; dagu @ v2.16.6; opentelemetry-collector-contrib @ v0.161.0 | native_proven | 16 | Two checks could change the verdict.

Worker choice (c7 vs c19): run the Claude worker in blueprints/us-equities/resear… | blueprints/us-equities/hosting/README.md, catalogs/us-equities/agents-operations.json, observability/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| portfolio-risk | engines-strategies | recorded | nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e); lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f; alpaca-py @ 0.44.0 | local_integration | 9 | Reopen the winner set in any of these cases:
- The preregistered SPY/LEAN one_zero replay fails the $0.01 absolute-tole… | blueprints/us-equities/engine/README.md, blueprints/us-equities/order-contract/README.md, catalogs/us-equities/runtime-target.json | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| research-factors-ml | engines-strategies | recorded | skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee; nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e); lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f | native_proven | 9 | Research winner (c13): overturn it if Qlib (c11) or vectorbt (c8) is run under the same frozen contract as blueprints/u… | blueprints/us-equities/engine/README.md, blueprints/us-equities/research-evaluation/README.md, catalogs/us-equities/runtime-target.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| security-supply-chain | agents-operations | recorded | codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0; dagu @ v2.16.6; opentelemetry-collector-contrib @ v0.161.0 | native_proven | 15 | This verdict holds only for the packet's current candidate set, and the choice between c14 and c9 for the third slot re… | blueprints/us-equities/hosting/README.md, catalogs/us-equities/agents-operations.json, observability/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| storage-compute | data-research | recorded | data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa; alpaca-py @ 0.44.0 | native_proven | 12 | The existing scripts cannot run a challenger as they stand. replay.py and sample.py import duckdb and have no backend o… | blueprints/us-equities/order-contract/README.md, catalogs/us-equities/data-research.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |

### us-equities (per-layer narrative)

#### Agents, models and workers (agents-models-workers)

- foundation-ai-memory @ v2.3.1 — This verdict is my own source review of the retained receipts. No TypeSafe inference results were supplied, and the packet withholds prior provider decisions.

The packet requirement (line 528) reads: 'Keep durable project knowledge, exact code and dated financial sources retrievable across native clients, with source recovery, explicit project scope and measurable retrieval quality.'

Revision: Serena (c9) replaces SocratiCode (c2) in the code slot. The requirement says 'exact code'. My earlier paraphrase, 'exact/conceptual', was not in the requirement. The catalog assigns exact symbol bodies and references to Serena (foundation-memory.json lines 221-223) and conceptual search to SocratiCode (lines 178-180).

(1) ai-memory (c19), durable project knowledge. In evidence/receipts/native-memory.json, native Codex 0.155.1 and Claude 2.1.277 each exited 0 after retrieving the same scoped durable page, and cross_client_handoff_received=true. In blueprints/us-equities/state-recovery/memory/receipt.json, an encrypted same-host Restic restore passed: 324 files, integrity_check ok, all 56 table counts matched. In evidence/receipts/foundation-native-20260920.json (memory_rag.ai_memory), scoped status, query and page retrieval passed.

(2) Serena (c9), exact code with source recovery. In foundation-native-20260920.json line 80, eight symbol/source/reference checks passed across fresh codex and claude-code MCP server contexts, and the exact Python parse_codex and CJS collect[0] source matched. That is native execution with exact-source equivalence in both clients.

(3) QMD (c13), measurable retrieval quality. It is the only candidate with a measured retrieval-quality result. In blueprints/us-equities/retrieval-evaluation/receipt.json, the pinned upstream runBenchmark API ran BM25-only over 12 frozen queries: exact recall@3 8/12, recall@1 5/12, MRR 0.56875, 4 misses retained, 0 model calls.

The 'dated financial sources' part is not covered by any winner on the evidence. QMD's rank-1 hit for the SEC-cutoff query is a project policy document (financial-data/README.md), not a dated filing. foundation-memory.json line 1048 notes that installed code search does not imply a financial-document corpus exists.

These are the best-evidenced lanes, not a measured head-to-head winner set; no alternative ran on the same fixture.
- foundation-serena @ v1.7.0 — This verdict is my own source review of the retained receipts. No TypeSafe inference results were supplied, and the packet withholds prior provider decisions.

The packet requirement (line 528) reads: 'Keep durable project knowledge, exact code and dated financial sources retrievable across native clients, with source recovery, explicit project scope and measurable retrieval quality.'

Revision: Serena (c9) replaces SocratiCode (c2) in the code slot. The requirement says 'exact code'. My earlier paraphrase, 'exact/conceptual', was not in the requirement. The catalog assigns exact symbol bodies and references to Serena (foundation-memory.json lines 221-223) and conceptual search to SocratiCode (lines 178-180).

(1) ai-memory (c19), durable project knowledge. In evidence/receipts/native-memory.json, native Codex 0.155.1 and Claude 2.1.277 each exited 0 after retrieving the same scoped durable page, and cross_client_handoff_received=true. In blueprints/us-equities/state-recovery/memory/receipt.json, an encrypted same-host Restic restore passed: 324 files, integrity_check ok, all 56 table counts matched. In evidence/receipts/foundation-native-20260920.json (memory_rag.ai_memory), scoped status, query and page retrieval passed.

(2) Serena (c9), exact code with source recovery. In foundation-native-20260920.json line 80, eight symbol/source/reference checks passed across fresh codex and claude-code MCP server contexts, and the exact Python parse_codex and CJS collect[0] source matched. That is native execution with exact-source equivalence in both clients.

(3) QMD (c13), measurable retrieval quality. It is the only candidate with a measured retrieval-quality result. In blueprints/us-equities/retrieval-evaluation/receipt.json, the pinned upstream runBenchmark API ran BM25-only over 12 frozen queries: exact recall@3 8/12, recall@1 5/12, MRR 0.56875, 4 misses retained, 0 model calls.

The 'dated financial sources' part is not covered by any winner on the evidence. QMD's rank-1 hit for the SEC-cutoff query is a project policy document (financial-data/README.md), not a dated filing. foundation-memory.json line 1048 notes that installed code search does not imply a financial-document corpus exists.

These are the best-evidenced lanes, not a measured head-to-head winner set; no alternative ran on the same fixture.
- foundation-qmd @ v2.8.3 — This verdict is my own source review of the retained receipts. No TypeSafe inference results were supplied, and the packet withholds prior provider decisions.

The packet requirement (line 528) reads: 'Keep durable project knowledge, exact code and dated financial sources retrievable across native clients, with source recovery, explicit project scope and measurable retrieval quality.'

Revision: Serena (c9) replaces SocratiCode (c2) in the code slot. The requirement says 'exact code'. My earlier paraphrase, 'exact/conceptual', was not in the requirement. The catalog assigns exact symbol bodies and references to Serena (foundation-memory.json lines 221-223) and conceptual search to SocratiCode (lines 178-180).

(1) ai-memory (c19), durable project knowledge. In evidence/receipts/native-memory.json, native Codex 0.155.1 and Claude 2.1.277 each exited 0 after retrieving the same scoped durable page, and cross_client_handoff_received=true. In blueprints/us-equities/state-recovery/memory/receipt.json, an encrypted same-host Restic restore passed: 324 files, integrity_check ok, all 56 table counts matched. In evidence/receipts/foundation-native-20260920.json (memory_rag.ai_memory), scoped status, query and page retrieval passed.

(2) Serena (c9), exact code with source recovery. In foundation-native-20260920.json line 80, eight symbol/source/reference checks passed across fresh codex and claude-code MCP server contexts, and the exact Python parse_codex and CJS collect[0] source matched. That is native execution with exact-source equivalence in both clients.

(3) QMD (c13), measurable retrieval quality. It is the only candidate with a measured retrieval-quality result. In blueprints/us-equities/retrieval-evaluation/receipt.json, the pinned upstream runBenchmark API ran BM25-only over 12 frozen queries: exact recall@3 8/12, recall@1 5/12, MRR 0.56875, 4 misses retained, 0 model calls.

The 'dated financial sources' part is not covered by any winner on the evidence. QMD's rank-1 hit for the SEC-cutoff query is a project policy document (financial-data/README.md), not a dated filing. foundation-memory.json line 1048 notes that installed code search does not imply a financial-document corpus exists.

These are the best-evidenced lanes, not a measured head-to-head winner set; no alternative ran on the same fixture.

Alternatives:
- SocratiCode (conditional) — It complements Serena as the conceptual code lane; the requirement's term is 'exact code'. Its native evidence is one limit=1 codebase_search per client, both returning tools/ecosystem/linux-usage-report.cjs lines 2-39 at score 0.6429 (native-rag.json lines 30-38 and 51-62). A cosine score is not a quality measure, and no recall or MRR receipt exists for it. Its advantages over Serena are automatic watcher freshness (add/update/delete with no tool call, native-rag.json lines 113-136) and a Desktop direct path (desktop-direct-rag.json). Neither freshness nor conceptual search is a term of the requirement. The Qdrant restore point counts (symbol_files 23, code_vectors 139) coincide with the SocratiCode index (graph_files 23, chunks 139). However, the receipt states it is 'not a semantic retrieval benchmark or SocratiCode MCP rebinding test' (qdrant/receipt.json line 57), so SocratiCode source recovery after restore is unestablished. It is AGPL-3.0. Keep it as a conceptual/freshness lane, not the exact-code winner.
- Qdrant (overlap) — It is the vector substrate under SocratiCode, not a retrieval interface. Its encrypted restore passed: 5 green collections, 201 points, exact-query ordered ids and scores matched, maximum_score_delta 0.0 (qdrant/receipt.json lines 27-37). It was one same-host drill with no off-host durability or key escrow (line 55), and it is not a retrieval-quality benchmark (line 57). No financial-document corpus is indexed.
- Context Mode (out_of_scope) — It is a token-efficiency sandbox for large tool output, not a durable knowledge or source-retrieval store. native-context-memory.json records native ctx_execute_file and ctx_stats calls completing. foundation-native-20260920.json holds only retained event-count estimates, which it says are not measured provider usage. No retrieval-quality result exists. The license differs between sources: the packet says NOASSERTION and the catalog says Elastic-2.0.
- RTK (out_of_scope) — It compacts CLI output; it does not retrieve knowledge. native-token-ci-github-20260920.json shows `rtk proxy` stdout with the same raw hash as plain git, and a gain ledger going from 0 to 3 commands and 6 estimated tokens. In portable-userspace-install-20260921.json, attempt 05 failed extraction under root mapping and a later unprivileged run passed. foundation-native-20260920.json records a failed compression-preview fidelity check.
- Headroom (measured_tradeoff) — It compresses context; it is not a retrieval store, and the catalog decision is 'alternative'. docs/token-efficiency-stack.md line 37 records a clean-prefix trial of 9,616->2,128 estimated tokens with exact recovery. Line 140 records that compression plus full recovery grew 5,105->18,777. The default ledger shows 0 saved, and the proxy/SDK path is unexecuted.
- Docling (conditional) — Source review only; the catalog marks it 'conditional'. It is the relevant ingestion candidate for the uncovered dated-financial-source gap (filing PDFs), but no install, run or table/unit extraction quality is recorded.
- Haystack (conditional) — Source review only. The catalog records 'No financial corpus pipeline or performance proof yet' (foundation-memory.json line 975). It would add a framework without a measured gain.
- LlamaIndex (unqualified) — Source review only; the catalog marks it 'alternative'. Integration maintenance needs reassessment (foundation-memory.json line 1012), and no local execution is recorded.
- Hindsight (unqualified) — It is named a 'Priority challenger' (docs/candidate-quality-review-20260921.md line 65), but its only evidence is a pinned source review: no install, no matched recall comparison, no recovery acceptance. Retention and reflection need a model.
- Basic Memory (conditional) — It is a priority challenger, with 'Pinned source review only ... no new install, upstream test execution, native model operation, matched answer-quality comparison or recovery acceptance' (candidate-quality-review.json line 442). AGPL fit is unreviewed.
- Claude-mem (overlap) — It overlaps the ai-memory cross-harness capture, and the docs advise against running overlapping stores. Source review only. The online observer flow documents a 30-day trial (foundation-memory.json lines 649 and 672).
- Letta Code (unqualified) — It is a separate stateful harness, 'not a transparent memory plugin for Codex/Claude' (foundation-memory.json line 937). Source review only.
- Supermemory (conditional) — Source review only; the catalog says it is not installed and duplicate automatic capture should be avoided. Local startup can print a generated API key. Export/restore and isolation are unqualified.
- OpenViking (conditional) — Source review only: 'No migration from ai-memory or measured token improvement performed'. The server is AGPL from v0.3, and it needs embedding and VLM configuration.
- Graphiti (conditional) — A temporal-graph candidate for issuer relations with 'no graph deployment or extraction accuracy proof here'. It needs a Neo4j/FalkorDB backend and an LLM, and it cannot invent historical source availability.
- Cognee (conditional) — A source-review-only research-corpus candidate. Its default LLM example uses OpenAI, and its OSS PostgreSQL graph store is described as a demo (foundation-memory.json line 559).
- Mem0 (conditional) — Not adopted. Source review only: 'no local financial-memory quality or savings evaluation', and extraction adds model calls. There is no evidence it fits better than ai-memory.
- LightRAG (unqualified) — Not adopted. Source review only. The catalog says graph retrieval is not automatically more accurate or cheaper than lexical+dense search, and no filing comparison has been run.

Overturn when: Only one retained check is runnable today: the frozen QMD baseline, `CI=true node blueprints/us-equities/retrieval-evaluation/run-bm25.mjs --package $QMD_PACKAGE --snapshot <new private dir>/catalog-snapshot.sqlite --fixture blueprints/us-equities/retrieval-evaluation/fixture.json --output <new path>` (README.md line 125). The script accepts only the reviewed 12-query us-equities-foundation fixture, QMD 2.8.3 and the bm25 backend (run-bm25.mjs lines 23, 26-27 and 39). The QMD lane verdict changes if that rerun exits with status retrieval_execution_error or no longer reproduces exact recall@3 8/12 and MRR 0.56875 against the recorded fixture_sha256.

No runnable challenger comparison exists yet. A challenger can only overturn a winner after a new harness is built and executed. It needs a separate held-out fixture with its own hash, frozen before running, with fixed relevance judgments over financial filings, code and project memory (README.md lines 92-95). Each arm runs at the same context budget. The verdict changes if a challenger improves exact-source recall@3/MRR, answer fidelity and abstention at equal or lower measured cost. It must also keep zero project-isolation violations, native Codex/Claude behavior and encrypted restore equivalence, following the blueprints/us-equities/state-recovery/memory/receipt.json pattern.

Challenger pairings: Hindsight and Basic Memory against ai-memory; SocratiCode against Serena on exact-symbol recovery; hybrid QMD against BM25 QMD. The Serena selection also changes if a rerun of its eight fresh-context symbol/source/reference checks no longer matches exact source.

Open gaps:
- The packet's label does not match its content. layer_id is 'agents-models-workers', but the requirement and all 21 candidates come from the foundation-memory group (packet lines 518-519; limitation line 526: foundation-memory, 28 entries, was chosen over agents-operations, 10, by entry count). The winners are memory, retrieval and code-retrieval tools. They must not be published as the agent/model/worker selection. codex-native-sdk, vllm, codex-acp, deerflow, langgraph, omniroute and others appear only in sota_components_not_in_candidates and remain unjudged by this verdict.
- Dated financial sources are not covered by any winner. No filing corpus is indexed, and dated-source as-of retrieval has not been exercised. QMD's SEC-cutoff hit is a policy document (retrieval-evaluation/receipt.json; foundation-memory.json line 1048).
- No held-out, multi-arm retrieval harness exists. run-bm25.mjs is locked to the frozen 12-query fixture, QMD 2.8.3 and BM25, so no challenger comparison is currently runnable.
- No matched head-to-head was run between any winner and any alternative. A source-only candidate has not failed.
- The only retrieval-quality measurement covers 12 curated queries, BM25 only, with 8/12 recall@3 and 4 misses. It is not an independent holdout and not answer accuracy.
- Serena has no recall or quality-rate measurement. Its evidence is eight pass/fail exact-match checks. SocratiCode has no quality measurement either, so the Serena-over-SocratiCode choice rests on the requirement's wording and the catalog roles, not on a measured comparison.
- Serena's installed version, 2.0.0.dev0 @ c6fbd1c, differs from the v1.7.0 pin (foundation-memory.json lines 245 and 251). An already-loaded Desktop connection does not reload its language settings (foundation-native-20260920.json line 33). Serena has no restore or watcher-freshness evidence.
- Restore evidence for ai-memory and Qdrant is same-host only, with no off-host durability, key escrow or new-host client rebinding. The Qdrant restore is not a SocratiCode MCP rebinding test.
- The ai-memory pin, v2.3.1, is behind upstream v2.4.0, and the receipts record 2.3.2 against the catalog's 2.3.1.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-agents-models-workers-20260922; codex: -)

#### Backtesting engine (backtesting-engine)

- nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e) — The requirement names NautilusTrader as the destination and LEAN as the oracle to preserve. These are the only two adopted candidates with executed engine evidence in the retained receipts.

c15 NautilusTrader 2.0.0rc5 (commit 1b0a49d):
- Native upstream evidence is synthetic FX only. evidence/receipts/native-nautilus-v2-20260920.json records the unchanged upstream synthetic EUR/USD quickstart, run natively in two isolated offline runs (run-3 and run-4). Each produced 902 orders, 902 fills and 451 positions, with 1000431.00000 USD ending cash and realized PnL reconciled in decimal to 431.00 USD. account.csv was byte-identical across the two runs; the other reports matched after UUID normalization. Two earlier attempts that returned empty reports remain on record as unsuccessful.
- The US-equity evidence is local integration, not native upstream. blueprints/us-equities/engine-nautilus/equity-replay/receipt.json (line 4: 'local integration with retained historical data; not an unchanged upstream test or broker execution') covers retained Alpaca AAPL SIP daily bars: 15 sessions, 2020-08-10 to 2020-08-28.
  - Baseline: 10 filled orders, 5 positions, -133.40 USD realized PnL, 99866.60 USD ending cash.
  - fee_slippage_stress: 10.00 USD fees, -144.40 USD realized PnL.
  - Both scenarios: 10 cash transitions verified and realized PnL reconciled. A separate reviewer recomputed every CSV cash transition, and all 8 local tests passed (exit 0).

c4 LEAN (commit 985ef30):
- blueprints/us-equities/historical-simulation/receipt.json records six frozen native SPY simulations from 2019-12-02 to 2020-04-30, each over 1457 data points. The five invested scenarios finished flat with native fill, fee and dividend cash reconciliation. over_limit got one native buying-power rejection and zero fills.
- blueprints/us-equities/engine/resolution-receipt.json shows the patched full-solution build (exit 0, 0 errors). The unchanged bundled backtest completed with 3943 data points, 3 orders and an order-list hash matching the original.

catalogs/us-equities/runtime-target.json names Nautilus as the destination and keeps LEAN as the comparison engine.

The winner evidence class is local_integration, not native_proven. That is the weakest class carrying the requirement's core claim (reproducible equity accounting on the destination engine). Destination-vs-oracle parity is not established: the only executed SPY/LEAN parity run is the one_zero case. It returned BLOCKED with 4 failed checks (evidence/artifacts/comparison-progress-20260922/summary.json lines 172-187). The other five frozen scenarios have not been run.

This winner set does not cover the requirement's 'broker-specific execution boundaries'. The Alpaca paper boundary is evidenced only through c14 alpaca-py in the broker/reconciliation layer, and the IBKR boundary is not established (runtime-target.json local_broker_acceptance not_established).
- lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f — The requirement names NautilusTrader as the destination and LEAN as the oracle to preserve. These are the only two adopted candidates with executed engine evidence in the retained receipts.

c15 NautilusTrader 2.0.0rc5 (commit 1b0a49d):
- Native upstream evidence is synthetic FX only. evidence/receipts/native-nautilus-v2-20260920.json records the unchanged upstream synthetic EUR/USD quickstart, run natively in two isolated offline runs (run-3 and run-4). Each produced 902 orders, 902 fills and 451 positions, with 1000431.00000 USD ending cash and realized PnL reconciled in decimal to 431.00 USD. account.csv was byte-identical across the two runs; the other reports matched after UUID normalization. Two earlier attempts that returned empty reports remain on record as unsuccessful.
- The US-equity evidence is local integration, not native upstream. blueprints/us-equities/engine-nautilus/equity-replay/receipt.json (line 4: 'local integration with retained historical data; not an unchanged upstream test or broker execution') covers retained Alpaca AAPL SIP daily bars: 15 sessions, 2020-08-10 to 2020-08-28.
  - Baseline: 10 filled orders, 5 positions, -133.40 USD realized PnL, 99866.60 USD ending cash.
  - fee_slippage_stress: 10.00 USD fees, -144.40 USD realized PnL.
  - Both scenarios: 10 cash transitions verified and realized PnL reconciled. A separate reviewer recomputed every CSV cash transition, and all 8 local tests passed (exit 0).

c4 LEAN (commit 985ef30):
- blueprints/us-equities/historical-simulation/receipt.json records six frozen native SPY simulations from 2019-12-02 to 2020-04-30, each over 1457 data points. The five invested scenarios finished flat with native fill, fee and dividend cash reconciliation. over_limit got one native buying-power rejection and zero fills.
- blueprints/us-equities/engine/resolution-receipt.json shows the patched full-solution build (exit 0, 0 errors). The unchanged bundled backtest completed with 3943 data points, 3 orders and an order-list hash matching the original.

catalogs/us-equities/runtime-target.json names Nautilus as the destination and keeps LEAN as the comparison engine.

The winner evidence class is local_integration, not native_proven. That is the weakest class carrying the requirement's core claim (reproducible equity accounting on the destination engine). Destination-vs-oracle parity is not established: the only executed SPY/LEAN parity run is the one_zero case. It returned BLOCKED with 4 failed checks (evidence/artifacts/comparison-progress-20260922/summary.json lines 172-187). The other five frozen scenarios have not been run.

This winner set does not cover the requirement's 'broker-specific execution boundaries'. The Alpaca paper boundary is evidenced only through c14 alpaca-py in the broker/reconciliation layer, and the IBKR boundary is not established (runtime-target.json local_broker_acceptance not_established).

Alternatives:
- Qlib (conditional) — A factor/ML research workflow, not an execution engine. The evidence is source review only and the native workflow is 'Prospective and unexecuted'. The reviewed config defaults to China/CSI300, and use is conditional on a point-in-time US dataset (data-research.json). It has no execution adapter and no run on the frozen inputs.
- Zipline Reloaded (overlap) — A second event-driven engine overlapping Nautilus and LEAN; the card says to avoid a second event engine without a specific need. The workflow is unexecuted: no install, no bundle ingestion and no run on the frozen SPY plan. No Alpaca route is verified.
- ib_async (out_of_scope) — An IBKR client SDK, not a backtesting engine. runtime-target.json selects the Nautilus native IBKR adapter for that boundary. The workflow is unexecuted, and IBKR local_broker_acceptance is not_established.
- Dockerized IB Gateway (conditional) — A gateway hosting option, not an engine. hosting-practice.json records it as conditional with native_acceptance not_established. Image digest, sign-in, restart, connectivity and reconciliation are unqualified. docs/hosting-container-practice.md keeps a native external TWS/IB Gateway as a valid path.
- Lumibot (unqualified) — Source review only; the Yahoo backtest workflow is unexecuted. The license conflict is unresolved: the LICENSE file says GPL-3.0 but setup.py declares MIT. The card keeps it as an alternative, 'not a second active engine'.
- skfolio (out_of_scope) — A portfolio model-selection complement, not an engine. The native receipt covers a raw-price label study (20 folds plus one reserved 2021Q1 evaluation), 'not new LEAN execution or portfolio P&L'. The 1.2.9 pin is behind upstream v1.3.0.
- vectorbt (conditional) — Vectorized research sweeps only; the card says selected strategies must be rechecked in the event engine. The evidence is source review with an unexecuted workflow. The license is Apache-2.0 plus Commons Clause. It has no order-state or reconciliation evidence.
- PyPortfolioOpt (out_of_scope) — An allocation optimizer that produces proposed weights, not an engine. The workflow is unexecuted, and the card prefers skfolio when model selection is central.
- LEAN Alpaca brokerage (conditional) — A broker adapter for the LEAN oracle path. Native evidence is compilation only: both builds exited 0. The adapter was never initialized and 0 broker orders were submitted. The unmodified build resolved 2 advisory pairs.
- alpaca-py (out_of_scope) — The Alpaca broker-boundary SDK, not a backtesting engine. It covers the requirement's broker-boundary clause in the broker/reconciliation layer, not this winner set. The paper receipt shows one SPY long-to-flat roundtrip: 2 writes, -0.08 USD cash-matched, and 0 additional writes on recovery. It does not test historical simulation.
- Backtrader (unqualified) — Not adopted. The latest release and HEAD date from 2023, the examples use dated Yahoo/IBPy integrations, and the workflow is unexecuted source review.
- backtesting.py (unqualified) — Not adopted. A single-instrument OHLC prototyping engine, which the card calls 'not the portfolio execution/reconciliation host'. It is AGPL-3.0, and its workflow is unexecuted.
- FinRL (out_of_scope) — Not adopted, with card decision 'watch' (engines-strategies.json lines 510-543). It is an educational RL train/test/trade framework, kept as an experimental benchmark and 'not a production execution default'. The workflow is 'Prospective and unexecuted', and the README redirects deployment work to FinRL-Trading. It has no fill-realism or reconciliation evidence.
- TradingAgents (out_of_scope) — Not adopted, with card decision 'watch' (engines-strategies.json lines 1582-1617). It is a multi-agent LLM analysis framework that 'rather than replace deterministic engine/risk code'. The workflow is unexecuted, no model calls were made, and it has no historical-data correctness audit. Its simulated exchange does not prove execution.
- cvxportfolio (out_of_scope) — Listed in the packet's sota_components_not_in_candidates with review_status unmaintained_signal. Its card (engines-strategies.json lines 856-887) is a cost-aware multi-period portfolio simulator marked conditional. It has an unexecuted workflow and states 'Research simulator is not an order gateway'. It is GPL-3.0-or-later.

Overturn when: Reopen the verdict if any of these occurs:

1. Nautilus fails the frozen SPY/LEAN parity comparison after the distributions_and_cash and market_on_open_proxy mappings are implemented. The comparison is frozen in blueprints/us-equities/engine-nautilus/acceptance-plan.md sections 1-3: start with one_zero, then run the remaining five scenarios in blueprints/us-equities/historical-simulation/plan.json against the LEAN outputs audited by `python3 blueprints/us-equities/historical-simulation/analysis.py --run $PRIVATE_RUN`. Tolerance is at most $0.01 absolute per value, with no post-result widening. Today only one_zero has run, and it is BLOCKED with 4 failed checks; the other five scenarios are unexecuted.

2. The parity worktree records that either mapping cannot be expressed in Nautilus. An example is a dividend SimulationModule that cannot post dividend cash in the one_zero case (engines-strategies.json line 191).

3. A maintained alternative engine passes the same frozen plan and failure contract with fewer failed checks. The contract includes the report-corruption and admission cases in tests/test_nautilus_equity_replay.py (`python3 -m unittest tests.test_nautilus_equity_replay -v`).

Open gaps:
- SPY/LEAN parity is not established. Only the one_zero case has been executed: it returned a completed BLOCKED comparison with returned_failed_checks 4 and publication_eligible false, limited to 'Source-host historical one_zero case only' (summary.json lines 172-187; runtime-target.json line 115). one_stress, two_zero, two_stress, adaptive_stress and over_limit (plan.json lines 19-23) have not been run. acceptance-plan.md line 16 still lists the frozen SPY comparison as 'Planned, not executed'.
- NautilusTrader 2.0.0rc5 is a prerelease, and 2.0.0 final has not shipped. The packet's upstream metadata lists v1.231.0 as the latest non-prerelease.
- The Nautilus US-equity evidence covers 15 AAPL sessions with retrospective close fills, unlimited synthetic depth and dividend/split dates excluded. It does not establish a point-in-time universe, finite liquidity, partial fills or corporate-action handling.
- The LEAN oracle uses bundled sample data over a known 2020 crash stress interval, with full-quantity fills. It has no financing, calibrated liquidation or untouched holdout.
- The requirement's broker-specific execution boundaries are not covered by this winner set. IBKR local_broker_acceptance is not_established (runtime-target.json). Nautilus has no upstream Alpaca adapter; the Alpaca path is a custom adapter on alpaca-py 0.44.0 (engines-strategies.json line 173), evidenced in the broker layer by a single paper roundtrip.
- In-flight broker faults have only synthetic test evidence. No strategy merit, profitability or capacity is established.
- The packet reports a narrow Nautilus risk-test defect: two bare matches! expressions (docs/blind-catalog-source-adjudication-20260921.md). This lane did not open that document, so the claim is retained from the packet and unverified here.
- The mapping-implementation trigger has no dated checkpoint in the evidence. The dividend SimulationModule is owned by a separate parity worktree (engines-strategies.json line 191).
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-backtesting-engine-20260922; codex: -)

#### Data quality and orchestration (data-quality-orchestration)

- candidate:anthropics-claude-code @ unpinned — This verdict is my own source review of retained receipts. No provider or TypeSafe inference results were supplied or reused. Revision: the worker winner changes from c2 (Codex) to c9 (Claude Code). The challenger refuter showed that the earlier ranking depended on the catalog's decision label, not on the receipts. On re-reading the receipts, c9 has the stronger evidence on the requirement's identity, broker-authority and scoped-telemetry clauses.

The packet requirement (packet line 532) is: bounded research with native identity and complete returned results; supervision of owned processes; retention of scoped telemetry, failed attempts and recoverable state; and no broker execution authority for research workers.

c9 Claude Code (native execution):
- Standalone research run in blueprints/us-equities/research-runtime/receipt.json, lines 59-89 and 169. It used workflow independent_report, the command `claude -p --model claude-opus-5 ... --tools '' --disallowedTools '*' --permission-mode dontAsk`, and recorded process_exit_code 0, native_subtype success, reported_models ["claude-opus-5"], exposed_tool_count 0 and report_validation citations_values_units_and_scope_passed.
- Its usage (total_tokens 14583) matched both stores through a research-scoped query: telemetry lines 106-114 record native_usage_equals_prometheus_and_loki true, a Loki query scoped by ecosystem_client_scope="financial-research", and loki_records_for_instance 51.
- Paired run in adoption/paired/receipt.json, lines 101-131. The same fields hold: status completed, exposed_tool_count 0 and report validation passed.
- The broker-authority clause is enforced by an explicit tool denial. The Codex worker receipt, by contrast, records only that no broker tools happened to be present in the environment (blueprints/us-equities/workers/receipt.json line 110).

c19 Dagu v2.16.6 (native execution):
- blueprints/us-equities/hosting/receipt.json (kind native_cli_e2e): a failure fixture requested exit 23, and the run failed with the dependent step aborted. A `dagu stop` cancellation gave status aborted. History survived a service restart. The server ran as a systemd user service with restart_policy on-failure (lines 93-94) and recorded model_calls 0 and broker_calls 0 (lines 96-97).
- blueprints/us-equities/research-runtime/receipt.json: the packet and order_table steps succeeded (lines 43-46), and retained_failures keeps the initial validation exit 1 (lines 141-147).
- Two observations of the paired graph differ in time. The research-runtime receipt (observed 2026-09-19T16:21:52Z, line 54: paired_model_workflow_executed false) predates adoption/paired/receipt.json (observed 19:41:50Z, lines 47-49: research_pair succeeded, exit_code 0). The later receipt supersedes the earlier one for the paired graph. Catalog line 309 still records the earlier blocked state.

c5 Loki v3.7.8 (native execution):
- It retains per-request records with request content omitted, scoped by client scope (research-runtime receipt lines 106-114; all_bodies_content_omitted true).
- evidence/receipts/foundation-native-20260920.json line 35: in the first native Claude run, Loki held all six requests while Prometheus missed the first two. Line 36 shows a fresh run that waited for telemetry initialization matched on native usage, Loki and Prometheus. The observed gap is therefore a startup-timing difference in one run, not a demonstrated retention advantage.
- Loki is selected because it keeps per-request, scoped records. Prometheus keeps aggregate counters.

All evidence is native execution on one authoring host over a bundled 2013 historical LEAN sample.
- dagu @ v2.16.6 — This verdict is my own source review of retained receipts. No provider or TypeSafe inference results were supplied or reused. Revision: the worker winner changes from c2 (Codex) to c9 (Claude Code). The challenger refuter showed that the earlier ranking depended on the catalog's decision label, not on the receipts. On re-reading the receipts, c9 has the stronger evidence on the requirement's identity, broker-authority and scoped-telemetry clauses.

The packet requirement (packet line 532) is: bounded research with native identity and complete returned results; supervision of owned processes; retention of scoped telemetry, failed attempts and recoverable state; and no broker execution authority for research workers.

c9 Claude Code (native execution):
- Standalone research run in blueprints/us-equities/research-runtime/receipt.json, lines 59-89 and 169. It used workflow independent_report, the command `claude -p --model claude-opus-5 ... --tools '' --disallowedTools '*' --permission-mode dontAsk`, and recorded process_exit_code 0, native_subtype success, reported_models ["claude-opus-5"], exposed_tool_count 0 and report_validation citations_values_units_and_scope_passed.
- Its usage (total_tokens 14583) matched both stores through a research-scoped query: telemetry lines 106-114 record native_usage_equals_prometheus_and_loki true, a Loki query scoped by ecosystem_client_scope="financial-research", and loki_records_for_instance 51.
- Paired run in adoption/paired/receipt.json, lines 101-131. The same fields hold: status completed, exposed_tool_count 0 and report validation passed.
- The broker-authority clause is enforced by an explicit tool denial. The Codex worker receipt, by contrast, records only that no broker tools happened to be present in the environment (blueprints/us-equities/workers/receipt.json line 110).

c19 Dagu v2.16.6 (native execution):
- blueprints/us-equities/hosting/receipt.json (kind native_cli_e2e): a failure fixture requested exit 23, and the run failed with the dependent step aborted. A `dagu stop` cancellation gave status aborted. History survived a service restart. The server ran as a systemd user service with restart_policy on-failure (lines 93-94) and recorded model_calls 0 and broker_calls 0 (lines 96-97).
- blueprints/us-equities/research-runtime/receipt.json: the packet and order_table steps succeeded (lines 43-46), and retained_failures keeps the initial validation exit 1 (lines 141-147).
- Two observations of the paired graph differ in time. The research-runtime receipt (observed 2026-09-19T16:21:52Z, line 54: paired_model_workflow_executed false) predates adoption/paired/receipt.json (observed 19:41:50Z, lines 47-49: research_pair succeeded, exit_code 0). The later receipt supersedes the earlier one for the paired graph. Catalog line 309 still records the earlier blocked state.

c5 Loki v3.7.8 (native execution):
- It retains per-request records with request content omitted, scoped by client scope (research-runtime receipt lines 106-114; all_bodies_content_omitted true).
- evidence/receipts/foundation-native-20260920.json line 35: in the first native Claude run, Loki held all six requests while Prometheus missed the first two. Line 36 shows a fresh run that waited for telemetry initialization matched on native usage, Loki and Prometheus. The observed gap is therefore a startup-timing difference in one run, not a demonstrated retention advantage.
- Loki is selected because it keeps per-request, scoped records. Prometheus keeps aggregate counters.

All evidence is native execution on one authoring host over a bundled 2013 historical LEAN sample.
- loki @ v3.7.8 — This verdict is my own source review of retained receipts. No provider or TypeSafe inference results were supplied or reused. Revision: the worker winner changes from c2 (Codex) to c9 (Claude Code). The challenger refuter showed that the earlier ranking depended on the catalog's decision label, not on the receipts. On re-reading the receipts, c9 has the stronger evidence on the requirement's identity, broker-authority and scoped-telemetry clauses.

The packet requirement (packet line 532) is: bounded research with native identity and complete returned results; supervision of owned processes; retention of scoped telemetry, failed attempts and recoverable state; and no broker execution authority for research workers.

c9 Claude Code (native execution):
- Standalone research run in blueprints/us-equities/research-runtime/receipt.json, lines 59-89 and 169. It used workflow independent_report, the command `claude -p --model claude-opus-5 ... --tools '' --disallowedTools '*' --permission-mode dontAsk`, and recorded process_exit_code 0, native_subtype success, reported_models ["claude-opus-5"], exposed_tool_count 0 and report_validation citations_values_units_and_scope_passed.
- Its usage (total_tokens 14583) matched both stores through a research-scoped query: telemetry lines 106-114 record native_usage_equals_prometheus_and_loki true, a Loki query scoped by ecosystem_client_scope="financial-research", and loki_records_for_instance 51.
- Paired run in adoption/paired/receipt.json, lines 101-131. The same fields hold: status completed, exposed_tool_count 0 and report validation passed.
- The broker-authority clause is enforced by an explicit tool denial. The Codex worker receipt, by contrast, records only that no broker tools happened to be present in the environment (blueprints/us-equities/workers/receipt.json line 110).

c19 Dagu v2.16.6 (native execution):
- blueprints/us-equities/hosting/receipt.json (kind native_cli_e2e): a failure fixture requested exit 23, and the run failed with the dependent step aborted. A `dagu stop` cancellation gave status aborted. History survived a service restart. The server ran as a systemd user service with restart_policy on-failure (lines 93-94) and recorded model_calls 0 and broker_calls 0 (lines 96-97).
- blueprints/us-equities/research-runtime/receipt.json: the packet and order_table steps succeeded (lines 43-46), and retained_failures keeps the initial validation exit 1 (lines 141-147).
- Two observations of the paired graph differ in time. The research-runtime receipt (observed 2026-09-19T16:21:52Z, line 54: paired_model_workflow_executed false) predates adoption/paired/receipt.json (observed 19:41:50Z, lines 47-49: research_pair succeeded, exit_code 0). The later receipt supersedes the earlier one for the paired graph. Catalog line 309 still records the earlier blocked state.

c5 Loki v3.7.8 (native execution):
- It retains per-request records with request content omitted, scoped by client scope (research-runtime receipt lines 106-114; all_bodies_content_omitted true).
- evidence/receipts/foundation-native-20260920.json line 35: in the first native Claude run, Loki held all six requests while Prometheus missed the first two. Line 36 shows a fresh run that waited for telemetry initialization matched on native usage, Loki and Prometheus. The observed gap is therefore a startup-timing difference in one run, not a demonstrated retention advantage.
- Loki is selected because it keeps per-request, scoped records. Prometheus keeps aggregate counters.

All evidence is native execution on one authoring host over a bundled 2013 historical LEAN sample.

Alternatives:
- Codex (overlap) — Codex is equally native-proven for completion and identity. blueprints/us-equities/workers/receipt.json records run.status completed, configured_model gpt-6-astra and total usage 135311 (lines 24-47). It also retains a failed ctx_execute_file attempt (lines 75-79 and 111), which is direct evidence of failed-attempt retention. In adoption/paired/receipt.json (lines 64-99) Astra completed with report validation passed. It is ranked below c9 for three reasons. (1) Broker authority is limited by the environment, not by configuration: workers/receipt.json line 110 says read-only mode does not restrict external MCP mutations and only that 'the recorded environment supplied no broker keys or broker tools'. The paired receipt (line 29) says Astra accepted only message items, but it records no exposed-tool count. (2) The retained evidence has no research-scoped telemetry match for Codex. foundation-native-20260920.json line 35 records only that native Codex usage matched Loki and Prometheus in the foundation run. (3) blueprints/us-equities/research-runtime/receipt.json lines 90-101 recorded codex_readiness.ready false (weekly usage 100%), and lines 148-152 record an unresolved device sign-in. The later paired receipt (line 207) records readiness restored. These are quota and sign-in failures, not capability failures. Codex remains the required first worker in the paired Astra-to-Claude graph and was left out only because of the 3-winner cap. The catalog's 'default' decision label (catalogs/us-equities/agents-operations.json lines 7-16) was not used as ranking evidence.
- OpenTelemetry Collector contrib (overlap) — The Collector is a required pipeline, not a competing choice. catalogs/us-equities/agents-operations.json (opentelemetry-collector-contrib entry, lines 854-894) says it supplies the privacy transform and OTLP delivery to Loki and Prometheus, and the Loki entry requires Collector sanitization before ingestion (line 1003). It forwards telemetry but does not retain it. It was left out of the winner set only because of the 3-winner cap and remains co-required.
- Prometheus (overlap) — Native usage matched Prometheus in the research-scoped query (blueprints/us-equities/research-runtime/receipt.json lines 112-113). Its series are aggregate counters (last_over_time of token_usage_tokens_total), not per-request records of failed attempts. In one run it missed the first two Claude requests during telemetry startup (evidence/receipts/foundation-native-20260920.json line 35). A fresh run that waited for initialization matched (line 36), so this is a startup-timing gap, not a proven retention defect. Prometheus complements Loki rather than replacing it.
- Restic (overlap) — Correction from the earlier proposal: Restic is the only candidate with executed restore receipts, so it partly covers the requirement's 'recoverable state' clause and is no longer marked out_of_scope. blueprints/us-equities/state-recovery/memory/receipt.json (kind native_cli_e2e, status passed_same_host_restore, lines 4-8) preserved 324 archived files and verified SQLite/FTS state. The Qdrant state-recovery receipt reports a same-host native restore of five collections and 201 points. The catalog's us_equities_fit (catalogs/us-equities/agents-operations.json line 1740) is 'Preserve selected reproducible research/configuration artifacts'. The catalog's limitation at line 1767 ('No live SQLite/Qdrant/Loki/Prometheus database ... was backed up') describes only the earlier public-file backup, and the later state-recovery receipts supersede it for SQLite and Qdrant. Restic is not the default here for three reasons: all restores were same-host; no Dagu run state, Loki or Prometheus store, or order journal was restored; and it does not run or supervise research. It was left out because of the 3-winner cap and because it covers worker memory and vector state, not run state.
- Grafana (out_of_scope) — Grafana is a visualization layer. Correction from the earlier proposal: docs/dashboard-rendered-acceptance.md line 29 records that exact panel queries matched native memory, Qdrant and QMD results, not research-run telemetry. The same line says 'Claude has no current telemetry series; absence is not zero usage or savings.' Grafana does not run research, supervise processes or retain state itself.
- DeerFlow (conditional) — blueprints/us-equities/deerflow/research-receipt.json records one embedded invoke_acp_agent task that completed. The same receipt says DeerFlow discards ACP completion and usage, which had to be recovered from private adapter logs. It also says ACP read-only mode maps to workspaceWrite/on-request. No planner, UI, scheduler or hosted service was accepted. This falls short of the requirement for complete returned results and strict read-only scope.
- Temporal (conditional) — The only evidence is the catalog's source review (catalogs/us-equities/agents-operations.json lines 319-359). There is no failure, cancellation or restart receipt. The catalog names Temporal as the escalation choice for host-loss or multi-day durability, which is exactly the gap Dagu leaves (in-flight resumption not proved). It is untested, not failed.
- Prefect (unqualified) — The only evidence is a source review (catalogs/us-equities/agents-operations.json lines 361-401). No flow was supplied or scheduled, and the catalog says Prefect would replace Dagu as the first scheduler rather than run alongside it. There is no execution receipt.
- Dagster (unqualified) — The only evidence is a source review (catalogs/us-equities/agents-operations.json lines 403-440). Dagster targets partition and backfill lineage, which the requirement does not ask for. No asset definitions were written and nothing was run.
- LangGraph (unqualified) — The only evidence is a source review. The catalog calls its import command an installation smoke test only (catalogs/us-equities/agents-operations.json line 262). InMemorySaver loses state on restart. The packet's upstream metadata puts the pin behind upstream.
- OpenAI Agents SDK (unqualified) — catalogs/us-equities/agents-operations.json (lines 1605-1644) records no provider API call and says the SDK does not inherit native Codex account identity. Tracing is on by default. It is API-backed, not native identity.
- Deep Agents (unqualified) — docs/candidate-quality-review-20260921.md line 44 calls it a serious challenger that still needs the same source-research task, permission boundaries, recovery test and complete cost comparison. None of these have been executed. It is untested, not failed.
- OpenHands SDK (unqualified) — docs/candidate-quality-review-20260921.md line 45 says installation, native-account and recovery acceptance remain open. It is a challenger for remote or isolated workers only.
- OpenHands Agent Canvas (unqualified) — docs/candidate-quality-review-20260921.md line 46 says hosting existing native workers may be useful but is not yet qualified here. There is no execution receipt.
- Microsoft Agent Framework (unqualified) — docs/candidate-quality-review-20260921.md line 47 says it fills a discovery gap, but a required application workflow must be qualified before another runtime is added. There is no execution evidence.
- OmniRoute (out_of_scope) — Not adopted, and it belongs to the routing layer. catalogs/us-equities/agents-operations.json (lines 97-145) says gateway transport health does not establish native identity and that the Codex executor strips max_output_tokens.
- FreeLLMAPI (out_of_scope) — Not adopted, and it is a routing alternative. catalogs/us-equities/agents-operations.json (lines 146-187) says a readiness 200 shows transport health only, and that Claude-looking aliases can route to local Qwen, so native identity is not preserved.
- vLLM (out_of_scope) — Not adopted, and it belongs to the model-serving layer. It does not supervise research runs or provide native account identity. The packet's upstream metadata puts the pin behind upstream.

Overturn when: Any of the following would change the verdict.

- c2 over c9: a fresh native run of blueprints/us-equities/workers/native_worker.py inside blueprints/us-equities/research-runtime/research-pair.yaml shows that the Codex worker enforces zero exposed tools, or an equivalent hard tool denial, and matches a research-scoped (client_scope financial-research) Loki and Prometheus usage query exactly, while Claude Code fails either check on the same packet.
- Dagu replaced: Temporal, Prefect or Deep Agents passes the same checks as blueprints/us-equities/hosting/receipt.json (a failure fixture with dependent-step abort, a cancellation fixture, and history preserved across restart) and also proves resumption of an interrupted run, which Dagu has not shown (hosting receipt line 100).
- Loki demoted: a fresh native worker run shows Loki missing requests that Prometheus or the Collector file sink retained.

Every such result must be recorded with a single owner for each side effect, complete usage and failed-attempt accounting, broker_calls 0 and matching model identity.

Open gaps:
- Recovery of an interrupted run is not shown. Dagu's restart preserved completed history only (blueprints/us-equities/hosting/receipt.json line 100), and none of the listed fixtures contains an interruption or resume case.
- The recoverable-state clause is covered only by preserved completed Dagu history and by same-host Restic restores of ai-memory and Qdrant state (blueprints/us-equities/state-recovery/memory/receipt.json line 8). No Dagu run state, telemetry store or order journal was restored, and nothing was recovered off-host.
- The 'data-quality' part of the layer title has no candidate evidence. Pandera appears only under the packet's sota_components_not_in_candidates, and the requirement text (packet line 532) does not mention dataset validation.
- The packet records no pin for c9 Claude Code (pin null), so the winning worker's version is not bound in this layer's evidence. The receipts record only configured_model claude-opus-5.
- The Dagu pin v2.16.6 is behind upstream v2.17.0 according to the packet metadata, and the newer release has not been tested.
- No research-scoped telemetry match was retained for the Codex worker. foundation-native-20260920.json line 35 records only a foundation-run match.
- All evidence is from one authoring host with a bundled 2013 historical LEAN sample (adoption/paired/receipt.json lines 19-23). There is no off-host hosting, no unattended schedule (blueprints/us-equities/hosting/receipt.json line 90: recurring_schedule false) and no new-machine reproduction.
- Configured model and provider are not independently attested per request (adoption/paired/receipt.json line 205). Net provider savings were not measured (blueprints/us-equities/research-runtime/receipt.json line 139: net_provider_tokens_saved null), and complete coordinator and worker usage is outside the native counters (adoption/paired/receipt.json line 133).
- Codex read-only mode is requested, not a hard OS sandbox, and external MCP mutations are not restricted (blueprints/us-equities/workers/receipt.json line 110). Claude's zero-tool enforcement is a client flag, not an OS sandbox either (blueprints/us-equities/research-runtime/receipt.json line 23).
- The first paired attempt was blocked because the Codex allowance was exhausted (blueprints/us-equities/research-runtime/receipt.json line 18 and lines 90-101). It succeeded only in the later run recorded in adoption/paired/receipt.json (lines 47-49). catalogs/us-equities/agents-operations.json line 309 still records the earlier blocked state.
- Temporal, Prefect, Dagster, LangGraph, the OpenAI Agents SDK, Deep Agents, the OpenHands SDK and Canvas, and Microsoft Agent Framework are untested, not failed.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-data-quality-orchestration-20260922; codex: -)

#### Evaluation and experiments (evaluation-experiments)

- codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0 — This verdict comes from my own review of the retained receipts. The packet withholds the provider decision and rationale fields, so none were carried over. What the receipts show, by candidate:

(1) Codex (c1), native execution. In blueprints/us-equities/workers/receipt.json, one native Codex SDK research task completed with configured model gpt-6-astra. It used 135311 total tokens and ran for 58410 ms, with no broker keys. The receipt keeps its failures: the ctx_execute_file tool failed (lines 76-78), and two follow-up scope attempts also failed and keep their usage (lines 132-206). All three turns total 204091 tokens (line 215).

(2) Claude Code (c4), native execution. In adoption/paired/receipt.json, a Dagu-run LEAN->DuckDB->Astra->Claude pair completed. Both reports passed the citation, value, unit and scope checks. Claude ran with 0 exposed tools, and the Astra report was bound into Claude's prompt by hash. Combined native-worker usage was 37069 tokens, and trading_authorized was false.

(3) Codex and Claude together, measured within each provider. blueprints/us-equities/research-efficiency/native-receipt.json has 8 native invocations graded blind against a frozen rubric. All 8 passed the semantic check; 6 passed the word protocol. The two Claude full-context answers failed the word limit (327 and 260 words), and both failures are retained. This compares focused against full context for each provider. It does not compare the candidates with each other.

(4) Dagu (c9), native execution of supervision. blueprints/us-equities/hosting/receipt.json records a failure fixture (step exit 23, then failed, with the dependent step aborted) and a cancellation fixture (aborted). After a service restart, completed history was kept, and anonymous access returned 401 while authenticated access returned 200. The receipt records model_calls 0 and broker_calls 0. blueprints/us-equities/research-runtime/receipt.json shows the Dagu packet and order_table steps succeeded. Claude's native usage matched Prometheus and Loki exactly (native_usage_equals_prometheus_and_loki true), and the receipt retains its failures.

Together these three cover native identity, complete returned results, process supervision, retained failed attempts and the no-broker boundary.
- candidate:anthropics-claude-code @ unpinned — This verdict comes from my own review of the retained receipts. The packet withholds the provider decision and rationale fields, so none were carried over. What the receipts show, by candidate:

(1) Codex (c1), native execution. In blueprints/us-equities/workers/receipt.json, one native Codex SDK research task completed with configured model gpt-6-astra. It used 135311 total tokens and ran for 58410 ms, with no broker keys. The receipt keeps its failures: the ctx_execute_file tool failed (lines 76-78), and two follow-up scope attempts also failed and keep their usage (lines 132-206). All three turns total 204091 tokens (line 215).

(2) Claude Code (c4), native execution. In adoption/paired/receipt.json, a Dagu-run LEAN->DuckDB->Astra->Claude pair completed. Both reports passed the citation, value, unit and scope checks. Claude ran with 0 exposed tools, and the Astra report was bound into Claude's prompt by hash. Combined native-worker usage was 37069 tokens, and trading_authorized was false.

(3) Codex and Claude together, measured within each provider. blueprints/us-equities/research-efficiency/native-receipt.json has 8 native invocations graded blind against a frozen rubric. All 8 passed the semantic check; 6 passed the word protocol. The two Claude full-context answers failed the word limit (327 and 260 words), and both failures are retained. This compares focused against full context for each provider. It does not compare the candidates with each other.

(4) Dagu (c9), native execution of supervision. blueprints/us-equities/hosting/receipt.json records a failure fixture (step exit 23, then failed, with the dependent step aborted) and a cancellation fixture (aborted). After a service restart, completed history was kept, and anonymous access returned 401 while authenticated access returned 200. The receipt records model_calls 0 and broker_calls 0. blueprints/us-equities/research-runtime/receipt.json shows the Dagu packet and order_table steps succeeded. Claude's native usage matched Prometheus and Loki exactly (native_usage_equals_prometheus_and_loki true), and the receipt retains its failures.

Together these three cover native identity, complete returned results, process supervision, retained failed attempts and the no-broker boundary.
- dagu @ v2.16.6 — This verdict comes from my own review of the retained receipts. The packet withholds the provider decision and rationale fields, so none were carried over. What the receipts show, by candidate:

(1) Codex (c1), native execution. In blueprints/us-equities/workers/receipt.json, one native Codex SDK research task completed with configured model gpt-6-astra. It used 135311 total tokens and ran for 58410 ms, with no broker keys. The receipt keeps its failures: the ctx_execute_file tool failed (lines 76-78), and two follow-up scope attempts also failed and keep their usage (lines 132-206). All three turns total 204091 tokens (line 215).

(2) Claude Code (c4), native execution. In adoption/paired/receipt.json, a Dagu-run LEAN->DuckDB->Astra->Claude pair completed. Both reports passed the citation, value, unit and scope checks. Claude ran with 0 exposed tools, and the Astra report was bound into Claude's prompt by hash. Combined native-worker usage was 37069 tokens, and trading_authorized was false.

(3) Codex and Claude together, measured within each provider. blueprints/us-equities/research-efficiency/native-receipt.json has 8 native invocations graded blind against a frozen rubric. All 8 passed the semantic check; 6 passed the word protocol. The two Claude full-context answers failed the word limit (327 and 260 words), and both failures are retained. This compares focused against full context for each provider. It does not compare the candidates with each other.

(4) Dagu (c9), native execution of supervision. blueprints/us-equities/hosting/receipt.json records a failure fixture (step exit 23, then failed, with the dependent step aborted) and a cancellation fixture (aborted). After a service restart, completed history was kept, and anonymous access returned 401 while authenticated access returned 200. The receipt records model_calls 0 and broker_calls 0. blueprints/us-equities/research-runtime/receipt.json shows the Dagu packet and order_table steps succeeded. Claude's native usage matched Prometheus and Loki exactly (native_usage_equals_prometheus_and_loki true), and the receipt retains its failures.

Together these three cover native identity, complete returned results, process supervision, retained failed attempts and the no-broker boundary.

Alternatives:
- LangGraph (conditional) — The only evidence is a source review of an upstream README (catalogs/us-equities/agents-operations.json lines 247-263). The recorded command is an import smoke test, not a working agent, and InMemorySaver loses state on restart. There is no native research run, supervision test or telemetry match. The pin, 1.2.11, is behind upstream 1.2.12.
- Dagster (out_of_scope) — Dagster is catalogued as an alternative for partitioned data assets and backfill lineage, from a README review only (agents-operations.json lines 403-439). No definitions or run exist. It addresses data lineage rather than supervising bounded research workers.
- OpenHands Agent Canvas (unqualified) — docs/candidate-quality-review-20260921.md line 46 says hosting the existing native workers 'is not yet qualified here'. The evidence is a README review only, with no installation, native-identity or recovery run.
- DeerFlow (conditional) — The native evidence is one embedded ACP prompt (blueprints/us-equities/deerflow/research-receipt.json). In that run DeerFlow discards ACP completion and usage data, so usage had to be recovered from private adapter logs. The 'read-only' mode actually maps to workspaceWrite/on-request, so strict read-only is not established. There is no planner/UI or persistent service. The discovery receipt covers a development commit (2.1.0-rc0), not stable v2.0.0. The 2026-09-21 review keeps it optional (candidate-quality-review-20260921.md line 43).
- Prometheus (overlap) — Prometheus supplies the telemetry-retention part of the requirement, and it was observed matching native Claude usage in all four categories (evidence/receipts/foundation-native-20260920.json lines 466-493; research-runtime/receipt.json telemetry). It is a supporting observability component, not a research-worker or supervision runtime, and it is already the default in the observability layer.
- Prefect (conditional) — The evidence is a README review only, and the catalog says 'No flow is supplied or scheduled here' (agents-operations.json lines 389-392). It would be chosen instead of Dagu, not in addition. It has no failure, cancellation or restart evidence comparable to Dagu's hosting receipt.
- Deep Agents (unqualified) — The 2026-09-21 review names it a 'serious challenger' but requires the same source-research task, permission boundaries, recovery and full cost comparison, none of which has run (candidate-quality-review-20260921.md line 44). The evidence is a README review only, and its installed version is undetermined (candidate-quality-review.json line 170).
- Microsoft Agent Framework (unqualified) — It fills a gap in discovery only. The review says to 'qualify a required application workflow before adding another runtime' (candidate-quality-review-20260921.md line 47). There is no native run.
- OpenHands SDK (unqualified) — It is a challenger for remote or isolated workers, but 'installation and native-account/recovery acceptance remain open' (candidate-quality-review-20260921.md line 45). The evidence is a README review only.
- Loki (overlap) — Loki is the supporting log store. Its records matched native Claude usage (foundation-native-20260920.json lines 478-484; research-runtime receipt: 51 Loki records for the instance). It is observability, not a worker or supervision runtime, and it is already the default in its own layer. It stores sanitized labels, not full transcripts (agents-operations.json line 1007).
- Grafana (overlap) — Grafana only visualizes data; it does not retain it. docs/dashboard-rendered-acceptance.md line 29 says 'Claude has no current telemetry series; absence is not zero usage or savings'. It supports the layer rather than satisfying the research-worker requirement.
- OpenTelemetry Collector contrib (overlap) — The Collector is the privacy-filtered telemetry path that feeds Prometheus and Loki, observed in foundation-native-20260920.json. It is a necessary supporting component but not a research-worker or supervision runtime. Traces are disabled (agents-operations.json line 882).
- Restic (overlap) — Restic covers recoverable state. The ai-memory and Qdrant restores passed on the same host (state-recovery/memory and qdrant receipts: 'passed_same_host_restore' and 'passed_same_host_native_restore'). Research-run state, off-host recovery and worker in-flight recovery are not covered. It is a backup layer, not a worker runtime.
- Temporal (conditional) — The catalog names it the preferred escalation for host-loss survival or multi-day approval workflows (agents-operations.json line 326). The evidence is a README review only, start-dev is not production, and activities retry by default. None of Dagu's failure, cancellation or restart tests has been run for it.
- OpenAI Agents SDK (conditional) — The catalog says 'No provider API call or model comparison performed', tracing is on by default, and the SDK does not inherit the native Codex identity (agents-operations.json lines 1632-1636). That fails the requirement's native-identity criterion as evidenced.
- Inspect AI (not a packet candidate; listed in sota_components_not_in_candidates) (unqualified) — The us-equities catalog makes Inspect AI the default for 'agent-evaluation', as the first choice for a frozen extraction/tool-use acceptance suite (agents-operations.json lines 1282-1320). The evidence is source review of the PyPI page only, and the catalog says 'Eval command would perform model calls; not run here'. It cannot be selected because it is not a packet candidate. The project's own frozen-rubric blind review in research-efficiency/native-receipt.json currently fills the evaluation role.
- MLflow (not a packet candidate) (conditional) — The catalog decision is conditional: use it 'when strategy/feature experiments require a durable registry'. The catalog also says 'No tracking server or experiment recorded by this task' (agents-operations.json lines 1695-1719). The evidence is a README review only.

Overturn when: The verdict changes if a challenger passes an executed comparison under the same conditions. The challenger would be Deep Agents (c10), the OpenHands SDK (c12), DeerFlow (c6) as a full planner/service, or Temporal (c19) as supervisor. The comparison would reuse the frozen task and rubric in blueprints/us-equities/research-efficiency/plan.json and the checks in tests/test_research_efficiency.py, tests/test_research_evaluation.py and tests/test_worker_recovery.py. To overturn, the challenger must reach semantic and protocol pass rates at least equal to the retained 8/8 and 6/8, with complete usage including failed attempts, native account identity and zero broker tools. For a supervisor challenger, it must also match or exceed Dagu's failure, cancellation and restart-history results in blueprints/us-equities/hosting/receipt.json, and it must add in-flight recovery. Separately, a native Inspect AI run of the frozen suite that finds errors the project rubric missed would change how this layer is evaluated.

Open gaps:
- No executed comparison between candidates exists. The research-efficiency receipt compares focused and full context within each provider only; with two tasks per provider it gives no confidence intervals and no provider ranking.
- The layer's actual evaluation tools (Inspect AI as the agent-evaluation default, promptfoo, MLflow) are not packet candidates. Each has source review only, with no executed eval run or experiment registry.
- Dagu restart keeps completed history but does not prove in-flight resumption (hosting/receipt.json limitations). The pin v2.16.6 is behind upstream v2.17.0, and no scheduling or standing model worker is active.
- Native configured-model checks are not independent per-request provider attestation (workers/receipt.json, paired receipt limitations).
- Codex zero-tools enforcement is requested and audited, not hard MCP prevention. Read-only filesystem mode does not restrict external MCP mutations.
- Provider-side cancellation is not proven, and no run timed out (research-efficiency limitations).
- Restic recovery covers the ai-memory and Qdrant state on the same host only. Research-run state and off-host disaster recovery are unproven.
- Grafana has no current Claude telemetry series (dashboard-rendered-acceptance.md line 29).
- Deep Agents, OpenHands SDK/Canvas and Microsoft Agent Framework have no installation or native-identity run.
- The packet leaves the Claude Code pin as null. docs/foundation-closure-20260921.md line 52 records installed version 2.1.278, and the research-efficiency runtime says the underlying Claude executable was not separately frozen.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-evaluation-experiments-20260922; codex: -)

#### Execution and broker adapters (execution-broker)

- nautilus-ibkr-adapter @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e) — This is my own source review of the retained receipts; it does not rely on provider or project labels. The evidence classes differ by winner, so the set-level class is the weakest load-bearing one: source_review, which applies to c1's IBKR broker boundary. Evidence for each winner follows.

c1: NautilusTrader 2.0.0rc5, packet component nautilus-ibkr-adapter.
- Destination: it is the destination named in catalogs/us-equities/runtime-target.json (engine.decision "selected_destination", line 30).
- Broker boundary (source review only): runtime-target.json line 49 records broker_boundaries[ibkr].local_broker_acceptance as "not_established". The nautilus-ibkr-adapter card in catalogs/us-equities/engines-strategies.json has evidence_level "source_review" (line 1683) and marks its workflow "Prospective and unexecuted" (line 1688). evidence/receipts/native-nautilus-v2-20260920.json line 12 excludes IBKR Gateway/TWS authentication, adapter connectivity and Alpaca integration acceptance. runtime-target.json line 71 records upstream_nautilus_adapter_present false for Alpaca.
- Engine evidence, which involves no broker:
  - Native upstream synthetic run: the same receipt shows the unchanged upstream synthetic EUR/USD quickstart at commit 1b0a49d2 running twice in isolation, offline. It recorded 902 fills, 451 positions, ending cash "1000431.00000", a byte-identical account.csv and decimal PnL of 431.00 USD. Two earlier empty-report runs are retained.
  - Local integration: blueprints/us-equities/engine-nautilus/equity-replay/receipt.json replays 15 retained AAPL sessions. The baseline scenario ended at -133.40 USD and fee_slippage_stress at -144.40 USD. Each scenario verified 10 cash transitions and reconciled realized PnL.
  - Test suite: one shared suite of 8 synthetic admission and report-corruption tests passed (line 89).
  - What this shows: reproducible equity accounting on synthetic close fills only.

c12: alpaca-py 0.44.0. This is the only broker boundary with actual provider execution, recorded in blueprints/us-equities/paper-e2e-20260921/paper-receipt.json:
- One SPY buy/sell on paper-api.alpaca.markets, with 2 write attempts and realized gross -0.08 USD.
- A separate read-only process reconciled with 5 GETs, all HTTP 200, finding 0 positions and 0 open orders; the cash delta matched.
- Completed-trial recovery made 0 additional writes.
- The receipt also records 27 synthetic tests and caps of 1000 USD maximum order notional and 4 maximum write attempts.
- It ran through the local paper_runner.py, not a Nautilus LiveNode.

c13: LEAN 985ef30a. It is retained because the requirement says to preserve the prior LEAN oracle.
- blueprints/us-equities/historical-simulation/receipt.json shows 6 frozen native SPY simulations. The 5 invested cases ended flat with fills, fees and dividend cash reconciled. The over_limit case got 1 native buying-power rejection and 0 fills.
- blueprints/us-equities/engine/resolution-receipt.json shows the unchanged bundled backtest completed with 3943 data points and 3 orders. That run used a locally patched LEAN build: 3 package-reference replacements (lines 6 and 24) that are not accepted upstream. Its brokerage_model was "Unchanged upstream default; not Alpaca" (line 77).

Overall, no winner has broker execution evidence through Nautilus.
- alpaca-py @ 0.44.0 — This is my own source review of the retained receipts; it does not rely on provider or project labels. The evidence classes differ by winner, so the set-level class is the weakest load-bearing one: source_review, which applies to c1's IBKR broker boundary. Evidence for each winner follows.

c1: NautilusTrader 2.0.0rc5, packet component nautilus-ibkr-adapter.
- Destination: it is the destination named in catalogs/us-equities/runtime-target.json (engine.decision "selected_destination", line 30).
- Broker boundary (source review only): runtime-target.json line 49 records broker_boundaries[ibkr].local_broker_acceptance as "not_established". The nautilus-ibkr-adapter card in catalogs/us-equities/engines-strategies.json has evidence_level "source_review" (line 1683) and marks its workflow "Prospective and unexecuted" (line 1688). evidence/receipts/native-nautilus-v2-20260920.json line 12 excludes IBKR Gateway/TWS authentication, adapter connectivity and Alpaca integration acceptance. runtime-target.json line 71 records upstream_nautilus_adapter_present false for Alpaca.
- Engine evidence, which involves no broker:
  - Native upstream synthetic run: the same receipt shows the unchanged upstream synthetic EUR/USD quickstart at commit 1b0a49d2 running twice in isolation, offline. It recorded 902 fills, 451 positions, ending cash "1000431.00000", a byte-identical account.csv and decimal PnL of 431.00 USD. Two earlier empty-report runs are retained.
  - Local integration: blueprints/us-equities/engine-nautilus/equity-replay/receipt.json replays 15 retained AAPL sessions. The baseline scenario ended at -133.40 USD and fee_slippage_stress at -144.40 USD. Each scenario verified 10 cash transitions and reconciled realized PnL.
  - Test suite: one shared suite of 8 synthetic admission and report-corruption tests passed (line 89).
  - What this shows: reproducible equity accounting on synthetic close fills only.

c12: alpaca-py 0.44.0. This is the only broker boundary with actual provider execution, recorded in blueprints/us-equities/paper-e2e-20260921/paper-receipt.json:
- One SPY buy/sell on paper-api.alpaca.markets, with 2 write attempts and realized gross -0.08 USD.
- A separate read-only process reconciled with 5 GETs, all HTTP 200, finding 0 positions and 0 open orders; the cash delta matched.
- Completed-trial recovery made 0 additional writes.
- The receipt also records 27 synthetic tests and caps of 1000 USD maximum order notional and 4 maximum write attempts.
- It ran through the local paper_runner.py, not a Nautilus LiveNode.

c13: LEAN 985ef30a. It is retained because the requirement says to preserve the prior LEAN oracle.
- blueprints/us-equities/historical-simulation/receipt.json shows 6 frozen native SPY simulations. The 5 invested cases ended flat with fills, fees and dividend cash reconciled. The over_limit case got 1 native buying-power rejection and 0 fills.
- blueprints/us-equities/engine/resolution-receipt.json shows the unchanged bundled backtest completed with 3943 data points and 3 orders. That run used a locally patched LEAN build: 3 package-reference replacements (lines 6 and 24) that are not accepted upstream. Its brokerage_model was "Unchanged upstream default; not Alpaca" (line 77).

Overall, no winner has broker execution evidence through Nautilus.
- lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f — This is my own source review of the retained receipts; it does not rely on provider or project labels. The evidence classes differ by winner, so the set-level class is the weakest load-bearing one: source_review, which applies to c1's IBKR broker boundary. Evidence for each winner follows.

c1: NautilusTrader 2.0.0rc5, packet component nautilus-ibkr-adapter.
- Destination: it is the destination named in catalogs/us-equities/runtime-target.json (engine.decision "selected_destination", line 30).
- Broker boundary (source review only): runtime-target.json line 49 records broker_boundaries[ibkr].local_broker_acceptance as "not_established". The nautilus-ibkr-adapter card in catalogs/us-equities/engines-strategies.json has evidence_level "source_review" (line 1683) and marks its workflow "Prospective and unexecuted" (line 1688). evidence/receipts/native-nautilus-v2-20260920.json line 12 excludes IBKR Gateway/TWS authentication, adapter connectivity and Alpaca integration acceptance. runtime-target.json line 71 records upstream_nautilus_adapter_present false for Alpaca.
- Engine evidence, which involves no broker:
  - Native upstream synthetic run: the same receipt shows the unchanged upstream synthetic EUR/USD quickstart at commit 1b0a49d2 running twice in isolation, offline. It recorded 902 fills, 451 positions, ending cash "1000431.00000", a byte-identical account.csv and decimal PnL of 431.00 USD. Two earlier empty-report runs are retained.
  - Local integration: blueprints/us-equities/engine-nautilus/equity-replay/receipt.json replays 15 retained AAPL sessions. The baseline scenario ended at -133.40 USD and fee_slippage_stress at -144.40 USD. Each scenario verified 10 cash transitions and reconciled realized PnL.
  - Test suite: one shared suite of 8 synthetic admission and report-corruption tests passed (line 89).
  - What this shows: reproducible equity accounting on synthetic close fills only.

c12: alpaca-py 0.44.0. This is the only broker boundary with actual provider execution, recorded in blueprints/us-equities/paper-e2e-20260921/paper-receipt.json:
- One SPY buy/sell on paper-api.alpaca.markets, with 2 write attempts and realized gross -0.08 USD.
- A separate read-only process reconciled with 5 GETs, all HTTP 200, finding 0 positions and 0 open orders; the cash delta matched.
- Completed-trial recovery made 0 additional writes.
- The receipt also records 27 synthetic tests and caps of 1000 USD maximum order notional and 4 maximum write attempts.
- It ran through the local paper_runner.py, not a Nautilus LiveNode.

c13: LEAN 985ef30a. It is retained because the requirement says to preserve the prior LEAN oracle.
- blueprints/us-equities/historical-simulation/receipt.json shows 6 frozen native SPY simulations. The 5 invested cases ended flat with fills, fees and dividend cash reconciled. The over_limit case got 1 native buying-power rejection and 0 fills.
- blueprints/us-equities/engine/resolution-receipt.json shows the unchanged bundled backtest completed with 3943 data points and 3 orders. That run used a locally patched LEAN build: 3 package-reference replacements (lines 6 and 24) that are not accepted upstream. Its brokerage_model was "Unchanged upstream default; not Alpaca" (line 77).

Overall, no winner has broker execution evidence through Nautilus.

Alternatives:
- LEAN Alpaca brokerage (conditional) — Only compilation has been observed. resolution-receipt.json records two builds. The unmodified adapter build exited 0 with 2 advisory pairs remaining (DotNetZip and System.Drawing.Common). The source-integrated build (2 adapter reference replacements) exited 0 with 0 advisory pairs. Its remaining_external_boundary is 'not_exercised_requires_operator_entitlement_and_broker_authorization', with broker_orders_submitted 0. Initialize calls ValidateSubscription, which requires QuantConnect product 347. The catalog card also notes the default NullSlippageModel. By contrast, alpaca-py (c12) has an executed and reconciled paper trial. This path also runs in the LEAN runtime, not in the selected Nautilus destination.
- Dockerized IB Gateway (conditional) — It is an optional hosting lane for the IBKR gateway, not an execution adapter. hosting-practice.json records decision 'conditional', evidence_level 'source_review' and native_acceptance 'not_established' at pin e19aa0be. docs/hosting-container-practice.md says Nautilus starts DockerizedIBGateway separately and that the default image uses the mutable 'stable' tag, so a digest must be retained. It also says image availability does not establish broker acceptance. The native external TWS/IB Gateway remains a valid path.
- ib_async (overlap) — It overlaps with the in-tree Nautilus IBKR adapter at the selected engine pin. The ib_async card in engines-strategies.json (lines 1361-1402) lists it as 'alternative' with evidence_level source_review and a 'Prospective and unexecuted' workflow that only constructs a local contract; it has no paper connectivity or execution acceptance. runtime-target.json does not mention ib_async. It is cited only for the shared IBKR boundary state (local_broker_acceptance 'not_established'), which applies equally to both IBKR paths. Neither IBKR path has broker evidence, so neither is preferred on evidence. Only a same-contract IBKR paper comparison can separate them.
- Lumibot (unqualified) — Source review shows it ships an Alpaca broker, but the catalog card workflow is 'Prospective and unexecuted'. The license conflict is unresolved: LICENSE says GPL-3.0 but setup.py says MIT. Adopting it would add a second strategy engine alongside the selected Nautilus destination. No paper, reconciliation or numeric-risk evidence is retained.
- Zipline Reloaded (out_of_scope) — Its catalog layers are backtesting and factor research, not broker execution. The card records alpaca_fit 'No selected built-in Alpaca paper route verified' and an unexecuted workflow.
- vectorbt (out_of_scope) — It is a vectorized research and backtesting tool. The card says research outputs 'must be translated and verified in the execution engine' and that it has no Alpaca execution route. Its license is Apache-2.0 with Commons Clause, and the workflow is unexecuted.
- skfolio (out_of_scope) — It covers portfolio optimization and model selection, and the card says 'No broker execution'. research-evaluation/receipt.json accepts it only for the causal raw-price label control (20 folds, 21 selections, 6605 records) and states no_pnl_or_execution_claim true. It is pinned at 1.2.9 while upstream is v1.3.0 (pin_behind_upstream).
- Qlib (out_of_scope) — It is an ML and factor research tool. The engines-strategies.json card (line 476) says 'No verified direct Alpaca execution adapter; export dated signals to the chosen engine.' The data-research.json data-qlib card (line 1355) says 'Keep Qlib experiments separate from the selected paper execution engine and broker adapter.' The workflow is unexecuted, and the bundled China/CSI300 config does not prove US compatibility.
- PyPortfolioOpt (out_of_scope) — It is an allocation optimizer. The card says 'Weights are proposals only; execution must check available assets, cash, rounding and open orders'. It has no broker adapter, and the workflow is unexecuted.
- Backtrader (out_of_scope) — Not adopted. It is a legacy backtesting engine. Its Alpaca integration lives in a separate, older repository, and its latest PyPI release and repository HEAD date from 2023. The workflow is unexecuted.
- backtesting.py (out_of_scope) — Not adopted. The card calls it a single-instrument prototyping engine with 'No reviewed Alpaca broker execution adapter' and says it is 'not the portfolio execution/reconciliation host'. It is AGPL-licensed.

Overturn when: Reopen the verdict if either of these checks fails.

(1) SPY/LEAN parity: a qualified rerun of the preregistered comparison against the one_zero case in blueprints/us-equities/historical-simulation/receipt.json still fails a check after the dividend and market-on-open mappings are hardened. The current result is BLOCKED with 4 failed checks (evidence/artifacts/comparison-progress-20260922/summary.json). A repeat failure would reopen Nautilus as the destination against the LEAN oracle.

(2) Broker-state comparison: a same-contract comparison on identical frozen inputs shows an alternative adapter passing cases the selected path fails. The cases are ownership, reconciliation, partial fill, cancel, reconnect and numeric risk. For IBKR, compare the Nautilus in-tree adapter (c1) against ib_async (c10). For Alpaca, compare the alpaca-py path (c12) against LEAN Alpaca (c3) or Lumibot (c9).

The baseline local checks are python3 -m unittest tests.test_nautilus_equity_replay tests.test_alpaca_paper tests.test_adaptive_paper_native -v. Only native paper runs of each arm can overturn the verdict; unit fixtures alone cannot.

Open gaps:
- The IBKR broker boundary is unexecuted. runtime-target.json line 49 records broker_boundaries[ibkr].local_broker_acceptance as 'not_established', and the nautilus-ibkr-adapter card evidence_level is source_review (engines-strategies.json line 1683). No socket session, paper order, cancellation race or reconnect reconciliation has been observed. This is why the winner set's evidence class is source_review.
- No broker boundary has run through Nautilus itself. The one executed Alpaca paper trial used blueprints/us-equities/alpaca-paper/paper_runner.py on alpaca-py. runtime-target.json adaptive_practice.broker_status says the adaptive Nautilus LiveNode trial was 'not started'. Its 180-fill capacity run used zero broker connections.
- SPY/LEAN parity is not established. next_acceptance retained-equity-replay is 'reported_execution_blocked_review_incomplete', and summary.json records result BLOCKED with returned_failed_checks 4.
- The Nautilus AAPL replay uses retrospective synthetic close fills with unlimited depth (OneTickSlippageFillModel) and excludes known dividend and split dates. It qualifies accounting mechanics, not realistic liquidity.
- The LEAN oracle's bundled-backtest evidence ran on a locally patched build (3 LEAN package-reference replacements). resolution-receipt.json states the local dependency patches have not been accepted upstream.
- Native in-flight faults are qualified only in synthetic tests: 27 tests cover partial fill, cancel, rejection, disconnect, crash and ambiguous submit. Recovery was observed only for an already-completed trial.
- Throughput is not established. 200 requests/minute was observed on the paper account. The advertised Elite rate of 1000/minute is not activated or qualified.
- The packet limitation reports two bare matches! expressions in Nautilus risk tests that do not assert denial variants. I did not verify this: it rests on docs/blind-catalog-source-adjudication-20260921.md, which I did not open.
- Nautilus 2.0.0rc5 is a prerelease (runtime-target.json line 29). The packet reports upstream latest as v1.231.0 non-prerelease yet marks pin_behind_upstream false.
- No strategy qualification exists: no point-in-time universe, financing-inclusive performance, broker-calibrated costs or deployable profitability.
- Correction: the alpaca-py card in engines-strategies.json (Sept 19 snapshot) still says evidence_level 'source_review' and 'Prospective and unexecuted'. The later paper-receipt.json supersedes it, but only for a one-trial smoke run.
- Correction: the nautilus-ibkr-adapter card rationale (engines-strategies.json line 1676) calls IBKR the 'selected live-primary broker path', then concedes runtime-target.json records no live-primary designation. Treat live-primary status as unestablished.
- The adaptive-paper-alpaca-adapter (a sota component, not a candidate) is the intended Nautilus Alpaca path. Its catalog card evidence_level is source_review, and its broker_readiness is not_started.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-execution-broker-20260922; codex: -)

#### Identity, provenance and lineage (identity-provenance)

- alpaca-py @ 0.44.0 — This verdict comes from my source review of retained receipts. I re-executed nothing, and each winner is proven only at a bounded scope.

(1) Acquisition (c4 alpaca-py 0.44.0). blueprints/us-equities/authenticated-data/native-receipt.json records a native_cli_e2e run on 2026-09-20:
- 25 AAPL SIP/raw daily bars over 3 pages and 2 corporate actions over 2 pages, from 5 HTTP 200 responses. A terminal page was observed, and private page hashes were recorded.
- 25 of 25 raw closes equal the frozen LEAN probe, and 2 numeric action values are equal.
- 1 currency is unknown, so the actions status is 'reconciliation_incomplete'.
- original_historical_availability is 'not_established'.

(2) Snapshot, replay and eligibility rejection (c5 DuckDB 1.5.5). On real data, blueprints/us-equities/lifecycle-sample/native-receipt.json materialized a DuckDB/Parquet ledger over captured documents ('synthetic': false). It verified five cutoff queries: 0 claims historically, 0 before first observation, 1 at first, 3 at last. historical_universe_eligible is false.
The hash-pinned replay and its four rejections (precision, overflow, overwrite and hash corruption, each exit 2) were shown only on a synthetic fixture. Those results are in blueprints/us-equities/nanosecond-replay/receipt.json ('synthetic': true, market_data_adapter_accepted false; component_ids duckdb, pandas). That receipt counts as synthetic evidence for c5, not native_proven.

(3) Identity and filing acquisition (c7 EdgarTools 5.58.0). In blueprints/us-equities/catalyst-provenance/access-resolution.json, native EdgarTools get_filings returned HTTP 200, with 371 index rows and 360 unique accessions.
The eligibility packets in the same receipt came from the repository's custom adapter, not from EdgarTools. That adapter is blueprints/us-equities/catalyst-provenance/catalyst.py (acquire/packet), and the receipt's limitation calls the bridge 'custom repository code'. The historical packet at 2020-03-03 has eligible_count 0, with 5 excluded before_first_availability, and the observed-time packet qualified 5.
The lifecycle receipt parsed 6 HTTP 200 documents offline under bwrap --unshare-net. They support 3 claims, including documented META ticker reuse. permanent_identity_crosswalk_established is false.

These three are the only adopted candidates with native receipts covering acquisition, identity and eligibility rejection. Every other adopted candidate has one of three things only: unexecuted catalog source review, synthetic-only evidence (c1), or a single XNYS session (c9).
- data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa — This verdict comes from my source review of retained receipts. I re-executed nothing, and each winner is proven only at a bounded scope.

(1) Acquisition (c4 alpaca-py 0.44.0). blueprints/us-equities/authenticated-data/native-receipt.json records a native_cli_e2e run on 2026-09-20:
- 25 AAPL SIP/raw daily bars over 3 pages and 2 corporate actions over 2 pages, from 5 HTTP 200 responses. A terminal page was observed, and private page hashes were recorded.
- 25 of 25 raw closes equal the frozen LEAN probe, and 2 numeric action values are equal.
- 1 currency is unknown, so the actions status is 'reconciliation_incomplete'.
- original_historical_availability is 'not_established'.

(2) Snapshot, replay and eligibility rejection (c5 DuckDB 1.5.5). On real data, blueprints/us-equities/lifecycle-sample/native-receipt.json materialized a DuckDB/Parquet ledger over captured documents ('synthetic': false). It verified five cutoff queries: 0 claims historically, 0 before first observation, 1 at first, 3 at last. historical_universe_eligible is false.
The hash-pinned replay and its four rejections (precision, overflow, overwrite and hash corruption, each exit 2) were shown only on a synthetic fixture. Those results are in blueprints/us-equities/nanosecond-replay/receipt.json ('synthetic': true, market_data_adapter_accepted false; component_ids duckdb, pandas). That receipt counts as synthetic evidence for c5, not native_proven.

(3) Identity and filing acquisition (c7 EdgarTools 5.58.0). In blueprints/us-equities/catalyst-provenance/access-resolution.json, native EdgarTools get_filings returned HTTP 200, with 371 index rows and 360 unique accessions.
The eligibility packets in the same receipt came from the repository's custom adapter, not from EdgarTools. That adapter is blueprints/us-equities/catalyst-provenance/catalyst.py (acquire/packet), and the receipt's limitation calls the bridge 'custom repository code'. The historical packet at 2020-03-03 has eligible_count 0, with 5 excluded before_first_availability, and the observed-time packet qualified 5.
The lifecycle receipt parsed 6 HTTP 200 documents offline under bwrap --unshare-net. They support 3 claims, including documented META ticker reuse. permanent_identity_crosswalk_established is false.

These three are the only adopted candidates with native receipts covering acquisition, identity and eligibility rejection. Every other adopted candidate has one of three things only: unexecuted catalog source review, synthetic-only evidence (c1), or a single XNYS session (c9).
- data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a — This verdict comes from my source review of retained receipts. I re-executed nothing, and each winner is proven only at a bounded scope.

(1) Acquisition (c4 alpaca-py 0.44.0). blueprints/us-equities/authenticated-data/native-receipt.json records a native_cli_e2e run on 2026-09-20:
- 25 AAPL SIP/raw daily bars over 3 pages and 2 corporate actions over 2 pages, from 5 HTTP 200 responses. A terminal page was observed, and private page hashes were recorded.
- 25 of 25 raw closes equal the frozen LEAN probe, and 2 numeric action values are equal.
- 1 currency is unknown, so the actions status is 'reconciliation_incomplete'.
- original_historical_availability is 'not_established'.

(2) Snapshot, replay and eligibility rejection (c5 DuckDB 1.5.5). On real data, blueprints/us-equities/lifecycle-sample/native-receipt.json materialized a DuckDB/Parquet ledger over captured documents ('synthetic': false). It verified five cutoff queries: 0 claims historically, 0 before first observation, 1 at first, 3 at last. historical_universe_eligible is false.
The hash-pinned replay and its four rejections (precision, overflow, overwrite and hash corruption, each exit 2) were shown only on a synthetic fixture. Those results are in blueprints/us-equities/nanosecond-replay/receipt.json ('synthetic': true, market_data_adapter_accepted false; component_ids duckdb, pandas). That receipt counts as synthetic evidence for c5, not native_proven.

(3) Identity and filing acquisition (c7 EdgarTools 5.58.0). In blueprints/us-equities/catalyst-provenance/access-resolution.json, native EdgarTools get_filings returned HTTP 200, with 371 index rows and 360 unique accessions.
The eligibility packets in the same receipt came from the repository's custom adapter, not from EdgarTools. That adapter is blueprints/us-equities/catalyst-provenance/catalyst.py (acquire/packet), and the receipt's limitation calls the bridge 'custom repository code'. The historical packet at 2020-03-03 has eligible_count 0, with 5 excluded before_first_availability, and the observed-time packet qualified 5.
The lifecycle receipt parsed 6 HTTP 200 documents offline under bwrap --unshare-net. They support 3 claims, including documented META ticker reuse. permanent_identity_crosswalk_established is false.

These three are the only adopted candidates with native receipts covering acquisition, identity and eligibility rejection. Every other adopted candidate has one of three things only: unexecuted catalog source review, synthetic-only evidence (c1), or a single XNYS session (c9).

Alternatives:
- pandas exact timestamp support (overlap) — pandas 3.0.6 parsed exact UTC nanoseconds only in a synthetic fixture, recorded in blueprints/us-equities/nanosecond-replay/receipt.json ('synthetic': true, market_data_adapter_accepted false). There it serves as a parsing dependency inside the DuckDB-pinned replay path, not as a separate provenance or identity solution. The packet gives no pin.
- lakeFS (conditional) — The evidence is source review only. The data-lakefs entry in catalogs/us-equities/data-research.json has decision 'alternative' and marks the quickstart as prospective and unexecuted. The same entry states that commits do not make external databases part of one atomic snapshot and that garbage collection can remove historical artifacts. No receipt shows lakeFS pinning an equities snapshot. Adding a lake would need local throughput and concurrency measurements first.
- Databento (conditional) — The evidence is source review only. The data-databento entry in catalogs/us-equities/data-research.json has decision 'conditional' and an unexecuted workflow marked as potentially billable. It needs a licensed dataset, and its feed is exchange-specific rather than consolidated. The packet also cites catalogs/us-equities/simulation-data-review.json for Databento, but that file has no Databento entry. There is no receipt for acquisition, ts_event/ts_recv or corporate actions. This capability has not been tested, which is different from failing.
- Massive Python client (conditional) — The evidence is source review only. The data-massive entry in catalogs/us-equities/data-research.json has decision 'conditional' and an unexecuted workflow that needs a key and an entitlement. Its aggregate adjustment covers splits but not dividends, and the inactive-ticker filters do not prove a complete universe. The packet's review_status is 'not_individually_reviewed', and the cited simulation-data-review.json has no Massive entry.
- exchange_calendars (conditional) — The native evidence is narrow. blueprints/us-equities/data/receipt.json shows one XNYS session (2013-10-07, 13:30-20:00 UTC) inside a 6-event LEAN simulation. That makes it a session-boundary dependency, not evidence of source identity, provenance or eligibility. Its catalog entry is limited to one XNYS session.
- QuestDB (conditional) — The evidence is source review only. The data-questdb entry in data-research.json has decision 'conditional' and records that no server was installed or started. It also warns that dedup/upsert can overwrite corrections. No throughput measurement shows a server is needed over embedded DuckDB.
- ClickHouse (conditional) — The evidence is source review only. The data-clickhouse entry in data-research.json has decision 'conditional' and records that no server, cluster, throughput or reliability evidence was created. Its merges and dedup do not provide an immutable revision ledger. The packet pin, v26.8.7.19-lts, is behind upstream.
- OpenBB (unqualified) — The evidence is source review only. The data-openbb entry has decision 'alternative', and its only workflow is an unexecuted router import. The entry says provider-normalized output does not mean normalized adjustment, time of availability or survivorship semantics. The license is AGPL-3.0, and the packet gives no pin.
- Polars (overlap) — The evidence is source review only. The data-polars entry has decision 'alternative', and it states that a lazy plan is not a point-in-time contract. Polars overlaps the DuckDB path without receipts of its own.
- DVC (unqualified) — The packet marks DVC not adopted, with review_status confirmed_default, but data-research.json lists data-dvc with decision 'default'. That discrepancy is unresolved. The evidence is source review only, and the workflow is unexecuted. The entry says content hashes prove identity, not validity or point-in-time correctness. It has not been shown to close a gap in the winner path.
- sec-edgar-downloader (overlap) — This candidate is not adopted. simulation-data-review.json records 'defer_redundant_downloader', meaning a second acquisition layer that does not resolve historical availability. data-research.json marks it 'alternative' with an unexecuted workflow. EdgarTools already has native acquisition evidence.
- yfinance (out_of_scope) — This candidate is not adopted. The data-yfinance entry has decision 'excluded': the data is for personal use, and it offers only present-day adjusted history and current tickers. That conflicts with the requirement for licensed point-in-time data.

Overturn when: An executed comparison on one frozen plan of representative securities would change the verdict. The plan must include delistings, ticker reuse (FB/META/METV) and corporate actions, and the comparison must show another candidate closing the open gaps with auditable records. The gaps are original historical availability, dividend currency, complete action coverage and a permanent identity crosswalk.

The existing scripts cannot run the challenger arms as they are:
- blueprints/us-equities/alpaca-historical/collect.py hard-requires alpaca_py_version 0.44.0 (line 137), data.alpaca.markets URLs (line 142) and the alpaca SDK (lines 320-326).
- blueprints/us-equities/authenticated-data/compare.py accepts only an AAPL reference with exactly 25 sessions (lines 47-48).
- blueprints/us-equities/nanosecond-replay/replay.py implements only DuckDB materialize and select (lines 172-176).

So a Databento or Massive arm first needs a new provider collector and a generalized multi-symbol comparator, each with its own plan, hashes and verify step. A lakeFS, QuestDB or ClickHouse arm needs new store-specific replay code. That code must reproduce the select results on blueprints/us-equities/nanosecond-replay/fixture.json with identical cutoff selections and all four rejections, and the arm also needs a measured throughput or concurrency need. Identity continuity is re-checked with blueprints/us-equities/lifecycle-sample/sample.py verify-ledger in every arm.

Open gaps:
- Original historical availability of provider observations is not established. The Alpaca receipt records original_historical_availability 'not_established', and the lifecycle ledger sets available_ns equal to observed_ns.
- Corporate-action reconciliation is incomplete: 1 dividend currency is unknown, and historical_coverage_established is false.
- There is no permanent identity crosswalk or continuous symbol-ownership intervals. Both permanent_identity_crosswalk_established and continuous_symbol_ownership_intervals_established are false.
- The evidence covers 1 AAPL sample, 3 hand-selected lifecycle cases and 5 SEC headers. It does not establish a survivorship-free universe or historical universe eligibility.
- The DuckDB replay and rejections (precision, overflow, overwrite, hash corruption) were demonstrated only on a synthetic fixture. No market-data adapter or symbol mapping was accepted.
- The SEC acceptance timezone is not established. blueprints/us-equities/lifecycle-sample/native-receipt.json line 15 says the native ACCEPTANCE-DATETIME is timezone-naive. The UTC-suffixed accepted_at values in blueprints/us-equities/catalyst-provenance/access-resolution.json come from catalyst.py, which assumes the naive value is America/New_York (catalyst.py lines 99 and 119-124). That assumption is unverified, so the dissemination lag stays unknown. It does not change the historical-cutoff result, which excludes by first_observed_at.
- The historical and observed eligibility packets come from the custom catalyst.py adapter. EdgarTools did not produce them.
- No candidate has an executed licensing, rights or entitlement check beyond Alpaca's bounded historical SIP request.
- The lineage and versioning components listed in the packet as not in candidates are not assessed here: data-openlineage, data-iceberg, data-arcticdb and data-mlflow, and Pandera (c15) as well. OpenLineage is source_review with decision 'conditional' per the challenger refuter's reading of data-research.json. This is a coverage gap, not a result.
- Databento, Massive, lakeFS, QuestDB, ClickHouse, OpenBB and Polars are untested for this requirement, which does not mean they failed. No comparison exists, and the tooling to run one does not exist yet.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-identity-provenance-20260922; codex: -)

#### Market data and reference (market-data-reference)

- data-alpaca-py @ v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28 — Among the adopted candidates, these three have retained receipts showing native execution of the acquisition, snapshot-storage and SEC reference steps that the requirement asks for. Adopted c3 exchange_calendars and c8 pandas also have native receipts, but they cover a session-calendar step and a parse step only (see alternatives). In each case the requirement's rejection and fail-closed behaviour comes from repository code running on top of these packages, not from the packages themselves.

(1) c9 alpaca-py 0.44.0 acquired licensed, source-identifiable observations and corporate actions. blueprints/us-equities/authenticated-data/native-receipt.json records native_cli_e2e 'native-alpaca-historical-20260920': 25 AAPL SIP/raw daily bars (3 pages) and 2 corporate actions (2 pages), with 5 HTTP 200 pages, observed terminal pagination and hash-anchored private artifacts. The bars matched the frozen LEAN probe 25/25 (maximum_absolute_close_difference "0.00"). The actions show numeric_values_equal 2 and unknown_currency 1, with status reconciliation_incomplete and original_historical_availability not_established. The comparison ran through the repository's compare.py, which is hard-wired to Alpaca and AAPL. catalogs/us-equities/runtime-target.json selects alpaca-py 0.44.0 for ingestion.

(2) c14 DuckDB 1.5.5 supplied the BIGINT/Parquet storage and reads for exact analytical snapshots. blueprints/us-equities/nanosecond-replay/receipt.json covers a SYNTHETIC fixture run natively through pandas 3.0.6 and DuckDB. It shows exact nanosecond cutoff selection and an identical early replay. The precision, overflow, overwrite and hash-mismatch rejections (exit_code 2) are enforced by the custom replay.py and point-in-time/temporal_snapshot.py contract (PIT.require and manifest checks), not by DuckDB (replay.py lines 30-41 and 115-137; DuckDB is used at lines 84-112 and 140-150). blueprints/us-equities/data/receipt.json records the Parquet sha256 of 6 LEAN simulation events on XNYS 2013-10-07. That receipt does not name DuckDB; the DuckDB use is visible only in blueprints/us-equities/data/summarize_backtest.py (lines 2, 8 and 19). blueprints/us-equities/lifecycle-sample/native-receipt.json lists duckdb 1.5.5 in its runtime, preserving source anchors and exact observation cutoffs over 6 HTTP 200 public documents through custom adapters.

(3) c6 EdgarTools 5.58.0 is the only adopted candidate with native SEC reference acquisition. blueprints/us-equities/catalyst-provenance/access-resolution.json native_upstream (lines 31-56) records get_filings with exit_code 0, http_status 200, cohort_rows 371, unique_accessions 360 and selected_context_rows 5. It names the original source URL and the complete compressed source sha256. The lifecycle-sample receipt records EdgarTools 5.58.0 in the offline processing that supports the ordered META ticker-reuse documentary evidence. EdgarTools did not produce the header acquisition or the unknown-availability rejection. The 5 headers came from the stdlib-only catalyst.py adapter (lines 57-65; its imports at lines 3-13 contain no edgar import). The historical packet (eligible_count 0, 5 before_first_availability at 2020-03-03) and the observed packet (5 qualified) also came from catalyst.py. The receipt itself says the provenance bridge is custom repository code (line 15). That rejection is therefore repository behaviour running over SEC data.

No candidate has an executed, measured comparison against another candidate. The selection rests on native receipts versus source review only.
- data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa — Among the adopted candidates, these three have retained receipts showing native execution of the acquisition, snapshot-storage and SEC reference steps that the requirement asks for. Adopted c3 exchange_calendars and c8 pandas also have native receipts, but they cover a session-calendar step and a parse step only (see alternatives). In each case the requirement's rejection and fail-closed behaviour comes from repository code running on top of these packages, not from the packages themselves.

(1) c9 alpaca-py 0.44.0 acquired licensed, source-identifiable observations and corporate actions. blueprints/us-equities/authenticated-data/native-receipt.json records native_cli_e2e 'native-alpaca-historical-20260920': 25 AAPL SIP/raw daily bars (3 pages) and 2 corporate actions (2 pages), with 5 HTTP 200 pages, observed terminal pagination and hash-anchored private artifacts. The bars matched the frozen LEAN probe 25/25 (maximum_absolute_close_difference "0.00"). The actions show numeric_values_equal 2 and unknown_currency 1, with status reconciliation_incomplete and original_historical_availability not_established. The comparison ran through the repository's compare.py, which is hard-wired to Alpaca and AAPL. catalogs/us-equities/runtime-target.json selects alpaca-py 0.44.0 for ingestion.

(2) c14 DuckDB 1.5.5 supplied the BIGINT/Parquet storage and reads for exact analytical snapshots. blueprints/us-equities/nanosecond-replay/receipt.json covers a SYNTHETIC fixture run natively through pandas 3.0.6 and DuckDB. It shows exact nanosecond cutoff selection and an identical early replay. The precision, overflow, overwrite and hash-mismatch rejections (exit_code 2) are enforced by the custom replay.py and point-in-time/temporal_snapshot.py contract (PIT.require and manifest checks), not by DuckDB (replay.py lines 30-41 and 115-137; DuckDB is used at lines 84-112 and 140-150). blueprints/us-equities/data/receipt.json records the Parquet sha256 of 6 LEAN simulation events on XNYS 2013-10-07. That receipt does not name DuckDB; the DuckDB use is visible only in blueprints/us-equities/data/summarize_backtest.py (lines 2, 8 and 19). blueprints/us-equities/lifecycle-sample/native-receipt.json lists duckdb 1.5.5 in its runtime, preserving source anchors and exact observation cutoffs over 6 HTTP 200 public documents through custom adapters.

(3) c6 EdgarTools 5.58.0 is the only adopted candidate with native SEC reference acquisition. blueprints/us-equities/catalyst-provenance/access-resolution.json native_upstream (lines 31-56) records get_filings with exit_code 0, http_status 200, cohort_rows 371, unique_accessions 360 and selected_context_rows 5. It names the original source URL and the complete compressed source sha256. The lifecycle-sample receipt records EdgarTools 5.58.0 in the offline processing that supports the ordered META ticker-reuse documentary evidence. EdgarTools did not produce the header acquisition or the unknown-availability rejection. The 5 headers came from the stdlib-only catalyst.py adapter (lines 57-65; its imports at lines 3-13 contain no edgar import). The historical packet (eligible_count 0, 5 before_first_availability at 2020-03-03) and the observed packet (5 qualified) also came from catalyst.py. The receipt itself says the provenance bridge is custom repository code (line 15). That rejection is therefore repository behaviour running over SEC data.

No candidate has an executed, measured comparison against another candidate. The selection rests on native receipts versus source review only.
- data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a — Among the adopted candidates, these three have retained receipts showing native execution of the acquisition, snapshot-storage and SEC reference steps that the requirement asks for. Adopted c3 exchange_calendars and c8 pandas also have native receipts, but they cover a session-calendar step and a parse step only (see alternatives). In each case the requirement's rejection and fail-closed behaviour comes from repository code running on top of these packages, not from the packages themselves.

(1) c9 alpaca-py 0.44.0 acquired licensed, source-identifiable observations and corporate actions. blueprints/us-equities/authenticated-data/native-receipt.json records native_cli_e2e 'native-alpaca-historical-20260920': 25 AAPL SIP/raw daily bars (3 pages) and 2 corporate actions (2 pages), with 5 HTTP 200 pages, observed terminal pagination and hash-anchored private artifacts. The bars matched the frozen LEAN probe 25/25 (maximum_absolute_close_difference "0.00"). The actions show numeric_values_equal 2 and unknown_currency 1, with status reconciliation_incomplete and original_historical_availability not_established. The comparison ran through the repository's compare.py, which is hard-wired to Alpaca and AAPL. catalogs/us-equities/runtime-target.json selects alpaca-py 0.44.0 for ingestion.

(2) c14 DuckDB 1.5.5 supplied the BIGINT/Parquet storage and reads for exact analytical snapshots. blueprints/us-equities/nanosecond-replay/receipt.json covers a SYNTHETIC fixture run natively through pandas 3.0.6 and DuckDB. It shows exact nanosecond cutoff selection and an identical early replay. The precision, overflow, overwrite and hash-mismatch rejections (exit_code 2) are enforced by the custom replay.py and point-in-time/temporal_snapshot.py contract (PIT.require and manifest checks), not by DuckDB (replay.py lines 30-41 and 115-137; DuckDB is used at lines 84-112 and 140-150). blueprints/us-equities/data/receipt.json records the Parquet sha256 of 6 LEAN simulation events on XNYS 2013-10-07. That receipt does not name DuckDB; the DuckDB use is visible only in blueprints/us-equities/data/summarize_backtest.py (lines 2, 8 and 19). blueprints/us-equities/lifecycle-sample/native-receipt.json lists duckdb 1.5.5 in its runtime, preserving source anchors and exact observation cutoffs over 6 HTTP 200 public documents through custom adapters.

(3) c6 EdgarTools 5.58.0 is the only adopted candidate with native SEC reference acquisition. blueprints/us-equities/catalyst-provenance/access-resolution.json native_upstream (lines 31-56) records get_filings with exit_code 0, http_status 200, cohort_rows 371, unique_accessions 360 and selected_context_rows 5. It names the original source URL and the complete compressed source sha256. The lifecycle-sample receipt records EdgarTools 5.58.0 in the offline processing that supports the ordered META ticker-reuse documentary evidence. EdgarTools did not produce the header acquisition or the unknown-availability rejection. The 5 headers came from the stdlib-only catalyst.py adapter (lines 57-65; its imports at lines 3-13 contain no edgar import). The historical packet (eligible_count 0, 5 before_first_availability at 2020-03-03) and the observed packet (5 qualified) also came from catalyst.py. The receipt itself says the provenance bridge is custom repository code (line 15). That rejection is therefore repository behaviour running over SEC data.

No candidate has an executed, measured comparison against another candidate. The selection rests on native receipts versus source review only.

Alternatives:
- Massive Python client (conditional) — The evidence is source review only. The data-research.json data-massive entry has decision 'conditional' and a native_workflow marked 'Prospective and UNEXECUTED'. There is no acquisition, entitlement or comparison receipt, and the repository has no Massive collector. The catalog notes that aggregate adjustment covers splits but not dividends. The packet's second evidence_ref, catalogs/us-equities/simulation-data-review.json, contains no Massive entry.
- Databento (conditional) — The evidence is source review only. The data-databento entry has decision 'conditional' and an UNEXECUTED workflow that may be billable. It is potentially stronger for licensed exchange-level history, point-in-time reference data and ts_event/ts_recv. However, there is no acquisition receipt, cost measurement, coverage comparison or collector in the repository. The exchange-specific feed is not consolidated US coverage, and corporate-action redistribution is restricted. simulation-data-review.json contains no Databento entry.
- exchange_calendars (overlap) — It has native evidence but is a complementary session-boundary dependency, not an acquisition or snapshot component. blueprints/us-equities/data/receipt.json records one XNYS session (2013-10-07, 13:30-20:00 UTC) via summarize_backtest.py. The catalog limitation says this does not cover every holiday, future schedule, venue, extended-hours session or halt. Retain it as the calendar companion.
- QuestDB (conditional) — The evidence is source review only. No server was installed or started. The catalog adopts it conditionally, for sustained tick ingestion after embedded files fail measured needs, but no throughput or concurrency measurement exists. Dedup/upsert can overwrite corrections unless a raw immutable ledger is kept.
- pandas exact timestamp support (overlap) — pandas 3.0.6 ran natively only as the timestamp parser (replay.py utc_ns, lines 30-41) in front of DuckDB, on synthetic clocks and symbols. The receipt states market_data_adapter_accepted false. It adds no independent acquisition or snapshot capability.
- Polars (overlap) — The evidence is source review only. The catalog lists Polars as an alternative to the SQL path and warns against duplicating a full SQL pipeline. There is no native receipt, and Polars supplies no data, corporate actions or point-in-time contract.
- ClickHouse (conditional) — The evidence is source review only. The command is prospective, and there is no server, throughput or reliability evidence. Background merges and deduplication are not an immutable revision ledger. The pin v26.8.7.19-lts is behind upstream v26.9.2.8-stable (packet pin_behind_upstream true).
- lakeFS (conditional) — The evidence is source review only. The catalog decision is 'alternative', aimed at concurrent teams that need atomic lake branches, and the quickstart is unexecuted. Commits do not make external databases part of an atomic snapshot, and garbage collection can remove historical artifacts.
- OpenBB (unqualified) — The evidence is source review only; the workflow imports the router but makes no data request. Provider-normalized output does not normalize adjustment, time-of-availability or survivorship semantics. OpenBB is AGPL-3.0, and each provider's terms are separate.
- yfinance (out_of_scope) — Not adopted. The catalog decision is 'excluded' because the data is for personal use and consists of present-day adjusted history and current tickers, so it cannot support point-in-time research.
- sec-edgar-downloader (overlap) — Not adopted. The catalog decision is 'alternative', a raw-only collector, and simulation-data-review.json records 'defer_redundant_downloader'. EdgarTools has a native get_filings receipt for the same SEC scope.
- Pandera (overlap) — Not adopted in this layer; it is the default in the data-quality layer. It is a schema-contract complement whose workflow is unexecuted and uses synthetic keys. Schema validation does not establish completeness, corporate actions or absence of leakage.
- DVC (overlap) — Not adopted in this layer; it is the default for data versioning. Its workflow is unexecuted. Content hashes prove identity, not validity or point-in-time correctness, and the winners' receipts already pin their artifacts by sha256.

Overturn when: Acquisition (c9): the repository currently has no runnable challenger arm. blueprints/us-equities/authenticated-data/compare.py reproduces only the c9 baseline. It loads alpaca-historical/collect.py (lines 15-20), verifies an Alpaca receipt (line 111) and rejects any symbol other than AAPL or any reference that is not exactly 25 sessions (lines 39-40 and 47-48). collect.py validate_plan also requires AAPL/sip/raw, alpaca_py_version 0.44.0 and data.alpaca.markets URLs (lines 125-143). The verdict should change only after an executed comparison meets all of the following:
- It uses a new provider-specific collector for Massive (c1) or Databento (c2). No such file exists yet.
- It uses a comparator generalized beyond Alpaca/AAPL.
- It runs against the same frozen blueprints/us-equities/authenticated-data/plan.json AAPL 2020-08-03..2020-09-04 contract plus representative delisted, ticker-reused (META) and dividend or split names.
- It shows the challenger reaching full corporate-action reconciliation (currency included) and auditable original historical availability where alpaca-py leaves them not_established, at acceptable measured request cost.
Until then, python3 blueprints/us-equities/authenticated-data/compare.py --run <run> --receipt-sha256 <sha> --lean <lean results> --lean-sha256 <sha> is the baseline check. The verdict should also be reopened if that baseline no longer reproduces 25/25 equal bars.

Snapshot store (c14): overturn if python3 blueprints/us-equities/nanosecond-replay/replay.py run on blueprints/us-equities/nanosecond-replay/fixture.json fails to reproduce the recorded selections and rejections. Also overturn if a measured throughput or concurrency test justifies a server (QuestDB c7 or ClickHouse c13).

SEC reference (c6): overturn if a native get_filings rerun through blueprints/us-equities/catalyst-provenance/native_edgar.py fails to reproduce the 371 rows and 360 unique accessions for the same day.

Open gaps:
- The Alpaca acquisition covers one retrospective AAPL sample: 25 daily bars and 2 actions. There is no survivorship-free universe, delisting completeness, intraday data or real-time entitlement.
- Corporate-action reconciliation is incomplete. 1 of 2 actions has an unknown dividend currency, and original historical availability is not_established.
- No executed cross-provider comparison exists. The existing compare.py and collect.py are hard-wired to Alpaca/AAPL, and there is no Massive or Databento collector, so the challenger arms are not runnable yet.
- The catalog entry for data-alpaca-py (catalogs/us-equities/data-research.json lines 22 and 38) still says evidence_level source_review and 'No account, entitlement, data request or order was exercised'. The later native receipt (2026-09-20) supersedes it, but the catalog has not been reconciled.
- The nanosecond replay is synthetic (market_data_adapter_accepted false). The fail-closed rejections are repository contract code (replay.py and temporal_snapshot.py), not DuckDB capabilities. DuckDB has no acceptance for ingesting a real feed.
- The EdgarTools-native evidence is limited to the get_filings index acquisition (371 rows, 360 unique accessions, 5 context rows) and the offline lifecycle parsing. The header acquisition and the unknown-availability rejection were produced by the stdlib-only catalyst.py. Historical as-known availability remains unestablished.
- The lifecycle sample has three hand-selected cases. There is no permanent identity crosswalk, and the timezone of the SEC acceptance timestamps is unknown.
- exchange_calendars is confirmed for one XNYS session only.
- No measured throughput or concurrency evidence exists to decide between embedded DuckDB and a server (QuestDB or ClickHouse).
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-market-data-reference-20260922; codex: -)

#### Observability and hosting (observability-hosting)

- codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0 — This is my own review of the retained receipts. No provider judgment was carried over, and no TypeSafe inference was run. The same three candidates are selected in this revision, with corrected reasons. Each winner covers one part of the requirement on native-execution evidence.

(1) c7 Codex: bounded research under native identity, with failed attempts retained. blueprints/us-equities/workers/receipt.json records a native SDK research run: status "completed", configured_model gpt-6-astra, duration_ms 58410, total totalTokens 135311. It keeps two failed follow-up extraction turns with their full usage (all_three_native_turns totalTokens 204091; successful_research_tasks 1, blocked_file_extraction_tasks 2). This receipt is the only direct evidence here that failed-attempt usage is retained. Its boundary is limited, though: read-only filesystem mode does not restrict external MCP mutations, and broker authority is withheld only because no broker keys or broker tools were supplied (line 110). For the research workload, telemetry reconciles in adoption/paired/observation.json, checked 2026-09-19: astra all_six_prometheus_categories_match_native true, native_loki_instance_matches_prometheus true, total_tokens 20776. Correction to the earlier proposal: the foundation-native-20260920.json codex result (loki_matches_direct true, prometheus_matches_direct true, every prometheus_missing category 0) came from a different task, seven MCP calls, run with --ask-for-approval never and --sandbox danger-full-access (lines 301-318). It shows telemetry fidelity on a tool-heavy run, not the read-only research boundary.

(2) c2 Dagu: supervision of owned processes. blueprints/us-equities/hosting/receipt.json records:
- a native failure fixture (step exit 23 -> failed, dependent step aborted)
- a `dagu stop` cancellation (aborted)
- completed history kept after a service restart
- 401 for anonymous and 200 for authenticated HTTP requests
- model_calls 0 and broker_calls 0

adoption/paired/receipt.json lines 47-51 record Dagu 2.16.6 research_pair succeeded with exit_code 0 (Astra then Claude).

(3) c1 OpenTelemetry Collector contrib: scoped telemetry. It is a component in research-runtime/receipt.json and adoption/paired/receipt.json, and both reconcile native usage against Prometheus and Loki with bodies redacted or omitted.

Trade-off explicitly accepted under the 3-winner cap: c1 does not store telemetry itself. Storage is done by c6 Prometheus and c12 Loki. Recoverable state beyond Dagu's completed history is covered only by c17 Restic, on the same host. c7/c2/c1 alone therefore do not meet the retention and recoverable-state parts of the requirement; those parts depend on c6, c12 and c17 as companions. Codex was chosen over the co-equal c19 Claude Code on two points. First, it retains failed-turn usage. Second, it matched Prometheus on the same seven-MCP-call task where Claude missed 77317 tokens. Claude has the stronger tool boundary (zero exposed tools); see c19. Evidence class: native execution plus local integration on one WSL host. No designed winner comparison was run.
- dagu @ v2.16.6 — This is my own review of the retained receipts. No provider judgment was carried over, and no TypeSafe inference was run. The same three candidates are selected in this revision, with corrected reasons. Each winner covers one part of the requirement on native-execution evidence.

(1) c7 Codex: bounded research under native identity, with failed attempts retained. blueprints/us-equities/workers/receipt.json records a native SDK research run: status "completed", configured_model gpt-6-astra, duration_ms 58410, total totalTokens 135311. It keeps two failed follow-up extraction turns with their full usage (all_three_native_turns totalTokens 204091; successful_research_tasks 1, blocked_file_extraction_tasks 2). This receipt is the only direct evidence here that failed-attempt usage is retained. Its boundary is limited, though: read-only filesystem mode does not restrict external MCP mutations, and broker authority is withheld only because no broker keys or broker tools were supplied (line 110). For the research workload, telemetry reconciles in adoption/paired/observation.json, checked 2026-09-19: astra all_six_prometheus_categories_match_native true, native_loki_instance_matches_prometheus true, total_tokens 20776. Correction to the earlier proposal: the foundation-native-20260920.json codex result (loki_matches_direct true, prometheus_matches_direct true, every prometheus_missing category 0) came from a different task, seven MCP calls, run with --ask-for-approval never and --sandbox danger-full-access (lines 301-318). It shows telemetry fidelity on a tool-heavy run, not the read-only research boundary.

(2) c2 Dagu: supervision of owned processes. blueprints/us-equities/hosting/receipt.json records:
- a native failure fixture (step exit 23 -> failed, dependent step aborted)
- a `dagu stop` cancellation (aborted)
- completed history kept after a service restart
- 401 for anonymous and 200 for authenticated HTTP requests
- model_calls 0 and broker_calls 0

adoption/paired/receipt.json lines 47-51 record Dagu 2.16.6 research_pair succeeded with exit_code 0 (Astra then Claude).

(3) c1 OpenTelemetry Collector contrib: scoped telemetry. It is a component in research-runtime/receipt.json and adoption/paired/receipt.json, and both reconcile native usage against Prometheus and Loki with bodies redacted or omitted.

Trade-off explicitly accepted under the 3-winner cap: c1 does not store telemetry itself. Storage is done by c6 Prometheus and c12 Loki. Recoverable state beyond Dagu's completed history is covered only by c17 Restic, on the same host. c7/c2/c1 alone therefore do not meet the retention and recoverable-state parts of the requirement; those parts depend on c6, c12 and c17 as companions. Codex was chosen over the co-equal c19 Claude Code on two points. First, it retains failed-turn usage. Second, it matched Prometheus on the same seven-MCP-call task where Claude missed 77317 tokens. Claude has the stronger tool boundary (zero exposed tools); see c19. Evidence class: native execution plus local integration on one WSL host. No designed winner comparison was run.
- opentelemetry-collector-contrib @ v0.161.0 — This is my own review of the retained receipts. No provider judgment was carried over, and no TypeSafe inference was run. The same three candidates are selected in this revision, with corrected reasons. Each winner covers one part of the requirement on native-execution evidence.

(1) c7 Codex: bounded research under native identity, with failed attempts retained. blueprints/us-equities/workers/receipt.json records a native SDK research run: status "completed", configured_model gpt-6-astra, duration_ms 58410, total totalTokens 135311. It keeps two failed follow-up extraction turns with their full usage (all_three_native_turns totalTokens 204091; successful_research_tasks 1, blocked_file_extraction_tasks 2). This receipt is the only direct evidence here that failed-attempt usage is retained. Its boundary is limited, though: read-only filesystem mode does not restrict external MCP mutations, and broker authority is withheld only because no broker keys or broker tools were supplied (line 110). For the research workload, telemetry reconciles in adoption/paired/observation.json, checked 2026-09-19: astra all_six_prometheus_categories_match_native true, native_loki_instance_matches_prometheus true, total_tokens 20776. Correction to the earlier proposal: the foundation-native-20260920.json codex result (loki_matches_direct true, prometheus_matches_direct true, every prometheus_missing category 0) came from a different task, seven MCP calls, run with --ask-for-approval never and --sandbox danger-full-access (lines 301-318). It shows telemetry fidelity on a tool-heavy run, not the read-only research boundary.

(2) c2 Dagu: supervision of owned processes. blueprints/us-equities/hosting/receipt.json records:
- a native failure fixture (step exit 23 -> failed, dependent step aborted)
- a `dagu stop` cancellation (aborted)
- completed history kept after a service restart
- 401 for anonymous and 200 for authenticated HTTP requests
- model_calls 0 and broker_calls 0

adoption/paired/receipt.json lines 47-51 record Dagu 2.16.6 research_pair succeeded with exit_code 0 (Astra then Claude).

(3) c1 OpenTelemetry Collector contrib: scoped telemetry. It is a component in research-runtime/receipt.json and adoption/paired/receipt.json, and both reconcile native usage against Prometheus and Loki with bodies redacted or omitted.

Trade-off explicitly accepted under the 3-winner cap: c1 does not store telemetry itself. Storage is done by c6 Prometheus and c12 Loki. Recoverable state beyond Dagu's completed history is covered only by c17 Restic, on the same host. c7/c2/c1 alone therefore do not meet the retention and recoverable-state parts of the requirement; those parts depend on c6, c12 and c17 as companions. Codex was chosen over the co-equal c19 Claude Code on two points. First, it retains failed-turn usage. Second, it matched Prometheus on the same seven-MCP-call task where Claude missed 77317 tokens. Claude has the stronger tool boundary (zero exposed tools); see c19. Evidence class: native execution plus local integration on one WSL host. No designed winner comparison was run.

Alternatives:
- Claude Code (measured_tradeoff) — Claude Code is a co-equal native research worker. The earlier reason for placing it below Codex (a "first Claude run Prometheus gap") was wrong for the research workload. Two Claude research runs on 2026-09-19 matched telemetry on their first request. research-runtime/receipt.json line 112 records native_usage_equals_prometheus_and_loki true with exposed_tool_count 0. adoption/paired/observation.json lines 72-79 record all_four_prometheus_categories_match_native true, loki_instance_matches_prometheus true and all_four_api_request_usage_categories_match_native true, for a run under Dagu research-pair with exit 0. Its broker boundary is stronger than c7's: zero exposed tools (`--tools '' --disallowedTools '*'`, research-runtime/receipt.json line 169; adoption/paired/receipt.json line 29). The trade-off comes from same-task observations of both clients. (a) On the 2026-09-20 seven-MCP-call task, Codex matched Prometheus, but Claude's prometheus_matches_direct was false with prometheus_missing total_tokens 77317 (foundation-native-20260920.json lines 353-359); Loki matched for both. (b) No failed Claude turn with its usage is retained, while c7's worker receipt keeps two. Claude therefore trails on the requirement's tool-bearing telemetry and failed-attempt clauses and leads on the no-broker-authority clause. The packet gives no pin (pin null). docs/foundation-closure-20260921.md line 52 records installed 2.1.278.
- Prometheus (overlap) — Prometheus is the metric store behind the selected Collector, so it complements c1 rather than offering another way to meet the requirement. It is outside the winner set only because of the 3-winner cap, and the retention clause depends on it. Observed gap: on the 2026-09-20 seven-MCP-call task, Claude's Prometheus series missed 77317 total tokens (foundation-native-20260920.json lines 353-359). Codex matched on that task, and both clients matched on the 2026-09-19 tool-free research runs (adoption/paired/observation.json lines 27 and 72). docs/dashboard-rendered-acceptance.md records seven scrape targets up and states that scraping is not provider-level or whole-ecosystem end-to-end evidence.
- Loki (overlap) — Loki is the sanitized log store behind the same Collector and complements c1. Its records matched native usage on every retained run: Codex loki_matched_requests 9 and Claude 6 on 2026-09-20; paired Astra 18 records and Claude 51 records, with instances matching Prometheus. It stores only labels and redacted bodies, and the catalog records no trace database and no high availability. It is outside the winner set only because of the cap, and the retention clause depends on it.
- Grafana (overlap) — Grafana visualizes Prometheus and Loki and adds no ingestion, supervision or state recovery. Its evidence class is corrected to native_proven, matching the packet's evidence_kind and catalog evidence_level (agents-operations.json line 950). The catalog limits that proof to local health, provisioned data-source and dashboard queries, and UI checks, with no external publication and no high availability (line 965). docs/dashboard-rendered-acceptance.md records exact panel-query agreement for memory, Qdrant and QMD, and also that Claude had no current telemetry series.
- Restic (conditional) — Restic is the only adopted candidate with native restore evidence for recoverable state beyond Dagu history, and the winner set depends on it for that clause. Its scope is same-host only. It restored ai-memory (324 files byte-equal) and Qdrant (201 points, exact query match). The repository and password are on one host, with off_host false, no key escrow, no schedule and no retention deletion. Telemetry stores and process supervision are not covered.
- DeerFlow (conditional) — One embedded ACP research prompt completed (totalTokens 42345). DeerFlow discards ACP completion and usage, so those figures came from private adapter logs. The read-only mode label mapped to workspaceWrite/on-request. No standing service, planner/UI or recovery was accepted. The 2026-09-21 review is source-only, at a newer revision.
- Temporal (conditional) — Source review only. Temporal is the named escalation for work that must survive host loss, but no local execution, failure/cancellation or restart receipt exists. The catalog notes that activities retry by default.
- LangGraph (unqualified) — Source review only, with an import smoke test as the proposed command. InMemorySaver loses state on restart. LangGraph is an agent-state graph, not a process supervisor or telemetry path. The pin is behind upstream (1.2.11 vs 1.2.12).
- Prefect (unqualified) — Source review only. No flow is supplied or scheduled. Prefect would replace Dagu as the first scheduler rather than run on top of it. There is no failure/cancellation/restart receipt.
- Dagster (out_of_scope) — Dagster is catalogued for data orchestration (asset lineage and backfills), not for supervising research workers or carrying telemetry. Source review only, and no definitions file is included.
- OpenAI Agents SDK (unqualified) — Source review only, with no provider call. It is API-backed and does not inherit native Codex account identity. Tracing is on by default, so a destination and a sensitive-data policy are required.
- OpenHands Agent Canvas (unqualified) — Source review of a README only. Hosting, account boundaries, persistence and migration are explicitly unqualified.
- OpenHands SDK (unqualified) — Source review only. It is a challenger for remote or isolated workers. Installation, native-account and recovery acceptance are all open.
- Deep Agents (unqualified) — Source review only. The review names it a serious challenger but requires the same source-research task, permission boundaries, recovery and full cost comparison, none of which has run.
- Microsoft Agent Framework (unqualified) — Source review only. It was listed to fill a discovery gap and needs a qualified application workflow before any runtime is added.
- OmniRoute (observed_failure) — Not adopted. OmniRoute is a routing gateway, not an observability or hosting component, and gateway inference failed acceptance. The Codex client attempt returned HTTP 400 (prefixed raw model not supported); the receipt keeps it separate from a direct HTTP 429 quota probe on the OpenAI-compatible route (foundation-native-20260920.json lines 185-204). The Claude client returned HTTP 429 after a launcher parser failure. Native encrypted restore ignored .enc files.

Overturn when: Two checks could change the verdict.

Worker choice (c7 vs c19): run the Claude worker in blueprints/us-equities/research-runtime/research-pair.yaml under Dagu. Claude already has tool-free, first-request telemetry parity, so that is not the deciding check. The verdict flips to c19 if both of the following hold:
(a) Claude retains a failed turn with full usage that reconciles to Prometheus and Loki.
(b) On a tool-bearing research run under a no-broker tool allowlist, Claude matches Prometheus in all four categories. Its 2026-09-20 seven-MCP-call run missed 77317 tokens.
The Codex choice also weakens if a Codex research run cannot keep its all-category Prometheus/Loki match once exposed tools are restricted to zero or to an allowlist that blocks MCP mutations.

Supervision choice: another scheduler (Temporal c20, Prefect c8, or Dagu v2.17.0) running blueprints/us-equities/hosting/research-evidence.yaml would have to:
- reproduce the hosting/receipt.json failure, cancellation and restart checks
- show in-flight resumption after a kill, without a duplicate effect owner

Regression check: `python3 -m unittest tests/test_observability.py` must keep passing. It checks only the process-identity and observation helpers of the current Codex blueprints/us-equities/workers/native_worker.py. It is not a check that transfers to other workers.

Open gaps:
- No research-workload receipt shows c7 running with a tool boundary equal to Claude's zero exposed tools. Read-only filesystem mode does not restrict external MCP mutations, and broker authority is withheld only because no broker keys or tools were supplied (workers/receipt.json line 110). The tool-heavy Codex telemetry match ran with danger-full-access and approval never.
- No failed Claude turn with its usage is retained, so c19 cannot yet be compared with c7 on the failed-attempt clause.
- The winners c7/c2/c1 alone do not meet the retention or recoverable-state clauses. Storage depends on c6/c12, and restore depends on c17, which is same-host only with no off-host disaster recovery or key escrow. Loki and Prometheus stores were not backed up.
- Dagu's restart kept completed history only. In-flight resumption and host-loss recovery are not shown (hosting/receipt.json line 100).
- The Dagu pin v2.16.6 is behind upstream v2.17.0, and the newer release has not been exercised.
- The Codex configured model and provider are verified, but there is no independent per-request provider attestation.
- Claude's tool-heavy Prometheus gap (77317) is not resolved for tool-bearing runs. Tool-free research runs matched.
- Collector traces are disabled and no trace database is deployed. There is no high availability and no external alert destination.
- No measured comparison exists against Temporal, Prefect, OpenHands, Deep Agents or Microsoft Agent Framework, which have source review only.
- The user service stops when Windows shuts down. There is no continuous off-host hosting, paid hosting or unattended broker operation.
- All evidence comes from one WSL host dated 2026-09-19/20. It does not carry over to a new WSL or macOS machine.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-observability-hosting-20260922; codex: -)

#### Portfolio and risk (portfolio-risk)

- nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e) — The requirement asks for four things: the NautilusTrader destination, reproducible equity accounting, the retained LEAN oracle, and a broker boundary with numeric risk and independent reconciliation. These three candidates are the only adopted ones with executed evidence for those parts.

c15 NautilusTrader 2.0.0rc5:
- evidence/receipts/native-nautilus-v2-20260920.json records the unchanged upstream synthetic EURUSD quickstart (commit 1b0a49d) run twice in isolation. Both runs ended at 1000431.00000 USD cash, realized PnL 431.00, all positions flat.
- blueprints/us-equities/engine-nautilus/equity-replay/receipt.json is a local integration, not an upstream test. It replayed 15 AAPL bars in two scenarios, twice each, with exit code 0. Baseline: realized PnL -133.40, ending cash 99866.60. Fee/slippage stress: fees 10.00, realized PnL -144.40. It verified 10 cash transitions per scenario, the account CSV repeated byte-identically, a separate reviewer recomputed the cash and PnL, and the 8 local synthetic tests passed.
- catalogs/us-equities/runtime-target.json names it the selected destination (engine.decision "selected_destination").

c16 LEAN:
- blueprints/us-equities/historical-simulation/receipt.json records 6 native simulations at source pin 985ef30. Five invested scenarios ended flat with fill, fee and dividend cash reconciled. The over_limit scenario got one native buying-power rejection and zero fills. The first case ended at 90734.08 USD with 428.64 USD dividends.
- blueprints/us-equities/engine/resolution-receipt.json shows the unchanged bundled backtest still passing: Completed, 3943 data points, 3 orders, matching the original order-list hash.
- This is the numeric risk and cash oracle the requirement says to preserve.

c8 alpaca-py 0.44.0:
- blueprints/us-equities/paper-e2e-20260921/paper-receipt.json records a real paper run. SPY was bought and sold (1 share each) with 2 writes and gross PnL -0.08 USD.
- A separate read-only SDK process then reconciled the account: 5 GET requests, all HTTP 200, 0 positions, 0 open orders, cash delta matching the reported PnL.
- Frozen numeric limits were in force: maximum order notional 1000, maximum gross exposure 1000, maximum 4 write attempts.
- Completed-trial recovery made 0 additional writes.
- This is the only broker boundary with observed execution plus independent reconciliation. runtime-target.json names alpaca-py as the selected Alpaca path.
- lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f — The requirement asks for four things: the NautilusTrader destination, reproducible equity accounting, the retained LEAN oracle, and a broker boundary with numeric risk and independent reconciliation. These three candidates are the only adopted ones with executed evidence for those parts.

c15 NautilusTrader 2.0.0rc5:
- evidence/receipts/native-nautilus-v2-20260920.json records the unchanged upstream synthetic EURUSD quickstart (commit 1b0a49d) run twice in isolation. Both runs ended at 1000431.00000 USD cash, realized PnL 431.00, all positions flat.
- blueprints/us-equities/engine-nautilus/equity-replay/receipt.json is a local integration, not an upstream test. It replayed 15 AAPL bars in two scenarios, twice each, with exit code 0. Baseline: realized PnL -133.40, ending cash 99866.60. Fee/slippage stress: fees 10.00, realized PnL -144.40. It verified 10 cash transitions per scenario, the account CSV repeated byte-identically, a separate reviewer recomputed the cash and PnL, and the 8 local synthetic tests passed.
- catalogs/us-equities/runtime-target.json names it the selected destination (engine.decision "selected_destination").

c16 LEAN:
- blueprints/us-equities/historical-simulation/receipt.json records 6 native simulations at source pin 985ef30. Five invested scenarios ended flat with fill, fee and dividend cash reconciled. The over_limit scenario got one native buying-power rejection and zero fills. The first case ended at 90734.08 USD with 428.64 USD dividends.
- blueprints/us-equities/engine/resolution-receipt.json shows the unchanged bundled backtest still passing: Completed, 3943 data points, 3 orders, matching the original order-list hash.
- This is the numeric risk and cash oracle the requirement says to preserve.

c8 alpaca-py 0.44.0:
- blueprints/us-equities/paper-e2e-20260921/paper-receipt.json records a real paper run. SPY was bought and sold (1 share each) with 2 writes and gross PnL -0.08 USD.
- A separate read-only SDK process then reconciled the account: 5 GET requests, all HTTP 200, 0 positions, 0 open orders, cash delta matching the reported PnL.
- Frozen numeric limits were in force: maximum order notional 1000, maximum gross exposure 1000, maximum 4 write attempts.
- Completed-trial recovery made 0 additional writes.
- This is the only broker boundary with observed execution plus independent reconciliation. runtime-target.json names alpaca-py as the selected Alpaca path.
- alpaca-py @ 0.44.0 — The requirement asks for four things: the NautilusTrader destination, reproducible equity accounting, the retained LEAN oracle, and a broker boundary with numeric risk and independent reconciliation. These three candidates are the only adopted ones with executed evidence for those parts.

c15 NautilusTrader 2.0.0rc5:
- evidence/receipts/native-nautilus-v2-20260920.json records the unchanged upstream synthetic EURUSD quickstart (commit 1b0a49d) run twice in isolation. Both runs ended at 1000431.00000 USD cash, realized PnL 431.00, all positions flat.
- blueprints/us-equities/engine-nautilus/equity-replay/receipt.json is a local integration, not an upstream test. It replayed 15 AAPL bars in two scenarios, twice each, with exit code 0. Baseline: realized PnL -133.40, ending cash 99866.60. Fee/slippage stress: fees 10.00, realized PnL -144.40. It verified 10 cash transitions per scenario, the account CSV repeated byte-identically, a separate reviewer recomputed the cash and PnL, and the 8 local synthetic tests passed.
- catalogs/us-equities/runtime-target.json names it the selected destination (engine.decision "selected_destination").

c16 LEAN:
- blueprints/us-equities/historical-simulation/receipt.json records 6 native simulations at source pin 985ef30. Five invested scenarios ended flat with fill, fee and dividend cash reconciled. The over_limit scenario got one native buying-power rejection and zero fills. The first case ended at 90734.08 USD with 428.64 USD dividends.
- blueprints/us-equities/engine/resolution-receipt.json shows the unchanged bundled backtest still passing: Completed, 3943 data points, 3 orders, matching the original order-list hash.
- This is the numeric risk and cash oracle the requirement says to preserve.

c8 alpaca-py 0.44.0:
- blueprints/us-equities/paper-e2e-20260921/paper-receipt.json records a real paper run. SPY was bought and sold (1 share each) with 2 writes and gross PnL -0.08 USD.
- A separate read-only SDK process then reconciled the account: 5 GET requests, all HTTP 200, 0 positions, 0 open orders, cash delta matching the reported PnL.
- Frozen numeric limits were in force: maximum order notional 1000, maximum gross exposure 1000, maximum 4 write attempts.
- Completed-trial recovery made 0 additional writes.
- This is the only broker boundary with observed execution plus independent reconciliation. runtime-target.json names alpaca-py as the selected Alpaca path.

Alternatives:
- skfolio (conditional) — blueprints/us-equities/research-evaluation/receipt.json covers only the installed WalkForward splitter. It was run on a raw-price label study: 20 development folds, one reserved 2021Q1 evaluation, 21 frozen selections and 6605 candidate records. The receipt states this is 'not new LEAN execution or portfolio P&L'. The catalog card (engines-strategies.json, skfolio entry) states 'no portfolio optimization'. It notes that purge and embargo default to zero and that estimates are not pre-trade enforcement or broker reconciliation. It supports causal split policy for strategy qualification, but it has no executed allocation or risk-model evidence. The pin (1.2.9) is behind upstream v1.3.0 per the packet.
- LEAN Alpaca brokerage (conditional) — blueprints/us-equities/engine/resolution-receipt.json shows the adapter compiling without credentials (runtime subscription validation not invoked). Its catalog card says account connection is unexecuted, no Alpaca paper orders were accepted, and QuantConnect product347 entitlement is still required. It is also not the selected Nautilus destination (runtime-target.json). The Alpaca boundary with observed paper execution is alpaca-py (c8).
- Dockerized IB Gateway (conditional) — catalogs/landscape/hosting-practice.json records decision conditional, evidence_level source_review and native_acceptance not_established. Image digest, sign-in, restart, API connectivity and broker reconciliation are all unqualified. docs/hosting-container-practice.md keeps the native external TWS/IB Gateway as a valid path. The IBKR boundary itself has local_broker_acceptance not_established (runtime-target.json).
- ib_async (unqualified) — Its engines-strategies.json card is decision alternative, evidence_level source_review, and its workflow is 'Prospective and unexecuted'. It is a community SDK, and its card says local contract construction is not IBKR paper acceptance. runtime-target.json selects Nautilus's native IBKR socket adapter for IBKR, with local_broker_acceptance not_established.
- PyPortfolioOpt (unqualified) — Its engines-strategies.json card is decision alternative, evidence_level source_review, and its workflow is 'Prospective and unexecuted'. The card's own rationale prefers skfolio when model selection is central. It has no executed allocation, risk-model or reconciliation evidence.
- Zipline Reloaded (overlap) — Its engines-strategies.json card is decision alternative, source_review, workflow unexecuted. The card's rationale says to 'avoid adopting a second event engine without a specific need'. It has no Alpaca paper route and no retained accounting or risk receipt.
- Qlib (conditional) — The engines-strategies.json card is decision conditional and the data-research.json data-qlib card is decision watch. Both are source_review with unexecuted workflows. The reviewed Alpha158/LightGBM YAML defaults to China/CSI300. The official dataset is temporarily disabled per the pinned README. Adoption waits on a point-in-time US dataset. It has no execution or risk role.
- vectorbt (unqualified) — Its engines-strategies.json card is decision alternative, source_review, workflow unexecuted. The license is Apache-2.0 with a Commons Clause condition. Its card says research outputs must be re-verified in the execution engine. It has no broker route and no retained accounting receipt.
- Lumibot (unqualified) — Its engines-strategies.json card is decision alternative, source_review, workflow unexecuted. The license conflict is unresolved: the LICENSE file is GPL-3.0 while setup.py declares MIT. It would be a second active engine alongside the selected Nautilus destination. No paper or accounting receipt is retained.

Overturn when: Reopen the winner set in any of these cases:
- The preregistered SPY/LEAN one_zero replay fails the $0.01 absolute-tolerance cash/equity check, or cannot map distributions_and_cash or market_on_open. The contract is in blueprints/us-equities/engine-nautilus/acceptance-plan.md section 3, against the LEAN oracle blueprints/us-equities/historical-simulation/receipt.json. It is currently recorded as a completed BLOCKED comparison, not accepted parity.
- The replay `python3 blueprints/us-equities/engine-nautilus/equity-replay/launch.py --python <NAUTILUS_ENV>/bin/python --run <RETAINED_ALPACA_RUN> --out <PRIVATE_EVIDENCE>/<RUN_ID>` no longer reproduces the recorded economic hashes.
- `python3 -m unittest tests.test_nautilus_equity_replay -v` or the tests/test_alpaca_paper.py suite regresses.
- A native in-flight fault case (partial, cancel race, crash boundary, or stale/risk breach, per acceptance-plan.md section 4) fails on the Alpaca or IBKR boundary.
- A portfolio/risk library (skfolio c4, PyPortfolioOpt c13, or the non-candidate cvxportfolio) produces an executed allocation/risk receipt on the same frozen inputs. That would add or replace a portfolio-construction winner.

Open gaps:
- SPY/LEAN parity is not accepted. runtime-target.json next_acceptance records 'reported_execution_blocked_review_incomplete', with four failed checks attributed to dividend cash posting and market-on-open mappings.
- The AAPL Nautilus replay uses 15 bars, excludes known dividend/split dates, and uses retrospective close fills with unlimited synthetic depth. It does not establish finite liquidity, partial fills, impact or halts.
- No native in-flight broker fault (partial fill, cancel, reject, disconnect, crash) was induced. The 27 Alpaca lifecycle tests are synthetic.
- The IBKR boundary is not established: local_broker_acceptance not_established, and Dockerized IB Gateway native_acceptance not_established.
- No executed portfolio-optimization or risk-model receipt exists for any candidate. The skfolio native run covers WalkForward splitting on raw-price labels only.
- The packet lists three SOTA components outside the candidate set: quantstats (confirmed_default), cvxportfolio (not_individually_reviewed) and empyrical-reloaded (unmaintained_signal). None of their receipts were in scope for this packet, so their role in this layer is unjudged.
- No point-in-time universe, strategy merit, financing-inclusive performance or profitability follows from any receipt.
- NautilusTrader 2.0.0rc5 is a prerelease; GitHub's latest non-prerelease is v1.231.0. The packet also records an unasserted-denial-variant test defect in Nautilus risk tests. I did not verify it from source here.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-portfolio-risk-20260922; codex: -)

#### Research, factors and ML (research-factors-ml)

- skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee — This verdict comes from my own review of the source files. The packet withholds the provider's prior decision, so none of its judgment is retained here.

How I chose the winners: the packet requirement at line 375 is the group-wide engines-strategies requirement. It says: "Use the selected NautilusTrader destination with broker-specific execution boundaries, deterministic numeric risk and reproducible equity accounting; preserve the prior LEAN oracle and qualify any strategy with causal data, costs and independent reconciliation." So the winner set has three parts:
- the destination the requirement names (c12);
- the oracle the requirement names (c1);
- the one research, factor or ML candidate with native causal-data evidence (c13).

Broker SDKs, adapters and gateways (c2, c4, c6, c16) cover the requirement's broker-execution clause, but that clause belongs to the paper and execution layers. None of them has any research, factor or ML evidence, so none is a default here.

c13 skfolio has native execution. blueprints/us-equities/research-evaluation/receipt.json lines 2-12 is kind native_cli_e2e, status accepted_for_causal_raw_price_label_control_only:
- Upstream skfolio 1.2.9 WalkForward (252/63/6, reduce_test=True) produced 20 chronological development folds and one reserved 2021Q1 evaluation.
- The run produced 21 frozen selections and 6605 candidate records.
- The plan was frozen before prices were scored (lines 18-23).
- An independent review (lines 1780-1792) verified 21 selection hashes and 21 training-exit boundaries, with 0 hash mismatches and 12 focused tests passed.

This meets the requirement's causal-data clause for a raw-price control study only. It only partly meets the costs clause: costs are a fixed 20bp round-trip proxy with no fill or commission model (line 1773). It does not meet the independent reconciliation clause economically. Line 1773 says "No cash/position/fee/dividend reconciliation", and the independent review was read-only with "no scoring rerun" (line 1782). Its catalog card is decision conditional, evidence_level native_proven (engines-strategies.json lines 733 and 740).

c12 NautilusTrader is the destination the requirement names:
- catalogs/us-equities/runtime-target.json lines 22-42 record decision selected_destination, prerelease true.
- evidence/receipts/native-nautilus-v2-20260920.json lines 1-20 records an unchanged upstream synthetic EURUSD quickstart that passed two isolated offline runs with exact cash reconciliation.
- blueprints/us-equities/engine-nautilus/equity-replay/receipt.json lines 1-80 is a local integration: a 15-bar AAPL replay run twice (exit_code 0). Realized PnL was reconciled in both scenarios: baseline -133.40 USD, and fee_slippage_stress -144.40 USD with fees of 10.00 USD.
- Dividend and market-on-open parity with LEAN is not accepted. The SPY one_zero comparison returned BLOCKED with 4 failed checks (evidence/artifacts/comparison-progress-20260922/summary.json lines 171-189; runtime-target.json lines 112-116).

c1 LEAN is the preserved oracle the requirement names. blueprints/us-equities/historical-simulation/receipt.json lines 1-10 records six frozen native LEAN simulations with fill, fee and dividend cash reconciliation, and one native buying-power rejection. The skfolio study also used nine pinned LEAN daily, map and factor files as byte-verified inputs (research-evaluation/receipt.json line 14; engines-strategies.json line 752).
- nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e) — This verdict comes from my own review of the source files. The packet withholds the provider's prior decision, so none of its judgment is retained here.

How I chose the winners: the packet requirement at line 375 is the group-wide engines-strategies requirement. It says: "Use the selected NautilusTrader destination with broker-specific execution boundaries, deterministic numeric risk and reproducible equity accounting; preserve the prior LEAN oracle and qualify any strategy with causal data, costs and independent reconciliation." So the winner set has three parts:
- the destination the requirement names (c12);
- the oracle the requirement names (c1);
- the one research, factor or ML candidate with native causal-data evidence (c13).

Broker SDKs, adapters and gateways (c2, c4, c6, c16) cover the requirement's broker-execution clause, but that clause belongs to the paper and execution layers. None of them has any research, factor or ML evidence, so none is a default here.

c13 skfolio has native execution. blueprints/us-equities/research-evaluation/receipt.json lines 2-12 is kind native_cli_e2e, status accepted_for_causal_raw_price_label_control_only:
- Upstream skfolio 1.2.9 WalkForward (252/63/6, reduce_test=True) produced 20 chronological development folds and one reserved 2021Q1 evaluation.
- The run produced 21 frozen selections and 6605 candidate records.
- The plan was frozen before prices were scored (lines 18-23).
- An independent review (lines 1780-1792) verified 21 selection hashes and 21 training-exit boundaries, with 0 hash mismatches and 12 focused tests passed.

This meets the requirement's causal-data clause for a raw-price control study only. It only partly meets the costs clause: costs are a fixed 20bp round-trip proxy with no fill or commission model (line 1773). It does not meet the independent reconciliation clause economically. Line 1773 says "No cash/position/fee/dividend reconciliation", and the independent review was read-only with "no scoring rerun" (line 1782). Its catalog card is decision conditional, evidence_level native_proven (engines-strategies.json lines 733 and 740).

c12 NautilusTrader is the destination the requirement names:
- catalogs/us-equities/runtime-target.json lines 22-42 record decision selected_destination, prerelease true.
- evidence/receipts/native-nautilus-v2-20260920.json lines 1-20 records an unchanged upstream synthetic EURUSD quickstart that passed two isolated offline runs with exact cash reconciliation.
- blueprints/us-equities/engine-nautilus/equity-replay/receipt.json lines 1-80 is a local integration: a 15-bar AAPL replay run twice (exit_code 0). Realized PnL was reconciled in both scenarios: baseline -133.40 USD, and fee_slippage_stress -144.40 USD with fees of 10.00 USD.
- Dividend and market-on-open parity with LEAN is not accepted. The SPY one_zero comparison returned BLOCKED with 4 failed checks (evidence/artifacts/comparison-progress-20260922/summary.json lines 171-189; runtime-target.json lines 112-116).

c1 LEAN is the preserved oracle the requirement names. blueprints/us-equities/historical-simulation/receipt.json lines 1-10 records six frozen native LEAN simulations with fill, fee and dividend cash reconciliation, and one native buying-power rejection. The skfolio study also used nine pinned LEAN daily, map and factor files as byte-verified inputs (research-evaluation/receipt.json line 14; engines-strategies.json line 752).
- lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f — This verdict comes from my own review of the source files. The packet withholds the provider's prior decision, so none of its judgment is retained here.

How I chose the winners: the packet requirement at line 375 is the group-wide engines-strategies requirement. It says: "Use the selected NautilusTrader destination with broker-specific execution boundaries, deterministic numeric risk and reproducible equity accounting; preserve the prior LEAN oracle and qualify any strategy with causal data, costs and independent reconciliation." So the winner set has three parts:
- the destination the requirement names (c12);
- the oracle the requirement names (c1);
- the one research, factor or ML candidate with native causal-data evidence (c13).

Broker SDKs, adapters and gateways (c2, c4, c6, c16) cover the requirement's broker-execution clause, but that clause belongs to the paper and execution layers. None of them has any research, factor or ML evidence, so none is a default here.

c13 skfolio has native execution. blueprints/us-equities/research-evaluation/receipt.json lines 2-12 is kind native_cli_e2e, status accepted_for_causal_raw_price_label_control_only:
- Upstream skfolio 1.2.9 WalkForward (252/63/6, reduce_test=True) produced 20 chronological development folds and one reserved 2021Q1 evaluation.
- The run produced 21 frozen selections and 6605 candidate records.
- The plan was frozen before prices were scored (lines 18-23).
- An independent review (lines 1780-1792) verified 21 selection hashes and 21 training-exit boundaries, with 0 hash mismatches and 12 focused tests passed.

This meets the requirement's causal-data clause for a raw-price control study only. It only partly meets the costs clause: costs are a fixed 20bp round-trip proxy with no fill or commission model (line 1773). It does not meet the independent reconciliation clause economically. Line 1773 says "No cash/position/fee/dividend reconciliation", and the independent review was read-only with "no scoring rerun" (line 1782). Its catalog card is decision conditional, evidence_level native_proven (engines-strategies.json lines 733 and 740).

c12 NautilusTrader is the destination the requirement names:
- catalogs/us-equities/runtime-target.json lines 22-42 record decision selected_destination, prerelease true.
- evidence/receipts/native-nautilus-v2-20260920.json lines 1-20 records an unchanged upstream synthetic EURUSD quickstart that passed two isolated offline runs with exact cash reconciliation.
- blueprints/us-equities/engine-nautilus/equity-replay/receipt.json lines 1-80 is a local integration: a 15-bar AAPL replay run twice (exit_code 0). Realized PnL was reconciled in both scenarios: baseline -133.40 USD, and fee_slippage_stress -144.40 USD with fees of 10.00 USD.
- Dividend and market-on-open parity with LEAN is not accepted. The SPY one_zero comparison returned BLOCKED with 4 failed checks (evidence/artifacts/comparison-progress-20260922/summary.json lines 171-189; runtime-target.json lines 112-116).

c1 LEAN is the preserved oracle the requirement names. blueprints/us-equities/historical-simulation/receipt.json lines 1-10 records six frozen native LEAN simulations with fill, fee and dividend cash reconciliation, and one native buying-power rejection. The skfolio study also used nine pinned LEAN daily, map and factor files as byte-verified inputs (research-evaluation/receipt.json line 14; engines-strategies.json line 752).

Alternatives:
- Qlib (conditional) — Qlib has only a source review. Its workflow was never run, so it has neither failed nor passed.

- engines-strategies.json lines 461-507 mark it decision conditional: 'Adopt only after a point-in-time US dataset and baseline are established'. Its Alpha158/LightGBM YAML defaults to China/CSI300, and the qrun workflow is 'Prospective and unexecuted' (line 482).
- data-research.json lines 1342-1380 mark it decision watch and note that the pinned README says the official dataset is temporarily disabled.
- The packet says adopted=true with review_status not_individually_reviewed, which conflicts with both catalog cards.
- No US configuration and no causal-split comparison against skfolio exist.
- vectorbt (conditional) — vectorbt has only a source review, and its workflow was never run (engines-strategies.json lines 249-294, line 269).

- Its licence is Apache-2.0 with the Commons Clause, not plain Apache (line 279).
- The card itself warns that fast parameter sweeps increase exposure to multiple testing.
- It has no chronological-split evidence to compare with the native skfolio receipt.
- Zipline Reloaded (overlap) — Zipline Reloaded has a factor-research layer but only a source review. Its workflow was never run and needs an ingested, licensed data bundle (engines-strategies.json lines 378-420).

It would be a second event engine alongside the selected Nautilus destination and the LEAN oracle. The card itself says to 'avoid adopting a second event engine without a specific need' (line 387).
- PyPortfolioOpt (overlap) — PyPortfolioOpt has only a source review, and its workflow was never run (engines-strategies.json lines 642-682).

- The card itself says 'skfolio is preferred when model-selection orchestration is central' (line 650).
- It provides no chronological validation, which the requirement's causal-data clause needs.
- Lumibot (unqualified) — Lumibot is a combined backtest, execution and broker engine. It adds no research, factor or ML capability beyond the named destination and oracle.

- It has only a source review, and its workflow was never run.
- Its licence conflict is unresolved: the LICENSE file says GPL-3.0 while setup.py says MIT (engines-strategies.json lines 203-248, line 234).
- LEAN Alpaca brokerage (out_of_scope) — This is a broker adapter. It serves the broker-execution clause in the paper and execution layers and has no research or factor evidence.

- The card records evidence_level native_proven (engines-strategies.json line 74), but that covers only the native adapter build: 'Native adapter builds were later accepted; account connection remains unexecuted' (line 92).
- The resolution receipt (lines 1-7) says runtime subscription validation was not invoked.
- alpaca-py (out_of_scope) — This is the broker SDK and reconciliation observer. It serves the paper-execution layer, not the research layer.

Its native paper evidence is real: paper-receipt.json shows 2 writes, -0.08 USD gross, a fresh reconciliation that passed, and 0 additional writes during recovery.

Correction: the engines-strategies.json card at line 121 still says evidence_level source_review, which predates this receipt.
- ib_async (out_of_scope) — This is a community IBKR client SDK, not a research component.

- It has only a source review, and its workflow was never run (engines-strategies.json lines 1362-1402).
- runtime-target.json lines 45-67 select the Nautilus native IBKR adapter instead.
- Dockerized IB Gateway (out_of_scope) — This is a hosting and gateway component, not a research component.

- catalogs/landscape/hosting-practice.json lines 43-53 record decision conditional, evidence_level source_review and native_acceptance not_established.
- Its image digest, sign-in, restart and reconciliation are all unqualified.

Overturn when: Research winner (c13): overturn it if Qlib (c11) or vectorbt (c8) is run under the same frozen contract as blueprints/us-equities/research-evaluation/plan.json and then:
- passes the same boundary checks as tests/test_research_evaluation.py: every training-label exit falls before its evaluation cutoff, and selections are persisted before labels;
- runs on a new, untouched interval; and
- shows better cost-adjusted out-of-sample results that a separate reviewer reconciles.

Engine winner (c12): overturn it if the SPY one_zero case in blueprints/us-equities/historical-simulation/plan.json (line 18; dividend policy at line 15), rerun on NautilusTrader against the LEAN oracle results in blueprints/us-equities/historical-simulation/receipt.json, still cannot preserve dividend cash and market-on-open semantics within a tolerance registered in advance after the recorded hardening. That failure would promote the LEAN oracle (c1) to the default.

Current state of that comparison:
- The last executed SPY one_zero comparison returned BLOCKED with returned_failed_checks 4 and unsupported mappings distributions_and_cash and market_on_open_proxy (evidence/artifacts/comparison-progress-20260922/summary.json lines 171-189).
- That harness (spy-parity compare.py) is not retained in this repository.
- The AAPL equity-replay deliberately avoids corporate-action dates (runtime-target.json line 115), so it cannot decide this.

Open gaps:
- No factor or ML model training was ever run. The skfolio receipt is a raw-price momentum/equal-weight label study on SPY, QQQ and IWM ETFs. Its limitations (lines 1771-1774) exclude a point-in-time universe, total returns, portfolio P&L, and any claim of statistical alpha or superiority.
- The requirement's 'independent reconciliation' clause is not met economically for c13. The receipt (line 1773) says 'No cash/position/fee/dividend reconciliation or new LEAN engine execution', and the independent review was read-only with no scoring rerun (line 1782).
- The skfolio catalog card is still decision conditional (engines-strategies.json line 733), even though its evidence_level is native_proven (line 740). Promoting it to a firmer decision remains unresolved.
- The reserved 2021Q1 segment has now been inspected and cannot be called untouched (research-evaluation/receipt.json line 1775; engines-strategies.json line 753).
- Costs were modelled only as a fixed 20bp round-trip proxy. There is no fill, commission, liquidity or capacity model (line 1773).
- WalkForward/CPCV purge and embargo default to zero (engines-strategies.json line 756). Development labels can cross fold boundaries (receipt line 1776).
- skfolio is pinned at 1.2.9 while upstream is at v1.3.0 (packet pin_behind_upstream true). The card's sources cite v1.2.8 files (lines 742, 762-768) alongside the 1.2.9 pin (line 735).
- NautilusTrader 2.0.0rc5 is a prerelease. SPY/LEAN one_zero parity is BLOCKED with 4 failed checks (distributions_and_cash, market_on_open_proxy) and is only 'recorded progress, not accepted parity' (runtime-target.json line 115; summary.json lines 171-189).
- The spy-parity compare.py harness and verdict.json are not retained in this repository.
- The AAPL replay is 15 bars with synthetic fills and avoids corporate-action dates.
- No executed evidence exists in this layer for Qlib, vectorbt, Zipline Reloaded or PyPortfolioOpt.
- No executed evidence exists for sota components outside the candidate list (scikit-learn, statsmodels, sktime, statsforecast, chronos, timesfm, alphalens-reloaded). scikit-learn 1.9.1 appears only as a runtime dependency (receipt line 28).
- The packet marks Qlib adopted=true, but the catalog cards say conditional (engines-strategies) and watch (data-research). That disposition is unresolved.
- macOS and fresh-host execution are not established (receipt line 1778).
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-research-factors-ml-20260922; codex: -)

#### Security and supply chain (security-supply-chain)

- codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0 — None of the packet's candidates is a security or supply-chain tool, so the adopted candidates were judged against the packet's requirement text as written (packet line 531): "Run bounded research with native identity and complete returned results; supervise owned processes; retain scoped telemetry, failed attempts and recoverable state without granting research workers broker execution authority." Each winner has a native-execution receipt and covers a different clause. No measured comparison exists between the candidates; the set was chosen by clause coverage from source review of retained receipts.

(1) Codex (c17), native execution. blueprints/us-equities/workers/receipt.json records run.status "completed" with the full usage totals returned (lines 24-48), after a native interactive login with "no credential store copied or inspected" (line 13). The failed ctx_execute_file attempt is kept (lines 75-79, 111). Line 110 records the boundary in full: "Read-only filesystem mode does not restrict external MCP mutations; the recorded environment supplied no broker keys or broker tools." Broker authority is therefore absent because of the environment, not blocked by enforcement.

(2) Dagu (c7), native execution. blueprints/us-equities/hosting/receipt.json has scope "no broker or model calls" (line 4). The failure fixture ended "failed" with its dependent step "aborted" (lines 25-30). The cancellation fixture ended "aborted" (lines 31-35). service_restart_exit is 0 and prior_history_rows_preserved is true (lines 37-38), and failed or aborted runs are kept in history after restart (lines 46-82). The service runs under systemd with restart_policy on-failure (lines 93-94) and has broker_calls 0 (line 97).

(3) OpenTelemetry Collector contrib (c14) is the only adopted candidate that covers the "retain scoped telemetry" clause with a boundary control. evidence/receipts/foundation-native-20260920.json lines 35-36 record native execution: native Codex usage matched Loki and Prometheus, and a fresh Claude run matched native/Loki/Prometheus consumption 35537 in all four categories. The initial Claude run is kept as a partial miss. The catalog entry (catalogs/us-equities/agents-operations.json lines 861, 865 and 878) says it supplies the privacy transform, carries usage metadata "without prompt bodies" and requires a reviewed privacy allowlist. The catalog's own evidence ref, observability/receipt.json, adds a privacy canary at lines 313-330, which that receipt labels "Independent synthetic review" (a synthetic canary through native POST and export), with forbidden_marker_absent true. It also keeps an initial privacy-review failure among its retained failed attempts (line 371) and reports status passed_with_explicit_limits (line 386).

In the earlier proposal Restic (c9) was the third winner. It was replaced because Dagu already keeps completed run history across restart (hosting line 38), while no other adopted candidate retains scoped telemetry. This is a coverage judgment, not a measured ranking. None of the three winners is a supply-chain control. The retained supply-chain receipts belong to syft/grype, which are not packet candidates (see challenger_preferred).
- dagu @ v2.16.6 — None of the packet's candidates is a security or supply-chain tool, so the adopted candidates were judged against the packet's requirement text as written (packet line 531): "Run bounded research with native identity and complete returned results; supervise owned processes; retain scoped telemetry, failed attempts and recoverable state without granting research workers broker execution authority." Each winner has a native-execution receipt and covers a different clause. No measured comparison exists between the candidates; the set was chosen by clause coverage from source review of retained receipts.

(1) Codex (c17), native execution. blueprints/us-equities/workers/receipt.json records run.status "completed" with the full usage totals returned (lines 24-48), after a native interactive login with "no credential store copied or inspected" (line 13). The failed ctx_execute_file attempt is kept (lines 75-79, 111). Line 110 records the boundary in full: "Read-only filesystem mode does not restrict external MCP mutations; the recorded environment supplied no broker keys or broker tools." Broker authority is therefore absent because of the environment, not blocked by enforcement.

(2) Dagu (c7), native execution. blueprints/us-equities/hosting/receipt.json has scope "no broker or model calls" (line 4). The failure fixture ended "failed" with its dependent step "aborted" (lines 25-30). The cancellation fixture ended "aborted" (lines 31-35). service_restart_exit is 0 and prior_history_rows_preserved is true (lines 37-38), and failed or aborted runs are kept in history after restart (lines 46-82). The service runs under systemd with restart_policy on-failure (lines 93-94) and has broker_calls 0 (line 97).

(3) OpenTelemetry Collector contrib (c14) is the only adopted candidate that covers the "retain scoped telemetry" clause with a boundary control. evidence/receipts/foundation-native-20260920.json lines 35-36 record native execution: native Codex usage matched Loki and Prometheus, and a fresh Claude run matched native/Loki/Prometheus consumption 35537 in all four categories. The initial Claude run is kept as a partial miss. The catalog entry (catalogs/us-equities/agents-operations.json lines 861, 865 and 878) says it supplies the privacy transform, carries usage metadata "without prompt bodies" and requires a reviewed privacy allowlist. The catalog's own evidence ref, observability/receipt.json, adds a privacy canary at lines 313-330, which that receipt labels "Independent synthetic review" (a synthetic canary through native POST and export), with forbidden_marker_absent true. It also keeps an initial privacy-review failure among its retained failed attempts (line 371) and reports status passed_with_explicit_limits (line 386).

In the earlier proposal Restic (c9) was the third winner. It was replaced because Dagu already keeps completed run history across restart (hosting line 38), while no other adopted candidate retains scoped telemetry. This is a coverage judgment, not a measured ranking. None of the three winners is a supply-chain control. The retained supply-chain receipts belong to syft/grype, which are not packet candidates (see challenger_preferred).
- opentelemetry-collector-contrib @ v0.161.0 — None of the packet's candidates is a security or supply-chain tool, so the adopted candidates were judged against the packet's requirement text as written (packet line 531): "Run bounded research with native identity and complete returned results; supervise owned processes; retain scoped telemetry, failed attempts and recoverable state without granting research workers broker execution authority." Each winner has a native-execution receipt and covers a different clause. No measured comparison exists between the candidates; the set was chosen by clause coverage from source review of retained receipts.

(1) Codex (c17), native execution. blueprints/us-equities/workers/receipt.json records run.status "completed" with the full usage totals returned (lines 24-48), after a native interactive login with "no credential store copied or inspected" (line 13). The failed ctx_execute_file attempt is kept (lines 75-79, 111). Line 110 records the boundary in full: "Read-only filesystem mode does not restrict external MCP mutations; the recorded environment supplied no broker keys or broker tools." Broker authority is therefore absent because of the environment, not blocked by enforcement.

(2) Dagu (c7), native execution. blueprints/us-equities/hosting/receipt.json has scope "no broker or model calls" (line 4). The failure fixture ended "failed" with its dependent step "aborted" (lines 25-30). The cancellation fixture ended "aborted" (lines 31-35). service_restart_exit is 0 and prior_history_rows_preserved is true (lines 37-38), and failed or aborted runs are kept in history after restart (lines 46-82). The service runs under systemd with restart_policy on-failure (lines 93-94) and has broker_calls 0 (line 97).

(3) OpenTelemetry Collector contrib (c14) is the only adopted candidate that covers the "retain scoped telemetry" clause with a boundary control. evidence/receipts/foundation-native-20260920.json lines 35-36 record native execution: native Codex usage matched Loki and Prometheus, and a fresh Claude run matched native/Loki/Prometheus consumption 35537 in all four categories. The initial Claude run is kept as a partial miss. The catalog entry (catalogs/us-equities/agents-operations.json lines 861, 865 and 878) says it supplies the privacy transform, carries usage metadata "without prompt bodies" and requires a reviewed privacy allowlist. The catalog's own evidence ref, observability/receipt.json, adds a privacy canary at lines 313-330, which that receipt labels "Independent synthetic review" (a synthetic canary through native POST and export), with forbidden_marker_absent true. It also keeps an initial privacy-review failure among its retained failed attempts (line 371) and reports status passed_with_explicit_limits (line 386).

In the earlier proposal Restic (c9) was the third winner. It was replaced because Dagu already keeps completed run history across restart (hosting line 38), while no other adopted candidate retains scoped telemetry. This is a coverage judgment, not a measured ranking. None of the three winners is a supply-chain control. The retained supply-chain receipts belong to syft/grype, which are not packet candidates (see challenger_preferred).

Alternatives:
- Restic (conditional) — Native same-host restores passed. blueprints/us-equities/state-recovery/memory/receipt.json has status passed_same_host_restore (line 8) with 324 byte-equal restored files (line 33). blueprints/us-equities/state-recovery/qdrant/receipt.json has status passed_same_host_native_restore (line 8) and keeps an initial restore failure with exit_code 101 (line 41). Neither receipt involves a broker action (memory line 134, qdrant line 58). It was left out only because of the three-winner cap: Dagu already preserves completed run history across restart, and nothing else covers telemetry. That is coverage-based, not a measured ranking. Correction to the earlier proposal: the isolated restore namespace (memory line 37) came from bubblewrap, which is listed separately at line 14, not from Restic. The restores are same-host only, and no broker/order journal is backed up (agents-operations.json line 1767). It becomes the choice when state recovery beyond completed-history restart is required.
- Microsoft Agent Framework (unqualified) — Source review only. docs/candidate-quality-review-20260921.md line 47 says it fills a discovery gap but needs a required application workflow qualified before another runtime is added. There is no local run, broker-boundary or recovery evidence.
- DeerFlow (conditional) — One native ACP research task completed (blueprints/us-equities/deerflow/research-receipt.json line 58). Its recorded sandbox had networkAccess false (lines 66-72) and 0 MCP tool calls (line 94), which does not show weaker isolation than the Codex worker; that earlier comparison is withdrawn. The actual gaps are these. DeerFlow returns text and discards ACP completion and usage, which were recovered from private adapter logs (line 14), so the 'complete returned results' clause is not met natively. Strict read-only enforcement is not established, because mode read-only maps to workspaceWrite (line 13). It was an embedded tool invocation, not the full planner or scheduler (line 12). Durable recovery was not exercised (line 17).
- OpenAI Agents SDK (overlap) — Source review only. The catalog lists it as an alternative (catalogs/us-equities/agents-operations.md line 125). It is an API-backed loop with its own authentication and tracing, not the native subscription identity. Upstream tracing is on by default and needs an opt-out (agents-operations.md line 77). No local run exists.
- Prefect (overlap) — Source review only. The catalog treats it as an alternative to Dagu when Python flows dominate (agents-operations.md lines 38 and 95). There is no supervision, cancellation or restart receipt.
- Temporal (conditional) — Source review only. It applies when jobs span days or must survive host failure (agents-operations.md line 40). Activities retry by default, possibly without limit, which is unsafe for uncertain broker writes (agents-operations.json line 348). No local acceptance exists.
- Loki (overlap) — Native execution was observed: Loki matched native usage for Codex and for both Claude runs (evidence/receipts/foundation-native-20260920.json lines 35-36). It is a storage and query backend that receives data through the c14 collector, which owns the privacy transform and allowlist (agents-operations.json lines 861 and 878). By itself it adds no scoping or redaction control. It observes research status only, with no broker connection (agents-operations.json line 990).
- Deep Agents (unqualified) — Source review only. docs/candidate-quality-review-20260921.md line 44 calls it a serious challenger that still needs the same source-research task, permission boundaries, recovery and complete cost comparison. None of these has run.
- OpenHands SDK (unqualified) — Source review only. docs/candidate-quality-review-20260921.md line 45 says installation and native-account and recovery acceptance remain open.
- OpenHands Agent Canvas (unqualified) — Source review only. docs/candidate-quality-review-20260921.md line 46 says hosting existing workers 'is not yet qualified here'.
- Grafana (overlap) — Visualization layer. docs/dashboard-rendered-acceptance.md line 29 shows exact panel queries matching native results, on 'our integration panels'. Lines 8-10 describe these as 'selected native operations and local integration checks'. The packet labels its evidence native_execution; this lane classes it as local_integration because the panels are project integrations. Lines 14-15 on keeping private session content off GitHub are an evidence-publishing rule, not a runtime boundary control. It reads telemetry that c14 already scopes and adds no worker, supervision or broker-boundary control.
- Dagster (overlap) — Source review only. It is the alternative for asset/partition lineage (agents-operations.md lines 39 and 96). There is no supervision, cancellation or restart receipt.
- Claude Code (overlap) — A native paired run completed with live_or_paper_broker_connected false (adoption/paired/receipt.json lines 17 and 22). The research-efficiency receipt records 'bounded_comparison_completed_with_two_word_protocol_failures' (blueprints/us-equities/research-efficiency/native-receipt.json line 1152). It overlaps the Codex worker, which the catalog keeps as the default research worker (catalogs/us-equities/agents-operations.json lines 15-16).
- Prometheus (overlap) — Native execution was observed, but on the initial Claude run Prometheus missed the first two requests (evidence/receipts/foundation-native-20260920.json line 35). A full match came only on a fresh run after waiting for telemetry initialization (line 36). It is a metrics backend fed by the c14 collector and adds no scoping or redaction control of its own.
- LangGraph (conditional) — Source review only. Its pin is behind upstream (packet: 1.2.11 vs 1.2.12). InMemorySaver loses state on restart, and checkpoints are not a durable broker ledger (agents-operations.json line 262).

Overturn when: This verdict holds only for the packet's current candidate set, and the choice between c14 and c9 for the third slot rests on clause coverage, not on measurement.

It changes if the layer's candidates include the security components already in its gate records: syft/grype (blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json), the syft SDK inventory (blueprints/us-equities/supply-chain/receipt.json) and gitleaks.

It also changes if a re-executed worker or hosting receipt shows broker credentials or order tools reachable from the research environment, contradicting blueprints/us-equities/workers/receipt.json line 110 or broker_calls 0 in blueprints/us-equities/hosting/receipt.json line 97.

Finally, it changes if a layer requirement makes durable state recovery a hard requirement that Dagu's completed-history restart does not meet. In that case c9 Restic, with its same-host restore receipts (blueprints/us-equities/state-recovery/memory/receipt.json, blueprints/us-equities/state-recovery/qdrant/receipt.json), should replace c14.

Open gaps:
- lane claude prefers non-adopted Syft (with Grype on its SBOMs) (https://github.com/anchore/syft): requires Rebuild the packet so the supply-chain components (syft, grype, gitleaks, cosign, openbao) are candidates. Then judge them against blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json and blueprints/us-equities/supply-chain/receipt.json, together with the worker and hosting receipts (blueprints/us-equities/workers/receipt.json, blueprints/us-equities/hosting/receipt.json), under a requirement text specific to this layer.
- Candidate-set mismatch. The packet's layer_id is security-supply-chain, but its requirement text (line 531), existing_overturn_when (line 522) and candidates are group-level agents-operations items. The actual security components are listed only under sota_components_not_in_candidates: syft, gitleaks https://github.com/gitleaks/gitleaks, grype https://github.com/anchore/grype, cosign https://github.com/sigstore/cosign and openbao https://github.com/openbao/openbao.
- No measured comparison ranks c14 against c9 for the third winner slot. With three winners, the 'recoverable state' clause rests on Dagu's completed-history restart (hosting receipt line 38 and limitations line 100: no in-flight resumption). Restic's same-host restore receipts stay outside the winner set.
- The c14 privacy canary is labelled 'Independent synthetic review; not an inference task' (observability/receipt.json line 314). Traces are disabled, no trace database was deployed, and broker monitoring was not accepted (agents-operations.json lines 839 and 882). A privileged audit sink for order/account identifiers is still only a requirement (line 866).
- Gitleaks (https://github.com/gitleaks/gitleaks) is catalog default and marked native_proven through evidence/receipts/runtime-tools.json, which was not opened here. foundation-closure-20260921.md lines 201-203 record 197 unchanged baseline matches and say no clean whole-repository security claim follows. observability/receipt.json line 392 records gitleaks_current_tree_findings 0 for that local validation scope only.
- Grype (https://github.com/anchore/grype) covers installed Python package metadata only, not bundled native extensions, host OS packages or transitive shared libraries (scan receipt line 16). Signature verification was false for the grype binary (line 52).
- Cosign (https://github.com/sigstore/cosign) and OpenBao (https://github.com/openbao/openbao) are source review only. No signature verification or service secret lifecycle was executed (agents-operations.json lines 1538-1553 and 1577-1595).
- catalogs/us-equities/gates-20260922.json lines 229-241 establish broker credential handling only as local_integration, checked by file presence alone. market_research.py keeps an unguarded credentials() function.
- The worker's broker boundary depends on the environment, not on enforcement. Read-only mode does not restrict external MCP mutations (workers/receipt.json line 110). There is no per-request provider attestation (line 109), no VM or network isolation boundary, and no off-host recovery. Dagu host shell execution 'is not a sandbox' (hosting receipt line 102).
- The Dagu pin v2.16.6 is behind upstream v2.17.0 (packet). Recovery in the hosting receipt is completed-history restart, not in-flight recovery.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-security-supply-chain-20260922; codex: -)

#### Storage and compute (storage-compute)

- data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa — This verdict comes from my own review of the retained receipts, not from the provider judgments the packet withheld. The requirement has two parts. The first is acquiring licensed, source-identifiable observations that keep feed, timestamps, identity and corporate actions. The second is producing exact, reproducible snapshots that reject data whose availability or eligibility is unknown. Each winner is the only adopted candidate with native receipts for one of those parts.

c1 DuckDB 1.5.5 (snapshot/compute). In blueprints/us-equities/lifecycle-sample/native-receipt.json (temporal_ledger proof, lines 130-178, and native_commands at lines 196-203), DuckDB Parquet preserved 3 source-derived claims with exact BIGINT observation cutoffs. All five cutoff queries were verified. The historical cutoff returned 0 eligible claims, historical_replay 0, before_first_observation 0, at_first_observation 1 and at_last_observation 3. historical_universe_eligible was false every time. verify-ledger exited 0. An independent network-disabled reproduction matched 28 ledger file size/hash entries (line 218). In blueprints/us-equities/nanosecond-replay/receipt.json, a synthetic fixture was materialized and selected through replay.py (pandas 3.0.6, then DuckDB BIGINT/Parquet) against a pinned snapshot sha256. Precision, overflow, overwrite and corruption were all rejected with exit code 2. The receipt records synthetic true and market_data_adapter_accepted false. In blueprints/us-equities/data/receipt.json, 6 LEAN bundled-simulation order events were written to Parquet under a recorded sha256 on one XNYS session.

c6 alpaca-py 0.44.0 (price and corporate-action acquisition). In blueprints/us-equities/authenticated-data/native-receipt.json (line 11 and results), native GET transport acquired 25 AAPL SIP/raw daily bars and 2 corporate actions over 5 HTTP 200 pages with terminal pagination. All 25 raw closes and both numeric action values match the frozen LEAN probe. Dividend currency and original historical availability remain unestablished. catalogs/us-equities/runtime-target.json line 70 names alpaca-py as the Alpaca ingestion path.

Evidence class: native execution, bounded to one symbol over a retrospective window, with hand-selected or synthetic cases.
- alpaca-py @ 0.44.0 — This verdict comes from my own review of the retained receipts, not from the provider judgments the packet withheld. The requirement has two parts. The first is acquiring licensed, source-identifiable observations that keep feed, timestamps, identity and corporate actions. The second is producing exact, reproducible snapshots that reject data whose availability or eligibility is unknown. Each winner is the only adopted candidate with native receipts for one of those parts.

c1 DuckDB 1.5.5 (snapshot/compute). In blueprints/us-equities/lifecycle-sample/native-receipt.json (temporal_ledger proof, lines 130-178, and native_commands at lines 196-203), DuckDB Parquet preserved 3 source-derived claims with exact BIGINT observation cutoffs. All five cutoff queries were verified. The historical cutoff returned 0 eligible claims, historical_replay 0, before_first_observation 0, at_first_observation 1 and at_last_observation 3. historical_universe_eligible was false every time. verify-ledger exited 0. An independent network-disabled reproduction matched 28 ledger file size/hash entries (line 218). In blueprints/us-equities/nanosecond-replay/receipt.json, a synthetic fixture was materialized and selected through replay.py (pandas 3.0.6, then DuckDB BIGINT/Parquet) against a pinned snapshot sha256. Precision, overflow, overwrite and corruption were all rejected with exit code 2. The receipt records synthetic true and market_data_adapter_accepted false. In blueprints/us-equities/data/receipt.json, 6 LEAN bundled-simulation order events were written to Parquet under a recorded sha256 on one XNYS session.

c6 alpaca-py 0.44.0 (price and corporate-action acquisition). In blueprints/us-equities/authenticated-data/native-receipt.json (line 11 and results), native GET transport acquired 25 AAPL SIP/raw daily bars and 2 corporate actions over 5 HTTP 200 pages with terminal pagination. All 25 raw closes and both numeric action values match the frozen LEAN probe. Dividend currency and original historical availability remain unestablished. catalogs/us-equities/runtime-target.json line 70 names alpaca-py as the Alpaca ingestion path.

Evidence class: native execution, bounded to one symbol over a retrospective window, with hand-selected or synthetic cases.

Alternatives:
- EdgarTools (overlap) — The test applied here is the same one that selected c6. EdgarTools is an acquisition and parsing path with native evidence. It acquired 371 SEC index entries / 360 unique accessions over HTTP 200 (access-resolution.json, lines 8 and 35-41), and it did offline qualification parsing of 6 lifecycle sources (lifecycle-sample/native-receipt.json, line 19). The EdgarTools receipts show no acquisition of the price bars or corporate-action records the requirement names. The cutoff rejections credited to its path came from other code. The header packets that are ineligible at the historical cutoff (eligible_count 0 at as-of 2020-03-03, and 5 only after local observation) came from the custom catalyst.py packet command (access-resolution.json, lines 15 and 104-117). The lifecycle cutoff proof was materialized and verified by DuckDB (lifecycle-sample/native-receipt.json, lines 196-203), with transport through native Requests. EdgarTools therefore supplies source-identifiable documentary identity/lifecycle inputs alongside c1+c6. It is not a better way to meet the acquisition or snapshot requirement. A third winner slot was not justified on this evidence.
- pandas exact timestamp support (overlap) — pandas 3.0.6 was exercised natively only as the parsing stage ahead of DuckDB in the nanosecond replay, and only on a synthetic fixture (synthetic true, market_data_adapter_accepted false). It is part of the selected chain, not a separate store or compute engine.
- exchange_calendars (overlap) — It is a session-calendar input, not storage, compute or observation acquisition. The native receipt confirms one XNYS session only (2013-10-07, 13:30-20:00 UTC), in blueprints/us-equities/data/receipt.json.
- QuestDB (conditional) — Source review only. The catalog records that it 'did not install/start a server', so no throughput or concurrency measurement exists to show that the embedded path falls short. It also records that dedup/upsert can overwrite corrections unless a raw immutable ledger is retained (data-research.json lines 512-515). Untested, not failed.
- ClickHouse (conditional) — Source review only. The local SQL command is prospective, and no server, cluster, throughput or reliability evidence was created. Eventual background merges/deduplication are not an immutable revision ledger (data-research.json lines 553-556). The packet marks the v26.8.7.19-lts pin as behind upstream v26.9.2.8-stable. Untested, not failed.
- Polars (unqualified) — Source review only, and its native_workflow is marked UNEXECUTED. Its catalog limitations say 'A fast lazy plan is not a point-in-time contract' and warn against duplicating a full SQL pipeline solely to add another framework (data-research.json lines 432-435). No demonstrated gap in the DuckDB path exists that it would close.
- lakeFS (conditional) — Source review only; the quickstart is unexecuted. Its catalog limitations say commits do not bring independently updated external databases into one atomic financial snapshot, and that branch retention or garbage collection can remove historical artifacts needed for reproducibility (data-research.json lines 766-770).
- Databento (conditional) — Source review only. No licensed download was executed, and none is billed. The cited catalogs/us-equities/simulation-data-review.json does not mention Databento (case-insensitive grep, 0 matches), so that ref does not support it. Untested, not failed.
- Massive Python client (conditional) — Source review only, and no entitled acquisition was executed. The cited simulation-data-review.json does not mention Massive or Polygon (case-insensitive grep, 0 matches). Untested, not failed.
- OpenBB (unqualified) — Source review only. The import check is unexecuted, and AGPL-3.0 obligations apply. Its catalog limitations say provider-normalized output does not normalize adjustment, time-of-availability or survivorship semantics (data-research.json data-openbb, lines 261ff).
- DVC (unqualified) — Not adopted in the packet. Evidence is source review only, and dvc init/add are marked UNEXECUTED. Its catalog limitation says 'Content hashes prove identity, not data validity or point-in-time correctness' (data-research.json line 724). Pinned-snapshot hashing is already exercised natively by the DuckDB replay path (nanosecond-replay/receipt.json, --snapshot-sha256).
- yfinance (out_of_scope) — Not adopted in the packet. Source review only. The catalog text states that upstream intends Yahoo Finance API data for personal use, and that present-day adjusted history with current tickers is insufficient for point-in-time research (data-research.json lines 286 and 300-302). That conflicts with the licensed, source-identifiable requirement.

Overturn when: The existing scripts cannot run a challenger as they stand. replay.py and sample.py import duckdb and have no backend option (replay.py lines 170-188; sample.py lines 402-418). compare.py loads alpaca-historical/collect.py (compare.py lines 15-20). Any challenger arm therefore first needs a new, reviewed backend or provider adapter that consumes the same inputs.

Store verdict. The baseline arm reruns the recorded commands:
- `python3 blueprints/us-equities/nanosecond-replay/replay.py materialize --source blueprints/us-equities/nanosecond-replay/fixture.json --output <new dir>`, then `replay.py select --snapshot <dir> --snapshot-sha256 66592c36e19f9509294ac5fe1d7bf6907aee324f74dd2ae025619d00e87e1726 --universe-id fixture-universe --feed fixture-feed --cutoff <each receipt cutoff>` (nanosecond-replay/receipt.json lines 92-128ff).
- `python3 blueprints/us-equities/lifecycle-sample/sample.py verify-ledger --source <ledger dir> --receipt-sha256 b66796b68f63918285b943d37229c448511a9a8f9b705fb087537948be9bb036` (lifecycle-sample/native-receipt.json line 201).

Promote QuestDB 10.0.1 or ClickHouse v26.8.7.19-lts only if an adapter over the same fixture and lifecycle source plan meets three conditions. It must reproduce identical selections and cutoff counts. It must reject the same precision, overflow, overwrite and corruption cases with exit code 2. It must also show measured ingest/query throughput or concurrency on representative securities that the DuckDB/Parquet arm cannot meet.

Acquisition verdict. A Databento or Massive collector must acquire the same AAPL SIP window (2020-08-03 to 2020-09-04) and the two action targets frozen in blueprints/us-equities/alpaca-historical/plan.json. It must be reconciled against the frozen LEAN probe by a compare path equivalent to authenticated-data/compare.py. Promote it only if it matches at least 25/25 closes and 2/2 actions, and also resolves dividend currency and historical availability with auditable records at an acceptable measured cost.

Open gaps:
- No candidate establishes a survivorship-free universe, delisting, ticker-reuse or complete corporate-action coverage. historical_universe_eligible is false in all five lifecycle cutoffs.
- The Alpaca dividend currency is unknown (unknown_currency 1), so cash-unit reconciliation of corporate actions is incomplete.
- Original historical (as-known) availability of the provider data is not established, and local available_ns equals observed_ns.
- No throughput, concurrency or scale measurement exists for DuckDB or for any server or lake alternative. The condition 'add a server after measurement' is therefore unevaluated, not failed.
- No challenger comparison can run until adapters exist. The replay, lifecycle and compare scripts are hard-wired to DuckDB and the Alpaca collector.
- Databento, Massive, QuestDB, ClickHouse, lakeFS, Polars, OpenBB and DVC are untested, not failed.
- No receipt establishes real-time feed entitlement or licensing/redistribution terms for stored data.
- The cutoff-rejection behaviour credited to the EdgarTools path is custom repository code (catalyst.py packet and the DuckDB ledger), not an upstream EdgarTools capability.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-storage-compute-20260922; codex: -)
<!-- verdicts:end -->
