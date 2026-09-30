# Memory layer S3: head-to-head preregistration (DRAFT r7, 2026-09-30)

**Status: DRAFT r7, not frozen.**
- r7 applies the coordinator's r7 brief of 2026-09-30, which relays the user's standing requirements of that date (quoted in "r6 → r7 changes"). It removes r6's reference arm and replacement routes in favour of a symmetric merit rule (sections 6–7), adds a maintenance gate (section 1), a token ledger (5.2) and a RAG section (8), and re-pins every system at its current release (3.1).
- **r7 repair round 1 (2026-09-30)** applies the GPT-6 cross-family review of this draft (verdict needs_changes, seven findings; [`inputs/r7/gpt6-review-20260930.md`](inputs/r7/gpt6-review-20260930.md)). The resolutions are listed under "r7 repair round 1" below. The text stays DRAFT r7.
- **r7 repair round 2 (2026-09-30)** applies the independent Opus review of `a266a383`, GPT-6's subsequent N1 finding, and the user's two accepted decisions: LongMemEval-V2 is the main usefulness test, and a host without a qualified winner selects the best-scoring eligible system (5.5, 7.6). Local pinned-source observations and separately labelled synthetic checks are in [`inputs/r7/repair2-verification-20260930.json`](inputs/r7/repair2-verification-20260930.json).
- **r7 repair round 3 (2026-09-30)** applies the pre-freeze review of `0d027e06` and the accepted dependency-maintenance scope. Local source verification and synthetic positive/negative controls are in [`inputs/r7/repair3-verification-20260930.json`](inputs/r7/repair3-verification-20260930.json). Landscape completeness is deferred by the current brief; this round makes no network request or model run.
- This is a protocol revision. It made no deployment, provider call or scored run. Its live checks are metadata and source reads (GitHub, PyPI, Hugging Face, container registries, `nvidia-smi`, client `--version`), captured in [`inputs/r7/live-verification-20260930.json`](inputs/r7/live-verification-20260930.json) and, for the repair round, [`inputs/r7/repair1-verification-20260930.json`](inputs/r7/repair1-verification-20260930.json).
- The freeze needs **both the user's acceptance and a GPT-6 cross-family review** of the complete bundle (section 11). Until then nothing runs under this protocol.
- Once frozen, it is never edited; later changes are dated amendments. A result that misses a bar is a documented FAIL, never a reason to loosen the bar or rerun silently.
- The r1–r6 review history is kept unchanged in Appendix A, with r6's section numbers. Decision record: [`docs/decisions/2026-09-30-memory-s3-r7.md`](../../docs/decisions/2026-09-30-memory-s3-r7.md).

**Decision this experiment makes:** which durable-memory system each host deploys for Claude Code and Codex, and, per role, which document-RAG system and local embedder and reranker it uses (section 8). Client versions are recorded at freeze; on 2026-09-30 `claude --version` returned 2.1.285 and `codex --version` returned 0.157.1. The two hosts decide separately:
- the workstation `nativestack-5975wx-20260925`;
- the Mac `mac-coordinator-64gb-20260925`.

**Merit rules:**
- no system has protected status; the deployed ai-memory is one contender among the others, and r6's reference role is gone;
- license, stars, popularity, installed or incumbent status are not evidence (the user's 2026-09-26 verdict-wave direction, retained from r6);
- every repository selected to run passes the maintenance gate; transitive dependencies require an SBOM and a clean OSV scan, with stale dependencies flagged (section 1);
- a missing result is `pending`, never `refuted`, the rule [`2026-09-23-verdict-integrity.md`](../../docs/decisions/2026-09-23-verdict-integrity.md) applies to missing lanes.

## r6 → r7 changes

**The user's requirements, 2026-09-30,** as relayed verbatim by the coordinator's r7 brief (this revision did not hear them directly):
1. The memory layer uses “the best sota repos, with highest quality performance, rag and token efficiency for full memory foundation”.
2. Repositories must be “the best candidates only with evidence, always check the repos quality, active maintenance, NEVER STALED REPOS”.
3. “No bias but evaluate on the sotaness and the quality of repos itself”; the current incumbent is not the default.

| # | r7 change | Sections | Sources |
|---|---|---|---|
| 1 | Maintenance gate: stale means archived or no default-branch commit in 90 days; selected repositories are checked at freeze and before every run; transitive dependencies receive OSV scans, SBOMs and stale flags; LongMemEval `9e0b455f` is a citation only | 1, 4.2 | OpenSSF Scorecard v5.5.0 Maintained check (section 1); accepted user decision 3; repository CI OSV recipe (1) |
| 2 | Every system at its current release, with tag and full commit; ai-memory v2.4.2 is a contender with no protected status; reserves engram, Graphiti and supermemory-local; Mem0, Letta and beads are out on fit, with locators | 3 | 3.1–3.3 |
| 3 | Harness: AMB `03c1d0f1` runs byte-identical; our LongMemEval adapters (retrieval and open-QA variants), scorer and thin provider clients live in this repository; AMB's locked mem0, cognee and hindsight libraries serve no arm | 4 | AMB locators in 4.3–4.4 |
| 4 | A symmetric merit rule replaces the reference, both replacement routes and the 14-hypothesis family: all-pairs Holm tests, the leader wins, a 0.02 practical-equivalence band, then tie-breaks on cost and on an exact repo-quality formula | 6, 7 | SciPy and statsmodels pins (6); Scorecard aggregate (7.4) |
| 5 | Token ledger: OmniRoute ingest usage per system and role, o200k recall payloads (gpt-tokenizer 4.0.0), native per-session usage from `claude -p` and `codex exec --json` in scratch config homes, latency p95 and resources | 5.2 | client docs and source in 5.2 |
| 6 | RAG section: a document-RAG head-to-head with each system wrapped as an MTEB `SearchProtocol` model, and embedder and reranker selection on MTEB 2.21.10 (LoCoMo, CoIR, English retrieval) over task sets disjoint from the evaluation set | 8 | MTEB 2.21.10 locators in 8 |
| 7 | Header DRAFT r7; the freeze needs the user's acceptance and a GPT-6 cross-family review | Status, 11 | the brief's item 7 |

**Retained from r6, with cross-references and pins updated:** the GPT-6 role contract and gateway invariants (2.1–2.2), the upstream deployment and isolation rules (3.5, 4.6), the dataset, tracks and dependence clusters (4.1), the dispatch wrapper (4.3), the 96-hour feasibility rule with its prospective stratified subset (5.2, 6), the statistics seed, resample count and quantile rule (6), latency (5.3), the coding-agent acceptance and early lifecycle screens (5.4), the research-memory usefulness tasks (5.5) and the host rules (9). Source keys I, R, M, W, V, U and B in retained text resolve through r6 §14 (Appendix A).

**Removed:** the C3′/C4′ reference and its preflight, the superiority and non-inferiority replacement routes, the 14-hypothesis family, the "no replacement qualified" label, any execution of LongMemEval's scorer or judge prompt, MTEB 2.21.8 (now 2.21.10) and gpt-tokenizer 3.4.0 (now 4.0.0, this repository's pin since #493).

**Brief items adjusted on primary evidence**, each also in the decision record:
- (a) The retrieval variant has to run AMB's LLM-free `retrieval` mode; "rag mode only" governs the answer-generating variant (4.3).
- (b) AMB's `supermemory` provider cannot score a local supermemory server, so supermemory-local gets a thin client in this repository (4.3).
- (c) Mem0's plugin defaults to, rather than hard-codes, `https://api.mem0.ai`; the exclusion stands on the Platform routes it calls (3.3).
- (d) Free VRAM measured 12,726 and later 12,005 MiB, not about 13.7 GB (8.2).
- (e) `CoIR-team/coir` is also stale; CoIR enters only as MTEB task data (1, 8.2).
- (f) AMB's LongMemEval judge prompts have no abstention branch; the 30 abstention questions form their own reported stratum (5.5).

**ACCEPTED by the user, 2026-09-30:** the best-scoring eligible-system fallback (7.6), LongMemEval-V2 as the main usefulness test with MemoryAgentBench secondary only where applicable and S8 as a do-no-harm check (5.5, 8.4), and the selected-repository versus transitive-dependency maintenance scope (1). These replace the minus-one floor, S8 usefulness coupling and round-2 executing-closure maintenance gate. Other coordinator choices still require bundle acceptance at freeze: the optional-stage rule and observable fallback preflight (2, 7.5), agentmemory's embedder (3.1), the priced-cost boundary (5.2, 7.3), repo-quality heuristics (7.4), RAG partition (8.1), common depth and failure accounting (4.5), and S8's route and future margin (8.4). The decision record distinguishes those choices from the three accepted decisions.

### r7 repair round 1 (2026-09-30)

A GPT-6 cross-family review of the initial draft (gateway `cx/gpt-6-astra`, effort max) returned **needs_changes** with seven findings. The coordinator reports that all 12 quoted source excerpts matched. The findings are captured verbatim in [`inputs/r7/gpt6-review-20260930.md`](inputs/r7/gpt6-review-20260930.md). This subsection records the original bounded repair round, before the separately issued round-2 brief. Its upstream reads went through `gh api graphql` and are captured in [`inputs/r7/repair1-verification-20260930.json`](inputs/r7/repair1-verification-20260930.json).

| Finding | Resolution | Sections |
|---|---|---|
| **F1 (high)**: stale harbor-datasets task bundles could execute code | "Static data" excludes any executed or interpreted file, and harbor-datasets supplies nothing. A task-level provenance manifest, enforced before every trial, governs any lane that executes tasks. The S8 code-task stage regenerates SWE-bench Verified tasks through Harbor's maintained adapter, with every executable part from a gate-passing source, and stays `pending` until its dated amendment. | 1, 8.4 |
| **F2 (high)**: AMB's Hindsight provider turns native observations off; "equal candidate depth" undefined | Hindsight gets a thin local provider like every other system, and AMB stays byte-identical. Banks keep the vendor's documented defaults; the effective bank configuration is read back and matched to the frozen settings before any ingest, and ingest ends only after consolidation. One operational depth policy covers every provider. The parity audit exercises every provider's actual ingest and recall paths, failures included. | 2, 3.5, 4.3, 4.5 |
| **F3 (high)**: tie-break membership undefined when several systems share the maximum | The maximizer set M is defined. A non-maximizer joins B only within 0.02 of the maximum and only if Holm finds it significantly worse than no leader. Comparisons use exact rationals, with frozen executable examples. | 7.2, 7.3 |
| **F4 (medium)**: gross versus control-subtracted cost | C is the gross, nonnegative priced cost of 5.2's frozen workload; the difference from the no-memory control is reported separately. Several equal minima, zero included, go to 7.4. C_RAG is defined for 8.3. | 5.2, 7.3, 8.3 |
| **F5 (medium)**: the fallback preflight mixed concurrency K with concurrency 1 | Two measurements: the fallback rate under the confirmatory dispatch at K, with a stated denominator, which alone controls stage disabling; and warm latency at concurrency 1. | 7.5 |
| **F6 (medium)**: the CI term could score unfinished runs | K = 10 needs the complete, paginated check and status set, with every run completed and passing. Missing, incomplete or truncated sets give K = 0. R and K are labelled coordinator heuristics. | 7.4 |
| **F7 (medium)**: no minimum usefulness for deployment | Round 1 coupled selection to S8 non-inferiority. **Superseded in round 2:** the accepted main LongMemEval-V2 rule supplies usefulness, and S8 is only the separate short-code do-no-harm check. | 5.5, 7.1, 8.4 |

**Corrections and clarifications made with these fixes:**
- r7 said AMB's locked `hindsight-all` 0.4.17 serves no arm, but AMB's `hindsight-http` provider builds its synchronous client from it (`from hindsight import HindsightClient`, `memory/hindsight.py:1252-1255`). With the thin provider, the statement now holds (4.3).
- C counts only 5.2's frozen workload. LongMemEval ingest usage is reported in ledger (a) but never enters C; r7 had left the workload implicit.
- At the 7.3 boundary, a member whose C is exactly c_min / 0.80 is dominated, as r6's selection condition c_min ≤ 0.80 × C implies. r7's wording had also kept it in the tied set.

**Round-1 residuals, historical:** the old 0/25 usefulness gap and coupling to pending S8 are superseded by repair round 2. S8's design, margin, test and relayed 36-task receipt, and execution of the depth and effective-bank checks, remain outstanding before qualification in their respective lanes.

### r7 repair round 2 (2026-09-30)

The repair brief reports Opus's **needs_changes** review of `a266a383` and GPT-6's **accept_with_minor** re-check with new finding N1. This revision resolves their protocol defects using the local upstream checkouts at the pins; it makes no network request, deployment or model run. The source receipt records the clone identities and corrections. Section 7.5's invalid-score example is a synthetic provider-boundary check, not a completed real gateway experiment. Native acceptance remains required before scoring.

| Finding | Protocol resolution | Sections |
|---|---|---|
| H1 | Exhausted question-seeds score zero against the frozen manifest; failure rate above 5% makes the arm pending. | 4.5 |
| H2 / F7 | Paired, multi-seed, Holm-adjusted LongMemEval-V2 usefulness replaces the minus-one floor and S8 coupling. | 5.5, 6, 7.1, 8.4 |
| M1 | Best-scoring operationally eligible system is the no-winner fallback; no incumbent privilege. | 7.6 |
| M2 | Round 2 gated the executing closure. **Superseded by accepted user decision 3:** selected repositories pass Maintained; transitive dependencies require OSV scans/SBOMs, with stale flags. Runtime egress remains denied except owned local services, gateway and embedder. | 1, 4.3, 4.6 |
| M3 | Both thin-provider recall methods default to k=20; every provider returns raw_response=None, giving the same answer-prompt context shape. | 4.3, 4.5 |
| M4 | Unique output directory per host, lane, track, question, seed, arm and attempt; analysis reads the exact native split file. | 4.3 |
| M5 | All providers expand and deduplicate to five source sessions, escalating to a frozen cap by one common rule. | 4.5 |
| M6 | Header-limited clients need a source-backed, measured exemption or frozen route; agentmemory and MemPalace currently lack that receipt and remain pending. | 2.2, 4.4 |
| M7 | Selection must fit the embedder, reranker and local generative models together under serving load. | 8.2, 9 |
| L1 | Local inference is unpriced; the gross-C cost boundary and its sensitivity are explicit at acceptance. | 5.2, 7.3 |
| L2 | cx/GPT-6 aliases are unpriced until a defensible price mapping exists; no zero or partial-total C is invented. | 5.2, 7.1 |
| L3 | Empty-context QA scores are unjudged zeros, separately flagged; provider-facing question and user IDs are opaque. | 4.1, 5.5 |
| L4 | Prospective cost/power preflight sets usefulness and QA subsets; identical retrieval ingest may be reused only from a verified pre-query snapshot. | 5.2, 5.5 |
| N1 | Every stage request needs an accepted/fallback outcome, including invalid scores after gateway success; unobservable outcomes leave the arm pending. | 7.5 |

Deployment corrections for all eleven systems are summarized in 3.5. The source review establishes recipes and measurement requirements, not a host's passed status.

### r7 repair round 3 (2026-09-30)

This round verifies the final review's source claims in the supplied pinned local clones. It corrects the protocol and executable decision examples; it does not execute a benchmark, refresh online maintenance metadata, download haystacks or perform a vulnerability scan. The corrections and their verification paths also appear in the decision record's anti-pattern log.

| Item | Protocol resolution | Sections |
|---|---|---|
| 1 | Every LongMemEval-V2 arm, including no retrieval, uses the same direct native harness invocation per domain, with identical reader/judge arguments and request-body wire checks. | 5.5 |
| 2 | Outcome-independent shared-trajectory haystack components are the resampling unit; the downloaded-file preflight must find at least 20 clusters, or usefulness stays pending. | 5.5, 6, 7.1 |
| 3 | Open QA receives the shortest prefix of the final ranking covering five sessions, capped at 20 items; emitted context tokens are recorded per arm. | 4.3, 4.5 |
| 4 | MemoryAgentBench is secondary only for applicable native modes; the per-system table excludes vendored candidate copies. | 5.5 |
| 5 | The executable usefulness rule computes the best set only over eligible, completely observed memory systems. | 7.1 |
| 6 | Fallback remains unresolved while a pending contender could change qualification or the selected primary maximizer. | 7.6 |
| 7 | A no-retrieval final-failure rate above 5% makes the entire usefulness family pending. | 4.5, 7.1 |
| 8 | Judge-effort, privacy and question-ID locators are corrected in this protocol, the decision record and the source receipt. | 5.5; round-2 receipt |
| User decision 3 | **ACCEPTED:** Maintained applies to selected repositories; dependencies pass OSV and appear in each arm's SBOM; stale transitive dependencies are report flags. | 1, 4.3 |

## 1. Maintenance gate (r7)

**Rule.** A repository is **stale** if GitHub reports it archived, or if its default branch has no commit in the 90 days before the check. This is the floor of OpenSSF Scorecard's **Maintained** check: Scorecard gives an archived project the minimum score and otherwise scores commit and collaborator issue activity over a 90-day look-back, with one activity per week earning the maximum ([`checks/evaluation/maintained.go:31-32,88-100`](https://github.com/ossf/scorecard/blob/c395761df6afe1a69e476bc60a013a94bcbc153f/checks/evaluation/maintained.go#L31-L100) and [`docs/checks.md:400-422`](https://github.com/ossf/scorecard/blob/c395761df6afe1a69e476bc60a013a94bcbc153f/docs/checks.md#L400-L422) at v5.5.0). Scorecard itself suggests checking the `archived` probe instead of relying on an aggregate or Maintained score alone ([`README.md:86-92`](https://github.com/ossf/scorecard/blob/c395761df6afe1a69e476bc60a013a94bcbc153f/README.md#L86-L92)). The gate is necessary, not sufficient: a project created less than 90 days ago passes it but gets Maintained 0 (`maintained.go:92-94`), and the full Maintained score enters the repo-quality score (7.4).

**Commands**, with `SINCE` the check time minus 90 days in UTC ISO-8601; `true` from the first or `0` from the second marks the repository stale:

```sh
gh api repos/OWNER/REPO --jq .archived
gh api "repos/OWNER/REPO/commits?since=SINCE&per_page=1" --jq length
```

When the account's REST quota is exhausted, `gh api graphql` gives the same verdict from the repository's `isArchived` field and its default branch's `history(since: SINCE) { totalCount }`; repair round 1 used that route ([`inputs/r7/repair1-verification-20260930.json`](inputs/r7/repair1-verification-20260930.json)).

**When.** At freeze, and before each development and confirmatory run on each host. A repository that becomes stale stops executing from that point; results it already produced stay recorded as they are, and the change needs a dated amendment.

**Consequences.**
- **Selected repositories — ACCEPTED 2026-09-30, user decision 3.** The 90-day Maintained rule excludes any stale repository we choose to run: harnesses, memory systems, RAG systems and tools, including selected runtimes, model servers, sidecars and task-code sources. Selection is by role, not by whether it is launched directly or through an adapter: a candidate implementation cannot be relabelled a dependency to evade the gate. No selected stale scripts, evaluators, prompt code or packages run. A pinned release still requires its source repository's current gate receipt.
- **Transitive dependencies — ACCEPTED 2026-09-30; replaces round 2's executing-closure/no-shim maintenance rule.** Imported libraries, native extensions and other dependencies of the selected implementations pass **osv-scanner with no known vulnerability** and are listed in an **SBOM per arm**, including harness import-time dependencies and installed but unused packages. Use the repository CI's checksum-pinned **google/osv-scanner v2.6.0**, `scan source --no-resolve` on resolved lockfiles (`.github/workflows/security-scan.yml:46-86`); freeze scanner identity, lock hashes, advisory snapshot/time, complete coverage and returned findings/exit status. S3 requires no known vulnerability, including any finding a CI-specific suppression would hide. Missing locks, coverage, SBOM or scan observation leaves the arm/harness pending; a known vulnerability blocks it until resolved. Staleness alone is a report flag and does **not** block the harness. Each SBOM entry records version, artifact hash, source repository/revision when known, execution class and vulnerability status; unknown provenance/activity remains unknown in the report. Neither a patched import shim nor a vendored candidate substitutes for the selected implementation. Fetch/build networking belongs to separately recorded provisioning; scored runtime egress remains governed by 4.6.
- **Stale transitive flags found so far.** AMB imports `rank_bm25` **0.2.2** at package load (`vectorize-io/agent-memory-benchmark@03c1d0f1:src/memory_bench/memory/__init__.py:2` → `bm25.py:1`). The supplied `dorianbrown/rank_bm25@47aa3ddf8dc1ebeb7ef4e65f2b4536af44594099` checkout's last commit is **2024-10-08**, beyond 90 days; flag it as stale in the AMB arm SBOM/report. This local observation does not refresh archival/default-branch metadata, and no clean OSV scan is claimed. The stale flag itself does not block AMB. The other lock entries are not labelled stale from version age alone; their vulnerability/provenance inventory remains pending.
- A stale source may supply static data only: a file pinned by the sha256 of its downloaded bytes and read by code from active repositories or from this one. **Static data is inert input that is only read (r7 repair).** A file that is executed, sourced, built or interpreted, such as a Dockerfile, a setup or build script, a test, a judge or grading script or a solution script, is code wherever it is hosted, and a bundle that contains one is not static data. Registry metadata, such as a Hugging Face LFS oid, is recorded but never replaces the downloaded-file hash.
- **LongMemEval `9e0b455f` appears only as a citation**: for the paper's definitions, the dataset format and the reference implementation that 4.2 reimplements. The dataset file is static data pinned by sha256 (4.1).
- LoCoMo enters only as MTEB data (`mteb/LoCoMo`, revision `02e2c3dea15d9fdfd1cd7a0f65f5f8ae2ed4c1ac`, read by MTEB); CoIR only as MTEB's CoIR tasks (8.2).
- **harbor-datasets supplies nothing (r7 repair).** Its task bundles carry executable tests and judges: [`datasets/aa-lcr/aa-lcr-1/tests/test.sh:4`](https://github.com/harbor-framework/harbor-datasets/blob/37db108843a49bb31a592e37a75e2c40dc3f9749/datasets/aa-lcr/aa-lcr-1/tests/test.sh#L4) at `37db1088` runs `python /tests/llm_judge.py`, and Harbor's verifier uploads a task's tests and executes its test script ([`src/harbor/verifier/verifier.py:175-232`](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/src/harbor/verifier/verifier.py#L175-L232) at v0.23.0). No bundle, file or data from it enters any S3 process; the S8 stage regenerates its tasks from maintained sources (8.4).
- **Task-level provenance manifest (r7 repair).** A lane that executes task bundles, today only 8.4's S8 stage, freezes one manifest per task. It lists every file of the generated task and every artifact the task fetches when built or run, such as the base image, installers and verifier dependencies. Each entry carries its sha256 or image digest, its class (inert input; environment or Dockerfile; setup or build script; test; judge or grader; solution), its source (repository and commit, or dataset and revision) and its selected-repository/dependency role under the accepted scope above. Selected executable sources need a current ACTIVE gate; transitive dependencies need SBOM/OSV coverage, with stale flags retained. Before every trial the runner re-hashes the task directory and checks the built image's digest; it refuses the trial if any file is unlisted or differs, or if its applicable maintenance/vulnerability requirement is not met. A refused task is recorded, and excluding a task after any result needs a dated amendment.

**Results at 2026-09-30T02:52:42Z** (window start 2026-07-02T02:52:42Z). The full capture, with every head, release date and the 300-commit counting cap, is [`inputs/r7/live-verification-20260930.json`](inputs/r7/live-verification-20260930.json) (sha256 `c02d1c506d31164891d3f1782a55993d1d5ae61f9a5c4b9c7e285aa839e24f69`). "300+" means the count reached the cap. No repository below is archived.

| Repository | Role in r7 | Last default-branch commit | Commits in window | Verdict |
|---|---|---|---|---|
| snap-research/locomo | LoCoMo origin; data only through MTEB | 2024-08-13 (`3eb6f2c5`) | 0 | **STALE** |
| xiaowu0162/LongMemEval | citation only | 2026-05-11 (`9e0b455f`) | 0 | **STALE** |
| harbor-framework/harbor-datasets (formerly laude-institute/harbor-datasets) | none; supplies nothing (1, 8.4) | 2026-05-16 (`37db1088`) | 0 | **STALE** |
| CoIR-team/coir | CoIR origin; data only through MTEB | 2025-06-30 (`89d0e769`) | 0 | **STALE** |
| vectorize-io/agent-memory-benchmark (AMB) | harness; the pin `03c1d0f1` is its head | 2026-09-22 | 12 | ACTIVE |
| embeddings-benchmark/mteb | harness | 2026-09-29 | 300+ | ACTIVE |
| ossf/scorecard | repo-quality score | 2026-09-29 | 22 | ACTIVE |
| niieani/gpt-tokenizer | payload counts | 2026-08-16 | 11 | ACTIVE |
| scipy/scipy; statsmodels/statsmodels; numpy/numpy | statistics | 2026-09-29; 2026-09-29; 2026-09-30 | 300+ each | ACTIVE |
| diegosouzapw/OmniRoute | GPT-6 gateway | 2026-09-29 (default branch `release/v3.8.52`) | 300+ | ACTIVE |
| harbor-framework/harbor | Harbor E2E harness (8.4) | 2026-09-30 | 300+ | ACTIVE |
| xiaowu0162/LongMemEval-V2 | main usefulness harness (5.5) | 2026-08-09 | 3 | ACTIVE |
| rohitg00/agentmemory; vectorize-io/hindsight; volcengine/OpenViking; topoteretes/cognee; MemPalace/mempalace; basicmachines-co/basic-memory; zilliztech/memsearch; akitaonrails/ai-memory | primary candidates (3.1) | 2026-09-24 to 2026-09-30 | 39; 300+; 300+; 300+; 300+; 300+; 79; 300+ | ACTIVE |
| Gentleman-Programming/engram; getzep/graphiti; supermemoryai/supermemory | reserves (3.2) | 2026-09-29 to 2026-09-30 | 300+; 116; 183 | ACTIVE |
| mem0ai/mem0; letta-ai/letta; gastownhall/beads (formerly steveyegge/beads) | out on fit (3.3) | 2026-09-25; 2026-09-10; 2026-09-30 | 236; 8; 300+ | ACTIVE |
| garrytan/gbrain | late-candidate screen (3.2) | 2026-09-29 | 300+ | ACTIVE |
| tobi/qmd; HKUDS/LightRAG; run-llama/llama_index | document-RAG candidates (8.3) | 2026-09-09; 2026-09-26; 2026-09-29 | 110; 300+; 102 | ACTIVE |
| DeusData/codebase-memory-mcp | code-retrieval fit record (8.4) | 2026-09-28 | 300+ | ACTIVE |

**Repair-round rerun at 2026-09-30T04:23:48Z** (window start 2026-07-02T04:23:48Z), for the sources of 8.4's S8 stage, through `gh api graphql` ([`inputs/r7/repair1-verification-20260930.json`](inputs/r7/repair1-verification-20260930.json), sha256 `e17484588948dc7150afba464d4806924bc08ae7858a726bda5ef1b70c9a2b35`). None is archived.
- ACTIVE: harbor-framework/harbor (526 commits in the window), SWE-bench/SWE-bench (113), huggingface/datasets (62), AnswerDotAI/fastcore (262) and astral-sh/uv (1,218).
- STALE: harbor-framework/harbor-datasets, still with no commit in the window (head `37db1088`).

**Round-2 local source observations, not a fresh online gate.** The supplied LongMemEval-V2 pin `2cc8c540` has commit date 2026-08-09; MemoryAgentBench `538026089` has commit date 2026-09-25. The brief designates them active under the 90-day rule; their archival/default-branch gate receipts are still refreshed at freeze. MemoryArena `6cd9de14` has last commit 2026-05-31 as relayed by the brief and confirmed by the supplied checkout's commit date: it is **STALE**, cited for ICML 2026 context only, and none of its code runs. Source receipt: `inputs/r7/repair2-verification-20260930.json`.

## 2. Systems, arms and the GPT-6 backbone

There is **no reference arm**. Every system in the family, ai-memory included, has exactly **one primary arm**, defined by the same rule:
- its upstream-recommended self-hosted deployment for coding-agent memory at the release pinned in 3.1, installed as 3.5 requires;
- every active LLM role on GPT-6 through the host's own OmniRoute (2.1–2.2);
- a current local embedder and dedicated reranker selected by 8.2 wherever upstream supports configuring them; otherwise the shipped model, labelled **shipped default**;
- **optional-stage rule (r7):** where upstream documents an optional recall stage, such as an LLM or cross-encoder reranker, without recommending it for this use case, the stage setting is chosen per system on the development split by the frozen comparison of 2.1 (LoCoMo supporting-evidence recall@5 with a one-sided cluster bootstrap at α = 0.05) before any confirmatory run. An inconclusive comparison keeps the upstream default. The unselected setting is a diagnostic outside the family;
- **native store configuration (r7 repair):** each arm keeps the system's documented defaults for per-store settings, such as Hindsight's bank configuration. Neither the harness nor a provider client overrides them, and the effective settings are frozen and read back before ingest (4.3, 4.5). A departure from them is a frozen, labelled configuration choice made before freeze, never a harness side effect.

**ai-memory v2.4.2 (r7).** ai-memory competes under exactly this rule. Its LLM reranker is "optional and off by default" and makes at most one LLM call per query to reorder candidates ([`docs/llm-providers.md:331-341`](https://github.com/akitaonrails/ai-memory/blob/a0ca8d1a5fbd5920799411fa891fe6d49c90efc1/docs/llm-providers.md#L331-L341); `AI_MEMORY_RERANKER=llm` is validated at [`crates/ai-memory-cli/src/config.rs:427-433,1762-1774`](https://github.com/akitaonrails/ai-memory/blob/a0ca8d1a5fbd5920799411fa891fe6d49c90efc1/crates/ai-memory-cli/src/config.rs#L427-L433)), so the optional-stage rule decides it. If selected, it runs through the openai-compatible provider on GPT-6 and is subject to the fallback preflight in 7.5. Its embedder follows 8.2 like any configurable system, through its `openai-compat` embedding provider (`docs/llm-providers.md:343-349`). r6's C3′/C4′ definitions and v2.4.0 feasibility notes are historical (r6 §1 in the r6 text at `f7e5e228`; review history in Appendix A). Of the ai-memory files r6 cited, `crates/ai-memory-llm/src/embedding.rs` and `reranker.rs` are byte-identical from v2.4.0 to v2.4.2; `config.rs` and `docs/llm-providers.md` changed (live capture, `changed_between_releases`), so r6's line references into those two files do not carry over.

**Deployed configurations (descriptive only).** The workstation runs ai-memory 2.4.1 (this checkout's `manifests/stack.json`); the Mac runs its production build `19b6429` in a C4-shaped configuration (r6 §1, in the r6 text at `f7e5e228`). Any measurement of them uses fresh diagnostic copies with the GPT-6 overlay, labelled D-workstation-GPT6 and D-mac-prod-GPT6, outside the family. The v2.4.2 re-pin is the user's 2026-09-30 decision as relayed by the brief; the base's `manifests/stack.json` still lists 2.4.1.

**Eligibility applies to every configuration** (7.1).

### 2.1 GPT-6 role contract (r6 1.1, retained)

Every active LLM role inside every scored system and diagnostic copy uses GPT-6 through **that host's own local OmniRoute**: extraction, retain/reflect, graph building, consolidation, summarization, LLM reranking, query rewriting/expansion, and any auxiliary or fallback LLM call. Deterministic operations and local embedding/cross-encoder inference remain local; an absent LLM role is recorded `not applicable`, not invented. A shipped local generative model that upstream offers no way to replace is recorded as a fixed-provider shipped default, not patched (for example qmd's query expansion, 8.3). The workstation endpoint is `http://127.0.0.1:20128/v1`. The Mac uses its own loopback gateway and LaunchAgent, on the same OmniRoute tree and patch IDs as the workstation (section 9). This supersedes “local-only providers” for **LLMs**; the memory service, stores, embeddings and non-LLM rerankers stay on the host. Sources: coordinator brief B:A/I; I:4–14,18–58; R:31–53; pinned gateway sources in 2.2 and host-receipt requirements in 9.

- Freeze a **per-host, per-arm, per-role matrix** containing the GPT-6 model ID, effort, provider/endpoint, prompt and schema hashes, output/context caps, timeouts, retries and fallback routing before confirmatory execution. Use the same selected model/effort for a matched role across systems where supported. If upstream shares one provider across roles, freeze that coupling and test the combined configuration; do not claim independent overrides. No fallback may silently invoke a shipped older model.
- **R02 development selection:** compare `cx/gpt-6-astra` at medium with `cx/gpt-6-astra-max`, using paired, interleaved calls with identical prompts/schema on S3's separate development split. **Before the first development call**, freeze, per role or coupled role set and on **each host**: LoCoMo full-system question-weighted supporting-evidence recall@5 plus schema validity, question count **n**, conversation/cluster manifest, task/source hashes, and a **one-sided cluster bootstrap at α=0.05 using section 6's SciPy binding with `alternative="greater"`** (development cluster arrays replace the confirmatory arrays). Coupled roles are selected jointly. Freeze the schema-validity acceptance rule, then select max only when the paired quality lower bound is >0; otherwise select medium when its lower bound is ≥−0.02 and it is cheaper. Record complete usage, latency, timeouts and fresh 429s. A `cx/gpt-6-sol` medium alternative, or a newer GPT-6-family model current at freeze, needs the same prespecified comparison. The optional-stage choices in section 2 use the same split, metric and test. An arm with any unresolved role is **pending**, and needs a **dated amendment before its first confirmatory run**; there is no post-result role choice. The development split shares no question or canonical conversation content with either confirmatory LongMemEval track or the 25 usefulness tasks. The li26 wire check is not memory-quality evidence. **Answerer and judge are fixed separately at Astra max** (5.5), not selected on these results. Sources: R:25–29,31–53; W:83–97.
- Record requested and returned model identity and the gateway build at freeze and on execution. Recheck freshness before freezing; any later change to model/effort, gateway tree/patches or role policy requires a dated amendment, not an in-run substitution (r6 user directions 1–4; section 11).

### 2.2 Gateway invariants for every scored GPT-6 call (r6 1.2, retained)

These also apply to ingestion, retries, development comparisons and QA/judging, not just the final query.

1. A role needing max sends the **`-max` model suffix**, e.g. `cx/gpt-6-astra-max` (cognee's LiteLLM spelling is `openai/cx/gpt-6-astra-max`). A chat/completions request without `reasoning_effort` runs at **medium**; the suffix wins over the body. Never use `auto`. Verify effective effort from the `call_logs` effort columns, including `reasoning_effort_upstream`; missing values are unverified, not inferred from the alias. These columns are populated only on rows with encrypted reasoning, so development wire checks and a value-free per-call audit must account for missing coverage. Sources: I:5–8; R:11,42,50; [OmniRoute executor at a58000c7](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/executors/codex.ts#L1424-L1465).
2. A **conversation is one question × seed × arm run**, including that run's ingest and recall; non-retrieval lanes substitute their frozen task/session ID. Give distinct runs distinct affinity identities and tag the arm separately. Allocate one stable `x-omniroute-session` key per conversation, never one per arm, where supported. `LLM_ARGS` and `HINDSIGHT_API_LLM_DEFAULT_HEADERS` are **process-static**, not per-call callbacks. **Route (a):** start one fresh arm process per run with that run's session key (470 × 5 × 8 = **18,800 starts per host** in the full, all-stochastic scenario, before deterministic reuse; official-track/QA/development extras are separate). **Route (b), Hindsight only:** omit the static session header and set `HINDSIGHT_API_{OP}_LLM_CACHE_AFFINITY=openai_prompt_cache_key` for the supported operations; this remains pending until wire checks show the emitted value gives the required stable within-run, distinct between-run gateway affinity. Neither route establishes dynamic idempotency headers. This corrects I:13/31 using R:7–11; an arm-wide constant pins its conversations to one account. Sources: [Hindsight config:176–182,403](https://github.com/vectorize-io/hindsight/blob/f8950b0c07d9e34c76493dba802bb309f0ce60fd/hindsight-api-slim/hindsight_api/config.py#L176-L182), [affinity implementation](https://github.com/vectorize-io/hindsight/blob/f8950b0c07d9e34c76493dba802bb309f0ce60fd/hindsight-api-slim/hindsight_api/engine/cache_affinity.py) (the same names sit at the same lines in 0.10.2, `5fc4ce20`; `cache_affinity.py` changed and is re-read before freeze); section 3.5. Native prompt-cache affinity remains separate from response-cache reuse.
3. Every call sends **`X-OmniRoute-No-Cache: true`** and is **dedup-ineligible**: `stream: true`, or a resolved temperature that is **absent or >0.1**, verified at the wire and against the frozen `maxTemperatureForDedup=0.1`. Explicit **1.0 is eligible for this exclusion**, just as omission resolves to 1.0 in the dedup gate; this corrects the original brief's stricter rule. Use a fresh `Idempotency-Key` per attempt where per-call headers exist; a static key is not fresh. The pinned [key composition](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore/idempotency.ts#L74-L110) combines raw key, provider/model and a digest of semantic fields, including messages: different bodies separate, but identical retries can replay. Therefore static-only adapters **omit both `Idempotency-Key` and the `x-request-id` fallback**, rather than sending a constant key; verify SDK-added headers and prove no replay in `call_logs` before scoring. [Header lookup and absent-key behavior](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/idempotencyLayer.ts#L42-L55) and [chatCore:759–766](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L759-L766) establish this choice. Sources: I:9–14,30–32; R:7–11; [cache gate](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1247-L1249), [dedup gate](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/services/requestDedup.ts#L205-L215). Header-limited clients, including AMB's answerer/judge, use 4.4's measured source-backed exemption or a frozen native per-arm route; otherwise they remain pending.
4. Keep OmniRoute compression **off**, with **`codex/*` excluded**; freeze and verify the byte-preserving request path. Sources: I:14; [compression dispatch](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L1416-L1478).
5. Prove the actual request envelope on each pinned adapter before scoring, including nested/background calls and retries. Use upstream header/SDK controls where available; a header-limited client needs the source-backed, measured exemption or separate native route in 4.4, otherwise it remains `pending`. A body `EXTRA_BODY` field is not an HTTP-header control. A gateway HTTP 200 or a model alias alone is not this proof. Keep only sanitized request metadata and effort/usage observations; never read credential stores or retain authorization headers.

**Gateway identity (r7).** r6 recorded "OmniRoute 3.8.51, tree `a58000c7`". The released `v3.8.51` tag resolves to a different commit, `c1e30b7676975feb298b49eff6ff58923c04b89e` (published 2026-09-30T01:41:50Z). Each host's own sanitized build receipt at freeze decides the gateway identity (section 9); the `a58000c7` links above remain source citations.

## 3. Candidates, reserves, exclusions and deployments

### 3.1 Primary candidates (the family)

Each release below is the repository's latest GitHub release on 2026-09-30 (`releases/latest`), resolved to its commit through `repos/OWNER/REPO/commits/TAG`. The run manifest pins each to an immutable artifact and sha256 (3.5).

| System | Release | Commit | Published (UTC) | r6 pin |
|---|---|---|---|---|
| [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) | [v0.9.29](https://github.com/rohitg00/agentmemory/releases/tag/v0.9.29) | `2d38dafede67d0d4ed920cde94d2106e98825b8a` | 2026-08-16 | same |
| [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | [v0.10.2](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.2) | `5fc4ce20917b916240cef27c212c387a177f115b` | 2026-09-29 | v0.10.1 (`f8950b0c`) |
| [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | [v0.4.22](https://github.com/volcengine/OpenViking/releases/tag/v0.4.22) | `e8716760934d95ef73414484a45bfe475b9296e2` | 2026-09-28 | v0.4.21 |
| [topoteretes/cognee](https://github.com/topoteretes/cognee) | [v1.6.2](https://github.com/topoteretes/cognee/releases/tag/v1.6.2) | `ba3631f2ed363a6ea50d649c34c56885af6b36fe` | 2026-09-29 | v1.6.1 (`eb90d037`) |
| [MemPalace/mempalace](https://github.com/MemPalace/mempalace) | [v3.10.0](https://github.com/MemPalace/mempalace/releases/tag/v3.10.0) | `22fd87f09c19d5ffb2d6966486483353937931c0` | 2026-09-16 | same |
| [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) | [v0.23.2](https://github.com/basicmachines-co/basic-memory/releases/tag/v0.23.2) | `c0bd87c6d5a4a58034b1d6c8c5018e443b0bd048` | 2026-08-25 | same |
| [zilliztech/memsearch](https://github.com/zilliztech/memsearch) | [v0.4.21](https://github.com/zilliztech/memsearch/releases/tag/v0.4.21) | `2a4652fa086fbd45e92bfd8da7781ebe1642baa7` | 2026-09-24 | same |
| [akitaonrails/ai-memory](https://github.com/akitaonrails/ai-memory) | [v2.4.2](https://github.com/akitaonrails/ai-memory/releases/tag/v2.4.2) | `a0ca8d1a5fbd5920799411fa891fe6d49c90efc1` | 2026-09-29 | r6 reference v2.4.0 (`b1b25219`) |

**agentmemory under the symmetric rule (r7).** r6 kept agentmemory's shipped local MiniLM as its primary by coordinator requirement B:C, an explicit exception to the current-model rule B:E. r7 applies one rule to every system. agentmemory supports an OpenAI-compatible embedder, so its primary arm uses the 8.2-selected embedder through that provider, and the shipped MiniLM configuration becomes a labelled diagnostic. If the coordinator or the user reaffirms B:C, it becomes a dated exception before freeze, recorded as one. The pinned-source facts r6 verified still hold:
- the local provider hard-codes Xenova MiniLM q8 ([v0.9.29 local provider](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/providers/embedding/local.ts#L8-L46));
- with `EMBEDDING_PROVIDER=openai`, `OPENAI_EMBEDDING_BASE_URL`, `OPENAI_EMBEDDING_MODEL` and `OPENAI_EMBEDDING_DIMENSIONS` select the endpoint, model and dimensions, but a non-empty **`OPENAI_API_KEY` takes precedence over `OPENAI_EMBEDDING_API_KEY`** ([embedding/index.ts:37–38](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/providers/embedding/index.ts#L37-L38), [embedding/openai.ts:64–68](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/providers/embedding/openai.ts#L64-L68)). The primary therefore needs a deliberately safe local-endpoint key policy and verified dimensions, without reading or copying a credential value.

The rest of r6's agentmemory contract is retained:
- Set `OPENAI_BASE_URL` to the host's gateway and `OPENAI_MODEL` and `OPENAI_REASONING_EFFORT` to the frozen GPT-6 selection. The pinned worker shares one LLM provider across roles, so its role matrix records a shared model/effort rather than fictitious per-role environment variables ([config.ts](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/config.ts#L70-L97), [provider wiring](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/index.ts#L250-L341)).
- The native chat path is non-streaming and omits temperature; its request/header support still has to meet 2.2 before scoring ([openai.ts:78–113](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/providers/openai.ts#L78-L113)).
- **Hook equivalence is required.** The primary adapter must execute the pinned shipped hooks, or demonstrate equivalent behaviour on frozen client-shaped fixtures, including SessionEnd transcript handling (upstream `src/hooks/session-end.ts:20`). The existing D2h replay alone does not establish that equivalence: v4's `am_hook_session` emulates HTTP events and omits transcript replay (`am-minilm-hooks`: v4 `lme_harness.py:759-784,1618-1619`; v4 `PREREGISTRATION.md:456-459,497-498`).
- Pins: agentmemory 0.9.29 at `2d38dafe`; iii 0.11.2, Linux asset `9c83c477…`; Node 24.21.0; and, for the MiniLM diagnostic, Xenova MiniLM q8 at `751bff37`, ONNX `afdb6f1a…`, staged by v4 `lane_tools.py` `install_minilm` (all in v4 `pins.json:36-39,70-77,89-93,1072-1100`). On macOS the Mac's own sanitized host receipt records its platform assets.

**Discovery inputs (r4, retained).** The Mac session's five model and repository sweeps (embedders, rerankers, memory LLMs, generation models and memory systems), each Opus-verified and dated 2026-09-27, are committed verbatim under `inputs/sweep-20260927-mac/` (commit ff12bf13), with their sha256 in `manifests/evidence.json`. Vendor-reported scores are motivation for the candidate list only (section 10), never S3 evidence.

### 3.2 Reserves and late candidates

**Reserves**, in priority order:
1. [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) v2.2.1 (`818be842f57a95063f62f1b745297a96c407c143`): local SQLite/FTS5, official Claude and Codex setup;
2. [getzep/graphiti](https://github.com/getzep/graphiti) v0.30.2 (`eaa4128681bc53487138a4bbc22d58336ebe70d2`);
3. **supermemory-local**: `supermemory-server` release [`server-v0.0.8`](https://github.com/supermemoryai/supermemory/releases/tag/server-v0.0.8) (`5d2b5855fe492a3682a1cde4a255e2db0c4db595`, published 2026-08-17).

**supermemory-local, verified from the self-hosting docs at that commit** (read, not executed):
- the server listens on `PORT` or `SUPERMEMORY_PORT`, default **6767** ([`apps/docs/self-hosting/configuration.mdx:16`](https://github.com/supermemoryai/supermemory/blob/5d2b5855fe492a3682a1cde4a255e2db0c4db595/apps/docs/self-hosting/configuration.mdx#L16));
- **any OpenAI-compatible LLM endpoint** works through `OPENAI_API_KEY` plus `OPENAI_BASE_URL` (`configuration.mdx:44`; `quickstart.mdx:72`), so the GPT-6 gateway can serve its LLM roles;
- embeddings default to local `Xenova/bge-base-en-v1.5` (`overview.mdx:27`);
- the Claude Code and Codex plugins target the local server with `SUPERMEMORY_API_URL=http://localhost:6767` (`overview.mdx:57`);
- `SUPERMEMORY_DISABLE_TELEMETRY` exists (`configuration.mdx:119-125`);
- self-hosting runs the pipeline on the model supplied, while the hosted service uses proprietary models (`quickstart.mdx:72`), so hosted results do not transfer. AMB's provider cannot drive it (4.3).

**Admission rule (r6, retained):** a reserve is screened for eligibility, meaning an official local install and official integration with both clients, in priority order. It is run whenever a primary candidate is ineligible, or when compute remains after the primary arms. An eligible system that is not run stays `pending`. Every winner claim is bounded to the evaluated set. A reserve admitted before confirmatory execution joins the family (section 6); one admitted afterwards is exploratory until a separately frozen comparison.

**Late candidates (r4, retained).** Any later survivor of the 32-layer sweep, or any other dated discovery, is handled like a reserve admitted after confirmatory execution. It must also pass the maintenance gate:
- it is exploratory until a separately frozen, dated amendment arm names it before its first run;
- it uses the same lanes, thresholds and decision rule;
- it can change a host's selection only through that amendment's own frozen comparison;
- it never edits this text.

r6's lower-priority reserves (MemMachine, Honcho, SimpleMem, MCP Memory Service) and its pending names (byterover-cli, deja-vu, total-agent-memory) are not r7 reserves; each may enter only through this rule.

**GBrain (r6 late-candidate screen, now at the current release).** `garrytan/gbrain` v0.60.10.0 (`608a174dcfa1d39d5ea2d8fb5b296122b1cc78c5`, 2026-09-29) is ACTIVE. Its published **449/470 `recall_all@5`** was verified by r6 at `e78f1c38` ([CHANGELOG:2039–2061](https://github.com/garrytan/gbrain/blob/e78f1c38b947b053f3a46881340f74f316be855a/CHANGELOG.md#L2039-L2061)). That run used hosted OpenAI embeddings and a [Voyage reranker](https://github.com/garrytan/gbrain/blob/e78f1c38b947b053f3a46881340f74f316be855a/CHANGELOG.md#L1960), and its local path is unmeasured, so it decides nothing. The screen covers official local installation, both clients, configurable local retrieval, GPT-6 routing and lifecycle at the current release. GBrain stays outside the family, and even a passing screen changes selection only through the late-candidate rule.

### 3.3 Exclusions, with evidence

- **Mem0** (OSS v2.2.1, 2026-09-25; the repository passes the gate). Its official integrations send memory off the host.
  - The Claude Code plugin sets `DEFAULT_API_URL = "https://api.mem0.ai"` ([`integrations/claude-code-plugin/core/memory_core.py:31`](https://github.com/mem0ai/mem0/blob/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd/integrations/claude-code-plugin/core/memory_core.py#L31) at `94c3fe9f`, the main head on 2026-09-30).
  - A `MEM0_API_URL` variable can override it (`:1995,2334,2584,2622`), so the brief's "hard-codes" is corrected here. The override does not bring memory home, though: the plugin calls Platform routes, `/v3/memories/add/` (`:1996`), `/v1/event/{id}/` (`:1916`) and `/v2/memories/` (`:2532`). The self-hosted server serves `/memories`, `/search` and related routes instead ([`server/main.py:367-547`](https://github.com/mem0ai/mem0/blob/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd/server/main.py#L367-L547)).
  - The official Codex path is `codex mcp add mem0 --url https://mcp.mem0.ai/mcp/` with a Platform account and key ([`docs/integrations/codex.mdx:16-18,71,78`](https://github.com/mem0ai/mem0/blob/94c3fe9f238f3dbf29c9ce98643bd71eb13077cd/docs/integrations/codex.mdx#L71-L79)).
  - Mem0 is at most a diagnostic arm outside the family: its self-hosted OSS server at the current release, through a thin client, never the Platform.
- **Letta**. The repository passes the gate, with 8 commits in the window, so the exclusion is on fit, not staleness. Its README says the `archive` branch "contains the retired Letta V1 API server" and sends active projects to `letta-ai/letta-code` ([`README.md:5,39`](https://github.com/letta-ai/letta/blob/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a/README.md#L39) at `5bcdd177`). `letta-code` v0.33.8 (`21daa38a`, ACTIVE) is "a stateful agent harness", an agent client of its own, not a memory provider for Claude Code or Codex.
- **beads** (`gastownhall/beads` v1.3.0, `f45b249ce6b40ba62aecc03949e6371e8f7c79d8`, ACTIVE). Its README calls it a "Distributed graph issue tracker for AI agents" ([`README.md:3`](https://github.com/gastownhall/beads/blob/3f9561db2bd1b1903ca8cbb39e9fc0cb37b0bccb/README.md#L3) at `3f9561db`) that provides "persistent, structured memory for coding agents" by replacing "messy markdown plans with a dependency-aware graph" (`README.md:15`). That is work tracking (`bd create`, `ready`, `claim`, `close`), not query-time recall of earlier sessions, so it is out on fit.
- **Attemory v0.1.3** (r6, retained): ineligible on fit. It has not established the required official local integration with both clients; its pinned README still lists MCP as planned ([603c03af:318–322](https://github.com/AttemorySystem/attemory/blob/603c03afa9a04e48b778922eae156a0024752f37/README.md#L318-L322); M:100–112).

### 3.4 Controls and diagnostics (outside the family)

- **Native no-external-memory controls, both clients (r6, retained):** Claude Code auto memory at the recorded client version, isolated with `--settings autoMemoryDirectory`, where `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` gives the no-memory control; and Codex native memories at 0.157.1 (`memories`, stable, off by default: [features/src/lib.rs](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/features/src/lib.rs)), enabled in an isolated `CODEX_HOME`. Controls use the same lanes. Unsupported cross-client behaviour is recorded as such, and a control is never eligible for deployment.
- Plain BM25 and dense retrieval with the 8.2-selected memory embedder, on the same eligible corpus, session mapping, deduplication and top-5 scorer (r6, M:61–67,117).
- Unselected optional-stage settings (section 2), shipped-default replays such as agentmemory's MiniLM, the deployed-configuration copies (section 2) and, if run, the Mem0 diagnostic (3.3).

### 3.5 Upstream deployment and isolated arm configurations (r6 2.1, updated)

Every system uses its upstream-recommended deployment for the selected host/use case, with the executable image **pinned by digest**, or a build/install from the selected tag's **lockfile**. A floating `latest`, a package version with newly resolved dependencies, or a setup-only smoke is insufficient. Freeze the upstream install/start/readiness/test/stop/backup/restore commands, source/lock hashes, platform image digest, native client integration pin and effective configuration per arm. If upstream documents several supported modes without a single recommendation, name the selected mode and its source rather than inventing an endorsement. All eight release identities in 3.1 remain fixed; their deployment recipes must be resolved before the bundle freeze (section 11).

- Each arm receives a **fresh container, volume and home**, loopback-only endpoints, its own database/index/model cache and isolated client profiles. The worker and every sidecar are inside that arm's isolation boundary; upstream compose that isolates only an engine does not also isolate its host worker. Use fresh empty stores for independent question/seed runs, not additive import/restore as a reset. Never score against a live deployment, including the persistent cognee service. Freeze how the container reaches its host-local gateway: container loopback is not host loopback. Verify the supported network/forwarding path and endpoint identity without exposing a public listener. These are experiment requirements, not claims that the upstream default deployment already enforces them.
- Keep upstream installs intact. Use supported configuration, not edits to upstream databases, libraries or model implementations, to satisfy isolation. Record upstream tests separately from S3 integration checks and preserve failures (section 4 and `docs/acceptance-evidence-policy.md`).
- **Recorded live hosting, never scored or touched (r6):** I:37–54 records `cognee-live` from the pinned digest on rootless Docker **29.8.1**, `127.0.0.1:3800`, auth on; and `hindsight-live` as a `systemd --user` unit on **3710/5433** with pg0. Archive sanitized copies of **both deploy receipts** in the freeze bundle. Ports **3800, 3710 and 5433** are on the protected fail-closed list (4.6). **`10.0.2.2:20128`** is the recorded candidate container-to-host transport; re-verify endpoint identity per isolated arm. Live envelopes use static session headers and are **not scored envelopes**. Hindsight's stale-`postmaster.pid` guard is a **local lifecycle modification**; a scored arm must not inherit it silently, and the retained unguarded first failure counts as Hindsight lifecycle evidence.

| System | Pinned native deployment and verified configuration to carry into the isolated arm | Evidence and boundary |
|---|---|---|
| **cognee 1.6.2** | Release commit `ba3631f2ed363a6ea50d649c34c56885af6b36fe`; image `cognee/cognee:1.6.2@sha256:41c06180608a053f07fffc4da56dd1efba62967dd3d4a1023b33939abee5d45d`, or that tag's `uv.lock` with `uv sync --python 3.12 --frozen --no-dev --no-editable` in a fresh container. `LLM_PROVIDER=custom`, `LLM_ENDPOINT` = local gateway, and LiteLLM model spelling `openai/cx/gpt-6-…`. Set base plus `LLM_EXTRACTION_MODEL`, `LLM_SUMMARIZATION_MODEL`, `LLM_QUERY_MODEL` from the role matrix; all other roles inherit the GPT-6 base. Set `STRUCTURED_OUTPUT_FRAMEWORK=instructor`, `LLM_INSTRUCTOR_MODE=tool_call`, `GRAPH_EXTRACTOR=llm`, `ENABLE_BACKEND_ACCESS_CONTROL=true`, `TELEMETRY_DISABLED=1`, `LITELLM_LOCAL_MODEL_COST_MAP=True`. Give each arm its own `/cognee-storage` and home, with no inherited `.env`. Use shipped SQLite/LanceDB/Ladybug stores. Pin `DataItem(data_id=uuid5(...))` per opaque source session, with frozen namespace/mapping. | I:16–35; [Dockerfile](https://github.com/topoteretes/cognee/blob/ba3631f2ed363a6ea50d649c34c56885af6b36fe/Dockerfile#L59-L140) and [DataItem](https://github.com/topoteretes/cognee/blob/ba3631f2ed363a6ea50d649c34c56885af6b36fe/cognee/tasks/ingestion/data_item.py#L14-L22), both byte-identical to 1.6.1; [LLM config at 1.6.2](https://github.com/topoteretes/cognee/blob/ba3631f2ed363a6ea50d649c34c56885af6b36fe/cognee/infrastructure/llm/config.py#L107-L128): `structured_output_framework` defaults to `litellm_native` (L107), so `instructor` is a frozen departure; per-role models L116–128; `llm_args` L193. The supplied 1.6.1 bare-metal smoke is setup evidence only; it is not the scored container. |
| **Hindsight 0.10.2** | Release commit `5fc4ce20917b916240cef27c212c387a177f115b`; upstream Docker path, e.g. standalone `ghcr.io/vectorize-io/hindsight:0.10.2@sha256:d1840062a5b79940ab7a9f4809ceb90fc776d4ad737cd9329e9b5836cc64ab70`, with the selected database mode pinned separately. Set `HINDSIGHT_API_LLM_PROVIDER=openai`, `_BASE_URL` = local gateway, `_MODEL` = frozen GPT-6; explicitly freeze the `HINDSIGHT_API_{RETAIN,REFLECT,CONSOLIDATION,MENTAL_MODEL_REFRESH}_LLM_{MODEL,REASONING_EFFORT}` model/effort/provider/base overrides. Set `HINDSIGHT_API_LLM_TEMPERATURE=none` and leave `HINDSIGHT_API_LLM_TEMPERATURE_{RETAIN,REFLECT,CONSOLIDATION,VERIFICATION}` unset: explicit operation values override the global value, and their built-in defaults are respectively 0.1/0.9/0.0/0.0. Verify omission at the wire. Freeze local embedding/reranker choices under 8.2. Use owned API/database/worker identities and loopback publishing, and external PostgreSQL, since upstream calls embedded pg0 "not recommended for production". Leave `HINDSIGHT_API_ENABLE_OBSERVATIONS` and `HINDSIGHT_API_ENABLE_AUTO_CONSOLIDATION` unset, so observations and automatic consolidation keep their documented default `true` ([`configuration.mdx:2257-2258`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/configuration.mdx#L2257-L2258)), and create banks without configuration fields (4.3, r7 repair). | I:56–58; at 0.10.2: [temperature names and defaults](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-api-slim/hindsight_api/config.py#L216-L245), [operation config](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-api-slim/hindsight_api/config.py#L383-L462), [installation](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/installation.md#L37-L39); [loopback compose](https://github.com/vectorize-io/hindsight/blob/f8950b0c07d9e34c76493dba802bb309f0ce60fd/docker/docker-compose/claude-code/docker-compose.yaml#L14-L17) (unchanged at 0.10.2). Four of the five Hindsight files r6 cited at `f8950b0c` changed at 0.10.2, so these links supersede r6's line references. The recorded gateway request-shape probes (**9/9** across sol/luna/astra, `max_tokens` up to 64000, JSON-object and required-tool shapes) are wire compatibility for the 0.10.1 service, not a ≥65000-output or complete lifecycle acceptance. |
| **agentmemory 0.9.29** | Release commit `2d38dafede67d0d4ed920cde94d2106e98825b8a`, its lockfile, iii **0.11.2**, and the platform-specific iii digest. Use the upstream CLI/source-build path inside a fresh arm container, including the local Transformers optional dependency for the MiniLM diagnostic, plus an isolated engine volume/home. Pin the worker and MCP package independently; keep Node/model pins above. Embedder per 3.1 and GPT-6 LLM configuration as specified above. | [upstream start](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/README.md#L76-L115), [source build](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/README.md#L748-L765), [engine-only compose](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/docker-compose.yml#L1-L47). The MCP package's `~0.9.0` runtime dependency is not a runtime pin. |

**Deployment-source supplement (repair round 2).** The supplied deployment-spec review found six source-supported recipes deployable as specified (agentmemory, Hindsight, memsearch, basic-memory, OpenViking and engram) and five requiring the corrections below. These are source-review verdicts, not executed deployment acceptance. Every row still needs the frozen installation, test, lifecycle, configuration and artifact receipts above. Version/tag or health-only checks cannot replace a native ingest→ready→recall→delete→restart→restore check through both clients.

| System at the pin in 3.1–3.2 | Native recipe and required correction/configuration | Pinned upstream locators |
|---|---|---|
| agentmemory | Documented npm CLI install plus iii engine; root compose isolates only iii, so the CLI/worker and MCP must also be in the owned arm. Pin the package, iii binary and complete dependency closure; freeze the source-build/lock path if the npm install cannot reproduce it. | `rohitg00/agentmemory@2d38dafe:INSTALL_FOR_AGENTS.md:24`; `rohitg00/agentmemory@2d38dafe:deploy/README.md:4`; `rohitg00/agentmemory@2d38dafe:docker-compose.yml:26` |
| Hindsight | Versioned upstream Docker deployment with external PostgreSQL as selected above; pin both artifacts. Read back bank defaults, wait for retain and consolidation operations, and run the native durability checks. A full-image health response does not pre-pass these. | `vectorize-io/hindsight@5fc4ce20:hindsight-docs/docs/developer/installation.md:37`; `vectorize-io/hindsight@5fc4ce20:hindsight-docs/docs/developer/installation.md:152`; `vectorize-io/hindsight@5fc4ce20:hindsight-docs/docs/developer/api/operations.mdx:109` |
| memsearch | CLI/library with Milvus Lite by default; `uv tool install memsearch` is the documented form, while the version pin is an S3 adaptation and does not pin transitive dependencies. Use the source checkout and CI's `uv sync --all-extras` with a verified lock for reproducibility. Configure embedding and each plugin's named LLM provider separately in the isolated global config; run `uv run python -m pytest`, then native index/stats/search and both shipped hook paths. | `zilliztech/memsearch@2a4652fa:README.md:430`; `zilliztech/memsearch@2a4652fa:.github/workflows/test.yml:34`; `zilliztech/memsearch@2a4652fa:docs/cli.md:303`; `zilliztech/memsearch@2a4652fa:docs/cli.md:465` |
| basic-memory | Build the pinned Docker source (`docker build -t basic-memory .` upstream form), freeze its lock and image identity, and publish only the owned loopback port. Mount fresh data/config using the image's effective paths and UID, not a guessed host path. `basic-memory status` and `reindex` are native readiness steps; connect clients to this same store through upstream MCP transport. | `basicmachines-co/basic-memory@c0bd87c6:docs/Docker.md:64`; `basicmachines-co/basic-memory@c0bd87c6:docs/Docker.md:111`; `basicmachines-co/basic-memory@c0bd87c6:docs/Docker.md:292` |
| OpenViking | Upstream Docker run with owned config/data mounts; derive and verify the version tag/digest, or source-build with `UV_LOCK_STRATEGY=locked`. Persist `plugin.recallQueryExpansion=off` and `plugin.recallCompress=off` in `ovcli.conf` for both clients, then restart them; setting variables only during plugin installation does not configure later hooks. Verify `/health` and `/ready` plus actual ingest/find/client capture. | `volcengine/OpenViking@e8716760:docs/en/guides/03-deployment.md:214`; `volcengine/OpenViking@e8716760:Dockerfile:30`; `volcengine/OpenViking@e8716760:docs/en/agent-integrations/01-overview.md:54`; `volcengine/OpenViking@e8716760:openviking/server/routers/system.py:100` |
| engram (reserve) | Native binary, owned SQLite store and official MCP integration; prefer bare MCP without spawning plugin hooks, or freeze an explicit `ENGRAM_URL` pointing to the supervised owned server. Keeping just the same data-dir/port does not prevent a hook from starting an unsupervised server during restart. Cloud autosync stays off. Verify the version/store-aware `/health` and full lifecycle. | `Gentleman-Programming/engram@818be842:docs/AGENT-SETUP.md:328`; `Gentleman-Programming/engram@818be842:plugin/claude-code/scripts/_helpers.sh:86`; `Gentleman-Programming/engram@818be842:DOCS.md:293` |
| cognee | Keep auth on as selected above: set a fresh `DEFAULT_USER_PASSWORD`, provision the owned default user and API key, and set MCP `COGNEE_API_AUTH_SCHEME=x-api-key`; otherwise the first API calls 401. Apply `TELEMETRY_DISABLED=1` to the API **and** MCP processes. A source-built image may report `1.6.2-local`, not exactly `1.6.2`; compare this with the frozen image/source identity. Set the embedding provider/endpoint/model/dimensions explicitly to the selected local service. | `topoteretes/cognee@ba3631f2:cognee/api/client.py:132`; `topoteretes/cognee@ba3631f2:cognee/api/client.py:297`; `topoteretes/cognee@ba3631f2:cognee-mcp/src/cognee_client.py:84`; `topoteretes/cognee@ba3631f2:cognee/shared/utils.py:400`; `topoteretes/cognee@ba3631f2:cognee/version.py:22`; `topoteretes/cognee@ba3631f2:cognee/infrastructure/databases/vector/embeddings/config.py:97` |
| supermemory-local (reserve) | Pinned `supermemory-server` binary and documented env configuration, not AMB's cloud provider. Bounded native status polling must stop on `failed`, HTTP 404 (including auto-deletion), or deadline; `done` alone is insufficient without searchable expected evidence. Test auth with a wrong-key control and verify actual bind/isolation. The supplied review leaves the v0.0.8 loopback/container boundary unresolved; this reserve stays pending until it is source-backed and observed. | `supermemoryai/supermemory@5d2b5855:apps/docs/self-hosting/quickstart.mdx:55`; `supermemoryai/supermemory@5d2b5855:apps/docs/concepts/how-it-works.mdx:109`; `supermemoryai/supermemory@5d2b5855:apps/docs/ingestion/add-memories.mdx:73`; `supermemoryai/supermemory@5d2b5855:apps/docs/self-hosting/configuration.mdx:16` |
| MemPalace | Use the pinned source/image and the native remote-team compose with Qdrant, pinning both images. Run init/mine in that **same compose project/store/backend**, with a writable corpus mount; an unrelated `docker run` volume creates a separate Chroma palace. Init writes origin/config, entities, `mempalace.yaml` and `.gitignore`; freeze supported LLM-init settings. Retain compose's bearer-token guard and explicitly set Qdrant backend for helper processes. Confirm HTTP MCP initialize/list/call, `/healthz` and authenticated `/statusz`; telemetry suppression is not an egress barrier. | `MemPalace/mempalace@22fd87f0:deploy/docker-compose.server.yml:7`; `MemPalace/mempalace@22fd87f0:deploy/docker-compose.server.yml:47`; `MemPalace/mempalace@22fd87f0:mempalace/palace/backend.py:41`; `MemPalace/mempalace@22fd87f0:mempalace/cli/cmd_init.py:110`; `MemPalace/mempalace@22fd87f0:mempalace/cli/cmd_init.py:178`; `MemPalace/mempalace@22fd87f0:mempalace/cli/cmd_serve.py:145` |
| ai-memory | Build the pinned local image through `docker compose build`, then use the upstream `docker run --env-file` shape with the private 0600 env file, a new owned name/volume and a proven free loopback port. Compose's optional `docker/.env` does not load the external provider file and its fixed name/volume/49374 allocation is unsuitable for isolated scoring. Never allocate the live 49474 service or the known occupied 49374 default. Run value-free effective-provider checks and native lifecycle; liveness alone cannot prove the LLM overlay loaded. | `akitaonrails/ai-memory@a0ca8d1a:docker/docker-compose.yml:13`; `akitaonrails/ai-memory@a0ca8d1a:docker/docker-compose.yml:25`; `akitaonrails/ai-memory@a0ca8d1a:docker/docker-compose.yml:26`; `akitaonrails/ai-memory@a0ca8d1a:README.md:288`; `akitaonrails/ai-memory@a0ca8d1a:crates/ai-memory-cli/src/commands/serve.rs:2497` |
| Graphiti (reserve) | Build the standalone MCP image from the pinned source with core version 0.30.2, not its older default; record the resolved dependency lock and built digest. Use the documented Neo4j compose with `NEO4J_URI=bolt://neo4j:7687` inside the network, not the example env's localhost. Pull Neo4j 5.26.0 and pin its digest before using `--pull never`; mount the effective config at the command's actual path, and prevent startup re-resolution with the frozen native `uv run --no-sync` command. The endpoint/key/embedding split and lifecycle need functional acceptance. | `getzep/graphiti@eaa41286:mcp_server/docker/Dockerfile.standalone:46`; `getzep/graphiti@eaa41286:mcp_server/docker/README.md:92`; `getzep/graphiti@eaa41286:mcp_server/docker/docker-compose-neo4j.yml:3`; `getzep/graphiti@eaa41286:mcp_server/docker/docker-compose-neo4j.yml:38`; `getzep/graphiti@eaa41286:mcp_server/src/graphiti_mcp_server.py:1188` |

These corrections do not permit editing upstream source. Supported config and isolated launch adaptations must be frozen, with any unresolved image, lock, selected-repository gate, dependency SBOM/OSV scan, route or transport left pending. The private deployment-spec file is an input lead; the public evidence is the upstream locators above and the round-2 source receipt.

**cognee request envelope (r6, retained).** For route (a), carry `LLM_ARGS={"temperature":1.0,"extra_headers":{"x-omniroute-session":"<run-key>","X-OmniRoute-No-Cache":"true"}}` in a fresh process for each run. `<run-key>` is resolved **once at process start**, not dynamically per call; this static-only configuration omits idempotency and request-ID headers, subject to 2.2's wire/replay check. Temperature 1.0 satisfies the dedup exclusion without requiring instructor streaming. r6 verified that `LLM_ARGS` takes precedence over folded sampling defaults at 1.6.1 ([config.py:271–298](https://github.com/topoteretes/cognee/blob/eb90d03740755f5252b8b12cce91fd09970f2d81/cognee/infrastructure/llm/config.py#L271-L298)); `llm_args` is still present at 1.6.2 (`config.py:193,201`), and the wire check confirms the precedence before scoring. The gateway removes temperature downstream for Codex models, so 1.0 concerns gateway eligibility, not a claimed GPT-6 sampling temperature. The successful instructor `tool_call` smoke supersedes the research inference that LiteLLM's JSON-object fallback would work: that fallback and the strict KnowledgeGraph schema returned 400 in the supplied smoke (I:25–35). BGE-small from that smoke is only a shipped-default diagnostic; configurable scored retrieval uses 8.2's selected local model.

## 4. Dataset, metric and harness

### 4.1 Dataset and tracks

- **Dataset:** `longmemeval_s_cleaned.json`, sha256 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`, 277,383,467 bytes, from [xiaowu0162/longmemeval-cleaned @98d7416c](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json). It is static data under section 1. On 2026-09-30 the Hugging Face LFS oid of that file equalled the pin; the freeze hashes the downloaded file.
  - 500 questions, 30 of them abstention questions, whose `question_id` ends in `_abs` (LongMemEval `README.md:81` at `9e0b455f`, cited).
  - Full-track population: **n=470**. The upstream README states that retrieval evaluation skips the 30 abstention instances because they have no answer location (`README.md:206`, cited). r7 plans all 470 unless the **prospective 96 h feasibility rule** in 5.2 and section 6 selects a stratified subset before any confirmatory result. The full population and any selected subset each have a frozen manifest.
  - Official track: n=419, which also excludes 51 of the 56 `single-session-assistant` questions; 5 remain (frozen `eligible-manifest.json`, checked against the pinned dataset).
- **Tracks (r5), reimplemented in r7:**
  - **Official track:** upstream's user-text construction and relabelled gold IDs, reimplemented in the S3 adapter from the cited definition ([LongMemEval @9e0b455f `run_retrieval.py:202`](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/retrieval/run_retrieval.py#L202), `process_item_flat_index`; citation only).
  - **Full-session track (primary):** presents complete sessions to the native adapters and scores raw session IDs against `answer_session_ids`, including assistant-side evidence, following A2. This construction is a local extension.
  - Both are scored by the S3 scorer (4.2) and frozen as question manifests with sha256.
- **What candidates see (r6, extended in repair round 2):** answers, `has_answer`, gold-session labels and scoring feedback are never visible to candidates. Session, question, `Query.id`, `Query.user_id`, `Document.user_id` and provider namespace IDs are opaque, independently assigned without raw-ID substrings, category names or `_abs` suffixes. AMB's stock adapter passes the raw question ID as `user_id` (`vectorize-io/agent-memory-benchmark@03c1d0f1:src/memory_bench/dataset/longmemeval.py:296`); the S3 adapters replace that field too. The evaluator alone holds the opaque-to-original map and judge-only metadata; no provider request receives that map or category/gold annotations.
- **Development separation (r6, extended):** freeze separate development question/history manifests for role-effort, optional-stage, local-model and volume/power checks, with source hashes and overlap checks against all 500 LongMemEval QA questions, both retrieval tracks and every confirmatory LongMemEval-V2 trajectory/question. No confirmatory question, answer, gold label, score or per-model leaderboard number may choose an embedder, reranker, effort, optional stage or prompt. Published numbers motivate the shortlist only. The retained 25 coding/research-memory diagnostics are also excluded from tuning (R:41–53; coordinator brief B:E). A cost/power preflight may inspect outcome-free corpus size/strata but never tune on held-out answers or model outcomes.
- **Ranking (r6, retained):** artifact-to-session ranking and expansion (graph nodes, summaries and pages that reference several sessions) are frozen per adapter before any scoring. Ranked source-session IDs are deduplicated before top-5 selection. The scorer receives the complete eligible corpus IDs. A system whose output cannot be mapped to source sessions gets retrieval `N/A`, never a constructed score.
- **Dependence (r5, retained):** questions share evidence histories, so resampling is by cluster (section 6). Construction: union questions whose gold sessions share identical canonical sequences of `(role, content)`, excluding session IDs and gold annotations from the content hash (this repository's v4 `lme_summarize.py:234`, `clusters`). Counts: 452 full-track clusters (434 singletons and 18 two-question clusters) and 401 official-track clusters (383 and 18), reproduced with the frozen function on the pinned dataset. Session-ID matching would give 465 and 414, understating dependence. The manifest is frozen and hashed before scoring.

### 4.2 Metric definitions (the S3 scorer, in this repository)

- **Source.** The LongMemEval paper (Wu et al., "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory", ICLR 2025, [arXiv:2410.10813](https://arxiv.org/abs/2410.10813)), §3.3 "Evaluation Metric", paragraph "Memory Recall" (p. 6): because the benchmark has human-annotated answer-location labels, it reports "Recall@k and NDCG@k, where k is the number of top items retrieved by the system". At session level the labels are `answer_session_ids` (`README.md:88` at `9e0b455f`, cited).
- **Definitions**, for question q with non-empty gold set G_q and the system's ranking R_q of distinct source sessions (4.1):
  - `recall_all@k(q)` = 1 if every session in G_q is among the first k sessions of R_q, else 0;
  - `recall_any@k(q)` = 1 if at least one is;
  - `ndcg_any@k(q)` = DCG_k / IDCG_k with binary relevance, DCG_k = rel_1 + Σ_{i=2..k} rel_i / log2(i), and IDCG_k the same sum over min(|G_q|, k) relevant items;
  - each is averaged over questions and then seed-averaged as in section 6.
- These are the "all" and "any" session forms of the paper's Recall@k, and its NDCG@k, as upstream's reference code writes them ([`src/retrieval/eval_utils.py:4-29`](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/retrieval/eval_utils.py#L4-L29) at `9e0b455f`, cited, never executed). Some questions have up to 6 gold sessions, so a perfect `recall_all@5` is unattainable for them; this is reported, not corrected.
- **Why reimplemented:** the stale-repository rule (section 1). Separately, `eval_utils.py:6` calls `np.asfarray`, which NumPy 2.0 removed ([`doc/source/release/2.0.0-notes.rst:197`](https://github.com/numpy/numpy/blob/v2.5.3/doc/source/release/2.0.0-notes.rst#L197)), so it cannot run unchanged under the pinned NumPy 2.x.
- **Conformance:** the scorer ships with unit tests written from these definitions (duplicates in R_q, |G_q| > k, gold sessions absent from R_q, rankings shorter than k), reviewed against the cited text before freeze. No upstream code runs.

### 4.3 Harness

AMB at [`03c1d0f1d27da63034f0931121c858faba512383`](https://github.com/vectorize-io/agent-memory-benchmark/tree/03c1d0f1d27da63034f0931121c858faba512383) runs **byte-identical**; the freeze bundle verifies the checkout's tree hash. It is also AMB's default-branch head on 2026-09-30. All S3 code lives in this repository:

1. **LongMemEval dataset adapters** on the pinned file (4.1). Each is passed as the `dataset` instance to unmodified `EvalRunner.run` ([`runner.py:51-71`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/runner.py#L51-L71)). Each builds documents with opaque session IDs and an ID-free context (r6 N2, Appendix A) in place of AMB's `"{question_id}_{session_id}"` IDs and ID-bearing context ([`dataset/longmemeval.py:285-289,329-342`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/dataset/longmemeval.py#L285-L342)):
   - **retrieval variant**: `task_type = "retrieval"`, run in AMB's LLM-free `retrieval` mode. For a retrieval-typed dataset the runner scores only `raw_response["documents"]` ([`runner.py:222-227`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/runner.py#L222-L227)), which only [`modes/retrieval.py:56-61`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/modes/retrieval.py#L56-L61) supplies. In `rag` mode that key is absent, so the brief's "rag mode only" governs the next variant, not this one. `retrieval_limit` is the common depth (4.5), `score_retrieval` only exports each ranked opaque-ID list, and the S3 scorer (4.2) computes the metrics;
   - **open-QA variant**: `task_type = "open"`, run in AMB's `rag` mode only, because `agentic-rag` constructs `GeminiLLM()` whenever no LLM is passed in ([`modes/agentic_rag.py:8,26-27`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/modes/agentic_rag.py#L26-L27)). It inherits AMB's LongMemEval answer prompt (`build_rag_prompt`, `dataset/longmemeval.py:129-168`) and per-category judge prompts (`get_judge_prompt_fn`, `:177-258`) unchanged (5.5).
2. **Thin `MemoryProvider` clients** (HTTP, MCP or CLI) to each system's current upstream deployment (3.5). They implement AMB's interface ([`memory/base.py:8-79`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/memory/base.py#L8-L79)) without changing ingest or recall semantics, including each system's native store configuration (section 2). Since repair round 1 every system uses one, Hindsight included.
3. **No AMB provider is reused (r7 repair).**
   - r7 had reused AMB's `hindsight-http` provider for Hindsight ([`memory/hindsight.py:1242-1255`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/memory/hindsight.py#L1242-L1255)). That provider cannot keep Hindsight's native pipeline:
     - It creates every bank with `enable_observations=False` ([`_bank_kwargs`, `:218-219`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/memory/hindsight.py#L218-L219)), on the synchronous path (`:236-243`) and on the asynchronous path that AMB's per-unit ingest takes (`:425-433`). The 0.10.2 server stores that field as a bank override ([`api/http.py:1951-1954,1989-2030`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-api-slim/hindsight_api/api/http.py#L1951-L2030); `PUT /v1/default/banks/{bank_id}`, `:8364-8384`), and a bank with it `false` runs no consolidation at all, automatic or manual ([`memory-banks.mdx:242`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/api/memory-banks.mdx#L242)). Hindsight's documented defaults turn observations and automatic consolidation on ([`config.py:1711-1712`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-api-slim/hindsight_api/config.py#L1711-L1712); `memory-banks.mdx:240-246`; `configuration.mdx:2257-2258`). AMB has no setting that restores them: its only bank-level overrides are `AMB_RETAIN_MISSION` and `AMB_RETAIN_EXTRACTION_MODE` (`:224-233`).
     - Its asynchronous recall ignores the `k` that AMB's retrieval mode passes and sends `budget: "high"` with `max_tokens` 32768 (`:708-747`).
     - It builds its synchronous client from AMB's locked `hindsight-all` 0.4.17 (`from hindsight import HindsightClient`, `:1252-1255`; that wheel's `hindsight/__init__.py:60`).
     - A timed-out or five-times-failed asynchronous recall returns an empty list (`:1155-1180`).
   - Hindsight therefore gets a **thin local provider** in this repository. It speaks the 0.10.2 service's documented REST API over `httpx`, as AMB's own provider already does for recall (`:838-861`). It:
     - creates each bank with no configuration field, so the bank keeps the server's defaults; configuration fields belong to the separate config API, not to bank creation ([`memory-banks.mdx:508`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/api/memory-banks.mdx#L508));
     - before any ingest, reads `GET /v1/default/banks/{bank_id}/config` ([`api/http.py:9380-9382`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-api-slim/hindsight_api/api/http.py#L9380-L9382)), whose response separates the resolved `config` from the bank's `overrides` (`memory-banks.mdx:546-548`). It proceeds only if `overrides` is empty and the resolved `config` matches the frozen effective settings, whose canonical-JSON sha256 is frozen at freeze from a development bank created the same way. A mismatch stops the run before ingest;
     - treats ingest as complete only when `GET /v1/default/banks/{bank_id}/operations` ([`operations.mdx:109-117`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/api/operations.mdx#L109-L117)) lists no pending or processing operation of any type for the bank, including the `consolidation` operations that follow each retain (`operations.mdx:67-73`). A failed operation is a logged ingest failure;
     - maps facts and observations to source sessions under the common expansion rule (4.1, 4.5); an observation reaches its sessions through the facts it cites (`source_fact_ids`, [`recall.mdx:163`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/api/recall.mdx#L163));
     - uses the common depth policy and retry policy of 4.5.
   - AMB's `supermemory` provider is **not** reusable against the local server. Its indexing-status poll hard-codes `https://api.supermemory.ai/v3/memories/{id}` and sends the API key there ([`memory/supermemory.py:77-85`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/memory/supermemory.py#L77-L85)). It ignores `k` in favour of 30 results (`:7,113-119`), and it returns one merged context document (`:127-128`), so no session ranking exists. The provider's SDK honours `SUPERMEMORY_BASE_URL` (supermemory 3.28.0 `_client.py:113-115`), but the poll does not.
   - supermemory-local therefore uses a thin client in this repository. This departs from the brief on the evidence above.
4. **AMB's locked libraries are transitive dependencies, not candidate implementations (accepted user decision 3).** AMB imports every provider when importing the memory package (`vectorize-io/agent-memory-benchmark@03c1d0f1:src/memory_bench/memory/__init__.py:1-13`). This pulls in `rank_bm25` 0.2.2, `mem0ai` 1.0.5, `qdrant_client` and `sentence_transformers` even with thin providers (`src/memory_bench/memory/bm25.py:1`, `mem0.py:5`, `hybrid_search.py:5` at that pin). `cognee` 0.5.4 and Hindsight libraries are also inventoried from the lock; they implement no scored candidate. Include all these dependencies in each AMB arm's SBOM and clean OSV scan. Flag `rank_bm25`'s 2024-10-08 last commit as stale (1); it does not block the harness. **AMB execution remains pending for missing SBOM/vulnerability acceptance**, not for a transitive Maintained verdict. Candidate services still use the selected releases in 3.1, never the harness's older bundled providers.
5. **The frozen dispatch wrapper (r6, retained)** holds no ingest, retrieval, scoring or statistics logic. It launches per-unit `EvalRunner.run(..., unit=<question_id>)` processes ([unit filter 119–121](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/runner.py#L119-L121)) in the frozen block-randomized order at the frozen process concurrency, and records each process identity and exit status. It exists because AMB runs questions one at a time in one process, and its provider `concurrency` bounds only queries within a unit (runner.py:282–385, 338–363). The parity audit and the bundle review cover it. The v4 driver (#386) remains a cited adapter/provenance reference, never an executable S3 runner.

**Output ownership (repair round 2, M4).** Allocate a fresh `EvalRunner(output_dir=<run-output>)` for **each host × lane × track × opaque question × seed × arm × attempt**. `<run-output>` is an owned location outside the checkout, with a different directory for every tuple. AMB's native result file is exactly `<run-output>/<dataset.name>/<effective run_name>/<mode.name>/<split>.json` (`vectorize-io/agent-memory-benchmark@03c1d0f1:src/memory_bench/runner.py:474`). The run manifest names that file and the ranked-session export sidecar; analysis reads those exact paths, never a glob, shared arm directory or inferred last file. Only after process completion does the collector verify the expected opaque query IDs, final file/hash, attempt status and sidecar, then reconcile them against the frozen manifest (4.5). Concurrent processes never write one native result file: final saves filter to the current query set and `_save` performs non-atomic read/merge/write (`runner.py:459`, `runner.py:492` at the same pin). Repeated attempts retain separate files and usage; only the frozen retry policy chooses the final score.

**Open-QA parity (repair rounds 2–3, M3/M5).** Both `retrieve` and `async_retrieve` on **every** thin provider explicitly default to `k=20`; do not inherit the base class's async default of 10. RAG mode omits k (`vectorize-io/agent-memory-benchmark@03c1d0f1:src/memory_bench/modes/rag.py:49`; `src/memory_bench/memory/base.py:54`). After 4.5's common escalation, the open-QA provider returns **the shortest prefix of the final ranking that covers five distinct source sessions, capped at k=20 items**, with `raw_response=None`. At exhaustion/cap, return the available prefix up to 20 and flag fewer than five sessions; never reorder, replace items or add gold evidence to fill it. Retrieval-only scoring keeps the full final ranking and its first-five-session expansion. The lane is frozen in the provider configuration, not inferred from question/category labels or the value of k. AMB formats every returned document into the answer context (`modes/rag.py:52-54`), so limiting the request's initial depth alone was insufficient. The unchanged LongMemEval answer prompt uses the same formatted text contract for all arms (`src/memory_bench/dataset/longmemeval.py:131` at that pin). Provenance/session mappings remain evaluator-only. Record the exact emitted memory-context **o200k tokens per question×seed×arm**, plus per-arm totals/distributions, prefix items/sessions and native reader input tokens separately (5.2). Development parity checks exercise omitted-k RAG calls, explicit-k retrieval calls, cap/exhaustion cases and emitted prompt bytes for every provider.

The adapters are offered upstream to AMB after the S3 decision; the offer is not a precondition.

**LongMemEval-V2 is the main usefulness harness, not a finalists-only diagnostic (user decision, 2026-09-30).** Its native backend contract, commands, baseline and independent usefulness family are frozen in 5.5 and section 6. AMB retrieval remains the primary ranking lane.

### 4.4 Runtime settings for every AMB process

- `OMB_ANSWER_LLM=openai`, `OMB_ANSWER_MODEL=cx/gpt-6-astra-max`, `OMB_JUDGE_LLM=openai`, `OMB_JUDGE_MODEL=cx/gpt-6-astra-max` ([`llm/__init__.py:21-40`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/llm/__init__.py#L21-L40)). The class named `GeminiJudge` takes `get_judge_llm()` (`judge.py:36-39`), and the runner builds it at `runner.py:42`.
- `OPENAI_BASE_URL=http://127.0.0.1:20128/v1` on the workstation, and the Mac's own loopback gateway on the Mac (section 9). The locked `openai` 2.26.0 SDK reads it (`_client.py:164`). `OPENAI_API_KEY` is the gateway key, handled per `docs/secret-storage.md` and never recorded. AMB's client requests strict `json_schema` output (`llm/openai.py:32-39`). The brief relays that the gateway supports this; the wire check must confirm it before scoring.
- `GEMINI_API_KEY` is a non-secret placeholder for an unused provider. AMB's CLI only checks that a Gemini or Google key is present ([`cli.py:25-30`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/cli.py#L25-L30)). The dispatch wrapper does not import the CLI. With both `OMB_*_LLM=openai`, in `rag` or `retrieval` mode, no Gemini or Groq client is constructed (`llm/__init__.py:21-40`; `modes/rag.py:33-35`). Egress to Google and Groq endpoints is denied at the arm boundary, so any accidental call fails loudly, and the wire proof records zero such connections.
- There is no `.env` in the checkout, because `cli.py:12` would load one with `override=True`. `EvalRunner(output_dir=…)` points outside the checkout (`runner.py:40,474-475`). `LONGMEMEVAL_DATA_PATH` names the pinned file, never the mutable download (`dataset/longmemeval.py:73-90`).
- **Envelope.** AMB's OpenAI client sends none of the 2.2 headers (`llm/openai.py:14,32-39`), but it omits `temperature`:
  - the gateway's semantic cache cannot serve these calls, because `isCacheableForRead` requires `temperature` to be exactly 0 ([`src/lib/semanticCache.ts:483-493`](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/src/lib/semanticCache.ts#L483-L493), identical at `a58000c7` and at `v3.8.51`);
  - an absent temperature resolves to 1.0, which makes the calls dedup-ineligible (2.2 item 3);
  - the missing session header affects only account affinity;
  - before scoring, the wire check confirms in `call_logs` that no answer or judge call was served from cache or replayed.

**Header-limited clients (repair round 2, M6; extends the exception in 2.2 item 3).** A client without arbitrary gateway headers can use the same exemption only when pinned-source request review and a complete per-attempt `call_logs`/wire receipt prove endpoint, model/effective effort, within-run affinity, zero response-cache hits, zero dedup/replay and complete usage attribution for every nested/retried call. Missing headers are not themselves proof of these properties. Where the request shape cannot exclude cache/dedup, freeze a separate per-arm gateway route using **supported native controls**, with its source locators, configuration hash and measured negative controls before scoring; do not patch the client or silently alter the shared route.

agentmemory's auth-header builder provides no S3 custom-header control (`rohitg00/agentmemory@2d38dafe:src/providers/_openai-shared.ts:148`); its omitted-temperature path may qualify for the measured exemption, but no such receipt exists here. MemPalace's OpenAI-compatible client sends only auth and temperature **0.1** (`MemPalace/mempalace@22fd87f0:mempalace/llm_client.py:347`), which is **dedup-eligible** under 2.2, so the AMB reasoning cannot exempt it. **Both scored configurations are pending now** until the appropriate verified exemption or per-arm route is frozen. AMB's own exemption likewise remains conditional on its wire receipt. A successful response or an absent cache marker alone does not establish eligibility.

### 4.5 Vendor-bias controls and parity

AMB is maintained by vectorize-io, Hindsight's vendor. The controls:
1. **A primary metric with no LLM judge:** `recall_all@5` (4.2, 5.1).
2. **Equal depth, defined operationally (r7 repair).**
   - *Scoring depth:* the first 5 distinct source sessions of each ranking (4.2), for every provider.
   - *Initial request depth:* k = 20 for every provider. That is AMB's retrieval-mode default ([`modes/retrieval.py:34,45-47`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/modes/retrieval.py#L34-L47)); both thin-provider methods also default to 20 for open QA (4.3).
   - *One escalation rule (repair round 2, M5):* expand each native ranked artifact through the frozen source-session mapping, deduplicate in first-occurrence order, and stop as soon as it represents **five distinct source sessions**, the store is exhausted, or the frozen native cap is reached. Otherwise rerun the same native recall with depth multipliers **1, 2, 4, 8, 16**, clamped to its documented maximum. Count APIs start at 20 items (global cap 320); token-sized APIs start at their upstream-default token limit (global cap 16× that limit). Hindsight starts at `max_tokens=4096` and `budget=mid` (`vectorize-io/hindsight@5fc4ce20:hindsight-api-slim/hindsight_api/api/http.py:448`). The adapter manifest freezes each supported knob/cap and item→session expansion before scoring; a smaller immutable native limit is labelled and retained, never bypassed. Every provider uses this stopping rule, including count-based systems. No score/gold label chooses a depth, and the last returned ranking, not a best-of-attempts ranking, is scored. Record each request's depth, native items, expanded distinct sessions, stopping reason, usage and total latency. Unsupported escalation is recorded as a fixed native cap; unmappable output remains N/A (4.1).
   - *Recall effort:* upstream defaults; for Hindsight, `budget` `mid` (`api/http.py:448`; [`configuration.mdx:1630`](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/configuration.mdx#L1630)). A documented non-default level, such as the `budget: "high"` that AMB's replaced provider sent (`memory/hindsight.py:743`), is an optional stage under section 2's rule.
   - A ranking shorter than 5 distinct sessions at exhaustion/cap is scored as returned and flagged, with item/session counts and cap reason; it is never topped up from another arm or from gold evidence. Open QA uses the same retrieval escalation, then independently applies 4.3's shortest-prefix **20-item prompt cap**; a 320-item final ranking never enters the answer prompt in full. Report context tokens per arm, including the formatted headings/separators. If five sessions appear only beyond item 20, QA gets the first 20 and the insufficient-session flag.
3. **One parity checklist for every system, Hindsight included** (r6's pre-freeze audit, extended in repair round 1):
   - native ingest and recall at the common depth above, with identical session mapping and deduplication, and one expansion rule for artifacts that cite several sessions, such as graph nodes, summaries, pages and observations (4.1);
   - no oracle input, the frozen GPT-6 role matrix, and no vendor-specific shortcut;
   - each system's effective store configuration, read back before ingest and matched to its frozen settings (for Hindsight, 4.3);
   - wire proof that no provider receives a raw session ID;
   - the actual ingest and recall paths as AMB calls them under the per-unit dispatch (`async_ingest` and `async_retrieve`), exercised on development fixtures. Ingest ends only when the system's own status interface reports that every background operation it started has finished. Injected failures at ingest and at recall (refused connection, timeout, server error) must each end in a logged failure, never in an empty ranking or a silently dropped document;
   - one frozen retry policy (attempts, backoff and per-call timeout) in every thin provider;
   - provider logs that separate a failed recall from an empty ranking. AMB's replaced Hindsight provider did not: it returned an empty list after a timeout or five failed attempts ([`memory/hindsight.py:1155-1180`](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/memory/hindsight.py#L1155-L1180)).

   Registry coverage and source inspection are not parity acceptance.
4. **A GPT-6 adversarial audit** of the adapters, providers, scorer and checklist before freeze, in addition to the section 11 bundle review. Its findings are resolved before freeze.
5. **The vendor leaderboard and AMB's published results are ignored.**

**Failure accounting (repair round 2, H1; baseline clarification in round 3).** Before any result, freeze the retry attempts, backoff, timeouts and a **5% final-failure threshold** for every system/lane. A scheduled question×seed that still fails ingest, recall, answering, judging or result publication after that policy scores **0**, with a failure reason, every attempt and all known usage retained. It remains in the frozen score denominator and paired arrays; a failed retrieval has zero on all 4.2 metrics. Valid empty retrieval is a scored outcome, not an execution failure. This is an S3 collector rule: AMB may abort at its asynchronous gather and publish no row (`vectorize-io/agent-memory-benchmark@03c1d0f1:src/memory_bench/runner.py:363`; `:385`), so native summary accuracy is not the analysis denominator. Reconcile the exact result files against the expected manifest, including zero-score failure records stored in the collector ledger, without editing native results. If final failures exceed 5% of scheduled unique question-seeds in **any required lane**, that arm is `pending`; its all-pairs p-values are 1, never removed from the planned family. **If the no-retrieval baseline exceeds 5% final failures, the entire main-usefulness family is pending**, with p=1 placeholders for all m_U pairs; zero-scored baseline failures cannot manufacture superiority. Exactly 5% does not exceed the threshold. Source-reviewed deterministic executions count once for this rate, though their result is reused in seed averaging. Unstarted work, missing observer coverage or an interrupted run awaiting its retry policy is pending, not an invented zero or a complete result. Shared baseline/judge/infrastructure failures are retained and reported; no post-result deletion repairs the denominator.

**Executable open-QA prefix examples (synthetic integration rule, not native prompt acceptance).** The mapping is evaluator-side provenance from the final native ranking, as in 4.1. The answerer receives item text only.

```python
def open_qa_prefix(items):
    prefix, sessions = [], set()
    for item in items[:20]:
        prefix.append(item)
        sessions.update(item["sessions"])
        if len(sessions) >= 5:
            break
    return prefix, len(sessions) < 5

items = [{"id": i, "sessions": {str(i // 3)}} for i in range(320)]
prefix, short = open_qa_prefix(items)
assert [item["id"] for item in prefix] == list(range(13)) and not short
late = [{"id": i, "sessions": {"same"}} for i in range(20)] + [
    {"id": 20, "sessions": {"b", "c", "d", "e"}}]
prefix, short = open_qa_prefix(late)
assert len(prefix) == 20 and short
assert open_qa_prefix([{ "sessions": {"a", "b", "c", "d", "e"}}] * 20)[0] == [
    {"sessions": {"a", "b", "c", "d", "e"}}]
assert open_qa_prefix([]) == ([], True)
print("4.5 open-QA prefix examples: all assertions hold")
```

### 4.6 Isolation, cache proxy and private inputs (r6, retained)

- **Isolation**, which AMB and every provider-driven process must satisfy before any scored run (requirements from the GPT-6 reviews on #386):
  - owned ports, stores, homes and caches inside the fresh per-arm container/volume/home boundary in 3.5, with lane-owned `HOME` and `HF_HOME`;
  - server readiness that checks identity;
  - process and process-group identity (pid, start ticks, boot id, executable) checked before any signal;
  - fail closed on an occupied port or unreadable identity; protected workstation ports include **49474, 3800, 3710 and 5433**, with no scored allocation, signal or store access to those services;
  - `env -i` for vendor harnesses;
  - production services and stores are never touched. On the workstation that includes ai-memory on 127.0.0.1:49474, cognee-live on 3800 and hindsight-live on 3710/5433 (I:37–54).
- **Deny-by-default runtime egress (repair round 2, M2).** Permit only owned loopback/arm-local service addresses (including its database/sidecars), the exact host-local gateway endpoint and the selected local embedder endpoint; block **all other destinations**, DNS/external fallbacks and telemetry included, for every process/sidecar and IPv4/IPv6 path. Container-to-host transport is a narrowly verified endpoint exception, not permission to reach the whole host/subnet. External dependency/model downloads happen only in separate provisioning, with frozen artifacts available offline for scoring. Verify both allowed calls and refused external connection attempts, and retain value-free network observations. Do not rely on endpoint env variables or telemetry log suppression: cognee defaults embeddings to OpenAI (`topoteretes/cognee@ba3631f2:cognee/infrastructure/databases/vector/embeddings/config.py:19`), memsearch defaults its embedding and compact providers to OpenAI (`zilliztech/memsearch@2a4652fa:src/memsearch/core.py:62`, `:274`), agentmemory's fallback URL is `api.openai.com` (`rohitg00/agentmemory@2d38dafe:src/providers/_openai-shared.ts:25`), and MemPalace only suppresses a Chroma telemetry logger (`MemPalace/mempalace@22fd87f0:mempalace/__init__.py:59`). Any unverified network boundary leaves the arm pending.
- **Embedding-cache proxy: omitted, preregistered (r4).** v4's A16.3 says the cache gives no reuse between arms, because ai-memory writes wall-clock timestamps into session pages, and stays "only for byte-identical repeats, such as infra retries", with no arm ever cache-only (v4 `PREREGISTRATION.md:566-573`). So neither the v4 proxy (sha256 `e08e11f8…`) nor #380's is used. Omitting it means only that a byte-identical repeat is recomputed rather than served from the cache. Each run records its embedding server's runtime and device, so a recomputation difference stays attributable.
- **Private inputs (r6).** S3 freezes its own model/effort matrix, sanitized gateway identity and wire-check receipts. v4's Modelfiles, `embed_gates.json` and v3-check IDs gate v4's own driver, which S3 does not run. No credential store, authorization value or production memory store is an experiment input (2.1–2.2).

## 5. Lanes

### 5.1 Retrieval (primary lane)

- **Metric:** `recall_all@5` (every supporting session in the top 5) on the full track (4.2).
- **Secondary:** the official track, and `ndcg_any@5`.
- **Arms:** one primary arm per system (section 2). Every departure from defaults is frozen.
- **Stale defaults:** MiniLM and BGE-small appear only in controls, diagnostics or genuinely fixed-provider configurations labelled **shipped default**. A provider/model switch changes the arm manifest before freeze, never after scores. Native pipelines that cannot host an alternative are recorded explicitly, not patched to manufacture a SOTA claim (I:21).
- **Diagnostics outside the family:** 3.4.

### 5.2 Token ledger and workload cost

**Frozen workload (r6, retained):** identical recorded coding sessions from this repository's own work, frozen with sha256; a frozen recall schedule (N recalls per session at fixed points); frozen queries, context boundaries and aggregation.

**Ledgers**, per host and per system, never added to one another:
- **(a) Ingest and internal LLM tokens per system and role**, from OmniRoute `call_logs` native usage (uncached input, cached input, output and reasoning kept apart). This covers every call the system makes (capture, extraction, consolidation, summarization, reranking, query rewriting and retries), attributed by the frozen per-run correlation key.
- **(b) Recall payload tokens:** `o200k_base` counts of each recall's returned and injected payload with [gpt-tokenizer 4.0.0](https://github.com/niieani/gpt-tokenizer/releases/tag/4.0.0) (`fb04ebca53f662200e737caefe9a5ef372a5e41a`; this repository's token-report pin since #493, `docs/token-practice.md:273`).
- **(c) Per-session injected context in each client.**
  - Claude Code: native usage from `claude -p --output-format json`, whose payload carries usage and `total_cost_usd` with a per-model breakdown ([headless docs](https://code.claude.com/docs/en/headless)).
  - Codex: `codex exec --json`, whose `turn.completed` events carry `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens` and `reasoning_output_tokens` ([`codex-rs/exec/src/exec_events.rs:20-21,50-72`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/exec/src/exec_events.rs#L50-L72)).
  - Each system is installed upstream-clean in a scratch `CLAUDE_CONFIG_DIR` or `CODEX_HOME` and runs the frozen workload. `CLAUDE_CONFIG_DIR` overrides `~/.claude` and holds settings, session history and plugins ([env-vars docs](https://code.claude.com/docs/en/env-vars)). `CODEX_HOME` must already exist as a directory ([`codex-rs/utils/home-dir/src/lib.rs:6-11`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/utils/home-dir/src/lib.rs#L6-L11)).
  - The same client's no-memory control runs the same workload. Its usage is reported beside each system's as a signed difference, never subtracted inside C (r7 repair).
  - The user's real `~/.claude` and `~/.codex` are never read or written; they stay frozen until Gate A window W closes.
  - Scratch homes sign in through a supported non-interactive route the user sets up; no credential is copied from the real homes (section 11).
- **(d) Latency p95 and resources** (5.3).

Count once: a payload count is never added to a usage total that already contains it. Unknown usage stays unknown and leaves that system's cost `pending`, never zero. MCP-only paths are measured at the client tool-call boundary. Payload-only counts support only a payload-size claim; being under a budget is not a token-saving claim.

**Ingest reuse and volume preflight (repair round 2, L4).** Open QA on a selected non-abstention full-session question may reuse retrieval's ingest only if corpus bytes, track construction, arm settings, opaque-ID map and seed are identical, and an upstream-supported pre-query snapshot/restore provides an independently verified clean copy of the fully ingested store. The query/output/affinity identities remain separately scoped by lane; QA cannot inherit retrieval-induced state changes. If native snapshot/reset cannot establish this, ingest separately and price/project that extra work. Official-track construction and the 30 abstention histories require their own ingest unless an identical eligible snapshot is already recorded. LongMemEval-V2 has different trajectories and never reuses LongMemEval-S ingestion. Charge actual reused ingest once, with the shared artifact hash and reuse edges recorded. Before freeze, project retrieval, optional QA, main usefulness, secondary TTL/CR, development, reader/judge and retries separately; choose and hash their prospective subsets using measured cost and power, then publish the combined host volume without double counting.

**Decision cost scalar C (tie-break 1 in 7.3; repaired in round 1).**
- C is the **gross, nonnegative** priced cost of the frozen workload above, per host and system. It sums, over every model invocation that workload causes in ledger (a) (the system's own calls while serving it) and ledger (c) (both clients' own model calls in its sessions), the sum over the invocation's token classes (uncached input, cached input, cache write, output including reasoning) of tokens × the frozen list price of that model and class. Usage from LongMemEval and the other benchmark lanes is reported in ledger (a) but never enters C.
- The control difference ΔC = C − C₀, where C₀ is the same clients' no-memory control on the same workload, is reported beside C and may be zero or negative. It never enters 7.3, because a ratio of control-subtracted costs moves with the baseline: gross costs of 120 and 130 stay tied under 7.3's 0.80 ratio, while 20 and 30 left after subtracting 100 would not.
- C is computed exactly, as a rational number from integer token counts and the frozen decimal prices, so that 7.3's equalities are exact.
- The price table is frozen at freeze for every model ID involved, with the authoritative model/provider price source, exact route-to-model mapping, token classes, currency/unit, retrieval date and saved-page sha256. A gateway alias or embedded cost-map estimate is not a list-price source. **The `cx/` GPT-6 routes are currently `unpriced`**: this offline repair has no authoritative price/mapping receipt and invents none.
- **One missing-price policy (repair round 2, L2):** omit unpriced invocations from the labelled priced subtotal, list their measured token classes separately, and leave **total C unavailable** if any workload invocation has unknown usage or an unpriced class. Never call the subtotal C, substitute zero, use subscription spend as a token price or compare a partial total to a complete one. Unknown prices do not exclude a system on merit (7.1); when 7.3 could change the selection, its cost decision is unresolved. A model-price receipt or a dated pre-result amendment is required to resolve it.
- **Unpriced local inference (repair round 2, L1):** local embedder/reranker/generative inference has no list-token charge inside C. Report its serving time, hardware/energy assumptions and resources separately (5.3); the resulting C comparison is a **priced-model-call cost** comparison, not total operating cost. At acceptance state the exact boundary: a member j with C_j > c_min leaves the cost-tied set iff **c_min ≤ 0.80 C_j**, equivalently **C_j ≥ c_min / 0.80**; all exact minima, including zero, stay. Report sensitivity with an explicitly labelled omitted local cost L_i: the total-operating-cost boundary would use **min_i(C_i + L_i) ≤ 0.80(C_j + L_j)** for non-minima. Do not insert guessed L_i into the frozen decision after results.
- 8.3's RAG decision uses C_RAG, defined there.

**r6 ingest budget, throughput and wall-clock feasibility (retained).** Use **about 115K extraction-input tokens per LongMemEval-S question per GPT-6-powered system** as coordinator brief B:G's planning assumption, not a measured total for every architecture (coordinator brief B:G; the approximately 115K-token history scale is also documented in [Attemory's pinned benchmark overview:125](https://github.com/AttemorySystem/attemory/blob/603c03afa9a04e48b778922eae156a0024752f37/README.md#L125)). Native calls may revisit text, and some systems have no extraction role; measure each complete workload rather than treating this estimate as usage.

- Full 470 implies **54.05M** extraction-input tokens per system per ingest pass. Five independent ingest/seed passes imply **270.25M** per such system per host; if all eight systems incurred that rate, the planning envelope would be **2.162B per host**, **4.324B across both hosts**. These are arithmetic scenarios, not invoices or accepted evidence. QA's 30 abstentions, the official-track construction when separately ingested, development, diagnostics, replies/reasoning, reflect/consolidation and retries add work. Record actual overlap once; do not multiply reused artifacts or sum cached subsets twice.
- **Concurrency is a frozen throughput parameter, not a quota gate.** The user's recorded 2026-09-27 direction for GPT-6 is **“full parallel utilization”** (relayed at V:32 from memory `provider-limits-and-logins.md:17–25`, historical evidence, not authority); coordinator repair decision 2 applies it as the K rule below. Use **K in-flight GPT-6 calls per host**, with K chosen on the development split from **measured throughput and fresh 429s**. Set it through each system's supported knobs, including nested/background calls, record the departure from defaults, and verify effective concurrency from `call_logs`; unsupported enforcement leaves the configuration pending. Use a **block-randomized dispatch order, identical across arms**, with its randomization seed frozen. Preserve conversation affinity and each host's own gateway; record any shared-account contention. Seeds replicate **only stochastic components**: an arm shown deterministic by pinned source review is **ingested once and counted once**, with the same value used in paired seed comparisons without inventing independent runs or duplicate usage.
- **Wall-clock decision:** the confirmatory retrieval run has **96 hours of wall-clock per host**, covering its selected arms, ingestion and retrieval, plus separately ingested track work, startup and retry overhead. This is the **coordinator's decision under delegated authority**, and the **user may overturn it before the freeze**. Before freeze, record development **tokens/s**, measured ingest/query durations, effective K and startup/queue overhead, and the projected wall-clock for **each host** under the complete planned work. If either projection exceeds **96 h**, adopt B:G's **prospective stratified subset by question type and dependence cluster**, with section 6's power calculation for the pairwise Holm family, before **any confirmatory result**. Freeze the selected manifest and recomputed cluster counts; do not truncate retrospectively to fit the window. If no justified subset fits, the retrieval plan remains pending before freeze.
- Preserve native pool cooldown/backoff and current `Retry-After` handling. Fresh 429s, timeouts or provider exhaustion are recorded with usage and handled by supported backoff. **Never gate on a recorded quota**, infer a current refusal from an old receipt, or replace GPT-6 with a stale model. Unexpected window overruns preserve incomplete work as `pending` and require a dated amendment, never an unplanned subset or early success stop. The separate latency lane in 5.3 excludes other arms' in-flight calls. Sources: coordinator repair decision 2 and B:G; I:35 is one small canary, **not** measured full-run throughput; R:31–53 supplies the development role comparison, **not** a pacing limit.

### 5.3 Latency and resources (r6 4.3, retained)

- **Measured:** client-observed time until usable evidence is delivered, including embedding, expansion, reranking and IPC or network time.
- **Frozen per host:** corpus, request schedule, 200 requests, concurrency 1, a 20-request warm-up discarded, and the nearest-rank quantile estimator.
- **Distributions:**
  - cold (the first request after a server start, 10 starts) and warm, reported separately;
  - the **warm p95 is the gated statistic**;
  - timeouts (10 s) and failures count at the timeout value and are reported. Latency is never computed from successful requests only.
- **Query-path GPT-6 calls are inside the gated warm p95**. The **1.0 s bar and 10 s timeout are unchanged**; a native query path requiring GPT-6 may be **latency-ineligible**, declared before execution. Run the latency lane with **no other arm's call in flight on that host**, keeping its frozen concurrency 1. Report dispatch queue wait separately; queueing/internal work after query submission remains in client-observed latency. Throughput-lane scheduling cannot hide or contaminate this gate.
- Also measured: peak RSS, VRAM on the workstation, disk growth, ingest-to-query-ready time, and cold-start time.

### 5.4 Coding-agent acceptance and early lifecycle screen (r6 4.4, retained)

**Coding-agent acceptance (both clients, official integrations only).** Order: Claude→Codex, then Codex→Claude. Isolated client profiles, with the enabled memory owners recorded explicitly. MCP-only systems must capture through real client tool calls. Required:
- capture of a unique decision, correction, failed approach and fix;
- scoped cross-client recall, with canaries in an adjacent project that must stay out;
- supersession of an updated fact;
- stored untrusted text treated as data;
- deletion, verified after restart and consolidation;
- restore into an empty instance;
- restart and interrupted-ingestion durability.

**Early development lifecycle screen (r6), before expensive confirmatory ingest.** Run these on disposable development fixtures on **each host**. They triage reported risks; issue reports are not new reproductions or automatic disqualifications. Reproduce the exact selected pin/path, retain commands/output and independent observations, and distinguish a reproduced failure (`FAIL`) from an unexecuted check (`pending`). A failed required lifecycle item makes the arm ineligible under section 7; missing arms do not shrink the planned family. Passing these checks does not replace the complete acceptance above after retrieval ranking.

| Report to probe | Frozen development check and required observation | Source |
|---|---|---|
| agentmemory **#1273**, governance deletion reports a match but deletes nothing | Capture a unique observation through each native client; delete through the supported intended path; prove absence in storage and BM25/vector/graph recall after restart and consolidation. A success response or `deleted:0` alone cannot pass. | [upstream report](https://github.com/rohitg00/agentmemory/issues/1273); M:45,128 |
| agentmemory **#1190**, additive restore / omitted stores | Snapshot records spanning the stores used by the arm; restore into a **fresh empty instance**, compare the full expected inventory and search/graph state, then verify a post-snapshot sentinel is absent. Separately probe restore into a dirty development instance to expose additive behavior; do not use it to reset scored questions. | [upstream report](https://github.com/rohitg00/agentmemory/issues/1190); [export/import at the pin](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/functions/export-import.ts#L306-L399) |
| agentmemory **#1389**, iii 0.11.2 memory growth/OOM | A bounded four-hour development hook-write soak, including provider-backoff windows, with frozen write schedule and host resource ceiling. Observe RSS/queue growth, completion and restart recovery; stop at the ceiling, preserving the failure. No claim that a shorter smoke rules out the reported sustained-load failure. | [upstream report](https://github.com/rohitg00/agentmemory/issues/1389); M:76,128 |
| MemPalace **P0 #1581**, HNSW corruption | Exercise the selected release's own overlapping MCP, hook and auto-ingest writers in one disposable arm; interrupt/restart, then verify index readability and every expected canary. Do not suppress native concurrency merely to avoid the report's trigger. The report names 3.3.0; behavior on the S3 3.10.0 pin must be measured. | [upstream report](https://github.com/MemPalace/mempalace/issues/1581); M:77,128 |
| Hindsight, reported **pg0 fsync-off** | Treat M's pg0 0.15.2 statement as an unverified lead. Inspect effective `SHOW fsync`, `SHOW synchronous_commit`, `SHOW full_page_writes`, database version and startup arguments in the isolated deployment; retain acknowledged-write inventory across interrupted ingestion and database/container crash/restart. Use upstream-supported durable external PostgreSQL if the embedded setup fails; freeze that choice before scoring. Process restart alone does not prove power-loss durability. | M:139,172; [upstream embedded-DB caveat at 0.10.2](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/installation.md#L37-L39) |
| Hindsight, reported **65K output-token requirement** vs GPT-6 limits | Check the frozen GPT-6 route's actual context/output limits and native retain behavior before ingest. At 0.10.2 the docs require at least 65,000 output tokens for listed-model parity (models.mdx:156) while advising the retain cap stay at its **64000** default (models.mdx:466; `config.py:1628`); 64000 does **not** prove 65000 output capacity or full extraction. Freeze any supported `HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS` adjustment, keep it greater than `HINDSIGHT_API_RETAIN_CHUNK_SIZE`, and probe truncation, schema completion, retries and retained-evidence completeness. An unknown GPT-6 limit remains a gate to resolve, not an invented number or a switch to an older model. | [models.mdx:156,466 at 0.10.2](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/models.mdx#L156); I:58 |

### 5.5 Usefulness

**Main test: LongMemEval-V2 (ACCEPTED 2026-09-30; replaces the minus-one floor and S8 usefulness coupling).** Use `xiaowu0162/LongMemEval-V2@2cc8c540bdb87fe6761629b585e727e1c4704520`, active under section 1. It has 451 curated questions over long web/enterprise agent trajectories and five abilities: static state recall, dynamic state tracking, workflow knowledge, environment gotchas and premise awareness (`xiaowu0162/LongMemEval-V2@2cc8c540:README.md:32`, `:41`, `:50`). This measures experience accumulated over long histories; short single-session coding outcomes cannot veto its usefulness conclusion.

- **Native integration.** Implement each thin backend against upstream `memory_modules.memory.Memory`, with `@register_memory`, a unique `memory_type`, native `insert(trajectory)` and `query(query, query_image=None)` returning typed text/image context; preserve the pinned service's ingest/recall semantics and shared-memory lifecycle. A memory-config JSON contains `memory_type` and `memory_params`. The harness exposes `--memory-config-path`, `--save-memory` and `--load-memory-dir`; it keeps question IDs/categories/gold/evaluator settings private and gives the backend only a random `query_invocation_id` (`xiaowu0162/LongMemEval-V2@2cc8c540:memory_modules/memory.py:25`, `:146`; **`README.md:219-223`**; `evaluation/harness.py:128`). Config JSON does not import custom classes: the S3 registration bootstrap must import its adapter before calling the unchanged harness entry point, following the published registration pattern; it contains no evaluator logic. Review and freeze that integration before native acceptance.
- **One native invocation per domain, including the control (round-3 item 1).** Use upstream data preparation/validation (`README.md:114-117`), then run **every arm through the same direct `evaluation/harness.py` entry point**, separately for `web` and `enterprise`. The no-memory control uses upstream **`evaluation/memory_configs/no_retrieval.json`**, byte-identical; `run_eval.py:188-189,297-354` constructs and calls that same native no-retrieval backend internally. Do not score the control through `evaluation/scripts/run_no_retrieval.sh`: its two-domain wrapper forwards temperature 0.6, top-p 0.95, top-k 20 and reader concurrency 16, omits reader reasoning effort and evaluator base URL (`run_eval.py:75-78,301-343`; `harness.py:853-854,875-880`). All custom backends and the control use the same frozen registration bootstrap, which only imports backend classes and calls unchanged `evaluation.harness.main()` with the direct-harness argv below. The bootstrap module in this template is a required, separately hashed S3 integration artifact; it is not built or run by this revision. Keep upstream source byte-identical.
- **Backbone and judge; frozen common arguments.** For every memory arm and no-retrieval control, freeze the following same direct-harness argv. Only the domain, its preselected runtime files, memory config and owned output directory vary by arm/domain/replication; the schedule seed varies by paired replication, identically across arms. Reader and evaluator models are **`cx/gpt-6-astra-max`**, both endpoints are the host gateway, and both CLI reasoning-effort arguments are **`high`**: reader choices are at `evaluation/harness.py:169`, judge choices at **`:193-196`**. There is no native `max` argument; the route suffix and 2.2 wire check must establish effective max. Reader/evaluator completion limits are 20,000/4,096, both timeouts 43,200 s, memory context cap 200,000, reader concurrency 16, prompt-build workers 1 and native reader thinking enabled. **Omit temperature, top-p, top-k, presence/repetition penalties for every arm**; the evaluator also omits sampling overrides (`evaluation/qa_eval_metrics.py:517-528`). Freeze the effective defaults and retry configuration as well. No Qwen-specific `top_k` or thinking-template request field is allowed on the GPT-6 route.

```sh
# Template, one domain/arm/paired replication; variables name frozen public artifacts.
rtk python -m s3_lme_registration \
  --domain "$S3_LME_DOMAIN" \
  --questions-path "$S3_LME_QUESTIONS" --haystack-path "$S3_LME_HAYSTACK" \
  --trajectories-path "$S3_LME_TRAJECTORIES" \
  --memory-config-path "$S3_LME_MEMORY_CONFIG" --output-dir "$S3_LME_OUTPUT" \
  --model cx/gpt-6-astra-max --base-url "$S3_LME_GATEWAY" \
  --api-key-env OPENAI_API_KEY --reasoning-effort high \
  --max-completion-tokens 20000 --memory-context-max-tokens 200000 \
  --timeout-seconds 43200 --reader-max-concurrent-requests 16 \
  --prompt-build-max-workers 1 --reader-enable-thinking \
  --shuffle-questions-seed "$S3_LME_PAIRED_SCHEDULE_SEED" \
  --evaluator-model cx/gpt-6-astra-max --evaluator-base-url "$S3_LME_GATEWAY" \
  --evaluator-api-key-env OPENAI_API_KEY --evaluator-reasoning-effort high \
  --evaluator-max-completion-tokens 4096 --evaluator-timeout-seconds 43200
```

- **Request-body wire acceptance is mandatory.** Capture sanitized reader and judge request bodies for every arm/control, domain and nested/retried call path. Compare all non-content parameters, including present/absent sampling and extra-body fields, completion limits, model and reasoning effort; confirm `--evaluator-base-url` actually routes the GPT-6 judge to the same host gateway. Record native concurrency, effective gateway/provider effort and 2.2's zero cache/dedup/replay and complete usage attribution. Deliberately add wrapper temperature/top-k in a development negative control: parity must fail. A matching argv, shell environment or route suffix does not prove matching emitted requests; any gap leaves that arm/control pending.
- **Prospective small-tier selection.** Start with tier **small**, both domains and all five abilities. Before any confirmatory result on either host, a held-out development preflight measures native ingest/reader/judge tokens, retries, startup, serving time and seed dependence. It first verifies section 6's outcome-independent haystack-component manifest and **minimum 20 clusters against the downloaded haystack/trajectory files**, then its cost/power estimate chooses full-small or a stratified subset by domain/ability and those fixed clusters, checking the minimum again for the selected sample. Freeze the manifests, selected IDs, downloaded-byte hashes, five replication IDs, run order, aggregation, context limits, budget/window and power at the actual sample/cluster count. Materialize the runtime files once **per domain**, using upstream `data.public_data.materialize_runtime_questions` and `materialize_runtime_haystack` (`data/public_data.py:79-124`), then use identical bytes for every arm and control in that domain. Each question-ID list contains only that domain's IDs; the native selector rejects a cross-domain list (`data/public_data.py:88-93`). `run_eval.py`'s question-ID flag is at **`:70`**, not `:69` (`--limit`); it is not a preparation-only command. No retrospective truncation, component splitting or best-of-seed selection. A shuffle seed is a schedule seed, not deterministic provider sampling. Deterministic ingestion may be reused once with provenance; stochastic reader/judge calls still get five paired replications.
- **Outcome and usefulness rule.** Aggregate native per-question correctness into question-weighted accuracy after averaging five paired replications. Final failed question-replications score zero under 4.5; missing execution and a baseline failure rate above 5% remain pending. Bootstrap section 6's **fixed shared-trajectory haystack components**, retaining each component's questions and all replications together, and apply Holm to the frozen usefulness family. **Fewer than 20 independent components leaves usefulness pending; no question-level substitute test is authorized.** A system passes if significantly better than no retrieval and not significantly worse than any point-estimate maximizer among operationally eligible, completely observed memory systems. A significantly worse system or lack of superiority evidence is unqualified, not evidence of no benefit. This is usefulness qualification; 7.6 separately defines the accepted fallback only when the qualification/selection is resolved. Report ability/domain strata, failures, power, cluster count and uncertainty.
- **Status.** No main-usefulness model run is claimed by this revision. Missing backend/native wire acceptance, dataset manifest, failure accounting, preflight or paired outcomes leaves this lane pending.

**Secondary: MemoryAgentBench TTL and CR, applicable systems only.** Use `HUST-AI-HYZ/MemoryAgentBench@538026089d1a8a8eff05121d0db89b388f360eba`, subject to the selected-repository gate, dependency SBOM/OSV policy and isolation. Native TTL ICL uses `exact_match`; CR fact-consolidation uses `substring_exact_match` (`README.md:178-180`). The real script is `bash_files/sh/run_memagent_rag_agents.sh:18`, invoking `python main.py --agent_config <frozen-config> --dataset_config <frozen-split>`; the README's `bash_files/eniac/...` path is absent at this pin. Freeze supported config/commands on GPT-6 and the local embedder, with native wire/lifecycle acceptance, rather than the author's shell/GPU/model choices. **Secondary results are reported only for applicable systems/modes below; never reach a selected candidate through a vendored copy.** They do not replace the main test or exclude systems lacking a native route.

The pinned dispatch recognizes `letta`, `mem0`, `cognee`, `zep`, `knowl`, `agentmemory`, `total_agent_memory` and `rag_*`, plus long-context controls (`agent.py:64-89`). Those names do not make the eleven S3 memory deployments or the document-RAG candidates interchangeable. Applicability is source-reviewed at this pin, not a run or a universal capability claim:

| Selected system | Pinned MemoryAgentBench path | Applicability / secondary status |
|---|---|---|
| agentmemory v0.9.29 | Native REST mode to the external service (`methods/agentmemory.py:3-17,111-128,142-190`) | **Applicable to normalized-fact CR only**, pending native acceptance. It parses and ingests prepared facts, not raw trajectory/session extraction. TTL is not established for this CR-specific parser (`:57-82`); no TTL result is claimed. |
| Hindsight v0.10.2 | No Hindsight dispatch at `agent.py:64-89` | Not applicable in the pinned native runner. |
| OpenViking v0.4.22 | No OpenViking dispatch at `agent.py:64-89` | Not applicable. |
| cognee v1.6.2 | `cognee` mode imports the benchmark's vendored tree (`agent.py:236-243,518-531`) | **Not applicable to the selected 1.6.2 release; vendored execution prohibited.** |
| MemPalace v3.10.0 | No MemPalace dispatch at `agent.py:64-89` | Not applicable. |
| basic-memory v0.23.2 | No basic-memory dispatch at `agent.py:64-89` | Not applicable. |
| memsearch v0.4.21 | No memsearch dispatch at `agent.py:64-89` | Not applicable. |
| ai-memory v2.4.2 | No ai-memory dispatch at `agent.py:64-89` | Not applicable. |
| engram (reserve) | No engram dispatch at `agent.py:64-89` | Not applicable. |
| Graphiti (reserve) | `zep` constructs `zep_cloud.Zep` (`agent.py:245-255`), not the selected Graphiti service | Not applicable; Zep cloud is no substitute. |
| supermemory-local (reserve) | No supermemory dispatch at `agent.py:64-89` | Not applicable. |
| qmd, LightRAG, llama_index document-RAG arms | Generic `rag_*` modes at `agent.py:86-87,258-265` do not dispatch these selected pipelines | Not applicable to those arms; native RAG controls may be labelled separate diagnostics. |

Letta/Mem0 remain excluded on fit (3.3), and Knowl/total_agent_memory are not S3 selected arms. Their dispatch presence is not admission to the family; a vendored implementation never supplies secondary acceptance for a selected release. Adding support requires a separate upstream-backed amendment before results. No MemoryAgentBench run is claimed here.

**MemoryArena is citation-only.** `ZexueHe/MemoryArena@6cd9de14b71915e39ac742a20dc33785e14b6aab`, ICML 2026, last commit 2026-05-31, is stale under section 1. Never run its scripts, evaluator or packages.

- **(a) Coding/research-memory diagnostics (r6 tasks retained):** retain **20 frozen queries plus 5 bounded continuation tasks**. **At least 8 of the 20** are US-equities research-memory queries, anchored below in recorded decisions and their evidence. Each of all 25 tasks gets frozen expected evidence, source hashes, semantic-success criteria, answerer/context policy and a binary success result. These are memory tasks for research agents: the north-star diagram sends scoped memory into research, whose output is evidence and proposals (`blueprints/us-equities/north-star.md:33–35,57–60,74–79`; `catalogs/us-equities/README.md:52–58`). This adds no strategy, data-availability or broker qualification claim. They are reported diagnostics, not the new usefulness qualification.
- **(b) LongMemEval QA (r7):**
  - Plan all **500** questions through the open-QA adapter variant (4.3) in AMB's `rag` mode; the cost/power preflight may choose a prospective, frozen stratified subset, with its actual counts reported. All 30 abstentions remain a separately identified population/audit stratum; subset reports never claim full-500 coverage. QA is secondary and consumes the separately projected workload in 5.2.
  - **GPT-6 Astra at max** (`cx/gpt-6-astra-max`) is both the fixed answerer and the judge, through each host's gateway (4.4).
  - AMB's LongMemEval answer prompt and per-category judge prompts are used unchanged (`dataset/longmemeval.py:129-168,177-258`). This replaces r6's plan to send upstream LongMemEval's `get_anscheck_prompt`, which is now citation-only (section 1).
  - **Abstention and empty context (repair round 2, L3).** AMB scores **any open-QA empty context wrong without judging**, even if the answer appropriately abstains (`vectorize-io/agent-memory-benchmark@03c1d0f1:src/memory_bench/runner.py:228`). Retain that native zero, mark it `empty_context_unjudged`, and report its count/rate by arm and abstention stratum; never claim it was a judge verdict. Non-empty-context abstentions use the unchanged base-category prompt, which has **no abstention branch**. Report native QA accuracy with that validity limit and separately audited abstention correctness; the audit cannot silently replace native scores. Every included abstention is in the manual-audit sampling frame. Provider-facing IDs have no `_abs` suffix or other category hint (4.1).
  - Keep the **stratified manual audit of abstention and knowledge-update questions**, its sampling rule and adjudication record.
  - The answerer sees only the question and the allowed retrieved context. The judge sees the question, the gold answer and the response, without arm or model labels, cost or latency results, or rankings. Shared model family and blinding do not establish judge validity.
  - 5.5(b) stays `pending` until the answerer and judge calls pass the 4.4 wire check.
  - Results are reported as **S3 QA scores with a gateway-hosted answerer and judge**, never as official leaderboard or local-inference scores.

**Research-memory task anchors for 5.5(a) (r6, retained).** The following eight query intents and expected evidence are mandatory in the 20-query manifest; freeze exact wording, eligible memory packet and source hashes before scoring. Their gold evidence is evaluator-only. The other 12 queries and all 5 continuations must be fully specified in the freeze bundle as in r5. Each task must retrieve the recorded decision **and its boundary**, not merely mention a repository. Decision-index paths below identify the retained decision lineage, not new installations; their line numbers refer to the input checkout at `75e30ea4` (r6 §14).

| ID / query intent | Expected evidence and semantic success | Frozen source locations |
|---|---|---|
| RM01 — What changed the SEC access decision? | Distinguish the initial native 403/refusal from the later tested-archive access resolution; retain the failed receipt rather than rewriting it as a success. | `catalogs/us-equities/decision-index.json:6352–6355` (EdgarTools bounded adoption); `blueprints/us-equities/catalyst-provenance/README.md:3–14,67–72` |
| RM02 — May the parsed real 8-K be used at a historical trading cutoff? | Recover the pinned real fixture and its missing acceptance metadata; explain its quarantine and distinguish native parsing/byte reduction from historical availability. | `catalogs/us-equities/decision-index.json:6330–6333`; `blueprints/us-equities/catalyst-provenance/README.md:16–23,108–114` |
| RM03 — What did catalyst dataset acceptance actually cover? | Recover 371 memberships / 360 accessions, five acquired headers, 366 unfetched rows and nine header item links; distinguish observed metadata from verified catalysts and a historically available universe. | `catalogs/us-equities/decision-index.json:6330–6333`; `blueprints/us-equities/data-readiness/README.md:12–15,38–46` |
| RM04 — Is the AAPL split-basis change an investment loss or engine acceptance? | Recover 499.23 → 124.8075 as a basis change, the 25-session factor/map scope, and the failed native test-host attempt with zero NUnit cases. Do not turn normalization into return/P&L or a passing upstream suite. | `catalogs/us-equities/decision-index.json:17233–17236`; `blueprints/us-equities/data-readiness/README.md:14–20,43–46` |
| RM05 — Can an FB/META `asof` query and today's asset UUID establish historical membership? | Recall the selected bounded Alpaca identity probe; distinguish request symbol mapping, current asset identity and observation availability from historical universe membership and original publication/revision times. | `catalogs/us-equities/decision-index.json:1592–1595`; `blueprints/us-equities/identity-readiness/README.md:17–41` |
| RM06 — How was the zero-volume META case continued? | Recall the original rejection and the decision to fetch only the saved continuation; keep source zeros plus a separate quarantine. All four chains completed; that is neither ten independent sessions nor an atomic revision snapshot. The task recalls the recorded action, not a new authenticated request. | `catalogs/us-equities/decision-index.json:1592–1595`; `blueprints/us-equities/identity-readiness/README.md:43–56,78–98` |
| RM07 — Can the 2021 segment be called an untouched holdout again? | Recall that the chronological control's reserved segment has been inspected, with 20 development folds and 21 frozen selections; keep unselected alternatives visible and prohibit retuning on their better outcomes. | `catalogs/us-equities/decision-index.json:19176` (skfolio record); `blueprints/us-equities/simulation-research/README.md:20–24,38–51` |
| RM08 — Do the SPY/QQQ/IWM results justify historical +200% mover research or engine P&L claims? | Retrieve the curated-control scope, lack of all-equities/delisted/mover/catalyst-arrival reconstruction and distinction between raw-price labels and engine accounting; identify the still-open historical-universe/publication/revision gate. | `catalogs/us-equities/decision-index.json:17248,19176`; `blueprints/us-equities/simulation-research/README.md:20–30,47–51`; `blueprints/us-equities/identity-readiness/README.md:114–120` |

Use GPT-6 Astra max with the same frozen answerer/context policy for all 25 diagnostic tasks; publish their total and eight-task research-memory success counts. **There is no minus-one floor on these diagnostics.** Missing diagnostic evidence is labelled pending for that diagnostic and cannot substitute for main usefulness. Extraction and other system roles use the separately frozen 2.1 matrix. Without the main 5.5 test, the result is a retrieval/lifecycle comparison or an explicitly unqualified 7.6 fallback, not accepted positive long-workflow usefulness.

## 6. Statistics (frozen before any confirmatory run)

- **Sample commitment (r6, retained):** plan all 470 full-track questions, all six types and all **452** canonical clusters; the full official population is **419 questions / 401 clusters**, secondary. If the development projection exceeds the **96 h per-host window**, the only permitted reduction is B:G's **prospective stratified subset**, sized and frozen with the power calculation below under 5.2 **before any confirmatory result on either host**. Freeze its question and cluster counts rather than continuing to quote full-population counts for a subset; its official-track intersection stays secondary. No adaptive subsampling, retrospective cost-driven truncation or early success stopping is authorized. Five seeds improve within-question averaging for stochastic components; they do not create 2,350 independent questions. Source-reviewed deterministic arms are ingested once and counted once.
- **Frozen before the first confirmatory result:**
  - the question-to-cluster manifest (sha256), built by 4.1's canonical `(role, content)` rule (452 full-track and 401 official-track clusters for full coverage; prospectively recomputed counts if 5.2 selects a subset);
  - seed aggregation: the five paired seeds (20260927–20260931) are averaged within each question for stochastic components; a deterministic arm supplies one source-reviewed result without multiplying ingestion or usage;
  - question-weighted differences;
  - the RNG (NumPy `PCG64`, bootstrap seed 20260927);
  - 10,000 cluster resamples. Each resample keeps every question of each drawn cluster.
- **Upstream statistics binding:** pin **scipy==1.18.1** (`e4e854eaa8f18d807cd3496028e257e36caa93cc`) and **statsmodels==0.15.0** (`278ff9950636cdd4939b4055e339a8e681d79cab`), plus the exact NumPy version in the analysis lock (2.x; v2.5.3 was the current release on 2026-09-30).
- **Pairwise family (r7).** For every unordered pair (i, j) of planned family systems on a host, the per-cluster arrays are `s`, the sum of seed-averaged question differences q_i − q_j within the cluster, and `n`, the cluster's question count:

```python
res = scipy.stats.bootstrap(
    (s, n),
    lambda s, n, axis=-1: s.sum(axis) / n.sum(axis),
    paired=True,
    vectorized=True,
    n_resamples=10000,
    method="percentile",
    confidence_level=0.95,
    alternative="two-sided",
    rng=numpy.random.Generator(numpy.random.PCG64(20260927)),
)
d = res.bootstrap_distribution
p = min(1.0, 2 * min(numpy.mean(d <= 0), numpy.mean(d >= 0)))
```

  - A fresh generator with the same seed for each pair draws identical cluster indices for every pair: a joint bootstrap over the shared clusters.
  - Holm uses **`statsmodels.stats.multitest.multipletests(p, alpha=0.05, method='holm')`** over the frozen vector of all **m = k(k−1)/2** planned pairs, with **p = 1.0 for every pair involving a missing or ineligible system**, so m never shrinks; the placeholders are not imputed outcomes ([statsmodels v0.15.0](https://github.com/statsmodels/statsmodels/blob/v0.15.0/statsmodels/stats/multitest.py#L233-L247)).
  - With the eight primaries, **m = 28**. A reserve admitted before confirmatory execution raises k, which is frozen before execution.
  - A rejected pair is decided in the direction of the observed difference.
  - Two-sided 95% percentile intervals per pair are reported and decide nothing. Explicit `n_resamples=10000` overrides SciPy's 9999 default ([SciPy signature](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_resampling.py#L300-L303), [interval calculation](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_resampling.py#L661-L683)).
  - The r6 cluster sign-flip `scipy.stats.permutation_test(permutation_type="samples")` stays as a diagnostic that decides nothing, with its RNG and resamples frozen and whole cluster sums sign-flipped at fixed question counts.
- **Power (r6's report, retargeted in r7).** Report, from the frozen analysis code, the achieved power to Holm-separate a true difference of 0.05 and of 0.02 at the frozen m and cluster structure, over discordance 0.10–0.30, with Monte Carlo uncertainty and the seed-dependence assumption stated.
  - An illustrative normal approximation (470 paired questions, two-sided) for a difference of 0.05 gives power 0.64, 0.25 and 0.13 at discordance 0.10, 0.20 and 0.30 at the strictest Holm step (α = 0.05/28), and 0.93, 0.68 and 0.51 at the last step (α = 0.05).
  - For a difference of 0.02 it is at most 0.04 at the strictest step and 0.28 at the last.
  - Differences inside the 0.02 band will therefore rarely be separated, and even 0.05 differences may remain not separated. 7.2 therefore decides on the point estimate and uses the tests to label the result and to bar significantly worse systems from the tie-break.
  - Power is information, not a gate or a margin change. A prospective subset (5.2) must report this calculation for its frozen size before any result.
- **LongMemEval-V2 resampling unit and minimum (round-3 item 2).** Build an outcome-independent graph on **all questions in the downloaded tier's haystack mapping**, before subset selection. Connect two questions when their haystacks share a trajectory ID or a canonical trajectory-content hash (canonical JSON with sorted keys, excluding only the trajectory `id`), or when they use the same native shared memory instance. The **connected components** are the resampling clusters; shared trajectories/memory never cross independent clusters, even through an unselected bridging question. Freeze trajectory/file hashes, the full question→component manifest and the component IDs represented in the selected subset; all five paired replications and all arms/control for a question stay in its component. The preflight verifies the mapping, referenced trajectory existence/content hashes and counts against the actual downloaded `haystacks/lme_v2_small.json` and `trajectories.jsonl`, then recomputes represented counts for any selected subset. The native loader supplies question→trajectory lists (`data/public_data.py:51-64,110-124`); the harness builds one shared memory for a common haystack (`evaluation/harness.py:1169-1170,1180-1213`), and the leaderboard requires the same web/enterprise haystacks across operating points (`leaderboard/README.md:149-150`). **Minimum: 20 independent components in the selected sample.** This is a preregistered design safeguard, not an upstream requirement or a guarantee of power/coverage. With one shared haystack per domain the design may yield only about two components (or fewer if connected): **the main-usefulness lane stays pending**, and cannot establish that no system qualifies or authorize a 7.6 fallback. Question count, repeated seeds or subset selection do not increase the cluster count; no question-level alternative test or outcome-based regrouping is allowed. No downloaded-file count is claimed by this source-only repair.
- **Separate main-usefulness family (repair rounds 2–3).** LongMemEval-V2 uses the same paired seed aggregation, cluster-bootstrap test and Holm α=0.05 **only after the minimum above passes**, with its own fixed haystack-component/sample manifest. Each draw retains every selected question and all replications of the drawn component; fresh same-seed generators give joint indices across pairs, with the `s`/`n` question weighting above. Include every unordered pair of k planned memory systems **and** each system versus no retrieval: **m_U = k(k+1)/2** (36 with eight primaries). Missing/ineligible-arm pairs retain p=1; baseline comparisons are included even though baseline is outside the retrieval family. If the minimum is not met, the baseline exceeds 5% final failures or required comparison coverage is missing, the family is **pending**, using p=1 placeholders, not a negative usefulness conclusion. The best set is all exact point-estimate maximizers among operationally eligible memory systems with complete usefulness outcomes, never the no-retrieval control or an ineligible higher scorer. A pass requires an observed positive difference and Holm rejection versus no retrieval, and no Holm rejection in any best member's favour. Freeze the family before results; publish power at the verified cluster count for superiority and best comparisons. Low power with otherwise complete valid evidence may leave every system unqualified and invoke 7.6; insufficient clusters/coverage cannot. Neither case authorizes relaxing α or choosing a post-result subset.
- **Outside the retrieval and usefulness families:** other controls/diagnostics (3.4), development checks, the official track, `ndcg_any@5`, 5.5(a)/(b), secondary MemoryAgentBench TTL/CR and S8's separate non-inferiority check (8.4).
- **Missing results:** a missing system or lane result is `pending` and is not imputed.
- **Governing statistics (r4, retained):** these statistics govern S3 on both hosts. The A-protocol's family α values (0.0333, 0.0167), its +5 pp/−2 pp rule and its one-look-per-family rule do not transfer (r6 §12, Appendix A).

## 7. Symmetric merit rule (per host)

### 7.1 Eligibility, required of every system alike

1. passes the current maintenance gate for every selected repository and the dependency SBOM/OSV requirements (section 1), source-backed deployment, network and GPT-6 wire/effort acceptance (2.2, 3.5, 4.4, 4.6);
2. deploys on that host and passes every item of the 5.4 lifecycle/coding-client acceptance;
3. warm p95 latency (5.3) at most 1.0 s, with the complete serving configuration co-resident (8.2);
4. has complete primary retrieval results and failure accounting (4.5); an exceeded failure threshold or missing required observer/result leaves it pending;
5. **main usefulness:** passes 5.5's LongMemEval-V2 superiority-to-no-retrieval and not-worse-than-eligible-best rule, with complete paired outcomes, at least 20 verified haystack components, baseline final failures at most 5% and the separate Holm family (section 6);
6. **cost readiness:** total C is available wherever the cost tie-break can change the decision; otherwise 7.3 is unresolved. Unpriced routes are handled only by 5.2's one policy and do not falsely disqualify a lone primary leader;
7. **short-code do-no-harm, separate from usefulness:** if S8 has been frozen/run, each client's resolve rate is non-inferior within its prospectively frozen margin, with token overhead reported (8.4). S8 cannot exclude a system **on usefulness** and its current pending status does not block a LongMemEval-V2-based host decision. Until S8 is qualified, report coding non-inferiority as pending, never passed; a later observed hard do-no-harm failure blocks cutover/retention in that coding scope.

Items 1–4 are operational hard gates for both qualified selection and the 7.6 fallback; item 7 is a hard do-no-harm requirement in its frozen coding scope. Item 5 is statistical usefulness qualification. The no-winner fallback can select an operationally eligible system with complete evidence that fails to establish usefulness; it must say so. All-zero main-usefulness results cannot pass item 5. The 25 diagnostics and short-code tasks supply no replacement floor.

**Executable usefulness examples (synthetic decisions, not bootstrap/evaluator acceptance).** `losses` contains Holm-rejected pairs `(loser, winner)` from the frozen family; scores are exact native-correctness aggregates. `eligible` is the independently established operationally eligible memory set with complete usefulness observations; it excludes the control. The analysis uses this rule after native statistics. Missing expected comparison/family observations use `complete=False`; a synthetic cluster count here does not verify downloaded data.

```python
from fractions import Fraction as F

def usefulness_status(system, scores, losses, *, eligible, cluster_count,
                      complete=True, failure_rate=F(0), baseline_failure_rate=F(0)):
    if (not complete or cluster_count < 20 or failure_rate > F(5, 100)
            or baseline_failure_rate > F(5, 100)):
        return "pending"
    if system not in eligible or system == "no_retrieval":
        return "ineligible"
    if "no_retrieval" not in scores or any(i not in scores for i in eligible):
        return "pending"
    memory = {i: q for i, q in scores.items() if i in eligible and i != "no_retrieval"}
    top = max(memory.values())
    best = {i for i, q in memory.items() if q == top}
    superior = (scores[system] > scores["no_retrieval"]
                and ("no_retrieval", system) in losses)
    not_worse = all((system, leader) not in losses for leader in best)
    return "qualified" if superior and not_worse else "unqualified"

zero = {"A": F(0), "B": F(0), "no_retrieval": F(0)}
ready = {"eligible": {"A", "B"}, "cluster_count": 20}
assert usefulness_status("A", zero, set(), **ready) == "unqualified"
scores = {"A": F(8, 10), "B": F(6, 10), "no_retrieval": F(5, 10)}
losses = {("no_retrieval", "A"), ("no_retrieval", "B"), ("B", "A")}
assert usefulness_status("A", scores, losses, **ready) == "qualified"
assert usefulness_status("B", scores, losses, **ready) == "unqualified"
assert usefulness_status("A", scores, set(), **ready) == "unqualified"  # superiority unproved
tied = {"A": F(8, 10), "B": F(8, 10), "C": F(7, 10), "no_retrieval": F(5, 10)}
tied_ready = {"eligible": {"A", "B", "C"}, "cluster_count": 20}
assert usefulness_status("C", tied, {("no_retrieval", "C"), ("C", "B")}, **tied_ready) == "unqualified"
assert usefulness_status("C", tied, {("no_retrieval", "C")}, **tied_ready) == "qualified"
ineligible_high = dict(scores, X=F(9, 10))
assert usefulness_status("A", ineligible_high, losses | {("A", "X")}, **ready) == "qualified"
assert usefulness_status("X", ineligible_high, losses, **ready) == "ineligible"
assert usefulness_status("A", scores, losses, failure_rate=F(5, 100), **ready) == "qualified"
assert usefulness_status("A", scores, losses, failure_rate=F(51, 1000), **ready) == "pending"
assert usefulness_status("A", scores, losses, baseline_failure_rate=F(5, 100), **ready) == "qualified"
for system in ready["eligible"]:
    assert usefulness_status(system, scores, losses, baseline_failure_rate=F(51, 1000), **ready) == "pending"
assert usefulness_status("A", scores, losses, eligible={"A", "B"}, cluster_count=19) == "pending"
assert usefulness_status("A", scores, losses, eligible={"A", "B"}, cluster_count=2) == "pending"
assert usefulness_status("A", scores, losses, complete=False, **ready) == "pending"
print("7.1 usefulness examples: all assertions hold")
```

### 7.2 Winner and tie-break set

Repaired in round 1 (finding F3): the maximizer set and the quantifier are explicit.
- Let q_i be each eligible system's full-track `recall_all@5` (4.2). Each q_i is computed exactly, as a rational number; a seed-averaged question score is a multiple of 1/5, so every comparison below is exact.
- Let q* be the largest q_i. The **maximizer set** is M = {i : q_i = q*}, and every member of M is a leader.
- The **tie-break set** B contains every member of M and each other eligible system j that meets both conditions:
  - q_j ≥ q* − **0.02**, the preregistered practical-equivalence band;
  - for **every** leader m in M, Holm does not reject the pair (j, m) in m's favour (section 6). A significant loss to any one leader excludes j.
- A system significantly worse than a leader is therefore never in B, however small the difference. A system that no leader is separated from, but that lies more than 0.02 below q*, is outside B: the leaders win over it on the point estimate, and the report states "not separated from" for each such pair.
- If B has one member, it is selected. It is labelled **best** if Holm separates it from every other eligible system, and otherwise **leader, not separated from** the listed systems.
- If B has several members, whether several leaders or leaders plus admitted systems, 7.3 applies, then 7.4.
- The frozen code at the end of 7.3 states this rule exactly, with examples that include tied leaders whose pairwise decisions against a third system conflict.

### 7.3 Tie-break 1: token and cost efficiency

Repaired in round 1 (finding F4): the rule handles several equal minima, zero included.
- Within B, let c_min be the lowest decision cost C (5.2), which is gross, nonnegative and exact.
- The **cost-tied set** A contains each member j with C_j = c_min or 0.80 × C_j < c_min, where 0.80 is the cost ratio r6 froze for its cost route. A member whose C exceeds c_min leaves A when c_min ≤ **0.80 ×** its C; every member at c_min stays.
- If A has one member, it is selected. Otherwise every member of A goes to 7.4; this covers several equal minimum costs, zero included.
- A member whose C is exactly c_min / 0.80 leaves A, matching r6's selection condition c_min ≤ 0.80 × C. r7's wording had also kept such a member tied (repair clarification).
- If an unknown C, or an unavailable price, could change the outcome, selection is unresolved.

**Frozen rule and examples for 7.2 and 7.3 (repair round 1).** This code is part of the preregistration. The analysis applies exactly these two functions, and the examples must pass under the frozen Python before freeze. `worse` holds the pairs that section 6's Holm step rejects, oriented by the observed difference.

```python
# S3 r7 sections 7.2-7.3: frozen rule and examples (r7 repair round 1, F3 and F4)
from fractions import Fraction as F

BAND = F(2, 100)    # 7.2 practical-equivalence band
RATIO = F(80, 100)  # 7.3 cost ratio (r6)


def tie_break_set(q, worse):
    """q: {system: exact full-track recall_all@5}. worse: the pairs (i, m) that
    Holm rejects with m ahead of i (section 6); a pair with a zero observed
    difference never enters it. Returns the maximizer set M and the set B."""
    top = max(q.values())
    M = {i for i in q if q[i] == top}
    B = M | {j for j in q if j not in M and q[j] >= top - BAND
             and all((j, m) not in worse for m in M)}
    return M, B


def cost_tied(C):
    """C: {member of B: exact gross decision cost, >= 0}. A single member is
    selected by 7.3; several members go to 7.4."""
    c_min = min(C.values())
    return {j for j in C if C[j] == c_min or RATIO * C[j] < c_min}


n = F(470)  # full-track questions; seed averages are multiples of 1/5

# (1) One maximizer; the runner-up is 20/470 below it, outside the band.
assert tie_break_set({"A": 300 / n, "B": 280 / n}, set()) == ({"A"}, {"A"})
# (2) Tied leaders with conflicting pairwise decisions. C is inside the band
# but Holm separates it from co-leader A (not from B), so C is out. D is
# separated from neither co-leader, so D is in.
q = {"A": 300 / n, "B": 300 / n, "C": 295 / n, "D": F(1453, 5) / n}
assert tie_break_set(q, {("C", "A")}) == ({"A", "B"}, {"A", "B", "D"})
assert tie_break_set(q, set()) == ({"A", "B"}, {"A", "B", "C", "D"})
# (3) The band is compared exactly: 271.2 of 470 is exactly 0.02 below 280.6
# of 470 and is in (binary floating point would put it out); one fifth of a
# question less is out.
assert tie_break_set({"A": F(1403, 5) / n, "E": F(1356, 5) / n}, set())[1] == {"A", "E"}
assert tie_break_set({"A": F(1403, 5) / n, "E": F(1355, 5) / n}, set())[1] == {"A"}
# (4) Several equal minimum costs, zero included: every minimum stays tied.
assert cost_tied({"A": F(10), "B": F(10), "D": F(13)}) == {"A", "B"}
assert cost_tied({"A": F(0), "B": F(0), "D": F(5)}) == {"A", "B"}
assert cost_tied({"A": F(0), "B": F(3)}) == {"A"}
# (5) A unique minimum is selected when it costs at most 0.80 x every other
# member, r6's boundary included; otherwise the members above stay tied.
assert cost_tied({"A": F(8), "B": F(10)}) == {"A"}
assert cost_tied({"A": F(8), "B": F("9.9")}) == {"A", "B"}
# (6) Gross costs, never control-subtracted ones (5.2): 120 and 130 stay tied,
# although 20 and 30 left after subtracting a common 100 would not.
assert cost_tied({"A": F(120), "B": F(130)}) == {"A", "B"}
assert cost_tied({"A": F(20), "B": F(30)}) == {"A"}
print("7.2-7.3 frozen examples: all assertions hold")
```

### 7.4 Tie-break 2: repo-quality score

For each remaining member's repository, scored at the freeze gate run:

RQ = (Σ_{c ∈ S} w_c · s_c + 2.5 · R + 2.5 · K) / (Σ_{c ∈ S} w_c + 5)

- **s_c** ∈ [0, 10] is the OpenSSF Scorecard score of check c, over the seven checks Maintained, CI-Tests, Code-Review, Branch-Protection, Signed-Releases, Vulnerabilities and Dangerous-Workflow. **S** is the subset with a conclusive score, because Scorecard's own aggregate skips inconclusive (−1) checks ([`pkg/scorecard/scorecard_result.go:83-120`](https://github.com/ossf/scorecard/blob/c395761df6afe1a69e476bc60a013a94bcbc153f/pkg/scorecard/scorecard_result.go#L83-L120) at v5.5.0).
- **w_c** is Scorecard's risk weight ([`README.md:605-613`](https://github.com/ossf/scorecard/blob/c395761df6afe1a69e476bc60a013a94bcbc153f/README.md#L605-L613); `scorecard_result.go:86`), with each check's risk from `docs/checks/internal/checks.yaml:19,141,227,287,655,747,772`:
  - Dangerous-Workflow is Critical, weight 10;
  - Maintained, Code-Review, Branch-Protection, Signed-Releases and Vulnerabilities are High, weight 7.5;
  - CI-Tests is Low, weight 2.5.

  The first term is therefore Scorecard's own aggregate over these seven checks.
- **R**, release cadence: R = 10 × min(1, n90 / 3). n90 counts GitHub releases that are neither drafts nor prereleases, published in the 90 days before the gate run; for a project that publishes no releases, it counts version tags. One release a month on average over Scorecard's 90-day window earns full marks.
- **K**, CI on the pinned release commit (repaired in round 1, finding F6). At the freeze gate run, capture the commit's complete check and status set:

  ```sh
  gh api --paginate "repos/OWNER/REPO/commits/SHA/check-runs?filter=latest&per_page=100"
  gh api --paginate "repos/OWNER/REPO/commits/SHA/status?per_page=100"
  gh api "repos/OWNER/REPO/commits/SHA/check-suites?per_page=1" --jq .total_count
  ```

  GitHub's REST description ([`rest-api-description@af2c1025`](https://github.com/github/rest-api-description/blob/af2c102501766f14fe4edc688e449427a971e66a/descriptions/api.github.com/api.github.com.json), `api.github.com.json`) caps `per_page` at 100 and limits the check-run listing to a ref's 1000 most recent check suites (`:55478-55482`); the check-suite listing reports a `total_count` (`:55584`). The capture is complete when the retrieved check runs and status contexts each equal their reported `total_count` and the ref has at most 1000 check suites. The complete set is frozen, with its sha256, as the relevant set.
  - K = 10 only if the set is complete and non-empty, every check run has status `completed` (none `queued`, `in_progress`, `waiting`, `requested` or `pending`; `:145900-145911`) and conclusion `success`, `neutral` or `skipped` (`:145913-145925`), and every status context's latest state is `success`. A commit with check runs but no status context meets the last condition; the combined `state` is not used alone, because GitHub reports it as `pending` when there are no statuses (`:55667`).
  - Otherwise K = 0, with the reason recorded: missing (no check run and no status), incomplete (an unfinished run or a `pending` context), truncated (a retrieved count below `total_count`, or more than 1000 check suites) or failed (any other conclusion or state, such as `failure`, `error`, `cancelled`, `timed_out` or `action_required`). An API error or rate-limit refusal is retried after the reported reset, and the final response is the one recorded.
- R and K take the Low-risk weight 2.5, the same as CI-Tests. Their definitions and weights are coordinator heuristics, not Scorecard's measures, and the user may change them before freeze.
- **Scorecard runs.**
  - The v5.5.0 CLI, `scorecard --repo=github.com/OWNER/REPO --checks=Maintained,CI-Tests,Code-Review,Branch-Protection,Signed-Releases,Vulnerabilities,Dangerous-Workflow --format=json`, runs against the default branch.
  - It runs again with `--commit=<pinned SHA>` ([`options/flags.go:35-36,124-127`](https://github.com/ossf/scorecard/blob/c395761df6afe1a69e476bc60a013a94bcbc153f/options/flags.go#L124-L127)) for Vulnerabilities and Dangerous-Workflow. A check that cannot evaluate a non-HEAD commit keeps its default-branch result, recorded as such.
  - The REST API at `api.scorecard.dev` is only a cross-check.
  - The GitHub token is injected per `docs/secret-storage.md` and never recorded.
- The highest RQ, rounded to one decimal, is selected. An exact tie gives joint winners, and the host decision goes to the user.
- Stars, forks, downloads and popularity never count. Scorecard describes aggregate scores as telling "nothing about what individual behaviors a repository is or is not doing" (`README.md:109-112`), which is why RQ only breaks ties.

### 7.5 Silent-fallback LLM stages (r6's C4′ preflight, generalized)

- **Scope.** This applies to every system whose selected configuration has an LLM stage that can silently fall back. ai-memory's reranker is an example: "A timeout, provider error, or incomplete/invalid score set preserves the normal order", and queries over its four-call cap "keep their local ranking without waiting" (`docs/llm-providers.md:338-341` at `a0ca8d1a`).
- **Preflight: two separate development measurements under the frozen envelope** (repaired in round 1, finding F5):
  1. *Fallback rate under confirmatory load.* The system's development retrieval queries (4.1's development split) are dispatched as the confirmatory run will dispatch them: through the frozen dispatch wrapper (4.3), with K in-flight GPT-6 calls per host (5.2) and the same query concurrency per instance. The denominator is every recall request for which the selected stage is configured to run. The numerator is the requests on which the stage fell back, whether through timeout, provider error, invalid output or saturation such as ai-memory's four-call cap ([`docs/llm-providers.md:338-341`](https://github.com/akitaonrails/ai-memory/blob/a0ca8d1a5fbd5920799411fa891fe6d49c90efc1/docs/llm-providers.md#L338-L341)). **An observed stage outcome, not the presence/absence of a completed gateway call, decides that numerator** (N1). Require a per-request `accepted` or `fallback:<reason>` outcome from a supported native signal or a source-backed provider-boundary observer of the actual consumed stage output and validation result. A source-defined `not_applicable` precondition, such as fewer than two candidates, is separately counted and excluded from the denominator; saturation remains included. Unknown/unmatched outcomes are `unobserved`, never accepted or zero fallbacks, and leave the arm pending. Record gateway transport status separately: an HTTP 200 and completed `call_logs` row can still precede invalid-output rejection and preservation of the original ranking.
  2. *Gated warm latency at concurrency 1.* 5.3's frozen warm schedule (200 requests, concurrency 1, a 20-request warm-up discarded, no other arm's call in flight), with the stage on. Its p95 is the development estimate for 7.1 item 3. Fallbacks seen here are reported but do not enter the 5% rate.
- **Stage disabling** follows measurement 1 alone: development fallbacks above 5% disable the stage before any confirmatory run by dated amendment, or the arm is `pending`. Measurement 2 disables nothing; the confirmatory 5.3 run decides latency eligibility.
- **Confirmatory fallbacks above 5%**, counted as in measurement 1 over the system's confirmatory recall requests: that system's comparisons are inconclusive, and host selection is unresolved if they could change the winner.
- No configuration may switch after confirmatory scores.

**Observable validation and fault control (repair round 2, N1).** ai-memory supplies native signals for saturation, provider error, timeout and incomplete/invalid scores (`akitaonrails/ai-memory@a0ca8d1a:crates/ai-memory-mcp/src/server.rs:2114`, `:2133`, `:2176`). Its acceptance predicate requires exactly one finite score in [0,1] for each candidate ID, with no extra/missing/duplicate ID (`server.rs:2157`). Freeze the native logging level and query correlation needed to attribute these events; a boundary observer must capture the actual candidate IDs, canonical scores consumed by that stage and resulting acceptance/ranking, validating the same predicate at the pin. Unchanged order alone is not a fallback signal: valid scores can preserve it. A stage without a trustworthy native accepted-output signal or this complete boundary observation stays pending; absence of a warning is not an accepted-output signal.

Before either development preflight can pass, inject incomplete, duplicate, unknown-ID, nonfinite and out-of-range scores, plus timeout, provider error and saturation, through the actual selected query path. **The invalid-score response must complete successfully at the gateway**; retain the completed transport observation and then observe a native invalid-score fallback, preserved original ranking, a fallback numerator increment and complete outcome coverage. Run a valid-score control too, including one that preserves the original order. A proxy that sees only transport success must fail this control. Upstream's `reranker_degrades_on_partial_malformed_error_and_timeout` (`server.rs:6004`) is a source/test reference, not a run made here; the native gateway fault control remains required. The following source-backed synthetic example verifies the repaired discrete observation rule without claiming a service/gateway run:

```python
import math

def observed_stage_outcome(candidate_ids, consumed_scores, *, gateway_completed):
    # gateway_completed is transport evidence only; the stage predicate decides.
    # None means the consumed output/outcome could not be observed.
    if consumed_scores is None:
        return "pending"
    expected = set(candidate_ids)
    seen = set()
    valid = len(consumed_scores) == len(candidate_ids)
    for candidate_id, relevance in consumed_scores:
        valid &= (candidate_id in expected and candidate_id not in seen
                  and math.isfinite(relevance) and 0 <= relevance <= 1)
        seen.add(candidate_id)
    return "accepted" if valid and seen == expected else "fallback:invalid_output"

ids = ["opaque-a", "opaque-b"]
invalid = [("opaque-a", 0.9)]  # successful transport, incomplete stage output
assert observed_stage_outcome(ids, invalid, gateway_completed=True) == "fallback:invalid_output"
assert observed_stage_outcome(ids, [(ids[0], 0.9), (ids[1], 0.8)], gateway_completed=True) == "accepted"
for scores in [[(ids[0], 0.9), (ids[0], 0.8)], [(ids[0], 0.9), ("unknown", 0.8)],
               [(ids[0], float("nan")), (ids[1], 0.8)], [(ids[0], 1.1), (ids[1], 0.8)]]:
    assert observed_stage_outcome(ids, scores, gateway_completed=True) == "fallback:invalid_output"
assert observed_stage_outcome(ids, None, gateway_completed=True) == "pending"
assert observed_stage_outcome(ids, None, gateway_completed=False) == "pending"
outcomes = [observed_stage_outcome(ids, invalid, gateway_completed=True), "accepted"]
assert sum(o.startswith("fallback:") for o in outcomes) / len(outcomes) == 0.5
print("7.5 successful-transport invalid-score example: fallback observed; unknown is pending")
```

### 7.6 No qualified winner: best-scoring eligible-system fallback

**ACCEPTED 2026-09-30: "Best-scoring eligible system."** If no system qualifies under 7.1, the host deploys the operationally eligible system with the highest observed primary `recall_all@5`, labelled **fallback; usefulness not qualified**, with the failed/inconclusive statistical qualification reported. The incumbent is one contender and is never kept by default.

**Operationally eligible** means the system passes the current selected-repository maintenance gate and dependency SBOM/OSV requirements, has a source-backed deployment that actually starts and works on that host, passes all required lifecycle, wire/effort, network, latency and observer hard gates, and has **no failed hard gate** (7.1 items 1–4 and any already-frozen coding do-no-harm requirement). A missing required deployment/hard-gate observation leaves it pending and excludes it from the currently selectable set, **but does not permit ignoring it if its eventual eligibility could change the result**. Lack of significant main-usefulness superiority is not an operational hard-gate failure. Before declaring that no system qualifies, main-usefulness outcomes/comparisons must be complete, the 20-cluster minimum must pass and baseline final failures must be at most 5%; missing or invalid evidence is pending, not failed qualification.

Apply this definition symmetrically to every system, ai-memory included. Require complete comparable primary results for all operationally eligible contenders that could change the choice; select the exact primary maximizer(s), with **no lower-score equivalence-band promotion** in this fallback. Exact primary ties use 7.3, then 7.4, on those maximizers; an unavailable cost capable of changing that tie remains unresolved under 5.2. A cold-copy cutover and rollback receipt is still required. If there are **zero operationally eligible systems**, deployment is unresolved with each hard-gate reason listed; do not deploy a failed/pending arm or call retention of the current installation a qualified/fallback decision. This empty-set limit does not reinstate an incumbent default.

**Pending-contender guard (round-3 item 6).** The fallback stays **unresolved** while a planned pending contender could qualify, exceed the best currently eligible primary score, or tie it and change 7.3/7.4. This includes missing 7.5 stage-outcome coverage and section 9 host evidence. An unknown/incomplete primary score is potentially higher; only a complete comparable score strictly below the eligible maximum, with no remaining qualification uncertainty, cannot change this fallback. A demonstrated failed hard gate excludes a contender; an unobserved gate does not. Do not shrink the choice to whichever arms finished first.

```python
from fractions import Fraction as F

def fallback_status(scores, eligible, pending, *, usefulness_complete=True,
                    any_qualified=False, pending_qualification=False):
    # scores contains complete primary results only, never partial estimates.
    if not usefulness_complete or pending_qualification:
        return "pending", set()
    if any_qualified:
        return "qualified_selection", set()
    if not eligible:
        return "unresolved", set()
    if any(i not in scores for i in eligible):
        return "pending", set()
    top = max(scores[i] for i in eligible)
    if any(i not in scores or scores[i] >= top for i in pending):
        return "pending", set()
    return "fallback", {i for i in eligible if scores[i] == top}

scores = {"A": F(8, 10), "B": F(6, 10), "P": F(9, 10)}
assert fallback_status(scores, {"A", "B"}, {"P"}) == ("pending", set())
assert fallback_status({**scores, "P": F(8, 10)}, {"A", "B"}, {"P"}) == ("pending", set())
assert fallback_status(scores, {"A", "B"}, {"unknown"}) == ("pending", set())
assert fallback_status({**scores, "P": F(7, 10)}, {"A", "B"}, {"P"}) == ("fallback", {"A"})
assert fallback_status({**scores, "P": F(7, 10)}, {"A", "B"}, {"P"},
                       pending_qualification=True) == ("pending", set())
assert fallback_status(scores, {"A", "B"}, set()) == ("fallback", {"A"})  # P failed a hard gate
assert fallback_status(scores, {"A", "B"}, set(), usefulness_complete=False) == ("pending", set())
assert fallback_status(scores, set(), set()) == ("unresolved", set())
print("7.6 pending-contender examples: all assertions hold")
```

## 8. RAG and retrieval-model selection (r7)

There is no incumbent default here either: qmd, the host's deployed embedders and rerankers, and ai-memory's MiniLM compete on the same terms as every challenger.

### 8.1 Task sets, frozen before any result

- **Source.** MTEB 2.21.10 (`7fac921e8672cfb6799d7c6a9a542832bc10cbb6`) defines ten retrieval tasks in `MTEB(eng, v2)` ([`mteb/benchmarks/benchmarks/benchmarks.py:21-84`](https://github.com/embeddings-benchmark/mteb/blob/7fac921e8672cfb6799d7c6a9a542832bc10cbb6/mteb/benchmarks/benchmarks/benchmarks.py#L21-L84)). Their corpora are disjoint from the memory data.
- **Partition rule.** To keep embedder selection and RAG evaluation apart, the tasks are split by corpus size alone. Corpus size is outcome-blind, and it also bounds ingest cost for systems that extract with an LLM.
- **Sizes.** They come from `mteb/descriptive_stats/Retrieval/<task>.json` at that commit. The three HardNegatives tasks report only `num_samples`, which counts documents plus queries.
- **E_doc, document-RAG evaluation, the five smallest corpora:** ArguAna (8,674 documents), SCIDOCS (25,657), CQADupstackGamingRetrieval (45,301), CQADupstackUnixRetrieval (47,382) and ClimateFEVERHardNegatives (48,416 samples).
- **S_doc, document embedder and reranker selection:** FiQA2018 (57,638 documents), FEVERHardNegatives (164,698 samples), TRECCOVID (171,332 documents), HotpotQAHardNegatives (226,621 samples) and Touche2020Retrieval.v3 (303,732 documents).

### 8.2 Embedder and reranker selection

MTEB 2.21.10, run one model at a time on the workstation's RTX 4090 without stopping live services:
- **Memory role:** MTEB's LoCoMo task ([`mteb/tasks/retrieval/eng/lmeb_retrieval.py:996-1043`](https://github.com/embeddings-benchmark/mteb/blob/7fac921e8672cfb6799d7c6a9a542832bc10cbb6/mteb/tasks/retrieval/eng/lmeb_retrieval.py#L996-L1043); data `mteb/LoCoMo` at `02e2c3dea15d9fdfd1cd7a0f65f5f8ae2ed4c1ac`, cc-by-nc-4.0).
  - The selection metric stays r6's question-weighted supporting-evidence recall@5, frozen before the first check, not the task default `ndcg_at_10` (`:119-124`).
  - Rerankers use MTEB's two-stage procedure ([`docs/get_started/advanced_usage/two_stage_reranking.md`](https://github.com/embeddings-benchmark/mteb/blob/7fac921e8672cfb6799d7c6a9a542832bc10cbb6/docs/get_started/advanced_usage/two_stage_reranking.md)): stage-1 predictions, then `convert_to_reranking(top_k=100)`, then stage 2.
  - Freeze the corpus, native inference, pooling and prompt, dimensions, truncation, artifact revision and quantization, candidate depth and scoring before the check (r6).
- **Code role:** the `CoIR` benchmark's tasks in MTEB (`benchmarks.py:528-558`: AppsRetrieval, CodeFeedbackMT, CodeFeedbackST, CodeSearchNetCCRetrieval, CodeTransOceanContest, CodeTransOceanDL, CosQA, COIRCodeSearchNetRetrieval, StackOverflowQA and SyntheticText2SQL), scored by nDCG@10. These run as MTEB task data; no code from the stale `CoIR-team/coir` runs.
- **Document role:** S_doc (8.1), scored by nDCG@10.

**Candidates are current models only.** The challengers are r6's verified 2026-09-27 shortlist (r6 §14 E row; `inputs/sweep-20260927-mac/embed.md`, `rerank.md`): Nemotron-3-Embed-8B-BF16 and -1B-BF16, F2LLM-v2-4B and -0.6B, harrier-oss-v1-0.6b, MemReranker-4B, Qwen3-Reranker-0.6B and ettin-reranker-400m. Full revisions are expanded at freeze. The incumbents compete on the same tasks:

| Incumbent | Artifact and revision | Where it runs today |
|---|---|---|
| Nemotron-3-Embed-1B | `nvidia/Nemotron-3-Embed-1B-BF16` @ `c0c9fea93ea424587517f2c59e20db9f1d6bf615` | the workstation's vLLM embedder (`manifests/stack.json`) |
| embeddinggemma-300M | `ggml-org/embeddinggemma-300M-GGUF` @ `0f741b5a6585bd53aeb15cd1372c56f2a0f65e12` (base `google/embeddinggemma-300m` @ `57c266a740f537b4dc058e1b0cda161fd15afa75`, gated) | qmd's default embedder ([qmd v2.8.3 `README.md:560,729,1272`](https://github.com/tobi/qmd/blob/facd35e01359e59d938bc9418e93fb9318addee3/README.md#L560)) |
| qwen3-reranker-0.6b | `ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF` @ `a02f48bb4f057028298c21fa033da2b30d7742d5` (base `Qwen/Qwen3-Reranker-0.6B` @ `e61197ed45024b0ed8a2d74b80b4d909f1255473`) | qmd's default reranker (`README.md:561,730,1273`) |
| MiniLM | `sentence-transformers/all-MiniLM-L6-v2` @ `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | ai-memory's pinned baseline (`manifests/stack.json`) |

**VRAM budget.**
- On 2026-09-30, `nvidia-smi` showed 12,726 MiB free (time not recorded), then 12,005 of 24,564 MiB free at 03:13:24Z. Neither reproduces the brief's "about 13.7 GB".
- Each check runs within the free memory measured at its own start, less 1 GiB.
- **Co-residency (repair round 2, M7):** individual model checks do not establish that their selected combination serves the arms. Before selection/freeze, enumerate and measure feasible embedder+reranker combinations **together with every required local generative/shipped model**, native runtimes, buffers and the frozen concurrent serving schedule for each arm. The workstation constraint is **peak additional serving VRAM ≤ measured free VRAM − 1 GiB** (the recorded roughly 12 GB is historical, re-measured at qualification); Mac shared-memory/RSS is measured separately. Only a jointly feasible combination may serve every arm that needs it. If independent role leaders cannot co-reside, freeze a feasible jointly tested combination from the shortlist before confirmatory scores or leave the serving plan pending until a pre-approved GPU stop/restore window. Never qualify models one at a time and silently unload one during another arm's measured work. Record cold/warm transitions and all local serving costs; no live service is stopped by this repair.
- Nemotron-3-Embed-8B-BF16 needs about 16 GB for its BF16 weights alone (8 billion parameters × 2 bytes), so it does not fit. It stays `pending`, not refuted, until the user approves a GPU window (section 9) or an official quantized artifact is qualified.

**Selection rule, per role.**
- The model with the best selection metric wins.
- Tests use the paired bootstrap of section 6. LoCoMo resamples conversation clusters; MTEB tasks resample queries stratified by task, with the unweighted mean over tasks as the statistic. Holm runs over the role's frozen candidate list.
- Within the 0.02 band, 7.2's rule applies, followed by tie-breaks on lower warm p95 encode latency at the frozen batch size, then on lower peak VRAM. An exact residual tie is a joint selection.
- Model repositories get no Scorecard score.
- The selected model serves every configurable system and the common diagnostics (3.4).

### 8.3 Document-RAG head-to-head

- **Candidates**, all ACTIVE (section 1):
  - [qmd](https://github.com/tobi/qmd) v2.8.3 (`facd35e01359e59d938bc9418e93fb9318addee3`), through `qmd query` and `qmd search --json` (`README.md:54-56,76-80`);
  - [LightRAG](https://github.com/HKUDS/LightRAG) v1.5.7 (`28ff1b05f2ac3f3e6fa14dd2cd33656579bd0c9c`), through `QueryParam(only_need_context=True)` with its default `mix` mode ([`lightrag/base.py:90-117`](https://github.com/HKUDS/LightRAG/blob/28ff1b05f2ac3f3e6fa14dd2cd33656579bd0c9c/lightrag/base.py#L90-L117));
  - a [llama_index](https://github.com/run-llama/llama_index) v0.14.25 (`f12d46acab73f5b2243ef49c2f00101617b38ce4`) hybrid pipeline: BM25 plus a dense retriever, fused by `QueryFusionRetriever` in `reciprocal_rerank` mode with `num_queries=1`, so that no LLM rewrites the query ([`llama-index-core/llama_index/core/retrievers/fusion_retriever.py:24-41`](https://github.com/run-llama/llama_index/blob/f12d46acab73f5b2243ef49c2f00101617b38ce4/llama-index-core/llama_index/core/retrievers/fusion_retriever.py#L24-L41));
  - OpenViking v0.4.22, through `find` (`README.md:59,144` at `e8716760`);
  - memsearch v0.4.21, through its hybrid dense, BM25 and RRF search (`README.md:46,386,465` at `2a4652fa`);
  - cognee v1.6.2, through `SearchType.CHUNKS` (`cognee/modules/search/types/SearchType.py:4-16` at `ba3631f2`).
- **Wrapper.** Each system is wrapped as an MTEB `SearchProtocol` model ([`mteb/models/models_protocols.py:23-84`](https://github.com/embeddings-benchmark/mteb/blob/7fac921e8672cfb6799d7c6a9a542832bc10cbb6/mteb/models/models_protocols.py#L23-L84)). `index(corpus, …)` ingests through the system's native path, and `search(queries, …, top_k)` returns `{query_id: {doc_id: score}}`. `mteb.evaluate` runs the wrappers on E_doc. Returned artifacts must map to MTEB document IDs through a mapping frozen per wrapper; unmappable output is `N/A`, never a constructed score.
- **Configuration.**
  - Each system runs its shipped retrieval path, with every active LLM role on GPT-6 (2.1).
  - Configurable embedders and rerankers use the 8.2 document-role selection. S_doc chose it, so nothing leaks into E_doc. Otherwise the shipped model is used and labelled.
  - qmd's query expansion uses its own local fine-tuned GGUF (`README.md:562,731`), and its model overrides accept only GGUF URIs (`README.md:752`). qmd therefore runs with a recorded fixed-provider shipped default, not GPT-6.
- **Metrics:** nDCG@10 (primary; MTEB's main score), recall@10, warm p95 query latency (5.3's schedule), tokens per query (o200k of the returned payload plus native LLM usage at query time) and ingest tokens (5.2's ledgers).
- **Decision.** Section 7's merit and quality rules apply:
  - the primary is the unweighted mean nDCG@10 over E_doc;
  - tests use a paired bootstrap over queries stratified by task, with Holm over all 15 pairs;
  - then the 0.02 band, 7.3 and 7.4;
  - 7.3 uses C_RAG (repair round 1, finding F4): the gross priced cost of ingesting E_doc and answering every E_doc query through the wrapper, summed over every model call at ingest and at query time from ledger (a), with 5.2's price table and exact arithmetic. No client session exists here. A system with no priced model call has C_RAG = 0, which 7.3's equal-minimum rule handles.

  The memory-specific lifecycle/usefulness/coding items (5.4, 5.5 and 8.4) do not apply; the selected-repository maintenance, dependency SBOM/OSV, network, cost-readiness, observation and latency rules do.
- **Feasibility.** Before freeze, project the GPT-6 ingest tokens and wall-clock of the LLM-extraction systems on E_doc. If the projection exceeds the RAG window, drop E_doc tasks prospectively, largest corpus first, before any result. The coordinator or user sets that window before freeze; it defaults to 96 h per host, as in 5.2.

### 8.4 Code retrieval and the S8 code-task stage

- **S8: short-code do-no-harm only (ACCEPTED 2026-09-30).** The separate Harbor end-to-end stage checks each client's resolve rate for non-inferiority to the same client's no-memory control within a frozen margin and reports gross/signed token overhead. These short single-session tasks cannot exclude a system **on usefulness**; long-workflow usefulness is decided by LongMemEval-V2 (5.5). S8's pending design no longer makes every host's memory selection pending. Once its amendment is frozen, its coding do-no-harm result is required in that coding cutover/retention scope, reported separately from positive usefulness.
- **Route (repair round 1, finding F1).** S8 uses SWE-bench Verified tasks regenerated by Harbor's maintained adapter, never task bundles from the stale `harbor-datasets` (section 1).
  - *Harness and adapter:* `harbor-framework/harbor` v0.23.0 (tag object `3c305dc5`, commit `1e5c5c6db929a10a140d05e606882c671ae20729`) and its `adapters/swebench`, ACTIVE.
  - *Data:* the adapter loads `princeton-nlp/SWE-bench_Verified` by name, with no revision ([`adapters/swebench/src/swebench_adapter/adapter.py:46`](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/adapters/swebench/src/swebench_adapter/adapter.py#L46)). That is a separate Hugging Face dataset ([revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/tree/c104f840cc67f8b6eec6f759ebc8b2693d585d4a), last modified 2025-02-18), not an alias of the maintained [`SWE-bench/SWE-bench_Verified` at `78f471bf655a3137b2e8a75af1501690ec009ec3`](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified/tree/78f471bf655a3137b2e8a75af1501690ec009ec3), its main head on 2026-09-30 (last modified 2026-08-16). Both are static data pinned by the sha256 of the downloaded parquet. Every generated task's source row must be field-identical to the maintained revision's row for the same instance, and a task with any differing field is excluded before any result.
  - *Executable parts and their sources:*
    - the Dockerfile, from the adapter's template: `FROM` the SWE-bench instance image that swebench's test specification names ([`task-template/environment/Dockerfile:18`](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/adapters/swebench/src/swebench_adapter/task-template/environment/Dockerfile#L18); `utils.py:55`), then the uv 0.7.13 installer fetched with `curl | sh` (`Dockerfile:40`);
    - `tests/test.sh`, generated from swebench's test specifications ([`utils.py:6-8,55`](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/adapters/swebench/src/swebench_adapter/utils.py#L6-L55); the adapter requires `swebench>=4.1.0`, `pyproject.toml:12`). It runs the subject repository's own tests ([`task-template/tests/test.sh:4`](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/adapters/swebench/src/swebench_adapter/task-template/tests/test.sh#L4)), then a grading `parser.py` whose inline dependencies `swebench==4.0.3`, `datasets==2.16.1` and `fastcore<1.11` resolve when the verifier runs (`:10,82`), on a public verifier network (`task.toml:18-19`);
    - Harbor's verifier, which uploads and runs that script (`verifier.py:175-232`). No LLM judge is involved.

    At the repair-round gate, harbor, SWE-bench/SWE-bench, huggingface/datasets, AnswerDotAI/fastcore and astral-sh/uv were ACTIVE (section 1).
  - *Enforcement:* section 1's task-level provenance manifest. Image tags are mutable, so the built task image is frozen by digest; that covers the base image and the installer. The verifier's resolved dependency set is frozen and recorded on every trial, and a trial whose resolved set differs does not score. Every selected task's subject repository must pass the gate at freeze, and a task whose subject repository is stale is excluded (a task-selection filter).
- **Relayed prior check.** The coordinator relays that the separate token-tool E2E verified 36 SWE-bench Verified tasks as field-identical to `SWE-bench/SWE-bench_Verified@78f471bf`, with `tests/test.sh` being Harbor's adapter-generated script. This revision has not seen that receipt, nor which task bundles it compared. The check is cited as relayed, and its receipt is required before freeze.
- **Status: `pending`.** S8 runs only after a dated amendment freezes task/provenance manifests, each primary system and each client's no-memory control, task count, seeds, native resolve scoring, non-inferiority margin and paired test (including client-wise multiplicity), token-overhead accounting and failure policy. Pending S8 means coding non-inferiority is not yet claimed; it does **not** veto the main usefulness result or host selection.
- codebase-memory-mcp v0.11.0 (`8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798`) refused `/testbed`. That refusal is recorded as a fit limit, not as a quality result.
  - Upstream refuses any indexing root with fewer path components than the platform minimum ([`src/foundation/workspace.h:28-29`](https://github.com/DeusData/codebase-memory-mcp/blob/8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798/src/foundation/workspace.h#L28-L29); `docs/CONFIGURATION.md:196-199`), and Harbor tasks mount the repository at `/testbed`.
  - The refusal itself is relayed by the brief. No receipt for it exists in this checkout, so the Harbor lane's receipt must be cited before freeze.

## 9. Hosts (r6, retained with r7 edits)

Each host selects **separately**, with primary retrieval, main LongMemEval-V2 usefulness, hard gates and section 7's rule applied to its own measurements. Secondary/diagnostic lanes and S8's separately qualified do-no-harm scope keep their stated boundaries.
- **Order of acceptance testing on each host:** by primary-lane point estimate, descending. Continue while any untested eligible configuration could still change that host's selection.
- **Cross-host differences** are a diagnostic, not a gate.
- **CUDA timing, VRAM behaviour, model-serving compatibility and lifecycle acceptance do not transfer to macOS**, and Mac results do not transfer back.
- **Workstation GPU window.** r4 recorded production vLLM embeddings on 127.0.0.1:18231 and llama.cpp generation on 127.0.0.1:18232. r7's model selection runs within free VRAM without stopping them (8.2). A model that does not fit still needs **a scheduled production stop and restore that the user approves**; no S3 or AMB-driven process stops a production unit itself.
- **Per-host qualification.** Before its confirmatory run, each host records the RSS, latency and co-residency of every serving model, and runs 7.5's preflight for every system with a silent-fallback stage. Mac qualification is tracked by issue #379, and the bundle must cite its resulting measurement receipt.
- **Mac Hindsight (r6): reported runnable, host receipt required.** **Coordinator brief B:I** relays that Apple Container **1.4.1** was installed by the user on **2026-09-27**, with **Postgres 18.6 and pgvector 0.8.6**. These are the coordinator's supplied host observations, conditional on the **Mac's own sanitized receipts in the bundle before freeze**. Use Hindsight 0.10.2's supported external-PostgreSQL route (`installation.md:37-39` at `5fc4ce20`) through that host's runtime with fresh arm resources and a frozen digest. Reported hosting does not pre-pass 5.4 or the early durability/output-cap checks.
- **Both GPT-6 backbones (r6).** Each host's gateway identity comes from its own sanitized build/patch receipt before freeze (2.2's gateway identity note). The workstation uses `http://127.0.0.1:20128/v1`. **Coordinator brief B:A/I** relays that the Mac has **its own LaunchAgent gateway on the same tree/patch IDs, 12/12 verified**; include **the Mac's own 12/12 and effective-build receipts** before freeze; the Mac does not call the workstation's gateway. Keep reported readiness separate from new arm-level wire/effort/usage and lifecycle acceptance. No sign-in or quota recheck is inferred from an older blocker.

## 10. What this does not claim

- Local-harness scores are not official leaderboard results.
- Vendor-published numbers, AMB's leaderboard included, are motivation only.
- A “SOTA” discovery shortlist is not a measured universal winner. GPT-6 wiring, model-card scores, source review, recorded setup smoke, this host's new acceptance and another host's acceptance are different evidence levels. Neither GBrain's hosted 449/470 nor Hindsight's recorded wire probes decides S3.
- Passing the maintenance gate shows activity, not quality. A Scorecard score is a heuristic, and RQ only breaks ties.
- Registry metadata, such as Hugging Face LFS oids and image digests, is not a hash of downloaded bytes.
- A retrieval score says nothing about capture or deletion safety; 5.4 covers those.
- Non-inferiority to no memory on S8 (8.4) shows only that resolve rate is within the frozen do-no-harm margin; it is not positive long-workflow usefulness. A 7.6 deployment fallback without main usefulness qualification is explicitly labelled as such.
- Agreement among reviewers, and blinding, do not validate a measurement.
- Nothing here changes a host until the winner passes a cold-copy cutover with rollback.

## 11. Freeze procedure

1. Build the experiment bundle:
   - this document and the decision record;
   - the inputs under `inputs/` with sha256: the r4 Mac sweeps, five r6 captures (r6 §14), r7 live capture, all three repair-source captures and GPT-6 review capture; current maintenance receipts for selected repositories and complete per-arm dependency SBOM/OSV receipts, including harness import paths and stale transitive flags;
   - the downloaded dataset's sha256 and byte count, the full-population 470, official 419 and QA 500 manifests, any prospectively selected subset with its recomputed cluster and official-intersection counts, the development split hashes with the no-overlap check, and all 20 query and 5 continuation task specifications with their expected evidence and the manual-audit sampling rule;
   - **AMB `03c1d0f1d27da63034f0931121c858faba512383` verified byte-identical**, each arm's executed-environment hash, both S3 dataset adapter variants with the no-judge and zero-Google/Groq wire proof, the S3 scorer and its tests, the dispatch wrapper, every thin provider client (Hindsight's included), each system's frozen effective store settings (for Hindsight, the bank-configuration hash), the common depth mapping and retry policy, the parity checklist, and the GPT-6 adversarial audit with its resolutions;
   - the **main LongMemEval-V2** small-tier/subset, full-tier haystack-component manifest and downloaded-file verification of at least 20 selected components (or pending lane status), per-domain runtime files/ID lists, native registration/config/bootstrap hashes and the same direct-harness argv for all arms/control, upstream no-retrieval config hash, shared-state/context policy, reader/evaluator request-body wire proofs, five paired replications, arm/baseline failure thresholds/ledgers, prospective cost/power/window estimate and separate k/m_U Holm family; native MemoryAgentBench configs/commands for applicable secondary modes only, with the per-system applicability table and no vendored candidate execution; MemoryArena excluded from execution;
   - the S8 amendment with task/provenance manifests, resolve-rate margin/test and relayed 36-task receipt, or its recorded `pending` coding do-no-harm status; neither option reintroduces a usefulness or host-selection coupling;
   - the A17 supersession amendment (`blueprints/memory-stack/longmemeval/A17-SUPERSESSION.md`), revised to match r7. Its lines 16 and 19–21 still describe r4–r6's reference arm, and that file lies outside this revision's paths;
   - the analysis code bound to **SciPy 1.18.1 / statsmodels 0.15.0**, locked NumPy version, frozen 7.2–7.3 functions and 4.5/7.1/7.5/7.6 examples passing with their negative controls, both pairwise families (k, m/m_U, placeholders), 10,000-resample and linear-quantile settings, verified usefulness component minimum, diagnostic sign-flip and achieved-power reports (including prospective subsets); open-QA prefix/context-token evidence, output ownership/exact native filenames and score-manifest reconciliation with retained zero-score failures;
   - client and plugin versions;
   - the 8.2 selection receipts with every model's full revision, quantization and native serving pin, and the E_doc/S_doc partition;
   - the RAG wrappers and their mapping rules;
   - the GPT-6 per-role model/effort matrix, the R02 and optional-stage decisions with per-role or coupled-set n, metric, α and test and per-host outcomes, the fixed Astra-max answerer and judge, and no stale fallback models;
   - per-host gateway build receipts, container-to-loopback transport, denied-egress negative controls, conversation affinity, cache/dedup exclusion and effective-effort wire receipts for all call paths, AMB/LongMemEval-V2 answerer/evaluator included; every header-limited client's verified exemption/per-arm native route, or its explicit pending status;
   - each system's upstream install/test/lifecycle recipe and immutable image/lock pins, fresh container/volume/home identities, effective role overrides and early lifecycle-screen results, both sanitized live deploy receipts, and the Mac's own hosting and 12-of-12 gateway receipts;
   - prompts, seeds, fixtures, configurations, **development-selected K**, supported concurrency knobs and observed call concurrency, block-randomized dispatch, measured development tokens/s and **projected wall-clock per host against the 96 h window**, prospective full/subset/reuse decisions, joint serving-model co-residency receipts, 7.5 preflights with full stage-outcome coverage and a successful-gateway invalid-score native control, non-overlapping ledgers, authoritative price mappings or declared unpriced coverage and cost limits, explicit gross-C/local-cost sensitivity boundary, Scorecard/RQ inputs with pinned-commit check/status captures (7.4), and the supported scratch-home sign-in route for 5.2(c).
2. Verify that every referenced file and link exists.
3. Get a GPT-6 cross-family review of the **bundle**, and resolve every required finding.
4. **Obtain the user's explicit acceptance** of the reviewed bundle, including the coordinator decisions listed in "r6 → r7 changes", the repair-round decisions in the decision record's "Decisions for acceptance" and the A17 supersession. Freeze only after both.
5. Record the immutable commit and the bundle's sha256 list outside the worktree, rerun the maintenance gate, then run.
6. Keep per-case outputs, failures and each arm's actual execution status.

## Appendix A. r1–r6 review history (unchanged)

The sections below are r6's sections 10–16 exactly as they stand at `f7e5e228` (PR #390's head `d161f691` merged with `main`), except that each heading gains the prefix "r6 §". Their section numbers, "Fixed in" pointers, source keys (I, R, M, W, V, U and B, defined in r6 §14) and locators refer to the r6 text, not to r7. Where they name LongMemEval's scorer or judge prompt for execution, or ai-memory v2.4.0 as the reference, r7 supersedes them ("r6 → r7 changes").

## r6 §10. r1 findings and their fixes

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

## r6 §11. r2 re-check findings and their fixes (r3)

| r2 re-check finding | Fixed in |
|---|---|
| partly resolved r1-2: cluster assignment, weighting, seed aggregation, RNG, C4′ preflight | §6: frozen preflight, cluster manifest, seed averaging, question weighting, PCG64 seed |
| partly resolved r1-4: payload ledger promoted to complete cost; aggregation undefined | §4.2 decision ledger; §7 routes use it |
| new medium 1: "lower 95% bound" ambiguous | §6: one-sided 5th percentile, `numpy.percentile(method="linear")` |
| new medium 2: non-inferiority escapes Holm | §6: per-host family holds both hypotheses; Holm at α 0.05 |
| new medium 3: payload fallback changes the winner | §4.2: payload counts support only a payload-size claim; incomplete ledger means `pending` |
| new high 4: superiority bypasses usefulness | §7: usefulness floor before either route |

## r6 §12. Relationship to the A1–A16.3 protocol and A17 (r4, proposed)

- **What A17 was.** VelaNext was retired, so the confirmatory rerun R1 of the frozen memory-stack protocol (A1–A16.3, v3 #380 and v4 #386) needed another host and a new amendment naming it before any run (`docs/decisions/2026-09-25-retire-vela-velanext.md:36-44`). The workstation took R1 as "A17" (`docs/decisions/2026-09-25-workstation-sota-refresh.md:542-546`; issue #274). No A17 text was ever written, and no session holds a draft (checked 2026-09-27).
- **Why S3 supersedes it without spending a look.** No confirmatory arm of A1–A16.3 has ever run on any host: no C3′, C4′, C4 or D2h result exists (`retire-vela-velanext.md:43-44`; `catalogs/foundation/memory-stack-20260925.json:1318`; `docs/decisions/2026-09-27-mac-single-writer-staged.md:48`). Retiring R1 in favour of S3 therefore consumes no confirmatory look and selects nothing after seeing results.
- **What carries over.** The user's 2026-09-25 choice of official ai-memory v2.4.0 as the control (issue #274; `workstation-sota-refresh.md:228`) becomes S3's reference, and the A-protocol's C3/C4/D2h configurations are the starting point for S3's C3′, C4′ and agentmemory configuration. There are two stated differences (r5):
  - C3′/C4′ use Qwen3-Embedding-4B's native, unprefixed input, because v2.4.0 has no prefix setting;
  - agentmemory's adapter must prove shipped-hook equivalence (sections 1 and 2). The historical Mac C3 on `19b6429` stays descriptive.
- **Additional r6 differences:** the GPT-6 LLM backbone (including C4′ and agentmemory), development-selected configurable local retrieval models, Astra-max QA/judging, isolated native deployments and research-memory usefulness scope in sections 1–5. The A-protocol's local generation pins and historical zero-LLM results are not carried over as r6 scored configurations.
- **What does not carry over.** The A-protocol's statistics and decision rules (section 6), its v4 = v3 reproduction gate and its VelaNext-only drivers. S3's gates, unmodified AMB orchestration with frozen provider modules, and section 6's upstream-bound statistics replace them.
- **The amendment.** `blueprints/memory-stack/longmemeval/A17-SUPERSESSION.md` records this as a dated amendment in the protocol's own lineage, a new file, since frozen text is never edited. It is **proposed**. It takes effect only when the user confirms it at the S3 freeze (section 9). Until then nothing runs under either protocol.

## r6 §13. r4 review findings and their fixes (r5)

| r4 finding | Fixed in |
|---|---|
| high 1: v2.4.0 has no embedding-prefix setting; C3′/C4′ cannot reproduce prefixed C3/C4 | §1 definitions: native unprefixed input; S3 controls, not reproductions; embedding-request bytes verified before scoring; §12 |
| high 2: session-ID clustering misses shared conversation content | §3 canonical `(role, content)` rule, 452/401 clusters reproduced with frozen v4 code; §6 manifest |
| medium 3: upstream does not supply both corpus constructions | §3 official track upstream; full-session track the A2 local extension |
| medium 4: D2h is not the shipped default, and hook replay omits transcripts | §2 explicit local-MiniLM configuration; hook equivalence required |
| medium 5: C4′ fallbacks not connected to the decision rule | §7 reference fallbacks: comparisons inconclusive, selection unresolved, no post-hoc C3′ comparator |
| low 6: pending provenance written as present | §2 inputs "will be committed"; §5 #379 is an issue, and the bundle cites its receipt |

## r6 §14. r6 changes and their sources

**Source convention.** Repository `path:line` citations refer to the input checkout at **`75e30ea4`** unless a different pin is named. `embed.md`, `rerank.md`, `memsys.md`, `memllm.md` and `gen.md` mean files under [`inputs/sweep-20260927-mac/`](inputs/sweep-20260927-mac/README.md). Upstream links specify the inspected tag/commit. **I, R, M, W and V now resolve exclusively to the repository copies below**, captured **2026-09-27**. Each has one added source/date line and the required personal-home prefix → `~` and session scratch-prefix → `<scratch>` substitutions; all other bytes, including EOF newline state, are preserved. Hashes cover **these sanitized copies**, and line ranges count the added first line. No mutable scratchpad or workflow journal is an evidentiary locator for this revision. Former J/G leads are replaced with the pinned upstream citations in 1.2, 2/2.1 and 4.4; host/image observations still require their own sanitized native receipts before freeze (5/9), not raw worker conversations or credential stores.

| Key | Repository capture, line range and sha256 | Evidence boundary |
|---|---|---|
| **I** | [`inputs/r6/s3-r6-inputs.md:1–58`](inputs/r6/s3-r6-inputs.md); sha256 `22389274ad57b42b4ad365a9495ab630331cc2ba4e7f76cfe9a10c3d52901e31` | Gateway rules **4–14**; cognee smoke **16–35**; live hosting **37–54**; Hindsight **56–58**. Supersedes the stale `b0a99fe4…` capture. I:13/31's arm-wide affinity, I:53's effort knob and the broad omission claim at I:48 are corrected in 1.2/2.1. I:34's manifest registration is future integration work outside this repair. |
| **R** | [`inputs/r6/gateway-ab-designs.md:1–101`](inputs/r6/gateway-ab-designs.md); sha256 `d38e9973eda2ae1c84fb2f635959a2068a4358267bb4df51586460959a0ee73b` | Arm rules **7–11**, upstream-harness/statistics rule **15–29**, R02 **31–53**. Supersedes the stale `27e45209…` capture. Its promptfoo/li26 mechanics are leads for their own lane; S3 uses AMB and its own frozen metric. No R02 line supports the removed one-request pacing rule. |
| **M** | [`inputs/r6/memory-merit-synth.md:1–175`](inputs/r6/memory-merit-synth.md); sha256 `89da63f6197d03384e7b716270cb04130d4b3f534dc2a88a247791d05824688f` | Merit/admission/lifecycle leads. Unverified code-level claims remain leads (**167–173**); selected facts use pinned upstream citations in 2 and 4.4. |
| **W** | [`inputs/r6/eval-frameworks-report.md:1–131`](inputs/r6/eval-frameworks-report.md); sha256 `c5f25772de014b945a20b02c2e4b464d34c59f90e9f09060500600ebff0c7f55` | Upstream framework research: AMB **10,53–71**, MTEB **73–81**, SciPy/statsmodels **83–97**. Migration instructions and source review, not executed S3 acceptance. |
| **V** | [`inputs/r6/r6-claude-review.md:1–125`](inputs/r6/r6-claude-review.md); sha256 `aac90a9b092c7a1ea38cb42c455bd00768cabc7a8696b6035001c458924a4824` | Full cross-family review: H1–H4 **11–52**, M1–M5 **56–98**, L1–L4 **102–109**, verification gaps **119–123**. Its P/I/R/M locators describe the pre-repair revision; the active locators in this document use the captures above. Its claims are leads until checked against pinned sources; corrections are recorded in 15. |
| **U** | User's **2026-09-27 directions 1–4**, reproduced below | Normative directions, distinct from the coordinator's detailed requirements A–I. |
| **B** | **Coordinator's r6 brief, requirements A–I**, mapped below; attribution checked against V:103 | Coordinator-authored specification under delegation. **B:I** relays Apple Container 1.4.1 / Postgres 18.6 / pgvector 0.8.6 and the Mac's 12/12 gateway claim; the Mac's own receipts remain required before freeze. The **96 h** window is the coordinator's repair decision 2, overturnable by the user before freeze. |

**U:1–4, verbatim user directions; A–I are not user quotations:**

1. “make sure the memory lane using the best of the best repos, congee, hindsight or other evl via gpt6, via runtime workers hosting the sota repos powered by gpt6”
2. “never use staled models, keep using the real SOTA models”
3. “deploy hindsight and cognee now with gpt6 via omni when ready, and make sure our architecture layers resolute with the best candidates live natively, with the best repos of full lifecycle and upstream commands e2e”
4. “make sure they are the best in its layer, with evl of the sotaness, features and best suitable for our ecosystem and pave the way to north star”

| Change | Landed in | Source and resulting contract |
|---|---|---|
| **A — GPT-6 backbone and gateway discipline** | **1.1–1.2, 2, 3, 4.1, 5, 9, 12** | U:1–3; B:A; I:4–14,18–58; R:7–11,31–53; pinned upstream links in 1.2. Every active LLM role is GPT-6; choose/freeze model and effort on the separate development split, use `-max` where needed, conversation affinity, no-cache plus a dedup-ineligible stream/resolved temperature, fresh per-call IDs where supported or verified omission, compression off and observed effort. C4′'s old local LLM and agentmemory's zero-LLM primary are superseded explicitly. |
| **B — Answerer and judge** | **4.5, 9** | B:B; I:5–12; R:50; [OmniRoute max suffix](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/executors/codex.ts#L1451-L1456). Fixed GPT-6 Astra max for QA answerer/blinded judge; retained stratified manual audit, with prompts and judge independence frozen. |
| **C — Native hosting and corrected configurations** | **2.1, 3, 9** | B:C; I:16–58; Pinned key-precedence and adapter sources in 2/2.1; W:53–71. Live deployments are hosting evidence only; preserve both deploy receipts and the failed unguarded Hindsight start. Fresh container/volume/home per arm, upstream image/lock pins, no scored persistent cognee, instructor `tool_call`, per-role GPT-6 overrides and corrected embedding key precedence. |
| **D — Candidates and plain retrieval diagnostics** | **2, 4.1, 6** | B:D; M:9–13,59–67,71–117; [GBrain pinned session metric and 449/470](https://github.com/garrytan/gbrain/blob/e78f1c38b947b053f3a46881340f74f316be855a/CHANGELOG.md#L2039-L2061); pinned Mem0/Attemory admission sources in 2. Keep seven primaries/C4′, exclude Mem0 OSS/Attemory on fit, screen GBrain through the late-candidate rule; add BM25/dense Qwen3 outside the family. |
| **E — Current local retrieval challengers** | **2, 3, 4.1, 9** | U:2; B:E; `embed.md:9–17,28–41,64–75`; `rerank.md:9–14,44–73`. LoCoMo chooses configurable local embedders/dedicated rerankers; LongMemEval never selects them. MiniLM/BGE-small are labelled controls/diagnostics or documented fixed-provider defaults, with agentmemory's explicitly directed B:C MiniLM exception. MTEB 2.21.8 supplies the registered task and two-stage runner (W:73–81). `memllm.md:136–199` and `gen.md:23–85` remain discovery inputs; their local generation rankings do not override the mandated GPT-6 LLM backbone. |
| **F — Research-agent usefulness** | **4.5(a), 7, 9** | B:F; `blueprints/us-equities/north-star.md:33–35,57–60,74–79`; `catalogs/us-equities/README.md:52–58`; decision-index and four domain READMEs at the RM01–RM08 locations. Keep 20 queries + 5 continuations; at least eight research-memory queries have frozen expected evidence and count toward the same minus-one usefulness floor. |
| **G — Cost, sample and pooled-account load** | **4.2, 6, 9** | B:G and coordinator repair decision 2; approximately 115K history scale in [pinned benchmark overview](https://github.com/AttemorySystem/attemory/blob/603c03afa9a04e48b778922eae156a0024752f37/README.md#L125); I:35. Plan **all 470** (452/401 full-population clusters), with only a **prospective stratified subset** if measured projection exceeds **96 h per host**. Preserve stochastic paired seeds, 10,000 resamples, Holm α=0.05 over 14 and +0.05/−0.02 rules. Freeze development-selected K for **full parallel utilization**, measured tokens/s and wall-clock projections; a deterministic arm is ingested/counted once. Never gate on a recorded quota. |
| **H — Probe lifecycle blockers early** | **4.4, 5, 9** | B:H; M:45,76–77,128,138–142,172; agentmemory issues [1273](https://github.com/rohitg00/agentmemory/issues/1273), [1190](https://github.com/rohitg00/agentmemory/issues/1190), [1389](https://github.com/rohitg00/agentmemory/issues/1389); MemPalace [1581](https://github.com/MemPalace/mempalace/issues/1581); Hindsight [models.mdx:154–169](https://github.com/vectorize-io/hindsight/blob/f8950b0c07d9e34c76493dba802bb309f0ce60fd/hindsight-docs/docs/developer/models.mdx#L154-L169) and I:58. Development checks target delete, complete empty-instance restore, sustained-load OOM, concurrent-writer corruption, actual database durability settings and output-limit compatibility. |
| **I — Both hosts ready for their own qualification** | **1.1, 5, 9** | **B:A/I**, the coordinator's relayed Apple Container/Postgres/pgvector and 12/12 gateway observations, not U's verbatim words. The Mac's own sanitized hosting, gateway and build/patch receipts are mandatory before freeze; keep each host's decision and scored-arm qualification separate. |

**Corrections recorded in r6, with verification paths.** In addition to the table: (1) R:8 supersedes per-arm affinity in I:13/31; (2) the pinned upstream implementation supersedes the research claim that agentmemory's separate embedding key wins, confirmed in the pinned `embedding/index.ts:37–38` and `embedding/openai.ts:64–68`; (3) I:25–35's measured instructor success/JSON failures supersede cognee's research-only structured-output inference, with the pinned LiteLLM/config corrections in 2.1 retained; (4) GBrain's pinned `CHANGELOG.md:2042–2061` supersedes `memsys.md:36`'s chunks/session dismissal; (5) the coordinator's B:I report conditionally supersedes the old Mac owner-install blocker. The sweep summary's broad “no Mac path” for Nemotron (`README.md:16`) is also narrowed to its unregistered llama.cpp class: the detailed `embed.md:12,40–41,71` leaves PyTorch/MPS as a development qualification path. These corrections do not rewrite historical source captures or claim unexecuted acceptance.

## r6 §15. r6 cross-family review findings and their fixes

The complete review is **V**, captured above. All thirteen findings are applied in this repair; the table records the correction and its verification path. This is a **protocol/source repair**, not runtime acceptance or a freeze. Measured throughput, provider parity, latency/fallbacks and native host receipts remain bundle prerequisites.

| Finding | Fixed in | Applied change and source verification |
|---|---|---|
| **H1 — stale sources** | **1.1–2.1, 4.4, 9, 14** | Captured all five requested inputs; hashes and every active I/R/M/W/V line locator refer to the sanitized repository copies. R02 is R:31–53; live hosting is I:37–54; Hindsight is I:56–58. Removed J/G scratchpad/journal locators in favor of the existing pinned upstream citations and explicit host-receipt requirements. Original bytes differ only by the required header/sanitization, including preserved EOF newlines. |
| **H2 — standalone harness** | **Status, 3, 9, 12** | Unmodified **AMB 03c1d0f1**, frozen/hashed MemoryProvider modules, unchanged **LongMemEval @9e0b455f** scoring, pinned loader path, Gemini-key/.env handling and equal-depth parity audit. **Correction to V:24 and V:27:** the shipped cognee provider is an in-process SDK wrapper, not an HTTP client, and hard-codes an old LLM/BGE-small plus top_k=50. Its separate frozen provider adaptation is required; AMB orchestration stays unmodified. Verified at [cognee.py:66–86,118–137](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/memory/cognee.py#L66-L86), [Hindsight HTTP:1242–1255](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/memory/hindsight.py#L1242-L1255), [CLI:12–30](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/cli.py#L12-L30) and W:53–71. |
| **H3 — pacing/feasibility** | **1, 3, 4.2, 6, 9, 14** | Removed unsourced single-call/one-second limits. Freeze development-selected **K** for the user's **full parallel utilization**, native concurrency controls, block-randomized order, measured tokens/s and per-host projection. **96 h per host** is the coordinator's decision; a prospective stratified subset with power calculation is allowed only before results. Deterministic arms ingest/count once. The review's canary projection is illustrative, not full-run throughput (I:35; V:29–41). |
| **H4 — query latency/fallbacks** | **1, 4.3, 6, 7, 9** | GPT-6 query calls remain inside **warm p95 ≤1.0 s**, with **10 s** timeouts. Isolate latency from other arms' calls; report queue wait separately. Development preflight now measures C4′ fallback rate and warm p95; **>5% fallbacks selects C3′ before confirmatory execution**. Later failure still leaves the host unresolved. Source: [ai-memory v2.4.0 reranker behavior](https://github.com/akitaonrails/ai-memory/blob/v2.4.0/docs/llm-providers.md#L185-L195). No GPT-6 latency has been measured by this repair. |
| **M1 — statistics implementation** | **6, 7, 9** | Bound the unchanged weighted-cluster estimand to **SciPy 1.18.1 / statsmodels 0.15.0**, explicit **10,000** paired resamples, **PCG64(20260927)**, linear fifth percentile and **14** Holm hypotheses with missing-arm p=1.0. Sign-flip is diagnostic only. Removed the undefined adjusted-bound equivalence. Verified [SciPy signature/quantile path](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_resampling.py#L300-L303) and [Holm branch](https://github.com/statsmodels/statsmodels/blob/v0.15.0/statsmodels/stats/multitest.py#L233-L247); W:83–97. |
| **M2 — envelope/static headers** | **1.2, 2.1, 9, 14** | Wire-verified stream or absent/>0.1 resolved temperature; explicit 1.0 is permitted. Defined question × seed × arm conversation, fresh-process route and conditional Hindsight affinity route. Static idempotency keys are never called fresh: omit both key headers on static-only adapters and prove no replay. Read [idempotency.ts:74–110](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore/idempotency.ts#L74-L110) and [header fallback:42–55](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/idempotencyLayer.ts#L42-L55), closing V's stated verification gap. An initial source lookup under services returned 404; [chatCore's import:33](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts#L33) resolves the actual path used here. |
| **M3 — live deployments** | **2.1, 3, 4.4, 9** | Recorded I:37–54's hosting evidence; protect ports **3800/3710/5433**, archive both sanitized deploy receipts, recheck **10.0.2.2:20128**, preserve the guard modification and first failure, and keep live services unscored/untouched. Corrected operation **LLM_MODEL/LLM_REASONING_EFFORT** names and global-none/unset-operation temperature resolution. Verified [config.py:210–245,383–462](https://github.com/vectorize-io/hindsight/blob/f8950b0c07d9e34c76493dba802bb309f0ce60fd/hindsight-api-slim/hindsight_api/config.py#L210-L245); live claims are input receipts, not newly reproduced execution. |
| **M4 — R02 selection** | **1.1, 3, 6, 9** | Before development calls freeze full-system LoCoMo supporting-evidence recall@5, schema validity, **n**, cluster manifest and one-sided α=.05 bootstrap; coupled roles select jointly, on each host. Unresolved roles leave arms pending and require a dated amendment before their first confirmatory run. R:31–53 motivates the comparison; section 6 supplies its statistical implementation. |
| **M5 — judge/model checks** | **4.1, 4.5(b), 9** | Unchanged LongMemEval **get_anscheck_prompt**, including abstention, under the Astra-max envelope rather than the temperature-0 script call path; MTEB **2.21.8 LoCoMo** and upstream two-stage reranking with recall@5 frozen before selection. Verified [judge prompt/call path](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/evaluation/evaluate_qa.py#L24-L43), [LoCoMo registration](https://github.com/embeddings-benchmark/mteb/blob/2.21.8/mteb/tasks/retrieval/eng/lmeb_retrieval.py#L996-L1038) and W:73–81. MTEB's default ndcg_at_10 is not silently substituted. |
| **L1 — GPU consent** | **5** | Restored **“a scheduled production stop and restore that the user approves”**; the runner never stops production itself (V:102; accepted r5 source at 75e30ea4, this file:221). |
| **L2 — attribution/Mac receipts** | **Status, 1–5, 9, 14** | U contains only verbatim directions **1–4**; **B** is the coordinator's **A–I** brief. Host-install and 12/12 statements are relayed observations; require the Mac's own receipts before freeze (V:103). |
| **L3 — MiniLM exception** | **2, 4.1, 14** | MiniLM remains primary as the explicitly directed **B:C exception to B:E**, despite agentmemory's configurable OpenAI-compatible embedder. **Attribution correction to V:106:** requirement C is coordinator-authored, reaffirmed by this delegated repair request; it is not one of U's verbatim directions. Upstream [local provider](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/providers/embedding/local.ts#L8-L46) and [OpenAI-compatible provider](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/src/providers/embedding/openai.ts#L64-L68). |
| **L4 — achieved power** | **6, 9** | Require both routes' achieved-power report from frozen analysis over stated discordance **0.10–0.30**, with cluster/seed/family assumptions and simulation uncertainty. Informational, not a new gate or margin; prospective subset power remains required. V:108–109's normal approximation stays illustrative. |

**Verification boundary.** This repair read the pinned AMB registry/CLI/runner/loader/providers, OmniRoute dedup/idempotency code, Hindsight config/affinity, ai-memory reranker documentation, SciPy/statsmodels implementations, LongMemEval judge prompt and MTEB LoCoMo/two-stage sources. It did not execute provider/model runs, inspect live services or credential stores, remeasure the Mac, or treat archived worker answers as upstream acceptance. The byte/hash/locator checks verify the document repair; they do not satisfy the experiment's pre-freeze execution gates.

**Repair validation.** Sanitized-copy byte equality (including EOF state), all five copy hashes, active source-locator bounds, all 13 finding rows, analysis-snippet syntax and `git diff --check` pass. The coordinator committed the repair and merged `main` under the hot-file protocol, re-registering this document and the five `inputs/r6/` copies in `manifests/evidence.json`; `python3 scripts/validate.py` then passed (merge commit `f968acf8`). The section 16 fixes change this document again, so it is re-registered and re-validated in the same commit.

## r6 §16. r6 re-check findings and their fixes (2026-09-27)

A one-round Claude re-check compared the repaired draft with pinned AMB `03c1d0f1`, LongMemEval `9e0b455f`, SciPy 1.18.1, statsmodels 0.15.0 and MTEB 2.21.8. It confirmed the 13 section 15 rows and found the defects below. N1 and N2 sat in the AMB text that coordinator decision 3 had adopted from the review, so their fix is a coordinator decision.

**Decision (coordinator, 2026-09-27; alternatives and overturn condition in section 3):** one frozen, hashed LongMemEval dataset adapter in AMB's retrieval mode. The coordinator verified the premises in the AMB source at `03c1d0f1`:
- `EvalRunner.__init__` constructs `GeminiJudge()` (runner.py:42);
- AMB's LongMemEval dataset has `task_type = "open"` (longmemeval.py:67);
- its documents carry `"{question_id}_{session_id}"` IDs in the ID and the context (longmemeval.py:329–349);
- the retrieval branch makes no judge call and passes the provider's ranked documents to `score_retrieval` (runner.py:222–227; modes/retrieval.py);
- `EvalRunner.run` takes a `Dataset` instance (runner.py:51–71);
- the lock pins cognee 0.5.4 and hindsight-client 0.9.2 (uv.lock:854–855, 2077–2078).

| Finding | Severity | Fixed in | Fix |
|---|---|---|---|
| **N1 — Gemini judge on every LongMemEval query** | High | 3, 9 | Retrieval mode with the adapter's `task_type = "retrieval"` removes every judge call. A placeholder is used only to construct the client. The wire proof shows no Google or judge call. |
| **N2 — gold-revealing raw session IDs** | High | 3 | The adapter emits opaque IDs, an ID-free context and the frozen track, and exports each ranked opaque-ID list through `score_retrieval`. The parity audit verifies at the wire that no provider receives a raw ID. |
| **N3 — cognee lock conflict** | Medium | 3, 9 | The cognee arm runs cognee v1.6.1's tag lock plus unmodified AMB source. The bundle hashes each arm's executed environment. hindsight-client 0.9.2 versus the 0.10.1 service is added to the parity audit. |
| **N4 — sequential runner versus K and route (a)** | Medium | 3, 9 | A frozen dispatch wrapper with no benchmark logic launches unmodified per-unit `EvalRunner.run` processes in the frozen order and concurrency. |
| **N5 — AMB judge prompts and headers** | Medium | 4.5(b) | AMB's judge is not used. The S3 answerer and judge run outside AMB under 1.2, and 4.5(b) is `pending` until the answerer integration passes the wire check. |
| **N6 — `validate.py` on the pushed tree** | Medium | Repair validation | The coordinator re-registered the document and the five `inputs/r6/` copies. `validate.py` passed at `f968acf8` and is re-run for this commit. |
| **N7 — V:28 locator** | Low | 15 (H2 row) | "Correction to V:24 and V:27". |
| **N8 — user attribution** | Low | 4.2 (K rule) | V:32, the memory locator, and "historical evidence, not authority"; the K rule is attributed to coordinator decision 2. |
| **N9 — removed runner still named** | Low | 2 (pins), 5 | "the Mac's own sanitized host receipt"; "no S3 or AMB-driven process". |
| **N10 — precision** | Low | 4.4, 4.5(b), 14, 15 | `M:139,172`; `167–173`; `evaluate_qa.py#L24-L43`; section 5 removed from H4's "Fixed in". `embed.md:31–41` (the challenger shortlist, section 4.1) and `28–41` (controls plus shortlist, E row) stay distinct by design, after checking the committed sweep file: rows 28–30 are the MiniLM control, mxbai and LFM2-ColBERT. |

**Residual verification gaps**, named by the re-check and not checkable from its snapshot, all left for the section 9 bundle review:
- OmniRoute `codex.ts`, `chatCore.ts`, `idempotency.ts`, `idempotencyLayer.ts` and `requestDedup.ts`;
- Hindsight `config.py`, `cache_affinity.py` and its installation and model docs;
- cognee config and Dockerfile, and agentmemory sources;
- the GBrain, Mem0 and Attemory links, and the `akitaonrails/ai-memory` URL;
- MTEB `two_stage_reranking.md`, which is not in the wheel;
- the sweep-file and RM01–RM08 locators.
