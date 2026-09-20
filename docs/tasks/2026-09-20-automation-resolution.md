# Resolve reviewed GitHub Action upgrades

Scope: finish the two initial Dependabot proposals after PR #26 and keep the
catalog's automation status current. Base `d0fe136c218fedff93c93ac674e302ae19b2d924`;
one isolated automation writing checkout, coordinated with the foundation owner.
No native services, recovery trials, accounts, models, runtime pins or trading
behavior are changed. The [manifest](../../catalogs/foundation/automation.json)
is the compact inventory; the [handbook](../github-automation.md) defines ownership.

## Demonstrated problem and retained failures

- [PR #29](https://github.com/seathatflowsinourveins/native-agent-stack/pull/29)
  proposes setup-python 7.0.0. [Validation 35541399411](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35541399411)
  failed with `.github/workflows/native-offhost-app-state.yml: SHA-256 mismatch`
  and a byte-length mismatch after changing its two action pins.
- [PR #30](https://github.com/seathatflowsinourveins/native-agent-stack/pull/30)
  proposes setup-go 7.0.0. [Validation 35541500332](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35541500332)
  failed with `.github/workflows/native-offhost-restore.yml: SHA-256 mismatch`,
  its byte-length mismatch, and `.github/workflows/native-service-reboot.yml:
  SHA-256 mismatch`.

These failures correctly require review of changed published files. No setup
action incompatibility was established by those failures. The original bot
commits `045c857402879a5c44d96a8d501574a23e5ed0d5` and
`7f205a90eae0438f8df53a80b68ce4f053c7e568` are retained as cherry-picked commits
in one coordinated resolution. Only reviewed current files get new registry
hashes; historical execution receipts retain their original source revisions.

## Source review and selection

The manifest records exact revisions, primary links, supported inputs, reused
upstream success runs and acceptance commands. Python and Go v7 migrate their
internals to ESM while retaining our selected interfaces and Node 24 runtime.
Python removes an unused `pip-install` input: its source/release notes are more
precise than the README's broad no-input-change wording. Go's two old pins resolve
to v6.4.0 and v6.5.0; the old reboot workflow comment claiming Dagu's exact CI pin
was stale and is replaced with the selected action version only.

The official Node v7 action is selected in the existing token-tool workflow,
preserving Node 24 and disabled package-manager caching. Its release includes
ESM, cache-output and authentication handling changes. Existing hosted tool
fixtures provide the relevant repository integration check; no model usage or
package-publishing credential flow is introduced.

The bounded new Python/Go lane uses unchanged upstream verifier scripts fetched
at the exact action revisions and checked against reviewed SHA-256 values before
execution. Python checks its version and the action-output executable path. Go
checks both selected versions; a separate exact `GOVERSION` assertion compensates
for the upstream helper's regex match. Unchanged Go `fmt` tests exercise compilation
and execution with toolchain switching and dependency proxies disabled. These
are setup/toolchain integration evidence, not a recovery replay or upstream
full-suite qualification. Relevant upstream full runs are reused, not rerun.

## Verification and observations

Hosted upgrade qualification is pending on the review branch. Record the run,
source, returned outputs, elapsed times and artifact IDs after it completes.
Local verification on 2026-09-20 passed: actionlint 1.7.12 exited 0 with empty
output; strict offline zizmor 1.30.1 exited 0 with `[]`. The five integrity,
catalog, foundation, recorded-convergence and explorer validators exited 0
(68 components, 1024 hashed files, 4 profiles, 100 receipts). The existing
`test_validate`, `test_workflow_security`, `test_ecosystem_manifest` and
`test_foundation_catalog` suites ran 95 tests in 2.771 seconds and returned `OK`.
These are local structural and failure-mode checks, not hosted execution.
The existing publication round trip from PR #26 remains valid for its unchanged
workflow and named archive; it is now linked directly from the catalog. No second
publication or unchanged recovery qualification is needed for these pin changes.

Failure evidence remains in the original runs and the new jobs' `always()`
fourteen-day artifacts. GitHub logs are the fallback for setup/download/upload
failures before files exist. GitHub-hosted runner disposal owns cleanup. These
jobs have read-only repository permissions and no checkout or native state.

Independent review inspected exact helper bytes/argv, permissions, pipefail,
cancellation and failure retention. Its Node evidence concern is resolved by
requiring the changed existing native-token workflow to pass at the new pin;
the result is pending until that run completes.

## Ownership and rollback

One existing daily Codex task owns upstream research; Dependabot owns Action pin
proposals. No gh-aw, Renovate, additional schedule or paid engine is activated.
The automation maintainer integrates this coordinated replacement and then
closes the superseded proposals. Future upgrades follow the same reviewed-hash
procedure, retaining source/interface review and applicable evidence.

Rollback reverts the affected action pins and compatibility workflow together
with their reviewed registry entries. Keep required validation and historical
evidence intact. The main ruleset and publication workflow are unchanged here.
No measured research gain or token savings is claimed.
