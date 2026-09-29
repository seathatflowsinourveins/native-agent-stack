"""Count-only scan of tool results (item 7, M14 call states): which result templates the Claude Code client writes for a call
that did not run or did not finish, with the row fields beside them (is_error, toolDenialKind, the toolUseResult form) and the
tool kind (Bash, an MCP tool, another built-in tool). Prints fixed class names, enum values and counts only: no ids, tool
names beyond the three kinds, paths, commands or result text."""
import json
import os
import re
import sys
from collections import Counter, defaultdict

# Result templates, tested in this order against the result text (a string, or its text blocks joined with '').
TEMPLATES = [
    ("tool_use_error:InputValidationError", re.compile(r"<tool_use_error>InputValidationError")),
    ("tool_use_error:No such tool available", re.compile(r"<tool_use_error>(?:Error: )?No such tool available")),
    ("tool_use_error:Cancelled", re.compile(r"<tool_use_error>Cancelled: ")),
    ("tool_use_error:Error: Streaming fallback", re.compile(r"<tool_use_error>Error: Streaming fallback")),
    ("tool_use_error:other", re.compile(r"<tool_use_error>")),
    ("user_does_not_want_to_proceed", re.compile(r"The user doesn't want to proceed with this tool use")),
    ("request_interrupted_for_tool_use", re.compile(r"\[Request interrupted by user for tool use\]")),
    ("request_interrupted_other", re.compile(r"\[Request interrupted by user")),
    ("permission_to_use_denied", re.compile(r"Permission to use \S+(?: .*)? has been denied")),
    ("permission_to_use_other", re.compile(r"Permission to use ")),
    ("permission_for_denied", re.compile(r"Permission for this tool use was denied")),
    ("pretooluse_hook_error", re.compile(r"PreToolUse:\S+ hook error: ")),
    ("automode_no_verdict", re.compile(r"The server-side auto mode classifier gave no verdict")),
    ("host_hook_agent_isolated", re.compile(r"This agent is isolated")),
    ("exit_code", re.compile(r"Exit code -?\d+")),
    ("mcp_not_connected", re.compile(r"MCP server \S.* is not connected \(status: ")),
]


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
    return None


def template(text):
    if text is None:
        return "(no text)"
    for name, pattern in TEMPLATES:
        if pattern.match(text):
            return name
    for name, pattern in TEMPLATES:
        if pattern.search(text[:400]):
            return name + " (not at the start)"
    return "(other)"


def said_form(said, text):
    """The toolUseResult form: absent, an object (with interrupted true), or a string equal to the text, 'Error: ' + the text, or else
    the class of its own template."""
    if said is None:
        return "absent"
    if isinstance(said, dict):
        return "object(interrupted)" if said.get("interrupted") is True else "object"
    if not isinstance(said, str):
        return type(said).__name__
    if text is not None and said == text:
        return "string=text"
    if text is not None and said == "Error: " + text:
        return "string='Error: '+text"
    if said == "User rejected tool use":
        return "string='User rejected tool use'"
    return "string:" + template(said[7:] if said.startswith("Error: ") else said)


def kind_of(name):
    if name == "Bash":
        return "Bash"
    if isinstance(name, str) and name.startswith("mcp__"):
        return "mcp"
    return "other_builtin" if name else "(no call)"


c = defaultdict(Counter)
files = 0
for root in sys.argv[1:]:
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if not fname.endswith(".jsonl"):
                continue
            try:
                fh = open(os.path.join(dirpath, fname), "rb")
            except OSError:
                continue
            files += 1
            names = {}
            with fh:
                for raw in fh:
                    if b'"tool_use"' not in raw and b'"tool_result"' not in raw:
                        continue
                    try:
                        row = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(row, dict):
                        continue
                    msg = row.get("message")
                    blocks = msg.get("content") if isinstance(msg, dict) else None
                    if not isinstance(blocks, list):
                        continue
                    for b in blocks:
                        if not isinstance(b, dict):
                            continue
                        if row.get("type") == "assistant" and b.get("type") == "tool_use":
                            names.setdefault(b.get("id"), b.get("name"))
                        elif row.get("type") == "user" and b.get("type") == "tool_result":
                            text = text_of(b.get("content"))
                            t = template(text)
                            err = b.get("is_error") is True
                            kind = kind_of(names.get(b.get("tool_use_id")))
                            denial = row.get("toolDenialKind")
                            denial = denial if isinstance(denial, str) else ("(absent)" if denial is None else type(denial).__name__)
                            c["results"]["is_error=" + str(err)] += 1
                            if t == "(other)" and not err and denial == "(absent)":
                                continue
                            key = "%s | is_error=%s | toolDenialKind=%s | toolUseResult=%s | %s" % (
                                t, err, denial, said_form(row.get("toolUseResult"), text), kind)
                            c["templates"][key] += 1
                            if denial != "(absent)":
                                c["denial_kinds"][denial + " is_error=" + str(err)] += 1
print(json.dumps({"transcript_files": files, **{k: dict(sorted(v.items())) for k, v in c.items()}}, indent=1, sort_keys=True))
