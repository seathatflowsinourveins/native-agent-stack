"""Deterministic metrics for the X9 round-2 comparison, as promptfoo python assertions (promptfoo 0.123.1,
src/python/wrapper.py, calls getattr(module, name)(output, context) and accepts a bool) and for analyze.py.

`output` is summarize.py's JSON. Ground truth is the run's own `system/init` event: a server is active when its
status there is "connected". Per run:
- correct (primary): K1/K2, the answer's leading yes/no equals the ground truth; K3, the answer names every
  connected server.
- answered: K1/K2, the answer starts with yes or no; K3, it names at least one connected server.
- no_builtin_skill: no Skill call naming mcp, context, plugin or plugins. Claude Code 2.1.283 refuses each such call
  with a tool error (uncounted probe, probe/probe-skill-builtins.jsonl).
- loaded_schema (descriptive): at least one ToolSearch call.
- executed_target (descriptive): at least one successful call to a tool of the target server (mcp__<target>__...);
  for K3, a successful call to any MCP tool. It shows "successful execution" as distinct from "listed availability".
- cli_diagnostic (descriptive): a Bash command containing "claude mcp" or "claude plugin".
- asks_user (descriptive): the answer explicitly asks the user to run, type, share, paste or send something.
- names_command (descriptive): the answer names /mcp, /context, /plugin or /plugins.
"""
import json
import re

YES_NO = re.compile(r"^\W*(yes|no)\b", re.I)
ASKS = re.compile(r"\b(could|can|would|will) you\b[^.?!\n]*\b(run|type|share|paste|send)\b"
                  r"|\bplease\b[^.?!\n]*\b(run|type|share|paste|send)\b", re.I)
COMMAND = re.compile(r"(?<![\w/.~])/(mcp|context|plugins?)\b", re.I)
BUILTIN = {"mcp", "context", "plugin", "plugins"}


def facts(output):
    return json.loads(output) if isinstance(output, str) else output


def servers(s):
    return {k.split(":")[-1]: v for k, v in (s.get("init") or {}).get("mcp_servers", {}).items()}


def named(s):
    final = s.get("final") or ""
    return {n for n, st in servers(s).items()
            if st == "connected" and re.search(rf"(?<![A-Za-z0-9]){re.escape(n)}(?![A-Za-z0-9])", final, re.I)}


def compute(s, case, target):
    final = s.get("final") or ""
    m = YES_NO.match(final)
    ans = m.group(1).lower() if m else None
    connected = {n for n, st in servers(s).items() if st == "connected"}
    if case == "K3":
        got = named(s)
        correct, answered = bool(connected) and got >= connected, bool(got)
    else:
        truth = "yes" if servers(s).get(target) == "connected" else "no"
        correct, answered = ans == truth, ans is not None
    calls = s.get("calls") or []
    prefix = "mcp__" if case == "K3" else f"mcp__{target}__"
    executed = any((c["name"] or "").startswith(prefix) and c.get("is_error") is False for c in calls)
    cli = any(c["name"] == "Bash" and re.search(r"\bclaude (mcp|plugin)\b", c.get("command") or "") for c in calls)
    builtin = any(c["name"] == "Skill" and (c.get("skill") or "").lstrip("/").lower() in BUILTIN for c in calls)
    return {"correct": correct, "answered": answered, "no_builtin_skill": not builtin,
            "loaded_schema": any(c["name"] == "ToolSearch" for c in calls), "executed_target": executed,
            "cli_diagnostic": cli, "asks_user": bool(ASKS.search(final)), "names_command": bool(COMMAND.search(final))}


def _metric(name):
    def fn(output, context):
        v = context["vars"]
        return compute(facts(output), v["case"], v.get("target", ""))[name]
    return fn


METRICS = ("correct", "answered", "no_builtin_skill", "loaded_schema", "executed_target", "cli_diagnostic",
           "asks_user", "names_command")
(correct, answered, no_builtin_skill, loaded_schema, executed_target, cli_diagnostic, asks_user,
 names_command) = (_metric(n) for n in METRICS)
