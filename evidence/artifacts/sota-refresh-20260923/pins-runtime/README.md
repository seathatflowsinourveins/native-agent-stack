# SOTA refresh 2026-09-23 -- unit pins-runtime

Scope: qualify the newest releases of dagu, clickhouse and skfolio against retained
acceptance checks. Worktree `/home/example/code/nas-wt-w2-pins-runtime`, branch
`claude/w2-pins-runtime-20260923`, base `origin/main` `7407bf3`. All installs went
into unit-owned prefixes under `/home/example/.cache/sota-refresh-20260923/pins-runtime/`;
no PATH binary, `~/.config`, `~/.local/share/ai-memory`, `~/.headroom`, live Qdrant,
running service, systemd unit or shell profile was touched. No broker contact, paid
API or credential read was needed or attempted.

## dagu 2.16.6 -> v2.17.0 -- qualified (native_proven)

[`dagu.json`](dagu.json). Release resolved via `gh api repos/dagucloud/dagu/releases/latest`
(v2.17.0, published 2026-09-21T13:31:48Z). The pre-existing
`/home/example/.local/share/codex-ecosystem/tools/dagu-2.17.0/dagu` binary's sha256
was verified byte-identical to a freshly downloaded and checksum-verified release
tarball's extracted binary.

Two checks:
1. The retained graceful stop/`--step retry` job-recovery acceptance
   (`blueprints/convergence-practice/job-recovery/run.py`, passed on 2.16.6 in
   `evidence/receipts/native-dagu-job-recovery-20260920.json`) rerun on 2.17.0 in a
   patched scratch copy: **PASSED**, same shape (aborted -> targeted retry ->
   succeeded, checkpoint reused, 12/12 tests, same run-id).
2. Open PR #81's `dagu-inflight-resume-after-kill` fixture (SIGKILL mid-step, then
   attempt recovery), which at 2.16.6 only waited ~1-2s post-kill and was corrected
   by a Codex coordinator review to "inconclusive" rather than "refutes_incumbent"
   because that window is inside both of Dagu's documented thresholds (30s
   `lock_stale_threshold`, 90s heartbeat `stale_threshold`). Rerun on 2.17.0 with a
   **120s hold** past the kill before attempting recovery, plus the original
   immediate post-kill history/ps capture: `dagu retry --run-id` was still refused
   (`already running... socket=/tmp/@dagu_inflight_<hash>.sock`) and `dagu history`
   still reported `running` 2m31s after the kill. **CORRECTED (this fix round):** an
   earlier draft of this README claimed this "conclusively" settled PR #81's
   self-healing question; that is retracted. No `dagu scheduler` process was ever
   started in this fixture, and Dagu's documented self-healing path is
   scheduler-driven zombie detection (a 45s zombie-detection interval times 3
   consecutive stale checks, on top of the 90s heartbeat threshold -- roughly 225s
   of scheduler uptime, per the 2.17.0 binary's own `--help` text), which this test
   never exercised. Separately, the `dagu start --run-id <same>` refusal
   (`already exists`) is a duplicate-run-ID error, not a staleness signal, and was
   previously misread as threshold-relevant. What is actually established: without
   a scheduler running, a manual `retry` on a SIGKILLed run is still refused 120s
   post-kill. Whether a running scheduler's zombie detection would recover the run
   (at 120s or at the ~225s the documented mechanism needs) remains **untested and
   inconclusive**, the same status PR #81 recorded -- not settled by this rerun. See
   `dagu.json`'s `correction_note` and revised `limits` for the full detail. The
   patched harness copies used for both dagu checks are committed under
   [`patched-harnesses/`](patched-harnesses/) with hashes and diffs against the
   tracked/PR #81 originals; an earlier, non-completing first attempt at the
   job-recovery rerun (work dir `recovery-2170-1790122973`, no `result.json`
   produced) is disclosed in `dagu.json` rather than omitted.

## ClickHouse v26.8.7.19-lts -> v26.9.2.8-stable -- not_comparable (native_proven)

[`clickhouse.json`](clickhouse.json). Release resolved via
`gh api repos/ClickHouse/ClickHouse/releases/latest` (v26.9.2.8-stable, published
2026-09-22T14:53:49Z, newer than the newest `-lts` row). Checksum of
`clickhouse-common-static-26.9.2.8-amd64.tgz` verified against the release's own
`.sha512` sidecar.

There is **no prior native ClickHouse acceptance receipt at any version** in this
repository: the only retained evidence
(`evidence/artifacts/layer-verdicts-20260922/{claude,codex}/us-equities-storage-compute-20260922.json`,
packet c6) is an unopened-README `source_review` disposition; the storage-compute
layer's actual accepted incumbent is DuckDB, not ClickHouse. So "the storage-compute
acceptance the current pin passed" named in this unit's task does not exist to
re-run. In its place, a first-time storage-compute smoke test was run directly
against the new static binary: `CREATE TABLE ... ENGINE=Memory`, multi-row insert,
`GROUP BY` aggregation, write to Parquet, and re-read from Parquet -- the
post-round-trip aggregation matched the pre-write aggregation exactly for both test
symbols. Verdict is `not_comparable` (no prior receipt to compare against), not
`qualified`, and this smoke test does not itself qualify ClickHouse for the
storage-compute layer's real acceptance bar (throughput/concurrency/immutable-ledger
semantics remain untested). **CORRECTED (this fix round):** the receipt's recorded
command text previously did not match what actually ran (it showed a relative
`./usr/bin/clickhouse` path and a `bars.parquet` relative path passed via `-n
--query`); the binary actually used lives at the versioned extraction path
`extracted/clickhouse-common-static-26.9.2.8/usr/bin/clickhouse`, and the query was
run via `--queries-file` against the retained `work/smoke.sql` (absolute paths),
producing `work/run.log`; both are retained verbatim and match the reported output
exactly, so only the recorded command text was wrong, not the result. One remaining
operational note: an initial `--queries-file` attempt against a different scratch
path hung indefinitely for an undiagnosed reason and was killed; it was not
reproduced once the SQL and output were kept under the clickhouse `work/` prefix
used for the retained run.

## skfolio 1.2.9 -> v1.3.0 -- qualified (native_proven)

[`skfolio.json`](skfolio.json). Release resolved via the PyPI JSON API (`v1.3.0`,
uploaded 2026-09-20T10:12:25Z UTC). The retained WalkForward optimizer acceptance
from open PR #81
(`blueprints/gap-resolution-20260922/skf-walkforward-optimizer/run_optimizer.py`,
receipt `evidence/artifacts/gap-resolution-20260922/portfolio-risk/skf_walkforward_optimizer.json`)
was rerun in a fresh venv against skfolio 1.3.0, against the SAME frozen
SPY/QQQ/IWM `lean-985ef30` inputs (plan.json sha256 verified unchanged) and the
same 252/63/6/`reduce_test=True` WalkForward split. Both MeanRisk and
HierarchicalRiskParity optimizers reproduced the 1.2.9 receipt's numbers to
reported precision (the 1.2.9 receipt rounded to 3 decimals; the 1.3.0 rerun is
full-precision and matches after rounding, not bit-for-bit): development Sharpe
approximations 0.778/0.846, reserved-segment weights and Sharpe 1.940
(SPY-concentrated MeanRisk) and 1.871 (diversified HRP). `inputs_unchanged=true`.
The patched harness copy used is committed under
[`patched-harnesses/skfolio-run-optimizer-130.py`](patched-harnesses/skfolio-run-optimizer-130.py)
with its diff against the PR #81 branch original.

## Not attempted / blocked

None of the three checks required a broker, paid API or credential this unit does
not have; all three ran to completion. The clickhouse verdict is limited to
`not_comparable` rather than `qualified` because no prior passing acceptance
existed to compare against, as explained above -- this is disclosed, not a blocked
check.

## Cleanup

All installs and work directories live under
`/home/example/.cache/sota-refresh-20260923/pins-runtime/{dagu,clickhouse,skfolio}/`.
Disposable `/tmp/@dagu_inflight_*.sock` files left by the killed dagu test runs were
removed. No background service was left running; the clickhouse process that hung
on `--queries-file` was killed (not the pinned host `dagu`/other tool processes).
