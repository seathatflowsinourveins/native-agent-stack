# Suite-parallelism trial oracle (2026-10-03)

North-star action served: shorten the two required test jobs (`validate-macos`,
`validate`) so every pull request reaches a verdict sooner, without changing
which tests run or how their outcomes are judged.

This directory is the independent, stdlib-only oracle for the preregistered
trial of [unittest-parallel](https://github.com/craigahobbs/unittest-parallel)
1.8.6 (release commit `bda5d77dc1a2fa2df90f5f5a7de297ea375e345c`, PyPI wheel
sha256 `7f04b0ada502f6b3d655ef49ea2a785f0e37869f9d0ce7a075c1a18ec204ac93`,
hard dependency `coverage` 7.16.2). The trial runs the same frozen suite
serially and in parallel on actual GitHub-hosted runners; this oracle decides
from their logs whether each parallel arm is equivalent to the serial
production command and whether it is fast enough to adopt. It runs no test of
the suite itself and starts no service.

Evidence class: everything checked here so far is local integration evidence
and synthetic fixtures (real local runs of the controls), not upstream
acceptance and not a GitHub-hosted run.

| File | Purpose |
|---|---|
| `ids.py` | Sorted, de-duplicated test ids of a checkout, from discovery only. |
| `compare.py` | Parses every arm-run, checks eligibility, writes `result.json` and an optional Markdown summary. |
| `controls/test_zz_trial_controls.py` | Known-outcome control file (never placed under `tests/`). |
| `controls/crash_control/test_crash.py` | Crash control: one test calls `os._exit(3)`. |
| `controls/control_expectations.json` | What every arm must report for the controls. |
| `test_compare.py` | Tests of the oracle against real control logs and mutated copies. |
| `test_b1_failure_mode.py` | Regression test of the B1 wrapper's failure mode (fix round item 7), in temporary trees; the trial workflow does not run it. |
| `make_fixtures.py` | Regenerates `fixtures/` from real local runs of the controls. |
| `fixtures/` | Sanitized real control logs (`real/`), mutated copies (`mutated/`), `index.json`, `inventory-controls.txt`. |

`experiment.json` freezes every file in this table by hash except the fixture
logs. Those are frozen through `fixtures/index.json`, which is itself frozen
and lists each log's sha256; `test_compare.py` requires every file under
`fixtures/` other than `index.json` and `inventory-controls.txt` to be listed
there with that hash, and no listed file to be missing.

## Arms

Baseline arm per OS is `S`, the production command. Each arm's command must
match the table token for token (`compare.py` splits `meta.json` `command`
with `shlex` and compares it with `ARMS[os][arm]["command"]`). Any other token
makes the run ineligible: a token before `-m` such as an interpreter flag
(`-X dev`, `-O`) or a wrapper (`coverage run`, `timeout 300`), another
interpreter name, a reordering, another spelling of a flag (`-j3`,
`--level=module`) or an extra argument. The workflow records `command.txt`
as the arm's words before any time limit wraps them, so the limit never
appears in it.

| OS | Arm | Command |
|---|---|---|
| macos-15 | S | `python3 -m unittest -v` |
| macos-15 | P3 | `python3 -m unittest_parallel -j 3 --level module -v` |
| macos-15 | P3F | `python3 -m unittest_parallel -j 3 --level module --disable-process-pooling -v` |
| macos-15 | P3C | `python3 -m unittest_parallel -j 3 --level class -v` |
| macos-15 | P4 | `python3 -m unittest_parallel -j 4 --level module -v` |
| ubuntu-24.04 | S | `python3 -m unittest -v` |
| ubuntu-24.04 | L4 | `python3 -m unittest_parallel -j 4 --level module -v` |
| ubuntu-24.04 | L4F | `python3 -m unittest_parallel -j 4 --level module --disable-process-pooling -v` |
| ubuntu-24.04 | L4C | `python3 -m unittest_parallel -j 4 --level class -v` |

The only permitted extra is the plan's diagnostic on `S`: `--durations N`
(a positive integer; the workflow appends `--durations 25`), placed after
`-v`. The parser skips its table. `test_compare.py` checks that this table,
the workflow's `set --` lines and `compare.py` name the same commands.

## Input layout (contract with the trial workflow)

One directory per run under `--results DIR`:

- `DIR/<os>-<arm>-r<N>/`: a timed arm-run, repeat `N` (1, 2, 3).
- `DIR/<os>-<arm>-controls[-r<N>]/`: that arm's command run on the controls file alone.
- `DIR/<os>-<arm>-crash[-r<N>]/`: that arm's command run on the crash control alone.

`<os>` is `macos-15` or `ubuntu-24.04`. Each directory holds:

- `log.txt`: stdout and stderr of the command, in one file (`> log.txt 2>&1`).
- `exit-code.txt`: one integer, the command's exit status (for the crash
  control, the bound's status: `timeout` exits 124 when it fires).
- `meta.json`: `{"os", "arm", "repeat", "command", "python_version",
  "platform", "runner_image", "checkout_sha", "step_seconds"}`;
  `step_seconds` (the test step's duration, the selection metric) is required
  for arm-runs only. Control and crash runs still need every other field,
  with `repeat` 1 unless the directory name gives `-r<N>`.
- `git-status.txt`: `git status --porcelain=v1 --untracked-files=all` of the
  checkout after the run, or the recorder's text `git status failed`. It
  must exist and be empty (the oracle's second part).
- `runtime.json`: the runner's runtime record, whose `run_attempt` is
  `GITHUB_RUN_ATTEMPT` (`"1"` on a run's first attempt, one more for each
  re-run). It must record attempt 1.

Other entries are listed in `result.json` `inputs.ignored_entries`, never
dropped silently.

## Parsing rules (preregistered)

Derived from CPython `Lib/unittest/` at v3.13.16 (macOS, `actions/setup-python`
3.13) and v3.12.3 (the ubuntu-24.04 system Python): `runner.py`, `result.py`
and `suite.py` are byte-identical at those two tags. Also derived from
unittest-parallel's `src/unittest_parallel/main.py` at `bda5d77`. `compare.py`
cites the file and line beside each rule.

1. Summary: the last `separator2`, `Ran N test(s) in X.XXXs`, blank, status
   line block (`OK`, `OK (skipped=K)`, `FAILED (failures=F, errors=E,
   skipped=K, expected failures=X, unexpected successes=U)`, `NO TESTS RAN`).
   Buffered stdout is flushed after it, so the block need not be last. No such
   block means a truncated log.
2. Mode: a `Running N test suites (M total tests) across K workers` line
   (unittest-parallel main.py:134-137) marks a parallel log.
3. A description is `<method> (<module>.<class>.<method>)`; a docstring adds
   its first line on a second line. Fixture failures and skips are named
   `setUpClass (<module>.<class>)` (also `setUpModule`, `tearDownClass`,
   `tearDownModule`). Subtests add ` (<params>)` or ` [<msg>]`.
4. Serial: each test prints `<description> ... ` and its status follows at
   once, on a later line after test output, or glued to the end of an
   unterminated output line (all three occur in real CI logs). After
   `expected failure` or `unexpected success` CPython prints a following
   fixture result as a bare status word; it is named from the error report.
5. Parallel: each test prints a start line and a result line, and lines of
   different workers interleave. Result lines decide outcomes; start lines
   only reveal missing results. Output glued before a record and records glued
   after a docstring line are separated. A subtest status that CPython writes
   separately from its docstring description is reattached.
6. Outcomes: `ok`, `FAIL`, `ERROR`, `skipped`, `expected failure`,
   `unexpected success`. A test whose subtests failed gets no status line of
   its own; its outcome is derived (`ERROR` over `FAIL` over `skipped`) and
   each failing subtest is its own record.
7. Self-consistency, or the run is ineligible: started tests equal `Ran N`;
   records per outcome equal the status line's counts; the status word agrees
   with the counts; the error report lists exactly the failing records.
8. Exit status is compared as zero versus non-zero only: CPython exits 1 on
   failure and 5 when no test ran; unittest-parallel exits with the failure,
   error and unexpected-success count, capped at 255.

## Eligibility (per run directory; reported, never silently dropped)

The oracle has two parts, and `compare.py` applies both. An arm-run is
ineligible when any of these hold.

Part 1:

- `log.txt`, `exit-code.txt` or `meta.json` is missing or invalid.
- `meta.json` disagrees with the directory name.
- The command is not the arm's preregistered command, token for token
  ("Arms").
- `checkout_sha` differs from the frozen corpus (`--expected-sha`, else the most common value).
- `python_version` differs from S on that OS.
- The log is truncated or has no Ran line, or a self-consistency check above fails.
- The exit status disagrees with the status line.
- The header is missing (parallel) or present (serial), or reports a worker count other than `min(suites, jobs)`.
- The executed ids are not exactly the trial inventory. Skipped tests must
  still appear; tests behind a failed or skipped `setUpClass` or
  `setUpModule` count as accounted.
- Its records differ from the S baseline of the same OS outside the flaky ids.
- `runtime.json` is missing or records no `run_attempt`, or an attempt above
  1. A job re-run voids the run (see "Re-runs").

Part 2:

- `git-status.txt` is missing, says `git status failed` or is not empty:
  the run left the checkout dirty or its status is unrecorded.

The control and crash runs must meet the same file, command, `run_attempt`
and `git-status.txt` rules, or that control run fails and its arm is not
eligible. The workflow's clean-checkout step repeats part 2 on its own as a
second check (`checkout-status.json`).

Flaky ids: ids (fixture keys included) whose records differ among the
eligible S repeats of an OS. They are listed in `result.json`
(`verdicts.<os>.baseline.flaky_ids`) and excluded from mismatch counting. S
runs that disagree on `python_version` void that OS.

Id mapping: at base `56473e4b`, `tests/test_native_maintenance.py` loaded six
classes through `load_tests` under bare module names, with 29 ids in total
(`compare.py` `B1_CLASSES` and `B1_IDS`: 6, 7, 2, 2, 2 and 10 ids). The trial
head loads them as child modules of the wrapper, which prefixes their ids with
`tests.test_native_maintenance.`. `--inventory-base` (the base) and
`--inventory-trial` (the head) may differ only by that single prefix on
exactly those 29 base ids, as a bijection. The base must hold all 29, and
every other id must be the same in both. A partial rewrite, another prefix
(for every module or for one), identical inventories or any other difference
sets `id_mapping.ok` to false. `compare.py` then gives every OS the outcome
`no verdict`. Arms are compared on trial ids.

## Decision rule (preregistered)

An arm is eligible when all of these hold:

- It has at least three runs (`--min-repeats`).
- Every one of its runs is eligible under both oracle parts.
- Its controls run and crash control run on that OS passed.

The S arm must be eligible too, or the OS gets no verdict. Then:

1. Take the fastest eligible parallel arm by median `step_seconds` (a tie
   goes to the arm name that sorts first).
2. Adopt it only if its median is at most 0.60 times the S median and its
   maximum is at most 0.75 times the fastest S run. Otherwise reject, with no
   fall-through to a slower arm. The ratios are compared exactly, as
   fractions of the recorded seconds, with no rounding before the comparison:
   a true ratio of 0.600040 or 0.750040 fails, while exactly 0.6000 and 0.7500
   pass. `result.json` shows each ratio rounded to four decimals for display,
   and exactly as a fraction (`median_vs_s_median_exact`,
   `max_vs_s_fastest_exact`).
3. If the adopted arm is P3 (L4), take P3F (L4F) instead when that arm is
   eligible, meets step 2 and its median is at most 1.10 times the pooled
   median, also compared exactly.
4. If `id_mapping.ok` is false, every OS gets `no verdict`, whatever steps 1
   to 3 gave.

The plan states this preference: "prefer P3F if within 10% of P3". The
coordinator confirmed it on 2026-10-03, before any hosted run, for P3F over
P3 and for L4F over L4.

Every OS of the preregistration (`macos-15`, `ubuntu-24.04`) is listed in
`result.json` `verdicts` and in the summary, with all its arms. An OS for
which no run directory arrived (timed, control or crash) gets `no verdict`
with the reason `no run directory`.

## Re-runs (preregistered)

The trial is repeated only as a whole, by a new synchronize of the draft pull
request (a new head commit), never by re-running jobs. A job re-run voids the
affected arm-run, which is reported as a failed attempt. Every attempt is
reported.

- Every artifact upload sets `overwrite: false`. The input's description in
  actions/upload-artifact's `action.yml` at the pinned `043fb46d` says the
  action then fails if an artifact of that name already exists. A re-run's
  upload fails visibly instead of replacing the earlier attempt's artifact,
  and `compare.py` reads the earlier one. That this holds across the attempts
  of one workflow run rests on that description and on upstream issue
  reports, not on a hosted run.
- When a re-run's artifact reaches `compare.py` (for example because the first
  attempt uploaded none), its `runtime.json` `run_attempt` is above 1, and
  the run is ineligible.
- The observed record lists every workflow run and every attempt of it,
  taken from the jobs API, beside `result.json`.

## Controls

The workflow runs controls as separate jobs, never inside the timed arms, and
never copies them into `tests/`.

- Controls run: copy `controls/test_zz_trial_controls.py` alone into an empty
  directory, `cd` there and run the arm's exact command. Every arm, S included,
  must report exactly what `standalone_run` in `control_expectations.json`
  lists. That means `Ran 8`, `FAILED (failures=2, errors=2, skipped=1,
  expected failures=1, unexpected successes=1)`, a non-zero exit, these exact
  records (a pass, a skip, a failure, an error, a failing subtest with a
  docstring, an expected failure, an unexpected success, a multi-line
  docstring, a `setUpClass` error that keeps one test from running) and, in
  parallel, a header of 1 module suite or 3 class suites over 9 tests.
- Crash control: copy `controls/crash_control/test_crash.py` alone into an
  empty directory and run `timeout 300 <arm command>`. It passes when the test
  started, the recorded exit status is non-zero and no `OK` summary appears. A
  hang ended by the bound (exit 124) is fail-closed and passes. Locally, serial
  runs exit 3 at once. unittest-parallel 1.8.6 waits on the lost task until the
  bound fires, pooled and unpooled, at module and class level. The macos-15
  image's `timeout` availability is not verified here; if the workflow bounds
  the step another way, it must still write the exit status.

The copies are made in empty directories under `RUNNER_TEMP`
(`control-controls/`, `control-crash/`), outside the checkout, and the
workflow never removes them. After both control runs, the job records the
checkout's `git status --porcelain=v1 --untracked-files=all` in each control
run's `git-status.txt`. A control run that wrote into the checkout therefore
shows up there and fails its arm.

## Run it

From a checkout root, with the interpreter and installed packages of the arm
(module-level skips and import errors become ids of their own):

```sh
D=blueprints/convergence-practice/macos-suite-parallelism-20261003
python3 $D/ids.py > inventory-trial.txt          # summary on stderr
python3 $D/compare.py --results results --inventory-base inventory-base.txt \
  --inventory-trial inventory-trial.txt --expected-sha "$PR_HEAD_SHA" \
  --out result.json --summary-md summary.md
python3 -m unittest discover -s $D -p test_compare.py
python3 -m unittest discover -s $D -p 'test_*.py'  # adds test_b1_failure_mode.py
```

Pass `--expected-sha` with the PR head SHA. Without it the most common
`checkout_sha` stands in, which is weaker than asserting the frozen corpus.
`blueprints/` is not a package, so production CI never runs
`test_compare.py` or `test_b1_failure_mode.py`. The trial workflow runs
`test_compare.py` and `ids.py` on ubuntu-24.04 only, with the image's
`python3`. The inventory job runs `ids.py`, and the compare job runs
`test_compare.py` before `compare.py`. `compare.py` never runs on macOS, and
one Linux inventory serves both runners. `test_b1_failure_mode.py` runs
locally only.

Local integration evidence, not a hosted run: U2 tested this oracle on
CPython 3.13.16 and 3.14.4, and the integrator on 3.13.16 and a uv-managed
3.12.3 (the version of the ubuntu-24.04 image's `python3`). The fix round of
2026-10-03 re-ran `test_compare.py` on 3.13.16 and 3.12.3, and so did the
second fix round, with `test_b1_failure_mode.py`.

`compare.py` exits 0 when `result.json` was written (the outcome is inside it)
and 2 for unusable inputs. `result.json` lists every run's eligibility and reasons,
mismatches, count deltas against S and timing. It also lists the controls, the
flaky ids, the per-arm median, minimum and maximum with both speed ratios, the
id-mapping check and the verdict for every preregistered OS (`no verdict`,
reason `no run directory`, for an OS none of whose runs arrived).

## Fixtures

`make_fixtures.py` produced `fixtures/` on 2026-10-03 from real runs of the
controls on a WSL2 x86_64 host with CPython 3.13.16. It used a scratch
virtualenv with unittest-parallel 1.8.6 and coverage 7.16.2 (cp313 manylinux
wheel sha256 `4358b9c8c0125b460407f3017c6cce8156e904b32772c5630d27112f52bdbfe5`),
installed with `--only-binary=:all: --require-hashes`. Its installed `main.py`
has sha256 `ae1bf2f5831ec21c8dc80f1f2b62dd85530b0f4751cff109c854ca33faa0b179`,
byte-identical to `bda5d77`. Every configuration ran with that one interpreter.
The crash bound was 20 s locally.

Logs are sanitized: the scratch root, virtualenv, interpreter and home
prefixes became `<scratch>`, `<venv>`, `<python>` and `<home>`. The mutated
copies are their sources with the edits declared in `index.json`, which
`test_compare.py` re-applies. Covered edits: a dropped line, serial and
parallel; a changed outcome, self-consistent and unbalanced; a truncated log;
a missing Ran line; an extra id.

Regenerate with
`python3 make_fixtures.py --parallel-python <venv>/bin/python --work <scratch>`,
where `<scratch>` is an empty or absent directory outside the checkout.
`make_fixtures.py` refuses a `--work` at or inside the checkout root, and a
non-empty one. It creates every run directory itself and deletes none.

## Local checks recorded on 2026-10-03

These are local integration evidence:

- `ids.py` on the base commit `56473e4b` listed 9,800 unique ids
  (`countTestCases()` 9,800, no duplicates, no loader errors). The macOS
  full-suite log of run 37073310931 (push to main at that commit) reports
  `Ran 9800 tests`. Its parsed ids equal the inventory exactly, with zero
  parse anomalies.
- Four real macOS full-suite logs (runs 36946376402, 37042100443,
  37073310931, 37075955141; 9,483 to 9,829 tests, one with a failing
  subtest) parse with zero anomalies. Started tests equal `Ran N` and the
  outcome counts equal the status lines.
- Thirty real unittest-parallel runs of two generated noisy suites (720 and
  1,440 tests; module, class and test level; 3, 4 and 8 workers; pooled and
  unpooled) parse with zero anomalies. Each one's records equal the serial
  run's. Those runs exposed two shapes the parser now handles: the separately
  written subtest status (rule 5), and worker output that absorbs the blank
  line before the error report.

## Limits

- Class-level arms (P3C, L4C) change module-fixture semantics.
  unittest-parallel runs each class suite with a fresh result (main.py:294-301,
  :328-344). CPython ties `setUpModule`/`tearDownModule` to the result's
  previous class and tears the module down at the end of each top-level run
  (suite.py:102-132, :188-202). Both therefore run once per class instead of
  once per module: locally, 3 calls for a module of 3 classes against 1 at
  module level and serially. Thirteen test modules define `setUpModule`.
  Where a module fixture fails or skips, the extra fixture records make the
  run ineligible. Side effects that leave outcomes unchanged are invisible to
  this oracle.
- One `--inventory-trial` serves both OSes. The workflow builds it once, on
  ubuntu-24.04's system CPython 3.12.3 with only the trial lock installed
  (none of the arms' npm pins, zizmor or promotion-gate venv), and applies it
  to the macOS arms too. Discovery could depend on the platform; the evidence
  that it does not is the base-commit check above (the Linux inventory equals
  the set executed on macOS). The first hosted macOS S run decides it for the
  trial head: a platform difference makes every macOS run ineligible, S
  included, so macOS gets no verdict (fail-closed).
- Warning filters differ between S and the parallel arms. With no `-W`
  option, `python3 -m unittest` sets `warnings='default'` (CPython 3.12.3
  `Lib/unittest/main.py:88-92`; 3.13.16 `:87-91`) and applies it with
  `warnings.simplefilter` inside `TextTestRunner.run` (`runner.py:231-234`,
  byte-identical at both tags). unittest-parallel 1.8.6 builds its
  `TextTestRunner` without `warnings=` (`main.py:337-343` at `bda5d77`), so
  the parallel arms run under the interpreter's default filters. S logs may
  therefore carry `DeprecationWarning` and `ResourceWarning` text that the
  parallel logs lack. The parser treats that text as output between records,
  as in the four real macOS full-suite logs above. A test whose outcome
  depends on the active warning filter could differ, and the oracle would
  count that as a mismatch against S. Such a mismatch is triaged against this
  stated cause.
- Three tests failed on macOS only in this repository's CI from 2026-09-25
  to 2026-10-02, as timing, signal or node-suite failures:
  `tests.test_secret_path_guard.K4GuardTests.test_k4_timing` (timing, 2 runs
  on 2026-10-01), the `(signal='SIGQUIT')` subtest of
  `tests.test_credential_run.ProcessTests.test_exit_code_and_signal_propagate`
  (signal, 1 run on 2026-10-02) and
  `tests.test_child_usage_suite.ChildUsageNodeSuite.test_node_suite_passes`
  (node suite, 4 runs on 2026-09-30). The source is plan W2's measurement of
  2026-10-03 (read-only REST reads, not re-measured here): 30 macOS-only
  failures among 1,025 pull-request head SHAs, with the failing tests named
  for 15 of them. All three ids are in the trial head's inventory. Nothing
  excludes them in advance: the only exclusion is the flaky-id rule (records
  that differ among the eligible S repeats), so a mismatch on one of them
  still makes its run ineligible under the zero-tolerance rule, and it is
  triaged against this history.
- Receipts committed from the trial must not contain the runner's home
  directory paths, which appear in tracebacks on both OSes:
  `scripts/validate.py` rejects home paths, so sanitize logs before
  committing them.
- A bare `skipped` fixture status after an expected failure or unexpected
  success cannot be named (no error block lists skips). The counts and the
  inventory check then make the run ineligible (fail-closed).
- If two subtests on different workers both wait for a separately written
  status, the statuses are reattached first-come first-served.
