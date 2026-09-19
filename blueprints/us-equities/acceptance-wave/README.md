# Native acceptance wave — September 19, 2026

This wave advances three concrete gaps using existing dependencies:
**LEAN execution-cost sensitivity, DuckDB temporal selection and a strict Alpaca
order-intent boundary**. Three independent workers implemented and reviewed changes
in separate worktrees; one coordinator integrated the evidence.

These are separate offline acceptances. Synthetic temporal data was not fed into
the LEAN experiment, and neither path submitted an order. The next direction is
[daily and intraday catalyst research](research-protocol.md), including historical
+200% mover discovery and separate pre-event/post-signal hypotheses.

The [factor, data-feed and regime design](factors-regimes.md) connects those
hypotheses to timestamped inputs and future automatic selection among validated
strategies. It is source-reviewed architecture, not an enabled strategy-switching service.

## Direct native results

| Capability | Observed result | Acceptance boundary |
| --- | --- | --- |
| Native LEAN 985ef30 with documented dependency remediation | Three completed runs, identical fixed 100-share SPY round trip: ending equity **$100,233.00**, **$100,214.11**, **$100,163.44** for zero costs, $1/order + 5 bps and $1/order + 20 bps | Fee/slippage response and serialized cash reconciliation; no alpha, quantity/latency calibration or paper execution |
| DuckDB 1.5.5 SQL and Parquet | **11 command exits**: snapshot, six selections, four expected rejections. February values 100/200; March correction 90 and removed membership; April 90/300; February replay unchanged | Synthetic source/version/universe integrity and selection; real-data availability and entitlement remain unauthenticated |
| alpaca-py 0.44.0 request serialization | Isolated probe **exit 0**; **3** unsupported advanced cases rejected locally; **8** other negative cases rejected; one import-time socket constructor and **0** blocked transport/process events | Basic create-intent guard and request models; no TradingClient, broker request, advanced adapter or replacement/cancel workflow |

[LEAN receipt and argument arrays](../execution-realism/receipt.json),
[DuckDB receipt and selections](../point-in-time/receipt.json), and
[order receipt and native observation](../order-contract/receipt.json) retain
actual results and artifact hashes. Raw streams remain private. Hashes establish
byte identity, not independent provider attestation.

LEAN accounting is exact over exported values and reconciles to rounded native
totals within half a cent; exported prices do not expose internal precision.
All **1,476** mounted engine/data hashes remained unchanged. Two build/restore
timeouts are retained; the accepted recipe uses the installed native compiler.
The SDK's first instrumentation attempt blocked an import-time IPv6 capability
probe; the final isolated run distinguishes construction from transport.

## Native replay

Use [the accepted 36-distribution SDK lock](../../../adoption/sdk/README.md),
the existing remediated LEAN engine and fresh private outputs. These runners are
local adapters around upstream APIs, not unchanged upstream examples.

```sh
python3 blueprints/us-equities/execution-realism/run.py \
  --lean-source "$LEAN_SOURCE" --dotnet "$DOTNET_ROOT/dotnet" \
  --out "$NEW_PRIVATE_RESULT_DIR"

"$SDK_PYTHON" blueprints/us-equities/point-in-time/temporal_snapshot.py snapshot \
  --source blueprints/us-equities/point-in-time/fixture.json \
  --output "$NEW_PRIVATE_SNAPSHOT_DIR"

python3 blueprints/us-equities/order-contract/order_contract.py \
  < blueprints/us-equities/order-contract/basic-intent.json
```

Follow [temporal selection](../point-in-time/README.md) using the digest returned
by that new snapshot, then the documented cutoff/feed/universe query. Follow
[the SDK probe recipe](../order-contract/README.md) for network isolation.
Version output alone is not acceptance.

## Integration and next waves

The manifest now records **48 selected components**. Alpaca's SDK was already
installed in the accepted lock; this adds its explicit component/adoption mapping
without another package installation. The catalog still contains **479 repository
identities**. This wave deepens proof of selected capabilities.

1. **Historical catalyst/candidate replay:** declare extreme-mover labels and
   preserve as-known schedules, article/bar versions, receipt times and complete
   candidate universes. Accept source rights and exact timestamp handling.
2. **Both-track experiments:** freeze labels, chronological splits, costs/latency
   and controls; compare pre-event and post-signal hypotheses. Record all attempts.
3. **Execution state:** exercise offline duplicate/uncertain-result, partial-fill,
   restart, cancel and reconciliation before authorized paper integration.
4. **Foundation operation:** continue held-out retrieval, native memory lifecycle,
   off-host recovery and unattended-host acceptance against the
   [open-gate ledger](../../../catalogs/us-equities/convergence-review.json).

No client restart or extra sign-in was required for these offline commands.
This session used direct Context Mode and bounded workers. The deterministic
scripts make no model calls; that does not mean the coordinator or workers used
no tokens. This wave establishes no causal provider-token savings, new model
inference receipt, Mac/remote-host acceptance, paid deployment or broker order.
