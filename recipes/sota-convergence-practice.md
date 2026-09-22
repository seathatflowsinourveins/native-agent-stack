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

# 3. Review lanes -- the agent-lab saved workflow, not a manual step
#    (reads/writes files under $WORK_DIR; see .claude/workflows/ for the graph name)
run-saved-workflow sota-convergence --args '{"work_dir": "'"$WORK_DIR"'"}'

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

## Evidence classes

Keep these distinguished in the record and in review comments, per the
[acceptance evidence policy](../docs/acceptance-evidence-policy.md):

- **Metadata** -- `github-freshness.json` and the manifest's `upstream`
  fields: GitHub REST facts only (stars, `pushed_at`, latest release/tag,
  license, archived, rename). Not a behavioral or compatibility claim.
- **Source review** -- lane `selected`/`new_candidates` entries and any
  `review_status` not prefixed `confirmed_`: a lane read documentation or a
  README and reasoned about fit. Nothing was installed, built or run.
- **Native run** -- `review_status` values prefixed `confirmed_` (survived
  adversarial verification) and anything the manifest cites to a receipt
  under `evidence/` or `manifests/evidence.json`: an actual reproducible
  execution exists, separately dated and scoped from this manifest.

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
