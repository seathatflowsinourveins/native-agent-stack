# CC review corrections — 2026-10-10

The CC's 03:52Z review requested two P2 corrections and listed eight P3
notes. Local review record: `coordination/command-center/research-cc-role-20261008/pr955-claude-read-35fec025.md`,
SHA-256 `4942847c478b99f63c2239b6d14543ef4a0d99a26f82354219dc96d0a6ee2d59`.
This is review provenance, not an upstream dependency pin. The supported
implementation remains installed WSL 3.0.1, chrony 4.8 and systemd 259.5;
Git 2.53.0 supplies the timer-generator behavior. The [source register](sources.md)
records their release commits, files, line ranges and selected byte hashes.
No replacement runtime or host configuration is introduced.

| Finding | Correction / disposition |
| --- | --- |
| P2-1 PHC0 attributed to distro chrony | Decision, README, source register, audit and plan distinguish WSL VM-init `::1:323` from distro observe-only `127.0.0.1:3323`. Capture requires both explicit endpoint pairs. PHC0 offsets establish host-clock agreement; monitor offsets estimate network-time error. The NY/no-chrony-edit outcome stands. |
| P2-2 timer test accepts a coordinated :35 change | The normal test requires the recorded base's sole OnCalendar to equal original_calendar, SHA-256 of recorded UTF-8 text to equal its recorded sha256, and that hash to equal base_unit_sha256. Mutant fixtures change both plan/drop-in to :35 with base :34, corrupt the plan hash or corrupt the recorded hash; all are rejected. |
| P3-1 Git maintenance rewrites bases | Require a live base-hash/expression match immediately before applying; regenerate Git records/drop-ins after git maintenance start rewrites the random minute. Pinned builtin/gc.c verifies the behavior. |
| P3-2 60- drop-in overrides set-property | Document future policy edits to the 60- file; pinned systemd.unit.xml precedence and unit.c priority-50 writer verify it. |
| P3-3 exact Windows key edit | Require the historical pre-edit hash and complete byte backup; preserve encoding, BOM and CRLF, verify only memory=104GB changes to memory=96GB, and restore the full backup for the inverse. A changed precondition needs a new reviewed edit. |
| P3-4 usable guest memory | Label the CC's 102.16 GiB observation and the 96GB linear estimate separately; account for WSL's totalram-minus-32MiB ancestor cap and earlier guest-wide reclaim. Normal workload acceptance remains unmeasured here. |
| P3-5 time preconditions | Assert original time.json draft_target_precondition values as well as memory.json absence and Windows backup hashes. Original snapshots are historical and stay intact. |
| P3-6 expired WU watch | Remove its drop-in and change-plan entry from the apply set. Retain its original base, audit and DST comparison. Six active timer drop-ins remain. |
| P3-7 optional DefaultDependencies=no | Deferred: the review identifies small, untested value; no demonstrated need justifies changing the accepted service draft. |
| P3-8 stale shard-6 note | Replace with dated CC and GitHub checks. Existing-head green/skipped observations do not establish corrected-head CI or native boot acceptance. |

[regression-checks.json](measurements/regression-checks.json) retains actual
command intervals, exits, published outputs and hashes. Removing only the
endpoint fix in a temporary fixture yields exit 1. Removing only the base
calendar/hash assertions makes all three invalid fixtures escape the normal
check, so the unchanged mutant regression yields exit 1. The candidate's
full eight-test run yields exit 0, including installed systemd-analyze verify
on temporary units. Each red fixture removes one fix without changing its
acceptance test. Earlier actual red-before / accepted-mutation observations
are also recorded, with their uncaptured timings stated explicitly.

[time-post-restart.json](measurements/time-post-restart.json) retains the
read-only 05:24:02Z explicit endpoint/process reads. Both pairs succeed;
PHC0 is selected on the VM endpoint and Cloudflare on the monitor endpoint.
All seven recorded timer-base hashes remain equal; six draft targets are
present and the expired watch's is absent. These are observed file/endpoint
states, not inferred proof of the CC's complete application, memory boot
persistence or 96GB workload performance. Do not overwrite present files.

The graph covering main lacks these unmerged draft files, so code/source
verification used the exact worktree files after checking index coverage;
no graph completeness claim is made. Protected trading work and host apply
remain outside this correction. Full repository validation and the redacted
PR-range gitleaks result are recorded in the final PR/coordination handoff
after the final candidate is checked, avoiding a self-referential receipt.

## CC micro P3 corrections

The CC's 06:15:55Z micro accepts both prior P2 fixes and requests the following
record corrections. Its SHA-256 is
`33083ea3a60179a7cc6826f930c721600ef460871b3dc4046d618946ba667e31`.

| Finding | Correction / evidence |
| --- | --- |
| P3-a live set-property versus file precedence | Restrict 60-over-50 precedence to configuration reload/boot. Pinned systemctl.xml:663–680 explicitly applies live properties immediately. CC records the 05:10:02Z 33G/26G override and 05:13:04Z reset; fresh 06:23:25Z manager/kernel high and max read-backs agree with the drafts. |
| P3-b completed boot and skipped Windows option | Attribute the 05:09:55Z boot to the CC and say it was not run by this lane. Fresh service read-back shows start at 05:09:58Z and Result=success/enabled. Cite the CC application/reset records and retained 104GB choice; 96GB remains unapplied. |
| P3-c missing IPv4 probe receipt | Replace the uncaptured pre-restart sentence with fresh paired commands: 127.0.0.1:323 returns 506/exit 1, while ::1:323 succeeds with PHC0. Both complete receipts are retained. |

The ninth draft test compares manager/kernel limits with the configured
policy and requires both transport outcomes in the follow-up receipt.
Removing the new receipt block in a temporary fixture makes this evidence
check fail. CC application metadata stays separately attributed; none of
these reads or tests runs a host setting or boot command.

The repository-wide jCodeMunch cap is assigned to overlap-token/nevo in a
separate measured PR that lands first. The earlier consolidation proposal
is superseded and stays unapplied. This lane prepares one P3 forward commit
on 056c6984, then waits for the co-op's landing-rebase cue before any push.
