#!/usr/bin/env python3
"""Read-only: every Notification type the installed native Claude Code binary knows, and the decision each one carries.

The client passes the type to Notification hooks as `notification_type`. In the bundled code the matcher values of the Notification event are the array that a spread identifier names
plus a few more values (`matcherMetadata:{fieldToMatch:"notification_type",values:[...<name>,"elicitation_complete","elicitation_response"]}`), and a type is emitted at call sites
written as `notificationType:"<type>"` (other emit sites use other spellings, so that count is a lower bound and a count of 0 does not prove that a type is never emitted).
The spread name is a minified identifier: it can contain `$`, and the same short name is reused for unrelated values in other scopes (2.1.283: `P$o=["permission_prompt",...]` beside
`var P$o=new Set([...])`). The script therefore resolves the name to the array literal assigned to it (`<name>=["a","b",...]` as a complete initializer that is not a member access, quoted lowercase names only), never picks an array by its
contents or length, and fails closed when the name has no such assignment, two different ones, an array without `permission_prompt` and `idle_prompt`, when the binary holds no
catalog, or when it declares a catalog whose values the reader cannot parse. Every catalog it finds counts (their union is the matcher-value set). The result is joined with DECISIONS below: the one table the repository's test also reads, so a type
has one decision in one place.

Each decision is `ring` (the overlay's matcher names it) or `quiet`, with whether the hooks reference documents the type (fetched 2026-09-29) and the reason. The script exits 1 when a
type in the binary has no entry (`UNKNOWN`), when a decision disagrees with the overlay's matcher, and when the catalog or its base array cannot be resolved (a reader that finds nothing,
or the wrong thing, must not pass): rerun it after each client update.
usage: python3 -B notification_types_scan.py [<binary>] [<checkout>]   (run from the checkout root; the default binary is the installed ~/.local/bin/claude)"""
import json, mmap, os, re, sys
from pathlib import Path

DECISIONS = {
    # 2026-10-06 Q55: installed Claude Code 2.1.291; exact host gate output/ruling in
    # docs/decisions/2026-10-06-auth-storage-failure-notification.md (DECISIONS row).
    "auth_storage_failure": ("ring", False, "2026-10-06 Q55: a credential-storage or sign-in failure that needs the user is an escalation under the quiet-bell-only-for-escalations rule; observed by the installed Claude Code 2.1.291 host currency gate"),
    "permission_prompt": ("ring", True, "a tool or a sandboxed command's network request waits for approval and the person has not typed for about 6 s since the prompt appeared (terminal sessions; a session hosted by the Agent SDK sends it about 6 s after the request whether or not the person types)"),
    "elicitation_dialog": ("ring", True, "an MCP server opened a form and the person has not typed for about 6 s"),
    "elicitation_url_dialog": ("ring", True, "an MCP server asked the person to open a URL and they have not typed for about 6 s"),
    "agent_needs_input": ("ring", True, "a background session waits for input while agent view is open, or an agent-team setup question waits"),
    "quota_auto_resume_stale": ("ring", True, "a usage limit reset while the computer slept over 30 minutes: the client waits for Enter"),
    "quota_auto_resume_disabled": ("ring", True, "the client ended its usage-limit wait without continuing the task"),
    "worker_permission_prompt": ("ring", False, "an agent-team teammate needs permission or network access (team inbox poller)"),
    "push_notification": ("ring", False, "the model's own PushNotification, which a local session sends only while the client judges the person away (the terminal's focus report, else 60 s without input; a remote workspace skips the check)"),
    # 2026-10-09 F10: pinned 2.1.295 $.ui.notify emitter and hooks-reference check;
    # source and before/after installed-client proof share the floor decision record.
    "plugin_notification": ("quiet", False, "Claude Code 2.1.295 plugin $.ui.notify forwards arbitrary plugin text/title without an intrinsic approval or input wait; quiet under the escalation-only bell rule (docs/decisions/2026-10-09-claude-code-floor.md)"),
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

CATALOG = re.compile(rb'fieldToMatch:"notification_type",values:\[\.\.\.([\w$]+)((?:,"[a-z_]+")*)\](?=[,;)}])')   # a complete literal: `values:[...x,"a"].concat([...])` is not recognized
CANDIDATE = re.compile(rb'fieldToMatch\s*:\s*"notification_type"')   # every place a matcher catalog is declared, whatever the spelling of its values
NAMES_ARRAY = rb'\[("[a-z_]+"(?:,"[a-z_]+")*)\]'
REQUIRED_IN_BASE = frozenset({"permission_prompt", "idle_prompt"})


def names_of(items):
    return [item.strip(b'"').decode() for item in items.split(b",") if item]


def assignment_pattern(spread):
    """`<spread>=["a","b",...]` as a COMPLETE initializer (the literal is followed by `,` `;` `)` or `}`, so `<spread>=[...].concat([...])` is not one) where the name is not the tail of a longer identifier;
    `new Set([...])`, `new Map(...)` and other values do not match. Member assignments are excluded by `member_access`."""
    return rb'(?<![\w$])' + re.escape(spread) + b'=' + NAMES_ARRAY + rb'(?=[,;)}])'


def member_access(data, start):
    """True when the token before `start`, skipping whitespace and /* */ comments, is a dot: the name is a property (`obj.name`, `obj. name`, `obj./* c */name`), not a variable."""
    i = start
    while i > 0:
        while i > 0 and data[i - 1:i] in (b" ", b"\t", b"\n", b"\r"):
            i -= 1
        if data[max(0, i - 2):i] == b"*/":
            j = data.rfind(b"/*", max(0, i - 4000), i - 2)   # a bounded look back
            if j < 0:
                return False
            i = j
            continue
        break
    return data[i - 1:i] == b"."


def assignments(data, spread):
    """The array literals assigned to `spread` as variables (a set of tuples of names)."""
    return {tuple(names_of(m.group(1))) for m in re.finditer(assignment_pattern(spread), data) if not member_access(data, m.start())}


def scan(binary):
    """Read the binary and return {"types": {name: {"notificationType_literals": n, "matcher_value": bool}}, "catalog_found": bool, "catalogs_resolved": bool,
    "catalogs": [{"spread": name, "base_candidates": n, "base_size": n, "extras": [names]}], "catalog_candidates": n, "unrecognized_catalogs": n, "base_array_size": n, "catalog_extra_values": [names]}.
    A catalog declaration whose values the reader cannot parse (`unrecognized_catalogs`) makes the scan unresolved: every declared catalog must be recognized.
    Scope limits: the array is read where it is assigned, so a later mutation of it (`Ojo.push(...)`) is invisible to a static read; minified names are not resolved by scope, so a plain assignment of the same short name in another scope, beside a catalog that spreads a function parameter, would be taken for the
    catalog's array (the three release binaries do not do this; two different arrays, no array, or a base without permission_prompt and idle_prompt fail closed)."""
    with open(binary, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        literals = {}
        for found in re.finditer(rb'notificationType:"([a-z][a-z0-9_]*)"', data):
            name = found.group(1).decode()
            literals[name] = literals.get(name, 0) + 1
        catalogs, matcher_values = [], []
        recognized = {found.start() for found in CATALOG.finditer(data)}
        unrecognized = [found.start() for found in CANDIDATE.finditer(data) if found.start() not in recognized]   # declared catalogs whose values the reader cannot parse
        for found in CATALOG.finditer(data):
            spread = found.group(1)
            arrays = assignments(data, spread)
            base = list(next(iter(arrays))) if len(arrays) == 1 else []
            extras = names_of(found.group(2))
            catalogs.append({"spread": spread.decode(), "base_candidates": len(arrays), "base_size": len(base), "extras": extras, "base_ok": REQUIRED_IN_BASE <= frozenset(base)})
            matcher_values += base + extras
    seen = frozenset(matcher_values)
    names = sorted(frozenset(literals) | seen)
    return {"types": {name: {"notificationType_literals": literals.get(name, 0), "matcher_value": name in seen} for name in names},
            "catalog_found": bool(catalogs), "catalogs_resolved": bool(catalogs) and all(c["base_ok"] for c in catalogs) and not unrecognized,
            "catalog_candidates": len(recognized) + len(unrecognized), "unrecognized_catalogs": len(unrecognized),
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
              "catalogs_resolved": found["catalogs_resolved"], "catalogs": found["catalogs"], "catalog_candidates": found["catalog_candidates"], "unrecognized_catalogs": found["unrecognized_catalogs"],
              "catalog_extra_values": found["catalog_extra_values"], "matcher_values": sum(1 for r in rows.values() if r["matcher_value"]),
              "unknown": sorted(n for n, r in rows.items() if r["decision"] == "UNKNOWN"),
              "decision_disagrees_with_the_overlay": sorted(n for n, r in rows.items() if r["decision"] != "UNKNOWN" and (r["decision"] == "ring") != r["overlay_matcher_names_it"]),
              "decided_but_not_in_this_binary": sorted(n for n in DECISIONS if n not in found["types"])}
    print(json.dumps(report, indent=2))
    reader_blind = not found["catalog_found"] or not found["catalogs_resolved"]
    return 1 if report["unknown"] or report["decision_disagrees_with_the_overlay"] or reader_blind else 0


if __name__ == "__main__":
    sys.exit(main())
