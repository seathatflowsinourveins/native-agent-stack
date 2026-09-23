# Workers comparison: artifact-acceptance adjudicator prompt (pinned 2026-09-23)

You receive the same stripped packet and two judges' JSON outputs. For each
(arm, submission) where the judges disagree, decide `artifact_accepted` from the
packet's frozen outputs and preregistered clauses only; where they agree, copy the
agreed value. Leak rule and output schema are identical to the judge prompt, plus
`"adjudicated": true|false` per row. Do not re-score rows the judges agree on.
