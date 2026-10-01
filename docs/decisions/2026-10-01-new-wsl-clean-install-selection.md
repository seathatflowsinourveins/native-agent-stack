# The new WSL's clean-install recommendations, per foundation layer (2026-10-01)

## Decision

For the clean install of the new WSL distribution, the repositories below are recommendations on repository evidence,
not merit winners. Under program decision 5 and the accepted U11 design (revision 4, `89424e36`), each layer's
preregistered comparison on the new distribution selects its winner, and a recommendation is one input to that
comparison's arm set; it is not confirmed by default. Where the column says "compare", the critics could not separate
the candidates and every listed arm installs fresh. The judges themselves flagged 19 of the 21 layers as close calls
(all but native-clients and agent-sdks). One model family judged; see Cross-family status.

| Layer | Recommended, or the arms to compare | Status |
| --- | --- | --- |
| native-clients | Claude Code; Codex | recommended |
| agent-sdks | Claude Agent SDK; Codex SDK and codex exec/app-server | recommended |
| instructions-skills | Trail of Bits security skills (trailofbits/skills) | recommended, close call |
| mcp-surfaces | mcporter; MCP Inspector | recommended, close call |
| workers | claude-code (native subagents, worktree isolation, agent teams); Codex native workers (subagents); Worktrunk | recommended, close call |
| isolation | sandbox-runtime (recommended); a rootless container on the hosting-services engine winner; gVisor runsc on that engine; boxlite with /dev/kvm; it uses Worktrunk and the hosting-services engine | compare the arms on the new WSL |
| code-navigation | Serena; claude-plugins-official (code-intelligence LSP plugins) | recommended, close call |
| semantic-rag | SocratiCode (embeddings from the local model server; its documented providers are Ollama, LM Studio, LiteLLM, OpenAI and Google); semble; ColGREP with LateOn-Code-edge; ColGREP with LateOn-Code; BM25 baseline; ripgrep baseline | compare the arms on the new WSL |
| document-retrieval | tobi/qmd; MinerU | recommended, close call |
| web-research | trafilatura; Playwright CLI | recommended, close call |
| durable-memory | ai-memory, LLM reranker on and off; Hindsight, local model and hosted model; agentmemory through its Claude Code and Codex hooks; deja-vu | compare the arms on the new WSL |
| token-efficiency | ccusage (measurement, selected); no compression layer (baseline); RTK; sqz; Headroom; Context Mode (frozen control) | compare the arms on the new WSL |
| observation-inference | OTel Collector Contrib; Prometheus; Loki; Grafana; llama.cpp optional inference; Phoenix | recommended, close call |
| quality-evaluation | Inspect AI; Harbor (containerized agent E2E runner); Promptfoo | recommended, close call |
| ci-supply-chain | zizmor; attest; Syft; Dependabot; codeql-sarif; actionlint (kjanat) | recommended, close call |
| scheduling-supervision | Dagu; systemd | recommended, close call |
| hosting-services | Docker Compose (selected); Podman with Quadlet; rootless Docker Engine | compare the arms on the new WSL |
| secrets-credentials | betterleaks; trufflehog | recommended, close call |
| git-github-automation | git; gh (GitHub CLI); worktrunk; difftastic; sem (lowest confidence; kept only if the structural-diff comparison shows a gain); claude-code-action | recommended, close call |
| recovery-portability | mise; Restic; chezmoi | recommended, close call |
| cross:wsl-distro | Ubuntu 26.04.1 LTS (Canonical WSL image), primary; Ubuntu 24.04.5 LTS (Canonical WSL image), fallback | recommended, close call |

For a compare layer the row lists every arm its deciding comparison names. Each pick's upstream install command and
source, its role, the deciding comparison and the critics' checks are in
`evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json`; the folder's README says where the
full judge and critic returns are kept and why.

## One owner per tool (no overlap)

Each tool belongs to exactly one layer; another layer that needs it lists it under "uses". Two tools that do the same
job became one comparison owned by one layer. The map is `ownership.json` in the evidence folder.

| Layer | Owns | Uses from another layer |
| --- | --- | --- |
| native-clients | Claude Code; Codex | - |
| agent-sdks | Claude Agent SDK; Codex SDK (the package; the CLI it drives comes from native-clients) | Claude Code and Codex (native-clients) |
| instructions-skills | Trail of Bits skills | - |
| mcp-surfaces | mcporter; MCP Inspector | - |
| workers | nothing installed | the native subagents of Claude Code and Codex (native-clients); Worktrunk (git-github-automation) |
| isolation | sandbox-runtime; compare: the container boundary for untrusted work (a rootless container on the hosting-services engine winner, gVisor runsc, boxlite) | Worktrunk (git-github-automation); the container engine (hosting-services) |
| code-navigation | Serena (Codex sessions); the official code-intelligence LSP plugins (Claude Code sessions) | - |
| semantic-rag | compare: SocratiCode, semble, ColGREP, against BM25 and ripgrep baselines | the local model server for embeddings (observation-inference) |
| document-retrieval | QMD; MinerU | - |
| web-research | trafilatura; Playwright CLI | - |
| durable-memory | compare, one memory owner: ai-memory, Hindsight, agentmemory, deja-vu | the local model server for Hindsight's local-model arm (observation-inference) |
| token-efficiency | ccusage (measurement); compare: RTK, sqz, Headroom, against no compression layer | - |
| observation-inference | OTel Collector Contrib; Prometheus; Loki; Grafana; Phoenix (trace sink only); compare, one local model server: Ollama, llama.cpp | - |
| quality-evaluation | Inspect AI (evaluations); Harbor (agent end-to-end runner); promptfoo (CI regression gate) | - |
| ci-supply-chain | zizmor; attest; Syft; Dependabot; CodeQL upload-sarif; actionlint | - |
| scheduling-supervision | Dagu | systemd user units (cross:wsl-distro) |
| hosting-services | Docker Compose; compare, one container engine: Podman with Quadlet, Docker Engine | - |
| secrets-credentials | betterleaks (detection: pre-commit, history, CI); trufflehog (verification of found credentials only) | - |
| git-github-automation | git; gh; Worktrunk; difftastic (diffs for people); sem (diffs for agents; only if its comparison shows a gain); claude-code-action | - |
| recovery-portability | mise (runtimes; it installs uv, which owns Python packages and locks); Restic; chezmoi | - |
| cross:wsl-distro | Ubuntu 26.04.1 LTS (fallback 24.04.5 LTS); systemd (part of the distribution) | - |

Overlaps in the selection and how they are resolved:

- Claude Code and Codex were picked in native-clients, workers and agent-sdks. native-clients owns both clients; workers uses their native subagents and agent-sdks owns only the SDK packages.
- Worktrunk was picked in workers, isolation and git-github-automation. git-github-automation owns it; workers and isolation use it.
- Podman was an arm in isolation and in hosting-services, and Docker in both comparisons. One container-engine comparison, owned by hosting-services. isolation owns only the boundary question on top of the winning engine: plain rootless container, gVisor runsc or boxlite.
- Ollama (semantic-rag, as SocratiCode's embedding service) and llama.cpp (observation-inference, as the local inference route) are two local model servers. One local model server, owned by observation-inference: Ollama against llama.cpp. It must serve the code-RAG winner's embeddings; SocratiCode documents Ollama, OpenAI, Google, LM Studio and LiteLLM as providers, not llama.cpp directly.
- Phoenix (observation) also runs experiments and scores evals, the job of Inspect AI (quality-evaluation). Phoenix is the trace sink only; evaluations belong to Inspect AI.
- systemd was a pick of scheduling-supervision. It comes with the base distribution; scheduling-supervision owns Dagu and uses systemd user units.
- uv (Python versions, packages and locks) overlaps mise (runtime versions). mise owns runtime versions and installs uv; uv owns Python packages, virtual environments and locks. The judges placed uv under mise.
- Serena and the official LSP plugins both give symbol navigation. Split by client: the LSP plugins in Claude Code sessions, Serena in Codex sessions, as the judges assigned them.
- betterleaks and trufflehog both scan for secrets. betterleaks detects (pre-commit, history, CI); trufflehog only verifies what is found against the provider.
- difftastic and sem both produce structural diffs. difftastic for people reviewing; sem for agents, and only if its comparison shows a gain.

Comparison order: the code-RAG comparison runs before the local-model-server comparison, which then has to serve the
code-RAG winner's embedding provider; the container-engine comparison runs before isolation's boundary comparison.

At the boundary with the us-equities layers: analytical storage (DuckDB with Parquet) is owned by storage-compute,
research data versioning (DVC) by identity-provenance, research experiment tracking (MLflow) by evaluation-experiments
and market-data validation (pandera) by data-quality-orchestration; retrieval evaluation (agent-retrieval-bench) stays
with the foundation as a candidate task set for the semantic-rag and document-retrieval comparisons.

Residual: QMD runs its own embedding and reranking models in process (node-llama-cpp); it is not a second model server, and it stays inside document-retrieval.

The 12 us-equities layers own only trading-specific capabilities; shared infrastructure (agents, memory, scheduling, observability, storage tooling, CI, evaluation) is used from the owning foundation layer, not selected again. The trading lane owner accepted this rule on 2026-10-01 for its run after the GPT pool resets; its earlier trading selections that are now foundation-owned (Inspect AI, gitleaks, Grype, the observability stack) become uses of the foundation layers.


## Fact corrections

The critics found seven facts that did not hold, and an independent audit by the Codex lane (Astra at max, 2026-10-01)
gave the supported replacement for each. None changes a recommendation; each is recorded here and in `selection.json`
(`fact_corrections`), and the original returns stay as they were.

- native-clients: Letta (letta-ai/letta) was excluded as stale_or_archived. It is not archived; default-branch commit 5bcdd177 on 2026-09-10. The supported basis is outside_requirement: the repository holds the retired V1 server, not a client. It stays excluded on that criterion. (https://github.com/letta-ai/letta/commit/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a)
- secrets-credentials: The judge wrote that the two local scanners send no content off the host. TruffleHog verifies credentials through the providers' APIs, so its verification contacts those services; local scanning alone does not establish that nothing leaves the host. (https://github.com/trufflesecurity/trufflehog/blob/main/README.md)
- secrets-credentials: The judge read Betterleaks' published result as a classification of already captured secrets. Betterleaks' 0.892 figure is an author-run CredData result with a modified configuration. (https://lookingatcomputer.substack.com/p/rare-not-random)
- git-github-automation: The judge wrote that claude-code-action has no GitHub release in the last 90 days. claude-code-action published v1.0.239 on 2026-10-01; the floating v1 'Latest' object does not show staleness. (https://api.github.com/repos/anthropics/claude-code-action/releases?per_page=10)
- git-github-automation: The judge read a cancelled July CI run as Worktrunk's current CI state. Worktrunk commit ca8d3797 has current Linux, macOS and Windows checks. (https://api.github.com/repos/max-sixty/worktrunk/commits/ca8d3797b245/check-runs?per_page=100)
- git-github-automation: The selection assumed sem runs a Linux test suite in CI. sem's workflows at dfcb3de6 build and package for Windows; Linux testing is not established. (https://github.com/Ataraxy-Labs/sem/blob/dfcb3de6c8bb32eda4005b0b3260b2b437f256db/.github/workflows/test-windows.yml)
- cross:wsl-distro: The judge cited microsoft/WSL#40593 as the reason 24.04.5 is a safe fallback. The issue does not show comparative safety: a 2026-05-19 contributor comment describes shared-cgroup collisions across instances. (https://github.com/microsoft/WSL/issues/40593#issuecomment-4486165852)

## Cross-family status

Only one model family judged this run. The GPT-6.1 Sol reviews of the 32 layers on 2026-10-01 (PR #575) reviewed the
source host's record rather than these blind packets, so their agreement with these recommendations is not a second
blind judgment: against them, 3 layers agree (native-clients, mcp-surfaces, scheduling-supervision), 13 overlap in
part and 4 differ (instructions-skills, web-research, hosting-services, secrets-credentials), and in each of the four
the review kept the source host's tools. A blind GPT-6.1 Sol run on the same packets, criteria and prompts is requested
from the Codex lane. Where the two families agree, the recommendation stands as an arm; where they differ, both picks
enter the layer's comparison.

## Why this method

The user asked on 2026-10-01 for the best repositories per layer for the clean install, after asking twice why the
architecture still showed the source host's list. The old list carried three advantages for what the host already ran:
its winners column copied the host's pins, the verdict tooling could crown only an adopted candidate, and the challenger
search made each newcomer prove a gap against the pick of record (the design record
`docs/decisions/2026-10-01-u11-merit-neutral-selection.md`, accepted for implementation by both reviewers at revision 4,
`89424e36`). This run removed those advantages without waiting for that tooling:

- **Blind packets.** Each judge read only the layer's requirement, what a deciding comparison would measure, the target
  hosts and the candidates as name and repository, in a seeded shuffle. The packets held every candidate of the
  landscape catalogs, every survivor of the 2026-09-29 sweep and the second-family review's selections; they did not
  hold 15 of the 25 survivors of the 2026-09-26 sweep or most proposals the v1 sweeps refuted (see Not covered). Selection words in the requirement texts were
  made neutral (`build_packets.py`, the `NEUTRAL` list).
- **Symmetric evidence.** The project's own receipts and records were excluded, because native runs exist mostly for
  what the source host installed. Judges used upstream public evidence only. Comparisons on record were meant to enter
  where every named arm ran; four did, and the Harbor end-to-end run of the token tools (36 tasks, seven arms, PR #570)
  qualified under that rule but was left out of the token-efficiency packet, so its comparison on the new distribution
  starts from that run.
- **Frozen criteria.** Capability fit, public measured evidence, 90-day currency, maintenance, WSL2 and RTX 4090 fit, an
  upstream install command and agent-client integration; stars, popularity and current use are not evidence. The
  criteria and prompts were hashed at 2026-10-01T17:35:24Z (`preregistration.json`), 35 seconds before the run started.
- **Adversarial critics.** One critic per group re-checked two or three facts per pick against primary sources, looked
  for a stronger candidate and for reasoning that leaned on popularity or current use, and returned upheld, revised or
  undetermined. An undetermined layer becomes "compare".

Run: workflow `wf_c2377ebb-65c`, 11 judges and 3 critics, Claude Opus 5.5 at effort max (`stack-researcher`), 14 of 14
returned, 3,144,333 subagent tokens and 622 tool calls.

## What the critics changed

- instructions-skills: the second pack (Anthropic's example-skills) was removed; its install turns on 12 skills at once,
  and the packet's own rule adds a pack only after a paired run shows a gain.
- code-navigation: codebase-memory-mcp was removed; its only answer-quality measurement, its authors' preprint, places it
  below the file-exploration baseline (83% against 92%).
- durable-memory: deja-vu was added as a fourth arm of the comparison.
- Five layers were undetermined and became "compare": isolation (the container slot), semantic-rag, durable-memory,
  token-efficiency and hosting-services (the container engine).
- 7 checked facts did not hold (corrected under Fact corrections). All are in the judges' reasons; none overturns a pick:
  - native-clients: letta-ai/letta (C03) is stale or archived under the frozen definition (archived, or no default-branch commit in 90 days)
  - secrets-credentials: The judge's ggshield reason: 'The two local scanners need no hosted account and send no content off the host'
  - secrets-credentials: The judge's reading that the post 'classifies secrets that were already captured; it is not a standalone detection test' (only partly true: the filter runs after capture, but the .892 is reported for running Betterleaks against CredData)
  - git-github-automation: The judge's claim that claude-code-action has no GitHub Release in the last 90 days and that its latest release object is v1 (2025-08-26)
  - git-github-automation: The judge's statement that worktrunk's latest main-branch 'ci' run was cancelled (2026-07-23), read as current CI state
  - git-github-automation: sem's default-branch CI runs a Linux test suite (implied by the 'tested' status the selection assumes)
  - cross:wsl-distro: Issue #40593 shows that Ubuntu-24.04 instances avoid the systemd user-session failure (the judge's basis for the fallback)
- The critics flagged reasoning that leaned on current use in two layers (native-clients and instructions-skills) and
  restated those reasons on the criteria.

## The base distribution and the recipe

The judges selected Ubuntu 26.04.1 LTS, with 24.04.5 LTS as the fallback; the critic upheld it and found that
microsoft/WSL#40593 (a systemd user-session start failure) does not separate the two. The recipe
`adoption/platforms/linux-wsl2-new-distro.md` is written for 24.04.5 and has not run on any host. Its rehearsal on a
throwaway name is where the two images are compared: first boot, the user session with a second instance running, the
GPU through WSL, and the toolchains.

## Not covered

- The 12 us-equities layers: the trading lane owner runs this method unchanged on the GPT lane after the pool resets at
  2026-10-03T17:14Z. The user-pinned NautilusTrader and IBKR destination is a requirement, not a judged slot.
- The cross rows for the runtime workers, the GPT-6 harnesses, the credential practice and the convergence practice.
- Part of the field. The packets did not hold 15 of the 25 survivors of the 2026-09-26 sweep (in observation-inference
  grafana/tempo, traceloop/openllmetry, ollama, nvidia_gpu_exporter and dcgm-exporter; in quality-evaluation mteb, mutmut,
  cosmic-ray and opik; in mcp-surfaces mcpc and conformance; in scheduling-supervision absurd; in instructions-skills
  skill-scanner and financial-services; in durable-memory anthropics/claude-code) or 266 of the 328 distinct layer and
  repository pairs that the v1 sweeps refuted. Under the U11 design those enter the field as pending and are voted
  again; until then this selection inherits the v1 refutations for them.

## What follows

1. An install profile for the new distribution built from this list: a pinned version and the upstream install command
   for each pick, every arm of the five comparison layers included (program unit U8).
2. The recipe's image choice settled by the rehearsal of both images.
3. Stage 2 on the new distribution, then each comparison layer's preregistered head-to-head.

## Evidence class

Source-review recommendations by model judges with adversarial checks, not merit winners, representative comparisons or
new-host acceptance; all 14 agents were one model family (Claude Opus 5.5), with no replication across families or
orders and no fresh per-arm comparison. No
candidate was installed or measured by the run. The install commands record upstream's documented path, eleven of them a
script piped to a shell and eleven naming @latest; the install profile pins each release and verifies its checksum
before stage 2 runs it. A judge's deciding comparison is input to the preregistered arm set of U11's section D, not the
arm set itself.

## Overturn

A preregistered comparison on the new distribution; the re-vote of the candidates the packets did not hold, which can
add arms or reopen a selected layer; a fact a later check finds wrong where a pick rests on it; a new upstream release
or maintenance change that alters a criterion.

## Addendum (2026-10-01): the cross-family half ran

The blind GPT-6.1 Sol run requested under "Cross-family status" ran the same day on the same frozen packets, criteria
and prompts: 11 judges in 3 groups and one critic per group, GPT-6.1 Sol at effort max through the Codex CLI
(`cross-family/`, with its preregistration addendum recorded before the first process). Against this record's
recommendations the two families agree exactly on 2 layers (native-clients and agent-sdks), overlap on 19 and differ on
none. The GPT critics upheld 4 selections, revised 1 (workers) and found 16 undetermined. Under the agreement rule
frozen before the run (`cross-family/agreement-rule.txt`), applied as written, every pick both families made stands as
its layer's pick for the new distribution, so all 21 layers have standing picks: native-clients and agent-sdks on
identical recommendations, document-retrieval, scheduling-supervision and the base distribution on identical pick
sets, and the other 16 layers on shared picks with every pick of one family only entering the layer's comparison as a
challenger. A standing pick is final once it passes acceptance on the new distribution and, where challengers exist,
the measured comparison. Each row's standing picks, challengers, arms and gate ledger are in
`catalogs/foundation/final-catalog-20261001.json` (decision record `docs/decisions/2026-10-01-final-catalog.md`). The
Decision table above remains this run's record.
