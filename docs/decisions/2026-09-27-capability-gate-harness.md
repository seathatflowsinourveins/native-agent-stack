# Capability-gate harness: promptfoo codex-sdk with native OTel counts (2026-09-27)

**Scope.** How the #381 Codex capability gates run and score: the jcodemunch and ai-memory approval gates and the
M13 worktree-binding gate. The harness is [`tools/capability-gate/`](../../tools/capability-gate/README.md).

**Chosen:** promptfoo 0.123.1 `openai:codex-sdk` for the sessions and the per-row verdicts, with Codex's native OTel
`codex.tool_result` records in Loki for the invoke counts. Local code is limited to three things:
- the launcher;
- the assertions and hook;
- a wrapper that creates the worktrees, checks the expected row matrix and each control's predicted outcome, and
  compares the two upstream counts.

**Alternatives considered:**
- **`matrix_scan.py`.** The E2E-matrix transcript scorer of token-efficiency-evidence-cards stays unmerged. Its owner
  recommends upstream scoring for these receipts, following the user's direction to use SOTA upstream harnesses
  rather than self-written tests.
- **The coordinator's scratch driver `m13_probe.py`,** never committed. Its 2026-09-27 M13 run passed, 40 of 40
  per class, and both controls failed. It is replaced because its scoring depended on `matrix_scan.py`.
- **Inspect Scout 0.5.3.** It scans transcripts after the fact but does not launch the sessions, bind worktrees or
  write per-row fixtures.
- **Harbor v0.23.0.** An orchestration candidate that cannot run the unchanged profile in existing worktrees.

**Change to the earlier harness map.** The map kept M13 and the capability gate as a documented local integration,
because Harbor and Inspect could not express existing-worktree binding or `-p stack-worker` unchanged.
`working_dir` plus the launcher express both, so M13 now runs on the upstream harness.

**`trace-error-spans` is not used.** At 0.123.1,
[`codex-sdk.ts:1508-1512`](https://github.com/promptfoo/promptfoo/blob/0.123.1/src/providers/openai/codex-sdk.ts#L1508-L1512)
treats an item as failed when `item.error !== undefined`. codex-cli 0.157.1 sends `"error": null` on success, so every
completed MCP call became an error span in the 2026-09-27 smoke. The latest release on 2026-09-27 was 0.123.1, and
`main` still had the check. The JavaScript assertions require `status === "completed"` and a falsy `error` instead.

**Overturn:**
- A promptfoo release that ignores a null `error`: re-add `trace-error-spans` with `max_count: 0`.
- A promptfoo profile setting: drop the launcher.
- An upstream harness that runs the unchanged profile in existing worktrees with per-row fixtures and native OTel
  reconciliation, using less local code than this one: adopt it.

**Amendment 2026-09-27: retained results, tool identity, directory changes.** A GPT-6 cross-family review of the
first host receipts (recorded at `55fc8d17`) returned `needs_changes`. Its findings, recorded in each receipt:
- the scored results were deleted after the run, so no verdict could be checked again against the returned results
  (acceptance-evidence policy, "Preserve the returned result");
- jcodemunch and ai-memory rows passed on any tool of the server, and jcodemunch only needed a signature fragment;
- M13 rejected `cd` but no other directory change, and the shell item has no working-directory field;
- the M13 receipt omitted the shell class's missing Loki reconciliation.

The harness now makes these changes:
- it retains every run's results file privately and prints the file's sha256 in the verdict line;
- only the prescribed tool with the prescribed arguments counts, and the jcodemunch detail is the symbol id plus the
  full signature;
- it rejects `cd`, `pushd`, `popd`, `chdir`, `Set-Location` and `-C`/`--chdir`/`--directory`;
- the README states the shell working-directory limitation.

Re-recorded receipts supersede the first ones, which keep the review.

## Sources

- promptfoo 0.123.1 (tag commit `34f74d34`), https://github.com/promptfoo/promptfoo/tree/0.123.1:
  - `site/docs/providers/openai-codex-sdk.md`: the provider and its config keys;
  - `src/providers/openai/codex-sdk.ts#L1508-L1512`: the null-error check;
  - `#L2430`: the raw items;
  - `site/docs/configuration/expected-outputs/deterministic.md#trajectorytool-used`: tool-span assertions;
  - `site/docs/configuration/reference.md` "Extension Hooks";
  - `site/docs/configuration/test-cases.md`: test-level `providers` and dynamic test generation;
  - `src/evaluator.ts#L3587` (`beforeEach` per step) and `#L4102` (steps run in order with at most `maxConcurrency`
    in flight).
- @openai/codex-sdk 0.153.4, bundled with promptfoo 0.123.1: `dist/index.js` passes `working_dir` as `--cd` and sets
  `CODEX_INTERNAL_ORIGINATOR_OVERRIDE=codex_sdk_ts`.
- codex-cli 0.157.1 (`rust-v0.157.1`, tag commit `ac0e23e5`):
  - rejects `-c profile=...` (observed on this host 2026-09-27);
  - `enabled` per MCP server (`codex-rs/config/src/mcp_types.rs#L379`) and the approval keys of decision F7;
  - `codex-rs/core/src/mcp_tool_call.rs#L1612`: the error of an MCP call refused under approval policy `never`, which
    the `prompt` controls must show.
- promptfoo 0.123.1 `src/logger.ts#L227`: `PROMPTFOO_LOG_DIR` overrides the log directory, so the wrapper pins it.
- Loki v3.7.8 (tag commit `09e6ce2f`): `docs/sources/reference/loki-http-api.md#L474-L475` (query range bounds) and
  `docs/sources/get-started/labels/structured-metadata.md#L74` (label filters on structured metadata).
- jcodemunch-mcp 1.108.319: `counter.py#L584` (`_QUERY_ARG`) and `#L616-L630` (`shape_execute_args`), read in the
  installed package.
- Measurements: the 2026-09-27 smokes of this harness on the workstation, in the harness PR.
