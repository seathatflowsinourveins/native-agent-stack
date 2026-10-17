# Opt-in credential-run watchdog TERM grace

The watchdog already accepts a grace argument internally. At current main
`0f4ee075b2ab3af1b099d5ca1ecb8cae02ee3f5b`, the no-flag default is
`TERM_GRACE_SECONDS = 2.0` (`credential_run.py:125`), passed by Watchdog at967
to the TERM-then-KILL loop at934. The dispatch's zero-grace premise does not
match these source bytes. This change preserves that exact existing default,
watchdog program and ordinary process-group cleanup; it exposes a per-call
override rather than changing an existing caller's lifetime.

The sole new CLI form is `credential_run.py ID --term-grace SECONDS -- COMMAND`,
with one separate canonical decimal integer,1-3600. Repetition, fractional/
non-finite/out-of-range values, attached values and missing values refuse
before any inventory/store access. The option does not apply to --check.
No-flag calls still construct Watchdog with its original argument list and
send its original2.0 string. Opt-in calls pass their selected integer only to
their own watchdog. Explicit normal release still disarms it without signals.

The watchdog runs with an empty environment. Its existing EOF behavior sends
TERM to the owned command group, waits the selected grace while checking group
existence, then sends KILL if necessary. This PR leaves that program unchanged.
It also leaves end_group, parent-death behavior, credential lookup/loading,
masking, child scrubbing and must_not_be_set rules unchanged. The small changes
in _main and run_command route only the parsed option. The reviewed diff leaves
those policy functions/constants and the watchdog program unchanged. Semantic
tests exercise synthetic parsing, required-variable refusal, child scrubbing,
must_not_be_set and masking against both the current module and a fixed base
control. Unrelated future edits do not fail a whole-file equality assertion.

K4's new grammar at `scripts/hooks/secret_path_guard.py:3104,3119-3134`
admits exactly the separate bounded integer form. Child arguments after --
retain their existing meaning. The options parity check pins the one addition,
and semantic compatibility cases reuse the existing runner-start, environment,
mention, usage and documentation fixtures. All existing safety checks in that
function remain after the added validation. No other guard rule changes.

## Primary sources and limits

- Linux man-pages6.17, official repository
  https://git.kernel.org/pub/scm/docs/man-pages/man-pages.git at
  `c420f73ec92dacd8c6801283e2e4c47e9a1828b7`:
  `man/man7/signal.7:372,387,403-407` defines TERM versus uncatchable,
  unblockable KILL; the signal-mask section explains delayed delivery.
  `man/man2/kill.2:28-81` defines process/group signal targeting and signal0
  existence/permission probes. The supported os.killpg calls remain unchanged.
- CPython3.12.3 at `f6650f9ad73359051f3e558c2431a109bc016664`,
  `Lib/subprocess.py:2176-2216` supplies supported signal/wait primitives.
  The existing watchdog follows CPython's multiprocessing resource-tracker
  pipe/EOF design, already cited in credential_run.py's source.
- Public mechanism references:
  [signal(7)](https://git.kernel.org/pub/scm/docs/man-pages/man-pages.git/tree/man/man7/signal.7?id=c420f73ec92dacd8c6801283e2e4c47e9a1828b7)
  and [kill(2)](https://git.kernel.org/pub/scm/docs/man-pages/man-pages.git/tree/man/man2/kill.2?id=c420f73ec92dacd8c6801283e2e4c47e9a1828b7)
  at the Linux man-pages pin above establish the TERM/KILL and group-targeting
  semantics. Each future caller must validate its own recovery budget before
  choosing a grace; 630 seconds is an accepted example, not a budget validated
  by this generic tool. Caller validation and wiring remain separate.

These are existing supported mechanisms. The override cannot guarantee
recovery success, alter kernel signal semantics, control escaped groups, or
change the existing PID/group-reuse and parent-death boundaries. It extends
only the watchdog's caller-selected TERM wait. Existing cleanup's2s default
is not broadened. No installation, live command, key, broker or daemon action
is part of this development change. Both families review this shared tool
and guard before adoption.

## Existing caller inventory

The companion JSON indexes all503 references in92 tracked files at the base,
including hidden paths. Literal and aliased executable command builders were
then inspected. Baseline git grep finds zero --term-grace occurrences. The
following are every in-tree CLI construction/use site identified by that
tracked-source audit; all keep their original argv in this PR:

| Site at base | Route | New flag |
| --- | --- | --- |
| tools/adoption/runtime_acceptance.py:134-136 | Slot-backed acceptance command | absent |
| tools/adoption/runtime_profiles.py:1027-1034 | Slot-backed runtime launcher and fallback slots | absent |
| tools/claude-review-worker/worker.py:795-796 | Sandboxed reviewer CLI | absent |
| tools/claude-review-worker/worker.py:1914 | Key availability check | absent |
| tools/credentials/anthropic_key_health.py:193-200 | Check/probe argv builders, executed237/257 | absent |
| blueprints/native-skill-practice/e-series/e1/e1_run.py:100-104 | Promptfoo --slot wrapper | absent |
| tools/credentials/canary_lane_consumer.sh:19-20 | Generated lane canary instruction | absent |
| tools/credentials/canary_workflow.js:17,23 | Workflow probe/check instructions | absent |
| tools/credentials/canary_proof.py:1454-1455 | Generated operator probe instruction | absent |
| tests/fixtures/seq2-launch.txt:391-398 | Historical lane B keyed wrapper | absent |
| tests/fixtures/pre_skip/launch_seq2.py:391-398 | Earlier keyed wrapper fixture | absent |
| tests/test_credential_run.py:186-241,299-305 | Isolated SYN CLI launchers | absent |
| tests/test_anthropic_key_health.py:361-478 | Mock/SYN health command checks | absent |
| tests/test_claude_review_worker.py:934-996,1722,2049,2101 | SYN sandbox/runner fixtures | absent |
| tests/test_e_series.py:1845-1858,1997,2119-2125 | SYN configurable-runner fixtures | absent |
| tests/test_secret_path_guard.py:3513-3618,3842-3934,4993-5046 | Heuristic command-text cases | absent |
| adoption/credential-inventory.json:174-705 | Declarative check instructions, exact lines in JSON | absent |

Module-only consumers do not opt in: scripts/credential_status.py:361 uses
inventory-policy helpers; tools/credentials/canary_scan_worker.py:53 uses
Command/end_group; canary_proof.py:59 uses policy/helpers. The scalar run_command
production caller is _main; its default dispatch remains the original3args.
The existing test helper test_credential_run.py:341-346 calls that native
process API with synthetic state. Non-invocation mentions, documentation,
receipts, archived logs and module imports are retained in the complete JSON
locator index, not counted as live caller adoption. This audit covers this
repository at the stated base; it makes no claim about external private jobs.

## Validation

New fail-first tests use the existing WatchdogTests process-group fixture with
an empty child environment. They execute the new constructor/API path, TERM-
handling and TERM-ignoring children, default2s behavior and successful disarm.
Pure parser tests access no inventory. Guard cases accept1/630/3600 and refuse
all required malformed forms, including first-position options, --check and a
missing separator. Semantic compatibility/parity checks retain the original
rules without freezing whole files. The ignoring-child test checks the actual
watchdog argv is 1, distinguishing the opt-in from the existing 2.0 default.
The full existing credential and privacy-guard suites run as compatibility
checks using their established synthetic fixtures. No real credential store,
credential value or provider is read or printed by the new tests.

Measured compatibility:107 credential/new tests pass;13 new tests also pass
on managedCPython3.12.3. The native guard run has one host-install comparison
failure because this candidate is deliberately not installed, with2 existing
environment skips. Its existing portable CI mode passes90 cases with3 skips
(including that host-install comparison). Skips are not host acceptance.
The first credential run caught the legacy help-line assertion; the original
usage line was retained and a separate opt-in form added before the final pass.
The help/usage output therefore gains two documented lines; it is not byte-
identical, while no-flag execution and default grace are unchanged.

Only arithmetic source metadata is refreshed beyond those production regions:
the guard's installer checksum and its registry row, plus the credential tool's
registry row. Other registry rows and every installer behavior remain intact;
no installer is run against the host. The supported installer tests use their
own temporary homes. Future r4 adoption, shared-lane acknowledgement and both
family reviews remain separate from creating this PR.

## Review-wave test corrections

The ignoring-child regression now asserts that its real watchdog receives the
selected argument `1`, rather than accepting a watchdog that silently uses
the existing `2.0` default. A local negative control discards the override and
the test fails on that exact argument mismatch. The native signal tests still
cover a TERM handler, a TERM-ignoring child, the lower grace bound and disarm.

Whole-file equality assertions were removed from ongoing CI. Existing K4
runner fixtures check the unchanged admission/refusal decisions, and synthetic
policy cases check parsing, required-variable refusal, environment scrubbing,
forbidden names and output masking. The historical base is a fixed semantic
control, not a restriction on unrelated future edits to current source.

The exact original 13-test module ran verbosely against base: 15 failed
assertions and one missing-feature error, including the previously unrecorded
CLI-refusal test. The prepared 14-test module also ran verbosely against base:
17 failed assertions and one missing-feature error; both policy controls and
the existing guard semantic cases pass there. The prepared module passes all
14 tests on managed CPython 3.12.3; the combined credential/new suite passes
108 tests on that runtime. The preparation validator passes with 12040 hashed
files and 240 receipts. The full-review relay adds no production blocker;
these test and documentation corrections form one fold, with a separate
delta review before adoption.

## Follow-ups

- Extend native handler-duration coverage beyond the default grace while
  remaining within a larger selected value. The fold's actual-argv assertion
  already detects a silently ignored override; the duration case is deferred.
- Pin displaced historical line citations in
  `2026-10-08-guard-hook-fails-closed.md:15,141` to their intended version.
  The current grammar docstring now names parse_args instead of stale lines;
  historical documents and frozen snapshots remain unchanged.
- Exact no-flag help/usage text compatibility remains a follow-up: two added
  lines document the option, while default execution remains unchanged.
