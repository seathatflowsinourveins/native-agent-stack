# NEWS-PIT-LLM result (frozen run, 2026-09-25)

The protocol `sota-mover-news-llm-20260925` was frozen at commit `70bd2b84` with sha256 `bba1b157…`, and the branch
was pushed before any outcome was computed. The evaluation ran once, from HEAD `9504cd73`, on a clean tree, and
exited 0. Evidence class HIST.

Scores come from the point-in-time ChronoGPT-Instruct checkpoints under the operative prefix rule D22. Verdicts are
scoped to firms present in the 2026-09-21 asset master (L11). Numbers are in `evaluation-summary.json`; the private
results file is hashed there.

| Item | Days | Gross mean per day | Net mean per day | Net t (Newey-West) | Verdict |
|---|---|---|---|---|---|
| NEWS-1 overnight long-short, liquid, 2016-2026 | 2,658 | -0.03 bps (t -0.02) | -8.4 bps | -5.03 | not rejected |
| NEWS-2 overnight long leg | 2,663 | +2.4 bps (t 1.06) | -1.8 bps | -0.78 | not rejected |
| NEWS-2B long leg minus the news-day benchmark | 2,663 | +0.06 bps | +0.06 bps | 0.05 | not rejected |
| NEWS-3 regular-hours entry at +15 min to the close, long-short | 2,618 | -11.0 bps (t -7.16) | -19.4 bps | -12.62 | not rejected |
| NEWS-4 overnight long-short, last 24 months | 495 | -0.08 bps | -8.4 bps | -1.75 | not rejected |

- No gate passed:
  - long-only paper candidate false;
  - long-short candidate false;
  - regular-hours candidate false;
  - the recent long leg's net mean is -4.2 bps per day over 495 days.
- **NEWS-1 upper bounds:**
  - the gross one-sided 95% bound is +2.7 bps per day and the net bound -5.7;
  - both the model authors' 3 bps per day and the paper's 34 bps per day are excluded.
- **Headline direction:** ChronoGPT-Instruct's headline direction carries no open-to-close information for liquid
  names in 2016-2026.
- **NEWS-3:** entries 15 minutes after a regular-hours headline, in the model's direction, lose 11 bps per day
  before costs (t -7.2). That is a reversal after the initial reaction. It was seen in this run, not predicted, so it
  may only be tested as a new, separately preregistered hypothesis on data that has not been used, i.e. forward.
