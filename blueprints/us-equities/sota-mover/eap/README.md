# Earnings announcement premium (EAP) with SEC 8-K Item 2.02 dates

Phase 1 of a historical test of whether the Frazzini-Lamont earnings announcement
premium exists in US common stocks from 2017-01 to 2026-08. Expected announcement
months come from SEC 8-K Item 2.02 acceptance times, and the question is whether
the long leg survives measured costs. The premium is a scheduled-catalyst
pre-positioning target: it is rated plausible historically and disputed in the US
after 2004, so this is a sharp yes/no test.

**Status:** `protocol.json` is `draft_pending_independent_pre_outcome_review`
(`frozen_before_outcomes: false`). No return, P&L, hit rate or post-decision
price change has been computed on real data. `evaluate.py` refuses to run until
the protocol is frozen and its sha256 is supplied.

## Files

| File | Purpose |
| --- | --- |
| `protocol.json` | Preregistration: items EAP-1..4, Holm (m=4), segments, gates, minimum samples, MDE, costs, deviations D1-D12 and the freeze procedure. |
| `collect_edgar.py` | Resumable SEC collector: `universe` (current `company_tickers.json` mapped to daily-dataset symbols), `fetch` (submissions JSON plus needed continuations, <= 8 req/s, gzipped raw bytes with a sha256 manifest), `tzcheck` (acceptance clock against SGML headers), `extract` (8-K/10-Q/10-K rows). |
| `expected_dates.py` | Pure point-in-time functions: after-close rollover, Item 2.02 events, the exactly-4 monthly rule, fiscal-quarter matching, event-time dates and trades; `accuracy` CLI (no returns). |
| `signal.py` | Pure functions: lanes, delisting-aware holding returns, portfolios, extreme-mover proxy, half-spread and fee costs, Newey-West t, Student-t tail, Holm; raw-column lane loader. The file name shadows the standard-library `signal` module. Load it by path (`expected_dates.load_sibling`), and never put this directory on `sys.path`. |
| `evaluate.py` | Frozen-protocol evaluation. It refuses (exit 2) before opening any data unless the status is `frozen_pre_outcome`, `frozen_before_outcomes` is true, `frozen_at` is set and `--protocol-sha256` matches. |
| `receipts/*.json` | Small committed receipts: counts and sha256 only. |

## Commands

The private data root is `~/.local/state/native-agent-stack/research/sota-mover/eap/`
and is not in git. Use the tool Python that has DuckDB; tests use the system `python3`.

```bash
PY=~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python
DAILY=~/codex-ecosystem/state/broad-market-20260921/dataset/daily.parquet
$PY collect_edgar.py universe --daily "$DAILY"
ECOSYSTEM_JOB_MEMORY_HIGH=3G ECOSYSTEM_JOB_MEMORY_MAX=4G ECOSYSTEM_JOB_SECONDS=7200 \
  ~/codex-ecosystem/bin/ecosystem-bounded-run $PY collect_edgar.py fetch --rate 7.0
$PY collect_edgar.py extract
$PY collect_edgar.py tzcheck --sample 24
ECOSYSTEM_JOB_MEMORY_HIGH=3G ECOSYSTEM_JOB_MEMORY_MAX=4G ECOSYSTEM_JOB_SECONDS=1800 \
  ~/codex-ecosystem/bin/ecosystem-bounded-run $PY expected_dates.py accuracy \
  --root ~/.local/state/native-agent-stack/research/sota-mover/eap --daily "$DAILY"
# after an independent reviewer freezes protocol.json and commits it:
$PY evaluate.py --protocol-sha256 "$(sha256sum protocol.json | cut -d' ' -f1)" \
  --root ~/.local/state/native-agent-stack/research/sota-mover/eap --daily "$DAILY"
```

From the repository root, the tests (SYN) are:

```bash
python3 -m unittest tests.test_sota_eap_expected_dates tests.test_sota_eap_signal \
  tests.test_sota_eap_evaluate tests.test_sota_eap_collect -v
```

## Evidence labels

- **SYN:** unit tests on synthetic fixtures. They exercise every code path, including the planted-premium, null and cost-eaten cases.
- **HIST:** real SEC metadata, identity coverage, the acceptance-clock check, date-prediction accuracy and lane-membership counts from raw close and volume before each decision session. See `receipts/`.

Nothing here is upstream acceptance or a paper or live result.

## Pre-freeze results (HIST, no outcomes), 2026-09-25

**Identity**

- The current SEC map has 8,004 CIKs (10,413 ticker rows).
- 6,127 CIKs (7,276 symbols) match daily-dataset symbols.
- 10,721 daily symbols have no current CIK. These are delisted or renamed issuers, funds and derivatives, and they are not guessed.

**Collection**

- 7,369 submissions and continuation files were collected, with 0 not found and 7,363 requests in the full run.
- Every SEC response was HTTP 200, at a mean of 6.96 req/s under a 7.0 cap.
- The filing set holds 642,028 rows, including 142,944 8-K Item 2.02 filings dated 2015-01-05..2026-09-24 from 3,973 CIKs.
- The manifest sha256 is `bb4688f5...`; full values are in `receipts/collection-summary.json`.

**Acceptance clock**

- The JSON `acceptanceDateTime` is UTC. Converted to America/New_York, it equals the SGML header in 24 of 24 samples.
- The first hypothesis, that the digits were already Eastern time, matched 0 of 24. It is preserved in the receipt and was rejected before any accuracy computation.

**Date-prediction accuracy (monthly rule, main lane, 2017-01..2026-08)**

- Of 61,243 expected firm-months, 89.8% announced in the expected month.
- 89.5% of actual announcements by eligible firms fell in the expected month.
- By calendar year, precision ranges from 87.4% to 92.0%.
- For comparison, Frazzini-Lamont report 93% for firms with 4 announcements, using Compustat. Barber et al. report 61-82% for global annual announcements.

**Event-time rule**

- 60,537 matched announcements have a median error of 0 days.
- 70.6% fall within 3 days and 93.1% within 7 days.

## Known limitations

These are recorded in `protocol.json#/deviations`:

- Current-ticker identity drops delisted issuers (survivorship).
- There are no delisting returns.
- Weights are dollar-volume weights, not market capitalisation.
- Item 2.02 filings are noisier than earnings dates.
- The cost table is conservative and comes from mover entries.
- 116 months give an MDE of about 0.56-0.69%/month, which is at or above the published 61 bp.
- The Heitz-Narayanamoorthy-Zekhnini abstract was not retrieved here.
