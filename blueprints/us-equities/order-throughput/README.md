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
   exponentially (capped at 60 s) if neither header is present. A
   broker-designated delay is honoured in full, never truncated; one longer
   than 60 s stops submissions (`rate_limit_backoff_exceeds_max`). A changed `x-ratelimit-limit`
   header recomputes the budget, still bounded by `--cap`. The same code
   therefore runs at 200/min, and at 1000/min once the header rises and
   `--cap 1000` allows it.
3. **Probes.** Each probe is a DAY limit BUY for `qty` (default 1) of one liquid
   symbol (default SPY). It is priced `--band-bps` (default 500 = 5%) below the
   current bid, rounded down to the cent. The price is refreshed from the data
   endpoint every 60 s on a worker thread, so the main loop never blocks on it,
   and the refresh does not use the trading budget. A quote without a
   timestamp, or one older than `max_quote_age_seconds` (60 s) or more than
   1 s ahead of the host clock, refuses the run before any order
   (`quote_stale`, `quote_timestamp_missing`), because a stale bid could make
   the probe marketable. If a refresh fails or is stale, submissions freeze
   and cleanup runs. In the PRE or
   POST session, orders carry `extended_hours=true`. The CLOSED session is
   refused. The calendar is adaptive-paper `sessions.py` (2026 only). A
   synchronous rejection, such as a price collar, is recorded as data by HTTP
   status. `--max-consecutive-rejections` ends the run.
4. **State from the websocket.** Order state comes from `trade_updates`, not
   from polling, so the REST budget goes only to submits and cancels. A probe
   is cancelled individually (`DELETE /v2/orders/{id}`) once the stream shows
   it was acknowledged (`pending_new`/`new`/`accepted`). Cancels always take
   priority over new submits. If a probe gets no acknowledgement or no
   terminal event within `stream_timeout_seconds` (`--stream-timeout`,
   default 10 s, bounds 0.5-120 s), submissions freeze and the run cleans up.
   Paper cancel confirmations lagged about 16 s in the 2026-09-24 opening
   auction, so the default freezes there (see "Native paper evidence
   2026-09-24"). Stream events are timestamped on the stream thread
   when they arrive, and REST completions are timestamped on the REST worker.
   Latencies therefore exclude the time an event waits for the main loop.
   A port defect (an exception instead of an HTTP outcome) is recorded, not
   raised. The first one freezes submissions and makes the run `failed`. An
   affected submit becomes ambiguous, so the sweep and reconciliation resolve
   it. Further in-flight failures are recorded the same way.
5. **Cleanup** runs on normal end, STOP, SIGINT/SIGTERM, a freeze or an
   exception. It cancels every live probe individually. It then lists open
   orders and cancels anything left with this run's `client_order_id` prefix,
   including submits whose outcome was ambiguous. A final open-order listing
   must show **zero** open orders with the prefix (`verified_zero_open`).
   The cleanup deadline is `cleanup_timeout_seconds` (60 s) of time outside
   any governor freeze. A 429 backoff during cleanup extends it, up to a hard
   ceiling of the timeout plus 3 x the governor's 60 s maximum backoff (240 s
   by default). A broker delay that outlasts the ceiling is still honoured,
   so cleanup then ends unverified. If a verification listing is incomplete or still shows
   orders, the sweep and verification run again, at most 3 rounds, within the
   ceiling. A failing step is recorded in `step_errors`, and the next step
   still runs. A 429 storm longer than the ceiling ends as `needs_attention`
   with `verified_zero_open: false`. In that case, use `recover` (below).
6. **Reconciliation (bounded, at the end only).** It lists all orders
   submitted since the run started and compares them with the local and
   stream record. The listing is paged (at most 20 pages), and the governor
   admits every page. No page goes out unadmitted. Any of the following makes the run
   unclean: an order missing at the broker, an unknown order with the prefix,
   a stream/REST terminal-status mismatch, a non-terminal order, a filled
   probe, an unresolved ambiguous submit, or any changed position. The whole
   nonzero-position snapshot is compared with the preflight, not only the
   probe symbol (`all_positions_unchanged`, `changed_position_symbols`).

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
  10000 USD), 429s (`max_http_429` 5 tolerated; the run stops on the next
  one, so 0 stops at the first), consecutive rejections and in-flight
  REST calls (`--inflight` 4). The run must also finish inside the current
  session segment. The submission phase ends early enough to leave room for
  the stream start (15 s), the cleanup ceiling (240 s), reconciliation (30 s)
  and a 30 s margin, which is 315 s by default.
- **Durable journal and crash recovery.** A paper run writes an append-only
  JSONL journal (mode 0600, created exclusively). The default path is
  `<output>.journal.jsonl`; set it with `--journal`. The start record
  carries the `client_order_id` prefix and is fsynced before the stream
  starts and before any order is sent. Each probe intent is written and
  flushed before its POST, and the end record is fsynced. After SIGKILL, OOM
  or power loss, `capacity.py recover --journal ...` cancels every open order
  with that prefix, individually and through the governor, and verifies zero
  open. Its preflight reads only `GET /v2/account` on the trading endpoint
  (identity and rate headers), so a market-data outage or a symbol-specific
  data failure cannot block it. The prefix alone is enough, even if the last intent lines were lost.
  `audit` lists the prefix's orders read-only. Like adaptive-paper's STOP,
  which blocks entries but never cancels, the STOP file does not block
  `recover`.
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
at 180/min. The receipt then shows `effective_limit: 200`.

**Avoid the opening auction.** Start paper runs at least about 15 minutes
after the 09:30 ET open. On 2026-09-24 the paper endpoint took about 16 s to
confirm cancels on `trade_updates` right after the open, and the default
10 s stream timeout froze the run (`stream_terminal_missing`). If a run must
start earlier, raise the timeout, for example `--stream-timeout 30`
(`stream_timeout_seconds`, 0.5-120 s, default 10; recorded in the receipt's
`config`). A raised timeout only avoids the freeze. With `--max-open-orders`
10 and 16 s confirmations, throughput is bounded well below the target, so an
opening-auction run is not expected to meet the capacity criteria.

After a crash, or when a receipt shows `verified_zero_open: false`:

```sh
# read-only: counts of this run's orders by status
"$PY" blueprints/us-equities/order-throughput/capacity.py audit \
  --env-file "$ENV_FILE" --journal "$PRIVATE_OUTPUT/capacity-200.journal.jsonl" \
  --output "$PRIVATE_OUTPUT/capacity-200-audit.json"
# cancel every open order with the journal's prefix, then verify zero open
"$PY" blueprints/us-equities/order-throughput/capacity.py recover \
  --env-file "$ENV_FILE" --journal "$PRIVATE_OUTPUT/capacity-200.journal.jsonl" \
  --output "$PRIVATE_OUTPUT/capacity-200-recover.json"
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Completed, and the capacity criteria were met (recover/audit: completed) |
| 1 | Completed, but below target |
| 2 | Refused before any order |
| 3 | `needs_attention`, `failed`, or cleanup/reconciliation not clean |

## Acceptance criteria for a capacity run

These criteria are frozen: at least 5 consecutive full windows at a ratio
of at least 0.85. `--required-windows` and `target_actions_ratio` can be set
lower for exploratory runs. `acceptance.passed` is then false, with the
blocker `criteria_below_frozen_minimum`. A run reports `acceptance.passed`
only when its evidence class is `native_paper`, the frozen criteria apply,
and **all** of the following hold:

- **Sustained.** At least `ceil(0.85 * effective_limit)` **completed** order
  actions in each of 5 consecutive full 60-second windows. That is **170
  actions/min at a 200 limit** and 850 at 1000. Completed actions are
  broker-accepted (2xx) submits and acknowledged (2xx) cancels, counted in
  the window where they were sent. Rejected submits (for example 422 or
  403), 429s, unsent calls and refused cancels are reported as attempted
  actions and never count toward the target. At a 200 limit this means about 85 submits plus 85 cancels per
  minute. A target of "170 submits/min" is impossible with individual cancels,
  because it would need about 340 calls/min. The arithmetic is in
  `rate-limit-evidence-20260924.json`.
- **0 unhandled 429.** Each 429 froze admissions for its backoff, and the
  affected submit, cancel or read was later resolved (for example, an
  ambiguous submit was proven created or not created by the complete
  listing).
- **100% websocket completeness.** Every order known to exist had a stream
  acknowledgement and a terminal event. An order is known to exist if REST
  accepted it, the stream reported it, or the final broker listing shows it.
  The last case includes an ambiguous submit whose order was created. A
  stream `rejected` event counts as both an acknowledgement and a terminal
  event.
- **Clean reconciliation.** See step 6 above.
- **Cleanup verified.** Zero open orders with this run's prefix at the end.
- **No unexpected fills.**
- **No health freezes.** Any freeze fails the run, for example
  `stream_stop_failed`, `client_id_collision`, `requote_failed` or
  `port_exception`.

`acceptance.passed` is **self-reported** by the harness
(`passed_is_self_reported: true`). Under
`docs/acceptance-evidence-policy.md`, the harness's own `passed` field is not
independent confirmation, and the reconciliation uses the same port and
session as the run. Native acceptance therefore also needs an observation by
a separate method. For example, check the Alpaca dashboard or the account
activity export for the run's prefix against the receipt's submit, cancel and
status counts. The `audit` command is a later read-only listing through the
same port, which makes it weaker evidence than the dashboard.

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
- Per-window completed and attempted submits, cancels and order actions.
- Websocket completeness.
- Cleanup and reconciliation results.
- The acceptance block, with `passed_blockers`.
- Provenance: git revision, SHA-256 of the harness and adaptive-paper source
  files it uses, the alpaca-py and Python versions, the argument vector with
  path values replaced by `<path>`, the end time and the exit code.

It contains no credentials, account identifier or account hash, and no broker
order IDs. The journal holds the prefix, configuration and per-probe
client order IDs. It contains no secrets, account identity or broker order
IDs.

## Files

| File | Role |
|---|---|
| `capacity.py` | Engine (`CapacityRun`), configuration and bounds, cancel-all guard, journal and `recover`/`audit`, receipt, CLI |
| `rate_governor.py` | Token bucket + rolling window + remaining/reset + 429 backoff |
| `alpaca_capacity_port.py` | Native paper port; reuses adaptive-paper `transport` read-only |
| `capacity_fixture.py` | Offline fake clock, broker and `trade_updates` stream |
| `rate-limit-evidence-20260924.json` | Cited limits, repository-measured header counts, round-trip arithmetic |
| `rate_limit_evidence.py` | Rebuilds or `--check`s that JSON from the committed trial receipts |
| `evidence/` | Native paper receipts of 2026-09-24, their sanitization index and the independent observation |

## Evidence status (2026-09-24)

| Status | What |
|---|---|
| Measured (offline fixture) | The governor and engine under 200 and 1000 headers, a header rise, 429 freeze/backoff (including during cleanup), refusals, cleanup, and reconciliation, including a lost response for a created order. Also: per-page listing admission, several in-flight calls completing out of order, the real `ThreadPoolExecutor` path, failing in-flight port calls, and crash then journal recovery. See `tests/test_order_throughput.py`. |
| Measured (repository files) | 419 trading-origin `x-ratelimit-limit: 200` and 9 data-origin `10000` headers in the retained adaptive-paper trial outputs. |
| Measured (native paper, 2026-09-24) | One run at a 200/min trading limit met the frozen capacity criteria, and a coordinator-reported SDK listing (no retained artifact) matches its order counts. One pre-market refusal and one frozen opening-auction run are retained. See "Native paper evidence 2026-09-24". `alpaca_capacity_port.py` ran with alpaca-py 0.44.0 at revision `4911baf`. |
| Not yet measured | 1000 order actions/min (the account reports `x-ratelimit-limit: 200`), any run with `--stream-timeout` raised, and any other host. |
| Unverified assumptions | Whether the paper endpoint honours `after_order_id` pagination in practice (it is documented on the Trading API "Get All Orders" reference, updated 2026-05-27, as exclusive and not to be combined with `after`/`until`; adaptive-paper uses the same cursor), exact `trade_updates` event names under load, and Alpaca price-collar behavior for far-from-market limits. |

## Native paper evidence 2026-09-24

These are **capacity measurements, not strategy trades**. Every order was a
non-marketable 1-share SPY DAY limit buy placed 5% below the bid and cancelled
individually. No order filled and no position changed. Nothing here counts as a
strategy trade, fill, signal or performance result. **1000/min is not
measured**, because the account reported `x-ratelimit-limit: 200`.

- **Host class:** WSL2 workstation (Linux x86_64 under Windows), Python 3.12.3,
  alpaca-py 0.44.0, harness revision `4911baf` with default configuration.
  That revision predates `--stream-timeout`, so every run used the 10 s default.
- **Account tier:** every trading-endpoint rate header seen reported
  `x-ratelimit-limit: 200` (1001 headers in the passing run). The data endpoint reported
  10000. The budget was therefore 180 calls/min (headroom 0.9) and the frozen
  target was 170 completed order actions per full 60 s window.

| Receipt (`evidence/`) | Start (UTC) | Session | Result |
|---|---|---|---|
| `capacity-200-20260924.json` | 13:15:31 | PRE | Refused before any order: `quote_stale` (exit 2). Retained non-pass. |
| `capacity-200-20260924-rth.json` | 13:31:31 | RTH (open auction) | 10 orders submitted and accepted, then frozen with `stream_terminal_missing` (exit 3, `needs_attention`). Submit-to-stream-terminal latency was p50 16.1 s and max 16.8 s. Of 15 cancel requests for the 10 orders, 11 returned 204 and 4 returned 422. Cleanup ended with one harness order still open (`verified_zero_open: false`), and reconciliation found seq 10 non-terminal. Retained non-pass. |
| `capacity-200-20260924-rth-recover.json` | 13:32 | recover | About 20 s after the frozen run ended, the broker listed all 10 of that prefix's orders as `canceled`. Recover issued 0 cancels and verified zero open (exit 0). |
| `capacity-200-20260924-rth2.json` | 13:50:01 | RTH | **Capacity criteria met (self-reported).** 5 full windows at 180 order actions each (about 90 submits and 90 cancels), 496 submits and 496 cancels, all 2xx. 0 HTTP 429, websocket completeness 1.0 (1488 events), clean reconciliation, 0 open, no fills. Submit-to-stream-terminal latency was p50 0.37 s and p99 2.06 s. Exit 0. |

**Independent observation** (`independent-observation-20260924.json`). On
2026-09-24 the workflow coordinator listed the paper account through the
alpaca-py SDK, separately from the harness code path. It found 496 orders with
the passing run's prefix since its `started_at`, all `canceled`, filled
quantity 0, and 0 positions and 0 open orders. This matches the receipt's 496
accepted submits and 496 acknowledged cancels. It confirms only those counts
and states. It uses the same broker and account, and it does not check the
per-window rates, latencies or websocket completeness. The first coordinator
listing was not retained, so it was re-run at 14:16Z as a retained script
(`evidence/observe-capacity-20260924.py`; alpaca-py 0.44.0, Python 3.12.3). It
reproduced the same counts. Its stdout is kept as
`evidence/observe-capacity-20260924.stdout.json`, with the hashes, the redacted argv and
the exit code in `independent-observation-20260924.json`.

**Finding and fix.** Paper cancel confirmations lagged about 16 s on
`trade_updates` during the opening auction. That is longer than the 10 s
stream timeout, so the harness froze. The fix is a `--stream-timeout` flag
(`stream_timeout_seconds`, 0.5-120 s, default unchanged at 10) plus the
operating rule above: avoid about the first 15 minutes after the open, or
raise the flag. `tests/test_order_throughput.py` (`StreamTimeoutTests`)
reproduces a 16 s confirmation lag in the offline fixture. The default
timeout freezes, and a 30 s timeout completes without a freeze. That is
fixture evidence only. No native run with a raised timeout has been made.

**Sanitization.** `index-20260924.json` records the SHA-256 of each private
original and of each committed copy. It also records host-path redactions,
of which there were none: the harness already writes `<path>` for argv
paths and stores no credentials, account identifiers or broker order IDs,
so the four committed receipts are byte-identical to the originals. The run
journals and stdout captures stay private and only their hashes are recorded.

