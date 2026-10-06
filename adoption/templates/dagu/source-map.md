# Native upkeep source mapping (2026-10-06)

Evidence class: **source review**, not a host deployment, model run or measured
scheduler acceptance. Read-only NativeStack interop first ran at
**2026-10-06T04:26:27Z**, after the cold-boot hold. Stdin/output declarations were
read at 04:28:26Z; invoked scripts and upkeep stdin at 04:29:26Z. Each timestamp
came from native `date -u`. Environment-file declarations were pointers only;
no credential file, value or process environment was read.

## Functions and scheduling

| Dagu definition | Actual source function | Source timer | Dagu mapping |
| --- | --- | --- | --- |
| `ecosystem-upkeep` | Native Claude print: opus, max effort, auto mode, 80 turns; task stdin; private append log; one qualified maintenance cycle | Daily 07:30 America/New_York; jitter 10 min; persistent | 09:45 local cron, moved after the corrected paper window; 2-day catch-up, latest missed slot. Live-sync dependency remains weak, with failures visible. Claude body retains its 45-minute bound. |
| `ecosystem-research-progress` | `observability/grand-dashboard/progress.py --repo LIVE --cache CACHE`: public checkpoint snapshots, changed-data publish or ten-minute heartbeat | Startup 15 s; 30 s after completion; accuracy 5 s | One minute job, two source-derived checks separated by 30 s and dependency ordering (co-op A6, 2026-10-06T04:14:17Z). Each check retains the 20-second source bound. |
| `stack-currency` | `scripts/currency_due.py`, with the live clone as the source | Daily midnight; jitter 15 min; persistent | Midnight local cron, 2-day catch-up, latest missed slot. Actual source has no surface-watch dependency; only the due-file function moves. |
| `token-report-refresh` | `tools/token-report/token_manifest.py refresh --config CONFIG`; weekend 05-08 quiet condition; offline/update-check settings | 03:15, 10:15, 16:15, 22:15 local; nonpersistent | Same local slots, no catch-up. Quiet condition, 900-second bound, private umask, NoNewPrivileges and idle I/O carried. CONFIG remains a pointer; the new clone needs its maintained initializer. |
| `host-requests-workstation` | `scripts/host_requests.py poll --role workstation`; actual notify.conf adds loopback ntfy text notices | Startup 2 min; 10 min after completion; jitter 1 min | Ten-minute wall-clock slots. Preserve polling and bounded notice delivery; transport requires the destination's supported contract. |
| `native-agent-stack-sync` | Clean tracked main pin plus clean live-clone detach/update, then scoped `qmd --index native-agent-stack-catalog update` | Main: boot 5 min, 15 min active period, jitter 60 s. Live: boot 2 min, 15 min active period, persistent | One quarter-hour job with main-pin before live-sync. No embedding/GPU call. Dirty work and unpushed branch references are preserved. |

Dagu cron slots are wall-clock based. The source startup/boot delays, random
jitter and completion-relative timer anchors are not reproduced exactly.
The co-op's explicit first GREEN run establishes the initial invocation.
The source's unbounded persistent-timer replay is replaced with the declared
finite catch-up for daily jobs; no systemd timer watermark is imported.
Progress's two checks preserve roughly the source observation frequency, not
an exact monotonic phase or a measured scheduled result. The separate
command-center dashboard timer keeps its own ownership.

The co-op's 2026-10-06T05:04:26Z correction widens the protected windows to
10:35-13:45Z and 19:50-00:10Z on 2026-10-07. Heavy sync/upkeep use a native
precondition that rejects a start whose full declared bound overlaps a window.
It defers before a case starts and never kills a running case. Upkeep's old
07:30 local slot would fall inside the morning window, so its new daily slot
is 09:45 local. The guard is dated to this declared window; later operator
directions must supply updated resource windows rather than assuming it covers
future sessions. No user-manager restart is part of deployment.

The installed Dagu 2.18.2
[scheduler](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/internal/service/scheduler/scheduler.go#L820-L894)
ticks on minute boundaries and its
[planner](https://github.com/dagucloud/dagu/blob/5ca5c59f6b67734c9f0ae186bd59f5e0bb5846f4/internal/service/scheduler/tick_planner.go#L663-L684)
selects at most one live start candidate per DAG per tick. A parsed
`@every 30s` is not evidence for two scheduled checks per minute.
The 30-second pause uses installed uutils coreutils 0.10.0,
[commit 28b6856d](https://github.com/uutils/coreutils/tree/28b6856d7b215bf844b4223589cb54ade84f5223),
with its native `sleep` help confirming seconds.

## Source hashes

All four invoked repository scripts exactly matched the owned base
`ecfa112764c664d35377dd66b8cfcb67e5a94d60`. Their original sources are available
at that [repository pin](https://github.com/seathatflowsinourveins/native-agent-stack/tree/ecfa112764c664d35377dd66b8cfcb67e5a94d60).

| Invoked source | Native SHA256 | Exact base match |
| --- | --- | --- |
| `observability/grand-dashboard/progress.py` | `9c386558e4f07d659179750d218bd78a8898c68b198e70e73484040a63110740` | yes |
| `scripts/currency_due.py` | `4b2e9ecd31ebe0801d7ae44f958a173b372819a0b1984838277502a13ebfb9fe` | yes |
| `tools/token-report/token_manifest.py` | `57c98b9b1389315a06de47f59d6d4708e00f44959e02a717f14e0c500365b8b4` | yes |
| `scripts/host_requests.py` | `8f00d9b7fe1d5fa506b3ad071b093e0d7572e4c80ca29c865e28b2e7c3b8fdc5` | yes |

The actual upkeep task input's original SHA256 was
`4e06ff5e6cd18e01afcb322f6601833a2364581fec584ac8281d27d8d05dacd0`.
The versioned task normalizes its private practice-checkout path, describes
Dagu scheduling and retains current operator scope/resource boundaries.
It does not carry a historical source-file claim as new authorization.

| Source unit or drop-in | Raw source SHA256 |
| --- | --- |
| `ecosystem-upkeep.service` | `1d464c75f84864f5dba18309516935cd59c300ccb614aa8836fb5a6b3e7026f7` |
| `ecosystem-upkeep.timer` | `a3057eaa7d1a05ced32049dcabfe8faf6d89fbafe0b72b1fc35f1d42db559a38` |
| `ecosystem-research-progress.service` | `fc63635301937302eb0ac1d4192a6212d677e5d38f6d4d356bbca85902da9285` |
| `ecosystem-research-progress.timer` | `15439048aa8b150fb313e449c552422f5a07d4f7edc80c4b56c3beab6b729227` |
| `stack-currency.service` | `48dcfd9bf64e5a8e4fea6a28725f34a81f3b53c1c51d0d1f5616df84cfc3e232` |
| `stack-currency.timer` | `ce1800a5a724a196c8327c74e5a2ebd299e93cabfcbd4fb7dc2b67babac053e6` |
| `token-report-refresh.service` | `a70361e0bee385b5f8eb4954b609dedab274eef61bbe228e8fefb3905a2f666e` |
| `token-report-refresh.timer` | `6b14a289fcf638670abad24d2ba698707bb08035b87b64949322e13e22ccca0c` |
| `host-requests-workstation.service` | `20fd2c221667a7604693f71e99552a38d8c20884c87e21ba0614bde340e5c17f` |
| `host-requests-workstation.service.d/notify.conf` | `9239355dc578d86b0b52257a8cb226ddfb9f2caed52f4265f7ef4eae3171e1a3` |
| `host-requests-workstation.timer` | `fa35694fa0f35aa9672de295ca54db3c974e76b1018016b8ff721620500317e9` |
| `native-agent-stack-main-pin.service` | `719bb289c70b7c3a16ac43aeab278257949390e55ca2569fa1626222bce54c43` |
| `native-agent-stack-main-pin.timer` | `be5646372da30867b2534b89e2c29ff917be3bc06eac3a190ec6deb554eed6cd` |
| `ecosystem-live-clone-sync.service` | `9a92c52099510268044277035d468ff62460a00b05c04c9c5146a9a0adf7bc87` |
| `ecosystem-live-clone-sync.timer` | `c4073f53d66397968e36638cba64623533f5f4cffca383b01bf61d6a4d5f49bb` |

## Acceptance limits

The source main-pin skips a checkout move when tracked work exists. A passing
helper exit alone therefore does not prove HEAD advanced: the co-op compares
both intended HEADs to their own origin/main before accepting sync. Live-sync
refuses tracked and untracked work; failed status/fetch/index commands must not
be reported as a successful index update.

The research source hardcodes old Loki 13100; the destination uses 21300.
The notification source is an ntfy text POST; native Alertmanager uses its
JSON alert contract. Co-op A7/A8 route it through the existing native API on
21093 with critical/unit/host labels and a function-specific alertname.
The ntfy option remains available for old deployments. The dashboards owner
provides the reviewed --loki-url emitter interface for explicit 21300 targeting.
Endpoint/transport portability must be explicit so that
WSL's shared network namespace cannot make an old backend look like a new
host's accepted function. Co-op owner evidence and new real run/read-backs,
rather than these source hashes or parser checks, close deployment acceptance.

The [dated not-needed row](../../../docs/decisions/2026-10-06-upkeep-dagu.md)
covers hindsight-ensure; preserving historical memory data stays a separate
retirement task.
