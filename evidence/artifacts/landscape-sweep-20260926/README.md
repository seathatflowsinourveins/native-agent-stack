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
manifest and source reviews. `tavily-leads.json` and the attempts' compact records were written for this record,
and each states its method.

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
  240 page fetches and 1,004 GitHub API calls. GPT-6: 396, 264 and 748.

## Measured usage

The two kinds of counters below are never summed.

**Claude.** The source is `child-usage-wf_8397ada1-777.json` in the attempts directory. It was measured with
`child-usage.mjs` at tool commit `23b2ab06` (sha256 `71509f66…9480`).

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

## Survivors and reopened layers

| Layer | Proposed | Survived | Survivors | Reopen triggers |
| --- | --- | --- | --- | --- |
| foundation/native-clients | 8 | 0 | none | first:vote_missing (fit_gpt6); pin_moved (macos-arm64/ai-memory) |
| foundation/instructions-skills | 15 | 2 | cisco-ai-defense/skill-scanner, anthropics/financial-services | first:vote_missing (fit_gpt6); pin_moved (macos-arm64/ai-memory) |
| foundation/workers | 8 | 0 | none | first:vote_missing (fit_gpt6) |
| foundation/isolation | 8 | 0 | none | first:vote_missing (fit_gpt6) |
| foundation/code-navigation | 8 | 0 | none | first:vote_missing (fit_gpt6); selection_changed (mcp-inspector (license None -> NOASSERTION)) |
| foundation/document-retrieval | 7 | 0 | none | first:vote_missing (fit_gpt6) |
| foundation/semantic-rag | 8 | 0 | none | first:vote_missing (fit_gpt6); pin_moved (linux-wsl2-x86_64/vllm); pin_moved (macos-arm64/ai-memory) |
| foundation/durable-memory | 14 | 2 | anthropics/claude-code, langchain-ai/langmem | first:vote_missing (fit_gpt6); pin_moved (macos-arm64/ai-memory) |
| foundation/web-research | 8 | 0 | none | first:vote_missing (fit_gpt6) |
| foundation/token-efficiency | 8 | 0 | none | none |
| foundation/quality-evaluation | 14 | 5 | ukgovernmentbeis/inspect_ai, embeddings-benchmark/mteb, boxed/mutmut, sixty-north/cosmic-ray, comet-ml/opik | none |
| foundation/ci-supply-chain | 8 | 1 | boostsecurityio/poutine | none |
| foundation/scheduling-supervision | 8 | 4 | temporalio/temporal, dagucloud/dagu, earendil-works/absurd, microsoft/pg_durable | none |
| foundation/hosting-services | 8 | 0 | none | selection_changed (mcp-inspector (license None -> NOASSERTION)) |
| foundation/recovery-portability | 8 | 0 | none | pin_moved (macos-arm64/ai-memory) |
| foundation/observation-inference | 14 | 5 | grafana/tempo, traceloop/openllmetry, ollama/ollama, utkuozdemir/nvidia_gpu_exporter, nvidia/dcgm-exporter | pin_moved (linux-wsl2-x86_64/vllm) |
| foundation/agent-sdks | 8 | 0 | none | none |
| foundation/mcp-surfaces | 8 | 2 | apify/mcpc, modelcontextprotocol/conformance | selection_changed (mcp-inspector (license None -> NOASSERTION)) |
| foundation/secrets-credentials | 7 | 3 | betterleaks/betterleaks, praetorian-inc/noseyparker, gitguardian/ggshield | none |
| foundation/git-github-automation | 8 | 1 | ataraxy-labs/sem | none |
| us-equities/market-data-reference | 6 | 4 | databento/databento-python, massive-com/client-python, man-group/arcticdb, hydrosquall/tiingo-python | none |
| us-equities/identity-provenance | 8 | 2 | oxen-ai/oxen, dfahrn/securities-master | first:effort_deviation (discover:identity-provenance) |
| us-equities/storage-compute | 7 | 1 | chdb-io/chdb | none |
| us-equities/data-quality-orchestration | 8 | 1 | flyteorg/flyte | first:effort_deviation (discover:data-quality-orchestration); first:effort_deviation (refute-fit:data-quality-orchestration) |
| us-equities/research-factors-ml | 13 | 4 | bashtage/linearmodels, shiyu-coder/kronos, datadog/toto, lgai-research/exaone-forecast | first:discovery_missing (gpt6); pin_moved (linux-wsl2-x86_64/vllm) |
| us-equities/backtesting-engine | 7 | 0 | none | none |
| us-equities/execution-broker | 13 | 9 | ib-api-reloaded/ib_async, csingley/ibflex, wboayue/rust-ibapi, nautechsystems/nautilus_ibapi, gnzsnz/ib-gateway-docker, ibcalpha/ibc, extrange/ibkr-docker, nautechsystems/nautilus_trader, falk-brauer/kumo-nautilus-alpaca-adapter | first:discovery_missing (gpt6) |
| us-equities/portfolio-risk | 6 | 1 | csingley/ibflex | first:discovery_missing (gpt6) |
| us-equities/evaluation-experiments | 6 | 0 | none | first:discovery_missing (gpt6) |
| us-equities/agents-models-workers | 11 | 1 | hf:XingChen-AGI/Xing4.0-29B-A4B | first:discovery_missing (gpt6); pin_moved (linux-wsl2-x86_64/vllm) |
| us-equities/observability-hosting | 6 | 1 | restic/rest-server | first:discovery_missing (gpt6) |
| us-equities/security-supply-chain | 13 | 7 | betterleaks/betterleaks, pypi/pypi-attestations, cli/cli, mongodb/kingfisher, datadog/guarddog, slsa-framework/slsa-verifier, chainguard-dev/malcontent | first:discovery_missing (gpt6) |

Repositories without a host prefix are on GitHub. `hf:` marks a Hugging Face model repository.

**Why a layer reopened.** Each retained failure gives its layer the reopen entry `retained_failure`, which points at
`returns.json#/failures/<layer>`.

- **`first:vote_missing (fit_gpt6)`.** The first-round GPT-6 fit votes did not return (9 layers).
- **`first:discovery_missing (gpt6)`.** The first-round GPT-6 discovery did not return (7 layers). These layers have
  Claude-only discovery, but their fit votes are two-family.
- **`first:effort_deviation`.** A worker ran below effort max (2 layers).
- **`pin_moved` and `selection_changed`.** These entries copy the saturation report's current triggers at append
  time. The inputs were this checkout's receipt staleness and the run's catalog-freshness artifact 36205743492.

18 layers reopened for retained failures, and 11 layers carry report triggers. Together, 22 layers carry at least one
reopen entry. Seven more layers stay at 0 because they have survivors. After this record, `agent-sdks`,
`backtesting-engine` and `token-efficiency` have a clean count of 1, and every other layer is at 0. No layer is a
saturation candidate.

**Claude-only passes (not survivors).** In the 9 layers without first-round GPT-6 fit votes, 27 proposals passed the
facts refuter and the Claude fit refuter. Their GPT-6 fit vote is missing, which counts as refuted. These proposals
are neither refuted on merit nor two-family agreement. They are the first candidates for a second-family fit vote:

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
nine run-specific limits below. Each was passed as `--limit`.

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
   fit votes a missing vote counts as refuted: those proposals are not survivors, their only fit votes are Claude's,
   and they are never counted as two-family agreement. Every affected layer is reopened (retained_failure). The false
   usage-limit marker of 02:17Z (text in a cited README matched the prototype's check) fell in the stopped run 1, not
   in this run.
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
   counted. Run wf_8397ada1-777 ran from 02:23Z to 12:51Z with 201 Claude children at effort max (40 discovery, 40
   GPT-6 discovery wrappers, 40 facts refuters, 40 Claude fit refuters, 40 GPT-6 fit wrappers, 1 critic). Claude
   usage per resolved model is in
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
lead before using it.

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
- **`independent-review.json`.** The independent review's findings and their repairs.
- **The attempts directory.**
  - `child-usage-wf_8397ada1-777.json`: this run's usage.
  - `child-usage-wf_a874897e-af1.json` and `wf_a874897e-af1.json`: run 1's lower-bound usage and its compact
    record, which is the ledger's `record_ref`.
  - `child-usage-wf_1753e674-5dc.json` and `wf_1753e674-5dc.json`: the smoke's usage and its compact record.

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

**Verification.** After a simulated registration of every new and changed file,
`scripts/saturation_ledger.py --check --base origin/main` and `scripts/validate.py` passed. The pinned gitleaks
8.30.1 found nothing with the repository configuration. The coordinator registers the files in
`manifests/evidence.json`.

**Independent review.** A separate headless Claude session (Opus, read-only tools) reviewed the first version of
this record and of the tool and allowlist changes. It returned `needs_changes` with six low findings.
`independent-review.json` records each finding and its repair. There was one review and one repair round.
The review is same-family; no Codex review was run, because another session's GPT-6 jobs were using the shared
Codex account at the time.

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
