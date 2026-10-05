# Unattended US-equities research and journal recovery

The templates run the named `nyse-post-close-evidence` research job with Dagu
**2.16.6** and recover selected research SQLite journals with restic **0.19.1**.
This serves US-equities research and historical simulation: the DAG summarizes
an operator-supplied local LEAN simulation and validates its evidence. It neither
acquires market data nor executes broker orders.

The [decision](../../../../docs/decisions/2026-10-05-trading-unattended-hosting-recovery.md)
records the alternatives, scheduler comparison and remaining gates. These are
portable examples. PR-4 installed no unit, started no scheduler and used no
existing host service. Operating-host and alert selection is **user decision 2**.

## One Dagu process and an explicit job environment

[dagu-equities.service.example](dagu-equities.service.example) runs `dagu start-all`
with `Restart=on-failure`, combining the web UI and scheduler in one process.
[config.yaml.example](config.yaml.example) disables the optional coordinator in
that file; it otherwise defaults to enabled. Sources:
`dagucloud/dagu@v2.16.6:internal/cmd/startall.go:32-45` and
`internal/cmn/config/loader.go:1311-1319`
([start-all](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/cmd/startall.go#L32),
[default](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/cmn/config/loader.go#L1311)).

Replace every `/path/to/...` in a **private copy** of the unit and DAG. Put the
four job variables `STACK_REPO`, `SDK_ENV`, `LEAN_EVENTS` and `RESEARCH_OUTPUT`
in the DAG's `env:` block. This keeps the job complete when invoked by either
the scheduler or native CLI. `SDK_ENV` is the existing locked trading runtime.
An `Environment=` line in the unit cannot supply them: `env -i` discards that
inherited environment. Sources: `coreutils/coreutils@v9.4:src/env.c:824-838`
([implementation](https://github.com/coreutils/coreutils/blob/v9.4/src/env.c#L824)) and
`dagucloud/dagu@v2.16.6:internal/spec/dag.go:1663-1673`
([DAG env](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/spec/dag.go#L1663)).
The four passthrough entries remain available for other native CLI definitions;
this DAG obtains its values from its own block.

Deploy only the private research DAG to the chosen Dagu DAG directory, with its
local input and output paths adapted. Each run writes
`order-events-${DAG_RUN_ID}.parquet`, preserving earlier outputs and avoiding the
summarizer's overwrite refusal on the following session. Dagu supplies this
identifier (`dagucloud/dagu@v2.16.6:internal/runctx/context_env.go:28`,
`internal/cmn/runenv/keys.go:12-13`
[source](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/cmn/runenv/keys.go#L12)).

The UI listens on loopback and keeps `permissions.run_dags: false` and
`permissions.write_dags: false`. On 2.16.6 the run permission is an API guard;
the scheduler's local dispatch path starts its subprocess independently. This
is a **source finding**, awaiting observation in the operating-host drill.
Sources: `dagucloud/dagu@v2.16.6:internal/service/frontend/api/v1/dagruns.go:163-167`
([API guard](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/service/frontend/api/v1/dagruns.go#L163))
and `internal/service/scheduler/dag_executor.go:280-321`
([local dispatch](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/service/scheduler/dag_executor.go#L280)).
Anonymous loopback observation requires a trusted local user; these permissions
do not cover all administration APIs. DAG artifact storage stays off.

## NYSE session schedule

[equity-research-evidence.yaml](equity-research-evidence.yaml) names its schedule
contract **nyse-post-close-evidence** in the description and tag. Its cron is
`CRON_TZ=America/New_York 30 16 * * 1-5`: one attempt at 16:30 New York time on
each weekday, with daylight-saving changes handled by the explicit time zone.
This pin has no separate schedule-name field; its cron object permits an
expression and optional runtime profile. Sources:
`dagucloud/dagu@v2.16.6:internal/cmn/schema/dag.schema.json:855-876`,
`internal/ir/schedule.go:281-305`, `go.mod:65`, and the locked parser
`robfig/cron@v3.0.1:parser.go:93-103`
([timezone parser](https://github.com/robfig/cron/blob/v3.0.1/parser.go#L93)).

Cron cannot skip exchange holidays. The normal `calendar_check` step runs
[session_day.py](session_day.py) in `SDK_ENV`, checks exchange-calendars **4.13.2**,
and queries XNYS for today's New York date and actual close. A non-session prints
`non_session`; the `nyse_session` precondition skips that step and its dependents.
Import, package-version or calendar failures fail the normal check step instead
of being mistaken for a holiday. A manual run before close prints `before_close`
and skips the research chain.

The calendar is locked in
`blueprints/us-equities/runtime-2604/trading-2604-runtime/pyproject.toml:11`
(PR-1 revision `d00e4e6eeb92c7c99066ea5d0bd85f379c931c4f`). The brief's shorter
`runtime-2604/pyproject.toml` path is absent at this PR's base; the nested bundled
file was read directly, and `manifests/stack.json` independently carries 4.13.2.
PR-4 adds no lock or dependency installation. Calendar sources:
`gerrymanoim/exchange_calendars@4.13.2:exchange_calendars/exchange_calendar.py:1012-1016,1263-1279`
and `exchange_calendars/exchange_calendar_xnys.py:157-165`
([session API](https://github.com/gerrymanoim/exchange_calendars/blob/4.13.2/exchange_calendars/exchange_calendar.py#L1263),
[close times](https://github.com/gerrymanoim/exchange_calendars/blob/4.13.2/exchange_calendars/exchange_calendar_xnys.py#L157)).
**Early-close days still run at 16:30**, after their earlier close, with no
additional cron or run. Step skip and dependency propagation come from
`dagucloud/dagu@v2.16.6:internal/runtime/runner.go:1633-1648,1267-1281`
([precondition result](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/runtime/runner.go#L1633)).

## Journal snapshot and restic procedure

[journal_recovery.py](journal_recovery.py) stays in `hosting/` alongside the job
and operator drills. It owns recovery of selected research files without coupling
to a broker adapter or changing an order-state writer. It is stdlib integration
glue around CPython's published Online Backup example and native restic commands.

Select **every journal required by the research consumer**, with explicit required
tables. The procedure opens each source read-only and uses
`sqlite3.Connection.backup` to a new staging directory, then closes the destination
in DELETE journal mode. Never copy an active SQLite, WAL or SHM file directly.
Sources: `python/cpython@v3.12.3:Doc/library/sqlite3.rst:1107-1155`
([concurrent backup and example](https://github.com/python/cpython/blob/v3.12.3/Doc/library/sqlite3.rst#L1107))
and `Modules/_sqlite/connection.c:2067-2077`. Each journal is independently
consistent; this does not create an atomic transaction across journals.
Consumers needing one must quiesce their writers before taking the snapshots.

The frozen inventory records every staged file's relative path, SHA-256, bytes,
`PRAGMA integrity_check` and required tables' row counts. It is written inside
staging and as a separate immutable **external oracle**. Retain that oracle
independently from the restored copy. Staging stays frozen through backup; a
failed snapshot operation never becomes an accepted inventory.

Every nonzero native restic exit fails the procedure, including **exit 3**, when
restic creates a snapshot but cannot read all source files. Snapshot existence
is insufficient for acceptance. Source:
`restic/restic@v0.19.1:doc/040_backup.rst:787-806`
([exit codes](https://github.com/restic/restic/blob/v0.19.1/doc/040_backup.rst#L787)).

Run the cycle at least once every **24 hours**, including weekends and holidays,
using one private rotation-state file per repository. Default checks rotate
`1/7` through `7/7`; all partitions are read within **seven days**. The cursor
advances only after successful native checking. A gap over 24 hours or reversed
clock refuses continuation until `--full-check` successfully reads all data and
resets the rotation. This is an operator execution requirement; no backup timer
was enabled by PR-4. Every cycle also restores and compares its snapshot.
Source: `restic/restic@v0.19.1:doc/045_working_with_repos.rst:482-521`
([deterministic partitions](https://github.com/restic/restic/blob/v0.19.1/doc/045_working_with_repos.rst#L482)).

Restore the exact returned snapshot ID's staging subtree to a **new** directory,
with `--verify --overwrite never`. Compare the exact restored file set, inventory
bytes and every file's SHA-256 and byte count against the external oracle; then
check journal integrity and required row counts. **integrity_check and row counts
alone do not prove completeness**: altered records can preserve both.
Source: `restic/restic@v0.19.1:doc/050_restore.rst:55-73`
([subfolder restore](https://github.com/restic/restic/blob/v0.19.1/doc/050_restore.rst#L55)).

For an already initialized **local** repository and its operator-owned password
file, the template command is:

```sh
rtk env TMPDIR="$PRIVATE_TMP" nice -n 19 python3 \
  blueprints/us-equities/hosting/journal_recovery.py cycle \
  --restic-bin "$RESTIC_BIN" --repository "$LOCAL_REPOSITORY" \
  --password-file "$RESTIC_PASSWORD_FILE" --work "$NEW_PRIVATE_WORK" \
  --rotation-state "$PRIVATE_ROTATION_STATE" \
  --journal "research=$RESEARCH_JOURNAL" --required-table research=events \
  --journal "evidence=$EVIDENCE_JOURNAL" --required-table evidence=runs
```

Adapt names and tables to the consumer's contract; `events` and `runs` are the
fixture tables. The work directory must be new. The password file must be outside
staging; its contents are never read or printed by the Python script. Keep the
repository, raw output, state and oracle private. If a crash leaves a `.lock` or
`.new` rotation file, preserve the failed output and resolve that private state
before retrying; do not reset the cursor to conceal a missed interval.
Remote repository URLs are outside this local procedure. A second-host consumer
can run `verify --restored "$RESTORE" --inventory "$FROZEN_INVENTORY"` against
its independently retained oracle after the separately approved destination
restore. Key recovery belongs to user decision 3.

## Same-host operator drills and proof

Run [drill_process_restart.py](drill_process_restart.py) **later on the operating
host**, shortly before the next eligible 16:30 slot, using its locked trading
Python. Supply `--dagu-bin`, `--dagu-home`, `--config`, this one DAG's
`--dag-history` directory and the exact aware `--due-at` timestamp. The script
verifies an existing unit's MainPID and executable, kills `start-all` with
SIGKILL, observes automatic restart and waits for the next successful due run.
Native history plus original `status.jsonl` must attest the exact `scheduleTime`
and scheduler trigger while the deployed UI has `run_dags: false`. A manual run
does not count. The script installs, enables and starts no unit. SIGKILL induces
failure; under `Restart=on-failure`, clean SIGTERM need not trigger restart
(`systemd/systemd@v255:man/systemd.service.xml:818-836`
[source](https://github.com/systemd/systemd/blob/v255/man/systemd.service.xml#L818)).

**A process-restart drill is not reboot, missed-run or independent-alert acceptance.**
It observes one process failure and the following slot. Host boot, downtime across
slots, catch-up, duplicate runs and independent notification need separate host
receipts and the chosen alert path.

Run the disposable local backup-check-restore drill with:

```sh
rtk env TMPDIR="$PRIVATE_TMP" nice -n 19 python3 \
  blueprints/us-equities/hosting/drill_local_recovery.py \
  --restic-bin "$RESTIC_BIN" --output "$NEW_SANITIZED_REPORT"
```

It generates and later deletes a throwaway password, creates two synthetic WAL
journals and commits to each while its Online Backup copy is active. It backs
up, reads subset **1/1** (every pack in this small proof), restores and independently
compares bytes, hashes and required state. Stdlib unittest separately exercises
the default seven-part rotation. It also runs these controls:

- `--control snapshot` makes one staged file unreadable: native backup must exit
  **3** and the procedure must exit nonzero before checking or restoring.
- `--control restore` deletes a required file after native restore: comparison
  must make the procedure exit nonzero.

The [sanitized offline proof](evidence/offline-proof.json) and
[local integration receipt](../../../../evidence/receipts/trading-unattended-hosting-recovery-20261005.json)
retain actual native output and command exits with separate observations.
The fixture is our integration check, using the unchanged restic 0.19.1 executable.
Neither operator drill was run on an operating service.

**The same-host drill cannot close the off-host-recovery gate.** Closure needs
**user decision 3**: an independent destination, key recovery and a restore by a
consumer on a second host, checked against the independent oracle and required
state. Its recovery-time objective must still be selected and measured. The
scratch proof establishes no off-host durability, retention deletion or alert.

Historical [Dagu receipt](receipt.json) and
[static-file backup acceptance](backup/README.md) retain their original scopes;
neither attests execution of the new scheduled templates.
