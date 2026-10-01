# The new WSL's clean-install selection, per foundation layer (2026-10-01)

## Decision

For the clean install of the new WSL distribution, each of the 20 foundation layers and the base distribution installs
the repositories below. Where the column says "compare", the new distribution installs every listed arm fresh by its
upstream commands, and the layer's preregistered head-to-head there picks the winner (program decision 5). The list
was chosen blind on repository evidence; it is not a measured merit result, and each layer's comparison on the new
distribution confirms or overturns it.

| Layer | Install on the new WSL | Status |
| --- | --- | --- |
| native-clients | Claude Code; Codex | selected |
| agent-sdks | Claude Agent SDK; Codex SDK and codex exec/app-server | selected |
| instructions-skills | Trail of Bits security skills (trailofbits/skills) | selected |
| mcp-surfaces | mcporter; MCP Inspector | selected |
| workers | claude-code (native subagents, worktree isolation, agent teams); Codex native workers (subagents); Worktrunk | selected |
| isolation | sandbox-runtime (srt); Worktrunk; Podman (rootless) | compare the arms on the new WSL |
| code-navigation | Serena; claude-plugins-official (code-intelligence LSP plugins) | selected |
| semantic-rag | SocratiCode; semble; ollama | compare the arms on the new WSL |
| document-retrieval | tobi/qmd; MinerU | selected |
| web-research | trafilatura; Playwright CLI | selected |
| durable-memory | ai-memory; Hindsight; agentmemory (rohitg00); deja-vu | compare the arms on the new WSL |
| token-efficiency | ccusage; rtk-ai/rtk | compare the arms on the new WSL |
| observation-inference | OTel Collector Contrib; Prometheus; Loki; Grafana; llama.cpp optional inference; Phoenix | selected |
| quality-evaluation | Inspect AI; Harbor (containerized agent E2E runner); Promptfoo | selected |
| ci-supply-chain | zizmor; attest; Syft; Dependabot; codeql-sarif; actionlint (kjanat) | selected |
| scheduling-supervision | Dagu; systemd | selected |
| hosting-services | Docker Compose; Podman / Quadlet (engine arm A); Docker Engine / Moby (engine arm B) | compare the arms on the new WSL |
| secrets-credentials | betterleaks; trufflehog | selected |
| git-github-automation | git; gh (GitHub CLI); worktrunk; difftastic; sem (lowest confidence; kept only if the structural-diff comparison shows a gain); claude-code-action | selected |
| recovery-portability | mise; Restic; chezmoi | selected |
| cross:wsl-distro | Ubuntu 26.04.1 LTS (Canonical WSL image), primary; Ubuntu 24.04.5 LTS (Canonical WSL image), fallback | selected |

Each pick's upstream install command and source, its role, the deciding comparison and the critics' checks are in
`evidence/artifacts/new-wsl-clean-install-selection-20261001/selection.json`; the folder's README says where the
full judge and critic returns are kept and why.

## Why this method

The user asked on 2026-10-01 for the best repositories per layer for the clean install, after asking twice why the
architecture still showed the source host's list. The old list carried three advantages for what the host already ran:
its winners column copied the host's pins, the verdict tooling could crown only an adopted candidate, and the challenger
search made each newcomer prove a gap against the pick of record (the design record
`docs/decisions/2026-10-01-u11-merit-neutral-selection.md`, accepted for implementation by both reviewers at revision 4,
`89424e36`). This run removed those advantages without waiting for that tooling:

- **Blind packets.** Each judge read only the layer's requirement, what a deciding comparison would measure, the target
  hosts and the candidates as name and repository, in a seeded shuffle; every candidate on record entered, including the
  2026-09-29 sweep's survivors and the second-family review's selections. Selection words in the requirement texts were
  made neutral (`build_packets.py`, the `NEUTRAL` list).
- **Symmetric evidence.** The project's own receipts and records were excluded, because native runs exist mostly for
  what the source host installed. Judges used upstream public evidence only; comparisons on record entered only where
  every named arm ran.
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
- 7 checked facts did not hold. All are in the judges' reasons; none overturns a pick:
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

## What follows

1. An install profile for the new distribution built from this list: a pinned version and the upstream install command
   for each pick, every arm of the five comparison layers included (program unit U8).
2. The recipe's image choice settled by the rehearsal of both images.
3. Stage 2 on the new distribution, then each comparison layer's preregistered head-to-head.

## Evidence class

Source review by model judges with adversarial checks. No candidate was installed or measured by the run.

## Overturn

A preregistered comparison on the new distribution; a fact a later check finds wrong where a pick rests on it; a new
upstream release or maintenance change that alters a criterion.
