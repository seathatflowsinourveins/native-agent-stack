# Native lifecycle and a new PC's acceptance

Use the selected component's [native recipe](manifest.json), the current pin in
[stack.json](../manifests/stack.json), and the stage record in the
[component matrix](../blueprints/token-native-focus/saturation-audit.json).
The matrix covers every selected component. The broader
[decision index](../catalogs/us-equities/decision-index.json) also contains
alternatives and research identities. Current counts are generated in the
[HTML catalog](../docs/ecosystem/index.html); installing every alternative is
not a prerequisite for the selected workflow.

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
