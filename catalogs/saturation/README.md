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
- optional `record_ref`, `lane_calls`, `not_retained` and `notes`
- `prev_sha256`
- `layers[]`

Each layer entry holds these fields:

- `catalog` (`foundation` or `us-equities`) and `layer_id`
- `requirement_sha256`: the sha256 of the canonical JSON `{next_action, decision_ref}` from the
  layer's `research-state.json` row
- `platform_profiles_sha256`: the sha256 of the canonical `adoption/manifest.json#/platform_profiles`
- `votes`: `retained`, `not_retained` or `not_returned`, with a `votes_note` unless `retained`
- `calls`
- `proposed`, `known` and `new`
- `survived[]` and `refuted[]`: each entry names a `repo` and its two votes. With retained
  votes, the votes are `facts` and `fit`, each `{vote, ref}`. Otherwise they are
  `lens_votes[0..1]`. A survivor also names its `source_review`.
- `reopen[]` of `{trigger, ref}`

`known` lists the proposals that the manifest layer already names outside this lane, or that an
earlier sweep already put through both refuters. `new` lists the rest. A proposal from a stopped
run was never adjudicated, so it stays `new`.

The sha256 values use canonical JSON: sorted keys, no whitespace, UTF-8. The first record chains
to `{schema_version, policy}`, so changing `policy` also breaks the chain.

## What `--check` verifies

- The structure, and that `prev_sha256` and `head_sha256` match. Editing, reordering or deleting
  a record fails. With `--base REF`, the ledger at `REF` must be an unchanged prefix. This catches
  a rewrite that recomputes every hash.
- `manifest_ref`, `usage_ref`, `record_ref`, every `source_review` and every vote `ref` file must
  be registered in `manifests/evidence.json` with a matching sha256.
- A completed sweep needs `child_usage.status == complete` and `lower_bound_usage: false`. A
  stopped sweep needs `lower_bound_usage: true`.
- Each refuted or survived entry needs both votes. Survival is recomputed: the entry survives only
  when neither vote refutes it. Each vote must agree with the object its `ref` points to.
- A completed sweep must adjudicate every proposal, and its proposals must equal the manifest's
  rows for its `lane` in that layer, with the same survival.
- Every survivor must match a surviving lane row and have a source review of the same repository
  that names the layer.
- `known` and `new` are recomputed.

## Derived state

`--report` derives these values and never stores them.

A completed sweep is **clean** for a layer when all three hold:

- `votes` is `retained`
- nothing survived
- `reopen` is empty

A layer becomes a `saturation_candidate` after `K = 3` consecutive clean completed sweeps. Each
counted sweep must fall at least `min_gap_days = 7` after the previous counted one, under an
unchanged requirement hash and platform-profile hash.

The count changes as follows:

- A stopped sweep neither counts nor resets.
- A sweep closer than the gap neither counts nor resets.
- Each of these resets the count to 0:
  - a survivor
  - a reopen entry
  - a sweep whose votes were not retained
  - a changed requirement or platform-profile hash, whether between sweeps or against today's
    files
  - a current `pin_moved` or `stale` flag from `scripts/receipt_staleness.py --json` on a selected
    component
  - a selection that the latest `catalog-freshness` manifest shows as archived, renamed or
    relicensed

The weekly workflow reads those last two inputs. Every layer that is not a candidate is **due**.

## Seed (2026-09-23)

The seed has two records. `python3 scripts/saturation_ledger.py --derive-seed` reads each value
from these files:

- [`catalogs/sota-convergence/manifest-20260923.json`](../sota-convergence/manifest-20260923.json),
  lane `landscape-sweep-20260923`
- [`evidence/artifacts/landscape-sweep-20260923-attempts/`](../../evidence/artifacts/landscape-sweep-20260923-attempts/):
  the stopped-run record and both `child-usage.mjs` outputs
- the 11 source reviews under
  [`evidence/artifacts/landscape-sweep-20260923/`](../../evidence/artifacts/landscape-sweep-20260923/)

`tests/test_saturation_ledger.py` rebuilds the seed and compares it byte for byte.

1. **`landscape-sweep-20260923-attempt-1`** (workflow run `wf_28d47bbc-1b5`) is `stopped`, with
   `lower_bound_usage: true`. It covers 9 layers and the 27 repositories they proposed, with their
   per-layer calls. No refuter returned, so every layer has `votes: not_returned` and no outcome.
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
