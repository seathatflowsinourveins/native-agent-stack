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
example, once vLLM is switch-adopted) is one `apply`, which flips only
`current/<id>` and restarts only the units the component's own `surfaces[]`
name -- never `adaptive-paper-rung1x-20260923-ladder2`,
`ibkr-paper-post-20260923`, `incentive-forward@1330`,
`mover-daily-scan-0925` or `mover-rth-trial-20260924`, which `apply` refuses
to restart under any circumstance.

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
carries (which is never a root path and could never have matched). `apply
--confirm-within SEC` additionally schedules `systemd-run --user
--on-active=<SEC>s --setenv=ECO_INSTALL_ROOT=... -- ecosystem-switch rollback
--txn T --if-unconfirmed` (every test-stub variable in play is forwarded the
same way, so the timer acts on the same root and stubs the run that
scheduled it actually used), so an operator who never runs `confirm --txn T`
gets an automatic revert once that window elapses, without needing to stay
attached to watch it. `rollback ID` (no `--txn`) targets that component's
most recently touched transaction with at least one reversible operation (by
ledger sequence -- never by sorting transaction-id text, which sorts a plain
`apply` transaction's id after a `relink-`-prefixed one regardless of which
actually happened more recently, and never a bare `adopt --baseline`/
`--resync`/`prune` record, which carries nothing to reverse). `rollback
--txn T` also refuses a txn a *later* apply on the same component has since
superseded (re-pointing `current/<id>` to T's old root would silently
clobber that later apply), and `confirm --txn T` refuses a txn that was
already rolled back, whose post-apply verify already failed, or that is
still `in_progress` (a crashed or interrupted `apply` that never reached its
own post-apply verify) -- confirming one of those would mark a half-applied
component "applied" through the ledger alone, and since `recover` only
reconciles a transaction still `in_progress`, it would then never see that
transaction again either. A crashed or interrupted `apply`/`adopt --relink`
never completes after the fact: `ecosystem-switch recover` finds any
transaction still `in_progress` and rolls it back, the same as an explicit
`rollback` would.

**Prune.** `prune --list` reports which `tools/<name>-<version>` prefixes no
`current/<id>` link points at, that are not the previous root of any
not-yet-rolled-back transaction (a pending or already-applied transaction's
own rollback target stays live until that transaction is actually rolled
back, not merely superseded by a later one), and this tool's own
reduced-scope in-use check (PATH entries, `bin/` symlink targets, this
user's own running processes' exe/cwd/cmdline, and this user's `systemd
--user` unit file text) does not find referenced elsewhere; `prune --apply
ROOT --reason TEXT` removes one such prefix and records the reason on the
ledger. This in-use check is deliberately narrower than
`bin/ecosystem-wave-retention` on the host (which additionally inspects
mounts, symlink hops and a citation search across evidence repositories, and
this tool's own check cannot see a hard-coded root inside a wrapper script
under `adoption/tools/` in the catalog checkout, since it only ever reads
`$ECO_INSTALL_ROOT`): treat an "eligible" prefix here as a lead worth
checking by hand before deleting it, not a proof that nothing on the host
still needs it, and extend this check with that script's fuller technique
before relying on it unattended.

Component coverage today is intentionally partial: `adoption/pins-linux-x86_64.json`'s
schema_version 2 migration gave every one of its 14 existing pins the fields
`ecosystem-switch` needs (`root_name`, `current_link`, `entrypoints[]`,
`surfaces[]`, `state_dirs[]`, `window`, `rollback_class`), but none of those
14 is a live service with an external hard-coded root today, so none of their
`surfaces[]` is populated yet. The actual hard-coded-root consumers this
page's own Facts (see `docs/tasks/sota-rollout-20260925/briefs/switch.md`)
named -- vLLM, the Gitleaks/mcp-inspector/serena-context guarded wrappers,
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
