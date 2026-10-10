# Review instructions

Apply the `## Code Review Rules` in the root `AGENTS.md` and in each nested `AGENTS.md`
that covers a changed path.

## Code Review Rules

### Corrections

- Flag a fix that does not cite the upstream source, at the pinned version, for the mechanism it
  changes, or that lacks a regression test failing before the fix. Safe path: cite the source
  file and line, release note or issue, and test the failing case.

Source: [us-equities-trading #46](https://github.com/seathatflowsinourveins/us-equities-trading/pull/46),
`AGENTS.md:139-143` at `6c42c8ab1e287a160da43b48b75692b42b880a81`.
