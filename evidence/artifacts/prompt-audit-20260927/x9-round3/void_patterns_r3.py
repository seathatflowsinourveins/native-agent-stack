"""Round 3's void patterns: round 2's (x9-round2/void_patterns.py, the attempt-2 rules), extended with the places
round 3 adds that say which lane wrote which X9 text, or that hold round 3's own work.

Scopes are round 2's: MAPPING applies to everything a judge ran, read or received; ACCESS to what it ran or opened;
WEB to web searches and opened URLs; PHRASES to context injected before its first tool call.
Added for round 3:
- MAPPING: the round-3 run worktrees and per-arm run directories, the arm files, the round-3 analysis and mapping
  files, and round 2's returns, which carry each family's choice;
- ACCESS: the round-3 work directory, round 2's judge directory (its runner records name the model next to its
  choice) and the hold directory the work is moved to before dispatch;
- WEB: pull request #445 and later numbers this work may open.
"""
import re

MAPPING = re.compile("|".join([
    r"2026-09-27-prompt-audit-resolution", r"prompt-audit-20260927", r"(?<![\w-])gpt6\.txt\b",
    r"(?<![\w-])claude\.txt\b", r"gpt6-round1", r"claude-round1", r"judgment-mapping", r"adjudication-mapping",
    r"family's own lane",
    r"wt-x9r3-[gc0]\b", r"\bruns/[gc0]/", r"CLAUDE\.[gc0]\.md\b", r"analysis-r3\.json", r"results-r3\.json",
    r"round3-mapping", r"attempt2-mapping", r"returns2/"]), re.I)
ACCESS = re.compile("|".join([
    r"convergence-prompt-audit", r"prompt-audit-x9-round2", r"prompt-audit-adjudication", r"/\.hold\b",
    r"/\.claude/projects", r"code/native-agent-stack", r"/subagents/", r"/tasks/",
    r"\bgit\s+(?:-C\s+\S+\s+)?(?:log|show|blame|diff|grep)\b",
    r"convergence-r3", r"x9-round3", r"/j2/", r"/\.hold3\b", r"wt-pa-r3", r"wt-r3-base", r"wt-x5\b"]), re.I)
WEB = re.compile(r"native-agent-stack|seathatflowsinourveins|pull/44\d|#44\d\b", re.I)
PHRASES = re.compile(r"name the command that would|Distinguish listed availability from successful execution", re.I)
