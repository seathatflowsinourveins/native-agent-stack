# First-pass October 6 landscape assessments

Date: 2026-10-06. This decision publishes two completed foundation sweeps as
first-pass catalog assessments: best of what was searched. It serves the north-star research and historical simulation
by preserving the alternatives, exclusions and comparisons needed for later
foundation decisions. It changes no installation, runtime pin or native
acceptance status.

The vendor-official follow-up is `landscape-sweep-20261006-vendor`: workers
smoke `wf_fba23622-d34`, then the full thirteen ordered layers. Its converted
manifest will join the same PR before the GPT read and command-center ACK.
The command center then synthesizes all three sweeps per layer: adopt through
clean upstream installation, a smoke test and organic counters in a quiet
window; keep as a catalog candidate; or exclude. Local head-to-head or A/B
campaigns do not gate a row under the owner's rule of 2026-10-06.

## Comparison and decision

Use the existing landscape-sweep publication steps independently for each
sweep, with two dated manifests in one PR. Combining their lane objects into one
manifest would require inventing merge semantics for the singular completeness
critic. The native builder accepts separate output paths and IDs; the saturation
ledger accepts separate registered manifests on the same date.

| Sweep | Workflow | Foundation layers | Proposed | Historical assessments surviving refutation | Refuted |
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

Historical survival means the proposed assessment withstood the recorded fact
and fit refutations. It includes accepted negative assessments. Current
eligibility is separate: `batrachianai/toad` is **EXCLUDED** as verified stale,
not a current survivor. A new primary default-branch query again returned no
commits since 2026-07-08. Preserve its original negative-assessment votes;
rewriting them as a refutation would contradict the retained evidence.
`gethamster/horde`, created 2026-09-08, retains **TOO NEW TO ASSESS (<90 days)**.
The historical 22/17 counts therefore coexist with one current stale exclusion;
the remaining 22/16 assessments keep their individual negative or provisional
dispositions. None is an installation or native-use qualification.

The dated [selection reconciliations](../../catalogs/sota-convergence/reconciliations-20261006-first-pass.json)
carry the first-pass status, current exclusion and age warning through the
native generator. Both RESULT carriers note these limits. All eleven reviewed
layers reopen with `selection_changed` for the vendor follow-up, with additional
Toad/Horde references on their layers. The native ledger preserves historical
outcome bindings rather than inventing a later vote.

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
the original conversion had no lost workers or retained-failure reopens. This
publication now reopens the reviewed layers for the vendor-first selection
follow-up. Preserve the
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
tested multi-sweep critic and provenance merge semantics. Retained candidate
comparisons are historical overturn proposals, not mandatory local campaigns.
The subsequent command-center adoption synthesis uses maintained primary
sources, clean upstream installation, smoke and organic counters.
Catalog membership alone never
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
- Toad's current maintenance check: `toad-maintenance-metadata.json` and
  `toad-maintenance-commits.json` under the role artifacts retain the actual
  primary API returns. Horde's `horde-age-metadata.json` under the runtime
  artifacts retains its creation date. Their exact API endpoints and overturn
  conditions are in the dated reconciliation carrier.
- `native-agent-stack@0d5e6506434fab598dee861c749a22e628beb75a`:
  `docs/acceptance-evidence-policy.md:24-33` (claim boundaries) and
  `docs/lanes.md:94-128` (shared hot-file and registry protocol).
