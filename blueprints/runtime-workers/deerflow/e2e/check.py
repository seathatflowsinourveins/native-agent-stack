"""Pre-grader transport sanity only. Never a task-success verdict.

DeerFlow v2.1.0 client.py:538-565,830-910: values contain complete messages;
messages-tuple contains deltas and must not be appended to the values snapshot.
The final answer is handed unchanged to Inspect Evals v0.22.0 gaia_scorer.
No targets, answer normalization, generated-code execution or local oracle.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def read_completion(trace):
    path = Path(trace)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000_000:
        raise ValueError("missing or oversized native trace")
    snapshot = None
    ended = False
    with path.open() as events:
        for line in events:
            try:
                record = json.loads(line)
            except ValueError as exc:
                raise ValueError("malformed native event") from exc
            if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
                raise ValueError("malformed native event")
            if ended or record.get("type") == "error":
                raise ValueError("failed or ambiguous native completion")
            if record.get("type") == "values":
                snapshot = record["data"].get("messages")
            if record.get("type") == "end":
                ended = True
    if not ended or not isinstance(snapshot, list) or not snapshot:
        raise ValueError("native end and final values snapshot are required")
    final = snapshot[-1]
    if not isinstance(final, dict) or final.get("type") != "ai" or final.get("tool_calls"):
        raise ValueError("last message must be a final assistant answer")
    content = final.get("content")
    if isinstance(content, list):
        # Match the upstream client's text-block extraction without coercion.
        chunks = []
        for block in content:
            if not isinstance(block, dict):
                raise ValueError("malformed assistant content block")
            if block.get("type") in {"text", "output_text"}:
                if not isinstance(block.get("text"), str):
                    raise ValueError("malformed assistant text block")
                chunks.append(block["text"])
        content = "".join(chunks)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("missing assistant answer")
    return content


if __name__ == "__main__":
    try:
        read_completion(sys.argv[1])
        result = {"transport_ok": True, "verdict": "deferred to upstream gaia_scorer"}
    except (OSError, ValueError, IndexError) as exc:
        result = {"transport_ok": False, "error_class": type(exc).__name__}
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["transport_ok"] else 1)
