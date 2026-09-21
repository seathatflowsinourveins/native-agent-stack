# Explicit paper recovery

`await recover(controller, metadata, config)` uses a fresh, unstarted
`AlpacaPaperTransport` in `controller.port`. The caller holds the same account
writer lock as normal paper execution, checks the stored configuration hash and
account identity, restores the original journal, and sets the port's history
window to the original trial start. `metadata` supplies `trial_id` and
`baseline_cash`. The default reconciliation function is the coordinating
`runner.reconcile`; test-only injection is available as `reconcile_fn`.

This is direct recovery through the selected official Alpaca SDK transport. It
does **not** restart the native strategy engine. Recovery permanently closes the
journal to new entries and renews only its cleanup window. Prior request budgets,
fills, costs, loss limits and order identities remain intact.

The module retires a reservation only when the durable journal proves that no
request was attempted, or when the transport explicitly provides `not_sent=True`
for a request prevented before HTTP. `definitive_rejection=True` alone does not
prove this: an actual HTTP refusal belongs to the controller's separate
`broker_refused` contract. A missing lookup, timeout or ambiguous response never proves that an
order was absent. Attempted orders are adopted by their original client IDs and
reconciled before any new exit. Unknown orders, unmatched positions and cash
differences stop recovery. It never uses account-wide cancellation or liquidation.

All owned open orders are canceled first. Actual terminal confirmation and a
fresh snapshot must precede a residual exit. Exits use sequential SELL-only
LIMIT/DAY orders with fresh quotes and the original per-order quantity/notional
caps. Quantities retain up to nine decimal places. Cleanup client IDs advance
past prior journal IDs, including previous failed cleanup attempts. Fully unfilled
exit cancellation stops with `needs_attention`; there is no blind repricing loop.

An admission freeze alone does not forbid a confirmed owned exit. Lost events,
failed observation callbacks, identity conflicts and incomplete reconciliation
do. All requests still cross the existing transport/controller budget and wire
guards. The order deadline is the minimum of the configured cleanup window, the
ledger window and 120 seconds; asynchronous port teardown has a separate
10-second bound. Cancellation of an awaiting task cannot retract a request that
has already reached the broker. Such outcomes remain unresolved for a subsequent
explicit recovery.

Results identify attempted cleanup client IDs, exact journal residual quantities,
unresolved intents and the last observed broker positions. `flat: true` and
`status: passed` require a fresh final broker reconciliation with zero positions,
zero unresolved orders and no recovery errors. Results never imply strategy
performance or throughput acceptance.

## Verification

```sh
python3 -m unittest tests.test_adaptive_paper_recovery -v
```

The 18 local fault checks use the real durable `Ledger` and a fake broker port.
They cover crash after POST, delayed cancellation, expired trial cleanup,
nine-decimal partial fill exit, unknown exposure, missing attempted-order lookup,
provably unsent reservations, ambiguous exit, unfilled exit cancellation, stable
cleanup IDs, stale quotes, closed market, shared budget exhaustion, explicit stop,
task cancellation, deadline expiry and stream observation integrity. The fake
broker independently checks cash/position agreement; production uses the root
reconciler. These checks are local integration evidence, not broker E2E or
unchanged upstream acceptance.

The dependency baseline is `dda748041859c57499bd4441ebd8ca5fbb8c5bb3` plus the
nine-decimal safety fix `15c5c77fdca5124af28371b272df07ecede5aa86`. This module
reuses the inspected transport and ledger interfaces; it does not add a new SDK,
new broker endpoint, credential reader or execution engine.

A development test initially found that `asyncio.wait_for` handling mislabeled
an underlying broker timeout as the cleanup timer expiring. The adapter now
checks its own `asyncio.timeout` context's expiry flag and preserves ambiguous
broker timeout classification. The failing and passing runs are retained in the
task's local execution history.

The final run passed all 18 checks in 1.213 seconds under Python 3.12 in a fresh
`bwrap --unshare-all --clearenv` namespace without network or credential mounts.
Only the repository, system runtime, public user-name lookup file and temporary
filesystem were exposed. A first sandbox attempt failed before test collection
because the ledger's `Path.home()` needs that public lookup file; the raw failed
run was retained separately. The final stderr receipt SHA-256 is
`62d51eb980f3b70aae7dd3fa1eb4447de67512e7ca671e0dfb6073628294d518`.
Recovery source SHA-256:
`a02fdf5213fe3ed1e9513b90b43701eabdc01daf72862e25e6da1b027f88ce62`;
test source SHA-256:
`a2a503647f5666f5d16c750bebd6c470cb0b11bc46a1fd149be24e9072ffc523`.

`python3 scripts/validate_catalogs.py` and `git diff --check` passed.
`python3 scripts/validate.py` found two existing publication issues outside this
module: a personal path in the integrated native-adapter README and a possible
local session identifier in the transport tests. The coordinator owns those
publication fixes; this failed check is not reported as passed.

A subsequent review tightened the refusal contract above. Two regression tests
distinguish an explicit local `not_sent` guarantee from an actual HTTP refusal
without that guarantee. The prior source hashes and 18-test receipt describe the
earlier version; the revised 20-test local suite passes separately.
