#!/usr/bin/env python3
"""Independently audit retained, privately scoped native protocol. No model calls."""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = b'{"ids":["alpha","bravo","charlie","delta"],"total":18}\n'


def audit(private_root):
    private_root = Path(private_root)
    logs = []
    for name in ("connection-1", "connection-2"):
        path = private_root / (name + ".protocol.jsonl")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        logs.append(rows)

    def request(rows, method):
        found = [x["message"] for x in rows if x["direction"] == "client"
                 and x["message"].get("method") == method]
        assert len(found) == 1, "Expected exactly one " + method
        return found[0]

    def response(rows, req):
        found = [x["message"] for x in rows if x["direction"] == "server"
                 and x["message"].get("id") == req["id"] and "result" in x["message"]]
        assert len(found) == 1, "Expected one native response"
        return found[0]["result"]

    first, second = logs
    start = response(first, request(first, "thread/start"))
    resume_request = request(second, "thread/resume")
    resumed = response(second, resume_request)
    thread_id = start["thread"]["id"]
    assert resume_request["params"] == {"threadId": thread_id}, "Resume must use only existing ID"
    assert resumed["thread"]["id"] == thread_id, "Thread identity changed"
    assert start["thread"]["sessionId"] == resumed["thread"]["sessionId"], "Session identity changed"
    assert len([x for rows in logs for x in rows if x["message"].get("method") == "thread/start"]) == 1
    for result in (start, resumed):
        assert (result["model"], result["reasoningEffort"]) == ("gpt-6-astra", "ultra")
    for rows in logs:
        request(rows, "initialize")
        config_ids = {x["message"]["id"] for x in rows if x["message"].get("method") == "config/read"}
        for row in rows:
            obj = row["message"]
            if row["direction"] == "server" and obj.get("id") in config_ids and "result" in obj:
                assert set(obj["result"]["config"]) <= {"model", "model_reasoning_effort"}

    calls = [(i, x["message"]) for i, rows in enumerate(logs) for x in rows
             if x["direction"] == "server" and x["message"].get("method") == "item/tool/call"]
    assert [(i, m["params"]["tool"], m["params"]["arguments"]) for i, m in calls] == [
        (0, "recovery_step", {"action": "checkpoint"}),
        (0, "recovery_step", {"action": "wait"}),
        (1, "recovery_step", {"action": "finalize"})], "Wrong native action sequence"
    for i, obj in calls:
        assert obj["params"]["threadId"] == thread_id
        returns = [x["message"] for x in logs[i] if x["direction"] == "client"
                   and x["message"].get("id") == obj["id"] and "result" in x["message"]]
        if obj["params"]["arguments"]["action"] == "wait":
            assert returns == [], "Pending wait incorrectly received a tool result"
        else:
            assert len(returns) == 1 and returns[0]["result"]["success"] is True
            payload = json.loads(returns[0]["result"]["contentItems"][0]["text"])
            assert payload["execution_count"] == 1
            assert payload["checkpoint_sha256"] == hashlib.sha256(EXPECTED).hexdigest()

    interrupt = request(first, "turn/interrupt")
    assert response(first, interrupt) == {}
    statuses = []
    for i, rows in enumerate(logs):
        turn_id = response(rows, request(rows, "turn/start"))["turn"]["id"]
        completed = [x["message"]["params"]["turn"] for x in rows
                     if x["message"].get("method") == "turn/completed"]
        assert len(completed) == 1 and completed[0]["id"] == turn_id
        statuses.append(completed[0]["status"])
        if i == 0:
            assert interrupt["params"] == {"threadId": thread_id, "turnId": turn_id}
    assert statuses == ["interrupted", "completed"]
    assert (private_root / "fixture/checkpoint.json").read_bytes() == EXPECTED
    final = json.loads((private_root / "fixture/final.json").read_text())
    assert final == {"checkpoint_sha256": hashlib.sha256(EXPECTED).hexdigest(),
                     "execution_count": 1, "status": "complete"}
    snapshots = [x["message"]["params"]["tokenUsage"]["total"] for rows in logs for x in rows
                 if x["message"].get("method") == "thread/tokenUsage/updated"
                 and x["message"]["params"]["threadId"] == thread_id]
    assert snapshots and all(a["totalTokens"] <= b["totalTokens"] for a, b in zip(snapshots, snapshots[1:]))
    total = snapshots[-1]
    assert total["inputTokens"] + total["outputTokens"] == total["totalTokens"]
    assert total["cachedInputTokens"] <= total["inputTokens"]
    assert total["reasoningOutputTokens"] <= total["outputTokens"]
    builtin_commands = sum(x["message"].get("method") == "item/started" and
                           x["message"].get("params", {}).get("item", {}).get("type") == "commandExecution"
                           for rows in logs for x in rows)
    assert builtin_commands == 0
    return {"status": "passed", "native_thread_start_requests": 1,
            "native_resume_requests": 1, "same_thread_and_session_identity": True,
            "new_connection_initialize_requests": 2,
            "native_tool_actions": ["checkpoint", "wait", "finalize"],
            "unfinished_wait_received_no_tool_response": True,
            "turn_statuses": statuses, "native_builtin_command_items": builtin_commands,
            "checkpoint_sha256": hashlib.sha256(EXPECTED).hexdigest(),
            "native_usage_snapshots": len(snapshots), "final_native_total": total,
            "private_configuration_response_allowlist_passed": True,
            "limits": "Independent deterministic inspection of retained native protocol and fixture bytes; no new provider call, no independent-host recovery, and no arbitrary descendant cleanup claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_run_dir")
    args = parser.parse_args()
    print(json.dumps(audit(args.private_run_dir), indent=2, sort_keys=True))
