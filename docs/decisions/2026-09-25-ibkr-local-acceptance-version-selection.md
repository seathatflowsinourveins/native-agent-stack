# Decision: NautilusTrader 1.231.0's Python IB adapter for IBKR local acceptance, keep-but-compare against the first 2.0.x release containing nautilus_trader#5041 (2026-09-25)

**Status:** keep-but-compare. Recorded on branch `claude/ibkr-acceptance-prep-20260925` (base
`origin/main@ae3d3d37`) by the live-gates workflow under the user's standing paper authorization.
It needs independent review before merge.

**User decision, 2026-09-25 (binding; relayed verbatim by the live-gates coordinator as user
decision 3, recorded here at 2026-09-25T23:21Z):** "NautilusTrader 1.231.0 + ibapi 10.45.1 for
local acceptance, keep-but-compare against the first 2.0.x release containing nautilus_trader PR
#5041". This record implements that decision. Where an earlier revision of this record named
the pinned 2.0.0rc5 Rust adapter as the comparison arm, or let an rc5 result or another release
overturn the selection, the decision governs (see the update of 2026-09-25T23:21Z below).

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
Every such receipt is labelled with its engine version. The comparator is **the first 2.0.x
release (a published release, not a dev wheel or a `develop` or PR-branch build) that contains
nautilus_trader#5041**; no release contains it yet. The pinned 2.0.0rc5 Rust adapter is not an
overturn arm. The gate still flips only through a manual, dated commit after qualification.

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
  `ibkr-acceptance/README.md`, `ibkr-paper-orders/README.md` "Why 1.231.0",
  `evidence/receipts/ibkr-readonly-acceptance-20260923.json`) cite the issue text, not an rc5
  observation.
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
   - It is not the comparison arm (user decision, 2026-09-25). An rc5 stock-order probe may
     still run as optional evidence for the #4983 reclassification (below).
2. **Wait for a release that contains #5041:** rejected as the only path. There is no date, the
   PR is still in review with a dirty merge state, and the gate would stay unmeasured meanwhile.
3. **Build `develop` or the #5041 branch:** rejected. An unreleased, unreviewed build is no stable
   pin, and a result would not transfer to the release.
4. **LEAN's IB brokerage (the retained comparison engine):** out of scope. This gate is about the
   Nautilus native adapter; LEAN stays the engine-level comparison.
5. **The official `ibapi` client alone:** not an engine adapter. It is used only as the
   independent observer and for the runner's own-order cleanup.

## Comparison that would overturn it

The comparator is fixed by the user's decision of 2026-09-25: the first 2.0.x release (not a
dev wheel) containing nautilus_trader#5041. Only items 2 and 3 can overturn the selection.

1. **rc5 stock-order probe (optional evidence, not an overturn path).** Through rc5's Rust
   adapter, place one resting SPY LIMIT BUY of 1 share at half the bid on the same paper
   Gateway, cancel it, and confirm both with the independent ibapi observer. It bears only on
   the #4983 reclassification in `runtime-target.json` (`rc5_reclassified_reports`):
   - If rc5 places and cancels natively, the reclassification stands.
   - If rc5 denies the order locally, #4983 goes back to `rc5_blockers`.
   - Neither outcome changes this selection or its comparator.
2. **Release comparison (the comparator).** When the first 2.0.x release (a published release,
   not a dev wheel or a `develop` or PR-branch build) that contains nautilus_trader#5041 is out,
   run the same frozen case set on its native IB adapter against the same paper account, with
   the same observer: A1-A4, B1, B2 and C1 from `local-acceptance-plan.json`, plus the C1-C4
   order cases.
   - If every case passes with zero duplicate submissions and zero unexplained differences, that
     release replaces 1.231.0 for this gate. The gate receipt is re-bound to it, and this record
     is superseded by a dated follow-up.
   - If the release fails a case that 1.231.0 passes, 1.231.0 stays and the failure is reported
     upstream.
   - Whether that release also carries the #4946 fix (`develop` commit `ed6fc8bf`) and closes
     #4983, #5007, #5057 and #5060 is recorded with the comparison; it does not change which
     release is the comparator.
3. If 1.231.0 fails a case that the release of item 2 passes on the same plan, 1.231.0 is
   overturned at once.
4. Any other trigger needs a new user decision and does not overturn the selection: an rc5
   result, a release that closes #4983, #5057, #5060 or #4946 without containing #5041, or a
   later 1.x release.

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

## Update, 2026-09-25T21:23Z (first independent review of PR #280)

Re-checked with `gh api`; source reading, not observed. The selection is unchanged.

- #4983 is still open with 0 comments. The canonical records now carry it as a stale v1.227.0
  report for rc5: `catalogs/us-equities/runtime-target.json` moves it from `rc5_blockers` to
  `rc5_reclassified_reports`, and the `ibkr-local-acceptance` gate note opens with a dated
  superseding paragraph. The rc5 stock-order probe (comparison 1) still confirms or overturns
  that reading.
- PR #5041 is unchanged: open, not merged, head `4b17ac3c`, body sha256 `050141af…`, and its
  root `Cargo.toml` diff is `ibapi = "=3.3.0"` to `ibapi = "=4.2.0"`. Both records now say
  `=4.2.0`.
- #4946 is a fourth rc5 obstacle, on the risk path. For a broker-routed `SMART` instrument the
  account registered under venue `IB` is not found, so the risk engine skips every
  account-scoped pre-trade check (the fail-open branch is `crates/risk/src/engine/mod.rs:1218-1234`
  at `v2.0.0rc5`). It was closed at 2026-09-25T11:03:11Z by `develop` commit `ed6fc8bf`
  ("Apply pre-trade risk to the destination execution account"), which is in no release, and
  #5041 lists it as covered. `runtime-target.json` `rc5_blockers` now lists #5007, #5057, #5060
  and #4946 with their sources. Comparison 2 therefore needs a release that also carries the
  #4946 fix, not only one that closes #4983, #5057 and #5060.
- Releases are unchanged: the newest is `v2.0.0rc5` and the newest stable is `v1.231.0`.

The runner was revised in the same review, before any run: the kill-switch latch and the run
lock moved to one frozen per-account path, and the gate receipt is written only by its
`gate-receipt` builder after an independent corroboration record passes (the Gateway API
message log or the next-day IBKR activity statement; `ibkr-acceptance/README.md`, "Independent
corroboration").

## Update, 2026-09-25T23:21Z (second independent review of PR #280)

The selection is unchanged; its comparator now follows the user's decision quoted under
**Status**. Nothing was re-checked upstream for this update.

- The title, the Decision section, alternative 1 and the overturn comparisons now name the first
  2.0.x release (not a dev wheel) containing nautilus_trader#5041 as the comparator. The rc5
  stock-order probe stays only as optional evidence for the #4983 reclassification, and item 3
  no longer has an rc5 arm. Any other trigger needs a new user decision (item 4).
- This supersedes the 21:23Z statement that comparison 2 needs a release that also carries the
  #4946 fix: the comparator is the first 2.0.x release containing #5041, and whether it carries
  `ed6fc8bf` is recorded with the comparison.
- The runner and plans moved to revision 3, still before any run: the gate receipt needs a
  Gateway API message log record, so every run claim is corroborated by IB's own records and
  none rests on the in-process observer alone (an activity statement is an optional additional
  record); a record time later than the builder's clock plus 300 s is refused; and `preflight`
  holds the run lock while it connects.
