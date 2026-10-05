# Unattended US-equities research and journal recovery

The templates run the named `nyse-post-close-evidence` research job with Dagu
**2.16.6** and recover selected research SQLite journals with restic **0.19.1**.
This serves US-equities research and historical simulation: the DAG summarizes
an operator-supplied local LEAN simulation and validates its evidence. The research
operator's simulation job owns refreshing `LEAN_EVENTS` after that session's
actual close and **by 16:25 America/New_York**, before the 16:30 attempt. It neither
acquires market data nor executes broker orders.

The [decision](../../../docs/decisions/2026-10-05-trading-unattended-hosting-recovery.md)
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
the scheduler or native CLI. `SDK_ENV` is the installed SDK built from
[`adoption/sdk/requirements-linux-x86_64-py313.lock:241`](../../../adoption/sdk/requirements-linux-x86_64-py313.lock),
which locks exchange-calendars 4.13.2. Use that maintained native environment;
PR-4 adds no second runtime, lock or dependency installation.
An `Environment=` line in the unit cannot supply them: `env -i` discards that
inherited environment. Sources: `coreutils/coreutils@v9.4:src/env.c:824-838`
([implementation](https://github.com/coreutils/coreutils/blob/v9.4/src/env.c#L824)) and
`dagucloud/dagu@v2.16.6:internal/spec/dag.go:1663-1673`
([DAG env](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/spec/dag.go#L1663)).
`env_passthrough` is an **allowlist**. The four scheduled-job entries and all seven
entries used by [research-runtime](../research-runtime/README.md) remain in the
config: `LEAN_RESULTS`, `RESEARCH_WORKSPACE`, `NATIVE_CODEX_HOME`,
`NATIVE_CODEX_BIN`, `NATIVE_CLAUDE_BIN`, `NATIVE_RUNTIME_PATH` and
`SDK_OBSERVATION_DIR`. Those recipes must also supply their own environment to
their native CLI calls; the scheduled DAG obtains its four values from its own
block. Sources: `dagucloud/dagu@v2.16.6:internal/cmn/config/loader.go:344-347`
and `internal/cmn/config/env.go:77-95`.

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

## Native installation and operating-host service boundary

These commands are **for the operator later**, after user decision 2 selects the
operating host. Use a clean upstream release on a new Linux/WSL host, verified
against its publisher's checksum; reuse a previously verified installation at the
same pin. For Linux amd64 the historical verified archive SHA-256 is
`06c3ed951fb58408313b1db25bc9f90ff2f427cbdbe68aaff55cd5465c167717`
([historical receipt](receipt.json)); still verify the downloaded archive against
the tagged release's `checksums.txt`:

```sh
gh release download v2.16.6 --repo dagucloud/dagu \
  --pattern dagu_2.16.6_linux_amd64.tar.gz --pattern checksums.txt
awk '$2 == "dagu_2.16.6_linux_amd64.tar.gz"' checksums.txt | sha256sum --check --strict
tar -xzf dagu_2.16.6_linux_amd64.tar.gz
"$DAGU" version
install -m 0600 config.yaml.example "$RESEARCH_HOME/config.yaml"
```

Set `DAGU`, `RESEARCH_HOME`, `STACK_REPO`, `SDK_ENV`, `LEAN_EVENTS` and
`RESEARCH_OUTPUT` to private operator paths, adapt the private DAG and unit, and
keep **config and private DAG mode 0600**. Download/extraction must target a
private installation directory, with `DAGU` pointing to its extracted executable.
The supported upstream release is
[dagucloud/dagu@v2.16.6](https://github.com/dagucloud/dagu/releases/tag/v2.16.6);
no rebuilt Dagu or restic binary belongs to this recipe.

`auth.mode: none` permits anonymous reads and some administration on loopback;
**do not expose it with a network listener or tunnel**. The historical Basic
configuration returned 401 and repeatedly challenged the browser. When changing
to `none`, remove the `auth.basic` subsection: the native config validator refuses
a Basic block under that mode. The [dated auth observation](../../../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/2-dashboard-auth-mode.json)
retains that finding, distinct from this round's offline probes. Use upstream
authentication in a separately reviewed network deployment. `run_dags: false`
and `write_dags: false` do not form a global Viewer role. Artifact storage is
enabled by default; this DAG disables it explicitly. Native scratch acceptance
on **2.16.6 and 2.17.2** found that `base.yaml` does not propagate that key.
**2.17.2 adds anonymous cross-run `GET /api/v1/artifacts` under `none`**; its
historical boundary remains relevant to any later pin change. See the
[2026-09-25 source/observation record](../../../docs/decisions/2026-09-25-workstation-sota-refresh.md).
This round keeps 2.16.6 and runs neither version's server.

After adapting and placing the private unit under the operating user's
`~/.config/systemd/user/dagu-equities.service`, the operator's lifecycle commands
are:

```sh
loginctl enable-linger
systemctl --user daemon-reload
systemctl --user enable --now dagu-equities.service
systemctl --user restart dagu-equities.service
systemctl --user status dagu-equities.service
"$DAGU" history --context local --dagu-home "$RESEARCH_HOME" --format json
# Later removal preserves the evidence directories:
systemctl --user disable --now dagu-equities.service
```

`loginctl enable-linger` without a name selects the caller: it keeps the user
manager alive after logout and permits boot activation
(`systemd/systemd@v255:man/loginctl.xml:186-195`
[source](https://github.com/systemd/systemd/blob/v255/man/loginctl.xml#L186)).
It **cannot keep a WSL VM or Windows host running**. Windows/WSL shutdown, VM
lifetime and host reboot interrupt this user unit; unattended availability still
needs the later host receipt. `start-all` replaces the previous manual-history
`server` example and owns the scheduler within the same supervised process.
`Restart=on-failure` provides process restart, with no claim of resuming in-flight
steps or catching up a missed schedule. The builder executed none of these
service/linger commands.

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
and queries XNYS for today's New York date and actual close. It constructs bounds
from **December 1 of the previous year through January 31 of the following year**,
bracketing New Year's Day and observed January holidays before the first session.
The native calendar's session boundaries determine coverage
(`gerrymanoim/exchange_calendars@4.13.2:exchange_calendars/exchange_calendar.py:1257-1279`).
A truly uncovered date remains a hard error. A covered non-session prints
`non_session`; the `nyse_session` precondition skips that step and its dependents.
Import, package-version or calendar failures fail the normal check step instead
of being mistaken for a holiday. A manual run before close prints `before_close`
and skips the research chain.

The SDK lock cited above is on this branch's base. Calendar sources:
`gerrymanoim/exchange_calendars@4.13.2:exchange_calendars/exchange_calendar.py:1012-1016,1263-1279`
and `exchange_calendars/exchange_calendar_xnys.py:157-165`
([session API](https://github.com/gerrymanoim/exchange_calendars/blob/4.13.2/exchange_calendars/exchange_calendar.py#L1263),
[close times](https://github.com/gerrymanoim/exchange_calendars/blob/4.13.2/exchange_calendars/exchange_calendar_xnys.py#L157)).
**Early-close days still run at 16:30**, after their earlier close, with no
additional cron or run. Step skip and dependency propagation come from
`dagucloud/dagu@v2.16.6:internal/runtime/runner.go:1633-1648,1267-1281`
([precondition result](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/runtime/runner.go#L1633)).

On a session after close, `--events "${LEAN_EVENTS}"` also requires the events
file's mtime to be between that session's actual close and the check instant.
`missing_input`, `stale_input` or `future_input` are visible normal-step output
tokens with **exit 1**, so Dagu fails the run and blocks the dependent evidence
chain. They appear in `dagu history --status failed`; only `non_session` and
`before_close` retain a successful guard and a skipped research chain.
Calendar/import/IO errors remain failures. The producer must complete and atomically publish that session's
local LEAN simulation output by 16:25; mtime is an availability contract, not
proof of the market dates or quality inside a file. No upstream acquisition job
is introduced here.

## Manual run, cancellation and replay

On the chosen operating host, use the same private config and DAG as the service.
Start a manual check with a fresh, operator-chosen run ID:

```sh
"$DAGU_BIN" start --context local --dagu-home "$PRIVATE_DAGU_HOME" \
  --config "$PRIVATE_CONFIG" --run-id "$NEW_RUN_ID" "$PRIVATE_DAG"
```

In another terminal, cancel that exact active run and inspect its native history:

```sh
"$DAGU_BIN" stop --context local --dagu-home "$PRIVATE_DAGU_HOME" \
  --config "$PRIVATE_CONFIG" --run-id "$NEW_RUN_ID" equity-research-evidence
"$DAGU_BIN" history --context local --dagu-home "$PRIVATE_DAGU_HOME" \
  --config "$PRIVATE_CONFIG" --run-id "$NEW_RUN_ID" \
  --status succeeded,failed,aborted --limit 1000 --format json equity-research-evidence
```

An aborted or failed run needs inspection and corrected input before replay.
Replay with another fresh run ID using the start command; `DAG_RUN_ID` keeps
earlier output intact. A manual run before close or on a holiday skips the
research steps. A manual run never proves scheduler dispatch or catch-up. These
commands are operator procedures, not commands run by this builder. Sources:
`dagucloud/dagu@v2.16.6:internal/cmd/start.go:45-67; internal/cmd/stop.go:20-38,53-91;
internal/cmd/history.go:160-345; internal/cmd/flags.go:463-481`, corroborated by
the installed 2.16.6 `start`, `stop` and `history --help` (all exit 0).

## Journal snapshot and restic procedure

[journal_recovery.py](journal_recovery.py) stays in `hosting/` alongside the job
and operator drills. It owns recovery of selected research files without coupling
to a broker adapter or changing an order-state writer. It is stdlib integration
glue around CPython's published Online Backup example and native restic commands.

Select **every journal required by the research consumer**, with explicit required
tables. The procedure opens each source read-only and uses
`sqlite3.Connection.backup(..., pages=-1)` within a read transaction to a new staging directory, then closes the destination
in DELETE journal mode. Never copy an active SQLite, WAL or SHM file directly.
The source must already use **WAL**; the worker checks `PRAGMA journal_mode`
and refuses other modes by default without modifying the source. Explicit
`--allow-non-wal` on `snapshot` or `cycle` accepts writer blocking: the source
read transaction holds a SHARED lock throughout the bounded copy, so a
rollback-journal writer can receive `SQLITE_BUSY` while trying to commit.
Prefer quiescing those writers before opting in. WAL permits concurrent writers.
Source: `sqlite/sqlite@version-3.53.1:src/backup.c:346-354,383-389`.
Sources: `python/cpython@v3.12.3:Doc/library/sqlite3.rst:1107-1155`
([concurrent backup and example](https://github.com/python/cpython/blob/v3.12.3/Doc/library/sqlite3.rst#L1107))
and `Modules/_sqlite/connection.c:2013,2067-2102`. One native step avoids restarting
an incremental copy on each WAL commit. An isolated stdlib subprocess bounds each
copy at **120 seconds**, including worker startup; timeout kills and waits for
the worker and prevents inventory publication. The maximum logical journal size
is **256 MiB** per source, checked in the read transaction. Operators can set
`--backup-timeout` and `--max-journal-bytes` after measuring the required sizes and
copy times; neither limit silently drops a journal. These are explicit integration
policy limits, not upstream defaults. Source:
`python/cpython@v3.12.3:Doc/library/subprocess.rst:62-68` (native timeout).
The timeout bounds the spawned worker; the OS's initial process creation itself
cannot always be interrupted, as the same source explains.
Each journal is independently
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

Run the cycle **daily**, including weekends and holidays,
using one private rotation-state file per repository. Default checks rotate
`1/7` through `7/7`; all partitions are read within **seven days**. The cursor
advances only after successful native checking. The **whole 1..7 rotation**, from
its cycle-start timestamp through subset 7's successful completion, has a seven-day
deadline in UTC. There is no strict per-step 24-hour cutoff: daily execution with
60 seconds of jitter and the 25-hour fall-back day fit the bound. An incomplete
cycle older than seven days, a gap since the last success over seven days, reversed
clock or pre-v2 state requires `--full-check`; only successful full reading can
restart the cursor. Starting the next rotation resets its origin before subset 1;
capture the invocation time before snapshot/backup, and check completion time
again before publishing state. This is an operator execution requirement; no backup timer
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
env TMPDIR="$PRIVATE_TMP" nice -n 19 python3 \
  blueprints/us-equities/hosting/journal_recovery.py cycle \
  --restic-bin "$RESTIC_BIN" --repository "$LOCAL_REPOSITORY" \
  --password-file "$RESTIC_PASSWORD_FILE" --work "$NEW_PRIVATE_WORK" \
  --rotation-state "$PRIVATE_ROTATION_STATE" \
  --backup-timeout 120 --max-journal-bytes 268435456 \
  --journal "research=$RESEARCH_JOURNAL" --required-table research=events \
  --journal "evidence=$EVIDENCE_JOURNAL" --required-table evidence=runs
```

Adapt names and tables to the consumer's contract; `events` and `runs` are the
fixture tables. The work directory must be new. The password file must be outside
staging; its contents are never read or printed by the Python script. Keep the
repository, raw output, state and oracle private. Native `fcntl.flock` owns the
rotation lock; the `.lock` inode remains but process exit releases the lock.
A stale lock file is safe to reuse; a live holder causes visible refusal. Never
unlink it to bypass a holder. Native temporary-file plus `os.replace` publication
avoids stale `.new` collisions; preserve failed artifacts without resetting the
cursor. Source: `python/cpython@v3.12.3:Doc/library/fcntl.rst:139-149`.

Backup uses **`--group-by host,tags`**, with the stable host
`equity-research-recovery` and tag `journal-recovery`, so new staging paths share
a parent group. Any later `forget --keep-*` policy must use **the same grouping**,
filtered to that host/tag; first inspect `forget --dry-run --group-by host,tags`
with the chosen retention counts. Retention counts and deletion remain unaccepted;
this procedure performs neither forget nor prune. Sources:
`restic/restic@v0.19.1:doc/040_backup.rst:197-206` and
`doc/060_forget.rst:225-233`.
Controls are for **disposable repositories only**. Their backups use the distinct
host `equity-research-recovery-control` and tag `journal-recovery-control` with
the same `host,tags` grouping. An exit-3 control snapshot therefore cannot become
a production backup parent or count in production retention. The local drill
creates its disposable repository; never point a control at the operating repository.

Remote repository URLs are outside this local procedure. A second-host consumer
can run `verify --restored "$RESTORE" --inventory "$FROZEN_INVENTORY"` against
its independently retained oracle after the separately approved destination
restore. Key recovery belongs to user decision 3.

## Same-host operator drills and proof

Run [drill_process_restart.py](drill_process_restart.py) **later on the operating
host**, shortly before the next eligible 16:30 slot, using its locked trading
Python. Supply `--dagu-bin`, `--dagu-home`, `--config`, this one DAG's
`--dag-history` directory and the exact aware `--due-at` timestamp. The script
verifies an existing unit's MainPID and executable, then uses native
`systemctl --user kill --kill-whom=main --signal=SIGKILL <unit>` to address that
unit's current main process. The window must reserve **more than 150 seconds**
before due (90 seconds restart allowance plus 60 seconds margin) and 180 seconds
after due for completion; it is checked again just before fault delivery.
A restart observed at or after due fails with a distinct missed-slot reason.
The drill observes automatic restart and waits for the next successful due run.
Native history plus original `status.jsonl` must attest the exact `scheduleTime`
and scheduler trigger, with every required research step succeeded, while the
deployed UI has `run_dags: false`. A skipped evidence chain does not count. A manual run
does not count. The script installs, enables and starts no unit. SIGKILL induces
failure; under `Restart=on-failure`, clean SIGTERM need not trigger restart
(`systemd/systemd@v255:man/systemd.service.xml:818-836`
[source](https://github.com/systemd/systemd/blob/v255/man/systemd.service.xml#L818)).
Unit-addressed fault delivery is provided by
`systemd/systemd@v255:man/systemctl.xml:541-549,2377-2388`.
Dagu's supported REST run-details API also exposes `scheduleTime` and
`triggerType` (`dagucloud/dagu@v2.16.6:internal/service/frontend/api/v1/dagruns.go:2066-2096;
transformer.go:362,371`). This later acceptance drill retains original
`status.jsonl` to hash and corroborate the native bytes without an HTTP/auth
dependency. That internal format requires revalidation on a Dagu pin move.
The omitted `catchup_window` does not replay missed slots
(`dagucloud/dagu@v2.16.6:internal/cmn/schema/dag.schema.json:151-153`).

**A process-restart drill is not reboot, missed-run or independent-alert acceptance.**
It observes one process failure and the following slot. Host boot, downtime across
slots, catch-up, duplicate runs and independent notification need separate host
receipts and the chosen alert path.

Run the disposable local backup-check-restore drill with:

```sh
env TMPDIR="$PRIVATE_TMP" nice -n 19 python3 \
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
- `--control restore` alters the restored SQLite `user_version` header while
  integrity, required table counts **and file bytes remain equal**. The SHA-256
  comparison must make the procedure exit nonzero, proving that those secondary
  checks alone would accept incomplete recovery of the original state.

The [round 2 sanitized offline proof](evidence/offline-proof-r2.json) and
[local integration receipt](../../../evidence/receipts/trading-unattended-hosting-recovery-r2-20261005.json)
retain actual native output and command exits with separate observations.
The fixture is our integration check, using the unchanged restic 0.19.1 executable.
Neither operator drill was run on an operating service.

The scripts require **Python 3.11 or later**: `hashlib.file_digest` was added in
3.11 (`python/cpython@v3.12.3:Doc/library/hashlib.rst:267-302`). The builder checked
that API and executed on Python 3.13.15; it did not run a separate 3.11 interpreter.
The receipt notes the builder's RTK fallback; portable recipes require only plain
`env`, `nice`, the locked SDK where needed, and the upstream binaries. The retained
[round 1 proof](evidence/offline-proof.json) remains historical evidence.
The [native Dagu probes](evidence/native-dagu-probes-r2.json) observed both skip
and success chains. The [pinned cron Next probe](evidence/cron-next-probe-r2.json)
was prepared from v3.0.1 source but returned 127 because no Go compiler was found;
its DST expectations are recorded, not measured. No compiler was installed.

The [round 3 native DAG proof](evidence/native-dagu-probes-r3.json) executes all
six deployed steps in a private scratch copy with the locked SDK, synthetic
historical LEAN input and a fixed post-close guard clock. All six steps and the
run succeed; native history with `--context local --from <UTC Z> --status succeeded
--limit 1000` returns that manual run. Separate real-guard missing/stale/future
probes each exit 1 and record failed run/guard status 2 with no dependent marker.
The [round 3 recovery proof](evidence/offline-proof-r3.json) observes concurrent
WAL writes during both copies and verifies that both failing controls use their
separate host/tag group. These are local integration fixtures; no scheduler or
operating-host restart ran. The [round 3 receipt](../../../evidence/receipts/trading-unattended-hosting-recovery-r3-20261005.json)
pins tested source hashes and records the red/green regressions and native output.

## Why this glue exists

The [pinned native review](evidence/upstream-glue-review-r2.json) records installed
help, tagged release notes/source and the alternatives checked before repair.
Native `ecal` **does exist** in exchange_calendars 4.13.2. It renders calendars;
it provides neither the post-close eligibility token nor this input-freshness
contract. Native Dagu already owns preconditions, dependency skips, retries and
handlers; none is reimplemented here. No retry/handler policy is enabled by this
job, and independent alerts still need user decision 2.

| Kept integration | One-line gap justification at the pin |
| --- | --- |
| `session_day.py` | `gerrymanoim/exchange_calendars@4.13.2:pyproject.toml:67-68; exchange_calendars/ecal.py:100-149` ships a calendar renderer; its `exchange_calendar.py:1012-1016,1257-1279` APIs supply session/close queries, leaving our eligibility/freshness token as job policy. |
| `journal_recovery.py` | `restic/restic@v0.19.1:doc/040_backup.rst:679-703; doc/045_working_with_repos.rst:482-521; doc/050_restore.rst:55-73` supplies stream backup, partition checks and restore, leaving the external frozen oracle, required table contract, bounded rotation and failure controls to the consumer. |
| `drill_process_restart.py` | `systemd/systemd@v255:man/systemctl.xml:541-549,2377-2388` supplies unit-addressed kill and `man/systemd.service.xml:818-836` supplies restart; Dagu `@v2.16.6:internal/service/frontend/api/v1/transformer.go:362,371` supplies slot/trigger fields, leaving identity/time/holiday guards and exact-slot correlation as acceptance policy. |
| `drill_local_recovery.py` | `python/cpython@v3.12.3:Modules/_sqlite/connection.c:2067-2102` supplies Online Backup and restic `@v0.19.1:doc/050_restore.rst:55-73` supplies restore, leaving the concurrent-write fixture, two deliberately failing controls and path-free receipt as our local integration evidence. |

Specifically checked: `restic backup --stdin-from-command -- sqlite3 "$DB"
".backup ..."` captures **stdout**, while SQLite's `.backup` writes a destination
file (`sqlite/sqlite@version-3.53.1:src/shell.c.in:9074-9099`); it would save an
empty stream instead of that DB. `.dump` emits SQL (`src/shell.c.in:3759`), which
could form a logical restore procedure but does not preserve the already-frozen
binary file inventory. Keep the **native Online Backup API**, not a rebuilt SQLite
backup implementation. CPython's single native step has no wall-time argument
(`python/cpython@v3.12.3:Modules/_sqlite/connection.c:2011-2016,2075-2102`), so
stdlib subprocess timeout bounds it. Native `fcntl.flock` replaces our previous
exclusive-create lock/sentinel, including automatic release after a crash.

The maintained upstream **sqlite3_rsync** utility also copies live databases
(`sqlite/sqlite@version-3.53.1:tool/sqlite3_rsync.c:13-40`); it is a replication
protocol rather than this encrypted restic repository plus consumer-oracle
procedure. The final T **off-host-recovery row, line 102**, retains restic and the
stdlib Online Backup API; the prior hosting comparison deferred Litestream. This
repair keeps that decision and does not reopen it. The final row does not name
Litestream; the earlier comparison is recorded separately in the pinned review.

**The same-host drill cannot close the off-host-recovery gate.** Closure needs
**user decision 3**: an independent destination, key recovery and a restore by a
consumer on a second host, checked against the independent oracle and required
state. Its recovery-time objective must still be selected and measured. The
scratch proof establishes no off-host durability, retention deletion or alert.

Historical [Dagu receipt](receipt.json) and
[static-file backup acceptance](backup/README.md) retain their original scopes;
neither attests execution of the new scheduled templates.
