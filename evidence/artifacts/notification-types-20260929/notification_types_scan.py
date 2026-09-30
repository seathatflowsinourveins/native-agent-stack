#!/usr/bin/env python3
"""Read-only: every Notification type the installed native Claude Code binary knows, and the decision each one carries.

The client passes the type to Notification hooks as `notification_type`. In the bundled code the matcher values of the Notification event are one 15-item base array plus two
more (`matcherMetadata:{fieldToMatch:"notification_type",values:[...<base>,"elicitation_complete","elicitation_response"]}`, where the spread name is a minified identifier that can
contain `$`), and a type is emitted at call sites written as `notificationType:"<type>"` (other emit sites use other spellings, so that count is a lower bound and a count of 0 does
not prove that a type is never emitted). The script maps the binary, reads the base array, the catalog's extra values and the literals, and joins them with DECISIONS below: the one
table the repository's test also reads, so a type has one decision in one place.

Each decision is `ring` (the overlay's matcher names it) or `quiet`, with whether the hooks reference documents the type (fetched 2026-09-29) and the reason. The script exits 1 when a type
in the binary has no entry (`UNKNOWN`), when a decision disagrees with the overlay's matcher, and when it cannot find the base array or the catalog (a reader that finds nothing must not
pass): rerun it after each client update.
usage: python3 -B notification_types_scan.py [<binary>] [<checkout>]   (run from the checkout root; the default binary is the installed ~/.local/bin/claude)"""
import json, mmap, os, re, sys
from pathlib import Path

DECISIONS = {
    "permission_prompt": ("ring", True, "a tool or a sandboxed command's network request waits for approval and the person has been away about 6 s"),
    "elicitation_dialog": ("ring", True, "an MCP server opened a form and the person has not typed for about 6 s"),
    "elicitation_url_dialog": ("ring", True, "an MCP server asked the person to open a URL and they have not typed for about 6 s"),
    "agent_needs_input": ("ring", True, "a background session waits for input while agent view is open, or an agent-team setup question waits"),
    "quota_auto_resume_stale": ("ring", True, "a usage limit reset while the computer slept over 30 minutes: the client waits for Enter"),
    "quota_auto_resume_disabled": ("ring", True, "the client ended its usage-limit wait without continuing the task"),
    "worker_permission_prompt": ("ring", False, "an agent-team teammate needs permission or network access (team inbox poller)"),
    "push_notification": ("ring", False, "the model's own PushNotification, which the tool sends only while the client judges the person away (the terminal's focus report, else 60 s without input)"),
    "idle_prompt": ("quiet", True, "a finished-and-waiting ping about 60 s after a turn: the noise the record removed"),
    "auth_success": ("quiet", True, "authentication completed; the person just did it"),
    "elicitation_complete": ("quiet", True, "an MCP elicitation finished; nothing waits for the person"),
    "elicitation_response": ("quiet", True, "the client sent an elicitation response; nothing waits for the person"),
    "agent_completed": ("quiet", True, "a background session finished or failed while agent view is open: the person is looking at it (a failure is silenced too)"),
    "quota_auto_resume_fired": ("quiet", True, "the client continued the task by itself after a usage limit; no one needs to act"),
    "computer_use_enter": ("quiet", False, "the computer-use tool starts driving a desktop, not a request for the person; in 2.1.285 the name occurs once, in the matcher list, so a text search found no emit site (it cannot prove absence)"),
    "computer_use_exit": ("quiet", False, "the client says \"Claude is done using your computer\" when the computer-use tool finishes; nothing waits for the person"),
    "model_refusal_fallback": ("quiet", False, "a fallback after a model refusal; this host sets CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK=1, and in 2.1.285 the name is a matcher value and a system-message subtype with no `notificationType:` call site found (a text search cannot prove absence)"),
}


def scan(binary):
    """Read the binary and return {"types": {name: {"notificationType_literals": n, "matcher_value": bool}}, "base_array_size": n, "catalog_found": bool, "catalog_extra_values": [names]}."""
    with open(binary, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        literals = {}
        for found in re.finditer(rb'notificationType:"([a-z][a-z0-9_]*)"', data):
            name = found.group(1).decode()
            literals[name] = literals.get(name, 0) + 1
        base = []
        for found in re.finditer(rb'\[("(?:[a-z_]+)"(?:,"[a-z_]+"){3,})\]', data):
            items = [item.strip(b'"').decode() for item in found.group(1).split(b",")]
            if "permission_prompt" in items and "idle_prompt" in items and len(items) > len(base):
                base = items
        catalog = re.search(rb'fieldToMatch:"notification_type",values:\[\.\.\.[\w$]+((?:,"[a-z_]+")*)\]', data)
        extras = [item.strip(b'"').decode() for item in catalog.group(1).split(b",") if item] if catalog else []
    matcher_values = set(base) | set(extras)
    names = sorted(set(literals) | matcher_values)
    return {"types": {name: {"notificationType_literals": literals.get(name, 0), "matcher_value": name in matcher_values} for name in names},
            "base_array_size": len(base), "catalog_found": catalog is not None, "catalog_extra_values": extras}


def main():
    args = [a for a in sys.argv[1:]]
    binary = Path(args[0]) if args and not Path(args[0]).is_dir() else Path(os.path.realpath(Path.home() / ".local/bin/claude"))
    worktree = Path(args[-1]) if args and Path(args[-1]).is_dir() else Path(".")
    overlay = json.loads((worktree / "adoption/templates/claude.settings.linux-wsl2.overlay.json").read_text(encoding="utf-8"))
    ring_in_overlay = frozenset(overlay["hooks"]["Notification"][0]["matcher"].split("|"))
    found = scan(binary)
    rows = {}
    for name, seen in found["types"].items():
        decision = DECISIONS.get(name)
        rows[name] = {**seen, "decision": decision[0] if decision else "UNKNOWN", "documented_in_the_hooks_reference": decision[1] if decision else None,
                      "overlay_matcher_names_it": name in ring_in_overlay}
    report = {"binary": binary.name, "types": rows, "base_array_size": found["base_array_size"], "catalog_found": found["catalog_found"],
              "catalog_extra_values": found["catalog_extra_values"], "matcher_values": sum(1 for r in rows.values() if r["matcher_value"]),
              "unknown": sorted(n for n, r in rows.items() if r["decision"] == "UNKNOWN"),
              "decision_disagrees_with_the_overlay": sorted(n for n, r in rows.items() if r["decision"] != "UNKNOWN" and (r["decision"] == "ring") != r["overlay_matcher_names_it"]),
              "decided_but_not_in_this_binary": sorted(n for n in DECISIONS if n not in found["types"])}
    print(json.dumps(report, indent=2))
    reader_blind = found["base_array_size"] == 0 or not found["catalog_found"]
    return 1 if report["unknown"] or report["decision_disagrees_with_the_overlay"] or reader_blind else 0


if __name__ == "__main__":
    sys.exit(main())
