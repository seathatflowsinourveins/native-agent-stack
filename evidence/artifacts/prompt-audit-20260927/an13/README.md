# AN-13: a headless `/doctor prompt-audit` run (2026-09-28)

A peer session asked for a headless run of the client's `/doctor prompt-audit` on this repository with this pull
request's changes applied. The run happened twice in one read-only tree that was never committed: `main` at
`eb678281`, plus the then-uncommitted diffs of this pull request and of the template pull request (#458).

| Run | Command | Result |
| --- | --- | --- |
| First, 09:38:42Z to 10:05:59Z | `timeout 3000 claude -p "/doctor prompt-audit" --model claude-opus-5-5 --effort max --permission-mode plan --disallowedTools "Edit Write NotebookEdit" --output-format stream-json --verbose` | Exit 0 after 37 turns, but with a 1,537-character interim note instead of the report. The client stopped all four background Explore agents after its 600 s wait (`subagent_stats.killed.system: 4`, none completed). Its stderr: "Background tasks still running after 600s; terminating. Set CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 to wait indefinitely." |
| Rerun, 10:39:16Z to 11:06:30Z | the same with `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`, `timeout 5400` and `< /dev/null` | Exit 0 after 60 turns. Its one background Explore agent completed, and the result is the full report (20,827 characters). Two tool calls were denied in plan mode: one `ctx_execute` and one `Bash` |

Both runs used client 2.1.283 and `claude-opus-5-5`. `an13-runs.json` (from `extract_an13.py`) holds each run's facts:
- timing and outcome;
- both usage blocks, as the client reports them;
- the subagent statistics and the event counts;
- the client's own cost figure at list prices: $22.74 for the first run and $13.97 for the rerun.

`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` is documented in the
[environment-variable reference](https://code.claude.com/docs/en/env-vars): default 600000, and 0 waits
indefinitely. It is not in the client's CHANGELOG.

**Not published:**
- the report text, which quotes the user-level instruction file and names installed plugins and skills;
- the event logs, which carry host paths, session ids and the plugin, skill and MCP inventories.

## Findings and what happens to them

The report found no high-confidence item. It found six medium findings, three low-confidence flags and four plugin
findings, and it proposed no provider change. Nothing was edited from it.

| Finding | Where | Disposition |
| --- | --- | --- |
| M1: the trigger "Before any action … for every action" is broader than the rule's subject (writing, building, installing or adopting) | `AGENTS.md:3` | Paired with M2. Under X5b, `AGENTS.md:3` carries the operator's paragraph word for word, so it follows the user-level file and is not edited alone. Left to the user |
| M2: the same wording | the user-level instruction file | The user's decision |
| M3: a pinned model version in the model policy | the user-level instruction file | The user's decision |
| M4a, M4b: pressure wording and broad "always before" triggers | a vendored user-level skill, pinned at trial status and shared with Codex (`adoption/skills/manifest.json`) | Residual: it needs the native before-and-after comparison the report describes. #456 removed the token-lanes carrier's instruction to follow the skill, but `isolated-builder` still preloads it (`.claude/agents/isolated-builder.md:9`). The project-side options left are ending the trial or not preloading it there. Those are separate work |
| M5: a history narrative in place of the rule | `blueprints/convergence-practice/application-delivery/AGENTS.md:15-18` | A single-family candidate: it needs a second-family lane before any edit |
| L1: a client-version condition | `examples/claude-native/CLAUDE.md:44` and the user-level file | Recorded flag; the condition still matters on older clients |
| L2: two verification lines | the user-level file | Recorded flag; candidates for a re-test, not for removal |
| L3: a project skill path that does not exist here | `.claude/agents/semantic-evidence-reviewer.md:12-13` | Recorded flag; the same sentence's fallback covers it |
| P1 to P4: emphatic wording in three installed plugin skills, and a pinned model version in a fourth | plugin text | Recorded flags. This is upstream text, reported without edits |
