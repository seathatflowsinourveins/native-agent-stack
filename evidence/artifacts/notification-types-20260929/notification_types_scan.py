#!/usr/bin/env python3
"""Read-only: every Notification type the installed native Claude Code binary knows, and the decision each one carries.

The client passes the type to Notification hooks as `notification_type`. In the bundled code the matcher values of the Notification event are the array that a spread identifier names
plus a few more values (`matcherMetadata:{fieldToMatch:"notification_type",values:[...<name>,"elicitation_complete","elicitation_response"]}`), and a type is emitted at call sites
written as `notificationType:"<type>"` (other emit sites use other spellings, so that count is a lower bound and a count of 0 does not prove that a type is never emitted).
The spread name is a minified identifier: it can contain `$`, and the same short name is reused for unrelated values in other scopes (2.1.283: `P$o=["permission_prompt",...]` beside
`var P$o=new Set([...])`). The script therefore resolves the name to the array literal assigned to it (`<name>=["a","b",...]`, quoted lowercase names only), never picks an array by its
contents or length, and fails closed when the name has no such assignment, two different ones, an array without `permission_prompt` and `idle_prompt`, or when the binary holds no
catalog. Every catalog it finds counts (their union is the matcher-value set). The result is joined with DECISIONS below: the one table the repository's test also reads, so a type
has one decision in one place.

Each decision is `ring` (the overlay's matcher names it) or `quiet`, with whether the hooks reference documents the type (fetched 2026-09-29) and the reason. The script exits 1 when a
type in the binary has no entry (`UNKNOWN`), when a decision disagrees with the overlay's matcher, and when the catalog or its base array cannot be resolved (a reader that finds nothing,
or the wrong thing, must not pass): rerun it after each client update.
usage: python3 -B notification_types_scan.py [<binary>] [<checkout>]   (run from the checkout root; the default binary is the installed ~/.local/bin/claude)"""
import json, mmap, os, re, sys
from pathlib import Path

DECISIONS = {
    "permission_prompt": ("ring", True, "a tool or a sandboxed command's network request waits for approval and the person has not typed for about 6 s since the prompt appeared (terminal sessions; a session hosted by the Agent SDK sends it about 6 s after the request whether or not the person types)"),
    "elicitation_dialog": ("ring", True, "an MCP server opened a form and the person has not typed for about 6 s"),
    "elicitation_url_dialog": ("ring", True, "an MCP server asked the person to open a URL and they have not typed for about 6 s"),
    "agent_needs_input": ("ring", True, "a background session waits for input while agent view is open, or an agent-team setup question waits"),
    "quota_auto_resume_stale": ("ring", True, "a usage limit reset while the computer slept over 30 minutes: the client waits for Enter"),
    "quota_auto_resume_disabled": ("ring", True, "the client ended its usage-limit wait without continuing the task"),
    "worker_permission_prompt": ("ring", False, "an agent-team teammate needs permission or network access (team inbox poller)"),
    "push_notification": ("ring", False, "the model's own PushNotification, which a local session sends only while the client judges the person away (the terminal's focus report, else 60 s without input; a remote workspace skips the check)"),
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

CATALOG = re.compile(rb'fieldToMatch:"notification_type",values:\[\.\.\.([\w$]+)((?:,"[a-z_]+")*)\]')
NAMES_ARRAY = rb'\[("[a-z_]+"(?:,"[a-z_]+")*)\]'
REQUIRED_IN_BASE = frozenset({"permission_prompt", "idle_prompt"})


def names_of(items):
    return [item.strip(b'"').decode() for item in items.split(b",") if item]


def assignment_pattern(spread):
    """`<spread>=["a","b",...]` where the name is not the tail of a longer identifier; `new Set([...])`, `new Map(...)` and other values do not match."""
    return rb'(?<![\w$])' + re.escape(spread) + b'=' + NAMES_ARRAY


def scan(binary):
    """Read the binary and return {"types": {name: {"notificationType_literals": n, "matcher_value": bool}}, "catalog_found": bool, "catalogs_resolved": bool,
    "catalogs": [{"spread": name, "base_candidates": n, "base_size": n, "extras": [names]}], "base_array_size": n, "catalog_extra_values": [names]}."""
    with open(binary, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        literals = {}
        for found in re.finditer(rb'notificationType:"([a-z][a-z0-9_]*)"', data):
            name = found.group(1).decode()
            literals[name] = literals.get(name, 0) + 1
        catalogs, matcher_values = [], []
        for found in CATALOG.finditer(data):
            spread = found.group(1)
            arrays = {tuple(names_of(a.group(1))) for a in re.finditer(assignment_pattern(spread), data)}
            base = list(next(iter(arrays))) if len(arrays) == 1 else []
            extras = names_of(found.group(2))
            catalogs.append({"spread": spread.decode(), "base_candidates": len(arrays), "base_size": len(base), "extras": extras, "base_ok": REQUIRED_IN_BASE <= frozenset(base)})
            matcher_values += base + extras
    seen = frozenset(matcher_values)
    names = sorted(frozenset(literals) | seen)
    return {"types": {name: {"notificationType_literals": literals.get(name, 0), "matcher_value": name in seen} for name in names},
            "catalog_found": bool(catalogs), "catalogs_resolved": bool(catalogs) and all(c["base_ok"] for c in catalogs),
            "catalogs": [{k: v for k, v in c.items() if k != "base_ok"} for c in catalogs],
            "base_array_size": max((c["base_size"] for c in catalogs), default=0),
            "catalog_extra_values": list(dict.fromkeys(item for c in catalogs for item in c["extras"]))}


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
              "catalogs_resolved": found["catalogs_resolved"], "catalogs": found["catalogs"],
              "catalog_extra_values": found["catalog_extra_values"], "matcher_values": sum(1 for r in rows.values() if r["matcher_value"]),
              "unknown": sorted(n for n, r in rows.items() if r["decision"] == "UNKNOWN"),
              "decision_disagrees_with_the_overlay": sorted(n for n, r in rows.items() if r["decision"] != "UNKNOWN" and (r["decision"] == "ring") != r["overlay_matcher_names_it"]),
              "decided_but_not_in_this_binary": sorted(n for n in DECISIONS if n not in found["types"])}
    print(json.dumps(report, indent=2))
    reader_blind = not found["catalog_found"] or not found["catalogs_resolved"]
    return 1 if report["unknown"] or report["decision_disagrees_with_the_overlay"] or reader_blind else 0


if __name__ == "__main__":
    sys.exit(main())
