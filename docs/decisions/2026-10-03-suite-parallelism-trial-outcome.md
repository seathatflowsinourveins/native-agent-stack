# unittest-parallel 1.8.6 is not adopted: the preregistered suite-parallelism trial failed (2026-10-03)

Lane: foundation. North-star action served: a reliable, fast landing path (shorter required test jobs) for every unit
that moves the stack toward US-equities research and paper readiness. Status: decided. Nothing is adopted, the
adoption pull requests for `validate-macos` (PR-A) and `validate` (PR-A2) are not opened, and draft pull request #646,
which holds the trial, is to be closed unmerged by the coordinator after this record's pull request opens. This record
changes no workflow, test, ruleset, required check or repository setting.

The measurements are kept in
[`evidence/receipts/suite-parallelism-trial-20261003.json`](../../evidence/receipts/suite-parallelism-trial-20261003.json),
with sanitized excerpts and a trimmed oracle output in
[`evidence/artifacts/suite-parallelism-trial-20261003/`](../../evidence/artifacts/suite-parallelism-trial-20261003/README.md),
because GitHub's run records expire under the repository's 90-day retention and the run's 18 artifacts on 2026-11-02.

## Decision

- **Do not adopt unittest-parallel 1.8.6 on this suite as it stands.** The preregistered rule gave ubuntu-24.04 the
  outcome reject (no parallel arm is eligible) and macos-15 no verdict (no run directory). Both required test jobs keep
  their serial commands (`python3 -m unittest` in `validate`, `python3 -m unittest -v` in `validate-macos`).
- **Keep the failed attempt** as this record, the receipt and the artifacts (AGENTS.md:18;
  `docs/acceptance-evidence-policy.md:60-61`).
- **Next action, separate and small:** raise the Linux `validate` job's limit (`timeout-minutes: 40`,
  `.github/workflows/validate.yml:31`, 2,400 s) in its own pull request. The trial's serial jobs on the same runner took
  1,212 to 1,724 s here, and the production `validate` job took up to 1,828 s in the CI measurements of 2026-10-03
  (pull request #632). This record makes no such change.
- **Hand-offs** for the next-trial preconditions below go to the owners of the named tests through Lane B. This
  pull request changes no test.

## What was tried

The trial was preregistered in draft pull request #646 before any hosted run: the head
`1e4bb5ab7c79faa83e4cd8d04cf8dc6d33c7b0de` was committed at 08:20:29Z and the run was created at 08:23:23Z on
2026-10-03. Its records at that head are
[`experiment.json`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/1e4bb5ab7c79faa83e4cd8d04cf8dc6d33c7b0de/blueprints/convergence-practice/macos-suite-parallelism-20261003/experiment.json)
(status `planned`, sha256 `305fc2fa2ddd2c0a0eba4d85d748807db87302bde59a6b6489de866bee416c08`; a byte copy is in the
artifacts as `preregistration-experiment.json.txt`) and
[`docs/decisions/2026-10-03-macos-suite-parallelism-trial.md`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/1e4bb5ab7c79faa83e4cd8d04cf8dc6d33c7b0de/docs/decisions/2026-10-03-macos-suite-parallelism-trial.md)
(sha256 `dda340f8e62a3f1e2dcf450336eee5ae7cce24ffef0bd0fd40a1768bb7a4c992`).

- **Arms**, three repeats each, on GitHub-hosted runners at the pull request's head: on ubuntu-24.04, S
  (`python3 -m unittest -v --durations 25`), L4 (`python3 -m unittest_parallel -j 4 --level module -v`), L4F (L4 plus
  `--disable-process-pooling`) and L4C (`-j 4 --level class`); on macos-15, S, P3, P3F, P3C and P4. unittest-parallel
  1.8.6 and coverage 7.16.2 were installed from hash locks in every arm.
- **Controls** in separate jobs: an injected file with a pass, a skip, a failure, an error, a failing subtest, an
  expected failure, an unexpected success, a multi-line description and a failing `setUpClass`, and a crash control
  (`os._exit(3)`) under `timeout --kill-after=30 300`.
- **Oracle** (`compare.py`, frozen at the head): a run is eligible only with zero mismatches against the first eligible S
  run (the exact (test id, outcome) records, the exact command, `run_attempt` 1, a clean checkout); an arm is eligible
  only with three eligible runs and passing controls. **Rule:** adopt the fastest eligible arm only if its median is at
  most 0.60 of S's median and its slowest run at most 0.75 of S's fastest, as exact fractions; otherwise reject; prefer
  L4F over L4 within 1.10 of L4's median.

## What happened

Run 37109532421 (attempt 1, event `pull_request`) ran all 18 ubuntu-24.04 jobs on runner image 20260927.320.1 with
CPython 3.12.3, 4 CPUs and X64. Every timed run checked out the head, and the jobs API's test-step seconds equal each
run's own `step_seconds`.

| Arm | Test-step seconds (r1, r2, r3) | Median | Job seconds | Exit codes | Result records per run | Eligible runs |
| --- | --- | --- | --- | --- | --- | --- |
| S | 1,688, 1,659, 1,186 | 1,659 | 1,724, 1,705, 1,212 | 0, 0, 0 | 9,823 (`Ran 9823 tests`, `OK (skipped=967)`) | 3 of 3 |
| L4 | 649, 438, 459 | 459 | 685, 466, 491 | 1, 1, 1 | 9,624, no `Ran` line | 0 of 3 |
| L4F | 539, 692, 710 | 692 | 574, 725, 744 | 1, 1, 1 | 9,624, no `Ran` line | 0 of 3 |
| L4C | 667, 659, 704 | 667 | 698, 688, 733 | 1, 1, 1 | 9,741, no `Ran` line | 0 of 3 |

- **Every parallel run crashed at the end.** All nine end with `TypeError: cannot pickle '_contextvars.Context' object`,
  raised from `results = pool.map(test_fn, test_suites, chunksize=1)` (`unittest_parallel/main.py` line 160 at the
  release commit) through `multiprocessing` reduction. None printed a `Ran N tests` line or an error report.
- **The oracle** marked all nine runs ineligible (no `Ran` line; ids that never ran; ids that differ from S) and gave
  ubuntu-24.04 the outcome **reject**. macos-15 got **no verdict** (no run directory). The id mapping was ok (29 ids, 6
  classes, the single prefix `tests.test_native_maintenance.`), every run directory's checkout was clean, and every
  control and crash control passed: the controls file reported `Ran 8` and
  `FAILED (failures=2, errors=2, skipped=1, expected failures=1, unexpected successes=1)` with exit 1 under S and exit 5
  under unittest-parallel (2 + 2 + 1, `main.py:240-242`); the crash control exited 3 under S and hung every parallel arm
  until the 300 s bound (exit 124), which the preregistration counts as fail-closed.
- **Ids that never ran** were the same in every run of a level, all in three modules:

| Module | Module level (L4, L4F; each of 6 runs) | Class level (L4C; each of 3 runs) |
| --- | --- | --- |
| `tests/test_adaptive_paper_fees.py` | 61: AdaptiveLaneFees 9, FeeCheckpoint 3, FeeHTTPBoundary 2, FeeLedger 16, FeeNormalization 6, FeeReconciliation 6, FeeSnapshot 7, MoverFeeHelpers 3, MoverLaneFees 9 | 7: FeeSnapshot |
| `tests/test_adaptive_paper_transport.py` | 116: AsyncTransport 59, ConfiguredQuoteFeed 5, DataFeedSelection 5, HTTPBoundary 12, HaltFeedSeed 8, LeverageNormalizeAccountTests 4, Normalization 9, OrderContractBoundary 6, TradingStatusParsing 8 | 59: AsyncTransport |
| `tests/test_adoption_version_probes.py` | 22: DeclaredProbeTests 3, LinuxReportUnderbash32Tests 4, LinuxReportUnderbashTests 4, MacosReportUnderbash32Tests 4, MacosReportUnderbashTests 4, ReportStructureTests 3 | 16: LinuxReportUnderbash32Tests, LinuxReportUnderbashTests, MacosReportUnderbash32Tests and MacosReportUnderbashTests, 4 each |
| Total | 199 | 82 |

- **Other differences from S**, beyond the ids that never ran:
  - L4 (module level, pooled): none in 3 of 3 runs. Every test that ran matched its serial outcome, including
    `tests.test_secret_path_guard.K4GuardTests.test_k4_timing`.
  - L4C: `tests.test_secret_path_guard.K4GuardTests.test_k4_timing` failed in 3 of 3 runs, on a different set of
    subtests each time (r1 `helper='k4_needs_walk'`; r2 `row='T-STORE-STAGES'`; r3 `row='T-STORE-STAGES'`,
    `helper='k4_runner_environment'` and `helper='k4_runner_start'`). It passed in all 3 S runs and all 6 module-level
    runs. It is a timing-bound test and the slowest test of every serial run (48.9, 60.0 and 30.7 s), and the
    preregistration lists it among this repository's macOS-only CI failures of 2026-10-01.
  - L4F: `tests.test_order_throughput.CapacityRunTests.test_cli_refuses_live_base_url_from_env_file_without_network`
    errored in 3 of 3 runs. It was ok in every S, L4 and L4C run, and the module alone passes locally (`Ran 76 tests`,
    `OK (skipped=1)`) both serially and unpooled under unittest-parallel on CPython 3.12.3 and 3.13.16. **Its cause is
    not known.** The traceback is not in the log, because unittest-parallel prints its error report only after
    `pool.map` returns (`main.py:164-211`) and the run crashed first.
- **Speed, measured but not an adoption claim.** L4's median was 459 s against S's median of 1,659 s (153/553, 0.277),
  and its slowest run 649 s against S's fastest of 1,186 s (649/1186, 0.547). L4F (0.417 and 0.599) and L4C (0.402 and
  0.594) were also inside the rule's speed bounds. No arm was eligible, so the rule never reached speed. These seconds
  cover 9,624 or 9,741 of 9,823 tests and end in a crash, and the serial run itself varied from 1,186 to 1,688 s on the
  same runner type and image. The `--durations 25` tables of the S runs show no dominant test: the slowest is 2.6% to
  3.6% of a run and the 25 slowest together 22.8% to 24.6%.

### The cancellation

The coordinator cancelled the run at 09:12:40Z. This was the coordinator's decision, not part of the preregistered
rule, which has no early stop. By then every ubuntu-24.04 job had succeeded; the last arm job, `arms-linux (3, S)`,
finished at 09:12:25Z. None of the 20 macos-15 jobs (15 arm jobs and 5 control jobs) had received a runner in the
49 minutes since they were created at 08:23:23-24Z; each reports zero steps. The `compare` job (`if: always()`) still
ran from 09:12:42Z to 09:13:11Z and uploaded the official result. The decision is justified on three grounds:

- **The failure is deterministic**: one exception, at the same line, in 9 of 9 parallel runs, with identical sets of ids
  that never ran in every run of a level.
- **It does not depend on the platform**: every `IsolatedAsyncioTestCase` instance stores a `contextvars.Context` on
  CPython 3.12.3 and on 3.13.16, the macOS arms' Python line, and pickling finds a class by its qualified name on every
  platform. The local reproductions fail the same way on both versions. Every macOS parallel arm would have hit the same
  three modules, so macOS could only end in reject or no verdict (an inference from these facts, not a macOS run).
- **The shared macOS pool was held up**: from 08:23 to 09:12, five of this repository's macOS jobs (from Adoption
  bootstrap smoke runs, which carry the required `validate-macos` check) held runners in 46 of 50 sampled minutes, and
  never more than five. Had they started, the 20 trial jobs would have held those runners while other pull requests'
  required checks waited, for an outcome already fixed on macOS. Other repositories that share the account's macOS
  concurrency were not read.

No macOS job started, so no macOS attempt was voided or hidden, and macOS keeps the outcome no verdict.

## Root causes

Both are reproduced locally (the receipt's `local_reproductions` and the artifact `local-reproductions.txt`). The
three modules are byte-identical at the trial head and at this record's base.

- **(a) `unittest.IsolatedAsyncioTestCase` cannot be sent to a worker.** Its `__init__` stores
  `self._asyncioTestContext = contextvars.copy_context()` (CPython `Lib/unittest/async_case.py` line 38 at v3.12.3,
  line 42 at v3.13.16), and unittest-parallel pickles the suites of live test instances for its spawned workers. Two
  suite modules use the class: `FeeSnapshot(FeePrivacyCapture, unittest.IsolatedAsyncioTestCase)` at
  `tests/test_adaptive_paper_fees.py:295` (7 tests) and `AsyncTransport(unittest.IsolatedAsyncioTestCase)` at
  `tests/test_adaptive_paper_transport.py:478` (59 tests); no other test file at the trial head does. At module level each whole
  module's suite fails to be sent (61 and 116 ids); at class level only those two classes do (7 and 59). Locally, a toy
  module with one plain class and one `IsolatedAsyncioTestCase` class fails at module level and runs only its plain
  class at class level, and a plain-only module passes, on CPython 3.12.3 and 3.13.16; the two real modules fail the
  same way on 3.12.3.
- **(b) Four dynamically built classes are not importable under their qualified names.**
  `tests/test_adoption_version_probes.py:431-437` defines `behavior_case(platform_id, shell, label)`, which returns
  `unittest.skipUnless(shell, reason)(type(f"{platform_id.capitalize()}ReportUnder{label.replace(' ', '').replace('.', '')}Tests", (ReportBehaviorMixin, unittest.TestCase), {...}))`,
  and lines 440-443 bind the results as `LinuxReportUnderBashTests`, `MacosReportUnderBashTests`,
  `LinuxReportUnderBash32Tests` and `MacosReportUnderBash32Tests`. `type()` names the classes from the label, with a
  lower-case "bash" (`LinuxReportUnderbash32Tests` and so on), and the module has no attribute of that name. CPython's
  pickler looks a class up by its `__qualname__` in its module (`Modules/_pickle.c` lines 3664 and 3697 at v3.12.3), so
  locally the run stops with
  `_pickle.PicklingError: Can't pickle <class 'tests.test_adoption_version_probes.LinuxReportUnderbash32Tests'>: attribute lookup LinuxReportUnderbash32Tests on tests.test_adoption_version_probes failed`
  (lines 3700-3702). This is the same class of defect as the B1 wrapper that the trial branch fixed: classes that a
  worker cannot find under the name pickle looks up.
- **Why the runs went to the end and show one exception.** CPython's pool pickles each task in its task-handler thread
  (`Lib/multiprocessing/pool.py:540`), records a failure against the map (`:544`), keeps only the first exception
  (`:822`) and marks the map ready only once all jobs are done (`:826`). Every other suite therefore ran, and `get()`
  then raised the first exception (`:774`), the `TypeError`. The `PicklingError` of (b) never appears in the hosted logs;
  its hosted effect is inferred from the ids that never ran (exactly those four classes at class level). Every other
  module's suite was sent and ran, so at this head, on Linux, these three modules are the only ones that cannot be
  sent.

Upstream: [issue 27](https://github.com/craigahobbs/unittest-parallel/issues/27) reports the same `TypeError` for a
project that mixed in asyncio tests. Its reporter closed it six minutes later, saying they had probably mixed in
asyncio unit tests that the report did not show; it has no maintainer comment. The README at the release commit does not mention asyncio, `contextvars`,
pickling or spawned processes, and the default branch is two commits ahead of the release, both changing only
`AGENTS.md`. PyPI listed 1.8.6 as the latest release on 2026-10-03.

## What this attempt does not show

- Anything about macOS: no macOS job ran.
- Whether a suite fixed under precondition (i) would meet the rule: the parallel seconds cover 9,624 or 9,741 of 9,823
  tests and end in a crash, and the serial seconds of the missing tests are not measured.
- The cause of the L4F error.
- Whether the class-level K4 timing failures come from CPU load alone.
- Anything about the alternatives listed below.

## Departures from the preregistration

- **The cancellation**, described above.
- **Where the observed record lives.** The preregistration's `next_decision_changing_test` asked for an observed
  convergence record (one `native_cli_execution` observation per timed run) beside `experiment.json`. That directory
  exists only on the trial branch, which is never merged, and its workflow re-runs the whole trial on every push to that
  branch and in any pull request that adds it. The same per-run data is therefore in the receipt, and this pull
  request contains no workflow.

## Alternatives

Not evaluated by this trial. They are listed for a pending survey in a separate lane, and nothing is asserted about
them here: pytest-xdist, stestr, nose2's multiprocess plugin, green, one process per module under `xargs -P`, and
GitHub's parallel steps. unittest-parallel's own `--thread` mode (`main.py:62-63` at the release commit) was not part
of this trial either.

## Overturn conditions and next-trial preconditions

Revisit this decision when a new trial, preregistered anew, meets the rule on an OS, or when unittest-parallel
publishes a release or a documented mode that sends `IsolatedAsyncioTestCase` suites to its workers (to be verified
locally first). A new trial needs, in this order:

1. **Picklable suites in the three modules**: `FeeSnapshot` and `AsyncTransport` (both `IsolatedAsyncioTestCase`)
   and the four classes built by `behavior_case`. `tests/test_adaptive_*.py` are trading-lane tests
   (`docs/lanes.md:48`); `tests/test_adoption_version_probes.py` is a foundation test. Hand-off through Lane B.
2. **The K4 timing test under CPU contention** (`tests/test_secret_path_guard.py`, its owner), because it failed in
   every class-level run.
3. **A diagnostic hosted run that prints the traceback of the L4F error** in
   `tests.test_order_throughput.CapacityRunTests` (a trading-lane test, `docs/lanes.md:51`).
4. **A whole-suite local preflight under the candidate runner before preregistering** (the anti-pattern row of
   2026-10-03 in `docs/harness-defaults.md`). The preregistration recorded that this preflight had not run and that no
   whole-suite parallel run had happened anywhere.

## Evidence class

- **Native execution on GitHub-hosted ubuntu-24.04, receipt retained** (template class `native_proven`): the per-run
  exit codes, test-step seconds, result records, ids that never ran, other differences, controls and the oracle's
  verdicts. The controls are synthetic fixtures executed on the hosted runners.
- **Independent observation of platform records** (read-only `gh` REST GET calls on 2026-10-03): the run, job, step
  and artifact records, the jobs API's test-step seconds (equal to the runs' own) and the macOS queue count.
- **Local integration**: the reproductions on CPython 3.12.3 and 3.13.16 with unittest-parallel 1.8.6 and coverage
  7.16.2 on the local host.
- **Source review** at pinned commits: unittest-parallel's `main.py` and README, its issue 27 and commit comparison,
  PyPI's JSON, CPython's `async_case.py`, `pool.py` and `_pickle.c`, and GitHub's documentation of the paths filter.
- **Computed**: the speed ratios, as exact fractions from the measured seconds.
- **Unknown**: the cause of the L4F error.
- **Coordinator decision**: the cancellation, recorded with the run and job records it rests on.

Nothing here is an upstream test or upstream acceptance.

## SOTA sources

- craigahobbs/unittest-parallel at release commit `bda5d77dc1a2fa2df90f5f5a7de297ea375e345c` ("unittest-parallel
  1.8.6"): `src/unittest_parallel/main.py:150-160` (spawned pool, `pool.map` at 160), `:164-211` (report after the map),
  `:240-242` (exit status) and `:62-63` (`--thread`); `README.md:43-71` ("Parallelism Level", "Process and Thread
  Pools"). Issue 27: https://github.com/craigahobbs/unittest-parallel/issues/27. Commits after the release:
  https://github.com/craigahobbs/unittest-parallel/compare/bda5d77dc1a2fa2df90f5f5a7de297ea375e345c...main. PyPI:
  https://pypi.org/pypi/unittest-parallel/json (1.8.6, wheel sha256
  `7f04b0ada502f6b3d655ef49ea2a785f0e37869f9d0ce7a075c1a18ec204ac93`).
- python/cpython at v3.12.3 (`f6650f9ad73359051f3e558c2431a109bc016664`): `Lib/unittest/async_case.py:35-38`,
  `Lib/multiprocessing/pool.py:367`, `:528-546`, `:774` and `:809-831`, `Modules/_pickle.c:3646-3704`; at v3.13.16
  (`cbc944f4bc59639a444dd971c737788ba2283a91`): `Lib/unittest/async_case.py:42`.
- github/docs at `068546469ae7f079368d12f969991a045121c4a0`:
  `data/reusables/actions/workflows/triggering-a-workflow-paths5.md` (a pull request's paths filter uses the three-dot
  diff).
- GitHub REST API, workflow jobs and artifacts: https://docs.github.com/en/rest/actions/workflow-jobs and
  https://docs.github.com/en/rest/actions/artifacts.
- In-repository: `docs/acceptance-evidence-policy.md:55-63`, `docs/evidence.md:18` (`compatibility_attempt`),
  `docs/lanes.md:94-141` (hot-file protocol) and the trial's records at `1e4bb5ab` cited above.
