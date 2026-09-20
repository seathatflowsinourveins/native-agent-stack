# Two maintained catalogs

| Catalog | Purpose | Start here |
| --- | --- | --- |
| Foundation | Native Codex/Claude runtimes, rules, skills, workers, isolation, retrieval, memory, research, efficiency, evaluation, CI, scheduling, hosting, recovery and observation | [Foundation guide](foundation/README.md) · [Layer manifest](foundation/manifest.json) · [Harness defaults](../docs/harness-defaults.md) |
| Trading architecture | Reproducible historical/simulation research and separate IBKR/NautilusTrader and Alpaca paper execution boundaries | [US-equities guide](us-equities/README.md) · [North star](../blueprints/us-equities/north-star.md) |

Both catalogs reference shared component pins, upstream source reviews and scoped execution receipts. General engineering does not inherit broker prerequisites. Trading work reuses the foundation and adds data, strategy, risk and broker-specific acceptance.

The broad repository decision union remains at [its existing path](us-equities/decision-index.json) for compatibility; it contains shared research discovery, not just trading adoption. Curated lists and stars are discovery sources. Explicit catalog decisions establish selected capabilities, and execution receipts establish only the workflows they actually measured.
