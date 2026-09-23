# Preregistration: blind comparison of two implementations (2026-09-23)

Written before any arm is evaluated. Arms carry opaque labels; the label key is sealed in
SEALED-KEY.json and is not given to any judge or refuter.

## Comparisons
- `catalog-automation-20260923`: arms `arm-3d8f2a61`, `arm-b94c07e5` (spec: spec-catalog.md)
- `agentlab-automation-20260923`: arms `arm-58d9c4b7`, `arm-e21a6f03` (spec: spec-agent-lab.md)

One arm per comparison is the incumbent: it is already merged. The protocol files name it only by its label.

## Metrics (per arm)
- `defect_weight`, lower is better. Computed as 10 × confirmed_high + 3 × confirmed_medium + 1 × confirmed_low.
  - A defect is *confirmed* when a single-arm reviewer (who sees only that arm) reports it, and
    an independent refuter reading the original source fails to refute it. The refuter defaults to
    refuted=true when uncertain.
  - The workflow script computes the value deterministically.
- `battery_pass_rate`, higher is better. The passed fraction of the applicable checks in the fixed
  battery script (battery_catalog.py / battery_agentlab.py), run identically on each arm's
  checkout. Harness errors count as not applicable and are reported.
- `requirements_met_rate`, higher is better. Computed as (met + 0.5 × partial) / applicable over
  the shared requirement list in the spec, as graded by the single-arm reviewer.
- `own_suite_pass`, 1 or 0. It is 1 when the arm's own acceptance commands, as listed in the
  battery, all exit 0 at its head.

## Closure (computed by tools/compare/closure.mjs, never by an agent)
- The challenger overturns the incumbent only if **all** of these hold:
  - defect_weight(challenger) < defect_weight(incumbent)
  - battery_pass_rate(challenger) >= battery_pass_rate(incumbent)
  - requirements_met_rate(challenger) >= requirements_met_rate(incumbent)
  - own_suite_pass(challenger) >= own_suite_pass(incumbent)
- Otherwise the incumbent is retained.
- A missing metric means insufficient evidence, and the incumbent is retained.

## Grafting (independent of closure)
- Every confirmed high or medium defect in the winning arm gets fixed in a follow-up PR, as long
  as the losing arm does not share that defect.
- Every battery check the winning arm fails, where the loser passes, is also fixed in that PR.

## Known limitation
The battery was authored by the coordinator, who had already seen earlier review findings on both
arms (for example the OSV `-e` path and the zizmor token scope). The checks are therefore derived
from known failure modes, not blind to them.

## Amendment 1 (2026-09-23, after run wf_40347d59-2e8, before re-judging)

The completeness critic and the refuters flagged four problems in that run: a leak, two harness
defects and one missing output. Metrics, thresholds and the closure rule are **unchanged**. Only
these things changed:
- **Neutral protocol ids.** The ids become `cmp-a-20260923` (catalog) and `cmp-b-20260923`
  (agent-lab). The first agent-lab id contained a repository name, so 3 of 3 refuters flagged a
  leak and the publication gate blocked it.
- **Harness fix, same-file copy.** `wfemu.py`'s download-artifact model raised SameFileError when
  the artifact path already equalled the download destination. That wrongly made K05/K06 not
  applicable (K05 for one arm, K06 for both).
- **Harness fixes, agent-lab false negatives.** All three disadvantaged the challenger.
  - K23: the job emulation now sets `RUNNER_TEMP` and `GITHUB_ENV` and carries `GITHUB_ENV` writes
    between steps, as the hosted runner does.
  - K27: the check now also accepts an in-CI `diff -r` of the two skills directories.
  - K28: the check now accepts "squash" plus "pull request"/"PR", not only the literal
    `gh pr merge`.
- **Frozen outputs for `own_suite_pass`.** The packet now carries each acceptance command's exit
  code as anonymised codes C1..Cn.

The single-arm reviews and the defect refutations are reused unchanged from run wf_40347d59-2e8.
The batteries are re-run by an independent child with harness v2.
