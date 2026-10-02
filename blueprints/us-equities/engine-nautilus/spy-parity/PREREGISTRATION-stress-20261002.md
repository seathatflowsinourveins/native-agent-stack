# SPY one_stress: costs and rounding mapping, 2026-10-02

Status: source and synthetic/native API preparation only; no stress engine replay.
The separate [manifest](mapping-manifest-stress-20261002.json) inherits the
hash-bound v2 mapping. Frozen LEAN inputs, oracle, tolerance sheet, historical
manifests, receipts, review records and replay history remain immutable.

Native source: NautilusTrader official 2.0.0rc5, commit
`1b0a49d2792a9432a3aca3fcb617ce7a630d905e`. The custom low-level
[FillModel protocol](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/concepts/backtesting/fill-models.md)
returns a book to the existing matching engine before native events are emitted.
The official `FixedFeeModel` charges one USD once per filled OCO leg. The canceled
sibling incurs no fee. No bars or exported fills are repriced, and no cash is
invented to reconcile a target.

Stress fixture precision is explicitly six decimals with increment 0.000001;
`one_zero` retains precision four. The decision-close OCO trigger spacing remains
0.0001. BUY execution applies Decimal price times 1.002; SELL applies times 0.998.
Round once using ROUND_HALF_EVEN at six decimals. Preserve full Decimal products
in the cash ledger. The original zero fill-price tolerance and 0.01 USD cash
allowance remain unchanged. Six-decimal precision describes this sample fixture,
not a real exchange order tick.

Frozen predictions: intent BUY 304 at 1577826000; native fill 304 at 324.227160,
1577977200; exit intent SELL 304 at 1588190400; native fill -304 at 291.106620,
1588255200. Fees total 2 USD; posted distributions total 428.64; final quantity
zero; reconstructed cash 90357.995840; native cents display 90358.00.

Before engine operation, independently review the existing five harness modules,
`cost_models.py`, this preregistration, the new manifest and both exact platform
locks. Retain a `spy-parity-v2-harness-review/1` record with all ten hashes,
completion before the run and zero unresolved findings. The runner rejects a
missing, stale or unresolved stress review before constructing an engine. Freeze
argument arrays, source hashes and input hashes before engine operation.

The inherited mandatory Linux bwrap isolation remains a gate. The compatible
official macOS wheel and native API checks do not meet that gate. No Mac result
may claim a complete PASS while namespace/read-only/isolation checks are absent.
Engine evidence requires two fresh owned processes, native exports, and the
independent comparator with `--lean-data` to rehash all five inputs. `--bars`
alone remains incomplete. Any price/quantity/time/fee/distribution mismatch,
partial/double fill, denied/rejected order, missing OCO cancellation, unexplained
cash residue or ERROR-level engine line fails. No mapping/gate is promoted by
source preparation or synthetic checks.

This newly dated stress scope requires review before every qualifying run.
Historical v2 replays and their failed preconditions stay retained and do not
become reviewed retroactively. Margin, leverage and adaptive-state mappings
remain outside this implementation.

The preserved text-only [v2 source snapshot](historical-source-v2-a2ad39a.json) holds the
eight exact original source files from base a2ad39abd8c6827069395682f50d5058492a0f34.
Historical receipt and review hashes still validate those bytes; they do not
qualify the new run.py/compare.py or stress mapping.
