# Decision: keep the LongMemEval agentmemory lock under non-manifest names (2026-09-25)

**Decided in:** the pull request for host request #274 that adds
`blueprints/memory-stack/longmemeval/`, written by the Mac coordinator's session. Merging that pull
request adopts the decision.

**Scope:** two files, `blueprints/memory-stack/longmemeval/agentmemory/package-lock.json.frozen`
and `package.json.frozen` beside it. No other lockfile, scanner setting or workflow changes.

## Context

#274 asks for the agentmemory 0.9.29 lockfile that the Mac arms D1 and D2 used, byte-exact. It is
a record of the measured system: npm lockfile v3 with `@agentmemory/agentmemory` 0.9.29 and
`iii-sdk` 0.11.2 (sha256 `e45aa62e9a2b6897e7024d138945b5c5a3bcc50f2e0d1ba548ecc5b6a73c8a27`),
plus its `package.json` (sha256
`f735eef9db3d00f08dcacf74d5057a5a662d620856fce836ca1ad07ac67ec76e`). Nothing in the catalog or the
adoption profiles installs it. A benchmark run restores it into an isolated prefix.

## Evidence

- `osv-scanner scan source --config .github/osv-scanner.toml --no-resolve` on a copy named
  `package-lock.json` (OSV-Scanner 2.6.0, 2026-09-25): exit 1, 227 packages, two advisories.
  - GHSA-45rx-2jwx-cxfr (CVE-2026-59892), high, CVSS 7.5: `@opentelemetry/propagator-jaeger`
    1.30.1, fixed in 2.9.0; denial of service through an unhandled exception on a malformed
    header.
  - GHSA-8988-4f7v-96qf (CVE-2026-54285), medium, CVSS 5.3: `@opentelemetry/core` 1.30.1, fixed
    in 2.8.0; unbounded memory allocation in W3C baggage propagation.

  Both come in through `iii-sdk` 0.11.2 (`iii-sdk` requires `@opentelemetry/core` ^1.30.0, and
  `@opentelemetry/sdk-trace-node` requires the Jaeger propagator). Neither entry is optional or a
  development dependency.
- Under the name `package-lock.json`, `tests/test_osv_lockfile_coverage.py` requires the file in
  `.github/osv-scanner-lockfiles.json`, and the required `osv-scanner` check then exits 1. The
  required `dependency-review` check (`fail-on-severity: high`) sees `package-lock.json` anywhere
  in the repository through GitHub's dependency graph, so the high advisory would fail it on the
  pull request that adds the file. That second point follows from GitHub's documented manifest
  names and the advisory data; it was not tried on a live pull request.
- Discriminating control, OSV-Scanner 2.6.0 with `-r` over two scratch directories holding the
  same bytes: the one with `package-lock.json` and `package.json` found 227 packages and the two
  advisories (exit 1); the one with the `.frozen` names reported "No package sources found"
  (exit 128). The coverage test's `TRACKED` pattern does not match the `.frozen` names either.
- The bytes stay pinned: `SHA256SUMS` in that directory and `manifests/evidence.json` list both
  files, and `scripts/validate.py` checks their sha256.
- Restoring works: copying both files back to their npm names in a scratch prefix and running
  `npm ci --dry-run --ignore-scripts` (npm 11.19.0, node v24.21.0, an empty npm configuration and
  cache) exits 0 with "added 186 packages".

## Decision

Store the pair as `package-lock.json.frozen` and `package.json.frozen`. Restore the npm names
only in the isolated prefix a benchmark run uses; the directory's README gives the commands.
Upgrading the OpenTelemetry packages is not an option for this record, because it would change
the system the Mac measured.

## Alternatives considered

- **Keep the npm names and suppress the advisories** (rejected). It needs inventory entries in
  `.github/osv-scanner-lockfiles.json`, two `[[IgnoredVulns]]` entries in
  `.github/osv-scanner.toml` that expire within 90 days and must be renewed for as long as the
  file exists, and `allow-ghsas: GHSA-45rx-2jwx-cxfr` in `.github/workflows/dependency-review.yml`.
  That workflow change counts toward the overturn trigger of section 6 of
  [2026-09-22-github-automation-closure.md](2026-09-22-github-automation-closure.md). After merge,
  Dependabot would open alerts and security-update pull requests against a file that must not
  change, and Scorecard would report it.
- **The inventory's `excluded` list** (rejected).
  - The lock could qualify for it. The unit test accepts an exclusion when its reason calls the
    file a fixture, and the list already holds three captured `dvc.lock` copies on that basis.
  - But the list steers only the `osv-scanner` job. `dependency-review` reads any
    `package-lock.json` by name, whatever the inventory says, and its `fail-on-severity: high`
    would fail on GHSA-45rx-2jwx-cxfr. Scorecard and the Socket app also find lockfiles by name.
- **Leave the lock out** and point at the copy on the agent-ecosystem LongMemEval lane branch
  (rejected). #274 asks for it here, and that branch is private and unmerged.
- **Generate the lock at run time** (rejected). npm would resolve current versions, not the ones
  the arms ran.

This follows `requirements.txt.fixture` (section 3 of the same closure record), which was renamed
for the same reason: a name that scanners read reports a file that is kept unchanged on purpose.
That file is a test fixture. This lock is a captured record of what the arms installed, which makes
it the first file kept from the scanners by renaming that is not a test fixture.

## What the rename does not do

It does not make the dependency safe. A run that restores the pair installs both vulnerable
packages. The harness binds agentmemory's REST port to 127.0.0.1, and only the harness sends it
requests. Whether agentmemory 0.9.29 registers the Jaeger or W3C baggage propagators was not
checked.

## Overturn

- OSV-Scanner, GitHub's dependency graph, Scorecard or the Socket app starts reading `*.frozen`
  files.
- The lock stops being a frozen record: a later run installs agentmemory from a new lock. That
  lock gets its npm name and the normal scan, or its own entry here with evidence.
- Both required checks gain a supported per-path exclusion for frozen records. The files then go
  back to their npm names under that exclusion.
