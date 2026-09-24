# Saturation sweep

This recipe runs one landscape sweep over the layers that are due, keeps its evidence, and
appends its record to the [saturation ledger](../catalogs/saturation/README.md).

A person starts each sweep. The weekly `saturation-tracking` workflow only reports what is due.
Nothing schedules a model run: `research-state.json` keeps `execution_policy.automatic_model_calls`
set to `false`, and changing that is a separate decision for the landscape owners.

**Cost class: high.** The 2026-09-23 completed run used 119 children at effort max. The stopped
attempt alone used at least 168,052 output tokens. Sweep only the due layers, at most monthly
([SOTA convergence practice](sota-convergence-practice.md)), or sooner when a reopen trigger fires.

## 1. Scope

Read the open issue labelled `saturation-tracking`, or build the same report locally:

```sh
python3 scripts/saturation_ledger.py --check
python3 scripts/receipt_staleness.py --json --out "$WORK_DIR/receipt-staleness.json" > /dev/null
python3 scripts/saturation_ledger.py --report --staleness "$WORK_DIR/receipt-staleness.json"
```

The due layers are every layer that is not a saturation candidate. A layer with a current reopen
trigger is always due. Freeze the scope, meaning the layer list and each layer's
`research-state.json` row, before starting.

## 2. Run the lane

Run the landscape-sweep lane in an agent-lab coordinator session: one discovery researcher per
due layer, then a facts refuter and a fit refuter per layer, a completeness critic, and at most
one bounded follow-up round. These are the same limits as `lane_limits["landscape-sweep-20260923"]`
in `catalogs/sota-convergence/manifest-20260923.json`. Set each worker's model and effort
explicitly. A candidate survives only when neither refuter refutes it.

Merge the lane into a dated SOTA manifest with
[the six commands](sota-convergence-practice.md#the-six-commands-in-order), under a new lane
name. That work, and any edit under `catalogs/sota-convergence/` or `catalogs/landscape/`, stays
with the lane owners and their review gates.

## 3. Keep the evidence

Retain each of these under `evidence/artifacts/<lane>/` and `<lane>-attempts/`:

- the workflow run id, and the model and effort for each role;
- the sha256 of the prompts, recorded as `prompts_sha256`;
- the `child-usage.mjs` output, with the tool commit and sha256, the command, the exit code and
  the raw-output sha256;
- a stopped or superseded run as its own record, with its usage marked as a lower bound;
- lost workers, per-layer call counts and critic follow-ups;
- **the retained per-vote returns**: each candidate's facts and fit votes, with their cited
  references, in a JSON file. A vote `ref` points into it (`path#/json/pointer`) at an object that
  carries a boolean `refuted`. Without these returns, a layer is recorded as
  `votes: not_retained` and never counts as clean;
- one source review per survivor. See the files under
  `evidence/artifacts/landscape-sweep-20260923/` for the shape.

Register every new file, without typing hashes by hand:

```sh
python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, "scripts"); import host_receipts
for p in sys.argv[1:]: host_receipts.register_file(Path("."), p)' evidence/artifacts/<lane>/*.json
python3 scripts/validate.py
```

## 4. Append the record

Write `RESULT.json`. Leave out every computed field: `prev_sha256`, `manifest_sha256`,
`usage_sha256`, `requirement_sha256`, `platform_profiles_sha256`, `known` and `new`. `--append`
computes them from today's files.

```json
{
 "sweep_id": "landscape-sweep-YYYYMMDD", "date": "YYYY-MM-DD", "workflow_run": "wf_...",
 "status": "completed", "manifest_ref": "catalogs/sota-convergence/manifest-YYYYMMDD.json",
 "lane": "landscape-sweep-YYYYMMDD", "prompts_sha256": "<64 hex>",
 "usage_ref": "evidence/artifacts/<lane>-attempts/child-usage-wf_....json", "lower_bound_usage": false,
 "layers": [
  {"catalog": "foundation", "layer_id": "document-retrieval", "votes": "retained",
   "calls": {"web_search": 6, "web_fetch": 2, "gh_api": 24},
   "proposed": ["https://github.com/o/a", "https://github.com/o/b"],
   "survived": [{"repo": "https://github.com/o/a", "source_review": "evidence/artifacts/<lane>/o-a.json",
                 "facts": {"vote": "not_refuted", "ref": "evidence/artifacts/<lane>/votes.json#/document-retrieval/0/facts"},
                 "fit": {"vote": "not_refuted", "ref": "evidence/artifacts/<lane>/votes.json#/document-retrieval/0/fit"}}],
   "refuted": [{"repo": "https://github.com/o/b", "facts": {"vote": "not_refuted", "ref": "..."},
                "fit": {"vote": "refuted", "ref": "..."}}],
   "reopen": []}
 ]
}
```

Then append and check:

```sh
python3 scripts/saturation_ledger.py --append RESULT.json
python3 scripts/saturation_ledger.py --check --base origin/main
python3 -m unittest tests.test_saturation_ledger
```

Record a stopped run the same way: set `"status": "stopped"` and `"lower_bound_usage": true`,
and give each layer `votes: not_returned` with a `votes_note`. A stopped run neither counts nor
resets.

Add a `reopen` entry, `{trigger, ref}`, when the sweep finds any of these:

- a changed requirement
- a new platform
- a retained failure
- a credible missing capability
- a comparison that changes a result

Each one resets that layer's count.

`--append` refuses in these cases:

- the existing ledger does not check
- the `sweep_id` is already recorded
- the new record fails any binding: a survivor without a surviving manifest row or a registered
  source review, a missing vote, survival that disagrees with the votes, or unregistered or
  incomplete usage

`--append` never rewrites earlier records, and it never writes `research-state.json`. When a
layer reaches `saturation_candidate`, the landscape owners decide whether to add `closure_refs`.
