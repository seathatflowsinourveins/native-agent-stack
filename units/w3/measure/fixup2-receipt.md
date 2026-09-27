# PR-A second fixup receipt — 2026-09-27

## Sources and scope

This extends the selected detector without a new dependency. The contract is
[`preregistration.json`, M4](../../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json#L2921-L2930):
all remote fetches, including nested and unclassifiable operations; routed rate
at least 0.9, with excess unknowns incomplete. The detector reference is
[mksglu/context-mode v1.0.169, routing.mjs:788–795](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L788-L795).
The user-required lower bound is a local conservative measurement extension,
not an upstream parser capability.

Read-only research checked the installed context-mode 1.0.169 source, the
[upstream release](https://github.com/mksglu/context-mode/releases/tag/v1.0.169),
and the pinned source. Tag v1.0.169 resolves to
`589d8214d56740a28b5f7bf63167743d586b0b40`; installed and pinned routing sources
have Git blob hash `e92ab46b2faf6597789bdc5eb3a5a90460d9da3c`.

Invocation semantics come from
[Python interface options](https://docs.python.org/3.13/using/cmdline.html#interface-options),
[Node v24.21.0 CLI](https://nodejs.org/docs/v24.21.0/api/cli.html#-),
and [POSIX.1-2024 sh OPTIONS/STDIN](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/sh.html).
Installed Python 3.13.15, Node v24.21.0 and Bash 5.2.21 help corroborate the
stdin, command-string and script-file entrypoints. The GNU Bash manual endpoint
timed out twice; that page was not used as inspected evidence.

The installed skill catalog supplied search-first, diagnosing-bugs, tdd,
context-mode and verification-before-completion. Tests use the already selected
`measureTranscript`/aggregate reporting interfaces and both CLI adapters.

## Dated errata and anti-patterns

The earlier `fixup-receipt.md` remains historical evidence. Its statement that
interpreter heredocs are covered was too broad: ignored stdin was promoted to
confirmed HTTP operations, and interpreter syntax could be lost by shell
heredoc/quote processing. An interpreter name alone does not select stdin as
source. Command-string/module/script-file invocations leave heredoc input as
data. Verification begins with the failing ignored-stdin control in
`tests.test_token_measurement.TokenMeasurement`.

Confirmed-only routed share can hide parser omissions. The conservative gate
must retain every raw HTTP_SCRIPT match not accounted for by executed-text
classification as a possible fetch. These are separate from confirmed
operations, including when the text is only a grep pattern, comment or written
script. The #381 routed-rate gate must read `routed_share_lower_bound`.

## Evidence classes

Test processes use `TMPDIR` and `GIT_CEILING_DIRECTORIES` set to the same
unit-local directory, with `PYTHONDONTWRITEBYTECODE=1`. The covering run used
`tmp`; the full retry used `.pytest_cache/tmp`, as described below. Output excerpts are
sanitized; no private transcript corpus or credential store is read.

**Synthetic fixtures:** failing-first tests exercise static transcript analysis;
HTTP-looking command strings in these fixtures are never executed.

**Local integration:** covering modules, local native RTK replay controls and
workflow checksums will be recorded with returned outcomes below.

**Local measurement:** no new token-savings or private-corpus measurement.
**Unchanged upstream tests:** none. **Live provider execution:** none.

## Synthetic fixture results

The first ignored-stdin test covered 12 invocations across Bash, ctx shell and
ctx batch. Before the fix, all 36 cases incorrectly confirmed one operation:

```text
Ran 1 test in 1.562s
FAILED (failures=36)
AssertionError: 1 != 0
```

The first lower-bound controls failed before their implementation:

```text
Ran 4 tests in 1.115s
FAILED (errors=26)
KeyError: 'fetch_mentions_unconfirmed'
```

Those controls cover the two residual parser omissions across all three shell
carriers, raw versus confirmed counts within a batch, weighted aggregation,
and the earlier pattern/comment/written-script false positives.

Subsequent input-boundary controls went red before the boundary repair:

```text
Ran 2 tests in 2.351s
FAILED (failures=15)
AssertionError: 0 != 1
AssertionError: 1 != 0
```

One trial fixture placed arguments after a different, already closed heredoc
instead of after the tested redirection; it was corrected before implementation.
The corrected ignored-stdin controls explicitly exercise arguments after the
same heredoc redirection, and still failed before the fix:

```text
Ran 1 test in 1.767s
FAILED (failures=9)
```

The first lower-bound green attempt also exposed two incorrect test expectations:
the existing share helper reports four decimals, while the tests compared full
precision fractions (`0.6667 != 0.6666666666666666` and
`0.3333 != 0.3333333333333333`). Expectations were corrected to the established
reporting contract; this did not change the runtime rounding rule.

Final M4-only run, `rtk python3 -m unittest tests.test_token_measurement -k test_m4`:

```text
Ran 11 tests in 5.877s
OK
```

For each C1/C2 omission with one routed fetch: confirmed remote fetches = 1,
unconfirmed mentions = 1, `routed_share = 1`, and
`routed_share_lower_bound = 0.5`. The possible fetch is visible in its carrier
bucket and leaves status incomplete. Comments, grep patterns, written scripts
and ignored stdin give zero confirmed operations, one possible mention, a null
confirmed share and lower bound 0. Retained positive interpreter cases do not
double-count their HTTP matches as possible mentions.

## Local integration results

Final covering command:

```sh
rtk python3 -m unittest tests.test_token_measurement tests.test_skill_usage tests.test_child_usage_suite
```

Returned exit 0:

```text
Ran 133 tests in 24.895s
OK
```

This includes the existing Node suite and native RTK replay controls through
their unittest wrappers. Those replay controls test local hook behavior; they
are not a replay of a published PR or provider execution.

`rtk sha256sum --check --strict SHA256SUMS`, from the workflows directory,
returned exit 0 with all 14 entries OK. The changed module checksum was refreshed
and the changed README added. `rtk node --check` for the module and
`rtk git diff --check` each returned exit 0.

`rtk python3 scripts/validate.py` returned exit 1 with SHA-256 and byte-count
mismatches for seven paths: workflows README, SHA256SUMS, child-usage and
test-child-usage; tests/test_skill_usage.py; and tools/skill-usage README and
skill_usage.py. The three mismatched source/test files not edited in this round
are byte-identical to HEAD; their inventory drift was already in the supplied
worktree. The coordinator owns evidence registration. No manifest was edited.
`validate.sh` was not present in this worktree, so no local wrapper or
publication-replay acceptance is asserted.

The optional full local command, `rtk python3 -m unittest`, was also attempted
under the same isolated test environment. Its context-mode invocation returned
this tool failure without a unittest completion summary:

```text
tool call failed for context-mode/ctx_execute
timed out awaiting tools/call after 300s
```

An explicit longer subprocess timeout did not extend the tool host's RPC
deadline. This attempt establishes no full-suite pass/fail receipt. The
subprocess deadline later stopped RTK but briefly left its unittest child
running. A later host-visible process check found that attempt gone.
The full-suite scratch-copy fixture had recursively copied the worktree into
its own unit-local TMPDIR; that generated tree was removed during cleanup.
No full-suite completion output was recovered.
The
previously supplied 6,633-test run with two failures and 760 skips remains
historical evidence; no causal claim is made about those failures. The
coordinator's full-suite and final publication replay remain unestablished.

For the retry, TMPDIR moved to `units/w3/measure/.pytest_cache/tmp`, with the
Git ceiling set to the same directory. This stays inside the unit while using
the existing exclusions in `tests/test_catalog_freshness_propose.py:721–723,765–767`;
no fixture or runtime code was changed to achieve that isolation. A background
context-mode retry returned only its startup output, so it was stopped without
claiming a completion result. Native-process cleanup could not see the
context-mode process namespace; the owned background tree was subsequently
stopped through that tool's process context. The retained retry uses a managed
tool session so output remains recoverable, with log analysis through
context-mode.

The managed full-suite retry completed with exit 1. Actual returned final
summary:

```text
Ran 6656 tests in 633.902s
FAILED (failures=247, errors=151, skipped=783)
```

Its command was `python3 -m unittest` through `rtk env`, with TMPDIR and the Git
ceiling under the unit's `.pytest_cache/tmp` and bytecode generation disabled.
The final tool chunk truncated intermediate failure traces; the summary above
was retained. Consequently, the captured trace is not a complete inventory of
all failure causes, and absence of a test name in it proves nothing. This run
does not establish passing full-suite or publication acceptance. The covering
133-test result is a separate, complete returned result.

Observed errors in the retained portion include:

```text
ValueError: the temporary directory <worktree>/units/w3/measure/.pytest_cache/tmp must lie outside the state directory and every repository
ValueError: private_output_must_be_outside_git
ValueError: blind answers must remain outside Git
ValueError: private_run_directory_must_be_outside_source_repository
```

These expose full-suite fixtures that require temporary state outside every
repository, whereas this unit requires TMPDIR inside its directory. That
constraint was not relaxed, and unrelated fixture/policy tests were not
rewritten. A retained failure also names the freshness fixture's publication
validator. These examples do not explain every failure; the complete failure
inventory was not retained by the tool. Final coordinator replay and a passing
full-suite receipt remain outstanding.
