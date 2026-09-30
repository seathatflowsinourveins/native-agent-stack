---
name: omniroute-runtime-worker
description: Delegate a bounded foundation engineering task from Claude to the native Codex SDK worker through the selected OmniRoute gateway.
---

Read `examples/omniroute-codex-sdk/README.md` for invocation and lifecycle details.
Use this project's `examples/omniroute-codex-sdk/worker.py` through Claude's native
Bash tool. The primary route is `cx/gpt-6.1-sol-max`, with native Max effort.
The coordinator retains its native Claude account and model route.

Give a writing worker its own worktree, bounded file ownership, an executable
acceptance condition and an existing private Codex home. Tell it other workers
are present and that it must preserve their edits. Feed the task on stdin:

```sh
rtk uv run --locked --script examples/omniroute-codex-sdk/worker.py \
  --workspace "$WORKER_PROJECT" \
  --codex-home "$PRIVATE_WORKER_HOME" \
  --timeout 300 \
  --prompt -
```

Use the selected gateway's native Responses lane at loopback port 20128. Keep
native caches, tools and project skill discovery intact; load only task-relevant
skill bodies. Install selected skills through the existing runtime-worker skill
recipe, rather than importing the entire catalog into the task prompt. Optional
MCP services require their own configuration and acceptance.

Keep returned thread IDs private and use `--resume` for continuation. The latest
thread usage snapshot includes previous turns; count it once. A deadline invokes
native interruption and child cleanup; remote termination and unknown provider
usage remain unverified. Do not automatically replay a failed writing task.

Use explicit `--model cx/gpt-6-astra-max` for consequential architecture,
conflicting primary evidence, or a failure unresolved after one bounded Sol
repair. Record that trigger and the acceptance result. The separate Claude SDK
bridge remains a trial after its gateway errors; it is not the primary worker.

Sources: [Claude native project skills](https://code.claude.com/docs/en/skills)
and [official Codex SDK, rust-v0.159.2](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python).
Functional scope and retained failures are recorded in
`docs/decisions/2026-09-30-omniroute-runtime-workers.md`.
