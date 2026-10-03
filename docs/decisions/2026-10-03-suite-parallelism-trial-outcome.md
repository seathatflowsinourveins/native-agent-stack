# unittest-parallel 1.8.6 is not adopted: the preregistered suite-parallelism trial failed (2026-10-03)

Lane: foundation. North-star action served: a reliable, fast landing path (shorter required test jobs) for every unit
that moves the stack toward US-equities research and paper readiness. Status: decided. Nothing is adopted, the
adoption pull requests for `validate-macos` (PR-A) and `validate` (PR-A2) are not opened, and draft pull request #646,
which holds the trial, is to be closed unmerged by the coordinator after this record's pull request opens. This record
changes no workflow, test, ruleset, required check or repository setting.

The convergence record of this trial is the observed record
[`evidence/artifacts/suite-parallelism-trial-20261003/experiment.json`](../../evidence/artifacts/suite-parallelism-trial-20261003/experiment.json)
(status `observed`, decision `reject`, 36 observations: the 12 timed ubuntu-24.04 runs, the 4 ubuntu-24.04 control
jobs and the 20 macos-15 jobs that never started). `scripts/validate_convergence.py` validates it, and
`manifests/evidence.json` lists it in `convergence_records`. The receipt
[`evidence/receipts/suite-parallelism-trial-20261003.json`](../../evidence/receipts/suite-parallelism-trial-20261003.json)
keeps the detailed measurements and the claim text, and
[`evidence/artifacts/suite-parallelism-trial-20261003/`](../../evidence/artifacts/suite-parallelism-trial-20261003/README.md)
keeps sanitized excerpts and a trimmed oracle output, because GitHub's run records expire under the repository's
90-day retention and the run's 18 artifacts on 2026-11-02.

## Decision

- **Do not adopt unittest-parallel 1.8.6 on this suite as it stands.** The preregistered rule gave ubuntu-24.04 the
  outcome reject (no parallel arm is eligible) and macos-15 no verdict (no run directory). Both required test jobs keep
  their serial commands (`python3 -m unittest` in `validate`, `python3 -m unittest -v` in `validate-macos`).
- **Keep the failed attempt** as this record, the observed convergence record, the receipt and the artifacts
  (AGENTS.md:18; `docs/acceptance-evidence-policy.md:60-61`).
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

Run 37109532421 (attempt 1, event `pull_request`) ran all 18 ubuntu-24.04 jobs; the 16 arm and control jobs recorded
runner image 20260927.320.1, CPython 3.12.3, 4 CPUs and X64 in all 20 of their run directories (the inventory and
compare jobs record none of these). Every timed run checked out the head, and the jobs API's test-step seconds equal
each run's own `step_seconds`.

| Arm | Test-step seconds (r1, r2, r3) | Median | Job seconds | Exit codes | Ids with a result record, per run | Eligible runs |
| --- | --- | --- | --- | --- | --- | --- |
| S | 1,688, 1,659, 1,186 | 1,659 | 1,724, 1,705, 1,212 | 0, 0, 0 | 9,823 (`Ran 9823 tests`, `OK (skipped=967)`) | 3 of 3 |
| L4 | 649, 438, 459 | 459 | 685, 466, 491 | 1, 1, 1 | 9,624, no `Ran` line | 0 of 3 |
| L4F | 539, 692, 710 | 692 | 574, 725, 744 | 1, 1, 1 | 9,624, no `Ran` line | 0 of 3 |
| L4C | 667, 659, 704 | 667 | 698, 688, 733 | 1, 1, 1 | 9,741, no `Ran` line (r3 has 9,743 records: the K4 timing test gave three subtest FAIL records) | 0 of 3 |

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

- **What those ids did in S**, the same in each of the three S runs: at module level 90 were ok and 109 skipped (skip
  reasons: "requires isolated reviewed alpaca-py runtime" for 92 ids, "requires pinned combined native runtime" for the
  9 `MoverLaneFees` ids, "no bash 3.2 binary" for the 8 `bash32` ids), at class level 8 ok and 74 skipped. All 66
  `IsolatedAsyncioTestCase` tests and the 8 `bash32` tests were among the skipped, so at class level unittest-parallel
  lost only the 8 tests of `LinuxReportUnderbashTests` and `MacosReportUnderbashTests` that ran in S. How these tests
  end on macOS is unknown (no macOS run). Per module, with the receipt's `data.missing_ids` holding the counts per
  class:

| Module | Module level: ok / skipped in S | Class level: ok / skipped in S |
| --- | --- | --- |
| `tests/test_adaptive_paper_fees.py` | 38 / 23; skipped: AdaptiveLaneFees 2, FeeCheckpoint 3, FeeHTTPBoundary 2, FeeSnapshot 7, MoverLaneFees 9 | 0 / 7 |
| `tests/test_adaptive_paper_transport.py` | 38 / 78; skipped: AsyncTransport 59, ConfiguredQuoteFeed 5, DataFeedSelection 2, HTTPBoundary 12 | 0 / 59 |
| `tests/test_adoption_version_probes.py` | 14 / 8; skipped: LinuxReportUnderbash32Tests 4, MacosReportUnderbash32Tests 4 | 8 / 8; ok: LinuxReportUnderbashTests 4, MacosReportUnderbashTests 4 |
| Total | 90 / 109 | 8 / 74 |

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
rule, which has no early stop. By then every ubuntu-24.04 arm, control and inventory job had succeeded; the last arm
job, `arms-linux (3, S)`, finished at 09:12:25Z. None of the 20 macos-15 jobs (15 arm jobs and 5 control jobs) had
received a runner in the 49 minutes since they were created at 08:23:23-24Z; each reports zero steps. The `compare`
job (`if: always()`), created at 09:12:40Z, still ran from 09:12:42Z to 09:13:11Z and uploaded the official result.
The decision is justified on three grounds:

- **The failure is deterministic**: one exception, at the same line, in 9 of 9 parallel runs, with identical sets of ids
  that never ran in every run of a level.
- **It does not depend on the platform**: every `IsolatedAsyncioTestCase` instance stores a `contextvars.Context` on
  CPython 3.12.3 and on 3.13.16 (the 3.13 line the macOS arms would have used through setup-python's `'3.13'`: 3.13.16
  locally; the hosted patch release was never recorded), and pickling finds a class by its qualified name on every
  platform. The toy reproductions fail the same way on both versions. Every macOS parallel arm would have hit the same
  three modules, so macOS could only end in reject or no verdict (an inference from these facts, not a macOS run).
- **The shared macOS pool was held up**: from 08:23 to 09:12, five of this repository's macOS jobs (from Adoption
  bootstrap smoke runs, which carry the required `validate-macos` check) held runners in 46 of 50 sampled minutes, and
  never more than five. Had they started, the 20 trial jobs would have held those runners while other pull requests'
  required checks waited, for an outcome that, by the inference above, could only be reject or no verdict. Other
  repositories that share the account's macOS concurrency were not read.

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
  module's suite fails to be sent (61 and 116 ids); at class level only those two classes do (7 and 59). This holds
  although none of these 66 tests ran in the trial's ubuntu-24.04 runs: all were skipped in every S run, because
  `HAS_SDK` was false there (it is true only when both `alpaca` and `requests` import: `tests/test_adaptive_paper_transport.py:18-23`
  and `tests/test_adaptive_paper_fees.py:43-48`; the trial arms installed only unittest-parallel and coverage, and
  `.github/requirements-ci.txt` installs neither package). The skip is a property of that environment, not of the
  operating system. Both classes carry
  `@unittest.skipUnless(HAS_SDK, "requires isolated reviewed alpaca-py runtime")`. A class-level skip only marks the
  class (`Lib/unittest/case.py:159-161` at v3.12.3), the loader builds one instance per test
  (`Lib/unittest/loader.py:94`) and the skip applies only when a test runs (`case.py:612-617`), so every instance
  holds its context before anything is skipped. Locally, a toy module with one plain class and one
  `IsolatedAsyncioTestCase` class fails at module level and runs only its plain class at class level, and a plain-only
  module passes, on CPython 3.12.3 and 3.13.16; the two real modules fail the same way on 3.12.3.
- **(b) Four dynamically built classes are not importable under their qualified names.**
  `tests/test_adoption_version_probes.py:431-437` defines `behavior_case(platform_id, shell, label)`, which returns
  `unittest.skipUnless(shell, reason)(type(f"{platform_id.capitalize()}ReportUnder{label.replace(' ', '').replace('.', '')}Tests", (ReportBehaviorMixin, unittest.TestCase), {...}))`,
  and lines 440-443 bind the results as `LinuxReportUnderBashTests`, `MacosReportUnderBashTests`,
  `LinuxReportUnderBash32Tests` and `MacosReportUnderBash32Tests`. `type()` names the classes from the label, with a
  lower-case "bash" (`LinuxReportUnderbash32Tests` and so on), and the module has no attribute of that name. CPython's
  pickler looks a class up by its `__qualname__` in its module (`Modules/_pickle.c` lines 3664 and 3697 at v3.12.3), so
  locally the run stops with
  `_pickle.PicklingError: Can't pickle <class 'tests.test_adoption_version_probes.LinuxReportUnderbash32Tests'>: attribute lookup LinuxReportUnderbash32Tests on tests.test_adoption_version_probes failed`
  (lines 3700-3702) on CPython 3.12.3; the coordinator saw the same at module level on 3.13.16, an output that is not
  in the retained artifacts. On ubuntu-24.04 the two `bash32` classes (8 tests) were skipped in every S run (no bash 3.2
  binary), and the two `bash` classes (8 tests) ran, ok: they are the only class-level missing ids that ran in S. This
  is the same class of defect as the B1 wrapper that the trial branch fixed: classes that a worker cannot find under
  the name pickle looks up.
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

- Anything about macOS: no macOS job ran, so the serial outcome there of the tests that never ran is unknown too.
- Whether a suite fixed under precondition (i) would meet the rule: the parallel seconds cover 9,624 or 9,741 of 9,823
  tests and end in a crash, and the serial seconds of most missing tests are not measured. The `--durations 25` tables
  list only each S run's 25 slowest tests, and the only missing ids they list are two in S-r3:
  `MacosReportUnderbashTests.test_every_probe_is_bounded_classified_and_nothing_else_runs` (5.594 s) and
  `LinuxReportUnderbashTests.test_every_probe_is_bounded_classified_and_nothing_else_runs` (5.546 s). Most missing ids
  were only skipped in S (109 of 199 at module level and 74 of 82 at class level; 90 and 8 were ok), all 66
  `IsolatedAsyncioTestCase` tests among them: those two classes break unittest-parallel at pickling although their
  tests are skipped wherever `HAS_SDK` is false, as in every S run (root cause (a)).
- Speed beyond three runs per arm: each arm ran three times on shared hosted runners, so the medians, the extremes and
  the ratios rest on n=3, and each slowest-over-fastest ratio divides by the single fastest S run (1,186 s) inside a
  serial spread of 1,186 to 1,688 s. A new trial should set its repeat count with this noise in view.
- The cause of the L4F error.
- Whether the class-level K4 timing failures come from CPU load alone.
- Anything about the candidate classes in the completeness critique below.

## Departures from the preregistration

- **The cancellation**, described above.
- **Where the observed record lives.** The preregistration's `next_decision_changing_test` asked for an observed
  convergence record (one `native_cli_execution` observation per timed run) beside `experiment.json`. That directory
  exists only on the trial branch, which is never merged, and its workflow re-runs the whole trial on every push to that
  branch and in any pull request that adds it. The observed record is therefore
  `evidence/artifacts/suite-parallelism-trial-20261003/experiment.json`, beside the retained artifacts, and this pull
  request contains no workflow. Its `frozen_inputs` point to the retained byte copy of the preregistered record
  (`preregistration-experiment.json.txt`, sha256 `305fc2fa2ddd2c0a0eba4d85d748807db87302bde59a6b6489de866bee416c08`)
  and to `result-trimmed.json`, because the frozen files themselves exist only at the trial head `1e4bb5ab`; their 15
  preregistered hashes were re-checked there with `git show` (15 of 15 equal). The copy keeps the `.json.txt` suffix
  because its own `frozen_inputs` name those trial-branch files, so it cannot validate on main, and
  `scripts/validate_convergence.py --all-recorded` would refuse it as an undeclared convergence record.
- **The observed record's shape.** It carries the preregistered `predeclared_metrics`, `commands`, lane, roles and base
  revision unchanged, and departs from the plan in three ways, each stated in its `limitations`. (1) It adds one
  observation per control job (tasks `controls-ubuntu-24.04` and `controls-macos-15`, command 7), which the
  preregistration did not plan. The contract allows `passed` only with exit code 0
  (`scripts/validate_convergence.py:120`), so a control observation's `exit_code` is its control step's own exit (0;
  the step records each command's exit and never fails), and the commands' expected exits (1 and 3 under S, 5 and 124
  under unittest-parallel) are in its scope text. (2) The 20 macos-15 jobs are skipped observations with no exit code
  and no quality. (3) Token usage is null (unknown) for every observation, not the preregistered observed zeros: no
  model ran in a hosted job and the jobs expose no token counter. `native_retries` is 0 for the 16 executed jobs
  (`run_attempt` 1 everywhere), and runner time, which the contract has no field for, is in each observation's scope
  text.

## Completeness critique

The coordinator's completeness critique of this unit (2026-10-03), requested in the review of pull request #652, asks
which modality, source or candidate class the unit missed. Its seeds below feed the next landscape sweep of the
`ci-supply-chain` layer.

### Modality missed before the trial

- **No whole-suite run under the candidate runner before preregistering.** The only parallel preflight ran the
  29-test wrapper module. The plan's whole-suite local preflight never ran, as the preregistration itself recorded
  (the 2026-10-03 row "Preregistering a hosted whole-suite trial after a preflight of one module" in
  `docs/harness-defaults.md`).
- **The hosted behaviour of background steps was never examined.** The plan's search-first comparison named GitHub
  background steps, and the preregistration lists "a background-steps arm" among the open plan items it did not test.
  No hosted job ran one, although GitHub had announced the `background`, `wait`, `wait-all`, `cancel` and `parallel`
  step keywords on 2026-06-25.

### Candidate classes this trial did not evaluate

The list comes from a read-only single-family research lane (Codex, `gpt-6.1-sol` at max effort, live search,
2026-10-03): a lead, not authority. Every claim relayed here was re-read on 2026-10-03 with GET requests at the cited
release, pinned below by commit. **VERIFIED** means the cited upstream text or record says it. **LEAD-ONLY** means
it was not found or not checked there, so it is not asserted. None of these classes ran on this suite, so whether
any of them keeps the suite's ids and outcomes is unknown.

- **GitHub Actions parallel steps running module shards**, one `python3 -m unittest` process per shard. Source: the
  GitHub changelog "Actions steps can now be run in parallel" (2026-06-25) and github/docs
  `content/actions/reference/workflows-and-actions/workflow-syntax.md` at `2bd66de8` (lines 1078-1084, 1107-1111,
  1140-1147, 1172, 1193-1199 and 1224).
  - Favours: no added package and no pickling, since each shard is its own interpreter that imports its modules by
    name. Each step keeps its own log. A failed background step fails the job at the next `wait` or `wait-all`. At
    most 10 background steps run at once in a job.
  - Blocks: loading a module by name calls its `load_tests` with `pattern=None`, unlike discovery (CPython v3.13.16
    `Lib/unittest/loader.py:117`, `:178`, `:427`, `:449`), so the union of the shards must be shown to equal the
    discovered inventory.
  - Status: VERIFIED for the keywords, the limit, the failure propagation and the loader's behaviour. LEAD-ONLY: import
    order and process-isolation parity, and how background steps behave on these two hosted runners.
- **One `python3 -m unittest` process per module under `xargs -P`.** Source: GNU findutils 4.10.0 release
  announcement (bug-findutils, 2024-06-01) and the installed GNU xargs 4.10.0 manual page ("EXIT STATUS").
  - Favours: no added Python package. GNU xargs exits 123 when a child exits with 1 to 125 and 125 when a child is
    killed by a signal.
  - Blocks: the same `load_tests` and parity questions as above, and a hang needs an external deadline.
  - Status: VERIFIED for the GNU exit statuses and the release date. LEAD-ONLY: the macOS xargs (Apple
    `shell_cmds`), and GNU Parallel's options and release.
- **stestr 4.2.1** (PyPI upload 2026-02-20). Source: mtreinish/stestr at `2802f142`
  (`stestr/config_file.py:201-206`, `stestr/subunit_runner/program.py:181-192`, `stestr/output.py:154-159`,
  `doc/source/MANUAL.rst:456-463`, `pyproject.toml:30-38`) and testing-cabal/testtools at `088c98e2` (2.9.1:
  `testtools/testresult/real.py:2210` and `:2285-2294`).
  - Favours: each worker runs stdlib discovery and keeps only the ids in its id file, so no TestCase is pickled. A
    worker that exits non-zero adds a synthetic failing test. Scheduling uses historical timing data.
  - Blocks: its stream records an error and a failure as the same status (`addFailure = addError`, both converted to
    `fail`), so the per-id outcome oracle would need another recorder. It brings at least eight distributions (stestr
    and seven direct dependencies), against two for unittest-parallel.
  - Status: VERIFIED for all of the above. LEAD-ONLY: that `stestr run --subunit` can exit 0 despite failures (the
    4.2.1 manual has no exit-code section), and that a closed worker stream can hang.
- **pytest 9.1.1 with pytest-xdist 3.8.0** (PyPI uploads 2026-06-19 and 2025-07-01). Source: pytest-dev/pytest at
  `cf470ec0` (`doc/en/how-to/unittest.rst:29` and `:33-35`, `pyproject.toml:49-56`) and pytest-dev/pytest-xdist at
  `1e3e4dc1` (`docs/how-it-works.rst:20-36` and `:80-89`, `docs/distribution.rst:58`, `:65` and `:121`,
  `src/xdist/dsession.py:238-240` and `:556-564`, `pyproject.toml:34-37`).
  - Favours: every worker collects the tests itself and the controller sends only test indexes, so nothing is pickled.
    `subTest` is supported since pytest 9.0. It offers `loadfile`, `loadscope` and `worksteal` distribution and
    `--max-worker-restart`.
  - Blocks: pytest does not support the `load_tests` protocol, which `tests/test_native_maintenance.py` uses (the only
    test module here that defines it), so the ids would differ. Its direct dependencies make seven distributions on
    CPython 3.12 Linux (pytest, iniconfig, packaging, pluggy, pygments, pytest-xdist and execnet).
  - Status: VERIFIED for all of the above. LEAD-ONLY: how pytest collects the four `type()`-built classes and runs
    `IsolatedAsyncioTestCase`, and the full dependency closure.
- **nose2 0.16.0 multiprocess plugin** (PyPI upload 2026-03-02: one `py3-none-any` wheel and no required dependency).
  Source: nose-devs/nose2 at `c93ca65a` (`nose2/plugins/mp.py:36`, `:128-139`, `:165-171` and `:345-351`,
  `nose2/plugins/loader/loadtests.py:9-13`, `nose2/plugins/junitxml.py:192-195` and `:205-209`).
  - Favours: one universal wheel and no required dependency. Workers reload dotted test names, so no TestCase is
    pickled.
  - Blocks: its own documentation warns that suites using `load_tests` do not work correctly with the multiprocess
    plugin. A lost worker is only logged, the loop never ends a hung worker, and the plugin joins every process without
    a timeout. Its JUnit XML writes expected failures and unexpected successes as skipped.
  - Status: VERIFIED for all of the above. LEAD-ONLY (an inference, not run): that the dotted-name reload fails for the
    four `type()`-built classes, as pickling's lookup does.
- **concurrencytest 0.1.11** (PyPI upload 2026-03-13; requires python-subunit and testtools). Source:
  cgoldberg/concurrencytest at `266e27c8` (`concurrencytest.py:104-113` and `:139-144`) and testing-cabal/subunit at
  `c8560528` (1.4.6: `python/subunit/__init__.py:375-379`).
  - Favours: it forks after discovery, so the children inherit the test instances and nothing is pickled.
  - Blocks: the parent keeps only a stream reader per child and never waits on one (the module has no `waitpid`), and
    subunit's parser ignores a connection lost outside a test, so a child that dies before its first test can go
    unreported (an inference from those lines).
  - Status: VERIFIED for the mechanism, the lines and the dependencies. LEAD-ONLY: that its partitioning repeats module
    fixtures.
- **green 4.0.2** (PyPI upload 2024-04-18). Source: CleanCut/green at `4de285b0` (`green/config.py:177-178` and
  `:426-430`, `green/loader.py:371-377`, `green/runner.py:137`, `requirements.txt`), PyPI JSON and the repository
  record (last push 2024-11-12).
  - Blocks: the release is an sdist only (`green-4.0.2.tar.gz`), which this repository's `--only-binary=:all:`
    hash-locked installs refuse, and the repository has had no push since 2024-11-12. Its concurrency option is
    `-s`/`--processes` (`-j` writes a JUnit report). Workers load test-module targets, and the runner reads results with
    a blocking `queue.get()` that has no timeout.
  - Status: VERIFIED for all of the above. LEAD-ONLY: that a worker's death hangs the run.
- **unittest-parallel's other modes.** Source: craigahobbs/unittest-parallel at `bda5d77d`
  (`src/unittest_parallel/main.py:123-128` and `:142-160`, `README.md:59-70`).
  - Blocks: `--level test` also maps live TestCase instances to the spawned pool, so it pickles them too, and
    `--disable-process-pooling` only sets `maxtasksperchild` to 1. `--thread` uses a `ThreadPoolExecutor`, so nothing is
    pickled, but the README says it improves performance only on free-threaded Python (the runners' CPython 3.12.3 has
    the GIL) and not to use it with `unittest.mock`, which 100 of this suite's 234 test modules import (counted at this
    record's base).
  - Status: VERIFIED.
- **CPython regrtest and zope.testrunner 8.3**, which the lead's own completeness sweep added (zope.testrunner PyPI
  upload 2026-07-30). Source: python/cpython at `cbc944f4` (v3.13.16: `Lib/test/libregrtest/single.py:29-31`,
  `Lib/test/libregrtest/worker.py:120-122`) and zopefoundation/zope.testrunner at `1061ccc4`
  (`src/zope/testrunner/find.py:437-438`, `pyproject.toml:41-44`).
  - regrtest loads a module's tests with `loadTestsFromModule` and runs each worker in a temporary working directory.
    zope.testrunner puts plain TestCase suites in its `UnitTests` layer by default and needs three core distributions.
  - Status: VERIFIED for those lines, the dependencies and the date. LEAD-ONLY: regrtest's availability on the
    runners' Python and its parity, and the lead's view that zope.testrunner's layers give little parallelism here.

### Found after the trial, not part of this record's evidence

A second preregistered trial, of GitHub parallel steps running module shards, is being prepared. A local whole-suite
preflight for it (local integration evidence only, on another machine) reproduced the serial outcomes exactly. Its
record will follow. No number from that preflight is used here.

### Seeds for the next landscape sweep

The seeds use the sweep's `--seeds` format, a JSON object keyed by layer id
(`tools/sota-convergence/landscape-sweep/README.md`, and the precedent `seeds-20260926.json`); `build_inputs.py`
refuses a key that is not a landscape layer id (`build_inputs.py:21-22` and `:225-234`). The lifecycle task, parallel
test execution inside one CI job for a stdlib unittest suite, asks for tools, so its key is the repository sweep's
`ci-supply-chain` layer, whose requirement covers attributable hosted checks. The skills sweep's lifecycle-task keys
(`skills-test`, `skills-ci-pr`) select skills, not test runners. This record writes nothing under `tools/` or
`catalogs/`.

```json
{
  "ci-supply-chain": [
    "Lifecycle task: parallel test execution inside one CI job for a stdlib unittest suite. This repository's suite has 9,823 ids at the trial head, load_tests in tests/test_native_maintenance.py, two IsolatedAsyncioTestCase classes and four type()-built classes; its required jobs are validate (ubuntu-24.04) and validate-macos (macos-15). unittest-parallel 1.8.6 was rejected on ubuntu-24.04 by a preregistered trial on 2026-10-03 (docs/decisions/2026-10-03-suite-parallelism-trial-outcome.md; evidence/artifacts/suite-parallelism-trial-20261003/experiment.json).",
    "GitHub Actions parallel steps (background, wait, wait-all, parallel; GitHub changelog 2026-06-25; at most 10 concurrent background steps per job) running disjoint module shards, one python3 -m unittest process per shard. A second preregistered trial is being prepared.",
    "One python3 -m unittest process per module under xargs -P or GNU Parallel, with no added Python package.",
    "stestr 4.2.1: id files, discovery and id filtering in each worker, timing-based scheduling; its subunit stream records errors and failures as one status.",
    "pytest-xdist 3.8.0 with pytest 9.1.1: index dispatch without pickling; pytest does not support the load_tests protocol.",
    "nose2 0.16.0 multiprocess plugin: dotted-name reload; its documentation warns that load_tests suites do not work correctly with it.",
    "concurrencytest 0.1.11: fork after discovery; the parent never waits on its children.",
    "green 4.0.2 (sdist-only release, no push since 2024-11-12), CPython regrtest and zope.testrunner 8.3: candidates with stronger blockers or unverified availability.",
    "unittest-parallel --thread: no pickling, but its README says it speeds up only free-threaded Python and must not be used with unittest.mock.",
    "Question for the next critic: which classes did this list miss? In particular flaky-test tooling (detecting, rerunning or quarantining timing-bound tests such as tests.test_secret_path_guard.K4GuardTests.test_k4_timing, which failed in 3 of 3 class-level runs), shard balancing from recorded durations (the serial runs' --durations tables, stestr's timing-based scheduler, the plan's pytest-split) and test selection (running only the tests a change affects, such as the plan's pytest-testmon), each judged on this suite's measured needs."
  ]
}
```

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
4. **A whole-suite local preflight under the candidate runner before preregistering** (the 2026-10-03 row
   "Preregistering a hosted whole-suite trial after a preflight of one module" in `docs/harness-defaults.md`). The
   preregistration recorded that this preflight had not run and that no whole-suite parallel run had happened
   anywhere.

## Evidence class

- **Convergence record**: `evidence/artifacts/suite-parallelism-trial-20261003/experiment.json`, status `observed`,
  decision `reject`. It holds 16 `native_cli_execution` observations of hosted ubuntu-24.04 jobs (the 12 timed runs and
  the 4 control jobs, whose fixtures are synthetic) and 20 skipped macOS observations, generated from the raw run
  directories, the jobs API and `result.json`. `scripts/validate_convergence.py` checks its declared consistency and
  artifact hashes, not its truth.
- **Native execution on GitHub-hosted ubuntu-24.04, receipt retained** (template class `native_proven`): the per-run
  exit codes, test-step seconds, result records, ids that never ran and their serial outcomes, other differences and
  the oracle's verdicts.
- **Synthetic fixtures executed on the hosted runners** (template class `synthetic`): the control and crash-control
  results.
- **Independent observation of platform records** (read-only `gh` REST GET calls on 2026-10-03): the run, job, step
  and artifact records, the jobs API's test-step seconds (equal to the runs' own) and the macOS queue count.
- **Local integration**: the reproductions with unittest-parallel 1.8.6 and coverage 7.16.2 on the local host: the toy
  modules on CPython 3.12.3 and 3.13.16, the three real modules on 3.12.3 only and the order-throughput module on both.
- **Source review** at pinned commits: unittest-parallel's `main.py` and README, its issue 27 and commit comparison,
  PyPI's JSON, CPython's `async_case.py`, `case.py`, `loader.py`, `pool.py` and `_pickle.c`, and GitHub's
  documentation of the paths filter.
- **Source review for the completeness critique** (GET reads on 2026-10-03 at the commits pinned below): each claim
  relayed there is marked VERIFIED or LEAD-ONLY. The candidate list itself is a lead from a single-family Codex lane.
- **Computed**: the speed ratios, as exact fractions from the measured seconds.
- **Unknown**: the cause of the L4F error.
- **Coordinator decision**: the cancellation, recorded with the run and job records it rests on.
- **Usage**: the hosted jobs ran deterministic commands and no model. Runner time is the per-job seconds in the
  receipt's `data.jobs`, for the 18 ubuntu-24.04 jobs only (11,524 s in total, 11,461 s of them in the 16 observed arm
  and control jobs); the 20 macOS jobs were never assigned a runner. The observed record keeps token usage null
  (unknown), not counted as zero. The model usage of the planning, build and review sessions is unknown: it is not
  recorded and not counted as zero.

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
  `Lib/unittest/case.py:159-161`, `:176-182` and `:612-617`, `Lib/unittest/loader.py:94`,
  `Lib/multiprocessing/pool.py:367`, `:528-546`, `:774` and `:809-831`, `Modules/_pickle.c:3646-3704`; at v3.13.16
  (`cbc944f4bc59639a444dd971c737788ba2283a91`): `Lib/unittest/async_case.py:42`.
- github/docs at `068546469ae7f079368d12f969991a045121c4a0`:
  `data/reusables/actions/workflows/triggering-a-workflow-paths5.md` (a pull request's paths filter uses the three-dot
  diff).
- GitHub REST API, workflow jobs and artifacts: https://docs.github.com/en/rest/actions/workflow-jobs and
  https://docs.github.com/en/rest/actions/artifacts.
- Completeness critique, read with GET requests on 2026-10-03 at these commits (each tag resolved through the GitHub
  commits API):
  - craigahobbs/unittest-parallel at `bda5d77d`: `src/unittest_parallel/main.py:123-128` and `:142-160`, and
    `README.md:59-70`.
  - pytest-dev/pytest 9.1.1 at `cf470ec0bf7eb89cd97dd56df4859eae5db46447`, and pytest-dev/pytest-xdist v3.8.0 at
    `1e3e4dc16523c8a8f6c67d95a950166420718c99`.
  - mtreinish/stestr 4.2.1 at `2802f1425f45b9ad0857ff4685ab469dcd2cf2e0`, and testing-cabal/testtools 2.9.1 at
    `088c98e24961ecf6d94ea5204457f2dcffe2f1c6`.
  - nose-devs/nose2 0.16.0 at `c93ca65ac6f62475209aa8944fda14c671615549`.
  - cgoldberg/concurrencytest 0.1.11 at `266e27c833f9b1ecb47142bdddbac5199bebab72`, and testing-cabal/subunit 1.4.6 at
    `c85605280cb1d975b3076b9ad7ac38f17e858945`.
  - CleanCut/green 4.0.2 at `4de285b05b8e6b161159be2241b219dc5176f0e5`.
  - zopefoundation/zope.testrunner 8.3 at `1061ccc4b6b5a824870f2142bc948863b7ba1f70`.
  - python/cpython v3.13.16 at `cbc944f4bc59639a444dd971c737788ba2283a91`: `Lib/unittest/loader.py:100`, `:117`,
    `:178`, `:427` and `:449`, `Lib/test/libregrtest/single.py:29-31` and `Lib/test/libregrtest/worker.py:120-122`.
  - github/docs at `2bd66de8cea336061c9ea060c9b37385136e6ab3`:
    `content/actions/reference/workflows-and-actions/workflow-syntax.md` (`background`, `wait`, `wait-all`, `cancel`,
    `parallel`), and the GitHub changelog
    https://github.blog/changelog/2026-06-25-actions-steps-can-now-be-run-in-parallel/.
  - GNU findutils 4.10.0 release announcement:
    https://lists.gnu.org/archive/html/bug-findutils/2024-06/msg00017.html. The "EXIT STATUS" section of the
    installed GNU xargs 4.10.0 manual page.
  - PyPI JSON for each release named, at `https://pypi.org/pypi/<name>/<version>/json` (upload dates and files), and
    the GitHub repository records of green, concurrencytest, stestr and nose2 (archived state and last push).
- In-repository: `docs/acceptance-evidence-policy.md:55-63`, `docs/evidence.md:18` (`compatibility_attempt`),
  `docs/lanes.md:94-141` (hot-file protocol), `blueprints/convergence-practice/contract-reference.md:84-92` (usage
  fields), `scripts/validate_convergence.py:99-123` (failure coverage and run status), the sweep's
  `tools/sota-convergence/landscape-sweep/README.md` and `build_inputs.py:21-22` and `:225-234` (the seeds format), and
  the trial's records at `1e4bb5ab` cited above.
