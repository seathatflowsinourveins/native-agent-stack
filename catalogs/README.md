# Two maintained catalogs

Start with the [grand catalog handbook](../docs/grand-catalog-handbook.md). It
explains the September 22, 2026 layer verdicts: 20 foundation and 12 trading
layers, each with its winners, named alternatives, evidence class and the
comparison that would overturn it, plus how to rerun them.

For the full rows, use the [landscape ledger](landscape/README.md), its frozen
snapshot [layer-verdicts-20260922.json](sota-convergence/layer-verdicts-20260922.json)
or the offline comparison view (`docs/ecosystem/index.html#landscape`,
generated with `python3 scripts/build_ecosystem.py --write` -- not committed,
or download it from a `publish-catalog.yml` workflow artifact (7-day retention, `workflow_dispatch`/`v*`-tag runs only)). The
[trading gate ladder](us-equities/gates-20260922.json) tracks the sim → paper →
live gates.

| Catalog | Purpose | Start here |
| --- | --- | --- |
| Foundation | Native Codex/Claude runtimes, rules, skills, workers, isolation, retrieval, memory, research, efficiency, evaluation, CI, scheduling, hosting, recovery and observation | [Foundation guide](foundation/README.md) · [Layer manifest](foundation/manifest.json) · [Harness defaults](../docs/harness-defaults.md) |
| Trading architecture | Reproducible historical/simulation research and separate IBKR/NautilusTrader and Alpaca paper execution boundaries | [US-equities guide](us-equities/README.md) · [North star](../blueprints/us-equities/north-star.md) |

Both catalogs reference shared component pins, upstream source reviews and scoped execution receipts. General engineering does not inherit broker prerequisites. Trading work reuses the foundation and adds data, strategy, risk and broker-specific acceptance.

Both follow the [upstream acceptance evidence policy](../docs/acceptance-evidence-policy.md): research and reuse supported upstream skills, examples, tests and automation; retain actual native results and independent observations. Our integration tests and synthetic fixtures remain explicitly scoped.

The [GitHub automation handbook](../docs/github-automation.md) defines check and
maintenance ownership, manual publication provenance, and representative native
research acceptance with measured baselines and explicit limitations.
The [automation manifest](foundation/automation.json) records selected upstream
revisions, maintenance ownership and actual hosted qualification separately from
proposals and remaining gaps.

The broad repository decision union remains at [its existing path](us-equities/decision-index.json) for compatibility; it contains shared research discovery, not just trading adoption. Curated lists and stars are discovery sources. Explicit catalog decisions establish selected capabilities, and execution receipts establish only the workflows they actually measured.
