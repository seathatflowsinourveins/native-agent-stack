# Freeze: mover paper trial `mover-mac-20260924a` (written before any broker I/O)

Frozen 2026-09-24 12:43 ET by the Mac trading-lane coordinator session (single writer for this Mac's
Alpaca paper account; no other process or host trades it). Authority: `docs/paper-lane-policy.md`.

## What runs

- Engine: `blueprints/us-equities/adaptive-paper/mover_runner.py paper`, from a read-only `git archive` of
  main `3699012eb6ad` (`frozen-3699012.SHA256SUMS`, 562 files, sha256 `08587b84…`; `mover-v3/` excluded).
- Runtime: CPython 3.12.14 (uv), lock `evidence/artifacts/macos-syn-e2e-20260924/requirements-macos-arm64-py312.lock`
  (sha256 `d756583b…`): nautilus-trader 2.0.0rc5, alpaca-py 0.44.0, numpy 2.5.3; 20/20 packages, `uv pip check` ok.
- Account/endpoint: this Mac's Alpaca **paper** account, `https://paper-api.alpaca.markets`, SIP feed, state root
  `~/.local/state/native-agent-stack/alpaca-paper/`, kill switch
  `~/.local/state/native-agent-stack/alpaca-paper/STOP`.
- Config `config-mover-mac-20260924a.json` (sha256 `13688ae0ada8…`): `config-mover.json` with only
  `mover.rule`, `session_scope`, `trial_end_et`, `exit` and `notes` changed.

## Strategy (mechanics-only)

Protocol `mover-early-entry-v1-20260924`, `paper_e2e`. Nothing validated (0 of 768 rule-exits passed development;
v2 likewise), so the protocol's paper candidate is the most-traded development rule, `10:00|G0.20|V250000|any`
(`evidence/summary-dev-val-run-v1.json` `.paper_candidate`), labelled mechanics-only: it shows the pipeline works,
not an edge. The expected net return from the research is negative.

Deviations from the candidate (fixed now, before any outcome of this session is seen):

1. Late scan and entry: `mover_scan.py` evaluates the 10:00 rule at trial start (~12:50 ET); its snapshot prefilter
   uses the latest trade at that time, so names that faded below 1.18x the previous close are missed.
2. Entry at trial start instead of 10:00.
3. Exit X2 (60 minutes after the first fill) instead of the candidate's X1, because the engine bounds a hold at
   `duration_seconds + cleanup_seconds` (about 70 minutes).

## Numeric bounds (all from `config-mover.json`)

Capital 10,000 USD (ledger equity, never the account balance); at most 5 symbols; 200 USD per entry
(`max_entry_notional_usd`); ledger caps 2,000 USD per order / 100 shares / 2,000 USD gross; lifetime gross loss and
drawdown 1,000 USD; 1x; at most 20 outstanding orders; at most 200 trading requests and 180 submits per minute;
quotes at most 3 s old; entry spread at most 100 bps; marketable limits capped at 50 bps; entry window 30 s, entry
timeout 60 s; exit timeout 10 s, at most 20 exits per symbol; trial 3,600 s + 600 s cleanup; flatten reserve 120 s,
so the hard flatten is trial start + 68 min (before `trial_end_et` 15:30). Boundary disposition: flat, no open
orders; any residual goes to `mover_runner.py recover`.

## Acceptance (fixed before the run)

- Operational pass: receipt `status` `passed` or `completed_no_signals`, `flat` true, end reconciliation
  `cash_match` and `positions_match` true, 0 open orders, `pnl_consistent` true, no duplicate or unexplained broker
  effects, no ledger halt.
- Recorded, not thresholded: fills and slippage per leg, exit reasons, realized P&L, request/submit peaks per 60 s
  (the 200/min paper budget versus the 1,000/min Elite target), and, after the session, `paper_compare.py`
  differences from the historical fill model.
- Any other ending is recorded as `needs_attention` or failed with its reason, and recovery runs before the next trial.

## Known effects accepted

- `--allow-shared-account`: this state root holds the adaptive lane (Mac trials of #188). Fills here make that lane's
  next trial on this account refuse with `next_trial_cash_mismatch`. Its Mac acceptance is complete; the native-faults
  harness keeps its own state root. Separating the lanes needs a second paper account (user login).
- Mover v3 (#190): 2026-09-24 lies in the gap v3 never reads (2026-09-21 to N0-1); the exposure is disclosed on #190.
