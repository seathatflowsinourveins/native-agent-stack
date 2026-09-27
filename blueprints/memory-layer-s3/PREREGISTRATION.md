# Memory layer S3: head-to-head preregistration (DRAFT r4, 2026-09-27)

**Status: DRAFT r4, not frozen.**
- r4 governs the memory decision on both hosts and proposes that the unwritten A17 plan (the workstation's confirmatory R1 under A1–A16.3) is superseded, not run (section 12, with the amendment file `blueprints/memory-stack/longmemeval/A17-SUPERSESSION.md`). Other r4 changes:
  - reference feasibility on v2.4.0 is established from source (section 1);
  - the arms are defined from the v4 driver (#386), and the harness is v4-based with a new isolated runner (section 3);
  - agentmemory's primary arm is its shipped hook path (section 2);
  - a late-candidate rule is added (section 2);
  - the Mac production diagnostic arm is added (section 1);
  - the cache proxy's omission is preregistered (section 3);
  - there is a GPU window and a Mac Hindsight status (section 5).

  The user confirms the supersession at the freeze.
- r2 (sha256 `8c99d974…`) received GPT-6 `needs_changes`. It resolved 9 of r1's 11 findings, left 2 partly resolved (statistics specifics, token ledgers), and raised 4 new ones (1 high, 3 medium). r3 applies GPT-6's replacement text for all six; see section 11.
- The next GPT-6 review is the bundle review of section 9.
- r1 (sha256 `623efad9…`) received GPT-6 `needs_changes` (6 high, 4 medium, 1 low). This revision answers every finding; section 10 maps each one.
- It freezes only as described in section 9: after an `accept` on the complete experiment bundle, not on this file alone.
- Once frozen, it is never edited. Later changes are dated amendments.
- A result that misses a bar is a documented FAIL, never a reason to loosen the bar or rerun silently.

**Decision this experiment makes:** which durable-memory configuration each host deploys for Claude Code 2.1.283 and Codex 0.157.1. The two hosts decide separately:
- the workstation `nativestack-5975wx-20260925`;
- the Mac `mac-coordinator-64gb-20260925`.

The user decided on 2026-09-27 that the memory layer is chosen on merit and the winner supersedes ai-memory (decision record in PR #383, `docs/decisions/2026-09-27-mac-single-writer-staged.md`). Merit rules:
- license, stars, installed or incumbent status are not evidence (the user's 2026-09-26 verdict-wave direction);
- a missing result is `pending`, never `refuted`, the same rule [`2026-09-23-verdict-integrity.md`](../../docs/decisions/2026-09-23-verdict-integrity.md) applies to missing lanes.

## 1. Configurations and their roles

- **Reference (per host, frozen):** official **ai-memory v2.4.0**, the control build the user chose on 2026-09-25 for the confirmatory rerun (R1), in two configurations:
  - **C3′:** production embedder, reranker off;
  - **C4′:** the same, with ai-memory's LLM reranker.
  - The reference arm is **C4′**, ai-memory's claimed production configuration. **C3′** is a diagnostic ablation outside the decision family.
  - If C4′ cannot run, the reference arm is C3′ and C4′ is reported `pending`.
  - **Definitions (r4).** C3′ and C4′ are the A-protocol's C3 and C4 configurations run on the official v2.4.0 binary.
    - **C3′:** Qwen3-Embedding-4B (`qwen3-embedding:4b`) with the production query prefix, reranker off.
    - **C4′:** C3′ plus `AI_MEMORY_RERANKER=llm` through the openai-compat provider, model `qwen3.5-9b-64k`, reasoning `low`, 3 workers.
    - Sources: `blueprints/memory-stack/longmemeval/v4/lme_harness.py:1562-1567,1575`, v4 `PREREGISTRATION.md:46-47,221-233,289-300`.
    - More than 5% rerank fallbacks makes a C4′ result inconclusive (v4 `PREREGISTRATION.md:231-233`).
  - **Feasibility on v2.4.0, from source (r4).** Official v2.4.0 (tag object `5c4350e3`) ships the LLM reranker.
    - `crates/ai-memory-cli/src/config.rs:413-420,1744-1759` parses and validates `AI_MEMORY_RERANKER=llm`.
    - `crates/ai-memory-llm/src/reranker.rs` implements `LlmReranker`.
    - `docs/llm-providers.md:185-192` documents the behaviour.
    - The v2.4.0 docs name no specific reranker model, only "a small, fast model" (`docs/llm-providers.md:136-147`), so the reranker model stays the preregistered production one:
      - the base is `qwen3.5:9b` Q4_K_M, pinned by manifest and GGUF digest (v4 `pins.json:141-147`);
      - the v4 Modelfile is sha256 `60dbf344…`. It says `FROM qwen3.5:9b`, a mutable tag, with no template.
      - The runner therefore verifies the exact base, records the effective template and parameters, and hashes the served blob bytes.
  - **Lineage (r4).** The Mac's production build `19b6429` is 46 commits ahead of v2.4.1 and 62 behind it; v2.4.0 is its ancestor (the Mac's 2026-09-27 lineage check). The official v2.4.0 reference is therefore code that production's line descends from, not a divergent build.
  - The historical Mac C3 (0.570) ran on a 2.5-pre build `19b6429` (`evidence/artifacts/memory-stack-20260925/experiment.json`). It is descriptive only and is not this reference.
- **Deployed (descriptive only):**
  - workstation: ai-memory 2.4.1;
  - Mac: **D-mac-prod (r4)**, the Mac's production build `19b6429` in a C4-shaped configuration: production's Ollama `qwen3-embedding:4b` embedder and `qwen3.5-9b-64k` reranker. The Mac session asked for it because it is what actually runs there and carries 46 commits the reference lacks.

  Measured as labelled diagnostic arms; not in the decision family.
- **Eligibility applies to every configuration, the reference included** (section 7). The reference gains no advantage from its role, and "retention" never means qualification.

## 2. Candidates, controls and reserves (frozen identities)

**Primary candidates** (latest releases read with `gh api repos/<r>/releases/latest` on 2026-09-27; the run manifest pins each to an immutable artifact and sha256):

| Candidate | Release |
|---|---|
| [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) | v0.9.29 |
| [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | v0.10.1 |
| [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | v0.4.21 |
| [topoteretes/cognee](https://github.com/topoteretes/cognee) | v1.6.1 |
| [MemPalace/mempalace](https://github.com/MemPalace/mempalace) | v3.10.0 |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | v0.23.2 |
| [zilliztech/memsearch](https://github.com/zilliztech/memsearch) | v0.4.21 |

**agentmemory's primary arm (r4)** is its shipped Claude Code hook path, the A-protocol's D2h shape (`am-minilm-hooks`: v4 `lme_harness.py:759-784,1618-1619`; v4 `PREREGISTRATION.md:456-459,497-498`). Sessions are ingested through the plugin's shipped hook sequence, not a direct import. The pins are:
- agentmemory 0.9.29 at `2d38dafe`;
- iii 0.11.2, Linux asset `9c83c477…`;
- Node 24.21.0;
- Xenova MiniLM q8 at `751bff37`, ONNX `afdb6f1a…`, staged by v4 `lane_tools.py` `install_minilm`.

All four are in v4 `pins.json:36-39,70-77,89-93,1072-1100`. On macOS the runner records its own platform assets.

**Discovery inputs (r4).** The Mac session's five model and repository sweeps (embedders, rerankers, memory LLMs, generation models and memory systems), each Opus-verified and dated 2026-09-27, are committed under `inputs/` with sources and dates. Each is marked vendor-reported or measured. Vendor-reported scores, such as AA-LCR v1.1 and MemReranker's self-reported LongMemEval, are motivation for the candidate list only (section 8), never S3 evidence.

**Late candidates (r4).** The 32-layer landscape sweep is held for the user's Gates A and B, so this preregistration does not wait for its durable-memory survivors. Any later survivor, or any other dated discovery, is handled like a reserve admitted after confirmatory execution (section 6):
- it is exploratory until a separately frozen, dated amendment arm names it before its first run;
- it uses the same reference, lanes, thresholds and decision rule;
- it can change a host's selection only through that amendment's own frozen comparison;
- it never edits this text.

**Native no-external-memory controls, both clients:**
- **Claude Code auto memory** at 2.1.283, isolated with `--settings autoMemoryDirectory`. `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` gives the no-memory control.
- **Codex native memories** at 0.157.1 (`memories`, stable, off by default: [features/src/lib.rs](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/features/src/lib.rs)), enabled in an isolated `CODEX_HOME`.

Controls are measured with the same lanes. Unsupported cross-client behaviour is recorded as such. Being a control does not make a configuration eligible for deployment.

**Reserves**, frozen in this priority order:
1. [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) v2.2.1: local SQLite/FTS5, official Claude and Codex setup;
2. Graphiti;
3. Supermemory local;
4. MemMachine;
5. Honcho;
6. SimpleMem;
7. MCP Memory Service.

**Admission rule:** a reserve is screened for eligibility, meaning an official local install and official integration with both clients, in priority order. It is run whenever a primary candidate is ineligible, or when compute remains after the primary arms. An eligible system that is not run stays `pending`. Every winner claim is bounded to the evaluated set.

Also pending from the 2026-09-26 sweep, where only a missing vote refuted them: byterover-cli, deja-vu and total-agent-memory. They are screened with the reserves.

## 3. Dataset and adapter contract

- **Dataset:** `longmemeval_s_cleaned.json`, sha256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`, from [xiaowu0162/longmemeval-cleaned @98d7416c](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json).
  - 500 questions; 30 abstention.
  - Full track: n=470.
  - Official track: n=419, which also excludes the 51 `single-session-assistant` questions.
- **Tracks:** each track uses the upstream track-specific corpus construction, including user-text session construction and its label changes. Both are frozen as question manifests with sha256, built by upstream code at [LongMemEval @9e0b455f](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/retrieval/run_retrieval.py).
- **What candidates see:**
  - Answers, `has_answer`, gold-session labels and scoring feedback are never visible to candidates.
  - Candidates see opaque session ids. The evaluator alone holds the opaque-to-original provenance map.
- **Ranking:**
  - Artifact-to-session ranking and expansion (graph nodes, summaries and pages that reference several sessions) are frozen per adapter before any scoring.
  - Ranked source-session ids are deduplicated before top-5 selection.
  - The scorer receives the complete eligible corpus ids.
  - A system whose output cannot be mapped to source sessions gets retrieval `N/A`, never a constructed score.
- **Scorer:** upstream [`eval_utils.py` @9e0b455f](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/retrieval/eval_utils.py), unchanged, run in a pinned environment.
- **Dependence:** questions share evidence histories (465 gold-session clusters, 5 of them non-singleton), so resampling is by cluster (section 6). Some questions have up to 6 gold sessions, so a perfect `recall_all@5` is unattainable for them; this is reported, not corrected.
- **Harness and runner (r4).**
  - **Base.** The arms' adapter logic comes from the v4 driver (#386, `blueprints/memory-stack/longmemeval/v4/`), where C4 and D2h exist; v3 (#380) has neither. v4's files stay frozen and are never run on a shared host (v4 `README.md:21-24,86-93`). S3's runner is **new code**, and every change lands in new files.
  - **Isolation**, which the runner must implement before any scored run (the requirements come from the GPT-6 reviews on #386):
    - owned ports, stores, homes and caches, with lane-owned `HOME` and `HF_HOME`;
    - server readiness that checks identity;
    - process and process-group identity (pid, start ticks, boot id, executable) checked before any signal;
    - fail closed on an occupied port or unreadable identity;
    - `env -i` for vendor harnesses;
    - production services and stores are never touched. On the workstation that includes ai-memory on 127.0.0.1:49474.
  - **Embedding-cache proxy: omitted, preregistered (r4).** v4's A16.3 says the cache gives no reuse between arms, because ai-memory writes wall-clock timestamps into session pages, and stays "only for byte-identical repeats, such as infra retries", with no arm ever cache-only (v4 `PREREGISTRATION.md:566-573`). So neither the v4 proxy (sha256 `e08e11f8…`) nor #380's is used.
    - Omitting it means only that a byte-identical repeat is recomputed rather than served from the cache.
    - Each run records its embedding server's runtime and device, so a recomputation difference stays attributable.
  - **Private inputs.** S3 needs only the reranker Modelfile, which has been public since #386, and its base pin. v4's other Modelfiles, `embed_gates.json` and the v3-check ids gate v4's own driver, which S3 does not run. The runner writes and freezes its own gates in the bundle.

## 4. Lanes

**4.1 Retrieval (primary lane).**
- **Metric:** `recall_all@5` (every supporting session in the top 5) on the full track.
- **Secondary:** the official track, and `ndcg_any@5` under its upstream name.
- **Arms:** each candidate has exactly **one primary arm**: its shipped default configuration with local-only providers. Where a candidate needs an LLM (for example Hindsight retain and reflect, or cognee extraction), it uses the frozen local model in 4.5.
- **Diagnostics outside the decision family:** common-embedder arms (BAAI/bge-m3), and development runs used only to fix adapter settings, kept on a separate question split that is never scored in the confirmatory run.

**4.2 Workload cost ("is it more token-efficient?").**
- **Frozen workload:** identical recorded coding sessions from this repository's own work, frozen with sha256; a frozen recall schedule (N recalls per session at fixed points); frozen queries, context boundaries and aggregation.
- **Complete workload cost:** every token for:
  - capture;
  - writes and extraction;
  - embedding inputs;
  - recall;
  - query expansion and reranking;
  - consolidation and summarization;
  - answers where the lane has them;
  - retries.
- **Two separate ledgers, never added together:**
  - (a) `o200k_base` text counts, gpt-tokenizer 3.4.0, of injected and returned payloads;
  - (b) native per-model usage as each model reports it (cached input, uncached input, output and reasoning kept apart).

  A payload count is never added to a request total that already contains it.
- **Decision ledger (r3).** Each host freezes **one decision ledger and its non-overlapping scalar aggregation** before execution, and applies it the same way to every compared arm and to the final selection.
  - The decision ledger must be a normalized complete-workload ledger: every relevant model invocation, including internal extraction, embedding, consolidation, reranking and retries.
  - Payload-only counts (ledger a) support only a payload-size claim. They never stand in for complete workload cost.
  - If the decision ledger is incomplete for an arm, that arm's cost qualification is `pending`.
  - If the reference's cost is zero, the cost route cannot qualify. Report absolute counts and an undefined ratio.
- MCP-only paths are measured at the client tool-call boundary.
- A required cost that is unknown leaves that configuration's cost qualification `pending`. It never counts as zero.
- **Reporting:** candidate-to-reference ratios are reported only at matched quality (section 7). A configuration's being under a budget is not a token-saving claim.

**4.3 Latency and resources.**
- **Measured:** client-observed time until usable evidence is delivered, including embedding, expansion, reranking and IPC or network time.
- **Frozen per host:** corpus, request schedule, 200 requests, concurrency 1, a 20-request warm-up discarded, and the nearest-rank quantile estimator.
- **Distributions:**
  - cold (the first request after a server start, 10 starts) and warm, reported separately;
  - the **warm p95 is the gated statistic**;
  - timeouts (10 s) and failures count at the timeout value and are reported. Latency is never computed from successful requests only.
- Also measured: peak RSS, VRAM on the workstation, disk growth, ingest-to-query-ready time, and cold-start time.

**4.4 Coding-agent acceptance (both clients, official integrations only).** Order: Claude→Codex, then Codex→Claude. Isolated client profiles, with the enabled memory owners recorded explicitly. MCP-only systems must capture through real client tool calls. Required:
- capture of a unique decision, correction, failed approach and fix;
- scoped cross-client recall, with canaries in an adjacent project that must stay out;
- supersession of an updated fact;
- stored untrusted text treated as data;
- deletion, verified after restart and consolidation;
- restore into an empty instance;
- restart and interrupted-ingestion durability.

**4.5 Usefulness.**
- **(a) Coding-memory queries:** 20 frozen coding-memory queries with frozen expected evidence and semantic-success criteria, plus 5 bounded continuation tasks. Each is scored as task success under a fixed answerer and context policy.
- **(b) LongMemEval QA:** full 500 questions with one frozen local answerer, `Qwen/Qwen3-8B-GGUF` Q4_K_M, non-thinking, frozen prompt, context budget and seeds; one frozen blinded judge; a stratified manual audit of abstention and knowledge-update questions. Local-judge scores are labelled local-harness results.

The same local model serves as the extraction LLM where 4.1 requires one. Without lane 4.5, the outcome may only be described as a retrieval and lifecycle comparison.

## 5. Hosts

Each host selects and qualifies **separately**, against **its own** measured reference, with every lane (4.1–4.5).
- **Order of acceptance testing on each host:** by primary-lane point estimate, descending. Continue while any untested eligible configuration could still change that host's selection.
- **Cross-host differences** are a diagnostic, not a gate.
- **CUDA timing, VRAM behaviour, model-serving compatibility and lifecycle acceptance do not transfer to macOS**, and Mac results do not transfer back.
- **Workstation GPU window (r4).** The workstation's arms need the GPU. It is held by production vLLM embeddings on 127.0.0.1:18231 and llama.cpp generation on 127.0.0.1:18232. The runs therefore need a drained-GPU window, a scheduled production stop and restore that the user approves. The runner never stops a production unit itself.
- **Per-host qualification (r4).** Before its confirmatory run, each host records:
  - RSS, latency and co-residency of every serving model;
  - the reference reranker's latency against ai-memory's reranker timeout, since timeouts become fallbacks and more than 5% fallbacks makes C4′ inconclusive.

  The Mac's numbers come from its #379 PR.
- **Mac Hindsight (r4).** Hindsight 0.10.1 installs on the Mac but cannot start. Its `pg0-embedded` 0.15.2 Postgres is linked to Homebrew OpenSSL, and the Mac has no Homebrew. Relinking would modify the upstream artifact, so it is not a faithful arm. The macOS profile's own Postgres choice, Apple Container, needs the owner's sudo install. Until the user decides, the Mac's Hindsight arm is `pending`, not `refuted`.

## 6. Statistics (frozen before any confirmatory run)

- **Reference availability** is settled by a frozen preflight before any scoring: C4′ must install, start and return a well-formed reranked result on 5 frozen development questions. If it fails, the reference arm is C3′ and C4′ is `pending`, decided before the confirmatory run.
- **Frozen before the first confirmatory result:**
  - the question-to-cluster manifest (sha256), built by merging questions that share any gold session;
  - seed aggregation: the five paired seeds (20260927–20260931) are averaged within each question;
  - question-weighted differences;
  - the RNG (NumPy `PCG64`, bootstrap seed 20260927);
  - 10,000 cluster resamples. Each resample keeps every question of each drawn cluster.
- **"Lower 95% bound"** means the **one-sided 5th-percentile bound** of the resampled difference, using `numpy.percentile(..., method="linear")`. Two-sided 95% intervals (2.5th and 97.5th percentiles) are reported separately and decide nothing.
- **Hypothesis family, one per host, frozen before execution.** For every admitted primary candidate arm against that host's reference arm, the family holds both hypotheses:
  - superiority, H0: Δ ≤ 0;
  - non-inferiority, H0: Δ ≤ −0.02.

  Δ is the full-track `recall_all@5` difference. Each p-value is the cluster-bootstrap share of resampled Δ at or below the null bound. Holm correction runs at family α = 0.05 across all of them.
  - Missing arms cannot qualify, and they do not shrink the planned family.
  - Reserves admitted after confirmatory execution are exploratory until a separately frozen comparison.
- **Outside the family:** C3′, the deployed arms, controls, the common-embedder diagnostics, the official track and `ndcg_any@5`.
- **Missing results:** a missing arm or lane result is `pending` and is not imputed.
- **Governing statistics (r4):** these statistics govern S3 on both hosts. The A-protocol's family α values (0.0333, 0.0167), its +5 pp/−2 pp rule and its one-look-per-family rule do not transfer (section 12).

## 7. Decision rule (per host)

**Eligibility, required of every configuration, the reference included:**
1. passes every item of 4.4;
2. warm p95 latency (4.3) at most 1.0 s;
3. the decision-ledger cost (4.2) is complete, not `pending`;
4. lane 4.5 (a) results are complete for all 25 frozen tasks.

**Usefulness floor (r3), applied to both routes before the replacing set is formed.** The candidate's 4.5 (a) successes must be at least the reference's successes minus one, on the same 25 frozen tasks with the same scoring rules. Missing task results leave qualification `pending`.

**Replacement routes.** An eligible candidate that meets the usefulness floor replaces the reference by either route:
- **Superiority:** the Holm-adjusted p of its superiority hypothesis (§6) is below 0.05, **and** the observed full-track `recall_all@5` difference is at least **0.05**. This does not claim the population improvement exceeds 5 points.
- **Non-inferiority plus cost:** the Holm-adjusted p of its non-inferiority hypothesis (§6) is below 0.05, which is equivalent to the adjusted one-sided lower bound lying above **−0.02**, **and** its decision-ledger workload cost (4.2) is at most **0.80×** the reference's.

**Selection among several replacing candidates.**
- Let `qmax` be the highest `recall_all@5` point estimate among them.
- The cost-selection set is every replacing candidate with q ≥ qmax − **0.02**.
- The member with the lowest decision-ledger workload cost (the same frozen scalar aggregation for every member) is selected.
- This is a practical decision tolerance, not statistical equivalence.
- If an unknown cost could change the winner, selection is unresolved.
- An exact residual tie gives joint winners.

**If no eligible candidate replaces the reference:**
- the host keeps its currently deployed configuration, labelled "no replacement qualified";
- that label confers no qualification on the reference;
- if the reference itself is ineligible, that is reported as a finding.

## 8. What this does not claim

- Local-harness scores are not official leaderboard results.
- Vendor-published numbers are motivation only.
- A retrieval score says nothing about capture or deletion safety; 4.4 covers those.
- Agreement among reviewers, and blinding, do not validate a measurement.
- Nothing here changes a host until the winner passes a cold-copy cutover with rollback.

## 9. Freeze procedure

1. Build the experiment bundle:
   - this document;
   - the source inputs committed under `inputs/` with sha256: the GPT-6 landscape and prompt, and the Mac's 2026-09-27 model and repository sweeps (r4);
   - the dataset hash and question manifests;
   - the v4 driver (#386) as the frozen adapter source, the S3 runner (new code, section 3), its frozen gates and every adapter (r4, replacing "the harness v3 (#380)");
   - the A17 supersession amendment (section 12);
   - the analysis code;
   - client and plugin versions;
   - the model weights and quantizations (Qwen3-8B Q4_K_M and every embedder);
   - prompts, seeds, fixtures and configurations.
2. Verify that every referenced file and link exists (the decision record merged with #383).
3. Get a GPT-6 cross-family review of the **bundle**. Freeze only on `accept`, after every required finding is resolved.
4. Record the immutable commit and the bundle's sha256 list outside the worktree, then run.
5. Keep per-case outputs, failures and each arm's actual execution status.

## 10. r1 findings and their fixes

| r1 finding | Fixed in |
|---|---|
| high 1: incumbent privileged, no cheaper route, retention implies qualification | §1 eligibility applies to all; §7 two routes; §7 retention label |
| high 2: comparator, arms and test selectable after results; 2.5-pre vs 2.4.x | §1 frozen reference C4′ on v2.4.0; §4.1 one primary arm; §6 test and cluster bootstrap; §1 historical C3 descriptive |
| high 3: dataset and adapter contract | §3 |
| high 4: token units and accounting | §4.2 |
| high 5: CI overlap is not a tie | §7 qmax − ε selection |
| high 6: Mac subordinate, no Mac costs | §5 per-host selection with all lanes |
| medium 7: freeze binds the whole bundle; accept required | §9 |
| medium 8: latency definition | §4.3 |
| medium 9: usefulness lane | §4.5 |
| medium 10: native Codex control | §2 |
| low 11: reserve admission and engram | §2 |

## 11. r2 re-check findings and their fixes (r3)

| r2 re-check finding | Fixed in |
|---|---|
| partly resolved r1-2: cluster assignment, weighting, seed aggregation, RNG, C4′ preflight | §6: frozen preflight, cluster manifest, seed averaging, question weighting, PCG64 seed |
| partly resolved r1-4: payload ledger promoted to complete cost; aggregation undefined | §4.2 decision ledger; §7 routes use it |
| new medium 1: "lower 95% bound" ambiguous | §6: one-sided 5th percentile, `numpy.percentile(method="linear")` |
| new medium 2: non-inferiority escapes Holm | §6: per-host family holds both hypotheses; Holm at α 0.05 |
| new medium 3: payload fallback changes the winner | §4.2: payload counts support only a payload-size claim; incomplete ledger means `pending` |
| new high 4: superiority bypasses usefulness | §7: usefulness floor before either route |

## 12. Relationship to the A1–A16.3 protocol and A17 (r4, proposed)

- **What A17 was.** VelaNext was retired, so the confirmatory rerun R1 of the frozen memory-stack protocol (A1–A16.3, v3 #380 and v4 #386) needed another host and a new amendment naming it before any run (`docs/decisions/2026-09-25-retire-vela-velanext.md:36-44`). The workstation took R1 as "A17" (`docs/decisions/2026-09-25-workstation-sota-refresh.md:542-546`; issue #274). No A17 text was ever written, and no session holds a draft (checked 2026-09-27).
- **Why S3 supersedes it without spending a look.** No confirmatory arm of A1–A16.3 has ever run on any host: no C3′, C4′, C4 or D2h result exists (`retire-vela-velanext.md:43-44`; `catalogs/foundation/memory-stack-20260925.json:1318`; `docs/decisions/2026-09-27-mac-single-writer-staged.md:48`). Retiring R1 in favour of S3 therefore consumes no confirmatory look and selects nothing after seeing results.
- **What carries over.** The user's 2026-09-25 choice of official ai-memory v2.4.0 as the control (issue #274; `workstation-sota-refresh.md:228`) becomes S3's reference, and the A-protocol's C3/C4/D2h configurations become S3's C3′, C4′ and agentmemory arm (sections 1 and 2). The historical Mac C3 on `19b6429` stays descriptive.
- **What does not carry over.** The A-protocol's statistics and decision rules (section 6), its v4 = v3 reproduction gate and its VelaNext-only drivers. S3's own gates, runner and statistics replace them.
- **The amendment.** `blueprints/memory-stack/longmemeval/A17-SUPERSESSION.md` records this as a dated amendment in the protocol's own lineage, a new file, since frozen text is never edited. It is **proposed**. It takes effect only when the user confirms it at the S3 freeze (section 9). Until then nothing runs under either protocol.
