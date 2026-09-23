# Foundation baseline: September 20 New York / September 21 UTC, 2026

Retain native Claude Code and Codex, the selected upstream context tools, and
bounded workers under the existing Dagu/systemd supervision. The reviewed
candidate set supports this baseline. It does not establish a universal best
stack or that every layer has passed every lifecycle condition. The foundation
is ready for continued engineering within its accepted scopes; the trading
destination retains separate data, simulation and broker gates.

This recheck starts from `23533cea0631252e43218ce3c73a50caa1c1374d`.
It reuses the [16-layer catalog](../catalogs/foundation/manifest.json),
[component pins](../manifests/stack.json), and [native profile](../recipes/claude-native-profile.md).
No new SDK, full community plugin bundle, gateway or scheduler is needed to close
the demonstrated setup gaps. Existing terminal profiles, upstream installations,
selected ECC skill hashes and persistent native settings were inspected again.

## Current source convergence

| Source, reviewed pin | Why it merits the shortlist | Decision and limits |
| --- | --- | --- |
| [ECC](https://github.com/affaan-m/ECC/tree/2b6e839771e53096d8451a213d40dc64ec8acac0), `2b6e8397` | Research before implementation; bounded refinement of missing worker context | Retain installed `search-first` and `iterative-retrieval`; both match recorded source hashes and appear once each in native Claude discovery. Do not adopt the full hooks/rules bundle. |
| [Shan Claude practice](https://github.com/shanraisshan/claude-code-best-practice/tree/bde3f03174714fff4145d21cfda41ddd2ffffb28), `bde3f031` | Native-format examples, concise instructions, worktrees, independent review and test gates | Reference; source review is its acceptance level. Embedded workflow examples can be older than the repository head. |
| [Awesome Claude Code](https://github.com/hesreallyhim/awesome-claude-code/tree/1abbc780c889b08fb424d82346dbc8057cb345fd), `1abbc780` | Broad discovery for a named missing capability | Link-only discovery; CC-BY-NC-ND-4.0. This newer head does not invalidate runtime acceptance. |
| [VoltAgent subagents](https://github.com/VoltAgent/awesome-claude-code-subagents/tree/ca7a50b7648682c3a9e33dbf0a12c5a4c770cb89), `ca7a50b7` | Role-contract examples | Conditional reference; inspect tools, model and permissions per role. A reviewer title does not enforce read-only behavior. |
| [Awesome MCP](https://github.com/punkpeye/awesome-mcp-servers/tree/1e0b27d6240f1c8cdff30927f54566dc4aedbce3), `1e0b27d6` | Integration discovery | Evaluate the actual server, authority and output cost before adoption. No blanket registration. |
| [Anthropic skills](https://github.com/anthropics/skills/tree/34040c9c568585f6929bedeaad110ad08f079624), `34040c9c` | Official skill-format and task examples | On-demand reference. Licenses vary; document skills are source-available. Existing Claude sync already exposes selected official skills. |

ECC, Shan and VoltAgent still match the previous source review. The two awesome
lists advanced. The earlier [review](community-native-practice.md) remains a dated
record; this table records the subsequent observations. Recent activity, stars,
author claims and list membership are discovery signals, not comparative tests.

Two concrete exceptions matter. ECC's [token guide](https://github.com/affaan-m/ECC/blob/2b6e839771e53096d8451a213d40dc64ec8acac0/docs/token-optimization.md)
suggests model substitutions and a fixed thinking budget. Current [Claude cost
guidance](https://code.claude.com/docs/en/costs#adjust-extended-thinking) says
adaptive models ignore nonzero `MAX_THINKING_TOKENS`; preserve the selected
model and native effort control. Shan's [cross-model example](https://github.com/shanraisshan/claude-code-best-practice/blob/bde3f03174714fff4145d21cfda41ddd2ffffb28/development-workflows/cross-model-workflow/cross-model-workflow.md)
is dated March 6 and names older models. Reuse its independent review principle,
without importing old model names or mandatory interview/restart sequences.

## Final candidates by foundation layer

These are retained candidates with task-specific merits, not a requirement to
activate all tools. Their repository-root links identify projects, not new HEAD
pins. Exact accepted versions, alternative decisions and evidence remain in the
linked manifests at base `23533cea`; this pass rechecks the specifically dated
community/client/SDK candidates above and below. No unchanged layer is recertified
by this research pass.

| Layer | Selected repositories / native facility | Merit and remaining boundary |
| --- | --- | --- |
| Native clients | [Claude Code](https://github.com/anthropics/claude-code), [Codex](https://github.com/openai/codex) | Preserve native accounts, supported tools, caching and session recovery. Installed 2.1.278 / 0.155.1 match checked release metadata. |
| Instructions and skills | ECC; [OpenAI skills](https://github.com/openai/skills) (gh-fix-ci, security-best-practices); [TypeSafe](https://github.com/typesafe-ai/skills); [Agent Skills](https://github.com/agentskills/agentskills) as a conditional supporting format validator, not a procedure source | Small essential instructions plus selected skills. Source-format checks and discovery do not prove better task outcomes. Reconciled 2026-09-23 against the counterbalanced adjudication (`evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-instructions-skills-20260922.json`, winner_lane claude, 2/2 votes, 0 refuting): TypeSafe (c8) has stronger retained on-demand-procedure evidence than the row previously listed, while Agent Skills (c9) validates the installed skills' format without supplying its own task procedures. |
| Workers | Native subagents; [Beads](https://github.com/gastownhall/beads) when dependency queues help | Owned tasks and checkouts, concise handoffs, one integrator. Same-host recovery has a bounded accepted fixture; provider cancellation and independent-host recovery remain separate. |
| Isolation | Git worktrees; [Anthropic sandbox-runtime](https://github.com/anthropics/sandbox-runtime) when required | Worktrees isolate edits; explicit OS/process boundaries isolate execution. A tool list or role prompt is not an OS sandbox. |
| Code navigation | [ripgrep](https://github.com/BurntSushi/ripgrep), [Serena](https://github.com/oraios/serena), [ast-grep](https://github.com/ast-grep/ast-grep); scoped indexed tools | Exact search for known identifiers; symbols/structure for relevant questions. Inspect original source before changes or correctness judgments. |
| Document retrieval | [QMD](https://github.com/tobi/qmd), [Context Hub](https://github.com/andrewyng/context-hub), [MarkItDown](https://github.com/microsoft/markitdown) | Scoped retrieval/conversion; selected corpora only. Existing QMD negative/miss results still constrain wider quality claims. |
| Semantic RAG | [SocratiCode](https://github.com/giancarloerra/SocratiCode), [Qdrant](https://github.com/qdrant/qdrant), [vLLM](https://github.com/vllm-project/vllm) | Accepted local conceptual retrieval. Preserve embedding identity and compatible runtime; another project/GPU requires qualification. |
| Durable memory | [ai-memory](https://github.com/akitaonrails/ai-memory) | Shared scoped continuity across harnesses; retrieved text remains untrusted. No duplicate automatic learning store. |
| Web research | [Tavily CLI](https://github.com/tavily-ai/tavily-cli), [agent-browser](https://github.com/vercel-labs/agent-browser), primary documentation | Bounded discovery, extraction and browser operations. Search acceptance does not qualify every crawl/research mode. |
| Token efficiency | [RTK](https://github.com/rtk-ai/rtk), [Context Mode](https://github.com/mksglu/context-mode), [Repomix](https://github.com/yamadashy/repomix), selected [Headroom](https://github.com/chopratejas/headroom)/[TOON](https://github.com/toon-format/toon) | Choose one sufficient lane per artifact, retain original recovery. Compression and cache counters cannot be summed into provider savings. |
| Quality and evaluation | Actual project/upstream tests; [promptfoo](https://github.com/promptfoo/promptfoo), [ShellCheck](https://github.com/koalaman/shellcheck), [Difftastic](https://github.com/Wilfred/difftastic) where applicable | Behavior oracles and independent findings. Consensus and synthetic fixtures alone are insufficient. |
| CI and supply chain | GitHub native automation; [zizmor](https://github.com/zizmorcore/zizmor), [gitleaks](https://github.com/gitleaks/gitleaks), [Syft](https://github.com/anchore/syft) | Pinned actions, permission/secret checks and inventory. No blanket vulnerability assurance. |
| Scheduling and supervision | [Dagu](https://github.com/dagucloud/dagu), Linux user services | Reuse command graphs and owned process trees. Avoid multiple independent retry owners for one effect. |
| Hosting and services | Existing locked Next/React/FastAPI/PostgreSQL fixture | Familiar supported interfaces, explicit deployment ownership. Fixture acceptance does not authorize paid hosting or qualify production recovery. |
| Recovery and portability | [Restic](https://github.com/restic/restic), application backups and native resume | Retain bytes, source pins, ownership and recovery tests. Actual production data, lost credentials and independent administrative recovery remain distinct. |
| Observation and optional inference | [OpenTelemetry](https://github.com/open-telemetry), [otel-tui](https://github.com/ymtdzzz/otel-tui), [agentsview](https://github.com/kenn-io/agentsview), existing Claude HUD | Scoped native usage/history and useful rendering. Optional inference/gateways need their own route and workload tests. |

## SDK and runtime decisions

Version metadata was read on September 21 UTC through official GitHub
`releases/latest` and `commits?per_page=1`, PyPI package JSON, and npm `latest`
endpoints. The [source observations](../evidence/artifacts/foundation-closure-20260921/source-observations.json)
retain exact URLs, returned versions, methods and registry/release differences.

Use the native CLI for a bounded review. Use an official SDK when the application
needs structured events, custom tools or programmatic session control. Existing
Codex SDK integration remains accepted only within its recorded tests.

| Candidate checked now | Merit | Decision |
| --- | --- | --- |
| [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview): Python registry 0.2.157; TypeScript 0.3.278 | Official programmatic native agent loop | Preferred Claude SDK candidate when needed; not newly installed or qualified. GitHub latest Python release reported 0.2.156, so registry/release labels differ. |
| [Codex SDK](https://developers.openai.com/codex/sdk): 0.155.1 | Supported start/run/resume interface | Retain existing working integration; qualify a version change before promotion. |
| [Temporal Python](https://github.com/temporalio/sdk-python/tree/eb642b14947bd8bcdf8816cffb6a63869803f5c6): 1.33.0 | Cross-host durable workflow ownership/replay | Deferred until required; adds a service and distinct effect/recovery semantics. |
| [LangGraph](https://github.com/langchain-ai/langgraph/tree/ed384f3a124660db6dccd6c53eaad48e1457e0b5): 1.2.11 | Explicit state/checkpoints for agent applications | Deferred unless building an application needing these semantics. |
| [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk/tree/856d99d48e4b11c70c5f1cab21e7830570dbc324): 1.49.2 | Remote isolated worker environments | Conditional for remote/container workers; does not improve the current local review merely by installation. |

Current [Claude SDK configuration](https://code.claude.com/docs/en/agent-sdk/claude-code-features)
says omitted `settingSources` loads user/project/local settings; explicit `[]`
disables those sources, while managed policy and global configuration remain.
Test actual effective settings instead of relying on older SDK advice.
Native `TaskStop`/`SendMessage` and user cancellation/SDK `stop_task` have different
[continuation semantics](https://code.claude.com/docs/en/sub-agents#resume-subagents).
The accepted [worker recovery](../blueprints/convergence-practice/worker-recovery/README.md)
does not establish SDK cancellation, provider billing cessation, host failure or
distributed exactly-once effects.

The starter's named `evidence-reviewer` currently restricts its tools to
Read/Glob/Grep. That particular role remains a conditional restricted profile,
not an accepted inherited-tool worker. Use an inherited-tool native reviewer
under an explicit no-edit task contract for the normal review lane. This retains
installed hook compatibility but does not enforce read-only access at OS level;
select a separately qualified sandbox when that enforcement is required.

## Actual session and terminal evidence

The named Claude and Codex Windows Terminal profiles already exist and resolve
to the expected native launchers. They were not reinstalled or duplicated.
Native Claude 2.1.278 opened authenticated in the selected project, displayed
Opus 5 with xhigh effort, and rendered the HUD. `/context all`, `/context`,
`/usage` and `/mcp` ran in the interactive client, not as headless model prompts.

The first `/context all` reported approximately **33.8k / 1m** context tokens:
system prompt 3.3k, system tools 14k, MCP definitions 609, custom agents 141,
memory/instructions 4.5k, skills 9.5k and messages 1.8k. These rounded UI estimates
are not a provider bill. It listed 68 skills, three custom agents and 95 available
MCP tools. All six MCP servers displayed connected. The existing embedding-prefix
whitespace warning remains intentional; removing those spaces would alter the
accepted embedding input format.

`/usage` first showed zero API duration and zero input/output/cache tokens before
any model prompt. After the bounded native review it showed nonzero usage:
Opus input 4, output about 9.4k, cache read 93.0k and cache write 52.2k; an auxiliary
Haiku request showed about 1.1k input and 12 output. The session view reported
41 seconds API duration and an API-equivalent estimate of $0.81, not a subscription
bill. The transcript's two unique Opus response IDs total 4 input, 9,429 output,
93,038 cache read and 52,217 cache creation tokens. Auxiliary request totals are
not fully reconstructed from those two response IDs; do not call their sum the
complete session usage. The live HUD rendered model, project, context and usage.
This establishes context/usage views, nonzero usage display and HUD rendering on
this host. It does not prove exact billing reconciliation, Windows Terminal dropdown use,
every HUD statistic, automatic compaction, or every MCP operation. Repeated
diagnostic output itself increased message context; these commands are checks
for a concrete question, not a mandatory startup ritual.

Manual `/compact` then completed with successful native PreCompact hook messages
for ai-memory and Context Mode. The native compact-boundary record reports
87,434 pre-compaction and 14,934 post-compaction tokens, taking 42,506 ms. This is
a native context-size observation, not provider savings: compaction itself uses
inference. A subsequent no-tool continuity prompt recovered the review-contract
identifier and unknown-savings boundary. Automatic compaction and preservation
of every fact remain untested.
The initial broker wording was ambiguous; a follow-up returned an explicit
statement that this review establishes no broker execution acceptance. Both
responses are retained in the [compaction observation](../evidence/artifacts/foundation-closure-20260921/compaction.json).

## Persistent practice and future PCs

Use the saved [native profile](../recipes/claude-native-profile.md) and
[session handbook](token-session-handbook.md). The current host already has the
native PATH, RTK setting, Context Mode hooks, scoped memory/index configuration,
short global instructions and two selected shared ECC skills. This pass preserves
the existing model, effort, accounts and permissions. More reasoning is a chosen
quality preference, not a token-saving claim.

1. On a new PC, select the needed adoption profile and install its pins through
   the linked upstream commands. Resolve that PC's paths and use native sign-in.
2. Merge the short instruction contract and selected supported settings. Preserve
   existing preferences. Adopt project memory and indexes explicitly; do not copy
   credentials or another host's active state.
3. Check one useful native task, discovery, recovery and cleanup for the selected
   capability. Use upstream tests/examples when available, and label local glue
   checks separately. Historical receipts cannot be a new host's passed status.
4. In ordinary work, start from the requested result and a meaningful acceptance
   condition; load only matching skills and sources. Reuse valid evidence, use
   bounded workers, resolve supported review findings, and preserve failures.
5. Refresh the existing token report after meaningful efficiency changes or when
   reporting counters. Keep Context Mode/RTK estimates, exact artifact reductions,
   native cache reuse and complete provider usage separate.

The current session has the installed capabilities and follows this selection
policy. It is not proven maximally efficient or exhaustively current: early
discovery returned oversized metadata, and parallel research/review has its own
cost. No causal whole-session or lifetime token saving is claimed.

## North-star boundary

Retain NautilusTrader 2.0.0rc5 / IBKR and the separate Alpaca path. The
[official IBKR integration](https://nautilustrader.io/docs/latest/integrations/interactive_brokers/)
is a native adapter; the current [integration list](https://nautilustrader.io/docs/latest/integrations/)
does not supply an Alpaca adapter. Existing engine/FX replay and authenticated
Alpaca data are not equity execution acceptance. Continue the frozen
[engine acceptance plan](../blueprints/us-equities/engine-nautilus/acceptance-plan.md):
economic-oracle replay, broker fault behavior, IBKR paper and Alpaca paper remain
separate. Model workers research and review; deterministic code owns numeric risk,
orders and reconciliation. Existing paper authorization persists.

## Review and limits

Three bounded read-only workers independently checked community sources, runtime
choices and local configuration. Their findings converged on retaining the
baseline, correcting provenance drift, and closing the interactive evidence gap.
A native Claude review and final structural checks are recorded with the closure
evidence. Agreement is supporting review evidence, not a substitute for the
actual native observations or upstream/project behavior checks.

The [review adjudication](../evidence/artifacts/foundation-closure-20260921/review-adjudication.md)
retains accepted and unsupported findings; the [screen observations](../evidence/artifacts/foundation-closure-20260921/observations.json)
are explicitly separate from the [native context export](../evidence/artifacts/foundation-closure-20260921/context-before.txt).
The [validation record](../evidence/artifacts/foundation-closure-20260921/validation.json)
reports passing artifact/catalog checks and the secret scanner's 197 unchanged
baseline matches on SHA-256-shaped metadata. No clean whole-repository security
claim follows from that comparison.
