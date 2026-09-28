"""Audit attempt 2's four X9 judgments against void_patterns.py (attempt1-void.json, attempt_2_rules).

usage: audit_attempt2.py J CLAUDE_AB_TRANSCRIPT CLAUDE_BA_TRANSCRIPT [OUT_NAME]
J is the attempt-2 directory; the GPT-6 events are J/runs/gpt6/x9r2-judge-{AB,BA}/events.jsonl with the prompt the
runner sent in prompt.txt, and the Claude transcripts are the two blind-adjudicator subagent JSONL files. Scopes,
as recorded in void_patterns.py:
- MAPPING: everything a judge ran, read or received: its prompt, commands, tool inputs, command outputs, tool
  results, web searches and their results, advisor results, and every injected attachment;
- ACCESS: what a judge ran or opened: commands and tool inputs;
- WEB: web searches and opened URLs;
- PHRASES: context injected before the judge's first tool call (later injected context is reported, not voiding);
- any mcp__ call by a Claude judge.
A judgment with any voiding hit is void. The audit reads no choice. Writes x9-round2/audit-attempt2.json with each
hit's pattern, scope and a short window around the match, except inside credential attachments, where only the hit
is recorded.
"""
import json
import sys
from pathlib import Path

X = Path(__file__).resolve().parent / "x9-round2"
sys.path.insert(0, str(X))
import void_patterns as v  # noqa: E402

J = Path(sys.argv[1])
CLAUDE = {"AB": Path(sys.argv[2]), "BA": Path(sys.argv[3])}
OUT_NAME = sys.argv[4] if len(sys.argv) > 4 else "audit-attempt2.json"  # a self-test writes elsewhere


def window(text, m, quiet):
    return None if quiet else text[max(0, m.start() - 80):m.end() + 80]


class Audit:
    def __init__(self):
        self.hits, self.info, self.items = [], [], {}

    def check(self, text, scope, patterns, quiet=False, voiding=True):
        text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
        for name in patterns:
            m = getattr(v, name).search(text)
            if m:
                (self.hits if voiding else self.info).append(
                    {"pattern": name, "scope": scope, "match": m.group(0), "window": window(text, m, quiet)})

    def count(self, kind):
        self.items[kind] = self.items.get(kind, 0) + 1


def gpt6(order):
    job = J / "runs" / "gpt6" / f"x9r2-judge-{order}"
    a = Audit()
    a.check((job / "prompt.txt").read_text(), "prompt", ["MAPPING"])
    for line in (job / "events.jsonl").read_text().splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            a.count("non-json line")
            continue
        it = e.get("item") or {}
        if e.get("type") != "item.completed":
            continue
        kind = it.get("type")
        a.count(kind)
        if kind == "command_execution":
            a.check(it.get("command") or "", "command", ["MAPPING", "ACCESS"])
            a.check(it.get("aggregated_output") or "", "command output", ["MAPPING"])
        elif kind == "web_search":
            a.check({"query": it.get("query"), "action": it.get("action")}, "web search", ["WEB", "MAPPING"])
            a.check(it.get("results") or "", "web results", ["MAPPING"])
        elif kind in ("agent_message", "reasoning"):
            continue
        else:
            a.check(it, f"item {kind}", ["MAPPING", "ACCESS"])
    return a


def claude(order):
    a = Audit()
    first_tool_seen = False
    for line in CLAUDE[order].read_text().splitlines():
        e = json.loads(line)
        t = e.get("type")
        if t == "attachment":
            att = e.get("attachment") or {}
            kind = att.get("type") or "?"
            a.count(f"attachment {kind}")
            quiet = kind.startswith("credential")
            body = {"attachment": att, "rendered": e.get("rendered")}
            a.check(body, f"attachment {kind}", ["MAPPING"], quiet=quiet)
            a.check(body, f"attachment {kind}" + (" (after first tool call)" if first_tool_seen else ""),
                    ["PHRASES"], quiet=quiet, voiding=not first_tool_seen)
            continue
        msg = e.get("message") or {}
        content = msg.get("content")
        if t == "user" and isinstance(content, str):
            a.count("user text")
            a.check(content, "prompt" if not first_tool_seen else "user text", ["MAPPING"])
            if not first_tool_seen:
                a.check(content, "prompt", ["PHRASES"])
            continue
        for b in content if isinstance(content, list) else []:
            bt = b.get("type")
            a.count(bt)
            if bt == "tool_use":
                first_tool_seen = True
                name, inp = b.get("name") or "", b.get("input")
                a.check({"name": name, "input": inp}, f"tool call {name}", ["MAPPING", "ACCESS"])
                if name in ("WebSearch", "WebFetch"):
                    a.check(inp, f"tool call {name}", ["WEB"])
                if name.startswith("mcp__"):
                    a.hits.append({"pattern": "mcp__ call", "scope": "tool call", "match": name, "window": None})
            elif bt == "server_tool_use":
                first_tool_seen = True
                a.check(b.get("input"), f"server tool {b.get('name')}", ["MAPPING", "ACCESS"])
            elif bt == "tool_result" or bt.endswith("_tool_result"):
                a.check(b.get("content"), bt, ["MAPPING"])
            elif bt == "text" and t == "user":
                a.check(b.get("text") or "", "user text block", ["MAPPING"] + ([] if first_tool_seen else ["PHRASES"]))
        if t == "user" and e.get("toolUseResult") is not None:
            a.check(e["toolUseResult"], "tool result (structured)", ["MAPPING"])
    return a


out = {}
for fam, fn in (("gpt6", gpt6), ("claude", claude)):
    for order in ("AB", "BA"):
        a = fn(order)
        out[f"{fam}-{order}"] = {"void": bool(a.hits), "hits": a.hits, "info": a.info, "items": a.items}
(X / OUT_NAME).write_text(json.dumps(
    {"patterns_sha256": __import__("hashlib").sha256((X / "void_patterns.py").read_bytes()).hexdigest(),
     "judgments": out}, ensure_ascii=False, indent=1) + "\n")
for k, r in out.items():
    print(k, "VOID" if r["void"] else "clean", [(h["pattern"], h["scope"], h["match"]) for h in r["hits"]][:8],
          "| info:", [(h["pattern"], h["scope"]) for h in r["info"]][:4], "| items:", r["items"])
