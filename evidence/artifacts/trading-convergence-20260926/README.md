# Trading convergence 2026-09-26: retained evidence

Evidence for [`catalogs/us-equities/convergence-20260926.json`](../../../catalogs/us-equities/convergence-20260926.json).
Host paths are rewritten repository-relative; `<session-scratch>` replaces private session paths and
`<private-memory>` private memory paths. UUIDs, including those inside source URLs, are replaced by `<uuid>`
because `scripts/validate.py` treats any UUID as a possible session identifier; the record's quotes use the same
sanitized text.

- `gpt6-votes/<layer>--<lens>.md`: each GPT-6 cross-family refutation, copied unchanged apart from path
  sanitization. `gpt-6-live` ran with `-c web_search="live"`; `gpt-6-cached` ran with the client default (cached
  search index). Every vote quote in the record is checked verbatim against these texts.
- `packets/<layer>.json`: the per-layer input the mappers read: the Claude proposal (winner status, challengers,
  rejections), the Claude claim checks and the researched candidates.
- `papers-strategy.md`: the live GPT-6 academic-paper sweep for strategy-research (first line `PAPERS: 25 verified`).
  Its one direct protocol contradiction (the ABJK 2022 sample description) was re-verified by the coordinator against
  the manuscripts and is corrected in Mover v3 round 18.

These are model outputs: each is one refutation attempt, not a panel, and not upstream acceptance.
