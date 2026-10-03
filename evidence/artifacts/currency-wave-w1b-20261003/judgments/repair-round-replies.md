# R645 — PR #645 review replies and handoff

Branch: `foundation/currency-w1b-20261003`. Base HEAD remains `081e4ae68af70c7463620251a803c4e73f04efb8`. The R645 repairs are uncommitted; no commit or push was performed. Replies below are prepared for the coordinator to post after committing the repair. Branch links resolve the repaired content after that publication.

This bounded unit corrects the foundation observation/browser evidence supporting US-equities research and historical simulation. All twelve required checks pass, the final publication check passes, and the final staged Gitleaks scan passes. Host/browser acceptance remains within the recorded limits.

## Bot thread 1 — agent-browser receipt kind

Changed `agent-browser-0382-qualification-20261003` to `compatibility_attempt`, a kind defined by `scripts/validate.py` `RECEIPT_KINDS`. The receipt index and audit row now use that same kind. The stack freshness text, audit functional/lifecycle scopes and decision distinguish 0.38.2 installation/version/offline readiness from the retained browser workflow evidence that predates this pin. Browser installation, Chrome launch and the fixture workflow remain untested for 0.38.2. See [the corrected receipt](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/evidence/receipts/agent-browser-0382-qualification-20261003.json) and [R645 acceptance](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/evidence/artifacts/currency-wave-w1b-20261003/acceptance.json).

## Bot thread 2 — Grafana restart evidence

The storage/viewing row now separates selected Grafana 13.2.3 from deployed 13.2.2 and explicitly limits host restart acceptance to 13.2.2. It describes 13.2.3 as isolated synthetic qualification. `check_persistence.py` and host service activation were not run. See [the corrected observation row](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/observability/README.md).

## Finding 1 — acceptance record and final validate.py

Replaced the decision’s handoff-report pointer with an in-repository acceptance link and added the same path to each receipt’s `data.repository_acceptance`. `acceptance.json` now retains R645’s required commands, exit codes, actual returned stdout/stderr and hashes, failed attempts, the successful retry and a final `validate.py` result for base head `081e4ae68` plus these uncommitted repairs. After storing that result, `register_file` refreshed the artifact and a last read-only validation returned the same passed output. See [acceptance.json](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/evidence/artifacts/currency-wave-w1b-20261003/acceptance.json).

## Finding 2 — retained stdout provenance

Each receipt’s `data.retained_stdout` names its retained files and producing commands. Grafana names the W1-r2 namespace-wrapper `lifecycle.sh fresh`, `upgrade` and `queries` commands. Agent-browser names the W1-r2 0.38.1 control `skills list` and W1b 0.38.2 `skills list` commands. `integration-commands.json.retained_output_provenance` also records the earlier control and explicitly says it was not a W1b execution. All five stdout files retain their original bytes; the skills files remain byte-identical at 898 bytes each. See [the provenance record](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/evidence/artifacts/currency-wave-w1b-20261003/integration-commands.json).

## Finding 3 — unresolved “above” reference

The Grafana receipt and its evidence-index mirror now name stat/table/Loki issues #132901, #132502 and #132879 directly. Browser rendering remains untested. See [the corrected limitation](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/evidence/receipts/grafana-1323-qualification-20261003.json).

## Finding 4 — agent-browser install_note

The note now says an isolated-prefix npm install of `agent-browser@0.38.2` exited 0 and points to the exact recorded command in `agent-browser/qualification-record.json#/facts/install`. It explicitly states that the bootstrap `install_npm` route was not run. See [the corrected pin note](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/adoption/pins-linux-x86_64.json).

## Finding 5 — excerpt lengths and partial path

The decision and review record now describe the original 600-character cutoff and the shorter published copies after host-path sanitization, without claiming every published excerpt is exactly 600 characters. The trailing incomplete ` /ho` fragment was removed from the Dagu excerpt. Complete W1-r2 judge records remain separate from these original W1 excerpts. See [the corrected excerpt record](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/evidence/artifacts/currency-wave-w1b-20261003/review-decisions.json).

## Finding 6 — scoped_refreshes checked_at

Set `scoped_refreshes[0].checked_at` to `2026-10-03T07:15:38.637092+00:00`, the maximum `ended_at` of the eight retained API checks. The later record-write timestamp is no longer labelled as the check time. Earlier dated observations remain unchanged. See [the corrected snapshot](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/catalogs/landscape/upstream-snapshot.json).

## Finding 7 — hot-file ordering and lane acknowledgement

Coordinator-owned under R645. No commit rewriting, rebase, push, label change or trading-lane acknowledgement was attempted. Before merge, the coordinator must place all shared hot-file hunks in the last commit, rebase/re-register against the current main, apply the required lane label and obtain the trading acknowledgement for the final head. The repaired stack/evidence files are left ready for that protocol.

## Finding 8 — anonymous Viewer access

Corrected the backend README to “Sign-up is disabled; anonymous Viewer access is enabled on loopback” and linked Install and configure. It now agrees with the unchanged template’s `allow_sign_up=false`, anonymous `enabled=true` and `org_role=Viewer`. The decision’s owner-follow-up statement was updated to reflect the completed correction. See [the corrected access documentation](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/observability/backends/README.md).

## Finding 9 — verification gaps and coordinator checks

The missing local `validate.py` result is now recorded and the final stored state was validated again. The required five-module command passes 264 tests with 3 skips; all three registry tests pass individually with no skips. Generated reports were regenerated using their native write commands and remain byte-identical. `build_ecosystem.py --check` still passes while reporting 12 architecture-pin drift rows in excluded configuration-owner/trading editions. Full-suite validate-macos/PR-head CI, the PR’s non-empty SOTA sources section, labels, acknowledgement and pre-merge hot-file/rebase protocol remain coordinator checks. Configuration-owner and trading paths were not edited.

## Finding 10 — Sol should-fix: CVE reachability

Applied repository-provisioning scope explicitly to all three CVE entries. Missing alert provisioning does not prove the absence of database-backed rules; anonymous Viewer and disabled sign-up do not prove there are no existing Editors; and provisioned proxy datasources without stored credentials do not prove the absence of UI-created shared dashboards, sharing tokens or additional datasources. The record now names the supported upgrade’s preserved database and makes inspection of existing users/Editor memberships, alert rules, shared dashboards/tokens and datasource/credential configuration an open host item. The receipt and decision carry the same limitation. Recorded native outputs and the independent judge text remain unchanged. Fresh release/GHSA API outputs are retained in acceptance.json. See [the corrected qualification record](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/evidence/artifacts/currency-wave-w1b-20261003/grafana/qualification-record.json).

## Finding 11 — independent publisher-network verification gap

No repository defect or pin change was requested for this reviewer-local network gap. R645’s read-only GitHub release and GHSA source checks succeeded and are retained, but no new archive download, npm integrity check or signature verification is claimed. The earlier publisher/digest evidence remains in each qualification receipt’s `data.artifact.integrity_source`, which names the upstream artifact/checksum URLs, digests and retained command results. Those retained integrity observations are distinct from R645’s source checks and repository acceptance.

## Acceptance commands

Each command below exited 0. Exact returned outputs and their hashes are retained in [acceptance.json](https://github.com/seathatflowsinourveins/native-agent-stack/blob/foundation/currency-w1b-20261003/evidence/artifacts/currency-wave-w1b-20261003/acceptance.json). `TMPDIR` was set to a writable workspace directory; the five-module retry used the owned builds workspace outside Git repositories.

| Command | Exit | Decisive output |
| --- | --- | --- |
| `rtk python3 scripts/validate.py` | 0 | passed; final stored state: 69 components, 189 receipts, 9427 hashed files |
| `rtk python3 scripts/validate_convergence.py --all-recorded --root . --json` | 0 | valid=true; recorded experiments have no reported errors |
| `rtk python3 scripts/landscape.py --root .` | 0 | status=passed; coverage/reference integrity |
| `rtk python3 -B -m unittest tests.test_stack_lifecycle tests.test_render_config tests.test_adoption_contract tests.test_grand_dashboard tests.test_landscape_sweep_harness` | 0 | Ran 264 tests; OK (skipped=3) |
| `rtk python3 scripts/validate_catalogs.py` | 0 | Catalog structure and evidence classes validated |
| `rtk python3 scripts/validate_foundation.py --root . --json` | 0 | ok=true; errors=[] |
| `rtk python3 scripts/component_matrix.py --check` | 0 | status=checked; rows=32 |
| `rtk python3 scripts/new_host_grand_list.py --check` | 0 | status=passed; layers=32; winners=66 |
| `rtk python3 scripts/build_ecosystem.py --check` | 0 | status=passed; 12 declared architecture_pin_drift rows |
| `rtk python3 -B -m unittest tests.test_osv_lockfile_coverage.LockfileInventoryTests.test_every_tracked_lockfile_and_manifest_is_listed` | 0 | Ran 1 test; OK; no skips |
| `rtk python3 -B -m unittest tests.test_blind_checkout.RepositoryClassificationTests.test_every_blueprint_value_under_a_label_key_is_classified` | 0 | Ran 1 test; OK; no skips |
| `rtk python3 -B -m unittest tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests.test_all_published_workflows_are_listed_and_covered` | 0 | Ran 1 test; OK; no skips |

Native report preparation also exited 0: `rtk python3 scripts/component_matrix.py --write` and `rtk python3 scripts/new_host_grand_list.py --write`. Their returned written counts are retained in the acceptance artifact.

## Last stored-state validation and staged secret scan

The last read-only validation ran after recording the passed validation output and the final `register_file` update. Exit 0; actual returned output:

```text
{"components": 69, "hashed_files": 9427, "profiles": 4, "receipts": 189, "status": "passed"}
Integrity and scope checks only; no live provider or GPU execution.
```

The last staged scan used the installed upstream Gitleaks 8.30.1 binary and supported repository pre-commit flags: `git --pre-commit --staged --redact --no-banner --no-color --config <WORKTREE>/.gitleaks.toml`. Its temporary index and writable object directory were under the owned builds workspace, with read-only access to the common objects. Exit 0; 16 staged files; actual returned output:

```text
4:42AM INF 0 commits scanned.
4:42AM INF scanned ~185685 bytes (185.68 KB) in 181ms
4:42AM INF no leaks found
```

The original index SHA-256 was identical before and after the final scan: `e9fc059ddaa60016bb2fda70dd5ee2bbdcf394cd7f8cea6d9e032e848684033a`. The working index and HEAD were not changed.

The acceptance artifact preserves both failed host-launcher help attempts, the 140-failure/3-error test run caused by the outside-repository guard, and the failed publication check caused by scratch files inside the checkout. The succeeding retries used native commands and corrected scratch locations; no test, harness or validator implementation was changed.

## Complete repair file inventory

The 16 files below are the full repair inventory. Shared rows apply to both selected components and the R645 review/verification handoff.

| Component / purpose | File |
| --- | --- |
| agent-browser | `adoption/pins-linux-x86_64.json` |
| agent-browser | `blueprints/token-native-focus/saturation-audit.json` |
| agent-browser | `evidence/receipts/agent-browser-0382-qualification-20261003.json` |
| agent-browser | `manifests/stack.json` |
| Grafana | `evidence/artifacts/currency-wave-w1b-20261003/grafana/qualification-record.json` |
| Grafana | `evidence/receipts/grafana-1323-qualification-20261003.json` |
| Grafana | `observability/README.md` |
| Grafana | `observability/backends/README.md` |
| Shared review / validation | `catalogs/landscape/upstream-snapshot.json` |
| Shared review / validation | `docs/decisions/2026-10-03-currency-wave-w1b.md` |
| Shared review / validation | `evidence/artifacts/currency-wave-w1b-20261003/integration-commands.json` |
| Shared review / validation | `evidence/artifacts/currency-wave-w1b-20261003/review-decisions.json` |
| Shared review / validation | `evidence/artifacts/currency-wave-w1b-20261003/acceptance.json` |
| Shared review / validation | `manifests/evidence.json` |
| Shared review / validation | `evidence/artifacts/currency-wave-w1b-20261003/r645/required-unittests-failed.stdout.txt` |
| Shared review / validation | `evidence/artifacts/currency-wave-w1b-20261003/r645/required-unittests-failed.stderr.txt` |

The two new files under `r645/` retain sanitized failed-test stdout/stderr. Every changed/added evidence file was registered with `scripts/host_receipts.py` `register_file`, and `manifests/evidence.json` was written last. Receipt/index/audit kinds and limitations are synchronized.

## Working-tree handoff

`rtk git status --short` (exit 0):

```text
 M adoption/pins-linux-x86_64.json
 M blueprints/token-native-focus/saturation-audit.json
 M catalogs/landscape/upstream-snapshot.json
 M docs/decisions/2026-10-03-currency-wave-w1b.md
 M evidence/artifacts/currency-wave-w1b-20261003/acceptance.json
 M evidence/artifacts/currency-wave-w1b-20261003/grafana/qualification-record.json
 M evidence/artifacts/currency-wave-w1b-20261003/integration-commands.json
 M evidence/artifacts/currency-wave-w1b-20261003/review-decisions.json
 M evidence/receipts/agent-browser-0382-qualification-20261003.json
 M evidence/receipts/grafana-1323-qualification-20261003.json
 M manifests/evidence.json
 M manifests/stack.json
 M observability/README.md
 M observability/backends/README.md
?? evidence/artifacts/currency-wave-w1b-20261003/r645/
```

`rtk git diff --stat` (exit 0; tracked-file statistics, with the two added stdout/stderr files listed in the inventory above):

```text
 adoption/pins-linux-x86_64.json                    |   2 +-
 .../token-native-focus/saturation-audit.json       |  10 +-
 catalogs/landscape/upstream-snapshot.json          |   2 +-
 docs/decisions/2026-10-03-currency-wave-w1b.md     |  75 ++++-
 .../currency-wave-w1b-20261003/acceptance.json     | 320 ++++++++++++++++++++-
 .../grafana/qualification-record.json              |  24 +-
 .../integration-commands.json                      |  12 +-
 .../review-decisions.json                          |   4 +-
 .../agent-browser-0382-qualification-20261003.json |  19 +-
 .../grafana-1323-qualification-20261003.json       |  31 +-
 manifests/evidence.json                            |  69 +++--
 manifests/stack.json                               |   2 +-
 observability/README.md                            |   2 +-
 observability/backends/README.md                   |   3 +-
 14 files changed, 512 insertions(+), 63 deletions(-)
```

`rtk git diff --check` exited 0 with no output. No commit or push was performed.

Completeness critic: both bot threads and every supplied finding have a reply. Receipt classification/mirrors, all five retained stdout provenance entries, selected/deployed Grafana scope, all three CVE entries, excerpt sanitization, timestamps, anonymous Viewer documentation, acceptance links and registration were checked. The next host lifecycle sweep retains the live Grafana database inspection and agent-browser 0.38.2 browser use/cleanup qualification. Coordinator-owned merge ordering, labels, acknowledgement and full-suite CI are explicitly handed back.
