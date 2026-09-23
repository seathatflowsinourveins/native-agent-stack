# Frozen research task (native-clients gap 2 & 8, and reused for gap 12)

Frozen 2026-09-23 before any arm ran. This exact prompt text is passed verbatim
to both `claude -p` and `codex exec`, and (for gap 12) to the Claude Agent SDK
and to `claude -p` again.

CORRECTION (fix round): "committed to the worktree BEFORE any arm ran" (as
the receipts originally claimed) is not accurate as a git-commit claim --
this file, rubric.json and run-order.json were written before any run (by
file modification time, 00:58:26-00:58:39 EDT, before the first raw output
at 00:59:19), but were only committed to git afterward, in the single
commit that added this whole evidence set after every run completed. Freeze
timing here is established by file modification time, not commit time.
Separately, the literal `task-prompt.txt` file actually passed to
`run-arm.sh` for the six gap-2/8 runs was not preserved: the `task-prompt.txt`
now in this directory has a modification time of 01:06:40, after the last
gap-2/8 output (01:01:45), and its formatting differs cosmetically from this
file's rendering of the prompt below (no backticks around the date command
and TIMESTAMP line; the TIMESTAMP placeholder is quoted instead). The
prompt's substance is unchanged and all 6 outputs behaved consistently with
either wording, but the exact bytes sent cannot be independently
re-verified from the current worktree state alone.

## Prompt (verbatim)

Research question: Name ONE specific, real, verifiable technique used in
production LLM coding-agent systems to reduce token usage during tool calls or
long sessions (for example prompt caching, context compaction, retrieval-based
context reduction, or a named provider feature). In 3 to 5 sentences: (1) name
the technique and, if you can, the system or provider that uses it, (2)
explain briefly how it reduces tokens, and (3) give one concrete quantifiable
claim about its benefit or a tradeoff (a percentage, ratio, or comparable
number). Then, using the Bash tool exactly once, run:
`date -u +%Y-%m-%dT%H:%M:%SZ` and finish your reply with a final line
`TIMESTAMP: <output>` containing that command's exact stdout. Do not use any
tool other than Bash, and do not run any other command.

## Matched settings

- Tool scope (intended): Bash only (claude: `--allowedTools Bash`; codex:
  default workspace-write sandbox restricted to running the one `date`
  command, no other tool surface offered since codex exec's native toolset
  is shell-only).
- CORRECTION (fix round, recorded after the runs, from the raw system/init
  events): `--allowedTools Bash` only auto-approves Bash without prompting;
  it does NOT restrict which tools are available to the model (restricting
  availability requires the SDK's separate `tools` option, not used here).
  In this unit's actual runs, the claude -p research arm and all blind-judge
  calls ran with cwd=~/code/agent-lab (not this unit's owned
  worktree) and 124 tools available, including WebFetch, WebSearch, and the
  serena/ai-memory/socraticode/jcodemunch MCP servers -- not a Bash-only
  tool set. codex exec's sandbox restriction is a genuine tool-scope
  restriction (its native toolset is shell-only), so the two arms were not
  actually matched on tool scope, only on the prompt's instruction to use
  only Bash. Each of the 6 runs happened to comply (one `date` call, no
  web/MCP calls observed), so this did not contaminate the answer text, but
  "matched tool scope" should be read as "the same instruction was given",
  not as "the same tools were available". See
  evidence/artifacts/gap-wave3-20260923/native-clients/arm-comparison-research-task.json
  for the corrected receipt text.
- Effort: medium (claude: `--effort medium`; codex:
  `-c model_reasoning_effort=medium`).
- Single turn, non-interactive (`claude -p`, `codex exec`).
- No web/network tools were actually invoked in either arm (confirmed from
  the raw command_execution/tool_use events), even though the claude -p arm
  had web tools available per the correction above.

## Second task

Optional per the binding rules ("one frozen research task, and optionally a
second, short, distinct one"). Not run in this unit: the single task above
already exercises research recall, one mandatory tool call and blind judging,
and running a second task would materially increase the `claude -p` call
budget (judge calls scale with output count) without adding a new
discriminating signal for gaps 2/8. Recorded as a scope choice, not an
oversight.
