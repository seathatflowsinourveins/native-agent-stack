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
preregistered in its `experiment.json` (status `planned`). Besides these, it changes only the expected-workflow set of
`tests/test_workflow_security_coverage.py` and registers its files in `manifests/evidence.json`. None of the trial's
job names is a required context. On 2026-10-03, before the first push, the branch is re-based onto that day's main
with every trial file byte-identical (the 16 frozen sha256s in `experiment.json` are unchanged): `base_revision`
still names `9b0b8d6d`, the revision the inputs were measured against, and the pull request description names the
main commit actually used.

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
jobs); macOS at most one of each, so with the control job the macOS workflow holds no more than three of the plan's
five macOS slots. The same opening also starts three macOS jobs of `adoption-bootstrap.yml`, because this pull
request changes `manifests/evidence.json`, one of that workflow's bootstrap paths: bootstrap-macos,
bootstrap-macos-brew and validate-macos, so up to six macOS jobs meet five slots (see "Risks"). The serial and
sharded arms are separate jobs so that no step inside a `parallel:` group carries an `if:`, which the reference does
not document there; macOS's limit of two timed jobs at once is therefore one serial plus one sharded job
(`max-parallel: 1` each), beside the one control job.

Shard lists are built at run time, in each workflow's inventory job, from the test files of the checked-out head by
the frozen `make_shards.py` (longest-processing-time-first over files, from the frozen `weights.json`; a file missing
from the weights takes the mean weight, so a new file can never drop out). The inventory job fails, and no arm runs,
unless loading every `tests/test_*.py` by name gives exactly the discovery ids, no id is loaded twice, nothing fails
to import, and every file is in exactly one list or the tail of each arm.

Every shard step is a plain `run:` step with no expression in its script; it runs its list with
`python3 -m unittest -v`, records the exit status and exits with it, so a failing shard is expected to fail its step,
the group and the job, as production would (the reference's lines 1078-1086; the control job measures it). Each shard
step has a hang guard (`timeout-minutes` 25 on Linux, 40 on macOS), expected to stop the step; the hang control
measures that on each OS.

## The preregistered rule

The full text is `experiment.json`'s `quality_rule`; `README.md` gives the same rules with their sources. In short:

- **S** is eligible with three runs, each complete, its exit status agreeing with its status line, its executed ids
  exactly the inventory, the exact command, a clean checkout, `run_attempt` 1, the pull request head and a valid step
  time. Ids whose records differ among the S runs are flaky and are excluded from the comparison.
- **G and GT** runs are eligible when every shard log is complete and consistent, every command is
  `python3 -m unittest -v` plus its list, the lists are the inventory's, every log ran exactly its modules' ids, the
  union is the inventory with each id once, the `(kind, key, outcome)` records equal the first eligible S run outside
  the flaky ids, every step ran its job's Python version, and the checkout, attempt, head and step-time rules hold.
- **Controls** per OS: one job runs the arms' shard step body in one `parallel:` group on a passing control, a
  hanging control (stopped by a 1-minute step limit, writing a heartbeat), a control that fails one test after 90 s
  and one that ends its process with `os._exit(3)` after 120 s, so the last two must outlive a sibling's stop and a
  sibling's failure. Each step has an `id`, and the finish step records each step's own outcome from the steps
  context. The job must fail; the exit statuses must be 0, none (stopped), a non-zero status with
  `FAILED (failures=1)`, and 3; the steps' own outcomes success, failure, failure, failure (an unrecorded outcome is
  never evidence: when any of the four control steps' outcomes is unrecorded, no recorded one is wrong and every
  other expectation holds, the controls are unmeasurable and the OS gets no verdict); the steps must start
  within 15 s of each other, so that the
  failing control outlives the hang step's stop (at most 70 s after its start) and the crashing control outlives the
  failing control's failure; the hang step must be stopped, when its shell ended (the first heartbeat with another
  parent pid, else the process's last heartbeat), at least 50 s after its probe and before the failing control's
  probe plus 90 s, so the 1-minute limit stopped it, and the group must end less than 240 s after that probe; every
  background step must run the foreground step's Python and see a variable exported through `GITHUB_ENV` by an
  earlier step. A second job asserts this, and the compare job repeats the check on the same artifact: when the second
  job failed although the repeated check passes, the check job failed outside its checks and the OS is incomplete;
  when both fail, the controls failed. A control step that left no probe, no log and no exit status although the
  group started, which only a runner fault does, makes the OS incomplete, its recorded outcome included, unless what
  the steps that ran recorded shows wrong behaviour; the start spread and the hang checks then judge only the steps
  that ran. Whether background steps start with SIGINT or SIGQUIT ignored, and whether the hang control's process
  outlives its step, are recorded and reported, not judged.
- **Decision**, per OS: an arm is eligible with three eligible runs and passed controls; S ineligible or
  unmeasurable controls give no verdict; no eligible sharded arm gives reject; otherwise take the eligible arm with
  the smaller median step time (a tie goes to G), and adopt only if its median is at most 3/5 of the S median and its
  slowest run at most 3/4 of the fastest S run, as exact fractions; otherwise reject, with no fall-through. Never a
  rule outcome, the OS is incomplete after any re-run (the compare job's own run attempt other than 1, or a recorded
  run attempt of any run or control directory other than 1), a cancelled or skipped job or a missing run, a job
  status cancelled (of an arm run or of the control run), an unrecorded run attempt (no `runtime.json`), a run whose
  test phase never started (its clock-start step did not succeed: a setup failure, never ineligibility and never a
  hand-over to the other arm), an S run whose step was lost to a runner fault (no `command.txt`, `log.txt` or
  `exit-code.txt` although its test phase started), arm runs that recorded more than one Python version or machine
  (the runtime changed during the run), a sharded run whose records differ from the S baseline while the arm runs ran
  on more than one runner image (`meta.json` `runner_image`; the difference may come from the image, which provides
  the tools and versions that tests gate on, not from sharding), a control run that is missing or whose group never
  started, control steps lost to a runner fault while no other control evidence failed, a controls-check job that
  failed although the compare job's own check passes, an inventory job that failed without a `report.json` that
  records a gate finding (the gate never reported, or its own child interpreter was stopped from outside), or an
  inventory job that
  succeeded although a file of its artifact is absent from the compare job's download (a partly downloaded artifact
  set); an inventory gate that failed on a finding, or an inventory artifact that is present but unusable, gives no
  verdict. The order: re-runs first; then a failed or unreported inventory gate; then the other incomplete
  conditions; then an unusable inventory artifact, an ineligible S or unmeasurable controls; then the rule. A shard
  step that never reached its command or exit status makes its run ineligible even after a runner fault;
  `result.json` flags a sharded arm that the rule passed over while it was ineligible only so, and arm runs on more
  than one runner image whatever the outcome (beside a sharded run whose records differ from the S baseline they also
  make the OS incomplete, above), and the outcome record must address every flag.
- **Which run decides, and the protocol.** A run decides an OS when its result.json, or, only if result.json is
  absent from the compare artifact, the outcome line compare.py printed, gives adopt, reject or no verdict for that
  OS; a run in which neither exists is incomplete. A result.json lists the OS that its run did not measure as not
  measured, which decides nothing. Per OS, the deciding run is the first run of that OS's own trial workflow that
  decides it before that OS's trial ended. Until an OS's trial ends, a repeat is allowed for it only by closing and
  reopening the draft pull request when no run of either trial workflow is in progress. Once an OS's trial has
  ended, at its deciding run or without a verdict, nothing changes it: its later runs are reported only, and
  cancelling or reopening during such a run is not a deviation for that OS. Any coordinator action other than the
  close-and-reopen repeat that changes the head, or that makes a run incomplete after its first serial, shards or
  controls job started, is a protocol deviation: pushing a commit, or cancelling that run by hand, reopening during
  it or deleting its artifacts or the run itself; it ends the trial of each OS it affects without a verdict at the
  moment it occurs. No run starts while the pull request conflicts with main, because GitHub runs no pull_request
  workflow on a pull request with a merge conflict: the trial of an OS that then still needs a run ends without a
  verdict (not measured), and no push may resolve the conflict. `compare.py` writes `result.json`
  last, after `summary.md` and `checkout-status.json`, through a temporary file and a rename, and prints its outcome
  lines after it, so a failure before the rename leaves no `result.json`. No job is ever re-run, the compare job
  included. `cancel-in-progress: true`: a reopen during a run cancels it instead of queueing an unattended second
  run. Its cost: one reopen starts both workflows, so a repeat for one OS waits until the other OS's run has ended,
  or has been cancelled once that OS's trial ended.

## Lessons of the first trial applied

1. **A whole-suite local preflight before preregistering.** The coordinator ran it at `d2777ee7` (local integration
   evidence; limits below): the serial run (1,305 s, `FAILED (failures=32, skipped=1181)`, all 32 host-specific), and 4
   shards as 4 concurrent processes in 361 s unpinned and 378 s pinned to 4 cores, 3 shards pinned to 3 cores in 487 s,
   each with its 9,853 parsed records equal to the serial run's. A first attempt differed only because a shell's
   background job started the shards with SIGINT and SIGQUIT ignored, which skipped a SIGQUIT subtest.
2. **The observed record cannot land on the trial branch.** Each workflow runs only on `opened` and `reopened`, with
   a paths filter on its own file and no `synchronize`; to repeat the trial after an incomplete run, close and reopen
   the pull request. No job is ever re-run: any run attempt other than 1, the compare job's own included, makes the
   OS incomplete in `compare.py`, not merely the touched run ineligible, so a re-run can neither reject an OS (as a
   re-run control job failing its attempt check would have) nor hand the decision to the other arm.
3. **Two independent workflows**, each with its own ubuntu-24.04 inventory job, arms, controls and compare job, so a
   stalled macOS queue never holds the Linux evidence.
4. **Counts agree everywhere and the limits are stated**: n = 3; the controls are synthetic fixtures executed on the
   hosted runner; the hosted jobs run no model; hosted behaviour that no run has measured is stated as an
   expectation with the first-run check that settles it (`README.md`, "First-run checklist").
5. **Self-review and independent review before the first push**: arithmetic, retention, coverage gaps and design
   holes; six rounds of independent review of this preregistration (evidence reviews in all six, security reviews
   in the first two) were resolved before any hosted run (`experiment.json`, `discovery_provenance`; the third to
   sixth rounds below).

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
  or the controls show that background steps do not honour `timeout-minutes`, `GITHUB_ENV` or the interpreter, that
  a failing background step does not fail on its own, or that one step's stop or failure stops its siblings.
- After an adoption, a failure that appears only in sharded runs.
- A suite change that makes the inventory gate fail (a file loaded only by discovery, an id loaded twice).

## Risks

- **Signal dispositions.** Whether the hosted runner starts background steps with SIGINT or SIGQUIT ignored is not
  documented; locally, ignored dispositions skipped a SIGQUIT subtest, which would be a record mismatch. Every shard's
  probe and the control job measure it.
- **Environment of background steps.** The reference covers exports made by a background step, not whether earlier
  `GITHUB_ENV` exports and `actions/setup-python`'s `PATH` reach one; if not, the shard holding
  `tests.test_shell_parser_ci` fails its tripwire, or a macOS shard runs another Python, and the run is ineligible.
- **Step outcomes of background steps.** GitHub's published workflow schema (actions/languageservices
  `workflow-parser/src/workflow-v1.0.json` at `880ac43b`, lines 2168-2197 and 2255-2270) lets a step inside
  `parallel:` carry an `id`, and the runner source (actions/runner v2.337.0, `BackgroundStepCoordinator.cs` lines
  371-392) flushes each waited step's outcome and conclusion at the group's wait; that the hosted service fills
  `steps.<id>` for them is unmeasured. If it leaves any of the four control steps' outcomes unfilled while no recorded
  one is wrong and every other control expectation holds, the controls are unmeasurable and the OS gets no verdict,
  which decides it, since a repeat would meet the same platform (`README.md` rule 5 states when the controls fail
  instead and when a lost control step makes the OS incomplete). The first run reads the controls' recorded outcomes.
- **Stopping a timed-out step.** The runner source signals only the step's own shell (`ProcessInvoker.cs` lines
  443-465, 829-853 and 855-869; `ScriptHandler.cs` line 346) and records a timed-out background step as failed
  (`BackgroundStepCoordinator.cs` lines 244-248), so a stopped shard's Python process is expected to live on until the
  job ends. Unmeasured; the hang control's heartbeat measures it. Whether the process outlives its step is reported,
  not judged; when the step's shell ended (the parent pid change) is judged, at or after 50 s from the step's probe
  and before the failing control's probe plus 90 s. A stopped shard writes no exit status, so its run is ineligible
  either way, and every job's own `timeout-minutes` bounds it.
- **A runner fault inside the test phase.** A step lost to a runner fault is handled as `README.md` "Limits" ("Lost
  steps") defines it: a lost S step, or a lost control step while no other recorded control evidence fails, makes the
  OS incomplete, while a shard step that is lost or stopped before its command or exit status makes its run
  ineligible, flagged when the rule passes over its arm; while the arm runs ran on more than one runner image, such a
  run whose records differ from the S baseline makes the OS incomplete instead.
- **Python runtime and runner image.** Premise verified on 2026-10-03 with GET requests: the actions/runner-images
  release `macos-15-arm64/20260829.0321` (published 2026-09-01) moved the image's cached Python 3.13 from 3.13.14 to
  3.13.15, and an image deployment usually takes 2 to 3 days (actions/runner-images `README.md` at `6d942e63`, line
  198), so the jobs of one multi-hour run can land on images that cache different patch releases. Every macOS job,
  the ubuntu-24.04 inventory job included, takes the exact release 3.13.15 with `check-latest: false`, the one the
  newest image (20260907.0337.1) caches; `actions/setup-python` at `5fda3b95` takes an exact version from the tool
  cache, else downloads it (`src/find-python.ts` lines 102-123), and actions/python-versions lists 3.13.15 for darwin
  arm64 and linux 24.04 x64 (`versions-manifest.json` at `52ee1aa0`). Each job's interpreter check asserts CPython
  3.13.15 before the clock starts. On either OS, arm runs that recorded more than one Python version or machine make
  the OS incomplete. An image with one runtime can still differ in a tool or version that tests gate on, which can
  flip a test between the S runs and a sharded run on another image, or make it hang there until its step's limit
  stops the step: arm runs on more than one runner image are flagged whatever the outcome, and beside a sharded run
  whose records differ from the S baseline they make the OS incomplete (`README.md`, "Limits"). `validate-macos`
  takes whatever 3.13 patch its image caches.
- **The inventory gate's own child interpreter.** A child stopped from outside (SIGKILL from the out-of-memory killer,
  or SIGTERM, SIGINT or SIGHUP from a runner) is recorded in `report.json` as an execution problem, not a finding, and
  makes the run incomplete; any other failure of a child is a finding, and a failed gate with a finding gives no
  verdict.
- **Re-runs.** No re-run is permitted, so the first run cannot show whether a re-run job's upload
  (`overwrite: false`, which fails if an artifact of that name already exists: actions/upload-artifact `action.yml`
  at `043fb46d`, lines 37-42) collides with the first attempt's artifact, or whether a job re-run also re-runs the
  jobs that need it. `compare.py` gives incomplete in each case.
- **macOS slots.** Up to six macOS jobs (this trial's three and adoption-bootstrap's three, started by the
  `manifests/evidence.json` change, since adoption-bootstrap's `pull_request` trigger takes the default types) meet
  the plan's five slots at the opening and again at every reopen, the queueing hazard that kept the first trial's
  macOS jobs from starting. The coordinator opens, and reopens, the pull request only when the macOS queue is not
  saturated and reads the queue before and after each; queue time does not enter `step_seconds`.
- **Egress audit on macOS.** harden-runner's agent logged a non-fatal installation warning on a previous hosted
  validate-macos run (`evidence/artifacts/wsl-retrieval-retirement-20261003/ci-correction.md`, line 7). The first run
  reads one macos-15 job's harden-runner log; if the agent did not start, the outcome record says macOS egress was
  unaudited. The jobs hold no secret and a read-only token.
- **zizmor's experimental support for parallel steps** (zizmor 1.30.1 warns, and its `docs/usage.md` at v1.30.1 calls it
  experimental). Measured on scratch copies of the Linux workflow (offline, `--no-config --no-ignores --persona
  regular`): template-injection, unpinned-uses and artipacked report constructs planted inside a `parallel:` group
  exactly as outside it, and github-env too under a `pull_request_target` trigger; other audits were not probed. The
  trial's group steps carry no expression, action, `if:` or `GITHUB_ENV`/`GITHUB_PATH` write, which
  `test_compare.py` checks in the trial's compare job and locally; the repository's required suite does not collect
  it (`blueprints/` is not a package). actionlint 1.17.0 parses the groups, their step ids and their scripts with
  shellcheck. The hosted `validate` job's online zizmor step on the pushed head is a first-run checklist item.
- **Text the pull request controls.** Log tails, loader errors and inventory problems reach the job logs and the step
  summary; the record is `result.json`, the exit files and the job results, never the rendered summary.
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
- The local oracle dry run used the coordinator's real logs with synthetic metadata, `--min-repeats 1` and
  `--skip-list-recompute`; it shows the comparison on real logs, not a verdict.
- Artifact attribution checks names and layout, not authorship: every arm job runs the pull request head.
- The macOS inventory is built on ubuntu-24.04 with the arms' Python release; a platform-dependent id gives no
  verdict.
- Skip reasons are not compared; side effects that leave outcomes unchanged are invisible to the oracle.
- Verified on 2026-10-03 before the push: actions/download-artifact `src/download-artifact.ts` at `3e5f45b2`, lines
  185-198 (read with a GET request by this trial's builder unit, and re-read separately by the coordinator at the
  same pin), sets the download path to the target directory itself when the download is a single artifact,
  `merge-multiple` is set or exactly one artifact matched, so the control artifact lands as
  `results/controls/<os>-controls/`; a nested path would leave the control run absent, which `compare.py` counts as
  incomplete, never as a wrong attribution. `git diff --name-only 9b0b8d6d 1809afba` over `.claude/agents`,
  `adoption/agents`, `examples/claude-native/agents` and `.codex` is empty, and no later commit of the branch touches
  those paths. Not yet verified: the hosted `validate` job's online zizmor step on the pushed head (first-run
  checklist).

## Usage rule and evidence classes

No usage claim. The hosted jobs run deterministic commands and no model; the model usage of the sessions that built
this trial is not recorded and stays unknown. Evidence classes so far: local integration (the coordinator's preflight,
the inventory gate at the base, the oracle's dry run on real logs), synthetic fixtures (real local runs of a fixture
suite and of the controls, on which the oracle's 119 tests pass on CPython 3.13.16 and 3.12.3), a local probe of
zizmor on planted constructs, and source review (the GitHub documentation, GitHub's workflow schema, the runner
source, CPython and the alternatives at their pins). Nothing here is native execution on a hosted runner or upstream
acceptance; the controls, once run, are synthetic fixtures executed on the hosted runner.

## After the run

The observed record goes to a separate records pull request; the trial branch is not pushed to after its first push.
That pull request carries an outcome record under `docs/decisions/`, a receipt under `evidence/receipts/` and sanitized
artifacts (the compare artifact's `result.json`, `summary.md` and `checkout-status.json`, a byte copy of this
preregistration, sanitized log excerpts), because the run's artifacts expire after 30 days and its records under the
repository's 90-day retention. It names the deciding run per OS, reports every other run and attempt with the reason
for each repeat and what cancelled each cancelled run (and names any protocol deviation), addresses every flag in
`result.json`, and records the answers of `README.md`'s first-run checklist (the macOS queue before and after the
opening and every reopen, every attempt, the controls' step outcomes, spans, the hang step's stop and heartbeat, the
probes, the macOS harden-runner log, the hosted online zizmor result), taking every number from `result.json`, the
exit files and the jobs API.

A passing result would lead, for each adopting OS, to an adoption pull request that also builds the shard lists at
run time inside the production job, updates `tests/test_workflow_hardening.py` for sharded whole-suite jobs (the
whole-suite classification, the full-history rule and the `validate.yml:validate` assertion) and adds a shard-coverage
guard test (every test file in exactly one shard). That adoption pull request must also put the parallel-group
plain-text check (no step inside any `parallel:` group of any workflow carries an expression, an action reference,
an `if:` or a `GITHUB_ENV` or `GITHUB_PATH` write) into `tests/test_workflow_hardening.py`, which the required suite
runs; here it lives in `test_compare.py`, which only the trial's compare job and local runs collect. None of that is
done here.

## Third review round (2026-10-03)

An evidence delta review before the first push found no high or medium defect and nine low findings (R3-1 to R3-9).
This revision, still before any hosted run, resolved them:

- **R3-1.** `compare.py` writes `result.json` last (after `summary.md` and `checkout-status.json`, through a
  temporary file and a rename) and prints its outcome lines after it, so a failure before the rename leaves no
  `result.json`. One sentence states the deciding event, keyed on `result.json` or the printed outcome line, not on
  the compare step's exit status.
- **R3-2.** A file of a successful inventory job's artifact that is absent from the compare job's download makes the
  OS incomplete (a partly downloaded artifact set); a present but unusable file still gives no verdict.
- **R3-3.** Any unrecorded control step outcome, with nothing recorded wrong and every other expectation met, makes
  the controls unmeasurable (no verdict); only recorded evidence rejects.
- **R3-4.** A control step lost to a runner fault (no probe, log or exit status) makes the OS incomplete unless
  other recorded control evidence fails; the checks across steps judge only the steps that ran.
- **R3-5 to R3-9.** The headers and this record no longer say either run can be cancelled alone; the Linux serial
  job's comment gives the base's 40-minute `validate` limit and main's 60 since 2026-10-03; runs after an OS's trial
  ended are reported only; any coordinator action other than the repeat that changes the head or makes a run
  incomplete is a deviation; a merge conflict that blocks a needed run ends that OS's trial without a verdict (not
  measured); every deciding-run statement names the first run of that OS's own trial workflow, and `result.json`
  lists the OS a run did not measure as `not measured`.
- **Drift control.** `compare.PROTOCOL` holds the protocol's seven sentences, `result.json` repeats them, and
  `test_compare.py` checks that `README.md`, the `quality_rule`, this record and both workflow headers state each one
  word for word.

Removed or simplified: the clause about a `compare.py` that exited non-zero and the separate rule for a failed
upload became the one deciding-event sentence; `compare_run_attempt` 1 left the deciding-run statements (any other
attempt gives incomplete anyway); "none of the four" unrecorded outcomes became "any"; the two prohibitions of hand
cancellation and of a reopen during a run became the one deviation sentence, which no longer reaches a run after an
OS's trial ended.

Accepted residual risks:

- No trial job checks the frozen sha256s at run time (the review proposed one; none is added). Validate re-hashes
  them on every push to the pull request that does not conflict with main (`validate_convergence.py
  --all-recorded` covers this planned record and `validate.py` the manifest), so an edit that is not refrozen fails
  it and a refrozen push passes it; every run records the head it tested, and a changed head is a deviation.
- The branch changes `manifests/evidence.json` and `tests/test_workflow_security_coverage.py`, which other pull
  requests change too, so a conflict with main after the opening can end an OS without a verdict (not measured):
  re-registering on main would take a push, which the protocol forbids.
- A control step is recognised as lost only when it left no probe, log and exit status; a fault after its probe
  leaves evidence that is judged and can reject.
- Accepted by design in the review: a hand cancellation after `controls-check` reported failed controls turns an
  expected reject into an end without a verdict; it allows no fresh draw and no adopt.
- Unmeasured until the first run: background step outcomes in the steps context, the re-parenting of a stopped
  step's process, and whether `if: always()` jobs run after a cancellation (if not, the run has no `result.json` and
  is incomplete).

## Fourth review round (2026-10-03)

An evidence delta review before the first push found one high, one medium and seven low findings (R4-1 to R4-9).
This revision, still before any hosted run, resolved them:

- **R4-1.** An image rollout during one macOS run could give its jobs different Python 3.13 patch releases, which
  `compare.py` judged as ineligibility (a wrong reject, an unflagged hand-over to the other arm, or a final no
  verdict). The premise was verified with GET requests ("Risks", "Python runtime"). Every macOS job now takes the
  exact release 3.13.15 and asserts it in its interpreter check before the clock starts; arm runs that recorded
  more than one Python version or machine make the OS incomplete; arm runs on more than one runner image are only
  flagged (the fifth round adds the incomplete case beside a record mismatch). The check that every step ran its
  job's Python stays an ineligibility. `compare.py` holds no copy of the pin: the workflow's pin, asserted before
  each clock starts, and the equality across runs are the control.
- **R4-2.** An S run whose test phase started but whose step left no `command.txt`, `log.txt` or `exit-code.txt`
  (lost to a runner fault) makes the OS incomplete, as a lost control step does; `README.md` "Limits" ("Lost steps")
  defines lost steps once, and `experiment.json` and "Risks" point to it.
- **R4-3 to R4-9.** Both headers drop "a protocol deviation" from the reopen clause of their "Re-runs" paragraph;
  the first-run checklist points to "Protocol deviations (preregistered)"; the third round's claim about its new
  tests now names the commit exported (`f0d54bdf`, whose trial files equal `1809afba`'s) and says that two of them
  pin kept behaviour (the fifth round names them), the second round's claim names its one such test, and
  `README.md` no longer keeps that history; the pull request claims word-for-word identity only for the seven
  `compare.PROTOCOL` sentences; `README.md` rule 5 states once when the controls fail, and the other
  documents point to it; the deciding run is the first that decides an OS before that OS's trial ended, a deviation
  ends a trial at the moment it occurs, and the printed outcome line decides only if `result.json` is absent from the
  compare artifact; the GET of `download-artifact.ts` lines 185-198 is credited to this trial's builder unit, the
  coordinator's read being a second one.

`test_compare.py` has 117 tests after this revision. The six new or changed tests (the two runtime-version cases,
two machines, another runner image, the pinned workflow steps, the lost S step) each fail on an export of the
previous head `1b72bf87` with only `test_compare.py` replaced, and pass on this one; the other 111 pass on both. The
drift test fails when any one of the five documents alone changes a protocol sentence.

Removed or simplified: the two Python-version ineligibility checks of `compare.py` (S runs on two versions, a
sharded run on another version than S); the history of earlier rounds' test results in `README.md`; the separate
lost-step paragraphs in `experiment.json` and "Risks", which now point to `README.md` "Limits".

Accepted residual risks:

- Environmental-fault paths of the oracle, where a runner, image, network or artifact-service fault could reach a
  rule outcome, were searched in the third and fourth review rounds and again in this revision, which examined the
  code it changes: the two new incomplete conditions and the image flag only add incomplete outcomes or flags; the
  removed ineligibility checks are covered by the comparison across runs, which comes first; the lost S step is
  recognised only when none of its files exists; and a failed download of the pinned release stops a job before its
  clock. The search is not exhaustive.
- The interpreter's implementation is not recorded per run; every job's interpreter check asserts CPython before
  its clock starts, so another implementation can only give a run whose test phase never started (incomplete).
- An S step that wrote any of its files before a fault is judged on them: S is ineligible and the OS gets no verdict,
  final. A shard step lost to a runner fault still makes its run ineligible, flagged on one runner image, as preregistered; on more than one image its records differ from the S baseline and the OS is incomplete.
- A macOS image that no longer caches 3.13.15 makes `actions/setup-python` download it before the clock starts; a
  failed download fails the job before its test phase (incomplete).
- Arm runs on different runner images with one runtime are flagged whatever the outcome. An image change can shift
  timing, which n = 3 bounds only loosely (runner noise), and it can flip a test that gates on a tool or version the
  image provides, or make it hang until its step's limit stops the step, which would make a sharded run ineligible
  through a record mismatch that sharding did not cause and give reject or a hand-over to the other arm; since the
  fifth and sixth review rounds, such a mismatch beside more than one image makes the OS incomplete instead, a run
  with a step that never wrote its exit status included (`README.md`, "Limits"). Still accepted: a shard step stopped
  only after it wrote every record it owns (a hang in the last class's or module's teardown, or at interpreter exit)
  leaves records equal to the S baseline, so on more than one image its run stays ineligible and its arm flagged,
  which can still give reject or a hand-over even if the image caused the stop (seventh review round below). Still
  accepted: whether two
  consecutive images differ in a gated tool is unverified. Linux's system python3 is not pinned; the comparison
  across runs covers it.

## Fifth review round (2026-10-03)

An evidence delta review before the first push approved the fourth round's changes and found one high finding, which
predates that round, and one low finding (R5-1, R5-2). This revision, still before any hosted run, resolved them:

- **R5-1.** A runner image provides tools and versions that tests gate on, so a test can run on the image of the S
  runs and be skipped on that of a sharded run; that run was then ineligible through a record mismatch, which could
  give reject or a hand-over to the other arm while the image difference was only flagged. A sharded run whose
  records differ from the S baseline while the arm runs ran on more than one runner image now makes the OS
  incomplete, unless that run is ineligible only through steps that never wrote an exit status (the sixth round
  drops this exception); on one image a record mismatch still makes the run ineligible, and more than one image
  without a mismatch stays a flag.
  `README.md` rule 5, the `quality_rule`, "Decision" above and `decision_rule` list the condition; "Risks",
  `README.md` "Limits" and `experiment.json` limitation [19] name the mechanism.
- **R5-2.** `experiment.json`'s entry for the third round names its two tests that pin kept behaviour:
  `test_a_wrong_recorded_outcome_beside_an_unrecorded_one_rejects` passes on the export of `f0d54bdf`, and
  `test_a_lost_control_step_beside_wrong_recorded_evidence_rejects` gives the kept reject there but errors on the
  `lost_steps` field that the export lacks, so every new test of that round but the first fails or errors there
  (measured again in this revision).

`test_compare.py` has 118 tests after this revision. The new test,
`test_a_record_mismatch_beside_another_runner_image_is_incomplete_not_a_rule_outcome`, fails on an export of the
previous head `d6a8d6ce` with only `test_compare.py` replaced, in its three subtests of the new rule (one sharded arm
differs, which must not hand over; both arms differ, which must not reject; the other image is an S run's), and
passes on this one; its two subtests of kept behaviour (every arm run on one image; a step that never wrote its exit
status, on two images, which the sixth round makes incomplete) pass on both, and the other 117 tests pass on both.
The protocol sentences are unchanged.

## Sixth review round (2026-10-03)

An evidence delta review before the first push found one high and one low finding, both in the fifth round's change
(R6-1, R6-2). This revision, still before any hosted run, resolved them:

- **R6-1.** The fifth round's exception left an image-caused path to a rule outcome open: a test that gates on a
  tool or version of the other image can hang until the shard step's `timeout-minutes` stops the step, which writes
  no exit status, so the run was ineligible only through that step, and the rule could hand the decision to the
  other arm or give reject, with only flags. The exception is dropped: a sharded run whose test phase started and
  whose records differ from the S baseline while the arm runs ran on more than one runner image makes the OS
  incomplete. On one image such a run stays ineligible, and an arm ineligible only through steps that never wrote an
  exit status is flagged when the rule passes over it, as preregistered. `README.md` rule 5, the `quality_rule`,
  "Decision" above and `decision_rule` state the condition in the same words; "Risks", `README.md` "Limits",
  `experiment.json` limitations [5] and [19] and the residual of the fourth round above say so.
- **R6-2.** The flag statements (beside a sharded run whose records differ from the S baseline, the runner images
  also make the OS incomplete) are now true as written, so they are unchanged.

`test_compare.py` has 119 tests after this revision. The fifth round's subtest of a step that never wrote its exit
status on two images now expects incomplete, and the new test
`test_a_shard_step_hung_until_its_limit_on_another_runner_image_is_incomplete_not_a_handover` stops a shard step
inside a hanging test, on two images (incomplete) and on one (ineligible and flagged). On an export of the previous
head `2ad9627b` with only `test_compare.py` replaced, exactly the two subtests on two images fail
(`'adopt' != 'incomplete'`), the new test's subtest on one image passes, and the other 117 tests pass on both. The
protocol sentences are unchanged.

## Seventh review round (2026-10-03)

A narrow evidence delta review of the sixth round's change approved it (no high or medium finding) and left two low
findings, both about this record, before the first push:

- **R7-1.** Dropping the exception also dropped the sentence that accepted the case of a shard step stopped after it
  wrote every record it owns (a hang in the last class's or module's teardown, or at interpreter exit). That case
  leaves records equal to the S baseline, so it raises no record mismatch, and on more than one runner image its run
  stays ineligible and its arm flagged; the rule can still give reject or a hand-over even if the image caused the
  stop. The case predates the sixth round and its code behaviour is unchanged. It is an accepted residual, stated in
  "Risks" above, `README.md` "Limits" and `experiment.json` limitation [5]; widening the incomplete condition to cover
  it (any started sharded run with an unfinished step, on more than one image) is the code option, not taken because
  this is the last round before the oracle freezes and the flag already makes the outcome record address it.
- **R7-2.** The residual about a shard step lost to a runner fault said "ineligible (flagged)" without the two-image
  case; it now says it is flagged on one image and makes the OS incomplete on more than one.

The environmental-fault paths of the oracle (a runner, a download, an upload, a step, a cancellation, a reopen, a
conflict, a crash, a runtime or an image that intervened in one run) were searched in the third to seventh review
rounds, each by a reviewer asked to look for a path to a wrong adopt or reject. Every search found something the next
round closed or recorded, so the search is not exhaustive; the first hosted run is the next test, and the first-run
checklist in `README.md` is what reads it.

## SOTA sources

- github/docs at `c67a9362ec63f3993d095bf70bd11724359cc50e`,
  `content/actions/reference/workflows-and-actions/workflow-syntax.md` lines 1070-1074 (step `timeout-minutes`),
  1078-1086 (`background`), 1107-1168 (`wait`, `wait-all`) and 1193-1224 (`parallel`); at
  `63859c481b2195607ff94c4dda765fb131a34759`, `events-that-trigger-workflows.md` lines 465, 466 (no `pull_request`
  workflow runs on a pull request with a merge conflict), 473 and 484-489; at
  `03d2e24b34bd88c361f1185f0aae1c46062c6510`, `contexts.md` lines 209 (`github.run_attempt`), 384 (`job.status`) and 779
  (`needs.<job_id>.result`). GitHub changelog of 2026-06-25:
  https://github.blog/changelog/2026-06-25-actions-steps-can-now-be-run-in-parallel/
- actions/download-artifact at `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c`, `src/download-artifact.ts` lines 85-95, 149-163
  and 176-246 (a pattern that matches nothing downloads nothing; a missing name fails; lines 186-195: without
  `merge-multiple` each artifact gets its own directory unless exactly one matches); actions/upload-artifact at
  `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, `action.yml` lines 37-42 (`overwrite`).
- actions/languageservices at `880ac43bc39b0fd7b735ff7976044289bbea3724`, `workflow-parser/src/workflow-v1.0.json`
  lines 2168-2197 and 2255-2270 (a step inside `parallel:` may carry an `id`).
- actions/runner v2.337.0 (`397b032cbf865e9c3ddfab89d533ec19325e1273`): `src/Runner.Worker/BackgroundStepCoordinator.cs`
  lines 63, 78, 225, 244-248 and 371-392; `src/Runner.Sdk/ProcessInvoker.cs` lines 443-465, 829-853 and 855-869;
  `src/Runner.Worker/Handlers/ScriptHandler.cs` line 346.
- github/docs at `a3e0414f748215594e8605810f1c7d82cf781683`,
  `content/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs.md`; at
  `336b7f546d9443dab4e1fa4f0f470e45448c7abc`, `data/reusables/actions/actions-group-concurrency.md` line 11
  (`cancel-in-progress: true`).
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
- zizmor 1.30.1 (`docs/usage.md` at v1.30.1, "Parallel steps"; the installed binary for the local probe);
  kjanat/actionlint 1.17.0 (validate.yml lines 71-96).
- The Python runtime (GET requests on 2026-10-03): the actions/runner-images release `macos-15-arm64/20260829.0321`
  (target `55bf90593780b5928df324f55e0bb8f34fb9bc1e`, cached Python 3.13.14 to 3.13.15); at
  `6d942e630479cd99a93dadfc766af11242bfa402`, `images/macos/macos-15-arm64-Readme.md` (image 20260907.0337.1, cached
  Python 3.13.15) and `README.md` line 198 (an image deployment usually takes 2 to 3 days); actions/setup-python at
  `5fda3b95a4ea91299a34e894583c3862153e4b97`, `README.md` line 71 and `src/find-python.ts` lines 102-123;
  actions/python-versions at `52ee1aa09f9f41a759b7a7010eda15fb0e2b190e`, `versions-manifest.json` (3.13.15 for darwin
  arm64 and linux 24.04 x64).
- In-repository: `docs/acceptance-evidence-policy.md` and `docs/lanes.md` (hot-file protocol). Not in this
  repository: plan W1 of 2026-10-03 (a coordinator's approved plan) and the first trial's outcome record
  (`docs/decisions/2026-10-03-suite-parallelism-trial-outcome.md`, on an unmerged branch when this record was written).
