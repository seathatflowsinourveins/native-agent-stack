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

The trading packets were rebuilt once. The first run gave each trading layer its
group's shared candidate list, so sibling layers chose from identical candidates.
The recorded trading verdicts come from a second run in which each packet held the
convergence manifest's own entries for that layer, with evidence from their domain
cards (`lane_packets.py --trading-candidates manifest`). The foundation packets were
identical in both runs. The ledger's v1 `candidates` lists remain the dated group-wide
review.

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
- **Trading candidates are layer-specific, from one source.** The trading verdicts
  were recorded from packets built from the convergence manifest's entries for each
  layer. The four rows first judged against a group list now name their own tools:
  - `security-supply-chain`: Syft, Grype and Gitleaks.
  - `data-quality-orchestration`: Dagu and Pandera.
  - `evaluation-experiments`: Inspect AI and MLflow.
  - `agents-models-workers`: ai-memory, SocratiCode and Serena.

  Other trading rows changed too. For example, `execution-broker` now records the
  Alpaca paper adapter and alpaca-py, because the Nautilus IBKR adapter has no broker
  acceptance yet. A candidate the manifest does not list for a layer cannot be
  chosen for it, so a missing tool is a manifest gap to fix at the next convergence
  run.
- **Recorded pins can lag.** The trading `agents-models-workers` row cites older
  foundation pins, for example ai-memory 2.3.1 and Serena 1.7.0. The convergence
  manifest owns current versions.
- **Evidence strength varies by row.** One foundation row (`git-github-automation`)
  and two trading rows (`identity-provenance`, `evaluation-experiments`) record
  `source_review` winners. `data-quality-orchestration` rests on a synthetic
  fixture, and no winner rests on a `measured_comparison`. Every
  `keep_but_compare` row names the comparison it still owes.

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
| agents-models-workers | foundation-memory | recorded | foundation-ai-memory @ v2.3.1; foundation-socraticode @ v1.14.0; foundation-serena @ v1.7.0 | native_proven | 16 | The verdict changes if the frozen 12-query harness at blueprints/us-equities/retrieval-evaluation/ (fixture.json, run-b… | evidence/receipts/native-context-memory.json, evidence/receipts/native-memory.json, evidence/receipts/native-rag.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| backtesting-engine | engines-strategies | recorded | nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e); lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f | native_proven | 1 | Reopen the verdict if any of these three things happens.

1. The hardened SPY/LEAN one_zero rerun fails. The rerun come… | blueprints/us-equities/engine/README.md, evidence/receipts/native-nautilus-v2-20260920.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| data-quality-orchestration | agents-operations | recorded | dagu @ v2.16.6; data-pandera @ v0.33.1; source 62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6 | synthetic | 2 | Replace Dagu only when a candidate such as Temporal produces a comparable retained receipt under blueprints/us-equities… | blueprints/us-equities/hosting/README.md, catalogs/landscape/us-equities.json | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| evaluation-experiments | agents-operations | recorded | inspect-ai @ inspect-ai0.3.266; source ec4dfc6953784dc45b79de3147530c89868c6e26; data-mlflow @ v3.16.1; source 32792afe5b0183fce10532d3a023f5cfa8612d09 | source_review | 4 | The verdict changes when an executed receipt shows one of the following:

(a) inspect-ai 0.3.266 fails the next accepta… | catalogs/landscape/us-equities.json | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| execution-broker | engines-strategies | recorded | adaptive-paper-alpaca-adapter @ 7e7eefe28315f3de3aa4dc75cc8b6524f70829cb (blueprints/us-equities/adaptive-paper); alpaca-py @ 0.44.0 | local_integration | 4 | Reopen the verdict if either of the following happens, on the same frozen config and failure contract. (1) The first op… | blueprints/us-equities/adaptive-paper/receipt.json, blueprints/us-equities/order-contract/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| identity-provenance | data-research | recorded | data-dvc @ 3.67.1; source 356dfa03278058b02df42124f243c2c345329dae | source_review | 7 | This verdict changes only after an executed comparison on the retained synthetic point-in-time fixture. The metric cann… | catalogs/landscape/us-equities.json | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| market-data-reference | data-research | recorded | data-alpaca-py @ v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28; data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a; data-exchange-calendars @ 4.13.2; source dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a | native_proven | 9 | Four checks could change this verdict.

1. A retained blueprints/us-equities/ receipt shows c14 Databento (or another f… | blueprints/us-equities/catalyst-provenance/receipt.json, blueprints/us-equities/data/receipt.json, catalogs/landscape/us-equities.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| observability-hosting | agents-operations | recorded | opentelemetry-collector-contrib @ v0.161.0; prometheus @ v3.14.0; loki @ v3.7.8 | native_proven | 11 | 1. Backend retention: run `python3 observability/backends/check_persistence.py --grafana-env <private Grafana env file>… | observability/README.md, observability/backends/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| portfolio-risk | engines-strategies | recorded | skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee | native_proven | 3 | The verdict should be reopened in three cases. (1) Rerunning `python3 -m unittest discover -s tests -p test_research_ev… | blueprints/us-equities/research-evaluation/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| research-factors-ml | engines-strategies | recorded | skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee; data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a | native_proven | 22 | For c23, the verdict changes if either of these fails:
- python3 -m unittest discover -s tests -p test_research_evaluat… | blueprints/us-equities/catalyst-provenance/receipt.json, blueprints/us-equities/research-evaluation/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| security-supply-chain | agents-operations | recorded | syft @ v1.52.0; grype @ v0.119.0; gitleaks @ v8.30.1 | native_proven | 2 | Change the verdict if either of these is retained. (a) A native OpenBao receipt under blueprints/us-equities/ showing t… | blueprints/us-equities/supply-chain/README.md, blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json, recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| storage-compute | data-research | recorded | data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa | native_proven | 9 | The storage/compute default changes only if an executed comparison beats c4 on the same frozen, representative multi-sy… | blueprints/us-equities/data/receipt.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |

### us-equities (per-layer narrative)

#### Agents, models and workers (agents-models-workers)

- foundation-ai-memory @ v2.3.1 — This verdict is my own review of the retained receipts, revised to address the refuter findings. No TypeSafe inference results were supplied, and no provider judgment was retained. The requirement asks for durable project knowledge, exact code and dated financial sources, with cross-client retrieval, source recovery, explicit project scope and measurable quality.

c7 ai-memory. Native execution in evidence/receipts/native-memory.json. Native Codex 0.155.1 exited 0, and its receipt says only that it "called native MCP memory_read_page; returned correct heading and four disabled features" (line 21). It records neither the heading text nor explicit scope. Native Claude 2.1.277 exited 0 with terminal_reason completed. Its receipt records the heading "Shared project memory deployment" and "Single memory_read_page call with explicit scope" (line 47). The same receipt records cross_client_handoff_received true and 8 Codex and 9 Claude ai_memory_observations. For explicit project scope, blueprints/us-equities/memory-lifecycle/README.md (lines 3 and 5) records a native run of the upstream ai-memory 2.3.1 binary: 31 MCP tool calls and 23 fixture checks passed. Each project got back its own body, searches for the other project's unique term returned zero hits, and a superseded page was retrievable at its ingestion-time instant. Line 28 limits this: it covers ingestion-time rather than market valid-time data and does not exercise the Codex or Claude hooks or semantic retrieval quality.

c12 SocratiCode. Native execution in evidence/receipts/native-rag.json. Native Codex and native Claude each ran MCP codebase_search with limit 1. Both returned tools/ecosystem/linux-usage-report.cjs lines 2-39 with score 0.6429. The index held 35 files and 139 chunks with status green. Embeddings came from local Nemotron-3-Embed-1B-BF16 through vLLM. evidence/receipts/desktop-direct-rag.json repeats the result in the Desktop client.

c9 Serena. The structured calls, completed find_symbol and find_referencing_symbols, appear only under historical_codex in evidence/receipts/native-context-memory.json. The Claude side rests on a single inventory line, "Actual fetch symbol and 3 references retrieved.", in evidence/receipts/component-history.json (line 101). That file calls itself "a provenance statement, not a new live test" (line 46), and it records version 2.0.0.dev0 rather than the packet pin v1.7.0.

Why these three. Each performs native MCP retrieval for one part of the requirement: memory (c7), conceptual code (c12) or exact symbols and references (c9). The correction to my earlier text is that they are not the only adopted candidates run in both client families. c14 ran in native Claude through the MCPorter bridge and in Codex Desktop through a CLI bridge. c11 ran in both clients. c14 still stays an overlap fallback, because component-history.json records neither native Claude nor native Codex MCP registration for it and its edges are static. c11 returns bounded output and is not durable-knowledge retrieval.

None of the winners has measured retrieval quality beyond single queries, and none covers dated financial sources.
- foundation-socraticode @ v1.14.0 — This verdict is my own review of the retained receipts, revised to address the refuter findings. No TypeSafe inference results were supplied, and no provider judgment was retained. The requirement asks for durable project knowledge, exact code and dated financial sources, with cross-client retrieval, source recovery, explicit project scope and measurable quality.

c7 ai-memory. Native execution in evidence/receipts/native-memory.json. Native Codex 0.155.1 exited 0, and its receipt says only that it "called native MCP memory_read_page; returned correct heading and four disabled features" (line 21). It records neither the heading text nor explicit scope. Native Claude 2.1.277 exited 0 with terminal_reason completed. Its receipt records the heading "Shared project memory deployment" and "Single memory_read_page call with explicit scope" (line 47). The same receipt records cross_client_handoff_received true and 8 Codex and 9 Claude ai_memory_observations. For explicit project scope, blueprints/us-equities/memory-lifecycle/README.md (lines 3 and 5) records a native run of the upstream ai-memory 2.3.1 binary: 31 MCP tool calls and 23 fixture checks passed. Each project got back its own body, searches for the other project's unique term returned zero hits, and a superseded page was retrievable at its ingestion-time instant. Line 28 limits this: it covers ingestion-time rather than market valid-time data and does not exercise the Codex or Claude hooks or semantic retrieval quality.

c12 SocratiCode. Native execution in evidence/receipts/native-rag.json. Native Codex and native Claude each ran MCP codebase_search with limit 1. Both returned tools/ecosystem/linux-usage-report.cjs lines 2-39 with score 0.6429. The index held 35 files and 139 chunks with status green. Embeddings came from local Nemotron-3-Embed-1B-BF16 through vLLM. evidence/receipts/desktop-direct-rag.json repeats the result in the Desktop client.

c9 Serena. The structured calls, completed find_symbol and find_referencing_symbols, appear only under historical_codex in evidence/receipts/native-context-memory.json. The Claude side rests on a single inventory line, "Actual fetch symbol and 3 references retrieved.", in evidence/receipts/component-history.json (line 101). That file calls itself "a provenance statement, not a new live test" (line 46), and it records version 2.0.0.dev0 rather than the packet pin v1.7.0.

Why these three. Each performs native MCP retrieval for one part of the requirement: memory (c7), conceptual code (c12) or exact symbols and references (c9). The correction to my earlier text is that they are not the only adopted candidates run in both client families. c14 ran in native Claude through the MCPorter bridge and in Codex Desktop through a CLI bridge. c11 ran in both clients. c14 still stays an overlap fallback, because component-history.json records neither native Claude nor native Codex MCP registration for it and its edges are static. c11 returns bounded output and is not durable-knowledge retrieval.

None of the winners has measured retrieval quality beyond single queries, and none covers dated financial sources.
- foundation-serena @ v1.7.0 — This verdict is my own review of the retained receipts, revised to address the refuter findings. No TypeSafe inference results were supplied, and no provider judgment was retained. The requirement asks for durable project knowledge, exact code and dated financial sources, with cross-client retrieval, source recovery, explicit project scope and measurable quality.

c7 ai-memory. Native execution in evidence/receipts/native-memory.json. Native Codex 0.155.1 exited 0, and its receipt says only that it "called native MCP memory_read_page; returned correct heading and four disabled features" (line 21). It records neither the heading text nor explicit scope. Native Claude 2.1.277 exited 0 with terminal_reason completed. Its receipt records the heading "Shared project memory deployment" and "Single memory_read_page call with explicit scope" (line 47). The same receipt records cross_client_handoff_received true and 8 Codex and 9 Claude ai_memory_observations. For explicit project scope, blueprints/us-equities/memory-lifecycle/README.md (lines 3 and 5) records a native run of the upstream ai-memory 2.3.1 binary: 31 MCP tool calls and 23 fixture checks passed. Each project got back its own body, searches for the other project's unique term returned zero hits, and a superseded page was retrievable at its ingestion-time instant. Line 28 limits this: it covers ingestion-time rather than market valid-time data and does not exercise the Codex or Claude hooks or semantic retrieval quality.

c12 SocratiCode. Native execution in evidence/receipts/native-rag.json. Native Codex and native Claude each ran MCP codebase_search with limit 1. Both returned tools/ecosystem/linux-usage-report.cjs lines 2-39 with score 0.6429. The index held 35 files and 139 chunks with status green. Embeddings came from local Nemotron-3-Embed-1B-BF16 through vLLM. evidence/receipts/desktop-direct-rag.json repeats the result in the Desktop client.

c9 Serena. The structured calls, completed find_symbol and find_referencing_symbols, appear only under historical_codex in evidence/receipts/native-context-memory.json. The Claude side rests on a single inventory line, "Actual fetch symbol and 3 references retrieved.", in evidence/receipts/component-history.json (line 101). That file calls itself "a provenance statement, not a new live test" (line 46), and it records version 2.0.0.dev0 rather than the packet pin v1.7.0.

Why these three. Each performs native MCP retrieval for one part of the requirement: memory (c7), conceptual code (c12) or exact symbols and references (c9). The correction to my earlier text is that they are not the only adopted candidates run in both client families. c14 ran in native Claude through the MCPorter bridge and in Codex Desktop through a CLI bridge. c11 ran in both clients. c14 still stays an overlap fallback, because component-history.json records neither native Claude nor native Codex MCP registration for it and its edges are static. c11 returns bounded output and is not durable-knowledge retrieval.

None of the winners has measured retrieval quality beyond single queries, and none covers dated financial sources.

Alternatives:
- foundation-codebase-memory-mcp (overlap) — This is a static-graph exact-code fallback. It has runs in both client families, but only through bridges. evidence/receipts/native-cli-gaps.json records native Claude running search_graph and trace_path through MCPorter with status passed, returning collect at lines 91-127 with 4 callees. The native Codex CLI follow-up there was blocked_before_tools by usage_limit_exceeded. evidence/receipts/desktop-cli-workflows.json (lines 11 and 25-41) records the active Codex Desktop task running static graph search and trace with search_exit 0 and trace_exit 0. It returned collect in tools/ecosystem/linux-usage-report.cjs at lines 91-127 with callees installation, sourcesFor, runParser and overlaps, and runtime_execution_trace false. evidence/receipts/component-history.json (lines 249-251) records native_claude and native_codex as 'not independently demonstrated' and current_desktop as a 'Root CLI bridge'. So c14 has no native MCP registration proof, its static edges do not prove runtime execution, and it overlaps c9 and c12 for exact code. A head-to-head against c9 on exact-symbol recall has not been run.
- Qdrant (overlap) — Qdrant is the vector store behind c12, not a separate retrieval interface. evidence/receipts/native-rag.json shows collection codebase_72cfa87c5abf with status green, reached through SocratiCode. component-history.json records it as a supporting local service. Its card states that no financial-document corpus exists yet. Selecting c12 already includes it.
- Context Mode (conditional) — Context Mode ran in both clients: native-context-memory.json fresh_startup records ctx_execute, and observability/restart-receipt.json records 11 tools and 14 successful results. It executes large outputs and returns bounded results, which does not make it a durable project-knowledge or code retrieval store. blueprints/us-equities/workers/receipt.json records ctx_execute_file failing in the SDK worker on the project-root restriction, with a scoped override blocked by the approval policy. estimated_tokens_saved was 0 in workers/receipt.json and restart-receipt.json.
- vllm (conditional) — vLLM is a runtime dependency that serves c12's local embeddings, not a retrieval layer. evidence/receipts/vllm-compatibility.json shows 0.29.0 installed but failing GPU startup with 'RuntimeError: UVA is not available' on the WSL host. 0.25.0 was restored, and desktop-direct-rag.json records active_model_service_version 0.25.0 with retrieval passing. The packet's upstream v0.30.0 is untested.
- foundation-repomix (conditional) — Repomix builds selected-file handoff bundles only. evidence/receipts/portable-cli-artifacts.json records one standalone CLI fixture pack (repomix_contains_selected_paths true) and says it is 'not an LLM invocation'. component-history.json records native Claude and Codex use as 'not independently demonstrated' and one lossy artifact at 3679→645 o200k tokens. The output is not a retrievable index and has no quality measure. I corrected the evidence class to synthetic because only a fixture CLI run is retained.
- foundation-toon (out_of_scope) — TOON is a serialization format, not retrieval. portable-cli-artifacts.json records one standalone encode/decode fixture roundtrip (toon_roundtrip_equal true) that is 'not an LLM invocation'. component-history.json says it is not independently demonstrated in native clients, and a nested fixture grew from 69 to 94 tokens. I corrected the evidence class to synthetic.
- RTK (out_of_scope) — RTK compacts command output and does not retrieve knowledge. The native hook and explicit calls passed (component-history.json id rtk; native-context-memory.json 'rtk git log -6' exit 0). The only measure is a lossy artifact count of 533→176 tokens (artifact-reductions.json historical_rtk), which is not a retrieval-quality result.
- codex-native-sdk (conditional) — This is the evidenced worker runtime that matches the layer title, but it does not meet the stated retrieval requirement. blueprints/us-equities/workers/receipt.json records one completed research turn that read receipts through Context Mode ctx_execute. ctx_execute_file failed, and the configured model is not independent provider attestation. policy.md delegates retrieval to the QMD, Serena, SocratiCode, ai-memory and Context Mode lanes.
- codex-acp (out_of_scope) — This is an ACP worker adapter. deerflow/research-receipt.json records one embedded prompt that completed, but the 'read-only' mode maps to workspaceWrite/on-request. The receipt says no memory/RAG integration was exercised.
- deerflow (out_of_scope) — DeerFlow is an optional research host. native-receipt.json shows memory disabled and the discovery database running in memory. research-receipt.json records one invoke_acp_agent prompt with no planner, UI or standing service, and states that no memory/RAG integration or durable recovery was exercised.
- omniroute (out_of_scope) — OmniRoute is a provider gateway, not retrieval. health-receipt.json holds status-only HTTP 200 checks. astra-receipt.json and routing/README.md record one Astra text response of 136 tokens after an initial HTTP 400 and an HTTP 499. The README says tools, compaction and worker parity remain unproved.
- langgraph (out_of_scope) — LangGraph provides an agent-state graph, not retrieval. Its only evidence is a source-review URL, which I did not open. Its card says the import is an installation smoke test only and that InMemorySaver loses state on restart.
- foundation-pageindex (unqualified) — PageIndex is the only candidate whose role targets document and financial retrieval, but its evidence is a source-review URL only. I did not open it, and nothing was run on a financial corpus. The pin is behind upstream (v0.2.18 vs v0.2.19). Untested does not mean it failed.
- Graphiti (unqualified) — Graphiti's evidence is source review only (URLs, not opened). The card says there is no graph deployment and no extraction-accuracy proof. Dated sourced relationships would fit the financial-source part of the requirement, but nothing was executed.
- foundation-pgvector (unqualified) — pgvector's evidence is source review only (URL, not opened). The card says a build is not extension activation and that it adds no benefit over the current Qdrant index without an established SQL integration need.
- foundation-agent-retrieval-bench (unqualified) — This is an evaluation harness that could supply the measurable-quality part of the requirement, but nothing was downloaded or evaluated, and I did not open its URLs. The card states that its 427 examples across 25 repositories are not a financial-document benchmark.

Overturn when: The verdict changes if the frozen 12-query harness at blueprints/us-equities/retrieval-evaluation/ (fixture.json, run-bm25.mjs, receipt.json) is extended into a preregistered held-out set and run at a matched context budget. The set should cover dated financial documents with as-of dates, exact code symbols and project decisions, with gold source spans. The receipt currently measures only QMD 2.8.3 BM25, with recall@3 of 8/12. A candidate would need to beat c7/c12/c9 on exact-source recall@3 and on correct abstention without higher measured native task cost. It must also keep project isolation, checked with `python3 -m unittest discover -s tests -p test_memory_lifecycle.py` (the command documented in blueprints/us-equities/memory-lifecycle/README.md line 37) and a fresh run of blueprints/us-equities/memory-lifecycle/run.py. An exact-symbol head-to-head in which c14 beats c9 in native MCP registration in both clients would move c14 into the winner set. A native failure of c7, c12 or c9 on current pins in either client would also overturn the verdict.

Open gaps:
- No adopted candidate has evidence of retrieving dated financial sources. The Qdrant card says no financial-document corpus exists, the deerflow research receipt says no memory/RAG integration was exercised, and the memory-lifecycle README (line 28) covers ingestion-time rather than market valid-time data.
- No winner has measured retrieval quality. SocratiCode has one limit-1 query (score 0.6429), and ai-memory has one read of a known page in each client. The packet's '8/12 exact-source recall at three' is retained at blueprints/us-equities/retrieval-evaluation/receipt.json (lines 362-368 and 703). It measures QMD 2.8.3 BM25, which is not a packet candidate. The receipt itself says it is not an independent holdout or complete financial RAG (line 706).
- Candidate coverage: the only lane with measured retrieval quality over the us-equities corpus (QMD) is absent from the candidate set, and the packet lists sota_components_not_in_candidates as empty. It therefore cannot be recorded in challenger_preferred.
- The layer title 'Agents, models and workers' does not match the retrieval requirement text. Worker candidates (c20, c19, c21) were judged against the retrieval requirement.
- Serena's native Claude proof is one component-history inventory line (component-history.json line 101), which the file itself labels as provenance rather than a live test (line 46). The recorded version is 2.0.0.dev0, not the packet pin v1.7.0. Structured Serena calls are retained only for Codex.
- The ai-memory Codex receipt does not record explicit scope or the heading text (native-memory.json line 21). The ai-memory pin v2.3.1 is behind upstream v2.4.0. Current pins were not re-executed.
- No exact-symbol comparison between c9 and c14 exists, and c14's runs in both families were through CLI bridges, not native MCP.
- Off-host durability and new-host client rebinding for the memory store remain unqualified. The memory-lifecycle run did not exercise service restart durability or the active hooks.
- The source-review-only candidates (c2, c10, c15, c22) have not failed. They are untested.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-agents-models-workers-20260922; codex: -)

#### Backtesting engine (backtesting-engine)

- nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e) — This is my own review of the retained files. Provider and card judgments were checked against those files, not taken as given.

c5 (NautilusTrader 2.0.0rc5) is the destination named in the requirement (packet line 194). catalogs/us-equities/runtime-target.json also records it with engine.decision "selected_destination" and source_commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e.

What was observed natively: evidence/receipts/native-nautilus-v2-20260920.json shows the unchanged upstream synthetic EUR/USD quickstart passing in two isolated offline runs, run-3 and run-4. Each run had 902 orders, 902 fills and 451 positions. Ending cash was 1000431.00000 USD from a start of 1000000.00, and realized PnL was 431.00, with every position flat. account.csv was byte-identical across the two runs. Fills and positions matched once UUIDv4 identities were normalized. The two earlier attempts, run-1 and run-2, returned empty reports and are retained as unsuccessful.

A local integration check is also retained: blueprints/us-equities/engine-nautilus/equity-replay/receipt.json (lines 39-88). It records two native runs, final-1 and final-2, both with exit code 0, over 15 AAPL sessions. Each scenario had 10 fills and 5 closed positions. The baseline scenario ended with cash 99866.60 and realized PnL -133.40. The fee_slippage_stress scenario ended with cash 99855.60, realized PnL -144.40 and fees 10.00. realized_pnl_reconciled is true in both scenarios. A separate reviewer recomputed every CSV cash transition and closed-position PnL, but did not rerun the native replay (line 83).

c4 (LEAN 985ef30) is kept only as the oracle, which the requirement explicitly asks to preserve. blueprints/us-equities/engine/receipt.json shows the unmodified bundled BasicTemplateFrameworkAlgorithm completing with 3943 data points, 3 submitted orders and 3 filled orders. Its order_list_hash matches upstream. blueprints/us-equities/engine/resolution-receipt.json shows the three-reference patched build replaying with the same hash, and it reports 0 vulnerable packages in both the launcher audit and the source-integrated adapter audit.

Neither engine has passed SPY/LEAN parity. evidence/artifacts/comparison-progress-20260922/summary.json records the one_zero comparison as BLOCKED, with returned_failed_checks 4 and two unsupported mappings: distributions_and_cash and market_on_open_proxy. The selection therefore covers engine execution and cash-accounting determinism. It does not cover parity, numeric-risk verification or broker readiness.
- lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f — This is my own review of the retained files. Provider and card judgments were checked against those files, not taken as given.

c5 (NautilusTrader 2.0.0rc5) is the destination named in the requirement (packet line 194). catalogs/us-equities/runtime-target.json also records it with engine.decision "selected_destination" and source_commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e.

What was observed natively: evidence/receipts/native-nautilus-v2-20260920.json shows the unchanged upstream synthetic EUR/USD quickstart passing in two isolated offline runs, run-3 and run-4. Each run had 902 orders, 902 fills and 451 positions. Ending cash was 1000431.00000 USD from a start of 1000000.00, and realized PnL was 431.00, with every position flat. account.csv was byte-identical across the two runs. Fills and positions matched once UUIDv4 identities were normalized. The two earlier attempts, run-1 and run-2, returned empty reports and are retained as unsuccessful.

A local integration check is also retained: blueprints/us-equities/engine-nautilus/equity-replay/receipt.json (lines 39-88). It records two native runs, final-1 and final-2, both with exit code 0, over 15 AAPL sessions. Each scenario had 10 fills and 5 closed positions. The baseline scenario ended with cash 99866.60 and realized PnL -133.40. The fee_slippage_stress scenario ended with cash 99855.60, realized PnL -144.40 and fees 10.00. realized_pnl_reconciled is true in both scenarios. A separate reviewer recomputed every CSV cash transition and closed-position PnL, but did not rerun the native replay (line 83).

c4 (LEAN 985ef30) is kept only as the oracle, which the requirement explicitly asks to preserve. blueprints/us-equities/engine/receipt.json shows the unmodified bundled BasicTemplateFrameworkAlgorithm completing with 3943 data points, 3 submitted orders and 3 filled orders. Its order_list_hash matches upstream. blueprints/us-equities/engine/resolution-receipt.json shows the three-reference patched build replaying with the same hash, and it reports 0 vulnerable packages in both the launcher audit and the source-integrated adapter audit.

Neither engine has passed SPY/LEAN parity. evidence/artifacts/comparison-progress-20260922/summary.json records the one_zero comparison as BLOCKED, with returned_failed_checks 4 and two unsupported mappings: distributions_and_cash and market_on_open_proxy. The selection therefore covers engine execution and cash-accounting determinism. It does not cover parity, numeric-risk verification or broker readiness.

Alternatives:
- cvxportfolio (unqualified) — The only evidence_ref is an external README URL for version 1.5.1, which this lane could not open. The evidence kind is source_review only. The packet's card_limitations (packet lines 25-28) say the prospective workflow is unexecuted and that the tool is a research simulator, not an order gateway. Its role, multi-period portfolio policies with cost models, sits beside the engine requirement rather than meeting it: it has no broker boundaries and no execution-grade equity accounting. review_status is unmaintained_signal. There is no native run, integration or comparison on the frozen SPY/AAPL inputs.

Overturn when: Reopen the verdict if any of these three things happens.

1. The hardened SPY/LEAN one_zero rerun fails. The rerun comes after the distributions_and_cash and market_on_open_proxy mappings are hardened. It must meet the exact event set and the tolerance of at most $0.01 absolute difference per value defined in blueprints/us-equities/engine-nautilus/acceptance-plan.md (lines 75-143). Its result would replace the BLOCKED row in evidence/artifacts/comparison-progress-20260922/summary.json.

2. `python3 -m unittest tests.test_nautilus_equity_replay -v` no longer exits 0 with 8 tests. This check is synthetic-class only: it runs the admission, numeric-refusal and oracle-rejection fixtures and does not reproduce the native cash figures.

3. An owner-side native rerun no longer reproduces the reconciled cash figures: 99866.60 for baseline and 99855.60 for fee_slippage_stress. The rerun is `python3 blueprints/us-equities/engine-nautilus/equity-replay/launch.py --python <NAUTILUS_ENV>/bin/python --run <RETAINED_ALPACA_RUN> --out <PRIVATE_EVIDENCE>/<RUN_ID>`. It needs private retained Alpaca data and a Nautilus environment, so it cannot be run from the repository alone.

A non-adopted engine, Lumibot (c6) or ai-trader (c1), would be promoted only by passing the same one_zero parity case with reconciled cash on the same frozen inputs.

Open gaps:
- SPY/LEAN one_zero parity is not established. The retained comparison is BLOCKED with 4 failed checks, and runtime-target.json next_acceptance status is reported_execution_blocked_review_incomplete.
- The per-check totals and the private spy-parity/verdict.json are not retained in this repository. The summary shows only a source sha256.
- Deterministic numeric risk is not established by any retained winner evidence. The packet (line 192) records two bare matches! expressions in the Nautilus risk tests that do not assert denial variants; this is a source-review test defect, not an observed runtime failure. tests/test_nautilus_equity_replay.py contains test_numeric_and_participation_refusals, but that is a synthetic admission fixture, not a native risk-engine check.
- The native AAPL replay cannot be reproduced from the repository alone. launch.py requires --python, --run and --out (lines 17-19), and the input is a private retained Alpaca run (receipt.json lines 36 and 105). The repository tests are synthetic fixtures and do not assert the 99866.60 or 99855.60 figures.
- The AAPL replay deliberately avoids corporate-action dates and uses retrospective synthetic close fills with unlimited depth. It does not establish liquidity or fill realism.
- IBKR adapter acceptance is not_established. Alpaca native in-flight fault behavior is still unqualified (packet line 190).
- No point-in-time universe, causal-data qualification, cost-aware out-of-sample strategy evaluation or profitability is established.
- The LEAN Alpaca adapter was never initialized because the product-347 entitlement check was not invoked. A successful LEAN build is not a security certification.
- Nautilus is still a prerelease (2.0.0rc5). The claim that upstream's latest non-prerelease is v1.231.0 comes only from the packet's upstream metadata and card text; no repository receipt confirms it.
- cvxportfolio (c2) has no retained local evidence.
- No evidence exists for the non-adopted c1, c3 or c6, so they were not assessed as alternatives.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-backtesting-engine-20260922; codex: -)

#### Data quality and orchestration (data-quality-orchestration)

- dagu @ v2.16.6 — The two winners rest on different evidence classes. The set-level class is therefore the weaker one, synthetic.

c3, Dagu v2.16.6, is native_proven. It is the only candidate with retained native execution for the orchestration requirement. blueprints/us-equities/hosting/receipt.json has kind native_cli_e2e and is dated 2026-09-19. It records a manual `dagu start` run with exit_code 0 and status succeeded for the 3-step run. It also records three fixtures. In the failure fixture, requested_step_exit is 23 and cli_exit is 1, the run status is failed and the dependent step is aborted. In the cancellation fixture, `dagu stop` returns stop_exit 0 and the run status is aborted. In the restart fixture, service_restart_exit is 0 and prior_history_rows_preserved is true. The receipt further records inherited_environment "HOME PATH DAGU_HOME only", model_calls 0 and broker_calls 0, and it retains the initial schema and env-passthrough failures.

The failure and cancellation fixtures show Dagu's own step-level supervision of owned processes. The systemd user service with restart_policy on-failure supervises only the read-only `dagu server` dashboard. Service.recurring_schedule, ui_run_dags and automatic_model_dispatch are all false, and hosting/README.md says manual CLI commands remain the execution lane.

blueprints/us-equities/research-runtime/receipt.json has kind native_model_e2e. It records native_history_status succeeded, with the packet and order_table steps succeeded. Its final_validation_exit_codes [0,0] are the two `dagu validate` YAML validations, not step results. It records paired_model_workflow_executed false. A separate native Claude Opus 5 report ran outside the Dagu graph with process_exit_code 0, and its usage matched Prometheus and Loki. The receipt retains the failed initial Dagu validation and the unresolved Codex sign-in failure.

c4, pandera 0.33.1, is synthetic. It is the data-quality snapshot gate that complements Dagu; it does not orchestrate. The packet's evidence_ref for c4 is only an upstream URL, which I could not open. In my own source review, blueprints/us-equities/data/README.md documents a fail-closed promotion gate. The retained synthetic fixture output blueprints/us-equities/data/fixtures/bad-gate-result.json shows status fail, row_count 4 and 5 failing named checks, with pandera 0.33.1 and pandas 3.0.6. tests/test_promotion_gate.py lines 156-165 assert the same 5 failing checks. That fixture class runs only through the gate's isolated venv (line 90 skipUnless), and I did not re-execute it. This is synthetic evidence of schema-gate behavior, not validation of real market data.
- data-pandera @ v0.33.1; source 62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6 — The two winners rest on different evidence classes. The set-level class is therefore the weaker one, synthetic.

c3, Dagu v2.16.6, is native_proven. It is the only candidate with retained native execution for the orchestration requirement. blueprints/us-equities/hosting/receipt.json has kind native_cli_e2e and is dated 2026-09-19. It records a manual `dagu start` run with exit_code 0 and status succeeded for the 3-step run. It also records three fixtures. In the failure fixture, requested_step_exit is 23 and cli_exit is 1, the run status is failed and the dependent step is aborted. In the cancellation fixture, `dagu stop` returns stop_exit 0 and the run status is aborted. In the restart fixture, service_restart_exit is 0 and prior_history_rows_preserved is true. The receipt further records inherited_environment "HOME PATH DAGU_HOME only", model_calls 0 and broker_calls 0, and it retains the initial schema and env-passthrough failures.

The failure and cancellation fixtures show Dagu's own step-level supervision of owned processes. The systemd user service with restart_policy on-failure supervises only the read-only `dagu server` dashboard. Service.recurring_schedule, ui_run_dags and automatic_model_dispatch are all false, and hosting/README.md says manual CLI commands remain the execution lane.

blueprints/us-equities/research-runtime/receipt.json has kind native_model_e2e. It records native_history_status succeeded, with the packet and order_table steps succeeded. Its final_validation_exit_codes [0,0] are the two `dagu validate` YAML validations, not step results. It records paired_model_workflow_executed false. A separate native Claude Opus 5 report ran outside the Dagu graph with process_exit_code 0, and its usage matched Prometheus and Loki. The receipt retains the failed initial Dagu validation and the unresolved Codex sign-in failure.

c4, pandera 0.33.1, is synthetic. It is the data-quality snapshot gate that complements Dagu; it does not orchestrate. The packet's evidence_ref for c4 is only an upstream URL, which I could not open. In my own source review, blueprints/us-equities/data/README.md documents a fail-closed promotion gate. The retained synthetic fixture output blueprints/us-equities/data/fixtures/bad-gate-result.json shows status fail, row_count 4 and 5 failing named checks, with pandera 0.33.1 and pandas 3.0.6. tests/test_promotion_gate.py lines 156-165 assert the same 5 failing checks. That fixture class runs only through the gate's isolated venv (line 90 skipUnless), and I did not re-execute it. This is synthetic evidence of schema-gate behavior, not validation of real market data.

Alternatives:
- Temporal (unqualified) — The packet evidence is only an upstream README URL, with review_status not_individually_reviewed. No local execution receipt exists under blueprints/. Temporal's claimed advantage over Dagu is durable history and in-flight recovery, but no failure, cancellation, in-flight recovery, identity or usage check has been run. The card limitations say start-dev is not production, and default unlimited activity retries are unsafe for broker writes. Temporal is untested, not failed.
- modal (out_of_scope) — Modal is managed cloud compute for elastic Python/GPU jobs. It is not local supervision of owned processes with native identity. `modal run` was not run and may incur charges (card_limitations). The only evidence is a PyPI URL (not_individually_reviewed) that I could not open. It is also unclear whether native subscription credentials belong in cloud containers. Modal is untested, not failed.

Overturn when: Replace Dagu only when a candidate such as Temporal produces a comparable retained receipt under blueprints/us-equities/. It must pass the same checks as blueprints/us-equities/hosting/receipt.json: a failure fixture with the dependent step aborted, cancellation, service restart with history preserved, an environment/identity restriction and zero broker calls. It must also demonstrate in-flight recovery after a process kill, which Dagu has not demonstrated.

Replace pandera if `python3 -m pytest tests/test_promotion_gate.py -rs` fails with the gate's isolated venv present, whether resolved through PROMOTION_GATE_PYTHON or the documented ~/.local/share/codex-ecosystem/tools/promotion-gate-20260922/.venv path, and with zero skips in the FixtureGateRuns class. A run in which FixtureGateRuns is skipped has not exercised pandera and does not count. Also replace pandera if another validator reproduces every named-check outcome on the same blueprints/us-equities/data/fixtures/ inputs, including the fail-closed unmapped_failures result for null-price-cell.csv, and additionally catches a failure the pandera gate misses.

Open gaps:
- In-flight workflow recovery is not established for Dagu. Restart acceptance preserves completed history only (hosting/receipt.json limitations).
- Service-level supervision of workflow runs is not established. systemd supervises only `dagu server`, and there is no scheduler, UI-triggered run or standing model worker (hosting/receipt.json service block and limitations).
- The paired Astra-to-Claude model workflow under Dagu was not executed; native Linux Codex allowance was exhausted (research-runtime/receipt.json paired_model_workflow_executed false). The Claude report ran outside the Dagu graph.
- There is no off-host, continuous or disaster-recovery hosting. A WSL/Windows shutdown stops the service.
- Dagu v2.17.0, the upstream latest, has not been tested.
- Temporal and Modal have no local execution evidence. They are untested, not failed.
- The pandera gate is shown only on synthetic CSV fixtures. No production bars/universe ingest exists (data/README.md), and the duckdb:// input path is source-only.
- Discrepancy: packet card_limitations for c4 say 'fail-closed promotion ... still implementation work', while data/README.md documents a fail-closed promotion gate with 2026-09-22 fixture outputs. The packet card may predate the gate.
- Discrepancy: hosting/receipt.json records basic auth with an anonymous 401 after restart, while hosting/README.md now documents upstream auth.mode none with anonymous API reads returning 200. No receipt I read covers the current auth mode.
- Native session identifiers are not retained in the public receipt. Telemetry correlation is by process instance, timestamp and usage.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-data-quality-orchestration-20260922; codex: -)

#### Evaluation and experiments (evaluation-experiments)

- inspect-ai @ inspect-ai0.3.266; source ec4dfc6953784dc45b79de3147530c89868c6e26 — This selection rests on source review only. No candidate in this layer has retained native execution against the requirement. The winners were chosen because their documented roles fit the requirement, not because any behavior was observed.

c2 (inspect-ai): its recorded role is "Programmable task/solver/scorer evaluations" (catalogs/us-equities/agents-operations.json line 1287). Its us_equities_fit asks for "deterministic checks first" (line 1293), and it is MIT licensed (line 1292). The retained evidence is metadata, not a run. catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json records:
- a pinned README at ec4dfc6953784dc45b79de3147530c89868c6e26 (sha256 a9a1e07b955d869137d8ad109f1c238268f361dcdfac30cfcc94983a51a99b17, 3099 bytes; lines 84 and 86);
- installation_performed=false and model_calls=0 (lines 124-125);
- the missing acceptance, "resumability and bounded failure behavior" (line 122).
The card's commands are prospective. Its eval requires an "explicitly authorized model backend" (agents-operations.json lines 1300-1310).

c1 (data-mlflow): this covers the retained-state half. Its role is "Local experiment runs, parameters, metrics and artifacts" (catalogs/us-equities/data-research.json line 786). It carries an exact source pin, v3.16.1 at 32792afe5b0183fce10532d3a023f5cfa8612d09 (line 789). It is the only mlflow card with a serverless local sqlite workflow (line 801), and that snippet is unexecuted: "No experiments or models were run by this review" (line 807).

This revision changes the mlflow key from c3 to c1. The evidence for c1 is at least as strong: c1 has an exact commit pin and a local, serverless path. c3 has a tag-only pin and a network server command (agents-operations.json lines 1697 and 1709).

Phoenix (c6) is the closest single-component alternative, and it is equally unexecuted. See its alternative entry.
- data-mlflow @ v3.16.1; source 32792afe5b0183fce10532d3a023f5cfa8612d09 — This selection rests on source review only. No candidate in this layer has retained native execution against the requirement. The winners were chosen because their documented roles fit the requirement, not because any behavior was observed.

c2 (inspect-ai): its recorded role is "Programmable task/solver/scorer evaluations" (catalogs/us-equities/agents-operations.json line 1287). Its us_equities_fit asks for "deterministic checks first" (line 1293), and it is MIT licensed (line 1292). The retained evidence is metadata, not a run. catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json records:
- a pinned README at ec4dfc6953784dc45b79de3147530c89868c6e26 (sha256 a9a1e07b955d869137d8ad109f1c238268f361dcdfac30cfcc94983a51a99b17, 3099 bytes; lines 84 and 86);
- installation_performed=false and model_calls=0 (lines 124-125);
- the missing acceptance, "resumability and bounded failure behavior" (line 122).
The card's commands are prospective. Its eval requires an "explicitly authorized model backend" (agents-operations.json lines 1300-1310).

c1 (data-mlflow): this covers the retained-state half. Its role is "Local experiment runs, parameters, metrics and artifacts" (catalogs/us-equities/data-research.json line 786). It carries an exact source pin, v3.16.1 at 32792afe5b0183fce10532d3a023f5cfa8612d09 (line 789). It is the only mlflow card with a serverless local sqlite workflow (line 801), and that snippet is unexecuted: "No experiments or models were run by this review" (line 807).

This revision changes the mlflow key from c3 to c1. The evidence for c1 is at least as strong: c1 has an exact commit pin and a local, serverless path. c3 has a tag-only pin and a network server command (agents-operations.json lines 1697 and 1709).

Phoenix (c6) is the closest single-component alternative, and it is equally unexecuted. See its alternative entry.

Alternatives:
- phoenix (conditional) — Phoenix is the strongest challenger. It is a single component whose card covers both halves of the requirement: its layers are observability and agent-evaluation, and its role is "Local trace inspection and evaluation workspace" (agents-operations.json lines 1241-1245). It is also the only card that names failed attempts: "failed tool calls and usage in versioned evaluation datasets" (line 1251).

On the same criteria as the winners, it has no executed evidence: "Server launch is prospective; no app instrumented and no judge-model calls run" (line 1268). Its evaluation is described in judge-model terms, whereas inspect-ai's card asks for deterministic checks first (line 1293).

It stays conditional rather than winning on two recorded trade-offs, not on observed behavior:
- Licensing: the card says Elastic-2.0 with self-host restrictions (lines 1250 and 1267). The packet's upstream license field is NOASSERTION, so the license identity is unreconciled.
- It would replace two MIT/Apache components with one restricted-license component, before any comparison has been executed.

No-broker-authority is not a distinguishing factor. PHOENIX_ALLOWED_PROVIDERS=NONE is explicitly not an inference authorization boundary (line 1270), but none of the candidates provides that denial either. Only an executed comparison can promote phoenix; see overturn arm (c).
- data-river (out_of_scope) — River's role is "Incremental models, pipelines and progressive validation". It is an online-learning model library, not a harness for evaluating research runs or retaining their state. data-research.json lines 1304-1340 show only an unexecuted snippet. The card warns that "Immediate synthetic labels are not a valid financial online-evaluation assumption" and says delayed fills and returns, late corrections and restart behavior must be modeled.
- foundation-mteb (out_of_scope) — Its role is "Embedding/retrieval evaluation tooling", not evaluation of bounded research runs or retained experiment state. foundation-memory.json lines 1210-1245 mark its commands as prospective and not executed, and its native_workflow is an unpinned `pip install mteb`. The card records version 2.21.0 (line 1218). Upstream staleness comes only from the packet's upstream metadata, which gives pin 2.21.0, pin_behind_upstream true and latest 2.21.6.
- foundation-agent-retrieval-bench (conditional) — This is the only candidate with an executed run on record. blueprints/convergence-practice/arb-trace2code/receipt.json records an unmodified upstream v0.2.1 run (commit b487f3866cc13dd971819cb902517a6a50282404, modified false, status completed). It reports:
- upstream tests "15 passed in 0.15s";
- lexical and BM25 each with evaluated 101, exit_code 0 and skipped {};
- no model or provider calls.
That run was on Darwin arm64 (lines 71 and 73), not on this PC.

A separate receipt, blueprints/convergence-practice/local-fixture/evaluation-receipt.json, is local_integration evidence, not native: a source-authored 24-question fixture, not an external holdout (lines 64 and 69). Its MRR, 0.9666666666666666 for BM25 against 0.9 for lexical, is a macro mean over 20 positive queries (line 44).

Both receipts cover file-level retrieval quality only. Neither evaluates research runs, failed-attempt retention or recoverable experiment state.

Overturn when: The verdict changes when an executed receipt shows one of the following:

(a) inspect-ai 0.3.266 fails the next acceptance recorded at catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json line 123: "One mock-model task with deterministic scoring, bounded concurrency/retries, retained failure log, interruption and resume; no provider request." Retained evidence does not establish that a no-provider model backend exists in the pinned release; that must be observed.

(b) A local sqlite MLflow run cannot read back the parameters, metrics and FAILED status it recorded. This command is this lane's own derived check. It is not the catalog snippet: data-research.json line 801 only logs a param and a metric and prints the tracking URI.
python3 -c "import tempfile, mlflow; d=tempfile.mkdtemp(); mlflow.set_tracking_uri('sqlite:///'+d+'/m.db'); mlflow.set_experiment('x'); r=mlflow.start_run(); mlflow.log_param('k','v'); mlflow.log_metric('m',1); mlflow.end_run(status='FAILED'); g=mlflow.get_run(r.info.run_id); print(g.info.status, dict(g.data.params), dict(g.data.metrics))"
It passes only if the output shows FAILED together with param k=v and metric m=1.

(c) Phoenix arize-phoenix-v20.14.0 alone passes the full check set, in a credential-free environment: deterministic evaluation, failed-attempt retention, parameter and metric readback, interruption and resume, and no provider calls. Phoenix doing this with one component where the winners need two would overturn the verdict.

It would also overturn if any other adopted candidate passes the same checks with fewer components. Record such a result in the same receipt shape as blueprints/convergence-practice/arb-trace2code/receipt.json. That file is a shape template only; it contains no evaluation-experiments task.

Open gaps:
- No frozen evaluation-experiments fixture exists: a Glob for inspect, mlflow and phoenix files under <host-path>/blueprints returned nothing. The only receipts, arb-trace2code and local-fixture, are retrieval evaluations, so overturn_protocol lists no fixture_paths.
- No candidate's evidence covers supervising owned processes, native worker identity, or whether research workers' returned results are complete. These requirement clauses belong to the orchestration and runtime layer.
- No candidate provides denial of broker execution authority to research workers. That has to be enforced in code and environment scoping. This gap applies equally to c1, c2, c3 and c6.
- inspect-ai: no install, eval run, failure-log retention or resume has been observed (installation_performed=false, model_calls=0). The card's eval command requires an explicitly authorized model backend (agents-operations.json line 1306), and no no-provider backend is established.
- inspect-ai release status is unreconciled. The 2026-09-20 releases/latest call returned HTTP 404 (UKGovernmentBEIS__inspect_ai.json lines 35-37), and the card says "repository has no latest GitHub release" (agents-operations.json line 1312). The 2026-09-22 packet instead gives upstream.latest "release/2025-11-28" with pin_behind_upstream false.
- mlflow (c1 and c3): no tracking store, run or failed-run retention has been observed. Neither card mentions failed runs.
- phoenix: no instrumented app, trace retention or evaluation has been observed. The license is Elastic-2.0 on the card but NOASSERTION in the packet's upstream metadata.
- Correction, retained from the previous round: the foundation-agent-retrieval-bench card's limitation "No benchmark download/evaluation performed" (packet c7 card_limitations; foundation-memory.json line 1317) is stale. blueprints/convergence-practice/arb-trace2code/receipt.json records a completed upstream evaluation. That receipt's host is Darwin arm64, so it is not evidence for this PC.
- No measured comparison between any two candidates exists for this layer.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-evaluation-experiments-20260922; codex: -)

#### Execution and broker adapters (execution-broker)

- adaptive-paper-alpaca-adapter @ 7e7eefe28315f3de3aa4dc75cc8b6524f70829cb (blueprints/us-equities/adaptive-paper) — c5 is the only adopted candidate whose retained evidence places a broker-specific Alpaca boundary inside the selected NautilusTrader 2.0.0rc5 LiveNode. It also keeps deterministic numeric risk in code. The evidence is local integration, not broker execution. blueprints/us-equities/adaptive-paper/receipt.json records status "local_integration_passed_new_broker_trial_pending". It pins the engine to 2.0.0rc5 (1b0a49d2792a9432a3aca3fcb617ce7a630d905e) and alpaca-py to 0.44.0 (cc4cb3b7ba50ae250e621983c2779047fb16bb28). It records a frozen numeric execution_contract: capital_usd "10000", gross_exposure_usd "5000", order_notional_usd "1000", loss_and_drawdown_usd "25", and 200/180 request and submission budgets. It also records a SQLite durable intent and fill journal. The receipt's native_capacity run is labelled "wall_clock_local_native_engine_with_synthetic_broker". It made 180 submissions and 90 roundtrips in 60.428166906000115 s, ended flat, and used broker_connections 0 and paper_orders 0. The verification block records 895 tests run, 893 passed and 2 skipped. It also records 42 unchanged upstream Nautilus adapter-template tests passed, labelled "not Alpaca broker E2E". broker_readiness is "not_started" (regular_session_window_unavailable), so c5 has never sent a broker order. c4 (alpaca-py 0.44.0) is the SDK beneath c5 and is the only adopted candidate with observed actual paper orders. blueprints/us-equities/paper-e2e-20260921/paper-receipt.json (evidence_kind "native_alpaca_paper") records 2 filled SPY orders, write_attempts 2 and realized_gross_pnl_usd "-0.08". It also records a separate fresh reconciliation (positions 0, open_orders 0, cash delta matching PnL) and a completed-trial recovery with additional_writes 0. That trial ran through a different deterministic runner (blueprints/us-equities/alpaca-paper/paper_runner.py), not c5's Nautilus adapter. blueprints/us-equities/order-contract/README.md records the observed native SDK serialization behavior, which is local and offline. In that run, float qty and limit_price fields were used and advanced_instructions was dropped. A local boundary must therefore guard the SDK. catalogs/us-equities/runtime-target.json names both as the selected Alpaca path. Its broker-state-failures status is "bounded_alpaca_synthetic_cases_passed_native_faults_pending".
- alpaca-py @ 0.44.0 — c5 is the only adopted candidate whose retained evidence places a broker-specific Alpaca boundary inside the selected NautilusTrader 2.0.0rc5 LiveNode. It also keeps deterministic numeric risk in code. The evidence is local integration, not broker execution. blueprints/us-equities/adaptive-paper/receipt.json records status "local_integration_passed_new_broker_trial_pending". It pins the engine to 2.0.0rc5 (1b0a49d2792a9432a3aca3fcb617ce7a630d905e) and alpaca-py to 0.44.0 (cc4cb3b7ba50ae250e621983c2779047fb16bb28). It records a frozen numeric execution_contract: capital_usd "10000", gross_exposure_usd "5000", order_notional_usd "1000", loss_and_drawdown_usd "25", and 200/180 request and submission budgets. It also records a SQLite durable intent and fill journal. The receipt's native_capacity run is labelled "wall_clock_local_native_engine_with_synthetic_broker". It made 180 submissions and 90 roundtrips in 60.428166906000115 s, ended flat, and used broker_connections 0 and paper_orders 0. The verification block records 895 tests run, 893 passed and 2 skipped. It also records 42 unchanged upstream Nautilus adapter-template tests passed, labelled "not Alpaca broker E2E". broker_readiness is "not_started" (regular_session_window_unavailable), so c5 has never sent a broker order. c4 (alpaca-py 0.44.0) is the SDK beneath c5 and is the only adopted candidate with observed actual paper orders. blueprints/us-equities/paper-e2e-20260921/paper-receipt.json (evidence_kind "native_alpaca_paper") records 2 filled SPY orders, write_attempts 2 and realized_gross_pnl_usd "-0.08". It also records a separate fresh reconciliation (positions 0, open_orders 0, cash delta matching PnL) and a completed-trial recovery with additional_writes 0. That trial ran through a different deterministic runner (blueprints/us-equities/alpaca-paper/paper_runner.py), not c5's Nautilus adapter. blueprints/us-equities/order-contract/README.md records the observed native SDK serialization behavior, which is local and offline. In that run, float qty and limit_price fields were used and advanced_instructions was dropped. A local boundary must therefore guard the SDK. catalogs/us-equities/runtime-target.json names both as the selected Alpaca path. Its broker-state-failures status is "bounded_alpaca_synthetic_cases_passed_native_faults_pending".

Alternatives:
- NautilusTrader (native IBKR socket adapter) (conditional) — This is the selected live-primary broker boundary on the selected engine, but its only packet evidence is the upstream integration doc URL, which is source review and was not opened. catalogs/us-equities/runtime-target.json broker_boundaries[ibkr] records local_broker_acceptance "not_established". It also states that adapter installation does not establish socket access, paper order behavior, cancellation races or reconnect reconciliation. No IBKR paper or live session is retained. c7 becomes a winner once a signed-in paper TWS/Gateway session passes the ownership, reconciliation and partial/cancel/reconnect cases. The engine itself is shared with c5 and is not in question here.
- LEAN Alpaca brokerage (out_of_scope) — The requirement keeps LEAN as the prior oracle, not as the execution destination. blueprints/us-equities/engine/resolution-receipt.json records native builds, not execution. The unmodified adapter build had exit 0 but still resolved 2 advisory pairs. The source-integrated build had exit 0 and 0 advisory pairs. The unchanged bundled backtest completed with brokerage_model "Unchanged upstream default; not Alpaca". remaining_external_boundary is "not_exercised_requires_operator_entitlement_and_broker_authorization", with broker_orders_submitted 0. Initialization, product 347 entitlement, connectivity and reconciliation were never exercised. The native_proven class covers compilation and advisory audits only, not broker execution.
- hkuds/vibe-trading (unqualified) — The candidate is not adopted and has no retained evidence (evidence_refs empty, evidence_kind null). The packet note describes only a prospective comparison, in which its sdk_order_gate.py and reconciliation would have to pass the existing 27 local Alpaca lifecycle cases with fewer failures than the current deterministic adapter. That comparison has not been executed, so its capability is untested, not failed.
- pydantic/pydantic (unqualified) — The candidate is not adopted and has no retained evidence (evidence_refs empty). The packet note proposes a strict typed order-intent schema, but no fixture shows it rejecting intents that the current checks accept. blueprints/us-equities/order-contract/README.md already records a hand-written fail-closed boundary (unknown fields, duplicate keys, floats, exponent notation and oversized input rejected). Nine focused tests passed for that boundary. Any advantage would have to be demonstrated.

Overturn when: Reopen the verdict if either of the following happens, on the same frozen config and failure contract. (1) The first open-session c5 paper trial (python runner.py paper, recorded in blueprints/us-equities/adaptive-paper/receipt.json broker_readiness) fails ownership, reconciliation or durable-ledger recovery. (2) An alternative gate passes more of the lifecycle cases in tests/test_alpaca_paper.py and tests/test_adaptive_paper_safety.py / tests/test_adaptive_paper_recovery.py than the current adapter; candidates include c2's sdk_order_gate or a c3 strict-schema boundary run against tests/test_order_contract.py. c7 is promoted once a paper IBKR session records local_broker_acceptance other than not_established in catalogs/us-equities/runtime-target.json.

Open gaps:
- The c5 adaptive adapter has not submitted a single broker order. broker_readiness is not_started (regular_session_window_unavailable), and native_capacity used a synthetic broker with 0 broker connections.
- The only actual paper orders (2 SPY fills, -0.08 USD) went through blueprints/us-equities/alpaca-paper/paper_runner.py, not the Nautilus-integrated c5 adapter. Those orders prove nothing about c5.
- Native in-flight faults (partial fill, crash, stream loss, ambiguous POST under outage) remain unqualified. completed_trial_recovery explicitly did not inject a broker outage or process crash.
- IBKR (c7) is unaccepted: no paper or live session, socket access, cancellation race or reconnect reconciliation was observed.
- SPY/LEAN dividend-cash parity is blocked. runtime-target next_acceptance retained-equity-replay reports 4 failed checks, so the LEAN oracle comparison is not accepted.
- Historical-to-paper signal parity, continuous operation, Elite 1000/min throughput and fractional residual recovery under native faults are unqualified.
- The alpaca-py SDK serializes qty and limit_price as floats and drops advanced_instructions (order-contract README). Exact decimal wire preservation is not established.
- No causal cost-aware strategy qualification or profitability follows from any receipt.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-execution-broker-20260922; codex: -)

#### Identity, provenance and lineage (identity-provenance)

- data-dvc @ 3.67.1; source 356dfa03278058b02df42124f243c2c345329dae — I selected c2 (DVC) from source review only. Nothing was executed. Among the eight packet candidates (all adopted: true), DVC's content-addressed, Git-linked snapshot pinning comes closest to the "exact reproducible analytical snapshots" part of the requirement. The retained entry at catalogs/us-equities/data-research.json lines 692-736 describes it as "Pins exact raw/curated snapshots and preprocessing dependencies" (line 704). Its evidence_level is "source_review" (line 706). Its native_workflow (dvc init / dvc add / dvc status) is labelled "Prospective and UNEXECUTED" (line 711). DVC cannot meet the layer requirement on its own. Its retained requirements say the "Snapshot must already include source contract, universe, adjustment and knowledge-cutoff metadata" (line 721). Its limitation says "Content hashes prove identity, not data validity or point-in-time correctness" (line 724). So DVC depends on an upstream snapshot producer and would add to it, not replace it. It does not cover licensed acquisition, feed/timestamp preservation, corporate actions or rejecting data whose availability is unknown. That producer-side behaviour is observed only in project code built on DuckDB, which is not a packet candidate. blueprints/us-equities/point-in-time/receipt.json is a native_cli_e2e run of temporal_snapshot.py on DuckDB 1.5.5 over synthetic data. Late corrections were excluded before availability (line 122). missing_availability was rejected with row_schema_mismatch, exit_code 2 (lines 105-107, 309). Corruption was rejected with snapshot_artifact_hash_mismatch (lines 113-115). entitlement_verified is false (lines 27 and 125). Rejection of empty snapshots comes from the Pandera/exchange_calendars gate, not from any candidate: blueprints/us-equities/data/fixtures/empty-snapshot-gate-result.json has status "fail" with row_count 0. c4 is the only packet candidate with native evidence, and that evidence is for code retrieval, not market-data provenance.

Alternatives:
- cosign (conditional) — cosign signs and verifies the identity of artifacts such as software or blobs. It does not version or identify market observations, feeds, timestamps or corporate actions. The packet records review_status not_individually_reviewed (packet line 23), and the card says no signing or identity flow was started. Nothing local exercises it. It could later sign snapshot manifests, but no evidence shows that done.
- data-kafka (out_of_scope) — Kafka is a durable partitioned event log for ingestion and fan-out. It does not produce exact analytical snapshots or security identity. The card itself limits ordering to partition-local and says it gives no exactly-once guarantee for external sinks. The packet records upstream latest as "show" and released_at null, so release metadata is unresolved. This is source review only; nothing was executed.
- foundation-socraticode (out_of_scope) — The native evidence is real but covers a different capability. evidence/receipts/native-rag.json records both clients retrieving project code through SocratiCode, and evidence/receipts/desktop-direct-rag.json records direct code retrieval. That is code retrieval. It is not source-identifiable US-equity observations, feed/timestamp preservation or reproducible data snapshots. evidence/receipts/vllm-compatibility.json records a host-specific vLLM 0.29.0 GPU startup failure, with retrieval restored on 0.25.0.
- data-openlineage (conditional) — OpenLineage is a lineage-event standard and client. Its retained limitation says it "is not a persistent lineage server, scheduler or dataset version store" (catalogs/us-equities/data-research.json, OpenLineage entry lines 819-859), so it cannot produce exact snapshots alone. The architecture blueprint (blueprints/us-equities/architecture/README.md line 49) limits OpenLineage to "demonstrated transformation/lineage needs". Its example only prints a Dataset object, is labelled UNEXECUTED and was not observed. The catalog rationale at line 827, which the packet withholds, was also read; see limits.
- data-arcticdb (conditional) — ArcticDB offers versioned dataframe storage, but the packet records its license as NOASSERTION. The card says the pinned release is BSL-1.1 and that production and business rights must be resolved with the licensor. The card also says "Storage version time is not proof of market information availability". It was not individually reviewed (packet line 185), and nothing local exercises it.
- data-mlflow (conditional) — MLflow tracks experiment runs, parameters and metrics. It does not own dataset identity or snapshots. The retained entry says "No experiments or models were run by this review" and that autologging "does not capture every data revision" (catalogs/us-equities/data-research.json lines 780-817). It could link runs to DVC snapshots downstream, but that link has not been exercised.
- data-iceberg (conditional) — Iceberg table snapshots could pin contents. The card says catalog creation alone would not prove append, conflict handling or time travel. It also says storage snapshots do not imply past information availability. Nothing was executed locally, and it was not individually reviewed (packet line 247). The catalog rationale at catalogs/us-equities/data-research.json line 869, which the packet withholds, calls it "unnecessary for the first local Parquet snapshots". That rationale was read but is not the basis of this disposition; see limits.

Overturn when: This verdict changes only after an executed comparison on the retained synthetic point-in-time fixture. The metric cannot be reproduction of the receipt's snapshot_sha256 (961135fd9b40a412dd96a9b100b512823eae1c74ba102393712d69c7469013e3). temporal_snapshot.py writes "ingested_at": SEC.utc_now() into the manifest (line 135) and then hashes that manifest (line 144). sec_data.py utc_now (lines 50-51) returns wall-clock time to the microsecond, so every materialization produces a new manifest digest. Also, the receipt's snapshot was written to $PRIVATE_RUN/snapshot (receipt.json lines 135-143), which is not retained in the repository. Use source_sha256 f5d0ebf62889db580fdfd5e2f774c1ada9d01434dcba904019247f23f8ac2f3a instead. It is the sha256 of source.json, a byte copy of fixture.json (temporal_snapshot.py lines 124 and 144), so it should be reproducible from blueprints/us-equities/point-in-time/fixture.json. Also use the per-file sha256 values in the manifest. Whether the DuckDB Parquet output is byte-deterministic has not been verified. Run each arm over the same materialized snapshot directory. The verdict changes in three cases: DVC fails to detect a single-byte change or fails to restore the same per-file bytes after checkout; another candidate reproduces them with fewer steps; or the temporal_snapshot.py manifest alone proves sufficient, making DVC redundant. The existing checks must still pass: python3 -m unittest tests.test_point_in_time tests.test_security_identity tests.test_lifecycle_sample.

Open gaps:
- lane claude prefers non-adopted data-duckdb via blueprints/us-equities/point-in-time/temporal_snapshot.py (project code; not a packet candidate) (https://github.com/duckdb/duckdb): requires Run python3 -m unittest tests.test_point_in_time; the file loads temporal_snapshot.py at line 11 and covers missing availability (line 59), corruption and wrong manifest hash (line 108) and no-overwrite (line 124). Then run the overturn_protocol arms on blueprints/us-equities/point-in-time/fixture.json. Compare source_sha256 and per-file sha256 reproduction, single-byte change detection and rejection of unknown availability for DVC-over-snapshot against the temporal_snapshot.py manifest alone. The test outcome is currently unknown; this lane ran nothing.
- No packet candidate acquires licensed, source-identifiable US-equity observations. Acquisition, feed/timestamp preservation and corporate-action handling fall outside every candidate's evidence.
- DVC has not been executed in this repository. Its native_workflow is labelled Prospective and UNEXECUTED (catalogs/us-equities/data-research.json lines 710-718).
- DVC requires the snapshot to already carry source contract, universe, adjustment and knowledge-cutoff metadata (line 721). Its content hashes prove identity, not validity or point-in-time correctness (line 724). Rejecting unknown availability depends on project code (temporal_snapshot.py), and the only native evidence for that code is synthetic (receipt.json: entitlement_verified false, availability_evidence_authenticated false).
- The manifest-level snapshot_sha256 cannot be reproduced across materializations because it embeds ingested_at (temporal_snapshot.py line 135). The materialized snapshot from the receipt run is not retained in the repository. The receipt says the trusted manifest digest must be retained independently (receipt.json line 15).
- It is unverified whether DuckDB write_parquet output (zstd, ordered by row_id) is byte-identical across runs. This determines whether per-file hashes can serve as a cross-run reproducibility metric.
- The packet limitations still apply. The Alpaca receipt covers 25 AAPL daily bars and two corporate actions only. Dividend currency is missing, so cash units cannot be reconciled. The three lifecycle cases do not establish historical as-known eligibility or permanent security identity.
- Nothing compares the snapshot options by measurement: DVC, Iceberg, ArcticDB and the plain temporal_snapshot.py manifest.
- The data-kafka upstream release metadata is unresolved (latest "show", released_at null).
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-identity-provenance-20260922; codex: -)

#### Market data and reference (market-data-reference)

- data-alpaca-py @ v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28 — This revision adds c9 to the winner set. The packet lists only c9's README (packet lines 244-247), but the repository retains native receipts for it. Between them, c6, c9 and c13 cover every requirement clause that has native evidence. Each clause remains bounded to a sample.

c9 alpaca-py:
- blueprints/us-equities/authenticated-data/native-receipt.json (kind native_cli_e2e, observed 2026-09-20T01:09:45Z) records a native Alpaca-py 0.44.0 GET run through collect.py collect (exit_code 0).
- It acquired 25 AAPL SIP/raw daily bars over 3 pages and 2 corporate actions over 2 pages. All 5 pages returned HTTP 200, each with its own sha256, and terminal pagination was observed on both stages.
- compare.py (exit_code 0) found 25/25 raw closes equal to the frozen LEAN probe, with maximum difference 0.00. Both numeric action values were equal, and 1 dividend currency is unknown (actions status reconciliation_incomplete).
- blueprints/us-equities/identity-readiness/native-receipt.json (native_cli_e2e, alpaca-py 0.44.0 plus DuckDB 1.5.5) retained 10 FB/META query observations over 8 HTTP 200 responses: 9 qualified and 1 quarantined. The original capture exited 1 (meta_unmapped invalid_numeric_field), and that failure is preserved.
- The mapped FB/META alias comparison shows 3 equal rows and 0 field mismatches.
- ledger.py materialize (exit 0) wrote DuckDB Parquet with exact BIGINT observation eligibility. ledger.py select for meta_mapped returned count 0 at cutoff 2022-06-11T00:00:00Z, count 0 at 2026-09-20T01:42:36.567740474Z, and count 2 one nanosecond later. Each selection carries a selected_rows_sha256.
- This is the only retained native evidence for price observations, feed (SIP/raw), identity aliasing and corporate actions, and it rejects rows before observation.

c6 EdgarTools:
- blueprints/us-equities/catalyst-provenance/access-resolution.json records native edgartools 5.58.0 get_filings: exit_code 0, http_status 200, cohort_rows 371, unique_accessions 360, 8-K 362 / 8-K/A 9. The source is 5079824 bytes, its sha256 is recorded and gzip validation passed.
- The historical packet at as_of 2020-03-03T00:00:00Z had eligible_count 0 (before_first_availability 5). The observed packet qualified 5.
- The earlier HTTP 403 in catalyst-provenance/receipt.json remains a dated failure.

c13 exchange_calendars:
- blueprints/us-equities/data/receipt.json is a native run of data/summarize_backtest.py, which calls get_calendar('XNYS'). It produced session open 2013-10-07T13:30:00+00:00 and close 20:00:00+00:00, plus source and parquet sha256 values.
- historical-simulation/receipt.json shows expected_xnys_sessions 104 against daily_rows_in_window 104, with no missing or extra dates.

Boundary: in all three, the eligibility gate is project code (catalyst.py, security-identity/ledger.py), not an upstream SDK feature. Both receipts also say original historical availability is not established.
- data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a — This revision adds c9 to the winner set. The packet lists only c9's README (packet lines 244-247), but the repository retains native receipts for it. Between them, c6, c9 and c13 cover every requirement clause that has native evidence. Each clause remains bounded to a sample.

c9 alpaca-py:
- blueprints/us-equities/authenticated-data/native-receipt.json (kind native_cli_e2e, observed 2026-09-20T01:09:45Z) records a native Alpaca-py 0.44.0 GET run through collect.py collect (exit_code 0).
- It acquired 25 AAPL SIP/raw daily bars over 3 pages and 2 corporate actions over 2 pages. All 5 pages returned HTTP 200, each with its own sha256, and terminal pagination was observed on both stages.
- compare.py (exit_code 0) found 25/25 raw closes equal to the frozen LEAN probe, with maximum difference 0.00. Both numeric action values were equal, and 1 dividend currency is unknown (actions status reconciliation_incomplete).
- blueprints/us-equities/identity-readiness/native-receipt.json (native_cli_e2e, alpaca-py 0.44.0 plus DuckDB 1.5.5) retained 10 FB/META query observations over 8 HTTP 200 responses: 9 qualified and 1 quarantined. The original capture exited 1 (meta_unmapped invalid_numeric_field), and that failure is preserved.
- The mapped FB/META alias comparison shows 3 equal rows and 0 field mismatches.
- ledger.py materialize (exit 0) wrote DuckDB Parquet with exact BIGINT observation eligibility. ledger.py select for meta_mapped returned count 0 at cutoff 2022-06-11T00:00:00Z, count 0 at 2026-09-20T01:42:36.567740474Z, and count 2 one nanosecond later. Each selection carries a selected_rows_sha256.
- This is the only retained native evidence for price observations, feed (SIP/raw), identity aliasing and corporate actions, and it rejects rows before observation.

c6 EdgarTools:
- blueprints/us-equities/catalyst-provenance/access-resolution.json records native edgartools 5.58.0 get_filings: exit_code 0, http_status 200, cohort_rows 371, unique_accessions 360, 8-K 362 / 8-K/A 9. The source is 5079824 bytes, its sha256 is recorded and gzip validation passed.
- The historical packet at as_of 2020-03-03T00:00:00Z had eligible_count 0 (before_first_availability 5). The observed packet qualified 5.
- The earlier HTTP 403 in catalyst-provenance/receipt.json remains a dated failure.

c13 exchange_calendars:
- blueprints/us-equities/data/receipt.json is a native run of data/summarize_backtest.py, which calls get_calendar('XNYS'). It produced session open 2013-10-07T13:30:00+00:00 and close 20:00:00+00:00, plus source and parquet sha256 values.
- historical-simulation/receipt.json shows expected_xnys_sessions 104 against daily_rows_in_window 104, with no missing or extra dates.

Boundary: in all three, the eligibility gate is project code (catalyst.py, security-identity/ledger.py), not an upstream SDK feature. Both receipts also say original historical availability is not established.
- data-exchange-calendars @ 4.13.2; source dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a — This revision adds c9 to the winner set. The packet lists only c9's README (packet lines 244-247), but the repository retains native receipts for it. Between them, c6, c9 and c13 cover every requirement clause that has native evidence. Each clause remains bounded to a sample.

c9 alpaca-py:
- blueprints/us-equities/authenticated-data/native-receipt.json (kind native_cli_e2e, observed 2026-09-20T01:09:45Z) records a native Alpaca-py 0.44.0 GET run through collect.py collect (exit_code 0).
- It acquired 25 AAPL SIP/raw daily bars over 3 pages and 2 corporate actions over 2 pages. All 5 pages returned HTTP 200, each with its own sha256, and terminal pagination was observed on both stages.
- compare.py (exit_code 0) found 25/25 raw closes equal to the frozen LEAN probe, with maximum difference 0.00. Both numeric action values were equal, and 1 dividend currency is unknown (actions status reconciliation_incomplete).
- blueprints/us-equities/identity-readiness/native-receipt.json (native_cli_e2e, alpaca-py 0.44.0 plus DuckDB 1.5.5) retained 10 FB/META query observations over 8 HTTP 200 responses: 9 qualified and 1 quarantined. The original capture exited 1 (meta_unmapped invalid_numeric_field), and that failure is preserved.
- The mapped FB/META alias comparison shows 3 equal rows and 0 field mismatches.
- ledger.py materialize (exit 0) wrote DuckDB Parquet with exact BIGINT observation eligibility. ledger.py select for meta_mapped returned count 0 at cutoff 2022-06-11T00:00:00Z, count 0 at 2026-09-20T01:42:36.567740474Z, and count 2 one nanosecond later. Each selection carries a selected_rows_sha256.
- This is the only retained native evidence for price observations, feed (SIP/raw), identity aliasing and corporate actions, and it rejects rows before observation.

c6 EdgarTools:
- blueprints/us-equities/catalyst-provenance/access-resolution.json records native edgartools 5.58.0 get_filings: exit_code 0, http_status 200, cohort_rows 371, unique_accessions 360, 8-K 362 / 8-K/A 9. The source is 5079824 bytes, its sha256 is recorded and gzip validation passed.
- The historical packet at as_of 2020-03-03T00:00:00Z had eligible_count 0 (before_first_availability 5). The observed packet qualified 5.
- The earlier HTTP 403 in catalyst-provenance/receipt.json remains a dated failure.

c13 exchange_calendars:
- blueprints/us-equities/data/receipt.json is a native run of data/summarize_backtest.py, which calls get_calendar('XNYS'). It produced session open 2013-10-07T13:30:00+00:00 and close 20:00:00+00:00, plus source and parquet sha256 values.
- historical-simulation/receipt.json shows expected_xnys_sessions 104 against daily_rows_in_window 104, with no missing or extra dates.

Boundary: in all three, the eligibility gate is project code (catalyst.py, security-identity/ledger.py), not an upstream SDK feature. Both receipts also say original historical availability is not established.

Alternatives:
- Databento (conditional) — The only evidence is the README (source review). No acquisition, entitlement or cost receipt is retained. The card lists three limits: an exchange-specific feed is not consolidated US coverage, a late adjustment factor can leak into earlier decisions, and corporate-action redistribution is contract-restricted. It is the natural comparison arm against c9 for consolidated history and delistings, but it is unexecuted.
- Massive Python client (unqualified) — The only evidence is the README; no request was executed. The card says the free-tier terms do not grant commercial use or redistribution, and inactive/date ticker filters do not prove a survivorship-free universe. It overlaps c9, which has retained native bar and corporate-action acquisition.
- data-fredapi (out_of_scope) — It supplies macro series and vintages, not US-equity observations. The only evidence is the README, and the card says no data request was run. The last release was 2024-05-05 and review_status is unmaintained_signal. A vintage date lacks an intraday availability time.
- data-gdeltdoc (out_of_scope) — It is a news-coverage client, not an equity market-data or reference source. The only evidence is the README, and review_status is unmaintained_signal. The card says GDELT first-seen time is not publication or tradable-availability time.
- data-feast (out_of_scope) — It is a feature store for downstream retrieval, not an acquisition or reference source. The only evidence is the README. The card says event-time point-in-time retrieval does not exclude late corrections. The retained as-of gates are project DuckDB and Python code (security-identity/ledger.py, catalyst.py).
- data-dlt (unqualified) — It is a generic extraction/loading pipeline with no retained run. The card says schema inference is not a financial data-quality contract, and watermark-only extraction can miss late revisions. The retained acquisitions use project adapters with hashed private pages; no comparison against dlt was executed.
- data-kafka (out_of_scope) — It is event-log transport, not a data source. The only evidence is the README. The packet's existing_overturn_when says to add a server only after local throughput/concurrency measurements justify it, and none is retained.
- QuestDB (unqualified) — The card says no server was installed or started, and dedup/upsert can overwrite corrections. The retained snapshot path is DuckDB/Parquet with sha256 hashes (data/summarize_backtest.py; identity-readiness ledger materialize). No throughput measurement justifies a server.
- atilaahmettaner/tradingview-mcp (unqualified) — It is not adopted and has no evidence_refs. The packet's entry conditions are documented data rights and an as-of query reconciled against Alpaca news timestamps. Neither is shown as met.

Overturn when: Four checks could change this verdict.

1. A retained blueprints/us-equities/ receipt shows c14 Databento (or another feed) acquiring consolidated bars and corporate actions for the same representative securities with raw-page sha256 hashes. The securities must include a delisting, the FB/META alias case and an AAPL split/dividend with a known currency. The rows must pass the same cutoff gate (security-identity/ledger.py select returns count 0 before observation) and close c9's open gaps: delisting, dividend currency and action coverage. That would replace or join c9. The reverse also counts: a rerun of blueprints/us-equities/alpaca-historical/collect.py verify or authenticated-data/compare.py that no longer reproduces 25/25 equal closes or the recorded page sha256 values would demote c9.
2. Rerunning `python3 -m unittest tests.test_security_identity tests.test_alpaca_historical tests.test_catalyst_provenance` could fail. Separately, the private-run commands recorded in the receipts could fail to reproduce their recorded results. For ledger.py select, those are counts 0/0/2 and their selected_rows_sha256 values. For catalyst.py packet --as-of 2020-03-03T00:00:00Z, the result is before_first_availability 5. Either outcome would demote c9 or c6. These reruns need host-private $ACQUISITION_RUN/$IDENTITY_LEDGER artifacts; the unit tests alone use offline fixtures.
3. summarize_backtest.py hardcodes session 2013-10-07 (line 30), so it cannot test new dates. The runnable c13 check is `python3 -c "import exchange_calendars as x; c=x.get_calendar('XNYS'); [print(d, c.is_session(d), c.session_close(d) if c.is_session(d) else None) for d in ('2013-07-04','2013-11-29','2013-12-24')]"` under exchange-calendars 4.13.2. Its output would be compared with the NYSE-published 2013 holiday and early-close schedule. A mismatch would demote c13.
4. The comparison in the packet's existing_overturn_when is still unexecuted. Once run, it should replace this sample-bounded verdict.

Open gaps:
- Original historical availability is not established for any winner. The authenticated-data receipt records original_historical_availability not_established (line 107). The identity-readiness receipt records provider_revision_availability_established false and historical_delisting_established false (lines 449, 467). All five SEC events qualify only as of the 2026-09-19 local observation. The cutoff gates reject rows only before local observation; they do not reconstruct as-known history.
- The c9 coverage is small: one retrospective AAPL sample of 25 sessions (2020-08-03 to 2020-09-04) and 2 corporate actions, plus FB/META over 3 sessions in 2022-06. There is no survivorship-free universe and no delisting case, and action coverage is incomplete. The process-date window may omit events (authenticated-data receipt line 129).
- The dividend currency is unknown for 1 action, so corporate actions are not fully reconciled to cash units (authenticated-data receipt lines 119-128). Corporate actions were not routed through the ledger.py cutoff gate; only bars were.
- One meta_unmapped row is quarantined (documentation_discrepancy_rows 1), and the original capture exited 1 with invalid_numeric_field (identity-readiness receipt lines 10-13, 429-446).
- The temporal gates are project code (catalyst.py, security-identity/ledger.py), not upstream SDK capabilities. Transport also uses pinned private _session/_retry seams (authenticated-data receipt lines 215-218).
- The c13 evidence covers one hardcoded XNYS session (summarize_backtest.py line 30) and a 104-session date check that does not prove row or market coverage. Holidays, early closes, halts and extended hours are untested. The 4.13.2 version is inferred from requirements.txt and stack.json; data/receipt.json does not record it.
- Licensing and redistribution rights for the Alpaca SIP data are not established. The historical SIP response does not establish real-time access or entitlements (authenticated-data receipt line 223).
- EdgarTools dependencies are version-pinned, not wheel-hash-locked, and a new host needs its own native acceptance.
- codex lane absent for this layer
- unindexed alternative sec-api-io/sec-api-python https://github.com/SEC-API-io/sec-api-python
- unindexed alternative rossod4/quantlab https://github.com/Rossod4/quantlab

Lanes: codex_absent (claude: us-equities-market-data-reference-20260922; codex: -)

#### Observability and hosting (observability-hosting)

- opentelemetry-collector-contrib @ v0.161.0 — The requirement is retained, scoped telemetry for bounded native research runs, including failed attempts and recoverable state. c14 (otelcol-contrib), c5 (Prometheus) and c6 (Loki) have the most direct retained native-execution evidence for it. All of that evidence is retained records dated 2026-09-19; none was observed now. In observability/receipt.json (kind native_cli_e2e), `otelcol-contrib validate` exited 0 and upstream_checksum_matches is true. Native Codex 0.155.1 and Claude 2.1.278 each completed the fixtures/observability-check.json task (sum 42, service_count 4). The receipt records collected_turn_histogram_matches_native_usage true for Codex and collected_request_logs_and_metrics_match true for Claude (lines 163-202). For Prometheus, the `up` query returned "1" for seven targets (lines 109-119), and the privacy canary's retained values were ["7","7"] (lines 130-138). For Loki, a LogQL query taking the max per receipt_id returned total_tokens 80770 (lines 121-127). sdk_receipt_lane (lines 246-254) records after_collector_restart_total_tokens 80770 and unknown usage kept as None/absent rather than coerced to zero. Qualifier: the 80770 figure comes from metadata summaries of two earlier SDK receipts (40187 + 40583, lines 206-224), republished through write_observation. They were not new model calls. Separately, observability/backends/receipt.json records a synthetic-fixture run of observability/backends/check_persistence.py. It restarted only the five backend units (restart_exit_code 0), and afterwards the Prometheus historical sample and the Loki fixture log were still present. It also records every listener bound to 127.0.0.1 and archive_sha256_verified true. Qualifier on failed attempts: the four retained_failed_attempts (lines 370-375) are prose notes about acceptance-harness failures. They are not failed research-worker runs retained in Loki or Prometheus. Keeping a status 'failed' observation with usage None is shown only by an offline temp-directory test (tests/test_observability.py lines 32-54). This is native execution on one WSL host plus a synthetic persistence fixture, not a measured comparison against the alternatives.
- prometheus @ v3.14.0 — The requirement is retained, scoped telemetry for bounded native research runs, including failed attempts and recoverable state. c14 (otelcol-contrib), c5 (Prometheus) and c6 (Loki) have the most direct retained native-execution evidence for it. All of that evidence is retained records dated 2026-09-19; none was observed now. In observability/receipt.json (kind native_cli_e2e), `otelcol-contrib validate` exited 0 and upstream_checksum_matches is true. Native Codex 0.155.1 and Claude 2.1.278 each completed the fixtures/observability-check.json task (sum 42, service_count 4). The receipt records collected_turn_histogram_matches_native_usage true for Codex and collected_request_logs_and_metrics_match true for Claude (lines 163-202). For Prometheus, the `up` query returned "1" for seven targets (lines 109-119), and the privacy canary's retained values were ["7","7"] (lines 130-138). For Loki, a LogQL query taking the max per receipt_id returned total_tokens 80770 (lines 121-127). sdk_receipt_lane (lines 246-254) records after_collector_restart_total_tokens 80770 and unknown usage kept as None/absent rather than coerced to zero. Qualifier: the 80770 figure comes from metadata summaries of two earlier SDK receipts (40187 + 40583, lines 206-224), republished through write_observation. They were not new model calls. Separately, observability/backends/receipt.json records a synthetic-fixture run of observability/backends/check_persistence.py. It restarted only the five backend units (restart_exit_code 0), and afterwards the Prometheus historical sample and the Loki fixture log were still present. It also records every listener bound to 127.0.0.1 and archive_sha256_verified true. Qualifier on failed attempts: the four retained_failed_attempts (lines 370-375) are prose notes about acceptance-harness failures. They are not failed research-worker runs retained in Loki or Prometheus. Keeping a status 'failed' observation with usage None is shown only by an offline temp-directory test (tests/test_observability.py lines 32-54). This is native execution on one WSL host plus a synthetic persistence fixture, not a measured comparison against the alternatives.
- loki @ v3.7.8 — The requirement is retained, scoped telemetry for bounded native research runs, including failed attempts and recoverable state. c14 (otelcol-contrib), c5 (Prometheus) and c6 (Loki) have the most direct retained native-execution evidence for it. All of that evidence is retained records dated 2026-09-19; none was observed now. In observability/receipt.json (kind native_cli_e2e), `otelcol-contrib validate` exited 0 and upstream_checksum_matches is true. Native Codex 0.155.1 and Claude 2.1.278 each completed the fixtures/observability-check.json task (sum 42, service_count 4). The receipt records collected_turn_histogram_matches_native_usage true for Codex and collected_request_logs_and_metrics_match true for Claude (lines 163-202). For Prometheus, the `up` query returned "1" for seven targets (lines 109-119), and the privacy canary's retained values were ["7","7"] (lines 130-138). For Loki, a LogQL query taking the max per receipt_id returned total_tokens 80770 (lines 121-127). sdk_receipt_lane (lines 246-254) records after_collector_restart_total_tokens 80770 and unknown usage kept as None/absent rather than coerced to zero. Qualifier: the 80770 figure comes from metadata summaries of two earlier SDK receipts (40187 + 40583, lines 206-224), republished through write_observation. They were not new model calls. Separately, observability/backends/receipt.json records a synthetic-fixture run of observability/backends/check_persistence.py. It restarted only the five backend units (restart_exit_code 0), and afterwards the Prometheus historical sample and the Loki fixture log were still present. It also records every listener bound to 127.0.0.1 and archive_sha256_verified true. Qualifier on failed attempts: the four retained_failed_attempts (lines 370-375) are prose notes about acceptance-harness failures. They are not failed research-worker runs retained in Loki or Prometheus. Keeping a status 'failed' observation with usage None is shown only by an offline temp-directory test (tests/test_observability.py lines 32-54). This is native execution on one WSL host plus a synthetic persistence fixture, not a measured comparison against the alternatives.

Alternatives:
- Grafana (overlap) — Observed natively. Readiness returned HTTP 200, and the provisioned dashboard and datasources survived a backend restart (observability/backends/receipt.json persistence checks; check_persistence.py lines 75-76). The dashboard render predates the SDK receipt panel. Grafana only visualizes data that Prometheus and Loki already retain, so it adds no retention or identity capability. The packaged build commit differs from the tag commit (grafana_tag_build_commit_equal false). It is supporting, not a core winner.
- alertmanager (overlap) — `amtool check-config` exited 0. A firing and a resolved notification went through the local webhook route to ntfy, and a silence persisted across a backend restart (observability/backends/receipt.json). external_delivery_tested is false (observability/receipt.json). It adds local alerting but does not retain research telemetry or state itself.
- ntfy (overlap) — Its local inbox received the firing and resolved notifications, and a synthetic message persisted after restart (check_persistence.py ntfy_message check, recorded true in observability/backends/receipt.json). There was no external delivery (external_delivery_tested false). It is a notification sink, not telemetry retention for research runs.
- opentelemetry-collector (overlap) — Its only evidence is the contrib distribution asset otelcol-contrib 0.161.0 (observability/receipt.json components). The standalone core binary was not exercised separately, so it is subsumed by c14.
- Restic (conditional) — Native backup, `check --read-data` and a verified restore passed (22 files, 160642 bytes; hashes matched independently). The scope was static public reference files only: live_databases 0, and no Loki, Prometheus, SQLite or broker-journal backup. off_host_destination is false and the timer is not enabled. It covers only a narrow part of the recoverable-state clause and retains no telemetry.
- sandbox-runtime (conditional) — Relevant to restricting research workers. Native filesystem checks returned allowed_write_exit 0, denied_read_exit 1 and separate_denied_write_exit 1 (evidence/receipts/runtime-tools.json). Network denial was configured but not exercised, and an overlapping read/write path returned exit 0 inside an ephemeral hidden mount. It is not an observability or retention component and does not show that workers lack broker authority.
- mlflow (unqualified) — The only evidence is an external README URL, which could not be opened under the local-read constraint. The packet card records no tracking server or experiment run, so there is no local execution evidence of lineage or trace retention. Untested, not failed.
- phoenix (unqualified) — The only evidence is an external README, not opened. The card says the server launch is prospective with no app instrumented. The license is ELv2; upstream metadata reports NOASSERTION. There is no native trace-retention evidence. Untested, not failed.
- opensandbox (unqualified) — The only evidence is an external README, not opened. The card says help/import is not proof of isolation, and the pin server/v0.2.3 is behind upstream release-1.1.0. There is no local execution evidence.
- modal (out_of_scope) — Managed cloud compute. The card says `modal run` may incur charges and was not run, and catalog inclusion does not authorize paid hosting. The only evidence is an external PyPI page, not opened.
- e2b (out_of_scope) — A managed sandbox, or self-hosted on AWS/GCP. The card says importing it is not a sandbox E2E. The only evidence is an external README, not opened, and it has no role in local telemetry retention.

Overturn when: 1. Backend retention: run `python3 observability/backends/check_persistence.py --grafana-env <private Grafana env file> --evidence-dir <fresh directory>` against the running local stack. It restarts the five backend units, compares before and after snapshots, and exits 1 if any check is false. If prometheus_historical_sample or loki_log comes back false, retention by the c5 and c6 winners is contradicted. 2. Retention contract: run `python3 -m pytest tests/test_observability.py`. These are offline guards only, not native retention checks. A failure in test_sdk_observation_is_bounded_atomic_and_preserves_unknown_usage (failed status and usage None preserved) or test_dashboard_keeps_receipt_identity_separate_from_shared_resource (max by receipt_id) would break the retained-identity and unknown-usage basis. 3. Alternatives: if c11 phoenix or c9 mlflow is run natively on fixtures/observability-check.json and measurably retains per-task identity, failed research attempts or unknown usage that the collector-to-Prometheus/Loki path loses, the verdict changes. The native usage match and the 80770 deduplication after a collector restart have no retained runnable script in the repository. Re-establishing them is listed under open_gaps.

Open gaps:
- No runnable script in the repository re-runs the native usage-match or per-receipt_id deduplication queries. Both rest on the retained observability/receipt.json record only.
- The 80770 deduplicated total comes from republished summaries of two earlier SDK receipts, not new model calls (observability/receipt.json sdk_receipt_lane.source).
- Failed research-worker attempts were never ingested and queried natively in Loki or Prometheus. retained_failed_attempts is prose about harness failures, and preservation of failed status is shown only offline (tests/test_observability.py lines 32-54).
- check_persistence.py restarts only the five backend units, not the collector, and uses a synthetic fixture. Collector-restart equality exists only as a retained record.
- There is no high availability, off-host backup or disaster recovery for the telemetry backends. Single-host persistence is not replication.
- Retention periods were configured but never aged out, so expiry behaviour is unverified.
- The SDK native turn histogram was not observed (native_turn_histogram_observed false).
- Traces are disabled and no trace database is deployed, so per-step research lineage is not retained.
- Nothing shows research workers lack broker execution authority. sandbox-runtime network denial was not exercised.
- Live Loki and Prometheus data was not included in the restic backup (live_databases 0).
- The alert-rule count differs across records: six in observability/receipt.json, final_rule_count 8 in the backends receipt, and fourteen asserted in tests/test_observability_backends_alerts.py. The current rendered set was not re-verified.
- No measured comparison exists against any alternative telemetry or trace store.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-observability-hosting-20260922; codex: -)

#### Portfolio and risk (portfolio-risk)

- skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee — c3 (skfolio) is the only adopted candidate with retained native execution evidence under the repository root. In blueprints/us-equities/research-evaluation/receipt.json (kind "native_cli_e2e", observed_utc 2026-09-19T22:59:04Z, status "accepted_for_causal_raw_price_label_control_only"), native skfolio 1.2.9 WalkForward (252/63/6, reduce_test=True) produced 20 chronological development folds, 21 frozen selections and 6605 candidate records. The skfolio-specific test evidence is the focused-tests command (receipt.json:1561-1576, `python3 -m unittest discover -s tests -p test_research_evaluation.py -q`), which exited 0 with "12 passed". The "214 passed, 0 skipped" full-tests entry (receipt.json:1577-1590) is the adopted SDK's complete repository suite run with $SDK_PYTHON (README.md:66-67). It shows the working SDK was left intact, but it does not test skfolio. The independent_review block records status "accepted", 42 private-artifact hashes verified with 0 mismatches, and blocking_findings []. README.md:73-74 says the installed WalkForward source matches the reviewed hash recorded in the receipt, and that this accepts "the splitter used here, not every skfolio optimizer". So the selection covers only chronological validation for the causal-data part of the requirement. It does not cover portfolio optimization, numeric risk enforcement, equity accounting or Nautilus integration. c1, c2 and c4 have only upstream README URLs as evidence (source review) and no local execution. This is my own source review of the retained receipt, README and evaluate.py. I used the packet's evidence_kind labels as provider metadata and did not rely on them.

Alternatives:
- cvxportfolio (unqualified) — The only evidence is the upstream README URL at 1.5.1 (source review). Under blueprints/, fixtures/ and tests/, the only file that mentions cvxportfolio, empyrical or quantstats is tests/test_sota_convergence.py, which checks manifest metadata and runs nothing. The multi-period cost-model policies have never been installed or run on this repository's frozen inputs. The packet's card limitations say the simulator is not an order gateway and may download risk-free data when a cash column is absent. It is GPL-3.0. Being untested does not mean it failed.
- empyrical-reloaded (unqualified) — The only evidence is the upstream README URL at 0.5.12 (source review), and the packet's review_status is "unmaintained_signal". No local execution receipt was found. The packet's card limitations report an import-name clash with the older empyrical package, and say the optional pandas-datareader path does not work with Python >=3.12. Its metric functions overlap with c4's reporting role and provide neither the deterministic pre-trade risk nor the accounting the requirement asks for.
- quantstats (conditional) — The only evidence is the upstream README URL at v0.0.81 (source review). The packet's review_status is "confirmed_default", but I found no execution receipt under the repository root. The packet's card limitations say its tear sheets are descriptive, work on return periods rather than trades, and cannot fix leakage, fills or accounting errors. Its role is limited to human-readable reporting of results that already exist. It becomes usable only once a Nautilus or LEAN run produces reconciled equity returns for it to read.

Overturn when: The verdict should be reopened in three cases. (1) Rerunning `python3 -m unittest discover -s tests -p test_research_evaluation.py -q` (tests/test_research_evaluation.py; the receipt used -q) no longer exits 0 with 12 passed. (2) A deliberate skfolio v1.3.0 upgrade fails. Run as written, evaluate.py cannot test v1.3.0: evaluate.py:182-183 raises ValueError for any skfolio version other than 1.2.9, and evaluate.py does not compute a WalkForward source hash (that hash is recorded only in receipt.json:32). The upgrade therefore needs four steps: edit requirements.in and the version gate in evaluate.py; regenerate requirements.lock with the README.md:107-113 `uv pip compile ... --generate-hashes` procedure; run evaluate.py into a fresh private output directory per README.md:91-98; then rerun the focused tests. The trigger is a boundary-test failure or a change in fold count or chronology (20 development folds, 252/63/6 splits). A changed WalkForward source hash is expected with a new version, so it would only mean the upstream source needs a new review. It is not grounds for overturning. (3) A native execution of cvxportfolio, or of skfolio's own optimizers, on the frozen inputs in blueprints/us-equities/research-evaluation/plan.json produces a retained receipt with cost-aware portfolio or risk outputs reconciled against Nautilus equity accounting, which the splitter-only skfolio evidence cannot provide.

Open gaps:
- No candidate provides deterministic numeric pre-trade risk enforcement, broker-specific execution boundaries or reproducible equity accounting inside NautilusTrader 2.0.0rc5. Those parts of the requirement are not covered by any evidence at this layer.
- The skfolio evidence covers only the WalkForward splitter used for a raw-price label study on SPY, QQQ and IWM. The README says this does not accept any skfolio optimizer or risk estimator, and the study does not measure portfolio P&L, dividends, financing or fills.
- The receipt's limitations say the reserved 2021Q1 window has already been inspected and only 11 completed episodes exist per candidate, so no alpha or superiority claim can be made.
- There is no purge or embargo beyond the 6-session gap. The README says the row gap is not an event-interval purge engine.
- The cvxportfolio, empyrical-reloaded and quantstats capabilities are untested locally. Being untested does not mean they failed.
- The skfolio pin (1.2.9) is behind upstream v1.3.0 (packet latest). evaluate.py hard-gates 1.2.9 (lines 182-183), so v1.3.0 needs a deliberate pin and gate change followed by native acceptance, and none has been run.
- The WalkForward source-hash match (receipt.json:32) was checked outside evaluate.py. The runner itself does not re-verify it, so reproducing the hash check needs a separate procedure that is not in the retained sources I read.
- Native acceptance covers only Linux/WSL with Python 3.13.15, according to the receipt's limitations.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-portfolio-risk-20260922; codex: -)

#### Research, factors and ML (research-factors-ml)

- skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee — This layer's requirement asks that any strategy be qualified with causal data, costs and independent reconciliation. Only two adopted candidates have retained native execution that bears directly on it. The rest have only an upstream README URL or receipts from other layers. For both winners, what the upstream package did natively is kept separate here from what the project's custom repository code did.

c23 skfolio: native execution observed for the chronological splitter.
- blueprints/us-equities/research-evaluation/README.md, "Observed native results — September 19, 2026" (lines 39-77), and receipt.json record the run. Installed skfolio 1.2.9 WalkForward supplied the 252-session training, 63-session evaluation and six-session exclusion splits (README lines 17-19).
- The run produced 20 development folds, 21 frozen selections and 6605 candidate records, exit 0.
- 12 focused boundary tests and 214 suite tests passed with zero skips, as recorded (README line 66-67).
- An independent review verified 42 artifact hashes, exact public/native result equality and 21 selection hashes (README lines 75-77).
- Attribution: the boundary guarantee comes mainly from the project's evaluate.py, not from skfolio. That rule requires every exact training label end to precede the next evaluation decision (README lines 19-21). The six-row gap is not an event-interval purge (README line 137). The packet's c23 card_limitations also says WalkForward purge/embargo default to zero. skfolio is selected as the natively verified splitter, with the hash-matched source reviewed per README lines 73-74. It is not credited as a leakage guard.

c11 edgartools: native execution observed for SEC archive acquisition only.
- blueprints/us-equities/catalyst-provenance/access-resolution.json native_upstream (lines 31-55) records edgartools 5.58.0 at source_pin abe44344.
- The run called edgar.get_filings(2020,1,form='8-K',filing_date='2020-03-02') and Filings.to_context via native_edgar.py. It returned exit_code 0, http_status 200, 371 cohort_rows and 360 unique_accessions. The complete compressed source hash and gzip decode were verified.
- The earlier HTTP 403 is kept as a retained failure (receipt.json; access-resolution.json retained_failures, lines 168-174).
- Correction from the prior round: the causal gate was not done by EdgarTools. Rejecting all five headers at the 2020-03-03 historical cutoff (eligible_count 0, before_first_availability 5) and qualifying them only after local observation (eligible_count 5) was done by the custom catalyst.py adapter (acquire, then packet). access-resolution.json line 15 says the bridge is custom repository code, and lines 57-117 hold the provenance_adapter.
- Validation current for c11 (access-resolution.json lines 245-270): 236 integrated tests (exit 0, 0 skipped) and 21 focused tests. Independent code review was accepted. An independent evidence review was accepted, checking 7 private and 6 raw hashes with no_blocking_findings true. These supersede the earlier receipt's 13/215 counts.

Neither winner shows predictive edge. README lines 52-62 show the reserved selection, momentum20 at 0.118407% mean after the cost proxy, below the equal-weight control at 0.162293% over 11 completed episodes. The winners are chosen as native evaluation and data-acquisition tooling, not as a signal.
- data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a — This layer's requirement asks that any strategy be qualified with causal data, costs and independent reconciliation. Only two adopted candidates have retained native execution that bears directly on it. The rest have only an upstream README URL or receipts from other layers. For both winners, what the upstream package did natively is kept separate here from what the project's custom repository code did.

c23 skfolio: native execution observed for the chronological splitter.
- blueprints/us-equities/research-evaluation/README.md, "Observed native results — September 19, 2026" (lines 39-77), and receipt.json record the run. Installed skfolio 1.2.9 WalkForward supplied the 252-session training, 63-session evaluation and six-session exclusion splits (README lines 17-19).
- The run produced 20 development folds, 21 frozen selections and 6605 candidate records, exit 0.
- 12 focused boundary tests and 214 suite tests passed with zero skips, as recorded (README line 66-67).
- An independent review verified 42 artifact hashes, exact public/native result equality and 21 selection hashes (README lines 75-77).
- Attribution: the boundary guarantee comes mainly from the project's evaluate.py, not from skfolio. That rule requires every exact training label end to precede the next evaluation decision (README lines 19-21). The six-row gap is not an event-interval purge (README line 137). The packet's c23 card_limitations also says WalkForward purge/embargo default to zero. skfolio is selected as the natively verified splitter, with the hash-matched source reviewed per README lines 73-74. It is not credited as a leakage guard.

c11 edgartools: native execution observed for SEC archive acquisition only.
- blueprints/us-equities/catalyst-provenance/access-resolution.json native_upstream (lines 31-55) records edgartools 5.58.0 at source_pin abe44344.
- The run called edgar.get_filings(2020,1,form='8-K',filing_date='2020-03-02') and Filings.to_context via native_edgar.py. It returned exit_code 0, http_status 200, 371 cohort_rows and 360 unique_accessions. The complete compressed source hash and gzip decode were verified.
- The earlier HTTP 403 is kept as a retained failure (receipt.json; access-resolution.json retained_failures, lines 168-174).
- Correction from the prior round: the causal gate was not done by EdgarTools. Rejecting all five headers at the 2020-03-03 historical cutoff (eligible_count 0, before_first_availability 5) and qualifying them only after local observation (eligible_count 5) was done by the custom catalyst.py adapter (acquire, then packet). access-resolution.json line 15 says the bridge is custom repository code, and lines 57-117 hold the provenance_adapter.
- Validation current for c11 (access-resolution.json lines 245-270): 236 integrated tests (exit 0, 0 skipped) and 21 focused tests. Independent code review was accepted. An independent evidence review was accepted, checking 7 private and 6 raw hashes with no_blocking_findings true. These supersede the earlier receipt's 13/215 counts.

Neither winner shows predictive edge. README lines 52-62 show the reserved selection, momentum20 at 0.118407% mean after the cost proxy, below the equal-weight control at 0.162293% over 11 completed episodes. The winners are chosen as native evaluation and data-acquisition tooling, not as a signal.

Alternatives:
- foundation-qmd (out_of_scope) — Its receipts cover Markdown BM25 retrieval for agent documentation. desktop-cli-workflows.json claims native QMD search/get in a Codex Desktop task, and native-cli-gaps.json line 37 lists qmd as not_exercised in one section. No receipt covers factor construction, temporal validation or strategy qualification.
- data-arcticdb (unqualified) — The only evidence is an upstream README URL (source review, not opened in this lane). There is no local install or run. The packet also flags BSL-1.1 licensing uncertainty and notes that storage version time is not market-availability time.
- data-sktime (overlap) — Its temporal-split role overlaps the natively exercised skfolio WalkForward. The only evidence is a README URL and no run was retained. Because the boundary rule is enforced by the project's evaluate.py (research-evaluation README lines 19-21), swapping splitters under the same checks would likely tie. Only an event-interval purge measured on the same frozen plan would distinguish it.
- alphalens-reloaded (unqualified) — Its IC and turnover diagnostics are unexecuted, and the packet's review_status is unmaintained_signal: last push 2025-12-15, and PyPI 0.4.6 is ahead of the GitHub 0.4.5 tag. The only evidence is a README URL. The packet notes that IC excludes the full cost stack.
- chronos (unqualified) — No inference, GPU or cost-adjusted equity evaluation was performed (packet limitations). The only evidence is a README URL, and generic forecasting benchmarks do not establish US-equity edge.
- data-tsfresh (unqualified) — The only evidence is a README URL and no feature-extraction run was retained. The packet flags leakage and multiple-testing risk, and evidence/receipts/broad-universe-research-20260921.json records that no predictive signal was established.
- deerflow (conditional) — It runs natively, but as an optional research host, not a factor or ML tool. research-receipt.json shows one embedded invoke_acp_agent prompt (exit 0) that read two receipts and returned counts. native-receipt.json is a model-free discovery. The receipt itself says there is no planner/UI, no standing service and no strict read-only enforcement (read-only maps to workspaceWrite/on-request).
- vllm (out_of_scope) — This is a serving runtime for local RAG. vllm-compatibility.json records that 0.29.0 installed but failed GPU startup ('RuntimeError: UVA is not available') and 0.25.0 was restored. The pin is behind upstream (packet latest v0.30.0). No factor or model evaluation was run.
- foundation-haystack (out_of_scope) — Document retrieval pipelines; the packet says there is no financial corpus pipeline or performance proof. The only evidence is README and release URLs.
- data-river (unqualified) — The only evidence is a README URL. Progressive validation with delayed fills and labels is unexercised, and the packet says immediate synthetic labels are invalid for finance.
- data-statsforecast (unqualified) — The only evidence is a README URL; the bundled airline data is a method demo. No rolling evaluation on equity data was retained.
- foundation-docling (out_of_scope) — PDF/OCR ingestion, with table and unit extraction quality unmeasured (packet). The only evidence is README and release URLs, and it does not address factor validation.
- arch (conditional) — Block bootstrap, SPA and MCS would address the multiple-comparison gap in c23's study, but they are unexecuted: the only evidence is a README URL, and the packet notes an NCSA/Other license ambiguity.
- ray-serve (out_of_scope) — Distributed compute and serving with no distributed or failover acceptance (packet). The only evidence is a README URL, and no current workload needs it.
- timesfm (unqualified) — Unexecuted, with only a README URL. The 3.0 weights carry a non-commercial license (packet), and the only example is a synthetic series.
- foundation-markitdown (out_of_scope) — Proven only for local HTML-to-Markdown conversion (portable-cli-artifacts.json: markitdown_contains_heading true). The pin is behind upstream (v0.1.7 vs v0.1.8), and it plays no factor or ML role.
- statsmodels (unqualified) — Interpretable regressions and diagnostics are unexecuted in retained evidence; the only evidence is a README URL. The packet notes that significance does not establish economic profitability.
- foundation-sentence-transformers (out_of_scope) — An embedding and reranking SDK; compatibility with the current vLLM service is unestablished (packet). The only evidence is README and release URLs.
- scikit-learn (overlap) — scikit-learn 1.9.1 appears in the locked runtime of research-evaluation/receipt.json as a skfolio dependency. Its own predictive baselines and TimeSeriesSplit were not exercised, and its packet evidence is a README URL. It serves as a substrate of the winner, not an independently qualified default.
- Qlib (unqualified) — The bundled workflow is China/CSI300-specific; US compatibility and data download are unverified, and the workflow is unexecuted (packet). The only evidence is a README URL.
- tradermonty/claude-trading-skills (unqualified) — Not adopted and has no evidence_refs. Correction from the prior round: the packet note (packet line 402), like the SOTA manifest's comparison_that_would_overturn at catalogs/sota-convergence/manifest-20260922.json line 6134, describes a hypothetical overturn test. That test would apply one backtest-expert checklist criterion to the retained broad-universe results and see whether it catches a defect that two review lanes and 158 local tests missed. It does not claim that a defect was caught. The comparison has not been executed, so the candidate is untested, not failed.
- shiyu-coder/kronos (unqualified) — Not adopted and has no evidence_refs. Its packet note (line 484) describes a comparison that has not been run: Kronos forecasts beating the C0 all-eligible control net of 5/10/20 bps per side on the retained broad-universe dataset. evidence/receipts/broad-universe-research-20260921.json records that the frozen broad-universe protocol established no predictive signal. There is no Kronos result, so it is untested, not failed.

Overturn when: For c23, the verdict changes if either of these fails:
- python3 -m unittest discover -s tests -p test_research_evaluation.py
- a replay of blueprints/us-equities/research-evaluation/evaluate.py under the hash-locked blueprints/us-equities/research-evaluation/requirements.lock that shows a training label exit at or after its evaluation cutoff, or results that differ from receipt.json

The replay has preconditions (README lines 81-105): a fresh private output directory, since the runner rejects an existing one, and --lean-source pointing at the pinned LEAN checkout.

It also changes if an executed comparison on the same frozen plan.json (or on the broad-universe protocol tested by tests/test_broad_universe_evaluate.py) shows an alternative beating skfolio WalkForward under the same evaluate.py boundary checks. The alternative could be an event-interval purge splitter (sktime, sklearn TimeSeriesSplit) or a candidate forecaster (Kronos, Chronos, TimesFM), with the forecaster needing a cost-adjusted edge over the C0 control at 5/10/20 bps per side.

For c11, the verdict changes if a rerun of blueprints/us-equities/catalyst-provenance/native_edgar.py (edgartools 5.58.0, get_filings/to_context; needs the private SEC contact environment and network) no longer completes with exit 0 and the recorded 371 rows / 360 unique accessions. That is the native component. Separately, the custom causal gate would fail if python3 -m unittest tests.test_catalyst_provenance fails, or if catalyst.py packet --as-of 2020-03-03T00:00:00Z on the retained acquisition run no longer gives eligible_count 0 (access-resolution.json lines 104-111). A gate failure would weaken the causal-data pairing but would not by itself be an EdgarTools failure.

Open gaps:
- No retained evidence shows predictive or economic edge. In the reserved 2021Q1 segment, the selected momentum20 (0.118407% mean after cost proxy) was below the equal-weight control (0.162293%) over 11 completed episodes (blueprints/us-equities/research-evaluation/README.md lines 47-62). Separately, evidence/receipts/broad-universe-research-20260921.json states that no predictive signal was established.
- The skfolio study uses a curated 3-ETF control universe (SPY, QQQ, IWM) with raw-price labels. It has no total-return, dividend, fill, financing or cash reconciliation and no NautilusTrader execution (research-evaluation/README.md lines 115-132), so it does not meet the requirement's Nautilus/broker reconciliation clause for this layer.
- The leakage boundary is enforced by the project's evaluate.py, not by skfolio. The WalkForward six-row gap is not an event-interval purge (README lines 19-21 and 137), and purge/embargo default to zero (packet c23 card_limitations). A statistically independent purge/embargo policy is unestablished.
- The reserved 2021Q1 segment has now been inspected and cannot serve as an untouched holdout (README lines 32-37).
- EdgarTools' native role covers only one day's 8-K index acquisition: 371 rows and 360 unique accessions (catalyst-provenance/access-resolution.json lines 31-55). The point-in-time gate over five headers is custom catalyst.py code (line 15). The evidence establishes no point-in-time universe, fundamentals factors or dissemination-lag modelling (line 13), and its dependencies are version-pinned rather than wheel-hash-locked (line 16).
- No candidate listed only by README URL (c2-c6, c9, c10, c12, c14, c15, c17, c18, c20-c22, c24) has a retained native run for this layer.
- No multiple-testing correction (for example arch SPA/MCS) has been applied to the retained strategy searches.
- The c13 and c16 packet notes describe overturn comparisons that have not been executed; no artifacts exist.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-research-factors-ml-20260922; codex: -)

#### Security and supply chain (security-supply-chain)

- syft @ v1.52.0 — Only syft (c4), grype (c2) and gitleaks (c3) have retained native execution evidence. The other adopted candidates have only upstream README references. (1) Syft: blueprints/us-equities/supply-chain/receipt.json (id syft-sdk-inventory-20260919, status passed_scoped_inventory_acceptance) records a native Syft 1.52.0 scan. It ran in a read-only, network-isolated bubblewrap namespace, exited 0 and found 36 Python packages. The package name/version/PURL entries matched 36/36 between the Syft and CycloneDX outputs and 36/36 against installed dist-info metadata. The source fingerprint was unchanged before and after the scan. The release archive matched the publisher checksum list and the GitHub asset digest; signature_verified is false. (2) Grype: blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (status passed_scoped_scan_zero_findings) records native Grype 0.119.0 with database schema v6.1.9, built 2026-09-22T06:30:41Z. It scanned the Syft SBOMs of the NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages). Every syft/grype command exited 0, with 0 runtime matches and 0 adapter matches. The archive checksum matched and signature_verified is false. (3) Gitleaks: evidence/receipts/runtime-tools.json (kind native_cli_e2e, recorded 2026-09-19T04:55:03Z) records a native gitleaks history scan that exited 0 over 22 commits (1174704 bytes, approximate) with 0 findings and 100 percent redaction. The pinned command is in recipes/README.md line 93. Together these three cover dependency inventory, known-vulnerability matching and secret scanning. All are scoped, dated native_proven results, not security certifications.
- grype @ v0.119.0 — Only syft (c4), grype (c2) and gitleaks (c3) have retained native execution evidence. The other adopted candidates have only upstream README references. (1) Syft: blueprints/us-equities/supply-chain/receipt.json (id syft-sdk-inventory-20260919, status passed_scoped_inventory_acceptance) records a native Syft 1.52.0 scan. It ran in a read-only, network-isolated bubblewrap namespace, exited 0 and found 36 Python packages. The package name/version/PURL entries matched 36/36 between the Syft and CycloneDX outputs and 36/36 against installed dist-info metadata. The source fingerprint was unchanged before and after the scan. The release archive matched the publisher checksum list and the GitHub asset digest; signature_verified is false. (2) Grype: blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (status passed_scoped_scan_zero_findings) records native Grype 0.119.0 with database schema v6.1.9, built 2026-09-22T06:30:41Z. It scanned the Syft SBOMs of the NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages). Every syft/grype command exited 0, with 0 runtime matches and 0 adapter matches. The archive checksum matched and signature_verified is false. (3) Gitleaks: evidence/receipts/runtime-tools.json (kind native_cli_e2e, recorded 2026-09-19T04:55:03Z) records a native gitleaks history scan that exited 0 over 22 commits (1174704 bytes, approximate) with 0 findings and 100 percent redaction. The pinned command is in recipes/README.md line 93. Together these three cover dependency inventory, known-vulnerability matching and secret scanning. All are scoped, dated native_proven results, not security certifications.
- gitleaks @ v8.30.1 — Only syft (c4), grype (c2) and gitleaks (c3) have retained native execution evidence. The other adopted candidates have only upstream README references. (1) Syft: blueprints/us-equities/supply-chain/receipt.json (id syft-sdk-inventory-20260919, status passed_scoped_inventory_acceptance) records a native Syft 1.52.0 scan. It ran in a read-only, network-isolated bubblewrap namespace, exited 0 and found 36 Python packages. The package name/version/PURL entries matched 36/36 between the Syft and CycloneDX outputs and 36/36 against installed dist-info metadata. The source fingerprint was unchanged before and after the scan. The release archive matched the publisher checksum list and the GitHub asset digest; signature_verified is false. (2) Grype: blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (status passed_scoped_scan_zero_findings) records native Grype 0.119.0 with database schema v6.1.9, built 2026-09-22T06:30:41Z. It scanned the Syft SBOMs of the NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages). Every syft/grype command exited 0, with 0 runtime matches and 0 adapter matches. The archive checksum matched and signature_verified is false. (3) Gitleaks: evidence/receipts/runtime-tools.json (kind native_cli_e2e, recorded 2026-09-19T04:55:03Z) records a native gitleaks history scan that exited 0 over 22 commits (1174704 bytes, approximate) with 0 findings and 100 percent redaction. The pinned command is in recipes/README.md line 93. Together these three cover dependency inventory, known-vulnerability matching and secret scanning. All are scoped, dated native_proven results, not security certifications.

Alternatives:
- openbao (unqualified) — Its only evidence is an upstream README reference (https://github.com/openbao/openbao/blob/v2.6.2/README.md), which I could not open under this lane's local-read boundary. The packet marks it source_review and not_individually_reviewed. The card itself says no server config is supplied, no service starts and credential handling is unaccepted. There is no local receipt of scoped secret issuance or of denying broker credentials to research workers. That is the clause of the requirement it would most directly serve, but it is untested, not failed.
- cosign (unqualified) — Its only evidence is an upstream README reference (https://github.com/sigstore/cosign/blob/v3.1.3/README.md), which I could not open under this lane's local-read boundary. The packet marks it source_review and not_individually_reviewed, and its card says no signing or identity flow was started. The retained syft and grype receipts both record signature_verified: false with checksum-only verification. Cosign would close that gap, but no verification run is retained.

Overturn when: Change the verdict if either of these is retained. (a) A native OpenBao receipt under blueprints/us-equities/ showing the paper runtime received scoped, revocable broker credentials while a research-worker identity was denied them. That would directly satisfy the requirement's 'without granting research workers broker execution authority' clause and would warrant adding c1 as a winner. (b) A native cosign verification of the pinned syft/grype release artifacts that turns their signature_verified: false into a verified identity. A re-run of the scan recorded in blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json against a later database changes the findings, not the tool selection. After any receipt change, run python3 -m pytest tests/test_catalogs.py; it asserts local evidence refs exist and grype is native_proven.

Open gaps:
- The packet's requirement text (bounded research, native identity, process supervision, telemetry, no broker execution authority for research workers) and its existing_overturn_when (scheduler/graph escalation) match the agents-operations group, not a security/supply-chain requirement. I judged the candidates against it as supplied; the coordinator should confirm the requirement mapping.
- None of the evidence establishes separation of broker credentials from research workers. OpenBao has no execution receipt, and its card says IBKR credential handling is 'selected live-primary, unaccepted'.
- No release signature or build provenance is verified for syft or grype. Both receipts record signature_verified: false with checksum-only matching.
- The Grype scan covers Python package metadata only. It does not cover bundled Rust/Cython extensions, host OS packages, transitive shared libraries or IBKR-side software. Its zero matches are tied to the 2026-09-22T06:30:41Z database snapshot.
- The Syft inventory covers one SDK prefix (36 packages). Three outbound symlinks were not followed, and whole-host and external-interpreter coverage is absent.
- The gitleaks receipt does not name which repository its 22 commits came from. It is a 2026-09-19 point-in-time result with no recurring scan evidence, and its sandbox network denial was 'configured but not separately exercised'.
- There is no measured comparison between these tools and alternatives (e.g. other SBOM, vulnerability or secret scanners). Selection rests on native receipts, not on a head-to-head comparison.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-security-supply-chain-20260922; codex: -)

#### Storage and compute (storage-compute)

- data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa — DuckDB (c4) is the only storage/compute candidate here with retained native execution evidence. I checked each point below against the source files myself.

(1) blueprints/us-equities/data/receipt.json (kind native_cli_e2e, recorded 2026-09-19) records one native run of blueprints/us-equities/data/summarize_backtest.py. The script refuses to overwrite an existing Parquet file (lines 17-18). It casts fillPrice and fillQuantity to DECIMAL(20, 8) (lines 22-24), writes zstd Parquet, reads the file back, and records SHA-256 hashes for both the source and the Parquet. The run produced events 6, distinct_orders 3, statuses filled 3 / submitted 3, calendar XNYS, sample_session 2013-10-07 and parquet_sha256 48ec550a96771e284bde09f6793b0d064e47bf3a731d8a1ac389a509b616f66d.

(2) blueprints/us-equities/research-runtime/receipt.json records the same parquet_sha256 at line 53. At lines 43-46 its Dagu step order_table is 'succeeded', and blueprints/us-equities/research-runtime/prepare-evidence.yaml lines 9-10 show that this step runs summarize_backtest.py. The final_validation_exit_codes [0, 0] at lines 38-41 belong to the two Dagu YAML validations, not to the order_table step. Two recorded runs therefore produced identical Parquet bytes on this bundled input.

(3) blueprints/us-equities/financial-data/receipt.json records duckdb_version 1.5.5 and research_environment_suite tests 84, failures 0, skips 0. It also records native_roundtrip: 'Exact DECIMAL(38,12) values including 12345678901234567890123456.123456789012 survive Parquet and the packet CLI'. Those checks used synthetic fixtures.

(4) blueprints/us-equities/workers/requirements.txt pins duckdb==1.5.5, which matches the packet pin v1.5.5.

Scope: DuckDB is selected only as the embedded SQL/Parquet engine for exact, hash-identified, reproducible research snapshots. The evidence does not show acquisition of licensed observations, preservation of corporate actions, or rejection of data whose historical availability is unknown. Pandera (c8) now has retained, executed fail-closed gate results, but only on synthetic 0-4-row fixtures, so it stays conditional (see alternatives). This is my own source review of the local receipts. No TypeSafe inference was supplied or run, and I did not use any withheld packet decision fields.

Alternatives:
- Pandera (conditional) — Pandera does a different job from c4: it checks a snapshot before promotion. It is not a storage/compute engine. Correction to my earlier proposal: there are retained, executed gate results. Six result files sit in blueprints/us-equities/data/fixtures/, and four of them are cited here: good-gate-result.json (status pass, row_count 4), bad-gate-result.json (status fail, row_count 4, checked_at 2026-09-22T15:12:36.900809+00:00, failing valid_trading_session, volume_integral_non_negative, observed_at_not_future, high_ge_max_open_close and unique_symbol_session), null-price-cell-gate-result.json (fail, row_count 2) and empty-snapshot-gate-result.json (fail, row_count 0). The six also include a fractional-negative-volume result (fail, row_count 2) and one more file. Every result records pandera 0.33.1, which matches the packet pin. catalogs/us-equities/gates-20260922.json lines 66-81 classify the gate as evidence_class 'synthetic' and say 'No real snapshot ingest exists yet'. tests/test_promotion_gate.py reruns the fixtures (lines 142-239), but it is skipUnless the isolated venv exists (lines 90-91). The packet card limitation calling fail-closed promotion 'still implementation work' (packet line 234) is therefore outdated for the synthetic case. Pandera still does not join the winner set. The fixtures are tiny synthetic CSVs, not a representative snapshot. And the gate's fixed CHECK_NAMES (promotion_gate.py lines 45-49) contain no historical availability, eligibility or corporate-action check, only observed_at not in the future.
- data-arrow (overlap) — Arrow is an interchange and Parquet IO library, not a storage or compute engine. The packet evidence is one upstream README, which I did not open. c4 already writes and rereads the Parquet with native, hash-identified results. pyarrow 25.0.1 appears in the gate results' versions field only as an environment dependency. Arrow is not a separate default until a round-trip receipt shows a precision or time-unit need that DuckDB does not meet.
- data-dlt (unqualified) — The only evidence is an upstream README, which I did not open. No retained pipeline run loads licensed US-equity observations into DuckDB. The packet's card limitations say watermark-only extraction can miss late revisions, and that schema inference is not a financial data-quality contract.
- data-iceberg (unqualified) — The only evidence is an upstream README, which I did not open. There is no append, multi-writer, cross-engine or time-travel execution. The card says catalog creation alone would prove none of these, and that storage snapshots do not imply past information availability. No local throughput or concurrency measurement is retained to justify a lake.
- QuestDB (unqualified) — The only evidence is an upstream README, which I did not open. The card says the catalog did not install or start a server, and that dedup/upsert can overwrite corrections. No measured ingestion or temporal-join comparison against c4 is retained.
- ClickHouse (unqualified) — The only evidence is an upstream README, which I did not open. The card says the local SQL command is prospective, with no server, cluster, throughput or reliability evidence. Background merges are not an immutable revision ledger. The pin v26.8.7.19-lts is behind upstream latest v26.9.2.8-stable (packet pin_behind_upstream true).
- ray-serve (out_of_scope) — Ray does distributed compute and model serving, not snapshot storage. The only evidence is an upstream README, which I did not open. The card says no distributed performance or failover acceptance was done. No retained measurement shows the single-process DuckDB workload needs a cluster.
- data-feast (unqualified) — The only evidence is an upstream README, which I did not open. No historical-retrieval run is retained. The card says event-time point-in-time retrieval does not exclude late corrections, and that freshness, skew and access control need separate evidence.
- foundation-toon (out_of_scope) — TOON is a compact serialization format for model context, not storage or compute. evidence/receipts/portable-cli-artifacts.json records one fixture round trip: toon-encode and toon-decode exit 0, toon_roundtrip_equal true. evidence/receipts/component-history.json records that native_claude and native_codex use was 'not independently demonstrated', and that a nested fixture grew from 69 to 94 tokens. Nothing covers analytical snapshots or market data.

Overturn when: The storage/compute default changes only if an executed comparison beats c4 on the same frozen, representative multi-symbol US-equity snapshot. The challenger is c5 QuestDB, c6 ClickHouse or c2 Iceberg. The comparison must follow blueprints/us-equities/data/summarize_backtest.py: write to a new path, reread, and hash. It must reuse the exact-decimal and cutoff cases in tests/test_financial_data.py (test_native_parquet_roundtrip_preserves_exact_decimals_and_cutoffs, test_decimal_storage_boundaries_do_not_use_context_rounded_absolute_value). The challenger must keep exact decimals and cutoffs, produce a byte-reproducible snapshot hash, and show a measured throughput or concurrency need that c4 cannot meet. Separately, c8 Pandera joins the winner set once a retained run of blueprints/us-equities/data/promotion_gate.py on a representative real snapshot fails closed on injected defects and passes the clean snapshot, rerunnable through tests/test_promotion_gate.py. The gate is judged only on its declared CHECK_NAMES. No current candidate supplies a check that rejects rows with unknown historical availability or eligibility; that remains an open gap, not a c8 overturn criterion.

Open gaps:
- No candidate's evidence shows acquisition of licensed, source-identifiable US-equity observations. c4's native run used LEAN bundled simulation order events (sample_session 2013-10-07), not market data.
- blueprints/us-equities/financial-data/receipt.json records a live SEC acquisition that failed with http_403 and produced 0 Parquet datasets. A later native EdgarTools request succeeded (blueprints/us-equities/catalyst-provenance/access-resolution.md lines 3-19: 371 index entries, six raw-source requests). The packet (line 370) says the later acquisition qualifies only its selected requests. Neither is storage/compute evidence. The DECIMAL(38,12) round trip is synthetic-fixture evidence only.
- At the storage or gate layer, nothing preserves corporate actions or security identity or rejects data whose historical availability or eligibility is unknown. promotion_gate.py CHECK_NAMES (lines 45-49) include only observed_at_not_future.
- No local throughput or concurrency measurements exist, so c2, c5 and c6 cannot be judged either way.
- c8's executed gate results cover only synthetic fixtures of 0-4 rows. gates-20260922.json says 'No real snapshot ingest exists yet, so a production paper run is not yet gated end-to-end.'
- The matching parquet_sha256 in the data and research-runtime receipts shows reproducibility on one tiny six-event input only.
- codex lane absent for this layer

Lanes: codex_absent (claude: us-equities-storage-compute-20260922; codex: -)
<!-- verdicts:end -->
