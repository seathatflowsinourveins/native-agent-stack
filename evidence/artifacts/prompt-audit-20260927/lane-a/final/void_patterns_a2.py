"""Void patterns for lane A's final round on X5a/X5c (round 2): its two independent lanes and, if they split, its
blind adjudication. Fixed before either lane runs; audit_selftest_a2.py proves each named pattern both ways.

Changed from lane A's adjudication patterns (lane-a/adj/void_patterns_a.py), because attempt 2 voided both GPT-6
judgments on a read the Codex runtime makes at startup (`cat ~/.codex/RTK.md`, also made by the GPT-6 probe and
lane runs before that attempt was dispatched):
- the Codex home is matched as a whole except the files the runtime's own instructions load (AGENTS.md, RTK.md,
  skills/, version.json, models_cache.json), so session logs, state databases, history and a search rooted at the
  home still void; the Claude home likewise except CLAUDE.md, RTK.md, agents/, skills/ and commands/;
- ai-memory's store is added (its hooks record this session's tool calls);
- git history commands are no longer voiding: the lane roots are plain copies without a repository, and
  `git diff --no-index` between the base and proposed copies is an expected check;
- per lane, the other lane's return location is added: the GPT-6 job directory (k2/work) for Claude judges, and
  this session's subagent transcripts (already listed) for GPT-6 judges.

Scopes as before: MAPPING applies to everything a judge ran, read or received; ACCESS to what it ran or opened; WEB
to web searches and opened URLs; PHRASES to context injected before its first tool call.
"""
import re

HOME = r"(?:~|\$HOME|\$\{HOME\}|/home/[^/\s'\"]+)"
MAPPING = re.compile("|".join([
    r"lane-a/", r"adjudication-mapping", r"tally-lanes", r"tally-a\.json", r"make_adjudication_a",
    r"gpt6\.runner\.json", r"x5-adj-(?:AB|BA)", r"\"gpt6\":\s*\"(?:agree|amend|reject)\"",
    r"\"claude\":\s*\"(?:agree|amend|reject)\""]), re.I)
ACCESS_PARTS = {
    "hold_and_work_dirs": r"convergence-prompt-audit|prompt-audit-x9-round2|prompt-audit-adjudication|/\.hold\w*"
                          r"|j5-stage|j6-stage|convergence-r3|x9-round3|lane-a2?\b|/j[2-6]/|/x5/runs\b"
                          r"|wt-pa-r3|wt-r3-base|wt-x5\b|tok-base-",
    "session_transcripts": r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}/(?:tasks|subagents)/",
    "claude_home": HOME + r"/\.claude(?!/(?:CLAUDE\.md|RTK\.md|agents/|skills/|commands/))",
    "codex_home": HOME + r"/\.codex(?!/(?:AGENTS\.md|RTK\.md|skills/|version\.json|models_cache\.json))",
    "memory_store": HOME + r"/\.local/share/ai-memory",
    "live_checkout": r"code/native-agent-stack",
}
OTHER_LANE = {"claude": r"/k2/work\b", "gpt6": r"(?!)"}  # GPT-6 judges reach Claude returns only through transcripts


def access(lane):
    parts = dict(ACCESS_PARTS, other_lane=OTHER_LANE[lane])
    return {k: re.compile(v, re.I) for k, v in parts.items()}


WEB = re.compile(r"native-agent-stack|seathatflowsinourveins|pull/4[45]\d|#4[45]\d\b", re.I)
PHRASES = re.compile(r"So never self-write without a SOTA source", re.I)
