#!/usr/bin/env python3
"""Generate an owned, synthetic MCP `tools/list`-shaped fixture.

The fix-round finding for headroom-0.38.0-upgrade-recovery noted the original
check used fixtures/rag-note.md (351 bytes / 75 tokens), which is small and
low-entropy enough that Headroom's router selected a no-op transform, so the
check never exercised real compression. This script builds a larger,
repetitive, MCP-tool-listing-shaped JSON document (the kind of artifact the
0.37.0 receipt's own MCP-listing fixture exercised) so the corrected re-run
has a fixture that can actually trigger compression.

This is an owned synthetic acceptance artifact, not captured production MCP
traffic: it reuses the tool names and boilerplate JSON-schema shapes visible
in this repository's own MCP server instructions (jcodemunch, serena,
ai-memory, context-mode, socraticode) and repeats/varies them across many
synthetic tool entries, matching the repetition-based synthetic-fixture
convention already used by evidence/receipts/native-token-clean-prefix-
20260920.json (fixtures/records.json repeated across 300 rows).
"""
from __future__ import annotations

import json
import sys

TOOL_FAMILIES = [
    ("jcodemunch", "route", "Start here: describe the task in plain words, get back an action to run against the indexed codebase."),
    ("jcodemunch", "menu", "Search the jCodeMunch action catalog when you already know roughly what you want."),
    ("jcodemunch", "order", "Dispatch any jCodeMunch action by name with order(action, args); read-only by default."),
    ("serena", "find_symbol", "Locate a symbol definition by name path within the project, optionally restricted to a relative path."),
    ("serena", "find_referencing_symbols", "Find all symbols that reference the given symbol, with surrounding context."),
    ("serena", "get_symbols_overview", "Get a top-level overview of the symbols defined in a given file or directory."),
    ("serena", "replace_symbol_body", "Replace the full body of an existing symbol identified by name path and file."),
    ("serena", "insert_after_symbol", "Insert new source text immediately after the given symbol's body."),
    ("serena", "insert_before_symbol", "Insert new source text immediately before the given symbol's body."),
    ("ai-memory", "memory_query", "Retrieve relevant memory pages, observations, or handoffs scoped to a project or globally."),
    ("ai-memory", "memory_read_page", "Read one durable memory page by its identifier, including its full body."),
    ("context-mode", "ctx_execute", "Run a command through Context Mode so large stdout/stderr is filtered outside the model."),
    ("context-mode", "ctx_search", "Search Context Mode's retained output history for a prior command's results."),
    ("socraticode", "codebase_search", "Run a conceptual semantic search over the locally indexed and embedded codebase."),
    ("socraticode", "codebase_symbol", "Fetch a single symbol's indexed summary and embedding-based neighbors."),
    ("socraticode", "codebase_impact", "Estimate the blast radius of changing a given symbol across the indexed codebase."),
]

COMMON_PROPERTIES = {
    "path": {"type": "string", "description": "Absolute or repo-relative path this action should read, write, or resolve symbols within."},
    "query": {"type": "string", "description": "Free-text or structured query describing what the caller wants to find or do."},
    "max_results": {"type": "integer", "description": "Upper bound on the number of results to return in a single call.", "default": 20},
    "include_context": {"type": "boolean", "description": "Whether to include surrounding lines or symbol context in the response.", "default": True},
    "scope": {"type": "string", "description": "Optional scope restriction such as a project name, workspace, or symbol kind filter."},
}


def build_tool_entries(repeat: int) -> list[dict]:
    entries = []
    for i in range(repeat):
        for server, name, description in TOOL_FAMILIES:
            entries.append(
                {
                    "name": f"{server}__{name}",
                    "server": server,
                    "description": description,
                    "inputSchema": {
                        "type": "object",
                        "properties": COMMON_PROPERTIES,
                        "required": ["query"] if "search" in name or "query" in name or name in ("route", "menu") else [],
                        "additionalProperties": False,
                    },
                    "annotations": {
                        "readOnlyHint": server != "serena" or name.startswith("find") or name.startswith("get"),
                        "destructiveHint": False,
                        "idempotentHint": True,
                        "variant_index": i,
                    },
                }
            )
    return entries


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdout"
    repeat = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    doc = {"tools": build_tool_entries(repeat)}
    text = json.dumps(doc, indent=2) + "\n"
    with open(out_path, "w") as f:
        f.write(text)
    sys.stderr.write(f"wrote {len(text)} bytes, {len(doc['tools'])} tool entries to {out_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
