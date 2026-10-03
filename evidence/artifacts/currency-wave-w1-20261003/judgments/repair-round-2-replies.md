# R642b thread replies — PR #642

Reviewed the five supplied threads against head `2d6f49233fa15e4993819c718d131bc6c10e5125` before changing files. The replies below describe the prepared working-tree repair. The coordinator still owns commit and push; HEAD and the ordinary Git index remain unchanged.

## observability/README.md:30

Fixed the live Collector row by separating deployed **0.161.0**, which owns the live traffic/restart/retained-storage evidence, from selected **0.162.0**. The selected row links its W1 scratch receipt and states that runtime acceptance remains pending. No service switch was performed. The decision records the corrected evidence boundary.

## adoption/bootstrap.md:584

Added the supported existing-host transition: retarget `extraKnownMarketplaces.claude-hud.source.ref` to `v0.10.0`, let the next native session synchronize the changed source, run `claude plugin marketplace update claude-hud`, then `claude plugin update claude-hud@claude-hud --scope user`, reload, and verify the installed commit against `75683c6de1ac07f6bbef00d739001679dba0740c`.

Sources are the official [update instructions](https://code.claude.com/docs/en/plugins/install#update-plugins-now), [marketplace update reference](https://code.claude.com/docs/en/plugins/cli-reference#plugin-marketplace-update), [source synchronization reference](https://code.claude.com/docs/en/plugins/loading#plugins-and-marketplaces-that-arent-on-disk-at-session-start), and installed Claude Code 2.1.288 help/tagged changelog. Marketplace refresh follows the configured tag, so the ref change must precede the updates. Native version/help ran only with temporary `HOME`, `CLAUDE_CONFIG_DIR` and cwd; their actual output is retained in `native-checks.json#/r642b_claude_hud_upgrade`. The bootstrap and decision explicitly say **documented, host verification pending**. A safe offline GitHub-tag transition was not verified, and the host's real configuration/plugins were not changed.

## evidence/artifacts/currency-wave-w1-20261003/native-checks.json:44

Re-ran all four exact integration commands from their W1 scratch installs after completing every mcporter pin-site reversion and the eight-component PR metadata correction. Each command's shell recorded start/end with `date -u +%Y-%m-%dT%H:%M:%SZ`. Fresh commands, original stdout/stderr, hashes and times are retained under `commands/*-r642b-timed`, and both affected receipts point to these entries. The four original null-time entries remain labelled `earlier_untimed_attempt`; interim timed attempts also remain preserved. The decision cites the final timed runs below, not the original untimed attempts.

| Final run on 2026-10-03 | Start UTC | End UTC | Exit | Returned signal |
| --- | --- | --- | --- | --- |
| Inspector tools/list | 08:23:59 | 08:24:00 | 0 | Six tool names: set_tool_tier, announce_model, jcodemunch_guide, order, menu, route |
| Inspector tools/call | 08:24:00 | 08:24:01 | 0 | order/get_session_stats; isError false; visible_tools 6 |
| Inspector unknown-tool control | 08:24:01 | 08:24:02 | 5 | Expected tool_not_found |
| mcporter 0.14.2 canary | 08:24:02 | 08:24:03 | 0 | visible_tools 6; compatibility-attempt evidence for the hold only |

## manifests/stack.json:658

R642 had added current-version pointers to the dated OpenResearch/Worktrunk document, but their recipe-map entries still selected its historical installation section. The canonical `adoption/manifest.json` mappings for OpenResearch, Worktrunk and Syft now select `recipes/README.md`, carrying current pins **0.2.15**, **0.80.0** and **1.54.0**, primary sources, bounded evidence and previous-version rollback references. Each audit row's `native_integration.recipe_document` mirrors that same path. The new foundation Syft archive recipe uses its W1 native archive/checksum/extraction commands. The trading owner's dated 1.52.0 recipe remains untouched and is no longer the canonical current mapping.

## adoption/pins-linux-x86_64.json:136

Held mcporter at accepted Linux **0.14.1**, restoring its stack row, audit row, Linux artifact/hash/install row and current installation/CI references from `git diff origin/main`. macOS retains its independently accepted **0.13.13** pin; its Linux comparison and lag-test receipt return to 0.14.1. Additional current sites repaired include `scripts/native_token_ci.py`, `tools/token-report/README.md`, and `tests/test_adoption_bootstrap_macos.py`. Generated reports reflect the hold. The snapshot selects 0.14.1, records its freshly verified exact source commit, accurately reports latest v0.14.2, and preserves the W1 attempt as a dated observation.

The 0.14.2 receipt is now `compatibility_attempt`, linked from no current pin or audit acceptance row. It retains the dependency finding and the ad-hoc canary solely as evidence for the hold. A fresh offline/read-only `npm ls --global --prefix <qualification-root>/mcporter/prefix --all --json` corroborated the finding: exit **1**, `ELSPROBLEMS`, invalid bundled core **2.2.0** beside resolved server **2.3.0**. Its native problems field, stderr, times and original stdout hash are retained in that receipt. Reopen only after a consistent resolved tree and qualified persistent daemon/serve role, including use, restart and recovery. The [PR title and description](https://github.com/seathatflowsinourveins/native-agent-stack/pull/642) now count **eight moves** and list mcporter as held; metadata was re-read to verify the correction.

## Acceptance

The actual returned command output and failed conditions are retained in `evidence/artifacts/currency-wave-w1-20261003/review-bot-repair-checks.json`. All changed evidence was re-registered with `host_receipts.register_file`; `manifests/evidence.json` was the final repository file written. The component matrix and grand list were regenerated through their native write commands; the ecosystem build remained check-only.

| Command | Exit | Decisive returned result |
| --- | --- | --- |
| `python3 scripts/validate.py` | 0 | passed; 69 components, 196 receipts, 9,423 hashed files |
| `python3 scripts/validate_convergence.py --all-recorded --root . --json` | 0 | valid true |
| `python3 scripts/landscape.py --root .` | 0 | status passed; 32 layers, 69 explained components |
| Required nine-module unittest command below | 0 | Ran 325 tests; OK (skipped=3) |
| `python3 scripts/validate_catalogs.py` | 0 | Catalog structure and evidence classes validated |
| `python3 scripts/validate_foundation.py --root . --json` | 0 | ok true; errors [] |
| `python3 scripts/component_matrix.py --check` | 0 | 32 rows; checked |
| `python3 scripts/new_host_grand_list.py --check` | 0 | passed; 32 layers, 66 winners |
| `python3 scripts/build_ecosystem.py --check` | 0 | deterministic build passed; existing dated pin drift stays explicit |
| Three pre-push registry tests below | 0 | Ran 3 tests; OK |
| `gitleaks protect --staged --redact` with temporary native Git index and pinned 8.30.1 executable | 0 | Final scan: ~208,358 bytes; no leaks found |
| `git diff --check` | 0 | No whitespace errors |

Required suite, unchanged:

```sh
python3 -B -m unittest tests.test_stack_lifecycle tests.test_render_config tests.test_adoption_contract tests.test_grand_dashboard tests.test_landscape_sweep_harness tests.test_observability_tool_names tests.test_observability_run_correlation tests.test_sdk_usage_scope tests.test_blind_checkout
```

It ran through native `uv run --no-project --python 3.13 --with PyYAML==6.0.3` under installed Bubblewrap 0.9.0: read-only host root, writable owned worktree/task cache, read-only worktree `.git`, and a private `/tmp`. The existing temporary-root Git markers caused the first 11 errors; choosing another writable root retained that condition. The initial private-tmpfs wrapper made the worktree read-only and correctly refused 35 render-fixture writes. Those failed runs are retained. The final supported wrapper passed the full suite without editing tests or removing other-worker markers. The three optional skips concern an installed Context Mode security build selector, real Bash 3.2 and ShellCheck.

Pre-push command:

```sh
python3 -B -m unittest tests.test_osv_lockfile_coverage.LockfileInventoryTests.test_every_tracked_lockfile_and_manifest_is_listed tests.test_blind_checkout.RepositoryClassificationTests.test_every_blueprint_value_under_a_label_key_is_classified tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests.test_all_published_workflows_are_listed_and_covered
```

The staged scan used `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY` and read-only alternate repository objects in task scratch. Native `read-tree HEAD`, `git add -A`, scanning, and `git reset -- .` touched only that temporary index/object directory. The ordinary index hash was checked unchanged after cleanup. No commit or push was performed. All configuration-owner new-WSL files and `blueprints/us-equities/` retain their bytes.

## R642b per-component changed-file map

Paths are repository-relative. The dated decision/evidence registration and check artifact cover the repair as a whole.

| Component/scope | Files changed by R642b |
| --- | --- |
| Collector | observability/README.md |
| Claude HUD | adoption/bootstrap.md; evidence/artifacts/currency-wave-w1-20261003/native-checks.json |
| mcp-inspector | evidence/receipts/mcp-inspector-290-qualification-20261003.json; evidence/artifacts/currency-wave-w1-20261003/native-checks.json |
| OpenResearch, Worktrunk, Syft | adoption/manifest.json; blueprints/token-native-focus/saturation-audit.json; recipes/README.md |
| mcporter hold | manifests/stack.json; catalogs/landscape/upstream-snapshot.json; blueprints/token-native-focus/saturation-audit.json; adoption/pins-linux-x86_64.json; adoption/pins-macos-arm64.json; adoption/bootstrap.md; adoption/platforms/linux-wsl2.md; docs/token-efficiency-stack.json; recipes/README.md; scripts/native_token_ci.py; tests/test_adoption_bootstrap_macos.py; tools/token-report/README.md; evidence/receipts/mcporter-0142-qualification-20261003.json; evidence/artifacts/currency-wave-w1-20261003/native-checks.json |
| Generated reports | catalogs/landscape/new-host-grand-list.json; docs/new-host-grand-list.md |
| Shared decision/acceptance/registration | docs/decisions/2026-10-03-currency-wave-w1.md; evidence/artifacts/currency-wave-w1-20261003/review-bot-repair-checks.json; manifests/evidence.json |
| jcodemunch-mcp, playwright-cli | No additional component changes in R642b; their W1 moves are preserved |

## Final worktree status

```text
 M adoption/bootstrap.md
 M adoption/manifest.json
 M adoption/pins-linux-x86_64.json
 M adoption/pins-macos-arm64.json
 M adoption/platforms/linux-wsl2.md
 M blueprints/token-native-focus/saturation-audit.json
 M catalogs/landscape/new-host-grand-list.json
 M catalogs/landscape/upstream-snapshot.json
 M docs/decisions/2026-10-03-currency-wave-w1.md
 M docs/new-host-grand-list.md
 M docs/token-efficiency-stack.json
 M evidence/artifacts/currency-wave-w1-20261003/native-checks.json
 M evidence/receipts/mcp-inspector-290-qualification-20261003.json
 M evidence/receipts/mcporter-0142-qualification-20261003.json
 M manifests/evidence.json
 M manifests/stack.json
 M observability/README.md
 M recipes/README.md
 M scripts/native_token_ci.py
 M tests/test_adoption_bootstrap_macos.py
 M tools/token-report/README.md
?? evidence/artifacts/currency-wave-w1-20261003/review-bot-repair-checks.json
```

```text
 adoption/bootstrap.md                              |  26 +-
 adoption/manifest.json                             |   6 +-
 adoption/pins-linux-x86_64.json                    |   8 +-
 adoption/pins-macos-arm64.json                     |   2 +-
 adoption/platforms/linux-wsl2.md                   |   2 +-
 .../token-native-focus/saturation-audit.json       |  29 +--
 catalogs/landscape/new-host-grand-list.json        |  14 +-
 catalogs/landscape/upstream-snapshot.json          | 105 +++++++-
 docs/decisions/2026-10-03-currency-wave-w1.md      | 140 +++++++++--
 docs/new-host-grand-list.md                        |   2 +-
 docs/token-efficiency-stack.json                   |   4 +-
 .../currency-wave-w1-20261003/native-checks.json   | 268 ++++++++++++++++++++-
 .../mcp-inspector-290-qualification-20261003.json  |   7 +-
 .../mcporter-0142-qualification-20261003.json      |  35 ++-
 manifests/evidence.json                            |  79 +++---
 manifests/stack.json                               |  12 +-
 observability/README.md                            |   3 +-
 recipes/README.md                                  |  32 ++-
 scripts/native_token_ci.py                         |   2 +-
 tests/test_adoption_bootstrap_macos.py             |   2 +-
 tools/token-report/README.md                       |   4 +-
 21 files changed, 657 insertions(+), 125 deletions(-)
```

The diff stat excludes the new, untracked `review-bot-repair-checks.json`; the staged secret scan included it. All modifications are unstaged after temporary-index cleanup.
