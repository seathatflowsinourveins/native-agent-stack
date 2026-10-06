# NativeStack2604 upkeep timer transfer

Status: host-apply repair after independent review; guard partially applied by the co-op, revised recipe and native-data acceptance pending. The approved full-resolution plan, Phase 1 step 6, assigns disk-headroom-guard and native-data to systemd user timers. The co-op's P1-TIMERS direction and A49 select `adoption/templates/systemd/`. No new install-plan row, owner, API or default enablement is introduced. The separate #723 review is outside this transfer.

This serves reliable foundation upkeep during US-equities research and historical simulation, while keeping native harness observations current. It changes no trading gate, acquisition or broker operation. The co-op is the host writer and supplies the two green runs after repository checks pass; this lane changes source only. Exact apply, read-back and restoration-aware rollback are in [the transfer runbook](../../adoption/templates/systemd/upkeep-transfer.md).

## Source and reuse

CI correction: the hosted validation of 28d82fc4 failed the two positive rollback
tests because their default temporary root did not meet the real rollback's
home-directory contract. The earlier local run's TMPDIR masked that assumption;
its passing fixtures are not CI acceptance. Bind the rollback fixture to a
private home-cache directory through CPython's maintained
[TemporaryDirectory dir argument](https://github.com/python/cpython/blob/v3.13.16/Lib/tempfile.py#L115).
Keep HOME, production root validation and every apply/rollback command unchanged.
A positive control forces the cached default to /tmp without creating a fixture
there; an out-of-home manifest still fails before any manager call and preserves
the candidate bytes. The [CI repair receipt](../../evidence/artifacts/ns2604-p1-upkeep-timers-20261006/ci-repair-20261006.json)
keeps the hosted failure and later local results distinct. Full-suite validation
waits until after the 2026-10-06 paper window ends at 13:45Z; publication requires
that run.

The private approved `PLAN-full-resolution-20261005.md` has SHA256 775119dc6840552def19142a10e2730b489b6365c346e6f9fb6f5db5f2572ba2. Its Phase 1 at 63-106 and timer assignment at 100-104 distinguish these two timers from the other upkeep jobs assigned to Dagu. Command-center item task-ns2604-coop-20261006T031317Z and the co-op's A49 govern the bounded transfer.

Reuse the existing observer and [native-data unit examples](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ecfa112764c664d35377dd66b8cfcb67e5a94d60/observability/native-data/README.md#L158), including their two-minute cadence. The observer projects supported native metadata, runs no model, and preserves unknown observations. It remains the maintained integration at `observability/native-data/snapshot.py`; no replacement collector or scheduler is built.

The old observer accepted only Loki 13100. The destination's [Loki plan row](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ecfa112764c664d35377dd66b8cfcb67e5a94d60/evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json) uses 21300. Accept exactly those two recorded literal IPv4-loopback push URLs, selected explicitly in the private configuration. Preserve the old default and reject other authorities, ports, paths, schemes, userinfo, queries, fragments and malformed types. Proxy and redirect controls remain. Local fixtures verify that publication uses 21300 and that an unsuccessful HTTP response fails the actual observer entry point.

Read-only destination metadata identifies `ns2604-loki.service` as loaded/running and `ecosystem-loki.service` as not-found. The new native-data unit orders after the destination name. It does not start Loki itself; the co-op must verify the approved listener before enabling publication. This metadata read is local integration, not a new service or provider acceptance.

The [ENOSPC decision:218-226](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ecfa112764c664d35377dd66b8cfcb67e5a94d60/docs/decisions/2026-10-05-disk-headroom-enospc.md#L218) reports two-minute sampling, alerts below 60 GiB and supported uv cache pruning below 30 GiB. Read-only interop after the cold hold, at 2026-10-06 04:26-04:28Z, established the actual source. No source service was started, no environment file or credential store was read, and no host configuration changed.

| NativeStack source | SHA256 | Transferred contract |
| --- | --- | --- |
| `disk-headroom-guard.service` | `da706cb9947ff96a2b503ca3074923bfc471f6c5b8b50f82ba7e669d06b6bd7e` | oneshot, Nice 19, state-root executable |
| `disk-headroom-guard.timer` | `3d975232392dd4b76f35cd8a941214cd1a8829816605aa02e33426d81928990c` | boot 2 min, interval 2 min, accuracy 15 s |
| `ecosystem-native-data.service` | `7fdc4366c94fd813f027498f0127698022a8fa4bafa4a8bc3038782efd7bcce6` | maintained observer, 90 s timeout, private umask, no new privileges |
| `ecosystem-native-data.timer` | `ec306282555c8c3dbc7669027022aea925aa0dc99c8c6a7118d1b6567ff6fb57` | boot 45 s, interval 2 min, accuracy 10 s |
| `ops/disk-headroom-guard.sh` | `b2e0515c01ec385118f0d3c8a40b4102932ed05784085d13bc488074bceba58c` | root sampling, local CSV/alert logs, only `uv cache prune` mitigation |

The guard writes local alerts and sends no network notification. The transfer omits process arguments, which can contain credentials, retaining PID, elapsed time and command name. Failed or malformed samples fail before pruning. Logging failures return nonzero while allowing low-space mitigation. Symlinked state and non-regular log paths, including FIFOs, are preserved and rejected before opening. Synthetic controls prove these paths without real pruning.

Thresholds retain GNU `df --output=avail -B1G /` display semantics: fractional block counts round up, so the sample is not an exact byte threshold ([coreutils/coreutils@8e075ff8ee11692c5504d8e82a48ed47a7f07ba9, doc/coreutils.texi:903](https://github.com/coreutils/coreutils/blob/8e075ff8ee11692c5504d8e82a48ed47a7f07ba9/doc/coreutils.texi#L903)). Pruning uses only the supported command for unused, regenerable cache entries ([astral-sh/uv@70fe1196a546e49148a73b1c592b2f74c33af80e, docs/concepts/cache.md:142-145](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/docs/concepts/cache.md#L142)). It changes no dataset or installation root. The guard keeps its source's unlimited oneshot startup timeout; a long prune delays subsequent triggers rather than overlapping another run.

Supersession ledger 5470cd659bd44c9d285c9b0fd36313d05c542ea3d37914924cb738c05d8efc16 at `/rows/28,30,59,61` identifies `disk-headroom-guard.service/.timer` and `ecosystem-native-data.service/.timer` as transfer gaps. Its source inventory evidence is historical. Repository templates and checks do not close the host gaps.

## Native systemd contracts

Installed systemd is 259.5-0ubuntu3.4; its official source is [systemd/systemd@b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a](https://github.com/systemd/systemd/tree/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a). The latest official release is [v262, published 2026-09-22](https://github.com/systemd/systemd/releases/tag/v262). This transfer adds supported unit formats to the installed runtime; it upgrades no runtime or OS.

- [Timer semantics:50-53](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L50): an active service is not restarted by another timer trigger. Repetitive jobs must not retain active state with RemainAfterExit=yes.
- [Persistent:386-392](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L386) affects calendar timers. Do not claim catch-up behavior for the preserved monotonic interval.
- [Oneshot state:209-219](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.service.xml#L209): success normally ends inactive/dead. A green run requires a successful synchronous start, Result=success, ExecMainStatus=0 and journal/artifact freshness; live timestamps can disappear after unload, as corrected below. Service is-active is not the acceptance oracle.
- [Verifier status:1369-1378](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd-analyze.xml#L1369): default verify can return 0 despite warnings. Use `systemd-analyze --user --man=no --generators=no --recursive-errors=no verify` for all rendered unit files. The unknown-directive control must fail.
- The reviewed native-data service already provides a bounded 90 s oneshot, UMask=0077, NoNewPrivileges and qualifying Node PATH. Nice 19 follows the task's scheduling boundary and [systemd.exec:1315-1322](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.exec.xml#L1315). Quoted template parameters preserve whitespace in the selected absolute paths.

## Acceptance and limits

Current local results: the destination URL initially failed validation, then all 44 observer tests passed. Four unit-contract/native-parser tests pass, including default verification exit 0 and strict verification exit 1 for the same unknown directive. The first parser invocation lacked XDG_RUNTIME_DIR and failed before parsing; a private fixture runtime corrected that input without broad environment inheritance or service activation. Six guard tests pass, covering thresholds, malformed samples, prune failure, logging failure, symlinked state and preserved FIFO logs. Commands are stubbed; no real cache is pruned.

These results are local integration and synthetic fixtures, not unchanged upstream suites, host activation or provider qualification. The first source-read attempt used an unavailable RTK path and returned 127; the corrected read returned 0. Both are retained privately. Host install, daemon-reload, enablement, fresh green runs and read-back remain co-op actions. The public receipt records source hashes, test outputs and this boundary.

The completeness critic found a FIFO blocking case; the regular-file gate and bounded preservation controls resolve it. No material code blocker remains. Alternatives were a replacement observer, scheduler loop, or new default plan owner. Maintained reuse and the approved timer/library placement settle these choices. Reconsider if upstream changes the supported output/timer contract, an approved listener changes, or repeated native runs show the cadence cannot meet its upkeep function. Retain source inputs, actual outputs, failures and restoration state for that comparison.

## Independent host review and repair, 2026-10-06

The Opus host-apply review at 2c43a27f returned apply_with_changes. The co-op
applied the guard half at 05:45Z: genuine free space was 634GiB, so no prune ran.
The old automated green gate exited 1 because its live start/invocation fields
were empty. Do not turn that failure into a pass. The co-op judged the single
05:45:36Z execution by its journal start/finish, Result=success, ExecMainStatus=0
and the fresh CSV row. Native-data was not applied. The revised unit's new cache
binding and the revised recipe still need the co-op's reviewed apply.

Correction: the original decision required a fresh live ExecMainStartTimestamp.
Systemd can unload an inactive unit and discard those execution properties;
inactivity alone is not the cause. The durable evidence is the journal
([systemd@b3d8fc43, man/systemd.unit.xml:558-586](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.unit.xml#L558)).
The revised gate requires one successful native start job after a captured
cursor, with exact USER_UNIT and USER_INVOCATION_ID, Result/ExecMainStatus and
changed, fresh artifact content. The observer summary is restricted to that
invocation and joined by snapshot hash
([job.c:812-821](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/core/job.c#L812),
[unit.c:6834-6839](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/core/unit.c#L6834),
[journalctl.xml:355-374](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/journalctl.xml#L355)).
No automatic start retry or mutable plan file substitutes for completion.

The destination gates use the canonical host template at ecfa11276:8-9:
ai-memory 29374 and optional Qdrant 21633, alongside Loki 21300 from that pin's
loki.yaml:3-8. The new destination example declares these bindings without
changing the original observer schema/default. The render gate rejects copied
old endpoints, unresolved paths, missing token/native/project/data prerequisites,
Node<22, a dirty/wrong checkout and unsafe batch/XDG roots. Native git creates a
separate detached live checkout at the exact approved commit; main's checkout
remains untouched. Configuration/state directories are created privately only
when absent. Node's bound follows [QMD@v2.8.3 package.json:99-100](https://github.com/tobi/qmd/blob/v2.8.3/package.json#L99).

The independent publication observation queries Loki 21300's native query_range
API over a frozen service-run window and requires the complete published
snapshot marker, not just any HTTP 204. It joins observed_unix to the invocation
summary and hash-bound local snapshot while retaining unknown/stale counts.
The marker contains no snapshot hash: that hash is computed after publication.
Source: [grafana/loki@09e6ce2 (v3.7.8), HTTP API:462-540](https://github.com/grafana/loki/blob/09e6ce2ff1bdc19763a10265b870c86f51c98655/docs/sources/reference/loki-http-api.md#L462)
and maintained snapshot.py:489-525. Local mocked HTTP/journal controls prove the
oracle's failures; they are not a native query or provider acceptance.

The manifest records baseline bytes/mode or symlink target, expected installed
identity, each prepared mutation phase, exact persistent/runtime enablement
links and prior timer activation. Apply and rollback record removal/copy intent
before mutation, so interruption can resume while later operator edits remain
untouched. The fresh-shell rollback validates the owned private manifest before
any manager/deletion call, scopes scheduling to recorded intents, restores only
captured mutations, runs reset-failed where required, and retains source,
observation data and receipts. Native cp-a preserves prior bytes/mode/links;
blanket disable is excluded because it can remove manual links
([systemctl.xml:936-945](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemctl.xml#L936)).

Check other loaded units' NeedDaemonReload immediately before each explicit
reload and native enable's implicit reload. This is a quiescent-owner gate, not
an atomic guarantee about concurrent writers or unloaded files. A proposed
enable --no-reload was rejected before publication: it leaves the global
unit-file-state cache dirty and makes unrelated units report pending reload
([manager.h:278-281](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/core/manager.h#L278),
[unit.c:3852-3853](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/core/unit.c#L3852)).
Use the supported native enable --now after its immediate gate. Read-back checks
each timer's fresh filesystem enablement, active state, effective target/cadence,
empty drop-ins, loaded fragment and exact installed identities. Grouped
is-active/is-enabled only promises that any named unit qualifies
([systemctl.xml:214-216,1037-1044](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemctl.xml#L214)).

Guard deviations are explicit: UMask 0077, NoNewPrivileges=true, the reviewed
mise/local/system PATH, and UV_CACHE_DIR=%h/.cache/uv. The cache variable is the
supported upstream selector; no dataset/root is pruned
([uv@70fe1196, crates/uv-static/src/env_vars.rs:66-69](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/crates/uv-static/src/env_vars.rs#L66)).
TimeoutStartSec=90s is supported and matches the observer, but is an unmeasured
guard policy alternative: genuine prune duration has not been qualified. Retain
the source's unlimited bound, disclose it, and measure an isolated native prune
before choosing a different bound. No forced disk-pressure experiment is allowed.

The dated operator gates retain the reviewer's 20-minute lead-in before the
corrected paper windows. Recheck before each sequential service start; pause
between steps and never kill a running case. No daemon-reexec or OS restart is
part of this transfer.

The first two executable controls reproduced the exact review defects: old 13100
config rendered successfully and fresh-shell rollback falsely exited 0. Their
failed streams remain. Controls now also cover wrong read endpoints, Node/pin/
prerequisite failures, preserved operator bytes/dangling links/aliases, partial
apply and rollback, early manifests, GC-empty live fields, failed/stale native
jobs, wrong Loki generation, both-timer states/cadence and window/reload gates.
These are synthetic/local integration; all host acceptance remains separate.

## Cache-lock correction from the command-center verdict

The later exact-head verdict is ACK_AFTER with one required P2. The source's
unlimited systemd startup bound did not mean an unlimited uv lock wait:
[uv@70fe1196 cache.md:160-164](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/docs/concepts/cache.md#L160)
and [cache_prune.rs:31-43](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/crates/uv/src/commands/cache_prune.rs#L31)
show safe pruning waits for an exclusive cache lock while other uv processes hold
shared locks. The default UV_LOCK_TIMEOUT is 300 seconds
([locked_file.rs:17-28](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/crates/uv-fs/src/locked_file.rs#L17),
[env_vars.rs:1539-1543](https://github.com/astral-sh/uv/blob/70fe1196a546e49148a73b1c592b2f74c33af80e/crates/uv-static/src/env_vars.rs#L1539)).
The reader observed 18 shared cache locks. A genuinely low-space run could
therefore wait five minutes, fail, and delay sampling beyond the two-minute
interval. The old source has the same limitation; the high-space green run did
not exercise pruning.

Adopt UV_LOCK_TIMEOUT=10 as an explicit guard policy: the supported integer
seconds selector bounds the lock-wait branch well below the 120-second timer
interval. It does not bound successful pruning, process startup or all I/O.
Retain the service's source-unlimited startup bound pending real duration
qualification. A lock timeout remains a nonzero service result; the script
records a distinct cache-in-use/deferred alert without logging raw uv output.
Never --force: upstream permits ignoring the lock only when no other uv reader
or writer is running, which does not describe this host. Reconsider the
10-second lock budget only with an isolated native duration/availability control;
do not force disk pressure or prune the shared cache for qualification.

The source guard now distinguishes no matching processes from an actual ps
failure, retains privacy-safe PID/elapsed/comm metadata, and uses the same native
prune command. Both guard.service and the guard script change from the applied
2c43a27f bytes; the co-op must re-stage them from the reported new head.
Comment/spacing changes to the timer do not alter its cadence.

All captured/comparison commands use native subprocess interfaces or rtk proxy.
The new receipt records PATH Python 3.13.16 versus service /usr/bin/python3
3.14.4 and distinguishes synthetic command/HTTP/journal controls from local
integration/native-parser checks. The old receipt is historical; its mixed
class is clarified in the new repair receipt rather than described as an
unchanged upstream suite. The guard automated green failure and manual owner
judgment remain separate.
