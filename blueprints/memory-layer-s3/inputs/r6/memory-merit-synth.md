Source: <scratch>/memory-merit-synth.md; capture date: 2026-09-27.
## Is Hindsight the best memory system for this stack?

**Provenance.** This draws on two Claude research lanes and one refuter pass, all dated 2026-09-27. Every claim was confirmed by the refuter against its cited source, except those marked *(not verified)*.
- The GPT-6 cross-family research job did not run. Its lane refused the network step and returned only a read-only readback of the repository catalogs, so this answer has no cross-family research vote.
- Both research inputs arrived truncated. Nothing from the missing parts is used.
- "S3" means `blueprints/memory-layer-s3/PREREGISTRATION.md`, DRAFT r5 (not frozen), on `origin/claude/memory-layer-s3-prereg-20260927` @ 75e30ea4. I read it directly with `git show`.

### 1. Direct answer

**The evidence does not show Hindsight is the best, and it does not show Hindsight is below its peers.** The refuter ran 18 dominance checks, in both directions, and every one returned `holds=false`. Hindsight has earned a place in S3; it has not earned a verdict.

On your second point: no system in this set is clearly worse than its peers. Two should get no further effort, but because they don't fit this stack, not because they lose on merit: Mem0 OSS and Attemory (see §3).

**The first caveat: none of Hindsight's published numbers is for the pinned v0.10.1.**
- The paper ran v0.1.0 (vendor blog `2026-03-23-agent-memory-benchmark.mdx:92` @ v0.10.1).
- The vendor-harness (AMB) 94.6% ran 0.4.x. Its `uv.lock` pins hindsight-api 0.4.15 and hindsight-all/embed 0.4.17; the blog says 0.4.19.
- The independent full rerun ran 0.4.17.
- The only same-judge comparison (OAMB) ran 0.9.2.

**Dimension by dimension**

1. **Published performance**
   - For:
     - It has the highest score in the only same-model, same-judge comparison of several systems. OAMB used 60 balanced LongMemEval-S questions with DeepSeek V4.1 Flash in every role: Hindsight 57/60, Mem0 OSS 52, OpenViking 51 (github.com/rocke2020/open-agent-memory-benchmark @03509051, 2026-09-13; third party, affiliation not verified).
     - An independent full-500 rerun scored 448/500 (89.6%) on a DeepSeek stack with API 0.4.17, with about 2 pp run-to-run drift. The author calls it a provider variant, not a reproduction (rocke2020/agent-memory-benchmark, branch `deepseek-provider` @b6eac3db, 2026-08-22).
     - Vendor paper, LongMemEval-S QA with a GPT-OSS-120B judge: 83.6% with GPT-OSS-20B, 89.0% with GPT-OSS-120B, 91.4% with Gemini-3 Pro answering. Full-context GPT-OSS-20B scores 39.0% (arXiv 2512.12818v1 Table 3, 2025-12-14; vendor plus co-authors).
     - Vendor harness AMB: LongMemEval-S 94.6% (473/500), LoCoMo10 92.0% (1417/1540), BEAM-10M mean rubric score 0.6408 with 147/200 passing (github.com/vectorize-io/agent-memory-benchmark @03c1d0f1).
   - Against:
     - The OAMB lead is not significant: exact McNemar p = 0.125 against Mem0 and 0.070 against OpenViking. The report's own status is `no_clear_accuracy_leader`.
     - No retrieval recall has been published for LongMemEval, LoCoMo or BEAM, so Hindsight cannot be placed on S3's metric at all.
     - Two README v0.10.1 claims are refuted: "most accurate agent memory system ever tested" (line 44), and "independently reproduced" by Virginia Tech and The Washington Post (line 50), since both institutions are co-author affiliations.
     - Paper Table 3 mixes judges: its Zep, Supermemory and full-context GPT-4o columns are copied from Supermemory's GPT-4o-judged report.
     - The AMB 94.6% run used 43,624.5 context tokens per question. That is 1.88× the vendor's own hybrid-search control, which scored 74.0% with 23,221.7 tokens under the same answerer and judge.
     - The 91.4% and 94.6% results both depend on hosted Gemini answerers.
2. **Local by default: against.** The default LLM provider is `openai`, falling back to gpt-4o-mini. Only the embedder (bge-small-en-v1.5), the reranker (ms-marco-MiniLM-L-6-v2) and the pg0 database are local (`hindsight_api/config.py` @ v0.10.1, lines 1082, 1084, 1119, 1204-1205, 1264-1266). agentmemory (in keyless mode) and MemPalace are local by default.
3. **Both-client integration: tie.** Hindsight has official hooks plus MCP for both Claude Code and Codex, as agentmemory and MemPalace do. That puts it ahead of Mem0, whose plugins need a hosted key. The refuter did not re-read Hindsight's installer or hook files.
4. **Write cost and serving weight: against by design, but not the worst measured.**
   - Every retain runs LLM extraction, plus Postgres and a worker. agentmemory and MemPalace write with zero LLM calls.
   - In OAMB, however, Hindsight indexed fastest of the three: median 761 s from indexing to ready per history, against 842 s for Mem0 OSS and 1,190 s for OpenViking. It used 58.44M indexing tokens for 60 histories (only partly counted).
   - No full LongMemEval-S ingest time exists (see misquote c). The catalog's ~86 h is an unverified projection.
5. **Maintenance: middle of the pack.** Releases since 2026-07-29: Hindsight 6 core releases; agentmemory 1, MemPalace 5, Honcho 1, Mem0 9 (Python), OpenViking 23, ai-memory 43, GBrain 109 (`gh api …/releases`, 2026-09-27).
   - Open issue #4696 is not a default-configuration hang. The reporter retracted the 1-document observation (recall takes about 8 s there) and traced the problem to a qwen3-reranker-8b they had chosen, running on CPU (https://github.com/vectorize-io/hindsight/issues/4696).
6. **Lifecycle: for.** It has the richest set of lifecycle features here: supersession on re-retain, reversible invalidation, bank export and import in restore or merge mode, and cloning. None of these was exercised.
   - The peers' gaps are confirmed. agentmemory has #1273 open (governance delete deletes nothing) and #1190 open (restore is additive). MemPalace has no verified restore, and its "contradiction detection" is exact-match deduplication (arXiv 2604.21284).

**How S3 decides, and where that leaves Hindsight.** S3 chooses on full-track `recall_all@5` and workload cost. Candidates must first pass eligibility gates (the §4.4 lifecycle acceptance items and a 1.0 s warm-p95 latency limit) and a usefulness floor (§7). End-to-end QA, where all of Hindsight's published strength lies, is not the deciding lane. Its lifecycle strength counts at the §4.4 gate.

**Why these numbers cannot be compared**
- Metric: QA accuracy (Hindsight, Mem0, Honcho, Zep, OAMB) is not session `recall_all@5` (S3's metric), and neither is `recall_any@5` (the agentmemory and MemPalace vendor figures). `recall_any@5` counts a hit when any one gold session is in the top 5, so it is easier.
- Judge and answerer:
  - GPT-OSS-120B in the paper;
  - gemini-2.5-flash-lite judging gemini-3.1-pro-preview in AMB;
  - GPT-5 for Mem0 OSS;
  - GPT-4o for Honcho, Zep, Supermemory, Mastra, GBrain's QA, and the baselines copied into Hindsight's Table 3;
  - DeepSeek for OAMB and the rocke2020 rerun.
- Question set: the paper, AMB and Mem0 use the original 500 questions, including 30 abstention questions. S3 uses the cleaned 470-question full track.
- Context budget: AMB Hindsight used 43.6K tokens per question against 23.2K for its control. Mem0 Platform used the top 200 memories. In OAMB, Hindsight used 15.91k tokens and Mem0 6.54k.
- Aggregation and hosted parts: Mastra's 94.87% is an unweighted mean of category scores (468/500 = 93.6% per question). GBrain's 95.53% used hosted OpenAI embeddings and a Voyage reranker.

**The only comparisons that hold up**
- Our own harness (Mac, descriptive only):
  - agentmemory with local MiniLM scored 0.821 `recall_all@5` against the historical ai-memory C3 at 0.570: +0.251, 95% CI [+0.203, +0.299], Holm p 0.0001.
  - agentmemory's keyless default scored 0.617 (+0.047, p 0.52).
  - Plain BM25 (0.747) and dense Qwen3 (0.753) also beat C3 in the same harness (`~/code/native-agent-stack/evidence/artifacts/memory-stack-20260925/experiment.json`, observations 16-20).
  - Ingestion went through REST, not the shipped hooks. C3 ran on a 2.5-pre build, not S3's v2.4.0 reference (S3 line 57).
- OAMB, as above: same model and same judge, no clear leader. Mem0 ran with OAMB's own temporal extraction prompt.
- Roughly comparable: MemPalace 96.6% against agentmemory 95.2% vendor `recall_any@5`. Both use the same dataset file, metric and MiniLM embedder, but how MemPalace built its corpus is unclear.
- Roughly comparable: Zep 71.2% against Mastra OM 84.23%, EmergenceMem 82.4% and Supermemory 81.6%, all with a gpt-4o answerer and judge (arXiv 2501.13956v1). These were run by different vendors about a year apart.

### 2. Systems that remain competitive

| System | Retrieval evidence (metric) | Local by default | Both clients | LLM calls on write | Serving weight | Releases since 07-29; confirmed open bugs | Lifecycle |
|---|---|---|---|---|---|---|---|
| Hindsight v0.10.1 | None; QA only. OAMB 57/60 (on v0.9.2) | No (`openai`) | Hooks + MCP (tie) | Extraction on every retain; OAMB 761 s per history | API + worker + pg0 Postgres + local embedder and reranker + LLM | 6; #4696 (seen with a non-default 8B reranker) | Richest; not exercised |
| agentmemory v0.9.29 | `recall_all@5` 0.821, our measurement, 470-question full track (local MiniLM, REST path); keyless default 0.617 | Yes, keyless; 0.821 needs `EMBEDDING_PROVIDER=local` | Hooks + MCP (tie); shipped-hook equivalence unproven | None | iii engine + server, no Postgres | 1; #1389 (iii engine OOM) | Delete (#1273) and restore (#1190) broken, both open |
| MemPalace v3.10.0 | Vendor `recall_any@5`: 96.6% raw, 98.4% hybrid v4 (450 held-out); palace modes 84.2% / 89.4% R@5 (maintainer-reported); our `recall_all@5` re-score 0.857 / 0.887 *(not verified)* | Yes | Hooks + MCP (tie) | None | Lighter than Hindsight (ChromaDB) | 5; P0 #1581 (HNSW corruption) | No verified restore; contradiction detection is exact-match dedup |
| OpenViking v0.4.21 | None; OAMB 51/60 (on v0.4.19) | Uncited | Hooks + MCP *(peer lane, not verified)* | VLM/LLM extraction; OAMB 1,190 s per history, 58.22M tokens for 60 histories | OAMB median retrieval 0.79 s (Hindsight 0.17 s) | 23 | Uncited |
| GBrain v0.59.0.0 | Vendor `recall_all@5` 95.53% (449/470) on S3's exact metric and split, using hosted embeddings and reranker; cannot be ranked against 0.821 | Not shown; local path unmeasured | Plugins for both *(peer lane; Codex hooks not verified)* | *not verified* | *not verified* | 109 | *not verified* |

- **Mem0 OSS v2.2.1** is competitive on QA: 52/60 in OAMB, and 91.0% vendor-reported under a GPT-5 judge. But it defaults to OpenAI, and its official Claude Code and Codex plugins (hooks plus MCP) require a hosted Mem0 Platform key (`docs/integrations/codex.mdx` and `claude-code.mdx` @ v2.2.1). It therefore fails this stack's local, both-client requirement. The 73.8% re-run tested the hosted Platform, not OSS, and was run by a competitor (Maximem, 2026-05-27).
- **Reference, ai-memory:** 43 releases since 07-29. S3's reference is the official v2.4.0 C4′ configuration, which has never run (`~/code/native-agent-stack/docs/decisions/2026-09-27-mac-single-writer-staged.md:48`).

### 3. Clearly dominated systems: none

All 18 dominance checks returned `holds=false`, so nothing is dropped on merit. The catalog's rejects are not merit findings either:
- Honcho, OpenViking and Basic Memory were rejected on AGPL grounds (license is excluded under your rule), and all three share one copied rationale (`~/code/native-agent-stack/catalogs/foundation/memory-stack-20260925.json` lines 401, 438 and 475).
- The Letta reject names no peer that beats it.

**Insufficient evidence, not dropped**
- cognee (S3 primary): no confirmed figure; the peer lane's entry was truncated.
- Basic Memory (S3 primary): internal vendor figures only (recall@5 0.951 on a 60-question subset; LoCoMo recall@5 0.745, then 0.823 after a fix).
- memsearch (S3 primary) and engram (reserve 1): no published benchmark.
- Honcho (reserve 5): vendor QA only. LongMemEval-S 90.4% under a GPT-4o judge, where Gemini 3 Pro with full context alone scores 92.0% (plasticlabs.ai, 2025-12-19).
- Graphiti/Zep (reserve 2): its 71.2% trails peers using a gpt-4o answerer, but those peers' other dimensions are uncited. It is a poor fit, not a dominated system.
- Supermemory (reserve 3): cross-judge figures only; its page's gpt-4o QA row repeats its Recall@20 value (97%).
- MCP Memory Service (reserve 7): R@5 of 86.0%, without saying whether that counts any or all gold sessions.
- Letta server: retired.

**Ineligible for this stack, not dominated**
- Attemory: vendor `recall_all@5` of 0.9638, the highest in the set. It has no capture hooks, no Codex plugin, and takes about 21 s per query (vendor figure), against S3's 1.0 s warm-p95 gate (line 254).
- Mem0 OSS: its plugins need a hosted key.

**Not assessed in this wave:** MemMachine, SimpleMem, claude-mem, MemOS, byterover-cli, deja-vu, total-agent-memory.

### 4. S3 arm set and screening order (the S3 owner decides)

S3's frozen protocol picks each host's winner, not any number above. S3 treats vendor numbers as "motivation only" (line 286) and never as S3 evidence (line 92). S3 is still DRAFT r5 and freezes only after a GPT-6 `accept` on the whole bundle (lines 3 and 304), so arm changes can still go into r6.

**What the evidence supports for the arm set**
1. Keep all seven primary candidates (agentmemory, Hindsight, OpenViking, cognee, MemPalace, basic-memory, memsearch) and the v2.4.0 C4′ reference. The evidence gives no reason to drop any of them.
2. Don't add Mem0 OSS or Attemory. Both fail S3's admission rule, which requires an official local install and official integration with both clients (line 115). That is a fit problem, not a merit one.
3. Screen GBrain for admission.
   - It is the only system that publishes S3's exact metric on S3's exact split.
   - The catalog's reason for setting it aside, "Chunks are not sessions" (`memory-stack-20260925.json:280`), is contradicted by GBrain's CHANGELOG [0.48.4.0], lines 2042-2045, which define `recall_all@5` at session level.
   - Its figure depends on hosted parts and its local path is unmeasured, so it must pass admission before it can be run. That can happen in r6 or through a late-candidate amendment (lines 94-98).
4. Add plain BM25, and possibly dense Qwen3, as diagnostics outside the decision family. In the historical harness both beat C3 and agentmemory's keyless default. Running them shows whether a candidate adds anything over a plain retriever.
5. For the Hindsight arm:
   - Freeze how its recalled facts map back to source sessions. Output that cannot be mapped scores retrieval `N/A` (line 136), and no run has ever reported session recall for Hindsight.
   - Pin both the core (0.10.1) and the capture package, `integrations/coding-agents/v0.7.0` @ 0c0869b7. The Mac sweep notes that `releases/latest` does not show that package.
   - The Mac arm stays `pending`: pg0-embedded is linked against Homebrew OpenSSL (line 227). That comes from the Mac session.

**Screening order.** S3 §5 already orders acceptance testing by the primary-lane point estimate (line 218). For the order of execution, the evidence supports:
1. The §6 reference preflight: C4′ on 5 frozen development questions (line 231).
2. The zero-LLM arms:
   - agentmemory with `EMBEDDING_PROVIDER=local`, plus the shipped-hook equivalence proof S3 requires (lines 81-82);
   - MemPalace, after freezing which mode its shipped hooks actually use, since the published figures are for raw and hybrid modes.
   - Probe their §4.4 deletion, restore and durability items early, either as development checks (line 164) or through an r6 order change. agentmemory's #1273, #1190 and #1389, and MemPalace's P0 #1581, hit those items directly and could disqualify an arm whatever its recall.
3. basic-memory and memsearch. There is no comparable evidence for either, and their write cost is not verified.
4. The LLM-extraction arms in the drained-GPU window (line 221): Hindsight on the workstation, OpenViking and cognee.
   - They use the frozen Qwen3-8B Q4_K_M as their extraction model (lines 163 and 211).
   - Measure each one's local ingest rate on development questions first, because no full LongMemEval-S ingest time exists for any of them.
5. Reserves in the frozen order (lines 106-117).
   - Graphiti and Supermemory will probably fail admission, because the lanes report no official plugins for both clients *(not verified)*.
   - Honcho's status is disputed: the peer lane reports first-party plugins for both clients, while the Mac sweep says "SDK-based". The admission screen will settle it.

**Check before the freeze (lane claims the refuter did not check)**
- The peer lane reports that Hindsight needs an LLM supporting at least 65,000 output tokens (`models.mdx:156`). Check this against the frozen Qwen3-8B Q4_K_M.
- The Hindsight lane reports that pg0 0.15.2 starts Postgres with fsync off. That matters for the §4.4 durability items.
- The Hindsight lane reports three settings that could break a frozen arm: coding-agents `autoUpdate` defaults to true, an unset `embedVersion` runs the latest hindsight-embed, and the installer pre-selects Hindsight Cloud.
- agentmemory reportedly switches to a hosted embedder when provider keys are in the environment (`src/config.ts:265-278`). S3's `env -i` rule (line 151) already covers this.
- Other open issues the lanes cite: Hindsight #4529 (pg0 index corruption blocks retain; the reporter suspects hardware), plus #4702, #4687 and #4493 on the Codex path; agentmemory #1321; MemPalace #1924, #2326 and #2403.

### Misquotes the refuter found (7)
a. **The date of AMB's 94.6%.** The catalog calls it "undated" (`memory-stack-20260925.json:201`, relayed by the GPT-6 compile), and the peer lane gave "repo commit 2026-09-22". In fact it was committed and announced on **2026-03-23** (commits decbb07f and 7021c59c). 2026-09-22 is the date of the AMB HEAD commit.
b. **The version and LLM behind the 94.6%.** The Hindsight lane said they were "not recorded". AMB's `catalog.json` names gemini-2.5-flash-lite as the extraction model, and the lock file pins 0.4.15 and 0.4.17 (the blog says 0.4.19). So the run was on 0.4.x, not v0.10.1.
c. **The 8.4 h ingest.** Both Claude lanes said 30,090,034 ms (8.4 h) for 11,303 documents. 11,303 is only the count for questions 264-500, out of 23,867 document occurrences, and a resumed run does not restore its time or counts. The 8.4 h covers roughly the resumed half, and the full ingest time is not recorded.
d. **BEAM 100K.** The peer lane gave 75%. The correct figure is **73.4%** (mean score 0.7337; 81.5% pass). The vendor's landing page shows 75%, which contradicts the vendor's own data file.
e. **AMB `mean_recall`.** The Hindsight lane said it is null for every Hindsight run. It is null for every LongMemEval, LoCoMo, BEAM, LifeBench and PersonaMem row, but the hindsight-cloud PrecisionMemBench row shows recall 1.0 and precision 0.8481 over 77 queries. The underlying point, that no LongMemEval or LoCoMo recall exists, still stands.
f. **Supermemory's judge.** The peer lane said the page does not state one. It does: "gpt-4o judges the answers".
g. **Honcho, OpenViking and Basic Memory.** The GPT-6 compile said their numbers are on LoCoMo, a different benchmark from Hindsight's. Honcho's 90.4% is LongMemEval-S, and Hindsight publishes LoCoMo results too. The real mismatch is the judge and the model.

Related corrections:
- The GBrain catalog row (line 280), covered in §4.
- The Mac sweep calls Attemory's figure "undated"; it is dated by its commit, 2026-08-13.

### Refuted claims (8)
- README v0.10.1: "independently reproduced" (line 50).
- README v0.10.1: "most accurate … ever tested" (line 44).
- Hindsight lane: "no independent reproduction exists".
- Hindsight lane: #4696 "hangs forever, even on a 1-document bank".
- Peer lane: "Mastra's 94.87% and Mem0 Platform's 94.4% are higher". Mastra's figure is 93.6% per question, Mem0's 472/500 is below Hindsight's 473/500, and the numbers span four judge setups.
- Peer lane: "Mem0 has no official Codex capture". It has one, but it needs a hosted key.
- Hindsight lane: "the dominance rule cannot be met for Mem0". OAMB is a same-judge comparison, and Mem0 is still not dominated.
- Peer lane: "Hindsight is frontier on QA". Its lead is unproven, not disproven.

### Unverifiable, not used
- The Gemini 3 Pro full-context 92.0% as a ceiling for Hindsight (it used a different judge).
- The MemPalace `recall_all@5` re-score.
- Basic Memory LoCoMo R@5 76.4% (absent from the vendor's summaries).
- The ~86 h Hindsight projection.
- Hindsight's code-level claims: installer behaviour, fact extraction, http.py routes, pg0 fsync, Codex hook status and the AMB recall budget.
- Cognee BEAM 100K 0.79.

Token tools used: `ctx_execute` once, to copy S3's PREREGISTRATION.md into the session scratchpad and list its section headers. Everything else was focused Read calls and rg/git in Bash. No compressors were stacked, and no token savings are claimed.
