"""Audit lane A's final X5c adjudication judges against void_patterns_final.py: lane-a2/audit_a2.py with the
INJECTED check on attachments and advisor results of a Claude judge.

usage: audit_final.py OUT_JSON NAME=gpt6:JOB_DIR|NAME=claude:TRANSCRIPT ...
JOB_DIR holds the runner's prompt.txt and events.jsonl; TRANSCRIPT is a Claude subagent JSONL file. Scopes:
- MAPPING: everything a judge ran, read or received: its prompt, commands, tool inputs, command outputs, tool
  results, web searches and their results, advisor results, and every injected attachment;
- ACCESS (each named part in void_patterns_final.ACCESS_PARTS, the same for both families): what it ran or opened;
- WEB: web searches and opened URLs;
- PHRASES: context injected before the judge's first tool call (later injected context is reported, not voiding);
- INJECTED: every attachment of a Claude judge, including hook context, and its advisor results (the two exempt
  attachment kinds are named in void_patterns_final.py);
- any mcp__ call by a Claude judge.
A judgment with any voiding hit is void. The audit reads no verdict or choice.
"""
import hashlib
import json
import sys
from pathlib import Path

X = Path(__file__).resolve().parent
sys.path.insert(0, str(X))
import void_patterns_final as v  # noqa: E402


class Audit:
    def __init__(self, lane):
        self.hits, self.info, self.items, self.access = [], [], {}, v.access(lane)

    def check(self, text, scope, patterns, quiet=False, voiding=True):
        text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
        for name in patterns:
            regs = self.access.items() if name == "ACCESS" else [(name, getattr(v, name))]
            for part, rx in regs:
                m = rx.search(text)
                if m:
                    (self.hits if voiding else self.info).append({
                        "pattern": name if name != "ACCESS" else f"ACCESS:{part}", "scope": scope,
                        "match": m.group(0),
                        "window": None if quiet else text[max(0, m.start() - 80):m.end() + 80]})

    def count(self, kind):
        self.items[kind] = self.items.get(kind, 0) + 1

    def result(self):
        return {"void": bool(self.hits), "hits": self.hits, "info": self.info, "items": self.items}


def audit_gpt6(job):
    a = Audit("gpt6")
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


def audit_claude(transcript):
    a = Audit("claude")
    first_tool_seen = False
    for line in transcript.read_text().splitlines():
        e = json.loads(line)
        t = e.get("type")
        if t == "attachment":
            att = e.get("attachment") or {}
            kind = att.get("type") or "?"
            a.count(f"attachment {kind}")
            quiet = kind.startswith("credential")
            body = {"attachment": att, "rendered": e.get("rendered")}
            a.check(body, f"attachment {kind}", ["MAPPING"], quiet=quiet)
            if kind != "prompt_snapshot":  # the judge's own agent definition (void_patterns_final.py)
                a.check(body, f"attachment {kind}", ["INJECTED"], quiet=quiet, voiding=kind != "session_context")
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
                a.check(b.get("content"), bt, ["MAPPING"] + (["INJECTED"] if bt == "advisor_tool_result" else []))
            elif bt == "text" and t == "user":
                a.check(b.get("text") or "", "user text block", ["MAPPING"] + ([] if first_tool_seen else ["PHRASES"]))
        if t == "user" and e.get("toolUseResult") is not None:
            a.check(e["toolUseResult"], "tool result (structured)", ["MAPPING"])
    return a


def main(out, specs):
    res = {}
    for spec in specs:
        name, rest = spec.split("=", 1)
        kind, path = rest.split(":", 1)
        res[name] = (audit_gpt6 if kind == "gpt6" else audit_claude)(Path(path)).result()
    Path(out).write_text(json.dumps({"patterns_sha256": hashlib.sha256((X / "void_patterns_final.py").read_bytes())
                                    .hexdigest(), "judgments": res}, ensure_ascii=False, indent=1) + "\n")
    for k, r in res.items():
        print(k, "VOID" if r["void"] else "clean", [(h["pattern"], h["scope"], h["match"]) for h in r["hits"]][:8],
              "| info:", [(h["pattern"], h["scope"]) for h in r["info"]][:4], "| items:", r["items"])
    return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
