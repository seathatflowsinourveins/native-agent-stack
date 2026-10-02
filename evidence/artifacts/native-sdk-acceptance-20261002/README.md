# Native SDK task and source-suite evidence — 2026-10-02

This bundle publishes bounded results from actual target SDK tasks and separate
unchanged upstream source tests. The [registered receipt](../../receipts/native-sdk-acceptance-20261002.json)
binds every public attachment. It does not close the full foundation resolution.

| Observation | Outcome | Evidence scope |
| --- | --- | --- |
| Claude SDK 0.2.163, native CLI 2.1.287, original Quickstart bug-fix task | **FAILED**: three oracle passes, one error despite successful SDK termination | Actual model/tool execution; the missing `None` guard still crashes |
| Codex SDK/native CLI 0.160.0, separate informed repair | **PASSED**: all four unchanged oracle cases | Narrow integration task; receives the concrete Claude failure and adds only the `None` guard |
| Claude SDK 0.2.163 default source suite | **PASSED**: 1,587 passed, six skipped | Unchanged upstream command in a private legacy-host environment; separate from target/provider acceptance |
| OpenHands SDK 1.50.1 default `tests/sdk` suite | **PASSED**: 6,621 passed, seven skipped, 12 xfailed, 83 warnings | Unchanged upstream command after a preserved 16-failure environment attempt; no OpenHands provider-task acceptance |

`claude-trial.json`, `codex-trial.json` and `source-suites.json` are explicitly
derived projections of frozen private records, with subsequent independent
review verdicts and original byte/hash bindings. The coordinator observed
execution, native exits and process samples; reviewers checked retained outputs,
source and artifact bindings without recreating those executions. A hash proves
byte identity, not that a new execution occurred. In particular, the successful
oracle output also occurs in the historical positive control.

The two candidate files are exact resulting bytes. `codex-oracle.stderr.txt` is
exact native output. `claude-oracle.stderr.txt` preserves native output except
that the two private trial-root paths become `<owned-trial>`; its public hash
differs from the bound original. `native-suite-excerpts.json` selects one exact
native summary line from each source-suite attempt and records its original
line number. No raw conversation, account data or machine-specific active
configuration is published. The complete permitted captures stay private.

The frozen [four-case local oracle](../../../examples/native-sdk-acceptance/claude-quickstart/test_utils.py)
has SHA256 `7f555898a5cef064bc72121a9d123f61d7161ad573c2117b342ece316eecb1d5`.
It was kept outside the worker's writable candidate directory. Its native Codex
read-only sandbox enforcement probe observed a file-create denial (`EROFS`) and
socket-create denial (`EPERM`). That verifier observation does not establish a
negative permission test for either generation task. Before/after exact client
process-name samples do not establish complete descendant or host lifecycle.

Native token counters retain their original scopes. Claude top-level and
per-model usage overlap; thinking/cache details must not be added again. Codex
cached input and reasoning output are subsets, and absent cache-write usage is
normalized to zero by the selected SDK. Codex's requested model/effort are known;
resolved model/provider identity and cost were not returned. Different tasks,
prompts and starting states preclude a model-efficiency comparison here.

The OpenHands failed attempt had 16 failures: 13 depended on current model
metadata and three on temporary-path topology/length. One bounded environment
repair removed the forced local LiteLLM map and mounted the owned temporary
directory at `/tmp`. Source/tests/lock remained unchanged. Public-network access
was shared, including host loopback, for upstream metadata/plugin checks; exact
fetched model-map bytes were not retained. Default stress/ACP-live exclusions,
seven optional ToolShield skips and all warnings remain limitations. A prior
repair note cited the wrong LiteLLM filename; independent inspection corrected
it to `litellm/litellm_core_utils/get_model_cost_map.py`, retaining both records.

The Claude source suite's five collection-level skip identities are inferred
from source and absent dependencies; they were not enumerated in the retained
native output. One zopfli test identity was printed. Source tests, synthetic
fixtures and actual useful work remain distinct evidence classes.

Remaining gates include Claude useful-task success, the OpenHands FACTS provider
task, the separately owned Codex default source suite, researcher/reviewer roles,
resume/recovery, selected MCP integration, full lifecycle, target token routing
and comparative efficiency. Current release currency is also separate: these
historical Claude tasks used 2.1.287; preparation for a later role trial follows
the configuration owner's 2.1.288 reconciliation.

## SOTA sources

- Claude SDK [`query` and result types at v0.2.163](https://github.com/anthropics/claude-agent-sdk-python/tree/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7), including [upstream test CI](https://github.com/anthropics/claude-agent-sdk-python/blob/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/.github/workflows/test.yml#L18).
- Codex [TypeScript SDK at rust-v0.160.0](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/sdk/typescript), including [`Turn` and its supported run options](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/typescript/src/thread.ts).
- OpenHands [default SDK CI at v1.50.1](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/.github/workflows/tests.yml#L110), [selected source tree](https://github.com/OpenHands/software-agent-sdk/tree/1e1390acc8788346ba4804c34323284009bf3f5e) and [optional ToolShield guard](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/tests/sdk/security/test_toolshield_llm_analyzer.py#L29).
- Existing [acceptance evidence policy](../../../docs/acceptance-evidence-policy.md) and [native result receipt format](../../receipts/native-returned-results-20260921.json).
