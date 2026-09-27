## Summary

This second PR-A fixup prevents visible HTTP calls missed by shell-text analysis
from inflating the #381 M4 gate. Executed-text analysis remains the primary
classifier of confirmed fetches. A separate possible-fetch counter supplies a
conservative denominator, while ignored interpreter stdin stays out of the
confirmed count.

The implemented measurement counters do not establish full PR-A acceptance.
The M1 eligibility and M15 infrastructure-error classification residuals remain.

## Changes

- In `examples/claude-native/workflows/child-usage.mjs`, select interpreter
  heredoc source by invocation: default stdin or `-` for Python/Node, supported
  shell stdin forms, and retained explicit stdin forms for other interpreters.
  Python command/module/script and Node eval/print/script invocations leave
  their heredoc as data. Analyze retained bodies separately so interpreter
  syntax cannot consume subsequent shell commands or written-script heredocs.
- Add `fetch_mentions_unconfirmed` for raw `HTTP_SCRIPT` matches that primary
  analysis did not account for. These are possible fetches, not confirmed ones.
  Report the count and both M4 shares in `m4` and `m4.by_carrier`, summing counts
  before recomputing aggregate shares.
- Preserve `routed_share = ctx_fetch_and_index / remote_fetches` over confirmed
  operations. Add `routed_share_lower_bound = ctx_fetch_and_index /
  (remote_fetches + fetch_mentions_unconfirmed)`, treating possible fetches as
  unrouted. **The #381 M4 >= 0.9 gate must read `routed_share_lower_bound`.**
  Possible fetches leave M4 status incomplete.
- Extend `tests/test_token_measurement.py` with failing-first ignored-stdin,
  parser-omission, body-boundary, raw-count and aggregate controls. Keep the
  existing interpreter positives and pattern/comment/written-script negatives.
- Update the workflow and skill-usage READMEs with the two shares, carrier
  counts, gate requirement and remaining static-analysis limits. Refresh
  workflows `SHA256SUMS` for the changed module and README.
- Retain dated errata, returned verification excerpts and current commit
  handoffs in `units/w3/measure/`. The earlier fixup receipt is unchanged.

## Evidence

**Synthetic fixtures:** ignored-stdin controls initially failed all 36 cases
across the three shell carriers. The first possible-fetch controls produced
26 missing-counter errors before implementation. Additional stdin-option and
body-boundary controls also failed before repair. Final M4-only run: **11 tests,
OK**. For each Python shift/Node apostrophe omission plus one routed fetch:

| Field | Returned value |
| --- | --- |
| Confirmed `remote_fetches` | 1 |
| `fetch_mentions_unconfirmed` | 1 |
| `routed_share` | 1 |
| `routed_share_lower_bound` | 0.5 |
| Status | incomplete |

Ignored stdin, shell comments, grep patterns and written scripts still produce
zero confirmed operations. Confirmed interpreter HTTP calls are not counted
again as possible fetches. This is static fixture analysis, not network traffic.

**Local integration:**

```sh
rtk python3 -m unittest tests.test_token_measurement tests.test_skill_usage tests.test_child_usage_suite
```

Returned **133 tests, OK, exit 0**, including the existing Node suite and native
RTK replay controls through unittest wrappers. The covering run used TMPDIR
under `units/w3/measure/tmp`, GIT_CEILING_DIRECTORIES set to that directory, and
PYTHONDONTWRITEBYTECODE=1. The full-suite retry used the unit-local
`.pytest_cache/tmp` directory, excluded by the existing scratch-copy fixture.

Workflow `sha256sum --check --strict SHA256SUMS` returned **14 entries OK,
exit 0**. Node syntax checking and `git diff --check` also returned exit 0.

`python3 scripts/validate.py` returned **exit 1**: SHA-256 and byte-count
mismatches for seven inventory paths, including three source/test files
unchanged from the supplied HEAD. The coordinator owns evidence registration;
this round does not edit `manifests/evidence.json`. No `validate.sh` exists in
this worktree. The native RTK replay above is local integration evidence,
not publication replay or a passing publication receipt.

The completed local `python3 -m unittest` retry returned **6,656 tests,
247 failures, 151 errors, 783 skipped, exit 1** in 633.902 seconds. This is
**not full-suite acceptance**. Its final summary was retained; intermediate
failure traces were truncated by the tool, so they are not a complete failure
inventory. Earlier attempts hit a context-mode timeout and scratch-copy
recursion, as recorded in the receipt. The supplied historical 6,633-test run
with two failures and 760 skips remains separate; no result is relabeled as
passing or used to attribute all failures to this fixup.
Retained errors include tests requiring temporary/private output outside every
repository, conflicting with the required unit-local TMPDIR. Those unrelated
policies and fixtures were not rewritten, and that observation is not a claim
to explain every failure.

The [second fixup receipt](units/w3/measure/fixup2-receipt.md) retains returned
summaries, earlier failed attempts and dated corrections.

**Local measurement:** no new private transcript or token-savings run.
**Unchanged upstream tests:** none; these are local integration controls.
**Live provider execution:** none.

## SOTA sources

- [#381 preregistration, M4](evidence/artifacts/token-adoption-e2e-20260926/preregistration.json#L2921-L2930):
  all remote fetches including nested/unclassifiable operations; routed rate
  at least 0.9. The lower-bound rule is the requested local extension to this
  contract, not an upstream parser feature.
- mksglu/context-mode **v1.0.169**, commit
  `589d8214d56740a28b5f7bf63167743d586b0b40`:
  [mandated detector reference, routing.mjs:788–795](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L788-L795),
  [heredoc stripping](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L228-L229),
  and [release](https://github.com/mksglu/context-mode/releases/tag/v1.0.169).
  Installed and pinned detector source matched during read-only research.
- Official interpreter semantics:
  [Python 3.13 interface options](https://docs.python.org/3.13/using/cmdline.html#interface-options),
  [Node v24.21.0 stdin](https://nodejs.org/docs/v24.21.0/api/cli.html#-),
  [Node eval](https://nodejs.org/docs/v24.21.0/api/cli.html#-e---eval-script),
  and [POSIX.1-2024 sh OPTIONS/STDIN](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/sh.html).
- Existing native RTK replay reference: rtk-ai/rtk **v0.50.0**,
  [hook check](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs#L2940-L2952),
  [lexer](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/lexer.rs#L488-L526),
  and [consumer rules](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1087-L1494).
  This identifies the reference implementation, not the installed binary build.

## Residuals and not done

- **M1 per-lane eligibility:** attempted/loaded/inserted counters do not compute
  successful opportunities among eligible tasks separately for every required
  lane. Those populations and semantic outcomes still require qualification.
- **M15 infrastructure errors:** attempted/succeeded/failed/unfinished MCP
  counters do not distinguish infrastructure errors from invoked-command
  nonzero exits, classify every ctx error, or reproduce new error classes.
  They do not establish the preregistered per-server error ceiling.
- **M4 static limits:** the lower bound protects against missed visible
  `HTTP_SCRIPT` matches. Data-only mentions can reduce it conservatively.
  Loops, dynamic imports/code, external scripts, aliases and nonliteral
  subprocess arguments still require independent observation. Neither share
  certifies arbitrary runtime behavior.
- **Publication acceptance:** evidence registration, coordinator replay and a
  passing publication validation receipt are not established here. Historical
  full-suite failures reported in `tests.test_pre_commit_gate` and
  `tests.test_secret_path_guard` are not silently replaced or attributed to this
  fixup.
- RTK binary-hash attestation, live provider/E2E measurement, semantic sidecar
  witness review and ambiguous interleaved/resumed code-mode associations
  remain outside this fixup. The shared sandbox bucket does not establish
  exclusive context-mode use.

## Recommended lane label

`lane:foundation`
