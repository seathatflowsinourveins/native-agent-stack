# Trading lane rules

Rules for trading research waves, data readiness and experiments. The north star and the paper-lane authorization are recorded below.

For brokers, engines and data, use the vendor's own maintained repositories at their clean releases: [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py), [the official Alpaca MCP server](https://github.com/alpacahq/alpaca-mcp-server) where an MCP is needed, [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader), and [the official IBKR TWS API distribution](https://interactivebrokers.github.io/). No self-built adapter where upstream ships one; glue covers only what upstream lacks and cites its source at a pin. [Current release verification](../../docs/decisions/2026-10-05-official-upstream-never-rebuild.md) records the sources; runtime selections stay with the trading lane.

For architecture or research waves, read `blueprints/us-equities/architecture/README.md`
and the matching source-review supplement. `catalogs/us-equities/decision-index.json`
is the validated repository union; register new decision arrays explicitly with
`scripts/catalog_decisions.py --write --supplement PATH.json#/collection`.

The simulation-research wave adopts isolated EdgarTools and skfolio
recipes. Read `blueprints/us-equities/simulation-research/README.md` for current
results and remaining data gates. Its 2021 control segment has been inspected,
so no experiment may present it as a fresh untouched holdout. Native filing
parsing, live SEC access and historical information availability are separate
claims. Keep provider identities local and preserve acquisition refusals.
`blueprints/us-equities/catalyst-provenance/access-resolution.md` records successful native
SEC access and real-index compatibility. Keep its monitored contact private;
bounded streaming diagnostics must bypass the upstream cache after closing clients.

`blueprints/us-equities/data-readiness/README.md` links the
September 20 catalyst-dataset and corporate-action wave. Retained source bytes,
native parser behavior, materialized data integrity and actual historical
availability are separate claims. Read that plan and the matching receipt before
repeating acquisition or advancing a strategy gate.

`blueprints/us-equities/authenticated-data/README.md` records native
Alpaca AAPL acceptance. Continue with `blueprints/us-equities/identity-readiness/README.md`
for the symbol-mapping/observation gate. A request's symbol-asof date, current asset
UUID/status and newly captured historical values are not original availability or
historical universe membership. Reuse retained anchored runs before refetching;
new hosts must establish their own permitted observations and acceptance.

For the catalyst-convergence wave, read `blueprints/us-equities/catalyst-convergence/README.md`
and its plan on demand. The frozen daily/intraday protocol is in
`blueprints/us-equities/catalyst-experiment/protocol.json`; lifecycle evidence is in
`blueprints/us-equities/lifecycle-sample/native-receipt.json`. Local observation
availability cannot substitute for original historical publication/revisions.
Native research efficiency also requires both semantic quality and the frozen
output contract. The selected direction is daily/intraday
catalyst research, including historical +200% mover discovery. Preserve as-known
candidate universes and source revisions; the current synthetic temporal fixture
and fixed LEAN schedule are not an accepted historical strategy dataset.

## Trading north star

The north star is US-equities research and historical simulation with the selected
NautilusTrader 2.0.0rc5/IBKR destination and a separate Alpaca adapter path, followed
by independently qualified paper operation for each broker. Current selections
are in `catalogs/us-equities/runtime-target.json`; dated LEAN/Alpaca receipts remain
comparison evidence rather than overriding that destination.
Read `catalogs/us-equities/README.md` for selection and `blueprints/us-equities/north-star.md`
for boundaries. The native worker policy applies to workers launched by its example,
not automatically to unrelated SDKs or projects. Keep models in research and
deterministic code in numeric/risk/order state.
The user has explicitly authorized broker-specific paper-trading E2E after the
current foundation work. Follow `docs/paper-lane-policy.md`: proceed through native
paper readiness and measured acceptance without repeated human approval. Missing
live credentials or live configuration do not gate paper; live trading and paid
hosting remain separate scopes.

Trading-lane rules for research waves, data readiness and experiments live in `blueprints/us-equities/AGENTS.md`; read it before any trading research wave, experiment, data acquisition, strategy-gate change or registration of a decision array under `catalogs/us-equities/`.
