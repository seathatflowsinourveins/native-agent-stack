# SubagentStart token-lanes carrier: native probe and RTK hook checks (2026-09-27)

- Host: `nativestack-5975wx-20260925` (the WSL2 workstation). Claude Code 2.1.283, RTK 0.50.0.
- Probe runs: 02:37Z to 02:53Z UTC. Retained RTK capture: 03:28:14Z to 03:28:15Z.
- Change under test: the [carrier decision](../../../docs/decisions/2026-09-27-token-lanes-subagent-start.md).
  The probe ran the hook and block files before they were committed; their SHA-256 values in
  [`receipt.json`](receipt.json) `files_under_test` identify the exact bytes, which the change commits unchanged.
- Machine-readable record: [`receipt.json`](receipt.json).

**Evidence class: `local_integration`.** Each run is a native Claude Code operation on this host through this
repository's integration, for subagents launched with the Agent tool. It is not `native_proven` for Workflow
children, because no Workflow subagent ran. It measures no lane use, compliance or token savings.

## Question

Does the `SubagentStart` hook put the token-lanes block into a non-blind subagent's context and keep it out of a
blind one's? How does RTK 0.50.0's Claude hook rewrite each Bash shape the block describes?

## Method

Each probe run was one `claude -p --output-format json` session (stdin `/dev/null`, timeout 300 s) in this
repository's main checkout. Its main session (Opus 5.5) launched one Haiku 4.5 subagent through the Agent tool and
relayed the reply verbatim. Positive runs added a settings file whose `SubagentStart` group (matcher `""`,
timeout 5) runs `python3 "<worktree>/adoption/hooks/claude/token-lanes-subagent-start.py"`. Negative runs used only
the host's live settings, whose `SubagentStart` group runs ai-memory and not this hook. Each child's transcript was
then read directly for the block's first-line marker `TOKEN LANES (source:` and for its `SubagentStart` entries.

The v2 question given to the child, verbatim:

> Without calling any tool, look through everything already in your context for this turn other than this task
> message itself, including any system reminders or hook-provided context. Is there any text there that contains
> the phrase TOKEN LANES? Answer FOUND or NOT FOUND on the first line. If FOUND, on the second line quote exactly
> the 60 characters that begin with TOKEN LANES, character for character, in quotes.

The blind control used the same prompt with `subagent_type "blind-judge"`. `receipt.json` has both prompts in full.

## Results

| Run (start, UTC) | Hook | Child | Child's reply | Child transcript |
| --- | --- | --- | --- | --- |
| v2 negative (02:50:39Z) | none | `general-purpose` | `NOT FOUND` | no marker; only ai-memory's SubagentStart hook ran |
| v2 positive (02:50:57Z) | token-lanes | `general-purpose` | `FOUND` / `"TOKEN LANES (source: docs/token-session-handbook.md, "Token "` | one `hook_additional_context` attachment from SubagentStart; the token-lanes hook exited 0 with 3,258 bytes of output |
| v2 blind control (02:52:25Z) | token-lanes | `blind-judge` | `NOT FOUND` | no marker; no entry for the token-lanes hook |
| v1 negative (02:37:40Z) | none | `general-purpose` | `NO` | no marker |
| v1 positive (02:49:08Z) | token-lanes | `general-purpose` | `NO` | block attached, as in v2 positive |

The v2-positive quote equals the committed block's first 60 characters exactly. Recomputing the hook's output
from the committed files gives the same 3,258 bytes the v2-positive transcript recorded. All five runs exited 0.

Provider usage for all five runs, as the CLI's `modelUsage` reported it: Opus 5.5 input 20, output 2,344, cache
read 263,466, cache creation 153,558; Haiku 4.5 input 50, output 4,290, cache read 14,666, cache creation 70,203;
`costUSD` $1.44 in total, including the failed v1 design.

### RTK 0.50.0 hook checks

Every input ran through `rtk hook check -- <input>` and through `rtk hook claude` with a Claude PreToolUse Bash
payload on stdin. That is the processor the Claude settings template runs. Neither executes the input. Both entry
points agreed on every case:

| Input | Result |
| --- | --- |
| `git status && git log -n 3` | `rtk git status && rtk git log -n 3` |
| `git status` / `git diff --stat` (two lines) | `rtk git status` / `rtk git diff --stat` |
| `git status` / `echo done` | `rtk git status` / `echo done` |
| `cd /tmp` / `git status` | `cd /tmp` / `rtk git status` |
| `git diff \| head -n 5` | `rtk git diff \| head -n 5` |
| `git log -n 20 \| grep fix` | `git log -n 20 \| rtk grep fix` |
| `gh pr view 1 \| head -n 5`, `echo $(git status)`, backticks, `<(...)`, `> /tmp/x.txt`, a heredoc, a two-line block with `$(...)` on one line, `echo a` / `echo b` | not rewritten (`rtk hook check` exit 1, `No rewrite for: ...`; no `updatedInput`) |

`receipt.json` lists all 17 inputs with both outputs verbatim. A block of `echo` lines is never rewritten because
`echo` has no RTK rule, so it cannot test multi-line handling. The same cases were first observed between 02:28Z
and 02:46Z; the 03:28Z capture is the retained one.

## Retained failure

Probe v1 asked whether a block whose *first line starts with* `TOKEN LANES` was present. Both arms answered `NO`,
although the v1-positive child transcript held the block, so v1 did not discriminate. The likely cause is that
Claude Code frames attached context (the child's prompt snapshot records `contextRendering: announced`). The
child's reasoning was redacted, so that cause is not observed. v2 replaced the question.

## Limits

- One native operation per arm for Agent-tool subagents, on one host and client version. No Workflow child has
  run with the hook; the [WP1 baseline](../child-lane-baseline-20260926/README.md) recorded SubagentStart for 465
  `workflow-subagent` children.
- The blind control shows that no block reached the `blind-judge` child. It does not show that the hook ran and
  skipped: a hook with empty output leaves no entry in the transcript. The skip logic is covered by
  `tests/test_token_lanes_subagent_start.py`.
- A plugin-scoped blind agent type such as `plugin:blind-judge` does not start with `blind-` and would receive the
  block.
- The RTK results hold for RTK 0.50.0 with this host's user configuration.

## Sanitization

Raw CLI output and child transcripts stay private on the host, because they carry session, agent and tool-use
identifiers and local paths. `receipt.json` `raw_files_private` identifies each one by SHA-256, byte count and
event or line count. Absolute scratch and worktree paths are written as `<scratch>` and `<worktree>`. Hook
commands inside transcripts are reduced to the hook's name. No transcript text is published beyond each child's
reply.
