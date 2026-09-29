"""Usage and timing of one `codex exec --json` review, from its event stream: the turn.completed usage blocks, the
event count by type and the start and finish times. No thread id, message text or command text is copied.

usage: gpt6_review_usage.py EVENTS.jsonl STARTED FINISHED
"""
import json
import sys
from collections import Counter

events = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
types = Counter(e.get("type") for e in events)
items = Counter((e.get("item") or {}).get("type") for e in events if e.get("type") == "item.completed")
turns = [e.get("usage") for e in events if e.get("type") == "turn.completed"]
failed = [e.get("type") for e in events if e.get("type") in ("turn.failed", "error")]
print(json.dumps({
    "model": "gpt-6-astra", "effort": "max", "sandbox": "read-only", "web_search": "live",
    "started": open(sys.argv[2]).read().strip(), "finished": open(sys.argv[3]).read().strip(),
    "events": sum(types.values()), "event_types": dict(sorted(types.items())),
    "completed_items": dict(sorted(items.items())),
    "turn_usage": turns, "failures": failed,
    "note": "Codex usage fields as reported per turn; cached_input_tokens is a subset of input_tokens and "
            "reasoning_output_tokens a subset of output_tokens, so they are never added.",
}, indent=1))
