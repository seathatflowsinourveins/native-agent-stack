# betterleaks v1.8.1 beside gitleaks 8.30.1: verification, parity and a non-required trial job (2026-09-27)

Local evidence for plan move M3, recorded on host `nativestack-5975wx-20260925` (WSL2, x86_64) from base
commit `ba1700ad` (the full `catalog_revision` is in [`run-record.json`](run-record.json)). The change
adds one job and its tests:

1. [`.github/workflows/validate.yml`](../../../.github/workflows/validate.yml) gains
   `secret-scan-betterleaks` next to the required `secret-scan` job. Its context is absent from
   [`.github/main-ruleset.json`](../../../.github/main-ruleset.json), so a red run informs and never blocks
   a merge.
2. [`tests/test_workflow_hardening.py`](../../../tests/test_workflow_hardening.py) gains
   `BetterleaksTrialJobTests` (5 tests).

The required `secret-scan` job, the pre-commit hook, the pins files and `catalog-freshness.yml` are
unchanged.

**Why betterleaks.** The gitleaks README on `master` (line 12, read 2026-09-28T03:04Z) says: "Gitleaks
is feature complete. I'm not merging new features into Gitleaks. Future releases will be security
patches only. I'm shifting my focus to Betterleaks". The betterleaks v1.8.1 release is immutable and
signs its `checksums.txt` with a Sigstore bundle. The gitleaks v8.30.1 release has no signature assets,
and GitHub holds no attestation for its archive.

**Evidence classes.**

- `upstream-unchanged`: the verification steps and their controls, run with cosign v3.0.6, sha256sum and
  gh 2.101.0. Also zizmor 1.30.1 (offline) and actionlint 1.7.12 with shellcheck 0.11.0.
- `our-integration`: the unchanged binaries run over this repository and over the unchanged fixture
  classes of `tests/test_gitleaks_config.py`, our value-blind triage of the redacted reports, a local
  simulation of the job's run steps, and the new hardening tests.
- `live-run-pending`: the job on a GitHub-hosted runner, and zizmor's online audits.

None of this is a hosted Actions run.

## 1. Verification before first execution (upstream-unchanged)

| Step | Result |
| --- | --- |
| cosign v3.0.6 bootstrap | Its digest matched three sources before it ran: `sigstore/cosign-installer` v4.1.2 `action.yml` line 108 (the installer's own bootstrap pin), the release's `cosign_checksums.txt`, and the GitHub release asset digest. cosign's own signature was not verified. GitHub holds no attestation for the binary: `gh attestation verify` returned HTTP 404 and `gh release verify v3.0.6` found none (checked after its first run). Its release bundle needs a Sigstore verifier, and cosign checking itself shows only self-consistency. |
| betterleaks `checksums.txt` | `cosign verify-blob --bundle checksums.txt.sigstore.json` printed `Verified OK`. It pinned the identity regexp `^https://github\.com/betterleaks/betterleaks/\.github/workflows/release\.yml@refs/tags/v1\.8\.1$`, issuer `https://token.actions.githubusercontent.com`, repository, ref `refs/tags/v1.8.1`, the tag commit and trigger `push`. |
| betterleaks archive | `sha256sum --check --ignore-missing --strict checksums.txt`: `betterleaks_1.8.1_linux_x64.tar.gz: OK` |
| Signer certificate | SAN and build signer: `release.yml@refs/tags/v1.8.1`. Source repository digest: the tag commit. Trigger: `push`. Rekor `hashedrekord` entry, log index 2507892221. |
| Failing controls | Each of these fails with rc 1: a v1.8.0 ref, the gitleaks repository, the Google issuer, a zero workflow SHA, `checksums.txt` with one bit changed, and the archive with one bit changed. |
| GitHub release attestation | `gh release verify` and `gh release verify-asset` pass (predicate `release/v0.2`, 9 subjects). The one-bit-changed archive fails. |
| gitleaks 8.30.1 archive | The digest matches the `validate.yml` pin, `pins.json` and the upstream checksums file. |

## 2. What betterleaks reads, and flag mapping (v1.8.1 source)

- **Config discovery** (`cmd/root.go` lines 38-44, 270-272). The order is `--config`, then
  `BETTERLEAKS_CONFIG` or `GITLEAKS_CONFIG`, then the matching `_TOML` variables, then
  `.betterleaks.toml` or `.gitleaks.toml` in the target. Ignore files are read the same way:
  `.betterleaksignore` first, then `.gitleaksignore` (lines 282-284). This change adds no
  `.betterleaks.*` file, so `.gitleaks.toml` and `.gitleaksignore` are read as they are.
- **Allowlists** become expression filters (`config/translate_filters.go`, `TranslateLegacyFilters`).
  In the fixture run, every "is not detected" case produced no finding. Every `.gitleaksignore`
  fingerprint test passed.
- **`[extend] useDefault = true`** extends each tool's own embedded defaults (`config/config.go` line
  352). betterleaks has 417 rules in `config/betterleaks.toml`; gitleaks has 222 in
  `config/gitleaks.toml`. The same file therefore selects different rules.
- **Flags.** `git`, `dir`, `--config`, `--max-target-megabytes`, `--log-opts`, `--redact`,
  `--no-banner`, `--report-format json` and `--report-path` are accepted unchanged: the scans below use
  the `secret-scan` job's argument list. There are four differences:
  - betterleaks applies `--max-target-megabytes` to file sources only (`cmd/directory.go` lines 42 and
    66; `cmd/git.go` has no size limit). gitleaks 8.30.1 also enforces it on every fragment
    (`detect/detect.go` lines 431-436). So a history scan by betterleaks reads blobs over 2 MB that
    gitleaks skips.
  - An empty JSON report is `null` in betterleaks and `[]` in gitleaks.
  - The `sourcegraph-access-token` rules differ. gitleaks matches any bare 40-hex value near the
    keywords `sgp_` or `sourcegraph` (`config/gitleaks.toml` lines 3051-3058). betterleaks requires
    the `sgp_` prefix (`config/betterleaks.toml` lines 8784-8786).
  - `--validation` is off by default (`cmd/root.go` line 112). It would send candidates to provider
    endpoints, so the job never passes it and a hardening test forbids it.
- **`.git` in dir mode.** Both default configs skip a path matching `(?:^|/)\.git$` (line 49 of
  `config/betterleaks.toml` and of `config/gitleaks.toml`), so a runner's `.git` directory should not be
  read. The local worktree's `.git` is a file, so only the hosted run shows it.

## 3. Parity on this repository (our-integration)

Both tools ran on the clean worktree at the base commit with `--config .gitleaks.toml` and
`--redact`. Rows and triage classes are in [`parity.json`](parity.json).

| Scan | gitleaks 8.30.1 | betterleaks 1.8.1 |
| --- | --- | --- |
| Full history: `git . --log-opts=HEAD --max-target-megabytes 2` | rc 0, no findings, 697 commits, 72.7 s | rc 1, 91 findings, 55.3 s (attempt 2) |
| Working tree: `dir . --max-target-megabytes 2` | rc 0, no findings, 10.6 s | rc 1, 16 findings, 1.0 s |
| Fixture classes (25 tests, `GITLEAKS_TESTS_REQUIRED=1`) | 25 ok | 17 ok, 4 FAIL, 4 ERROR |
| History scan resources, raised caps (`/usr/bin/time -v`) | 3.3 GiB peak RSS, 1:13.83 wall | 7.9 GiB peak RSS, 0:55.23 wall |

betterleaks is **not a superset** on the fixtures:

- **13 detections are missing.** gitleaks's `sourcegraph-access-token` flags bare 40-hex values in
  fixtures d2, d4 and d5. At three of those lines betterleaks reports `generic-api-key` instead. The
  real scans had no gitleaks finding to miss.
- **Five tests fail on the empty-report format alone.** The negative tests b, d, d3, e and f fail only
  because an empty report is `null`. In each, betterleaks reported nothing, which is what the test
  requires.

The new findings come from betterleaks-only rules (`generic-password`, `generic-credential-uri`) and
from `generic-api-key` on generated explorer HTML in history, which gitleaks skips by size. Each
finding's line was re-read and the rule's regex re-applied at the reported byte columns. Only key text,
value length, character classes, shape and marker words were printed; no value was printed or stored
(`harness/triage.py`, `harness/triage_history.py`).

| Category | Tree | History |
| --- | --- | --- |
| Content digests under a `*_sha256` field of the generated explorer HTML (history only; each fragment is a 6-13 MB line) | 0 | 73 |
| False positives: code expressions, a printf template, prose | 7 | 8 |
| Test fixtures: URL and redaction fixtures with placeholder passwords | 4 | 4 |
| Readable passphrases of the scratch restic repositories that test-arm scripts create | 3 | 3 |
| Example URLs quoted from advisory text in retained scanner output | 2 | 2 |
| An all-caps `REPLACE_...` placeholder in an example config (history only) | 0 | 1 |

**No real secret was found.** Before any swap, each class needs an allowlist, a fingerprint or a fix.

Resources: under the host gitleaks guard's caps (4G high, 6G max, no swap, 600 s), the first betterleaks
history scan was stopped at 602.7 s with no report. At 542 s it had a 5.3 GiB resident set and 43.1%
lifetime CPU. The recorded run is attempt 2 with raised caps. gitleaks finished under the guard's caps
in 72.7 s.

## 4. The trial job

The job runs these steps in order:

1. `step-security/harden-runner`, audit only.
2. Checkout with `persist-credentials: false` and full history.
3. cosign fetched by URL and checked against the installer's pinned digest.
4. betterleaks: `verify-blob` with the identity above, then the signed checksums, then the archive
   digest pin, then extraction.
5. The three fixture classes, run through a `gitleaks` symlink to the verified binary.
6. The redacted history and tree scans, which print rule, file and line only.

Permissions are `contents: read`. The actions are pinned by SHA. The job uploads no artifact, no step
receives `GH_TOKEN`, and checkout does not persist credentials. Steps 5 and 6 need a successful install
step.

The history-ancestry class of `tests/test_gitleaks_config.py` is left out, because it scans without
`--redact` and its failure message quotes the findings. The redacted history scan covers that ground.

These checks were run:

- **Hardening tests.** The new tests pass (rc 0). Three mutations each fail their test (rc 1): the dir
  scan without `--redact`, the job named `secret-scan`, and extraction before `verify-blob`. The
  workflow was restored byte-identical after the mutations.
- **Local simulation** (`harness/sim_job.py`). The install steps returned 0. The fixture step and both
  scans returned 1, with 8 fixture failures, 91 history findings and 16 tree findings. So until the
  triage above is resolved, **the job's first hosted run is expected to be red**.
- **zizmor 1.30.1** (the `validate.yml` command, offline): rc 0 before and after the change, with
  "No findings to report" and 42 then 43 suppressed. The added suppressed finding is
  `anonymous-definition` at the new job, which carries no `name:` so it can never take the required
  context's name.
- **actionlint 1.7.12**: rc 0 on all workflows and on `validate.yml`, with shellcheck 0.11.0 on `PATH`.
  A control proved shellcheck was active: rc 1 with SC2086 when it was on `PATH`, rc 0 without it.

## Deviations and host side effects

- **betterleaks history attempt 1** ran under the guard's caps and hit the 600 s limit (rc 143).
- **A gh attestation filter** named predicate `release/v0.1` and returned HTTP 404. The attestation is
  `release/v0.2`; `gh release verify-asset` passed.
- **The first shellcheck control** ran outside a git repository and exited 3. It was repeated with the
  workflow passed as a file.
- **The first history triage** located findings by character offset and missed those in the explorer
  HTML. It now uses byte offsets, with 0 relocation failures.
- **The first simulation** ran cosign with the real home directory, which created `~/.sigstore`: 6
  files, the TUF cache. The first betterleaks run created `~/.cache/com.github.wasilibs`: a 2.5 MB
  wazero compilation cache. Both were enumerated and removed as literal paths. The simulator now keeps
  `TUF_ROOT`, `HOME` and `XDG_CACHE_HOME` in scratch.

A betterleaks pre-commit hook would write that cache on every developer host.

## Open before a swap

- **Triage.** Allowlist, fingerprint or fix the 16 tree findings and 91 history findings, including
  the three test-arm passphrases.
- **Tests.** Adapt the tests to a `null` empty report.
- **The `sourcegraph-access-token` difference.** Decide whether it matters.
- **Memory.** The history scan's 7.9 GiB peak must be measured on a hosted runner.
- **Unenforced size limit.** `--max-target-megabytes` is not enforced in git mode.
- **Freshness.** The betterleaks and cosign pins are not in the catalog-freshness table; this change
  leaves `catalog-freshness.yml` alone.
- **Receipts.** There is no `receipts[]` entry, because `manifests/stack.json` has no betterleaks
  component. The files are registered in `manifests/evidence.json` only.

## Files

| File | What it is |
| --- | --- |
| [`run-record.json`](run-record.json) | Sources, download digests, verification outputs and controls, scans with resources, fixture counts, CI simulation, lint, tests and deviations |
| [`parity.json`](parity.json) | Rule, file and line of every new finding with its triage class, the per-test fixture outcomes, and the classification |
| [`harness/`](harness/) | The local scripts that produced these files: scans, fixture collector, value-blind triage, job simulator and `parity.json` generator. They are thin wrappers around the upstream binaries, labelled local integration. |

Raw reports, logs and tracebacks stay outside the repository. Host paths are written as `<scratch>` and
`<worktree>`.
