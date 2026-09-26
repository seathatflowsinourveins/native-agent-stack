# Landscape sweep, 2026-09-26

This directory keeps the evidence of the 2026-09-26 landscape sweep over all 32 layers (20 foundation, 12
us-equities), Workflow run `wf_8397ada1-777`. Its ledger record is `landscape-sweep-20260926` in
[`catalogs/saturation/ledger.json`](../../../catalogs/saturation/ledger.json). Its lane is `landscape-sweep-20260926` in
[`catalogs/sota-convergence/manifest-20260926.json`](../../../catalogs/sota-convergence/manifest-20260926.json). The
earlier attempts are in [`../landscape-sweep-20260926-attempts/`](../landscape-sweep-20260926-attempts/).

**Evidence class.** This directory holds discovery proposals, refuter votes and upstream source reviews. Nothing was
installed, run or benchmarked, and no winner changed. Winner pins move only through the verdict wave, which the
coordinator owns and will run from this manifest.

## What ran

The run used the 2026-09-26 scratchpad prototype of the lane. The same lane is now packaged as
[`tools/sota-convergence/landscape-sweep/`](../../../tools/sota-convergence/landscape-sweep/README.md) (#324). The
run's `prompts_sha256` is `3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4`, the sha256 of the
prototype's staged templates. The packaged templates, filled with this run's values, give the same hash (a local check
in `tests/test_landscape_sweep_harness.py`). The packaged tools produced the returns, lanes, layers, usage records,
manifest and source reviews. `tavily-leads.json`, the lead-vetting addendum `tavily-leads-vetting.json` and the
attempts' compact records were written for this record, and each states its method.

| Run | Window (UTC) | Outcome |
| --- | --- | --- |
| `wf_1753e674-5dc` | 01:36 to 02:06 | one-layer smoke (mcp-surfaces), completed; retained as an attempt, not a ledger record |
| `wf_a874897e-af1` | 02:07 to 02:22 | stopped (run 1); ledger record `landscape-sweep-20260926-attempt-1` |
| `wf_8397ada1-777` | 02:23 to 12:51 | completed; this directory and ledger record `landscape-sweep-20260926` |

| Label | Model (requested, resolved) | Effort | Children |
| --- | --- | --- | --- |
| `discover:<layer>` | opus, claude-opus-5-5 | max | 40 (32 first-round, 8 follow-up) |
| `gpt6-discover:<layer>` | sonnet wrapper, claude-sonnet-5; runs gpt-6-astra through the Codex CLI | max; GPT-6 max | 40 |
| `refute-facts:<layer>` | sonnet, claude-sonnet-5 | max | 40 |
| `refute-fit:<layer>` | opus, claude-opus-5-5 | max | 40 |
| `gpt6-refute-fit:<layer>` | sonnet wrapper, claude-sonnet-5; runs gpt-6-astra through the Codex CLI | max; GPT-6 max | 40 |
| `critic` | opus, claude-opus-5-5 | max | 1 |

The usage record shows every child at effort max, with three exceptions. Three workers ran their remaining turns at
effort low after they loaded the pinned `property-based-testing` skill, whose frontmatter sets `effort: low`. Each of
those workers is a retained failure of its layer.

A candidate survives only when the facts refuter and both fit refuters (Claude and GPT-6) vote not refuted. The
counts:

- **Proposals.** 287, merged per round and capped at 8.
- **Survivors.** 56 survivals of 54 repositories. `betterleaks/betterleaks` and `csingley/ibflex` each survived in
  two layers.
- **Critic.** The critic returned and flagged 8 layers, the cap. All 8 follow-up rounds returned; no round was lost
  and no layer was excluded.
- **GPT-6 jobs.** 64 of 80 returned output. Each of those 64 outputs matches the file Codex wrote (copy check:
  `match` 64). The 16 failures are explained under the lane limits, and `gpt6-jobs.json` keeps each job's timeline.
- **Discovery calls.** These counts cover discovery only, as each worker reported them. Claude: 170 web searches,
  240 page fetches and 1,004 GitHub API calls. GPT-6: 396, 264 and 748. The Claude web search figure counts capped
  calls as searches. Measured from the transcripts, Claude discovery made 169 WebSearch calls: 154 returned results
  and 15 were capped (see [WebSearch session cap](#websearch-session-cap)). The GPT-6 searches used Codex's cached
  web index, not the live web (see [GPT-6 cached web search](#gpt-6-cached-web-search)).
- **WebSearch cap.** From 04:10:13Z the session's WebSearch cap refused every Claude WebSearch call: 46 of this
  run's 200, in 30 workers. Every layer is reopened for it, so no layer counts as clean.

## Measured usage

The two kinds of counters below are never summed.

**Claude.** The source is `child-usage-wf_8397ada1-777.json` in the attempts directory. It was measured with
`child-usage.mjs` at tool commit `7760b1da` (sha256 `85b95813…730d`), which keeps a superseded attempt's
usage-integrity failures (the third review round, under Files). The three usage records were re-measured
together at that commit, and each `child_usage` is identical to the earlier measurement at `1bd2416b`
(sha256 `d60d1df4…e056`): none of this run's 8 superseded attempts holds usage that the totals cannot count, so the
status stays `complete`. `1bd2416b` had added the per-child WebSearch count (`web_search`) and left every usage
figure as the measurement at `23b2ab06` gave it.

| Resolved model | Attempts | Input | Output | Cache read | Cache creation |
| --- | --- | --- | --- | --- | --- |
| claude-opus-5-5 | 84 | 7,528 | 7,594,754 | 468,125,763 | 15,375,728 |
| claude-sonnet-5 | 125 | 2,208 | 3,948,438 | 74,707,158 | 16,719,155 |
| `<synthetic>` | 8 | 0 | 0 | 0 | 0 |

The attempts are the 201 children plus 8 superseded attempts. The Workflow paused at a Claude usage limit, and after
the reset it re-ran 8 waiting refuter calls under the same call keys. The first attempts of those calls returned
nothing; `superseded_attempts` lists them, and their usage still counts. The `<synthetic>` rows are the notices the
client wrote for those attempts, and they name no model. The record is `complete`. `child-usage.mjs` exited 1 only
because of the three effort deviations, and each deviation is recorded as a retained failure.

**GPT-6.** The source is `returns.json` `gpt6_usage` (Codex counters).

- **Jobs.** 80 in total: 64 `ok`, 8 `failed_exit_null`, 6 `failed_exit_3` and 2 `failed_exit_1`. The runner kept no
  earlier attempts.
- **Usage.** Input 54,799,666 (cached 47,413,760; cache write 0). Output 832,174 (reasoning 556,333).
- **Unreported jobs.** 16 jobs reported no usage. Two of them ran until the Codex usage-limit error, so their use is
  not in these figures.

## WebSearch session cap

Claude Code allows one session at most `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` WebSearch calls, 200 by default.
The count covers the main conversation and every subagent, workflow children included. A capped call is not an
error: it returns a notice that tells the worker to go on with what it has and not to search again (tools
reference, ["Session search limit"](https://code.claude.com/docs/en/tools-reference#session-search-limit), read
2026-09-26). The coordinator session ran with the default. The 2.1.283 client that wrote every capped row has the
same default.

**Where the budget went.** The session's four workflow runs of 2026-09-26 made exactly 200 WebSearch calls that
returned results, between 01:45Z and 04:08Z:

- the smoke `wf_1753e674-5dc`: 1;
- run 1 `wf_a874897e-af1`: 25;
- the session's separate workflow `wf_9dec7824-293`: 20;
- this run: 154.

The first two counts are in the attempts' usage records. The third was counted from that run's transcripts for this
record and is not retained here. The session's 10 WebSearch calls of 2026-09-25 did not count toward the cap. The
documented reset is `/clear`, and the client keeps the count in its process; the transcripts do not show which
reset applied.

**When and whom it capped.** The first capped call was at 04:10:13Z (`discover:agents-models-workers`) and the last
at 11:55:57Z (`refute-fit:execution-broker:followup`). In between, 46 of this run's 200 WebSearch calls were capped,
in 30 workers. The usage record counts each worker's calls and capped calls (`web_search`):

| Role | WebSearch calls | Capped | Workers capped |
| --- | --- | --- | --- |
| first-round discovery | 158 | 4 | 3 of 32 |
| follow-up discovery | 11 | 11 | 7 of 8 |
| facts refuters | 17 | 17 | 8 of 40 |
| Claude fit refuters | 12 | 12 | 11 of 40 |
| critic | 2 | 2 | 1 of 1 |

No WebSearch call of a Claude refuter, a follow-up discovery worker or the critic returned results. 42 of the 43
facts-refuter attempts, 42 of the 43 Claude fit-refuter attempts, the critic (10:55Z to 11:26Z) and all 8 follow-up
discovery workers started after 04:10:13Z. The refuters that made no WebSearch call never met the notice. The GPT-6
lanes search through Codex, outside this cap, but only in Codex's cached mode (see
[GPT-6 cached web search](#gpt-6-cached-web-search)).

**Votes.** Ten vote reasonings mention the cap:

- **One decides on it.** The identity-provenance facts refuter refuted `databento/databento-python`
  (`returns.json#/votes/identity-provenance/3/facts`, confidence 0.45). Its page fetch of the corporate-actions
  documentation returned nothing usable, its WebSearch call was capped, and its rule refutes an unverified claim
  central to the demonstrated gap. The same repository survived in market-data-reference.
- **Eight name a check the refuter could not make** and decide on other evidence.
- **One discusses a candidate's own handling of the cap** (tavily-ai/skills in instructions-skills).

**How the record treats it.** Every capped worker is a `web_search_capped` retained failure of its layer, which
reopens the layer. 16 layers have a capped worker of their own. The critic's capped calls count for every layer, as
its effort deviation would. Its two capped searches concerned DCGM on WSL2 and OpenFIGI, but the notice told it to
stop searching, so it judged every layer's completeness without search. As a result, every layer is reopened and no
layer counts as clean. Before this repair, `agent-sdks`, `backtesting-engine` and `token-efficiency` derived a clean
count of 1:

- `agent-sdks` has its own capped worker: its Claude fit refuter's only WebSearch call was capped at 06:45Z.
- `backtesting-engine` and `token-efficiency` reopen through the critic alone.

The refuters judged every survivor without search results. The verdict wave that starts from this manifest should
not read those votes as search-verified. The harness README (Coordination) now says how to raise the cap before a
full sweep. The lane's budgets allow 1,120 Claude searches (40 × 12 discovery, 80 × 8 refutation).

## GPT-6 cached web search

Every GPT-6-Astra lane of this run, discovery and fit, searched Codex's cached web index, not the live web (lane
limit 11).

- **The runner's command.** The prototype runner started each job as `codex --search exec`. Its script stays in the
  coordinator's private work directory. The script file's timestamps show that the version with that line was in use
  from 05:42:45Z until 16:36:56Z, when the line became `codex exec ... -c web_search="live"`. The version before
  05:42:45Z is not retained; the table below shows that exec searches cached with or without `--search`.
- **What `--search` does to `exec`.** The Codex qualification of 2026-09-26 (#332) measured three cases on Codex
  0.155.1 and 0.157.1 against a local stand-in provider
  ([`websearch-0.155.1.json`](../sota-refresh-20260926/codex/results/websearch-0.155.1.json),
  [`websearch-0.157.1.json`](../sota-refresh-20260926/codex/results/websearch-0.157.1.json)). Both versions behave
  the same, and the run's returns do not record which one ran.

| Case | Command | `external_web_access` in each search request |
| --- | --- | --- |
| W1 | `codex --search exec ...` | false |
| W2 | `codex exec ...` | false |
| W3 | `codex exec -c web_search="live" ...` | true |

A top-level `--search` does not reach `exec`, which keeps its default cached mode. That the OpenAI provider behaves
the same rests on source reading, as the
[qualification receipt](../../receipts/codex-01571-qualification-20260926.json) states, not on a live measurement.
On 2026-09-26 the coordinator observed a real `codex` 0.157.1 `exec` with `-c web_search="live"` make a live search.
That observation is not retained.

**Consequence.** GPT-6 discoveries and votes rested on the provider's cached web index, so the release and activity
facts that GPT-6 cited (latest release, release date, `pushed_at`, stars) may lag upstream. The web search that the
method limits give the GPT-6 lanes was this cached mode. Together with the Claude WebSearch cap, no lane after
04:10:13Z had live web search except through `gh api` and WebFetch. The limit changes no vote, survivor or reopen
entry.

**Next runs.** Future runs pass `-c web_search="live"`. The packaged `codex_job.py` still passes `--search`; its fix
follows in a separate pull request.

## Survivors and reopened layers

| Layer | Proposed | Survived | Survivors | Reopen triggers |
| --- | --- | --- | --- | --- |
| foundation/native-clients | 8 | 0 | none | first:vote_missing (fit_gpt6); critic:web_search_capped; pin_moved (macos-arm64/ai-memory) |
| foundation/instructions-skills | 15 | 2 | cisco-ai-defense/skill-scanner, anthropics/financial-services | first:vote_missing (fit_gpt6); first:web_search_capped (refute-facts:instructions-skills); followup:web_search_capped (discover:instructions-skills:followup); critic:web_search_capped; pin_moved (macos-arm64/ai-memory) |
| foundation/workers | 8 | 0 | none | first:vote_missing (fit_gpt6); critic:web_search_capped |
| foundation/isolation | 8 | 0 | none | first:vote_missing (fit_gpt6); critic:web_search_capped |
| foundation/code-navigation | 8 | 0 | none | first:vote_missing (fit_gpt6); critic:web_search_capped; selection_changed (mcp-inspector (license None -> NOASSERTION)) |
| foundation/document-retrieval | 7 | 0 | none | first:vote_missing (fit_gpt6); first:web_search_capped (refute-facts:document-retrieval); critic:web_search_capped |
| foundation/semantic-rag | 8 | 0 | none | first:vote_missing (fit_gpt6); critic:web_search_capped; pin_moved (linux-wsl2-x86_64/vllm); pin_moved (macos-arm64/ai-memory) |
| foundation/durable-memory | 14 | 2 | anthropics/claude-code, langchain-ai/langmem | first:vote_missing (fit_gpt6); first:web_search_capped (refute-facts:durable-memory); first:web_search_capped (refute-fit:durable-memory); followup:web_search_capped (discover:durable-memory:followup); critic:web_search_capped; pin_moved (macos-arm64/ai-memory) |
| foundation/web-research | 8 | 0 | none | first:vote_missing (fit_gpt6); first:web_search_capped (refute-facts:web-research); first:web_search_capped (refute-fit:web-research); critic:web_search_capped |
| foundation/token-efficiency | 8 | 0 | none | critic:web_search_capped |
| foundation/quality-evaluation | 14 | 5 | ukgovernmentbeis/inspect_ai, embeddings-benchmark/mteb, boxed/mutmut, sixty-north/cosmic-ray, comet-ml/opik | followup:web_search_capped (discover:quality-evaluation:followup); critic:web_search_capped |
| foundation/ci-supply-chain | 8 | 1 | boostsecurityio/poutine | critic:web_search_capped |
| foundation/scheduling-supervision | 8 | 4 | temporalio/temporal, dagucloud/dagu, earendil-works/absurd, microsoft/pg_durable | critic:web_search_capped |
| foundation/hosting-services | 8 | 0 | none | first:web_search_capped (refute-fit:hosting-services); critic:web_search_capped; selection_changed (mcp-inspector (license None -> NOASSERTION)) |
| foundation/recovery-portability | 8 | 0 | none | critic:web_search_capped; pin_moved (macos-arm64/ai-memory) |
| foundation/observation-inference | 14 | 5 | grafana/tempo, traceloop/openllmetry, ollama/ollama, utkuozdemir/nvidia_gpu_exporter, nvidia/dcgm-exporter | first:web_search_capped (refute-facts:observation-inference); critic:web_search_capped; pin_moved (linux-wsl2-x86_64/vllm) |
| foundation/agent-sdks | 8 | 0 | none | first:web_search_capped (refute-fit:agent-sdks); critic:web_search_capped |
| foundation/mcp-surfaces | 8 | 2 | apify/mcpc, modelcontextprotocol/conformance | critic:web_search_capped; selection_changed (mcp-inspector (license None -> NOASSERTION)) |
| foundation/secrets-credentials | 7 | 3 | betterleaks/betterleaks, praetorian-inc/noseyparker, gitguardian/ggshield | critic:web_search_capped |
| foundation/git-github-automation | 8 | 1 | ataraxy-labs/sem | critic:web_search_capped |
| us-equities/market-data-reference | 6 | 4 | databento/databento-python, massive-com/client-python, man-group/arcticdb, hydrosquall/tiingo-python | first:web_search_capped (refute-facts:market-data-reference); first:web_search_capped (refute-fit:market-data-reference); critic:web_search_capped |
| us-equities/identity-provenance | 8 | 2 | oxen-ai/oxen, dfahrn/securities-master | first:effort_deviation (discover:identity-provenance); first:web_search_capped (refute-facts:identity-provenance); first:web_search_capped (refute-fit:identity-provenance); critic:web_search_capped |
| us-equities/storage-compute | 7 | 1 | chdb-io/chdb | first:web_search_capped (refute-facts:storage-compute); critic:web_search_capped |
| us-equities/data-quality-orchestration | 8 | 1 | flyteorg/flyte | first:effort_deviation (discover:data-quality-orchestration); first:effort_deviation (refute-fit:data-quality-orchestration); critic:web_search_capped |
| us-equities/research-factors-ml | 13 | 4 | bashtage/linearmodels, shiyu-coder/kronos, datadog/toto, lgai-research/exaone-forecast | first:discovery_missing (gpt6); first:web_search_capped (refute-fit:research-factors-ml); followup:web_search_capped (discover:research-factors-ml:followup); critic:web_search_capped; pin_moved (linux-wsl2-x86_64/vllm) |
| us-equities/backtesting-engine | 7 | 0 | none | critic:web_search_capped |
| us-equities/execution-broker | 13 | 9 | ib-api-reloaded/ib_async, csingley/ibflex, wboayue/rust-ibapi, nautechsystems/nautilus_ibapi, gnzsnz/ib-gateway-docker, ibcalpha/ibc, extrange/ibkr-docker, nautechsystems/nautilus_trader, falk-brauer/kumo-nautilus-alpaca-adapter | first:discovery_missing (gpt6); first:web_search_capped (refute-fit:execution-broker); followup:web_search_capped (discover:execution-broker:followup); followup:web_search_capped (refute-fit:execution-broker:followup); critic:web_search_capped |
| us-equities/portfolio-risk | 6 | 1 | csingley/ibflex | first:discovery_missing (gpt6); critic:web_search_capped |
| us-equities/evaluation-experiments | 6 | 0 | none | first:discovery_missing (gpt6); critic:web_search_capped |
| us-equities/agents-models-workers | 11 | 1 | hf:XingChen-AGI/Xing4.0-29B-A4B | first:discovery_missing (gpt6); first:web_search_capped (discover:agents-models-workers); first:web_search_capped (refute-fit:agents-models-workers); followup:web_search_capped (discover:agents-models-workers:followup); critic:web_search_capped; pin_moved (linux-wsl2-x86_64/vllm) |
| us-equities/observability-hosting | 6 | 1 | restic/rest-server | first:discovery_missing (gpt6); first:web_search_capped (discover:observability-hosting); critic:web_search_capped |
| us-equities/security-supply-chain | 13 | 7 | betterleaks/betterleaks, pypi/pypi-attestations, cli/cli, mongodb/kingfisher, datadog/guarddog, slsa-framework/slsa-verifier, chainguard-dev/malcontent | first:discovery_missing (gpt6); first:web_search_capped (discover:security-supply-chain); first:web_search_capped (refute-fit:security-supply-chain); followup:web_search_capped (discover:security-supply-chain:followup); critic:web_search_capped |

Repositories without a host prefix are on GitHub. `hf:` marks a Hugging Face model repository.

**Correction (lane limit 12).** The execution-broker proposal of wboayue/rust-ibapi calls nautilus_trader#4983 an rc5
blocker. At source, #4983 reports v1.227.0, and at rc5 the IB execution client's `handles_order_venue` returns true,
so the engine's `ClientVenueMismatch` denial cannot fire for it. Read instead: rc5 IBKR execution is unqualified (no
rc5 stock order observed). The proposal text, its votes and its survival are unchanged.

**Why a layer reopened.** Each retained failure gives its layer the reopen entry `retained_failure`, which points at
`returns.json#/failures/<layer>`.

- **`critic:web_search_capped`.** The critic's WebSearch calls were capped, and they count for every layer (32
  layers; see [WebSearch session cap](#websearch-session-cap)).
- **`first:web_search_capped` and `followup:web_search_capped`.** A worker of that layer and round had a capped
  WebSearch call (16 layers).
- **`first:vote_missing (fit_gpt6)`.** The first-round GPT-6 fit votes did not return (9 layers).
- **`first:discovery_missing (gpt6)`.** The first-round GPT-6 discovery did not return (7 layers). These layers have
  Claude-only discovery, but their fit votes are two-family.
- **`first:effort_deviation`.** A worker ran below effort max (2 layers).
- **`pin_moved` and `selection_changed`.** These entries copy the saturation report's current triggers at append
  time. The inputs were this checkout's receipt staleness and the run's catalog-freshness artifact 36205743492.

All 32 layers reopened for retained failures, and 11 of them also carry report triggers. After this record every
layer is at 0, and no layer is a saturation candidate.

**Refuted by absence (not survivors).** In the 9 layers without first-round GPT-6 fit votes, 27 proposals passed the
facts refuter and the Claude fit refuter. Their GPT-6 fit vote is missing, and the survival rule counts a missing vote
as refuted, so they are listed under `refuted`. They are neither refuted on merit nor two-family agreement:

- The fit vote's `gpt6` member in `returns.json` is `{missing: true}`.
- Each layer's `votes_note` in the ledger names them.
- `saturation_ledger.py` (`refuted_by_absence`) does not count them as adjudicated, so a later sweep that proposes
  them again lists them as new.
- `build_inputs.py` shows them to the next discovery round as `previous_sweep.not_adjudicated`, not as refuted.

The coordinator's incident log (its 03:47Z to 03:55Z entry) planned to record the affected layers "never as
two-family agreement and never as refuted-by-absence". The ledger has no third outcome, so these proposals stay under
`refuted`, as the survival rule requires. The missing marker, the `votes_note` and the two tools keep them from
counting as refuted on merit. These proposals are the first candidates for a second-family fit vote:

- native-clients: earendil-works/pi
- instructions-skills: mattpocock/skills
- workers: openai/codex, sipyourdrink-ltd/bernstein
- isolation: superradcompany/microsandbox, boxlite-ai/boxlite
- code-navigation: anthropics/claude-plugins-official, abhigyanpatwari/gitnexus
- document-retrieval: opendatalab/mineru, docling-project/docling, cinnamon/kotaemon, huggingface/sentence-transformers,
  arabold/docs-mcp-server
- semantic-rag: osu-nlp-group/hipporag, lightonai/next-plaid, minishlab/semble, ollama/ollama,
  giancarloerra/socraticode
- durable-memory: campfirein/byterover-cli, rohitg00/agentmemory, mempalace/mempalace, vshulcz/deja-vu,
  vbcherepanov/total-agent-memory
- web-research: exa-labs/exa-mcp-server, unclecode/crawl4ai, adbar/trafilatura, openai/codex

## Lane limits

The manifest's `lane_limits/landscape-sweep-20260926` holds the four method limits that `convert.py` writes and the
twelve run-specific limits below. Each was passed as `--limit`.

1. Harness: this run used the 2026-09-26 scratchpad prototype of the lane, not the packaged
   tools/sota-convergence/landscape-sweep/ harness merged afterwards (#324). Its prompts_sha256
   3adfbed7a83e85da3fd7951032e1fa3a579101772a47b211580065c6b42618d4 is the sha256 of the prototype's staged
   templates; the packaged templates filled with this run's values reproduce it (a local check,
   tests/test_landscape_sweep_harness.py).
2. Layer inputs: the prototype's input builder cut known-repository slugs with rstrip('.git'). A local check against
   the GitHub repositories named in this repository's catalogs and manifests finds 95 of the 614 known-repository
   slugs cut, in 30 of the 32 layers (qdrant/qdrant appeared as qdrant/qdran, pydantic/pydantic-ai as
   pydantic/pydantic-a), so discovery saw slightly wrong known-repository lists. The ledger's known/new split is
   recomputed from the manifest baseline and is not affected.
3. GPT-6 lanes: 16 of the 80 GPT-6 jobs returned nothing; evidence/artifacts/landscape-sweep-20260926/gpt6-jobs.json
   keeps each job's times and markers. Two discovery jobs ended with the shared Codex account's usage-limit error
   event (03:47-03:55Z), and six jobs (five discovery, one fit) were refused by the runner's usage-limit marker from
   03:57Z to 04:12Z; the coordinator records the account signed in again at 04:15Z. Eight first-round fit jobs
   requested from 04:17Z to 05:35Z never started: the prototype runner's start command split its shell script at an
   embedded quote in its usage-limit event check (added at about 03:57Z, per the coordinator's incident log), which
   shifted its arguments, so its slot loop never obtained a slot; the next fit job started at 05:52Z. The seven
   layers without a GPT-6 discovery return have Claude-only discovery. In the nine layers without GPT-6 first-round
   fit votes a missing vote counts as refuted: those proposals are not survivors, and they are never counted as
   two-family agreement. The 27 of them that the facts refuter and the Claude fit refuter both passed are refuted by
   absence, not on merit: each layer's votes_note names them, their fit vote's gpt6 member is {missing: true}, and
   saturation_ledger.py and build_inputs.py do not count them as adjudicated. Every affected layer is reopened
   (retained_failure). The false usage-limit marker of 02:17Z (text in a cited README matched the prototype's check)
   fell in the stopped run 1, not in this run.
4. Seeds: the run's seeds (tools/sota-convergence/landscape-sweep/seeds-20260926.json) placed two candidates
   differently from manifests/candidates.json: NVIDIA/TensorRT-LLM under observation-inference (candidates.json:
   semantic-rag), and EleutherAI/lm-evaluation-harness under quality-evaluation only (candidates.json: also
   us-equities evaluation-experiments). OSU-NLP-Group/HippoRAG was seeded to durable-memory as well as semantic-rag.
   Of the 50 seeds that name a GitHub or Hugging Face repository, no discovery worker in any layer proposed 12:
   vercel-labs/skills, vercel-labs/agent-browser, vercel-labs/agent-skills and openai/skills (instructions-skills),
   microsoft/markitdown (document-retrieval), vllm-project/vllm (semantic-rag), akitaonrails/ai-memory
   (durable-memory), NVIDIA/TensorRT-LLM and sgl-project/sglang (observation-inference), skfolio/skfolio
   (research-factors-ml and portfolio-risk), and the Hugging Face model Qwen/Qwen3.8-27B (agents-models-workers).
   UKGovernmentBEIS/inspect_ai, seeded to evaluation-experiments, was proposed only in quality-evaluation, and
   Qwen3.8-Flash-Next, seeded without an owner, was proposed only as other owners' GGUF builds.
5. Effort: after loading the pinned property-based-testing skill, whose frontmatter sets effort: low, three Claude
   workers (discover:identity-provenance, discover:data-quality-orchestration, refute-fit:data-quality-orchestration)
   ran their remaining turns at effort low. Each is an effort_deviation retained failure, and its layer is reopened.
6. Claude usage limit: the Workflow paused at a Claude usage limit and, after the reset, re-ran its 8 waiting refuter
   calls under the same call keys. Their first attempts returned nothing and are recorded as superseded attempts,
   whose usage still counts; every call returned.
7. Call counts cover discovery only (both families, as each worker reported them); refuter and critic calls are not
   counted. The workers' own Claude web_search total (170) counts capped calls as searches: measured from the
   transcripts (web_search in the usage record), the Claude discovery workers made 169 WebSearch calls, and 15 of
   them were capped (limit 10). Run wf_8397ada1-777 ran from 02:23Z to 12:51Z with 201 Claude children at effort max
   (40 discovery, 40 GPT-6 discovery wrappers, 40 facts refuters, 40 Claude fit refuters, 40 GPT-6 fit wrappers, 1
   critic). Claude usage per resolved model is in
   evidence/artifacts/landscape-sweep-20260926-attempts/child-usage-wf_8397ada1-777.json and GPT-6 usage in the
   returns' gpt6_usage; the two are never summed.
8. Codex review: the Codex review step of recipes/sota-convergence-practice.md (step 5) is this run's GPT-6-Astra
   lanes, which gave second-family discovery and fit votes through the Codex CLI, recorded per vote in the retained
   returns. No separate Codex review of this manifest was run.
9. Earlier attempts: the one-layer smoke (wf_1753e674-5dc, mcp-surfaces) completed, and run 1 (wf_a874897e-af1,
   earlier templates with prompts_sha256 1b7844800af40911484591d738a86741fd4a68cbb58339bc8126418c4c6a8783) was
   stopped by the coordinator after 3 of its 11 started children returned, when the user asked for
   SOTA-skill-aligned, incumbency-neutral prompts. Both are retained under
   evidence/artifacts/landscape-sweep-20260926-attempts/; nothing from them is merged into this lane.
10. WebSearch session cap: Claude Code allows one session at most CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION WebSearch
    calls (default 200), counted across the coordinator and every subagent, workflow children included; a capped call
    returns a notice that tells the worker to go on without searching (code.claude.com tools-reference, 'Session
    search limit'). The coordinator session ran with the default, and its four workflow runs of 2026-09-26 used the
    200 calls between 01:45Z and 04:08Z: the smoke 1, run 1 25, the session's separate workflow wf_9dec7824-293 20
    (counted from its transcripts, not retained here) and this run 154. From 04:10:13Z
    (discover:agents-models-workers) to 11:55:57Z (refute-fit:execution-broker:followup), 46 of this run's 200
    WebSearch calls were capped, in 30 workers: 4 calls of 3 first-round discovery workers, 11 of 7 of the 8
    follow-up discovery workers, 17 of 8 facts refuters, 12 of 11 Claude fit refuters and 2 of the critic. No Claude
    refuter, follow-up discovery worker or critic WebSearch call returned results. One vote rests on the cap: the
    identity-provenance facts refuter refuted databento/databento-python because it could not cross-check a claim by
    search (returns votes/identity-provenance/3/facts). Every capped worker is a web_search_capped retained failure
    of its layer and the critic's counts for every layer, so every layer is reopened and no layer counts as clean.
    The GPT-6 lanes search through Codex, outside this cap.
11. GPT-6 web search: every GPT-6-Astra lane of this run, discovery and fit, searched Codex's cached web index, not
    the live web. The prototype runner started each job as codex --search exec: its script, kept in the coordinator's
    private work directory, holds that line from 05:42:45Z until 16:36:56Z, when it became -c web_search="live" (the
    version before 05:42:45Z is not retained). The Codex qualification of 2026-09-26 (#332) measured on Codex 0.155.1
    and 0.157.1, against a local stand-in provider, that a top-level --search does not reach exec: with --search
    before exec (case W1) and with no flag (case W2) every search request carried external_web_access: false, and
    only -c web_search="live" (case W3) sent true
    (evidence/artifacts/sota-refresh-20260926/codex/results/websearch-0.155.1.json and websearch-0.157.1.json; that
    the OpenAI provider behaves the same rests on source reading, per
    evidence/receipts/codex-01571-qualification-20260926.json). The run's returns do not record the Codex version;
    both versions behave the same. On 2026-09-26 the coordinator observed a real codex 0.157.1 exec with -c
    web_search="live" make a live search; that observation is not retained. The web search that the method limits
    give the GPT-6 lanes was therefore cached: GPT-6 discoveries and votes rested on the provider's cached web index,
    and the release and activity facts GPT-6 cited (latest release, release date, pushed_at, stars) may lag upstream.
    Together with limit 10, no lane after 04:10:13Z had live web search except through gh api and WebFetch. Future
    runs pass -c web_search="live"; the fix of the packaged codex_job.py follows in a separate pull request.
12. Correction, 2026-09-26 (the trading lane's review of #357): the execution-broker proposal of wboayue/rust-ibapi,
    which compares a re-pin through nautilus_trader PR #5041, says "rc5 also stays blocked by open issue #4983" and
    "cases rc5 fails (the #4983 local order denial)", and its discovery notes call #4983 an rc5 adapter failure. That
    is refuted at source (gh api, read 2026-09-26): #4983's body reports Version v1.227.0; at commit 1b0a49d2,
    identical to tag v2.0.0rc5, the IB execution client overrides handles_order_venue to return true
    (crates/adapters/interactive_brokers/src/execution/core.rs:493-495), so the ClientVenueMismatch denial behind the
    execution engine's handles_order_venue check (crates/execution/src/engine/mod.rs:2222) cannot fire for it; and
    the open PR #280 already reclassifies #4983 in catalogs/us-equities/runtime-target.json as a stale v1.227.0
    report. Read instead: rc5 IBKR execution is unqualified (no rc5 stock order observed). The proposal text stays as
    the model wrote it, and its votes and survival are unchanged.

Notes on limit 3:

- **Job timeline.** `gpt6-jobs.json` keeps, for each of the 80 GPT-6 jobs, the workflow's status, the time its prompt
  was written, the runner's started, finished and exit values, and the refusal and usage-limit-event markers. It also
  keeps the coordinator's incident-log entries that the limit cites, each attributed.
- **Stuck runner processes.** While this record was being made, the eight never-started fit jobs' prototype runner
  processes were still looping at 13:52Z. Each had received the work-directory path as its slot count, and none had
  started Codex. `gpt6-jobs.json` records that observation.
- **Scope.** The limits describe the prototype run. The packaged runner (`codex_job.py`) is a separate
  implementation.

## Tavily leads (not evidence)

Before this record, the coordinator ran one Tavily Research (pro) report per layer. `tavily-leads.json` compares them
with the sweep, using the prototype's `tavily_crosscheck.py` on the converted `returns.json`. It keeps no report text.
Each report's request id is kept only as `uuid-sha256:<16 hex>`.

The reports named 208 GitHub repositories. The script counted 136 of them as missed. This file splits those 136 as
follows:

- **11 were in the layer input.** The script reads only `github.com` links, so it missed the input's bare
  `owner/repo` entries, some of them cut short by the prototype.
- **57 are in this repository's catalogs.**
- **4 were proposed in another layer.**
- **64 remain leads.**

Some leads are not repositories at all, such as `assets/img` and `docs/codeql-overview`. The verdict wave checks each
lead before using it. The [lead vetting](#tavily-lead-vetting-addendum) below screened all 136 after the sweep.

| Layer | Leads |
| --- | --- |
| agent-sdks | langchain-ai/langgraphjs, tsharp/agent-runtime |
| agents-models-workers | amikos-tech/chromadb-ops, predibase/lorax |
| backtesting-engine | fbertram/turingtrader |
| ci-supply-chain | actions/attest-build-provenance, anchore/sbom-action, attestplane/attestplane, cyclonedx/cdxgen-action, sbom-tool/sbom-tools-action, spdx/tools-golang |
| code-navigation | assets/img, docs/codeql-overview, sourcegraph/cody-vs |
| data-quality-orchestration | whylabs/whylogs |
| document-retrieval | grobidorg/grobid, layout-parser/layout-parser, run-llama/llama-parse-ts, unstructured-io/unstructured-js-client |
| durable-memory | qdrant/qdrant-helm |
| evaluation-experiments | evalplus/evalplus, evolvinglmms-lab/lmms-eval, openai/simple-evals |
| git-github-automation | k1low/gh-pr-reviews, kbrdn1/gwm-cli, peter-evans/create-pull-request |
| hosting-services | 88plug/k3d-gpu, eknkc/ssr-benchmark, jakkaj/k3d-gpu, kludex/starlette, pallets/quart, sanic-org/sanic, tanrax/python-api-frameworks-benchmark |
| identity-provenance | pachyderm/pachyderm |
| instructions-skills | langchain-ai/langchain-skills, langchain-ai/skills-benchmarks |
| isolation | kata-containers/documentation |
| market-data-reference | finos/openmama, mypmc/marketstore, openmama/openmama, questdb/questdb-trading-data-demo |
| native-clients | anthropics/anthropic-sdk-go, dongri/openai-api-rs, jeremychone/rust-genai, yanceyofficial/rs-openai |
| observability-hosting | yanghaku/wasmer-gpu-go |
| portfolio-risk | auto-differentiation/quantlib-risks-py, quantales/pyquantlib |
| research-factors-ml | jialuechen/torchquant |
| security-supply-chain | aboutcode-org/scancode-toolkit, awslabs/git-secrets, cyclonedx/cdxgen, microsoft/sbom-tool |
| semantic-rag | activeloopai/deeplake, igor-im/code-rag, jonnoc/coderag, kdegroup/coderag |
| storage-compute | timescale/docs |
| token-efficiency | bowang-lab/vllm, flashinfer-ai/flashinfer, zilliztech/gptcache |
| web-research | alphaxiv/openresearch-cli, alxdr3k/tavily-cli |
| workers | microsoft/sico |

## Tavily lead vetting (addendum)

After the sweep, Workflow run `wf_6a6cb7b8-c22` (14:11:51Z to 15:27:54Z) vetted all 136 leads that the cross-check
counted as missed. `tavily-leads-vetting.json` keeps the result. It is discovery-completeness evidence, not a
verdict: it is not a ledger record, it changes no layer count, and the verdict wave still checks each candidate.

- **Screen.** One Claude screener per layer (Sonnet) was told to check each lead through `gh api` and its README.
  The screeners dismissed 100 leads with a reason and wrote 36 proposals in the sweep's discovery format. 7 are
  labelled `not_adopted`, so 29 were kept, in 15 layers.
- **Votes.** The sweep's facts refuter (Claude Sonnet) and both fit refuters (Claude Opus and GPT-6-Astra) voted on
  the 29 kept proposals, with the sweep's templates and survival rule. No vote was missing.
- **Result.** No proposal survived. The Claude fit refuter refuted all 29, the GPT-6 fit refuter 21 and the facts
  refuter 4. In 8 cases GPT-6 did not refute but Claude did: apache/airflow (which the facts refuter refuted too),
  grobidorg/grobid, kbrdn1/gwm-cli, peter-evans/create-pull-request, abiosoft/colima, google/nsjail,
  victoriametrics/victorialogs and victoriametrics/victoriametrics.
- **Limitations.** The vetting has the run's two search limits. Its Claude workers had no WebSearch: the session cap
  refused both of its WebSearch calls (screen:semantic-rag and refute-fit:observation-inference:leads). Its GPT-6
  fit jobs searched Codex's cached index (lane limit 11). The sweep's templates tell a refuter to default to refuted
  when uncertain, so the missing search may have pushed Claude votes toward refuted. The 8 split cases are the first
  leads to recheck once both families search live.
- **Usage.** `child-usage-wf_6a6cb7b8-c22.json` measures 75 Claude children, all at effort max, with complete usage:
  claude-sonnet-5 60 children (output 1,626,358 tokens) and claude-opus-5-5 15 (output 532,024). The 15 GPT-6 jobs
  reported input 8,401,965 tokens (cached 7,047,936) and output 105,625 (reasoning 74,715). The two are never summed.

## skills_usage

This table comes from `returns.json` `skills_usage`. Each worker reported its own `skills_used`, and nothing else
checked those reports. A count is the number of worker returns that list the skill. Each Claude role returned 40
times (32 first-round and 8 follow-up rounds). GPT-6 discovery returned 33 times and GPT-6 fit 31 times.

| Role | Skills (reports) |
| --- | --- |
| discover_claude | search-first 40, verification-before-completion 37, supply-chain-risk-auditor 34, iterative-retrieval 33, fp-check 4, property-based-testing 2, mcp-builder 1 |
| discover_gpt6 | search-first 12, verification-before-completion 12, iterative-retrieval 11, supply-chain-risk-auditor 8, fp-check 3, openai-docs 1 |
| facts | fp-check 15, verification-before-completion 14, supply-chain-risk-auditor 8, iterative-retrieval 4, search-first 2 |
| fit_claude | verification-before-completion 40, supply-chain-risk-auditor 38, fp-check 35, iterative-retrieval 3, property-based-testing 1 |
| fit_gpt6 | verification-before-completion 7, supply-chain-risk-auditor 6, fp-check 6 |

The GPT-6 lanes ran with `--ignore-user-config`. Only 12 of the 33 GPT-6 discovery returns and 7 of the 31 GPT-6 fit
returns list any skill, so these counts do not measure GPT-6 skill use.

## Files

- `inputs/` (added 2026-09-26 after the record merged): the 32 layer-input files exactly as this run read them (written 2026-09-25 21:30-22:44 local, before the run), with `inputs/SHA256SUMS` (`cd inputs && sha256sum -c SHA256SUMS`). They show lane limit 2's truncated known-repository slugs as the workers saw them. The verdict wave's GPT-6 fit re-votes for the 27 not-adjudicated entries use these originals rather than rebuilt inputs.

- **`returns.json`.** The output of `convert.py`, redacted as described below. It holds the discovery returns with
  the frozen scope hashes, the facts and two-family fit votes, the raw family returns, the retained failures,
  `skills_usage` and `gpt6_usage`. The ledger's `returns_ref` points to it.
- **`lanes.json`.** The lane record that `build_manifest.py` merged into `manifest-20260926.json`, redacted as
  described below.
- **`layers.json`.** The ledger layer entries from `convert.py`, with refs written as `@RETURNS@`. `make_result.py`
  filled in those refs.
- **Source reviews.** `<owner>-<repo>.json` for 53 GitHub repositories and `hf-xingchen-agi-xing4-0-29b-a4b.json`
  for the Hugging Face model. Each review records the upstream provenance at the default-branch commit, from
  `source_reviews.py`. There is one review per surviving repository, and its `layers` names every layer where it
  survived.
- **`gpt6-jobs.json`.** The GPT-6 job timeline, the stuck-runner observation and the cited coordinator incident-log
  entries that support lane limit 3. It holds no model text and no host paths.
- **`tavily-leads.json`.** Discovery leads only.
- **`tavily-leads-vetting.json`.** The lead-vetting addendum, discovery-completeness evidence rather than a verdict.
  Per layer it keeps the leads, the screen's dismissals and proposals, and each refuter's vote on the kept proposals
  (refuted, confidence, a reasoning excerpt of at most 300 characters and refs). Its method, limitations, totals and
  usage are in the file.
- **`child-usage-wf_6a6cb7b8-c22.json`.** The lead-vetting run's Claude usage and WebSearch counts, from
  `usage_record.py`.
- **`independent-review.json`.** The three review rounds' findings and their repairs, and the trading lane's
  correction (lane limit 12).
- **The attempts directory.**
  - `child-usage-wf_8397ada1-777.json`: this run's usage and per-worker WebSearch counts.
  - `child-usage-wf_a874897e-af1.json` and `wf_a874897e-af1.json`: run 1's lower-bound usage and its compact
    record, which is the ledger's `record_ref`.
  - `child-usage-wf_1753e674-5dc.json` and `wf_1753e674-5dc.json`: the smoke's usage and its compact record.
  - Each compact record's `provider_usage.web_search` copies its run's measured WebSearch counts. Run 1 made 25
    calls and the smoke 1, none capped.

**Redactions.**

- **Session scratchpad path and user name.** `convert.py` exited 3 (possible private content) because two Claude
  discovery notes cited the coordinator session's scratchpad path. The notes were `raw/durable-memory/followup` and
  `raw/scheduling-supervision/first`. `scripts/host_receipts.py` `sanitize()` was then applied to every string of the
  four outputs. In those two notes it replaced the session id with `[redacted]` and the user name with `<user>`. It
  also replaced the user name in one facts vote's reasoning (observability-hosting, superradcompany/microsandbox),
  which quoted the operator account's group list; that string appears in both `returns.json` and `lanes.json`.
  Afterwards, `convert.py`'s private-content check found nothing in the four outputs.
- **Credential-name marker.** `build_manifest.py` refused `lanes.json` while one string held its credential-name
  marker `APCA`. The string is a secrets-credentials comparison that named the Alpaca credential class. In
  `lanes.json` only, "Alpaca APCA pair" now reads "Alpaca API-key pair"; `returns.json` keeps the worker's text.
- **Shortened commit ids.** Workers cited git commit ids in their free text. gitleaks' `sourcegraph-access-token`
  rule reads any word-bounded 40-hex value as a token when the scanned text also contains the keyword
  "sourcegraph". A secrets-credentials refuter named that rule id in its reasoning, so the pre-commit scan flagged
  130 values: 77 commit ids in the lane's free text and 53 catalog pins in the manifest. Every 40-hex id inside a string of `returns.json` (549 ids) and `lanes.json` (143 ids) is
  therefore shortened to its first 12 characters, which still resolves on GitHub. Vote structure is unchanged
  (repository, refuted, role and round). The manifest was rebuilt from the shortened `lanes.json`. Its only 40-hex
  values are now the 60 catalog pins that the generator copies from the catalog layer files. They hold 39 distinct
  git commit ids. A new `.gitleaks.toml` allowlist exempts exactly those 39 ids, pinned by value, for this rule in
  this exact file. Any other 40-hex value, an uppercase variant or an `sgp_` token stays detected. It follows the
  2026-09-23 pin allowlist of `manifest-20260923.json` and comes with regression tests `test_d3` and `test_d4` in
  `tests/test_gitleaks_config.py`.
- **Lead-vetting addendum.** One facts refuter's ref named this repository's checkout path; it reads `<checkout>`.
  `sanitize()` then ran on every string of `tavily-leads-vetting.json`, and the private-content check found nothing.
  The file names sourcegraph/* leads, so its 23 40-hex ids (22 commit ids in refs and the usage measurement's
  `tool_commit`) are shortened to 12 characters as above; the usage record keeps the full `tool_commit`.

**Verification.** After a simulated registration of every new and changed file,
`scripts/saturation_ledger.py --check --base origin/main` and `scripts/validate.py` passed, and they passed again
after lane limit 11 and the lead-vetting addendum, and after the third round's repairs and lane limit 12. The pinned
gitleaks 8.30.1 found nothing with the repository configuration. The coordinator registers the files in
`manifests/evidence.json`.

**Independent review.** There were three review rounds, each followed by one repair round. The first two were
same-family; the third was GPT-6-Astra.

1. **First round.** A separate headless Claude session (Opus, read-only tools) reviewed the first version of this
   record and of the tool and allowlist changes. It returned `needs_changes` with six low findings. Codex was not
   used because another session's GPT-6 jobs were using the shared Codex account at the time.
2. **Second round.** The coordinator's workflow reviewers (Claude Opus) reviewed the committed record and reported
   two findings. Both were verified against the transcripts, the returns and the ledger, and both were repaired:
   - **High.** The session's WebSearch cap went unrecorded, and three layers derived as clean. It is now lane
     limit 10 and the section above. `web_search_capped` retained failures now reopen every layer.
   - **Medium.** The 27 proposals refuted only by the missing GPT-6 fit vote counted downstream as refuted on
     merit. The ledger and the input builder now tell absence from merit.

The reviewers also offered a second fix for the medium finding: collect the nine missing GPT-6 fit votes before
appending. That was not done. Those votes would come from a new model run, hours after this run and on another
runner, so they would not be this run's votes. The verdict wave, which the coordinator owns, is where they belong,
and the 27 proposals are listed above as its first candidates. `independent-review.json` records each finding and its
disposition.

3. **Third round.** A read-only GPT-6-Astra review (max effort, live web search) of the record's checkout, which
   held lane limit 11 and the lead-vetting addendum, returned `NOT_READY` with two P2 findings, both in the tools.
   Each was reproduced by a regression test that failed before the repair, and both were repaired in `7760b1da`:
   - **A.** `child-usage.mjs` reported a run `complete` although a superseded attempt held an assistant message
     without provider usage. Such usage-integrity failures of a superseded attempt now make the run incomplete. The
     three usage records were re-measured at `7760b1da`; each `child_usage` is unchanged, so no status,
     `lower_bound_usage` or ledger outcome changed.
   - **B.** `make_result.py` checked failure coverage over all layers at once, so a layer could lose its critic
     failure and its reopen entry and count as clean. Coverage is now checked per worker and per layer. This record
     passes the new check: every layer holds the critic's failure, and every other worker's failure is in its layer.

The trading lane's review of #357 found the #4983 attribution of the rust-ibapi proposal refuted at source; it is
the dated correction in lane limit 12. Lane limit 12 and the third round's repairs have not been reviewed again.

## Attempts

- **Smoke, `wf_1753e674-5dc`.**
  - The run: one layer (mcp-surfaces), 5 children, complete usage, and 2 GPT-6 jobs, both `ok`.
  - Its conversion with `convert.py --scope` gave 8 proposals and 1 survivor.
  - It is a harness check, so it has no ledger record, and its proposals are not in this lane.
  - Its templates predate `skills_used` reporting.
- **Run 1, `wf_a874897e-af1`, stopped.**
  - The coordinator stopped it after 3 of its 11 started children returned, when the user asked for SOTA-skill-aligned,
    incumbency-neutral prompts. All 3 returned children were GPT-6 discovery wrappers, and no Claude discovery or
    refuter returned.
  - Its ledger record `landscape-sweep-20260926-attempt-1` has `votes: not_returned` entries for native-clients and
    instructions-skills (their GPT-6 proposals) and lists the 8 children stopped in flight as `lost_workers`. It
    neither counts nor resets.
  - The GPT-6 discovery wrapper for workers returned exit 3 because of the false usage-limit marker, which
    `wf_a874897e-af1.json` records.
  - Its usage is a lower bound. Claude output was 279,241 tokens on claude-opus-5-5 and 49,705 on claude-sonnet-5.
    Separately, its three finished GPT-6 jobs reported 41,783 Codex output tokens.
