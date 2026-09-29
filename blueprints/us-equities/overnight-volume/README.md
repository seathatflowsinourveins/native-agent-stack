# Overnight volume watch (BOATS)

[`watch.py`](watch.py) watches the overnight session (20:00 to 04:00 ET) on the Blue Ocean ATS (BOATS). It covers every
overnight-tradable US equity and flags a name when its session volume stands out against:

- its SIP average daily volume;
- its own 20-session BOATS baseline;
- or its price has moved away from the prior regular close.

It only monitors:

- It makes no order, cancel or position call and no trading-API write.
- Every Alpaca request is a GET on an allow-list (paper trading `/v2/assets`; data `/v2/stocks/snapshots` and
  `/v2/stocks/bars`). Before it is made, it passes a per-source call budget (`monitor.Budget`) and a cap on all data
  calls in any minute. The only other request is the notify tier's POST to a loopback ntfy topic.
- It reads the PAPER key pair only, from the 0600 file that `PAPER_ENV_FILE` names in an interactive shell
  (`docs/secret-storage.md`), and never prints a key.

The thresholds are in [`thresholds-v1.json`](thresholds-v1.json): id `overnight-volume-watch-v1`, trade date
2026-09-29, sha256 `8287b858b3e12ee55d482fb4a98109267b17b8b6ca10bf46d5ad64f767c5dd2b`.

- The file was committed on its own before the first sweep.
- Any change needs a new id.
- `start.json` records the git HEAD and the sha256 of `watch.py`, `monitor.py` and the thresholds file that the
  process loaded.

## Documented facts

All six pages were fetched again on 2026-09-29 at 01:53Z and showed the same `updatedAt` values. The line numbers
below come from those copies.

| Fact | Source (updatedAt) |
| --- | --- |
| The overnight session runs 8:00 PM to 4:00 AM ET, from 8:00 PM ET Sunday to 4:00 AM ET Friday. It "technically occurs on the evening before the trade date". BOATS carries its executions and market data (L12, L18, L24-29). | [24/5 Trading, Trading API](https://docs.alpaca.markets/us/docs/245-trading-for-trading-api.md) (2026-07-07T14:20:23Z) |
| On the Algo Trader Plus plan, use feed=`boats` for snapshots and historical bars. The free plan uses feed=`overnight` (L41-63). Overnight orders are limit orders only, with TIF `day` or `gtc` (L79-80). `overnight_tradable` and `overnight_halted` are asset attributes (L130-131, L139). | same page |
| The session follows the NYSE holiday calendar: no overnight session runs before a full holiday (L31). | [24/5 Trading](https://docs.alpaca.markets/us/docs/245-trading.md) (2026-07-07T14:17:11Z) |
| The snapshot feed enum includes `boats` (Blue Ocean, overnight US) and `overnight` (L51, L181-182). | [Snapshots](https://docs.alpaca.markets/us/reference/stocksnapshots-1.md) (2026-05-27T17:58:03Z) |
| `overnight` is Alpaca's feed derived from BOATS. Its trades are 15 minutes delayed and adjusted to fit the bid-ask spread (L72). | [Historical Stock Data](https://docs.alpaca.markets/us/docs/historical-stock-data-1.md) (2026-02-11T05:30:13Z) |
| The streams are `v1beta1/boats` and `v1beta1/overnight` (L33-34). | [Real-time Stock Data](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data.md) (2026-05-18T07:19:29Z) |
| Extended-hours `T` trades and odd-lot `I` trades add daily volume only (L292, L302-303). VWAP counts only trades that update high/low and volume (L336-337). A bar is emitted only when no field is 0 (L339). | [Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq.md) (2026-09-21T05:18:36Z) |

## Observed semantics (2026-09-29 01:14:21Z)

These were read with read-only GETs and PAPER keys. The probe outputs are scratch files, not evidence, until they move
into a sanitized receipt.

- The BOATS snapshot `dailyBar.t` is `2026-09-29T00:00:00Z`. That keys it to the trade date, 20:00 ET the evening
  before, so the watch compares the UTC date of `dailyBar.t`. An ET date would place it on 2026-09-28.
- `prevDailyBar` is the previous overnight session (`2026-09-28T00:00:00Z`, SPY v 131,031), not a regular session. It
  is never used.
- feed=boats is real time on this plan: TSLA's last trade was under 1 s old, and every trade and quote was on venue B.
- feed=overnight also returns 200 here, but it is the delayed, derived feed (SPY daily v 15,203 against 24,128 on
  boats).
- SIP carries no overnight activity, and its daily close stays the regular close. So the reference close comes from
  SIP 1Day bars.
- BOATS 1Day bars come one per trade date at `T00:00:00Z`, with none dated on a weekend. A 1Day request also returns
  the in-progress trade-date bar, so the baseline keeps only the 20 SIP session dates.
- Inferred: the BOATS daily bar is keyed to the session and does not roll at ET midnight. The minute bars of one
  session straddle midnight. If SPY's `dailyBar.t` changes, the watch writes a `session_bar_rolled` record to
  `sweeps.jsonl`, so the first sweep after midnight observes this directly.
- v2/assets returns the overnight flags as strings inside `attributes`:
  - 13,495 names are tradable, 9,683 are overnight_tradable and 3,502 are overnight_halted;
  - none carries both flags.
- Rate limits: data 10,000 a minute, trading 200 a minute.

## Measures, tiers and budget

The measures are defined in `thresholds-v1.json`:

- `overnight_shares` is the BOATS `dailyBar.v` of tonight's session bar.
- Dollar volume is v times vw. It is approximate, because vw leaves out odd lots.
- `adv_fraction` compares overnight shares with the SIP ADV20, using `monitor.AdvLoader`'s formula (split-adjusted).
- `change` compares the BOATS close with the SIP close of 2026-09-28.
- `relvol_boats20` compares overnight shares with the BOATS 1Day volume over the 20 SIP sessions before the trade
  date, divided by 20. It counts only with at least 10 prior BOATS sessions.

Tiers and lists:

- **Significant:** at least $250k and any of 2% of ADV, 5% move or 5x relvol.
- **Notify:** at least $1M and any of 5% of ADV, 10% move or 10x relvol.
- Each name alerts once per tier.
- Only the notify tier is pushed: non-fund names, at most 5 a sweep and 40 a session.
- Two top-25 lists are written every sweep.

Call budget for 9,683 names:

- Start-up makes 99 calls: 1 assets call, 49 SIP 1Day calls and 49 BOATS 1Day calls.
- Each 120 s sweep makes 20 snapshot calls at once, or 10 a minute on average.
- The busiest minute has at most 118 data calls: the 98 daily-bar calls, then the first sweep's 20. The plan is refused
  above 500 (5% of 10,000), so a universe above 41,600 names is refused.
- While the watch runs, the budget refuses any data call beyond 500 in a rolling minute, daily bars and snapshots
  together.
- A sweep's first snapshot call is a probe. After an error or a rate-limited answer (fewer than 3,500 calls left, a
  429's headers included), the sweep makes no other call, and it checks the calls left again before each later call.
- `watch.py plan --symbols N` prints the plan without a network call.

## Commands

Run the commands from the repository root. `PYTHONDONTWRITEBYTECODE=1` keeps `__pycache__` out of the checkout.

```sh
# the plan: no network, no credentials
python3 blueprints/us-equities/overnight-volume/watch.py plan --symbols 9683

# smoke: start-up plus one sweep, never posts, prints counts only. Use a scratch --out, never the run's directory.
bash -ic 'PYTHONDONTWRITEBYTECODE=1 python3 blueprints/us-equities/overnight-volume/watch.py once \
  --env-file "$PAPER_ENV_FILE" --out "/var/tmp/ovw-once-$(date +%H%M%S)"'

# launch: a sweep every 120 s until 04:00 ET on 2026-09-29 (backstop 04:05 ET for an external supervisor)
bash -ic 'PYTHONDONTWRITEBYTECODE=1 python3 blueprints/us-equities/overnight-volume/watch.py run \
  --env-file "$PAPER_ENV_FILE" --out "$HOME/.local/state/native-agent-stack/overnight-volume/20260929"'
```

To stop before 04:00 ET, run `touch "$OUT/STOP"` or send SIGTERM. Both write `stop.json`.

- Between sweeps, SIGTERM takes effect at once and the STOP file within 5 s.
- Start-up checks both before every request and ends a retry wait early. It also ends at its 600 s deadline
  (`startup_deadline`, exit code 1).
- A request in flight is never interrupted. Each blocking read has a 20 s timeout, so a stop can wait that long for
  it. A sweep in progress finishes its snapshot calls first (20 at 9,683 names, three at a time).

`--no-push` records notify alerts without posting them, and it holds back queued alerts restored from an earlier run.
A restart on the same `--out` restores what was already alerted and pushed from `alerts.jsonl`, so nothing alerts or
posts twice. Each push attempt is written to disk before it is posted, so a crash can lose a notice but never repeat
it. Dry-run records are never restored.

Read-back:

```sh
OUT="$HOME/.local/state/native-agent-stack/overnight-volume/20260929"
jq -c 'select(.event=="sweep") | {sweep, at, with_overnight_volume, significant, notify, new_alerts, pushes, calls}' "$OUT/sweeps.jsonl" | tail -n 3
jq -r 'select(.event=="alert") | [.at, .tier, .s, .overnight_dollar_volume, .adv_fraction, .change, .relvol_boats20] | @tsv' "$OUT/alerts.jsonl"
jq '.top' "$OUT/board.json"
curl -s 'http://127.0.0.1:18080/overnight-volume/json?poll=1'   # the ntfy topic
```

## Output files

All files live in the one `--out` directory: owner-only 0600 files in 0700 directories, as `monitor.Sink` writes
them. The watch refuses an `--out` inside a git worktree (a `.git` entry at or above it, symlinks resolved) before it
creates a file or makes a request.

| File | Contents |
| --- | --- |
| `start.json` | Git HEAD, code and thresholds sha256, the plan, universe and reference coverage, and the restored counts |
| `sweeps.jsonl` | One record a sweep: each chunk's status, calls, rate-limit remaining, counts, new alerts and pushes. Also start, stop, `sweep_error` and `session_bar_rolled` records |
| `alerts.jsonl` | The first crossing per symbol and tier, with every measure. Each push attempt (`push`, fsynced before the post) and its result (`push_result`: sent or failed) |
| `top.jsonl` | Both top-25 lists, every sweep |
| `board.json` | The latest state, replaced atomically |
| `snapshots/HHMMSS.json.gz` | The raw BOATS snapshots of every name with a session bar (point-in-time record, ET time of the sweep) |
| `stop.json` | The stop reason (`stop_time`, `stop_file`, `sigterm`, `once`, `refused`, `error`, `startup_deadline`) and totals |

Pushes go to the observability stack's loopback ntfy topic `http://127.0.0.1:18080/overnight-volume`, which is
separate from Alertmanager's `ecosystem-alerts`.

- The URL rule and the POST are mirrored from `scripts/host_requests.py` (`check_notify_url`, `send_notice`). The tests
  compare the URL rule with the original.
- A failed post is recorded and never stops a sweep.

## Claim boundaries

- BOATS is one ATS. Its volume is indicative venue data, not consolidated volume.
- ADV20 and the reference close are split-adjusted SIP values. The BOATS baseline is unadjusted, as calibrated, so a
  split inside the 20-session window distorts `relvol_boats20`.
- The fund tag (`monitor.FUND_NAME` on asset names) misses some ETFs.
- The tiers are unvalidated monitoring thresholds, not a trading rule. Their calibration counts cover five earlier
  nights, taken from full-session totals.
- The files record what was received and when. They make no historical-availability claim.
- Overnight order behaviour on paper accounts is not verified. The documentation describes limit orders with TIF
  `day` or `gtc`, and says nothing about paper accounts.

## Checks

```sh
TMPDIR=/var/tmp PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_overnight_volume
git diff --quiet origin/main -- blueprints/us-equities/incentive-monitor/monitor.py \
  blueprints/us-equities/incentive-monitor/board_scan.py blueprints/us-equities/broad-universe/scan.py
```

This watch edits none of those three files. `broad-universe/scan.py` is evidence-pinned in `manifests/evidence.json`.
`monitor.py` and `board_scan.py` are live code identities of the incentive monitor.
