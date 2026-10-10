---
name: omniroute-runtime-worker
description: Delegate a bounded foundation engineering task from Claude to the native Codex SDK worker through the selected OmniRoute gateway.
---

Read `examples/omniroute-codex-sdk/README.md` for invocation and lifecycle details.
Use this project's `examples/omniroute-codex-sdk/worker.py` through Claude's native
Bash tool. The primary route is `cx/gpt-6.1-sol-max`, with native Max effort.
The coordinator retains its native Claude account and model route.
Writing (`workspace-write`) dispatch is not yet qualified at 0.160.0; the README
and `docs/decisions/2026-10-03-omniroute-sdk-worker-0160.md` hold the evidence.

Give a writing worker its own worktree, bounded file ownership, an executable
acceptance condition and the enhanced private Codex home described in
`examples/omniroute-codex-sdk/enhancements.md`. Use that scoped setup by default;
preserve an existing home's configuration and adopt only reviewed selected keys.
Pass native readiness before dispatch, requiring Context Mode. Add
`--require-skill NAME` only after the documented installer has installed that
selected skill in the private worker home; a new home with none installed has
no skill requirement. Require Serena too when the task needs semantic navigation. Tell it other workers
are present and that it must preserve their edits. Feed the task on stdin:

```sh
rtk proxy uv run --locked --script examples/omniroute-codex-sdk/worker.py \
  --workspace "$WORKER_PROJECT" \
  --codex-home "$PRIVATE_WORKER_HOME" \
  --preflight --require-mcp context-mode \
  --timeout 60 &&
rtk proxy uv run --locked --script examples/omniroute-codex-sdk/worker.py \
  --workspace "$WORKER_PROJECT" \
  --codex-home "$PRIVATE_WORKER_HOME" \
  --timeout 600 \
  --prompt -
```

Use the selected gateway's native Responses lane at loopback port 21128, the
worker's default. Keep
the exact model route in the live catalog; the default Sol/max suffix requires
an OmniRoute build carrying PR #15167. Requested effort does not establish
gateway-forwarded effort or backend identity. Keep
native caches, tools and project skill discovery intact; load only task-relevant
skill bodies. Install selected skills through the existing runtime-worker skill
recipe, rather than importing the entire catalog into the task prompt. Optional
MCP services use their native configuration and task-specific readiness checks.
Use the coordinator's selected native workflow roles for research, implementation
and verification, and the bounded Dagu graph when the task needs automation.

Keep returned thread IDs private and use `--resume` for continuation. The latest
thread usage snapshot includes previous turns; count it once. A deadline invokes
native interruption and child cleanup; remote termination and unknown provider
usage remain unverified. Do not automatically replay a failed writing task.
After a `content_filter` stop, preserve native guidance and resume only for an
explicit permitted alternative or unrelated authorized task.

Use explicit `--model cx/gpt-6-astra-max` for consequential architecture,
conflicting primary evidence, or a failure unresolved after one bounded Sol
repair. Record that trigger and the acceptance result. The separate Claude SDK
bridge remains a trial after its gateway errors; it is not the primary worker.

Sources: [Claude native project skills](https://code.claude.com/docs/en/skills)
and [official Codex SDK, rust-v0.160.0](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python).
Functional scope and retained failures are recorded in
`docs/decisions/2026-09-30-omniroute-runtime-workers.md` and
`docs/decisions/2026-10-03-omniroute-sdk-worker-0160.md`.
