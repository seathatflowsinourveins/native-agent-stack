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
123 execution checks and19 preconditions, with no failures, skips or blocking
mappings. The actual data files were rehashed at execution and comparison.
All four declared UUID-normalized economic exports have the same SHA256.
The [published receipt](../../blueprints/us-equities/engine-nautilus/spy-parity/receipt-stress-20261002.json)
contains the exact engine, review/source/data hashes, starts, original receipt
digests and observed economics. Full raw returns remain in private task evidence.

The native fills are304 SPY bought at324.227160 and sold at291.106620,
at the frozen entry/exit timestamps. Fees are2.00 USD, dividends428.64 USD,
and final quantity zero. Native cash is **90357.99 USD**, while exact Decimal
reconciliation is90357.995840 USD. Per-order native Money rounding accounts
for the difference from the prospective cent display90358.00. The unchanged
0.01 USD cash tolerance passes; the oracle, deadline, mapping and tolerance
were not changed after execution. Each engine processed725 bars, recorded
zero error log lines and ended with no open orders, positions or pending intents.

The first two isolation attempts failed before any engine ran: C1 denied mount
propagation, and C2 denied the proc mount. Their logs remain preserved.
C3 supplied task-container `systempaths=unconfined`, retaining the inner strict
fence; no host/VM sysctl or existing profile was changed. Owned engine and
comparison processes exited0. The sleeping container controllers required the
Docker stop timeout/SIGKILL and exited137; that is preserved separately from
the successful engine checks.

## Recovery source and pinned SDKs

At `2c669e18f705212f6f407b80f668d2a253591167`, explicit and forced recovery
startup require benchmark quotes. Each owned residual exit continues to require
a fresh quote for its own symbol. A missing quote for another held symbol no
longer blocks an otherwise safe owned exit. The two new wiring tests fail at
the base source and pass after the constructor correction.

The [recovery receipt](../../blueprints/us-equities/adaptive-paper/receipt-recovery-f1-20261002.json)
binds four exact source hashes and the official hash-locked macOS ARM64 runtime:
Python3.13.15, Alpaca-py0.44.0 and Nautilus2.0.0rc5. Fourteen bounded runs
passed **523 unique tests**, with zero skips/failures and exit0 throughout.
These exercise real SDK/native code against deterministic fake broker ports,
including residual-only reconciliation, ambiguous submissions across reopen,
durable STOP and callback/accounting guards. They do not call paper accounts.

The initial415-test run carried133 dependency skips; it remains historical.
Two later controller-limited runs were incomplete and are excluded from the523
total. The initial uv option conflict is retained; its correction kept
binary-only, hash-locked official installation. The pinned engine's upstream
callback-loss reproducer still requires the existing callback guard.

## Admission and case boundaries

| Required scope | Current observed disposition | Remaining action |
| --- | --- | --- |
| Frozen `one_zero` | Historical receipt at its original source; no new replay here | Preserve its exact scope. A changed harness/host needs prospective qualification. |
| Frozen `one_stress` | Two fresh processes qualify the new reviewed stress mapping as above | Carry the measured receipt; do not broaden it to other cases. |
| Frozen `over_limit` | New refusal-only mapping under preparation | Independently review the exact native risk-denial source and run the frozen no-fill comparison before qualification. |
| Frozen `two_zero`, `two_stress`, `adaptive_stress` | Blocked by pinned native maintenance-margin and liquidation mapping gaps | Reproduce frozen mark-to-market maintenance and partial-liquidation economics with an upstream-supported, reviewed mapping. No invented fills/cash or tolerance widening. |
| Surviving NativeStack WSL2 | Destination/transport not enrolled in this task | Follow the [activation packet](2026-10-02-north-star-host-paper-activation.md); qualify the actual workstation and its platform artifact lock. Mac Linux simulation is insufficient. |
| Alpaca paper | Required Keychain entries absent; no account call | Store credentials in the native Keychain, perform supported read-only preflight, then separately admit the paper/fault run. |
| IBKR paper | Local native session absent; exact rc5 recovery harness gap persists | Qualify the single-account rc5 order/restart/fill-replay sequence. Historical1.231 lifecycle is insufficient; open upstream5007/5057/5060 remain visible. |
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
