#!/usr/bin/env python3
"""Round 3, gap 10 synthetic arm: native-schema samples through the SDK's notification handling.

For each server-notification method in the native `codex app-server generate-json-schema --experimental`
output, build a minimal (required fields only) and a maximal (every declared property) params sample,
validate both against the native schema with jsonschema, then pass them through the SDK's own
CodexClient._coerce_notification and a MessageRouter. A negative control drops one required field
and must come back as UnknownNotification. Usage: schema_dispatch.py SCHEMA_DIR OUT
"""
from __future__ import annotations

import copy
import json
import queue
import sys
import threading
from pathlib import Path

import jsonschema

from openai_codex.client import CodexClient
from openai_codex.generated.notification_registry import NOTIFICATION_MODELS
from openai_codex.models import UnknownNotification
from openai_codex._message_router import MessageRouter


def resolve(schema, root: dict) -> dict:
    if not isinstance(schema, dict):  # boolean subschema (`true` accepts anything)
        return {}
    while "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        schema = {**root["definitions"][name], **{k: v for k, v in schema.items() if k != "$ref"}}
    return schema


def valid(value, schema, root: dict) -> bool:
    try:
        jsonschema.validate(value, {**resolve(schema, root), "definitions": root["definitions"]})
        return True
    except jsonschema.ValidationError:
        return False


def sample(schema, root: dict, full: bool, depth: int = 0):
    """Build a params sample; for oneOf/anyOf, the first branch whose sample validates is used."""
    schema = resolve(schema, root)
    if depth > 14:
        return None
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    for key in ("oneOf", "anyOf"):
        if key in schema:
            base = {k: v for k, v in schema.items() if k != key}
            options = sorted(schema[key], key=lambda o: resolve(o, root).get("type") == "null")
            fallback = None
            for option in options:
                opt = resolve(option, root)
                union = {**base, **opt,
                         "properties": {**base.get("properties", {}), **opt.get("properties", {})},
                         "required": list(dict.fromkeys([*base.get("required", []), *opt.get("required", [])]))}
                # Two merges of the parent keywords with the branch; the first native-valid sample wins.
                for merged in (union, {**base, **opt}):
                    candidate = sample(merged, root, full, depth + 1)
                    if valid(candidate, schema, root):
                        return candidate
                    fallback = candidate if fallback is None else fallback
            return fallback
    if "allOf" in schema:
        parts = [resolve(p, root) for p in schema["allOf"]]
        if len(parts) == 1:
            return sample({**{k: v for k, v in schema.items() if k != "allOf"}, **parts[0]}, root, full, depth + 1)
        merged: dict = {"type": "object", "properties": {}, "required": []}
        for part in parts:
            merged["properties"].update(part.get("properties", {}))
            merged["required"].extend(part.get("required", []))
        return sample(merged, root, full, depth + 1)
    if not schema:
        return None if not full else "x"
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "null")
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        required = schema.get("required", [])
        keys = list(dict.fromkeys([*props, *required])) if full else required
        extra = schema.get("additionalProperties")
        return {k: sample(props.get(k, extra if isinstance(extra, dict) else {}), root, full, depth + 1) for k in keys}
    if t == "array":
        items = schema.get("items")
        return [sample(items, root, full, depth + 1)] if full and isinstance(items, dict) else []
    if t == "string":
        return "x"
    if t == "integer":
        return max(0, int(schema.get("minimum", 0)))
    if t == "number":
        return 0.0
    if t == "boolean":
        return False
    return None


def deliver(n) -> str:
    """Route one notification through a fresh MessageRouter with the matching consumer registered.

    Returns the queue it was delivered to ("turn", "login" or "global"), or "not_delivered" if the
    consumer did not receive the same object within one second.
    """
    router = MessageRouter()
    login_id, turn_id = router._notification_login_id(n), router._notification_turn_id(n)
    if login_id is not None:
        router.register_login(login_id)
        kind, get = "login", lambda: router.next_login_notification(login_id)
    elif turn_id is not None:
        router.register_turn(turn_id)
        kind, get = "turn", lambda: router.next_turn_notification(turn_id)
    else:
        kind, get = "global", router.next_global_notification
    router.route_notification(n)
    box: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: box.put(get()), daemon=True).start()
    try:
        return kind if box.get(timeout=1) is n else "not_delivered"
    except queue.Empty:
        return "not_delivered"


def main() -> int:
    schema_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    root = json.loads((schema_dir / "ServerNotification.json").read_text())
    methods = {}
    for branch in root["oneOf"]:
        m = branch["properties"]["method"]["enum"][0]
        methods[m] = branch["properties"].get("params") or {"type": "object"}
    client = CodexClient()  # never started: only the notification coercion path is exercised
    rows = {}
    for m, pschema in sorted(methods.items()):
        row: dict = {"in_sdk_registry": m in NOTIFICATION_MODELS}
        for label, full in (("minimal", False), ("maximal", True)):
            s = sample(pschema, root, full)
            try:
                jsonschema.validate(s, {**resolve(pschema, root), "definitions": root["definitions"]})
                row[f"{label}_native_valid"] = True
            except jsonschema.ValidationError as error:
                row[f"{label}_native_valid"] = False
                row[f"{label}_native_error"] = error.message[:160]
            n = client._coerce_notification(m, s)
            row[f"{label}_sdk_typed"] = not isinstance(n.payload, UnknownNotification)
            row[f"{label}_delivered"] = deliver(n)
        req = resolve(pschema, root).get("required") or []
        if req:
            bad = copy.deepcopy(sample(pschema, root, False))
            bad.pop(req[0], None)
            row["negative_control_untyped"] = isinstance(client._coerce_notification(m, bad).payload, UnknownNotification)
        rows[m] = row
    both_valid = [m for m, r in rows.items() if r["minimal_native_valid"] and r["maximal_native_valid"]]
    summary = {
        "native_methods": len(methods), "sdk_registry": len(NOTIFICATION_MODELS),
        "native_equals_sdk_registry": set(methods) == set(NOTIFICATION_MODELS),
        "native_only": sorted(set(methods) - set(NOTIFICATION_MODELS)),
        "sdk_only": sorted(set(NOTIFICATION_MODELS) - set(methods)),
        "samples_native_valid_both": len(both_valid),
        "typed_minimal": sum(r["minimal_sdk_typed"] for r in rows.values()),
        "typed_maximal": sum(r["maximal_sdk_typed"] for r in rows.values()),
        "typed_both_among_native_valid": sum(rows[m]["minimal_sdk_typed"] and rows[m]["maximal_sdk_typed"] for m in both_valid),
        "untyped_among_native_valid": sorted(m for m in both_valid if not (rows[m]["minimal_sdk_typed"] and rows[m]["maximal_sdk_typed"])),
        "negative_controls": sum("negative_control_untyped" in r for r in rows.values()),
        "negative_controls_untyped": sum(bool(r.get("negative_control_untyped")) for r in rows.values()),
        "delivered": {k: sum(r[f"{v}_delivered"] == k for r in rows.values() for v in ("minimal", "maximal"))
                      for k in ("turn", "login", "global", "not_delivered")},
        "sdk_more_lenient_than_native": sorted(m for m, r in rows.items() if r.get("negative_control_untyped") is False),
        "not_native_valid": sorted(m for m, r in rows.items() if not (r["minimal_native_valid"] and r["maximal_native_valid"])),
    }
    out.write_text(json.dumps({"summary": summary, "methods": rows}, indent=2) + "\n")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
