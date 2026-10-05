# Unit T PR-4: unattended research hosting and journal recovery

Date: 2026-10-05. Lane: trading. Builder base:
`4c897418fe35a030a1188ae447eaf31c893f8eff`.
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
  a non-session token skips the research chain without failing it.
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
  within seven days, at most 24 hours apart, persisting only successful checks;
  an overdue rotation needs a successful full `--read-data` check before reset.
  [Partitions](https://github.com/restic/restic/blob/v0.19.1/doc/045_working_with_repos.rst#L482).
- `restic/restic@v0.19.1:doc/050_restore.rst:55-73` restores an exact snapshot's
  subtree. Our consumer verifies exact inventory, hashes and bytes against an
  external oracle, then integrity and required-table counts as secondary checks.
  [Restore syntax](https://github.com/restic/restic/blob/v0.19.1/doc/050_restore.rst#L55).
- `systemd/systemd@v255:man/systemd.service.xml:818-836` defines on-failure
  restart. The later operator drill verifies identity before SIGKILL and uses
  Dagu's original status fields:
  `dagucloud/dagu@v2.16.6:internal/cmd/history.go:568-602`,
  `internal/persis/file/dagrun/dagrun.go:55-59`,
  `internal/ir/run_status.go:156-179`, `internal/ir/status.go:10-18,133-149`.
  History alone omits the slot/trigger, so it must be corroborated.
  [Restart policy](https://github.com/systemd/systemd/blob/v255/man/systemd.service.xml#L818).

The calendar lock was read at PR-1's actual bundle path
`blueprints/us-equities/runtime-2604/trading-2604-runtime/pyproject.toml:11`,
revision `d00e4e6eeb92c7c99066ea5d0bd85f379c931c4f`. The brief's shorter
`runtime-2604/pyproject.toml` path is absent at this base and in that worktree.
`manifests/stack.json` independently carries 4.13.2. PR-4 adds no lock and claims
no execution of the installed trading runtime.

Snapshot/restore glue and both drills belong in `hosting/`, which owns this
research job's recovery without adapter coupling. Each journal gets its own
Online Backup, an independently frozen file inventory and explicit required
tables. This does not provide atomic cross-journal transactions. No new timer
was enabled; the operator must meet the daily check interval.

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

The [local integration receipt](../../evidence/receipts/trading-unattended-hosting-recovery-20261005.json)
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
gap. Missed partition executions lose coverage; persistent cursor, 24-hour bound
and full reset address that gap. Remaining modalities are host reboot,
downtime/catch-up and duplicate-slot behavior, independent alerts, destination
and key loss, second-host consumer restore and measured recovery time. These
feed the next hosting/recovery lifecycle sweep and remain open.

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
