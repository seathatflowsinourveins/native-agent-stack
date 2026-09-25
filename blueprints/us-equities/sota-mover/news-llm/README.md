# SOTA mover study: LLM headline direction without look-ahead (phase 1)

**Status: draft preregistration. Nothing is frozen and no outcome has been computed.**
[`protocol.json`](protocol.json) has status `draft_pending_independent_pre_outcome_review` and
`frozen_before_outcomes: false`. `evaluate.py` refuses to read any event, score or price until
`receipts/freeze-record.json` names a frozen protocol (status `frozen_pre_outcome`) committed in an ancestor of HEAD,
every code, reference and private-input pin matches, and the study directory is clean (template:
`receipts/freeze-record.template.json`).

## Question

Lopez-Lira & Tang (arXiv 2304.07619v6) show that GPT-4's reading of a firm's headline predicts that firm's
next-session return (gross long-short 0.34%/day, Sharpe 2.97, Oct 2021-May 2024). The effect decays (Sharpe 6.54 to
1.22) and breaks even near 20 bps per round trip. Critics show that prompting cannot remove a model's knowledge of
later prices. This study tests the paper's trading design with the **chronologically consistent** ChronoGPT-Instruct
1.55B classifier (`manelalab/chrono-gpt-instruct-v1-<Y-1>1231` for a headline in year Y) and the model authors'
prompt. Their own estimate for that prompt is about 3 bps/day gross, below the ~9 bps/day of modelled long-short
costs, so **NEWS-1 is expected to fail**; its value is the upper bound and the break-even cost. Every verdict applies
to firms present in the 2026-09-21 asset master (survivorship, limitation L11).

| Item | Window | Lane | Series | Segment | Family |
|---|---|---|---|---|---|
| NEWS-1 | overnight (open to close) | liquid | long-short, both legs | 2016-02-02..2026-09-18 | fixed sequence 1st; Holm |
| NEWS-4 | overnight | liquid | long-short, both legs | last 24 months | fixed sequence 2nd |
| NEWS-2B | overnight | liquid | long leg minus all scored liquid events | 2016-02-02..2026-09-18 | Holm (m=3), LONG-ONLY member |
| NEWS-2 | overnight | liquid | long leg (absolute) | same | Holm (m=3), LONG-ONLY member |
| NEWS-3 | intraday, release + 15 min (quote) to close | liquid | long-short, both legs | 2016-02-02..2026-09-18 | Holm (m=3) |

The secondary Holm family has three members: NEWS-1, LONG-ONLY (NEWS-2B and NEWS-2 as one intersection-union test,
p = the larger of the two) and NEWS-3. Each family bounds its false rejections at 0.05, so the chance of any false gate
is at most 0.10. Gates, all computed in `evaluate.evaluate_items`: long-only paper candidate = LONG-ONLY and a positive
recent long leg; long-short candidate = NEWS-1 and NEWS-4; intraday candidate = NEWS-3. Non-rejected items report the
one-sided 95% upper bound of the mean net and gross return against 3 and 34 bps/day. Shorts under the SEC Rule 201
restriction (from pre-decision data) are excluded from confirmatory items.

Positions use the operative prefix rule (D22): an answer starting "UNF" is UNFAVORABLE (-1), "FAV" FAVORABLE (+1),
"UNC" UNCLEAR (0). The model often writes "UNFLEXIBLE"/"UNFRIENDLY" for UNFAVORABLE (26-31% of 2023-2024 outputs).
The rule was chosen from output text only; the authors' exact-word rule is reported beside every item.

## Files

| File | Purpose |
|---|---|
| `protocol.json` | The preregistration: paper facts, model pins, prompt, filters, windows, prices, costs, portfolios, items, gates, MDE, deviations, limitations, freeze procedure. |
| `checkpoints.json` | Hugging Face revision and sha256 of every checkpoint file, the reviewed `ChronoGPT_instruct.py` sha256, tokenizer file hashes, and the load policy. |
| `news_signal.py` | Every preregistered rule as a pure function (standard library only): timing windows, timestamp and ingestion guards, novelty, instrument filter, prompt variants, label parsing, lanes, auction and entry-quote prices, Rule 201 flags, fees, net returns, portfolios, Newey-West, fixed sequence, Holm. Named to avoid shadowing the standard-library `signal`. |
| `prepare.py` | Builds the event list from the news archive, calendar, asset master and prior-session daily bars; writes counts only. |
| `score.py` | `fetch` downloads the pinned checkpoints with sha256 checks; `run` scores events resumably and stores provenance for every label. |
| `collect_auctions.py` | Official auction prints and entry-time SIP quotes from the Alpaca data API (read-only, rate-limited, guarded credentials). |
| `evaluate.py` | Post-freeze evaluation behind the EAP-standard guard (freeze record, ancestor freeze commit, clean tree, sha pins, a guard token checked inside every loader); score-row checks, Rule 201 flags, families, upper bounds and gates. |
| `receipts.py` | Regenerates `receipts/` from the private root (counts and sha256 only; refuses to write the home path). |
| `receipts/` | Small committed receipts: prepare funnel, model downloads, collection coverage and HTTP tallies, scoring probes, scoring status. |

Tests: `tests/test_sota_news_llm_{signal,prepare,score,collect,evaluate}.py` (synthetic fixtures only; no GPU, model
files, network or private data).

## Commands

Private data root (never committed): `~/.local/state/native-agent-stack/research/sota-mover/news-llm/`. Checkpoints:
`~/.local/share/native-agent-stack/models/chronogpt-instruct/`.

```sh
# tests (system Python 3.12)
python3 -m unittest tests.test_sota_news_llm_signal tests.test_sota_news_llm_prepare \
  tests.test_sota_news_llm_score tests.test_sota_news_llm_collect tests.test_sota_news_llm_evaluate -v

# events (Python with duckdb)
ecosystem-bounded-run ~/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/bin/python prepare.py

# checkpoints and scores (read-only vLLM runtime: torch + tiktoken)
python3 score.py fetch
systemd-run --user --unit=sota-news-score-<ts> -p MemoryHigh=3G -p MemoryMax=4G -p RuntimeMaxSec=28800 \
  ~/.local/share/codex-ecosystem/tools/vllm-0.30.0/bin/python score.py run \
  --events <root>/events.jsonl.gz --out <root>/scores --decoder cached --batch-size 32 \
  --max-batch-tokens 3072 --check-batch1 16 --lanes liquid     # then --lanes small (resumable)

# prices (Alpaca data API, <= 2,000 requests/min before 03:30 ET, 500 after)
python3 collect_auctions.py auctions
python3 collect_auctions.py spreads

# after the freeze only
python3 evaluate.py --print-pins          # hashes to copy into protocol.json#/pins at the freeze
python3 evaluate.py                       # reads the sha only from receipts/freeze-record.json
```

## Scoring decisions made before the freeze (label counts only)

- **Prompt.** ChronoGPT-Instruct (1.55B) does not answer the Lopez-Lira & Tang prompt in its YES/NO format: in the
  upstream `extract_response` wrapper it echoed a "Headline: ..." line for 248 of 256 headlines. Three variants were
  compared on the same 500-event label-agnostic sample. The operative prompt is the model authors' own headline
  classification prompt (He, Lv, Manela & Wu, arXiv 2510.11677, section 3.3): FAVORABLE / UNFAVORABLE / UNCLEAR ->
  +1 / -1 / 0, in their Alpaca format. The float32 probe gave 474/500 directional labels, against 56/500 for the paper
  prompt in the same format and 29/500 in the upstream wrapper. The paper's prompt stays verbatim in the protocol.
- **Numerics.** In bfloat16 (the upstream casts) a prompt's logits moved by 0.6-0.9 with batch shape or padding, more
  than typical label margins, and batch-32 labels agreed with batch-1 labels on only 160/200. Scoring therefore runs
  in float32 (TF32 off), where batch 1, batch 32 and padded rows give identical logits.
- **Decoder.** A key/value-cached greedy decoder matched full recompute on 700/700 real prompts (second-step logit
  difference <= 8.6e-5) at about 3.4x the speed. Every checkpoint in the full run also rescored 16 events at batch 1.
- **Prior evidence.** The model authors report an H-L Sharpe of 0.95 (about 3 bps/day gross, next-day close-to-close,
  2007-2023) for this prompt. With about 9 bps/day of modelled long-short costs, a net pass needs a much larger
  same-session effect.

## Security of the model path

`pytorch_model.bin` and `config.pt` are pickles: they are loaded only with `torch.load(..., weights_only=True)`.
`ChronoGPT_instruct.py` was reviewed (no exec, eval, subprocess or network outside `from_pretrained`) and is imported
from the local file only when its sha256 matches the pin. `from_pretrained` and remote-code loaders are never used, and
the scoring process runs with `HF_HUB_OFFLINE=1` and a local tiktoken cache. Scoring runs in float32 through a
line-for-line override of the only two methods that cast to bfloat16 (see protocol D14 for the measurement behind it).

## Freeze discipline

Before the freeze, only counts, coverage, timestamps, spread measurements, model scores and label distributions are
computed on real data. The exact list is in `protocol.json#/pre_freeze_computations`. No return, P&L, hit rate or
post-decision price change has been computed.
