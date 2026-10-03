# Decision: scope the required macOS check to macOS-relevant changes and changed tests (2026-10-03)

**Status:** implemented in the pull request that adds this record (branch `c5/macos-ci-scope`, cut from the
verification base below), as the coordinator's brief directed, from the draft with sha256
`3a5eba0772ed82cf86e0688809788241f676e79072333a0416b75f3371e2b83f`. That pull request makes the workflow, test and docs
edits of §6 and adds the receipt `evidence/artifacts/macos-ci-scope-20261003/`. Edits to the draft's text: this status
line; repository paths in place of working-copy names; the paragraph after the data table that names the receipt;
§6.8 (implementation notes); §8.1's last paragraph; one bullet in §10; and the implementing PR's re-reads in the SOTA
sources. The ruleset does not change.

**Asked by:** the user, 2026-10-03: retire or narrow the macOS lane if it causes stagnation without real benefit, and
decide by evidence and research convergence.

**Lane:** foundation.

**Verification base:** `origin/main` at `6112d14d40f741855f0b961124d98939daaad00e` (2026-10-03T20:22:47Z). The
previous round's base was `d2fc3803e`. `git diff --stat d2fc3803e 6112d14d4` shows no change to `.github/`,
`tests/test_workflow_hardening.py`, `tests/test_adoption_bootstrap_macos.py`, `adoption/platforms/macos-arm64.md` or
`docs/github-automation.md`, so line numbers read at either commit agree.

**Supersedes in part:**
- `docs/decisions/2026-09-22-github-automation-closure.md`, "validate-macos required (2026-09-25)". This record acts on
  that section's flake overturn and rejects the remedy it prescribes (§5).
- The Decision and Alternatives sections of open PR #632 (`docs/decisions/2026-10-03-macos-full-suite-coverage.md`
  @85e9bc653). Its receipt and measurements stand.

**Review history:**
1. Claude draft: option B, a required `validate-macos` gated by a list of Mac-relevant paths.
2. Critic verdict: accept with fixes. Blocker D1 and defects D2 to D12.
3. GPT-family classification of the same 25 failures (§3.2).
4. This repair round, the last before consensus. §11 gives the disposition of every critic item.

**Evidence tags:**
- **[measured]:** a count or time computed from the named data, in the previous round, the critic's round or this
  round. §10 says which numbers more than one round reproduced.
- **[doc]:** a file:line at the verification base, or a URL read on 2026-10-03.
- **[inference]:** reasoning or model output. The queue simulation and the changed-tests duration estimates are
  inferences.

**Data:**

| Key | Source |
| --- | --- |
| G | GraphQL read of all 1,800 "Adoption bootstrap smoke" runs created 2026-09-23T23:16:19Z to 2026-10-03T18:29:50Z, with check-run start, end and conclusion. Fetched 2026-10-03T18:37:38Z. |
| L | GraphQL read of live jobs at 2026-10-03T18:44:39Z. |
| E | The REST sample `evidence/artifacts/macos-ci-scope-20261003/macos-ci-evidence.json`: 1,000 runs, with jobs fetched for 256. |
| R | Replay. For each PR run's head SHA, the file list of `git diff` against its merge base with main. 1,747 of 1,792 head SHAs were present; a missing diff counts as "runs". |
| M | `git log --first-parent --name-only` on `6112d14d4` since 2026-09-25T00:00:00Z: 369 commits. |
| J | REST read of the steps of job 111226811878 (run 37131206057, a PR run of 2026-10-03). |
| P | GraphQL list of the repository's 643 pull requests: head branch, state, merge commit and closedAt. Fetched 2026-10-03T20:27Z. |
| K-C | Claude's classification of the 25 macOS-only failures, made from the full-suite artifacts. |
| K-G | The GPT family's independent classification of the same 25: Sol at max effort, read-only, same artifacts. Result `macos-classify2-20261003T193218Z`. |
| O | The critic's own observations, cited where they are not re-observed here. |

The receipt `evidence/artifacts/macos-ci-scope-20261003/` holds G, R, M, J, P, E and both families' per-run labels
(`runs30.json`). Its README maps each key to its files with their sha256, names what was not retained (L, the full
K-C and K-G results, and the original replay and simulation code), and gives the command that re-runs the replay.

## 1. Question and constraints

The question: does the macOS lane cause stagnation without real benefit, and if so, should it be retired or narrowed?

**Account cap.**
- At most 5 macOS jobs run at once, shared across the whole account. [doc: docs.github.com/en/actions/reference/limits]
- The same page says "GitHub Support can increase job concurrency limits". Whether Support grants that to a `User`
  account is not verified. [doc; not verified]

**Ownership limits.** The repository owner is a `User`, which rules out:
- merge queue [doc: managing-a-merge-queue];
- larger runners [doc: actions-runner-pricing, larger-runners].

**Required checks.**
- `validate-macos` is one of 8 required contexts, with integration 15368.
- `strict_required_status_checks_policy` is `false` and `bypass_actors` is `[]`.
- [doc: `.github/main-ruleset.json:5, :32, :35-42`]

**How GitHub treats skipped checks.** [doc: troubleshooting-required-status-checks]
- A job skipped by a conditional reports "Success" to the required-check evaluation. Its check run's conclusion is
  `SKIPPED`.
- A workflow skipped by a `paths:` filter leaves its checks Pending, which blocks the merge.
- A job that depends on a failed job is skipped. A required job therefore needs `!cancelled()` or `always()` beside
  `needs`.
- Cancellation never produces a skipped, and so passing, check. In all 4 runs where `changes` was cancelled
  (36762317842, 36748640486, 36291864049 and 36101147793), every dependent bootstrap job concluded `CANCELLED`, not
  `SKIPPED`. [measured: G; also in the critic's survived-refutation list]

**Contexts the plan relies on.** [doc: contexts reference, "Context availability", read 2026-10-03]
- A job-level `env` may read `needs`.
- A job-level `if` may read `needs` and use `cancelled()`.
- A step-level `if` may read `env`.

**Re-runs and pull_request events.** [doc: re-run-workflows-and-jobs; events-that-trigger-workflows#pull_request]
- A re-run reuses the original `GITHUB_SHA` and `GITHUB_REF`.
- A `pull_request` run tests the merge commit `refs/pull/N/merge`.
- The default activity types are `opened`, `synchronize` and `reopened`.
- No run starts while the PR has a merge conflict.

**The Mac's role.** [doc]
- The Mac coordinator is live. It owns `macos-acceptance` and `coordination` (`adoption/host-roles.json:22-31`).
- Its contract is "bounded coding and local deterministic checks"
  (`docs/decisions/2026-10-02-two-host-north-star-architecture.md:38`).
- Its key acceptance is "the runner, guard and status test suites on the macOS CI job"
  (`adoption/platforms/macos-arm64.md:865-866`).
- macOS is not a supported platform. `macos-arm64` is `drafted_not_accepted` (`adoption/manifest.json:13-19, :29-46`).

**Repository rules that pin today's design.** [doc]
- `tests/test_workflow_hardening.py:1249-1257` forbids `needs:` and a job-level `if:` on `validate-macos`.
- `docs/github-automation.md:351-363`: "a required check must run on every PR".
- `docs/acceptance-evidence-policy.md:42-53` rejects a vacuous pass, including "zero tests selected". Such a check is
  recorded "as untested, not passed".
- The 09-25 overturn rule is at `docs/decisions/2026-09-22-github-automation-closure.md:1481-1486`.

## 2. Decision

Keep the macOS lane and keep `validate-macos` required. Stop running the full macOS suite on every pull request.
Narrowing beats retirement, because the lane caught a real Mac-host defect, even if late (§3.2).

### On a pull request, `validate-macos` runs in one of three ways

- **Full.**
  - Trigger: the PR changes a path in `MACOS_PATTERNS`, the list in §6.2. It has the previous round's 67 patterns plus
    22 added in review, 89 in all.
  - The job also runs in full when the `changes` job fails or cannot decide. This is the fail-safe.
- **Changed tests.**
  - Trigger: the PR changes no listed path, but changes top-level test modules (`tests/test_*.py`).
  - The same required job runs only those modules on macos-15.
  - If anything else under `tests/` changes (helpers, fixtures, data, nested paths), the job runs in full instead.
  - If every changed module was deleted, nothing is selected and the job is skipped (untested), as below.
  - If a selected module runs zero tests, the job fails rather than pass vacuously.
- **Skipped.**
  - Trigger: the PR changes neither a listed path nor a test module.
  - GitHub counts the skipped required job as passing. This record counts it as untested.

### Other parts of the decision

- **B+.** The two macOS bootstrap jobs, `bootstrap-macos` and `bootstrap-macos-brew`, run on a PR only when
  `validate-macos` runs in full. `bootstrap-linux` does not change.
- **Trigger T1 (§8.1).**
  - When main's push run first goes red on macOS only, someone posts it within 1 h and fixes or reverts it within 4 h.
  - What caused the red decides whether `tests/*` joins the list.
- **Other events.** Push, schedule and dispatch runs do not change: they always run in full. Main's push run is the
  safety net after merge.
- **Ruleset.** No change.

## 3. Evidence

### 3.1 Cost

**The job got slower.**
- The median PR `validate-macos` job went from 9.7 min on 09-24 to 34.8 min on 10-03. [measured: G]
- The suite went from 5,596 tests in 489 s (09-25) to 9,483 tests in 1,830 s (10-02). [doc: PR #632 :31-32]

**Time to result for PR `validate-macos`, from run creation to job completion.** [measured: G]

| Window | Queue median / p90 | Time to result median / p90 |
| --- | --- | --- |
| 09-24 | 0.1 / 8.4 min | 10.2 / 19.4 min |
| 09-26 to 10-03 | 1.2 / 37.2 min | 27.0 / 66.8 min |
| 10-03 | 34.8 / 124.3 min | 69.0 / 159.2 min |

The REST sample is a different sample (256 runs with jobs). It gives a queue median of 4.1 min, p90 70.4 min and max
230.1 min. It is reported beside G, not as agreement with G. [measured: E]

**One job, step by step.** [measured: J] Job 111226811878 was created at 14:54:24Z and started at 17:47:33Z, so it
queued 2 h 53 min. It then ran for 39.1 min:

| Steps | Time |
| --- | --- |
| Job setup, harden-runner and checkout | 22 s |
| The 11 validator steps | 77 s |
| macOS bootstrap smoke | 108 s |
| Recording smoke | 27 s |
| Adoption-module gate | 129 s |
| Full suite | 1,974 s |

**The 5-slot cap binds.**
- This repository alone held all 5 macOS slots for 51.3 of 235.2 h (21.8%). That counts completed jobs only, so it is a
  lower bound. [measured: G]
- **Where the completed-job slot-hours went:** [measured: G]

  | Job | PR | Push |
  | --- | --- | --- |
  | `validate-macos` | 348.8 | 120.9 |
  | `bootstrap-macos` with `-brew` | 81.2 | 27.7 |

  `validate-macos` is 81.0% of the total.

**The bootstrap jobs' path gate does little.**
- Their PATTERNS list contains `manifests/evidence.json`, which 97% of main commits touch.
- So the gate skipped them on only 52 of 1,211 PR runs that have a `changes` result (4.3%).
- At 18:37:38Z the queue held 25 `bootstrap-macos` and 24 `bootstrap-macos-brew` jobs against 18 `validate-macos`.
- [measured: G]

**Live backlog at 18:44:39Z.** [measured: L, P]
- 19 `validate-macos` jobs were queued.
- PR #666's job was queued from 16:14Z and started at 18:09:41Z. The PR was closed at 18:17:17Z.

**Queue medians over 09-26 to 10-03, on one basis (success and failure only).** [measured: G]
- 1.2 min for PR runs.
- 0.94 min for all events. Including cancelled runs it is 0.68 min.

### 3.2 Benefit: what the macOS suite found (two families, same artifacts)

**Counts by family.** [measured: K-C, K-G]

| Category | Claude | GPT |
| --- | --- | --- |
| mac-host-defect | 2 | 1 |
| test-portability-only | 12 | 10 |
| flaky-or-infra | 11 | 6 |
| unknown | 0 | 8 |
| cross-platform product defect | 0 | 0 |

**How far the families agree.**
- On category, 17 of 25: 10 portability, 6 flaky-or-infra and 1 defect.
- On the label "would affect real Mac host use", 18 of 25:
  - Claude: yes 2, no 21, unknown 2.
  - GPT: yes 1, no 15, unknown 9.
- In all 8 disagreements, GPT says unknown where Claude assigned a category. The artifact did not capture the inner
  error. No run is a defect for GPT and benign for Claude.
- Both labels are kept below, and neither is upgraded.

**Where the families agree.**
- **The Mac-host defect class.** Both families name the same and only one: Darwin `killpg` returns EPERM on a
  zombie-only process group, and the error escapes `stop_group` in
  `tools/sota-convergence/landscape-sweep/codex_job.py`. #549 fixed it (squash 50bba7bb0).
  - GPT confirms it for run 36768476923.
  - GPT leaves run 36743424532, the same class at an earlier head, as unknown.
- **No cross-platform product defect reached main.**

**The Mac-host defect did reach main, as a latent defect (D2).**
- **Introduced** with #324 (1b0e4598f, 2026-09-26T05:08:52Z). At that commit, `stop_group` catches only
  `ProcessLookupError` around both `killpg` calls, and `group_alive` treats `PermissionError` as alive.
  [doc: `git show 1b0e4598f:tools/sota-convergence/landscape-sweep/codex_job.py:370-397`]
- **Passed CI at introduction.** The required full suite passed on that commit: push run 36219928794 concluded
  `SUCCESS` at 05:28:41Z. [measured: G]
- **First detected** in run 36743424532, created 2026-09-30T16:20:04Z, about 4.5 days later. #549 had added tests that
  hit the defect.
- **Fixed on main** with 50bba7bb0 (#549, merged 2026-10-01T04:30:26Z). [measured: P]

So the suite missed the only Mac-host defect when it was introduced. What the lane did was detect it later and block
PR #549 until the product was fixed. Under an advisory lane, #549 could have merged red, and the defect would have
stayed latent. [inference]

**The 8 disagreements, with each family's reason.** [measured: K-C, K-G]

| Run | PR | Claude | GPT |
| --- | --- | --- | --- |
| 37112688327 | #647, merged | test-portability-only. The WSL install plan's `sha256sum --check --status` exits 1 under macOS's `/sbin/sha256sum`. The fixture discarded the program's output. 676bf3f14 changed only the test. | unknown. `run_program` discarded stdout and stderr, so the failing command is not in the artifact. 676bf3f14 is a candidate, not proof. |
| 37103824254 | #635, open | flaky-or-infra, Mac impact unknown. The SIGHUP subtest timed out after 20 s; SIGINT and SIGTERM passed in the same run. Cause not established; the test passed before and after. | unknown. The artifact holds no process state. The `killpg` explanation does not transfer, because `adoption_status.py` already catches `OSError`. |
| 37093976373 | #622, merged | test-portability-only. 11 of 12 failures are the `security-scan.yml` step body run under macOS bash without `mapfile`. 1 is a wall-clock flake in `test_incentive_monitor`: the run crossed 23:59 ET. | unknown at run level. The 11 portability failures are established; the monitor failure is unresolved. GPT's rule marks a run unknown if any failure is unresolved. |
| 36867111096 | push to main (b8dd81ddc) | flaky-or-infra. A time-of-check race in `closed_udp_port`, which binds `:0`, closes the socket, then probes. | unknown. The artifact records no endpoint or datagram, so port reuse, another listener and a product issue cannot be told apart. |
| 36825377925 | push to main (5597f9fae) | flaky-or-infra. A reentrancy race between a buffered print and the SIGHUP handler in the test fixture (CPython `bufferedio`). Fixed in the test by 231eed43e (#601). | unknown. The child's exception is not in the artifact. The #601 fix (d3fdc3974) is a candidate. |
| 36745793168 | #548, merged | flaky-or-infra. A Node linearity timing check, fixed by #556, plus an unexplained credential-runner error in attempt 2. | unknown at run level. The Node timing failures are established and fixed by #556; the attempt-2 timeout is unresolved. |
| 36743424532 | #549, merged | mac-host-defect. XNU `killpg` EPERM escapes `stop_group` at cc00dbd9; same class as 36768476923. | unknown. Only missing exit records; the artifact does not print the runner's exception. feeccf896 (#549) is a candidate. |
| 36514090096 | #417, merged | flaky-or-infra. The artifact-upload step failed after every bootstrap step passed; the log blob was never persisted (service side). | unknown. No action diagnostic in the evidence. |

**GPT's closing position, recorded as stated and not turned into a count.** "Linux green on the same SHA" establishes
the comparison, but does not make random-data or timing failures macOS-specific. The unresolved runs cannot be counted
as harmless when deciding how far to narrow macOS CI.

Two of GPT's eight unknown runs would not have run on their PRs under this decision (§3.3):
- 37103824254: `scripts/adoption_status.py` and its test are both listed.
- 36514090096: a bootstrap artifact upload on a docs-only PR.

Neither is counted as harmless. The code involved is listed, so any PR that changes it runs in full, and main's push
runs keep exercising it. A recurrence there fires T1 or overturn 1.

**What the Mac runs from this checkout.** [doc: the previous round's Mac host audit; spot-checked `adoption/host-roles.json:22-31`, `evidence/artifacts/mac-stage1-client-layer-20260927/README.md:688` and `docs/decisions/2026-10-02-two-host-north-star-architecture.md:36-49`]
- **Runs:**
  - the client layer and guards: `install_claude_profile.py`, `secret_path_guard.py`, `effort-default-guard.py`,
    `render_config.py` and `apply_claude_settings.py`;
  - the launcher in `bootstrap-macos.sh`;
  - the recording tooling: `host_receipts.py` and related scripts.
- **Does not run:** the brew loop or the launchd agents ("No Homebrew on this host").

### 3.3 The full macOS-only set is 30, not 25 (D4)

The 13 failures left out of the 25 all have Linux runs. 5 of them are macOS-only. [O: `gh api .../commits/<sha>/check-runs` and artifacts]

| Run | Cause | Classified by |
| --- | --- | --- |
| 36349458060 | `/private/var` in a test | the critic only |
| 36354429337 | `/private/var` in a test | the critic only |
| 36350481386 | `/private/var` in a test | the critic only |
| 36351247715 | NotADirectoryError `'var'`, per the f6e5a0384 message (#425) | the critic only |
| 36329129034 | A push run on main: a host-receipts `catalog_revision` that is not in the checkout. A data or ref issue, not Darwin. | the critic only |

That makes 30, the same count as PR #632.

**Where the 30 land.** [measured: R]

| Group | B0 (previous list) | B′ (89 patterns) | This decision (B′ + changed tests + B+) |
| --- | --- | --- | --- |
| Push runs on main | 3, unaffected | 3 | 3 |
| Bootstrap-job failures | 2, unaffected | 2 | 1 still runs. 36514090096 no longer runs (B+): Claude flaky, GPT unknown. |
| PR `validate-macos` failures that still block | 16 | 16 | 21: 16 in full mode, plus 5 deterministic failures caught in changed-tests mode |
| PR flakes that no longer block | 4 | 4 | 4: 3 skipped, 1 whose module is not selected. Three are flaky in both families; 37103824254 is Claude flaky, GPT unknown. |
| Deterministic PR failures that escape | 5 (2 merged) | 5 (2 merged) | 0 |

Restricted to the 25 that both families classified, B0 gives what the previous round meant:
- 7 PR failures no longer block: 4 flaky and 3 portability.
- 14 still run, including both defect runs.
- 2 bootstrap failures and 2 push failures are unaffected.

That sums to 25. The previous round's bullets counted the 2 defect runs twice and summed to 27.

**The escape bound is withdrawn as uninformative (D6).**
- Between the first and last of the 30 failures (2026-09-27T15:19:31Z to 2026-10-03T09:20:04Z), main took 180 squash
  merges. [measured: M]
- Under this decision, 62 of them would skip `validate-macos` entirely, and none carried a Mac-host defect.
- The one-sided 95% upper bound, 1 − 0.05^(1/62), is 4.7%. The base rate is one defect PR (#549) in 180 to 190 merged
  PRs, 0.53% to 0.56%. A bound 9 times the base rate cannot separate "the gate catches everything" from "the gate
  catches nothing". [inference]

### 3.4 The 09-25 overturn rule, checked

**Flake condition: met under Claude's labels, and at the boundary under GPT's.** The window is the 20 consecutive
decisive runs created 2026-09-30T14:19:51Z to 17:27:38Z. [measured: G]
- **Claude** classifies three of them as flaky: 36733726477, 36745793168 and 36751526079. That is 15% against a limit
  of "above 10%". [measured: K-C]
- **GPT** classifies 36733726477 and 36751526079 as flaky-or-infra. It labels 36745793168 unknown at run level.
  - In that run it establishes the Node timing failure, the same check, as flaky-or-infra in both attempts.
  - It leaves an attempt-2 credential-runner timeout unresolved.
  - Counting that run, the rate is 3 of 20. Without it, the rate is 2 of 20 = 10%, which is not above the limit.
    [measured: K-G]
- All three involve the ChildUsage Node timing check, which #556 (7d7dcd08b) fixed that day. The latest 20 decisive
  runs contain no classified flake. [measured: G + K-C]
- **This decision does not rest on that condition alone.** The user's 2026-10-03 request reopens the scope directly,
  and the 10-03 queue (median 34.8 min) is the stagnation it names.

**Queue condition: not met** over 7 days. The median is 1.2 min for PR runs against a 15-min limit (§3.1). Only the
day of 10-03 is above the limit.

**What the 09-25 record prescribes (D3, corrected).**
- It says to "move `validate-macos` back to a `paths:`-filtered, non-required lane while keeping the `bootstrap-*`
  jobs' existing gating" [doc: docs/decisions/2026-09-22-github-automation-closure.md:1485-1486]. Call that remedy C′.
- C′ is an advisory PR lane, not "post-merge and weekly only". The previous round described it wrongly.
- Its `paths:` filter would be the old one, equal to the push list, which includes `manifests/evidence.json`. That list
  matches 97% of commits, so C′ would still run the suite on nearly every PR.
- C′ therefore gives almost no slot relief and removes the merge block. It is evaluated in §4 and rejected in §5.

### 3.5 D1: what a list-only gate lets through, and the remedies measured

**Mechanism.** [doc: `.github/workflows/adoption-bootstrap.yml:616-622`, events-that-trigger-workflows,
re-run-workflows-and-jobs]
1. A PR that the gate skips can merge a test that fails on macOS.
2. Main's push run then fails.
3. Every later full-mode PR fails its required check: each tests the merge commit, which carries the failing test.
4. Fixing main does not free those PRs. A re-run reuses the same `GITHUB_SHA`, so each blocked PR needs a new event.
5. Under the previous list, a repair to an unlisted test was itself gated out.

**The 18 deterministic macOS-only PR failures in the 30, by evidence class.**
- 11 that both families agree on: 10 portability and 1 defect (36768476923).
- 3 that only Claude classified. GPT says unknown: 37112688327, 37093976373 and 36743424532.
- 4 that only the critic classified (unpaired runs, observed directly): 36349458060, 36350481386, 36351247715 and
  36354429337.

**Key observation.** In all 18, the failing test module is one that the PR's own head diff changed.
[measured: R + suite logs] No observed deterministic failure came from a product change that broke an unchanged test.

**What escapes under a list-only gate (B′).** 5 of the 18 would have been skipped. [measured: R, P]

| Run | PR | State | Evidence class |
| --- | --- | --- | --- |
| 36752399506 | #539 | merged | both families |
| 36351247715 | #425 | merged | critic only. The run-to-PR mapping is the critic's, from the f6e5a0384 message, and is not re-verified here. |
| 36524134513 | #489 | open | both families |
| 36690153586 | #535 | open | both families |
| 36350481386 | #426 | open | critic only |

- Each merged case would have turned main red on macOS only.
- 36349458060 maps to no PR in P. It runs in full under every candidate, so it does not change the comparison.

**The candidates, measured on the same data.** [measured: R and M; [inference] where marked]
- PR jobs: 1,069 completed PR `validate-macos` jobs, 348.8 slot-hours under D.
- Main commits: 369 first-parent commits.
- Simulation: a 5-slot first-in-first-out replay of all completed macOS jobs. It is a direction only: it under-predicts
  the observed p90 1.5× overall and 2.7× on 10-03.

| Candidate, on top of B′ (89 patterns) | Full-suite PR jobs | Changed-tests jobs | Skipped PR jobs | PR slot-h | Total macOS slot-h, sim (with B+) | PR wait p90 min, sim (with B+) | Deterministic failures that escape (of 18) | Merged escapes | Main commits skipped / of those touching `tests/*.py` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D, status quo | 1,069 | 0 | 0 | 348.8 | 579.7 | 19.2 (observed 29.4) | 0 | 0 | 0 / 0 |
| Previous list (B0, 67 patterns) | 416 | 0 | 653 (61.1%) | 127.6 | 358.5 (308.6) | 1.8 (0.9) | 5 | 2 | 237 / 95 |
| B′ alone, or B′ with T1 only (c) | 439 | 0 | 630 (58.9%) | 133.0 | 363.8 (315.7) | 1.8 (1.1) | 5; with (c), found after merge | 2 | 232 / 90 |
| (a-mac): plus the 117 test modules that import or name a listed module (86 new) | 578 | 0 | 491 (45.9%) | 179.1 | 409.9 (373.0) | 3.1 (2.5) | 1 (#426, open) | 0 | not computed |
| (a-all): plus `tests/*` | 702 | 0 | 367 (34.3%) | 216.0 | 446.8 (419.1) | 5.4 (4.1) | 0 | 0 | 142 / 0 |
| (b1): plus a fixed smoke run (the 7-module adoption gate) on every otherwise-skipped PR | 439 | 630 smoke runs, about 2.65 min each [inference] | 0 | 160.8 [inference] | 391.7 | 3.2 | 5. The smoke set holds none of the failing modules. | 2 | 232 / 90 |
| **(b2): plus changed-tests mode (this decision)** | **441** | **261; median 0.67, p90 1.23 min [inference]** | **367 (34.3%)** | **136.8 [inference]** | **367.7 (319.6)** | **2.4 (1.4)** | **0** | **0** | **142 / 0; another 90 run changed-tests** |

Notes on the table:
- The critic's exposure figure, 92 of 225 gated-out main commits touching `tests/*.py`, used 355 commits at
  `d2fc3803e` with a local-date boundary. The B0 row (95 of 237) is the same measure at `6112d14d4` from
  2026-09-25T00:00Z.
- The changed-tests durations are 0.5 min of setup plus the selected modules' test counts × 0.20 s per test. The 0.5
  min is one job's measured setup (J). The 0.20 s is 1,974 s / 9,849 tests from one day's suite log; real modules vary
  around that average. The VM provisioning for the 261 extra jobs is not measured.
- The (a-mac) set comes from a static scan: a test module that imports, or names by path literal, a listed non-test
  module. It covers 117 of the 234 test modules.
- **Exposure while main is red.** When main is red on macOS only, every full-mode PR stalls. That is 41.3% of PR jobs
  under (b2), against 65.7% under (a-all). Under (b2), a changed-tests PR stalls only if it changes the failing module.
  [measured: R]

**Main's push runs, as the safety net.** [measured: G]
- 391 completed push `validate-macos` runs: 383 success and 8 failure.
- The 8 failures form 6 red streaks. Each cleared at the next green push run, after 0.04 to 2.01 h.
- All 6 were flakes or infrastructure.

## 4. Options considered

| Option | Gates | Mac host needs | Throughput | Moving parts |
| --- | --- | --- | --- | --- |
| A. Retire all macOS CI | Allowed by the 09-25 overturn | Fails. It removes the only real-Darwin test of the launcher (bash 3.2), the guards, the 3.9 recording smoke and the BSD userland. The #549 defect would have stayed latent. [inference] | Best | Fewest |
| B (previous round). Required, gated by the 67-pattern list | Fails D1: 5 of 18 escape, 2 merged | Keeps a Darwin run for listed paths | 653 PR jobs skipped | One list, one output |
| B-advisory. The same list, non-required | Fails. Escapes are as in B, and failures do not block. #219 rejected this shape (docs/decisions/2026-09-22-github-automation-closure.md:1434-1437). Under it #549 could have merged red. | Weak | As B | Ruleset change |
| C′. The 09-25 remedy: non-required, PR `paths:` filter equal to the push list | Allowed, but drops the block that forced #549's product fix | Weak | Almost none: the filter matches 97% of commits | Ruleset change |
| C. Non-required; post-merge and weekly only | Allowed | Detects only after merge | Slot-hours −60% [inference] | Ruleset change |
| D. Status quo | The overturn condition is met | Full | 10-03 time to result: median 69 min, p90 159 min [measured: G] | None |
| E. A Mac-core subset (about 10 min) on every PR, full suite after merge | Allowed | Like B | Every PR still takes a slot | A curated list |
| F. PR #632's O2: an in-job gate on a frozen INERT list, 14-day dry run | Pre-registered | Like D | INERT-type lists skip about 25% | Gate script and dry run |
| G. CPython-style aggregator job | Same substance | Like B | Like B | Ruleset context swap and a new job |
| H. Merge queue | Not available to a `User` repository [doc] | — | — | Needs transfer to an organization |
| I. Buy capacity, or ask GitHub Support for a higher concurrency limit (D10) | — | — | Unknown. Larger runners need Team or Enterprise [doc]. A Support grant for a `User` account is not verified. | External |
| J. Parallelize the suite (PR #632, O4) | — | — | Shorter jobs; each PR still takes a slot | Complements every option |
| (a-mac), (a-all), (b1), (b2), (c) | The D1 remedies, measured in §3.5 | | | |

## 5. Why this decision, in the record's rule order

The record's rule order is: gates, then what the Mac host needs, then throughput, then fewer moving parts.

### 1. Gates

**Changing the lane is permitted.**
- The 09-25 flake condition was met on 09-30 under Claude's labels. Under GPT's labels it sits at the boundary (§3.4).
- The user's 2026-10-03 request reopens the scope in any case.

**The 09-25 remedy C′ is rejected.**
- Its PR filter matches 97% of commits, so it gives almost no relief.
- It is non-required, which repeats the shape that #219's evidence rejected (docs/decisions/2026-09-22-github-automation-closure.md:1434-1437).
- The required check is what made #549 fix `codex_job.py` before merging. [inference]

**PR #632's three O1 objections, answered:**
1. *"`test_workflow_hardening.py:1249-1257` forbids `needs:` and `if:`."* That test encodes the 09-25 decision, so it
   changes with this one (§6.3).
2. *"A skipped required check is a vacuous pass."*
   - The policy at `acceptance-evidence-policy.md:42-53` governs acceptance claims.
   - A skipped run is recorded `SKIPPED`, and this record counts it as untested.
   - A changed-tests run is a scoped real execution on Darwin. It refuses to pass with zero tests, and its step summary
     says the full suite did not run.
   - No PR may claim a macOS full-suite pass from either result.
3. *"The bootstrap list covers install inputs, not what 9,000 tests depend on."*
   - This record builds a new list for that purpose (§6.2).
   - Every changed test module also runs on Darwin.

**D1 (the critic's blocker).**
- **The bar.** B′ alone lets 5 of 18 deterministic failures through, 2 of them merged, so it fails.
- **(c) alone meets the critic's minimum bar** ("accepted with a trigger that fires on it"), but is rejected on the
  data.
  - In the 6-day window it would have fired twice, for the merged #425 and #539. Three more escapes sit on PRs that
    are still open.
  - That is main red on macOS about twice a week, and each time every full-mode PR stalls until a fix lands. That is
    the stagnation the user asked about.
- **(a-all) and (b2)** both let 0 of 18 escape.
- **(b2) also contains a red main better.** A red main stalls 41.3% of PR jobs under (b2), against 65.7% under
  (a-all) (§3.5).

**The path (b2) misses, and why (a-all) is not chosen.**
- (a-all) also catches an unlisted product change that breaks an unchanged test when the PR also touches some other
  test. (b2) misses that path.
- The path was observed 0 times in 18. So the decision includes the escalation itself: the first T1 event with this
  cause adds `tests/*` to the list in the fix PR, which is (a-all) (§8.1).

### 2. What the Mac host needs

- (a-all) and (b2) both keep a Darwin run for everything the Mac runs, because the list covers it.
- Both keep a Darwin run for every changed test.
- The suites named as the Mac's key acceptance (runner, guard, status) are all listed, so a change to them always runs
  in full:
  - `test_credential_run`;
  - `test_secret_path_guard` and `test_effort_default_guard`;
  - `test_adoption_status` and `test_credential_status`.
- A and C′ fail this test (§4).

### 3. Throughput

(b2) is clearly ahead of (a-all):

| Measure | (b2) | (a-all) |
| --- | --- | --- |
| Full-suite PR jobs | 441 | 702 |
| PR slot-hours | 136.8 [inference] | 216.0 |
| Total macOS slot-hours, sim, with B+ | 319.6 | 419.1 |
| PR wait p90, sim (direction only) | 1.4 min | 4.1 min |

**B+ (D5)** saves another 48 slot-hours in simulation (367.7 → 319.6). It costs nothing at the merge gate, because the
bootstrap jobs are not required and the Mac uses neither Homebrew nor the launchd agents. The previous round's 2.1-min
bootstrap durations exclude VM provisioning, so this understates the saving. [inference]

### 4. Fewer moving parts

(a-all) is simpler: one more pattern. (b2) adds four moving parts:
- one new `changes` output;
- about 15 step-level guards;
- a module-name validator;
- a zero-test guard.

This criterion ranks last, and (b2) wins on the ones before it. The hardening tests in §6.3 pin every one of the four.

**The research precedent for running only edited tests before merge** [doc]:
- PyTorch's target-determination heuristic `EditedByPR`. It runs the test files that a PR edits at top confidence
  (`tools/testing/target_determination/heuristics/edited_by_pr.py`, `_get_modified_tests`, read from `main` on
  2026-10-03).
- Google's pre-submit testing of affected targets, with full post-submit runs and culprit rollback (Memon et al.,
  ICSE-SEIP 2017). This record's T1 is a small version of that rollback discipline.

## 6. Exact changes (one implementing PR)

### 6.1 Workflow plan for `.github/workflows/adoption-bootstrap.yml`

```diff
 on:
   push:
     branches: [main]
     paths: [...]   # unchanged; 'manifests/evidence.json' stays: the post-merge net (§6.3 PushNetTests)
-  # No `paths:` filter here (2026-09-25, ...)                        (comment :35-40)
+  # No `paths:` filter here: a required check must report on every pull_request. validate-macos reports a
+  # full result, a changed-tests result or SKIPPED, as the `changes` job decides
+  # (docs/decisions/2026-10-03-macos-ci-scope.md).
   pull_request:
   schedule: [unchanged]
   workflow_dispatch:

-  # Lightweight path-change detector ... (comment :54-63)
+  # (rewritten to describe bootstrap, macos and macos_tests; every failure path calls fail_safe)
   changes:
     if: github.event_name == 'pull_request'          # unchanged
     outputs:
       bootstrap: ${{ steps.filter.outputs.bootstrap }}
+      macos: ${{ steps.filter.outputs.macos }}
+      macos_tests: ${{ steps.filter.outputs.macos_tests }}
     steps:
-      - name: Detect whether any bootstrap-relevant path changed in this pull request
+      - name: Detect which bootstrap- and macOS-relevant paths changed in this pull request
         id: filter
         run: |
           set +e
           set -uo pipefail
+          fail_safe() {
+            echo "bootstrap=true" >> "$GITHUB_OUTPUT"
+            echo "macos=true" >> "$GITHUB_OUTPUT"
+            echo "macos_tests=" >> "$GITHUB_OUTPUT"
+          }
           PATTERNS=( ...unchanged... )
+          MACOS_PATTERNS=( ...the 89 entries of §6.2, one quoted entry per line... )
           if [ -z "${BASE_SHA:-}" ] || [ -z "${HEAD_SHA:-}" ]; then
             echo "::warning::changes: missing base or head sha ...; failing safe" >&2
-            echo "bootstrap=true" >> "$GITHUB_OUTPUT"
+            fail_safe
             exit 0
           fi
-          diff_file="$(mktemp)" || { echo "bootstrap=true" >> "$GITHUB_OUTPUT"; exit 0; }
+          diff_file="$(mktemp)" || { fail_safe; exit 0; }
           if ! git diff -z --no-renames --name-only "$BASE_SHA...$HEAD_SHA" > "$diff_file"; then
             echo "::warning::changes: git diff failed; failing safe" >&2
-            echo "bootstrap=true" >> "$GITHUB_OUTPUT"
+            fail_safe
             rm -f "$diff_file"
             exit 0
           fi
-          match=false
+          match=false; macos=false; tests_other=false
+          macos_paths=(); test_modules=()
           while IFS= read -r -d '' file; do
             [ -z "$file" ] && continue
             ...existing PATTERNS loop, unchanged...
+            for pattern in "${MACOS_PATTERNS[@]}"; do
+              # shellcheck disable=SC2254
+              case "$file" in
+                $pattern) macos=true; macos_paths+=("$file"); break ;;
+              esac
+            done
+            case "$file" in
+              tests/*)
+                rest="${file#tests/}"
+                case "$rest" in
+                  */*) tests_other=true ;;   # nested path; tested first, because a case-glob `*` also matches `/`
+                  test_*.py)
+                    module="tests.${rest%.py}"
+                    if [[ "$module" =~ ^tests\.test_[A-Za-z0-9_]+$ ]]; then
+                      [ -f "$file" ] && test_modules+=("$module")   # a module the PR deleted is dropped
+                    else
+                      tests_other=true                             # any other name shape: full mode
+                    fi ;;
+                  *) tests_other=true ;;     # helpers, fixtures, data: full mode
+                esac ;;
+            esac
           done < "$diff_file"
           rm -f "$diff_file"
+          if [ "$macos" = false ] && [ "$tests_other" = true ]; then macos=true; fi
+          macos_tests=""
+          if [ "$macos" = false ]; then macos_tests="${test_modules[*]:-}"; fi
           echo "bootstrap=$match" >> "$GITHUB_OUTPUT"
+          echo "macos=$macos" >> "$GITHUB_OUTPUT"
+          echo "macos_tests=$macos_tests" >> "$GITHUB_OUTPUT"
+          # Step summary. Full: list macos_paths, or "a non-module tests/ path changed".
+          # Changed-tests: list the modules and say the full suite will not run.
+          # Skip: "validate-macos skipped: no listed path and no test module changed
+          # (docs/decisions/2026-10-03-macos-ci-scope.md); untested, not passed; main's push run covers it."

   bootstrap-macos:                                   # :247
   bootstrap-macos-brew:                              # :541
-    if: ${{ !cancelled() && (github.event_name != 'pull_request' || needs.changes.outputs.bootstrap != 'false') }}
+    if: ${{ !cancelled() && (github.event_name != 'pull_request' || (needs.changes.outputs.bootstrap != 'false' && needs.changes.outputs.macos != 'false')) }}
   # bootstrap-linux (:173) unchanged

-  # Required check (...): ... It has no `needs:` and no `if:` of its own ...   (comment :601-605)
+  # Required check (.github/main-ruleset.json). On pull_request it runs full, changed-tests or not at all, as
+  # `changes` decides (docs/decisions/2026-10-03-macos-ci-scope.md); off pull_request it always runs full.
+  # A skipped run is untested, not passed; a changed-tests run is a scoped result, not a full-suite pass.
   validate-macos:
+    needs: changes
+    # !cancelled() replaces the implicit success() of `needs` (changes is skipped off pull_request, and a
+    # failed changes job must still run this job). `!= 'false'`, never `== 'true'`: an empty output
+    # (changes failed, cancelled or skipped) runs the full job.
+    if: ${{ !cancelled() && (github.event_name != 'pull_request' || needs.changes.outputs.macos != 'false' || needs.changes.outputs.macos_tests != '') }}
     runs-on: macos-15
     timeout-minutes: 60
+    env:
+      VALIDATE_MACOS_MODE: ${{ (github.event_name == 'pull_request' && needs.changes.outputs.macos == 'false') && 'changed-tests' || 'full' }}
     steps:
       # harden-runner, checkout and setup-python: unchanged, no if:
       - name: Validate manifests and evidence integrity
+        if: env.VALIDATE_MACOS_MODE == 'full'
       # ...the same `if:` line on each of the 15 steps from "Validate manifests and evidence integrity" (:628)
       # through "Run the full test suite (gating on macOS)" (:732)...
+      - name: Run the changed test modules (changed-tests mode)
+        if: env.VALIDATE_MACOS_MODE == 'changed-tests'
+        shell: bash
+        env:
+          MODULES: ${{ needs.changes.outputs.macos_tests }}
+        run: |
+          set +e
+          read -r -a modules <<< "$MODULES"
+          python3 -m unittest -v "${modules[@]}" >full-suite-macos.log 2>&1
+          code=$?
+          set -e
+          ran="$(sed -n 's/^Ran \([0-9][0-9]*\) tests\{0,1\} in .*/\1/p' full-suite-macos.log | tail -n 1)"
+          echo "validate-macos changed-tests mode: ran ${ran:-0} tests from: $MODULES. The full suite did not run; this is a scoped result, not a macOS full-suite pass." >> "$GITHUB_STEP_SUMMARY"
+          tail -n 5 full-suite-macos.log
+          if [ "${ran:-0}" -eq 0 ]; then
+            echo "::error::changed-tests mode ran no test: untested, not passed (docs/acceptance-evidence-policy.md)"
+            exit 1
+          fi
+          exit "$code"
       - name: Upload the full test suite result   # unchanged: if: always(); uploads the log of either mode
```

**Security notes.**
- The module list reaches the shell only through `env:`, never as `${{ }}` inside `run:`.
- `changes` admits only names that match `^tests\.test_[A-Za-z0-9_]+$`. Any other name forces full mode.
- The offline zizmor pass and actionlint 1.7.12 must stay clean, as at docs/decisions/2026-09-22-github-automation-closure.md:1525-1528.

**Precedent.** The fail-safe shape (`!cancelled()` with `!= 'false'`) is the one the bootstrap jobs already use
(:157-173). It follows GitHub's guidance to pair `always()` with `needs` for required checks. [doc]

### 6.2 `MACOS_PATTERNS`: criteria, literal list and recorded exclusions

**Criteria.** A path is listed if it meets any of C1 to C8. The implementing PR may add entries only under these
criteria.

The literal list follows, in bash case-glob spelling. In a case pattern `*` also matches `/`, so `dir/*` covers the
whole tree.

```
# C1  the workflow itself
'.github/workflows/adoption-bootstrap.yml'
# C2  the macOS install and launcher surface
'adoption/bootstrap-macos.sh'
'adoption/pins-macos-arm64.json'
'adoption/manifest.json'
'adoption/launchd/*'
'adoption/tools/*'
'tools/adoption/render_launchd.py'
'tools/adoption/embed_acceptance.py'
'evidence/artifacts/macos-embed-reference-20260923/*'
# C3  code the Mac runs from this checkout
'adoption/hooks/*'
'scripts/hooks/*'
'tools/adoption/install_claude_profile.py'
'tools/adoption/render_config.py'
'tools/adoption/apply_claude_settings.py'
'tools/adoption/install_skills.py'
'tools/adoption/managed_block.py'
'scripts/host_receipts.py'
'scripts/hardware_profile.py'
'scripts/component_matrix.py'
'scripts/new_host_grand_list.py'
'scripts/validate.py'
'scripts/adoption_status.py'
'scripts/platform_status.py'
'scripts/path_safety.py'
# C4  code documented as running on macOS
'tools/sota-convergence/landscape-sweep/*'
'tools/credentials/*'
# C5  non-test code with a Darwin branch, macOS path handling (/private/tmp, /private/var),
#     or a non-Linux refusal that listed code executes
'blueprints/convergence-practice/mac-memory-patch/*'
'blueprints/convergence-practice/document-ingestion/bootstrap.py'
'blueprints/us-equities/data-lake/backfill.py'
'tools/token-e2e/freeze_snapshot.py'
'blueprints/us-equities/adaptive-paper/credential_guard.py'
'scripts/kernel_keyring.py'
'tools/sota-convergence/adjudicate.py'
'blueprints/convergence-practice/offhost-app-state/run.py'
'blueprints/convergence-practice/offhost-restore/verify.py'
'blueprints/convergence-practice/service-reboot/run.py'
'blueprints/us-equities/alpaca-historical/collect.py'
'blueprints/us-equities/catalyst-dataset/dataset.py'
'blueprints/us-equities/research-efficiency/experiment.py'
# C6  in-repo import closure of C3 and C4
'scripts/catalog_decisions.py'
'scripts/landscape.py'
'scripts/saturation_ledger.py'
'scripts/new_wsl_profile.py'
'scripts/codex_quota.py'
'scripts/credential_boot_receipt.py'
'scripts/credential_status.py'
'tools/adoption/apply_codex_lane.py'
'tools/adoption/codex_roles.py'
# C8  scripts validate-macos runs as its own steps (adoption-bootstrap.yml:628-661)
'scripts/validate_catalogs.py'
'scripts/validate_foundation.py'
'scripts/build_ecosystem.py'
'tools/sota-convergence/build_verdicts.py'
'scripts/validate_convergence.py'
'scripts/release_due.py'
# C7  tests: the job's own gate set, direct tests of C2-C6, and Darwin-branch or bash-3.2 test files
'tests/test_adoption_bootstrap.py'
'tests/test_adoption_bootstrap_macos.py'
'tests/test_adoption_launchd.py'
'tests/test_adoption_contract.py'
'tests/test_adoption_status.py'
'tests/test_adoption_version_probes.py'
'tests/test_render_config.py'
'tests/test_workflow_hardening.py'
'tests/test_workflow_security_coverage.py'
'tests/test_install_claude_profile.py'
'tests/test_apply_claude_settings.py'
'tests/test_effort_default_guard.py'
'tests/test_secret_path_guard.py'
'tests/test_host_receipts.py'
'tests/test_component_matrix.py'
'tests/test_new_host_grand_list.py'
'tests/test_path_safety.py'
'tests/test_hardware_profile*.py'
'tests/test_gitleaks_guarded_macos.py'
'tests/test_credential_run.py'
'tests/test_landscape_sweep_*.py'
'tests/test_gpt6_family_tiering_20260926.py'
'tests/test_local_inference_latest_20260926.py'
'tests/test_native_dashboard_data.py'
'tests/test_new_wsl_client_config.py'
'tests/test_observability_writer_identity.py'
'tests/test_observability_writer_identity_host.py'
'tests/test_child_usage_suite.py'
'tests/test_install_skills.py'
'tests/test_managed_block.py'
'tests/test_platform_status.py'
'tests/test_currency_due_notice.py'
'tests/test_token_lanes_subagent_start.py'
'tests/test_credential_tools.py'
'tests/test_credential_status.py'
```

**Coverage.** 89 patterns match 151 tracked files at `6112d14d4`, and no pattern is dead. [measured: `git ls-files` +
fnmatch]

**The 22 additions, by critic item.**
- **D8, 7 direct tests of listed modules.** `tests/test_credential_status.py` is the most likely "status" suite in
  `macos-arm64.md:866`. That identification is an inference.
- **C5, widened, 9 files.** Found by the widened grep below.
- **C8, 6 step scripts.** This reconciles the list with `tests/test_adoption_bootstrap_macos.py:3712-3725`.

**Drift guard.** The C5 grep is widened to cover:
- `/private/(tmp|var)`;
- `platform.system() != 'Linux'`;
- `sys.platform != 'linux'`.

It runs over non-test code, excluding `tests/`, `evidence/`, `docs/`, `catalogs/`, `*.md` and `*.json`. It finds 27
files at `6112d14d4`: 21 are covered, and 6 are excluded with a reason. [measured]

**Recorded exclusions.** The drift-guard test carries these in an `EXCLUDED` map.

| Path | Why it is not listed |
| --- | --- |
| `blueprints/convergence-practice/wsl-memory-maintenance/run.py` | Refuses to run off Linux x86_64 (`:172`). A WSL-host blueprint the Mac never runs. |
| `blueprints/convergence-practice/wsl-native-tools/install.py` | Same refusal (`:48`). |
| `blueprints/convergence-practice/wsl-retrieval/run-initial.py.txt`, `run-qmd-attempt-2.py.txt`, `run-recording-aid.py.txt` | Archived run scripts kept as text. Never executed; Linux-only guard. |
| `blueprints/gap-resolution-20260922/worktrunk-0-79-0-requalify/install.py` | Refuses to run off Linux x86_64 (`:48`). |
| `manifests/evidence.json` (an input that `test_adoption_bootstrap_macos.py:3712-3725` lists) | 97% of main commits touch it. It is platform-neutral JSON, and Linux `validate` runs the same validators on it. It stays in the push `paths:` as the post-merge net (D11). |
| `blueprints/convergence-practice/wsl-native-tools/pins.json` (a bootstrap PATTERNS entry) | WSL tool pins with no macOS consumer. [inference] |
| `adoption/templates/*`, `adoption/hosts/*` | Data that the listed `render_config.py` consumes. Listing them would add 38 full-suite PR jobs (439 → 477), and no macOS-only failure from them was observed. Push runs cover them after merge, because `adoption/**` is a push path. [measured: R] |

### 6.3 Tests

These are local integration tests on Linux `validate`.

**Expectations that change in `tests/test_workflow_hardening.py` (D9).**
- **`:1249-1257`, `test_validate_macos_is_reachable_on_every_pull_request`.** Replaced by
  `test_validate_macos_gate_fails_safe`, which asserts:
  - `needs: changes`;
  - `block_if(job)` matches `!cancelled()` or `always()`;
  - the condition contains `github.event_name != 'pull_request'`, `needs.changes.outputs.macos != 'false'` and
    `needs.changes.outputs.macos_tests != ''`;
  - the condition contains no `== 'true'`;
  - the job-level `env` defines `VALIDATE_MACOS_MODE` with `'full'` as the fallback branch.
- **`:1292-1300`, `test_the_pre_fix_condition_text_fails_this_tests_own_assertions`.** Extended: the text
  `needs.changes.outputs.macos == 'true'` must fail the new gate assertions. This is the negative control.
- **`:1259-1290`, `test_bootstrap_jobs_stay_path_gated_on_pull_request_and_still_run_off_it`.**
  - The current assertions stay.
  - For `bootstrap-macos` and `bootstrap-macos-brew`, add: `needs.changes.outputs.macos != 'false'` is present and
    `macos == 'true'` is absent.
  - For `bootstrap-linux`, add: no `outputs.macos` term.
- **`:1321`.** `re.findall(r"(?m)^            '([^']+)'$", job)` collects every 12-space quoted line in the job. It would
  now collect `MACOS_PATTERNS` too and fail the PATTERNS-equals-push-paths assertion. Scope it to the text between
  `PATTERNS=(` and its closing `)`. The assertion itself stays.
- **`:1331`.** It finds the step by the fragment "Detect whether any bootstrap-relevant path changed". Change the
  fragment to "Detect which bootstrap- and macOS-relevant paths changed".
- **`:1336`.** The asserted literal becomes `diff_file="$(mktemp)" || { fail_safe; exit 0; }`.
- **`:1348` and `:1352`.** These assert `echo "bootstrap=true"` inside the missing-SHA and diff-failure blocks. They
  now assert `fail_safe` there.
- **New fail-safe assertion.** The `fail_safe` body writes `bootstrap=true`, `macos=true` and an empty `macos_tests`.

**Unchanged tests.**
- `test_pull_request_trigger_has_no_path_filter` (`:1244-1247`).
- `TargetRulesetTests` (`:467-487`): `validate-macos` stays required at 15368, and strict stays off.
- `test_adoption_bootstrap_macos_jobs_are_not_exempt` (`:141-155`).
- `tests/test_adoption_bootstrap_macos.py:3727-3731` needs a comment update only.
- `tests/test_shell_parser_ci.py:70` and `tests/test_landscape_sweep_skills.py:2324` keep their
  `adoption-bootstrap.yml:validate-macos` entries.

**New tests.**
- **`MacosPatternsTests`:**
  - The list contains the workflow file.
  - Every pattern matches at least one `git ls-files` path.
  - Drift guard: every non-test file the widened C5 grep finds is either covered or named in `EXCLUDED` with a reason.
  - Every script that a `validate-macos` `run:` line executes is covered.
  - Every input that `test_adoption_bootstrap_macos.py:3712-3725` lists is covered, except `manifests/evidence.json`.
- **`ValidateMacosModeTests`:**
  - Every `validate-macos` step after setup-python carries exactly `if: env.VALIDATE_MACOS_MODE == 'full'`. The
    exceptions are the changed-tests step and the `always()` upload.
  - The changed-tests step carries `if: env.VALIDATE_MACOS_MODE == 'changed-tests'`.
  - That step reads `MODULES` from `env:` and has no `${{` inside `run:`.
  - It contains the zero-test guard.
  - The `changes` script validates module names against `^tests\.test_[A-Za-z0-9_]+$`.
  - It tests for nested paths before `test_*.py`.
  - It drops missing files with `[ -f "$file" ]`.
  - Negative control: the step text with the guard line removed must fail.
- **`PushNetTests` (D11):** the push `paths:` keeps `manifests/evidence.json`, and the comment above it names it as the
  post-merge net.

**Acceptance commands.**
- `python3 scripts/validate.py`
- `python3 -m unittest` with these modules: `tests.test_workflow_hardening`, `tests.test_adoption_bootstrap_macos`,
  `tests.test_adoption_bootstrap`, `tests.test_shell_parser_ci`, `tests.test_landscape_sweep_skills` and
  `tests.test_workflow_security_coverage`
- actionlint 1.7.12 with shellcheck on `PATH`
- the offline zizmor strict pass

### 6.4 Ruleset

**No change.**
- `validate-macos` stays a required context, integration 15368.
- `strict_required_status_checks_policy` stays `false`, and `bypass_actors` stays `[]`.
- [doc: `.github/main-ruleset.json:5, :32, :41`]

The job's name does not change, so the context still matches. A job skipped by a job-level conditional satisfies a
required check. [doc: troubleshooting-required-status-checks]

### 6.5 Docs and records

- **`docs/github-automation.md:351-363`.**
  - A required check must report on every PR.
  - `validate-macos` reports full, changed-tests or skipped.
  - A job skipped by a job-level conditional reports `skipped`, which GitHub accepts.
  - A changed-tests result is scoped.
- **`docs/decisions/2026-09-22-github-automation-closure.md:1420`.** Add a dated note: "Superseded in part 2026-10-03:
  flake overturn met 09-30; the prescribed non-required lane was rejected; see 2026-10-03-macos-ci-scope.md".
- **`adoption/platforms/macos-arm64.md:865-866`.** Say when `validate-macos` runs each mode. Say that the Mac's key
  acceptance suites are listed, so changes to them always run in full.
- **This record, plus a sanitized measurement receipt under `evidence/`.**
  - The receipt holds G, R, M, the simulation code and its outputs, and the dual-family classification counts.
  - Add its `manifests/evidence.json` entry.
  - The receipt is `evidence/artifacts/macos-ci-scope-20261003/`. Its README lists each file with its sha256, says
    where the working copies came from, and gives the command that re-runs the replay.
- **The PR.** It carries `lane:foundation` and a `## SOTA sources` section.
- **PR #632.** The owner either marks its Decision and Alternatives as superseded, or closes it and carries its receipt
  into this PR. Its R6 (de-flake the signal and timing tests) still stands.

### 6.6 Cut-over and queued runs (D7 fixed)

1. **The gate PR changes the workflow (C1),** so its own `validate-macos` runs in full. That is control (a) in §6.7.
2. **Optionally cancel queued PR runs.** This is the owner's call, because it touches other lanes' PRs.
   - **Why the old recipe was wrong.** A run lists as `queued` while any of its jobs is queued, even with
     `validate-macos` in progress. At 19:30:08Z, 5 such runs held slots [O]. `gh run cancel` cancels the whole run,
     including a running bootstrap job.
   - **List the queued runs:**
     ```
     gh run list -R seathatflowsinourveins/native-agent-stack -w adoption-bootstrap.yml -s queued -e pull_request -L 100 --json databaseId
     ```
   - **Check each run's jobs.** For each ID, read the job statuses with `gh run view <id> --json jobs`.
   - **Keep only runs that qualify.** A run qualifies when no job is `in_progress` and `validate-macos` is `queued`.
   - **Record the literal IDs** on the lane board.
   - **Cancel by recorded ID only:** `gh run cancel <id>`.
   - **Budget.** This costs 1 + N calls against the shared gh login.
3. **After merge, each open PR needs a new `pull_request` event**: a push, or close and reopen. A re-run reuses the old
   SHA and workflow file. [doc]
4. **Re-measure with the same GraphQL read after 24 h and after 7 days:**
   - the share of PR runs in each mode;
   - the PR `validate-macos` queue p90;
   - T1 events.

### 6.7 Hosted controls

These are discriminating controls, as `acceptance-evidence-policy.md:42-53` requires. Each runs on a throwaway PR
unless stated.

- **(a) Listed path runs in full.** The gate PR itself. It must pass.
- **(b) Unlisted path with no test change is skipped.** A docs-only PR.
  - `validate-macos`, `bootstrap-macos` and `bootstrap-macos-brew` all conclude `SKIPPED`.
  - `gh pr view --json mergeStateStatus` shows the PR mergeable under the live ruleset.
- **(c) Changed-tests mode, negative first.** The PR adds `tests/test_zz_macos_mode_probe.py`, whose one test asserts
  `sys.platform != "darwin"`, and touches no listed path.
  - Changed-tests mode runs 1 test and fails.
  - With the assertion inverted, it passes, and the step summary says "ran 1 tests from: tests.test_zz_macos_mode_probe".
- **(d) A zero-test selection is skipped, not passed.** The PR only deletes a top-level test module. `macos_tests` is
  empty, and `validate-macos` concludes `SKIPPED`, not `SUCCESS`.
- **(e) A changed helper runs in full.** The PR changes a non-module file under `tests/`.
- **(f) Fail-safe.** The PR's `changes` step exits before writing outputs. `validate-macos` runs in full.
- **(g) Push runs are unchanged.** The first push to main after the merge runs in full.

### 6.8 Implementation notes (2026-10-03, implementing PR)

Where the implementation goes beyond the §6.1 sketch, and why. None of these changes which mode a pull request gets.

- **Output order.** `changes` writes `macos_tests`, then `bootstrap`, then `macos`, both in `fail_safe` and on the
  normal path. The sketch wrote `macos` before `macos_tests`: a step that stopped between the two would leave
  `macos=false` with no module list, which skips `validate-macos`. With `macos` last, any earlier stop leaves it
  empty, and an empty output runs the full job.
- **Grouped writes.** Each set of outputs is one grouped write, `{ ...; } >> "$GITHUB_OUTPUT"`, as in
  `catalog-freshness.yml`. The `validate` job's actionlint step runs shellcheck, whose SC2129 fails consecutive
  separate redirects to one file; the sketch's separate `echo ... >> "$GITHUB_OUTPUT"` lines failed it locally
  (kjanat/actionlint 1.17.0 with shellcheck 0.11.0). So the §6.3 assertions on those lines read the grouped write.
- **Empty selection.** The changed-tests step fails when `MODULES` is empty, before `unittest` starts: with no module
  argument, `python3 -m unittest` would discover and run the whole suite under the changed-tests label. The step
  also re-checks each name against `^tests\.test_[A-Za-z0-9_]+$`.
- **Locale.** `changes` runs under `LC_ALL=C`, so the module-name regex admits ASCII names only.
- **Step summaries.** `changes` shows Mac-relevant paths only in the characters `[A-Za-z0-9._/+-]` (any other as `?`),
  at most 20. Its skip summary also carries the line "skipped: no Mac-relevant change; this is not a macOS pass". The
  changed-tests summary adds the skipped-test count after "ran N tests from: <modules>".
- **bash 3.2.** `changes` keeps its matched paths and modules in strings, not arrays: expanding an empty array under
  `set -u` is an error before bash 4.4, and the hardening tests also run the script on macOS.
- **Tests beyond §6.3.** `ChangesModeComputationTests` runs the `changes` script against a scratch repository: a listed
  path gives full mode; top-level test modules alone give changed-tests mode; any other `tests/` path gives full mode;
  a change to neither, or a deletion only, is skipped; a missing or unknown SHA gives full mode. One mutation control
  per guard must turn its scenario red. `ChangedTestsStepRunTests` runs the changed-tests step against probe modules,
  with a control showing that the zero-test guard is what fails a "Ran 0 tests" run that exits 0.
- **Drift-guard expression.** §6.2 names the three widened terms. The test's expression also carries C5's Darwin-branch
  terms: a quoted `Darwin`, a shell comparison with `Darwin`, and `sys.platform == "darwin"`. At the verification base
  it finds the same 27 files as `git grep -I -E` with that expression: 21 covered and 6 excluded.
- **actionlint.** §6.1 and §6.3 name actionlint 1.7.12. The repository's `validate` job has run kjanat/actionlint
  1.17.0 since 2026-09-28 (`.github/workflows/validate.yml:76-92`), and that run checks this workflow.

## 7. Rollback

- `git revert` the gate's squash commit through a PR. That PR touches the workflow (C1), so it runs in full. The ruleset
  never changed.
- Open PRs keep their last result until their next event. To restore full per-PR coverage at once, re-trigger them.
- A rollback takes about one PR cycle: about 35 min plus the queue. [inference]

## 8. Overturn conditions

Measured the same way as here: GraphQL check runs, with both families' classification rubric.

### 8.1 T1, the D1 trigger (part of the decision)

**When T1 fires.**
- A push, schedule or dispatch `validate-macos` run on main concludes `FAILURE`, and Linux `validate` concluded
  `SUCCESS` on the same SHA. Call that main being red on macOS only.
- The first such run fires T1.

**Within 1 h of that run's completion,** the foundation lane posts to the lane board:
- the run URL;
- the SHA;
- the PR that introduced the failing content, found with `git log` on the failing test module or path.

**Within 4 h,** a fix or a `git revert` of the introducing PR merges.
- The fix PR changes the failing module or a listed path, so it runs in changed-tests or full mode. The repair is
  therefore proven on Darwin before it merges.
- Why 4 h: the 6 red streaks on main in the window cleared in 0.04 to 2.01 h (§3.5). 4 h is about twice the longest.
  [inference]

**If the remedy fails, these fire:**
1. **The 4-h deadline passes.** Any coordinator reverts the introducing PR.
2. **The cause is the path (b2) misses.** That is, the introducing PR did not change the failing test module (a product
   change broke an unchanged test), or a changed-tests pass is later contradicted on main for the same module.
   - The fix PR also adds `tests/*` to `MACOS_PATTERNS`, which moves to (a-all).
   - A follow-up record states the cause.
3. **The cause is a path that meets C1 to C8 but is missing from the list.** The fix PR adds it.
4. **Two T1 events within 30 days, whatever the cause.** Move to (a-all).
5. **Three T1 events within 30 days.** Revert to D, the ungated required check, until a new record is written.

**T1 is a process rule.** This record names no mechanism inside the repository for it, so the implementing PR
automates none of it: no workflow step detects a macOS-only red run on main or posts it. The foundation lane watches
main's push runs and acts as above.

### 8.2 Other overturn conditions

1. **Mac-host product escape.**
   - The condition: a red push run on main, on macOS only, that traces to a PR whose `validate-macos` was skipped or
     ran in changed-tests mode, and that both families classify as a Mac-host product defect.
   - If its path meets a criterion, fix the list.
   - If it meets none, revert to D until a criterion is recorded.
   - Two list-gap escapes within 30 days also revert to D.
2. **Queue.** The PR `validate-macos` queue p90 stays above 15 min over any 7 days. Apply these levers in order:
   1. R1: collapse push runs on main.
   2. J: parallelize the suite.
   3. A GitHub Support request for higher concurrency. Availability for a `User` account is not verified.
   4. If the queue is still above 15 min, move to C′.
3. **Flake.** Classified flakes exceed 10% of a rolling window of 20 decisive full-mode runs, for 7 days.
   - Hand them to R6's owners.
   - If they are not fixed, move to C′.
4. **No benefit, powered (D6).**
   - After at least 600 merged PRs with no Mac-host defect caught on a PR or on main, move to C′.
   - At the observed rate of 1 in 180 to 190, the expected count is 3.2 to 3.3, so P(0 | rate unchanged) is about
     0.04.
   - If the Mac stops running code from this checkout, move to A.
5. **Host role.**
   - If `host-roles.json` drops the Mac's `coordination` and `macos-acceptance` roles, move to A.
   - If `macos-arm64` leaves `drafted_not_accepted`, move to D, as shipping-platform coverage.
6. **Platform.** Any of these reopens the decision:
   - a merge queue becomes available;
   - GitHub changes how a skipped job counts for a required check;
   - the macOS concurrency cap changes;
   - Support raises the limit.
7. **Timeout.** A full-mode run hits 60 min. As a stopgap, raise the timeout; then run J.
8. **Push net (D11).** Either of these:
   - `manifests/evidence.json` leaves the push `paths:`;
   - fewer than 90% of main merges get their own push run over 7 days.

   Then re-plan the net before the next merge: run `changes` on push and drop the push `paths:` filter, or add a daily
   schedule.

## 9. Residuals

- **The replay is retrospective, not held out.** The list and the remedy were designed with the classification already
  known. Prospective evidence comes from the 24-h and 7-day re-measurements and from push runs.
- **(b2)'s structural gap.** An unlisted product change can break an unchanged test while the PR also changes some other
  test. This was observed 0 times in 18, and T1's escalation covers it.
- **The changed-tests costs are estimates.** They rest on one job's setup time and an average per-test time. VM
  provisioning for about 261 extra short jobs in the window is not measured.
- **The simulation is a lower bound.** It under-predicts observed waits 1.5× overall and 2.7× on 10-03. Its numbers
  show direction only.
- **Classification limits.**
  - GPT left 8 of 25 unknown.
  - GPT's position is recorded: unresolved runs cannot be counted as harmless.
  - The 5 runs outside the 25 rest on the critic's single-family observation.
  - The 36351247715 → #425 mapping is borrowed from the critic.
  - 36349458060 maps to no PR.
- **The suite's sensitivity to Mac-host defects is low or unknown.** The one Mac-host defect passed the full suite when
  it was introduced, and was found 4.5 days later.
- **A scoped or skipped result can be misread as a macOS pass.** The mitigations are the step-summary text, this record
  and the docs. Some reader may still misread one.
- **Fix-forward needs an owner.** T1 names the foundation lane. Its 1-h and 4-h deadlines depend on that lane being
  staffed.
- **The push net is coverage by coincidence.** It exists because 97% of commits touch `manifests/evidence.json`.
  `MACOS_PATTERNS` is not a subset of the push paths, so a merge that touches no push path gets no push run of its own.
  Its content is tested at the next push run or the weekly run.
  - Under this decision, that gap matters only for merges in skip mode: changed-tests merges already ran their modules
    on Darwin before merging.
- **The list may be incomplete.** The import closure is static, and some data that Mac-run code consumes is excluded by
  decision: `adoption/templates/**`, `adoption/hosts/**`, and agent and skill content.
- **Unmeasured load.**
  - Other repositories in the account share the 5 macOS slots, and their usage is unknown.
  - macOS jobs outside this workflow were not measured, for example `hardware-profile-smoke.yml`'s `macos-profile` job.
- **Two open follow-ups**, unknown in at least one family:
  - `bootstrap-macos.sh`'s `curl --retry 3` did not retry a 5xx that surfaced as exit 56 (run 37109532368);
  - the SIGHUP timeout in `tests/test_adoption_status.py` (run 37103824254).
- **Full-mode PRs are still slow.** They pay about 35 min, and flakes still block them.
- **Merge skew is unchanged.** `strict` stays off.
- **Two records disagree** until PR #632 is amended or closed.

## 10. Measurement notes

- **Reproduced in all three rounds** (previous, critic's and this one):
  - the replay of B0: 653 of 1,069 PR jobs skipped;
  - total macOS slot-hours, D / B0 / B0+: 579.7 / 358.5 / 308.6;
  - 348.8 slot-hours for PR `validate-macos`;
  - 52 skipped bootstrap check runs.
- **New in this round:**
  - the queue medians 1.2 / 0.94 / 0.68;
  - 1,211 PR runs with a `changes` result;
  - the push-run red streaks;
  - the 4 cancelled-`changes` runs;
  - every number for B′, (a-mac), (a-all), (b1) and (b2);
  - the main-commit exposure at `6112d14d4`;
  - the 30-run tallies.
- **Taken from the previous round, with the critic's confirmation, and not recomputed here:**
  - the time-to-result table;
  - the live backlog L;
  - 51.3 of 235.2 h at full occupancy;
  - 120.9 push slot-hours;
  - "the latest 20 decisive runs contain no classified flake".
- **The observed PR wait p90 reads 28.9, 29.0 or 29.4 min,** depending on the quantile rule (draft, critic and this
  round). On 10-03 it reads 124.3, 126.5 or 135.4.
- **gh use in this round:**
  - 1 paginated GraphQL command for the PR list (13 pages);
  - 1 REST read of one job's steps.
- **Load.** No heavy replay ran during the 21:30Z to 01:00Z measurement window. Every git replay and simulation finished
  before 20:50Z, at nice 19.
- **Receipt check (implementing PR, 2026-10-03).** `evidence/artifacts/macos-ci-scope-20261003/replay.py` re-ran the
  pull-request replay from G, R and M with the shipped `MACOS_PATTERNS` and matched every figure it checks: the five
  candidate rows of §3.5 (counts, slot-hours, and (b2)'s 0.67 / 1.23 min estimate), the 18 D1 rows and their escapes,
  the pull-request rows of the 30-run table, the main-commit exposure and the coverage (89 patterns, 151 files, none
  dead). Its output is `replay-output.txt` beside it. Two figures do not reproduce, and the decision rests on neither:
  - The saved simulation output, `sim_r2.json`, gives (b2) with B+ as 339.9 slot-hours and a PR wait p90 of 1.7 min,
    not the 319.6 and 1.4 in §3.5 and §5, so "B+ saves another 48 slot-hours" reads 27.8 on the saved output. The
    simulation code was not retained, so neither figure can be re-run. (b2) stays below (a-all)'s 419.1 either way.
  - "52 of 1,211" (§3.1): 52 counts skipped `bootstrap-macos` check runs across all events, one of them a
    `workflow_dispatch` run. The pull-request figure is 51 of 1,211 (4.2%).

## 11. Review disposition

| Item | Disposition |
| --- | --- |
| D1, blocker | **Fixed.** The remedy is changed-tests mode (b2) plus T1 with its escalation. On the data: 0 of 18 deterministic failures escape (B′ alone: 5, of which 2 merged); 58.7% of PR jobs skip the full suite and 34.3% skip entirely; 0 of 142 skipped main commits touch tests (B′: 90 of 232; the critic's figure, 92 of 225 at `d2fc3803e`, is kept). |
| D2 | **Fixed.** §3.2 says the defect was latent on main from 1b0e4598f to 50bba7bb0, and that the suite passed at introduction (push run 36219928794). Option A now reads "would have stayed latent". |
| D3 | **Fixed.** C′ is described as docs/decisions/2026-09-22-github-automation-closure.md:1485-1486 prescribes it, and evaluated beside B-advisory. Required beats advisory per #219 (docs/decisions/2026-09-22-github-automation-closure.md:1434-1437) and #549. |
| D4 | **Fixed.** The set is 30. The tallies are redone over 30 and over 25 (§3.3), and the 2.4% bound is withdrawn. |
| D5 | **Fixed.** B+ is adopted in the same PR, gated on `macos != 'false'` beside `bootstrap != 'false'`. PATTERNS does not change. |
| D6 | **Fixed.** Overturn 4 is powered at 600 merged PRs (P(0) ≈ 0.04). The escape bound (now 4.7%) is labelled uninformative. |
| D7 | **Fixed.** The cancel recipe filters on job status, keeps any run with an `in_progress` job, and cancels only by recorded literal ID. |
| D8 | **Fixed.** 22 entries are added. The drift-guard grep is widened and its 6 exclusions are recorded with reasons. The list is reconciled with `test_adoption_bootstrap_macos.py:3712-3725`; `manifests/evidence.json` is the one recorded exclusion. |
| D9 | **Fixed.** §6.3 lists each expectation that changes, at :1249-1257, :1292-1300, :1259-1290, :1321, :1331, :1336, :1348 and :1352. |
| D10 | **Fixed.** A Support request is a lever. Whether it is available to a `User` account is not verified. |
| D11 | **Fixed.** `PushNetTests` pins `manifests/evidence.json`. The record states that the net is coverage by coincidence, names its gap, and adds overturn 8. |
| D12 | **Fixed.** Queue medians are given on one basis (1.2 / 0.94 / 0.68). "52 of 1,211" is corrected. REST and G are reported side by side, not as agreement. The 25-run tallies sum correctly. PR #666 closed at 18:17:17Z. The simulation is presented as direction only. |

## SOTA sources

**GitHub documentation, read 2026-10-03:**
- troubleshooting-required-status-checks (skipped jobs, skipped workflows, the `always()` with `needs` pattern). It
  now lives at
  docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks.
  The implementing PR re-read it at 2026-10-03T21:09Z: "A job is skipped by a conditional | The job reports
  'Success'", and "Use `always()` with `needs` for required checks that depend on other jobs";
- status checks reference (docs.github.com/en/pull-requests/reference/status-checks), re-read by the implementing PR at
  the same time: "A job that is skipped will report its status as 'Success'. It will not prevent a pull request from
  merging, even if it is a required check.";
- contexts reference, re-read by the implementing PR at github/docs@2bd66de8cea336061c9ea060c9b37385136e6ab3,
  `content/actions/reference/workflows-and-actions/contexts.md:97, :100, :110` (the `jobs.<job_id>.env`,
  `jobs.<job_id>.if` and `jobs.<job_id>.steps.if` rows below);
- control-jobs-with-conditions;
- contexts reference, "Context availability"
  (docs.github.com/en/actions/reference/workflows-and-actions/contexts), read 2026-10-03 at 20:55Z. The rows used:
  - `jobs.<job_id>.env`: github, needs, strategy, matrix, vars, secrets, inputs;
  - `jobs.<job_id>.if`: github, needs, vars, inputs, plus `always`, `cancelled`, `success` and `failure`;
  - `jobs.<job_id>.steps.if`: includes `env` and `needs`;
- limits (macOS concurrency, and the Support line);
- managing-a-merge-queue;
- actions-runner-pricing and larger-runners;
- secure-use (self-hosted runners);
- re-run-workflows-and-jobs;
- events-that-trigger-workflows#pull_request.

**Changed-test selection before merge:**
- pytorch/pytorch `main`, read 2026-10-03:
  - `tools/testing/target_determination/heuristics/edited_by_pr.py` (`_get_modified_tests`,
    `EditedByPR.get_prediction_confidence`);
  - `tools/testing/target_determination/heuristics/__init__.py`.
- Memon et al., "Taming Google-Scale Continuous Testing", ICSE-SEIP 2017. Pre-submit testing of affected targets,
  post-submit runs and culprit rollback.

**Change-based gating and subsets of a platform's tests on PRs.** These were cited in the previous round and not
re-read in this one:
- python/cpython @83b40d06: `.github/workflows/build.yml` and `Tools/build/compute-changes.py`;
- astral-sh/ruff @127e77ef: `ci.yaml`;
- astral-sh/uv @46b84fd0: `test.yml` and `plan.yml`;
- pytorch/pytorch @073b3e8c: `trunk.yml`;
- denoland/deno @b4f08f12: `ci.ts:253-254` and `:558-591`, re-read in this round. Those lines skip macOS release jobs
  on PRs without the `ci-full` label;
- rust-lang/rust @db8f076d: `jobs.yml` and `ci.md`;
- mozilla firefox @d0f18859: `backstop.py`.

**Papers:**
- Gallaba et al., ASE 2018;
- Uber, EuroSys 2019 §2.1;
- Jin and Servant, ICSE 2021;
- Hanley and Lippman-Hand, JAMA 1983 (the zero-numerator bound, now labelled uninformative).

**In this repository, at `6112d14d4`:**
- `.github/workflows/adoption-bootstrap.yml:9-63, :157-173, :242-247, :536-541, :595-753`;
- `.github/main-ruleset.json`;
- `docs/decisions/2026-09-22-github-automation-closure.md:1420-1528`;
- `docs/acceptance-evidence-policy.md:42-53`;
- `docs/github-automation.md:351-363`;
- `tests/test_workflow_hardening.py:60-100, :141-155, :467-487, :1235-1354`;
- `tests/test_adoption_bootstrap_macos.py:3700-3731`;
- `adoption/platforms/macos-arm64.md:865-866`;
- `docs/decisions/2026-10-02-two-host-north-star-architecture.md:36-49`;
- `git show 1b0e4598f:tools/sota-convergence/landscape-sweep/codex_job.py:370-397`;
- PR #632 @85e9bc653.
