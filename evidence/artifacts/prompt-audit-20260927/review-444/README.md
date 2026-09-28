# Review of #444's round-3 head (2026-09-28)

One review round ran on `0779e91a`, before the head was first pushed. Each family's reviewer ran once, and one
repair round followed.

| Reviewer | Prompt | Return | Usage |
| --- | --- | --- | --- |
| GPT-6: `codex exec -s read-only -m gpt-6-astra -c model_reasoning_effort=max -c web_search=live`, run in the worktree, 12:58:47Z to 13:08:54Z | `gpt6-prompt.txt` | `gpt6-review.md`: changes-needed, 1 should-fix | `gpt6-usage.json`, from `gpt6_review_usage.py` |
| Claude: one `evidence-reviewer` agent, given the coordinator's command results | `claude-brief.txt` | `claude-review.md`: changes-needed, 5 should-fix, 3 nits | `claude-usage.json`, from `review_usage.py` |

The returns are kept as written, with the worktree path written as `<worktree>`. `final_text.py` took the Claude
return from the agent's transcript, which is not published.

## Findings and what happened to them

| Finding | Disposition |
| --- | --- |
| GPT-6 1: "at most 10 turns", although one K5 run's result reports 11 | Fixed: the record says `--max-turns 10` and names the 11-turn result. So does the package README |
| GPT-6, in its command table: `git diff --check` reports trailing spaces in the retained judge prompts | Not changed: the prompts are kept as the judges received them, with host paths replaced. No check reads their whitespace |
| Claude 1: M4 handed to the user, although its evidence says it is project work | Fixed: the record and `an13/README.md` call M4 a project-side residual, name the preload and say it needs a second-family lane |
| Claude 2: the Codex lane's host result stated with no retained output | Fixed: [`codex-worker-lane-host-20260928/`](../../codex-worker-lane-host-20260928/) keeps the three outputs, sanitized as #406's were, plus a recheck with exit codes and times. The record cites it |
| Claude 3: no control shows the judges' audit can fire | Fixed: `x9-round3/audit_control_r3.py` and `x9-round3/judges/audit-control.json`. On unchanged copies, the audit reproduced the published verdicts; with one planted access per judgment, it voided all four |
| Claude 4: changes made after the freeze were not all disclosed | Fixed: the record and the package README list every difference between the frozen and run builders |
| Claude 5: the behavior-change claim is broader than what was measured | Fixed: the record says the applied text tied with the line it replaced on all three preregistered metrics, and that the 10-to-8 gap is over the other candidate |
| Claude 6 (nit): the X5b sentence on obligations, and which test reads the dispatch pointer | Fixed in the record |
| Claude 7 (nit): which judges made advisor calls | Fixed: "the two Claude judges", with the advisor-usage caveat |
| Claude 8 (nit): `/home`, `/tmp` and `/Users` listed as outside paths in one Claude B/A action | Explained in the record and the package README: they come from a Grep pattern over the judge's own input |
| Claude, not checked: the runs used `ba1700ad`'s files, not the files as applied | Added as a limit in the record and the package README |

No second review round was run. The repairs had no independent review.
