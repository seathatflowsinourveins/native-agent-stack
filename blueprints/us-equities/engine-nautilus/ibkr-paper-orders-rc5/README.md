# IBKR paper orders on NautilusTrader 2.0.0rc5

This build serves the trading north star's bounded SPY paper order qualification
on the selected NautilusTrader destination. It uses the upstream **built-in
ExecTester**, LiveNode and native Interactive Brokers factories. The four case
labels mirror the [frozen 1.231.0 trial](../ibkr-paper-orders/README.md): accept a
resting buy, cancel it, fill a one-share buy, flatten and independently prove flat.

**Current admission result: `refused_unenforced_notional`, exit 3, before any
connection.** The selected pin supports `max_notional_per_order`, but its risk
engine can skip that check for broker-routed stock instruments. A configured
limit cannot establish an enforced limit. There is no command line bypass.
This is an offline build with a documented source blocker, not a paper run or a
passed `ibkr-local-acceptance` gate. The coordinator owns review and broker execution.

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

The decision is to preserve the user's rc5 pin and the upstream strategy and
refuse an unenforced bound. Switching to the frozen 1.231.0 strategy would
change the destination; selecting a later revision would change the pin;
reimplementing the entry as a protected limit would duplicate upstream trading
logic. None is adopted. Overturn this refusal only with original-source and
native evidence that the selected route checks the notional before dispatch,
including a discriminating over-limit case with zero broker submissions.

An additional bound needs review before enabling the execution path: the native
strategy closes the whole position. If both the market entry and the resting
buy fill, native shutdown can create a SELL of two shares. The runner records an
unexpected C1 fill as failure, but that observation alone cannot enforce a
one-share closing-order ceiling. Removing the notional refusal is therefore
insufficient to establish all of the frozen bounds.

The official-ibapi checker, broker `liquidHours` parser and redaction are reused
directly from [the frozen harness](../ibkr-paper-orders/run.py). Only its pure
helpers and official read-only checker are loaded. Its 1.231.0 strategy is never
constructed. The receipt binds that dependency with `source_hashes` in addition
to the new runner and plan hashes.

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

The second command returns exit 3 at the current pin. Outside the regular-hours
window it reports the window refusal first. This is an expected refusal and
places no orders. The order-run recipe, retained for coordinator review, is:

```sh
rtk "$orders_env/bin/python" \
  blueprints/us-equities/engine-nautilus/ibkr-paper-orders-rc5/run.py \
  --port 4002 --receipt "$orders_env/../receipt-rc5-orders.json"
```

That recipe also refuses before connecting until the source blocker and remaining
bound gaps are resolved. `7497` is the only alternative port. An account is never
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
| Risk engine | Set `bypass=False` and `max_notional_per_order={"SPY=STK.SMART": "1000"}`. Constructor support is verified; the source-proven enforcement gap causes refusal. |
| Submit rate | `6/00:07:00` limits native dispatch over the whole run instead of the example's default rate. |
| Quotes | REALTIME and `batch_quotes=False` replace DELAYED. Delayed data cannot establish bounded current-price admission. |
| Sell quotes and other orders | Disable limit sells, stops and brackets. Entry quantity and limit quantity remain one; entry stays MARKET IOC on the first quote. |
| Resting order | Retain upstream `tob_offset_ticks=500`, `use_post_only=True`. At the frozen USD 0.01 tick this rests USD 5 below the bid. |
| Resting lifetime | Use GTD with seven-minute expiration and explicitly disable modify/cancel-replace. Upstream `limit_order_is_one_shot` treats an expiration as one attempt, preventing repeated rejected or filled limit buys. |
| Stop | Preserve native cancel-on-stop, close-on-stop and `reduce_only_on_stop=False`. Native close remains MARKET with the upstream default GTC; no custom flatten strategy or retries are introduced. |
| Node timeouts | Use `_common.py`'s builder methods with the frozen 60-second connection budget, 5-second reconciliation/portfolio/disconnection timeouts and a 45-second post-stop grace for callbacks. |
| Runtime control | Host the node with upstream `run_async()`, capture cache/handle first and handle SIGINT, SIGTERM and SIGHUP. A parent process reserves the final 60 seconds for independent observation and requests graceful stop before enforcing the hard deadline. |
| Logging | Set native stdout/file log levels OFF and `print_config=False` to keep the account/config out of native logs; the receipt reads the cache directly. These installed LoggerConfig parameters were verified offline. |

The 500-tick resting offset follows upstream's own execution example rather
than the frozen harness's half-bid price, which is much farther from market.
For example, at a **synthetic** USD 770 bid the USD 5 offset is about 0.65%.
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

## Receipts and remaining acceptance

The receipt kind is `ibkr_paper_orders_nautilus_2_0_0rc5`, with evidence class
`native_paper`. A refusal records unperformed checks as null and cases as
`not_run`; it never invents zero counts or fills. Every refusal maps to its
blocked acceptance step and cases. A provisional `cleanup_required` receipt is
atomically written before starting the node and refreshed as observations arrive.
A killed child leaves that provisional state for the parent and reviewer.

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
and fees remain available for review. **Console output is unredacted** if native
clients emit diagnostics; the console is not the sanitized receipt.

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

These states were read from upstream on 2026-10-05. Step 2's frozen-bound
obligation is additionally blocked by the selected pin's #4946 path. No receipt
from this builder advances broker readiness or a strategy gate.

## Offline checks and completeness review

Use a scratch directory outside the worktree and outside `/tmp`, with nice 19:

```sh
orders_scratch="${XDG_CACHE_HOME:-$HOME/.cache}/rc5-orders-r1/tmp"
rtk mkdir -p "$orders_scratch"
rtk env TMPDIR="$orders_scratch" PYTHONDONTWRITEBYTECODE=1 nice -n 19 \
  "$orders_env/bin/python" -m unittest tests.test_ibkr_paper_orders_rc5
rtk env TMPDIR="$orders_scratch" PYTHONDONTWRITEBYTECODE=1 nice -n 19 \
  python3 -m unittest tests.test_ibkr_paper_orders_rc5
rtk env TMPDIR="$orders_scratch" PYTHONDONTWRITEBYTECODE=1 nice -n 19 python3 scripts/validate.py
rtk env TMPDIR="$orders_scratch" PYTHONDONTWRITEBYTECODE=1 nice -n 19 python3 scripts/evidence_manifest.py --check
rtk env TMPDIR="$orders_scratch" nice -n 19 git diff --check
```

The tests cover plan and endpoint violations, whole-run and broker-hours
refusal, exact pins, redaction, receipt shape, a synthetic C1–C4 event mapping,
provisional receipt timing, independent proof failures and actual installed
config/model constructors. Native checks skip when the interpreter lacks rc5.
Orchestration fixtures replace both the official checker and node process;
their counterfactual cap resolution exists only in test mocks. No test starts
a node or connects to a broker. These are local integration checks and synthetic
fixtures, not unchanged upstream tests or native paper evidence.

Completeness review: original Python examples, installed APIs, tagged Rust risk
and strategy paths, the official checker and IB preset documentation were
considered. Config support alone missed the broker account/venue risk boundary;
that finding produced the mandatory refusal. The source also exposes the
two-share close edge case and lacks a pre-submit quote-age/loss admission guard
in ExecTester. The next trading execution sweep must find a maintained native
guard for those bounds at the chosen pin before authorizing an enabled recipe.
Actual commission timing, precautionary settings, reconnect, restart, alerts,
kill switch and paper execution remain unobserved here.

API correction retained from the offline probes: the Python instrument
provider's `determine_venue` accepts a contract dictionary, not an official
ibapi `Contract` instance. A proposed `symbol_to_mic_venue={"SPY": "IB"}` does
not remap this stock's ARCA primary exchange in rc5; the dictionary probe and
[stock-venue resolver](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/adapters/interactive_brokers/src/providers/instruments.rs#L347)
confirmed it. That proposed workaround is not used.
