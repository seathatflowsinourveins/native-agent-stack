# Decision: retire PR #515, the ranked catalog index (2026-10-03)

**Status:** retire the proposal with this dated record; close #515 after this record lands on main.

**Decided by:** session `native-agent-stack-0c`, taking custody of an unowned PR after the
[custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/515#issuecomment-5967135709)
and its two-hour objection window. The notice was posted at 08:22:06Z on 2026-10-03; the window ended
at 10:22:06Z. The build-time read found no objection and found the PR open at its unchanged head.
This is a custody session's disposition, not a user decision.

**North-star action served:** keep foundation selection evidence honest for the harness that supports
US-equities research, historical simulation and subsequent independently qualified paper operation.
This record preserves the proposal's useful facts without treating source-host bookkeeping as merit.

## Sources and scope

The retained proposal is [PR #515](https://github.com/seathatflowsinourveins/native-agent-stack/pull/515),
head `3d4a9510136c8f38b636b70b04e0ac53060b2fa9`, branch
`claude/catalog-index-ranking-20260929`. Unless a different revision is named, the file:line citations
below refer to that head. The record was built on main at
`9b0b8d6d25f9e3fb8f71770500e774170423315e`; policy citations are pinned there. PR metadata and native
Actions results were read on 2026-10-03.

Component identities are available in the retained PR head, rather than repeated here. In the default
blind-export mode, Markdown under `docs/` is copied unchanged; the allowlisted mode has a narrower
export ([tools/sota-convergence/blind_checkout.py:814-826 at main][blind-docs]). Anonymous JSON
pointers below retain the five specific pairs without naming components in a decision record.

## What the proposal did

The historical proposal attempted to combine catalogs, evidence metadata and ranking. Repository evidence needs its
own scope: [OpenSSF Scorecard's documented assessment](https://github.com/ossf/scorecard/blob/ac4b584439389e57f8d56d925f7fef245d8dda1f/README.md) and [CNCF Landscape's catalog representation](https://github.com/cncf/landscape2/blob/2ee800dfe0d43a5a3beace3bec83ba469c7ccdc0/README.md) do not establish a universal merit ordering.
The retained branch adds four files; their exact Git blob identities at the retained head are:
four files; their exact Git blob identities at the retained head are:

| New file | Blob |
| --- | --- |
| `scripts/catalog_index.py` | `d146df1792d77865c4dc375a3d3af98548c35915` |
| `catalogs/landscape/catalog-index.json` | `2a513b52e86aa74625a40839ce57ed556de66a7f` |
| `tests/test_catalog_index.py` | `cb60e27768933dc83670006b423a86f970e5facc` |
| `docs/decisions/2026-09-29-catalog-index-ranking.md` | `743147b9389465a4603426f4fcf4020f45ebe913` |

The generated index joins committed catalogs and evidence. The explorer gains a **Ranked by evidence**
tab; CI checks regeneration; the freshness bot regenerates the index after registering a receipt;
the matrix-refresh procedures gain another write step. These are preserved proposal facts, not changes
made by this retirement ([old record:16-23][old-scope], [old record:193-206][old-procedures]; the
receipt-then-index call order is at [scripts/freshness_propose.py:681-687][old-freshness-order]).

## Why retire it

The active ranking rule gives the source host's selection of record precedence:

| Key | Source at the retained head | What determines it |
| --- | --- | --- |
| K1, `recorded_role` | [scripts/catalog_index.py:205-209][k1] | Recorded role first: winner, alternative, then historical card. |
| K2, `evidence_tier` | [scripts/catalog_index.py:210-216][k2] | Winners and alternatives take the verdict's `evidence_class`; card-only entries take their card's kind. |
| K3, `host_verification_at_pin` | [scripts/catalog_index.py:220-234][k3] | Source-host receipts on `linux-wsl2-x86_64`, with recorded verdict or stack pins and role-specific levels. |
| K4, `measured_rank` | [scripts/catalog_index.py:244-250][k4] | A comparable verified measurement could order a tie; every actual K4 is zero. |

Merit requires repository-specific primary evidence and a comparison on the same frozen tasks, using the arms'
supported upstream interfaces. A source host's installed state, pins, bookkeeping and integration holds describe
deployment custody; they supply no comparative repository result. [Harbor's native task interface][program-5]
supports the bounded comparison, while [Scorecard's documented scope][scorecard] keeps security assessment distinct.
Those practice and evidence boundaries ground this retirement; an unmeasured rank remains undetermined.

U11 remains **proposed, revision 5**, rather than accepted policy ([U11:1-9 at main][u11-status]).
Its proposed frozen-task procedure is distinct from an upstream runtime result; the native harness is the execution basis.
selection rule gives the selection of record no precedence in selection, ties or arm order
([U11:126-127][u11-precedence]). A qualifying merit claim under that design needs a preregistered rule,
a registered comparison receipt and a recomputed outcome ([U11:111-117][u11-receipt]).

#515's own record rejected evidence before role because it could put a stronger-evidence alternative
above a recorded winner ([old record:139-140][old-role-first]). The record in #595 explicitly declined
merging #515 and says it does not depend on it ([docs/decisions/2026-10-01-final-catalog.md:303-306 at
#595 head `7f6a1781a5d8803a04baddb36f936c237e5ce8ba`][p595-independent]).

**A merit-neutral re-key supplies no ranking result until a layer records a qualifying head-to-head comparison.**
Use the same frozen tasks and supported native installation/test commands for each arm, through
[the pinned upstream harness][program-5-merit]. U11 remains a proposed additional protocol rather than accepted policy;
its extra bar applies only after that design is accepted. Removing bookkeeping keys supplies no measurement:
keys supplies no measurement: the retained JSON has an empty `measurements` array, no
measurement-ordered placements and zero K4 on every placement
([catalogs/landscape/catalog-index.json:34-57][index-counts], [JSON:42085][index-measurements]).
Keeping an inert index or merely renaming its keys supplies no evidence-strength comparison.
The alternatives are to retain this history and reopen on a qualified result, or to record a separately reviewed
selection-policy change with its supported sources and consequences.

## Defects and staleness observed at retirement

The native [Actions run 36617653643](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36617653643)
ran at the retained head. Its [validate-macos job 109574692808](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36617653643/job/109574692808)
failed. Artifact `adoption-bootstrap-full-suite-macos-36617653643-1` (artifact id `11056809383`,
ZIP SHA-256 `c43af480123f68aabbeb3a1182edd4159aad8101221ceac0630cd33ef134217e`) contains
`full-suite-macos.log:8593`: `test_role_record_pointers_resolve_and_read_set_equals_inputs` fails
because its expected temporary-directory path keeps the unresolved spelling, while the actual call
uses the symlink-resolved spelling: `var` versus `private/var` in the macOS temporary-path prefix.
The historical suite ran 7,650 tests, with one failure and 978
skips; these are that CI run's results, not a new macOS execution.

The cause is visible in the pinned sources: [tests/test_catalog_index.py:278][mac-root] keeps
`Path(temporary.name)` unresolved, while [scripts/catalog_index.py:1063][resolved-root] resolves
the root; the assertion compares those roots ([test:1023][mac-assertion]). Any revival must change the
fixture to `Path(temporary.name).resolve()` and obtain passing macOS evidence.

The [osv-scanner job](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/36617653508/job/109574692291)
also failed at the retained head. The PR body's checklist named only that failure, describing it as
repository-wide; it omitted the macOS failure. The original advisory cause has not been re-derived
here. [Merged #622](https://github.com/seathatflowsinourveins/native-agent-stack/pull/622) subsequently
retired the historical WSL retrieval fixture's replay/install entry points and scanned its unchanged lock
in a separate archive partition; it did **not** retire osv-scanner
([.github/workflows/security-scan.yml:3-9][osv-scope] and [:62-81 at `dcae68bd`][osv-scan]). That later
change neither repairs #515's macOS test nor establishes the cause of its older scanner failure.

The merge base is `ed293987f3eab7e065581f74824c588d16fb8fbe`. Staleness was recomputed from Git history,
counting all main commits, rather than copied from the planning contract:

| Main snapshot | Commits after the merge base | Commits touching `manifests/evidence.json` |
| --- | ---: | ---: |
| Planning base `dcae68bd08a191f37ba564eceda9fc4a9d6d4a6e` | 86 | 82 |
| Build base `9b0b8d6d25f9e3fb8f71770500e774170423315e` | 90 | 86 |

For each pinned snapshot, the commands are `git rev-list --count <merge-base>..<snapshot>` and
`git rev-list --count <merge-base>..<snapshot> -- manifests/evidence.json`. The older index is a
dated snapshot; the build-base figures above are not new index contents.

## Unique facts retained: at ed293987 plus the branch

All index tallies below were recomputed from `git show
3d4a9510136c8f38b636b70b04e0ac53060b2fa9:catalogs/landscape/catalog-index.json`: enumerate the raw
layers, placements, `role_records`, entities, distinct receipt ids, coverage rows and status items;
group positions within each layer; compare the original sort keys with K2 and K3 interchanged.
The resulting figures match the committed count fields. They describe **ed293987 plus the branch**,
not today's main or a new host's acceptance ([old record:70-86][old-snapshot]).

| Fact | Recomputed value | Pinned source |
| --- | ---: | --- |
| Layers | 32: 30 recorded, 2 `pending_lanes` | [JSON:40-57][index-counts] and `layers[].banner.verdict_status` |
| Source records | 614, zero unresolved | [JSON:56-57][index-counts] and raw `role_records` |
| Entities | 875 | [JSON:8-9][index-conservation] and raw `entities[]` |
| Receipts | 172 listed, 172 attached, zero unattached | [JSON:14-17][index-conservation] and distinct `entities[].receipts.ids` |
| Placements | 440: 414 ranked, 26 outside, zero caution | [JSON:40-57][index-counts] and raw placement arrays |
| Shared ranked placements | 368 | [JSON:55][index-counts] and raw `shared` fields |
| Distinct positions within layers | 120 | [JSON:42][index-counts] and per-layer position sets |
| Largest tie | 16 | [JSON:43][index-counts] and per-layer position groups |
| Catalog/manifest coverage | 94 files: 8 index inputs, 4 matrix inputs, 30 decision-index sources, 52 not reached | [JSON:5-6,20-25][index-conservation] and `coverage.catalog_files[]` |
| Unmodeled collections | 5 | [JSON:478-499][unmodeled] |
| Status items | 294: 213 info, 81 warning, zero error | [JSON:42268][status-array] and raw level counts |
| Structured measurements | 0 | [JSON:42085][index-measurements] |
| Class/verification inversions | 5 pairs, zero winner pairs | [JSON:35-38][index-overturn] and independent key comparison |
| A `pin_current` tiebreak would unshare | 23 placements, leaving 345 shared | [JSON:38][index-overturn] and independent tie regrouping |

The five unmodeled collections are `catalogs/foundation/memory-stack-20260925.json#/non_repository_decisions`,
`catalogs/us-equities/local-model-workloads-20260924.json#/non_repository_decisions`,
`catalogs/us-equities/models.json#/entries`,
`catalogs/us-equities/mover-v3-sweep-20260924.json#/non_repository_decisions`, and
`manifests/stack.json#/models` ([JSON:478-499][unmodeled]).

### Status-item account

The type counts are recomputed from `status_items[]`, retaining zero-count types from the declared
type vocabulary. Their sum is 294 ([JSON:59-81][status-counts]).

| Type | Count |
| --- | ---: |
| `coverage/not-reached` | 52 |
| `domain-card/default-never-winner` | 8 |
| `evidence/class-verification-inversion` | 5 |
| `evidence/mixed-kind` | 25 |
| `evidence/unmapped-kind` | 4 |
| `evidence/winner-tier-below-alternative` | 6 |
| `freshness/layer-reopened` | 30 |
| `freshness/pin-behind-upstream` | 33 |
| `identity/component-id-conflict` | 0 |
| `identity/multiple-component-ids` | 8 |
| `identity/unresolved` | 0 |
| `role/duplicate-role-record` | 0 |
| `role/selected-card-no-verdict` | 11 |
| `role/selected-card-not-winner` | 72 |
| `role/winner-card-not-selected` | 4 |
| `source/sweep-manifest-divergence` | 1 |
| `status/declared-above-derived` | 4 |
| `verification/alternative-receipt-off-platform` | 0 |
| `verification/alternative-receipt-version-mismatch` | 1 |
| `verification/alternative-receipt-version-unknown` | 0 |
| `verification/host-fail-recorded` | 2 |
| `verification/joined-by-repository` | 28 |

### The five flipped pairs

The pointers are zero-based JSON locations in the retained index, not ranking positions. Every row
pairs its first pointer (tier A, K3 level 1) with `/layers/11/placements/9` (tier B, K3 level 0).
Class-first order puts the first pointer ahead; verification-first order reverses it. All five are
within `foundation/observation-inference`; none involves a recorded winner. The original placement
fields are at [JSON:23376-23756][pair-placements]; the common entry's tier is at line 23701.

| First placement | Second placement | Status item and pinned file:line |
| --- | --- | --- |
| `/layers/11/placements/4` | `/layers/11/placements/9` | `/status_items/60`, [JSON:42757-42765][pair-60] |
| `/layers/11/placements/5` | `/layers/11/placements/9` | `/status_items/61`, [JSON:42767-42775][pair-61] |
| `/layers/11/placements/6` | `/layers/11/placements/9` | `/status_items/62`, [JSON:42777-42785][pair-62] |
| `/layers/11/placements/7` | `/layers/11/placements/9` | `/status_items/63`, [JSON:42787-42795][pair-63] |
| `/layers/11/placements/8` | `/layers/11/placements/9` | `/status_items/64`, [JSON:42797-42805][pair-64] |

The old record's line 163 calls the common entry tier C. The retained JSON's placement instead says
tier B. This account follows the original JSON and its sort keys; the prose discrepancy is preserved
as a correction rather than repeated ([old record:162-164][old-evidence-order], `JSON#/layers/11/placements/9`).

### Rejected alternatives, sources and review history

- A blended score was rejected because it hides the underlying behaviors; [OpenSSF Scorecard's per-check explanation][scorecard] supplies the upstream basis.
  The cited upstream source, [OpenSSF Scorecard README:109-112 at
  `ac4b584439389e57f8d56d925f7fef245d8dda1f`][scorecard], says an aggregate tells "nothing about what
  individual behaviors a repository is or is not doing". That passage was re-read at build time.
- A Thoughtworks Radar crosswalk was rejected as a conflicting second ordinal whose adoption meaning overstates
  an unreviewed accepted status ([old record:149-150][old-alternatives]); its upstream reference is the
  [Thoughtworks Technology Radar FAQ](https://www.thoughtworks.com/radar/faq), accessed 2026-10-03.
- The `pin_current` tiebreak was rejected as currency rather than deciding evidence ([old record:146-147][old-alternatives]).
  The [landscape manifest's rule:32][pin-rule] requires a relevant compatibility or improvement result to supersede
  an accepted pin. Its independently recomputed effect is retained above.

The proposal used **CNCF landscape2** for a catalog generated from source data and **Backstage** for
entity status items. Its dated source account names `cncf/landscape2` at `2ee800df`, `README` and
`docs/config/data.yml`, and Backstage's descriptor format and life-of-an-entity documentation
([old record:175-185][old-sources]). The source-data practice was re-read in [landscape2 README:25-31
at full pin `2ee800dfe0d43a5a3beace3bec83ba469c7ccdc0`][landscape2-source] and its
[data.yml:42-51][landscape2-data]. Backstage's read-only `status.items` pattern was re-read in
[descriptor-format.md:457-509 at `6413b66c8913ab8ad41afd5f25973e16afdc4b33`][backstage-status].
These are the proposal's reference patterns; retirement adds no catalog implementation.

The PR body reports one independent Claude review with seven findings, one repair round, then a delta
verification confirming 8/8. The old record describes the repair/rebase ([old record:3-9][old-repair])
and explicitly says no GPT cross-family review ran ([old record:221-222][old-review]). Those are
retained historical review claims about #515, not a review of this retirement; this retirement's own
reviews are recorded on [#660](https://github.com/seathatflowsinourveins/native-agent-stack/pull/660). The original author session
is unidentified. The [trading-lane ACK at this head](https://github.com/seathatflowsinourveins/native-agent-stack/pull/515#issuecomment-5896926888)
was for #515's proposed integration and becomes moot on retirement.

## Freshness wording and preservation

#515's `build_receipt` claim edit still says "Scheduled catalog-freshness run"
([scripts/freshness_propose.py:456-474][old-freshness]). [#616](https://github.com/seathatflowsinourveins/native-agent-stack/pull/616)
was open, draft and `lane:foundation` on the build-time read; its trigger-neutral wording is
"Catalog-freshness run" ([scripts/freshness_propose.py:448-465 at #616 head
`ea7a49d64c63bbe65684d6063799c420a1e02834`][neutral-freshness]). Retirement drops #515's edit, so it
creates no conflict with #616. Any revival rebases onto main's wording at that time and never
brings "Scheduled" back.

`refs/pull/515/head` was verified remotely at `3d4a9510136c8f38b636b70b04e0ac53060b2fa9` with
`git ls-remote origin refs/pull/515/head`. Keep the branch. GitHub's
[instructions for inactive pull requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/checking-out-pull-requests-locally#modifying-an-inactive-pull-request-locally)
describe retrieving a previously opened PR through `pull/ID/head` (accessed 2026-10-03).

The record follows [Nygard, *Documenting Architecture Decisions* (2011)](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions),
accessed 2026-10-03: keep the old decision and mark its changed status. Maintained
[adr/madr's template:3 at `ba75bb1b20d42af5746b246ad348c202419ae681`][madr-template]
supports rejected, deprecated and superseded statuses; its [status-field decision][madr-status] makes
status explicit. The repository precedent retains historical receipts while recording retirement
([docs/decisions/2026-09-25-retire-vela-velanext.md:33-46 at main][retirement-precedent]).

## Reopening triggers

1. A layer records a head-to-head comparison that decides merit under program decision 5
   ([program decision 5:97-104][program-5-merit]). If U11 is accepted first, the comparison must also
   meet its bar: a preregistered decision rule and a registered receipt bound to its inputs and outcome
   ([U11:111-117][u11-receipt]). A merit-only index may then return with K1-K3 removed, K4 bound to
   that comparison's recorded result, the macOS fixture fix and main's current freshness wording.
2. The user restores the provisional install of the recorded selection as the default, program decision 5's
   overturn ([program decision 5:105-106][program-5-overturn]).
3. The user restores precedence for the selection of record by an explicit decision. This is a separate
   user decision, not decision 5's overturn.
4. The user asks again for a ranked single index.

This record changes no catalog, verdict, receipt, pin, explorer, CI or blind-checkout file. It does
not touch #595 or #616. Foundation owns this new `docs/decisions/` file
([docs/lanes.md:24 at main][lane-ownership]); a new record here does not require evidence-manifest
registration ([docs/lanes.md:116-124][lane-policy]). No shared hot file changes, so the foundation
PR needs no trading-lane ACK ([docs/lanes.md:145-150][lane-labels]).

[blind-docs]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/tools/sota-convergence/blind_checkout.py#L814-L826
[old-scope]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L16-L23
[old-procedures]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L193-L206
[old-freshness-order]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/scripts/freshness_propose.py#L681-L687
[old-evidence-order]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L162-L167
[k1]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/scripts/catalog_index.py#L205-L209
[k2]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/scripts/catalog_index.py#L210-L216
[k3]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/scripts/catalog_index.py#L220-L234
[k4]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/scripts/catalog_index.py#L244-L250
[program-5]: https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md
[program-5-merit]: https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md
[program-5-overturn]: https://github.com/adr/madr/blob/ba75bb1b20d42af5746b246ad348c202419ae681/template/adr-template.md
[u11-status]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-u11-merit-neutral-selection.md#L1-L9
[u11-context]: https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md
[u11-precedence]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-u11-merit-neutral-selection.md#L126-L127
[u11-receipt]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-u11-merit-neutral-selection.md#L111-L117
[old-role-first]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L139-L140
[p595-independent]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/7f6a1781a5d8803a04baddb36f936c237e5ce8ba/docs/decisions/2026-10-01-final-catalog.md#L303-L306
[index-counts]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L34-L57
[index-conservation]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L3-L25
[index-overturn]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L35-L38
[index-measurements]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L42085
[mac-root]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/tests/test_catalog_index.py#L274-L288
[resolved-root]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/scripts/catalog_index.py#L1060-L1065
[mac-assertion]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/tests/test_catalog_index.py#L1020-L1024
[osv-scope]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/dcae68bd08a191f37ba564eceda9fc4a9d6d4a6e/.github/workflows/security-scan.yml#L3-L9
[osv-scan]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/dcae68bd08a191f37ba564eceda9fc4a9d6d4a6e/.github/workflows/security-scan.yml#L62-L81
[old-snapshot]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L70-L86
[unmodeled]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L478-L499
[status-array]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L42268
[status-counts]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L59-L81
[pair-60]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L42757-L42765
[pair-61]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L42767-L42775
[pair-62]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L42777-L42785
[pair-63]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L42787-L42795
[pair-64]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L42797-L42805
[pair-placements]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/catalog-index.json#L23376-L23756
[old-alternatives]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L146-L150
[scorecard]: https://github.com/ossf/scorecard/blob/ac4b584439389e57f8d56d925f7fef245d8dda1f/README.md#L109-L112
[pin-rule]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/catalogs/landscape/manifest.json#L32
[old-sources]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L175-L185
[landscape2-source]: https://github.com/cncf/landscape2/blob/2ee800dfe0d43a5a3beace3bec83ba469c7ccdc0/README.md#L25-L31
[landscape2-data]: https://github.com/cncf/landscape2/blob/2ee800dfe0d43a5a3beace3bec83ba469c7ccdc0/docs/config/data.yml#L42-L51
[backstage-status]: https://github.com/backstage/backstage/blob/6413b66c8913ab8ad41afd5f25973e16afdc4b33/docs/features/software-catalog/descriptor-format.md#L457-L509
[old-repair]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L3-L9
[old-review]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/docs/decisions/2026-09-29-catalog-index-ranking.md#L221-L222
[old-freshness]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/3d4a9510136c8f38b636b70b04e0ac53060b2fa9/scripts/freshness_propose.py#L456-L474
[neutral-freshness]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/ea7a49d64c63bbe65684d6063799c420a1e02834/scripts/freshness_propose.py#L448-L465
[madr-template]: https://github.com/adr/madr/blob/ba75bb1b20d42af5746b246ad348c202419ae681/template/adr-template.md#L3
[madr-status]: https://github.com/adr/madr/blob/ba75bb1b20d42af5746b246ad348c202419ae681/docs/decisions/0008-add-status-field.md#L5-L23
[retirement-precedent]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-25-retire-vela-velanext.md#L33-L46
[lane-policy]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/lanes.md#L116-L124
[lane-ownership]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/lanes.md#L24
[lane-labels]: https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/lanes.md#L145-L150
