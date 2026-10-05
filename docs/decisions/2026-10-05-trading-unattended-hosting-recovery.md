# Unit T PR-4: unattended research hosting and journal recovery

Date: 2026-10-05. Lane: trading. Builder base:
`4c897418fe35a030a1188ae447eaf31c893f8eff`.
Repair round 2 base: `b3a01ce273952260df0b552d5075997b737b71ad`, whose tree
matches the coordinator's round 1 commit. No commit or pin move by the builder.
Repair round 3 starts from `f417d2257869b8fdf90ad91b3246196a8b6a81f2`.
North-star action: run US-equities local research/evidence after each NYSE
session and preserve the research journals needed to reproduce its state.
This implements the coordinator's final `decision-record-T-final.md`, lines
102-103 (gates), 233-237 (rejections), 267-271 (overturn), 297 (PR-4), 351
(residual) and 400-406 (Dagu/restic sources). The coordinator retains that record.

## Decision and alternatives

Retain Dagu **2.16.6** and restic **0.19.1**, without changing
`manifests/stack.json`. Run one `dagu start-all` process, disable the optional
coordinator in the config file, and deliver all four job variables in the
private DAG's `env:` block. The named schedule contract is
`nyse-post-close-evidence`, at 16:30 America/New_York on NYSE session days.
Early-close days keep the same execution time. The job processes existing local
simulation input and evidence; it does not connect to a broker.

The final unit T record rejected these alternatives for this owned job:

| Alternative | Reason; comparison that could reopen it |
| --- | --- |
| Prefect, Dagster, Temporal | Another orchestrator overlaps Dagu without a demonstrated research-job requirement (T rule D). A measured requirement Dagu cannot meet would justify a new comparison. |
| A second `dagu scheduler` unit | Two supervised units for one job; start-all already combines the needed services. Reopen if operating-host lifecycle acceptance misses due runs. |
| GitHub Actions market schedules | Dagu owns scheduling; that alternative's reliability was an unverified lead, not a tested advantage. A dated native reliability comparison could reopen it. |
| Coordinator setting in systemd `Environment=` | `/usr/bin/env -i` discards it. Keep the default override visible in the config file. |
| Coordinator setting as an `env -i` operand | Supported, but the config key keeps this choice visible in the checked-in example. |
| Copying active WAL journals; same-host-only repository | Copies can be inconsistent; the source host cannot provide off-host durability. Use Online Backup and keep the independent recovery gate open. |

This bounded builder read search-first and modern-python guidance; the supplied
pins, stdlib/unittest contract and no-services/no-install envelope take precedence
over broader registry searches, research agents or new tool installation. No
general landscape sweep or host memory/context service query was performed.

## Pinned sources and rules

The [hosting recipe](../../blueprints/us-equities/hosting/README.md) gives the exact
operator commands and source-linked rule table. The verified original sources are:

- `dagucloud/dagu@v2.16.6:internal/cmd/startall.go:32-45` (combined UI/scheduler,
  optional coordinator), `internal/cmn/config/loader.go:1311-1319` (enabled
  default). Installed `dagu start-all --help` and `dagu version` both returned
  exit 0, with version 2.16.6.
  [Start-all source](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/cmd/startall.go#L32).
- `coreutils/coreutils@v9.4:src/env.c:824-838` empties the inherited environment;
  `dagucloud/dagu@v2.16.6:internal/spec/dag.go:1663-1673` builds explicit DAG
  environment. This justifies placing `STACK_REPO`, `SDK_ENV`, `LEAN_EVENTS`
  and `RESEARCH_OUTPUT` in the DAG rather than in discarded `Environment=` lines.
  [env source](https://github.com/coreutils/coreutils/blob/v9.4/src/env.c#L824).
- `dagucloud/dagu@v2.16.6:internal/ir/schedule.go:281-305`,
  `internal/cmn/schema/dag.schema.json:855-876` and `go.mod:65`; its locked
  `robfig/cron@v3.0.1:parser.go:93-103` accepts `CRON_TZ`. The schedule name is
  a documented contract and tag, since the pinned cron object has no name key.
  [Timezone parser](https://github.com/robfig/cron/blob/v3.0.1/parser.go#L93).
- `gerrymanoim/exchange_calendars@4.13.2:exchange_calendars/exchange_calendar.py:1012-1016,1263-1279`
  queries the session and actual close;
  `exchange_calendars/exchange_calendar_xnys.py:157-165` defines 13:00 early
  and 16:00 ordinary closes. At 16:30 both are complete.
  [Calendar API](https://github.com/gerrymanoim/exchange_calendars/blob/4.13.2/exchange_calendars/exchange_calendar.py#L1263).
- `dagucloud/dagu@v2.16.6:internal/runtime/runner.go:1633-1648,1267-1281`
  skips a step on a false precondition and propagates the skip to dependents.
  A preceding normal calendar command exposes package/version/calendar failures;
  a covered non-session token skips the research chain without failing it.
  Bracket the queried year with prior December 1/following January 31, since
  `exchange_calendar.py:1257-1279` measures coverage by its first/last sessions.
  A January 1-to-December 31 window falsely raised DateOutOfBounds on New Year
  holidays; real 4.13.2 regressions reproduced that before the correction.
  [Precondition implementation](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/runtime/runner.go#L1633).
- `dagucloud/dagu@v2.16.6:internal/cmn/runenv/keys.go:12-13`,
  `internal/runctx/context_env.go:28` supplies `DAG_RUN_ID`, used in output
  filenames to preserve earlier evidence when the daily job repeats.
  [Run identifier](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/cmn/runenv/keys.go#L12).
- `dagucloud/dagu@v2.16.6:internal/service/frontend/api/v1/dagruns.go:163-167`
  guards the API with `permissions.run_dags`; its
  `internal/service/scheduler/dag_executor.go:280-321` dispatches locally without
  that API check. This source inference awaits operating-host observation of
  the configured scheduler with `run_dags: false`.
  [Local dispatch](https://github.com/dagucloud/dagu/blob/v2.16.6/internal/service/scheduler/dag_executor.go#L280).
- `python/cpython@v3.12.3:Doc/library/sqlite3.rst:1107-1155` documents concurrent
  Online Backup and the exact `src.backup(dst, pages=..., progress=...)` example;
  `Modules/_sqlite/connection.c:2067-2077` calls SQLite's Online Backup API.
  [Backup example](https://github.com/python/cpython/blob/v3.12.3/Doc/library/sqlite3.rst#L1107).
- `restic/restic@v0.19.1:doc/040_backup.rst:787-806` defines complete success
  (exit 0), fatal error (exit 1) and incomplete snapshots (exit 3). All nonzero
  exits refuse acceptance, including 3.
  [Exit codes](https://github.com/restic/restic/blob/v0.19.1/doc/040_backup.rst#L787).
- `restic/restic@v0.19.1:doc/045_working_with_repos.rst:482-521` defines
  deterministic `n/t` partition checks. Our policy rotates all seven subsets
  within seven days **per whole rotation**, persisting only successful checks;
  an overdue rotation needs a successful full `--read-data` check before reset.
  [Partitions](https://github.com/restic/restic/blob/v0.19.1/doc/045_working_with_repos.rst#L482).
- `restic/restic@v0.19.1:doc/050_restore.rst:55-73` restores an exact snapshot's
  subtree. Our consumer verifies exact inventory, hashes and bytes against an
  external oracle, then integrity and required-table counts as secondary checks.
  [Restore syntax](https://github.com/restic/restic/blob/v0.19.1/doc/050_restore.rst#L55).
- `systemd/systemd@v255:man/systemd.service.xml:818-836` defines on-failure
  restart. `man/systemctl.xml:541-549,2377-2388` supplies unit-addressed
  `kill --kill-whom=main --signal=SIGKILL`. The later operator drill verifies
  identity before native fault delivery and uses
  Dagu's original status fields:
  `dagucloud/dagu@v2.16.6:internal/cmd/history.go:568-602`,
  `internal/persis/file/dagrun/dagrun.go:55-59`,
  `internal/ir/run_status.go:156-179`, `internal/ir/status.go:10-18,133-149`.
  History alone omits the slot/trigger, so it must be corroborated.
  The supported REST run-details alternative exposes both fields at
  `internal/service/frontend/api/v1/dagruns.go:2066-2096; transformer.go:362,371`.
  Original `status.jsonl` is retained to hash/corroborate native bytes without
  an HTTP/auth dependency; its internal format must be revalidated on pin moves.
  [Restart policy](https://github.com/systemd/systemd/blob/v255/man/systemd.service.xml#L818).

The SDK_ENV lock evidence at this base is
`adoption/sdk/requirements-linux-x86_64-py313.lock:241` (exchange-calendars 4.13.2).
Round 1 cited an unlanded runtime bundle; that is not main's SDK_ENV authority and
has been removed from the current recipe. Round 2 executes the existing locked
SDK for real-calendar tests; it installs no environment and adds no lock.

Snapshot/restore glue and both drills belong in `hosting/`, which owns this
research job's recovery without adapter coupling. Each journal gets its own
Online Backup, an independently frozen file inventory and explicit required
tables. This does not provide atomic cross-journal transactions. No new timer
was enabled; the operator must run daily and complete every rotation within seven days.

## Round 2 native reuse and repairs

The 2026-10-05 standing rule applies on every new Linux/WSL operating host: use
clean maintained upstream installations, replacing only the consumer's integration
policy. The [native glue review](../../blueprints/us-equities/hosting/evidence/upstream-glue-review-r3.json)
records pinned installed help, release notes and source. Checked restic 0.19.1's
`--stdin-from-command`, SQLite 3.53.1's `.backup`/`.dump` and maintained
`sqlite3_rsync`, CPython's native backup/subprocess/flock, Dagu 2.16.6's
preconditions/retries/handlers and exchange_calendars 4.13.2's **ecal CLI**.
The final T off-host-recovery row **102** keeps restic with stdlib Online Backup;
the earlier hosting comparison deferred Litestream. This repair does not reopen
the selection. The final row itself does not name Litestream, so the review
records the earlier comparison separately rather than inventing a final-row quote.

`restic/restic@v0.19.1:doc/040_backup.rst:679-703` captures a command's stdout.
SQLite `.backup` writes a file (`sqlite/sqlite@version-3.53.1:src/shell.c.in:9074-9099`),
so invoking it as a restic stdin producer would capture an empty stream. `.dump`
emits logical SQL (`src/shell.c.in:3759`), not the frozen binary file inventory.
SQLite's own `sqlite3_rsync` copies live databases
(`tool/sqlite3_rsync.c:13-40`), without replacing restic's encrypted repository
and the external consumer oracle. The existing CPython Online Backup API is the
native copying function; we do not rebuild it.

### Why this glue exists

| Kept glue | One-line pin-cited reason |
| --- | --- |
| `session_day.py` | exchange_calendars `@4.13.2:pyproject.toml:67-68; exchange_calendars/ecal.py:100-149` ships calendar rendering, leaving our post-close and input-freshness token to compose its native session/close API. |
| `journal_recovery.py` | restic `@v0.19.1:doc/040_backup.rst:679-703; doc/045_working_with_repos.rst:482-521; doc/050_restore.rst:55-73` supplies backup/check/restore, leaving the frozen external oracle, required tables, bounded rotation and controls as consumer policy. |
| `drill_process_restart.py` | systemd `@v255:man/systemctl.xml:541-549,2377-2388; man/systemd.service.xml:818-836` supplies unit-addressed kill and supervision; Dagu `@v2.16.6:internal/service/frontend/api/v1/transformer.go:362,371` supplies slot/trigger, leaving identity/time/holiday guards and exact-slot correlation as acceptance policy. |
| `drill_local_recovery.py` | CPython `@v3.12.3:Modules/_sqlite/connection.c:2067-2102` supplies copying and restic `@v0.19.1:doc/050_restore.rst:55-73` supplies restore, leaving synthetic concurrent writers, failure controls and sanitized evidence as our integration fixture. |

**Replaced** the exclusive-create lock sentinel with native `fcntl.flock`
(`python/cpython@v3.12.3:Doc/library/fcntl.rst:139-149`); process exit releases
the lock even when its file remains. Dagu supplies dependency skipping,
preconditions (`internal/runtime/runner.go:1267-1281,1633-1648`), retries
(`:1502-1525`) and lifecycle handlers (`:1196-1206`) natively. No Python retry,
handler or scheduler implementation is added, and this job enables no retry
or alert handler policy. An independent alert path remains decision 2.

The recovery worker calls native `Connection.backup(..., pages=-1)` in one read
transaction, permitting concurrent WAL writers while avoiding incremental-copy
restarts (`python/cpython@v3.12.3:Modules/_sqlite/connection.c:2013,2067-2102`).
It checks source `PRAGMA journal_mode` and refuses non-WAL journals unless
`--allow-non-wal` explicitly accepts rollback-journal writer blocking. The read
transaction holds a SHARED lock for the whole bounded copy; those writers can
receive `SQLITE_BUSY` at commit. Prefer quiescing writers before opting in
(`sqlite/sqlite@version-3.53.1:src/backup.c:346-354,383-389`).
That API has no hard wall-time parameter; `subprocess.run(timeout=...)` bounds
the isolated worker (`Doc/library/subprocess.rst:62-68`). The documented defaults are **120 seconds and 256 MiB per
journal**, with explicit `--backup-timeout`/`--max-journal-bytes` parameters;
failed/oversize/timed-out snapshots publish no inventory. Each per-journal
snapshot is consistent; simultaneous commits need not all appear in that snapshot.

Rotation now timestamps the invocation before snapshot/backup, bounds completion
of the **whole seven-subset cycle** in UTC, and accepts 24 h + 60 s jitter and
the 2026-11-01 fall-back. It refuses incomplete overdue cycles, clock reversal,
over-seven-day idle gaps and old state until successful full checking. Backup
and any later forget policy group by **host,tags**
(`restic/restic@v0.19.1:doc/040_backup.rst:197-206; doc/060_forget.rst:225-233`),
so disposable staging paths share parent/retention groups. No forget/prune ran.
Control backups use a separate `equity-research-recovery-control` host and
`journal-recovery-control` tag, isolating incomplete snapshots from production
parents/retention. Controls are documented for disposable repositories only.

The seven research-runtime passthrough entries are restored as well as the four
scheduled-job entries: Dagu's allowlist is at
`dagucloud/dagu@v2.16.6:internal/cmn/config/loader.go:344-347; internal/cmn/config/env.go:77-95`.
The research operator's simulation job must atomically publish `LEAN_EVENTS`
after the session's actual close **by 16:25 New York**. Its mtime must be between
close and check time. Missing/stale/future tokens exit 1 and fail the native run,
blocking its dependents and remaining visible to failed-history/handler queries.
Only covered non-session/before-close tokens retain a skipped research chain.
This availability check does not establish market-data
freshness or point-in-time correctness inside the file.

The hosting README again carries the verified pinned-download/checksum recipe,
0600 private config/DAG, loopback exposure warning, auth transition note,
historical 2.17.2 artifact boundary and operator-only systemctl lifecycle steps.
It adds native `loginctl enable-linger` (`systemd/systemd@v255:man/loginctl.xml:186-195`)
and the caveat that linger cannot extend Windows/WSL VM lifetime. Portable
templates use plain `env TMPDIR=... nice -n 19 python3 ...`; the builder's actual
commands used RTK's fallback, recorded separately from the portable recipe.
Recovery uses Python **3.11+**, because `hashlib.file_digest` was added then
(`python/cpython@v3.12.3:Doc/library/hashlib.rst:267-302`); execution used 3.13.15.

The drill resolves its scratch root at creation, scrubs lexical and canonical
forms and refuses any remaining absolute path before publishing `--output`.
The restore control now alters SQLite header content while integrity, required
counts and file bytes remain equal; external SHA-256 comparison still refuses it.
Tests cover symlinked roots, both controls, native lock contention/stale files,
slow/overdue rotation, real holiday/early-close calendars and native Dagu
skip/success chains, all on scratch directories without a scheduler.

## Round 3 corrections and verification

The cross-family read found seven new p2 defects and a missing manual run/cancel
recipe. Each behavioral regression was run against the old code first (exit 1),
then against its scoped repair (exit 0), including a native Dagu failure probe.
The hosting recipe restores native `start --run-id`, `stop --run-id` and
`history --status succeeded,failed,aborted` commands for operator inspection and
replay (`dagucloud/dagu@v2.16.6:internal/cmd/start.go:45-67; stop.go:20-38,53-91;
history.go:160-345; flags.go:463-481`; all three installed help commands exit 0).

Native systemctl fault delivery replaces `os.kill`; identity guards remain.
The restart window reserves more than 150 seconds, rechecks immediately before
the fault and refuses a restart observed at/after due with a distinct reason.
Dagu does not replay missed slots when `catchup_window` is omitted
(`dagucloud/dagu@v2.16.6:internal/cmn/schema/dag.schema.json:151-153`).
No operating-host process was signalled during this repair.

The historical round-2 receipt now names the published main base and explicitly
identifies its tested working tree by `integration_source_sha256`; its old source
hashes and results remain historical. The native test helper uses its private
scratch root even with caller `TMPDIR` unset. Round-3 verification uses the locked
SDK, so real-calendar tests execute rather than skip. Fresh native evidence is
recorded in the [native DAG artifact](../../blueprints/us-equities/hosting/evidence/native-dagu-probes-r3.json),
[recovery artifact](../../blueprints/us-equities/hosting/evidence/offline-proof-r3.json) and
[local-integration receipt](../../evidence/receipts/trading-unattended-hosting-recovery-r3-20261005.json); a private copy of
the deployed DAG uses synthetic post-close time/input, not a live market run.

Round 4 restores the round-2 review's exact `f417d2257` bytes and its original
receipt hash/15859-byte pin. Round-3 additions have a separate review linked by
the round-3 receipt; its parent link retains the earlier native observations.
The operator replay window is the same New York date after that session's close,
with input mtime after close; later runs skip or process another session.
Native `dagu status --run-id` must show every research node succeeded before
replay counts as recovery (`dagucloud/dagu@v2.16.6:internal/cmd/status.go:18-47`).
The restart drill refuses unit globs before fault delivery, because literals
refer to exactly one unit (`systemd/systemd@v255:man/systemctl.xml:1826-1833`).

## Dagu 2.16.6 to 2.18.2 scheduler comparison

Read both tagged source trees, the available intervening release notes at tags,
and the full `internal/service/scheduler/` diff. The
[comparison artifact](../../blueprints/us-equities/hosting/evidence/dagu-scheduler-comparison.json)
records original source hashes, changes and exact locators.
[2.17.0](https://github.com/dagucloud/dagu/releases/tag/v2.17.0) describes
global queue pacing and queued retries (#2775);
[2.18.0](https://github.com/dagucloud/dagu/releases/tag/v2.18.0) describes
scheduler dotenv loading (#2937);
[2.18.2](https://github.com/dagucloud/dagu/releases/tag/v2.18.2), published
2026-10-04, describes busy-slot logging (#2980), optional signal propagation
and shutdown changes. Release metadata for v2.17.1 returned HTTP 404; no claim
about that missing release's contents is made.

The production scheduler diff changes five files: environment preparation,
queued-condition state and failures, retry liveness, suspension migration and
shutdown, global queue admission and busy-slot logging. Relevant locators at
`dagucloud/dagu@v2.18.2` are
`internal/service/scheduler/dag_executor.go:468-475`,
`tick_planner.go:758-784,1560-1568,1658-1661`,
`scheduler.go:607-614,842-855`, `retry_scanner.go:165-181` and
`queue_dispatcher.go:929-950`. The cron model/parser, precondition mechanism,
catch-up and durable schedule state were separately compared as well.

**No compared fix is required by this job's defined schedule.** It uses a
five-field cron, explicit DAG `env:`, local execution, no dotenv, no configured
global queue, no distributed workers, no retry policy, no SMTP and no catch-up
acceptance claim. Busy-slot additions improve observation without changing skip
guards. The dotenv fix would matter after switching to dotenv; optional graceful
signal propagation does not underwrite a SIGKILL process drill. This is source
comparison, not execution comparison or a claim that 2.16.6 is the newest pin.
Hold 2.16.6 provisionally and route any justified move through the foundation owner.

The comparison also checked descriptor/interval additions in
`dagucloud/dagu@v2.18.2:internal/ir/schedule.go:17-19,281-345` and interrupted
precondition handling in `internal/runtime/condition.go:19-82`. Neither is needed
by the explicit five-field cron and single scalar eligibility comparison used
here; interrupted-precondition behavior remains outside the claimed acceptance.

## Evidence, corrections and completeness critic

The **round 2** [local integration receipt](../../evidence/receipts/trading-unattended-hosting-recovery-r2-20261005.json)
and [offline proof](../../blueprints/us-equities/hosting/evidence/offline-proof-r2.json)
retain a fresh native backup/check/restore of **16,531,456 journal bytes** and
independent committed-write observations within each single `pages=-1` native
call. Snapshot refusal is native exit **3**, procedure exit **1**; restore
mutation is native restore exit **0**, procedure exit **1**, with equal integrity,
required counts and bytes. The throwaway password was deleted. **42 tests**
passed, including six real-calendar cases, genuine DateOutOfBounds, freshness,
both controls, native lock contention/stale state, whole-cycle jitter/fall-back,
restart guards, symlinked scratch roots and Python 3.11-compatible syntax.

The [native Dagu record](../../blueprints/us-equities/hosting/evidence/native-dagu-probes-r2.json)
retains non-session and stale-input skips plus an executed success chain, all
with native CLI exit **0**. Skips have node status **5**, successful steps **4**.
These are manual short-lived runs, not scheduler or host restart acceptance.
The verdict JSON has `nv_summary` without the referenced `nv[2]` recipe; the
probe therefore uses the pinned upstream scalar-precondition/dependency pattern.
Native `dagu validate` on the revised DAG also returned **0**.

The pinned [cron Next probe record](../../blueprints/us-equities/hosting/evidence/cron-next-probe-r2.json)
holds the tiny Go program and local v3.0.1 module prepared from tagged source.
Execution with module networking disabled returned **127**: `go` was not found
in PATH or the checked standard/ecosystem locations. No compiler was installed
under the source-only network constraint. The supplied expected results,
2026-11-02T21:30Z and 2027-03-15T20:30Z, are **not measured Next results**; this
uses the user's explicit option to record why the probe cannot run.

Round 2 completeness critic: the native skip probes showed that Dagu can report
overall success while the research chain is skipped. The process-restart drill
now requires **every required research step** succeeded before counting the due
slot. Input mtime is only a producer availability contract, not proof of the
market dates/content. A strict per-step interval hid daily jitter and DST; a
whole-cycle UTC deadline plus completion check covers those cases. Sentinel
lock files could survive crashes; native process-owned locks address that gap.
During artifact publication the sanitizer first refused a relative `./` module
path; its absolute-path test now admits relative paths and has a regression.
The remaining modalities are actual operating-host lifecycle/independent alerts,
an executable cron Next probe, real consumer journal selection and state,
independent destination/key recovery, second-host restore and measured RTO.
They remain limits for the next hosting/recovery sweep.

The historical **round 1** [local integration receipt](../../evidence/receipts/trading-unattended-hosting-recovery-20261005.json)
and [offline proof](../../blueprints/us-equities/hosting/evidence/offline-proof.json)
retain actual native restic output on scratch directories. Two synthetic WAL
journals were each written while their Online Backup was active, then restored
with exact bytes and required state. Subset 1/1 reads every pack in this small
proof. The unreadable-snapshot control observed native exit 3 and procedure exit
1; the missing-restored-file control observed native restore exit 0 and procedure
exit 1. The throwaway password was generated privately and deleted. Stdlib tests
exercise the default seven-part rotation, failed checks, stale-state refusal
and altered content preserving integrity and row counts. These are local
integration and synthetic tests, not an unchanged upstream suite.

Corrections retained this turn: an initial lookup under `internal/scheduler/`
matched no files and was not an empty-diff result. `rg` located
`internal/service/scheduler/`, whose full tagged diff was then read. The calendar
tag is `4.13.2`; the `v4.13.2` URL returned HTTP 404 and was corrected against the
existing native calendar receipt and actual source. The pyproject location was
corrected as above. These source-location mistakes changed no pin or acceptance.

Completeness critic: process liveness alone cannot attest a due slot, so the later
drill checks original scheduler trigger and slot. Same-count mutation bypasses
count/integrity-only checks; external hashes and a mutation test address that
gap. Missed partition executions lose coverage; persistent cursor, seven-day whole-cycle bound
and full reset address that gap. Remaining modalities are host reboot,
downtime/catch-up and duplicate-slot behavior, independent alerts, destination
and key loss, second-host consumer restore and measured recovery time. These
feed the next hosting/recovery lifecycle sweep and remain open.

Round 6 on 2026-10-05 corrects six review threads without changing historical
proof or receipt bytes. The guard now fails visibly with `late_input` when
publication misses the documented 16:25 New York cutoff; replay uses that same
cutoff. Oracle publication applies mode 0400 before file fsync and syncs the
parent directory (`python/cpython@v3.12.3:Doc/library/os.rst:996-1005,1077-1087`).
Rotation checks the previous cycle origin even when its cursor has returned to
1; an overdue rollover requires a successful native full read before reset.
Daily jitter still fits each whole rotation, but can require that full read at
rollover. The restart drill parses its active file permission with upstream
PyYAML 6.0.3 (`yaml/pyyaml@6.0.3:lib/yaml/__init__.py:117-125`), including Dagu's
default and legacy override (`dagucloud/dagu@v2.16.6:internal/cmn/config/loader.go:586-611`).
Its operator Python therefore additionally needs the documented PyYAML install;
no YAML parser is rebuilt here. It parses and hashes the same captured native
status bytes, tolerating a replaced directory entry while polling. The round-3
receipt is now discoverable in the receipt catalog with its original claim and
limitations. Focused regressions cover each correction; earlier receipts remain
dated evidence of the earlier behavior and do not attest these repairs.

## Overturn and limits

| T overturn row | Reopen when |
| --- | --- |
| Scheduler | A restart or reboot drill on the operating host misses a due run, or the 2.18.2 comparison finds a fix the drill depends on; bump through the foundation pin path first. |
| Coordinator setting | A Dagu pin move drops or renames `coordinator.enabled`; re-check `dagu start-all --help` on every move. |
| Recovery | A restore rehearsal fails the inventory/hash comparison or recovery-time objective, or the journal changes to a store with a different supported snapshot method. |
| Calendar | A dated comparison with official NYSE dates finds a material error in the grid, or exchange_calendars no longer covers the next session year. |

The operating host and independent alert path remain **user decision 2**.
Neither operator drill was run against an operating service. A process-restart
drill is not reboot, missed-run or independent-alert acceptance. The same-host
drill cannot close the off-host-recovery gate: closure needs **user decision 3**,
an independent destination, key recovery and a restore by a consumer on a second
host under a selected and measured recovery-time objective. Scratch execution
and local template validation close neither gate. No broker credentials, live
mode, paid hosting, retention deletion, model calls, commit or push belong to
this unit.
