# Saturation ledger

`ledger.json` is an append-only record of landscape sweeps, one record per sweep, with per-layer
results. It answers one question per layer: how many consecutive sweeps have found nothing that
survives review? It does not close a layer. A **saturation candidate** is an input to closure.
Closing a layer still goes through
[`catalogs/landscape/research-state.json`](../landscape/research-state.json) `closure_refs`, and
that edit belongs to the landscape owners
([stopping rule](../../docs/landscape-continuation.md#a-bounded-stopping-rule)).
Nothing here writes `research-state.json`, the verdict ledgers or the SOTA manifests.

| File | Role |
| --- | --- |
| `ledger.json` | The records, a hash chain (`prev_sha256`, `head_sha256`) |
| `ledger.schema.json` | JSON Schema (2020-12) for the structure |
| [`scripts/saturation_ledger.py`](../../scripts/saturation_ledger.py) | `--check`, `--report`, `--append RESULT.json`, `--derive-seed` |
| [`.github/workflows/saturation-tracking.yml`](../../.github/workflows/saturation-tracking.yml) | Weekly report and the single `saturation-tracking` issue; it makes no model calls |
| [`recipes/saturation-sweep.md`](../../recipes/saturation-sweep.md) | How a person runs a sweep and appends its record |

## Record

Each sweep record holds these fields:

- `sweep_id`, `date`, `workflow_run` and `status` (`completed` or `stopped`)
- `manifest_ref` and `manifest_sha256`: the SOTA manifest that holds the lane's candidate rows
- `lane` and `prompts_sha256`
- `usage_ref` and `usage_sha256`: the registered `child-usage.mjs` output
- `lower_bound_usage`
- `returns_ref` and `returns_sha256`: the registered retained lane returns (each layer's discovery
  return and each facts and fit vote). Required when any layer has `votes: retained`.
- optional `record_ref`, `lane_calls`, `lost_workers` (labels of `usage_ref` children that never
  returned), `not_retained` and `notes`
- `prev_sha256`
- `layers[]`

Each layer entry holds these fields:

- `catalog` (`foundation` or `us-equities`) and `layer_id`
- `requirement_sha256`: the sha256 of the canonical JSON `{next_action, decision_ref}` from the
  layer's `research-state.json` row
- `platform_profiles_sha256`: the sha256 of the canonical `adoption/manifest.json#/platform_profiles`

  Both are the scope frozen before the run (`--scope`) when the layer cites a discovery return,
  which retains them; otherwise `--append` computes them from that day's files.
- `votes`: `retained`, `not_retained` or `not_returned`, with a `votes_note` unless `retained`
- `discovery_ref`, required with `votes: retained`: `returns_ref#/pointer` to the layer's
  discovery return, `{catalog, layer_id, proposed[], requirement_sha256, platform_profiles_sha256}`
- `calls`
- `proposed`, `known` and `new`
- `survived[]` and `refuted[]`: each entry names a `repo` and its two votes. With retained
  votes, the votes are `facts` and `fit`, each `{vote, ref}`, where `ref` is
  `returns_ref#/pointer` to `{role, repository, refuted}`. Otherwise they are `lens_votes[0..1]`,
  each pointing at that lens's vote in this layer's lane row of `manifest_ref`. A survivor also
  names its `source_review`.
- `reopen[]` of `{trigger, ref}`

`known` lists the proposals that the manifest layer already names outside this lane, or that an
earlier sweep already put through both refuters. `new` lists the rest. A proposal that a stopped
run never adjudicated stays `new`; an entry it did record carries both votes bound to evidence, so
it is known. `known` and `new` are reported, not counted: the clean count never reads them.

A vote that did not return counts as refuted, so its proposal is listed under `refuted`. When no
returned vote refutes that proposal, it is **refuted by absence**: the vote objects that its refs
point to mark the missing vote `{missing: true}` (for a two-family fit vote, the missing family
member). `--check` and `--append` do not count such a proposal as an earlier adjudication, so a later
sweep that proposes it again lists it as `new`. The landscape-sweep harness also names these
proposals in the layer's `votes_note`, and its `build_inputs.py` shows them to the next discovery
round as `not_adjudicated`, not as `refuted`.

The sha256 values use canonical JSON: sorted keys, no whitespace, UTF-8. The first record chains
to `{schema_version, policy}`, so changing `policy` also breaks the chain.

## What `--check` verifies

- The structure, calendar dates, and that `prev_sha256` and `head_sha256` match. Editing,
  reordering or deleting a record fails. With `--base REF`, the ledger at `REF` must be an
  unchanged prefix. This catches a rewrite that recomputes every hash. `REF` must be a commit; a
  commit without the ledger file means there is no earlier ledger.
- `manifest_ref`, `usage_ref`, `returns_ref`, `record_ref`, every `source_review` and every vote
  and discovery `ref` file must be registered in `manifests/evidence.json` with a matching sha256.
- A retained layer needs a `discovery_ref` whose `proposed` equals the layer's `proposed`, so an
  empty layer is evidence only through its retained discovery return. The discovery return's
  frozen `requirement_sha256` and `platform_profiles_sha256` must equal the layer's, so a scope
  change during the sweep stands as a current trigger rather than being recorded as tested. Every vote and discovery
  `ref` needs a JSON pointer: a retained vote must resolve in `returns_ref` (not the manifest, the
  usage output or the run record) to an object with the same role and repository, and a lens vote
  must resolve to that lens in this layer's lane row for the same repository.
- `lost_workers` must be exactly the children of `usage_ref` that never completed; leaving one out
  fails, and an absent list means none.
- `workflow_run` must be the run `usage_ref` measured (the last segment of
  `child_usage.transcript_dir`). No two records share a `workflow_run`, usage output or returns
  file (by path or sha256), and no two completed sweeps share a manifest lane (by path or sha256).
  A stopped run may name the manifest it used only as its known/new baseline.
- A completed sweep needs `child_usage.status == complete`, `lower_bound_usage: false`, and a
  completed child for each layer's discovery worker (`discover:<layer>`) and, for a layer with
  proposals, both refuters (`refute-facts:<layer>`, `refute-fit:<layer>`). Its `date` must equal
  the `manifest_ref`'s `checked_at`. A stopped sweep needs `lower_bound_usage: true`.
- Each refuted or survived entry needs both votes. Survival is recomputed: the entry survives only
  when neither vote refutes it. Each vote must agree with the object its `ref` points to.
- A completed sweep must adjudicate every proposal, and its proposals must equal the manifest's
  rows for its `lane` in that layer, with the same survival.
- Every survivor must match a surviving lane row and have a source review of the same repository
  whose `layers` list names the layer.
- `known` and `new` are recomputed.

### Where append-only is enforced

`tests/test_saturation_ledger.py` runs `check_append_only` against the merge base of `HEAD` and
`origin/$GITHUB_BASE_REF` (or `origin/main`). `validate.yml` runs the full unit test suite with
full history on every pull request, so a pull request that rewrites an earlier record fails there
even when it recomputes every hash. In a pull-request run with full history, a missing merge base
fails the test; in a shallow clone it is skipped.

## Derived state

`--report` derives these values and never stores them.

A completed sweep is **clean** for a layer when all three hold:

- `votes` is `retained`, with a `discovery_ref`
- nothing survived
- `reopen` is empty

A layer becomes a `saturation_candidate` after `K = 3` consecutive clean completed sweeps. Each
counted sweep must fall at least `min_gap_days = 7` after the previous counted one, under an
unchanged requirement hash and platform-profile hash.

The count changes as follows:

- A stopped sweep neither counts nor resets.
- A sweep closer than the gap neither counts nor resets.
- Each of these resets the count to 0, durably, because the ledger records it:
  - a survivor
  - a reopen entry
  - a sweep whose votes or discovery return were not retained
  - a changed requirement or platform-profile hash between sweeps
- Each of these holds the count at 0 only while it stands, because `--report` reads it from
  today's files and the weekly workflow never writes the ledger:
  - a changed requirement or platform-profile hash against today's files
  - a current `pin_moved` or `stale` flag from `scripts/receipt_staleness.py --json` on a selected
    component (it clears when the host re-records the receipt)
  - a selection that the latest scheduled `catalog-freshness` manifest shows as archived, renamed
    or relicensed

  The next sweep over that layer records each current trigger as a `reopen` entry, which makes the
  reset durable ([recipe](../../recipes/saturation-sweep.md#4-append-the-record)).

The weekly workflow reads the receipt and freshness inputs. It marks the freshness input `partial`
when that run's `github-freshness.json` reports upstream errors or partial errors, since
unfetched components carry no archived, renamed or license data. Every layer that is not a
candidate is **due**.

## Seed (2026-09-23)

The seed has two records. `python3 scripts/saturation_ledger.py --derive-seed` reads each value
from these files:

- [`catalogs/sota-convergence/manifest-20260923.json`](../sota-convergence/manifest-20260923.json),
  lane `landscape-sweep-20260923`
- [`evidence/artifacts/landscape-sweep-20260923-attempts/`](../../evidence/artifacts/landscape-sweep-20260923-attempts/):
  the stopped-run record and both `child-usage.mjs` outputs
- the 11 source reviews under
  [`evidence/artifacts/landscape-sweep-20260923/`](../../evidence/artifacts/landscape-sweep-20260923/)

`tests/test_saturation_ledger.py` rebuilds both seed records and compares them with the committed
ones. The requirement and platform-profile hashes are left out of that comparison, because they
are computed from today's files at append time. The test recomputes them instead from
`research-state.json` and `adoption/manifest.json` at each commit named below.

1. **`landscape-sweep-20260923-attempt-1`** (workflow run `wf_28d47bbc-1b5`) is `stopped`, with
   `lower_bound_usage: true`. It covers 9 layers and the 27 repositories they proposed, with their
   per-layer calls. No refuter returned, so every layer has `votes: not_returned` and no outcome.
   Its 8 children stopped in flight are `lost_workers`, from the stopped run's usage output. The
   attempt record has no date of its own: `date` is the manifest's `checked_at`, the superseding
   run's date. The run produced no manifest; `manifest_ref` is only the known/new baseline. Both
   points are in the record's `notes`.
2. **`landscape-sweep-20260923`** (workflow run `wf_38aa6d5d-d6c`) is `completed`, with complete
   usage. It covers 32 layers and 107 proposals: 11 survivors and 96 refuted.

The raw lane returns and prompts were not retained. `prompts_sha256` is `null`, and every layer
has `votes: not_retained`. The manifest keeps each vote's `refuted` flag and a 400-character
excerpt by lens index. It does not say which lens was the facts refuter and which was the fit
refuter, so the seed cites the manifest's votes as `lens_votes` and does not assign roles.
`us-equities/backtesting-engine` has no lane rows, and its discovery return was not retained, so
an empty proposal set cannot be verified.

The requirement and platform-profile hashes are identical at `9eac1f9` (the lane), `0465141` (the
usage record) and `4a4c8a2` (the seed's base).

**Consequence:** no seed layer counts as clean, and every layer is due. The loop's end-to-end
acceptance is the first scoped manual sweep appended with `--append` with retained votes. Until
then, only this seed exists.
