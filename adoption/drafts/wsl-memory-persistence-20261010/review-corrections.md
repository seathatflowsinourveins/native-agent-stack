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
