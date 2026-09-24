# Incentive monitor and forward study

Records market-side and non-market-side incentive signals continuously, ranks an early-stage board, and feeds a
preregistered paper forward study. Data collection places no orders; the forward study trades only on Alpaca paper
through the adaptive engine's mover trial mode.

## Sources (entitlements measured 2026-09-24 with the paper key of an Algo Trader Plus user)

| Side | Source | Access | Measured |
| --- | --- | --- | --- |
| Market | SIP snapshots, every active tradable US equity | REST, 500 symbols per call | 13,191 symbols in about 27 calls; data limit header 10,000/min |
| Market | OPRA option trades, every contract | websocket `trades: ["*"]`, msgpack | about 920 trades/s at 10:18 ET |
| Market | Trading status, LULD bands, imbalances, every symbol | IEX stock stream `v2/iex`, `statuses`/`lulds`/`imbalances: ["*"]` | 900 s capture: statuses and LULD identical to `v2/sip` (6 and 1,457 messages); imbalances on `v2/sip` only |
| Market | Screener: most actives by volume and by trades (top 100 each), movers (top 50 each side) | REST, 3 calls per sweep | docs only |
| Market | Option chain snapshots (implied volatility, greeks, quotes) for the top 25 board candidates | REST, 1 page of at most 1,000 contracts per root per sweep | docs only |
| Market | Option open interest per contract | trading API `/v2/options/contracts`, once per root per day | docs only |
| Market | Trade halts with reason codes | Nasdaq Trader RSS, at most once a minute | 24 halts listed at 10:16 ET; tens of seconds behind the status stream |
| Non-market | Benzinga news | websocket `news: ["*"]` | connected |
| Non-market | SEC EDGAR current filings (8-K, 6-K, Schedule 13D, SC TO-T, 425, S-1, 424B4) | Atom, declared contact (`SEC_USER_AGENT`) | 317 filings on the first sweep |
| Non-market | Corporate-action events (every type, insert/update/delete) | Server-Sent Events on `stream.data.alpaca.markets/v1beta1/events/corporate-actions` | host answered 200 (the data host 404); replay back to 2026-07-09 |
| Non-market | FINRA daily short sale volume (consolidated NMS file) | `cdn.finra.org`, once a day after 18:05 ET | docs only; posted by 18:00 ET on the trade date |

The SIP stock stream `v2/sip` is left to the trading engine: a user may hold one connection per stream endpoint
(406 "connection limit exceeded"). On the development host (checked 2026-09-24) the scheduled engine sessions (mover
paper, forward decisions) use `feed: sip` and the capacity soak and scans are REST only; `adaptive-paper/config.json`
is the only `iex` config in the repository. The monitor holds a host lease file per stream endpoint (`--lease-dir`,
default `$XDG_RUNTIME_DIR/alpaca-stream-leases`), so a second monitor refuses a held endpoint before connecting, and a
406 on the IEX endpoint waits 15 minutes (`--iex-conflict-wait`) instead of contending. The engine takes no lease:
run the monitor with `--no-iex-status` on a day an `iex` engine config is scheduled. EDGAR's `type` filter is a prefix
match, so rows are kept by exact form; Form 4 is not polled because the prefix `4` returns mostly other forms.

Trading status coverage. The docs say the status messages "can be accessed from any {source} depending on your
subscription" and that production keys need sales enablement. The only native capture (900 s, paper key) saw status
messages for tape C alone, identical on both endpoints; CTA (tapes A and B) statuses on IEX are unobserved, not
disproven. The monitor counts every stream message by type and tape (`iex_tapes` in each sweep of `monitor.jsonl`)
so the first full session settles coverage, and the Nasdaq RSS stays merged into the halt state either way. The
stream sends changes only (no snapshot on subscribe): a halt that began before the connection is known from the RSS.

## Call budget

Every REST source has an explicit cap per sweep (start-up loads a cap per process). A call over its cap is refused
before any request, and a source without a cap is refused. The plan is written to `monitor.jsonl` at start (event
`budget`); each sweep records its calls per source (`source_calls`), the caps (`budget_per_sweep`), refusals
(`budget_refused`) and the last rate-limit headers. The monitor exits with code 2, before any sweep, when the plan
breaks a rule: data REST calls above 5% of the 10,000/min data limit (steady rate plus the one-off daily-bar load in
the first minute), trading REST calls above 5% of the 200/min trading limit, or the Nasdaq RSS polled more than once a
minute. With the defaults (20 s sweeps, about 13,500 symbols):

| Source | API | Per sweep | Per minute |
| --- | --- | --- | --- |
| SIP snapshots | data | 27 | 81 |
| Screener | data | 3 | 9 |
| Option chains (25 roots x 1 page) | data | 25 | 75 |
| Daily bars for relative volume | data | 68 once at start | 233 in the first minute, all data sources |
| Option contracts (open interest) | trading | 2 | 6, plus 1 assets call at start (cap 10) |
| EDGAR (7 forms) | sec.gov | 7 | 21 (SEC fair access: 10 per second) |
| Nasdaq halts RSS | nasdaqtrader.com | 1 every 60 s | 1 |
| FINRA file | cdn.finra.org | 1 | at most one new file a day; a missing file is retried hourly |
| Corporate-action stream | stream host | 2 connects/min (endpoint limit header 20) | 1 bounded context replay at start |

Optional data sources (screener, option chains) pause for a sweep while the data API reports fewer than 3,500 calls
left in its window.

## Run

```sh
set -a; . "$SEC_CONTACT_ENV"; set +a     # SEC_USER_AGENT: the truthful declared contact, sent to SEC only
python monitor.py once --env-file ENV --out DIR   # one polled sweep, no streams (the corporate-action context replay runs)
python monitor.py run  --env-file ENV --out DIR --until-et 20:00 [--sweep-seconds 20] [--no-option-chains ...]
```

Output (owner-only files under `DIR/<YYYYMMDD>/`): `news.jsonl`, `edgar.jsonl`, `halts.jsonl`,
`options-minute.jsonl` (per root and sweep interval, labelled `drained_at`, by right and days-to-expiry bucket), `options-large.jsonl` (prints of
at least 100,000 USD premium), `snapshots/HHMMSS.json.gz` (rows whose last trade changed), `regime.jsonl` (breadth,
dispersion, 10% mover counts, index changes), `board.json` and `board.jsonl` (board version 1), `board-v2.json` and
`board-v2.jsonl`, `status.jsonl`, `luld.jsonl` and `imbalance.jsonl` (IEX stream), `halt-state.json` (the merged halt
state), `corporate-actions.jsonl` (every event as received, deduplicated by event id), `screener.jsonl`,
`options-iv.jsonl` (per root and sweep: near-the-money implied volatility of the first expiry at least 7 days out, the
contracts around it with greeks and quotes, day call and put volume), `options-oi.jsonl` (per root and day),
`monitor.jsonl` (budget, sweeps, call counts, stream health). FINRA files are kept once under `DIR/finra/` with a
manifest (receive time, sha256, rows). Every record carries the monitor's receive time. The data stays private: it is
licensed market data and news, and FINRA's data is for non-commercial use.

After a restart the monitor rebuilds the session's filings, news window, option totals, merged halt state, LULD
bands, implied-volatility baselines and open interest from its own files; the corporate-action stream resumes from
the newest archived event id (`Last-Event-Id`, inclusive, so the redelivered event is dropped), or from the start of
the day when nothing is archived or the last id is more than 7 days old.

## Board

Board version 1 (`board.json`, the forward study's). `score()` adds fixed components: relative volume, distinct news
articles in the last 30 minutes, M&A filings (Schedule 13D, SC TO-T, 425) credited to the subject company only,
material 8-K items, dilution filings (negative), today's news or volatility halts (Nasdaq RSS), short-dated call premium
and large option prints (option roots mapped to equities, including adjusted and class roots). The board's `early`
label means the price is within 10% of the reference close in either direction. `board.json` also lists every symbol
with any non-price component (`incentive_symbols`) and the monitor's start time, restored counts and stream downtime.
The weights were fixed on 2026-09-24 without outcome data; the board is an unvalidated detector, never a strategy by
itself.

Board version 2 (`board-v2.json`). Every version 1 component and weight is unchanged (`score_v1` keeps the version 1
score), the threshold stays 2, and these components are added, fixed on 2026-09-24 without outcome data and
unvalidated (the board stays a detector to be tested prospectively; `rules_v2` in the file states each rule):

| Component | Weight | Rule | Non-price |
| --- | --- | --- | --- |
| `stream_news_halt` | 2.0 | the status stream showed a news halt today (UTP T1 T2 T3 T12 H10 H11, CTA P D A C) and the RSS has no news halt for the name | yes |
| `stream_volatility_halt` | 1.0 | the status stream showed a volatility pause today (UTP LUDP LUDS T5 T7, CTA M), no news halt, and no RSS halt of any kind | no |
| `corporate_action` | 0.5 | a split, merger, spin-off or name/symbol change dated from yesterday to 10 days ahead, or first inserted today | yes |
| `iv_runup` | 1.0 | near-the-money IV up at least 20% on its baseline (the previous session's last value for the same expiry, else the first value today from 09:45 ET), baseline at least 30 minutes old | yes |
| `short_volume_high` | 0.5 | the latest FINRA short sale volume ratio at least 0.80 on at least 200,000 reported off-exchange shares | no |

Stream halt parts only add what the RSS lacks, so one halt is never counted twice. Each version 2 row carries
`context`: the merged halt state, the LULD band and the distance to it, corporate actions (type, role, date, terms),
screener ranks, implied-volatility change and open interest, and the FINRA row (with the mean ratio over up to five
earlier stored files). Limitations: implied volatility is sampled only for the top 25 candidates by the version 1
score, so a run-up that began before a root entered that set is invisible until the next session; the FINRA ratio
uses off-exchange volume only and is a day old during the session; corporate-action context comes from a 30-day
replay at start plus the live stream.

## Forward study

[forward-protocol-v1.json](forward-protocol-v1.json) (`incentive-board-forward-v1-20260924`) is frozen before its first
order and was amended before that order after an independent review (its `amendments_before_first_order`). At 10:30
and 13:30 ET (refused after 13:35 or 10:35), `board_scan.py` takes at most five names with a non-price incentive
whose fresh SIP snapshot is 0-10% above the reference close, records four untraded incentive-free controls per name
from the same gain bucket, writes a selection record with the sha256 of the code, protocol, pinned config
([config-forward-1030.json](config-forward-1030.json), [config-forward-1330.json](config-forward-1330.json)) and scan,
and then the engine's mover scan. Selection and controls are limited to operating companies (SEC company tickers, less
registered funds and fund-like asset names); a session's two decisions never share a control; the ledger holds one
exclusive record per decision (no re-rolls) and a record for every refusal. The scan uses the rule `HH:MM|G0|V1000000|any`,
exit X2, 200 USD per entry and 1x. The analysis runs once,
after the first trading day with at least 20 sessions and 100 round trips. It is paper forward evidence only: the live gate also needs a historical holdout,
which this study cannot supply for its history-less components.

Protocol v1 runs on board version 1: `board_scan.py` refuses (`board_version_mismatch`) any board whose
`board_version` is missing or differs, so `board-v2.json` can never feed it. The frozen protocol file is unchanged
(its pin lives in `board_scan.py`). Deploying this monitor and bridge changes the sha256 of `monitor.py` and
`board_scan.py` that every decision record binds, which under the protocol's own stop rule starts a new protocol
version: keep the running study on its deployed copy until it is retired or a version 2 protocol is approved.

## Checks

`python3 -m unittest tests.test_incentive_monitor tests.test_incentive_forward` (synthetic fixtures, no network; one
test runs a whole `once` sweep against a synthetic response router; the engine's own `mover.load_scan` must accept the
bridge's scan). The monitor has not been run against the live endpoints with the version 2 sources.
