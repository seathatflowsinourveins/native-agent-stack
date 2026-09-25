# Native-fault harness on macOS, 2026-09-24 10:23 ET: C01/C02 native, C04/C05 still blocked

This is the committed minimal harness (`../../native-faults/`: `harness.py` sha256 `af7ce5cd…`, `plan.json`
`2ce6f6be…`) run from the read-only `6f7a77c` archive (`../mac-2026-09-24-a-passed/frozen-6f7a77c.SHA256SUMS`) in the
same runtime, following the documented procedure (`../../native-faults/README.md`, "Run"). The host is
`macos-m5pro-20260924`, the second physical machine; the state root was the dedicated
`~/.local/state/native-agent-stack/native-faults`, and the harness took the engine's account-writer lock. It ran at
14:23:10Z, before `../mac-2026-09-24-a-passed/`, so its SPY order predates that ledger's history window. The receipt is
`receipt.json`, byte for byte as the harness wrote it. It holds no credential, account id or account fingerprint.

Result: `native_faults_incomplete`, exit 1. This is the documented outcome for the current engine. One POST of the
four allowed was reserved.

| Case | Outcome | Evidence class | Broker requests |
|---|---|---|---|
| C01 accept resting buy (SPY 1 @ 382.96, bid 765.92) | passed | native_paper | submit 200, `pending_new` |
| C02 cancel resting | passed | native_paper | cancel 204 plus six reads 200, `canceled` |
| C05 cancel again | passed | engine_short_circuit | one read, no DELETE; found terminal by client id |
| C04 definitive rejection (306.4001) | unobserved | none | none; refused before send, `invalid_price_increment` |

Cleanup proved flat with `runner.reconcile`: 0 open orders, 0 positions, cash delta 0.00. This matches the 2026-09-23
WSL receipt (`../../native-faults/receipt.json`) case for case, so C01 and C02 now have native paper evidence on two
physical machines.

`plan.json` has no C03; its cases are C01, C02, C05 and C04. Native evidence for C05 (a real DELETE and its refusal)
and C04 (a definitive refusal that reaches the broker) is blocked on the unmerged engine changes in PR #169. This run
does not duplicate them. The `native-fault-behaviour` gate stays `not_established`, and its receipt path is
unchanged.
