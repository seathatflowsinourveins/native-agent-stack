# Minimal native paper broker-fault harness

Gate: `native-fault-behaviour` in `catalogs/us-equities/gates-20260922.json`
(receipt path `blueprints/us-equities/adaptive-paper/native-faults/receipt.json`).
This directory holds the harness, its frozen `plan.json`, this note, the current
live receipt `receipt.json` (the 2026-09-25 18:25Z run on the released engine),
the retained receipt of the 2026-09-24 18:58Z run on the order-contract engine,
`receipt-20260924t185811.json`, the retained receipt of the first passing run,
`receipt-20260924t143905.json` (2026-09-24 14:39Z), the retained receipt of the
earlier incomplete run, `receipt-20260923.json`, and under `evidence/` the
independent observations of the three passing runs' broker orders, a second,
standard-library observation of the 2026-09-25 run by a separate session, the
sanitized run record of the 2026-09-25 run, and that run's host-clock evidence
(five `chrony-20260925t*.txt` snapshots, `host-clock-diagnosis-20260925.txt` and
`host-clock-process-view-20260925t224915z.txt`). The offline
suite `tests/test_native_faults_min.py` is a local synthetic fixture with a fake
transport; it drives the real `runner.Controller` and `safety.Ledger`.

## Native run of 2026-09-25 18:25Z on the released engine: `native_faults_passed`

One live Alpaca paper run at 2026-09-25 18:25:13Z to 18:25:15Z, started by the
native-fault gate-lane worker of that day's live-gates workflow from a clean
worktree at origin/main ae3d3d37, with the pinned runtime (Python 3.12.3,
alpaca-py 0.44.0, nautilus_trader 2.0.0rc5), against the paper account assigned
to that lane as its only order writer. No account id, credential or host path
is recorded. Before the run, one `chronyc tracking` answer put the system clock
0.0009 s from PHC0, the Hyper-V clock that carries the Windows host's time, which
was itself about 0.29 s fast. During the run the host clock was in fact 0.22 to
0.35 s ahead of Alpaca's (**Host clock** below). The offline suite passed under
the pinned runtime (its 24
tests, run together with the 7 of
`tests/test_adaptive_paper_source_hashes_manifest.py`: 31 OK); and GET requests
showed the account active, flat, with zero open orders and the market open.
The process exit code, 0, was retained this time. The raw stdout (135 bytes,
the status line, sha256 `27ca2ff1...`) and stderr (181 bytes, two alpaca-py
stream warnings on a code-1000 socket close, sha256 `9a43dcad...`) stay
private; `evidence/run-20260925t182513.json` records them with the tree
binding, the runtime, the clock check, the offline tests, the GET checks and a
readback of the run's ledger events.

The receipt binds the released engine. Its `harness_sha256` (19d0a9b9...) and
`plan_sha256` (f276b26c...) are unchanged since the 18:58Z run. Its
`engine_sources_sha256` for runner.py (f157be18...), safety.py (7e00d5bb...) and
transport.py (2653682b...) equal the engine entries in `../source-hashes.json`
at ae3d3d37, where all 57 entries of that manifest matched the tree, and
`../order-contract/order_contract.py` (57405f75...) is unchanged. This is the
re-run that the 2026-09-24 binding amendment below requires before the
`native-fault-behaviour` gate is cited for the released engine.
`c04_pre_send_exemption` names both exemptions for the single
`nf-20260925t182513-9a1b9a-c04` client id.

**Binding check (2026-09-25, after review).** `scripts/trading_gates.py` now
compares the six sha256 values this receipt binds with the files in the tree:
`engine_sources_sha256` for runner.py, safety.py, transport.py and
`../order-contract/order_contract.py`, plus `harness_sha256` and `plan_sha256`.
For the three files that `../source-hashes.json` lists, it also compares them with
that manifest. The output gives `source_bindings` counts and lists each difference
under `warnings`. The check is report-only: a stale binding never changes this
gate's status, rung readiness, `errors` or the exit code, so a later engine change
does not fail CI because of this receipt. The warning stays until a re-run
rebinds the receipt. A dated amendment in the gate note does not clear it,
because the receipt still binds the older bytes. `tests/test_trading_gates_bindings.py`
covers the check with synthetic fixtures, and it prints any stale binding in this
tree to stderr without failing.

This is a keep-but-compare choice. Two alternatives were rejected:
- A failing check (an error, or a binding member in the flip condition). Every
  later engine change would then fail CI until a new paper run rebinds the
  receipt.
- A unit test alone. Nobody reads its output at a gate decision.

Overturn condition: make a stale binding an error for this established gate if a
gate decision cites this receipt while the checker lists its binding as stale, or
if the user makes a current binding a rung requirement.

| Case | Outcome | Evidence class | Broker requests |
|---|---|---|---|
| C01 accept resting buy (SPY 1 @ 385.67, bid 771.35) | passed | native_paper | submit 200, `pending_new`, broker id recorded |
| C02 cancel resting | passed | native_paper | cancel 204 plus five reads 200; ledger and fresh snapshot `canceled`, zero filled |
| C05 cancel again | passed | native_paper | DELETE sent (`delete_sent: true`), answered 204, then one read 200; no new freeze reason; `ledger_before` equals `ledger_after` (`canceled`, zero filled) |
| C04 definitive rejection (308.5401, bid 771.35) | passed | native_paper | submit 422, then client-id read 404; ledger `broker_refused` with `{"http_status": 422, "refusal": "sub_penny_minimum_price_variance"}` |

`posts_reserved` was 2 of 4, with one transport build, no stop error and no
interruption. Cleanup proved flat with `runner.reconcile` over a fresh snapshot:
zero open orders, zero positions, cash delta 0.00. The `IN_FLIGHT` marker was
removed and no `CLEANUP_REQUIRED` marker was written. GET requests after the run
again showed zero positions and zero open orders, with cash and equity
unchanged. The ledger readback shows the trial start, the c01 reservation and
three order observations, and the c04 reservation followed by `broker_refused`
(422, `sub_penny_minimum_price_variance`), with no client id outside this run's
prefix. The outcomes repeat both 2026-09-24 passing runs case for case. C05's
second DELETE was again answered 204, so the engine's handling of a 404 or 422
cancel refusal is still offline-tested only, and C04's 422 remains
paper-endpoint evidence.

**Independent observation.**
`evidence/independent-observation-20260925t182513.json` records a listing at
18:25:42Z by the same separate method as the 2026-09-24 observations (the
unchanged `evidence/observe-native-faults-20260924.py`, alpaca-py 0.44.0,
Python 3.12.3). Its stdout is retained byte-identical as
`evidence/observe-native-faults-20260925t182513.stdout.json` (sha256
14d71155...); stderr was empty and the exit code 0. The lane's env file uses
`export NAME=value` lines, which `runner.credentials()` accepts but the
observer's parser does not, so the observer read it through a `sed` pipe that
removed the leading `export ` (no copy on disk). For prefix
`nf-20260925t182513-9a1b9a-` since the receipt's `started_at` it saw one broker
order, `c01`, `canceled` with filled quantity 0, and no other order at all in
that window; the `c04` client-id lookup returned 404; 0 open orders and 0
positions. These match the receipt. The same claim boundary applies as for the
earlier observations: independent of the harness and engine code, not of the
broker, and made by the session that started the run.

**Second independent observation, by a separate session.**
`evidence/observe-native-fault-20260925t184220z.stdout.json` (sha256
19ce56c3...) is the retained stdout of
`evidence/observe-native-fault-20260925t184220z.py` (sha256 6b9cf045...), run
at 18:46:44Z to 18:46:45Z by a subagent session that did not start the run,
with an empty stderr and exit code 0. The script uses only the Python standard
library (`urllib`, Python 3.12.3 run with `-I -B`) and imports no harness,
engine, order-contract or alpaca-py code; it sends only GET requests, refuses
redirects, and exits 3 after one request if the credentials belong to another
account. It sent 9 GETs, all answered 200 except the expected 404 for `c04`,
and matched the receipt on 29 of 29 checks (`all_match: true`, no mismatches):
a complete order listing since the receipt's `started_at` minus 300 s held
exactly one order, `c01` (SPY buy 1 limit 385.67 day, not extended hours),
canceled at 18:25:14.525Z inside the receipt window with filled quantity 0 and
no fill activity; the `c04` client-id lookup returned 404; there was no fill
activity on the account since then, 0 open orders and 0 positions; cash and
equity equal the pre-run GET probe (compared, not printed); and `plan.json`
equals the receipt's `plan_sha256`. A read-only, immutable open of the run's
private ledger (sha256 1930c84a...) found `c01`'s recorded broker id equal to
the broker's order, `c04` `broker_refused` with no broker id, intents exactly
`c01` and `c04`, and no foreign intent, execution or position row; that
cross-check reads the engine's own record. The 8 fields the 18:25:42Z alpaca-py
observer also reports have identical values. Limits: GET requests cannot show
the run's own HTTP answers (the C01 200, the C02 and C05 DELETE 204s, the C04
422 body) or their order; the observer uses the same broker API and account as
the harness; and its synthetic self-test (24 of 24 passed: a matching world
exits 0, 12 injected mismatches exit 1, a wrong account exits 3, an unsafe env
file exits 2 without a request, a redirect is refused, only GET is sent) stays
in the lane's private scratch and is not committed.

**Host clock (added 2026-09-25 after review).** During the run the host clock was
0.22 to 0.35 s ahead of Alpaca's clock. The ledger reserved c01's submit at
18:25:14.702Z, before the POST was sent, and Alpaca stamped that order
`submitted_at` 18:25:14.480Z. The GET probes' broker-clock readings, 33 s before
and 27 s after the run, cap the offset at 0.35 s at those times.

The pre-run reading of 0.0009 s does not contradict this. Two chronyd daemons
were steering the one kernel clock:
- One follows PHC0, the Hyper-V PTP clock that carries the Windows host's time.
  That clock was about 0.27 to 0.29 s fast. Between the other daemon's steps the
  clock was pulled forward again, toward PHC0 time: before each of its steps
  sampled from 18:54Z to 18:57Z, the other daemon measured it about 0.28 s ahead
  again. How this daemon moves the clock (slewing or stepping) was not captured.
  The 0.0009 s snapshot (`evidence/chrony-20260925t182439z-before-run.txt`, all
  13 lines) was this daemon's answer. The same snapshot also shows RMS offset
  0.083 s, Frequency 12.063 ppm slow and Residual freq -3087.581 ppm.
- The other is this distribution's own chronyd, which follows internet NTP
  servers. It was restarted at 18:09:44Z with clock control on and
  `makestep 0.1 -1`. From then to 19:00Z it stepped the clock back 45 times by
  0.10 to 0.50 s, about once a minute, and forward once (+0.124 s at 18:46:23Z).
  The lane's unsaved 18:22:44Z reading (38.28.93.135, last offset +0.375 s,
  4012 ppm fast) was this daemon's answer, at its -0.375 s step.

No step reached the run. The last step before it was at 18:24:55Z and the next at
18:25:56Z, and the ledger's 21 request times increase monotonically. The engine's
0.25 s clock check (`validate_preflight`, `runner.py:703-704`) is not part of this
harness (`harness.py:42`, `harness.py:296-314`), so the run neither passed nor
failed it. No case outcome depends on the offset. A clock that runs ahead makes
quotes look older, not future-dated. Both observations compared broker timestamps
with the receipt window, and both fall inside it. On host time, `submitted_at` is
1.146 s after the window opens and `canceled_at` 0.599 s before it closes.
Corrected for the host's 0.22 to 0.35 s lead, those margins are 1.37 to 1.50 s
and 0.25 to 0.38 s.

The evidence is in these files:
- The other four `evidence/chrony-20260925t*.txt` snapshots. Like the pre-run
  snapshot, they are byte-identical copies of the lanes' private files under
  `~/.local/state/native-agent-stack/live-gates-20260925/`, including
  `ladder-1x/chrony-series.txt`.
- `evidence/host-clock-diagnosis-20260925.txt`, captured at 21:37Z. It holds the
  Hyper-V clock name, the configuration change, two command sockets per loopback
  address, ten queries alternating between the two daemons, and the journal.
- `evidence/host-clock-process-view-20260925t224915z.txt`, captured at 22:49Z
  after the second review, because the 21:37Z capture holds no `ps` output. Only
  this distribution's chronyd (systemd MainPID 2546733, started 18:09:44Z, the PID
  in the journal) and one child process of it are visible here, while both
  sockets and the alternating answers remain. That the PHC0 daemon runs outside
  this distribution's process view is an inference from these observations.
- The `host` section of the run record.

Time sync was not changed. Before the next timed paper run on this host, it must
be made single-source, because a backward step during a run raises
`request_clock_moved_backward` (`safety.py:1100-1101`).

## Run of 2026-09-24 18:58Z on the order-contract engine, retained as `receipt-20260924t185811.json`

This run's receipt was `receipt.json` until the 2026-09-25 run replaced it; it
is kept byte-for-byte as `receipt-20260924t185811.json` (sha256 d7f1cf2f...).

One live Alpaca paper run at 2026-09-24 18:58:11Z to 18:58:12Z, started by the
workflow coordinator from the #198 branch head 81cbb06e after the order-contract
boundary was wired into every submit (see "Order-contract boundary" below). Same
host class, pinned runtime and dedicated paper account as the 14:39Z run; no
account id, credential or host path is recorded. The raw stdout stays private
(231 bytes, sha256 `1481924e...`, byte-identical to the 14:39Z run's stdout: a
stream-restart line and the status line, neither with a timestamp). The exit
code was not retained; by harness design `native_faults_passed` is the exit-0
status.

That receipt binds main's tree at 3b7ae710. Its `harness_sha256` (19d0a9b9...), `plan_sha256`
(f276b26c...) and `engine_sources_sha256` for runner.py (8bb8d577...), safety.py
(ad520fc4...), transport.py (34e6c4e6...) and `../order-contract/order_contract.py`
(57405f75...) equal the SHA-256 of those files on main after #198 merged (checked
at 3b7ae710), and the runner, safety and transport values equalled the engine
entries in `../source-hashes.json` until the engine-release merge (amendment
below). `c04_pre_send_exemption` names both
exemptions (the `FaultLedger` price-increment check and the `FaultTransport`
order-contract price increment), each for the single `nf-20260924t185811-6ddd39-c04`
client id.

Amendment, 2026-09-24 (engine-release merge): the adaptive-paper engine release
of that day (0b492619 and its review follow-up 1cf633e4), merged with main after
this run, changed runner.py, safety.py and transport.py, including the REST
observation path, `Ledger.record_order` and the `GuardedSession` read allowlist
this receipt exercised; it did not change harness.py, plan.json or
`../order-contract/order_contract.py`. Since that merge the receipt's runner,
safety and transport values no longer equal `../source-hashes.json`, so the
receipt qualifies the order-contract engine before that release. Before the
`native-fault-behaviour` gate is cited for the released engine, this plan (C01,
C02, C05, C04) must run again on it and bind its source hashes. The 2026-09-25
run (top of this note) did so.

| Case | Outcome | Evidence class | Broker requests |
|---|---|---|---|
| C01 accept resting buy (SPY 1 @ 384.06, bid 768.12) | passed | native_paper | submit 200, `pending_new`, broker id recorded |
| C02 cancel resting | passed | native_paper | cancel 204 plus five reads 200; ledger and fresh snapshot `canceled`, zero filled |
| C05 cancel again | passed | native_paper | DELETE sent (`delete_sent: true`), answered 204, then one read 200; no new freeze reason; `ledger_before` equals `ledger_after` (`canceled`, zero filled) |
| C04 definitive rejection (307.2601, bid 768.15) | passed | native_paper | submit 422, then client-id read 404; ledger `broker_refused` with `{"http_status": 422, "refusal": "sub_penny_minimum_price_variance"}` |

`posts_reserved` was 2 of 4, with one transport build, no stop error and no
interruption. Cleanup proved flat with `runner.reconcile` over a fresh snapshot:
zero open orders, zero positions, cash delta 0.00, and the `IN_FLIGHT` marker
was removed. The outcomes repeated the 14:39Z run case for case, now through the
order-contract boundary: the transport sends a POST only after `build_envelope()`
and the body-equals-envelope wire check pass, so C01's 200 and C04's 422 both
followed those checks, and C04 carried its exact sub-penny price only through
the named exemption. The receipt records the request statuses, not the checks
themselves. C05's second DELETE was again answered 204, so the engine's handling
of a 422 cancel refusal is still offline-tested only.

**Independent observation.**
`evidence/independent-observation-20260924t185811.json` records a listing at
18:58:28Z by the same separate method as the 14:39Z observation (the unchanged
`evidence/observe-native-faults-20260924.py`, alpaca-py 0.44.0, Python 3.12.3).
Its stdout is retained byte-identical as
`evidence/observe-native-faults-20260924t185811.stdout.json` (sha256
0c047ba0...); stderr was empty and the exit code was not retained. For prefix
`nf-20260924t185811-6ddd39-` since the receipt's `started_at` it saw one broker
order, `c01`, `canceled` with filled quantity 0; the `c04` client-id lookup
returned 404; 0 open orders and 0 positions. These match the receipt. The same
claim boundary applies as for the 14:39Z observation: independent of the harness
and engine code, not of the broker. Its `subject_receipt` names `receipt.json`,
which held this run's receipt when the observation was made; its client-id
prefix identifies the run, now retained as `receipt-20260924t185811.json`.

## First passing native run (2026-09-24 14:39Z), retained as `receipt-20260924t143905.json`

This run's receipt was `receipt.json` until the 18:58Z run replaced it; it is
kept byte-for-byte as `receipt-20260924t143905.json` (sha256 e3cec5a6...).

One live Alpaca paper run at 2026-09-24 14:39:05Z to 14:39:06Z, started by the
workflow coordinator from this branch's code at commit 8051464. The host class
is the WSL2 workstation (Linux, Python from the pinned adaptive-paper runtime),
against a paper account dedicated to this PC. No account id, credential or
host path is recorded. The raw stdout stays private (231 bytes, sha256
`1481924e43f2867e5e62338ab60bb5b60cbe9ff9df3f54c36f8fa348f082ecac`). The run
wrote `receipt.json` in place, replacing the 2026-09-23 receipt, which is kept
byte-for-byte as `receipt-20260923.json`.

That receipt bound the tree of its run. Its `harness_sha256` (3f01fb31...),
`plan_sha256` (f276b26c...) and `engine_sources_sha256` for runner.py
(a6101294...), safety.py (ad520fc4...) and transport.py (b92e8752...) equalled
the SHA-256 of those files and the engine entries in `../source-hashes.json` at
that time. The order-contract change later edited harness.py, runner.py and
transport.py (see "Order-contract boundary" below).

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
404 or 422 as data. So `broker_refusal_observed` is false. Natively, the case
shows only that the engine sends the repeat DELETE and stays consistent with a
204 answer (both native runs received 204). Its handling of a 404 or 422
answer to that DELETE is covered only by the offline tests.

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

**Gate status.** `scripts/trading_gates.py` lists `native-fault-behaviour`
as a flip candidate (`/status == "native_faults_passed"` holds). The ladder allows a
status change "only by a dated commit after the checker lists the gate as a flip
candidate". The gate note adds that "native (non-synthetic) faults were actually
exercised ... is qualified manually before the dated commit that flips this
gate". `docs/acceptance-evidence-policy.md` says "Parsing a wrapper's own
`passed` field is not independent confirmation", so the qualification uses the
independent observation below. The gate was flipped to `established` (evidence
class `native_proven`, the ladder's class for paper-run gates) in a separate
dated commit on 2026-09-24, whose note cites the receipt, the independent
observation and the Codex review of 8051464. The engine's handling of a 422
cancel refusal stays offline-tested only, and the C04 422 is paper-endpoint
evidence only. The 18:58Z run above re-established the same status on the
order-contract engine, and the 2026-09-25 run on the released engine; the
gate's `receipt_path` now resolves to the 2026-09-25 receipt, whose `/status`
is also `native_faults_passed`. The flip condition checks only that `/status`.
The binding to the released engine rests on the hash comparison in
`evidence/run-20260925t182513.json`, and `scripts/trading_gates.py` repeats that
comparison on every run as a report-only warning (**Binding check** above).

## Independent observation of the 14:39Z run

`evidence/independent-observation-20260924.json` (unchanged) names
`receipt.json` as its subject: that path held the 14:39Z run's receipt when the
observation was made, and its client-id prefix `nf-20260924t143905-29d7ec-`
identifies that run, now retained as `receipt-20260924t143905.json`. It records a listing made by the
workflow coordinator at 2026-09-24 15:01:47Z by a separate method: an alpaca-py
0.44.0 script (`evidence/observe-native-faults-20260924.py`, sha256
6f4b1c19...) on Python 3.12.3, not `harness.py` and not the engine transport.
Its stdout is retained byte-identical as
`evidence/observe-native-faults-20260924.stdout.json` (sha256 420d762c...);
stderr was empty and the exit code 0.

For prefix `nf-20260924t143905-29d7ec-` since the receipt's `started_at` it saw
one broker order, `c01`, `canceled` with filled quantity 0. The client-id lookup
for `c01` returned the same. The lookup for `c04` returned 404, so no broker
order exists for it. There were 0 open orders and 0 positions. These counts
match the receipt: one accepted submit (C01, later canceled), one submit
refused with 422 that created no order (C04), cleanup flat.

The observation uses the same broker API and account, so it is independent of
the harness and engine code, not of the broker. It confirms only these
broker-side facts. It does not observe the run's own HTTP statuses (C04's 422
body, C05's 204 DELETE answer), ledger contents, or the engine's handling of a
422 cancel refusal, which remains offline-tested only.

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

## Order-contract boundary (2026-09-24, after the native run)

The engine transport now validates every submit with the order contract's
`build_envelope()` before any HTTP request (`../README-transport.md`), which also
refuses a sub-penny price. The harness's default transport is therefore
`FaultTransport`: the engine transport except that the single C04 client id is
validated with its price truncated to the cent and then carries its exact
sub-penny price. Every other contract rule, and the wire check that the POST body
equals the envelope, still applies to C04; every other client id is validated as
in the engine. New receipts also bind `../order-contract/order_contract.py` in
`engine_sources_sha256` and name both exemptions in `c04_pre_send_exemption`.

This change edits `transport.py`, `runner.py` and `harness.py`. The retained
`receipt-20260924t143905.json` therefore binds the **older engine**: its
`harness_sha256` (3f01fb31...) and its `engine_sources_sha256` for runner.py
(a6101294...) and transport.py (b92e8752...) do not equal the files here.
safety.py (ad520fc4...) is unchanged. `receipt-20260923.json` already bound an
older engine. The wired boundary was first exercised natively by the 18:58Z run
(now `receipt-20260924t185811.json`); the engine release then changed runner.py,
safety.py and transport.py. The 2026-09-25 run (`receipt.json`, top of this
note) binds the current harness, runner, transport, safety and order-contract
files. Any later change to one of those files leaves that receipt binding the
older file until a new run is recorded, and until then `scripts/trading_gates.py`
lists the difference under `warnings`.

## Run

The harness has no expected-account input. It takes the engine's account-writer
lock for whichever account the env file names (`harness.py:296-301`) and refuses
only a non-flat account (`harness.py:308-310`), so a flat env file of another
lane would send the C01 and C04 POSTs to that lane's account. Follow these
steps (added 2026-09-25 after the second review of PR #278). The run record
shows that the 2026-09-25 run followed steps 1, 4 and 5 and step 3's private
`--out` and retained exit code (`get_checks`, `harness.argv_redacted`,
`harness.exit_code`, `harness.receipt_copy`). Step 2 and step 3's no-ladder
condition were not recorded separately: that run used a fresh state root, its
accepted C01 buy shows that no `STOP` file was present, and the run lane reported
that no harness or engine process was running before it (a worker report, not
part of the run record). Keep every account value private; none is committed.

1. Confirm the account with GET requests only. Load the env file of the paper
   account assigned to this gate lane through `runner.credentials()` and read
   the account, clock, positions and open orders. Compare the first 12 hex digits
   of sha256(account id) with the value the lane keeps privately for its
   assigned account, and stop before any further request on a mismatch.
   Continue only if the account is `ACTIVE` and not trading- or account-blocked,
   holds zero positions and zero open orders, and the clock says the market is
   open.
2. Check that no marker exists: no engine `STOP` file
   (`~/.local/state/native-agent-stack/alpaca-paper/STOP`, `safety.py:39`; while
   it exists the ledger refuses the C01 buy with `stop_blocks_entry`), and no
   `IN_FLIGHT` or `CLEANUP_REQUIRED` in any earlier harness state root used for
   this account. The harness checks only the state root it is given, and refuses
   with exit 2 when a marker is there.
3. Run inside the regular session, at least five minutes before the close, and
   never while a ladder session runs on this host: both use the engine's `STOP`
   file and account-writer lock namespace (`safety.py:39`, `safety.py:366`).
   Write the receipt to a private path, not to the tracked `receipt.json`, and
   keep the exit code:

   ```
   ~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python \
     blueprints/us-equities/adaptive-paper/native-faults/harness.py run \
     --env-file ~/.config/<private>/alpaca-paper.env \
     --state-root ~/.local/state/native-agent-stack/native-faults \
     --out ~/.local/state/native-agent-stack/<private-lane-dir>/receipt.json
   echo $? > ~/.local/state/native-agent-stack/<private-lane-dir>/harness.exit
   ```
4. Repeat the GET probe of step 1 after the run: same account, zero positions,
   zero open orders.
5. Retain the current `receipt.json` under a dated name, copy the private receipt
   to `receipt.json` byte for byte, and check that both copies have the same
   sha256.

The harness uses these interfaces:

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
pre-send check for every client id. No reproducible way to cause such a fault
was identified within this plan's bounds. This is an inference from the
documentation and the engine's own pre-send checks, not an observation that
those statuses cannot occur:

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
described under "Gate status" above. The 18:58Z receipt meets the same items on
the order-contract engine, with the same C05 204 and without a retained exit
code. The 2026-09-25 receipt meets them on the released engine, with the same
C05 204, and its exit code 0 is retained in `evidence/run-20260925t182513.json`.

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
