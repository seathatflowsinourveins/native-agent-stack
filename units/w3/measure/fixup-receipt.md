# PR-A narrow fixup receipt — 2026-09-27

Scope: the repair-verification findings for unit measure only. The supplied
worktree did not contain `units/w3/measure`; this directory retains the requested
handoff and sanitized verification record. Historical receipts are unchanged.

## Source review

- Extend the existing detector, using mksglu/context-mode **v1.0.169**,
  [`hooks/core/routing.mjs:228–229,727–804`](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L727-L804).
  Its heredoc stripping is a routing blind spot; the #381 M4 denominator must
  retain statically visible interpreter HTTP operations as unclassifiable.
- Interpreter semantics: [Python command line](https://docs.python.org/3.14/using/cmdline.html#interface-options),
  [Node eval/print/stdin](https://nodejs.org/docs/latest-v24.x/api/cli.html),
  [Deno eval](https://docs.deno.com/runtime/reference/cli/eval/), and
  [Bun runtime eval](https://bun.sh/docs/runtime).
- Present-field validation: [Object.hasOwn](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/hasOwn)
  distinguishes absent fields from present null/undefined values. Review classes
  retain the existing #381 contract and digest-bound sidecar format.
- RTK reference: rtk-ai/rtk **v0.50.0**, `src/main.rs:2940–2952`,
  `src/discover/lexer.rs:119–135,488–526`, and
  `src/discover/registry.rs:1087–1345,1451–1494`.
  The installed command self-reports `rtk 0.50.0`; that string is not build identity.
- Codex sandbox normalization retains the existing adapter and openai/codex
  **rust-v0.157.1** [code-mode emission test](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/tests/suite/code_mode.rs#L721-L760).
  Both READMEs now explicitly describe the shared `ctx_sandbox_fetch` mapping.
- Unit-local test isolation uses the standard-library
  [unittest.mock.patch.object](https://docs.python.org/3/library/unittest.mock.html#patch-object)
  context manager. No runtime output-path policy changes.

The installed skill catalog supplied context-mode, diagnosing-bugs, tdd,
search-first (inline research), and verification-before-completion. Existing
measurement/test interfaces cover this bounded repair; no new dependency or
orchestration mechanism was introduced. Public reference pages were fetched
through context-mode. The context-mode v1.0.169 `CHANGELOG.md` URL returned HTTP
404; the pinned routing source, rather than that unavailable changelog, supports
the detector comparison.

## Dated corrections / anti-patterns

- Interpreter-fed heredocs and supported quoted interpreter code are executable
  input. Treating them as shell data understated M4's denominator. Verification:
  positive controls at `measureTranscript`, alongside existing data-only controls.
- A valid review class must not mask a malformed sibling class. Verification:
  mixed-record controls at the measurement export and both sidecar CLIs.
- RTK version/probe acceptance is a capability check, not proof of the qualified
  binary hash. The documentation will state the observed scope of the gate.
- Code-mode shell fetches need an explicit documented bucket mapping if the
  existing `ctx_sandbox_fetch` field is retained.
- The existing output-path test assumed its temporary directory was outside the
  checkout. With the required unit-local TMPDIR it failed (`2 != 0`). A test-only
  checkout root now makes output and checkout siblings. An initial missing mock
  import produced `NameError`; adding the standard-library import corrected it.
  Verification: the final covering-module run below exercises both permitted
  output and inside-checkout refusal.

## Evidence

All test runs used `TMPDIR` and `GIT_CEILING_DIRECTORIES` set to
`$PWD/units/w3/measure/tmp`, with `PYTHONDONTWRITEBYTECODE=1`. Temporary fixtures
were cleaned up. Runtime observations: Python 3.13.15, Node v24.21.0, and a
binary on PATH self-reporting `rtk 0.50.0`.

### Synthetic fixtures: failing first

Command:

```sh
rtk python3 -m unittest tests.test_token_measurement.TokenMeasurement.test_m4_interpreter_heredocs_and_quoted_code_stay_in_denominator
```

Returned before the M4 fix, exit 1:

```text
AssertionError: 0 != 1
FAILED (failures=51)
```

The 54 cases cover 18 interpreter inputs across Bash, ctx shell and ctx batch
carriers. After the fix all pass: one routed fetch plus each interpreter fetch
produces `unclassifiable=1`, `remote_fetches=2`, both shares `0.5`, and status
`incomplete`. The earlier data-heredoc/comment/grep controls also pass.

Command:

```sh
rtk python3 -m unittest tests.test_token_measurement.TokenMeasurement.test_mixed_sidecar_records_validate_every_present_class tests.test_skill_usage.CodexLanes.test_both_cli_sidecars_reject_malformed_classes_in_mixed_records
```

Returned before the validation fix, exit 1:

```text
AssertionError: 0 != 1
AssertionError: 0 != 2
AssertionError: True != False
Ran 2 tests in 5.739s
FAILED (failures=27)
```

The controls cover valid combinations, misspelled enums, present null values,
empty/malformed/duplicate part reviews and a missing class. After the fix,
invalid records are rejected by both CLIs and cannot grant an exception through
the measurement export. The standalone log/find controls also pass.

### Local integration: covering modules

Command, with the environment described above:

```sh
rtk python3 -m unittest tests.test_token_measurement tests.test_skill_usage tests.test_child_usage_suite
```

Attempts retained:

| Attempt | Returned result | Correction |
| --- | --- | --- |
| Initial covering run | 128 tests, exit 1, one failure: output path refused | Isolate the test checkout under unit-local TMPDIR |
| First isolation run | 128 tests, exit 1, one error: `NameError: name 'mock' is not defined` | Import `unittest.mock` |
| Final covering run | 128 tests, exit 0 | All covering controls passed |

Final returned summary:

```text
Ran 128 tests in 20.284s

OK
```

This includes the existing Node child-usage suite via its unittest wrapper and
the native RTK replay integration controls. `rtk git diff --check` also exited 0.

### Evidence boundaries

- **Synthetic fixtures:** the transcript/sidecar controls above, including the
  exact counter expectations; they do not represent actual network requests.
- **Local integration:** the covering-module run, native RTK hook-check probes,
  both sidecar CLIs and whitespace verification.
- **Local measurement:** no new private transcript corpus or token-savings run.
- **Unchanged upstream tests:** not run in this fixup; local controls do not
  substitute for upstream acceptance.
- **Live provider execution:** none. No model, broker or credential store was used.

## Residual scope

M4 remains a static detector: dynamic code, external scripts, aliases and
nonliteral subprocess commands need independent observation. The RTK gate does
not establish binary-hash identity. `ctx_sandbox_fetch` intentionally retains
the shared context-mode/Codex mapping, now documented in both READMEs. This
receipt records covering-module acceptance; the coordinator records publication
acceptance from the replayed head's `validate.sh` and full suite.
