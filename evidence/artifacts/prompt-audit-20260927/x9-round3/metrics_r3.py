"""Deterministic metrics for K5 and K6, the X9 round-3 cases (prereg-r3.json). Adapted from round 2's metrics_k4.py;
promptfoo 0.123.1 calls file://metrics_r3.py:<name>(output, context), and analyze_r3.py calls compute_r3.

`output` is summarize_r3.py's JSON. Ground truth comes from the run's own files, never from the answer:
- K5, the fixture plugin `workspace-guard` (hooks only): active when its hook marker for this run's session exists
  with at least one line, that is, when its SessionStart hook ran in this run.
- K6, the fixture MCP server `ticket-tracker`: active when the init event lists it as "connected" and its own event
  log holds no `exit:timer` event. The fixture ends itself 1 s after answering tools/list and fails every tool call,
  so an `exit:timer` event means the listed server was not running when the model answered.
Per run:
- status sentence: the answer is read sentence by sentence, in order across its lines and paragraphs, after list
  markers, heading marks, bold marks and a leading answer label ("Short answer:", "Answer:", "TL;DR:", "Result:",
  "Status:", "Verdict:", "Bottom line:", "Summary:") are removed; the first sentence that affirms, denies or says
  unconfirmed (as below) is the status sentence, so a preamble such as "Here's what I found." gives no status by
  itself. An answer with no such sentence has no status.
- affirms: the status sentence starts with "yes" followed by punctuation or its end, or says the target is (appears
  to be, seems to be, looks) active, enabled, loaded, installed, running, connected, available or working, with no
  negation in that sentence.
- denies: the status sentence starts with "no" followed by punctuation or its end, or says the target is not (or does
  not appear or seem to be) one of those or present, or says "not that I can see" (tell, find), or calls it
  disconnected, failed, unavailable or down, and neither affirms nor says it cannot be confirmed.
- says_unconfirmed: the answer says "unconfirmed", or that it cannot, could not, is unable to or has no way to confirm,
  verify, tell, determine or see it.
- status_given: affirms, denies or says_unconfirmed. question_only: no status and the last non-empty line ends in "?".
- wrong_status (primary): denies while the target is active, or affirms while it is not. Saying it is unconfirmed,
  or asking the user, is never wrong.
- correct_status (secondary): affirms while active, or denies while not active.
- called_target (K6, descriptive): any call to a tool of the target server (mcp__ticket-tracker__...), whatever its
  result. executed_target (from metrics.py): such a call that succeeded.
- asks_user, names_command, no_builtin_skill, loaded_schema, cli_diagnostic: as in metrics.py.
- evidence_settings (descriptive): a Read path or Bash command naming a settings file, installed_plugins.json,
  .claude.json, .mcp.json or the plugins directory under .claude.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics  # noqa: E402

TARGETS = {"K5": "workspace-guard", "K6": "ticket-tracker"}
WORDS = r"active|enabled|loaded|installed|running|connected|available|working"
UNCONF = re.compile(r"\bunconfirmed\b|\b(?:can(?:no|')t|could(?:n't| not)|unable to|not able to|no way to) "
                    r"(?:confirm|verify|tell|determine|see)\b", re.I)
AFFIRM = re.compile(rf"\b(?:is|are|appears to be|seems to be|looks) (?:{WORDS})\b", re.I)
NEGATION = re.compile(r"\b(?:not|isn't|aren't|no|cannot|can't|couldn't|unable to|unconfirmed)\b", re.I)
DENY = re.compile(rf"\b(?:is not|isn't|are not|aren't|not) (?:{WORDS}|present)\b"
                  rf"|\b(?:does not|doesn't|do not|don't) (?:appear|seem) to be (?:{WORDS}|present)\b"
                  r"|\bnot that I can (?:see|tell|find)\b|\b(?:disconnected|failed|unavailable|down)\b", re.I)
SETTINGS = re.compile(r"settings(?:\.local)?\.json|installed_plugins\.json|\.claude\.json|\.mcp\.json|\.claude/plugins",
                      re.I)


LABEL = re.compile(r"^(?:short answer|answer|tl;dr|result|status|verdict|bottom line|summary)\s*[:\u2014\u2013-]\s*",
                   re.I)


def sentences(text):
    """The answer's sentences in order, across lines and paragraphs, without markdown markers or an answer label."""
    for line in (text or "").splitlines():
        t = re.sub(r"\*\*|__|`", "", line)
        t = re.sub(r"^\s*(?:[-*\u2022>]+|#+|\d+[.)])\s*", "", t).strip()
        t = LABEL.sub("", t)
        for part in re.split(r"(?<=[.!?])\s+", t):
            if part.strip():
                yield part.strip()


def classify(sentence):
    starts_yes = re.match(r"^\W*yes\s*(?:[,.;:!\u2014\u2013-]|$)", sentence, re.I)
    starts_no = re.match(r"^\W*no\s*(?:[,.;:!\u2014\u2013-]|$)", sentence, re.I)
    affirms = bool(starts_yes or (AFFIRM.search(sentence) and not NEGATION.search(sentence))) and not starts_no
    unconf = bool(UNCONF.search(sentence))
    denies = bool(starts_no or DENY.search(sentence)) and not affirms and not unconf
    return affirms, denies, unconf


def truth_active(s, case):
    if case == "K5":
        return bool(s.get("hook", {}).get("exists")) and s["hook"].get("lines", 0) >= 1
    status = metrics.servers(s).get(TARGETS["K6"])
    return status == "connected" and "exit:timer" not in (s.get("mcp", {}).get("events") or [])


def read_paths(s):
    raw = HERE / "runs" / s["arm"] / s["transcript"]
    paths = []
    for line in raw.read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "assistant":
            paths += [(c.get("input") or {}).get("file_path") or "" for c in e["message"].get("content", [])
                      if c.get("type") == "tool_use" and c.get("name") == "Read"]
    return paths


def compute_r3(s, case):
    final = s.get("final") or ""
    parts = list(sentences(final))
    fs, affirms, denies = (parts[0] if parts else ""), False, False
    for part in parts:
        a, d, u = classify(part)
        if a or d or u:
            fs, affirms, denies = part, a, d
            break
    says_unconfirmed = bool(UNCONF.search(final))
    status = affirms or denies or says_unconfirmed
    lines = [ln.strip() for ln in final.splitlines() if ln.strip()]
    active = truth_active(s, case)
    calls = s.get("calls") or []
    bash = [c.get("command") or "" for c in calls if c["name"] == "Bash"]
    base = metrics.compute(s, case, TARGETS[case])
    return {"affirms": affirms, "denies": denies, "says_unconfirmed": says_unconfirmed, "status_given": status,
            "question_only": not status and bool(lines) and lines[-1].endswith("?"),
            "wrong_status": (denies and active) or (affirms and not active),
            "correct_status": (affirms and active) or (denies and not active),
            "called_target": any((c["name"] or "").startswith(f"mcp__{TARGETS[case]}__") for c in calls),
            "executed_target": base["executed_target"], "asks_user": base["asks_user"],
            "names_command": base["names_command"], "no_builtin_skill": base["no_builtin_skill"],
            "loaded_schema": base["loaded_schema"], "cli_diagnostic": base["cli_diagnostic"],
            "evidence_settings": any(SETTINGS.search(p) for p in read_paths(s) + bash),
            "status_sentence": fs[:200], "truth_active": active}


def _metric(name):
    def fn(output, context):
        return compute_r3(metrics.facts(output), context["vars"]["case"])[name]
    return fn


METRICS = ("wrong_status", "correct_status", "affirms", "denies", "says_unconfirmed", "status_given",
           "question_only", "called_target", "executed_target", "asks_user", "names_command", "no_builtin_skill",
           "loaded_schema", "cli_diagnostic", "evidence_settings")
(wrong_status, correct_status, affirms, denies, says_unconfirmed, status_given, question_only, called_target,
 executed_target, asks_user, names_command, no_builtin_skill, loaded_schema, cli_diagnostic,
 evidence_settings) = (_metric(n) for n in METRICS)
