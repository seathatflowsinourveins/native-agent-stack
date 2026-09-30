Source: <scratch>/s3-r6/repair/claude-review.md; capture date: 2026-09-27.
I found four high-severity defects: two need new text (the self-written harness and the GPT-6 pacing), and two are pre-freeze blockers (stale sources and the latency gate). r6 should not freeze as written.

- **G (full 470 questions):** honest but not feasible. The arithmetic is exact (54.05M, 270.25M, 2.162B and 4.324B, recomputed in code and labelled as scenarios). But r6 gives no wall-clock projection and adds a pacing limit that no source supports.
- **F and H (research-memory tasks and lifecycle probes):** genuinely sourced. Every RM01–RM08 number sits at its cited README line, and every decision-index anchor falls inside the right record: edgartools (6330, 6352), LEAN (17233, 17248), alpaca-py (1592) and skfolio (19176). My first attribution pass suggested otherwise, but that came from a bad lookup method, not the file.

`P:n` below means line n of `<scratch>/wt-s3/blueprints/memory-layer-s3/PREREGISTRATION.md`.

## High

**H1. Source keys I and R are stale, and R changed too (§14, P:444–445).**
- **Defect:**
  - s3-r6-inputs.md now has sha256 `30eb565f…` and 58 lines; r6 records `b0a99fe4…`, lines 1–38.
  - gateway-ab-designs.md now has sha256 `7deb3208…` and 101 lines; r6 records `27e45209…`, lines 1–84. You flagged only the inputs file; this second change is new.
  - The captured versions no longer exist at those paths, so §9 step 2 ("every referenced file exists") fails.
  - R gained a block, "Harness: upstream, not self-written" (R:14–28), which r6 never absorbs.
  - Old R:14–36 appears to have moved to R:30–52 (inferred from content; please verify). So P:67's "R:14–36, especially 24–36" now points at the statistics block.
  - I's Hindsight lines moved from 36–38 to 55–57; r6 cites them at P:149, P:268 and P:460.
  - The M, J and G hashes still match.
- **Replacement:** "I: s3-r6-inputs.md:1–58, sha256 `30eb565fd95d78570ae7e499ebc540a415a79cbba0fb75d1b40796fd17289555`. It supersedes the overwritten `b0a99fe4…` capture. Live deployments are I:36–53; Hindsight is I:55–57. R: gateway-ab-designs.md:1–101, sha256 `7deb3208e7717005e6b9d2d40cfde72d4f16d0e1cfc24827684f8db718e2ea09`. Arm rules are R:6–10, the upstream-harness rule R:14–28, and R02 R:30–52." Then remap every I: and R: locator.

**H2. The runner is self-written (§3 P:181; §9 P:375).**
- **Defect:** "S3's runner is **new code**" contradicts the user's direction ("…rather than self written test"). It also contradicts W3: "Planned S3 runner… replaced"; "should not be filled by inventing another harness" (report.md:9, 52–70, 128).
- **Source:** AMB's registry at `03c1d0f1` ships cognee, Hindsight (including an HTTP provider) and bm25 providers. AMB's `cli.py` exits without GEMINI_API_KEY or GOOGLE_API_KEY (`_resolve_gemini_key`), and loads `.env` with `override=True`.
- **Replacement:**

  > "S3 writes no standalone runner. Orchestration is AMB `03c1d0f1d27da63034f0931121c858faba512383`, unmodified. Its cognee and Hindsight HTTP providers target the isolated containers of §2.1. The other five primaries and the reference are added only as frozen, hashed AMB MemoryProvider modules. AMB's answer assertions and retrieval-mode scores are not S3 results. Providers export ranked opaque session IDs, scored by unchanged LongMemEval `eval_utils.py` @9e0b455f. AMB's loader must consume the pinned file (sha256 `d6f21ea9…`); the official user-text track is a provider ingest parameter. Recorded upstream defects: (1) the Gemini-key exit — use AMB's Python runner, or a non-secret placeholder with Google egress blocked plus wire proof that no Gemini call occurs; (2) no `.env` in the checkout. AMB is maintained by Hindsight's vendor (vectorize-io), so a pre-freeze parity audit shows every provider uses its native ingest and recall at equal depth. The §3 isolation rules bind every process AMB drives."

**H3. The G pacing is unsourced and the run may not be feasible (§4.2 P:237–239).**
- **Defect:**
  - "One in-flight GPT-6 request per host, two across S3, one per second" cites R:26–32. Those lines are R02's arms and metrics and say nothing about pacing.
  - It contradicts the user's recorded 2026-09-27 decision: "gpt6 can run with full parallel utilization… run them parallel" and "do not adopt… throttles" (memory `provider-limits-and-logins.md:17–25`; historical evidence, not authority).
  - The harness cannot enforce it on concurrency inside the systems themselves (Hindsight `*_LLM_MAX_CONCURRENT`; ai-memory's reranker caps at four).
  - There is no throughput or wall-clock projection.
- **Illustration only (one 7-call canary at ~1K tokens per call; larger chunks change it):**
  - I:34's canary gives about 145 input tokens/s at one call in flight.
  - That is about 104 h per ingest pass and about 22 days for five passes, per GPT-6-ingesting system per host.
  - Combined with "no cost-driven subset… never shorten the run" (P:306, P:239), this invites post-hoc truncation.
- **Replacement:**

  > "Concurrency is a frozen throughput parameter, not a quota gate. Use K in-flight GPT-6 calls per host, with K chosen on the development split from measured throughput and fresh 429s. Set it via each system's supported knobs, record it as a departure, and verify it from call_logs. Use a block-randomized dispatch order, identical across arms. Before the freeze, state measured development tokens/s and the projected wall-clock per host. If the projection exceeds [user-set window], adopt G's stratified subset with its prospective power calculation, decided before any result. Seeds replicate only stochastic components; an arm that is deterministic by source review is ingested once and counted once."

**H4. GPT-6 in the query path versus unchanged latency gates (P:42, P:239, §4.3, P:307, P:331, P:350).**
- **Defect:**
  - r6 moves C4′'s reranker, and any query-rewriting or LLM-reranking role, to gateway GPT-6.
  - It does not restate the consequence under unchanged gates: warm p95 ≤ 1.0 s for every configuration including the reference, the 10 s timeout, and >5% rerank fallbacks making the host unresolved.
  - ai-memory v2.4.0 documents the reranker as "an LLM call on the search hot path… On any error or timeout… preserves the fused order" and "saturated queries keep their local ranking without waiting."
  - "Measure client-observed queueing" (P:239) lets other arms' calls holding the host slot leak into an arm's latency.
  - The exact GPT-6 rerank latency is unmeasured (my inference), but the incoherence stands regardless of the number.
- **Replacement:**

  > "§4.3: query-path GPT-6 calls are inside the gated warm p95. The 1.0 s bar and 10 s timeout are unchanged, and a native query path requiring GPT-6 may be latency-ineligible; this is declared before execution. The latency lane runs with no other arm's call in flight on that host, and queue wait is reported separately. §6 preflight (a justified change to r5's 'settles only whether C4′ can run'): because r6 replaces C4′'s local LLM, the preflight also measures C4′'s fallback rate and warm p95 on the development split under the frozen envelope. If fallbacks exceed 5%, the reference is C3′ before any confirmatory run."

## Medium

**M1. Bind the statistics to scipy/statsmodels (§6; §7 P:339).**
- **Source:** W5 (report.md:82–96); R:24–28. In scipy v1.18.1, `n_resamples` defaults to 9999, and the confidence interval goes through `stats.quantile` (`_resampling.py:663`).
- **Replacement:**

  > "Estimand unchanged, using scipy==1.18.1 and statsmodels==0.15.0. Use per-cluster arrays: s = the sum of seed-averaged question Δ, and n = the question count (452 clusters).
  > `res = scipy.stats.bootstrap((s, n), lambda s, n, axis=-1: s.sum(axis)/n.sum(axis), paired=True, vectorized=True, n_resamples=10000, method='percentile', confidence_level=0.95, alternative='greater', rng=numpy.random.Generator(numpy.random.PCG64(20260927)))`.
  > Bound = `numpy.percentile(res.bootstrap_distribution, 5, method='linear')`. p_sup = share ≤ 0; p_NI = share ≤ −0.02.
  > Holm = `multipletests(p, alpha=0.05, method='holm')` over all 14 planned hypotheses, with p = 1.0 for missing arms so m stays 14.
  > A cluster sign-flip `permutation_test(permutation_type='samples')` for superiority is reported but decides nothing."

  In §7, delete "equivalent to the adjusted one-sided lower bound", which is undefined.

**M2. The call envelope is over-strict in one place and unimplementable in another (§1.2 P:73–74; P:152).**
- **Temperature rule:**
  - The pinned `shouldDeduplicate` (requestDedup.ts @a58000c7) returns false when `stream === true`. It treats an absent temperature as 1.0 and deduplicates only at ≤ `maxTemperatureForDedup`.
  - So an explicit 1.0 is gated exactly like omission, as I:30–31 already say. This corrects the brief's rule A as well as r6's "Temperature 1.0 alone does not replace this rule."
  - In-flight dedup also needs concurrent identical requests, which r6's own pacing rules out. As written, the rule can push cognee to `pending`.
- **Static headers:** cognee's `LLM_ARGS` and Hindsight's `HINDSIGHT_API_LLM_DEFAULT_HEADERS` (config.py:176) are process-static.
  - Nothing implements r6's "resolved at conversation/call scope".
  - cognee-live's 13 calls on one account (I:44) confirm static headers pin affinity, consistent with R:7.
- **Undefined unit:** "Conversation" is not defined for ingest.
- **Replacement:**

  > "Every call sends `X-OmniRoute-No-Cache: true` and is dedup-ineligible: `stream: true`, or a resolved temperature that is absent or > 0.1, verified at the wire. Idempotency-Key is fresh where per-call headers exist; a static key is not fresh. Before choosing between an absent and a constant key, read the pinned idempotency.ts key composition (chatCore.ts:763–765 shows messages feed the digest), and prove no replay in call_logs. A conversation is one question × seed × arm run. Route (a): one fresh arm process per run, carrying that run's key (about 18,800 starts per host). Route (b), Hindsight only: no static session header, and `HINDSIGHT_API_{OP}_LLM_CACHE_AFFINITY=openai_prompt_cache_key` (config.py:180, 403), pending a wire check of the value sent."

**M3. The live deployments are not absorbed (§2.1, §3; I:36–53).**
- **Replacement:**

  > "Live services are hosting evidence only; they are never scored or touched. cognee-live runs from the pinned digest on rootless Docker 29.8.1 at 127.0.0.1:3800, auth on. hindsight-live is a systemd --user unit on 3710/5433 (pg0). Archive sanitized copies of both deploy receipts. Add 3800, 3710 and 5433 to the fail-closed port list. The path 10.0.2.2:20128 is the candidate container-to-host transport; re-verify it per arm. Live envelopes use static session headers, so they are not scored envelopes. hindsight-live's stale-`postmaster.pid` guard is a local lifecycle modification: a scored arm does not inherit it silently, and the unguarded first failure counts as H evidence. Use upstream knob names `HINDSIGHT_API_{RETAIN,REFLECT,CONSOLIDATION,MENTAL_MODEL_REFRESH}_LLM_{MODEL,REASONING_EFFORT}` (config.py:383, 401, 426, 440, 460), not the input's `{…}_REASONING_EFFORT`. Set `HINDSIGHT_API_LLM_TEMPERATURE=none` and leave `HINDSIGHT_API_LLM_TEMPERATURE_{RETAIN,REFLECT,CONSOLIDATION,VERIFICATION}` unset: per-operation values override the global (config.py:212), and the shipped defaults are 0.1/0.9/0.0/0.0 (config.py:242–245)."

  This replaces P:149's "temperatures are explicitly frozen".

**M4. The R02 effort-selection rule is underspecified (P:67).**
- **Defect:** "Role quality", "significant" and "paired lower bound" have no stated metric, sample size, test or alpha. It does not say whether coupled roles are selected jointly, whether selection runs per host, or what happens to an unresolved role after the freeze.
- **Replacement:**

  > "Before the first development call, freeze, per role or coupled role set: LoCoMo full-system supporting-evidence recall@5 plus schema validity; n; a one-sided cluster bootstrap at 0.05 (the M1 binding); joint selection for coupled roles; and runs on each host. An arm with an unresolved role is pending, and needs a dated amendment before its first confirmatory run."

**M5. Other self-written evaluation pieces (4.5(b) P:272; 4.1 P:200).**
- **Source:** LongMemEval `evaluate_qa.py:24` `get_anscheck_prompt`, which includes the abstention case. Its call path runs at temperature 0 (L108), which is cache- and dedup-eligible at the gateway. W4: MTEB 2.21.8 registers LoCoMo and documents two-stage reranking (report.md:72–80).
- **Replacement:**

  > "The judge prompt is `get_anscheck_prompt`, unchanged, sent to Astra max under §1.2, not through evaluate_qa.py's call path. The embedder and reranker check runs MTEB 2.21.8's LoCoMo task, with the metric frozen first."

## Low

- **L1. User approval dropped from the GPU window (§5 P:295).** r5 said "a scheduled production stop and restore that the user approves"; r6 dropped "that the user approves". Restore it.
- **L2. Coordinator text attributed to the user (§14 P:449; §5 P:301–302).** Requirements A–I are the coordinator's brief; only directions 1–4 are the user's words. Split U into U (directions 1–4) and a separate key for the brief, which relays the Apple Container 1.4.1 / Postgres 18.6 / pgvector 0.8.6 and 12/12 claims. Require the Mac's own receipts in the bundle before freeze.
- **L3. agentmemory's MiniLM exception is mis-framed (P:93, P:199).**
  - **Defect:** r6 frames it as "no alternative" at provider level, but §4.1 says "wherever upstream supports configuration".
  - **Replacement:** "MiniLM stays primary by user requirement C — a user-directed exception to E, although agentmemory supports an OpenAI-compatible embedder."
- **L4. Achieved power is not stated (P:306).**
  - **Illustration** (normal approximation, n=470, 10–30% discordant questions, seeds ignored): an exactly equivalent arm clears the −0.02 non-inferiority bar with probability 0.20–0.39 at α 0.05, and 0.03–0.09 at Holm's first step (0.05/14).
  - **Replacement:** "Report achieved power for both routes from the frozen analysis code over a stated discordance range; this is information, not a gate or a margin change."

## What is correct
- Requirements A–I each landed: status line, GPT-6 role contract, `-max`, compression off, effort columns (§1.1–1.2), Astra-max answerer and judge with the manual audit kept, per-arm isolation, seven primaries and C4′ kept, Mem0 and Attemory ineligible on fit, the GBrain screen, BM25 and dense Qwen3 diagnostics, and the Mac "runnable" note.
- F's numbers match the cited READMEs: data-readiness 12, 15, 17–18, 38–40; simulation-research 22–23, 41–42; identity-readiness 50, 79, 90, 97, 114–120; catalyst-provenance 3–6, 11, 69–70. North-star 33–35, 57–60 and 74–79 support the justification.
- The early lifecycle checks are backed by the merit synthesis (M:44, 127, 137–138). At the Hindsight pin, models.mdx says "at least 65,000 output tokens" and requires `RETAIN_MAX_COMPLETION_TOKENS` > `RETAIN_CHUNK_SIZE` (3000).
- The statistics are preserved: 452/401 clusters, PCG64 seed 20260927, 10,000 resamples, a linear 5th-percentile bound, Holm at α 0.05 over 14 hypotheses, +0.05/−0.02 thresholds, and the minus-one usefulness floor. r5's accepted fixes (§10, §11, §13) are all present.
- The development split is LoCoMo with overlap checks, the answerer and judge are fixed rather than selected, and the two hosts decide separately.
- Spot-checked at their pins and true: Hindsight's per-operation env names and its `none` temperature setting, cognee's "Keys given directly in LLM_ARGS win", and ai-memory's reranker behaviour.

## Verification gaps
- I did not parse the workflow journal (J). Claims resting only on J are not re-checked: agentmemory's key precedence, the image digests, the GBrain changelog lines and the Mem0/Attemory lines.
- I did not spot-check the embed.md and rerank.md locators.
- I did not read OmniRoute's `idempotency.ts`.
- GPT-6 rerank latency and throughput are unmeasured.

TOKEN TOOLS USED: ctx_batch_execute/ctx_execute: hashing inputs, the r5→r6 diff, decision-index and README line checks, pinned upstream greps via curl, arithmetic; Read: artifact, brief, inputs, report, memory file; Grep: ai-memory repository URL.