# Gap crosswalk: preregistration (written before any TypeSafe call)

Date: 2026-09-23. Model `jev-1.13.0`, question revision `gap-crosswalk-questions-v1` (crosswalk.py).

## Eval set (labels frozen before inference)

The 315 bdd04ca gaps of `catalogs/landscape/gap-resolution-20260922.json` at PR #81 head `ef2ae46`, after the Opus review,
the Codex review and the Codex follow-up. Gap-level label: settled -> settles, advanced -> partially, not_settled or
open -> not_addressed. Candidate receipts per gap: every gap receipt whose layer_ids or gap_refs name the gap's layer.
Only gaps with at least one candidate are scored for addressing. Known label noise: an open gap was never checked against
unreferenced receipts, so a true positive there is scored as a false positive.

Blocker labels: the ledger category, mapped documentation_fix/manifest_gap -> catalog_edit, needs_user_input ->
needs_user_decision; codex_limited and peer_owned are excluded (they described session state, not the gap).

## Decision rule for the current rows (92bb279)

- TypeSafe never sets a status on its own. A (gap, receipt) pair enters the Opus review queue when
  P(settles) + P(partially) >= T. T is the largest value in {0.05, 0.1, 0.2, 0.3, 0.5} whose eval recall of
  addressed gaps (settled or advanced) is at least 0.90; if none reaches 0.90, every candidate pair is reviewed.
- The reviewer (Opus/high, read-only) decides settles / partially / not_addressed per queued pair from the receipt and
  the gap text; its decision is what the crosswalk records.
- Blocker categories are advisory. If eval agreement is below 0.60, the crosswalk still publishes them but labels them
  "advisory, eval agreement X", and the executable list goes to the Opus reviewer too.

## Reported regardless of outcome

Confusion matrix, threshold table, blocker agreement and pairs, request count, errors, input/output tokens, latency.
