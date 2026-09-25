# Earnings announcement premium (EAP) with SEC 8-K Item 2.02 dates

Phase 1 of a historical test of the Frazzini-Lamont earnings announcement premium in US
common stocks, 2017-01 to 2026-08. Expected announcement months come from SEC 8-K
Item 2.02 acceptance times. The question is whether the expected-announcer long leg beats
SPY after measured costs. The published US results are 61 bp/month for 1973-2004
(Frazzini-Lamont) and 75.9 bp/month for 1991-2010 (Barber et al.). Nothing in this design
uses a view on the premium after 2004. A claim that it disappeared (Heitz, Narayanamoorthy
and Zekhnini, SSRN 3296537) was not retrieved or verified here and is not a prior.

**Status:** `protocol.json` is `draft_pending_independent_pre_outcome_review`
(`frozen_before_outcomes: false`). No return, P&L, hit rate or post-decision price change
has been computed on real data. `evaluate.run()` refuses until the protocol is frozen,
recorded in `receipts/freeze-record.json`, every pin matches and the directory is clean in git.

## Files

| File | Purpose |
| --- | --- |
| `protocol.json` | Preregistration. Primary adoption family: EAP-2 then EAP-4, a fixed sequence at alpha 0.05. Secondary family: EAP-1 and EAP-3 under Holm. Also segments, minimum samples, MDE, upper-bound wording, costs, deviations D1-D13 and `pins`. |
| `collect_edgar.py` | Resumable SEC collector (<= 8 req/s, raw bytes with a sha256 manifest): `universe`, `fetch`, `tzcheck`, `extract`. |
| `expected_dates.py` | Pure point-in-time rules (rollover, exactly-4, fiscal-quarter matching, event-time) and the `accuracy` CLI (no returns). |
| `eap_signal.py` | Pure lanes, delisting-aware holding returns, portfolios, 2% capped weights, cost tables, fees, Newey-West t, t quantiles, Holm and the fixed sequence. |
| `spreads.py` | Measured closing half-spreads on D(t) sessions from Alpaca SIP quotes (data host only), producing `data/cost-table-eap-v1.json`. |
| `prefreeze.py` | Survivorship, weight-concentration and event-count receipts built from pre-D(t) inputs. |
| `evaluate.py` | Guarded evaluation. The guard lives in `run()`, and the data pass needs the `FrozenProtocol` token that `guard()` creates. `--print-pins` hashes the pinned files. |
| `data/cost-table-eap-v1.json` | The pinned measured cost table (HIST). |
| `receipts/` | Pre-freeze receipts (counts and sha256 only) and `freeze-record.template.json`. |

## Commands

The private data root is `~/.local/state/native-agent-stack/research/sota-mover/eap/`. It
is not in git. Use the tool Python that has DuckDB; the pure tests also run on the system `python3`.

```bash
PY=~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python
DAILY=~/codex-ecosystem/state/broad-market-20260921/dataset/daily.parquet
ROOT=~/.local/state/native-agent-stack/research/sota-mover/eap
BR="env ECOSYSTEM_JOB_MEMORY_HIGH=3G ECOSYSTEM_JOB_MEMORY_MAX=4G ECOSYSTEM_JOB_SECONDS=7200 ~/codex-ecosystem/bin/ecosystem-bounded-run"
$PY collect_edgar.py universe --daily "$DAILY"
$BR $PY collect_edgar.py fetch --rate 7.0
$PY collect_edgar.py extract && $PY collect_edgar.py tzcheck --sample 24
$BR $PY expected_dates.py accuracy --root "$ROOT" --daily "$DAILY"
$PY spreads.py sample --daily "$DAILY" && $BR $PY spreads.py fetch && $PY spreads.py table
for c in survivorship weights events; do $BR $PY prefreeze.py $c --daily "$DAILY" --out receipts/$c.json; done   # then: mv receipts/events.json receipts/event-counts.json
$PY evaluate.py --print-pins --root "$ROOT" --daily "$DAILY"   # values for protocol.json#/pins
```

Evaluation happens only after the freeze. The coordinator commits the frozen protocol, then
writes and commits `receipts/freeze-record.json` from the template. `evaluate.py` takes the
expected sha256 from that record; an optional `--protocol-sha256` must equal it.

```bash
$BR $PY evaluate.py --root "$ROOT" --daily "$DAILY"
```

Tests (SYN), run from the repository root:

```bash
python3 -m unittest tests.test_sota_eap_expected_dates tests.test_sota_eap_signal \
  tests.test_sota_eap_evaluate tests.test_sota_eap_collect -v
# the DuckDB classes, including the frozen end-to-end run in a scratch git repo, need:
$PY -m unittest tests.test_sota_eap_evaluate -v
```

## Pre-freeze results (HIST, no outcomes)

**Identity**

- 6,127 CIKs (7,276 symbols) out of 8,004 current SEC CIKs match daily-dataset symbols.
- Per decision session, 1,406-2,112 main-lane-qualifying common-like daily symbols (33.8%-42.2%) have no current CIK: `receipts/survivorship.json`.
- The resulting bias is unsigned (deviation D3). The unmatched names include failures, acquired firms, funds and ADRs.

**Filings**

- 642,028 rows, including 142,944 Item 2.02 8-Ks dated 2015-01-05..2026-09-24 from 3,973 CIKs.
- Every SEC response was HTTP 200.
- `acceptanceDateTime` is UTC. Converted to Eastern time, it equals the SGML header in 24 of 24 samples.

**Date-prediction accuracy (monthly rule, main lane)**

- 89.8% of expected firm-months announced in the expected month, and 89.5% of actual announcements fell in their expected month.
- The event-time rule is within 7 days for 93.1% of matched announcements.

**Event counts**

- Firm-months with >= 5 known Item 2.02 events: 8.1% of all mapped firm-months and 12.6% of the main lane (`receipts/event-counts.json`).

**Weights**

- The capped long leg has a maximum weight of 1.88%-2.00% and an effective N of 54-199.
- Uncapped, a single name reached a 59% weight (effective N 2.7): `receipts/weights.json`.

**Costs**

- 3,236 stratified closing-quote samples, all HTTP 200.
- Median half-spread by dollar-volume tier: 9.7 bp ($1-5M), 4.2 bp ($5-50M), 2.4 bp ($50-500M) and 1.5 bp (>= $500M): `data/cost-table-eap-v1.json`.
- The mover-v1 table (18-75 bp) is kept only as a sensitivity.

## Evidence labels

- **SYN:** unit tests and the scratch-repository end-to-end run on synthetic data.
- **HIST:** the real SEC metadata, identity, clock, accuracy, spread, survivorship, weight and event-count receipts.

Nothing here is upstream acceptance or a paper or live result.

## Known limitations

These are recorded in `protocol.json#/deviations`:

- Current-ticker identity (survivorship, unsigned).
- No delisting returns.
- Dollar-volume weights capped at 2% instead of market capitalisation.
- Item 2.02 filings are noisier than earnings dates.
- A quoted closing spread overstates closing-auction costs.
- 116 months give 80% power only above about 0.56%/month even at the optimistic SD assumption, against an expected adoption effect near 0.4%/month.

## Result of the frozen run (2026-09-25, protocol sha256 `c00ca2cd…`, freeze commit `0332a94e`)

One evaluation, run once after the pushed freeze, HIST evidence, 116 valid months (2017-01..2026-08). Summary in
`receipts/evaluation-summary.json`; the full private file is hashed there.

| Item | Family | Mean per month | t (NW 4) | p one-sided | 95% upper bound |
|---|---|---|---|---|---|
| EAP-2 long leg minus SPY | primary | +0.105% | 0.50 | 0.31 | 0.455% |
| EAP-4 EAP-2 net of measured costs | primary | +0.060% | 0.28 | 0.39 | 0.410% |
| EAP-1 long-short | secondary | +0.202% | 0.98 | 0.16 | 0.544% |
| EAP-3 high past-reaction subset minus SPY | secondary | +0.121% | 0.26 | 0.40 | 0.880% |

Decision: `no_evidence_underpowered`. The fixed sequence stops at EAP-2, so the pre-positioning rule is not adopted.
For EAP-1 the one-sided 95% upper bound (0.544%) lies below Frazzini-Lamont's 0.61% per month (a comparison stated
after the result, not a preregistered item). Descriptive only: the uncapped dollar-volume-weighted long leg minus SPY
is +0.52% per month (t 1.85), but those weights put up to 59% in one name, which is why the 2% cap was preregistered;
it is a candidate hypothesis for a new protocol, not a finding. The equal-weighted long leg minus SPY is -0.20%.
