# The final catalog of the new-WSL architecture (2026-10-01)

Lane: shared (foundation content; it lists the trading rows read-only). North-star action served: the clean install of
the new WSL distribution and the finalization board (#140). Status: a generated record. It judges nothing; it applies
the frozen agreement rule as written.

## Decision

`catalogs/foundation/final-catalog-20261001.json`, rendered as `docs/final-catalog-20261001.md` by
`scripts/final_catalog.py` and checked in CI (`--check`), is the one final list for the new WSL. For each of the 37
rows of the dated edition (`catalogs/foundation/new-wsl-architecture-20261001.json`: 20 foundation layers, 12 trading
layers and 5 cross-cutting rows) it carries:

- the source host's selection of record at its pin of record, labelled as bookkeeping (program decision 5,
  `docs/decisions/2026-10-01-definitive-sota-wsl-program.md`), and as an unjudged incumbent where no blind record
  exists;
- the blind clean-install recommendation of #589 (Claude Opus 5.5) and its cross-family counterpart, the blind
  GPT-6.1 Sol run recorded here (`evidence/artifacts/new-wsl-clean-install-selection-20261001/cross-family/`);
- the standing picks and status that the agreement rule gives, frozen before any GPT return existed
  (`cross-family/agreement-rule.txt`, in `preregistration-addendum.json` at 2026-10-01T20:44:31Z, committed as a
  scanner-safe rendering that carries the recorded file's sha256): every pick both families made stands as the layer's
  pick for the new WSL, and every pick only one family made is a challenger in the layer's measured comparison;
- a gate ledger: the edition's gates and closure gaps, plus the gates that make each standing pick final.

Result at main `85543efe` plus this record, across 37 rows: `two_family_pick` 2, `shared_pick` 3,
`partial_comparison` 16, `owner_lane_run_pending` 12 and `no_blind_record` 4. All 21 judged layers have standing
picks: the two families agree exactly on 2, overlap on 19 and differ on none. The GPT critics found source review
unable to separate the top candidates in 16 layers; under the rule that leaves the picks both families made standing
and sends the rest to each layer's measured comparison as challengers. The standing picks differ from the source
host's record in 16 rows. No selection of record changes.

| Layer | Status | Standing picks (both families) | Challengers (one family) | Claude Opus 5.5 | GPT-6.1 Sol |
| --- | --- | --- | --- | --- | --- |
| native-clients | `two_family_pick` | anthropics/claude-code, openai/codex | — | recommended: anthropics/claude-code, openai/codex | recommended (upheld): openai/codex, anthropics/claude-code |
| instructions-skills | `partial_comparison` | trailofbits/skills | mattpocock/skills | recommended: trailofbits/skills | compare (undetermined): mattpocock/skills, trailofbits/skills |
| workers | `partial_comparison` | max-sixty/worktrunk, openai/codex | anthropics/claude-code | recommended: anthropics/claude-code, openai/codex, max-sixty/worktrunk | recommended (revised): openai/codex, max-sixty/worktrunk |
| isolation | `partial_comparison` | anthropics/sandbox-runtime, max-sixty/worktrunk | podman-container-tools/podman | compare: anthropics/sandbox-runtime, max-sixty/worktrunk, podman-container-tools/podman | recommended (upheld): max-sixty/worktrunk, anthropics/sandbox-runtime |
| code-navigation | `partial_comparison` | oraios/serena | anthropics/claude-plugins-official, ast-grep/ast-grep | recommended: oraios/serena, anthropics/claude-plugins-official | compare (undetermined): ast-grep/ast-grep, oraios/serena |
| document-retrieval | `shared_pick` | opendatalab/mineru, tobi/qmd | — | recommended: tobi/qmd, opendatalab/mineru | compare (undetermined): tobi/qmd, opendatalab/mineru |
| semantic-rag | `partial_comparison` | giancarloerra/socraticode, ollama/ollama | minishlab/semble, qdrant/qdrant | compare: giancarloerra/socraticode, minishlab/semble, ollama/ollama | compare (undetermined): giancarloerra/socraticode, qdrant/qdrant, ollama/ollama |
| durable-memory | `partial_comparison` | akitaonrails/ai-memory | basicmachines-co/basic-memory, rohitg00/agentmemory, vectorize-io/hindsight, vshulcz/deja-vu | compare: akitaonrails/ai-memory, vectorize-io/hindsight, rohitg00/agentmemory, vshulcz/deja-vu | compare (undetermined): akitaonrails/ai-memory, basicmachines-co/basic-memory |
| web-research | `partial_comparison` | microsoft/playwright-cli | adbar/trafilatura | recommended: adbar/trafilatura, microsoft/playwright-cli | compare (undetermined): microsoft/playwright-cli |
| token-efficiency | `partial_comparison` | ccusage/ccusage | mksglu/context-mode, ojuschugh1/sqz, rtk-ai/rtk | compare: ccusage/ccusage, rtk-ai/rtk | compare (undetermined): mksglu/context-mode, ojuschugh1/sqz, ccusage/ccusage |
| quality-evaluation | `partial_comparison` | harbor-framework/harbor, ukgovernmentbeis/inspect_ai | microsoft/playwright, promptfoo/promptfoo | recommended: ukgovernmentbeis/inspect_ai, harbor-framework/harbor, promptfoo/promptfoo | compare (undetermined): ukgovernmentbeis/inspect_ai, harbor-framework/harbor, microsoft/playwright |
| ci-supply-chain | `partial_comparison` | actions/attest, anchore/syft, dependabot/dependabot-core, kjanat/actionlint, zizmorcore/zizmor | github/codeql-action | recommended: zizmorcore/zizmor, actions/attest, anchore/syft, dependabot/dependabot-core, github/codeql-action, kjanat/actionlint | compare (undetermined): actions/attest, zizmorcore/zizmor, kjanat/actionlint, anchore/syft, dependabot/dependabot-core |
| scheduling-supervision | `shared_pick` | dagucloud/dagu, systemd/systemd | — | recommended: dagucloud/dagu, systemd/systemd | compare (undetermined): dagucloud/dagu, systemd/systemd |
| hosting-services | `partial_comparison` | docker/compose, moby/moby | fastapi/fastapi, podman-container-tools/podman, postgres/postgres | compare: docker/compose, podman-container-tools/podman, moby/moby | compare (undetermined): moby/moby, docker/compose, fastapi/fastapi, postgres/postgres |
| recovery-portability | `partial_comparison` | jdx/mise, restic/restic | twpayne/chezmoi | recommended: jdx/mise, restic/restic, twpayne/chezmoi | compare (undetermined): jdx/mise, restic/restic |
| observation-inference | `partial_comparison` | open-telemetry/opentelemetry-collector-contrib | arize-ai/phoenix, ggml-org/llama.cpp, grafana/grafana, grafana/loki, openlit/openlit, prometheus/prometheus | recommended: open-telemetry/opentelemetry-collector-contrib, prometheus/prometheus, grafana/loki, grafana/grafana, ggml-org/llama.cpp, arize-ai/phoenix | compare (undetermined): open-telemetry/opentelemetry-collector-contrib, openlit/openlit |
| agent-sdks | `two_family_pick` | anthropics/claude-agent-sdk-python, openai/codex | — | recommended: anthropics/claude-agent-sdk-python, openai/codex | recommended (upheld): openai/codex, anthropics/claude-agent-sdk-python |
| mcp-surfaces | `partial_comparison` | modelcontextprotocol/inspector, openclaw/mcporter | mcpjam/inspector | recommended: openclaw/mcporter, modelcontextprotocol/inspector | recommended (upheld): openclaw/mcporter, modelcontextprotocol/inspector, mcpjam/inspector |
| secrets-credentials | `partial_comparison` | betterleaks/betterleaks | trufflesecurity/trufflehog | recommended: betterleaks/betterleaks, trufflesecurity/trufflehog | compare (undetermined): betterleaks/betterleaks |
| git-github-automation | `partial_comparison` | ataraxy-labs/sem, cli/cli, git/git, max-sixty/worktrunk | anthropics/claude-code-action, wilfred/difftastic | recommended: git/git, cli/cli, max-sixty/worktrunk, wilfred/difftastic, ataraxy-labs/sem, anthropics/claude-code-action | compare (undetermined): git/git, max-sixty/worktrunk, cli/cli, ataraxy-labs/sem |
| cross:wsl-distro | `shared_pick` | Ubuntu 24.04.5 LTS (Canonical WSL image), fallback, Ubuntu 26.04.1 LTS (Canonical WSL image), primary | — | recommended: Ubuntu 26.04.1 LTS (Canonical WSL image), primary, Ubuntu 24.04.5 LTS (Canonical WSL image), fallback | compare (undetermined): Ubuntu 24.04.5 LTS (Canonical WSL image), Ubuntu 26.04.1 LTS (Canonical WSL image) |

The 12 trading rows are `owner_lane_run_pending` and the four cross-cutting rows `no_blind_record`; their pins of record
are unjudged incumbents, not winners. Each row's comparison arms and full gate ledger are in the record. Seven rows read
differently from their label:

- **durable-memory.** ai-memory is the only memory pick both families made on source review (Claude: ai-memory,
  Hindsight, agentmemory and deja-vu; GPT: ai-memory and Basic Memory), so the rule makes it the standing pick, not a
  default. The only measurement on record points the other way: LongMemEval-S recall_all@5 on the source host,
  descriptive and without ai-memory's production reranker (C4), gave agentmemory 0.821, BM25 0.747 and ai-memory
  0.496 (`evidence/artifacts/memory-stack-20260925/convergence.json`); Hindsight is unmeasured (K1 has not run). #591
  records the user's request that the memory head-to-head of #526 decide and that its best-scoring eligible system be
  installed, so memory's install waits for that comparison, with the memory gaps of item 1 below. The pin of record is
  2.4.1 (`manifests/stack.json:96`); upstream released v2.5.2 on 2026-10-01 (`cross-family/facts/durable-memory.json`).
- **token-efficiency.** The only shared pick is ccusage, a usage meter rather than a compression tool. No compression
  tool has both families behind it: RTK (Claude), Context Mode and sqz (GPT) are challengers, and the compression slot
  stays the no-compression baseline until the Gate A E2E measures one.
- **ci-supply-chain.** The challenger `github/codeql-action` is the Claude pick `codeql-sarif`: the `upload-sarif`
  step this repository already runs (`.github/workflows/security-scan.yml:146`) next to CodeQL default setup, so it
  needs no stage-2 comparison.
- **workers and mcp-surfaces.** Claude Code's native subagents and MCPJam Inspector were picks of one family only, so
  each is a challenger (a with/without arm).
- **git-github-automation.** sem stands under the rule, although the Claude pick's own text keeps it "only if the
  structural-diff comparison shows a gain"; that comparison is its first gate.
- **hosting-services.** The families read the layer differently: the Claude judges scoped it to the container engine
  and listed Docker Engine as one arm against Podman with Quadlet, while the GPT judge, like the source host's record,
  also picked the application stack (FastAPI, PostgreSQL). Docker Compose and Moby stand; Podman, FastAPI and
  PostgreSQL are challengers, and the comparison's preregistration settles the layer's scope before its arms run.
- **cross:wsl-distro.** Both families picked both Ubuntu images, so both stand. The order (26.04.1 primary, 24.04.5
  fallback) is the Claude judges' alone; the GPT critic found it undetermined. Its one failed fact check refuted its
  own judge's claim that Canonical's listing lacked the 26.04.1 WSL image: the critic found that image, dated
  2026-08-27, with signed checksum files. Neither run downloaded or checksum-tested the bytes. The rehearsal that #589
  plans compares the two images; the GPT critic also named Debian 13 as possibly stronger, a question for that
  rehearsal's preregistration rather than a pick.

**How the rule is read, and when that changed.** The overlap clause ("the shared picks stand and every pick only one
family made enters the layer's comparison") names no status condition; the rule attaches one only to its agree clause.
The generator's first version, written while the judges ran and before any critic returned, added one: where either
family's critic found the evidence undetermined, it held the shared picks as comparison arms, which left 17 judged
layers with no standing pick. After the results, at the user's direction on 2026-10-01, the generator applies the
clause as written. No judgment was redone and no pick changed; only the reading of the frozen text did. The two
readings differ in labels more than in work, since stage 2 installs every arm of a comparison layer either way (#589,
"What follows"); what changes is that the standing picks install as each layer's default on the new WSL (memory excepted, above)
while the comparison runs. Two cases
the frozen definitions leave open are disclosed. Equal pick sets with unequal statuses (document-retrieval,
scheduling-supervision and cross:wsl-distro) match neither agree, which needs equal statuses, nor overlap, which needs
unequal sets; the generator classifies them as overlap, so their picks stand with nothing left to compare
(`shared_pick`). And agreement on a comparison keeps a layer without a standing pick, while an overlap keeps its shared
picks standing whatever the statuses; no layer is in the first case. The tests encode each branch of the rule.

## The cross-family run

- **Inputs.** The frozen criteria, judge prompt, critic prompt and 21 packets of #589, each verified against
  `preregistration.json` by sha256 before the run. Added and frozen first (`preregistration-addendum.json`, recorded
  2026-10-01T20:44:31Z, five seconds before the first process): a harness adapter (`adapter.txt`), output schemas, the
  packet-to-judge assignment and the agreement rule, plus a facts sidecar with the three GitHub API endpoints the
  judge prompt names for all 209 candidates, captured without popularity fields (`facts/`).
- **Family and dispatch.** GPT-6.1 Sol at `model_reasoning_effort=max` through `codex exec` (Codex CLI 0.159.3, native
  ChatGPT sign-in), read-only sandbox, live web search, ephemeral sessions, schema-bound final message; 11 independent
  judge processes in 3 groups and one critic per group, the original dispatch shape. Every process succeeded on its
  first attempt (14 processes, 14 attempts, no retry).
- **Critic verdicts.** revised 1, undetermined 16, upheld 4. The GPT critics ran 156 fact checks; 1 failed, and it
  refuted a judge's claim: in cross:wsl-distro, judge J11 wrote that Canonical's listing lacked
  `ubuntu-26.04.1-wsl-amd64.wsl`, and critic C-G3 found that image (dated 2026-08-27) with signed checksum files. Every
  judge return names each packet candidate exactly once (the frozen prompt's rule).
- **Blindness.** The processes received only the adapter, the frozen prompts, criteria, packets and facts. The audit
  of every event stream counts 100 web searches, 160 opened pages and 39 commands; none of them names the project's
  repositories or a local path outside the inputs (`run-record.json`). The audit sees queries, page actions and
  commands, not the content of search results.
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
- **Private originals.** Prompts, event streams, returns and stderr stay outside the repository with the coordinator's
  private records; `run-record.json` lists the sha256 of each.

## What final means here

A layer's standing picks are the picks both model families made blind, and they are its picks for the new WSL clean
install. A standing pick is final once it installs by its upstream command and passes acceptance on the new host
(`two_family_pick`, `shared_pick`) and, where challengers exist (`partial_comparison`), once the layer's measured
comparison has run there (the stage-2 comparison of program decision 5): its preregistered result decides whether a
challenger replaces a standing pick or joins the standing picks. A row without a blind record has no
standing pick until both families judge it. The record never promotes a row by itself: a status changes only through
the frozen rule, a measured comparison on the new host, or a new edition, and no selection of record on the source
host changes through it.

The six exit criteria of #140 are the acceptance test for the whole catalog. At main `20ea4ae2` one is met (the
`verdict-review-gate` required check), two are partly met (the release pin, and the grid and matrix regeneration) and
three are unmet (a non-grandfathered verdict wave for all 32 layers with no `pending_lanes`, the Linux
`platform_status` derivation from independently reviewed host receipts, and the readiness snapshot). The status of each
criterion, with its evidence, is posted on #140 with this record.

## Gaps that remain

The gate ledger of each row in the record is the exact list; these are the gaps that span rows, in the order that
unblocks the most.

1. **Stage-2 comparisons on the new WSL.** Every `partial_comparison` row installs its standing picks and its
   challengers fresh and runs a preregistered comparison whose result decides whether a challenger replaces or joins the
   standing picks (program decision 5). Order constraints from #589: semantic-rag runs before the
   local-model-server comparison in observation-inference, and the container engine in hosting-services runs before
   isolation's container slot. For durable-memory, S3 is not frozen (#526, r7 draft); no result is recorded on any host
   for ai-memory with its reranker (C4), agentmemory through its hooks (D2h), Hindsight (K1) or MemPalace (M1/M2); the
   confirmatory gates name the retired VelaNext host, so a surviving host is preregistered first
   (`docs/decisions/2026-09-25-retire-vela-velanext.md`); the frozen LongMemEval harness runs only in an isolated
   runner. Token efficiency is decided by the Gate A E2E.
2. **The trading layers.** No blind record exists for the 12 us-equities rows; the trading lane owner runs the method
   unchanged on the GPT lane after 2026-10-03T17:14Z (#589).
3. **The cross-cutting rows without a blind record.** None of them has a standing pick; each pin of record is an
   unjudged incumbent.
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
     judged "GPT-6.1 Sol runtime workers through harness SDKs" yet. The next step is a preregistered packet for each row
     (worker runtimes: OpenHands, GPT Researcher, DeerFlow, Crawl4AI, pi, DeepAgents, Harbor, AgentRelay, Relaycast and
     the 13 unvoted sweep rows above; harnesses and gateways: Codex CLI and SDKs, OmniRoute, LiteLLM, claude-code-router,
     agentgateway), judged by both families with the frozen method.
4. **New-host acceptance for every standing pick.** Neither run installed or measured a candidate; each standing pick
   installs by its upstream command on the new distribution and records its acceptance there.
5. **The field the packets did not hold.** 15 of the 25 survivors of the 2026-09-26 sweep and 266 of the 328 refuted
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
6. **Record drift for the next edition update** (overturn conditions 2, 3 and 5 of the edition): the agent-sdks row
   cites `openai-codex==0.154.0`, and the rows that pin Codex read 0.159.2 where main pins 0.159.3 (#580); the
   gpt6-harnesses row calls #560 open, and it merged on 2026-10-01; the durable-memory row and `manifests/stack.json:96`
   pin ai-memory 2.4.1, and upstream released v2.5.2 on 2026-10-01; the Next.js pin of record reads 16.3.6 where the stack pins 16.3.8 (#587), and #587 shifted later
   `manifests/stack.json` line citations by one; the trading lane asked for its wording correction of the
   `trading_rule` passage of `ownership.json` (#589 comment, 2026-10-01T19:21Z).
7. **The #140 exit criteria** (see above): the non-grandfathered re-record (program unit U4, foundation), widening
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

## Overturn

Regenerate with `python3 scripts/final_catalog.py --write` and re-read the statuses when any of these happens: a new
edition or an update of this one; a change to `selection.json` or the cross-family record; the trading lane's blind run
on the 12 us-equities layers; a blind run for the four cross-cutting rows; a stage-2 comparison result on the new host;
a fact a later check finds wrong where a pick rests on it. A move of the grand list alone shows as drift in `--check`.

## Evidence class

The statuses and standing picks are a deterministic join (`structural_validation`). The picks they join are
`source_review` by model judges with adversarial critics in two model families, so a standing pick rests on blind
two-family convergence alone: neither run installed or measured a candidate, and the source host's records were
excluded from both. Install and comparison evidence on the new host is still owed for every row.

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
