# U11: merit-neutral selection rules (design for review, 2026-10-01)

Status: proposed. Nothing in this record is implemented, and no prompt, verdict or acceptance record changes with it.
Owner of the files and of the implementing pull request: the foundation lane's coordinator (session
`sota-default-harness-setup`). Review: one cross-family read coordinated by the Codex catalog lane's root and one
Claude Opus read, then one repair round, as `docs/decisions/2026-10-01-definitive-sota-wsl-program.md` asks of a
design unit.

## Why

The user's rule of 2026-10-01 (decision 5 of the program record) says a layer's winner on the new distribution is
what the repositories' own quality supports, and that the source host's pins, installed state and integration holds
are not evidence for or against a repository. The user then asked why the architecture still showed a biased list.
Four rules in this repository's own tooling give the incumbent an advantage that the repositories' quality does not:

1. **The sweep's fit refuter puts the burden on the challenger.** `tools/sota-convergence/landscape-sweep/templates.json`
   (`fit`) refutes a proposal when it has "no concrete, evidence-backed gap versus the current winners", and says
   "Default to refuted=true when uncertain". A challenger has to prove a gap against the pick of record, and a tie or
   an open question counts against it.
2. **Discovery novelty and merit eligibility are one list.** `build_inputs.py` hands the workers `known_repositories`
   (winners, alternatives, catalog candidates, the baseline manifest) as already known, so discovery looks only for
   new names. That is right for discovery. Nothing else assembles the full field of known candidates for a merit
   judgment, so a known challenger is neither proposed again nor judged.
3. **A verdict can crown only an adopted candidate.** `tools/sota-convergence/lane_packets.py` (`build_candidate`)
   marks a candidate adopted when its catalog disposition is `selected` or `conditional`; a newcomer is never adopted;
   `record_verdicts.py` (`validate_lane_return`) and `scripts/landscape.py` (`lane_winner_components`) refuse any other
   winner key; and a lane return has no "undetermined" form, although `verdict_status` already allows `no_selection`.
4. **The evidence on record is asymmetric.** Native runs exist mostly for what the source host installed, so a rule that
   prefers the strongest evidence class prefers the incumbent. Fewer runs on record is not lower quality.

## Design

**A. Two contracts, kept apart.**
- *Discovery (novelty):* unchanged in purpose. It finds credible repositories that are not yet known. Surviving its
  refuters means "credible enough to enter the field", never "better than the pick of record"
  (`landscape-sweep/convert.py` already says survival does not mean beating the winner).
- *Merit (the full field):* per layer, a frozen eligible field: every candidate on record (the selection of record,
  the verdict selections, the alternatives, the catalog candidates, the second-family review's selections, the
  sweeps' survivors and the seeds), minus exclusions that each carry a reason from the selection principles (archived
  or stale under the maintenance rule, infeasible on the hosts, outside the requirement, a paid service without a
  demonstrated gap). Adoption is recorded as a fact about the source host and never decides eligibility. The field,
  its discovery coverage and its exclusions are frozen and hashed before any judgment.

**B. Fit refuter, version 2.** A new template version; the current templates and their pinned hashes stay for every
sweep already started (`tests/test_landscape_sweep_harness.py` pins both).
- Judge each proposal against the layer's requirement and the selection principles, not against the current winners.
- Three votes: `credible`, `not_credible` with the decisive reason, or `pending` when the evidence is unavailable or
  uncertain. `pending` is not a refutation, in the same way that unknown maintenance never refutes today.
- Blind and balanced: withhold which candidate the source host runs (the withholding of `lane_packets.py` is reused),
  shuffle candidate order, and swap positions in any pairwise judgment.

**C. Verdict lane contract, version 2.** A new contract version; the sealed 2026-09-22 wave and its rules stay.
- Eligible winner keys are the frozen field's candidates. `adopted` stays in the packet for bookkeeping and is withheld
  from the judges.
- A lane may return `undetermined`, recorded as `verdict_status` `no_selection` with `open_gaps` naming the deciding
  comparison.
- One bar for every candidate: a merit winner, incumbent or challenger, needs an executed comparison on the frozen
  tasks on record. Without one the lane returns `undetermined`, and the incumbent stays the selection of record, which
  is not a merit result.

**D. The comparisons that decide (program unit U5).**
- Freeze the objective, the tasks, the oracle, the resource budget and the quality criteria before any judging, and
  sample the tasks from the layer's real workload (OpenAI's evaluation guide lists "biased design" among its
  anti-patterns).
- Run each arm fresh at its current release, installed by its upstream commands. A fixture, a source review or a
  historical run never qualifies a version or a distribution it did not run on.
- Report uncertainty: paired differences on the shared tasks, clustered standard errors where tasks share a source, and
  a power estimate for the effect that would change the decision. Record `undetermined` when the interval includes no
  decisive difference or the run is underpowered.
- When a model judges, control position and length bias, and use a panel of judges from different model families.
- Run the arms as one evaluation set so that failed samples are retried and completed work is reused, as Inspect's
  eval sets do, and keep every failure with its usage.

**E. Inputs.** A sweep or verdict input carries the frozen field, not only the winners and alternatives, and the dated
acceptance context through an explicit field. The catalog lane found on 2026-10-01 that the generated inputs drop
`next_acceptance` from `catalogs/us-equities/runtime-target.json` because the builder's projection does not read it.

## Files the implementation touches (after review)

`tools/sota-convergence/landscape-sweep/templates.json` (fit v2 and its discover note), the fit vote schema,
`saturation_ledger.py` and `convert.py` (how `pending` counts), `build_inputs.py` (the field and the acceptance context),
`tests/test_landscape_sweep_harness.py` (new pinned hashes), `tools/sota-convergence/lane_packets.py`,
`tools/sota-convergence/lane-prompt.md`, `tools/sota-convergence/record_verdicts.py`, `scripts/landscape.py`, the lane
contract in `tools/sota-convergence/README.md`, and their tests. The implementation lands with failing tests first,
the Gate A owner's script check, and the trading lane owner's acknowledgement, because the verdict tooling covers the
trading rows.

## What stays untouched

The active workflow `wf_85f3021d-b4d` and its frozen inputs; the sealed 2026-09-22 verdict wave; the pinned prompt
hashes of sweeps already started; every acceptance contract and receipt. No candidate wins or loses by this record.

## Review question

Does this design remove the incumbent's advantage from discovery fit and from verdict eligibility while it keeps one
evidence bar for incumbents and challengers? Name any path where adoption status still changes eligibility, the burden
of proof or the order of judgment, and any rule that would let a merit claim stand without an executed comparison.

## Sources

- The user's rule: decision 5 of `docs/decisions/2026-10-01-definitive-sota-wsl-program.md`.
- Position, length and self-preference bias of model judges and their mitigations: Zheng et al. 2023, "Judging
  LLM-as-a-Judge with MT-Bench and Chatbot Arena", arXiv:2306.05685; Wang et al. 2023, "Large Language Models are not
  Fair Evaluators", arXiv:2305.17926; OpenAI, "Evaluation best practices",
  https://developers.openai.com/api/docs/guides/evaluation-best-practices (read 2026-10-01: position and verbosity
  bias, pairwise comparison, the "biased design" anti-pattern).
- Panels of judges: Verga et al. 2024, "Replacing Judges with Juries", arXiv:2404.18796.
- Uncertainty: Anthropic, "A statistical approach to model evaluations" (2024-11-19),
  https://www.anthropic.com/research/statistical-approach-to-model-evals, and the paper arXiv:2411.00640 (read
  2026-10-01: clustered standard errors, paired differences, power analysis).
- Retries and reuse across a set of evaluations: Inspect, `docs/eval-sets.qmd` at commit
  0321960a92aa52390413ce011d67ffb5962a2b11 (read 2026-10-01).
- This repository: `docs/convergence-architecture.md` and `docs/acceptance-evidence-policy.md`.
- The Codex catalog lane's root named the OpenAI, Anthropic and Inspect sources and the separation of discovery novelty
  from merit eligibility on 2026-10-01; they were read before they were cited here.

## Overturn

The review finds a rule that still gives adoption an advantage, or one that lets a merit claim stand without an
executed comparison; or a comparison shows that a rule here selects worse than the current one on the same frozen
tasks.
