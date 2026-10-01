# Incentive monitor and forward study

Records market-side and non-market-side incentive signals continuously, ranks an early-stage board, and feeds a
preregistered paper forward study. Data collection places no orders; the forward study trades only on Alpaca paper
through the adaptive engine's mover trial mode.

## Sources (entitlements measured 2026-09-24 with the paper key of an Algo Trader Plus user)

| Side | Source | Access | Measured |
| --- | --- | --- | --- |
| Market | SIP snapshots, every active tradable US equity | REST, 500 symbols per call | 13,191 symbols in about 27 calls; data limit header 10,000/min |
| Market | OPRA option trades, every contract | websocket `trades: ["*"]`, msgpack | about 920 trades/s at 10:18 ET |
| Market | Trading status, LULD bands, imbalances, every symbol | IEX stock stream `v2/iex`, `statuses`/`lulds`/`imbalances: ["*"]`, only with `--iex-status` | 900 s capture: statuses and LULD identical to `v2/sip` (6 and 1,457 messages); imbalances on `v2/sip` only |
| Market | Screener: most actives by volume and by trades (top 100 each), movers (top 50 each side) | REST, 3 calls per sweep | docs only |
| Market | Option chain snapshots (implied volatility, greeks, quotes) for the top 25 board candidates, 09:45-16:00 ET | REST, 1 page of at most 1,000 contracts per root per sweep, expiries 7-42 days out | docs only |
| Market | Option open interest per contract | trading API `/v2/options/contracts`, once per root per day, only with `--option-oi` | docs only |
| Market | Trade halts with reason codes | Nasdaq Trader RSS, at most once a minute | 24 halts listed at 10:16 ET; tens of seconds behind the status stream |
| Non-market | Benzinga news | websocket `news: ["*"]` | connected |
| Non-market | SEC EDGAR current filings (8-K, 6-K, Schedule 13D, SC TO-T, 425, S-1, 424B4) | Atom, declared contact (`SEC_USER_AGENT`) | 317 filings on the first sweep |
| Non-market | Corporate-action events (every type and region, insert/update/delete) | Server-Sent Events on `stream.data.alpaca.markets/v1beta1/events/corporate-actions` | host answered 200 (the data host 404); replay back to 2026-07-09; 12,000-54,000 events a day, almost all cash-dividend updates |
| Non-market | FINRA daily short sale volume (consolidated NMS file) | `cdn.finra.org`, once a day after 18:05 ET, once more after the next publication | docs only; posted by 18:00 ET on the trade date, "in rare instances" updated on a later day |

Coexistence. Alpaca allows one connection per stream endpoint (406 "connection limit exceeded") and Nasdaq one RSS
request a minute. The version 1 monitor that feeds the forward study holds news and OPRA, polls EDGAR and the RSS, and
takes no lease. Version 2 therefore declares its role on every run: beside a running version 1 monitor it must run as
a follower (`--follow-v1 V1_OUT`, V1_OUT being version 1's `--out`), which holds no news or OPRA connection, polls
neither EDGAR nor the RSS (their budgets are zero, so any such call is refused), reads those inputs from the complete
lines version 1 appends to today's `news`, `edgar`, `halts`, `options-minute` and `options-large` files, records version
1's last heartbeat (`follow_v1_heartbeat`), writes `board-v2.json` only and never writes to V1_OUT. `--standalone`
states that no version 1 monitor runs on the account; version 2 must not otherwise run beside version 1. A standalone
run refuses to start (exit 2, `v1_monitor_running_use_follow_v1`) while a version 1 monitor runs on this host, found
from `/proc` (a `monitor.py run` process running the frozen file or given version 1's arguments); on another host of
the same account the declaration is the only guard. The follower still makes its own SIP snapshot calls (27 per sweep)
beside version 1's.

The SIP stock stream `v2/sip` is left to the trading engine. On the development host (checked 2026-09-24) the scheduled
engine sessions (mover paper, forward decisions) use `feed: sip` and the capacity soak and scans are REST only;
`adaptive-paper/config.json` is the only `iex` config in the repository. The IEX stream is opt-in (`--iex-status`), and
is refused while any declared scheduled engine config (`--engine-config`, repeatable) streams `feed: iex` or cannot be
read. The monitor holds a host lease file per stream endpoint in one fixed directory per user
(`~/.cache/alpaca-stream-leases` from the password database, whatever `XDG_RUNTIME_DIR` or `HOME` say, so cron, systemd
and shells agree; `--lease-dir` overrides), so a second version 2 monitor refuses a held endpoint before connecting; a
406 on the IEX endpoint waits 15 minutes (`--iex-conflict-wait`) instead of contending. A stream's reconnect backoff
resets only after a data message or 60 s connected (the welcome batch before a 406 does not reset it), and 402, 405,
409 and 410 stop that stream for the run. The leases are per host; the engine and version 1 take none. EDGAR's `type`
filter is a prefix match, so rows are kept by exact form; Form 4 is not polled because the prefix `4` returns mostly
other forms.

Trading status coverage. The docs say the status messages "can be accessed from any {source} depending on your
subscription" and that production keys need sales enablement. The only native capture (900 s, paper key) saw status
messages for tape C alone, identical on both endpoints; CTA (tapes A and B) statuses on IEX are unobserved, not
disproven. The monitor counts every stream message by type and tape (`iex_tapes` in each sweep of `monitor.jsonl`)
so the first full session settles coverage, and the Nasdaq RSS stays merged into the halt state either way. The
stream sends changes only (no snapshot on subscribe): a halt that began before the connection is known from the RSS.

## Call budget

Every REST source has an explicit cap: per sweep for polled sources, per rolling minute for the daily-bar load, per
process for start-up loads. A call over its cap is refused before any request, and a source without a cap is refused.
The plan is written to `monitor.jsonl` at start (event `budget`); each sweep records its calls per source
(`source_calls`), the caps (`budget_per_sweep`), refusals (`budget_refused`) and the last rate-limit headers. The
monitor exits with code 2, before any sweep, when the plan breaks a rule or a bound is invalid (for example a
non-positive interval): data REST calls above 5% of the 10,000/min data limit in any minute (the steady rate plus one
full daily-bar pass), trading REST calls above 5% of the 200/min trading limit, or the Nasdaq RSS polled more than once
a minute. With the defaults (20 s sweeps, about 13,500 symbols, standalone):

| Source | API | Per sweep | Per minute |
| --- | --- | --- | --- |
| SIP snapshots | data | 27 | 81 |
| Screener | data | 3 | 9 |
| Option chains (25 roots x 1 page, plus up to 5 band-less retries) | data | 30 | 90; none outside 09:45-16:00 ET |
| Daily bars for relative volume | data | 68 in any minute, until loaded | at most 248 in any minute, all data sources |
| Option contracts (open interest, `--option-oi` only) | trading | 2 | 6, plus 1 assets call at start (cap 10) |
| EDGAR (7 forms; none as a follower) | sec.gov | 7 | 21 (SEC fair access: 10 per second) |
| Nasdaq halts RSS (none as a follower) | nasdaqtrader.com | 1 every 60 s | 1 |
| FINRA file | cdn.finra.org | 1 | at most one new file a day and one update check per file; any failure waits an hour |
| Corporate-action stream | stream host | 2 connects/min (endpoint limit header 20), the context replay included | 1 context replay at start (90 s deadline) |

Optional data sources (screener, option chains) pause for a sweep while the data API reports fewer than 3,500 calls
left in its window; open-interest calls pause while the trading API reports fewer than 100 of its 200. A failed
daily-bar load resumes at the failed request (the per-minute cap bounds its retries), so relative volume keeps being
retried all day without repeating finished requests. Option chains and open interest read with a 10 s timeout, and a
sweep waits at most one sweep interval (10 s minimum) for its chains; the rest are asked again next sweep.

## Run

```sh
set -a; . "$SEC_CONTACT_ENV"; set +a     # SEC_USER_AGENT: the truthful declared contact, sent to SEC only
python monitor.py once --standalone --env-file ENV --out DIR   # one polled sweep, no streams (the corporate-action context replay runs)
python monitor.py run  --standalone --env-file ENV --out DIR --until-et 20:00 [--sweep-seconds 20] [--iex-status --engine-config CFG ...]
python monitor.py run  --follow-v1 V1_OUT --env-file ENV --out DIR2   # beside the running version 1 monitor
```

Output (owner-only files under `DIR/<YYYYMMDD>/`): `news.jsonl`, `edgar.jsonl`, `halts.jsonl`,
`options-minute.jsonl` (per root and sweep interval, labelled `drained_at`, by right and days-to-expiry bucket), `options-large.jsonl` (prints of
at least 100,000 USD premium), `snapshots/HHMMSS.json.gz` (rows whose last trade changed), `regime.jsonl` (breadth,
dispersion, 10% mover counts, index changes), `board.json` and `board.jsonl` (board version 1), `board-v2.json` and
`board-v2.jsonl`, `status.jsonl`, `luld.jsonl` and `imbalance.jsonl` (IEX stream), `halt-state.json` (the merged halt
state), `corporate-actions.jsonl` (every event as received, deduplicated by event id), `screener.jsonl`,
`options-iv.jsonl` (per root and sweep: near-the-money implied volatility of the first expiry 7 to 42 days out, the
contracts around it with greeks and quotes, day call and put volume, whether the strike band was used),
`options-oi.jsonl` (per root and day), `monitor.jsonl` (budget, sweeps, call counts, stream health). A follower writes
no `board.json`, `news.jsonl`, `edgar.jsonl`, `halts.jsonl` or option-trade files (those are version 1's). FINRA files
are kept once under `DIR/finra/` with a manifest (receive time, sha256, rows, update check); a file that changed on its
update check replaces the stored one and the earlier version stays under `DIR/finra/superseded/`. Every record carries
the monitor's receive time. The data stays private: it is licensed market data and news, and FINRA's data is for
non-commercial use.

After a restart the monitor rebuilds the session's filings, news window, option totals, merged halt state, LULD
bands, implied-volatility baselines and open interest from its own files (a follower re-reads version 1's files from
their start). The corporate-action stream resumes from the newest archived event id whatever its age (`Last-Event-Id`,
inclusive, so the redelivered event is dropped); when that id is not redelivered, the first newer event is recorded as
`ca_resume_gap`, since events between may be lost. An empty archive starts from the earliest event the server still
replays (2026-07-09 when probed on 2026-09-24; about 12,000-54,000 events a day, so the first start writes the whole
retained history once), or from `--ca-archive-since` (`today` or an RFC 3339 time).

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
| `stream_news_halt` | 2.0 | the status stream showed a news halt today (UTP T1 T2 T3 T12 H10 H11, CTA P D A C) and the RSS has no news halt for the name; it replaces version 1's `volatility_halt` | yes |
| `stream_volatility_halt` | 1.0 | the status stream showed a volatility pause today (UTP LUDP LUDS T5 T7, CTA M), no news halt, and no RSS halt of any kind today | no |
| `corporate_action` | 0.5 | a US-region split, merger, spin-off or name/symbol change dated from yesterday to 10 days ahead, or whose first insert event is from today (its later updates keep it) | yes |
| `iv_runup` | 1.0 | near-the-money IV of the first expiry 7 to 42 days out, sampled 09:45-16:00 ET with the latest sample at most two sweeps old, up at least 20% on its baseline for the same expiry (the previous session's last sample by 16:00 ET, else the first sample today), baseline at least 30 minutes old | yes |
| `short_volume_high` | 0.5 | the latest FINRA short sale volume ratio at least 0.80 on at least 200,000 reported off-exchange shares | no |

Halts keep version 1's precedence across both sources: one halt component per name, a news halt over a volatility
halt, so a halt is never counted twice (a stream news halt seen before the RSS lists it replaces version 1's
`volatility_halt`, and the row's `context.superseded_v1_parts` says so). Both boards come from one scoring pass per
sweep, so each version 2 row's `score_v1` and version 1 parts are exactly `board.json`'s for the same `at`; a symbol
that only a version 2 source makes a candidate after that pass joins at the next sweep. Board version 1 is written
before any version 2 work, and a version 2 failure is recorded (`board_v2_error`) without stopping board version 1.
Each version 2 row carries `context`: the merged halt state, the LULD band and the distance to it, corporate actions
(type, role, date, first insert, terms), screener ranks, implied-volatility change (with the latest sample's and the
baseline's times) and open interest, and the FINRA row (with the mean ratio over up to five earlier stored files).

Limitations: implied volatility is sampled only for the top 25 candidates by the version 1 score, so a run-up that
began before a root entered that set is invisible until the next session; the option session window is fixed at
09:45-16:00 ET, so on an early-close day samples after the options close are stale; a truncated chain page is taken
to start at the first expiry (pages are expected in contract-symbol order, not documented); the FINRA ratio uses
off-exchange volume only and is a day old during the session, and an update posted under another file name is not
seen; corporate-action context comes from a 30-day replay at start plus the live stream; a follower's merged halt
state has only today's RSS halts (version 1's files), not a halt still in force from an earlier day.

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
(its pin lives in `board_scan.py`). Protocol v1 is bound to its frozen code, `monitor.py` and `board_scan.py` of
05c28491 (sha256 pinned in `monitor.FROZEN_V1`): this bridge refuses every protocol v1 decision (`code_not_frozen`)
because its own code is not that code, and this monitor refuses to start (exit 2, `beside_frozen_v1_bridge`) beside the
frozen bridge, so copying it into the study's deployed directory cannot make v1-labelled decisions run on new code.
Under the protocol's own stop rule a code change starts a new protocol version: keep the running study on its deployed
copy until it is retired or a version 2 protocol is approved, and run this monitor beside it only as a follower.

**Engine binding gap (trading lane, 2026-09-25).** Each decision record hashes only the engine files listed in
`board_scan.ENGINE_FILES`: `mover.py`, `mover_runner.py`, `mover_strategy.py`, `safety.py`, `runner.py`,
`native_adapter.py`, `transport.py` and `mover-early-entry/rules.py`.

Measured on `main` after #187, the transitive import closure of `mover_runner.py` within `adaptive-paper/` has 14
further modules that the list omits:
- existed when v1 froze (05c28491) and have changed since: `leverage`, `mover_simulation`, `native_strategy` and
  `sessions`;
- existed then, unchanged since: `exits`, `feeds`, `recovery`, `selector`, `strategies` and `strategies_v1`;
- added after the freeze: `corporate_actions`, `credential_guard`, `credential_source` and `financing`.

A v1 record therefore cannot show which code of those modules ran. The v1 bridge is frozen, so the gap stays in v1 as
a recorded limitation.

No v1 order has been placed. Because the engine changed after v1 froze, a v1 start on the P0 engine would be a new
engine under the frozen label. Protocol v2, which pairs board v2 with the P0 engine, should close the gap before its
pre-outcome review. It can bind the whole engine, for example:
- the sha256 of every `*.py` in `blueprints/us-equities/adaptive-paper/` plus `mover-early-entry/rules.py`; or
- the git tree hash of those directories, taken from a clean checkout;

together with the pinned runtime lock.

## Checks

`python3 -m unittest tests.test_incentive_monitor tests.test_incentive_forward` (synthetic fixtures, no network: whole
`once` sweeps and short `run` loops, standalone and follower, run against a synthetic response router with fake stream
modules; the engine's own `mover.load_scan` must accept the bridge's scan). The monitor has not been run against the
live endpoints with the version 2 sources.
