# Mover trial mode (protocol `mover-early-entry-v1-20260924`, paper_e2e)

A bounded paper trial that enters up to five scanner-selected movers at trial start
and exits them by one protocol rule. The historical study picks the rule and exit, so
the trial is parameterised by `mover.rule` and `mover.exit` in the config. Modules:

| File | Role |
| --- | --- |
| `mover.py` | Pure logic: config and scan validation, sizing, marketable-limit pricing, X1-X4, the per-symbol order state machine (`MoverBook`) with its exit budget and hand-off rule |
| `mover_strategy.py` | NautilusTrader strategy shell that executes the book's actions |
| `mover_runner.py` | `check` / `paper` / `recover` / `synthetic` commands, the native trial loop and the recovery adoption scope |
| `mover_simulation.py` | Synthetic broker port (scripted quotes, resting limits, partial fills; intents follow the transport's `normalize_intent` contract) |
| `config-mover.json` | Example: pre-market only, trial end 09:25 ET, exit X2, rung 1, conservative caps (200 USD per entry, 2000 USD ledger per-order and gross caps) |

A mover trial reuses the engine: the paper-only endpoint gate, `runner.credentials`,
`transport.preflight`, `runner.validate_preflight` (flat account, no open orders,
tradable universe, fresh benchmark quote, session window), `safety.Ledger`/`RiskLimits`
(every order is reserved and capped there), `runner.Controller`,
`transport.AlpacaPaperTransport`, `native_adapter.build_node`, `runner.reconcile`,
`recovery.recover` and the shared `STOP` kill switch. The only shared-engine change is
recovery's exit sizing, which now stays within the ledger's own per-order share cap
(`RiskLimits.effective_max_order_qty`). In "fixed" mode that is `max_order_qty`, as
before, so `config.json` and `config-sip.json` behave identically; the notional-mode
`config-leverage-*.json` recoveries gain the same fix (README-recovery.md).

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
  V in USD; V may use a K, M or B suffix. `price_at_t` must be at least the protocol's
  1.00 USD minimum (`scan_symbol_below_min_price`), and `dollar_volume_at_t` must reach V.
  When `gain_pct_at_t` is supplied it must reach G less 1e-7 percent points: the scanner
  fires at a ratio gain of G - 1e-9 (clarification C25) and writes percent points to nine
  decimals. `news_before_t` rules need `"news_before_t": true`.
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
- the mover entry cap, `mover.max_entry_notional_usd` (200 USD in the example);
- the remaining gross budget, `min(max_gross_exposure_usd / appreciation_allowance, equity x ledger leverage envelope)`.

A symbol whose price times the allowance exceeds the entry cap is skipped
(`price_exceeds_entry_headroom`). The entry cap is separate from the ledger's
per-order cap because the ledger's cap bounds every order, exit sells included; see
*Two caps* below. Rungs come from `rung_schedule` (sessions 1-20 at rung 1 in the
example); a session beyond the schedule is refused. A rung above 1 needs the canonical
`leverage_policy` block, whose PRE and POST cells cap the ledger at 1x. Entries are sized
at the full rung, so `max_leverage` must be positive (`unqualified_lane_configuration`)
and at least the highest scheduled rung (`mover_rung_exceeds_max_leverage`). The config must
set `max_order_qty_mode: "notional"` (`mover_requires_notional_order_qty_mode`
otherwise): only then is the ledger's per-order share cap, which also sizes recovery's
exits, `floor(max_order_notional_usd / bid)` whole shares.

## Orders

- **Entry.** One buy per symbol at trial start, as a marketable limit:
  `ask x (1 + entry cap)`, rounded down to the tick, whole shares, TIF day. The
  adapter sets `extended_hours` in PRE and POST. The buy waits, within
  `entry.window_seconds`, for a fresh, unhalted quote with an admissible spread and
  fresh marks on held symbols. Any unfilled remainder is canceled after
  `entry.timeout_seconds`. A buy is never re-priced or re-sent, even after a refusal.
- **Exits** run on every quote and on the runner's 0.1 s tick:
  - X1 two minutes before the session's regular close (15:58 ET; 12:58 on early closes);
  - X2 60 minutes after the first fill;
  - X3 when the bid is at or below 0.85 x the running high since entry;
  - X4 when the bid is at or below 0.85 x or at or above 1.50 x the entry price.

  Stops never rest at the broker. Every exit, in every session, is a marketable
  limit sell at `bid x (1 - exit cap)` rounded up to the tick but never above the bid
  rounded down to the tick, re-priced after `exit_orders.timeout_seconds`. X1 is such a
  limit, not CLS/MOC, because the transport carries limit/DAY orders only.
- **Ticks and instruments.** Limits use the 0.01 tick at or above 1 USD and 0.0001
  below, as Alpaca and the ledger's price-increment check require. Every mover
  instrument is registered at 4 decimals: a symbol scanned above 1 USD can fall below it
  (X4's stop does for any entry up to about 1.17 USD), and a 2-decimal instrument can
  neither price a marketable limit under a sub-penny bid nor carry the sub-penny fill
  (the native adapter refuses it as `cumulative_fill_precision_requires_reconciliation`).
- **Two caps.** `mover.max_entry_notional_usd` (200 USD) sizes and bounds each buy;
  `MoverController` also refuses a larger buy before the ledger reserves it
  (`mover_entry_notional_cap_exceeded`). The ledger's `max_order_notional_usd` (2000
  USD) and 100-share cap bound every order, exit sells included. Config load requires
  the ledger cap to be at least ten times the entry cap (`mover.EXIT_HEADROOM_FACTOR`;
  `mover_ledger_order_cap_below_exit_headroom` otherwise). A leg therefore sells in one
  order through a tenfold rise. Beyond that it sells in whole-share chunks, one open
  order per symbol at a time, until one share is worth more than the ledger cap. At
  the 2x allowance an entered share costs about 100 USD at most, so that point needs
  about a twentyfold rise. A sell is never sent while that symbol's buy is open, because a
  wash-trade refusal would stop the run.
- **Exit budget.** Each leg may send `exit_orders.max_orders_per_symbol` exits, counted
  from the latest grant. No exit is sent on a halted quote (it could not fill; the leg
  waits). A sell refused before any broker request (the ledger or NautilusTrader
  refused it, so the ledger holds no sent intent) is not charged; it is retried after
  1 s and has its own bound of the same size. A latched force reason grants each leg one
  fresh budget. A leg that exhausts its budget before any force latches the book-wide
  force `exit_orders_exhausted` (or `exit_refusals_exhausted`), so every leg flattens.
  Each evaluation handles cancels and exits for every leg before any entry. A force that
  latches during it sends every leg through the cancels and exits once more, and the
  entries that follow see it. That same evaluation therefore cancels open buys, flattens
  every leg and skips waiting entries, and it sends no buy (so no buy is sent and
  canceled in one batch).
- **Force reasons** cancel open buys and flatten: the STOP file, a controller stop
  (SIGINT/SIGTERM), an adapter error, a ledger halt, a transport gap, a
  mark-to-market failure, the session close, an exhausted exit budget and the hard
  flatten. The hard flatten is the configured `trial_end_et`, or earlier when the
  ledger's sell window (`duration_seconds + cleanup_seconds` from trial start) less
  `flatten_reserve_seconds` ends first.
- **Hand-off to recovery.** Once a force has latched and a position or an open order
  remains, the native loop stops and leaves the residual to recovery when every held
  leg's exits are blocked (budget spent after the fresh grant, a limit that is not
  positive, or one share above the ledger's per-order cap), or when no exit has filled
  for three exit timeouts (30 s in the example) since the latch or the last fill. That
  covers exits resting unfilled, refused, waiting on a halt, or impossible without fresh
  quotes, so a stuck position is not left unmanaged until the sell window ends. Before a
  force, a blocked leg keeps retrying and the other legs keep their rules: recovery stops
  at its first failed symbol, so an early hand-off could leave sellable legs unsold. The
  receipt's `handoff_to_recovery` records the reason and the seconds after the force.
- **Gross guard.** When marked gross exposure reaches `gross_guard_fraction` of the
  ledger cap, the largest position exits (`gross_cap_guard`). The ledger halts
  permanently above its cap, and a rising mover would otherwise trip it.
- **Reconciliation.** It runs at start (flat, no open orders), every 30 s while nothing
  is in flight, and at the end: flat, and cash delta equal to this trial's fills. The
  baseline is this trial's own starting cash. The engine's between-trial cash check is
  kept as an observation rather than a refusal: the receipt carries
  `inter_trial_cash_changed`, and the private `trial.json` holds the delta. Quote-driven
  orders are suspended while a snapshot is in flight.

## Recovery

A residual after the native loop, and the `recover` command, go through
`recovery.recover` (sell-only, no strategy restart) on a fresh transport that subscribes
the residual's symbols (or the benchmarks when flat). The mover ledger keeps every
session's intents and each scan trades other symbols, while a transport can only adopt
an intent for a symbol it subscribes (at most 30). So a mover recovery port adopts every
unresolved intent and only those terminal intents whose symbol it subscribes. A skipped
terminal intent stays covered: the snapshot pages every order since the lane's first
trial, and reconciliation raises `submitted_intent_absent` for any attempted ledger intent
it lacks. The recovery receipt's `adoption_scope` counts adopted and skipped intents.
Each recovery exit is sized in whole shares within the ledger's cap at the bid
(`floor(max_order_notional_usd / bid)` in notional mode), so a position worth more than
the ledger cap exits in chunks. When one share alone is worth more than it, recovery ends
`needs_attention` (`recovery_quantity_not_representable`). Its result and the trial
receipt then list the position under `unsellable_positions`: symbol, quantity, bid, cap
and `share_exceeds_ledger_order_cap`. A trial that needed a forced recovery stays
`needs_attention` even when the recovery passed; `recover` then takes a fresh broker
proof and, when it passes, sets `trial.json` back to `finished`.

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

`check --assume-fresh` and `synthetic --allow-stale-scan` evaluate the scan as of its own
`scan_time`. Every other check still applies, and a malformed file is refused with its
reason (`scan_invalid_json`, `scan_time_invalid`, ...) rather than raised.

`paper` refuses before reading credentials when the scan is stale, empty or invalid.
A pre-market-only config also refuses outside PRE. State lives in
`<state-root>/<account fingerprint>/mover/` (`ledger.sqlite3`, `trial.json`), under the
same account lock as the adaptive lane. A trial that ends `needs_attention` blocks the
next one until `recover` passes. Exit codes follow the engine: 0 passed or no signals,
2 not started, 3 needs attention or failed. The receipt lists, per symbol:

- scan fields;
- intended notional, caps and the binding cap;
- client order ids and a SHA-256 prefix of each broker id;
- submit, accept and fill times and prices;
- the ledger's final order status and whether a refusal came before any broker request;
- the exit reason, the exit budget state and realized P&L.

A native loop that handed its residual to recovery records `handoff_to_recovery`, and a
position no engine order could sell is listed under `unsellable_positions`. An exception
inside the native loop (for example a periodic reconciliation that finds an order this
ledger does not own) stops the node like any other end. The receipt still lists every
leg's orders, fills and events, adds `error_type`, `error_reason` and a `mover_loop_error`
event, and ends `needs_attention`; the forced recovery handles any residual. The
`sizing` block records the entry cap, the ledger's per-order cap and the exit
headroom factor.

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
  fill is at or before 08:25, which means a rule time before about 08:24. An X1 config
  is refused when X1 could never fire: a trial end at or before 15:58
  (`mover_x1_preempted_by_trial_end`), or a session-close latch at or before it
  (`mover_x1_preempted_by_session_close`). The native loop latches `session_close`
  `cleanup_seconds` before the controller close, which is 16:00 without extended hours
  (20:00 with them), so a regular-session X1 config needs `cleanup_seconds` below 120.
  That is necessary, not sufficient: each plan is also refused (`mover_x1_unreachable`)
  when its hard flatten (the trial end, or the sell window less `flatten_reserve_seconds`)
  comes at or before X1. X1 is two minutes before the session's regular close from the
  engine calendar (15:58, or 12:58 on a scheduled early close; study clarification C26).
- **Pre-market data.** `quote_max_age_seconds` is at most 3 s. The 2026-09-23 after-hours
  trial stopped on the stream's 3 s data timeout (`trials/20260923-post-extended-hours`).
  `stream_quote_timeout_seconds` can lengthen that transport timeout while the ledger
  keeps its 3 s order gate; choosing a value is a separate recorded decision.
- **Low prices and spreads.** The entry spread cap is at most 100 bps. Per-order
  quantity is at most 100 shares, so low-priced symbols buy less than their notional.
  Symbols priced above `mover.max_entry_notional_usd / appreciation_allowance` are skipped.
- **Exit headroom.** A leg stays sellable until one share is worth more than the
  ledger's per-order cap. In the example that is 2000 USD, about a twentyfold rise from
  an entered share (about 100 USD at most). One such share also exceeds the 2000 USD
  gross cap, so the ledger has halted by then. Past that point no engine order can sell
  the leg. The book blocks it (`exit_share_exceeds_ledger_order_cap`) and keeps retrying
  until a force, then hands off. Recovery ends `needs_attention` with the position held,
  and `unsellable_positions` names it. RiskLimits keeps the per-order cap at or below the
  gross cap, so a larger bound needs a larger gross cap. The tenfold minimum
  (`mover.EXIT_HEADROOM_FACTOR`) is a code constant. It is the largest factor the
  example's gross cap allows over its entry cap, and it was chosen without a measured
  distribution of scanned movers' largest rise within the hold. That distribution is
  the comparison that would change it.
- **Ledger limits are pinned.** A mover ledger keeps the risk limits it was created with
  and refuses to open under different ones (`persisted_risk_limits_differ`). A ledger
  created under the earlier single 200 USD per-order cap keeps a 200 USD sell cap: its
  config must keep `max_order_notional_usd` at 200, which the headroom check allows only
  with an entry cap of at most 20 USD.
- **Fixed constants.** The hand-off bound (three exit timeouts) and the 1 s pre-wire
  retry are code constants (`mover.HANDOFF_EXIT_TIMEOUTS`, `PRE_WIRE_RETRY_SECONDS`)
  chosen without a paper measurement; a broker run that shows slower fills is the
  comparison that would change them.
- **Sub-penny fills.** A 4-decimal instrument carries fills to 0.0001. A cumulative
  average finer than that (several partial fills at different prices) still stops the
  native adapter, as it does for the adaptive lane.
- **Evidence.** Everything here is SYN until an actual broker run: unit tests, the
  native end-to-end tests with `mover_simulation.py` and `synthetic`. Alpaca paper
  fills are the broker's simulation, not exchange executions.
