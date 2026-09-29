# Trading lane rules

Moved verbatim from the root `AGENTS.md`; the north star and paper-lane authorization stay there.

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
