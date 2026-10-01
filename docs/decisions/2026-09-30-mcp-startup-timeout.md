# Decision: one MCP server startup timeout of 120 s in the Claude settings template (2026-09-30)

**Decided by:** the coordinator's F3 delta of 2026-09-30, which came from the unit F4 cross-family review. The Gate A
owner accepted the key (`MCP_TIMEOUT`), the scope (the template's `env` object) and the value (`"120000"`). The host
batch applies it; this change applies nothing on a host. The Gate A owner's review of PR #553 asked for this record.

**Scope:** `adoption/templates/claude.settings.template.json` `env.MCP_TIMEOUT`, the step-4 note in
`adoption/bootstrap.md` and `tests/test_install_claude_profile.py` `McpStartupTimeoutTemplateTests`.

## Context

- Claude Code's MCP server startup timeout is `MCP_TIMEOUT`: "Timeout in milliseconds for MCP server startup
  (default: 30000, or 30 seconds)" (env-vars page, L470). The MCP page gives the same variable for the startup timeout
  (L405). A server's own `timeout` field sets that server's tool-execution timeout only (L406 and L411).
- The Codex template gives `serena` and `context-mode` 60 s and `socraticode` 120 s (`startup_timeout_sec`,
  `adoption/templates/codex.config.template.toml`). Under Claude Code's 30 s default, a server that needs longer fails
  in Claude while it connects under Codex.
- No record measures the start-up time of the stack's servers on the reference host.

## Alternatives

1. **Keep Claude Code's 30 s default.** Rejected until measured: the Codex lane already gives two of the same servers
   60 s and one 120 s, and no start-up distribution shows every stack server ready within 30 s.
2. **A per-server startup timeout.** Not available:
   - Claude Code 2.1.286 `claude mcp add --help` lists eight options, none for a timeout or start-up (read 2026-09-30
     with a scratch `HOME`; help text sha256 `3809ec89…`). The F3 delta recorded the same for 2.1.285.
   - The MCP page documents no per-server startup field; the per-server `timeout` bounds tool calls.
3. **`MCP_CONNECT_TIMEOUT_MS` or `CLAUDE_CODE_MCP_STARTUP_WAIT_MS`.** Not substitutes:
   - `MCP_CONNECT_TIMEOUT_MS` bounds how long blocking startup waits for the connection batch (default 5,000 ms). The
     env-vars page calls it "Distinct from `MCP_TIMEOUT`, which bounds an individual server's connect attempt" (L460).
   - `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` bounds how long a non-interactive session's first turn waits for pending
     servers (L317).
   - Neither extends a server's own startup deadline.

## Decision

- The template's `env` sets `MCP_TIMEOUT` to `"120000"`. The one global value equals the Codex template's slowest
  `startup_timeout_sec` (`socraticode`, 120 s) and applies to every MCP server Claude Code starts.
- Cost: a server that never starts is marked failed after up to 120 s instead of 30 s.
  - Interactive startup is non-blocking by default, so the wait delays only that server's tools (env-vars L459).
  - A `-p` run with `--mcp-config` waits for still-pending servers before its first turn, "up to the `MCP_TIMEOUT`
    startup timeout" (headless page L240). There the first turn can wait up to 120 s.
  - A run that needs a shorter first-turn wait sets `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` (L317).
- `McpStartupTimeoutTemplateTests` holds the key and value.

## Overturn condition

- **Measured start-up.** Suppose a start-up distribution on the reference host shows every stack MCP server ready
  within 30 s. Then drop the key and return to the default.
- **Upstream option.** Suppose a Claude Code release adds a per-server startup option, such as a `claude mcp add` flag
  or a server-entry field. Then set the value on the servers that need it and drop the global key.
- **Codex change.** Suppose the Codex template's slowest `startup_timeout_sec` changes. Then keep the two equal, or
  record why they differ.

## Sources

Read 2026-09-30. Page hashes are of the fetched markdown.

- Claude Code env-vars reference, <https://code.claude.com/docs/en/env-vars> (sha256 `a908ea67…`): L317
  (`CLAUDE_CODE_MCP_STARTUP_WAIT_MS`), L459 (`MCP_CONNECTION_NONBLOCKING`), L460 (`MCP_CONNECT_TIMEOUT_MS`) and L470
  (`MCP_TIMEOUT`).
- Claude Code MCP page, <https://code.claude.com/docs/en/mcp> (sha256 `86b6d45a…`): L405-406 and L411.
- Claude Code headless page, <https://code.claude.com/docs/en/headless> (sha256 `f2d9f93d…`): L240.
- Claude Code 2.1.286 `claude mcp add --help` (sha256 `3809ec89…`).
- `adoption/templates/codex.config.template.toml`: the `startup_timeout_sec` of `serena`, `socraticode` and
  `context-mode`.
