"""Lane A's void patterns for its X5a/X5c adjudication: round 3's X9 scopes (x9-round3/void_patterns_r3.py), with
the places that say which lane wrote which X5 return or that hold other judges' output.

Scopes are round 3's: MAPPING applies to everything a judge ran, read or received; ACCESS to what it ran or opened;
WEB to web searches and opened URLs; PHRASES to context injected before its first tool call.
- MAPPING: lane A's own record paths (returns, briefs, runner records, tally and adjudication mapping) and a verdict
  keyed by family name. The repository root (46184751) holds rounds 1-2 of this audit, whose file names
  (round1/gpt6.json, review/claude-brief.txt) say nothing about lane A, so only lane-A-specific names are listed;
  root_scan_a.py checks that no root file matches.
- ACCESS: the private work and hold directories, the staging copies, attempt 1's directory (j5), the runner's job directory (other judges'
  output), this session's subagent task outputs and transcripts (anchored on the session id: the root has its own
  docs/tasks/), session transcripts (Claude and Codex homes), the live checkout, and git history;
- WEB: this repository and its open pull requests;
- PHRASES: either return's amendment text, injected before the judge read anything (a family-keyed verdict is
  MAPPING everywhere).
"""
import re

MAPPING = re.compile("|".join([
    r"lane-a/", r"adjudication-mapping-a", r"tally-lanes", r"make_adjudication_a", r"gpt6\.runner\.json",
    r"\"gpt6\":\s*\"(?:agree|amend|reject)\"", r"\"claude\":\s*\"(?:agree|amend|reject)\""]), re.I)
ACCESS = re.compile("|".join([
    r"convergence-prompt-audit", r"prompt-audit-x9-round2", r"prompt-audit-adjudication", r"/\.hold\b",
    r"/\.hold3\b", r"j5-stage", r"convergence-r3", r"x9-round3", r"/j2/", r"/j3/", r"/j5/",
    r"/x5/runs\b", r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}/(?:tasks|subagents)/", r"/\.claude/projects", r"~/\.codex\b", r"/home/[^/\s]+/\.codex\b",
    r"\$HOME/\.codex\b", r"code/native-agent-stack",
    r"\bgit\s+(?:-C\s+\S+\s+)?(?:log|show|blame|diff|grep)\b",
    r"wt-pa-r3", r"wt-r3-base", r"wt-x5\b"]), re.I)
WEB = re.compile(r"native-agent-stack|seathatflowsinourveins|pull/44\d|#44\d\b", re.I)
PHRASES = re.compile(r"The installed client is also a source of truth|So never self-write without a SOTA source", re.I)
