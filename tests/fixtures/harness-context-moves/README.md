# Relocated rule contracts (2026-10-05)

Frozen passage bytes from job 075 at `2e681ae5c8f7dfd5d92c7ee9f7b8205ed077f710`,
with the PR #726 repair exceptions recorded in
`docs/decisions/2026-10-05-harness-context-budget.md`. No trailing separator
newline is included. The original 868-byte routing paragraph is restored to
root AGENTS.md until the two-host render gate; the portable 782-byte form is
bound to the Codex top-rule section. The trading and dashboard fixtures remove
only their redundant self-pointers as directed by the repair read. All other
passage bytes are the original moved text, including the complete workflow
group whose StructuredOutput sentence is also restored in the user block.

`PortableTopRuleTests` slices each destination by the named heading (the Codex
top-rule marker is its section boundary) before comparing raw bytes. The
fixtures and byte counts are reviewed contracts, never regenerated from current
destination content by the test.

## Agent-team accuracy correction (2026-10-06)

The [separate dated decision](../../../docs/decisions/2026-10-06-agent-teams-carrier-corrections.md)
links this correction to the preserved October 5 decision and snapshots.

The feature check's approved effort and 5.5 task-tool corrections supersede only
the active contracts for passages 09 and 10. Their October 5 snapshots remain
unchanged in `09.txt` and `10.txt`. The dated `09-20261006.txt` and
`10-20261006.txt` bind the corrected passages, including their terminating line
ending, to the same destination section. All other contracts retain their original
bytes. Sources are the README's agent-team docs and pinned changelog citations;
the tests still compare frozen expected bytes, rather than regenerate them.

## Instruction-core trim (2026-10-07)

The [instruction-core decision](../../../docs/decisions/2026-10-07-instruction-core.md)
changes the active contracts in two ways. Every earlier snapshot keeps its bytes.

Contract 01 leaves `contracts.json`. Root `AGENTS.md` no longer has the
`## Workers, effort and lanes` heading, and its copy of the routing paragraph is
now a pointer to the Codex user-level block. `01.txt` stays as the 868-byte
October 5 snapshot and is bound to no destination. Contract 08 still binds the
782-byte portable form to the Codex top-rule section, so the statement above
that the 868-byte paragraph is restored to root `AGENTS.md` describes October 5
and no longer the current file.

Contracts 12 and 13 are new. `12.txt` (485 UTF-8 bytes) is the courier recipe
for messaging a Claude Code session, which was line 30 of the Codex template at
`475127d43c1cce70dba5cd31238af4e078fa17eb`. `13.txt` (319 bytes) is the
upstream-practice citation sentence that followed the dispatch-mode sentence on
line 43 of the portable Claude block at the same commit. Each is a new bullet at
the end of the README's `## Native workflow mechanics relocated (2026-10-05)`
section, and neither fixture includes a trailing newline. They bind moved text;
they are not context-savings measurements.
