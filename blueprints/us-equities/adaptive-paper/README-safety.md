# Durable safety core for bounded adaptive paper trials

`safety.py` is a Python 3.12+ standard-library component. It does not contact a
broker, read credentials, choose a strategy, or establish profitability. Models
and strategies may propose intents; deterministic code owns risk and accounting.
The accepted one-roundtrip smoke adapter remains unchanged.

The default frozen trial allocates $10,000, caps gross held-plus-pending exposure
at $5,000, and permits one whole share per entry, at most $1,000 per order, ten
held or pending symbols and twenty unresolved orders. Loss and drawdown caps are
$25 each. Quotes must be positive, uncrossed, no older than three seconds and no
wider than fifteen basis points. Entry needs a regular open session with at least
300 seconds before close. Entry lasts 300 seconds from the persisted start;
risk-reducing exit remains eligible for another 120 seconds while the session is
open. STOP and loss halts forbid entries but permit bounded owned-position exits.

`RiskLimits` accepts explicit bounded alternatives, persists them in the account
database and rejects later mismatches. The gross limit cannot exceed allocated
capital, and new reservations also respect currently marked allocated equity.
Changing limits never comes from a model response. Risk-reducing orders remain
subject to quantity, order notional, quote, session, and cleanup bounds; no finite
limit-order mechanism guarantees a flat finish.

## Public interfaces

- `RiskLimits(...)`, `Quote(symbol, bid, ask, timestamp)`, `Intent`, `Position`,
  `AccountState` are dataclasses. Money and quantities use `Decimal`; input decimal
  values are strings, integers, or Decimals, never binary floats or booleans.
  Fractional quantities retain up to nine decimal places, including exact residual
  exits; bounded Decimal exponents are formatted without rounding or truncation.
- `account_lock(account_id, lock_root=None)` and
  `account_lock_fingerprint(fingerprint, lock_root=None)` share the accepted
  `~/.local/state/native-agent-stack/alpaca-paper/locks/<sha256>.lock` namespace.
  Use the fingerprint function for an identity already hashed by transport.
- `Ledger(db_path, limits=None)` opens the account-scoped SQLite store. Hold the
  account lock for the entire writer lifetime. `start_trial(now)` durably retains
  the first start; calling it again does not reset the trial or cleanup clock.
- `begin_recovery(now)` starts a separately explicit bounded cleanup invocation.
  It permanently blocks entries, preserves risk halts, limits, fills, positions
  and request history, and permits owned-position exits for `cleanup_seconds`
  from that invocation. Session/quote/quantity bounds still apply. Never call
  repeatedly inside a loop to extend an active recovery indefinitely.
- `begin_next_trial(now, trial_id)` starts an explicitly selected new bounded trial
  in the same account database. The caller must first observe fresh flat/idle
  broker state and cash reconciliation with admissions stopped. The ledger also
  requires every old intent terminal, no position, no risk halt, and a never-used
  trial ID. It resets only the trial clock and completed `recovery_only` markers;
  all limits, fills, cash, loss, peak P&L and request history remain intact. Use
  this API for the first named trial too if first-ID reuse must be prevented.
- `reserve_intent(client_id, symbol, side, qty, limit_price, *, quote, now,
  market_open, session_close, stop_file=None)` atomically reserves exposure and
  returns an `Intent`. `newly_reserved` is true only once. An exact duplicate
  returns the existing identity without authorizing another submission; changed
  duplicate terms fail. Revalidate quote age, STOP, session, time and halt state
  at the final transport boundary after rate-limit waits.
- `validate_pending(client_id, *, quote, now, market_open, session_close,
  stop_file=None)` performs that final revalidation without reserving exposure
  twice. Call it again after any budget wait and immediately before the POST.
- `mark_not_sent(client_id, reason)` releases a definitively refused pre-send
  reservation as local terminal status `not_sent`, without inventing a broker ID.
  It never refunds a reserved request attempt. Call only when transport knows
  that no HTTP request was sent; a timeout or other ambiguous send must remain
  unresolved and be queried by its existing client ID. Observed orders cannot
  be marked not sent, and a later broker observation of such an ID fails closed.
- `mark_broker_refused(client_id, http_status, refusal=None)` records distinct local terminal
  status `broker_refused` for an attempted zero-fill order without broker ID.
  Only HTTP 401/403/404 qualify, and transport must first establish that the
  subsequent client-ID lookup returned 404. It retains the HTTP status and budget.
  Timeout, 400, 422, 429 and 5xx remain ambiguous, with one exception that Alpaca's
  documentation proves definitive: a 422 whose `refusal` is `SUB_PENNY_REFUSAL`
  (`"sub_penny_minimum_price_variance"`), which the transport assigns only to the
  documented body code 42210000 with "sub-penny increment does not fulfill minimum
  pricing criteria" (https://docs.alpaca.markets/us/docs/orders-at-alpaca.md: such
  orders "will be rejected"). That page documents the body, not the HTTP status;
  the 422 was inferred from the code prefix and the POST /v2/orders 422 entry. It
  was observed once on the paper endpoint in the 2026-09-24 native-fault run
  (`native-faults/receipt.json`, C04: submit 422, then lookup 404). The same body
  under any other status still stays ambiguous. The message, not the code, is the discriminator. The ledger also requires the intent's own durable
  limit price to violate the minimum price variance (`refusal_contradicts_intent_price`
  otherwise). Any other 422, including "client_order_id must be unique", stays
  ambiguous. `reserve_intent` still refuses such a price before send
  (`invalid_price_increment`, via the overridable `_check_price_increment`); only
  the native-fault harness's `FaultLedger` exempts its single C04 client ID.
  Neither local terminal status is
  adopted or looked up as a broker order on restart; any later broker observation
  of the identity fails closed.
- `record_order(client_id, broker_id, status, cumulative_qty, average_price, *,
  timestamp=None)` applies owned broker observations and returns whether state
  changed. Cumulative quantity decreases are stale and ignored. Duplicate fills
  are idempotent; contradictory identity, average price or terminal state fails.
  Later partial fills cannot reverse an observed pending-cancel status.
- `request_budget(now, kind, client_id=None)` supports `submit`, `read`, `cancel`
  and `data_read`. Zero means an attempt was durably reserved. A positive delay
  means nothing was reserved: wait within the caller's remaining deadline, then
  call again. There are no sleeps here; returned delay is bounded to 60 seconds.
  Bind every order POST to its `client_id` to prohibit a second attempt after an
  ambiguous response or process crash.
- `mark_to_market(quotes, now)` accepts a list or mapping of `Quote` values and
  returns `AccountState`. Update marks from fresh quote observations. Every held
  symbol must have a fresh mark before increasing exposure. Risk refusals retain
  their actual observations and resulting persistent loss halts.
  Valuation and owned exits permit a wide but valid fresh spread: the bid still
  represents current liquidation risk. The spread admission cap applies to buys.
- `intents()`, `unresolved()`, `positions()` and `accounting()` expose durable
  state. Positions map symbol to `Position` with `qty`, `cost_basis_usd`, and
  `average_cost`. `freeze(reason)` stores an irreversible halt for this bounded
  trial; use a short reason code, never raw broker/account text. `close()` releases
  the database connection.

The request ledger admits at most 200 total HTTP attempts and at most 180 submit
attempts in any rolling sixty-second window. Thus submissions leave at least
twenty calls for reads/cancels; if those calls consume more, the global limit
reduces available submission capacity. Requests that fail or time out still count.
All transports for this account must share this one database and account lock.
An unrelated account client is outside the lock's control. Requests/minute are
not fills/minute or completed roundtrips/minute.

## Durability, accounting and limits

SQLite WAL with `synchronous=FULL` commits each intent, request reservation and
fill-accounting update. Unique client and broker IDs prevent aliasing. Transactions
also serialize reservations across connections. The database and its directory
are created privately; journal directory metadata is fsynced at initialization.
No account IDs, keys or secret headers are stored. Retain the account database
across process restarts; a new database would lose budget and risk continuity.

Fill cost uses `new cumulative quantity * new average - old cumulative quantity *
old average`, not the latest average multiplied by the fill delta. Cost basis uses weighted
average inventory accounting. `cash_delta_usd` is the exact sum of observed gross
buy/sell cash flows; broker fees and other account activity require independent
reconciliation. `cumulative_realized_loss_usd` accumulates losing realized deltas;
wins do not erase it. `gross_loss_usd` adds current negative marked position P&L.
Drawdown measures the fall from the persisted peak total marked P&L.

The transport/coordinator must validate event ownership, reconcile stream gaps,
compare broker positions and cash, and stop on unexplained differences. Per-order
cumulative updates are idempotent and tolerate stale quantities. This module does
not reconstruct exchange chronological execution order across different orders;
its weighted-average realized attribution follows applied observations, while
gross cash flow and total marked P&L remain independently reconcilable. Do not
infer tax-lot accounting or native stream recovery from these local tests.

The first `start_trial` clock cannot be reset by calling `start_trial` again.
Only explicit `begin_next_trial` with fresh external proof can rotate a completed,
flat trial while retaining account-wide history. Deleting or replacing the
database is not a supported reset. A timed-out trial requires reconciliation and
`begin_recovery` for a separately bounded cleanup invocation; do not manufacture
a fresh trial or reset request history to hide unresolved state. Identify the
actual recovery adapter: a direct SDK fractional exit does not establish that a
whole-share native engine adapter supports fractional execution.

## Leverage schedule (opt-in, `leverage-schedule-v1-20260922`)

The default lane stays 1x: `runner.load_config` refuses `max_leverage > 1`
unless a config's top-level `leverage_policy` block validates against
`leverage.py`'s `validate_leverage_policy`. With no such block (both shipped
configs, `config.json`/`config-sip.json`), every path in this document is
unchanged -- `RiskLimits.leverage` is `None`, the persisted `meta.limits`
bytes are byte-identical to before this policy existed, and the buy-side
gross-exposure check is the original `min(effective_gross_cap, equity)`.

Under a validated policy (`config-leverage-1x/2x/4x.json`), the effective
ceiling for new entries is `min(schedule[session][regime],
drawdown_ladder(drawdown_fraction), overnight_max_leverage if the session
policy allows overnight holds, the broker-proven account multiplier,
config `max_leverage` <= 4)`. Every existing hard ceiling in this document
(`max_order_notional_usd`, `max_gross_exposure_usd`, `max_gross_loss_usd`,
`max_drawdown_usd`, held-symbol and outstanding-order caps, STOP and
`halted_reason`) is unchanged and independent of it. The leverage ceiling
gates entries only: sells and exits are never refused by it, and it never
raises a risk halt or forces liquidation on its own -- a ladder step to 0
(from accumulated drawdown) blocks new buys with `leverage_ceiling_zero`
while leaving existing holdings to the unchanged stop/take-profit/trailing/
time-decay/portfolio-rotation exit chain. `Ledger._leverage_envelope` is the
independent, regime-unaware ledger-layer ceiling `reserve_intent`/
`validate_pending` enforce even if the policy layer (`strategies.py`) were
somehow bypassed; it fails closed (0) for a timestamp outside the frozen
session calendar. See `leverage.py`'s module docstring for the full
schedule/ladder contract and
`agent-lab/docs/decisions/2026-09-22-leverage-schedule-and-entitlement.md`
for the design record. Leverage above 1x is paper-only, requires a
preflight-proven account multiplier at least equal to the requested
leverage (`runner._check_margin_entitlement`), and remains unqualified
until each rung's `leverage-ladder-1x/2x/4x` gate row shows
`needs_attention == 0`.

F2 (2026-09-22 residual review, reachability): a rung's `max_leverage`,
schedule cells and drawdown ladder establish the safety **envelope** in
force at that cap -- the most a run is permitted to reach -- not a target a
run is guaranteed to hit. `strategies_v1._decide_core`'s entry budget
(`min(gross_cap, capital*leverage) - max_order_notional`) and its inverse-
volatility allocation do not by construction force achieved exposure up to
the configured ceiling, so a "4x" run can complete, and its gate row can
show `needs_attention == 0`, without its gross-to-equity exposure ever
having exceeded the 2x rung's own ceiling; the `README.md`/config-note
claim that every rung "gets the same proportional room to run" described
only the drawdown/loss caps' dollar-fraction scaling, not achieved
exposure, and has been corrected in the rung configs' `notes` accordingly.
Every leveraged run's `outcome`/receipt (`leverage_policy is not None`)
now separately records what was actually achieved: `outcome["leverage"]`
gains `peak_achieved_leverage` (peak gross exposure / mark-to-market
equity, distinct from the existing fixed-capital-denominated
`peak_effective_leverage`), `ceiling_at_peak_achieved_leverage` (the
policy-layer ceiling in force at that peak), `next_lower_rung_ceiling`
(`leverage.next_lower_rung_ceiling(config max_leverage)`; `None` for the
1x rung) and `seconds_above_next_lower_rung_ceiling` (cumulative wall-clock
time the run's achieved leverage spent above the next-lower rung's own
ceiling, computed per-tick by `runner._leverage_achievement_step`). These
fields are absent from every default-path (no `leverage_policy` block, or
`leverage_policy is None`) outcome, exactly like the rest of
`outcome["leverage"]`; they do not change `leverage.py`'s
`CANONICAL_V1_BLOCK` schedule/ladder or `strategies_v1._decide_core`'s
sizing math, which stay a ceiling, not a target, per
`agent-lab/docs/decisions/2026-09-22-leverage-schedule-and-entitlement.md`.
A rung's gate row is not, by itself, evidence that the rung's exposure was
ever achieved -- that evidence is this recorded achieved-leverage receipt.
No gate row in `catalogs/us-equities/gates-20260922.json` currently reads
`peak_achieved_leverage`/`seconds_above_next_lower_rung_ceiling`, so a gate
row can still flip to established on a receipt whose achieved exposure never
exceeded a lower rung's own ceiling; the rung configs' `notes` have been
corrected to say so instead of claiming the opposite.

2026-09-22 leverage fix round 1 (LEV-RI-A/CX-P1/EH-1/CX-P2, all `major`/
`blocker` findings against G-e/F2): `strategies_v1._decide_core`'s
leveraged-rung entry budget (`leverage_ceiling is not None`) now counts
every current holding's notional regardless of this tick's own exit
decision (a same-tick take-profit/stop/trailing/portfolio-rotation exit
removes a symbol from `targets` immediately, even though the position is
still physically held until its sell order actually fills -- CX-P1), plus
the caller-supplied notional of any still-resting, unfilled buy order
(`LeverageInputs.pending_buy_notional_usd`, sourced from the ledger's own
`AccountState.pending_buy_notional_usd` and threaded through
`native_strategy._leverage_inputs` -> `strategies.AdaptivePolicy.decide` --
LEV-RI-A); previously `used` only summed this tick's own `targets`, so a
symbol still awaiting a fill or a sale from an earlier or the same tick was
invisible to the leveraged budget, letting a rung's aggregate exposure climb
past its regime ceiling (`leverage.LeveragePolicy.envelope` is deliberately
regime-independent -- see its docstring -- so this was the only enforcement
of the regime-specific part). The non-leveraged path (`leverage_ceiling is
None`, e.g. both default configs) is unchanged (`used` stays `targets`-only)
to preserve the golden-equivalence contract. `outcome["leverage"]`'s
`peak_gross_exposure_usd`/`peak_achieved_leverage`/`broker_margin_used` now
measure filled-position exposure only (`AccountState.gross_exposure_usd`
minus its own `pending_buy_notional_usd`, which used to be folded in
uncredited -- EH-1); the peak pending-buy notional observed is recorded
separately as `peak_pending_buy_notional_usd`. `runner.load_config`'s
`PolicyConfig` construction now also passes `max_order_notional` from the
config's own `max_order_notional_usd` instead of silently keeping
`PolicyConfig`'s 1000 default regardless of a rung's configured 2000/4000
(CX-P2), so entries can actually size up to what each rung's own
`max_order_notional_usd`/ledger-side cap allows.

Run `python3 -m unittest discover -s tests -p test_adaptive_paper_safety.py -v` for
the synthetic local failure cases. These checks establish local state invariants,
not native broker throughput, fault behavior, order fills, or strategy quality.
`tests/test_adaptive_paper_leverage.py` covers `leverage.py` itself.
