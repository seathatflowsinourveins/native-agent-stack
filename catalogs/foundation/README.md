# FOUNDATION capability catalog

FOUNDATION selects the general native workflow: clients, skills, owned workers,
source retrieval, memory, research, quality, applications, observation and recovery.
Start with the layer needed for the task in [manifest.json](manifest.json), then
read its scoped capability decision in [decisions.json](decisions.json). A default
is a selected way to do a task, not permission to install or activate every tool.

The [current layer comparisons](../landscape/foundation.json) explain why each
choice is retained, what happened to named alternatives, and what evidence would
change the decision. Open [Choices & alternatives](../../docs/ecosystem/index.html#landscape)
for the searchable offline view.

The catalog references 61 selected components through 46 capability decisions. Its
registered evidence references are listed per capability. These are coverage counts, not a
score of complete installation, execution or lifecycle acceptance.

The [operator surface manifest](surfaces.json) maps every layer to its upstream
dashboard, native terminal view or CLI, plus installation and lifecycle runbooks.
The existing [Foundation explorer](../../docs/ecosystem/index.html#foundation)
joins those surfaces with canonical repository pins and capability evidence.
Links labelled **This PC** are dated loopback examples: they do not provision a
service or establish installation on another machine. Hosted services, generated
reports, retained exports and live upstream UIs keep their distinct scopes.

The [September 20 community review](../../docs/community-native-practice.md)
explains the selected ECC and Claude practice sources across all twenty layers.
Use the [native Claude profile](../../recipes/claude-native-profile.md) for
terminal entry, small persistent instructions, selected skills and new-PC checks.

## Installation map across all twenty layers

Use each linked recipe's exact upstream commands, platform constraints and returned
evidence. This map joins the selected implementations; it does not reinstall a
working tool or turn every landscape alternative into a default. Component pins
and original results remain in the canonical manifests linked below.

| Layer | Selected implementations | Installation and scoped E2E procedure |
| --- | --- | --- |
| Native clients | Codex, Claude Code | [Native client installation](../../recipes/README.md#component-catalog-install-and-check), [terminal profiles](../../recipes/claude-native-profile.md) |
| Instructions and skills | Native instructions, selected ECC skills, shanraisshan guidance, skills-ref, Tavily skills | [Pinned skills and short defaults](../../recipes/claude-native-profile.md#small-persistent-contract-selected-upstream-skills), [community merits](../../docs/community-native-practice.md) |
| Workers | Native Codex/Claude workers, official Codex SDK, Worktrunk, Beads, systemd | [Worker contract and native commands](../../blueprints/us-equities/worker-supervision/README.md); only general worker operations are reused here |
| Isolation | Worktrunk, sandbox-runtime; Apple Container on macOS | [Native tool recipes](../../recipes/README.md), [platform-specific container checks](../../blueprints/convergence-practice/container-storage/README.md) |
| Code navigation | ast-grep, Serena, jCodeMunch, SocratiCode, codebase-memory, Repomix, MCPorter/Inspector | [Exact symbols and local semantic search](../../docs/foundation-stack.md#local-semantic-code-search-and-exact-symbols), [other native commands](../../recipes/README.md) |
| Document retrieval | QMD, Context Hub, MarkItDown, Poppler | [Scoped lexical retrieval](../../docs/foundation-stack.md#memory-and-lexical-retrieval), [document ingestion](../../blueprints/convergence-practice/document-ingestion/README.md) |
| Semantic RAG | SocratiCode, Qdrant, vLLM, Hugging Face Hub/Nemotron | [Selected GPU/runtime installation](../../docs/foundation-stack.md#local-semantic-code-search-and-exact-symbols) |
| Durable memory | ai-memory, Qdrant, Restic | [Native memory installation](../../docs/foundation-stack.md#memory-and-lexical-retrieval), [application-state restore](../../blueprints/convergence-practice/offhost-app-state/README.md) |
| Web research | agent-browser, Playwright CLI, OpenResearch, Tavily CLI | [Browser/paper tool recipes](../../recipes/README.md), [Tavily installation and returned results](../../recipes/tavily.md) |
| Token efficiency | RTK, Context Mode, jCodeMunch, Headroom, QMD, Repomix, TOON, ccusage | [Native token procedures](../../docs/foundation-stack.md#native-token-tools-and-actual-client-acceptance), [measurement boundaries](../../docs/token-practice.md) |
| Quality and evaluation | promptfoo, Playwright Test, Difftastic, ShellCheck, skills-ref | [Native installations](../../recipes/README.md), [application behavioral checks](../../blueprints/convergence-practice/application-delivery/README.md) |
| CI and supply chain | GitHub Actions, zizmor, Syft, Gitleaks | [Native CI/security verification](../../blueprints/convergence-practice/ci-security/README.md), [dependency inventory](../../blueprints/us-equities/supply-chain/README.md) |
| Scheduling and supervision | Dagu, systemd, Beads | [Job supervision](../../blueprints/us-equities/hosting/README.md), [upstream retry and guest reboot](../../blueprints/convergence-practice/service-reboot/README.md) |
| Hosting and services | FastAPI, Next.js/React, PostgreSQL, MCPorter/Inspector; platform-specific containers | [Native application installation and checks](../../blueprints/convergence-practice/wsl-application/README.md), [application contract](../../blueprints/convergence-practice/application-delivery/README.md) |
| Recovery and portability | Restic, ai-memory, Qdrant, Dagu, systemd, native session continuation | [Lifecycle operations](../../adoption/lifecycle.md), [off-host application restore](../../blueprints/convergence-practice/offhost-app-state/README.md) |
| Observation and inference | OpenTelemetry Collector/otel-tui, Prometheus, Grafana, Loki, Alertmanager, ntfy, AgentsView, ccusage; vLLM/llama.cpp | [Observation setup](../../observability/README.md), [native backends](../../observability/backends/README.md), [GPU compatibility evidence](../../blueprints/convergence-practice/gpu-inference/README.md) |
| Agent SDKs and runtime workers | Codex CLI/SDK; Claude Agent SDK, OpenHands SDK, Temporal, LangGraph remain deferred | [Native client installation](../../recipes/README.md#component-catalog-install-and-check), [SDK table review](../../docs/foundation-closure-20260921.md#sdk-and-runtime-decisions) |
| MCP servers and client surfaces | mcporter, mcp-inspector | [Native project MCP](../../recipes/README.md#native-project-mcp), [other native commands](../../recipes/README.md) |
| Secrets and credentials | Native per-client login, Gitleaks | [Native CI/security verification](../../blueprints/convergence-practice/ci-security/README.md), [lifecycle operations](../../adoption/lifecycle.md) |
| Git practice and GitHub automation | Worktrunk, gh CLI, Difftastic, codex-for-claude review bridge | [GitHub automation handbook](../../docs/github-automation.md), [optional Codex for Claude](../../recipes/README.md#optional-codex-for-claude) |

The September 21 reconciled baseline has 43 accepted capabilities, two partial
optional capabilities and one source-review capability. Layer coverage overlaps:
do not add per-layer counts. No required installation gap is declared in the
current manifest. The retained native Claude terminal observations establish
configured HUD rendering; every statistic and new-host activation remain separate.
The outer companion plugin, exact-model optional gateway inference, four retained
QMD benchmark misses and whole-task causal savings keep their explicit boundaries.

Each layer records its purpose, selected approach, activation condition, lifecycle
scope and next actionable gap. Decisions join actual `component_ids` and
`evidence_ids`; they retain an explicit `evidence_scope`, limitations and activation
rule. `accepted_within_scope` describes the named capability only. Partial,
source-review and pending decisions remain distinguishable from acceptance.

Pins remain in [the stack manifest](../../manifests/stack.json). Original receipt
claims, evidence classes, paths and limitations remain in
[the evidence manifest](../../manifests/evidence.json). Lifecycle `stage_refs` point
to the exact status in [the component matrix](../../blueprints/token-native-focus/saturation-audit.json);
they do not duplicate its commands, stage scope or receipt content. Read those
canonical details before reusing acceptance. Unlisted stages and the explicit
`lifecycle.unknown` field do not become successful by implication.

The [broad decision index](../us-equities/decision-index.json) remains the shared
research inventory at its existing path. Discovery lists, candidates and older
[foundation/memory](../us-equities/foundation-memory.json) or
[agent/operations](../us-equities/agents-operations.json) source reviews remain
available. Their directory placement and reviewed source pins do not supersede
the currently selected component pin or qualify an entire repository.

The manifest explicitly leaves NautilusTrader, LEAN, Alpaca, skfolio, EdgarTools and the currently
financial-only DuckDB/pandas claims in the [US-equities domain](../us-equities/README.md).
Some domain-located fixtures demonstrate reusable operations such as process-tree
termination, dependency inventory or state restore. A FOUNDATION decision cites
only that operation; it does not import strategy, market-data, broker or trading
acceptance. Tavily has a [native CLI receipt](../../evidence/receipts/native-tavily-cli-20260920.json)
for upstream installation, Search/Extract and fresh eight-skill discovery. It retains
the initial Desktop probe failure and temporary-state recovery; it does not claim
that every skill ran in a model turn or that the current Desktop registry hot-reloaded.
The later [current-task receipt](../../evidence/receipts/native-tavily-session-20260920.json)
records eight host-supplied skill entries and actual Search/Extract skill use in
the Desktop task, retaining a broad-search miss and useful direct extraction.

The three tracked foundation priorities are:

1. Keep general capabilities and financial-domain decisions separate, with
   explicit claim scope. This catalog addresses that structure; maintain the
   references when evidence changes rather than migrating the broad inventory.
2. Preserve the accepted inherited-tool worker recovery scope. The
   [combined native receipt](../../evidence/receipts/native-worker-cgroup-20260920.json)
   records same-child continuation, automatic systemd descendant cleanup after
   a forced parent-runtime crash, one unchanged checkpoint and one final effect.
   The earlier manual-cleanup and refused-role trials remain recorded failures;
   this WSL fixture does not establish whole-host or remote-provider recovery.
3. Reuse independently accepted scoped recovery. Synthetic Restic byte/mode
   recovery, one orderly guest service reboot and the
   [native application-state trial](../../blueprints/convergence-practice/offhost-app-state/README.md)
   passed. The application trial retains ten unchanged ai-memory and four Qdrant
   upstream test passes, exact encrypted transfer and actual destination queries
   across separate fresh source/destination jobs. The
   [guest receipt](../../evidence/receipts/native-service-reboot-20260920.json)
   retains real retry/history, pre-login observation, checkpoint and cleanup
   evidence. Production data, client rebinding, cross-application atomicity,
   physical-host disaster recovery and lost-account/key recovery remain separate
   deployment requirements. Four optional/source-review capabilities retain their
   explicit limits; this does not establish universal repository saturation.

Use [the convergence guide](../../docs/convergence-architecture.md) for the work
sequence and [the lifecycle guide](../../adoption/lifecycle.md) for selected native
operations. Keep failed attempts, unknown usage and new-host limits intact.
Use the [catalog retrieval recipe](../../docs/catalog-retrieval.md) to register the
current clone's selected guidance in a named local index for future sessions.
The newer vLLM startup failure, failed gateway inference/compression attempts,
unverified live HUD and TOON expansion remain counterexamples, not successes.

Validate references without installing tools, calling providers or replaying
native acceptance:

```sh
python3 scripts/validate_foundation.py --root . --json
python3 -m unittest tests.test_foundation_catalog
```

The validator checks the 20 layers, unique identities, component/evidence joins,
source paths, explicit scope/limitations, canonical lifecycle statuses, candidate
separation and scoped supersession. It rejects copied pin/receipt fields. A later
decision may supersede only an earlier decision for the same capability and
component scope, retaining the old record with a reason and scope. Structural
validation cannot certify the truth or adequacy of a prose claim; review the cited
receipt and its limitations before changing an adoption decision.

## GitHub automation

The [automation manifest](automation.json) selects maintained upstream interfaces
and records revisions, commands, ownership, actual hosted results and remaining
gaps. The [concise handbook](../../docs/github-automation.md) covers event handling,
reviewed dependency updates, native publication provenance and research-task
acceptance. Required checks, source integrity, setup-toolchain fixtures and useful
Codex/Claude research output remain separate evidence. The existing daily Codex
maintenance task owns source research; optional gh-aw and Renovate candidates do
not add competing writers or schedules.
