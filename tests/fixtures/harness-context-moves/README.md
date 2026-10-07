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
