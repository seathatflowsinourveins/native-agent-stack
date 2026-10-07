# Decision: correct current agent-team carriers and preserve their history

Date: 2026-10-06. Lane: foundation. Status: decided; repository record awaiting
independent review.

## Context

The [October 5 context-budget decision](2026-10-05-harness-context-budget.md#relocated-passage-contracts-amended-by-pr-726)
bound relocated workflow passages to frozen byte contracts. Its passage 09/10
claims need corrections in the current workflow guidance. The command center's
October 6 feature check and historical-record preservation direction authorize
the current-carrier correction and this separate linked record.

## Decision

Correct the [current agent-team guidance](../../examples/claude-native/workflows/README.md)
and the eight named rows in the [upstream dispositions catalog](../../catalogs/foundation/upstream-surface-dispositions.json).
The agent-teams switch is enabled under CC rule 18's narrow scope. Catalog
states retain the supported schema; applied settings, pending hook installation
and upstream defaults remain distinct.

The docs give an in-process teammate its definition's effort; the v2.1.288
changelog confirms that behavior only for plugin agents. The configured lead
and project-agent paths here both specify max, so that distinction does not
change their declared effort. Actual runtime effort for user/project agents
remains unverified. Opus/Sonnet 5.5 have no shared task list without the explicit
TODO-tool opt-in; current guidance records that qualification.

Update the active [passage contracts](../../tests/fixtures/harness-context-moves/contracts.json)
to the new [09-20261006.txt](../../tests/fixtures/harness-context-moves/09-20261006.txt)
and [10-20261006.txt](../../tests/fixtures/harness-context-moves/10-20261006.txt)
fixtures: 865 and 2,034 UTF-8 bytes including their terminating line endings.
These are corrected-text contracts, not new context-savings measurements or
native acceptance results. The original [09.txt](../../tests/fixtures/harness-context-moves/09.txt)
and [10.txt](../../tests/fixtures/harness-context-moves/10.txt) snapshots, the
October 5 decision and its measurements remain unchanged. The other nine
active contracts keep their original bytes.

## Alternatives and revisit condition

Retaining the old current guidance would preserve claims contradicted or
qualified by upstream evidence. Rewriting the October 5 record or its snapshots
would obscure what was originally measured. Correcting the current carriers
with new contracts and this linked record preserves both the usable guidance
and its evidence history.

Revisit the guidance when newer upstream docs or releases change team effort,
task-tool availability or the named feature defaults, or when the CC changes
rule 18's scope. Compare the new primary evidence with these pinned sources;
issue another linked record and update current carriers if it supersedes them.

## Sources

- [Agent-team docs, effort](https://code.claude.com/docs/en/agent-teams.md#L277)
  and [in-process default](https://code.claude.com/docs/en/agent-teams.md#L107-L111).
- [Claude Code v2.1.292 changelog, v2.1.288 plugin-agent effort fix](https://github.com/anthropics/claude-code/blob/fbe20e00e2851fc01506f54f98a8f0b875af3847/CHANGELOG.md#L365).
- [Same pinned changelog, v2.1.268 TODO-tool qualification](https://github.com/anthropics/claude-code/blob/fbe20e00e2851fc01506f54f98a8f0b875af3847/CHANGELOG.md#L1986).
- Private source locators: `coordination/e2e-truth-20261006/feature-gap-wf_2da8a9ff-307.json#/result/final`,
  `coordination/command-center/cc-tools/CC-RULES-ADDENDUM-20261006.md:9-23`, and
  CC item `task-ns2604-coop-20261006T223917Z`, point 6. Each changed catalog row
  carries its own upstream docs or versioned changelog citation.
