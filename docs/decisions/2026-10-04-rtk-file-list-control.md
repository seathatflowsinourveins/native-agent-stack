# RTK 0.51.0 file-list control correction — 2026-10-04

PR #693's `native-token-tools` run 37226622626 failed the historical
`rtk-exactness-controls-diff-and-grep-unchanged` assertion. Its plain grep
fixture returned native exit 0 / 60 bytes / 3 lines, RTK exit 0 / 45 bytes /
4 lines, and a proxy arm identical to native. The diff control stayed identical
in all three arms. This note supplements the dated 0.51.0 qualification receipt;
its historical host claim and earlier evidence remain unchanged.

The coordinator selected option (a): keep the intended upstream behavior and
repair our control. The alternative is to hold RTK at 0.50.0 if the documented
fold cannot reconstruct the native paths. Hook exclusions for `grep -l`/`-rl`
are the overturn action if a later model E2E observation expands a wrong path.
This foundation repair serves reliable context and artifact navigation for
US-equities research and historical simulation.

## Pinned upstream evidence

The installed client reports `rtk 0.51.0`. The GitHub release API reports
publication at `2026-10-02T13:33:54Z` and names both changes in the
[v0.51.0 release](https://github.com/rtk-ai/rtk/releases/tag/v0.51.0).
The tag resolves to `e001f773f80b22b7dc4c7a79521b30e35aaef026`.

- [feac25d15f254dcdbb6c6629b91328a821eb24ce](https://github.com/rtk-ai/rtk/commit/feac25d15f254dcdbb6c6629b91328a821eb24ce)
  folds the shared directory prefix in bare file lists. Tagged
  [src/cmds/system/search.rs:612](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/cmds/system/search.rs#L612)
  documents a `<prefix> (N files)` header followed by N relative tails;
  lines 670–674 emit it. Reconstruction is literal `prefix + tail`, preserving
  nested suffixes without trimming or path normalization. The unchanged
  [lossless unit test at search.rs:1345](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/cmds/system/search.rs#L1345)
  demonstrates this inverse, and
  [tests/search_file_list_fold_test.rs:43](https://github.com/rtk-ai/rtk/blob/v0.51.0/tests/search_file_list_fold_test.rs#L43)
  checks the grep header and complete sorted tails.
- [3223a80145e482762abbf50ac01656360f906f14](https://github.com/rtk-ai/rtk/commit/3223a80145e482762abbf50ac01656360f906f14)
  prevents folding when raw output contains a carriage return or escape;
  the NUL guard also remains. The tagged guard is
  [search.rs:631](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/cmds/system/search.rs#L631),
  before `lines()` can remove a carriage return. The unchanged unit examples at
  [search.rs:1337](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/cmds/system/search.rs#L1337)
  cover a filename ending in CR and an OSC 8 hyperlink. This repair's native
  fixture exercises the CR filename case.

## Local integration result

The renamed `rtk-exactness-controls-diff-unchanged-and-grep-fold-lossless`
keeps both diff predicates unchanged and requires successful grep exits, three
distinct native paths, a header with the correct count, and an exact match
between sorted reconstructed paths and native paths. The existing proxy check
continues to require identical output and exits for every case.

The new `t6b-grep-non-plain-file-list` uses three explicit paths with a long
shared prefix, including one filename ending in CR. Its check requires the CR
signal and three path records, then compares the entire RTK output and exit to
native. It rejects a guard fixture with no signal and an implementation that
silently drops the CR.

| Observation | Returned result | Evidence class |
| --- | --- | --- |
| Old assertion with the synthetic 0.51.0 grep shape | One unittest, one failure, exit 1 | Synthetic local contract check |
| Existing native exactness fixture with the old assertion | Fails `rtk-exactness-controls-diff-and-grep-unchanged`, exit 1; reproduces the 60/45-byte grep shape | Local integration of installed upstream CLI |
| Fold repair, before the CR guard addition | Three focused tests pass, exit 0 | Local contract checks |
| Guard test before its fixture/check addition | One unittest, one failure, exit 1: the required guard check is absent | Synthetic local contract check |
| Injected CR in a folded tail before preserving LF records | One unittest, one failure, exit 1: `splitlines()` incorrectly hid the corrupted tail; the inverse now splits only LF | Synthetic local contract check |
| Fold and guard repair | Three focused tests pass, exit 0; malformed headers, missing/extra/duplicate/changed paths, absent folds, CR loss, exit corruption and proxy corruption are rejected | Local contract checks |
| Repaired native exactness fixture | Nine checks pass across 11 cases / 33 arms / 73 commands, exit 0 | Local integration of installed upstream CLI |

Independent inspection of the native command records confirms the reconstructed
path multiset, equal native/proxy raw stdout hashes, equal CR-case hashes across
all three arms, and unchanged diff hashes and exits between the failing and
passing fixture runs. The reconstruction test also covers the upstream absolute
prefix/nested-tail example and literal spaces and header-like directory names.
These observations do not substitute for the upstream
Cargo test suite, a new-host installation, or native-model acceptance.

The first run of the referencing modules hit environment preconditions: the
requested TMPDIR was physically inside the checkout, so the grader refused
private fixture writes there, and native npm packing failed. The same TMPDIR
path now points to isolated `/tmp` storage, retaining those refusal checks.
The first rerun passed the Git preflight but still had 198 grader failures.
Canonicalizing that same job TMPDIR did not resolve them: independent inspection
found an existing `/tmp/.git` directory. Native `git -C /tmp rev-parse
--is-inside-work-tree` exits 128, whereas the unchanged
`tools/token-e2e/frozen_checks.py:1311` guard refuses any ancestor `.git` entry,
including an invalid one. An isolated failing test reproduces
`E_PATH reason=work_tree`. The guard and shared `/tmp/.git` remain untouched.
The canonicalized referencing-module run returned 914 tests, 198 failures,
35 skips, exit 1; every failure is in `tests.test_token_e2e_grader`. The primary
`tests.test_native_token_ci` module returned 49 tests, no failures, exit 0.
Native npm uses a job-local cache and distinct empty user/global config files;
an intermediate attempt using `/dev/null` for both configs was rejected by
npm as double loading (exit 1). The first publication check also scanned
unignored generated temporary artifacts; those artifacts are now ignored.
All failed outputs remain in the bounded job's temporary storage alongside
the reruns. Provider usage is unmeasured.

`python3 scripts/validate.py` returns exit 1 with registry drift only: hashes and
byte counts for the changed receipt, script and test module, plus the receipt's
appended limitations mirror. `manifests/evidence.json` remains coordinator-owned.
`git diff --check` returns exit 0.

## Residual and completeness critic

Agent-facing expansion of folded paths is unmeasured. An E2E observation of a
model using a wrong expanded path leads to adding `grep -l`/`-rl` to the hook
exclusions. The deterministic inverse and the CR guard pass for the selected
Linux fixtures; this does not measure model interpretation.

The source review covers the tagged implementation, release, both commits,
the documented inverse, upstream unit examples and the native grep integration
test. The repair covers ordinary grep folding, malformed/lost-path controls,
proxy recovery and CR refusal. Native `rg`, `grep -L`, NUL/OSC 8 cases, Windows
and macOS, the upstream Cargo suite and model E2E remain outside this bounded
round; retain them as candidate modalities for the next file-list qualification
sweep rather than treating the selected fixtures as their acceptance.

Discovery correction: `tests/grep_forward_args_test.rs` was an incorrect
upstream locator (HTTP 404). The original feac25d commit file list identifies
`tests/grep_faithful_format_test.rs`; that file was then fetched at v0.51.0.
The format and guard claims above use the exact tagged paths linked here.
