# Requirement coverage and remaining acceptance

Source matrices checked 2026-09-19; current routing updated 2026-09-20. This is a
bounded architecture selection across eighteen requirements. The [runtime target](../../../catalogs/us-equities/runtime-target.json)
and [acceptance plan](../engine-nautilus/acceptance-plan.md) govern the selected
Nautilus/IBKR and separate Alpaca paths; older source matrices retain their dates.
The central identity union accounts for the full public star snapshot and explicitly registered beyond-star candidates. Identity coverage
does not mean every file was reviewed or every repository installed.

| Requirement | Current selection | Remaining acceptance |
|---|---|---|
| Native clients and SDKs | Codex, Claude; native paired worker workflow | Per-host hooks/settings and provider cancellation |
| Token-efficient architecture | Context Mode, RTK, bounded retrieval, native caching | Exact-release hook behavior; causal net savings |
| Memory and learning | One ai-memory store; isolated lifecycle acceptance | Evaluated learning promotion; no automatic policy adoption |
| Retrieval | QMD, SocratiCode, DuckDB | Held-out quality and financial corpus completeness |
| Embeddings and models | Accepted local encoder; MLX conditional on Mac | Model/corpus migration and native Mac serving |
| Skills and orchestration | Native skills, Dagu; DeerFlow optional | Skill compatibility; durable replay when required |
| Portability | Locked Linux/WSL recipes | Native macOS acceptance |
| Worker lifecycle | Native systemd transient tree cleanup | Provider interruption, partial-result reconciliation |
| Observation | OTel, Loki, Prometheus, Grafana, grand dashboard | Outage delivery/loss accounting and alert coverage |
| Recovery and supply chain | Existing restic, snapshots, Syft evidence | Off-host recovery and key custody |
| Historical/PIT data | LEAN baseline, reviewed universe semantics | Data rights, delistings, actions and original availability |
| Events and exact time | Native integer-nanosecond replay | Actual provider capture, revisions and receipt timestamps |
| Factors and extreme movers | Frozen daily/intraday catalyst protocol | All-candidate historical research and controls |
| Backtests and evaluation | NautilusTrader 2.0.0rc5; LEAN historical comparison; skfolio conditional | Retained equity replay/parity; holdouts, calibrated execution, funding, full trial ledger |
| Market-state transitions | Causal stress experiment; offline diagnostic candidates | General selector, stale-state rules and transition costs |
| IBKR | Native Nautilus socket adapter; paper path selected | Native TWS/Gateway sign-in, paper account, unique client ID, data permissions and execution/recovery acceptance |
| Alpaca | SDK, offline contract and dated authenticated read-only acquisition; separate paper adapter | Current entitlements/Elite activation, execution adapter, risk journal/reconciliation and paper acceptance |
| Grand dashboard | Native health/usage plus recorded decision/gate progress | Checkpoint maintenance and additional execution adapters |

The new source matrices are [foundation](../../../catalogs/us-equities/convergence-program/foundation.md),
[trading/data](../../../catalogs/us-equities/convergence-program/trading.md) and
[hosting](../../../catalogs/us-equities/convergence-program/hosting.md). They retain
defaults, comparators, rejected/deferred candidates, release and commit identities,
source hashes and depth labels. Current defaults remain coherent; additional
repositories are adopted only when they solve a demonstrated requirement.

The three source matrices contain 36 decisions and 169 newly captured
pinned source captures (167 distinct repository/path/hash files), plus 10
explicitly reused source references. Review covered
selected sections, not every byte of those files. Each matrix contains two
bounded discovery/challenge rounds; this is not a universal saturation claim.

Alpaca Elite's 200/1,000 tier concerns **API calls per minute**, not completed
trades. Current margin semantics differ from older PDT model implementations.
Consult the [current primary-source review](../../../catalogs/us-equities/convergence-program/trading.json)
and verify the actual account before paper execution. Simulation is the user's
current priority. September 20 [authenticated data receipts](../authenticated-data/README.md)
and [identity observations](../identity-readiness/README.md) preserve actual read-only
Alpaca access; the former also records the earlier read-only paper-account check.
The remaining gate is current account/feed/routing permission and broker execution
acceptance, not a blanket claim that Alpaca credentials are absent. IBKR native
sign-in and broker acceptance remain unestablished. No credentials are copied or
queried by this coverage update.
