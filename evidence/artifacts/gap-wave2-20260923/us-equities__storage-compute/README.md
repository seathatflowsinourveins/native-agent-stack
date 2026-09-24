# Gap wave 2: us-equities / storage-compute (2026-09-23)

The gaps come from the crosswalk at main 92bb279 (PR #85), copied to `inputs/gaps-input.json`.
Every preregistration in `prereg/` was committed in af80671 before its check ran.
A read-only Codex (gpt-6-astra) review of round 1 (a0f57fa) found seven problems. The fix-round preregistrations (`prereg/*-fixround.json`) were committed in 23c9902, before round 2 ran.
A Codex re-review of round 2 (6155b51) found two more problems:
- The kill test's in-flight marker did not prove that an engine-level write was interrupted.
- One raw file had a gitignored `.jsonl` name.

The round-3 preregistration (`prereg/10-fixround2.json`) was committed in 1f234b9. Round 3 is the primary benchmark evidence, and rounds 1 and 2 are kept alongside it. The real-snapshot and paired-receipt checks use round 2.
`results.json` is generated from the receipts by
`blueprints/gap-wave2-20260923/us-equities__storage-compute/build_receipts.py`.

| Gap | Outcome | Receipt | Evidence class |
|---:|---|---|---|
| 0 | advanced | `0-alpaca-snapshot-parquet-duckdb-gate.json` | local_integration |
| 3 | settled | `3-four-store-throughput-concurrency.json` | local_integration |
| 4 | settled | `4-real-snapshot-promotion-gate.json` | local_integration |
| 6 | covered_elsewhere | `6-paired-astra-claude-covered.json` | source_review |
| 10 | settled | `10-four-store-latency-recovery-footprint.json` | local_integration |

## What ran

- **Gaps 0 and 4.** Two real Alpaca daily-bar snapshots were used: SIP feed, raw adjustment, 24 symbols by 20 sessions. The merged #84 ingest (`blueprints/us-equities/data/ingest_snapshot.py`) wrote them, and this unit read them without modifying them.
  - Each file hash matches its ingest receipt.
  - The pinned Pandera gate passed 12 of 12 checks on both snapshots. It ran in a freshly built venv from `blueprints/us-equities/data/requirements.lock` using `--require-hashes`.
  - A mutated control of each snapshot fails exactly `high_ge_max_open_close` and `unique_symbol_session`.
  - Each snapshot was also written to Zstandard Parquet and set to read-only (mode 0444). A two-way `EXCEPT ALL` comparison found zero differing rows. Round 2 added a precision check: 0 rows lost precision, and the check does detect the probe value `1.23456`. Round 2 also retains the full ingest receipts.
  - DuckDB 1.5.5 bars queries match the receipt counts.
  - As a supplementary check, the gate also passed on LEAN's bundled AlgoSeek daily bars: 5 symbols over 252 sessions, plus the full history of 17 tickers (70,011 rows).
- **Gap 0 remainder.** Two things are still open:
  - The exact request (5 symbols over 1 year with `feed=iex`, and its licence-scope record) needs the paper credential file and a broker market-data call. It is owned by sota-workflow-resolution.
  - The catalyst-join query has not run.
- **Gaps 3 and 10.** Four stores were compared: DuckDB 1.5.5, ClickHouse 26.8.11.7-lts (a single loopback server), QuestDB 10.0.1 with its bundled JRE (a single loopback server) and pyiceberg 0.12.0 (SQLite SQL catalog). Each store loaded the same fixed-seed 50,000,000-row OHLCV dataset.
  - Per store, the runs covered:
    - bulk load
    - Q1 to Q4 latency (5 timed runs)
    - writers-only, readers-only and mixed phases at 1, 4 and 8 clients, reporting p50, p95 and p99
    - a SIGKILL kill-and-recover test
    - disk and RSS footprint
  - In rounds 2 and 3, the full Q1 to Q4 result rows agree across all four stores. Keys and counts match exactly, and floats agree within a relative tolerance of 1e-9.
  - The round-3 kill test:
    - The writer writes an `I` marker immediately before each engine call.
    - Each store was killed while its writer was inside an engine call, at least 25% of the median call duration after the `I` marker and before any ack.
    - After recovery, the test checked every batch for exact row count, distinct timestamps and expected content.
  - All acknowledged batches were exact in every store, and every in-flight batch was absent.
  - A detection control shows that this per-batch check catches a lost-plus-duplicated batch pair. The round-1 aggregate check misses that case.
  - pyiceberg concurrent appends needed commit retries. In round 3, 58 appends failed after pyiceberg's own retries: 2 at W4, 13 at W8, 6 at M4 and 37 at M8. The harness rewrote and committed each one, which left 58 orphan data files. The kill added none.
  - A second DuckDB process cannot open the file while a writer holds it.
  - Raw per-store JSON and stdout are in `raw/bench-*`.
- **Gap 6.** `adoption/paired/receipt.json` records the executed 2026-09-19 Dagu `research-pair` run: gpt-6-astra, then claude-opus-5, both completed, with reports validated and usage recorded. `verify_paired_receipt.py` rechecks its hashes and status fields. In round 2 it also rebuilds both prompts with `run_worker.native_prompt` and checks their hashes. Two controls confirm the checks work:
  - A one-byte report change fails the report-hash check.
  - An edited Astra finding, with a matching updated report hash, fails only the handoff (prompt-hash) check.
  - No model was called for gap 6. The only model call in this unit was the Codex read-only review.

## Limits

- The benchmarks ran three times per store on a shared WSL2 host with 24 CPUs. The 1-minute load average when each store started was 19 to 34 in round 1, 9 to 13 in round 2 and 4 to 5 in round 3. The latency and throughput numbers are therefore noisy. For example, DuckDB bulk load was 11.7M, 21.4M and 23.1M rows/s across the three rounds.
- The harness uses Python clients, and client serialization time is included in every latency.
- The kill test uses a process kill only. It does not test power loss or fsync policy.
- A first ClickHouse run under the default 256-task cgroup limit lost a worker and was rerun with a 4,096-task limit. The failed attempt's output is kept in `raw/bench-clickhouse.attempt1-tasksmax256.stdout.txt`.
- No market-data row or price-derived value is committed.
- `blueprints/us-equities/data/README.md` lines 119 to 124 are now stale relative to #84. They were not edited here.

## Installs and downloads (all under `$HOME/.cache/gap-wave2-20260923/storage-compute/`)

- QuestDB 10.0.1 runtime tarball: 98,016,278 bytes. Its sha256 matches the GitHub asset digest.
- ClickHouse common-static 26.8.11.7 tgz: 235,732,763 bytes. `sha512sum -c` reported OK.
- The uv wheel cache for both venvs is about 502 MB.
- The Alpaca market-data plan docs page is 495,323 bytes. Only an excerpt is kept.
- Downloads and heavy runs went through `ecosystem-bounded-run`.
- All servers used loopback ports and temporary data directories, and all of them were stopped.

## Independent review

There were three read-only Codex reviews, each run with `codex exec --sandbox read-only --ephemeral`, model gpt-6-astra and reasoning effort ultra, one call at a time. The prompts and final messages are in `raw/codex-review-{1,2,3}.txt`.

| Review | Commit reviewed | Tokens used | Outcome |
|---:|---|---:|---|
| 1 | a0f57fa | 93,417 | 7 findings, all fixed in round 2 |
| 2 | 6155b51 | 67,760 | 2 findings, fixed in round 3 |
| 3 | d8ad36a | 57,828 | No outcome-changing findings. All 48 cited raw files are tracked and hash-match. |

No Claude model call was made by this unit.
