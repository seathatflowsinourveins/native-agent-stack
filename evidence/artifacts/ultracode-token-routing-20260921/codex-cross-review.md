# Codex cross-family review (Lane C bridge), 2026-09-21

Reviewed state: working tree before the recheck stage and before the fixes listed in the task record (review 9). Envelope: `{"outcome": "completed:success", "job_status": "completed", "result_status": 0, "elapsed_ms": 405190, "thread_id": "[redacted]", "turn_id": "[redacted]", "touched_files": []}`

## Prompt

Read-only cross-family review. Repository: ~/code/agent-lab (branch codex/native-expansion). Do not edit, create or delete any file and do not change git state.

Review ONLY these named files, as they are in the working tree, against `git diff HEAD -- <file>` for tracked ones (the rest are new and untracked):
- .claude/agents/source-scout.md (new), .claude/agents/evidence-reviewer.md, .claude/agents/isolated-builder.md
- .claude/workflows/review-changes.js, .claude/workflows/readiness-audit.js
- .claude/workflows/test-envelope.mjs, .claude/workflows/child-usage.mjs (new), .claude/workflows/test-child-usage.mjs (new), .claude/workflows/test-contract-mutations.mjs (new)
- .claude/settings.json, AGENTS.md (Parallel work section only), docs/native-token-workflow.md (section "Workflow contract" to end of file)
- docs/tasks/2026-09-21-ultracode-token-routing.md and docs/evidence/ultracode-token-routing-20260921/ (receipts the tests read)

Intent of the change: route Claude Code workflow stages to lean, task-matched project agents (source-scout Sonnet/medium for extraction and acceptance commands, evidence-reviewer Opus/high read-only review, isolated-builder Sonnet/medium in a worktree), keep MCP lanes deferred behind ToolSearch with named grants, keep one byte-identical worker packet across saved workflows, record per-child requested/resolved model and provider usage from native Workflow transcripts, and size workflows to the task (`workflowSizeGuideline: unrestricted`, three concurrent).

Find concrete correctness defects, not style: logic errors in child-usage.mjs (message de-duplication, per-model accounting, completeness rules, --latest resolution), holes in the static contract in test-envelope.mjs (ways a saved workflow or agent definition could violate the contract and still pass), contradictions between agent bodies, workflow stage prompts, AGENTS.md and docs/native-token-workflow.md, claims in the docs or task record that the in-repository receipts do not support, and anything in review-changes.js acceptance logic that could report `accepted` without the evidence it requires.

You may run these read-only checks and should report their exact summary lines: `node .claude/workflows/test-envelope.mjs`, `node .claude/workflows/test-child-usage.mjs`, `node .claude/workflows/test-contract-mutations.mjs`, `node .claude/workflows/test-codex-envelope.mjs`, `node .claude/workflows/check-syntax.mjs .claude/workflows/review-changes.js .claude/workflows/readiness-audit.js`.

Return a prioritized list. For each finding: severity (high/medium/low), file and line, the defect in one or two sentences, and the evidence (quoted line or command output). If you find nothing actionable in an area, say so explicitly. Keep the whole answer under 900 words.

## Returned findings

Found nine actionable issues. No files or git state were changed. Counterexamples below used in-memory substitutions, not native Workflow runs.

1. **Medium — [review-changes.js:119](.claude/workflows/review-changes.js:119): acceptance does not require complete file coverage.** An inventory can omit a requested untracked file entirely while its remaining claims receive confirmed verdicts. A probe requesting both the workflow and `source-scout.md`, but returning evidence only for the workflow, produced `"status":"accepted","accepted":true,"evidence_issues":[]`, despite line 49 requiring every untracked file to be read and inventoried.

2. **Medium — [child-usage.mjs:23](.claude/workflows/child-usage.mjs:23): missing usage silently undercounts successful children.** Assistant messages without usage are discarded; an empty usage object becomes zero counters. Probes returned `complete:true, requests:1` for two distinct messages when one lacked usage, and `complete:true` with every counter zero for `usage:{}`.

3. **Medium — [child-usage.mjs:42](.claude/workflows/child-usage.mjs:42): an unresolved model passes completeness.** Missing models are filtered out before `resolved.some(...)`, making the check vacuously succeed. A usage-bearing message without `message.model` returned `"complete":true,"resolved_models":[],"issues":[]`.

4. **Medium — [test-envelope.mjs:243](.claude/workflows/test-envelope.mjs:243): the scanner misses valid calls and effective option overrides.** Adding `if (args.extraStage) await agent ('extra', { label: 'extra' })` bypasses the `agent(` matcher; [line 238](.claude/workflows/test-envelope.mjs:238) also reads the first property, overlooking a later conditional `model` override to `undefined`. Each mutation returned `SUMMARY passed=142 failed=0 total=142`.

5. **Medium — [test-envelope.mjs:291](.claude/workflows/test-envelope.mjs:291): packet validation checks only its opening label.** The assertion uses `startsWith('Worker packet contract:')`, rather than the complete shared packet. Replacing the reviewer’s `PACKET +` with `'Worker packet contract:' +`, dropping all shared rules, still returned `SUMMARY passed=142 failed=0 total=142`.

6. **Medium — [test-envelope.mjs:295](.claude/workflows/test-envelope.mjs:295): incompatible or missing stage routing passes.** Validation checks only supplied agent names, without binding stages to their intended roles. Removing inventory/review `agentType`, or routing review to `isolated-builder`, each passed all 142 assertions despite losing the intended capabilities and restrictions.

7. **Medium — [test-envelope.mjs:320](.claude/workflows/test-envelope.mjs:320): builder isolation is unprotected.** Removing `isolation: worktree` from `isolated-builder.md` still returned `SUMMARY passed=142 failed=0 total=142`. The remaining assertions validate model, effort and tools without preserving automatic worktree isolation.

8. **Medium — [source-scout.md:11](.claude/agents/source-scout.md:11): acceptance-command permissions conflict.** Its body permits named acceptance commands to write artifacts, while [review-changes.js:19](.claude/workflows/review-changes.js:19) requires “read-only effects” and [the documented contract:58](docs/native-token-workflow.md:58) permits writes only with an owned worktree. The worker receives inconsistent instructions for ordinary build/test checks.

9. **Low — [task record:32](docs/tasks/2026-09-21-ultracode-token-routing.md:32): retained receipts do not establish the builder’s claimed execution evidence.** The record asserts worktree cwd, commit and passing commands, but the builder receipt contains usage/model metadata without those observations. [test-child-usage.mjs:77](.claude/workflows/test-child-usage.mjs:77) checks only completeness, agent type, model and effort; the stronger runtime claims remain unverified from the supplied receipts.

No additional actionable findings in identified-message deduplication, per-model arithmetic, `--latest` selection within the inspected layout, current named MCP grants, or settings/AGENTS sizing agreement. Stored numeric receipt comparisons matched.

Checks run:

- `node .claude/workflows/test-envelope.mjs` — `SUMMARY passed=142 failed=0 total=142`, exit 0.
- `node .claude/workflows/test-child-usage.mjs` — exit 1, `EROFS: read-only file system, mkdtemp '/tmp/child-usage-XXXXXX'`; no summary emitted.
- `node .claude/workflows/test-contract-mutations.mjs` — exit 1, `EROFS: read-only file system, mkdtemp '/tmp/contract-mutation-XXXXXX'`; no summary emitted.
- `node .claude/workflows/test-codex-envelope.mjs` — seven PASS lines, exit 0; no summary emitted.
- Syntax check, exit 0:
  ```
  SYNTAX_OK .claude/workflows/review-changes.js
  SYNTAX_OK .claude/workflows/readiness-audit.js
  ```

The receipt-only assertion block also ran separately without writes: `RECEIPT_BLOCK_ONLY passed=13 failed=0 total=13`.
