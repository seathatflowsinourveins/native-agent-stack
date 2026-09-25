# ORB-SIP result (frozen run, 2026-09-25)

Protocol `sota-orb-stocks-in-play-v1-20260925`, sha256 `0a943b48…`, freeze commit `201dbbe2` (pushed before any
outcome). Runs from that tree, in this order: `simulate.py run` (39,691 selected trades per fill model, 850,177 in
the base population), `quote_check.py sample/fetch/apply` (1,015 stamps, all quoted), `evaluate.py run`. Evidence
class HIST. Numbers are in `results-summary.json`; per-trade data stays private (hash recorded there).

## Preregistered verdicts (post-publication segment 2024-01-02..2026-08-14, F1, fixed sequence)

| Item | n | Mean | 95% CI | Verdict |
|---|---|---|---|---|
| ORB-1 combined net R | 10,771 | -0.760R | -0.808 to -0.709 | not supported; an effect of 0.08R or more is excluded on the 500 most liquid names |
| ORB-2 long-only net R | 5,421 | -0.730R | -0.802 to -0.655 | not supported (not tested in sequence; reported) |
| ORB-3 portfolio daily return | 657 sessions | -0.51% | -0.54% to -0.47% | not supported (not tested in sequence; reported) |

The sample gate was met (10,771 against n_min 5,054). The quote check left the verdict unchanged (quote-adjusted
ORB-1 -0.765R). Break-even round-trip cost is negative (-6.1 bps against 12.1 bps measured), so the strategy loses
before costs.

## Reproduction of the paper (descriptive)

With the paper's own cost model (F0, commission only), 2017-2023: portfolio Sharpe -0.62, total return -27%, trade
win rate 16.8%. The paper reports Sharpe 2.81.

## Robustness: the 1-minute bar cannot order entry and stop

A 10%-of-ATR stop sits inside a single 1-minute bar's range often:
- 4,544 of 10,771 post-publication trades have the entry and the stop in the same bar under F0;
- 6,214 do under F1.

The preregistered rule (D6) resolves that bar against the trade. Resolving it in the trade's favour (F0fav,
descriptive) gives +0.219R (95% CI 0.141 to 0.298) before any spread. The measured 12 bps round trip is about the
same size, so no ordering assumption produces a tradable edge on these names.

The paper's result is consistent with this ordering artifact. Settling the ordering would need SIP trade ticks for
the same-bar cases. That would be a new, separately preregistered protocol, not a change to this one.
