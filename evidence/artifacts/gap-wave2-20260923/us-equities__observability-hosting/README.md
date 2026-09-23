# Gap wave 2 (2026-09-23): us-equities / observability-hosting

One open gap (crosswalk index 0, main 92bb279, PR #85): the Claude and Codex
lanes disagreed ({otelcol-contrib, loki, prometheus} vs {otelcol-contrib,
restic, sandbox-runtime}), the counterbalanced adjudication split 2-2, and the
gap asks for an executed comparison.

| gap | outcome | receipt |
|---|---|---|
| 0 | advanced | `0-executed-comparison-dagu-arm.json` |

The work had three parts:

- **A. Source review of #87.** The executed comparison in
  `evidence/artifacts/sota-refresh-20260923/obs-compare/` is on origin/main and
  matches merge 43bb931 byte for byte. It covers all five contested candidates
  natively, but it used a synthetic OTLP emitter. The term probe found no Dagu
  or paper-runtime workload.
- **B. Dagu arm, run here.** This part started after an independent Codex review
  of commit 508ec00 found that `covered_elsewhere` overclaimed the Dagu arm,
  which had not been run. A real Dagu 2.16.6 DAG sent its native otel spans and
  its step log files through otelcol-contrib 0.161.0 to Prometheus 3.14.0
  (span metrics) and Loki 3.7.8. The runs used loopback ports (except Loki in
  rounds 1 and 2; see below) and a temporary HOME and DAGU_HOME.
  - Round 1 found a Dagu problem. The HTTP endpoint form that Dagu's schema
    documents (`http://host:4318/v1/traces`) is passed to Dagu's gRPC exporter
    and fails with "too many colons in address".
  - Round 2 used the gRPC form (`127.0.0.1:34317`, `insecure: true`) and passed.
    A second Codex review then found that Loki had been configured with ports
    only, so in rounds 1 and 2 it listened on all interfaces. That round is
    disclosed and kept in the record.
  - Round 3 bound Loki to 127.0.0.1 and hung at its first query. Loki's query
    frontend was advertising the WSL interface IP while gRPC listened only on
    loopback ("dial tcp <lan-ip>:33101: connect: connection refused").
    The round was stopped and recorded as aborted.
  - Round 4 added `frontend.address: 127.0.0.1` and is the result the committed
    script reproduces. Every run listener was on 127.0.0.1, and all six in-script
    assertions passed:
    - Span-metric series for the DAG and all 3 steps were in Prometheus before
      `kill -9`, after the restart, and from the restic-restored TSDB.
    - The pre-kill Loki marker lines were present after the restart and in the
      restored store.
    - restic took a hot backup while the stack was running.
      `check --read-data` and `restore --verify` both succeeded.
    - The restored DAGU_HOME was byte-identical to the original, and
      `dagu history` read the restored run.
    - srt (sandbox-runtime 0.0.77) denied a DAG step's egress ("No matching
      config rule, denying: example.com:443").
    - The post-run check found 0 service processes and 0 listeners left.

- **C. Paper-runtime arm (rounds 5-8), added in a continuation of this unit.**
  The real paper runner loads Alpaca credentials and calls the broker, so it
  stays with the peer session. Before deferring it, this unit ran the isolated
  alternative that is available here: the adaptive-paper runtime's own native
  path (`runner.run_native` on NautilusTrader 2.0.0rc5, AdaptiveStrategy and the
  SQLite WAL Ledger journal) against the repository's synthetic
  `SimulatedPort`. There was no network, no credentials and no broker. It ran
  as a Dagu step inside srt, and a parallel step took a hot restic snapshot of
  the live journal. This part is local_integration evidence, not paper-account
  evidence.
  - Round 5 failed during setup. A global TMPDIR pushed srt's bridge socket path
    past 108 bytes.
  - Round 6 passed every in-script check, but two defects showed up:
    - After the collector restarted, filelog re-read all 311 lines with no offset
      store, leaving 622 in Loki. The Dagu arm's round 4 shows the same doubling.
    - The count-connector counters undercounted (16 of 20 intents).
  - Round 7 persisted offsets with `file_storage` and tried a Prometheus exporter
    for the counts. The exporter showed only recent deltas, and a query mistake
    aborted the checker.
  - Round 8 (the committed script) passed everything except the log-derived
    counter:
    - Workload: the runtime passed, flat, with 16 native fills.
    - Sandbox: srt denied egress, writes outside the allowed directory and a
      decoy read, while the unsandboxed controls succeeded.
    - Loki: it held exactly 300 of 300 runtime lines before the kill, after
      `kill -9` and from the restored store, with no duplicates. LogQL
      `count_over_time` matched at every stage.
    - Span metrics were retained and restored.
    - restic: the hot and cold snapshots checked clean. The cold restore was
      byte-identical, and the journal passed `integrity_check` with table counts
      equal to the runtime's.
    - Log-derived counter: the count-connector counter read 298 of 300. Collector
      self-telemetry recorded no drop, and the root cause is not isolated.
    - Cleanup: 0 processes and 0 listeners left. Every listener was on 127.0.0.1.
  - Fix round after the independent Codex review. The review found weak
    in-script checks: substring exit matches, name-only span checks,
    timestamp-only Loki checks, and no test that the hot snapshot overlapped the
    workload. `recheck_paper_arm.py` re-checked the committed raw files with
    exact checks, and round 8 passed all 17 (`raw/recheck-paper-arm.txt`).
    Rounds 5 and 6 served as negative controls: they failed the checks they
    should.

Still open (see `remaining` in the receipt):
- Real paper-account telemetry and a broker-session order-journal backup. These
  belong to the peer session sota-workflow-resolution. Part C is a
  synthetic-port substitute, not this.
- The ledger row is still `pending_lanes`. Re-judging it is the coordinator's
  job.
- The accuracy of the log-derived Prometheus counters (count connector) is
  unresolved.
- The workload was small: one run per round, one kill, local restic
  repositories only, and no trace backend.

Files:
- `0-executed-comparison-dagu-arm.json`: the receipt, including the
  preregistrations (including rounds), commands, results, remaining work and
  limits.
- `raw/`: sanitized raw outputs (`$HOME` in place of host paths). This includes
  the verifier output for part A, `dagu-arm-round{1,2,3,4}/` for part B, and
  `paper-arm-round{5,6,7,8}/` plus `paper-sim-dry/` for part C. Every
  file's sha256 is in the receipt's `raw_outputs`.
- `results.json`: generated from the receipts by
  `blueprints/gap-wave2-20260923/us-equities__observability-hosting/make_results.py`.
- Helpers and preregistrations:
  `blueprints/gap-wave2-20260923/us-equities__observability-hosting/`.
  `dagu_arm.sh` is part B's run script. `paper_arm.sh` and
  `paper_sim_workload.py` are part C's, `collect_paper_raw.py` sanitizes part C's raw copies,
  and `recheck_paper_arm.py` is the verdict-bearing checker for rounds 6 and 8. Its scratch data remains on the host under
  the gap-wave2 cache as the recovery path.

## Coordinator note (2026-09-23): privacy sweep, third pass

RFC 1918 addresses replaced by `<lan-ip>` (loopback and 0.0.0.0 unchanged):

- `0-executed-comparison-dagu-arm.json`: 4 replacement(s), sha256 `78f5429b2f87...` -> `ff0a6b20b68b...`
- `README.md` (this file): 1 replacement
- `raw/dagu-arm-round3/loki-frontend-errors-excerpt.log`: 10 replacement(s), sha256 `a2d4e43377f7...` -> `8bdadba50cf6...`

Pins updated: `0-executed-comparison-dagu-arm.json` (`raw_outputs` sha256 and bytes of the Loki excerpt). The address also appeared in the receipt text, this README, the round-4 preregistration and a comment in `dagu_arm.sh`, all redacted the same way; no generator writes the excerpt.
