"""Void patterns for lane A's final X5c adjudication: void_patterns_a2.py (the final round's lanes) with these
changes, fixed before dispatch and proven both ways by audit_selftest_final.py:
- the final lanes' directory (k2: their roots and the GPT-6 lane's runner job) was moved under .hold3 before
  dispatch; `/k2/` is added to the hold part for a judge that guesses the old path, and the lane job directory is
  the other-lane part for both families, since a judge of either family that read it would learn which return came
  from which lane (the lanes themselves did not need this for GPT-6);
- codex_home also allows a plugin's skills as the runtime loads them (plugins/cache/.../skills/): the final round's
  GPT-6 probe read one at startup; `..` segments are refused in every allowed Codex-home path;
- adjudication_runs: this adjudication's runner work directory (j7/x5c/runs, its gpt6/ job directories and the job
  names), for both families;
- MAPPING (every scope) adds the final round's record names and the family-to-verdict JSON forms of its tally;
- INJECTED: a family name next to a verdict word, or a phrase that attributes a lane, return or judgment to a family.
  It applies only to context a Claude judge did not fetch (attachments, including hook context, and advisor
  results), because the repository's own prose about the two families is subject matter in files a judge reads.
  The prompts are frozen before dispatch and scanned by root_scan_final.py instead. Two attachment kinds are
  exempt: prompt_snapshot is the judge's own agent definition, whose leak rule quotes "Claude's proposal" as an
  example; session_context is the client's start-of-session snapshot (the user's email and the live checkout's git
  status), whose commit subjects name lanes as subject matter, so its hits are reported, not voiding, and no commit
  is made while judges run.
"""
import re

HOME = r"(?:~|\$HOME|\$\{HOME\}|/home/[^/\s'\"]+)"
MAPPING = re.compile("|".join([
    r"lane-a/", r"adjudication-mapping", r"tally-lanes", r"tally-a\.json", r"make_adjudication_a",
    r"gpt6\.runner\.json", r"x5-adj-(?:AB|BA)",
    r"tally[-_]final", r"audit-lanes", r"returns/(?:gpt6|claude)\b", r"a2-gpt6", r"<agent-id-3>",
    # a family key with a verdict value, as a string, a list or a verdict object; quotes may be JSON-escaped
    r'\\?"(?:gpt6|claude)\\?"\s*:\s*(?:\[\s*|\{\s*\\?"verdict\\?"\s*:\s*)?\\?"(?:agree|amend|reject)\\?"']),
    re.I)
ACCESS_PARTS = {
    "hold_and_work_dirs": r"convergence-prompt-audit|prompt-audit-x9-round2|prompt-audit-adjudication|/\.hold\w*"
                          r"|j5-stage|j6-stage|convergence-r3|x9-round3|lane-a2?\b|/j[2-6]/|/x5/runs\b"
                          r"|wt-pa-r3|wt-r3-base|wt-x5\b|tok-base-|/k2/|withheld-check",
    "session_transcripts": r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}/(?:tasks|subagents)/",
    "claude_home": HOME + r"/\.claude(?!/(?:CLAUDE\.md|RTK\.md|agents/|skills/|commands/))",
    "codex_home": HOME + r"/\.codex(?!/(?:AGENTS\.md|RTK\.md|version\.json|models_cache\.json"
                         r"|(?:skills/|plugins/cache/(?:(?!\.\.?/)[\w.@+-]+/)+skills/)(?!(?:[^\s'\"]*/)?\.\.)))",
    "memory_store": HOME + r"/\.local/share/ai-memory",
    "live_checkout": r"code/native-agent-stack",
    "adjudication_runs": r"/x5c/runs\b|/runs/gpt6\b|\.\./gpt6\b|x5c-final-(?:AB|BA)",
    "other_lane": r"/k2/work\b|/work/gpt6\b",
}


def access(lane):
    return {k: re.compile(p, re.I) for k, p in ACCESS_PARTS.items()}


FAMILY = r"(?:gpt-?6|claude|opus|anthropic|openai)"
VERDICT = r"(?:agree[sd]?|amend(?:s|ed)?|reject(?:s|ed)?|accept(?:s|ed)?)"
INJECTED = re.compile(
    rf"\b{FAMILY}(?:'s)?[- ](?:lane|judge|return|reviewer|adjudicat\w*|amendment|verdict|proposal)s?\b"
    rf"|\b{FAMILY}\b[\s\S]{{0,60}}?\b{VERDICT}\b|\b{VERDICT}\b[\s\S]{{0,60}}?\b{FAMILY}\b", re.I)
WEB = re.compile(r"native-agent-stack|seathatflowsinourveins|pull/4[45]\d|#4[45]\d\b", re.I)
PHRASES = re.compile(r"So never self-write without a SOTA source", re.I)
