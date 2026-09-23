# Minimal native paper broker-fault harness

Gate: `native-fault-behaviour` in `catalogs/us-equities/gates-20260922.json`
(receipt path `blueprints/us-equities/adaptive-paper/native-faults/receipt.json`).
This directory holds the harness, its frozen `plan.json`, this note and the
first live receipt `receipt.json`. The offline suite
`tests/test_native_faults_min.py` is a local synthetic fixture with a fake
transport; it drives the real `runner.Controller` and `safety.Ledger`.

**With the current engine a live run cannot reach `native_faults_passed`.**
C04 is refused by the Ledger before any POST is sent, and C05 short-circuits
on a client-id lookup without sending a DELETE. A live run therefore yields
partial native evidence only (C01 and C02), with the best status
`native_faults_incomplete`.

The one live run (2026-09-23 14:20:24Z, from a read-only `git archive` of the
harness commit) went exactly that way. The plan and engine source hashes in
the receipt match this tree; its `harness_sha256` (742fb666...) is the harness
as run. `harness.py` was changed after the run so that an exception inside
cleanup still writes `CLEANUP_REQUIRED` and a receipt (the run itself cleaned
up without error), so the next run binds a new harness hash.

| Case | Outcome | Evidence class | Broker requests |
|---|---|---|---|
| C01 accept resting buy (SPY 1 @ 384.58, bid 769.16) | passed | native_paper | submit 200, `pending_new` |
| C02 cancel resting | passed | native_paper | cancel 204 plus six reads 200, `canceled` |
| C05 cancel again | passed | engine_short_circuit | one read 200, no DELETE; the order was found terminal by client id |
| C04 definitive rejection (307.6601) | unobserved | none | none; refused before send, `invalid_price_increment` |

Cleanup proved flat with zero open orders by `runner.reconcile` (cash delta
0.00). One POST was reserved out of the four allowed. Status:
`native_faults_incomplete`, so the gate stays `not_established`.

## Run

```
~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python \
  blueprints/us-equities/adaptive-paper/native-faults/harness.py run \
  --env-file ~/.config/<private>/alpaca-paper.env \
  --state-root ~/.local/state/native-agent-stack/native-faults \
  --out blueprints/us-equities/adaptive-paper/native-faults/receipt.json
```

Run it during regular hours, at least five minutes before the close. The
harness uses these interfaces:

- Credentials come from `runner.credentials()`. The file must be mode 0600,
  owned by you and outside any Git worktree, and is read only in-process.
- The state root must be under `~/.local/state/native-agent-stack/`. It cannot
  be that directory itself or the engine default (`alpaca-paper`). Each run
  gets a fresh `nf-<utc>-<hex>` directory with its own ledger.
- Exit codes: 0 means `native_faults_passed`; 2 means not started or refused
  before any write; 3 means `cleanup_required`; 1 covers everything else,
  including `native_faults_incomplete`.

## Cases and bounds

The run makes one `AlpacaPaperTransport`, starts it once and binds it to the
engine `Controller` and `Ledger`. The four cases then run in order on that
transport:

| Case | Action | Pass (judged from ledger state) |
| --- | --- | --- |
| C01 accept_resting_buy | SPY qty-1 DAY limit at 50% of the streamed bid, rounded down to the cent | Broker accepts; ledger shows submitted, broker id recorded, open, zero filled |
| C02 cancel_resting | Engine cancel | Ledger `canceled`, zero filled; a fresh broker snapshot shows `canceled` |
| C05 cancel_again | Engine cancel again | No exception, no new transport freeze reason, ledger and effect unchanged. Receipt records `delete_sent` and `broker_refusal_observed` |
| C04 definitive_rejection | SPY qty-1 limit at 40% of the bid plus $0.0001 (at least $1) | Every submit status is one of the engine's definitive refusals (401, 403, 404) and the ledger shows `broker_refused` with no position or cash effect. Any other status (400, 422, 429, 5xx) fails. If the Ledger refuses before send, the case is `unobserved` with reason `engine_refused_before_send: invalid_price_increment` |

The plan's `c04_sub_penny_increment` must be strictly between 0 and 0.01.

Bounds:

- Signal handlers go in before the transport is built. A SIGINT or SIGTERM
  stops new buy admissions and ends the case sequence. A second signal that
  arrives while cleanup is running logs `<SIG> received: cleanup in progress;
  not aborting, waiting for flat proof` to stderr and does not abort cleanup.
- The run refuses to start unless the account is flat with zero open orders
  (via `transport.snapshot()`). It also takes the engine's account-writer lock.
  The lock is taken after `transport.start()` opens the streams but before any
  write. It cannot come earlier: the transport's REST client sends every request
  through the owner loop that only `start()` sets, and a second client is out of
  bounds.
- Before the first POST the harness writes `IN_FLIGHT` in the run directory.
  The marker holds the run id and the client-id prefix. It is removed only
  after cleanup proves flat, or when no write was ever attempted. SIGKILL or a
  host crash skips cleanup and leaves `IN_FLIGHT` in place. Recover by hand:
  cancel orders with that prefix, confirm the account is flat, then delete the
  marker. While `IN_FLIGHT` remains, the receipt status is `cleanup_required`.
- At most `max_posts` (4) POSTs, enforced ahead of the engine's own request
  budget.
- It never retries and stops after the first failed or errored case.
- Cleanup always runs in `finally` on the same started transport:
  1. It cancels every non-terminal ledger intent that carries this run's
     client-id prefix.
  2. It proves flat with `runner.reconcile` over a fresh snapshot.
  3. If that fails, it writes `CLEANUP_REQUIRED` in the run directory and
     keeps `IN_FLIGHT`.

## Receipt honesty

- A case is marked `native_paper` only when the transport's request observer
  recorded a broker HTTP response within that case. For C05 the response must
  come from the DELETE itself. A C05 whose only request was the client-id GET is
  marked `engine_short_circuit` with `delete_sent: false`.
- Unobserved and not-run cases are marked `none`.
- `status` becomes `native_faults_passed` only when all four cases pass with
  `native_paper` evidence and cleanup proves flat.
- The receipt records per-case request kinds and statuses, the engine ledger
  state, and the SHA-256 hashes of the plan, harness and engine sources.
- It does not record credentials, the account id or the account fingerprint.
- The price reference is the engine's streamed quote bid. The engine transport
  has no last-trade read.

## Expected outcome from source reading (confirmed by the 2026-09-23 run)

- **C04 will be `unobserved`.** `Ledger.reserve_intent` refuses any price of
  at least $1 that is not on a whole cent (`invalid_price_increment`), so no
  POST is sent. The offline suite shows this path with the real Ledger. If the
  request were sent, the transport maps Alpaca's 422 to `AmbiguousSubmission`,
  and `Ledger.mark_broker_refused` accepts only 401, 403 and 404. So this
  engine cannot record a 422 as a definitive refusal.
- **C05 will not provoke Alpaca's 422.** `AlpacaPaperTransport.cancel` looks
  the order up by client id and returns it without a DELETE once it is
  terminal. The receipt records this as evidence class `engine_short_circuit`,
  `delete_sent: false` and `broker_refusal_observed: false`.
- For these reasons one run of this harness cannot flip the gate on its own. A
  `native_faults_incomplete` receipt is the honest expected result.
