# RTK 0.51.0 file-list control: retained output, 2026-10-04

These small sanitized artifacts retain the original terminal evidence used by
[the decision note](../../../docs/decisions/2026-10-04-rtk-file-list-control.md).
Job 035's outputs were copied from its surviving temporary storage. Job 042
repairs PR #698 from `45a7218c0`; it leaves the registry to the coordinator.
The upstream reference is [rtk-ai/rtk v0.51.0](https://github.com/rtk-ai/rtk/tree/v0.51.0),
tag commit `e001f773f80b22b7dc4c7a79521b30e35aaef026`, particularly `feac25d`
and `3223a80`. No credentials or native conversations were read or copied.

Terminal streams retain their returned assertion messages and unittest counts.
Checkout, native-home and owned temporary paths become `<CHECKOUT>`,
`<NATIVE_HOME_PATH>`, `<JOB_035_TMP>`, `<JOB_042_TMP>`, `<JOB_TMP_PATH>` or
`<TEMP_PATH>` (generated paths from the initial tempfile fallback).
The one large job 035 referencing-module stream is explicitly a final-summary
excerpt; its omitted tracebacks are not reconstructed. The native JSON retains
the harness's scope markers and pre-sanitization stdout/stderr hashes.

## Historical job 035

- `job-035-red-unittest.txt` and `job-035-red-native.txt`: the former unchanged
  grep control fails (exit 1) on the 0.51.0 fold. The native stream retains the
  60-byte native / 45-byte RTK shape and matching diff/proxy hashes.
- `job-035-green-fold-unittest.txt`, `job-035-red-guard-unittest.txt`,
  `job-035-red-fold-cr-unittest.txt` and `job-035-green-guard-unittest.txt`:
  the three-test fold repair passes, the absent guard and hidden CR each fail
  one test (exit 1), then the three-test guard repair passes (exit 0).
- `job-035-green-native-final.txt`: nine checks across 11 cases / 33 arms /
  73 commands pass (exit 0). This is local integration, not an upstream suite.
- `job-035-acceptance-native-token-ci-final.txt`,
  `job-035-acceptance-other-referencing-modules.txt`,
  `job-035-acceptance-referencing-excerpt.txt`,
  `job-035-grader-isolated-failure.txt` and
  `job-035-acceptance-validate-final.txt`: the retained 49-test and 290-test
  passes (35 skips in the latter), the historical 914-test / 198-failure
  grader refusal, its isolated example, and the seven registry-drift findings
  before the registry commit. These are historical results, not reruns.

## Job 042 rejection and native checks

The two isolated deletion runs invoke Python's unchanged unittest runner with
`tests.test_native_token_ci.NativeTokenCIContracts.` followed by
`test_rtk_exactness_grep_fold_rejects_duplicate_native_paths` and
`test_rtk_exactness_grep_guard_rejects_wrong_lf_record_count`:

- `job-042-red-distinctness-deleted.txt`: only the native distinctness term is
  deleted, leaving the three-record length check. Two tests run; the duplicate
  test fails and the LF count test passes (exit 1).
- `job-042-red-lf-count-deleted.txt`: only
  `len(non_plain_list["stdout"].split("\n")) == 4` is deleted. Two tests run;
  both wrong-count subcases fail and the duplicate test passes (exit 1).
- `job-042-red-order.txt`: the permutation rejection test fails against the
  earlier sorted comparison (one test, exit 1).
- `job-042-green-focused.txt`: all six fold, guard, order, isolation and
  dispatch tests pass after restoring predicates and adding the plain sibling
  (exit 0). Each isolated malformed fixture fails only its named check.
- `job-042-green-native-final.txt`: the existing `rtk_exactness_fixture(Run)`
  executes the installed CLI. Ten checks pass over 12 cases / 36 arms /
  76 fixture commands, plus a version command (exit 0); owned state is cleaned.
- `job-042-validate-base-after-ignore.txt`: validation of the unchanged
  `45a7218c0` baseline passes after the registry commit (exit 0).

[native-controls.json](native-controls.json) copies the original `Run.command`
records for the version, both-file diff and all three grep cases, plus the
fixture's full check and arm summaries and the source receipt's hash. It omits
the other command streams. Independent inspection of these stdout records
shows that the recursive list preserves the non-lexical native order
`f3.txt`, `f2.txt`, `f1.txt`; the CR explicit list stays verbatim; and the same
explicit operands with the CR suffix removed fold to three ordered tails.
Native/proxy stdout hashes and exits match in every retained grep case. This
inspection is separate from the harness's `passed` fields.

`job-042-environment-failure-excerpts.txt` preserves the initial publication
scratch-file failure, the first namespace run (942 tests, 35 failures, two
errors, 35 skips), an intermediate bind-target refusal before tests, and the
subsequent export-canary failure (966 tests, eight failures, 35 skips). These
are explicitly selected failure/summary lines, not full reconstructed logs.
`job-042-green-export-environment.txt` retains the eight affected tests passing
after canonicalizing the same job TMPDIR. The decision note records the native
namespace, UID and same-filesystem copy corrections and their source. Grader
code and privacy guards were not patched for acceptance.

`job-042-acceptance-unittest-final.txt` is the complete sanitized terminal
stream for the final requested five-module invocation: 966 tests, 35 skips,
no failures, exit 0. It runs Python's unittest runner against a byte-identical
native Git copy from `45a7218c0` with the working-tree implementation/test
changes, a canonicalized workspace job TMPDIR, the original nonzero UID/GID
and a private util-linux user/mount namespace. The shared ancestor Git marker stays
untouched. `job-042-validate-final.txt` retains the final validator's exit-1
registry drift only; the coordinator owns that registration step.

The evidence establishes the selected Linux CLI fixtures and our integration
oracle. Upstream Cargo suites, other hosts, native-model interpretation and
provider token usage remain outside its scope.
