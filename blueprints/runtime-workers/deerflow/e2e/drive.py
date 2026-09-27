"""Use DeerFlow's unchanged embedded client; v2.1.0 client.py:179-210,770-910.

Raw framework events remain in private run storage. The receipt reports only
allowlisted observations from those events, never raw prompts or model output.
"""
import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path

from deerflow.client import DeerFlowClient
from deerflow.config.paths import get_paths
from deerflow.runtime.user_context import get_effective_user_id


def main():
    thread = "release-research"
    print(json.dumps({"type": "worker-version", "data": {
        "framework_version": importlib.metadata.version("deerflow-harness")
    }}), flush=True)
    client = DeerFlowClient(config_path=os.environ["DEER_FLOW_CONFIG_PATH"],
                            model_name="worker", thinking_enabled=True,
                            subagent_enabled=True, plan_mode=True)
    for event in client.stream(Path("/runtime/task.md").read_text(), thread_id=thread,
                               recursion_limit=100):
        # The host captures this pipe outside all mounts visible to this worker.
        print(json.dumps({"type": event.type, "data": event.data}, default=str), flush=True)
    out = Path("/run-artifacts")
    out.mkdir(exist_ok=True)
    origin = get_paths().sandbox_outputs_dir(thread, user_id=get_effective_user_id())
    for name in ("files.json", "summarize.py", "report.json"):
        path = origin / name
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 1_000_000:
            shutil.copyfile(path, out / name)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Full private native logs are captured separately by the runner.
        print("DeerFlow run failed: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1) from None
