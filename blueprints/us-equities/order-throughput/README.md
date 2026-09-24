# Paper execution-capacity harness

This harness checks one thing: how many order actions per minute an Alpaca
**paper** account can sustain under the broker's rate limit. Every order's state
must also be observed on the `trade_updates` websocket, and the broker's own
record must reconcile at the end. The current target is about 200 order
actions/min. The later target is about 1000/min.

## Policy: these are not strategy trades

> Execution-capacity qualification only. Harness orders are non-marketable
> probes that are cancelled individually; they are not strategy trades and must
> never be counted as strategy trades, fills, signals or performance.

Every receipt carries this statement, `counts_as_strategy_trades: false` and
`strategy_trades: 0`. The adaptive-paper rule still applies: no strategy
manufactures trades to hit a throughput target. A capacity result is a
statement about the paper transport and the broker limit only. It is never
evidence of strategy quality.

## What it does

1. **Preflight (read-only).** It reuses adaptive-paper `transport.preflight`
   to read the account, clock, positions, open orders, asset and latest quote.
   The run adopts the trading endpoint's `x-ratelimit-limit` from these GETs.
   The market-data endpoint reports its own, unrelated limit (10000 in the
   retained trials), so that value is recorded but never sizes the budget.
2. **Budget.** `rate_governor.RateGovernor` admits a call only when all of
   these hold:
   - A token bucket refilling at `budget/60` per second has a token.
   - Fewer than `budget` calls were made in the last 60 seconds, where
     `budget = floor(min(--cap, observed limit) * --headroom)` and headroom
     defaults to 0.9.
   - The broker's `x-ratelimit-remaining`, minus calls made since that
     response, is above the reserve (`limit - budget`) until `x-ratelimit-reset`.

   A 429 freezes every admission and is counted. The run then backs off for
   `Retry-After` (seconds or HTTP-date), or until `x-ratelimit-reset`, or
   exponentially if neither header is present. A changed `x-ratelimit-limit`
   header recomputes the budget, still bounded by `--cap`. The same code
   therefore runs at 200/min, and at 1000/min once the header rises and
   `--cap 1000` allows it.
3. **Probes.** Each probe is a DAY limit BUY for `qty` (default 1) of one liquid
   symbol (default SPY). It is priced `--band-bps` (default 500 = 5%) below the
   current bid, rounded down to the cent. The price is refreshed from the data
   endpoint every 60 s, which does not use the trading budget. If a refresh
   fails, submissions freeze and cleanup runs. In the PRE or
   POST session, orders carry `extended_hours=true`. The CLOSED session is
   refused. The calendar is adaptive-paper `sessions.py` (2026 only). A
   synchronous rejection, such as a price collar, is recorded as data by HTTP
   status. `--max-consecutive-rejections` ends the run.
4. **State from the websocket.** Order state comes from `trade_updates`, not
   from polling, so the REST budget goes only to submits and cancels. A probe
   is cancelled individually (`DELETE /v2/orders/{id}`) once the stream shows
   it was acknowledged (`pending_new`/`new`/`accepted`). Cancels always take
   priority over new submits. If a probe gets no acknowledgement or no
   terminal event within `stream_timeout_seconds` (10 s), submissions freeze
   and the run cleans up.
5. **Cleanup** runs on normal end, STOP, SIGINT/SIGTERM, a freeze or an
   exception. It cancels every live probe individually. It then lists open
   orders and cancels anything left with this run's `client_order_id` prefix,
   including submits whose outcome was ambiguous. A final open-order listing
   must show **zero** open orders with the prefix (`verified_zero_open`).
6. **Reconciliation (bounded, at the end only).** It lists all orders
   submitted since the run started (paged, at most 20 pages) and compares them
   with the local and stream record. Any of the following makes the run
   unclean: an order missing at the broker, an unknown order with the prefix,
   a stream/REST terminal-status mismatch, a non-terminal order, a filled
   probe, an unresolved ambiguous submit, or a changed position.

## Safety

- **Paper only.** `CapacityConfig.validate` refuses any base URL other than
  `https://paper-api.alpaca.markets` before any request. This includes an
  `APCA_API_BASE_URL` in the env file. The HTTP session is adaptive-paper's
  `GuardedSession`: its origin is pinned, SDK retries are zero, redirects are
  refused, and the paths are a fixed allowlist.
- **STOP kill switch.** The host STOP file is adaptive-paper's
  `safety.DEFAULT_STOP` (`~/.local/state/native-agent-stack/alpaca-paper/STOP`).
  It works as it does in adaptive-paper:
  - If it exists at start or under the account lock, the run is refused.
  - If it appears during the run, new submits stop and cleanup cancels the
    run's orders.
  - The native port re-checks it immediately before every POST.
- **Account-writer lock.** The run holds adaptive-paper's
  `account_lock_fingerprint` for its whole duration. It therefore cannot
  overlap an adaptive-paper trial on the same account, and each lane keeps
  its own REST budget.
- **Adaptive lane conflict.** An adaptive-paper trial reconciles every order
  placed since its first trial started, and it freezes on any
  `client_order_id` it does not own (`external_order_detected`). On an account
  that has adaptive-paper state (`<state-root>/<fingerprint>/adaptive/trial.json`),
  the harness is refused unless `--accept-adaptive-lane-conflict` is given.
  **Use a separate paper account for capacity runs.** If you use a
  non-default adaptive `STATE_ROOT`, pass it as `--adaptive-state-root`.
- **Caps.** The configuration bounds total orders (`--max-orders`, default
  600, at most 20000), duration (`--duration`, default 330 s, at most 3600),
  and open orders (`--max-open-orders`, default 10). It also bounds per-order
  and open notional (`--max-order-notional` 1000 and `--max-open-notional`
  10000 USD), 429s (`max_http_429` 5), consecutive rejections and in-flight
  REST calls (`--inflight` 4). The run must also finish, including cleanup,
  inside the current session segment.
- **Existing exposure.** The run is refused unless the exact number of
  existing nonzero positions and open orders matches `--acknowledge-positions`
  and `--acknowledge-open-orders` (both default 0).
- **No cancel-all by default.** `DELETE /v2/orders` would cancel other
  strategies' orders on a shared account. `--allow-cancel-all` permits it only
  when `cancel_all_guard` passes. The preflight must have seen **no** open
  orders, and a fresh, complete listing must show that every open order carries
  this run's prefix. Adaptive-paper's `GuardedSession` does not admit that
  path, so the native port reports `supports_cancel_all = False` and always
  cancels individually. Only the offline fixture exercises the guarded
  cancel-all branch.
- **Unexpected fills.** A probe should never fill. If one does, submissions
  freeze and the status becomes `needs_attention`. The receipt records
  `unexpected_fill_qty`. The harness never trades to flatten; the operator
  resolves the fill.
- **A marketable round-trip mode is not implemented.** See the arithmetic in
  `rate-limit-evidence-20260924.json` for what such a mode would cost.

## Running it

### Offline (fixture, no credentials, no network)

```sh
python3 blueprints/us-equities/order-throughput/capacity.py offline --output /tmp/capacity-offline-200.json
python3 blueprints/us-equities/order-throughput/capacity.py offline --limit-header 1000 --cap 1000 \
  --max-orders 3000 --output /tmp/capacity-offline-1000.json
python3 -m unittest tests.test_order_throughput -v
```

Offline receipts have `evidence_class: "offline_fixture"`, and
`acceptance.passed` is always false for them. The fixture models only the
following: fixed 60-second rate windows with `x-ratelimit-*` headers,
429 + Retry-After, individual and cancel-all cancels, paged listings, and
`trade_updates` events. It shows the harness logic, not Alpaca behavior.

### Paper (native, evidence class `native_paper`)

Use the adaptive-paper pinned environment: `adaptive-paper/requirements.txt`,
with `alpaca-py==0.44.0` in an isolated Python 3.12 venv. Credentials come
only from the existing ENV_FILE mechanism. This is adaptive-paper
`runner.credentials`: a file with mode 0600, owned by you, outside any Git
worktree, containing only `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`. Never
put keys on a command line, in the repository, in a prompt or in an
artifact.

```sh
PY="$ADAPTIVE_PAPER_VENV/bin/python"
# about 200 order actions/min (default trading limit 200)
"$PY" blueprints/us-equities/order-throughput/capacity.py paper \
  --env-file "$ENV_FILE" --output "$PRIVATE_OUTPUT/capacity-200.json"
# about 1000 order actions/min, once the paper endpoint reports x-ratelimit-limit 1000
"$PY" blueprints/us-equities/order-throughput/capacity.py paper \
  --env-file "$ENV_FILE" --cap 1000 --max-orders 3000 --output "$PRIVATE_OUTPUT/capacity-1000.json"
```

If the header still reports 200 when `--cap 1000` is given, the budget stays
at 180/min. The receipt then shows `effective_limit: 200`. Exit codes:

| Code | Meaning |
|---|---|
| 0 | Completed, and the capacity criteria were met |
| 1 | Completed, but below target |
| 2 | Refused before any order |
| 3 | `needs_attention`, `failed`, or cleanup/reconciliation not clean |

## Acceptance criteria for a capacity run

A run qualifies (`acceptance.passed`) only when its evidence class is
`native_paper` and **all** of the following hold:

- **Sustained.** At least `ceil(0.85 * effective_limit)` order actions in each
  of 5 consecutive full 60-second windows. That is **170 actions/min at a 200
  limit** and 850 at 1000. One submit and one cancel each count as one
  action. At a 200 limit this means about 85 submits plus 85 cancels per
  minute. A target of "170 submits/min" is impossible with individual cancels,
  because it would need about 340 calls/min. The arithmetic is in
  `rate-limit-evidence-20260924.json`.
- **0 unhandled 429.** Each 429 froze admissions for its backoff, and the
  affected submit, cancel or read was later resolved (for example, an
  ambiguous submit was proven created or not created by the complete
  listing).
- **100% websocket completeness.** Every order that exists at the broker had
  a stream acknowledgement and a terminal event. A stream `rejected` event
  counts as both.
- **Clean reconciliation.** See step 6 above.
- **Cleanup verified.** Zero open orders with this run's prefix at the end.
- **No unexpected fills.**

## Receipt

The JSON receipt is written atomically with mode 0600 through adaptive-paper
`runner.save`. It contains:

- The configuration, probe plan and `client_order_id` prefix.
- A preflight summary: counts only, plus the trading and data limit headers
  seen.
- Governor state: budget, reserve, admitted calls, 429 count, backoffs and
  denial counts.
- `rate_limit_changes`.
- Observed rate-limit header counts, and the minimum remaining value per
  origin.
- HTTP status counts.
- Latency p50/p95/p99 for three spans: submit to REST acknowledgement, submit
  to stream acknowledgement, and submit to stream terminal event.
- Per-window submits, cancels and order actions.
- Websocket completeness.
- Cleanup and reconciliation results.
- The acceptance block.

It contains no credentials, account identifier or account hash, and no broker
order IDs.

## Files

| File | Role |
|---|---|
| `capacity.py` | Engine (`CapacityRun`), configuration and bounds, cancel-all guard, receipt, CLI |
| `rate_governor.py` | Token bucket + rolling window + remaining/reset + 429 backoff |
| `alpaca_capacity_port.py` | Native paper port; reuses adaptive-paper `transport` read-only |
| `capacity_fixture.py` | Offline fake clock, broker and `trade_updates` stream |
| `rate-limit-evidence-20260924.json` | Cited limits, repository-measured header counts, round-trip arithmetic |
| `rate_limit_evidence.py` | Rebuilds or `--check`s that JSON from the committed trial receipts |

## Evidence status (2026-09-24)

| Status | What |
|---|---|
| Measured (offline fixture) | The governor and engine under 200 and 1000 headers, a header rise, 429 freeze/backoff, refusals, cleanup and reconciliation. See `tests/test_order_throughput.py`. |
| Measured (repository files) | 419 trading-origin `x-ratelimit-limit: 200` and 9 data-origin `10000` headers in the retained adaptive-paper trial outputs. |
| Not yet measured | Any native paper run of this harness. |
| Not exercised against the SDK | `alpaca_capacity_port.py` was not run with alpaca-py 0.44.0 in this change, because the SDK was not installed on the authoring host and no network was used. |
| Unverified assumptions | Whether the paper endpoint honours `after_order_id` pagination (adaptive-paper uses the same cursor), exact `trade_updates` event names under load, and Alpaca price-collar behavior for far-from-market limits. |
