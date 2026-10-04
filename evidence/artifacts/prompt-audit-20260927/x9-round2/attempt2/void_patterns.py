"""The attempt-2 void patterns (attempt1-void.json, attempt_2_rules), as regexes for the attempt-2 audit.

MAPPING applies to everything a judge ran, read or received: commands, file paths, searches, command outputs, tool
results, and context injected before its first tool call. These strings occur only in sources that say which lane
wrote which X9 text. ACCESS applies to what a judge ran or opened (commands, file paths and search paths), not to
file contents: these locations hold such sources, while repository prose may mention them harmlessly. A git history
command counts as ACCESS, since the root is an export without history. WEB applies to web searches and opened URLs.
PHRASES applies to injected context only, since the judge's own input quotes both texts.
"""
import re

MAPPING = re.compile("|".join([
    r"2026-09-27-prompt-audit-resolution", r"prompt-audit-20260927", r"(?<![\w-])gpt6\.txt\b",
    r"(?<![\w-])claude\.txt\b", r"gpt6-round1", r"claude-round1", r"judgment-mapping", r"adjudication-mapping",
    r"family's own lane"]), re.I)
ACCESS = re.compile("|".join([
    r"convergence-prompt-audit", r"prompt-audit-x9-round2", r"prompt-audit-adjudication", r"/\.hold\b",
    r"/\.claude/projects", r"code/native-agent-stack", r"/subagents/", r"/tasks/",
    r"\bgit\s+(?:-C\s+\S+\s+)?(?:log|show|blame|diff|grep)\b"]), re.I)
WEB = re.compile(r"native-agent-stack|seathatflowsinourveins|pull/44[34]|#44[34]\b", re.I)
PHRASES = re.compile(r"name the command that would|Distinguish listed availability from successful execution", re.I)
