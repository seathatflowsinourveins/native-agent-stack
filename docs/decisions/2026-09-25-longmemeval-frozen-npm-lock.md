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

## Addendum (2026-09-27): extending scope to the LongMemEval v4 driver's six locks

**Added in:** the review-fix round on the pull request for host request #384 that commits the
LongMemEval-S v4 driver byte-exact under `blueprints/memory-stack/longmemeval/v4/` (#386).
Merging that pull request adopts this addendum.

**Scope added:** six files under `blueprints/memory-stack/longmemeval/v4/`: the five
`requirements/*.lock.txt.frozen` files (`build`, `embed`, `hindsight`, `mempalace`, `official`)
and `vendor/agentmemory-repo-package-lock.json.frozen`. The decision above still governs only the
two files named in its own Scope; this addendum extends the same reasoning and evidence bar to
these six, per that Scope's Overturn bullet ("a later run installs agentmemory from a new
lock... That lock gets its npm name and the normal scan, or its own entry here with evidence") and
the v4 driver README's own deferred promise to add this addendum once #380 merged (#380 has now
merged to `main`).

### Context

The v4 driver (#386) is a second, separate byte-exact transfer from the private `agent-ecosystem`
repository (commit `576689a`), for the workstation's A17 rerun. Its five Python venvs and one npm
lock are captured the same way #380's agentmemory lock was: hash-locked records of what five
isolated venvs (and one repository clone) installed for specific measured or to-be-measured runs,
kept unchanged under names no dependency scanner reads
(`requirements/*.lock.txt.frozen`, `vendor/agentmemory-repo-package-lock.json.frozen`), for the
same mechanical reason given above (`tests/test_osv_lockfile_coverage.py`'s `TRACKED` pattern
matches any tracked file ending in `.lock.txt`). Their `.in` sources pin the packages these locks
resolve — `requirements/official.in` alone pins 25 of its 28 lines, including `Jinja2==3.1.3`,
`nltk==3.9.1`, `pillow==10.2.0`, `torch==2.3.1` and `transformers==4.43.3` — so this is not a
speculative concern; the pins are the ones the driver's README already names.

### Evidence

`osv-scanner scan source --config .github/osv-scanner.toml --no-resolve` (OSV-Scanner 2.6.0,
2026-09-27) on scratch copies named with their plain (non-`.frozen`) names, one `--lockfile=`
override per file (`--lockfile=requirements.txt:<path>` for the five Python locks,
`--lockfile=package-lock.json:<path>` for the npm one — the same flag shape
`.github/workflows/security-scan.yml` builds from `.github/osv-scanner-lockfiles.json`).
A second run of the same command with an empty config file gives the unfiltered counts
(re-run 2026-09-27 for the GPT-6 re-check). Pairs below read "unfiltered / with the repository
config":

| File (plain name) | Packages scanned | Vulnerable packages | Unique advisories |
| --- | --- | --- | --- |
| `official.lock.txt` | 64 | 9 / 9 | 115 / 114 |
| `embed.lock.txt` | 91 | 3 / 2 | 3 / 2 |
| `mempalace.lock.txt` | 80 | 1 / 1 | 4 / 4 |
| `hindsight.lock.txt` | 223 | 0 / 0 | 0 / 0 |
| `build.lock.txt` | 3 | 0 / 0 | 0 / 0 |
| `agentmemory-repo-package-lock.json` | 376 | 2 / 2 | 2 / 2 |

("Unique advisories" collapses GHSA/CVE/PYSEC/BIT aliases of the same finding to one row; the
raw, alias-duplicated JSON output was retained for this review round but is not committed.)
The two differences are the repository's two `[[IgnoredVulns]]` entries, which apply here
too (see the last point of the next list): GHSA-8mgp-746c-j5xp (alias PYSEC-2026-3740) on
`nltk` 3.9.1 in `official.lock.txt`, and GHSA-h35f-9h28-mq5c (alias PYSEC-2026-3447) on
`setuptools` 81.0.0 in `embed.lock.txt`.

Representative findings, not the full list:

- `official.lock.txt`: `nltk` 3.9.1 alone carries 43 unique advisories, 42 with the repository
  config (path traversal, SSRF, ReDoS and arbitrary-file-read classes; e.g. GHSA-6hm5-jgcp-p838,
  GHSA-qvv7-cg9c-w4x3); `transformers` 4.43.3 carries 26 (mostly ReDoS); `torch` 2.3.1 carries
  20; `pillow` 10.2.0 carries 15 (buffer overflow, decompression-bomb and out-of-bounds-read
  classes); `jinja2` 3.1.3 carries 4 (sandbox breakout, e.g. GHSA-cpwx-vrp4-4pq7).
- **The repository's OSV ignores are global, not lock-scoped.** OSV-Scanner 2.6.0 matches an
  `[[IgnoredVulns]]` entry by advisory ID and `ignoreUntil` only
  ([`internal/config/config.go:104-112`](https://github.com/google/osv-scanner/blob/v2.6.0/internal/config/config.go#L104-L112),
  `ShouldIgnore`); the evidence path in an entry's `reason` scopes nothing. Both entries written
  for the Lumibot lock therefore also filter these locks when they are scanned:
  GHSA-8mgp-746c-j5xp (`nltk` through 3.10.3) removes one advisory from `nltk` 3.9.1 in
  `official.lock.txt`, and GHSA-h35f-9h28-mq5c (`setuptools` below 83.0.0) removes the only
  advisory on `setuptools` 81.0.0 in `embed.lock.txt`. The scanner's "Filtered 4 vulnerabilities"
  line counts those two advisories with their aliases, not four unrelated ones. Nothing here
  relies on those ignores: under their `.frozen` names these files reach no scanner, and the counts
  above name both filtered advisories.
- `mempalace.lock.txt`: `chromadb` 1.5.9 carries 4, including GHSA-f4j7-r4q5-qw2c
  (PYSEC-2026-311, CVE-2026-45829), described upstream as a pre-authentication code-injection
  vulnerability.
- `embed.lock.txt`: `torch` 2.11.0 (GHSA-rrmf-rvhw-rf47, low) and `transformers` 5.7.0
  (GHSA-xrqw-3rrv-vx5w, a `save_pretrained` path-traversal issue) carry one each.
- `agentmemory-repo-package-lock.json` (376 packages: the agentmemory repository's own lock,
  distinct from and larger than the install-prefix lock #380 already freezes) repeats the exact
  pair the decision above found for that smaller lock: GHSA-45rx-2jwx-cxfr (high,
  `@opentelemetry/propagator-jaeger` 1.30.1) and GHSA-8988-4f7v-96qf (medium,
  `@opentelemetry/core` 1.30.1), both again reached through `iii-sdk` 0.11.2.
- `hindsight.lock.txt` (223 packages) and `build.lock.txt` (3 packages) returned no advisories at
  scan time.

Discriminating control: the same scan (`-r`, no `--lockfile=` overrides) over a second scratch
directory holding the same six files under their committed `.frozen` names reported "No package
sources found" (exit 128) — identical in kind to the original record's control, and consistent
with `TRACKED` not matching the `.frozen` names either.

Under their plain names, the five Python locks would need an inventory entry the same way the
npm pair above does, and the required `osv-scanner` check would then fail on the advisories
above (most immediately GHSA-6hm5-jgcp-p838 and the rest of `nltk`'s 42, which `official.lock.txt`
carries unfiltered — see Context). `dependency-review` is a different mechanism: it reads GitHub's
native dependency graph, which recognizes manifests by fixed per-ecosystem names
(`requirements.txt`, `package-lock.json`, and so on), not by this repository's `TRACKED` pattern.
None of the six plain names here — `official.lock.txt`, `embed.lock.txt`, `hindsight.lock.txt`,
`mempalace.lock.txt`, `build.lock.txt`, `agentmemory-repo-package-lock.json` — is one of those
recognized names (the npm one specifically is not `package-lock.json`, the same point the driver's
README already makes about `TRACKED`), so `dependency-review` would not see any of them either
way; unlike the 2026-09-25 record's own file, which was named exactly `package-lock.json` and so
was reachable by both checks. The gate these six files actually escape by staying `.frozen` is
`osv-scanner`, for the five that would otherwise need a `TRACKED` inventory entry.

The bytes stay pinned: `SHA256SUMS` in `blueprints/memory-stack/longmemeval/v4/` and
`manifests/evidence.json` list all six files, and `scripts/validate.py` checks their sha256.

### Decision

Extend the decision above to these six files: keep them as `*.lock.txt.frozen` and
`vendor/agentmemory-repo-package-lock.json.frozen`. Restore each to its plain name only in an
isolated prefix a setup or benchmark run uses, never in the checkout itself — the driver's
README gives the commands. Upgrading any of the pinned packages is not an option for this record
either, because doing so would change the measured or to-be-measured system.

### What the rename does not do

It does not make any of these six dependency sets safe. A run that restores them installs every
vulnerable package listed above. `hindsight.lock.txt` and `build.lock.txt` showing no advisory
today is a snapshot, not a guarantee. Whether the served processes (agentmemory 0.9.29 under
`am-minilm-hooks`, ai-memory's reranker path, MemPalace's chromadb store, Hindsight's own API)
exercise the vulnerable code paths was not checked; every service in this lane binds to
127.0.0.1 only (the driver README's shared-host section), which narrows but does not eliminate
the exposure.

### Overturn

Unchanged from the decision above, plus: a later run relocks any of these six files (the new lock
gets its plain name and the normal scan, or its own dated entry here with evidence).
