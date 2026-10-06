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
