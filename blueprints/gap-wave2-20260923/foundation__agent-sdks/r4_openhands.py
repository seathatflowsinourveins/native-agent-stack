#!/usr/bin/env python3
"""Round 4, gap 8: OpenHands software-agent-sdk conversation with a real (local) model.

The model is Qwen3-4B-Instruct-2507-FP8 served by this unit's loopback vLLM (127.0.0.1:28431),
reached through LiteLLM's OpenAI-compatible route. The agent gets the SDK's terminal and file-editor
tools and must create a file whose content includes a random token that only the prompt carries.
Mode `local` uses a LocalWorkspace conversation. Mode `remote` connects to an openhands-agent-server
process on a loopback port (Workspace(host=...)) and runs the same task as a RemoteConversation;
mode `container` does the same against the official agent-server image run by rootless podman
(host network, server bound to 127.0.0.1), with WORKSPACE a path inside the container.
Usage: r4_openhands.py MODE WORKSPACE PERSIST_DIR OUT [SERVER_URL]
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r4_common import delta, metrics, wait_idle  # noqa: E402

from pydantic import SecretStr  # noqa: E402

from openhands.sdk import LLM, Agent, Conversation, Tool  # noqa: E402
from openhands.tools.file_editor import FileEditorTool  # noqa: E402
from openhands.tools.terminal import TerminalTool  # noqa: E402


def main() -> int:
    mode, workspace, persist, out = sys.argv[1:5]
    server = sys.argv[5] if len(sys.argv) > 5 else None
    token = "oh-r4-" + secrets.token_hex(5)
    rec: dict = {"mode": mode, "pid": os.getpid(), "started_at": time.time()}
    llm = LLM(model="openai/qwen3-4b", base_url="http://127.0.0.1:28431/v1", api_key=SecretStr("dummy-local"),
              usage_id="r4-agent", temperature=0.0, max_output_tokens=2048, num_retries=1)
    agent = Agent(llm=llm, tools=[Tool(name=TerminalTool.name), Tool(name=FileEditorTool.name)])
    target = str(Path(workspace) / "proof.txt")
    task = (f"Create the file {target} (use this absolute path) whose only line is {token} . "
            f"Use a tool to create it, then verify it with `cat {target}`, then finish.")
    m0 = wait_idle()
    try:
        if mode == "local":
            conv = Conversation(agent=agent, workspace=workspace, persistence_dir=persist, visualizer=None)
        else:
            from openhands.sdk import Workspace
            ws = Workspace(host=server, working_dir=workspace)
            conv = Conversation(agent=agent, workspace=ws, visualizer=None)
            rec["conversation_class"] = type(conv).__name__
        conv.send_message(task)
        conv.run()
        events = list(conv.state.events)
        rec["event_types"] = [type(e).__name__ for e in events]
        rec["actions"] = [str(getattr(getattr(e, "action", None), "__class__", type(None)).__name__)
                          for e in events if type(e).__name__ == "ActionEvent"]
        rec["tool_names"] = [getattr(e, "tool_name", None) for e in events if type(e).__name__ == "ActionEvent"]
        rec["execution_status"] = str(conv.state.execution_status)
        stats = getattr(conv, "conversation_stats", None) or getattr(conv.state, "stats", None)
        try:
            usage = stats.get_combined_metrics() if stats is not None else None
            rec["sdk_metrics"] = usage.model_dump(mode="json") if usage is not None else None
            if isinstance(rec["sdk_metrics"], dict):
                rec["sdk_metrics"] = {k: rec["sdk_metrics"].get(k) for k in ("accumulated_token_usage", "accumulated_cost")}
        except Exception as error:  # metrics are secondary
            rec["sdk_metrics_error"] = f"{type(error).__name__}: {error}"[:300]
        if mode != "local":
            try:  # read the file back through the workspace API (for the container it lives in the container)
                res = ws.execute_command(f"cat {target}")
                rec["workspace_cat"] = {"exit_code": getattr(res, "exit_code", None),
                                        "stdout_has_token": token in (getattr(res, "stdout", "") or "")}
            except Exception as error:
                rec["workspace_cat_error"] = f"{type(error).__name__}: {error}"[:300]
        conv.close()
        rec["status"] = "ok"
    except Exception as error:
        rec["status"] = "failed"
        rec["error"] = f"{type(error).__name__}: {str(error)[:1500]}"
    rec["provider_delta"] = delta(m0, metrics())
    proof = Path(workspace) / "proof.txt"
    rec["proof_file_exists"] = proof.is_file() if mode != "container" else None
    rec["proof_file_has_token"] = ((proof.is_file() and token in proof.read_text()) if mode != "container"
                                   else (rec.get("workspace_cat") or {}).get("stdout_has_token"))
    rec["token_in_prompt_only"] = True
    rec["finished_at"] = time.time()
    Path(out).write_text(json.dumps(rec, indent=2, default=str) + "\n")
    print(json.dumps({k: rec.get(k) for k in ("mode", "status", "execution_status", "proof_file_has_token")}))
    return 0 if rec["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
