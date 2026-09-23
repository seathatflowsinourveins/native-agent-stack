# Frozen research task (native-clients gap 2 & 8, and reused for gap 12)

Frozen 2026-09-23 before any arm ran. This exact prompt text is passed verbatim
to both `claude -p` and `codex exec`, and (for gap 12) to the Claude Agent SDK
and to `claude -p` again.

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

- Tool scope: Bash only (claude: `--allowedTools Bash`; codex: default
  workspace-write sandbox restricted to running the one `date` command, no
  other tool surface offered since codex exec's native toolset is shell-only).
- Effort: medium (claude: `--effort medium`; codex:
  `-c model_reasoning_effort=medium`).
- Single turn, non-interactive (`claude -p`, `codex exec`).
- No web/network tools in either arm.

## Second task

Optional per the binding rules ("one frozen research task, and optionally a
second, short, distinct one"). Not run in this unit: the single task above
already exercises research recall, one mandatory tool call and blind judging,
and running a second task would materially increase the `claude -p` call
budget (judge calls scale with output count) without adding a new
discriminating signal for gaps 2/8. Recorded as a scope choice, not an
oversight.
