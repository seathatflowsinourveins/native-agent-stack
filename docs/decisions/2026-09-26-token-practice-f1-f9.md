# Decision: token practice F1–F9 (2026-09-26)

**Decided by:** the token-save foundation plan; PR-R records its F1–F9 decisions and source checks.

**Scope:** lane:shared records and recipes. These decisions distinguish the selected practice,
host window A/B work and hosted CI qualification; this documentation change does not certify
that any host reconfiguration or new provider run completed.

## F1. RTK version (2026-09-26)

**Decision:** retain the qualified RTK v0.50.0 stable pin and reject `dev-*` prereleases.
**Alternatives rejected:** the `dev-0.51.0-rc.467` candidate and adopting a prerelease merely
because it is newer.
**Overturn:** the first stable release after v0.50.0 triggers qualification. Switch only when
a replay against the same five-exclusion baseline preserves eligible command-part coverage
and exactness, with no new output or exit-code regression.
Sources: [v0.50.0](https://github.com/rtk-ai/rtk/releases/tag/v0.50.0),
[retained qualification](../../evidence/receipts/rtk-050-qualification-20260925.json) and
[exactness exclusions](../../recipes/README.md#native-context-mode-and-hooks).
A partial rewrite is not complete coverage of a compound call.

## F2. Exclude jq (2026-09-26)

**Decision:** add plain `"jq"` as the fifth hook exclusion to preserve exact JSON output.
**Alternatives rejected:** keep the four-entry configuration and recover truncated jq output
only after it is consumed; exclude the entire compound call when just its jq segment needs
exactness.
**Overturn:** a stable candidate must preserve complete jq output on the same truncation
fixtures, including long lines and more than 40 lines, and match native exit codes, while
retaining the other segments' rewrites. Compare both versions with identical exclusions
before deciding to remove this one.
Source: [RTK v0.50.0 `compile_exclude_patterns`, `registry.rs:1540–1569`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1540-L1569);
[recipe and discriminating probes](../../recipes/README.md#native-context-mode-and-hooks).
A plain entry becomes `^jq($|\s)`; it is not a whole-call ban.

## F3. Command shape (2026-09-26)

**Decision:** use RTK-compatible command shapes and separate unsafe segments when a hook
rewrite is wanted.
**Alternatives rejected:** upgrading to a prerelease to recover structurally deferred calls,
or batching an unsafe substitution, file redirect or heredoc with otherwise eligible commands.
**Overturn:** a stable upstream release must rewrite those previously deferred shapes and
producer pipelines while preserving native output, exit codes and permission behavior on
the same positive and negative controls.
Sources: [RTK v0.50.0 `src/hooks/decision.rs:86–88`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/hooks/decision.rs#L86-L88),
[`registry.rs:1087–1345`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1087-L1345)
and [the handbook's precise rule](../token-session-handbook.md#what-runs-automatically-and-what-you-select).
The plan's multiline shorthand needs qualification: [`registry.rs:727–732, 951–1013`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L951-L1013)
rewrites ordinary independent lines; unsupported blocks defer. `gh` is not producer-safe,
so a preceding rewritten git segment does not qualify a `gh ... | head` pipeline.

## F4. Codex RTK guidance (2026-09-26)

**Decision:** inline upstream RTK awareness verbatim in Codex's global instructions, followed
by a marked exactness/builtin exceptions block; keep the Codex rewriting hook held.
**Alternatives rejected:** relying on an `@RTK.md` pointer, prefixing every command without
exceptions, or treating hook exclusions as protection against an explicit `rtk` prefix.
**Overturn:** a release containing RTK #4175. Then re-copy the upstream text and drop the
builtin line. Other exactness exceptions retain their own probes; the Codex hook separately
needs native unwrapping of RTK or `updatedInput` without `allow`, followed by qualification.
Sources: [v0.50.0 awareness](https://github.com/rtk-ai/rtk/blob/v0.50.0/hooks/rtk-awareness-full.md),
[Codex v0.157.1 literal instruction loading](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/agents_md.rs#L150-L177),
[issue #3969](https://github.com/rtk-ai/rtk/issues/3969),
[fix #4175](https://github.com/rtk-ai/rtk/pull/4175),
[explicit-prefix bypass, `registry.rs:1690–1693`](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1690-L1693)
and [the recipe's Codex hook hold](../../recipes/README.md#native-context-mode-and-hooks).

## F5. Output routing (2026-09-26)

**Decision:** keep automatic large-output routing as a recorded gap and pursue the
context-mode enhancement instead of writing a PostToolUse router.
**Alternatives rejected:** a self-written `updatedToolOutput` filter with no maintained
upstream reference implementation; treating context-mode's advisory hooks as automatic
execution.
**Overturn:** a maintained upstream implementation of that output-filter path, exercised on
large successful and failed results, must retain required facts and recovery paths and
improve total compression-plus-recovery cost against explicit ctx selection.
Sources: [reviewed context-mode `hooks/pretooluse.mjs`](https://github.com/mksglu/context-mode/blob/6f0cc6841c687e754059f36714a11233fda1a02b/hooks/pretooluse.mjs)
and [upstream-first acceptance policy](../acceptance-evidence-policy.md).
This record does not claim an enhancement has been filed by PR-R.

## F6. jcodemunch scope (2026-09-26)

**Decision:** restore jcodemunch-mcp to local scope (project-scoped) in window A.
**Alternatives rejected:** user-scope registration that injects its code-navigation preference
into every Claude project, and removing the useful opted-in package entirely.
**Overturn:** a measured task class where jCodeMunch beats `rg`, Serena and SocratiCode, or
regular jCodeMunch use in projects beyond the originally opted-in project. Either reopens
the user-scope template decision; Codex additionally needs a comparison of Codex-issued
retrieval calls that favors jCodeMunch.
Sources: [Claude profile addendum](2026-09-23-claude-user-profile.md#addendum-2026-09-25-jcodemunch-registers-per-project-not-at-user-scope)
and [Codex scope decision](2026-09-25-codex-mcp-scope.md).
The plan's `claude mcp get jcodemunch` observation from `/tmp`, `Scope: User config`,
records stale scope drift, not the target. Verify local visibility in the opted-in project
and absence in an unrelated directory; this record does not assert that window A ran.

## F7. Codex MCP approval (2026-09-26)

**Decision:** configure required read-only MCP tools per server with
`default_tools_approval_mode = "approve"` and an `enabled_tools` read-tool allowlist.
**Alternatives rejected:** leaving required worker reads unable to run under approval policy
`never`, changing that global policy, or approving every tool on a mixed read/write server.
**Prerequisite:** F7 originally marked both key names unverified. Before PR-D uses them, check
the codex-cli 0.157.1 config reference. PR-R verified both in the pinned
[`codex-rs/core/config.schema.json`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/config.schema.json)
(`RawMcpServerConfig`, `PluginMcpServerConfig`); `AppToolApproval` includes `approve`.
[`config/src/mcp_types.rs:262–272`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/mcp_types.rs#L262-L272)
defines the server default and allowlist. This verifies syntax, not a worker's successful call.
**Overturn:** a fresh worker under unchanged `never` policy and default server approval must
complete every required read while still refusing an unapproved write, making the explicit
read-tool approval unnecessary; otherwise retain it and qualify the configured worker.

## F8. Cost source (2026-09-26)

**Decision:** measure a priced token estimate per successful task using observed tokens and
cited provider list prices; retain all failed/interrupted attempts' usage and unknowns.
**Alternatives rejected:** calling that estimate billed cost, attributing aggregate Loki
events without a run ID to one task, or summing cumulative Codex completion snapshots.
**Overturn:** use collector events for task attribution only after a retained run ID and
complete token fields reconcile against the same transcripts/rollout records across success,
failure and interruption. Only reconciled provider billing can justify a billed-cost claim;
a retained `cost_usd` field alone remains an estimate.
Sources: [Claude cost accounting](https://code.claude.com/docs/en/costs#using-the-usage-command),
[Codex v0.157.1 event processor](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/exec/src/event_processor_with_jsonl_output.rs)
and [counter scope rules](../token-session-handbook.md#what-runs-automatically-and-what-you-select).
Until collector attribution is available, use Claude transcripts and Codex rollout
`token_count` records, difference cumulative totals once, and never count cache subsets twice.

## F9. Hosted CI coverage (2026-09-26)

**Decision:** retain the plan's bounded 11-of-18-tool hosted CI baseline after #370, and add
the remaining tools through PR-CI.
**Alternatives rejected:** calling the existing job full 18-tool acceptance, counting a
version check as a functional fixture, or calling our integration assertions upstream tests.
**Overturn:** raise the covered count only when the hosted workflow retains a pinned native
operation and a discriminating success/failure fixture for each additional tool, with actual
outputs and cleanup. Full coverage requires all 18; metadata checks alone cannot close it.
Sources: [hosted workflow](../../.github/workflows/native-token-e2e.yml),
[native fixture harness](../../scripts/native_token_ci.py) and
[evidence classification policy](../acceptance-evidence-policy.md).
MCPorter's bridge exercise is distinct from a standalone tool fixture; coverage and evidence
classes must remain explicit when PR-CI updates that baseline.

## ccusage publication trigger (2026-09-26)

This supersedes only the ccusage publication clause in
[the workstation refresh decision](2026-09-25-workstation-sota-refresh.md):
**Trigger: any version newer than 20.0.24 is published.**
The former condition named only 20.0.25; publication of a later version must also reopen
qualification. Keep the installed 20.0.24 pin until that qualification passes.
[GitHub's latest-release API](https://api.github.com/repos/ccusage/ccusage/releases/latest)
returned [v20.0.24](https://github.com/ccusage/ccusage/releases/tag/v20.0.24), published
2026-09-21T11:23:53Z, when checked for this record.
[The release identity](../../manifests/landscape.json) includes the
[tag-resolved commit](https://api.github.com/repos/ccusage/ccusage/commits/v20.0.24),
`ecb676cce27cb5dd0090c7804a5cecc35e8ba805`; a tag alone is not publication.

**Update (2026-09-27): the trigger fired and 20.0.26 qualified.**
[v20.0.26](https://github.com/ccusage/ccusage/releases/tag/v20.0.26) was published
2026-09-27T16:26:00Z at `d9821088b98aa536c7a385aa1a4579d6fa02269b`; v20.0.25 exists only as
a tag and was never published to npm. The
[qualification receipt](../../evidence/receipts/ccusage-20026-qualification-20260927.json)
records the tarball digests, the unchanged upstream Rust suite (944 passed, 0 failed,
3 ignored) and the Node tests (34 of 34, identical files at both tags), the unchanged
native_token_ci fixture on both versions, and identical daily, weekly and monthly token
totals on this host's native histories. 20.0.26 also prices `claude-opus-5-5` and
`gpt-6-luna`, which 20.0.24 left unpriced. The coordinator switched the workstation launcher
at 2026-09-27T22:01:01Z and kept the 20.0.24 prefix for rollback; the Linux and macOS pins
move to 20.0.26, the macOS one on registry evidence only.
**Next trigger: any version newer than 20.0.26 is published.** Changed token totals on the
same native range, a failed fixture, or a failing upstream suite at the new tag would
overturn a move; a cost figure still needs qualified prices for every model it covers.
