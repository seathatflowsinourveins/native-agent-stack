#!/usr/bin/env python3
"""Independently inspect the returned native transcripts of the schema fault controls.

This local observation uses JSON tree differences, not the harness's passed field.
The fault seam is pinned upstream src/serena/mcp.py:281 (make_mcp_tool).
"""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def delta(before, after, path=""):
    if isinstance(before, dict) and isinstance(after, dict) and before.keys() == after.keys():
        return [item for key in before for item in delta(before[key], after[key], f"{path}.{key}")]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [item for index, (left, right) in enumerate(zip(before, after))
                for item in delta(left, right, f"{path}[{index}]" )]
    return [] if before == after else [{"path": path.removeprefix("."), "before": before, "after": after}]


baseline = {context: (ROOT / "independent" / f"{context}.stdout.txt").read_bytes().splitlines(keepends=True)
            for context in ("claude-code", "codex")}
rows = []
for name, target in (("changed-schema-claude", "claude-code"), ("changed-schema-codex", "codex")):
    receipt = json.loads((ROOT / name / "receipt.json").read_text())
    commands = [command for command in receipt["commands"] if "mcp_exchange" in command]
    observed = []
    for context, command in zip(baseline, commands):
        lines = command["stdout"].encode().splitlines(keepends=True)
        differences = delta(json.loads(baseline[context][1]), json.loads(lines[1]))
        assert lines[0] == baseline[context][0]
        assert command["exit_code"] == 0
        names = lambda line: [tool["name"] for tool in json.loads(line)["result"]["tools"]]
        assert names(lines[1]) == names(baseline[context][1])
        assert command["stderr"].count("[SCHEMA-CONTROL]") == (1 if context == target else 0)
        if context == target:
            assert len(differences) == 1
            assert differences[0]["path"].endswith(".inputSchema.properties.needle.type") or (
                differences[0]["path"].endswith(".inputSchema.properties.substring_pattern.type"))
            assert differences[0]["before"] == "string" and differences[0]["after"] == "integer"
        else:
            assert lines[1] == baseline[context][1] and not differences
        observed.append({"context": context, "native_exit_code": command["exit_code"],
                         "initialize_bytes_unchanged": True, "tool_names_unchanged": True,
                         "schema_differences": differences,
                         "tools_list_sha256": hashlib.sha256(lines[1]).hexdigest()})
    rows.append({"control": name, "target": target, "observations": observed,
                 "receipt_sha256": hashlib.sha256((ROOT / name / "receipt.json").read_bytes()).hexdigest()})
report = {"evidence_class": "independent_artifact_observation",
          "method": "Exact initialize bytes, JSON tree deltas, tool names, native exit codes and runtime fault markers",
          "limits": ["Local deliberate faults; they do not establish any historical dependency cause"], "controls": rows}
(ROOT / "controls-observation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
