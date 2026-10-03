# Suite shards with GitHub's parallel steps: a second preregistered trial (2026-10-03)

Lane: foundation. North-star action served: a shorter, still fail-closed required test job, so that every pull
request that moves the stack toward the north star (US-equities research and historical simulation, then
broker-specific paper readiness) reaches a verdict sooner. Status: trial preregistered before any hosted run;
nothing is adopted. This record changes no required check, ruleset, production workflow or test command.

## Decision

Trial GitHub Actions' native parallel steps for the two whole-suite jobs: run the existing unittest suite as N
concurrent single-process shards inside one job, each shard the stock `python3 -m unittest -v <modules>`, against the
serial production command, on the runners of both required jobs:

- `validate` (`.github/workflows/validate.yml`, ubuntu-24.04, 4 vCPUs, the image's system CPython 3.12; its step
  "Test validation failure modes" runs `python3 -m unittest`);
- `validate-macos` (`.github/workflows/adoption-bootstrap.yml`, macos-15, 3 cores, `actions/setup-python` 3.13; its
  full-suite step runs `python3 -m unittest -v`).

Parallel steps are generally available since 2026-06-25 (GitHub changelog, "Actions steps can now be run in
parallel"). The workflow-syntax reference (github/docs at `c67a9362`, lines 1193-1224) defines `parallel:` as a group
of background steps with an implicit wait at its end; lines 1078-1086 allow at most 10 concurrent background steps
per job and fail the job at the wait when a background step fails.

The trial belongs to a draft pull request that is never merged. It adds two workflows,
`.github/workflows/suite-shards-trial-linux.yml` and `.github/workflows/suite-shards-trial-macos.yml`, and the
oracle, generator and records in
[`blueprints/convergence-practice/suite-shards-trial-20261003/`](../../blueprints/convergence-practice/suite-shards-trial-20261003/README.md),
preregistered in its `experiment.json` (status `planned`). The only other change is the expected-workflow set of
`tests/test_workflow_security_coverage.py`. None of the trial's job names is a required context.

Why this candidate: the first trial (unittest-parallel 1.8.6, draft pull request #646, run 37109532421) failed its
rule on Linux because that runner pickles live `TestCase` instances: `IsolatedAsyncioTestCase` holds a
`contextvars.Context`, and four dynamically built classes are not importable by name; macOS was never measured.
Shards built from test files need no package and no pickling, load `load_tests` and dynamic classes as production
does, and keep each job's name, so the required contexts would not change.

## Arms

| OS | Arm | Timed phase |
|---|---|---|
| ubuntu-24.04 | S | `python3 -m unittest -v` (one step) |
| ubuntu-24.04 | G4 | 4 shard steps in one `parallel:` group covering every test file |
| ubuntu-24.04 | G4T | 4 shard steps without `tests.test_secret_path_guard`, then that module alone in a serial tail step |
| macos-15 | S | `python3 -m unittest -v` (one step) |
| macos-15 | G3 | 3 shard steps in one `parallel:` group |
| macos-15 | G3T | 3 shard steps without `tests.test_secret_path_guard`, then the serial tail |

Three repeats per arm, `fail-fast: false`. Linux holds at most two serial and two sharded jobs at once (four timed
jobs); macOS at most one of each, so with the control job no more than three of the plan's five macOS slots. The
serial and sharded arms are separate jobs so that no step inside a `parallel:` group carries an `if:`, which the
reference does not document there; macOS's limit of two timed jobs at once is therefore one serial plus one sharded
job (`max-parallel: 1` each), beside the one control job.

Shard lists are built at run time, in each workflow's inventory job, from the test files of the checked-out head by
the frozen `make_shards.py` (longest-processing-time-first over files, from the frozen `weights.json`; a file missing
from the weights takes the mean weight, so a new file can never drop out). The inventory job fails, and no arm runs,
unless loading every `tests/test_*.py` by name gives exactly the discovery ids, no id is loaded twice, nothing fails
to import, and every file is in exactly one list or the tail of each arm.

Every shard step is a plain `run:` step with no expression in its script; it runs its list with
`python3 -m unittest -v`, records the exit status and exits with it, so a failing shard fails its step, the group and
the job, as production would. Each shard step has a hang guard (`timeout-minutes` 25 on Linux, 40 on macOS).

## The preregistered rule

The full text is `experiment.json`'s `quality_rule`; `README.md` gives the same rules with their sources. In short:

- **S** is eligible with three runs, each complete, its exit status agreeing with its status line, its executed ids
  exactly the inventory, the exact command, a clean checkout, `run_attempt` 1, the pull request head and a valid step
  time; the eligible S runs share one Python version. Ids whose records differ among the S runs are flaky and are
  excluded from the comparison.
- **G and GT** runs are eligible when every shard log is complete and consistent, every command is
  `python3 -m unittest -v` plus its list, the lists are the inventory's, every log ran exactly its modules' ids, the
  union is the inventory with each id once, the `(kind, key, outcome)` records equal the first eligible S run outside
  the flaky ids, every step ran S's Python version, and the checkout, attempt, head and step-time rules hold.
- **Controls** per OS: one job runs the arms' shard step body in one `parallel:` group on a passing, a failing, a
  crashing (`os._exit(3)`) and a hanging control (stopped by a 1-minute step limit). The job must fail, the exit
  statuses must be 0, 1, 3 and none (stopped), every background step must run the foreground step's Python and see a
  variable exported through `GITHUB_ENV` by an earlier step. A second job asserts this. Whether background steps
  start with SIGINT or SIGQUIT ignored is recorded, not judged.
- **Decision**, per OS: an arm is eligible with three eligible runs and passed controls; S ineligible gives no
  verdict; no eligible sharded arm gives reject; otherwise take the eligible arm with the smaller median step time
  (a tie goes to G), and adopt only if its median is at most 3/5 of the S median and its slowest run at most 3/4 of the
  fastest S run, as exact fractions; otherwise reject, with no fall-through. A cancelled or partial run is recorded
  as incomplete, never as a rule outcome; a failed inventory gate gives no verdict.

## Lessons of the first trial applied

1. **A whole-suite local preflight before preregistering.** The coordinator ran it at `d2777ee7` (local integration
   evidence; limits below): the serial run (1,305 s, `FAILED (failures=32, skipped=1181)`, all 32 host-specific), and 4
   shards as 4 concurrent processes in 361 s unpinned and 378 s pinned to 4 cores, 3 shards pinned to 3 cores in 487 s,
   each with its 9,853 parsed records equal to the serial run's. A first attempt differed only because a shell's
   background job started the shards with SIGINT and SIGQUIT ignored, which skipped a SIGQUIT subtest.
2. **The observed record cannot land on the trial branch.** Each workflow runs only on `opened` and `reopened`, with
   a paths filter on its own file and no `synchronize`; to repeat the trial, close and reopen the pull request. A job
   re-run still voids its arm-run (`run_attempt` must be 1). "Re-run failed jobs" would also re-run the control job,
   which fails by design, and so fail the controls; only the compare job may be re-run on its own.
3. **Two independent workflows**, each with its own ubuntu-24.04 inventory job, arms, controls and compare job, so a
   stalled macOS queue never holds the Linux evidence and either run can be cancelled alone.
4. **Counts agree everywhere and the limits are stated**: n = 3; the controls are synthetic fixtures executed on the
   hosted runner; the hosted jobs run no model.
5. **Self-review for the review bot's classes of finding** before hand-over: arithmetic, retention, coverage gaps
   and design holes (the concurrency group's queued run is described in both workflows and in `README.md`).

## Alternatives considered

Each line relays only what was read at the cited source; the comparison came from a read-only Codex lane
(gpt-6.1-sol), whose claims were treated as leads and checked against these sources on 2026-10-03.

- **unittest-parallel 1.8.6 with shims**: every level sends live suites to spawned workers through `pool.map`
  (craigahobbs/unittest-parallel at `bda5d77`, `src/unittest_parallel/main.py` lines 122-128 and 150-160), and an
  `IsolatedAsyncioTestCase` keeps a `contextvars` context (CPython v3.13.16 `Lib/unittest/async_case.py` line 42); a
  shim would change what runs, so equivalence would need a new trial.
- **pytest with pytest-xdist**: pytest does not support the `load_tests` protocol (pytest 9.1.1
  `doc/en/how-to/unittest.rst` lines 33-35), which `tests/test_native_maintenance.py` uses, so the id set would change;
  each xdist worker collects the whole suite itself (pytest-xdist v3.8.0 `docs/how-it-works.rst` lines 6-30).
- **stestr 4.2.1**: each worker rediscovers the suite and filters it by an id list (mtreinish/stestr 4.2.1
  `stestr/config_file.py` lines 201-206, `stestr/subunit_runner/program.py` lines 181-190), so nothing is pickled, but
  results travel as subunit rather than the unittest verbose log both jobs keep, and it adds packages.
- **nose2 0.16.0**: its own `load_tests` plugin warns that suites using `load_tests` do not work correctly with the
  multiprocess plugin (nose-devs/nose2 0.16.0 `nose2/plugins/loader/loadtests.py` lines 9-13); workers reload tests by
  name (`nose2/plugins/mp.py` lines 345-352).
- **green 4.0.2**: concurrency is `-s/--processes` and `-j` writes JUnit (CleanCut/green 4.0.2 `green/config.py` lines
  177-178 and 426-427); its PyPI release has only an sdist (`green-4.0.2.tar.gz`, PyPI JSON for 4.0.2), which the
  repository's `--only-binary=:all:` hash-locked installs refuse.
- **concurrencytest 0.1.11**: forks children that report over subunit, and the parent keeps only the pipe and never
  waits on the child (cgoldberg/concurrencytest 0.1.11 `concurrencytest.py` lines 104-144), so a child that dies before
  reporting adds no failure.
- **One process per module under `xargs -P`**: the same loading as these shards (fresh `python3 -m unittest`
  processes, CPython `Lib/unittest/loader.py` lines 100-117 at v3.13.16), but every process shares one step: one exit
  status (GNU findutils 4.10.0 `xargs(1)`, "EXIT STATUS": 123 when any invocation exits 1 to 125), one time limit and
  one log stream. The Codex lane ranked it second, after parallel steps.
- **Matrix sharding into separate jobs**: rejected in plan W1, because legs rename the required checks and a
  `needs:`-based aggregate on `validate-macos` is forbidden by `tests/test_workflow_hardening.py`.

## Overturn conditions

- This trial's outcome per OS: **adopt** opens a separately reviewed adoption pull request for that OS (below);
  **reject**, **no verdict** or **incomplete** keeps the serial command and is recorded as a failed or partial attempt.
- GitHub changes the documented semantics or limits of `parallel:` or background steps (workflow-syntax reference),
  or the controls show that background steps do not honour `timeout-minutes`, `GITHUB_ENV` or the interpreter.
- After an adoption, a failure that appears only in sharded runs.
- A suite change that makes the inventory gate fail (a file loaded only by discovery, an id loaded twice).

## Risks

- **Signal dispositions.** Whether the hosted runner starts background steps with SIGINT or SIGQUIT ignored is not
  documented; locally, ignored dispositions skipped a SIGQUIT subtest, which would be a record mismatch. Every shard's
  probe and the control job measure it.
- **Environment of background steps.** The reference covers exports made by a background step, not whether earlier
  `GITHUB_ENV` exports and `actions/setup-python`'s `PATH` reach one; if not, the shard holding
  `tests.test_shell_parser_ci` fails its tripwire, or a macOS shard runs another Python, and the run is ineligible.
- **zizmor's experimental support for parallel steps** (zizmor 1.30.1 warns, and its `docs/usage.md` at v1.30.1 calls it
  experimental): audit coverage inside the groups is not established; the shard steps are plain `run:` steps with no
  expression in their scripts. actionlint 1.17.0 parses the groups and runs shellcheck on their scripts.
- **Runner noise.** Shared hosted runners vary (the first trial's serial runs took 1,186 to 1,688 s on one image);
  n = 3 bounds this only loosely.
- **Shard drift.** The lists change with every new test file; a file missing from the weights takes the mean weight.
  At base `9b0b8d6d` one file (`tests.test_catalog_freshness_runtime`) does, at 5.45 s against its local 0.23 s.
- **Timing-bound tests.** `tests.test_secret_path_guard.K4GuardTests.test_k4_timing` (30 to 60 s serially) failed under
  class-level parallel load in the first trial; the T arms keep its module out of the group, the G arms do not.
- **Coupling inside a shard.** Modules that share a shard share a process; the hosted lists (234 files) differ from
  the preflight's (233 files, and the small files are partitioned differently), so a coupling the preflight did not
  meet could appear. The record comparison judges it.

## Limitations

- The preflight ran on another machine (48 cores), another CPython patch release (3.13.16, against 3.12 on the Linux
  runner) and an earlier base (`d2777ee7`); it is local integration evidence, not a hosted run.
- n = 3 per arm. Hosted macOS has never run this suite in shards, and the first trial never ran on macOS at all.
- The local oracle dry run used the coordinator's real logs with synthetic metadata and `--skip-list-recompute`.
- The macOS inventory is built on ubuntu-24.04 with the arms' Python line; a platform-dependent id gives no verdict.
- Skip reasons are not compared; side effects that leave outcomes unchanged are invisible to the oracle.

## Usage rule and evidence classes

No usage claim. The hosted jobs run deterministic commands and no model; the model usage of the sessions that built
this trial is not recorded and stays unknown. Evidence classes so far: local integration (the coordinator's preflight,
the inventory gate at the base, the oracle's dry run on real logs, the oracle's 62 tests on CPython 3.13.16 and 3.12.3),
synthetic fixtures (real local runs of a fixture suite and of the controls) and source review (the GitHub
documentation, CPython and the alternatives at their pins). Nothing here is native execution on a hosted runner or
upstream acceptance; the controls, once run, are synthetic fixtures executed on the hosted runner.

## After the run

The observed record goes to a separate records pull request; the trial branch is not pushed to after its first push.
That pull request carries an outcome record under `docs/decisions/`, a receipt under `evidence/receipts/` and sanitized
artifacts (the compare artifact's `result.json`, `summary.md` and `checkout-status.json`, a byte copy of this
preregistration, sanitized log excerpts), because the run's artifacts expire after 30 days and its records under the
repository's 90-day retention.

A passing result would lead, for each adopting OS, to an adoption pull request that also builds the shard lists at
run time inside the production job, updates `tests/test_workflow_hardening.py` for sharded whole-suite jobs (the
whole-suite classification, the full-history rule and the `validate.yml:validate` assertion) and adds a shard-coverage
guard test (every test file in exactly one shard). None of that is done here.

## SOTA sources

- github/docs at `c67a9362ec63f3993d095bf70bd11724359cc50e`,
  `content/actions/reference/workflows-and-actions/workflow-syntax.md` lines 1070-1074 (step `timeout-minutes`),
  1078-1086 (`background`), 1107-1168 (`wait`, `wait-all`) and 1193-1224 (`parallel`); at
  `63859c481b2195607ff94c4dda765fb131a34759`, `events-that-trigger-workflows.md` lines 465, 473 and 484-489; at
  `03d2e24b34bd88c361f1185f0aae1c46062c6510`, `contexts.md` lines 209 (`github.run_attempt`), 384 (`job.status`) and 779
  (`needs.<job_id>.result`). GitHub changelog of 2026-06-25:
  https://github.blog/changelog/2026-06-25-actions-steps-can-now-be-run-in-parallel/
- actions/download-artifact at `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`, `src/download-artifact.ts` lines 85-95, 149-163
  and 176-246 (a pattern that matches nothing downloads nothing; a missing name fails).
- python/cpython at v3.13.16 (`cbc944f4bc59639a444dd971c737788ba2283a91`): `Lib/unittest/main.py` lines 144-153 and
  231-234, `Lib/unittest/loader.py` lines 100-117, `Lib/unittest/async_case.py` line 42, `Python/pytime.c` lines 1164-1170
  and 1202-1203; at v3.12.3 (`f6650f9ad73359051f3e558c2431a109bc016664`): `Lib/unittest/main.py` lines 155-164 and
  242-245, `Lib/unittest/loader.py` lines 97-113, `Python/pytime.c` lines 1105-1111 and 1145-1146.
- The first trial's oracle, whose parser `logparse.py` copies unchanged:
  `blueprints/convergence-practice/macos-suite-parallelism-20261003/compare.py` at
  `1e4bb5ab7c79faa83e4cd8d04cf8dc6d33c7b0de` (lines 41-74 and 137-792).
- The alternatives at the pins and lines cited above: craigahobbs/unittest-parallel `bda5d77`, pytest 9.1.1,
  pytest-xdist v3.8.0, mtreinish/stestr 4.2.1, nose-devs/nose2 0.16.0, CleanCut/green 4.0.2 (and its PyPI JSON),
  cgoldberg/concurrencytest 0.1.11, GNU findutils 4.10.0 `xargs(1)`.
- zizmor 1.30.1 (`docs/usage.md` at v1.30.1, "Parallel steps"); kjanat/actionlint 1.17.0 (validate.yml lines 71-96).
- In-repository: `docs/acceptance-evidence-policy.md` and `docs/lanes.md` (hot-file protocol). Not in this
  repository: plan W1 of 2026-10-03 (a coordinator's approved plan) and the first trial's outcome record
  (`docs/decisions/2026-10-03-suite-parallelism-trial-outcome.md`, on an unmerged branch when this record was written).
