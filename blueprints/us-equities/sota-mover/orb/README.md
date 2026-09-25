# Stocks-in-Play 5-minute ORB replication (preregistered, phase 1)

An exact replication of Zarattini, Barbon and Aziz (2024), *A Profitable Day Trading Strategy For The U.S.
Equity Market* (SSRN 4729284, version of 16 Feb 2024): the 5-minute opening-range breakout on the 20 names
with the highest opening relative volume, a stop 10% of the 14-day ATR away and an exit at the close. The
paper reports Sharpe 2.81 (2016-2023) with commission as its only cost. We expect it to fail after measured
spreads. The post-publication segment (2024-01-02..2026-08-14) decides.

**Status:** `protocol.json` is `draft_pending_independent_pre_outcome_review` with `frozen_before_outcomes: false`.
No outcome has been computed. `simulate.py run` and `evaluate.py run` refuse to run until the protocol is
frozen and its sha256 is passed as `--protocol-sha256`.

Evidence labels: **HIST** for historical simulation on Alpaca SIP data, **SYN** for the synthetic tests.
Nothing here describes paper or live behaviour.

## Protocol in brief

- **Items (Holm, m = 3, family alpha 0.05, one-sided, post-publication, F1):**
  - ORB-1: combined mean net R > 0 (primary);
  - ORB-2: long-only mean net R > 0 (does not depend on borrow);
  - ORB-3: mean daily return > 0 for the portfolio at the paper's sizing.
- **Verdicts:** each item also needs its F2 (one-tick stress) point estimate above 0. Fewer post-publication
  trades than `n_min_trades` (7,207) makes the verdict inconclusive, not a fail.
- **Descriptive (no gate):**
  - reproduction for 2017-2021 and 2022-2023 under F0, F1 and F2 (Table 2 analogues);
  - the Fig. 4 and Table 1 analogues on every filter 1-3 name;
  - break-even cost against measured cost;
  - a Rule 201 sensitivity for the short leg.
- **Fill models:**
  - F0 is paper-exact: fills at the trigger and $0.0035 per share.
  - F1 is primary: measured half-spread, gap-through fills at the bar open, SEC fee and FINRA TAF on sales,
    zero commission, and a same-bar entry and stop resolved against the trade.
  - F2 is F1 plus one tick.
- **Deviations D1-D12 and clarifications C1-C6** are listed in `protocol.json`. The main ones:
  - D1: the top 20 are ranked within universe A, not all NYSE/Nasdaq stocks.
  - D2: the reproduction runs from 2017-01-24.
  - D4: the conservative sizing reading, where each of 20 slots gets equity/20, risks 1% of that
    allocation and is capped at 4x it.

## Reproduce

Paths are placeholders. The private data root is `~/.local/state/native-agent-stack/research/sota-mover/orb/`
(mode 0700). Run jobs that read more than 1 GB under `ecosystem-bounded-run` with
`ECOSYSTEM_JOB_MEMORY_HIGH=3G ECOSYSTEM_JOB_MEMORY_MAX=4G`. DuckDB runs at `memory_limit='2.5GB'`, `threads=4`,
with its temp directory under the private root.

```sh
PY=~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python   # Python 3.12.3, duckdb 1.5.5
BR="env ECOSYSTEM_JOB_MEMORY_HIGH=3G ECOSYSTEM_JOB_MEMORY_MAX=4G ECOSYSTEM_JOB_SECONDS=3600 ~/codex-ecosystem/bin/ecosystem-bounded-run"
cd blueprints/us-equities/sota-mover/orb
# pre-outcome (allowed before the freeze)
$BR $PY orb_prepare.py or-table          # 09:30-09:34 range per symbol-day from the stage-1 minute corpus
$BR $PY orb_prepare.py candidates        # 14-day ATR, volume and RelVol from sessions before t; filters 1-3
$PY orb_prepare.py select                # top 20 per session, direction, dojis, thin sessions
$BR $PY orb_prepare.py triggers          # first trigger minute of each order (bar highs/lows only)
$PY orb_prepare.py verify-or --n 300     # SQL range vs signal.opening_range on a sha-keyed sample
$PY collect_quotes.py sample             # 1-in-10 (2017-2023) / 1-in-5 (2024-2026) fired orders, 4 stamps each
$BR $PY collect_quotes.py fetch --env-file ~/.config/codex-ecosystem/secrets/alpaca-paper-2.env --per-minute 1500
$PY collect_quotes.py table              # half-spread cells per segment group -> private cost-table.json
$PY evaluate.py power                    # MDE and minimum sample from signal counts
$PY orb_prepare.py receipt               # counts and sha256 of the private artifacts
# post-freeze only (refused until protocol.json is frozen and its sha256 matches)
SHA=$(sha256sum protocol.json | cut -c1-64)
$BR $PY simulate.py run --protocol-sha256 $SHA
$BR $PY simulate.py run --protocol-sha256 $SHA --population base
$PY evaluate.py run --protocol-sha256 $SHA
```

Tests (SYN):

```sh
python3 -m unittest tests.test_sota_orb_signal tests.test_sota_orb_guard tests.test_sota_orb_pipeline -v
$PY -m unittest tests.test_sota_orb_pipeline -v   # the end-to-end dry run needs duckdb; python3 skips it
```

The fetch calls only `GET https://data.alpaca.markets/v2/stocks/quotes` (`feed=sip`, `asof=2026-09-22`). It
loads the key pair inside its own process through `adaptive-paper/credential_guard.py` and never touches a
trading endpoint. It stays at or below 2,000 requests per minute, dropping to 500 per minute from 03:30 ET.
It keeps every page, gzipped and hashed in a resumable ledger.

## Files

| File | Role |
| --- | --- |
| `protocol.json` | preregistration: rules, deviations, items, gates, sample size, freeze discipline |
| `signal.py` | pure rule functions (stdlib only); loaded by path because the name shadows the stdlib `signal` |
| `orb_common.py` | paths, calendar, the freeze guard `require_frozen` |
| `orb_prepare.py` | pre-outcome data work: opening ranges, 14-day features, selection, trigger minutes, receipt |
| `collect_quotes.py` | cost sample, SIP quote fetch, half-spread table |
| `simulate.py` | post-freeze trade outcomes under F0/F1/F2 (guarded) |
| `evaluate.py` | `power` (pre-freeze, counts only) and `run` (post-freeze items, Holm, verdicts, descriptives; guarded) |
| `evidence/pre-outcome-receipt.json` | counts and sha256 of the private pre-outcome artifacts (no outcome) |

All data and per-trade results stay private. The repository holds only code, the protocol, tests and the
counts receipt.

## Hook for a live-shadow stage

If a verdict is supported, a separate prospective protocol would run the same `signal.py` and
`orb_prepare.py` logic on live SIP data at 09:35 ET. It would record the would-be orders, trigger times and
quotes without placing orders, then compare realised fills with F1 before any paper order. This study
authorises no paper or live orders.
