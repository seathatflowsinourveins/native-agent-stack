# Native skills and advisory source review

This opt-in practice combines the upstream TypeSafe skill, existing Promptfoo
HTTP/echo providers and native Codex/Claude evidence-review roles. It selects
useful semantic assistance without replacing native accounts, worker models,
deterministic rules or execution. The [selection record](../../docs/native-skill-practice-20260921.md)
and [manifest](../../catalogs/landscape/native-practice.json) distinguish source
review, installation, returned native results and remaining limits.

## Install only the selected skills

Use the upstream `skills` installer for both clients; do not additionally install
the TypeSafe marketplace plugin for the same skill:

```sh
npx skills add typesafe-ai/skills --skill typesafe-ai --agent codex claude-code --global
npx skills add openai/skills --skill gh-fix-ci security-best-practices --agent codex claude-code --global
```

For a project-owned copy, omit `--global` and use `--copy`. Preserve existing
skills, native sign-in and configuration. The recorded source commits and file
hashes in the manifest identify the reviewed versions; a later installer result
requires a fresh source comparison. Installer risk badges are not native
acceptance or a security certification.

Use the [Claude role](../../examples/claude-native/agents/semantic-evidence-reviewer.md)
or [Codex role](../../examples/codex-native/agents/semantic-evidence-reviewer.toml)
only for a semantic evidence task. Place the selected definition in the project's
native agents directory. Both inherit model/effort. Claude declares the TypeSafe
skill and has a direct-read fallback for headless invocation. Codex explicitly
loads the skill and uses native read-only source access with an explicit directory.
No service credential belongs in a worker prompt or role definition.

The coordinator supplies authorized TypeSafe results, with source references and
the deterministic availability decision. The worker recovers source evidence,
checks entity/time/scope and can correct the advice. Existing no-tools report
workers may consume already qualified inputs; installing a skill does not enable
new tools in that lane. The exact-only scout remains separate.

## Reproduce the bounded diagnostic

The provider/gate/response adapters and six contract tests were reused unchanged
from the earlier agent-lab TypeSafe pilot. `cases.json` preserves that 16-case
fixture for its contract checks; it is not rerun as this task's fresh inference.
`catalog-cases.json` is a separate eight-case diagnostic built from actual retained
catalog excerpts and the pinned upstream skill. An independent reviewer labeled
it before inference; two ambiguous claims were clarified before labels were frozen
at SHA-256 `7cc28c50afb9842de3d8dc923e80159bf99d0f0e9acd643684a99b61b3ad3a40`.
No expected label is sent to TypeSafe. C6's future-availability fields are explicitly
illustrative gate inputs, not historical acquisition evidence.

The retained Promptfoo run compacted the JSON-valued C1/C2 source strings before
rendering the provider prompt. Their parsed JSON is equal to the frozen source;
the bytes differ. The result separates frozen-excerpt hashes, actual rendered
source hashes and the earlier summary's trimmed-excerpt hashes. The other six
source strings are unchanged. This provenance correction does not alter labels,
responses or the original private report.

Use the selected Promptfoo 0.123.1 and a supported Node runtime. From this folder:

```sh
node --test test-contract.cjs
REQUEST_TIMEOUT_MS=15000 timeout 180s promptfoo eval -c promptfooconfig.yaml \
  --env-file /private/path/to/this-project.env \
  --no-cache --max-concurrency 1 --repeat 1 --no-share --no-write --no-table \
  --output /private/path/to/results.json
```

Disable Promptfoo telemetry/update checks on a new PC, as the adopted native
launcher does. Supply only that project's authorized `TYPESAFE_API_KEY`. The
upstream provider has zero retries; the request and whole-process deadlines are
separate. Review raw results privately before publishing a sanitized receipt.

The [fresh result](typesafe-result.json) records TypeSafe `jev-1.13.0` at **7/8**
frozen labels versus **3/8** for weak literal containment. It made eight uncached
requests with zero service errors, 4,846 input and 375 output tokens. Median
observed provider latency was 171.5 ms. Promptfoo exit 100 preserves the one
TypeSafe and five comparator assertion failures; it is not a clean evaluation pass.
C4 returned `contradicted` where the frozen label was `insufficient`. Do not change
the labels after seeing the model output. Native source review must retain that
disagreement and its possible interpretation rather than promote the universal
claim. C6 remains rejected by the availability gate despite semantic support.

The [worker packet](worker-packet.json) omits oracle labels and carries the original
source excerpts and advisory probabilities. Native worker results are assisted
source verification, not an independent matched model benchmark. No general
accuracy, latency, token savings, trading value or universal SOTA claim follows
from these small selected tests. Current native results and failed attempts are
recorded in the selection record and its linked receipt.
