"""Replay the retained marker oracle; this performs no model request."""

import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("artifact", type=Path)
parser.add_argument("expected_marker")
args = parser.parse_args()
raw = args.artifact.read_text()
if args.artifact.suffix == ".json":
    observed = json.loads(raw)["final_response"]
elif args.artifact.suffix in {".jsonl", ".ndjson"}:
    messages = [event["item"]["text"] for line in raw.splitlines()
                if (event := json.loads(line)).get("type") == "item.completed"
                and event.get("item", {}).get("type") == "agent_message"]
    if len(messages) != 1:
        raise ValueError("expected exactly one retained assistant message")
    observed = messages[0]
else:
    observed = raw
matched = observed.strip() == args.expected_marker
print(json.dumps({"artifact": args.artifact.name, "expected_marker": args.expected_marker,
                  "observed_marker": observed.strip(), "match": matched}, sort_keys=True))
raise SystemExit(0 if matched else 1)
