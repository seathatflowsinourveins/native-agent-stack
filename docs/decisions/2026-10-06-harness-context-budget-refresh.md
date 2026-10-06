# Reopen the harness context audit when upstream changes

**Date:** 2026-10-06. **Status:** source review in progress; two Codex tagged-source checks and final disposition/validation remain pending. **Purpose:** preserve the foundation's context-loading contract for north-star R&D while reviewing actual upstream changes. No instruction file, template or live client configuration is changed.

The [October 5 audit](2026-10-05-harness-context-budget.md#freshness-alternatives-and-overturn-conditions) requires a primary-source re-read when any tracked instruction body changes. This unit covers three changed documents and six previously unreviewed names. A fetched digest is not a completed audit, and re-baselining cannot clear an unreviewed item. The compact evidence and pending work are in [review.json](../../evidence/artifacts/ns2604-context-audit-20261006/review.json).

## Current primary documents

The exact October 5 reviewed body bytes were not found in the checked cache/worktree/related archive. Their known digests differ from the current bodies. This review therefore reads today's primary bodies and qualifies the comparison; it does not invent a historical semantic delta from different hashes alone. Current bodies are retained losslessly in private review state for the next comparison.

| Source, read 2026-10-06 | Reviewed current guidance | Audit consequence |
| --- | --- | --- |
| [Claude memory](https://code.claude.com/docs/en/memory) | Imported files expand at launch; ancestors concatenate; nested instructions load on demand; under 200 lines is a writing target. Automatic memory's 200-line/25KB scope is a different limit. | Preserve the current loading distinction; organization into imports alone does not establish context savings. |
| [Claude skills](https://code.claude.com/docs/en/skills#skill-content-lifecycle) | Listing metadata differs from invoked content. Invoked bodies persist; compaction retains bounded content with recent invocations prioritized. Current docs describe 5,000 tokens per skill within 25,000 shared tokens and a 1,536-character listing-text cap. | Preserve native listing/compaction behavior; measure invoked content separately and recover required guidance from its original source if omitted. |
| [Codex AGENTS guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md) | Root-to-cwd discovery and override/fallback precedence; configurable 32KiB project-document limit. The watched extensionless URL now returns redirected HTML; vendor Markdown is available. | Prefer the official Markdown body for this watched row to avoid markup-only churn, after the reopened source review completes. |

Current memory SHA256 b4e76ef1a2356fe39d5b5a70368a884e4128f1fc77a70e3556af9d4f84940562; skills cf869f4c734b4094b0eaacb308b79447c9ebd5587ec30e186fc54441e8b11147; official Codex Markdown 9d1f87a2d1cb55b4782b95abe710692b35b9659789c2db31a22c7074a3383e8e. The fresh Codex HTML and a related durable HTML archive have identical normalized main text, but neither archive matches the previously reviewed hash. That supports markup-only change relative to that archive, not to the unavailable reviewed bytes.

## Names and installed-client checks

Installed Claude 2.1.292 version/help were checked before its tagged changelog. Its native artifact SHA256 a967e7b1d8b4e47ee421d5433027880347952b0c0857abf880e2c942a4ec93b3 identifies the inspected embedded source; equivalence to a publisher download is not asserted. Six names remain a source-review work list, with 7 of 9 total document/name items reviewed so far.

| Name | Current source-review judgment |
| --- | --- |
| idleCompaction | Leave the native default/rollout alone. Installed schema says false opts out and true cannot force rollout. No named entry was found in the fetched settings reference or 2.1.292 changelog; installed source establishes presence. Do not assign an unverified settings-file scope. |
| CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS | No global override. A named SDK/print stream-json consumer may opt in when it needs session-state messages. |
| CLAUDE_CODE_GZIP_REQUEST_BODIES | Leave tri-state unset; preserve the client's body-size/rollout and proxy/mTLS/custom-CA transport decisions. |
| NODE_EXTRA_CA_CERTS | No global setting without an evidenced additional-CA requirement; use vendor-supported scoped trust configuration when necessary. |
| guardian_conversation_history_tools | Installed Codex 0.160.1 lists under development/false. Tagged-source verification pending; do not enable from this review. |
| guardian_root_handoff_context | Installed Codex 0.160.1 lists under development/false. Tagged-source verification pending; do not enable from this review. |

[Claude environment reference](https://code.claude.com/docs/en/env-vars) and [network trust documentation](https://code.claude.com/docs/en/network-config#ca-certificate-store) were re-read. Explicit choices are proposed dispositions, not claims that live environment values were read or applied. Source/version and overturn conditions accompany the ten-field rows in the review ledger.

The 2.1.292 [Agent effort addition](https://github.com/anthropics/claude-code/blob/fbe20e00e2851fc01506f54f98a8f0b875af3847/CHANGELOG.md#L6) is present in the installed Agent input schema, with instruction/user-directed overrides and fork inheritance. The [UNC approval fix](https://github.com/anthropics/claude-code/blob/fbe20e00e2851fc01506f54f98a8f0b875af3847/CHANGELOG.md#L17) is a release-note claim: the inspected installed excerpt is a command-path ask guard, not a proof of the specific Read/PreToolUse/auto-mode behavior. The [print/SDK background waiting fix](https://github.com/anthropics/claude-code/blob/fbe20e00e2851fc01506f54f98a8f0b875af3847/CHANGELOG.md#L22) has matching installed wait/wakeup control flow. None of these source checks is live behavior acceptance.

## Proposed carrier sentences for the command center

For Claude Agent tool delegation on 2.1.292 or later, pass an explicitly requested effort through the supported parameter; forks retain the parent's effort.

After compaction, verify that required guidance for the active skill remains available; recover missing guidance from its original SKILL.md.

These are proposed sentences for the command center. This PR edits no CLAUDE.md, AGENTS.md or instruction template. The other reviewed policies are already expressed by existing import-cost, native-description and source-first instructions; no redundant carrier text is needed.

## Resolver ownership and completion

The command center assigned NativeStack2604's upstream-surface resolver to the currency lane on 2026-10-06. The shared catalog has neighbouring open edits in #802, #770, #769 and #764. Take main's copy after rebase, preserve every existing row and append this unit's reviewed rows in the final shared-file commit. Do not overwrite a neighbour's valid source correction, including #802's context_management locator.

Completion requires source review of both pending Codex names, all nine current rows with version/source/overturn information, the native watch reporting zero scoped unreviewed after applying them, and repository checks. Paper-window limits defer tagged-source/Semble indexing and local validation until after 00:10Z. A source audit does not produce a new native token count, provider/GPU result or runtime acceptance; these remain their own evidence classes.
