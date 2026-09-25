# news-forward: live news-LLM paper pilot

Evidence label: **pilot**. This is an execution shakedown of the news-LLM
headline-direction rules from `../news-llm/`, not forward-study evidence. The
counted forward study starts only after the historical protocol is frozen.
Earnings-premium and opening-range strategies are not wired (both failed their
frozen historical tests).

## Shared code path

`news_signal.py` (windows, timestamp/D5/novelty/id-order guards, lanes, labels,
checkpoint mapping) and `score.py` (pinned checkpoint, sha256 checks,
`weights_only=True`, reviewed model code, float32, cached decoder, operative
`hlmw_alpaca` FAVORABLE/UNFAVORABLE/UNCLEAR prompt) are imported by path from
`../news-llm/`. Nothing there is copied or edited.

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
| `config.json` | `"mode": "dry-run"` or `"paper"` |
| `systemd/` | `news-forward.service` and `news-forward.timer` (weekdays 03:55 ET; exits 20:05 ET) |

## Session mapping (New York time)

| Headline release | Label | Action |
|---|---|---|
| previous close – 09:00 | `open_auction` | liquid lane: basket at 09:15, OPG market by 09:27, CLS exit 15:40–15:45 |
| 09:00 – 09:30 | `excluded_0900_0930` | none, as in the study |
| 09:30 – 15:30 | `rth` | liquid lane: marketable limit at release+15 (ask×1.002 / bid×0.998, skip >50 bps), CLS exit |
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
- **Kill switch at 2% of E.** It cancels our orders, flattens every arm and
  stops. `<state>/STOP` refuses every order.
- **Exits** (core and pm):
  - CLS at 15:40–15:45;
  - a day market order at 15:55 for any holding without a live exit;
  - after 16:02, extended-hours limits at bid−0.5% / ask+0.5% every
    10 minutes until 20:00.

  Exits come from per-arm ledgers built from our own fills. An arm never
  closes another arm's shares.

## Arms

| Arm | Prefix | Entry | Exit | Gross cap |
|---|---|---|---|---|
| core (`confirmatory_pilot`) | `nf1-` | OPG basket / RTH release+15 | CLS | L·E |
| pm (`exploratory`) | `nf1x-pm-` | 04:00–09:00 liquid headlines: extended-hours limit at release+15 (ask×1.003 / bid×0.997, skip >1% spread), 25% size; only the event that is also the core's first in its window | CLS | 0.25·E ∧ PRE ceiling |
| ah (`exploratory`) | `nf1x-ah-` | 16:00–19:30 headlines: same entry, 25% size, after the corporate-action guard | next session's OPG | 0.25·E ∧ POST overnight ceiling |

`config.json` `arms.<arm>.orders_from` gates each arm's orders; before that
date its intents are validated and journaled only. The core basket skips a
symbol whose ah position is exiting in the same auction. At 19:50 the ah arm
re-runs the corporate-action guard on its holdings and flattens any
`must_flatten` symbol. Reconciliation expects exactly the ah holdings to remain
overnight.

## Order contract gap

`order-contract/order_contract.py` v1 admits only `time_in_force: day`.
`planner.contract_envelope` still validates OPG/CLS orders with
`build_envelope`: it passes `day` for the check, then admits `opg`/`cls` only
for plain market orders without extended hours. The envelope records this in a
`local_extension` field. Adding `opg`/`cls` to the contract itself is an
integration item outside this directory.

## GPU schedule

The scorer loads onto the GPU only when free VRAM is at least 9 GB. Before
08:30 it also requires `<state>/gpu-early-ok` (touch it once the batch scorer and
any delta pass have finished) and no active `sota-news-*` user unit. Before
08:30 it exits after 120 s idle, which releases the GPU. From 09:00, if the GPU
is not allowed, the CPU scorer runs.

## State (`~/.local/state/native-agent-stack/research/sota-mover/news-forward/`)

`journal/<date>.jsonl` (news, eligibility, candidate, score, decision,
order_intent/submitted/refused, fill, shadow_quote, risk, reconciliation,
lifecycle), `score-queue.jsonl`, `scores.jsonl`, `status.json`,
`scorer-status.json` and `receipts/<date>-summary.json` with a `.sha256`
sidecar.

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
