# news-forward: live news-LLM paper runner

Evidence labels:

- **pilot**: days before `config.json` `rth_reversal.from`. These were the execution shakedown
  of the news-LLM headline-direction rules from `../news-llm/`.
- **Frozen study.** That study has since run once, from `baf158eb`, and no gate passed. From
  `rth_reversal.from` (2026-09-28 at the earliest) the RTH window runs the **preregistered
  `rth_reversal` arm**; see `../news-reversal/forward-protocol.json`.
- **Counted sessions.** Which of those sessions count is decided only by
  `../news-reversal/analyze.py`, from the freeze and deployment records.
- **execution_test.** The overnight OPG/CLS core arm's study (NEWS-1) failed; its fills are
  never evidence.

Earnings-premium and opening-range strategies are not wired (both failed their frozen historical
tests).

## Shared code path (the frozen study's rules, by path)

`news_signal.py` and `score.py` are imported by path from `../news-llm/` (the frozen study code
merged at `014a67b0`). Nothing there is copied or edited. The runner calls them for:

- **Windows and guards:** windows, guard A, novelty, lanes and checkpoint mapping.
- **Guard B:** `ingestion_guard` against the decision cutoff, with our own `received_at` as the
  ingestion time. The study's id-based `estimated_ingestion` is journaled beside it. The
  superseded id-order guard is gone.
- **D5:** the narrowed D5 regex (`MOVEMENT_RE`).
- **Labels:** the operative D22 label, `operative_score` on the raw output. The stored strict
  label is journaled as `strict_label` and never trades.
- **Rule 201:** `ssr_carryover` on split-adjusted bars, and `ssr_flag` with the decision quote.
  Missing data fails closed; the live runner also checks today's session low.
- **First headline per window:** `first_per_window` (F13).
- **Closing price:** `select_auction_price` for the official closing auction mark.

`score.py` provides the pinned checkpoint, sha256 checks, `weights_only=True`, the reviewed model
code, float32, the cached decoder and the operative `hlmw_alpaca`
FAVORABLE/UNFAVORABLE/UNCLEAR prompt.

One live-only difference: on CPU, `live_score.MmapCpuScorer` loads the same
verified weights with `load_state_dict(assign=True)` so they stay file-backed.
The copy-based CPU load was killed by earlyoom at 7.5 GB RSS on 2026-09-25.
Measured on 2026-09-25: its labels and raw outputs matched the study's GPU
float32 probe (`probe/fp32-hlmw_alpaca/scores-20241231.jsonl`) on 50 of 50
events. The GPU path uses `score.Scorer` unchanged.

## Files

| File | Purpose |
|---|---|
| `common.py` | Paths, loading modules by path, calendar, append-only fsynced JSONL journal |
| `planner.py` | Pure rules: session labels, daily schedule, screener, lanes, σ, section-A sizing, Rule 201, basket, per-arm caps, ids, ledgers, envelopes, exits, reconciliation |
| `autolev.py` | Pure evidence-gated auto-leverage, composed with adaptive-paper `leverage.py` |
| `live_news.py` | Read-only data client (GET allow-list, ≤300 req/min), 15 s news poller with `received_at` |
| `live_score.py` | Scorer process (vLLM runtime); queue → `scores.jsonl`; runs in its own `news-forward-scorer` unit (MemoryMax=9G) |
| `executor.py` | Paper-3 account binding and refusals, order-contract gate, alpaca-py submission; `check-account` CLI |
| `shadow.py` | Extended-hours and small-lane quote snapshots (release, +15, +60 min) |
| `supervisor.py` | Session timeline, GPU schedule, basket, RTH entries, close-out, kill switch, reconciliation, daily receipt |
| `config.json` | `"mode": "dry-run"` or `"paper"`; `rth_reversal.from` switches the RTH window to the preregistered arm |
| `systemd/` | `news-forward.service` and `news-forward.timer` (weekdays 03:55 ET; exits 20:05 ET) |

## Session mapping (New York time)

| Headline release | Label | Action |
|---|---|---|
| previous close – 09:00 | `open_auction` | liquid lane: basket at 09:15, OPG market by 09:27, CLS exit from 15:40 (retried to 15:49) |
| 09:00 – 09:30 | `excluded_0900_0930` | none, as in the study |
| 09:30 – 15:25 | `rth` (pilot days) | liquid lane: momentum marketable limit at release+15 (ask×1.002 / bid×0.998, skip >50 bps) until 15:40, CLS exit; later entry times are skipped |
| 09:30 – 15:30 | `rth` (from `rth_reversal.from`) | liquid lane, first headline per symbol: `rth_reversal` (arm `rev`, `nf1r-`) against the operative label on the first quote stamped in [+15, +16] min, limit at its ask/bid, skip >50 bps, cancel after 60 s, entries until 15:46, CLS exit; the momentum decision on the same quote is journaled as `core_shadow` only |
| 15:30 – 16:00 | `excluded_last_30min` | none |
| 04:00–09:30, 16:00–20:00 | `ext_pre` / `ext_post` | shadow quotes only (also the small-cap lane in every session) |

## Sizing and limits (coordinator amendment, 2026-09-25 01:46 ET)

The flat $2,000 per name and $40,000 gross from the original brief were
replaced as follows.

- **Per-name size (section A).** `min(0.0015·E/σ_i, 0.5%·MDV20_i, 5%·E)`.
  E is start-of-day equity, persisted per date so restarts keep it. σ_i is the
  sample stdev of 20 daily close-to-close returns before the decision. MDV20_i
  is the median dollar volume over those 20 sessions. Whole shares only; a name
  under 1 share or $1,000 is skipped. At most 12 names per leg per window.
- **Core gross cap = L·E.** L comes from `autolev.py`:
  - n·x̄/(n+60) shrinkage;
  - EWMA σ with a 20-session half-life;
  - quarter Kelly;
  - evidence gate: n ≥ 20, round trips ≥ 100, one-sided 95% lower bound > 0;
  - otherwise L = 1.0; pilot rows never count.

  L is then capped by adaptive-paper `leverage.py`: canonical v1 block, session
  schedule, Reg T overnight cap, drawdown ladder, kill switch and account
  multiplier. The strategy has no regime model, so `envelope()` is used, the
  regime-independent bound. The `unavailable` regime would map every session
  to 0. Each day's decision and its inputs are journaled as
  `leverage_decision`.
- **Other caps.** Per order: 5%·E. Account gross (all arms): the leverage.py
  RTH ceiling × E. One symbol per arm per day.
- **Net-exposure cap** (coordinator review, 2026-09-25). Per arm and per
  window, |long notional − short notional| ≤ 0.10·E.
  - The OPG basket (`planner.apply_net_cap`) scales the larger leg down pro
    rata. It keeps whole shares and drops a name that falls under 1 share or
    $1,000. Notional already committed in the window counts but is never
    rescaled.
  - Sequential entries (core RTH, pm, ah) are shrunk to the window's
    remaining headroom, or skipped with `net_exposure_cap`.
  - A leg with fewer than 2 names may trade alone, but only inside this cap.
    This replaces the study's 2-name leg minimum for execution. The `rth_reversal`
    estimand keeps it: a day has a long-short value only when both legs have at least 2
    filled names (`news_signal.daily_portfolios` in `../news-reversal/analyze.py`).
  - Pre-cap and post-cap notionals are journaled: a `net_cap` record for the
    basket, and `pre_cap_notional`, `est_notional` and `net_before`/`net_after`
    on each decision.
- **OPG sizing (review M3).**
  - The basket requires a two-sided pre-market quote with a spread of at most
    100 bps, and a mid within ±15% of the prior close. The mid is the reference
    price.
  - Every cap is planned at 95%: per-name size, arm and account gross, and the
    net cap.
  - Before every entry, `executor.RiskGate` re-checks the per-order and
    per-name notional, one symbol per arm and day, names per leg, arm gross,
    account gross and the window's net cap, at 100% of each.
  - Basket orders are submitted in a leg order that pulls the running net
    toward zero.
- **Fill-based exposure (M4).** Every 30 s, exposure is rebuilt from the
  broker's full order history, paginated since `ledger_epoch`:
  - filled quantity at its entry price;
  - working entries at their limit or recorded reference price;
  - rejected, cancelled or expired remainders are released.

  The result is synced into the gate and journaled as `net_actual`. After the
  open, a window whose filled net exceeds its cap is trimmed pro rata back to
  95% of the cap with marketable limits (`net_trim`, stage `trim<n>`). A
  rejected leg at submission is limited by the gate itself.
- **Kill switch at 2% of E (B1).** The kill is persisted per date in
  `runstate/<date>-<mode>.json`, so a restart stays killed. Every kill cycle
  (20 s in RTH, 45 s outside):
  1. cancels our orders and waits for their final states;
  2. re-flattens with a new round id (`kill<n>`): market orders in RTH,
     extended-hours limits otherwise, priced from the quote with a
     last-trade fallback;
  3. repeats until the broker shows none of our positions.

  Entries are refused while killed; exits never are, and every exit path
  keeps running. `<state>/STOP` refuses every order.
- **Exits.** Every exit comes from per-holding state built from our own fills,
  whatever the entry date (M5). It is capped at the broker's position after
  working exits (no oversell), and working orders are cancelled and final
  before the book is re-read (m3).
  - Carry-over holdings from earlier dates exit in the opening auction
    (`xopg<n>`). From 09:31, marketable limits replace any that did not fill
    (`cof<n>`, every 60 s).
  - RTH entries stop at 15:40 (M2). CLS exits (`cls<n>`) are re-planned
    every 30 s until 15:49 until every holding is covered (M1).
  - From 15:55, a day market order (`mkt<n>`) goes to any holding still
    uncovered.
  - After 16:02, extended-hours limits at bid−0.5% / ask+0.5% (`ext<n>`,
    last-trade fallback) go out every 10 minutes until 20:00.

  Tonight's ah holds are excepted from these closes. Round counters persist
  across restarts. An order that already existed under its id is journaled as
  `order_idempotent_existing` (m2), not as a new submission.
- **Exit-only mode (M6).** If a paper start's account check fails while any of
  our positions is open, or the positions cannot be read, the run stays in
  paper mode for exits and the kill, and refuses entries. Without our
  positions it runs as dry-run, journaled.

## Arms

| Arm | Prefix | Entry | Exit | Gross cap |
|---|---|---|---|---|
| core (`execution_test`) | `nf1-` | OPG basket; RTH release+15 on pilot days only | CLS | L·E |
| rev (`preregistered_forward`) | `nf1r-` | from `rth_reversal.from`: RTH release+15 against the label (see the session table) | CLS | 1.0·E (autolev floor, capped by leverage.py) |
| pm (`exploratory`) | `nf1x-pm-` | 04:00–09:00 liquid headlines: extended-hours limit at release+15 (ask×1.003 / bid×0.997, skip >1% spread), 25% size; only the event that is also the core's first in its window | CLS | 0.25·E ∧ PRE ceiling |
| ah (`exploratory`) | `nf1x-ah-` | 16:00–19:30 headlines: same entry, 25% size, after the corporate-action guard | next session's OPG | 0.25·E ∧ POST overnight ceiling |

`config.json` `arms.<arm>.orders_from` gates each arm's orders; before that
date its intents are validated and journaled only. The core basket skips a
symbol whose ah position is exiting in the same auction. At 19:50 the ah arm
re-runs the corporate-action guard on its holdings and flattens any
`must_flatten` symbol. Reconciliation expects exactly the ah holdings to remain
overnight.

The ah arm holds one night at most (`planner.overnight_hold_allowed`). It
enters only when the next XNYS session is the next calendar day. On Fridays and
on days before an exchange holiday, every ah entry is skipped with
`ah_next_session_not_next_day`, before any quote or corporate-action lookup. No
position is held across a weekend or holiday; on Friday 2026-09-25 the ah arm
enters nothing.

## Limitations

- **L-OC (order-contract bypass for auction orders).** Accepted for the pilot;
  `order_contract.py` is not edited.
  - `order-contract/order_contract.py` v1 admits only `time_in_force: day`.
  - `planner.contract_envelope` validates every OPG/CLS order with
    `build_envelope` using `day`, then admits `opg`/`cls` only for plain market
    orders without extended hours and without a limit price.
  - Each such envelope carries a `local_extension` field naming the
    substitution.
  - The contract's own checks therefore never see the auction TIF.
  - Closing it requires adding `opg`/`cls` to `order_contract.py` and its
    tests, outside this directory.

## GPU schedule

The scorer loads onto the GPU only when free VRAM is at least 9 GB. Before
08:30 it also requires `<state>/gpu-early-ok` (touch it once the batch scorer and
any delta pass have finished) and no active `sota-news-*` user unit. Before
08:30 it exits after 120 s idle, which releases the GPU. From 09:00, if the GPU
is not allowed, the CPU scorer runs.

## State (`~/.local/state/native-agent-stack/research/sota-mover/news-forward/`)

- `journal/<date>.jsonl`, with these record kinds:
  - news, eligibility, candidate, score and decision (arms core, pm, ah, rev and
    `core_shadow`), decision_wait;
  - order_intent, order_submitted, order_idempotent_existing, order_refused
    and order_cancel;
  - fill, shadow_quote, close_mark, net_cap, net_actual, net_trim and risk;
  - leverage_decision, reconciliation, rev_daily, autolev_daily_row and lifecycle.

  Every row carries the run's `evidence_label`: `pilot`, or `reversal_forward` from
  `rth_reversal.from`.
- `HALT-rth_reversal`, written by `../news-reversal/analyze.py monitor --apply` on a harm stop.
  It refuses new `rth_reversal` entries; exits, the kill switch and other arms are unaffected.
- Persisted per date and mode: `runstate/<date>-<mode>.json` (kill and
  round counters), `sod/<date>-<mode>.json` (E) and
  `ref-prices/<date>-<mode>.json` (entry reference prices).
- `score-queue.jsonl` and `scores.jsonl`.
- `status.json`: running `git_head`, `git_dirty` and per-file `code_sha256`.
- `scorer-status.json`.
- `receipts/<date>-summary.json`, with a `.sha256` sidecar.

The unit stops restarting after 5 failed starts within 10 minutes
(`StartLimitIntervalSec=600`, `StartLimitBurst=5`).

## Switching from dry-run to paper

1. The user creates a new Alpaca paper account and stores its keys in
   `~/.config/codex-ecosystem/secrets/alpaca-paper-3.env` (mode 0600, names
   `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`).
2. Read-only check (no order, cancel or position write):
   `~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python executor.py check-account`
   It must print `"verdict": "ready_for_paper"`. It refuses a missing file, a
   guard failure, the paper-2 key, a non-paper host, or foreign orders or
   positions.
3. Set `"mode": "paper"` in `config.json`, then run
   `systemctl --user restart news-forward.service`. The journal must show:
   - a `start` record with `"mode": "paper"` and
     `"account_verdict": "ready_for_paper"`;
   - a `paper_mode_enabled` record with the flag, the time and the
     `first_order_not_before` value.

   If any check fails, the run continues as dry-run and journals the refusal.
   No paper order is sent before `config.json` `first_order_not_before`.
