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
  Its other hunk, tagged [src/discover/registry.rs:1536](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/discover/registry.rs#L1536)
  and [1775](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/discover/registry.rs#L1775),
  prevents the hook from rewriting bare grep/rg file-list pipeline producers,
  protecting the prefix header from line-consuming stages; this control invokes
  standalone direct argv and does not enter that hook-rewrite path.
- [3223a80145e482762abbf50ac01656360f906f14](https://github.com/rtk-ai/rtk/commit/3223a80145e482762abbf50ac01656360f906f14)
  prevents folding when raw output contains a carriage return or escape;
  the NUL guard also remains. The tagged guard is
  [search.rs:631](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/cmds/system/search.rs#L631),
  before `lines()` can remove a carriage return. The unchanged unit examples at
  [search.rs:1337](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/cmds/system/search.rs#L1337)
  cover a filename ending in CR and an OSC 8 hyperlink. This repair's native
  fixture exercises the CR filename case.

## Local integration result

At `5a4add33a` (pre-rebase `421e4ee87`, the same patch) on 2026-10-04, the renamed
`rtk-exactness-controls-diff-unchanged-and-grep-fold-lossless` kept both diff
predicates unchanged and compared sorted reconstructed paths with native paths.
The PR #698 follow-up at the pre-rebase review head `45a7218c0` (its registry commit was replaced by `5e6afa4f0` on rebase) now compares the complete sequences
in order. Both plain-list predicates require successful grep exits, three
distinct native paths and the correct header/tail count. The proxy check
continues to require identical output and exits for every case.

Order is part of the documented inverse: tagged
[search.rs:613](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/cmds/system/search.rs#L613)
specifies engine order, [670–674](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/cmds/system/search.rs#L670)
iterates the original paths, and the lossless unit test at 1345–1354 rebuilds
the original string. The integration test's sorted-tail assertion checks
membership; it does not authorize reordering. Matching non-lexical sequences
pass our oracle, while a permutation of the same three paths fails only the
plain-list check. The native run also preserves order. Reconsider this comparison
if unchanged native operands demonstrably produce unstable order across the
three arms; keep that observation separate from permission to reorder the fold.

The new `t6b-grep-non-plain-file-list` uses three explicit paths with a long
shared prefix, including one filename ending in CR. Its check requires the CR
signal and three path records, then compares the entire RTK output and exit to
native. It rejects a guard fixture with no signal and an implementation that
silently drops the CR.

The follow-up adds `t6c-grep-plain-file-list`: the same explicit `grep -l`
operands, contents and shared directory, with only the first filename's CR
suffix removed. A tenth check requires this CR-free sibling to fold and to
reconstruct the native sequence. Its native folded output, beside `t6b`'s
verbatim CR output, makes the guard observation non-vacuous.

Two new rejection tests isolate the previously uncovered terms. All three CR
arms agree and retain the signal while returning either two or four records;
only the LF count check fails. A three-record native list with a duplicate path
and a matching folded/proxy result fails only native distinctness. Deleting one
term at a time turns its corresponding test red while the other test remains
green; restoring both terms passes. These are synthetic local contract checks.

Minimal original red/green streams and acceptance excerpts from job 035, and
the new job 042 streams, are retained in the
[sanitized artifact](../../evidence/artifacts/rtk-051-file-list-control-20261004/README.md).
The artifact includes native grep stdout/argv/hashes, not just check verdicts.
Paths become scope markers; raw conversations and account state are absent.

| Observation | Returned result | Evidence class |
| --- | --- | --- |
| Old assertion with the synthetic 0.51.0 grep shape | One unittest, one failure, exit 1 | Synthetic local contract check |
| Existing native exactness fixture with the old assertion | Fails `rtk-exactness-controls-diff-and-grep-unchanged`, exit 1; reproduces the 60/45-byte grep shape | Local integration of installed upstream CLI |
| Fold repair, before the CR guard addition | Three focused tests pass, exit 0 | Local contract checks |
| Guard test before its fixture/check addition | One unittest, one failure, exit 1: the required guard check is absent | Synthetic local contract check |
| Injected CR in a folded tail before preserving LF records | One unittest, one failure, exit 1: `splitlines()` incorrectly hid the corrupted tail; the inverse now splits only LF | Synthetic local contract check |
| Fold and guard repair | Three focused tests pass, exit 0; malformed headers, missing/extra/duplicate/changed paths, absent folds, CR loss, exit corruption and proxy corruption are rejected | Local contract checks |
| Repaired native exactness fixture at `5a4add33a` (pre-rebase `421e4ee87`, the same patch) | Nine checks pass across 11 cases / 33 arms / 73 commands, exit 0 | Local integration of installed upstream CLI |
| Native distinctness term deleted in job 042 | Two unittests, one failure, exit 1; LF count control passes | Synthetic local contract check |
| LF record-count term deleted in job 042 | Two unittests, two failing count variants, exit 1; distinctness control passes | Synthetic local contract check |
| Same paths reordered under the former sorted comparison | One unittest, one failure, exit 1 | Synthetic local contract check |
| Restored predicates and ordered fold with plain sibling | Six focused tests pass, exit 0 | Local contract checks |
| Job 042 native exactness fixture | Ten checks pass across 12 cases / 36 arms / 76 fixture commands, plus one version command, exit 0 | Local integration of installed upstream CLI |

Independent inspection of the native command records confirms the reconstructed
path sequence, equal native/proxy raw stdout hashes, equal CR-case hashes across
all three arms, and unchanged diff hashes and exits between the failing and
passing fixture runs. The reconstruction test also covers the upstream absolute
prefix/nested-tail example and literal spaces and header-like directory names.
These observations do not substitute for the upstream
Cargo test suite, a new-host installation, or native-model acceptance.

In job 035, the first run of the referencing modules hit environment preconditions: the
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

At repair commit `5a4add33a` (pre-rebase `421e4ee87`, the same patch), `python3 scripts/validate.py` returned exit 1 with
registry drift only: hashes and byte counts for the changed receipt, script and
test module, plus the receipt's appended limitations mirror. After the registry
commit the pre-rebase review head `45a7218c0` (its registry commit was replaced by `5e6afa4f0` on rebase), the unchanged baseline rerun in job 042 returned exit 0:
69 components, 9,897 hashed files, four profiles and 199 receipts. Its first
attempt included unignored job-local upstream downloads and failed publication
path checks; ignoring those private scratch files resolved that failure before
the baseline rerun. This corrects the former unscoped present-tense drift claim.
`manifests/evidence.json` remains coordinator-owned. The earlier repair's
`git diff --check` returned exit 0; job 042 records its own final checks below.

Job 042's first full-module attempt used a private user/mount namespace, but
mount's canonicalization of the saved source descriptor bound the empty new
target to itself. The requested TMPDIR became unavailable and tempfile fell
back to the namespace's `/tmp`; the namespace UID was also zero. That attempt
returned 942 tests, 35 failures, two errors and 35 skips (exit 1), including the
bootstrap's root refusal, npm packing and Git cross-device hardlink failures.
An intermediate retry stopped before tests because the acceptance copy was
unavailable at that empty bind target (exit 1). Adding `--no-canonicalize`,
restoring the original nonzero UID/GID in a nested user namespace and using a
native `git clone --no-hardlinks` copy with byte-identical implementation/test
inputs on the same bind mount resolved those conditions.

The next full run returned 966 tests, eight failures and 35 skips (exit 1).
Only export-canary tests failed: the lexical workspace TMPDIR still spelled a
path under native HOME even though its symlink resolved outside it. Original
`tools/token-e2e/grade.py:1125` deliberately checks both spellings. Setting TMPDIR
to that job path's canonical target then passed all eight affected tests
(exit 0). These corrections change only the acceptance environment; the grader,
its privacy guards, shared `/tmp/.git` and native account configuration are
unchanged. Minimal failed-attempt excerpts and the eight-test pass are retained
in the artifact. The namespace commands use installed util-linux 2.39.3's
[unshare](https://github.com/util-linux/util-linux/blob/v2.39.3/sys-utils/unshare.c)
and [mount](https://github.com/util-linux/util-linux/blob/v2.39.3/sys-utils/mount.c),
with Python's unchanged unittest runner and the existing native fixture.

The final job 042 acceptance command, with the canonical workspace job TMPDIR
inside that namespace, ran `python3 -m unittest tests.test_native_token_ci
tests.test_token_e2e_grader tests.test_adoption_bootstrap_macos
tests.test_agentsview_qualification tests.test_workflow_hardening`: 966 tests,
35 skips, no failures, exit 0. The implementation and all five test modules
were independently compared byte-for-byte with the working tree. The final
native fixture passes ten checks; its original stdout/argv/hashes are retained
beside the terminal streams. Final `python3 scripts/validate.py` returns exit 1
with registry drift only (changed hashes/byte counts, the appended limitations
mirror and new artifact registrations); `git diff --check` returns exit 0.
These working-tree results are separate from the passing pre-rebase `45a7218c0` baseline; after the rebase onto `38ac9aca1` and the registry commit `5e6afa4f0`, `python3 scripts/validate.py` passes (exit 0).

## Residual and completeness critic

Agent-facing expansion of folded paths is unmeasured. An E2E observation of a
model using a wrong expanded path leads to adding `grep -l`/`-rl` to the hook
exclusions. The deterministic inverse and the CR guard pass for the selected
Linux fixtures; this does not measure model interpretation.

The source review covers the tagged implementation, release, both commits
including the registry hunk, the documented ordered inverse, upstream unit
examples and the native grep integration test. The PR #698 follow-up closes
the missed predicate-isolation, explicit-operand fold, order and durable-log
modalities identified in the independent read. The repair covers ordinary grep
folding, malformed/lost-path controls, proxy recovery and CR refusal. Native
`rg`, `grep -L`, NUL/OSC 8 cases, Windows
and macOS, the upstream Cargo suite and model E2E remain outside this bounded
round; retain them as candidate modalities for the next file-list qualification
sweep rather than treating the selected fixtures as their acceptance.

Discovery correction: `tests/grep_forward_args_test.rs` was an incorrect
upstream locator (HTTP 404). The original feac25d commit file list identifies
`tests/grep_faithful_format_test.rs`; that file was then fetched at v0.51.0.
The format and guard claims above use the exact tagged paths linked here.
