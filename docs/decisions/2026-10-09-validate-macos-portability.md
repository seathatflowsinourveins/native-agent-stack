# Repair the macOS validation seams

**CI execution update, 2026-10-10:** [Retire adoption macOS CI](2026-10-10-retire-macos-ci.md)
ends the future adoption-CI execution expectation below. The portable code
repairs remain in place; this policy change adds no native macOS acceptance result.

Lane: foundation. The macOS validation job reached the full repository suite,
then failed on lexical path aliases, Linux-only test instrumentation and native
Linux integration contracts. This change repairs the portable interfaces and
names the platform requirements of the integrations that cannot run on Darwin.
The current main/nightly/dispatch advisory policy remains in force.

## Native failure evidence

The reproduced native failure is main run
[37992778130](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37992778130),
commit `dfeea13377cfb15936f856d9ed8df3c6575a7895`, job
[114030975988](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37992778130/job/114030975988),
step 21, **Run the full test suite (gating on macOS)**. It ran 12,166 tests in
2,428.707 seconds and reported 115 failures, 509 errors and 1,480 skips.

Artifact `11648210573`, `full-suite-macos.log`, is 4,141,374 bytes with SHA256
`8835a4e1902007206028dd18d38e4a3292d589873dd8b08a6eea6793e37e80d5`.
The archived log was parsed in memory through the installed GitHub CLI. The
ordinary step output showed durations and a tail, without the failure headers.

The archive distinguishes the dispatch's aggregate shorthand: 412 headers
belong to the source-policy tests, including 407 failures of their Linux
`/proc/self/fd` watcher. There are six direct readiness failures, including the
SDK path-alias failures. Local-pages refresh contributes 67 strict ancestor
symlink errors from the uncanonicalized temporary fixture prefix. Other
families include Linux sealed descriptors, BSD byte-count padding, Bash 3.2,
frozen WSL commands and a scratch checkout contaminated by the active CI log.
These are counts from this pinned artifact, not a new census of 100 Mac jobs.

## Resolved paths and exact read permissions

The SDK reader checked containment on a resolved path, then called lexical
`relative_to` on the original path. On Darwin, `/var` and `/private/var` can name
the same location while those lexical prefixes differ. The reader now uses one
resolved copy for containment and the relative reference, for both normalized
and raw SDK receipts. Absolute-path and outside-root refusals remain enforced.

The original lexical declarations are retained for the independent source-policy
guard. Its exact caller positions and approved reader digest are updated with
the reviewed bytes. Both the original declaration and the canonical linked
reference require their own role approval; descendant symlinks and `..` selectors
cannot select a different independently approved file. Negative controls exercise
that distinction before any target bytes open.

Trusted temporary fixture prefixes are resolved once in the readiness, pages and
metadata-verifier tests. Explicit symlink regressions still exercise aliases and
escapes. Production page-source ancestor checks remain strict. The metadata
verifier's packet and protocol files are unchanged.

The source-policy watcher now tracks paths from intercepted `os.open` calls and
their directory descriptors. The skill-listing fixture compares `fstat`/`stat`
device and inode identities. Neither needs Linux `/proc` to establish that the
same controlled file was read, and forbidden-open assertions remain active.

## Native execution and cache behavior

Fleet producer execution still requires a sealed, immutable Linux memfd
snapshot. Unsupported systems receive finite unavailable metadata and retain
dated snapshot/Actions observations. A mutable pathname is not substituted for
the execution guarantee. Collection tests retain the real sealed transport on
supported Linux systems and mock that seam only when the native API is absent.
Tests of real descriptors and kernel seals state their Linux requirement.
Snapshot/seal failures and later producer-transport failures have distinct
unavailable reasons; both close the snapshot descriptor and retain fallback data.

Cache temporary creation uses public `os.open` with the checked directory
descriptor, `O_CREAT | O_EXCL | O_NOFOLLOW`, mode `0600` and available `O_CLOEXEC`.
Random names and exclusive creation follow CPython v3.13.16's `_mkstemp_inner`.
Its public `tempfile.mkstemp` has no `dir_fd` argument, which is the demonstrated
gap previously filled by a Linux `/proc` pathname. Collision attempts are bounded
at 100; replacement and cleanup remain bound to the same descriptor. Regression
controls cover collisions, permissions, explicit close-on-exec creation flags and
host-path reopening. Checking `os.get_inheritable` alone cannot establish that
the creation flag was supplied because CPython already returns noninheritable
descriptors. Removing the explicit flag now fails the collision test.

## Shell and workflow boundaries

Both review workflows already used `wc -c`; BSD `wc` pads that count. POSIX `tr`
now normalizes the count before the report notice is formed. A padded-count
fixture failed before the change and preserves truncation checks on both systems.

Frozen Ubuntu/WSL integrations that require GNU date/readlink -m/sha256sum/stat,
Linux namespaces, `/proc`, systemd, GNU timeout or util-linux flock have precise
Darwin or capability guards. Static/event-policy tests stay active. Bash
`inherit_errexit` and compound-test behavior are probed where the actual shell
capability determines coverage; supported modern shells retain the checks.
The frozen commands and their failure semantics are preserved.
Scout alias migration remains portable: Apple's maintained `readlink` implements
`-f` using `realpath`. The fixture root is resolved before it supplies ownership
paths, so an aliased temporary prefix cannot misclassify the previous or current
owner as foreign. The Darwin skip is removed. Claude capture tests name their
actual util-linux `flock` requirement; the Inspector probe names Linux's port
range file and util-linux `setsid`, while its `ss` command remains stubbed.
Fleet's explicit native-platform boundary is included in the existing macOS
selector inventory, as required by its strict coverage-drift check.

The catalog scratch-copy test excludes only checkout-root `full-suite*.log`
runner diagnostics. Nested retained evidence logs still copy. Its filesystem
control reproduced contamination before the change.

Both macOS test modes print `FAIL:` and `ERROR:` headers from their saved log.
The original unittest exit code remains the gate, including a successful run
with no grep matches. Executable workflow fixtures prove failure/error headers
are visible while failed tests still fail the step. Existing advisory event
guards and required contexts are preserved.

## Reproduced checks and limits

| Check | Evidence class | Result |
| --- | --- | --- |
| Two real SDK alias regressions before the reader fix | synthetic/local integration | Two path errors; outside-root refusal controls passed |
| Full readiness module through a symlink `TMPDIR` before repair | synthetic/local integration | Seven errors and two failures, reproducing alias and fixture-hook behavior |
| Readiness module after repair | local integration | 35/35 under normal and symlink temporary prefixes |
| Page refresh through an aliased temporary prefix before repair | synthetic/local integration | Native strict symlink refusal reproduced |
| Pages module after fixture canonicalization and exact reader pin | local integration | 44/44 under a real symlink temporary prefix |
| Metadata-verifier fixture probe controls | local integration | Four fail-before subcases; complete 47-test module passes under an aliased temporary prefix |
| Both workflow diagnostic modes | local integration | Two fail-before subcases; 10 executable workflow checks pass after repair |
| Source-policy and Fleet modules | local integration | 83/83 normally and with symlink `TMPDIR`; missing-memfd simulation has 76 passes and seven specific native integration skips |
| Scout ownership fixture through an actual symlink temporary prefix | synthetic/local integration | Existing test failed for both previous/current owners before resolution; all six ownership cases pass after resolution, with no Darwin skip |
| Fleet producer-launch reason | local integration | New fallback/Actions receipt control failed on the snapshot-only reason, then passed with distinct transport metadata; seal-failure control still passes |
| Default Linux collection transport | local integration | Sealed-receipt control failed with the unconditional transport mock, then passed when normal Linux collection retained its real memfd path |
| Cache creation flag discrimination | synthetic/local integration | Deleting explicit `O_CLOEXEC` in memory fails the collision control; unchanged implementation passes |

The affected-module integration gate, FULL manifest validation and private-name
scan are reported with the PR at its actual head. Linux alias, missing-API and
BSD-output fixtures are simulations of the relevant seams. A post-fix native
Darwin full-suite result is not established by those fixtures or by a skipped PR
job. The next eligible native main/nightly/dispatch job supplies that evidence.

## SOTA sources

- CPython **v3.13.16**, checked against installed Python 3.13.16:
  [pathlib lexical `relative_to` and symlink `resolve`](https://docs.python.org/3.13/library/pathlib.html),
  [Path implementation](https://github.com/python/cpython/blob/v3.13.16/Lib/pathlib/_local.py),
  [public descriptor-relative filesystem operations](https://docs.python.org/3.13/library/os.html),
  and [native API availability](https://github.com/python/cpython/blob/v3.13.16/Modules/posixmodule.c).
- CPython **v3.13.16**,
  [`Lib/tempfile.py`, `_mkstemp_inner`](https://github.com/python/cpython/blob/v3.13.16/Lib/tempfile.py):
  random-name/exclusive/mode-0600 creation. Installed `tempfile.mkstemp` lacks
  `dir_fd`; installed `os.open` supports it. The adaptation preserves the
  existing checked directory descriptor.
- POSIX.1-2024, Issue 8:
  [`wc -c`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/wc.html) and
  [`tr`](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/tr.html):
  supported byte-count and whitespace normalization interfaces.
- Apple **file_cmds**, commit
  [`659a8a301e2acf0343f8b8673a154a2ca4d07084`, `stat/stat.c`](https://github.com/apple-oss-distributions/file_cmds/blob/659a8a301e2acf0343f8b8673a154a2ca4d07084/stat/stat.c):
  the `readlink` entry point accepts `-f` and uses `realpath`. This primary source
  corrects the earlier GNU-only classification of Scout's portable command;
  it is source evidence, not a new native Darwin execution.
- [The native failed Actions run](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37992778130)
  and its pinned artifact above: actual Darwin failures, distinct from local
  simulations. Existing workflow policy is documented in
  [the 2026-10-05 advisory decision](2026-10-05-macos-ci-advisory.md).
- Native source at base
  [`3c01bdddc66896f8e36f9f21d452710808a9557e`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/3c01bdddc66896f8e36f9f21d452710808a9557e):
  readiness reader, source-policy guard, Fleet transport/cache, review workflows
  and frozen Ubuntu/WSL test contracts. Their existing native interfaces and
  ownership checks define the repaired seams.
