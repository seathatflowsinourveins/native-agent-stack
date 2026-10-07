# Native gateway token-feature evaluation, 2026-10-05

[Decision, inventory, alternatives and primary source pins](../../../docs/decisions/2026-10-05-gateway-token-features.md). This is a native promptfoo comparison of text returned by OmniRoute's request-local compression preview. No custom runner, provider callback, rebuilt vendor runtime or shared setting change is introduced.

Every preview measurement, model-call result, table and usage comparison in this artifact is **input-preprocessing evidence only**. None qualifies integrated worker routes, an enabled gateway pipeline or output style. A3's option 1 remains with the gateway owner for an isolated route, settings-hash readback and scoped usage/retry observations.

The 24 preview requests use eight synthetic fixtures across raw/RTK/Caveman, with enabled fidelity/risk gates. The native preview returns flattened role-prefixed text, not a restored chat/Responses body. Its original/compressed strings were frozen as static promptfoo variables before inference. [plan.json](plan.json) fixes the task/oracle/control contract; [freeze.json](freeze.json) records the hash bundle. [preview-metrics.json](preview-metrics.json) retains every safety result and engine estimate. Five RTK cases fell back, including a URL validation failure. Caveman returned original text for all eight cases. Failure preservation prevents a global adoption inference.

Native commands (owned-cache prefix/state/output, omitted from public paths):

```sh
rtk npm install --global --include=optional --prefix <owned-cache> promptfoo@0.123.1
rtk proxy omniroute --base-url http://127.0.0.1:20128 --output json --quiet --no-color compression preview --file fixtures/<case>-<arm>.json
rtk proxy <owned-cache>/bin/promptfoo eval --config promptfoo.json --repeat 2 --max-concurrency 1 --no-cache --no-share --no-write --no-table --no-progress-bar --output <private-results.json>
```

Promptfoo native pass/failure smoke fixtures returned expected exits 0/100. The retained first comparison exited 100: 29 exact passes, 19 failures across 48 actual HTTP-200 calls. Its rendered output can include reasoning summaries, and the gate question lacked an explicit answer label. The separately [frozen qualification](qualification/plan.json) uses the native raw.output_text assertion and explicit label; four tool/four user-prose fixtures cover the eligible Caveman role. It made 48 new actual calls and passed all exact final-answer checks, exit 0. No frozen first result is relabelled passed.

| Static-input qualification arm | Exact passes | Native input | Native output | Native total | Cached input subset | Reasoning output subset |
| --- | --- | --- | --- | --- | --- | --- |
| Raw | 16/16 | 17950 | 1575 | 19525 | 5760 | 1331 |
| RTK | 16/16 | 13150 | 1684 | 14834 | 4608 | 1440 |
| Caveman | 16/16 | 17758 | 1535 | 19293 | 6912 | 1291 |

The [sanitized receipt](receipt.json), [pilot calls](pilot-calls.json) and [qualification calls](qualification/calls.json) retain every call's returned native usage and failed conditions. Raw native model outputs remain private. All 96 benchmark calls returned complete terminal usage fields, including zero cache writes. Missing preparation/review/recovery and backend retry counters remain unknown; terminal call usage is not complete-task coverage. Cached input and reasoning are subsets and are counted once. Preview estimates use a separate tokenizer boundary. No unchanged vendor test suite, complete-task savings, enabled integrated stage, outputstyle or worker-home acceptance is inferred. An owner-isolated route plus complete usage/retry observation remains required.

A3's separately [frozen native transformVars phase](transform-vars/plan.json) runs from the repository root, using the same qualification provider, prompts, payloads and oracles. Promptfoo's [inline transform and process shim](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/util/transform.ts#L135-L149) invokes the upstream [OmniRoute preview CLI](https://github.com/diegosouzapw/OmniRoute/blob/23a11484862b3bb589a55e85b00e4ac53ffeb234/bin/cli/commands/compression.mjs#L137-L151). The native CLI handles its own authentication; lane code reads no credential value/file. The transform validates the returned text against the prior qualification's SHA256 before direct inference. It is supported native configuration, with no standalone runner or provider callback.

This new phase exited 0: **48/48 exact answers**, 24 distinct preview invocations, 300947 ms. Promptfoo [prepares variables before repeat expansion](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/evaluator.ts#L4833-L4840), so 24 preview calls are reused across 48 inference calls. [Preview metrics](transform-vars/preview-metrics.json) and [calls](transform-vars/calls.json) retain both scopes. All previews were valid and reference-matching; this does not prove they avoided fallback/no-op.

| Native-transform input-preprocessing arm | Exact passes | Native input | Native output | Native total | Cached input subset | Reasoning output subset |
| --- | --- | --- | --- | --- | --- | --- |
| Raw | 16/16 | 17950 | 1646 | 19596 | 2304 | 1402 |
| RTK | 16/16 | 13150 | 1588 | 14738 | 1152 | 1344 |
| Caveman | 16/16 | 17758 | 1516 | 19274 | 4608 | 1272 |

All **144 distinct model calls** across the three phases retain terminal usage; preparation/review/recovery and backend retries stay unknown. The native result export masks its artifact hash fields. The receipt preserves those masks and separately derives hashes from retained artifact text against the frozen configuration; it does not invent native returned hashes. Inference headers report gateway version 3.8.51 and compression `off; source=off`, separately from installed canary source metadata. Option 1's owner-isolated integrated route remains pending.
