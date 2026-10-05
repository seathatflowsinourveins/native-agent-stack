# PR-0 read-only host recorder

This bounded foundation evidence change implements research unit A's finalized
PR-0. It serves the north-star action of qualifying the native credential guard
and agent shell before PR-1 freezes host-specific launcher reachability, so
subsequent research and historical simulation can use evidenced client settings.

## Decision and sources

Use a checkout-independent Python stdlib probe and plain `kind: host_baseline`
receipts under `evidence/receipts/`. Each host `local_integration` receipt binds the
complete observation artifact and immutable archived source with independent SHA256s.
The historical upgrade sidecar uses the policy's `Independent observation` class
for native histories. Source-file hashes establish archived byte identity, not
which bytes a past Python stdin invocation executed.
It carries no component install stage or pass result. Observation success does
not mean every optional binary or kernel
feature is present. Record all field exits and failures without substituting
24.04 data for either 26.04 host.

The comparison used repository source at
`3b8f9c8a1b938358d65bf422f61592dc3b89407d`, full reads of
`scripts/host_receipts.py` and `docs/contributing-evidence.md`, the finalized unit
A record and `finalize-AB.json` in the coordinator's research directory, and
installed native versions and tagged upstream source. Exact locators and
coordinator commands are in [the recorder guide](../../tools/adoption/host-baseline.md#sources).
The `search-first` skill's scoped repository and primary-source search selected
reuse of the evidence receipt style, Python's `tomllib`/`subprocess`, and the native Linux
Landlock/bubblewrap interfaces. Stdlib-only scripts and unittest follow the
task's explicit constraint and the existing repository test workflow. No new
package or runtime is installed. Registry and external MCP recorder discovery
were not used because deployment dependencies are outside this change's fixed
contract. Scoped ai-memory retrieval was unavailable: the call returned that
MCP approval is required while the session policy never allows approval. Current
canonical source was read directly instead.

Alternatives were a shell probe and a new JSON import path in the receipt CLI.
The probe requires Python 3.11+ with stdlib `tomllib` and `ctypes`; exact Python
versions are not inferred from the Ubuntu release. Its source envelope reports
an unverified canonical-source hash; it cannot attest the executed stdin bytes.
Future captures use a frozen input archive hashed externally by the coordinator.
The receipt CLI currently supports
local command execution only; adding import support would expand this bounded
change. An upstream stdin-capable recorder that preserves the exact fields,
silent privacy failure and full sanitized artifact could overturn this choice
after the same local checks. The repair uses the coordinator-selected plain
receipt format instead of introducing a new import interface or a component
anchor. No existing component acceptance index changes.

## Historical upgrade evidence

The three coordination originals `run.log`, `versions-before.txt` and
`versions-after.txt` for wave2's coreutils-2604 operation were read in full.
The sanitized upgrade receipt preserves only version maps, start/end stamps and
the logged apt exit. The originals contain no exit codes for the before/after
queries or per-utility version commands, so none are invented. It is historical
coordination evidence from NativeStack2604, not a newly executed upgrade or a
current 26.04 baseline. Package versions go from rust-coreutils
`0.8.0-0ubuntu3` to `0.10.0-1ubuntu2~26.04.1`; gnu-coreutils and
coreutils-from-uutils remain at their recorded versions.

## Local controls and corrections

The first two targeted unittest attempts each exited 1: the static scan
incorrectly classified first the literal `sudo` in the defensive deny set, then
the package-name tuple, as invocations. The scan now checks literal argv list
heads and command-shaped strings, plus the fixed
version inventory. Verification is `python3 -m unittest
tests.test_host_baseline_probe -v`; fixture execution also flags any actual
privilege-launcher execution. This was a local test defect, not a capability
finding. The planted-home-path and uppercase-login controls returned exit 3 with
both streams empty, including under optimized Python. Shape, failure retention,
configuration-value omission and file/stdin checksum controls passed on that
first attempt.

The original corrected module ran four tests and exited 0; that result is
historical. The retained r1 stdin artifact from NativeStack exited 0, with Ubuntu
`24.04` and `x86_64` observed. Its 64 observations retain eleven exit-1 results:
the three coreutils package lookups, rust-findutils, sudo-rs, the unavailable
sudoers marker, four optional-binary lookups and the gdb path lookup. The gdb
version call exits 127; the other 52 observations and all 64 date queries exit 0. Landlock
reported ABI 7; bwrap exited 0; ptrace_scope reported 1. The captured user config
has no explicit Codex inherit or allow_login_shell key and no Claude
CLAUDE_CODE_SHELL key. These are recorded gaps for later qualification, not
changes made by this recorder. The original Codex version observation included
its read-only-filesystem PATH-alias warning alongside exit 0; the repair separates
stderr from the version's first stdout line. The actual source
checkout differs from the builder checkout and is recorded separately in the
artifact.

An initial scan over all eight new or changed files exited 1 because the existing
evidence manifest contains one home-path match. A full read of that manifest at
HEAD and comparison of added lines found counts `base=1`, `current=1`,
`added=0`; login counts were all zero. All seven new files had zero login and
home-path matches. Existing unrelated manifest content is preserved.

During read-only source inspection four shell launches returned exit 101 because
the sandbox reported ENOSPC. The context tool also reported ENOSPC. Only this
task's temporary downloaded source caches were deleted; subsequent native
inspection succeeded. Web page opening was unsupported by the search provider;
the named primary sources were fetched directly and tagged GitHub source was
read with `gh api` instead.

## Completeness critic

The inventory covers the requested coreutils/findutils implementations, sudo
identity without execution, other launcher version calls, optional shell
tools, native kernel checks, passwd shell, both clients and selected rendered
user settings. Extra OS-release and architecture observations attribute the
24.04 reference without publishing a machine name. The coordinator's two actual
26.04 artifacts are now retained, bound to their unchanged archived source.
The next sweep must label privileges, TTY and namespace conditions
per host; this baseline establishes neither guard reachability nor fresh-session
effective configuration. User settings alone do not resolve profile overlays,
managed settings, project settings or environment overrides. File metadata alone
does not establish passwordless operation. No extra host was queried in this
builder task.

## Repair round r1

The accepted Opus verdict has no p1 findings. Per the coordinator's receipt
decision, the component `claude-code/install/pass` receipt and its duplicate
host directory are removed. The 24.04 plain receipt uses the existing public
NativeStack identity. Three host receipts and the historical NativeStack2604
coreutils sidecar carry `kind: host_baseline`, execution context or historical
source metadata, limitations and hashes of complete artifacts. The host captures
use `local_integration`; the sidecar's classification is corrected below. No version is typed into
an acceptance result, and the component acceptance index remains unchanged.

The coordinator supplied the unchanged 26.04 captures made with the absolute
WSL executable and `bash -lc`: NativeStack2604 at 2026-10-05T01:02:27Z after F9
apply and StackMeasure2604 at 01:02:53Z-01:02:54Z on that UTC date. Their exact timestamps remain in each field.
The guide records why bare `wsl.exe` and direct `-- python3 -` were inadequate.
The builder reruns only the local 24.04 probe. The archived r0 source's actual
SHA256 matches both supplied self-reported canonical hashes; it is retained as
evidence rather than presented as the repaired probe. That match does not attest
the executed stdin bytes. The r1 24.04 capture is bound to its archived r1 source.

The repaired Codex version value is its first stdout line; stderr stays separate.
The 24.04 execution is inside the read-only client sandbox. Codex's startup
alias write attempt is blocked there; the original native 26.04 captures do not
prove startup had no incidental effects. The probe changes no host settings.
`main()` catches every exception, including `KeyboardInterrupt`, and exits 3
without a traceback. Regression fixtures force those failures with both streams
empty under ordinary and optimized Python, and retain a failing Codex exit
without putting stderr into its version value.
The targeted module passed all seven tests with exit 0. The local r1 stdin
collection exited 0 at 2026-10-05T01:47:45Z; its independently hashed probe
source is bound by the 24.04 receipt. Gdb path lookup exited 1 and its version
command exited 127. The dpkg query retained exit 0 with an empty gdb version;
that does not establish an installed debugger. The time package is observed as
`1.9-0.2build1`, and bwrap reports `0.9.0` on this 24.04 context.

Passwordless sudo is explicitly unknown. The generic recipe link is a criterion
and establishes no per-host acceptance. Root reachability rows remain
`status-unknown` until independently evidenced. The updated probe adds gdb,
launcher-family package versions and bwrap's version. These additional fields
were not collected in the supplied r0 captures, so the 26.04 receipts state that
gap rather than fill it with 24.04 values. StackMeasure2604's retained probe is
now the source for its current rust-coreutils version.

The repair removes the unsupported claim that no privilege launcher executes:
sudo and sudo-rs never execute, other launchers run `--version`, and bwrap runs
`true`. It also removes the uncited distribution-shipping and inventory-tool
comparison claims. The prior ENOSPC report remains historical; r1 uses
`~/.cache/t-pr0-baseline-r1`, outside both the checkout and `/tmp`, for TMPDIR.
The history-squash finding belongs to the coordinator: this builder is explicitly
forbidden to commit or push. Registration is the final file mutation in r1.

The first r1 `python3 scripts/validate.py` exited 1 because the removed component
receipt remains in the coordinator-owned Git index. Its manifest entry is gone
and the worktree file is deleted. An alternate-index rerun was proposed, then
corrected after reading `scripts/validate.py:237`: publication enumeration
deliberately strips every `GIT_` override. The supported `--root` source-archive
mode instead checks an exact export of the proposed publication files, including
untracked additions and excluding the deleted receipt. The real Git index is
unchanged; the coordinator must stage the deletion for the normal worktree
command to pass. No validator code or scope is weakened.

## Review-thread repair t1

All six connector premises were checked against code and committed artifacts at
`68ed2b16045e66599f8a1fa2933adb5f1d6f5a0f`. No capture is replaced or re-executed.
The only host invocation in this round is the authorized 24.04 stdin dry run,
whose output stays in scratch outside the checkout. TMPDIR is `~/.cache/t710t`,
and commands run at nice 19. No other distribution is invoked.

The login gate now inspects observation outputs and stderr as whole tokens or
path components. It omits fixed schema keys, command text and selected OS labels;
it also distinguishes declared executable basenames and leading banner names
from account identities. Parent paths and unexpected returned text remain
checked. The home-path assertion still covers the entire document. Fixtures
cover `ubuntu`, `codex` and `user`, partial-token collisions, genuine uppercase
identity disclosures and login components outside a home directory. Existing
ordinary/optimized-Python silent-failure controls remain in place.

The exact r1 source is archived as `host-baseline-probe-r1.txt` alongside r0.
The three retained host receipts bind immutable archives, so the supported
entrypoint can evolve without changing historical evidence. Their recorded
`probe.output` strings are self-reported canonical-source hashes. Receipt
metadata now states that executed input hashes were not independently recorded
and remain unknown. The updated probe explicitly labels its own canonical hash
unverified, including when additional outer-wrapper bytes are supplied on stdin.
The guide freezes and externally hashes future input bytes with `sha256sum`
before using the same archive as stdin and recording the coordinator's digest.

For future captures, dpkg-query records `${db:Status-Status}` alongside the name
and version, separated by tabs. A query can return exit 0 with an empty version
and status `not-installed`. The retained r0/r1 rows lack the status field;
receipts mark it unrecorded without editing any row or inferring installation.
The historical upgrade sidecar uses exactly `Independent observation` from
`docs/acceptance-evidence-policy.md` for native histories. The three enum classes
in `docs/contributing-evidence.md` and the host-receipt schema apply to component
host receipts; this plain receipt is outside that schema. In `scripts/validate.py`,
`historical_inventory` is a receipt kind, not an evidence class. No enum or
validator is extended.

Python traversed each committed artifact's observations, native exits and nested
date-query exits. These are the retained totals, checked by the targeted test;
they exclude fixture invocations and the scratch dry run:

| Artifact | Observations | Exit 0 | Exit 1 | Exit 127 | Date exit 0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `nativestack-2404.json` | 64 | 52 | 11 | 1 | 64 |
| `nativestack2604.json` | 56 | 50 | 6 | 0 | 56 |
| `stackmeasure2604.json` | 56 | 50 | 6 | 0 | 56 |

Before the fixes, the updated targeted module ran 12 tests and exited 1 with
13 failed subtests/assertions and three missing-metadata errors. The failures
cover common-login rejection, partial-token rejection, mutable r1 source binding,
the unqualified canonical hash claim under modified stdin, missing package status,
stale decision counts and the historical sidecar's integration label. The tests
retain those discriminating controls; this is repository integration and evidence
consistency testing, not upstream or model acceptance. After the fixes, the same
12-test module exited 0. The authorized local stdin dry run exited 0 with one
JSON object, empty stderr, zero case-insensitive login matches and zero home-path
matches. Its output stays in scratch. All five pre-existing files in the artifact
directory, including the three host captures, retain their original SHA256s.
Registration follows the completed source, receipt, documentation and test changes.

## Delta-review repair t2

The Opus delta read accepted t1 without p1 findings and identified four p2 gaps
at `d06098ffb070dacfcbc9a424874de989cb55c8db`. Its banner finding is confirmed
against all three retained artifacts: the NativeStack captures report
`2.1.289 (Claude Code)` and StackMeasure2604 reports `2.1.288 (Claude Code)`.
In each banner the tool name is not leading. The t2 gate exempted declared
tool-name words throughout their version banner and removed matching vendor
tags without limiting them to the first parenthesized group. The t3 review
below showed that these substitutions also erased explicit account forms such
as `USER=<login>` and `uid=N(<login>)`. The t2 fixtures covered the retained
Claude banners, an Ubuntu gdb banner and identity paths, but missed these forms.

The whole-document gate copies the personal-home and Windows-user-path patterns
unchanged from `scripts/validate.py:29-30`. Windows/WSL profile names with suffixes
are rejected regardless of the current login, including when a path appears in
a key or command description. The existing Linux home-prefix check remains.
The t2 gate accepted compound names outside those recognized profile prefixes,
including `<login>-data` and `<login>.HOST`, and only checked the attached option
`-u<login>`. This weakening preserved login `user` on the marker diagnostic but
also admitted account compounds. The t3 repair replaces that policy with a
narrow fixed-marker exemption and stronger compound controls.

All four receipts now contain a dated amendment entry referring to
`PR #710 t1 (7ec3f2a5f) and t2`. The stamp comes from `date -u` and dates this
retrospective entry. It does not backdate the t1 edits or change initial
`recorded_at_utc` stamps. Changed fields are listed; NativeStack's previous
mutable source path and the upgrade sidecar's previous integration class are
retained as prior values, checked against their original receipt blobs at
`68ed2b16045e66599f8a1fa2933adb5f1d6f5a0f`. The guide distinguishes initial
assembly and later amendments, and names the coordinator command as the command
for the two r0 26.04 captures collected in repair round r1.

The discriminating targeted run before these fixes exited 1: 18 tests, 22 failed
assertions/subtests and four missing-amendment errors. It covers the banner,
profile-path, attached-option, amendment and command-wording gaps. The first
post-fix module run exited 1 because its fixture incorrectly required 2.1.289
on StackMeasure2604 too. Direct inspection of the committed
`stackmeasure2604.json` client-version field verified 2.1.288; the fixture was
corrected without changing that artifact. Replaying the corrected banner test
against the unchanged HEAD probe failed all three subtests with exit 1; the
final targeted module passed all 18 tests with exit 0. The local stdin dry run
exited 0 with zero login, home-prefix and profile-path matches and empty stderr.
Both copied regexes match the validator's patterns and flags exactly, and all
six retained artifact files have unchanged SHA256s. TMPDIR is
`~/.cache/t710t2`, outside the checkout, and runs use nice 19. The only native
probe invocation is the authorized local stdin dry run to scratch; historical
captures and archived sources retain their bytes. Registration follows the
completed source, receipt, guide, decision and test changes.

## Delta-review repair t3 (2026-10-05)

The Opus delta read accepted t2 without p1 findings and identified two privacy
gaps at `22ec2b15419cb5f508976bac586aece72c3a7a3b`. Both are confirmed through
the existing `main()` fixture boundary. Before the first fix, all 42 new banner
subtests failed with exit 1: standalone tool-name logins, account assignments,
user options, login-at-host and tilde forms, UID and passwd forms, punctuation
identities, and a vendor label in a later parenthesized group. The t3 gate
checked unstripped values for `USER=`, `LOGNAME=`, `--user=`, `-u <login>`,
`<login>@`, `~<login>`, `uid=N(<login>)`, `<login>:x:` and standalone-login values
before any exemption. Tool-name exemptions required start, whitespace or `(`
on the left and whitespace, `)` or end on the right. A vendor ID had to open the
first parenthesized group. These enumerated checks missed the additional account
annotations and merged-stderr case confirmed by the t4 review below. The
20-test module then passed with exit 0.

The next discriminating run exited 1 with 19 failed compound subtests/assertions
before the compound fix. Casefolded login matching now uses ASCII alphanumeric
boundaries, rejecting punctuation compounds in output and stderr; attached
option checks cover `-[a-z]*u<login>` and `-g<login>`. A separate numeric-suffix
check also rejects `<login>123`. Only the complete fixed marker path is exempt,
so login `user` accepts the real stat diagnostic while a path ending in
`90-wsl-default-user-data` fails closed. There is no blanket path-prefix rule.

The first whole-document replay passed 10 of 15 combinations and exited 1.
The stronger checks found two additional system-label collisions in the original
captures: the default `~/.local/share/codex-ecosystem/bin` launcher parent for
login `codex`, and the numeric version `0.0.0~ubuntu25` for login `ubuntu`.
The five failing capture/login pairs became a regression test, which exited 1
before the scoped exemptions. The exact default launcher parent is now exempt
only in a matching executable lookup; its definition is retained in
`scripts/adoption_status.py:1124-1134` at the t2 HEAD. A distro tag followed by
digits is exempt only inside a numeric dpkg version in a row matching the queried
package. Raw identity checks still run first, and recorded strings are unchanged.
Codex's own `codex-cli` banner brand has the same narrow word bounds as its
tool name. No arbitrary parent paths or compound prefixes are exempted.

The boundary policy still deliberately accepts a login embedded in a longer
ASCII word or preceded by another letter/digit, unlike r1's arbitrary substring
check. The existing `fixture-userland` and `1ubuntu2` controls are system/package
labels that require this distinction. All compound forms listed in the t3 review,
including the numeric-only suffix, now fail closed outside scoped labels.

The final targeted module passed all 21 tests with exit 0. The whole-document
gate passed all three unchanged committed captures with each of `claude`,
`codex`, `ubuntu`, `user` and `alice` (15 of 15, exit 0). The authorized local
stdin dry run exited 0 with one JSON object, empty stderr and zero login,
home-prefix, actual-home and profile-path matches. Its output stays in scratch.
TMPDIR is `~/.cache/t710t3`, outside the checkout, and commands use nice 19.
The three captures, both source archives and upgrade artifact retain their
original SHA256s. The receipts retain their dated amendments. No host is
recaptured; registration follows the completed source, tests, guide and decision.

## Delta-review repair t4 (2026-10-05)

The cross-family verdict at `ce2c11ba0382e9d227f241669f20094a4490edaa` accepted
t3 without p1 findings and identified two p2 privacy gaps. The first is confirmed
with 128 account-annotation fixtures across eight tool-name logins and four
vendor/stderr fixtures. Against the unchanged t3 gate, the three selected test
methods exited 1 with 132 failures; the complete three-capture, five-login matrix
already passed. The account fixtures include numeric ID/group records, spaced
user/group/owner options and assignments, login phrases and build attribution.

The repair chooses the verdict's structural alternative: exempt only a leading
product label instead of extending the identity-form list. An optional GNU
prefix and immediate eponymous group belong to that label; Claude's numeric
version and `(Claude Code)` form its observed leading label. Later text is never
stripped for mentioning the tool name. The vendor tag must immediately follow
the leading tool label on the same line. It cannot erase an ID/group record or
cross the newline between stdout and merged stderr. The three selected methods
then exited 0, including all 15 immutable-capture controls with identical returned
documents and empty stderr. The guide now distinguishes the enumerated raw
checks from the checks on text outside the bounded product label.

The second finding concerns the normalization inherited from r0/r1. Raw substring
replacement changed a prefix-sharing sibling home into a misleading tilde value
before the whole-document gate ran. A new `main()` regression exited 1 with
16 failing subtests: three prefix-sharing paths and an embedded backup path,
each in output, stderr, command text and a key. Normalization now handles only
a value equal to the current home or beginning with its complete component and
`/`. Siblings and embedded references retain their original home path and fail
closed with exit 3 and empty stdout/stderr. Exact current-home and child-path
controls remain valid. The same selected test then exited 0. This changes the
live recorder, preserving both historical source archives and captured values.

The verdict's local stdin dry-run command was run with the updated probe and
TMPDIR `~/.cache/t710t4`, using nice 19. It exited 0 with one JSON object, empty
stderr and zero login, home-prefix, actual-home and profile-path matches. Its
output stays in scratch. The module's tests now retain the full 15-pair matrix.
The t3 intermediate counts above remain historical reported results; the t4
regressions reproduce the new findings against the committed t3 code. Historical
captures, source archives, upgrade evidence and receipt amendments stay unchanged.
Registration follows the completed recorder, tests, guide and decision changes.

## Post-merge privacy repair r5 (2026-10-05)

The t4 cross-family verdict accepted PR #710 with three p2 residuals. Against
main `ec0b8fd821a7b2004c331d2185b33d9e5ed47896`, the new Claude regression exited
1 with three failing subtests: prerelease and build suffixes containing the login
were erased with the leading label. The exemption now retains the entire suffix
for the existing login checks. This keeps the observed numeric/product label
controls and a benign build suffix passing, without assuming a stricter upstream
version grammar. The same regression then exited 0.

The home-path regression exited 1 with 14 failing subtests against the unchanged
t4 normalization: sibling escapes and interior `..` traversal, each in output,
stderr, command text and a key, plus two lexical-normalization controls. Absolute
values with a `..` component now fail closed before tilde conversion. Remaining
absolute paths use Python's maintained stdlib `posixpath.normpath` before the
complete-home membership check; symlinks are not resolved. The implementation
was checked in the installed CPython 3.13.15 stdlib
([python/cpython v3.13.15, Lib/posixpath.py](https://github.com/python/cpython/blob/v3.13.15/Lib/posixpath.py)).
The two dotted/repeated-separator controls return `~/bin/env`, and all traversal
fixtures return exit 3 with empty stdout and stderr. The regression then exited 0.

The existing sibling-home subtests now use the case index instead of the shared
executable basename. A stdlib `TestResult` ID check first exited 1 with eight
duplicates among 18 subtests, then exited 0 with all 18 IDs distinct.

Targeted acceptance passed all 26 module tests with exit 0, including the
unchanged 15-pair committed-capture matrix. The local stdin dry run exited 0 with
one JSON object, empty stderr and zero login, home-prefix and actual-home matches.
Its output stays in scratch under TMPDIR `~/.cache/baseline-privacy-r5`; commands
use nice 19. The six historical capture/source/upgrade artifacts retain their
original SHA256s, and receipts remain unchanged. Registration follows the
completed recorder, tests, guide and decision changes.

## Privacy repair r6 (2026-10-05)

The r5 cross-family read accepted the change with three p2 findings. The fidelity
regression against `26d6bdd7bd9ae5a0ce1c50fce499b8479dc95c6e` exited 1 with 12
failing subtests: normalizing a whole output value collapsed URL separators and
removed a trailing slash from error text. Normalization now uses the existing
stdlib `posixpath.normpath` only for single-line, whitespace-free absolute values.
For other values, a leading complete home prefix is replaced while its remainder
stays verbatim. This chooses the review's bounded alternative without adding a
path-token parser. The same control passed with exit 0.

The traversal regression adds newline- and carriage-return-terminated `..` in
output, stderr, command text and keys. These eight new subtests failed against
the committed r5 probe (exit 1). Checking `/`-delimited components on each line
now refuses them with exit 3 and empty stdout/stderr; the regression exited 0.
The existing sibling, interior-traversal and lexical-normalization controls stay
passing. The guide also narrows its whole-document claim to homes under the
Linux home prefix: an embedded reference to a home elsewhere can survive unless
a profile pattern or login check matches. This corrects the claim without
changing the gate's scope.

A committed unittest now asserts that the sibling-home subtest IDs are unique.
The IDs were already distinct at r5, so this control passes on that baseline
(exit 0). Reintroducing the former shared `env` label in memory makes it fail
(exit 1); the unchanged case-index labels pass (exit 0). These outcomes preserve
the distinction between a new behaviour repair and coverage of an existing fix.

The targeted module passed all 28 tests with exit 0. The six historical artifacts
and four receipts remain unchanged. Commands use nice 19 with scratch under
TMPDIR `~/.cache/baseline-privacy-r6`, outside the worktree and `/tmp`.
Registration follows the completed recorder, tests, guide and decision changes.
