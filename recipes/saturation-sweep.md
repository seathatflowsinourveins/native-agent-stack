# Saturation sweep

This recipe runs one landscape sweep over the layers that are due, keeps its evidence, and
appends its record to the [saturation ledger](../catalogs/saturation/README.md).

A person starts each sweep. The weekly `saturation-tracking` workflow only reports what is due.
Nothing schedules a model run: `research-state.json` keeps `execution_policy.automatic_model_calls`
set to `false`, and changing that is a separate decision for the landscape owners.

**Cost class: high.** The 2026-09-23 completed run used 119 children at effort max. The stopped
attempt alone used at least 168,052 output tokens. The 2026-09-29 run (20 foundation layers; 131 Claude children,
52 of them Sonnet wrappers that each ran one GPT-6 job; 7.1 hours, of which 2.6 were a single idle gap) cost $425 at
Claude list price: Opus 5.5 $400 and Sonnet 5.5 $25. Of that, $101 (24%) is advisor inference inside the workers,
which `child-usage.mjs` does not count (its record prices to the other $324), and $19 is the nine superseded attempts
the record lists. The first round was $337 and the bounded follow-up round $88; the wrappers are $27, and the GPT-6
tokens themselves are billed to the Codex or gateway accounts and are only in the run record. Per counted child,
advisor calls included, the discovery workers averaged $5.65, the fit refuters $4.60 and the facts refuters $4.13 (all
Opus 5.5 at effort max, with a median of 43, 34 and 32 calls), the critic $5.50 and the two wrapper roles $0.37 and
$0.64. Source: `evidence/artifacts/landscape-sweep-20260929-attempts/spend-scan-wf_08a5b367-311.json` (`ccusage` shows
$398 for the run: Opus 5.5 only, since it leaves Sonnet 5.5 unpriced). Sweep only the due layers, at most monthly
([SOTA convergence practice](sota-convergence-practice.md)), or sooner when a reopen trigger fires. Probe the GPT-6
lane before the run (runbook step 4) and watch for `LIMIT` while it runs: the follow-up round starts by itself after
the critic and spends Claude stages even when every GPT-6 vote will fail, and a layer with a missing vote stays
reopened.

## 1. Scope

Read the open issue labelled `saturation-tracking`, or build the same report locally:

```sh
python3 scripts/saturation_ledger.py --check
python3 scripts/receipt_staleness.py --json --out "$WORK_DIR/receipt-staleness.json" > /dev/null
python3 scripts/saturation_ledger.py --report --staleness "$WORK_DIR/receipt-staleness.json"
```

The due layers are every layer that is not a saturation candidate. A layer with a current reopen
trigger is always due. Freeze the scope, meaning the layer list and each layer's
`research-state.json` row, before starting, and keep its hashes:

```sh
python3 scripts/saturation_ledger.py --scope > "$WORK_DIR/scope.json"
```

## 2. Run the lane

Run the landscape-sweep lane in an agent-lab coordinator session: one discovery researcher per
due layer, then a facts refuter and a fit refuter per layer, a completeness critic, and at most
one bounded follow-up round. These are the same limits as `lane_limits["landscape-sweep-20260923"]`
in `catalogs/sota-convergence/manifest-20260923.json`. Set each worker's model and effort
explicitly. A candidate survives only when neither refuter refutes it. Label the workers
`discover:<layer>`, `refute-facts:<layer>` and `refute-fit:<layer>`, as the 2026-09-23 run did:
`--check` reconciles those labels in the usage output with the recorded layers.

Merge the lane into a dated SOTA manifest with
[the six commands](sota-convergence-practice.md#the-six-commands-in-order), under a new lane
name. That work, and any edit under `catalogs/sota-convergence/` or `catalogs/landscape/`, stays
with the lane owners and their review gates.

## Run the lane in this repository (2026-09-26)

[`tools/sota-convergence/landscape-sweep/`](../tools/sota-convergence/landscape-sweep/README.md) runs this lane
from this repository on Linux/WSL2 or macOS, from freezing the scope through `RESULT.json`. Its lanes are
two-family:

- **Discovery.** Each layer gets a Claude Opus researcher (`discover:<layer>`) and a GPT-6-Astra researcher through
  the Codex CLI (`gpt6-discover:<layer>`).
- **Refutation.** A Sonnet facts refuter (`refute-facts:<layer>`) and two fit refuters, Claude Opus
  (`refute-fit:<layer>`) and GPT-6-Astra (`gpt6-refute-fit:<layer>`), all run at effort max. A candidate survives
  only when neither the facts refuter nor either fit refuter refutes it.

A failed part of the lane never leaves a clean layer. A lost round, a discovery family or a vote that did not
return, a lost critic, and a Claude worker whose WebSearch call the session's cap refused each give the layer a
`retained_failure` reopen entry pointing at its listed failures in the retained returns. The critic's failure
counts for every layer. The lane's search budgets exceed Claude Code's default of 200 WebSearch calls per
session, so start the coordinator session with `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` raised (harness README,
Coordination).

The labels that `--check` reconciles are unchanged. The harness also writes what section 3 asks for: the retained
returns, the sanitized `child-usage.mjs` record and `prompts_sha256`. An agent-lab coordinator session remains an
alternative way to run the lane.

## 3. Keep the evidence

Retain each of these under `evidence/artifacts/<lane>/` and `<lane>-attempts/`:

- the workflow run id, and the model and effort for each role;
- the sha256 of the prompts, recorded as `prompts_sha256`;
- the `child-usage.mjs` output, with the tool commit and sha256, the command, the exit code and
  the raw-output sha256;
- a stopped or superseded run as its own record, with its usage marked as a lower bound;
- lost workers, per-layer call counts and critic follow-ups;
- **the retained lane returns**, one JSON file per sweep (the record's `returns_ref`): each
  layer's discovery return as `{catalog, layer_id, proposed[], requirement_sha256,
  platform_profiles_sha256}` (the two hashes copied from the frozen `scope.json`), and each
  candidate's facts and fit votes as `{role, repository, refuted, ...}` with their cited references. A layer's
  `discovery_ref` and each vote `ref` point into it (`path#/json/pointer`). Without these returns,
  a layer is recorded as `votes: not_retained` and never counts as clean. A retained layer with no
  proposals still needs its discovery return;
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
`usage_sha256`, `returns_sha256`, `requirement_sha256`, `platform_profiles_sha256`, `known` and `new`. `--append`
computes them: the requirement and platform-profile hashes from each cited discovery return's
frozen scope (otherwise today's files), the rest from today's files. `date` is the lane manifest's
`checked_at`, and `workflow_run` is the run the usage output measured.

```json
{
 "sweep_id": "landscape-sweep-YYYYMMDD", "date": "YYYY-MM-DD", "workflow_run": "wf_...",
 "status": "completed", "manifest_ref": "catalogs/sota-convergence/manifest-YYYYMMDD.json",
 "lane": "landscape-sweep-YYYYMMDD", "prompts_sha256": "<64 hex>",
 "usage_ref": "evidence/artifacts/<lane>-attempts/child-usage-wf_....json", "lower_bound_usage": false,
 "returns_ref": "evidence/artifacts/<lane>/returns.json",
 "layers": [
  {"catalog": "foundation", "layer_id": "document-retrieval", "votes": "retained",
   "discovery_ref": "evidence/artifacts/<lane>/returns.json#/discovery/document-retrieval",
   "calls": {"web_search": 6, "web_fetch": 2, "gh_api": 24},
   "proposed": ["https://github.com/o/a", "https://github.com/o/b"],
   "survived": [{"repo": "https://github.com/o/a", "source_review": "evidence/artifacts/<lane>/o-a.json",
                 "facts": {"vote": "not_refuted", "ref": "evidence/artifacts/<lane>/returns.json#/votes/document-retrieval/0/facts"},
                 "fit": {"vote": "not_refuted", "ref": "evidence/artifacts/<lane>/returns.json#/votes/document-retrieval/0/fit"}}],
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
python3 scripts/component_matrix.py --write   # convergence by layer reads the ledger's completed sweeps
```

The pull request that adds the record runs the same append-only comparison in `validate.yml`,
against the merge base with the target branch.

Record a stopped run the same way: set `"status": "stopped"` and `"lower_bound_usage": true`,
give each layer `votes: not_returned` with a `votes_note`, and list every child that never
returned in `lost_workers`. A stopped run neither counts nor resets.

Add a `reopen` entry, `{trigger, ref}`, when the sweep finds any of these:

- a changed requirement
- a new platform
- a retained failure
- a credible missing capability
- a comparison that changes a result

Also copy each of the report's current reopen triggers for a covered layer (`pin_moved`,
`stale_receipt`, `selection_changed`, and a requirement or platform-profile change) into that
layer's `reopen`. The report reads those from today's files, so they hold a layer at 0 only while
they stand; the ledger entry keeps the reset after the flag clears. Each reopen entry resets that
layer's count.

`--append` refuses in these cases:

- the existing ledger does not check
- the `sweep_id` is already recorded
- the new record fails any binding: a survivor without a surviving manifest row or a registered
  source review, a missing vote or discovery return, a vote or discovery `ref` without a pointer
  into `returns_ref`, survival that disagrees with the votes, an invalid date, or unregistered
  or incomplete usage

`--append` never rewrites earlier records, and it never writes `research-state.json`. When a
layer reaches `saturation_candidate`, the landscape owners decide whether to add `closure_refs`.
