@AGENTS.md

Before claiming a plugin or MCP server is active, verify the relevant component in this
session: tools (including deferred tools via ToolSearch), skills, agents or hooks.
Distinguish listed availability from successful execution. Use available read-only
diagnostics first; if the claim remains unresolved, ask for the relevant `/plugin`,
`/mcp` or `/context` output. Invoke a command through Skill only if the installed
client exposes it there.

A session that acts as the command center reads `docs/command-center.md` first. How a candidate
is installed and finalized follows `docs/decisions/2026-10-07-clean-upstream-install-finalizes-a-candidate.md`.

## Compact Instructions

When compacting, preserve each modified file's branch or worktree, each test or
acceptance command with its exit code, each open claim's provenance (URL,
repo@pin:path:line or command), failed attempts, open review findings,
unresolved gaps and any workflow run ID needed to resume.
