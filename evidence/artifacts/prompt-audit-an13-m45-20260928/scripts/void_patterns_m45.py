"""M5 adjudication's void patterns, adapted from x9-round3/void_patterns_r3.py and frozen before any judge starts.

Scopes as in round 3: MAPPING applies to everything a judge ran, read or received; ACCESS to what it ran or opened;
WEB to web searches and opened URLs; PHRASES to context injected before the judge's first tool call.
- MAPPING: the names of the first-round returns, their tally and the order mapping, which say which lane wrote which
  text, and phrases that attribute a return to a family.
- ACCESS: the private work directory and where it is held, the runner's job directory, the retired base worktree,
  the main checkout, session transcripts, subagent and task output, and git history commands.
- WEB: this repository, its owner and its pull requests.
- PHRASES: the first-round verdict lines as the coordinator printed them.
"""
import re

MAPPING = re.compile("|".join([
    r"gpt6-m45", r"claude-m45", r"round1-tally", r"m45-mapping", r"audit-judge-m45", r"claude-brief-m45",
    r"save_claude_return", r"\b(?:gpt-?6|codex|claude)(?:'s)? lane\b", r"family's own", r"evidence-reviewer"]), re.I)
ACCESS = re.compile("|".join([
    r"convergence-m45", r"m45-adj-runs", r"wt-m45-base", r"/\.hold3?\b", r"code/native-agent-stack",
    r"/\.claude/projects", r"/subagents/", r"/tasks/", r"convergence-prompt-audit", r"wt-pa-rebase",
    r"\bgit\s+(?:-C\s+\S+\s+)?(?:log|show|blame|diff|grep|status|branch|reflog)\b"]), re.I)
WEB = re.compile(r"native-agent-stack|seathatflowsinourveins|pull/4\d\d|#4\d\d\b", re.I)
PHRASES = re.compile(r"M5 amend 0\.\d+|\"M5\": \[\"amend\"|round1-tally", re.I)
