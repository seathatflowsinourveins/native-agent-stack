# Incentive monitor and forward study

Records market-side and non-market-side incentive signals continuously, ranks an early-stage board, and feeds a
preregistered paper forward study. Data collection places no orders; the forward study trades only on Alpaca paper
through the adaptive engine's mover trial mode.

## Sources (entitlements measured 2026-09-24 with the paper key of an Algo Trader Plus user)

| Side | Source | Access | Measured |
| --- | --- | --- | --- |
| Market | SIP snapshots, every active tradable US equity | REST, 500 symbols per call | 13,191 symbols in about 27 calls; data limit header 10,000/min |
| Market | OPRA option trades, every contract | websocket `trades: ["*"]`, msgpack | about 920 trades/s at 10:18 ET |
| Market | Trade halts with reason codes | Nasdaq Trader RSS | 24 halts listed at 10:16 ET |
| Non-market | Benzinga news | websocket `news: ["*"]` | connected |
| Non-market | SEC EDGAR current filings (8-K, 6-K, Schedule 13D, SC TO-T, 425, S-1, 424B4) | Atom, declared contact (`SEC_USER_AGENT`) | 317 filings on the first sweep |

The SIP stock stream is not used here: a user may hold one connection per stream endpoint and the trading engine
needs it. EDGAR's `type` filter is a prefix match, so rows are kept by exact form; Form 4 is not polled because
the prefix `4` returns mostly other forms.

## Run

```sh
set -a; . "$SEC_CONTACT_ENV"; set +a     # SEC_USER_AGENT: the truthful declared contact, sent to SEC only
python monitor.py once --env-file ENV --out DIR   # one polled sweep, no streams
python monitor.py run  --env-file ENV --out DIR --until-et 20:00
```

Output (owner-only files under `DIR/<YYYYMMDD>/`): `news.jsonl`, `edgar.jsonl`, `halts.jsonl`,
`options-minute.jsonl` (per root and minute, by right and days-to-expiry bucket), `options-large.jsonl` (prints of
at least 100,000 USD premium), `snapshots/HHMMSS.json.gz` (rows whose last trade changed), `regime.jsonl` (breadth,
dispersion, 10% mover counts, index changes), `board.json` and `board.jsonl`, `monitor.jsonl` (sweeps, call counts,
stream health). Every record carries the monitor's receive time. The data stays private: it is licensed market data
and news.

## Board

`score()` adds fixed components: relative volume, news in the last 30 minutes, M&A filings (Schedule 13D, SC TO-T,
425), material 8-K items, dilution filings (negative), news or volatility halts, short-dated call premium and large
option prints. `early` means the price is within 10% of the reference close. The weights were fixed on 2026-09-24
without outcome data; the board is an unvalidated detector, never a strategy by itself.

## Forward study

[forward-protocol-v1.json](forward-protocol-v1.json) (`incentive-board-forward-v1-20260924`) is frozen before its first
order. At 10:30 and 13:30 ET, `board_scan.py` takes at most five early-stage names with a non-price incentive from a
fresh board, re-checks each with a fresh SIP snapshot, records 20 deterministic untraded controls, and writes the
engine's mover scan (`HH:MM|G0|V1000000|any`, exit X2, 200 USD per entry, 1x). The analysis waits for at least 20
sessions and 100 round trips. It is paper forward evidence only: the live gate also needs a historical holdout,
which this study cannot supply for its history-less components.

## Checks

`python3 -m unittest tests.test_incentive_monitor tests.test_incentive_forward` (synthetic fixtures; the engine's own
`mover.load_scan` must accept the bridge's scan).
