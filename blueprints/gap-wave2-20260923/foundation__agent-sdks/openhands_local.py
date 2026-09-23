#!/usr/bin/env python3
"""OpenHands software-agent-sdk local conversation with the SDK's scripted TestLLM.

No provider is called: `openhands.sdk.testing.TestLLM` (upstream) returns scripted
assistant messages, while the SDK's real agent loop, terminal tool execution,
event log and file-based conversation persistence run locally.
Phase `first`: the scripted agent runs one terminal command in the workspace and
finishes. Phase `reload` (a new process): the same conversation id is loaded from
the persistence dir, prior events are counted, and one more scripted turn runs.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from openhands.sdk import Agent, Conversation, Tool
from openhands.sdk.llm import Message, MessageToolCall, TextContent
from openhands.sdk.testing import TestLLM
from openhands.tools.terminal import TerminalTool

CONV_ID = uuid.uuid5(uuid.NAMESPACE_URL, "gap-wave2-20260923/agent-sdks/openhands")  # fixed across both phases


def call(name: str, args: dict, cid: str) -> Message:
    return Message(role="assistant", content=[TextContent(text="")],
                   tool_calls=[MessageToolCall(id=cid, name=name, arguments=json.dumps(args), origin="completion")])


def main() -> int:
    phase, workspace, persist, out = sys.argv[1:5]
    if phase == "first":
        script = [call(TerminalTool.name, {"command": "echo gap8-openhands-$PPID > proof.txt && cat proof.txt"}, "c1"),
                  call("finish", {"message": "wrote proof.txt"}, "c2")]
    else:
        script = [call(TerminalTool.name, {"command": "cat proof.txt"}, "c3"),
                  call("finish", {"message": "read proof.txt after reload"}, "c4")]
    llm = TestLLM.from_messages(script)
    agent = Agent(llm=llm, tools=[Tool(name=TerminalTool.name)])
    conv = Conversation(agent=agent, workspace=workspace, persistence_dir=persist, conversation_id=CONV_ID,
                        visualizer=None)
    rec = {"phase": phase, "pid": os.getpid()}
    rec["events_before"] = len(conv.state.events)
    conv.send_message("Write proof.txt" if phase == "first" else "Read proof.txt again")
    conv.run()
    events = list(conv.state.events)
    rec["events_after"] = len(events)
    rec["event_types"] = [type(e).__name__ for e in events]
    obs = [e for e in events if type(e).__name__ == "ObservationEvent"]
    rec["observations"] = [str(getattr(e, "observation", ""))[:300] for e in obs]
    rec["execution_status"] = str(conv.state.execution_status)
    rec["proof_file"] = (Path(workspace) / "proof.txt").read_text().strip() if (Path(workspace) / "proof.txt").exists() else None
    rec["llm_calls"] = llm._call_count
    conv.close()
    Path(out).write_text(json.dumps(rec, indent=2, default=str))
    print(json.dumps({k: rec[k] for k in ("phase", "events_before", "events_after", "execution_status", "proof_file")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
