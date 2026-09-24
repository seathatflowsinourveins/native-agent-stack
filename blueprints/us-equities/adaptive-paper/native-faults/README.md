# Minimal native paper broker-fault harness

Gate: `native-fault-behaviour` in `catalogs/us-equities/gates-20260922.json`
(receipt path `blueprints/us-equities/adaptive-paper/native-faults/receipt.json`).
This directory holds the harness, its frozen `plan.json`, this note, the current
live receipt `receipt.json` (the 2026-09-24 run) and the retained receipt of the
earlier incomplete run, `receipt-20260923.json`. The offline suite
`tests/test_native_faults_min.py` is a local synthetic fixture with a fake
transport; it drives the real `runner.Controller` and `safety.Ledger`.

## Native run of 2026-09-24: `native_faults_passed`

One live Alpaca paper run at 2026-09-24 14:39:05Z to 14:39:06Z, started by the
workflow coordinator from this branch's code at commit 8051464. The host class
is the WSL2 workstation (Linux, Python from the pinned adaptive-paper runtime),
against a paper account dedicated to this PC. No account id, credential or
host path is recorded. The raw stdout stays private (231 bytes, sha256
`1481924e43f2867e5e62338ab60bb5b60cbe9ff9df3f54c36f8fa348f082ecac`). The run
wrote `receipt.json` in place, replacing the 2026-09-23 receipt, which is kept
byte-for-byte as `receipt-20260923.json`.

The receipt binds this tree. Its `harness_sha256` (3f01fb31...), `plan_sha256`
(f276b26c...) and `engine_sources_sha256` for runner.py (a6101294...), safety.py
(ad520fc4...) and transport.py (b92e8752...) equal the SHA-256 of those files
here and the engine entries in `../source-hashes.json`. The later merge of
origin/main changed none of these five files.

| Case | Outcome | Evidence class | Broker requests |
|---|---|---|---|
| C01 accept resting buy (SPY 1 @ 382.96, bid 765.92) | passed | native_paper | submit 200, `pending_new`, broker id recorded |
| C02 cancel resting | passed | native_paper | cancel 204 plus five reads 200; ledger and fresh snapshot `canceled`, zero filled |
| C05 cancel again | passed | native_paper | DELETE sent (`delete_sent: true`), answered 204, then one read 200; no new freeze reason; `ledger_before` equals `ledger_after` (`canceled`, zero filled) |
| C04 definitive rejection (306.3601) | passed | native_paper | submit 422, then client-id read 404; ledger `broker_refused` with `{"http_status": 422, "refusal": "sub_penny_minimum_price_variance"}` |

`posts_reserved` was 2 of 4, with one transport build, no stop error and no
interruption. Cleanup proved flat with `runner.reconcile` over a fresh snapshot:
zero open orders, zero positions, cash delta 0.00. The `IN_FLIGHT` marker was
removed. The receipt does not record the process exit code. By harness design,
`native_faults_passed` is the exit-0 status.

C05 differs from the expectation written before the run: Alpaca paper answered
the DELETE of an already-canceled order with 204, not the 422 its DELETE
reference suggests ("The order status is not cancelable"). The plan accepts 204,
404 or 422 as data. So `broker_refusal_observed` is false, and the case shows
that the engine sends the repeat DELETE and stays consistent with any of the
three answers. It does not show how the engine handles a 422 cancel refusal;
that path is covered only offline.

**What C04's definitive refusal rests on.** Alpaca documents that orders
exceeding the minimum price variance "will be rejected", with the body
`{"code": 42210000, "message": "... sub-penny increment does not fulfill
minimum pricing criteria"}`
(https://docs.alpaca.markets/us/docs/orders-at-alpaca.md). This run observed
that body with HTTP 422 on the first and only POST of the C04 client id. The
limit price 306.3601 violates the two-decimal increment. The follow-up
client-id lookup returned 404, and there was no position or cash effect before
or after. The transport raises `RejectedSubmission(422,
"sub_penny_minimum_price_variance")` only when all of these hold, and the ledger
then records `broker_refused`. This is one observation, on the paper endpoint,
from one host and one account. It confirms the previously inferred 422 for this
body there. It is not evidence for the live endpoint, and it does not make 422
definitive in general. The comments in `safety.py` and `transport.py` still
describe the 422 as inferred. They are left as they are because editing them
would change the engine hashes this receipt binds.

**Gate status.** `scripts/trading_gates.py` now lists `native-fault-behaviour`
as a flip candidate (`/status == "native_faults_passed"` holds). The gate's own
rule still keeps it `not_established` in this change. The ladder allows a
status change "only by a dated commit after the checker lists the gate as a flip
candidate". The gate note adds that "native (non-synthetic) faults were actually
exercised ... is qualified manually before the dated commit that flips this
gate". `docs/acceptance-evidence-policy.md` says "Parsing a wrapper's own
`passed` field is not independent confirmation". The qualification therefore
needs an independent observation that has not been made yet, for example an
order listing by a separate method (not the harness or the engine transport)
for prefix `nf-20260924t143905-29d7ec-`. It would show the C01 order `canceled`
with zero filled, no broker order for the C04 client id, and zero open orders
and positions. The order-throughput `independent-observation-20260924.json` is
the pattern to follow.

## Retained history: the incomplete run of 2026-09-23

Retained as `receipt-20260923.json`, byte-identical to the `receipt.json`
registered before the 2026-09-24 run (sha256 28b9db92...).

The first live run (2026-09-23 14:20:24Z, from a read-only `git archive` of the
harness commit) predates the 2026-09-24 engine change. It produced the
incomplete result in the table below. Its `plan_sha256`, `harness_sha256`
(742fb666...) and `engine_sources_sha256` (runner.py, safety.py, transport.py)
are the pre-change hashes and do not match this tree. Before the engine change,
`harness.py` was also changed after the run, following review: an
exception inside cleanup still writes `CLEANUP_REQUIRED` and a receipt (the run
itself cleaned up without error), a leftover marker from an earlier run
refuses a new start, the write-ahead marker is fsynced, and a failed transport
stop fails the run.

| Case | Outcome | Evidence class | Broker requests |
|---|---|---|---|
| C01 accept resting buy (SPY 1 @ 384.58, bid 769.16) | passed | native_paper | submit 200, `pending_new` |
| C02 cancel resting | passed | native_paper | cancel 204 plus six reads 200, `canceled` |
| C05 cancel again | passed | engine_short_circuit | one read 200, no DELETE; the order was found terminal by client id |
| C04 definitive rejection (307.6601) | unobserved | none | none; refused before send, `invalid_price_increment` |

Cleanup proved flat with zero open orders by `runner.reconcile` (cash delta
0.00). One POST was reserved out of the four allowed. Status:
`native_faults_incomplete`.

The 2026-09-24 engine change closed its two gaps. It was verified offline first,
with unit tests using a fake broker and mocked HTTP, then natively by the run
above:

- C05: `AlpacaPaperTransport.cancel` now sends the DELETE for every owned order
  to its known broker id instead of returning early when a client-id lookup
  shows it terminal. Alpaca's answer is data. A 404 or 422 is accepted without a
  freeze when the follow-up lookup shows the order terminal. The repeated terminal
  observation changes no ledger state.
- C04: Alpaca's documented sub-penny rejection body is recognised as definitive
  only with HTTP 422. See "C04 choice" below.
  The harness's `FaultLedger` lets only the C04 client id past the pre-send
  `invalid_price_increment` check, so Alpaca itself answers the fault.

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
| C05 cancel_again | Engine cancel of the already-canceled order | The DELETE is sent and answered 204, 404 or 422. No exception, no new transport freeze reason, ledger and effect unchanged. Receipt records `delete_sent`, `cancel_http_statuses` and `broker_refusal_observed` |
| C04 definitive_rejection | SPY qty-1 limit at 40% of the bid plus $0.0001 (at least $1), sent by the only client id `FaultLedger` exempts | Either the ledger records `broker_refused` for a 422 carrying the documented sub-penny body, with refusal `sub_penny_minimum_price_variance`, or every submit status is 401, 403 or 404. The client-id lookup returns 404, and there is no position or cash effect. Any other 400, 422, 429 or 5xx fails. If the engine still refuses before send, the case is `unobserved` with reason `engine_refused_before_send: ...` |

The plan's `c04_sub_penny_increment` must be strictly between 0 and 0.01.

Bounds:

- Signal handlers go in before the transport is built. A SIGINT or SIGTERM
  stops new buy admissions and ends the case sequence. A second signal that
  arrives while cleanup is running logs `<SIG> received: cleanup in progress;
  not aborting, waiting for flat proof` to stderr and does not abort cleanup.
- The run refuses to start (status `not_started`, exit 2, before reading
  credentials or building a transport) while any earlier run directory under
  the state root still holds `IN_FLIGHT` or `CLEANUP_REQUIRED`: that run may own
  an order the broker has not shown yet.
- The run refuses to start unless the account is flat with zero open orders
  (via `transport.snapshot()`). It also takes the engine's account-writer lock.
  The lock is taken after `transport.start()` opens the streams but before any
  write. It cannot come earlier: the transport's REST client sends every request
  through the owner loop that only `start()` sets, and a second client is out of
  bounds.
- Before the first POST the harness writes `IN_FLIGHT` in the run directory
  and fsyncs the file and the directory.
  The marker holds the run id and the client-id prefix. It is removed only
  after cleanup proves flat, or when no write was ever attempted. SIGKILL or a
  host crash skips cleanup and leaves `IN_FLIGHT` in place. Recover by hand:
  cancel orders with that prefix, confirm the account is flat, then delete the
  marker. While `IN_FLIGHT` remains, the receipt status is `cleanup_required`.
- At most `max_posts` (4) POSTs, enforced ahead of the engine's own request
  budget.
- It never retries and stops after the first failed or errored case.
- A transport that fails to stop makes the run `error`, never a pass.
- Cleanup always runs in `finally` on the same started transport:
  1. It cancels every non-terminal ledger intent that carries this run's
     client-id prefix.
  2. It proves flat with `runner.reconcile` over a fresh snapshot.
  3. If that fails, it writes `CLEANUP_REQUIRED` in the run directory and
     keeps `IN_FLIGHT`.

## Receipt honesty

- A case is marked `native_paper` only when the transport's request observer
  recorded a broker HTTP response within that case. For C05 the response must
  come from the DELETE itself. A C05 with no DELETE (the engine as run on
  2026-09-23) is marked `engine_short_circuit` with `delete_sent: false`.
- For C04 the receipt records `ledger_refusal`, the ledger's own durable
  `broker_refused` event (HTTP status and refusal). It also records
  `c04_pre_send_exemption`, the one client id that `FaultLedger` exempts.
- Unobserved and not-run cases are marked `none`.
- `status` becomes `native_faults_passed` only when all four cases pass with
  `native_paper` evidence and cleanup proves flat.
- The receipt records per-case request kinds and statuses, the engine ledger
  state, and the SHA-256 hashes of the plan, harness and engine sources.
- It does not record credentials, the account id or the account fingerprint.
- The price reference is the engine's streamed quote bid. The engine transport
  has no last-trade read.

## C04 choice: the documented sub-penny rejection

The alternative was a fault Alpaca answers with 401, 403 or 404, keeping the
pre-send check for every client id. Within this plan's bounds no such fault is
reachable:

- The create-order reference
  (https://docs.alpaca.markets/us/reference/postorder.md) documents only two
  refusals: 403 "Buying power or shares is not sufficient." and 422 "Input
  parameters are not recognized."
- A 403 needs a buy larger than buying power, or a sell of unheld shares. The
  Ledger refuses both before send: a $1,000 order cap on a qty-1 buy, and
  `sell_exceeds_owned_unreserved_position`.
- A 401 needs other credentials, so a second client, which is out of bounds.
- No 404 is documented for this endpoint.
- A non-existent or non-tradable symbol has no streamed quote, so the engine
  refuses it before send (`no_current_quote`, quote-freshness wire guard). Its
  status is also undocumented and would be a 422 at best.

So C04 takes the reclassification the gate text allows: the engine counts a
broker 422 on an invalid price as a definitive refusal. This applies only where
the documentation proves it definitive. The orders guide
(https://docs.alpaca.markets/us/docs/orders-at-alpaca.md, "Sub-penny
increments") says limit prices at or above $1.00 take at most two decimals, and
four below. It says "Orders received in excess of the minimum price variance
will be rejected", and gives the body `{"code": 42210000, "message": "invalid
limit_price 290.123. sub-penny increment does not fulfill minimum pricing
criteria"}`.

That page documents the body and the rejection, not the HTTP status. Before
the 2026-09-24 run, the 422 was an inference: the code's 422 prefix and the create-order reference's only
input-refusal status, 422 "Input parameters are not recognized."
(https://docs.alpaca.markets/us/reference/postorder.md). The 2026-09-24 run
observed it once on the paper endpoint (see above). The engine fails closed if it is wrong: `documented_refusal`
requires status 422, and any other status with this body stays ambiguous.
The code 42210000 alone is not treated as sufficient, since it may be shared
by other 422 refusals (the offline fixtures use it for several). The message
match is the discriminator, and the transport requires both.

422 is not definitive in general. Alpaca also returns it for "client_order_id
must be unique"
(https://alpaca.markets/learn/how-to-fix-common-trading-api-errors-at-alpaca),
which proves that an order exists. The transport therefore requires all of the
following before it raises `RejectedSubmission(422,
"sub_penny_minimum_price_variance")`:

- the documented code and, as the discriminator, the documented message;
- a limit price that really violates the documented increment;
- the first POST of this client id (SDK retries are disabled);
- a client-id lookup that returns 404.

`Ledger.mark_broker_refused` then accepts 422 only with that refusal, and only
for an intent whose durable price violates the increment. Timeout, 400, 422,
429 and 5xx otherwise stay ambiguous, as README-safety.md states.

The pre-send check stays for the engine. The only exemption is the harness's
`FaultLedger`, for its single `<prefix>c04` client id. No engine path can send a
sub-penny price.

## What a qualifying native run must show

This list was written before the 2026-09-24 run and is kept unchanged. That
run's receipt meets every item it can record. It does not record the exit
code, which follows from `native_faults_passed` by harness design. C05's DELETE
answer was 204 rather than the expected 422, and 204 is one of the accepted
answers. Meeting the list makes the receipt
a flip candidate. The dated flip commit still needs the manual qualification
described under "Gate status" above.

A receipt can flip the gate only when it shows all of the following, bound to
this tree's plan, harness and engine hashes:

- Status `native_faults_passed`, exit 0, `posts_reserved` 2 of 4, one transport
  build and no stop error.
- C01 and C02 as before: submit 200 and an open status, then cancel 204 and
  `canceled` in the ledger and in a fresh broker snapshot.
- C05 with evidence `native_paper`, `delete_sent: true` and requests `cancel`
  then `read`. The DELETE status is expected to be 422, since Alpaca's DELETE
  reference documents
  "The order status is not cancelable"; 204 or 404 is also accepted as data.
  `new_transport_freeze_reasons` must be empty and `ledger_before` must equal
  `ledger_after`, both `canceled` with zero filled.
- C04 with evidence `native_paper` and requests `submit` 422 then `read` 404.
  This observation is what confirms the inferred HTTP 422 for the documented
  sub-penny body.
  The ledger shows `broker_refused` with `ledger_refusal` `{"http_status": 422,
  "refusal": "sub_penny_minimum_price_variance"}`, and `effect_before` equals
  `effect_after`.
- If Alpaca answers the sub-penny POST with another code or message, C04 fails
  as ambiguous and the run ends `cleanup_required`. It never passes. The harness
  cannot prove an ambiguous submission flat, so its client id must then be
  resolved by hand. An order accepted despite the sub-penny price (submit 200)
  also fails C04; cleanup then cancels it.
- Cleanup proves flat with `runner.reconcile` and zero open orders, and the
  `IN_FLIGHT` marker is removed.

A run that shows anything else stays partial or failed evidence, and the gate
stays `not_established`.
