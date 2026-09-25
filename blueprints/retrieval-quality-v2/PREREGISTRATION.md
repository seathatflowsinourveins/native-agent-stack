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
