# Runtime workers for native Claude

The retained foundation coding path is native Claude → native Bash → the
official Codex SDK → the selected OmniRoute Responses lane. Use
`cx/gpt-6.1-sol-max` with native Max effort for the primary worker. Use
`cx/gpt-6-astra-max` explicitly for consequential architecture, conflicting
primary evidence or a failure remaining after one bounded Sol repair; retain
the trigger and result. The
[September 30 decision](../../docs/decisions/2026-09-30-omniroute-runtime-workers.md)
and [native Claude callsite receipt](../../evidence/receipts/omniroute-claude-callsite-20260930.json)
define the accepted scope: one bounded read-only caller path and the separately
recorded direct SDK lifecycle. The comparative SDK selection remains unresolved.

## Dispatch and retain the actual result

Give each worker a task contract containing the exact base, owned files,
relevant sources, acceptance command, deadline and output destination. Give a
writer its own worktree and private worker home. Supply all three paths below
explicitly: the executable's defaults do not enforce this ownership policy.
Use the existing [project dispatcher](../../.claude/skills/omniroute-runtime-worker/SKILL.md)
from Claude and the [supported SDK recipe](../../examples/omniroute-codex-sdk/README.md)
to prepare the private home; keep native sign-ins native.

```sh
rtk uv run --locked --script examples/omniroute-codex-sdk/worker.py \
  --workspace "$WORKER_PROJECT" \
  --codex-home "$PRIVATE_WORKER_HOME" \
  --native-result "$PRIVATE_NATIVE_RESULT" \
  --prompt "$WORKER_TASK"
```

`WORKER_PROJECT` names the owned task worktree; `PRIVATE_WORKER_HOME` names its
prepared private state; `PRIVATE_NATIVE_RESULT` names a new private result file.
The worker retains that file with mode `0600`. Inspect the original command
exit and test output, and independently observe the resulting artifact. The
compact caller summary alone cannot establish acceptance. Retain failed and
interrupted attempts. Count the latest cumulative native thread snapshot once;
keep parent usage, gateway estimates and unknown provider usage separate.

Source: the [official SDK](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python),
its [child transport configuration](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py),
and the [acceptance evidence policy](../../docs/acceptance-evidence-policy.md).

## Select another runtime or extension by its task

| Task | Selected path or candidate | Acceptance boundary |
| --- | --- | --- |
| Foundation coding and repair | Official Codex SDK through OmniRoute | Retained bounded caller/lifecycle evidence; broader writing and extension coverage need their own acceptance. |
| Consequential judgment | Explicit Astra/Max through the same native SDK | Record why this stage is needed and its result. |
| OpenHands sandboxed execution | [Existing OpenHands O1 blueprint](openhands/README.md) | Resolve the owned target and installation prerequisites; pass its isolation and dispatch gates before model execution. |
| OpenHands terminal or editor interaction | Official OpenHands CLI/ACP, separate candidate | Released CLI 1.16.0 pins SDK 1.21.0; it does not qualify the blueprint's SDK 1.49.6 or current SDK 1.50.0. |
| Alternate extensible workers | Pi, OpenCode, Goose, oh-my-pi | Source review; retain the current Pi owner's conditional trial. A model label or provider configuration is insufficient acceptance. |
| Claude review command or standardized editor transport | Official Codex for Claude plugin; maintained Codex ACP adapter/acpx | Independent interfaces with separate gateway/authentication/lifecycle acceptance. |
| Task skills | [Pinned runtime skill trial](skills/README.md) | Select relevant skills, verify discovery and actual invocation; its broad inventory is a trial. |
| MCP, plugins, hooks, memory and observation | The selected native capability's existing recipe | A shared `SKILL.md` format does not install or qualify these separate runtime integrations. |
| Claude Agent SDK through the translated gateway | [Existing bridge trial](../../examples/claude-runtime-sdk/README.md) | Recorded provider attempts failed; the bridge remains unqualified. |

The [dated landscape review](../../docs/runtime-worker-landscape-20260930.md)
and [machine-readable catalog](../../catalogs/foundation/runtime-worker-landscape-20260930.json)
name current repositories, immutable pins, supported entry points and the test
that would change each disposition. Full landscape coverage belongs in these
on-demand references, rather than every worker's starting prompt.

## Enhance the retained worker first

For the next extension acceptance, choose one task and one relevant pinned skill
from the existing manifest. Freeze the positive task, adjacent negative,
unchanged task oracle and required invocation evidence. Compare the retained
worker with the same worker plus that extension. Keep the skill read and native
result private, publish sanitized locators/results, retain failures and usage,
and qualify only the demonstrated role. The existing
[native skill lifecycle](../../adoption/skills/lifecycle.md) and
[upstream skill evaluation guidance](https://developers.openai.com/blog/eval-skills)
supply the procedure. This guide does not declare a measured extension winner.

For OpenHands, preserve the existing frozen task, image, arms, grading controls
and O1 topology. Current SDK 1.50.0 is a source-reviewed upgrade candidate; its
[release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.50.0)
does not transfer the pinned blueprint's acceptance to this host. Resolve that
owned revision with the live runtime session before changing it.

Use the existing native component recipes for context, caching, isolation and
observation. Qualify optional services only for tasks needing them. Installation,
version/help, unchanged upstream tests, local integration fixtures and live
provider execution remain separate evidence levels.
