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
- `account_lock(account_id, lock_root=None)` and
  `account_lock_fingerprint(fingerprint, lock_root=None)` share the accepted
  `~/.local/state/native-agent-stack/alpaca-paper/locks/<sha256>.lock` namespace.
  Use the fingerprint function for an identity already hashed by transport.
- `Ledger(db_path, limits=None)` opens the account-scoped SQLite store. Hold the
  account lock for the entire writer lifetime. `start_trial(now)` durably retains
  the first start; calling it again does not reset the trial or cleanup clock.
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

The first trial start and limits intentionally cannot be reset through this API.
A later feature may rotate a completed, reconciled, flat trial while retaining
the account-wide request history. Deleting or replacing the database is not a
supported reset. A timed-out trial with unresolved orders/positions requires
explicit reconciliation and a separately bounded cleanup path; do not manufacture
a fresh trial to hide the unresolved state.

Run `python3 -m unittest discover -s tests -p test_adaptive_paper_safety.py -v` for
the synthetic local failure cases. These checks establish local state invariants,
not native broker throughput, fault behavior, order fills, or strategy quality.
