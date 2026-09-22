# Two maintained catalogs

For the dated reason behind each selection and the named alternatives, use the
[current landscape ledger](landscape/README.md) or its
[offline comparison view](../docs/ecosystem/index.html#landscape). It covers every
foundation layer and all four domain research layers, with evidence limits and
the comparison that would change each decision.

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
