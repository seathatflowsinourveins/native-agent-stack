# Frozen catalyst experiment

This is a numeric exploratory protocol for two US-equity research hypotheses.
It extends the [earlier research contract](../acceptance-wave/research-protocol.json)
without claiming a strategy works. [protocol.json](protocol.json) is authoritative;
its first executed hash is retained in the [native receipt](receipt.json).

| Lane | Fixed candidate rule | Timing |
| --- | --- | --- |
| Daily agreement continuation | Newly available original SEC8-K Item1.01; completed-session return≥2%; volume≥1.5×prior20-session median | Decide16:15ET; first eligible quote next full session09:35 or later; fifth holding-session15:55 exit |
| Intraday catalyst early mover | Known Item1.01 available within0–3session windows; completed-minute return≥5% from prior close; elapsed-session volume≥3×the same elapsed window in20prior sessions | Decisions09:35–10:30ET each minute; entry≥60seconds later; exit after60minutes or15:55 |

These are post-catalyst hypotheses. An unscheduled event learned afterward cannot
justify pre-positioning. SEC [Item1.01](https://www.sec.gov/files/form8-k.pdf)
describes a material definitive agreement; it does not establish favorable news.
The original event, filing, parsed item and subsequent amendment are separate.
An absent parser result is unknown, not confirmed absence of a catalyst.

The common universe requires historically supported ordinary-share/listing
identity, prior close$1–50, twenty complete prior sessions and median daily dollar
volume≥$5million. All eligible, rejected, missing and eventual non-mover cases stay
in the ledger. Candidates are never drawn from a list of eventual winners.

The fixed prices, liquidity, timing and risk values are research choices accepted
before outcome inspection. They are not calibrated estimates, recommended trades
or claims about Alpaca buying power.

## Availability and execution boundaries

Each input needs a source hash, its economic/valid time and a separately supported
availability time. Current downloads do not become historical knowledge. Unknown
original availability uses actual observation conservatively and fails historical
eligibility. The [identity wave](../identity-readiness/README.md) illustrates that
boundary with real captured responses; its data is not a ready catalyst universe.

A minute timestamp identifies its start. Completion and actual availability must
both precede the decision. Late revisions cannot rewrite prior decisions. The
protocol skips half-days in v1 and requires complete matching volume windows;
missing/zero-activity bars are quarantined, with no inferred halt or forward fill.
This follows the distinctions in Alpaca's
[aggregation documentation](https://docs.alpaca.markets/us/docs/market-data-faq).

Daily16:15 formation uses completed bars, not a stale regular-session quote.
Every entry needs a supported fresh quote, spread≤100bps and actual halt/session
evidence; intraday decisions also require that quote gate. Split bases must agree
across price, share-volume and trailing windows. Cash distributions and delistings
need supported units and proceeds before any accounting claim.

## Outcomes, controls and partitions

The +200% threshold means a price ratio≥3, but these are distinct labels:

- One-session regular close / prior close.
- Same-session regular high / regular open.
- Same-session high / prior close.
- Close exactly five sessions later / anchor close.
- Declared exit midpoint / executable-entry midpoint.

High-based labels are ex-post excursions, not attainable sales. Return text uses
28 significant Decimal digits for display; +200% flags use exact rational source
values, so display rounding cannot turn a just-below-threshold value into a hit.
The label helper does arithmetic only; the future dataset must prove each timestamp and price
basis. First crossings remain resolution-limited; missing horizons stay censored.
The synthetic formula example is separate from the synthetic candidate row and
must not be interpreted as its subsequent market performance.

Both lanes retain combined, event-only, price/volume-only, matched non-catalyst and
cash arms. Matching uses pre-outcome price/liquidity bins and a fixed hash rule.
All false positives, nonfills, missing controls, halts and negative results remain.

Development is2022–2023, validation2024 and provisionally reserved2025.
Calendar labels alone grant no holdout status: a complete per-case inspection
registry is mandatory, and known inspected reserved cases cannot be scored there.
The previously inspected2021Q1 ETF control is permanently unavailable as a fresh
holdout. No later boundary changes may be selected from observed outcomes.

Optional later development fitting can reuse native
[skfolio WalkForward](https://skfolio.org/generated/skfolio.model_selection.WalkForward.html)
on session rows with252/63/6; this wave does not run it or fit a selector.
Actual label intervals and shared issuer-event groups require independent purge
checks. Incomplete outcomes crossing segment boundaries remain censored.
The baseline contains two fixed rules, not a regime-switching optimizer.

## Simulation risk and promotion

The frozen simulation capital is$100,000, with1×baseline gross exposure.
Separate2×/4×sensitivities are hypothetical simulator parameters. Fees, maintenance
margin and liquidation can make a4×path immediately infeasible; retain that
failure. They are not account entitlements or automatic leverage choices.

The protocol specifies executable bid/ask crossing, per-share fees,10/50bps
adverse impact,60/300second latency and volume/displayed-size capacity limits.
Borrowed-cash financing uses explicitly hypothetical10%/20%APR assumptions.
Cash accounting, dividends/splits, margin and liquidation require a later reviewed
LEAN execution integration; no such run occurs here. The
[LEAN slippage API](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/supported-models)
is an integration reference, not evidence those cost assumptions are calibrated.

Research promotion requires250fills,100issuers and40entry sessions per lane and
evaluation segment,≥90%matched controls, positive net return and a positive
simultaneous confidence bound versus matched controls, drawdown≤20%, and the
predeclared1×cost/latency stress. The protocol fixes bootstrap settings and retains
every arm and stress path. Rare +200%labels require separate minimum counts;
insufficient evidence never permits lowering the threshold after inspection.

These gates can authorize proposing a separately reviewed paper candidate.
Neither passing a synthetic test nor a favorable historical result submits orders
or authorizes live trading.

## What actually ran

The project-owned [exercise](exercise.py) calls the installed upstream DuckDB
Python API. It is not an upstream trading CLI and does not fetch data.

```python
connection = duckdb.connect(":memory:")
connection.execute(availability_sql, {"cutoff": integer_ns}).fetchall()
```

Using DuckDB1.5.5/Python3.13.15 with network access disabled:

| Synthetic check | Direct result |
| --- | --- |
| Five observations, cutoffs100/110/120/130 | Selected counts0/1/1/3 |
| Unknown availability / local quarantine | Excluded at every tested cutoff |
| Future-source timestamp perturbation | Earlier cutoff120 remains unchanged |
| BIGINT epoch arithmetic | One nanosecond remains exactly1 |
| Candidate boundary examples | Both fixed lanes pass supplied synthetic prerequisites |
| Thirteen focused failure/boundary tests |13passed |

The [contract helper](contract.py) checks supplied feature shapes, thresholds,
clock boundaries, split-basis agreement, label formulas, purge intervals and
registry prerequisites. It does **not** build real features, validate actual venue
calendars, establish source truth, rank portfolios, match controls, bootstrap
returns, reconcile cash or implement promotion. These remain explicit empirical
and implementation gates.

The separate entry_gate helper checks minimum latency only. It does not implement
the daily next-session schedule, quotes, spread, liquidity, halt or portfolio-risk
gates. The original native run is retained; a reviewed exact-rational label-boundary
correction produced a second immutable synthetic run with the same protocol hash.

## Reproduce the bounded exercise

Use an already adopted SDK environment with DuckDB1.5.5. No installation or login
is needed for this offline exercise. Set a new private output parent and an
existing Python executable; the run refuses to overwrite an existing output.

```bash
SDK_PYTHON=/path/to/adopted/sdk/bin/python
RUN_PARENT=/path/to/new/private/catalyst-protocol-run
mkdir -p "$RUN_PARENT"
bwrap --unshare-net --ro-bind / / \
  --bind "$RUN_PARENT" "$RUN_PARENT" --tmpfs /tmp \
  "$SDK_PYTHON" blueprints/us-equities/catalyst-experiment/exercise.py \
  --output "$RUN_PARENT/run-1"
python3 -m unittest discover -s tests -p test_catalyst_experiment.py -v
```

Run from the repository root. Bubblewrap availability and these Linux isolation
flags are host-specific; this receipt establishes no macOS execution.
The private freeze binds protocol, source and synthetic-input hashes before
native SQL/labels. Public receipts retain compact results and artifact hashes,
without host paths. No provider usage or token-savings claim comes from this wave.
