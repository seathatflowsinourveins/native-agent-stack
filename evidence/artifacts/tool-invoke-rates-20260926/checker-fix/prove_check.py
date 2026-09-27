"""Read-only Loki checks for prove.sh: per-server, per-skill and per-subagent counts for one ecosystem.task.id.

Usage: prove_check.py <loki base> <task id> <deadline seconds> [--dry-run] [--forbidden-file F]...
                      [--collector staged collector.yaml] [--events-glob GLOB] [--window 30m]
Only structured-metadata KEYS, expected name values and counts are printed; an unexpected value is counted, never
printed. The forbidden files hold strings that must not appear in Loki or in the Collector's events file (the
proof's commands and prompts); their content is never printed.

Fixed 2026-09-26 (window-2 finding 2 / decision-thread PRRT_kwDOUg_LrM6mT7_M): the forbidden-string loader dropped
lines under 8 characters and prove.sh's own generator dropped lines under 12, so a short executed command (e.g.
`pwd`) was never tested; and no assertion ever compared a record's body against the Collector's fixed placeholder,
so a leak that happened to be short could pass silently. Both length floors are gone (empty lines only are
dropped), every forbidden literal is matched against parsed body/attribute-value strings (never the raw serialized
blob or JSON line, so a short literal cannot false-positive on brackets, key names or an unrelated substring), and
`REPORT_FIXED_BODY` now asserts every tagged record's body equals the transform/privacy placeholder exactly, in
both the Loki sink and the Collector's file-exporter sink.
"""
import glob
import re
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# observability/collector/collector.yaml, transform/privacy: `set(body, "[content omitted]")`.
FIXED_BODY = "[content omitted]"

results = {"pass": 0, "fail": 0}


def instant(loki, expr):
    query = urllib.parse.urlencode({"query": expr, "time": f"{time.time():.3f}"})
    try:
        with urllib.request.urlopen(f"{loki}/loki/api/v1/query?{query}", timeout=60) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        return None, f"HTTP {error.code}"
    out = {}
    for r in body["data"]["result"]:
        key = tuple(sorted(r.get("metric", {}).items()))
        out[key] = float(r["value"][1])
    return out, None


def by(expr_labels, pipeline, selector, window, unwrap=None):
    keep = ", ".join(expr_labels) or "service_name"
    group = f"sum by ({', '.join(expr_labels)}) " if expr_labels else "sum "
    fn = "sum_over_time" if unwrap else "count_over_time"
    tail = f" | unwrap {unwrap} | __error__=\"\"" if unwrap else ""
    keep_list = keep + (f", {unwrap}" if unwrap else "")
    return f"{group}({fn}({selector} | {pipeline} | keep {keep_list}{tail} [{window}]))"


def build_checks(claude, any_, window):
    """The 12 count-based checks + 3 zero-checks, bound to this run's task-scoped selectors and window. Kept as
    a function (not module-level) so importing this file for its offline-replayable pieces (privacy_checks,
    streams_to_lines, record_values, otlp_body_and_values, load_forbidden) never touches the network or argv."""
    checks = [
        ("Claude MCP tool_result by server: context-mode plugin >= 1, qmd >= 2",
         by(["mcp_server_name"], 'event_name="tool_result" | tool_family="mcp"', claude, window),
         lambda r: at_least([("mcp_server_name", "plugin_context-mode_context-mode")])(r)
         and at_least([("mcp_server_name", "qmd")], 2)(r)),
        ("Claude skill_activated by name: codebase-design >= 1",
         by(["skill_name"], 'event_name="skill_activated"', claude, window),
         at_least([("skill_name", "codebase-design")])),
        ("Claude Agent launches (accepted tool_decision) by subagent_type: general-purpose >= 1",
         by(["subagent_type"], 'event_name="tool_decision" | decision="accept" | tool_name=~"Agent|Task"',
            claude, window),
         at_least([("subagent_type", "general-purpose")])),
        ("Claude Workflow launches (accepted tool_decision) >= 1",
         by([], 'event_name="tool_decision" | decision="accept" | tool_name="Workflow"', claude, window),
         lambda r: sum(r.values()) >= 1),
        ("Claude tool_result by actor: workflow >= 1 and main_or_subagent >= 1",
         by(["actor"], 'event_name="tool_result"', claude, window),
         at_least([("actor", "workflow"), ("actor", "main_or_subagent")])),
        ("Claude api_request MCP attribution: subagent/qmd >= 1 and workflow/qmd >= 1",
         by(["actor", "mcp_server_name"], 'event_name="api_request" | mcp_server_name!=""', claude, window),
         lambda r: any(dict(k) == {"actor": "subagent", "mcp_server_name": "qmd"} for k in r)
         and any(dict(k) == {"actor": "workflow", "mcp_server_name": "qmd"} for k in r)),
        ("Claude subagent_completed total_tool_uses for general-purpose >= 1",
         by(["agent_type"], 'event_name="subagent_completed"', claude, window, unwrap="total_tool_uses"),
         at_least([("agent_type", "general-purpose")])),
        ("Claude Bash tool_result carries shell_rtk",
         by(["shell_rtk"], 'event_name="tool_result" | tool_family="shell"', claude, window),
         lambda r: any(dict(k).get("shell_rtk") in ("true", "false") for k in r)),
        ("Codex MCP tool_result by server: context-mode >= 1",
         by(["mcp_server_name"], 'event_name="codex.tool_result" | tool_family="mcp"', any_, window),
         at_least([("mcp_server_name", "context-mode")])),
        ("Codex tool_result by actor: main >= 1 and subagent >= 1",
         by(["actor"], 'event_name="codex.tool_result"', any_, window),
         at_least([("actor", "main"), ("actor", "subagent")])),
        ("Codex agent_communication spawn sends >= 1",
         by([], 'event_name="codex.agent_communication" | kind="spawn" | state="send"', any_, window),
         lambda r: sum(r.values()) >= 1),
        ("tool results by client: claude-code >= 1 and codex_exec >= 1",
         by(["client"], 'event_name=~"tool_result|codex.tool_result"', any_, window),
         at_least([("client", "claude-code"), ("client", "codex_exec")])),
    ]
    zero_checks = [
        ("unparsed tool_parameters == 0", by([], 'tool_details="unparsed"', any_, window)),
        ("names replaced by the name pattern == 0",
         by([], 'mcp_server_name="other" or mcp_tool_name="other" or skill_name="other" or originator="other"'
                ' or client="other"', any_, window)),
        ("agent types outside the built-in agents (custom) == 0 (the proof uses general-purpose only)",
         by([], 'subagent_type="custom" or agent_type="custom" or agent_name="custom"', any_, window)),
    ]
    return checks, zero_checks


# name -> (expression, predicate on {labels: value}, description of the expectation)
def at_least(label_values, minimum=1):
    def check(result):
        return all(any(dict(k).get(label) == value and v >= minimum for k, v in result.items())
                   for label, value in label_values)
    return check


def report(name, ok, detail=""):
    results["pass" if ok else "fail"] += 1
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" :: {detail}" if detail else ""))


def shown(result):
    return "; ".join(f"{dict(k) or '{}'}={v:g}" for k, v in sorted(result.items())[:8]) or "no series"


def load_forbidden(paths):
    """Every non-empty line of every file, with NO minimum length: a 3-character executed command (e.g. `pwd`)
    must be checked exactly like a long sentence. (Pre-fix this filtered out anything under 8 characters.)"""
    out = []
    for path in paths:
        out += [line.strip() for line in open(path) if line.strip()]
    return out


def otlp_body_and_values(obj):
    """One parsed OTLP JSON log line -> (last logRecord body string or None, [every string attribute value]).
    Reads only decoded values, never the line's raw text, so a short forbidden literal can't false-positive on
    JSON punctuation or an unrelated key name."""
    body, values = None, []
    for rl in obj.get("resourceLogs", []) or []:
        for sl in rl.get("scopeLogs", []) or []:
            for lr in sl.get("logRecords", []) or []:
                b = (lr.get("body") or {}).get("stringValue")
                if isinstance(b, str):
                    body = b
                for a in lr.get("attributes", []) or []:
                    v = (a.get("value") or {}).get("stringValue")
                    if isinstance(v, str):
                        values.append(v)
    return body, values


def fetch_lines(loki, task, window_s):
    """Every record tagged with task from Loki's query_range (structured metadata included), most-recent
    window_s*10 seconds. Returns a list of (stream_labels: tuple, body: str, meta: dict)."""
    end = time.time_ns()
    query = urllib.parse.urlencode({"query": '{service_name=~".+"} | ecosystem_task_id="%s"' % task, "limit": 5000,
                                    "start": str(end - window_s * 10 * 10**9), "end": str(end)})
    request = urllib.request.Request(f"{loki}/loki/api/v1/query_range?{query}",
                                     headers={"X-Loki-Response-Encoding-Flags": "categorize-labels"})
    with urllib.request.urlopen(request, timeout=60) as response:
        streams = json.load(response)["data"]["result"]
    return streams_to_lines(streams)


def streams_to_lines(streams):
    out = []
    for s in streams:
        stream = tuple(sorted(s.get("stream", {}).items()))
        for e in s["values"]:
            body = e[1] if len(e) > 1 else None
            meta = e[2].get("structuredMetadata", {}) if len(e) > 2 and isinstance(e[2], dict) else {}
            out.append((stream, body, meta))
    return out


def record_values(body, meta):
    vals = [body] if isinstance(body, str) else []
    vals += [v for v in meta.values() if isinstance(v, str)]
    return vals


def privacy_checks(lines, forbidden, collector=None, events_lines=None, fixed_body=FIXED_BODY, report=report):
    """The whole privacy block, over an already-fetched `lines` list (see fetch_lines/streams_to_lines) and an
    already-filtered `events_lines` list of raw JSONL strings (already restricted to the proof's task id).
    Offline-replayable: `lines`/`events_lines` can come from a live fetch, a saved export, or a synthetic
    fixture — the assertions are identical either way. Returns nothing; reports via the `report` callback."""
    report("the proof's records were fetched without truncation", 0 < len(lines) < 5000, f"records={len(lines)}")
    label_sets = {stream for stream, _, _ in lines}
    report("every stream's labels are exactly {service_name}", label_sets == {(("service_name", ""),)} or all(
        len(s) == 1 and s[0][0] == "service_name" for s in label_sets), f"label sets={sorted(label_sets)}")
    keys = sorted({k for stream, _, _ in lines for k, _ in stream} | {k for _, _, m in lines for k in m})
    if collector:
        config = open(collector).read()
        allow = set()
        for statement in re.findall(r"keep_keys\(attributes, \[([^\]]*)\]\)", config):
            allow |= set(re.findall(r'"([^"]+)"', statement))
        allowed = {re.sub(r"[^A-Za-z0-9_]", "_", k) for k in allow} | {
            "detected_level", "observed_timestamp", "scope_name", "severity_number", "severity_text", "flags",
            "trace_id", "span_id", "service_name"}
        extra = sorted(set(keys) - allowed)
        report("every key on the proof's records comes from the Collector allowlists or Loki's own fields",
               not extra, f"extra={extra}")
    # Name fields may hold only the names this proof uses (value counts only; a stray value is never printed).
    expected = {
        "mcp_server_name": {"plugin_context-mode_context-mode", "qmd", "context-mode", "custom"},
        "mcp_tool_name": {"ctx_stats", "status", "custom"},
        "skill_name": {"codebase-design", "custom_skill"},
        "subagent_type": {"general-purpose"}, "agent_type": {"general-purpose"},
        "agent_name": {"general-purpose", "workflow-subagent"},
        "originator": {"codex_exec"}, "client": {"claude-code", "codex_exec"},
        "invocation_trigger": {"nested-skill", "claude-proactive", "user-slash"},
        "tool_family": {"shell", "read", "edit", "mcp", "skill", "toolsearch", "web", "agent", "code_mode", "other"},
        "actor": {"main", "subagent", "workflow", "main_or_subagent", "auxiliary"},
        "shell_rtk": {"true", "false"}, "kind": {"spawn", "message", "followup", "result"},
        "state": {"send", "receive"}}
    stray = {}
    for _, _, m in lines:
        for key, allowed_values in expected.items():
            if key in m and m[key] not in allowed_values:
                stray[key] = stray.get(key, 0) + 1
        if "workflow_name" in m:  # model-typed workflow names are never exported
            stray["workflow_name"] = stray.get("workflow_name", 0) + 1
    report("name fields hold only the names this proof uses (bash and prompt text cannot hide in them)", not stray,
           f"unexpected value counts={stray}")
    banned = [k for k in ("tool_parameters", "tool_input", "full_command", "bash_command", "arguments", "output",
                          "content", "error", "prompt", "user_email", "user_account_id") if k in keys]
    report("proof records carry no content or identity key", bool(lines) and not banned,
           f"records={len(lines)} banned={banned}")
    # Every tagged record's body must equal the Collector's fixed placeholder exactly (not a substring search).
    not_fixed = sum(1 for _, body, _ in lines if body != fixed_body)
    report(f"every Loki record's body is exactly {fixed_body!r} (transform/privacy set(body, ...))",
           bool(lines) and not_fixed == 0, f"records={len(lines)} not_fixed={not_fixed}")
    # Forbidden-string search over parsed values only (body + metadata values), never the raw serialized blob:
    # a short literal like `pwd` must not be able to false-positive on JSON brackets or an unrelated key name.
    all_values = {v for _, body, m in lines for v in record_values(body, m)}
    hits = sum(1 for f in forbidden if any(f in v for v in all_values))
    report("no executed command or prompt text (any length) is stored in a Loki record's body or metadata value",
           bool(forbidden) and hits == 0, f"strings checked={len(forbidden)} found={hits}")
    if events_lines is not None:
        parsed = []
        for line in events_lines:
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        bodies_values = [otlp_body_and_values(obj) for obj in parsed]
        not_fixed_e = sum(1 for body, _ in bodies_values if body is not None and body != fixed_body)
        report(f"every tagged events-file record's body is exactly {fixed_body!r}",
               bool(bodies_values) and not_fixed_e == 0,
               f"records={len(bodies_values)} not_fixed={not_fixed_e}")
        event_values = {v for body, vals in bodies_values for v in ([body] if isinstance(body, str) else []) + vals}
        event_hits = sum(1 for f in forbidden if any(f in v for v in event_values))
        banned_keys = [k for k in ("tool_parameters", "tool_input", "full_command", "arguments", "user.email")
                       if any(f'"key":"{k}"' in line for line in events_lines)]
        report("the Collector's events file holds the proof's records without command, prompt or content"
               " (any length), and without content/identity keys",
               bool(events_lines) and event_hits == 0 and not banned_keys,
               f"lines={len(events_lines)} value hits={event_hits} banned keys={banned_keys}")
    print("INFO structured metadata keys on proof records: " + ", ".join(keys))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("loki")
    parser.add_argument("task")
    parser.add_argument("deadline", type=float)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--forbidden-file", action="append", default=[])
    parser.add_argument("--window", default="30m")
    parser.add_argument("--collector", help="staged collector.yaml: the allowlists bound the metadata keys")
    parser.add_argument("--events-glob", help="Collector file/events output to scan for the proof's records")
    parser.add_argument("--streams-json", help="offline replay: a saved Loki query_range result in place of a "
                                                "live fetch (see offline_recheck.py / failing_first_ab.py)")
    args = parser.parse_args()
    task = args.task.replace('"', "")
    claude = '{service_name=~"claude-code.*"} | ecosystem_task_id="%s"' % task
    any_ = '{service_name=~".+"} | ecosystem_task_id="%s"' % task
    checks, zero_checks = build_checks(claude, any_, args.window)

    if args.dry_run:
        for name, expr, _ in checks + [(n, e, None) for n, e in zero_checks]:
            result, error = instant(args.loki, expr)
            report(f"dry run query parses and returns no series for a fresh task id: {name}",
                   error is None and not result, error or shown(result))
    elif args.streams_json:
        # Offline replay: assert against a saved/synthetic export instead of a live Loki fetch (no network).
        lines = streams_to_lines(json.load(open(args.streams_json)))
        forbidden = load_forbidden(args.forbidden_file)
        events_lines = None
        if args.events_glob:
            events_lines = [line for path in sorted(glob.glob(args.events_glob))
                            for line in open(path, errors="replace") if task in line]
        privacy_checks(lines, forbidden, args.collector, events_lines)
    else:
        deadline = time.time() + args.deadline
        pending = list(checks)
        while pending and time.time() < deadline:
            still = []
            for name, expr, predicate in pending:
                result, error = instant(args.loki, expr)
                if error is None and predicate(result):
                    report(name, True, shown(result))
                else:
                    still.append((name, expr, predicate))
            pending = still
            if pending and time.time() < deadline:
                time.sleep(10)
        for name, expr, _ in pending:
            result, error = instant(args.loki, expr)
            report(name + f" (within {args.deadline:g} s)", False, error or shown(result))
        for name, expr in zero_checks:
            result, error = instant(args.loki, expr)
            report(name, error is None and sum((result or {}).values()) == 0, error or shown(result or {}))

        lookback_s = int(args.window[:-1]) * {"s": 1, "m": 60, "h": 3600}[args.window[-1]]  # count queries' window
        lines = fetch_lines(args.loki, task, lookback_s)
        forbidden = load_forbidden(args.forbidden_file)
        events_lines = None
        if args.events_glob:
            events_lines = [line for path in sorted(glob.glob(args.events_glob))
                            for line in open(path, errors="replace") if task in line]
        privacy_checks(lines, forbidden, args.collector, events_lines)
    print(f"SUMMARY prove: {results['pass']} passed, {results['fail']} failed")
    return 1 if results["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
