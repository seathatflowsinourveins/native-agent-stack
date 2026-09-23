# Grand catalog handbook: foundation, runtimes and the north star

This is the handbook for the catalog as frozen on **September 22, 2026**. It covers
two catalogs: the **foundation** that every native Claude and Codex session runs
on (20 layers), and the **US-equities north star** that builds simulation, paper
and live trading on that foundation (12 layers). Thirty layers record their winning
repositories, the named alternatives, why the winners were chosen, the evidence
class behind that choice and the comparison that would overturn it. Two trading
layers stay `pending_lanes`: both lanes' sets and the comparison that would decide
them are recorded instead. The
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
| Layers with a recorded verdict | 30 of 32 (2 `pending_lanes`) |
| Selected, versioned components | 69 |
| Foundation capability decisions | 54 |
| Repository identities in the discovery index | 844 |
| Trading gates established / total | 7 / 20 (no rung ready) |

Use the offline explorer (`ecosystem/index.html`, generated with
`python3 scripts/build_ecosystem.py --write` -- not committed, or download it
from a `publish-catalog.yml` workflow artifact (7-day retention, `workflow_dispatch`/`v*`-tag runs only)) for every candidate, alternative
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

Each layer was given a stripped evidence packet, and two independent lanes each
chose a winner set from the retained evidence (see the cross-family run below).
The record tool then applied the rules in code: every recorded winner must name
its evidence class and the reason it beats the alternatives, and the tool derives
its platform status from that evidence class and supplies its install anchor. The dated
[convergence manifest](../catalogs/sota-convergence/manifest-20260922.json) was
refreshed from the same day's lane run. Sealed lane returns are under
`evidence/artifacts/layer-verdicts-20260922/claude/` and `.../codex/`, and adjudications
under `.../adjudication/`. A row records one evidence class for its whole winner set,
the weakest among its winners as both lanes were asked to report it. Read each
winner's `why_selected` for its own evidence.

The recorded verdicts come from the cross-family run. Both lanes judged the same
packets (`lane_packets.py --trading-candidates manifest --withhold-labels`):
- **Trading packets** hold the convergence manifest's own entries for the layer, with
  evidence from their domain cards and the layer's taxonomy scope terms.
- **Foundation packets** drop the labels that revealed the incumbent (candidate review
  status, decision selection and decision review status). Every packet keeps each
  candidate's `adopted` flag, because only an adopted candidate may win; it marks the
  prior selected-or-conditional set without saying which was the default. The
  repository the lanes read kept the labels: see the label-exposure limit below.
  The 32 packets (with `SHA256SUMS`, matching every sealed return's `packet_sha256`)
  and the scrubbed adjudication inputs with their lane key are retained under
  `evidence/artifacts/layer-verdicts-20260922/packets/` and `.../adjudication-inputs/`.
- **Both lanes ran against a checkout** of catalog main with the September 22 v2
  verdicts removed (ledger verdict fields, sealed returns, this handbook and the
  explorer). Each saw neither the other lane's returns nor those verdicts. The
  checkout kept the older v1 decision fields and the foundation decision records'
  selection labels.
- **The Claude lane** used an Opus 5.5 proposer, two refuters and one revision per
  layer. **The Codex lane** ran `codex_lane.py` on GPT-6 Astra at high effort, one
  read-only call per layer. Both received the same record-step notes.

Earlier runs were superseded. The first trading run used group-wide candidate lists;
two intermediate trading runs carried review labels that revealed the withheld
decision; and one trading return had read this handbook while it still held earlier
verdicts. Evidence fields still correlate with the withheld decision: incumbent
entries more often carry native evidence and an install recipe, and some card role
text says "optional" or "fallback".

**Cross-family result.** The two lanes named the same winner set in 20 of 32 layers
(`same_winner`). In the other 12 the sets overlapped. Eleven differed by one or two
components; `observability-hosting` differed by four, two unique to each lane. An
anonymous adjudication decided 10 of them: returns A and B had host paths and model
names scrubbed, an Opus evidence reviewer chose the set the evidence better
supports, and two reviewers tried to refute the pick. It was then run again with A
and B swapped. `record_verdicts.py` accepts an adjudicated winner only when its
judgments cover both presentation orders and all chose the same lane with no
refuting vote, and each sealed adjudication record lists every judgment's order and
pick. Claude's set won 7 and Codex's 3. In `execution-broker` and
`observability-hosting` every judgment chose whichever return was shown as A (2-2
over four judgments, two per order), so the evidence does not separate the sets.
Those two rows stay `pending_lanes` with both sets recorded, and their split
adjudications are sealed with the others. The adjudicators are the same model family
as one lane, which the scrubbing and the order swap mitigate but do not remove.

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
| Workers | Claude Code, Worktrunk (keep but compare) | Owned writing worktrees, integration and independent evidence review |
| Isolation | Worktrunk, sandbox-runtime (retain) | Exercise the required restriction; worktrees do not enforce it |
| Code navigation | Serena (retain) | Exact source retrieval and original-code confirmation |
| Document retrieval | QMD, MarkItDown, Poppler (keep but compare) | Corpus- and format-specific retrieval and conversion checks |
| Semantic RAG | SocratiCode, Qdrant, vLLM (keep but compare) | Hardware-compatible embeddings, scoped indexing and real retrieval |
| Durable memory | ai-memory (keep but compare) | Scoped cross-client recall and restore; matched quality comparison still owed |
| Web research | Tavily CLI, agent-browser, OpenResearch (retain) | Actual source acquisition, attribution and task-specific completeness |
| Token efficiency | RTK, Headroom, ccusage (keep but compare) | Recoverable originals and matching usage categories; no blanket savings claim |
| Quality and evaluation | promptfoo, Playwright Test (retain) | Meaningful behavior checks; source validation is not model-quality evidence |
| CI and supply chain | zizmor, Syft, GitHub attestations (retain) | Actual scoped runs; an inventory is not a vulnerability verdict |
| Scheduling and supervision | systemd, Dagu (keep but compare) | Failure, cancellation and in-flight restart behavior |
| Hosting and services | FastAPI, PostgreSQL, Next.js (retain) | Reproduce the scoped application; production hosting is separate |
| Recovery and portability | Restic, uv (keep but compare) | Empty-target install and off-host restore, then consumer verification |
| Observation and inference | OpenTelemetry Collector, Prometheus, Loki (keep but compare) | Actual task/event delivery and recovery on the destination host |
| Agent SDKs and runtime workers | Codex SDK (retain) | A rerun of the matched three-arm worker comparison |
| MCP servers and client surfaces | MCPorter, MCP Inspector (retain) | Scoped server discovery and contract checks per client |
| Secrets and credentials | Gitleaks (keep but compare) | Full-coverage scanning and a credential-store decision per host |
| Git practice and GitHub automation | Worktrunk, Difftastic, gh CLI (retain; source review only) | Executed hosted runs of each automation lane |

Optional container platforms, cloud providers, inference gateways and alternative
orchestrators are not a universal startup bundle. Select them through the
[hosting comparison](hosting-container-practice.md) and their per-layer decisions.
This handbook does not start services, create schedules or select paid hosting.

## Runtime workers, SDKs and research applications

The agent-SDK layer's recorded winner is the `codex` component. This name covers
two distinct, separately versioned pins: the native **Codex CLI** binary
(`codex-cli`, 0.155.1) and the **Codex Python SDK** package (`openai-codex`,
0.154.0) that drives it programmatically. The exercised programmatic research
worker uses the **Python SDK** (`openai-codex` 0.154.0), explicitly selecting
the native Codex CLI binary (0.155.1) as its backing runtime; the two pins are
not interchangeable and a version bump to one does not imply the other moved.
**OpenAI Agents SDK** and **Claude Agent
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
naming its owner, evidence class, receipt and machine-checkable flip condition,
with one explicit exception: the `live-go` gate's status is `user_decision`
(evidence class `none`, `flip_condition: null`) because it records the user's
own authorization after every required paper and live gate is established, not
a condition any checker can evaluate. `python3 scripts/trading_gates.py --check`
verifies the other 19 gates' ladder arithmetically; a status changes only
through a dated commit after the checker lists the gate as a flip candidate,
except `live-go`, which only the user can flip. On September 22:

| Rung | Established | Open |
| --- | --- | --- |
| Simulation | Offline equity replay, rc5 supply-chain scan, fail-closed snapshot gate (synthetic), exchange_calendars in the stack | SPY/LEAN parity (blocked on two unsupported mappings), dividend module, pre-2020 delisting, dated security identity, point-in-time news and filings, paid data arm |
| Paper | Alpaca paper smoke, broker-path alert rules (synthetic), credential handling | Adaptive-paper broker trial |
| Live | None | Leverage ladder 1x/2x/4x, native fault behaviour, IBKR local acceptance, explicit live go |

No rung is ready. Catalog inclusion does not authorize live configuration, paid
data or hosting, or orders.

## Hardware profiles

`scripts/hardware_profile.py` (stdlib only) measures the current host — cores,
CPU model (`/proc/cpuinfo` on Linux/WSL, `machdep.cpu.brand_string` on
macOS), RAM (`/proc/meminfo` on Linux/WSL; the Windows-side `.wslconfig`
memory value is also read when reachable but only used as a fallback when
`/proc/meminfo` itself cannot be read, since the kernel-visible total is the
measured, `native_proven` value and the config file is `source_review`;
`sysctl hw.memsize`/`hw.ncpu` and Apple Silicon detection on macOS) and, where
present, GPU VRAM via `nvidia-smi` — and recommends a tier for each
hardware-dependent layer from the declarative
[`adoption/hardware-profiles.json`](../adoption/hardware-profiles.json): the
workflow concurrency cap (`min(16, cores - 2)`, this project's per-run
concurrent-agent sizing), the local generation model tier by VRAM or unified
memory (Apple unified memory is scaled by a declared, labelled GPU
working-set fraction before comparison, not treated as 100% usable VRAM,
since it is shared with the OS and any concurrent embedding/semantic-RAG
service — a `concurrent_use_warning` is set when both are non-trivial on the
same unified-memory host), the embedding/semantic-RAG fit (SocratiCode,
Qdrant, vLLM), and suggested `ECOSYSTEM_JOB_MEMORY_HIGH`/`ECOSYSTEM_JOB_MEMORY_MAX`
override values for `ecosystem-bounded-run` (its own defaults, 4G/6G, remain
the WSL-stability containment floor; this is a bounded-fraction ceiling
suggestion for hosts with headroom, never applied automatically).
`tests/test_hardware_profile.py` covers the pure tier/threshold logic, CSV/
sysctl parsing (via mocked subprocess output) and the WSL RAM-source
precedence against synthetic (labelled) inputs.

`adoption/hardware-profiles.json` records one measured entry per host actually
run: this host (measured: `Intel(R) Core(TM) Ultra 9 275HX`, 24 cores, WSL
`/proc/meminfo` 47 GB against a configured `.wslconfig` ceiling of 48 GB, RTX
5090 Laptop GPU reporting 23.9 GB VRAM via `nvidia-smi` against the "24 GB"
marketing figure;
`evidence/artifacts/sota-refresh-20260923/hw-profiles/this-host.json`,
evidence class `native_proven`), and the GitHub-hosted `macos-15` runner
(measured by
[`hardware-profile-smoke.yml`](../.github/workflows/hardware-profile-smoke.yml)
run 35808320867: Apple M1 (Virtual), 3 cores, 7 GB unified memory; an MLX
Qwen2.5-0.5B-Instruct-4bit smoke generated 32 tokens at a reported 146.6
tokens/s with 0.29 GB peak memory; `native_proven` for the macOS code path and
the arm64 MLX install, not for workstation-sized memory tiers). The 128 GB WSL workstation and the
48 GB / 64 GB macOS arm64 unified-memory hosts are recorded as
`labelled_projection` entries with their sizing arithmetic shown inline, not as
measurements; treat them as projections until a fresh run of the script on
each host replaces them. That workflow also runs a tiny MLX generation smoke
test (`mlx-community/Qwen2.5-0.5B-Instruct-4bit`, pinned by Hugging Face
revision SHA) on the macOS runner using `mlx-lm` installed from a hash-locked,
`uv pip compile --generate-hashes --exclude-newer` requirements file
(`tools/mlx-smoke/requirements.lock.txt`; the exclusion date keeps the CI
job's redundant-compile-and-diff check deterministic as new transitive
releases publish), recording tokens/s and peak memory straight from
`mlx_lm.generate.stream_generate`'s own `GenerationResponse` as `native_proven`
for that exact runner, once it actually runs.

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
   manifest --withhold-labels`, so each trading packet carries that layer's own
   manifest entries and no packet carries a decision-bearing label (the defaults
   reproduce the first run's packets). Build a blind checkout with every recorded
   verdict removed: the v2 fields, the sealed returns, packets and adjudication
   inputs, this handbook and the explorer, and also every `selection`, `decision`,
   `disposition`, `current_choice` and `review_status` value in the catalog and
   blueprint JSON files (the September 22 checkout kept those). Point both lanes at it. Then run the Claude lane through the saved
   `layer-verdict-lane` workflow, which lives in the agent-lab repository's
   `.claude/workflows/`, not in this catalog.
4. Run the independent Codex lane (`codex_lane.py`) on the same packets without
   exposing the Claude returns. It passes Codex a strict-output copy of the lane
   schema; the record step still enforces the dropped keywords.
5. Record both lanes with `record_verdicts.py`. A row is `same_winner` when both
   lanes name the same set of winner components. When they disagree, the row
   stays `pending_lanes` until an adjudication file is supplied. Adjudicate from
   anonymized returns in both presentation orders and record every judgment in the
   file's `judgments`; the tool rejects a winner that any order or refuter
   contradicts, and seals a split with the row left `pending_lanes`.
6. Regenerate this page's tables with `build_verdicts.py --write` and check with
   `--check`.

Reopen a layer on a demonstrated gap, a changed requirement, relevant upstream
behavior or a challenger result. A new release, a star count or reviewer
agreement alone never promotes a candidate. Preserve historical records with
their dates and superseding links.

### Limits of the September 22 verdicts

- **Two layers are contested.** `execution-broker` and `observability-hosting` stay
  `pending_lanes`. Both lanes agree on a core: the Alpaca paper adapter with
  alpaca-py, and the OpenTelemetry Collector contrib distribution. They disagree on
  the rest: the Nautilus IBKR adapter; Loki and Prometheus against Restic and
  sandbox-runtime. Order-swapped adjudication split 2-2; the sealed records under
  `evidence/artifacts/layer-verdicts-20260922/adjudication/` hold every judgment.
  The comparison that would decide them is an executed one, such as IBKR adapter
  acceptance or a retention and recovery test of the observability backends.
- **The lanes could read the incumbent's labels.** The packets withheld them, but
  the checkout both lanes read kept every prior label outside the v2 verdict fields:
  - `catalogs/foundation/decisions.json` keeps each of its 54 decisions' `selection`
    (8 `default`, 37 `conditional`, 4 `optional`, 3 `candidate`, 2 `trial`);
  - the landscape ledgers keep their v1 `current_choice`, `decision`, `rationale`
    and candidate `disposition`;
  - `candidate-quality-review.json`, `hosting-practice.json`, `native-practice.json`
    and other catalog files carry `decision`, `selection` or `disposition` values;
  - trading cards such as `runtime-target.json` (`selected_destination`) and
    `data-research.json` (`default` entries), and blueprint receipts such as
    `blueprints/us-equities/adaptive-paper/receipt.json` (whose `decision` keeps
    NautilusTrader selected), carry the trading choices.

  Every foundation return in both lanes (20 of 20 each) lists at least one of these
  label-bearing files among its sources; 19 of 20 list `decisions.json`, and the
  Claude `durable-memory` return notes that `candidate-quality-review.json` exposes
  the prior dispositions. Three trading returns in each lane list one
  (`backtesting-engine` and `execution-broker` in both). Some
  returns and adjudications cite a label as evidence (the Claude `agent-sdks` return
  and the `workers` and `code-navigation` adjudications, for example). The verdicts,
  the foundation ones above all, are therefore not independent of the prior
  selection. The evidence itself is interleaved with those decisions across the
  catalog, so no checkout can hide the prior choice completely; a rerun on a
  checkout with those fields removed would measure how much they steered the result.
- **Adjudication is not independent of one lane's family.** The adjudicators are
  Opus 5.5, the same family as the Claude lane. Scrubbed returns and the order swap
  reduce that influence but do not remove it. Scrubbing removed host paths and model
  names but not process wording. In the retained adjudication inputs, five Claude
  returns say they were corrected after an earlier round or after refuter findings,
  a cue only that lane's pipeline produces, and no Codex return does. Three of those
  layers went to Claude (`instructions-skills`, `observation-inference`,
  `web-research`), one to Codex (`code-navigation`) and one to neither
  (`observability-hosting`). Claude won 3 of the 4 decided cue layers and 4 of the 6
  decided layers without a cue, too few to separate a cue effect from the evidence.
  The sealed Claude returns carry more such wording in their `limits`, which the
  adjudication inputs left out. A Codex-side adjudication of the 10 decided layers,
  with process wording removed, would test both.
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
  to fix at the next convergence run. Neither execution candidate has broker
  acceptance: the adaptive-paper Alpaca adapter has placed no paper orders (its
  broker trial is pending), and the Nautilus IBKR adapter has no broker acceptance
  yet.
- **The two catalogs can pin different versions of one component.** Every trading
  winner's pin equals the convergence manifest's pin for that component id. Five
  foundation winners have no manifest component and record `unpinned`
  (`candidate:typesafe-ai-skills`, `candidate:openai-skills`,
  `candidate:actions-attest`, `candidate:astral-sh-uv`, `candidate:cli-cli`). The trading
  `agents-models-workers` row records ai-memory v2.3.1, which is what its cited
  receipt executed. The foundation `durable-memory` row records 2.3.2 from later
  evidence. Upgrading one catalog's pin does not upgrade the other's.
- **Evidence strength varies by row.** Of the 30 recorded rows, 16 record
  `native_proven`, 7 `local_integration`, 4 `synthetic` and 3 `source_review`
  (`git-github-automation`, `identity-provenance`, `evaluation-experiments`). The
  synthetic rows are `token-efficiency`, `recovery-portability`,
  `observation-inference` and `data-quality-orchestration`. No winner rests on a
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
| agent-sdks | - | recorded | codex @ 0.155.1 | native_proven | 4 | The verdict changes only through a re-preregistered rerun of the sealed three-arm workers comparison, not a new ad-hoc … | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| ci-supply-chain | - | recorded | zizmor @ 1.30.1; syft @ 1.52.0; candidate:actions-attest @ unpinned | native_proven | 5 | Any of these checks would change the verdict.

(1) On a host where zizmor 1.30.1 is installed, python3 -m unittest -v t… | blueprints/convergence-practice/ci-security/README.md, blueprints/us-equities/supply-chain/README.md, catalogs/foundation/automation.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| code-navigation | - | recorded | serena @ 2.0.0.dev0 @ c6fbd1c5932df2494ffa0020af5a9fbe80b82143 | native_proven | 4 | Change the scoped verdict if an executed comparison on fixtures/before.py and fixtures/after.py shows another candidate… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| document-retrieval | - | recorded | qmd @ 2.8.3; markitdown @ 0.1.7; poppler @ 26.09.0 | local_integration | 3 | Change the retrieval selection when an executed comparison using blueprints/us-equities/retrieval-evaluation/fixture.js… | blueprints/convergence-practice/document-ingestion/README.md, recipes/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| durable-memory | - | recorded | ai-memory @ 2.3.2 | native_proven | 9 | Change the verdict only on the result of an executed comparison. It must be a preregistered representative comparison, … | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| git-github-automation | - | recorded | worktrunk @ 0.79.0; candidate:cli-cli @ unpinned; difftastic @ 0.71.0 | source_review | 1 | Any of these results would change the verdict.
(a) A challenger structural-diff tool runs on fixtures/before.py and fix… | docs/github-automation.md, recipes/README.md, recipes/native-upgrades-20260921.md | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| hosting-services | - | recorded | fastapi @ 0.141.1; nextjs @ 16.3.5; postgresql @ 18.6 | native_proven | 8 | Change the verdict if a container lane (Compose with Moby, or Podman/Quadlet) runs the same frozen acceptance for the s… | blueprints/convergence-practice/application-delivery/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| instructions-skills | - | recorded | affaan-m/ECC @ dd6ee538aee0f548d4a6b520118f875431fd749e; candidate:typesafe-ai-skills @ unpinned; candidate:openai-skills @ unpinned | local_integration | 7 | Two checks could change this verdict.

1. Record-integrity check: python3 -m unittest tests.test_landscape. Its test_na… | catalogs/landscape/native-practice.json, recipes/claude-native-profile.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| isolation | - | recorded | worktrunk @ 0.79.0; sandbox-runtime @ 0.0.77 | native_proven | 5 | Either of two checks would change this verdict.

1. A task requires a hostile-code, VM/OCI or resource-limit boundary, … | recipes/README.md, recipes/native-upgrades-20260921.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| mcp-surfaces | - | recorded | mcporter @ 0.13.13; mcp-inspector @ 2.7.0 | native_proven | 1 | The verdict changes if a current-host re-run of the retained operations fails. The retained operations are the ones lis… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| native-clients | - | recorded | claude-code @ 2.1.278; codex @ 0.155.1 | native_proven | 5 | Change the verdict only on an executed comparison, not on source review. The condition has two parts. First, the native… | recipes/README.md, recipes/claude-native-profile.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| observation-inference | - | recorded | opentelemetry-collector-contrib @ 0.161.0; prometheus @ 3.14.0; loki @ 3.7.8 | synthetic | 10 | Change the verdict if a fresh native reconciliation no longer matches.

1. Run a fresh native Claude task. Either use t… | observability/README.md, observability/backends/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| quality-evaluation | - | recorded | promptfoo @ 0.123.1; playwright-test @ 1.63.0 | local_integration | 7 | Either of two outcomes would change this verdict.
1. Inspect AI (c1) runs the frozen cases in blueprints/native-skill-p… | blueprints/convergence-practice/wsl-application/README.md, recipes/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| recovery-portability | - | recorded | restic @ 0.19.1; candidate:astral-sh-uv @ unpinned | synthetic | 5 | State half: re-run the manual hosted workflows in blueprints/convergence-practice/offhost-restore/README.md and bluepri… | adoption/research.json, blueprints/us-equities/hosting/backup/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| scheduling-supervision | - | recorded | dagu @ 2.16.6; systemd @ 255.4-1ubuntu8.17 | local_integration | 4 | Three checks. (1) Re-verify the baseline. `python3 blueprints/convergence-practice/job-recovery/run.py --dagu <reviewed… | blueprints/us-equities/hosting/README.md, blueprints/us-equities/worker-supervision/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| secrets-credentials | - | recorded | gitleaks @ 8.30.1 | local_integration | 1 | Detection side: `python3 -m unittest -v tests.test_gitleaks_config` would count against gitleaks if, on the target host… | recipes/README.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| semantic-rag | - | recorded | socraticode @ 1.14.0; qdrant @ 1.19.1; vllm @ 0.25.0 | native_proven | 5 | Two findings would overturn this verdict. The first is a sealed comparison showing better source-grounded recall, fresh… | recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| token-efficiency | - | recorded | rtk @ 0.49.0; headroom @ 0.37.0; ccusage @ 20.0.24 | synthetic | 4 | A repeated, counterbalanced native comparison on a frozen task, with the complete provider usage of every attempt count… | recipes/README.md, recipes/native-upgrades-20260921.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| web-research | - | recorded | tavily-cli @ 0.1.8; agent-browser @ 0.38.1; openresearch @ 0.2.7 | local_integration | 5 | Browser part: overturn if an executed run shows Playwright CLI or another candidate completing the same task more corre… | recipes/README.md, recipes/native-upgrades-20260921.md, recipes/tavily.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| workers | - | recorded | claude-code @ 2.1.278; worktrunk @ 0.79.0 | local_integration | 10 | Overturn if a real task needs durable multi-host state, approval waits or effect recovery beyond native workers, and a … | recipes/claude-native-profile.md, recipes/native-upgrades-20260921.md | linux-wsl2-x86_64: conditional; macos-arm64: untested |

### foundation (per-layer narrative)

#### Agent SDKs and runtime workers (agent-sdks)

- codex @ 0.155.1 — c4 (Codex SDK/CLI) stays the default because it is the incumbent, with a native integration on record. It did not win a comparison. My own source review found these observations.
(1) Native end-to-end run. blueprints/us-equities/workers/receipt.json (kind native_model_e2e, 2026-09-19) records the Python openai-codex 0.154.0 SDK driving native Codex 0.155.1. One research task finished with run.status "completed", duration_ms 58410 and configured_model "gpt-6-astra". The run returned per-turn usage (totalTokens 135311, lines 40-47) and the exact result fields (lines 51-58). It also returned structured tool events (lines 59-85): four Context Mode calls completed and one ctx_execute_file call failed. The same receipt records two more native turns (lines 132-220). Both had extraction_task_succeeded false, one blocked by the project root and one by approval policy. Across all three turns the total is 204091 tokens, with successful_research_tasks 1 and blocked_file_extraction_tasks 2. blueprints/us-equities/workers/README.md lines 39-45 name the upstream SDK calls used.
(2) Executed three-arm workers comparison. evidence/artifacts/comparison-progress-20260922/summary.json lines 132-157 record 9 submissions across three arms: native Claude CLI, the Codex SDK via native_worker.py, and the Claude Agent SDK. The result is "unresolved" and publication_eligible is false, with the note "no arm accepted as a winner and no SDK adoption follows". worker-receipts-followup.json lines 112-238 add detail. Codex arm B completed both replays with reported_completeness 1. Its cancel submission ended no_receipt/SIGINT with usage not_requested. Claude Agent SDK arm C also succeeded on both replays with completeness 1, and its cancel was interrupted with usage unavailable. Recovery was not run and no artifact judge was pinned. So the comparison neither overturns nor confirms c4.
(3) Activation record. catalogs/foundation/decisions.json lines 2831-2841 set selection "conditional" and review_status "source_review", with the activation text "Use the Codex CLI/SDK for existing supported start/run/resume workflows". The decision's evidence_ids point only to token-practice-coverage-20260920; the link to the us-equities receipt is mine, not the decision's.
Two limits apply. First, native_worker.py line 77 sets ephemeral=True, so this integration does not show resume. Second, README lines 53-57 say inherited MCP servers and hooks are not made read-only, so c4 isolation is unverified.

Alternatives:
- Claude Agent SDK (conditional) — This correction replaces my earlier 'source review only' description. c3 was measured, as arm C in the executed workers comparison (evidence/artifacts/comparison-progress-20260922/summary.json lines 132-157). Its two replays succeeded with reported_completeness 1, and its cancel was interrupted with usage unavailable (worker-receipts-followup.json lines 177-238). That is comparable to Codex arm B, but the comparison is 'unresolved' and publication-ineligible, and 'no SDK adoption follows'. catalogs/sota-convergence/sdk-runtime-coverage-20260922.json line 3907 (judge prose) says the Python SDK 0.2.157 login probe was executed. It also says the SDK 'was still recorded as measured-but-not-adopted' because the add-candidate condition 'A or B fails' was not met. That is second-hand; its primary source is outside this repository. The TypeScript sibling probe shows one partial advantage over the c4 receipt: a resumed session with the same session_id (evidence/artifacts/sdk-runtime-coverage-20260922/probes-20260922.json lines 235-237). The same probe's review found isolation overstated: the session loaded the host's settings and tools and left a transcript and memory rows behind. Pin mismatch: registry 0.2.157 against GitHub release 0.2.156 (docs/foundation-closure-20260921.md line 82).
- OpenHands SDK (conditional) — The only evidence is source review. docs/foundation-closure-20260921.md line 86 pins 1.49.2 at commit 856d99d4 and calls it 'Conditional for remote/container workers; does not improve the current local review merely by installation.' The retained evidence has no install, native run or comparison arm for it. It was not among the three arms of the workers comparison. Its benefit, remote or container isolation, addresses a need no current local worker has declared.
- Temporal (out_of_scope) — Not adopted. docs/foundation-closure-20260921.md line 84 (Temporal Python 1.33.0) says 'Deferred until required; adds a service and distinct effect/recovery semantics.' Temporal is a durable workflow runtime, not an agent SDK that gives a worker structured events or custom tools. Its evidence is source review only.
- LangGraph (unqualified) — Not adopted. docs/foundation-closure-20260921.md line 85 (1.2.11, commit ed384f3a) says 'Deferred unless building an application needing these semantics' (explicit state and checkpoints). Its evidence is source review only, with no native run. It would add a framework layer over provider clients rather than the native SDK path.

Overturn when: The verdict changes only through a re-preregistered rerun of the sealed three-arm workers comparison, not a new ad-hoc run. That comparison is recorded as unresolved in evidence/artifacts/comparison-progress-20260922/summary.json lines 132-157; its runner is outside this repository. The rerun must close the gaps recorded there: run recovery, pin an artifact judge, and apply the same isolation check to both arms. c3 replaces c4 as the default only if the closure resolves with arm C ahead of arm B on replay correctness, cancel/usage completeness and recovery. It must also pass post-run isolation (no host settings, tools or hooks beyond those allowed, and no leftover transcript or memory rows) at comparable provider usage. The recovery stage's offline precondition is python3 -m unittest tests.test_worker_recovery, which exercises blueprints/convergence-practice/worker-recovery/stage.py. It launches no agent and cannot overturn the verdict alone. python3 -m unittest tests.test_native_worker_fixture is also offline replay only. Separately, a declared remote or container worker need (OpenHands SDK), graph-checkpoint need (LangGraph) or durable multi-host replay need (Temporal) would reopen the layer.

Open gaps:
- The only executed Codex SDK vs Claude Agent SDK comparison is unresolved and publication-ineligible, with 'no arm accepted as a winner' (evidence/artifacts/comparison-progress-20260922/summary.json lines 133-151). Recovery was not run and artifact acceptance has no pinned judge.
- The Codex cancel submission has no native returned receipt: arm_status no_receipt, usage not_requested (worker-receipts-followup.json lines 152-176). Claude Agent SDK interruption reports usage as unavailable. Neither shows actual provider consumption.
- c4 isolation is unverified. The SDK overlays env onto the parent environment, and read-only permissions do not make inherited MCP servers or hooks read-only (blueprints/us-equities/workers/README.md lines 53-57; receipt.json line 110). The recorded tool events came from the host's Context Mode server.
- native_worker.py line 77 creates ephemeral threads, so the c4 integration has not shown multi-turn resume. Custom-tool registration through the SDK is also unobserved. The 'start/run/resume' wording in the foundation closure is a project description, not an observation.
- In the c4 receipt, two of three native turns failed their extraction task, blocked by the project root and by approval policy (receipt.json lines 132-220).
- The receipt's actual research prompt is private (research-prompt.txt, distributed false, receipt.json lines 126-130). blueprints/us-equities/workers/research-task.md is a blank template, so that receipt cannot be reproduced from repository fixtures.
- Version skew: the receipt records openai-codex 0.154.0 against native 0.155.1, while the packet pin is 0.155.1. The foundation closure asks for a version change to be qualified before promotion.
- The foundation decision's evidence_ids cite only token-practice-coverage-20260920, not the us-equities worker receipt or the workers comparison (catalogs/foundation/decisions.json lines 2838-2840). Its next_gap cites SDK table lines 78-84, but the table is at lines 80-86 of docs/foundation-closure-20260921.md.
- The only evidence for OpenHands (remote/container), LangGraph (checkpoints) and Temporal (durable replay) is source review.
- No matched execution compares the candidate SDKs on structured events, custom tools or session control.
- The Codex receipt demonstrates a bounded programmatic worker with existing MCP tools; it does not establish arbitrary custom-tool registration or complete event handling.
- SDK cancellation, provider billing cessation, distributed recovery and exactly-once effects remain unqualified.
- The recorded file-tool scope failure and subsequent approval-blocked override remain unresolved acceptance boundaries.
- CLI session-resume evidence does not independently qualify SDK resume behavior.

Lanes: same_winner (claude: foundation-agent-sdks-20260922; codex: foundation-agent-sdks-20260922)

#### CI and supply chain (ci-supply-chain)

- zizmor @ 1.30.1 — The requirement names four properties: scoped workflow permissions, pinned dependencies, actual runtime inventory and attributable hosted checks. Each winner has a recorded native run that covers at least one of them.

(1) zizmor 1.30.1 (c7) covers pinned action references. blueprints/convergence-practice/ci-security/README.md lines 3-8 records a SHA-256-locked wheel in the exact-head CI run. Lines 19-24 record a native Linux run: the workflow directory returned exit 0 with no findings, the inert fixture returned exit 14 with template-injection, unpinned-uses and artipacked, and both acceptance tests passed with no skips. tests/test_workflow_security.py lines 56-59 assert exit 14 and the presence of template-injection and unpinned-uses. docs/github-automation.md lines 217-223 records a recheck of all workflows with no findings at the regular persona. catalogs/foundation/decisions.json lines 1413-1446 (offline-security-inventory, accepted_within_scope) lists this layer.

Correction from the earlier proposal: no retained evidence shows zizmor rejecting over-broad permissions. The fixture itself declares permissions: contents: read (tests/fixtures/workflow-security/unsafe.yml.txt lines 4-5), and no test or receipt contains an excessive-permissions finding. The scoped-permissions property rests on configuration review, not zizmor execution. That review covers a read-only default token, where only the publication job adds id-token: write and attestations: write alongside contents: read (docs/catalog-provenance.md lines 20-24). It also covers the statement that every workflow is contents: read only (catalogs/foundation/automation.json line 254). The pull-request checklist also requires SHA pins and contents: read (docs/github-automation.md lines 340-344).

(2) Syft 1.52.0 (c3) covers actual runtime inventory. In a native local run, it exited 0 and found 36 Python packages, with 36/36 agreement between the two output formats and with installed metadata (blueprints/us-equities/supply-chain/README.md lines 3-25). The archive SHA-256 matched both the publisher's checksum list and GitHub's release-asset digest (same README, lines 36-38). catalogs/us-equities/hosting-source-review.json lines 96-102 records native_cli_e2e.

(3) actions/attest 4.2.2 (c4) covers attributable hosted checks. Hosted publication run 35541322881 succeeded at d0fe136c. An independent consumer download matched the catalog digest. Online and detached verification of the original, altered and original archive returned 0/1/0 (docs/catalog-provenance.md lines 8-14; catalogs/foundation/automation.json lines 208-221).

All of this is my source review of retained records; I re-executed nothing. The native_proven class holds only for each recorded host, commit and scope.
- syft @ 1.52.0 — The requirement names four properties: scoped workflow permissions, pinned dependencies, actual runtime inventory and attributable hosted checks. Each winner has a recorded native run that covers at least one of them.

(1) zizmor 1.30.1 (c7) covers pinned action references. blueprints/convergence-practice/ci-security/README.md lines 3-8 records a SHA-256-locked wheel in the exact-head CI run. Lines 19-24 record a native Linux run: the workflow directory returned exit 0 with no findings, the inert fixture returned exit 14 with template-injection, unpinned-uses and artipacked, and both acceptance tests passed with no skips. tests/test_workflow_security.py lines 56-59 assert exit 14 and the presence of template-injection and unpinned-uses. docs/github-automation.md lines 217-223 records a recheck of all workflows with no findings at the regular persona. catalogs/foundation/decisions.json lines 1413-1446 (offline-security-inventory, accepted_within_scope) lists this layer.

Correction from the earlier proposal: no retained evidence shows zizmor rejecting over-broad permissions. The fixture itself declares permissions: contents: read (tests/fixtures/workflow-security/unsafe.yml.txt lines 4-5), and no test or receipt contains an excessive-permissions finding. The scoped-permissions property rests on configuration review, not zizmor execution. That review covers a read-only default token, where only the publication job adds id-token: write and attestations: write alongside contents: read (docs/catalog-provenance.md lines 20-24). It also covers the statement that every workflow is contents: read only (catalogs/foundation/automation.json line 254). The pull-request checklist also requires SHA pins and contents: read (docs/github-automation.md lines 340-344).

(2) Syft 1.52.0 (c3) covers actual runtime inventory. In a native local run, it exited 0 and found 36 Python packages, with 36/36 agreement between the two output formats and with installed metadata (blueprints/us-equities/supply-chain/README.md lines 3-25). The archive SHA-256 matched both the publisher's checksum list and GitHub's release-asset digest (same README, lines 36-38). catalogs/us-equities/hosting-source-review.json lines 96-102 records native_cli_e2e.

(3) actions/attest 4.2.2 (c4) covers attributable hosted checks. Hosted publication run 35541322881 succeeded at d0fe136c. An independent consumer download matched the catalog digest. Online and detached verification of the original, altered and original archive returned 0/1/0 (docs/catalog-provenance.md lines 8-14; catalogs/foundation/automation.json lines 208-221).

All of this is my source review of retained records; I re-executed nothing. The native_proven class holds only for each recorded host, commit and scope.
- candidate:actions-attest @ unpinned — The requirement names four properties: scoped workflow permissions, pinned dependencies, actual runtime inventory and attributable hosted checks. Each winner has a recorded native run that covers at least one of them.

(1) zizmor 1.30.1 (c7) covers pinned action references. blueprints/convergence-practice/ci-security/README.md lines 3-8 records a SHA-256-locked wheel in the exact-head CI run. Lines 19-24 record a native Linux run: the workflow directory returned exit 0 with no findings, the inert fixture returned exit 14 with template-injection, unpinned-uses and artipacked, and both acceptance tests passed with no skips. tests/test_workflow_security.py lines 56-59 assert exit 14 and the presence of template-injection and unpinned-uses. docs/github-automation.md lines 217-223 records a recheck of all workflows with no findings at the regular persona. catalogs/foundation/decisions.json lines 1413-1446 (offline-security-inventory, accepted_within_scope) lists this layer.

Correction from the earlier proposal: no retained evidence shows zizmor rejecting over-broad permissions. The fixture itself declares permissions: contents: read (tests/fixtures/workflow-security/unsafe.yml.txt lines 4-5), and no test or receipt contains an excessive-permissions finding. The scoped-permissions property rests on configuration review, not zizmor execution. That review covers a read-only default token, where only the publication job adds id-token: write and attestations: write alongside contents: read (docs/catalog-provenance.md lines 20-24). It also covers the statement that every workflow is contents: read only (catalogs/foundation/automation.json line 254). The pull-request checklist also requires SHA pins and contents: read (docs/github-automation.md lines 340-344).

(2) Syft 1.52.0 (c3) covers actual runtime inventory. In a native local run, it exited 0 and found 36 Python packages, with 36/36 agreement between the two output formats and with installed metadata (blueprints/us-equities/supply-chain/README.md lines 3-25). The archive SHA-256 matched both the publisher's checksum list and GitHub's release-asset digest (same README, lines 36-38). catalogs/us-equities/hosting-source-review.json lines 96-102 records native_cli_e2e.

(3) actions/attest 4.2.2 (c4) covers attributable hosted checks. Hosted publication run 35541322881 succeeded at d0fe136c. An independent consumer download matched the catalog digest. Online and detached verification of the original, altered and original archive returned 0/1/0 (docs/catalog-provenance.md lines 8-14; catalogs/foundation/automation.json lines 208-221).

All of this is my source review of retained records; I re-executed nothing. The native_proven class holds only for each recorded host, commit and scope.

Alternatives:
- actionlint (overlap) — The native evidence is strong. Version 1.7.12 at 914e7df2 passed attestation and checksum verification, and actionlint returned exit 0 with empty output across all workflows (docs/github-automation.md lines 128-135 and 217-223). It is part of the validate job. However, it checks workflow syntax, expressions and embedded shellcheck. It does not check permissions, action pins, runtime inventory or attribution, and it does not execute a job (docs/github-automation.md lines 93-95). Keep it as a complementary required validator, not as a layer winner.
- Trivy (unqualified) — The only retained evidence is a source review of v0.74.0. Its decision is 'defer_until_sbom_and_db_freshness_policy' (catalogs/us-equities/hosting-source-review.json line 155). Its execution_status is 'research_only_except_explicit_existing_tool_and_memory_recovery_results' (line 160). It would need versioned vulnerability-database provenance and a fix-applicability policy, and it would duplicate a single-scanner lane. It has not been run here, which is different from having failed.
- Dependabot (conditional) — The initial hosted scans succeeded and opened PRs #29 and #30. Their integrity failures, on unreviewed workflow hashes, were retained (docs/github-automation.md lines 56-60; catalogs/foundation/automation.json lines 36 and 201-203). The weekly Monday 09:00 UTC timing and a nonempty minor/patch group remain unobserved (docs/github-automation.md line 61; automation.json line 265). It owns only GitHub Actions references. It is not activated for pip, because .github/requirements-ci.lock is not a name it discovers, and four of the five pinned CI binaries are curl-downloaded tarballs it cannot parse (automation.json line 249). It proposes pin updates; it does not enforce pinning.
- gitleaks (overlap) — Native gitleaks accepted clean controls and rejected inert fixtures (catalogs/foundation/decisions.json lines 1413-1446). Since the rulesets were applied on 2026-09-22, secret-scan has been a required check (docs/github-automation.md lines 359-365). Lines 298-302 of the same file, which say it was not yet required, are superseded. docs/foundation-closure-20260921.md line 63 names gitleaks for this layer alongside zizmor and Syft. Its function, however, is secret scanning, which is none of the four requirement axes, and it mainly belongs to the secrets-credentials layer (decisions.json lines 2910-2935). Its hosted coverage is also incomplete. The first hosted run timed out. The --max-target-megabytes 2 limit skips the 11 MB explorer HTML. An unrestricted-history scan leaves one residual finding pending a coordinator decision (docs/github-automation.md lines 473-490). No successful hosted run ID is recorded in the sources I read.
- Grype (conditional) — The packet records Grype as adopted=false with evidence_kind source_review. My source review disagrees on the evidence class, and I state that disagreement explicitly. The disagreement does not change the packet's adoption decision. A local native scan of 0.119.0 found 0 matches for 21 runtime packages and 2 adapter packages against database v6.1.9 (blueprints/us-equities/supply-chain/README.md lines 139-194; the raw outputs are not committed). catalogs/us-equities/agents-operations.json line 1456 records native_proven, and automation.json lists Grype in supply-chain.yml's sbom-vuln job. No hosted sbom-vuln run is recorded. The requirement asks for an inventory, not a vulnerability verdict. Grype also tracks upstream's latest release rather than a fixed pin, never passes --fail-on, and its threshold decision is pending (docs/github-automation.md lines 307-322).

Overturn when: Any of these checks would change the verdict.

(1) On a host where zizmor 1.30.1 is installed, python3 -m unittest -v tests.test_workflow_security reports a failure or any skip. The test class skips when zizmor is absent (tests/test_workflow_security.py line 16), so a run with skips proves nothing. The same applies if python3 scripts/validate_convergence.py blueprints/convergence-practice/ci-security/experiment.json --root . --json fails.

(2) A fresh Syft run against the SDK recorded in blueprints/us-equities/supply-chain/receipt.json no longer matches the installed metadata 36/36.

(3) A new hosted publish-catalog run on the 2026-09-22 workflow bytes fails the 0/1/0 original/altered/original gh attestation verify sequence in docs/catalog-provenance.md.

Separately, Dependabot (c5) could displace a winner if a recorded hosted weekly run shows a nonempty grouped update and its pin ownership extends past GitHub Actions references. A zizmor permissions negative control, meaning a fixture with over-broad permissions rejected at the adopted persona, would move the scoped-permissions axis from configuration review to native evidence.

Open gaps:
- No retained zizmor negative control shows it rejecting over-broad workflow permissions. The unsafe fixture declares contents: read, and the tests assert only template-injection and unpinned-uses. The scoped-permissions axis rests on configuration and source review (docs/catalog-provenance.md lines 20-24; automation.json line 254), not on native analyzer execution.
- The hosted 0/1/0 attestation qualification is for run 35541322881 at d0fe136c (2026-09-20). On 2026-09-22, publish-catalog.yml added a tag trigger, a changed job condition, a Syft SBOM step and a second attest step (automation.json lines 153-159). The sources I read record no hosted run of the current workflow bytes, so neither the archive attestation nor the SBOM attestation is re-qualified.
- The hosted sbom-vuln job in supply-chain.yml has no recorded run ID. Syft's native inventory evidence comes from a local run on one host against one SDK prefix, not whole-host or whole-runtime coverage. Update 2026-09-22 (docs/decisions/2026-09-22-github-automation-closure.md): hosted sbom-vuln run 35799579095 returned 0 Critical, 0 High, 5 Medium, 1 Low for 13 packages.
- The Syft install checked checksums only. Signature and build provenance were not verified (blueprints/us-equities/supply-chain/README.md lines 51-52).
- Dependabot's weekly timing and nonempty minor/patch grouping are unobserved. Python and binary pins have no automated updater; the report-only catalog-freshness drift table stands in for one. Update 2026-09-22 (docs/decisions/2026-09-22-github-automation-closure.md): weekly Dependabot run 35583086998 (Monday 2026-09-21 09:24 UTC) succeeded with no PR, so a nonempty group is still unobserved; Dependabot security updates now cover alerted lock files, and pip version updates stay off.
- Offline zizmor analysis at the regular persona does not cover online advisories, secrets or provenance (ci-security README lines 48-52). Update 2026-09-22 (docs/decisions/2026-09-22-github-automation-closure.md): security-scan.yml's zizmor-online job adds the online audits on push/schedule/dispatch as SARIF; locally on 168a3a8 they returned 0 findings at the regular persona.
- No vulnerability threshold policy exists. Grype is report-only, and Trivy is deferred. Update 2026-09-22 (docs/decisions/2026-09-22-github-automation-closure.md): a threshold policy is now committed (grype --fail-on high with a reviewed .grype.yaml, dependency-review fail-on-severity high, OSV-Scanner failing on any unignored vulnerability in every tracked lockfile), but no hosted run of these gates is recorded yet, so the gap stays open until one is; Trivy remains deferred.
- "Reproducible changes" is not established end to end. Static checks execute no job, and hosted runs qualify only their named commits.
- The three winners cover complementary requirements; no executed comparison establishes that this combination is globally superior to every alternative.
- Syft's installed-package inventory excludes external interpreters, host libraries and complete vendored-native-library discovery; its release signature was not verified.
- zizmor acceptance covers offline regular-persona analysis. The unsafe fixture is inert synthetic input, and successful analysis does not execute workflows.
- Publication provenance establishes origin and byte integrity for the named historical commit, not reproducible builds, catalog correctness or current publication behavior.
- Complete dependency locking and ongoing update ownership are not established across every runtime; Dependabot's scheduled timing and grouped-update behavior remain unobserved.
- The Grype scan establishes a dated zero-match result, not vulnerability absence, positive-detection sensitivity or remediation quality.

Lanes: same_winner (claude: foundation-ci-supply-chain-20260922; codex: foundation-ci-supply-chain-20260922)

#### Code navigation (code-navigation)

- serena @ 2.0.0.dev0 @ c6fbd1c5932df2494ffa0020af5a9fbe80b82143 — Select Serena for exact source and references in qualified languages. evidence/receipts/foundation-native-20260920.json records native execution: eight symbol/source/reference checks passed across fresh Codex and Claude server contexts after Python/TypeScript configuration repair, with exact Python parse_codex and CJS collect[0] source matches. evidence/receipts/native-context-memory.json also records completed find_symbol and find_referencing_symbols calls. This directly supports the requirement; use focused original-source reads when already sufficient and activate structural or indexed alternatives only for a concrete retrieval question.

Alternatives:
- ast-grep (conditional) — Adopted, and it shares the structural-code-lane decision with c3 (decisions.json lines 606-654). Its only retained execution is weaker for this requirement. evidence/receipts/portable-cli-artifacts.json is a native_cli_e2e fixture that says it is 'not an LLM invocation or general quality benchmark' (lines 4 and 15). The initial command returned exit_code 1 with matched false (lines 53-67). The corrected --stdin run found 8 function definitions with the pattern 'function $NAME($$$ARGS) { $$$BODY }' (lines 110-125). That shows definition matching only: no references and no native model host. It stays useful as index-free exact syntax search when the question is a structural pattern. It does not beat the winners on 'exact source and references'. The quota-blocked Codex CLI attempt did not exercise either tool, so it counts against neither c1 nor c3.
- CodeGraph (unqualified) — Not adopted. The only evidence is a README/license review at commit ba3c21e50d9129d2f5f3843ec3728868ae6d47a1, which records 'No installation, model inference, broker call or native acceptance was performed by this audit'. Its speed and completeness claims 'need a relevant language/workload comparison' (catalogs/us-equities/star-audit.json lines 9884-9904). It is untested, not failed. No executed evidence shows it beating the adopted lanes.
- jCodeMunch (measured_tradeoff) — Native retrieval returned a byte-exact function. Complete search/source responses measured 861 tokens versus 5476 for the whole file and 601 for the known focused function. Useful for scoped discovery, but the retained comparison does not establish better reference retrieval than Serena or justify indexing for known-source reads.
- codebase-memory-mcp (conditional) — Retained Desktop search and trace exited successfully and identified collect plus four static callees. That establishes a bounded graph operation, not complete incoming references, full implementation retrieval or runtime dependencies. Use for graph questions or demonstrated language-server gaps.

Overturn when: Change the scoped verdict if an executed comparison on fixtures/before.py and fixtures/after.py shows another candidate returning exact changed greeting source and correct incoming references where Serena fails, or matching correctness at lower complete indexing/retrieval/update cost. Broader replacement requires representative target-language tasks beyond these small fixtures.

Open gaps:
- No matched cross-candidate benchmark establishes source/reference completeness and total cost across representative languages and repositories.
- The reviewed evidence does not establish symbol-update/deletion correctness for every index or language server.
- Artifact token comparisons use different tasks and accounting boundaries; they cannot establish causal provider savings or a global ranking.
- Static graph results do not establish dynamic runtime behavior.
- lanes disagreed: claude=codebase-memory-mcp,jcodemunch-mcp,serena; codex=serena; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-code-navigation-20260922.json

Lanes: disagree (claude: foundation-code-navigation-20260922; codex: foundation-code-navigation-20260922)

#### Documents and ingestion (document-retrieval)

- qmd @ 2.8.3 — Select QMD BM25 for scoped search/get, with MarkItDown for qualified HTML conversion and Poppler for qualified born-digital PDFs. The measured native comparison in evidence/artifacts/foundation-rd-20260921/qmd-comparison.json reported equal BM25/hybrid recall@3 of 0.5, with average latency of 5 versus 10328 ms. Native execution recorded in evidence/receipts/native-catalog-retrieval-20260920.json retrieved both selected sources first and recovered exact pinned bodies apart from a display newline. catalogs/foundation/decisions.json records selected MarkItDown HTML conversion passing. Native Poppler execution in blueprints/convergence-practice/document-ingestion/accepted/receipt.json and blueprints/convergence-practice/wsl-document-ingestion/receipt.json passed three pages, 24 cells, eight positive and four absent queries. Those PDF results use a designed synthetic corpus and project-local geometry/provenance checks, not general layout inference. The winner-set evidence class is conservatively local_integration because ingestion qualification relies on bounded project fixtures.
- markitdown @ 0.1.7 — Select QMD BM25 for scoped search/get, with MarkItDown for qualified HTML conversion and Poppler for qualified born-digital PDFs. The measured native comparison in evidence/artifacts/foundation-rd-20260921/qmd-comparison.json reported equal BM25/hybrid recall@3 of 0.5, with average latency of 5 versus 10328 ms. Native execution recorded in evidence/receipts/native-catalog-retrieval-20260920.json retrieved both selected sources first and recovered exact pinned bodies apart from a display newline. catalogs/foundation/decisions.json records selected MarkItDown HTML conversion passing. Native Poppler execution in blueprints/convergence-practice/document-ingestion/accepted/receipt.json and blueprints/convergence-practice/wsl-document-ingestion/receipt.json passed three pages, 24 cells, eight positive and four absent queries. Those PDF results use a designed synthetic corpus and project-local geometry/provenance checks, not general layout inference. The winner-set evidence class is conservatively local_integration because ingestion qualification relies on bounded project fixtures.
- poppler @ 26.09.0 — Select QMD BM25 for scoped search/get, with MarkItDown for qualified HTML conversion and Poppler for qualified born-digital PDFs. The measured native comparison in evidence/artifacts/foundation-rd-20260921/qmd-comparison.json reported equal BM25/hybrid recall@3 of 0.5, with average latency of 5 versus 10328 ms. Native execution recorded in evidence/receipts/native-catalog-retrieval-20260920.json retrieved both selected sources first and recovered exact pinned bodies apart from a display newline. catalogs/foundation/decisions.json records selected MarkItDown HTML conversion passing. Native Poppler execution in blueprints/convergence-practice/document-ingestion/accepted/receipt.json and blueprints/convergence-practice/wsl-document-ingestion/receipt.json passed three pages, 24 cells, eight positive and four absent queries. Those PDF results use a designed synthetic corpus and project-local geometry/provenance checks, not general layout inference. The winner-set evidence class is conservatively local_integration because ingestion qualification relies on bounded project fixtures.

Alternatives:
- Context Hub (conditional) — It covers a different scope: selected curated developer documentation, not controlled ingestion of local documents. The curated-developer-docs entry in catalogs/foundation/decisions.json (lines 817-856) is conditional and limited to a named documentation gap. It cites retained native search and retrieval, and the packet labels its evidence as mixed. docs/token-native-saturation.md (lines 16 and 72) shows only the 'use' stage accepted, and its kept comparison grew by 85 tokens. There is no measured retrieval-quality comparison against this layer's fixture.
- Docling (unqualified) — The only evidence is a source review. catalogs/us-equities/foundation-memory.json (foundation-docling, lines 1134-1170) states that commands are prospective and were not run, and that table and unit extraction quality is unmeasured. Model weights carry separate licences. The Poppler README (lines 118-123) says to adopt Docling only when it passes a frozen layout/OCR corpus with provenance and answer checks. That comparison has not been run, so the capability is untested rather than failed.
- LlamaIndex (unqualified) — The only evidence is a source review. catalogs/us-equities/foundation-memory.json (foundation-llama_index, lines 983-1018) lists the layer as rag-pipeline, says commands were not run, and notes a README emphasis on LlamaParse with possible managed-parsing cost and data transfer. It has no ingestion or retrieval receipt for this layer, so it is untested rather than failed.

Overturn when: Change the retrieval selection when an executed comparison using blueprints/us-equities/retrieval-evaluation/fixture.json, with a sealed representative corpus and repeated runs, demonstrates useful quality gains at acceptable end-to-end latency while preserving original-body fidelity. Change the parser selection when the representative layout/OCR extension described in blueprints/convergence-practice/document-ingestion/README.md demonstrates better extraction with preserved provenance and justified runtime costs.

Open gaps:
- The QMD four-mode comparison used one ordered run and an expanded index without a complete corpus seal; repeated warm/cold latency and representative corpus recall remain unestablished.
- The earlier scoped benchmark's eight top-three successes and four misses are separate from the later expanded-index diagnostic.
- Two exact QMD source-body retrievals do not establish arbitrary query recall or automatic index freshness.
- Poppler acceptance covers designed born-digital Latin pages with explicit table geometry and local exact-phrase retrieval. OCR, inferred layouts, arbitrary filings and semantic questions remain unqualified.
- MarkItDown optional PDF/Office extras are not established by the selected HTML conversion.
- No retained comparison establishes end-to-end answer quality or provider-token savings for the combined ingestion and retrieval workflow.
- lanes disagreed: claude=poppler,qmd; codex=markitdown,poppler,qmd; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-document-retrieval-20260922.json

Lanes: disagree (claude: foundation-document-retrieval-20260922; codex: foundation-document-retrieval-20260922)

#### Durable memory (durable-memory)

- ai-memory @ 2.3.2 — ai-memory (c5) is the only adopted candidate with retained native execution evidence for this requirement. That evidence applies to the installed 2.3.2 pin (source 353841d91618d20b110b208de284a74d0b960379), not to the newer reviewed revision 5157c6b or upstream v2.4.0. The evidence shows:
(1) The receipt evidence/receipts/memory-landscape-lifecycle-20260921.json (kind "native_cli_e2e", lines 1-16) records native memory and RAG use across Codex and Claude. docs/native-memory-rag-lifecycle.md lines 29-41 describe the Codex use. They also describe a fresh native Claude task that called memory_read_page and exited after four turns. Its 764-byte final reply was read back from the stored Stop observation, all nine lifecycle observations were present, and consolidation generation 9 completed on attempt 1.
(2) The native maintenance commands in docs/memory-landscape-maintenance.md lines 127-139 cover doctor, status, curator, lint, auto-improve and two scheduler ticks. Two unchanged upstream test filters also passed there: 4 scheduler tests and 18 assistant-capture tests.
(3) Allowlisted lifecycle capture is installed for both native Claude and native Codex through the upstream installer (docs/memory-landscape-maintenance.md lines 104-125). This gives capture that can be inspected.
(4) The synthetic lexical probe (blueprints/memory-lifecycle-probe/README.md lines 3-19) passed write, overwrite, delete and restart checks for ai-memory with 28/28 content checks. Its first attempt failed the no-model-download rule, and that failure was preserved.
Every other adopted candidate has pinned source review only (catalogs/landscape/candidate-quality-review.json, qualification_gap at lines 442, 564, 624, 744, 856, 914, 972). The exception is Basic Memory, which has the same small synthetic probe. None of the others has native Codex/Claude capture, deletion or recovery evidence. This is the best-supported operational fit. It is not a demonstrated recall, learning-quality or cost winner (candidate-quality-review.json line 377).

Alternatives:
- Basic Memory (conditional) — It matched ai-memory only on a tiny synthetic three-note lexical lifecycle (write, overwrite, delete, reindex), with 28/28 content checks across both tools. The probe explicitly says it ranks neither semantic quality nor recovery. Basic Memory reindex is not a lost-database restore, and the two tools had unequal recovery checks (blueprints/memory-lifecycle-probe/README.md lines 3-19 and 40-45). There is no native Codex/Claude hook capture, cross-project isolation or restore evidence. AGPL-3.0 deployment fit is unreviewed (candidate-quality-review.json lines 437 and 466).
- Mem0 (conditional) — Only the pinned source (a39a802) was reviewed: no install, upstream test run, native model operation, matched answer-quality comparison or recovery acceptance (candidate-quality-review.json lines 559-564). It is an application-memory SDK. Its published benchmark claims do not carry over to project continuity across native Codex and Claude. A second agent-memory database is not an automatic improvement (docs/memory-landscape-maintenance.md line 42).
- Letta Code (unqualified) — Letta Code is a stateful agent runtime, not a drop-in memory store. Adopting it means replacing the native Codex/Claude worker architecture, which is outside this layer (docs/memory-landscape-maintenance.md line 45; candidate-quality-review.json line 739). Only the pinned source (dfb5639) was reviewed, with no execution evidence (line 744).
- OpenViking (conditional) — OpenViking is a hierarchical context filesystem that would unify resources, memory and skills. It is worth considering only if fragmented context becomes a measured obstacle. Its benchmark carry-over, migration and AGPL deployment fit are unevaluated, and only the pinned source (172c105) was reviewed (candidate-quality-review.json lines 909-914; docs/candidate-quality-review-20260921.md line 72).
- Graphiti (conditional) — Graphiti is a temporal entity-relationship graph that could complement project memory for entity or time questions. There is no evidence that it improves the project wiki or supplies inspectable native-client capture, deletion or restore (candidate-quality-review.json lines 619-624; docs/memory-landscape-maintenance.md line 41). Only the pinned source was reviewed.
- Cognee (conditional) — Cognee is a graph and context candidate for research corpora. Its default LLM recipe uses OpenAI, so the local profile would need qualifying. Only the pinned source (663a2dc) was reviewed, with no capture, deletion or restore evidence for native Codex/Claude (candidate-quality-review.json lines 851-856; docs/candidate-quality-review-20260921.md line 71).
- Supermemory (conditional) — The cloud-only exclusion is stale; a local server and an Ollama route are documented. However, its provider calls, licensing, export/restore, isolation and representative retrieval are unqualified, and only the pinned source (57b430b) was reviewed (candidate-quality-review.json lines 967-972).
- Hindsight (unqualified) — Not adopted in the packet. It is named a priority challenger for retain/recall/reflect memory, and its documented native Codex/Claude subscription providers remove the API-key exclusion. Still, only the pinned source (680406b) was reviewed. Its published benchmarks do not measure this project's recall, isolation or cost (candidate-quality-review.json lines 497-502), so the evidence does not show it satisfies the requirement better.
- Claude-mem (overlap) — Not adopted in the packet. Its automatic capture, compression and retrieval overlap ai-memory's capture role. The review rules out running overlapping capture stores by default, and only the pinned source was reviewed (candidate-quality-review.json lines 679-684; docs/memory-landscape-maintenance.md line 44).

Overturn when: Change the verdict only on the result of an executed comparison. It must be a preregistered representative comparison, built on the frozen-input structure of blueprints/memory-lifecycle-probe/corpus.json. It must be rechecked by python3 blueprints/memory-lifecycle-probe/verify.py and extended as recorded in the next_decision_changing_test of blueprints/blind-catalog-convergence/memory-experiment.json. That test covers held-out grounded questions, abstention, supersession, project isolation (as asserted by tests/test_memory_lifecycle.py) and an actual clean-target restore. The verdict changes if that run shows a candidate such as Basic Memory or Hindsight with better source-grounded recall/usefulness than ai-memory 2.3.2, with at least equal capture, deletion and restore behavior and acceptable complete provider usage and latency. A native restore failure or an ai-memory isolation regression in that suite would also change it.

Open gaps:
- No matched semantic-recall or usefulness benchmark between ai-memory and any alternative exists. The only comparative run is a three-note lexical probe that ranks nothing (blueprints/memory-lifecycle-probe/README.md lines 8-9 and 129-132).
- The quality of learned writes is unestablished. The scheduler admitted sessions, but the single model review rejected its proposal for insufficient durable evidence (docs/memory-landscape-maintenance.md lines 135-136 and 161-164).
- In the synthetic probe, ai-memory's native restore/reindex was not run because the process guard enumerates all same-name processes. Deletion covered only current search results, not erasure from history, logs or backups (blueprints/memory-lifecycle-probe/README.md lines 40-45 and 133-134).
- Captured assistant excerpts are sanitized and capped at 2,000 bytes, so they are not complete transcripts. Claude prompt capture remains opted out (docs/memory-landscape-maintenance.md lines 113-116).
- Recovery beyond the synthetic hosted restore is unqualified: independent physical host, lost-key/account recovery, native-client rebinding and whole-stack recovery (packet decision synthetic-offhost-application-restore limitations).
- Native evidence applies to installed 2.3.2 (353841d). The reviewed revision 5157c6b and upstream v2.4.0 are not installed or qualified (packet pin_behind_upstream true; candidate-quality-review.json line 382).
- Exact session and lifetime memory token savings are null or unknown (evidence/receipts/memory-landscape-lifecycle-20260921.json lines 69-72).
- The scheduler covers all store scopes with a per-project limit, and only one project is adopted. Isolation with multiple projects in production is unobserved (docs/memory-landscape-maintenance.md lines 148-150).
- Useful autonomous learning remains unestablished: the retained real-session review rejected insufficient durable evidence, and scheduler admission produced no learned edits.
- Representative semantic recall, decision accuracy, handoff usefulness and complete provider consumption have no matched comparison.
- Capture is bounded and sanitized; it does not establish complete transcript retention or universal current-session coverage.
- TTL controls default search visibility until sweep; deletion observations do not establish erasure from historical versions, logs or backups.
- Same-host restored SQLite/FTS state does not establish live-client rebinding, atomic database/wiki consistency or independent disaster recovery.
- The reviewed ai-memory upstream revision is not the accepted installed 2.3.2 revision; upgrade behavior remains unqualified.
- The synthetic ai-memory comparison initially attempted an unwanted model download. The corrected explicit embedding opt-out passed, but network bytes were not measured.

Lanes: same_winner (claude: foundation-durable-memory-20260922; codex: foundation-durable-memory-20260922)

#### Git practice and GitHub automation (git-github-automation)

- worktrunk @ 0.79.0 — The requirement (packet line 186) names three functions: worktree ownership, GitHub review/PR automation and structural diffs. Each winner covers one of them, and nothing else in the evidence covers that function better.

(1) c4 worktrunk 0.79.0, for worktrees. catalogs/foundation/decisions.json#owned-worktrees (lines 477-519, scope at line 499) records "Native listing and disposable create/list/remove passed; dirty removal was refused without loss", with use stage accepted_within_scope. I opened evidence/receipts/worktrunk-list.json. It records the native command `wt list --format json` with exit_code 0 and worktree_count 3, which is native execution.

(2) c2 GitHub CLI, for the GitHub-side operations. It is the only candidate that operates on GitHub at all. Its only evidence ref is docs/github-automation.md, and I reviewed it as source. Only one dated result there is explicitly attributed to gh. Lines 128-132 record that on 2026-09-20 "`gh attestation verify` returned exit 0" for actionlint 1.7.12, and that the attestation named the expected source, tag and release workflow. The rules check is recorded with no date and no named client: lines 180-183 say "a separate `GET /repos/OWNER/REPO/rules/branches/main` confirmed both required contexts". Lines 359-366 record that the 2026-09-22 ruleset application was compared field by field "through the GitHub API". gh api is documented as the maintenance/apply command (lines 187-192 and 368-376), but the doc does not say which client produced those results. No gh PR command (create/review/merge) result is recorded anywhere. decisions.json lines 2971-2982 state that gh has no inventory entry and "no lifecycle stage at all". c2 is therefore selected on source review for GitHub API, ruleset and attestation operations, not on proven PR automation.

(3) c1 difftastic 0.71.0, for structural diffs. decisions.json#deterministic-quality-tools (lines 1351-1411) records difftastic use as accepted_within_scope for "native shell/structural comparison". blueprints/token-native-focus/saturation-audit.json lines 2886-2933 record the command `difft --exit-code --color never fixtures/before.py fixtures/after.py`, native_cli_e2e receipts and retained operation fresh-difftastic.

The combined decision git-github-automation-practice (decisions.json lines 2950-3002, line 2970) says that no new execution was run to freeze this layer. c2 has no lifecycle evidence, so the weakest class across the set is source_review.
- candidate:cli-cli @ unpinned — The requirement (packet line 186) names three functions: worktree ownership, GitHub review/PR automation and structural diffs. Each winner covers one of them, and nothing else in the evidence covers that function better.

(1) c4 worktrunk 0.79.0, for worktrees. catalogs/foundation/decisions.json#owned-worktrees (lines 477-519, scope at line 499) records "Native listing and disposable create/list/remove passed; dirty removal was refused without loss", with use stage accepted_within_scope. I opened evidence/receipts/worktrunk-list.json. It records the native command `wt list --format json` with exit_code 0 and worktree_count 3, which is native execution.

(2) c2 GitHub CLI, for the GitHub-side operations. It is the only candidate that operates on GitHub at all. Its only evidence ref is docs/github-automation.md, and I reviewed it as source. Only one dated result there is explicitly attributed to gh. Lines 128-132 record that on 2026-09-20 "`gh attestation verify` returned exit 0" for actionlint 1.7.12, and that the attestation named the expected source, tag and release workflow. The rules check is recorded with no date and no named client: lines 180-183 say "a separate `GET /repos/OWNER/REPO/rules/branches/main` confirmed both required contexts". Lines 359-366 record that the 2026-09-22 ruleset application was compared field by field "through the GitHub API". gh api is documented as the maintenance/apply command (lines 187-192 and 368-376), but the doc does not say which client produced those results. No gh PR command (create/review/merge) result is recorded anywhere. decisions.json lines 2971-2982 state that gh has no inventory entry and "no lifecycle stage at all". c2 is therefore selected on source review for GitHub API, ruleset and attestation operations, not on proven PR automation.

(3) c1 difftastic 0.71.0, for structural diffs. decisions.json#deterministic-quality-tools (lines 1351-1411) records difftastic use as accepted_within_scope for "native shell/structural comparison". blueprints/token-native-focus/saturation-audit.json lines 2886-2933 record the command `difft --exit-code --color never fixtures/before.py fixtures/after.py`, native_cli_e2e receipts and retained operation fresh-difftastic.

The combined decision git-github-automation-practice (decisions.json lines 2950-3002, line 2970) says that no new execution was run to freeze this layer. c2 has no lifecycle evidence, so the weakest class across the set is source_review.
- difftastic @ 0.71.0 — The requirement (packet line 186) names three functions: worktree ownership, GitHub review/PR automation and structural diffs. Each winner covers one of them, and nothing else in the evidence covers that function better.

(1) c4 worktrunk 0.79.0, for worktrees. catalogs/foundation/decisions.json#owned-worktrees (lines 477-519, scope at line 499) records "Native listing and disposable create/list/remove passed; dirty removal was refused without loss", with use stage accepted_within_scope. I opened evidence/receipts/worktrunk-list.json. It records the native command `wt list --format json` with exit_code 0 and worktree_count 3, which is native execution.

(2) c2 GitHub CLI, for the GitHub-side operations. It is the only candidate that operates on GitHub at all. Its only evidence ref is docs/github-automation.md, and I reviewed it as source. Only one dated result there is explicitly attributed to gh. Lines 128-132 record that on 2026-09-20 "`gh attestation verify` returned exit 0" for actionlint 1.7.12, and that the attestation named the expected source, tag and release workflow. The rules check is recorded with no date and no named client: lines 180-183 say "a separate `GET /repos/OWNER/REPO/rules/branches/main` confirmed both required contexts". Lines 359-366 record that the 2026-09-22 ruleset application was compared field by field "through the GitHub API". gh api is documented as the maintenance/apply command (lines 187-192 and 368-376), but the doc does not say which client produced those results. No gh PR command (create/review/merge) result is recorded anywhere. decisions.json lines 2971-2982 state that gh has no inventory entry and "no lifecycle stage at all". c2 is therefore selected on source review for GitHub API, ruleset and attestation operations, not on proven PR automation.

(3) c1 difftastic 0.71.0, for structural diffs. decisions.json#deterministic-quality-tools (lines 1351-1411) records difftastic use as accepted_within_scope for "native shell/structural comparison". blueprints/token-native-focus/saturation-audit.json lines 2886-2933 record the command `difft --exit-code --color never fixtures/before.py fixtures/after.py`, native_cli_e2e receipts and retained operation fresh-difftastic.

The combined decision git-github-automation-practice (decisions.json lines 2950-3002, line 2970) says that no new execution was run to freeze this layer. c2 has no lifecycle evidence, so the weakest class across the set is source_review.

Alternatives:
- Codex for Claude review bridge (conditional) — Correction from the prior round: the outer Claude delegation has been exercised once, natively. evidence/receipts/foundation-rd-20260921.json (line 10) records "Literal native Claude-to-Codex foreground review returned successfully". Its artifact, evidence/artifacts/foundation-rd-20260921/native-review.json, records command `claude -p "/codex:review --wait --scope branch --base 9074852... --json"` (lines 6-15), official_companion 1.0.6 at source pin db52e28f (lines 19-27, matching the c3 pin), codex status 0 (line 44), claude_result subtype success / terminal_reason completed (lines 50-53) and process_exit_code 0 (line 109). The catalog's partial_acceptance use stage and its 'outer delegation unexercised' text are stale against this receipt: saturation-audit.json lines 2240 and 2256-2261 cite only token-practice-gap-followup-20260920.json, decisions.json lines 2973 and 2997 still say partial_acceptance, and decisions.json contains no reference to foundation-rd-20260921. c3 still stays conditional rather than default, for three reasons. First, the evidence is one foreground review of a local branch diff covering three files (receipt line 12; artifact line 39), not a GitHub PR review. Second, it does not cover worktrees, GitHub API/ruleset operations or structural diffs. Third, the artifact's own limits (lines 136-142) leave Workflow background polling, same-workspace concurrency, the cause of an earlier aborted attempt and durable Codex threads unqualified. Codex usage, model and effort are not exposed (lines 111-114). decisions.json line 2960 scopes it to a concrete cross-client review task.

Overturn when: Any of these results would change the verdict.
(a) A challenger structural-diff tool runs on fixtures/before.py and fixtures/after.py and produces more correct syntax-aware hunks, with fewer spurious changes and a correct exit code, than `difft --exit-code --color never fixtures/before.py fixtures/after.py`.
(b) A gh lifecycle receipt, or a failed gh PR/ruleset/attestation operation, is recorded. A failure would demote c2. A matched challenger passing that same operation would replace it.
(c) c3 would be promoted from conditional to a default review lane if a retained native-review artifact shows /codex:review completing a Workflow-background (polled) or same-workspace concurrent review, or a review of an actual GitHub PR fetched through gh, with its findings checked against source.
After any catalog change, including the correction that records foundation-rd-20260921 as c3 use-stage evidence, re-run the decision-consistency check with `python3 -m unittest tests.test_catalog_decisions`.

Open gaps:
- gh CLI has no manifests/stack.json inventory entry and no lifecycle stage (decisions.json lines 2971-2982). The only gh-attributed dated result is `gh attestation verify` exit 0 on 2026-09-20 (docs/github-automation.md lines 128-132). The ruleset GET (lines 180-183) is undated. The 2026-09-22 comparison (lines 359-366) is recorded as 'through the GitHub API', with no client named.
- No gh PR operation (create/review/merge) result is recorded. PR automation is therefore unestablished for every candidate. The gh-aw agentic workflow candidate is public preview and not activated (docs/github-automation.md lines 138-157).
- The catalog lifecycle for codex-for-claude is stale. saturation-audit.json lines 2240 and 2256-2261 and decisions.json lines 2973 and 2997 still say the outer delegation is unexercised / partial_acceptance, but evidence/receipts/foundation-rd-20260921.json records a successful outer foreground review, and decisions.json does not reference that receipt.
- c3's outer review evidence is one foreground review of a local branch diff covering three files. Workflow background polling, same-workspace concurrency, the earlier aborted attempt's cause and Codex usage/model/effort remain unqualified (native-review.json lines 111-114 and 136-142).
- No new execution was run to freeze this layer (decisions.json line 2970). Winner evidence is dated 2026-09-20/21 and was not recertified on the current host (saturation-audit.json current_host_recertified_by_this_audit false for worktrunk and difftastic).
- Worktrunk crash cleanup without deleting unrelated or dirty state is not established (decisions.json line 507).
- No matched comparison of any winner against a challenger exists for this layer. Selection rests on scoped acceptance, not on a measured comparison.
- GitHub CLI has no separate component inventory or lifecycle qualification; its selection rests on source review of documented integration and recorded operations.
- No matched end-to-end comparison establishes superiority across worktree creation, structural review, PR handling and cleanup.
- Worktrunk's disposable lifecycle used disabled hooks; crash recovery and permission isolation are not established.
- Difftastic's small Python fixture does not establish semantic review accuracy across languages.
- The GitHub automation guide retains contradictory applied-versus-pending ruleset passages; its latest dated section reports application, but live state was not checked.
- The review bridge's outer plugin invocation remains unqualified.

Lanes: same_winner (claude: foundation-git-github-automation-20260922; codex: foundation-git-github-automation-20260922)

#### Application and service hosting (hosting-services)

- fastapi @ 0.141.1 — FastAPI (c1, API service), Next.js (c2, UI server) and PostgreSQL (c6, persistent state) are the only adopted candidates with native execution evidence of running the selected local typed application. catalogs/foundation/decisions.json lines 1636-1776 (decision local-typed-application, layer_ids include hosting-services) mark them "accepted_within_scope" for install, use, persistence and restart. Recovery is "not_established" for all four components. The recipe blueprints/convergence-practice/application-delivery/README.md was run natively on a Mac with Next.js 16.3.5, React 19.3.0, FastAPI 0.141.1 and PostgreSQL 18.6 built from source (lines 13-14, 34). It passed all 12 API checks, the production build and a real browser create/update. The created record then survived a PostgreSQL stop/start and an API/Next restart byte-for-byte (lines 113-118). A migration was reversed in an empty synthetic database (lines 147-152). The same application was run again natively on WSL2 Ubuntu 24.04 (blueprints/convergence-practice/wsl-application/README.md lines 10-13), with "status": "passed_with_explicit_platform_adaptations" and 12 passed API checks (wsl-application/receipt.json lines 4 and 108). The recipe keeps scope explicit, which the requirement asks for. Ports are loopback only (15432, 18080, 18081). Runtime and state stay in an ignored .runtime directory, authentication is local synthetic trust only, and no account or credential store is used (README lines 41-43 and 127-133; WSL README lines 72-74 and 111-114). Rollback steps are documented (README lines 141-143). React (c11) passed the same checks, but inside the Next.js process, so it is recorded as overlap to stay within the three-winner limit. Evidence class: native execution on named local fixtures. This is not production, cloud or independent-host qualification.
- nextjs @ 16.3.5 — FastAPI (c1, API service), Next.js (c2, UI server) and PostgreSQL (c6, persistent state) are the only adopted candidates with native execution evidence of running the selected local typed application. catalogs/foundation/decisions.json lines 1636-1776 (decision local-typed-application, layer_ids include hosting-services) mark them "accepted_within_scope" for install, use, persistence and restart. Recovery is "not_established" for all four components. The recipe blueprints/convergence-practice/application-delivery/README.md was run natively on a Mac with Next.js 16.3.5, React 19.3.0, FastAPI 0.141.1 and PostgreSQL 18.6 built from source (lines 13-14, 34). It passed all 12 API checks, the production build and a real browser create/update. The created record then survived a PostgreSQL stop/start and an API/Next restart byte-for-byte (lines 113-118). A migration was reversed in an empty synthetic database (lines 147-152). The same application was run again natively on WSL2 Ubuntu 24.04 (blueprints/convergence-practice/wsl-application/README.md lines 10-13), with "status": "passed_with_explicit_platform_adaptations" and 12 passed API checks (wsl-application/receipt.json lines 4 and 108). The recipe keeps scope explicit, which the requirement asks for. Ports are loopback only (15432, 18080, 18081). Runtime and state stay in an ignored .runtime directory, authentication is local synthetic trust only, and no account or credential store is used (README lines 41-43 and 127-133; WSL README lines 72-74 and 111-114). Rollback steps are documented (README lines 141-143). React (c11) passed the same checks, but inside the Next.js process, so it is recorded as overlap to stay within the three-winner limit. Evidence class: native execution on named local fixtures. This is not production, cloud or independent-host qualification.
- postgresql @ 18.6 — FastAPI (c1, API service), Next.js (c2, UI server) and PostgreSQL (c6, persistent state) are the only adopted candidates with native execution evidence of running the selected local typed application. catalogs/foundation/decisions.json lines 1636-1776 (decision local-typed-application, layer_ids include hosting-services) mark them "accepted_within_scope" for install, use, persistence and restart. Recovery is "not_established" for all four components. The recipe blueprints/convergence-practice/application-delivery/README.md was run natively on a Mac with Next.js 16.3.5, React 19.3.0, FastAPI 0.141.1 and PostgreSQL 18.6 built from source (lines 13-14, 34). It passed all 12 API checks, the production build and a real browser create/update. The created record then survived a PostgreSQL stop/start and an API/Next restart byte-for-byte (lines 113-118). A migration was reversed in an empty synthetic database (lines 147-152). The same application was run again natively on WSL2 Ubuntu 24.04 (blueprints/convergence-practice/wsl-application/README.md lines 10-13), with "status": "passed_with_explicit_platform_adaptations" and 12 passed API checks (wsl-application/receipt.json lines 4 and 108). The recipe keeps scope explicit, which the requirement asks for. Ports are loopback only (15432, 18080, 18081). Runtime and state stay in an ignored .runtime directory, authentication is local synthetic trust only, and no account or credential store is used (README lines 41-43 and 127-133; WSL README lines 72-74 and 111-114). Rollback steps are documented (README lines 141-143). React (c11) passed the same checks, but inside the Next.js process, so it is recorded as overlap to stay within the three-winner limit. Evidence class: native execution on named local fixtures. This is not production, cloud or independent-host qualification.

Alternatives:
- React (overlap) — React 19.3.0 has the same accepted_within_scope stage records as the winners in the same decision (catalogs/foundation/decisions.json lines 1700-1723). It is the UI library rendered by the Next.js server, not a separately hosted service, so its hosting role is covered by c2. It was left out only because of the three-winner limit. Recovery is not_established.
- Docker Compose (conditional) — Source review only: v5.5.1 at pin 5f94fb0a with native_acceptance not_established (catalogs/landscape/hosting-practice.json lines 21-30). The guide says no container trial establishes that it wins or fails on this workload (docs/hosting-container-practice.md lines 5-6). Its lifecycle value has not been compared with the current native services.
- Docker Engine / Moby (conditional) — Source review only: docker-v29.8.1 at pin 464cd50c with native_acceptance not_established. No matched result shows better reproduction or recovery than the accepted native services (catalogs/landscape/hosting-practice.json lines 10-19). On WSL the guide warns that Desktop integration and a separate engine conflict (docs/hosting-container-practice.md lines 24-29).
- Podman / Quadlet (conditional) — Source review only: v6.1.2 at pin 04f3aa43 with native_acceptance not_established. Image, networking, volume, GPU and Docker-API compatibility are unmeasured (catalogs/landscape/hosting-practice.json lines 32-42). Adopt it only when rootless or systemd-managed containers are the stated requirement (docs/hosting-container-practice.md line 13).
- Dev Containers CLI (conditional) — The decision is defer_container_profile_until_container_hosting_is_selected (adoption/research.json line 334). It would add a Docker-compatible runtime plus container-specific account, socket and GPU integration (line 335). Its lock does not pin the base image or application dependencies (line 342). No container was built or executed (line 345), and every native command has the status 'not executed by this research pass' (lines 347-367).
- Dockerized IB Gateway (conditional) — It is a broker-gateway sidecar for the Nautilus IBKR path, not the typed application's hosting. Image digest, sign-in, restart, API connectivity and broker reconciliation are not qualified (catalogs/landscape/hosting-practice.json lines 44-52). The default image uses a mutable 'stable' tag (docs/hosting-container-practice.md lines 31-36).
- Modal (out_of_scope) — It is a managed cloud GPU/job service. It needs a separate Modal account, native login and compute budget. 'modal run executes cloud code and may incur charges; not run here', and all commands are prospective (catalogs/us-equities/agents-operations.json lines 606-644). This is outside the local reproducible-hosting requirement, and paid hosting is not authorized by catalog inclusion.
- BentoML (out_of_scope) — Its layers are model-serving and packaging (catalogs/us-equities/agents-operations.json lines 565-603), not hosting the typed application. Commands are prospective and not executed, no cloud deployment or model call was run, and the entry prefers direct vLLM until packaging adds value.

Overturn when: Change the verdict if a container lane (Compose with Moby, or Podman/Quadlet) runs the same frozen acceptance for the same locked application. That acceptance is blueprints/convergence-practice/application-delivery/acceptance-plan.json via make verify, as reproduced natively in blueprints/convergence-practice/wsl-application/receipt.json: 12 API checks, the browser create/update, migration reversal and exact row/history after restart. The container lane must preserve those results and measurably close a gap the native lane leaves open. Examples are isolated backup/independent-host restore, interruption recovery, or a smaller install/rebuild/cleanup cost, as required by catalogs/landscape/hosting-practice.json comparison_required. A defined production, remote or GPU requirement that the native fixture cannot meet would also reopen the layer. The existing native portability check is python3 -m unittest discover -s blueprints/convergence-practice/application-delivery -p 'test_portability.py' -v.

Open gaps:
- Recovery is not_established for nextjs, react, fastapi and postgresql (catalogs/foundation/decisions.json lines 1695-1772). No backup/independent-host restore acceptance exists (application-delivery/README.md lines 135-137).
- No production authentication, hosted deployment, production load test or cloud hosting is established. The PostgreSQL build is a synthetic loopback trust-auth fixture without TLS, not a production service (README lines 127-133).
- Migration reversal proves schema reversal only, not user-data recovery or production-safe rollback (README lines 150-152).
- No container lane (Docker/Compose, Podman/Quadlet, Dev Containers) has been run against this workload, so native versus container is unmeasured (docs/hosting-container-practice.md lines 5-6).
- The candidate list omits Dagu/systemd, which hosting-practice.json cites as the retained service-supervision lanes (line 6). This packet does not establish their fit to the application's supervision.
- Apple container (sota_components_not_in_candidates) has separate Mac-only named-volume persistence evidence (decisions.json lines 1779-1838) and does not qualify Linux/WSL hosting.
- The WSL run used explicit platform adaptations: Linux Chrome for Testing 153.0.8010.52 instead of the Mac's 153.0.8010.53, Python 3.13.15 instead of 3.14.7, and direct PostgreSQL build commands because of the MAKELEVEL defect (wsl-application/README.md lines 15-20 and 78-83). Another PC needs its own evidence.
- The TIME-WAIT bind-preflight rejection seen on WSL is recorded as a retained operational limit (wsl-application/README.md lines 150-153).
- Independent-host backup restoration, host-loss recovery and production authentication are not established.
- The accepted database configuration uses loopback and local trust and omits TLS, ICU, readline and zlib; it does not qualify a production database profile.
- No matched native-versus-container application comparison establishes deployment, recovery, isolation or operating-cost superiority.
- Cloud hosting, remote-team access, GPU compatibility, production load and paid-provider acceptance remain unqualified.
- The retained TypeScript generator incompatibility and initial container bind failure remain failures of their specific attempted configurations.
- The WSL recipe records clean-build and TIME-WAIT issues with explicit recovery procedures; successful execution does not imply every historical recipe invocation succeeds unchanged.

Lanes: same_winner (claude: foundation-hosting-services-20260922; codex: foundation-hosting-services-20260922)

#### Instructions and skills (instructions-skills)

- affaan-m/ECC @ dd6ee538aee0f548d4a6b520118f875431fd749e — The requirement is concise canonical rules plus useful upstream procedures, without turning on whole instruction or plugin catalogs. c4, c8 and c3 are the only adopted candidates whose retained records show selected, pinned skill files installed on this host, hash-matched and observed in native client discovery. Every other adopted candidate stops at source review, or at a format validator that supplies no procedure.

c4, ECC selected skills:
- Only two ECC skills were installed. The raw receipt at evidence/receipts/native-claude-profile-20260920.json lines 27-41 records search-first (sha256 d66d7442..., 8021 bytes) and iterative-retrieval (sha256 b453b16d..., 6786 bytes), both at source commit 2b6e8397 with native_discovery true.
- catalogs/foundation/community-practice-20260920.json lines 313-341 and 684 match this and exclude the full ECC and VoltAgent bundles. docs/foundation-closure-20260921.md line 21 says both skills appear once each in native Claude discovery.
- Observed level: installation, a hash match and native Claude discovery. No task trial was run.
- Caveat: the canonical on-demand-guidance decision still records ECC as selection 'optional', review_status 'source_review', with the use stage 'not_applicable' (catalogs/foundation/decisions.json lines 246-247 and 276-279).

c8, TypeSafe skill:
- Pinned at 65a39f39 with a recorded SKILL.md hash (catalogs/landscape/native-practice.json lines 32-36). It was installed with the recorded npx skills commands, and all three global SKILL.md hashes plus the project copy matched (lines 21-27).
- blueprints/native-skill-practice/native-receipt.json shows the following:
  - Claude's initialization listed the skill (lines 199-203).
  - The Claude worker read SKILL.md from disk because the body was not visibly preloaded (lines 205 and 277).
  - The corrected Codex run loaded the project copy and completed 8 cases (lines 81 and 107).
  - The first Codex attempt failed source access, and that failure is retained (lines 48-57).
- blueprints/native-skill-practice/typesafe-result.json records 8 requests and 0 service errors. The model matched 7 of 8 frozen labels, against 3 of 8 for weak literal containment. Promptfoo exited 100, and the C4 disagreement is kept.
- The 'uncached' wording comes from blueprints/native-skill-practice/README.md line 75 and native-practice.json line 54, not from the result file.
- This is a small provider diagnostic, not a general ranking.

c3, OpenAI gh-fix-ci and security-best-practices:
- Both are pinned at 49f948fa and were installed with the same recorded npx skills command, with hashes matched (native-practice.json lines 21-27, 74-76 and 129-131).
- Both passed skills-ref validation with exit 0 (native-receipt.json lines 29-38). Both appear in Claude's initialization listing (native-receipt.json lines 199-203).
- The unchanged gh-fix-ci helper ran against PR #55 and exited 0 with 'PR #55: no failing checks detected.' A separate native query saw five SUCCESS checks (native-practice.json lines 95-112).
- security-best-practices has only been installed and discovered (line 152).

All three records limit activation to named skills loaded for relevant tasks (native-practice.json lines 49, 88 and 144), which is what this layer asks for. The winner set takes the weakest class among them, local_integration: host-local install, hash and discovery, plus bounded helper and provider runs. No winner has a measured improvement in task quality or cost.

Record conflict: the foundation closure's Instructions-and-skills row names 'ECC; Anthropic skills; Agent Skills' (docs/foundation-closure-20260921.md line 53) and does not name TypeSafe or the OpenAI skills. This verdict follows the later, more specific native-practice.json receipts. The conflict is kept in open_gaps rather than hidden.
- candidate:typesafe-ai-skills @ unpinned — The requirement is concise canonical rules plus useful upstream procedures, without turning on whole instruction or plugin catalogs. c4, c8 and c3 are the only adopted candidates whose retained records show selected, pinned skill files installed on this host, hash-matched and observed in native client discovery. Every other adopted candidate stops at source review, or at a format validator that supplies no procedure.

c4, ECC selected skills:
- Only two ECC skills were installed. The raw receipt at evidence/receipts/native-claude-profile-20260920.json lines 27-41 records search-first (sha256 d66d7442..., 8021 bytes) and iterative-retrieval (sha256 b453b16d..., 6786 bytes), both at source commit 2b6e8397 with native_discovery true.
- catalogs/foundation/community-practice-20260920.json lines 313-341 and 684 match this and exclude the full ECC and VoltAgent bundles. docs/foundation-closure-20260921.md line 21 says both skills appear once each in native Claude discovery.
- Observed level: installation, a hash match and native Claude discovery. No task trial was run.
- Caveat: the canonical on-demand-guidance decision still records ECC as selection 'optional', review_status 'source_review', with the use stage 'not_applicable' (catalogs/foundation/decisions.json lines 246-247 and 276-279).

c8, TypeSafe skill:
- Pinned at 65a39f39 with a recorded SKILL.md hash (catalogs/landscape/native-practice.json lines 32-36). It was installed with the recorded npx skills commands, and all three global SKILL.md hashes plus the project copy matched (lines 21-27).
- blueprints/native-skill-practice/native-receipt.json shows the following:
  - Claude's initialization listed the skill (lines 199-203).
  - The Claude worker read SKILL.md from disk because the body was not visibly preloaded (lines 205 and 277).
  - The corrected Codex run loaded the project copy and completed 8 cases (lines 81 and 107).
  - The first Codex attempt failed source access, and that failure is retained (lines 48-57).
- blueprints/native-skill-practice/typesafe-result.json records 8 requests and 0 service errors. The model matched 7 of 8 frozen labels, against 3 of 8 for weak literal containment. Promptfoo exited 100, and the C4 disagreement is kept.
- The 'uncached' wording comes from blueprints/native-skill-practice/README.md line 75 and native-practice.json line 54, not from the result file.
- This is a small provider diagnostic, not a general ranking.

c3, OpenAI gh-fix-ci and security-best-practices:
- Both are pinned at 49f948fa and were installed with the same recorded npx skills command, with hashes matched (native-practice.json lines 21-27, 74-76 and 129-131).
- Both passed skills-ref validation with exit 0 (native-receipt.json lines 29-38). Both appear in Claude's initialization listing (native-receipt.json lines 199-203).
- The unchanged gh-fix-ci helper ran against PR #55 and exited 0 with 'PR #55: no failing checks detected.' A separate native query saw five SUCCESS checks (native-practice.json lines 95-112).
- security-best-practices has only been installed and discovered (line 152).

All three records limit activation to named skills loaded for relevant tasks (native-practice.json lines 49, 88 and 144), which is what this layer asks for. The winner set takes the weakest class among them, local_integration: host-local install, hash and discovery, plus bounded helper and provider runs. No winner has a measured improvement in task quality or cost.

Record conflict: the foundation closure's Instructions-and-skills row names 'ECC; Anthropic skills; Agent Skills' (docs/foundation-closure-20260921.md line 53) and does not name TypeSafe or the OpenAI skills. This verdict follows the later, more specific native-practice.json receipts. The conflict is kept in open_gaps rather than hidden.
- candidate:openai-skills @ unpinned — The requirement is concise canonical rules plus useful upstream procedures, without turning on whole instruction or plugin catalogs. c4, c8 and c3 are the only adopted candidates whose retained records show selected, pinned skill files installed on this host, hash-matched and observed in native client discovery. Every other adopted candidate stops at source review, or at a format validator that supplies no procedure.

c4, ECC selected skills:
- Only two ECC skills were installed. The raw receipt at evidence/receipts/native-claude-profile-20260920.json lines 27-41 records search-first (sha256 d66d7442..., 8021 bytes) and iterative-retrieval (sha256 b453b16d..., 6786 bytes), both at source commit 2b6e8397 with native_discovery true.
- catalogs/foundation/community-practice-20260920.json lines 313-341 and 684 match this and exclude the full ECC and VoltAgent bundles. docs/foundation-closure-20260921.md line 21 says both skills appear once each in native Claude discovery.
- Observed level: installation, a hash match and native Claude discovery. No task trial was run.
- Caveat: the canonical on-demand-guidance decision still records ECC as selection 'optional', review_status 'source_review', with the use stage 'not_applicable' (catalogs/foundation/decisions.json lines 246-247 and 276-279).

c8, TypeSafe skill:
- Pinned at 65a39f39 with a recorded SKILL.md hash (catalogs/landscape/native-practice.json lines 32-36). It was installed with the recorded npx skills commands, and all three global SKILL.md hashes plus the project copy matched (lines 21-27).
- blueprints/native-skill-practice/native-receipt.json shows the following:
  - Claude's initialization listed the skill (lines 199-203).
  - The Claude worker read SKILL.md from disk because the body was not visibly preloaded (lines 205 and 277).
  - The corrected Codex run loaded the project copy and completed 8 cases (lines 81 and 107).
  - The first Codex attempt failed source access, and that failure is retained (lines 48-57).
- blueprints/native-skill-practice/typesafe-result.json records 8 requests and 0 service errors. The model matched 7 of 8 frozen labels, against 3 of 8 for weak literal containment. Promptfoo exited 100, and the C4 disagreement is kept.
- The 'uncached' wording comes from blueprints/native-skill-practice/README.md line 75 and native-practice.json line 54, not from the result file.
- This is a small provider diagnostic, not a general ranking.

c3, OpenAI gh-fix-ci and security-best-practices:
- Both are pinned at 49f948fa and were installed with the same recorded npx skills command, with hashes matched (native-practice.json lines 21-27, 74-76 and 129-131).
- Both passed skills-ref validation with exit 0 (native-receipt.json lines 29-38). Both appear in Claude's initialization listing (native-receipt.json lines 199-203).
- The unchanged gh-fix-ci helper ran against PR #55 and exited 0 with 'PR #55: no failing checks detected.' A separate native query saw five SUCCESS checks (native-practice.json lines 95-112).
- security-best-practices has only been installed and discovered (line 152).

All three records limit activation to named skills loaded for relevant tasks (native-practice.json lines 49, 88 and 144), which is what this layer asks for. The winner set takes the weakest class among them, local_integration: host-local install, hash and discovery, plus bounded helper and provider runs. No winner has a measured improvement in task quality or cost.

Record conflict: the foundation closure's Instructions-and-skills row names 'ECC; Anthropic skills; Agent Skills' (docs/foundation-closure-20260921.md line 53) and does not name TypeSafe or the OpenAI skills. This verdict follows the later, more specific native-practice.json receipts. The conflict is kept in open_gaps rather than hidden.

Alternatives:
- Agent Skills reference tools (conditional) — This is a format validator, not a source of procedures.
- catalogs/foundation/decisions.json lines 296-336 (portable-skill-reference) gives selection 'conditional' and review_status accepted_within_scope. The evidence_scope is 'The native reference validator accepted and rendered one selected skill', with the limitation that the format 'does not define every Codex or Claude extension'.
- catalogs/landscape/native-practice.json lines 216-227 says the repository has 'no SKILL.md additions to install'. It gives evidence_level 'source_review_and_installed_help_observation' and says reference validation 'does not establish Claude/Codex extension support or native discovery'.
- It supports the winners: skills-ref exited 0 for all three installed skills (blueprints/native-skill-practice/native-receipt.json lines 29-38). It still delivers no task procedures itself.
- Correction from the earlier round: the evidence class is local_integration, a host-local validator run, not native_proven.
- Shan Claude best practice (conditional) — It is kept only as a reference.
- docs/foundation-closure-20260921.md line 22 says 'source review is its acceptance level', and community-practice-20260920.json lines 120-128 gives decision 'retain' with evidence_level source_review.
- Foundation closure lines 37-39 warn that its cross-model example names older models and uses mandatory interview/restart sequences that should not be imported.
- decisions.json lines 286-289 gives its use stage as 'not_applicable'.
- No installation or discovery is recorded.
- The packet pin is 15969ed2, but the reviewed pin is bde3f031, so the current head has not been re-reviewed.
- Trail of Bits security skills (conditional) — catalogs/landscape/native-practice.json lines 199-214 gives decision 'conditional' with evidence_level source_review for differential-review at pin 32e34f81. Its mandatory full reporting and history phases, plus an optional plugin agent, make it heavier than the existing bounded review. The record says 'do not import the whole pack as a default'. No installation, discovery or task trial is retained.
- Vercel frontend skills (conditional) — catalogs/landscape/native-practice.json lines 166-182 gives decision 'conditional' with evidence_level source_review at pin 063bee94. The UI skill fetches mutable external rules. The record says the 70-rule React guide is not needed for the current static catalog. No installation, discovery or task trial is retained.
- Claude Code Templates (unqualified) — Its only retained record is the component_id in the on-demand-guidance decision (catalogs/foundation/decisions.json line 251). That decision's use stage for it is 'not_applicable' (lines 281-285), and its evidence_scope describes ECC files, not this repository. No selected file, pin review, installation or discovery observation exists in the referenced evidence.
- VoltAgent subagent collection (conditional) — Not adopted. It is a 'Conditional reference; inspect tools, model and permissions per role. A reviewer title does not enforce read-only behavior' (docs/foundation-closure-20260921.md line 24). community-practice-20260920.json says no role is installed. It covers role contracts rather than on-demand skill procedures, and no evidence shows it beating the winners.
- Anthropic webapp-testing skill (overlap) — Not adopted in the packet.
- catalogs/landscape/native-practice.json lines 183-198 gives decision 'overlap' at pin 34040c9c: webapp-testing duplicates the accepted agent-browser and Playwright lanes. No evidence shows that its always-wait-for-networkidle instruction beats task-specific readiness checks.
- The foundation closure does name 'Anthropic skills' in this layer's row (docs/foundation-closure-20260921.md line 53). Line 26 calls Anthropic skills an 'On-demand reference' and says 'Existing Claude sync already exposes selected official skills'.
- No receipt among the files read shows which official skills are synced, their pins or hashes, or their discovery. That claim is therefore documented, not observed, and it does not outrank the winners' install, hash and discovery receipts.

Overturn when: Two checks could change this verdict.

1. Record-integrity check: python3 -m unittest tests.test_landscape. Its test_native_skills_keep_source_pins_limits_and_local_evidence (tests/test_landscape.py lines 316-339) rejects a native-practice skill entry that has no full source commit, no content hash, no limits, or a missing evidence file. A failure against the current catalogs/landscape/native-practice.json, or a fresh re-hash or discovery check showing that the installed ECC, TypeSafe or OpenAI files no longer match their recorded pins and hashes, would remove that winner.

2. Task-performance check: no retained fixture can yet measure a skill arm.
- blueprints/native-skill-practice/catalog-cases.json is an eight-case claim-classification diagnostic about catalog evidence.
- blueprints/native-skill-practice/test-contract.cjs only checks the gate and parser contract for the 16-case cases.json (lines 5-7 and 66-77).
- A new frozen case set must be authored before inference, following the catalog-cases.json labelling procedure (README lines 45-50). Examples: a security-sensitive diff for Trail of Bits differential-review, or an accessibility review for the Vercel UI skill.
- If a native trial on that set, with retained receipts, shows a challenger producing more supported findings with fewer rule conflicts than the selected skills, the verdict would be overturned. node --test blueprints/native-skill-practice/test-contract.cjs should keep passing.

Open gaps:
- No retained fixture measures skill-arm task performance. catalog-cases.json covers claim classification, and test-contract.cjs checks only the gate and parser contract on cases.json, so the overturn trial needs a new frozen case set.
- No winner has a measured improvement in task quality or provider cost. community-practice-20260920.json records none, and native-practice.json lines 53, 93 and 149 say the same.
- Record conflict: the foundation closure's layer row (docs/foundation-closure-20260921.md line 53) names ECC, Anthropic skills and Agent Skills, not TypeSafe or the OpenAI skills. Line 26 says the Claude sync already exposes selected official Anthropic skills, but no receipt for that sync (pins, hashes, discovery) was found in the files read.
- ECC: the canonical on-demand-guidance decision still records selection 'optional', review_status 'source_review' and use stage 'not_applicable' (decisions.json lines 246-247 and 276-279). Only installation, hash and Claude discovery are established (native-claude-profile-20260920.json lines 27-41). No task-triggered activation or Codex discovery is cited.
- Discovery is client-level, not worker-level. Claude's initialization listed all three native-practice skills (native-receipt.json lines 199-203), but the worker context did not list them and read TypeSafe from disk (lines 277-284). Full body preload is not established (line 205).
- gh-fix-ci has been run only on the clean-check path. Failing-log extraction, repair quality and native agent activation are unqualified (native-practice.json lines 89-124).
- security-best-practices has installation and discovery only. Finding quality and false-positive control are unmeasured. Its references name FastAPI 0.128.x and Next.js 16.1.x, while the foundation pins are 0.141.1 and 16.3.5 (native-practice.json line 146).
- The TypeSafe 7/8 result covers eight selected cases. C4 disagrees with its frozen label, and the comparison baseline is weak literal containment, not a native coding-agent baseline.
- The packet pins for c4 (dd6ee538) and c5 (15969ed2) differ from the reviewed pins in the evidence (ECC 2b6e8397, Shan bde3f031), so the current heads have not been source-reviewed.
- c7 (claude-code-templates) has no source review of a selected file in the referenced evidence.
- Evidence from this host does not carry over to a new PC's native discovery or runtime.
- lanes disagreed: claude=affaan-m/ECC,candidate:openai-skills,candidate:typesafe-ai-skills; codex=affaan-m/ECC,candidate:openai-skills,skills-ref; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-instructions-skills-20260922.json

Lanes: disagree (claude: foundation-instructions-skills-20260922; codex: foundation-instructions-skills-20260922)

#### Isolation (isolation)

- worktrunk @ 0.79.0 — The requirement has two parts, so the winners are a pair. c5 (Worktrunk) keeps edits apart. c6 (sandbox-runtime 0.0.77) enforces a real filesystem and network boundary, and is applied only to the command and policy a task names. Both rest on native execution run on this Linux/WSL host.

c6 network side: evidence/receipts/native-sandbox-network-20260920.json (kind native_cli_e2e, package_version 0.0.77 at line 18) records three results. The allowed loopback request reached the owned server (server_requests_after 1). The explicit-deny and default-deny requests both exited 22 with proxy_403_reported true, and the server count stayed at 1.

c6 filesystem side: evidence/receipts/runtime-tools.json data.sandbox (lines 25-32, recorded 2026-09-19) records allowed_write_exit 0, denied_read_exit 1, separate_denied_write_exit 1 and host_file_created false. That receipt does not record a package version. On Linux, sandbox-runtime is built on bubblewrap and socat (catalogs/us-equities/agents-operations.json line 796), so bubblewrap is its underlying mechanism, not a separate alternative. catalogs/foundation/decisions.json scoped-os-isolation (lines 523-563) records selection "conditional" with activation "Apply native restrictions only to the owned command and policy required by the task". That matches the requirement's "only where the selected task requires enforced restrictions".

c5, corrected for version: the pinned 0.79.0 is qualified by c5's recipe_ref, recipes/native-upgrades-20260921.md (line 14: disposable worktree create/list/remove). The retained artifact evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json (lines 69-127, observed 2026-09-21, previous_version 0.78.0, installed_version 0.79.0) records native switch --create / list / remove on an owned disposable fixture with hooks disabled. It shows exit codes 0, 0, 0; listed_worktrees_before_cleanup 2; after_cleanup_worktrees 1; branch deleted; git_status_porcelain ""; and removed_worktree_directory_absent true. The same artifact also records a local regression comparison (lines 103-120): 0.78.0's --no-cd -x pwd ran in the invoking repository (baseline_behavior_passed false), while 0.79.0 ran in the selected worktree (candidate_behavior_passed true). The earlier worktrunk-owned-lifecycle check in evidence/receipts/token-native-retained-functional-20260920.json (lines 414-423: created_worktrees 2, remaining_worktrees 1, hooks_disabled, disposable_repository_only) is earlier-version evidence. It was recorded 2026-09-20, before 0.79.0 was released on 2026-09-21, and the receipt records no version. catalogs/foundation/decisions.json owned-worktrees (lines 478-521) lists isolation among its layer_ids with selection default. Its lifecycle stage_refs list only the "use" stage. docs/token-native-saturation.md line 121 gives worktrunk the role "optional" with stages "use, cleanup".

The packet's limitation stands: a worktree separates edits but is not a security sandbox. That is why c6 is needed wherever restrictions must be enforced. No other adopted candidate has native evidence on this host of an enforced filesystem or network restriction.
- sandbox-runtime @ 0.0.77 — The requirement has two parts, so the winners are a pair. c5 (Worktrunk) keeps edits apart. c6 (sandbox-runtime 0.0.77) enforces a real filesystem and network boundary, and is applied only to the command and policy a task names. Both rest on native execution run on this Linux/WSL host.

c6 network side: evidence/receipts/native-sandbox-network-20260920.json (kind native_cli_e2e, package_version 0.0.77 at line 18) records three results. The allowed loopback request reached the owned server (server_requests_after 1). The explicit-deny and default-deny requests both exited 22 with proxy_403_reported true, and the server count stayed at 1.

c6 filesystem side: evidence/receipts/runtime-tools.json data.sandbox (lines 25-32, recorded 2026-09-19) records allowed_write_exit 0, denied_read_exit 1, separate_denied_write_exit 1 and host_file_created false. That receipt does not record a package version. On Linux, sandbox-runtime is built on bubblewrap and socat (catalogs/us-equities/agents-operations.json line 796), so bubblewrap is its underlying mechanism, not a separate alternative. catalogs/foundation/decisions.json scoped-os-isolation (lines 523-563) records selection "conditional" with activation "Apply native restrictions only to the owned command and policy required by the task". That matches the requirement's "only where the selected task requires enforced restrictions".

c5, corrected for version: the pinned 0.79.0 is qualified by c5's recipe_ref, recipes/native-upgrades-20260921.md (line 14: disposable worktree create/list/remove). The retained artifact evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json (lines 69-127, observed 2026-09-21, previous_version 0.78.0, installed_version 0.79.0) records native switch --create / list / remove on an owned disposable fixture with hooks disabled. It shows exit codes 0, 0, 0; listed_worktrees_before_cleanup 2; after_cleanup_worktrees 1; branch deleted; git_status_porcelain ""; and removed_worktree_directory_absent true. The same artifact also records a local regression comparison (lines 103-120): 0.78.0's --no-cd -x pwd ran in the invoking repository (baseline_behavior_passed false), while 0.79.0 ran in the selected worktree (candidate_behavior_passed true). The earlier worktrunk-owned-lifecycle check in evidence/receipts/token-native-retained-functional-20260920.json (lines 414-423: created_worktrees 2, remaining_worktrees 1, hooks_disabled, disposable_repository_only) is earlier-version evidence. It was recorded 2026-09-20, before 0.79.0 was released on 2026-09-21, and the receipt records no version. catalogs/foundation/decisions.json owned-worktrees (lines 478-521) lists isolation among its layer_ids with selection default. Its lifecycle stage_refs list only the "use" stage. docs/token-native-saturation.md line 121 gives worktrunk the role "optional" with stages "use, cleanup".

The packet's limitation stands: a worktree separates edits but is not a security sandbox. That is why c6 is needed wherever restrictions must be enforced. No other adopted candidate has native evidence on this host of an enforced filesystem or network restriction.

Alternatives:
- Apple Container (conditional) — Its native execution evidence covers only storage persistence on a Mac. A PostgreSQL row survived a native stop/start in an ext4 named volume, and the owned fixtures were removed. No filesystem or network restriction boundary was tested. The Documents bind mount stalled, and recovery is not_established (decisions.json lines 1831-1834). It is Mac-only and does not apply to the Linux/WSL worker hosts. decisions.json lines 1787-1789 record it as optional, for use only with the matching Mac recipe.
- Podman / Quadlet (conditional) — The catalog records decision 'conditional' (hosting-practice.json line 36). The evidence is source review only, and native_acceptance is not_established (lines 31-42). It is a rootless OCI challenger for cases where the requirement is privilege or systemd service management. Image, networking, volume, GPU and Docker-API compatibility have not been measured. No container installation or trial was performed (hosting-practice.json line 5). Its OCI boundary is untested, not failed.
- Docker Engine / Moby (conditional) — The catalog records decision 'conditional' (hosting-practice.json line 14). The evidence is source review only, and native_acceptance is not_established (lines 9-19). The rationale says no matched result shows better reproduction or recovery than the accepted native services. hosting-container-practice.md lines 43-44 say hostile-code isolation needs its own evidence. The OCI boundary it would add is untested here: not failed, but not established.
- E2B (conditional) — Source review only (agents-operations.json lines 647-686, evidence_level source_review at line 661). Its native workflow commands are marked 'Prospective commands; not executed' (line 666), and the record says 'Import is not sandbox E2E.' (line 675). Using it needs an E2B account credential and a cloud usage budget, and self-hosting targets AWS/GCP infrastructure (lines 671, 676). Its conditional trigger is untrusted generated code that needs a separate VM boundary, and no retained task on this layer shows that need.
- gVisor (out_of_scope) — Not adopted. The decision is defer_oci_platform, with research-only status (hosting-source-review.json lines 104-122). Its stronger application-kernel boundary needs an OCI bundle or runtime plus workload and platform acceptance. The same record (line 137) says the existing bubblewrap, which is also sandbox-runtime's Linux backend, was sufficient for an isolated ai-memory restore with all namespaces and a read-only host root. It also says no containerized hosting platform currently requires runsc.

Overturn when: Either of two checks would change this verdict.

1. A task requires a hostile-code, VM/OCI or resource-limit boundary, and a challenger (Podman or Docker rootless, E2B, or gVisor runsc) passes a workload, network, resource, cleanup and host-compatibility trial. The trial must be recorded against the lifecycle stages in blueprints/token-native-focus/saturation-audit.json. It must also repeat the retained sandbox-runtime assertions: filesystem permit/deny, and loopback HTTP allowed/explicit-deny/default-deny.

2. A sandbox-runtime 0.0.77 rerun fails those same assertions, or a Worktrunk 0.79.0 owned create/list/remove on a disposable fixture fails to leave one worktree, a clean status and an absent removed directory.

The container-storage recipe at blueprints/convergence-practice/container-storage/README.md is the existing model for such a native fixture.

Open gaps:
- sandbox-runtime network evidence covers only temporary IPv4 loopback HTTP on this Linux/WSL host. TLS, SOCKS, DNS rebinding, IPv6, remote hosts and general sandbox escape are not established (native-sandbox-network-20260920.json limitations).
- The filesystem receipt (runtime-tools.json, recorded 2026-09-19) records no sandbox-runtime version. That the filesystem permit/deny results apply to the 0.0.77 pin is inferred, not recorded. Only the network receipt names 0.0.77.
- The first sandboxed request fails because upstream starts its socat listeners in the background without waiting for readiness. The accepted command relies on bounded curl connection-refused retries.
- An overlapping denied-read/write path produced an ephemeral hidden mount: the write exited 0 while the host stayed unchanged (runtime-tools.json line 30). Direct denial is shown only by a separate fixture.
- No candidate has a resource-limit, hostile-workload or VM-boundary qualification.
- The Worktrunk 0.79.0 qualification covers only a disposable owned repository with hooks disabled, no remote and an isolated config. Merge, unmerged-branch deletion, the interactive picker, shell integration and user-repository workflows were not qualified (orx-worktrunk-upgrades.json lines 122-127). The Rust upstream suite was not run because cargo and rustc were absent. The 0.78.0/0.79.0 directory comparison is a local regression check against the upstream test oracle, not an executed upstream test.
- The 2026-09-20 worktrunk-owned-lifecycle pass ran before 0.79.0 existed. It is earlier-version evidence, and the receipt records no version.
- 'Dirty removal was refused without loss' appears only as a summary sentence (decisions.json line 499; packet c5 evidence_scope). I found no opened receipt or saturation-audit assertion for it, so it is not part of the overturn metric.
- Crash cleanup is not proven. The owned-worktrees lifecycle stage_refs list only 'use' (decisions.json lines 512-517); the 'cleanup' stage appears only in the saturation table (docs/token-native-saturation.md line 121, role optional).
- Worktrees do not isolate permissions, accounts, global settings or shared services. Ordinary native or Dagu processes are not automatically sandboxed, and nothing shows that every Claude or Codex command runs under sandbox-runtime.
- Podman, Docker and E2B have no native execution on this host. Their boundaries are untested, not failed.
- Correction to older records: runtime-tools.json line 13 says 'Sandbox network denial configured but not separately exercised', and catalogs/us-equities/agents-operations.json line 800 says 'network denial was configured but not independently exercised'. The later native-sandbox-network-20260920 receipt exercised HTTP allow and deny, so both lines are stale for HTTP only.
- Worktrees do not isolate permissions, accounts, global configuration or shared services; crash cleanup preserving dirty and unrelated state remains unproven.
- Sandbox acceptance covers selected filesystem operations and Linux/WSL IPv4 loopback HTTP proxy policy. TLS, SOCKS, DNS rebinding, IPv6, remote hosts, resource limits and general escape resistance remain unqualified.
- The HTTP fixture initially failed because proxy readiness raced client startup; acceptance used bounded connection-refused retries.
- Overlapping read/write exclusions allowed an ephemeral write without changing the host; direct write denial was established only by the separate protected-write fixture.
- Ordinary native clients and Dagu processes are not automatically wrapped in sandbox-runtime.
- No retained matched comparison establishes that an OCI or managed VM alternative better satisfies this layer.
- Historical Worktrunk lifecycle evidence does not independently establish identical behavior at the packet's newer pin.

Lanes: same_winner (claude: foundation-isolation-20260922; codex: foundation-isolation-20260922)

#### MCP servers and client surfaces (mcp-surfaces)

- mcporter @ 0.13.13 — mcporter (c3) and MCP Inspector (c1) cover different parts of the requirement. mcporter bridges MCP servers. The Inspector inspects servers and calls their tools. The two do not overlap, so both are selected. Everything below is my own source review of retained receipts. I re-ran nothing.

c3 (mcporter): observability/restart-receipt.json is dated 2026-09-19. Its checked_at is 2026-09-19T15:41:40.084709+00:00 at line 5, and it is kind native_cli_e2e at line 4. The bridge_recovery block at lines 165-179 records mcporter 0.13.13 printing "Single-user daemon started.", discovered_tools 11, native_execute_stdout "bridge-recovered" and automatic_recovery false. The receipt keeps its failures at line 181: the initial bridge call refused stale daemon metadata, and a deliberate start timed out after 45 seconds.

evidence/receipts/current-session-observation-20260920.json (kind native_cli_e2e) adds two bridge calls on 2026-09-20:
- Lines 71-85: `mcporter --config $MCPORTER_CONFIG call context-mode.ctx_execute_file ...` ran with state executed and exit_code 0 at 2026-09-20T14:19:03.815Z. The same project-file read through the directly loaded MCP connection had failed with failed_project_root_scope (lines 56-69). That shows the bridge reaching a server surface the loaded client could not.
- Lines 336-361: `mcporter call --stdio jcodemunch-mcp ...` also returned exit_code 0.

c1 (MCP Inspector): evidence/receipts/token-native-retained-functional-20260920.json is recorded 2026-09-20T04:11:34.336Z and described as a retrospective publication of retained September 20 evidence. Its lines 84-104 (fresh-inspector-context-call) record an upstream_cli run with exit_code 0 and passed true. The checks "expected process exit" and "42 computed" both passed.

Linkage: catalogs/foundation/decisions.json lines 1841-1889 (native-mcp-adapters) ties both components to this layer. blueprints/token-native-focus/saturation-audit.json gives use-stage status accepted_within_scope for the Inspector (lines 4898-4904) and for mcporter (lines 5016-5021). mcporter's use stage cites only restart-receipt.json.

Configuration without adopting an unexamined registry entry rests on source review only. That covers the recipes/README.md commands and the mcp-surface-policy decision (decisions.json lines 2864-2908). The policy treats registries as discovery input only, and its evidence_scope says "no new execution was run to freeze this taxonomy layer". saturation-audit.json lines 4838 and 4943 give current_host_recertified_by_this_audit false for both components.
- mcp-inspector @ 2.7.0 — mcporter (c3) and MCP Inspector (c1) cover different parts of the requirement. mcporter bridges MCP servers. The Inspector inspects servers and calls their tools. The two do not overlap, so both are selected. Everything below is my own source review of retained receipts. I re-ran nothing.

c3 (mcporter): observability/restart-receipt.json is dated 2026-09-19. Its checked_at is 2026-09-19T15:41:40.084709+00:00 at line 5, and it is kind native_cli_e2e at line 4. The bridge_recovery block at lines 165-179 records mcporter 0.13.13 printing "Single-user daemon started.", discovered_tools 11, native_execute_stdout "bridge-recovered" and automatic_recovery false. The receipt keeps its failures at line 181: the initial bridge call refused stale daemon metadata, and a deliberate start timed out after 45 seconds.

evidence/receipts/current-session-observation-20260920.json (kind native_cli_e2e) adds two bridge calls on 2026-09-20:
- Lines 71-85: `mcporter --config $MCPORTER_CONFIG call context-mode.ctx_execute_file ...` ran with state executed and exit_code 0 at 2026-09-20T14:19:03.815Z. The same project-file read through the directly loaded MCP connection had failed with failed_project_root_scope (lines 56-69). That shows the bridge reaching a server surface the loaded client could not.
- Lines 336-361: `mcporter call --stdio jcodemunch-mcp ...` also returned exit_code 0.

c1 (MCP Inspector): evidence/receipts/token-native-retained-functional-20260920.json is recorded 2026-09-20T04:11:34.336Z and described as a retrospective publication of retained September 20 evidence. Its lines 84-104 (fresh-inspector-context-call) record an upstream_cli run with exit_code 0 and passed true. The checks "expected process exit" and "42 computed" both passed.

Linkage: catalogs/foundation/decisions.json lines 1841-1889 (native-mcp-adapters) ties both components to this layer. blueprints/token-native-focus/saturation-audit.json gives use-stage status accepted_within_scope for the Inspector (lines 4898-4904) and for mcporter (lines 5016-5021). mcporter's use stage cites only restart-receipt.json.

Configuration without adopting an unexamined registry entry rests on source review only. That covers the recipes/README.md commands and the mcp-surface-policy decision (decisions.json lines 2864-2908). The policy treats registries as discovery input only, and its evidence_scope says "no new execution was run to freeze this taxonomy layer". saturation-audit.json lines 4838 and 4943 give current_host_recertified_by_this_audit false for both components.

Alternatives:
- Awesome MCP servers registry (out_of_scope) — This is a discovery list of servers. It is not a bridge, inspector or configuration tool, so it cannot do the bridge or inspect work the requirement asks for. The requirement also excludes adopting an unexamined registry entry. The only support for this disposition is the project decision record: catalogs/foundation/decisions.json line 2873 and lines 2883-2885 say registries are discovery input only, that this registry is an unexamined source, and that a listing there does not establish adoption. The packet's evidence_ref for c2, recipes/README.md, never mentions this registry, so I dropped it as support. The evidence_class source_review means a review of that project decision record, not of the registry. No registry entry was reviewed or executed. The registry is untested, which is not the same as failed.

Overturn when: The verdict changes if a current-host re-run of the retained operations fails. The retained operations are the ones listed in blueprints/token-native-focus/saturation-audit.json:
- mcporter use-stage evidence: observability/restart-receipt.json, the bridge recovery (lines 5016-5021).
- mcporter retained_operation_ids: fresh-static-graph, fresh-static-callees, fresh-memory-status and fresh-socraticode-status (lines 4986-4991).
- Inspector: fresh-inspector-context-call (line 4872).
- The mcporter call commands recorded in evidence/receipts/current-session-observation-20260920.json lines 71-85 and 336-361.

That file lists operation IDs only. It defines no commands or checks for the four mcporter IDs. The re-run must therefore be rebuilt from the receipts' recorded commands and checks, not from the fixture alone.

Three further checks would also change the verdict:
- A replacement bridge or inspector passes the same operations with equal or better checks.
- mcporter v0.14.0 fails the bridge call or the daemon-recovery checks that 0.13.13 passed.
- A concrete MCP surface gap that neither tool can serve is closed by a reviewed registry entry that passes the same bridge and inspection acceptance.

Open gaps:
- The retained native runs are from 2026-09-19 (mcporter daemon recovery, restart-receipt.json line 5) and 2026-09-20 (mcporter bridge calls in current-session-observation-20260920.json; Inspector call in token-native-retained-functional-20260920.json, a retrospective publication). None was repeated. saturation-audit.json lines 4838 and 4943 show current_host_recertified_by_this_audit false for both components.
- mcporter is pinned at 0.13.13 while upstream is v0.14.0 (packet pin_behind_upstream true). v0.14.0 is untested, which does not mean it failed.
- saturation-audit.json lines 5023-5042 give not_established for mcporter's persistence, restart, cleanup and recovery lifecycle stages. The bridge recovery in restart-receipt.json was manual (automatic_recovery false). The shared daemon is not an owned disposable service.
- The mcporter retained_operation_ids (fresh-static-graph, fresh-static-callees, fresh-memory-status, fresh-socraticode-status) appear only as IDs in saturation-audit.json. No public receipt I read defines their commands or results.
- The Inspector evidence covers only a stdio arithmetic call ('42 computed'). It does not certify the full client plugin, hooks, project-file scope or desktop connection (saturation-audit.json line 4844). Recipe Inspector calls such as tools/list against other servers did not appear in the receipts I opened.
- The requirement's configure-without-registry-adoption part (mcp-surface-policy) rests on source review only. No new execution was run for this taxonomy layer.
- No measured comparison against other MCP bridges or inspectors was found. The selection rests on retained native execution alone, not on a head-to-head comparison.
- No registry entry from punkpeye/awesome-mcp-servers was reviewed against a concrete MCP surface gap.
- Inspector's arithmetic execution does not establish complete client plugin behavior, hooks, project-file scope or current Desktop connectivity.
- mcporter recovery required intervention after stale metadata refusal and a startup timeout; automatic recovery was not established.
- Shared-daemon isolation, persistence, scoped registration cleanup and changed-process-root recovery lack complete lifecycle acceptance.
- Project configuration policy is documented source evidence; it does not certify every server or client configuration.
- No executed comparison establishes superiority over a reviewed registry candidate or qualifies mcporter v0.14.0 against retained v0.13.13 behavior.
- 1 lane citation(s) name no repository evidence file (an unresolved path or a generated index); the full citations are kept in the sealed lane return

Lanes: same_winner (claude: foundation-mcp-surfaces-20260922; codex: foundation-mcp-surfaces-20260922)

#### Native clients (native-clients)

- claude-code @ 2.1.278 — Claude Code (c7) and Codex (c3) are the only candidates with retained native execution against this requirement: coding and bounded research using existing native accounts, client tools, model choices and resumable sessions. I checked this against the underlying artifacts as well as the prose.

(1) The bounded research task. evidence/artifacts/full-stack-convergence-20260921/native-client-results.json records both clients running the same prompt (prompt_sha256 d24422fd...) with exit_code 0, model_override null and permission_override null. So each client used its own native default model and account home, and the file's limitations state that credential stores were not read or copied. For Claude the observed model was claude-fable-5-1, with tool_count 11, every tool result is_error false and provider_total_tokens 250492. The tools were ToolSearch, Skill, RTK git log, QMD search/get, Serena find_symbol/find_referencing_symbols, the ai-memory query and Context Mode ctx_execute_file/ctx_stats. For Codex the observed model was gpt-6-astra, with tool_count 11, every tool result status completed and provider_total_tokens 255335. This matches docs/full-stack-convergence.md lines 25-35. The 'ultra' effort for that Codex run is stated only in that document, not in the artifact.

(2) Resumable sessions, which I observed in the receipts. blueprints/convergence-practice/native-recovery/claude/receipt.json records status passed on Linux WSL2 with native_version 2.1.278 (Claude Code). The model requested was claude-opus-5 with effort ultracode. The checks same_native_session_id, first_cli_sigint_exit, resumed_cli_exit_zero, checkpoint_unchanged and checkpoint_executed_once are all true. blueprints/convergence-practice/native-recovery/receipt.json records status passed with same_thread_id, same_session_id, model_and_effort_preserved (gpt-6-astra/ultra) and checkpoint_executed_once all true. That Codex run was on macOS with codex-cli 0.155.0-alpha.9.2.

(3) Readiness only. evidence/artifacts/claude-upstream-checks-20260921/results.json shows claude --version returning 2.1.278, codex --version returning codex-cli 0.155.1 and codex login status reporting a ChatGPT login.

The two clients serve independent accounts and model families, so both are retained and neither replaces the other. The winner class is native_proven because both the task run and the resume run are native client executions with retained stream hashes.

This is my own source review. No TypeSafe inference results were supplied. The token figures are retained provider accounting, not my measurement.
- codex @ 0.155.1 — Claude Code (c7) and Codex (c3) are the only candidates with retained native execution against this requirement: coding and bounded research using existing native accounts, client tools, model choices and resumable sessions. I checked this against the underlying artifacts as well as the prose.

(1) The bounded research task. evidence/artifacts/full-stack-convergence-20260921/native-client-results.json records both clients running the same prompt (prompt_sha256 d24422fd...) with exit_code 0, model_override null and permission_override null. So each client used its own native default model and account home, and the file's limitations state that credential stores were not read or copied. For Claude the observed model was claude-fable-5-1, with tool_count 11, every tool result is_error false and provider_total_tokens 250492. The tools were ToolSearch, Skill, RTK git log, QMD search/get, Serena find_symbol/find_referencing_symbols, the ai-memory query and Context Mode ctx_execute_file/ctx_stats. For Codex the observed model was gpt-6-astra, with tool_count 11, every tool result status completed and provider_total_tokens 255335. This matches docs/full-stack-convergence.md lines 25-35. The 'ultra' effort for that Codex run is stated only in that document, not in the artifact.

(2) Resumable sessions, which I observed in the receipts. blueprints/convergence-practice/native-recovery/claude/receipt.json records status passed on Linux WSL2 with native_version 2.1.278 (Claude Code). The model requested was claude-opus-5 with effort ultracode. The checks same_native_session_id, first_cli_sigint_exit, resumed_cli_exit_zero, checkpoint_unchanged and checkpoint_executed_once are all true. blueprints/convergence-practice/native-recovery/receipt.json records status passed with same_thread_id, same_session_id, model_and_effort_preserved (gpt-6-astra/ultra) and checkpoint_executed_once all true. That Codex run was on macOS with codex-cli 0.155.0-alpha.9.2.

(3) Readiness only. evidence/artifacts/claude-upstream-checks-20260921/results.json shows claude --version returning 2.1.278, codex --version returning codex-cli 0.155.1 and codex login status reporting a ChatGPT login.

The two clients serve independent accounts and model families, so both are retained and neither replaces the other. The winner class is native_proven because both the task run and the resume run are native client executions with retained stream hashes.

This is my own source review. No TypeSafe inference results were supplied. The token figures are retained provider accounting, not my measurement.

Alternatives:
- MCPorter native bridge (out_of_scope) — MCPorter is an MCP bridge and client surface. It is not a native coding or research client with accounts, model choice or resumable sessions. catalogs/foundation/decisions.json files native-mcp-adapters under the hosting-services, code-navigation and mcp-surfaces layers, not native-clients, and results.json line 1098 labels it 'MCP client'. Its retained evidence here is readiness only. results.json line 1136 gives evidence_class 'readiness'. Line 1128 shows 'mcporter list' reporting 'Listed 3 servers (2 healthy; 1 errors)' because the context-mode daemon had exited unexpectedly. The receipt, at line 45, adds that '38 zero-exit rows are not 38 functional E2Es'. The pin 0.13.13 is behind upstream v0.14.0. Correction from the earlier round: the class is downgraded from native_proven. The schema enum has no readiness value, so local_integration is the closest one: a zero-exit local command against locally configured servers, not a functional E2E. Bridge-recovery evidence is referenced only by ID in decisions.json, and I did not open it.
- Claude Agent SDK (conditional) — The only evidence is source review. docs/foundation-closure-20260921.md line 82 calls it the preferred Claude SDK candidate when needed, but says it was 'not newly installed or qualified'. The registry label 0.2.157 differs from the GitHub release label 0.2.156. Lines 76-78 limit SDK use to applications that need structured events, custom tools or programmatic session control. No native-account run, tool run or resume run is retained.
- OpenAI Agents SDK (unqualified) — The only evidence is source review. catalogs/us-equities/agents-operations.json line 1611 describes it as API-backed. Line 1624 says 'Prospective commands; not executed'. Lines 1634-1635 say 'No provider API call or model comparison performed' and that it 'Does not inherit Codex account entitlement'. Because it is API-backed, it does not meet the requirement to use existing native accounts. Correction from the earlier round: docs/foundation-closure-20260921.md is dropped from the refs because it does not mention this SDK.
- Letta Code (unqualified) — The retained pinned-source review describes persistent memory and a stateful harness, but records no native model operation, matched task-quality comparison or recovery acceptance. Native-account compatibility and migration benefits remain unestablished.
- Letta V1 legacy server (out_of_scope) — The retained source review identifies V1 as a legacy server preserved on an archive branch, with active development directed to Letta Code. It supplies no executed comparison establishing the required native-client behavior.

Overturn when: Change the verdict only on an executed comparison, not on source review. The condition has two parts. First, the native path cannot deliver a structured-event, custom-tool or programmatic-session capability that an application needs. Second, an SDK arm (Claude Agent SDK or Codex SDK) passes the same frozen recovery fixture on the same account. The fixtures are blueprints/convergence-practice/native-recovery/claude/ (checkpoint, SIGINT, same-session finalize) and blueprints/convergence-practice/native-recovery/ (Codex interrupt and same-thread resume). The SDK arm must match the receipt checks: same session/thread ID, checkpoint unchanged and checkpoint executed once. The offline oracles must still pass: 'python3 -m unittest tests.test_native_recovery' and 'python3 -m unittest discover -s blueprints/convergence-practice/native-recovery/claude -p test_*.py'. A separate trigger: either native client fails a rerun of the same-prompt read-only research task recorded in evidence/artifacts/full-stack-convergence-20260921/native-client-results.json on the intended host. That task has 11 tool results and no tool errors.

Open gaps:
- Codex resume ran on macOS with codex-cli 0.155.0-alpha.9.2 (native-recovery/receipt.json native_version and platform), not on the pinned 0.155.1 or on WSL. Same-thread resume is not established for the pinned version on this host.
- Claude resume ran with only Bash available and MCP tools denied (native-recovery/claude/README.md lines 40-43), using an explicit claude-opus-5/ultracode scoped to that trial (claude/receipt.json limitations). Resume with the full MCP tool set, and with the default model, is not established.
- The research task was one run per client with no matched baseline (native-client-results.json limitations; docs/full-stack-convergence.md line 37). It establishes neither a model-quality ranking nor a causal token difference between the clients.
- The Codex 'ultra' effort for the research task is stated only in docs/full-stack-convergence.md. native-client-results.json records the model but not the effort.
- Remote provider cancellation, cessation of billing, independent-host recovery and power-loss durability are not qualified for either client (both recovery receipts' limitations).
- The readiness rows (claude --version, codex --version, codex login status) are zero-exit checks, not functional E2E (claude-upstream-checks-20260921.json limitations).
- No new-PC or other-host activation evidence is retained. The results are source-host evidence dated 2026-09-20 and 2026-09-21.
- The Claude Agent SDK and OpenAI Agents SDK have no install, account or tool execution evidence.
- No matched execution establishes comparative model quality or causal provider savings across the candidates.
- Same-session recovery is established only for bounded local fixtures. Host failure, independent-host restoration, remote provider cancellation, billing cessation and distributed exactly-once effects remain unqualified.
- The Codex recovery experiment used a different recorded build from the later source-retrieval task; it does not establish recovery on every release.
- Successful selected-tool retrieval does not establish every installed tool, arbitrary coding tasks, all model choices or another host's activation.
- Neither SDK candidate has a retained same-task comparison preserving the required native account and recovery boundaries.
- MCPorter's referenced readiness output includes a Context Mode daemon error; version and listing success do not establish functional bridge recovery.

Lanes: same_winner (claude: foundation-native-clients-20260922; codex: foundation-native-clients-20260922)

#### Observation and optional inference (observation-inference)

- opentelemetry-collector-contrib @ 0.161.0 — The requirement asks for one privacy-filtered local pipeline that observes real native usage and service outcomes. On the retained evidence, three components do that work: the OTel Collector filters and delivers the data, Prometheus stores metrics and Loki stores logs. Grafana, the display layer, was a winner in the earlier round. It is now an alternative, because the evidence shows Loki carries both privacy verification and usage reconciliation, while Grafana's rows show only rendering and query agreement.

(1) Native execution, Collector and Prometheus. In docs/native-telemetry-resolution.md lines 11-45, native Claude Code 2.1.278 exported OTLP over HTTP/protobuf to the loopback Collector with content logging disabled. The task returned 34 input, 16,402 cache-creation, 14,959 cache-read and 787 output tokens, and a native Prometheus query matched them exactly. The retained receipt, observability/backends/telemetry-resolution-20260921.json lines 46-58, records per_type_exact_match true. The query itself is a python3 urllib call at lines 207-211 of that receipt.

(2) Native execution, Loki. observability/receipt.json lines 122-127 record a native Loki query returning total_tokens 80770. Lines 246-256 record the same 80770 after a Collector restart, and say the corrected Loki records held only allowed metadata and omitted bodies. Line 201 records Claude's collected_request_logs_and_metrics_match as true. Lines 296-301 record a passed restart persistence check across the backends.

(3) Privacy filtering rests on weaker evidence. The privacy canary in observability/receipt.json lines 313-329 is labelled 'Independent synthetic review; not an inference task'. It recorded loki_records 1 and forbidden_marker_absent true. Line 24 limits the filters to tested fields and trusted instrumentation, not arbitrary-content DLP. Line 371 retains the earlier privacy failure and its correction. The winner set's evidence class is therefore synthetic, the weakest class among the winners, even though usage fidelity itself is native_proven.

(4) Catalog records. catalogs/us-equities/agents-operations.json lines 859-882 record that the Collector supplies the privacy transform, the Prometheus exporter and delivery to Loki, and that traces are disabled. catalogs/foundation/decisions.json lines 2001-2075 record loopback-usage-observation as accepted_within_scope, selection 'conditional', with 'use' stages for all six components.

The optional llama.cpp route stays conditional on its own workload receipt. All of this is my own source review of dated retained evidence. No TypeSafe inference results were supplied, and I kept no provider judgments.
- prometheus @ 3.14.0 — The requirement asks for one privacy-filtered local pipeline that observes real native usage and service outcomes. On the retained evidence, three components do that work: the OTel Collector filters and delivers the data, Prometheus stores metrics and Loki stores logs. Grafana, the display layer, was a winner in the earlier round. It is now an alternative, because the evidence shows Loki carries both privacy verification and usage reconciliation, while Grafana's rows show only rendering and query agreement.

(1) Native execution, Collector and Prometheus. In docs/native-telemetry-resolution.md lines 11-45, native Claude Code 2.1.278 exported OTLP over HTTP/protobuf to the loopback Collector with content logging disabled. The task returned 34 input, 16,402 cache-creation, 14,959 cache-read and 787 output tokens, and a native Prometheus query matched them exactly. The retained receipt, observability/backends/telemetry-resolution-20260921.json lines 46-58, records per_type_exact_match true. The query itself is a python3 urllib call at lines 207-211 of that receipt.

(2) Native execution, Loki. observability/receipt.json lines 122-127 record a native Loki query returning total_tokens 80770. Lines 246-256 record the same 80770 after a Collector restart, and say the corrected Loki records held only allowed metadata and omitted bodies. Line 201 records Claude's collected_request_logs_and_metrics_match as true. Lines 296-301 record a passed restart persistence check across the backends.

(3) Privacy filtering rests on weaker evidence. The privacy canary in observability/receipt.json lines 313-329 is labelled 'Independent synthetic review; not an inference task'. It recorded loki_records 1 and forbidden_marker_absent true. Line 24 limits the filters to tested fields and trusted instrumentation, not arbitrary-content DLP. Line 371 retains the earlier privacy failure and its correction. The winner set's evidence class is therefore synthetic, the weakest class among the winners, even though usage fidelity itself is native_proven.

(4) Catalog records. catalogs/us-equities/agents-operations.json lines 859-882 record that the Collector supplies the privacy transform, the Prometheus exporter and delivery to Loki, and that traces are disabled. catalogs/foundation/decisions.json lines 2001-2075 record loopback-usage-observation as accepted_within_scope, selection 'conditional', with 'use' stages for all six components.

The optional llama.cpp route stays conditional on its own workload receipt. All of this is my own source review of dated retained evidence. No TypeSafe inference results were supplied, and I kept no provider judgments.
- loki @ 3.7.8 — The requirement asks for one privacy-filtered local pipeline that observes real native usage and service outcomes. On the retained evidence, three components do that work: the OTel Collector filters and delivers the data, Prometheus stores metrics and Loki stores logs. Grafana, the display layer, was a winner in the earlier round. It is now an alternative, because the evidence shows Loki carries both privacy verification and usage reconciliation, while Grafana's rows show only rendering and query agreement.

(1) Native execution, Collector and Prometheus. In docs/native-telemetry-resolution.md lines 11-45, native Claude Code 2.1.278 exported OTLP over HTTP/protobuf to the loopback Collector with content logging disabled. The task returned 34 input, 16,402 cache-creation, 14,959 cache-read and 787 output tokens, and a native Prometheus query matched them exactly. The retained receipt, observability/backends/telemetry-resolution-20260921.json lines 46-58, records per_type_exact_match true. The query itself is a python3 urllib call at lines 207-211 of that receipt.

(2) Native execution, Loki. observability/receipt.json lines 122-127 record a native Loki query returning total_tokens 80770. Lines 246-256 record the same 80770 after a Collector restart, and say the corrected Loki records held only allowed metadata and omitted bodies. Line 201 records Claude's collected_request_logs_and_metrics_match as true. Lines 296-301 record a passed restart persistence check across the backends.

(3) Privacy filtering rests on weaker evidence. The privacy canary in observability/receipt.json lines 313-329 is labelled 'Independent synthetic review; not an inference task'. It recorded loki_records 1 and forbidden_marker_absent true. Line 24 limits the filters to tested fields and trusted instrumentation, not arbitrary-content DLP. Line 371 retains the earlier privacy failure and its correction. The winner set's evidence class is therefore synthetic, the weakest class among the winners, even though usage fidelity itself is native_proven.

(4) Catalog records. catalogs/us-equities/agents-operations.json lines 859-882 record that the Collector supplies the privacy transform, the Prometheus exporter and delivery to Loki, and that traces are disabled. catalogs/foundation/decisions.json lines 2001-2075 record loopback-usage-observation as accepted_within_scope, selection 'conditional', with 'use' stages for all six components.

The optional llama.cpp route stays conditional on its own workload receipt. All of this is my own source review of dated retained evidence. No TypeSafe inference results were supplied, and I kept no provider judgments.

Alternatives:
- Grafana (overlap) — Grafana is the display layer over the winning stores; it neither filters nor stores the data. Its native evidence is panel and query agreement and rendering. Panel queries matched native memory, Qdrant and QMD results (dashboard-rendered-acceptance.md line 29). The Claude panel showed all four categories after the native task (native-telemetry-resolution.md line 45; dashboard-gap-resolution.md line 13). Its provisioned dashboard survived a restart (observability/receipt.json lines 296-301). None of its rows carries the privacy verification or an independent usage reconciliation, so with the winner set capped at three it ranks below Loki. It remains an accepted 'use' stage in the same pipeline (decisions.json lines 2057-2061).
- Alertmanager (conditional) — Alertmanager adds service-outcome alerting on top of the pipeline; it is not the usage-observation path. Native amtool alert query agreed with the UI on a FreeLLMAPI readiness warning (dashboard-rendered-acceptance.md line 31). The firing/resolved route used a dedicated loopback fixture, with external_delivery_tested and elapsed_latency_claimed both false (observability/receipt.json lines 303-311). Scheduled-service and reboot persistence are not qualified (decisions.json line 2036).
- ntfy (conditional) — ntfy delivers notifications; it is not the observation pipeline. Two parts were observed natively: feed delivery (native subscribe showed 23 retained records, dashboard-rendered-acceptance.md line 32) and the Prometheus to Alertmanager to ntfy route (1 firing and 1 resolved notification from a loopback fixture, with no external delivery, observability/receipt.json lines 303-311). The template fix itself rests on two unchanged upstream tests plus a local-integration renderer replay. No post-deployment production webhook was observed (native-telemetry-resolution.md lines 86-98; telemetry-resolution-20260921.json line 76).
- llama.cpp optional local inference (conditional) — llama.cpp covers the requirement's optional model-route clause and is qualified only on its own workload. One pinned Qwen3.8-27B Q4_K_M partial-offload repair passed all 12 original tests on a WSL RTX4090. That is one fixture and one trial, and generation took 179.191 seconds against a 180-second cap. The receipt records no host recovery, concurrent serving or frontier comparison, so the route stays optional, not a default.
- AgentsView (conditional) — AgentsView inspects session history; it is not the usage pipeline. One scoped archive refresh was observed (messages 3,193 to 3,697, 17 identities retained), but the result is a snapshot, not continuous ingestion (dashboard-gap-resolution.md line 11). Automatic archive discovery is unestablished (token-native-saturation.md lines 26-27), and the 0.43.0 pin is behind upstream v0.44.0.
- otel-tui (conditional) — otel-tui was accepted only on a synthetic loopback terminal trace (decisions.json lines 2097-2100). The adopted pipeline has traces disabled (agents-operations.json line 882), so otel-tui has no production trace role. Its only packet ref is the decision record, not an execution receipt.
- Claude HUD (overlap) — Claude HUD is an optional statusline display; it is not the observation pipeline. Native rendering of model, project, context and usage fields was observed in Claude 2.1.278 (foundation-closure-20260921.md lines 109-132). The packet's own limitation says this does not certify every HUD statistic, exact billing reconciliation or automatic compaction.
- Phoenix (unqualified) — The packet marks Phoenix adopted, but its only evidence is a source review. The catalog entry is 'conditional', with evidence_level source_review. Its launch commands are prospective and were not executed, no app was instrumented, and the license is ELv2 (agents-operations.json lines 1246-1268). Phoenix would itself be the local trace store and UI. It needs OTLP/OpenInference instrumentation and a retention policy (lines 1262-1265). The current Collector has traces disabled (line 882), so Phoenix would open a second, trace-level capture path, and auto-instrumentation can capture prompt and tool contents (line 1269).
- OpenLIT (unqualified) — OpenLIT is not adopted and was reviewed only from source. No install, hook invocation, inference or telemetry delivery was executed. Its hook and trace collector would duplicate collection and widen transcript and prompt capture (agents-operations.json lines 1147-1186). That conflicts with keeping one privacy-filtered pipeline.
- SGLang (unqualified) — Serving commands are prospective. No matched task execution, target-hardware compatibility or measured prefix-cache benefit establishes a better optional route.

Overturn when: Change the verdict if a fresh native reconciliation no longer matches.

1. Run a fresh native Claude task. Either use the claude -p invocation in docs/native-telemetry-resolution.md lines 22-27, or have the task read fixtures/observability-check.json, the prompt fixture of the native client acceptance recorded in observability/receipt.json lines 164 and 236-244. Then run the retained Prometheus query from observability/backends/telemetry-resolution-20260921.json lines 207-211: python3 -c "import urllib.request,urllib.parse,sys;sys.stdout.buffer.write(urllib.request.urlopen(\"http://127.0.0.1:19090/api/v1/query?\"+urllib.parse.urlencode({\"query\":\"sum by (type) (ecosystem_claude_code_token_usage_tokens_total)\"}),timeout=20).read())". The verdict changes if the input, cache-creation, cache-read and output values differ from the task's returned usage.

2. The verdict also changes if the native Loki receipt query (observability/receipt.json lines 122-127) no longer returns the per-receipt totals that were written.

3. Recovery: re-run python3 observability/backends/check_persistence.py with a fresh --evidence-dir and the local Grafana credential file. The verdict changes if its prometheus, loki or grafana checks fail.

4. A new privacy canary that shows a content field passing the Collector transform also changes the verdict. The repository has no script for this; the receipt records only a reviewer-run canary and a historical query.

5. If a required trace or evaluation question cannot be answered by this pipeline, OpenLIT or Phoenix would have to pass the same fidelity, privacy and recovery comparison on the same native task without duplicate capture.

For the optional inference route, re-run python3 blueprints/convergence-practice/gpu-inference/qualify.py on a newly frozen representative workload.

python3 -m unittest tests.test_observability is only an offline regression. It covers process identity, write_observation redaction and atomic no-overwrite writes, the receipt_id query text in the Grafana dashboard panel, and refusal to replay persistence. It does not check live reconciliation or the Collector's privacy.

Open gaps:
- The privacy-filter evidence is one synthetic canary reviewed by a reviewer (observability/receipt.json lines 313-329). The repository has no script that re-runs it, and it covers only tested fields and trusted instrumentation, not arbitrary-content DLP (line 24).
- No script or test in the repository re-runs the native usage reconciliation end to end. It exists only as retained commands in docs/native-telemetry-resolution.md lines 22-30 and observability/backends/telemetry-resolution-20260921.json lines 207-211 and 269-306.
- Scheduled-service and reboot persistence are not qualified (decisions.json line 2036). check_persistence.py covers one user-service restart only.
- Missing task attribution: the Prometheus counters before the task already held another Claude process's usage, so only the after-snapshot match per category is established (native-telemetry-resolution.md lines 47-49; telemetry-resolution-20260921.json line 344).
- The SDK receipt lane has no automatic spool expiry and no loss/recovery acceptance under a full disk or an extended outage (observability/receipt.json line 258).
- Traces are disabled and no trace database is deployed, so the pipeline answers no trace questions (agents-operations.json line 882).
- No latency or elapsed-time measurement is claimed for notifications (observability/receipt.json line 311).
- The ntfy template's formatting on the next real production notification has not been observed.
- The llama.cpp route is qualified on one fixture and one trial only; it has no host portability, concurrency or recovery evidence.
- Nothing here establishes lifetime token savings or a universal SOTA ranking.
- lanes disagreed: claude=loki,opentelemetry-collector-contrib,prometheus; codex=grafana,opentelemetry-collector-contrib,prometheus; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-observation-inference-20260922.json

Lanes: disagree (claude: foundation-observation-inference-20260922; codex: foundation-observation-inference-20260922)

#### Quality and evaluation (quality-evaluation)

- promptfoo @ 0.123.1 — This verdict comes from my source review of the retained evidence. I re-ran no commands, so every result below is documented as done, not observed now.

Promptfoo (c2): docs/promptfoo-upstream-retrieval.md lines 8-18 record Promptfoo 0.123.1 running NVIDIA's pinned upstream retrieval example through its native exec: provider. The run returned 4/4 paired documents first, 1 passing case, 0 failures and 0 errors. Lines 70-73 keep the earlier browser-automation failures and describe how they were fixed. Lines 20-22 limit the claim to compatibility with the upstream example; it is not a benchmark. Promptfoo also kept failures visible in blueprints/native-skill-practice/typesafe-result.json: promptfoo_exit_code 100 (line 7), service_errors 0, every failing per-case row kept, and C4 listed as a failure. The older receipt evidence/receipts/token-native-retained-functional-20260920.json (lines 107-125 and 424-432) is only a 2-assertion check with an echo provider and 0 provider tokens.

Playwright (c6): blueprints/convergence-practice/wsl-application/README.md lines 3-20 summarize a qualification lane for the project's own application on WSL. I opened blueprints/convergence-practice/wsl-application/receipt.json, which records:
- lines 104-113: make test exited 0 with 12 passed and 0 failed.
- lines 114-126: 'Frozen real browser create/update/reload' ran `pnpm exec playwright test` and exited 0 with passed 1, failed 0, retries 0, browser_assertions_changed false and page_errors 0.
- lines 161-184: failed setup attempts are kept (exit 2 and exit 1), each with its cause and fix.

This is a local integration check of the project's own application. It is a single browser test, not an upstream Playwright suite.

catalogs/foundation/decisions.json lines 1352-1411 (deterministic-quality-tools, accepted_within_scope, evidence id wsl-application-20260920) link both tools to this layer. The same record says fixture success does not prove model quality or production correctness in general.

The winner set's evidence class is local_integration. That is the weaker of the two: c2 is an upstream example run natively, while c6 tests the project's own application.

Correction: the packet lists docs/dashboard-rendered-acceptance.md as c6 evidence, but that file never mentions Playwright. Its only quality-tool row is the Promptfoo echo re-export (line 33).
- playwright-test @ 1.63.0 — This verdict comes from my source review of the retained evidence. I re-ran no commands, so every result below is documented as done, not observed now.

Promptfoo (c2): docs/promptfoo-upstream-retrieval.md lines 8-18 record Promptfoo 0.123.1 running NVIDIA's pinned upstream retrieval example through its native exec: provider. The run returned 4/4 paired documents first, 1 passing case, 0 failures and 0 errors. Lines 70-73 keep the earlier browser-automation failures and describe how they were fixed. Lines 20-22 limit the claim to compatibility with the upstream example; it is not a benchmark. Promptfoo also kept failures visible in blueprints/native-skill-practice/typesafe-result.json: promptfoo_exit_code 100 (line 7), service_errors 0, every failing per-case row kept, and C4 listed as a failure. The older receipt evidence/receipts/token-native-retained-functional-20260920.json (lines 107-125 and 424-432) is only a 2-assertion check with an echo provider and 0 provider tokens.

Playwright (c6): blueprints/convergence-practice/wsl-application/README.md lines 3-20 summarize a qualification lane for the project's own application on WSL. I opened blueprints/convergence-practice/wsl-application/receipt.json, which records:
- lines 104-113: make test exited 0 with 12 passed and 0 failed.
- lines 114-126: 'Frozen real browser create/update/reload' ran `pnpm exec playwright test` and exited 0 with passed 1, failed 0, retries 0, browser_assertions_changed false and page_errors 0.
- lines 161-184: failed setup attempts are kept (exit 2 and exit 1), each with its cause and fix.

This is a local integration check of the project's own application. It is a single browser test, not an upstream Playwright suite.

catalogs/foundation/decisions.json lines 1352-1411 (deterministic-quality-tools, accepted_within_scope, evidence id wsl-application-20260920) link both tools to this layer. The same record says fixture success does not prove model quality or production correctness in general.

The winner set's evidence class is local_integration. That is the weaker of the two: c2 is an upstream example run natively, while c6 tests the project's own application.

Correction: the packet lists docs/dashboard-rendered-acceptance.md as c6 evidence, but that file never mentions Playwright. Its only quality-tool row is the Promptfoo echo re-export (line 33).

Alternatives:
- ShellCheck (conditional) — evidence/receipts/portable-cli-artifacts.json (kind native_cli_e2e, line 4) shows `shellcheck fixtures/example.sh` returning exit_code 0 against expected_exit 0 (lines 21-28). That is one run on a clean fixture, and it kept no failing case. Line 15 limits the receipt to fixture-specific behavior, not a quality benchmark. ShellCheck is a static linter that applies only to shell changes. It does not verify changed behavior. catalogs/foundation/decisions.json lines 1398-1402 give it the status accepted_within_scope.
- Difftastic (overlap) — In evidence/receipts/portable-cli-artifacts.json lines 31-41, difft on fixtures/before.py and fixtures/after.py exited 0 where 1 was expected (matched false), and that mismatch was kept. Line 16 explains that exit 0 is difft's default and that --exit-code produced the expected 1. That exit code signals only whether a diff exists; it is not a pass/fail result on behavior. Difftastic is a review aid for structural diffs and overlaps with review tooling. catalogs/foundation/decisions.json (around lines 2958-2992) adds that no new execution was run for that layer.
- MCP Inspector (conditional) — evidence/receipts/token-native-retained-functional-20260920.json lines 84-105 show one Inspector stdio call to Context Mode: exit 0, check '42 computed' passed. Line 18 limits this to arithmetic only and does not certify the full plugin, hooks or connection. Line 15 says the operations were not rerun. It fits verification of an MCP surface only, not changed behavior in general.
- TypeSafe semantic skill (conditional) — These TypeSafe results are retained provider judgments, not my own. blueprints/native-skill-practice/typesafe-result.json (source_kind 'fresh_provider_execution_on_selected_public_excerpts', line 4) records 8 live jev-1.13.0 requests, run inside a Promptfoo harness (exit 100). They matched 7/8 frozen labels, against 3/8 for the exact-text baseline (lines 11-13). The artifact's own limits: eight selected cases, a weak comparator, no calibrated threshold and no authority to select. docs/native-skill-practice-20260921.md lines 111-118 record the one mismatch: C4 came back 'contradicted' instead of the frozen 'insufficient', and native Codex and Claude source review later corrected C4 to 'insufficient'. TypeSafe gives advisory semantic judgments within verification; it is not the verification harness itself. catalogs/landscape/native-practice.json lines 57-67 keep it at bounded_path_completed_with_limits.
- Official OpenAI CI and security skills (unqualified) — catalogs/landscape/native-practice.json gives gh-fix-ci the status installed_discovery_and_clean_helper_only (line 115) and security-best-practices the status installed_discovery_only (line 152). docs/native-skill-practice-20260921.md line 13 says security findings and false-positive control remain unqualified. Lines 151-153 say failure-log repair with gh-fix-ci and security finding quality 'remain separate qualification boundaries' and 'are not installation failures'. No verification of a failing check was observed.
- Inspect AI (unqualified) — catalogs/us-equities/agents-operations.json lines 1281-1320 record evidence_level source_review. Its commands are labeled 'Prospective commands; not executed for this catalog', and the record notes 'Eval command would perform model calls; not run here.' No local execution or kept failures exist. docs/acceptance-evidence-policy.md lines 49-50 say source inspection and native execution are separate outcomes.
- MLflow (out_of_scope) — catalogs/us-equities/agents-operations.json lines 1687-1726 file MLflow under experiment tracking and observability, with evidence_level source_review and prospective commands that were never run. MLflow tracks runs and artifacts; it does not verify changed behavior.

Overturn when: Either of two outcomes would change this verdict.
1. Inspect AI (c1) runs the frozen cases in blueprints/native-skill-practice/catalog-cases.json as an Inspect task and returns per-case results comparable to the Promptfoo harness in blueprints/native-skill-practice/promptfooconfig.yaml (7/8 TypeSafe and 3/8 baseline in blueprints/native-skill-practice/typesafe-result.json). It must also keep failures at least as visibly as Promptfoo does: a nonzero exit and the C4 disagreement.
2. The Playwright lane under blueprints/convergence-practice/wsl-application/playwright.config.ts either fails a fresh run without assertion changes, or does not catch an injected create/update regression. Either would take c6 out of the winner set.

Open gaps:
- The Promptfoo evidence is one upstream example with 4 pairs plus a 2-assertion echo fixture. It is not a held-out evaluation of model quality (docs/promptfoo-upstream-retrieval.md lines 20-22).
- The Playwright evidence is one browser test (passed 1 in receipt.json lines 114-126) on the project's own application. It is not an upstream Playwright suite.
- No kept evidence shows a winner catching an injected regression; the decisions.json next_gap still names this as missing.
- ShellCheck has one run on a clean fixture and no kept failing case. Difftastic's exit code signals only whether a diff exists.
- Promptfoo and Inspect AI have not been compared on the same frozen cases.
- TypeSafe C4: native Codex and Claude source review corrected it to 'insufficient' (docs/native-skill-practice-20260921.md lines 116-118). The underlying claim stays unqualified under either reading (line 113). Claude's review output was descriptive and not schema-validated (lines 139-140). Eight cases cannot support a ranking by quality, speed or cost.
- No representative held-out model-quality evaluation or matched comparison establishes universal superiority.
- The four-query retrieval assertion is locally authored and evaluates rounded upstream output; direct evaluation token usage and cost are unreported.
- Playwright acceptance covers a local synthetic ledger application, with no production authentication, load, external ingestion or independent-host restore qualification.
- Inspect AI execution, MLflow experiment tracking, CI failure repair and security finding quality remain unestablished by the reviewed evidence.
- TypeSafe's C4 disagreement and unmatched native-review baseline remain unresolved qualification boundaries.

Lanes: same_winner (claude: foundation-quality-evaluation-20260922; codex: foundation-quality-evaluation-20260922)

#### Recovery and portability (recovery-portability)

- restic @ 0.19.1 — State recovery (c4, Restic 0.19.1) rests on native execution with synthetic state. In catalogs/foundation/decisions.json, synthetic-offhost-restic-restore (packet lines 83-95) records a fresh GitHub-hosted runner. It passed seven unchanged upstream tests and refused the wrong password without restoring files. It also restored both exact synthetic snapshots with complete path/type/byte/hash/POSIX-mode equality. blueprints/convergence-practice/offhost-restore/README.md lines 3-14 give run35537533416. There, check --read-data covered two snapshots and four packs, both restore --verify runs returned exit0 with six files each, and the invalid password returned exit12. synthetic-offhost-application-restore (decisions.json lines 2480-2598; blueprints/convergence-practice/offhost-app-state/README.md lines 3-17) composes Restic with native ai-memory and Qdrant backup/restore across two hosted boot identities. The destination returned the exact scoped memory bodies, all ten Qdrant points and three ranked queries. 10 ai-memory and 4 Qdrant unchanged upstream tests passed. Earlier same-host restore evidence is in decisions.json lines 1891-1937 and adoption/lifecycle.md lines 231-279. Restic is the only adopted candidate with executed restore evidence. Tool reproduction (c1, uv 0.12.17) rests on native same-host execution. This corrects my earlier proposal, which said no such evidence existed. adoption/receipt.json lines 10-20 give status passed_scoped_sdk_reproduction_native_readiness_restored. The scope is a 'new private prefix on existing WSL host', and second_physical_machine is false. The commands at lines 108-121 all returned exit_code 0. They were 'uv pip sync ... --require-hashes --no-build --strict' ('Installed36 distributions'), the --no-cache --reinstall variant, and 'uv pip check' ('Checked36 packages'). Lines 74-83 record 115 tests, 0 failures and 0 errors. A second independent run is recorded in blueprints/catalog-clean-install/README.md lines 3-26 and evidence/artifacts/catalog-clean-install-20260921/04-locked-sdk-sync.log lines 3-25. It used a read-only checkout of dac2d1a3 and 'uv --no-config --no-cache pip sync --require-hashes --no-build --strict --reinstall', which returned exit_code 0 with 'Installed 36 packages'. The exact name/version set matched the lock, and 55 data fixtures passed. Of the full suite, 763 of 766 tests passed, with 1 error (HOME removed by the audit; a targeted rerun passed) and 2 skips (AUDIT.md lines 15-18). evidence/receipts/native-token-clean-prefix-20260920.json lines 10-46 and 430-437 add fresh isolated 'uv tool install' runs for Headroom and jCodeMunch. Both returned exit_code 0 into empty tool directories, with an existing package cache reused. The recipe is in adoption/lifecycle.md lines 56-98. uv is also the smallest tool lane in adoption/research.json lines 51-72: mise and chezmoi are 'optional_later', and Nix/Devbox are deferred. The winner set's class is synthetic, because Restic's recovery evidence covers synthetic state only. uv's evidence alone is local_integration: same-host native execution of the real lock with local fixture tests.
- candidate:astral-sh-uv @ unpinned — State recovery (c4, Restic 0.19.1) rests on native execution with synthetic state. In catalogs/foundation/decisions.json, synthetic-offhost-restic-restore (packet lines 83-95) records a fresh GitHub-hosted runner. It passed seven unchanged upstream tests and refused the wrong password without restoring files. It also restored both exact synthetic snapshots with complete path/type/byte/hash/POSIX-mode equality. blueprints/convergence-practice/offhost-restore/README.md lines 3-14 give run35537533416. There, check --read-data covered two snapshots and four packs, both restore --verify runs returned exit0 with six files each, and the invalid password returned exit12. synthetic-offhost-application-restore (decisions.json lines 2480-2598; blueprints/convergence-practice/offhost-app-state/README.md lines 3-17) composes Restic with native ai-memory and Qdrant backup/restore across two hosted boot identities. The destination returned the exact scoped memory bodies, all ten Qdrant points and three ranked queries. 10 ai-memory and 4 Qdrant unchanged upstream tests passed. Earlier same-host restore evidence is in decisions.json lines 1891-1937 and adoption/lifecycle.md lines 231-279. Restic is the only adopted candidate with executed restore evidence. Tool reproduction (c1, uv 0.12.17) rests on native same-host execution. This corrects my earlier proposal, which said no such evidence existed. adoption/receipt.json lines 10-20 give status passed_scoped_sdk_reproduction_native_readiness_restored. The scope is a 'new private prefix on existing WSL host', and second_physical_machine is false. The commands at lines 108-121 all returned exit_code 0. They were 'uv pip sync ... --require-hashes --no-build --strict' ('Installed36 distributions'), the --no-cache --reinstall variant, and 'uv pip check' ('Checked36 packages'). Lines 74-83 record 115 tests, 0 failures and 0 errors. A second independent run is recorded in blueprints/catalog-clean-install/README.md lines 3-26 and evidence/artifacts/catalog-clean-install-20260921/04-locked-sdk-sync.log lines 3-25. It used a read-only checkout of dac2d1a3 and 'uv --no-config --no-cache pip sync --require-hashes --no-build --strict --reinstall', which returned exit_code 0 with 'Installed 36 packages'. The exact name/version set matched the lock, and 55 data fixtures passed. Of the full suite, 763 of 766 tests passed, with 1 error (HOME removed by the audit; a targeted rerun passed) and 2 skips (AUDIT.md lines 15-18). evidence/receipts/native-token-clean-prefix-20260920.json lines 10-46 and 430-437 add fresh isolated 'uv tool install' runs for Headroom and jCodeMunch. Both returned exit_code 0 into empty tool directories, with an existing package cache reused. The recipe is in adoption/lifecycle.md lines 56-98. uv is also the smallest tool lane in adoption/research.json lines 51-72: mise and chezmoi are 'optional_later', and Nix/Devbox are deferred. The winner set's class is synthetic, because Restic's recovery evidence covers synthetic state only. uv's evidence alone is local_integration: same-host native execution of the real lock with local fixture tests.

Alternatives:
- mise (conditional) — adoption/research.json lines 74-208 give the decision optional_native_tool_layer_not_required_for_current_uv_only_adoption. Line 59 lists mise under optional_later, 'if multi-language tool/artifact bootstrap has concrete value beyond uv'. Every mise lock/install/exec command is marked 'source-confirmed recipe; not executed by this research pass'. The same source says a mise lock does not replace the SDK hash lock and that a locked install can need network and authentication. uv, by contrast, has two executed same-host hash-locked syncs (adoption/receipt.json lines 108-121; blueprints/catalog-clean-install/README.md lines 8-12). No multi-language case that needs mise is recorded.
- chezmoi (conditional) — adoption/research.json lines 413-518 give the decision defer_optional_selected_dotfile_management. Line 60 lists it as optional 'only for explicitly selected non-secret file ownership'. It has no universal dependency lock, exact-directory adoption can remove unmanaged entries, and it explicitly excludes provider account stores and memory databases, so it does not recover application state. None of its commands were executed.
- Litestream (conditional) — catalogs/us-equities/hosting-source-review.json line 196 gives the decision defer_until_continuous_replication_requirement. Line 202 gives execution_status 'research_only_except_explicit_existing_tool_and_memory_recovery_results'. The exceptions cover the existing restic and memory recovery results, not Litestream. Line 197 says v0.5.17 'creates _litestream_lock in sourceDB', which adds a standing writer/schema change. It also says 'Latest0.5 restore lacks older Age encryption' and that 'native ai-memory onlinebackup plus restic now supplies the bounded need without another daemon'. Lines 198-201 list only replicate/restore recipes, and no restore result is recorded.
- Determinate Nix installer (out_of_scope) — Not adopted. adoption/research.json lines 623-705 give the decision defer_privileged_platform_installation. It is a root-requiring system installer, not a dependency lock, and its receipt is not a package lock. No install or plan command was run.
- Devbox (out_of_scope) — Not adopted. adoption/research.json lines 521-622 give the decision defer_nix_environment_platform. It overlaps the accepted uv SDK lane and calls ensureNixInstalled, and no Nix or Devbox runtime was installed or accepted.

Overturn when: State half: re-run the manual hosted workflows in blueprints/convergence-practice/offhost-restore/README.md and blueprints/convergence-practice/offhost-app-state/README.md with an alternative backup arm, such as Litestream, beside Restic. The test case is a real state-loss case the current recipes do not cover. The verdict flips if the alternative passes install, wrong-key refusal, empty-target restore with complete byte/hash/mode equality, native ai-memory and Qdrant query equality, resume and cleanup on the adopted host while Restic fails, or if Restic fails that same acceptance. Tool half: repeat the clean-install procedure in blueprints/catalog-clean-install/README.md (which follows adoption/sdk/README.md) in a new prefix on the explicitly adopted host. The verdict flips if 'uv pip sync --require-hashes --no-build --strict' of adoption/sdk/requirements-linux-x86_64-py313.lock or 'uv pip check' fails there. It also flips if a recorded multi-language or system-dependency case needs mise and a locked 'mise install --locked' passes the same install, use and cleanup checks.

Open gaps:
- uv's hash-locked sync has been executed only in fresh prefixes on the existing WSL host (adoption/receipt.json line 146; blueprints/catalog-clean-install/README.md lines 3-6). Its uv tool installs also ran on the same host with the package cache reused (native-token-clean-prefix-20260920.json lines 11 and 433). A second physical machine or the explicitly adopted new PC has not been exercised.
- The uv lock covers only the 36-distribution Python SDK graph. Native client archives, npm tools, the OS/interpreter, the GPU stack, services and models keep separate recipes and acceptance (adoption/receipt.json line 147; AUDIT.md line 38). The clean-install audit did not qualify Context Mode, ai-memory or MCPorter (blueprints/catalog-clean-install/README.md lines 43-46).
- The packet's second evidence_ref for uv, docs/portable-userspace-install-20260921.md, contains no occurrence of 'uv' (grep count 0). The uv evidence comes from adoption/receipt.json and the catalog-clean-install artifacts instead.
- All Restic recovery evidence uses synthetic state. No existing private application archive or production data has been restored (decisions.json synthetic-offhost-application-restore limitations; packet lines 74 and 88).
- Lost-account and lost-password recovery are unqualified: ciphertext and password delivery share one GitHub administrative account (packet lines 76 and 89).
- Native-client rebinding, cross-application atomicity (snapshots are sequential), physical-host, power-loss and whole-stack disaster recovery are not established (packet line 77).
- UID/GID, timestamps, ACL/xattrs, sparse files, links, Windows filesystems and long-term retention remain unqualified for Restic (packet line 92).
- Neither tool reproduction nor state recovery has been executed on the requirement's 'explicitly adopted host' (a new physical PC with its own GPU and native sign-in). The evidence covers hosted runners and fresh prefixes on the existing WSL host.
- No measured comparison exists between Restic and Litestream, or between uv and mise. The alternatives are known from source review only.
- A newly adopted physical host still needs its own installation, native sign-in, client rebinding and representative application acceptance.
- uv's observed clean-prefix installs reused the existing host and package cache. The hash-locked SDK reproduction commands in adoption/research.json are source-reviewed recipes, not executions from that research pass.
- docs/portable-userspace-install-20260921.md establishes a separate selected client/token-tool subset on the existing WSL kernel; it does not qualify uv or the whole foundation.
- Off-host application recovery used newly generated synthetic state. Existing private application archives, production recovery and independent trust-domain availability remain unestablished.
- Atomic cross-application backups, lost-account/password recovery, power-loss recovery and long-term retention remain unqualified.
- No executed comparison establishes that an alternative improves installation or recovery for the selected workload.

Lanes: same_winner (claude: foundation-recovery-portability-20260922; codex: foundation-recovery-portability-20260922)

#### Scheduling and supervision (scheduling-supervision)

- dagu @ 2.16.6 — Dagu (c3) and the systemd user manager (c1) are the only candidates that were actually run for this layer's requirement. The other four were reviewed only from source. Dagu is the workflow layer. It provides run history, cancellation and resume from a checkpoint. catalogs/foundation/decisions.json, decision checkpointed-workflow-resume (lines 1576-1605): native `dagu stop` and retry kept one checkpoint on Mac and WSL, and a separate SSH-client termination left the same job running until it finished. The receipt evidence/receipts/native-service-reboot-20260920.json records three results: (1) native `dagu retry --run-id native-service-reboot-fixture --step finalize` exited with code 0 and the history states were running, aborted, succeeded, with same_run_id true; (2) after an orderly reboot of a disposable guest, the same run resumed automatically; (3) the unchanged upstream Dagu 2.16.6 retry tests (`go test ... ^TestRetryCommand`) returned exit_code 0, with pass_records 15, leaf_cases 14 and failed 0. The runner that produced the job-recovery result is blueprints/convergence-practice/job-recovery/run.py. It checks for aborted history after the native stop (lines 137-141), a same-run `retry --step finalize` that reaches succeeded (lines 144-148), and an unchanged checkpoint with the 12-test oracle (lines 149-151). systemd is the process-tree layer. It enforces deadlines and cleans up descendants. decisions.json owned-process-deadlines (lines 1533-1560) and blueprints/us-equities/worker-supervision/README.md lines 3-12 record that native `systemd-run --user` with RuntimeMaxSec and KillMode=control-group killed a parent, child and grandchild that all ignored TERM. The result was `timeout`, and a fresh run afterwards succeeded. The deadline and kill come from the systemd-run properties in the README (lines 32-51), not from fixture.py itself. decisions.json native-child-interruption-recovery (lines 2324-2359) adds automatic systemd cleanup of descendants after the parent runtime failed abruptly. The two tools cover different parts of the requirement and are used together in the reboot receipt (component_ids dagu and systemd), so they form one winner set rather than competing with each other. Evidence class: the tools ran natively, but every workload was synthetic or no-model, and the receipt labels the guest experiment as local synthetic integration coverage. The weakest class for the winner set is therefore local_integration, not native_proven for real workloads. Source of this judgment: my own review of the retained files. The packet withholds the provider's selection fields, so no provider judgment was carried over.
- systemd @ 255.4-1ubuntu8.17 — Dagu (c3) and the systemd user manager (c1) are the only candidates that were actually run for this layer's requirement. The other four were reviewed only from source. Dagu is the workflow layer. It provides run history, cancellation and resume from a checkpoint. catalogs/foundation/decisions.json, decision checkpointed-workflow-resume (lines 1576-1605): native `dagu stop` and retry kept one checkpoint on Mac and WSL, and a separate SSH-client termination left the same job running until it finished. The receipt evidence/receipts/native-service-reboot-20260920.json records three results: (1) native `dagu retry --run-id native-service-reboot-fixture --step finalize` exited with code 0 and the history states were running, aborted, succeeded, with same_run_id true; (2) after an orderly reboot of a disposable guest, the same run resumed automatically; (3) the unchanged upstream Dagu 2.16.6 retry tests (`go test ... ^TestRetryCommand`) returned exit_code 0, with pass_records 15, leaf_cases 14 and failed 0. The runner that produced the job-recovery result is blueprints/convergence-practice/job-recovery/run.py. It checks for aborted history after the native stop (lines 137-141), a same-run `retry --step finalize` that reaches succeeded (lines 144-148), and an unchanged checkpoint with the 12-test oracle (lines 149-151). systemd is the process-tree layer. It enforces deadlines and cleans up descendants. decisions.json owned-process-deadlines (lines 1533-1560) and blueprints/us-equities/worker-supervision/README.md lines 3-12 record that native `systemd-run --user` with RuntimeMaxSec and KillMode=control-group killed a parent, child and grandchild that all ignored TERM. The result was `timeout`, and a fresh run afterwards succeeded. The deadline and kill come from the systemd-run properties in the README (lines 32-51), not from fixture.py itself. decisions.json native-child-interruption-recovery (lines 2324-2359) adds automatic systemd cleanup of descendants after the parent runtime failed abruptly. The two tools cover different parts of the requirement and are used together in the reboot receipt (component_ids dagu and systemd), so they form one winner set rather than competing with each other. Evidence class: the tools ran natively, but every workload was synthetic or no-model, and the receipt labels the guest experiment as local synthetic integration coverage. The weakest class for the winner set is therefore local_integration, not native_proven for real workloads. Source of this judgment: my own review of the retained files. The packet withholds the provider's selection fields, so no provider judgment was carried over.

Alternatives:
- Prefect (overlap) — Source review only. The catalog entry (Prefect 3.8.6) marks its commands as 'Prospective commands; not executed for this catalog', and 'No flow is supplied or scheduled here'. It needs a persistent server or database. The entry says to choose it instead of Dagu, not in addition. No cancellation, checkpoint or process-tree result has been run to compare against Dagu's accepted receipts. Untested is not the same as failed.
- Dagster (conditional) — Source review only. Its commands are prospective and were not executed. Its role is partitioned data assets, lineage and backfills, which applies to data orchestration rather than supervising local processes. It needs an application-defined asset definitions file ('Definitions file is application work not included here') and a persistent metadata database. No run history or cancellation evidence exists for this layer.
- Restate (conditional) — Decision defer_new_service (source review, pin v1.7.10; execution_status is research-only). Durable handlers and replay only matter for long-running workers that run across processes, and there is no such workload today. It would duplicate the Dagu coordination and add persistence, auth and an SDK to operate. Its BUSL-1.1 license has a limited use grant.
- Temporal (conditional) — Decision defer_new_service (source review only, pin v1.32.0). A production service adds persistence and visibility databases, schema upgrades, auth and archival. start-dev is developer evidence only. docs/foundation-rd-readiness.md keeps it as keep-but-compare until a concrete requirement for durable cross-host operation goes beyond the accepted native path.

Overturn when: Three checks. (1) Re-verify the baseline. `python3 blueprints/convergence-practice/job-recovery/run.py --dagu <reviewed Dagu 2.16.6 binary> --work <new private dir>` is the existing runnable check. It must still return status passed, with aborted then succeeded history on the same run ID, an unchanged checkpoint, execution count 1 and 12 oracle tests (run.py lines 137-165; plan.json acceptance). For the systemd layer, the `systemd-run --user` command in blueprints/us-equities/worker-supervision/README.md lines 32-51 wraps blueprints/us-equities/worker-supervision/fixture.py. It must still return 1 with Result timeout, and all three original processes must be absent. A failure of either check overturns the accepted baseline. (2) Dagu v2.17.0 and the challengers cannot be run with the existing harnesses. run.py lines 120-122 reject any Dagu other than 2.16.6. service-reboot/plan.json pins the 2.16.6 archive and binary. No harness exists for Temporal, Restate or Prefect. Overturning requires a new frozen plan and runner that reproduce the same acceptance list in blueprints/convergence-practice/job-recovery/plan.json (lines 8-15) and blueprints/convergence-practice/service-reboot/plan.json (lines 37-46) for that arm. That arm must then pass all the cases natively with acceptable operational burden, or Dagu v2.17.0 must fail them. (3) A real workload requires surviving host loss, waits lasting days or durable effects across hosts. Dagu plus the user manager fails that requirement, and a challenger passes it under such a new harness.

Open gaps:
- Physical-PC reboot, power loss, a crash of the host or user manager, and recovery on an independent host are not established (decisions.json lines 2349, 2406, 2423; service-reboot/plan.json excluded list lines 47-56).
- No evidence covers remote model-provider cancellation, when billing stops, or distributed or external exactly-once effects, including broker orders (job-recovery/plan.json line 17 excludes them).
- All accepted workloads are synthetic or no-model. No real application workflow has been scheduled or recovered.
- Dagu upstream v2.17.0 is newer than the accepted 2.16.6 pin and has not been re-qualified. The existing runner rejects any other version (run.py lines 120-122), so a re-qualification needs a new frozen plan and runner.
- No harness exists to run Temporal, Restate or Prefect against the same frozen cases. Any comparison with a challenger needs new project work before it can run.
- docs/foundation-convergence-20260921.md lines 95-99: the next genuine daily maintenance trigger and restart persistence still need actual observations from the scheduler and a restart. Hard crash of the native Workflow is unqualified.
- No executed comparison exists between Dagu and Prefect, Dagster, Restate or Temporal on the same cases. Their exclusion rests on source review and operational burden, not on an observed failure.
- The retained prior failed attempts (service-reboot and job-recovery prior-attempts.json) remain failures. The accepted scope is narrow.
- service-reboot/plan.json line 4 still reads status 'protocol-only-until-a-native-receipt-is-reviewed', while a native receipt (evidence/receipts/native-service-reboot-20260920.json) exists. I did not verify whether the plan status was updated elsewhere.
- Physical-host failure, power loss, independent-host recovery and arbitrary production effects remain unqualified.
- Local process termination does not establish remote provider cancellation, billing cessation or distributed exactly-once effects.
- The orderly reboot experiment uses a synthetic workload; its project oracle is separate from the selected unchanged upstream Dagu retry tests.
- Persistent manual history and one guest timer do not establish every production schedule or daemon policy.
- The retained foundation review leaves the next genuine daily maintenance trigger and restart persistence unobserved.

Lanes: same_winner (claude: foundation-scheduling-supervision-20260922; codex: foundation-scheduling-supervision-20260922)

#### Secrets and credentials (secrets-credentials)

- gitleaks @ 8.30.1 — c1 (gitleaks 8.30.1) is the only adopted candidate, and it covers the detection half of the requirement: finding accidental secret exposure before publication. What was observed: blueprints/convergence-practice/wsl-native-tools/README.md (lines 3-12) and receipt-wsl-hardened.json (lines 68-89, 368-374) record the pinned gitleaks 8.30.1 binary running natively on a Linux/WSL2 host. With the default rules, it found exactly one "github-pat" finding (exit 1) in a generated inert secret and 0 findings (exit 0) in a clean directory. The README calls this "a synthetic tool check." tests/test_gitleaks_config.py checks the repository's .gitleaks.toml allowlist against synthetic fixtures and runs a branch-ancestry-scoped history scan. Its own docstring calls these local integration checks, and this lane did not run them. The layer decision in catalogs/foundation/decisions.json (lines 2910-2948, secrets-credentials-policy) is review_status "source_review" and says "no new execution was run to freeze this taxonomy layer"; its gitleaks lifecycle stage is "use"/"accepted_within_scope". The other half of the requirement, keeping sign-ins and credentials off the checkout, is supported only by source review. The evidence is a policy value, adoption/manifest.json line 428 authentication_transfer "native_login_on_target_only", not an executed component. The winner class is therefore local_integration: a native binary run on one host against synthetic fixtures, with no observed publication-pipeline run.

Alternatives:
- OpenBao (unqualified) — OpenBao is not adopted and has no execution, install or query evidence. Its packet evidence_ref, adoption/manifest.json, contains no mention of OpenBao (a case-insensitive search found no match), so that reference supports nothing about this candidate. catalogs/foundation/decisions.json line 2929 records OpenBao as 'an unused, unqualified candidate', and line 2939 says it has 'no lifecycle stage at all'. It is also a different function: a secret store or manager, not a pre-publication exposure detector. It could only complement gitleaks, if a concrete multi-host or multi-operator secret-sharing gap were shown.

Overturn when: Detection side: `python3 -m unittest -v tests.test_gitleaks_config` would count against gitleaks if, on the target host, it fails or is skipped. Examples are a non-allowlisted synthetic secret going undetected, or a non-empty result from the HEAD-ancestry-scoped history scan. The same applies if a replay of blueprints/convergence-practice/wsl-native-tools/receipt-wsl-hardened.json cannot reproduce 1 positive "github-pat" finding and 0 negative findings. Credential-storage side: the packet's existing condition applies. A concrete multi-host or multi-operator secret-sharing need must appear, and OpenBao (or a comparable manager) must pass an installed, queried comparison against the native-login-only policy. That comparison has no fixture or test yet, so it would have to be added before it could overturn anything.

Open gaps:
- No executed evidence shows that sign-ins and credentials actually stay off the checkout. That half of the requirement rests on a policy value (adoption/manifest.json line 428) and on decisions.json's activation text; it is source review only.
- The secrets-credentials-policy decision itself says no new execution was run for this layer (decisions.json line 2927). The gitleaks evidence is reused from the native WSL tool receipt and the offline-security-inventory decision (checked_at 2026-09-20).
- The gitleaks native receipt covers one Linux/WSL2 host with synthetic inert fixtures. It does not qualify other hosts, real-history completeness, or a publication-pipeline run.
- Secret scanning does not prove there is no secret anywhere (decisions.json line 1439). ci-security/README.md lines 48-50 say the zizmor offline analysis does not cover secrets.
- Native login state and account credentials are not inventoried as components (decisions.json line 2930). Broker credential handling is a trading gate, outside this foundation layer.
- OpenBao has no install, query or comparison evidence, and no fixture exists yet to compare it against the native-login policy.
- Gitleaks detects exposure; the evidence does not establish enforcement that all native sign-ins and credentials remain outside the checkout.
- Synthetic detection controls do not establish detection of every credential format or absence of secrets.
- The configuration records clean branch-ancestry and working-tree scans but a residual synthetic finding on another branch in the default all-refs scan.
- The configured size limit excludes oversized generated explorer HTML.
- No operational OpenBao comparison or multi-host credential lifecycle acceptance is retained.
- The broker credential environment variables belong to the separate trading gate.

Lanes: same_winner (claude: foundation-secrets-credentials-20260922; codex: foundation-secrets-credentials-20260922)

#### Semantic code retrieval (semantic-rag)

- socraticode @ 1.14.0 — The requirement names three parts: a scoped index, a compatible embedding service and recoverable state. SocratiCode (c7), Qdrant (c1) and vLLM (c8) are the only candidates with recorded native execution across that path. In evidence/receipts/native-rag.json (kind native_model_e2e, recorded 2026-09-19), native Codex and native Claude each made one successful SocratiCode codebase_search call. Both returned "tools/ecosystem/linux-usage-report.cjs lines2-39, score0.6429". The index had 35 files and 139 chunks, and Qdrant collection codebase_72cfa87c5abf reported green. The embedding came from nvidia/Nemotron-3-Embed-1B-BF16 with 2048 finite dimensions and a norm of 1.0000000207936353. Automatic add, update and delete each finished in about 3 seconds with no SocratiCode tool call during the mutations, and the probe was removed afterwards. docs/native-memory-rag-lifecycle.md lines 13-15 and 29-33 describe this as useful retrieval on one real question, not a recall benchmark. docs/full-stack-convergence.md lines 108-111 record native vLLM inference on the pinned revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 (2,048 finite dimensions, norm 0.9999999746521075). docs/token-native-saturation.md line 27 records that 0.25.0 is the working WSL pin after 0.29.0 failed to initialize. For recoverable state, catalogs/foundation/decisions.json records two accepted-within-scope restores of Qdrant snapshot and query state. same-host-restore (lines 1891-1919) is a same-host backup and restore. synthetic-offhost-application-restore (lines 2480-2509) is a fresh hosted job with synthetic state and complete Qdrant state/query equality. The cross-host driver and oracle in that second restore are local integration coverage. The project-semantic-index decision (lines 858-922) marks SocratiCode recovery as not_established. Recoverable state is therefore established for Qdrant's vector store only, not for SocratiCode's index or watcher lifecycle. All three are selected as components of one composed path. None is a universal winner, because no held-out retrieval-quality comparison exists.
- qdrant @ 1.19.1 — The requirement names three parts: a scoped index, a compatible embedding service and recoverable state. SocratiCode (c7), Qdrant (c1) and vLLM (c8) are the only candidates with recorded native execution across that path. In evidence/receipts/native-rag.json (kind native_model_e2e, recorded 2026-09-19), native Codex and native Claude each made one successful SocratiCode codebase_search call. Both returned "tools/ecosystem/linux-usage-report.cjs lines2-39, score0.6429". The index had 35 files and 139 chunks, and Qdrant collection codebase_72cfa87c5abf reported green. The embedding came from nvidia/Nemotron-3-Embed-1B-BF16 with 2048 finite dimensions and a norm of 1.0000000207936353. Automatic add, update and delete each finished in about 3 seconds with no SocratiCode tool call during the mutations, and the probe was removed afterwards. docs/native-memory-rag-lifecycle.md lines 13-15 and 29-33 describe this as useful retrieval on one real question, not a recall benchmark. docs/full-stack-convergence.md lines 108-111 record native vLLM inference on the pinned revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 (2,048 finite dimensions, norm 0.9999999746521075). docs/token-native-saturation.md line 27 records that 0.25.0 is the working WSL pin after 0.29.0 failed to initialize. For recoverable state, catalogs/foundation/decisions.json records two accepted-within-scope restores of Qdrant snapshot and query state. same-host-restore (lines 1891-1919) is a same-host backup and restore. synthetic-offhost-application-restore (lines 2480-2509) is a fresh hosted job with synthetic state and complete Qdrant state/query equality. The cross-host driver and oracle in that second restore are local integration coverage. The project-semantic-index decision (lines 858-922) marks SocratiCode recovery as not_established. Recoverable state is therefore established for Qdrant's vector store only, not for SocratiCode's index or watcher lifecycle. All three are selected as components of one composed path. None is a universal winner, because no held-out retrieval-quality comparison exists.
- vllm @ 0.25.0 — The requirement names three parts: a scoped index, a compatible embedding service and recoverable state. SocratiCode (c7), Qdrant (c1) and vLLM (c8) are the only candidates with recorded native execution across that path. In evidence/receipts/native-rag.json (kind native_model_e2e, recorded 2026-09-19), native Codex and native Claude each made one successful SocratiCode codebase_search call. Both returned "tools/ecosystem/linux-usage-report.cjs lines2-39, score0.6429". The index had 35 files and 139 chunks, and Qdrant collection codebase_72cfa87c5abf reported green. The embedding came from nvidia/Nemotron-3-Embed-1B-BF16 with 2048 finite dimensions and a norm of 1.0000000207936353. Automatic add, update and delete each finished in about 3 seconds with no SocratiCode tool call during the mutations, and the probe was removed afterwards. docs/native-memory-rag-lifecycle.md lines 13-15 and 29-33 describe this as useful retrieval on one real question, not a recall benchmark. docs/full-stack-convergence.md lines 108-111 record native vLLM inference on the pinned revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 (2,048 finite dimensions, norm 0.9999999746521075). docs/token-native-saturation.md line 27 records that 0.25.0 is the working WSL pin after 0.29.0 failed to initialize. For recoverable state, catalogs/foundation/decisions.json records two accepted-within-scope restores of Qdrant snapshot and query state. same-host-restore (lines 1891-1919) is a same-host backup and restore. synthetic-offhost-application-restore (lines 2480-2509) is a fresh hosted job with synthetic state and complete Qdrant state/query equality. The cross-host driver and oracle in that second restore are local integration coverage. The project-semantic-index decision (lines 858-922) marks SocratiCode recovery as not_established. Recoverable state is therefore established for Qdrant's vector store only, not for SocratiCode's index or watcher lifecycle. All three are selected as components of one composed path. None is a universal winner, because no held-out retrieval-quality comparison exists.

Alternatives:
- Hugging Face Hub native CLI (overlap) — This tool supplies and verifies the model files; it does not serve embeddings. docs/hf-memory-model-qualification.md lines 36-48 record native hf commands: checked: 15 for the Nemotron revision, plus a warning about 33 extra local cache-metadata files. Lines 50-68 record an upstream four-example retrieval check that ran through the vLLM endpoint. evidence/receipts/native-rag.json lists it as a component. It is a supporting part of the selected vLLM embedding path, not a separate answer to the requirement.
- code-memory (conditional) — The evidence is source review only; nothing was installed or run. docs/blind-catalog-source-adjudication-20260921.md lines 7-42 give four reasons. SocratiCode already has dense/BM25 fusion, so hybrid ranking is not a missing capability. The default Jina weights are licensed CC-BY-NC-4.0, and the loader does not pin a model revision. Two source-level stale-index pruning concerns have not been reproduced. The sampled tests check validation and response shape, not retrieval quality. The source review JSON marks it 'provisional_source_based_selection_not_adopted', and the recorded decision keeps the current route with only a conditional portability comparison.
- Haystack (out_of_scope) — The catalog places it in the rag-pipeline layer for composable document and retrieval pipelines, not scoped code indexing. The evidence is a pinned README review, and the proposed commands were not run. Its own limitation says there is no financial corpus pipeline or performance proof. There is no evidence of a code index, watcher freshness, compatibility with the local embedding service or state recovery.
- pgvector (unqualified) — It is a vector-storage candidate backed by pinned README review only; no commands were run. Its catalog entry says it 'Adds no benefit to current Qdrant code index unless a specific SQL integration need is established.' Building it is not the same as activating the database extension, and there is no evidence of native use or restore.
- LanceDB (unqualified) — It is not adopted and is backed by pinned README and quickstart review only; no commands were run. The standard x86 wheel needs AVX2/FMA/F16C. The catalog notes that generated vectors and filters must still be validated. Nothing shows it outperforms the Qdrant store, so it is not a preferred challenger.

Overturn when: Two findings would overturn this verdict. The first is a sealed comparison showing better source-grounded recall, freshness or restore behaviour for another stack. It would use blinded conceptual code questions with independently identified cross-file supporting locations, seeded from fixtures/rag-note.md, and compare a lexical baseline, the SocratiCode/Qdrant/vLLM-Nemotron path and code-memory with a pinned model. Metrics are recall, grounded answer accuracy, cross-project leakage, edit/rename/delete freshness, cold index time, RAM and empty-target restore. The comparison should be recorded against the lifecycle stages in blueprints/token-native-focus/saturation-audit.json. The second is an observed failure of the pinned vLLM 0.25.0 / Nemotron revision to serve on the current host.

Open gaps:
- No held-out or cross-model retrieval-quality benchmark exists. native-rag.json shows one real question answered correctly, and hf-memory-model-qualification.md shows four upstream examples ranked first. Both establish compatibility, not quality.
- SocratiCode index/watcher recovery is not_established (catalogs/foundation/decisions.json, project-semantic-index lifecycle). Restores are established only for Qdrant snapshot/query state: same-host, and a hosted job with synthetic state and local-integration composition.
- Restore on an independent physical host, lost-key/account recovery, native-client rebinding and whole-stack recovery are not established.
- Only vLLM 0.25.0 is accepted on this WSL host. 0.29.0 failed to initialize. The upstream latest, v0.30.0, has not been tested, and untested does not mean failed.
- Freshness after the project changes has to be checked against the current source before retrieved code is relied on. Another project or index needs its own scope.
- Nemotron 8B and other embedders have no local quality, latency or serving qualification.
- No token-saving or provider-cost measurement supports this layer.
- No sealed representative conceptual-code benchmark establishes comparative recall, grounded answer accuracy, cross-project isolation, latency or resource superiority.
- Four paired upstream retrieval examples establish embedding compatibility, not cross-model or domain quality.
- SocratiCode full-service restart/recovery and native-client rebinding remain unestablished; Qdrant recovery does not qualify the entire retrieval stack.
- Hosted recovery used synthetic state within one administrative domain; production recovery, atomic cross-application snapshots and lost-account/key recovery remain unqualified.
- The vLLM 0.29.0 failure is host-specific. The packet's newer 0.30.0 release has no retained runtime acceptance here.
- code-memory's deployment advantage and source-level freshness concerns require executed comparisons.
- fixtures/rag-note.md is a small seed fixture, not a held-out conceptual-code evaluation set.

Lanes: same_winner (claude: foundation-semantic-rag-20260922; codex: foundation-semantic-rag-20260922)

#### Context and usage efficiency (token-efficiency)

- rtk @ 0.49.0 — The requirement has two parts: supply useful context with recoverable originals, and measure artifact reductions separately from provider usage. Three candidates cover it. (1) RTK (c4) formats supported command output. Evidence: docs/token-practice.md lines 105-107 record one retained RTK Git log artifact pair, measured with o200k_base, of 537 -> 178 tokens at a fixed six-commit input. catalogs/foundation/decisions.json lines 1472-1502 (clean-token-tool-ci) records that local and GitHub clean installation passed forty-one command expectations and fourteen fidelity/recovery checks on local fixtures. docs/full-stack-convergence.md lines 132-137 says that run was a hosted clean install of RTK, QMD, Repomix and TOON on local fixtures. docs/token-native-saturation.md line 109 lists RTK as core with an accepted use stage only. docs/token-practice.md lines 191-193 says native Claude's Bash rewrite is configured. (2) Headroom (c5) is the only adopted candidate whose decision is specifically compression with exact-source recovery. catalogs/foundation/decisions.json lines 1195-1223 records that owned synthetic MCP compression/retrieval and isolated install/restart/uninstall passed. docs/token-native-saturation.md lines 3-8 says Headroom restored identical original content after restart, and line 82 lists accepted install, use, persistence, restart, cleanup and recovery stages with 11 retained pairs. docs/token-practice.md lines 215-217 and 233-234 retain both reductions and growth cases: 2,732 vs 5,105 tokens, or 18,777 when the full original is also fetched; 19,714 vs 36,625; and 191 vs 26,529 on a guarded log fixture. (3) ccusage (c1) covers the provider-usage half. catalogs/foundation/decisions.json lines 1309-1336 (native-usage-reading) records offline native usage parsing and scoped current-session observations with retained outputs, and keeps provider consumption, estimated savings, billing and cache subsets separate. docs/token-practice.md lines 291-296 confirms offline ccusage parsing within its stated gate. docs/full-stack-convergence.md lines 124-128 records the 20.0.24 upgrade with captured upstream test subsets. How the evidence was observed: RTK by native CLI execution on fixtures plus one artifact pair; Headroom by synthetic owned fixtures with isolated lifecycle; ccusage by offline local parsing. None of it is a matched provider-savings measurement. This is my own source review. The packet withheld the provider selections. When I opened decisions.json, every one of these decisions reads "selection": "conditional", and I did not use that as authority.
- headroom @ 0.37.0 — The requirement has two parts: supply useful context with recoverable originals, and measure artifact reductions separately from provider usage. Three candidates cover it. (1) RTK (c4) formats supported command output. Evidence: docs/token-practice.md lines 105-107 record one retained RTK Git log artifact pair, measured with o200k_base, of 537 -> 178 tokens at a fixed six-commit input. catalogs/foundation/decisions.json lines 1472-1502 (clean-token-tool-ci) records that local and GitHub clean installation passed forty-one command expectations and fourteen fidelity/recovery checks on local fixtures. docs/full-stack-convergence.md lines 132-137 says that run was a hosted clean install of RTK, QMD, Repomix and TOON on local fixtures. docs/token-native-saturation.md line 109 lists RTK as core with an accepted use stage only. docs/token-practice.md lines 191-193 says native Claude's Bash rewrite is configured. (2) Headroom (c5) is the only adopted candidate whose decision is specifically compression with exact-source recovery. catalogs/foundation/decisions.json lines 1195-1223 records that owned synthetic MCP compression/retrieval and isolated install/restart/uninstall passed. docs/token-native-saturation.md lines 3-8 says Headroom restored identical original content after restart, and line 82 lists accepted install, use, persistence, restart, cleanup and recovery stages with 11 retained pairs. docs/token-practice.md lines 215-217 and 233-234 retain both reductions and growth cases: 2,732 vs 5,105 tokens, or 18,777 when the full original is also fetched; 19,714 vs 36,625; and 191 vs 26,529 on a guarded log fixture. (3) ccusage (c1) covers the provider-usage half. catalogs/foundation/decisions.json lines 1309-1336 (native-usage-reading) records offline native usage parsing and scoped current-session observations with retained outputs, and keeps provider consumption, estimated savings, billing and cache subsets separate. docs/token-practice.md lines 291-296 confirms offline ccusage parsing within its stated gate. docs/full-stack-convergence.md lines 124-128 records the 20.0.24 upgrade with captured upstream test subsets. How the evidence was observed: RTK by native CLI execution on fixtures plus one artifact pair; Headroom by synthetic owned fixtures with isolated lifecycle; ccusage by offline local parsing. None of it is a matched provider-savings measurement. This is my own source review. The packet withheld the provider selections. When I opened decisions.json, every one of these decisions reads "selection": "conditional", and I did not use that as authority.
- ccusage @ 20.0.24 — The requirement has two parts: supply useful context with recoverable originals, and measure artifact reductions separately from provider usage. Three candidates cover it. (1) RTK (c4) formats supported command output. Evidence: docs/token-practice.md lines 105-107 record one retained RTK Git log artifact pair, measured with o200k_base, of 537 -> 178 tokens at a fixed six-commit input. catalogs/foundation/decisions.json lines 1472-1502 (clean-token-tool-ci) records that local and GitHub clean installation passed forty-one command expectations and fourteen fidelity/recovery checks on local fixtures. docs/full-stack-convergence.md lines 132-137 says that run was a hosted clean install of RTK, QMD, Repomix and TOON on local fixtures. docs/token-native-saturation.md line 109 lists RTK as core with an accepted use stage only. docs/token-practice.md lines 191-193 says native Claude's Bash rewrite is configured. (2) Headroom (c5) is the only adopted candidate whose decision is specifically compression with exact-source recovery. catalogs/foundation/decisions.json lines 1195-1223 records that owned synthetic MCP compression/retrieval and isolated install/restart/uninstall passed. docs/token-native-saturation.md lines 3-8 says Headroom restored identical original content after restart, and line 82 lists accepted install, use, persistence, restart, cleanup and recovery stages with 11 retained pairs. docs/token-practice.md lines 215-217 and 233-234 retain both reductions and growth cases: 2,732 vs 5,105 tokens, or 18,777 when the full original is also fetched; 19,714 vs 36,625; and 191 vs 26,529 on a guarded log fixture. (3) ccusage (c1) covers the provider-usage half. catalogs/foundation/decisions.json lines 1309-1336 (native-usage-reading) records offline native usage parsing and scoped current-session observations with retained outputs, and keeps provider consumption, estimated savings, billing and cache subsets separate. docs/token-practice.md lines 291-296 confirms offline ccusage parsing within its stated gate. docs/full-stack-convergence.md lines 124-128 records the 20.0.24 upgrade with captured upstream test subsets. How the evidence was observed: RTK by native CLI execution on fixtures plus one artifact pair; Headroom by synthetic owned fixtures with isolated lifecycle; ccusage by offline local parsing. None of it is a matched provider-savings measurement. This is my own source review. The packet withheld the provider selections. When I opened decisions.json, every one of these decisions reads "selection": "conditional", and I did not use that as authority.

Alternatives:
- Context Mode (measured_tradeoff) — The paired native evidence points in both directions. docs/token-practice.md lines 83-92 records one fixed-order pair per client: Codex went 135,217 -> 119,998 (11.26% lower) and Claude went 292,561 -> 368,121 (25.83% higher). Cache warmth and plugin availability were uncontrolled, so the pairs do not isolate a causal effect. docs/token-practice.md lines 317-321 records a later Claude selective pilot that made zero Context Mode calls and was 2.42% higher in aggregate; that is not a Context Mode treatment. Its ctx_stats counters mix session and retained-history scopes, which makes them hard to measure separately (lines 155 and 168-179). It is core and passed a use/restart task (docs/token-native-saturation.md lines 18 and 73), so it stays usable when an explicit filter lane is cheaper than a direct read, but it has not been shown to reduce Claude usage.
- Repomix (conditional) — The measured reduction comes from lossy structure. docs/token-practice.md line 112 records its outline at 3,697 -> 663 tokens against a complete pack. catalogs/foundation/decisions.json lines 1281-1284 says structural compression omits implementation details and that originals are still required for edits and correctness. It is suited to bounded selected-file handoffs, not general recoverable context supply. Its native acceptance is the use stage only (docs/token-native-saturation.md line 107) plus the CI fixture run. Version identity is also inconsistent: catalogs/us-equities/foundation-memory.json lines 302-329 records v1.18.0 installed, while the packet pin is 1.18.1. docs/full-stack-convergence.md lines 124-128 records the 1.18.1 upgrade separately.
- TOON (measured_tradeoff) — Not adopted. One component artifact shrank 1,664 -> 1,307 tokens (docs/token-practice.md line 108). The exact o200k_base full-catalog comparison went the other way: 59,792 compact-JSON tokens became 66,815 TOON tokens, 7,023 more, while the native tokenx heuristic claimed a reduction (lines 131-138). The guard kept compact JSON. It is a per-artifact representation choice, not a better default.
- Claude Token Efficient (overlap) — Not adopted and reviewed at source level only. catalogs/us-equities/star-audit.json lines 4506-4524 records review_depth readme_license_overview with decision overlaps_established. It is a short instruction file for response verbosity. It adds recurring instruction tokens and has only upstream benchmarks. No installation or model inference was performed. It does not address recoverable originals or separate usage measurement.

Overturn when: A repeated, counterbalanced native comparison on a frozen task, with the complete provider usage of every attempt counted, would change this verdict under any of three outcomes. First, Context Mode or Repomix matches correctness while reducing Claude provider usage relative to RTK plus a direct read. Second, the Headroom guard loses a required fact or fails exact original recovery on a retained pair in blueprints/token-native-focus/saturation-audit.json. Third, `python3 -m unittest tests/test_native_token_ci.py` or the RTK fidelity/recovery fixture checks it guards stop passing.

Open gaps:
- No matched baseline exists for the current native tasks. Exact whole-PC or lifetime provider savings for any winner are unmeasured (docs/full-stack-convergence.md lines 37 and 147-150).
- Headroom's recovery evidence comes from owned synthetic fixtures. Automatic interception of agent traffic is not configured, and its native ledger returned zero calls, so its native-use benefit in real sessions is not established.
- The RTK foundation gateway/lite previews failed required semantic checks. CLI acceptance does not repair them (catalogs/foundation/decisions.json line 1166).
- ccusage has an accepted use stage only. Missing attempt and child coverage blocks any whole-workflow efficiency claim (catalogs/foundation/decisions.json line 1336).
- The Context Mode paired results are one fixed-order pair per client with uncontrolled cache state. A causal effect in either direction is not established.
- The Headroom pin 0.37.0 is behind upstream v0.38.0, and 0.38.0 has not been qualified.
- Artifact reduction rows must not be summed. Several share sources, and the ten artifact pairs are not provider usage.
- lanes disagreed: claude=ccusage,headroom,rtk; codex=ccusage,context-mode,headroom; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-token-efficiency-20260922.json

Lanes: disagree (claude: foundation-token-efficiency-20260922; codex: foundation-token-efficiency-20260922)

#### Web research (web-research)

- tavily-cli @ 0.1.8 — This is my own review of the original receipts, revised after the refuter findings. It does not restate the packet's withheld dispositions. The requirement has three parts: attributable primary-source retrieval, interaction with selected pages, and bounded native commands without a standing research-agent stack. Each winner covers a different part, and each has retained native execution, including one retained Tavily search miss.

(1) Tavily CLI (c8) covers primary-source search and extraction. Three separate retained runs exist:
- docs/ecosystem/tavily-receipt.json (2026-09-20T02:48Z), lines 84-92 and 144: native authentication, plus one search capped at 3 results that returned three code.claude.com sources. Extraction was not exercised in that run.
- evidence/receipts/native-tavily-cli-20260920.json: `uv tool install tavily-cli` exited 0 (tavily-cli==0.1.8). A domain-limited `tvly search --max-results 4` exited 0 with result_count 4, and `tvly extract https://code.claude.com/docs/en/sub-agents` exited 0 with result_count 1 and failed_count 0.
- evidence/receipts/native-tavily-session-20260920.json (native_cli_e2e, Codex Desktop task, upstream_cli_version 0.1.8). An IBKR/Nautilus search exited 0 and returned three official ibkrcampus.com sources, but it missed the intended Nautilus adapter guide (line 11, and "intended_adapter_guide_found": false at line 83). This is a retained search miss. A direct known-URL `tvly extract` of the nautilustrader.io IBKR page then exited 0 with results 1 and failed_results [] (lines 86-90).
The decision's evidence_scope names both runs (catalogs/foundation/decisions.json lines 2294-2298). Across these runs, Search found relevant official sources but did not reliably surface a specific target page. Extraction of a known URL worked twice.

(2) agent-browser (c1) covers page interaction. evidence/receipts/desktop-cli-workflows.json (kind native_model_e2e) lines 42-61 record an active Codex Desktop task running open, snapshot -i, fill, click, get text #status, screenshot and close against fixtures/greeting.html. all_exit_codes is 0, observed_status is "Hello, Publication Codex Desktop!", the screenshot was visually inspected and the owned session was closed. That receipt records no agent-browser version. A separate 2026-09-21 `agent-browser --version` returned "agent-browser 0.38.1" (evidence/artifacts/claude-repository-evidence-20260921/results.json line 5788), and nothing ties that check to the fixture run. docs/dashboard-rendered-acceptance.md line 28 records a separate observed use on a real Dagu browser stream.

(3) OpenResearch (c7) covers primary literature. Two runs are retained:
- On 2026-09-20 (no version recorded; this predates the 0.2.4 to 0.2.7 upgrade), `orx --no-telemetry paper 2608.02583 --full` returned the full public paper, 63560 bytes, with no model or agent job (evidence/receipts/token-practice-gap-followup-20260920.json lines 66-71 and 195-200).
- For the current 0.2.7 pin, evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json lines 9-58 record `orx --no-telemetry discover keyword 'retrieval augmented generation memory' --limit 3` (exit 0, result_count 3), `orx --no-telemetry paper 2609.05760 --full` (exit 0, 69752 UTF-8 bytes) and 7 of 7 unchanged upstream Markdown tests passed. recipes/native-upgrades-20260921.md line 13 and docs/full-stack-convergence.md lines 124-128 point to this receipt.

All three winners are CLI commands run on demand. The set's class is local_integration, the weakest among the winners, because the browser interaction was shown only on a local fixture and a dashboard. The Tavily and OpenResearch runs are single bounded queries, not benchmarks.
- agent-browser @ 0.38.1 — This is my own review of the original receipts, revised after the refuter findings. It does not restate the packet's withheld dispositions. The requirement has three parts: attributable primary-source retrieval, interaction with selected pages, and bounded native commands without a standing research-agent stack. Each winner covers a different part, and each has retained native execution, including one retained Tavily search miss.

(1) Tavily CLI (c8) covers primary-source search and extraction. Three separate retained runs exist:
- docs/ecosystem/tavily-receipt.json (2026-09-20T02:48Z), lines 84-92 and 144: native authentication, plus one search capped at 3 results that returned three code.claude.com sources. Extraction was not exercised in that run.
- evidence/receipts/native-tavily-cli-20260920.json: `uv tool install tavily-cli` exited 0 (tavily-cli==0.1.8). A domain-limited `tvly search --max-results 4` exited 0 with result_count 4, and `tvly extract https://code.claude.com/docs/en/sub-agents` exited 0 with result_count 1 and failed_count 0.
- evidence/receipts/native-tavily-session-20260920.json (native_cli_e2e, Codex Desktop task, upstream_cli_version 0.1.8). An IBKR/Nautilus search exited 0 and returned three official ibkrcampus.com sources, but it missed the intended Nautilus adapter guide (line 11, and "intended_adapter_guide_found": false at line 83). This is a retained search miss. A direct known-URL `tvly extract` of the nautilustrader.io IBKR page then exited 0 with results 1 and failed_results [] (lines 86-90).
The decision's evidence_scope names both runs (catalogs/foundation/decisions.json lines 2294-2298). Across these runs, Search found relevant official sources but did not reliably surface a specific target page. Extraction of a known URL worked twice.

(2) agent-browser (c1) covers page interaction. evidence/receipts/desktop-cli-workflows.json (kind native_model_e2e) lines 42-61 record an active Codex Desktop task running open, snapshot -i, fill, click, get text #status, screenshot and close against fixtures/greeting.html. all_exit_codes is 0, observed_status is "Hello, Publication Codex Desktop!", the screenshot was visually inspected and the owned session was closed. That receipt records no agent-browser version. A separate 2026-09-21 `agent-browser --version` returned "agent-browser 0.38.1" (evidence/artifacts/claude-repository-evidence-20260921/results.json line 5788), and nothing ties that check to the fixture run. docs/dashboard-rendered-acceptance.md line 28 records a separate observed use on a real Dagu browser stream.

(3) OpenResearch (c7) covers primary literature. Two runs are retained:
- On 2026-09-20 (no version recorded; this predates the 0.2.4 to 0.2.7 upgrade), `orx --no-telemetry paper 2608.02583 --full` returned the full public paper, 63560 bytes, with no model or agent job (evidence/receipts/token-practice-gap-followup-20260920.json lines 66-71 and 195-200).
- For the current 0.2.7 pin, evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json lines 9-58 record `orx --no-telemetry discover keyword 'retrieval augmented generation memory' --limit 3` (exit 0, result_count 3), `orx --no-telemetry paper 2609.05760 --full` (exit 0, 69752 UTF-8 bytes) and 7 of 7 unchanged upstream Markdown tests passed. recipes/native-upgrades-20260921.md line 13 and docs/full-stack-convergence.md lines 124-128 point to this receipt.

All three winners are CLI commands run on demand. The set's class is local_integration, the weakest among the winners, because the browser interaction was shown only on a local fixture and a dashboard. The Tavily and OpenResearch runs are single bounded queries, not benchmarks.
- openresearch @ 0.2.7 — This is my own review of the original receipts, revised after the refuter findings. It does not restate the packet's withheld dispositions. The requirement has three parts: attributable primary-source retrieval, interaction with selected pages, and bounded native commands without a standing research-agent stack. Each winner covers a different part, and each has retained native execution, including one retained Tavily search miss.

(1) Tavily CLI (c8) covers primary-source search and extraction. Three separate retained runs exist:
- docs/ecosystem/tavily-receipt.json (2026-09-20T02:48Z), lines 84-92 and 144: native authentication, plus one search capped at 3 results that returned three code.claude.com sources. Extraction was not exercised in that run.
- evidence/receipts/native-tavily-cli-20260920.json: `uv tool install tavily-cli` exited 0 (tavily-cli==0.1.8). A domain-limited `tvly search --max-results 4` exited 0 with result_count 4, and `tvly extract https://code.claude.com/docs/en/sub-agents` exited 0 with result_count 1 and failed_count 0.
- evidence/receipts/native-tavily-session-20260920.json (native_cli_e2e, Codex Desktop task, upstream_cli_version 0.1.8). An IBKR/Nautilus search exited 0 and returned three official ibkrcampus.com sources, but it missed the intended Nautilus adapter guide (line 11, and "intended_adapter_guide_found": false at line 83). This is a retained search miss. A direct known-URL `tvly extract` of the nautilustrader.io IBKR page then exited 0 with results 1 and failed_results [] (lines 86-90).
The decision's evidence_scope names both runs (catalogs/foundation/decisions.json lines 2294-2298). Across these runs, Search found relevant official sources but did not reliably surface a specific target page. Extraction of a known URL worked twice.

(2) agent-browser (c1) covers page interaction. evidence/receipts/desktop-cli-workflows.json (kind native_model_e2e) lines 42-61 record an active Codex Desktop task running open, snapshot -i, fill, click, get text #status, screenshot and close against fixtures/greeting.html. all_exit_codes is 0, observed_status is "Hello, Publication Codex Desktop!", the screenshot was visually inspected and the owned session was closed. That receipt records no agent-browser version. A separate 2026-09-21 `agent-browser --version` returned "agent-browser 0.38.1" (evidence/artifacts/claude-repository-evidence-20260921/results.json line 5788), and nothing ties that check to the fixture run. docs/dashboard-rendered-acceptance.md line 28 records a separate observed use on a real Dagu browser stream.

(3) OpenResearch (c7) covers primary literature. Two runs are retained:
- On 2026-09-20 (no version recorded; this predates the 0.2.4 to 0.2.7 upgrade), `orx --no-telemetry paper 2608.02583 --full` returned the full public paper, 63560 bytes, with no model or agent job (evidence/receipts/token-practice-gap-followup-20260920.json lines 66-71 and 195-200).
- For the current 0.2.7 pin, evidence/artifacts/full-stack-convergence-20260921/orx-worktrunk-upgrades.json lines 9-58 record `orx --no-telemetry discover keyword 'retrieval augmented generation memory' --limit 3` (exit 0, result_count 3), `orx --no-telemetry paper 2609.05760 --full` (exit 0, 69752 UTF-8 bytes) and 7 of 7 unchanged upstream Markdown tests passed. recipes/native-upgrades-20260921.md line 13 and docs/full-stack-convergence.md lines 124-128 point to this receipt.

All three winners are CLI commands run on demand. The set's class is local_integration, the weakest among the winners, because the browser interaction was shown only on a local fixture and a dashboard. The Tavily and OpenResearch runs are single bounded queries, not benchmarks.

Alternatives:
- Playwright CLI (overlap) — It has real native evidence, but it does the same job as agent-browser: both are component_ids of the conditional decision bounded-browser-operations (catalogs/foundation/decisions.json lines 1049-1096). In evidence/receipts/token-practice-gap-followup-20260920.json, the first `open` of a file URL exited 1 because 'Access to file protocol is blocked' (lines 148-149). That failure is retained as 'browser-open' under failed_attempts_retained (lines 106-110), and the status at line 30 reads 'functional fixture passed after retained file-protocol rejection'. The same fixture bytes were then served over loopback HTTP. goto, snapshot, fill, click, eval, snapshot and close succeeded (successful_http_steps 7) and returned "Hello, Playwright!" (lines 116-150). The pin is @playwright/cli 0.1.21 with alpha Playwright dependencies 1.64.0-alpha-1789764292000, running on an existing Chrome 153.0.8010.52 with no browser download, and no arbitrary website was tested (line 19). agent-browser's fixture run had every exit code at 0 and was driven by a native model task. No retained comparison shows Playwright CLI doing a page task better, so it stays a conditional overlapping lane rather than a second default.
- Crawl4AI (unqualified) — The packet marks it adopted, but the only retained evidence is a README/license review at commit 862f6bccb9c063f49b9d42701baa0eea17a4993f (catalogs/us-equities/star-audit.json around lines 5960-5981). That review's decision is 'alternative', and it states that no installation, model inference or native acceptance was performed. The requirement is about selected pages, while Crawl4AI is a bulk crawl/ingestion framework, and the packet says bulk crawling needs task-specific qualification. It is untested, not failed.
- Cua Driver (out_of_scope) — The packet marks it adopted, but the retained review in catalogs/landscape/upstream-snapshot.json (around lines 5828-5891, commit 9bbfa7dd3e27ca7f1861ede70aaca390174493f9) is source review only. Its adoption_status is conditional_source_review_only and its role is a native desktop computer-use driver in the browser-and-ui layer. It states that no installation, desktop action, model inference or upstream test ran. It targets actions across desktop applications rather than retrieving web sources. It is untested, not failed.
- Firecrawl MCP (unqualified) — Not adopted. The only evidence is a README/license review at commit 387352ef94f684df4623c467374c6948aa1a3604 (catalogs/us-equities/star-audit.json around lines 3958-3979), which notes that hosted/API costs and rights to fetched content need explicit selection. No installation or native acceptance was performed, and there is no comparison against Tavily Search/Extract.
- Browser Use (unqualified) — Not adopted. The only evidence is a README/license review at commit d8110c5ff87ccba887aaa726cdb780f2f84bef8d (catalogs/us-equities/star-audit.json around lines 2608-2629). It describes a browser agent with hosted services, which would be a standing agent stack and conflicts with the requirement. No installation or native acceptance was performed.

Overturn when: Browser part: overturn if an executed run shows Playwright CLI or another candidate completing the same task more correctly or cheaply than agent-browser. The task is the fixtures/greeting.html sequence (open, snapshot, fill, click, read the #status text, close) plus a representative real selected page. Record the version for each arm and measure correctness, exit status (retained failures included), session cleanup and elapsed time. Source-retrieval part: overturn if a candidate such as Firecrawl or Crawl4AI beats Tavily Search/Extract plus OpenResearch 0.2.7 discover/paper on a defined frozen source list, measured on attributable completeness, extraction failed_count and total runtime/cost. The list should include a known-target case like the retained IBKR/Nautilus search miss. Record either comparison against the stage scopes in blueprints/token-native-focus/saturation-audit.json.

Open gaps:
- No measured comparison between agent-browser and Playwright CLI exists. Their shared decision is conditional, and neither has been shown better.
- The agent-browser fixture receipt (evidence/receipts/desktop-cli-workflows.json lines 42-61) records no version or host OS. Its 0.38.1 pin rests on a separate version check, not on the fixture run.
- Browser-session recovery and compatibility with arbitrary websites are unestablished (catalogs/foundation/decisions.json lines 1070-1071). The Playwright run needed a loopback HTTP recovery after a file-protocol rejection.
- Tavily Search reliability for a specific target is unestablished. One of the three retained searches missed the intended Nautilus adapter guide, and only a direct extraction of the known URL recovered it (evidence/receipts/native-tavily-session-20260920.json lines 11 and 83). Map, Crawl, Research and dynamic routing remain unqualified.
- The Tavily evidence is three small searches (3, 4 and 3 results) and two single-URL extractions with zero failures. That is not a completeness or accuracy benchmark, and the results do not establish that their sources' claims are correct.
- OpenResearch evidence is one 3-result keyword discovery and two full-paper retrievals (2608.02583 with no version recorded; 2609.05760 on 0.2.7). Discovery quality, handling of missing or ambiguous papers and exhaustive coverage are unestablished. The CLI Rust suite was not run because cargo and rustc were unavailable. The 0.2.7 pin is behind upstream v0.2.8, which is unqualified.
- Crawl4AI, Cua Driver, Firecrawl MCP and Browser Use have only source review. They are untested, not failed.
- No lifetime token savings or full lifecycle recovery has been measured for any winner.
- lanes disagreed: claude=agent-browser,openresearch,tavily-cli; codex=agent-browser,tavily-cli; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-web-research-20260922.json

Lanes: disagree (claude: foundation-web-research-20260922; codex: foundation-web-research-20260922)

#### Workers and task ownership (workers)

- claude-code @ 2.1.278 — This verdict comes from my own source review of retained receipts. No head-to-head comparison was run. The requirement has three parts: delegate bounded work, keep owned edits and failed results, and integrate only after review.

c12 (Claude native workers) is the only adopted candidate with retained executed evidence of an owned writing child that also keeps its failed results. c7 (Worktrunk) was qualified separately as the owned-worktree lifecycle tool. It did not provide the isolation used by the delegated child.

(1) Bounded delegation, native execution (c12). On Claude Code 2.1.278, one foreground native Opus child ran with the role's native `isolation: worktree`, not a Worktrunk worktree. It changed only planner.py in that worktree. The seed failed 8 of 12 visible tests. Afterwards all 12 unchanged tests passed. An independent oracle checked all 65,536 four-node graphs, and the primary checkout stayed clean (blueprints/convergence-practice/native-worker/README.md lines 3-26 and 42-44; catalogs/foundation/decisions.json owned-native-child, lines 338-376). The oracle was author-written and visible to the worker (README lines 35-37).

(2) Failed results kept, local integration fixture (c12). native-workflow-graceful-recovery (decisions.json lines 2600-2650) records a selected reviewer stop that kept a failed child and a null result. Replay reused the completed implementation. A same-session resume integrated the repair and kept later user edits. 29 visible and seven hidden checks passed. The record calls this "a local integration fixture, not an unchanged upstream product test".

(3) Interruption recovery, native execution on one synthetic same-host task (c12). The sequence was cancellation, continuation of the same child, parent SIGKILL, systemd cgroup cleanup and finalization of the same child. It produced one effect (decisions.json lines 2324-2383; blueprints/convergence-practice/worker-recovery/README.md lines 1-17).

(4) Owned edits, native execution (c7), on a synthetic repository with no model child.
- Worktrunk 0.78.0 created and listed owned worktrees, then removed them.
- It refused a dirty removal without loss (blueprints/convergence-practice/wsl-native-tools/receipt.json line 10 and lines 27-30).
- decisions.json owned-worktrees (lines 478-521) marks it selection "default", accepted_within_scope.
- Only a native old/new comparison of the corrected child working directory covers the packet pin 0.79.0. Its Rust suite was not run (docs/full-stack-convergence.md lines 124-130).
- docs/token-native-saturation.md line 121 rates worktrunk only "optional | use, cleanup | supporting workflow / 0".

(5) Review before integration: decisions.json lines 2672 and 2676 record eight native review-changes runs. The gate was fix-and-commit after independent review; the strict accepted status was never returned. c8/c11 also have executed review evidence: a native Claude-to-Codex foreground review returned (recipes/claude-codex-foreground-review.md lines 20-29). That covers only the review part, not delegation of owned edits.

docs/foundation-convergence-20260921.md line 20 records the project's decision to retain this setup. That is a claim, not extra evidence. The weakest winner evidence class is local_integration, because (2) is only a local fixture.
- worktrunk @ 0.79.0 — This verdict comes from my own source review of retained receipts. No head-to-head comparison was run. The requirement has three parts: delegate bounded work, keep owned edits and failed results, and integrate only after review.

c12 (Claude native workers) is the only adopted candidate with retained executed evidence of an owned writing child that also keeps its failed results. c7 (Worktrunk) was qualified separately as the owned-worktree lifecycle tool. It did not provide the isolation used by the delegated child.

(1) Bounded delegation, native execution (c12). On Claude Code 2.1.278, one foreground native Opus child ran with the role's native `isolation: worktree`, not a Worktrunk worktree. It changed only planner.py in that worktree. The seed failed 8 of 12 visible tests. Afterwards all 12 unchanged tests passed. An independent oracle checked all 65,536 four-node graphs, and the primary checkout stayed clean (blueprints/convergence-practice/native-worker/README.md lines 3-26 and 42-44; catalogs/foundation/decisions.json owned-native-child, lines 338-376). The oracle was author-written and visible to the worker (README lines 35-37).

(2) Failed results kept, local integration fixture (c12). native-workflow-graceful-recovery (decisions.json lines 2600-2650) records a selected reviewer stop that kept a failed child and a null result. Replay reused the completed implementation. A same-session resume integrated the repair and kept later user edits. 29 visible and seven hidden checks passed. The record calls this "a local integration fixture, not an unchanged upstream product test".

(3) Interruption recovery, native execution on one synthetic same-host task (c12). The sequence was cancellation, continuation of the same child, parent SIGKILL, systemd cgroup cleanup and finalization of the same child. It produced one effect (decisions.json lines 2324-2383; blueprints/convergence-practice/worker-recovery/README.md lines 1-17).

(4) Owned edits, native execution (c7), on a synthetic repository with no model child.
- Worktrunk 0.78.0 created and listed owned worktrees, then removed them.
- It refused a dirty removal without loss (blueprints/convergence-practice/wsl-native-tools/receipt.json line 10 and lines 27-30).
- decisions.json owned-worktrees (lines 478-521) marks it selection "default", accepted_within_scope.
- Only a native old/new comparison of the corrected child working directory covers the packet pin 0.79.0. Its Rust suite was not run (docs/full-stack-convergence.md lines 124-130).
- docs/token-native-saturation.md line 121 rates worktrunk only "optional | use, cleanup | supporting workflow / 0".

(5) Review before integration: decisions.json lines 2672 and 2676 record eight native review-changes runs. The gate was fix-and-commit after independent review; the strict accepted status was never returned. c8/c11 also have executed review evidence: a native Claude-to-Codex foreground review returned (recipes/claude-codex-foreground-review.md lines 20-29). That covers only the review part, not delegation of owned edits.

docs/foundation-convergence-20260921.md line 20 records the project's decision to retain this setup. That is a claim, not extra evidence. The weakest winner evidence class is local_integration, because (2) is only a local fixture.

Alternatives:
- Codex native workers (conditional) — Complementary cross-family worker and reviewer, not a separate default for this layer.

Its retained native evidence covers two things:
- Session resume: Codex on Mac and Claude on WSL resumed the same session (packet native-session-resume, lines 330-338).
- Review: native Codex independently reviewed the paper-guard correction (docs/foundation-rd-readiness.md lines 39-43 and 53-55).

It does not cover an owned writing child. In lean-workflow-child-routing, the Codex agent examples 'inherit model and effort and have no end-to-end run of their own' (decisions.json line 2678). agent-sdk-runtime-selection is source_review: 'no new execution was run' (decisions.json lines 2823-2862). No retained record shows a Codex-owned bounded writing child in an owned worktree that keeps its failed results.
- Codex for Claude companion (conditional) — Review bridge, not a delegation runtime. It has executed evidence for the review part of the requirement: one literal foreground /codex:review returned 'No actionable regressions were found' on a three-file paper-guard diff (recipes/claude-codex-foreground-review.md lines 20-37; evidence/receipts/foundation-rd-20260921.json lines 3 and 10-15).

Remaining gaps:
- The companion-backend decision is still partial_acceptance (decisions.json lines 378-424).
- Same-workspace concurrency, Workflow background polling and interrupted reviews are unqualified (recipe lines 48-50).
- SessionEnd shuts down the workspace broker without checking which session owns it (recipe lines 41-53).
- Beads (conditional) — Complements delegation; it does not replace it. Native Beads persisted task claims and dependency transitions in the selected fixture. Its recovery stage is 'not_established', and 'A queue is not worker cancellation, distributed lease correctness or restored task-effect acceptance' (decisions.json dependency-task-queue, lines 426-476, recovery lines 469-471). Useful only when tasks have real ordering to gate.
- DeerFlow (conditional) — Its native evidence is a historical native_model_e2e receipt at an older revision (42334f26d7025d905678f9075b079fc65f9beaf9; research-receipt.json lines 4 and 22). One embedded invoke_acp_agent research prompt completed. That was embedded tool invocation only (line 12), and the 'read-only' mode mapped to workspaceWrite with an on-request approval policy (line 13), so strict read-only enforcement was not established.

No full planner/UI, owned-edit worktree, failed-result retention or recovery was accepted. The current reviewed pin 656db1223dda8883a09e7fde23f89da3a1a7a7dc has source review only (catalogs/landscape/candidate-quality-review.json lines 81-142, disposition conditional at line 85).
- Deep Agents (conditional) — I keep the retained review's 'conditional' disposition (candidate-quality-review.json line 147); nothing I read contradicts it. The condition is unmet. The evidence is pinned source review only (c9926b1a96d204309d0b211701b288ce3bb4244b): 'no new install, upstream test execution, native model operation, matched answer-quality comparison or recovery acceptance', and measured cost is unknown (lines 143-198). docs/candidate-quality-review-20260921.md line 44 calls it a serious challenger, pending the same task, permission-boundary, recovery and cost comparison.
- OpenHands SDK (conditional) — The retained review (candidate-quality-review.json line 203) and docs/foundation-closure-20260921.md line 86 both mark it conditional for remote/container workers. I keep that disposition. The evidence is source review only (pin 9bc452ebf6b0093c531f25394c5ba5e9817ff910), with no install, native-account or recovery acceptance (lines 199-256). Installing it does not improve local review.
- OpenHands Agent Canvas (conditional) — The retained review marks it conditional (candidate-quality-review.json line 261) as a prospective host for existing native Claude/Codex ACP workers, not a replacement worker. 'Its hosting, account boundaries, persistence and migration remain unqualified here' (lines 257-314). Nothing was executed.
- Microsoft Agent Framework (conditional) — The retained review marks it conditional (candidate-quality-review.json line 319), but 'It closes a source-review coverage gap, not a demonstrated runtime gap' (lines 315-370). There was no install, test execution or recovery acceptance.
- LangGraph (conditional) — 'Deferred unless building an application needing these semantics' (docs/foundation-closure-20260921.md line 85). It stays keep-but-compare until a concrete application or a durable cross-host requirement exceeds the native path (docs/foundation-rd-readiness.md line 26). Only version metadata was reviewed; nothing was executed.
- Temporal (out_of_scope) — Not adopted; the recorded decision is defer_new_service. A production service adds persistence/visibility databases, schema upgrades, auth and archival, and start-dev is developer evidence only (catalogs/us-equities/hosting-source-review.json lines 48-65). It targets cross-host durable workflows, which this layer does not currently require (docs/foundation-closure-20260921.md line 84).

Overturn when: Overturn if a real task needs durable multi-host state, approval waits or effect recovery beyond native workers, and a challenger arm matches or beats the baseline on the same frozen tasks. The candidate challengers are Deep Agents, OpenHands SDK, DeerFlow at a current pin, and Codex-owned writing children.

The baseline arm is what the fixture actually ran: a Claude native worker (c12) with the role's native `isolation: worktree`. A Worktrunk-created (c7) worktree for the same child was never run on the fixture. It is a separate, unexecuted arm.

The frozen tasks are:
- the bounded-repair fixture in blueprints/convergence-practice/native-worker/: all 12 unchanged tests pass, the independent permutation oracle passes, and the primary checkout stays clean;
- the cancellation, crash-continuation and single-effect case in blueprints/convergence-practice/worker-recovery/.

Every arm must also keep failed or null child results and integrate only after independent review.

The artifact replay is `python3 -m unittest -v tests.test_native_worker_fixture`. It replays offline artifacts only and launches no model, so every arm needs its own native execution receipt.

Open gaps:
- No executed head-to-head comparison exists between native workers and any challenger. The 2026-09-21 refresh installed none of them (docs/candidate-quality-review-20260921.md lines 55-58).
- No model-child run used a Worktrunk worktree. The fixture used Claude's native isolation: worktree (blueprints/convergence-practice/native-worker/README.md lines 10-11 and 42-44). Worktrunk's dirty-removal refusal was observed on 0.78.0, not the 0.79.0 pin (blueprints/convergence-practice/wsl-native-tools/receipt.json line 10). docs/token-native-saturation.md line 121 rates worktrunk optional, while decisions.json line 487 selects it as default.
- Native Workflow hard crash, physical-host reboot, remote provider cancellation and external exactly-once effects are unqualified (docs/foundation-convergence-20260921.md lines 95-100).
- Complete accounting is unresolved: recovery native cumulative usage exceeds deduplicated persisted usage by 205701 tokens (decisions.json line 2624).
- Worker recovery covers one synthetic same-host task. The restricted Bash-only role is unqualified (decisions.json lines 2348-2350).
- Worktree crash cleanup that deletes no unrelated or dirty state is not proven. Worktrees do not isolate permissions, accounts or shared services (decisions.json lines 500-507). The Worktrunk Rust suite was not run (docs/full-stack-convergence.md lines 128-130).
- The review workflow's strict accepted status was never returned; the gate was fix-and-commit after independent review. The project-only settings profile is not qualified (decisions.json lines 2676 and 2679).
- The owned-native-child oracle is author-written and visible to the worker, so it is not a held-out benchmark (blueprints/convergence-practice/native-worker/README.md lines 35-37).
- Beads queue restart and recovery are not established (decisions.json lines 469-471). Companion same-workspace concurrent sessions and interrupted reviews are unqualified (recipes/claude-codex-foreground-review.md lines 48-50).
- lanes disagreed: claude=claude-code,worktrunk; codex=claude-code,codex,worktrunk; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-workers-20260922.json

Lanes: disagree (claude: foundation-workers-20260922; codex: foundation-workers-20260922)


### us-equities

| Layer | Group | Verdict status | Winner(s) + pin | Evidence class | Alternatives | Overturn when | Recipe anchor | Platform status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agents-models-workers | foundation-memory | recorded | codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0; foundation-ai-memory @ v2.3.1; foundation-socraticode @ v1.14.0 | native_proven | 19 | Run a preregistered same-task comparison on the same frozen public receipts, with a matched budget and the documented i… | blueprints/us-equities/workers/receipt.json, evidence/receipts/native-memory.json, evidence/receipts/native-rag.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| backtesting-engine | engines-strategies | recorded | nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e); lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f | native_proven | 4 | Rerun the bound comparator against the pinned oracle with this command: `python3 blueprints/us-equities/engine-nautilus… | blueprints/us-equities/engine/README.md, evidence/receipts/native-nautilus-v2-20260920.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| data-quality-orchestration | agents-operations | recorded | dagu @ v2.16.6; data-pandera @ v0.33.1; source 62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6 | synthetic | 2 | Two checks could change this verdict. First, an executed same-fixture comparison in which Temporal (server v1.32.0, Pyt… | blueprints/us-equities/hosting/README.md, catalogs/landscape/us-equities.json | linux-wsl2-x86_64: conditional; macos-arm64: untested |
| evaluation-experiments | agents-operations | recorded | foundation-agent-retrieval-bench @ v0.2.1; inspect-ai @ inspect-ai0.3.266; source ec4dfc6953784dc45b79de3147530c89868c6e26; data-mlflow @ v3.16.1; source 32792afe5b0183fce10532d3a023f5cfa8612d09 | source_review | 4 | Any one of these would change the verdict:
1. c7 is replaced if another candidate's evaluator, replaying the frozen ret… | catalogs/landscape/us-equities.json | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| execution-broker | engines-strategies | pending | - | - | 0 | Reopen the implementation choice if Nautilus cannot preserve a required cash/order semantic, fails a preregistered SPY/… | - | - |
| identity-provenance | data-research | recorded | data-dvc @ 3.67.1; source 356dfa03278058b02df42124f243c2c345329dae | source_review | 7 | Change the default after an executed DVC-versus-ArcticDB-or-Iceberg comparison using blueprints/us-equities/point-in-ti… | catalogs/landscape/us-equities.json | linux-wsl2-x86_64: not_established; macos-arm64: untested |
| market-data-reference | data-research | recorded | data-alpaca-py @ v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28; data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a; data-exchange-calendars @ 4.13.2; source dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a | native_proven | 9 | Change the verdict for the prices/corporate-actions scope, replacing c9 with c14 Databento or c7 Massive, when all of t… | blueprints/us-equities/catalyst-provenance/receipt.json, blueprints/us-equities/data/receipt.json, catalogs/landscape/us-equities.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| observability-hosting | agents-operations | pending | - | - | 0 | Escalate to another scheduler, graph or host only when a specified long-running workflow, host-loss recovery, asset/bac… | - | - |
| portfolio-risk | engines-strategies | recorded | skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee | native_proven | 3 | Reopen the choice if any of these checks fails: (a) `python3 -m unittest discover -s tests -p test_research_evaluation.… | blueprints/us-equities/research-evaluation/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| research-factors-ml | engines-strategies | recorded | skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee; data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a | native_proven | 20 | Revisit this verdict in any of the following cases. Checks (1) and (2) re-run the evidence behind the winners. Checks (… | blueprints/us-equities/catalyst-provenance/receipt.json, blueprints/us-equities/research-evaluation/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| security-supply-chain | agents-operations | recorded | grype @ v0.119.0; syft @ v1.52.0; gitleaks @ v8.30.1 | native_proven | 2 | Change the verdict if any of these happens.
1. `python3 -m unittest tests.test_supply_chain_scan` fails against bluepri… | blueprints/us-equities/supply-chain/README.md, blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json, recipes/README.md | linux-wsl2-x86_64: accepted; macos-arm64: untested |
| storage-compute | data-research | recorded | data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa | native_proven | 10 | Three checks could change the verdict.

1. Re-run blueprints/us-equities/data/summarize_backtest.py with pinned duckdb=… | blueprints/us-equities/data/receipt.json | linux-wsl2-x86_64: accepted; macos-arm64: untested |

### us-equities (per-layer narrative)

#### Agents, models and workers (agents-models-workers)

- codex-native-sdk @ CLI rust-v0.155.1; Python openai-codex 0.154.0 — I judged this from source review of retained receipts, against the layer title 'Agents, models and workers' and its scope terms (native-workers, sdk, durable-memory, handoff, code-retrieval). I did not observe any of these runs happening now. The native-execution receipts for the three winners are dated 2026-09-19 (workers/receipt.json line 3, native-memory.json line 5, native-rag.json line 5). desktop-direct-rag.json has no date field. artifact-reductions.json is an artifact measurement with 0 model requests, not a native execution.

(1) c20 codex-native-sdk. blueprints/us-equities/workers/receipt.json records one native run with status "completed": configured_model gpt-6-astra, duration_ms 58410, totalTokens 135311. It returned the exact engine and DeerFlow facts: 3943 data points, 3 simulated orders, 0 failed data requests, 23 skills. Across all three native turns, 1 research task succeeded and 2 file-extraction tasks were blocked, with totalTokens 204091 (lines 215-219). blueprints/us-equities/workers/policy.md holds the research-worker policy: no orders or credential stores, one retrieval lane per artifact, and usage reported only when returned. It is the only adopted candidate that ran a native worker model through the official SDK with an explicit read_only sandbox.

(2) c7 ai-memory. evidence/receipts/native-memory.json records both native clients retrieving the same scoped durable page. Codex 0.155.1 returned exit_code 0 with 8 observations. Claude 2.1.277 returned 9 observations, cross_client_handoff_received true, using explicit workspace/project scope. evidence/receipts/desktop-direct-rag.json records a direct Desktop read that the receipt labels coordinator-observed.

(3) c12 SocratiCode. evidence/receipts/native-rag.json records both native clients returning the identical result for one limit-1 query: tools/ecosystem/linux-usage-report.cjs lines 2-39, score 0.6429. The index held 35 files and 139 chunks, collection status green, with real 2048-dimension local embeddings. Automatic add/update/delete watching took about 3.0 s per phase. evidence/receipts/artifact-reductions.json measures an exact artifact selection of 2731 to 491 o200k tokens. It says this is not provider savings or a retrieval-quality score.

The winner set's weakest class is native_proven. It covers workers, durable cross-client memory and exact-scope code retrieval. It is not a measured comparison against the alternatives.
- foundation-ai-memory @ v2.3.1 — I judged this from source review of retained receipts, against the layer title 'Agents, models and workers' and its scope terms (native-workers, sdk, durable-memory, handoff, code-retrieval). I did not observe any of these runs happening now. The native-execution receipts for the three winners are dated 2026-09-19 (workers/receipt.json line 3, native-memory.json line 5, native-rag.json line 5). desktop-direct-rag.json has no date field. artifact-reductions.json is an artifact measurement with 0 model requests, not a native execution.

(1) c20 codex-native-sdk. blueprints/us-equities/workers/receipt.json records one native run with status "completed": configured_model gpt-6-astra, duration_ms 58410, totalTokens 135311. It returned the exact engine and DeerFlow facts: 3943 data points, 3 simulated orders, 0 failed data requests, 23 skills. Across all three native turns, 1 research task succeeded and 2 file-extraction tasks were blocked, with totalTokens 204091 (lines 215-219). blueprints/us-equities/workers/policy.md holds the research-worker policy: no orders or credential stores, one retrieval lane per artifact, and usage reported only when returned. It is the only adopted candidate that ran a native worker model through the official SDK with an explicit read_only sandbox.

(2) c7 ai-memory. evidence/receipts/native-memory.json records both native clients retrieving the same scoped durable page. Codex 0.155.1 returned exit_code 0 with 8 observations. Claude 2.1.277 returned 9 observations, cross_client_handoff_received true, using explicit workspace/project scope. evidence/receipts/desktop-direct-rag.json records a direct Desktop read that the receipt labels coordinator-observed.

(3) c12 SocratiCode. evidence/receipts/native-rag.json records both native clients returning the identical result for one limit-1 query: tools/ecosystem/linux-usage-report.cjs lines 2-39, score 0.6429. The index held 35 files and 139 chunks, collection status green, with real 2048-dimension local embeddings. Automatic add/update/delete watching took about 3.0 s per phase. evidence/receipts/artifact-reductions.json measures an exact artifact selection of 2731 to 491 o200k tokens. It says this is not provider savings or a retrieval-quality score.

The winner set's weakest class is native_proven. It covers workers, durable cross-client memory and exact-scope code retrieval. It is not a measured comparison against the alternatives.
- foundation-socraticode @ v1.14.0 — I judged this from source review of retained receipts, against the layer title 'Agents, models and workers' and its scope terms (native-workers, sdk, durable-memory, handoff, code-retrieval). I did not observe any of these runs happening now. The native-execution receipts for the three winners are dated 2026-09-19 (workers/receipt.json line 3, native-memory.json line 5, native-rag.json line 5). desktop-direct-rag.json has no date field. artifact-reductions.json is an artifact measurement with 0 model requests, not a native execution.

(1) c20 codex-native-sdk. blueprints/us-equities/workers/receipt.json records one native run with status "completed": configured_model gpt-6-astra, duration_ms 58410, totalTokens 135311. It returned the exact engine and DeerFlow facts: 3943 data points, 3 simulated orders, 0 failed data requests, 23 skills. Across all three native turns, 1 research task succeeded and 2 file-extraction tasks were blocked, with totalTokens 204091 (lines 215-219). blueprints/us-equities/workers/policy.md holds the research-worker policy: no orders or credential stores, one retrieval lane per artifact, and usage reported only when returned. It is the only adopted candidate that ran a native worker model through the official SDK with an explicit read_only sandbox.

(2) c7 ai-memory. evidence/receipts/native-memory.json records both native clients retrieving the same scoped durable page. Codex 0.155.1 returned exit_code 0 with 8 observations. Claude 2.1.277 returned 9 observations, cross_client_handoff_received true, using explicit workspace/project scope. evidence/receipts/desktop-direct-rag.json records a direct Desktop read that the receipt labels coordinator-observed.

(3) c12 SocratiCode. evidence/receipts/native-rag.json records both native clients returning the identical result for one limit-1 query: tools/ecosystem/linux-usage-report.cjs lines 2-39, score 0.6429. The index held 35 files and 139 chunks, collection status green, with real 2048-dimension local embeddings. Automatic add/update/delete watching took about 3.0 s per phase. evidence/receipts/artifact-reductions.json measures an exact artifact selection of 2731 to 491 o200k tokens. It says this is not provider savings or a retrieval-quality score.

The winner set's weakest class is native_proven. It covers workers, durable cross-client memory and exact-scope code retrieval. It is not a measured comparison against the alternatives.

Alternatives:
- foundation-toon (out_of_scope) — evidence/receipts/portable-cli-artifacts.json records only a native CLI encode/decode roundtrip on fixtures/records.json. Both toon-encode and toon-decode returned exit 0 and the roundtrip matched. evidence/receipts/component-history.json lists native_claude, native_codex and current_desktop as 'not independently demonstrated'. Line 139 records a nested fixture growing from 69 to 94 tokens. It is a serialization aid, not a worker, memory or retrieval lane.
- foundation-pageindex (unqualified) — The evidence is source review only: the packet cites upstream README and release URLs and no local execution. The pin (v0.2.18) is behind upstream (v0.2.19). No document-tree retrieval run on financial or code sources is retained. A source-only candidate has not failed.
- langgraph (unqualified) — The evidence is source review only; the packet's ref is the sdk==0.4.4 README. The card says the import command is installation smoke only, not a working agent, and that InMemorySaver loses state on restart. No retained receipt shows a native graph worker completing a task.
- vllm (conditional) — It is the embedding runtime that supports the SocratiCode winner, not a worker or retrieval lane. evidence/receipts/vllm-compatibility.json records latest 0.29.0 installing but failing GPU startup with 'RuntimeError: UVA is not available'. Active 0.25.0 was restored. The failure is host-specific. evidence/receipts/desktop-direct-rag.json shows active_model_service_version 0.25.0. No serving benchmark exists.
- omniroute (conditional) — blueprints/us-equities/routing/astra-receipt.json records three attempts. The first returned HTTP 400 ('requires a newer version of Codex'). The second ended with gateway 499 and no provider usage reported. After client-version alignment, one two-sentence text request completed using 136 tokens. blueprints/us-equities/routing/README.md says tools, compaction, deferred tools, full context and worker parity are still unproved. health-receipt.json is a status-only HTTP 200. It is an optional gateway, not a demonstrated worker substitute.
- foundation-repomix (conditional) — evidence/receipts/portable-cli-artifacts.json shows a native CLI pack of two fixture files with exit 0. evidence/receipts/component-history.json (line 212) records one root pack/full/outline comparison that went from 3679 to 645 o200k tokens and was lossy. Native Claude and native Codex use is recorded as 'not independently demonstrated'. The card says compression is not adequate evidence of correctness. The pin (v1.18.0) is behind upstream (v1.18.1).
- Serena (overlap) — evidence/receipts/native-context-memory.json records completed historical Codex find_symbol and find_referencing_symbols calls, but no returned result. evidence/receipts/component-history.json (lines 98-104) says native Claude retrieved a symbol and 3 references. It labels that inventory a provenance statement, not a new live test. Serena is a complementary exact-symbol lane; it does not replace durable memory or conceptual retrieval. Its cross-client evidence is weaker than c12's identical two-client result. The installed version is 2.0.0.dev0 @ c6fbd1c5, not the packet pin v1.7.0. No retrieval-quality measurement exists.
- foundation-pgvector (unqualified) — The evidence is source review of the upstream README only. The card says a build is not database-extension activation. It also says pgvector adds no benefit over the current Qdrant index unless an SQL integration need is established. No local execution is retained.
- Context Mode (conditional) — In blueprints/us-equities/workers/receipt.json, ctx_execute completed but ctx_execute_file failed three times. The failures came first from the project-root restriction, then from approval policy 'never' (line 196). That left 2 extraction tasks blocked. observability/restart-receipt.json exposes 11 tools and reports estimated_tokens_saved 0 at the snapshot. evidence/receipts/native-context-memory.json records native calls that passed. It is a tool-output lane, and its file extraction inside the SDK worker is still blocked.
- RTK (overlap) — It is a tool-output compaction lane, not a worker or memory layer. evidence/receipts/artifact-reductions.json records a historical rtk artifact reduced from 533 to 176 tokens (66.98%). evidence/receipts/component-history.json says automatic RTK in Codex was not established, and short native Claude commands showed zero estimated reduction. These counters are estimates, not provider savings.
- foundation-codebase-memory-mcp (overlap) — evidence/receipts/native-cli-gaps.json records Claude running search_graph and trace_path through the mcporter CLI bridge. evidence/receipts/desktop-cli-workflows.json records a static graph search and trace in the Codex Desktop task. evidence/receipts/component-history.json records direct native_claude and native_codex use as 'not independently demonstrated'. It is a static-graph fallback that overlaps Serena and SocratiCode. No quality measurement exists.
- Graphiti (unqualified) — The evidence is source review of the upstream README and release only. The card says there is no graph deployment and no extraction-accuracy proof, and that the default examples need model API credentials.
- Qdrant (overlap) — It is the vector store behind the SocratiCode winner. evidence/receipts/native-rag.json shows collection status green with persisted add/update/delete. It has no independent retrieval role, and the card says there is no financial-document corpus yet.
- codex-acp (conditional) — blueprints/us-equities/deerflow/native-receipt.json covers discovery only, with no prompt. blueprints/us-equities/deerflow/research-receipt.json records one completed ACP prompt that returned the correct facts (3943/3/0/23) with 42345 cumulative tokens and 0 blocked tasks. Its ACP 'read-only' mode maps to a workspaceWrite sandbox with approvalPolicy on-request, and strict filesystem read-only enforcement is not established (research-receipt.json line 13). The direction to use the official SDK worker (c20) when read-only enforcement is required comes from blueprints/us-equities/deerflow/README.md lines 24-25 and 133, not from the receipts. That run read files with head -c rather than through Context Mode, so it is not a matched comparison with c20. It is an adapter over the same native Codex backend.
- deerflow (conditional) — blueprints/us-equities/deerflow/research-receipt.json records one embedded invoke_acp_agent call that returned correct counts. The call was not a planner, UI, scheduler or hosted service, and DeerFlow discarded the ACP usage. It ran on a development commit (2.1.0-rc0), not stable v2.0.0. blueprints/us-equities/deerflow/native-receipt.json covers discovery and health with memory and scheduling disabled. blueprints/us-equities/deerflow/README.md (lines 19-28) says not to adopt the ACP profile as a protected unattended worker.
- foundation-agent-retrieval-bench (unqualified) — The evidence is source review only. The card says no benchmark was downloaded or evaluated, and its 427 examples are not a financial-document benchmark. It is an evaluation harness, not a lane.
- loopx-project/loopx (unqualified) — It is a non-adopted newcomer with no retained evidence refs. Its note only describes the qualifying test: restart and quota survival compared with the current coordinator.
- gastownhall/beads (unqualified) — It is a non-adopted newcomer with no retained evidence refs in this packet. There is no measured reduction in rework against the current coordinator.
- jdx/mise (out_of_scope) — It is a non-adopted newcomer with no retained evidence. It covers runtime and toolchain reproduction, not agents, models or workers.

Overturn when: Run a preregistered same-task comparison on the same frozen public receipts, with a matched budget and the documented interpreters and required arguments. The three arms are:
- c20: "$SDK_ENV/bin/python" blueprints/us-equities/workers/native_worker.py run --codex-bin --codex-home --workspace --receipt --prompt --deadline-seconds 180 (the command at blueprints/us-equities/workers/receipt.json line 106).
- DeerFlow via codex-acp: "$DEERFLOW_HOME/backend/.venv/bin/python" blueprints/us-equities/deerflow/native-research.py --node --adapter --codex-bin --codex-home --state-dir --readiness (the command at blueprints/us-equities/deerflow/research-receipt.json line 47).
- OmniRoute: "$WORKER_PYTHON" blueprints/us-equities/routing/omniroute-astra.py --base-url http://127.0.0.1:20128/v1 --output-dir (routing/README.md lines 74-78).

Every arm must use the same file-extraction method. Replace or supplement c20 if another arm returns the same facts while completing more tasks, blocking fewer extractions, enforcing a strict read-only filesystem and using fewer total and failed-attempt tokens.

Replace or supplement c7 or c12 if a held-out code/financial-source retrieval set, run at the same context budget, shows a candidate with better exact-source recall, abstention and source recovery. The retrieval candidates are Serena, codebase-memory-mcp, pgvector, PageIndex and Graphiti.

Open gaps:
- No measured head-to-head comparison exists between the worker backends (codex-native-sdk, DeerFlow/codex-acp, OmniRoute). Each ran separately on a different task. The c19+c21 run returned the same facts in 1 of 1 tasks, with 0 blocked and 42345 cumulative tokens. c20 used 135311 tokens (204091 across all three turns). c19 read files with head -c, while c20's task required Context Mode extraction, so the numbers are not comparable.
- The codex-native-sdk worker completed 1 research task. 2 follow-up extraction tasks were blocked, first by the Context Mode ctx_execute_file project-root restriction, then by the worker's own deny_all approval mode ('approval policy is "never"', workers/receipt.json line 196). For c20, strict read-only and unblocked extraction currently pull against each other. The turn deadline is neither a process timeout nor a spending cap.
- c20's read-only filesystem mode does not restrict external MCP mutations (workers/receipt.json line 110). The recorded environment supplied no broker keys or broker tools.
- The configured model/provider identity in the worker, ACP and OmniRoute receipts is not independent per-request provider attestation.
- Retrieval quality rests on a single limit-1 query (score 0.6429) in native-rag.json. That is not a holdout or recall measurement. The group's 8/12 exact-source recall figure comes from the packet limitations, not from a file I opened.
- Retrieval of dated financial sources is not established. The Qdrant/SocratiCode receipts record no financial-document corpus.
- ai-memory has automatic briefing, embedding and LLM consolidation disabled, and there is no historical backfill. Its pin (v2.3.1) is behind upstream (v2.4.0).
- The winners' native receipts are dated 2026-09-19 and were not re-executed now. desktop-direct-rag.json carries no date. Current quota and readiness are not established.
- No token-savings claim is supported. Artifact reductions are lossy selections, not provider savings.
- The three selected components have separate native receipts; a single composed SDK worker using both ai-memory and SocratiCode through restart and handoff is not established.
- No selected candidate has demonstrated a representative, independently held-out dated financial-source corpus with revision-aware retrieval, historical availability and calibrated abstention.
- The twelve-query lexical diagnostic measures a separate QMD lane; its results cannot be attributed to SocratiCode or ai-memory.
- Exact source locations were returned in bounded code tasks, but broad source-recovery completeness and semantic retrieval quality remain unqualified.
- The disposable memory lifecycle checks establish project routing and ingestion-time behavior, not tenant authorization, market valid-time semantics, secure erasure or off-host recovery.
- SDK filesystem restrictions do not remove external MCP mutation authority; full process cancellation and provider spending caps remain separate requirements.
- Selected-artifact reductions and cache counters do not establish matched whole-task savings, including failures and retries.
- No non-adopted candidate in this packet has retained comparative evidence sufficient to prefer it.

Lanes: same_winner (claude: us-equities-agents-models-workers-20260922; codex: us-equities-agents-models-workers-20260922)

#### Backtesting engine (backtesting-engine)

- nautilustrader @ 2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e) — The requirement assigns two roles: NautilusTrader as the destination runtime (packet c5 role) and LEAN as the frozen historical comparator, or oracle (packet c4 role). The retained evidence supports this pairing. It does not establish US-equity parity between the two engines.

c5 NautilusTrader 2.0.0rc5 (commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e):
- Native execution of the unchanged upstream synthetic EUR/USD quickstart, isolated and offline under bubblewrap (evidence/receipts/native-nautilus-v2-20260920.json). Runs run-3 and run-4 each record 902 orders, 451 positions, 902 fills and 903 account rows. Ending cash went from 1000000.00 to 1000431.00000 USD, with 431.00 realized PnL and all positions flat. account.csv is byte-identical across the two runs. positions.csv and fills.csv match only after UUID4 normalization. The earlier run-1 and run-2 exited 0 but produced empty reports, and are kept as unsuccessful observations.
- The US-equity evidence is local integration only, not an upstream test. There are two items:
  - A September 21 AAPL diagnostic (blueprints/us-equities/engine-nautilus/equity-replay/receipt.json). The receipt classifies itself as "local integration with retained historical data; not an unchanged upstream test or broker execution". It covers 15 sessions from 2020-08-10 to 2020-08-28. Two runs (final-1 and final-2) exited 0. Each scenario recorded 10 filled orders and 5 closed positions, with realized PnL reconciled:
    - baseline: ending cash 99866.60 USD.
    - fee_slippage_stress: ending cash 99855.60 USD, with 10.00 USD in fees.
    runtime-target.json line 115 records that this diagnostic deliberately avoids corporate-action dates and does not close the parity requirement. Line 131 records that its fills are synthetic.
  - A SPY one_zero parity replay against LEAN (blueprints/us-equities/engine-nautilus/spy-parity/verdict.json). Its verdict is "BLOCKED", with "complete": true and "failed": 4. The four failures are:
    - entry fill price (delta 0.2900)
    - exit fill price (delta -0.4550)
    - end_cash (delta -226.4800)
    - native_end_cash (delta -655.120)
    All four are attributed to the unsupported market_on_open_proxy and distributions_and_cash mappings, with unexplained residue 0.0000. mapping-manifest.json explains why. The simulated exchange rejects AT_THE_OPEN ("time in force AT_THE_OPEN is not currently supported"). The pinned wheel also exposes no mechanism for crediting dividend cash to a backtest account.
- runtime-target.json records Nautilus as "selected_destination" and retained-equity-replay as "reported_execution_blocked_review_incomplete". It records IBKR local_broker_acceptance as "not_established".

c4 LEAN (commit 985ef30ad3ac774218c5ac516b4cb0aa2655730f):
- Native source build: exit 0, 7855 warnings, 0 errors (blueprints/us-equities/engine/receipt.json). The unmodified bundled BasicTemplateFrameworkAlgorithm back-test ran without broker credentials. It completed with 3943 data points and 3 orders (submitted 3, filled 3), and its order_list_hash f209ed42701b0419858e0100595b40c0 matches upstream.
- A patched rebuild (blueprints/us-equities/engine/resolution-receipt.json) recorded 7730 warnings and 0 errors with the same hash. It resolved all 7 reported advisory pairs. Both dependency audits report 0 vulnerable packages.
- The receipt that actually carries the oracle role is blueprints/us-equities/historical-simulation/receipt.json (id native-historical-leverage-stress-20260919, kind native_cli_e2e). mapping-manifest.json lines 47-54 bind the parity harness to it at sha256 06ec065647abd91a0ca2b13da25dd75c3ccd159a3244a241a3207c58b36f95d9. That receipt records six frozen local LEAN SPY simulations over 2019-12-02 to 2020-04-30, with native fill, fee and dividend cash reconciliation. Its one_zero case has:
  - fills at 323.58 and 291.69 (304 shares)
  - dividends of 428.64
  - end cash of 90734.080
  - final quantity 0
  Its status is "accepted_for_known_stress_exposure_and_margin_mechanics_only". The data are bundled upstream sample files, not an accepted vendor dataset.
- runtime-target.json line 35 names "LEAN native source-build and dated historical simulation receipts" as the retained comparison engine.

cvxportfolio (c2) is not a winner. Its only evidence is an upstream README reference (source review), and its card says it is not an order gateway and that its workflow is unexecuted.
- lean @ 985ef30ad3ac774218c5ac516b4cb0aa2655730f — The requirement assigns two roles: NautilusTrader as the destination runtime (packet c5 role) and LEAN as the frozen historical comparator, or oracle (packet c4 role). The retained evidence supports this pairing. It does not establish US-equity parity between the two engines.

c5 NautilusTrader 2.0.0rc5 (commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e):
- Native execution of the unchanged upstream synthetic EUR/USD quickstart, isolated and offline under bubblewrap (evidence/receipts/native-nautilus-v2-20260920.json). Runs run-3 and run-4 each record 902 orders, 451 positions, 902 fills and 903 account rows. Ending cash went from 1000000.00 to 1000431.00000 USD, with 431.00 realized PnL and all positions flat. account.csv is byte-identical across the two runs. positions.csv and fills.csv match only after UUID4 normalization. The earlier run-1 and run-2 exited 0 but produced empty reports, and are kept as unsuccessful observations.
- The US-equity evidence is local integration only, not an upstream test. There are two items:
  - A September 21 AAPL diagnostic (blueprints/us-equities/engine-nautilus/equity-replay/receipt.json). The receipt classifies itself as "local integration with retained historical data; not an unchanged upstream test or broker execution". It covers 15 sessions from 2020-08-10 to 2020-08-28. Two runs (final-1 and final-2) exited 0. Each scenario recorded 10 filled orders and 5 closed positions, with realized PnL reconciled:
    - baseline: ending cash 99866.60 USD.
    - fee_slippage_stress: ending cash 99855.60 USD, with 10.00 USD in fees.
    runtime-target.json line 115 records that this diagnostic deliberately avoids corporate-action dates and does not close the parity requirement. Line 131 records that its fills are synthetic.
  - A SPY one_zero parity replay against LEAN (blueprints/us-equities/engine-nautilus/spy-parity/verdict.json). Its verdict is "BLOCKED", with "complete": true and "failed": 4. The four failures are:
    - entry fill price (delta 0.2900)
    - exit fill price (delta -0.4550)
    - end_cash (delta -226.4800)
    - native_end_cash (delta -655.120)
    All four are attributed to the unsupported market_on_open_proxy and distributions_and_cash mappings, with unexplained residue 0.0000. mapping-manifest.json explains why. The simulated exchange rejects AT_THE_OPEN ("time in force AT_THE_OPEN is not currently supported"). The pinned wheel also exposes no mechanism for crediting dividend cash to a backtest account.
- runtime-target.json records Nautilus as "selected_destination" and retained-equity-replay as "reported_execution_blocked_review_incomplete". It records IBKR local_broker_acceptance as "not_established".

c4 LEAN (commit 985ef30ad3ac774218c5ac516b4cb0aa2655730f):
- Native source build: exit 0, 7855 warnings, 0 errors (blueprints/us-equities/engine/receipt.json). The unmodified bundled BasicTemplateFrameworkAlgorithm back-test ran without broker credentials. It completed with 3943 data points and 3 orders (submitted 3, filled 3), and its order_list_hash f209ed42701b0419858e0100595b40c0 matches upstream.
- A patched rebuild (blueprints/us-equities/engine/resolution-receipt.json) recorded 7730 warnings and 0 errors with the same hash. It resolved all 7 reported advisory pairs. Both dependency audits report 0 vulnerable packages.
- The receipt that actually carries the oracle role is blueprints/us-equities/historical-simulation/receipt.json (id native-historical-leverage-stress-20260919, kind native_cli_e2e). mapping-manifest.json lines 47-54 bind the parity harness to it at sha256 06ec065647abd91a0ca2b13da25dd75c3ccd159a3244a241a3207c58b36f95d9. That receipt records six frozen local LEAN SPY simulations over 2019-12-02 to 2020-04-30, with native fill, fee and dividend cash reconciliation. Its one_zero case has:
  - fills at 323.58 and 291.69 (304 shares)
  - dividends of 428.64
  - end cash of 90734.080
  - final quantity 0
  Its status is "accepted_for_known_stress_exposure_and_margin_mechanics_only". The data are bundled upstream sample files, not an accepted vendor dataset.
- runtime-target.json line 35 names "LEAN native source-build and dated historical simulation receipts" as the retained comparison engine.

cvxportfolio (c2) is not a winner. Its only evidence is an upstream README reference (source review), and its card says it is not an order gateway and that its workflow is unexecuted.

Alternatives:
- cvxportfolio (unqualified) — Evidence is source review only: its sole evidence_ref is an upstream README URL at 1.5.1, not a retained local receipt, and this lane did not open it. No installation, run, cash reconciliation or comparison against the LEAN oracle on the frozen SPY one_zero case is retained. The packet's card limitations say it is a research simulator, not an order gateway, and that its prospective workflow is unexecuted. It could complement portfolio-level research, but on this evidence it can replace neither the destination runtime nor the oracle.
- lumiwealth/lumibot (unqualified) — Not adopted, and the packet has no evidence_refs for it (evidence_refs [], evidence_kind null). No parity replay against the LEAN one_zero oracle, cash reconciliation or paper roundtrip is retained.
- nkaz001/hftbacktest (out_of_scope) — Not adopted, and the packet has no evidence_refs for it. The packet note says it targets limit-order queue position and latency. The current protocol decides on daily or hourly bars with next-session fills, so that capability is not exercised. This rationale is packet text and was not verified from source in this lane.
- whchien/ai-trader (unqualified) — Not adopted, and the packet has no evidence_refs for it. The packet note positions it at most as a bounded research interface. No parity reproduction on the SPY one_zero case is retained.

Overturn when: Rerun the bound comparator against the pinned oracle with this command: `python3 blueprints/us-equities/engine-nautilus/spy-parity/compare.py --receipt blueprints/us-equities/engine-nautilus/spy-parity/receipt.json --lean-data <LEAN 985ef30 Data root> --verdict <out>`. The comparator is bound by blueprints/us-equities/engine-nautilus/spy-parity/mapping-manifest.json and tolerances.json.

The verdict changes in any of three cases:
(a) The Nautilus replay returns FAIL, has an unattributed failure or unexplained cash residue, or breaches a preregistered tolerances.json limit.
(b) Nautilus cannot close market_on_open_proxy or distributions_and_cash, either natively or through a newly preregistered mapping manifest, while a maintained alternative engine reaches PASS on the same frozen one_zero inputs, tolerances and hash bindings.
(c) The oracle's own receipt changes. compare.py lines 202-203 raise oracle_receipt_sha256_mismatch when blueprints/us-equities/historical-simulation/receipt.json no longer hashes to 06ec065647abd91a0ca2b13da25dd75c3ccd159a3244a241a3207c58b36f95d9, or when a native LEAN 985ef30 rerun of its one_zero case no longer reproduces fills at 323.58 and 291.69, dividends of 428.64 and end cash of 90734.080. Either would invalidate LEAN's oracle role.

The bundled-sample order_list_hash f209ed42701b0419858e0100595b40c0 in blueprints/us-equities/engine/receipt.json only shows the build is healthy. A regression in it would prompt a rebuild check, not an oracle overturn by itself. In every case the synthetic boundary checks in `python3 -m unittest tests.test_spy_parity -v` must keep passing.

Open gaps:
- The SPY/LEAN parity gate has not passed. verdict.json is BLOCKED with 4 failed checks. mapping-manifest.json marks market_on_open_proxy and distributions_and_cash as unsupported in Nautilus 2.0.0rc5. The comparison statuses for one_stress, two_zero, two_stress, adaptive_stress and over_limit remain blocked on costs_and_rounding_stress and margin_and_adaptive_state.
- Nautilus's only unchanged upstream native run is on synthetic FX data. Its US-equity evidence is local integration only: the SPY replay (evidence class HIST) and the AAPL diagnostic. The AAPL diagnostic uses synthetic scheduled fills over 15 sessions and deliberately avoids corporate-action dates.
- Nautilus 2.0.0rc5 is a prerelease (runtime-target.json line 29: prerelease true). The packet's upstream metadata lists v1.231.0 as the latest non-prerelease. That version comes from packet-generated metadata, not a retained receipt.
- No IBKR broker acceptance: runtime-target.json records local_broker_acceptance not_established. Native in-flight broker fault behavior is also unqualified.
- The LEAN oracle's SPY simulations run on bundled upstream sample files, not an accepted vendor dataset. Its status is scoped to known stress exposure and margin mechanics only. The Alpaca brokerage model and adapter initialization were not exercised.
- None of the receipts read establishes a causal point-in-time universe, a calibrated fill or cost model, or strategy profitability.
- The spy-parity README says the acceptance set exercises only the --lean-data comparator mode. The independent review count (21 of 24 claims) is not retained in the repository.
- SPY one_zero parity remains BLOCKED: four failed checks concern entry/exit prices and ending cash. Native ending cash differs from LEAN by -655.12 USD, explained by fill-price differences and unposted distributions.
- Nautilus equity evidence is a local integration over 15 retained AAPL bars with synthetic close fills, unlimited modeled depth, and known corporate-action dates excluded.
- Stressed costs, margin, adaptive state, realistic liquidity, and broader corporate-action semantics remain unqualified.
- Causal historical availability, point-in-time universes, independent strategy validation, financing-inclusive performance, and deployable profitability are not established.
- Broker-specific native failure recovery, IBKR acceptance, and continuous paper operation remain open; separate Alpaca receipts do not establish Nautilus adapter acceptance.

Lanes: same_winner (claude: us-equities-backtesting-engine-20260922; codex: us-equities-backtesting-engine-20260922)

#### Data quality and orchestration (data-quality-orchestration)

- dagu @ v2.16.6 — This is my own source review of the retained files. I ran nothing and did not use any TypeSafe inference results. Two candidates win: c3 (Dagu) for orchestration and c4 (pandera) for data quality. They cover separate scope terms and do not overlap. c3 has native CLI end-to-end evidence. blueprints/us-equities/hosting/receipt.json (kind "native_cli_e2e", version "2.16.6", publisher_checksum_matched true) records a successful 3-step run, evidence-20260919-ready, with exit_code 0: summarize, baseline_evidence and catalog_evidence all "succeeded". The receipt keeps the earlier failures, a schema error with exit 1 and a first execution with exit 1. It also records an exit-23 failure fixture that reached status "failed" with its dependent step "aborted", and a native `dagu stop` cancellation that reached "aborted" even though the CLI exited 0. After service_restart_exit 0, prior_history_rows_preserved is true. The service ran with model_calls 0 and broker_calls 0, and its inherited environment was limited to "HOME PATH DAGU_HOME only". blueprints/us-equities/research-runtime/receipt.json (kind "native_model_e2e") shows Dagu 2.16.6 running the packet and order_table steps to "succeeded". It also records paired_model_workflow_executed false and a retained validation failure ("entrypoint document must not define name"). Together, these match the requirement: bounded runs, a supervised owned process, retained failed attempts and history, and no broker authority. c4 has local integration evidence on synthetic fixtures only. blueprints/us-equities/data/README.md documents a fail-closed promotion_gate.py that runs pandera 0.33.1 in an isolated venv. The retained outputs blueprints/us-equities/data/fixtures/good-gate-result.json (status "pass", row_count 4, 12 named checks) and bad-gate-result.json (status "fail"; valid_trading_session, volume_integral_non_negative, observed_at_not_future, high_ge_max_open_close and unique_symbol_session failed) show the gate separating good from bad synthetic snapshots. tests/test_promotion_gate.py reruns these fixtures, but only when the gate venv exists on the host. Because c4 rests on synthetic fixtures, the set's class is "synthetic", the weakest class among the winners.
- data-pandera @ v0.33.1; source 62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6 — This is my own source review of the retained files. I ran nothing and did not use any TypeSafe inference results. Two candidates win: c3 (Dagu) for orchestration and c4 (pandera) for data quality. They cover separate scope terms and do not overlap. c3 has native CLI end-to-end evidence. blueprints/us-equities/hosting/receipt.json (kind "native_cli_e2e", version "2.16.6", publisher_checksum_matched true) records a successful 3-step run, evidence-20260919-ready, with exit_code 0: summarize, baseline_evidence and catalog_evidence all "succeeded". The receipt keeps the earlier failures, a schema error with exit 1 and a first execution with exit 1. It also records an exit-23 failure fixture that reached status "failed" with its dependent step "aborted", and a native `dagu stop` cancellation that reached "aborted" even though the CLI exited 0. After service_restart_exit 0, prior_history_rows_preserved is true. The service ran with model_calls 0 and broker_calls 0, and its inherited environment was limited to "HOME PATH DAGU_HOME only". blueprints/us-equities/research-runtime/receipt.json (kind "native_model_e2e") shows Dagu 2.16.6 running the packet and order_table steps to "succeeded". It also records paired_model_workflow_executed false and a retained validation failure ("entrypoint document must not define name"). Together, these match the requirement: bounded runs, a supervised owned process, retained failed attempts and history, and no broker authority. c4 has local integration evidence on synthetic fixtures only. blueprints/us-equities/data/README.md documents a fail-closed promotion_gate.py that runs pandera 0.33.1 in an isolated venv. The retained outputs blueprints/us-equities/data/fixtures/good-gate-result.json (status "pass", row_count 4, 12 named checks) and bad-gate-result.json (status "fail"; valid_trading_session, volume_integral_non_negative, observed_at_not_future, high_ge_max_open_close and unique_symbol_session failed) show the gate separating good from bad synthetic snapshots. tests/test_promotion_gate.py reruns these fixtures, but only when the gate venv exists on the host. Because c4 rests on synthetic fixtures, the set's class is "synthetic", the weakest class among the winners.

Alternatives:
- Temporal (conditional) — The only evidence is an upstream README URL (https://github.com/temporalio/temporal/blob/v1.32.0/README.md). I could not open it, and I found no local receipt, fixture or test for Temporal that runs failure, cancellation, restart or in-flight recovery. Durable history and activity-level recovery would address Dagu's recorded gap ("Restart acceptance preserves completed history; it does not prove in-flight resumption" in blueprints/us-equities/hosting/receipt.json), but that capability is untested here, not proven. The card also warns that activities retry by default and that unlimited retries are unsuitable for uncertain broker writes. It would also add a server and SDK beyond the single-binary lane. Temporal remains conditional on a specified in-flight or host-loss recovery requirement and an executed comparison.
- modal (unqualified) — The only evidence is a PyPI URL (https://pypi.org/project/modal/1.5.5/), which I could not open. The card says `modal run` executes cloud code that may incur charges and was "not run here". No local execution, identity, telemetry or cost evidence exists. It covers the managed-compute scope term, not orchestration of existing native commands or data-quality validation. Paid hosting is not authorized. The packet also lists upstream latest as v1.3.1 against a 1.5.5 pin, a metadata inconsistency I could not resolve.

Overturn when: Two checks could change this verdict. First, an executed same-fixture comparison in which Temporal (server v1.32.0, Python SDK 1.33.0) passes all the checks recorded for Dagu in blueprints/us-equities/hosting/receipt.json: the exit-23 failure producing status failed with its dependent step aborted, native cancellation reporting aborted, and completed history preserved across a service restart. Temporal would also need to resume an in-flight run after worker or host process loss without a duplicate effect owner, which Dagu has not shown. Second, running `python3 -m unittest tests.test_promotion_gate` with the gate venv present, where any fixture result differs from its retained outcome in blueprints/us-equities/data/fixtures/ (for example, good-gate-result.json no longer passing or bad-gate-result.json no longer failing its five named checks).

Open gaps:
- Dagu: completed-history restart is not recovery of in-flight work (blueprints/us-equities/hosting/receipt.json limitations). No model-worker queue, continuous off-host hosting, VM boundary or trading host is established.
- Dagu: the paired Astra-to-Claude model workflow was not executed (paired_model_workflow_executed false) because the Codex allowance was exhausted (usedPercent 100). The Claude Opus 5 report ran standalone, outside the Dagu graph, so complete returned results from a model worker running inside the orchestrated graph are not established.
- The two Dagu records disagree on dashboard authentication. The hosting receipt (2026-09-19) records basic auth with anonymous 401 and authenticated 200 after restart. The current hosting README says the dashboard now uses upstream auth.mode none, with anonymous API reads returning 200. No retained receipt covers the current auth mode.
- Dagu pin v2.16.6 is behind upstream v2.17.0 (pin_behind_upstream true). The newer release is untested; that means unknown, not failed.
- pandera: evidence covers synthetic CSV fixtures only. It does not establish provider completeness, correct corporate actions, accurate prices, absence of leakage or a production bars/universe ingest. The data README states that no such ingest ships yet.
- pandera: the duckdb:// input path is source-only because the duckdb package is not in the pinned gate install (blueprints/us-equities/data/README.md).
- Temporal and modal have no local execution, failure, cancellation, recovery or telemetry evidence. Their capabilities are untested, not failed.
- No measured comparison between orchestrators exists. The winner set rests on single-lane native and local evidence, not on a head-to-head test.
- lanes disagreed: claude=dagu,data-pandera; codex=dagu; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-data-quality-orchestration-20260922.json

Lanes: disagree (claude: us-equities-data-quality-orchestration-20260922; codex: us-equities-data-quality-orchestration-20260922)

#### Evaluation and experiments (evaluation-experiments)

- foundation-agent-retrieval-bench @ v0.2.1 — I judged fit against the layer title, "Evaluation and experiments", and its scope terms (evaluation, agent-evaluation, experiment-tracking, progressive-evaluation, validation-reporting), as the requirement_note directs. The shared group requirement covers supervision, telemetry and broker isolation. No candidate addresses those directly. Each winner fills a different scope term.

c7 (agent-retrieval-bench) is the only packet candidate with execution evidence. blueprints/convergence-practice/arb-trace2code/receipt.json records kind "actual_upstream_offline_retrieval_evaluation" at the unmodified v0.2.1 tag (commit b487f386...). The pinned upstream tests reported "15 passed in 0.15s". The lexical and bm25 runs each evaluated 101 samples with exit_code 0 and no model or provider calls. blueprints/convergence-practice/local-fixture/evaluation-receipt.json records a frozen 24-query fixture (20 positive queries, 4 no-gold) scored with the native ARB APIs: bm25 MRR 0.9666666666666666 and Recall@1 0.95; lexical MRR 0.9 and Recall@1 0.8. The fixture is source-authored, so it is a local integration check, not a held-out benchmark.

c2 (inspect-ai) is the only adopted candidate for programmable task/solver/scorer agent evaluation. Its evidence is source review only. catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json holds the pinned README and an MIT license at ec4dfc69. Lines 124-125 record installation_performed false and model_calls 0. It stays in the winner set only because the only better-evidenced option for this scope term, promptfoo, is not an adopted packet candidate. Promptfoo is recorded in challenger_preferred.

c1 (data-mlflow) covers experiment tracking. Its evidence is source review only. catalogs/us-equities/data-research.json lines 780-817 hold an immutable commit-pinned README reference (32792afe) and a serverless local SQLite workflow that is marked UNEXECUTED.

Because c1 and c2 are source review only, the class for the whole winner set is source_review, the weakest among the winners.
- inspect-ai @ inspect-ai0.3.266; source ec4dfc6953784dc45b79de3147530c89868c6e26 — I judged fit against the layer title, "Evaluation and experiments", and its scope terms (evaluation, agent-evaluation, experiment-tracking, progressive-evaluation, validation-reporting), as the requirement_note directs. The shared group requirement covers supervision, telemetry and broker isolation. No candidate addresses those directly. Each winner fills a different scope term.

c7 (agent-retrieval-bench) is the only packet candidate with execution evidence. blueprints/convergence-practice/arb-trace2code/receipt.json records kind "actual_upstream_offline_retrieval_evaluation" at the unmodified v0.2.1 tag (commit b487f386...). The pinned upstream tests reported "15 passed in 0.15s". The lexical and bm25 runs each evaluated 101 samples with exit_code 0 and no model or provider calls. blueprints/convergence-practice/local-fixture/evaluation-receipt.json records a frozen 24-query fixture (20 positive queries, 4 no-gold) scored with the native ARB APIs: bm25 MRR 0.9666666666666666 and Recall@1 0.95; lexical MRR 0.9 and Recall@1 0.8. The fixture is source-authored, so it is a local integration check, not a held-out benchmark.

c2 (inspect-ai) is the only adopted candidate for programmable task/solver/scorer agent evaluation. Its evidence is source review only. catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json holds the pinned README and an MIT license at ec4dfc69. Lines 124-125 record installation_performed false and model_calls 0. It stays in the winner set only because the only better-evidenced option for this scope term, promptfoo, is not an adopted packet candidate. Promptfoo is recorded in challenger_preferred.

c1 (data-mlflow) covers experiment tracking. Its evidence is source review only. catalogs/us-equities/data-research.json lines 780-817 hold an immutable commit-pinned README reference (32792afe) and a serverless local SQLite workflow that is marked UNEXECUTED.

Because c1 and c2 are source review only, the class for the whole winner set is source_review, the weakest among the winners.
- data-mlflow @ v3.16.1; source 32792afe5b0183fce10532d3a023f5cfa8612d09 — I judged fit against the layer title, "Evaluation and experiments", and its scope terms (evaluation, agent-evaluation, experiment-tracking, progressive-evaluation, validation-reporting), as the requirement_note directs. The shared group requirement covers supervision, telemetry and broker isolation. No candidate addresses those directly. Each winner fills a different scope term.

c7 (agent-retrieval-bench) is the only packet candidate with execution evidence. blueprints/convergence-practice/arb-trace2code/receipt.json records kind "actual_upstream_offline_retrieval_evaluation" at the unmodified v0.2.1 tag (commit b487f386...). The pinned upstream tests reported "15 passed in 0.15s". The lexical and bm25 runs each evaluated 101 samples with exit_code 0 and no model or provider calls. blueprints/convergence-practice/local-fixture/evaluation-receipt.json records a frozen 24-query fixture (20 positive queries, 4 no-gold) scored with the native ARB APIs: bm25 MRR 0.9666666666666666 and Recall@1 0.95; lexical MRR 0.9 and Recall@1 0.8. The fixture is source-authored, so it is a local integration check, not a held-out benchmark.

c2 (inspect-ai) is the only adopted candidate for programmable task/solver/scorer agent evaluation. Its evidence is source review only. catalogs/convergence-practice/architecture-wave/UKGovernmentBEIS__inspect_ai.json holds the pinned README and an MIT license at ec4dfc69. Lines 124-125 record installation_performed false and model_calls 0. It stays in the winner set only because the only better-evidenced option for this scope term, promptfoo, is not an adopted packet candidate. Promptfoo is recorded in challenger_preferred.

c1 (data-mlflow) covers experiment tracking. Its evidence is source review only. catalogs/us-equities/data-research.json lines 780-817 hold an immutable commit-pinned README reference (32792afe) and a serverless local SQLite workflow that is marked UNEXECUTED.

Because c1 and c2 are source review only, the class for the whole winner set is source_review, the weakest among the winners.

Alternatives:
- data-river (conditional) — River's progressive validation is an online-learning tool. It applies only if streaming model updates are justified. The card's own limitations say immediate synthetic labels are invalid for financial online evaluation, and that delayed fills or returns, late corrections and restarts must be modelled. The workflow is marked UNEXECUTED and the evidence is source review only (catalogs/us-equities/data-research.json lines 1304-1340).
- foundation-mteb (conditional) — MTEB evaluates embeddings, which overlaps the executed retrieval evaluation in c7. Its pin (2.21.0) is behind upstream (2.21.6). The card says its commands were not executed (catalogs/us-equities/foundation-memory.json lines 1210-1245). Other retained artifacts mention MTEB: leaderboard Space metadata and author-reported aggregates in evidence/artifacts/hf-memory-models-20260921/model-manifest.json, and leaderboard page observations in evidence/artifacts/hf-memory-models-20260921/dashboard-observations.json lines 15-33. None of them is a run of the mteb library. native-results.json line 475 states "No full RTEB/MTEB rerun".
- phoenix (conditional) — Phoenix is mainly a trace inspection workspace and overlaps the observability layer. The server launch is prospective, with no app instrumented and no judge-model calls run. The card says PHOENIX_ALLOWED_PROVIDERS=NONE is not an inference authorization boundary (catalogs/us-equities/agents-operations.json lines 1239-1280). The card licenses it as Elastic-2.0 (ELv2), which carries self-host restrictions. The packet's NOASSERTION value is GitHub's license classification, not a conflicting license (screening-ledger.json lines 6714 and 10770).
- promptfoo (conditional) — Promptfoo is not a packet candidate. Its card places it in the agent-evaluation layer with version 0.123.1 and source_review evidence (catalogs/us-equities/agents-operations.json lines 1321-1361). The card's "not run here" is superseded by two later retained local-integration runs of promptfoo 0.123.1. (1) evidence/artifacts/promptfoo-nemotron-upstream-20260921/qualification.json ran the command 'promptfoo eval -c promptfooconfig.yaml --no-cache -j 1 -o results.json report.html' with exit_code 0 and 1 case passed, 0 failed, 0 errors. That run is a four-query embedding example with a locally authored assertion. It also records a browser report check and retains the browser-harness failures. (2) blueprints/native-skill-practice/typesafe-result.json recorded promptfoo_exit_code 100 over an 8-case frozen pack, with the assertion failures retained. Neither run is a matched comparison with inspect-ai. Neither establishes resumability or retry behaviour. It is recorded as challenger_preferred, not selected.

Overturn when: Any one of these would change the verdict:
1. c7 is replaced if another candidate's evaluator, replaying the frozen retrieval fixture (blueprints/convergence-practice/local-fixture/evaluation-receipt.json, with upstream baseline blueprints/convergence-practice/arb-trace2code/receipt.json), gives a different or better-supported ranking on the same 20 positive queries and 4 no-gold queries, with failures retained.
2. c2 is demoted if the matched agent-evaluation comparison fails for inspect-ai or is won by promptfoo. That comparison is the frozen blueprints/native-skill-practice/catalog-cases.json pack under a promptfoo 0.123.1 echo-baseline arm and an inspect-ai 0.3.266 mock-model arm, preceded by 'node --test test-contract.cjs' in blueprints/native-skill-practice/. It covers deterministic scoring, bounded retries, a retained failure log, and interruption and resume, with zero provider calls. A promptfoo win moves the agent-evaluation slot to promptfoo only after the catalog adopts it.
3. c1 is replaced by c3 or another tracker if the experiment runs of the project's chronological evaluation (tests/test_research_evaluation.py) cannot be logged locally with exact data and code revisions and then recovered.

Open gaps:
- lane claude prefers non-adopted promptfoo (https://github.com/promptfoo/promptfoo): requires Run the frozen 8-case pack blueprints/native-skill-practice/catalog-cases.json under two arms. Arm 1 is promptfoo 0.123.1 using only the credential-free echo exact-text-baseline provider from blueprints/native-skill-practice/promptfooconfig.yaml. Arm 2 is an inspect-ai 0.3.266 mock-model task with the same deterministic scorer. Both arms need zero provider calls, bounded concurrency and retries, a retained failure log, and an interruption-and-resume check, which matches inspect-ai's recorded next_acceptance at UKGovernmentBEIS__inspect_ai.json line 123. Run 'node --test test-contract.cjs' from blueprints/native-skill-practice/ first as the existing adapter contract check. Compare scorer reproducibility, fidelity of the retained failure log and resume success. No inspect-ai fixture exists in the repository yet, so arm 2 must be authored and frozen before the run.
- No retained evidence shows inspect-ai, mlflow, river, mteb or phoenix installed or executed. Every workflow for them is prospective or marked UNEXECUTED.
- No retained matched comparison of promptfoo and inspect-ai exists. evidence/artifacts/claude-repository-evidence-20260921/results.json near line 5730 records its absence. The inspect-ai selection is not a measured win, and promptfoo's evidence comes from different tasks: a four-query embedding example and an 8-case TypeSafe diagnostic.
- No inspect-ai fixture exists under fixtures/, blueprints/ or tests/. The agent-evaluation comparison arm for c2 must be authored and frozen before it can run.
- The c7 execution is recorded on Darwin arm64 (arb-trace2code receipt environment), not this PC. It evaluates file-level code retrieval (gin and click are 82 of the 101 samples), not financial-document retrieval, answer quality or net trading performance.
- The local 24-query fixture is source-authored over 15 public docs. It has no abstention metric and makes no significance or default-promotion claim.
- No candidate addresses the shared group requirement on its own: supervised owned processes, native identity, retained failed attempts, recoverable state, or broker-authority isolation. Those remain with the runtime and orchestration layers.
- Progressive evaluation with delayed labels (c4) and validation reporting have no executed evidence in this layer.
- The chronological evaluation (tests/test_research_evaluation.py) is project-local code, not an upstream candidate. No link between it and any experiment tracker is established.
- lanes disagreed: claude=data-mlflow,foundation-agent-retrieval-bench,inspect-ai; codex=data-mlflow,inspect-ai; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-evaluation-experiments-20260922.json

Lanes: disagree (claude: us-equities-evaluation-experiments-20260922; codex: us-equities-evaluation-experiments-20260922)

- **Execution and broker adapters** (execution-broker): pending — lanes disagreed: claude=adaptive-paper-alpaca-adapter,alpaca-py; codex=adaptive-paper-alpaca-adapter,alpaca-py,nautilus-ibkr-adapter; the counterbalanced adjudication did not agree (claude 2, codex 2, 0 refuted; evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-execution-broker-20260922.json); an executed comparison must decide it

#### Identity, provenance and lineage (identity-provenance)

- data-dvc @ 3.67.1; source 356dfa03278058b02df42124f243c2c345329dae — Select c2 provisionally for this layer's reproducibility and data-versioning scope. Source review of the exact pinned [DVC README](https://raw.githubusercontent.com/treeverse/dvc/356dfa03278058b02df42124f243c2c345329dae/README.rst) observed concrete add, dependency-stage, experiment and remote-storage workflows connecting versioned data with code. This is documentation inspection, not native execution. catalogs/us-equities/data-research.json explicitly marks the local workflow unexecuted. Among the adopted candidates, that bounded file-and-dependency contract is the closest supported fit to exact analytical snapshots without an unmeasured broker or lake requirement. The historical native results in blueprints/us-equities/identity-readiness/native-receipt.json separately demonstrate project-local observation cutoffs and quarantine; they are not DVC acceptance. No winner is established for the full acquisition and historical-eligibility requirement.

Alternatives:
- cosign (out_of_scope) — It signs and verifies the identity of software artifacts. It does not provide identity or provenance for equity observations. The packet card records that no signing or identity flow was run here, and that not every upstream publishes signatures. It could later sign snapshot manifests, but no evidence shows it doing so. I could not open the README URL.
- data-kafka (conditional) — It matches the replay-log scope term, but the card says a single-node synthetic replay is only a prospective smoke check, and ordering holds only within a partition. It is a transport log, not a provenance or version store. The packet's existing overturn text says to add a server only after local throughput and concurrency measurements justify it, and the evidence contains none. In the upstream metadata, the latest field is 'show' and the release date is null.
- foundation-socraticode (out_of_scope) — It has the strongest evidence class in the packet. evidence/receipts/native-rag.json records a native_model_e2e run in which tools/ecosystem/linux-usage-report.cjs lines 2-39 were retrieved at score 0.6429, plus add, update and delete index phases. That evidence is about semantic code indexing and keeping the code index fresh. It shows nothing about identity, lineage or availability of US-equity data, so its evidence class does not carry over to this requirement.
- data-arcticdb (conditional) — It fits the versioned-store and snapshot-store terms. However, the card records a BSL-1.1 licence whose production and commercial-use terms are unresolved, and the upstream licence field is NOASSERTION. The card also says storage version time does not prove when market information was available. The evidence is source review only, with no local snapshot or replay comparison.
- data-mlflow (overlap) — It covers model lineage and experiment tracking, which happen after observations are acquired and snapshotted. The card says no experiments or models were run, and that autologging does not capture every data revision. It overlaps DVC's reproducibility role without closing the data-identity requirement.
- data-iceberg (conditional) — It fits the snapshot-store term. The card says that creating a catalog alone would not prove append, multi-writer conflict handling, cross-engine compatibility or time travel, and that storage snapshots do not show what information was available in the past. A table lake is justified only after a measured local need, and the evidence contains no such measurement.
- data-openlineage (conditional) — The retained review provides an unexecuted dataset-object example, with no emitted, persisted or replayed lineage events. Dataset-version and knowledge-cutoff facets remain an integration requirement. No executed comparison establishes a benefit over the initial snapshot manifests; the pinned README could not be retrieved.

Overturn when: Change the default after an executed DVC-versus-ArcticDB-or-Iceberg comparison using blueprints/us-equities/point-in-time/fixture.json and the invariants in tests/test_point_in_time.py and tests/test_security_identity.py shows a candidate preserves exact snapshots and rejection behavior while closing a demonstrated recovery or concurrency gap. A DVC failure on those invariants would also overturn this provisional selection; merely passing the existing project-local tests would not qualify a candidate.

Open gaps:
- DVC has source-review support only: no retained native add, restore and reproduction run demonstrates this repository's equity snapshot contract.
- No candidate evidence establishes the complete requirement: licensed acquisition, permanent security identity, historical universe eligibility, corporate-action completeness and original publication/revision availability remain separate obligations.
- The identity-readiness receipt demonstrates bounded observation-time selection and quarantine through project-local adapters. It does not qualify DVC or another candidate as the executing implementation.
- Content identity, signer identity, storage commit time and code-index freshness cannot substitute for original historical information availability.
- No executed comparison measures snapshot restoration fidelity, correction retention, lineage completeness, recovery, concurrency, storage cost or latency across the candidate stores.
- OpenLineage event persistence and consistent version/cutoff facets, and MLflow run-to-dataset bindings, remain unqualified.
- lanes disagreed: claude=data-dvc,data-openlineage; codex=data-dvc; adjudicated by evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-identity-provenance-20260922.json

Lanes: disagree (claude: us-equities-identity-provenance-20260922; codex: us-equities-identity-provenance-20260922)

#### Market data and reference (market-data-reference)

- data-alpaca-py @ v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28 — These three adopted candidates are the only ones with retained native execution against the requirement. The requirement is to acquire source-identifiable US-equity observations, keep feed, timestamp, identity and corporate-action data, and reject data whose historical availability is unknown. They cover separate scopes (prices and corporate actions, SEC filings, sessions), so they complement each other. Each fact below is a documented-as-done receipt dated 2026-09-19/20, not re-observed now.

(1) c9 alpaca-py. blueprints/us-equities/authenticated-data/native-receipt.json has kind native_cli_e2e and was observed 2026-09-20. The native alpaca-py GET, authentication and URL transport ran StockHistoricalDataClient.get("/stocks/bars") and CorporateActionsClient.get("/corporate-actions"), with result "25bars/3pages;2actions/2pages;5HTTP200;terminalboth" (native_commands, lines 194-203). Two parts are custom repository code, not alpaca-py (implementation_boundary, lines 215-218): the pagination and provenance/validation bridge, and pinned private _session/_retry seams. The comparison at lines 104-130 was produced by the custom comparator authenticated-data/compare.py. It records bars 25/25 equal to the frozen LEAN probe (maximum difference "0.00"). Actions are "reconciliation_incomplete": 2 numeric values equal, 1 equal and 1 unknown_currency. original_historical_availability is "not_established".

(2) c6 EdgarTools. blueprints/us-equities/catalyst-provenance/receipt.json keeps the dated native HTTP 403. blueprints/us-equities/catalyst-provenance/access-resolution.json (native_upstream, lines 31-55) records the contact-corrected native edgartools 5.58.0 get_filings/to_context run: exit 0, HTTP 200, 371 cohort rows, 360 unique accessions, and a hash-verified gzip source of 5079824 bytes. That is native source-identified filing acquisition. The rejection of data with unknown availability comes from the custom provenance adapter catalyst.py, not from EdgarTools (lines 8, 15, 57-117). At as-of 2020-03-03T00:00:00Z it gave eligible_count 0 with before_first_availability 5; at the local observation time it gave eligible_count 5.

(3) c13 exchange_calendars. blueprints/us-equities/data/summarize_backtest.py calls exchange_calendars.get_calendar("XNYS"). blueprints/us-equities/data/receipt.json records XNYS 2013-10-07 open 13:30:00+00:00 and close 20:00:00+00:00. blueprints/us-equities/historical-simulation/receipt.json checked 104 expected sessions with missing_session_dates [] and extra_session_dates [].

Pins: blueprints/us-equities/workers/requirements.txt has alpaca-py==0.44.0 and exchange-calendars==4.13.2, and manifests/stack.json lists exchange-calendars 4.13.2 at source dbe38b1f. Each receipt is bounded native execution on a single sample; no comparative measurement between providers exists.
- data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a — These three adopted candidates are the only ones with retained native execution against the requirement. The requirement is to acquire source-identifiable US-equity observations, keep feed, timestamp, identity and corporate-action data, and reject data whose historical availability is unknown. They cover separate scopes (prices and corporate actions, SEC filings, sessions), so they complement each other. Each fact below is a documented-as-done receipt dated 2026-09-19/20, not re-observed now.

(1) c9 alpaca-py. blueprints/us-equities/authenticated-data/native-receipt.json has kind native_cli_e2e and was observed 2026-09-20. The native alpaca-py GET, authentication and URL transport ran StockHistoricalDataClient.get("/stocks/bars") and CorporateActionsClient.get("/corporate-actions"), with result "25bars/3pages;2actions/2pages;5HTTP200;terminalboth" (native_commands, lines 194-203). Two parts are custom repository code, not alpaca-py (implementation_boundary, lines 215-218): the pagination and provenance/validation bridge, and pinned private _session/_retry seams. The comparison at lines 104-130 was produced by the custom comparator authenticated-data/compare.py. It records bars 25/25 equal to the frozen LEAN probe (maximum difference "0.00"). Actions are "reconciliation_incomplete": 2 numeric values equal, 1 equal and 1 unknown_currency. original_historical_availability is "not_established".

(2) c6 EdgarTools. blueprints/us-equities/catalyst-provenance/receipt.json keeps the dated native HTTP 403. blueprints/us-equities/catalyst-provenance/access-resolution.json (native_upstream, lines 31-55) records the contact-corrected native edgartools 5.58.0 get_filings/to_context run: exit 0, HTTP 200, 371 cohort rows, 360 unique accessions, and a hash-verified gzip source of 5079824 bytes. That is native source-identified filing acquisition. The rejection of data with unknown availability comes from the custom provenance adapter catalyst.py, not from EdgarTools (lines 8, 15, 57-117). At as-of 2020-03-03T00:00:00Z it gave eligible_count 0 with before_first_availability 5; at the local observation time it gave eligible_count 5.

(3) c13 exchange_calendars. blueprints/us-equities/data/summarize_backtest.py calls exchange_calendars.get_calendar("XNYS"). blueprints/us-equities/data/receipt.json records XNYS 2013-10-07 open 13:30:00+00:00 and close 20:00:00+00:00. blueprints/us-equities/historical-simulation/receipt.json checked 104 expected sessions with missing_session_dates [] and extra_session_dates [].

Pins: blueprints/us-equities/workers/requirements.txt has alpaca-py==0.44.0 and exchange-calendars==4.13.2, and manifests/stack.json lists exchange-calendars 4.13.2 at source dbe38b1f. Each receipt is bounded native execution on a single sample; no comparative measurement between providers exists.
- data-exchange-calendars @ 4.13.2; source dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a — These three adopted candidates are the only ones with retained native execution against the requirement. The requirement is to acquire source-identifiable US-equity observations, keep feed, timestamp, identity and corporate-action data, and reject data whose historical availability is unknown. They cover separate scopes (prices and corporate actions, SEC filings, sessions), so they complement each other. Each fact below is a documented-as-done receipt dated 2026-09-19/20, not re-observed now.

(1) c9 alpaca-py. blueprints/us-equities/authenticated-data/native-receipt.json has kind native_cli_e2e and was observed 2026-09-20. The native alpaca-py GET, authentication and URL transport ran StockHistoricalDataClient.get("/stocks/bars") and CorporateActionsClient.get("/corporate-actions"), with result "25bars/3pages;2actions/2pages;5HTTP200;terminalboth" (native_commands, lines 194-203). Two parts are custom repository code, not alpaca-py (implementation_boundary, lines 215-218): the pagination and provenance/validation bridge, and pinned private _session/_retry seams. The comparison at lines 104-130 was produced by the custom comparator authenticated-data/compare.py. It records bars 25/25 equal to the frozen LEAN probe (maximum difference "0.00"). Actions are "reconciliation_incomplete": 2 numeric values equal, 1 equal and 1 unknown_currency. original_historical_availability is "not_established".

(2) c6 EdgarTools. blueprints/us-equities/catalyst-provenance/receipt.json keeps the dated native HTTP 403. blueprints/us-equities/catalyst-provenance/access-resolution.json (native_upstream, lines 31-55) records the contact-corrected native edgartools 5.58.0 get_filings/to_context run: exit 0, HTTP 200, 371 cohort rows, 360 unique accessions, and a hash-verified gzip source of 5079824 bytes. That is native source-identified filing acquisition. The rejection of data with unknown availability comes from the custom provenance adapter catalyst.py, not from EdgarTools (lines 8, 15, 57-117). At as-of 2020-03-03T00:00:00Z it gave eligible_count 0 with before_first_availability 5; at the local observation time it gave eligible_count 5.

(3) c13 exchange_calendars. blueprints/us-equities/data/summarize_backtest.py calls exchange_calendars.get_calendar("XNYS"). blueprints/us-equities/data/receipt.json records XNYS 2013-10-07 open 13:30:00+00:00 and close 20:00:00+00:00. blueprints/us-equities/historical-simulation/receipt.json checked 104 expected sessions with missing_session_dates [] and extra_session_dates [].

Pins: blueprints/us-equities/workers/requirements.txt has alpaca-py==0.44.0 and exchange-calendars==4.13.2, and manifests/stack.json lists exchange-calendars 4.13.2 at source dbe38b1f. Each receipt is bounded native execution on a single sample; no comparative measurement between providers exists.

Alternatives:
- Databento (conditional) — Normalized historical/live data and instrument definitions fit the scope, and a UTC ts_record on corporate actions could address the unknown-availability gap. But the only retained evidence is the pinned README; the packet evidence has no data request, entitlement or local reconciliation receipt. The card records exchange-specific (not consolidated) coverage and limits on redistributing corporate-action data. The repository's comparator (authenticated-data/compare.py) is hard-coded to the Alpaca collector and a 25-session AAPL reference, so no Databento arm could be scored without new code.
- Massive Python client (conditional) — Official SDK (formerly Polygon.io) with ticker inactive/date filters. The only retained evidence is the pinned README; no data request was run. The card notes that the free tier does not grant commercial use or redistribution, and that the filters do not prove a complete historical universe.
- data-feast (conditional) — Point-in-time feature joins are in scope, but the only retained evidence is the pinned README. The card states that event-time retrieval does not exclude late corrections learned after the decision, and that freshness and skew need separate operational evidence. No local run was found.
- data-dlt (conditional) — Ingestion tooling, not a data source; the only retained evidence is the pinned README. The card notes that schema inference is not a financial data-quality contract and that watermark-only extraction can miss late revisions. No local pipeline receipt was found.
- data-gdeltdoc (conditional) — Community (non-official) news client; the last release is 2025-04-03. Per the card, GDELT DOC search has bounded windows, and GDELT first-seen time is not publication or tradable-availability time. That conflicts with the requirement to reject data of unknown historical availability. Evidence is the README only.
- data-fredapi (conditional) — Covers macro/vintage data. The card records that no data request was run and that the latest release is 2024-05-05. A vintage date also does not encode intraday announcement time. Evidence is the README only.
- data-kafka (conditional) — Event-stream infrastructure, not a data source. No local throughput or concurrency measurement justifies adding a server. The card notes that single-node replay is only a smoke check and that ordering is partition-local. Evidence is the README only.
- QuestDB (conditional) — Time-series store with temporal joins. The card says the catalog never installed or started a server, and dedup/upsert can overwrite corrections. No local throughput measurement justifies a server over the observed DuckDB/Parquet path in blueprints/us-equities/data/summarize_backtest.py.
- atilaahmettaner/tradingview-mcp (unqualified) — Not adopted and has no retained evidence. The packet note says it would need documented data rights plus a demonstrated as-of query reconciled against retained Alpaca news timestamps; neither exists.

Overturn when: Change the verdict for the prices/corporate-actions scope, replacing c9 with c14 Databento or c7 Massive, when all of the following hold on the frozen sample in blueprints/us-equities/authenticated-data/plan.json (AAPL, sip/raw 1Day, [2020-08-03, 2020-09-05)):
(a) The challenger arm is scored by a generalized version of blueprints/us-equities/authenticated-data/compare.py. The current script is hard-coded to the Alpaca collector and to AAPL with 25 reference sessions (lines 15-20 and 45-48), so it needs extending first, with its test module tests/test_historical_comparison.py extended alongside it.
(b) The scored arm gives bars 25/25 equal.
(c) The scored arm gives actions status "equal" (2 of 2, including USD currency), where Alpaca left 1 unknown_currency.
(d) Each record carries an auditable historical availability timestamp.
A universe-level overturn, meaning delistings and ticker reuse, first needs a new frozen universe plan, which plan.json's continuation defers.

Regression guards for the custom code the winners rely on are `python3 -m unittest tests.test_historical_comparison tests.test_catalyst_provenance tests.test_alpaca_historical`. The alpaca-py cases need the SDK interpreter: tests/test_alpaca_historical.py:233/237/296/314 call skipTest when the SDK is not installed. A failure invalidates the comparator or adapter logic behind c9's reconciliation and c6's availability gate, not EdgarTools or alpaca-py themselves. These tests run on synthetic/temporary inputs and do not re-validate the retained receipts.

Open gaps:
- No survivorship-free universe. The Alpaca receipt covers one retrospective AAPL sample of 25 daily bars and 2 corporate actions (native-receipt.json limitations, line 221), and plan.json's continuation defers an entitled universe.
- Corporate-action reconciliation is incomplete: dividend currency is missing, so cash units cannot be fully reconciled (native-receipt.json lines 118-130).
- Original historical point-in-time availability is not established for Alpaca bars or corporate actions (native-receipt.json line 107), so the winner set does not meet the requirement's reject-unknown-availability clause for prices and corporate actions.
- The availability gate that rejected all 5 SEC headers at the 2020-03-03 cutoff is custom repository code (catalyst.py), not EdgarTools. The SEC sample covers one day's index (371 rows / 360 unique accessions) and 5 headers, and no historical as-known filing set is established (access-resolution.json lines 8, 13 and 15).
- The c9 native path relies on custom pagination/provenance code and pinned private _session/_retry seams of alpaca-py (native-receipt.json lines 215-218). An SDK upgrade could break those seams.
- No generalized multi-provider comparator exists. compare.py is hard-coded to AAPL, 25 sessions and the Alpaca collector, so a Databento or Massive arm cannot be scored without new code.
- Exchange-calendar native evidence covers the XNYS session 2013-10-07 and a 104-session date check. It does not cover other venues, extended hours, halts or future schedules.
- No receipt I read establishes licensing or redistribution rights for the acquired data.
- News, macro-vintage, point-in-time feature store, stream-ingestion and server-store scope terms have no native evidence among the adopted candidates.
- The selected set provides bounded acquisition and reference capabilities; it does not fully satisfy licensed, historically eligible, reproducible all-equities research.
- Authenticated access does not establish all storage, redistribution, derived-data or real-time entitlements.
- Alpaca acceptance covers one retrospective AAPL sample. Delistings, ticker reuse, permanent security identity, complete corporate actions and an as-known historical universe remain unestablished.
- The dividend's missing currency prevents complete cash-unit reconciliation despite matching numeric values.
- SEC acceptance times and newly observed source bytes do not establish original historical dissemination or observation. The five sampled headers remain ineligible at the historical cutoff.
- Calendar execution establishes one XNYS session, not comprehensive holidays, emergency closures, extended hours or security-specific halts.
- Immutable capture and cutoff rejection depend on project-local adapters. Native SDKs alone do not establish those guarantees, and the Alpaca adapter uses pinned private transport seams.
- No executed provider comparison establishes superiority on representative universe coverage, correction semantics, cost, latency and historical availability.
- unindexed alternative sec-api-io/sec-api-python https://github.com/SEC-API-io/sec-api-python
- unindexed alternative rossod4/quantlab https://github.com/Rossod4/quantlab

Lanes: same_winner (claude: us-equities-market-data-reference-20260922; codex: us-equities-market-data-reference-20260922)

- **Observability and hosting** (observability-hosting): pending — lanes disagreed: claude=loki,opentelemetry-collector-contrib,prometheus; codex=opentelemetry-collector-contrib,restic,sandbox-runtime; the counterbalanced adjudication did not agree (claude 2, codex 2, 0 refuted; evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-observability-hosting-20260922.json); an executed comparison must decide it

#### Portfolio and risk (portfolio-risk)

- skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee — skfolio (c3) is the only adopted candidate in this layer with retained execution evidence in the repository. The evidence is in blueprints/us-equities/research-evaluation/receipt.json: kind "native_cli_e2e" (line 4), observed_utc 2026-09-19T22:59:04Z (line 10) and status "accepted_for_causal_raw_price_label_control_only" (line 11). Lines 12 and 16 record that the installed skfolio 1.2.9 WalkForward ran on chronological session rows with 252/63/6 and reduce_test=True. It produced 20 chronological development folds and one reserved 2021Q1 evaluation, with 21 frozen selections and 6605 retained candidate records. Nine bundled LEAN source hashes stayed unchanged. The reserved block (lines 1383-1447) has test_first 2021-01-04, test_last 2021-03-31, 61 test sessions and 11 observed episodes per candidate, with latest_training_exit 2020-12-24 before evaluation_cutoff 2021-01-04. The audit (lines 1465-1476) records all_training_exits_before_evaluation_cutoff true and prior_scoring_failures 0. Command records show run-1 (evaluate.py) exited 0 with 0-byte stderr (lines 1541-1560). The focused tests returned "12 passed" (lines 1561-1576, run with python3 -q), and the full suite returned "214 passed, 0 skipped" (lines 1577-1590, run under the recorded SDK interpreter). The receipt's independent_review is "accepted", but its scope was read-only and did not re-run scoring. It checked 42 artifact hashes with 0 mismatches, 21 selection hashes and 6605 ledger records, and found no blocking findings. The receipt records a WalkForward source hash and a reviewed upstream revision (lines 32 and 36), but no comparison result. The claim that they match comes only from the README, so it is a documented claim, not an observed check. blueprints/us-equities/research-evaluation/README.md limits the scope. This is a raw-price label study, not portfolio P&L, orders, cash, dividends or new LEAN execution. It "accepts the splitter used here, not every skfolio optimizer." So c3 wins only for the chronological-validation (portfolio-research) part of the layer. Its native_proven class covers WalkForward, not portfolio optimization or risk estimators. Every other adopted candidate has only a packet-cited upstream README as evidence, and this lane did not open those READMEs.

Alternatives:
- cvxportfolio (unqualified) — The packet's only evidence for c1 is an upstream README at pin 1.5.1, packet-cited (evidence_kind source_review) and not opened by this lane. The repository has no installation, execution, fixture or receipt for it; a search found no cvxportfolio recipe under blueprints/ or fixtures/. The packet's card limitations say its prospective workflow is unexecuted and its simulator is not an order gateway. They also warn that its forward-aligned return convention can leak future information if misaligned. It covers the multi-period portfolio-optimization scope term that c3's evidence does not, but that coverage is untested, not failed. It is GPL-3.0, while c3 is BSD-3-Clause.
- empyrical-reloaded (unqualified) — The packet's only evidence for c2 is an upstream README at pin 0.5.12, packet-cited (source_review) and not opened by this lane. No local execution or fixture shows its metric functions on the project's returns. The packet's card limitations say it shares the import name empyrical with the older package and cannot be installed alongside it. They also say its optional pandas-datareader path is incompatible with Python >=3.12. It fits the performance-evaluation and legacy-metrics scope terms, but that capability is untested, not failed.
- quantstats (unqualified) — The packet's only evidence for c4 is an upstream README at v0.0.81, packet-cited (source_review) and not opened by this lane. There is no local execution or fixture. The packet's card limitations say its tear sheets are descriptive only. They do not fix leakage, trial selection, fills or accounting. Its statistics work on return periods, not trades, and its default 252-period convention must be changed for other sampling frequencies. It is a candidate for human-readable performance reports, not a qualified risk or accounting control. It is untested, not failed.

Overturn when: Reopen the choice if any of these checks fails: (a) `python3 -m unittest discover -s tests -p test_research_evaluation.py -q` does not return 12 passed, exactly as recorded in receipt.json lines 1561-1576. (b) The full suite `-m unittest discover -s tests -q`, run under the recorded SDK interpreter, does not return 214 passed, 0 skipped. (c) A fresh run of blueprints/us-equities/research-evaluation/evaluate.py in an environment synced with --require-hashes from blueprints/us-equities/research-evaluation/requirements.lock, with --lean-source and a fresh --out, exits non-zero. It also fails if it does not reproduce plan_sha256 b8d1beba..., 21 selections and 6605 ledger records, or if all_training_exits_before_evaluation_cutoff comes back false. The frozen plan is blueprints/us-equities/research-evaluation/plan.json. (d) A separate sha256 of the installed skfolio/model_selection/_walk_forward.py differs from receipt.json runtime.walkforward_source_sha256 (line 32). evaluate.py does not check this hash itself. Also reopen the choice if a comparable frozen-input native run of cvxportfolio, empyrical-reloaded or quantstats is added under blueprints/us-equities/. It must be preregistered with a leakage and alignment check and carry a receipt for portfolio optimization or performance evaluation. Such a run would widen or change the winner set for the scope terms c3's evidence does not cover.

Open gaps:
- The native evidence for skfolio covers only WalkForward on 3 ETFs (SPY, QQQ, IWM) with raw-price labels. No skfolio optimizer, risk estimator or CPCV path was executed.
- No adopted candidate has retained execution evidence for the portfolio-optimization, performance-evaluation or legacy-metrics scope terms. c1, c2 and c4 are untested, not failed.
- The match between the installed WalkForward source hash (receipt line 32) and the reviewed upstream revision c99fcf71... (line 36) is stated only in README.md. The receipt records no comparison result, and independent_review does not list it among its checks.
- The 42 run artifacts (ledger, selections, stdout/stderr) are private and not in the repository. Only their hashes are retained. The independent review did not re-run scoring.
- The receipt makes no claim about portfolio P&L, total return, dividends, financing, cash, fees or position reconciliation. It uses a fixed 20bp round-trip cost proxy, not fills or liquidity.
- Only 11 completed reserved episodes per candidate. The receipt disclaims any statistical alpha, superiority or promotion claim, and the 2021Q1 segment has now been inspected, so it is no longer untouched.
- No connection is shown between these libraries and the NautilusTrader destination's deterministic numeric risk or broker reconciliation. Optimization and risk estimates are not pre-trade enforcement.
- The packet pins skfolio at 1.2.9 (behind upstream v1.3.0), and the packet's cited README is tagged v1.2.8. The newer release is not natively accepted.
- Native acceptance covers Linux/WSL with Python 3.13.15 only. Other hosts need their own acceptance.
- No matched execution compares the four candidates on common inputs, temporal boundaries and cost assumptions.
- Native skfolio acceptance establishes WalkForward-based raw-price label evaluation, not portfolio optimizer performance or reconciled portfolio P&L.
- The retained study omits dividend-inclusive returns, realistic fills, financing, borrowing, liquidity and capacity; its fixed cost deduction is illustrative.
- No accepted point-in-time equity universe, catalyst strategy, original historical availability or statistical alpha follows from this evidence.
- The inspected 2021Q1 segment cannot become an untouched holdout through reuse.
- Broker-specific execution, deterministic pre-trade enforcement and Nautilus/LEAN accounting parity require separate acceptance.

Lanes: same_winner (claude: us-equities-portfolio-risk-20260922; codex: us-equities-portfolio-risk-20260922)

#### Research, factors and ML (research-factors-ml)

- skfolio @ 1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee — These are the only adopted candidates whose own upstream code was run natively on work in this layer's scope (research-validation, model-selection, time-series-evaluation, financial-nlp, document-ingestion). The receipts show which parts are native and which are local integration.

c23 skfolio. Native part: blueprints/us-equities/research-evaluation/receipt.json (kind native_cli_e2e) records the installed upstream WalkForward called with 252/63/6 and reduce_test=True. Command run-1 (lines 1541-1560) ran `$WAVE_DIR/venv/bin/python blueprints/us-equities/research-evaluation/evaluate.py --lean-source ... --out ...` with exit 0. That interpreter came from a venv synced with `--require-hashes` from requirements.lock (lines 1505-1517), with skfolio 1.2.9 and scikit-learn 1.9.1. On SPY/QQQ/IWM sessions it produced 20 chronological development folds, 1 reserved 2021Q1 evaluation, 21 frozen selections and 6605 candidate records.

c23 local-integration part: the chronology audit comes from the project's evaluate.py wrapper, not from skfolio. The audit block (lines 1465-1476) reports 5290 training records, 1300 evaluation records and 15 censored records. Both all_observed_decision_before_entry_before_exit and all_training_exits_before_evaluation_cutoff are true. The 12 focused tests (lines 1561-1576) ran under system python3 against evaluate.py helper functions on synthetic 2018 data (tests/test_research_evaluation.py:10,27-29). They do not run WalkForward or read plan.json, which only main() does (evaluate.py:175,181,189,210). The receipt shows no edge. The reserved-period choice, momentum20, had mean_net_cost_proxy_label 0.001184071666615635470939591764, below equalweight (0.001622928696130345656850000132) and momentum120 (0.004403128517506842397527919636). This is a raw-price label control, not P&L.

c11 EdgarTools. Native parts:
- blueprints/us-equities/catalyst-provenance/receipt.json records EdgarTools 5.58.0 installed with 42 packages (lines 25-27).
- Its offline index run `native_edgar.py --fixture blueprints/us-equities/catalyst-provenance/fixture.idx` exited 0 (line 42), and native_document.py exited 0 (line 47). The document parse gave 5325 markdown bytes from a pinned upstream 8-K, which stayed quarantined.
- The first network runs exited 1, and the later metadata request returned 403.
- access-resolution.json native_upstream (lines 31-56) records `edgar.get_filings(2020,1,form='8-K',amendments=True,filing_date='2020-03-02')` with exit 0 and HTTP 200: 371 cohort rows, 360 unique accessions (8-K 362, 8-K/A 9) and 5 selected context rows.

c11 local-integration part (correcting the earlier draft): the five-header acquisition and the temporal gate came from the separate custom catalyst.py adapter, not from EdgarTools (access-resolution.json lines 8, 15, 57-112). `catalyst.py packet --as-of 2020-03-03T00:00:00Z` gave eligible_count 0 with before_first_availability 5. At the local observation time it gave eligible_count 5. The 13 unittest cases in tests/test_catalyst_provenance.py exercise catalyst.py on inline synthetic bytes (lines 9, 21-25), not fixture.idx.

Evidence class: I report native_proven because each winner's upstream library has retained native execution. Its causal properties, however, rest on local integration code. Neither winner is a measured comparison against the alternatives.

Provenance: this verdict is my own source review. No provider or TypeSafe inference judgment was supplied or used, and the two refuter reports were treated as claims that I re-checked against the cited lines.
- data-edgartools @ v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a — These are the only adopted candidates whose own upstream code was run natively on work in this layer's scope (research-validation, model-selection, time-series-evaluation, financial-nlp, document-ingestion). The receipts show which parts are native and which are local integration.

c23 skfolio. Native part: blueprints/us-equities/research-evaluation/receipt.json (kind native_cli_e2e) records the installed upstream WalkForward called with 252/63/6 and reduce_test=True. Command run-1 (lines 1541-1560) ran `$WAVE_DIR/venv/bin/python blueprints/us-equities/research-evaluation/evaluate.py --lean-source ... --out ...` with exit 0. That interpreter came from a venv synced with `--require-hashes` from requirements.lock (lines 1505-1517), with skfolio 1.2.9 and scikit-learn 1.9.1. On SPY/QQQ/IWM sessions it produced 20 chronological development folds, 1 reserved 2021Q1 evaluation, 21 frozen selections and 6605 candidate records.

c23 local-integration part: the chronology audit comes from the project's evaluate.py wrapper, not from skfolio. The audit block (lines 1465-1476) reports 5290 training records, 1300 evaluation records and 15 censored records. Both all_observed_decision_before_entry_before_exit and all_training_exits_before_evaluation_cutoff are true. The 12 focused tests (lines 1561-1576) ran under system python3 against evaluate.py helper functions on synthetic 2018 data (tests/test_research_evaluation.py:10,27-29). They do not run WalkForward or read plan.json, which only main() does (evaluate.py:175,181,189,210). The receipt shows no edge. The reserved-period choice, momentum20, had mean_net_cost_proxy_label 0.001184071666615635470939591764, below equalweight (0.001622928696130345656850000132) and momentum120 (0.004403128517506842397527919636). This is a raw-price label control, not P&L.

c11 EdgarTools. Native parts:
- blueprints/us-equities/catalyst-provenance/receipt.json records EdgarTools 5.58.0 installed with 42 packages (lines 25-27).
- Its offline index run `native_edgar.py --fixture blueprints/us-equities/catalyst-provenance/fixture.idx` exited 0 (line 42), and native_document.py exited 0 (line 47). The document parse gave 5325 markdown bytes from a pinned upstream 8-K, which stayed quarantined.
- The first network runs exited 1, and the later metadata request returned 403.
- access-resolution.json native_upstream (lines 31-56) records `edgar.get_filings(2020,1,form='8-K',amendments=True,filing_date='2020-03-02')` with exit 0 and HTTP 200: 371 cohort rows, 360 unique accessions (8-K 362, 8-K/A 9) and 5 selected context rows.

c11 local-integration part (correcting the earlier draft): the five-header acquisition and the temporal gate came from the separate custom catalyst.py adapter, not from EdgarTools (access-resolution.json lines 8, 15, 57-112). `catalyst.py packet --as-of 2020-03-03T00:00:00Z` gave eligible_count 0 with before_first_availability 5. At the local observation time it gave eligible_count 5. The 13 unittest cases in tests/test_catalyst_provenance.py exercise catalyst.py on inline synthetic bytes (lines 9, 21-25), not fixture.idx.

Evidence class: I report native_proven because each winner's upstream library has retained native execution. Its causal properties, however, rest on local integration code. Neither winner is a measured comparison against the alternatives.

Provenance: this verdict is my own source review. No provider or TypeSafe inference judgment was supplied or used, and the two refuter reports were treated as claims that I re-checked against the cited lines.

Alternatives:
- foundation-qmd (conditional) — Native Claude workflow ran a BM25 search over agent-lab docs (native-cli-gaps.json: result docs/native-rag-runtime.md, score 0.86, BM25 mode). It covers retrieval of project documents only: there is no financial corpus and the semantic models are not downloaded. component-history.json still records native_claude as 'not independently demonstrated' for qmd, which is a dated inconsistency with native-cli-gaps.json.
- data-arcticdb (unqualified) — Corrected from out_of_scope. The packet also tags data-research entries into this layer (packet limitations line 827), so a storage component is not excluded on scope alone. The evidence is a source-review README only, which this lane could not open, and no research-scope execution was retained. The BSL-1.1 licence caveat remains, as does the gap between storage version time and information-availability time.
- data-sktime (unqualified) — Its temporal splits and baselines overlap the natively executed skfolio WalkForward. The only evidence is a source-review README, which this lane did not open, and no execution was retained.
- alphalens-reloaded (unqualified) — It is the most directly on-scope factor IC and turnover diagnostic, but its prospective workflow is unexecuted. The evidence is a source-review README only, not opened here. PyPI (0.4.6) and GitHub (0.4.5) versions differ, and IC omits borrow and execution costs.
- chronos (unqualified) — No inference, GPU or hosted check was performed; the evidence is a source-review README only. Generic forecasting benchmarks do not establish US-equity alpha.
- data-tsfresh (unqualified) — Feature extraction has source-review evidence only and no fold-local execution. No retained run addresses its leakage or multiple-testing risk.
- deerflow (conditional) — Native discovery returned health 200 with 23 upstream skills and 0 configured models, and one embedded ACP prompt completed (research-receipt.json: status completed, native_turn_duration_ms 31027). That prompt only read two receipts and returned counts; no factor or ML work was done. The planner, UI and service were not accepted, and ACP read-only mode maps to workspaceWrite.
- vllm (conditional) — vLLM is a model-serving runtime, which is a scope term here, not a research method. Upstream 0.29.0 failed GPU startup on this WSL host with 'RuntimeError: UVA is not available', and 0.25.0 was restored (vllm-compatibility.json). The packet lists upstream at v0.30.0. No research-model inference or serving benchmark exists for this layer.
- foundation-haystack (unqualified) — The evidence is source review only, with no financial-corpus pipeline and no proof of performance.
- data-river (unqualified) — The evidence is source review only. Progressive validation with delayed financial labels was not executed.
- data-statsforecast (unqualified) — The evidence is source review only. The bundled airline dataset is a method demo, and no financial rolling evaluation was retained.
- foundation-docling (unqualified) — The evidence is source review only. Table and unit extraction quality is unmeasured, and the model weights carry separate licences. For filings, the natively executed EdgarTools document parser already covers ingestion.
- arch (unqualified) — Its volatility, bootstrap, SPA and MCS tools have source review only, and the prospective workflow is unexecuted. They would address the multiple-comparison gap, but no run exists.
- ray-serve (unqualified) — The evidence is source review only. No distributed performance or failover acceptance was done, and no research workload here needs it.
- timesfm (unqualified) — The evidence is source review only, with a synthetic API example. The TimesFM 3.0 weights are non-commercial, and there is no finance benchmark.
- foundation-markitdown (overlap) — Native evidence is limited to converting a local HTML fixture (portable-cli-artifacts.json: markitdown fixtures/greeting.html, exit 0) and one worker conversion from 389920 to 26322 bytes (component-history.json). PDF and Office extras are not proven. The pin 0.1.7 is behind upstream 0.1.8, and filing HTML-to-Markdown conversion overlaps the natively executed EdgarTools document parser.
- statsmodels (unqualified) — The evidence is source review only, and the prospective workflow is unexecuted.
- foundation-sentence-transformers (unqualified) — The evidence is source review only. Neither compatibility with the active vLLM service nor a financial embedding workload is established.
- scikit-learn (overlap) — scikit-learn 1.9.1 is in the hash-locked runtime of the native skfolio run (research-evaluation/receipt.json, runtime block around line 1461), but only as a dependency. Its own predictive-baseline and fold-local preprocessing workflow was not exercised, and its card evidence is a README only.
- Qlib (unqualified) — The evidence is source review only. The bundled workflow is China CSI300 with China-style costs, upstream data availability is unverified, and the prospective workflow is unexecuted.

Overturn when: Revisit this verdict in any of the following cases. Checks (1) and (2) re-run the evidence behind the winners. Checks (3) and (4) are comparisons against alternatives.

(1) skfolio chronology. In a venv synced with `--require-hashes blueprints/us-equities/research-evaluation/requirements.lock`, re-run `python3 blueprints/us-equities/research-evaluation/evaluate.py --lean-source <LEAN source> --out <new dir>`, using that venv's python3 as receipt command run-1 does. The verdict changes if the command fails, if the plan_sha256 recorded in results.json does not match blueprints/us-equities/research-evaluation/plan.json, or if the audit reports all_training_exits_before_evaluation_cutoff or all_observed_decision_before_entry_before_exit as false.

`python3 -m unittest discover -s tests -p test_research_evaluation.py -q` exercises only evaluate.py helper functions on synthetic data. A failure there invalidates the local integration code, not the WalkForward result.

(2) EdgarTools. In the edgartools==5.58.0 environment (blueprints/us-equities/catalyst-provenance/requirements.lock), `python3 blueprints/us-equities/catalyst-provenance/native_edgar.py --fixture blueprints/us-equities/catalyst-provenance/fixture.idx --out <path>` fails. For the custom temporal gate, `python3 blueprints/us-equities/catalyst-provenance/catalyst.py packet --run <acquisition run> --as-of 2020-03-03T00:00:00Z --out <path>` returns eligible_count above 0 for headers first observed later. That second check is local integration; `python3 -m unittest tests.test_catalyst_provenance` covers only catalyst.py on inline synthetic bytes.

(3) An adopted source-review candidate beats the winners when executed on the same frozen plan.json, inputs and 20bp round-trip cost-proxy contract. The most likely are alphalens-reloaded IC/turnover, arch SPA/MCS on the same candidate ledger, and the sktime temporal splitter.

(4) A forecaster such as non-adopted Kronos beats the C0 all-eligible control, net of 5/10/20 bps per side, under the separate broad-universe protocol (blueprints/us-equities/broad-universe/protocol.json; development 2017-2021, validation 2022-2023, reserved 2024-01-01..2026-08-14). That is the bar the five predeclared signals failed.

Open gaps:
- The skfolio receipt covers a selected ETF sample (SPY, QQQ, IWM), not a point-in-time equity universe. Labels are raw-price, not total-return, and each candidate has only 11 complete reserved episodes. It records no alpha, P&L, fill, dividend or cash reconciliation, and no new LEAN or Nautilus engine execution.
- WalkForward purge and embargo default to zero (packet card limitation). The 6-row gap plus the interval assertions does not establish independent samples, and development labels can cross fold boundaries.
- The chronology audit fields and the catalyst temporal gate are produced by project-local wrappers (evaluate.py, catalyst.py), not by the upstream libraries. The upstream native part is the WalkForward split, the get_filings index acquisition and document parsing.
- The EdgarTools acquisition is a bounded 5-header sample from one day (2020-03-02). It does not establish a historical as-known filing corpus, dissemination lag or a catalyst strategy.
- A retained broad-universe chronological study is layer-relevant research validation but credits no layer candidate. evidence/receipts/broad-universe-research-20260921.json lists component_ids alpaca-py, duckdb, claude-code and codex; its README 'Result: no signal is established' says all 15 signal x horizon promotion checks returned not_established, with no Bonferroni interval above zero. Together with the skfolio control, it means no in-scope signal has been established.
- None of the factor IC, forecasting, feature-extraction, online-learning, econometrics, volatility or RAG candidates (c2, c3, c4, c5, c6, c9, c10, c12, c14, c15, c17, c18, c20, c21, c24) has a retained execution. Untested is not failed.
- No measured comparison between any two candidates in this layer exists. The winner set reflects evidence strength, not a demonstrated performance ranking.
- Non-adopted c13 (tradermonty/claude-trading-skills) and c16 (shiyu-coder/Kronos) have no evidence_refs in the packet. The c16 note (packet line 486) is a hypothetical overturn condition, not a result, so challenger_preferred stays null.
- The packet card for c23 cites the skfolio README at v1.2.8, while the executed pin is 1.2.9 and upstream latest is v1.3.0 (pin_behind_upstream true).
- No winner establishes a complete factor/ML pipeline through NautilusTrader, broker-specific execution, deterministic risk enforcement and independently reconciled accounting.
- Skfolio acceptance covers chronological splitting in a project-local raw-price label study. It excludes dividend-inclusive returns, financing, realistic fills, capacity and portfolio cash reconciliation.
- The reserved 2021Q1 segment has been inspected and cannot become a fresh untouched holdout. The selected momentum20 diagnostic was below equalweight on the reported reserved mean net cost-proxy label.
- EdgarTools acquisition and parsing do not establish original historical information availability, complete filing narratives, a point-in-time security universe or predictive catalyst quality.
- No retained comparison establishes superiority among the forecasting, feature-extraction, econometric or financial-NLP alternatives.
- The non-adopted candidates c13 and c16 have no evidence_refs. Their packet notes do not establish an executed defect-finding or forecast-superiority comparison.
- The broad-universe protocol records historical availability, identity and survivorship assumptions. Its reserved period must not be reused as untouched for a newly designed challenger.

Lanes: same_winner (claude: us-equities-research-factors-ml-20260922; codex: us-equities-research-factors-ml-20260922)

#### Security and supply chain (security-supply-chain)

- grype @ v0.119.0 — Per the packet's requirement_note, I judged fit against the layer title "Security and supply chain" and the scope terms security, sbom, secrets and vulnerability-analysis, not against the shared agents-operations requirement text. Only three adopted candidates have retained native-execution evidence under the repository root. The other two have only upstream README references.

(1) c2 grype and (2) c4 syft. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (evidence_class native_proven, status passed_scoped_scan_zero_findings, observed 2026-09-22T07:43:37Z) records these native runs:
- Syft 1.52.0 made two SBOMs: the NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages).
- Grype 0.119.0 ran against a database with schema v6.1.9, built 2026-09-22T06:30:41Z. It returned runtime_grype_matches 0, adapter_grype_matches 0 and total_matches 0.
- All six recorded commands exited 0.
- The Grype archive matched the publisher checksum and the GitHub asset digest. signature_verified is false.

blueprints/us-equities/supply-chain/receipt.json (native_cli_e2e, observed 2026-09-19) records a Syft 1.52.0 scan of the equity-worker-sdk directory:
- It ran inside a read-only, network-isolated bubblewrap namespace and exited 0.
- It found 36 Python packages. All 36 agree between the Syft JSON and CycloneDX 1.7 outputs and with the installed dist-info metadata.
- License metadata was present for 34/36 packages and an SPDX expression for 31/36.
- The source fingerprint was identical before and after.

Together these cover the sbom and vulnerability-analysis terms.

(3) c3 gitleaks. evidence/receipts/runtime-tools.json (native_cli_e2e, recorded 2026-09-19T04:55:03Z) records a native history scan: exit_code 0, commits_scanned 22, bytes_scanned 1174704 (approximate), findings 0, redaction 100 percent. The pinned command is at recipes/README.md line 93. This covers the secrets-detection term.

These are native executions of the tools as recorded in retained receipts. I did not re-run them. None is a measured comparison against the non-winners. winner_evidence_class is native_proven because all three winners share it. I did not use TypeSafe inference: the coordinator supplied no results. This verdict is my own source review of the receipts.
- syft @ v1.52.0 — Per the packet's requirement_note, I judged fit against the layer title "Security and supply chain" and the scope terms security, sbom, secrets and vulnerability-analysis, not against the shared agents-operations requirement text. Only three adopted candidates have retained native-execution evidence under the repository root. The other two have only upstream README references.

(1) c2 grype and (2) c4 syft. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (evidence_class native_proven, status passed_scoped_scan_zero_findings, observed 2026-09-22T07:43:37Z) records these native runs:
- Syft 1.52.0 made two SBOMs: the NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages).
- Grype 0.119.0 ran against a database with schema v6.1.9, built 2026-09-22T06:30:41Z. It returned runtime_grype_matches 0, adapter_grype_matches 0 and total_matches 0.
- All six recorded commands exited 0.
- The Grype archive matched the publisher checksum and the GitHub asset digest. signature_verified is false.

blueprints/us-equities/supply-chain/receipt.json (native_cli_e2e, observed 2026-09-19) records a Syft 1.52.0 scan of the equity-worker-sdk directory:
- It ran inside a read-only, network-isolated bubblewrap namespace and exited 0.
- It found 36 Python packages. All 36 agree between the Syft JSON and CycloneDX 1.7 outputs and with the installed dist-info metadata.
- License metadata was present for 34/36 packages and an SPDX expression for 31/36.
- The source fingerprint was identical before and after.

Together these cover the sbom and vulnerability-analysis terms.

(3) c3 gitleaks. evidence/receipts/runtime-tools.json (native_cli_e2e, recorded 2026-09-19T04:55:03Z) records a native history scan: exit_code 0, commits_scanned 22, bytes_scanned 1174704 (approximate), findings 0, redaction 100 percent. The pinned command is at recipes/README.md line 93. This covers the secrets-detection term.

These are native executions of the tools as recorded in retained receipts. I did not re-run them. None is a measured comparison against the non-winners. winner_evidence_class is native_proven because all three winners share it. I did not use TypeSafe inference: the coordinator supplied no results. This verdict is my own source review of the receipts.
- gitleaks @ v8.30.1 — Per the packet's requirement_note, I judged fit against the layer title "Security and supply chain" and the scope terms security, sbom, secrets and vulnerability-analysis, not against the shared agents-operations requirement text. Only three adopted candidates have retained native-execution evidence under the repository root. The other two have only upstream README references.

(1) c2 grype and (2) c4 syft. blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json (evidence_class native_proven, status passed_scoped_scan_zero_findings, observed 2026-09-22T07:43:37Z) records these native runs:
- Syft 1.52.0 made two SBOMs: the NautilusTrader 2.0.0rc5 runtime site-packages (21 packages) and the adaptive-paper requirements.txt pins (2 packages).
- Grype 0.119.0 ran against a database with schema v6.1.9, built 2026-09-22T06:30:41Z. It returned runtime_grype_matches 0, adapter_grype_matches 0 and total_matches 0.
- All six recorded commands exited 0.
- The Grype archive matched the publisher checksum and the GitHub asset digest. signature_verified is false.

blueprints/us-equities/supply-chain/receipt.json (native_cli_e2e, observed 2026-09-19) records a Syft 1.52.0 scan of the equity-worker-sdk directory:
- It ran inside a read-only, network-isolated bubblewrap namespace and exited 0.
- It found 36 Python packages. All 36 agree between the Syft JSON and CycloneDX 1.7 outputs and with the installed dist-info metadata.
- License metadata was present for 34/36 packages and an SPDX expression for 31/36.
- The source fingerprint was identical before and after.

Together these cover the sbom and vulnerability-analysis terms.

(3) c3 gitleaks. evidence/receipts/runtime-tools.json (native_cli_e2e, recorded 2026-09-19T04:55:03Z) records a native history scan: exit_code 0, commits_scanned 22, bytes_scanned 1174704 (approximate), findings 0, redaction 100 percent. The pinned command is at recipes/README.md line 93. This covers the secrets-detection term.

These are native executions of the tools as recorded in retained receipts. I did not re-run them. None is a measured comparison against the non-winners. winner_evidence_class is native_proven because all three winners share it. I did not use TypeSafe inference: the coordinator supplied no results. This verdict is my own source review of the receipts.

Alternatives:
- openbao (unqualified) — The only evidence is the pinned upstream README (source_review, v2.6.2), which I could not open from this lane. The packet's card limitations say no server config is supplied and no service was started. No retained receipt shows a native OpenBao secret-lifecycle or service-identity run. It is untested, not failed. It covers the secrets-lifecycle part of the layer, which the winners do not cover (gitleaks detects secrets but does not manage them), but no native evidence qualifies it yet.
- cosign (conditional) — The only evidence is the pinned upstream README (source_review, v3.1.3), which I did not open. The packet's card limitations say no signing or identity-verification flow was started. Both winner receipts record signature_verified false for the Syft and Grype release archives, so artifact signature and identity verification is a real gap that cosign would fill. Its value depends on a native verification run against an upstream that publishes signatures. That run is not recorded. It is untested, not failed.

Overturn when: Change the verdict if any of these happens.
1. `python3 -m unittest tests.test_supply_chain_scan` fails against blueprints/us-equities/supply-chain/scan-nautilus-rc5-20260922/receipt.json. Examples: a nonzero exit code, a finding count that does not match the disposition table, or a raw-artifact byte/hash mismatch.
2. A re-scan with a later Grype database or dependency set records matches with a needs_review disposition.
3. `python3 -m unittest tests.test_gitleaks_config` shows the gitleaks config missing synthetic secret fixtures.
4. A new receipt records a native cosign verification of the Syft/Grype release artifacts (signature_verified true, exact identity), or a native OpenBao secret-lifecycle run. Such a receipt would add cosign or OpenBao to the winner set or replace a winner.

Open gaps:
- The Grype scan target is not the Syft-inventoried SDK. blueprints/us-equities/supply-chain/README.md line 141 says the Grype run 'closes the previously missing vulnerability scan of the SDK inventoried above', but the 2026-09-22 receipt scanned a different target: the NautilusTrader rc5 runtime venv (21 packages), not the 36-package equity-worker-sdk. For example, openai 3.16.2, openai-codex 0.154.0 and exchange-calendars 4.13.2 appear only in the 36-package inventory. The 36-package SDK has no recorded vulnerability scan.
- The syft card limitation 'vulnerability scanning were not performed' is still accurate for the 2026-09-19 inventory. It does not describe the 2026-09-22 Grype receipt, which covers a different target.
- Signature and provenance verification is missing for every installed supply-chain tool: signature_verified is false in both receipts. Only checksums were matched.
- The Syft and Grype scans cover Python package metadata only. They do not cover bundled Rust/Cython or native shared libraries, host OS packages, IBKR-side software, or code outside the scanned venv.
- Zero Grype matches holds only for the database built 2026-09-22T06:30:41Z. It says nothing about later disclosures or runtime safety.
- The gitleaks evidence is dated 2026-09-19 and covers 22 commits with approximate byte counts. It is not current coverage of later history and does not certify that no secrets exist.
- Secret lifecycle and service identity have no native evidence. No winner manages or scopes the broker credential environment variables. OpenBao is untested, not failed.
- No measured comparison exists between the winners and any alternative scanner or SBOM tool. The winners rest on native execution only.
- The requirement text is shared across the agents-operations group (research workers, supervision, telemetry). None of these tools establishes that research workers lack broker execution authority.
- Python metadata inventory excludes complete bundled native-library, host OS, external interpreter, and broker-side coverage.
- The September 22 Grype scan covers the 21-package Nautilus runtime and two declared adapter pins. It does not establish vulnerability coverage of the separate 36-package SDK inventoried on September 19, despite the broader wording in the supply-chain README.
- Zero vulnerability matches against the recorded database do not establish runtime safety, unpublished-vulnerability absence, or future database results.
- The retained Gitleaks receipt covers 22 commits; it does not establish current full-history cleanliness or detection of every secret type.
- Checksum matching does not establish artifact signer identity or build provenance; native Cosign verification remains unestablished.
- Secret issuance, rotation, revocation, and denial of broker execution authority to research workers remain unestablished by these candidates' receipts.
- The selected tools do not establish the group's process supervision, telemetry completeness, or recoverable-state requirements.

Lanes: same_winner (claude: us-equities-security-supply-chain-20260922; codex: us-equities-security-supply-chain-20260922)

#### Storage and compute (storage-compute)

- data-duckdb @ v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa — DuckDB (c4) is the only adopted candidate in the storage/compute role with retained local execution evidence. TOON (c10) also has a native_proven receipt, but it covers model-context serialization only (evidence/receipts/portable-cli-artifacts.json: toon_roundtrip_equal true). The other adopted store and compute candidates have only an upstream README reference. What the retained receipts show (they record past runs; I could not re-run anything now):

(1) blueprints/us-equities/data/receipt.json (kind native_cli_e2e, recorded_date 2026-09-19) records a run of blueprints/us-equities/data/summarize_backtest.py. The script uses DuckDB to read LEAN order-event JSON and casts fill price and quantity to DECIMAL(20, 8) (lines 20-24). It writes zstd Parquet (line 25) and refuses to overwrite an existing output (lines 17-18). It then rereads the Parquet and counts rows, distinct orders and statuses (lines 26-28): 6 events, 3 distinct orders, filled 3 and submitted 3. The receipt records source_sha256 8e22c0052e1e769708114064cba69c3ddaec2c5af8148a6cf171e0f296f192de and parquet_sha256 48ec550a96771e284bde09f6793b0d064e47bf3a731d8a1ac389a509b616f66d. The sample session 2013-10-07 is not read from the data: it is hard-coded (line 30), and only its XNYS open and close times come from exchange_calendars.

(2) blueprints/us-equities/research-runtime/receipt.json records a Dagu workflow that reported the same parquet_sha256.

(3) blueprints/us-equities/financial-data/receipt.json records duckdb_version 1.5.5. Its research_environment_suite reports 84 tests, 0 failures and 0 skips; its base_python_suite reports 2 skips because DuckDB is installed only in the research environment. It also records exact DECIMAL(38,12) values surviving a Parquet round trip, but those use artificial fixtures only. The live SEC acquisition failed with http_403 (parquet_datasets 0).

(4) blueprints/us-equities/workers/requirements.txt pins duckdb==1.5.5, matching the packet pin v1.5.5.

This fits the layer terms columnar-compute, parquet and local-store for exact, hash-identified local snapshots. It does not establish licensed acquisition, historical-availability rejection or market-data ingestion. The evidence class native_proven matches the packet's deterministic evidence_kind. The run itself is a project-local script over a bundled LEAN simulation output, not upstream DuckDB tests.

Alternatives:
- data-dlt (unqualified) — The only evidence is a reference to the upstream README. This lane did not open it because it has no network tool. No local pipeline run, DuckDB-destination load or late-revision handling is retained. The card says watermark-only extraction can miss late revisions.
- data-iceberg (conditional) — The only evidence is the upstream README, which I did not open. No catalog, append, multi-writer, cross-engine or time-travel check is retained, and the card says catalog creation alone would not prove these. The group overturn text allows a lake only after local throughput or concurrency measurements justify it. None exist.
- ray-serve (conditional) — Distributed compute is in scope, but no retained evidence shows a workload that needs it. No distributed performance or failover acceptance was performed (card limitation). The only evidence is the README, which I did not open.
- QuestDB (conditional) — No server was installed or started (card limitation). No ingestion, temporal-join or throughput measurement is retained. Dedup/upsert can overwrite corrections, which conflicts with an immutable revision ledger unless a raw ledger is kept first. The only evidence is the README, which I did not open.
- ClickHouse (conditional) — The local SQL command is only prospective. No server, cluster, throughput or reliability evidence exists (card limitation). The pin v26.8.7.19-lts is behind upstream v26.9.2.8-stable (packet pin_behind_upstream true). Background merges are not an immutable ledger. The only evidence is the README, which I did not open.
- data-arrow (overlap) — Arrow is an interchange and Parquet IO library, not a store (card limitation). DuckDB already did the retained Parquet write and reread. pyarrow 25.0.1 appears only as a dependency version in the promotion-gate outputs. No Arrow-specific precision round-trip check is cited for this component. The packet evidence is only the README, which I did not open.
- Pandera (conditional) — Pandera fits the schema-contracts term and complements DuckDB, but it is a validation gate, not a store or compute engine. Correction to my earlier proposal: the repository does retain gate outputs, although they are not among the packet's evidence_refs for c8. blueprints/us-equities/data/fixtures/good-gate-result.json shows status pass on row_count 4, run with pandera 0.33.1, pandas 3.0.6 and pyarrow 25.0.1, checked_at 2026-09-22T15:12:36.425193+00:00. fixtures/bad-gate-result.json shows status fail; the failing checks are valid_trading_session, volume_integral_non_negative, observed_at_not_future, high_ge_max_open_close and unique_symbol_session. Three more *-gate-result.json files exist: empty-snapshot, fractional-negative-volume and null-price-cell. So fail-closed rejection is shown, but only on synthetic 4-row CSV fixtures. blueprints/us-equities/data/README.md lines 119-124 says the repository has no production bars/universe ingest that produces a real snapshot yet. The remaining gap is a gate run on a real snapshot, not the absence of a receipt. The card's statement that fail-closed promotion is 'still implementation work' is stale for the gate script itself.
- foundation-toon (out_of_scope) — TOON is compact serialization for model context, not analytical storage or compute. Its native evidence is one CLI encode/decode fixture round trip (toon_roundtrip_equal true in evidence/receipts/portable-cli-artifacts.json). component-history.json says native_claude and native_codex are 'not independently demonstrated' and that a nested fixture grew from 69 to 94 tokens. It does not address snapshot reproducibility or availability rejection.
- data-feast (unqualified) — The only evidence is the README, which I did not open. No feature retrieval run is retained. The card says event-time point-in-time retrieval does not exclude late corrections, and that freshness and skew need separate operational evidence.
- bytebase/dbhub (unqualified) — Not adopted, with no evidence_refs and no pin. The packet note makes it conditional on three things: a curated research database, a demonstrated read-only principal, and bounded max_rows enforcement. None of these is evidenced. The note also shows it is an MCP access bridge, not a store.

Overturn when: Three checks could change the verdict.

1. Re-run blueprints/us-equities/data/summarize_backtest.py with pinned duckdb==1.5.5 on a LEAN order-events file whose sha256 equals the recorded source_sha256 8e22c0052e1e769708114064cba69c3ddaec2c5af8148a6cf171e0f296f192de, writing to a new Parquet path. That input is external to the repository: it lives under the LEAN build output named in the receipt command. The verdict changes if the re-run fails to reproduce 6 events, 3 distinct orders and parquet_sha256 48ec550a96771e284bde09f6793b0d064e47bf3a731d8a1ac389a509b616f66d. If no matching source file is available, the result is inconclusive, not a failure.

2. Run tests/test_financial_data.py under the pinned research-environment interpreter (the financial-data receipt runs it as the research Python with -m unittest tests.test_financial_data), not a base python3. The verdict changes if the DECIMAL(38,12) Parquet round-trip tests at lines 229 and 246 fail. A run that reports any skip does not exercise them and does not count.

3. Any store candidate (c2, c5 or c6) replaces or joins DuckDB only after an executed comparison on the same fixture and snapshot contract. It must show that DuckDB's local throughput or concurrency is insufficient and that the candidate preserves exact decimals and immutable snapshots. No such comparison exists.

Separately, Pandera (c8) would join the winner set if two conditions hold. First, tests/test_promotion_gate.py runs with the gate's isolated venv present (PROMOTION_GATE_PYTHON or the documented venv) and reports 0 skips in its fixture-run tests. Second, a retained blueprints/us-equities/data/promotion_gate.py result on a real, non-fixture snapshot shows fail-closed rejection.

Open gaps:
- DuckDB's retained runs cover a bundled LEAN historical simulation (6 order events) and artificial SEC-shaped fixtures. Neither is licensed US-equity market-data ingestion.
- The live SEC acquisition failed with http_403 (financial-data receipt: parquet_datasets 0, source_payloads 0, ready_financial_packets 0). No live DuckDB/Parquet financial dataset exists in the evidence I read.
- No evidence I read shows the store rejecting data whose historical availability or eligibility is unknown. The financial-data receipt records historical_point_in_time_reconstruction false.
- No throughput, concurrency or multi-writer measurement exists for DuckDB or any server or lake alternative (QuestDB, ClickHouse, Iceberg).
- The Pandera promotion gate has retained fail-closed outputs only on synthetic 4-row CSV fixtures, run on 2026-09-22. According to blueprints/us-equities/data/README.md lines 119-124, no production bars/universe ingest produces a real snapshot yet.
- The hash-reproduction check depends on an external LEAN order-events file (receipt command under the LEAN source build). It is not in the repository.
- The research-runtime receipt says the paired Astra-to-Claude workflow was not executed (paired_model_workflow_executed false).
- No candidate establishes the complete shared acquisition, licensing, identity and historical-eligibility requirement.
- DuckDB native evidence covers bundled simulation events; financial availability, amendment and decimal-boundary checks use artificial fixtures.
- The referenced SEC attempt failed with HTTP 403 and produced no live source payload or Parquet dataset; later acquisition results mentioned in the packet were not independently inspected.
- No retained comparison measures representative data volumes, concurrent writers/readers, latency, recovery or operational cost across storage candidates.
- Immutable-file guards, hashes and exact decimals do not establish original historical publication, complete corporate actions or survivorship-free universes.

Lanes: same_winner (claude: us-equities-storage-compute-20260922; codex: us-equities-storage-compute-20260922)
<!-- verdicts:end -->
