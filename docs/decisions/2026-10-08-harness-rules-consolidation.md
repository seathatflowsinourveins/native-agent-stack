# Decision: consolidated harness core and proactive native automation

Date: 2026-10-08. Trigger: owner direction dated 2026-10-08. Scope: G6a core instruction consolidation.

## Decision and behavior

The four-bullet philosophy remains the shared core. Its fourth bullet now assigns the harness automatic application of landscape-converged practice through hooks, workflows, rulesets, scheduled sweeps and runtime workers, whether or not the prompt names that practice. The existing primary-source, reproduced-evidence, focus, protected-window and correction duties remain.

The exact core configuration has SHA-256 `85eb7d41af97d086f76e4b96e55ddaf76240240fe55425a054f1954c85ff59c9`. It appears once in each of the six repository carriers:

- [AGENTS.md](../../AGENTS.md);
- [portable Claude instructions](../../examples/claude-native/CLAUDE.md);
- [Codex instruction template](../../adoption/templates/codex.AGENTS.template.md);
- [new-WSL Claude instructions](../../adoption/new-wsl/claude-user-instructions.md);
- [new-WSL Codex instructions](../../adoption/new-wsl/codex-user-instructions.md);
- [repository scaffold](../../adoption/scaffold/AGENTS.md).

The repository CLAUDE.md retains its AGENTS.md import. The existing native RTK awareness, Claude StructuredOutput sentence and repository/subtree prerequisites keep their content and scopes. Existing native loaders, managed carriers and test harnesses carry the new core; no replacement loader, upstream fork or new routing framework is introduced.

The [enforcement map](../harness-rule-enforcement.md) organizes responsibilities into core, repository/client contract, roles and lanes, domains, and enforcement. It names the actual enforcer and bounded gap for each rule family. An instruction or recurring schedule does not establish successful automatic adoption or semantic adherence.

## SOTA sources and adoption path

- Claude Code 2.1.294, `anthropics/claude-code@71cdddec623889d38af14b7a489670a03186f659`: [CHANGELOG.md](https://github.com/anthropics/claude-code/blob/71cdddec623889d38af14b7a489670a03186f659/CHANGELOG.md). Official [hooks](https://code.claude.com/docs/en/hooks), [memory](https://code.claude.com/docs/en/memory), [skills](https://code.claude.com/docs/en/skills) and [best practices](https://code.claude.com/docs/en/best-practices), fetched 2026-10-08. Native hooks provide runtime event entrypoints; task-selected skills and scoped rules provide disclosure; broadly applicable instructions remain concise in the startup carrier.
- Codex 0.161.0, `openai/codex@979011409de0a60b52f179721948e65531d26144`: [AGENTS discovery](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/src/agents_md.rs), [native hook discovery](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/hooks/src/engine/discovery.rs) and [native exec usage](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/exec/src/event_processor_with_jsonl_output.rs). Hook support is established by the installed version and pinned source; unsupported handler types are not assumed to work.
- GitHub official [rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets), [available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) and [schedule semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), fetched 2026-10-08. Rulesets enforce configured predicates; schedules start recurring work but can be delayed or dropped.
- [AGENTS.md open format](https://agents.md/) and [Agent Skills specification](https://agentskills.io/specification), read 2026-10-08. Reuse native instruction discovery and skill packaging for the shared core and task-specific detail.

The [primary-source receipt](../../evidence/artifacts/harness-rules-20261008/B-source-receipts.md) records installed-version checks, source pins and documentation boundaries. Both installed research routes ran; the [run receipt](../../evidence/artifacts/harness-rules-20261008/B-run-receipts.json) separates degraded GPT Researcher retrieval from successful DeerFlow retrieval and source review. Those runs inform the source survey, not a behavior claim for the new sentence.

## Measured impact and declared expectations

The shared core grows 169 UTF-8 bytes and 22 words: 1,486 to 1,655 bytes, 220 to 242 words. The existing `template_segments()` function measures the Codex top segment at 1,692 bytes/245 words; its SHA-256 changes from `bc9f31381973206657685bd1169ff18ce1f64304c3cf287be20fec314bd2aae7` to `bf363f0fdc267ac9fb5d814d950e7e9fb6b1cb436587f739d93e16cd0338ef42`. RTK pins remain unchanged.

The existing `startup_files()` scopes grow Claude 4,390 to 4,728 and Codex 4,491 to 4,829 bytes. The declared fixed ceilings use the existing rounded-up 5% rule: Claude 4,610 to 4,965; Codex 4,716 to 5,071. This is a declared expectation change rather than an automatic budget adjustment. The [test-impact receipt](../../evidence/artifacts/harness-rules-20261008/D-test-impact.json) binds these measurements and controls to its preparation base.

| Existing test | Declared change |
| --- | --- |
| StandingRuleSurfacesTests.test_the_portable_block_is_exactly_the_core_and_the_evidence_backed_line | CORE changes; exact equality and the retained StructuredOutput line remain. |
| StandingRuleSurfacesTests.test_every_layer_carries_the_same_core_and_no_dropped_rule | CORE changes in the same six layers; once-only and retired-rule exclusions remain. |
| StandingRuleSurfacesTests.test_the_repository_file_keeps_its_core_and_the_trading_prerequisite | CORE prefix changes; every repository/trading prerequisite assertion remains. |
| TemplateTests.test_top_rule_is_pinned_and_rendered_rtk_is_the_unchanged_pinned_source | Top-rule hash changes; native RTK source and pins remain. |
| PortableTopRuleTests.test_rendered_startup_files_fit_each_clients_fixed_byte_budget | Two declared fixed ceilings change to 4,965/5,071. |
| PortableTopRuleTests.test_growth_in_any_loaded_file_crosses_the_fixed_budget | The same constants change; the existing negative growth control remains. |

The recorded core-only preparation control at `8ee8b3bd796c738592e92acd94d7902db3692311` runs 32 tests successfully on the unchanged baseline. Exact proposed text under unchanged expectations produces 12 failed assertions/subtests across the six methods, with no errors. The overlay with the declared CORE/pin/budget changes runs all 32 successfully. Existing test-function bodies remain structurally unchanged in that core-only overlay. These are preparation controls; final reduced-head CI and the independent 5f comparison have their own results.

The installed clients' native counters measure the exact two-source text projections. Claude Code 2.1.294 `/context` reports projected memory 1,182 to 1,296 tokens, +114 client-estimated tokens. Codex 0.161.0 fresh one-turn `exec` reports input 17,165 to 17,231 tokens, +66 gateway-reported tokens. Paths, prompts and unchanged control layers are fixed in the [before](../../evidence/artifacts/harness-rules-20261008/D-native-two-scope-before.json) and [proposed](../../evidence/artifacts/harness-rules-20261008/D-native-two-scope-proposed.json) receipts. No characters-per-token approximation or external tokenizer replaces those counters.

These are controlled text projections. They do not prove quality, adherence, billing, effective gateway tier or final post-F9 loading. Native `exec` reports accumulated thread usage, so the comparison uses fresh one-turn threads. Source review and exact text/pin checks are distinct from native behavior acceptance.

## Alternatives and overturn conditions

Retaining the previous core leaves automatic harness action implicit. Putting the duty only in an on-demand procedure depends on selecting that procedure for a responsibility intended across tasks. A new section or routing layer splits the same duty and adds persistent context. The selected sentence in bullet four reuses the existing tested carriers and native automation interfaces.

Reopen the wording or organization if a controlled native comparison finds poorer adherence, focus or protected-window observance; if installed vendor loading/hook contracts change; or if an enforcement claim fails reproduction. Source-heading presence, popularity, agreement and freshness alone do not establish behavior.

## Reduced-PR and host verification

G6a contains only the six carriers, declared core test constants, this dated record, the enforcement map, the bounded proactive-amendment edit and their cited evidence/digest rows. Settings ownership and broader historical-record work remain separate follow-ups.

All eight validate shards must pass on the draft PR head. The reduced diff then receives the command-center read, co-op GPT review and the four shared acknowledgements before the explicit 5f landing cue. CC subsequently runs F9 and fresh-session load checks in both clients. The local PR does not apply live user instructions or client configurations.
