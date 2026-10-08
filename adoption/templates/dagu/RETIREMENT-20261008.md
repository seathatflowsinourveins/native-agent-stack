# NativeStack retirement: missing upkeep only — 2026-10-08

CC082012Z assigns this branch's custody to orch-records. Read-only observations
on NativeStack and NativeStack2604 at 08:59–09:07Z identify one additional
function missing from the original six-definition port: native-data collection.
The unchanged collector at main `28af9b9321d0492f6cdabe75091376560e7cdc4d` is
`observability/native-data/snapshot.py`, SHA256
`ec68f05a9dea2c8d3e37888b2928760bd085ce1567bcdd09145e82a6196fb68b`.
The [existing collector recipe](../../../observability/native-data/README.md#scheduled-deployment)
and native service/timer examples remain its source implementation. This port
adds only a Dagu invocation of that command.

| Source function | Current destination coverage and required work |
| --- | --- |
| Main pin + live-clone/QMD sync | Existing `native-agent-stack-sync.yaml` is prepared; deployment and live clone/helpers are missing. |
| Native Claude upkeep | Existing `ecosystem-upkeep.yaml` is prepared; deployment/task/helpers are missing. |
| Currency due-file | Existing `stack-currency.yaml` is prepared; deployment is missing. This reads the due file; it does not authorize the held7-LOCK install. |
| Token-report refresh | Existing `token-report-refresh.yaml` is prepared; deployment is missing; the destination private config pointer exists, contents uninspected. |
| Host requests | Existing `host-requests-workstation.yaml` is prepared; deployment/runtime copy is missing. |
| Native-data snapshot/publish | New `ecosystem-native-data.yaml` invokes the unchanged collector. No destination collector or private config was found; prepare a destination-owned config from the public example and documented schema. Do not copy a source private config or credential. |
| Research progress | Already owned by `ns2604-research-progress.timer`, startup15s /30s after completion. Its latest observed activation returned1; cause uninspected. Preserve that owner and report its failure; do not activate a second progress scheduler as a missing port. The earlier Dagu definition stays a prepared reference. |
| Disk headroom | Existing destination `disk-headroom-guard.timer` is active and its latest invocation returned0. No port is needed. |
| Hindsight ensure | The existing dated decision marks it not-needed, with ai-memory as interim owner. It still runs on the source. Keep the explicit exclusion distinct from a stopped-source claim; historical preservation and any changed adoption ruling stay with the CC. |

Dagu remains2.18.2 at maintainer pin
`5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4`. Native-data's `*/2` wall-clock
schedule approximates source boot45s / active2min / accuracy10s; it does not
reproduce the boot delay or source phase. The collector's own nonblocking lock
is unchanged. Source `UMask=0077`, `NoNewPrivileges`, 90-second bound, explicit
Node-capable PATH and disabled RTK telemetry are carried from the existing native
service example. A Node22-or-later runtime must already exist; this port installs
no runtime.

Use the README's native staging/inverse procedure for the six currently missing
functions: `native-agent-stack-sync`, `ecosystem-upkeep`, `stack-currency`,
`token-report-refresh`, `host-requests-workstation`, `ecosystem-native-data`.
Read the current operator freeze before any invocation; do not run the README's
older all-six activation loop unchanged because it includes the already owned
progress function. Stage outside the watched DAG directory, run only selected
missing jobs through their supported commands when released, and retain exact
native status/history and expected output. A skipped run, parse pass or successful
status-query exit is not a deployment GREEN.

As of CC084038Z, the runtime freeze stays in effect until the CC posts
`PAPER-WINDOW-CLOSED`; Alpaca paper is reserved for N2 from13:00Z. Quiet10:35–13:45Z
forbids wave1 jobs/runtime installs and gateway restart from11:30Z. The existing
`heavy-window-check.sh:17` and `:18` contains Oct6/7 epochs and provides no Oct8
coverage. This record does not add or change a guard rule, infer release from the
clock, start a job, install a DAG or restart a manager. Conflicting activation
goes to the CC as a question.

Native definition check for the new port is unchanged Dagu `validate` with an
isolated empty config/home, which upstream implements with `WithoutEval()`.
The collector source is unchanged; no new runner, parser or broker operation is
introduced. Native config/publish acceptance is pending: the destination private
config is absent. When deployed, the collector's compact result must name its
snapshot hash/row states and actual Loki204; unknown source measurements remain
unknown. Inverse: remove only the new owned native-data DAG (or restore its saved
predecessor) and its newly created private state/config if withdrawal is directed;
leave the existing scheduler, progress and disk owners intact.
