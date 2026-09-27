## Summary

PR-A makes the #381 measurement contract available through the existing Claude
child-usage and Codex skill-usage tools. It counts visible output and remote
fetch operations, preserves unknown/incomplete evidence, and keeps provider
usage separate from local byte counts and routing replay.

This narrow fixup restores interpreter HTTP operations omitted by the repair,
rejects malformed fields in mixed sidecar records, and corrects the documented
scope of RTK qualification and sandbox fetch buckets.

## Changes

- Add shared M3/M4/M5 result accounting, digest-bound exceptions, hook-context
  observations, MCP result states, proxy adjudication and RTK part accounting.
  Keep the legacy lane comparison fields and actor populations distinct.
- Normalize Codex persisted outputs and nested code-mode operations through the
  shared kernel. Preserve provider counter deltas and attempt completeness;
  count outer code-mode results as context bytes without double-counting nested
  results.
- Retain HTTP calls in interpreter-fed heredocs as M4 `unclassifiable` operations.
  Recognize Python combined flags ending in `c`, Node `-p`/`--print`, Deno `eval`
  and Bun `-e`/`--eval`, alongside the existing inline-code forms. Written-script
  heredocs, shell comments and quoted data retain their negative controls.
- Validate every supplied `exception`, `proxy_purpose` and `rtk_log_find` field
  and require at least one review class with a witness. Invalid mixed records
  fail both CLIs and remain visible in `invalid_exceptions` at the export.
- Document RTK replay as a Linux binary on PATH self-reporting `rtk 0.50.0` that
  passes the five-exclusion probe. The gate does not verify the qualification
  receipt's binary hash. State in both READMEs that `ctx_sandbox_fetch` includes
  nested Codex code-mode shell fetches as well as context-mode sandbox fetches.
- Add failing-first controls and isolate the existing outside-checkout output
  test so it works with the required unit-local TMPDIR.
- Include the coordinator's `manifests/evidence.json` registrations for
  `examples/claude-native/workflows/{child-usage.mjs,test-child-usage.mjs,README.md}`,
  `tools/skill-usage/{skill_usage.py,README.md}` and the measurement tests
  `tests/{test_skill_usage.py,test_token_measurement.py}`.
- Retain the sanitized fixup receipt and commit handoff under
  `units/w3/measure/`.

## Evidence

**Synthetic fixtures:** the interpreter control initially produced 51 failures
across 54 carrier/input cases. The mixed-sidecar controls initially produced
27 failures through the export and both CLIs. Both fixes now pass, including
the existing written-script, comment, quoted-pattern and standalone review
controls. The interpreter cases assert one routed operation plus one unknown
HTTP operation yields a remote denominator of two and routed share of 0.5.

**Local integration:**

```sh
rtk python3 -m unittest tests.test_token_measurement tests.test_skill_usage tests.test_child_usage_suite
```

Final result: **128 tests, OK, exit 0**. This includes the existing Node
child-usage suite through its unittest wrapper and native RTK replay probes.
All runs used TMPDIR under `units/w3/measure/tmp` with
GIT_CEILING_DIRECTORIES set to the same directory. `rtk git diff --check`
returned exit 0. The [fixup receipt](units/w3/measure/fixup-receipt.md) retains
sanitized output excerpts and failed attempts, including the temporary-directory
fixture correction.

<!-- Coordinator: append the replayed head's validate.sh and full-suite results
here after publication replay. Do not copy builder or pre-replay SHA claims. -->

**Local measurement:** no new private transcript or token-savings run.
**Unchanged upstream tests:** not run in this fixup; local controls are integration
evidence. **Live provider execution:** none.

## SOTA sources

- mksglu/context-mode **v1.0.169**:
  [routing detector and subprocess handling](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L727-L804),
  [heredoc stripping](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L228-L229),
  and [UTF-8 accounting reference](https://github.com/mksglu/context-mode/blob/v1.0.169/src/session/extract.ts#L1060-L1069).
- rtk-ai/rtk **v0.50.0**:
  [native hook check](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs#L2940-L2952),
  [lexer](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/lexer.rs#L488-L526),
  and [pipeline/consumer rules](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1087-L1494).
  These identify the reference implementation, not the executable's build.
- openai/codex **rust-v0.157.1**:
  [usage protocol](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/protocol.rs#L2234-L2310),
  [call/output models](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/models.rs#L1060-L1165),
  and [code-mode emission test](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/tests/suite/code_mode.rs#L721-L760).
- ccusage/ccusage **v20.0.24**:
  [Claude message deduplication](https://github.com/ccusage/ccusage/blob/v20.0.24/rust/adapters/claude/src/daily.rs#L410-L523)
  and [Codex counter deltas](https://github.com/ccusage/ccusage/blob/v20.0.24/rust/adapters/codex/src/parser.rs#L153-L350).
- Official interpreter entrypoints:
  [Python stdin and command options](https://docs.python.org/3.14/using/cmdline.html#interface-options),
  [Node eval/print/stdin](https://nodejs.org/docs/latest-v24.x/api/cli.html),
  [Deno eval](https://docs.deno.com/runtime/reference/cli/eval/), and
  [Bun eval](https://bun.sh/docs/runtime).
- [Object.hasOwn present-field semantics](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/hasOwn)
  and [unittest.mock.patch.object](https://docs.python.org/3/library/unittest.mock.html#patch-object)
  for sidecar validation and test-only checkout isolation.

The local metric definitions remain the frozen
[#381 preregistration](evidence/artifacts/token-adoption-e2e-20260926/preregistration.json).
These adapters and controls are local integration work derived from the sources
above; they are not unchanged upstream tests.

## Residuals and not done

M4 counts statically visible call sites/attempts. Loops, dynamic code, external
scripts, aliases and nonliteral subprocess arguments require separate
observation. Interpreter heredocs and the listed eval/print forms are covered.
Interleaved or resumed code-mode spans without a persisted parent association
still need independent review. RTK replay checks the declared version and
exclusion behavior, without binary-hash attestation. The shared sandbox bucket
does not establish exclusive context-mode use. Semantic sidecar witnesses
remain reviewer evidence.

No live provider or private-corpus measurement was performed in this fixup.

## Recommended lane label

`lane:foundation`
