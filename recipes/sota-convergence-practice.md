# SOTA convergence practice

The operating recipe for keeping [`catalogs/sota-convergence/`](../catalogs/sota-convergence/README.md)
current using [`tools/sota-convergence/`](../tools/sota-convergence/README.md). It replaces the
2026-09-22 wave's two hardcoded, host-path scripts with CLI-driven steps.

## When to rerun

- **Monthly**, as a bounded freshness check (steps 1, 2, 4 -- skip a full lane
  re-review if no selection changed).
- **When a layer decision changes**: a component is added/removed/promoted in
  `catalogs/foundation/decisions.json` or a `catalogs/us-equities/*.json` card
  changes `decision`, or the taxonomy in a prior dated manifest is edited.
- **When a reconciliation needs updating**: the destination engine, broker
  path, or an in-use-but-unpinned tool (like ripgrep) changes; edit
  `tools/sota-convergence/reconciliations-20260922.json` (or point
  `build_manifest.py --reconciliations` at a new dated copy) before rerunning.

Do not rerun merely because a dependent upstream shipped a release; a newer
release is information, not a reason to upgrade (see "what would overturn a
selection" below).

## The six commands, in order

```sh
# 1. Extract the working files (deterministic, no network)
python3 tools/sota-convergence/extract_layers.py --repo-root . --out "$WORK_DIR"

# 2. Authenticated GitHub metadata (network; gh must already be signed in)
python3 tools/sota-convergence/github_freshness.py --work-dir "$WORK_DIR" --workers 6

# 3. Review lanes -- an agent-lab saved workflow, not a manual step and not a
#    CLI command. In Claude Code, with ultracode on (see .claude/settings.json),
#    run the saved workflow by name "sota-convergence" with args:
#      {work_dir, repo, lanes?, refuters?, budgets?, max_proposals_per_lane?}
#    The workflow itself writes nothing to disk: it reads the working files and
#    the freshness snapshot from $WORK_DIR and returns one top-level object
#    {lanes, critic, lost} (the same shape build_manifest.py --lanes consumes:
#    lanes: [{lane, result: {layers: [...], calls, limits}, proposals: [...]}],
#    critic, lost). The coordinator -- not the workflow -- must persist that
#    returned object verbatim to "$WORK_DIR/lanes.json" before step 4 runs.

# 4. Merge into the dated manifest (no network; refuses to write on a leak)
python3 tools/sota-convergence/build_manifest.py \
  --work-dir "$WORK_DIR" --lanes "$WORK_DIR/lanes.json" \
  --out "$WORK_DIR/manifest-$(date +%Y%m%d).json" \
  --checked-at "$(date +%Y-%m-%d)" --id "sota-convergence-$(date +%Y%m%d)"

# 5. Codex foreground review of the manifest diff (cross-family; separate account/quota)
#    see recipes/claude-codex-foreground-review.md
claude -p '/codex:review --wait --scope branch --base BASE_COMMIT --json' \
  --output-format stream-json --verbose --max-turns 8

# 6. Publish: copy the reviewed manifest into catalogs/sota-convergence/,
#    update catalogs/sota-convergence/README.md's summary line, open a PR,
#    and run scripts/validate.py before merging (see "PR/CI step" below).
```

`$WORK_DIR` is a private, host-local scratch directory (never committed); it
holds the working files, `github-freshness.json`, `lanes.json` and the
generated manifest before publication.

## Layer-verdict lanes

A separate, independent pipeline from the six commands above -- it records a
per-layer winner onto the landscape ledger's schema v2 rows
(`catalogs/landscape/{foundation,us-equities}.json`), not the dated sota
manifest. Full contract in `tools/sota-convergence/README.md`'s "Record
verdicts" section; the same evidence-class distinctions above apply to every
lane's `winner_evidence_class`.

```sh
# Layout: WORK_DIR and BLIND_DIR sit outside every repository, and BLIND_DIR/export is at least four
# directories deep, outside home and /tmp. Every blind tool below refuses otherwise (the shared root rule in
# tools/sota-convergence/codex_lane.py). AL is a clean agent-lab checkout whose .claude/workflows/
# layer-verdict-lane.js is the vendored examples/claude-native/workflows/ copy.

# 1. Packets, blind: labels, popularity and recency withheld, registered receipts attached. Never pass
#    --gap-receipts in a blind wave (it names the previous winner; refused with --withhold-labels).
python3 tools/sota-convergence/lane_packets.py --root . --out "$WORK_DIR" \
  --manifest catalogs/sota-convergence/manifest-YYYYMMDD.json --trading-candidates manifest \
  --withhold-labels --registered-receipts --checked-at "$(date +%Y-%m-%d)" --seed "$(date +%Y%m%d)"

# 2. Blind export: only what the packets reference (plus tests/, tools/, scripts/), labels stripped, no .git.
#    Both lanes and the adjudication read this one export; record_verdicts.py refuses lanes on two trees.
python3 tools/sota-convergence/blind_checkout.py --source . --rev HEAD \
  --dest "$BLIND_DIR/checkout" --export "$BLIND_DIR/export" --allow-from-packets "$WORK_DIR/packets"
git worktree remove --force "$BLIND_DIR/checkout"

# 3. Claude lane: args carry the launch identity {repo, repo_tree_sha256, agent_sha256} and lane-prompt.md,
#    which the workflow echoes; run it headless from the export root with hooks disabled (every stage runs as
#    blind-lane-reviewer), then collect. claude_lane.py refuses a result whose launch or prompt does not match.
python3 tools/sota-convergence/claude_lane_args.py --work-dir "$WORK_DIR" --repo "$BLIND_DIR/export" \
  --agent-file ~/.claude/agents/blind-lane-reviewer.md > "$WORK_DIR/claude-args.json"
(cd "$BLIND_DIR/export" && claude -p --settings '{"disableAllHooks": true}' "Use a workflow. Run the saved \
workflow at scriptPath $AL/.claude/workflows/layer-verdict-lane.js with the Workflow tool, passing the JSON \
object in $WORK_DIR/claude-args.json exactly as args, then copy its task output file byte for byte to \
$WORK_DIR/claude-workflow-output.json.")
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); json.dump(d.get("result", d), open(sys.argv[2], "w"))' \
  "$WORK_DIR/claude-workflow-output.json" "$WORK_DIR/claude-result.json"
python3 tools/sota-convergence/claude_lane.py --result "$WORK_DIR/claude-result.json" --work-dir "$WORK_DIR" \
  --agentlab-root "$AL" --agent-file ~/.claude/agents/blind-lane-reviewer.md --repo "$BLIND_DIR/export" \
  --resolved-model claude-opus-5-5   # the resolved child model: node $AL/.claude/workflows/child-usage.mjs --latest

# 4. Codex lane on the same export (a separate account/quota, resumable; codex_lane.py refuses a --repo below
#    any .git). A deliberately non-blind run passes --allow-git-history --repo . instead.
python3 tools/sota-convergence/codex_lane.py --work-dir "$WORK_DIR" --repo "$BLIND_DIR/export" \
  --model <openai model> --effort high --jobs 2

# 5. Two-family adjudication of the layers whose lanes disagree (README "Two-family adjudication").
python3 tools/sota-convergence/adjudicate.py inputs --work-dir "$WORK_DIR" --lane-repo-root "$BLIND_DIR/export"
python3 tools/sota-convergence/adjudicate.py codex --work-dir "$WORK_DIR" --repo "$BLIND_DIR/export" \
  --model <openai model> --jobs 2
python3 tools/sota-convergence/adjudicate.py claude-args --work-dir "$WORK_DIR" --repo "$BLIND_DIR/export" \
  --run-dir "$BLIND_DIR/export" > "$WORK_DIR/adjudication-claude-args.json"
#    Run tools/sota-convergence/adjudication-lane.js headless from the export root as in step 3, with
#    adjudication-claude-args.json as args, and write the workflow's result to adjudication-claude-result.json.
python3 tools/sota-convergence/adjudicate.py claude-collect --work-dir "$WORK_DIR" \
  --result "$WORK_DIR/adjudication-claude-result.json" --model claude-opus-5-5
python3 tools/sota-convergence/adjudicate.py assemble --work-dir "$WORK_DIR" --out "$WORK_DIR/adjudications"

# 6. Record: validate every lane file (a rejected file is reported and treated as absent, never aborts the
#    run), seal the accepted ones and the adjudications, and write the ledger rows. Pass the same
#    --adjudications to --check. --run-id is required; the grandfathered 20260922 wave is never re-recorded.
#    --lane-repo-root must name the export adjudicate inputs got: the adjudication binds the sealed form of
#    each return, whose sources_read are relativized against it.
python3 tools/sota-convergence/record_verdicts.py --root . --work-dir "$WORK_DIR" --lane-repo-root "$BLIND_DIR/export" \
  --checked-at "$(date +%Y-%m-%d)" --run-id "$(date +%Y%m%d)" --adjudications "$WORK_DIR/adjudications" --write
python3 tools/sota-convergence/record_verdicts.py --root . --work-dir "$WORK_DIR" --lane-repo-root "$BLIND_DIR/export" \
  --checked-at "$(date +%Y-%m-%d)" --run-id "$(date +%Y%m%d)" --adjudications "$WORK_DIR/adjudications" --check

# 7. Register the new wave document, refresh the narrative and rerun the standing checks.
python3 tools/sota-convergence/build_verdicts.py --write --root . --run-id "$(date +%Y%m%d)" \
  --checked-at "$(date +%Y-%m-%d)" --manifest catalogs/sota-convergence/manifest-YYYYMMDD.json
python3 scripts/landscape.py --root .
python3 scripts/validate.py
python3 -m unittest
```

A lane disagreement (different winner component-id sets) stays
`pending_lanes` with the open gap recorded unless an adjudication file is
placed at `<adjudications-dir>/<catalog>__<layer_id>.json` and passed via
`--adjudications`; agreement between lanes alone never promotes a candidate
that neither lane actually selected as its winner (the same never-promote
rule as the six-command pipeline above, applied per layer instead of per
candidate). The disagreement's open gap names the two lanes' winner
*component_ids*, not the packet-local candidate keys, since only component
identity is meaningful once the packet itself is not part of the retained
record. A recorded winner's `pin` is the packet's manifest-joined pin, else
the winning candidate's own v1 pin text if any (`source_pin`, else
`revision` -- see `catalogs/landscape/{foundation,us-equities}.json`'s real
`candidates[]` fields), else `"unpinned"`.

Step 7's `build_verdicts.py --write` is the only step that regenerates
`docs/grand-catalog-handbook.md`'s generated block (tables and per-layer
narrative). `build_verdicts.py --check` fails whenever that block differs from
the checked-in handbook: after rows were recorded, and also after any change to
the generator itself, even while every row is still `pending_lanes`. Run
`--write` and commit the regenerated handbook in the same change as the rows
or the generator edit.

## Evidence classes

Keep these distinguished in the record and in review comments, per the
[acceptance evidence policy](../docs/acceptance-evidence-policy.md).
`review_status` and `evidence_level` are two independent axes, not one:
`review_status` records whether a *selection or pin change* survived
adversarial review; `evidence_level` records what was actually *executed*. A
component or entry can carry a `confirmed_*`/`_confirmed` `review_status` and
still be `source_review` -- the published 2026-09-22 manifest's `inspect-ai`
and `quantstats` rows are exactly that case (see
`catalogs/sota-convergence/README.md`'s "Method and limits").

- **Metadata** -- `github-freshness.json` and the manifest's `upstream`
  fields: GitHub REST facts only (stars, `pushed_at`, latest release/tag,
  license, archived, rename). Not a behavioral or compatibility claim.
- **`review_status`** (selection/pin confirmation, not execution) -- whether
  a lane's proposed change to a `selected`/`new_candidates` status survived
  two adversarial refuters. A `confirmed_*` prefix means the *proposal* was
  checked, not that the underlying tool ran: **`review_status` never
  establishes native execution**, regardless of prefix. A missing verdict
  (`survives: null`) stays `<status>_unverified`, never `confirmed_*` (see
  `disposition()`/the selected-status branch in `build_manifest.py`'s
  `merge_lanes`).
- **`evidence_level`** (execution classification, from the catalog card) --
  the field that actually classifies execution evidence: `source_review`
  means a lane read documentation/source and reasoned about fit, nothing was
  installed, built or run; `native_proven` (or anything the manifest cites to
  a receipt under `evidence/` or `manifests/evidence.json`) means an actual,
  reproducible execution exists, separately dated and scoped from this
  manifest. `build_manifest.py` carries `evidence_level` into each manifest
  trading entry row whenever the source `catalogs/us-equities/*.json` card
  sets it (`extract_layers.py` already reads it verbatim); foundation
  components (`manifests/stack.json`) do not currently carry the field.

## The never-promote rule

`disposition()` in `build_manifest.py` encodes it directly: a lane proposes a
label, two independent refuters try to break the proposal, and **survival
never upgrades a label**. A `not_adopted` newcomer that survives refutation
becomes `not_adopted_confirmed`, not `default`. Only `keep_but_compare` and
`targeted_candidate` are reachable outcomes for a newcomer; nothing is ever
promoted straight to `default`/`conditional` by this pipeline. A promotion
requires a separate, explicit edit to the source catalog decision, with its
own dated evidence -- never a side effect of a convergence run.

## Cross-family review and PR/CI

Run the [Codex foreground review](claude-codex-foreground-review.md) on the
manifest diff before publication; it is a separate account and quota from the
lane review above, and its absence (as in the 2026-09-22 wave, when the
account's usage limit was exhausted) must be recorded as "not established",
not silently skipped. Open the publication as a normal PR; CI runs
`scripts/validate.py` (publication hygiene: no host paths, no secret
prefixes, duplicate-key and receipt-kind checks) and `git diff --check`. Do
not merge a manifest that fails either.

## What would overturn a selection

Each `keep_but_compare` alternative and every refuted newcomer carries its own
`comparison_that_would_overturn` in the manifest -- read that field first. The
recurring shapes are: a measured same-task provider-token comparison (token
efficiency), a dated identity dataset that resolves known ticker collisions
(identity), a completed SPY/LEAN parity run (engine), a broker-specific
recovery case passed by a community adapter (execution), and an adversarial
recovery fixture passed by a compression tool (context tools). A newer
GitHub release, a higher star count, or lane agreement alone overturns
nothing.
