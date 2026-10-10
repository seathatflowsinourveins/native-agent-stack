# MCP (`mcp-surfaces`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## mcp-config-tool-search

**Status:** default. **Default:** Native MCP configuration with tool search at its default (tools deferred), default output caps and `alwaysLoad` unset

- **Route:** User-scope registrations; `alwaysLoad: true` only for a small server used on every turn; `ENABLE_TOOL_SEARCH=true` behind a non-first-party base URL
- **Alternatives, ranked:** 1. modelcontextprotocol/inspector 2.10.1 for inspection (overlap with mcporter to resolve)
- **Rejected:** `ENABLE_TOOL_SEARCH=auto:N`; Disabling tool search; Raising `MAX_MCP_OUTPUT_TOKENS` globally
- **Evidence:** mcp.md tool search and output limits; mcp-O2, O3, O4, O5, O6, O7
- **Notes:** Registrations drift between host and template (qmd stdio versus HTTP, ports, a server key): G6b. Verified: on user-scope registrations `alwaysLoad: true` loads every tool of that server upfront (the per-tool opt-out works only for --mcp-config, SDK and plugin servers); image results stay under MAX_MCP_OUTPUT_TOKENS; the upfront fallback behind a non-first-party base URL dates from 2.1.70.
- **Supersedes:** topic: MCP tool loading (native deferral converged)
- **Overturn when:** A measured context or quality gap from deferral, or a release changes tool-search defaults.

## mcp-shared-servers

**Status:** trial. **Default:** One vendor-native Streamable HTTP service per heavy MCP server, admitted one server at a time after a PSS before/after and tool-surface parity check

- **Route:** Registered with `claude mcp add --transport http --scope user`; stdio stays for servers without an HTTP mode
- **Alternatives, ranked:** 1. smart-mcp-proxy/mcpproxy-go (first trial alternative); 2. 1mcp-app/agent
- **Rejected:** A proxy in front of a server that already speaks HTTP, without a measured advantage; `claude mcp serve` as a pooling mechanism
- **Evidence:** mcp.md HTTP transport; docs/decisions/2026-10-08-qmd-shared-mcp.md (QMD pilot); Baseline RSS per group: serena plus pyright 5.7 GiB, chrome-devtools 2.6, context-mode 2.6, qmd 2.0
- **Notes:** Measurement owed: serena with pyright in three arms (per-session stdio, one native HTTP instance, behind mcpproxy-go): PSS, process-exporter RSS, latency and tool parity. Adjudicated mixed (native HTTP default, mcpproxy-go first alternative); the refuter upheld it. Admission gate per server, before PSS and tool parity: binds 127.0.0.1 only; rejects an invalid Origin with 403 (MCP 2026-07-28 Streamable HTTP); authenticates where the vendor supports it, through headersHelper, never literal values in a committed template; register through adoption/mcp/claude-user.json and re-render. Servers that scope by the client's project or working directory (serena) are excluded from sharing across projects.
- **Overturn when:** The three-arm run shows the proxy ahead on memory, latency or reliability on our servers.
