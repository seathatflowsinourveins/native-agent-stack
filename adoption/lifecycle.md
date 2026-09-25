# Native lifecycle and a new PC's acceptance

Use the selected component's [native recipe](manifest.json), the current pin in
[stack.json](../manifests/stack.json), and the stage record in the
[component matrix](../blueprints/token-native-focus/saturation-audit.json).
The matrix covers every selected component. The broader
[decision index](../catalogs/us-equities/decision-index.json) also contains
alternatives and research identities. Current counts are generated in the
HTML catalog (`docs/ecosystem/index.html`, generated with
`python3 scripts/build_ecosystem.py --write` -- not committed, download it
from a `publish-catalog.yml` workflow artifact (7-day retention, `workflow_dispatch`/`v*`-tag runs only) otherwise); installing every
alternative is not a prerequisite for the selected workflow.

An accepted stage means the linked dated operation passed within its stated
scope. `observed_installed` means an executable or library was available; it does
not mean a clean reinstall was tested. `partial_acceptance` keeps a fixture or
backend result separate from an unverified outer integration. `not_established`
is unknown, and `not_applicable` means the selected role has no such lifecycle.
This guide supplies future-host commands; reading or validating it does not run
those commands or turn historical evidence into that PC's acceptance.

The [two-tool clean-prefix receipt](../evidence/receipts/native-token-clean-prefix-20260920.json)
records actual execution of isolated upstream Headroom and jCodeMunch installs,
exact MCP results before/after process restart, and native uninstall. All owned
entrypoints and processes were gone afterward; retained inputs and outputs
survived. Its scoped verification counters and negative full-recovery comparison
are retained separately from the working installation and provider usage.

## Choose the host and retain the inputs

Start with `python3 scripts/adoption_status.py --help` and the selected profile
in [adoption/README.md](README.md). Inspect prerequisites without changing the
system. Linux/WSL recipes and the individual Mac receipts have distinct scopes.
Apple Container is macOS-only; Linux/WSL uses the direct native PostgreSQL recipe.
The published application, Poppler and memory fixtures now have WSL acceptance,
but a complete second-PC recovery of the whole stack remains unestablished.

Create a new private run directory outside the checkout. Set `RUN_DIR` to its
absolute path and retain the selected source commit, lockfiles, release asset,
publisher hash/signature, OS/architecture and native executable versions there.
Use a new versioned tool prefix. An existing prefix is evidence to inspect and
reuse, not something to erase to force a fresh-install result.

For each applicable stage retain the executable and argument vector, working
directory, exit code, start/end timestamps, stdout, stderr and hashes of input
and output artifacts. Keep native output verbatim in private files; publish only
sanitized summaries. Register the result against the component, stage, version
and host. A passed `--version` is an installation check, not functional E2E.

## Install, update and roll back by distribution type

The exact package names and pins remain in [recipes/README.md](../recipes/README.md).
These examples use upstream package managers in isolated prefixes. Their cleanup
commands remove only a deliberately selected disposable tool installation;
application data, native client sign-ins, counters and retained receipts remain.
No cleanup below is a startup requirement for an already working host.

### uv tools

For a new qualification prefix, use uv's supported tool-directory variables.
The Headroom example preserves the tested Python and extras; use the selected
component's own package specification for other tools.

```sh
(
set -eu
: "${RUN_DIR:?Choose a new private qualification directory}"
test ! -e "$RUN_DIR/uv-tools"
test ! -e "$RUN_DIR/uv-bin"
UV_TOOL_DIR="$RUN_DIR/uv-tools" UV_TOOL_BIN_DIR="$RUN_DIR/uv-bin" \
  uv tool install --python 3.13 'headroom-ai[mcp]==0.37.0'
UV_TOOL_DIR="$RUN_DIR/uv-tools" UV_TOOL_BIN_DIR="$RUN_DIR/uv-bin" uv tool list
"$RUN_DIR/uv-bin/headroom" --version
"$RUN_DIR/uv-bin/headroom" savings --json
)
```

Then run the role's real input/output or MCP acceptance with this executable.
`headroom savings` reads the selected native ledger; it is not proof that a
new installation has reduced any request. Use a separate explicit fixture
workspace when exercising compression, and retain the original and recovery.
On retirement of this disposable installation:

```sh
(
set -eu
: "${RUN_DIR:?Select the exact disposable qualification directory}"
test -d "$RUN_DIR/uv-tools"
UV_TOOL_DIR="$RUN_DIR/uv-tools" UV_TOOL_BIN_DIR="$RUN_DIR/uv-bin" \
  uv tool uninstall headroom-ai
UV_TOOL_DIR="$RUN_DIR/uv-tools" UV_TOOL_BIN_DIR="$RUN_DIR/uv-bin" uv tool list
test ! -e "$RUN_DIR/uv-bin/headroom"
)
```

Rollback selects the previously accepted prefix/executable and repeats the
affected functional check. An application built with `uv sync --locked` or
`uv run --frozen` stays in its project environment; `uv tool uninstall` is not
the removal command for that project. Keep its lockfile and environment until
the replacement passes. Never uninstall all user tools to roll back one package.

### npm tools and locked application dependencies

Choose the package specification from its component recipe. `TOOL_PREFIX` must
be an unused versioned directory, and `PACKAGE_NAME` is the package name without
the version suffix when removing it.

```sh
(
set -eu
: "${TOOL_PREFIX:?Choose an unused absolute versioned prefix}"
: "${PACKAGE_SPEC:?Select the exact upstream package and version}"
test ! -e "$TOOL_PREFIX"
npm install --global --prefix "$TOOL_PREFIX" "$PACKAGE_SPEC"
npm ls --global --prefix "$TOOL_PREFIX" --depth=0
)
```

Run the executable from `"$TOOL_PREFIX/bin/"` and the selected acceptance before
pointing any native client to it. Follow the component's documented lifecycle
script policy; a blanket `--ignore-scripts` can omit required native binaries.
For retirement of that disposable prefix's package:

```sh
(
set -eu
: "${TOOL_PREFIX:?Select the exact disposable package prefix}"
: "${PACKAGE_NAME:?Select the package name to retire}"
test -d "$TOOL_PREFIX"
npm uninstall --global --prefix "$TOOL_PREFIX" "$PACKAGE_NAME"
npm ls --global --prefix "$TOOL_PREFIX" --depth=0
)
```

The Next/React application uses its frozen pnpm lockfile and project prefix.
Follow [the WSL application recipe](../blueprints/convergence-practice/wsl-application/README.md)
for native build, schema/type checks and browser E2E. Retain both application
revisions and the database before changing dependencies. Reinstalling global npm
packages cannot roll back a database migration.

### Publisher archives and native source builds

Use the exact upstream release asset and its matching publisher checksum or
signature, then extract/build into an empty versioned prefix. The archive
procedure and retained hashes are in [the native recipes](../recipes/README.md#official-release-archives).
Keep the complete distribution, licenses and runtime resources. The PostgreSQL
and Poppler WSL guides include source/dependency verification and exact clean
build commands; their acceptance is stronger than merely starting `--help`.

These isolated archives have no universal upstream uninstaller. Retire only an
owned launcher or selected client registration after its process has stopped;
keep the old versioned prefix for rollback. If a prefix is eventually deleted,
first establish that it contains only that task's immutable tool files, not a
database, model cache, project checkout or account store. Package deletion was
not required to establish the retained native execution results.

The working WSL vLLM pin remains 0.25.0. Version 0.29.0 failed real startup with
unavailable UVA support. Preserve the accepted environment and model/vector
data; repeating installation until the version number is newer would not
resolve that compatibility failure.

### Switching an adopted component's active version

Everything above keeps the old versioned prefix around "for rollback" as a
manual convention: today, moving a component from one already-installed
version to another means finding and re-running every `ln -sfn` that pointed
at the old prefix by hand, non-atomically, with no record of what changed and
no automatic way back. `adoption/tools/ecosystem-switch`
(`adoption/tools/README.md` has its full command reference) replaces that
manual step for an adopted component, once `adopt --relink` has run for it
once: every consumer -- `bin/*`, a systemd unit, a wrapper script, an MCP
config -- is repointed at `current/<id>` instead of the real
`tools/<name>-<version>` prefix, with no real, resolved path changing (that
one-time migration verifies this itself, `readlink -f` before and after,
before it touches anything). From then on, moving that component to a
different already-installed prefix (the vLLM 0.25.0/0.29.0 case above, for
example, once vLLM is switch-adopted) is meant to be one `apply`, which flips
only `current/<id>` and restarts only the units the component's own
`surfaces[]` name -- never `adaptive-paper-rung1x-20260923-ladder2`,
`ibkr-paper-post-20260923`, `incentive-forward@1330`,
`mover-daily-scan-0925` or `mover-rth-trial-20260924`, which `apply` refuses
to restart under any circumstance.

**Not yet true for an interpreter-hosted service sharing a shared interpreter
(minor finding).** The `unit-restart` health probe (`/proc/<MainPID>/exe`
inside the new root: `apply` restarts the unit and requires the executable it
lands on to resolve under `--to-root`) can never pass for a service whose
entrypoint execs a Python interpreter it does not itself own. On this host
every `tools/vllm-*/bin/python` is a symlink into one shared
`python/cpython-3.13.15-linux-x86_64-gnu/bin/python3.13`, outside any single
`tools/vllm-<version>` root, so `path_is_under(exe, expected_root)` fails no
matter which vLLM version is live -- an `apply` would restart the model
service twice (once forward, once on the automatic rollback its own failed
probe triggers) and still exit non-zero. `UnitRestartTests`' own fixture
works around exactly this by copying a real, separate interpreter binary into
each versioned root rather than symlinking a shared one; vLLM's real install
does not do that today. Until it does (a private interpreter per version) or
this probe gains an alternative for that shape, vLLM stays a `pending`
`candidates[]` entry rather than a switch-managed component, and this
paragraph's "one apply" is the target design, not yet the demonstrated
result.

**Staging a new version for `ecosystem-switch` to adopt.**
`bootstrap-linux.sh --tools-suffix -rDATE` installs beside an already-adopted
version instead of over it (`tools/<id>-<version>-rDATE` rather than
`tools/<id>-<version>`) without touching that component's `pin`/lock records,
so the two prefixes coexist until `plan`/`apply` above flips `current/<id>`
between them. `--tools-suffix` alone still repoints the *canonical* `bin/*`
symlinks at the freshly staged prefix directly (every `install_*` function
links into `bin_dir`, which defaults to `ECO_INSTALL_ROOT/bin`, unless told
otherwise) -- it does **not** by itself keep a staged run from touching the
canonical links; only `--no-link` or `--link-dir DIR` actually isolate a
staged run's symlinks from the live `bin/*`.

`--no-link` installs the versioned root only and creates no `bin/*` symlink
for it at all -- but this is not full isolation for every pin kind (minor
finding). A uv-tool-kind pin's own tool environment lives at
`$ECO_INSTALL_ROOT/python-tools<suffix>` (`UV_TOOL_DIR` in
`install_uv_tool`), and `<suffix>` is empty unless `--tools-suffix` is also
given; `--no-link` alone keeps `uv`'s shim out of the shared `bin_dir` (uv
still "manages its own shim directory" under the staged prefix), but without
`--tools-suffix` too, `uv tool install` still runs against the *live*
`python-tools/` environment the live `bin/*` shims already use, even though
no new symlink is created there. Pair `--no-link` with `--tools-suffix` when
a uv-tool-kind pin must be fully isolated, not `--no-link` alone.

`--link-dir DIR` writes the symlinks themselves under `DIR` instead of the
canonical `bin_dir`, and the generated report's own listing reflects that;
the report *file* itself (`installed-versions<suffix|.staged>.txt`,
`versions_log_path` in `bootstrap-linux.sh`) is always written under
`$ECO_INSTALL_ROOT`, regardless of `--link-dir` -- `--link-dir` relocates
what the report lists, never the report file's own location (minor finding:
this page previously said `--link-dir` redirects "the reported
`installed-versions*.txt`" itself to `DIR`, which it does not).

Pair `--tools-suffix` with `--no-link` and/or `--link-dir` when the intent is
exactly "stage a root beside the live one, for `ecosystem-switch` to adopt
later" rather than "switch to the new version immediately by re-running
bootstrap" -- the second is also a valid, simpler path for a component
`ecosystem-switch` does not manage yet, but it is the old non-atomic,
non-ledgered `ln -sfn`-by-hand replacement this tool exists to retire, not a
mix of the two.

**Ledger.** Every operation `apply`, `adopt --relink` or `rollback` performs
appends one entry to `$ECO_INSTALL_ROOT/switch/ledger.jsonl`: a 0600,
append-only, newline-delimited JSON file, each line hash-chained to the one
before it (`hash = sha256(prev_hash + canonical_json({seq, txn, op,
component, surface, from, to, pre_sha256, post_sha256, backup, receipt,
window, rollback_class, actor, at_utc, prev_hash}))`, genesis `prev_hash` 64
zero characters). `$ECO_INSTALL_ROOT/switch/state.json` (each component's
current root, each transaction's status) is always recomputed from this
ledger, on every command that needs it -- it is derived cache, never the
source of truth, and is never hand-edited. `ecosystem-switch verify --json`
independently re-derives the whole chain and reports a broken link, a
mismatched entry hash, or a live root that no longer matches what the ledger
last recorded, rather than trusting a cached summary.

Major finding (round 8): a component's derived "current" root used to stay
stuck at whatever value it held before a `link` entry's own reversal
*removed* current/<id> entirely (a relink's first-ever forward entry always
has no prior value, since current/<id> did not exist before it, so rolling
it back unlinks it rather than repointing it) -- the derivation skipped
updating "current" whenever the touching entry's own recorded value was
empty, rather than recording that emptiness itself, so `status`/`verify`
could report a stale root for a component whose live current/<id> no longer
existed at all after its only-ever `adopt --relink` was fully rolled back.
Fixed by recording that value -- including "none, not linked" -- exactly
like any other.

**Windows.** `apply --window NAME` requires
`$ECO_INSTALL_ROOT/switch/windows/<name>.json` (`{name, start_utc, end_utc,
allowed_components}`) to name the switching component and to be open right
now; a maintenance window for a component that also has a live service (an
`unit-restart` surface) additionally gates that restart on
`/proc/meminfo`'s `MemAvailable` staying above a floor (default 6 GiB), so a
version switch never restarts a model-loading service while the host is
already under memory pressure.

**Rollback.** `apply` itself runs a post-switch verify and, on failure, rolls
back every operation of that one transaction in reverse order automatically,
in-process, before it ever returns to the caller. A service's `unit-restart`
step is always reversed only *after* its own `link` (never restarted while
`current/<id>` still points at the new root, which would leave the unit
running the new build with the link pointing at the old one); its health
probe on rollback compares against that `link`'s own recorded old root, not
the pre-restart MainPID string the ledger's `unit-restart` entry itself
carries (which is never a root path and could never have matched). A
`unit-restart` step that reaches `systemctl ... restart` before failing --
either the command itself exits non-zero, or it exits 0 but the post-restart
health probe rejects the result -- is still ledgered before `apply`
re-raises (major finding), because the restart is a real side effect even
though it failed: without that entry, an automatic rollback would revert the
`link` but never try restarting the unit again, leaving it running the new
(or a crashed) build while the ledger says `rolled_back`. `apply
--confirm-within SEC` additionally schedules `systemd-run --user
--on-active=<SEC>s --setenv=ECO_INSTALL_ROOT=... -- ecosystem-switch rollback
--txn T --if-unconfirmed` (every test-stub variable in play is forwarded the
same way, so the timer acts on the same root and stubs the run that
scheduled it actually used), so an operator who never runs `confirm --txn T`
gets an automatic revert once that window elapses, without needing to stay
attached to watch it. Round 9 (major finding): that callback used to take
`switch.lock`/`bootstrap.lock` the same non-blocking way every interactive
command does, so a lock merely busy for a moment at the exact instant the
timer fired (another `ecosystem-switch` command, or a `bootstrap-linux.sh`
run, which holds `bootstrap.lock` for its whole duration) lost the revert
for good -- nothing else in the tool ever re-fires it. `--if-unconfirmed`
now waits out a busy lock for up to
`ECOSYSTEM_SWITCH_IF_UNCONFIRMED_LOCK_WAIT_SECONDS` (default 300s) before
giving up with the same exit 75, and the transient unit itself carries
`Restart=on-failure`, `RestartSec=30` and a `StartLimitIntervalSec=`/
`StartLimitBurst=` pair sized to keep retrying for at least the operator's
own `--confirm-within` window, so systemd itself retries a 75 exit rather
than the callback being a genuine one-shot. `rollback ID` (no `--txn`)
targets that component's
most recently applied, still-standing transaction with at least one
reversible operation (by each transaction's own earliest ledger entry --
never by sorting transaction-id text, which sorts a plain `apply`
transaction's id after a `relink-`-prefixed one regardless of which actually
happened more recently, and round 7: never by raw last-touched ledger
sequence either, which lets an already-rolled-back transaction's own later
rollback entries out-rank a still-standing one, nor without restricting the
candidates to transactions still standing at all -- a rolled-back/superseded/
non-transactional `baseline`/`resync`/`prune` record carries nothing left to
reverse). Round 8 (minor finding): once a component has EVER had a real
`apply` transaction (whatever its current status -- an already-rolled-back
one still counts, so a further bare call past it stays a no-op rather than
falling through), the bare form is restricted to `apply` transactions only
and never automatically reaches the one-time `adopt --relink` migration
underneath, even once every apply is itself rolled back -- a repeated bare
`rollback ID` used to keep cascading past that point, tearing down
current/<id> and every entrypoint's indirection through it, after which
`apply`/`adopt --relink` refuse until someone relinks by hand, contradicting
"a second, redundant rollback ... is a clean no-op" below. A component that
has only ever been relinked keeps targeting its relink the same as always
(the bare form is the only way to undo it at all in that case); an operator
who wants to undo a relink migration once an `apply` also exists can still
do so explicitly with `rollback --txn <that-id>`. `rollback --txn T` also
refuses a txn ANY later, still-standing
transaction on the same component has since moved past -- round 7: purely by
ledger order and each candidate's own recorded status, never by reading the
live `current/<id>` link, which used to let two DIFFERENT later transactions
that coincidentally shared a value fool this check into reporting "not
superseded" (an A-B-A history: v1->v2, v2->v3, v3->v2 again) and clobber the
still-standing newer one; the operator rolls back every later standing
transaction first, newest first, before an earlier one becomes reachable
again (reports `already_superseded` rather than an error if `recover`,
below, already closed T that way itself) -- or whose live target no longer
matches what this same rollback's own `link` operation last set it to (a
compare-and-swap precondition, round 5: something else changed it since,
e.g. an out-of-band relink or bootstrap re-run, and overwriting that
unnoticed change is worse than refusing -- round 6: relaxed to also accept
the live target already matching what THIS reversal would itself restore, so
a rollback interrupted partway through, or run a second time after it
already finished, is idempotent and resumable rather than refused as if
something else had drifted it -- round 7: every one of a transaction's own
link/text-replace/file-write entries still needing reversal is checked this
way BEFORE any of them are touched, not just the one about to be reversed,
so a doomed rollback (its current/<id> link -- always reversed LAST, since
it is always a relink's first forward entry -- would fail this check)
refuses whole instead of leaving every earlier entry already reversed and
ledgered first -- round 8: that all-entries check now simulates the same
reverse walk the actual reversal loop uses, carrying each entry's own
post-reversal value forward to the next, older entry sharing its surface,
rather than comparing every entry independently against today's untouched
live bytes, which used to falsely refuse two entries of one transaction that
chain on the same surface even though the real reversal loop would complete
them correctly).

The superseded-refusal above (major finding, round 8) applies to a
transaction of ANY kind, including `adopt --relink` -- it no longer matters
whether the transaction being rolled back itself ever became the component's
own current/<id> setter. A relink performed while current/<id> already
exists only re-links entrypoints/surfaces (relink links current/<id> itself
only when it is absent), so round 7's version of this check -- gated on the
transaction setting current/<id> -- treated such a relink's own rollback as
exempt even while a later, still-standing `apply`/`relink` on the same
component stood: `rollback --txn` on it exited 0 and moved an entrypoint back
to a direct, unindirected target while current/<id> (and the ledger) still
named the later change as active. Round 8 also drops a resync's own power to
supersede a rollback on its own (round 4): a resync never itself changes the
live value (it only ever re-records whatever is already there), so it never
needed this special case to protect against clobbering a genuinely different
out-of-band value -- the compare-and-swap check above already does that,
resync or not -- and the special case went on to block a still-pending
transaction's own confirm-or-revert timer even when a resync merely
re-observed the exact value that transaction itself had set.

The `rollback:intent` audit marker recorded at the start of every reversal
(see `recover` below) is now written only once the superseded-refusal and
all-entries checks above have BOTH already passed (round 8 major finding):
round 7 wrote it first, before either check ran, so a rollback either check
went on to refuse still left the marker behind -- and the marker is
load-bearing (`confirm` refuses any transaction that carries one; `recover`
stops treating an `in_progress` transaction as a plain crashed apply once it
exists), so a transaction refused that way could never be closed by a retry
of `rollback`/`recover` (refused the same way every time, nothing about the
drift or the superseding transaction having changed): a permanent wedge.

`confirm --txn T` refuses
a txn that was already rolled back, whose post-apply verify already failed,
that is still `in_progress` (a crashed or interrupted `apply` that never
reached its own post-apply verify), that has a `rollback:intent` recorded
against it with no matching `rollback:done` (round 7: an interrupted or
in-flight rollback of an otherwise `applied`/`pending_confirmation`/
`verify_failed` transaction -- recompute_state leaves that status exactly
where it was until `rollback:done` is actually reached, so nothing else
catches this, and the Busy message a stacked `apply` gets names this same
`confirm --txn` as one way to close an open transaction), or that `recover`
has already closed as `superseded` -- confirming any of those would mark a
half-applied, half-reverted or already-superseded component "applied"
through the ledger alone.

**At most one open transaction per component.** Coordinator decision on the
txn state machine (round 5): `apply` and `adopt --relink` both refuse (a
busy-style `EXIT_BUSY`, the same 75 the `switch.lock` flock uses, naming the
open txn id) to start a second transaction on a component that already has
one `in_progress` or `pending_confirmation`. This is what closes the major
finding that a second `apply` on top of an unconfirmed one (A1 v1->v2
`--confirm-within`, then A2 v2->v3, nothing refusing it) used to defeat
confirm-or-revert outright -- once A2 itself reverted, A1's old root was
unrecoverable through either `rollback --txn A1` (refused as superseded by
A2) or `rollback foo` (which kept re-selecting A2). The operator closes the
open transaction first: `confirm --txn ID` (`pending_confirmation` only),
`rollback --txn ID`/`rollback <component>` (either state), or, for an
`in_progress` one left by a crash, `recover`.

Round 8 (major finding; invariant (a) in tests/test_adoption_switch_model.py):
"open" also covers a transaction whose OWN rollback started (a
`rollback:intent` with no matching `rollback:done`) but never finished, even
though its status is `applied`/`pending_confirmation`/`verify_failed` rather
than `in_progress`. Without this, a fresh `apply` could proceed on the same
component while an earlier transaction's own interrupted rollback sat
unresolved, becoming the component's new standing baseline on top of the
half-reversed earlier one -- after which resuming (or `recover` finishing)
that earlier transaction's rollback is correctly refused as superseded (it
would now clobber the new baseline), but it can never be closed the other way
either (closing it as `superseded` deliberately refuses once a transaction's
own rollback has already started -- a partial reversal makes "closing without
touching anything" untrue). Left with neither path, the transaction -- and
every later `apply`/`adopt --relink` on the same component, refused by this
same guard -- was stuck forever. Closed by refusing the fresh `apply` that
would have created the unresolvable state in the first place: an operator now
resumes or otherwise reconciles the interrupted rollback before a new
`apply`/`adopt --relink` is allowed to build on top of it.

A crashed or interrupted `apply`/`adopt --relink`/`rollback` never completes
after the fact. Round 7: `recover` reconciles two DIFFERENT crash shapes, not
one -- a previously-unresolved finding this separates rather than
conflating. The ordinary one is a transaction still `in_progress` (a crash
mid-`apply`/mid-`relink`, or an in-flight rollback of one that never itself
reached its own post-apply verify): `ecosystem-switch recover` finds every
one of those and closes each, either by rolling it back (nothing later
touched its component) or, when a *later* transaction on the same component
is still standing (round 8: literally the same ledger-order-and-status check
`rollback --txn` itself uses to refuse rolling back a superseded transaction,
not a separate read that merely agreed with it in practice -- round 7's own
version of this read the component's own last-recorded current-setting
transaction directly instead), by closing it as
`superseded` without touching anything -- accepting that later,
already-verified state as authoritative rather than clobbering it. Before
this split existed (round-5 finding), the superseded case was only ever
*refused*, never closed: since nothing else ever moves a transaction out of
`in_progress`, that refusal left it stuck forever, and with it, the
open-transaction guard above permanently refused every later `apply`/`adopt
--relink` on that component -- a safety fix that had turned into a permanent
denial-of-service against the very component it was protecting.

The second shape (round 7, previously-unresolved finding) is a transaction
that already reached `applied`/`pending_confirmation`/`verify_failed` -- not
`in_progress` -- but has a `rollback:intent` of its own recorded with no
matching `rollback:done`: a crash mid-`rollback` of an otherwise-normal
transaction (a manual `rollback`, or the confirm-or-revert timer's own
`--if-unconfirmed` call, not a crashed `apply`/`relink`). recompute_state
leaves that transaction's status exactly where it was until `rollback:done`
is actually reached, so the ordinary `in_progress` scan above never revisits
it at all -- this is the crash shape recover's own docs used to claim it
reconciled unconditionally ("mid-`rollback`") without actually doing so.
`recover` now always finishes this second shape's rollback the same
idempotent, resumable way (never `superseded`: that outcome's whole premise
is a transaction that crashed before its own post-apply verify ever ran, no
longer true once its own rollback may already have partially reversed it).

`recover` reports each transaction it reconciled under `recovered_txns`
(rolled back, either shape) or `superseded_txns` (the first shape only,
closed without touching anything), and any genuine problem (e.g. a
rollback's own compare-and-swap refusal above) under `rollback_problems` for
the operator, while it keeps reconciling every other unfinished transaction
in the same run. Round 6: `rollback`'s own reversal (the "rolling it back"
branch above, also used directly by a manual `rollback`) is idempotent and
resumable -- an interrupted rollback (the process was killed partway
through, not the apply/relink it is reversing) is resumed from whichever of
its operations the ledger already shows reversed, rather than refusing on
what used to look like drift; a second, redundant `rollback` of an
already-finished one is a clean no-op the same way. Round 7: a unit-restart
reversal that already soft-failed once is still never retried by a resumed
call (retrying a restart that already failed once is not this resumability
feature's job), but that outstanding failure is now re-reported in
`rollback_problems` on every later call instead of being silently treated as
resolved.

**Prune.** `prune --list` reports which `tools/<name>-<version>` prefixes no
`current/<id>` link points at, that are not the previous root of any
transaction still eligible to be rolled back (a pending or already-applied
transaction's own rollback target stays live until that transaction is
actually rolled back OR closed as `superseded` by `recover` -- once
superseded, that transaction itself can never be rolled back, so its own
previous root is no longer a live target either, the same as an
already-rolled-back transaction's), and this tool's own
reduced-scope in-use check (PATH entries, `bin/` symlink targets, this
user's own running processes' exe/cwd/cmdline, this user's `systemd --user`
unit file text, and -- previously-unresolved finding -- the wrapper-script
text under `wrapper_scan_dirs()`, default `~/codex-ecosystem/bin`, override
`ECOSYSTEM_SWITCH_WRAPPER_DIRS`) does not find referenced elsewhere;
`prune --apply ROOT --reason TEXT` removes one such prefix and records the
reason on the ledger. The wrapper scan is what now catches `gitleaks-guarded`
and `mcp-inspector-2.7.0-guarded` hard-coding a `tools/<root_name>` path with
no `bin/` symlink, unit file or PATH entry naming it at all (verified
read-only against this host's real `~/codex-ecosystem/bin`). This in-use
check is still deliberately narrower than `bin/ecosystem-wave-retention` on
the host (which additionally inspects mounts, symlink hops and a citation
search across evidence repositories, and this tool's own check cannot see a
hard-coded root inside a wrapper script *under `adoption/tools/` in the
catalog checkout*, since it only ever reads `$ECO_INSTALL_ROOT` and
`wrapper_scan_dirs()`, never the catalog checkout itself): treat an
"eligible" prefix here as a lead worth checking by hand before deleting it,
not a proof that nothing on the host still needs it, and extend this check
with that script's fuller technique before relying on it unattended.

Component coverage today is intentionally partial: `adoption/pins-linux-x86_64.json`'s
schema_version 2 migration gave every one of its 14 existing pins the fields
`ecosystem-switch` needs (`root_name`, `current_link`, `entrypoints[]`,
`surfaces[]`, `state_dirs[]`, `window`, `rollback_class`), but none of those
14 is a live service with an external hard-coded root today, so none of their
`surfaces[]` is populated yet. The actual hard-coded-root consumers this
page's own Facts (see the sota-rollout-20260925 `switch` track brief's Facts
section, `docs/tasks/sota-rollout-20260925/briefs/switch.md` in the sibling
`agent-lab-sota-rollout` checkout that planned this work -- not a path in
this repository) named -- vLLM, the Gitleaks/mcp-inspector/serena-context guarded wrappers,
Dagu, and the adaptive-paper `*/frozen/*` launchers -- are recorded as
`pending` `candidates[]` in that same pins file rather than given fabricated
`surfaces[]` entries; a later qualify wave should give each one a real pin
and real `surfaces[]`, informed by that host script's fuller in-use
technique for `prune`, before `ecosystem-switch` manages them.

## Native client integration and process lifecycle

Register only the selected tool in the intended native client/project. Inspect
the returned configuration and run a real operation with a fresh connection.
Existing Desktop processes can retain an older loaded connection. The
[Context Mode/jCodeMunch recipe](../recipes/README.md#focused-jcodemunch-retrieval)
and [client receipt](../evidence/receipts/native-token-focus-clients-20260920.json)
record exact project-file and symbol content returned through both clients.

For retiring a registration previously created by the corresponding upstream
command, inspect it first and remove that exact name from that same scope:

```sh
(
set -eu
: "${SERVER_NAME:?Select the exact Codex registration to retire}"
codex mcp get "$SERVER_NAME"
codex mcp remove "$SERVER_NAME"
codex mcp list
)
```

For Claude, choose the same `local`, `project` or `user` scope used at registration.
The jCodeMunch recipe uses `local`; removing a `project` entry would not retire
that registration.

```sh
(
set -eu
: "${SERVER_NAME:?Select the exact Claude registration to retire}"
: "${CLAUDE_SCOPE:?Select the original local, project or user scope}"
case "$CLAUDE_SCOPE" in local|project|user) ;; *) exit 2 ;; esac
claude mcp get "$SERVER_NAME"
claude mcp remove --scope "$CLAUDE_SCOPE" "$SERVER_NAME"
claude mcp list
)
```

The two clients own separate registrations; run only the command for the one
being retired. Codex's CLI removal targets its native configuration scope; a
project TOML entry or plugin-provided server must be removed/disabled at its own
declared source, not assumed removed from every scope by this command. Preserve
unrelated configuration and project state. Removal of an MCP registration is
not an uninstall of the executable or deletion of its index/counters.

For a retained user service, `OWNED_UNIT` must be the exact unit created by the
selected recipe. Observe state, stop it gracefully, verify it stopped, restart
it and repeat its real health/query check. Do this only when that service is
owned by the qualification run or its existing consumers have been accounted for.

```sh
systemctl --user show "$OWNED_UNIT" --property=ActiveState,SubState,MainPID
systemctl --user stop "$OWNED_UNIT"
systemctl --user is-active "$OWNED_UNIT"
systemctl --user start "$OWNED_UNIT"
systemctl --user status "$OWNED_UNIT" --no-pager
```

`is-active` is expected to return a nonzero exit status after a successful stop;
retain that expected outcome explicitly. For final retirement use
`systemctl --user disable --now "$OWNED_UNIT"` only if the run itself enabled
that unit. Keep its data directories. The shared MCPorter daemon is not an
owned disposable service; do not stop it to clean up another component.

Foreground tools should close through their native exit path. For a child
started by the qualification shell, record its PID, verify its identity, send
SIGTERM if needed and `wait` for that same child. Record its exit status and
verify its owned listener is gone. Avoid broad process-name termination. A
successful stop/start does not prove persistence: query the exact synthetic
record before and after.

## Stateful persistence and recovery

| Selected role | Accepted dated evidence | What the next host must retain |
| --- | --- | --- |
| ai-memory | [WSL 65-check native fixture](../blueprints/convergence-practice/wsl-memory-maintenance/README.md): restart, upstream HTTP backup, empty-target native restore and four clean exits | Exact scope/page versions, backup artifact, empty restore target, post-restore retrieval; production activation remains separate |
| PostgreSQL + API/UI | [WSL application](../blueprints/convergence-practice/wsl-application/README.md): 12 API checks, real browser flow, migration reversal and same rows/history after restart | Locked environment, before/after rows and schema, owned process/port cleanup; independent-host database restore is not yet accepted |
| Qdrant | [Native state recovery](../blueprints/us-equities/state-recovery/qdrant/receipt.json) | Native snapshot identity, isolated restored collection and actual retrieval; copying binary files alone is not state recovery |
| Restic | [WSL synthetic restore](../blueprints/convergence-practice/wsl-restore/receipt.json) | Exact snapshot ID, integrity/read checks, restored-byte equality and separately retained private key/password source |
| Dagu | [WSL controlled transport recovery](../blueprints/convergence-practice/wsl-transport-recovery/README.md) | Same run/checkpoint after owned SSH-client interruption and native completion; no host-reboot or distributed exactly-once claim |
| Native agent sessions | [Codex on Mac](../blueprints/convergence-practice/native-recovery/README.md), [Claude on WSL](../blueprints/convergence-practice/native-recovery/claude/README.md) | Native session/run identity and resumed task result; accounts remain locally signed in |

The native ai-memory commands are:

```sh
ai-memory backup --data-dir "$FIXTURE_DATA" --config "$FIXTURE_CONFIG" \
  --to "$RUN_DIR/ai-memory-backup.tar.gz"
ai-memory restore --data-dir "$EMPTY_RESTORE_DIR" \
  --from "$RUN_DIR/ai-memory-backup.tar.gz"
```

Use the fixture guide's separate running HTTP server/configuration for `backup`;
the command is a thin HTTP client. `restore` uses a new empty target and retains
the upstream process guard. No `--force` or process-guard bypass is needed.
Restart the restored fixture and query the same scoped pages; archive creation
alone does not prove a usable restore.

For a selected private Restic repository and exact captured snapshot:

```sh
restic snapshots --json
restic check
restic restore "$SNAPSHOT_ID" --target "$EMPTY_RESTORE_DIR"
```

Use the repository's native private configuration; never put a password or key
in the catalog. `restic check` does not itself compare every restored file with
the original. Compare the retained fixture hashes and open the restored native
application. Do not use a moving `latest` snapshot when reproducing a dated
acceptance, and do not overwrite an existing working directory to simulate
recovery.

Selected recovery now has two separately accepted hosted recipes:
[native application-state transfer](../blueprints/convergence-practice/offhost-app-state/README.md)
retains unchanged upstream tests and actual ai-memory/Qdrant destination queries;
[scheduled guest reboot](../blueprints/convergence-practice/service-reboot/README.md)
retains native Dagu retry, unchanged checkpoint, one effect and independent
pre-login observations. Each links exact commands, returned results, original
digests and cleanup. Reuse their matching scopes; neither certifies production
data, physical-host disaster recovery or lost-account/key availability.

## Baseline acceptance and the next session

Choose the cheapest adequate native path for each artifact. Compare the full
candidate sequence, including search/index or recovery costs when those are
part of the task. Preserve required information and quality assertions before
accepting fewer tokens. Existing measurements intentionally retain counterexamples:
jCodeMunch's 861-token search/source sequence beats a 5,476-token whole file but
costs more than a known 601-token focused read; the full-catalog TOON conversion
expands compact JSON. A correct installation does not guarantee a better
baseline on every input.

Read the [token practice](../docs/token-practice.md) and run the configured
[portable reporter](../tools/token-report/README.md) after meaningful changes.
Keep upstream cumulative estimates, unique exact artifact comparisons and
actual provider consumption in separate fields. SDK/Prometheus agreement
confirms consumption, not the counterfactual number of tokens avoided. Do not
sum overlapping runtime counters or repeated snapshots to manufacture lifetime
savings.

A future session loads the small adoption manifest first, selects one role,
checks the matching dated inputs and runs only a missing or changed applicable
stage. Record unresolved stages and retained failures. Guidance-only entries
need no process tests; stateful services require persistence/recovery evidence;
optional platform-specific tools do not become mandatory on another OS.

The [September 21 clean-userspace qualification](../docs/portable-userspace-install-20260921.md)
exercised pinned Claude/Codex installation, four token tools and two selected ECC
skills in a fresh official Ubuntu Base filesystem. It includes repeat-install,
overwrite-protection, local fixture and rollback results with retained failures.
That subset runs on the existing WSL kernel; fresh-PC boot, native sign-in,
terminal interaction and other scoped integrations still require that host's
own acceptance. Do not replay its receipt as a new machine's passed result.
