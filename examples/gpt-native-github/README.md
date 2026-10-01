# Native GPT tasks in GitHub

This example uses the maintained [Codex Action v1.12](https://github.com/openai/codex-action/blob/86365089eb2b84e0a8fb0717b304f8bdcb13b20e/README.md)
and native Codex CLI 0.159.2 for one frozen PR review or research packet. It stays
outside `.github/workflows/` until the intended runner and endpoint qualify.
The [current decision](../../docs/decisions/2026-09-30-gpt-lifecycle-convergence.md)
distinguishes local native review, upstream unit tests and hosted execution.

Use `workflow.yml`, `task.md`, `sources.json` and `result.schema.json` together.
The workflow checks out its dispatch revision under `controls/` and the frozen
inspection head under `subject/`. Absolute prompt/schema paths and
`TASK_CONTROL_DIR` keep the task controls separate from the inspected revision,
including heads that predate this example. Select a reviewed dispatch revision
whose control files are present. The task reads the selected subject and sources. A fresh
`codex-home` supplies neither workstation MCP registrations nor installed skills;
include necessary task material in the controls checkout. Refresh the source packet
through the existing research/convergence lane before freezing a new task.

Set these repository variables and the endpoint's existing bearer credential in
GitHub's native settings, then copy the example workflow into `.github/workflows/`:

| Setting | Contract |
| --- | --- |
| `GPT_NATIVE_ACTION_ENABLED` | `true` enables manual dispatch after qualification. |
| `RESPONSES_ENDPOINT` | Complete existing Responses POST URL, including `/v1/responses`. |
| `CODEX_REQUEST_MODEL` | Explicit endpoint-supported route; native task workers request `max`. |
| `RESPONSES_BEARER_KEY` secret | Existing credential accepted by that endpoint; the Action passes it to its proxy over stdin. |

The example uses a fresh hosted Linux runner. This host's loopback OmniRoute URL
is reachable only from a suitably located runner; this task installs no runner
and exposes no gateway. Qualify reachability, bearer acceptance, requested model,
effort and structured output together before enabling hosted execution. Native
read-only confinement is not a credential-isolation claim.

The runner installs only the pinned RTK release binary in its temporary directory,
verifies the upstream archive SHA-256, and adds that directory to the job PATH.
It changes no workstation hook or global configuration. Bootstrap commands run
natively before RTK exists. The pinned release is [RTK v0.50.0](https://github.com/rtk-ai/rtk/tree/1d87b8e719ce0a50c223cd93ca64dd16921f9aec),
with its [published checksums](https://github.com/rtk-ai/rtk/releases/download/v0.50.0/checksums.txt).

Dispatch with one bounded `objective` and full `head_sha` and `base_sha` values. The native task verifies the
actual revision and merge-base. The workflow has read-only repository permissions,
no automatic event, no PR posting or merge, a 20-minute bound and a seven-day
structured-result artifact. It does not cancel another run on a new dispatch:
native interruption and provider cancellation require separate evidence.

The Action's only output is `final-message`; `output-file` captures the bounded
answer. `--json` would emit native events into the job log, not a usage artifact.
This example does not request that stream or upload raw conversations. A result
schema and zero process exit still require independent task checks. Missing
usage remains unknown; do not generate counters in the answer or add resumed
thread totals, cached-input subsets, reasoning-output subsets or gateway totals.

Validate a proposed copy with the existing native workflow analyzer:

```sh
rtk zizmor --offline --no-config --strict-collection --no-progress examples/gpt-native-github/workflow.yml
```

Source contracts: [Action inputs](https://github.com/openai/codex-action/blob/86365089eb2b84e0a8fb0717b304f8bdcb13b20e/action.yml),
[protected arguments and output handling](https://github.com/openai/codex-action/blob/86365089eb2b84e0a8fb0717b304f8bdcb13b20e/src/runCodexExec.ts),
[Codex CLI flags](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/exec/src/cli.rs),
[checkout v7.0.1](https://github.com/actions/checkout/tree/3d3c42e5aac5ba805825da76410c181273ba90b1)
and [artifact upload v7.0.1](https://github.com/actions/upload-artifact/tree/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a).
