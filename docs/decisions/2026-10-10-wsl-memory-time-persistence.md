# WSL memory and time persistence — 2026-10-10

Status: the CC applied the Linux memory and six timer-zone drafts at the
05:09:55Z boot; this lane has not run a host application or boot test.
The CC retained 104GB and skipped the optional 96GB key edit. Repository
corrections await review and landing after the separate indexing-cap PR.
Drafts are in
[adoption/drafts/wsl-memory-persistence-20261010](../../adoption/drafts/wsl-memory-persistence-20261010/README.md).
The per-claim pinned [source register](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md)
is part of this decision. Numeric policy values come from the CC; upstream
sources establish their meaning and supported implementation.

## Measured memory state and options

The read-only Linux commands at **2026-10-10T02:31:25Z** show systemd
259.5-0ubuntu3.4, kernel 6.18.40.1, WSL 3.0.1.0,
`user-1000.slice MemoryMax=68719476736` (64 GiB) and
`MemoryHigh=infinity`, `non-systemd/memory.max=42949672960` (40 GiB),
and `vm.swappiness=10`. The slice's limit drop-ins are in `/run`;
no active swappiness assignment was found in the sampled `/etc/sysctl.d/*.conf`
or `/etc/sysctl.conf`. The proposed persistent target files/enablement link
are absent. [Raw memory receipt](../../adoption/drafts/wsl-memory-persistence-20261010/measurements/memory.json).

The Windows read-only interval is **02:31:25Z–02:31:28Z**. These are sequential
point counters, not an atomic snapshot, workload peak or percentile.

| Counter / method | Raw value | GiB (2^30 bytes) |
| --- | ---: | ---: |
| Win32_ComputerSystem.TotalPhysicalMemory | 137270288384 B | 127.843 |
| PerfOS Memory.AvailableBytes | 15419977728 B | 14.361 |
| Chrome private resident working set, PerfProc WorkingSetPrivate sum, 223 instances | 20978061312 B | 19.537 |
| Chrome WorkingSet64 sum, 222 processes | 27267678208 B | 25.395 |
| Chrome PrivateMemorySize64 sum (committed, not resident) | 44545335296 B | 41.486 |
| VmmemWSL WorkingSet64, one process | 61561454592 B | 57.334 |
| Windows committed / commit limit | 219609870336 / 228518133760 B | 204.528 / 212.824 |

The Chrome working-set sum may double-count shared pages. Its private
working-set counter is the appropriate unshared resident observation here;
private commit cannot be added to physical demand. The CC previously
reported Chrome “about 22 GB” and Windows “0.0 GiB” at 23:42–23:43Z; the
methods for those historical counters were not supplied, so they are not
treated as equivalent to this capture's AvailableBytes/private working set.
Counter meanings and installed WSL memory semantics are cited in
[the source register](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md#windows-configuration).

The masked `C:\Users\<PROFILE>\.wslconfig` SHA-256 is
`2de9d6a9196acc54ddda90590e55228f9aa4dba2afdfd48a308ca47dfcb87a67`.
Its active keys include `memory=104GB`, `swap=32GB`,
`swapFile=Z:\\wsl-swap\\swap.vhdx` and
`autoMemoryReclaim=dropCache`. The installed source parses GB as GiB;
its memory cap uses deferred commitment/overcommit. This is a maximum,
not a reservation. dropCache is idle-gated cache/slab reclaim, not an
application-memory ceiling; keeping it does not guarantee host headroom.
The Z: swap location remains as measured
([WSL 3.0.1 source](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md#windows-configuration)).

| Option | Nominal physical remainder at VM cap | Minus this Chrome private resident snapshot | Guest trade-off |
| --- | ---: | ---: | --- |
| Keep 104GB plus 64/40 GiB subgroup ceilings | 23.843 GiB | 4.306 GiB | Most guest capacity; subgroup maxima sum to 104 GiB and leave no additive budget at both maxima for other distro/system/kernel charges. |
| Lower only memory to 96GB; retain 64/40 ceilings | 31.843 GiB | 12.306 GiB | Adds 8 GiB nominal host margin; subgroup maxima exceed the VM cap by 8 GiB and guest pressure can occur before both are reached. |

The arithmetic is `TotalPhysicalMemory / 2^30 - configured GiB`, then
subtracts **only** the measured Chrome private working set. It is not a
measurement of all Windows demand or guaranteed available RAM. Cgroup
ceilings are limits, not reservations; they cover different branches of the
measured distro, not every charge in the shared WSL VM. Other distributions,
Windows workload peaks, restart cost, swap I/O and performance at either
future cap are unmeasured. VmmemWSL and the distro cgroup counters have
different scopes/accounting and were not equated.

The CC's dated 03:52Z review reports **102.16 GiB guest MemTotal at 104GB**.
That is a CC-reported observation, not the configured maximum or an atomic
counter in the Windows receipt. WSL 3.0.1 caps `wsl-user` at `sysinfo` total
RAM minus **32 MiB** ([main.cpp:105 and :3908–3909](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md#memory-and-boot)).
Thus the 64+40 GiB sibling ceilings already exceed that reported MemTotal
by about **1.8 GiB**. If the same difference between configured cap and
MemTotal persists at 96GB, usable RAM would be about **94.16 GiB**, and
the sibling sum would exceed it by about **9.8 GiB**. This is a linear
estimate; a post-restart MemTotal/ancestor-limit read is required to measure
it. Lowering to 96GB can force guest-wide reclaim before either sibling
ceiling is reached, even when each is below its own limit. The CC and user
own that policy trade-off; no workload success is inferred from the draft.

**Pre-restart recommendation: the 96GB key-only option.** The
current private Chrome demand leaves only about 4.3 GiB nominal room for
other Windows consumers at a fully used 104 GiB cap, compared with about
12.3 GiB at 96. The price is 8 GiB less guest capacity, with possible guest
reclaim/OOM under concurrent pressure. Preserve dropCache and the Z: swap
settings; no claim is made that lowering the cap is measured to improve
throughput. Reverse this choice if measured normal guest demand/pressure
shows unacceptable failure at 96 while a representative Windows workload
has enough headroom at 104. Capture those measurements at the CC's
application turn; do not gate or throttle work waiting for them.

The CC's application retained memory=104GB and did not apply the 96GB option
after the host/guest-capacity trade-off decision. The arithmetic above records
the dated alternatives; it is not an instruction to change the current host.
[CC application record](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md#cc-application-records).

Persist the requested Linux values through a systemd slice drop-in, native
boot oneshot and sysctl.d file. The WSL-created leaf needs per-distro
reapplication. The asynchronous boot.command route was considered and
rejected because its code does not order memory-controller activation;
the native oneshot explicitly requests MemoryAccounting and verifies the
write. [Pinned boot/controller sources](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md#memory-and-boot).
The CC's application and corrective-reset receipts record a native boot at
05:09:55Z and a reset at 05:13:04Z. This lane did not run that boot. Fresh
06:23:25Z reads show the oneshot enabled with Result=success (start 05:09:58Z),
slice MemoryMax=68719476736 and MemoryHigh=infinity, kernel slice high=max,
non-systemd max=42949672960 and high=max, and swappiness=10. These are current
read-backs plus a separately attributed CC boot record; a second-distro-start
persistence run and 96GB workload performance remain unmeasured here.
[CC records](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md#cc-application-records);
[follow-up receipt](../../adoption/drafts/wsl-memory-persistence-20261010/measurements/time-post-restart.json).

## Clock synchronization and timezone decision

At **02:35:15Z**, the original default chronyc query selected `#* PHC0`
with reach 377, poll 3 and normal leap status; tracking reported
**5.116 µs fast**, last offset **+7.179 µs**, RMS **35.039 µs**, stratum 1.
The CC's review corrected the attribution: this reference belongs to
**WSL's VM-init chronyd**, whose PHC offsets measure agreement with the
Hyper-V host clock. They do not measure accuracy against UTC. The separate
`chronyd --version` command reports the distro binary's **4.8** version;
it does not establish the VM-init daemon's version.
`timedatectl show` reports `Timezone=America/New_York`,
`LocalRTC=no`, `NTP=yes`, `NTPSynchronized=yes`.
`/etc/wsl.conf` was independently read at **02:39:02Z**:
`[boot] systemd=true`, `[time] useWindowsTimezone=true`.
[Raw time receipt](../../adoption/drafts/wsl-memory-persistence-20261010/measurements/time.json);
[selected config and calendar capture](../../adoption/drafts/wsl-memory-persistence-20261010/measurements/calendar.json).

The corrected read-only capture at **05:24:02Z** explicitly queries both
endpoints. `chronyc -h ::1 -p 323 tracking` and `sources` select VM-init
PHC0, stratum 1, with system time **0.006 µs fast relative to the host
reference** in that sample. `chronyc -h 127.0.0.1 -p 3323 tracking` and
`sources` select the distro monitor's `time.cloudflare.com`, stratum 4,
with system time **7.606074 ms slow relative to its network-time estimate**.
Both endpoint pairs exit 0. The process read retains `chronyd -n -F 1 -x`;
chrony 4.8's `-x` disables clock adjustment while tracking network-time
error. The CC reports NTS configuration; source selection alone does not
prove negotiated NTS transport. These sequential samples are separate
reference/error estimates, not a guarantee of UTC accuracy.
[Post-restart receipt](../../adoption/drafts/wsl-memory-persistence-20261010/measurements/time-post-restart.json).

**Retain WSL's VM-init PHC synchronization and the distro observe-only
monitor; change nothing in chrony.** The pinned installed WSL source starts
the VM agent at main.cpp:3219–3222 and generates `refclock PHC /dev/ptp0
poll 3 dpoll -2 offset 0`, `makestep 1.0 3` and `rtcsync` at :3698–3710.
There is no reason to seek that VM refclock in distro config or to confirm
a distro PHC refclock. PHC0 alone is a reference label; the source supplies
the implementation, while the explicit endpoint captures supply selection.
Microsoft's Hyper-V/Azure stable-link example remains supporting context,
not a configuration to transplant. Explicit hosts/ports bypass chronyc's
default Unix-socket/network fallback. The retained 06:23:25Z IPv4 :323 tracking
probe returns 506/exit 1 while the explicit IPv6 ::1:323 probe succeeds with
PHC0. These paired receipts show that a failed transport query does not
establish an absent VM daemon. Timezone changes are independent of synchronization.
[Microsoft, chrony and WSL primary references](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md#time-and-calendar).

| Zone option | Measured dependencies and DST effect | Trade-off / inverse |
| --- | --- | --- |
| **Selected: retain NY guest; make the six active machine calendars explicit** | Use UTC for pages refresh; NY for Git maintenance and local backup/prune. Keep the expired WU watch out of the apply set; its UTC comparison remains audit evidence. Existing explicit UTC/NY paper schedules and the explicit-zone clock hook retain their meaning. | Avoids changing implicit local records/guards found by the audit. Inverse removes only six new drop-ins; no guest zone/chrony/shell/hook edit. |
| Move guest to Etc/UTC | Requires `useWindowsTimezone=false` and CC's `timedatectl set-timezone Etc/UTC`. Without explicit NY suffixes, local 03:30 backup, 04:00 Sunday prune and midnight Git daily/weekly shift to UTC wall time. The template weekday/hour guard and local report stamps also change. | UTC is a supported server convention, but not enough evidence to override these existing local intents. Exact inverse restores the CC's original /etc/wsl.conf bytes (hash in calendar receipt), original America/New_York zone with timedatectl, and any separately backed-up display edits. No display edits are drafted because shell startup files are outside scope and the clock hook already names NY explicitly. |

The fresh user-bus timer snapshot contains **24 loaded timers**, compared
with the CC's earlier reported 27. Seven user timer files lack a zone: the
four cited, plus Git daily/weekly and restic prune. The expired WU watch
file is present but absent from the loaded timer list. The earlier bus call
without XDG_RUNTIME_DIR failed; the explicit user runtime-dir retry
succeeded. Unit files outside the named user-unit root are unexamined, so
24 loaded units is not a claim that all vendor calendars were audited.
[Each audited file:line and classification](../../adoption/drafts/wsl-memory-persistence-20261010/local-time-audit.md).

The next NY DST transition is **2026-11-01 06:00 UTC** (02:00 EDT becomes
01:00 EST), from pinned IANA rules. Native installed-systemd enumeration
around that fold, with base **05:29 UTC**, produced the following nominal
elapses. These are parser results, not observed future firings; timer
accuracy/persistence/activation remain separate.
[NY arm](../../adoption/drafts/wsl-memory-persistence-20261010/measurements/calendar.json),
[UTC arm](../../adoption/drafts/wsl-memory-persistence-20261010/measurements/calendar-utc.json),
[systemd/IANA sources](../../adoption/drafts/wsl-memory-persistence-20261010/sources.md#time-and-calendar).

| Calendar / proposed zone | Measured November fold sequence (UTC) | Result |
| --- | --- | --- |
| Pages `*:00/10:00 UTC` | NY arm: 05:30, 05:40, 05:50, **07:00**; UTC arm: 05:30, 05:40, 05:50, **06:00**, 06:10 | Explicit UTC removes the measured 70-minute NY fold gap for the described ten-minute cadence. |
| WU watch `*:05,35:00 UTC` (audit only) | NY arm: 05:35, **07:05**; UTC arm: 05:35, **06:05**, 06:35 | Explicit UTC would remove the 90-minute fold gap if this expired timer is separately reviewed for reuse. Its drop-in is excluded from this apply set. |
| Backup `03:30 America/New_York` | Nov 1 08:30; subsequent days 08:30 | Retains 03:30 local; UTC moves from 07:30 EDT to 08:30 EST. Using 03:30 UTC instead would move it to the preceding local date at 23:30 EDT / 22:30 EST. |
| Git hourly `1..23:34 America/New_York` | 05:34, **07:34**, 08:34 | Preserves the observed NY policy, including its fold gap and exclusion of local 00:34. Pairing hourly/daily/weekly in the same zone avoids reanchoring only one Git-generated cadence. |
| Git daily / weekly, NY | Tue Nov 3 05:34 / Mon Nov 2 05:34 after the base | Retains the local weekday and 00:34. |
| Sunday prune `04:00 America/New_York` | Nov 1 09:00 | Retains the explicitly described local 04:00. |

The clock hook uses `date -u` for UTC and `TZ=America/New_York date`
for display; both remain explicit through DST under either guest option.
The owner's shell-wide TZ is unmeasured. The audit also finds a local
weekday/hour ExecCondition in the repository's token-report template,
local/naive report filenames, and aware-offset local observations; it
distinguishes these from epoch-only calls and fixtures and makes no edits
to peer-owned code. A full UTC guest move can be reconsidered after those
owners adopt explicit zones and a representative DST/record acceptance
agrees with their intended semantics.

## Application, inverse and evidence limits

[change-plan.json](../../adoption/drafts/wsl-memory-persistence-20261010/change-plan.json)
and the bundle README enumerate exact destinations, absent-file
preconditions and inverses. Restore original Windows bytes rather than
replace the whole file with a two-line fragment. The same rule applies if
the unselected UTC guest alternative is later adopted. No live setting or
timer is changed by this proposal.

Before applying each of the six timer drop-ins, recheck that the live base
SHA-256 and sole `OnCalendar=` equal the plan's recorded hash/expression.
Git 2.53.0 regenerates daily/hourly/weekly timers with a random minute on
`git maintenance start`; re-record bases and regenerate their drop-ins after
any such change. The post-restart read observes all seven historical base
hashes unchanged, six draft targets present and the WU-watch target absent.
It does not authorize overwriting present files. Future slice policy changes
edit the `60-` drop-in because its settings win over `50-` files at reload or
boot. A later set-property call on an active unit still changes its live
limits immediately. The CC's 05:10:02Z boot-unit write of MemoryHigh=33G
and 05:13:04Z corrective reset are a recorded example; read both MemoryHigh
and the two kernel memory.high files after any such change.
The README also specifies the Windows pre-edit hash/byte backup and
encoding/BOM/CRLF-preserving memory-line-only diff procedure.

The nine parsing/fixture/native-parser checks are local integration; the
current-state and calendar captures are native read-only observations.
The new tests distinguish both chrony endpoints and reject a coordinated
`:35` plan/drop-in mutation against a recorded `:34` base, plus corrupt
base hashes. Persistent memory boot success and 96 GiB workload behavior
are not established by this lane's endpoint/base reads.
[validation.json](../../adoption/drafts/wsl-memory-persistence-20261010/validation.json)
records actual commands and exit codes. The earlier shard-6-red statement
was stale: the CC's 03:52Z read reported 35 checks green/skipped, and the
lane's 05:19Z read of the existing draft head found 28 successful and 8
skipped checks, with no failures. These are dated CI observations, not local
full-suite results or acceptance of the corrected head.
