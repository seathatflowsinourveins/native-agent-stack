# actionlint successor swap (2026-09-28)

Plan move M2, step 3, of the integrity-gate wave. The required `validate` job's
actionlint step now runs `kjanat/actionlint` v1.17.0 in place of
`rhysd/actionlint` 1.7.12, and the non-required `actionlint-successor` trial job
is removed from `.github/workflows/validate.yml`. The
[2026-09-27 parity trial](../actionlint-successor-parity-20260927/README.md)
chose the method and kept 1.7.12 until the hosted job matched it. This receipt
records that match, a fresh verification of the release and the state of the
trial's open items.

`receipt.json` holds the recorded values this page quotes. Its
`catalog_revision` is `f02192630ae121705556708ed28ad1596af31dd3` (#469), the
brief's base and the last commit in the hosted table. main advanced to bab06007
during the session. That commit touches no file of this branch except
`manifests/evidence.json`. The reads ran from 2026-09-28T23:57Z to
2026-09-29T00:12Z UTC (2026-09-28 evening EDT).

Evidence classes:

- **upstream-unchanged**: an upstream tool or verifier run as published.
- **hosted-observed**: GitHub-hosted runs of this repository, read back with
  `gh`.
- **our-integration**: this repository's tests, and scratch copies around the
  upstream tools.
- **live-run-pending**: needs a hosted run of this branch or of a control.

## Sources

- **Release.** [kjanat/actionlint v1.17.0](https://github.com/kjanat/actionlint/releases/tag/v1.17.0)
  is immutable. Its annotated tag 2da2ceb4 points to commit 08bb2c4f, and the
  tag signature verifies. The asset `actionlint_1.17.0_linux_amd64.tar.gz` has
  digest `620abd48…d6e5a`.
- **Install and attestation.** `docs/install.md` lines 124-134 at v1.17.0.
- **Exit status.** `docs/usage.md` lines 275-284 at kjanat v1.17.0 and lines
  181-190 at rhysd v1.7.12 give the same table: 0 means no problem was found.
- **Changes.** `CHANGELOG.md` at v1.17.0:
  - line 13: three cache safety policies are on without a configuration file;
  - line 238 (v1.8.0): concurrency `queue` is accepted.

## Upstream status, re-observed (upstream-unchanged)

Source: `gh api`, at 2026-09-28T23:57:59Z.

- **`rhysd/actionlint`.** The latest release is still v1.7.12 (2026-03-30).
  The main tip is still 011a6d15 (2026-04-19), with no commit on main since
  2026-06-29. Issue #719 is open (6 comments, last updated 2026-09-18).
- **`kjanat/actionlint`.** The latest release is v1.17.0 (2026-09-13); all
  recent releases are immutable. The last default-branch commit is dated
  2026-09-25.
- Nothing changed since the 2026-09-27 trial's reading.

## Verification (upstream-unchanged)

The five-command block in `docs/github-automation.md`, as changed here, ran
verbatim in an empty scratch directory at 2026-09-29T00:06Z:

| Command | Exit | Output |
| --- | --- | --- |
| `gh release download --repo kjanat/actionlint --pattern '*_linux_amd64.tar.gz' --pattern '*_checksums.txt' v1.17.0` | 0 | archive 3,067,604 bytes; checksums file 2,461 bytes |
| `gh attestation verify -R kjanat/actionlint actionlint_1.17.0_linux_amd64.tar.gz` | 0 | nothing on stdout or stderr |
| `sha256sum --check --ignore-missing actionlint_1.17.0_checksums.txt` | 0 | `actionlint_1.17.0_linux_amd64.tar.gz: OK` |
| `tar -xzf actionlint_1.17.0_linux_amd64.tar.gz actionlint` | 0 | binary sha256 `6e0e370a…` |
| `./actionlint -version` | 0 | `actionlint.kjanat.dev 1.17.0`, built with go1.27.1 |

- `sha256sum` of the archive printed the pinned digest. validate.yml's own
  `printf … | sha256sum --check` form printed `OK` with exit 0.
- **The attestation output is verbatim.** This `gh` prints no report on
  success when stdout is not a terminal, and a second plain run was also
  empty. The `--format json` run returned exit 0 and 1 result:
  - SLSA provenance v1, 23 subjects;
  - signer `kjanat/actionlint/.github/workflows/release.yml@refs/tags/v1.17.0`;
  - source ref `refs/tags/v1.17.0`, source digest 08bb2c4f;
  - trigger `push`, runner `github-hosted`.
- **Negative control.** The same archive checked against `-R rhysd/actionlint`
  exited 1 with `HTTP 404: Not Found`.
- **Same as the trial.** Every digest and identity equals the 2026-09-27
  trial's value.
- **Disposal.** The archive, the checksums file and the binary were deleted
  after the checks. None is committed.

## Hosted parity since #449 (hosted-observed)

The scope is every push run of `validate.yml` on main whose head is one of the
25 first-parent commits from b60d5182 (#449) through f0219263 (#469). Each
commit has one run, with none missing and every run on attempt 1.

Each cell gives the job conclusion, then the actionlint step's conclusion:

| # | Run | Head | Created (UTC, 09-28) | `validate` / rhysd 1.7.12 step | `actionlint-successor` / kjanat 1.17.0 step |
| --- | --- | --- | --- | --- | --- |
| 1 | 36397523830 | b60d5182 | 08:28 | success / success | success / success |
| 2 | 36398443755 | 4f31ef46 | 08:37 | success / success | success / success |
| 3 | 36401537552 | 8315274f | 09:07 | success / success | success / success |
| 4 | 36403888087 | 718e5620 | 09:30 | success / success | success / success |
| 5 | 36406958313 | c484ef9a | 09:59 | success / success | success / success |
| 6 | 36409124789 | 4a8b729a | 10:20 | success / success | success / success |
| 7 | 36410172987 | eb678281 | 10:31 | success / success | success / success |
| 8 | 36413530210 | 4a610e18 | 11:05 | success / success | success / success |
| 9 | 36416522826 | 85a604ac | 11:35 | success / success | success / success |
| 10 | 36420558684 | fb14dedf | 12:14 | success / success | success / success |
| 11 | 36429700534 | 9f8db582 | 13:35 | success / success | success / success |
| 12 | 36431699003 | dd996770 | 13:52 | success / success | success / success |
| 13 | 36438426118 | 3058b237 | 14:45 | success / success | success / success |
| 14 | 36450989979 | 8d8f79cd | 16:26 | success / success | success / success |
| 15 | 36453850824 | b9eb62d2 | 16:49 | success / success | success / success |
| 16 | 36456458035 | c1581fa2 | 17:12 | success / success | success / success |
| 17 | 36459546042 | c61e6657 | 17:38 | success / success | success / success |
| 18 | 36465601051 | c0966da2 | 18:29 | success / success | success / success |
| 19 | 36470292826 | 08aec098 | 19:09 | success / success | success / success |
| 20 | 36470666243 | c3f15cd2 | 19:12 | success / success | success / success |
| 21 | 36473583529 | bdf25d28 | 19:38 | success / success | success / success |
| 22 | 36487587560 | 11a23f1b | 21:39 | success / success | success / success |
| 23 | 36488253438 | 83229e24 | 21:45 | success / success | success / success |
| 24 | 36495358989 | f6e5a038 | 22:57 | success / success | success / success |
| 25 | 36497637857 | f0219263 | 23:22 | success / success | success / success |

**25 of 25**: both jobs and both actionlint steps succeeded on every run. PR
#449's own checks (run 36395668639) were also green for both jobs.

- **What success means.** Each step runs under `bash -e` and ends with
  `actionlint -color`. actionlint exits 0 only when it finds no problem, so on
  every run both binaries reported no diagnostic.
- **What it does not show.** The table pairs conclusions, not diagnostics, and
  no hosted run met a workflow that either binary rejects.
- **Method.** `gh run list` and `gh api …/runs/<id>/jobs` with `--jq`, listed
  in `receipt.json` `hosted_parity.method`.
- **Latest run.** In run 36497637857 both jobs ran on ubuntu-24.04 image
  20260920.314.1. The successor step logged
  `$RUNNER_TEMP/actionlint-successor/archive.tar.gz: OK` and
  `actionlint.kjanat.dev 1.17.0`.

## The 2026-09-27 trial's pending items

| Item (2026-09-27 `live_run_pending`) | Now | Closed by |
| --- | --- | --- |
| 1. First hosted run of the successor job and green PR checks | closed | PR #449's checks and the 25 runs above |
| 2. zizmor's online audits in the required job, with `github.token` | closed | validate job 109180818981, below |
| 3. `test_job_parser_matches_yaml_when_available` (needs PyYAML) | **open** | not observable from the hosted log, below |
| 4. Swapping the required gate | done here | this branch; its hosted run is pending |

- **Item 2.** Validate job 109180818981 (run 36497637857) closes it:
  - its zizmor step's environment shows `GH_TOKEN: ***`;
  - it printed no offline-mode warning, which a tokenless local run does print;
  - harden-runner recorded the zizmor process reaching `github.com:443` and
    `api.github.com:443`;
  - it audited `.github/dependabot.yml` and 20 workflows and ended
    `No findings to report. Good job! (48 suppressed)`.
- **Item 3.** It stays open. validate.yml line 141 (at f0219263) runs
  `python3 -m unittest` without `-v`, and the log ends `Ran 7079 tests in
  620.749s` and `OK (skipped=710)`. That counts skips but names none, and no
  step prints whether PyYAML imports. A hosted run that names this test's
  result would close it. Locally it still skips because PyYAML is absent.

## The `queue` key (upstream-unchanged binary, our scratch copies)

[The 2026-09-23 decision record](../../../docs/decisions/2026-09-23-bot-pr-dispatch.md)
kept `queue: max` out of `catalog-freshness.yml` because rhysd 1.7.12 rejected
it. Its overturn condition asks for a release that accepts `queue`, checked
directly. The verified 1.17.0 binary gives:

| Input | Exit | Output |
| --- | --- | --- |
| this branch's `catalog-freshness.yml` with `queue: max` in the propose job's concurrency | 0 | none |
| the same line as `queue: bogus` | 1 | `invalid value "bogus" for "queue" in "concurrency" section` |
| trial fixture c6 (`queue: max` with `cancel-in-progress: true`) | 1 | `"queue: max" cannot be combined with "cancel-in-progress: true"` |

This branch only dates the three present-tense claims:

- `catalog-freshness.yml`, the propose job's concurrency comment;
- `docs/github-automation.md`, the propose paragraph;
- `tests/test_catalog_freshness_propose.py`, the comment above the assertion.

Re-adopting `queue: max` is a separate behaviour change.

## Checks on this branch

- **kjanat 1.17.0 over this branch's 20 workflows (upstream-unchanged).**
  - `-color` exited 0, with and without shellcheck 0.9.0-1 on PATH.
  - `-format '{{json .}}'` returned 0 diagnostics in both configurations.
  - `-verbose` reported `Found 0 errors in 20 files`. With shellcheck on PATH
    it logged no disabled-rule line.
  - The unedited base gave the same result.
- **zizmor 1.30.1 with validate.yml's command, offline (upstream-unchanged).**
  It exited 0 with no findings: 47 suppressed here against 48 at the base.
  The missing one is the pedantic `anonymous-definition` for the removed
  unnamed job.
- **Failing first (our-integration).** With validate.yml swapped and the
  freshness row unchanged, `python3 -m unittest tests.test_catalog_freshness_pins`
  exited 1: `AssertionError: '1.7.12' != '1.17.0'`. With the row changed it
  exited 0.
- **Unit tests (our-integration).**
  - `tests.test_workflow_hardening`: 74 tests, OK, with 2 skips (no
    hash-frozen workflow; no PyYAML).
  - `tests.test_zizmor_negative_control`, `tests.test_workflow_security` and
    `tests.test_workflow_security_coverage`: 16 tests, OK.
- **After registration.** `scripts/validate.py`, the acceptance set and the
  pre-push registry tests ran after registration, so their exit codes are in
  the handoff. Before registration, the publication-validator test failed only
  on the five changed registered files' hashes.

## Residuals

- **Landscape verdict.** `catalogs/landscape/foundation.json` `/layers/11`
  still names rhysd/actionlint as `selected`, under the sealed two-lane verdict
  `foundation-ci-supply-chain-20260922`. It changes only through a sealed
  re-record in the verdict wave (F-LT-1), not here.
  `catalogs/us-equities/decision-index.json` follows that re-record.
- **`queue: max`.** The decision record's overturn condition is now met;
  re-adopting it is left to a separate change.
- **Dashboard.** The `actionlint-successor-trial` row in
  `observability/grand-dashboard/state.json` still describes the trial. The
  coordinator owns it.
- **Dated statements.** Records that name 1.7.12 stay as recorded; the list is
  in `receipt.json` `residuals`.
- **Selection risk.** kjanat/actionlint has one main maintainer and a fast
  release cadence. This reading saw no release after v1.17.0 and no
  default-branch commit after 2026-09-25.

## Overturn

Re-open the selection if either happens:

- rhysd/actionlint publishes a release after v1.7.12;
- GitHub ships an official workflow linter CLI.

Compare the candidate with kjanat/actionlint by the 2026-09-27 trial's parity
method before changing the pin.

## Live-run pending

- This branch's hosted validate run: the swapped step and zizmor's online
  audits over the changed `validate.yml`.
- A hosted negative control showing the swapped step failing a workflow it
  should reject.
- Item 3, the PyYAML parser cross-check.

## Retained failures and sanitization

- **Job logs.** `gh api …/actions/jobs/<id>/logs` exited 1 ("the response
  contains terminal escape sequences"), so the logs were read with
  `gh run view --job --log`.
- **Queue check.** The first run, in a scratch directory that was not a git
  repository, exited 3 ("no project was found"). The run was repeated in a
  git-initialised copy.
- **Sanitization.** Runner temporary paths appear as `$RUNNER_TEMP/…`; local
  paths as `<scratch>` and `<checkout root>`. Raw `gh` JSON, job logs and
  verbose lint output stayed in scratch. No credential value was read. The
  hosted log shows the token only as GitHub's `***` mask.
