# Native memory qualification preregistration

Status: **draft specification; configuration and exposure gates are not closed**.
This document registers a prospective local qualification procedure, not a passed
experiment, an approved production replacement, or a published benchmark result.

The objective is to compare `native_files`, `ai_memory`, and `hindsight` on the
same sanitized sources, and determine whether a challenger merits a broader
representative trial. The corpus is locally authored synthetic material. A
successful fixture run cannot establish production readiness or justify changing
the maintained selection by itself.

## Source and host boundary

- Work starts from repository `231eed43e17cc7953751b7caf90376b01cb5feec`.
  Canonical main was independently reported as
  `49a4260029244e3e20d8b2dd3ada00af7983a3c9` at 2026-10-02 05:36 UTC;
  its unrelated WSL changes are outside this unit.
- The maintained page `decisions/production-foundation-20260930.md` was read
  directly in scoped `default/wha`. Its 05:28 UTC checkpoint retains ai-memory
  2.5.2/source `7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83` and Ollama 0.34.4,
  while Hindsight 0.10.2 and coding-agents 0.8.0 remain isolated. Historical
  compaction, synthesis, timeout and consolidation failures remain failures.
- Surviving host: `mac-colima-memory-qualification-20261002`, Mac aarch64,
  64 GiB memory and 18 CPUs. Dedicated Colima `memory-qualification` profile:
  Colima 0.10.3/`00f6c297e92a82c04a4ab507db0a61435650d7e8`, VZ, 4 vCPUs,
  12 GiB RAM, 32 GiB disk, no host mounts, `--activate=false`. Guest: Ubuntu
  24.04.4 and Docker 29.5.2. These are coordinator-supplied host observations;
  the run must attest the matching host receipt and image digests before launch.
- Vela/VelaNext is retired. The frozen unsafe benchmark is excluded. No production
  service, provider, personal history, native login or default Docker context is
  changed by this preregistration. The coordinator owns the isolated runtime.

## Corpus and exposure

`corpus-manifest.json` defines freeze ID
`synthetic-native-qualification-20261002-v1`. There are 12 development cases
(two in each category) and 60 authored holdout cases (ten in each category):
current/historical facts; updates/conflicts; unfinished workflow/ownership;
entities/multistep joins; distractors; abstention/false premises. Source documents,
case IDs and scenario IDs are disjoint between splits; development values and
identities differ from holdout values and identities. Shared authoring patterns
and an author who has seen all cases still limit independence.

The ASCII-base64 packaged holdout archive is sealed by SHA-256, with separate
encoded-file, decoded-archive and every-member hashes. This
seal proves byte identity; it does not encrypt content or enforce access. The
author is exposed. Coordinator and tuning-executor exposure are initially
`not_attested`, never implicitly false. A coordinator content read makes that
coordinator exposed. Any tuning-executor source, query, gold, archive-member,
failure-detail or per-case score read before freezing configuration makes the
trial exploratory. An aggregate count or hash check alone does not reveal content.

Before calling a run confirmatory, independently attest that its tuning executor
was technically isolated from the sealed content and has not consumed authoring
tool arguments, archive bytes or a decoded member. Procedural instructions alone
do not prove this. Otherwise label this corpus an exposed synthetic qualification
fixture and obtain a separately authored external holdout for broader claims.
Publishing these files does not make the original authored fixtures independent.

## Two modes and frozen inputs

`common_retrieval` uses the same resolved answer-model revision, answer prompt,
tokenizer, generation settings and 4,096-token evidence budget across all arms.
The budget includes visible source IDs, timestamps and citation overhead. Each
arm consumes only the same raw source documents. Backend summaries, extracted
facts, golds and another arm's outputs may not be passed to a different arm.

`tuned_pipeline` evaluates each arm's complete supported ingestion, storage,
retrieval, reranking and generation configuration. It has its own frozen declared
budgets and resolved models; complete pipeline costs are included. Development
data may be used for tuning both modes. Common retrieval isolates evidence quality;
tuned pipeline answers a different operational question and is reported separately.

Before releasing holdout content, commit a configuration-freeze receipt containing:
corpus manifest SHA-256; adapter and scorer commits; source/archive hashes;
resolved provider/model IDs; all generation/retrieval/rerank settings; evidence
and answer token budgets; concurrency; supported deadlines and cancellation;
container image/version/digests; host receipt; randomization seed; and exposure
attestations. Every field must be concrete. Missing fields block confirmatory
execution. No model alias counts as a resolved revision. No tuning or corrective
retry is permitted after release; preserve failures and start a new exploratory
experiment if a configuration must change.

All arms ingest the same split's complete source set in a fixed chronological
order (`available_from`, then `source_id`). Queries run in the same seeded shuffled
order, with arm order counterbalanced within cases. Source registries and gold
records are scorer-only. Case `source_ids` must not restrict retrieval or be given
to the answer model. Clean isolated stores prevent cross-split or cross-arm state.

## Scoring and statistical decision

Each case passes only if the structured answer has the correct answer/abstain
type, every required fact, no forbidden or unsupported fact, the exact query
timestamp, and source-supported citations satisfying availability and temporal
requirements. An abstention needs the prescribed reason and its source citation.
An empty answer, fabricated citation, stale answer, missing response, timeout or
failed run is a failure. Retain diagnostic dimensions separately; do not remove
failed cases from the denominator. The frozen evaluator defines exact scalar
matching and complete citation coverage before the holdout is opened.

Report paired case accuracy, all six category results, citation/temporal errors,
abstention performance, construction/retrieval/generation phase times and p50/p95
end-to-end latency. Keep common and tuned mode results separate. Use paired
stratified bootstrap with 10,000 replicates and seed `20261002`: sample ten case
indices with replacement inside each category, carry both arms' results for each
index, and compute the mean paired accuracy difference in percentage points.

The prospective challenger is Hindsight; ai-memory is the incumbent and
native files is the control. **Tuned pipeline is the primary comparison**;
common retrieval is diagnostic. Promotion requires Hindsight's paired point gain
to be at least **+5 percentage points** against **both** ai-memory and native files,
with each simultaneous decision interval's lower bound strictly greater than
zero, plus every lifecycle, representative-workload and blind cross-family gate
below. Ordinary paired 95% intervals are descriptive. No post hoc winner selection
from the three arms is allowed. A third predeclared contrast compares native
files against ai-memory. If native files beat both memory-backed answer paths
by the same point-gain and interval rule, recommend direct-file answers for the
tested query scope, subject to matching native operational evidence. This does
not retire memory capture or continuity: keep only the memory roles justified
by their separate observed behavior. No decision file changes a default.

There may be **one 60-case extension only**, with ten new cases per category,
unchanged configurations and independently sealed sources. An initial result is
inconclusive when a comparator's interval admits both no gain and a gain, or the
+5-point practical threshold remains uncertain; a conclusive regression does not
trigger an extension. Any operational or lifecycle failure blocks extension.
Stop at 120 total cases, pooling both batches for the final result. To keep
simultaneous 95% decision coverage across three predeclared pairwise contrasts
and two planned looks, Bonferroni allocates alpha 0.05/6 to each interval: use **99.1666667% paired
intervals** at each decision look, alongside descriptive 95% intervals. For the
same frozen 10,000 bootstrap draws, decision quantiles are 0.0041666667 and 0.9958333333;
descriptive quantiles are 0.025 and 0.975. Never select a favorable subset. The
extension must be externally authored or technically withheld from the tuning
executor and released against the same configuration freeze. It is not present
in this 72-case package. If unavailable, stop as inconclusive. This rule does not
permit retraining, a second extension or changing the decision rule after results.

Decision intervals entirely within ±5 percentage points are treated as practical ties and cannot
justify promotion on accuracy. Report complete cost, latency and operational
burden for ties; prefer the existing selection unless a separately authorized
decision supports a change. Unknown usage, account charge, cache accounting or
whole-task net savings remains unknown. Never sum overlapping counters.

## Gates after synthetic qualification

Promotion additionally requires a matching current control and representative
lifecycle/latency gates: capture; session end; consolidation; persistence and
reopen; compaction and fresh-session recall; source updates/conflict handling;
safe deletion; supported cancellation; process settlement; restart and recovery;
cross-client interoperability without duplicate capture; and scoped rollback.
Retain prior failures beside new runs and demonstrate the relevant negative
control. A fixture score cannot close these gates.

Run 20 real, authorized canary sessions spanning the affected workflow and two
isolated service restarts, with no unresolved lost memory, cross-project leakage,
duplicate capture, orphaned work or unsupported usage claims. Record real measured
latency/cost thresholds in the freeze receipt before canaries; an unset threshold
is an open gate. Keep sanitized receipts, not personal conversation histories.

Independent blind cross-family convergence must use surviving hosts, the frozen
comparison and preserved adverse evidence. Neither same-family reviews nor an
unreviewed peer run satisfies it. Host and source sync alone cannot promote a
selection. Final adoption remains a separate canonical maintained decision.

## Research provenance

[LongMemEval-V2, v1](https://arxiv.org/abs/2605.12493v1) inspires environment-state,
workflow and premise-awareness coverage. [Agent Memory: Characterization and
System Implications, v2](https://arxiv.org/abs/2606.06448v2) inspires separate
construction, retrieval and generation accounting. Their pages were checked on
2026-10-02. This corpus is not either paper's dataset, does not reproduce their
published methods, and yields no score comparable to those benchmarks.
