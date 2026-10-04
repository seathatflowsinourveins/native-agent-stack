# Retrieval quality v2: preregistration

Drafted 2026-09-25, before any arm has been run. This document and
[`queries.json`](queries.json) (sha256 `4d0a0eaf0f6fc48b899f6139e7e98a6c1edf4798b1f17ddfbf5ec3e1cc6c5c7a`)
were written by an independent query author who did not run `qmd search`,
`qmd query`, SocratiCode, or any embedding/rerank call while authoring them.
The 30 queries and their graded relevance judgments were produced by reading
the corpus directly (`Read`/`grep`/`cat`), never by inspecting what any
retrieval system already returns, so the query set is not tuned to Arm A, Arm
B, or the closed v1 fixture. This addresses the gap recorded at
`catalogs/us-equities/convergence-review.json` (`retrieval-quality`,
`measured_gap`: "New held-out queries and relevance judgments for scoped
query-craft/hybrid comparison") and `catalogs/landscape/foundation.json`
(`document-retrieval`, `open_gaps`: "repeated warm/cold latency and
representative corpus recall remain unestablished").

## Status: nothing has run

No index has been built for v2, no query has been issued against any arm, and
no score in this document is measured. Every number below (the +0.05 gain
threshold, the bootstrap iteration count, `k=10`) is a **decision rule
parameter**, not a result. The only artifact that exists is the sealed query
set itself.

## Relationship to the v1 fixture

The v1 fixture (`blueprints/us-equities/retrieval-evaluation/fixture.json`,
12 queries) is **not held out any more**: its questions and gold files are
public and were read while designing v1's own report. None of the 30 queries
in `queries.json` reuse or paraphrase a v1 query; each targets a fact a v1
query did not test, even on a file v1 also used (for example, v1's
`alpaca-entitlement` query tests the LEAN Alpaca adapter's `ValidateSubscription`
entitlement check in `engine/resolution.md`, while this set's `kw-02` tests a
different, unrelated fact in the same file: which CVE and replacement package
resolved the DotNetZip advisory). A comparison run may still replay the v1
fixture as a **separate, non-blinded reference point**, but only v2's 30
queries count toward the decision rule below.

## Corpus and its pin

`full-corpus-manifest.json` pins all 33 files at repository commit `bfd03bc`.
This preregistration instead pins them at the query-authoring worktree's HEAD,
commit `3e4054d02eac06ae8ac995c5e96fe8a75c0824c8` on branch
`claude/retrieval-quality-prereg-20260925` (based on `origin/main`): 19 of the
33 files have changed since `bfd03bc` and 14 are byte-identical (verified by
comparing every file's current sha256 against `full-corpus-manifest.json`'s
`indexed_content_sha256`; the unchanged 14 are the observability trio's
`collector/README.md`/`desktop-restart.md`/`session-e2e.md`, both `deerflow`
result/task files plus its `README.md`, `engine/resolution.md`,
`financial-data/README.md`, `gap-resolution.md`, `hosting.md`,
`hosting/backup/README.md`, `routing/README.md`, `workers/research-task.md`,
and `catalogs/us-equities/source-followup.md`). `queries.json`'s own
`corpus` array carries the exact sha256 and byte count of all 33 files at this
pin; a runner must re-verify every hash against the checkout it actually
indexes before trusting a result, and must not silently substitute the
`bfd03bc` bytes for a file this pin marks changed.

**Index construction (before either arm runs):** build a fresh index owned by
this comparison, never the host's shared `~/.cache/qmd` index or config.
Point `HOME`/`XDG_*` at a scratch directory so QMD's schema init, model
lookup and any config sync land there instead. Materialize exactly the 33
pinned files (not a directory glob, since `blueprints/us-equities/**/*.md`
and `catalogs/us-equities/**/*.md` now contain far more than 33 files at
current HEAD) into a private staging tree that preserves each file's
`repository_path`, by extracting the pinned blob content directly rather than
copying today's working tree (which could have drifted since this document
was sealed):

```sh
STAGE="$SCRATCH_HOME/corpus-stage"   # under the run's own scratch dir, never the shared checkout
mkdir -p "$STAGE"
python3 - "$STACK_REPO" "$STAGE" <<'PY'
import json, pathlib, subprocess, sys, hashlib
repo, stage = sys.argv[1], pathlib.Path(sys.argv[2])
pin = json.load(open(f"{repo}/blueprints/retrieval-quality-v2/queries.json"))
commit = pin["corpus_commit"]
for doc in pin["corpus"]:
    blob = subprocess.run(
        ["git", "-C", repo, "show", f"{commit}:{doc['path']}"],
        check=True, capture_output=True,
    ).stdout
    assert hashlib.sha256(blob).hexdigest() == doc["sha256"], doc["path"]
    dest = stage / doc["path"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)
PY
qmd --index retrieval-quality-v2 collection add "$STAGE/blueprints/us-equities" \
  --name rqv2-foundation --mask '**/*.md'
qmd --index retrieval-quality-v2 collection add "$STAGE/catalogs/us-equities" \
  --name rqv2-catalog --mask '**/*.md'
qmd --index retrieval-quality-v2 collection add "$STAGE/observability" \
  --name rqv2-observability --mask '**/*.md'
qmd --index retrieval-quality-v2 update
```

A failed hash assertion for any of the 33 files stops index construction; it
is not skipped or waved through. Both arms query this same frozen index at
`-n 10` (QMD's own default results cap; the corpus is 33 documents, far below
the native candidate limit, so candidate starvation is not a concern here
either). Building the index makes zero provider or embedding-download calls
by itself; Arm B's local embedding/rerank models are a separate, explicit
step below.

## Arms

- **Arm A — BM25 lexical.** `qmd --index retrieval-quality-v2 search "<query>"
  -n 10 --format json`, run once per query, no collection filter (all 33
  documents are in scope; unlike the v1 fixture there is no 18-document
  eligibility subset here). This is QMD 2.8.3's existing default lane
  (`catalogs/us-equities/foundation-memory.md`: "Current profile is BM25
  only"), so Arm A needs no new model download.
- **Arm B — hybrid.** `qmd --index retrieval-quality-v2 query "<query>" -n 10
  --format json` (QMD's hybrid/vector path) against the **same** frozen
  index, on CPU (`NODE_LLAMA_CPP_GPU=false` or this build's documented CPU
  switch; the GPU stays reserved and lightly used per the run's own hard
  rules). Before Arm B runs, the runner must resolve QMD 2.8.3's actual
  hybrid-mode requirement (`qmd query --help`, `qmd skill show`, or the
  installed module source) for which embedding and reranker models it loads,
  pin each one's exact HF repository and revision, and record those pins in
  the run's receipt next to `queries.json`'s sha256. This preregistration
  does not itself select or download that model: `foundation-memory.md`
  records that "semantic query/reranking models are not downloaded" under
  the current profile, and "new HF models are not automatically compatible
  with QMD GGUF/pooling contracts," so an unverified guess at a revision here
  would not bind the actual run. Arm B fails closed (see below) if that pin
  cannot be resolved and recorded before the first query is issued.
- **Arm C — SocratiCode.** Out of scope for this comparison, per this task's
  own instructions. SocratiCode indexes code via a separate Nemotron/Qdrant
  pipeline, not QMD's Markdown BM25/hybrid lanes, and this comparison's
  independent-query-author role explicitly excludes running it.

Both arms query the identical frozen index built above; only the QMD
subcommand (and, for B, the loaded models) differs. Neither arm may be
re-run with a changed query, a changed `-n`, or a rebuilt index after seeing
its own partial results; a change of that kind requires a new dated
amendment to this file, in the open style of
`evidence/artifacts/blind-comparison-20260923/PREREGISTRATION.md`'s
Amendment 1, not a silent edit.

## Metrics

Computed per query against that query's own `relevance` array in
`queries.json` (grade 2 = directly answers, grade 1 = partially relevant,
grade 0 = every other corpus path, by omission), then averaged over all 30
queries for each arm. A query an arm fails to answer at all (error, timeout,
or malformed/unparseable output) scores 0 on every metric for that query and
that arm; it is retained in the average, never dropped, consistent with
`docs/acceptance-evidence-policy.md`.

- **nDCG@10** (graded gains). For each query, `DCG@10 = sum_{i=1..10} (2^grade_i
  - 1) / log2(i + 1)` over the top 10 returned results (grade 0 for any
  returned path not in the query's `relevance` array, and for unfilled ranks
  when fewer than 10 results are returned). `IDCG@10` is `DCG@10` of the
  query's own relevance grades sorted descending (i.e., every grade-2 file
  first, then every grade-1 file, capped at 10 total). `nDCG@10 = DCG@10 /
  IDCG@10`. Every query has at least one grade-2 file, so `IDCG@10 > 0`
  always and no query is excluded from the average for this reason.
- **recall@5 of grade-2 files.** For each query, the fraction of that query's
  *distinct* grade-2 paths that appear anywhere in the top 5 returned
  results. 28 of the 30 queries have exactly one grade-2 file, so recall@5 is
  0 or 1 for those; `nl-10` has two grade-2 files, so its recall@5 is 0, 0.5,
  or 1.
- **MRR.** Reciprocal rank (`1/rank` of the first hit, 0 if none appears in
  the top 10) of the first returned result with grade &ge; 1 (grade 2 or
  grade 1 both count, matching MRR's usual "first relevant result" reading;
  this is deliberately more permissive than recall@5's grade-2-only
  criterion, and the two metrics are not expected to agree on every query).

All three metrics are computed by a script committed alongside the run's
receipt from the arms' own returned JSON, never eyeballed or asserted by an
agent from memory.

## Decision rule

Arm B is selected over Arm A only if **both** hold, over the same 30 queries:

1. `mean(nDCG@10, B) - mean(nDCG@10, A) >= 0.05`.
2. A paired bootstrap 95% CI of that per-query nDCG@10 difference excludes 0:
   resample the 30 `(A_i, B_i)` nDCG@10 pairs with replacement 10,000 times,
   compute `mean(B) - mean(A)` on each resample, and take the resample
   distribution's 2.5th/97.5th percentiles. The interval's lower bound must
   be `> 0`.

If either condition fails, **BM25 (Arm A) stays the default**; QMD's current
profile is not disturbed by an inconclusive or negative result. recall@5 and
MRR are reported for both arms regardless of which one wins, as secondary,
non-gating evidence (for example, a hybrid arm that wins on nDCG@10 by
promoting more grade-1 partial matches without improving grade-2 recall@5
would be flagged in the writeup, not hidden). No threshold in this section
may be loosened after either arm's scores are known; a materially different
bar requires a new, separately dated preregistration, not an edit to this
one, mirroring `docs/decisions/2026-09-23-max-effort-default.md`'s existing
"probes and overturn conditions" pattern for this repository.

## What counts as failure

- Index construction fails closed on the first hash mismatch (see above); no
  arm runs against an unverified index.
- Arm B fails closed, and is reported as **not evaluated** (not as a 0 score
  standing in for "BM25 wins"), if its embedding/reranker model pin cannot be
  resolved and recorded, or if the pinned model cannot actually be loaded on
  CPU. A not-evaluated Arm B cannot satisfy the decision rule, so BM25 stays
  the default in that case too, but the two outcomes ("B was tried and lost"
  vs. "B could not be tried") must be reported as distinct.
- A query that errors or times out against a working arm counts as a 0 for
  that query on every metric, per the Metrics section; it is not retried
  silently, excluded from the mean, or backfilled from the other arm's
  result.
- Reusing this run's own query text, or any result it already returned, to
  hand-tune a later query set voids that later set's claim to being
  held out, in the same sense this document already voids the v1 fixture for
  future comparisons.

## Sealing

`queries.json` sha256: `4d0a0eaf0f6fc48b899f6139e7e98a6c1edf4798b1f17ddfbf5ec3e1cc6c5c7a`.
A separate query author wrote both files and recorded this sha256. The author ran no retrieval
system, embedding call or model query. Its workflow step finished before the runner step started:
in workflow run `wf_eaf5338d-556`, the journal records the query author's result before the
runner's start. The runner re-hashed `queries.json` and found it equal before any `qmd` call
(`seal` in `results-20260925.json`). Both files are first committed together with the results in
one pull request, so git history alone does not show this order; the workflow journal does.

*Correction, 2026-09-25, after the run.* An earlier sentence here said both files were "committed
to this worktree … before any `qmd search`". Workers in that run could not commit, so the
sentence was false, and the independent review caught it. The text above replaces it. No query,
judgment, metric or decision rule changed, and `queries.json` is byte-identical to its sealed
sha256. A future runner
must re-hash `queries.json` before use and treat a mismatch as grounds to
stop, not proceed with a silently different query set.

*Correction, 2026-09-26.* The paragraph above cites a workflow journal that is not in this
repository. The `seal.ordering_evidence` field of `results-20260925.json` only repeats it; that
field was added to the receipt by hand after the run, and `run.py` never wrote it. A matching
sha256 shows that the sealed bytes did not change. It does not show when they were sealed. A
worker that neither wrote the queries nor ran the comparison has since bound the order to the
native records, in the sanitized extract [`chronology-20260926.json`](chronology-20260926.json):

- In the append-only journal of workflow run `wf_eaf5338d-556`, line 4 is the query author's
  result, which reports the sealed `queries.json` hash, and line 5 is the runner's start.
- The run record puts the author's completion at 2026-09-25T20:20:49.172Z and the runner's start
  at 20:20:50.105Z. The runner's first `qmd` command came at 20:21:33.658Z.
- The author's transcript contains no qmd, SocratiCode or model-endpoint invocation.

Those records hold full prompts, outputs and host paths, so they stay private on the authoring
host; the extract lists their sha256 values. Treat the chronology as an independent observation
that can be repeated only on that host, not as publicly verifiable history.

## Amendment 1 (2026-09-26): one re-run with a repaired runner

An independent cross-family review of the merged pull request (#293) found defects in `run.py`,
not in this protocol:

- it passed the caller's `INDEX_PATH` and `QMD_CONFIG_DIR` to qmd, so index and configuration
  writes could reach shared host state;
- it went on to Arm B when a model's HF revision was unresolved;
- it credited hits whose docid did not match the pinned content hash;
- wrong-shaped JSON either aborted the whole run or counted as a clean empty result;
- a timed-out `qmd pull` or `qmd embed` crashed the run;
- every run overwrote `results-20260925.json`;
- it discarded qmd's own output after scoring it.

The Arms section forbids re-running an arm on a rebuilt index without a dated amendment. This
amendment allows exactly one re-run with the repaired runner, on these terms:

- The sealed `queries.json` is unchanged and its seal is re-verified. The 33 pinned files and
  their commit, `-n 10`, the Metrics, the Decision rule, the bootstrap seed (20260925) and the
  10,000 resamples are unchanged. Arm B runs on CPU.
- The index is rebuilt from the pinned bytes, and the models are pulled afresh into a new scratch
  HOME. A model's revision now counts as pinned only when Hugging Face lists the pulled file at
  that revision with the same sha256 and size; otherwise Arm B is not evaluated.
- After both arms, the runner also runs QMD's own benchmark command (`qmd bench`) on the same
  index, with a fixture derived from `queries.json`. It is corroboration only and never enters the
  Decision rule.
- The re-run writes new files (`results-<run-id>.json`, `native-<run-id>.json`,
  `report-<run-id>.md`). `results-20260925.json` stays unchanged as history.
- Both runs are reported. If they reach different decisions, the writeup reports a failed
  replication instead of choosing between them, and QMD's BM25-only profile is not changed on the
  strength of either run.

This amendment was written before the re-run started. The re-run's receipt records the sha256 of
this file as read before its first query (`seal.preregistration_sha256`).

## Known limitations

- 30 queries against 33 short documents is a small-sample comparison; the
  bootstrap CI is the intended safeguard against reading noise as a real
  gain, not a substitute for a larger corpus.
- The query author read every document's full text before writing questions,
  which is necessary for honest relevance judgments but means the judgments
  reflect one reader's understanding of "directly answers" vs. "partially
  relevant," not an adjudicated multi-rater agreement. A future round could
  add a second independent judge and report agreement, as
  `catalogs/us-equities/convergence-review.json`'s `agreement: "disagree"`
  pattern already does for the document-retrieval layer.
- This protocol measures retrieval quality only (nDCG@10, recall@5, MRR). It
  does not measure end-to-end answer quality, latency, or provider-token
  cost; those remain separate, unestablished claims per
  `catalogs/landscape/foundation.json`'s `document-retrieval` `open_gaps`.
- The corpus is pinned at this worktree's HEAD, not at `origin/main` at
  merge time; if other work advances `main` before this comparison runs, the
  runner must re-verify every one of the 33 sha256 values against the
  checkout it actually indexes (see Corpus and its pin) rather than assume
  this pin is still current.

## Correction, 2026-09-26, added after the re-run started

The first 18,013 bytes of this file, everything above this section, are the version whose sha256
(`916aac5ab50402df454e13936f84ef3ea9d194b2f545bac68580b839949fb938`) the first 2026-09-26 re-run
attempt recorded before its first query, as `seal.preregistration_sha256` in
`results-20260926T022931Z.json` (that attempt was stopped; see Amendment 2). This section was
appended afterwards.

The native records behind [`chronology-20260926.json`](chronology-20260926.json) also show that
the Sealing section's "before any `qmd` call" holds only for `run.py`'s official invocation at
2026-09-25T20:41:42Z. While writing `run.py`, the 2026-09-25 runner sent sealed queries to qmd by
hand: `kw-02` through `search` (20:27:27Z) and through hybrid `query` (20:30:10Z) on an
exploration index, and `nl-01`, `pa-01` and `nl-05` through `search` (20:39Z). It also ran
`run.py` twice with `--skip-arm-b` (20:38:36Z and 20:41:16Z), so it saw Arm A's results for all 30
queries twice before the official run, and those two receipts were not kept. The Arms section
required a dated amendment before an arm was re-run on a rebuilt index after its results had been
seen, and none was filed. None of these calls could change a query, a judgment, `-n`, a metric or
the Decision rule, which the seal and this document fix, and `run.py` gives Arm A no model or
setting to tune. The deviation is recorded here so that it is not hidden; the extract lists every
call.

The 2026-09-26 worker also sent Arm A's 30 queries through `qmd search` once before the re-run,
in a smoke test of the repaired runner with `--skip-arm-b` whose output was not kept; Arm A's
2026-09-25 results were already published. It sent no hybrid `query` outside the re-run itself.

## Amendment 2 (2026-09-26): the re-run is restarted once with a longer hang guard

The re-run allowed by Amendment 1 started at 2026-09-26T02:29:31Z (`results-`, `native-` and
`report-20260926T022931Z`). Arm A completed. Arm B's first five queries took 70 to 105 seconds
each, against 33 to 66 seconds on 2026-09-25, while the host carried unrelated load, and query
`nl-06` reached `run.py`'s 240-second per-query limit and was killed. That limit is the runner's
hang guard, not a parameter of this protocol. The worker stopped the attempt with SIGINT at
02:45:00Z, before any Arm B score had been computed. `run.py` then wrote the three files named
above; their status is `started` because the interrupt ended the run before it set a final status.
They are kept as a failed attempt and contribute no Arm B score and no decision.

The re-run is restarted once, in a new scratch HOME, with `--arm-b-query-timeout 1800`. Nothing
else changes: the same `run.py` (sha256
`efba31d53c4a36ac482e71d796146d600c76299952055c72005b5b27196f6004`), the sealed queries, the
pinned corpus, `-n 10`, the Metrics, the Decision rule, the seed and the resample count.
Amendment 1's reporting rule applies to the restart unchanged. The restart's receipt records the
sha256 of this file, including this amendment, as read before its first query.

## Erratum, 2026-09-26, added after the restart started

The first 21,129 bytes of this file, everything above this section, are the version whose sha256
the restart recorded before its first query
(`41e0ec0cf135df481ef97a5d24625c179beeee4c54ca50694d081cb52108efb5`, as
`seal.preregistration_sha256` in `results-20260926T024558Z.json`). In Amendment 2, "before any
Arm B score had been computed" should read "before any Arm B score had been written or seen":
`run.py` scores each query in memory as it completes, so the first five queries' scores existed
in memory and were discarded unread when the attempt stopped.

## Correction, 2026-09-26, added after the review of the repaired runner

The first 21,747 bytes of this file, everything above this section, are the version that an
independent review of the repaired `run.py` read (sha256
`637a0c0b10352abd7ab0368c7ef3ff444ed14b9113ad7f9480aa039b5e315229`). This section was appended
afterwards. The review found three passages above incomplete.

**Amendment 1's response rule.** Amendment 1 says the Metrics are unchanged and describes the fix
only as no longer crediting hits whose docid did not match. The repaired runner applies a stricter
rule, which Amendment 1 should have stated: when even one of a query's top 10 hits cannot be
verified against the pinned corpus, `run.py` rejects that query's whole response. A hit cannot be
verified when its collection or path is not one of the 33 pinned files, when its docid is not the
first six hex characters of that file's pinned sha256, or when it names an index other than the
run's own; a hit without an `?index=` parameter is accepted. A rejected response scores 0 on
nDCG@10, recall@5 and MRR, keeps no ranked paths, stays in the arm's mean and is recorded as an
error that lists the rejected hits, the same as an error, a timeout or malformed output under
Metrics. The 2026-09-25 runner instead kept the query's other hits, scored a hit outside the
pinned corpus as grade 0 at its rank, as the Metrics text describes, and credited a hit whose
docid did not match its pin. No reported result depends on the difference: none of the 60
responses scored in the restart (`results-20260926T024558Z.json`) or the 30 Arm A responses scored
in the stopped attempt had a rejected hit, and every hit either attempt received names
`?index=retrieval-quality-v2`.

**The stopped attempt.** Amendment 2's account of attempt `20260926T022931Z` is incomplete. Its
receipt has status `started`, and its Arm B entry reads `not_run` with no reason, which its report
shows as "not run" in every row: the words the protocol uses for an Arm B that failed closed. In
fact the attempt pulled and pinned the three models, embedded the index and ran Arm B queries
`nl-01` to `nl-06` (`nl-06` timed out after 240.6 s), and its native file keeps those calls. It does
not keep the call that was running when SIGINT arrived. Arm B's phase lasted 793.6 s from
02:31:47.220Z, so `nl-07` had been running for about 102 s after `nl-06` ended at 02:43:18.992Z,
and `run.py` efba31d5 recorded a call only after the call returned. Six per-query results existed
in memory when the attempt stopped, not five: scores for `nl-01` to `nl-05` and the zero of
`nl-06`'s timeout. That runner killed the qmd process group on SIGINT, but it had no handler for
SIGTERM or SIGHUP, so either signal would have ended it without writing the native file or the
report, and would have left the running qmd call behind in its own session.

The committed `run.py` now handles SIGINT, SIGTERM and SIGHUP (its "Interrupts" note): it kills
the qmd process group in flight, keeps that call's record with its partial output, marks the arm
`interrupted` and the run `aborted_interrupted`, and writes all three outputs. It also reads the
ETag that QMD caches for each model from the file QMD actually writes. Both changes came after
both 2026-09-26 receipts, which `run.py` efba31d5 wrote and which are kept unchanged;
[`run-efba31d5.patch`](run-efba31d5.patch) turns the committed `run.py` back into that file, byte
for byte. Neither change touches how a response is parsed, verified or scored, the bootstrap or
the Decision rule.

**The chronology extract.** [`chronology-20260926.json`](chronology-20260926.json) records
`observed_at_utc` 2026-09-26T02:38:37Z, nine minutes after attempt 1 hashed a version of this file
whose first correction already cited the extract (02:29:31Z). The committed extract is the one
generated at 02:38:37Z. Whether an earlier generation existed when this file first cited it, and
how it differed, was not recorded.

**Checks with the committed runner.** While fixing these defects, the worker ran the committed
`run.py` three more times against the real qmd, all with `--skip-native-bench`: once with decoy
`INDEX_PATH` and `QMD_CONFIG_DIR` values and `--skip-arm-b`, once stopped by SIGTERM during Arm A
with `--skip-arm-b`, and once stopped by SIGTERM during Arm B's `qmd pull`. They sent Arm A's
sealed queries through `qmd search` again, after Arm A's results had been published, sent no
hybrid `query` and loaded no model. Their outputs stayed in scratch;
[`repair-review-20260926.json`](repair-review-20260926.json) summarizes them. None of this changes
a query, a judgment, `-n`, a metric, the Decision rule or a reported result.

## Note, 2026-09-26, added after the final review of the repaired runner

The first 26,446 bytes of this file, everything above this section, are the version the final
review read (sha256 `cc44d28662869f174045fc9ffb47d71c7d6bb206087840ac049d56ebed236a8a`). This
section was appended afterwards. In the section above, "the committed `run.py`" means `run.py`
0792745e (sha256 `0792745e7262dfed2488e50b090560598582f523a1ebfdb76d998e539a490ad7`), which
[`run-efba31d5.patch`](run-efba31d5.patch) turns into efba31d5 and which ran the three checks
against the real qmd. Those checks' outputs and drivers are now committed in
[`repair-review-20260926/`](repair-review-20260926/).

`run.py` has since become `7a04a37842674b9494e3cb37b2915c5269847445d437e63a4192ebe0ed32ecd1`, and
[`restore-0792745e.patch`](restore-0792745e.patch) turns it back into 0792745e. The change records
empty or incomplete `qmd bench` output as `incomplete` instead of completed. It sanitizes the
reasons recorded for rejected hits and the other strings a receipt copies from qmd's output. It
also corrects the interruption bookkeeping: the receipt names the qmd call that was running when a
stop signal arrived apart from any call the stop cut short, records the decision's limitations
before the benchmark starts, and records a failure that follows a stop together with the stop. It
does not change how a response is parsed, verified or scored, the bootstrap or the Decision rule,
and the new `run.py` has made no run against the real qmd. No query, judgment, `-n`, metric,
Decision rule or reported result changes.
