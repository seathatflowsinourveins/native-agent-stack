# Suite parallelism for the two required test jobs: a preregistered trial (2026-10-03)

Lane: foundation. North-star action served: a reliable, fast landing path for every unit that moves the stack toward
the north star (US-equities research and historical simulation, then broker-specific paper readiness). Each unit lands
as a squash-merged pull request behind the required checks, and the two whole-suite checks set its time to green.
Status: trial preregistered, nothing adopted. This record changes no required check, ruleset, production workflow or
test command.

## Decision

Trial [craigahobbs/unittest-parallel](https://github.com/craigahobbs/unittest-parallel) 1.8.6 (release commit
`bda5d77dc1a2fa2df90f5f5a7de297ea375e345c`, MIT; its only hard dependency is `coverage` 7.16.2) against the serial
whole-suite command, on the actual runners of both required jobs:

- `validate-macos` (`.github/workflows/adoption-bootstrap.yml`, macos-15). Its full-suite step took a median 1,842 s and
  the job 2,270 s.
- `validate` (`.github/workflows/validate.yml`, ubuntu-24.04). The job took 1,727 to 1,828 s against its 2,400 s limit.

These figures come from plan W1's samples of 2026-10-02/03 and are not re-measured here. The trial is preregistered in
[`blueprints/convergence-practice/macos-suite-parallelism-20261003/experiment.json`](../../blueprints/convergence-practice/macos-suite-parallelism-20261003/experiment.json),
status `planned`, committed before any hosted run.

**The B1 fix, the oracle and the trial workflow are for a draft pull request (PR-T) that is never merged.** Nothing in
PR-T reaches `main` through it:

- **B1 fix** (`tests/test_native_maintenance.py`). The wrapper loaded six TestCase classes from three blueprint files
  under bare module names inside `load_tests`, so a spawned worker could not pickle them. The fix loads them when the
  wrapper is imported, as child modules registered in `sys.modules`. The 29 tests and their outcomes are unchanged; the
  six classes' ids gain the prefix `tests.test_native_maintenance.`.
- **Oracle** (`blueprints/convergence-practice/macos-suite-parallelism-20261003/`). `ids.py` lists the test ids from
  discovery only. `compare.py` parses every run's log and applies the preregistered eligibility and speed rules. The
  directory also holds a control file, a crash control, their expectations, fixtures from real local runs of the
  controls, and `test_compare.py`. `blueprints/` is not a package, so production discovery never collects any of it.
- **Trial workflow** (`.github/workflows/macos-suite-parallel-trial.yml`). It triggers only on pull requests that change
  the workflow file itself. Its two hash-locked runner locks are `.github/requirements-ci-suite-macos.txt` and
  `.github/requirements-ci-suite-linux.txt`, both added to `.github/osv-scanner-lockfiles.json`, and the workflow is
  added to the expected set in `tests/test_workflow_security_coverage.py`. None of its jobs is a required context.

Integrating the three units aligned the workflow with the oracle's run contract:

- the compare job passes `--expected-sha` with the pull request head;
- it runs `test_compare.py` on its own interpreter first, fail-closed;
- it requires a clean checkout after every run (`checkout-status.json`), because `compare.py` never reads
  `git-status.txt`;
- the inventory job installs the lock before collecting ids.

### What PR-A and PR-A2 change if the trial passes

Each adoption is its own pull request, under an observed record that meets the rule below for its runner, and lands
through the required checks.

**PR-A, macOS (`validate-macos`):**

1. Delete the duplicate 124 s step "Gate on the adoption test modules" (`adoption-bootstrap.yml:725-731`). Its seven
   modules run again in the full suite.
2. Install the macOS lock with `--only-binary=:all: --require-hashes` right before the suite step.
3. Replace `python3 -m unittest -v` (`:740`) with the adopted arm's command, keeping the `full-suite-macos.log`
   redirect, the exit propagation and the artifact name, and give the suite step its own `timeout-minutes`.
4. Make the B2 edits to `tests/test_workflow_hardening.py`. The suite-run regex (`:804`, `python3? -m unittest\b`) and
   `runs_whole_suite` (`:814`) must also recognize `unittest_parallel`, and `adoption-bootstrap.yml:validate-macos`
   joins the assertIn list (`:847-848`).
5. Carry the B1 fix and re-pin `tests/test_native_maintenance.py` in `manifests/evidence.json` through the hot-file
   protocol.
6. Decide the environment difference. The trial's macOS arms install the two npm pins (tree-sitter-bash, yaml) that
   `validate.yml` installs, because their tripwires fail in any job that is not a recorded gap. `validate-macos` is a
   recorded gap (`tests/test_shell_parser_ci.py`, `KNOWN_UNPROVISIONED`), so those tests skip in production. PR-A either
   adds the pins and removes the gap, or records that the adopted arm was measured with those tests running.
7. Add the observed record and update this record.

**PR-A2, Linux (`validate`):**

1. Replace `python3 -m unittest` (`validate.yml:218-219`) with the adopted Linux arm's command as measured, with `-v`.
2. Install the Linux lock, either through the hash-locked `.github/requirements-ci.txt` that the job already installs at
   `validate.yml:55-60` or as a second lock.
3. Give the step a timeout.
4. Apply the B2 regex change (`validate.yml:validate` is already in the assertIn list).

The macOS verdict decides PR-A and the Linux verdict decides PR-A2, independently.

## Preregistered checks

The record holds the full text; in short:

- **Corpus.** The whole suite at PR-T's head SHA, which every job asserts (a `pull_request` checkout is otherwise the
  merge commit), on actual GitHub-hosted macos-15 and ubuntu-24.04 runners. The trial lock is installed in every arm.
- **Arms.**
  - S: `python3 -m unittest -v --durations 25`, the production command plus `-v` and the plan's duration diagnostic.
  - macos-15: P3 (`-j 3 --level module`), P3F (P3 plus `--disable-process-pooling`), P3C (`-j 3 --level class`), P4
    (`-j 4 --level module`).
  - ubuntu-24.04: L4 (`-j 4 --level module`), L4F (L4 plus `--disable-process-pooling`), L4C (`-j 4 --level class`).
  - Three repeats each, with `fail-fast: false` and the repeat order rotated by one arm.
- **Controls**, in separate jobs for every arm, S included:
  - A control file with a pass, a skip, a failure, an error, a failing subtest, an expected failure, an unexpected
    success, a multi-line docstring and a `setUpClass` error, which every arm must report exactly.
  - A crash control (`os._exit(3)`) under a 300 s bound, which must exit non-zero with no `OK` summary.
- **Oracle**, in two parts:
  - Part 1 is `compare.py`'s rules. An arm-run is ineligible for any malformed input, a wrong command, SHA or
    interpreter, a log that is truncated or not self-consistent, a wrong header or worker count, an id set other than
    the trial inventory, or any `(test id, outcome)` record that differs from S outside the ids that flake among the S
    repeats.
  - Part 2 is the workflow's clean-checkout check.
  - The id mapping must hold as a bijection that changes only the six B1 classes.
- **Metrics.** The selection metric is the test step's seconds (`step_seconds`). The Actions jobs API's step and job
  timestamps are kept beside it and are not used by the rule.
- **Decision rule.**
  1. An arm is eligible only with at least three runs, zero oracle mismatches in every run, and passing controls.
  2. Adopt the fastest eligible arm by median only if its median is at most 0.60 times S's median and its maximum is at
     most 0.75 times S's fastest run.
  3. Prefer P3F over P3 (L4F over L4) if its median is within 10%.
  4. Otherwise reject, with no fall-through to a slower arm, and keep the record as a failed attempt.

### Handoff for PR-T

- Push the branch once and open PR-T as a **draft** that is never merged. Label it `lane:foundation` and fill in the
  template's `### SOTA sources` section from the list below. Every push re-runs the whole trial (15 macOS and 12 Linux
  arm jobs plus controls): for pull requests the paths filter compares the three-dot diff against the merge base,
  which always contains the new workflow.
- Do not rebase or merge `main` into PR-T unless you must. The inventory maps base `56473e4b` onto the head, so a head
  carrying newer `main` commits fails the id mapping and gets no verdict.
- GitHub runs no `pull_request` workflow on a pull request with a merge conflict. PR-T can conflict in
  `manifests/evidence.json`, and with open #615, which also edits `.github/osv-scanner-lockfiles.json`. If a merge is
  unavoidable, follow the hot-file protocol (`docs/lanes.md`), set `TRIAL_BASE_SHA` to the new merge base and refreeze
  `experiment.json` in the same commit.
- Before every push, run `python3 scripts/validate.py` and
  `python3 scripts/validate_convergence.py --all-recorded --root . --json`. The workflow, the locks, the controls, the
  oracle and the B1 fix are frozen inputs of the record.
- After the compare job, write the observed record from `result.json`, `checkout-status.json` and sanitized logs. Logs
  carry runner home paths, which `scripts/validate.py` rejects. Keep durable receipts in the repository, because
  artifacts expire after 30 days.
- Stopgap while the trial runs: if `validate` nears its 2,400 s limit, raise its `timeout-minutes` first, as on
  2026-09-26 and 2026-09-29.

## Alternatives

- **pytest-xdist.** Rejected. pytest does not support the `load_tests` protocol (its docs at 9.1.1, "How to use
  unittest-based tests with pytest"; `src/_pytest/unittest.py` never mentions it), so the six `load_tests` classes would
  drop out and the id set would change. pytest-xdist 3.8.0 also needs 7 hash-locked packages (pytest-xdist, execnet,
  pytest, iniconfig, packaging, pluggy, pygments) against 2. pytest-split and pytest-testmon share the `load_tests`
  gap, and testmon selects tests rather than running the same ones faster.
- **Matrix sharding.** Rejected. Legs rename the required check (`docs/github-automation.md:26-28`), an aggregate job
  would need `needs:`, which `tests/test_workflow_hardening.py:1248-1254` forbids on `validate-macos`, and plan W1
  records a limit of 5 concurrent macOS jobs on the account's Pro plan.
- **GitHub background steps.** Kept as an optional later arm, not a lead choice. The workflow-syntax reference documents
  them: `jobs.<job_id>.steps[*].background`, `wait`, `wait-all`, `cancel` and `parallel`, with at most 10 background
  steps per job and a background failure surfacing at the next `wait` (github/docs `c67a9362`, read on 2026-10-03). That
  corrects plan W1's note that the page did not show them. They would overlap the validators (about 80 s) with the
  suite, but both contend for the same 3 macOS cores, so they cannot shorten the suite step itself.
- **Raise the timeouts only.** A stopgap, not a speed-up: time to green stays at about 30 to 38 minutes.

## Overturn

Revisit this record when any of these happens:
- the trial's verdict for either runner;
- after an adoption, a failure that appears only in the parallel run;
- unittest-parallel is archived, or an advisory is published against it or `coverage`;
- a new unittest-parallel release changes the header, the exit status or the pool behaviour this oracle reads;
- GitHub background steps are verified and measured faster on the same oracle.

## Evidence class

- **Primary-source reads** on 2026-10-03, all read-only GETs:
  - PyPI JSON for both wheels: hashes, latest versions, not yanked.
  - unittest-parallel at `bda5d77`: `main.py` and the README.
  - CPython at the v3.13.16 commit `cbc944f4` and v3.12.3 `f6650f9a`.
  - The github/docs pages at the commits below.
  - pytest's docs at 9.1.1.
  - The open pull requests' file lists.
- **Local integration checks**, not upstream acceptance:
  - U1's spawned-worker pickling check (29 tests, before and after the fix).
  - U2's control fixtures from real local runs (WSL2, CPython 3.13.16).
  - From the integration, on CPython 3.13.16 and a uv-managed 3.12.3:
    - `test_compare.py`: 28 tests OK on both.
    - `ids.py`: 9,800 ids, the same with or without the lock and from `tests/` or the root.
    - The base-to-trial mapping: 29 ids, 6 classes, ok.
    - All eight Linux control runs pass `compare.py`'s checks under 3.12.3, with a 30 s crash bound.
  - actionlint, offline zizmor and the workflow hardening tests on the edited workflow.
- **No GitHub-hosted run** exists for this record. The hosted runs will be `native_cli_execution` evidence on
  GitHub-hosted runners.

## SOTA sources

- unittest-parallel 1.8.6 at `bda5d77dc1a2fa2df90f5f5a7de297ea375e345c`:
  [`src/unittest_parallel/main.py`](https://github.com/craigahobbs/unittest-parallel/blob/bda5d77dc1a2fa2df90f5f5a7de297ea375e345c/src/unittest_parallel/main.py)
  and the [README](https://github.com/craigahobbs/unittest-parallel/blob/bda5d77dc1a2fa2df90f5f5a7de297ea375e345c/README.md),
  sections "Parallelism Level" and "Process and Thread Pools";
  [PyPI 1.8.6](https://pypi.org/project/unittest-parallel/1.8.6/) and
  [coverage 7.16.2](https://pypi.org/project/coverage/7.16.2/).
- CPython 3.13.16 (commit `cbc944f4bc59639a444dd971c737788ba2283a91`):
  [`Lib/unittest/loader.py`](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/unittest/loader.py),
  [`runner.py`](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/unittest/runner.py),
  [`result.py`](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/unittest/result.py)
  and [`Lib/pickle.py`](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/pickle.py);
  CPython 3.12.3 [`Lib/unittest`](https://github.com/python/cpython/tree/f6650f9ad73359051f3e558c2431a109bc016664/Lib/unittest).
- GitHub docs:
  [workflow syntax](https://github.com/github/docs/blob/c67a9362ec63f3993d095bf70bd11724359cc50e/content/actions/reference/workflows-and-actions/workflow-syntax.md)
  (paths filters, `strategy.max-parallel`, step `timeout-minutes`) with its
  [three-dot diff rule](https://github.com/github/docs/blob/068546469ae7f079368d12f969991a045121c4a0/data/reusables/actions/workflows/triggering-a-workflow-paths5.md),
  [contexts](https://github.com/github/docs/blob/03d2e24b34bd88c361f1185f0aae1c46062c6510/content/actions/reference/workflows-and-actions/contexts.md),
  [events that trigger workflows](https://github.com/github/docs/blob/63859c481b2195607ff94c4dda765fb131a34759/content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md)
  (`pull_request` `GITHUB_SHA`, merge conflicts) and the
  [workflow jobs REST API](https://github.com/github/docs/blob/3c82d55225dacd8085eff49ad51ab7a928dc9c59/content/rest/actions/workflow-jobs.md).
- pytest 9.1.1 (commit `cf470ec0bf7eb89cd97dd56df4859eae5db46447`):
  [`doc/en/how-to/unittest.rst`](https://github.com/pytest-dev/pytest/blob/cf470ec0bf7eb89cd97dd56df4859eae5db46447/doc/en/how-to/unittest.rst).
- In-repository records: `docs/lanes.md` (hot-file protocol), `docs/acceptance-evidence-policy.md`,
  `docs/github-automation.md`, `docs/decisions/2026-10-02-github-automation-practice.md`.
