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
| `make_fixtures.py` | Regenerates `fixtures/` from real local runs of the controls. |
| `fixtures/` | Sanitized real control logs (`real/`), mutated copies (`mutated/`), `index.json`, `inventory-controls.txt`. |

## Arms

Baseline arm per OS is `S`, the production command. Each arm's command must
match exactly (`compare.py` parses `meta.json` `command`; any other argument
makes the run ineligible).

| OS | Arm | Command |
|---|---|---|
| macos-15 | S | `python3 -m unittest -v` |
| macos-15 | P3 | `python3 -m unittest_parallel -j 3 --level module -v` |
| macos-15 | P3F | P3 plus `--disable-process-pooling` |
| macos-15 | P3C | `python3 -m unittest_parallel -j 3 --level class -v` |
| macos-15 | P4 | `python3 -m unittest_parallel -j 4 --level module -v` |
| ubuntu-24.04 | S | `python3 -m unittest -v` |
| ubuntu-24.04 | L4 | `python3 -m unittest_parallel -j 4 --level module -v` |
| ubuntu-24.04 | L4F | L4 plus `--disable-process-pooling` |
| ubuntu-24.04 | L4C | `python3 -m unittest_parallel -j 4 --level class -v` |

`S` may add `--durations N` (the plan's diagnostic); the parser skips that
table. Record `command` without redirections; a leading `timeout 300` is
tolerated.

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

## Eligibility (per arm-run; reported, never silently dropped)

An arm-run is ineligible when any of these hold:

- `log.txt`, `exit-code.txt` or `meta.json` is missing or invalid.
- `meta.json` disagrees with the directory name.
- The command differs from the arm's preregistered flags.
- `checkout_sha` differs from the frozen corpus (`--expected-sha`, else the most common value).
- `python_version` differs from S on that OS.
- The log is truncated or has no Ran line, or a self-consistency check above fails.
- The exit status disagrees with the status line.
- The header is missing (parallel) or present (serial), or reports a worker count other than `min(suites, jobs)`.
- The executed ids are not exactly the trial inventory. Skipped tests must
  still appear; tests behind a failed or skipped `setUpClass` or
  `setUpModule` count as accounted.
- Its records differ from the S baseline of the same OS outside the flaky ids.

Flaky ids: ids (fixture keys included) whose records differ among the
eligible S repeats of an OS. They are listed in `result.json`
(`verdicts.<os>.baseline.flaky_ids`) and excluded from mismatch counting. S
runs that disagree on `python_version` void that OS.

Id mapping: `tests/test_native_maintenance.py` loads six classes through
`load_tests` under bare module names. The trial's fix gives their ids a dotted
prefix, so `--inventory-base` (production) and `--inventory-trial` must differ
only by that rewrite. The rewrite must be a bijection with one prefix per base
module and exactly six classes; identical inventories also pass. Arms are
compared on trial ids.

## Decision rule (preregistered)

An arm is eligible when all of these hold:

- It has at least three runs (`--min-repeats`).
- Every one of its runs is eligible.
- Its controls run and crash control run on that OS passed.

The S arm must be eligible too, or the OS gets no verdict. Then:

1. Take the fastest eligible parallel arm by median `step_seconds`.
2. Adopt it only if its median is at most 0.60 times the S median and its
   maximum is at most 0.75 times the fastest S run. Otherwise reject, with no
   fall-through to a slower arm.
3. If the adopted arm is P3 (L4), take P3F (L4F) instead when that arm is
   eligible, meets step 2 and its median is at most 1.10 times the pooled median.

The plan states this preference for P3F; applying it to L4F is this oracle's
reading.

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

Afterwards the workflow removes the copies before its `git status --porcelain` check.

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
```

Pass `--expected-sha` with the PR head SHA. Without it the most common
`checkout_sha` stands in, which is weaker than asserting the frozen corpus.
`blueprints/` is not a package, so production CI never runs
`test_compare.py`. The trial workflow should run it, and `ids.py`, on both
runners (this oracle was tested locally on CPython 3.13.16 and 3.14.4, not
3.12).

`compare.py` exits 0 when `result.json` was written (the outcome is inside it)
and 2 for unusable inputs. `result.json` lists every run's eligibility and reasons,
mismatches, count deltas against S and timing. It also lists the controls, the
flaky ids, the per-arm median, minimum and maximum with both speed ratios, the
id-mapping check and the verdict per OS.

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
`python3 make_fixtures.py --parallel-python <venv>/bin/python --work <scratch outside the checkout>`.

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
- One `--inventory-trial` serves both OSes. Discovery could depend on the
  platform; the evidence that it does not is the base-commit check above
  (the Linux inventory equals the set executed on macOS). Generate the
  inventory on the runner after installing the lock.
- Receipts committed from the trial must not contain the runner's home
  directory paths, which appear in tracebacks on both OSes:
  `scripts/validate.py` rejects home paths, so sanitize logs before
  committing them.
- A bare `skipped` fixture status after an expected failure or unexpected
  success cannot be named (no error block lists skips). The counts and the
  inventory check then make the run ineligible (fail-closed).
- If two subtests on different workers both wait for a separately written
  status, the statuses are reattached first-come first-served.
