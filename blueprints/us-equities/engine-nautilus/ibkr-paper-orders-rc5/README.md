# IBKR paper orders on NautilusTrader 2.0.0rc5

This build serves the trading north star's bounded SPY paper order qualification
on the selected NautilusTrader destination. It uses the upstream **built-in
ExecTester**, LiveNode and native Interactive Brokers factories. The four case
labels mirror the [frozen 1.231.0 trial](../ibkr-paper-orders/README.md): accept a
resting buy, cancel it, fill a one-share buy, flatten and independently prove flat.

Round r2 enables the bounded trial through runner quote admission and quantity
one while keeping the native risk engine enabled and its cap configured. The
selected pin skips the cap on the SMART/IB route. The receipt retains the
requested statement exactly: "engine notional cap configured, not enforced on
this route (#4946, fixed on develop, unreleased); bound held by qty=1 and quote
admission". Its adjacent release verification corrects the dated "unreleased"
clause: v2.0.0rc6 was published on 2026-10-05 and includes the fix. This build
still pins rc5. The coordinator owns review and broker execution; offline tests
do not establish the `ibkr-local-acceptance` gate.

## Source and decision, 2026-10-05

The selected source is `nautechsystems/nautilus_trader`, tag `v2.0.0rc5`, commit
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`:

- [exec_tester.py](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/examples/live/interactive_brokers/exec_tester.py)
  supplies the builder, IB configs/factories and ExecTester registration.
- [_common.py](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/examples/live/interactive_brokers/_common.py)
  supplies supported timeout and shutdown builder methods.
- [ExecTester strategy](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/testkit/src/testers/exec/strategy.rs)
  supplies the actual market entry, resting-limit maintenance, cancel and close
  behavior. The runner does not implement another order strategy.
- [Hosted LiveNode bindings](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/live/src/python/node.rs)
  support `run_async()` on a Python event loop and independent cache/control
  handles captured before starting it. The wrapper owns signal handling.
- [Risk-engine source](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/risk/src/engine/mod.rs#L1218)
  returns success when the account lookup for the instrument venue fails, before
  applying the configured notional check. The example's instrument venue is
  `SMART`; the adapter uses the broker venue `IB`.

The installed rc5 signatures were inspected and the actual ExecTester, IB and
LiveRiskEngineConfig constructors were exercised offline. The
[rc5 release notes](https://github.com/nautechsystems/nautilus_trader/releases/tag/v2.0.0rc5)
and original tagged Rust sources were also checked. Upstream
[#4946](https://github.com/nautechsystems/nautilus_trader/issues/4946) is **closed**,
but the missing-account branch remains in this selected tag; closed issue state
does not establish a fix in the installed pin. This is source evidence, not an
observed broker failure.

The command center's r2 decision preserves rc5 and the native strategy and
holds admission in the runner. Official client 92 requests timestamped
`reqTickByTickData(..., "BidAsk", 0, False)` followed by `reqCurrentTime()`.
The installed official ibapi 10.45.1 callback signatures were inspected. A
positive, uncrossed quote must be at most ten seconds old against the broker
clock; notices 10089/10167, delayed tick types and delayed data modes refuse.
One times the ask plus USD 10 headroom must fit the USD 1000 cap. The receipt
records bid, ask, age, timestamps, headroom and derived offset. The child checks
the age again and recomputes the cap and offset before constructing the node.

The resting offset is `floor(0.5 * admitted_bid / 0.01)`, following the frozen
trial's half-bid placement. A synthetic USD 770.01 bid gives 38500 ticks; the
native price is its current bid minus USD 385. This keeps the probe far below
market during the bounded trial. An unexpected resting fill remains a failed
case. MARKET entry and close retain upstream behavior; quote headroom is
admission evidence, and observed fill-bound breaches are failures.

Source currency correction, verified through GitHub on 2026-10-05:
[fix ed6fc8bf](https://github.com/nautechsystems/nautilus_trader/commit/ed6fc8bf47fd37dda97d63b9b2df160719ee2bac)
is an ancestor of [v2.0.0rc6](https://github.com/nautechsystems/nautilus_trader/releases/tag/v2.0.0rc6),
published at 03:03:18 UTC. "Fixed on develop, in no release" was accurate in the
retained October 1 metadata and is superseded by that release. Pin migration
and a discriminating native over-limit test are the engine-cap re-run trigger.

The official-ibapi checker, broker `liquidHours` parser and redaction are reused
directly from [the frozen harness](../ibkr-paper-orders/run.py). Only its pure
helpers and official read-only checker are loaded. Its 1.231.0 strategy is never
constructed. The receipt binds that dependency with `source_hashes` in addition
to the new runner and plan hashes.

Round r3 keeps the flat pre-check and quote admission in **one client-92
session**. A small session proxy postpones the frozen check's final disconnect
until the quote is admitted, then closes and joins the message-loop and EReader
threads within the unchanged 30-second check deadline. The official ibapi
10.45.1 `client.py` source supplied with the installed package justifies this:
`connect()` creates EReader and starts the API, `run()` drains its message queue,
and `disconnect()` closes/resets the transport without joining either reader.
Keeping that session removes the immediate same-id reconnect boundary.

Quote diagnostics retain the last milestone (`connected`, `nextValidId`,
`accounts`, `tick requested`, `quote`, `clock`), elapsed and per-stage timings,
and reqIds/codes with redacted text for errors and information. A deadline
exception retains the same diagnostics. Only quote-request 9202 errors,
connectivity failures and delayed-data codes refuse quote admission; unrelated
farm notices remain information. The original trial's exact timeout cause is
unproven, so the next coordinator run can distinguish the remaining callbacks.

## Environment and commands

Use the prepared Python 3.12 environment. To reproduce its three pins with uv:

```sh
orders_env="${XDG_CACHE_HOME:-$HOME/.cache}/ibkr-rc5-orders/venv"
rtk uv venv --python 3.12 "$orders_env"
rtk uv pip install --python "$orders_env/bin/python" \
  'nautilus_trader==2.0.0rc5' \
  'nautilus-ibapi==10.45.1' 'protobuf==5.29.6'
```

The official TWS API Python package is distributed as `nautilus-ibapi`; the
runner checks `ibapi.__version__`, not a guessed distribution named `ibapi`.
The recipe uses the base rc5 wheel; its installed metadata and
[tagged package configuration](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/pyproject.toml)
list `visualization` as the extra, and the native IB adapter ships with the wheel.
The engine must be exactly `2.0.0rc5` and ibapi exactly `10.45.1`, otherwise it
returns `refused_unpinned_runtime`. Protobuf and Python versions are recorded.

From the repository root, inspect admission without connecting:

```sh
rtk "$orders_env/bin/python" \
  blueprints/us-equities/engine-nautilus/ibkr-paper-orders-rc5/run.py --help
rtk "$orders_env/bin/python" \
  blueprints/us-equities/engine-nautilus/ibkr-paper-orders-rc5/run.py --plan-only
```

The second command returns exit 0 inside the window with pinned dependencies,
and records only structural validation. Outside regular hours it refuses.
Neither command connects or fetches a quote. The coordinator's order recipe is:

```sh
rtk "$orders_env/bin/python" \
  blueprints/us-equities/engine-nautilus/ibkr-paper-orders-rc5/run.py \
  --port 4002 --receipt "$orders_env/../receipt-rc5-orders.json"
```

That recipe performs the flat pre-check and quote admission before starting the
node. `7497` is the only alternative port. An account is never
accepted as an argument or loaded from `TWS_ACCOUNT`. After admission, the
official client 92 discovers exactly one DU account with zero nonzero positions
and zero open orders. Its account identifier stays in memory and travels to the
node process only over an anonymous pipe, then into the native execution config.

## Frozen bounds and deviations

[plan.json](plan.json) retains the frozen trial's numeric limits: SPY STK,
SMART/ARCA, USD, one share per order, at most six orders, at most USD 1000 per
order and at most USD 5 round-trip loss. The node uses client 91; the independent
official-ibapi checks use 92. The endpoint is loopback on 4002 or 7497, exactly
one managed account must begin with DU, and the account starts flat.

The whole 420-second run must fit inside 09:30–15:50 America/New_York on a
weekday. The ten-minute close buffer is included in that window. Once the
read-only pre-check has established account scope, today's SPY `liquidHours`
must also cover the remaining run; closed, missing, malformed or shortened
broker hours refuse the order phase. Raw hours and account values are not saved.

Changes from the upstream example are bounded configuration and observation:

| Setting | Deviation and reason |
| --- | --- |
| Instrument and endpoint | AAPL becomes SPY, using upstream RAW `SPY=STK.SMART`; 7497/101 become 4002/91, with 7497 allowed. |
| Account discovery | Replace `TWS_ACCOUNT` with the official pre-check's in-memory account. |
| Risk engine | Set `bypass=False` and `max_notional_per_order={"SPY=STK.SMART": "1000"}`. State the route's cap limitation and hold admission through quantity one and a fresh ask plus USD 10 headroom. |
| Submit rate | `6/00:07:00` limits native dispatch over the whole run instead of the example's default rate. |
| Quotes | REALTIME and `batch_quotes=False` replace DELAYED. Delayed data cannot establish bounded current-price admission. |
| Sell quotes and other orders | Disable limit sells, stops and brackets. Entry quantity and limit quantity remain one; entry stays MARKET IOC on the first quote. |
| Resting order | Derive `tob_offset_ticks=floor(0.5 * admitted_bid / 0.01)`; pass and validate it through the pipe. Set `use_post_only=False` because rc5's IB adapter denies every post-only submit. |
| Resting lifetime | Use GTD with seven-minute expiration and explicitly disable modify/cancel-replace. Upstream `limit_order_is_one_shot` treats an expiration as one attempt, preventing repeated rejected or filled limit buys. |
| Stop | Preserve native cancel/close-on-stop and `reduce_only_on_stop=False`; enable `use_individual_cancels_on_stop=True`. Nonterminal MARKET and IOC/FOK orders remain in flight through acceptance until terminal; other orders defer stop when SUBMITTED or lacking a venue id. The deadline bounds the wait. Native close remains MARKET GTC. |
| Node timeouts | Use `_common.py`'s builder methods with the frozen 60-second connection budget, 5-second reconciliation/portfolio/disconnection timeouts and a 45-second post-stop grace for callbacks. |
| Runtime control | Host the node with upstream `run_async()`, capture cache/handle first and handle SIGINT, SIGTERM and SIGHUP. A parent process reserves the final 60 seconds for independent observation and requests graceful stop before enforcing the hard deadline. |
| Logging | Set native stdout/file log levels OFF and `print_config=False`; send child stdout/stderr to DEVNULL and remove RUST_LOG, NAUTILUS_LOG and TWS_ACCOUNT from its environment. Read receipt evidence from the shared cache. |

The half-bid placement reuses the frozen harness's distant resting probe.
IB precautionary settings are configurable; this build has not observed the
Gateway's actual settings or a current quote, so it cannot certify that this
price lies inside this account's configured limits. IB documents these controls
in [Define Precautionary Settings](https://www.interactivebrokers.co.uk/en/software/tws.bak/usersguidebook/configuretws/define_precautionary_settings.htm).
No precautionary-limit override is sent. A venue rejection cannot pass C1.

The built-in ExecTester opens its market position before maintaining resting
limits. C1–C4 label case obligations; their labels do not impose the frozen
custom strategy's sequential chronology. The wrapper watches until C1 acceptance
and C3's full fill are present, or a failure, signal, case timeout or deadline
requests stop. The native strategy then supplies C2 and C4. Native cache events
with `reconciliation=True` cannot establish venue acceptance or cancellation.
Case outcomes, fills, the round trip and stop decisions use only this run's
ExecTester submissions. An in-memory client-order-id registry requires matching
non-reconciled `OrderInitialized` and `OrderSubmitted` events for `EXEC_TESTER-001`
and `TESTER-001` after node launch. Strategy identity and initialization time alone
are insufficient: startup reconciliation can claim external SPY orders for the
same strategy. The submission lineage follows upstream's
[IB submit path](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/adapters/interactive_brokers/src/execution/core_orders.rs#L142)
and distinguishes the
[external-order materialization path](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/execution/src/engine/mod.rs#L1101).
All other cache orders appear under `reconciled_external` with stable `X` labels,
types, sides, quantities, fill prices and event timestamps. They do not contribute
to cases, bounds observations or deferred stop. A reconciliation event on an
already owned order still fails that order's cases. Startup reconciliation and
`external_order_instrument_ids=[SPY]` remain enabled as in the upstream example.
An observer exception also waits for in-flight entry resolution before native
stop, bounded by the deadline, then awaits the running task;
snapshot, receipt, signal removal and disposal each have independent cleanup.
The handle receives stop only once. Parent deadline enforcement and independent
flat proof remain in place if graceful shutdown cannot complete.

The captured cache is a **live shared view**, verified in rc5's original
[node binding](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/live/src/python/node.rs#L911)
and [cache binding](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/common/src/python/cache.rs#L79).
`py_cache` passes the kernel's `Rc<RefCell<Cache>>` into `PyCache::from_rc`;
each `orders()` call borrows that same cache and returns cloned order objects.
The runner re-reads those objects on every poll.

## Receipts and remaining acceptance

The receipt kind is `ibkr_paper_orders_nautilus_2_0_0rc5`, with evidence class
`native_paper`. A refusal records unperformed checks as null and cases as
`not_run`; it never invents zero counts or fills. Every refusal maps to its
blocked acceptance step and cases. A provisional `cleanup_required` receipt is
atomically written before starting the node and refreshed as observations arrive.
A killed child leaves that provisional state for the parent and reviewer.
Pre-node child refusals write a `refused_child_*` reason before exiting; the
parent retains that cause after successful independent flat proof.
The shared client-92 session freezes `pre_check.observed` with a deep copy before
quote admission. A pre-check timeout or exception records `pre_check` as
`incomplete` with its phase-specific cause and leaves quote admission `not_run`.

The reader records order aliases, types, sides, limit prices, event types,
Nautilus event/init timestamps, fills, quantities, commissions and currencies.
It does not serialize native account, client-order, venue-order, trade or event
identifiers. It computes gross, commissions and net in Decimal, reports missing
or zero commissions as unresolved, and cannot pass with a loss-bound breach,
an unexpected resting fill, an incomplete round trip or missing evidence.
Observed quantity, instrument, order-budget and notional violations are also
failures. Post-submit observations do not replace a missing pre-submit guard.
Cancellation and close-phase ordering uses native `ts_init`, since IB execution
event timestamps can have coarser resolution; both timestamps are retained.

After the node process exits, official client 92 independently checks the same
account again. Zero positions and open orders, complete callbacks and unchanged
account scope are required. Failure or an unavailable proof returns
`cleanup_required`, exit 3. The independent proof runs after graceful shutdown
or forced termination, including an incomplete node phase. It places no orders.

Receipt text uses the frozen account-id pattern `\b(?:D?[UF]|I)\d{5,}\b`, IPv4,
absolute-path and account-amount redaction, with a final pass over serialized
text for the in-memory account and id-shaped text. Structured execution prices
and fees remain available for review. Node child output is discarded. **Console
output is unredacted** if the parent official clients emit diagnostics; the
console is not the sanitized receipt. The parent's JSON summary receives the
final id-shaped-text scrub.

Exit codes: **0** passed, **1** failed/incomplete, **2** not connected, **3** refused
or cleanup required. A passing C1–C4 subset would still leave the broader
[acceptance procedure](../acceptance-plan.md#5-ibkr-paper-procedure) open:

- Step 3 reconnect with an open order: unexercised;
  [#5057](https://github.com/nautechsystems/nautilus_trader/issues/5057) and
  [#5060](https://github.com/nautechsystems/nautilus_trader/issues/5060) are open.
- Step 3 restart reconciliation: unexercised;
  [#5007](https://github.com/nautechsystems/nautilus_trader/issues/5007), #5057 and
  #5060 are open.
- Step 4 kill switch and alert exercise: unexercised; #5060 remains an open
  reconciliation issue. Handling a signal is not acceptance of a kill switch.

These issue states were read from upstream on 2026-10-05. Step 2 reports runner
admission separately from the engine's #4946 cap limitation. No offline result
from this builder advances broker readiness or a strategy gate.

## Offline checks and completeness review

Use a scratch directory outside the worktree and outside `/tmp`, with nice 19:

```sh
orders_scratch="${XDG_CACHE_HOME:-$HOME/.cache}/rc5-orders-r3/tmp"
rtk mkdir -p "$orders_scratch"
rtk env TMPDIR="$orders_scratch" PYTHONDONTWRITEBYTECODE=1 nice -n 19 \
  "$orders_env/bin/python" -m unittest tests.test_ibkr_paper_orders_rc5
rtk env TMPDIR="$orders_scratch" PYTHONDONTWRITEBYTECODE=1 nice -n 19 \
  python3 -m unittest tests.test_ibkr_paper_orders_rc5
rtk env TMPDIR="$orders_scratch" PYTHONDONTWRITEBYTECODE=1 nice -n 19 python3 scripts/validate.py
rtk env TMPDIR="$orders_scratch" PYTHONDONTWRITEBYTECODE=1 nice -n 19 python3 scripts/evidence_manifest.py --check
rtk env TMPDIR="$orders_scratch" nice -n 19 git diff --check
```

The tests cover plan and endpoint violations, windows, pins, redaction, receipts,
synthetic C1–C4 mapping, quote age/delay/headroom refusals, offset validation,
deferred and single stop, observer cleanup failures, provisional receipt timing,
flat-proof causes and final breach statuses. Round r3 also tests shared-session
admission, missing-callback and deadline diagnostics, farm notice routing,
accepted entry deferral and persisted child refusals. Installed checks exercise the real
config/model constructors, post-only and individual-cancel flags and logger
config and the real builder/cache handle without starting the node. They skip
without rc5. All network readers and node execution are
synthetic; no test connects. These are local integration checks and fixtures,
not unchanged upstream tests or native paper evidence.

Completeness review: the cross-family review's post-only denial, late-fill stop
race, cancellation targeting, cleanup failures and status defects are addressed.
Original PyO3 source confirms the cache view; the installed official API supplies
timestamped admission. The upstream release check corrected stale #4946 release
metadata. Actual commissions, precautionary settings, entitlements, concurrent
account use, reconnect, restart, alerts, kill switch and paper execution remain
unobserved here. The coordinator's paper trial supplies native case evidence.

API correction retained from the offline probes: the Python instrument
provider's `determine_venue` accepts a contract dictionary, not an official
ibapi `Contract` instance. A proposed `symbol_to_mic_venue={"SPY": "IB"}` does
not remap this stock's ARCA primary exchange in rc5; the dictionary probe and
[stock-venue resolver](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/adapters/interactive_brokers/src/providers/instruments.rs#L347)
confirmed it. That proposed workaround is not used.

Cache probe correction: the installed public `Cache` view does not expose
`add_order`; that method belongs to the separate mutable Rust binding. Shared
observation is established by `PyCache::from_rc` and per-call borrows in the
original binding, rather than by an invented Python mutation method.
