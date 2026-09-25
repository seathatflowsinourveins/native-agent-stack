# Decision: NautilusTrader 1.231.0's Python IB adapter for IBKR local acceptance, keep-but-compare against 2.0.0rc5 (2026-09-25)

**Status:** keep-but-compare. Recorded on branch `claude/ibkr-acceptance-prep-20260925` (base
`origin/main@ae3d3d37`) by the live-gates workflow under the user's standing paper authorization.
It needs independent review before merge.

**Scope:** which NautilusTrader version may carry the `ibkr-local-acceptance` gate
(`catalogs/us-equities/gates-20260922.json`) through acceptance-plan section 5, steps 1-4.
It does not change the engine destination in `catalogs/us-equities/runtime-target.json`
(2.0.0rc5, source `1b0a49d2`), the Alpaca lane or any backtest. It does not flip the gate and
it authorizes no live configuration or order. `live-go` stays a user decision.

## Decision

Run IBKR local acceptance on **NautilusTrader 1.231.0's Python Interactive Brokers adapter**
(official `ibapi` 10.45.1) through
`blueprints/us-equities/engine-nautilus/ibkr-acceptance/local_acceptance.py`. A passed receipt
from that runner, together with the two prerequisite receipts it names, may be cited for the gate.
Every such receipt is labelled with its engine version. The pinned 2.0.0rc5 Rust adapter stays
the comparison arm until the comparison below runs. The gate still flips only through a manual,
dated commit after qualification.

## Evidence

Upstream, checked with `gh api` at 2026-09-25T18:21Z:

- [nautilus_trader#4983](https://github.com/nautechsystems/nautilus_trader/issues/4983) is open,
  with 0 comments. It was filed 2026-09-12 against **v1.227.0** (Rust adapter). The report: the
  execution engine denies every stock order because the order venue `SMART` never equals the
  client venue `IB`.
- **Source check, not observed:** at the pinned tag `v2.0.0rc5` (commit `1b0a49d2`),
  `crates/execution/src/engine/mod.rs:2222` asks `client.handles_order_venue(order_venue)`. The IB
  execution client overrides that method to return `true`
  (`crates/adapters/interactive_brokers/src/execution/core.rs:491-496`). Blame:
  `acfd4f76a4`, "Allow IB Rust orders to route MIC venue instruments (#4129)", merged
  2026-05-25T21:45:27Z. v1.227.0 was published 2026-05-18, before that merge. So the
  engine-level denial described in #4983 may not apply at rc5. No rc5 stock order has been
  tried on this host. The repository's rc5 blocker entries (runtime-target.json `rc5_blockers`,
  `ibkr-acceptance/README.md`, `evidence/receipts/ibkr-readonly-acceptance-20260923.json`) cite
  the issue text, not an rc5 observation.
- [PR #5041](https://github.com/nautechsystems/nautilus_trader/pull/5041) is open and not merged.
  It is not a draft; `mergeable_state` is `dirty`. It is one commit on `develop` (head
  `4b17ac3c`), +22,773/-11,740 across 123 files, updated 2026-09-25T10:28:06Z. The maintainer
  left `COMMENTED` reviews at 02:39:48Z and 09:17:18Z today, and the author replied to them.
  - The body (sha256 `050141af…`) rewrites the Rust adapter and moves the Rust `ibapi` pin from
    `=3.3.0` to **`=4.2.0`**. Earlier repository records say `=4.1.0`; that is now stale.
  - The body does not mention #4983.
  - It lists as implementation coverage open issues on exactly the paths steps 3-4 exercise:
    #5007 (startup fill reconciliation sends the prefixed account id, TWS error 321), #5057
    (working orders from a previous session cannot be managed after a restart), #5060
    (execution-query replies replayed as live fills), #4970 (a lost client-order-id mapping
    creates a duplicate reconciliation order), #4564 and #4932. All six were open at the check.
- Releases: the newest is `v2.0.0rc5` (prerelease, 2026-09-15). The newest stable release is
  `v1.231.0` (2026-08-02, titled "NautilusTrader 1.231.0 Beta"). No release contains #5041, and
  no 1.x release has followed 1.231.0.
- rc5 pins Rust `ibapi =3.3.0`, which treats IB notice 2188 as a fatal error
  (wboayue/rust-ibapi#764, fixed in v4.0.0). One native bar failure was observed on 2026-09-23;
  that observation is confounded (see `ibkr-acceptance/README.md`).

Local evidence (label `native_paper` unless stated):

- `ibkr-paper-orders/evidence/receipt-20260923-passed.json` (sha256 `e813c655…`) shows
  NautilusTrader 1.231.0's own IB execution engine placing a resting SPY buy (accepted),
  cancelling it, filling a marketable buy and flattening. Three orders were used, net -2.08 USD,
  and an independent ibapi flat proof passed. The after-hours run (`3e88b880…`) ended
  `incomplete` on the flatten step timeout and was cleaned up flat.
- `ibkr-acceptance/evidence/ibapi-readonly-20260923.json` (sha256 `af4d968c…`,
  `native_paper_readonly`) is step 1, passed on the same paper Gateway.
- 1.231.0 source, installed package at
  `~/.local/share/codex-ecosystem/tools/nautilus-1.231.0-ib` (`measured_local`, read only):
  - The execution client registers `venue=None` (`adapters/interactive_brokers/execution.py:209`).
  - A connection watchdog resets and resumes the client after a socket loss
    (`client/client.py:482-516`, `client/connection.py:127-132`).
  - After three IB 326 collisions the adapter falls back to client ids configured+1..+4
    (`client/connection.py:160-186`).
  - Startup reconciliation reads `reqOpenOrders` for its own client id and restores the client
    order id from `orderRef` (`client/order.py:109-164`, `execution.py:532-658`). A strategy's
    `external_order_claims` claims the reconciled order (`live/execution_engine.py:3549-3572`).
  - The risk engine's `HALTED` state denies submits and lets cancels through
    (`risk/engine.pyx:1137-1149`).

## Alternatives considered

1. **2.0.0rc5 Rust adapter, the pinned destination:** not selected for steps 2-4 now.
   - Its stock-order path has never been observed here.
   - Its restart and reconnect paths are the subject of the six open issues #5041 lists as
     covered. Running steps 3-4 there before a release carries those fixes would measure paths
     upstream reports as defective.
   - Its `ibapi =3.3.0` pin has the 2188 defect.
   - It stays the comparison arm.
2. **Wait for a release that contains #5041:** rejected as the only path. There is no date, the
   PR is still in review with a dirty merge state, and the gate would stay unmeasured meanwhile.
3. **Build `develop` or the #5041 branch:** rejected. An unreleased, unreviewed build is no stable
   pin, and a result would not transfer to the release.
4. **LEAN's IB brokerage (the retained comparison engine):** out of scope. This gate is about the
   Nautilus native adapter; LEAN stays the engine-level comparison.
5. **The official `ibapi` client alone:** not an engine adapter. It is used only as the
   independent observer and for the runner's own-order cleanup.

## Comparison that would overturn it

1. **rc5 stock-order probe (can run now).** Through rc5's Rust adapter, place one resting SPY
   LIMIT BUY of 1 share at half the bid on the same paper Gateway, cancel it, and confirm both
   with the independent ibapi observer.
   - If rc5 places and cancels natively, #4983 no longer blocks rc5, and the rc5 path becomes a
     candidate for steps 2-4. It still needs the comparison in item 2.
   - If rc5 denies the order locally, the #4983 blocker is confirmed for rc5.
2. **Release comparison.** When a NautilusTrader release (not a dev wheel) contains #5041, or
   otherwise closes #4983, #5057 and #5060, run the same frozen case set on its native IB
   adapter against the same paper account, with the same observer: A1-A4, B1, B2 and C1 from
   `local-acceptance-plan.json`, plus the C1-C4 order cases.
   - If every case passes with zero duplicate submissions and zero unexplained differences, that
     release replaces 1.231.0 for this gate. The gate receipt is re-bound to it, and this record
     is superseded by a dated follow-up.
   - If the release fails a case that 1.231.0 passes, 1.231.0 stays and the failure is reported
     upstream.
3. If 1.231.0 fails a case that the rc5 or release arm passes on the same plan, 1.231.0 is
   overturned at once.

## Limits

- No 1.x release has followed 1.231.0, and the open IB fixes (#5041) target the 2.x Rust
  adapter. A 1.231.0 pass shows that engine's behaviour, not the destination's.
- All evidence is paper, from one host (WSL2 with IB Gateway 10.50) and one account. Nothing
  here is live-endpoint evidence or a general property of IBKR.
- The runner's fault injection shuts the adapter's socket down from inside the process. That is
  a real TCP close seen by the Gateway, not a network partition, a Gateway restart or IBKR's
  nightly reset.
- No fill occurs in steps 2-4 by design, so their execution-id mapping is not exercised there;
  fills rest on the 2026-09-23 C1-C4 receipt.
