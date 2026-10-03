# Suite-shards trial (2026-10-03)

North-star action served: a shorter, still fail-closed required test job, so that every pull request that moves
the stack toward the north star reaches a verdict sooner, without changing which tests run or how their outcomes
are judged.

This is the second preregistered trial for the two whole-suite jobs, `validate` (`.github/workflows/validate.yml`,
ubuntu-24.04) and `validate-macos` (`.github/workflows/adoption-bootstrap.yml`, macos-15). The first trial
(unittest-parallel 1.8.6, draft pull request #646, run 37109532421) failed its rule on Linux because that runner
pickles live `TestCase` instances, and never ran on macOS. This trial runs the existing suite as N concurrent
single-process shards inside one job, with GitHub's native parallel steps, and every shard is the stock
`python3 -m unittest -v <modules>`: nothing is pickled, `load_tests` and dynamically built classes load as they do
in production. It adopts nothing; a passing result leads only to a separate, reviewed adoption pull request.

Evidence class of everything in this directory so far: local integration evidence and synthetic fixtures (real
local runs), not a GitHub-hosted run and not upstream acceptance.

| File | Purpose |
|---|---|
| `make_shards.py` | Frozen generator of the shard lists: longest-processing-time-first over test files, from `weights.json`. |
| `weights.json` | Frozen per-file weights (233 numbers, seconds) from one local serial run at `d2777ee7`. Balancing input only. |
| `inventory.py` | The fail-closed inventory gate run by each workflow's inventory job: parity, no duplicates, no import failure, every file in one list. |
| `record.py` | The workflows' recorder: runtime, clock start and stop, per-step probe, metadata and checkout status. |
| `logparse.py` | The first trial's log parser, copied unchanged (provenance and block hashes in its header). |
| `compare.py` | The oracle: eligibility of every run, the controls, the preregistered decision; `result.json`, `summary.md`, `checkout-status.json`. |
| `controls/test_ctl_*.py` | The four control modules (pass, fail, `os._exit(3)`, hang); never placed under `tests/`. |
| `test_compare.py` | Tests of everything above and of the two workflows' structure. |
| `make_fixtures.py` | Regenerates `fixtures/` from real local runs of a small fixture suite and of the controls. |
| `fixtures/` | Sanitized real logs, the fixture inventory and lists, probes and `index.json` (each file's sha256). |
| `experiment.json` | The preregistration (status `planned`), freezing every file above by sha256. |

The workflows are `.github/workflows/suite-shards-trial-linux.yml` and `.github/workflows/suite-shards-trial-macos.yml`,
and the decision record is `docs/decisions/2026-10-03-suite-shards-trial.md`.

## Arms

| OS (runner) | Arm | What runs in the timed phase |
|---|---|---|
| ubuntu-24.04 (4 vCPUs, the image's system CPython 3.12) | S | `python3 -m unittest -v`, one step (the production command of `validate` plus `-v`) |
| ubuntu-24.04 | G4 | 4 shard steps in one `parallel:` group, each `python3 -m unittest -v <its modules>`; every test file in one shard |
| ubuntu-24.04 | G4T | the same 4 steps without `tests.test_secret_path_guard`, then a serial tail step that runs that module alone |
| macos-15 (3 cores, `actions/setup-python` 3.13) | S | `python3 -m unittest -v`, one step (the production command of `validate-macos`) |
| macos-15 | G3 | 3 shard steps in one `parallel:` group |
| macos-15 | G3T | 3 shard steps without `tests.test_secret_path_guard`, then the serial tail |

Each arm runs three times (`repeat` 1 to 3, `fail-fast: false`). Linux runs at most two serial and two sharded jobs
at once (`max-parallel: 2` each, four in total); macOS at most one of each (`max-parallel: 1` each), so with the
control job no more than three of the plan's five macOS slots are held. The serial and sharded arms are separate
jobs, rather than one matrix with conditioned steps, so that no step inside a `parallel:` group needs an `if:` (the
workflow-syntax reference documents none there) and S times exactly the production step.

Every arm installs what its production job's suite needs. Linux: validate.yml's four suite-environment steps,
run bodies unchanged (the zizmor lock, the promotion-gate venv and the two npm pins). macOS: `actions/setup-python`
3.13 and the two npm pins, which `validate-macos` does not install: it is a recorded gap of the runtime tripwires in
`tests/test_shell_parser_ci.py` and `tests/test_landscape_sweep_skills.py`, and the trial's jobs are not.

The test phase's length (`step_seconds`) runs from a `Start the clock` step to a `Stop the clock` step
(`if: always()`): the S step alone, or the group plus the tail. `record.py` reads `time.monotonic_ns()` in both
steps (a system-wide clock on both OSes, see its header) and also keeps the wall-clock difference.

## Shard lists (built at run time)

The inventory job of each workflow runs `inventory.py`, which calls `make_shards.py` on the test files of the checked
out head, so the lists always cover the head that runs. Rules (`make_shards.py`):

- Units are test files (`tests/test_*.py`, as `tests.<stem>`), never id prefixes: `tests/test_native_maintenance.py`
  adds classes through `load_tests` under bare module names (for example `application_portability_tests`), and
  those ids belong to the file that loads them.
- Longest-processing-time-first: files by decreasing weight (ties by name), each to the least-loaded shard (ties to
  the lowest index), in whole milliseconds, so the lists depend only on the file set and `weights.json`.
- A file missing from `weights.json` takes the mean weight (5,450 ms) and is assigned like any other, so a new test
  file can never drop out. At base `9b0b8d6d` one file is new since the weights were measured:
  `tests.test_catalog_freshness_runtime` (locally 99 tests in 0.23 s).
- A shard may never be empty (`python3 -m unittest -v` without a module would run the whole suite by discovery);
  every shard step also refuses an empty list.

## Inventory gate (fail-closed)

`inventory.py` exits 1, and so fails the inventory job and skips every arm, unless all of these hold:

1. **Parity.** Loading every `tests/test_*.py` by name (`loadTestsFromName`, which calls `load_tests` with pattern
   `None`) gives exactly the ids of discovery (`discover(".", "test*.py", None)`, what `python3 -m unittest`
   collects; CPython `Lib/unittest/main.py` `_do_discovery` at v3.13.16 lines 231-234, v3.12.3 lines 242-245;
   `Lib/unittest/loader.py` `loadTestsFromModule` at v3.13.16 lines 100-117, v3.12.3 lines 97-113).
2. No id is loaded twice (by two files, twice by one file, or twice by discovery).
3. No import failure: no loader error and no loader-made id in either load, and neither child interpreter fails.
4. Every test file is in exactly one shard list or the tail of each arm, read back from the written files.

The macOS workflow's inventory job runs on ubuntu-24.04 with `actions/setup-python` 3.13 from the same pin as its
arms (the same Python line, another platform build), so that a stalled macOS queue cannot hold it.

## Run directory contract (workflows to `compare.py`)

`<os>-<arm>-r<N>/` per timed run and `<os>-controls/` for the control run, merged into one results tree:

- `runtime.json` (`run_attempt` from `GITHUB_RUN_ATTEMPT`, image, architecture, CPU count, interpreter),
  `meta.json` (`os`, `arm`, `repeat`, `checkout_sha`, `python_version`, `platform`, `runner_image`, `job_status`),
  `timing.json` (`step_ns`, `wall_ns`, the clock's name), `git-status.txt`
  (`git status --porcelain=v1 --untracked-files=all` after the run) and `foreground.probe.json`.
- S: `log.txt`, `exit-code.txt`, `command.txt`.
- G and GT: `shard-<i>.txt` (the list it ran, copied from the inventory artifact), `shard-<i>.log`, `shard-<i>.exit`,
  `shard-<i>.command`, `shard-<i>.probe.json`, `tail.txt`, and for GT `tail.log`, `tail.exit`, `tail.command`,
  `tail.probe.json`.

A probe records, inside the step, the interpreter, whether SIGINT and SIGQUIT are ignored, and whether each of five
exported variables is set (names only, never values).

## Eligibility (preregistered)

Logs are parsed by `logparse.py`. A shard's log has the grammar of the serial whole-suite log, so the first trial's
serial parser applies unchanged. Skip reasons are not compared (the parser reads `skipped '<reason>'` as `skipped`).

**S run.** Eligible when its log has a complete summary and no parse anomaly, its exit status agrees with its
status line (zero versus non-zero), its executed ids (plus ids behind a failed `setUpClass` or `setUpModule`) are
exactly the inventory with each id once, its command is exactly `python3 -m unittest -v`, `git-status.txt` exists
and is empty, `run_attempt` is `"1"`, `checkout_sha` is the pull request head, its job was not cancelled, and its
step time is valid (positive, and the monotonic and wall-clock lengths agree within 5 s or 1 %). The eligible S runs
must share one Python version.

**G and GT run.** Eligible when every shard log (and the tail) meets the S log rules, each command is exactly
`python3 -m unittest -v` followed by its list, the run's lists equal the inventory artifact's, each log's executed
ids equal its modules' ids, the union over all logs is exactly the inventory with each id once (a module in two
shards or an id that never started is ineligible), the multiset of `(kind, key, outcome)` records equals the first
eligible S run outside the flaky ids, every step's probe shows the job's Python version, which equals S's, and the
checkout, attempt, head, job status and step time rules hold.

**Flaky ids** are ids whose records differ among the eligible S runs; they are listed and excluded from the
comparison. The inventory artifact must record a passed gate, and its lists must equal what `make_shards.py` gives
for its test files and the frozen weights, or the OS gets no verdict.

## Controls (preregistered)

Per OS one control job runs the arms' shard step body, in one `parallel:` group, on the four control modules copied
alone into an empty directory: shard 0 passes (`Ran 2`, `OK`, exit 0), shard 1 has one failing test
(`FAILED (failures=1)`, exit 1), shard 2 ends its process with `os._exit(3)` (exit 3, no summary), and shard 3 sleeps
300 s under `timeout-minutes: 1` (it must be stopped: no exit status written, no summary). The job is expected to
fail; `controls-check` (`needs: controls`, `if: always()`) runs `compare.py controls` and fails unless the job's result
is `failure` and every shard behaved as listed, with the exact command, the foreground step's Python version in
every background step, and `SUITE_SHARDS_ENV_PROBE`, exported through `GITHUB_ENV` by an earlier step, set in every
background step. Whether background steps start with SIGINT or SIGQUIT ignored is recorded and reported, not
judged: a shell's background job starts its children so, which skipped a SIGQUIT subtest in the local preflight, and
any such effect on the suite shows up as a record mismatch in the arms.

## Decision rule (preregistered, per OS, fixed before any hosted run)

1. An arm is eligible when it has three runs, every run is eligible, and (for G and GT) the OS controls passed.
2. S must be eligible, or the OS gets **no verdict**.
3. No eligible sharded arm gives **reject**.
4. Otherwise take the eligible sharded arm with the smaller median step time (a tie goes to G, the arm without a
   tail). **Adopt** it only if its median is at most 3/5 of the S median and its slowest run at most 3/4 of the
   fastest S run, both compared as exact fractions of nanoseconds with no rounding before the comparison;
   otherwise **reject**, with no fall-through to the other arm.
5. A cancelled or skipped job, a missing run directory, a job status `cancelled` or a missing control run makes the
   OS **incomplete**, which is recorded as such and is never a rule outcome. A failed inventory gate, or an unusable
   inventory artifact, gives no verdict.

Every OS is listed in `result.json` and `summary.md`; each workflow measures its own OS, and the other OS is listed
with `no verdict` and the reason `no run directory`.

## Trigger, repetition and re-runs

Each workflow runs only on `pull_request` `opened` and `reopened`, with a paths filter on its own file. A push to the
branch (`synchronize`) never re-runs the trial, so the observed record cannot land on the trial branch by accident;
it goes to a separate records pull request. To repeat the trial, close and reopen the draft pull request. A job
re-run voids its arm-run (`run_attempt` must be `"1"`), and every upload sets `overwrite: false`. The concurrency
group (`cancel-in-progress: false`) keeps one run going: a reopen during a run queues one run, which starts unattended
when the first ends; a further reopen replaces the queued run, which then shows as cancelled.

## Run it

```sh
D=blueprints/convergence-practice/suite-shards-trial-20261003
python3 $D/inventory.py --os ubuntu-24.04 --root . --weights $D/weights.json --out inventory
python3 -m unittest discover -s $D -p "test_*.py"
python3 $D/compare.py verdict --results results --inventory inventory --expected-sha "$PR_HEAD_SHA" \
  --os ubuntu-24.04 --needs needs.json --out result.json --summary-md summary.md \
  --checkout-status checkout-status.json
python3 $D/compare.py controls --dir results/ubuntu-24.04-controls --os ubuntu-24.04 --job-result failure
python3 $D/make_fixtures.py --work <empty scratch directory outside the checkout>
```

`compare.py verdict` exits 0 when `result.json` was written (the outcome is inside it) and 2 for unusable arguments.

## Local evidence recorded on 2026-10-03 (local integration, not a hosted run)

- **Coordinator's whole-suite preflight** at `d2777ee7` (48-core WSL2 host, CPython 3.13.16; 9,844 ids in 233 files):
  the serial run (`python3 -m unittest -v --durations 0`) took 1,305 s and ended `FAILED (failures=32,
  skipped=1181)`, the 32 failures host-specific; loading every file by name gave exactly the discovery ids. Four
  LPT shards as four concurrent processes took 361 s unpinned and 378 s pinned to 4 cores; three shards pinned to 3
  cores took 487 s; in all three the 9,853 parsed records equalled the serial run's. A first attempt differed only
  because a shell's background job started the shards with SIGINT and SIGQUIT ignored, which skipped a SIGQUIT subtest.
- **The oracle on those real logs** (`serial.log` as S r1, the pinned 4-shard logs as G4 r1, synthetic metadata,
  `--min-repeats 1`, `--skip-list-recompute`): both runs eligible, zero mismatches, no id missing, extra or run twice:
  equal. Negative checks: the true S command (`--durations 0`) makes S ineligible under the command rule, and one
  mutated outcome in a shard is caught by the self-consistency check and by the record comparison.
- **`make_shards.py` against the preflight's lists** (same 233 files): it places the 109 heaviest files of G4 and the
  115 heaviest of G3 exactly as the preflight did; the remaining small files (each at most 298 ms; 7.6 s and 4.6 s in
  all) differ only by tie-breaking between the preflight's float loads and these integer milliseconds, and every
  shard's predicted load is equal within 1 ms. The preflight's equality evidence therefore covers a different
  partition of the small files.
- **`inventory.py` at the trial base `9b0b8d6d`**: 234 test files, 9,943 ids, parity true, no problem, identical
  output on CPython 3.13.16 and a bare 3.12.3; predicted seconds per shard: G4 318.9 x 4; G4T 301.1 x 4 plus a
  71.0 s tail; G3 425.1 x 3; G3T 401.5 x 3 plus 71.0 s.
- **`test_compare.py`**: 62 tests OK on CPython 3.13.16 and the bare 3.12.3.

## Limits

- The preflight ran on another machine (48 cores), another CPython patch release and an earlier base; hosted runners
  have 4 vCPUs (Linux) and 3 cores (macOS). Hosted macOS has never run this suite in shards.
- n = 3 per arm. Hosted wall-clock time varies with neighbours and image updates; three repeats bound this but do
  not remove it.
- Whether a hosted runner starts background steps with SIGINT or SIGQUIT ignored, whether `GITHUB_ENV` exports and
  `GITHUB_PATH` reach them, and whether `timeout-minutes` applies to them are not documented on the pages read; the
  controls and every shard's probe measure them, and the record comparison judges their effect.
- zizmor 1.30.1 marks its support for parallel steps as experimental (its `docs/usage.md` at v1.30.1, "Parallel
  steps"), so its audit coverage inside the groups is not established; the shard steps are plain `run:` steps with no
  expression in their scripts. actionlint 1.17.0 parses the groups and shellchecks their scripts.
- The macOS inventory is built on ubuntu-24.04. A platform-dependent id would make the macOS S runs ineligible (their
  executed ids must equal the inventory), which gives no verdict, not a wrong verdict.
- Skip reasons are not compared. Side effects that leave outcomes unchanged are invisible to the oracle.
- `tests.test_secret_path_guard.K4GuardTests.test_k4_timing` is timing-bound (30 to 60 s serially) and failed under
  class-level parallel load in the first trial; G4T and G3T keep its module out of the parallel group, G4 and G3 do not.
- A shard that hangs is stopped by its step limit (25 min on Linux, 40 min on macOS) and makes its run ineligible.
