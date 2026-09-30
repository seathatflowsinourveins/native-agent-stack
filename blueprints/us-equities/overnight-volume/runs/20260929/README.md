# Overnight volume watch `overnight-volume-20260929`, night of 2026-09-28/29: completed, data only, 0 orders

This is the sanitized receipt of the overnight volume watch ([`watch.py`](../../watch.py)) for trade date 2026-09-29.
It ran from 22:09:58 ET on 2026-09-28 to 04:00:04 ET on 2026-09-29 and made 176 sweeps of the BOATS overnight session.
`receipt.json` holds the figures. The watch's output, 25,039,445 bytes derived from licensed market data, stays
private; only its hashes, counts and times are published here, and no alerted symbol is named.

It is metadata only, not a gate run, and it evaluates no strategy. No acceptance clause was frozen for this watch, so it
has no pass or fail. The thresholds file was committed before the first sweep, but it defines monitoring tiers, not
acceptance. The watch ran without a systemd unit, from an interactive shell. No credential, account id, account number,
account fingerprint or host path is recorded.

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
- **Start-up.** The run's code has no stop check, no 600 s start-up deadline and no refusal of an `--out` inside a
  git worktree.

**Runtime.** Python 3.13.15, as recorded by the process in `start.json`.

**Credential route and account.** Account 1 (credential inventory id `alpaca-paper`), through the `$PAPER_ENV_FILE`
pointer to the 0600 env file store, passed as `--env-file` under `bash -ic`. The account comes from the coordinator's
brief and the run commit's documented launch command; the run's own files do not record which key file was passed.

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
| Output directory created (filesystem birth time) | 2026-09-29T02:09:29Z | 22:09:29 |
| Start record, first sweep | 2026-09-29T02:09:58Z | 22:09:58 |
| Last sweep | 2026-09-29T07:59:58Z | 03:59:58 |
| Planned stop | 2026-09-29T08:00:00Z | 04:00 |
| Stop record, reason `stop_time` | 2026-09-29T08:00:04Z | 04:00:04 |
| Backstop, not used | 2026-09-29T08:05:00Z | 04:05 |

- **Sweeps.** 176 sweeps, numbered 1 to 176 without a gap, every one exactly 120.0 s after the previous. A sweep
  took 1.04 s at the median (0.94 s to 1.18 s).
- **Coverage.** Every sweep made its 20 snapshot calls, and all 3,520 chunks returned ok. Each sweep returned
  snapshots for 9,669 of the 9,683 watched names; the other 14 never returned one.
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

1. **Stop time.** The brief gives the stop as about 04:05 ET. The stop record says 04:00:04 ET, reason `stop_time`.
   04:05 ET is the thresholds' backstop for an external supervisor, and there was none.
2. **Code not on main.** The watch ran `dca569ae`, the pre-review version of #480, as described above.
3. **No systemd unit.** The watch was launched from an interactive shell. There is no unit journal, and the process's
   console output was not retained.

## Units

None. The watch ran without a systemd unit, and `systemctl --user list-unit-files` listed no overnight-volume unit on
2026-09-30. The start and stop come from the watch's own `start.json`, `stop.json` and `sweeps.jsonl`.

## Limitations

- **Data only.** The watch evaluates no strategy and qualifies no gate. The tiers are unvalidated monitoring
  thresholds.
- **One venue.** BOATS is one ATS, so its volume is indicative venue data, not consolidated volume. The fund tag misses
  some ETFs.
- **Code not on main.** It is retrievable through `refs/pull/480/head` and `6545d7ad`, not from main.
- **No unit, no console.** The key pair (account 1) is not recorded in the run's files.
- **No broker read.** The no-order statement rests on the code and the recorded calls.
- **Delivery unchecked.** Posts count as sent when the POST returned without an error.
- **Late start.** The first 130 minutes of the session were not swept.

## Paper lane row

No paper-lane row changes with this record. The watch is data only and placed no order.

## Files

| File | What it is |
|---|---|
| `receipt.json` | The run receipt: code identity and its public copy, main's differences, thresholds and plan, universe, sweeps, requests, errors, alerts, the no-order basis, private file hashes and field provenance |
| `README.md` | This summary |

Private and not committed:
- the watch's 6 output files and 176 snapshot files, derived from licensed market data;
- the alerted symbols and their measures, which stay in `alerts.jsonl`.
