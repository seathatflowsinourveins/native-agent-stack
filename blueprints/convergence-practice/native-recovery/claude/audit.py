#!/usr/bin/env python3
"""Inspect this owned native trial's retained streams; never calls a model."""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = b'{"ids":["alpha","bravo","charlie","delta"],"total":18}\n'


def audit(root):
    root = Path(root)
    streams = [[json.loads(line) for line in (root / (name + ".stream.jsonl")).read_text().splitlines()]
               for name in ("initial", "resumed")]
    identities, commands, terminals = [], [], []
    for stream in streams:
        inits = [x for x in stream if x.get("type") == "system" and x.get("subtype") == "init"]
        assert len(inits) == 1 and inits[0]["model"] == "claude-opus-5"
        identities.append(inits[0]["session_id"])
        calls = [b for x in stream if x.get("type") == "assistant"
                 for b in x["message"]["content"] if b.get("type") == "tool_use"]
        assert all(c["name"] == "Bash" for c in calls)
        commands.append([c["input"]["command"] for c in calls])
        results = [x for x in stream if x.get("type") == "result"]
        assert len(results) == 1
        assert results[0]["session_id"] == identities[-1]
        terminals.append(results[0])
    expected_id = json.loads((root / "native-identity.json").read_text())["session_id"]
    assert identities == [expected_id, expected_id]
    assert commands == [["python3 stage.py checkpoint", "python3 stage.py wait"],
                        ["python3 stage.py finalize"]]
    assert terminals[1]["subtype"] == "success" and terminals[1]["is_error"] is False
    journal = [json.loads(line)["action"] for line in (root / "fixture/actions.jsonl").read_text().splitlines()]
    assert journal == ["checkpoint", "wait", "finalize"]
    assert (root / "fixture/checkpoint.json").read_bytes() == EXPECTED
    final = json.loads((root / "fixture/final.json").read_text())
    assert final == {"checkpoint_sha256": hashlib.sha256(EXPECTED).hexdigest(),
                     "execution_count": 1, "status": "complete"}
    usage = [t["usage"] for t in terminals]
    field_map = {"input_tokens": "inputTokens", "cache_creation_input_tokens": "cacheCreationInputTokens",
                 "cache_read_input_tokens": "cacheReadInputTokens", "output_tokens": "outputTokens"}
    combined = {key: sum(u[key] for u in usage) for key in field_map}
    final_model = terminals[1]["modelUsage"]["claude-opus-5"]
    assert all(combined[key] == final_model[native] for key, native in field_map.items())
    assert sum(u["output_tokens_details"]["thinking_tokens"] for u in usage) == final_model["thinkingTokens"]
    totals = [sum(u[key] for key in field_map) for u in usage]
    return {"status": "passed", "native_session_identity_preserved": True,
            "native_model_both_invocations": "claude-opus-5",
            "native_bash_commands": commands, "action_journal": journal,
            "checkpoint_sha256": hashlib.sha256(EXPECTED).hexdigest(),
            "initial_result_subtype": terminals[0]["subtype"],
            "resumed_result_subtype": terminals[1]["subtype"],
            "usage_reconciliation": {"per_invocation_terminal_totals": totals,
                                     "combined_disjoint_categories": combined,
                                     "combined_tokens": sum(totals),
                                     "matches_resumed_cumulative_model_usage": True,
                                     "thinking_is_already_in_output": True,
                                     "native_retries": None, "billing": None,
                                     "enclosing_coordinator_usage": None, "savings_claim": None},
            "limits": "Independent retained-stream and artifact review confirms identities, actions and usage reconciliation. SIGINT timing and live-process observations are supervisor evidence; provider cancellation remains unknown."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_run_dir")
    args = parser.parse_args()
    print(json.dumps(audit(args.private_run_dir), indent=2, sort_keys=True))
