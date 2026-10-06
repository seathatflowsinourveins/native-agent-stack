# NativeStack2604 upkeep timer transfer

Status: repository preparation complete; host acceptance pending. The approved full-resolution plan, Phase 1 step 6, assigns disk-headroom-guard and native-data to systemd user timers. The co-op's P1-TIMERS direction and A49 select `adoption/templates/systemd/`. No new install-plan row, owner, API or default enablement is introduced. The separate #723 review is outside this transfer.

This serves reliable foundation upkeep during US-equities research and historical simulation, while keeping native harness observations current. It changes no trading gate, acquisition or broker operation. The co-op is the host writer and supplies the two green runs after repository checks pass; this lane changes source only. Exact apply, read-back and restoration-aware rollback are in [the transfer runbook](../../adoption/templates/systemd/upkeep-transfer.md).

## Source and reuse

The private approved `PLAN-full-resolution-20261005.md` has SHA256775119dc6840552def19142a10e2730b489b6365c346e6f9fb6f5db5f2572ba2. Its Phase1 at63-106 and timer assignment at100-104 distinguish these two timers from the other upkeep jobs assigned to Dagu. Command-center item task-ns2604-coop-20261006T031317Z and the co-op's A49 govern the bounded transfer.

Reuse the existing observer and [native-data unit examples](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ecfa112764c664d35377dd66b8cfcb67e5a94d60/observability/native-data/README.md#L158), including their two-minute cadence. The observer projects supported native metadata, runs no model, and preserves unknown observations. It remains the maintained integration at `observability/native-data/snapshot.py`; no replacement collector or scheduler is built.

The old observer accepted only Loki13100. The destination's [Loki plan row](https://github.com/seathatflowsinourveins/native-agent-stack/blob/ecfa112764c664d35377dd66b8cfcb67e5a94d60/evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json) uses21300. Accept exactly those two recorded literal IPv4-loopback push URLs, selected explicitly in the private configuration. Preserve the old default and reject other authorities, ports, paths, schemes, userinfo, queries, fragments and malformed types. Proxy and redirect controls remain. Local fixtures verify that publication uses21300 and that an unsuccessful HTTP response fails the actual observer entry point.

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

Supersession ledger5470cd659bd44c9d285c9b0fd36313d05c542ea3d37914924cb738c05d8efc16 at `/rows/28,30,59,61` identifies `disk-headroom-guard.service/.timer` and `ecosystem-native-data.service/.timer` as transfer gaps. Its source inventory evidence is historical. Repository templates and checks do not close the host gaps.

## Native systemd contracts

Installed systemd is259.5-0ubuntu3.4; its official source is [systemd/systemd@b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a](https://github.com/systemd/systemd/tree/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a). The latest official release is [v262, published2026-09-22](https://github.com/systemd/systemd/releases/tag/v262). This transfer adds supported unit formats to the installed runtime; it upgrades no runtime or OS.

- [Timer semantics:50-53](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L50): an active service is not restarted by another timer trigger. Repetitive jobs must not retain active state with RemainAfterExit=yes.
- [Persistent:386-392](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L386) affects calendar timers. Do not claim catch-up behavior for the preserved monotonic interval.
- [Oneshot state:209-219](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.service.xml#L209): success normally ends inactive/dead. A green run requires a successful synchronous start, Result=success, ExecMainStatus=0 and a fresh execution timestamp. Service is-active is not the acceptance oracle.
- [Verifier status:1369-1378](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd-analyze.xml#L1369): default verify can return0 despite warnings. Use `systemd-analyze --user --man=no --generators=no --recursive-errors=no verify` for all rendered unit files. The unknown-directive control must fail.
- The reviewed native-data service already provides a bounded90s oneshot, UMask0077, NoNewPrivileges and qualifying Node PATH. Nice19 follows the task's scheduling boundary and [systemd.exec:1315-1322](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.exec.xml#L1315). Quoted template parameters preserve whitespace in the selected absolute paths.

## Acceptance and limits

Current local results: the destination URL initially failed validation, then all 44 observer tests passed. Four unit-contract/native-parser tests pass, including default verification exit 0 and strict verification exit 1 for the same unknown directive. The first parser invocation lacked XDG_RUNTIME_DIR and failed before parsing; a private fixture runtime corrected that input without broad environment inheritance or service activation. Six guard tests pass, covering thresholds, malformed samples, prune failure, logging failure, symlinked state and preserved FIFO logs. Commands are stubbed; no real cache is pruned.

These results are local integration and synthetic fixtures, not unchanged upstream suites, host activation or provider qualification. The first source-read attempt used an unavailable RTK path and returned 127; the corrected read returned 0. Both are retained privately. Host install, daemon-reload, enablement, fresh green runs and read-back remain co-op actions. The public receipt records source hashes, test outputs and this boundary.

The completeness critic found a FIFO blocking case; the regular-file gate and bounded preservation controls resolve it. No material code blocker remains. Alternatives were a replacement observer, scheduler loop, or new default plan owner. Maintained reuse and the approved timer/library placement settle these choices. Reconsider if upstream changes the supported output/timer contract, an approved listener changes, or repeated native runs show the cadence cannot meet its upkeep function. Retain source inputs, actual outputs, failures and restoration state for that comparison.
