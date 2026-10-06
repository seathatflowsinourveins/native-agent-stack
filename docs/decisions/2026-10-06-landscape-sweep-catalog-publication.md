# Publish the October 6 landscape assessments

Date: 2026-10-06. This decision publishes two completed foundation sweeps as
catalog assessments. It serves the north-star research and historical simulation
by preserving the alternatives, exclusions and comparisons needed for later
foundation decisions. It changes no installation, runtime pin or native
acceptance status.

## Comparison and decision

Use the existing landscape-sweep publication steps independently for each
sweep, with two dated manifests in one PR. Combining their lane objects into one
manifest would require inventing merge semantics for the singular completeness
critic. The native builder accepts separate output paths and IDs; the saturation
ledger accepts separate registered manifests on the same date.

| Sweep | Workflow | Foundation layers | Proposed | Survived | Refuted |
| --- | --- | ---: | ---: | ---: | ---: |
| Runtimes | `wf_eed0e74b-ba4` | 7 | 102 | 22 | 80 |
| Roles | `wf_dd41894e-66a` | 4 | 59 | 17 | 42 |

The runtime layers are agent SDKs, workers, isolation, scheduling and
supervision, hosting services, MCP surfaces, and observation and inference.
The role layers are instructions and skills, native clients, Git and GitHub
automation, and quality evaluation. Neither sweep adds a trading decision.

The surviving assessments retain these explicit catalog dispositions:

| Sweep | `targeted_candidate` | `keep_but_compare` | `not_adopted_confirmed` |
| --- | ---: | ---: | ---: |
| Runtimes | 9 | 7 | 6 |
| Roles | 11 | 2 | 4 |

Survival means the proposed assessment withstood the recorded fact and fit
refutations. It includes accepted negative assessments: `batrachianai/toad`
remains `not_adopted_confirmed`, with the returned maintenance exclusion.
`gethamster/horde` retains its “TOO NEW TO ASSESS (<90 days)” warning. A surviving
assessment does not qualify a tool for installation or native use.

Each candidate's comparison, verdict and supporting returned evidence are
retained in `foundation[].candidates[]` in the two manifests. The field
`disposition` gives the verdict; `demonstrated_gap`, `adversarial_verification`
and `comparison_that_would_overturn` give its scope and overturn comparison.
Refuted proposals remain present alongside surviving assessments. Existing
component rows outside the eleven reviewed layers remain explicitly
`not_individually_reviewed`; their generated pin comparisons are historical
inventory, not a new upstream-currency or installation claim.

## Evidence and provenance

- [Runtime manifest](../../catalogs/sota-convergence/manifest-20261006-runtimes.json)
  and [role manifest](../../catalogs/sota-convergence/manifest-20261006-roles.json)
  retain both complete critic blocks independently.
- The returned discovery, votes, failures, follow-up directions, copy checks and
  superseded attempts are retained under
  `evidence/artifacts/landscape-sweep-20261006-{runtimes,roles}/returns.json`.
- The corresponding `RESULT.json` files bind each manifest, return artifact and
  wrapped usage record. Every survivor has a registered source-review receipt.
  The native reviewer fetched repository metadata and README bytes at the
  `reviewed_commit` recorded in that receipt. For repository-modality reviews,
  this is a publication-time default-branch source snapshot; it is not a claim
  that the original refuters judged that same commit or ran upstream tests.
- Both complete workflow usage wrappers preserve raw measurement exit 1 and
  their explained recovery of one superseded critic attempt. The raw exit is
  not rewritten to zero. Retained earlier fit attempts and their usage remain
  in the returned artifacts. Unknown usage is never replaced by zero.
- The separate completed agent-SDK smoke run `wf_0fed86b5-3e8` keeps its own
  wrapped usage in the runtime attempts directory. It is neither another full
  sweep nor an extra term in a sum of overlapping provider usage.
- The role work directory contained no extracted baseline. Its four frozen
  layer inputs and all three freshness files are byte-identical to the runtime
  sweep's copies. Publication therefore uses that shared frozen extraction,
  with the role sweep's own lanes, scope, critic, manifest ID and output path.

These are retained historical workflow observations and source reviews.
Publication generators, hash checks and repository contract tests establish
local artifact consistency. They do not constitute upstream acceptance,
native-use qualification, a new model run or proof that a candidate is better
than the incumbent.

## Completeness and next sweep

Both original critics triggered bounded follow-up work in every reviewed layer;
the converted records have no lost workers or reopened layers. Preserve the
critics' general directions as inputs to the next relevant landscape sweep:
vendor-first native interfaces; previous exclusions and named changed
conditions; version trains and tag-only releases; Codeberg, closed first-party
and platform coverage; measured incumbent comparisons; and cross-layer model,
research, identity and CI leads. These directions are research leads, not newly
verified capability claims.

## Overturn condition

For every individual assessment, use its retained
`comparison_that_would_overturn` field. Reopen a layer when its requirement or
platform scope changes, a relevant pin moves, evidence becomes stale, or a
retained failure invalidates a clean result. Preserve the old verdict and
usage; do not rewrite the historical record.

Change this publication design if the maintained harness gains explicit,
tested multi-sweep critic and provenance merge semantics. A subsequent adoption
decision still requires the candidate's stated measured comparison, maintained
primary sources and the organic native-use bar. Catalog membership alone never
overturns the incumbent or authorizes installation.

## SOTA sources

- `native-agent-stack@0d5e6506434fab598dee861c749a22e628beb75a`:
  `tools/sota-convergence/landscape-sweep/README.md:481-529,631-674`
  (native publication, retained attempts and usage contract);
  `tools/sota-convergence/build_manifest.py:1815,2062,2075,2154`
  (separate manifest outputs and critic carrier);
  `tools/sota-convergence/landscape-sweep/source_reviews.py:1242-1312`
  (pinned publication-time source reviews);
  `tools/sota-convergence/landscape-sweep/make_result.py:196-254`
  (binding source reviews and retained conditions);
  `scripts/saturation_ledger.py:738,941` (registered manifest and ledger checks).
- The upstream repository, full `reviewed_commit`, README path and observed
  source excerpts for each surviving assessment are in its source-review
  receipt, referenced by the corresponding `RESULT.json` layer entry.
- `native-agent-stack@0d5e6506434fab598dee861c749a22e628beb75a`:
  `docs/acceptance-evidence-policy.md:24-33` (claim boundaries) and
  `docs/lanes.md:94-128` (shared hot-file and registry protocol).
