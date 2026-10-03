#!/usr/bin/env python3
"""Collect the confirmatory gate's runs from the state directory into this folder.

usage: GATE_STATE=<state directory> gate_collect.py

For every run it writes sanitized copies of the Codex event log, the score, the run metadata, the last
message and Codex's stderr, plus an excerpt of the server log limited to the lines the receipt cites.
It prints a JSON summary (per run and per arm) that the receipt is built from.
Host paths become <STATE>, <HOME> and <SCRATCH>, the user name <user>, the host name <host>, and
session identifiers <uuid>.

Reporting script, not part of the wrapper or the scoring. Compared with the first gate's copy it also
reports, per run, the wall time, the tokens per second of each model call (from the servers'
print_timing lines), Ollama's per-request durations and the load average at the start of the run.
Local script, not an upstream component.
"""
import datetime
import getpass
import json
import os
import pathlib
import re
import socket
import sys

HERE = pathlib.Path(__file__).resolve().parent
STATE = os.environ["GATE_STATE"].rstrip("/")
HOME = str(pathlib.Path.home())
USER = getpass.getuser()
HOST = socket.gethostname()
UUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")
SCRATCH = re.compile(r"/tmp/claude-\d+[^\s\"'<>]*")
LABELS = ["warmup-A", "warmup-B", "A1", "B1", "A2", "B2", "A3", "B3"]
MAX_LINE = 40000

LLAMA_PATTERNS = [
    r"unsupported Responses tool type",
    r"Request converted: OpenAI Responses",
    r"ggml_cuda_init: failed to initialize CUDA",
    r"n_slots = \d+, n_ctx_slot",
    r"build_info|version: ",
    r"print_timing: .*(prompt eval time|       eval time|total time)",
    r"using differential autoparser",
]
OLLAMA_PATTERNS = [
    r'msg="parsed Responses tools"',
    r'\[GIN\].*"/v1/responses"',
    r'msg="inference compute"',
    r'msg="starting llama-server"',
    r'msg="using llama-server for model"',
    r'msg="template selection"',
    r'msg="llama-server completion request"',
    r"llama_context: n_ctx ",
    r"n_slots = \d+, n_ctx_slot",
    r"level=(WARN|ERROR)",
    r"prompt eval time|       eval time|total time",
]
TIMING = re.compile(
    r"print_timing: id\s+\d+ \| task\s+(-?\d+) \|\s+(prompt eval time|eval time|total time) =\s+([\d.]+) ms /\s+(\d+) tokens"
    r"(?: \(\s*[\d.]+ ms per token,\s+([\d.]+) tokens per second\))?"
)
GIN = re.compile(r'\[GIN\] \S+ - (\S+) \| (\d+) \|\s+(\S+) \|\s+\S+ \| POST\s+"/v1/responses"')


def san(text):
    text = text.replace(STATE, "<STATE>").replace(HOME, "<HOME>")
    text = SCRATCH.sub("<SCRATCH>", text)
    text = text.replace(USER, "<user>")
    if HOST and len(HOST) > 3:
        text = text.replace(HOST, "<host>")
    return UUID.sub("<uuid>", text)


def read(path):
    return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")


def meta(path):
    out = {}
    for line in read(path).splitlines():
        key, _, value = line.partition("=")
        out[key] = value
    return out


def seconds_between(start, end):
    if not start or not end:
        return None
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return int((datetime.datetime.strptime(end, fmt) - datetime.datetime.strptime(start, fmt)).total_seconds())


def model_calls(lines):
    """One entry per model call that the server finished and timed (print_timing lines)."""
    calls, current = [], None
    for line in lines:
        match = TIMING.search(line)
        if not match:
            continue
        _, what, ms, tokens, tps = match.groups()
        if what == "prompt eval time":
            current = {"prompt_tokens": int(tokens), "prompt_tokens_per_second": float(tps) if tps else None,
                       "generated_tokens": None, "generation_tokens_per_second": None, "total_ms": None}
            calls.append(current)
        elif current is not None and what == "eval time":
            current["generated_tokens"] = int(tokens)
            current["generation_tokens_per_second"] = float(tps) if tps else None
        elif current is not None and what == "total time":
            current["total_ms"] = float(ms)
    return calls


def first_converted_request(lines):
    """llama-server --verbose logs the request after its Responses -> Chat Completions conversion."""
    for number, line in enumerate(lines, 1):
        marker = "converted request: "
        at = line.find(marker)
        if at < 0:
            continue
        try:
            body, _ = json.JSONDecoder().raw_decode(line[at + len(marker):])
        except ValueError:
            return number, line, None
        return number, line, body
    return None, None, None


def excerpt(arm, lines):
    patterns = [re.compile(p) for p in (LLAMA_PATTERNS if arm == "llama" else OLLAMA_PATTERNS)]
    kept = []
    for number, line in enumerate(lines, 1):
        if any(p.search(line) for p in patterns):
            text = san(line)
            if len(text) > MAX_LINE:
                text = text[:MAX_LINE] + " …[line cut]"
            kept.append(f"{number}: {text}")
    return kept


def load_at_start():
    path = pathlib.Path(STATE) / "runs" / "load.tsv"
    out = {}
    if path.exists():
        for line in read(path).splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                out[parts[0]] = parts[2]
    return out


def main():
    out_runs = HERE / "runs"
    out_runs.mkdir(exist_ok=True)
    loads = load_at_start()
    summary = {"runs": [], "arms": {}}
    for label in LABELS:
        src = pathlib.Path(STATE) / "runs" / label
        if not (src / "run-meta.txt").exists():
            continue
        dst = out_runs / label
        dst.mkdir(exist_ok=True)
        info = meta(src / "run-meta.txt")
        arm = info.get("arm")
        for name in ("events.jsonl", "score.json", "run-meta.txt", "last-message.txt", "codex-stderr.txt"):
            if (src / name).exists():
                (dst / name).write_text(san(read(src / name)), encoding="utf-8")
        log_lines = read(src / "server.log").splitlines() if (src / "server.log").exists() else []
        kept = excerpt(arm, log_lines)
        header = [
            f"# Excerpt of the {arm} server log of run {label}: only the lines the receipt cites,",
            "# each prefixed with its line number in the full log. Paths, user and session ids are replaced.",
            f"# Full log: {len(log_lines)} lines, kept in the state directory, not published.",
        ]
        extra = []
        tools_passed = None
        if arm == "llama":
            number, line, body = first_converted_request(log_lines)
            if line is not None:
                extra.append(f"{number}: {san(line)[:MAX_LINE]}")
            if body is not None:
                tools_passed = [(t.get("function") or {}).get("name") for t in body.get("tools", [])]
        (dst / "server-log-excerpt.txt").write_text("\n".join(header + kept + extra) + "\n", encoding="utf-8")
        score = json.loads(read(src / "score.json")) if (src / "score.json").exists() else {}
        skip_lines = [k for k in kept if "unsupported Responses tool type" in k]
        parsed_lines = [k for k in kept if "parsed Responses tools" in k]
        gin_lines = [k for k in kept if "[GIN]" in k]
        gin_durations = [m.group(3) for m in (GIN.search(line) for line in log_lines) if m]
        calls = score.get("mcp_tool_calls", [])
        summary["runs"].append({
            "label": label,
            "arm": "A (llama-server)" if arm == "llama" else "B (Ollama)",
            "scored": not label.startswith("warmup"),
            "server_pid": int(info.get("server_pid", 0)),
            "server_started_utc": info.get("server_started_utc"),
            "server_ready_utc": info.get("server_ready_utc"),
            "codex_finished_utc": info.get("codex_finished_utc"),
            "server_stopped_utc": info.get("server_stopped_utc"),
            "server_alive_after_stop": info.get("server_alive_after_stop"),
            "wall_time_s": seconds_between(info.get("server_ready_utc"), info.get("codex_finished_utc")),
            "load_average_at_start_1_5_15_min": loads.get(label),
            "codex_exit_code": score.get("codex_exit_code"),
            "turn_status": score.get("turn_status"),
            "completed_item_types": score.get("completed_item_types"),
            "mcp_tool_calls": calls,
            "target_tool_called": any(c.get("tool") == "get_current_time" for c in calls),
            "tool_call_completed": score.get("tool_call_completed"),
            "tool_result_datetimes": score.get("tool_result_datetimes"),
            "final_answer": san(score.get("final_answer") or "") or None,
            "final_answer_contains_result": score.get("final_answer_contains_result"),
            "run_pass": score.get("run_pass"),
            "reason": score.get("reason"),
            "error_events": [san(e) for e in score.get("error_events", [])],
            "model_calls": model_calls(log_lines),
            "server_log": {
                "skipped_tool_type_lines": skip_lines,
                "function_tools_passed_to_model_first_request": tools_passed,
                "parsed_responses_tools_lines": parsed_lines,
                "responses_http_lines": gin_lines,
                "ollama_responses_request_durations": gin_durations,
            },
        })
    for arm in ("A", "B"):
        scored = [r for r in summary["runs"] if r["scored"] and r["arm"].startswith(arm)]
        summary["arms"][arm] = {
            "scored_runs": len(scored),
            "runs_passed": sum(1 for r in scored if r["run_pass"]),
            "tool_call_completed_runs": sum(1 for r in scored if r["tool_call_completed"]),
            "pass": len(scored) == 3 and all(r["run_pass"] for r in scored),
        }
    pids = pathlib.Path(STATE) / "runs" / "pids.tsv"
    if pids.exists():
        (out_runs / "pids.tsv").write_text("label\trole\tpid\tchild_pids_at_stop\n" + san(read(pids)), encoding="utf-8")
    loads_file = pathlib.Path(STATE) / "runs" / "load.tsv"
    if loads_file.exists():
        (out_runs / "load.tsv").write_text("label\tutc\tload_average_1_5_15_min\n" + read(loads_file), encoding="utf-8")
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
