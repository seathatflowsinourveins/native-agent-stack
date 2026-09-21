# Native Claude-to-Codex foreground review

Use the installed official Codex companion from a dedicated review worktree.
Preserve native account, model and permission settings. Inspect the selected
branch/base and keep only this Claude session in the review checkout while it
runs; other projects and the live coordinating Claude session can remain active.

```sh
claude -p '/codex:review --wait --scope branch --base BASE_COMMIT --json' \
  --output-format stream-json --verbose --max-turns 8
```

Replace `BASE_COMMIT` with the verified comparison base. Retain stdout/stderr
outside the checkout, and inspect the returned companion result, not only the
outer Claude exit status. The native slash command expands directly and invokes
the official `codex-companion.mjs review` implementation. No custom relay or
workflow parser is needed for this path. Native authentication is a prerequisite;
do not copy account stores or add broker credentials to a code-review process.

## Returned September 21 result

The [native receipt](../evidence/artifacts/foundation-rd-20260921/native-review.json)
records Claude Code 2.1.278, Codex CLI 0.155.1 and official companion 1.0.6
(source `db52e28f4d9ded852ab3942cea316258ae4ef346`). The review compared
`1f06fb78eef6324d10995f10f6c290886fd5c81f` with
`907485219d8437ee407ec716615b0e3af4e35cc2`: the paper runner's final submission
clock check, its regression tests and README. It returned Codex status 0:

> No actionable regressions were found. All 32 local synthetic Alpaca paper tests passed; native broker execution was not exercised.

The retained Claude result reports Fable 5.1, two turns, no permission denials and
108.423 seconds of monotonic wall time for the command. Claude's returned token
counts and list-price cost estimate are recorded separately. This companion path
does not expose Codex model/effort/token totals; they remain unknown. Its review
thread is ephemeral in the inspected source. Retaining the original native
stream and a hash-bound public projection preserves the returned result without
claiming a durable Codex conversation or provider savings.

## Lifecycle boundary

The installed companion stores its broker by workspace. Its SessionEnd hook
shuts down that workspace's broker without checking which session owns it,
although job cleanup is session-filtered. A dedicated checkout avoids sharing
this broker with another Claude session. This source observation does not prove
the cause of the earlier aborted background review, whose failure remains in
the [prior record](../evidence/artifacts/native-claude-coop-20260921/persistent-profile.json).

Retain outputs before SessionEnd cleanup. A successful foreground run does not
qualify concurrent same-workspace sessions, Workflow background polling,
interrupted reviews or broker execution. Reopen this isolation choice when a
supported upstream lifecycle change and a measured concurrent-session test
establish safe ownership. Review agreement alone does not establish correctness;
the selected source and behavior tests remain the acceptance evidence.

[Official companion](https://github.com/openai/codex-plugin-cc),
[native Claude headless mode](https://code.claude.com/docs/en/headless).
