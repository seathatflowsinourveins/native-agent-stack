# Incentive monitor run `incentive-monitor-20260929`, 2026-09-29: completed, data only, 0 orders

This is the sanitized receipt of the incentive monitor's run on 2026-09-29, from 03:55 to 20:00 ET, under the systemd
user unit `incentive-monitor-20260929`. It used the key pair of the second Alpaca paper account (credential inventory
id `alpaca-paper-2`) for data and asset-list reads only. `receipt.json` holds the figures, and this directory also holds
the unit's console, byte-identical ([Files](#files)). The monitor's output, 390,574,042 bytes of licensed market data
and news, stays private; only its hashes, counts and times are published here.

It is metadata plus a partial broker listing, not a gate run, and it evaluates no strategy. No acceptance clause was
frozen for this run, so it has no pass or fail; this receipt records what the run did. The boards it writes are
unvalidated detectors. No credential, account id, account number, account fingerprint, broker order id or ref,
activity id, execution id or host path is recorded.

## Setup

**Code.** Main `b528bb55` (committed 2026-09-29), run from the read-only engine clone in the private paper state.
`monitor.py` has sha256 `88f3423a…` (135,534 bytes). Four sources agree on that hash:
- the clone's file, read on 2026-09-30;
- `git show b528bb55:blueprints/us-equities/incentive-monitor/monitor.py`;
- line 45 of `frozen-b528bb55.SHA256SUMS` (70 entries, sha256 `36daf194…`), the private hash list that checks the
  frozen engine clone of the 2026-09-29 paper series;
- `monitor.code_sha256` in the final `board.json` and `board-v2.json`, which is the process's own hash of the file it
  loaded.

The clone's HEAD was `b528bb55` with an empty git status when it was read. `monitor.py` is unchanged at the base
`f03f41c7`.

**Runtime.** Python 3.12.3 from the pinned `adaptive-paper-20260921` virtual environment, run with `python -B`. The
version was read on 2026-09-30, not at run time.

**Credential route.** The 0600 env file store ([docs/secret-storage.md](../../../../../docs/secret-storage.md)),
through the `$PAPER_ENV_FILE_2` pointer, passed as `--env-file` under `/bin/bash -ic`. The unit's interactive shell
exports that pointer and `SEC_CONTACT_ENV`, which names the SEC declared-contact file. The launch script refuses to
start without `PAPER_ENV_FILE_2`, `SEC_USER_AGENT` (set from that file) and `ENGINE_SHA`. Only variable names are
recorded.

**Settings.** From the monitor's own start and budget records:
- `run --standalone` until 20:00 ET, one sweep every 20 s, board versions 1 and 2;
- nine sources: SIP snapshots, OPRA trades, news, EDGAR, Nasdaq halts, corporate-action events, the screener,
  option chains and FINRA short volume. `--option-oi` and `--iex-status` stayed off;
- a universe of 13,499 symbols;
- per-sweep caps of 27 snapshot calls, 3 screener calls, 30 option-chain calls, 7 EDGAR calls, 1 halts poll and
  1 FINRA call, and 0 option-contract calls; daily bars at most 68 in any minute;
- planned data calls of 180 per minute, 248 in the first minute, against a cap of 500 (5% of the data API's 10,000
  per minute), and trading calls of 1 per minute against 10. The plan broke no rule.

**Unit.** `incentive-monitor-20260929.service` has `Type=exec`, `UMask=0077`, `Restart=on-failure` after 120 s, at
most 5 starts an hour and `OnFailure=paper-alert@%n.service`, and it appends stdout to the console. Its timer fired at
`2026-09-29 03:55:00 America/New_York` (`AccuracySec=1s`, not persistent). `ExecStart` runs `/bin/bash -ic`, which
exports the SEC contact variables and execs the private launch script `run-monitor.sh`. That script runs the clone's
`monitor.py` as `run --standalone --env-file "$PAPER_ENV_FILE_2" --out <private state root>/incentive-monitor
--until-et 20:00`. The unit file, the timer file and the script were all modified before the start and are hashed in
`receipt.json`; they match by time, not by proof.

**Purpose.** The data is a point-in-time record, with receive times, of the incentive sources that the preregistered
forward study [`forward-protocol-v1.json`](../../forward-protocol-v1.json) (`incentive-board-forward-v1-20260924`) is
built on. The protocol gives the reason: several board components have no usable history, and halt and news receive
times exist only from the monitor's first day. The protocol names `alpaca-paper-2` as the study's isolated account
(line 63).

This run cannot feed a protocol v1 decision, however. Its `board.json` carries monitor sha256 `88f3423a…`, while v1
is bound to `monitor.py` `4c8029e5…` and `board_scan.py` `0912f48b…` (`monitor.FROZEN_V1`, the code of `05c28491`):
- the frozen v1 bridge would refuse this board with `monitor_code_mismatch`;
- this code's bridge refuses v1 decisions with `code_not_frozen`.

Using boards from this code needs a new protocol version ([incentive-monitor README](../../README.md)).

## Run

| Event | UTC | ET |
|---|---|---|
| Timer armed | 2026-09-29T05:43:11Z | 01:43:11 |
| Unit started (journal) | 2026-09-29T07:55:00.309Z | 03:55:00 |
| Monitor start record | 2026-09-29T07:55:00.531Z | 03:55:00 |
| First sweep | 2026-09-29T07:55:01Z | 03:55:01 |
| Last sweep | 2026-09-30T00:00:10Z | 20:00:10 |
| Monitor stop record, `stop_file` false | 2026-09-30T00:00:13.849Z | 20:00:13 |
| Unit stopped (journal resource record) | 2026-09-30T00:00:14.110Z | 20:00:14 |

- **Sweeps.** 2,874 sweeps. The interval between sweep starts was 20.0 s at the median (mean 20.156 s, minimum
  20.0 s, maximum 109.0 s).
- **Long sweeps.** A sweep took 3.32 s at the median (1.98 s to 108.28 s).
  - 19 sweeps took longer than 20 s, between 10:38:22 and 17:33:21 ET, 16 of them after 16:00 ET.
  - 14 intervals exceeded 25 s, all between 16:20:36 and 17:34:26 ET. The longest sweep started at 17:29:30 ET.
  - The monitor records no per-source timing, so the files do not show the cause.
- **Snapshots.** Each sweep returned 13,186 to 13,191 SIP snapshot rows and wrote one snapshot file of the rows whose
  last trade had changed: 2,874 files, 14 of them empty.
- **Option chains** were read in 1,125 sweeps, from 09:45:02 to 15:59:51 ET.
- **Halts and filings.** The Nasdaq halts RSS was polled 961 times and showed 46 halt changes. EDGAR returned 696 new
  filings.
- **FINRA.** At 18:05:09 ET the monitor fetched the 2026-09-29 short-volume file. At 18:05:29 and 18:05:49 ET it found
  the 2026-09-28 and 2026-09-25 files unchanged on their update checks.
- **Relative volume.** The daily-bar load finished (`adv_loaded` true in the final board).

## Totals

**Streams.**

| Stream | Connected (ET) | Disconnects | Down | Messages |
|---|---|---|---|---|
| News | 03:55:01 | 0 | 0.0 s | 916 |
| OPRA trades | 03:55:01 | 1, at 17:31:12 ET; back at 17:31:14 ET | 2.1 s | 9,886,534 |
| Corporate-action events | 03:55:07 | 0 | 0.0 s | 51,822 archived |
| IEX status | not requested | | | |

- The OPRA drop was `ConnectionClosedError: no close frame received or sent`, reconnect attempt 1.
- The corporate-action stream resumed from the newest archived event. Its start-up context replay held 1,298 events
  (278 actions) since 2026-08-30T04:00:00Z. It surfaced 1,321 events and dropped 1 duplicate.
- No OPRA trade failed to parse.

**Calls and budget.** These are the monitor's cumulative counters at the last sweep and its per-sweep call records:
- **Total.** 135,617 calls: 114,534 to Alpaca, 20,119 to SEC EDGAR, 961 to the Nasdaq RSS and 3 to FINRA.
- **Inside sweeps.** Snapshots made 77,598 calls, which is 2,874 sweeps times 27, and the screener 8,622 (times 3).
  Option chains made 28,245 calls and daily bars 12. EDGAR made 20,118 (times 7), with 961 halts polls and 3 FINRA
  calls.
- **Outside sweeps.** 57 Alpaca calls and 1 SEC call were made outside sweep windows, by the start-up loads and the
  background daily-bar load. The files do not attribute them by source.
- **Caps.** No source ever exceeded its per-sweep cap, and the budget refused 0 calls.
- **Busiest minute.** The busiest 60 s of in-sweep data calls held 180, from 13:45:02Z, against the cap of 500. That
  count leaves out the 57 calls outside sweeps.
- **Rate limits.** The data API's lowest recorded remaining allowance was 9,996 of 10,000, at 14:29:22Z. The trading
  API's reading stayed at 199 of 200, from the start-up asset-list response, in all 2,874 sweeps.

**Private files.** The day directory holds 16 files and 2,874 snapshot files, 390,574,042 bytes in all.
`receipt.json` holds each file's sha256 (`private_files`) and the snapshot manifest's (`private_snapshots`). No file
changed after the unit stopped; the latest modification was at 2026-09-30T00:00:13.845Z.

| File | Records | Bytes |
|---|---|---|
| `monitor.jsonl` (budget, sweeps, streams) | 2,884 | 2,417,359 |
| `board.jsonl` (board version 1) | 2,874 | 16,463,362 |
| `board-v2.jsonl` | 2,874 | 47,574,315 |
| `regime.jsonl` | 2,874 | 653,938 |
| `screener.jsonl` | 2,874 | 53,729,381 |
| `news.jsonl` | 916 | 563,824 |
| `edgar.jsonl` | 696 | 240,571 |
| `halts.jsonl` | 46 | 14,548 |
| `corporate-actions.jsonl` | 51,822 | 23,925,347 |
| `options-minute.jsonl` | 532,713 | 58,750,876 |
| `options-large.jsonl` | 26,819 | 5,437,119 |
| `options-iv.jsonl` | 27,996 | 34,763,130 |
| `board.json`, `board-v2.json`, `halt-state.json` (latest state) | | 27,484; 60,925; 5,568 |
| `adv20.json` (relative-volume baseline) | | 234,299 |
| `snapshots/` (2,874 gzip files) | 3,555,660 rows | 145,711,996 |

Each record count matches the monitor's own counter where one exists:
- `news.jsonl` matches the news stream's message count;
- `edgar.jsonl` and `halts.jsonl` match the sweeps' new filings and halt changes;
- `options-iv.jsonl` matches the option-chain roots answered;
- `corporate-actions.jsonl` matches the archived-event count;
- the board, regime and screener files hold one record per sweep.

The snapshot manifest's sha256 is `a5b73f5f…`; recompute it with `cd snapshots && sha256sum *.json.gz | sha256sum`.

## Broker reconciliation and orders

No broker reconciliation was run for the monitor itself. The coordinator's read-only reconciliation for the
2026-09-29 paper series listed account 2's orders in two windows. It ran on 2026-09-30 at 09:06Z with
`reconcile_ext_series.py` (sha256 `50b9da4c…`, the main copy in
[`../../../adaptive-paper/trials/ext-20260928/`](../../../adaptive-paper/trials/ext-20260928/reconcile_ext_series.py)).
- From 11:00Z to 13:45Z it listed 18 orders, all `mvr-pre-20260929-`.
- From 20:00Z to 00:10Z it listed 22 orders: 21 `mvr-ext-20260929-` and 1 `rec-ext-20260929-`.

No listed order lacks a paper-series prefix. No broker read covers 07:55Z-11:00Z or 13:45Z-20:00Z.

The monitor placed no order. The basis:
- **Code.** Every REST request goes through `Http.get`, which builds a urllib request without a body (a GET),
  behind the fail-closed per-source budget. The sources list no order, position or activity endpoint, and the stream
  connections subscribe to news, OPRA trades and corporate-action events. The docstring says: "Data only: it never
  places, changes or cancels an order."
- **Recorded calls.** The trading API's rate-limit reading never changed after the start-up asset-list read, and
  the budget refused nothing. Option contracts, the only other trading-host source, had a cap of 0.
- **Broker listing.** The two windows above.

## Errors, rejects and retries

- **Sweep errors.** No sweep carried an error key (`<source>_error`), a rate-limit floor or a budget refusal, and
  the final `board.json` lists no sweep error.
- **Option chains.** 27,996 roots were answered.
  - 3 roots answered HTTP 400, at 11:41:48, 12:03:08 and 14:12:31 ET, and were marked as having no options for the
    day. 107 were empty.
  - 120 were asked again without the strike band, and 19 such retries were deferred to a later sweep.
  - No chain request hit its deadline, the budget or another error.
- **Streams.** One drop: OPRA at 17:31:12 ET, back 2.1 s later.
- **HTTP 406: 0.** A 406 would be written as a `stream_error` record followed by `stream_conflict` or
  `stream_down`, and the run has none. The IEX stream, the one with a 406 wait, was not requested.
- **HTTP 429: 0 recorded.** A failed REST call is written as a `<source>_error` key in its sweep or as `http_<code>`
  in the option-chain counts, and no sweep has either for 429. The daily-bar loader retries a failed request without
  writing it, so a 429 absorbed by such a retry would not show.
- **Console.** It holds only the two bash job-control notices of the unit's non-terminal interactive shell. The
  monitor wrote nothing to stdout or stderr.
- **Receive times.** `options-large.jsonl` rows carry the trade time (`trade_ts`) but no receive time, although the
  incentive-monitor README says every record carries one.

## Deviations from the plan

None. The unit started once at its timer time, ran standalone with the planned sources and caps, and stopped itself
at 20:00 ET. The brief gives the output as 379 MB; that is a disk-usage figure, and the files hold 390,574,042 bytes.

## Units (systemd user journal and service manager)

| Unit | Start (UTC) | Stop (UTC) | Result |
|---|---|---|---|
| `incentive-monitor-20260929` | 07:55:00 | 00:00:14 (2026-09-30) | `Result=success`, main process exited with status 0 (service manager); no exit record in the journal |

- **Journal.** `journalctl --user -u incentive-monitor-20260929 --since 2026-09-29 --until 2026-09-30` (systemd
  255) returns 3 records: the start job, its completion, and the resource-accounting record at stop (50min 37.840s
  CPU, 435.8M memory peak, 2.4M swap peak). It has no `EXIT_STATUS`, `EXIT_CODE` or `UNIT_RESULT` record, as in the
  2026-09-28 receipt.
- **Service manager.** `systemctl --user show` reported on 2026-09-30:
  - `Result=success`, `ExecMainStatus=0` and `NRestarts=0`;
  - `ExecMainCode=1`, which is CLD_EXITED (the main process exited), not an exit status;
  - start at 03:55:00 EDT and exit at 20:00:14 EDT.

  These are observed values, not inferred from a missing failure record.
- **Starts.** 1 start and 0 restarts. The `OnFailure` alert unit never started: it has no invocation id, no start
  timestamp and no journal entry.

## Limitations

- **Data only.** The run evaluates no strategy and qualifies no gate. The boards are unvalidated detectors fixed
  without outcome data.
- **Code identity** rests on hashes read on 2026-09-30 and on the process's own `code_sha256` in `board.json`, which
  it computed at start.
- **Private launch files.** The launch script and the unit files are matched by modification time, not by a hash
  taken at run time. The Python version was read on 2026-09-30.
- **Exit status.** The journal holds no exit record. The exit status comes from the service manager's retained
  properties.
- **Broker coverage.** No broker read covers 07:55Z-11:00Z or 13:45Z-20:00Z on account 2. For those hours the
  no-order statement rests on the code and the recorded calls.
- **Unrecorded retries.** A 429 absorbed by a daily-bar retry would not be recorded. 57 Alpaca calls and 1 SEC call
  are not attributed by source.
- **Long sweeps.** The cause of the 19 long sweeps is not in the files.
- **FINRA files.** The files this run fetched sit in the monitor's shared `finra/` directory and are not hashed here.
- **Licensed data.** The data stays private; only hashes, counts and times are published.

## Paper lane row

No paper-lane row changes with this record. The run is data only and placed no order.

## Files

| File | What it is |
|---|---|
| `receipt.json` | The run receipt: code identity, settings, unit and journal records, sweeps, streams, calls, errors, the no-order basis, the account 2 listing, private file hashes and field provenance |
| `README.md` | This summary |
| `monitor-20260929.console` | The unit's console (stdout and stderr), byte-identical: two bash job-control notices |

Private and not committed:
- the day directory's 16 files and 2,874 snapshot files (licensed market data and news);
- the launch script `run-monitor.sh`, the unit file and the timer file;
- the FINRA files;
- the engine clone.
