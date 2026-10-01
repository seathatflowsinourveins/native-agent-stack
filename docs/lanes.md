# Interim lanes: foundation and trading

## Purpose

During an interim period, two lanes share this repository:

- **Foundation**: the general native harness -- Claude Code and Codex setup,
  adoption, memory, retrieval, research convergence and saturation tracking,
  workers, and observability backends.
- **Trading**: US-equities research, then historical simulation, then paper,
  then live.

The trading lane is moving to a private trading repository. Until it has
moved, trading sessions own the trading paths below. This file assigns paths
and PR labels for that period; it does not change the catalog boundary (see
[Existing boundary statements](#existing-boundary-statements)).

## Path ownership

Every path below was verified against `main` at `6d9a7a5`.

| Owner | Paths |
| --- | --- |
| Foundation | `catalogs/foundation/`, `catalogs/convergence-practice/`, `catalogs/saturation/`; `catalogs/landscape/*` except `us-equities.json` and the gap ledgers; `tools/`, `recipes/`, `examples/`, `fixtures/`; `adoption/` (including `adoption/hardware-profiles.json`) except the trading profile entries; `evidence/hosts/**`; `docs/` except the trading documents and shared files named here; `blueprints/` except the trading blueprints; `observability/backends/`, `observability/collector/`, `observability/native-data/` |
| Trading | `catalogs/us-equities/`; `catalogs/landscape/us-equities.json`; `blueprints/us-equities/`; `blueprints/gap-wave2-20260923/us-equities__*`; `observability/paper-trading-live/`; `scripts/trading_gates.py`; `scripts/verify_nautilus_ci.py`; the `trading-nautilus` and `research-runtime` profile entries in `adoption/manifest.json`; `docs/paper-lane-policy.md`; `docs/decisions/2026-09-22-broker-credential-handling.md`; the [trading tests](#trading-tests) |
| Shared hot files | `manifests/evidence.json`, `manifests/stack.json`, `observability/grand-dashboard/state.json`, `AGENTS.md`, `catalogs/sota-convergence/*`, the gap ledgers (`catalogs/landscape/gap-*.json` and their `docs/gap-*.md` renderings) |

- A path not listed here follows the lane its change serves; a change that
  serves both lanes is `lane:shared`.
- A change to this file is `lane:shared`. So is a change to `adoption/sdk/`,
  which is a recipe of the `research-runtime` profile and is also cited by
  `catalogs/landscape/foundation.json` and `adoption/platforms/linux-wsl2.md`.
- `catalogs/landscape/component-evidence-matrix.json`,
  `docs/component-evidence-matrix.md`,
  `catalogs/landscape/new-host-grand-list.json`,
  `docs/new-host-grand-list.md`,
  `catalogs/foundation/final-catalog-20261001.json` and
  `docs/final-catalog-20261001.md` are generated foundation reports. Either lane
  rewrites them, but only with their `--write` commands (see the
  [hot-file protocol](#hot-file-protocol)). The final catalog's `--check` fails
  when the architecture edition, the blind selection, its cross-family record or
  their facts change, so a PR that edits an edition row runs
  `python3 scripts/final_catalog.py --write`; a move of the grand list alone is
  reported as drift and does not fail.

### Trading tests

A test module belongs to the lane of the code or receipts it loads. At
`6d9a7a5`, 60 modules under `tests/` load trading paths:

- `test_trading_gates.py` (`scripts/trading_gates.py`) and
  `test_native_nautilus_ci.py` (`scripts/verify_nautilus_ci.py`);
- modules that load code or receipts from `blueprints/us-equities/`:
  `adaptive_paper_hermetic.py`, `test_adaptive_*.py`, `test_alpaca_*.py`,
  `test_broad_universe_*.py`, `test_catalyst_*.py`, `test_historical_*.py`,
  `test_ibkr_*.py`, `test_lifecycle_*.py`, `test_mover_*.py`,
  `test_order_*.py`, `test_promotion_gate*.py`, `test_research_*.py`,
  `test_corporate_action_readiness.py`, `test_delisting_coverage.py`,
  `test_execution_realism.py`, `test_extreme_gainer_audit.py`,
  `test_financial_data.py`, `test_ingest_snapshot.py`,
  `test_memory_lifecycle.py`, `test_nanosecond_replay.py`,
  `test_native_faults_min.py`, `test_nautilus_equity_replay.py`,
  `test_pit_availability.py`, `test_point_in_time.py`,
  `test_security_identity.py`, `test_spy_parity.py`,
  `test_supply_chain_scan.py` and, added after `6d9a7a5`, the simulation
  modules `test_sim_*.py` (`test_sim_capacity.py`,
  `test_sim_engine_crosscheck.py`, `test_sim_crosscheck_hftbacktest.py` and
  `test_sim_paper_compare.py`).

Foundation tests that read trading files as data, such as `test_catalogs.py`,
`test_landscape.py`, `test_lane_packets.py` and `test_stack_lifecycle.py`,
stay with the tool they test. Coordinate before changing one for a trading
reason.

## Foundation files under trading paths

These foundation files live under `catalogs/us-equities/` and move out before
the trading lane migrates. All of them exist at `6d9a7a5`:

- `decision-index.json`, the validated repository decision union that
  `scripts/catalog_decisions.py --write` regenerates;
- `star-audit.json` and `star-audit.md`;
- `coverage.json`;
- `foundation-memory.json` and `foundation-memory.md`;
- `foundation-source-review.md`;
- `native-workflows.md`;
- `repository-index.md`.

A move also updates every reference to the moved file, including `AGENTS.md`,
`catalogs/README.md` and the scripts that read or write it.

Other foundation research also sits under trading paths and is not classified
yet, for example `catalogs/us-equities/architecture/foundation.json`,
`catalogs/us-equities/architecture/foundation-sources.json`,
`catalogs/us-equities/convergence-program/foundation.json` and `.md`, and
blueprints such as `blueprints/us-equities/memory-lifecycle/`, `workers/`,
`worker-supervision/`, `retrieval-evaluation/` and `state-recovery/`.
Classify them before the migration.

## Hot-file protocol

Put every shared hot-file edit in the branch's last commit, and rebase right
before merge. Never hand-merge `manifests/evidence.json`: take `main`'s copy
and re-register your own files.

```sh
git fetch origin
git diff --name-only --diff-filter=AM origin/main...HEAD  # files you added or changed
git diff origin/main...HEAD -- manifests/evidence.json     # entries you added
git rebase origin/main
git checkout origin/main -- manifests/evidence.json
python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, "scripts"); import host_receipts
for p in sys.argv[1:]: host_receipts.register_file(Path("."), p)' <files to register>
python3 scripts/component_matrix.py --write
python3 scripts/new_host_grand_list.py --write
python3 scripts/final_catalog.py --write
python3 scripts/validate.py
```

- Take both listings before the rebase. The checkout drops everything your
  branch added to `manifests/evidence.json`, so re-add your own `receipts[]`
  and `convergence_records[]` entries from the second listing.
- `<files to register>` means each file in the first listing that `main`'s
  manifest already lists, each new file under `evidence/` and any other new
  file your branch registered. Every tracked evidence file is listed today;
  `scripts/validate.py` enforces it for `evidence/receipts/` and
  `evidence/artifacts/`, and `scripts/host_receipts.py validate` for
  `evidence/hosts/`. Never pass `manifests/evidence.json` itself or the six
  generated reports above; their `--write` commands re-register them. Remove
  the entry of a file your branch deleted; `scripts/validate.py` reports it as
  `file missing`.
- If the rebase stops on `manifests/evidence.json`, run the commands after
  `git rebase` at that point, `git add` the results and run
  `git rebase --continue`. Otherwise fold the results into the last commit
  with `git commit --amend`. Push with `git push --force-with-lease`.
- Merging instead of rebasing is equally valid, and it is the path for a
  session under a no-force-push rule: `git merge origin/main`, and on a
  conflict in `manifests/evidence.json` run `git checkout --theirs
  manifests/evidence.json` (the merge's "theirs" is `main`), then the same
  registration and `--write` commands, `git add` the results, commit the
  merge and push normally. The squash merge into `main` keeps its history
  linear either way.
- If the branch changed `evidence/hosts/`, also run
  `python3 scripts/host_receipts.py validate`.

The registration command comes from
[the saturation sweep recipe](../recipes/saturation-sweep.md). It calls
`register_file` in `scripts/host_receipts.py`, which keeps `files[]` sorted.

## Labels and PRs

Every PR carries exactly one label: `lane:foundation`, `lane:trading` or
`lane:shared`. Use `lane:shared` when a PR changes paths owned by both lanes or
changes what a shared hot file says. Re-registering hashes and regenerating
reports through the protocol above does not by itself make a PR shared. A
`lane:shared` PR needs the other lane's acknowledgement, as a comment or review
on the PR, before merge. Branch names do not encode lanes; the label does. The
[PR template](../.github/pull_request_template.md) asks for the lane.

Merge with the checked and reviewed head pinned:

```sh
gh pr view <N> --json headRefOid --jq .headRefOid
gh pr checks <N> --required --json name,bucket --jq '"\(length) required checks, buckets: \(map(.bucket) | unique | join(","))"'
gh pr merge <N> --squash --match-head-commit <SHA>
```

- `<SHA>` is the full 40-character `headRefOid` the first command prints, read
  immediately before the merge. It must be the head on which the review
  completed. `gh pr checks --required` lists only the required checks that exist
  and keeps the latest run of each, so a check that failed and then passed shows
  as passed. Merge only when the second command prints the ruleset's number of
  required contexts (8 in `.github/main-ruleset.json`) with the single bucket
  `pass`; a shorter count means a required check has not started. Do not read the
  command's exit code as that verdict. It is 1 when any required check failed,
  even while others are pending, 8 when none failed and one is pending, and 0
  otherwise, so a cancelled or skipped required check also exits 0
  ([`checks.go` L248-252](https://github.com/cli/cli/blob/v2.101.0/pkg/cmd/pr/checks/checks.go#L248-L252)
  and [`aggregate.go` L72-88](https://github.com/cli/cli/blob/v2.101.0/pkg/cmd/pr/checks/aggregate.go#L72-L88)
  at gh v2.101.0: `CANCELLED` is bucket `cancel`, counted as neither failed nor
  pending), and with `--json` it exits 0 whatever the state. A description edit
  starts a new `validate.yml` run on the same head (its `pull_request` types
  include `edited`), so run it after the last edit. `gh` sends `<SHA>` as
  GitHub's `expectedHeadOid` ([gh pr merge](https://cli.github.com/manual/gh_pr_merge):
  "Commit SHA that the pull request head must match to allow merge"), and GitHub
  refuses the merge if the head has moved since; the mechanics are in the
  [decision record](decisions/2026-09-22-github-automation-closure.md).
- The rebase or merge of `main` that the [hot-file protocol](#hot-file-protocol)
  asks for comes before that read, because it makes a new head. If `main`
  changed a shared hot file after `<SHA>` (`git fetch origin`, then
  `git diff --name-only <SHA>...origin/main`), merge `main` again through the
  protocol, wait for the required checks on the new head and pin that head
  instead. The review carries over only if
  `git diff <SHA> <new head> -- <reviewed files>` prints nothing, where
  `<reviewed files>` leaves out `manifests/evidence.json` and the generated
  reports; otherwise review the new head. This is analogous to GitHub's
  stale-approval rule, which dismisses an approval when the approved diff changes
  ([available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-a-pull-request-before-merging)).
- The flag guards the head, not the base. The ruleset keeps strict up-to-date
  checks off, because concurrent sessions share `main`, and this User-owned
  repository cannot use a merge queue
  ([decision record](decisions/2026-09-22-github-automation-closure.md)). Two
  pull requests that each passed against an older `main` can therefore still
  break it together: "Status checks may fail after you merge your branch if
  there are incompatible changes with the base branch"
  ([loose required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-status-checks-to-pass-before-merging)).
  Merging `main` right before the merge narrows that window without closing
  it, and `validate.yml` runs again on every push to `main`.

## Coordination

When another live session owns an area, hand off instead of editing it.
Message that session with the paths, verified facts and boundaries where the
client supports it (for Claude Code peers, see
[Lane B of the cooperation recipe](../recipes/claude-codex-cooperation-lanes.md#lane-b-live-session-coordination)).
Mirror the handoff as a GitHub issue or PR comment so other clients, hosts and
later sessions see it.

## No CI lane check for now

No CI job checks lane labels or path ownership. There is one code owner, the
real conflicts live in the shared hot files, and the trading lane is moving
out. Revisit after two lane-crossing incidents.

## Existing boundary statements

This file adds interim path ownership only. The catalog boundary stays where
it is already stated:

- [catalogs/README.md](../catalogs/README.md): two maintained catalogs.
  General engineering does not inherit broker prerequisites; trading work
  reuses the foundation.
- The `domain_boundary` array in
  [catalogs/foundation/manifest.json](../catalogs/foundation/manifest.json):
  the components whose current accepted use is scoped to trading.
