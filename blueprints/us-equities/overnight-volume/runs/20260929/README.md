# Overnight volume watch `overnight-volume-20260929`, night of 2026-09-28/29: completed, data only, 0 orders

This is the sanitized receipt of the overnight volume watch ([`watch.py`](../../watch.py)) for trade date 2026-09-29.
It ran under the transient systemd user unit `overnight-volume-watch-20260929.service` from 22:09:29 ET on 2026-09-28
to 04:00:04 ET on 2026-09-29 and made 176 sweeps of the BOATS overnight session.
`receipt.json` holds the figures. The watch's output, 25,039,445 bytes derived from licensed market data, stays
private; only its hashes, counts and times are published here, and no alerted symbol is named.

It is metadata only, not a gate run, and it evaluates no strategy. No acceptance clause was frozen for this watch, so it
has no pass or fail. The thresholds file was committed before the first sweep, but it defines monitoring tiers, not
acceptance. The freeze notes of the 2026-09-29 paper series state what the watcher may do, and it met each statement
([Deviations from the plan](#deviations-from-the-plan)). No credential, account id, account number, account
fingerprint, pid or host path is recorded.

## Setup

**Code.** The watch's `start.json` records git HEAD `dca569ae` (committed 2026-09-28 21:55:05 ET) with an empty git
status. The watch computes that status itself over `overnight-volume/` and `incentive-monitor/monitor.py` only. The
process hashed the files it loaded, and each hash matches `git show` at `dca569ae`:
- `watch.py` `1cdd9265…`;
- `monitor.py` `88f3423a…`, unchanged on main;
- `thresholds-v1.json` `8287b858…`, unchanged on main.

`dca569ae` is not on main. It is in no local ref (remote-tracking branches included) and not in the history of
`refs/pull/480/head`, because PR #480's branch was rebased after the launch. That history holds `6545d7ad`, committed
at 22:10:28 ET, whose `watch.py` is the same git blob (`090372b4…`). The code that ran is therefore retrievable:
`git fetch origin refs/pull/480/head`, then `git show 6545d7ad:blueprints/us-equities/overnight-volume/watch.py |
sha256sum`.

Main's version differs. The PR head `04ab3308` added a repair round after a GPT-6 review, and the squash merge
`1b8d6334` (#480) carries it. Its `watch.py` (`d6fd26f0…`) has 145 lines added and 34 removed against the run's. The
changes that matter for reading this run's files:
- **Push records.** The run's code writes one `push` record per attempt, after the POST, with `status` sent or
  failed. Main writes a `push` record before the POST and a `push_result` after it. So this run's `alerts.jsonl` has
  `push` records with a status and no `push_result` records, although the [README](../../README.md) on main describes
  the latter.
- **Rate-limit probe.** In the run's code, a failed or rate-limited first chunk did not stop a sweep's fan-out. No
  chunk failed.
- **Plan.** The run's plan counts the first minute as 108 calls; main counts 118. Both stay under the cap of 500.
- **Start-up.** Main checks a stop request and its 600 s start-up deadline before every start-up request and wait,
  and refuses an `--out` inside a git worktree. The run's code applied its 600 s deadline only inside the daily-bar
  passes' budget waits and retries, checked for a stop only before the start-up began, and did not refuse an `--out`
  inside a worktree.

**Runtime.** Python 3.13.15, as recorded by the process in `start.json`.

**Credential route and account.** Account 1 (credential inventory id `alpaca-paper`), through the `$PAPER_ENV_FILE`
pointer to the 0600 env file store, passed as `--env-file` under `/bin/bash -ic`. The unit's `ExecStart`, logged in
the journal, names that pointer ([Units](#units-systemd-user-journal)). The watch's own files do not record which
key file was passed, and the pointer's value is not recorded.

**Thresholds** ([`thresholds-v1.json`](../../thresholds-v1.json), id `overnight-volume-watch-v1`):
- significant tier: at least $250,000 of overnight dollar volume and any of 2% of ADV20, a 5% move from the prior
  regular close or 5x the 20-session BOATS volume;
- notify tier: at least $1,000,000 and any of 5% of ADV20, a 10% move or 10x relative volume. Only this tier posts,
  for non-fund names only, at most 5 a sweep and 40 a session;
- relative volume counts only with at least 10 prior BOATS sessions; two top-25 lists are written every sweep;
- posts go to the loopback ntfy topic `http://127.0.0.1:18080/overnight-volume`, and pushing was enabled.

**Plan.** The watch wrote this at start:
- 9,683 symbols, one sweep every 120 s, 20 snapshot calls a sweep (10.0 a minute on average);
- 99 start-up calls, with at most 98 daily-bar calls in any minute;
- 108 calls in the first minute, against a cap of 500 (5% of the data API's 10,000 per minute).

The plan broke no rule.

**Universe and reference.**
- **Assets.** Of 14,373 assets, 13,495 were tradable, 9,683 overnight-tradable and 3,502 overnight-halted. The watch
  covered the 9,683 overnight-tradable names.
- **Reference.** The prior regular session was 2026-09-28, and the 20 reference sessions ran from 2026-08-31 to
  2026-09-28. ADV20 covered 9,683 names and the reference close 9,677.
- **BOATS baseline.** It covered 3,629 names, 1,197 of them with at least 10 prior BOATS sessions.
- **Start-up calls.** The start-up made exactly its 99 planned calls: 1 asset list and 98 daily-bar requests. Every
  attempt is a counted call, so no start-up request was retried or needed a second page.

## Run

| Event | UTC | ET |
|---|---|---|
| Output directory born (filesystem birth time) | 2026-09-29T02:09:29.233Z | 22:09:29 |
| Unit started (journal) | 2026-09-29T02:09:29.283Z | 22:09:29 |
| The watch began its start-up (derived) | 2026-09-29T02:09:29.351Z to .451Z | 22:09:29 |
| Start record, first sweep | 2026-09-29T02:09:58Z | 22:09:58 |
| Last sweep | 2026-09-29T07:59:58Z | 03:59:58 |
| Planned stop | 2026-09-29T08:00:00Z | 04:00 |
| Stop record, reason `stop_time` | 2026-09-29T08:00:04Z | 04:00:04 |
| Unit stopped (journal resource record) | 2026-09-29T08:00:04.686Z | 04:00:04 |
| Backstop (`backstop_et`) | 2026-09-29T08:05:00Z | 04:05 |

- **Start-up.** The start record (22:09:58 ET) follows the watch's 99 start-up calls, which it counts before writing
  the record. The watch began its start-up 0.12 to 0.22 s after the output directory's birth: its summary's `seconds`
  (21,035.1, counted from the start of `Watch.execute`) taken back from the summary's write at 08:00:04.501Z. The
  watch's own `mkdir` on `--out`, just before that, therefore found the directory in place. The directory is also
  50 ms older than the unit's Started record; what created it is not recorded.
- **Sweeps.** 176 sweeps, numbered 1 to 176 without a gap, every one exactly 120.0 s after the previous. A sweep
  took 1.04 s at the median (0.94 s to 1.18 s).
- **Coverage.** Every sweep made its 20 snapshot calls, and all 3,520 chunks returned ok. Each sweep returned
  9,669 of the 9,683 names, with the same per-chunk counts in all 176 sweeps; which 14 names were missing is not
  recorded.
- **Session bars.** The number of names with an overnight session bar grew from 796 at the first sweep to 1,317 at
  the last.
- **Late start.** The first sweep came 130 minutes after the session opened at 20:00 ET. The session bar's volume is
  cumulative, so the first sweep's measures include activity from before the watch started.
- **Session bar rollover.** SPY's BOATS `dailyBar.t` stayed at 2026-09-29T00:00:00Z in all 176 sweeps, across
  midnight ET, and no `session_bar_rolled` record was written. This directly observes what the overnight-volume README
  lists as inferred: the BOATS daily bar is keyed to the session and does not roll at ET midnight.

## Totals

**Requests.** 3,619 requests: 1 asset list, 98 daily-bar requests and 3,520 snapshot requests (176 sweeps times 20).
- **Failures.** 0 failed.
- **Busiest minute.** At most 119 requests in any minute. That minute could hold only the start-up's 99 and the first
  sweep's 20, because a 60 s window holds at most one sweep start.
- **Rate limit.** The lowest remaining data allowance was 9,998 of 10,000.

**Alerts.** 75 alert records: 62 significant and 13 notify.
- **Names.** They covered 62 distinct names, and all 13 notify names had also alerted significant. The fund tag
  marked 40 of the significant alerts and 7 of the notify alerts.
- **Reasons.** 48 of the 62 significant alerts crossed on the ADV fraction alone.
- **Timing.** New alerts came in 42 sweeps: 22 at the first sweep, and the last at 03:59:58 ET.
- **At the stop.** 61 names met the significant tier and 13 the notify tier, 6 of them non-fund names. At the first
  sweep the counts were 17, 5 and 4.

**Posted or not.**
- **Posted.** 6 notify alerts were posted to the loopback ntfy topic, all `sent`, 0 failed: 4 at sweep 1 (22:09:58
  ET), 1 at sweep 70 (00:27:58 ET) and 1 at sweep 128 (02:23:58 ET). The queued names and the posted names are the
  same set. "Sent" means the POST returned without an error; the ntfy server's own record was not read.
- **Not posted.** The 7 fund-tagged notify alerts (`excluded_fund_name`) and the 62 significant alerts, since that
  tier never posts.

**Private files.** The output directory holds 6 files and 176 snapshot files, 25,039,445 bytes in all.
`receipt.json` holds each file's sha256 (`private_files`) and the snapshot manifest's (`private_snapshots`). No file
changed after the stop record; the latest modification was at 2026-09-29T08:00:04.501Z.

| File | Records | Bytes |
|---|---|---|
| `start.json` (code identity, plan, universe, reference) | | 1,908 |
| `stop.json` (stop reason and totals) | | 333 |
| `sweeps.jsonl` (start, 176 sweeps, stop) | 178 | 246,494 |
| `alerts.jsonl` (75 alerts, 6 push records) | 81 | 31,239 |
| `top.jsonl` (two top-25 lists a sweep) | 176 | 2,542,252 |
| `board.json` (state at the last sweep) | | 41,476 |
| `snapshots/` (176 gzip files of raw BOATS snapshots) | 183,112 rows | 22,175,743 |

Each snapshot file's row count equals its sweep's count of names with a session bar. The snapshot manifest's sha256 is
`55ece656…`; recompute it with `cd snapshots && sha256sum *.json.gz | sha256sum`. The names cross midnight ET, so that
order is lexical, not chronological.

## Broker reconciliation and orders

No broker read covers the watch window: 02:09Z to 08:00Z on 2026-09-29 on account 1.

The watch placed no order. The basis:
- **Code.** Every Alpaca request goes through `GuardedHttp.get`. It checks an allow-list of three GET endpoints
  before any request: paper trading `/v2/assets`, and data `/v2/stocks/snapshots` and `/v2/stocks/bars`. The only
  other request is the notify POST to the loopback ntfy URL.
- **Recorded calls.** 1 asset list, 98 daily-bar requests and 3,520 snapshot requests, all allow-listed GETs, plus 6
  posts to the loopback topic.

## Errors, rejects and retries

- **Errors.** No sweep error, no failed or skipped chunk and no rate-limit floor. The stop record's `refused` and
  `error` fields are null.
- **HTTP 429: 0.** A failed chunk, a 429 included, is recorded with status `error` and its message, and all 3,520
  chunks returned ok. The start-up does not write each retry, but every attempt is a counted call, and the start-up
  made exactly its planned 99.
- **HTTP 406.** Not applicable: the watch opens no stream.

## Deviations from the plan

The plan is the run commit's thresholds and launch command, and what the freeze notes of the three 2026-09-29 paper
series say about the watcher. The freeze notes stay private and are cited by sha256 (`receipt.json`
`private_notes_sha256`); no acceptance clause in them names the watcher. The run met each statement
(`frozen_expectations`):

| Freeze note | Line | Statement | Met |
|---|---|---|---|
| `pre-20260929/FREEZE.md` (`3cd44b78…`) | 12 | "The only other paper-key consumer is the data-only overnight watcher (key 1, no trading writes). It stops at 04:05 ET." | Yes: key 1, 0 orders, stopped at 04:00:04 ET |
| `rth-20260929/FREEZE.md` (`4e595a8d…`) | 7 | The same, with "before this series starts" | Yes: the rth unit started at 10:00:05 ET |
| `ext-20260929/FREEZE.md` (`c72bbfed…`) | 7 | The same as the pre note | Yes |

1. **Stop time.** The brief gives the stop as about 04:05 ET. The watch stopped itself at 04:00:04 ET (the thresholds'
   `stop_et` 04:00, reason `stop_time`), before 04:05 ET. 04:05 ET is the thresholds' `backstop_et`, which the run
   commit's README calls the backstop for an external supervisor; whether any stop at 04:05 ET was configured is not
   recorded.
2. **Code not on main.** The watch ran `dca569ae`, the pre-review version of #480, as described above.

## Units (systemd user journal)

| Unit | Start (UTC) | Stop (UTC) | Result |
|---|---|---|---|
| `overnight-volume-watch-20260929.service` (transient) | 02:09:29 | 08:00:04 | Not recorded: no exit line in the journal, and the unit is gone from the service manager |

- **Unit.** A transient systemd user unit. Its `ExecStart` runs `/bin/bash -ic` with the command
  `exec python3 blueprints/us-equities/overnight-volume/watch.py run --env-file "$PAPER_ENV_FILE" --out
  "<private overnight-volume directory>/20260929"`, decoded from the command line the user manager logged as the
  unit's description. `<private overnight-volume directory>` stands for the watch's output root, a sibling of the
  private paper state directory, not inside it. The watch arguments are the run commit's documented launch arguments.
- **Journal.** `journalctl --user -u overnight-volume-watch-20260929.service --since 2026-09-28 --until 2026-09-30`
  (systemd 255) returns 7 records. The unit started on 2026-09-28 ET, so a query from 2026-09-29 misses its start.
  - 22:09:29 ET: the start job's completion, with the `ExecStart` above.
  - 22:09:29 ET: the two bash job-control notices of an interactive shell without a terminal.
  - 22:09:58 ET: the watch's start line on stdout (99 start-up calls, 9,683 names watched).
  - 04:00:04 ET: the watch's summary line on stdout (reason `stop_time`, 176 sweeps, 3,619 calls).
  - 04:00:04 ET: the resource record at stop (45.760 s CPU, 145.8M memory peak, 72.0K swap peak).
  - 04:09:59 ET: a notice that the transient unit file could not be opened (no such file), so it was gone by then.

  The journal has no exit-status or result line. The console lines stay in the journal; the start line's figures
  equal `start.json`'s, and the summary line's equal `stop.json`'s and the last sweep's.
- **Starts.** 1 start and 0 restarts: one Started record, one invocation id and one process, whose pid equals the one
  in `start.json` (neither value is published).
- **Service manager.** On 2026-09-30, `systemctl --user show` reports the unit as `LoadState=not-found`, and
  `systemctl --user list-unit-files` lists no overnight-volume unit. The result and exit status it prints for a unit it
  no longer holds are defaults, not observations.

## Limitations

- **Data only.** The watch evaluates no strategy and qualifies no gate. The tiers are unvalidated monitoring
  thresholds.
- **One venue.** BOATS is one ATS, so its volume is indicative venue data, not consolidated volume. The fund tag misses
  some ETFs.
- **Code not on main.** It is retrievable through `refs/pull/480/head` and `6545d7ad`, not from main.
- **Exit status.** The journal holds no exit line and the transient unit is gone from the service manager, so the
  exit status and the unit's result are not recorded; the watch's stop record says `stop_time` with no error. Whether
  any stop at 04:05 ET was configured is not recorded either.
- **Key file.** The watch's own files do not record it; the unit's `ExecStart` names the `$PAPER_ENV_FILE` pointer
  (account 1), not its value.
- **Output directory.** What created it is not recorded: it was born 50 ms before the unit's Started record, and the
  watch's own `mkdir` found it in place.
- **Coverage.** Which 14 names never returned a snapshot is not recorded.
- **No broker read.** The no-order statement rests on the code and the recorded calls.
- **Delivery unchecked.** Posts count as sent when the POST returned without an error.
- **Late start.** The first 130 minutes of the session were not swept.

## Paper lane row

No paper-lane row changes with this record. The watch is data only and placed no order.

## Files

| File | What it is |
|---|---|
| `receipt.json` | The run receipt: code identity and its public copy, main's differences, thresholds and plan, universe, sweeps, requests, errors, alerts, the no-order basis, the unit and its journal records, the frozen expectations, private file and note hashes and field provenance |
| `README.md` | This summary |

Private and not committed:
- the watch's 6 output files and 176 snapshot files, derived from licensed market data;
- the alerted symbols and their measures, which stay in `alerts.jsonl`;
- the console lines, which stay in the unit's journal;
- the series freeze notes, cited by sha256.
