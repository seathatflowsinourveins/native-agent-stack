# Stocks-in-Play 5-minute ORB replication (preregistered, phase 1)

An exact replication of Zarattini, Barbon and Aziz (2024), *A Profitable Day Trading Strategy For The U.S.
Equity Market* (SSRN 4729284, version of 16 Feb 2024): the 5-minute opening-range breakout on the 20 names
with the highest opening relative volume, a stop 10% of the 14-day ATR away and an exit at the close. The
paper reports Sharpe 2.81 (2016-2023) with commission as its only cost. We expect it to fail after measured
spreads. The post-publication segment (2024-01-02..2026-08-14) decides.

**Status:** `protocol.json` is `draft_pending_independent_pre_outcome_review` with `frozen_before_outcomes: false`.
No outcome has been computed. `simulate.py`, `quote_check.py` and `evaluate.py` refuse to run unless all of these
hold:

- `evidence/freeze-record.json` records the protocol sha256 passed as `--protocol-sha256`;
- `protocol.json` is frozen and hashes to that value;
- the study directory's git tree is clean (HEAD is recorded);
- every pinned private artifact and external input matches its sha256;
- the trades file matches its counts file, which records the same protocol sha256.

Evidence labels: **HIST** for historical simulation on Alpaca SIP data, **SYN** for the synthetic tests.
Nothing here describes paper or live behaviour.

## Protocol in brief

- **Items (fixed sequence ORB-1 -> ORB-2 -> ORB-3, each one-sided at alpha 0.05, stopping at the first
  non-rejection; post-publication, F1):**
  - ORB-1: combined mean net R > 0 (primary);
  - ORB-2: long-only mean net R > 0 (does not depend on borrow);
  - ORB-3: mean daily return > 0 for the portfolio at the paper's sizing.
- **Verdicts:**
  - "Supported on the 500 most liquid names" needs three things: a rejection, an F2 point estimate above 0,
    and F1's mean net R above 0 after the post-freeze quote check (`quote_check.py`).
  - A non-rejection reads "effect >= 0.08R excluded" only when the one-sided 95% upper bound is below 0.08R.
    Otherwise it reads "inconclusive at 0.08R".
  - Fewer post-publication trades than `n_min_trades` (5,054) makes every verdict inconclusive.
- **Descriptive (no gate):**
  - reproduction for 2017-2021 and 2022-2023 under F0, F1 and F2 (Table 2 analogues);
  - the Fig. 4 and Table 1 analogues on every filter 1-3 name;
  - break-even cost against measured cost;
  - a Rule 201 sensitivity for the short leg;
  - a week-block bootstrap of ORB-1;
  - same-bar counts and the F0fav variant.
- **Fill models:**
  - F0 is paper-exact: fills at the trigger and $0.0035 per share.
  - F1 is primary but not claimed conservative. It uses the measured half-spread by cell, gap-through fills
    at the bar open, SEC fee and FINRA TAF on sales, zero commission, and resolves a same-bar entry and stop
    against the trade.
  - F2 is F1 plus 2 bps per side.
  - F0fav is descriptive: F0 with same-bar bars resolved in the trade's favour.
- **Deviations D1-D13 and clarifications C1-C6** are listed in `protocol.json`. The main ones:
  - D1: the top 20 are ranked within a point-in-time top-500 liquidity membership (from sessions before t)
    intersected with the minute corpus; 3.2% of member days are outside the corpus and dropped.
  - D2: the reproduction runs from 2017-01-24.
  - D4: the conservative sizing reading, where each of 20 slots gets equity/20, risks 1% of that
    allocation and is capped at 4x it.
  - D8: split windows, cross-checked against Alpaca split records (145 of 151 confirmed).
  - D13: triggers count from the start of the 09:35 bar.

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
$BR $PY orb_prepare.py membership        # point-in-time top-500 liquidity membership per session (D1)
$BR $PY orb_prepare.py candidates        # 14-day ATR, volume and RelVol from sessions before t; filters 1-3
$PY orb_prepare.py select                # top 20 per session, direction, dojis, thin sessions
$BR $PY orb_prepare.py triggers          # first trigger minute of each order (bar highs/lows only)
$PY orb_prepare.py verify-or --n 300     # SQL range vs orb_signal.opening_range on a sha-keyed sample
$PY collect_quotes.py sample             # 1-in-10 (2017-2023) / 1-in-5 (2024-2026) fired orders, 4 stamps each
$BR $PY collect_quotes.py fetch --env-file ~/.config/codex-ecosystem/secrets/alpaca-paper-2.env --per-minute 1500
$PY collect_quotes.py table              # half-spread cells per segment group -> private cost-table.json
$PY evaluate.py power                    # MDE and minimum sample from signal counts
$PY split_check.py fetch --env-file ENV  # provider split records (GET /v1/corporate-actions)
$PY split_check.py compare               # D8 cross-check
$PY orb_prepare.py receipt               # counts and sha256 of the private artifacts
# post-freeze only; SHA is the value in evidence/freeze-record.json, all changes committed
$BR $PY simulate.py run --protocol-sha256 $SHA
$BR $PY simulate.py run --protocol-sha256 $SHA --population base
$PY quote_check.py sample --protocol-sha256 $SHA
$PY quote_check.py fetch --protocol-sha256 $SHA --env-file ENV
$PY quote_check.py apply --protocol-sha256 $SHA
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
| `orb_signal.py` | pure rule functions (stdlib only); not named `signal.py`, which would shadow the stdlib module |
| `orb_common.py` | paths, calendar, the freeze guard (`require_frozen`, `require_clean_tree`, `verify_pins`, `check_trades`) |
| `orb_prepare.py` | pre-outcome data work: opening ranges, membership, 14-day features, selection, trigger minutes, receipt |
| `split_check.py` | pre-outcome D8 cross-check against provider split records |
| `quote_check.py` | post-freeze quotes at sampled stop exits and gap-through fills (guarded) |
| `collect_quotes.py` | cost sample, SIP quote fetch, half-spread table |
| `simulate.py` | post-freeze trade outcomes under F0/F1/F2/F0fav (guarded) |
| `evaluate.py` | `power` (pre-freeze, counts only) and `run` (post-freeze items, fixed sequence, verdicts, descriptives; guarded) |
| `evidence/pre-outcome-receipt.json` | counts and sha256 of the private pre-outcome artifacts (no outcome) |

All data and per-trade results stay private. The repository holds only code, the protocol, tests and the
counts receipt.

## Hook for a live-shadow stage

If a verdict is supported, a separate prospective protocol would run the same `orb_signal.py` and
`orb_prepare.py` logic on live SIP data at 09:35 ET. It would record the would-be orders, trigger times and
quotes without placing orders, then compare realised fills with F1 before any paper order. This study
authorises no paper or live orders.
