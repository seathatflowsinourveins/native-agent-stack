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

Evidence class of everything in this directory so far: local integration evidence (real local runs of the suite),
synthetic fixtures (real local runs of a fixture suite and of the controls, which the oracle's tests use) and source
review, not a GitHub-hosted run and not upstream acceptance.

| File | Purpose |
|---|---|
| `make_shards.py` | Frozen generator of the shard lists: longest-processing-time-first over test files, from `weights.json`. |
| `weights.json` | Frozen per-file weights (233 numbers, seconds) from one local serial run at `d2777ee7`. Balancing input only. |
| `inventory.py` | The fail-closed inventory gate run by each workflow's inventory job: parity, no duplicates, no import failure, every file in one list. |
| `record.py` | The workflows' recorder: runtime, clock start and stop, per-step probe, metadata with each step's outcome, the hang control's heartbeat, checkout status. |
| `logparse.py` | The first trial's log parser, copied unchanged (provenance and block hashes in its header). |
| `compare.py` | The oracle: eligibility of every run, the controls, the preregistered decision; `result.json`, `summary.md`, `checkout-status.json`. |
| `controls/test_ctl_*.py` | The four control modules (pass; fail after 90 s; `os._exit(3)` after 120 s; hang with a heartbeat); never placed under `tests/`. |
| `test_compare.py` | Tests of everything above and of the two workflows' structure. |
| `make_fixtures.py` | Regenerates `fixtures/` from real local runs of a small fixture suite and of the controls (about two minutes). |
| `fixtures/` | Sanitized real logs, the fixture inventory and lists, probes, the hang control's heartbeat and `index.json` (each file's sha256). |
| `experiment.json` | The preregistration (status `planned`), freezing every file above by sha256. |

The workflows are `.github/workflows/suite-shards-trial-linux.yml` and `.github/workflows/suite-shards-trial-macos.yml`,
and the decision record is `docs/decisions/2026-10-03-suite-shards-trial.md`.

## Arms

| OS (runner) | Arm | What runs in the timed phase |
|---|---|---|
| ubuntu-24.04 (4 vCPUs, the image's system CPython 3.12) | S | `python3 -m unittest -v`, one step (the production command of `validate` plus `-v`) |
| ubuntu-24.04 | G4 | 4 shard steps in one `parallel:` group, each `python3 -m unittest -v <its modules>`; every test file in one shard |
| ubuntu-24.04 | G4T | the same 4 steps without `tests.test_secret_path_guard`, then a serial tail step that runs that module alone |
| macos-15 (3 cores, CPython 3.13.15 from `actions/setup-python`) | S | `python3 -m unittest -v`, one step (the production command of `validate-macos`) |
| macos-15 | G3 | 3 shard steps in one `parallel:` group |
| macos-15 | G3T | 3 shard steps without `tests.test_secret_path_guard`, then the serial tail |

Each arm runs three times (`repeat` 1 to 3, `fail-fast: false`). Linux runs at most two serial and two sharded jobs
at once (`max-parallel: 2` each, four in total); macOS at most one of each (`max-parallel: 1` each), so with the
control job the macOS workflow holds no more than three of the plan's five macOS slots. The same opening also starts
three macOS jobs of `adoption-bootstrap.yml` (see "Limits"). The serial and sharded arms are separate
jobs, rather than one matrix with conditioned steps, so that no step inside a `parallel:` group needs an `if:` (the
workflow-syntax reference documents none there) and S times exactly the production step.

Every arm installs what its production job's suite needs. Linux: validate.yml's four suite-environment steps,
run bodies unchanged (the zizmor lock, the promotion-gate venv and the two npm pins). macOS: CPython 3.13.15 from
`actions/setup-python` (see "Limits") and the two npm pins, which `validate-macos` does not install: it is a recorded
gap of the runtime tripwires in `tests/test_shell_parser_ci.py` and `tests/test_landscape_sweep_skills.py`, and the
trial's jobs are not.

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

A child interpreter stopped from outside, by SIGKILL, SIGTERM, SIGINT or SIGHUP (the kernel's out-of-memory killer, a
runner that stops a job), is an execution problem, not a finding: `report.json` lists it under `execution_problems`,
with `parity` null, and the gate still fails, so no arm runs, but the run is incomplete, not a failed gate (rule 5).
Any other failure of a child (a non-zero exit, an end by another signal, output that is not JSON) is a finding under 3.

The macOS workflow's inventory job runs on ubuntu-24.04 with CPython 3.13.15 from the same `actions/setup-python` pin
as its arms (the same release, another platform build), so that a stalled macOS queue cannot hold it.

## Run directory contract (workflows to `compare.py`)

`<os>-<arm>-r<N>/` per timed run, uploaded by its job as the artifact `arm-<os>-<arm>-r<N>`, and `<os>-controls/`
for the control run, uploaded as the artifact `controls`. The compare job downloads them without merging (one
directory per artifact: `results/arm-<run name>/<run name>/`, and `results/controls/<os>-controls/`).
`compare.py` counts a run directory only from the artifact whose name gives it: any other top-level entry is
ignored and listed in `result.json`, an arm artifact that holds anything besides its run directory makes that run
ineligible, and the control artifact must hold exactly `<os>-controls`. When only one arm artifact exists,
`actions/download-artifact` extracts it without its directory (`src/download-artifact.ts` at `3e5f45b2`, lines
186-195); that bare directory is not attributed, and the missing runs make the OS incomplete. Each directory holds:

- `runtime.json` (`run_attempt` from `GITHUB_RUN_ATTEMPT`, image, architecture, CPU count, interpreter),
  `meta.json` (`os`, `arm`, `repeat`, `checkout_sha`, `python_version`, `platform`, `runner_image`, `job_status`,
  and `steps`: the outcome and conclusion of every step with an `id`, from the workflow's `toJSON(steps)`),
  `timing.json` (`step_ns`, `wall_ns`, the clock's name), `git-status.txt`
  (`git status --porcelain=v1 --untracked-files=all` after the run) and `foreground.probe.json`.
- S: `log.txt`, `exit-code.txt`, `command.txt`.
- G and GT: `shard-<i>.txt` (the list it ran, copied from the inventory artifact), `shard-<i>.log`, `shard-<i>.exit`,
  `shard-<i>.command`, `shard-<i>.probe.json`, `tail.txt`, and for GT `tail.log`, `tail.exit`, `tail.command`,
  `tail.probe.json`.
- Controls: the four shards' files as for G, and `heartbeat.json` (the hang control's heartbeat, below).

A probe records, inside the step, the interpreter, whether SIGINT and SIGQUIT are ignored, the step's start as
`time.monotonic_ns()` and `time.time_ns()`, and whether each of seven variables is set (names only, never values):
the four that validate.yml's suite-environment steps export through `GITHUB_ENV` (`CHILD_USAGE_SHELL_PARSER`,
`LANDSCAPE_SWEEP_SKILLS_YAML`, `PROMOTION_GATE_PYTHON`, `REQUIRE_PROMOTION_GATE_VENV`), the control job's
`SUITE_SHARDS_ENV_PROBE`, and `GITHUB_ACTIONS` and `CI`, which the runner sets.

## Eligibility (preregistered)

Logs are parsed by `logparse.py`. A shard's log has the grammar of the serial whole-suite log, so the first trial's
serial parser applies unchanged. Skip reasons are not compared (the parser reads `skipped '<reason>'` as `skipped`).

**S run.** Eligible when its log has a complete summary and no parse anomaly, its exit status agrees with its
status line (zero versus non-zero), its executed ids (plus ids behind a failed or skipped `setUpClass` or
`setUpModule`, which unittest never runs) are exactly the inventory with each id once, its command is exactly
`python3 -m unittest -v`, `git-status.txt` exists and is empty, `run_attempt` is `"1"`, `checkout_sha` is the pull
request head, its job was not cancelled, and its step time is valid (positive, and the monotonic and wall-clock
lengths agree within 5 s or 1 %).

**G and GT run.** Eligible when every shard log (and the tail) meets the S log rules, each command is exactly
`python3 -m unittest -v` followed by its list, the run's lists equal the inventory artifact's, each log's executed
ids equal its modules' ids, the union over all logs is exactly the inventory with each id once (a module in two
shards or an id that never started is ineligible), the multiset of `(kind, key, outcome)` records equals the first
eligible S run outside the flaky ids, every step's probe shows the job's Python version, and the checkout, attempt,
head, job status and step time rules hold.

**Flaky ids** are ids whose records differ among the eligible S runs; they are listed and excluded from the
comparison. The inventory artifact must record a passed gate, and its lists must equal what `make_shards.py` gives
for its test files and the frozen weights, or the OS gets no verdict.

## Controls (preregistered)

Per OS one control job runs the arms' shard step body, in one `parallel:` group, on the four control modules copied
alone into an empty directory. Each control step has an `id` (`control-0` to `control-3`), and the job's finish step
records every step's own outcome from the steps context (`toJSON(steps)`), so that no failure can hide behind
another shard's:

| Step | Control | Expected |
|---|---|---|
| `control-0` | `test_ctl_pass` | `Ran 2`, `OK`, exit 0, at once; step outcome `success` |
| `control-3` | `test_ctl_hang`: a 300 s test under `timeout-minutes: 1`, appending `<monotonic ns> <parent pid>` to a heartbeat file every second | stopped at its limit: no exit status written, no summary; step outcome `failure` |
| `control-1` | `test_ctl_fail`: one test fails after 90 s | `FAILED (failures=1)`, a non-zero exit; step outcome `failure` |
| `control-2` | `test_ctl_crash`: the process ends itself with `os._exit(3)` after 120 s | exit 3, no summary; step outcome `failure` |

Control shards 1 and 2 fail only after control shard 3's 1-minute limit, and 2 only after 1 has failed, so both must
outlive the stop of a sibling step and a sibling's failure to write their exit statuses (checks 4 and 5 make sure of
it). The job is expected to fail; `controls-check` (`needs: controls`, `if: always()`) runs `compare.py controls` and
fails unless:

1. the job's result is `failure`, and the control artifact holds exactly `<os>-controls`;
2. every shard behaved as listed, with the exact command, and each step's own outcome is `success`, `failure`,
   `failure`, `failure` as listed (a recorded wrong outcome fails the controls; an unrecorded one is never evidence of
   failure: when any of the four control steps' outcomes is unrecorded, no recorded one is wrong and every other
   expectation holds, the controls are **unmeasurable**, because the steps context carried no outcome for those
   background steps: the check still fails, and the OS gets no verdict, not reject; see "Decision rule");
3. every background step ran the foreground step's Python version and saw `SUITE_SHARDS_ENV_PROBE`, exported through
   `GITHUB_ENV` by an earlier step;
4. the four steps started together: their probes' monotonic timestamps lie within 15 s. The hang step is stopped at
   most 70 s after its start (the 60 s limit, then SIGINT, up to 7.5 s, SIGTERM, up to 2.5 s and a kill, from the
   runner source below), so the failing control (90 s) is still running at that stop and the crashing control (120 s)
   at the failing control's failure;
5. the hang control's step was stopped at least 50 s after its probe (the 60 s limit less 10 s for the heartbeat
   interval and the step's start-up: the step was not stopped early) and before the failing control's probe plus 90 s
   (before any sibling could fail, so the 1-minute limit stopped it). The stop is the first heartbeat with another
   parent pid (the step's shell ended while the test process lived on) or, when the parent pid never changed, the
   process's last heartbeat (it ended with its shell); a process that kept its parent and still beat when the group
   ended fails this check, since nothing then shows the stop. And the finish step, which runs only after the whole
   group ended, began less than 240 s after the hang step's probe (the group did not wait for the 300 s sleep). Its
   expected value is about 120 s, set by the crashing control.

Reported, not judged: whether background steps start with SIGINT or SIGQUIT ignored (a shell's background job starts
its children so, which skipped a SIGQUIT subtest in the local preflight; any such effect on the suite shows up as a
record mismatch in the arms), and whether the hang control's test process outlived its step (its parent pid changed,
or its heartbeat still advanced when the finish step read it again 3 s later). The runner source signals only a
stopped step's own process: on a timeout `ProcessInvoker.cs` (actions/runner v2.337.0, `397b032c`, lines 443-465 and
855-869) sends SIGINT to the step's shell, waits up to 7.5 s, sends SIGTERM, waits up to 2.5 s and then kills that
one process, with `killProcessOnCancel: false` from `ScriptHandler.cs` line 346, and `BackgroundStepCoordinator.cs`
lines 244-248 give a timed-out background step the result `Failed`. None of these signals is sent to the step's
Python child, so the expected hosted behaviour, unmeasured, is that the stopped step fails while its Python process
lives on, re-parented, until the job ends; the heartbeat measures this, and the time the parent shell ended is the
stop that check 5 judges. A control run whose parallel group never started (the foreground probe step,
`id: foreground`, did not succeed or left no probe) makes the OS incomplete, never a rule outcome. So does a control
step that left no probe, no log and no exit status although the group started, which only a runner fault does (each
step's script writes its probe first, and its log and exit status even when its command fails), its recorded outcome
included, unless what the steps that ran recorded shows wrong behaviour (then the controls fail); checks 4 and 5 then
judge only the steps that ran (`result.json` `controls.<os>.lost_steps`).

## Decision rule (preregistered, per OS, fixed before any hosted run)

1. An arm is eligible when it has three runs, every run is eligible, and (for G and GT) the OS controls passed.
2. S must be eligible and the controls measurable, or the OS gets **no verdict**.
3. No eligible sharded arm gives **reject**.
4. Otherwise take the eligible sharded arm with the smaller median step time (a tie goes to G, the arm without a
   tail). **Adopt** it only if its median is at most 3/5 of the S median and its slowest run at most 3/4 of the
   fastest S run, both compared as exact fractions of nanoseconds with no rounding before the comparison;
   otherwise **reject**, with no fall-through to the other arm.
5. The OS is **incomplete**, which is recorded as such and is never a rule outcome, when any of these holds: a
   re-run (the compare job's own `GITHUB_RUN_ATTEMPT` is not `"1"`, or a run or control directory records a
   `run_attempt` other than `"1"`); a cancelled or skipped job; a missing run directory; a job status `cancelled`, of
   an arm run or of the control run; an unrecorded run attempt (`runtime.json` missing, or without `run_attempt`: a
   setup step failed before the run directory was prepared); a run whose test phase never started (its clock-start
   step, `id: start`, has an outcome other than `success` in `meta.json`, or `timing.json` records no clock start: a
   setup step failed or the job stopped before the test phase); an S run whose test phase started but which left no
   `command.txt`, `log.txt` or `exit-code.txt` (its step lost to a runner fault, "Limits"); arm runs that recorded
   more than one Python version (`meta.json` `python_version`) or machine (`runtime.json` `machine`): the runtime
   changed during the run ("Limits"); a sharded run whose records differ from the S baseline while the arm runs ran on
   more than one runner image (`meta.json` `runner_image`), unless that run is ineligible only through steps that
   never wrote an exit status: the difference may come from the image, which provides the tools and versions that
   tests gate on, not from sharding ("Limits"); a missing control run, or one whose parallel group
   never started; control steps that left no probe, log or exit status although the group started, when no other
   control evidence failed (a runner fault inside the control group, "Controls"); a `controls-check` job that failed
   although the compare job's own check of the same control artifact passed (the check job failed outside its checks:
   a setup step, the download or the runner); an inventory job that failed without a `report.json` that records a
   gate finding (the gate never reported, or its own child interpreter was stopped from outside); an inventory job
   that succeeded although a file of its artifact (`inventory.txt`, `module_ids.json`, `report.json` or a shard list)
   is absent from the compare job's download (a partly downloaded artifact set, a runner fault). The OS gets **no
   verdict** when the inventory gate failed on a finding (`report.json` with `ok` false and at least one problem),
   when the inventory artifact is present but unusable, when S is ineligible, or when the controls are unmeasurable
   (Controls, check 2). The controls fail, which leaves no sharded arm eligible (rule 1), only on recorded evidence
   of wrong behaviour: a recorded wrong step outcome or another failed expectation that the record shows. Without
   such evidence, a control step lost to a runner fault makes the OS incomplete, and unrecorded control step outcomes
   alone make the controls unmeasurable (no verdict). The order: re-runs first; then a failed or
   unreported inventory gate (a finding gives no verdict, anything else incomplete); then the other incomplete
   conditions; then an unusable inventory artifact, an ineligible S or unmeasurable controls (no verdict); then rules
   3 and 4. A shard step that started but never reached its command, or never wrote its exit status, is a failure of
   the sharded arm: its run is ineligible, even when a runner fault caused it. When the rule rejects or adopts while
   passing over a sharded arm that was ineligible only for that reason (every problem of its ineligible runs is a file
   such a step never wrote, its unfinished log or ids that only such a step owned), `result.json` flags the arm under
   `flags`; it also flags arm runs on more than one runner image, whatever the outcome ("Limits"), and beside a sharded
   run whose records differ from the S baseline they also make the OS incomplete (above). A flag itself is reported,
   never judged, and the outcome record must address every flag.

Every OS is listed in `result.json` and `summary.md`; each workflow measures its own OS, and the other OS is listed
as `not measured`, with the reason `no run directory`.

## Trigger, repetition and re-runs

Each workflow runs only on `pull_request` `opened` and `reopened`, with a paths filter on its own file. A push to the
branch (`synchronize`) never re-runs the trial, so the observed record cannot land on the trial branch by accident;
it goes to a separate records pull request.

**Which run decides (preregistered).** A run decides an OS when its result.json, or, only if result.json is absent
from the compare artifact, the outcome line compare.py printed, gives adopt, reject or no verdict for that OS; a run
in which neither exists is incomplete. A result.json lists the OS that its run did not measure as not measured,
which decides nothing. Per OS, the deciding run is the first run of that OS's own trial workflow that decides it
before that OS's trial ended. Until an OS's trial ends, a repeat is allowed for it only by closing and reopening the
draft pull request when no run of either trial workflow is in progress. Once an OS's trial has ended, at its deciding
run or without a verdict, nothing changes it: its later runs are reported only, and cancelling or reopening during
such a run is not a deviation for that OS.

`compare.py` writes `summary.md` and `checkout-status.json` first and `result.json` last, through a temporary file
and a rename, and prints its outcome lines after that: a failure before the rename (for example a full disk, or the
oracle's own tests failing in the step before) leaves no `result.json`, and once `result.json` exists, it decides
any OS for which it gives adopt, reject or no verdict, whatever the compare step's exit status.

**Protocol deviations (preregistered).** Any coordinator action other than the close-and-reopen repeat that changes
the head, or that makes a run incomplete after its first serial, shards or controls job started, is a protocol
deviation: pushing a commit, or cancelling that run by hand, reopening during it or deleting its artifacts or the run
itself; it ends the trial of each OS it affects without a verdict at the moment it occurs. No run starts while the
pull request conflicts with main, because GitHub runs no pull_request workflow on a pull request with a merge
conflict: the trial of an OS that then still needs a run ends without a verdict (not measured), and no push may
resolve the conflict. The merge-conflict behaviour is github/docs `events-that-trigger-workflows.md` at `63859c48`,
line 466. A run cancelled before its first serial, shards or controls job started is incomplete, not a deviation.
`compare.py` does not see a deviation; the outcome record names it, and reports every run, its outcome, the reason
for each repeat and, for every cancelled run, what cancelled it and the evidence (a reopen shows as a newer run of
the same workflow that started while the cancelled run was in progress).

**Re-runs.** Never re-run any job, the compare job included, and never use "Re-run failed jobs" or "Re-run all
jobs" (the control job fails by design, so they would always re-run it). Any re-run makes the OS incomplete: the
compare job passes its own `GITHUB_RUN_ATTEMPT` to `compare.py`, which also reads every run and control directory's
`run_attempt`. Every upload sets `overwrite: false`, which fails "if an artifact for the given name already exists"
(actions/upload-artifact `action.yml` at `043fb46d`, lines 37-42). Unverified, because no re-run is permitted: whether
a re-run job's upload collides with the first attempt's artifact of that name, so that its data never reaches a
compare job, or succeeds, so that its directory (attempt 2) does; and whether a job re-run also re-runs the jobs that
need it (the re-run page of github/docs at `a3e0414f` does not say). The outcome is incomplete in each case. If a
re-run happens anyway, the run's attempts and artifact listing (GET) settle which applied.

**Concurrency.** `cancel-in-progress: true` (github/docs `data/reusables/actions/actions-group-concurrency.md` at
`336b7f54`, line 11): a reopen during a run cancels that run instead of queueing a second full run that would start
unattended when the first ends and hold on macOS up to three of the five slots for hours. Its cost: one reopen
starts both trial workflows, so a repeat for one OS waits until the other OS's run has ended, or has been cancelled
once that OS's trial ended; in particular a Linux repeat may wait for the macOS run, however long the macOS queue is.

## Run it

```sh
D=blueprints/convergence-practice/suite-shards-trial-20261003
python3 $D/inventory.py --os ubuntu-24.04 --root . --weights $D/weights.json --out inventory
python3 -m unittest discover -s $D -p "test_*.py"
python3 $D/compare.py verdict --results results --inventory inventory --expected-sha "$PR_HEAD_SHA" \
  --run-attempt 1 --os ubuntu-24.04 --needs needs.json --out result.json --summary-md summary.md \
  --checkout-status checkout-status.json
python3 $D/compare.py controls --artifact results/controls --os ubuntu-24.04 --job-result failure
python3 $D/make_fixtures.py --work <empty scratch directory outside the checkout>
```

`compare.py verdict` writes `summary.md` and `checkout-status.json` first and `result.json` last (a temporary file,
then a rename), prints one outcome line per OS after it and exits 0; a failure before the rename leaves no
`result.json`. It exits 2 for unusable arguments (a missing `--run-attempt` included). `compare.py controls` exits 0
when the control run met every expectation and 1 otherwise. The record is `result.json`, the `.exit` and
`exit-code.txt` files and the job results, never the rendered step summary or a log annotation: the logs and the
summary carry text the pull request controls (log tails, loader errors, inventory problems), which can mislead a
reader of the web page but cannot change an exit status, a job result or an artifact.

## First-run checklist (GET requests and artifact downloads only)

1. Before the opening and before every reopen: read the macOS queue (queued and in-progress macos-15 jobs of the
   repository). This pull request changes `manifests/evidence.json`, so `adoption-bootstrap.yml`, whose
   `pull_request` trigger takes the default types, also starts bootstrap-macos, bootstrap-macos-brew and
   validate-macos at the opening and again at every reopen: with this workflow's three, up to six macOS jobs against
   five slots. The coordinator opens, and reopens, the pull request only when the macOS queue is not saturated and
   reads the queue again after each; record every reading and every macOS job's queue time.
2. For each workflow run: the run object's `run_attempt` and every job's attempt are 1, and `result.json`'s
   `inputs.compare_run_attempt` is `"1"`; the artifact listing holds the nine `arm-*` artifacts, `inventory`,
   `controls` and `compare`, and `inputs.ignored_entries` is empty. For a cancelled run, what cancelled it and when
   (see "Protocol deviations (preregistered)" in "Trigger, repetition and re-runs").
3. Controls: in the controls artifact, `meta.json` `steps` holds `foreground` and `control-0` to `control-3` with
   outcomes `success`, `success`, `failure`, `failure`, `failure` (this settles whether the steps context carries a
   background step's outcome after the group's implicit wait; when it records some or none of the four and nothing
   else fails, `result.json` marks the controls unmeasurable and the OS gets no verdict); `lost_steps` (control steps
   that left no probe, log or exit status); the probes' monotonic starts; `heartbeat.json`, read
   through `result.json` `controls.<os>.hang`: the stop (`stop_after_probe_seconds`, `stop_seen_as`), its deadline
   (`stop_deadline_after_probe_seconds`), the alive span, whether and when the parent shell ended, and whether the
   process still ran during the recheck. A stop seen as a parent pid change near 60 to 70 s with `outlived_step`
   true, the expectation from the runner source, and a stop seen as the last heartbeat of a process that ended with
   its step both pass when the stop lies at or after 50 s and before the deadline; the record states which was
   observed. And, from the jobs API, the controls job's step list with each step's conclusion, `started_at` and
   `completed_at` (the hang step's span on the service clock should be at least 60 s and well under 300 s).
4. Probes: every background step's SIGINT and SIGQUIT dispositions, the exported names and the Python version, in
   the controls and in each arm-run.
5. Read the harden-runner step log of one macos-15 job; if its agent did not start, write "macOS egress unaudited" in
   the outcome record.
6. Record the result of the hosted `validate` job's online zizmor step (`.github/workflows/validate.yml` line 70) on
   the pushed head; the local offline zizmor run is not that check.
7. `result.json` `verdicts.<os>.flags`: every flag (a sharded arm passed over while it was ineligible only through
   steps that never wrote an exit status, or arm runs on more than one runner image) is addressed in the outcome
   record.
8. Take every number of the outcome record from `result.json`, the exit files and the jobs API, never from the step
   summary or log annotations.

## Local evidence recorded on 2026-10-03 (local integration, synthetic fixtures and a probe, not a hosted run)

- **Coordinator's whole-suite preflight** at `d2777ee7` (48-core WSL2 host, CPython 3.13.16; 9,844 ids in 233 files):
  the serial run (`python3 -m unittest -v --durations 0`) took 1,305 s and ended `FAILED (failures=32,
  skipped=1181)`, the 32 failures host-specific; loading every file by name gave exactly the discovery ids. Four
  LPT shards as four concurrent processes took 361 s unpinned and 378 s pinned to 4 cores; three shards pinned to 3
  cores took 487 s; in all three the 9,853 parsed records equalled the serial run's. A first attempt differed only
  because a shell's background job started the shards with SIGINT and SIGQUIT ignored, which skipped a SIGQUIT subtest.
- **The oracle on those real logs** (`serial.log` as S r1, the pinned 4-shard logs as G4 r1, synthetic metadata in
  the artifact layout, `--run-attempt 1`, `--min-repeats 1`, `--skip-list-recompute`): both runs eligible, zero
  mismatches, no id missing, extra or run twice: equal (the OS is incomplete only because the dry run has no G4T run
  and no control run). Negative checks: the true S command (`--durations 0`) makes S ineligible under the command
  rule; one mutated outcome in a shard is caught by the self-consistency check and by the record comparison;
  `run_attempt` 2 in G4 r1, or `--run-attempt 2`, makes the OS incomplete as a re-run.
- **`make_shards.py` against the preflight's lists** (same 233 files): it places the 109 heaviest files of G4 and the
  115 heaviest of G3 exactly as the preflight did; the remaining small files (each at most 298 ms; 7.6 s and 4.6 s in
  all) differ only by tie-breaking between the preflight's float loads and these integer milliseconds, and every
  shard's predicted load is equal within 1 ms. The preflight's equality evidence therefore covers a different
  partition of the small files.
- **`inventory.py` at the trial base `9b0b8d6d`**: 234 test files, 9,943 ids, parity true, no problem, identical
  output on CPython 3.13.16 and a bare 3.12.3; predicted seconds per shard: G4 318.9 x 4; G4T 301.1 x 4 plus a
  71.0 s tail; G3 425.1 x 3; G3T 401.5 x 3 plus 71.0 s.
- **The controls run together locally** (`make_fixtures.py`, CPython 3.13.16, the four control processes started
  within 0.09 s of each other; synthetic fixtures): the passing control ended at once, the hang control was stopped
  60 s after it started (its own process killed; its last heartbeat 59.05 s after its probe), the failing control
  ended `FAILED (failures=1)` after 90.0 s with exit 1, the crashing control exited 3 after 120 s, and the finish
  step's record began 120.30 s after the hang control's probe.
- **zizmor 1.30.1 inside a parallel group** (offline, `--no-config --no-ignores --persona regular`, on scratch
  copies of `suite-shards-trial-linux.yml` outside the checkout): an `${{ github.event.pull_request.title }}` echoed
  in Shard 0's script, an unpinned `uses: actions/checkout@v4` step and a step writing that expression to
  `GITHUB_ENV`, all planted inside the shards job's `parallel:` group, gave the same findings as the same three
  planted as ordinary steps before the group: `template-injection` on both expressions, `unpinned-uses` and
  `artipacked` on the action; with the trigger changed to `pull_request_target`, `github-env` also fired on the
  planted write in either place. The unchanged workflow gave no finding. Other audits were not probed, and zizmor
  still warns that its parallel-step support is experimental.
- **`test_compare.py`**: 118 tests OK on CPython 3.13.16 and the bare 3.12.3 (synthetic fixtures).

## Limits

- The preflight ran on another machine (48 cores), another CPython patch release and an earlier base; hosted runners
  have 4 vCPUs (Linux) and 3 cores (macOS). Hosted macOS has never run this suite in shards.
- n = 3 per arm. Hosted wall-clock time varies with neighbours and image updates; three repeats bound this but do
  not remove it.
- Unmeasured hosted behaviour, each settled by a first-run check above: whether a hosted runner starts background
  steps with SIGINT or SIGQUIT ignored, and whether earlier `GITHUB_ENV` exports and `actions/setup-python`'s `PATH`
  reach them (the probes); whether `timeout-minutes` stops a background step, which the runner source does
  (`BackgroundStepCoordinator.cs` at v2.337.0, lines 78 and 225), when, and whether its Python process outlives it
  (the hang control); whether the steps context carries a background step's outcome after the group's implicit wait,
  which GitHub's published workflow schema (actions/languageservices `workflow-parser/src/workflow-v1.0.json` at
  `880ac43b`, lines 2168-2197 and 2255-2270: a `parallel:` item is a step that may carry an `id`) and the runner
  source (`CompleteWaitedSteps`, lines 371-392, flushes each waited step's outcome and conclusion) both imply. If any
  of the four control steps' outcomes does not arrive while no recorded one is wrong and every other control
  expectation holds, the controls are unmeasurable and the OS gets no verdict, which decides it, since a repeat would
  meet the same platform (rule 5 states when the controls fail instead, and when a lost control step makes the OS
  incomplete).
- A shard that hangs is expected to be stopped by its step limit (25 min on Linux, 40 min on macOS), which makes its
  run ineligible (no exit status); its Python process may live on until the job ends (the hang control measures it),
  and every job's own `timeout-minutes` bounds it.
- Lost steps. A step lost to a runner fault is one whose script never ran although the test phase (for a control
  step, the control group) had started, so it left none of its files (for the S step `command.txt`, `log.txt` and
  `exit-code.txt`; for a control step its probe, log and exit status). A lost S step makes the OS incomplete, and so
  does a lost control step unless other recorded control evidence fails (rule 5). A shard step that is lost, or
  stopped before its command or its exit status, makes its run ineligible, not incomplete, so it can hand the
  decision to the other arm or give reject; `result.json` flags a sharded arm that the rule passed over while it was
  ineligible only so (`verdicts.<os>.flags`), and the outcome record must address the flag. The asymmetry: a shard
  step is the candidate itself, which would meet the same fault in production, while S is the baseline and the
  controls measure the platform for both arms, and a lost S or control step measured nothing. A step that wrote any
  of its files is judged on them.
- Python runtime and runner image (premise verified on 2026-10-03 with GET requests): the actions/runner-images release
  `macos-15-arm64/20260829.0321` (published 2026-09-01) moved the image's cached Python 3.13 from 3.13.14 to 3.13.15,
  and an image deployment usually takes 2 to 3 days (actions/runner-images `README.md` at `6d942e63`, line 198), so
  the jobs of one multi-hour run can land on images that cache different patch releases. Every macOS job, the
  ubuntu-24.04 inventory job included, therefore takes the exact release 3.13.15 (`check-latest: false`), the one
  that the newest image, 20260907.0337.1, caches (`images/macos/macos-15-arm64-Readme.md` at `6d942e63`):
  `actions/setup-python` at `5fda3b95` takes an exact version from the tool cache, else downloads it from
  actions/python-versions (`README.md` line 71, `src/find-python.ts` lines 102-123), whose `versions-manifest.json`
  at `52ee1aa0` lists 3.13.15 for darwin arm64 and linux 24.04 x64. Each job's interpreter check asserts CPython
  3.13.15 before the clock starts, so another release or implementation gives a run whose test phase never started.
  Linux runs the image's system python3. On either OS, arm runs that recorded more than one Python version or machine
  make the OS incomplete (rule 5), since the runtime changed during the run. An image with the same runtime can
  still differ in the tools and versions that tests gate on (tests that skip unless `shutil.which` finds a tool, for
  example), so a test can run on one image and be skipped on another: with the S runs on one image and a sharded run
  on another, that run's records would differ from the S baseline, and the run would be ineligible through a record
  mismatch that sharding did not cause, giving reject or a hand-over to the other arm. Whether two consecutive images
  differ in such a tool is unverified. Arm runs on more than one runner image are therefore flagged whatever the
  outcome (`verdicts.<os>.flags`, `summary.md`), and beside a sharded run whose records differ from the S baseline,
  unless that run is ineligible only through steps that never wrote an exit status, they make the OS incomplete
  (rule 5). On one image a record mismatch stays the sharded arm's failure, and more than one image without a
  mismatch is only the flag. `compare.py` holds no copy of the pin: the workflow's pin, asserted by each job before
  its clock starts, and the equality across runs are the control. `validate-macos` takes whatever 3.13 patch its
  image caches.
- zizmor 1.30.1 calls its parallel-step support experimental (its `docs/usage.md` at v1.30.1, "Parallel steps"); the
  probe above measured four audits inside a group, not all. The shard and control steps carry no expression, action,
  `if:` or `GITHUB_ENV`/`GITHUB_PATH` write inside a group, which `test_compare.py` checks in the trial's compare job
  and locally; the repository's required suite does not collect `test_compare.py` (`blueprints/` is not a package),
  so an adoption pull request moves that plain-text check into `tests/test_workflow_hardening.py`. actionlint 1.17.0
  parses the groups, their step ids and their scripts with shellcheck. The hosted `validate` job's online zizmor step
  on the pushed head has not run yet (checklist item 6).
- Artifact layout: the control artifact is downloaded by pattern into `results/controls`. The pinned
  `actions/download-artifact` extracts into the target directory itself when the download is a single artifact,
  `merge-multiple` is set or exactly one artifact matched (`src/download-artifact.ts` at `3e5f45b2`, lines 185-198,
  read with a GET request by this trial's builder unit on 2026-10-03 and re-read separately by the coordinator at the
  same pin), so `results/controls/<os>-controls/` holds the control run; a nested path
  (`results/controls/controls/<os>-controls/`) would leave the control run absent, which `compare.py` counts as
  incomplete, never as a wrong attribution.
- No agent definition changes on this branch: `git diff --name-only 9b0b8d6d 1809afba -- .claude/agents
  adoption/agents examples/claude-native/agents .codex` was empty on 2026-10-03, and no later commit of the branch
  touches those paths.
- No trial job checks the frozen sha256s at run time. Validate (`.github/workflows/validate.yml`) runs on every push
  to the pull request while it does not conflict with main, and re-hashes them: `scripts/validate_convergence.py
  --all-recorded` checks every `{path, sha256}` entry of each record in `convergence_records`, this planned one
  included (its `check_artifacts` runs whatever the record's status), and `scripts/validate.py` every manifest row.
  So a push that edits a frozen file without refreezing fails Validate, and one that refreezes passes it. Every run
  records the head it tested (`meta.json` `checkout_sha`, `result.json` `inputs.expected_sha`); the outcome record
  compares each run's head with the first run's, and a changed head is a protocol deviation.
- Artifact attribution checks names and layout, not authorship: every arm job runs the pull request head, so a head
  that writes another run's directory into its own artifact makes its own run ineligible, but code that rewrites its
  own run directory is not detected beyond the oracle's rules.
- macOS slots: this pull request changes `manifests/evidence.json`, an `adoption-bootstrap.yml` path, so the opening
  and every reopen also start bootstrap-macos, bootstrap-macos-brew and validate-macos: up to six macOS jobs against
  the plan's five slots, each time. Queueing delays a job but does not enter `step_seconds`; a stalled queue that ends
  in cancellation makes the OS incomplete, unless the run was cancelled by hand after its first serial, shards or
  controls job started (the protocol deviation in "Trigger, repetition and re-runs"). The first trial's macOS jobs
  never started while five adoption-bootstrap macOS jobs held the pool.
- `step-security/harden-runner` audits egress on macos-15 only if its agent starts; a previous hosted validate-macos
  run logged a non-fatal installation warning (`evidence/artifacts/wsl-retrieval-retirement-20261003/ci-correction.md`,
  line 7). Checked on the first run (checklist item 5); the jobs hold no secret and a read-only token.
- The macOS inventory is built on ubuntu-24.04. A platform-dependent id would make the macOS S runs ineligible (their
  executed ids must equal the inventory), which gives no verdict, not a wrong verdict.
- Skip reasons are not compared. Side effects that leave outcomes unchanged are invisible to the oracle.
- `tests.test_secret_path_guard.K4GuardTests.test_k4_timing` is timing-bound (30 to 60 s serially) and failed under
  class-level parallel load in the first trial; G4T and G3T keep its module out of the parallel group, G4 and G3 do not.
