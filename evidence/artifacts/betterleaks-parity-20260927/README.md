# betterleaks v1.8.1 beside gitleaks 8.30.1: verification, parity and a non-required trial job (2026-09-27)

Local evidence for plan move M3, recorded on host `nativestack-5975wx-20260925` (WSL2, x86_64) from base
commit `ba1700ad` (the full `catalog_revision` is in [`run-record.json`](run-record.json)). A review round
followed on 2026-09-28 (UTC); its reruns and controls are under `repair_round` in `run-record.json`. A
coordinator repair followed the same day ([section 5](#5-report-only-job-and-passphrase-rows-coordinator-repair-2026-09-28);
`coordinator_repair`). The change adds one job, its tests and one test port:

1. [`.github/workflows/validate.yml`](../../../.github/workflows/validate.yml) gains
   `secret-scan-betterleaks` next to the required `secret-scan` job. Its context is absent from
   [`.github/main-ruleset.json`](../../../.github/main-ruleset.json) and from the live ruleset read back on
   2026-09-28, so no run of it blocks a merge.
2. [`tests/test_workflow_hardening.py`](../../../tests/test_workflow_hardening.py) gains
   `BetterleaksTrialJobTests` (7 tests in the review round, 10 since the coordinator repair).
3. [`tests/test_gitleaks_config.py`](../../../tests/test_gitleaks_config.py) reads a JSON report of `null`
   as no findings. betterleaks writes an empty report that way; gitleaks writes `[]` and is unaffected.

The required `secret-scan` job, the pre-commit hook, the pins files and `catalog-freshness.yml` are
unchanged.

**The trial job is report-only.** Findings and fixture-test assertion failures appear as counts in its step
summary and do not fail it, so it is red only when verification, the scanner or the test run errors
(section 5). Its green does not say that a change adds no secret: the required `secret-scan` job stays the
gate.

**Why betterleaks.** The gitleaks README on `master` (line 12, read 2026-09-28T03:04Z) says: "Gitleaks
is feature complete. I'm not merging new features into Gitleaks. Future releases will be security
patches only. I'm shifting my focus to Betterleaks". The betterleaks v1.8.1 release is immutable and
signs its `checksums.txt` with a Sigstore bundle. The gitleaks v8.30.1 release has no signature assets,
and GitHub holds no attestation for its archive.

**Evidence classes.**

- `upstream-unchanged`: the verification steps and their controls, run with cosign v3.0.6, sha256sum and
  gh 2.101.0. Also zizmor 1.30.1 (offline) and actionlint 1.7.12 with shellcheck 0.11.0.
- `our-integration`: the unchanged binaries run over this repository and over the fixture classes of
  `tests/test_gitleaks_config.py`, our value-blind triage of the redacted reports, the review round's
  reruns and controls, a local simulation of the job's run steps, and the new hardening tests with their
  failing controls. Also the coordinator repair's exit-status controls, tests and simulation, and the
  coordinator's host observation for the three passphrase rows (section 5).
- `independent observation` (the policy's platform-record class): the repository's active ruleset, read
  back with `gh api`. This is a configuration read, not a CI run.
- `live-run-pending`: the job on a GitHub-hosted runner, and zizmor's online audits.

None of this is a hosted Actions run.

## 1. Verification before first execution (upstream-unchanged)

| Step | Result |
| --- | --- |
| cosign v3.0.6 bootstrap | Its digest matched three sources before it ran: `sigstore/cosign-installer` v4.1.2 `action.yml` line 108 (the installer's own bootstrap pin), the release's `cosign_checksums.txt`, and the GitHub release asset digest. cosign's own signature was not verified, and the release is not immutable (`immutable: false`). GitHub holds no attestation for the binary: `gh attestation verify` returned HTTP 404 and `gh release verify v3.0.6` found none (checked after its first run). Its release bundle needs a Sigstore verifier, and cosign checking itself shows only self-consistency. |
| betterleaks `checksums.txt` | `cosign verify-blob --bundle checksums.txt.sigstore.json` printed `Verified OK`. It pinned the identity regexp `^https://github\.com/betterleaks/betterleaks/\.github/workflows/release\.yml@refs/tags/v1\.8\.1$`, issuer `https://token.actions.githubusercontent.com`, repository, ref `refs/tags/v1.8.1`, the tag commit and trigger `push`. |
| betterleaks archive | `sha256sum --check --ignore-missing --strict checksums.txt`: `betterleaks_1.8.1_linux_x64.tar.gz: OK` |
| Signer certificate | SAN and build signer: `release.yml@refs/tags/v1.8.1`. Source repository digest: the tag commit. Trigger: `push`. Rekor `hashedrekord` entry, log index 2507892221. |
| Failing controls | Each of these fails with rc 1: a v1.8.0 ref, the gitleaks repository, the Google issuer, a zero workflow SHA, `checksums.txt` with one bit changed, and the archive with one bit changed. |
| GitHub release attestation | `gh release verify` and `gh release verify-asset` pass (predicate `release/v0.2`, 9 subjects). The one-bit-changed archive fails. |
| gitleaks 8.30.1 archive | The digest matches the `validate.yml` pin, `pins.json` and the upstream checksums file. |

## 2. What betterleaks reads, and flag mapping (v1.8.1 source)

- **Config discovery** (`cmd/root.go` lines 38-44, 269-279). The order is `--config`, then
  `BETTERLEAKS_CONFIG` or `GITLEAKS_CONFIG`, then the matching `_TOML` variables, then
  `.betterleaks.toml` or `.gitleaks.toml` in the target. Both jobs pass `--config .gitleaks.toml`.
- **Ignore files** (`cmd/root.go` lines 445-469). betterleaks loads the `--gitleaks-ignore-path` file,
  then the ignore file inside that path if it is a directory, then the scanned directory's own ignore
  file. In each directory `.betterleaksignore` wins over `.gitleaksignore` (lines 281-291). The trial
  job passes `--gitleaks-ignore-path .gitleaksignore`, so the reviewed fingerprints always load.
- **Suppression channels that only betterleaks reads.** These are a `.betterleaksignore` in the scanned
  directory, a `.betterleaks.toml` for runs without `--config`, and an inline allow comment that names
  betterleaks (`detect/detect.go` lines 57 and 962). betterleaks also honours the gitleaks comment, as
  gitleaks does. None of the three exists in this repository, and
  `test_no_suppression_channel_that_only_betterleaks_reads` keeps it that way.
- **Allowlists** become expression filters (`config/translate_filters.go`, `TranslateLegacyFilters`).
  In the fixture run, every "is not detected" case produced no finding.
- **Fingerprints.** The four `.gitleaksignore` tests passed, but they do not show suppression: three
  only parse files, and `test_c` checks that a new commit is *not* suppressed. Every in-ancestry
  fingerprint in `.gitleaksignore` names `sourcegraph-access-token`, which betterleaks does not fire on
  those lines, so their effect cannot be observed. A scratch control shows that betterleaks applies
  fingerprints. One fingerprint from the recorded report, passed as `--gitleaks-ignore-path`, removed
  exactly that finding: git mode went from 91 to 90 findings and dir mode from 16 to 15. An empty
  directory in the same place removed none.
- **`[extend] useDefault = true`** extends each tool's own embedded defaults (`config/config.go` line
  352). betterleaks has 417 rules in `config/betterleaks.toml`; gitleaks has 222 in
  `config/gitleaks.toml`. The same file therefore selects different rules.
- **Flags.** `git`, `dir`, `--config`, `--max-target-megabytes`, `--log-opts`, `--redact`,
  `--no-banner`, `--report-format json` and `--report-path` are accepted unchanged: the scans below use
  the `secret-scan` job's argument list. There are five differences:
  - betterleaks applies `--max-target-megabytes` to file sources only (`cmd/directory.go` lines 42 and
    66; `cmd/git.go` has no size limit). gitleaks 8.30.1 also enforces it on every fragment
    (`detect/detect.go` lines 431-438). So a history scan by betterleaks reads blobs over 2 MB that
    gitleaks skips.
  - An empty JSON report is `null` in betterleaks (`cmd/git.go` line 74 and `cmd/directory.go` line
    72 start from a nil slice) and `[]` in gitleaks (`detect/detect.go` line 127). The fixture tests now
    read `null` as no findings.
  - The `sourcegraph-access-token` rules differ. gitleaks matches any bare 40-hex value near the
    keywords `sgp_` or `sourcegraph` (`config/gitleaks.toml` lines 3051-3058). betterleaks requires
    the `sgp_` prefix (`config/betterleaks.toml` lines 8784-8786).
  - **Archives.** betterleaks opens archives to depth 8 by default (`cmd/root.go` line 103); gitleaks
    8.30.1 does not open them ("no archive traversal is done", its `cmd/root.go` line 92). The trial job
    passes `--max-archive-depth 0`, for like-for-like coverage and so that it does not unpack archives
    from pull-request content. None of the parity rows is an archive member.
  - `--validation` is off by default (`cmd/root.go` line 112). It would send candidates to provider
    endpoints, so the job never passes it and a hardening test forbids it.

  With both added flags, the recorded commit set and the worktree gave the same findings as the recorded
  scans: 91 and 16, at the same rule, file, line and columns, and in git mode the same commit.
- **`.git` in dir mode.** Both default configs skip a path matching `(?:^|/)\.git$` (line 49 of
  `config/betterleaks.toml` and of `config/gitleaks.toml`). A local control confirms it with this
  repository's config. A scratch directory held the same synthetic token-shaped line in
  `.git/planted.txt` and in `planted/planted.txt`, and both scanners reported only the second
  (`harness/git_dir_skip_control.sh`). The hosted run still has to show it on the runner's checkout.

## 3. Parity on this repository (our-integration)

Both tools ran on the clean worktree at the base commit with `--config .gitleaks.toml` and
`--redact`. Rows and triage classes are in [`parity.json`](parity.json).

| Scan | gitleaks 8.30.1 | betterleaks 1.8.1 |
| --- | --- | --- |
| Full history: `git . --log-opts=HEAD --max-target-megabytes 2` | rc 0, no findings, 697 commits, 72.7 s | rc 1, 91 findings, 55.3 s (attempt 2) |
| Working tree: `dir . --max-target-megabytes 2` | rc 0, no findings, 10.6 s | rc 1, 16 findings, 1.0 s |
| Fixture classes (25 tests, `GITLEAKS_TESTS_REQUIRED=1`), tests as at the base commit | 25 ok | 17 ok, 4 FAIL, 4 ERROR |
| The same classes after the `null`-report port | 25 ok | 22 ok, 3 FAIL |
| History scan resources, raised caps (`/usr/bin/time -v`) | 3.3 GiB peak RSS, 1:13.83 wall | 7.9 GiB peak RSS, 0:55.23 wall |

betterleaks is **not a superset** on the fixtures:

- **13 detections are missing.** gitleaks's `sourcegraph-access-token` flags bare 40-hex values in
  fixtures d2, d4 and d5. At three of those lines betterleaks reports `generic-api-key` instead. The
  real scans had no gitleaks finding to miss.
- **Five tests failed on the empty-report format alone.** The negative tests b, d, d3, e and f failed
  only because an empty report is `null`. In each, betterleaks reported nothing, which is what the test
  requires. After the port they pass, and only d2, d4 and d5 fail.

The new findings come from betterleaks-only rules (`generic-password`, `generic-credential-uri`) and
from `generic-api-key` on generated explorer HTML in history, which gitleaks skips by size. Each
finding's line was re-read and the rule's regex re-applied at the reported byte columns. Only key text,
value length, character classes, shape and marker words were printed; no value was printed or stored
(`harness/triage.py`, `harness/triage_history.py`).

| Category | Tree | History |
| --- | --- | --- |
| Content digests under a `*_sha256` field of the generated explorer HTML (history only). The 73 findings sit on lines of 6,106,817 to 13,080,697 bytes, and gitleaks skips a git-mode fragment of 3,000,000 bytes or more (`harness/measure_explorer_lines.py`) | 0 | 73 |
| False positives: code expressions, a printf template, prose | 7 | 8 |
| Test fixtures: URL and redaction fixtures with placeholder passwords | 4 | 4 |
| Restic passphrases in test scripts: two test arms export one value for the repositories they initialise under their scratch-directory argument; `rerun-isolated.sh` uses another for an existing repository under a host state directory, which it does not create | 3 | 3 |
| Example URLs quoted from advisory text in retained scanner output | 2 | 2 |
| An all-caps `REPLACE_...` placeholder in an example config (history only) | 0 | 1 |

**Value-blind triage identified no live credential, and it cannot confirm that none exists.** The three
passphrase rows are fixed disposable test values for synthetic fixtures, and no repository they protected
is retained. Their status is `disposable_test_values_no_retained_repository`, from the coordinator's host
observation of 2026-09-28 (section 5). Two of them sit in trading-lane paths. `rerun-isolated.sh` calls its
value a fixed disposable test string. On the recording host, the state directory that the script names was
absent (stat only, 2026-09-28T04:16Z). The same 25-character value is also in 4 retained round copies of the
step script that the paper arm generates. The 28-character value is also quoted in 2 receipts of the same
recovery wave. Neither scanner flags those 6 files. Before any swap, each class needs an allowlist, a
fingerprint or a fix; the three passphrase rows get fingerprints, with section 5 as the reason.

Resources: under the host gitleaks guard's caps (4G high, 6G max, no swap, 600 s), the first betterleaks
history scan was stopped at 602.7 s with no report. At 542 s it had a 5.3 GiB resident set and 43.1%
lifetime CPU. The recorded run is attempt 2 with raised caps. gitleaks finished under the guard's caps
in 72.7 s.

## 4. The trial job

The job runs its steps with `shell: bash`, which GitHub runs as `bash --noprofile --norc -eo pipefail`,
so a check that fails inside a pipeline fails its step. An unspecified shell would be `bash -e`,
without pipefail. The steps run in this order:

1. `step-security/harden-runner`, audit only.
2. Checkout with `persist-credentials: false` and full history.
3. cosign fetched by URL and checked against the installer's pinned digest.
4. betterleaks: `verify-blob` with the identity above, then the signed checksums, then the archive
   digest pin, then extraction.
5. The three fixture classes, run through a `gitleaks` symlink to the verified binary. Assertion failures
   are reported, not failed (section 5).
6. The redacted history and tree scans, with `--max-archive-depth 0`, `--gitleaks-ignore-path
   .gitleaksignore` and `--exit-code 0`. They print rule, file and line only, and count findings by rule
   in the step summary.

Permissions are `contents: read`. The actions are pinned by SHA. The job uploads no artifact, no step
receives `GH_TOKEN`, and checkout does not persist credentials. Steps 5 and 6 need a successful install
step.

The history-ancestry class of `tests/test_gitleaks_config.py` is left out, because it scans without
`--redact` and its failure message quotes the findings. The redacted history scan covers that ground.

The review round ran these checks on its final files (details in `run-record.json`, `repair_round`).
Section 5 has the coordinator repair's reruns on the files as they now stand.

- **Hardening tests.** The 7 new tests pass (rc 0). 17 changes each fail the test that covers them
  (rc 1), and the files were restored byte-identical (`harness/mutation_controls.py`). The changes are:
  - the dir scan without `--redact`, and with `--redact=0`;
  - either scan without one of the two added flags;
  - the job named `secret-scan`;
  - an upload-artifact step;
  - the job's bash default removed, and a step with its own shell;
  - extraction before `verify-blob`;
  - the pinned-digest check after extraction;
  - one certificate flag removed;
  - the cosign digest check after cosign's first run;
  - the history class, or the whole test module, added to the fixture run;
  - a `.betterleaksignore` or `.betterleaks.toml` at the root, or the inline betterleaks allow comment
    in a tracked file.
- **Local simulation** (`harness/sim_job.py`, with GitHub's command for `shell: bash`). The install
  steps returned 0. The fixture step and both scans returned 1: `Ran 25 tests; FAILED (failures=3)`,
  91 history findings and 16 tree findings. That was before the job became report-only; in section 5's
  rerun every run step returns 0.
- **zizmor 1.30.1** (the `validate.yml` command, offline): rc 0 with "No findings to report" and 43
  suppressed findings, one more than before the change. The added one is `anonymous-definition` at the
  new job, which carries no `name:` so it can never take the required context's name.
- **actionlint 1.7.12**: rc 0 on all workflows and on `validate.yml`, with shellcheck 0.11.0 on `PATH`.
  A control proved shellcheck was active: rc 1 with SC2086 when it was on `PATH`, rc 0 without it.
- **Tests, lint and self-scan** (`harness/final_checks.sh`, `harness/scan_changed.sh`; details under
  `repair_round.final_checks`):
  - `tests.test_gitleaks_config` passed 28 of 28 with gitleaks 8.30.1. The first run skipped one test
    while another gitleaks scan held the per-user lock; the rerun after it cleared skipped none.
  - `tests.test_workflow_hardening` ran 68 tests: OK, 2 skipped as before. The freshness-pin and
    workflow-security modules passed.
  - The 17 changes above failed their tests again, zizmor gave the same output, actionlint and
    shellcheck (also on the harness scripts) printed nothing, and `scripts/validate.py` passed.
  - Both scanners found nothing in the 25 changed or new files, or in the branch's commit.

## 5. Report-only job and passphrase rows (coordinator repair, 2026-09-28)

Before the pull request opened, the coordinator repaired two things. Details are in `run-record.json`,
`coordinator_repair`.

**Report-only through the scanner's own option.** Both scans pass `--exit-code 0`. In betterleaks v1.8.1,
`cmd/root.go` line 82 registers that flag ("exit code when leaks have been encountered", default 1); the
verified binary's `--help` prints the same text. `findingSummaryAndExit` exits 1 on a scan error before it
uses that status (lines 640-641, then 644-645), and a report it cannot write is fatal (line 636). So
findings exit 0, a scanner error still exits 1, and each scan step exits with the scanner's own status.
The precedent is `security-scan.yml`'s zizmor online audits: `--no-exit-codes`, "findings do not fail this
job". The job has no `continue-on-error`.

**The fixture step reports assertion failures and fails on anything else.** Fixture tests d2, d4 and d5
fail on every run on the rule difference in section 3, so a failing step would keep the job red. CPython's
`unittest` counts an `AssertionError` as a failure and any other exception as an error
(`Lib/unittest/case.py`, `_addError`). It writes a closing status line (`Lib/unittest/runner.py`) and exits
1 for an unsuccessful run and 5 when no test ran (`Lib/unittest/main.py`, Python 3.12 and later). The step
turns exit status 1 into 0 only when that line reads `FAILED (failures=N)`, with at most `skipped=N` added.
An error, no test run, another exit status or a missing line fails it. One limit remains:
`_run_gitleaks` accepts scanner exit status 1 and turns any other unexpected status into an
`AssertionError`, so this step cannot tell a scanner error from a detection difference. The two scans are
the check for scanner errors.

**Step summary.** The scans append their finding count, the count per rule id and the scanner's exit
status. The fixture step appends unittest's run line, its status line and its exit status. No value, path
or failure message reaches the summary; the log still lists rule, file and line.

**Checks on the files as they now stand (our-integration).**

- **Exit-status controls** on the verified binary (`harness/exit_code_controls.sh`), over one generated
  token-shaped line that is never printed. Default flags exit 1. `--exit-code 0` exits 0 in dir and git
  mode. With `--exit-code 0`, four cases each exit 1: an unreadable directory (a partial scan), a missing
  `--config`, a report path in a missing directory, and an unknown revision in `--log-opts`. An unreadable
  file is skipped without a scan error (rc 0).
- **Hardening tests.** `BetterleaksTrialJobTests` has 10 tests. The review round's assertion that no scan
  passes `--exit-code` is removed. Three tests are new:
  - one reads the flag and each scan step's exit path;
  - two run the steps with GitHub's command for `shell: bash`, one with a stand-in scanner that follows
    the exit paths above, the other with a stand-in fixture module.

  42 controls each fail their test and only that test (`harness/mutation_controls.py`): the review round's
  17, one of them updated for the renamed step, and 25 new. Every named test ran green first, and the
  files were restored byte-identical.
- **Local simulation** (`harness/sim_job.py` with a scratch step summary, under the bounded runner with the
  review round's raised caps). Every run step returned 0. The fixture step reported `Ran 25 tests; FAILED
  (failures=3)`. The scans reported 91 and 16 findings, with the same per-rule counts as `parity.json`. The
  job's first hosted run is expected to be green unless verification, the scanner or the test run errors
  there.
- **Final checks** (`harness/final_checks.sh`, before commit):
  - `tests.test_workflow_hardening` ran 71 tests: OK, 2 skipped as before.
  - `tests.test_gitleaks_config` passed 28 of 28 with gitleaks 8.30.1. The first run skipped 21 without a
    printed reason; a verbose rerun ten seconds later skipped none.
  - The freshness-pin and workflow-security modules passed, and the 42 controls failed their tests again.
  - zizmor 1.30.1 gave the review round's output line: "No findings to report", 43 suppressed.
  - actionlint 1.7.12 with shellcheck 0.11.0, and shellcheck on the harness scripts, printed nothing.
  - `scripts/validate.py` runs after the re-registration in the branch's last commit, whose message records
    the result.

**Passphrase rows: `disposable_test_values_no_retained_repository`.** The coordinator recorded these facts
on 2026-09-28, on the host that ran the scripts (our-integration; no values, host paths or usernames):

- All three rows are the scripts' fixed disposable test strings for synthetic fixtures:
  - `rerun-isolated.sh` comments its value as a fixed disposable test string;
  - `dagu_arm.sh` and `paper_arm.sh` create their repositories under the per-run scratch-directory
    argument `$R`;
  - `restic-filesystem-semantics.json` backs up synthetic trees built by `fixture.py`.
- None of the recorded repositories exists on that host: not the ai-memory rerun repository under the host
  state directory, and not the Windows-drive `gap-resolution-restic*` directories.
- `find` over the home directory, `/var/tmp` and `/tmp` at depth 7 found no directory named
  `restic-repo`, `restic-hot` or `gap-resolution-restic*`.

A value-blind recheck by the repair at 2026-09-28T07:01Z matched each point. The search was
positive-controlled: a planted `restic-repo` directory under `/var/tmp` was found (1 match) and then
removed. It visited 142,683 directories. The 9 it could not read are systemd or snap private service
directories under `/tmp` and `/var/tmp`.

The same values also sit in 6 tracked files that neither scanner flags (section 3). Before a swap, allowlist
the three rows by fingerprint, with this record as the reason.

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
  wazero compilation cache. Both were enumerated and removed as literal paths. The simulator keeps
  `TUF_ROOT`, `HOME` and `XDG_CACHE_HOME` in scratch, and since the review round so do
  `harness/run_scans.sh` and `harness/run_bl_git2.sh`. The review round's runs left both paths absent.
- **The first-round final checks** (tests, lint, a scan of the new files, and scans of the branch's
  commits) came from two scripts that stayed in scratch, and their results appeared only in the
  handoff. They are now in `run-record.json` (`first_round_checks`), and the committed
  `harness/final_checks.sh` and `harness/scan_changed.sh` replace those scripts.
- **The recorded triage** printed up to 70 characters left of each match with only 12-character tokens
  masked. A shorter credential there would have been printed. `harness/triage.py` now prints only the
  length and character classes of that text. The triage output was never committed. The changed script
  ran once on the recorded tree report: 16 findings, 0 relocation failures, and every left text printed
  as a descriptor.
- **A rule keyword in `run-record.json`.** An intermediate edit named the `sourcegraph-access-token`
  rule there. gitleaks tests every bare 40-hex value in a fragment that holds one of that rule's
  keywords, so the post-commit self-scan reported the file's commit ids: 12 findings in dir mode and 3
  in the branch range, all redacted. betterleaks reported none. The entry was reworded without the
  keywords, the commits were rebuilt, and the scans were repeated clean. Keep that rule's keywords out
  of any receipt file that holds commit ids.
- **Coordinator repair, exploratory exit-status run.** Before `harness/exit_code_controls.sh` existed, a
  scratch command that was not kept ran the same eight cases. It gave the same exit statuses, and the
  script's run is the recorded one.
- **Coordinator repair, first control run.** The first run of the 42 controls counted 4 fixture controls as
  also failing `test_fail` and `test_error`. Those were the stand-in module's own headers, quoted in the
  failure message; each control's exit status was 1. The test now indents that output, the harness reads
  only this class's own headers, and the rerun is the recorded one.

A betterleaks pre-commit hook would write the wazero cache on every developer host.

## Open before a swap

- **Passphrase rows.** Allowlist the three rows by fingerprint, with section 5 as the reason: fixed
  disposable test values for synthetic fixtures, and no retained repository. The 6 unflagged files that
  hold the same values need nothing from either scanner. Two rows are trading-lane paths.
- **Triage.** Allowlist, fingerprint or fix the 16 tree findings and 91 history findings.
- **The `sourcegraph-access-token` difference.** Decide whether it matters; the three fixture tests
  d2, d4 and d5 fail on it, and the trial reports those failures without failing.
- **Archives.** The trial passes `--max-archive-depth 0`. Decide whether the swapped gate should open
  archives, and give the pre-commit hook the same flags as the job.
- **Suppression channels.** Keep `test_no_suppression_channel_that_only_betterleaks_reads` and the
  explicit `--gitleaks-ignore-path` through the swap.
- **Signal.** The trial is report-only (section 5): it stays green with findings, and its step summary
  counts them by rule. A baseline report or a trial-only ignore file would make a finding mean "new", but
  either would accept the untriaged rows first. Plan M3 swaps only when every new hit is triaged, and the
  swapped gate must fail on findings again, without `--exit-code 0`.
- **Memory.** The history scan's 7.9 GiB peak must be measured on a hosted runner.
- **Unenforced size limit.** `--max-target-megabytes` is not enforced in git mode.
- **Freshness.** The betterleaks and cosign pins are not in the catalog-freshness table; this change
  leaves `catalog-freshness.yml` alone.
- **Receipts.** There is no `receipts[]` entry, because `manifests/stack.json` has no betterleaks
  component. The files are registered in `manifests/evidence.json` only.

## Files

| File | What it is |
| --- | --- |
| [`run-record.json`](run-record.json) | Sources, download digests, verification outputs and controls, scans with resources, fixture counts, CI simulation, lint, tests, deviations, the review round's reruns, controls and final checks, and the coordinator repair (`coordinator_repair`) |
| [`parity.json`](parity.json) | Rule, file and line of every new finding with its triage class, the per-test fixture outcomes before and after the port, and the classification |
| [`harness/`](harness/) | Every local script that produced a result recorded here, including the review round's and the coordinator repair's: scans, fixture collectors, value-blind triage, size measurement, controls (among them the exit-status controls), job simulator, final checks and the `parity.json` generator. They are thin wrappers around the upstream binaries, labelled local integration. |

The branch's post-commit range scans are reported with the pull request, because recording them here
would change the commits they scan. Raw reports, logs and tracebacks stay outside the repository. Host
paths are written as `<scratch>` and `<worktree>`.
