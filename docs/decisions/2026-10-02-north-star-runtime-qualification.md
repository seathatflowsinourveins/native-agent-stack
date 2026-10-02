# North Star offline runtime qualification

Date: 2026-10-02. Scope: deterministic frozen-data simulation and source-level
paper-recovery contracts. The [foundation execution record](2026-10-02-north-star-readiness-execution.md)
and [two-host architecture](2026-10-02-two-host-north-star-architecture.md)
retain the selected repositories, native clients and all twenty layers.
This record reports observed execution and the remaining admission gates.

## Cost and rounding stress

The prospective independent review accepted ten exact source hashes at
`648228d3252d1e82b7e0378bfd90210d1e1aacd3`, with zero unresolved findings,
before either native engine process. A task-owned Linux ARM64 VM on the Mac
used official pinned Nautilus `2.0.0rc5` wheels, an immutable Python container,
and a strict inner bubblewrap fence. Ten zero-engine fence checks passed.
Source, runtime and data were read-only; the native process had a cleared
environment, Python isolation, separate PID/user namespaces and loopback-only
network. Host accounts, broker credentials and shared inference were absent.
This executor is not the surviving NativeStack WSL2 workstation.

Two separate fresh processes each produced two fresh native BacktestEngine
exports. Each independent strict comparison passed **142/142** checks:
123 execution checks and 19 preconditions, with no failures, skips or blocking
mappings. The actual data files were rehashed at execution and comparison.
All four declared UUID-normalized economic exports have the same SHA256.
The [published receipt](../../blueprints/us-equities/engine-nautilus/spy-parity/receipt-stress-20261002.json)
contains the exact engine, review/source/data hashes, starts, original receipt
digests and observed economics. Full raw returns remain in private task evidence.

The native fills are 304 SPY bought at 324.227160 and sold at 291.106620,
at the frozen entry/exit timestamps. Fees are 2.00 USD, dividends 428.64 USD,
and final quantity zero. Native cash is **90357.99 USD**, while exact Decimal
reconciliation is 90357.995840 USD. Per-order native Money rounding accounts
for the difference from the prospective cent display 90358.00. The unchanged
0.01 USD cash tolerance passes; the oracle, deadline, mapping and tolerance
were not changed after execution. Each engine processed 725 bars, recorded
zero error log lines and ended with no open orders, positions or pending intents.

The first two isolation attempts failed before any engine ran: C1 denied mount
propagation, and C2 denied the proc mount. Their logs remain preserved.
C3 supplied task-container `systempaths=unconfined`, retaining the inner strict
fence; no host/VM sysctl or existing profile was changed. The accepted stress
engine and comparison processes exited0. The sleeping container controllers required the
Docker stop timeout/SIGKILL and exited137; that is preserved separately from
the successful engine checks.

## Native initial-margin refusal

The refusal-only `over_limit` mapping at
`deff844fb7803c11ad5f16ab7d7db8d87f14ca4a` passed **86/86** strict checks
in each of two fresh fenced processes. Each process produced two fresh native
BacktestEngine exports; all four exports match after the declared UUID-only
normalization. The coordinator rehashed the five actual input files and original
raw exports, reproduced the normalization from the reviewed source, and verified
the review completed before both starts. The [published refusal receipt](../../blueprints/us-equities/engine-nautilus/spy-parity/receipt-over-limit-20261002.json)
binds all thirteen runtime hashes, the unchanged oracle/plan/tolerances, original
review and evidence digests, and observed native economics.

At the frozen decision close, native risk denies the 1217-share BUY request.
Its native order type `MARKET`, status `DENIED` and `OrderDenied` event remain
unchanged. The original reason is
`INITIAL_MARGIN_EXCEEDS_FREE_BALANCE: free=100000.00 USD, margin=195851.81 USD`.
Risk bypass is false, no per-order notional cap is imposed, and the native
StandardMarginModel uses the preregistered 0.5 margin rates and leverage 2.
Each engine processes 725 bars with zero fills, fill-model calls, fees, errors,
open orders or positions. Free/total cash stays 100000.00 USD and initial/maintenance
margin stays 0.00 USD at every native mark. Both frozen ex-date alerts fire; their
zero-eligible dividend emissions are on time. This qualifies economic no-fill
refusal only; it supplies no general MOO fill, maintenance-margin, liquidation
or adaptive equivalence.

The first reviewed native attempt at `473b7282` failed the existing callback
guard because the strategy had no `.id` property. It produced no complete
receipt and observed no risk refusal; its original review, partial exports and
exit1 remain preserved. A compiled native Strategy test reproduced that failure
before the one-line change to `.strategy_id`. All 15 targeted tests then passed
with zero skips, including the native OrderDenied callback and adjacent APIs.
The same independent reviewer checked that narrow repair, all source hashes
and fresh output/command bindings prospectively before the successful replays.
Earlier missing-clock and callback-retention source findings, fail-first tests
and intermediate diagnostics also remain historical; none is counted as a
successful replay or repaired retrospectively.

The task container and VM are now stopped, with artifacts/disks retained for
rollback. Before shutdown, the only remaining container process was its sleeping
controller. Its Docker timeout exit137 remains distinct from accepted replay
exit0 and the preserved failed replay exit1. The existing memory-qualification
profile remains stopped and the default Docker context remains unchanged.

## Recovery source and pinned SDKs

At `2c669e18f705212f6f407b80f668d2a253591167`, explicit and forced recovery
startup require benchmark quotes. Each owned residual exit continues to require
a fresh quote for its own symbol. A missing quote for another held symbol no
longer blocks an otherwise safe owned exit. The two new wiring tests fail at
the base source and pass after the constructor correction.

The [recovery receipt](../../blueprints/us-equities/adaptive-paper/receipt-recovery-f1-20261002.json)
binds four exact source hashes and the official hash-locked macOS ARM64 runtime:
Python 3.13.15, Alpaca-py 0.44.0 and Nautilus 2.0.0rc5. Fourteen bounded runs
passed **523 unique tests**, with zero skips/failures and exit0 throughout.
These exercise real SDK/native code against deterministic fake broker ports,
including residual-only reconciliation, ambiguous submissions across reopen,
durable STOP and callback/accounting guards. They do not call paper accounts.

The initial 415-test run carried 133 dependency skips; it remains historical.
Two later controller-limited runs were incomplete and are excluded from the 523
total. The initial uv option conflict is retained; its correction kept
binary-only, hash-locked official installation. The pinned engine's upstream
callback-loss reproducer still requires the existing callback guard.

The deterministic trading-ladder check exits 0 with no validation errors, but
reports one stale native-paper source binding among six bound files. Its retained
`native-fault-behaviour` receipt binds the old `runner.py` SHA256
`34ab492f450431e79a3d5d5c6de32185b22590e1a109b3c5fd976db0aa0aa29e`;
this correction has SHA256
`d2c2944fe24a39c4304c976f49b09b553999d8f102ab08eeb0e28856c7e7ca7b`.
The historical receipt and release hash manifest remain unchanged. The checker
reports bindings without changing gate status, so its arithmetic ladder cannot
qualify the corrected runner's native paper faults. A newly admitted paper run
must rebind actual measured source; synthetic tests do not replace that step.

## Admission and case boundaries

| Required scope | Current observed disposition | Remaining action |
| --- | --- | --- |
| Frozen `one_zero` | Historical receipt at its original source; no new replay here | Preserve its exact scope. A changed harness/host needs prospective qualification. |
| Frozen `one_stress` | Two fresh processes qualify the new reviewed stress mapping as above | Carry the measured receipt; do not broaden it to other cases. |
| Frozen `over_limit` | Two fresh processes qualify native initial-margin refusal:86/86 strict checks each, four matching normalized exports | Carry this exact economic refusal scope; native execution labels are retained and provide no general MOO or maintenance/liquidation equivalence. |
| Frozen `two_zero`, `two_stress`, `adaptive_stress` | Blocked by pinned native maintenance-margin and liquidation mapping gaps | Reproduce frozen mark-to-market maintenance and partial-liquidation economics with an upstream-supported, reviewed mapping. No invented fills/cash or tolerance widening. |
| Surviving NativeStack WSL2 | Destination/transport not enrolled in this task | Follow the [activation packet](2026-10-02-north-star-host-paper-activation.md); qualify the actual workstation and its platform artifact lock. Mac Linux simulation is insufficient. |
| Alpaca paper | Required Keychain entries absent; no account call | Store credentials in the native Keychain, perform supported read-only preflight, then separately admit the paper/fault run. |
| IBKR paper | Local native session absent; exact rc5 recovery harness gap persists | Qualify the single-account rc5 order/restart/fill-replay sequence. Historical 1.231 lifecycle is insufficient; open upstream 5007/5057/5060 remain visible. |
| Historical data fitness | Frozen fixture source/provenance checked; production PIT/data entitlement acceptance unproved | Validate the intended provider's point-in-time records, adjustments, sessions and entitlement before research claims. |
| Native memory/retrieval/provider lifecycle | Existing scoped receipts retained; broader gates remain partial/blocked | Respect the closed memory decision and current owners. No candidate trial or shared inference is queued by this offline execution. |

The paper activation packet supplies supported native authentication, per-command
Keychain use, task-scoped locked runtimes and preflight steps. It explicitly
marks commands that are missing for exact rc5 IBKR recovery. Source synchronization
does not enroll an account or authorize a live-money order.

Full-stack and two-host production readiness remain **false**. Deterministic
offline North Star implementation can proceed with these accepted cases and
explicit gaps. Whole-task usage, provider settlement, applied compression,
blind cross-family replacement convergence and net savings remain unknown.

Public artifacts contain source revisions, operation scopes and exact evidence
digests. Native account stores, personal host paths, raw histories and full
controller returns remain private. Rollback retains the isolated source commits,
official artifact locks and stopped task containers/profile; it never replaces
another owner's service or default branch.
