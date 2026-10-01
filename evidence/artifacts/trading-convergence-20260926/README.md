# Trading convergence 2026-09-26: retained evidence

Evidence for [`catalogs/us-equities/convergence-20260926.json`](../../../catalogs/us-equities/convergence-20260926.json).
Host paths are rewritten repository-relative; `<session-scratch>` replaces private session paths and
`<private-memory>` private memory paths, and `<email>` email addresses. Claim checks that cite private host memory
keep their name and verdict with their text withheld. In mapper reasoning, layer summaries and packet prose, a
sentence or clause that cites it is replaced by `[A sentence citing private host memory is withheld.]` or
`[A clause citing private host memory is withheld.]`; the three clause markers were set by hand on 2026-10-01 after
an independent landing review, because the builder is not retained. UUIDs, including those inside source URLs, are replaced by `<uuid>`
because `scripts/validate.py` treats any UUID as a possible session identifier; the record's quotes use the same
sanitized text.

- `gpt6-votes/<layer>--<lens>.md`: each GPT-6 cross-family refutation, copied unchanged apart from path
  sanitization. `gpt-6-live` ran with `-c web_search="live"`; `gpt-6-cached` ran with the client default (cached
  search index). Every vote quote in the record is an exact span of these texts (whitespace collapsed).
- `packets/<layer>.json`: the per-layer input the mappers read: the Claude proposal (winner status, challengers,
  rejections), the Claude claim checks and the researched candidates.
- `papers-strategy.md`: the live GPT-6 academic-paper sweep for strategy-research (first line `PAPERS: 25 verified`).
  Its one direct protocol contradiction (the ABJK 2022 sample description) was re-verified by the coordinator against
  the manuscripts; a text-only correction is proposed in Mover v3 round 18 (PR #360, under review).

These are model outputs: each is one refutation attempt, not a panel, and not upstream acceptance.
