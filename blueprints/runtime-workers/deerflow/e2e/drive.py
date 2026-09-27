"""Native client transport, DeerFlow v2.1.0 client.py:770-910,1255-1277.

The host captures framework events outside every worker-visible mount. Inspect's
GAIA input is supplied unchanged; no answer target or scorer is mounted here.
"""
import importlib.metadata
import json
import os
import sys
from pathlib import Path

from deerflow.client import DeerFlowClient


def main():
    print(json.dumps({"type": "worker-version", "data": {
        "framework_version": importlib.metadata.version("deerflow-harness")
    }}), flush=True)
    client = DeerFlowClient(config_path=os.environ["DEER_FLOW_CONFIG_PATH"],
                            model_name="worker", thinking_enabled=True,
                            subagent_enabled=True, plan_mode=True)
    inventory = client.list_skills(enabled_only=True)
    print(json.dumps({"type": "worker-skills", "data": {
        "names": sorted(s["name"] for s in inventory["skills"])
    }}), flush=True)
    for event in client.stream(Path("/run-input.txt").read_text(),
                               thread_id=os.environ["DEERFLOW_CONVERSATION_ID"], recursion_limit=100):
        print(json.dumps({"type": event.type, "data": event.data}, default=str), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("DeerFlow run failed: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1) from None
