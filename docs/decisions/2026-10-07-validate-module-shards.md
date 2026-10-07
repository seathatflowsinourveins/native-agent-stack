---
status: proposed
date: 2026-10-07
decision-makers: command center
---

# Run hosted validate as module shards with one required result

The landing queue pays the full serial Linux suite for every landing. The
command center's 2026-10-07 directive selects a GitHub Actions matrix over
test-module lists, with a final required check still named `validate`. This
serves the north-star action of finishing the foundation's landing queue before
US-equities research and independent broker paper qualification.

## Superseded instruction and retained evidence

This record supersedes only the Linux `validate` serial-command instruction in
[`2026-10-03-suite-parallelism-trial-outcome.md`, Decision](2026-10-03-suite-parallelism-trial-outcome.md#decision):
both jobs kept their serial commands after the failed unittest-parallel trial.
The earlier record, its reject result, missing macOS verdict, frozen inputs and
observed receipts remain unchanged. The macOS command and every other workflow
job remain unchanged. This adopts GitHub's independent matrix jobs and Python's
native unittest loader and runner; it does not adopt unittest-parallel or send
test objects through a process pool.

The workflow contracts at
`native-agent-stack@b16cb8cf7cb8e37bf0d0edb9924502beb3e6a276:tests/test_workflow_hardening.py:842-859,945-956`,
`tests/test_shell_parser_ci.py:478-482` and
`tests/test_landscape_sweep_skills.py:2477-2481` bind one serial whole-suite
invocation. Their deliberate replacement is a kind 3 contract change: complete
discovery runs once across the matrix, with stronger coverage and result checks.
The PR description lists the affected test IDs individually against this record.
The pin-derived provisioning, ordering, export, full-history checkout and
timeout/faulthandler assertions remain mandatory. Fixture-only input extensions
retain their original pass/fail assertions.

The same kind 3 change applies to
`tests.test_promotion_gate.WorkflowProvisioningContract.test_unittest_step_runs_the_full_suite`.
The command center authorized only that method's serial binding on 2026-10-07;
its neighboring provisioner and every numeric/promotion assertion remain
byte-identical. Its replacement checks unconditional promotion provisioning,
the required final job and actual aggregate coverage/failure controls using the
existing tiny native fixture. This makes the PR `lane:shared`; the trading lane's
acknowledgement is required before merge and is requested by the command center.

## Replacement invariant

The existing job ID `validate` becomes eight matrix cells with distinct shard
check names. Every cell uses the current Ubuntu 24.04 runner, the unchanged CI
requirements installer and the same promotion environment, pinned tree-sitter
parser and pinned Node YAML provisioning. All cells discover the current tree
through Python's native `TestLoader.discover`, including the `load_tests`
protocol. A module added later receives a deterministic shard automatically.
Modules are indivisible discovery entrypoints; an imported test class belongs
to the module that discovered it, and package hooks keep their native suite.

If discovery shows the same test class's origin module under multiple owners,
the helper conservatively assigns the complete native order to cell zero and
reports the other cells as empty assignments. This preserves shared module and
class fixture semantics and multiplicity. It is an explicit serial performance
fallback, not a coverage exception or a claim that the timing target was met.

The assignment uses historical module weights and a positive fallback for an
unmeasured module. Each cell runs only its assigned module suites, in their
original discovery order, using `TextTestRunner`. No test-ID deduplication,
pickling, test pattern filter or maintained manual module inventory is used.
The job's non-test validators, generators and Node contract run once, in cell
zero. Matrix failure does not cancel siblings (`fail-fast: false`).

The final job has the exact check name `validate`, explicitly needs the matrix
and runs with `always()`. It accepts only a successful dependency and a complete
set of shard receipts. The receipts must agree on tree/discovery/assignment;
their executed module union must equal native discovery exactly, each module
once. Missing, duplicate or conflicting receipts and failed, cancelled or
skipped dependencies fail the final check. Native ran, failed, errored and
skipped counts are summed in its summary; expected failures and unexpected
successes remain separate. Logs and partial results remain evidence rather
than being replaced with a passing summary. GitHub documents that a skipped
job reports success, so a conditionally skipped aggregator cannot enforce this
contract.

Module coverage is the native suite attempt, not a claim that a skipped class's
methods ran: unittest can report a class-fixture skip without starting those
methods. Scheduled case identities, native started cases and native skip/error
counts are kept separate. These are cooperative native execution receipts and
consistency checks; arbitrary repository test code runs in the same process.

## Evidence and alternatives

The retained native log of
[run 37653671981, job 112905135751](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37653671981/job/112905135751)
has SHA-256
`b1d2d43e0c9cb6a4a079910707bab69ea5302573c5396c621711b6f1b2c8b643`.
Its native summary is 11,583 cases in 1,524.459 seconds, with 17 failures and
1,034 skips. This is failed execution retained as timing evidence, not a passing
acceptance result. Completion timestamps yield approximate scheduling weights
in `scripts/validate_shard_weights.json`; fixture and import overhead can move
between modules. The largest observed module is about 136.894 seconds. An
eight-way longest-first assignment estimates about 190.557 seconds of test work
in the slowest shard before replicated provisioning and queue overhead.

Eight cells give substantial estimated margin under the requested twelve-minute
push-to-final target while repeating fewer environments than ten or twelve.
The draft's actual hosted run is the timing acceptance; local fixtures and these
historical estimates cannot establish it. A six-cell comparison may be computed
from the same weights without another test run; the hosted record must expose
each cell's provisioning and total duration so the fixed cost is visible.

Rejected alternatives are keeping the serial queue bottleneck, retrying the
failed process-pool trial, manually maintaining test lists, weakening tests or
preserving an unused whole-suite command to satisfy their text checks. No
requirements file, repository setting or required-check name changes.

This final summary supersedes #706's G-6 serial count-reporting step. #706 keeps
its G-1 PR-metadata workflow work and adapts at its own landing turn, rank 38;
this PR changes none of those metadata jobs.

## Overturn

Restore or amend the shard design if native discovery coverage differs, a
module is missing or executed twice, provisioning-related skips grow, the
final job can pass a failed/cancelled/skipped shard, or actual hosted latency
misses the target. A discovered ordering/fixture dependency must be repaired or
kept in one indivisible module, with its failed result retained. Adding cells
or changing weights needs evidence of the bottleneck; it never changes coverage.

## SOTA sources

- GitHub Actions [matrix strategy and failure handling](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations),
  sections About matrix strategies and Handling failures, read 2026-10-07.
- GitHub Actions [needs context](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#needs-context),
  `needs.<job_id>.result` values, read 2026-10-07.
- GitHub Actions [always expression](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#always)
  and [skipped-job status](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions),
  read 2026-10-07.
- GitHub [required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)
  accepts successful, skipped or neutral statuses; the conditions page explicitly
  says a skipped job does not prevent a merge even when required. Read 2026-10-07.
- CPython [unittest discovery and load_tests protocol](https://docs.python.org/3.12/library/unittest.html#load-tests-protocol),
  and [TestLoader/TextTestRunner](https://docs.python.org/3.12/library/unittest.html#unittest.TestLoader),
  the native harness used by the current workflow.
- Existing provisioners and diagnostics:
  `native-agent-stack@b16cb8cf7cb8e37bf0d0edb9924502beb3e6a276:.github/workflows/validate.yml:147-250`;
  previous serial instruction at the same pin,
  `docs/decisions/2026-10-03-suite-parallelism-trial-outcome.md:24-27`.


## Contract changes by existing test ID

These kind 3 entries include indirect changes through the shared suite classifier.
Their provisioning and diagnostic failure controls remain; the new final-step
fixtures reject missing coverage and failed, cancelled or skipped dependencies.

| Existing test ID | Kind | Replacement |
| --- | --- | --- |
| `tests.test_workflow_hardening.WholeSuiteJobsCheckOutFullHistory.test_whole_suite_jobs_set_fetch_depth_zero` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_workflow_hardening.WholeSuiteHeadroomAndDiagnostics.test_every_whole_suite_job_names_its_suite_step` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_workflow_hardening.WholeSuiteHeadroomAndDiagnostics.test_each_suite_lists_its_50_slowest_tests_with_faulthandler_on` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_workflow_hardening.WholeSuiteHeadroomAndDiagnostics.test_linux_suites_abort_five_minutes_before_the_job_limit` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_workflow_hardening.WholeSuiteHeadroomAndDiagnostics.test_validate_uploads_its_verbose_log_even_when_the_suite_fails` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_workflow_hardening.ValidateSuiteStepTracesAHang.test_a_hang_prints_the_hung_test_traceback_and_fails_the_step` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_workflow_hardening.ValidateSuiteStepTracesAHang.test_control_without_faulthandler_the_hang_leaves_no_traceback` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningStepTests.test_provisioning_step_exists_in_the_validate_job` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningStepTests.test_provisioning_step_precedes_the_unittest_step` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningStepTests.test_step_command_is_derived_from_the_pin_file` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningStepTests.test_step_exports_the_directory_through_github_env` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningStepTests.test_step_cannot_be_skipped_or_ignored` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningStepTests.test_the_provisioning_job_is_the_job_that_runs_the_suite` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningStepTests.test_every_whole_suite_job_provisions_the_parser_or_is_a_recorded_gap` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningControls.test_each_mutant_is_reported_in_its_category` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.ProvisioningControls.test_a_scratch_copy_of_the_workflow_without_the_step_fails_the_structure_tests` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.RealRatchetControls.test_the_real_workflows_pass` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.RealRatchetControls.test_a_new_whole_suite_job_in_a_real_workflow_is_reported` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.RealRatchetControls.test_provisioning_a_recorded_gap_job_is_cleared_by_deleting_its_entry` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_shell_parser_ci.RealRatchetControls.test_a_step_that_only_names_the_pin_file_is_judged_by_the_structure_checks` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_landscape_sweep_skills.SkillsYamlProvisioningTests.test_the_validate_job_provisions_the_yaml_pin_before_the_suite` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_landscape_sweep_skills.SkillsYamlProvisioningTests.test_every_whole_suite_job_provisions_the_yaml_pin_or_is_a_recorded_gap` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_landscape_sweep_skills.SkillsYamlProvisioningControls.test_each_mutant_is_reported_in_its_category` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_landscape_sweep_skills.SkillsYamlProvisioningControls.test_the_ratchet_reports_a_new_whole_suite_job_and_a_gap_that_now_provisions` | 3 | Complete module-shard coverage with the original provisioning/diagnostic invariant. |
| `tests.test_promotion_gate.WorkflowProvisioningContract.test_unittest_step_runs_the_full_suite` | 3 | Unconditional promotion provisioning, complete native module coverage and an always-running strict final result. |
