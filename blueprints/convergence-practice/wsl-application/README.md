# Native WSL run-ledger qualification

This lane runs the existing [typed application](../application-delivery/README.md)
on Ubuntu 24.04 x86-64 under WSL2, from public source
`cabbe2c96e39096b510f739f07a6e4132da082de`. It retains the original API and browser
assertions, application pins and lockfiles. [freeze.json](freeze.json) records
those exact inputs; [receipt.json](receipt.json) records native results and failed
attempts. Historical Mac results are separate evidence.

The native WSL run passed all 12 API/database guards, the production build,
schema/type checks, the unchanged browser create/update workflow, separate
empty-database migration reversal, and exact record/history persistence across
PostgreSQL and application restarts. All owned servers and browsers were stopped.

The existing Node 24.21.0, uv 0.12.17 and Python 3.13.15 are reused. The project's
`>=3.13,<3.15` requirement and universal `uv.lock` support that Python. pnpm
12.4.2 is installed only in the qualification prefix. Linux Chrome for Testing
153.0.8010.52 is an explicit platform adaptation: Google's official metadata does
not list the Mac receipt's installed Chrome 153.0.8010.53 as a Linux CfT artifact.
The Playwright 1.63.0 test and its assertions remain unchanged.

## Isolated prerequisites

Choose a new task-owned prefix outside canonical projects; do not reuse an
existing database or installation. Set `QUAL_PREFIX` to that absolute path,
`QUAL_APP` to its `source/blueprints/convergence-practice/application-delivery`,
and `QUAL_RECIPE` to this published recipe directory. Clone the public repository
into `source` and detach at the revision above. Check ports 15432, 18080 and 18081
before starting anything. Stop if occupied; never stop another task's process.
Copy this lane's `playwright.config.ts` into the sibling `wsl-application` directory
of the pinned clone, leaving `application-delivery` unchanged.

The host already provided GCC 13.3.0, GNU Make 4.3, Perl, curl, tar, unzip, shasum,
`dpkg-deb`, the Ubuntu archive keyring, glibc 2.39 and SQLite 3.45.1. The missing
native tools/libraries were supplied by the seven exact packages in
[ubuntu-packages.json](ubuntu-packages.json). Its dependency constraints match
those existing libraries. Verify each signed Ubuntu `InRelease` with `gpgv`, each
uncompressed `Packages` hash/size against that release, and each downloaded `.deb`
SHA-256 against its package entry. Extract payloads using only:

```sh
dpkg-deb -x "$VERIFIED_DEB" "$QUAL_PREFIX/tools/sysroot"
```

This executes no maintainer scripts and changes no system package database.
Retain package copyright files. `sources.json` records the upstream pnpm metadata,
Linux native artifact integrity, Chrome artifact identity and PostgreSQL publisher
checksum. The measured pnpm installation verified both npm metadata and archive
integrity, extracted `@pnpm/exe.linux-x64@12.4.2`, and linked its `pnpm` executable
only into `tools/bin`. pnpm 12's package is a native wrapper; the old
`package/bin/pnpm.cjs` path does not exist. No lifecycle script was executed.
Extract the exact verified Chrome archive into `tools/chrome-linux64`.

Use process-local variables in the qualification shell:

```sh
export PATH="$QUAL_PREFIX/tools/bin:$QUAL_PREFIX/tools/sysroot/usr/bin:$PATH"
export M4="$QUAL_PREFIX/tools/sysroot/usr/bin/m4"
export BISON_PKGDATADIR="$QUAL_PREFIX/tools/sysroot/usr/share/bison"
export LD_LIBRARY_PATH="$QUAL_PREFIX/tools/sysroot/usr/lib/x86_64-linux-gnu"
export ALSA_CONFIG_PATH="$QUAL_PREFIX/tools/sysroot/usr/share/alsa/alsa.conf"
export UV_PYTHON="$(command -v python3.13)"
export UV_PYTHON_DOWNLOADS=never
export UV_CACHE_DIR="$QUAL_APP/.runtime/uv-cache"
export XDG_CACHE_HOME="$QUAL_PREFIX/cache"
export NEXT_TELEMETRY_DISABLED=1
export WSL_CHROME_EXECUTABLE="$QUAL_PREFIX/tools/chrome-linux64/chrome"
cd "$QUAL_APP"
make setup
```

The Chrome launch keeps Playwright's isolated temporary context and loopback
application lifecycle. GPU acceleration is disabled. No personal browser,
credential store, model, provider or account is used.

## PostgreSQL clean build

The original nested `make postgres-install` has a clean-build defect: the
recursive `$(MAKE)` reaches PostgreSQL with `MAKELEVEL=1`. In PostgreSQL 18.6,
`src/Makefile.global.in` lines 393–401 creates generated headers only at
`MAKELEVEL=0`. A fresh build therefore fails on missing `utils/errcodes.h`.
The original file and its historical hashes are preserved. Run the supported
upstream build directly from the shell after source configuration:

```sh
test ! -e .runtime/postgresql/18.6
mkdir -p .runtime/postgresql-source .runtime/postgresql-build
curl --fail --location --proto '=https' --tlsv1.2 \
  https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2 \
  --output .runtime/postgresql-source/postgresql-18.6.tar.bz2
printf '%s  %s\n' \
  555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f \
  .runtime/postgresql-source/postgresql-18.6.tar.bz2 | shasum -a 256 -c -
tar -xjf .runtime/postgresql-source/postgresql-18.6.tar.bz2 \
  -C .runtime/postgresql-source
(cd .runtime/postgresql-build && \
  ../postgresql-source/postgresql-18.6/configure \
  --prefix="$QUAL_APP/.runtime/postgresql/18.6" \
  --without-icu --without-readline --without-zlib)
# These are shell-level commands, not recursive Makefile recipes.
taskset -c 0-3 make -C .runtime/postgresql-build -j 4
taskset -c 0-3 make -C .runtime/postgresql-build install
cp .runtime/postgresql-source/postgresql-18.6/COPYRIGHT \
  .runtime/postgresql/18.6/COPYRIGHT
make postgres-init postgres-start postgres-databases
make migrate migrate-test
make migrate migrate-test
```

Use up to four allowed CPU IDs if the host's affinity differs. Installation and
initialization must refuse existing destinations. The local source configuration
has no ICU, readline, zlib or TLS, uses UTF-8/C locale and local synthetic trust
authentication, and listens only on loopback with no Unix socket. It qualifies
this fixture, not a production database service.

## Native verification and restart

Run the original verify actions, selecting only the task-owned Linux browser:

```sh
pnpm peers check
uv run --frozen python verify_schema.py
pnpm typecheck
taskset -c 0-3 pnpm build
make test
taskset -c 0-3 pnpm exec playwright test \
  --config ../wsl-application/playwright.config.ts
```

The browser config imports the original config, retaining its test directory,
headless Chromium mode, zero retries, one worker, timeout, isolated server start,
`reuseExistingServer: false` and graceful process cleanup. It changes the Linux
executable path and disables GPU acceleration. All original assertions still run.
The JSON browser report is written under this alternate config directory's
`.runtime/browser-results.json`.

For schema reversal, create a separate empty synthetic database using the owned
`createdb`, set `DATABASE_URL` only for each Alembic invocation, and exercise
`upgrade head` → `downgrade base` → `upgrade head`. Inspect table names after each
step, then drop only this explicitly created reversal database. This proves
schema reversal, not recovery of deleted data.

For persistence, retain the browser-created row's full API JSON and database row
plus both history events. Stop the owned API/Next and PostgreSQL, start the same
database and application, and compare the exact retained values, including ID,
timestamps, revision, status and events. Reopen the retained row in a fresh
headless browser and assert its passed status and two recorded changes. Keep raw
row identifiers and machine paths in private evidence.

The frozen supervisor's exclusive bind preflight can reject a recently stopped
API port while TCP is in `TIME-WAIT`, despite no remaining listener. This occurred
on WSL. Wait for normal TCP expiry and retry the same supervisor; do not terminate
unowned processes or change the acceptance assertions to bypass it.

## Cleanup and limits

Stop the owned application supervisor, let it reap API/Next process groups, and
run `make postgres-stop`. Verify the three ports are free and no owned browser or
application processes remain. Retain selected synthetic data and full logs,
including failures, outside public receipts. To roll back, first stop those owned
processes, preserve needed evidence, then remove only the newly created task
prefix after review. Reverting this recipe alone does not delete database state.

This acceptance has no authentication, external ingestion, deployment, production
load, backup/independent-host restore, model execution or trading claim. Whole-task
model usage is unknown; no token-saving claim is made.
