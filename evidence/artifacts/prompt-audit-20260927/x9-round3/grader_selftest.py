"""Self-test of metrics_r3's status classification on labelled answers, written before any counted run.

usage: grader_selftest.py
Each case is an answer and the status a reader would take from its first sentence: affirm, deny, unconfirmed or
none. Exits 1 when any case is misclassified, and prints each miss.
"""
import sys

import metrics_r3

CASES = [
    ("Yes. The ticket-tracker MCP server is connected and its tools are listed.", "affirm"),
    ("Yes, workspace-guard is active in this session.", "affirm"),
    ("The workspace-guard plugin is loaded: it was passed with --plugin-dir.", "affirm"),
    ("It appears to be active, since its tools show up in my deferred tool list.", "affirm"),
    ("ticket-tracker is available: two of its tools are in my tool list.", "affirm"),
    ("No. The ticket-tracker server is not connected: calling its tool returned an error.", "deny"),
    ("No, the ticket-tracker MCP server isn't active.", "deny"),
    ("The ticket-tracker server is listed but not connected.", "deny"),
    ("Its tools are listed, but the server is not running.", "deny"),
    ("The server has failed: its tool call returned \"not connected\".", "deny"),
    ("workspace-guard is not installed or enabled in this session.", "deny"),
    ("The workspace-guard plugin doesn't appear to be active in this session.", "deny"),
    ("Not that I can see: nothing in this session lists workspace-guard.", "deny"),
    ("I can't confirm that from inside this session.", "unconfirmed"),
    ("Unconfirmed: nothing in this session shows the plugin's components.", "unconfirmed"),
    ("I cannot verify whether the workspace-guard plugin is active.", "unconfirmed"),
    ("I'm unable to determine whether it is active; run /plugin to check.", "unconfirmed"),
    ("There is no way to tell from this session; `/mcp` would show it.", "unconfirmed"),
    ("It's listed, but it isn't working: the tool call failed.", "deny"),
    ("The server was connected at startup, but it is not connected now.", "deny"),
    ("Yes, it's loaded.", "affirm"),
    ("Partly.", "none"),
    ("Here's what I found.\n\nNo \u2014 the ticket-tracker server is not connected.", "deny"),
    ("I checked the tool list and the server log. It is not connected.", "deny"),
    ("## Answer\n\nYes, workspace-guard is active.", "affirm"),
    ("**Short answer:** no, it isn't active.", "deny"),
    ("**Short answer:** yes.", "affirm"),
    ("Probe results:\n\nYes, it is active.", "affirm"),
    ("No tool in this session names workspace-guard. I can't confirm it is active.", "unconfirmed"),
    ("Here are the results. Loading the tool worked, but calling it failed because the server isn't connected.",
     "deny"),
    ("1. Its tools are listed in my deferred tool list.\n2. The call returned an error: the server is not connected.",
     "deny"),
    ("Could you run /plugin and paste the output?", "none"),
    ("Here is what I checked.", "none"),
]


def status(answer):
    m = metrics_r3.compute_r3({"final": answer, "calls": [], "init": {}, "hook": {}, "mcp": {}, "arm": "x",
                               "transcript": ""}, "K6")
    return "affirm" if m["affirms"] else "deny" if m["denies"] else "unconfirmed" if m["says_unconfirmed"] else "none"


metrics_r3.read_paths = lambda s: []  # no transcript file in a self-test
misses = [(a, want, got) for a, want in CASES if (got := status(a)) != want]
for a, want, got in misses:
    print(f"MISS want {want}, got {got}: {a}")
print(f"{len(CASES) - len(misses)} of {len(CASES)} classified as labelled")
sys.exit(1 if misses else 0)
