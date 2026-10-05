# Native gateway token-feature evaluation, 2026-10-05

[Decision, inventory, alternatives and primary source pins](../../../docs/decisions/2026-10-05-gateway-token-features.md). This is a native promptfoo comparison of text returned by OmniRoute's request-local compression preview. No custom runner, provider callback, rebuilt vendor runtime or shared setting change is introduced.

The 24 preview requests use eight synthetic fixtures across raw/RTK/Caveman, with enabled fidelity/risk gates. The native preview returns flattened role-prefixed text, not a restored chat/Responses body. Its original/compressed strings were frozen as static promptfoo variables before inference. [plan.json](plan.json) fixes the task/oracle/control contract; [freeze.json](freeze.json) records the hash bundle. [preview-metrics.json](preview-metrics.json) retains every safety result and engine estimate. Five RTK cases fell back, including a URL validation failure. Caveman returned original text for all eight cases. Failure preservation prevents a global adoption inference.

Native commands (owned-cache prefix/state/output, omitted from public paths):

```sh
rtk npm install --global --include=optional --prefix <owned-cache> promptfoo@0.123.1
rtk proxy omniroute --base-url http://127.0.0.1:20128 --output json --quiet --no-color compression preview --file fixtures/<case>-<arm>.json
rtk proxy <owned-cache>/bin/promptfoo eval --config promptfoo.json --repeat 2 --max-concurrency 1 --no-cache --no-share --no-write --no-table --no-progress-bar --output <private-results.json>
```

Promptfoo native pass/failure smoke fixtures returned expected exits 0/100. The retained first comparison exited 100: 29 exact passes, 19 failures across 48 actual HTTP-200 calls. Its rendered output can include reasoning summaries, and the gate question lacked an explicit answer label. The separately [frozen qualification](qualification/plan.json) uses the native raw.output_text assertion and explicit label; four tool/four user-prose fixtures cover the eligible Caveman role. It made 48 new actual calls and passed all exact final-answer checks, exit 0. No frozen first result is relabelled passed.

| Qualification arm | Exact passes | Native input | Native output | Native total | Cached input subset | Reasoning output subset |
| --- | --- | --- | --- | --- | --- | --- |
| Raw | 16/16 | 17950 | 1575 | 19525 | 5760 | 1331 |
| RTK | 16/16 | 13150 | 1684 | 14834 | 4608 | 1440 |
| Caveman | 16/16 | 17758 | 1535 | 19293 | 6912 | 1291 |

The [sanitized receipt](receipt.json), [pilot calls](pilot-calls.json) and [qualification calls](qualification/calls.json) retain every call's returned native usage and failed conditions. Raw native model outputs remain private. All 96 benchmark calls returned complete terminal usage fields, including zero cache writes. Missing preparation/review/recovery and backend retry counters remain unknown; terminal call usage is not complete-task coverage. Cached input and reasoning are subsets and are counted once. Preview estimates use a separate tokenizer boundary. No unchanged vendor test suite, complete-task savings, enabled integrated stage, outputstyle or worker-home acceptance is inferred. An owner-isolated route plus complete usage/retry observation remains required.
