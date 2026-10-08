# Move the upkeep functions to Dagu (2026-10-06)

CC082012Z's Oct8 retirement continuation is recorded in
[RETIREMENT-20261008.md](../../adoption/templates/dagu/RETIREMENT-20261008.md).
It adds the missing native-data invocation, preserves the already deployed
progress/disk owners and current paper-window holds, and records deployment gaps
without promoting the original authoring checks to host acceptance.

## Decision and scope

The approved environment-transfer plan selects Dagu for the workstation's
upkeep, research-progress, stack-currency, token-report-refresh and
host-requests jobs. Main-pin and live-clone-sync become one job. The work serves
the foundation used for US-equities research and historical simulation; it does
not move broker timers or perform broker operations.

The six definitions live in `adoption/templates/dagu/`. Their commands must
come from the source distribution's units and scripts, with portable paths and
documented differences in scheduling. The co-op installs the reviewed files on
the destination, runs each job once and records its actual result. This change
does not authorize the authoring lane to apply anything on either host.

Internal authority: command-center item
`task-ns2604-coop-20261006T031317Z`, the approved full-resolution plan dated
2026-10-05 (SHA256
`775119dc6840552def19142a10e2730b489b6365c346e6f9fb6f5db5f2572ba2`,
Phase 1, lines 97-105), and the co-op's P1-DAGU direction dated 2026-10-06.

## Supported Dagu format

The destination's native `dagu version` reports **2.18.2**. Its matching
[maintainer release](https://github.com/dagucloud/dagu/releases/tag/v2.18.2)
was published on 2026-10-04. All field references below use
`dagucloud/dagu` commit
`5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4`, the target of that tag.

The embedded [DAG schema](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/internal/cmn/schema/dag.schema.json)
defines `description`, `schedule`, `catchup_window`, `overlap_policy`,
`hist_retention_days`, `timeout_sec`, `env` and `steps`. A local step uses
the canonical v2 `run` field; a shell override uses `with.shell`. The legacy
step fields `command`, `script` and `shell` are deprecated. The local backup
definition supplies the destination's existing schedule/catch-up/history
conventions; those conventions are not proof that a new job has run.

Do not copy the backup definition's `max_active_runs: 1`: the same schema marks
that field deprecated and ignored for local DAG queues. The pinned
[queue processor](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/internal/service/scheduler/queue_processor.go#L414-L420)
creates a local queue with concurrency one. This describes scheduler queue
dispatch, not a promise that arbitrary external processes cannot overlap.
`overlap_policy` governs missed-interval catch-up, not every kind of concurrent
invocation. Omit catch-up where the source timer has `Persistent=false`.

Native `dagu validate` is the own check for the definitions. The pinned
[validation command](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/internal/cmd/validate.go#L75-L84)
loads the spec with `WithoutEval()`. Use an isolated config and home for this
check; it is a parse/definition check, not a GREEN host run.

The destination scheduler does not currently provide the source unit
templates' private umask or `NoNewPrivileges` setting. Carry `umask 0077`
inside each job and use the installed non-set-user-ID
[`setpriv --no-new-privs` wrapper](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/sys-utils/setpriv.1.adoc#L58-L59)
where the source unit requires it. Low I/O priority uses
[`ionice -c 2 -n 7`](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/schedutils/ionice.1.adoc#L48-L52);
heavy work uses `nice -n 19` under the approved lane bounds. Both util-linux
commands report **2.41.3** natively. Their references use its matching tag
commit `5305e6c70b274f679329b79c0e1ef5a07e9dc1a6` and
[release notes](https://github.com/util-linux/util-linux/blob/5305e6c70b274f679329b79c0e1ef5a07e9dc1a6/Documentation/releases/v2.41.3-ReleaseNotes).
This carries job-local settings without changing the scheduler service.

## Not-needed record

| Date (UTC) | Source function | Status | Reason and boundary |
| --- | --- | --- | --- |
| 2026-10-06 | `native-stack-production-hindsight-ensure.timer` and its service | not-needed | The approved transfer plan explicitly excludes hindsight-ensure. ai-memory is the recorded interim memory owner; the D3r4 candidates, including Hindsight and Cognee, remain isolated in StackMeasure2604. No Hindsight ensure job is installed by this change; historical data preservation remains a separate retirement task. |

The memory boundary is recorded in command-center item
`task-ns2604-coop-20261005T041934Z` and the pinned
[repository-quality rule, line 38](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ecfa112764c664d35377dd66b8cfcb67e5a94d60/docs/decisions/2026-10-04-repository-quality-rule.md#L38).
This row does not stop a source service, delete state or pre-select a D3r4
winner.

## Alternatives and acceptance

Native source review after the cold-boot hold is recorded in the
[source map](../../adoption/templates/dagu/source-map.md). All four invoked
repository scripts hash-match base `ecfa112764c664d35377dd66b8cfcb67e5a94d60`.
Upkeep is a native Claude print task, not a missing standalone upkeep script;
main/live sync are inline unit commands ported into two small helpers.

The source progress emitter hardcodes Loki 13100, while NativeStack2604 uses
21300. The co-op's dashboards builder owns its backwards-compatible
`--loki-url` port and both emitter files (A8, 2026-10-06T04:58:49Z); this lane
uses its reviewed runtime copy and does not edit those files. The co-op
sequences that PR first. Until the reviewed emitter exists, the progress job
cannot claim a host GREEN run.

The source host-request drop-in posts text to ntfy 18080. A7/A8 select the
existing native Alertmanager on 21093, using its
[API v2 JSON contract](https://github.com/prometheus/alertmanager/blob/73c6bfe7393929211294c1954f30d8ed78e4d0ad/api/v2/openapi.yaml)
at installed **0.34.1**, and the command center's value-free
critical/unit/host label shape. The new explicit option preserves the existing
ntfy option. Its scoped runtime copy selects the live role repository with
`--stack-root`; neither sign-ins nor Telegram receiver secrets are copied.
API acknowledgement/appearance is the co-op's bounded notice oracle; it is
not claimed as a Telegram-delivery receipt.

The co-op's 2026-10-06T05:04:26Z resource-window correction supersedes the
earlier brief: protect 10:35-13:45Z and 19:50-00:10Z on 2026-10-07, with no
heavy phase or user-manager restart. Sync/upkeep preconditions check their
full duration before starting; they defer and never kill a running case.
Upkeep's daily slot moves from 07:30 to 09:45 America/New_York so its first
scheduled invocation is after the widened morning window. The guard is
explicitly dated; it does not claim to know later paper-session windows.

Retaining separate systemd upkeep timers would preserve their scheduling
mechanism but would contradict this approved Dagu move. Copying private host
paths into YAML would leave the new host dependent on the source layout.
Reimplementing the maintenance functions before reading their source would
leave parity unproved. The selected approach ports their supported commands
and explicitly records differences between systemd timer and Dagu scheduling.

Acceptance consists of the repository validator, relevant tests, Dagu's native
definition validation and `git diff --check`, followed by the co-op's install,
one successful real run per job and an exact-run `dagu status` or JSON history
read-back. The pull request carries apply and rollback commands. Authoring
checks and synthetic fixtures never substitute for those host run receipts.

Overturn this choice if the installed Dagu cannot represent a required source
function, loses a required safety boundary or fails its native run/read-back.
Report that bounded incompatibility to the owner rather than silently dropping
the function or treating a skipped run as successful acceptance.
