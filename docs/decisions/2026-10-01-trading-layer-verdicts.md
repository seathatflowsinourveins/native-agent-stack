# Trading layers: owner's verdicts after the 2026-10-01 closure assessment

- **Status:** accepted by the trading lane owner, 2026-10-01.
- **Scope:** the 12 us-equities layers of `catalogs/landscape/research-state.json`.
- **Related records:**
  - the program record `docs/decisions/2026-10-01-definitive-sota-wsl-program.md` (#573);
  - the architecture edition in PR #574 (`catalogs/foundation/new-wsl-architecture-20261001.json` on that branch), whose 12 trading rows carry these verdicts.

## Inputs

- **The assessment.** `evidence/artifacts/layer-closure-assessment-20261001/us-equities.json`, with
  `us-equities-run-variance.json` and `us-equities-synthesis.md`.
  - Method: one Claude Opus assessor and one adversarial Claude Opus refuter per layer.
  - They read PR #358's head `4d11709c`.
  - Six layers have two complete refuted results (the workflow was resumed after a sign-in); two of them differ by
    one step (backtesting-engine c1 and c4, portfolio-risk c5). The conclusions hold in both.
- **The criterion.** `catalogs/landscape/research-state.json` `saturation.close_only_when`, items c1-c5.
- **Evidence class of the assessment.** Model-authored source review. It is neither an acceptance class of
  `docs/acceptance-evidence-policy.md` nor the second independent review that c4 asks for.
- **Spot-checks on main `b72c588f`** (2026-10-01):
  - `manifests/stack.json` versions match every stack pin named below. pandera, grype and codex-native-sdk are not
    in it: pandera's pin comes from the layer entry, grype's from `catalogs/foundation/automation.json` (sha256-pinned,
    run by `supply-chain.yml`), and codex-native-sdk's from the artifact (CLI rust-v0.155.1, openai-codex 0.154.0).
  - Every layer entry in `catalogs/landscape/us-equities.json` has `checked_at` 2026-09-22.
  - `catalogs/landscape/us-equities.json:2773` (skfolio `conditional`) and `:2840` (skfolio as `component_id`) are as
    cited.
  - `runtime-target.json` had no security or supply-chain entry.
- **A correction of the owner's own wording.** An earlier draft of these verdicts, and the first version of #574's
  backtesting-engine note, named an undecided `costs_and_routing` contract. That was a misreading of a truncated
  assessment string; the assessment itself names `costs_and_rounding_stress`. The blockers of the five SPY cases are
  `costs_and_rounding_stress` and `margin_and_adaptive_state`
  (`blueprints/us-equities/engine-nautilus/spy-parity/mapping-manifest-v2.json`, `dependent_comparison_status`).

## Rules applied (shared with every row of the architecture edition)

- **Closed or open.** A layer is closed only when all five items are met. Otherwise its verdict is "selection of
  record, open", and the missing items are named.
- **The winner cell carries the pin of record only:**
  - `catalogs/us-equities/runtime-target.json` for the engine and brokers;
  - `manifests/stack.json` for other components;
  - the adaptive-paper engine at main `dca821cc` (#559) for the Alpaca paper path.
- **Evidence class.** The class follows the policy table. Paper results count only as fills and passed trials.
- **Gates.** Upstream and user-side gates are stated as gates, not as defects.

## Overall

**No trading layer is closed. All 12 are "selection of record, open".**
- c4 (a second independent review that finds no unresolved material gap) is unmet in every layer.
- No layer has a dated closure record (c5).
- Every layer entry is still `checked_at` 2026-09-22, before the 09-23 gap-wave2 receipts and the 09-26 cross-family
  corrections.

The first move is therefore the same for every layer: re-record the layer entry with those inputs. Only then do a
comparison and a second review mean anything.

## Rows

Distance is the number of items not met. Items are graded M (met), P (partial) and U (unmet).

| Layer | Verdict | Selection of record (pin of record) | c1-c5 | Blocking item | Gates | Evidence class of the selection |
| --- | --- | --- | --- | --- | --- | --- |
| backtesting-engine | selection of record, open (distance 4) | NautilusTrader 2.0.0rc5 (tag `v2.0.0rc5` = `1b0a49d2`, prerelease, selected destination); LEAN `985ef30a` (frozen comparison oracle, not the destination); alpaca-py 0.44.0 (separate Alpaca path) | M P P U P (other run P P P P P) | c3: five of six SPY parity cases have no mapping yet: `costs_and_rounding_stress` blocks one_stress, `margin_and_adaptive_state` blocks two_zero, adaptive_stress and over_limit, and both block two_stress (`spy-parity/mapping-manifest-v2.json`); one_zero passed 2026-09-23. Cross-family (#358 at `b0eb7a11`, after the assessment's read): GPT-6 accepts provisional retention and disputes comparative merit; consistent with `comparison_required` | none user-side; the trading lane freezes the missing mappings | Upstream example or native operation (the unchanged rc5 quickstart, `evidence/receipts/native-nautilus-v2-20260920.json`, and the LEAN sample) and local integration check (SPY/LEAN parity `one_zero` on rc5, `spy-parity/verdict-v2.json` PASS) |
| market-data-reference | selection of record, open (distance 4) | alpaca-py 0.44.0; EdgarTools 5.58.0; exchange_calendars 4.13.2; DuckDB 1.5.5 with Parquet | M P U U P | c3: no provider comparison on the frozen AAPL plan, and no point-in-time or availability evidence | paid market data (Databento arm, Massive history beyond the free tier) | Upstream native operation (bounded Alpaca AAPL acquisition and SEC access receipts, historical host) |
| research-factors-ml | selection of record, open (distance 5; owner's selection of 2026-10-01, see below) | EdgarTools 5.58.0 (stack pin) for SEC filing acquisition and parsing; skfolio 1.2.9 (stack pin) for portfolio models and chronological evaluation. Alphalens Reloaded is a conditional candidate for factor diagnostics; Qlib and tsfresh are deferred; skfolio 1.4.10 and EdgarTools 5.59.1 are upgrade candidates | P P P U P (c1 stays partial until the layer entry is re-recorded with the selection) | c3: the layer's preregistered overturn-protocol arms on the same contract | none | EdgarTools: upstream example or native operation (`blueprints/us-equities/catalyst-provenance/access-resolution.md`); skfolio: local integration check (`blueprints/us-equities/research-evaluation/receipt.json`) |
| portfolio-risk | selection of record, open; the selection is **inconsistent** (distance 5) | NautilusTrader 2.0.0rc5 risk limits (engine of record). skfolio 1.2.9 is winner in one place of the entry and conditional in another | P P U U P (other run c5 U) | c1: settle skfolio as winner or conditional; then c3 (a fresh, single-execution, preregistered matched comparison, and a separately frozen skfolio upgrade experiment) | none | Local integration check (skfolio WalkForward; the September 23 Nautilus risk-limit executions) |
| execution-broker | selection of record, open (distance 5) | NautilusTrader 2.0.0rc5 with its in-tree IBKR adapter (selected path; local broker acceptance not established). Alpaca: alpaca-py 0.44.0 with the adaptive-paper engine at main `dca821cc` | P P U U U | c3: IBKR acceptance-plan steps 2-4 on rc5 | **the user's IB Gateway paper sign-in** (2FA); upstream rc5 obstacles #5007, #5057 and #5060 open, #4946 fixed on develop in no release, fix candidate PR #5041 open (read 2026-10-01) | Alpaca: paper execution (the trading lane's class, not one of the policy's six) on engine `b528bb55`: the 2026-09-29 series passed 11 of 13 trials (receipts on main via #564). `dca821cc` (the fee fix) has no paper execution yet: it first ran in the 2026-10-01 account-2 recovery (flat at 06:14 ET), and the 2026-10-01 native-fault run rebound that gate to it (`native_faults_passed`, PR #584). IBKR rc5: source review only |
| storage-compute | selection of record, open (distance 5) | DuckDB 1.5.5 with Parquet (sole recorded winner), with the acquisition inputs above | P P U U P | c3: no representative comparison (frozen universe, history, latency, rights, correction and availability semantics) | paid data rights for the comparison inputs | Upstream native operation (broad-universe study on the historical host; its input is private and not in the repository) |
| identity-provenance | selection of record, open (distance 5) | alpaca-py 0.44.0 (symbol-mapping observations); EdgarTools 5.58.0; DuckDB 1.5.5 | P P U U U | c3: the `verdict_overturn_when` comparison on `blueprints/us-equities/point-in-time/fixture.json` with the `validate_source` invariants. No gate blocks it; it needs a recorded DVC install | user-owned identity sources (`gates-20260922.json`) for the as-known dataset | Upstream native operation (bounded acquisitions); synthetic fixture (point-in-time) |
| data-quality-orchestration | selection of record, open (distance 5; queue: on_requirement_change) | pandera v0.33.1 (layer entry; not in `manifests/stack.json`) for validation; Dagu 2.16.6 (stack pin) and systemd user units for scheduling | P P P U U | c3: the Dagu-vs-Temporal kill comparison (gap-wave2 #7) does not meet the same-fixture clause of `verdict_overturn_when` | none | Local integration check (gap-wave2 receipts) |
| evaluation-experiments | selection of record, open (distance 5; queue: on_requirement_change) | Not one selection: `current_choice` lists the foundation workers and the observability stack, while the verdict winners are inspect-ai, mlflow and agent-retrieval-bench | P P P U U | c1: reconcile `current_choice` with the verdict winners | none | Upstream native operation of foundation components; no evaluation comparison |
| agents-models-workers | selection of record, open (distance 5); **follows the foundation memory and retrieval layers** | ai-memory, SocratiCode, QMD, Serena at their `manifests/stack.json` pins; codex-native-sdk has no stack entry (the artifact gives CLI rust-v0.155.1 and openai-codex 0.154.0, behind the stack's codex CLI 0.159.2). The layer entry's pins lag the stack (ai-memory 2.3.1 vs 2.4.1; SocratiCode 1.14.0 vs 1.15.0). GPT-6 disputes the earns_it label of ai-memory and SocratiCode (#358) | P P P U U | c3: a preregistered held-out financial, document and code retrieval comparison with abstention | none | Upstream native operation (installed-pin qualification receipts, historical host) |
| observability-hosting | selection of record, open (distance 5 under the shared rule; its assessor's half-credit 4 is not used; queue: on_requirement_change) | Codex, Claude Code, Dagu, otelcol-contrib 0.161.0, Prometheus 3.15.0, Loki 3.7.8, Grafana 13.2.2, Restic 0.19.1 at their stack pins. Five pins are behind upstream; Grafana 13.2.3 is a security release | P P P U U | c2: one frozen set (the Tempo conflict; Jaeger and OpenObserve dispositions); then c3 on the target host | none | Upstream native operation (historical host); the new host collects its own |
| security-supply-chain | selection of record, open (distance 5; queue: on_requirement_change; owner's selection of 2026-10-01, see below) | Inherits the foundation gates: Syft 1.52.0 and Gitleaks 8.30.1 (stack pins) and Grype 0.119.0 (`catalogs/foundation/automation.json`, sha256-pinned, run by `supply-chain.yml`'s sbom-vuln job). Betterleaks 1.9.0 challenges Gitleaks (upstream ships security patches only and names it the successor); OSV and provenance stay scoped separately | P P P U U (c1 stays partial until the layer entry is re-recorded) | the layer's own re-run trigger (cosign verify-blob and OpenBao secret-lifecycle receipts) | none | Upstream example or native operation: Grype 0.119.0 (`evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/0-grype-sdk-sbom.json`), Syft and Gitleaks (`3-syft-binary-os-coverage.json`, `5-gitleaks-current-history.json`; those receipts do not record the tool versions) |

For the architecture page, each row's install command is the profile recipe's (`adoption/manifest.json` profiles
`trading-nautilus` and `research-runtime`). The assessment found, by reading the source, that bootstrap pins only codex and
claude-code; this is not yet confirmed by execution. So on the new distro:
- "install recorded" is a recipe pointer, not a passed install;
- each row's new-host status is "not yet installed", until the new host runs it and returns a receipt.

## Decisions on the synthesis's risks

1. **nautilus_trader #4983.** This change reclassifies it as a catalog correction, without waiting for the IB Gateway
   sign-in.
   - `runtime-target.json` moves #4983 to `rc5_reclassified_reports` as a stale v1.227.0 report. At rc5 (`1b0a49d2`) the
     execution engine denies an order only when `handles_order_venue` is false
     (`crates/execution/src/engine/mod.rs:2222`), and the IB execution client returns `true`
     (`crates/adapters/interactive_brokers/src/execution/core.rs:491-496`). This is source reading, not an rc5 order
     observation.
   - The rc5 obstacles listed instead are on the recovery and reconciliation paths: #5007, #5057 and #5060, open on
     2026-10-01. #4946 (account-scoped pre-trade checks) is closed upstream, in no release.
   - The structure follows PR #280 (2026-09-25). Its IBKR version-selection record stays with #280 and the sign-in.
   - The rc5 IBKR stock-order path stays **unqualified** until native paper execution (acceptance steps 2-4).
   - Evidence class: source review at a pinned commit, plus issue states read with `gh api` on 2026-10-01.
   - Overturn: a native rc5 paper run that reproduces a venue mismatch, or upstream evidence that #4983 applies to rc5.
2. **backtesting-engine's stale status.** A dated superseding note sits in
   `blueprints/us-equities/engine-nautilus/acceptance-plan.md`, after its September 21 status table. It reports:
   - the 2026-09-23 `one_zero` PASS (`spy-parity/verdict-v2.json`);
   - the five cases without a mapping (`spy-parity/mapping-manifest-v2.json`);
   - the IBKR step-1 receipt.
   The dated layer entry in `catalogs/landscape/us-equities.json` is not edited; the layer's re-record absorbs these
   facts.
3. **No research, factor or ML component in the selection of record.** This is true and deliberate: `runtime-target.json`
   is the engine and broker destination record. The research selection is therefore recorded separately, in
   decision 7, not in `runtime-target.json`.
4. **Evidence labels overstate classes.** The catalog term `native_proven` was applied to local integration checks (the
   skfolio winner, Dagu 2.17.0 on a patched harness, SPY parity). The rows above use the policy classes, not that label.
   The relabelling goes in the re-record units.
5. **Preregistration changed after outputs were seen** (several gap-wave2 criteria). Those results count as exploratory in
   the re-record. No layer cites them as a passed preregistered comparison.
6. **Security currency.** Grafana 13.2.3 and the gitleaks successor (Betterleaks) are foundation-pin decisions; the trading
   rows inherit them. They are raised with the foundation owner; nothing is selected here.

7. **Selections for the two layers without one (owner's decision, 2026-10-01).** The 2026-09-22 layer verdicts, the
   closure assessment (Claude Opus) and a cross-family adjudication (`gpt-6-astra`, effort max; PR #575,
   `evidence/artifacts/new-wsl-layer-reviews-20261001/selection-gap-convergence-followup.json`) converge on the same
   components. Each has a pin of record and a recorded run.
   - research-factors-ml: EdgarTools 5.58.0 and skfolio 1.2.9, as above. Nautilus is the engine, not the research
     selection. Predictive ML waits for a prediction contract and an executable economic oracle.
   - security-supply-chain: the foundation's Syft, Grype and Gitleaks gates, as above. The stack registry is not the
     only pin record: Grype's pin lives in `catalogs/foundation/automation.json`.
   - Neither selection closes the layer: c2-c5 stay open, and the layer entries are re-recorded with them in the
     layers' re-record units.
   - Overturn: the layer's preregistered comparison; a qualified upgrade (skfolio 1.4.10, EdgarTools 5.59.1); an
     activated factor-diagnostics requirement (Alphalens); a qualified Betterleaks compatibility oracle; or the
     security layer's re-run.

## Overturn conditions

- A layer re-record or a comparison changes an item's grade.
- A second independent review reports zero unresolved material gaps for a layer.
- A new upstream release or security fix changes a pin of record.
- The user selects a research, factor or ML component, or a paid data entitlement.
