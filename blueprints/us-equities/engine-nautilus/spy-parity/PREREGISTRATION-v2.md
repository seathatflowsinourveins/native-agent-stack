# SPY/LEAN parity, mapping manifest v2: preregistration

Drafted 2026-09-22. Gate G-a, case `one_zero`. Machine-readable terms:
[`mapping-manifest-v2.json`](mapping-manifest-v2.json).

## Status: nothing has run

**No v2 replay, v2 comparison or v2 verdict exists.** `run.py` and `compare.py`
have not been changed or run for v2, and the harness changes v2 needs are listed
as not implemented. The published result is still the v1 **BLOCKED**
[`verdict.json`](verdict.json), bound to the unchanged v1
[`mapping-manifest.json`](mapping-manifest.json).

This document rests on three things, none of them a parity run:

* the synthetic engine-semantics probes in [`probes/v2/`](probes/v2/). Their bars
  and factor rows are synthetic, never SPY/LEAN data. Each probe ran once under
  the pinned rc5 interpreter in `bwrap --unshare-all`, and each run is recorded in
  a `*.observed.json` with sha256 values;
* the NautilusTrader source at the pinned commit
  `1b0a49d2792a9432a3aca3fcb617ce7a630d905e` and the LEAN source at
  `985ef30ad3ac774218c5ac516b4cb0aa2655730f` (cited by file and line in the
  manifest);
* arithmetic on the five frozen, hash-matched LEAN inputs.

## What v2 changes

v1 marks two mappings `unsupported`. v2 assigns each one an engine-native
mechanism and gives it the new status `preregistered`. A preregistered row is
not `resolved`, and it can never be used to explain away a failure. Any failure
on either row makes the v2 result FAIL, not BLOCKED.

| Mapping | v1 | v2 mechanism |
| --- | --- | --- |
| `market_on_open_proxy` | Fill at the close of the next session's first bar. | A native OCO pair, submitted from the decision bar. One leg is a STOP_MARKET and the other a MARKET_IF_TOUCHED, with triggers at the decision close ± 0.0001. When the next bar opens away from the previous close, the matching engine's gap-open trade tick fills the crossed leg at `bar.open` (`fill_at_market=true`), and the engine's OCO contingency cancels the sibling. |
| `distributions_and_cash` | Computed outside the engine, flagged `engine_posted=false`. | A Python `SimulationModule` passed through `add_venue(modules=[...])`. At each ex-date instant it returns `[Money]`, and `SimulatedExchange.try_adjust_account` posts that amount as a reported `AccountState`. The amount is the frozen factor-file distribution times the position the engine reports in `ctx.positions` at that instant. The ex-date is the next session after the factor row (LEAN's next tradable date), at 00:00 New York. |

`decision_visibility` is amended because the pair now rests from the decision
bar. The five other v1 rows and `tolerances.json` are unchanged; the tolerance
file must still hash to `c8bc7231…c15a`.

## Hypothesis

With the v2 mechanisms implemented as the manifest specifies, and no change to
tolerances, inputs or sizing, the v2 `one_zero` replay reproduces the LEAN oracle
exactly:

* entry fill of 304 at **323.58**, stamped 1577977200;
* exit fill of −304 at **291.69**, stamped 1588255200;
* each fill is a single fill, and the sibling leg is canceled at the same instant;
* engine-posted distributions of **0.00** at 1576818000 (0 shares held) and
  **428.64** at 1584676800 (304 × 1.41);
* native exported end cash **90,734.08**, within 0.01, with a zero unexplained
  residue.

The fill predictions follow from the frozen rows:

| Event | Decision close C | Next open | Gap | Leg crossed at the open | Faithful to oracle |
| --- | ---: | ---: | ---: | --- | --- |
| Entry (BUY) | 321.8600 | 323.5800 | +1.7200 | STOP_MARKET BUY @ 321.8601 | yes |
| Exit (SELL) | 293.2100 | 291.6900 | −1.5200 | STOP_MARKET SELL @ 293.2099 | yes |

In both events the untouched MIT leg's trigger also lies outside the tested bar's
range: entry low 323.41 against an MIT at 321.8599, and exit high 291.71 against
an MIT at 293.2101.

## Is the OCO proxy a faithful market-on-open equivalent?

**For both oracle events: yes, as predicted.** Each has a gap far larger than one
tick. Each 304-share order is tiny beside the open tick's share of the bar volume
(about 1.6 million and 3.4 million shares). The entry costs 98,368.32, which fits
inside 100,000 of cash.

**In general: no.** The proxy matches LEAN's `MarketOnOpenFill` only inside the
manifest's `faithfulness_domain`:

* **No gap (open == C, the only on-grid price strictly between the triggers).**
  The engine does not generate a gap-open tick. The pair then fills at a trigger
  on the high or low tick: the synthetic probe filled BUY at 100.0001 under
  default ordering and at 99.9999 under adaptive ordering, both times against an
  open of 100.0000. If the bar never leaves C, the pair fills in a later bar.
  v2 names this failure `moo_proxy_no_gap` and does not tolerate it. It is
  predicted not to occur in `one_zero`.
* **Quantity above the open tick's size.** The fill splits across two prices
  (`probe_oco_full`).
* **A gap-up buy that overdraws the CASH account.** The portfolio logs an ERROR,
  and v2 refuses the run.
* **An unlinked pair with only a strategy-level sibling cancel.** Both legs
  double-fill (`probe_gap_open`). Only the native `ContingencyType.OCO` is
  allowed.

## What would falsify it

Any of the following refutes the hypothesis, and v2 will not reinterpret it or
absorb it into a tolerance:

1. An OCO fill price differs from the tested bar's open, or the fill lands in any
   bar other than the next session's first bar.
2. Both legs of a pair fill, a leg fills partially, or a leg is denied, rejected
   or filled on the decision bar.
3. The module's `process()` is not called at an ex-date instant, reads a quantity
   other than 0 and 304, or has an adjustment not applied.
4. The distributions are missing from the native account report as reported
   `AccountState` rows, or native end cash differs from 90,734.08 by more than
   0.01.
5. Any nonzero unexplained residue, any skipped check, or any ERROR-level engine
   log line.

## What still counts as fabrication, and is forbidden

* Injecting any synthetic tick or bar at the open, or using latency or timer
  tricks to reach such a tick.
* Limit prices or triggers derived from the next bar.
* Submitting the orders at the next bar.
* A strategy-level cancel in place of the native OCO.
* A fill model or export re-pricing that selects the open.
* A distribution amount taken from the oracle (428.64, per-event values or end
  cash), or chosen to reconcile a balance.
* Cash posted by any path other than the module's return value.
* Eligible quantity taken from anything other than `ctx.positions` at the
  ex-date instant.
* An ex-date computed as calendar + 1.
* Posting at the first bar after the ex-date instead of at the ex-date instant.
* A second rounding stage.

## Corrections to v1 (made here, not in v1)

v1 is not edited. v2 records these corrections to v1's text, with line numbers in
v1's `mapping-manifest.json`:

* **Lines 141 and 153** say no mechanism credits a simulated account. That is
  false: `SimulationModule` → `try_adjust_account` → reported `AccountState` does
  so. v1's symbol scan searched for names containing "dividend", so it could not
  find the generic adjustment path.
* **Line 158** says any module that posts dividend cash is an invented balancing
  entry. That is false as a blanket rule. An entry counts as invented only when
  its amount is chosen to reconcile a target.
* **Line 155** puts the ex-date at the calendar day after the factor row. LEAN
  uses the next tradable date. For `one_zero` the two coincide (both rows fall on
  a Thursday), so v1's numbers are unaffected.
* **Lines 121 and 128** say no construct produces a bar-open fill. That is
  incomplete. The gap-open trade tick fills resting stop-market and
  market-if-touched orders at the open.

## Before any v2 run

1. Implement `harness_changes_required` from the manifest, and have the changes
   independently reviewed.
2. Bind `mapping-manifest-v2.json` by sha256 in the receipt.
3. Run twice under the v1 isolation recipe, then compare with the unchanged
   tolerances.

Only a complete PASS may move the two rows to `resolved`, and that move is made
in a later, dated manifest revision. Nothing here changes a gate or catalog
status.
