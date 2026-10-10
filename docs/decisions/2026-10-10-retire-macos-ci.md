# Retire adoption macOS CI (2026-10-10)

**Status:** selected by the owner on 2026-10-10, around 02:28 UTC; the
implementation is subject to the normal PR review and merge checks.

## Decision and scope

Remove `bootstrap-macos`, `bootstrap-macos-brew` and `validate-macos` from
`.github/workflows/adoption-bootstrap.yml`. Remove their macOS path classifier,
`MACOS_PATTERNS` drift guard, mode outputs, and tests whose contract requires
those jobs. The remaining `changes` job selects the Linux bootstrap on pull
requests using the existing input patterns. Missing SHAs and failed diffs keep
its fail-open behavior. Linux still runs on eligible main pushes, the daily
06:47 UTC schedule, and manual dispatch.

The day-to-day environment the owner uses is WSL/Linux. Maintaining an
additional advisory adoption lane distracts from that environment. The macOS
jobs were reported red during 2026-10-07 through 2026-10-09; the retained
[portability repair record](2026-10-09-validate-macos-portability.md) cites a
specific native failure and distinguishes its measured failures from the
broader reported window. This decision does not claim a new survey of all runs.

GitHub documents standard GitHub-hosted runner use as free for public
repositories. These standard macOS jobs therefore offered no runner-minute
bill to eliminate. The benefit is a smaller maintenance obligation and more
attention for the environment in use. Larger runners and storage have separate
billing rules; no savings estimate is claimed for them.

The daily macOS proposal [#914](https://github.com/seathatflowsinourveins/native-agent-stack/pull/914)
is superseded. Its close comment links to the implementation PR for this
decision. Required status contexts stay as already configured; the removed
jobs were advisory and outside that required set.

## Retained portability and evidence

The portable repairs in
[#948](https://github.com/seathatflowsinourveins/native-agent-stack/pull/948)
remain: resolved SDK containment/relative references, the stricter independent
source-policy guard, canonical disposable fixture roots and the other portable
interfaces. Darwin/capability skip guards remain in the tests. The macOS
bootstrap script, platform profile, manual instructions and portable installer
tests remain available.

Past hosted receipts and their recorded run IDs remain historical evidence.
The retained hosted-smoke metadata is marked retired; it does not advertise an
active job or change the profile's drafted acceptance state. Removing CI gives
no new native macOS acceptance result. WSL/Linux runs and simulations continue
to carry their own evidence limits.

This retirement is bounded to the three adoption jobs. The separate
`hardware-profile-smoke.yml` diagnostic has its own owner and scope. Historical
records and artifacts are preserved.

The generated WSL handbook records the normalized adoption manifest digest.
Its maintained builder refreshes that reference and the output receipt when
the historical hosted-smoke row gains retirement metadata. The resolver's
repository fixture also stops assuming the retired Mac job supplies a literal
tests directory. Its workflow-derived enforcement and advisory read-inventory
implementation is unchanged.

## Superseded decisions

This policy replaces the adoption macOS job/scope/coverage requirements in:

- [2026-10-03-macos-ci-scope.md](2026-10-03-macos-ci-scope.md).
- [2026-10-03-macos-full-suite-coverage.md](2026-10-03-macos-full-suite-coverage.md).
- [2026-10-05-macos-ci-advisory.md](2026-10-05-macos-ci-advisory.md).

Those documents receive dated forward pointers. Their earlier measurements,
implementation history and native failure artifacts remain available. The
native-after-run expectation in the 2026-10-09 repair record also ends with
retirement of these jobs; its portable code changes remain in force.

## Revisit

Reconsider maintained macOS CI when the owner requests it, or when a macOS
adopter appears who needs that coverage. Establish the new scope and native
validation evidence in a fresh decision at that time.

## Validation and sources

The implementation uses the repository's existing workflow structure and
keeps the Linux event/path contracts. Local validation uses the CI-pinned
`kjanat/actionlint` 1.17.0 and `zizmor` 1.30.1, the workflow-policy and hardening
modules, affected portable/adoption tests, and FULL evidence validation. Exact
commands and measured outcomes belong to the implementation PR; a syntax or
fixture check does not establish a native macOS run.

## SOTA sources

- GitHub, [GitHub Actions billing — Free use of GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions#free-use-of-github-actions),
  read **2026-10-10**: standard GitHub-hosted runners are free for public
  repositories; larger runners are charged separately.
- GitHub, [GitHub-hosted runners](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners),
  read **2026-10-10**: the supported hosted-runner model and its public-repository
  use. This decision retires the existing job graph rather than replacing the
  runner platform.
- Maintained repository source at
  [`a56f85e8397751d36fdbdc03910f15ac877ad00c`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/a56f85e8397751d36fdbdc03910f15ac877ad00c):
  `.github/workflows/adoption-bootstrap.yml`, the workflow contract tests and
  the landed #948 portable repairs.
- The same maintained source pin's
  scripts/build_new_wsl_handbook.py, --write/--check, and
  blueprints/runtime-workers/openhands/resolver/push_gate.py,
  derive_ci_protected: supported handbook regeneration and the distinction
  between workflow-named protection and advisory read-derived inventory.
- CI tool pins: `.github/workflows/validate.yml` selects
  [`kjanat/actionlint` v1.17.0](https://github.com/kjanat/actionlint/releases/tag/v1.17.0)
  with its SHA256-verified release archive; `.github/requirements-ci.txt`
  checksum-locks [`zizmor` 1.30.1](https://github.com/zizmorcore/zizmor/releases/tag/v1.30.1).
  The installed clients report those same versions.
