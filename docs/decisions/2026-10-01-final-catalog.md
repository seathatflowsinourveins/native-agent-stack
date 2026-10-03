# The final catalog of 2026-10-01: the blind GPT half of the clean-install selection and its comparison with the Claude record

Lane: shared (foundation content; it lists the trading rows read-only). North-star action served: the evidence behind
the new WSL's definitive round and the finalization board (#140); the clean install itself follows the definitive
manifest. Status: a generated record. It judges nothing, and it is not an install list. Its fold extends the frozen
agreement rule in two places, disclosed below. Revised on 2026-10-02 after the cross-family review of #595 (see
"Revision of 2026-10-02").

## Decision

`catalogs/foundation/final-catalog-20261001.json`, rendered as `docs/final-catalog-20261001.md` by
`scripts/final_catalog.py` and checked in CI (`--check`), is the record of the blind GPT-6.1 Sol half of the
clean-install selection of 2026-10-01 and of its comparison with the blind Claude Opus 5.5 record of the same day
(#589). **It is not an install list.** The install record is the definitive manifest (#602,
`evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`, decided in
`docs/decisions/2026-10-01-new-wsl-definitive-defaults.md`); the generator names that manifest and never reads it, so
`--check` does not depend on it. For each of the 37 rows of the dated edition
(`catalogs/foundation/new-wsl-architecture-20261001.json`: 20 foundation layers, 12 trading layers and 5 cross-cutting
rows) the record carries:

- the source host's selection of record at its pin of record, labelled as bookkeeping (program decision 5,
  `docs/decisions/2026-10-01-definitive-sota-wsl-program.md`), and as an unjudged incumbent where no blind record
  exists; each pin is quoted from the edition without the edition's note on what the new distribution installs, which
  four trading pins carry (DVC, pandera, Inspect AI and MLflow);
- the blind Claude half of #589 and the blind GPT-6.1 Sol half recorded here
  (`evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/`): each half's status, critic verdict and
  picks, with the upstream facts captured for each pick before the GPT run;
- which picks both halves named, which only the Claude half named and which only the GPT half named, and the agreement
  class: the class the generator gives and, next to it, the class that the text of the rule frozen before any GPT
  return existed gives as written (`cross-family/agreement-rule.txt`, in `preregistration-addendum.json`). The record
  carries the rule's sha256, so a change to the rule fails `--check` until the record is regenerated.

A pick both halves named is agreement on source review, not an install decision, and the record schedules no
comparison. The rule's fold (its line 6) attaches install and comparison consequences to each class; the record does
not carry them out. The definitive manifest decides every slot, and its decision can differ from what both halves
named: at #602 (`675bdd51`) it installs nothing yet for durable memory (the memory-owner slot waits for the memory
head-to-head), for code search (split between semble and SocratiCode) or for the agent structural diff (sem not
installed), although both halves named ai-memory, SocratiCode and sem.

Result at main `99d5b122` plus this record, across 37 rows: `same_picks_both_recommended` 2,
`same_picks_split_status` 3, `some_picks_shared` 16, `owner_lane_run_pending` 12 and `no_blind_record` 4. In the 21
judged layers the generator's classes are agree 2 and overlap 19; the rule's text as written gives agree 2, overlap 16,
differ 1 (cross:wsl-distro) and unclassified 2 (document-retrieval and scheduling-supervision). The GPT critics found
source review unable to separate the top candidates in 16 layers. The picks both halves named differ from the source
host's record in 16 rows. No selection of record changes.

| Layer | Class | Named by both halves | Claude half only | GPT half only | Claude Opus 5.5 | GPT-6.1 Sol |
| --- | --- | --- | --- | --- | --- | --- |
| native-clients | `same_picks_both_recommended` (agree) | anthropics/claude-code; openai/codex | — | — | recommended (upheld) | recommended (upheld) |
| instructions-skills | `some_picks_shared` (overlap) | trailofbits/skills | — | mattpocock/skills | recommended (revised) | compare (undetermined) |
| workers | `some_picks_shared` (overlap) | max-sixty/worktrunk; openai/codex | anthropics/claude-code | — | recommended (upheld) | recommended (revised) |
| isolation | `some_picks_shared` (overlap) | anthropics/sandbox-runtime; max-sixty/worktrunk | podman-container-tools/podman | — | compare (undetermined) | recommended (upheld) |
| code-navigation | `some_picks_shared` (overlap) | oraios/serena | anthropics/claude-plugins-official | ast-grep/ast-grep | recommended (revised) | compare (undetermined) |
| document-retrieval | `same_picks_split_status` (overlap; as written: unclassified) | opendatalab/mineru; tobi/qmd | — | — | recommended (upheld) | compare (undetermined) |
| semantic-rag | `some_picks_shared` (overlap) | giancarloerra/socraticode; ollama/ollama | minishlab/semble | qdrant/qdrant | compare (undetermined) | compare (undetermined) |
| durable-memory | `some_picks_shared` (overlap) | akitaonrails/ai-memory | rohitg00/agentmemory; vectorize-io/hindsight; vshulcz/deja-vu | basicmachines-co/basic-memory | compare (undetermined) | compare (undetermined) |
| web-research | `some_picks_shared` (overlap) | microsoft/playwright-cli | adbar/trafilatura | — | recommended (upheld) | compare (undetermined) |
| token-efficiency | `some_picks_shared` (overlap) | ccusage/ccusage | rtk-ai/rtk | mksglu/context-mode; ojuschugh1/sqz | compare (undetermined) | compare (undetermined) |
| quality-evaluation | `some_picks_shared` (overlap) | harbor-framework/harbor; ukgovernmentbeis/inspect_ai | promptfoo/promptfoo | microsoft/playwright | recommended (upheld) | compare (undetermined) |
| ci-supply-chain | `some_picks_shared` (overlap) | actions/attest; anchore/syft; dependabot/dependabot-core; kjanat/actionlint; zizmorcore/zizmor | github/codeql-action | — | recommended (upheld) | compare (undetermined) |
| scheduling-supervision | `same_picks_split_status` (overlap; as written: unclassified) | dagucloud/dagu; systemd/systemd | — | — | recommended (upheld) | compare (undetermined) |
| hosting-services | `some_picks_shared` (overlap) | docker/compose; moby/moby | podman-container-tools/podman | fastapi/fastapi; postgres/postgres | compare (undetermined) | compare (undetermined) |
| recovery-portability | `some_picks_shared` (overlap) | jdx/mise; restic/restic | twpayne/chezmoi | — | recommended (upheld) | compare (undetermined) |
| observation-inference | `some_picks_shared` (overlap) | open-telemetry/opentelemetry-collector-contrib | arize-ai/phoenix; ggml-org/llama.cpp; grafana/grafana; grafana/loki; prometheus/prometheus | openlit/openlit | recommended (upheld) | compare (undetermined) |
| agent-sdks | `same_picks_both_recommended` (agree) | anthropics/claude-agent-sdk-python; openai/codex | — | — | recommended (upheld) | recommended (upheld) |
| mcp-surfaces | `some_picks_shared` (overlap) | modelcontextprotocol/inspector; openclaw/mcporter | — | mcpjam/inspector | recommended (upheld) | recommended (upheld) |
| secrets-credentials | `some_picks_shared` (overlap) | betterleaks/betterleaks | trufflesecurity/trufflehog | — | recommended (upheld) | compare (undetermined) |
| git-github-automation | `some_picks_shared` (overlap) | ataraxy-labs/sem; cli/cli; git/git; max-sixty/worktrunk | anthropics/claude-code-action; wilfred/difftastic | — | recommended (upheld) | compare (undetermined) |
| cross:wsl-distro | `same_picks_split_status` (overlap; as written: differ) | Ubuntu 24.04.5 LTS (Canonical WSL image); Ubuntu 26.04.1 LTS (Canonical WSL image) | — | — | recommended (upheld) | compare (undetermined) |

The 12 trading rows are `owner_lane_run_pending` and the four cross-cutting rows other than the distribution are
`no_blind_record`; their pins of record are unjudged incumbents, not winners. Each half's picks with their captured
facts, the Claude half's comparison arms and the set the rule's fold derives from the two halves are in the JSON record.
Seven rows need a note:

- **durable-memory.** ai-memory is the only memory pick both halves named on source review (Claude: ai-memory,
  Hindsight, agentmemory and deja-vu; GPT: ai-memory and Basic Memory). That is not a merit result: the only
  measurement on record at 2026-10-01 points the other way. LongMemEval-S recall_all@5 on the source host, descriptive
  and without ai-memory's production reranker (C4), gave agentmemory 0.821, BM25 0.747 and ai-memory 0.496
  (`evidence/artifacts/memory-stack-20260925/convergence.json`); Hindsight is unmeasured (K1 has not run). #591 records
  the user's request that the memory head-to-head of #526 decide the memory slot. The pin of record is 2.4.1
  (`manifests/stack.json:96`); upstream released v2.5.2 on 2026-10-01 (`cross-family/facts/durable-memory.json`).
- **token-efficiency.** The only pick both halves named is ccusage, a usage meter rather than a compression tool. No
  compression tool was named by both halves: RTK by the Claude half, Context Mode and sqz by the GPT half.
- **ci-supply-chain.** `github/codeql-action`, named by the Claude half only, is the Claude pick `codeql-sarif`: the
  `upload-sarif` step this repository already runs (`.github/workflows/security-scan.yml:146`) next to CodeQL default
  setup.
- **workers and mcp-surfaces.** Claude Code's native subagents (workers) were named by the Claude half only, and MCPJam
  Inspector (mcp-surfaces) by the GPT half only.
- **git-github-automation.** Both halves named sem, although the Claude pick's own text keeps it "only if the
  structural-diff comparison shows a gain".
- **hosting-services.** The halves read the layer differently: the Claude judges scoped it to the container engine and
  listed Docker Engine as one arm against Podman with Quadlet, while the GPT judge, like the source host's record, also
  picked the application stack (FastAPI, PostgreSQL). Both halves named Docker Compose and Moby; Podman was named by
  the Claude half only, FastAPI and PostgreSQL by the GPT half only.
- **cross:wsl-distro.** Both halves picked both Ubuntu images under the generator's packet matching (the second
  extension below). Compared as written, the Claude names carry the role suffixes ", primary" and ", fallback", so the
  halves share no name and the rule's text classifies the layer as differ. The order (26.04.1 primary, 24.04.5
  fallback) is the Claude judges' alone; the GPT critic found it undetermined. Its one failed fact check refuted its
  own judge's claim that Canonical's listing lacked the 26.04.1 WSL image: the critic found that image, dated
  2026-08-27, with signed checksum files. Neither run downloaded or checksum-tested the bytes. The GPT critic also
  named Debian 13 as possibly stronger, without picking it.

**How the fold extends the frozen rule.** The generator does not apply the frozen rule exactly as written: its fold
extends the rule's text in two places. Every judged row carries both the generator's class (`agreement`) and the class
the text gives as written (`agreement_as_written`), with the extensions that changed it (`extensions_applied`):

1. *Equal pick sets with unequal statuses.* The rule's agree needs equal statuses and its overlap needs unequal sets
   (`agreement-rule.txt`, line 5), so the text leaves the case unclassified. The generator classifies it as overlap
   (`agreement` in `scripts/final_catalog.py`), and the record names the case `same_picks_split_status`. Rows:
   document-retrieval, scheduling-supervision and cross:wsl-distro.
2. *Names matched to packet candidates.* The rule normalizes a pick without a GitHub URL by its name (line 2). The
   generator matches the name to the packet candidate whose words it contains (`pick_key`), which drops a role suffix
   such as ", primary" or ", fallback". Compared as written (lowercase, whitespace collapsed), the two halves share no
   distribution name. Row: cross:wsl-distro.

Reducing a GitHub URL to owner/name is not a third extension: every pick URL in both records is a plain repository URL,
where that reduction equals the rule's literal URL form (a test checks every pick). A Claude arm description names a
pick only through the pick's full owner/name. The earlier whole-word match on the repository name alone would read an
arm `trailofbits/skills` as naming `mattpocock/skills`, but no recorded arm triggered that: the Claude half recorded
no arms for instructions-skills, so neither version of the record dropped `mattpocock/skills`. On the two records, the
change only adds to the derived set eight picks that arms described in words already name: semble (semantic-rag),
agentmemory, Hindsight and deja-vu (durable-memory), RTK, sqz and Context Mode (token-efficiency) and Podman
(hosting-services). Each now appears there twice, as the arm's words and as the pick's owner/name. The record keeps the
derived set for reading the halves side by side; it schedules nothing.

## Revision of 2026-10-02

The cross-family review of #595 (GPT-6.1 Sol, reading `025c4892`) found that the record's claim to apply the rule
exactly as written was false in the two places above, and that its framing conflicted with the merged install
decisions: it made every pick both halves named the layer's pick for the new WSL (a "standing pick") and every pick one
half named a challenger in a measured comparison on the new host, which would have put comparison arms on the clean
WSL and given that status to slots the definitive manifest holds. This revision re-scopes the record as the record of
the blind GPT half and its comparison with the Claude record, with the definitive manifest as the install record. It
removes the install and comparison consequences, the gate ledger, the install commands and the judges'
deciding-comparison texts from the record; discloses the two extensions and reports the class as written; hashes the
rule; matches arm descriptions by full owner/name; and records the timing and inventory limits below. No judgment was
redone and no pick changed.

The review of that revision found two remaining faults, both corrected the same day. Four quoted pins still carried the
edition's note on what the new distribution installs, which for pandera also contradicts the definitive manifest (its
`market-data-validation` slot names Pointblank as the default, still open). The generator now leaves that note out of
every quoted pin, and a test allows install wording in the outputs only in the disclaimers, the pointers to the install
record, file names and the distribution row's title. And the account of the matcher above had claimed that the earlier
matcher dropped `mattpocock/skills`; it never did on the recorded halves, and the paragraph now gives the change's
actual effect.

The reading of the overlap clause had changed once before, also without any judgment redone. The generator's first
version, written while the judges ran and before any critic returned, held the shared picks as comparison arms wherever
either half's critic found the evidence undetermined (17 judged layers). After the results, at the user's direction on
2026-10-01, the second version let the shared picks stand with no status condition and described that reading as the
rule applied as written.

## The cross-family run

- **Inputs.** The frozen criteria, judge prompt, critic prompt and 21 packets of #589, each verified against
  `preregistration.json` by sha256 before the run. Added and frozen first (`preregistration-addendum.json`, recorded
  2026-10-01T20:44:31Z): a harness adapter (`adapter.txt`), output schemas, the packet-to-judge assignment and the
  agreement rule, plus a facts sidecar with the three GitHub API endpoints the judge prompt names for all 209
  candidates, captured without popularity fields (`facts/`). By the coordinator's private run log, the first process
  started five seconds after the addendum was recorded; the committed files cannot show that (see the limits below).
- **Family and dispatch.** GPT-6.1 Sol at `model_reasoning_effort=max` through `codex exec` (Codex CLI 0.159.3, native
  ChatGPT sign-in), read-only sandbox, live web search, ephemeral sessions, schema-bound final message; 11 independent
  judge processes in 3 groups and one critic per group, the original dispatch shape. Every process succeeded on its
  first attempt (14 processes, 14 attempts, no retry).
- **Critic verdicts.** revised 1, undetermined 16, upheld 4. The GPT critics ran 156 fact checks; 1 failed, and it
  refuted a judge's claim: in cross:wsl-distro, judge J11 wrote that Canonical's listing lacked
  `ubuntu-26.04.1-wsl-amd64.wsl`, and critic C-G3 found that image (dated 2026-08-27) with signed checksum files. Every
  judge return names each packet candidate exactly once (the frozen prompt's rule).
- **Blindness, and its limit.** Besides the adapter, the frozen prompts, criteria, packets and facts, every process
  also received the user's global Codex instructions. `codex exec` loads `$CODEX_HOME/AGENTS.md` into the model's
  instructions: a probe on 2026-10-02 returned a canary placed there, and NONE without it
  (`cross-family/instruction-probe.json`). The run used the default `CODEX_HOME`, whose `AGENTS.md` names eight packet
  candidates: ai-memory, Hindsight, SocratiCode, QMD, Playwright CLI, Ollama, Context Mode and ast-grep. The Claude half
  of #589 ran as workflow subagents, which receive the global `CLAUDE.md` (it names the same tools) and the project
  `AGENTS.md` (it names promptfoo, Harbor, Inspect and QMD); #591 recorded the same limit for its round. Agreement on
  the layers those tools belong to (semantic-rag, document-retrieval, web-research, durable-memory, token-efficiency,
  code-navigation and quality-evaluation) is therefore not independent evidence. The definitive round re-judges every
  open slot with both families in a clean room, with no instruction files, hooks or MCP servers. The audit of every
  event stream counts 100 web searches, 160 opened pages and 39 commands, and none of them names the project's
  repositories or a local path outside the inputs (`run-record.json`). The audit sees queries, page actions and
  commands, not the instructions or the content of search results.
- **Timing and inventory: disclosed limits.** Three properties of the run cannot be checked from the committed files:
  - `run-record.json` gives each process attempt's exit, duration and returned usage, but no start or end timestamp.
    The order of the addendum and the processes therefore rests on the coordinator's account.
  - The first process's start, 2026-10-01T20:44:36Z, is stated only in this record and the folder's README. It comes
    from the coordinator's run log, which stays private with the other originals: `run-record.json` lists its sha256,
    not its content. The committed records time only the addendum (`preregistration-addendum.json`, `recorded_at`) and
    the run's finish (`selection-gpt.json`, `run.finished_at`, 2026-10-01T21:58:06Z).
  - The instruction file every process loaded (`$CODEX_HOME/AGENTS.md`, above) is absent from the frozen-input
    inventory of `preregistration-addendum.json`. Its sha256 appears only in the probe of the next day
    (`instruction-probe.json`, `default_home_agents_md_sha256`, recorded 2026-10-02T02:25:00Z), which shows what the
    file held then, not what the run loaded.
- **Usage, as returned by Codex.** 20,644,160 input tokens (18,536,320 cached) and 360,405 output tokens (214,127
  reasoning) across the 14 processes; wall time per process up to 27 minutes. The Claude side of this unit (research
  workflow, verifiers and completeness critic) is reported with the pull request.
- **Deviations from the parent run.** The tool mapping in the adapter (web search for `ctx_fetch_and_index` and
  `ctx_search`; captured GitHub API facts for the three named endpoints); schema-bound output; the coordinator's
  packet-to-judge assignment, since the parent's is not public; and the route: AGENTS.md has cross-family votes run
  through the OmniRoute gateway, while this run used the native Codex client with the model and effort pinned on every
  launch. Codex's delegation to a child agent failed under `--ephemeral` ("no rollout found for thread id") once in
  each of 8 of the 14 processes (judges J02, J03, J06, J07, J08 and J10, critics C-G1 and C-G3); each finished alone,
  and the failure is kept in the private stderr.
- **Private originals.** Prompts, event streams, returns, stderr and the run log stay outside the repository with the
  coordinator's private records; `run-record.json` lists the sha256 of each.

## What the record does not decide

The record decides nothing about installation. A pick both halves named is two-family agreement on source review,
within the limits above; a pick one half named is that half's alone. Whether a slot installs a tool, which tool, and
which comparison backs or overturns that choice are the definitive manifest's decisions. Its decision record runs those
comparisons before the clean install, on the current workstation or on a throwaway rehearsal distribution, and the
clean WSL never installs comparison arms (`docs/decisions/2026-10-01-new-wsl-definitive-defaults.md`, decision 6). The
record never promotes a row by itself, and no selection of record on the source host changes through it.

The six exit criteria of #140 are the acceptance test for the whole catalog. At main `20ea4ae2` one is met (the
`verdict-review-gate` required check), two are partly met (the release pin, and the grid and matrix regeneration) and
three are unmet (a non-grandfathered verdict wave for all 32 layers with no `pending_lanes`, the Linux
`platform_status` derivation from independently reviewed host receipts, and the readiness snapshot). The status of each
criterion, with its evidence, is posted on #140 with this record.

## Gaps that remain

These are the gaps of this record, in the order that unblocks the most. Slot install decisions, and the measurements a
held slot waits for, are the definitive manifest's.

1. **The trading layers.** No blind record exists for the 12 us-equities rows; #589 left the method, unchanged, to the
   trading lane owner on the GPT lane after 2026-10-03T17:14Z.
2. **The cross-cutting rows without a blind record.** Neither half judged them; each pin of record is an unjudged
   incumbent.
   - `cross:runtime-workers`: no frozen candidate set or closure record; the roster README the row cites exists only in
     PR #535; the OpenHands worker on main is configured for `cx/gpt-6-astra-max`
     (`blueprints/runtime-workers/openhands/config/worker.json:8`), a resolved official task exits 2, and the isolation
     probe has not run. Sol executions of the worker candidates are recorded in open PRs (#524 pi, 28 tasks; #551
     Codex SDK worker kit; #566 one OpenHands Sol-Max call) and, since #580, in one native-account turn of the Codex
     Python SDK requested at `gpt-6.1-sol` max, which returned the exact canary marker (the backend model was not
     observed, and the wrapper's exit 1 was corrected offline); the same SDK's attempt through OmniRoute
     (`cx/gpt-6.1-sol-max`) returned HTTP 429, cause unknown, so the gateway route is held
     (`evidence/artifacts/runtime-sdk-20261001/receipt.json`, status `native_account_pair_qualified_gateway_held`).
     AgentRelay and Relaycast have no layer yet.
   - `cross:gpt6-harnesses`: the row cites Codex 0.159.2, main pins 0.159.3 since #580 merged on 2026-10-01, and
     upstream released rust-v0.160.0 the same day. OmniRoute is pinned at 3.8.50; 3.8.51 is npm-qualified as a
     candidate without moving the pin (`evidence/artifacts/omniroute-npm-3851-qualification-20260930/`), and the
     source host runs rebuilt source builds, with Sol's max effort passed through on the running build only
     (`evidence/artifacts/omniroute-sol-max-20260930/`). Sol runs of the Codex CLI lane through OmniRoute are on main
     as reviews and one builder run (#532, #572, #575, #587), not as acceptance of the lane.
   - The GPT-6.1 Sol route of each runtime candidate, as recorded on 2026-10-01 (the routing contract sets Sol at ultra
     for coordination, where ultra is a Codex-client delegation mode that sends `xhigh`, and Sol at max for workers):

     | Candidate | Configured model on record | Sol execution recorded | Where |
     | --- | --- | --- | --- |
     | OpenHands software-agent-sdk | `cx/gpt-6-astra-max` (`blueprints/runtime-workers/openhands/config/worker.json:8`) | one Sol-Max call, 85 tokens | #566 (draft) |
     | Codex Python SDK | `cx/gpt-6-astra-max` in the merged route qualification (#560, `evidence/artifacts/runtime-sdk-20260930/receipt.json:37`); since #580, `gpt-6.1-sol` at max on the native account and `cx/gpt-6.1-sol-max` through OmniRoute (`evidence/artifacts/runtime-sdk-20261001/receipt.json:89,107`) | on main, one native-account turn at Sol/max returned the exact canary marker (19,424 input tokens; backend model not observed), while the OmniRoute attempt returned HTTP 429 (gateway held); in a draft, a Sol/Max parent (153,813 native tokens) with an Astra judge child | #580 (merged); #551 (draft) |
     | pi v0.99.1 | `sharedgw/gpt-6.1-sol` | 28 tasks | #524 (open, decision "trial") |
     | GPT Researcher, DeerFlow, Crawl4AI | Astra arms (`cx/` and `sharedgw/gpt-6-astra-max`) | none; recipes only | #426, #427, #428 (drafts) |
     | Codex CLI lane (stack-worker profile) | `gpt-6.1-sol` at max with live web search | reviews and one builder run through OmniRoute; the lane proof is `none_recorded` | #532, #572, #575, #587 (merged) |
     | Claude Agent SDK | no Sol route recorded | none | — |
     | DeepAgents; the Codex 0.159.3 canary | not stated in the PR bodies | unknown | #566 (draft), #580 (merged) |

   - `cross:credential-practice` and `cross:convergence-practice` are this repository's own practices and carry no
     blind record by design; their gates are the lane owners'.
   - Neither runtime row has a landscape layer, a saturation-ledger entry or a packet, so neither model family has
     judged "GPT-6.1 Sol runtime workers through harness SDKs" yet. A blind record for either row needs a preregistered
     packet first (worker runtimes: OpenHands, GPT Researcher, DeerFlow, Crawl4AI, pi, DeepAgents, Harbor, AgentRelay,
     Relaycast and the 13 unvoted sweep rows below; harnesses and gateways: Codex CLI and SDKs, OmniRoute, LiteLLM,
     claude-code-router, agentgateway), judged by both families with the frozen method.
3. **The field the packets did not hold.** 15 of the 25 survivors of the 2026-09-26 sweep and 266 of the 328 refuted
   layer-repository pairs enter as pending and are voted again under U11 (#589, "Not covered"). This pass's
   completeness critic found more that the packets never held:
   - 13 rows that `catalogs/sota-convergence/sdk-runtime-coverage-20260922.json` rated keep-but-compare or targeted and
     that no ledger sweep ever voted: claude-agent-sdk-typescript, awslabs/cli-agent-orchestrator, github/copilot-cli,
     mini-swe-agent, zeroshot, dbos-transact-ts, inngest, agent-client-protocol, fastmcp, snyk/agent-scan,
     nvidia/openshell, trailofbits/coop and microsoft/conductor (agent-sdks, workers, isolation, mcp-surfaces and
     scheduling-supervision sweeps);
   - 33 proposals of the 2026-09-29 sweep that count as refuted only because the GPT-6 fit vote was missing
     (`evidence/artifacts/landscape-sweep-20260929/returns.json`, `failures`), among them TensorRT-LLM, exo,
     llama-swap, mistral.rs, mlx-lm, docker/mcp-gateway and five supply-chain firewalls, plus the missing GPT-6
     discovery passes for web-research, token-efficiency and recovery-portability; their follow-up round reruns in
     those layers' next sweep;
   - the 13 skills lifecycle tasks of `catalogs/landscape/skills-lifecycle.json`, which no edition row covers beyond
     instructions-skills (the skills sweep, keyed by lifecycle task);
   - the TypeScript SDK dimension (claude-agent-sdk-typescript, openai-agents-js, langgraphjs) and the gateway
     alternatives on record but in no candidate set (LiteLLM, claude-code-router, agentgateway); OmniRoute itself is a
     candidate in no landscape catalog;
   - the owned fork `seathatflowsinourveins/ai-memory`, referenced by no record (`public-owned.json`, 2026-09-20, lists
     one repository), and `NVIDIA/Model-Optimizer` and `microsoft/graphrag`, which appear in no catalog.
   openai-agents-python, adk-python and smolagents have written dispositions in
   `sdk-runtime-coverage-20260922.json` and `catalogs/landscape/foundation.json`; they are re-voted with the rest of the
   field, not added as new.
4. **Record drift for the next edition update** (overturn conditions 2, 3 and 5 of the edition): the agent-sdks row
   cites `openai-codex==0.154.0`, and the rows that pin Codex read 0.159.2 where main pins 0.159.3 (#580); the
   gpt6-harnesses row calls #560 open, and it merged on 2026-10-01; the durable-memory row and `manifests/stack.json:96`
   pin ai-memory 2.4.1, and upstream released v2.5.2 on 2026-10-01; the Next.js pin of record reads 16.3.6 where the
   stack pins 16.3.8 (#587), and #587 shifted later `manifests/stack.json` line citations by one; the trading lane asked
   for its wording correction of the `trading_rule` passage of `ownership.json` (#589 comment, 2026-10-01T19:21Z).
5. **The #140 exit criteria** (see above): the non-grandfathered re-record (program unit U4, foundation), widening
   `ENFORCED_PLATFORMS` (`scripts/landscape.py:51`) after the four Linux overclaims clear, regenerating the grid and
   matrix from the new wave, a release (main is about 200 commits past v2026.09.26.2 and `release_due --strict` exits
   1), and the readiness snapshot (agent-lab #29 is merged and dated v2026.09.24.1).

## Alternatives

- **Merge the ranked catalog index of #515.** Its first ranking key orders entries by recorded role, winner first
  (`scripts/catalog_index.py:206` at `3d4a9510`). U11 gives the selection of record no precedence in selection, ties or
  arm order (`docs/decisions/2026-10-01-u11-merit-neutral-selection.md:123`), and program decision 5 treats the source
  host's bookkeeping as no evidence. #515 stays open for its owner to re-key or close; this record does not depend on it.
- **Extend `scripts/new_host_grand_list.py`.** Its scope is the 32 catalog layers without the cross-cutting rows, and it
  is regenerated whenever a receipt lands; a merit join inside it would churn with every receipt and would mix the
  source host's E2E bookkeeping with merit status.
- **Add merit fields to the edition's rows.** The edition is a hand-maintained dated record whose winners column is
  defined as bookkeeping; generated merit data inside it would blur that definition and could drift from the blind
  records. A generated sibling with `--check` keeps both exact.
- **Join the definitive manifest into this record.** It would print each slot's install decision beside the two
  halves, but it would couple `--check` to the manifest, which changes with every settlement, and would make this
  record a second install list. The record names the manifest and never reads it.
- **Classify by the rule's text alone.** The text leaves two layers unclassified and reads the halves' identical
  distribution images as different names. The record keeps the generator's class, discloses the two extensions and
  shows the class as written beside it.

## Overturn

Regenerate with `python3 scripts/final_catalog.py --write` and re-read the classes when any of these happens: a new
edition or an update of this one; a change to `selection.json`, the cross-family record, the agreement rule or the
captured facts; the trading lane's blind run on the 12 us-equities layers; a blind run for the four cross-cutting rows;
a fact a later check finds wrong where a pick rests on it. A move of the grand list alone shows as drift in `--check`.
Install decisions change only through the definitive manifest.

## Evidence class

The classes are a deterministic join (`structural_validation`) of two `source_review` records by model judges with
adversarial critics in two model families, whose instructions named some candidates (see "Blindness, and its limit").
Neither run installed or measured a candidate, and the source host's records were excluded from both. The record
carries no install, acceptance or comparison evidence.

## SOTA sources

- Generator contract and conventions: the in-repository reference implementation `scripts/new_host_grand_list.py`
  and `tests/test_new_host_grand_list.py` at `20ea4ae2` (`--check`/`--write`, JSON plus Markdown, the
  `PRIVATE_CONTENT` guard and `host_receipts.register_file`).
- Merit-neutral blind selection: `docs/decisions/2026-10-01-u11-merit-neutral-selection.md` (revision 4, `89424e36`)
  and the frozen criteria, prompts and packets of #589.
- Judge bias controls: Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" (arXiv:2306.05685v4) on
  position, verbosity and self-preference bias, answered by blind packets, seeded candidate order and a second model
  family; OpenAI, "Evaluation best practices"
  (https://developers.openai.com/api/docs/guides/evaluation-best-practices).
- Cross-family execution: openai/codex `codex exec` at 0.159.3 (`--output-schema`, `--json`, `-s read-only`,
  `--ephemeral`) and the routing contract `docs/decisions/2026-09-30-sol-primary-quality-defaults.md`.
