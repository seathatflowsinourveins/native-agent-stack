# Mover trial mode (protocol `mover-early-entry-v1-20260924`, paper_e2e)

A bounded paper trial that enters up to five scanner-selected movers at trial start
and exits them by one protocol rule. The historical study picks the rule and exit, so
the trial is parameterised by `mover.rule` and `mover.exit` in the config. Modules:

| File | Role |
| --- | --- |
| `mover.py` | Pure logic: config and scan validation, sizing, marketable-limit pricing, X1-X4, the per-symbol order state machine (`MoverBook`) |
| `mover_strategy.py` | NautilusTrader strategy shell that executes the book's actions |
| `mover_runner.py` | `check` / `paper` / `recover` / `synthetic` commands and the native trial loop |
| `mover_simulation.py` | Synthetic broker port (scripted quotes, resting limits, partial fills) |
| `config-mover.json` | Example: pre-market only, trial end 09:25 ET, exit X2, rung 1, conservative caps |

Nothing in the adaptive lane changed. A mover trial reuses the engine as is: the
paper-only endpoint gate, `runner.credentials`, `transport.preflight`,
`runner.validate_preflight` (flat account, no open orders, tradable universe, fresh
benchmark quote, session window), `safety.Ledger`/`RiskLimits` (every order is
reserved and capped there), `runner.Controller`, `transport.AlpacaPaperTransport`,
`native_adapter.build_node`, `runner.reconcile`, `recovery.recover` and the shared
`STOP` kill switch.

## Scanner file

The coordinator's scanner writes JSON; the trial records its SHA-256 and refuses a scan
older than `max_scan_age_seconds` (at most 300 s) at trial start, a scan stamped in the
future or before the rule's HH:MM, a rule string other than the config's, more than
five symbols, and any row that fails its own rule.

```json
{"schema_version": 1, "kind": "mover_scan", "protocol": "mover-early-entry-v1-20260924",
 "rule": "08:00|G20|V1000000|any", "scan_time": "2026-09-24T12:00:05Z",
 "regime": {"factor": "1", "inputs": {"spy_prev_close": "661.2", "spy_sma20": "650.1",
            "spy_rv20": "0.11", "spy_rv20_median252": "0.14"}},
 "symbols": [{"symbol": "ABCD", "rank": 1, "price_at_t": "3.21", "dollar_volume_at_t": "12500000",
              "entry_bar_dollar_volume": "450000", "gain_pct_at_t": "45.2", "news_before_t": true}]}
```

- Rule `HH:MM|G<gain>|V<dollar volume>|<any|news_before_t>`. G is in percent points and
  V in USD; V may use a K, M or B suffix. `dollar_volume_at_t` must reach V. When
  `gain_pct_at_t` is supplied it must reach G, and `news_before_t` rules need `"news_before_t": true`.
- `entry_bar_dollar_volume` is required but may be `null`. `regime` is optional.
  With the four inputs, the factor is recomputed: 1 when the previous close is above the
  20-session mean and 20-session realised volatility is below its 252-session median,
  else 0.5. A declared factor that disagrees is refused. A lone `factor` is accepted as
  precomputed. An absent block gives 0.5. The engine does not fetch history.

## Sizing (deterministic, in code)

`notional_i = equity x L_i / 5`, with `L = min(4, rung x regime_factor x drawdown_factor)`.
Below 5 USD, `L_i = min(L, 1)`. Equity is `capital_usd` plus the mover ledger's realized
P&L, never the account balance. The drawdown factor comes from the lane's equity peak:
1 within 10%, 0.5 within 10-20%, and beyond 20% no entries for this and the next nine
sessions. Each notional is capped, in scan rank order, at:

- 1% of `dollar_volume_at_t`;
- 10% of `entry_bar_dollar_volume`;
- the ledger per-order cap;
- the remaining gross budget, `min(max_gross_exposure_usd / appreciation_allowance, equity x ledger leverage envelope)`.

A symbol whose price times the allowance exceeds the per-order cap is skipped; see
below. Rungs come from `rung_schedule` (sessions 1-20 at rung 1 in the example); a
session beyond the schedule is refused. A rung above 1 needs the canonical
`leverage_policy` block, whose PRE and POST cells cap the ledger at 1x.

## Orders

- **Entry.** One buy per symbol at trial start, as a marketable limit:
  `ask x (1 + entry cap)`, rounded down to the tick, whole shares, TIF day. The
  adapter sets `extended_hours` in PRE and POST. The buy waits, within
  `entry.window_seconds`, for a fresh, unhalted quote with an admissible spread and
  fresh marks on held symbols. Any unfilled remainder is canceled after
  `entry.timeout_seconds`. A buy is never re-priced or re-sent, even after a refusal.
- **Exits** run on every quote and on the runner's 0.1 s tick:
  - X1 at 15:58 ET;
  - X2 60 minutes after the first fill;
  - X3 when the bid is at or below 0.85 x the running high since entry;
  - X4 when the bid is at or below 0.85 x or at or above 1.50 x the entry price.

  Stops never rest at the broker. Every exit, in every session, is a marketable
  limit sell at `bid x (1 - exit cap)` rounded up to the tick, re-priced after
  `exit_orders.timeout_seconds`. X1 is such a limit, not CLS/MOC, because the transport
  carries limit/DAY orders only.
- **Chunking.** The ledger's per-order notional and quantity caps also bound sells, so
  an appreciated position exits in chunks, one open order per symbol at a time. A
  sell is never sent while that symbol's buy is open, because a wash-trade refusal
  would stop the run.
- **Force reasons** cancel open buys and flatten: the STOP file, a controller stop
  (SIGINT/SIGTERM), an adapter error, a ledger halt, a transport gap, a
  mark-to-market failure, the session close and the hard flatten. The hard flatten is
  the configured `trial_end_et`, or earlier when the ledger's sell window
  (`duration_seconds + cleanup_seconds` from trial start) less `flatten_reserve_seconds`
  ends first. A leftover position goes through `recovery.recover`.
- **Gross guard.** When marked gross exposure reaches `gross_guard_fraction` of the
  ledger cap, the largest position exits (`gross_cap_guard`). The ledger halts
  permanently above its cap, and a rising mover would otherwise trip it.
- **Reconciliation.** It runs at start (flat, no open orders), every 30 s while nothing
  is in flight, and at the end: flat, and cash delta equal to this trial's fills. The
  baseline is this trial's own starting cash. The engine's between-trial cash check is
  kept as an observation rather than a refusal: the receipt carries
  `inter_trial_cash_changed`, and the private `trial.json` holds the delta. Quote-driven
  orders are suspended while a snapshot is in flight.

## Commands

```sh
PY=~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python
$PY mover_runner.py check --scan "$SCAN" [--assume-fresh]                  # no broker I/O
$PY mover_runner.py paper --env-file "$PAPER_ENV_FILE" --scan "$SCAN" --trial mover-YYYYMMDD \
    --output "$PRIVATE_OUTPUT/mover-paper.json" [--config config-mover.json] [--state-root DIR] \
    [--live-dir DIR] [--gate-result G --snapshot S] [--allow-shared-account]
$PY mover_runner.py recover --env-file "$PAPER_ENV_FILE" --output "$PRIVATE_OUTPUT/mover-recovery.json"
$PY mover_runner.py synthetic --scan "$SCAN" --output out.json [--allow-stale-scan] [--hold-seconds 4]
```

`paper` refuses before reading credentials when the scan is stale, empty or invalid.
A pre-market-only config also refuses outside PRE. State lives in
`<state-root>/<account fingerprint>/mover/` (`ledger.sqlite3`, `trial.json`), under the
same account lock as the adaptive lane. A trial that ends `needs_attention` blocks the
next one until `recover` runs. Exit codes follow the engine: 0 passed or no signals,
2 not started, 3 needs attention or failed. The receipt lists, per symbol:

- scan fields;
- intended notional, caps and the binding cap;
- client order ids and a SHA-256 prefix of each broker id;
- submit, accept and fill times and prices;
- the ledger's final order status;
- the exit reason and realized P&L.

It also carries totals checked against the ledger delta, start and end reconciliation,
and evidence class PAPER (broker) or SYN (synthetic). It has no account id, balance or
credential.

## Boundaries and limitations

- **Account sharing.** The adaptive lane's continuity check (`next_trial_cash_mismatch`)
  and its snapshot reconciliation (`external_order_detected` freezes the ledger) do not
  tolerate another ledger's cash changes or orders on its account. A mover session
  with fills makes that lane's next trial refuse; one with only unfilled orders makes
  it freeze on its next snapshot. The mover itself ignores foreign *terminal* orders
  and still fails closed on foreign open orders and on any cash or position effect.
  `paper` refuses when the same state root holds an adaptive lane for the account,
  unless `--allow-shared-account` is given. Use a separate paper account, or change the
  adaptive lane first.
- **Lifetime budgets.** The ledger's `max_gross_loss_usd` and `max_drawdown_usd` are at
  most capital / 10 and are lifetime budgets of the mover ledger: gross losses are
  never netted and the drawdown runs from the all-time P&L peak. They are exhausted
  long before the protocol's 20% drawdown tier. Any ledger halt (loss, drawdown, gross
  cap, external order) is permanent for that ledger, and the README's rule against
  changing state roots to evade a halt applies.
- **Hold length.** `trial_seconds` is at most 3600 and `cleanup_seconds` at most 600,
  so no hold exceeds about 70 minutes. X1 is only reachable for entries within that
  window of 15:58, and pre-market X2 fires before the 09:25 flatten only when the first
  fill is at or before 08:25, which means a rule time before about 08:24.
- **Pre-market data.** `quote_max_age_seconds` is at most 3 s. The 2026-09-23 after-hours
  trial stopped on the stream's 3 s data timeout (`trials/20260923-post-extended-hours`).
  `stream_quote_timeout_seconds` can lengthen that transport timeout while the ledger
  keeps its 3 s order gate; choosing a value is a separate recorded decision.
- **Low prices and spreads.** The entry spread cap is at most 100 bps. Per-order
  quantity is at most 100 shares, so low-priced symbols buy less than their notional.
  Symbols priced above `max_order_notional_usd / appreciation_allowance` are skipped.
- **Evidence.** Everything here is SYN until an actual broker run: unit tests, the
  native end-to-end tests with `mover_simulation.py` and `synthetic`. Alpaca paper
  fills are the broker's simulation, not exchange executions.
