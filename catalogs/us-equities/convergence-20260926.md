# Trading research convergence — 2026-09-26

Machine-readable record: [`convergence-20260926.json`](convergence-20260926.json). Retained evidence (every GPT-6
vote text, the per-layer packets and the paper sweep): [`evidence/artifacts/trading-convergence-20260926/`](../../evidence/artifacts/trading-convergence-20260926/README.md).

**What this is.** 13 trading layers (the 12 catalog trading layers plus strategy-research) were researched from the
user's starred repositories (379 triaged), 8 awesome lists and per-layer candidate
research. Each layer's Claude proposal was then challenged by a cross-family GPT-6 refutation. Every layer has a
live-search vote, and 8 also have a cached-search vote. The candidate records use the trading candidate shape of
[`manifest-20260926.json`](../sota-convergence/manifest-20260926.json) (sha256 `a72177d162f8…`,
#357). The verdict wave reads both records.

**What it is not.** Nothing here installs, promotes or re-pins a component. A disposition is an input to the
verdict wave, not a selection. Each GPT-6 vote is one refutation attempt, not a panel.

**Rule.** survives=false when any kept vote has position refutes, meaning the vote says the label is wrong (for a rejection, that it should not have been rejected). A vote with position corrects fixes a fact or a claim but leaves the label standing and does not change survival. survives=true when at least one kept GPT-6 vote addresses it and none refutes; null (disposition *_unverified) when no kept GPT-6 vote addresses it. Dispositions follow manifest-20260923's vocabulary.

| Layer | GPT-6 live | GPT-6 cached | Winners disputed | Candidates (survive / refuted / unverified) | Missed candidates | Corrections |
|---|---|---|---|---|---|---|
| agents-models-workers | needs_changes | needs_changes | foundation-ai-memory, foundation-socraticode | 5 / 7 / 0 | 12 | 18 |
| backtesting-engine | needs_changes | needs_changes | none | 5 / 1 / 9 | 5 | 13 |
| data-quality-orchestration | needs_changes | — | none | 8 / 0 / 8 | 2 | 13 |
| evaluation-experiments | needs_changes | needs_changes | none | 8 / 4 / 0 | 6 | 27 |
| execution-broker | needs_changes | — | nautilus-ibkr-adapter | 5 / 1 / 8 | 2 | 8 |
| identity-provenance | needs_changes | — | none | 12 / 1 / 0 | 3 | 17 |
| market-data-reference | needs_changes | needs_changes | none | 9 / 3 / 0 | 4 | 32 |
| observability-hosting | needs_changes | needs_changes | none | 3 / 5 / 5 | 4 | 22 |
| portfolio-risk | needs_changes | — | none | 6 / 6 / 4 | 2 | 12 |
| research-factors-ml | needs_changes | needs_changes | none | 4 / 5 / 8 | 9 | 22 |
| security-supply-chain | needs_changes | needs_changes | none | 11 / 3 / 0 | 5 | 33 |
| storage-compute | needs_changes | — | none | 6 / 2 / 5 | 5 | 14 |
| strategy-research | needs_changes | needs_changes | none | 13 / 2 / 0 | 5 | 24 |

Totals: 95 candidates survive, 40 are refuted and 47 are unverified (no kept GPT-6 vote addressed them). Votes kept: 716; each quote is an exact span of the retained vote text (dropped: 0 not found, 0 split by sanitization).

## Corrections that touch the paper lane

- **execution-broker.** The claim that NautilusTrader #4983 blocks IBKR stock orders on 2.0.0rc5 is refuted at the
  source. The issue reports v1.227.0, and at `1b0a49d2` (tag `v2.0.0rc5`) the IB execution client overrides
  `handles_order_venue` to return `true` (`crates/adapters/interactive_brokers/src/execution/core.rs:493-495`). This
  agrees with #280's reclassification. It does not establish that rc5 accepts stock orders; none has been observed.
- **portfolio-risk.** The September 23 records already hold skfolio, cvxportfolio and Nautilus risk-limit
  executions. The claim of "zero native execution" is refuted. The skfolio 1.4.0 upgrade trial cannot run
  unchanged because `evaluate.py` pins 1.2.9, so it needs its own frozen experiment.
- **strategy-research.** A live GPT-6 paper sweep (25 verified papers) found that the Mover v3 protocol
  describes ABJK 2022's sample as "large, liquid names". The coordinator re-verified from the manuscripts that
  ABJK keeps common stocks above $1 and that LPS 2019 excludes microcaps. A text-only correction is proposed in Mover v3
  round 18 (#360, under review).
  The two-sided test is unchanged.

## Critic gaps

- **strategy-research and security-supply-chain reported as missing from the packet**: refuted: both layers have proposals and votes here; the critic read a truncated relay payload
- **cross-family pass not run for 5 layers**: resolved: all 13 layers have a live GPT-6 vote (see attempts)
- **identity-provenance concurrency benchmark exercised ArcticDB outside its staged-write API**: open: rerun the Arctic arm with stage() and finalize_staged_data() before treating DVC's concurrency edge as settled
- **OpenBao never compared with HashiCorp Vault**: open: record the comparison (BUSL-1.1 licence is the expected discriminator)
- **trace backend (Tempo) evidence filed under a foundation layer only**: open: foundation-lane item; no trading row changes
- **academic papers were not a deliberate discovery modality**: done for strategy-research: a live GPT-6 paper sweep returned 25 verified papers (evidence/artifacts/trading-convergence-20260926/papers-strategy.md). Its one direct protocol contradiction, the ABJK 2022 sample description, was re-verified against the manuscripts; a text-only correction is proposed in Mover v3 round 18 (PR #360, under review). research-factors-ml has no paper pass yet.
- **workflow relay truncated three proposal payloads**: limitation: truncated fields are marked in the proposals; the mapper read full packets from files

## Limitations

- Cached-mode GPT-6 votes (lens gpt-6-cached) may lag upstream; the live votes were run to cover that.
- Claude candidate research and claim checks ran with web search; GPT-6 votes are one refutation each per mode, not a panel.
- Candidate labels are proposals for the verdict wave; nothing here promotes, installs or changes a pin.
- Upstream facts (versions, dates, stars) are as observed on 2026-09-26 and are not re-fetched by the builder.

## Attempts

Five layers' first GPT-6 attempts failed with 401 after a shared sign-out. Their second attempts were stopped so they could rerun with live search; the third attempts completed. All are listed in `attempts`.
