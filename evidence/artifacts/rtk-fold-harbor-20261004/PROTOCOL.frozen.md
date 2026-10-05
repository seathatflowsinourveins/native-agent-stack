# RTK fold phase 2: adjudication protocol

Written 2026-10-05, before any label exists, by the coordinator (session identifier omitted). The preregistration ("Metrics and adjudication") requires a reviewer to inspect every original trajectory call and fill every CSV row with 0/1. It does not fix who the reviewer is or how disagreements are resolved, so this protocol fixes both before labelling.

**Status.** Additions to the preregistered single-reviewer procedure are labelled as such below. Nothing here changes the metric definition, the analysis, the Holm family, the stopping rule or the overturn rule.

## Inputs (frozen by hash in batches.json)

- **Source packet:** `phase2-review.json`, from `review_packet.py`. It is blinded: no arm labels, no verifier rewards and no arm manifests. Exposure can still leak (for example, an `RTK.md` read), as the preregistration says; the prereg accepts that perfect blinding is impossible.
- **Batches:** six batches of 12 trials, made by a deterministic split (sorted by trial id, every sixth trial). They come in two forms:
  - `batch-<i>-of-6.json`, the raw form;
  - `review-batch-<i>-of-6.md`, an ordered per-trial rendering.
- **What a rendering contains, per action:**
  - the preregistered metric definition, verbatim;
  - the parsed commands with their cwd;
  - the agent's original tool-call arguments, always included, because code-mode JavaScript can build commands at run time;
  - the observation. Long text is cut in the middle, with the cut marked; error, exit and missing-path lines from the cut part are kept verbatim;
  - measure.py's automatic candidates, marked as non-binding hints.
- **The rows to label:** the 264 `(trial, call_id)` rows of `phase2-measures.adjudications.csv`. They equal the packet's actions one to one, checked by `split_review.py`.

## Primary reviewer (the preregistered single reviewer)

- **Who:** Claude Opus 5.5 at effort max, agent type `evidence-reviewer`, one fresh agent per batch. The batches run as two waves of three.
- **Family:** the trials ran Codex (GPT) agents, so the primary reviewer is from another model family.
- **What each agent may read:** only its own `review-batch-<i>-of-6.md`, plus `batch-<i>-of-6.json` for lookup. It must not open `jobs/`, `logs/`, `cfg/`, `arms/`, `tasks/`, `schedule.*`, `frozen-copy/`, `runtime/`, `checks/` or any other file in this directory. It must neither infer nor report an arm.
- **What it labels:** every row exactly once, 0 or 1, under the metric text only.
  - **A positive** must record: the offending path, a verbatim observation excerpt, the rationale, and whether it repeats an earlier wrong path in the same trial.
  - **Unknown:** a row the evidence cannot decide goes to `unknown`, with the reason.
- **Code check:** the labels must cover the batch's rows exactly once, or the batch is re-run.

## Cross-family audit (addition to the preregistered procedure)

- **Who:** GPT-6.1 Sol at max, through the packaged SDK worker, read-only.
- **Which rows:** every primary positive, plus a seeded 20% sample of primary negatives (Python `random.Random(20261004)` over the negatives sorted by `(trial, call_id)`, sample size `ceil(0.2 × negatives)`).
- **How:** the auditor labels each audit row independently from the same rendered text. It does not see the primary labels.
- **Agreement:** reported separately for the positives and for the negative sample.

## Disagreements

- **Resolution:** a row where the primary and the auditor disagree goes to a third, fresh Claude Opus 5.5 reader. That reader is blind to both labels and sees only that row's trial rendering and the metric text. The majority of the three labels stands.
- **Low agreement on the negative sample:** if agreement is below 85%, the GPT audit extends to all remaining negatives, and the majority rule above applies to every new disagreement.
- **Rows that stay `unknown`:** a row is `unknown` when any reader marks it so and the three-way reading does not settle it. It stays `unknown`, which blocks scoring as the preregistration requires. The report lists such rows.

## After labelling

- **Fill the CSV.** Fill `phase2-measures.adjudications.csv` with `wrong_path_action`, `reviewer` (the reader or readers whose label stands) and `notes` (the offending path and rationale for each positive).
- **Re-run the preregistered commands:**
  1. `measure.py --jobs jobs --phase p2 --output phase2-adjudicated.json --adjudications phase2-measures.adjudications.csv`, which must report `adjudicated: true`;
  2. `uv run --frozen --script analyze.py phase2-adjudicated.json phase2-analysis.json`.
- **Report.** Report arm A's adjudicated wrong-path count separately from the paired tests. Either one alone triggers the overturn rule.
