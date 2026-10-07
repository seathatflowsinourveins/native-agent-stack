# Complete the reopened instruction-surface source audit

Date: 2026-10-06. Decision: retain native defaults for the six newly reviewed names and continue watching the three instruction documents with their reviewed current bodies. This completes source currency for the foundation's context-loading contract. No instruction or client setting is applied, and no token-saving or runtime-acceptance claim is made.

The [partial decision at #805@23d4366e](https://github.com/seathatflowsinourveins/native-agent-stack/blob/23d4366e26910ae43783518bd6807625a9e5e409/docs/decisions/2026-10-06-harness-context-budget-refresh.md) and [its receipt](https://github.com/seathatflowsinourveins/native-agent-stack/blob/23d4366e26910ae43783518bd6807625a9e5e409/evidence/artifacts/ns2604-context-audit-20261006/review.json) remain unchanged. They recorded seven reviews and two pending Codex tagged-source checks. This new record supplies those checks and the final nine rows. Evidence: [review.json](../../evidence/artifacts/ns2604-context-audit-completion-20261006/review.json).

## Completed tagged-source checks

Installed Codex 0.160.1 reports both guardian names as under development and false. Its [0.160.1 release note](https://github.com/openai/codex/releases/tag/rust-v0.160.1), published 2026-10-05, describes the Windows remote stdio MCP environment repair. Feature conclusions come from the installed client and tagged source, rather than absence from that note.

The official rust-v0.160.1 checkout resolves to d27764b82f7118f674371e6d6e76271d9d606edb. Semble retrieval was followed by original-file reads. Both definitions are UnderDevelopment with default_enabled false.

| Name | Primary source and purpose | Disposition |
| --- | --- | --- |
| guardian_conversation_history_tools | [features/src/lib.rs:1684-1688](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/features/src/lib.rs#L1684-L1688); [reviewer_config.rs:48-62](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/src/guardian/reviewer_config.rs#L48-L62) additionally requires Apps. [The history prompt](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/src/context/guardian_conversation_history.rs#L29-L38) retrieves the owner's earlier instructions, including restrictions and revocations. | Decline explicit activation; no demonstrated host need. |
| guardian_root_handoff_context | [features/src/lib.rs:1666-1670](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/features/src/lib.rs#L1666-L1670); [its declaration at :333-334](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/features/src/lib.rs#L333-L334) limits worker Guardian root evidence to preceding root communication windows. | Decline explicit activation; retain native false. |

Tagged [history scenarios](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/tests/suite/scenarios_guardian_conversation_history_tests.rs#L98-L215) cover parent identity, bounded output and changed permissions. Tagged [root-handoff scenarios](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/tests/suite/guardian_root_handoff.rs#L67) cover activation, descendant restrictions and compaction fallback. These files were reviewed, not executed. Runtime-gate tracing beyond the sparse checkout is not asserted. The separate stable parent-compaction feature is outside this decision.

Overturn either decline when a supported upstream release and concrete host need are qualified through the unchanged corresponding upstream scenarios.

## Carried reviews and current document bodies

The four Claude dispositions retain the inspected 2.1.292 judgments: leave idleCompaction at its native rollout/default; leave session-state and gzip overrides unset globally; require an evidenced scoped additional-CA need for NODE_EXTRA_CA_CERTS. The installed artifact's SHA256 was rechecked against the previous embedded-source proof. [The environment reference](https://code.claude.com/docs/en/env-vars), [network trust reference](https://code.claude.com/docs/en/network-config#ca-certificate-store) and [2.1.292 changelog](https://github.com/anthropics/claude-code/blob/fbe20e00e2851fc01506f54f98a8f0b875af3847/CHANGELOG.md#L6) accompany that proof. Publisher-download equivalence and the specific UNC fix's live behavior remain unasserted. Agent effort, UNC release-note and print/background-wait findings keep their earlier source-only scope.

Current [memory](https://code.claude.com/docs/en/memory) and [skills](https://code.claude.com/docs/en/skills#skill-content-lifecycle) body hashes match the privately retained reviewed bodies. The official [Codex Markdown guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md) was refetched and matches its retained body. Watch that Markdown URL to avoid redirected HTML representation churn; update the digest only after review.

| Document | Reviewed SHA256 |
| --- | --- |
| Claude memory | b4e76ef1a2356fe39d5b5a70368a884e4128f1fc77a70e3556af9d4f84940562 |
| Claude skills | cf869f4c734b4094b0eaacb308b79447c9ebd5587ec30e186fc54441e8b11147 |
| Codex AGENTS Markdown | 9d1f87a2d1cb55b4782b95abe710692b35b9659789c2db31a22c7074a3383e8e |

Previous reviewed body bytes were unavailable; different hashes alone do not establish a historical semantic delta. Current guidance preserves import/loading distinctions, invoked-skill compaction limits and root-to-cwd Codex discovery. The partial record's two proposed carrier sentences remain proposals for the command center; this PR edits no instruction file or template.

## Completion and reopening

Preserve unrelated rows, update the three existing document rows by key, and append only the six newly reviewed name rows. Each retains its source, reviewed version, scope and overturn condition. The native watch result after applying these candidate rows is recorded separately in the receipt. The unchanged main catalog's earlier nine-unreviewed result remains retained. Source review and schema validation alone do not establish zero unreviewed.

The catalog and evidence registry are shared last-commit files. Neighbours include #802, #813, #770, #769 and #764. On rebase take main's catalog and re-apply only these nine keys, preserving its valid source corrections. #805's partial decision, receipt and resolver ownership amendment remain unchanged and separate.

Alternatives were leaving the reopened list unresolved or enabling developing features without an evidenced need. Installed and tagged sources support the native-default decision. Any new document-body digest reopens the audit; changed source or measured adoption need reopens the corresponding name disposition. Repository checks establish schema, references and hashes, not native context efficiency.

Completeness critic covered all nine keys, installed readbacks, tagged definitions, unchanged-scenario scope, current document identities and preserved history. A copied pending-source field in the new proposal was corrected before publication from the actual tagged-source result. No material source or schema gap remained.
